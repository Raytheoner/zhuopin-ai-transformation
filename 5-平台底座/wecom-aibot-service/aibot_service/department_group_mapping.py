"""部门→群 webhook 环境变量名映射加载（Paul 2026-07-12 拍板，2026-07-15 定型
为 webhook 机制）。与 `department_mapping.py`（发送人→部门）同构但是第二张
独立映射表——不要合并，键的语义不同（部门名 vs userid），值的语义也不同
（这里存的是环境变量名，不是真实凭据，真实 webhook URL 只落 `.env`）。
"""
from __future__ import annotations

from pathlib import Path

import yaml

DEFAULT_GROUP_MAPPING_PATH = Path(__file__).parent / "department_group_mapping.yaml"


def load_department_group_mapping(path: Path | None = None) -> dict[str, str]:
    target = path or DEFAULT_GROUP_MAPPING_PATH
    raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"部门群映射表格式错误（应为 mapping）：{target}")
    return {str(k): str(v) for k, v in raw.items()}
