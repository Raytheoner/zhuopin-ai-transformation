"""baoguan.py 端到端多层 BOM 展开（B1，shortage-multilevel-bom-b1，2026-07-13）。

姚祖怡 2026-07-09 批改发现：S02Y.0035 的瓶颈子件 R02A.0019 藏在未展开的半成品
下，既未被识别为缺料也未被现货覆盖，"按期"判断失真。本文件在 assess_supply_risk
整条链路上复现该场景（`_gross_need`/`estimate_material_arrivals` 的单元测试见
`tests/test_bom_multilevel_explosion.py`）。多层展开无条件生效（非开关控制）。
"""
from __future__ import annotations

from datetime import date

from zhuopin_platform.shared_tools.models import BomRow

from sc8.baoguan import RISK_GREEN, assess_supply_risk
from sc8.models import SalesOrder

TODAY = date(2026, 6, 22)


def _so(item="S02Y.0035", ship="2026-09-01", qty=500):
    return SalesOrder(so_id=f"FO-{item}", customer_id="", customer_name="客户A",
                      item_code=item, qty=qty, required_date=ship,
                      doc_type="预测订单", item_name="ECU")


def _bom_row(product, component, qty=1.0, level=1):
    return BomRow(product_id=product, component_id=component, component_name=component,
                 level=level, qty_per_unit=qty, loss_rate=0.0, unit="PCS")


def test_yao_scenario_semi_finished_raw_material_shortage_visible():
    """半成品无货、真原材料 R02A.0019 也无货无 SRM 承诺
    → 应判待催（不是按期），且 R02A.0019 必须实际出现在 no_feedback_materials 里
    （不是靠半成品巧合撞出同色）。"""
    so = _so(item="S02Y.0035", qty=500)
    bom = [
        _bom_row("S02Y.0035", "SEMI_X", qty=1.0),
        _bom_row("SEMI_X", "R02A.0019", qty=2.0),
    ]
    row = assess_supply_risk(so, bom, srm_deliveries=[], today=TODAY)
    assert row.risk != RISK_GREEN, "R02A.0019 无货无承诺，不应判按期"
    assert "R02A.0019" in row.no_feedback_materials
    assert "SEMI_X" not in row.no_feedback_materials, "半成品不应被当作待答交物料"


def test_single_level_bom_unchanged():
    """无半成品的单层 BOM：结果与改造前完全一致（向后兼容）。"""
    so = _so(item="F02N.0040", qty=10)
    bom = [_bom_row("F02N.0040", "R01"), _bom_row("F02N.0040", "R02")]
    row = assess_supply_risk(so, bom, srm_deliveries=[], today=TODAY)
    assert row.has_bom is True
    assert row.component_count == 2
