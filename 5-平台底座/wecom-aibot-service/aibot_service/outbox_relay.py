"""outbox → aibot 通用中继（队列 `#394`）——`.51` 只落盘，笔记本侧代发。

🔴 **它存在的唯一理由**：`#282` 拍板**不得新起 webhook** ⇒ 群推一律走 aibot
部门群 chatid；而 **aibot 那条全局唯一的长连接在笔记本上，SC2/FI2 跑在
`.51`**（同一机器人多处长连接会互相踢线，2026-08-06 已真实复现 3 次踢线 ＋
一次「收得到心跳、收不到消息」的僵尸态）。两端不同机 ⇒ 按
`openspec/changes/fi2-source-inversion/design.md` 决策点 8.2 已批的 **⑵ outbox
落盘轮询**形态：`.51` 把消息写进一份 JSONL，笔记本侧的常驻服务轮询取走、经
既有那条长连接代发。

**在本模块存在之前，SC2 周报每周五 20:00 准时生成、准时写 outbox，而群里
收不到任何东西**（`#361` 收口时如实登记：`fi2-source-inversion` 0/58 未开工，
中继无人建）。

━━━ 三条硬约束（`#394` 行内逐条明写，本模块逐条对应） ━━━

**① 部门 → chatid 只用 aibot 侧那张权威 yaml 解析，不得在中继里再抄一份。**
本模块 import `department_group_chatid_mapping`，**不含任何 chatid 字面量**。
`sc2/outbox.py` 的写侧同样只写部门名、不写 chatid——两侧合起来保证全仓
只有一处知道「采购部群是哪个 chatid」。

**② 投递成功才置 `delivered:true`，失败留在 outbox 等下一轮。**
「成功」＝ `await send_markdown()` 正常返回 **且** 回执帧 `errcode` 不是非零
（判据直接复用 `delivery.py` 的 `_assert_ack_accepted`，见下方 import 处的
红字，**不另写第二套**）。落盘即持久 ⇒ 笔记本关机只是**延迟**、不是丢。

**③ 首条真实送达须人眼反查一次收件群。**
代码做不了这件事——chatid 采集只证明「机器人收到过来自该 chatid 的消息」，
**不证明它就是采购部群**。故本模块把每次投递的 `chatid` 原样写进审计与
outbox 记录（`delivered_to`），使那次人眼反查**有据可对**；反查本身是人的
动作，写在变更包 tasks 里。

━━━ 🔴 合建一份，不按场景分家（队列 `#394` 待定夺项 O-10） ━━━

SC2 与 FI2 各建一份 ＝ 两份轮询逻辑、两处踩同样的坑。本模块合建一份。

🔑 **而合建之后有一个当初没预料到的结果，如实写下来**：`#394` 原文设想的是
「按 `scenario` 字段**分流**」，实现下来发现**根本不需要分流**——记录契约
（`channel`／`department`／`to_userid`／`msgtype`／`text`）本身是场景无关的，
本模块对 `SC2` 与 `FI2` 的处理逐字节相同。`scenario` 只被**留痕**消费（审计
与日志里答「这条是谁写的」）。⇒ **新场景接入不需要改本模块一行代码**，只需
按同一契约写 outbox。这一条是把「合建」从省事升级成正确的那个理由。

━━━ 为什么长在常驻服务里，而不是另起一个计划任务 ━━━

`push_followup_letter.py`／`dispatch_followup_letters.py` 那类一次性脚本各自
`AibotConnector(...).connect()` 起一条**自己的**连接——那是每天一次的批处理，
代价可接受。**轮询不是**：一个 5 分钟一次的任务若每轮都新起一条连接，等于
每 5 分钟拿单实例约束赌一次，把 `#282` 好不容易收敛掉的踢线风险重新引回来。
故本模块设计成**由常驻服务在它已经握着的那条连接上跑的后台任务**（范式同
`liveness.run_liveness_heartbeat`），全程**零新增连接**。

━━━ 一处如实登记的取舍：宁可重发，不可静默丢 ━━━

「发送成功」与「标记 `delivered`」不可能是一个原子动作。本模块选择**发一条
标一条**（不攒批），把两者之间的窗口压到最小；窗口内进程被杀 ⇒ 下一轮会
**重发那一条**。⚠️ 重发是可见的（群里两条一样的），静默丢是不可见的——
在这个项目里后者贵得多（`#82`：机制建成 9 天、天天在跑、一条没发出去、
没人察觉）。同理，**标记失败（文件在读与写之间被改过）走 `mark_failed`
并告警**，绝不假装标成功。

⚠️ **结构性不可投递的记录（部门拼错／通道名不认识／正文空）刻意留在
outbox 里不丢弃**，只在**首次**观测到时告警一次（同一 `(文件, 行, 原因)`
本进程内不重复告警，免得 5 分钟一条把告警做成噪音）。留着的代价是
`pending()` 数字下不去——**而那正是要的**：它是这条记录还没被人处理的
唯一外部信号。
"""
from __future__ import annotations

