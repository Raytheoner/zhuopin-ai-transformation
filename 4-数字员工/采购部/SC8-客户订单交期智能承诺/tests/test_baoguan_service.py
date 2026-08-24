"""baoguan_service 测试 —— compute_snapshot（mock 源）+ SnapshotStore（持久化/重启恢复）。

全 mock，不触网：通过 monkeypatch 替换 sc8.baoguan_service 里的三个真实加载器，
验证「拉三源 → build_dashboard → Snapshot」结构正确，且快照能落盘并重启恢复。
"""
from __future__ import annotations

from datetime import date

from zhuopin_platform.shared_tools.models import BomRow, SrmDeliveryOrder

from sc8 import baoguan_service as bs
from sc8.baoguan_service import Snapshot, SnapshotStore, compute_snapshot
from sc8.models import SalesOrder

TODAY = date(2026, 6, 24)


def _orders():
    return [
        SalesOrder(so_id="FO-1", customer_id="", customer_name="比亚迪",
                   item_code="RED", qty=10, required_date="2026-06-10",
                   doc_type="预测订单", item_name="ECU-A"),
        SalesOrder(so_id="FO-2", customer_id="", customer_name="上汽",
                   item_code="GRN", qty=20, required_date="2026-09-01",
                   doc_type="预测订单", item_name="ECU-B"),
    ]


def _bom(product, *comps):
    return [BomRow(product_id=product, component_id=c, component_name=c,
                   level=1, qty_per_unit=1.0, loss_rate=0.0, unit="PCS") for c in comps]


def _patch_sources(monkeypatch, *, orders, bom, srm, material_commitments=None):
    monkeypatch.setattr(bs, "load_real_orders",
                        lambda **kw: orders)
    monkeypatch.setattr(bs, "load_real_bom",
                        lambda product_ids, **kw: bom)
    monkeypatch.setattr(bs, "load_srm_deliveries",
                        lambda mode, **kw: srm)
    # 默认空字典（零漂移）；测试专用真实网络隔离，不代表生产默认关闭（生产端无条件尝试，
    # 见 compute_snapshot ⑦ 段与 sources.load_material_commitments docstring）。
    monkeypatch.setattr(bs, "load_material_commitments",
                        lambda mode, **kw: material_commitments or {})


def test_compute_snapshot_structure(monkeypatch):
    bom = _bom("RED", "C1") + _bom("GRN", "C2")
    srm = [SrmDeliveryOrder(delivery_id="SRM-C1", demand_id="", supplier_id="",
                            material_id="C1", qty_committed=0,
                            committed_date="2026-11-30", status="confirmed"),
           SrmDeliveryOrder(delivery_id="SRM-C2", demand_id="", supplier_id="",
                            material_id="C2", qty_committed=0,
                            committed_date="2026-08-01", status="confirmed")]
    _patch_sources(monkeypatch, orders=_orders(), bom=bom, srm=srm)

    snap = compute_snapshot(today=TODAY, status="2")
    assert snap.ok is True
    assert len(snap.rows) == 2
    # RED 有承诺但确定晚 → 真延期；GRN 按期 → 绿
    assert snap.counts["red"] == 1 and snap.counts["grn"] == 1
    # 序列化行含去重稳定键所需的 so（预测订单号）
    red = next(r for r in snap.rows if r["id"] == "RED")
    assert red["so"] == "FO-1" and red["risk"] == "red"
    assert snap.components == 2 and snap.srm_hit == 2
    assert snap.param_version


def test_srm_date_without_batch_detail_keeps_legacy_date(monkeypatch):
    """🔴 队列 #344 的取数边界，单独锁一条用例，别让它只活在文档里。

    某子件在 `/purchase/answer` 有承诺日（`srm_deliveries`）、但在逐笔答交明细
    （`load_material_commitments`，`receiveType==2` 按排程交货）里**没有记录** ⇒
    **仍沿用那个承诺日**，四色不变。

    #344 只改「有答交记录时怎么按数量取值」，**不改「什么算有答交」**——后者要动
    `load_srm_deliveries` 这条驱动四色的既有管线，而 #211 v2 明写其筛选「范围仅限
    本函数……未经授权不改判定逻辑」。该换源问题已另行登记待姚祖怡签认。
    （实测换源只影响 2 行、四色计数不变——**影响面小并不构成"顺手改掉"的理由**，
    正如影响面大也不构成"必须改"的理由。）
    """
    bom = _bom("GRN", "C2")
    srm = [SrmDeliveryOrder(delivery_id="SRM-C2", demand_id="", supplier_id="",
                            material_id="C2", qty_committed=0,
                            committed_date="2026-08-01", status="confirmed")]
    _patch_sources(monkeypatch, orders=_orders()[1:], bom=bom, srm=srm,
                   material_commitments={})   # 逐笔明细里查无此料

    snap = compute_snapshot(today=TODAY, status="2")
    row = next(r for r in snap.rows if r["id"] == "GRN")
    assert row["kit"] == "2026-08-01"      # 改造前是什么，现在还是什么
    assert row["risk"] == "grn"


