"""黄金基准回归（合成）—— 引擎确定性零偏差 + 分类档与预期一致（spec: fi1-reconcile-engine D9）。

样本覆盖四档：损耗溢短·标准内 / 超损·需人工 / 来料短缺·需人工 / 管理差异·无理论基准待核。
合成 golden 可入库；8/15 历史人工对账到位后替换为真实 golden（收口待对接人）。
"""
from __future__ import annotations

import csv

from zhuopin_platform.shared_tools.models import BomRow

from fi1.feed_source import parse_feeds, parse_outputs
from fi1.reconcile_engine import compute_reconcile
from fi1.variance_classify import classify_all

# 预期（人工核算，零偏差基准）
EXPECTED = {
    "G1": dict(theoretical_net=200, standard_loss=20.0, actual_feed=215, total_variance=15,
               variance_pct=0.075, classification="损耗溢短·标准内", needs_review=False),
    "G2": dict(theoretical_net=100, standard_loss=5.0, actual_feed=120, total_variance=20,
               variance_pct=0.2, classification="超损", needs_review=True),
    "G3": dict(theoretical_net=500, standard_loss=25.0, actual_feed=480, total_variance=-20,
               variance_pct=-0.04, classification="来料短缺", needs_review=True),
    "G4": dict(theoretical_net=0, standard_loss=0, actual_feed=30, total_variance=30,
               variance_pct=None, classification="管理差异·无理论基准待核", needs_review=True),
}


def _read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def test_golden_zero_deviation(golden_dir):
    bom = [BomRow(r["product_id"], r["component_id"], r["component_name"], int(r["level"]),
                  float(r["qty_per_unit"]), float(r["loss_rate"]), r["unit"])
           for r in _read(golden_dir / "golden_bom.csv")]
    outputs = parse_outputs(_read(golden_dir / "golden_outputs.csv"))
    feeds = parse_feeds(_read(golden_dir / "golden_feeds.csv"))

    comp = compute_reconcile(bom, outputs, feeds)
    classified = {c.component_id: c for c in classify_all(comp.components)}

    assert set(classified) == set(EXPECTED), "对账子件集合与黄金样本不符"
    for cid, exp in EXPECTED.items():
        c = classified[cid]
        for field, want in exp.items():
            got = getattr(c, field)
            assert got == want, f"{cid}.{field}: 期望 {want!r} 实得 {got!r}（黄金回归零偏差被破坏）"
