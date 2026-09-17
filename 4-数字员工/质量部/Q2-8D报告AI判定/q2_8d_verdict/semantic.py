"""语义层接口：24 条语义规则 ＋ 语义红线①②⑤（③本批同列）的判定来源。

🔴 档 1 没有 LLM 实现。`PENDING.SEMANTIC_LAYER_ACCEPTANCE` 未签认 ⇒ 默认来源 `PendingSemantic` 对一切返回
``None``（＝待人工）。`HumanVerdictSource` 承接质量工程师的人工裁决（L2 判例采集入口），其结论为**确认态**；
未来 LLM 来源（V3 固定模型＋prompt 版本、V4 二级置信）返回的红线结论为**疑似态**（P1），由 `kind` 区分。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .models import EightDInput


class SemanticSource(Protocol):
    kind: str   # "pending" | "human" | "llm"

    def rule_ratio(self, rule_id: str, doc: EightDInput) -> float | None: ...
    def redline_triggered(self, redline_no: int, doc: EightDInput) -> bool | None: ...


class PendingSemantic:
    """签认前唯一可用来源：什么都不判。"""
    kind = "pending"

    def rule_ratio(self, rule_id: str, doc: EightDInput) -> float | None:
        return None

    def redline_triggered(self, redline_no: int, doc: EightDInput) -> bool | None:
        return None


@dataclass
class HumanVerdictSource:
    """质量工程师逐条人工裁决（按 report_id 隔离）。值为得分比例 0–1 与红线是否触发。"""
    kind: str = "human"
    rules: dict[str, dict[str, float]] = field(default_factory=dict)      # report_id → {rule_id: ratio}
    redlines: dict[str, dict[int, bool]] = field(default_factory=dict)    # report_id → {no: triggered}

    def rule_ratio(self, rule_id: str, doc: EightDInput) -> float | None:
        v = self.rules.get(doc.report_id, {}).get(rule_id)
        if v is not None and not 0.0 <= v <= 1.0:
            raise ValueError(f"人工裁决比例越界：{doc.report_id}/{rule_id}={v}")
        return v

    def redline_triggered(self, redline_no: int, doc: EightDInput) -> bool | None:
        return self.redlines.get(doc.report_id, {}).get(redline_no)
