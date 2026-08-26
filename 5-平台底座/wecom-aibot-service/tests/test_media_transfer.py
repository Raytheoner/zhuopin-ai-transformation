"""队列 #416 ⑴：media 通道重试 + 可配超时。反例测试对旧实现（裸 await）变红。"""
from __future__ import annotations

import asyncio

import pytest

from zhuopin_platform.audit import AuditLogger

from aibot_service.media_transfer import (
    MediaTransferError,
    build_resend_notice,
    with_media_retry,
)


def _run(coro):
    return asyncio.run(coro)


async def _noop_sleep(_seconds: float) -> None:
    """把退避压成零耗时——测的是重试次序，不是真实等待。"""


def test_retries_until_success(tmp_path):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise asyncio.TimeoutError()   # 🔴 无参异常：str() 是空的
        return (b"ok", "a.docx")

    result = _run(with_media_retry(
        flaky, stage="download_inbound", audit=audit, sleep=_noop_sleep,
    ))

    assert result == (b"ok", "a.docx")
    assert calls["n"] == 3
    events = audit.query_by(scenario="wecom-aibot")
    retries = [e for e in events if e["action"] == "media_transfer_retry"]
    # 每一次失败单独留痕，且**类型名没有丢**（元缺陷 ⑵ 的同族要求）。
    assert len(retries) == 2
    assert [e["error"] for e in retries] == ["TimeoutError", "TimeoutError"]
    assert [e["decision"]["will_retry"] for e in retries] == [True, True]


def test_exhausted_retries_raise_media_transfer_error_not_silent(tmp_path):
    """🔴 不静默跳过：耗尽后**抛**，让上层能去请发件人重发。"""
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")

    async def always_timeout():
        raise asyncio.TimeoutError()

    with pytest.raises(MediaTransferError) as excinfo:
        _run(with_media_retry(
            always_timeout, stage="download_inbound", audit=audit,
            max_attempts=3, sleep=_noop_sleep,
        ))

    err = excinfo.value
    assert err.stage == "download_inbound"
    assert err.attempts == 3
    assert len(err.errors) == 3
    assert "TimeoutError" in str(err)
    last = [e for e in audit.query_by(scenario="wecom-aibot")
            if e["action"] == "media_transfer_retry"][-1]
    assert last["decision"]["will_retry"] is False


def test_timeout_is_configurable_and_enforced_by_this_layer():
    """本层超时**独立于 SDK 的 5.0s ack**——一个永不返回的操作必须被切断。"""
    async def never_returns():
        await asyncio.sleep(10)

    with pytest.raises(MediaTransferError):
        _run(with_media_retry(
            never_returns, stage="upload_forward",
            max_attempts=2, timeout_seconds=0.01, sleep=_noop_sleep,
        ))


def test_timeout_zero_disables_this_layer():
    """`timeout_seconds<=0` ＝ 摘掉本层超时（排查用），操作照常跑完。"""
    async def slow_but_finishes():
        await asyncio.sleep(0.02)
        return "done"

    assert _run(with_media_retry(
        slow_but_finishes, stage="download_inbound", timeout_seconds=0, sleep=_noop_sleep,
    )) == "done"


def test_cancellation_is_not_swallowed_as_a_retryable_failure():
    """取消不是失败——吞掉它服务就关不掉了。"""
    async def cancelled():
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        _run(with_media_retry(cancelled, stage="download_inbound", sleep=_noop_sleep))


def test_resend_notice_names_the_file_as_not_archived():
    text = build_resend_notice("tangyanping", MediaTransferError("download_inbound", 3, ["x"]))
    assert "tangyanping" in text
    assert "没有入档" in text
    assert "重新发一次" in text
