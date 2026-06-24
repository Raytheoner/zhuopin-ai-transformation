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


def _patch_sources(monkeypatch, *, orders, bom, srm):
    monkeypatch.setattr(bs, "load_real_orders",
                        lambda **kw: orders)
    monkeypatch.setattr(bs, "load_real_bom",
                        lambda product_ids, **kw: bom)
    monkeypatch.setattr(bs, "load_srm_deliveries",
                        lambda mode, **kw: srm)


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
