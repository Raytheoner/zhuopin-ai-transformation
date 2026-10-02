"""Release boundary tests: no ff, production call or external notification."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location("workflow_release_under_test",
                                                  BASE / "workflow_release.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def ref(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path))
    release = load()
    monkeypatch.setattr(release.state, "STATE", tmp_path)
    folder = tmp_path / "runs" / "sample"
    folder.mkdir(parents=True)
    project = tmp_path / "repo" / "service"
    project.mkdir(parents=True)
    ci = folder / "ci-report.json"
    stdout = folder / "ci.stdout.txt"
    stderr = folder / "ci.stderr.txt"
    stdout.write_text("1 passed", encoding="utf8")
    stderr.write_text("", encoding="utf8")
    target = {"nodeid": "service", "argv": [sys.executable, "-m", "pytest", "-q", "--tb=short", "--junit-xml=pytest-result.xml"],
              "cwd": str(project), "exit": 0,
              "stdout_path": str(stdout), "stdout_sha256": hashlib.sha256(stdout.read_bytes()).hexdigest(),
              "stderr_path": str(stderr), "stderr_sha256": hashlib.sha256(stderr.read_bytes()).hexdigest()}
    xml = folder / "ci-first-0.junit.xml"
    xml.write_bytes(b'<testsuite tests="1" failures="0" errors="0"/>')
    target.update(junit_path=str(xml), junit_sha256=ref(xml)["sha256"])
    ci.write_text(json.dumps({"task_id": "sample", "implementation_head": "head", "attempt_id": "first",
                              "expected_roots": ["service"], "targets": [target]}), encoding="utf8")
    review = folder / "review.json"
    review.write_text(json.dumps({"task_id": "sample", "implementation_head": "head",
                                  "thread_id": "review-thread", "conclusion": "approved",
                                  "findings": [], "ci_report": ref(ci)}), encoding="utf8")
    current = {"id": "sample", "phase": "review", "phase_status": "stage_output_needs_review",
               "attempts": [{"id": "first", "phase": "test", "status": "stage_output_needs_review"},
                            {"id": "review-1", "phase": "review", "status": "stage_output_needs_review",
                             "finished_at": "2026-09-25T00:00:00Z"}], "implementation_head": "head",
               "implementation_thread_id": "implement-thread",
               "workspace": str(project.parent), "ci_targets": [target], "ci_report": ref(ci),
               "review_evidence": {"review_head": "head", "review_thread_id": "review-thread",
                                   "review_conclusion": "approved", "review_findings": [],
                                   "review_report": ref(review)},
               "delivery_accepted": False}
    (folder / "state.json").write_text(json.dumps(current), encoding="utf8")
    return release, folder


def test_release_preparation_pauses_for_item_specific_ff_and_never_merges(fixture, monkeypatch):
    release, folder = fixture
    calls = []
    monkeypatch.setattr(release, "patchid_compare", lambda branch: {
        "verdict": "needs_merge", "all_in_master": False,
        "branch": branch, "branch_sha": "head", "base_sha": "master-head",
        "missing": [{"sha": "head", "patch_id": "p"}],
    })
    monkeypatch.setattr(release, "execute", lambda *a, **k: calls.append(a))
    result = release.prepare_release("sample", {"branch": "codex/sample",
                                                 "action_key": "merge_to_master"})
    assert result["status"] == "paused"
    assert result["authorization_required"] == "ff:sample:head"
    assert calls == []
    assert json.loads((folder / "release-request.json").read_text(encoding="utf8"))["delivery_accepted"] is False


def test_missing_ci_or_review_blocks_release(fixture, monkeypatch):
    release, folder = fixture
    current = json.loads((folder / "state.json").read_text(encoding="utf8"))
    current["ci_targets"][0]["exit"] = 1
    (folder / "state.json").write_text(json.dumps(current), encoding="utf8")
    monkeypatch.setattr(release, "patchid_compare", lambda branch: pytest.fail("no compare"))
    monkeypatch.setattr(release, "patchid_compare", lambda branch: pytest.fail("unverified review reached patch-id"))
    result = release.prepare_release("sample", {"branch": "codex/sample",
                                                "action_key": "merge_to_master"})
    assert result["status"] == "blocked"


@pytest.mark.parametrize("kind", ["missing", "hash", "failure", "attempt", "roots"])
def test_invalid_junit_blocks_release_before_patchid(fixture, monkeypatch, kind):
    release, folder = fixture
    current = json.loads((folder / "state.json").read_text(encoding="utf8"))
    ci = Path(current["ci_report"]["path"])
    report = json.loads(ci.read_text(encoding="utf8"))
    target = current["ci_targets"][0]
    xml = Path(target["junit_path"])
    if kind == "missing": xml.unlink()
    elif kind == "hash": xml.write_bytes(b"changed")
    elif kind == "failure":
        xml.write_bytes(b'<testsuite tests="1" failures="1" errors="0"/>')
        target["junit_sha256"] = ref(xml)["sha256"]
    elif kind == "attempt": report["attempt_id"] = "other"
    elif kind == "roots": report["expected_roots"] = ["service", "missing"]
    report["targets"] = current["ci_targets"]
    ci.write_text(json.dumps(report), encoding="utf8")
    current["ci_report"] = ref(ci)
    review = folder / "review.json"
    review_data = json.loads(review.read_text(encoding="utf8"))
    review_data["ci_report"] = ref(ci)
    review.write_text(json.dumps(review_data), encoding="utf8")
    current["review_evidence"]["review_report"] = ref(review)
    (folder / "state.json").write_text(json.dumps(current), encoding="utf8")
    monkeypatch.setattr(release, "patchid_compare", lambda *a: pytest.fail("invalid JUnit reached release"))
    result = release.prepare_release("sample", {"branch": "codex/sample", "action_key": "merge_to_master"})
    assert result["status"] == "blocked"


def test_release_requires_ci_to_run_from_target_project_directory(fixture, monkeypatch):
    release, folder = fixture
    current = json.loads((folder / "state.json").read_text(encoding="utf8"))
    current["ci_targets"][0]["cwd"] = current["workspace"]
    ci = folder / "ci-report.json"
    ci.write_text(json.dumps({"task_id": "sample", "implementation_head": "head",
                              "targets": current["ci_targets"]}), encoding="utf8")
    current["ci_report"] = ref(ci)
    (folder / "state.json").write_text(json.dumps(current), encoding="utf8")
    monkeypatch.setattr(release, "patchid_compare", lambda branch: pytest.fail("bad CI cwd reached patch-id"))
    result = release.prepare_release("sample", {"branch": "codex/sample", "action_key": "merge_to_master"})
    assert result == {"status": "blocked", "reason": "CI project working directory or command mismatch"}


def test_tampered_ci_output_blocks_release(fixture, monkeypatch):
    release, folder = fixture
    output = folder / "ci.stdout.txt"
    output.write_text("one test passed", encoding="utf8")
    current = json.loads((folder / "state.json").read_text(encoding="utf8"))
    target = current["ci_targets"][0]
    target["stdout_path"] = str(output)
    target["stdout_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
    ci_path = folder / "ci-report.json"
    ci_path.write_text(json.dumps({"task_id": "sample", "implementation_head": "head",
                                   "targets": current["ci_targets"]}), encoding="utf8")
    current["ci_report"] = ref(ci_path)
    (folder / "state.json").write_text(json.dumps(current), encoding="utf8")
    output.write_text("one test failed", encoding="utf8")
    monkeypatch.setattr(release, "patchid_compare", lambda branch: pytest.fail("tampered CI reached patch-id"))
    result = release.prepare_release("sample", {"branch": "codex/sample",
                                                "action_key": "merge_to_master"})
    assert result == {"status": "blocked", "reason": "CI output hash mismatch"}


def test_missing_raw_ci_output_blocks_release(fixture):
    release, folder = fixture
    current = json.loads((folder / "state.json").read_text(encoding="utf8"))
    current["ci_targets"][0].pop("stdout_path")
    current["ci_targets"][0].pop("stdout_sha256")
    ci = folder / "ci-report.json"
    ci.write_text(json.dumps({"task_id": "sample", "implementation_head": "head",
                              "targets": current["ci_targets"]}), encoding="utf8")
    current["ci_report"] = ref(ci)
    (folder / "state.json").write_text(json.dumps(current), encoding="utf8")
    assert release.prepare_release("sample", {"branch": "codex/sample", "action_key": "merge_to_master"}) == {
        "status": "blocked", "reason": "CI raw output missing; refresh CI evidence"}


def test_running_review_cannot_prepare_release_or_transfer(fixture, monkeypatch):
    release, folder = fixture
    (folder / "running.lock").write_text("review", encoding="utf8")
    monkeypatch.setattr(release.lane_machine, "transfer_out_lane",
                        lambda **kw: pytest.fail("running review reached deploy transfer"))
    assert release.prepare_release("sample", {"branch": "codex/sample", "action_key": "merge_to_master"}) == {
        "status": "blocked", "reason": "review attempt still running"}
    assert release.transfer_deploy("sample", "B", "A", "item")["status"] == "blocked"


def test_patch_already_in_master_is_skip_not_ff(fixture, monkeypatch):
    release, _ = fixture
    monkeypatch.setattr(release, "patchid_compare", lambda branch: {
        "verdict": "in_master", "all_in_master": True, "branch": branch,
        "branch_sha": "head", "base_sha": "master-head", "missing": [],
    })
    result = release.prepare_release("sample", {"branch": "codex/sample",
                                                 "action_key": "merge_to_master"})
    assert result["status"] == "skip_ff"


def test_transfer_only_records_pointer_without_notification_or_lan_call(fixture, monkeypatch):
    release, _ = fixture
    calls = []
    monkeypatch.setattr(release.lane_machine, "_read_state", lambda: {"lanes": {}})
    monkeypatch.setattr(release.lane_machine, "transfer_out_lane", lambda **kw: (
        calls.append(kw) or {"status": "running", "transfers": [{"note": kw["note"]}]}))
    monkeypatch.setattr(release.lane_machine, "deploy_discipline_pointer",
                        lambda: "Read LAN closeout source")
    monkeypatch.setattr(release.lane_machine, "lan_status",
                        lambda *a, **k: pytest.fail("transfer must not probe LAN"))
    result = release.transfer_deploy("sample", "B-fixture", "A1", "deploy-1")
    assert result["status"] == "transferred"
    assert result["pointer"] == "Read LAN closeout source"
    assert len(calls) == 1 and callable(calls[0]["notify_fn"])
    assert calls[0]["action_key"] == "deploy_51"


@pytest.mark.parametrize("action", ["external_send", "l2_gate_signoff", "asil_cd_related"])
def test_red_actions_never_prepare_automatic_release(fixture, action):
    release, _ = fixture
    assert release.prepare_release("sample", {"branch": "codex/sample",
                                               "action_key": action})["status"] == "blocked"

def test_transfer_same_item_is_idempotent_in_isolated_lane_state(fixture, tmp_path, monkeypatch):
    release, _ = fixture
    monkeypatch.setattr(release.lane_machine, "REPO_ROOT", tmp_path)
    first = release.transfer_deploy("sample", "B-fixture", "A1", "deploy-1")
    second = release.transfer_deploy("sample", "B-fixture", "A1", "deploy-1")
    assert first["status"] == second["status"] == "transferred"
    assert second["already_recorded"] is True
    lane = release.lane_machine._read_state()["lanes"]["A1"]
    assert len(lane["transfers"]) == 1

@pytest.fixture
def driver_release_fixture(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "state"))
    from test_workflow_driver import git, seed_approval, run_approved_review
    spec = importlib.util.spec_from_file_location("workflow_driver_release_test",
                                                  BASE / "workflow_driver.py")
    driver = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = driver
    spec.loader.exec_module(driver)
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "test@example.com")
    (repo / "service.py").write_text("VALUE = 1", encoding="utf8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    linked = tmp_path / "linked"
    git(repo, "worktree", "add", "--detach", str(linked), "HEAD")
    state_root = tmp_path / "state"
    monkeypatch.setattr(driver.state, "STATE", state_root)
    folder = state_root / "runs/sample"
    folder.mkdir(parents=True)
    (folder / "intent.md").write_text("review fixture", encoding="utf8")
    driver._save("sample", {"id": "sample", "source_checkout": str(repo), "workspace": str(linked)})
    approval = seed_approval(driver, linked, folder)
    result, _ = run_approved_review(driver, linked, folder)
    assert result["status"] == "stage_output_needs_review"
    return driver, linked, folder, approval


def test_driver_exposes_reviewed_release_without_merging(driver_release_fixture, monkeypatch):
    driver, _, _, _ = driver_release_fixture
    calls = []
    class FakeRelease:
        def prepare_release(self, task_id, evidence):
            calls.append((task_id, evidence))
            return {"status": "paused"}
    monkeypatch.setattr(driver, "_release_module", lambda: FakeRelease())
    assert driver.release_ready("sample", "codex/sample")["status"] == "paused"
    assert calls == [("sample", {"branch": "codex/sample", "action_key": "merge_to_master"})]


@pytest.mark.parametrize("case", ["missing", "bytes", "task", "design", "summary"])
def test_driver_release_ready_rejects_invalid_approval_context(driver_release_fixture, monkeypatch, case):
    driver, _, folder, approval = driver_release_fixture
    current = driver.state.load_state("sample")
    if case == "missing": current.pop("design_approval_ref")
    elif case == "bytes": approval.write_bytes(approval.read_bytes() + b" ")
    elif case in ("task", "design"):
        data = json.loads(approval.read_text(encoding="utf-8-sig"))
        data["task_id" if case == "task" else "design_head"] = "wrong"
        approval.write_text(json.dumps(data), encoding="utf8")
        current["design_approval_ref"] = ref(approval)
    else:
        path = folder / "review.json"
        report = json.loads(path.read_text(encoding="utf8"))
        report["approved_design_context"]["text"] = "forged"
        path.write_text(json.dumps(report), encoding="utf8")
        current["review_evidence"]["review_report"] = ref(path)
    driver._save("sample", current)
    calls = []
    class FakeRelease:
        def prepare_release(self, *args):
            calls.append(args)
            return {"status": "paused"}
    monkeypatch.setattr(driver, "_release_module", lambda: FakeRelease())
    assert driver.release_ready("sample", "codex/sample")["status"] == "blocked"
    assert calls == []

def test_review_without_native_thread_identity_cannot_release(fixture, monkeypatch):
    release, folder = fixture
    current = json.loads((folder / "state.json").read_text(encoding="utf8"))
    report_path = folder / "review.json"
    report = json.loads(report_path.read_text(encoding="utf8"))
    report["thread_id"] = None
    report_path.write_text(json.dumps(report), encoding="utf8")
    current["review_evidence"]["review_thread_id"] = None
    current["review_evidence"]["review_report"] = ref(report_path)
    (folder / "state.json").write_text(json.dumps(current), encoding="utf8")
    monkeypatch.setattr(release, "patchid_compare", lambda branch: pytest.fail("unverified review reached patch-id"))
    result = release.prepare_release("sample", {"branch": "codex/sample",
                                                "action_key": "merge_to_master"})
    assert result["status"] == "blocked"

@pytest.mark.parametrize("nodeid", [".", "service/.."])
def test_release_rejects_repository_root_ci_project(fixture, monkeypatch, nodeid):
    release, folder = fixture
    current = json.loads((folder / "state.json").read_text(encoding="utf8"))
    current["ci_targets"][0]["nodeid"] = nodeid
    current["ci_targets"][0]["cwd"] = current["workspace"]
    ci = folder / "ci-report.json"
    ci.write_text(json.dumps({"task_id": "sample", "implementation_head": "head",
                              "targets": current["ci_targets"]}), encoding="utf8")
    current["ci_report"] = ref(ci)
    review_path = Path(current["review_evidence"]["review_report"]["path"])
    review = json.loads(review_path.read_text(encoding="utf8"))
    review["ci_report"] = ref(ci)
    review_path.write_text(json.dumps(review), encoding="utf8")
    current["review_evidence"]["review_report"] = ref(review_path)
    (folder / "state.json").write_text(json.dumps(current), encoding="utf8")
    monkeypatch.setattr(release, "patchid_compare", lambda branch: pytest.fail("root CI reached patch-id"))
    result = release.prepare_release("sample", {"branch": "codex/sample", "action_key": "merge_to_master"})
    assert result == {"status": "blocked", "reason": "CI project working directory or command mismatch"}


@pytest.mark.parametrize("extra", [["--collect-only"], ["-k", "no_such_tests"]])
def test_release_rejects_noncanonical_pytest_arguments(fixture, monkeypatch, extra):
    release, folder = fixture
    current = json.loads((folder / "state.json").read_text(encoding="utf8"))
    current["ci_targets"][0]["argv"].extend(extra)
    ci = folder / "ci-report.json"
    ci.write_text(json.dumps({"task_id": "sample", "implementation_head": "head",
                              "targets": current["ci_targets"]}), encoding="utf8")
    current["ci_report"] = ref(ci)
    review_path = Path(current["review_evidence"]["review_report"]["path"])
    review = json.loads(review_path.read_text(encoding="utf8"))
    review["ci_report"] = ref(ci)
    review_path.write_text(json.dumps(review), encoding="utf8")
    current["review_evidence"]["review_report"] = ref(review_path)
    (folder / "state.json").write_text(json.dumps(current), encoding="utf8")
    monkeypatch.setattr(release, "patchid_compare", lambda branch: pytest.fail("filtered CI reached patch-id"))
    result = release.prepare_release("sample", {"branch": "codex/sample", "action_key": "merge_to_master"})
    assert result == {"status": "blocked", "reason": "CI project working directory or command mismatch"}
