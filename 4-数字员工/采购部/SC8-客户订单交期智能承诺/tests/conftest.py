"""SC8 测试共享夹具（全 mock，无真实网络调用）。

黄金基准样本覆盖三类（门禁文档 §2.1）：
  · 有反馈   F02N.0040（比亚迪）→ 全部子件有 SRM 承诺 → 高置信
  · 无反馈   F02N.0184（理想）  → 含无反馈子件 R02.B → 低置信 + +30 天
  · 含委外   X05A.0001（上汽）  → 料号前缀 X 委外 → 低置信 + +10 天
"""
from __future__ import annotations

import pytest
from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.shared_tools.models import BomRow, SrmDeliveryOrder

from sc8.config import ForecastParams
from sc8.models import SalesOrder
from sc8.pending_queue import FilePendingQueue


def _bom(product_id, component_id):
    return BomRow(
        product_id=product_id, component_id=component_id,
        component_name=component_id, level=1,
        qty_per_unit=1.0, loss_rate=0.0, unit="PCS",
    )


def _delivery(demand_id, material_id, committed_date):
    return SrmDeliveryOrder(
        delivery_id=f"D-{material_id}", demand_id=demand_id,
        supplier_id="ZA.0001", material_id=material_id,
        qty_committed=100, committed_date=committed_date, status="confirmed",
    )


@pytest.fixture
def bom() -> list[BomRow]:
    return [
        _bom("F02N.0040", "R01.A"), _bom("F02N.0040", "R01.B"),
        _bom("F02N.0184", "R02.A"), _bom("F02N.0184", "R02.B"),
        _bom("X05A.0001", "R03.A"),
    ]


@pytest.fixture
def srm_deliveries() -> list[SrmDeliveryOrder]:
    # 注意：F02N.0184 的 R02.B 故意缺失 → 触发无反馈启发式
    return [
        _delivery("SRM-1", "R01.A", "2026-06-20"),
        _delivery("SRM-2", "R01.B", "2026-06-25"),
        _delivery("SRM-3", "R02.A", "2026-06-18"),
        _delivery("SRM-5", "R03.A", "2026-06-30"),
    ]


@pytest.fixture
def lead_time() -> dict[str, int]:
    return {"F02N.0040": 5, "F02N.0184": 7, "X05A.0001": 3}


@pytest.fixture
def params() -> ForecastParams:
    # 显式构造，等同模块默认；测试可单独覆盖验证"改 config 即改行为"
    return ForecastParams(
        param_version="sc8-params-v0",
        no_feedback_lead_days=30, outsource_extra_days=10,
        logistics_days=1, deviation_alert_days=3,
    )


@pytest.fixture
def sales_orders() -> list[SalesOrder]:
    return [
        SalesOrder("SO2026060001", "Z012003", "比亚迪", "F02N.0040", 100, "2026-07-10", item_name="整车控制器"),
        SalesOrder("SO2026060002", "Z012007", "理想",   "F02N.0184", 50,  "2026-07-05", item_name="电机控制器"),
        SalesOrder("SO2026060003", "Z012011", "上汽",   "X05A.0001", 30,  "2026-07-20", item_name="委外组件"),
    ]


@pytest.fixture
def outsource_ids() -> set[str]:
    # Paul 拍板：MVP 过渡口径 = 仅维护清单（料号前缀关闭）。X05A.0001 在委外维护清单中。
    # 真实切换统一走 U9C 工艺路线 IsSubContract（6/12 后）。
    return {"X05A.0001"}


@pytest.fixture
def audit(tmp_path) -> AuditLogger:
    return AuditLogger.jsonl(tmp_path / "audit_log.jsonl")


@pytest.fixture
def queue(tmp_path) -> FilePendingQueue:
    return FilePendingQueue(tmp_path / "pending_approvals.jsonl")
