"""物料逐笔承诺提取（B2 数据管线，shortage-baoguan-criteria-v3，2026-07-10 会议定稿）。

与 _extract_board_po_map 不同：本函数不收窄成"最早一条"，保留每条
answerQty>0 的 (承诺日期, 数量) 记录，供 sc8.period_match 逐笔累加。全 mock。
"""
from __future__ import annotations

from datetime import date, timedelta

from sc8 import config
from sc8.sources import _chunk_date_windows, _extract_board_commitments, load_material_commitments


def _rec(material: str, vendor: str, items: list[dict], *, receive_type: int = 2) -> dict:
    """默认 receiveType=2（按排程交货，队列 #211 v2 权威口径）。"""
    return {"productCode": material, "innerVendorCode": vendor, "itemList": items,
            "receiveType": receive_type}


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


def test_unanswered_item_none_excluded():
    """队列 #296（v4，三态判据）：answerQty is None（待答交，供应商未回复）不产生
    记录——上游据此如实显示"无"。"""
    board = [_rec("M1", "V1", [_item("2026-07-01", None)])]
    result = _extract_board_commitments(board, materials=None)
    assert "M1" not in result


def test_answered_zero_qty_included_not_confused_with_no_reply():
    """队列 #296（v4）核心修复：answerQty==0（已答交、供应商确认答不了，"差异
    已确认"）是合法记录，**必须**产生记录、显示为 0——此前与"待答交"（None）
    被混为一谈是本次核心缺陷（姚祖怡原话："『无』与『0』被混为一谈"）。真实案例
    `R01A.1022`：planQty=5000, answerQty=0（2026-08-07 生产凭据实测）。"""
    board = [_rec("R01A.1022", "V1", [_item("2026-07-01", 0)])]
    result = _extract_board_commitments(board, materials=None)
    assert result["R01A.1022"] == [(date(2026, 7, 1), 0.0)]


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


def test_order_based_delivery_excluded(): # 队列 #211 v2：receiveType=1（按订单交货）不得计入
    board = [_rec("M1", "V1", [_item("2026-07-01", 30)], receive_type=1)]
    result = _extract_board_commitments(board, materials=None)
    assert "M1" not in result


def test_scheduled_and_order_based_mixed_only_scheduled_counted():
    """同料号同时存在按排程交货与按订单交货两条记录（姚祖怡 07-31 举证的真实拓扑），
    只有 receiveType=2（按排程交货）参与累加。"""
    board = [
        _rec("M1", "V1", [_item("2026-08-07", 500)], receive_type=1),   # 按订单交货，错误来源
        _rec("M1", "V2", [_item("2026-12-25", 14000)], receive_type=2),  # 按排程交货，权威来源
    ]
    result = _extract_board_commitments(board, materials=None)
    assert result["M1"] == [(date(2026, 12, 25), 14000.0)]


def test_load_material_commitments_mock_mode_returns_empty():
    assert load_material_commitments("mock") == {}


def test_load_material_commitments_real_mode_uses_connector():
    """显式给窄窗口（单段）时行为与改造前一致——不因新增分段查询而改变既有语义。"""
    conn = _FakeConnector([_rec("M1", "V1", [_item("2026-07-01", 30), _item("2026-07-10", 20)])])
    result = load_material_commitments(
        "real", start="2026-07-01", end="2026-07-31", connector=conn)
    assert sorted(result["M1"]) == [(date(2026, 7, 1), 30.0), (date(2026, 7, 10), 20.0)]


# ── #262：窗口结构性扩大（分段查询 + 合并，不再固定 60 天）─────────────────────

def test_chunk_date_windows_splits_at_60_day_span():
    windows = _chunk_date_windows(date(2026, 1, 1), date(2026, 6, 30), max_span_days=60)
    assert windows == [
        ("2026-01-01", "2026-03-02"),   # 60 天含首尾
        ("2026-03-03", "2026-05-02"),   # 下一段起点 = 上一段终点+1天，不重叠
        ("2026-05-03", "2026-06-30"),   # 尾段不足 60 天时按剩余天数收尾
    ]


def test_chunk_date_windows_single_window_when_within_span():
    assert _chunk_date_windows(date(2026, 1, 1), date(2026, 1, 31), max_span_days=60) == [
        ("2026-01-01", "2026-01-31"),
    ]


def test_chunk_date_windows_exact_span_boundary_is_one_window():
    windows = _chunk_date_windows(date(2026, 1, 1), date(2026, 3, 2), max_span_days=60)
    assert windows == [("2026-01-01", "2026-03-02")]


