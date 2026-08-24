"""群推送出口 —— outbox 落盘，由笔记本侧常驻中继经企微智能机器人代发。

🔴 **为什么不是直接发**（队列 `#282` 拍板 ＋ `fi2-source-inversion` design 决策点 8.2）：

- **不得新起 webhook**。`#270`/`#279`/`#281` 已于 2026-08-06 把群通报整体从 webhook
  迁到智能机器人 chatid 通道，理由是「**webhook 单向，群成员的回复进不到任何地方**」。
  姚祖怡恰恰是会在群里回话的那一位，配 webhook 等于让他的回复掉进黑洞。
- **而机器人的长连接在笔记本上，SC2 跑在 `.51`**。两者不同机器，`.51` 侧没有、也不该有
  那条 WebSocket（单实例约束：同一机器人多处长连接会互相踢线）。这与 FI2 的处境同构，
  故照其 design 已批的形态办：**`.51` 只负责把消息落进 outbox，笔记本侧中继轮询取走代发**。

**代价是显式的**：笔记本关机期间消息只是**积压**、不是丢失（落盘即持久），开机后由中继补发。
对「每周五一份周报」这种频次，延迟到下次开机可接受；**但它必须被看见**——故 `pending()`
把积压条数暴露出来，页面与 CLI 都能读到，不让「写进了 outbox」被误当成「已经发出去了」。

🔴 **本模块不解析 chatid，只写部门名**。部门 → 群 chatid 的权威映射是
`5-平台底座/wecom-aibot-service/aibot_service/department_group_chatid_mapping.yaml`，
由中继侧（与 aibot 同机、能 import 到那张表）解析。**在这里抄一份 chatid 常量会立刻产生
第二份真相**，而那张表的注释里已经写明它踩过的坑（键名 `IT` 而非 `IT部`、传错即
fail-closed 静默跳过）。少一份副本就少一次静默错发。
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from . import config

#: 本场景的收件部门。**必须与 `department_mapping.yaml` 的「值」逐字一致**。
#:
#: 🔴 组织事实：`PMC部` ⊂ `采购部`，但这里**只能写 `采购部`**——该字段取的是
#: 「部门→群 chatid」映射表的**键**（仅 `财务部/质量部/采购部/跨部门/IT` 五键）。
#: 传 `PMC部` 会命中「不在映射表」分支：**fail-closed 静默跳过、不报错、日志一切正常**。
DEPARTMENT = "采购部"

#: 允许的部门键。写进常量并在入队时校验，使拼错**当场炸**而不是静默不发。
#: 与上面那条注释是同一件事的两种防线：注释防人写错，本集合防写错后没人发现。
KNOWN_DEPARTMENTS = frozenset({"财务部", "质量部", "采购部", "跨部门", "IT"})

#: 1:1 私信收件人（企微 userid）。与 `notify.RECIPIENTS` 的「姚祖怡」对应。
YAO_USERID = "YaoZuYi"


class UnknownDepartmentError(ValueError):
    """部门键不在映射表里。**上抛而非静默跳过**——静默正是本模块要防的那个坑。"""


def outbox_path() -> Path:
    """outbox 文件路径。可用 `SC2_OUTBOX_PATH` 覆盖（中继与测试用）。

    缺省落场景 `reports/`，已被仓库 `.gitignore` 的 `**/reports/` 覆盖 ——
    周报正文含真实供应商名与采购金额，**不得入库**。
    """
    override = os.environ.get("SC2_OUTBOX_PATH", "").strip()
    if override:
        path = Path(override)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    return config.reports_dir() / "sc2_group_outbox.jsonl"


def _now_pair() -> tuple[str, str]:
    """(UTC, 本机本地) 两个时刻，**都带显式偏移**。

    根 `CLAUDE.md` 硬规则：引用任何时刻都要能一眼看出基准。本项目的证据源基准并不
    一致（审计 JSONL 是真 UTC，文件 mtime 与计划任务是本地），outbox 会被两侧同时
    读，故两个都写、都带 offset，免去下游再猜一次。
    """
    now = datetime.now(timezone.utc)
    return now.isoformat(timespec="seconds"), now.astimezone().isoformat(timespec="seconds")


def enqueue(*, period: str, text: str, department: str = DEPARTMENT,
            to_userid: str | None = YAO_USERID, path: Path | None = None) -> Path:
    """把一期周报写进 outbox（群 ＋ 可选 1:1 私信，各一条记录）。

    :returns: outbox 文件路径。
    :raises UnknownDepartmentError: 部门键不在映射表里。

    **一期写两条而不是一条**：群通报与私信是两次独立投递，中继可能一条成功一条失败；
    合成一条会让「群发出去了、私信没发」这种半成功状态无法表达，只能整条重发或整条丢弃。
    """
    if department not in KNOWN_DEPARTMENTS:
        raise UnknownDepartmentError(
            f"部门键 {department!r} 不在映射表 {sorted(KNOWN_DEPARTMENTS)} 中；"
            f"传错会被中继 fail-closed 静默跳过，故在此上抛")

    ts_utc, ts_local = _now_pair()
    target = path or outbox_path()
    records = [{
        "ts_utc": ts_utc, "ts_local": ts_local,
        "scenario": "SC2", "period": period,
        "channel": "aibot_group_chatid",     # 🔴 非 webhook（#282）
        "department": department,            # chatid 由中继侧按权威映射解析
        "msgtype": "markdown", "text": text,
        "delivered": False,
    }]
    if to_userid:
        records.append({
            "ts_utc": ts_utc, "ts_local": ts_local,
            "scenario": "SC2", "period": period,
            "channel": "aibot_direct",
            "to_userid": to_userid,
            "msgtype": "markdown", "text": text,
            "delivered": False,
        })

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return target


def pending(path: Path | None = None) -> int:
    """尚未被中继取走的条数。

    🔴 **这个数存在的唯一理由是让积压可见**。SC2 侧写完 outbox 就返回成功，若没有
    任何地方暴露「其实还没发出去」，就会重演 `#82` 那个形态：机制建成 9 天、每天在跑、
    一条消息都没真的发出去，而没有人察觉。页面与 CLI 都读它。
    """
    target = path or outbox_path()
    if not target.exists():
        return 0
    count = 0
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            if not json.loads(line).get("delivered"):
                count += 1
        except json.JSONDecodeError:
            continue          # 半行/损坏行不计入，但也不让它炸掉调用方
    return count
