"""黄金基准回归（合成）—— 匹配引擎 + 分类结果 + 价格校验零偏差（design D9/D12/D13/D14，
spec: fi2-match-engine/fi2-result-classify/fi2-price-check/fi2-recon-report，
v3 口径修正 2026-07-09 + R1/R5/R7 真值落地 2026-07-10）。

样本覆盖五类判定 + 明细错位正反例 + AP-PO 价格超差/未超差 + 孤立发票（详见 data/golden
四表）。合成 golden 可入库；真实小样本待 9 月数据闸接通后另行提交变更包补齐（design 晋档 2）。

⚠️ 用例来源（design D13）：CC 按 v3 定稿文档自拟 strawman，唐燕萍 R1-R7 规则草案已交付
（队列 #14，2026-07-10），本次已按定稿真值回归更新（AP-1010 因 R5 门禁降级为 L2 自行
消化），但 strawman 用例本身仍待唐燕萍团队批改，不代表已经过专家批改定稿。
"""
from __future__ import annotations

from fi2.run import run

EXPECTED = {
    ("AP-1000", "A001"): dict(classification="完全匹配", needs_review=False, status="l3_suggested_pass", price_check_failed=False),
    # AP-1010 未税金额 +0.3（金额微差），整单差异总额 0.3 ≤ R5 门禁线 ¥1 → L2 自行消化，不转人工
    ("AP-1010", "A001"): dict(classification="金额微差", needs_review=False, status="l2_self_resolved", price_check_failed=False),
    ("AP-2000", "B001"): dict(classification="明细错位", needs_review=True, status="needs_review", price_check_failed=False),
    ("AP-2000", "B002"): dict(classification="明细错位", needs_review=True, status="needs_review", price_check_failed=False),
    ("AP-3000", "C001"): dict(classification="数量金额不符", needs_review=True, status="needs_review", price_check_failed=False),
    ("AP-4000", "D001"): dict(classification="数量金额不符", needs_review=True, status="needs_review", price_check_failed=False),
    ("AP-4000", "D002"): dict(classification="数量金额不符", needs_review=True, status="needs_review", price_check_failed=False),
    ("AP-5000", "E001"): dict(classification="无发票支撑", needs_review=True, status="needs_review", price_check_failed=False),
    ("AP-6000", "F001"): dict(classification="数量金额不符", needs_review=True, status="needs_review", price_check_failed=False),
    ("AP-8000", "H001"): dict(classification="完全匹配", needs_review=True, status="needs_review", price_check_failed=True),
    ("AP-9000", "J001"): dict(classification="完全匹配", needs_review=False, status="l3_suggested_pass", price_check_failed=False),
}


def test_golden_zero_deviation(golden_dir):
    report = run("mock", mock_dir=golden_dir)
    items = {(it["ap_no"], it["item_code"]): it for it in report["items"]}

    assert set(items) == set(EXPECTED), "匹配结果料品集合与黄金样本不符"
    for key, expected in EXPECTED.items():
        got = items[key]
        for field, want in expected.items():
            assert got[field] == want, (
                f"{key}.{field}: 期望 {want!r} 实得 {got[field]!r}（黄金回归零偏差被破坏）"
            )

    assert report["summary"]["total"] == 11
    assert report["summary"]["l3_suggested_pass"] == 2
    assert report["summary"]["l2_self_resolved"] == 1
    assert report["summary"]["needs_review"] == 8
    assert report["summary"]["orphaned_invoices"] == 1
    assert report["summary"]["price_check_alerts"] == 1


def test_run_end_to_end_mock(golden_dir):
    """一键运行冒烟：mock 全链跑通，报告契约完整。"""
    report = run("mock", mock_dir=golden_dir)
    assert report["scenario"] == "FI2"
    assert report["automation_level"] == "L3"
    assert "未过账" in report["disclaimer"]
    assert len(report["items"]) == 11
