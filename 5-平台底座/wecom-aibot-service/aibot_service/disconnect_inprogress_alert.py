"""企微连接断连期间"进行中"提示（队列 #193）。

背景：企微 SDK 断连后会在后台自动重连（指数退避 1s→2s→4s→…→上限 30s，
`aibot/ws.py::_schedule_reconnect`），此前用户在整个断连过程中收不到任何
信号——`gap_alert.py` 只在**重连成功后**才发一条"已恢复"通报。07-31 一次
真实断连约 6 分钟（期间 5 次 `connection_error`，SDK 一直在自愈），因缺乏
"正在自愈中"的信号，Shao Peishen 无法区分"正在自愈"与"已经死了"，触发了
一次不必要的手动关机（详见队列 #193 行内记录）。

`liveness.py` 心跳文件是 5 分钟粒度的**进程存活**信号（与连接状态无关，
见其模块 docstring），粒度上无法支撑 60~90 秒阈值判断——本模块复用其
"轻量、刻意不进审计链"的设计取向（这是运行时状态通知，不是 AI 决策，同
心跳一样不写审计事件），但触发信号改用 `connection.py` 已有的、精度以秒
计的连接生命周期回调（`on_disconnected`/`on_reconnecting`/`on_authenticated`），
比 5 分钟粒度的心跳文件更贴合 60~90 秒阈值的精度要求。

发送通道**必须是独立 webhook（`fallback_send`）**，不能是同一条故障连接
本身——断连期间用它发送必然失败（与 `gap_alert.py` 2026-07-19 事故同一
教训）。

队列 #586（2026-09-16）：**断连窗口丢信风险告警**——本模块原有的"进行中"
提示只在断连持续 ≥ `DEFAULT_THRESHOLD_SECONDS`（60~90s）时才发一条，且
`gap_alert.py::build_reconnect_notice` 只在**进程启动时的那一次**
`connector.connect()` 前后被调用一次，SDK 内部自愈式重连（`on_disconnected`
→`on_reconnecting`→`on_authenticated`，本模块正挂在这条回调链上）此后每次
恢复都**不会再触发任何通知**——07-31/09-16 两次真实事故（唐燕萍 13:19:11–
13:19:14 那 3 秒断连窗口）都短于阈值、也都发生在进程运行期而非启动时，
两条既有机制对它同时失效，本机制关不掉、无人知道那扇窗口存在过。
企微 aibot 协议**没有离线消息补推能力**（见 `gap_alert.py` 模块 docstring）
——不存在"重连成功后自动补拉"这条路；本模块改走**不管时长、每次恢复都
点名窗口起止**发一条告警（`loss_risk_fallback_send`，独立于既有
`fallback_send`/`DEFAULT_THRESHOLD_SECONDS` 判据，两者互不影响、互不
覆盖——`fallback_send` 仍只在超阈值时报"还在自愈"，本告警只在**任一次
断连结束时**报"这段窗口内的来信可能已经丢了，请人工核对"）。
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Callable, Optional

# 60~90 秒区间取中值——短于此判定为正常重连抖动，不必打扰；长于此才是
# 值得主动告知的"进行中"事件。
DEFAULT_THRESHOLD_SECONDS = 75.0

# 与 `aibot/ws.py::_schedule_reconnect` 的指数退避上限保持一致（该值 SDK
# 未对外暴露构造参数，只能按其已知实现独立复现——上游若变更需同步更新）。
RECONNECT_MAX_DELAY_SECONDS = 30.0


def compute_next_retry_delay_seconds(attempt: int, base_delay_ms: int) -> float:
    """复现 SDK 的指数退避公式：`delay = min(base_delay_ms * 2**(attempt-1),
    30000)`。`attempt` 语义与 `on_reconnecting(attempt)` 回调一致（从 1 起）。"""
    if attempt < 1:
        attempt = 1
    delay_ms = min(base_delay_ms * (2 ** (attempt - 1)), RECONNECT_MAX_DELAY_SECONDS * 1000)
    return delay_ms / 1000


class DisconnectInProgressMonitor:
    """监控一次断连的生命周期：断开时启动计时任务，持续超阈值发一次
    "进行中"提示；重新认证成功（恢复）时取消计时任务并重置状态，供下一次
    断连重新计一次"新增"——同一次断连只发一次，不重复轰炸（去重按 #172
    "新增才提醒"口径的最简形态：本次断连从未提示过即为新增）。"""

    def __init__(
        self,
        *,
        fallback_send: Optional[Callable[[str], None]] = None,
        threshold_seconds: float = DEFAULT_THRESHOLD_SECONDS,
        reconnect_base_delay_ms: int = 2000,
        _sleep: Callable[[float], "asyncio.Future"] = asyncio.sleep,
        loss_risk_fallback_send: Optional[Callable[[str], None]] = None,
        _now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._fallback_send = fallback_send
        self._threshold_seconds = threshold_seconds
        self._reconnect_base_delay_ms = reconnect_base_delay_ms
        self._sleep = _sleep
        self._task: Optional["asyncio.Task"] = None
        self._last_attempt = 0
        self._loss_risk_fallback_send = loss_risk_fallback_send
        self._now = _now
        self._disconnected_at: Optional[datetime] = None

    def on_disconnected(self) -> None:
        """断连发生——启动一次计时任务；若已有计时任务在跑（理论上不该
        重复触发，防御性判断）则不重复启动。"""
        self._last_attempt = 0
        if self._task is not None and not self._task.done():
            return
        self._disconnected_at = self._now()
        self._task = asyncio.create_task(self._wait_and_alert())

    def on_reconnecting(self, attempt: int) -> None:
        self._last_attempt = attempt

    def on_recovered(self) -> None:
        """重新认证成功——取消未触发的计时任务，重置去重状态，供下一次
        断连重新计一次"新增"。**同时**（队列 #586）不管这次断连长短，都
        发一条"窗口丢信风险"告警——与上面的计时任务是两件独立的事，取消
        计时任务不影响本告警是否发送。"""
        if self._task is not None:
            self._task.cancel()
            self._task = None
        self._emit_loss_risk_alert()

    def _emit_loss_risk_alert(self) -> None:
        started_at = self._disconnected_at
        self._disconnected_at = None
        if started_at is None or self._loss_risk_fallback_send is None:
            return
        ended_at = self._now()
        window = f"{started_at.strftime('%H:%M:%S')}–{ended_at.strftime('%H:%M:%S UTC')}"
        gap_seconds = (ended_at - started_at).total_seconds()
        text = (
            f"🔴 监听断连窗口 {window}（约 {gap_seconds:.0f} 秒）已结束并自动重连。"
            "企微没有离线消息补推能力，该窗口内若有人发来消息可能已丢失，请人工核对相关来源是否收到回应。"
        )
        try:
            self._loss_risk_fallback_send(text)
        except Exception:  # noqa: BLE001 —— 告警失败不应影响服务本身运行
            pass

    async def _wait_and_alert(self) -> None:
        try:
            await self._sleep(self._threshold_seconds)
        except asyncio.CancelledError:
            return  # 阈值内已恢复，不发送
        if self._fallback_send is None:
            return
        next_delay = compute_next_retry_delay_seconds(
            self._last_attempt + 1, self._reconnect_base_delay_ms
        )
        text = (
            f"⏳ 企微智能机器人监听断连中，已重试 {self._last_attempt} 次，"
            f"下次重连预计 {next_delay:.0f} 秒后——本条为进行中提示，非最终结果，"
            "恢复后会收到确认消息。"
        )
        try:
            self._fallback_send(text)
        except Exception:  # noqa: BLE001 —— 提示失败不应影响服务本身运行
            pass
