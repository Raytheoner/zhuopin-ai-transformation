"""真实数据集成测试（design D15，队列 #60）。

默认跳过：仅当显式置 FI2_RUN_REAL=1 且 STOCK_API_BASE/STOCK_API_KEY 凭据就位时运行
（凭据从平台 `.env` 注入，与库存/预测订单同一份，Paul 2026-07-20 确认复用）。
CI / 普通 pytest 不触网；本地小样本真实验证时手动开启。

docNo 均为 2026-07-20 真实只读探测时验证过的历史真实单据（历史记录不会消失，长期有效）。
"""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("FI2_RUN_REAL") != "1",
    reason="真实集成测试：置 FI2_RUN_REAL=1 且 STOCK_API_BASE/STOCK_API_KEY 就位才运行",
)


def _connector():
    from zhuopin_platform.shared_tools.erp_connector import ZpConnector
    return ZpConnector(
        base_url="https://unused-in-this-test:0", user_code="u", ent_code="e",
        org_code="o", client_id="c", client_secret="s",
    )


def test_real_purchase_query_schema():
    conn = _connector()
    rows = conn.get_purchase_lines("ZPCG20251226004")
    assert rows, "应拉到真实 PO 明细行"
    for r in rows:
        assert r["DocNo"] and r["ItemCode"]
        assert r["ConfirmQty"] > 0


def test_real_ap_query_schema_and_tax_inclusive_price():
    """交叉验证 design D15-a②：AP TaxPrice 与其 SrcPONo/SrcPOLineNo 对应的 PO
    FinalPriceTC 一致（均为含税单价，R7 比对基准可直接用）。"""
    conn = _connector()
    ap_rows = conn.get_ap_lines("AP-2026030057")
    assert ap_rows, "应拉到真实 AP 明细行"
    first = ap_rows[0]
    assert round(first["APQtyTU"] * first["TaxPrice"], 2) == round(first["TotalAmtTC"], 2)

    po_rows = conn.get_purchase_lines(first["SrcPONo"])
    po_line = next(r for r in po_rows if str(r["DocLineNo"]) == str(first["SrcPOLineNo"]))
    assert po_line["FinalPriceTC"] == first["TaxPrice"]


def test_real_gr_query_schema():
    conn = _connector()
    rows = conn.get_gr_lines("RCV2607010095")
    assert rows, "应拉到真实收货单明细行"
    for r in rows:
        assert r["RcvDocNo"] and r["ItemCode"]


def test_real_ap_query_batch_filter_still_broken():
    """design D15-a① IT 缺口回归哨兵：`AP/Query` 的 `supplierCode` 过滤服务器端 SQL bug
    一旦被 IT 修复，本测试应转为失败——提醒回头把 `_fi_query` 的 docNo-only 限制放开、
    更新连接器与 feed_source 的批量取数方式。"""
    import urllib.error
    import urllib.parse
    import urllib.request

    base = os.environ.get("STOCK_API_BASE", "").rstrip("/")
    key = os.environ.get("STOCK_API_KEY", "")
    qs = urllib.parse.urlencode({"apiKey": key, "supplierCode": "ZA0066"})
    url = f"{base}/zp/api/AP/Query?{qs}"
    with urllib.request.urlopen(url, timeout=30) as r:
        import json
        body = json.loads(r.read().decode("utf-8"))
    assert body.get("Success") is not True, (
        "AP/Query supplierCode 过滤看起来已被 IT 修复！"
        "请更新 design D15-a①/tasks.md 11.9 状态，并评估接回批量取数路径。"
    )
