"""Fail-closed task-attempt state contract for the Codex handoff."""
import importlib.util
import hashlib
import json
import sys
import hashlib
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "workflow_state.py"


def load_state_module():
    spec = importlib.util.spec_from_file_location("workflow_state_under_test", MODULE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


JUNIT = b'<testsuites><testsuite tests="1" failures="0" errors="0" skipped="0"><testcase name="ok"/></testsuite></testsuites>'


@pytest.fixture
def ci_fixture(tmp_path, monkeypatch):
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path))
    state = load_state_module()
    folder = prepared(tmp_path)
    project = tmp_path / "repo/service"
    project.mkdir(parents=True)
    target = {"nodeid": "service", "cwd": str(project), "exit": 0,
              "argv": [sys.executable, "-m", "pytest", "-q", "--tb=short", "--junit-xml=pytest-result.xml"]}
    for name, content in (("stdout", b"1 passed"), ("stderr", b""), ("junit", JUNIT)):
        path = folder / ("ci-first-0.junit.xml" if name == "junit" else name + ".txt")
        path.write_bytes(content)
        target[name + "_path"] = str(path)
        target[name + "_sha256"] = hashlib.sha256(content).hexdigest()
    current = {"id": "sample", "implementation_head": "head", "workspace": str(project.parent),
               "ci_targets": [target], "attempts": [{"id": "first", "phase": "test", "status": "stage_output_needs_review"}]}
    report = {"task_id": "sample", "implementation_head": "head", "attempt_id": "first",
              "expected_roots": ["service"], "targets": current["ci_targets"]}
    def seal():
        path = folder / "report.json"
        path.write_text(json.dumps(report), encoding="utf8")
        current["ci_report"] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    seal()
    return state, current, report, seal


def test_complete_junit_evidence_is_accepted(ci_fixture):
    state, current, _, _ = ci_fixture
    assert state.ci_evidence_error(current) == ""


@pytest.mark.parametrize("xml", [JUNIT, b'<testsuite tests="1" failures="0" errors="0" skipped="1"><testcase><skipped/></testcase></testsuite>'])
def test_standard_junit_roots_and_skips(ci_fixture, xml):
    state, current, _, seal = ci_fixture
    target = current["ci_targets"][0]
    Path(target["junit_path"]).write_bytes(xml)
    target["junit_sha256"] = hashlib.sha256(xml).hexdigest()
    seal()
    assert state.ci_evidence_error(current) == ""


@pytest.mark.parametrize("xml", [b"", b"<bad", b"<unknown/>", b"<testsuites/>",
    b'<!DOCTYPE testsuite [<!ENTITY x "x">]><testsuite tests="1" failures="0" errors="0"/>',
    b'<testsuite tests="-1" failures="0" errors="0"/>',
    b'<testsuite tests="1.5" failures="0" errors="0"/>',
    b'<testsuite tests="1" failures="1" errors="0"/>',
    b'<testsuite tests="1" failures="0" errors="1"/>',
    b'<testsuite tests="1" failures="0" errors="0"><testcase><failure/></testcase></testsuite>',
    b'<testsuite tests="1" failures="0" errors="0"><testcase><error/></testcase></testsuite>',
    b'<testsuite/>'])
def test_invalid_xml_cannot_be_success(ci_fixture, xml):
    state, current, _, seal = ci_fixture
    target = current["ci_targets"][0]
    Path(target["junit_path"]).write_bytes(xml)
    target["junit_sha256"] = hashlib.sha256(xml).hexdigest()
    seal()
    assert "JUnit" in state.ci_evidence_error(current)


@pytest.mark.parametrize("case", ["missing", "hash", "relative", "outside", "filename", "attempt",
    "ledger", "duplicate", "omitted", "task", "head", "targets", "old_argv", "extra", "cwd"])
def test_ci_binding_rejects_drift(ci_fixture, case):
    state, current, report, seal = ci_fixture
    target = current["ci_targets"][0]
    if case == "missing": Path(target["junit_path"]).unlink()
    elif case == "hash": target["junit_sha256"] = "f" * 64
    elif case == "relative": target["junit_path"] = "ci-first-0.junit.xml"
    elif case in ("outside", "filename"):
        path = Path(current["workspace"]) / "ci-first-0.junit.xml" if case == "outside" else Path(target["junit_path"]).with_name("wrong.xml")
        path.write_bytes(JUNIT)
        target["junit_path"] = str(path)
    elif case == "attempt": report["attempt_id"] = "other"
    elif case == "ledger": current["attempts"] = []
    elif case == "duplicate": current["ci_targets"].append(dict(target))
    elif case == "omitted": report["expected_roots"].append("missing-service")
    elif case == "task": report["task_id"] = "other"
    elif case == "head": report["implementation_head"] = "other"
    elif case == "targets": report["targets"] = []
    elif case == "old_argv": target["argv"][-2:] = ["-p", "no:cacheprovider"]
    elif case == "extra": target["argv"].append("--collect-only")
    elif case == "cwd": target["cwd"] = current["workspace"]
    seal()
    assert state.ci_evidence_error(current)


