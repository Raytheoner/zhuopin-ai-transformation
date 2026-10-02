"""Human-start guardian entry tests exercise queue, LAN, lint and DryRun boundaries."""
import importlib.util
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location("guardian_entry_under_test", BASE / "guardian_entry.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def candidate(task_id="local-a", row=648, opener="A1", lane="alpha", *,
              lan_required=False, action="worktree_local_build"):
    return {"task_id": task_id, "row": row, "section": "一",
            "task_excerpt": "fixture scenario", "next_action": "build fixture scenario",
            "opener_id": opener, "lane": lane, "touches": ["fixture/service"],
            "action_key": action, "lan_required": lan_required}


def manifest(tmp_path, rows):
    watch = tmp_path / "watch.md"
    watch.write_text("controlled watch-piece", encoding="utf8")
    for row in rows:
        external = tmp_path.parent / (tmp_path.name + "-external")
        external.mkdir(exist_ok=True)
        path = external / ("lan-decision-" + row["task_id"] + ".json")
        path.write_text(json.dumps({
            "task_id": row["task_id"], "row": row["row"],
            "section": row["section"], "action_key": row["action_key"],
            "queue_full_sha256": hashlib.sha256(
                b"fixture scenario | build fixture scenario").hexdigest(),
            "lan_required": row.get("lan_required"),
            "next_action": row.get("next_action", ""),
            "lane": row["lane"], "touches": row["touches"],
            "text": "Human classifies this fixture's LAN dependency.",
        }), encoding="utf8")
        row["lan_decision"] = str(path)
    return {"batch_id": "B-human", "watch_piece": str(watch), "candidates": rows}


def executor(calls):
    def run(argv, **kwargs):
        calls.append(list(map(str, argv)))
        if "--format" in argv:
            row = int(argv[argv.index("--row") + 1])
            return {"exit": 0, "stdout": json.dumps({
                "row": str(row), "section": "一", "found": True, "carrier": "live",
                "file": "queue.md", "line": row + 10, "status_field": "open",
                "done": False, "reason": "open", "error": None, "read_errors": [],
                "searched": ["queue.md"]}), "stderr": ""}
        if "--field" in argv:
            return {"exit": 0, "stdout": "fixture scenario | build fixture scenario",
                    "stderr": ""}
        if "-DryRun" in argv:
            return {"exit": 0, "stdout": "泳道 1 条：\n  ◆ alpha ：A1（泳道内串行）",
                    "stderr": ""}
        return {"exit": 0, "stdout": "lint clean", "stderr": ""}
    return run


