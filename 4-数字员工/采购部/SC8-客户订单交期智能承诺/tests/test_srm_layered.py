"""SRM 分层取数（Task 1 / SOP §4.6）—— 全 mock 假连接器，不触网。

验证合并优先级：① /purchase/answer 权威 > ② 看板 boardDate > ③ 无（走无反馈启发式）。
真实看板字段口径：record{innerVendorCode, productCode, itemList[]{boardDate,
poLineList[]{poErpNo}}}（PO 字段 = poErpNo）。
"""
from __future__ import annotations

from sc8.sources import _extract_board_po_map, load_srm_deliveries


def _rec(material, vendor, board_date, pos, *, cancel_flag=None):
    """构造一条看板记录（pos = [poErpNo,...]）。"""
    return {
        "productCode": material,
        "innerVendorCode": vendor,
        "itemList": [{
            "boardDate": board_date,
            "cancelFlag": cancel_flag,
            "poLineList": [{"poErpNo": p} for p in pos],
        }],
    }


class _FakeConnector:
    """假 SRM 连接器：可控看板 + /purchase/answer 返回。"""

    def __init__(self, board, confirmed):
        self._board = board
        self._confirmed = confirmed          # {poErpNo: vExpectedDate}
        self.answer_calls = []

    def get_receive_board(self, start=None, end=None):
        return self._board

    def get_confirmed_dates(self, pairs):
        self.answer_calls.append(list(pairs))
        out = {po: self._confirmed[po] for (po, _v) in pairs if po in self._confirmed}
        failed = []
        return out, failed


def test_mode_mock_returns_empty():
    assert load_srm_deliveries("mock") == []


def test_extract_board_uses_poErpNo_not_pdrNo():
    board = [_rec("R01.A", "ZB0022", "2026-07-01", ["ZPCG001"])]
    pairs, board_dates = _extract_board_po_map(board, materials=None)
    assert pairs["R01.A"] == {("ZPCG001", "ZB0022")}
    assert board_dates["R01.A"] == "2026-07-01"


def test_answer_takes_priority_over_board():
    # R01.A 有 PO 且 /purchase/answer 有权威交期 → 用权威(更晚的真实承诺)，不用看板日
    board = [_rec("R01.A", "ZB0022", "2026-07-01", ["ZPCG001"])]
    conn = _FakeConnector(board, confirmed={"ZPCG001": "2026-11-30"})
    out = load_srm_deliveries("real", connector=conn)
    assert len(out) == 1
    assert out[0].material_id == "R01.A"
    assert out[0].committed_date == "2026-11-30"   # 权威，非看板 2026-07-01
    assert out[0].status == "confirmed"


def test_board_fallback_when_no_answer():
    # 有 PO 但 /purchase/answer 无答交（300115→None） → 退看板 boardDate
    board = [_rec("R01.A", "ZB0022", "2026-07-01", ["ZPCG001"])]
    conn = _FakeConnector(board, confirmed={})     # 无任何答交
    out = load_srm_deliveries("real", connector=conn)
    assert len(out) == 1
    assert out[0].committed_date == "2026-07-01"   # 看板辅助
    assert out[0].status == "planned"


def test_no_po_and_no_board_yields_no_record():
    # 子件不在看板 → 无记录 → 上游走无反馈 +30（兜底）
    board = [_rec("R01.A", "ZB0022", "2026-07-01", ["ZPCG001"])]
    conn = _FakeConnector(board, confirmed={"ZPCG001": "2026-11-30"})
    out = load_srm_deliveries("real", connector=conn, materials={"R99.X"})
    assert out == []                               # R99.X 不在看板


def test_earliest_answer_date_when_multiple_pos():
    board = [
        _rec("R01.A", "ZB0022", "2026-07-01", ["ZPCG001", "ZPCG002"]),
    ]
    conn = _FakeConnector(board, confirmed={"ZPCG001": "2026-11-30", "ZPCG002": "2026-09-15"})
    out = load_srm_deliveries("real", connector=conn)
    assert out[0].committed_date == "2026-09-15"   # 取最早权威承诺


def test_cancelled_plan_excluded():
    """已作废的排程明细（cancelFlag 真值）不参与 PO 提取（姚祖怡 07-26 V6 #7）。"""
    board = [_rec("R01.A", "ZB0022", "2026-07-01", ["ZPCG001"], cancel_flag=1)]
    pairs, board_dates = _extract_board_po_map(board, materials=None)
    assert pairs == {} and board_dates == {}


def test_cancelled_plan_excluded_from_deliveries():
    """作废计划整条从 load_srm_deliveries 结果中消失，不产生任何承诺记录。"""
    board = [_rec("R01.A", "ZB0022", "2026-07-01", ["ZPCG001"], cancel_flag=True)]
    conn = _FakeConnector(board, confirmed={"ZPCG001": "2026-11-30"})
    out = load_srm_deliveries("real", connector=conn)
    assert out == []


def test_cancel_flag_falsy_values_kept():
    """cancelFlag 为 None/0/False（现网现状）不受影响，向后兼容。"""
    board = [
        _rec("R01.A", "ZB0022", "2026-07-01", ["ZPCG001"], cancel_flag=None),
        _rec("R02.B", "ZB0099", "2026-07-02", ["ZPCG002"], cancel_flag=0),
    ]
    pairs, _ = _extract_board_po_map(board, materials=None)
    assert pairs["R01.A"] == {("ZPCG001", "ZB0022")}
    assert pairs["R02.B"] == {("ZPCG002", "ZB0099")}


def test_materials_filter_bounds_answer_calls():
    # materials 过滤 → 只对关注子件查 /purchase/answer（尊重 30s 限流）
    board = [
        _rec("R01.A", "ZB0022", "2026-07-01", ["PO_A"]),
        _rec("R02.B", "ZB0099", "2026-07-02", ["PO_B"]),
    ]
    conn = _FakeConnector(board, confirmed={"PO_A": "2026-08-01", "PO_B": "2026-08-02"})
    out = load_srm_deliveries("real", connector=conn, materials={"R01.A"})
    assert [o.material_id for o in out] == ["R01.A"]
    # 只对 R01.A 的 PO 发起答交查询，不含 PO_B
    queried = {po for call in conn.answer_calls for (po, _v) in call}
    assert queried == {"PO_A"}
