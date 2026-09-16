"""本机 outbox 直连适配器（队列 `#595`）——让一次性提醒脚本不再各自
`AibotConnector(...).connect()`，改为把消息写进本机 outbox，由常驻服务
已经握着的那条连接（`outbox_relay.run_outbox_relay`）代发。

**成因**：`#586` 取证实锤——`decision_reminder_check.py` 每次运行各自新开
一条独立 `AibotConnector`（同 BotID），与常驻监听「单实例约束」互相踢线，
09-16 当天 08:18／09:18／13:19／15:19 四次同型 `disconnected`，均落在该
脚本每小时 `:18` 那次调用后约 1 分钟。`outbox_relay.py`（队列 `#394`）已经
为 SC2/FI2 建好"落盘轮询、零新增连接"的范式——本模块把同一范式挪到
**同机**场景：不必跨机文件通路，直接写本机一份 JSONL，常驻服务的中继
后台任务原地起效。

**接口形状故意贴 `AibotConnector`**：只暴露 `async send_markdown(recipient,
text)` 与 `disconnect()` 两个方法——`decision_reminder.send_decision_reminder`／
`open_pool_reminder.send_open_pool_reminder` 都只调这两个方法，本适配器可
原地替换 `AibotConnector` 实例，**零改动**那两个既有函数与它们的既有单测。

🔴 **主服务不在线时必须 fail-loud，不得回退为自行建连**（队列 `#595` 行内
硬要求）：`send_markdown` 先核一次存活戳（`liveness.read_liveness`）——过期
或缺失即抛 `MainServiceUnavailableError`，**不写 outbox、不新开连接**。
调用方（`send_decision_reminder` 等）捕获该异常后走既有 webhook 兜底通道
（`fallback_send`，独立于本服务这条长连接），这正是"不回退为自行建连"
与"仍有一条送达路径"两条要求的交点。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from zhuopin_platform.audit import AuditEvent, AuditLogger

from .liveness import read_liveness
from .outbox_relay import CHANNEL_DIRECT

# 常驻服务每 5 分钟覆写一次存活戳（见 `liveness.DEFAULT_LIVENESS_INTERVAL_
# SECONDS`）；取 3 倍留够抖动余量（进程刚重启/短暂断连重连期间不误判），
# 同时仍远小于提醒脚本的调用间隔（最密集为逐小时），不会把"服务其实活着
# 只是心跳还没到点"误判成"服务不在线"。
DEFAULT_LIVENESS_FRESHNESS_SECONDS = 900  # 15 分钟

LOCAL_REMINDER_OUTBOX_REL = Path("reports") / "local_reminder_outbox.jsonl"


class MainServiceUnavailableError(RuntimeError):
    """常驻服务存活戳过期或缺失——本模块拒绝写 outbox（写了也没人代发）。"""


def resolve_local_outbox_path(service_dir: Path) -> Path:
    return service_dir / LOCAL_REMINDER_OUTBOX_REL


def ensure_local_outbox_exists(path: Path) -> None:
    """确保本机 outbox 文件存在——`outbox_relay.iter_pending` 把"文件不存在"
    读作跨机通路断了那一类硬故障（`OutboxReadError`），而本机 outbox 在
    "从未有过一条提醒"时天然不存在；服务启动时先 touch 一次，此后写侧
    （`append`）与常驻中继（读）均只需假设"文件恒在"。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()


@dataclass
class LocalOutboxConnector:
    """伪 connector：`send_markdown` 落盘到本机 outbox，`disconnect()` 空转
    （兼容既有 `try: ... finally: connector.disconnect()` 调用点）。"""

    outbox_path: Path
    liveness_path: Path
    audit: AuditLogger
    scenario: str
    evaluator: str = "system"
    freshness_seconds: float = DEFAULT_LIVENESS_FRESHNESS_SECONDS

    async def send_markdown(self, recipient: str, text: str) -> dict:
        now = datetime.now(timezone.utc)
        last_alive_at = read_liveness(self.liveness_path)
        if last_alive_at is None or (now - last_alive_at).total_seconds() > self.freshness_seconds:
            self.audit.record(AuditEvent(
                scenario="wecom-aibot", action="local_outbox_submit_service_down",
                evaluator=self.evaluator, automation_level="L1",
                decision={"sent": False, "recipient": recipient, "scenario": self.scenario},
                data_sources={
                    "outbox_path": str(self.outbox_path),
                    "liveness_path": str(self.liveness_path),
                    "last_alive_at": last_alive_at.isoformat() if last_alive_at else None,
                },
            ))
            raise MainServiceUnavailableError(
                f"主服务存活戳过期或缺失（{self.liveness_path}）——拒绝写入本机 "
                "outbox，不回退为自行新开连接（队列 #595）。"
            )

        record = {
            "channel": CHANNEL_DIRECT,
            "to_userid": recipient,
            "msgtype": "markdown",
            "text": text,
            "scenario": self.scenario,
            "submitted_at": now.isoformat(timespec="seconds"),
        }
        self.outbox_path.parent.mkdir(parents=True, exist_ok=True)
        with self.outbox_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

        self.audit.record(AuditEvent(
            scenario="wecom-aibot", action="local_outbox_submit_queued",
            evaluator=self.evaluator, automation_level="L1",
            decision={"sent": True, "recipient": recipient, "channel": "local_outbox"},
            data_sources={"outbox_path": str(self.outbox_path), "scenario": self.scenario},
        ))
        return {"queued": True}

    def disconnect(self) -> None:
        """无网络连接可断——本适配器不持有任何连接。"""
        return None