def test_compute_snapshot_resolves_leaf_components_not_semi_finished(monkeypatch):
    """姚祖怡 07-26 V6 #9 根因修复：BOM 含半成品中间层时，components（驱动 SRM/
    库存/PO 在途查询范围）应解析为真正叶子件，不应把半成品自身当作待查子件——
    半成品是自制件，从无供应商承诺/采购在途记录，查它毫无意义。"""
    bom = [
        BomRow(product_id="RED", component_id="SEMI", component_name="半成品",
              level=1, qty_per_unit=1.0, loss_rate=0.0, unit="PCS"),
        BomRow(product_id="SEMI", component_id="C1", component_name="原材料",
              level=2, qty_per_unit=2.0, loss_rate=0.0, unit="PCS"),
    ]
    srm = [SrmDeliveryOrder(delivery_id="SRM-C1", demand_id="", supplier_id="",
                            material_id="C1", qty_committed=0,
                            committed_date="2026-11-30", status="confirmed")]
    _patch_sources(monkeypatch, orders=[_orders()[0]], bom=bom, srm=srm)

    snap = compute_snapshot(today=TODAY, status="2")
    assert snap.components == 1   # 只有叶子件 C1，中间节点 SEMI 不计入


def test_compute_snapshot_fail_loud(monkeypatch):
    """real 源不可达 → 异常上抛（不吞、不回退 mock）。"""
    def _boom(**kw):
        raise RuntimeError("FO endpoint unreachable")
    monkeypatch.setattr(bs, "load_real_orders", _boom)
    try:
        compute_snapshot(today=TODAY)
        assert False, "应当 fail-loud 抛出"
    except RuntimeError as e:
        assert "unreachable" in str(e)


def test_snapshot_store_persist_and_reload(tmp_path):
    path = tmp_path / "baoguan_snapshot.json"
    store = SnapshotStore(path)
    assert store.has_data() is False
    assert store.get().ok is False             # 空态

    snap = Snapshot(generated_at="2026-06-24T10:00:00", today="2026-06-24",
                    rows=[{"id": "RED", "so": "FO-1", "risk": "red", "ship": "2026-06-10"}],
                    counts={"red": 1, "gap": 0, "yel": 0, "grn": 0}, status="2",
                    param_version="sc8-params-v0", components=2, srm_hit=2)
    store.set(snap)
    assert path.exists()

    # 新实例从 JSON 恢复（模拟重启）
    store2 = SnapshotStore(path)
    assert store2.has_data() is True
    got = store2.get()
    assert got.counts["red"] == 1 and got.rows[0]["so"] == "FO-1"


def test_snapshot_store_in_memory_no_file(tmp_path):
    store = SnapshotStore(None)               # 纯内存
    store.set(Snapshot(generated_at="x", today="2026-06-24", rows=[],
                       counts={"red": 0, "gap": 0, "yel": 0, "grn": 0}))
    assert store.has_data() is True


# ── PO 在途数据接入（功能批1，2026-07-23）：#12/#14 共享基础 ────────────────────

def test_compute_snapshot_wires_purchase_orders_into_rows(monkeypatch):
    """PO 加载成功 → component_status/dkq 等字段随行序列化出现（无需开净额也能测 cst）。"""
    bom = _bom("RED", "C1")
    srm = []   # 无 SRM 承诺 → C1 无答复、待催
    _patch_sources(monkeypatch, orders=[_orders()[0]], bom=bom, srm=srm)
    monkeypatch.setattr(bs, "load_purchase_orders_by_material",
                        lambda materials, **kw: {"C1": 40.0})

    snap = compute_snapshot(today=TODAY, status="2")
    red = next(r for r in snap.rows if r["id"] == "RED")
    assert red["cst"] == [{"id": "C1", "name": "C1", "qty": 10.0,
                          "st": "transit_unconfirmed", "tq": 40.0,
                          "aq": None, "gq": None, "cd": None, "cb": [],
                          "role": ""}]


