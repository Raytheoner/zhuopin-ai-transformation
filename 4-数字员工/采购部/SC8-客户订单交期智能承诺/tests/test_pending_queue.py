"""文件型待审批队列 + 幂等（design D5 关键项）。"""
from __future__ import annotations

from dataclasses import dataclass

from sc8.commitment import build_notifier
from sc8.pending_queue import STATUS_PENDING, STATUS_SENT


@dataclass
class _Msg:
    recipient: str = "比亚迪"
    title: str = "交付承诺"
    body: str = "正文"
    severity: str = "warning"
    requires_confirmation: bool = True


def test_enqueue_persists_pending(queue):
    item_id = queue.enqueue(_Msg(), reason="awaiting_L2_confirmation")
    rec = queue.get(item_id)
    assert rec["status"] == STATUS_PENDING
    assert rec["recipient"] == "比亚迪"
    assert len(queue.list_pending()) == 1


def test_approve_sends_once_then_idempotent(queue):
    sends: list[str] = []
    # A2：放行机制本身需总开关开启才真发（生产恒关，机制正确性单独验证）
    notifier = build_notifier(queue, audit=None, send_fn=lambda url, body: sends.append(body),
                              outbound_enabled=True)
    item_id = queue.enqueue(_Msg(body="承诺正文"), reason="awaiting_L2_confirmation")

    # 首次 approve → 外发一次，状态翻 'sent'
    assert queue.approve(item_id, confirmed_by="Paul", notifier=notifier) is True
    assert sends == ["承诺正文"]
    assert queue.get(item_id)["status"] == STATUS_SENT
    assert queue.get(item_id)["confirmed_by"] == "Paul"

    # 重复 approve / 重试 → 幂等，绝不重复外发
    assert queue.approve(item_id, confirmed_by="Paul", notifier=notifier) is True
    assert queue.approve(item_id, confirmed_by="李四", notifier=notifier) is True
    assert sends == ["承诺正文"]                       # 仍只发了一次
    assert len(queue.list_pending()) == 0


def test_approve_without_confirmer_is_blocked(queue):
    sends: list[str] = []
    notifier = build_notifier(queue, audit=None, send_fn=lambda url, body: sends.append(body))
    item_id = queue.enqueue(_Msg(), reason="awaiting_L2_confirmation")
    # 无确认人 → 不放行（fail-closed），不外发，保持 pending
    assert queue.approve(item_id, confirmed_by="", notifier=notifier) is False
    assert sends == []
    assert queue.get(item_id)["status"] == STATUS_PENDING


def test_approve_unknown_id_returns_false(queue):
    notifier = build_notifier(queue, audit=None, send_fn=lambda url, body: None)
    assert queue.approve("nonexistent", confirmed_by="Paul", notifier=notifier) is False
