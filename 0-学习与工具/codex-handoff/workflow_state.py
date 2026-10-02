"""Fail-closed, task-local state for Codex stage attempts.

Lane pause/heartbeat/deploy state belongs to 工具-泳道看护状态机.py.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE = Path(os.environ.get("ZHUOPIN_CODEX_STATE", str(ROOT / ".codex" / "state")))
_FINISH_ATTEMPT_AUTHORITY = object()


def _folder(task_id: str) -> Path:
    if not task_id or task_id in (".", "..") or "/" in task_id or "\\" in task_id:
        raise ValueError("invalid task id")
    return STATE / "runs" / task_id


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, value: dict) -> None:
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def load_state(task_id: str) -> dict:
    return json.loads((_folder(task_id) / "state.json").read_text(encoding="utf8"))


def ci_target_is_valid(target: object, workspace: str | Path) -> bool:
    """Validate the exact project-scoped pytest command recorded by the driver."""
    if not isinstance(target, dict):
        return False
    try:
        nodeid = target.get("nodeid")
        if (not isinstance(nodeid, str) or not nodeid or nodeid.startswith(("/", "\\"))
                or "\\" in nodeid or ":" in nodeid
                or any(part in ("", ".", "..") for part in nodeid.split("/"))):
            return False
        root = Path(workspace).resolve()
        project = (root / nodeid).resolve()
        argv = target.get("argv")
        if (not isinstance(argv, list) or len(argv) != 6
                or not isinstance(argv[0], str) or not Path(argv[0]).is_absolute()
                or Path(argv[0]).name.lower() not in ("python", "python.exe")
                or argv[1:] != ["-m", "pytest", "-q", "--tb=short", "--junit-xml=pytest-result.xml"]):
            return False
        return (project != root and project.is_relative_to(root) and project.is_dir()
                and Path(target["cwd"]).resolve() == project)
    except (OSError, KeyError, TypeError, ValueError):
        return False


def _linked(info) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _safe_parent(path: Path, root: Path) -> None:
    """Reject redirected ancestors before opening any evidence file."""
    if not path.is_absolute() or not root.is_absolute() or not path.is_relative_to(root):
        raise ValueError("JUnit path outside evidence boundary")
    for parent in (path.parent, *path.parent.parents):
        info = parent.lstat()
        if _linked(info) or not stat.S_ISDIR(info.st_mode):
            raise ValueError("JUnit redirected parent")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("JUnit resolved path outside evidence boundary")


def _file_identity(info) -> tuple:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def _regular_info(path: Path):
    info = path.lstat()
    if _linked(info) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("JUnit is not an owned regular file")
    return info


def _read_regular(path: Path, root: Path) -> tuple[bytes, tuple]:
    _safe_parent(path, root)
    before = _file_identity(_regular_info(path))
    with path.open("rb") as stream:
        opened = _file_identity(os.fstat(stream.fileno()))
        # Windows path stat and handle stat can expose different ctime values.
        # Compare ctime only within the same API, retaining identity/size/mtime across APIs.
        if opened[:-1] != before[:-1]:
            raise ValueError("JUnit file replaced before read")
        content = stream.read()
        if _file_identity(os.fstat(stream.fileno())) != opened:
            raise ValueError("JUnit file changed during read")
    if _file_identity(_regular_info(path)) != before:
        raise ValueError("JUnit file replaced during read")
    return content, before


class _NoDoctype(ET.TreeBuilder):
    def doctype(self, name, pubid, system):
        raise ValueError("JUnit DTD/ENTITY forbidden")


def junit_xml_error(content: bytes) -> str:
    """Parse bytes without DTD/entity expansion; totals are checked, never summed."""
    try:
        root = ET.fromstring(content, parser=ET.XMLParser(target=_NoDoctype()))
        suites = list(root.iter("testsuite"))
        if root.tag not in ("testsuites", "testsuite") or not suites:
            return "JUnit suite missing"
        for element in root.iter():
            if element.tag in ("failure", "error"):
                return "JUnit failure/error element"
            if element.tag not in ("testsuite", "testsuites"):
                continue
            if element.tag == "testsuite" and any(key not in element.attrib for key in ("tests", "failures", "errors")):
                return "JUnit counts missing"
            for key in ("tests", "failures", "errors", "skipped"):
                value = element.get(key)
                if value is not None and not re.fullmatch(r"[0-9]+", value):
                    return "JUnit invalid count"
                if key in ("failures", "errors") and value is not None and int(value) != 0:
                    return "JUnit reports failures/errors"
        return ""
    except (ET.ParseError, ValueError, TypeError, LookupError):
        return "JUnit malformed or unsafe XML"


def _junit_evidence_error(current: dict, report: dict, *, allow_legacy=False) -> str:
    targets = current["ci_targets"]
    attempt_id = report.get("attempt_id")
    roots = report.get("expected_roots")
    if attempt_id is None and not allow_legacy:
        return "CI attempt missing; refresh CI evidence"
    if attempt_id is not None:
        if not isinstance(attempt_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", attempt_id):
            return "CI attempt invalid"
        attempts = [a for a in current.get("attempts", []) if isinstance(a, dict) and a.get("id") == attempt_id]
        if len(attempts) != 1 or attempts[0].get("phase") != "test":
            return "CI attempt not in task ledger"
    names = [t.get("nodeid") for t in targets]
    if any(not isinstance(n, str) for n in names) or len(set(names)) != len(names):
        return "CI duplicate or invalid targets"
    if roots is None and not allow_legacy:
        return "CI expected roots missing; refresh CI evidence"
    if roots is not None and (not isinstance(roots, list) or not roots
            or any(not isinstance(r, str) for r in roots) or len(set(roots)) != len(roots)
            or set(roots) != set(names)):
        return "CI expected roots mismatch"
    try:
        folder = _folder(current["id"]).absolute()
        for index, target in enumerate(targets):
            if target.get("junit_error") or target.get("execution_error"):
                return "JUnit capture or execution failed"
            if allow_legacy and "junit_path" not in target and "junit_sha256" not in target:
                continue
            value, digest = target.get("junit_path"), target.get("junit_sha256")
            if (not isinstance(value, str) or not Path(value).is_absolute()
                    or not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest)):
                return "JUnit reference missing or invalid"
            path = Path(value)
            if attempt_id is None or path != folder / f"ci-{attempt_id}-{index}.junit.xml":
                return "JUnit task/attempt path mismatch"
            content, _ = _read_regular(path, folder)
            if hashlib.sha256(content).hexdigest() != digest:
                return "JUnit hash mismatch"
            error = junit_xml_error(content)
            if error:
                return error
    except (OSError, ValueError, KeyError, TypeError):
        return "JUnit unavailable or unsafe path"
    return ""


def ci_evidence_error(current: dict) -> str:
    """Return a concrete reason when canonical, raw-backed project CI is incomplete."""
    targets = current.get("ci_targets")
    if not isinstance(targets, list) or not targets or not all(
            isinstance(target, dict) and target.get("nodeid") and target.get("exit") == 0
            for target in targets):
        return "target CI missing or failed"
    workspace = current.get("workspace")
    if not isinstance(workspace, str) or not workspace:
        return "CI project working directory or command mismatch"
    for target in targets:
        if not ci_target_is_valid(target, workspace):
            return "CI project working directory or command mismatch"
        for stream in ("stdout", "stderr"):
            path_value = target.get(stream + "_path")
            digest = target.get(stream + "_sha256")
            if not isinstance(path_value, str) or not Path(path_value).is_absolute() or not isinstance(digest, str):
                return "CI raw output missing; refresh CI evidence"
            try:
                if hashlib.sha256(Path(path_value).read_bytes()).hexdigest() != digest:
                    return "CI output hash mismatch"
            except OSError:
                return "CI output unavailable"
    report_ref = current.get("ci_report")
    if (not isinstance(report_ref, dict) or not isinstance(report_ref.get("path"), str)
            or not Path(report_ref["path"]).is_absolute()
            or not isinstance(report_ref.get("sha256"), str)):
        return "CI report missing"
    try:
        report_path = Path(report_ref["path"])
        if (not report_path.is_file()
                or hashlib.sha256(report_path.read_bytes()).hexdigest() != report_ref["sha256"]):
            return "CI report hash mismatch"
        report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, TypeError):
        return "CI report unreadable"
    if (not isinstance(report, dict) or report.get("task_id") != current.get("id")
            or report.get("implementation_head") != current.get("implementation_head")
            or report.get("targets") != targets):
        return "CI report conflicts with task HEAD or targets"
    return _junit_evidence_error(current, report)


def ci_evidence_is_valid(current: dict) -> bool:
    return ci_evidence_error(current) == ""


def begin_attempt(task_id: str, phase: str, expected_head: str, *,
                  expected_state_snapshot: tuple | None = None, prepare=None) -> dict:
    folder = _folder(task_id)
    lock = folder / "running.lock"
    try:
        stream = lock.open("x", encoding="utf8")
    except FileExistsError:
        raise
    try:
        with stream:
            stream.write(json.dumps({"phase": phase, "time": _now()}))
        current = load_state(task_id)
        anchor = (
            current.get("implementation_head") if phase in ("test", "review")
            else current.get("design_head", current["source_head"]) if phase == "implement"
            else current["source_head"]
        )
        if not expected_head or anchor != expected_head:
            raise ValueError("HEAD drift")
        snapshot = (current.get("phase"), current.get("phase_status"),
                    len(current.get("attempts") or []))
        if expected_state_snapshot is not None and snapshot != expected_state_snapshot:
            raise ValueError("task state changed before attempt")
        if prepare is not None:
            prepare(current)
        attempt = {"id": uuid.uuid4().hex, "phase": phase, "status": "running", "started_at": _now()}
        current.setdefault("attempts", []).append(attempt)
        current["phase_status"] = "running"
        current["delivery_accepted"] = False
        _write_json(folder / "state.json", current)
        return attempt
    except Exception:
        lock.unlink(missing_ok=True)
        raise


def finish_attempt(task_id: str, attempt_id: str, outcome: dict) -> dict:
    """Reject direct settlement; outcomes must pass the workflow driver first."""
    raise ValueError("validated workflow outcome required")


def _finish_attempt(task_id: str, attempt_id: str, outcome: dict, *, _authority: object) -> dict:
    """Internal state mutation for an outcome validated by workflow_driver."""
    if _authority is not _FINISH_ATTEMPT_AUTHORITY:
        raise ValueError("validated workflow outcome required")
    folder = _folder(task_id)
    lock = folder / "running.lock"
    if not lock.is_file():
        raise ValueError("no active attempt lock")
    current = load_state(task_id)
    attempts = current.get("attempts", [])
    if not attempts or attempts[-1]["id"] != attempt_id or attempts[-1]["status"] != "running":
        raise ValueError("attempt mismatch")
    if not isinstance(outcome, dict) or not outcome.get("status"):
        raise ValueError("outcome status required")
    result = {k: v for k, v in outcome.items() if k != "delivery_accepted"}
    attempts[-1].update(result)
    attempts[-1]["finished_at"] = _now()
    current["phase_status"] = result["status"]
    current["delivery_accepted"] = False
    _write_json(folder / "state.json", current)
    lock.unlink()
    return current


def recover(task_id: str, observed: dict | None = None) -> dict:
    """Never trust caller-created observations to settle a running attempt.

    Recovery through this low-level API is always fail-closed. The workflow
    driver alone may settle a validated outcome through its private path.
    Unknown attempts and their locks remain untouched.
    """
    current = load_state(task_id)
    attempts = current.get("attempts", [])
    if not attempts:
        return {"status": "blocked_unknown", "reason": "no attempt"}
    latest = attempts[-1]
    if latest["status"] != "running":
        return {"status": latest["status"], "attempt_id": latest["id"]}
    return {
        "status": "blocked_unknown",
        "reason": "caller-supplied observation is not trusted evidence",
        "attempt_id": latest["id"],
    }