import asyncio
import glob as _glob
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Optional

from zhuopin_platform.audit import AuditEvent, AuditLogger

# 🔴 刻意从 `delivery.py` import 这两个「私有」名字，而不是复制一份判据过来：
# 「一次发送算不算被企微接受」在本仓库只应有一个答案。`_assert_ack_accepted`
# 的成因见 `delivery.py` 里 `#326` 那整段红字（SDK 今天替我们抛异常纯属它的
# 内部实现选择，本仓库这一侧独立断言 errcode 是纵深防御）。若哪天要把它们
# 提成公开名，两处一起改——但**不要在这里另写一个看起来一样的**。
from .delivery import DeliveryAckError, _assert_ack_accepted  # noqa: PLC2701
from .department_group_chatid_mapping import load_department_group_chatid_mapping
from .error_text import describe_exception

#: 群通报通道——`department` 经权威 yaml 解析成群 chatid。
CHANNEL_GROUP = "aibot_group_chatid"
#: 1:1 私信通道——`to_userid` 即目标，不查任何映射表。
CHANNEL_DIRECT = "aibot_direct"

#: 本中继认得的通道。**不认得的一律不发**（见 `_UNKNOWN_CHANNEL`）——
#: 猜一个目标出来发错群，比不发严重得多。
KNOWN_CHANNELS = frozenset({CHANNEL_GROUP, CHANNEL_DIRECT})

#: 本中继支持的消息体类型。`AibotConnector` 另有 `send_file`（需 media_id），
#: outbox 契约当前不承载附件，故只认 markdown；出现别的值 ⇒ 告警不发。
SUPPORTED_MSGTYPES = frozenset({"markdown"})

DEFAULT_POLL_INTERVAL_SECONDS = 300  # 5 分钟，同 liveness 心跳量级

#: 环境变量：outbox 文件路径清单，`os.pathsep`（Windows 上是 `;`）或换行分隔，
#: 支持 `*`/`?` 通配。未配置 ⇒ 中继整体关闭（并在审计里留一条明确的「关着」）。
OUTBOX_PATHS_ENV = "WECOM_AIBOT_OUTBOX_PATHS"
#: 环境变量：轮询间隔秒数。
POLL_INTERVAL_ENV = "WECOM_AIBOT_OUTBOX_POLL_SECONDS"

# ---- 跳过原因（全部属「结构性不可投递」，全部告警，全部留在 outbox 里）----
REASON_DEPARTMENT_MISSING = "department_missing"
REASON_DEPARTMENT_NOT_IN_MAPPING = "department_not_in_mapping"
REASON_GROUP_CHATID_NOT_CONFIGURED = "group_chatid_not_configured"
REASON_DIRECT_USERID_MISSING = "direct_userid_missing"
REASON_UNKNOWN_CHANNEL = "unknown_channel"
REASON_UNSUPPORTED_MSGTYPE = "unsupported_msgtype"
REASON_EMPTY_TEXT = "empty_text"
REASON_CORRUPT_LINE = "corrupt_line"

#: 跳过原因 → 给人看的一句话（告警正文用）。写全句而不是原因码——收到告警
#: 的人不该还要回来查代码才知道发生了什么。
SKIP_EXPLANATIONS = {
    REASON_DEPARTMENT_MISSING: "记录走群通道但没写 department，无从解析群 chatid",
    REASON_DEPARTMENT_NOT_IN_MAPPING:
        "department 不在 department_group_chatid_mapping.yaml 里（键名须与 "
        "department_mapping.yaml 的『值』逐字一致，如 `IT` 而非 `IT部`）",
    REASON_GROUP_CHATID_NOT_CONFIGURED: "该部门在映射表里，但 chatid 值为空（尚未采集）",
    REASON_DIRECT_USERID_MISSING: "记录走私信通道但没写 to_userid",
    REASON_UNKNOWN_CHANNEL: "channel 取值本中继不认识，不猜目标",
    REASON_UNSUPPORTED_MSGTYPE: "msgtype 本中继不支持（当前只支持 markdown）",
    REASON_EMPTY_TEXT: "正文为空，不发空消息",
    REASON_CORRUPT_LINE: "该行不是合法的 JSON 对象，已原样保留、未投递",
}


