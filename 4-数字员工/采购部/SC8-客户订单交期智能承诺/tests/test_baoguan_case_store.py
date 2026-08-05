"""保供案例处置中心（case_store）测试 —— 内存 SQLite，全 mock。

覆盖：建案幂等（同稳定键不重建）、状态机合法/非法流转、SLA 滞留、关闭、手动建案、events 留痕、
#223 bottleneck_unanswered 字段落库与旧库迁移。
"""
from __future__ import annotations

import sqlite3

from sc8.case_store import CaseStatus, CaseStore


def _store():
    return CaseStore(":memory:")


def _new(store, **kw):
    base = dict(item_code="S02Y.0188", fo_id="FO-1", customer_name="比亚迪",
                ship_date="2026-06-10", confirmed_gap_days=61,
                bottleneck_material="S02Y.0188")
    base.update(kw)
    return store.create_case(**base)


def test_create_case_idempotent_same_key():
    store = _store()
    c1, created1 = _new(store)
    c2, created2 = _new(store)                         # 同 (item_code, fo_id, ship_date)
    assert created1 is True and created2 is False
    assert c1.id == c2.id
    assert len(store.get_open_cases()) == 1
    assert c1.status == CaseStatus.EXPEDITE


def test_create_case_different_ship_date_is_new():
    store = _store()
    _new(store)
    _, created = _new(store, ship_date="2026-07-01")   # 出货日不同 → 新案
    assert created is True
    assert len(store.get_open_cases()) == 2


def test_advance_status_legal_flow():
    store = _store()
    c, _ = _new(store)
    c = store.advance_status(c.id, actor="保供小王", note="已催供应商")
    assert c.status == CaseStatus.COORDINATE
    c = store.advance_status(c.id, actor="保供小王", note="协调插单")
    assert c.status == CaseStatus.RESCHEDULE
    c = store.advance_status(c.id, actor="保供小王", note="供应商确认改期",
                             new_confirmed_date="2026-08-15")
    assert c.status == CaseStatus.CLOSED
    assert c.new_confirmed_date == "2026-08-15"


def test_advance_closed_raises():
    store = _store()
    c, _ = _new(store)
    store.resolve_case(c.id, actor="保供小王", note="料已齐")
    try:
        store.advance_status(c.id, actor="x")
        assert False, "已关闭不可推进"
    except ValueError:
        pass


def test_resolve_removes_from_open():
    store = _store()
    c, _ = _new(store)
    store.resolve_case(c.id, actor="保供小王", note="风险消除")
    assert store.get_open_cases() == []
    assert store.find_open_by_key("S02Y.0188", "FO-1", "2026-06-10") is None
    # 关闭后同键可再建新案
    _, created = _new(store)
    assert created is True


def test_manual_create_and_events():
    store = _store()
    c, created = store.create_case(item_code="F02N.0213", fo_id="FO-9",
                                   customer_name="上汽", ship_date="2026-07-01",
                                   actor="保供小李", manual=True)
    assert created is True
    store.advance_status(c.id, actor="保供小李", note="catch")
    evs = store.get_events(c.id)
    assert evs[0].action == "created" and "手动建案" in evs[0].note
    assert evs[-1].action == "advanced"


def test_stale_case_detection(monkeypatch):
    store = _store()
    c, _ = _new(store)
    # 把 updated_at 改到 100 小时前 → 超催货 24h SLA
    old = "2026-01-01T00:00:00"
    store._conn.execute("UPDATE supply_cases SET updated_at=? WHERE id=?", (old, c.id))
    store._conn.commit()
    stale = store.get_stale_cases()
    assert len(stale) == 1 and stale[0].id == c.id
    assert stale[0].is_overdue_sla is True


# ── 队列 #223：bottleneck_unanswered 落库与旧库迁移 ──────────────────────────────

def test_bottleneck_unanswered_defaults_false():
    store = _store()
    c, _ = _new(store)
    assert c.bottleneck_unanswered is False


def test_bottleneck_unanswered_persists_true():
    store = _store()
    c, _ = _new(store, bottleneck_unanswered=True)
    assert c.bottleneck_unanswered is True
    # 重新查询（走 get_case，非 create_case 返回值）同样为 True，证明真落库而非仅内存对象
    reloaded = store.get_case(c.id)
    assert reloaded.bottleneck_unanswered is True


def test_old_db_without_bottleneck_unanswered_column_migrates(tmp_path):
    """真实部署库（reports/*.db）可能已有旧 schema（无本列）——CaseStore 打开时须
    自动补迁移列，不能因 CREATE TABLE IF NOT EXISTS 对已存在表不生效而报错。"""
    db_path = tmp_path / "legacy_cases.db"
    # 手工建一个不含 bottleneck_unanswered 列的旧版表结构
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE supply_cases (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            case_no             TEXT    UNIQUE NOT NULL,
            item_code           TEXT    NOT NULL,
            fo_id               TEXT    NOT NULL DEFAULT '',
            customer_name       TEXT    NOT NULL DEFAULT '',
            ship_date           TEXT    NOT NULL DEFAULT '',
            confirmed_gap_days  INTEGER NOT NULL DEFAULT 0,
            bottleneck_material TEXT    NOT NULL DEFAULT '',
            status              TEXT    NOT NULL DEFAULT 'expedite',
            new_confirmed_date  TEXT    NOT NULL DEFAULT '',
            created_at          TEXT    NOT NULL,
            updated_at          TEXT    NOT NULL,
            resolved_at         TEXT    NOT NULL DEFAULT ''
        );
        INSERT INTO supply_cases (case_no, item_code, fo_id, ship_date, created_at, updated_at)
        VALUES ('BG-0001', 'S02Y.0188', 'FO-1', '2026-06-10', '2026-06-10T00:00:00', '2026-06-10T00:00:00');
    """)
    conn.commit()
    conn.close()

    store = CaseStore(str(db_path))   # 打开旧库不应报错，且自动补列
    cases = store.get_all_cases()
    assert len(cases) == 1
    assert cases[0].bottleneck_unanswered is False   # 迁移默认值，旧行按"已答复"兼容
    # 迁移后可正常建新案（新列可写）
    c2, created = store.create_case(item_code="S02Y.0189", fo_id="FO-2", customer_name="",
                                    ship_date="2026-06-11", bottleneck_unanswered=True)
    assert created is True and c2.bottleneck_unanswered is True
