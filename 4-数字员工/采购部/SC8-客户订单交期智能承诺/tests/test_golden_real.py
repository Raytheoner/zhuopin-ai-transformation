"""真实黄金基准回归（任务：内部真实验证沉淀）。

确定性回归：replay 冻结的真实输入（FO/BOM/SRM 快照）→ compute_forecasts →
断言输出与 expected.json 完全一致（关键路径齐料日 / 日期加减 / 风险 / 置信度 / 瓶颈物料）。
**离线、不触网**——冻结夹具让真实数据变可复跑的回归。

夹具由 `scripts/build_golden_real.py` 在 FO 在线时生成到 data/golden/real_frozen/。
未生成（FO 宕机期）→ 整组跳过，不阻塞 mock 套件。
夹具目录可经环境变量 SC8_GOLDEN_DIR 覆盖（验证脚本机理用）。
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import pytest

from zhuopin_platform.shared_tools.models import BomRow, SrmDeliveryOrder

from sc8.config import ForecastParams
from sc8.forecast import estimate_material_arrivals  # noqa: F401 (确保引擎可导)
from sc8.models import SalesOrder
from sc8.pipeline import compute_forecasts
from sc8.config import is_outsourced  # noqa: F401

_DEFAULT_DIR = Path(__file__).resolve().parent.parent / "data" / "golden" / "real_frozen"
GOLDEN_DIR = Path(os.environ.get("SC8_GOLDEN_DIR", str(_DEFAULT_DIR)))

pytestmark = pytest.mark.skipif(
    not (GOLDEN_DIR / "expected.json").exists(),
    reason=f"真实黄金夹具未生成（{GOLDEN_DIR}）；FO 在线后跑 scripts/build_golden_real.py 生成",
)


def _load():
    orders = [SalesOrder(**o) for o in json.loads((GOLDEN_DIR / "frozen_orders.json").read_text("utf-8"))]
    bom = [BomRow(**r) for r in json.loads((GOLDEN_DIR / "frozen_bom.json").read_text("utf-8"))]
    srm = [SrmDeliveryOrder(**d) for d in json.loads((GOLDEN_DIR / "frozen_srm.json").read_text("utf-8"))]
    meta = json.loads((GOLDEN_DIR / "frozen_meta.json").read_text("utf-8"))
    expected = json.loads((GOLDEN_DIR / "expected.json").read_text("utf-8"))
    p = meta["params"]
    params = ForecastParams(
        param_version=meta["param_version"],
        no_feedback_lead_days=p["no_feedback_lead_days"],
        outsource_extra_days=p["outsource_extra_days"],
        logistics_days=p["logistics_days"],
    )
    lead = {o.item_code: meta["smt_lead_mock_days"] for o in orders}
    from sc8 import config
    return orders, bom, srm, params, lead, expected, config.outsource_ids_from_env()


def test_real_golden_deterministic_no_drift():
    """冻结真实输入 → 预测输出与 expected.json 零漂移（确定性逻辑回归）。"""
    orders, bom, srm, params, lead, expected, out_ids = _load()
    forecasts = compute_forecasts(orders, bom, srm, lead, params=params, outsource_ids=out_ids)
    got = {f.so_id: f for f in forecasts}
    assert len(got) == len(expected), "预测条数与基准不符"
    for exp in expected:
        fc = got[exp["so_id"]]
        fd = fc.forecast_date.isoformat() if fc.forecast_date else None
        assert fd == exp["forecast_date"], f"{exp['so_id']} 预测交付日漂移"
        assert fc.delay_days == exp["delay_days"], f"{exp['so_id']} 延期天数漂移"
        assert fc.risk_level == exp["risk_level"], f"{exp['so_id']} 风险等级漂移"
        assert fc.confidence == exp["confidence"], f"{exp['so_id']} 置信度漂移"
        assert fc.bottleneck_material == exp["bottleneck_material"], f"{exp['so_id']} 瓶颈物料漂移"
