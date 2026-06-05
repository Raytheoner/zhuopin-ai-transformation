"""
供应商风险评分引擎 — 确定性规则，满足 IATF 16949 可追溯要求。

每个 Scorer 接收原始业务指标，返回 1-5 分（1=最差，5=最优）。
RiskScoringEngine 聚合四维度加权求综合分并映射风险等级。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


# ── 单维度评分器 ──────────────────────────────────────────────────────────────

class DeliveryScorer:
    """交付准时率 → 1-5 分（权重 35%）"""

    DEFAULT_SCORE = 2.5
    DEFAULT_SOURCE = "数据不足"

    def score(self, rate: Optional[float]) -> tuple[float, str]:
        """
        Args:
            rate: 准时率百分比 0-100，None 表示数据不可用

        Returns:
            (score, source_note)
        """
        if rate is None:
            return self.DEFAULT_SCORE, self.DEFAULT_SOURCE
        if rate >= 95:
            return 5.0, ""
        if rate >= 90:
            return 4.0, ""
        if rate >= 80:
            return 3.0, ""
        if rate >= 70:
            return 2.0, ""
        return 1.0, ""


class IQCScorer:
    """IQC 合格率 → 1-5 分（权重 30%）"""

    DEFAULT_SCORE = 2.5
    DEFAULT_SOURCE = "数据不足 - 需人工补录"

    def score(self, rate: Optional[float]) -> tuple[float, str]:
        if rate is None:
            return self.DEFAULT_SCORE, self.DEFAULT_SOURCE
        if rate >= 99:
            return 5.0, ""
        if rate >= 97:
            return 4.0, ""
        if rate >= 95:
            return 3.0, ""
        if rate >= 90:
            return 2.0, ""
        return 1.0, ""


class FinancialScorer:
    """财务稳定性 → 1-5 分（权重 20%）

    两项均值：注册资本（万元）+ 成立年限（年）
    任一为 None 时只用有效项评分，全部缺失返回 1 分。
    """

    def score(
        self,
        registered_capital_wan: Optional[float],
        years_established: Optional[float],
    ) -> tuple[float, str]:
        scores = []
        missing = []

        if registered_capital_wan is not None:
            scores.append(self._capital_score(registered_capital_wan))
        else:
            missing.append("注册资本")

        if years_established is not None:
            scores.append(self._years_score(years_established))
        else:
            missing.append("成立年限")

        if not scores:
            return 1.0, "人工录入缺失"

        note = f"人工录入缺失: {', '.join(missing)}" if missing else ""
        return round(sum(scores) / len(scores), 2), note

    @staticmethod
    def _capital_score(capital: float) -> float:
        if capital >= 5000:
            return 5.0
        if capital >= 1000:
            return 4.0
        if capital >= 500:
            return 3.0
        if capital >= 100:
            return 2.0
        return 1.0

    @staticmethod
    def _years_score(years: float) -> float:
        if years >= 10:
            return 5.0
        if years >= 5:
            return 4.0
        if years >= 3:
            return 3.0
        if years >= 1:
            return 2.0
        return 1.0


class SingleSourceScorer:
    """单源依赖风险 → 1-5 分（权重 15%）

    输入枚举 1-5（对应菜单选项），None 时默认最保守值 1。
    """

    # 菜单选项 → 分值
    OPTION_SCORES = {1: 5.0, 2: 4.0, 3: 3.0, 4: 2.0, 5: 1.0}

    DEFAULT_SCORE = 1.0
    DEFAULT_SOURCE = "需采购主数据确认"

    def score(self, option: Optional[int]) -> tuple[float, str]:
        if option is None:
            return self.DEFAULT_SCORE, self.DEFAULT_SOURCE
        return self.OPTION_SCORES.get(option, 1.0), ""


# ── 聚合引擎 ─────────────────────────────────────────────────────────────────

@dataclass
class DimensionScore:
    value: float
    source: str = ""


@dataclass
class ScoringResult:
    delivery: DimensionScore
    iqc: DimensionScore
    financial: DimensionScore
    single_source: DimensionScore
    composite_score: float = 0.0
    risk_level: int = 3
    weights: dict = field(default_factory=lambda: {
        "delivery": 0.35,
        "iqc": 0.30,
        "financial": 0.20,
        "single_source": 0.15,
    })

    LEVEL_LABELS = {
        1: "极低", 2: "低", 3: "中", 4: "高", 5: "极高"
    }

    @property
    def risk_label(self) -> str:
        return self.LEVEL_LABELS.get(self.risk_level, "未知")


class RiskScoringEngine:
    """接收四维度原始指标，计算综合风险评分和等级。"""

    WEIGHTS = {"delivery": 0.35, "iqc": 0.30, "financial": 0.20, "single_source": 0.15}

    def __init__(self):
        self._delivery = DeliveryScorer()
        self._iqc = IQCScorer()
        self._financial = FinancialScorer()
        self._single_source = SingleSourceScorer()

    def evaluate(
        self,
        delivery_rate: Optional[float] = None,
        iqc_rate: Optional[float] = None,
        registered_capital_wan: Optional[float] = None,
        years_established: Optional[float] = None,
        single_source_option: Optional[int] = None,
    ) -> ScoringResult:
        d_val, d_src = self._delivery.score(delivery_rate)
        i_val, i_src = self._iqc.score(iqc_rate)
        f_val, f_src = self._financial.score(registered_capital_wan, years_established)
        s_val, s_src = self._single_source.score(single_source_option)

        composite = round(
            d_val * self.WEIGHTS["delivery"]
            + i_val * self.WEIGHTS["iqc"]
            + f_val * self.WEIGHTS["financial"]
            + s_val * self.WEIGHTS["single_source"],
            2,
        )

        result = ScoringResult(
            delivery=DimensionScore(d_val, d_src),
            iqc=DimensionScore(i_val, i_src),
            financial=DimensionScore(f_val, f_src),
            single_source=DimensionScore(s_val, s_src),
            composite_score=composite,
            risk_level=self._map_level(composite),
            weights=dict(self.WEIGHTS),
        )
        return result

    @staticmethod
    def _map_level(score: float) -> int:
        """边界值归入较低风险等级（较高数字）。"""
        if score > 4.5:
            return 1
        if score > 3.5:
            return 2
        if score > 2.5:
            return 3
        if score > 1.5:
            return 4
        return 5
