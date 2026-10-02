"""Evidence must justify every automatic Codex workflow transition."""
import hashlib
import os
import importlib.util
import sys
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "workflow_gate.py"


def gate_module():
    spec = importlib.util.spec_from_file_location("workflow_gate_under_test", MODULE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def file_ref(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def test_intent_requires_real_queue_and_intent_evidence(tmp_path):
    gate = gate_module()
    approval_file = tmp_path / "intent-approval.json"
    approval = {"task_id": "sample", "row": 648, "section": "一",
                "action_key": "worktree_local_build", "intent_sha256": "e" * 64, "text": "approved"}
    approval_file.write_text(__import__("json").dumps(approval), encoding="utf8")
    intent_file = tmp_path / "intent.md"
    intent_file.write_text("approved prompt", encoding="utf8")
    state = {"id": "sample", "phase": "intent", "source_head": "abc", "row": 648,
             "section": "一", "action_key": "worktree_local_build", "intent_text_sha256": "e" * 64,
             "intent_ref": file_ref(intent_file)}
    assert gate.decide_next(state, {"exit_code": 0})["status"] == "paused"
    proof = {"queue_row": 648, "intent_sha256": state["intent_ref"]["sha256"],
             "intent_ref": state["intent_ref"],
             "intent_text_sha256": "e" * 64, "intent_approval": approval,
             "intent_approval_ref": file_ref(approval_file)}
    assert gate.decide_next(state, proof) == {
        "next_phase": "proposal", "status": "ready", "reason": "intent verified"
    }
    state["action_key"] = "external_send"
    assert gate.decide_next(state, proof)["status"] != "ready"
    state["action_key"] = "worktree_local_build"
    approval["action_key"] = "external_send"
    assert gate.decide_next(state, proof)["status"] == "paused"
    approval["action_key"] = "worktree_local_build"
    intent_file.write_text("tampered prompt", encoding="utf8")
    assert gate.decide_next(state, proof)["status"] == "paused"


def test_proposal_pauses_at_design_and_rejects_changed_approval(tmp_path):
    gate = gate_module()
    design = tmp_path / "design.md"
    design.write_text("approved draft", encoding="utf8")
    state = {"id": "sample", "phase": "proposal", "design_head": "def"}
    proof = {"openspec_valid": True, "design": file_ref(design), "proposal_sha256": "a" * 64,
             "tasks_sha256": "b" * 64}
    assert gate.decide_next(state, proof)["status"] == "paused"
    proof["approval"] = {"task_id": "sample", "design_head": "def",
                         "design_sha256": proof["design"]["sha256"], "text": "批准"}
    assert gate.decide_next(state, proof)["next_phase"] == "implement"
    design.write_text("changed after approval", encoding="utf8")
    assert gate.decide_next(state, proof)["status"] == "blocked"


def test_model_exit_zero_without_native_evidence_cannot_start_test(tmp_path):
    gate = gate_module()
    state = {"id": "sample", "phase": "implement", "workspace": str(tmp_path),
             "implementation_head": "fed", "attempt_started_at": "2026-09-25T00:00:00+00:00"}
    assert gate.decide_next(state, {"model_status": "output_needs_review", "exit_code": 0})["status"] == "blocked"


def test_implement_requires_matching_thread_workspace_hook_and_fresh_sentinel(tmp_path):
    gate = gate_module()
    artifact = tmp_path / "result.md"
    artifact.write_text("built", encoding="utf8")
    sentinel = tmp_path / "done.txt"
    sentinel.write_text("0", encoding="utf8")
    state = {"id": "sample", "phase": "implement", "workspace": str(tmp_path),
             "implementation_head": "fed", "attempt_started_at": "2026-09-25T00:00:00+00:00"}
    proof = {"model_status": "output_needs_review", "thread_id": "native-1",
             "native_thread_id": "native-1", "native_workspace": str(tmp_path),
             "native_tool_events": ["exec_command"], "native_hook_events": ["PreToolUse"],
             "artifacts": [file_ref(artifact)], "sentinel": str(sentinel)}
    assert gate.decide_next(state, proof)["next_phase"] == "test"
    os.utime(sentinel, (1, 1))
    assert gate.decide_next(state, proof)["status"] == "blocked"
    sentinel.touch()
    proof["native_thread_id"] = "other-thread"
    assert gate.decide_next(state, proof)["status"] == "blocked"
    proof["native_thread_id"] = "native-1"
    proof["native_hook_events"] = []
    assert gate.decide_next(state, proof)["status"] == "blocked"


def test_ci_and_independent_review_are_separate_gates(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path))
    gate = gate_module()
    import json
    workspace = tmp_path / "repo"
    service = workspace / "service"
    service.mkdir(parents=True)
    stdout, stderr = tmp_path / "stdout.txt", tmp_path / "stderr.txt"
    stdout.write_text("1 passed", encoding="utf8")
    stderr.write_text("", encoding="utf8")
    target = {"nodeid": "service", "argv": [sys.executable, "-m", "pytest", "-q", "--tb=short", "--junit-xml=pytest-result.xml"],
              "cwd": str(service), "exit": 0,
              "stdout_path": str(stdout), "stdout_sha256": hashlib.sha256(stdout.read_bytes()).hexdigest(),
              "stderr_path": str(stderr), "stderr_sha256": hashlib.sha256(stderr.read_bytes()).hexdigest()}
    folder = tmp_path / "runs/sample"
    folder.mkdir(parents=True)
    xml = folder / "ci-first-0.junit.xml"
    xml.write_bytes(b'<testsuite tests="1" failures="0" errors="0"/>')
    target.update(junit_path=str(xml), junit_sha256=file_ref(xml)["sha256"])
    ci_path = tmp_path / "ci.json"
    ci_path.write_text(json.dumps({"task_id": "sample", "implementation_head": "fed",
                                   "attempt_id": "first", "expected_roots": ["service"], "targets": [target]}), encoding="utf8")
    ci_ref = file_ref(ci_path)
    state = {"id": "sample", "phase": "test", "implementation_head": "fed",
             "workspace": str(workspace), "ci_targets": [target], "ci_report": ci_ref,
             "attempts": [{"id": "first", "phase": "test", "status": "stage_output_needs_review"}]}
    assert gate.decide_next(state, {"ci_targets": [{"nodeid": "tests/a.py", "exit": 1}]})["status"] == "blocked"
    assert gate.decide_next(state, {"ci_targets": [target]})["next_phase"] == "review"
    state["phase"] = "review"
    state["implementation_thread_id"] = "implement-thread"
    bad = {"review_head": "fed", "review_thread_id": "implement-thread", "review_conclusion": "approved"}
    assert gate.decide_next(state, bad)["status"] == "blocked"
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps({"task_id": "sample", "implementation_head": "fed",
        "ci_report": ci_ref, "thread_id": "review-thread", "conclusion": "approved", "findings": []}), encoding="utf8")
    good = {"review_head": "fed", "review_thread_id": "review-thread", "review_conclusion": "approved",
            "review_findings": [], "review_report": file_ref(review_path)}
    assert gate.decide_next(state, good)["next_phase"] == "release_ready"
    xml.write_bytes(b"tampered")
    assert gate.decide_next(state, good)["status"] == "blocked"
    state["phase"] = "test"
    assert gate.decide_next(state, {"ci_targets": [target]})["status"] == "blocked"


def test_unknown_or_red_action_never_auto_executes():
    gate = gate_module()
    state = {"id": "sample", "phase": "release_ready"}
    assert gate.decide_next(state, {"action_key": "new_unclassified_action"})["status"] == "paused"
    assert gate.decide_next(state, {"action_key": "external_send"})["status"] == "blocked"
