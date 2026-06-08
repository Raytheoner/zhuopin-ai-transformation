"""通用审计事件 —— 所有数字员工场景共用的留痕结构。"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass
class AuditEvent:
    """一次 AI 辅助决策的完整追溯记录。

    字段对所有场景通用；场景特有内容放进 ``payload``（仅决策结果，
    不含原始红色数据）。``content_hash`` 用于校验 AI 生成文本未被篡改。
    """

    scenario: str            # 场景编号，如 "SC1" / "Q1" / "FI1"
    action: str              # 动作，如 "supplier_risk_eval" / "complaint_triage"
    evaluator: str           # 人工责任人（L2 场景必填，IATF 要求可归责）
    automation_level: str    # "L1" / "L2" / "L3"
    decision: dict[str, Any] = field(default_factory=dict)   # 结构化决策结果
    data_sources: dict[str, str] = field(default_factory=dict)  # 各输入的来源
    content_hash: str = ""   # AI 生成文本的 SHA-256
    oem_context: str = ""    # 涉及 OEM 数据时的客户上下文（隔离审计）
    report_path: str = ""
    error: str = ""
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(tz=timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if not d.get("error"):
            d.pop("error", None)
        return d