def test_compute_snapshot_degrades_gracefully_when_po_source_fails(monkeypatch):
    """PO 端点异常（纯展示派生列）→ 降级为无数据，不阻断整体重算（与 FO/BOM/SRM 强
    fail-loud 语义有意区分）。"""
    bom = _bom("RED", "C1")
    _patch_sources(monkeypatch, orders=[_orders()[0]], bom=bom, srm=[])

    def _boom(materials, **kw):
        raise RuntimeError("PO endpoint unreachable")
    monkeypatch.setattr(bs, "load_purchase_orders_by_material", _boom)

    snap = compute_snapshot(today=TODAY, status="2")   # 不抛异常
    assert snap.ok is True
    red = next(r for r in snap.rows if r["id"] == "RED")
    assert red["cst"] == []   # 降级：无 PO 数据，#12 字段恒空，不影响四色/rows 计算


def test_compute_snapshot_skips_po_load_when_toggle_off(monkeypatch):
    """SC8_PO_TRANSIT=off → 完全不调用 PO 加载器（应急开关）。"""
    monkeypatch.setenv("SC8_PO_TRANSIT", "off")
    bom = _bom("RED", "C1")
    _patch_sources(monkeypatch, orders=[_orders()[0]], bom=bom, srm=[])
    called = []
    monkeypatch.setattr(bs, "load_purchase_orders_by_material",
                        lambda materials, **kw: called.append(1) or {})

    compute_snapshot(today=TODAY, status="2")
    assert called == []


# ── 物料逐笔承诺明细接入（#18-a/b，姚祖怡 07-28 判例回件，队列 #139）─────────────

def test_compute_snapshot_wires_material_commitments_into_confirmed_batches(monkeypatch):
    """material_commitments 加载成功 → 答交数量累计明细随行序列化出现（cst[].cb）。"""
    bom = _bom("RED", "C1")
    srm = [SrmDeliveryOrder(delivery_id="SRM-C1", demand_id="", supplier_id="",
                            material_id="C1", qty_committed=0,
                            committed_date="2026-07-20", status="confirmed")]
    _patch_sources(monkeypatch, orders=[_orders()[0]], bom=bom, srm=srm)
    monkeypatch.setattr(bs, "load_purchase_orders_by_material",
                        lambda materials, **kw: {"C1": 10.0})
    monkeypatch.setattr(bs, "load_material_commitments",
                        lambda mode, **kw: {"C1": [(date(2026, 7, 20), 10.0)]})

    snap = compute_snapshot(today=TODAY, status="2")
    red = next(r for r in snap.rows if r["id"] == "RED")
    assert red["cst"][0]["cb"] == [{"d": "2026-07-20", "q": 10.0}]


def test_compute_snapshot_degrades_gracefully_when_material_commitments_fails(monkeypatch):
    """material_commitments 端点异常（纯展示派生列）→ 降级为无数据，不阻断整体重算。"""
    bom = _bom("RED", "C1")
    srm = [SrmDeliveryOrder(delivery_id="SRM-C1", demand_id="", supplier_id="",
                            material_id="C1", qty_committed=0,
                            committed_date="2026-07-20", status="confirmed")]
    _patch_sources(monkeypatch, orders=[_orders()[0]], bom=bom, srm=srm)
    monkeypatch.setattr(bs, "load_purchase_orders_by_material",
                        lambda materials, **kw: {"C1": 10.0})

    def _boom(mode, **kw):
        raise RuntimeError("SRM board endpoint unreachable")
    monkeypatch.setattr(bs, "load_material_commitments", _boom)

    snap = compute_snapshot(today=TODAY, status="2")   # 不抛异常
    assert snap.ok is True
    red = next(r for r in snap.rows if r["id"] == "RED")
    assert red["cst"][0]["cb"] == []   # 降级：无 material_commitments 数据，cb 恒空


# ── 物料看板接线（队列 #334，tasks 4.2）──────────────────────────────────────

def test_compute_snapshot_attaches_material_board(monkeypatch):
    """compute_snapshot 末尾派生物料看板，结果落进 Snapshot.materials/materials_meta。"""
    bom = _bom("RED", "C1")
    srm = [SrmDeliveryOrder(delivery_id="SRM-C1", demand_id="", supplier_id="",
                            material_id="C1", qty_committed=0,
                            committed_date="2026-11-30", status="confirmed")]
    _patch_sources(monkeypatch, orders=[_orders()[0]], bom=bom, srm=srm,
                   material_commitments={"C1": [(date(2026, 11, 30), 5.0)]})
    monkeypatch.setattr(bs, "load_purchase_orders_by_material",
                        lambda materials, **kw: {"C1": 4.0})
    monkeypatch.setattr(bs, "load_purchase_supply_by_material",
                        lambda materials, **kw: {"C1": {"suppliers": ["S1"], "buyers": ["某某"]}})

    snap = compute_snapshot(today=TODAY, status="2")
    assert [m["id"] for m in snap.materials] == ["C1"]
    row = snap.materials[0]
    assert row["sup"] == ["S1"] and row["tq"] == 4.0
    assert row["owner"] and row["brand"]          # 取数缺口列显式标注，不留空
    assert snap.materials_meta["window"] == "2026-06 ~ 2026-08"
    assert [m["label"] for m in snap.materials_meta["months"]] == ["6月", "7月", "8月"]


