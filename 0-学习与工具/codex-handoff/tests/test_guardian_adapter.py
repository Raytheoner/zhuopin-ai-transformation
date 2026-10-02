"""Guardian seam tests use only fixture rows and fake runner output."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location("guardian_under_test", BASE / "guardian_adapter.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def rows():
    return [
        {"task_id": "local-a", "opener_id": "A1", "lane": "alpha",
         "touches": ["service/a"], "action_key": "worktree_local_build"},
        {"task_id": "local-b", "opener_id": "A2", "lane": "beta",
         "touches": ["service/a"], "action_key": "worktree_local_build"},
        {"task_id": "lan-only", "opener_id": "A3", "lane": "gamma",
         "touches": ["service/c"], "action_key": "worktree_local_build", "lan_required": True,
         "row": 303, "section": "一", "next_action": "publish only after LAN return"},
        {"task_id": "locks", "opener_id": "A4", "lane": "lock",
         "touches": ["tools/lock"], "action_key": "worktree_local_build", "kind": "lock_tools"},
    ]


def test_off_lan_excludes_internal_and_orders_touch_conflict():
    guardian = load()
    plan = guardian.plan_batch("B-fixture", rows(), {"effective": "off"})
    assert "lan-only" not in plan["dispatchable_ids"]
    assert plan["waves"][-1]["kind"] == "lock_tools"
    assert plan["waves"][0]["task_ids"] != ["local-a", "local-b"]
    assert plan["max_parallel"] <= 4
    assert plan["stagger_seconds"] >= 90
    assert plan["max_items"] == 10
    assert plan["mode"] == "guardian"


def test_unknown_lan_and_unknown_action_fail_closed():
    guardian = load()
    source = rows() + [{"task_id": "unknown", "opener_id": "A5", "lane": "u",
                        "touches": ["service/u"], "action_key": "not_registered"}]
    plan = guardian.plan_batch("B-fixture", source, {"effective": "unknown"})
    assert "lan-only" not in plan["dispatchable_ids"]
    assert "unknown" not in plan["dispatchable_ids"]
    assert plan["excluded"]["unknown"] == "human_decision"


def test_dry_run_mismatch_stops_before_model(tmp_path):
    guardian = load()
    plan_file = tmp_path / "watch.md"
    plan_file.write_text("fixture", encoding="utf8")
    plan = guardian.plan_batch("B-fixture", rows()[:2], {"effective": "on"},
                               mode="headless", plan_file=plan_file)
    calls = []

    def executor(argv, **kw):
        calls.append(argv)
        return {"exit": 0, "stdout": "泳道 1 条（并行上限 4，错峰 90s）：\n  ◆ wrong ：A1→A2（泳道内串行）",
                "stderr": ""}

    result = guardian.dispatch_batch(plan, True, executor)
    assert result["status"] == "blocked"
    assert len(calls) == 1 and "-DryRun" in calls[0]
    assert all("-ConsumerEnabled" not in c for c in calls)


def test_guardian_mode_and_disabled_headless_start_no_model(tmp_path):
    guardian = load()
    plan_file = tmp_path / "watch.md"
    plan_file.write_text("fixture", encoding="utf8")
    front = guardian.plan_batch("B-front", rows()[:1], {"effective": "on"},
                                plan_file=plan_file)
    assert guardian.dispatch_batch(front, True, lambda *a, **k: pytest.fail("headless runner forbidden"))["status"] == "needs_manual_wake"
    headless = guardian.plan_batch("B-headless", rows()[:1], {"effective": "on"},
                                   mode="headless", plan_file=plan_file)
    calls = []

    def executor(argv, **kw):
        calls.append(argv)
        return {"exit": 0, "stdout": "泳道 1 条（并行上限 4，错峰 90s）：\n  ◆ alpha ：A1（泳道内串行）",
                "stderr": ""}

    assert guardian.dispatch_batch(headless, False, executor)["status"] == "paused"
    assert len(calls) == 1


def test_max_wait_is_not_delivery_completion(monkeypatch):
    guardian = load()
    monkeypatch.setattr(guardian, "_wait_once", lambda batch: {"status": "max_wait", "lanes": []})
    assert guardian.observe_batch("B-fixture")["status"] == "needs_manual_wake"


def test_dependency_of_excluded_task_is_not_dispatched():
    guardian = load()
    source = rows() + [
        {"task_id": "after-lan", "opener_id": "A5", "lane": "after",
         "touches": ["service/d"], "action_key": "worktree_local_build",
         "depends_on": ["lan-only"], "row": 304, "section": "一",
         "next_action": "build after LAN service"},
        {"task_id": "after-after", "opener_id": "A6", "lane": "after2",
         "touches": ["service/e"], "action_key": "worktree_local_build",
         "depends_on": ["after-lan"], "row": 306, "section": "一",
         "next_action": "build dependent integration"},
    ]
    plan = guardian.plan_batch("B-fixture", source, {"effective": "off"})
    assert "after-lan" not in plan["dispatchable_ids"]
    assert "after-after" not in plan["dispatchable_ids"]
    assert plan["excluded"]["after-after"] == "dependency unavailable"


def test_unordered_opener_rows_follow_runner_numeric_order():
    guardian = load()
    source = [rows()[1], rows()[0]]
    plan = guardian.plan_batch("B-fixture", source, {"effective": "on"})
    assert plan["lane_ids"] == ["alpha", "beta"]
    assert plan["opener_ids"] == ["A1", "A2"]

def test_dry_run_same_lane_with_missing_opener_is_blocked(tmp_path):
    guardian = load()
    plan_file = tmp_path / "watch.md"
    plan_file.write_text("fixture", encoding="utf8")
    source = [rows()[0], {**rows()[1], "lane": "alpha", "touches": ["service/b"]}]
    plan = guardian.plan_batch("B-fixture", source, {"effective": "on"},
                               mode="headless", plan_file=plan_file)
    calls = []

    def executor(argv, **kw):
        calls.append(argv)
        return {"exit": 0, "stdout": "泳道 1 条（并行上限 4，错峰 90s）：\n  ◆ alpha ：A1（泳道内串行）",
                "stderr": ""}

    assert guardian.dispatch_batch(plan, True, executor)["status"] == "blocked"
    assert len(calls) == 1

def test_foreground_failed_task_blocks_dependents_but_independent_continues(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "codex-state"))
    guardian = load()
    guardian.lane_machine.REPO_ROOT = tmp_path
    source = [
        {"task_id": "first", "opener_id": "A1", "lane": "a", "touches": ["x"],
         "action_key": "worktree_local_build"},
        {"task_id": "dependent", "opener_id": "A2", "lane": "b", "touches": ["y"],
         "action_key": "worktree_local_build", "depends_on": ["first"]},
        {"task_id": "independent", "opener_id": "A3", "lane": "c", "touches": ["x"],
         "action_key": "worktree_local_build"},
    ]
    plan = guardian.plan_batch("B-front", source, {"effective": "on"})
    calls = []

    def advance(task_id, workspace, authorization, executor, model_runner):
        calls.append(task_id)
        if task_id == "first":
            return {"status": "blocked", "reason": "fixture failure"}
        return {"status": "ready", "next_phase": "release_ready"}

    monkeypatch.setattr(guardian, "_advance_task", advance)
    result = guardian.dispatch_batch(
        plan, True, lambda *a, **kw: pytest.fail("headless runner forbidden"),
        workspaces={r["task_id"]: tmp_path for r in source})
    assert result["status"] == "needs_manual_wake"
    assert calls == ["first", "independent"]
    assert result["tasks"]["dependent"]["status"] == "blocked_dependency"
    assert result["tasks"]["independent"]["status"] == "release_ready"

def test_headless_dispatch_separates_conflicting_waves_and_defers_dependents(tmp_path):
    guardian = load()
    plan_file = tmp_path / "watch.md"
    plan_file.write_text("fixture", encoding="utf8")
    source = [
        {"task_id": "first", "opener_id": "A1", "lane": "alpha",
         "touches": ["shared"], "action_key": "worktree_local_build"},
        {"task_id": "second", "opener_id": "A2", "lane": "beta",
         "touches": ["shared"], "action_key": "worktree_local_build"},
        {"task_id": "dependent", "opener_id": "A3", "lane": "gamma",
         "touches": ["other"], "action_key": "worktree_local_build",
         "depends_on": ["first"]},
    ]
    plan = guardian.plan_batch("B-headless", source, {"effective": "on"},
                               mode="headless", plan_file=plan_file)
    calls = []

    def executor(argv, **kw):
        calls.append(argv)
        only = argv[argv.index("-Only") + 1]
        lane = {"A1": "alpha", "A2": "beta", "A3": "gamma"}[only]
        return {"exit": 0, "stdout": f"泳道 1 条（并行上限 4，错峰 90s）：\n  ◆ {lane} ：{only}（泳道内串行）",
                "stderr": ""}

    result = guardian.dispatch_batch(plan, True, executor)
    launched = [c[c.index("-Only") + 1] for c in calls if "-ConsumerEnabled" in c]
    assert launched == ["A1", "A2"]
    assert "A3" in result["deferred_openers"]

def test_parent_child_touch_paths_are_separate_waves():
    guardian = load()
    source = [
        {"task_id": "parent", "opener_id": "A1", "lane": "p",
         "touches": ["service"], "action_key": "worktree_local_build"},
        {"task_id": "child", "opener_id": "A2", "lane": "c",
         "touches": ["service/api"], "action_key": "worktree_local_build"},
    ]
    plan = guardian.plan_batch("B-fixture", source, {"effective": "on"})
    assert len(plan["waves"]) == 2


def test_foreground_pause_persists_batch_task_and_lane_for_observation(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "codex-state"))
    guardian = load()
    guardian.lane_machine.REPO_ROOT = tmp_path
    source = rows()[:1]
    task_id = source[0]["task_id"]
    lane = source[0]["lane"]
    plan = guardian.plan_batch("B-persist", source, {"effective": "on"})
    calls = []

    outcomes = iter([
        {"status": "paused", "reason": "design approval required",
         "model": {"raw_output": "must not be copied into batch state"}},
        {"status": "ready", "next_phase": "release_ready", "reason": "fixture gate accepted"},
    ])

    def advance(task_id, workspace, authorization, executor, model_runner):
        calls.append(task_id)
        return next(outcomes)

    monkeypatch.setattr(guardian, "_advance_task", advance)
    result = guardian.dispatch_batch(plan, True,
        lambda *a, **kw: pytest.fail("foreground guardian must not launch headless runner"),
        workspaces={task_id: tmp_path})
    assert result["tasks"][task_id]["status"] == "paused"
    batch_record = tmp_path / "codex-state" / "guardian-batches" / "B-persist.json"
    assert batch_record.is_file()
    record = json.loads(batch_record.read_text(encoding="utf8"))
    assert record["tasks"][task_id]["lane"] == lane
    assert record["tasks"][task_id]["status"] == "paused"
    assert "model" not in record["tasks"][task_id]
    lane_state = guardian.lane_machine._read_state()["lanes"][lane]
    assert lane_state["status"] == "paused"
    assert lane_state["batch"] == "B-persist"
    assert task_id in lane_state["waiting_for"]
    heartbeat = guardian.lane_machine.resolve_heartbeat_path(
        guardian.lane_machine.heartbeat_rel_path(lane))
    assert heartbeat.is_file()
    assert "B-persist" in heartbeat.read_text(encoding="utf8")
    monkeypatch.setattr(guardian, "_wait_once", lambda batch: pytest.fail("persisted batch must be read locally"))
    observed = guardian.observe_batch("B-persist")
    assert observed["status"] == "needs_manual_wake"
    assert observed["tasks"][task_id]["lane"] == lane
    assert observed["lane_states"][lane]["status"] == "paused"
    again = guardian.dispatch_batch(plan, True,
        lambda *a, **kw: pytest.fail("headless runner forbidden"), workspaces={task_id: tmp_path})
    assert again["status"] == "needs_manual_wake"
    assert calls == [task_id]

    guardian.lane_machine.resume_lane(lane=lane, answer="已检查并恢复")
    resumed = guardian.dispatch_batch(plan, True,
        lambda *a, **kw: pytest.fail("headless runner forbidden"), workspaces={task_id: tmp_path})
    assert resumed["status"] == "release_ready"
    assert resumed["delivery_accepted"] is False
    final_record = json.loads(batch_record.read_text(encoding="utf8"))
    assert final_record["tasks"][task_id]["status"] == "release_ready"
    assert final_record["delivery_accepted"] is False
    assert calls == [task_id, task_id]


def test_foreground_paused_task_stops_later_tasks_in_same_lane(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "codex-state"))
    guardian = load()
    guardian.lane_machine.REPO_ROOT = tmp_path
    source = [
        {"task_id": "first", "opener_id": "A1", "lane": "serial",
         "touches": ["x"], "action_key": "worktree_local_build"},
        {"task_id": "second", "opener_id": "A2", "lane": "serial",
         "touches": ["y"], "action_key": "worktree_local_build"},
    ]
    plan = guardian.plan_batch("B-serial", source, {"effective": "on"})
    calls = []
    outcomes = iter([
        {"status": "paused", "reason": "design review"},
        {"status": "ready", "next_phase": "release_ready"},
        {"status": "ready", "next_phase": "release_ready"},
    ])

    def advance(task_id, workspace, authorization, executor, model_runner):
        calls.append(task_id)
        return next(outcomes)

    monkeypatch.setattr(guardian, "_advance_task", advance)
    workspaces = {entry["task_id"]: tmp_path for entry in source}
    guardian.dispatch_batch(plan, True, lambda *a, **kw: pytest.fail("headless runner forbidden"),
                            workspaces=workspaces)
    record_path = tmp_path / "codex-state" / "guardian-batches" / "B-serial.json"
    record = json.loads(record_path.read_text(encoding="utf8"))
    assert calls == ["first"]
    assert record["tasks"]["second"]["status"] == "waiting_lane"

    guardian.lane_machine.resume_lane(lane="serial", answer="已完成审核")
    guardian.dispatch_batch(plan, True, lambda *a, **kw: pytest.fail("headless runner forbidden"),
                            workspaces=workspaces)
    record = json.loads(record_path.read_text(encoding="utf8"))
    assert calls == ["first", "first", "second"]
    assert record["tasks"]["first"]["status"] == "release_ready"
    assert record["tasks"]["second"]["status"] == "release_ready"


def test_lan_hold_has_queue_locator_and_deploy_transfer_even_when_off():
    guardian = load()
    source = rows() + [
        {"task_id": "deploy", "opener_id": "A5", "lane": "deploy-lane",
         "touches": ["platform/release"], "action_key": "deploy_51",
         "row": 305, "section": "一", "next_action": "deploy service to .51"},
    ]
    plan = guardian.plan_batch("B-holds", source, {"effective": "off", "status": "off"})
    assert plan["lan_holds"] == [
        {"task_id": "lan-only", "row": 303, "section": "一",
         "next_action": "publish only after LAN return", "reason": "LAN unavailable"},
        {"task_id": "deploy", "row": 305, "section": "一",
         "next_action": "deploy service to .51", "reason": "deploy_51 requires release binding and LAN closeout"},
    ]
    assert plan["transfers"] == []
    assert "deploy" not in plan["dispatchable_ids"]


def test_lan_hold_without_live_queue_locator_fails_closed():
    guardian = load()
    source = [{**rows()[2], "row": None}]
    with pytest.raises(ValueError, match="queue locator"):
        guardian.plan_batch("B-missing-locator", source, {"effective": "unknown"})


def test_same_batch_changed_plan_cannot_resume_old_approval(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    guardian = load()
    guardian.lane_machine.REPO_ROOT = tmp_path
    plan = guardian.plan_batch("B-drift", rows()[:1], {"effective": "on"})
    calls = []

    def advance(task_id, workspace, authorization, executor, model_runner):
        calls.append(task_id)
        return {"status": "paused", "reason": "design approval required"}

    monkeypatch.setattr(guardian, "_advance_task", advance)
    first = guardian.dispatch_batch(
        plan, True, lambda *a, **kw: pytest.fail("headless runner forbidden"),
        workspaces={"local-a": tmp_path})
    assert first["tasks"]["local-a"]["status"] == "paused"
    guardian.lane_machine.resume_lane(lane="alpha", answer="resume")
    changed = {**plan, "lan": "off"}
    second = guardian.dispatch_batch(
        changed, True, lambda *a, **kw: pytest.fail("headless runner forbidden"),
        workspaces={"local-a": tmp_path})
    assert second["status"] == "blocked"
    assert "plan" in second["reason"]
    assert calls == ["local-a"]


def test_headless_two_openers_bind_as_one_powershell_only_argument(tmp_path):
    guardian = load()
    file = tmp_path / "watch.md"
    file.write_text("fixture", encoding="utf8")
    source = [rows()[0], {**rows()[1], "touches": ["service/b"]}]
    plan = guardian.plan_batch("B-two", source, {"effective": "on"},
                               mode="headless", plan_file=file)
    calls = []

    def powershell_binding(argv, **kwargs):
        calls.append(argv)
        index = argv.index("-Only")
        if argv[index + 1] != "A1,A2" or "A2" in argv[index + 2:]:
            return {"exit": 20, "stdout": "",
                    "stderr": "A positional parameter cannot be found that accepts argument A2"}
        if "-DryRun" in argv:
            return {"exit": 0, "stdout": "泳道 2 条：\n  ◆ alpha ：A1（泳道内串行）\n  ◆ beta ：A2（泳道内串行）",
                    "stderr": ""}
        return {"exit": 0, "stdout": "not completion evidence", "stderr": ""}

    result = guardian.dispatch_batch(plan, True, powershell_binding)
    assert result["status"] == "output_needs_review"
    assert len(calls) == 2


def test_stale_batch_lock_needs_task_settlement_before_recovery(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    guardian = load()
    guardian.lane_machine.REPO_ROOT = tmp_path
    monkeypatch.setattr(guardian, "_process_alive", lambda pid: False, raising=False)
    plan = guardian.plan_batch("B-crash", rows()[:1], {"effective": "on"})
    folder = tmp_path / "state" / "guardian-batches"
    folder.mkdir(parents=True)
    lock = folder / "B-crash.lock"
    lock.write_text(json.dumps({"batch_id": "B-crash", "pid": 999999}), encoding="utf8")
    record = folder / "B-crash.json"
    record.write_text(json.dumps({"batch_id": "B-crash", "delivery_accepted": False,
        "status": "running", "plan_sha256": guardian._plan_sha256(plan),
        "tasks": {"local-a": {"lane": "alpha", "opener_id": "A1",
                              "status": "running", "wave": 1}}}), encoding="utf8")
    task = tmp_path / "state" / "runs" / "local-a"
    task.mkdir(parents=True)
    (task / "running.lock").write_text("attempt still unresolved", encoding="utf8")
    (task / "state.json").write_text(json.dumps({"phase_status": "running"}), encoding="utf8")
    first = guardian.recover_batch("B-crash")
    assert first["status"] == "blocked_unknown"
    assert lock.exists()
    assert json.loads(record.read_text(encoding="utf8"))["tasks"]["local-a"]["status"] == "running"

    (task / "running.lock").unlink()
    (task / "state.json").write_text(json.dumps({"phase_status": "paused"}), encoding="utf8")
    second = guardian.recover_batch("B-crash")
    assert second["status"] == "needs_manual_wake"
    assert not lock.exists()
    saved = json.loads(record.read_text(encoding="utf8"))
    assert saved["tasks"]["local-a"]["status"] == "paused"
    assert saved["status"] == "recovered"
    assert saved["recovery"]["pid"] == 999999
    assert guardian.lane_machine._read_state()["lanes"]["alpha"]["status"] == "paused"


def test_crash_before_model_can_recover_pending_and_continue_once(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    guardian = load()
    guardian.lane_machine.REPO_ROOT = tmp_path
    monkeypatch.setattr(guardian, "_process_alive", lambda pid: False, raising=False)
    plan = guardian.plan_batch("B-pending", rows()[:1], {"effective": "on"})
    folder = tmp_path / "state" / "guardian-batches"
    folder.mkdir(parents=True)
    (folder / "B-pending.lock").write_text(
        json.dumps({"batch_id": "B-pending", "pid": 999999}), encoding="utf8")
    (folder / "B-pending.json").write_text(json.dumps({
        "batch_id": "B-pending", "delivery_accepted": False, "status": "running",
        "plan_sha256": guardian._plan_sha256(plan),
        "tasks": {"local-a": {"lane": "alpha", "opener_id": "A1",
                              "status": "pending", "wave": 1}}}), encoding="utf8")
    recovered = guardian.recover_batch("B-pending")
    assert recovered["status"] == "needs_manual_wake"
    calls = []
    def advance(task_id, workspace, authorization, executor, model_runner):
        calls.append(task_id)
        return {"status": "ready", "next_phase": "release_ready"}
    monkeypatch.setattr(guardian, "_advance_task", advance)
    first = guardian.run_foreground(plan, {"local-a": tmp_path},
                                    lambda *a, **kw: pytest.fail("no headless"),
                                    transfer_validator=lambda transfer: True)
    second = guardian.run_foreground(plan, {"local-a": tmp_path},
                                     lambda *a, **kw: pytest.fail("no headless"),
                                     transfer_validator=lambda transfer: True)
    assert first["status"] == second["status"] == "release_ready"
    assert calls == ["local-a"]


def test_live_batch_process_cannot_be_recovered(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    guardian = load()
    monkeypatch.setattr(guardian, "_process_alive", lambda pid: True, raising=False)
    folder = tmp_path / "state" / "guardian-batches"
    folder.mkdir(parents=True)
    lock = folder / "B-live.lock"
    lock.write_text(json.dumps({"batch_id": "B-live", "pid": 123}), encoding="utf8")
    (folder / "B-live.json").write_text(json.dumps({
        "batch_id": "B-live", "delivery_accepted": False, "status": "running",
        "tasks": {}}), encoding="utf8")
    assert guardian.recover_batch("B-live")["status"] == "blocked_unknown"
    assert lock.exists()


def test_release_ready_deploy_candidate_records_real_transfer_once(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    guardian = load()
    guardian.lane_machine.REPO_ROOT = tmp_path
    source = [rows()[0], {
        "task_id": "deploy", "opener_id": "A2", "lane": "deploy-lane",
        "touches": ["release"], "action_key": "deploy_51",
        "row": 305, "section": "一", "next_action": "publish reviewed fixture",
        "release_task_id": "local-a", "transfer_binding_sha256": "a" * 64,
    }]
    plan = guardian.plan_batch("B-transfer", source, {"effective": "off"})
    release = guardian._load("release_test", BASE / "workflow_release.py")
    release.lane_machine.REPO_ROOT = tmp_path
    monkeypatch.setattr(release, "_verified", lambda task_id: ({"id": task_id}, ""))
    monkeypatch.setattr(guardian, "_transfer_deploy", release.transfer_deploy, raising=False)
    calls = []
    def advance(task_id, workspace, authorization, executor, model_runner):
        calls.append(task_id)
        return {"status": "ready", "next_phase": "release_ready"}
    monkeypatch.setattr(guardian, "_advance_task", advance)
    first = guardian.run_foreground(plan, {"local-a": tmp_path},
                                    lambda *a, **kw: pytest.fail("no headless"),
                                    transfer_validator=lambda transfer: True)
    second = guardian.run_foreground(plan, {"local-a": tmp_path},
                                     lambda *a, **kw: pytest.fail("no headless"),
                                     transfer_validator=lambda transfer: True)
    assert calls == ["local-a"]
    assert first["status"] == second["status"] == "release_ready"
    record = json.loads((tmp_path / "state" / "guardian-batches" /
                         "B-transfer.json").read_text(encoding="utf8"))
    assert record["transfer_receipts"]["deploy"]["status"] == "transferred"
    lane = release.lane_machine._read_state()["lanes"]["deploy-lane"]
    assert len(lane["transfers"]) == 1
    assert lane["transfers"][0]["batch"] == "B-transfer"
    assert lane["transfers"][0]["action_key"] == "deploy_51"
    with pytest.raises(release.lane_machine.DeployAuthorizationRejected,
                       match="LAN 探针"):
        release.lane_machine.authorize_deploy(
            batch="B-transfer", wave=1, lane="deploy-lane",
            action_key="deploy_51", item=record["transfer_receipts"]["deploy"]["item"],
            authorized_text="fixture authorization, never production",
            prober=lambda: {"status": "off", "on_lan": False})


def test_deploy_transfer_waits_until_source_task_is_release_ready(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    guardian = load()
    guardian.lane_machine.REPO_ROOT = tmp_path
    source = [rows()[0], {
        "task_id": "deploy", "opener_id": "A2", "lane": "deploy-lane",
        "touches": ["release"], "action_key": "deploy_51",
        "row": 305, "section": "一", "next_action": "publish reviewed fixture",
        "release_task_id": "local-a", "transfer_binding_sha256": "a" * 64,
    }]
    plan = guardian.plan_batch("B-transfer-hold", source, {"effective": "off"})
    monkeypatch.setattr(guardian, "_advance_task",
                        lambda *a, **k: {"status": "paused", "reason": "design approval"})
    monkeypatch.setattr(guardian, "_transfer_deploy",
                        lambda *a, **k: pytest.fail("premature production transfer"), raising=False)
    result = guardian.run_foreground(plan, {"local-a": tmp_path},
                                     lambda *a, **kw: pytest.fail("no headless"),
                                     transfer_validator=lambda transfer: True)
    assert result["status"] == "needs_manual_wake"
    assert result["tasks"]["local-a"]["status"] == "paused"


def test_long_foreground_stage_refreshes_heartbeat_until_it_finishes(tmp_path, monkeypatch):
    import time
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    guardian = load()
    guardian.lane_machine.REPO_ROOT = tmp_path
    monkeypatch.setattr(guardian, "_HEARTBEAT_INTERVAL_SECONDS", 0.01, raising=False)
    plan = guardian.plan_batch("B-heart", rows()[:1], {"effective": "on"})
    def advance(*args):
        time.sleep(0.07)
        return {"status": "ready", "next_phase": "release_ready"}
    monkeypatch.setattr(guardian, "_advance_task", advance)
    result = guardian.run_foreground(plan, {"local-a": tmp_path},
                                     lambda *a, **kw: pytest.fail("no headless"))
    assert result["status"] == "release_ready"
    path = guardian.lane_machine.resolve_heartbeat_path(
        guardian.lane_machine.heartbeat_rel_path("alpha"))
    assert "still running" in path.read_text(encoding="utf8")


def test_invalid_driver_result_settles_batch_instead_of_stranding_running_task(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    guardian = load()
    guardian.lane_machine.REPO_ROOT = tmp_path
    plan = guardian.plan_batch("B-invalid", rows()[:1], {"effective": "on"})
    monkeypatch.setattr(guardian, "_advance_task", lambda *a: None)
    result = guardian.run_foreground(plan, {"local-a": tmp_path},
                                     lambda *a, **kw: pytest.fail("no headless"))
    assert result["status"] == "needs_manual_wake"
    assert result["tasks"]["local-a"]["status"] == "blocked"
    record = tmp_path / "state" / "guardian-batches" / "B-invalid.json"
    assert json.loads(record.read_text(encoding="utf8"))["tasks"]["local-a"]["status"] == "blocked"
    assert not record.with_suffix(".lock").exists()


def test_recovery_mutex_blocks_second_reconciler(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    guardian = load()
    monkeypatch.setattr(guardian, "_process_alive", lambda pid: False)
    folder = tmp_path / "state" / "guardian-batches"
    folder.mkdir(parents=True)
    lock = folder / "B-race.lock"
    lock.write_text(json.dumps({"batch_id": "B-race", "pid": 999999}), encoding="utf8")
    (folder / "B-race.json").write_text(json.dumps({
        "batch_id": "B-race", "delivery_accepted": False,
        "status": "running", "tasks": {}}), encoding="utf8")
    recovery_mutex = folder / "B-race.recovery.lock"
    with guardian._recovery_mutex(recovery_mutex):
        result = guardian.recover_batch("B-race")
        assert result["status"] == "blocked_unknown"
        assert lock.exists()
    assert recovery_mutex.exists()


def test_unhandled_batch_error_preserves_owner_lock_for_reconciliation(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    guardian = load()
    guardian.lane_machine.REPO_ROOT = tmp_path
    plan = guardian.plan_batch("B-exception", rows()[:1], {"effective": "on"})
    monkeypatch.setattr(guardian, "_advance_task",
                        lambda *a: {"status": "ready", "next_phase": "release_ready"})
    def fatal(*a):
        raise RuntimeError("unexpected transfer bookkeeping failure")
    monkeypatch.setattr(guardian, "_record_ready_transfers", fatal)
    with pytest.raises(RuntimeError, match="unexpected transfer"):
        guardian.run_foreground(plan, {"local-a": tmp_path},
                                lambda *a, **kw: pytest.fail("no headless"))
    record = tmp_path / "state" / "guardian-batches" / "B-exception.json"
    assert record.with_suffix(".lock").exists()
    assert json.loads(record.read_text(encoding="utf8"))["status"] == "running"


def test_uncertain_transfer_attempt_does_not_retry_on_human_wake(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    guardian = load()
    guardian.lane_machine.REPO_ROOT = tmp_path
    source = [rows()[0], {
        "task_id": "deploy", "opener_id": "A2", "lane": "deploy-lane",
        "touches": ["release"], "action_key": "deploy_51", "row": 305,
        "section": "一", "next_action": "publish fixture", "release_task_id": "local-a",
        "transfer_binding_sha256": "a" * 64}]
    plan = guardian.plan_batch("B-transfer-retry", source, {"effective": "off"})
    monkeypatch.setattr(guardian, "_advance_task",
                        lambda *a: {"status": "ready", "next_phase": "release_ready"})
    calls = []
    def transfer(*a, **kw):
        calls.append(a)
        return {"status": "blocked", "reason": "temporary evidence gap"} if len(calls) == 1 else {
            "status": "transferred", "pointer": "LAN closeout"}
    monkeypatch.setattr(guardian, "_transfer_deploy", transfer)
    first = guardian.run_foreground(plan, {"local-a": tmp_path},
                                    lambda *a, **kw: pytest.fail("no headless"),
                                    transfer_validator=lambda transfer: True)
    second = guardian.run_foreground(plan, {"local-a": tmp_path},
                                     lambda *a, **kw: pytest.fail("no headless"),
                                     transfer_validator=lambda transfer: True)
    assert first["status"] == "needs_manual_wake"
    assert second["status"] == "needs_manual_wake"
    assert len(calls) == 1
    record = json.loads((tmp_path / "state" / "guardian-batches" /
                         "B-transfer-retry.json").read_text(encoding="utf8"))
    assert record["transfer_attempts"]["deploy"]["status"] == "calling"


def test_unverified_live_transfer_source_never_writes_authoritative_state(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    guardian = load()
    guardian.lane_machine.REPO_ROOT = tmp_path
    source = [rows()[0], {
        "task_id": "deploy", "opener_id": "A2", "lane": "deploy-lane",
        "touches": ["release"], "action_key": "deploy_51", "row": 305,
        "section": "一", "next_action": "publish fixture", "release_task_id": "local-a",
        "transfer_binding_sha256": "a" * 64}]
    plan = guardian.plan_batch("B-transfer-drift", source, {"effective": "off"})
    monkeypatch.setattr(guardian, "_advance_task",
                        lambda *a: {"status": "ready", "next_phase": "release_ready"})
    monkeypatch.setattr(guardian, "_transfer_deploy",
                        lambda *a, **k: pytest.fail("stale queue reached transfer"))
    result = guardian.run_foreground(plan, {"local-a": tmp_path},
                                     lambda *a, **kw: pytest.fail("no headless"),
                                     transfer_validator=lambda transfer: False)
    assert result["status"] == "needs_manual_wake"
    assert result["transfer_failures"]["deploy"]["reason"] == "live queue/transfer binding changed"


def test_stage_validator_rechecks_before_each_model_stage(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    guardian = load()
    guardian.lane_machine.REPO_ROOT = tmp_path
    plan = guardian.plan_batch("B-stage-guard", rows()[:1], {"effective": "on"})
    advances = []
    validations = []
    def advance(task_id, workspace, authorization, executor, model_runner):
        advances.append(task_id)
        return {"status": "ready", "next_phase": "implement"}
    def validate(task_id):
        validations.append(task_id)
        return len(validations) <= 2
    monkeypatch.setattr(guardian, "_advance_task", advance)
    result = guardian.dispatch_batch(plan, True, lambda *a, **kw: None,
                                     workspaces={"local-a": tmp_path},
                                     stage_validator=validate)
    assert result["tasks"]["local-a"]["status"] == "blocked"
    assert advances == ["local-a"]
    assert validations == ["local-a", "local-a", "local-a"]


def test_transfer_only_batch_carries_completed_source_without_model(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    guardian = load()
    guardian.lane_machine.REPO_ROOT = tmp_path
    source = [{
        "task_id": "deploy-next", "opener_id": "A1", "lane": "lan-closeout",
        "touches": ["release"], "action_key": "deploy_51",
        "row": 649, "section": "一", "next_action": "deploy fixture to .51",
        "release_task_id": "completed-source",
        "release_reference": {"batch_id": "B-prior", "source_wave": 1,
                              "source_plan_sha256": "b" * 64,
                              "source_head": "c" * 40,
                              "source_row": 648, "source_section": "一",
                              "source_queue_full_sha256": "d" * 64},
        "transfer_binding_sha256": "a" * 64,
    }]
    plan = guardian.plan_batch("B-transfer-only", source, {"effective": "off"})
    assert plan["dispatchable_ids"] == []
    transfers = []
    monkeypatch.setattr(guardian, "_carry_source_verified", lambda transfer: True)
    monkeypatch.setattr(guardian, "_transfer_deploy",
                        lambda *args, **kwargs: transfers.append((args, kwargs)) or
                        {"status": "transferred"})
    result = guardian.dispatch_batch(plan, True, lambda *args, **kwargs: None,
                                     workspaces={}, transfer_validator=lambda transfer: True)
    assert result["status"] == "release_ready"
    assert result["transfer_receipts"]["deploy-next"]["status"] == "transferred"
    assert len(transfers) == 1
    assert transfers[0][0][0] == "completed-source"


def test_foreground_independent_lanes_run_concurrently_with_stagger(tmp_path, monkeypatch):
    import threading
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    guardian = load()
    guardian.lane_machine.REPO_ROOT = tmp_path
    source = [
        {"task_id": "a", "opener_id": "A1", "lane": "alpha",
         "touches": ["service/a"], "action_key": "worktree_local_build"},
        {"task_id": "b", "opener_id": "A2", "lane": "beta",
         "touches": ["service/b"], "action_key": "worktree_local_build"},
    ]
    plan = guardian.plan_batch("B-parallel", source, {"effective": "on"})
    assert plan["waves"][0]["task_ids"] == ["a", "b"]
    rendezvous = threading.Barrier(2)
    starts = []
    stagger_calls = []
    monkeypatch.setattr(guardian, "_stagger_sleep",
                        lambda seconds: stagger_calls.append(seconds), raising=False)

    def advance(task_id, *_args):
        starts.append(task_id)
        rendezvous.wait(timeout=2)
        return {"status": "ready", "next_phase": "release_ready"}

    monkeypatch.setattr(guardian, "_advance_task", advance)
    result = guardian.run_foreground(
        plan, {"a": tmp_path / "a", "b": tmp_path / "b"},
        lambda *a, **kw: pytest.fail("no headless"))
    assert result["status"] == "release_ready", result
    assert set(starts) == {"a", "b"}
    assert stagger_calls == [90]


def test_legacy_transfer_without_attempt_ledger_cannot_restart_when_state_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    guardian = load()
    guardian.lane_machine.REPO_ROOT = tmp_path
    row = {
        "task_id": "deploy", "opener_id": "A1", "lane": "lan-closeout",
        "touches": ["release"], "action_key": "deploy_51",
        "row": 649, "section": "一", "next_action": "deploy fixture",
        "release_task_id": "source",
        "release_reference": {"batch_id": "old", "source_wave": 1,
                              "source_plan_sha256": "b" * 64,
                              "source_head": "c" * 40,
                              "source_row": 648, "source_section": "一",
                              "source_queue_full_sha256": "d" * 64},
        "transfer_binding_sha256": "a" * 64,
    }
    plan = guardian.plan_batch("B-legacy", [row], {"effective": "off"})
    record = guardian.initial_batch_record(plan)
    record.pop("transfer_attempts")
    record["status"] = "blocked"
    record["transfer_failures"] = {"deploy": {"status": "blocked"}}
    path = tmp_path / "state" / "guardian-batches" / "B-legacy.json"
    path.parent.mkdir(parents=True)
    guardian._save_batch_record(path, record)
    monkeypatch.setattr(guardian, "_carry_source_verified", lambda transfer: True)
    transfers = []
    monkeypatch.setattr(guardian, "_transfer_deploy",
                        lambda *args, **kwargs: transfers.append(1) or {"status": "transferred"})
    result = guardian.run_foreground(
        plan, {}, lambda *args, **kwargs: None,
        transfer_validator=lambda transfer: True)
    assert result["status"] == "needs_manual_wake"
    assert result["transfer_receipts"] == {}
    assert transfers == []
    assert "transfer_attempts" not in guardian._read_batch_record(path, "B-legacy")


def test_transfer_items_share_guardian_batch_capacity():
    guardian = load()
    source = []
    for index in range(11):
        source.append({
            "task_id": f"deploy-{index}", "opener_id": f"A{index + 1}",
            "lane": f"lane-{index}", "touches": [f"release/{index}"],
            "action_key": "deploy_51", "row": 700 + index,
            "section": "一", "next_action": "transfer fixture",
            "release_task_id": "completed-source",
            "release_reference": {"batch_id": "B-prior", "source_wave": 1,
                                  "source_plan_sha256": "b" * 64,
                                  "source_head": "c" * 40,
                                  "source_row": 648, "source_section": "一",
                                  "source_queue_full_sha256": "d" * 64},
            "transfer_binding_sha256": "a" * 64,
        })
    plan = guardian.plan_batch("B-cap", source, {"effective": "off"})
    assert len(plan["transfers"]) == 10
    assert plan["excluded"]["deploy-10"] == "batch capacity"
    assert any(item["task_id"] == "deploy-10" for item in plan["lan_holds"])



def test_shared_claim_mutex_waits_for_short_normal_contention(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    import time

    guardian = load()
    path = tmp_path / "shared.mutex"
    entered = Event()
    release = Event()

    def holder():
        with guardian._recovery_mutex(path):
            entered.set()
            assert release.wait(3)

    def contender():
        with guardian._recovery_mutex(path):
            return "acquired"

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(holder)
        assert entered.wait(2)
        second = pool.submit(contender)
        try:
            time.sleep(0.05)
            assert not second.done(), "normal lock contention must wait, not fail"
        finally:
            release.set()
        first.result(timeout=3)
        assert second.result(timeout=3) == "acquired"


def test_shared_claim_mutex_times_out_closed(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    guardian = load()
    path = tmp_path / "shared.mutex"
    entered = Event()
    release = Event()

    def holder():
        with guardian._recovery_mutex(path):
            entered.set()
            assert release.wait(3)

    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(holder)
        assert entered.wait(2)
        try:
            with pytest.raises(TimeoutError, match="mutex"):
                with guardian._recovery_mutex(path, timeout_seconds=0.1):
                    pytest.fail("contended mutex was entered")
        finally:
            release.set()
        first.result(timeout=3)
def test_v2_plan_fingerprint_drops_only_verified_raw_stdout_hashes():
    guardian = load()
    plan = guardian.plan_batch("B-fingerprint-v2", rows(), {"effective": "off"})
    plan["waves"] = [{"task_ids": ["local-a"]}, {"task_ids": ["local-b"]}]
    plan["dry_run"] = {"status": "dry_run_verified", "lint_stdout_sha256": "a" * 64,
        "future_audit_field": "keep-bound", "receipts": [
            {"task_ids": ["local-a"], "lanes": ["alpha"], "stdout_sha256": "b" * 64,
             "future_receipt_field": "keep-bound"},
            {"task_ids": ["local-b"], "lanes": ["beta"], "stdout_sha256": "c" * 64}]}
    same = json.loads(json.dumps(plan))
    same["dry_run"]["lint_stdout_sha256"] = "d" * 64
    same["dry_run"]["receipts"][0]["stdout_sha256"] = "e" * 64
    assert guardian._plan_sha256(plan) == guardian._plan_sha256(same)
    mutations = (
        lambda p: p["dry_run"]["receipts"].reverse(),
        lambda p: p["dry_run"]["receipts"][0].update(task_ids=["other"]),
        lambda p: p["dry_run"]["receipts"][0].update(lanes=["other"]),
        lambda p: p["dry_run"]["receipts"][0].pop("lanes"),
        lambda p: p["dry_run"]["receipts"][0].update(stdout_sha256="invalid"),
        lambda p: p["dry_run"]["receipts"].pop(),
        lambda p: p["dry_run"].update(status="dry_run_failed"),
        lambda p: p["dry_run"].update(future_audit_field="tampered"),
        lambda p: p["dry_run"]["receipts"][0].update(future_receipt_field="tampered"),
        lambda p: p.update(batch_id="B-other"),
        lambda p: p.update(mode="headless"),
        lambda p: p.update(file="elsewhere.md"),
        lambda p: p.update(lan="on"),
        lambda p: p.update(lan_observed="unknown"),
        lambda p: p.update(dispatchable_ids=["other"]),
        lambda p: p.update(excluded={"other": "held"}),
        lambda p: p.update(lan_holds=[{"task_id": "other"}]),
        lambda p: p.update(transfers=[{"task_id": "other"}]),
        lambda p: p.update(waves=list(reversed(p["waves"]))),
        lambda p: p.update(lane_ids=["other"]),
        lambda p: p.update(opener_ids=["A9"]),
        lambda p: p["entries"][0].update(opener_id="A9"),
        lambda p: p["entries"][0].update(action_key="deploy_51"),
        lambda p: p.update(queue_evidence=[{"task_id": "changed"}]),
        lambda p: p.update(lan_evidence={"effective": "on"}),
        lambda p: p.update(execution_bindings={"workspaces": {"local-a": "elsewhere"},
                                                "authorizations": {"local-a": "changed"}}),
        lambda p: p.update(watch_sha256="f" * 64),
        lambda p: p.update(candidates_sha256="e" * 64),
        lambda p: p.update(max_items=9),
        lambda p: p.update(max_parallel=3),
        lambda p: p.update(stagger_seconds=91),
    )
    for mutation_index, mutate in enumerate(mutations):
        changed = json.loads(json.dumps(plan))
        mutate(changed)
        assert guardian._plan_sha256(plan) != guardian._plan_sha256(changed), (
            f"identity mutation #{mutation_index} was not fingerprinted")


def test_v1_digest_is_exact_legacy_and_unknown_version_fails_closed():
    guardian = load()
    plan = guardian.plan_batch("B-fingerprint-v1", rows(), {"effective": "off"})
    plan.pop("plan_fingerprint_version")
    plan["dry_run"] = {"status": "dry_run_verified", "lint_stdout_sha256": "a" * 64,
        "receipts": [{"task_ids": ["local-a"], "lanes": ["alpha"],
                      "stdout_sha256": "b" * 64}]}
    fields = ("batch_id", "mode", "file", "lan", "lan_observed", "dispatchable_ids",
        "excluded", "lan_holds", "transfers", "waves", "lane_ids", "opener_ids", "entries",
        "queue_evidence", "lan_evidence", "execution_bindings", "watch_sha256",
        "candidates_sha256", "dry_run", "max_items", "max_parallel", "stagger_seconds")
    legacy = {key: plan.get(key) for key in fields}
    digest = guardian.hashlib.sha256(json.dumps(legacy, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode("utf8")).hexdigest()
    assert guardian._plan_sha256(plan) == digest
    assert guardian._plan_sha256(plan) != guardian._plan_sha256({**plan,
        "plan_fingerprint_version": guardian.PLAN_FINGERPRINT_VERSION})
    changed = json.loads(json.dumps(plan))
    changed["dry_run"]["lint_stdout_sha256"] = "c" * 64
    assert guardian._plan_sha256(plan) != guardian._plan_sha256(changed)
    for bad_version in (True, 1.0, "1", None, 99):
        with pytest.raises(ValueError, match="fingerprint version"):
            guardian._plan_sha256({**plan, "plan_fingerprint_version": bad_version})
def test_guardian_advance_pins_explicit_luna_model(monkeypatch, tmp_path):
    guardian = load()
    captured = {}

    class Driver:
        @staticmethod
        def advance(*args, **kwargs):
            captured["kwargs"] = kwargs
            return {"status": "stage_output_needs_review"}

    monkeypatch.setattr(guardian, "_load", lambda name, path: Driver)
    result = guardian._advance_task(
        "workflow-path-guard-v5-mvp-0930-r2", tmp_path, None, lambda: None, None)
    assert result["status"] == "stage_output_needs_review"
    assert captured["kwargs"]["model"] == "gpt-6-luna"
