"""财务三单查询测试（design D15，队列 #60）。

验证 ZpConnector.get_purchase_lines/get_gr_lines/get_ap_lines 走 GET /zp/api/*/Query：
  · 信封同 Stock/Query（Success + Data.Rows），复用 STOCK_API_BASE/STOCK_API_KEY
  · 未配置 → fail-loud（RealEndpointNotReadyError，不静默回退、不返回空当成功）
  · apiKey 脱敏（异常不含明文）；Success=false → 抛错
全程 mock/monkeypatch，不触真实端点。
"""
from pathlib import Path

import pytest

from zhuopin_platform.shared_tools.erp_connector import ZpConnector
from zhuopin_platform.shared_tools.erp_connector import connector as erp_mod
from zhuopin_platform.shared_tools.connector_errors import RealEndpointNotReadyError

FIXTURES = Path(__file__).parent / "fixtures"


def _make_conn(tmp_path):
    return ZpConnector(
        base_url="https://testerp.example:4445", user_code="u", ent_code="001",
        org_code="Z", client_id="cid", client_secret="sec",
        fallback_dir=FIXTURES, po_cache_file=tmp_path / "po_cache.json",
    )


class _Resp:
    def __init__(self, body: bytes):
        self._body = body
        self.status = 200

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.mark.parametrize("method,path", [
    ("get_purchase_lines", "/zp/api/Purchase/Query"),
    ("get_gr_lines", "/zp/api/GR/Query"),
    ("get_ap_lines", "/zp/api/AP/Query"),
])
def test_fi_query_returns_rows(tmp_path, monkeypatch, method, path):
    monkeypatch.setenv("STOCK_API_BASE", "http://192.168.100.49:6666")
    monkeypatch.setenv("STOCK_API_KEY", "K")
    conn = _make_conn(tmp_path)
    body = b'{"ResCode":0,"Success":true,"ResMsg":null,"Data":{"Total":1,"Rows":[{"DocNo":"D1"}]}}'
    captured_url = {}

    def _fake_urlopen(req, timeout=None, context=None):
        captured_url["url"] = req.full_url
        return _Resp(body)
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", _fake_urlopen)

    rows = getattr(conn, method)("D1")
    assert rows == [{"DocNo": "D1"}]
    assert path in captured_url["url"]
    assert "docNo=D1" in captured_url["url"]
    assert "apiKey=K" in captured_url["url"]


def test_fi_query_failloud_without_config(tmp_path, monkeypatch):
    monkeypatch.delenv("STOCK_API_BASE", raising=False)
    monkeypatch.delenv("STOCK_API_KEY", raising=False)
    conn = _make_conn(tmp_path)
    with pytest.raises(RealEndpointNotReadyError):
        conn.get_ap_lines("AP-1")


def test_fi_query_success_false_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_API_BASE", "http://h:6666")
    monkeypatch.setenv("STOCK_API_KEY", "K")
    conn = _make_conn(tmp_path)
    body = b'{"Success":false,"ResMsg":"bad docNo","Data":null}'
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", lambda *a, **k: _Resp(body))
    with pytest.raises(RuntimeError) as ei:
        conn.get_purchase_lines("BOGUS")
    assert "财务查询 API 错误" in str(ei.value)


def test_fi_query_apikey_scrubbed_on_error(tmp_path, monkeypatch):
    import urllib.error
    monkeypatch.setenv("STOCK_API_BASE", "http://h:6666")
    monkeypatch.setenv("STOCK_API_KEY", "SUPERSECRETKEY123")
    conn = _make_conn(tmp_path)

    def _boom(*a, **k):
        raise urllib.error.HTTPError("http://h/zp/api/AP/Query", 500, "err", {}, None)
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", _boom)
    with pytest.raises(RuntimeError) as ei:
        conn.get_ap_lines("AP-1")
    assert "SUPERSECRETKEY123" not in str(ei.value)


def test_fi_query_empty_rows_when_data_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_API_BASE", "http://h:6666")
    monkeypatch.setenv("STOCK_API_KEY", "K")
    conn = _make_conn(tmp_path)
    body = b'{"Success":true,"Data":{"Total":0,"Rows":[]}}'
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", lambda *a, **k: _Resp(body))
    assert conn.get_gr_lines("GHOST") == []
