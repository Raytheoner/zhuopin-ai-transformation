"""发送人→部门映射加载（design.md D7）。非代码硬编码，配置进同目录 yaml。"""
from __future__ import annotations

from pathlib import Path

import yaml

DEFAULT_MAPPING_PATH = Path(__file__).parent / "department_mapping.yaml"

# 未命中映射表时的 fail-closed 落点（design.md D7：不猜测部门）。
UNMATCHED_DEPARTMENT = "待分拣"


def load_department_mapping(path: Path | None = None) -> dict[str, str]:
    target = path or DEFAULT_MAPPING_PATH
    raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"部门映射表格式错误（应为 mapping）：{target}")
    return {str(k): str(v) for k, v in raw.items()}


def resolve_department(sender: str, mapping: dict[str, str]) -> str:
    """未命中 fail-closed 归入 `UNMATCHED_DEPARTMENT`，不做模糊匹配/猜测。"""
    return mapping.get(sender, UNMATCHED_DEPARTMENT)
