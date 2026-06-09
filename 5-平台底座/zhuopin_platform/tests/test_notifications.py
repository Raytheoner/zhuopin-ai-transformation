"""通知通道测试（第 8 组，D3 解耦 + wecom + L2 门禁 + 审计）。

验证：
  · D3：CRM 草稿生成器只读 Protocol 字段，不 import DelayCase；任意满足 Protocol 的对象可用。
  · D6：无 ANTHROPIC_API_KEY 时降级模板，不发真实 API。
  · L2 门禁：推客户（requires_confirmation）未确认时不自动外发，只出草稿。
  · 审计：通知动作经注入 AuditLogger 留痕（动作/渠道/人工确认状态）。
  · wecom 全程 mock，不触真实企微端点。
"""
import json
from dataclasses import dataclass, field

import pytest

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.shared_tools.crm_notifier import (
    NotificationMessage,
    DelayNoticeInput,
    NotificationDraft,
    build_prompt,
    template_draft,
    generate_draft,
    DEFAULT_MODEL,
)
from zhuopin_platform.shared_tools.notifiers import Notifier
from zhuopin_platform.shared_tools.notifiers import wecom


# 一个普通对象（非 DelayCase）满足 DelayNoticeInput —— 证明解耦
@dataclass
class _FakeNotice:
    customer_name: str = "比亚迪"
    so_id: str = "SO2026040068"
    product_id: str = "F02N.0040"
    target_date: str = "2026-07-01"
    new_date: str = "2026-07-15"
    delay_days: int = 14
    reasons: list = field(default_factory=lambda: ["上游电容短缺，交期顺延"])


def test_draft_generator_decoupled_from_delaycase():
    """D3：crm_notifier 不 import delay_case / DelayCase（只读 Protocol）。"""
    import ast
    import zhuopin_platform.shared_tools.crm_notifier.draft as draft_mod
    tree = ast.parse(open(draft_mod.__file__, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert "delay_case" not in (node.module or "")
            assert all("DelayCase" not in a.name for a in node.names)
        elif isinstance(node, ast.Import):
            assert all("delay_case" not in a.name for a in node.names)


def test_template_draft_reads_protocol_fields():
    d = template_draft(_FakeNotice())
    assert isinstance(d, NotificationDraft)
    assert "比亚迪" in d.body
    assert "2026-07-15" in d.body  # 新交期
    assert "SO2026040068" in d.title
    assert d.requires_confirmation is True  # 推客户默认需 L2 确认


def test_build_prompt_contains_key_facts():
    p = build_prompt(_FakeNotice())
    assert "比亚迪" in p and "F02N.0040" in p and "14" in p


def test_generate_draft_falls_back_to_template_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    d = generate_draft(_FakeNotice(), api_key=None)
    assert isinstance(d, NotificationDraft)
    assert "比亚迪" in d.body


def test_default_model_is_sonnet_4_6():
    assert DEFAULT_MODEL == "claude-sonnet-4-6"


def test_notification_draft_satisfies_protocol():
    d = NotificationDraft(recipient="比亚迪", title="T", body="B", severity="warning")
    assert isinstance(d, NotificationMessage)


# ── L2 门禁 ──────────────────────────────────────────────────────────────────

def _fake_send_factory(calls):
    def _send(webhook_url, content):
        calls.append(content)
    return _send


def test_l2_gate_blocks_unconfirmed_customer_push():
    """推客户未确认 → 不自动外发，只返回草稿。"""
    calls = []
    notifier = Notifier(send_fn=_fake_send_factory(calls), webhook_url="http://x")
    msg = NotificationDraft(recipient="比亚迪", title="T", body="B",
                            severity="warning", requires_confirmation=True)
    sent = notifier.send(msg)  # 无 confirmed_by
    assert sent is False
    assert calls == []  # 绝不外发


def test_l2_gate_allows_confirmed_push():
    calls = []
    notifier = Notifier(send_fn=_fake_send_factory(calls), webhook_url="http://x")
    msg = NotificationDraft(recipient="比亚迪", title="T", body="B",
                            severity="warning", requires_confirmation=True)
    sent = notifier.send(msg, confirmed_by="张采购")
    assert sent is True
    assert len(calls) == 1 and "B" in calls[0]


def test_low_risk_internal_push_no_confirmation_needed():
    calls = []
    notifier = Notifier(send_fn=_fake_send_factory(calls), webhook_url="http://x")
    msg = NotificationDraft(recipient="内部群", title="日报", body="今日齐套率 95%",
                            severity="info", requires_confirmation=False)
    sent = notifier.send(msg)
    assert sent is True and len(calls) == 1


# ── 审计留痕 ──────────────────────────────────────────────────────────────────

def test_send_records_audit_with_confirmation_status(tmp_path):
    calls = []
    audit = AuditLogger.jsonl(tmp_path / "audit_log.jsonl")
    notifier = Notifier(send_fn=_fake_send_factory(calls), webhook_url="http://x",
                        audit=audit, scenario="SC8")
    msg = NotificationDraft(recipient="比亚迪", title="T", body="B",
                            severity="warning", requires_confirmation=True)
    notifier.send(msg, confirmed_by="张采购")

    records = audit.query_by(scenario="SC8")
    assert len(records) == 1
    rec = records[0]
    assert rec["action"] in ("notification_send", "notification_send_blocked")
    assert rec["decision"]["confirmed_by"] == "张采购"
    assert rec["decision"]["channel"] == "wecom"


def test_blocked_send_is_audited(tmp_path):
    audit = AuditLogger.jsonl(tmp_path / "audit_log.jsonl")
    notifier = Notifier(send_fn=lambda u, c: None, webhook_url="http://x",
                        audit=audit, scenario="SC8")
    msg = NotificationDraft(recipient="比亚迪", title="T", body="B",
                            requires_confirmation=True)
    notifier.send(msg)  # 未确认 → blocked
    rec = audit.query_by(scenario="SC8")[0]
    assert rec["action"] == "notification_send_blocked"


# ── wecom 推送（mock）────────────────────────────────────────────────────────

def test_wecom_send_markdown_ok(monkeypatch):
    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps({"errcode": 0}).encode("utf-8")
    monkeypatch.setattr(wecom.urllib.request, "urlopen", lambda *a, **k: _Resp())
    wecom.send_markdown("http://webhook", "**hi**")  # 不抛即通过


def test_wecom_raises_on_errcode(monkeypatch):
    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps({"errcode": 93000, "errmsg": "bad"}).encode("utf-8")
    monkeypatch.setattr(wecom.urllib.request, "urlopen", lambda *a, **k: _Resp())
    with pytest.raises(RuntimeError):
        wecom.send_markdown("http://webhook", "x")
