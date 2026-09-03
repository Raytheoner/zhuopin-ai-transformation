"""FI5 骨架冒烟测试。

本文件不测业务逻辑（引擎未实现，design 审未过）。它守两件事：
  ⑴ 路径引导可用 —— 平台底座与场景包在本 worktree 内可被正确 import；
  ⑵ 🔴 **未签认判据没有被人悄悄填上默认数** —— 这是本文件的真正用途。
     判据一旦被填了「看起来合理」的数就会静默生效、不报错、不产生任何信号；
     用例 `test_unsigned_criteria_stay_none` 就是把那个「不产生信号」变成一条红。
"""
from __future__ import annotations

import pytest

from fi5_expense_audit import config, models


def test_platform_bootstrap_importable():
    """平台底座可 import（路径引导 stub 生效）。"""
    from zhuopin_platform import bootstrap  # noqa: F401
    from zhuopin_platform.audit import AuditLogger  # noqa: F401


@pytest.mark.parametrize(
    "name",
    [
        "TRAVEL_STANDARD_TABLE",
        "ENTERTAINMENT_LIMIT_TABLE",
        "L2_BUDGET_BLOCK_PCT",
        "RISK_GRADE_BOUNDARIES",
    ],
)
def test_unsigned_criteria_stay_none(name):
    """🔴 四项判据须财务侧签认，未签认前**一律为 None**，不得有默认值。

    改这条用例之前请先读 `config.py` 首部：填数 = 替财务部做判断。
    签认到位的正确做法是「财务侧签认落档 → 改 config → 升 RULE_VERSION → 同步改本用例」，
    三步齐了才动，缺一步都不要动。
    """
    assert getattr(config, name) is None, (
        f"{name} 已被填值，但本场景判据尚无财务侧签认记录；"
        f"若已签认，请连同 RULE_VERSION 升版与签认落档一并提交"
    )


def test_rule_version_marked_unsigned():
    """规则版本号须自陈「未签认」，防止骨架被误当已定稿引用。"""
    assert "unsigned" in config.RULE_VERSION


def test_audit_finding_defaults_to_manual_review(simple_lines):
    """🔴 L2 默认侧：未经判据证成一律 needs_manual_review=True（根 CLAUDE.md §7-4）。"""
    finding = models.AuditFinding(claim_id=simple_lines[0].claim_id, line_no=1)
    assert finding.needs_manual_review is True


def test_budget_remaining(simple_budget):
    """`BudgetBalance.remaining` 是纯派生量，不含任何判据，可在骨架期即测。"""
    assert simple_budget[0].remaining == pytest.approx(1500.0)
    assert simple_budget[1].remaining == pytest.approx(200.0)
