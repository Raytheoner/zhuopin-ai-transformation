"""Offline end-to-end fixture for intent→release-ready; no network or real model."""
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

import pytest

BASE = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location("e2e_" + name, BASE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True,
                          encoding="utf8", check=True).stdout.strip()


@pytest.fixture
def chain(tmp_path, monkeypatch):
    repo = tmp_path / "isolated"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "Fixture")
    git(repo, "config", "user.email", "fixture@example.com")
    (repo / "AGENTS.md").write_text("Fixture only. No external actions.", encoding="utf8")
    git(repo, "add", "AGENTS.md")
    git(repo, "commit", "-qm", "source")
    linked = tmp_path / "linked-worktree"
    git(repo, "worktree", "add", "--detach", str(linked), "HEAD")
    repo = linked
    state_root = tmp_path / "runtime-state"
    folder = state_root / "runs" / "fixture-task"
    folder.mkdir(parents=True)
    (folder / "intent.md").write_text("Build a local pure-Python fixture only.", encoding="utf8")
    approval = tmp_path / "intent-approval.json"
    approval.write_text(json.dumps({"task_id": "fixture-task", "row": 648, "section": "一",
        "action_key": "worktree_local_build",
        "intent_sha256": hashlib.sha256(b"Build a local pure-Python fixture only.").hexdigest(),
        "queue_file": "fixture-queue.md", "queue_line": 1,
        "text": "approved synthetic fixture"}), encoding="utf8")
    queue = folder / "queue.json"
    queue.write_text(json.dumps({"exit": 0, "stdout": json.dumps({"found": True, "carrier": "live",
        "done": False, "row": "648", "section": "一", "error": None,
        "read_errors": [], "file": "fixture-queue.md", "line": 1})}), encoding="utf8")
    (folder / "state.json").write_text(json.dumps({
        "id": "fixture-task", "row": 648, "section": "一", "phase": "intent",
        "action_key": "worktree_local_build", "source_head": git(repo, "rev-parse", "HEAD"),
        "source_git_common_dir": git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"),
        "source_checkout": str(tmp_path / "isolated"),
        "intent_text_sha256": hashlib.sha256(b"Build a local pure-Python fixture only.").hexdigest(),
        "intent_ref": {"path": str(folder / "intent.md"),
                       "sha256": hashlib.sha256((folder / "intent.md").read_bytes()).hexdigest()},
        "intent_approval_ref": {"path": str(approval), "sha256": hashlib.sha256(approval.read_bytes()).hexdigest()},
        "queue_ref": {"path": str(queue), "sha256": hashlib.sha256(queue.read_bytes()).hexdigest()},
        "workspace": str(repo), "attempts": [], "delivery_accepted": False,
    }), encoding="utf8")
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(state_root))
    driver = load("workflow_driver")
    monkeypatch.setattr(driver.state, "STATE", state_root)
    calls = []

    def executor(argv, *, cwd, timeout):
        calls.append(list(argv))
        if argv[0] == "openspec":
            assert argv[-1] == "--strict"
            return {"argv": argv, "exit": 0, "stdout": "strict valid", "stderr": ""}
        return driver.handoff.execute(argv, cwd=cwd, timeout=timeout)

    def model(**kw):
        phase = kw["source_id"].split(":")[-1]
        calls.append(["model", phase, kw["sandbox"]])
        evidence = Path(kw["evidence"])
        evidence.mkdir()
        if phase == "proposal":
            change = repo / "openspec" / "changes" / "fixture-task"
            change.mkdir(parents=True)
            for name in ("proposal.md", "design.md", "tasks.md"):
                (change / name).write_text(name + " fixture", encoding="utf8")
            return {"status": "output_needs_review", "thread_id": "proposal-thread",
                    "tool_events": 3, "workspace": str(repo), "exit_code": 0}
        if phase == "implement":
            service = repo / "service"
            (service / "tests").mkdir(parents=True)
            (service / "calc.py").write_text("def answer():\n    return 42\n", encoding="utf8")
            (service / "tests" / "test_calc.py").write_text(
                "from calc import answer\n\ndef test_answer():\n    assert answer() == 42\n",
                encoding="utf8")
            (service / "__init__.py").write_text("", encoding="utf8")
            (evidence / "events.jsonl").write_text(
                json.dumps({"type": "thread.started", "thread_id": "implement-thread"}) + "\n" +
                json.dumps({"type": "item.completed", "item": {"type": "file_change", "status": "completed"}}) + "\n" +
                json.dumps({"type": "turn.completed"}) + "\n", encoding="utf8")
            hooks = state_root / "hooks"
            hooks.mkdir()
            (hooks / "implement.json").write_text(json.dumps({
                "utc": datetime.now(timezone.utc).isoformat(), "session_id": "implement-thread",
                "cwd": str(repo), "event": "PreToolUse", "error": None,
            }), encoding="utf8")
            return {"status": "output_needs_review", "thread_id": "implement-thread",
                    "workspace": str(repo), "tool_events": 1, "exit_code": 0}
        if phase == "review":
            (evidence / "final.txt").write_text(json.dumps({
                "implementation_head": git(repo, "rev-parse", "HEAD"),
                "conclusion": "approved", "findings": [],
            }), encoding="utf8")
            return {"status": "output_needs_review", "thread_id": "review-thread",
                    "workspace": str(repo), "tool_events": 1, "exit_code": 0}
        pytest.fail("unexpected model stage")

    return driver, repo, folder, executor, model, calls, state_root


