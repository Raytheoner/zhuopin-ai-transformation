"""文件型待审批队列（design D5 + 幂等关键项）。

实现平台 `PendingApprovalSink` 接口（Blocker2 钩子）：被 L2 门禁拦截的对客草稿落
`data/pending_approvals.jsonl`（append + 状态字段），责任人可读、可二次放行。

幂等（关键，design D5 补充）：`approve(id, confirmed_by)` → `Notifier.send` 成功后，
队列项**原子标记 'sent'**；重复点确认/重试 → 直接返回，**绝不重复外发客户**。
写操作复用平台 JsonlSink 同款 per-file 互斥锁；状态翻转用临时文件 + os.replace 原子替换。
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from zhuopin_platform.audit import AuditEvent, AuditLogger
from zhuopin_platform.shared_tools.crm_notifier.contracts import NotificationMessage
from zhuopin_platform.shared_tools.notifiers.dispatch import Notifier

from . import config

STATUS_PENDING = "pending"
STATUS_SENT = "sent"


@dataclass
class _QueuedMessage:
    """从队列记录重建的通知消息（满足 NotificationMessage Protocol，供 Notifier 复发）。"""
    recipient:             str
    title:                 str
    body:                  str
    severity:              str
    requires_confirmation: bool


class FilePendingQueue:
    """文件型 L2 待审批队列（实现平台 PendingApprovalSink.enqueue + 审批放行）。"""

    # 同一进程对同一文件共享一把锁（与平台 JsonlSink 同款，串行化读改写）
    _locks: dict[str, threading.Lock] = {}
    _locks_guard = threading.Lock()

    def __init__(self, path: Path | str):
        self.path = Path(path)
        key = str(self.path.resolve())
        with FilePendingQueue._locks_guard:
            self._lock = FilePendingQueue._locks.setdefault(key, threading.Lock())

    # ── PendingApprovalSink 接口 ──────────────────────────────────────────────
    def enqueue(self, message: NotificationMessage, reason: str = "") -> str:
        """把被拦截的高风险草稿入队（持久化 pending），返回队列项 id。"""
        item_id = uuid.uuid4().hex
        record = {
            "id": item_id,
            "status": STATUS_PENDING,
            "reason": reason,
            "recipient": getattr(message, "recipient", ""),
            "title": getattr(message, "title", ""),
            "body": getattr(message, "body", ""),
            "severity": getattr(message, "severity", None),
            "requires_confirmation": getattr(message, "requires_confirmation", None),
            # B3：所需审批级别（vp/l2，由 SC8 入队前标在草稿上；缺省 l2）
            "required_level": getattr(message, "required_level", config.LEVEL_L2),
            "confirmed_by": "",
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "sent_at": "",
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False) + "\n"
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line)
        return item_id

    # ── 审批放行（幂等）────────────────────────────────────────────────────────
    def approve(self, item_id: str, confirmed_by: str, notifier: Notifier,
                audit: AuditLogger | None = None,
                override_reason: str = "") -> bool:
        """L2 责任人放行：触发外发并原子标记 'sent'。

        幂等保证：整段 read→send→mark 在锁内串行；项已是 'sent' → 直接返回 True，
        **不再调用 notifier.send**（绝不重复外发客户）。

        B3 审批授权分级：项 `required_level=="vp"` 且 confirmed_by 不在 VP 白名单 →
        拒绝放行（返回 False、保持 pending、写 approval_denied_insufficient_level 审计）。

        Args:
            override_reason: L2 改判原因自由文本（判例采集器，写入 audit decision；空字符串时不填）。

        Returns:
            True  外发成功（或此前已外发，幂等返回 True）；
            False 项不存在 / 被门禁拦截（confirmed_by 为空 / 级别不足 / 总开关关闭）。
        """
        if not confirmed_by:
            return False  # 无确认人 → 不放行（与平台 Notifier fail-closed 一致）

        with self._lock:
            records = self._read_all_unlocked()
            idx = next((i for i, r in enumerate(records) if r.get("id") == item_id), None)
            if idx is None:
                return False
            item = records[idx]

            # 幂等：已外发 → 不重复发，直接返回成功
            if item.get("status") == STATUS_SENT:
                return True

            # B3：审批授权分级校验（VP 级项须 VP 白名单确认人）
            required_level = item.get("required_level", config.LEVEL_L2)
            if not config.approver_meets_level(confirmed_by, required_level):
                if audit is not None:
                    audit.record(AuditEvent(
                        scenario="SC8",
                        action="approval_denied_insufficient_level",
                        evaluator=confirmed_by,
                        automation_level="L2",
                        decision={
                            "queue_item_id": item_id,
                            "recipient": item.get("recipient", ""),
                            "required_level": required_level,
                            "confirmed_by": confirmed_by,
                        },
                    ))
                return False  # 级别不足 → 不放行，保持 pending

            # 复发原草稿（Notifier 仍执行 L2 判定；带 confirmed_by 放行）
            msg = _QueuedMessage(
                recipient=item.get("recipient", ""),
                title=item.get("title", ""),
                body=item.get("body", ""),
                severity=item.get("severity") or "warning",
                requires_confirmation=bool(item.get("requires_confirmation", True)),
            )
            sent = notifier.send(msg, confirmed_by=confirmed_by)
            if not sent:
                return False  # 仍被拦截（异常）→ 不标记，保持 pending

            # 原子标记 'sent'（成功后才翻转，重复 approve 命中上面的幂等分支）
            item["status"] = STATUS_SENT
            item["confirmed_by"] = confirmed_by
            item["sent_at"] = datetime.now(tz=timezone.utc).isoformat()
            records[idx] = item
            self._rewrite_all_unlocked(records)

            if audit is not None:
                decision = {
                    "queue_item_id": item_id,
                    "recipient": item.get("recipient", ""),
                    "confirmed_by": confirmed_by,
                }
                if override_reason:
                    decision["override_reason"] = override_reason
                audit.record(AuditEvent(
                    scenario="SC8",
                    action="approve_sent",
                    evaluator=confirmed_by,
                    automation_level="L2",
                    decision=decision,
                    override_reason=override_reason,
                ))
            return True

    # ── 读 / 查询 ─────────────────────────────────────────────────────────────
    def list_pending(self) -> list[dict]:
        with self._lock:
            return [r for r in self._read_all_unlocked() if r.get("status") == STATUS_PENDING]

    def get(self, item_id: str) -> dict | None:
        with self._lock:
            return next((r for r in self._read_all_unlocked() if r.get("id") == item_id), None)

    # ── 内部（须在持锁状态调用）────────────────────────────────────────────────
    def _read_all_unlocked(self) -> list[dict]:
        if not self.path.exists():
            return []
        out: list[dict] = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out

    def _rewrite_all_unlocked(self, records: list[dict]) -> None:
        """临时文件 + os.replace 原子替换整个队列文件（状态翻转用）。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(tmp, self.path)
