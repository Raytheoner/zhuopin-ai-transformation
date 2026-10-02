"""Pure, fail-closed evidence gates for task-driven Codex stage advancement."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

LANE_SCRIPT = Path(__file__).resolve().parents[1] / "工具-泳道看护状态机.py"
_STATE_SPEC = importlib.util.spec_from_file_location(
    "workflow_gate_state_evidence", Path(__file__).with_name("workflow_state.py"))
_STATE = importlib.util.module_from_spec(_STATE_SPEC)
sys.modules[_STATE_SPEC.name] = _STATE
_STATE_SPEC.loader.exec_module(_STATE)


def _decision(status: str, reason: str, next_phase: str | None = None) -> dict:
    return {"next_phase": next_phase, "status": status, "reason": reason}


def _sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value.lower())


def _valid_file(ref: object) -> bool:
    if not isinstance(ref, dict) or not _sha(ref.get("sha256")):
        return False
    try:
        path = Path(ref["path"])
        return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == ref["sha256"].lower()
    except (KeyError, OSError, TypeError, ValueError):
        return False


def _action_tier(action_key: str) -> str:
    spec = importlib.util.spec_from_file_location("workflow_gate_lane_classifier", LANE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.classify(action_key).tier


def _review_report_is_valid(task_state: dict, evidence: dict) -> bool:
    report_ref = evidence.get("review_report")
    if (not isinstance(report_ref, dict) or not isinstance(report_ref.get("path"), str)
            or not Path(report_ref["path"]).is_absolute() or not _valid_file(report_ref)):
        return False
    try:
        report = json.loads(Path(report_ref["path"]).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, TypeError):
        return False
    head = task_state.get("implementation_head")
    thread_id = report.get("thread_id") if isinstance(report, dict) else None
    return (
        isinstance(report, dict)
        and report.get("task_id") == task_state.get("id")
        and report.get("implementation_head") == head
        and report.get("ci_report") == task_state.get("ci_report")
        and isinstance(thread_id, str) and bool(thread_id)
        and thread_id != task_state.get("implementation_thread_id")
        and report.get("conclusion") == "approved" and report.get("findings") == []
        and evidence.get("review_head") == head
        and evidence.get("review_thread_id") == thread_id
        and evidence.get("review_conclusion") == "approved"
        and evidence.get("review_findings") == []
    )


def decide_next(state: dict, evidence: dict) -> dict:
    """Return one permitted next phase, or the reason this task must stop."""
    if not isinstance(state, dict) or not isinstance(evidence, dict):
        return _decision("blocked", "invalid state or evidence")
    action = evidence.get("action_key")
    if action:
        tier = _action_tier(action)
        if tier == "🔴":
            return _decision("blocked", "red action cannot be automated")
        if tier == "🟡":
            return _decision("paused", "human decision required")
        if tier == "⏭️":
            return _decision("paused", "transfer to LAN closeout required")
    phase = state.get("phase")
    if phase == "intent":
        approval = evidence.get("intent_approval")
        if (not isinstance(approval, dict) or not _valid_file(evidence.get("intent_approval_ref"))
                or not _valid_file(evidence.get("intent_ref"))
                or evidence.get("intent_ref") != state.get("intent_ref")
                or evidence.get("intent_sha256") != state.get("intent_ref", {}).get("sha256")
                or approval.get("task_id") != state.get("id")
                or approval.get("row") != state.get("row")
                or approval.get("section") != state.get("section")
                or approval.get("action_key") != state.get("action_key")
                or approval.get("intent_sha256") != evidence.get("intent_text_sha256")
                or evidence.get("intent_text_sha256") != state.get("intent_text_sha256")
                or not isinstance(approval.get("text"), str) or not approval["text"].strip()):
            return _decision("paused", "intent and action classification approval required")
        if (state.get("source_head") and isinstance(evidence.get("queue_row"), int)
                and evidence["queue_row"] > 0 and _sha(evidence.get("intent_sha256"))):
            return _decision("ready", "intent verified", "proposal")
        return _decision("blocked", "queue, intent or source HEAD missing")
    if phase == "proposal":
        if not (state.get("design_head") and evidence.get("openspec_valid") is True
                and _valid_file(evidence.get("design"))
                and _sha(evidence.get("proposal_sha256")) and _sha(evidence.get("tasks_sha256"))):
            return _decision("blocked", "OpenSpec proposal evidence incomplete")
        approval = evidence.get("approval")
        if approval is None:
            return _decision("paused", "design review required")
        if not isinstance(approval, dict) or not approval.get("text", "").strip():
            return _decision("blocked", "invalid design approval")
        if (approval.get("task_id") != state.get("id")
                or approval.get("design_head") != state["design_head"]
                or approval.get("design_sha256") != evidence["design"]["sha256"]):
            return _decision("blocked", "design approval drift")
        return _decision("ready", "approved design matches evidence", "implement")
    if phase == "implement":
        model_status = evidence.get("model_status")
        if model_status == "tool_failed":
            if (evidence.get("tool_failure_review_required") is not True
                    or not isinstance(evidence.get("native_tool_failures"), int)
                    or evidence["native_tool_failures"] < 1
                    or evidence["native_tool_failures"] != evidence.get("model_tool_failures")):
                return _decision("blocked", "tool failures lack matched native review evidence")
        elif model_status != "output_needs_review":
            return _decision("blocked", "model output not reviewable")
        if (not state.get("implementation_head") or not evidence.get("thread_id")
                or evidence.get("thread_id") != evidence.get("native_thread_id")
                or not state.get("workspace") or evidence.get("native_workspace") != state["workspace"]):
            return _decision("blocked", "native identity or implementation HEAD missing")
        if not evidence.get("native_tool_events") or not evidence.get("native_hook_events"):
            return _decision("blocked", "native tool or hook evidence missing")
        artifacts = evidence.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts or not all(_valid_file(a) for a in artifacts):
            return _decision("blocked", "artifact hash mismatch")
        try:
            sentinel = Path(evidence["sentinel"])
            started = datetime.fromisoformat(state["attempt_started_at"]).timestamp()
            if not sentinel.is_file() or sentinel.stat().st_mtime < started:
                return _decision("blocked", "stale or missing sentinel")
        except (KeyError, OSError, TypeError, ValueError):
            return _decision("blocked", "invalid sentinel evidence")
        return _decision("ready", "implementation evidence verified", "test")
    if phase == "test":
        ci_state = {**state, "ci_targets": evidence.get("ci_targets")}
        ci_error = _STATE.ci_evidence_error(ci_state)
        if not ci_error and state.get("implementation_head"):
            return _decision("ready", "target CI passed", "review")
        return _decision("blocked", ci_error or "target CI incomplete or failed")
    if phase == "review":
        ci_error = _STATE.ci_evidence_error(state)
        if ci_error:
            return _decision("blocked", "target CI invalid: " + ci_error)
        if state.get("implementation_head") and _review_report_is_valid(state, evidence):
            return _decision("ready", "independent review passed", "release_ready")
        return _decision("blocked", "review evidence incomplete or conflicting")
    if phase == "release_ready":
        return _decision("paused", "item-specific ff or transfer authorization required")
    return _decision("blocked", "unknown workflow phase")