def test_offline_full_chain_pauses_at_design_then_reaches_reviewed_release(chain, monkeypatch):
    driver, repo, folder, executor, model, calls, state_root = chain
    first = driver.advance("fixture-task", repo, None, executor, model_runner=model)
    assert first["status"] == "paused"
    assert [c for c in calls if c[0] == "model"] == [["model", "proposal", "workspace-write"]]
    saved = json.loads((folder / "state.json").read_text(encoding="utf8"))
    design = repo / "openspec" / "changes" / "fixture-task" / "design.md"
    assert saved["design_head"] == git(repo, "rev-parse", "HEAD")
    approval = state_root / "design-approval.json"
    approval.write_text(json.dumps({
        "task_id": "fixture-task", "design_head": saved["design_head"],
        "design_sha256": hashlib.sha256(design.read_bytes()).hexdigest(),
        "text": "Shao Peishen approved fixture design",
        "allowed_paths": ["service/__init__.py", "service/calc.py", "service/tests/test_calc.py"],
    }), encoding="utf8")
    second = driver.advance("fixture-task", repo, approval, executor, model_runner=model)
    assert second["next_phase"] == "test", second
    third = driver.advance("fixture-task", repo, None, executor, model_runner=model)
    assert third["next_phase"] == "review", third
    fourth = driver.advance("fixture-task", repo, None, executor, model_runner=model)
    assert fourth["next_phase"] == "release_ready", fourth
    saved = json.loads((folder / "state.json").read_text(encoding="utf8"))
    assert saved["delivery_accepted"] is False
    assert saved["implementation_thread_id"] != saved["review_evidence"]["review_thread_id"]
    assert (folder / "ci-report.json").is_file()
    ci_report = json.loads((folder / "ci-report.json").read_text(encoding="utf8"))
    assert ci_report["expected_roots"] == ["service"]
    target = ci_report["targets"][0]
    assert target["argv"][1:] == ["-m", "pytest", "-q", "--tb=short", "--junit-xml=pytest-result.xml"]
    assert Path(target["junit_path"]).read_bytes().startswith(b"<?xml")
    assert driver.state.ci_evidence_error(saved) == ""
    assert not (repo / "service/pytest-result.xml").exists()
    assert (folder / "review.json").is_file()
    release = load("workflow_release")
    monkeypatch.setattr(release.state, "STATE", state_root)
    monkeypatch.setattr(release, "patchid_compare", lambda branch: {
        "branch": branch, "branch_sha": saved["implementation_head"],
        "base_sha": saved["source_head"], "verdict": "needs_merge",
        "all_in_master": False, "missing": [{"sha": saved["implementation_head"]}],
    })
    request = release.prepare_release("fixture-task", {
        "branch": "codex/fixture-task", "action_key": "merge_to_master"})
    assert request["status"] == "paused"
    assert json.loads((folder / "release-request.json").read_text(encoding="utf8"))["ff_executed"] is False
    assert [c[1] for c in calls if c[0] == "model"] == ["proposal", "implement", "review"]


@pytest.mark.parametrize("action", ["unknown-action", "external_send", "l2_gate_signoff", "asil_cd_related"])
def test_unsafe_action_never_starts_proposal(chain, action):
    driver, repo, folder, executor, model, calls, _ = chain
    saved = json.loads((folder / "state.json").read_text(encoding="utf8"))
    saved["action_key"] = action
    (folder / "state.json").write_text(json.dumps(saved), encoding="utf8")
    result = driver.advance("fixture-task", repo, None, executor, model_runner=model)
    assert result["status"] in ("paused", "blocked")
    assert calls == []

def test_unapproved_design_never_starts_implementation(chain):
    driver, repo, folder, executor, model, calls, _ = chain
    assert driver.advance("fixture-task", repo, None, executor, model_runner=model)["status"] == "paused"
    assert driver.advance("fixture-task", repo, None, executor, model_runner=model)["status"] == "paused"
    assert [c[1] for c in calls if c[0] == "model"] == ["proposal"]


def test_design_head_drift_stops_before_model(chain):
    driver, repo, folder, executor, model, calls, state_root = chain
    driver.advance("fixture-task", repo, None, executor, model_runner=model)
    saved = json.loads((folder / "state.json").read_text(encoding="utf8"))
    design = repo / "openspec" / "changes" / "fixture-task" / "design.md"
    approval = state_root / "approval.json"
    approval.write_text(json.dumps({"task_id": "fixture-task", "design_head": saved["design_head"],
                                    "design_sha256": hashlib.sha256(design.read_bytes()).hexdigest(),
                                    "text": "fixture-only approval"}), encoding="utf8")
    (repo / "drift.txt").write_text("drift", encoding="utf8")
    git(repo, "add", "drift.txt")
    git(repo, "commit", "-qm", "drift")
    assert driver.advance("fixture-task", repo, approval, executor, model_runner=model)["status"] == "blocked"
    assert [c[1] for c in calls if c[0] == "model"] == ["proposal"]


def test_busy_attempt_does_not_duplicate_model(chain):
    driver, repo, folder, executor, model, calls, _ = chain
    (folder / "running.lock").write_text("unknown running attempt", encoding="utf8")
    assert driver.advance("fixture-task", repo, None, executor, model_runner=model)["status"] == "blocked"
    assert calls == []
    assert driver.recover("fixture-task")["status"] == "blocked_unknown"