class OutboxReadError(RuntimeError):
    """outbox 文件读不到（路径不通/权限/共享断了）。

    🔴 **这一条对本项目特别重要**：`.51` 与笔记本之间是一条文件通路，通路断了
    的表象是「读到 0 条待发」——与「本来就没有待发」**在系统看来长得一模一样**
    （同 §四 `#59` 那次断供 5 个工作日无人察觉的形态）。故读失败 MUST 上抛并
    告警，MUST NOT 当作「今天没有待发消息」。
    """


@dataclass(frozen=True)
class OutboxEntry:
    """一条待投递记录及其在文件中的**物理位置**。

    `raw` 是该行去掉首尾空白后的原文——回写时用它做**乐观并发校验**：写侧
    （`.51`）随时可能往同一文件追加新行，只有 `lines[index]` 仍逐字等于 `raw`
    才允许改写这一行。
    """

    path: Path
    index: int
    raw: str
    record: dict

    @property
    def scenario(self) -> str:
        value = self.record.get("scenario")
        return value if isinstance(value, str) else ""

    @property
    def period(self) -> str:
        value = self.record.get("period")
        return value if isinstance(value, str) else ""

    def describe(self) -> str:
        """给人看的一行定位串（告警/CLI 用）。"""
        bits = [b for b in (self.scenario, self.period, str(self.record.get("channel", ""))) if b]
        return f"{self.path.name}:{self.index + 1}" + (f"（{' / '.join(bits)}）" if bits else "")


@dataclass(frozen=True)
class ResolvedTarget:
    target: str
    kind: str  # "group" | "direct"


@dataclass
class RelayOutcome:
    """一轮轮询的结果。**每一项都要能被外部看见**——只报成功数等于没报。"""

    scanned: int = 0
    delivered: int = 0
    skipped: list[tuple[OutboxEntry, str]] = field(default_factory=list)
    failed: list[tuple[OutboxEntry, str]] = field(default_factory=list)
    mark_failed: list[OutboxEntry] = field(default_factory=list)
    unreadable: list[tuple[Path, str]] = field(default_factory=list)

    @property
    def pending_left(self) -> int:
        """本轮结束时仍未投递的条数（＝扫到的 − 投出去的）。"""
        return self.scanned - self.delivered

    def summary(self) -> str:
        return (
            f"扫描 {self.scanned} 条待投递，成功 {self.delivered} 条，"
            f"结构性跳过 {len(self.skipped)} 条，发送失败 {len(self.failed)} 条，"
            f"标记失败 {len(self.mark_failed)} 条，不可读 outbox {len(self.unreadable)} 份"
        )


# ---------------------------------------------------------------- 路径解析 --


def resolve_outbox_paths(raw: Optional[str]) -> list[Path]:
    """把环境变量原文解析成 outbox 路径清单。

    分隔符同时接受 `os.pathsep` 与换行（`.env` 里一行写不下时可折行）。含
    `*`/`?` 的项按通配展开——展开为空时**保留原样**，让它在读取阶段以
    `OutboxReadError` fail-loud，而不是在这里静默消失（一个「配了但没匹配到」
    的通配符若在解析阶段就蒸发，症状与「没配」完全一致）。

    去重但保序：同一份 outbox 被配置两次不会被扫两遍（会重复投递）。
    """
    if not raw or not raw.strip():
        return []

    tokens: list[str] = []
    for chunk in raw.replace("\n", os.pathsep).split(os.pathsep):
        token = chunk.strip().strip('"').strip("'")
        if token:
            tokens.append(token)

    resolved: list[Path] = []
    seen: set[str] = set()
    for token in tokens:
        candidates = sorted(_glob.glob(token)) if ("*" in token or "?" in token) else [token]
        if not candidates:
            candidates = [token]
        for candidate in candidates:
            path = Path(candidate)
            key = str(path).lower() if os.name == "nt" else str(path)
            if key in seen:
                continue
            seen.add(key)
            resolved.append(path)
    return resolved


# ------------------------------------------------------------------ 读 outbox --


