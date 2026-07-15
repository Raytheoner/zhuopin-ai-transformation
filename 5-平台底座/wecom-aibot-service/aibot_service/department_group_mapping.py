"""部门→企微群 chatid 映射加载（Paul 2026-07-12 拍板：归档成功后机器人回
部门群发一条通报留痕）。加载方式与 `department_mapping.py`（发送人→部门）
同构，但这是第二张独立映射表——不要合并，键的语义不同（userid vs 部门名）。
"""
from __future__ import annotations

from pathlib import Path

import yaml

DEFAULT_GROUP_MAPPING_PATH = Path(__file__).parent / "department_group_mapping.yaml"

# 真实 chatid 到位前的占位符前缀——真实值不可能以此开头（真实 chatid 是企微
# 分配的不透明 ID），据此可安全区分"未配置"与"配置了但连不上"两种失败。
_PLACEHOLDER_PREFIX = "PLACEHOLDER_"


def load_department_group_mapping(path: Path | None = None) -> dict[str, str]:
    target = path or DEFAULT_GROUP_MAPPING_PATH
    raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"部门群映射表格式错误（应为 mapping）：{target}")
    return {str(k): str(v) for k, v in raw.items()}


def resolve_group_chatid(department: str, mapping: dict[str, str]) -> str | None:
    """未命中或仍是占位符时返回 None（fail-closed，调用方应跳过通报而非误发）。"""
    chatid = mapping.get(department)
    if not chatid or chatid.startswith(_PLACEHOLDER_PREFIX):
        return None
    return chatid
