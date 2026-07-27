"""物料逐笔承诺提取（B2 数据管线，shortage-baoguan-criteria-v3，2026-07-10 会议定稿）。

与 _extract_board_po_map 不同：本函数不收窄成"最早一条"，保留每条
answerQty>0 的 (承诺日期, 数量) 记录，供 sc8.period_match 逐笔累加。全 mock。
"""
from __future__ import annotations

from datetime import date

from sc8.sources import _extract_board_commitments, load_material_commitments


def _rec(material: str, vendor: str, items: list[dict]) -> dict:
    return {"productCode": material, "innerVendorCode": vendor, "itemList": items}


def _item(board_date: str, answer_qty: int, *, cancel_flag=None) -> dict:
    return {"boardDate": board_date, "answerQty": answer_qty, "cancelFlag": cancel_flag}


class _FakeConnector:
    def __init__(self, board: list):
        self._board = board

    def get_receive_board(self, start=None, end=None):
        return self._board


def test_single_commitment_extracted():
    board = [_rec("M1", "V1", [_item("2026-07-01", 30)])]
    result = _extract_board_commitments(board, materials=None)
    assert result["M1"] == [(date(2026, 7, 1), 30.0)]


def test_multiple_commitments_preserved_not_collapsed():
    """多条承诺记录全部保留，不像 _extract_board_po_map 那样收窄成最早一条。"""
    board = [_rec("M1", "V1", [_item("2026-06-25", 30), _item("2026-07-05", 40)])]
    result = _extract_board_commitments(board, materials=None)
    assert sorted(result["M1"]) == [(date(2026, 6, 25), 30.0), (date(2026, 7, 5), 40.0)]


def test_zero_answer_qty_excluded():
    """answerQty<=0（未答交）不产生记录，不能当成"承诺数量为 0"参与累加。"""
    board = [_rec("M1", "V1", [_item("2026-07-01", 0)])]
    result = _extract_board_commitments(board, materials=None)
    assert "M1" not in result


def test_cancelled_plan_excluded_from_commitments():
    """已作废的交付计划（cancelFlag 真值）不参与承诺累加（姚祖怡 07-26 V6 #7）。"""
    board = [_rec("M1", "V1", [_item("2026-07-01", 30, cancel_flag=1),
                              _item("2026-07-05", 40, cancel_flag=None)])]
    result = _extract_board_commitments(board, materials=None)
    assert result["M1"] == [(date(2026, 7, 5), 40.0)]


def test_materials_filter_bounds_result():
    board = [_rec("M1", "V1", [_item("2026-07-01", 30)]),
             _rec("M2", "V1", [_item("2026-07-01", 20)])]
    result = _extract_board_commitments(board, materials={"M1"})
    assert list(result.keys()) == ["M1"]


def test_load_material_commitments_mock_mode_returns_empty():
    assert load_material_commitments("mock") == {}


def test_load_material_commitments_real_mode_uses_connector():
    conn = _FakeConnector([_rec("M1", "V1", [_item("2026-07-01", 30), _item("2026-07-10", 20)])])
    result = load_material_commitments("real", connector=conn)
    assert sorted(result["M1"]) == [(date(2026, 7, 1), 30.0), (date(2026, 7, 10), 20.0)]
