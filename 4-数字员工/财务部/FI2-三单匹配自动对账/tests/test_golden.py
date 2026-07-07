"""黄金基准回归（合成）—— 匹配引擎 + 分类结果零偏差（design D9，spec: fi2-match-engine/fi2-result-classify）。

样本覆盖五类判定 + 明细错位正反例（详见 data/golden 四表）。合成 golden 可入库；
真实小样本待 9 月数据闸接通后另行提交变更包补齐（design 晋档 2）。
"""
from __future__ import annotations

from fi2.run import run

EXPECTED = {
    ("PO-1000", "10"): dict(classification="完全匹配", needs_review=False, status="l3_suggested_pass"),
    ("PO-1000", "20"): dict(classification="金额微差", needs_review=True, status="needs_review"),
    ("PO-2000", "10"): dict(classification="明细错位", needs_review=True, status="needs_review"),
    ("PO-2000", "20"): dict(classification="明细错位", needs_review=True, status="needs_review"),
    ("PO-3000", "10"): dict(classification="数量金额不符", needs_review=True, status="needs_review"),
    ("PO-4000", "10"): dict(classification="数量金额不符", needs_review=True, status="needs_review"),
    ("PO-4000", "20"): dict(classification="数量金额不符", needs_review=True, status="needs_review"),
    ("PO-5000", "10"): dict(classification="无GR支撑", needs_review=True, status="needs_review"),
    ("PO-6000", "10"): dict(classification="数量金额不符", needs_review=True, status="needs_review"),
    ("PO-7000", "10"): dict(classification="数量金额不符", needs_review=True, status="needs_review"),
}


def test_golden_zero_deviation(golden_dir):
    report = run("mock", mock_dir=golden_dir)
    items = {(it["po_no"], it["line_no"]): it for it in report["items"]}

    assert set(items) == set(EXPECTED), "匹配结果 PO 行集合与黄金样本不符"
    for key, expected in EXPECTED.items():
        got = items[key]
        for field, want in expected.items():
            assert got[field] == want, (
                f"{key}.{field}: 期望 {want!r} 实得 {got[field]!r}（黄金回归零偏差被破坏）"
            )

    assert report["summary"]["total"] == 10
    assert report["summary"]["l3_suggested_pass"] == 1
    assert report["summary"]["needs_review"] == 9
    assert report["summary"]["orphaned_invoices"] == 1


def test_run_end_to_end_mock(golden_dir):
    """一键运行冒烟：mock 全链跑通，报告契约完整。"""
    report = run("mock", mock_dir=golden_dir)
    assert report["scenario"] == "FI2"
    assert report["automation_level"] == "L3"
    assert "未过账" in report["disclaimer"]
    assert len(report["items"]) == 10
