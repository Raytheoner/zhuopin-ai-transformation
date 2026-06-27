"""规则引擎 —— 82 条规则注册表 + 确定性判定（A 类）。"""
from .registry import Rule, RuleRegistry, load_registry

__all__ = ["Rule", "RuleRegistry", "load_registry"]
