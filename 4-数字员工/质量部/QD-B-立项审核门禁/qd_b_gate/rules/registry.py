"""规则注册表 —— 加载 data/rules/registry.json（工作汇总.xlsx 的机器可读快照）。

规则即数据（design.md D2）：判定逻辑在代码（deterministic.py / semantic.py），
规则元数据（ID/章节/检查项/适用类型/严重度/阈值/取数锚点/分类）在注册表。
规则函数按 rule_id 挂到注册表条目，缺函数的条目视为「未实现」。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path(__file__).resolve().parent.parent.parent / "data/rules/registry.json"


@dataclass(frozen=True)
class Rule:
    rule_id: str
    section: str
    check_item: str
    applies_to: str          # 开发（适用类型）
    severity: str            # 阻断/重要/一般/提示（原表 J 列）
    severity_level: str      # 错误/警告/提示（映射后，封面三级）
    check_type: str          # 完整性/合规性/计算准确性/一致性/逻辑合理性
    pass_condition: str
    threshold: str
    source_anchor: str       # 取数来源（章节锚点）
    impl_class: str          # A 可机器核 / B 半自动 / C 转人工
    blocking: bool           # 是否一票否决（severity_level == 错误）
    trial_result: str = ""   # 华丰试评结果（黄金基准雏形）

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Rule":
        return cls(
            rule_id=str(d.get("rule_id", "")),
            section=d.get("section", ""),
            check_item=d.get("check_item", ""),
            applies_to=d.get("applies_to", ""),
            severity=d.get("severity", ""),
            severity_level=d.get("severity_level", ""),
            check_type=d.get("check_type", ""),
            pass_condition=d.get("pass_condition", ""),
            threshold=d.get("threshold", ""),
            source_anchor=d.get("source_anchor", ""),
            impl_class=d.get("impl_class", "A"),
            blocking=bool(d.get("blocking", False)),
            trial_result=d.get("trial_result", ""),
        )


class RuleRegistry:
    def __init__(self, data: dict[str, Any]):
        self.rule_version: str = data.get("rule_version", "")
        self.source: str = data.get("source", "")
        self.severity_map: dict[str, str] = data.get("severity_map", {})
        self.rules: list[Rule] = [Rule.from_dict(r) for r in data.get("rules", [])]
        self._by_id = {r.rule_id: r for r in self.rules}

    def __len__(self) -> int:
        return len(self.rules)

    def get(self, rule_id: str | int) -> Rule | None:
        return self._by_id.get(str(rule_id))

    def by_class(self, impl_class: str) -> list[Rule]:
        return [r for r in self.rules if r.impl_class == impl_class]

    def blocking_rules(self) -> list[Rule]:
        return [r for r in self.rules if r.blocking]

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in self.rules:
            out[r.impl_class] = out.get(r.impl_class, 0) + 1
        return out


@lru_cache(maxsize=1)
def load_registry(path: str | Path | None = None) -> RuleRegistry:
    p = Path(path) if path else REGISTRY_PATH
    data = json.loads(p.read_text(encoding="utf-8"))
    return RuleRegistry(data)
