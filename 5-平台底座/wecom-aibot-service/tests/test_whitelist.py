from aibot_service.constants import PAUL_USERID
from aibot_service.whitelist import (
    WHITELISTED_SENDER_USERIDS,
    NOT_ONBOARDED_REPLY,
    is_whitelisted,
)


def test_whitelist_contains_five_specialists_plus_paul():
    """Paul 2026-07-16 口头确认五位专员；Paul 本人 2026-07-18 总线审计补入
    （此前不含 Paul 会导致他自己的 test 消息被误判为"未开通"）。"""
    assert WHITELISTED_SENDER_USERIDS == {
        "2023458",
        "ChenChen",
        "tangyanping",
        "YaoZuYi",
        "Hongqin.Wang",
        PAUL_USERID,
    }


def test_is_whitelisted_true_for_each_member():
    for userid in WHITELISTED_SENDER_USERIDS:
        assert is_whitelisted(userid) is True


def test_is_whitelisted_true_for_paul():
    assert is_whitelisted(PAUL_USERID) is True


def test_is_whitelisted_false_for_unknown_sender():
    assert is_whitelisted("random_colleague") is False
    assert is_whitelisted("") is False


def test_is_whitelisted_does_not_fuzzy_match():
    """fail-closed：不做子串/模糊匹配，只做精确 userid 命中。"""
    assert is_whitelisted("YaoZuYi（临时代理）") is False


def test_not_onboarded_reply_is_nonempty_text():
    assert isinstance(NOT_ONBOARDED_REPLY, str)
    assert NOT_ONBOARDED_REPLY.strip() != ""
