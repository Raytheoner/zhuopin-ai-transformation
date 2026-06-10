"""
SC3 在途跟踪引擎测试。
今日固定为 2026-05-09，与 supplychain test_supplier_tracking.py 黄金基准对齐。
覆盖三类：(1) 等价对照（Golden Baseline），(2) 风险分级单元，(3) srm_dates 注入。
"""
from datetime import date
from pathlib import Path

from sc3_intransit.intransit_engine import SupplierRisk, _classify_risk, analyze
from zhuopin_platform.shared_tools.csv_connector import CSVConnector

TODAY = date(2026, 5, 9)
MOCK_DIR = Path(__file__).parent / "mock_data"


def _connector():
    return CSVConnector(MOCK_DIR)


# ---------------------------------------------------------------------------
# Golden Baseline — 与 supplychain/tests/test_supplier_tracking.py 等价对照
# ---------------------------------------------------------------------------

class TestGoldenBaseline:
    """对照 supplychain test_supplier_tracking.py TestGoldenBaseline，逐场景等价。"""

    def _results(self):
        return analyze(_connector(), today=TODAY, planning_days=14)

    def test_po001_high_risk_overdue(self):
        """PO-001 M001：承诺交期 2026-05-07，已逾期 2 天 → 🔴"""
        r = next(x for x in self._results() if x.po_id == "PO-001")
        assert r.risk_level == "high"
        assert r.days_remaining == -2

    def test_po002_medium_risk_4days(self):
        """PO-002 M004：4 天后到期，DOS 充裕 → 🟡"""
        r = next(x for x in self._results() if x.po_id == "PO-002")
        assert r.risk_level == "medium"
        assert r.days_remaining == 4

    def test_po003_low_risk(self):
        """PO-003 M006：21 天后到期 → 🟢"""
        r = next(x for x in self._results() if x.po_id == "PO-003")
        assert r.risk_level == "low"
        assert r.days_remaining == 21

    def test_po004_high_risk_dual_trigger(self):
        """PO-004 M015：3 天到期且 DOS=2.33 天 → 🔴（双触发）"""
        r = next(x for x in self._results() if x.po_id == "PO-004")
        assert r.risk_level == "high"
        assert r.days_remaining == 3
        assert r.dos_days < 5

    def test_po005_medium_risk_7days(self):
        """PO-005 M012：恰好 7 天 → 🟡（边界值）"""
        r = next(x for x in self._results() if x.po_id == "PO-005")
        assert r.risk_level == "medium"
        assert r.days_remaining == 7

    def test_po006_received_skipped(self):
        """PO-006 M010：status=received → 不出现在结果中"""
        ids = [x.po_id for x in self._results()]
        assert "PO-006" not in ids

    def test_total_count(self):
        """共 5 笔在途订单（跳过 1 笔已收货）"""
        assert len(self._results()) == 5

    def test_sorted_by_risk(self):
        """结果按风险等级排序：high → medium → low"""
        levels = [r.risk_level for r in self._results()]
        high_idx   = [i for i, l in enumerate(levels) if l == "high"]
        medium_idx = [i for i, l in enumerate(levels) if l == "medium"]
        low_idx    = [i for i, l in enumerate(levels) if l == "low"]
        assert max(high_idx) < min(medium_idx)
        assert max(medium_idx) < min(low_idx)


# ---------------------------------------------------------------------------
# 风险分级单元测试 — 与 supplychain TestRiskClassification 等价
# ---------------------------------------------------------------------------

class TestRiskClassification:
    """独立单元测试：风险判定逻辑，不依赖 mock 文件。"""

    def _classify(self, days_remaining: int, dos_days: float) -> SupplierRisk:
        return _classify_risk(days_remaining, dos_days)

    def test_high_by_days_overdue(self):
        assert self._classify(-1, 20).risk_level == "high"

    def test_high_by_days_3(self):
        assert self._classify(3, 20).risk_level == "high"

    def test_high_by_dos(self):
        assert self._classify(10, 4).risk_level == "high"

    def test_medium_by_days_7(self):
        assert self._classify(7, 20).risk_level == "medium"

    def test_medium_by_dos(self):
        assert self._classify(10, 9).risk_level == "medium"

    def test_low(self):
        assert self._classify(8, 20).risk_level == "low"

    def test_boundary_days_3_is_high(self):
        assert self._classify(3, 20).risk_level == "high"

    def test_boundary_days_4_is_medium(self):
        assert self._classify(4, 20).risk_level == "medium"

    def test_boundary_days_7_is_medium(self):
        assert self._classify(7, 20).risk_level == "medium"

    def test_boundary_days_8_is_low(self):
        assert self._classify(8, 20).risk_level == "low"

    def test_boundary_dos_below5_is_high(self):
        assert self._classify(10, 4.9).risk_level == "high"

    def test_boundary_dos_below10_is_medium(self):
        assert self._classify(10, 9.9).risk_level == "medium"

    def test_high_reasons_overdue(self):
        r = self._classify(-1, 20)
        assert any("已过" in s or "承诺交期" in s for s in r.risk_reasons)

    def test_high_reasons_low_dos(self):
        r = self._classify(10, 3)
        assert any("DOS" in s for s in r.risk_reasons)


# ---------------------------------------------------------------------------
# srm_dates 注入测试 — 与 supplychain TestSrmDatesInjection 等价
# ---------------------------------------------------------------------------

class TestSrmDatesInjection:
    """srm_dates 注入：覆盖 CSV 承诺交期，验证风险重新计算。"""

    def test_srm_dates_overrides_csv(self):
        """PO-001 延后到 2026-06-01 → 变低风险"""
        srm_dates = {"PO-001": "2026-06-01"}
        results = analyze(_connector(), today=TODAY, planning_days=14, srm_dates=srm_dates)
        r = next(x for x in results if x.po_id == "PO-001")
        assert r.days_remaining == (date(2026, 6, 1) - TODAY).days  # 23 天
        assert r.risk_level == "low"

    def test_srm_dates_none_fallback(self):
        """不传 srm_dates，行为与原来完全一致"""
        r1 = analyze(_connector(), today=TODAY, planning_days=14, srm_dates=None)
        r2 = analyze(_connector(), today=TODAY, planning_days=14)
        assert [(r.po_id, r.risk_level, r.days_remaining) for r in r1] == \
               [(r.po_id, r.risk_level, r.days_remaining) for r in r2]

    def test_srm_dates_partial_override(self):
        """只覆盖 PO-001，PO-002 保持 CSV 原值"""
        srm_dates = {"PO-001": "2026-06-01"}
        results = analyze(_connector(), today=TODAY, planning_days=14, srm_dates=srm_dates)
        po002 = next(x for x in results if x.po_id == "PO-002")
        assert po002.days_remaining == 4
