"""队列 #193：断连"进行中"提示单测。"""
from __future__ import annotations

import asyncio

from aibot_service.disconnect_inprogress_alert import (
    DEFAULT_THRESHOLD_SECONDS,
    DisconnectInProgressMonitor,
    compute_next_retry_delay_seconds,
)


# ── compute_next_retry_delay_seconds：复现 SDK 指数退避公式 ─────────────────

def test_compute_next_retry_delay_matches_sdk_exponential_backoff():
    # delay_ms = min(base * 2**(attempt-1), 30000)；base=2000ms
    assert compute_next_retry_delay_seconds(1, 2000) == 2.0
    assert compute_next_retry_delay_seconds(2, 2000) == 4.0
    assert compute_next_retry_delay_seconds(3, 2000) == 8.0
    assert compute_next_retry_delay_seconds(4, 2000) == 16.0


def test_compute_next_retry_delay_capped_at_sdk_max():
    # attempt=5: 2000*16=32000ms，应封顶在 30000ms=30s（SDK `_reconnect_max_delay`）
    assert compute_next_retry_delay_seconds(5, 2000) == 30.0
    assert compute_next_retry_delay_seconds(10, 2000) == 30.0


def test_compute_next_retry_delay_attempt_below_one_treated_as_one():
    assert compute_next_retry_delay_seconds(0, 2000) == compute_next_retry_delay_seconds(1, 2000)


# ── DisconnectInProgressMonitor：断连生命周期状态机 ─────────────────────────

async def _immediate_sleep(_seconds: float) -> None:
    """模拟"阈值已到"——立即返回，不真实等待，供确定性测试断言。"""
    return


def test_threshold_reached_sends_alert_with_retry_count_and_next_delay():
    sent: list[str] = []

    async def scenario():
        monitor = DisconnectInProgressMonitor(
            fallback_send=sent.append, _sleep=_immediate_sleep, reconnect_base_delay_ms=2000,
        )
        monitor.on_disconnected()
        monitor.on_reconnecting(2)
        await monitor._task  # 等计时任务跑完（_immediate_sleep 不真实阻塞）

    asyncio.run(scenario())

    assert len(sent) == 1
    assert "已重试 2 次" in sent[0]
    # 下次重试是第 3 次尝试：min(2000*2**2, 30000)/1000 = 8 秒
    assert "8 秒" in sent[0]


def test_no_reconnecting_event_reports_zero_retries():
    sent: list[str] = []

    async def scenario():
        monitor = DisconnectInProgressMonitor(fallback_send=sent.append, _sleep=_immediate_sleep)
        monitor.on_disconnected()
        await monitor._task

    asyncio.run(scenario())

    assert len(sent) == 1
    assert "已重试 0 次" in sent[0]


def test_recovered_before_threshold_cancels_pending_alert():
    sent: list[str] = []

    async def _never_wakes_naturally(_seconds: float) -> None:
        await asyncio.sleep(1000)  # 只会被 on_recovered 的 cancel 打断，不会自然醒来

    async def scenario():
        monitor = DisconnectInProgressMonitor(fallback_send=sent.append, _sleep=_never_wakes_naturally)
        monitor.on_disconnected()
        await asyncio.sleep(0)  # 让计时任务真正启动、进入 sleep
        monitor.on_recovered()
        await asyncio.sleep(0)  # 让取消传播完成

    asyncio.run(scenario())

    assert sent == []


def test_fallback_send_none_does_not_raise():
    async def scenario():
        monitor = DisconnectInProgressMonitor(fallback_send=None, _sleep=_immediate_sleep)
        monitor.on_disconnected()
        await monitor._task

    asyncio.run(scenario())  # 不抛异常即通过


def test_fallback_send_failure_is_swallowed():
    def _boom(_text: str) -> None:
        raise RuntimeError("webhook 挂了")

    async def scenario():
        monitor = DisconnectInProgressMonitor(fallback_send=_boom, _sleep=_immediate_sleep)
        monitor.on_disconnected()
        await monitor._task

    asyncio.run(scenario())  # 不向上抛出即通过——提示失败不应影响服务本身运行


def test_second_disconnect_without_recovery_does_not_restart_timer():
    """理论上不该重复触发（SDK 一次真实断连只应回调一次 on_disconnected）
    ——防御性判断：已有计时任务在跑时不重复启动新任务。"""

    async def _long_sleep(_seconds: float) -> None:
        await asyncio.sleep(1000)

    async def scenario():
        monitor = DisconnectInProgressMonitor(fallback_send=lambda t: None, _sleep=_long_sleep)
        monitor.on_disconnected()
        first_task = monitor._task
        await asyncio.sleep(0)
        monitor.on_disconnected()  # 重复触发（防御性场景）
        assert monitor._task is first_task, "不应重复创建新计时任务"
        monitor.on_recovered()  # 收尾，避免任务悬空触发 pytest 警告
        await asyncio.sleep(0)

    asyncio.run(scenario())


def test_new_disconnect_after_recovery_starts_a_fresh_timer():
    """恢复后的下一次断连应重新计一次"新增"——去重状态随 on_recovered 重置。"""
    sent: list[str] = []

    async def scenario():
        monitor = DisconnectInProgressMonitor(fallback_send=sent.append, _sleep=_immediate_sleep)
        monitor.on_disconnected()
        await monitor._task
        monitor.on_recovered()

        monitor.on_reconnecting(5)  # 上一次断连的重试计数不应残留
        monitor.on_disconnected()
        await monitor._task

    asyncio.run(scenario())

    assert len(sent) == 2
    assert "已重试 0 次" in sent[1], "新一次断连应重新从 0 次计起，不沿用上一次的重试计数"


def test_default_threshold_is_within_60_to_90_seconds_range():
    assert 60 <= DEFAULT_THRESHOLD_SECONDS <= 90