class _MultiWindowConnector:
    """按调用顺序记录每次 (start, end)，每段返回不同的 board 数据（无重叠数据）。"""

    def __init__(self, boards_by_call: list[list[dict]]):
        self._boards = list(boards_by_call)
        self.calls: list[tuple[str, str]] = []

    def get_receive_board(self, start=None, end=None):
        self.calls.append((start, end))
        idx = len(self.calls) - 1
        return self._boards[idx] if idx < len(self._boards) else []


def test_default_window_queries_multiple_chunks_and_merges(monkeypatch):
    """默认（不传 start/end）走 config 前瞻天数，分段查询后合并——不再只查 60 天。"""
    monkeypatch.setenv("SC8_COMMITMENT_LOOKAHEAD_DAYS", "150")   # 150 天 → 3 段
    conn = _MultiWindowConnector([
        [_rec("M1", "V1", [_item("2026-07-01", 30)])],           # 段一：近期未答交/已答交
        [_rec("M1", "V1", [_item("2026-11-25", 10000)])],        # 段二：R01A.1028 真实场景复现
        [],                                                       # 段三：空
    ])
    result = load_material_commitments("real", connector=conn)
    assert len(conn.calls) == 3
    assert sorted(result["M1"]) == [(date(2026, 7, 1), 30.0), (date(2026, 11, 25), 10000.0)]


def test_far_future_commitment_no_longer_lost_to_60_day_window(monkeypatch):
    """R01A.1028 真实复现：60 天默认窗口下"无"，扩大窗口后正确取得 10000/2026-11-25。

    队列 #296（v4）修正：段一的"未答交排程"占位改用 `answer_qty=None`——0 现在是
    合法的"已答交=0"值（见 test_answered_zero_qty_included_not_confused_with_no_reply），
    不能再用 0 表示"未答交"，否则测试会随实现修正而意外通过/失败。"""
    monkeypatch.setenv("SC8_COMMITMENT_LOOKAHEAD_DAYS", "120")
    conn = _MultiWindowConnector([
        [_rec("R01A.1028", "V1", [_item("2026-08-05", None)])],   # 段一：60天内仅未答交排程
        [_rec("R01A.1028", "V1", [_item("2026-11-25", 10000)])],  # 段二：真实答交批次
    ])
    result = load_material_commitments("real", connector=conn)
    assert result["R01A.1028"] == [(date(2026, 11, 25), 10000.0)]


def test_no_overlap_across_chunk_boundary_avoids_double_counting():
    """分段边界日期各自只被查询一次，不因窗口重叠导致同一条记录被累计两次。"""
    conn = _MultiWindowConnector([
        [_rec("M1", "V1", [_item("2026-03-02", 100)])],   # 段一末尾
        [_rec("M1", "V1", [_item("2026-03-03", 200)])],   # 段二开头（紧邻不重叠）
    ])
    result = load_material_commitments(
        "real", start="2026-01-01", end="2026-05-02", connector=conn)
    assert len(conn.calls) == 2
    assert sorted(result["M1"]) == [(date(2026, 3, 2), 100.0), (date(2026, 3, 3), 200.0)]


# ── config.material_commitment_lookahead_days()（队列 #262 根因修复）───────────

def test_material_commitment_lookahead_days_defaults_365(monkeypatch):
    """队列 #296 v4：默认值 180→365（姚祖怡 08-06 第四次举证后明确要求）。"""
    monkeypatch.delenv("SC8_COMMITMENT_LOOKAHEAD_DAYS", raising=False)
    assert config.material_commitment_lookahead_days() == 365


def test_material_commitment_lookahead_days_explicit_override(monkeypatch):
    monkeypatch.setenv("SC8_COMMITMENT_LOOKAHEAD_DAYS", "90")
    assert config.material_commitment_lookahead_days() == 90


def test_material_commitment_lookahead_days_invalid_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("SC8_COMMITMENT_LOOKAHEAD_DAYS", "not-a-number")
    assert config.material_commitment_lookahead_days() == 365


def test_365_day_window_chunks_into_six_segments():
    """队列 #296：真实测算 365 天窗口分段数（非估算"约7段"，实测 6 段）。"""
    today = date(2026, 8, 7)
    windows = _chunk_date_windows(today, today + timedelta(days=365))
    assert len(windows) == 6


def test_material_commitment_lookahead_days_floor_is_one(monkeypatch):
    monkeypatch.setenv("SC8_COMMITMENT_LOOKAHEAD_DAYS", "0")
    assert config.material_commitment_lookahead_days() == 1