def iter_pending(path: Path) -> tuple[list[OutboxEntry], list[tuple[int, str]]]:
    """扫一份 outbox，返回 (待投递记录, 损坏行)。

    :raises OutboxReadError: 文件不可读——**包含"不存在"**。见该异常的 docstring：
        `.51` 那条文件通路断掉时的表象就是"文件不见了"，不得当成"没有待发"。

    - `delivered` 为真的行跳过（已投递过）。
    - 空行跳过、不计入任何一类（写侧末尾天然有一个空串）。
    - 非法 JSON / 非 dict 的行进"损坏行"，**原样保留在文件里**、不投递、告警。
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OutboxReadError(f"outbox 不可读：{path} —— {describe_exception(exc)}") from exc

    pending: list[OutboxEntry] = []
    corrupt: list[tuple[int, str]] = []
    for index, line in enumerate(text.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError:
            corrupt.append((index, stripped))
            continue
        if not isinstance(record, dict):
            corrupt.append((index, stripped))
            continue
        if record.get("delivered"):
            continue
        pending.append(OutboxEntry(path=path, index=index, raw=stripped, record=record))
    return pending, corrupt


# ------------------------------------------------------------------ 目标解析 --


def resolve_target(
    record: dict, mapping: dict[str, str]
) -> tuple[Optional[ResolvedTarget], str]:
    """把一条记录解析成投递目标。返回 `(目标, "")` 或 `(None, 跳过原因)`。

    🔴 **本函数是硬约束①的落点**：群通道的 chatid **只**从传入的 `mapping`
    （＝`department_group_chatid_mapping.yaml`）取，本模块不含任何 chatid
    字面量、也不做任何"部门名近似匹配"——`采购部` 与 `PMC部`、`IT` 与 `IT部`
    在这里是完全不同的键，写错即 fail-loud 跳过，**不猜**（`#387` 那次静默
    错投的成因正是拿一条推断链去顶替事实）。
    """
    channel = record.get("channel")
    if channel not in KNOWN_CHANNELS:
        return None, REASON_UNKNOWN_CHANNEL

    msgtype = record.get("msgtype", "markdown")
    if msgtype not in SUPPORTED_MSGTYPES:
        return None, REASON_UNSUPPORTED_MSGTYPE

    text = record.get("text")
    if not isinstance(text, str) or not text.strip():
        return None, REASON_EMPTY_TEXT

    if channel == CHANNEL_DIRECT:
        userid = record.get("to_userid")
        if not isinstance(userid, str) or not userid.strip():
            return None, REASON_DIRECT_USERID_MISSING
        return ResolvedTarget(target=userid.strip(), kind="direct"), ""

    department = record.get("department")
    if not isinstance(department, str) or not department.strip():
        return None, REASON_DEPARTMENT_MISSING
    department = department.strip()
    if department not in mapping:
        return None, REASON_DEPARTMENT_NOT_IN_MAPPING
    chatid = mapping.get(department) or ""
    if not chatid:
        return None, REASON_GROUP_CHATID_NOT_CONFIGURED
    return ResolvedTarget(target=chatid, kind="group"), ""


# ------------------------------------------------------------------ 回写标记 --


def build_delivered_record(record: dict, *, target: ResolvedTarget, ack: object, now: datetime) -> dict:
    """在原记录上叠加投递结果，**不删不改任何既有字段**。

    `delivered_to` 存的是实际发出去的那个 chatid/userid——硬约束③那次人眼
    反查要对的就是这个值；只写 `delivered:true` 事后无从复核发到了哪。
    """
    updated = dict(record)
    updated["delivered"] = True
    updated["delivered_at_utc"] = now.isoformat(timespec="seconds")
    updated["delivered_to"] = target.target
    updated["delivered_kind"] = target.kind
    if isinstance(ack, dict):
        errcode = ack.get("errcode")
        updated["delivered_ack"] = {
            "errcode": errcode if isinstance(errcode, int) else None,
            "errmsg": ack.get("errmsg") if isinstance(ack.get("errmsg"), str) else None,
        }
    return updated


def mark_delivered(entry: OutboxEntry, updated_record: dict) -> bool:
    """把某一行改写成"已投递"。成功返回 True；**位置校验不过返回 False**。

    🔴 **必须做位置校验**：写侧（`.51` 上的 SC2/FI2）随时可能在本轮"读"与
    "写"之间往同一文件追加新行。做法是整份重读、只在 `lines[index]` 仍逐字
    等于 `entry.raw` 时替换那一行，其余行**原样保留**——后追加的行位于更大的
    下标，天然不受影响。校验不过 ⇒ 返回 False（调用方记 `mark_failed` 并告警），
    **MUST NOT 强行覆盖**：那会把写侧刚落的一条消息直接抹掉。

    写入走"临时文件 + `os.replace`"，避免中途失败留下半份 outbox。
    """
    try:
        lines = entry.path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False

    if entry.index >= len(lines) or lines[entry.index].strip() != entry.raw:
        return False

    lines[entry.index] = json.dumps(updated_record, ensure_ascii=False)
    tmp = entry.path.with_name(entry.path.name + ".relaytmp")
    try:
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.replace(tmp, entry.path)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        return False
    return True


# ---------------------------------------------------------------------- 轮 --


def _audit(
    audit: AuditLogger, evaluator: str, action: str, decision: dict, sources: dict, error: str = ""
) -> None:
    audit.record(
        AuditEvent(
            scenario="wecom-aibot",
            action=action,
            evaluator=evaluator,
            automation_level="L1",
            decision=decision,
            data_sources={k: str(v) for k, v in sources.items()},
            error=error,
        )
    )


async def _alert_once(
    alert_send: Optional[Callable[[str], None]],
    alerted: set,
    key: tuple,
    text: str,
) -> None:
    """同一 `(文件, 行, 原因)` 本进程内只告警一次。

    轮询每 5 分钟一轮，而结构性不可投递的记录会**一直留在 outbox 里**（刻意
    的，见模块 docstring）——不去重就是每天 288 条同样的告警，两天之内没有
    人会再看这条通道。**告警本身失败绝不向上抛**：中继是旁路，它的告警更是
    旁路的旁路。
    """
    if alert_send is None or key in alerted:
        return
    alerted.add(key)
    try:
        await asyncio.to_thread(alert_send, text)
    except Exception:  # noqa: BLE001 —— 告警失败不得影响投递主链路
        pass


async def relay_once(
    *,
    connector,
    audit: AuditLogger,
    paths: Iterable[Path],
    mapping: dict[str, str],
    evaluator: str = "system",
    alert_send: Optional[Callable[[str], None]] = None,
    alerted: Optional[set] = None,
    now: Optional[datetime] = None,
) -> RelayOutcome:
    """扫一遍全部 outbox，把待投递记录经 `connector` 发出去。

    `connector` 类型故意不标注（同 `group_notify.notify_department_group_via_chatid`
    的既有惯例），只要求具备 `send_markdown(target, content)` 协程接口——传进来
    的就是常驻服务已经握着的那一条连接，**本函数从不自己建连接**。

    每条记录彼此独立：一条失败/跳过不影响其余条，也不影响其余 outbox 文件。
    """
    outcome = RelayOutcome()
    alerted = alerted if alerted is not None else set()
    stamp = now or datetime.now(timezone.utc)

    for path in paths:
        try:
            pending, corrupt = iter_pending(path)
        except OutboxReadError as exc:
            outcome.unreadable.append((path, str(exc)))
            _audit(audit, evaluator, "outbox_relay_scan_failed", {}, {"path": str(path)}, str(exc))
            # 🔴 读不到 ≠ 没有待发。这条告警不去重（它是"通路断了"，
            # 每轮都该响，直到有人管）。
            if alert_send is not None:
                try:
                    await asyncio.to_thread(
                        alert_send,
                        f"outbox 中继读不到 {path} —— 这**不等于**没有待发消息，"
                        f"请确认 `.51` 到本机的文件通路是否还通。原因：{exc}",
                    )
                except Exception:  # noqa: BLE001
                    pass
            continue

        for index, raw in corrupt:
            entry = OutboxEntry(path=path, index=index, raw=raw, record={})
            outcome.skipped.append((entry, REASON_CORRUPT_LINE))
            _audit(
                audit, evaluator, "outbox_relay_skipped",
                {"reason": REASON_CORRUPT_LINE}, {"path": str(path), "line": index + 1},
            )
            await _alert_once(
                alert_send, alerted, (str(path), index, REASON_CORRUPT_LINE),
                f"outbox 中继跳过 {path.name} 第 {index + 1} 行："
                f"{SKIP_EXPLANATIONS[REASON_CORRUPT_LINE]}",
            )

        outcome.scanned += len(pending)

        for entry in pending:
            target, reason = resolve_target(entry.record, mapping)
            if target is None:
                outcome.skipped.append((entry, reason))
                _audit(
                    audit, evaluator, "outbox_relay_skipped",
                    {"reason": reason, "scenario": entry.scenario, "period": entry.period},
                    {"path": str(entry.path), "line": entry.index + 1},
                )
                await _alert_once(
                    alert_send, alerted, (str(entry.path), entry.index, reason),
                    f"outbox 中继跳过 {entry.describe()}：{SKIP_EXPLANATIONS[reason]}。"
                    f"该条**仍留在 outbox 里**等人处理，不会被丢弃。",
                )
                continue

            try:
                ack = await connector.send_markdown(target.target, entry.record["text"])
                _assert_ack_accepted(ack, what=f"outbox 中继投递（{entry.describe()}）")
            except Exception as exc:  # noqa: BLE001 —— 失败留在 outbox 等下一轮（硬约束②）
                outcome.failed.append((entry, describe_exception(exc)))
                _audit(
                    audit, evaluator, "outbox_relay_send_failed",
                    {
                        "scenario": entry.scenario, "period": entry.period,
                        "target": target.target, "kind": target.kind,
                        # `DeliveryAckError` ＝ 企微明确拒了；其余 ＝ 连接/传输侧。
                        "rejected_by_wecom": isinstance(exc, DeliveryAckError),
                    },
                    {"path": str(entry.path), "line": entry.index + 1},
                    describe_exception(exc),
                )
                continue

            if not mark_delivered(entry, build_delivered_record(
                entry.record, target=target, ack=ack, now=stamp
            )):
                # 🔴 已经发出去了，但标不上——下一轮会重发这一条。绝不假装
                # 标成功（那才是真正的丢），也绝不强行覆盖（会抹掉写侧刚落的行）。
                outcome.mark_failed.append(entry)
                _audit(
                    audit, evaluator, "outbox_relay_mark_failed",
                    {"scenario": entry.scenario, "period": entry.period, "target": target.target},
                    {"path": str(entry.path), "line": entry.index + 1},
                )
                if alert_send is not None:
                    try:
                        await asyncio.to_thread(
                            alert_send,
                            f"outbox 中继**已发出但未能标记已投递**：{entry.describe()} → "
                            f"{target.target}。下一轮会重发这一条（群里会看到两条一样的），"
                            f"请人工确认后手工把该行 delivered 置真。",
                        )
                    except Exception:  # noqa: BLE001
                        pass
                continue

            outcome.delivered += 1
            _audit(
                audit, evaluator, "outbox_relay_delivered",
                {
                    "scenario": entry.scenario, "period": entry.period,
                    "channel": entry.record.get("channel"),
                    # 硬约束③：把实际发到的 chatid 留痕，人眼反查时有据可对。
                    "target": target.target, "kind": target.kind,
                    "ack": ack if isinstance(ack, dict) else None,
                },
                {"path": str(entry.path), "line": entry.index + 1},
            )

    return outcome


async def run_outbox_relay(
    *,
    connector,
    audit: AuditLogger,
    paths: list[Path],
    mapping: Optional[dict[str, str]] = None,
    interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    evaluator: str = "system",
    alert_send: Optional[Callable[[str], None]] = None,
    on_round: Optional[Callable[[RelayOutcome], None]] = None,
    _sleep: Callable[[float], "asyncio.Future"] = asyncio.sleep,
) -> None:
    """常驻后台任务：每 `interval_seconds` 扫一遍 outbox 并代发，直至被取消。

    立即跑第一轮（进程刚起来时把关机期间积压的先送出去，不必等满一个周期），
    随后按周期轮询。范式同 `liveness.run_liveness_heartbeat`：调用方在服务
    退出时 `task.cancel()`，不留悬空任务。

    ⚠️ **单轮异常一律吞掉并留痕**，绝不让中继的一次失败把常驻服务的主链路
    （收件归档／回执／转发）带下水——它是旁路。
    """
    resolved_mapping = mapping if mapping is not None else load_department_group_chatid_mapping()
    alerted: set = set()
    while True:
        try:
            outcome = await relay_once(
                connector=connector, audit=audit, paths=paths, mapping=resolved_mapping,
                evaluator=evaluator, alert_send=alert_send, alerted=alerted,
            )
            if on_round is not None:
                on_round(outcome)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 —— 中继是旁路，绝不拖垮主链路
            _audit(audit, evaluator, "outbox_relay_round_failed", {}, {}, describe_exception(exc))
        await _sleep(interval_seconds)
