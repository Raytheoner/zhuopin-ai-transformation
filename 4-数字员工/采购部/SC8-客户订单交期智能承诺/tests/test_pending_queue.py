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
    required_level: str = "l2"


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


# ── B3 审批授权分级 ────────────────────────────────────────────────────────────
def test_vp_item_rejects_non_vp_approver(queue, audit):
    """VP 级项被非 VP 白名单确认人放行 → 拒绝、保持 pending、写审计。"""
    sends: list[str] = []
    notifier = build_notifier(queue, audit=audit, send_fn=lambda url, body: sends.append(body),
                              outbound_enabled=True)
    item_id = queue.enqueue(_Msg(required_level="vp"), reason="awaiting_L2_confirmation")
    assert queue.approve(item_id, confirmed_by="李四", notifier=notifier, audit=audit) is False
    assert sends == []
    assert queue.get(item_id)["status"] == STATUS_PENDING
    denials = audit.query_by(scenario="SC8", action="approval_denied_insufficient_level")
    assert len(denials) == 1 and denials[0]["decision"]["required_level"] == "vp"


def test_vp_item_accepts_vp_approver(queue, audit):
    """VP 级项被 VP 白名单确认人（Paul）放行 → 外发（总开关开启）。"""
    sends: list[str] = []
    notifier = build_notifier(queue, audit=audit, send_fn=lambda url, body: sends.append(body),
                              outbound_enabled=True)
    item_id = queue.enqueue(_Msg(required_level="vp"), reason="awaiting_L2_confirmation")
    assert queue.approve(item_id, confirmed_by="Paul", notifier=notifier) is True
    assert len(sends) == 1
    assert queue.get(item_id)["status"] == STATUS_SENT


# ── override_reason 判例采集 ─────────────────────────────────────────────────
def test_approve_with_override_reason_in_audit(queue, audit):
    """带 override_reason 的 approve → audit decision 可查到该字段；verify_chain 通过。"""
    sends: list[str] = []
    notifier = build_notifier(queue, audit=audit, send_fn=lambda url, body: sends.append(body),
                              outbound_enabled=True)
    item_id = queue.enqueue(_Msg(), reason="awaiting_L2_confirmation")
    reason = "客户紧急插单，SRM 承诺已电话确认，口头授权先行"
    assert queue.approve(item_id, confirmed_by="Paul", notifier=notifier,
                         audit=audit, override_reason=reason) is True
    assert len(sends) == 1

    events = audit.query_by(scenario="SC8", action="approve_sent")
    assert len(events) == 1
    ev = events[0]
    assert ev["decision"]["override_reason"] == reason
    assert ev.get("override_reason") == reason      # 顶级字段也有
    assert audit.verify_chain().ok is True


def test_approve_without_override_reason_no_key(queue, audit):
    """不传 override_reason → audit decision 中不含该 key（不写空字符串）。"""
    sends: list[str] = []
    notifier = build_notifier(queue, audit=audit, send_fn=lambda url, body: sends.append(body),
                              outbound_enabled=True)
    item_id = queue.enqueue(_Msg(), reason="awaiting_L2_confirmation")
    assert queue.approve(item_id, confirmed_by="Paul", notifier=notifier, audit=audit) is True

    events = audit.query_by(scenario="SC8", action="approve_sent")
    assert len(events) == 1
    assert "override_reason" not in events[0]["decision"]
