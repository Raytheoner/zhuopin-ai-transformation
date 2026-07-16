from aibot_service.whitelist import (
    WHITELISTED_SENDER_USERIDS,
    NOT_ONBOARDED_REPLY,
    is_whitelisted,
)


def test_whitelist_contains_exactly_five_confirmed_userids():
    """Paul 2026-07-16 口头确认：陈承/陈忱/唐燕萍/姚祖怡/王泓钦五人。"""
    assert WHITELISTED_SENDER_USERIDS == {
        "2023458",
        "ChenChen",
        "tangyanping",
        "YaoZuYi",
        "Hongqin.Wang",
    }


def test_is_whitelisted_true_for_each_member():
    for userid in WHITELISTED_SENDER_USERIDS:
        assert is_whitelisted(userid) is True


def test_is_whitelisted_false_for_unknown_sender():
    assert is_whitelisted("ShaoPeiShen") is False
    assert is_whitelisted("random_colleague") is False
    assert is_whitelisted("") is False


def test_is_whitelisted_does_not_fuzzy_match():
    """fail-closed：不做子串/模糊匹配，只做精确 userid 命中。"""
    assert is_whitelisted("YaoZuYi（临时代理）") is False


def test_not_onboarded_reply_is_nonempty_text():
    assert isinstance(NOT_ONBOARDED_REPLY, str)
    assert NOT_ONBOARDED_REPLY.strip() != ""
