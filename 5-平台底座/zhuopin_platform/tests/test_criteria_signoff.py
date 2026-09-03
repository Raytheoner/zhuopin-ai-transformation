"""`criteria_signoff` 单测。

本文件的重心是**反例**：把「未签认判据被静默读成 None」这件不报错的事，变成一条红。

按 opener 要求，`test_guard_is_load_bearing` 一节专门证明这些反例用例**是靠守卫成立的**
——把守卫关掉（用一个绕过 `.value` 保护的子类），同一条断言立刻失败。没有这一节，
「守卫在守什么」就只是口头声称。
"""
from __future__ import annotations

import dataclasses
import inspect

import pytest

from zhuopin_platform.criteria_signoff import (
    UNSIGNED_VERSION_TAG,
    CriteriaRegistry,
    CriteriaSignoffError,
    Criterion,
    CriterionContractError,
    CriterionNotSignedOffError,
    Signoff,
    UnknownCriterionError,
)


# ── 夹具 ────────────────────────────────────────────────────────────────────
@pytest.fixture
def unsigned_criterion() -> Criterion:
    return Criterion(
        key="L2_BUDGET_BLOCK_PCT",
        question="占用预算余额超过百分之几即拦截并通知上级",
        owner="财务侧",
        note="须随《报销政策判据表》一并签认",
    )


@pytest.fixture
def valid_signoff() -> Signoff:
    return Signoff(
        signed_by="某某某",
        signed_on="2026-10-11",
        evidence="3-治理与合规/报销政策判据表-2026-10-11.md",
        rule_version="demo-signed-2026-10-11",
    )


@pytest.fixture
def registry(unsigned_criterion: Criterion) -> CriteriaRegistry:
    return CriteriaRegistry(
        "FI-DEMO",
        [
            unsigned_criterion,
            Criterion(key="RISK_GRADE_BOUNDARIES", question="风险分级的边界怎么划", owner="财务侧"),
        ],
    )


# ══ ① 核心反例：读未签认判据必须抛 ═══════════════════════════════════════════
def test_reading_unsigned_criterion_raises(unsigned_criterion: Criterion):
    """🔴 本模块的全部理由都在这一条：读未签认判据**抛**，不返回 None。"""
    with pytest.raises(CriterionNotSignedOffError):
        _ = unsigned_criterion.value


def test_reading_unsigned_via_registry_raises(registry: CriteriaRegistry):
    """经注册表读也一样抛——多一层间接不等于多一条旁路。"""
    with pytest.raises(CriterionNotSignedOffError):
        registry.value_of("L2_BUDGET_BLOCK_PCT")


def test_unsigned_error_message_says_who_should_sign(unsigned_criterion: Criterion):
    """异常信息须让人当场知道「谁该签、签的是什么」，否则只是又一条看不懂的报错。"""
    with pytest.raises(CriterionNotSignedOffError) as ei:
        _ = unsigned_criterion.value
    msg = str(ei.value)
    assert "财务侧" in msg
    assert "占用预算余额" in msg
    assert "须随《报销政策判据表》一并签认" in msg


def test_raw_value_of_unsigned_is_none(unsigned_criterion: Criterion):
    """未签认时存的确实是 None（这条守的是「一律为 None」那半句）。"""
    assert unsigned_criterion.raw_value is None
    assert unsigned_criterion.is_signed is False


def test_unknown_key_raises_not_returns_none(registry: CriteriaRegistry):
    """拼错 key 必须炸。静默返回 None 会让「拼错了」伪装成「还没签认」。"""
    with pytest.raises(UnknownCriterionError):
        registry.value_of("L2_BUDGET_BLOCK_PCTT")


def test_unknown_criterion_is_not_a_key_error(registry: CriteriaRegistry):
    """`UnknownCriterionError` 刻意不继承 KeyError——KeyError 太容易被顺手吞掉。"""
    with pytest.raises(CriteriaSignoffError):
        registry.criterion("不存在")
    assert not issubclass(UnknownCriterionError, KeyError)


# ══ ② 「给个默认值」的旁路一律不存在 ═════════════════════════════════════════
def test_no_default_bypass_in_public_api():
    """🔴 读值路径上**不得出现任何带默认值的形参**，也不得有 *args/**kwargs 兜底。

    有 `default` 就等于有旁路：一行 `value_of(k, default=0)` 能让本模块的全部保护归零。
    `Criterion.value` 是 property（天生传不了参），`CriteriaRegistry.value_of` 由本条盯住。
    """
    sig = inspect.signature(CriteriaRegistry.value_of)
    params = list(sig.parameters.values())
    assert [p.name for p in params] == ["self", "key"], (
        f"value_of 的签名变成了 {sig}——多出来的形参若带默认值即是旁路"
    )
    for p in params:
        assert p.default is inspect.Parameter.empty
        assert p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)


def test_criterion_value_is_a_property_not_a_callable():
    """`.value` 必须是属性而非方法——方法迟早会被人加上 `default=` 参数。"""
    assert isinstance(inspect.getattr_static(Criterion, "value"), property)


