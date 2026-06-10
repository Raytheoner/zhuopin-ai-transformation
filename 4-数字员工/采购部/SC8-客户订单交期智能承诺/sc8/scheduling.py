"""SMT 排产（收割自 supplychain smt_scheduling）。

SMT 完工日 = max(所有物料到货日)（齐料日/关键路径）+ SMT 工时（自然日，MVP 简化）。
工时表本批用 dict 注入（mock）；真实切换接 U9C / SRM 工时来源（任务 N.1）。
"""
from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path


def load_smt_lead_time(csv_path: Path | str) -> dict[str, int]:
    """从 CSV 加载 SMT 工时对照表 { product_id: smt_lead_days }。"""
    result: dict[str, int] = {}
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            product_id = row["product_id"].strip()
            lead_days = row["smt_lead_days"].strip()
            if product_id and lead_days:
                result[product_id] = int(lead_days)
    return result


def schedule_smt(
    product_id: str,
    material_arrivals: dict[str, date],
    lead_time_map: dict[str, int],
) -> date | None:
    """计算 SMT 最早完工日。

    Returns:
        完工日（date），或 None（物料未到齐 / 产品无工时配置 → 无法排产）。
    """
    if product_id not in lead_time_map:        # 未配置工时 → 无法估算
        return None
    if not material_arrivals:                  # 无物料到货记录 → 无法排产
        return None
    latest_arrival = max(material_arrivals.values())   # 齐料日 = 关键路径
    return latest_arrival + timedelta(days=lead_time_map[product_id])