def test_material_board_does_not_shift_existing_rows_or_counts(monkeypatch):
    """红线：新增视图不得改动任何既有判定。逐字段比对「有无物料看板」两种情形。"""
    bom = _bom("RED", "C1") + _bom("GRN", "C2")
    srm = [SrmDeliveryOrder(delivery_id="SRM-C1", demand_id="", supplier_id="",
                            material_id="C1", qty_committed=0,
                            committed_date="2026-11-30", status="confirmed"),
           SrmDeliveryOrder(delivery_id="SRM-C2", demand_id="", supplier_id="",
                            material_id="C2", qty_committed=0,
                            committed_date="2026-08-01", status="confirmed")]
    _patch_sources(monkeypatch, orders=_orders(), bom=bom, srm=srm)
    monkeypatch.setattr(bs, "load_purchase_orders_by_material", lambda materials, **kw: {})
    monkeypatch.setattr(bs, "load_purchase_supply_by_material", lambda materials, **kw: {})
    with_board = compute_snapshot(today=TODAY, status="2")

    monkeypatch.setattr(bs, "build_material_board",
                        lambda rows, **kw: (_ for _ in ()).throw(RuntimeError("disabled")))
    without_board = compute_snapshot(today=TODAY, status="2")

    assert with_board.rows == without_board.rows          # 逐字段
    assert with_board.counts == without_board.counts
    assert with_board.components == without_board.components
    assert with_board.srm_hit == without_board.srm_hit
    assert without_board.materials == [] and without_board.materials_meta == {}


def test_compute_snapshot_degrades_gracefully_when_supply_loader_fails(monkeypatch):
    """供应商/制单人取数失败（纯展示派生列）→ 供应商列为空，物料看板与整体重算仍完成。"""
    bom = _bom("RED", "C1")
    srm = [SrmDeliveryOrder(delivery_id="SRM-C1", demand_id="", supplier_id="",
                            material_id="C1", qty_committed=0,
                            committed_date="2026-11-30", status="confirmed")]
    _patch_sources(monkeypatch, orders=[_orders()[0]], bom=bom, srm=srm)
    monkeypatch.setattr(bs, "load_purchase_orders_by_material", lambda materials, **kw: {})

    def _boom(materials, **kw):
        raise RuntimeError("ERP unreachable")
    monkeypatch.setattr(bs, "load_purchase_supply_by_material", _boom)

    snap = compute_snapshot(today=TODAY, status="2")   # 不抛异常
    assert snap.ok is True and snap.materials
    assert snap.materials[0]["sup"] == []


def test_line_status_is_fetched_once_and_shared_by_both_po_loaders(monkeypatch):
    """行级关闭状态查询按料号逐个打 ERP、无缓存（生产约 1600 次 HTTP／约 2 分钟）——
    物料看板不得让它跑第二遍。预取一次、显式传给 ⑥⑧ 两个 loader。"""
    bom = _bom("RED", "C1")
    srm = [SrmDeliveryOrder(delivery_id="SRM-C1", demand_id="", supplier_id="",
                            material_id="C1", qty_committed=0,
                            committed_date="2026-11-30", status="confirmed")]
    _patch_sources(monkeypatch, orders=[_orders()[0]], bom=bom, srm=srm)

    calls = {"prefetch": 0}
    sentinel = {("PO1", "1"): 4}

    def _prefetch(components, **kw):
        calls["prefetch"] += 1
        return sentinel
    monkeypatch.setattr(bs, "_prefetch_line_status", _prefetch)

    seen: list[object] = []
    monkeypatch.setattr(bs, "load_purchase_orders_by_material",
                        lambda materials, **kw: (seen.append(kw.get("line_status")) or {}))
    monkeypatch.setattr(bs, "load_purchase_supply_by_material",
                        lambda materials, **kw: (seen.append(kw.get("line_status")) or {}))

    compute_snapshot(today=TODAY, status="2")
    assert calls["prefetch"] == 1                 # 只取一次
    assert seen == [sentinel, sentinel]           # 两个 loader 拿到的是同一份