@pytest.mark.parametrize("banned", ["get", "get_or_none", "value_or", "fetch", "lookup"])
def test_registry_has_no_softening_aliases(banned: str):
    """禁止出现「宽松版读值」的别名——换个名字的旁路仍然是旁路。"""
    assert not hasattr(CriteriaRegistry, banned)


def test_registry_has_no_getattr_fallback(registry: CriteriaRegistry):
    """注册表不得有 `__getattr__` 容错回退（那是拼错 key 的静默通道）。"""
    assert "__getattr__" not in vars(CriteriaRegistry)
    with pytest.raises(AttributeError):
        _ = registry.随便一个不存在的属性  # noqa: B018


# ══ ③ 不变式：不许「填了数没人签」，也不许「签了没值」 ═══════════════════════
def test_value_without_signoff_is_rejected_at_construction():
    """🔴 填了数却没有签认记录 ⇒ 构造期即抛。

    这是五份本地实现都**没有**堵上的洞：它们只断言 `is None`，
    所以「填了个数、同时把那条 assert 也改了」两步就能悄悄放行。
    这里把它变成数据结构层面的不可能。
    """
    with pytest.raises(CriterionContractError) as ei:
        Criterion(key="X", question="定个什么", owner="财务侧", raw_value=0.9)
    assert "没有签认记录" in str(ei.value)


def test_signoff_without_value_is_rejected(valid_signoff: Signoff):
    """签认了却没有值 ＝ 空签，且会与「未签认」撞语义 ⇒ 抛。"""
    with pytest.raises(CriterionContractError) as ei:
        Criterion(key="X", question="定个什么", owner="财务侧", signoff=valid_signoff)
    assert "None 在本模块里唯一含义是「未签认」" in str(ei.value)


def test_signed_as_no_threshold_must_be_explicit(valid_signoff: Signoff, unsigned_criterion: Criterion):
    """结论是「不设阈值」时须签成显式值（False / {}），不得签成 None。"""
    c = unsigned_criterion.signed(False, valid_signoff)
    assert c.value is False          # 显式「不设限」，读得出来
    assert c.is_signed is True


@pytest.mark.parametrize("field", ["signed_by", "signed_on", "evidence", "rule_version"])
def test_signoff_fields_have_no_defaults(field: str):
    """🔴 四个字段全部必填、无默认值——给默认就等于允许漏填还能构造成功。"""
    defaults = {
        f.name for f in dataclasses.fields(Signoff) if f.default is not dataclasses.MISSING
    }
    assert field not in defaults


@pytest.mark.parametrize("bad", ["", "   ", "TBD", "待定", "n/a", "无"])
def test_signoff_rejects_placeholder_signer(bad: str):
    """空签认人与占位词一律拒——「TBD 签的」不是签认，是签认二字的 cosplay。"""
    with pytest.raises(CriterionContractError):
        Signoff(signed_by=bad, signed_on="2026-10-11", evidence="某文件.md", rule_version="v1")


def test_criterion_is_frozen(unsigned_criterion: Criterion):
    """判据不可变——没有 `c.raw_value = 0.9` 这条就地赋值的路。"""
    with pytest.raises(dataclasses.FrozenInstanceError):
        unsigned_criterion.raw_value = 0.9  # type: ignore[misc]


def test_signed_returns_new_object_and_leaves_original_unsigned(
    unsigned_criterion: Criterion, valid_signoff: Signoff
):
    """签认返回新对象；原对象仍未签认（状态跃迁留痕，不被运行期赋值抹掉）。"""
    signed = unsigned_criterion.signed(0.9, valid_signoff)
    assert signed.value == 0.9
    assert signed.signoff is valid_signoff
    assert unsigned_criterion.is_signed is False
    with pytest.raises(CriterionNotSignedOffError):
        _ = unsigned_criterion.value


def test_signed_requires_a_real_signoff_object(unsigned_criterion: Criterion):
    """不能拿一个字符串冒充签认记录。"""
    with pytest.raises(CriterionContractError):
        unsigned_criterion.signed(0.9, "某某某说可以")  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_field,bad_value", [("key", ""), ("question", "  "), ("owner", "TBD")])
def test_criterion_declaration_requires_real_text(bad_field: str, bad_value: str):
    """判据自身的三个必填文本字段不得为空或占位词。"""
    kwargs = {"key": "X", "question": "定个什么", "owner": "财务侧", bad_field: bad_value}
    with pytest.raises(CriterionContractError):
        Criterion(**kwargs)  # type: ignore[arg-type]


# ══ ④ 注册表：查缺、重复 key、版本一致性 ═════════════════════════════════════
def test_duplicate_key_is_rejected(unsigned_criterion: Criterion):
    """重复 key 会让后者静默盖掉前者——必有一条判据从此无人守。"""
    with pytest.raises(CriterionContractError) as ei:
        CriteriaRegistry("FI-DEMO", [unsigned_criterion, unsigned_criterion])
    assert "重复声明" in str(ei.value)


def test_unsigned_keys_lists_all_gaps(registry: CriteriaRegistry):
    assert registry.unsigned_keys() == ("L2_BUDGET_BLOCK_PCT", "RISK_GRADE_BOUNDARIES")
    assert registry.signed_keys() == ()
    assert registry.fully_signed is False


