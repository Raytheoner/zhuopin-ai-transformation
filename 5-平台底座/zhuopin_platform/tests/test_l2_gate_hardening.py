"""L2 门禁与审计加固测试（Antigravity 评审 Blocker1 / Blocker2 钩子 / High4 / High5）。"""
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.audit.events import AuditEvent
from zhuopin_platform.audit.sinks import JsonlSink
from zhuopin_platform.shared_tools.connector_audit import ConnectorAudit, DebugLog
from zhuopin_platform.shared_tools.crm_notifier import NotificationDraft
from zhuopin_platform.shared_tools.erp_connector import ZpConnector
from zhuopin_platform.shared_tools.notifiers import Notifier, PendingApprovalSink

FIXTURES = Path(__file__).parent / "fixtures"


# ══ Blocker1：FAIL-CLOSED —— 缺字段/未知一律拦截，绝不默认放行 ══════════════════

def _noop_send_factory(calls):
    def _send(url, content):
        calls.append(content)
    return _send


def test_missing_requires_confirmation_is_blocked():
    """通知对象未定义 requires_confirmation → 必须被拦下（fail-closed），不自动外发。"""
    calls = []
    notifier = Notifier(send_fn=_noop_send_factory(calls), webhook_url="http://x")
    # 满足部分契约但**遗漏 requires_confirmation**（且 severity 非 critical）
    msg = SimpleNamespace(recipient="比亚迪", title="延期通知", body="...", severity="warning")
    sent = notifier.send(msg)
    assert sent is False, "缺 requires_confirmation 时绝不能自动外发"
    assert calls == []


def test_unknown_severity_is_blocked():
    """requires_confirmation=False 但严重度未知 → 保守拦截。"""
    calls = []
    notifier = Notifier(send_fn=_noop_send_factory(calls), webhook_url="http://x")
    msg = SimpleNamespace(recipient="x", title="t", body="b", requires_confirmation=False)
    assert notifier.send(msg) is False
    assert calls == []


def test_explicit_optout_low_severity_sends():
    """显式 requires_confirmation=False + 已知非 critical 严重度 → 低风险放行。"""
    calls = []
    notifier = Notifier(send_fn=_noop_send_factory(calls), webhook_url="http://x")
    msg = NotificationDraft(recipient="内部群", title="日报", body="齐套率95%",
                            severity="info", requires_confirmation=False)
    assert notifier.send(msg) is True
    assert len(calls) == 1


def test_critical_severity_blocked_even_if_optout():
    """severity=critical 即便 requires_confirmation=False 也拦截。"""
    calls = []
    notifier = Notifier(send_fn=_noop_send_factory(calls), webhook_url="http://x")
    msg = NotificationDraft(recipient="x", title="t", body="b",
                            severity="critical", requires_confirmation=False)
    assert notifier.send(msg) is False
    assert calls == []


# ══ Blocker2：持久化钩子（接口预留）—— 拦截的草稿入待审批队列 ════════════════════

class _FakeQueue:
    """SC8 待审批队列的测试替身（满足 PendingApprovalSink Protocol）。"""
    def __init__(self):
        self.items = []
    def enqueue(self, message, reason=""):
        self.items.append((message, reason))


def test_blocked_draft_handed_to_pending_sink(tmp_path):
    q = _FakeQueue()
    assert isinstance(q, PendingApprovalSink)
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    notifier = Notifier(send_fn=lambda u, c: None, webhook_url="http://x",
                        audit=audit, scenario="SC8", pending_sink=q)
    msg = NotificationDraft(recipient="比亚迪", title="延期", body="...",
                            requires_confirmation=True)
    notifier.send(msg)  # 未确认 → 拦截入队
    assert len(q.items) == 1
    assert q.items[0][1] == "awaiting_L2_confirmation"
    rec = audit.query_by(scenario="SC8")[0]
    assert rec["decision"]["queued_for_approval"] is True


def test_confirmed_send_not_queued(tmp_path):
    q = _FakeQueue()
    notifier = Notifier(send_fn=lambda u, c: None, webhook_url="http://x",
                        pending_sink=q)
    msg = NotificationDraft(recipient="比亚迪", title="t", body="b",
                            requires_confirmation=True)
    assert notifier.send(msg, confirmed_by="张采购") is True
    assert q.items == []  # 已确认外发，不入队


# ══ High4：并发写文件不损坏 ══════════════════════════════════════════════════

def test_jsonl_sink_concurrent_writes_intact(tmp_path):
    sink = JsonlSink(tmp_path / "audit.jsonl")
    n_threads, per = 20, 50

    def worker(tid):
        for i in range(per):
            sink.write(AuditEvent(scenario="T", action=f"{tid}-{i}",
                                  evaluator="", automation_level="L1"))

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
    for t in threads: t.start()
    for t in threads: t.join()

    lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == n_threads * per
    for ln in lines:
        json.loads(ln)  # 每行均为完整合法 JSON（无穿插损坏）


def test_debug_log_concurrent_writes_intact(tmp_path):
    dbg = DebugLog(path=tmp_path / "srm.debug.log", enabled=True)
    n_threads, per = 20, 50

    def worker(tid):
        for i in range(per):
            dbg.record(req={"t": tid, "i": i}, resp={"ok": True})

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
    for t in threads: t.start()
    for t in threads: t.join()

    lines = (tmp_path / "srm.debug.log").read_text(encoding="utf-8").splitlines()
    assert len(lines) == n_threads * per
    for ln in lines:
        json.loads(ln)


# ══ High5：回退路径也留审计痕迹 ═════════════════════════════════════════════════

def test_zp_fallback_path_is_audited(tmp_path):
    """ZpConnector 回退 CSV（生产计划无 zp 端点）时，回退路径也写轻量痕迹。"""
    sink = JsonlSink(tmp_path / "trace.jsonl")
    conn = ZpConnector(
        base_url="https://testerp.example:4445", user_code="u", ent_code="001",
        org_code="Z", client_id="c", client_secret="s",
        fallback_dir=FIXTURES, po_cache_file=tmp_path / "po.json",
        audit=ConnectorAudit(sink=sink),
    )
    plans = conn.get_production_plan()  # 纯 CSV 回退路径
    assert len(plans) > 0
    records = sink.read_all()
    assert any(r["source"] == "CSV" and r["action"] == "get_production_plan"
               for r in records), "回退路径必须留审计痕迹（High5）"
