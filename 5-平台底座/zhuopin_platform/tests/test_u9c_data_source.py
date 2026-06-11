"""U9C_DATA_SOURCE 开关 + real 模式 fail-loud + 审计按端点标源（u9c-connector-convergence）。

红线（Paul 拍板 Q3）：real 模式无真实端点 → 显式报错，**绝不静默回退 mock**；
CSV 回退仅留 mock 模式；过渡期显式 opt-in 回退须标 CSV_mock + 非权威 + 禁入 L2。
"""
import json
from pathlib import Path

import pytest

from zhuopin_platform.audit.sinks import JsonlSink
from zhuopin_platform.shared_tools.connector_audit import ConnectorAudit
from zhuopin_platform.shared_tools.connector_errors import RealEndpointNotReadyError
from zhuopin_platform.shared_tools.erp_connector import ZpConnector
from zhuopin_platform.shared_tools.erp_connector import connector as erp_mod

FIXTURES = Path(__file__).parent / "fixtures"


def _conn(tmp_path, *, data_source=None, allow_mock_fallback=False, audit=None):
    return ZpConnector(
        base_url="https://mock.zp.test:4445", user_code="u", ent_code="001",
        org_code="Z", client_id="cid", client_secret="csec",
        fallback_dir=FIXTURES, po_cache_file=tmp_path / "po.json",
        audit=audit, data_source=data_source, allow_mock_fallback=allow_mock_fallback,
    )


def test_default_data_source_is_mock(tmp_path, monkeypatch):
    monkeypatch.delenv("U9C_DATA_SOURCE", raising=False)
    conn = _conn(tmp_path)
    assert conn._data_source == "mock"
    plans = conn.get_production_plan()          # mock → CSV 回退
    assert len(plans) > 0


def test_env_switch_to_real(tmp_path, monkeypatch):
    monkeypatch.setenv("U9C_DATA_SOURCE", "real")
    conn = _conn(tmp_path)                       # 不显式传 → 读 env
    assert conn._data_source == "real"


def test_real_mode_no_endpoint_fail_loud(tmp_path, monkeypatch):
    """real 模式无真实端点 → 显式报错，不返回 mock。"""
    monkeypatch.delenv("U9C_ALLOW_MOCK_FALLBACK", raising=False)
    conn = _conn(tmp_path, data_source="real")
    with pytest.raises(RealEndpointNotReadyError):
        conn.get_production_plan()


def test_real_mode_optin_fallback_marks_csv_mock(tmp_path):
    """real 模式显式 opt-in 回退 → CSV 但审计标 CSV_mock + 警告（非权威）。"""
    sink = JsonlSink(tmp_path / "trace.jsonl")
    conn = _conn(tmp_path, data_source="real", allow_mock_fallback=True,
                 audit=ConnectorAudit(sink=sink))
    with pytest.warns(UserWarning):
        plans = conn.get_production_plan()
    assert len(plans) > 0
    records = sink.read_all()
    assert any(r["source"] == "CSV_mock" and r["action"] == "get_production_plan"
               for r in records)


def test_mock_mode_fallback_source_is_plain_csv(tmp_path):
    """mock 模式回退痕迹标 CSV（非 CSV_mock）—— 正常 mock 运行，区别于 real 降级。"""
    sink = JsonlSink(tmp_path / "trace.jsonl")
    conn = _conn(tmp_path, data_source="mock", audit=ConnectorAudit(sink=sink))
    conn.get_production_plan()
    records = sink.read_all()
    assert any(r["source"] == "CSV" and r["action"] == "get_production_plan" for r in records)
    assert not any(r["source"] == "CSV_mock" for r in records)


def test_bom_trace_source_is_u9c_webapi(tmp_path, monkeypatch):
    """Q1：BOM 走 U9C webapi → 审计来源标 U9C_webapi（非 zp_ERP）。"""
    sink = JsonlSink(tmp_path / "trace.jsonl")
    conn = _conn(tmp_path, audit=ConnectorAudit(sink=sink))
    monkeypatch.setattr(conn, "_get_token", lambda: "tok")

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps({"Success": True, "Data": []}).encode("utf-8")
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", lambda *a, **k: _Resp())

    conn.get_bom_for_products(["PROD001"])
    records = sink.read_all()
    assert any(r["source"] == "U9C_webapi" for r in records)
    assert not any(r["source"] == "zp_ERP" for r in records)
