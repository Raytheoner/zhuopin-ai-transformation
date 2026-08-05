"""真延期识别 + 去重推送（alert_dispatch）测试 —— 全 mock，捕获推送。"""
from __future__ import annotations

from sc8.alert_dispatch import detect_new_red, dispatch_new_reds
from sc8.baoguan_service import Snapshot
from sc8.case_store import CaseStore


def _row(item, so="FO-1", ship="2026-06-10", risk="red", cg=61, gap=61, bn="C1", nfd=None):
    return {"id": item, "so": so, "ship": ship, "risk": risk, "cg": cg, "gap": gap,
            "bn": bn, "comp": 3, "nf": 1, "cust": "比亚迪", "nfd": nfd or []}


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


# ── 队列#147续（2026-07-29，Paul 拍板改口径后）：告警措辞改用 gap（全量口径） ──────

def test_alert_markdown_uses_gap_not_confirmed_gap_when_confirmed_only():
    """瓶颈子件已答复（非 nfd 成员）→ 沿用"确定延期"措辞，天数取 gap（此时 gap==cg，
    因为全部子件都已确认时两者本就同源，见 baoguan._classify docstring）。"""
    store = CaseStore(":memory:")
    sent = []
    row = _row("A", cg=41, gap=41, bn="C1", nfd=[])   # C1 已答复，不在 nfd 里
    dispatch_new_reds(detect_new_red(_snap([row]), None), store,
                      webhook_url="http://hook", sender=lambda u, c: sent.append(c))
    assert "确定延期 +41 天" in sent[0]
    assert "确定瓶颈子件 `C1`" in sent[0]


def test_alert_markdown_uses_conservative_wording_when_bottleneck_unanswered():
    """瓶颈子件未答复（在 nfd 里）→ 改用"保守预警"措辞 + 全量 gap 天数，不把无答复
    估算包装成"确定"发给运维群（真实案例 S02Y.0135 同构：cg=41 但 gap=109，瓶颈未答复）。"""
    store = CaseStore(":memory:")
    sent = []
    row = _row("A", cg=41, gap=109, bn="C9", nfd=[{"id": "C9", "qty": 300, "eta": "2026-10-27"}])
    dispatch_new_reds(detect_new_red(_snap([row]), None), store,
                      webhook_url="http://hook", sender=lambda u, c: sent.append(c))
    assert "保守预警 +109 天（未答复估算）" in sent[0]
    assert "瓶颈子件（未答复）`C9`" in sent[0]
    assert "确定延期" not in sent[0]   # 不能把估算说成确定


def test_dispatch_case_stores_bottleneck_unanswered_flag():
    """#223：建案时 bottleneck_unanswered 落库需与 _alert_markdown 的 unanswered 判据同源——
    瓶颈子件在 nfd 明细里即 True，供 case_draft.py 客户草稿据此选措辞分支。"""
    store = CaseStore(":memory:")
    row = _row("A", cg=41, gap=109, bn="C9", nfd=[{"id": "C9"}])
    dispatch_new_reds(detect_new_red(_snap([row]), None), store,
                      webhook_url=None, sender=lambda u, c: None)
    case = store.get_open_cases()[0]
    assert case.bottleneck_unanswered is True


def test_dispatch_case_bottleneck_answered_flag_false():
    store = CaseStore(":memory:")
    row = _row("A", cg=41, gap=41, bn="C1", nfd=[])   # C1 已答复，不在 nfd 里
    dispatch_new_reds(detect_new_red(_snap([row]), None), store,
                      webhook_url=None, sender=lambda u, c: None)
    case = store.get_open_cases()[0]
    assert case.bottleneck_unanswered is False


def test_dispatch_case_stores_gap_not_confirmed_gap():
    """建案的 confirmed_gap_days 字段改存 gap（全量口径，与建案原因——该行判红——同源）。"""
    store = CaseStore(":memory:")
    row = _row("A", cg=41, gap=109, bn="C9", nfd=[{"id": "C9"}])
    dispatch_new_reds(detect_new_red(_snap([row]), None), store,
                      webhook_url=None, sender=lambda u, c: None)
    cases = store.get_open_cases()
    assert len(cases) == 1 and cases[0].confirmed_gap_days == 109


# ── 真实事故复现修复（2026-07-29，队列#147续口径切换首轮重算触发企微限流）──────────

def test_dispatch_continues_after_single_push_failure():
    """单行推送失败（如企微限流 errcode=45009）不应中断循环——案例仍建、后续行仍处理，
    不能像真实事故那样让一次限流拖垮整轮 /api/refresh。"""
    store = CaseStore(":memory:")
    sent = []

    def _flaky_sender(url, content):
        if "A" in content:
            raise RuntimeError("企业微信推送失败 errcode=45009 api freq out of limit")
        sent.append(content)

    rows = [_row("A"), _row("B", so="FO-2")]
    pushed = dispatch_new_reds(detect_new_red(_snap(rows), None), store,
                               webhook_url="http://hook", sender=_flaky_sender)
    # A 推送失败不计入 pushed，但案例仍建；B 不受影响正常处理
    assert [r["id"] for r in pushed] == ["B"]
    assert len(sent) == 1
    assert {c.item_code for c in store.get_open_cases()} == {"A", "B"}  # 两个案例都建了


def test_dispatch_records_push_failure_in_audit():
    store = CaseStore(":memory:")
    events = []

    class _Audit:
        def record(self, ev): events.append(ev)

    def _boom(url, content):
        raise RuntimeError("企业微信推送失败 errcode=45009")

    dispatch_new_reds(detect_new_red(_snap([_row("A")]), None), store,
                      webhook_url="http://hook", audit=_Audit(), sender=_boom)
    actions = [e.action for e in events]
    assert "baoguan_red_alert_push_failed" in actions
    # 失败也要写主审计事件，pushed 标 False（如实记录，不假装成功）
    main_event = next(e for e in events if e.action == "baoguan_red_alert")
    assert main_event.decision["pushed"] is False
