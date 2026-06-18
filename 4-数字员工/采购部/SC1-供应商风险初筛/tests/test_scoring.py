import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.scoring import (
    DeliveryScorer, IQCScorer, FinancialScorer,
    SingleSourceScorer, RiskScoringEngine,
)


class TestDeliveryScorer:
    def setup_method(self):
        self.scorer = DeliveryScorer()

    def test_above_95(self):
        assert self.scorer.score(95.0)[0] == 5.0
        assert self.scorer.score(100.0)[0] == 5.0

    def test_90_to_94(self):
        assert self.scorer.score(90.0)[0] == 4.0
        assert self.scorer.score(94.9)[0] == 4.0

    def test_80_to_89(self):
        assert self.scorer.score(80.0)[0] == 3.0
        assert self.scorer.score(89.9)[0] == 3.0

    def test_70_to_79(self):
        assert self.scorer.score(70.0)[0] == 2.0

    def test_below_70(self):
        assert self.scorer.score(69.9)[0] == 1.0
        assert self.scorer.score(0.0)[0] == 1.0

    def test_none_returns_default(self):
        val, src = self.scorer.score(None)
        assert val == 2.5
        assert "数据不足" in src


class TestIQCScorer:
    def setup_method(self):
        self.scorer = IQCScorer()

    def test_above_99(self):
        assert self.scorer.score(99.0)[0] == 5.0
        assert self.scorer.score(100.0)[0] == 5.0

    def test_97_to_98(self):
        assert self.scorer.score(97.0)[0] == 4.0
        assert self.scorer.score(98.9)[0] == 4.0

    def test_95_to_96(self):
        assert self.scorer.score(95.0)[0] == 3.0

    def test_90_to_94(self):
        assert self.scorer.score(90.0)[0] == 2.0

    def test_below_90(self):
        assert self.scorer.score(89.9)[0] == 1.0

    def test_none_returns_default(self):
        val, src = self.scorer.score(None)
        assert val == 2.5
        assert "数据不足" in src


class TestFinancialScorer:
    def setup_method(self):
        self.scorer = FinancialScorer()

    def test_high_capital_and_years(self):
        val, src = self.scorer.score(5000.0, 10.0)
        assert val == 5.0
        assert src == ""

    def test_medium_values(self):
        val, _ = self.scorer.score(1000.0, 5.0)
        assert val == 4.0

    def test_capital_only(self):
        val, src = self.scorer.score(500.0, None)
        assert val == 3.0
        assert "成立年限" in src

    def test_years_only(self):
        val, src = self.scorer.score(None, 3.0)
        assert val == 3.0
        assert "注册资本" in src

    def test_both_none(self):
        val, src = self.scorer.score(None, None)
        assert val == 1.0
        assert "缺失" in src

    def test_capital_below_100(self):
        val, _ = self.scorer.score(50.0, 10.0)
        assert val == (1.0 + 5.0) / 2

    def test_less_than_1_year(self):
        val, _ = self.scorer.score(5000.0, 0.5)
        assert val == (5.0 + 1.0) / 2


class TestSingleSourceScorer:
    def setup_method(self):
        self.scorer = SingleSourceScorer()

    def test_option_1_is_5(self):
        assert self.scorer.score(1)[0] == 5.0

    def test_option_5_is_1(self):
        assert self.scorer.score(5)[0] == 1.0

    def test_none_returns_default_1(self):
        val, src = self.scorer.score(None)
        assert val == 1.0
        assert src != ""


