"""FI5 骨架冒烟测试。

本文件不测业务逻辑（引擎未实现，design 审未过）。它守三件事：
  ⑴ 路径引导可用 —— 平台底座与场景包在本 worktree 内可被正确 import；
  ⑵ 🔴 **未签认判据没有被人悄悄填上默认数** —— 这是本文件的真正用途。
     判据一旦被填了「看起来合理」的数就会静默生效、不报错、不产生任何信号；
     `test_criteria_registry_all_unsigned` 就是把那个「不产生信号」变成一条红。
  ⑶ 🔴 **G-5 反向依赖**：写审计的 `decision` 恒带当时生效的 `RULE_VERSION`。

📌 **2026-09-03 迁移**：⑵ 原为 `test_unsigned_criteria_stay_none`（断言 `config.X is None`）
＋ `test_rule_version_marked_unsigned`，两者与其余四个财务场景各手抄一份（5 > 3）。
现改为**断言底座注册表的状态**：未签认、且读取必抛。
🔴 **守的行为一处未变，只是断言对象从「模块常量是不是 None」变成「注册表这条签认了没有」**
—— 后者更硬：`None` 只是「碰巧没值」，而未签认是一个**读了就炸**的状态。
"""
from __future__ import annotations

import pytest

from zhuopin_platform.criteria_signoff import CriterionNotSignedOffError

from fi5_expense_audit import config, models


def test_platform_bootstrap_importable():
    """平台底座可 import（路径引导 stub 生效）。"""
    from zhuopin_platform import bootstrap  # noqa: F401
    from zhuopin_platform.audit import AuditLogger  # noqa: F401


# 本场景的四项待签认判据（顺序即注册表声明顺序）。
CRITERIA_KEYS = (
    "TRAVEL_STANDARD_TABLE",
    "ENTERTAINMENT_LIMIT_TABLE",
    "L2_BUDGET_BLOCK_PCT",
    "RISK_GRADE_BOUNDARIES",
)


def test_criteria_registry_declares_exactly_these():
    """🔴 四项判据一条不多、一条不少地登记在注册表里。

    少一条 ⇒ 那条判据从此无人守，且不会有任何信号；
    多一条 ⇒ 多半是有人把「权限缺口」「存在性未核实」这类**不靠签认解除**的东西
    顺手并了进来（`G-2 = (a)` 明令不许）。
    """
    assert config.CRITERIA.keys() == CRITERIA_KEYS


@pytest.mark.parametrize("key", CRITERIA_KEYS)
def test_criteria_registry_all_unsigned(key):
    """🔴 四项判据须财务侧签认，未签认前**读了就炸**，不得有默认值。

    改这条用例之前请先读 `config.py` 首部：填数 = 替财务部做判断。
    签认到位的正确做法是「财务侧签认落档 → `Criterion.signed(值, Signoff(...))`
    → 升 RULE_VERSION → 同步改本用例」，四步齐了才动，缺一步都不要动。
    """
    assert config.CRITERIA.is_signed(key) is False, (
        f"{key} 已被签认，但本场景尚无财务侧签认落档；"
        f"若确已签认，请连同 RULE_VERSION 升版与落档凭据一并提交"
    )
    with pytest.raises(CriterionNotSignedOffError):
        config.CRITERIA.value_of(key)


def test_rule_version_consistent_with_signoff_state():
    """规则版本号须自陈「未签认」，防止骨架被误当已定稿引用。

    `assert_rule_version` 在 `config.py` 导入期已跑过一遍；这里再跑一次，守的是
    **那一行本身别被删掉** —— 删了它，导入期的双向校验就没了，而删除不会有任何信号。
    """
    config.CRITERIA.assert_rule_version(config.RULE_VERSION)
    assert "unsigned" in config.RULE_VERSION


def test_audit_decision_carries_rule_version():
    """🔴 G-5 反向依赖：写审计的 `decision` 恒带当时生效的 `RULE_VERSION`。

    依赖方向是**审计日志指向判据版本**——判据底座不认识 audit，audit 记着用的哪版口径。
    这样每条 AI 决策的日志天然回答了「当时口径签完没有」（版本号自带 `unsigned` 标记）。
    """
    from zhuopin_platform.audit import AuditEvent

    event = AuditEvent(
        scenario="FI5", action="expense_audit", evaluator="示例复核人",
        automation_level="L2",
        decision=config.audit_decision(claim_id="EXP-2026-09-0001", risk_grade="待判"),
    )
    assert event.decision["rule_version"] == config.RULE_VERSION
    assert "unsigned" in event.decision["rule_version"]


def test_audit_finding_defaults_to_manual_review(simple_lines):
    """🔴 L2 默认侧：未经判据证成一律 needs_manual_review=True（根 CLAUDE.md §7-4）。"""
    finding = models.AuditFinding(claim_id=simple_lines[0].claim_id, line_no=1)
    assert finding.needs_manual_review is True


def test_budget_remaining(simple_budget):
    """`BudgetBalance.remaining` 是纯派生量，不含任何判据，可在骨架期即测。"""
    assert simple_budget[0].remaining == pytest.approx(1500.0)
    assert simple_budget[1].remaining == pytest.approx(200.0)