def test_human_start_defaults_to_workflow_driver_executor(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    monkeypatch.setattr(entry, "ROOT", tmp_path)
    calls = []
    default = executor(calls)
    original_load = entry.guardian._load

    def load_driver(name, path):
        module = original_load(name, path)
        if name == "driver":
            module.default_executor = default
        return module

    monkeypatch.setattr(entry.guardian, "_load", load_driver)
    monkeypatch.setattr(entry.handoff, "execute",
                        lambda *args, **kwargs: pytest.fail("bypassed workflow_driver.default_executor"))

    result = entry.start(manifest(tmp_path, [candidate()]),
                         lan_prober=lambda: {"status": "on", "effective": "on"}, run=False)

    assert result["status"] == "planned", result
    assert any("--format" in call for call in calls)
    assert any("--file" in call and "--enforce" in call for call in calls)
    assert any("-DryRun" in call for call in calls)


def test_human_start_off_lan_persists_reviewable_hold_without_model(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    calls = []
    data = manifest(tmp_path, [
        candidate(), candidate("lan-only", 649, "A2", "lan-lane", lan_required=True),
    ])
    result = entry.start(data, executor=executor(calls),
                         lan_prober=lambda: {"status": "off", "effective": "off"},
                         run=False)
    assert result["status"] == "planned"
    assert result["plan"]["dispatchable_ids"] == ["local-a"]
    assert result["plan"]["lan_holds"][0]["row"] == 649
    assert result["plan"]["lan_holds"][0]["next_action"] == "build fixture scenario"
    assert any("--format" in call for call in calls)
    assert any("--field" in call for call in calls)
    assert any("--file" in call and "--enforce" in call for call in calls)
    assert any("-DryRun" in call for call in calls)
    assert all("-ConsumerEnabled" not in call for call in calls)
    saved = tmp_path / "state" / "guardian-plans" / "B-human.json"
    assert saved.is_file()
    assert json.loads(saved.read_text(encoding="utf8"))["lan_holds"][0]["row"] == 649


def test_human_start_rejects_non_live_row_before_dryrun(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    calls = []

    def bad(argv, **kwargs):
        result = executor(calls)(argv, **kwargs)
        if "--format" in argv:
            result["stdout"] = json.dumps({
                "row": "648", "section": "一", "found": True, "carrier": "archive",
                "file": "archive.md", "line": 1, "done": False,
                "error": None, "read_errors": []})
        return result

    result = entry.start(manifest(tmp_path, [candidate()]), executor=bad,
                         lan_prober=lambda: {"status": "on", "effective": "on"},
                         run=True)
    assert result["status"] == "blocked"
    assert "queue" in result["reason"]
    assert all("-DryRun" not in call for call in calls)


def test_human_start_requires_prepared_matching_task_before_model(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    calls = []
    data = manifest(tmp_path, [candidate()])
    data["workspaces"] = {"local-a": str(tmp_path)}
    result = entry.start(data, executor=executor(calls),
                         lan_prober=lambda: {"status": "on", "effective": "on"},
                         run=True)
    assert result["status"] == "blocked"
    assert "prepared" in result["reason"]
    assert all("-ConsumerEnabled" not in call for call in calls)


def test_human_start_exact_prepared_state_advances_and_second_wake_does_not_relaunch(
        tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    entry.guardian.lane_machine.REPO_ROOT = tmp_path
    workspace = _prepared_source(entry, tmp_path)
    data = manifest(tmp_path, [candidate()])
    data["workspaces"] = {"local-a": str(workspace)}
    advances = []

    def advance(task_id, workspace, authorization, executor, model_runner):
        advances.append(task_id)
        return {"status": "ready", "next_phase": "release_ready"}

    monkeypatch.setattr(entry.guardian, "_advance_task", advance)
    first = entry.start(data, executor=executor([]),
                        lan_prober=lambda: {"status": "on", "effective": "on"},
                        run=True)
    second = entry.start(data, executor=executor([]),
                         lan_prober=lambda: {"status": "on", "effective": "on"},
                         run=True)
    assert first["tasks"]["local-a"]["status"] == "release_ready"
    assert first["status"] == "release_ready"
    assert second["status"] == "release_ready"
    assert first["delivery_accepted"] is False
    assert advances == ["local-a"]



def test_same_batch_live_queue_change_requires_new_review(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    data = manifest(tmp_path, [candidate()])
    first = entry.start(data, executor=executor([]),
                        lan_prober=lambda: {"status": "on", "effective": "on"},
                        run=False)
    assert first["status"] == "planned"

    def changed(argv, **kwargs):
        result = executor([])(argv, **kwargs)
        if "--field" in argv:
            result["stdout"] += " | changed queue requirement"
        return result

    decision_path = Path(data["candidates"][0]["lan_decision"])
    decision = json.loads(decision_path.read_text(encoding="utf8"))
    decision["queue_full_sha256"] = hashlib.sha256(
        b"fixture scenario | build fixture scenario | changed queue requirement").hexdigest()
    decision_path.write_text(json.dumps(decision), encoding="utf8")
    second = entry.start(data, executor=changed,
                         lan_prober=lambda: {"status": "on", "effective": "on"},
                         run=True)
    assert second["status"] == "blocked"
    assert "plan changed" in second["reason"]



def test_prepared_queue_anchor_must_match_current_live_locator(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    state = tmp_path / "state" / "runs" / "local-a"
    state.mkdir(parents=True)
    sealed = state / "queue.json"
    sealed.write_text(json.dumps({"stdout": json.dumps({
        "row": "648", "section": "一", "found": True, "carrier": "live",
        "file": "queue.md", "line": 100, "done": False,
        "error": None, "read_errors": []})}), encoding="utf8")
    (state / "state.json").write_text(json.dumps({
        "id": "local-a", "row": 648, "section": "一",
        "action_key": "worktree_local_build",
        "queue_ref": {"path": str(sealed),
                      "sha256": hashlib.sha256(sealed.read_bytes()).hexdigest()},
    }), encoding="utf8")
    data = manifest(tmp_path, [candidate()])
    data["workspaces"] = {"local-a": str(tmp_path)}
    result = entry.start(data, executor=executor([]),
                         lan_prober=lambda: {"status": "on", "effective": "on"},
                         run=True)
    assert result["status"] == "blocked"
    assert "queue anchor" in result["reason"]


def test_two_openers_bind_as_one_powershell_only_argument(tmp_path):
    entry = load()
    file = tmp_path / "watch.md"
    file.write_text("fixture", encoding="utf8")
    plan = {"file": str(file), "entries": [
        {"task_id": "one", "opener_id": "A1", "lane": "alpha"},
        {"task_id": "two", "opener_id": "A2", "lane": "beta"},
    ], "waves": [{"task_ids": ["one", "two"]}],
            "max_parallel": 4, "stagger_seconds": 90}
    calls = []

    def powershell_binding(argv, **kwargs):
        calls.append(argv)
        if "-DryRun" in argv:
            index = argv.index("-Only")
            if argv[index + 1] != "A1,A2" or "A2" in argv[index + 2:]:
                return {"exit": 20, "stdout": "",
                        "stderr": "A positional parameter cannot be found that accepts argument A2"}
            return {"exit": 0, "stdout": "泳道 2 条：\n  ◆ alpha ：A1（泳道内串行）\n  ◆ beta ：A2（泳道内串行）",
                    "stderr": ""}
        return {"exit": 0, "stdout": "lint clean", "stderr": ""}

    result = entry._dry_run(plan, powershell_binding)
    assert result["status"] == "dry_run_verified"
    assert len(calls) == 2


def test_reviewed_watch_piece_bytes_cannot_change_before_run(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    data = manifest(tmp_path, [candidate()])
    assert entry.start(data, executor=executor([]),
                       lan_prober=lambda: {"status": "on"}, run=False)["status"] == "planned"
    Path(data["watch_piece"]).write_text("changed opener body", encoding="utf8")
    second = entry.start(data, executor=executor([]),
                         lan_prober=lambda: {"status": "on"}, run=False)
    assert second["status"] == "blocked"
    assert "plan changed" in second["reason"]


def test_reviewed_candidate_action_cannot_change_before_run(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    data = manifest(tmp_path, [candidate()])
    assert entry.start(data, executor=executor([]),
                       lan_prober=lambda: {"status": "on"}, run=False)["status"] == "planned"
    data["candidates"][0]["next_action"] = "a different task"
    decision_path = Path(data["candidates"][0]["lan_decision"])
    decision = json.loads(decision_path.read_text(encoding="utf8"))
    decision["next_action"] = "a different task"
    decision_path.write_text(json.dumps(decision), encoding="utf8")
    second = entry.start(data, executor=executor([]),
                         lan_prober=lambda: {"status": "on"}, run=False)
    assert second["status"] == "blocked"
    assert "next action" in second["reason"]


def test_prepared_queue_full_text_must_match_current_live_row(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    folder = tmp_path / "state" / "runs" / "local-a"
    folder.mkdir(parents=True)
    sealed = folder / "queue.json"
    sealed.write_text(json.dumps({"stdout": json.dumps({
        "row": "648", "section": "一", "found": True, "carrier": "live",
        "file": "queue.md", "line": 658, "done": False,
        "error": None, "read_errors": []})}), encoding="utf8")
    (folder / "state.json").write_text(json.dumps({
        "id": "local-a", "row": 648, "section": "一",
        "action_key": "worktree_local_build",
        "queue_ref": {"path": str(sealed),
                      "sha256": hashlib.sha256(sealed.read_bytes()).hexdigest()},
        "queue_full_sha256": hashlib.sha256(b"older queue text").hexdigest(),
    }), encoding="utf8")
    data = manifest(tmp_path, [candidate()])
    data["workspaces"] = {"local-a": str(tmp_path)}
    result = entry.start(data, executor=executor([]),
                         lan_prober=lambda: {"status": "on"}, run=True)
    assert result["status"] == "blocked"
    assert "queue" in result["reason"]


def test_competing_first_plan_cannot_be_overwritten(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    data = manifest(tmp_path, [candidate()])
    plan_path = tmp_path / "state" / "guardian-plans" / "B-human.json"
    original_link = entry.os.link

    def competing_link(source, target):
        if Path(target) == plan_path:
            plan_path.write_text(json.dumps({
                "batch_id": "B-human", "candidates_sha256": "other"}), encoding="utf8")
            raise FileExistsError(str(target))
        return original_link(source, target)

    monkeypatch.setattr(entry.os, "link", competing_link)
    result = entry.start(data, executor=executor([]),
                         lan_prober=lambda: {"status": "on"}, run=False)
    assert result["status"] == "blocked"
    assert "plan changed" in result["reason"]
    assert json.loads(plan_path.read_text(encoding="utf8"))["candidates_sha256"] == "other"


def test_human_start_requires_next_action_even_for_local_green(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    row = candidate()
    row.pop("next_action")
    result = entry.start(manifest(tmp_path, [row]), executor=executor([]),
                         lan_prober=lambda: {"status": "on"}, run=False)
    assert result["status"] == "blocked"
    assert "next_action" in result["reason"]


def test_excluded_non_lan_candidate_is_not_reported_as_lan_hold(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    row = candidate(action="merge_to_master")
    result = entry.start(manifest(tmp_path, [row]), executor=executor([]),
                         lan_prober=lambda: {"status": "on"}, run=True)
    assert result["status"] == "no_dispatchable_candidates"
    assert result["plan"]["lan_holds"] == []


def test_one_live_queue_row_cannot_be_scheduled_as_two_tasks(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    data = manifest(tmp_path, [candidate(),
        candidate("second", 648, "A2", "beta")])
    result = entry.start(data, executor=executor([]),
                         lan_prober=lambda: {"status": "on"}, run=False)
    assert result["status"] == "blocked"
    assert "duplicate queue row" in result["reason"]


def test_missing_lan_classification_cannot_default_to_local(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    row = candidate()
    row.pop("lan_required")
    result = entry.start(manifest(tmp_path, [row]), executor=executor([]),
                         lan_prober=lambda: {"status": "off"}, run=False)
    assert result["status"] == "blocked"
    assert "lan_required" in result["reason"]


def _prepared_source(entry, tmp_path):
    origin = tmp_path / "git-origin"
    origin.mkdir()
    def git(*args, cwd=origin):
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                              text=True, encoding="utf8", check=True).stdout.strip()
    git("init", "-q")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.com")
    (origin / "AGENTS.md").write_text("fixture only", encoding="utf8")
    git("add", "AGENTS.md")
    git("commit", "-qm", "fixture")
    workspace = tmp_path / "workspace"
    git("worktree", "add", "--detach", str(workspace), "HEAD")
    common_dir = git("rev-parse", "--path-format=absolute", "--git-common-dir",
                     cwd=workspace)
    folder = tmp_path / "state" / "runs" / "local-a"
    folder.mkdir(parents=True)
    query = folder / "queue.json"
    query.write_text(json.dumps({"stdout": json.dumps({
        "row": "648", "section": "一", "found": True, "carrier": "live",
        "file": "queue.md", "line": 658, "done": False,
        "error": None, "read_errors": []})}), encoding="utf8")
    (folder / "state.json").write_text(json.dumps({
        "id": "local-a", "row": 648, "section": "一",
        "action_key": "worktree_local_build", "status": "prepared",
        "source_git_common_dir": common_dir,
        "source_checkout": str(origin),
        "queue_full_sha256": hashlib.sha256(
            b"fixture scenario | build fixture scenario").hexdigest(),
        "queue_ref": {"path": str(query), "sha256": hashlib.sha256(query.read_bytes()).hexdigest()},
    }), encoding="utf8")
    return workspace


def _bound_transfer_manifest(tmp_path, workspace):
    source = candidate()
    deploy = candidate("deploy-a", 649, "A2", "lan-lane",
                       lan_required=True, action="deploy_51")
    deploy["release_task_id"] = "local-a"
    binding = tmp_path / "transfer-binding.json"
    binding.write_text(json.dumps({
        "source_task_id": "local-a", "deploy_task_id": "deploy-a",
        "source_row": 648, "source_section": "一",
        "deploy_row": 649, "deploy_section": "一",
        "source_queue_full_sha256": hashlib.sha256(
            b"fixture scenario | build fixture scenario").hexdigest(),
        "deploy_queue_full_sha256": hashlib.sha256(
            b"fixture scenario | build fixture scenario").hexdigest(),
        "deploy_next_action": "build fixture scenario",
        "deploy_lane": "lan-lane",
        "text": "Human confirms deploy-a is the LAN closeout of local-a.",
    }), encoding="utf8")
    deploy["transfer_binding"] = str(binding)
    data = manifest(tmp_path, [source, deploy])
    data["workspaces"] = {"local-a": str(workspace)}
    return data, binding


def test_entry_transfers_bound_release_ready_task_with_live_recheck(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    entry.guardian.lane_machine.REPO_ROOT = tmp_path
    workspace = _prepared_source(entry, tmp_path)
    data, binding = _bound_transfer_manifest(tmp_path, workspace)
    monkeypatch.setattr(entry.guardian, "_advance_task",
                        lambda *args: {"status": "ready", "next_phase": "release_ready"})
    transfers = []
    monkeypatch.setattr(entry.guardian, "_transfer_deploy",
                        lambda *args, **kwargs: transfers.append((args, kwargs)) or {"status": "transferred"})
    calls = []
    result = entry.start(data, executor=executor(calls),
                         lan_prober=lambda: {"status": "off"}, run=True)
    assert result["tasks"]["local-a"]["status"] == "release_ready"
    assert "deploy-a" in result["transfer_receipts"], result["transfer_failures"]
    assert result["transfer_receipts"]["deploy-a"]["status"] == "transferred"
    assert len(transfers) == 1
    assert sum("--field" in call for call in calls) >= 4


def test_entry_rechecks_live_deploy_row_after_model_before_transfer(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    entry.guardian.lane_machine.REPO_ROOT = tmp_path
    workspace = _prepared_source(entry, tmp_path)
    data, _ = _bound_transfer_manifest(tmp_path, workspace)
    changed = {"now": False}
    monkeypatch.setattr(entry.guardian, "_advance_task",
                        lambda *args: changed.update(now=True) or
                        {"status": "ready", "next_phase": "release_ready"})
    transfers = []
    monkeypatch.setattr(entry.guardian, "_transfer_deploy",
                        lambda *args, **kwargs: transfers.append((args, kwargs)) or {"status": "transferred"})
    def drift(argv, **kwargs):
        result = executor([])(argv, **kwargs)
        if changed["now"] and "--field" in argv and "--row" in argv and argv[argv.index("--row") + 1] == "649":
            result["stdout"] += " | deploy changed"
        return result
    result = entry.start(data, executor=drift,
                         lan_prober=lambda: {"status": "off"}, run=True)
    assert result["batch_phase"] == "blocked", result
    assert result["tasks"]["local-a"]["status"] == "blocked"
    assert result["transfer_receipts"] == {}
    assert transfers == []
    persisted = json.loads((tmp_path / "state" / "guardian-batches" /
                            "B-human.json").read_text(encoding="utf8"))
    assert persisted["transfer_attempts"] == {}
    proof = tmp_path.parent / (tmp_path.name + "-external") / "retire-no-call.json"
    proof.write_text(json.dumps({
        "batch_id": "B-human", "plan_sha256": persisted["plan_sha256"],
        "decision": "retire_stalled_batch",
        "text": "Human retires a rejected transfer that never entered the side effect.",
    }), encoding="utf8")
    retired = entry.retire_batch("B-human", proof)
    assert retired["status"] == "retired", retired
    claims = json.loads((tmp_path / "state" / "guardian-claims.json").read_text(
        encoding="utf8"))["claims"]
    assert "row:一:649" not in claims


def test_partial_first_plan_write_never_publishes_record(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    data = manifest(tmp_path, [candidate()])
    original_dump = entry.json.dump
    def broken_dump(obj, stream, *args, **kwargs):
        stream.write("{partial")
        raise OSError("simulated disk failure")
    monkeypatch.setattr(entry.json, "dump", broken_dump)
    result = entry.start(data, executor=executor([]),
                         lan_prober=lambda: {"status": "on"}, run=False)
    assert result["status"] == "blocked"
    assert not (tmp_path / "state" / "guardian-plans" / "B-human.json").exists()
    monkeypatch.setattr(entry.json, "dump", original_dump)


def test_transfer_manifest_cannot_relabel_approved_lan_action(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    workspace = _prepared_source(entry, tmp_path)
    data, _ = _bound_transfer_manifest(tmp_path, workspace)
    data["candidates"][1]["next_action"] = "ship an unrelated item"
    decision_path = Path(data["candidates"][1]["lan_decision"])
    decision = json.loads(decision_path.read_text(encoding="utf8"))
    decision["next_action"] = "ship an unrelated item"
    decision_path.write_text(json.dumps(decision), encoding="utf8")
    result = entry.start(data, executor=executor([]),
                         lan_prober=lambda: {"status": "off"}, run=False)
    assert result["status"] == "blocked"
    assert "next action" in result["reason"]


def test_off_lan_false_requires_matching_external_classification(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    data = manifest(tmp_path, [candidate()])
    decision = tmp_path / "lan-decision.json"
    decision.write_text(json.dumps({
        "task_id": "local-a", "row": 648, "section": "一",
        "action_key": "worktree_local_build",
        "queue_full_sha256": hashlib.sha256(
            b"fixture scenario | build fixture scenario").hexdigest(),
        "lan_required": True, "next_action": "build fixture scenario",
        "lane": "alpha", "touches": ["fixture/service"],
        "text": "This task requires internal LAN.",
    }), encoding="utf8")
    data["candidates"][0]["lan_decision"] = str(decision)
    result = entry.start(data, executor=executor([]),
                         lan_prober=lambda: {"status": "off"}, run=False)
    assert result["status"] == "blocked"
    assert "LAN classification" in result["reason"]


def test_first_plan_binds_workspace_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    data = manifest(tmp_path, [candidate()])
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    data["workspaces"] = {"local-a": str(left)}
    first = entry.start(data, executor=executor([]),
                        lan_prober=lambda: {"status": "on"}, run=False)
    assert first["status"] == "planned"
    data["workspaces"]["local-a"] = str(right)
    second = entry.start(data, executor=executor([]),
                         lan_prober=lambda: {"status": "on"}, run=False)
    assert second["status"] == "blocked"
    assert "plan changed" in second["reason"]

def test_touches_cannot_be_relabelled_to_fake_independent_lane(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    data = manifest(tmp_path, [candidate()])
    data["candidates"][0]["touches"] = ["unrelated"]
    result = entry.start(data, executor=executor([]),
                         lan_prober=lambda: {"status": "off"}, run=False)
    assert result["status"] == "blocked"
    assert "LAN classification" in result["reason"]


def test_watch_piece_modified_during_dryrun_is_not_published(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    data = manifest(tmp_path, [candidate()])
    def alter(argv, **kwargs):
        result = executor([])(argv, **kwargs)
        if "-DryRun" in argv:
            Path(data["watch_piece"]).write_text("changed after lint", encoding="utf8")
        return result
    outcome = entry.start(data, executor=alter,
                          lan_prober=lambda: {"status": "on"}, run=False)
    assert outcome["status"] == "blocked"
    assert "watch-piece" in outcome["reason"]
    assert not (tmp_path / "state" / "guardian-plans" / "B-human.json").exists()


def test_queue_changes_during_dryrun_before_dispatch_are_blocked(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    data = manifest(tmp_path, [candidate()])
    changed = {"now": False}
    def alter(argv, **kwargs):
        result = executor([])(argv, **kwargs)
        if "-DryRun" in argv:
            changed["now"] = True
        if changed["now"] and "--field" in argv:
            result["stdout"] += " | changed"
        return result
    outcome = entry.start(data, executor=alter,
                          lan_prober=lambda: {"status": "on"}, run=False)
    assert outcome["status"] == "blocked"
    assert "queue" in outcome["reason"]
    assert not (tmp_path / "state" / "guardian-plans" / "B-human.json").exists()


def test_different_batches_cannot_advance_same_live_queue_row(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    entry.guardian.lane_machine.REPO_ROOT = tmp_path
    first_workspace = tmp_path / "work-a"
    second_workspace = tmp_path / "work-b"
    first_workspace.mkdir()
    second_workspace.mkdir()
    monkeypatch.setattr(entry, "_prepared_workspaces",
                        lambda data, plan: ({task: Path(path) for task, path in data["workspaces"].items()}, {}))
    advances = []
    monkeypatch.setattr(entry.guardian, "_advance_task",
                        lambda task, *args: advances.append(task) or
                        {"status": "ready", "next_phase": "release_ready"})
    first = manifest(tmp_path, [candidate()])
    first["batch_id"] = "B-first"
    first["workspaces"] = {"local-a": str(first_workspace)}
    assert entry.start(first, executor=executor([]),
                       lan_prober=lambda: {"status": "on"}, run=True)["status"] == "release_ready"
    second = manifest(tmp_path, [candidate("local-b")])
    second["batch_id"] = "B-second"
    second["workspaces"] = {"local-b": str(second_workspace)}
    result = entry.start(second, executor=executor([]),
                         lan_prober=lambda: {"status": "on"}, run=True)
    assert result["status"] == "blocked"
    assert "claim" in result["reason"]
    assert advances == ["local-a"]


def test_different_batches_cannot_write_same_workspace_concurrently(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    entry.guardian.lane_machine.REPO_ROOT = tmp_path
    workspace = tmp_path / "shared-work"
    workspace.mkdir()
    monkeypatch.setattr(entry, "_prepared_workspaces",
                        lambda data, plan: ({task: Path(path) for task, path in data["workspaces"].items()}, {}))
    advances = []
    monkeypatch.setattr(entry.guardian, "_advance_task",
                        lambda task, *args: advances.append(task) or
                        {"status": "paused", "reason": "awaiting human design review"})
    first = manifest(tmp_path, [candidate()])
    first["batch_id"] = "B-first"
    first["workspaces"] = {"local-a": str(workspace)}
    first_result = entry.start(first, executor=executor([]),
                               lan_prober=lambda: {"status": "on"}, run=True)
    assert first_result["tasks"]["local-a"]["status"] == "paused"
    second = manifest(tmp_path, [candidate("local-b", 649, "A1", "alpha")])
    second["batch_id"] = "B-second"
    second["workspaces"] = {"local-b": str(workspace)}
    result = entry.start(second, executor=executor([]),
                         lan_prober=lambda: {"status": "on"}, run=True)
    assert result["status"] == "blocked"
    assert "claim" in result["reason"]
    assert advances == ["local-a"]


def test_different_batches_cannot_steal_same_lane_state(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    entry.guardian.lane_machine.REPO_ROOT = tmp_path
    first_workspace = tmp_path / "work-a"
    second_workspace = tmp_path / "work-b"
    first_workspace.mkdir()
    second_workspace.mkdir()
    monkeypatch.setattr(entry, "_prepared_workspaces",
                        lambda data, plan: ({task: Path(path) for task, path in data["workspaces"].items()}, {}))
    advances = []
    monkeypatch.setattr(entry.guardian, "_advance_task",
                        lambda task, *args: advances.append(task) or
                        {"status": "paused", "reason": "human review"})
    first = manifest(tmp_path, [candidate()])
    first["batch_id"] = "B-first"
    first["workspaces"] = {"local-a": str(first_workspace)}
    assert entry.start(first, executor=executor([]),
                       lan_prober=lambda: {"status": "on"}, run=True)["tasks"]["local-a"]["status"] == "paused"
    second = manifest(tmp_path, [candidate("local-b", 649)])
    second["batch_id"] = "B-second"
    second["workspaces"] = {"local-b": str(second_workspace)}
    result = entry.start(second, executor=executor([]),
                         lan_prober=lambda: {"status": "on"}, run=True)
    assert result["status"] == "blocked"
    assert "claim" in result["reason"]
    assert advances == ["local-a"]


def test_entry_adds_item_design_authorization_after_proposal_pause(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    entry.guardian.lane_machine.REPO_ROOT = tmp_path
    workspace = _prepared_source(entry, tmp_path)
    data = manifest(tmp_path, [candidate()])
    data["workspaces"] = {"local-a": str(workspace)}
    calls = []
    def advance(task_id, workspace, authorization, executor, model_runner):
        calls.append(str(authorization) if authorization else None)
        if authorization is None:
            return {"status": "paused", "reason": "design authorization required"}
        return {"status": "ready", "next_phase": "release_ready"}
    monkeypatch.setattr(entry.guardian, "_advance_task", advance)
    first = entry.start(data, executor=executor([]),
                        lan_prober=lambda: {"status": "on"}, run=True)
    assert first["tasks"]["local-a"]["status"] == "paused"
    approval = tmp_path / "design-approval.json"
    approval.write_text('{"text":"Approve design head for this fixture"}', encoding="utf8")
    data["authorizations"] = {"local-a": str(approval)}
    entry.guardian.lane_machine.resume_lane(lane="alpha", answer="设计已审，另附逐项授权")
    second = entry.start(data, executor=executor([]),
                         lan_prober=lambda: {"status": "on"}, run=True)
    assert second["status"] == "release_ready"
    assert calls == [None, str(approval)]
    sealed = tmp_path / "state" / "guardian-authorizations" / "B-human.json"
    assert json.loads(sealed.read_text(encoding="utf8"))["authorizations"]["local-a"]["sha256"] == hashlib.sha256(approval.read_bytes()).hexdigest()
    approval.write_text('{"text":"changed after sealing"}', encoding="utf8")
    third = entry.start(data, executor=executor([]),
                        lan_prober=lambda: {"status": "on"}, run=True)
    assert third["status"] == "blocked"
    assert "authorization" in third["reason"]


def test_retire_stalled_batch_requires_external_evidence_then_releases_claim(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    entry.guardian.lane_machine.REPO_ROOT = tmp_path
    workspace = _prepared_source(entry, tmp_path)
    monkeypatch.setattr(entry, "_prepared_workspaces",
                        lambda data, plan: ({task: Path(path) for task, path in data["workspaces"].items()}, {}))
    calls = []
    monkeypatch.setattr(entry.guardian, "_advance_task",
                        lambda task, *args: calls.append(task) or
                        {"status": "paused", "reason": "review"})
    first = manifest(tmp_path, [candidate()])
    first["batch_id"] = "B-first"
    first["workspaces"] = {"local-a": str(workspace)}
    result = entry.start(first, executor=executor([]),
                         lan_prober=lambda: {"status": "on"}, run=True)
    assert result["tasks"]["local-a"]["status"] == "paused"
    assert entry.retire_batch("B-first", None)["status"] == "blocked"
    evidence = tmp_path / "retire.json"
    evidence.write_text(json.dumps({
        "batch_id": "B-first",
        "plan_sha256": entry.guardian._plan_sha256(result["plan"]) if "plan" in result else
            json.loads((tmp_path / "state" / "guardian-batches" / "B-first.json").read_text(encoding="utf8"))["plan_sha256"],
        "decision": "retire_stalled_batch",
        "text": "Human reviewed the unfinished attempt and retires this batch.",
    }), encoding="utf8")
    retired = entry.retire_batch("B-first", evidence)
    assert retired["status"] == "retired"
    entry.guardian.lane_machine.resume_lane(lane="alpha", answer="stale old-batch answer")
    assert entry.start(first, executor=executor([]),
                       lan_prober=lambda: {"status": "on"}, run=True)["status"] == "retired"
    assert calls == ["local-a"]
    second = manifest(tmp_path, [candidate("local-b")])
    second["batch_id"] = "B-second"
    second["workspaces"] = {"local-b": str(workspace)}
    second_result = entry.start(second, executor=executor([]),
                                lan_prober=lambda: {"status": "on"}, run=True)
    assert second_result["tasks"]["local-b"]["status"] == "paused"
    assert calls == ["local-a", "local-b"]
    assert entry.start(first, executor=executor([]),
                       lan_prober=lambda: {"status": "on"}, run=True)["status"] == "retired"


def test_human_guardian_rejects_primary_checkout_before_claim_or_model(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    entry.guardian.lane_machine.REPO_ROOT = tmp_path
    _prepared_source(entry, tmp_path)
    data = manifest(tmp_path, [candidate()])
    data["workspaces"] = {"local-a": str(tmp_path / "git-origin")}
    builds = []
    monkeypatch.setattr(entry.guardian, "_advance_task",
                        lambda *args: builds.append(1) or {"status": "ready"})
    result = entry.start(data, executor=executor([]),
                         lan_prober=lambda: {"status": "on"}, run=True)
    assert result["status"] == "blocked", result
    assert "source checkout" in result["reason"]
    assert builds == []
    assert not (tmp_path / "state" / "guardian-claims.json").exists()


def test_completed_prior_batch_transfers_without_restarting_model(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    entry.guardian.lane_machine.REPO_ROOT = tmp_path
    workspace = _prepared_source(entry, tmp_path)
    first = manifest(tmp_path, [candidate()])
    first["batch_id"] = "B-prior"
    first["workspaces"] = {"local-a": str(workspace)}
    builds = []
    monkeypatch.setattr(entry.guardian, "_advance_task",
                        lambda *args: builds.append(args) or {
                            "status": "ready", "next_phase": "release_ready"})
    prior = entry.start(first, executor=executor([]),
                        lan_prober=lambda: {"status": "off"}, run=True)
    assert prior["tasks"]["local-a"]["status"] == "release_ready"
    assert len(builds) == 1
    source_plan = json.loads((tmp_path / "state" / "guardian-plans" / "B-prior.json").read_text(encoding="utf8"))
    source_sha = entry.guardian._plan_sha256(source_plan)
    source_head = "c" * 40
    original_load = entry.guardian._load

    class VerifiedRelease:
        @staticmethod
        def _verified(task_id):
            assert task_id == "local-a"
            return ({
                "implementation_head": source_head,
                "queue_full_sha256": hashlib.sha256(
                    b"fixture scenario | build fixture scenario").hexdigest(),
            }, "")

    monkeypatch.setattr(entry.guardian, "_load",
                        lambda name, path: VerifiedRelease
                        if name == "release" else original_load(name, path))
    deploy = candidate("deploy-next", 649, "A2", "lan-closeout",
                       lan_required=True, action="deploy_51")
    deploy["release_task_id"] = "local-a"
    deploy["release_reference"] = {"batch_id": "B-prior"}
    binding = tmp_path.parent / (tmp_path.name + "-external") / "cross-batch-binding.json"
    binding.write_text(json.dumps({
        "source_task_id": "local-a", "deploy_task_id": "deploy-next",
        "source_row": 648, "source_section": "一",
        "deploy_row": 649, "deploy_section": "一",
        "source_queue_full_sha256": hashlib.sha256(
            b"fixture scenario | build fixture scenario").hexdigest(),
        "deploy_queue_full_sha256": hashlib.sha256(
            b"fixture scenario | build fixture scenario").hexdigest(),
        "deploy_next_action": "build fixture scenario",
        "deploy_lane": "lan-closeout",
        "source_batch_id": "B-prior",
        "source_plan_sha256": source_sha,
        "source_implementation_head": source_head,
        "text": "Human binds the completed source to this LAN closeout.",
    }), encoding="utf8")
    deploy["transfer_binding"] = str(binding)
    second = manifest(tmp_path, [deploy])
    second["batch_id"] = "B-transfer"
    transfers = []
    monkeypatch.setattr(entry.guardian, "_transfer_deploy",
                        lambda *args, **kwargs: transfers.append((args, kwargs))
                        or {"status": "transferred"})
    result = entry.start(second, executor=executor([]),
                         lan_prober=lambda: {"status": "off"}, run=True)
    assert result["batch_phase"] == "release_ready", result
    assert result["transfer_receipts"]["deploy-next"]["status"] == "transferred"
    assert result["transfer_receipts"]["deploy-next"]["production_executed"] is False
    assert len(builds) == 1
    assert len(transfers) == 1
    claims = json.loads((tmp_path / "state" / "guardian-claims.json").read_text(
        encoding="utf8"))["claims"]
    assert "lane:lan-closeout" not in claims
    assert claims["row:一:649"] == {"batch_id": "B-transfer", "task_id": "deploy-next"}
    assert claims["row:一:648"] == {"batch_id": "B-prior", "task_id": "local-a"}
    # A later transfer cannot use the same completed source once its old row claim drifts.
    claims.pop("row:一:648")
    registry = tmp_path / "state" / "guardian-claims.json"
    payload = json.loads(registry.read_text(encoding="utf8"))
    payload["claims"] = claims
    registry.write_text(json.dumps(payload), encoding="utf8")
    next_deploy = candidate("deploy-later", 650, "A3", "lan-closeout",
                            lan_required=True, action="deploy_51")
    next_deploy["release_task_id"] = "local-a"
    next_deploy["release_reference"] = {"batch_id": "B-prior"}
    next_binding = binding.parent / "cross-batch-later.json"
    later = json.loads(binding.read_text(encoding="utf8"))
    later.update(deploy_task_id="deploy-later", deploy_row=650)
    next_binding.write_text(json.dumps(later), encoding="utf8")
    next_deploy["transfer_binding"] = str(next_binding)
    third = manifest(tmp_path, [next_deploy])
    third["batch_id"] = "B-transfer-later"
    refused = entry.start(third, executor=executor([]),
                          lan_prober=lambda: {"status": "off"}, run=True)
    assert refused["status"] == "blocked", refused
    assert "claim" in refused["reason"]
    assert len(builds) == 1
    assert len(transfers) == 1


def test_retire_preserves_deploy_claim_when_transfer_state_won_before_receipt(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    entry.guardian.lane_machine.REPO_ROOT = tmp_path
    workspace = _prepared_source(entry, tmp_path)
    data, _binding = _bound_transfer_manifest(tmp_path, workspace)
    data["batch_id"] = "B-crashed-transfer"
    monkeypatch.setattr(entry.guardian, "_advance_task",
                        lambda *args: {"status": "ready", "next_phase": "release_ready"})

    def transfer_then_crash(task_id, batch, lane, item, *, wave):
        entry.guardian.lane_machine.transfer_out_lane(
            batch=batch, wave=wave, lane=lane, action_key="deploy_51",
            note=task_id + ":" + item, notify_fn=lambda _message: None)
        return {"status": "blocked", "reason": "receipt not persisted after transfer"}

    monkeypatch.setattr(entry.guardian, "_transfer_deploy", transfer_then_crash)
    first = entry.start(data, executor=executor([]),
                        lan_prober=lambda: {"status": "off"}, run=True)
    assert first["transfer_receipts"] == {}
    state = entry.guardian.lane_machine._read_state()
    assert state["lanes"]["lan-lane"]["transfers"]
    plan = json.loads((tmp_path / "state" / "guardian-plans" /
                       "B-crashed-transfer.json").read_text(encoding="utf8"))
    proof = tmp_path.parent / (tmp_path.name + "-external") / "retire-crash.json"
    proof.write_text(json.dumps({
        "batch_id": "B-crashed-transfer",
        "plan_sha256": entry.guardian._plan_sha256(plan),
        "decision": "retire_stalled_batch",
        "text": "Human retires a batch after checking transfer state.",
    }), encoding="utf8")
    retired = entry.retire_batch("B-crashed-transfer", proof)
    assert retired["status"] == "retired", retired
    claims = json.loads((tmp_path / "state" / "guardian-claims.json").read_text(
        encoding="utf8"))["claims"]
    assert claims["row:一:649"] == {
        "batch_id": "B-crashed-transfer", "task_id": "deploy-a"}


def test_pre_dispatch_claim_has_retirable_record_after_owner_crash(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    entry.guardian.lane_machine.REPO_ROOT = tmp_path
    workspace = _prepared_source(entry, tmp_path)
    data = manifest(tmp_path, [candidate()])
    data["batch_id"] = "B-claim-crash"
    data["workspaces"] = {"local-a": str(workspace)}
    planned = entry.start(data, executor=executor([]),
                          lan_prober=lambda: {"status": "on"}, run=False)
    assert planned["status"] == "planned"
    entry._claim_execution(planned["plan"])
    record = tmp_path / "state" / "guardian-batches" / "B-claim-crash.json"
    assert json.loads(record.read_text(encoding="utf8"))["status"] == "claimed"
    proof = tmp_path.parent / (tmp_path.name + "-external") / "retire-claim.json"
    proof.write_text(json.dumps({
        "batch_id": "B-claim-crash",
        "plan_sha256": entry.guardian._plan_sha256(planned["plan"]),
        "decision": "retire_stalled_batch",
        "text": "Human retires a claimed batch that never dispatched.",
    }), encoding="utf8")
    retired = entry.retire_batch("B-claim-crash", proof)
    assert retired["status"] == "retired", retired
    claims = json.loads((tmp_path / "state" / "guardian-claims.json").read_text(
        encoding="utf8"))["claims"]
    assert "row:一:648" not in claims


def test_item_review_can_settle_calling_transfer_only_when_lane_proves_absence(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    entry.guardian.lane_machine.REPO_ROOT = tmp_path
    workspace = _prepared_source(entry, tmp_path)
    data, _ = _bound_transfer_manifest(tmp_path, workspace)
    data["batch_id"] = "B-settle"
    monkeypatch.setattr(entry.guardian, "_advance_task",
                        lambda *args: {"status": "ready", "next_phase": "release_ready"})
    monkeypatch.setattr(entry.guardian, "_transfer_deploy",
                        lambda *args, **kwargs: {"status": "blocked", "reason": "preflight unavailable"})
    result = entry.start(data, executor=executor([]),
                         lan_prober=lambda: {"status": "off"}, run=True)
    assert result["transfer_receipts"] == {}
    record = json.loads((tmp_path / "state" / "guardian-batches" /
                         "B-settle.json").read_text(encoding="utf8"))
    attempt = record["transfer_attempts"]["deploy-a"]
    assert attempt["status"] == "calling"
    entry.guardian.lane_machine._with_state(
        lambda state: state["lanes"].setdefault(
            "lan-lane", {"status": "paused", "history": [], "transfers": []}))
    lane_path = entry.guardian.lane_machine._state_path()
    plan = json.loads((tmp_path / "state" / "guardian-plans" /
                       "B-settle.json").read_text(encoding="utf8"))
    transfer = plan["transfers"][0]
    external = tmp_path.parent / (tmp_path.name + "-external") / "settle.json"
    external.write_text(json.dumps({
        "batch_id": "B-settle",
        "plan_sha256": entry.guardian._plan_sha256(plan),
        "decision": "retire_stalled_batch",
        "text": "Human reviewed the exact stalled transfer.",
        "settle_not_transferred": {
            "deploy-a": {
                "decision": "not_transferred", "task_id": "deploy-a",
                "lane": "lan-lane", "item": transfer["item"],
                "attempt_at": attempt["at"],
                "lane_state_sha256": hashlib.sha256(lane_path.read_bytes()).hexdigest(),
                "text": "I checked the authoritative lane history for this item.",
            },
        },
    }), encoding="utf8")
    retired = entry.retire_batch("B-settle", external)
    assert retired["status"] == "retired", retired
    assert retired["retirement"]["settled_not_transferred"] == ["deploy-a"]
    claims = json.loads((tmp_path / "state" / "guardian-claims.json").read_text(
        encoding="utf8"))["claims"]
    assert "row:一:649" not in claims
    assert claims["row:一:648"] == {"batch_id": "B-settle", "task_id": "local-a"}


@pytest.mark.parametrize("invalid_mode", ["wrong_sha", "authoritative_transfer"])
def test_item_review_refuses_false_no_transfer_settlement(tmp_path, monkeypatch, invalid_mode):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    entry.guardian.lane_machine.REPO_ROOT = tmp_path
    workspace = _prepared_source(entry, tmp_path)
    data, _ = _bound_transfer_manifest(tmp_path, workspace)
    data["batch_id"] = "B-settle-negative"
    monkeypatch.setattr(entry.guardian, "_advance_task",
                        lambda *args: {"status": "ready", "next_phase": "release_ready"})
    monkeypatch.setattr(entry.guardian, "_transfer_deploy",
                        lambda *args, **kwargs: {"status": "blocked", "reason": "preflight unavailable"})
    result = entry.start(data, executor=executor([]),
                         lan_prober=lambda: {"status": "off"}, run=True)
    assert result["transfer_receipts"] == {}
    record = json.loads((tmp_path / "state" / "guardian-batches" /
                         "B-settle-negative.json").read_text(encoding="utf8"))
    attempt = record["transfer_attempts"]["deploy-a"]
    plan = json.loads((tmp_path / "state" / "guardian-plans" /
                       "B-settle-negative.json").read_text(encoding="utf8"))
    transfer = plan["transfers"][0]

    def seed(state):
        lane = state["lanes"].setdefault(
            "lan-lane", {"status": "paused", "history": [], "transfers": []})
        if invalid_mode == "authoritative_transfer":
            lane["transfers"].append({
                "batch": "B-settle-negative", "wave": 1,
                "action_key": "deploy_51",
                "note": transfer["release_task_id"] + ":" + transfer["item"]})

    entry.guardian.lane_machine._with_state(seed)
    lane_path = entry.guardian.lane_machine._state_path()
    digest = hashlib.sha256(lane_path.read_bytes()).hexdigest()
    external = tmp_path.parent / (tmp_path.name + "-external") / "settle-negative.json"
    external.write_text(json.dumps({
        "batch_id": "B-settle-negative",
        "plan_sha256": entry.guardian._plan_sha256(plan),
        "decision": "retire_stalled_batch",
        "text": "Human reviewed the exact stalled transfer.",
        "settle_not_transferred": {
            "deploy-a": {
                "decision": "not_transferred", "task_id": "deploy-a",
                "lane": "lan-lane", "item": transfer["item"],
                "attempt_at": attempt["at"],
                "lane_state_sha256": "0" * 64 if invalid_mode == "wrong_sha" else digest,
                "text": "I checked the authoritative lane history for this item.",
            },
        },
    }), encoding="utf8")
    retired = entry.retire_batch("B-settle-negative", external)
    assert retired["status"] == "blocked", retired
    claims = json.loads((tmp_path / "state" / "guardian-claims.json").read_text(
        encoding="utf8"))["claims"]
    assert claims["row:一:649"] == {
        "batch_id": "B-settle-negative", "task_id": "deploy-a"}
def test_plan_then_run_accepts_only_stdout_hash_drift(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    entry.guardian.lane_machine.REPO_ROOT = tmp_path
    workspace = _prepared_source(entry, tmp_path)
    data = manifest(tmp_path, [candidate()])
    data["batch_id"] = "B-0930_Codex业务闭环v2"
    data["workspaces"] = {"local-a": str(workspace)}
    hashes = iter([("1", "a"), ("2", "b")])
    dry_calls = []
    def dry(plan, execute):
        lint_hash, receipt_hash = next(hashes)
        dry_calls.append((lint_hash, receipt_hash))
        return {"status": "dry_run_verified", "lint_stdout_sha256": lint_hash * 64,
                "receipts": [{"task_ids": ["local-a"], "lanes": ["alpha"],
                              "stdout_sha256": receipt_hash * 64}]}
    monkeypatch.setattr(entry, "_dry_run", dry)
    stage_dispatches = []
    monkeypatch.setattr(entry.guardian, "_advance_task",
        lambda task_id, *args, **kwargs: (stage_dispatches.append(task_id) or
            {"status": "ready", "next_phase": "release_ready"}))
    assert entry.start(data, executor=executor([]),
        lan_prober=lambda: {"status": "on", "effective": "on"}, run=False)["status"] == "planned"
    result = entry.start(data, executor=executor([]),
        lan_prober=lambda: {"status": "on", "effective": "on"}, run=True)
    saved = json.loads((tmp_path / "state/guardian-plans/B-0930_Codex业务闭环v2.json").read_text(encoding="utf8"))
    assert result["status"] == "release_ready"
    assert dry_calls == [("1", "a"), ("2", "b")] and stage_dispatches == ["local-a"]
    assert saved["dry_run"]["lint_stdout_sha256"] == "1" * 64
    assert saved["dry_run"]["receipts"][0]["stdout_sha256"] == "a" * 64


@pytest.mark.parametrize("tampered_field", ["task_ids", "lanes"])
def test_plan_then_run_blocks_semantic_receipt_tamper_before_stage_dispatch(tmp_path, monkeypatch, tampered_field):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    entry = load()
    entry.guardian.lane_machine.REPO_ROOT = tmp_path
    workspace = _prepared_source(entry, tmp_path)
    data = manifest(tmp_path, [candidate()])
    data["batch_id"] = "B-0930_Codex业务闭环v2"
    data["workspaces"] = {"local-a": str(workspace)}
    wrong_receipt = iter([False, True])
    def dry(plan, execute):
        wrong = next(wrong_receipt)
        receipt = {"task_ids": ["local-a"], "lanes": ["alpha"], "stdout_sha256": "d" * 64}
        if wrong:
            receipt[tampered_field] = ["other"]
        return {"status": "dry_run_verified", "lint_stdout_sha256": "c" * 64,
                "receipts": [receipt]}
    monkeypatch.setattr(entry, "_dry_run", dry)
    stage_dispatches = []
    monkeypatch.setattr(entry.guardian, "_advance_task",
                        lambda *args, **kwargs: stage_dispatches.append(args[0]))
    entry.start(data, executor=executor([]), lan_prober=lambda: {"status": "on"}, run=False)
    result = entry.start(data, executor=executor([]), lan_prober=lambda: {"status": "on"}, run=True)
    assert result["status"] == "blocked" and "plan changed" in result["reason"]
    # The only orchestration-to-model-stage dispatch seam was never crossed.
    assert stage_dispatches == []
