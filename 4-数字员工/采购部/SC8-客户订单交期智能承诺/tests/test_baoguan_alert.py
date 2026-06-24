"""真延期识别 + 去重推送（alert_dispatch）测试 —— 全 mock，捕获推送。"""
from __future__ import annotations

from sc8.alert_dispatch import detect_new_red, dispatch_new_reds
from sc8.baoguan_service import Snapshot
from sc8.case_store import CaseStore


def _row(item, so="FO-1", ship="2026-06-10", risk="red", cg=61, bn="C1"):
    return {"id": item, "so": so, "ship": ship, "risk": risk, "cg": cg,
            "bn": bn, "comp": 3, "nf": 1, "cust": "比亚迪"}


def _snap(rows):
    return Snapshot(generated_at="x", today="2026-06-24", rows=rows,
                    counts={"red": 0, "gap": 0, "yel": 0, "grn": 0})


def test_detect_new_red_first_run_all_new():
    curr = _snap([_row("A"), _row("B", so="FO-2"), _row("G", risk="grn")])
    new = detect_new_red(curr, None)
    assert {r["id"] for r in new} == {"A", "B"}      # 绿的不算


def test_detect_new_red_excludes_existing():
    prev = _snap([_row("A")])
    curr = _snap([_row("A"), _row("B", so="FO-2")])   # A 既有、B 新增
    new = detect_new_red(curr, prev)
    assert [r["id"] for r in new] == ["B"]


def test_detect_new_red_stable_key_not_rowindex():
    """行序变化但稳定键不变 → 不算新增。"""
    prev = _snap([_row("A"), _row("B", so="FO-2")])
    curr = _snap([_row("B", so="FO-2"), _row("A")])   # 仅顺序变
    assert detect_new_red(curr, prev) == []


def test_dispatch_pushes_once_and_builds_case():
    store = CaseStore(":memory:")
    sent = []
    new = detect_new_red(_snap([_row("A")]), None)
    pushed = dispatch_new_reds(new, store, webhook_url="http://hook",
                               sender=lambda url, content: sent.append(content))
    assert len(pushed) == 1 and len(sent) == 1
    assert "保供真延期" in sent[0] and "比亚迪" not in sent[0]   # 运维口径，不含客户名
    assert len(store.get_open_cases()) == 1


def test_dispatch_dedup_no_repeat_push():
    store = CaseStore(":memory:")
    sent = []
    row = _row("A")
    # 第一次刷新：建案 + 推送
    dispatch_new_reds(detect_new_red(_snap([row]), None), store,
                      webhook_url="http://hook", sender=lambda u, c: sent.append(c))
    # 第二次刷新：同真延期仍在（prev 也有它 → detect 为空），即使强行再 dispatch 也因已建案不重推
    again = dispatch_new_reds([row], store, webhook_url="http://hook",
                              sender=lambda u, c: sent.append(c))
    assert again == [] and len(sent) == 1
    assert len(store.get_open_cases()) == 1


def test_dispatch_writes_audit():
    store = CaseStore(":memory:")
    events = []

    class _Audit:
        def record(self, ev): events.append(ev)

    dispatch_new_reds(detect_new_red(_snap([_row("A")]), None), store,
                      webhook_url=None, audit=_Audit(), sender=lambda u, c: None)
    assert len(events) == 1
    assert events[0].action == "baoguan_red_alert" and events[0].scenario == "SC8"
