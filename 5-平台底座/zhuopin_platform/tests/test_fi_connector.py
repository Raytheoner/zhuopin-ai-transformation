"""财务三单查询测试（design D15，队列 #60）。

验证 ZpConnector.get_purchase_lines/get_gr_lines/get_ap_lines 走 GET /zp/api/*/Query：
  · 信封同 Stock/Query（Success + Data.Rows），复用 STOCK_API_BASE/STOCK_API_KEY
  · 未配置 → fail-loud（RealEndpointNotReadyError，不静默回退、不返回空当成功）
  · apiKey 脱敏（异常不含明文）；Success=false → 抛错
全程 mock/monkeypatch，不触真实端点。
"""
import json
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


# ── 批量取数（design D16，队列 #61 追加：supplierCode 过滤 2026-07-21 起可用）──

def test_get_ap_lines_by_supplier_paginates_until_exhausted(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_API_BASE", "http://h:6666")
    monkeypatch.setenv("STOCK_API_KEY", "K")
    conn = _make_conn(tmp_path)
    conn._FI_PAGE_SIZE = 2   # 小页方便测试跨页

    pages = {
        1: [{"DocNo": "AP-1"}, {"DocNo": "AP-2"}],
        2: [{"DocNo": "AP-3"}, {"DocNo": "AP-4"}],
        3: [{"DocNo": "AP-5"}],
    }
    seen_pages = []

    def _fake_urlopen(req, timeout=None, context=None):
        qs = dict(x.split("=") for x in req.full_url.split("?", 1)[1].split("&"))
        page = int(qs["page"])
        seen_pages.append(page)
        rows = pages.get(page, [])
        body = json.dumps({"Success": True, "Data": {"Total": 5, "Rows": rows}}).encode()
        return _Resp(body)
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", _fake_urlopen)

    rows = conn.get_ap_lines_by_supplier("ZA0066")
    assert [r["DocNo"] for r in rows] == ["AP-1", "AP-2", "AP-3", "AP-4", "AP-5"]
    assert seen_pages == [1, 2, 3]   # 拉到 Total 就停，不多拉一页


def test_get_ap_lines_by_supplier_empty_result(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_API_BASE", "http://h:6666")
    monkeypatch.setenv("STOCK_API_KEY", "K")
    conn = _make_conn(tmp_path)
    body = json.dumps({"Success": True, "Data": {"Total": 0, "Rows": []}}).encode()
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", lambda *a, **k: _Resp(body))
    assert conn.get_ap_lines_by_supplier("ZA9999") == []


def test_get_ap_lines_by_supplier_url_contains_filter_no_docno(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_API_BASE", "http://h:6666")
    monkeypatch.setenv("STOCK_API_KEY", "K")
    conn = _make_conn(tmp_path)
    captured = {}

    def _fake_urlopen(req, timeout=None, context=None):
        captured["url"] = req.full_url
        body = json.dumps({"Success": True, "Data": {"Total": 0, "Rows": []}}).encode()
        return _Resp(body)
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", _fake_urlopen)

    conn.get_ap_lines_by_supplier("ZA0066")
    assert "supplierCode=ZA0066" in captured["url"]
    assert "docNo" not in captured["url"]
    assert "page=1" in captured["url"] and "pageSize=" in captured["url"]


# ── 期间/余额窄化参数（design D17，队列 #70 追加，2026-07-22）──────────────

def test_get_ap_lines_by_supplier_period_params_in_url(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_API_BASE", "http://h:6666")
    monkeypatch.setenv("STOCK_API_KEY", "K")
    conn = _make_conn(tmp_path)
    captured = {}

    def _fake_urlopen(req, timeout=None, context=None):
        captured["url"] = req.full_url
        body = json.dumps({"Success": True, "Data": {"Total": 0, "Rows": []}}).encode()
        return _Resp(body)
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", _fake_urlopen)

    conn.get_ap_lines_by_supplier(
        "ZA0066", date_from="2026-01-01", date_to="2026-07-22", min_balance=1000
    )
    assert "supplierCode=ZA0066" in captured["url"]
    assert "dateFrom=2026-01-01" in captured["url"]
    assert "dateTo=2026-07-22" in captured["url"]
    assert "minBalance=1000" in captured["url"]


def test_get_ap_lines_by_supplier_period_params_default_omitted(tmp_path, monkeypatch):
    """不传 date_from/date_to/min_balance 时，URL 与 D16 原行为完全一致（向后兼容）。"""
    monkeypatch.setenv("STOCK_API_BASE", "http://h:6666")
    monkeypatch.setenv("STOCK_API_KEY", "K")
    conn = _make_conn(tmp_path)
    captured = {}

    def _fake_urlopen(req, timeout=None, context=None):
        captured["url"] = req.full_url
        body = json.dumps({"Success": True, "Data": {"Total": 0, "Rows": []}}).encode()
        return _Resp(body)
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", _fake_urlopen)

    conn.get_ap_lines_by_supplier("ZA0066")
    for absent in ("dateFrom", "dateTo", "minBalance"):
        assert absent not in captured["url"]


def test_get_ap_lines_by_supplier_partial_period_params(tmp_path, monkeypatch):
    """只传 date_from（不传 date_to/min_balance）——三者互相独立，不强制同进同出。"""
    monkeypatch.setenv("STOCK_API_BASE", "http://h:6666")
    monkeypatch.setenv("STOCK_API_KEY", "K")
    conn = _make_conn(tmp_path)
    captured = {}

    def _fake_urlopen(req, timeout=None, context=None):
        captured["url"] = req.full_url
        body = json.dumps({"Success": True, "Data": {"Total": 0, "Rows": []}}).encode()
        return _Resp(body)
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", _fake_urlopen)

    conn.get_ap_lines_by_supplier("ZA0066", date_from="2026-01-01")
    assert "dateFrom=2026-01-01" in captured["url"]
    assert "dateTo" not in captured["url"]
    assert "minBalance" not in captured["url"]


# ── 附件（发票扫描件，design D18，队列 #78 追加，2026-07-23）─────────────────

def test_list_attachments_returns_data_array(tmp_path, monkeypatch):
    """List 信封与其余财务端点不同：Data 直接是数组（无 Rows 包裹），真实探测确认。"""
    monkeypatch.setenv("STOCK_API_BASE", "http://h:6666")
    monkeypatch.setenv("STOCK_API_KEY", "K")
    conn = _make_conn(tmp_path)
    captured = {}
    body = json.dumps({
        "ResCode": 0, "Success": True, "ResMsg": None,
        "Data": [{"ID": 1002607060006241, "Title": "26327000000742719331.pdf", "Size": "63KB"}],
    }).encode()

    def _fake_urlopen(req, timeout=None, context=None):
        captured["url"] = req.full_url
        return _Resp(body)
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", _fake_urlopen)

    rows = conn.list_attachments("AP-2026070036", "AP")
    assert rows == [{"ID": 1002607060006241, "Title": "26327000000742719331.pdf", "Size": "63KB"}]
    assert "/zp/api/Attachment/List" in captured["url"]
    assert "docNo=AP-2026070036" in captured["url"]
    assert "docType=AP" in captured["url"]


def test_list_attachments_empty_when_data_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_API_BASE", "http://h:6666")
    monkeypatch.setenv("STOCK_API_KEY", "K")
    conn = _make_conn(tmp_path)
    body = json.dumps({"Success": True, "Data": None}).encode()
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", lambda *a, **k: _Resp(body))
    assert conn.list_attachments("AP-GHOST", "AP") == []


def test_list_attachments_failloud_without_config(tmp_path, monkeypatch):
    monkeypatch.delenv("STOCK_API_BASE", raising=False)
    monkeypatch.delenv("STOCK_API_KEY", raising=False)
    conn = _make_conn(tmp_path)
    with pytest.raises(RealEndpointNotReadyError):
        conn.list_attachments("AP-1", "AP")


def test_download_attachment_returns_raw_bytes(tmp_path, monkeypatch):
    """Download 直接返回原始二进制（非 JSON 信封），真实探测确认（application/pdf）。"""
    monkeypatch.setenv("STOCK_API_BASE", "http://h:6666")
    monkeypatch.setenv("STOCK_API_KEY", "K")
    conn = _make_conn(tmp_path)
    pdf_bytes = b"%PDF-1.5\r\n...fake pdf bytes..."
    captured = {}

    def _fake_urlopen(req, timeout=None, context=None):
        captured["url"] = req.full_url
        return _Resp(pdf_bytes)
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", _fake_urlopen)

    content = conn.download_attachment("AP-2026070036", "AP")
    assert content == pdf_bytes
    assert "/zp/api/Attachment/Download" in captured["url"]
    assert "docNo=AP-2026070036" in captured["url"]
    assert "docType=AP" in captured["url"]
    assert "apiKey=K" in captured["url"]


def test_download_attachment_failloud_without_config(tmp_path, monkeypatch):
    monkeypatch.delenv("STOCK_API_BASE", raising=False)
    monkeypatch.delenv("STOCK_API_KEY", raising=False)
    conn = _make_conn(tmp_path)
    with pytest.raises(RealEndpointNotReadyError):
        conn.download_attachment("AP-1", "AP")


def test_download_attachment_empty_content_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_API_BASE", "http://h:6666")
    monkeypatch.setenv("STOCK_API_KEY", "K")
    conn = _make_conn(tmp_path)
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", lambda *a, **k: _Resp(b""))
    with pytest.raises(RuntimeError, match="返回空内容"):
        conn.download_attachment("AP-1", "AP")


def test_download_attachment_apikey_scrubbed_on_error(tmp_path, monkeypatch):
    import urllib.error
    monkeypatch.setenv("STOCK_API_BASE", "http://h:6666")
    monkeypatch.setenv("STOCK_API_KEY", "SUPERSECRETKEY123")
    conn = _make_conn(tmp_path)

    def _boom(*a, **k):
        raise urllib.error.HTTPError("http://h/zp/api/Attachment/Download", 500, "err", {}, None)
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", _boom)
    with pytest.raises(RuntimeError) as ei:
        conn.download_attachment("AP-1", "AP")
    assert "SUPERSECRETKEY123" not in str(ei.value)
