"""携客云 SRM 连接器测试（第 5 组）。

验证：
  · 看板解析：get_demand_orders / get_delivery_orders 产出正确 shape（SrmDemandOrder/SrmDeliveryOrder）。
  · D2：_post 写轻量访问痕迹（source=SRM）、不再有 SQLite 审计、req/resp 全文不进合规痕迹。
  · 只读 + 全程 mock：无真实网络调用。
"""
import io
import json

import pytest

from zhuopin_platform.audit.sinks import JsonlSink
from zhuopin_platform.shared_tools import models
from zhuopin_platform.shared_tools.connector_audit import ConnectorAudit, DebugLog
from zhuopin_platform.shared_tools.srm_connector import XkySrmConnector
from zhuopin_platform.shared_tools.srm_connector import connector as srm_mod


# 一条携客云 receiveBoard 记录（含一个 item，已被供应商答交）
_CANNED_BOARD = [
    {
        "productCode": "R01B.0039",
        "prodFeature": "电容 10uF",
        "innerVendorCode": "ZA.0317",
        "itemList": [
            {
                "planQty": 1000,
                "answerQty": 1000,
                "deliveriedQty": 0,
                "boardDate": "2026-07-01",
                "scheduleBatch": "SRM-2026-001",
                "poLineList": [{"pdrNo": "PO20260519"}],
            }
        ],
    }
]


def _make_conn(audit=None, debug=None):
    return XkySrmConnector(
        api_base="https://openapi.xiekeyun.com", app_key="k", app_secret="s",
        owner_company_code="ZP", erp_code="ZP", audit=audit, debug=debug,
    )


def test_get_demand_orders_parsing(monkeypatch):
    conn = _make_conn()
    monkeypatch.setattr(conn, "get_receive_board", lambda *a, **k: _CANNED_BOARD)
    demands = conn.get_demand_orders()
    assert len(demands) == 1
    d = demands[0]
    assert isinstance(d, models.SrmDemandOrder)
    assert d.material_id == "R01B.0039"
    assert d.qty_required == 1000
    assert d.customer_order == "PO20260519"
    assert d.status == "ordered"  # answerQty>0, deliver<plan


def test_get_delivery_orders_only_answered(monkeypatch):
    conn = _make_conn()
    monkeypatch.setattr(conn, "get_receive_board", lambda *a, **k: _CANNED_BOARD)
    deliveries = conn.get_delivery_orders()
    assert len(deliveries) == 1
    dv = deliveries[0]
    assert isinstance(dv, models.SrmDeliveryOrder)
    assert dv.supplier_id == "ZA.0317"
    assert dv.qty_committed == 1000
    assert dv.committed_date == "2026-07-01"
    assert dv.status == "confirmed"


def test_signature_is_deterministic():
    conn = _make_conn()
    common = {"appKey": "k", "ownerCompanyCode": "ZP",
              "operateCompanyCode": "ZP", "timestamps": "1700000000"}
    assert conn._sign(dict(common)) == conn._sign(dict(common))


def test_no_sqlite_audit_attributes():
    """D2：剥离 SQLite 审计后，连接器不应再有任何 SQLite 审计成员。"""
    conn = _make_conn()
    for attr in ("_audit_conn", "_audit_db_path", "_init_audit_db", "_write_audit"):
        assert not hasattr(conn, attr), f"SQLite 审计残留：{attr}"


def _fake_urlopen_factory(resp_obj):
    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps(resp_obj).encode("utf-8")
    def _fake(req, timeout=15):
        return _Resp()
    return _fake


def test_post_writes_lightweight_trace_no_full_text(tmp_path, monkeypatch):
    """D2：一次 SRM 查询写一条轻量痕迹（source=SRM），合规痕迹不含 req/resp 全文。"""
    trace_sink = JsonlSink(tmp_path / "access_trace.jsonl")
    conn = _make_conn(audit=ConnectorAudit(sink=trace_sink))
    resp = {"errorCode": "0", "data": {"lineList": [{"vExpectedDate": "1782931200"}]}}
    monkeypatch.setattr(srm_mod.urllib.request, "urlopen", _fake_urlopen_factory(resp))

    conn.get_confirmed_date("PO20260519", "ZA.0317")

    records = trace_sink.read_all()
    assert len(records) == 1
    rec = records[0]
    assert rec["source"] == "SRM"
    assert rec["target"] == "PO20260519"
    # 合规轻量痕迹绝不含 req/resp 全文
    assert "req" not in rec and "resp" not in rec and "vExpectedDate" not in json.dumps(rec)


def test_debug_off_by_default_no_file(tmp_path, monkeypatch):
    conn = _make_conn()  # debug=None → 默认无全文日志
    resp = {"errorCode": "0", "data": {"lineList": [{"vExpectedDate": "1782931200"}]}}
    monkeypatch.setattr(srm_mod.urllib.request, "urlopen", _fake_urlopen_factory(resp))
    conn.get_confirmed_date("PO1", "V1")
    assert not any(p.name.endswith(".debug.log") for p in tmp_path.iterdir())
