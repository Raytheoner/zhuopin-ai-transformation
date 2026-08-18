"""O1 数字员工入口：run_smt_schedule 薄包装 + 审计接入 + 数据源档位闸。

形状对齐 O2 `run_kit_alert()`（dataclass 返回值 + `audit_logger` 可选）。

三条设计约束（openspec 变更包 o1-smt-scheduling-mvp，design 已拍板）：
  · D3 —— 首版自动化等级记 **L1**。首版产出是一个纯计算返回的日期，无任何下发/
    推送/写回动作，没有可供人工确认的动作对象；标 L2 会造出一个空门禁。
    全景规划 §2.1.3 所载 L2 定位在场景具备「排程方案下发车间」能力时生效，
    届时须补人工确认门禁。
  · D4 —— 返回值与审计均携带 `lead_time_is_placeholder`，使「这个完工日能不能
    对外用」不必读代码即可判断。
  · D5 —— real 档位的 fail-loud **由底座 `ZpConnector._fallback_or_failloud` 抛出**，
    本模块只负责把 connector 传进来、不拦截、不自建等价判断。同一语义两处实现
    必然漂移（队列 #308 所根治的那类问题）。
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

from zhuopin_platform.audit import AuditEvent

from .schedule_engine import schedule_smt, load_smt_lead_time, is_placeholder_lead_time


class _PlanSource(Protocol):
    """底座连接器中本场景实际用到的那一小片。"""

    def get_production_plan(self) -> list[Any]: ...


@dataclass
class ScheduleResult:
    """一次排产推算的完整结果。

    刻意把「算出来了」与「没算出来」分成两个字段并列返回，而不是只给成功项——
    只给成功项会让「某个工单悄悄消失」看起来和「它不存在」一模一样。
    """

    products: list[str]                                  # 本次涉及的全部产品
    scheduled: dict[str, date]                           # 产品 → 最早完工日
    unschedulable: dict[str, str]                        # 产品 → 无法排产的原因
    lead_time_is_placeholder: bool                       # 🔴 工时是否为占位数据
    analyzed_at: str
    data_sources: dict[str, str] = field(default_factory=dict)


def run_smt_schedule(
    plans: list[Any] | None,
    material_arrivals: dict[str, dict[str, date]],
    lead_time_map: dict[str, int] | None = None,
    connector: _PlanSource | None = None,
    audit_logger: Any | None = None,
) -> ScheduleResult:
    """SMT 排产入口：取工单 → 逐产品推算完工日 → 写审计 → 返回结果。

    Args:
        plans:             生产计划/工单列表；给 None 且提供 connector 时改由连接器取
        material_arrivals: { product_id: { material_id: 预计到货日 } }
        lead_time_map:     SMT 工时对照表；缺省读随附 CSV 夹具
        connector:         底座连接器。**real 档位下取工单失败会由它抛
                           `RealEndpointNotReadyError`，本函数不捕获、不回退**
        audit_logger:      审计接收方；None ＝ 静默（单测与离线试算用）

    Returns:
        ScheduleResult

    Raises:
        RealEndpointNotReadyError: real 档位且未显式 opt-in 时由底座抛出，
            此时不返回任何完工日、亦不写审计。
    """
    # ── 取工单。fail-loud 由底座抛出，此处刻意不 try/except ──────────────
    # `plans` 是档 1 的 mock/inline 注入口，`connector` 是档 2 的真实取数口，
    # 二者互斥：同时给会让「这批工单到底哪来的」在审计里说不清，故直接拒绝，
    # 不做「优先用谁」的静默取舍。
    if plans is not None and connector is not None:
        raise ValueError("plans 与 connector 互斥，只能提供其一（前者为 mock 注入，后者为真实取数）")
    if plans is None:
        if connector is None:
            raise ValueError("plans 与 connector 至少提供其一")
        plans = connector.get_production_plan()
        plan_source = "connector"
    else:
        plan_source = "mock"

    if lead_time_map is None:
        lead_time_map = load_smt_lead_time()
        lead_time_placeholder = is_placeholder_lead_time()
        lead_time_source = "CSV_placeholder"
    else:
        # 调用方自带工时表：无从判断其可信度，保守按占位处理
        lead_time_placeholder = True
        lead_time_source = "caller"

    # ── 逐产品推算 ──────────────────────────────────────────────────────
    products = sorted({p.product_id for p in plans})
    scheduled: dict[str, date] = {}
    unschedulable: dict[str, str] = {}

    for product_id in products:
        arrivals = material_arrivals.get(product_id) or {}
        finish = schedule_smt(product_id, arrivals, lead_time_map)
        if finish is not None:
            scheduled[product_id] = finish
        elif product_id not in lead_time_map:
            unschedulable[product_id] = "该产品不在 SMT 工时对照表中（无工时配置）"
        else:
            unschedulable[product_id] = "无任何物料到货记录，无法确定齐料日"

    analyzed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    data_sources = {
        "production_plan": plan_source,
        "material_arrivals": "mock",
        "smt_lead_time": lead_time_source,
    }

    result = ScheduleResult(
        products=products,
        scheduled=scheduled,
        unschedulable=unschedulable,
        lead_time_is_placeholder=lead_time_placeholder,
        analyzed_at=analyzed_at,
        data_sources=data_sources,
    )

    if audit_logger is not None:
        audit_logger.record(AuditEvent(
            scenario="O1",
            action="smt_schedule",
            evaluator="auto",
            automation_level="L1",          # design D3：首版无下发动作，不设空门禁
            decision={
                "products": products,
                "scheduled": {k: v.isoformat() for k, v in scheduled.items()},
                "unschedulable": unschedulable,
                "scheduled_count": len(scheduled),
                "unschedulable_count": len(unschedulable),
                # 🔴 事后追溯「这个完工日当时能不能信」全靠这一条
                "lead_time_is_placeholder": lead_time_placeholder,
                "analyzed_at": analyzed_at,
            },
            data_sources=data_sources,
        ))

    return result
