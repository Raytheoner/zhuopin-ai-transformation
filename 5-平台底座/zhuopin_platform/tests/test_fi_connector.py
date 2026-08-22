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


# ── 采购订单行级关闭状态（队列 #173，#139④ 根治，2026-08-03）─────────────────

def test_get_purchase_line_status_builds_status_map(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_API_BASE", "http://h:6666")
    monkeypatch.setenv("STOCK_API_KEY", "K")
    conn = _make_conn(tmp_path)
    body = json.dumps({"Success": True, "Data": {"Total": 2, "Rows": [
        {"DocNo": "ZPCG1", "DocLineNo": 10, "LineStatus": 2, "ItemCode": "R01D.0006"},
        {"DocNo": "ZPCG2", "DocLineNo": 210, "LineStatus": 4, "ItemCode": "R01D.0006"},
    ]}}).encode()
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", lambda *a, **k: _Resp(body))

    result = conn.get_purchase_line_status(["R01D.0006"])
    assert result == {("ZPCG1", "10"): 2, ("ZPCG2", "210"): 4}


def test_get_purchase_line_status_queries_each_item_code(tmp_path, monkeypatch):
    """服务端每次只接受一个 itemCode 过滤值，多料号逐个查询。"""
    monkeypatch.setenv("STOCK_API_BASE", "http://h:6666")
    monkeypatch.setenv("STOCK_API_KEY", "K")
    conn = _make_conn(tmp_path)
    seen_item_codes = []

    def _fake_urlopen(req, timeout=None, context=None):
        qs = dict(x.split("=") for x in req.full_url.split("?", 1)[1].split("&"))
        code = qs["itemCode"]
        seen_item_codes.append(code)
        row = {"DocNo": f"PO-{code}", "DocLineNo": 10, "LineStatus": 2, "ItemCode": code}
        body = json.dumps({"Success": True, "Data": {"Total": 1, "Rows": [row]}}).encode()
        return _Resp(body)
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", _fake_urlopen)

    result = conn.get_purchase_line_status(["A", "B"])
    assert seen_item_codes == ["A", "B"]
    assert result == {("PO-A", "10"): 2, ("PO-B", "10"): 2}


def test_get_purchase_line_status_skips_rows_missing_key_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_API_BASE", "http://h:6666")
    monkeypatch.setenv("STOCK_API_KEY", "K")
    conn = _make_conn(tmp_path)
    body = json.dumps({"Success": True, "Data": {"Total": 2, "Rows": [
        {"DocNo": "", "DocLineNo": 10, "LineStatus": 2},          # 缺 DocNo
        {"DocNo": "ZPCG1", "DocLineNo": 10, "LineStatus": None},  # 缺 LineStatus
    ]}}).encode()
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", lambda *a, **k: _Resp(body))
    assert conn.get_purchase_line_status(["A"]) == {}


def test_get_purchase_line_status_empty_item_codes_returns_empty(tmp_path):
    conn = _make_conn(tmp_path)
    assert conn.get_purchase_line_status([]) == {}


# ── 采购订单行级明细：确认数量 ConfirmQty（SC2 判例回灌，2026-08-22）─────────

def test_get_purchase_line_details_exposes_confirm_qty(tmp_path, monkeypatch):
    """🔴 「确认数量」是采购口径下的**采购订单量**，只有这个端点给得出。

    姚祖怡 2026-08-21 判例批改回件：「ERP 标准采购中的采购订单量只取确认数量那一栏，
    这是采购最终下单给供应商的数量，也是收货数量的依据，其余数据不用考虑。」
    真实反例 ZPCG20260409002 行 10：`ZpViewPurOrder.qty=3000`，而 ConfirmQty=200。
    """
    monkeypatch.setenv("STOCK_API_BASE", "http://h:6666")
    monkeypatch.setenv("STOCK_API_KEY", "K")
    conn = _make_conn(tmp_path)
    body = json.dumps({"Success": True, "Data": {"Total": 1, "Rows": [
        {"DocNo": "ZPCG20260409002", "DocLineNo": 10, "LineStatus": 3,
         "ItemCode": "R01I.0846", "ConfirmQty": 200.0,
         "FinalPriceTC": 19.15, "TotalMnyTC": 3830.0},
    ]}}).encode()
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", lambda *a, **k: _Resp(body))

    detail = conn.get_purchase_line_details(["R01I.0846"])[("ZPCG20260409002", "10")]
    assert detail["confirm_qty"] == 200.0
    assert detail["line_status"] == 3
    assert detail["total_amount"] == 3830.0


def test_get_purchase_line_details_keeps_missing_confirm_qty_as_none(tmp_path, monkeypatch):
    """缺失**不折成 0.0**：0 会被下游当成「订了 0 个」正常求和，而真相是没取到。"""
    monkeypatch.setenv("STOCK_API_BASE", "http://h:6666")
    monkeypatch.setenv("STOCK_API_KEY", "K")
    conn = _make_conn(tmp_path)
    body = json.dumps({"Success": True, "Data": {"Total": 1, "Rows": [
        {"DocNo": "ZPCG1", "DocLineNo": 10, "LineStatus": 2},
    ]}}).encode()
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", lambda *a, **k: _Resp(body))
    assert conn.get_purchase_line_details(["A"])[("ZPCG1", "10")]["confirm_qty"] is None


def test_get_purchase_line_status_unchanged_after_refactor(tmp_path, monkeypatch):
    """`get_purchase_line_status` 改成了明细方法的薄封装 —— **返回值必须逐字不变**。

    SC8 等既有调用方依赖它；本次重构对它们必须是零感知的。缺 LineStatus 的行
    仍然被剔除（不得因为改成了取明细就悄悄多返回一个 None）。
    """
    monkeypatch.setenv("STOCK_API_BASE", "http://h:6666")
    monkeypatch.setenv("STOCK_API_KEY", "K")
    conn = _make_conn(tmp_path)
    body = json.dumps({"Success": True, "Data": {"Total": 2, "Rows": [
        {"DocNo": "ZPCG1", "DocLineNo": 10, "LineStatus": 2, "ConfirmQty": 5.0},
        {"DocNo": "ZPCG2", "DocLineNo": 20, "LineStatus": None, "ConfirmQty": 7.0},
    ]}}).encode()
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", lambda *a, **k: _Resp(body))
    assert conn.get_purchase_line_status(["A"]) == {("ZPCG1", "10"): 2}


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


# ── get_ap_lines_by_invoice_no（队列 #295，FI2 税务导出 Excel 接入追加）───────

def test_get_ap_lines_by_invoice_no_paginates(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_API_BASE", "http://h:6666")
    monkeypatch.setenv("STOCK_API_KEY", "K")
    conn = _make_conn(tmp_path)
    body = json.dumps({"Success": True, "Data": {"Total": 2, "Rows": [
        {"DocNo": "AP-1", "InvoiceNo": "42719331"},
        {"DocNo": "AP-1", "InvoiceNo": "42719331"},
    ]}}).encode()
    captured = {}

    def _fake_urlopen(req, timeout=None, context=None):
        captured["url"] = req.full_url
        return _Resp(body)
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", _fake_urlopen)

    rows = conn.get_ap_lines_by_invoice_no("42719331")
    assert [r["DocNo"] for r in rows] == ["AP-1", "AP-1"]
    assert "invoiceNo=42719331" in captured["url"]
    assert "docNo=" not in captured["url"]


def test_get_ap_lines_by_invoice_no_empty_result(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_API_BASE", "http://h:6666")
    monkeypatch.setenv("STOCK_API_KEY", "K")
    conn = _make_conn(tmp_path)
    body = json.dumps({"Success": True, "Data": {"Total": 0, "Rows": []}}).encode()
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", lambda *a, **k: _Resp(body))
    assert conn.get_ap_lines_by_invoice_no("00000000") == []


def test_get_ap_lines_by_invoice_no_failloud_without_config(tmp_path, monkeypatch):
    monkeypatch.delenv("STOCK_API_BASE", raising=False)
    monkeypatch.delenv("STOCK_API_KEY", raising=False)
    conn = _make_conn(tmp_path)
    with pytest.raises(RealEndpointNotReadyError):
        conn.get_ap_lines_by_invoice_no("42719331")


# ── 传输层瞬时失败重试（2026-08-22 实测：端点会随机 TLS 断连）────────────────

def test_fi_request_retries_transport_error(tmp_path, monkeypatch):
    """🔴 端点会随机 `SSL: UNEXPECTED_EOF_WHILE_READING` 断连，重打一次就成功。

    按料号逐个查一次周报要打 589 次；**单次 5% 的失败率在 589 次串行调用下几乎
    必然命中**，整份周报因此永远出不来。故传输层瞬时失败必须重试。
    """
    monkeypatch.setenv("STOCK_API_BASE", "http://h:6666")
    monkeypatch.setenv("STOCK_API_KEY", "K")
    monkeypatch.setattr(erp_mod.time, "sleep", lambda *_: None)
    conn = _make_conn(tmp_path)
    calls = {"n": 0}
    ok = json.dumps({"Success": True, "Data": {"Total": 0, "Rows": []}}).encode()

    def _flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise erp_mod.urllib.error.URLError("SSL: UNEXPECTED_EOF_WHILE_READING")
        return _Resp(ok)
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", _flaky)

    assert conn.get_purchase_line_details(["A"]) == {}
    assert calls["n"] == 2, "第一次断连后应当重试"


def test_fi_request_still_fails_loud_after_retries(tmp_path, monkeypatch):
    """重试用尽仍原样失败——**不降级、不返回空集冒充"该窗口没数据"**。"""
    monkeypatch.setenv("STOCK_API_BASE", "http://h:6666")
    monkeypatch.setenv("STOCK_API_KEY", "K")
    monkeypatch.setattr(erp_mod.time, "sleep", lambda *_: None)
    conn = _make_conn(tmp_path)

    def _always_down(*a, **k):
        raise erp_mod.urllib.error.URLError("down")
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", _always_down)

    with pytest.raises(RuntimeError, match="已重试"):
        conn.get_purchase_line_details(["A"])


def test_fi_request_does_not_retry_http_error(tmp_path, monkeypatch):
    """HTTP 错误重试多少次结果都一样，重试只会掩盖问题——一次即上抛。"""
    monkeypatch.setenv("STOCK_API_BASE", "http://h:6666")
    monkeypatch.setenv("STOCK_API_KEY", "K")
    conn = _make_conn(tmp_path)
    calls = {"n": 0}

    def _http_500(*a, **k):
        calls["n"] += 1
        raise erp_mod.urllib.error.HTTPError("u", 500, "boom", {}, None)
    monkeypatch.setattr(erp_mod.urllib.request, "urlopen", _http_500)

    with pytest.raises(RuntimeError, match="HTTP 500"):
        conn.get_purchase_line_details(["A"])
    assert calls["n"] == 1
