"""Release preparation and LAN transfer records; never execute ff or production."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location("workflow_release_" + name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


state = _load("state", BASE / "workflow_state.py")
gate = _load("gate", BASE / "workflow_gate.py")
lane_machine = _load("lane", ROOT / "0-学习与工具" / "工具-泳道看护状态机.py")
handoff = _load("handoff", BASE / "handoff.py")
execute = handoff.execute
requirements = _load("requirements", BASE / "workflow_requirements.py")


def patchid_compare(branch: str) -> dict:
    script = _load("patchid", ROOT / "0-学习与工具" / "工具-patchid比对.py")
    return script.compare(branch=branch, base="master", repo=ROOT)


def _verified(task_id: str) -> tuple[dict | None, str]:
    try:
        current = state.load_state(task_id)
    except (OSError, ValueError, KeyError):
        return None, "task state unavailable"
    if current.get("phase") != "review" or not current.get("implementation_head"):
        return None, "independent review phase missing"
    if (state._folder(task_id) / "running.lock").exists():
        return None, "review attempt still running"
    attempts = current.get("attempts") or []
    adjudications = current.get("review_adjudications") or []
    latest = attempts[-1] if attempts else {}
    if (current.get("phase_status") != "stage_output_needs_review"
            or latest.get("phase") != "review" or not latest.get("finished_at")
            or not (latest.get("status") == "stage_output_needs_review"
                    or latest.get("status") == "blocked" and adjudications
                    and adjudications[-1].get("attempt_id") == latest.get("id"))):
        return None, "review attempt not finalized"
    ci_error = state.ci_evidence_error(current)
    if ci_error:
        return None, ci_error
    targets = current.get("ci_targets")
    ci_ref = current.get("ci_report")
    review_evidence = current.get("review_evidence")
    if not gate._valid_file(ci_ref) or not isinstance(review_evidence, dict):
        return None, "CI report or review missing"
    review_ref = review_evidence.get("review_report")
    if not gate._valid_file(review_ref):
        return None, "review report hash mismatch"
    native_review_ref = review_evidence.get("review_result")
    if native_review_ref is not None and not gate._valid_file(native_review_ref):
        return None, "native review result hash mismatch"
    native_events_ref = review_evidence.get("review_events")
    if native_review_ref is not None and not gate._valid_file(native_events_ref):
        return None, "native review events hash mismatch"
    try:
        ci = json.loads(Path(ci_ref["path"]).read_text(encoding="utf8"))
        review = json.loads(Path(review_ref["path"]).read_text(encoding="utf8"))
    except (OSError, ValueError):
        return None, "machine report unreadable"
    head = current["implementation_head"]
    if review.get("review_failure_class") is not None:
        adjudications = current.get("review_adjudications") or []
        if (review.get("review_failure_class") != "optional_missing_path"
                or review.get("review_tool_failures") != 1 or not native_review_ref
                or not adjudications or adjudications[-1].get("result") != native_review_ref
                or adjudications[-1].get("classification") != "optional_missing_path"):
            return None, "review failure adjudication missing"
    if (ci.get("task_id") != task_id or ci.get("implementation_head") != head
            or ci.get("targets") != targets
            or review.get("ci_report") != ci_ref
            or review.get("task_id") != task_id or review.get("implementation_head") != head
            or not review.get("thread_id")
            or not current.get("implementation_thread_id")
            or review.get("thread_id") == current.get("implementation_thread_id")
            or review.get("conclusion") != "approved" or review.get("findings") != []
            or review_evidence.get("review_head") != head
            or review_evidence.get("review_thread_id") != review.get("thread_id")
            or review_evidence.get("review_conclusion") != "approved"
            or review_evidence.get("review_findings") != []):
        return None, "CI or independent review report conflicts with task HEAD"
    return current, ""


def prepare_release(task_id: str, evidence: dict) -> dict:
    if not isinstance(evidence, dict) or evidence.get("action_key") != "merge_to_master":
        return {"status": "blocked", "reason": "action cannot be prepared for automatic release"}
    current, reason = _verified(task_id)
    if current is None:
        return {"status": "blocked", "reason": reason}
    branch = evidence.get("branch")
    if not isinstance(branch, str) or not branch.strip():
        return {"status": "blocked", "reason": "branch required for patch-id precheck"}
    try:
        patch = patchid_compare(branch)
    except (OSError, ValueError, RuntimeError) as exc:
        return {"status": "blocked", "reason": "patch-id precheck failed: " + str(exc)}
    if patch.get("branch_sha") != current["implementation_head"]:
        return {"status": "blocked", "reason": "branch HEAD differs from reviewed implementation"}
    request = {"task_id": task_id, "branch": branch, "implementation_head": current["implementation_head"],
               "ci_report": current["ci_report"], "review_report": current["review_evidence"]["review_report"],
               "patchid": patch, "delivery_accepted": False, "ff_executed": False}
    path = state._folder(task_id) / "release-request.json"
    state._write_json(path, request)
    if patch.get("verdict") == "in_master" and patch.get("all_in_master") is True:
        return {"status": "skip_ff", "reason": "patch-id already in master", "request": str(path)}
    if patch.get("verdict") != "needs_merge" or patch.get("all_in_master") is not False:
        return {"status": "blocked", "reason": "unknown patch-id verdict", "request": str(path)}
    return {"status": "paused", "reason": "item-specific ff authorization required",
            "authorization_required": "ff:" + task_id + ":" + current["implementation_head"],
            "request": str(path)}


def transfer_deploy(task_id: str, batch: str, lane: str, item: str, *, wave: int = 1) -> dict:
    current, reason = _verified(task_id)
    if current is None:
        return {"status": "blocked", "reason": reason}
    if not batch or not lane or not item or not item.strip():
        return {"status": "blocked", "reason": "batch, lane and deploy item required"}
    note = task_id + ":" + item.strip()
    present = lane_machine._read_state().get("lanes", {}).get(lane, {})
    if any(t.get("batch") == batch and t.get("action_key") == "deploy_51"
           and t.get("note") == note for t in present.get("transfers", [])):
        return {"status": "transferred", "item": item, "already_recorded": True,
                "pointer": lane_machine.deploy_discipline_pointer()}
    # An explicit no-op callback prevents the source helper's default WeCom send.
    transfer = lane_machine.transfer_out_lane(batch=batch, wave=wave, lane=lane,
                                               action_key="deploy_51", note=note,
                                               notify_fn=lambda _message: None)
    return {"status": "transferred", "item": item,
            "pointer": lane_machine.deploy_discipline_pointer(),
            "evidence": transfer, "production_executed": False}


def closeout(task_id: str, workspace: Path, *, executor=None) -> dict:
    """Archive only verified local work; caller retains the original queue lock.

    This does not publish, commit, alter old CI/review evidence, or claim that
    receipt consumption is equivalent to downstream business delivery.
    """
    workspace = Path(workspace).resolve()
    current, reason = _verified(task_id)
    if current is None:
        return {'status': 'blocked', 'reason': reason}
    head = handoff.git('rev-parse', 'HEAD', cwd=workspace)
    if (str(workspace) != current.get('workspace') or head['exit']
            or head['stdout'].strip() != current['implementation_head']):
        return {'status': 'blocked', 'reason': 'closeout workspace or reviewed HEAD drift'}
    observed = handoff.git('status', '--porcelain', '--untracked-files=all', cwd=workspace)
    permitted = {'docs/requirements/INDEX.md', f'openspec/changes/{task_id}/tasks.md',
                 f'openspec/changes/{task_id}/acceptance.json',
                 f'openspec/changes/{task_id}/acceptance-functional.json'}
    if observed['exit'] or any(line[3:].replace('\\', '/') not in permitted
                               for line in observed['stdout'].splitlines()):
        return {'status': 'blocked', 'reason': 'unverified changes outside closeout metadata'}
    checked = requirements.inspect(workspace, task_id, stage='closeout')
    if checked['status'] != 'ready':
        return checked
    if (current.get('requirements_contract') or {}).get('business_acceptance_required'):
        try:
            packet=json.loads((workspace/f'openspec/changes/{task_id}/acceptance.json').read_text(encoding='utf8'))
            trusted=[{'path':t['junit_path'],'sha256':t['junit_sha256']} for t in current['ci_targets']]
            acceptance=_load('business_acceptance',BASE/'business_acceptance.py').verify(
                workspace,task_id,packet,trusted_junit=trusted)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            return {'status':'blocked','reason':'business acceptance missing/invalid: '+str(exc)}
        if acceptance['status']!='accepted':
            return {'status':'blocked','reason':'business acceptance failed: '+acceptance['reason']}
    if executor is None:
        # Same Windows shim and execution contract as the original driver.
        executor = _load('driver', BASE / 'workflow_driver.py').default_executor
    validated = executor(['openspec', 'validate', task_id, '--strict'], cwd=workspace, timeout=120)
    if validated.get('exit') != 0:
        return {'status':'blocked', 'reason':'closeout OpenSpec validation failed', 'validation':validated}
    archived = executor(['openspec', 'archive', task_id, '-y'], cwd=workspace, timeout=120)
    if archived.get('exit') != 0:
        return {'status':'blocked', 'reason':'OpenSpec archive failed; no queue closeout', 'archive':archived}
    matches = list((workspace / 'openspec/changes/archive').glob('*-' + task_id))
    if (workspace / 'openspec/changes' / task_id).exists() or len(matches) != 1:
        return {'status':'blocked', 'reason':'archive location not proven; no queue closeout'}
    archived_change = matches[0]
    if requirements.lint.package_fingerprint(archived_change) != checked['package_sha256']:
        return {'status':'blocked', 'reason':'archived package differs from checked package'}
    # Verify each delta requirement made it into the main spec. OpenSpec handles
    # merge semantics; this postcondition also detects a no-op/simulated archive.
    import re
    for delta in (archived_change / 'specs').glob('*/spec.md'):
        main = workspace / 'openspec/specs' / delta.parent.name / 'spec.md'
        if not main.is_file():
            return {'status':'blocked', 'reason':'synced main spec missing'}
        text = delta.read_text(encoding='utf8')
        sections = re.split(r'^## ', text, flags=re.M)
        for section in sections:
            if section.startswith(('ADDED Requirements', 'MODIFIED Requirements')):
                for heading in re.findall(r'^### Requirement: .+$', section, re.M):
                    if heading not in main.read_text(encoding='utf8'):
                        return {'status':'blocked', 'reason':'main spec sync not proven'}
    return {'status':'archived', 'archive_path':archived_change.relative_to(workspace).as_posix(),
            'task_id':task_id, 'row':current.get('row'), 'queue_writeback_ready':True,
            'reviewed_head':current['implementation_head'], 'delivery_accepted':False,
            'requires_revalidation_after_commit':True,
            'next':'持原共享锁更新 INDEX 为 archive，并用原队列工具只销本地对应项；登记 §二后 release/status。'}
