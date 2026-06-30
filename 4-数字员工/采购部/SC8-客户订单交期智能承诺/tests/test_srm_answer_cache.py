"""SRM 答交缓存（srm_answer_cache）测试 —— 提速立即重算的增量取数。

覆盖：首次全查并缓存 firm、TTL 内复用跳过查询、过期重查、未答交始终重查、
ttl<=0 关闭复用；以及 load_srm_deliveries 接入缓存后第二次显著少查。
全 mock 不触网。
"""
from __future__ import annotations

from pathlib import Path

from sc8.srm_answer_cache import fetch_confirmed_cached


class FakeConn:
    """假携客云连接器：记录每次 get_confirmed_dates 查了哪些对。"""
    def __init__(self, answers: dict[str, str | None]):
        self.answers = answers          # {poErpNo: 承诺日 或 None(未答交)}
        self.calls: list[list[tuple[str, str]]] = []

    def get_confirmed_dates(self, pairs):
        pairs = list(pairs)
        self.calls.append(pairs)
        out = {po: self.answers[po] for po, _v in pairs if self.answers.get(po)}
        return out, []                  # (confirmed, failed)


def test_first_fetch_caches_firm_then_reuses(tmp_path: Path):
    cache = tmp_path / "c.json"
    conn = FakeConn({"PO1": "2026-07-01", "PO2": None})   # PO1 已答交、PO2 未答交
    pairs = [("PO1", "V"), ("PO2", "V")]

    # 首次：两对都查；PO1 firm 入缓存，PO2 未答交不缓存
    conf1, st1 = fetch_confirmed_cached(conn, pairs, cache_path=cache, ttl_sec=3600, now=1000)
    assert conf1 == {"PO1": "2026-07-01"}
    assert st1 == {"total": 2, "reused": 0, "queried": 2}
    assert conn.calls[0] == [("PO1", "V"), ("PO2", "V")]

    # 再次（TTL 内）：PO1 复用、不再查；只重查未答交的 PO2
    conf2, st2 = fetch_confirmed_cached(conn, pairs, cache_path=cache, ttl_sec=3600, now=2000)
    assert conf2 == {"PO1": "2026-07-01"}
    assert st2 == {"total": 2, "reused": 1, "queried": 1}
    assert conn.calls[1] == [("PO2", "V")]                # 只查了 PO2


def test_expired_firm_is_requeried(tmp_path: Path):
    cache = tmp_path / "c.json"
    conn = FakeConn({"PO1": "2026-07-01"})
    pairs = [("PO1", "V")]
    fetch_confirmed_cached(conn, pairs, cache_path=cache, ttl_sec=3600, now=1000)
    # now 超过 TTL → PO1 重查
    _conf, st = fetch_confirmed_cached(conn, pairs, cache_path=cache, ttl_sec=3600, now=1000 + 3601)
    assert st["queried"] == 1
    assert conn.calls[-1] == [("PO1", "V")]


def test_unanswered_never_cached(tmp_path: Path):
    cache = tmp_path / "c.json"
    conn = FakeConn({"PO9": None})           # 始终未答交
    pairs = [("PO9", "V")]
    for t in (1000, 1100, 1200):             # 连续三次都在 TTL 内
        fetch_confirmed_cached(conn, pairs, cache_path=cache, ttl_sec=99999, now=t)
    assert len(conn.calls) == 3              # 未答交每次都重查（这是会变的部分）


def test_ttl_zero_disables_reuse(tmp_path: Path):
    cache = tmp_path / "c.json"
    conn = FakeConn({"PO1": "2026-07-01"})
    pairs = [("PO1", "V")]
    fetch_confirmed_cached(conn, pairs, cache_path=cache, ttl_sec=0, now=1000)
    fetch_confirmed_cached(conn, pairs, cache_path=cache, ttl_sec=0, now=1001)
    assert len(conn.calls) == 2              # ttl<=0 不复用，每次全查


def test_corrupt_cache_is_ignored(tmp_path: Path):
    cache = tmp_path / "c.json"
    cache.write_text("{ 半截坏 json", encoding="utf-8")   # 损坏缓存
    conn = FakeConn({"PO1": "2026-07-01"})
    conf, st = fetch_confirmed_cached(conn, [("PO1", "V")], cache_path=cache, ttl_sec=3600, now=1000)
    assert conf == {"PO1": "2026-07-01"} and st["queried"] == 1   # 当作空、重新填充


# ── 集成：load_srm_deliveries 接入缓存后第二次少查（需平台 SrmDeliveryOrder）──

def _board(material: str, vendor: str, po: str, bdate: str) -> dict:
    return {"productCode": material, "innerVendorCode": vendor,
            "itemList": [{"boardDate": bdate, "poLineList": [{"poErpNo": po}]}]}


class FakeSrmConn(FakeConn):
    def __init__(self, answers, board):
        super().__init__(answers)
        self._board = board

    def get_receive_board(self, start, end):
        return self._board


def test_load_srm_deliveries_uses_cache(tmp_path: Path):
    from sc8.sources import load_srm_deliveries
    cache = str(tmp_path / "srm.json")
    board = [_board("M1", "V", "PO1", "2026-07-01"),
             _board("M2", "V", "PO2", "2026-07-02")]
    conn = FakeSrmConn({"PO1": "2026-07-01", "PO2": None}, board)
    mats = {"M1", "M2"}

    out1 = load_srm_deliveries("real", materials=mats, connector=conn,
                               cache_path=cache, ttl_sec=3600)
    out2 = load_srm_deliveries("real", materials=mats, connector=conn,
                               cache_path=cache, ttl_sec=3600)
    # 两次结果一致（M1 权威 confirmed、M2 走看板 planned）
    got1 = {d.material_id: (d.committed_date, d.status) for d in out1}
    got2 = {d.material_id: (d.committed_date, d.status) for d in out2}
    assert got1 == got2
    assert got1["M1"] == ("2026-07-01", "confirmed")
    # 第二次 /purchase/answer 只查未答交的 PO2（PO1 命中缓存复用）
    assert conn.calls[0] == [("PO1", "V"), ("PO2", "V")]
    assert conn.calls[1] == [("PO2", "V")]