class TestRiskScoringEngine:
    def setup_method(self):
        self.engine = RiskScoringEngine()

    def test_all_perfect(self):
        result = self.engine.evaluate(
            delivery_rate=98.0,
            iqc_rate=99.5,
            registered_capital_wan=5000.0,
            years_established=15.0,
            single_source_option=1,
        )
        assert result.composite_score == 5.0
        assert result.risk_level == 1

    def test_all_poor(self):
        result = self.engine.evaluate(
            delivery_rate=50.0,
            iqc_rate=80.0,
            registered_capital_wan=50.0,
            years_established=0.5,
            single_source_option=5,
        )
        assert result.composite_score == 1.0
        assert result.risk_level == 5

    def test_boundary_4_5_is_level_2(self):
        # 构造使综合分恰好 = 4.5：delivery=5,iqc=5,financial=5,single=1
        # 5*0.35 + 5*0.30 + 5*0.20 + 1*0.15 = 1.75+1.5+1.0+0.15 = 4.4 ≠ 4.5
        # delivery=5,iqc=5,financial=3,single=5
        # 5*0.35+5*0.30+3*0.20+5*0.15 = 1.75+1.5+0.6+0.75 = 4.6 → 1级
        # 需精确构造：delivery=5,iqc=5,financial=2,single=5
        # 5*0.35+5*0.30+2*0.20+5*0.15 = 1.75+1.5+0.4+0.75 = 4.4 → 2级
        result = self.engine.evaluate(
            delivery_rate=98.0,   # 5
            iqc_rate=99.0,        # 5
            registered_capital_wan=50.0,  # 1 → capital=1, years=5 → avg=(1+4)/2=2.5
            years_established=5.0,
            single_source_option=1,  # 5
        )
        # 5*0.35+5*0.30+2.5*0.20+5*0.15 = 1.75+1.5+0.5+0.75 = 4.5 → level 2
        assert result.composite_score == 4.5
        assert result.risk_level == 2  # boundary: 4.5 → 2级

    def test_boundary_1_5_is_level_5(self):
        result = self.engine.evaluate(
            delivery_rate=65.0,    # 1
            iqc_rate=88.0,         # 1
            registered_capital_wan=50.0,  # capital=1, years_est below constructs 1
            years_established=0.5,
            single_source_option=5,  # 1
        )
        # 1*0.35+1*0.30+1*0.20+1*0.15 = 1.0 → level 5
        assert result.composite_score == 1.0
        assert result.risk_level == 5

    def test_all_none_excludes_delivery_and_renormalizes(self):
        # 交付 rate=None → 剔除交付维度，对 iqc/financial/single 归一化（/0.65）：
        # (2.5*0.30 + 1.0*0.20 + 1.0*0.15)/0.65 = 1.10/0.65 = 1.6923 → 1.69
        result = self.engine.evaluate()
        assert result.composite_score == 1.69
        assert result.risk_level == 4
        assert result.weights["delivery"] == 0.0   # 交付维度被剔除，有效权重 0

    def test_weights_sum_to_1(self):
        result = self.engine.evaluate()
        assert abs(sum(result.weights.values()) - 1.0) < 1e-9

    def test_delivery_present_keeps_original_weights(self):
        # 交付有真实数据时，权重不变（35/30/20/15），与历史行为一致
        result = self.engine.evaluate(delivery_rate=98.0, iqc_rate=99.0,
                                       registered_capital_wan=5000.0,
                                       years_established=10.0, single_source_option=1)
        assert result.weights == {"delivery": 0.35, "iqc": 0.30,
                                   "financial": 0.20, "single_source": 0.15}
        assert result.composite_score == 5.0

    def test_delivery_insufficient_does_not_force_high_risk(self):
        """回归 ZB0022 失真：交付数据不足不应把还不错的供应商压成极高风险。

        旧逻辑：delivery=0%(1分)*0.35 拉低综合分 → 误判 5 级。
        新逻辑：剔除交付维度后，按 iqc/financial/single 归一化评估。
        """
        # iqc=99(5)、财务=5000万/10年(5)、单源=有替代(option1→5)，交付数据不足
        result = self.engine.evaluate(
            delivery_rate=None, iqc_rate=99.0,
            registered_capital_wan=5000.0, years_established=10.0,
            single_source_option=1,
        )
        # (5*0.30 + 5*0.20 + 5*0.15)/0.65 = 3.25/0.65 = 5.0 → 1 级（极低风险）
        assert result.composite_score == 5.0
        assert result.risk_level == 1
        assert result.risk_level != 5   # 关键：不再因 0% 假象误判极高

    def test_result_has_risk_label(self):
        result = self.engine.evaluate(delivery_rate=98.0, iqc_rate=99.0,
                                       registered_capital_wan=5000.0,
                                       years_established=10.0,
                                       single_source_option=1)
        assert result.risk_label in ("极低", "低", "中", "高", "极高")