@pytest.mark.parametrize("kind", ["hardlink", "symlink", "reparse", "directory"])
def test_junit_reference_rejects_nonregular_files(ci_fixture, monkeypatch, kind):
    import os
    from types import SimpleNamespace
    state, current, _, _ = ci_fixture
    path = Path(current["ci_targets"][0]["junit_path"])
    if kind == "hardlink": os.link(path, path.with_name("second-link"))
    elif kind == "directory":
        path.unlink()
        path.mkdir()
    elif kind == "symlink":
        original = path.with_name("original")
        path.rename(original)
        try: path.symlink_to(original)
        except OSError as exc: pytest.skip(f"symlink unavailable: {exc}")
    else:
        lstat = Path.lstat
        def reparse(p, *a, **kw):
            info = lstat(p, *a, **kw)
            if p == path:
                return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
            return info
        monkeypatch.setattr(Path, "lstat", reparse)
    assert "JUnit" in state.ci_evidence_error(current)


def test_dtd_is_rejected_for_utf16_bytes(ci_fixture):
    state, current, _, seal = ci_fixture
    xml = '<!DOCTYPE testsuite [<!ENTITY x "boom">]><testsuite tests="1" failures="0" errors="0">&x;</testsuite>'.encode("utf-16")
    target = current["ci_targets"][0]
    Path(target["junit_path"]).write_bytes(xml)
    target["junit_sha256"] = hashlib.sha256(xml).hexdigest()
    seal()
    assert "JUnit" in state.ci_evidence_error(current)


def prepared(tmp_path):
    folder = tmp_path / "runs" / "sample"
    folder.mkdir(parents=True)
    (folder / "state.json").write_text(
        json.dumps({"id": "sample", "source_head": "abc", "status": "prepared"}),
        encoding="utf8",
    )
    return folder


def test_duplicate_attempt_does_not_replace_first(tmp_path, monkeypatch):
    folder = prepared(tmp_path)
    state = load_state_module()
    monkeypatch.setattr(state, "STATE", tmp_path)
    first = state.begin_attempt("sample", "proposal", "abc")
    with pytest.raises(FileExistsError):
        state.begin_attempt("sample", "proposal", "abc")
    assert state.load_state("sample")["attempts"] == [first]
    assert (folder / "running.lock").is_file()


def test_unknown_crash_keeps_lock_and_evidence(tmp_path, monkeypatch):
    folder = prepared(tmp_path)
    state = load_state_module()
    monkeypatch.setattr(state, "STATE", tmp_path)
    attempt = state.begin_attempt("sample", "proposal", "abc")
    result = state.recover("sample", {"process": "unknown", "attempt_id": attempt["id"]})
    assert result["status"] == "blocked_unknown"
    assert (folder / "running.lock").is_file()
    assert state.load_state("sample")["attempts"][0]["id"] == attempt["id"]


def test_recover_rejects_forged_terminal_observation_and_preserves_state(tmp_path, monkeypatch):
    folder = prepared(tmp_path)
    state = load_state_module()
    monkeypatch.setattr(state, "STATE", tmp_path)
    attempt = state.begin_attempt("sample", "proposal", "abc")
    lock = folder / "running.lock"
    before = (folder / "state.json").read_bytes()

    result = state.recover("sample", {
        "process": "exited", "validated": True, "attempt_id": attempt["id"],
        "outcome": {"status": "completed", "exit": 0},
    })

    assert result["status"] == "blocked_unknown"
    assert "trusted evidence" in result["reason"]
    assert (folder / "state.json").read_bytes() == before
    assert lock.is_file()