def test_require_all_signed_lists_every_gap_at_once(registry: CriteriaRegistry):
    """整体查缺须一次列全，不能报第一条就停（否则要修 N 轮才知道缺 N 条）。"""
    with pytest.raises(CriterionContractError) as ei:
        registry.require_all_signed()
    msg = str(ei.value)
    assert "L2_BUDGET_BLOCK_PCT" in msg
    assert "RISK_GRADE_BOUNDARIES" in msg
    assert "财务侧" in msg


def test_empty_registry_is_not_fully_signed():
    """🔴 空注册表不算「全签完了」——那是最坏的一种假绿灯。"""
    empty = CriteriaRegistry("FI-EMPTY", [])
    assert empty.fully_signed is False
    with pytest.raises(CriterionContractError) as ei:
        empty.require_all_signed()
    assert "不是一回事" in str(ei.value)


def test_fully_signed_registry_passes(valid_signoff: Signoff, registry: CriteriaRegistry):
    signed_all = CriteriaRegistry(
        registry.scenario,
        [c.signed(1, valid_signoff) for c in registry],
    )
    assert signed_all.fully_signed is True
    signed_all.require_all_signed()  # 不抛即通过
    assert signed_all.value_of("L2_BUDGET_BLOCK_PCT") == 1


def test_rule_version_must_declare_unsigned_while_gaps_remain(registry: CriteriaRegistry):
    """尚有未签认判据时，版本号不自陈 `unsigned` ⇒ 抛（收拢五份场景各写一遍的那条 assert）。"""
    registry.assert_rule_version("fi-demo-skeleton-unsigned-2026-09-03")  # 不抛
    with pytest.raises(CriterionContractError) as ei:
        registry.assert_rule_version("fi-demo-v1.0")
    assert UNSIGNED_VERSION_TAG in str(ei.value)


def test_rule_version_must_drop_unsigned_tag_once_all_signed(
    registry: CriteriaRegistry, valid_signoff: Signoff
):
    """反方向也查：全签完了还挂 `unsigned` ⇒ 版本号在撒谎。只查一半等于没查。"""
    signed_all = CriteriaRegistry(registry.scenario, [c.signed(1, valid_signoff) for c in registry])
    signed_all.assert_rule_version("fi-demo-signed-2026-10-11")  # 不抛
    with pytest.raises(CriterionContractError):
        signed_all.assert_rule_version("fi-demo-still-unsigned")


def test_registry_container_semantics(registry: CriteriaRegistry):
    assert len(registry) == 2
    assert "L2_BUDGET_BLOCK_PCT" in registry
    assert registry.keys() == ("L2_BUDGET_BLOCK_PCT", "RISK_GRADE_BOUNDARIES")
    assert registry.is_signed("RISK_GRADE_BOUNDARIES") is False
    assert registry.criterion("RISK_GRADE_BOUNDARIES").owner == "财务侧"


def test_registry_rejects_non_criterion_members():
    with pytest.raises(CriterionContractError):
        CriteriaRegistry("FI-DEMO", ["L2_BUDGET_BLOCK_PCT"])  # type: ignore[list-item]


def test_registry_requires_a_scenario():
    with pytest.raises(CriterionContractError):
        CriteriaRegistry("", [])


# ══ ⑤ 守卫是否真的在承重（关掉守卫 ⇒ 上面的反例即失败）═══════════════════════
class _GuardOffCriterion(Criterion):
    """把 `.value` 的 fail-loud 守卫关掉的子类 —— **仅供本测试用，业务代码不得出现**。

    它模拟的正是最可能发生的那次「顺手改一下」：有人嫌抛异常碍事，
    把 `value` 改成直接返回 `raw_value`。
    """

    @property
    def value(self):  # type: ignore[override]
        return self.raw_value


def test_guard_is_load_bearing():
    """🔴 证明上面那些反例用例**是靠守卫成立的**，不是碰巧通过。

    做法：拿一个「守卫已关掉」的子类跑同一条断言——它必须**失败**。
    若它反而通过了，说明守卫压根没在承重，那些绿灯全是假的。
    """
    guard_off = _GuardOffCriterion(key="X", question="定个什么", owner="财务侧")

    # 守卫关掉后，同一条断言不再成立：读未签认判据静默返回 None
    assert guard_off.value is None, "子类未能关掉守卫，本条元测试自身失效"

    with pytest.raises(pytest.fail.Exception):
        # 复刻 `test_reading_unsigned_criterion_raises` 的断言；守卫关掉 ⇒ 它必须报 DID NOT RAISE
        with pytest.raises(CriterionNotSignedOffError):
            _ = guard_off.value


def test_guard_off_also_breaks_the_registry_path():
    """注册表那条路径同理：守卫关掉后 `value_of` 也变成静默返回 None。"""
    reg = CriteriaRegistry("FI-DEMO", [_GuardOffCriterion(key="X", question="定个什么", owner="财务侧")])
    assert reg.value_of("X") is None
    with pytest.raises(pytest.fail.Exception):
        with pytest.raises(CriterionNotSignedOffError):
            reg.value_of("X")
