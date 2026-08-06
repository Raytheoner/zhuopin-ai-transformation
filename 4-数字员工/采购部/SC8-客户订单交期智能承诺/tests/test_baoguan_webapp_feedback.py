"""保供 Web 服务新路由测试（队列 #110 Feature A/B + #112）：Flask test_client，全 mock 不触网。

覆盖：反馈接口必填校验/成功落盘/未配置时 503、判例包列表/详情/提交全链路、
访问日志中间件在真实路由上的接入（#112）。
"""
from __future__ import annotations

import json

from sc8 import case_review, webapp
from sc8.baoguan_service import SnapshotStore
from sc8.case_store import CaseStore
from sc8.feedback_store import JsonlAppendStore


def _client(*, feedback_store=None, case_review_dir=None, case_review_store=None,
           access_log_path=None):
    app = webapp.create_app(snapshot_store=SnapshotStore(None), case_store=CaseStore(":memory:"),
                            audit=None, ops_webhook_url=None,
                            feedback_store=feedback_store, case_review_dir=case_review_dir,
                            case_review_store=case_review_store, access_log_path=access_log_path)
    app.config.update(TESTING=True)
    return app, app.test_client()


# ── Feature A：看板逐行反馈 ───────────────────────────────────────────────────

def test_feedback_returns_503_when_not_configured():
    _, c = _client()
    r = c.post("/api/baoguan/feedback", json={"product_id": "S02Y.0188", "so_id": "SO1", "verdict": "correct"})
    assert r.status_code == 503


def test_feedback_rejects_missing_required_fields(tmp_path):
    store = JsonlAppendStore(tmp_path / "fb.jsonl")
    _, c = _client(feedback_store=store)
    r = c.post("/api/baoguan/feedback", json={"product_id": "", "so_id": "SO1", "verdict": "correct"})
    assert r.status_code == 400
    r2 = c.post("/api/baoguan/feedback", json={"product_id": "S02Y.0188", "so_id": "SO1", "verdict": "maybe"})
    assert r2.status_code == 400


def test_feedback_success_appends_record(tmp_path):
    store = JsonlAppendStore(tmp_path / "fb.jsonl")
    _, c = _client(feedback_store=store)
    r = c.post("/api/baoguan/feedback", json={
        "product_id": "S02Y.0188", "so_id": "FO2026060001", "ship_date": "2026-07-10",
        "verdict": "incorrect", "reason": "瓶颈子件其实有货", "risk": "red",
    })
    assert r.status_code == 200 and r.get_json()["ok"] is True
    recs = store.read_all()
    assert len(recs) == 1
    assert recs[0]["product_id"] == "S02Y.0188" and recs[0]["verdict"] == "incorrect"
    assert recs[0]["reason"] == "瓶颈子件其实有货"


def test_feedback_does_not_touch_judgment_logic(tmp_path):
    """红线：反馈接口只落盘，不改任何快照/判据数据（配套断言：接口不接触 snapshot_store）。"""
    store = JsonlAppendStore(tmp_path / "fb.jsonl")
    app, c = _client(feedback_store=store)
    before = app.config["SNAP"].get().to_dict()
    c.post("/api/baoguan/feedback", json={"product_id": "X", "so_id": "Y", "verdict": "correct"})
    after = app.config["SNAP"].get().to_dict()
    assert before == after


# ── Feature B：判例包网页表单化 ────────────────────────────────────────────────

def _write_package(d, package_id="pkg-1"):
    data = {
        "package_id": package_id, "title": "批X · 议题", "recipient": "姚祖怡",
        "cases": [
            {"case_no": 1, "scenario": "场景1", "current_verdict": "现状1", "proposed_verdict": "拟改1"},
            {"case_no": 2, "scenario": "场景2", "current_verdict": "现状2", "proposed_verdict": "拟改2"},
        ],
    }
    (d / f"{package_id}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_case_review_routes_503_when_not_configured():
    _, c = _client()
    assert c.get("/cases/review").status_code == 503
    assert c.get("/cases/review/pkg-1").status_code == 503


def test_case_review_list_shows_packages(tmp_path):
    _write_package(tmp_path)
    _, c = _client(case_review_dir=tmp_path, case_review_store=JsonlAppendStore(tmp_path / "sub.jsonl"))
    r = c.get("/cases/review")
    assert r.status_code == 200
    assert "批X" in r.get_data(as_text=True)


def test_case_review_detail_404_when_package_missing(tmp_path):
    _, c = _client(case_review_dir=tmp_path, case_review_store=JsonlAppendStore(tmp_path / "sub.jsonl"))
    assert c.get("/cases/review/nope").status_code == 404


def test_case_review_detail_get_renders_form(tmp_path):
    _write_package(tmp_path)
    _, c = _client(case_review_dir=tmp_path, case_review_store=JsonlAppendStore(tmp_path / "sub.jsonl"))
    r = c.get("/cases/review/pkg-1")
    assert r.status_code == 200
    assert "场景1" in r.get_data(as_text=True)


def test_case_review_submit_appends_full_submission(tmp_path):
    _write_package(tmp_path)
    sub_path = tmp_path / "sub.jsonl"
    store = JsonlAppendStore(sub_path)
    _, c = _client(case_review_dir=tmp_path, case_review_store=store)
    r = c.post("/cases/review/pkg-1", data={
        "respondent": "姚祖怡",
        "verdict_1": "agree", "note_1": "",
        "verdict_2": "", "note_2": "其实应该是这样……",   # 硬约束①：✏️非空但未勾选，仍需独立记录
        "supplement": "顺带说一句，#17 的问题也还没解决",
        "new_issue": ["新问题A", "新问题B"],              # 硬约束③：一次提交追加多条新问题
    })
    assert r.status_code == 200
    recs = store.read_all()
    assert len(recs) == 1
    rec = recs[0]
    assert rec["package_id"] == "pkg-1" and rec["respondent"] == "姚祖怡"
    responses = {r["case_no"]: r for r in rec["responses"]}
    assert responses[1]["verdict"] == "agree" and responses[1]["note"] == ""
    assert responses[2]["verdict"] is None and responses[2]["note"] == "其实应该是这样……"
    assert rec["supplement"] == "顺带说一句，#17 的问题也还没解决"
    assert rec["new_issues"] == ["新问题A", "新问题B"]


def test_case_review_submit_does_not_touch_judgment_logic(tmp_path):
    """红线：判例包提交只落盘，不经 audit、不改任何判据（见 case_review.py 顶部说明）。"""
    _write_package(tmp_path)
    app, c = _client(case_review_dir=tmp_path, case_review_store=JsonlAppendStore(tmp_path / "sub.jsonl"))
    before = app.config["SNAP"].get().to_dict()
    c.post("/cases/review/pkg-1", data={"respondent": "x"})
    after = app.config["SNAP"].get().to_dict()
    assert before == after


# ── #112：访问日志中间件在真实路由上接入（跨功能集成点）───────────────────────

def test_access_log_records_real_route_hits(tmp_path):
    log_path = tmp_path / "access.jsonl"
    _, c = _client(access_log_path=log_path)
    c.get("/api/ping")   # 豁免，不应落盘
    c.get("/api/baoguan")
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["path"] == "/api/baoguan" and rec["service"] == "成品保供预警看板"
