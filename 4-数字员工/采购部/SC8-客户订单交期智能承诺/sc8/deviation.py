"""承诺交期偏差监控（C1 / 审计报告 §3.3 P1-D，SOP §4.3）。

消费 `config.DEVIATION_ALERT_DAYS`（VP 2026-06-11 签字 = 3 天）：把"已对客承诺的交付日"
与"最新实际进展推算的交付日"比对，偏差**严格大于**阈值（或最新已无法预测）→
① 告警（breached）；② 触发重算（注入回调 on_breach）；③ 写 audit 留痕。

纯函数 + 依赖注入（与 pipeline 一致）：off-LAN 用 mock 日期序列即可完整验证。
"实际进展"由编排层用最新数据重跑 compute_forecasts 得到 forecast_date 后喂入本模块
（本模块不耦合连接器，不直接对客发送——更正走既有 notify.build_correction_draft + L2 门禁）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from zhuopin_platform.audit import AuditEvent, AuditLogger

from . import config

SCENARIO = "SC8"
ACTION_DEVIATION_ALERT = "delivery_deviation_alert"


@dataclass
class DeviationResult:
    """一条承诺的偏差监控结果。"""
    so_id:              str
    customer_name:      str
    committed_date:     date
    actual_date:        date | None     # 最新实际进展推算交付日（None=现已无法预测）
    deviation_days:     int | None      # abs 天数差；None=无法预测
    breached:           bool            # 超阈值（或无法预测）→ 需告警
    requires_recompute: bool


def evaluate_deviation(
    committed_date: date,
    actual_date: date | None,
    *,
    threshold_days: int = config.DEVIATION_ALERT_DAYS,
) -> tuple[int | None, bool]:
    """计算偏差天数与是否超阈值。

    actual_date=None（最新无法预测）→ 视为重大偏差（breached=True，C1-b 拍板）。
    否则 deviation = abs((actual_date - committed_date).days)；**严格大于** 阈值才告警。
    """
    if actual_date is None:
        return None, True
    deviation_days = abs((actual_date - committed_date).days)
    return deviation_days, deviation_days > threshold_days


def monitor_deviation(
    committed_date: date,
    actual_date: date | None,
    *,
    so_id: str,
    customer_name: str = "",
    threshold_days: int = config.DEVIATION_ALERT_DAYS,
    audit: AuditLogger | None = None,
    on_breach: Callable[[DeviationResult], None] | None = None,
) -> DeviationResult:
    """监控一条承诺的偏差：超阈值 → 写审计 + 触发重算回调。

    Args:
        committed_date: 此前对客承诺的交付日。
        actual_date:    最新实际进展推算交付日（None=现已无法预测）。
        audit:          None 则不留痕（测试/离线）。
        on_breach:      超阈值时调用（注入"重跑 compute_forecasts + record_correction"等）；
                        None 则仅告警 + 留痕，不触发重算。
    """
    deviation_days, breached = evaluate_deviation(
        committed_date, actual_date, threshold_days=threshold_days)
    result = DeviationResult(
        so_id=so_id, customer_name=customer_name,
        committed_date=committed_date, actual_date=actual_date,
        deviation_days=deviation_days, breached=breached,
        requires_recompute=breached,
    )
    if breached:
        if audit is not None:
            audit.record(AuditEvent(
                scenario=SCENARIO,
                action=ACTION_DEVIATION_ALERT,
                evaluator="",
                automation_level="L2",
                decision={
                    "so_id": so_id,
                    "customer_name": customer_name,
                    "committed_date": committed_date.isoformat(),
                    "actual_date": actual_date.isoformat() if actual_date else None,
                    "deviation_days": deviation_days,
                    "threshold_days": threshold_days,
                    "reason": "无法预测交付日" if actual_date is None else "偏差超阈值",
                },
            ))
        if on_breach is not None:
            on_breach(result)
    return result
