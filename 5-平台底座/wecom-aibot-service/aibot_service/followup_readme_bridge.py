"""S4 桥一（队列 #366 M1）：回件到达即在跟进信 README 打中间态。

## 它补的是哪一格

**串行闸永远不会自己开。** 闸的判据源是 `README-跟进机制与命名约定.md` 的
「发送状态」列，而机器只写队列：回件到达时本服务自动追 §一 入信行（做到
了）、拆件回灌由人写队列行（做到了）、**唯独没有任何东西去改 README 那一
格**。2026-08-21 当天两次真实咬人——采购部#17 的回件 13:13:24 落盘、队列
13:15 就自动追了行，而 README 状态列一动没动，闸对姚祖怡仍锁着。

本模块让「回件物理到达」这件事**在权威源上立刻可见**：把该信的状态改写为
第九态 `📨 回件已到，待拆件 <UTC>`。

🔴 **第九态仍属在途、闸仍锁**——它不是「闭环」的弱化版，而是「已推送」与
「已回件并回灌」之间那段此前完全不可见的空白。真正开闸仍须人拆件回灌后
转闭环四态（由 S4 桥二在 `release` 上强制，见 `工具-共享文档编辑锁.py::
_validate_followup_reply_state_sync`）。

## 三条硬约束

1. **配对走两级通道**（`OP-0823-D` 改判，队列 #366；原「匹配不上就不动」
   已退休，理由见下节）。判据一份，落在 `followup_gate.pair_reply_to_letter`：
   ① **stem 精确匹配**命中即止；② 未命中则配「该收信人**最新一封已发出**
   的信」——不看文件名、不看正文，**docx 与纯文字一视同仁**。
   两级都落空时 **fail-loud**：记审计事件 ＋ 打印 WARN，不静默跳过。
   🔴 **例外**：「最新一封已闭环」这一种落空是**预期内常态**（闭环后的补充
   说明必然走到它），只记审计 ＋ 低噪一行，**不得升级为需人处置的告警**。
2. **必须走编辑锁**，不得直接写文件绕开协议〇.7。复用既有
   `SubprocessQueueEditLock`（与队列写入同一把协议实现，不分叉）。
3. **`acquire` 拿不到锁必须重试**（指数退避，默认 3 次）；**放弃时必须
   打日志并告警**，不得静默。锁忙不是"没事发生"，是"这条回件的可见性这次
   丢了"。

## 为什么「匹配不上就不动」这条原硬约束被退休了（它的理由曾经是对的）

原文写的是：「一条文本回件无法确定地指向哪一封信，硬配会造出比漏配更难
发现的错误」——**该判断在「靠内容猜」的前提下成立**。`OP-0823-D` 换掉的
是前提，不是猜法：**不按内容配，按位置配**。位置的确定性来自本项目已有的
硬约束「跟进信串行原则：同一收信人同时只能有一封在途」，而机器人在落档
那一刻已知发件人企微 userid ⇒ 部门 ⇒ 收信人。

**漏配的代价已被实测量化**：README 中 12 封信的状态列停在「✅ 已推送」，
最久积压 20 天以上，且后果有两个——⑴ 串行闸误锁，该发的信发不出；
⑵ **度量失真**，「未转态」与「回得慢」在数据上长得一模一样。
**误配的代价则有限**：第九态是「回件已到，待拆件」、**闸仍锁**，人拆件时
一眼就能看出配错了。

⚠️ **仍然保留 stem 为第一优先**：它确定性最高，且**去掉它就是净回归**——
今天能正常转态的 docx 回件，会反过来受制于「最新一封」的判断。

## 为什么不做「拿不到锁就暂存、下次补录」

队列侧那条路径（`queue_lock_pending.py`）之所以成立，是因为**队列行丢了
等于这条回件在调度视野里从未发生**，代价极高。README 这一格不同：即使
本次没打上，**桥二仍会在拆件 release 时把人拦下来**——两座桥是冗余而非串
联，缺一座不会漏。故此处只做有限重试 ＋ 告警，不新增第三个暂存文件。
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Callable, Optional

from zhuopin_platform.audit import AuditEvent, AuditLogger
from zhuopin_platform.shared_tools import followup_gate

from .queue_edit_lock import QueueLockBusy
from .readme_table import (
    ReadmeTableError,
    column_index,
    extract_target_filename,
    iter_rows,
    write_status,
)

# 🔴 必须是**仓库相对、正斜杠**的字面量：`工具-共享文档编辑锁.py::cmd_release`
# 按 `args.file == FOLLOWUP_README_TARGET` 逐字比对来决定跑不跑 README 那套
# release 校验。传绝对路径能锁住文件，但那道校验会**静默不跑**（同
# CLAUDE.md §5「工具静默回退」）；传 `Path("a/b")` 在 Windows 上 `str()` 出来
# 是反斜杠，同样比不中。`PurePosixPath` 的 `str()` 在任何平台都是正斜杠。
FOLLOWUP_README_REL = "6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md"
LOCK_TARGET = PurePosixPath(FOLLOWUP_README_REL)

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_SECONDS = 2.0

ACTION_MARKED = "marked"
ACTION_UNMATCHED = "unmatched"
ACTION_ALREADY = "already_beyond"
ACTION_LOCK_BUSY = "lock_busy"
ACTION_NO_README = "no_readme"
# `OP-0823-D`：未命中的三种原因分开记 action，**不再合并成一个 unmatched**
# ——它们的处置级别不同，合并会让「预期内常态」和「真的出问题了」在审计
# 里长得一模一样（本项目已记的「错误不产生信号」那一族的镜像形态：这次是
# 「常态产生了错误的信号」）。
ACTION_SUPPLEMENT = "supplement_after_closed"   # 最新一封已闭环 ⇒ 低噪，常态
ACTION_NO_DISPATCHED = "no_dispatched_letter"   # 该收信人无已发出的信 ⇒ WARN
ACTION_NO_DEPARTMENT = "no_department"          # 收信人解析不出 ⇒ WARN


@dataclass
class BridgeResult:
    action: str
    letter_number: Optional[str] = None
    detail: str = ""
    # 命中的是哪条通道（`stem` / `latest`），未命中为空串。派单件 §3.4
    # 要求「审计事件须记录本次命中的是哪条规则」——日后复盘误配时，第一个
    # 要问的就是「这条是逐字对上的，还是按位置推的」。
    channel: str = ""


def _utc_stamp(now: Optional[datetime] = None) -> str:
    """UTC，且**显式带 `Z`**——根 CLAUDE.md §5 硬规则：引用任何时刻前先答
    一句「这是 UTC 还是本地」，并在输出里标基准。本服务其余留痕（审计
    JSONL、告警文案）同样是真 UTC，此处保持一致。"""
    moment = now or datetime.now(tz=timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_reply_arrived_status(previous_status: str, archived_filename: str,
                               now: Optional[datetime] = None) -> str:
    """新状态值 ＝ 第九态前缀 ＋ UTC 戳 ＋ 溯源，**原状态原样接在后面**。

    前缀在最前，是因为闭环判据一律按前缀比对；旧状态不删，是因为「这封信
    是什么时候推送的」是后续转闭环态时要引用的事实——**覆盖式写入会把它
    弄丢，而这一格没有任何别处的副本**。
    """
    stamp = _utc_stamp(now)
    return (
        f"{followup_gate.REPLY_ARRIVED_STATUS} {stamp}"
        f"（企微机器人自动标记，入信归档 `{archived_filename}`；"
        f"**仍属在途、串行闸仍锁**，拆件回灌后须转闭环四态之一）"
        f"　━━━　原状态 ━━━　{previous_status}"
    )


def _cell(row, index: int) -> str:
    return row.cells[index] if 0 <= index < len(row.cells) else ""


def _letter_rows(readme_text: str) -> tuple[list, dict]:
    """README 表格 → (`followup_gate.LetterRow` 列表, {编号: RowLocation})。

    列位置按表头字样定位（`readme_table.column_index`），不写死序号——该表
    的列顺序不归本模块管，而写死序号的失效形态是「读到了另一列的内容，且
    完全不报错」。定位不到则回落到实测的固定序号，并且**只在这种情况下**
    回落，不静默把两条路径混用。
    """
    rows = iter_rows(readme_text)
    header = rows[0].header_cells if rows else []
    num_idx = column_index(header, "编号")
    date_idx = column_index(header, "日期")
    recipient_idx = column_index(header, "收信人")
    topic_idx = column_index(header, "主要事项")
    num_idx = 0 if num_idx is None else num_idx
    date_idx = 1 if date_idx is None else date_idx
    recipient_idx = 2 if recipient_idx is None else recipient_idx
    topic_idx = 3 if topic_idx is None else topic_idx

    letters = []
    locations = {}
    for order, row in enumerate(rows):
        number = _cell(row, num_idx)
        letters.append(followup_gate.LetterRow(
            number=number,
            date=_cell(row, date_idx),
            recipient=_cell(row, recipient_idx),
            target_filename=extract_target_filename(_cell(row, topic_idx)),
            status=row.cells[row.status_col_index],
            order=order,
        ))
        locations[number] = row
    return letters, locations


def _pair(readme_text: str, archived_filename: str, department: Optional[str]):
    """跑一次两级配对，返回 (`PairingOutcome`, 命中行的 `RowLocation` 或 None)。"""
    letters, locations = _letter_rows(readme_text)
    outcome = followup_gate.pair_reply_to_letter(
        archive_filename=archived_filename,
        department=department,
        rows=letters,
    )
    row = locations.get(outcome.letter.number) if outcome.letter else None
    return outcome, row


def _health_note(readme_text: str) -> str:
    """§3.1bis 健康检查：各部门「已发出且未闭环」的信有几封。

    🔴 只报数。它**不参与任何转态判定，也不阻塞配对**——这正是它被从配对
    判据里挪出来的原因（见 `followup_gate` §五 的红字）。
    """
    try:
        letters, _ = _letter_rows(readme_text)
    except ReadmeTableError:
        return ""
    grouped = followup_gate.unclosed_dispatched_by_department(letters)
    if not grouped:
        return ""
    parts = "、".join(
        f"{dept} {len(items)} 封" for dept, items in sorted(grouped.items())
    )
    return f"README 健康检查：已发出未闭环 {parts}（只报数，不影响本次配对）"


def _row_number(row) -> str:
    return row.cells[0] if row.cells else "?"


_MISS_ACTION = {
    followup_gate.PAIR_MISS_LATEST_CLOSED: ACTION_SUPPLEMENT,
    followup_gate.PAIR_MISS_NO_DISPATCHED: ACTION_NO_DISPATCHED,
    followup_gate.PAIR_MISS_NO_DEPARTMENT: ACTION_NO_DEPARTMENT,
}


def resolve_letter_number(
    *,
    archived_filename: str,
    repo_root: Path,
    department: Optional[str] = None,
) -> Optional[str]:
    """**只读**预配对：这份回件将回灌到哪一封信？返回编号（如 `财务部#15`）。

    队列 #416 ⑸ 用它在**归档落盘之前**拿到编号，好把编号写进归档文件名
    ——审计里那条 `followup_readme_bridge_*` 事件同一时刻就拿到了这个值，
    「信息就在手边，只是没写进文件名」。

    🔴 三条硬纪律：
    ⑴ **只读、不持锁、不写盘**——它跑在归档主流程的关键路径上，任何写动作
       都会把「读一下 README」升级成一次可能失败的事务。
    ⑵ **绝不向上抛**——拿不到编号是「文件名少一段」，不是「归档失败」。
       任何异常一律吞成 None，与 `mark_reply_arrived` 的不抛契约同源。
    ⑶ **不猜**——`_pair` 未命中即 None，不打分、不取最相似的一个。

    与随后 `mark_reply_arrived` 的配对**同源**（同一个 `_pair`）：两次调用
    之间 README 若被改动，以 `mark_reply_arrived` 的结论为准——它才是往
    README 上写字的那一方，文件名里的编号只是它的一份可读副本。
    """
    try:
        readme_text = (repo_root / FOLLOWUP_README_REL).read_text(encoding="utf-8")
        outcome, row = _pair(readme_text, archived_filename, department)
    except Exception:  # noqa: BLE001 —— 见纪律⑵
        return None
    # 🔴 **不能只认 `outcome.matched`**：队列 #416 ⑸ 点名的那份 08-26 回件
    # 走的正是 `supplement_after_closed`（最新一封已闭环 ⇒ 这是闭环后的补充
    # 说明），它 `matched=False`、但 `outcome.letter` 是**确定定位到的那一行**
    # ——审计里那条 `followup_readme_bridge_supplement_after_closed` 的
    # `letter_number: 财务部#15` 就是从它来的。只认 matched 会让本条修复
    # 恰好在它要修的那个真实案例上失效。
    #
    # 反过来，`no_dispatched_letter` / `no_department` 两条**根本没有 letter**
    # ⇒ 仍然是 None，不猜。
    if row is None or outcome.letter is None:
        return None
    number = _row_number(row).strip()
    # 编号自身含 `-` 会破坏 `_ARCHIVE_NAME_RE` 的分段（见那里的红字）——
    # 形态不合即当作没拿到，宁可少一段，不生成一个解析不回来的文件名。
    if not number or "-" in number or "#" not in number:
        return None
    return number


def mark_reply_arrived(
    *,
    archived_filename: str,
    repo_root: Path,
    audit: AuditLogger,
    lock_factory: Callable[[], object],
    department: Optional[str] = None,
    evaluator: str = "system",
    now: Optional[datetime] = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
    alert_send: Optional[Callable[[str], None]] = None,
    log: Callable[[str], None] = print,
) -> BridgeResult:
    """把 `archived_filename` 对应的那封信在 README 上标为第九态。

    `department` ＝ 归档时已解析出的收信人部门（`intake.IntakeResult.department`）
    ——通道②按它定位「该收信人最新一封已发出的信」。传 None 时通道②不可用，
    只剩 stem 精确匹配（老行为），并在未命中时 fail-loud 说明原因。

    **本函数绝不向上抛**——它是归档主流程的旁路增强，任何失败都不得让一条
    已经成功归档的回件反过来算作处理失败（同 `sync_after_archive` 的既有
    契约）。失败一律走审计 ＋ 告警。
    """
    readme_path = repo_root / FOLLOWUP_README_REL
    try:
        readme_text = readme_path.read_text(encoding="utf-8")
    except OSError as exc:
        return _record(audit, evaluator, BridgeResult(
            ACTION_NO_README, detail=f"README 读取失败：{readme_path}（{exc}）"
        ), log=log)

    health = _health_note(readme_text)

    try:
        outcome, row = _pair(readme_text, archived_filename, department)
    except ReadmeTableError as exc:
        return _record(audit, evaluator, BridgeResult(
            ACTION_NO_README, detail=f"README 表格解析失败：{exc}"
        ), log=log)

    if row is None or not outcome.matched:
        return _record(audit, evaluator, BridgeResult(
            _MISS_ACTION.get(outcome.channel, ACTION_UNMATCHED),
            letter_number=outcome.letter.number if outcome.letter else None,
            detail=outcome.detail,
            channel=outcome.channel,
        ), log=log, health=health)

    current_status = row.cells[row.status_col_index]
    if (followup_gate.is_closed_status(current_status)
            or followup_gate.is_reply_arrived_status(current_status)):
        # 幂等：同一条回件重投、或人已抢先转态，都不该把状态往回推。
        return _record(audit, evaluator, BridgeResult(
            ACTION_ALREADY, letter_number=_row_number(row),
            detail=f"README「{_row_number(row)}」已处于「"
                   f"{followup_gate.normalize_status(current_status)[:30]}」，不覆盖。",
        ), log=log)

    lock = lock_factory()
    last_error = ""
    for attempt in range(1, max_attempts + 1):
        try:
            lock.try_acquire()
        except QueueLockBusy as exc:
            last_error = str(exc)
            if attempt < max_attempts:
                sleep(backoff_seconds * (2 ** (attempt - 1)))
                continue
            break
        try:
            # 🔴 持锁后**重读重定位**：从上面那次读到现在，别的会话可能已经
            # 改过这一格（这正是编辑锁存在的理由）。用锁外读到的
            # `RowLocation` 直接写回，等于把别人的改动按行号覆盖掉。
            fresh_text = readme_path.read_text(encoding="utf-8")
            fresh_outcome, fresh_row = _pair(fresh_text, archived_filename, department)
            if fresh_row is None or not fresh_outcome.matched:
                return _record(audit, evaluator, BridgeResult(
                    _MISS_ACTION.get(fresh_outcome.channel, ACTION_UNMATCHED),
                    letter_number=(fresh_outcome.letter.number
                                   if fresh_outcome.letter else None),
                    detail=f"持锁后重定位落空（README 在此期间被改动？）："
                           f"{fresh_outcome.detail}",
                    channel=fresh_outcome.channel,
                ), log=log)
            fresh_status = fresh_row.cells[fresh_row.status_col_index]
            if (followup_gate.is_closed_status(fresh_status)
                    or followup_gate.is_reply_arrived_status(fresh_status)):
                return _record(audit, evaluator, BridgeResult(
                    ACTION_ALREADY, letter_number=_row_number(fresh_row),
                    detail="持锁后重读发现已被转态，不覆盖。",
                ), log=log)
            readme_path.write_text(
                write_status(
                    fresh_text, fresh_row,
                    build_reply_arrived_status(fresh_status, archived_filename, now),
                ),
                encoding="utf-8",
            )
            return _record(audit, evaluator, BridgeResult(
                ACTION_MARKED, letter_number=_row_number(fresh_row),
                detail=f"README「{_row_number(fresh_row)}」已标为"
                       f"「{followup_gate.REPLY_ARRIVED_STATUS}」（{fresh_outcome.detail}）",
                channel=fresh_outcome.channel,
            ), log=log, health=health)
        finally:
            lock.release()

    result = BridgeResult(
        ACTION_LOCK_BUSY, letter_number=_row_number(row),
        detail=(
            f"README 编辑锁 {max_attempts} 次重试后仍占用，"
            f"「{_row_number(row)}」本次未标第九态（回件已正常归档、队列行已追）"
            f"——桥二会在拆件 release 时兜住，不会漏。最后一次：{last_error}"
        ),
    )
    if alert_send is not None:
        try:
            alert_send(result.detail)
        except Exception:  # noqa: BLE001 —— 告警自身失败不得反过来破坏本函数"不抛"的契约
            pass
    return _record(audit, evaluator, result, log=log)


# 🔴 分支 → 输出前缀。`ACTION_SUPPLEMENT` 刻意是「·」而不是「⚠」：
# 闭环后的补充说明是**预期内常态**，把它按警告报出去，等于每条补充都制造
# 一次假警报（派单件 §3.3 第 3 条点名要防的正是这个）。
_LOG_PREFIX = {
    ACTION_MARKED: "✓",
    ACTION_ALREADY: "·",
    ACTION_SUPPLEMENT: "·",
    ACTION_UNMATCHED: "⚠",
    ACTION_NO_DISPATCHED: "⚠",
    ACTION_NO_DEPARTMENT: "⚠",
    ACTION_LOCK_BUSY: "⚠",
    ACTION_NO_README: "⚠",
}


def _record(audit: AuditLogger, evaluator: str, result: BridgeResult,
            *, log: Callable[[str], None], health: str = "") -> BridgeResult:
    """统一留痕：审计事件 ＋ 一行可见输出。**每一条分支都经过这里**，
    包括"没做事"的那几条——静默跳过正是本模块要消灭的东西。"""
    prefix = _LOG_PREFIX.get(result.action, "·")
    try:
        log(f"{prefix} [跟进信README桥] {result.detail}")
        if health:
            # §3.1bis：健康检查只在这里露一行，**不改变任何返回值**。
            log(f"· [跟进信README桥] {health}")
    except Exception:  # noqa: BLE001
        pass
    try:
        audit.record(AuditEvent(
            scenario="wecom-aibot",
            action=f"followup_readme_bridge_{result.action}",
            evaluator=evaluator,
            automation_level="L1",
            decision={
                "letter_number": result.letter_number or "",
                # 派单件 §3.4：日后复盘误配，第一个要问的就是「这条是逐字
                # 对上的（stem），还是按位置推的（latest）」。
                "channel": result.channel,
            },
            data_sources={"detail": result.detail, "health": health},
        ))
    except Exception:  # noqa: BLE001 —— 留痕失败不得反过来破坏"不抛"的契约
        pass
    return result
