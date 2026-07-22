"""真实数据集成测试（design D15，队列 #60/#61）。

默认跳过：仅当显式置 FI2_RUN_REAL=1 且 STOCK_API_BASE/STOCK_API_KEY 凭据就位时运行
（凭据从平台 `.env` 注入，与库存/预测订单同一份，Paul 2026-07-20 确认复用）。
CI / 普通 pytest 不触网；本地小样本真实验证时手动开启。

docNo 均为 2026-07-20 真实只读探测时验证过的历史真实单据（历史记录不会消失，长期有效）。

2026-07-21（队列 #61 复验）：陈承定位根因——新版本 DLL 把 apiKey 从硬编码改读服务器
Web.config 的 `ZP_API_KEY`，部署时该配置项遗漏导致全端点 401；已补配置 + iisreset 修复。
本次复验：①本文件四个 schema 测试全绿（apiKey 恢复）；②`test_real_ap_query_batch_filter_now_fixed`
额外发现 `AP/Query` 的批量过滤 bug（队列 #60/#61 报给 IT 的那个）同批也被修复了。
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


def _raw_ap_query(**params):
    import json
    import urllib.parse
    import urllib.request

    base = os.environ.get("STOCK_API_BASE", "").rstrip("/")
    key = os.environ.get("STOCK_API_KEY", "")
    qs = urllib.parse.urlencode({"apiKey": key, **params})
    url = f"{base}/zp/api/AP/Query?{qs}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def test_real_ap_query_batch_filter_now_fixed():
    """design D15-a①/队列 #61 复验（2026-07-21，陈承新版本 DLL 部署后）：`AP/Query` 的
    `supplierCode`/`itemCode`/`invoiceNo` 过滤 + 不传 `docNo` 的全表分页，均已从服务器端
    SQL 列名错误恢复为正常返回——此前登记的"AP 端只能 docNo 单查"限制已解除。

    这是原始接口层面的探测（裸 urllib），下面 `test_real_get_ap_lines_by_supplier`
    走连接器封装的生产代码路径，是同一发现在 design D16 落地后的端到端复验。
    """
    by_supplier = _raw_ap_query(supplierCode="ZA0066")
    assert by_supplier.get("Success") is True
    assert by_supplier["Data"]["Total"] > 0

    by_item = _raw_ap_query(itemCode="R01A.0175")
    assert by_item.get("Success") is True
    assert by_item["Data"]["Total"] > 0

    by_invoice = _raw_ap_query(invoiceNo="26942000000425333446")
    assert by_invoice.get("Success") is True
    assert by_invoice["Data"]["Total"] > 0

    full_table = _raw_ap_query(page=1, pageSize=3)
    assert full_table.get("Success") is True
    assert full_table["Data"]["Total"] > 1000   # 全库 AP 单据量级


def test_real_get_ap_lines_by_supplier():
    """design D16（队列 #61 追加）：连接器批量取数方法端到端真实验证——分页拉取
    ZA0066（艾睿，R7 三家外币供应商之一）名下全部 AP 明细行，条数应与直接探测的
    `Total` 一致（分页逻辑无遗漏/无重复），且行行确实属于该供应商。
    """
    conn = _connector()
    expected_total = _raw_ap_query(supplierCode="ZA0066")["Data"]["Total"]
    rows = conn.get_ap_lines_by_supplier("ZA0066")
    assert len(rows) == expected_total
    assert all(r["SupplierCode"] == "ZA0066" for r in rows)


def test_real_ap_query_period_and_balance_params():
    """design D17（队列 #70，2026-07-22）：陈承 07-21 群回复——`AP/Query` 新增
    `dateFrom`/`dateTo`（按立账日期 `AccrueDate` 筛选）+ `minBalance`（按余额下限）
    参数，此前 #60/D15-a① 记录的"按期间批量拉单无参数、供应商是唯一可用维度"
    结论已过时。本用例真实验证三点：①两个新参数单独可用；②与既有 `supplierCode`
    组合可用；③`minBalance` 语义确为"下限"（阈值升高时命中总数单调不增，且
    返回行 Balance 均 ≥ 阈值），避免误当"上限"或"精确匹配"接反语义。
    """
    date_from, date_to = "2026-01-01", "2026-07-22"

    by_date = _raw_ap_query(dateFrom=date_from, dateTo=date_to, page=1, pageSize=5)
    assert by_date.get("Success") is True
    assert by_date["Data"]["Total"] > 0
    for row in by_date["Data"]["Rows"]:
        assert date_from <= row["AccrueDate"][:10] <= date_to

    combined = _raw_ap_query(
        supplierCode="ZA0066", dateFrom=date_from, dateTo=date_to, page=1, pageSize=200
    )
    assert combined.get("Success") is True
    assert all(r["SupplierCode"] == "ZA0066" for r in combined["Data"]["Rows"])

    low = _raw_ap_query(minBalance="0", page=1, pageSize=3)
    high = _raw_ap_query(minBalance="100000", page=1, pageSize=3)
    assert high["Data"]["Total"] < low["Data"]["Total"]        # 阈值升高，命中数单调不增
    assert all(r["Balance"] >= 100000 for r in high["Data"]["Rows"])   # 下限语义，非精确匹配/上限


def test_real_get_ap_lines_by_supplier_with_period_params():
    """design D17：连接器封装层端到端验证——`get_ap_lines_by_supplier` 新增的可选
    `date_from`/`date_to`/`min_balance` 窄化条件在真实服务器上生效，返回条数与
    裸探测一致（分页逻辑对新增 filters 同样无遗漏/无重复）。"""
    conn = _connector()
    date_from, date_to = "2026-01-01", "2026-07-22"
    expected_total = _raw_ap_query(
        supplierCode="ZA0066", dateFrom=date_from, dateTo=date_to
    )["Data"]["Total"]
    rows = conn.get_ap_lines_by_supplier(
        "ZA0066", date_from=date_from, date_to=date_to
    )
    assert len(rows) == expected_total
    assert all(r["SupplierCode"] == "ZA0066" for r in rows)
