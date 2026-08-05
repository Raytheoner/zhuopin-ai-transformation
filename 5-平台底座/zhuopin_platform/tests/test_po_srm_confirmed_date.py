"""get_purchase_orders 真实 SRM 确认日期查询（A1 扩展，shortage-baoguan-criteria-v3，
2026-07-10 会议定稿方案B）。

现状 supplier_confirmed_date 是 expected_date 的硬编码占位，不是真实数据。
本测试覆盖：注入 srm_connector 后按 (po_id, supplier_id) 查真实确认日期覆盖占位值；
查不到/未注入/查询失败时退回现状行为，均 mock，不触网。

队列 #208 修复（2026-08-05）：makeDate/交期一律改用相对"当前时刻"计算，
不再写死绝对日期——get_purchase_orders(days=60) 按 makeDate 相对当天做滚动窗口
过滤，写死的历史日期会在约 60 天后滑出窗口，使本文件在无任何代码改动的情况下
自行"回归失败"（真实实例：makeDate 写死 2026-06-01，2026-08-01 起窗口滑出、
5 个用例全部失败，经 triage 排除代码回归/测试污染，冻结时间复现证实纯属日历
漂移）。改相对日期后本文件不再随时间推移自行过期。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from zhuopin_platform.shared_tools.erp_connector.connector import ZpConnector

_NOW = datetime.now()


def _days_ago(n: int) -> str:
    """返回相对当前时刻 n 天前的日期字符串，保证 makeDate 恒在默认 60 天窗口内。"""
    return (_NOW - timedelta(days=n)).strftime("%Y-%m-%d")


def _days_ahead(n: int) -> str:
    """返回相对当前时刻 n 天后的日期字符串，用于交期/确认日期等展示性字段。"""
    return (_NOW + timedelta(days=n)).strftime("%Y-%m-%d")


def _make_zp(tmp_path: Path, srm_connector=None) -> ZpConnector:
    return ZpConnector(
        base_url="https://mock.zp.test:4445", user_code="u", ent_code="001",
        org_code="Z", client_id="cid", client_secret="csec",
        fallback_dir=tmp_path, po_cache_file=tmp_path / "po.json",
        srm_connector=srm_connector,
    )


def _row(po_id: str, item_code: str, supplier: str, delivery: str) -> dict:
    return {
        "erpNo": po_id, "itemCode": item_code, "qty": 100, "rcvQtyTU": 0,
        "makeDate": _days_ago(10), "deliveryDate": delivery, "supplyCode": supplier,
    }


class _FakeSrmConn:
    def __init__(self, confirmed: dict[str, str], raise_error: bool = False):
        self._confirmed = confirmed
        self._raise = raise_error
        self.calls: list = []

    def get_confirmed_dates(self, pairs):
        self.calls.append(list(pairs))
        if self._raise:
            raise RuntimeError("SRM 查询失败（模拟）")
        out = {po: d for po, _v in pairs if po in self._confirmed for d in [self._confirmed[po]]}
        return out, []


def test_no_srm_connector_behaves_as_before(tmp_path):
    """未注入 srm_connector（默认 None）→ supplier_confirmed_date 仍等于 expected_date（现状不变）。"""
    zp = _make_zp(tmp_path, srm_connector=None)
    delivery = _days_ahead(15)
    rows = [_row("PO1", "M1", "V1", delivery)]
    with patch.object(zp, "_zp_post", return_value=rows):
        result = zp.get_purchase_orders()
    assert result[0].supplier_confirmed_date == result[0].expected_date == delivery


def test_srm_confirmed_date_overrides_placeholder(tmp_path):
    """SRM 查到真实确认日期 → 覆盖占位值，且与 expected_date 不同。"""
    delivery = _days_ahead(15)
    confirmed = _days_ahead(25)
    fake = _FakeSrmConn({"PO1": confirmed})
    zp = _make_zp(tmp_path, srm_connector=fake)
    rows = [_row("PO1", "M1", "V1", delivery)]
    with patch.object(zp, "_zp_post", return_value=rows):
        result = zp.get_purchase_orders()
    assert result[0].expected_date == delivery
    assert result[0].supplier_confirmed_date == confirmed
    assert fake.calls == [[("PO1", "V1")]]


def test_srm_no_match_falls_back_to_expected_date(tmp_path):
    """SRM 查不到该 PO 的确认记录 → 退回 expected_date。"""
    delivery = _days_ahead(15)
    fake = _FakeSrmConn({})  # 空确认表
    zp = _make_zp(tmp_path, srm_connector=fake)
    rows = [_row("PO1", "M1", "V1", delivery)]
    with patch.object(zp, "_zp_post", return_value=rows):
        result = zp.get_purchase_orders()
    assert result[0].supplier_confirmed_date == delivery


def test_srm_query_failure_does_not_break_po_fetch(tmp_path):
    """SRM 查询异常 → 不阻断整体 PO 取数，退回 expected_date。"""
    delivery = _days_ahead(15)
    fake = _FakeSrmConn({}, raise_error=True)
    zp = _make_zp(tmp_path, srm_connector=fake)
    rows = [_row("PO1", "M1", "V1", delivery)]
    with patch.object(zp, "_zp_post", return_value=rows):
        result = zp.get_purchase_orders()  # 不应抛异常
    assert len(result) == 1
    assert result[0].supplier_confirmed_date == delivery


def test_multiple_pos_partial_srm_match(tmp_path):
    """多张 PO，部分有 SRM 确认、部分没有——各自独立处理。"""
    delivery1, delivery2 = _days_ahead(15), _days_ahead(20)
    confirmed1 = _days_ahead(25)
    fake = _FakeSrmConn({"PO1": confirmed1})
    zp = _make_zp(tmp_path, srm_connector=fake)
    rows = [_row("PO1", "M1", "V1", delivery1), _row("PO2", "M2", "V2", delivery2)]
    with patch.object(zp, "_zp_post", return_value=rows):
        result = zp.get_purchase_orders()
    by_id = {r.po_id: r for r in result}
    assert by_id["PO1"].supplier_confirmed_date == confirmed1
    assert by_id["PO2"].supplier_confirmed_date == delivery2  # 退回 expected_date
