"""部门→群 chatid 映射加载（队列 #270：群 cc 改走智能机器人 chatid 通道，
取代群机器人 **webhook** 通报——webhook 单向，群成员的回复进不到任何地方；
智能机器人已是这些群的成员、群里也确实回复过，只是 chatid 值本身尚未采集，
这是另一条正在并行推进的依赖，不在本模块范围内）。

与 `department_group_mapping.py`（部门→webhook 环境变量名，服务旧通道）
同构但是第二张独立映射表——不要合并，值的语义不同（这里存的是 chatid
本身，那边存的是环境变量名）。chatid 不是秘密（同 `dispatch.py` 里明文放
的 `KNOWN_RECIPIENT_USERIDS` 一个敏感级别），可安全提交，故本表可直接落
yaml 明文，不必像 webhook URL 那样只存变量名、真实值留给 `.env`。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from zhuopin_platform.audit import AuditEvent, AuditLogger

DEFAULT_GROUP_CHATID_MAPPING_PATH = Path(__file__).parent / "department_group_chatid_mapping.yaml"


def load_department_group_chatid_mapping(path: Path | None = None) -> dict[str, str]:
    """加载部门→群 chatid 映射表。yaml 里裸键（无值）与显式空字符串都规整为
    `""`，交由 `resolve_group_cc_chatid` 统一按"未配置"处理。"""
    target = path or DEFAULT_GROUP_CHATID_MAPPING_PATH
    raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"部门群 chatid 映射表格式错误（应为 mapping）：{target}")
    return {str(k): ("" if v is None else str(v)) for k, v in raw.items()}


def resolve_group_cc_chatid(
    *,
    department: Optional[str],
    mapping: dict[str, str],
    audit: AuditLogger,
    evaluator: str = "system",
) -> Optional[str]:
    """跟进信发送方（`scripts/push_followup_letter.py` 手动 CLI／
    `aibot_service.dispatch.dispatch_followup_letters` 每日批处理）在决定是否
    把 `cc_group_chatid` 传给 `push_followup()` 前调用本函数——本函数就是
    "消费部门→群 chatid 映射表的那段代码"，fail-closed 判据与审计留痕都在
    这里做，`push_followup()` 本身只负责"给了就发"。

    department 为空/未知、不在映射表里、映射表里值为空（真实值尚未采集的
    占位状态）——三种情况均视为"未配置"，跳过群 cc 并记一条
    `followup_group_cc_skipped` 审计（同 `group_notify.py._skip` 的精神：
    每次跳过都留痕，不静默吞掉），返回 `None`。
    """
    if not department:
        _record_skip(audit, evaluator, department or "", "department_unknown")
        return None

    if department not in mapping:
        _record_skip(audit, evaluator, department, "department_not_in_mapping")
        return None

    chatid = mapping.get(department)
    if not chatid:
        _record_skip(audit, evaluator, department, "group_chatid_not_configured")
        return None

    return chatid


def _record_skip(audit: AuditLogger, evaluator: str, department: str, reason: str) -> None:
    audit.record(
        AuditEvent(
            scenario="wecom-aibot",
            action="followup_group_cc_skipped",
            evaluator=evaluator,
            automation_level="L1",
            decision={"department": department, "reason": reason},
            data_sources={},
        )
    )