def test_finish_attempt_rejects_untrusted_direct_outcome(tmp_path, monkeypatch):
    folder = prepared(tmp_path)
    state = load_state_module()
    monkeypatch.setattr(state, "STATE", tmp_path)
    attempt = state.begin_attempt("sample", "proposal", "abc")
    before = (folder / "state.json").read_bytes()

    with pytest.raises(ValueError, match="validated workflow outcome"):
        state.finish_attempt("sample", attempt["id"], {"status": "completed", "exit": 0})

    assert (folder / "state.json").read_bytes() == before
    assert (folder / "running.lock").is_file()
def test_completed_attempt_survives_reload_with_evidence_pointer(tmp_path, monkeypatch):
    folder = prepared(tmp_path)
    state = load_state_module()
    monkeypatch.setattr(state, "STATE", tmp_path)
    attempt = state.begin_attempt("sample", "proposal", "abc")
    state._finish_attempt("sample", attempt["id"], {"status": "stage_output_needs_review", "evidence": "report.json"}, _authority=state._FINISH_ATTEMPT_AUTHORITY)
    assert not (folder / "running.lock").exists()
    reloaded = load_state_module()
    monkeypatch.setattr(reloaded, "STATE", tmp_path)
    saved = reloaded.load_state("sample")
    assert saved["attempts"][0]["evidence"] == "report.json"
    assert saved["delivery_accepted"] is False


def test_prepare_initializes_empty_attempt_ledger(tmp_path, monkeypatch):
    from types import SimpleNamespace

    entry = Path(__file__).resolve().parents[1] / "handoff.py"
    spec = importlib.util.spec_from_file_location("handoff_prepare_under_test", entry)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "STATE", tmp_path)
    full_row = "fixture queue complete row"
    def query(argv, **kwargs):
        if "--field" in argv:
            return {"exit": 0, "stdout": full_row, "stderr": ""}
        return {"exit": 0, "stdout": json.dumps({
            "found": True, "carrier": "live", "done": False, "row": "648", "section": "一",
            "error": None, "read_errors": [], "file": "fixture-queue.md", "line": 1}), "stderr": ""}
    monkeypatch.setattr(module, "execute", query)
    monkeypatch.setattr(module, "git", lambda *a, **k: {
        "exit": 0,
        "stdout": str(tmp_path / "repo.git") if "--git-common-dir" in a else "abc",
        "stderr": ""})
    approval = tmp_path / "intent-approval.json"
    approval.write_text(json.dumps({"task_id": "sample-task", "row": 648, "section": "一",
        "action_key": "worktree_local_build", "intent_sha256": hashlib.sha256(b"fixture").hexdigest(),
        "queue_file": "fixture-queue.md", "queue_line": 1,
        "queue_full_sha256": hashlib.sha256(b"old row").hexdigest(),
        "text": "approved fixture"}), encoding="utf8")
    with pytest.raises(ValueError, match="approval"):
        module.prepare(SimpleNamespace(id="sample-task", row=648, section="一", intent="fixture",
                                       action_key="worktree_local_build", intent_approval=str(approval)))
    approved = json.loads(approval.read_text(encoding="utf8"))
    approved["queue_full_sha256"] = hashlib.sha256(full_row.encode("utf8")).hexdigest()
    approval.write_text(json.dumps(approved), encoding="utf8")
    assert module.prepare(SimpleNamespace(id="sample-task", row=648, section="一", intent="fixture",
                                          action_key="worktree_local_build", intent_approval=str(approval))) == 0
    saved = json.loads((tmp_path / "runs" / "sample-task" / "state.json").read_text(encoding="utf8"))
    assert saved["phase"] == "intent"
    assert saved["source_checkout"] == str(module.ROOT.resolve())
    assert saved["phase_status"] == "prepared"
    assert saved["attempts"] == []
    assert saved["delivery_accepted"] is False
    assert saved["queue_full_sha256"] == hashlib.sha256(full_row.encode("utf8")).hexdigest()


def test_attempt_prepare_callback_runs_only_after_lock_and_persists_with_attempt(tmp_path, monkeypatch):
    folder = prepared(tmp_path)
    state = load_state_module()
    monkeypatch.setattr(state, "STATE", tmp_path)
    calls = []

    def prepare(current):
        assert (folder / "running.lock").is_file()
        calls.append(True)
        current["review_history"] = [{"attempt_id": "old-review"}]
        current["phase"] = "test"

    attempt = state.begin_attempt("sample", "proposal", "abc", prepare=prepare)
    saved = state.load_state("sample")
    assert calls == [True]
    assert saved["phase"] == "test"
    assert saved["phase_status"] == "running"
    assert saved["review_history"] == [{"attempt_id": "old-review"}]
    assert saved["attempts"] == [attempt]
