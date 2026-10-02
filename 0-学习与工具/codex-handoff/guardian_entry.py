"""Human-start guardian entry: live queue lookup, LAN probe, watch-piece DryRun, then approved stages."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
QUERY = ROOT / "0-学习与工具" / "工具-队列查询.py"
LINT = ROOT / "0-学习与工具" / "工具-opener块lint.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location("guardian_entry_" + name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


guardian = _load("adapter", BASE / "guardian_adapter.py")
handoff = _load("handoff", BASE / "handoff.py")


def _blocked(reason: str, **details) -> dict:
    return {"status": "blocked", "reason": reason, "delivery_accepted": False, **details}


def _live_candidate(candidate: dict, execute) -> tuple[dict, dict]:
    row = candidate.get("row")
    section = candidate.get("section")
    excerpt = candidate.get("task_excerpt")
    if (not isinstance(row, int) or isinstance(row, bool) or row < 1
            or section not in ("一", "四")
            or not isinstance(excerpt, str) or not excerpt.strip()
            or not isinstance(candidate.get("next_action"), str)
            or not candidate["next_action"].strip()
            or not isinstance(candidate.get("lan_required"), bool)):
        raise ValueError("queue candidate requires row, section, exact task excerpt, next_action and explicit lan_required")
    base = [sys.executable, str(QUERY), "--row", str(row), "--section", section]
    status = execute([*base, "--format", "json"], cwd=ROOT, timeout=90)
    if status.get("exit") != 0:
        raise ValueError("queue query failed")
    try:
        found = json.loads(status.get("stdout", ""))
    except (ValueError, TypeError) as exc:
        raise ValueError("queue query returned invalid JSON") from exc
    if (not isinstance(found, dict) or found.get("found") is not True
            or found.get("carrier") != "live" or found.get("done") is not False
            or found.get("error") is not None or found.get("read_errors") != []
            or str(found.get("row")) != str(row) or found.get("section") != section
            or not isinstance(found.get("file"), str) or not found["file"]
            or not isinstance(found.get("line"), int) or found["line"] < 1):
        raise ValueError("queue row is not live and open")
    full = execute([*base, "--field", "all"], cwd=ROOT, timeout=90)
    text = full.get("stdout", "")
    if (full.get("exit") != 0 or not isinstance(text, str)
            or excerpt not in text or candidate["next_action"].strip() not in text):
        raise ValueError("queue full-row excerpt/next action mismatch")
    status_again = execute([*base, "--format", "json"], cwd=ROOT, timeout=90)
    try:
        after = json.loads(status_again.get("stdout", ""))
    except (ValueError, TypeError) as exc:
        raise ValueError("queue query changed during full-row lookup") from exc
    stable = ("row", "section", "found", "carrier", "done", "error",
              "read_errors", "file", "line")
    if status_again.get("exit") != 0 or not isinstance(after, dict) or any(
            after.get(key) != found.get(key) for key in stable):
        raise ValueError("queue query changed during full-row lookup")
    item = dict(candidate)
    evidence = {"task_id": candidate.get("task_id"), "row": row, "section": section,
                "file": found["file"], "line": found["line"],
                "full_sha256": hashlib.sha256(text.encode("utf8")).hexdigest()}
    return item, evidence




def _external_lan_decision(candidate: dict, evidence: dict, manifest: dict) -> str:
    raw_path = candidate.get("lan_decision")
    if not isinstance(raw_path, str) or not Path(raw_path).is_absolute():
        raise ValueError("external LAN classification decision required")
    path = Path(raw_path).resolve()
    protected = [ROOT.resolve()]
    workspaces = manifest.get("workspaces", {})
    if not isinstance(workspaces, dict):
        raise ValueError("workspaces must be a mapping")
    for workspace in workspaces.values():
        if isinstance(workspace, str):
            protected.append(Path(workspace).resolve())
    if any(path == root or path.is_relative_to(root) for root in protected):
        raise ValueError("LAN classification must be outside repository and model workspaces")
    try:
        raw = path.read_bytes()
        decision = json.loads(raw.decode("utf-8-sig"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise ValueError("LAN classification decision invalid") from exc
    expected = {
        "task_id": candidate["task_id"], "row": candidate["row"],
        "section": candidate["section"], "action_key": candidate["action_key"],
        "queue_full_sha256": evidence["full_sha256"],
        "lan_required": candidate["lan_required"],
        "next_action": candidate["next_action"].strip(),
        "lane": candidate["lane"], "touches": candidate["touches"],
    }
    if (not isinstance(decision, dict) or
            any(decision.get(key) != value for key, value in expected.items()) or
            not isinstance(decision.get("lan_required"), bool) or
            not isinstance(decision.get("text"), str) or not decision["text"].strip()):
        raise ValueError("LAN classification does not match live queue candidate")
    return hashlib.sha256(raw).hexdigest()


def _execution_bindings(manifest: dict) -> dict:
    workspaces = manifest.get("workspaces", {})
    if not isinstance(workspaces, dict):
        raise ValueError("workspaces must be a mapping")
    result = {"workspaces": {}}
    for task_id, value in workspaces.items():
        if not isinstance(task_id, str) or not isinstance(value, str):
            raise ValueError("workspace binding must be a path mapping")
        result["workspaces"][task_id] = str(Path(value).resolve())
    return result


def _authorization_evidence(manifest: dict, plan: dict) -> dict:
    authorizations = manifest.get("authorizations", {})
    if not isinstance(authorizations, dict):
        raise ValueError("authorizations must be a mapping")
    workspaces = [Path(path).resolve() for path in
                  plan["execution_bindings"]["workspaces"].values()]
    result = {}
    for task_id, value in authorizations.items():
        if task_id not in plan["dispatchable_ids"] or not isinstance(value, str):
            raise ValueError("authorization must name a dispatchable task and path")
        path = Path(value).resolve()
        if path.is_relative_to(ROOT.resolve()) or any(
                path.is_relative_to(workspace) for workspace in workspaces):
            raise ValueError("authorization must be outside repository and all model workspaces")
        result[task_id] = {"path": str(path),
                           "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return result


def _authorization_seal(plan: dict, manifest: dict, *, append: bool) -> None:
    """Approvals arrive after proposal; seal each new item exactly once under an OS lock."""
    folder = Path(guardian.workflow_state.STATE) / "guardian-authorizations"
    if not append and not folder.is_dir():
        return
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (plan["batch_id"] + ".json")
    provided = _authorization_evidence(manifest, plan)
    with guardian._recovery_mutex(path.with_suffix(".mutex")):
        sealed = (json.loads(path.read_text(encoding="utf-8-sig"))
                  if path.is_file() else {"batch_id": plan["batch_id"], "authorizations": {}})
        if (not isinstance(sealed, dict) or sealed.get("batch_id") != plan["batch_id"]
                or not isinstance(sealed.get("authorizations"), dict)):
            raise ValueError("authorization seal invalid")
        old = sealed["authorizations"]
        if any(task_id not in provided or provided[task_id] != proof
               for task_id, proof in old.items()):
            raise ValueError("authorization differs from sealed item approval")
        if append:
            old.update(provided)
            guardian.workflow_state._write_json(path, sealed)
        elif any(task_id not in old for task_id in provided):
            raise ValueError("authorization has not been sealed for this batch")



def _completed_source(candidate: dict, execute) -> dict:
    """Read-only old-batch source reference; no model stage is replayed."""
    request = candidate.get("release_reference")
    source_id = candidate.get("release_task_id")
    if (not isinstance(request, dict) or "batch_id" not in request
            or not isinstance(source_id, str) or not source_id):
        raise ValueError("completed source batch reference required")
    old_batch = request["batch_id"]
    prior_record_path = guardian._batch_record_path(old_batch)
    folder = Path(guardian.workflow_state.STATE)
    prior_plan = json.loads((folder / "guardian-plans" / (old_batch + ".json")).read_text(
        encoding="utf-8-sig"))
    prior_record = guardian._read_batch_record(prior_record_path, old_batch)
    plan_sha = guardian._plan_sha256(prior_plan)
    source_task = prior_record["tasks"].get(source_id)
    if (prior_plan.get("batch_id") != old_batch or prior_record.get("plan_sha256") != plan_sha
            or not isinstance(source_task, dict)
            or source_task.get("status") != "release_ready"
            or not isinstance(source_task.get("wave"), int)):
        raise ValueError("completed source prior batch proof missing")
    source_rows = [item for item in prior_plan.get("queue_evidence", [])
                   if item.get("task_id") == source_id]
    if len(source_rows) != 1:
        raise ValueError("completed source queue receipt missing")
    source = source_rows[0]
    registry = json.loads((folder / "guardian-claims.json").read_text(encoding="utf-8-sig"))
    key = f"row:{source['section']}:{source['row']}"
    if registry.get("claims", {}).get(key) != {"batch_id": old_batch, "task_id": source_id}:
        raise ValueError("completed source queue claim changed")
    release = guardian._load("release", BASE / "workflow_release.py")
    current, reason = release._verified(source_id)
    if current is None:
        raise ValueError("completed source release gate failed: " + reason)
    if current.get("queue_full_sha256") != source["full_sha256"]:
        raise ValueError("completed source state queue anchor differs")
    base = [sys.executable, str(QUERY), "--row", str(source["row"]),
            "--section", source["section"]]
    status = execute([*base, "--format", "json"], cwd=ROOT, timeout=90)
    full = execute([*base, "--field", "all"], cwd=ROOT, timeout=90)
    status_again = execute([*base, "--format", "json"], cwd=ROOT, timeout=90)
    if status.get("exit") != 0 or full.get("exit") != 0 or status_again.get("exit") != 0:
        raise ValueError("completed source live queue query failed")
    before = json.loads(status["stdout"])
    after = json.loads(status_again["stdout"])
    expected = {"found": True, "carrier": "live", "done": False,
                "error": None, "read_errors": [], "file": source["file"],
                "line": source["line"], "section": source["section"]}
    if (not isinstance(before, dict) or not isinstance(after, dict)
            or any(before.get(field) != value or after.get(field) != value
                   for field, value in expected.items())
            or str(before.get("row")) != str(source["row"])
            or str(after.get("row")) != str(source["row"])
            or hashlib.sha256(full["stdout"].encode("utf8")).hexdigest()
            != source["full_sha256"]):
        raise ValueError("completed source live queue row changed")
    resolved = {"batch_id": old_batch, "source_wave": source_task["wave"],
                "source_plan_sha256": plan_sha,
                "source_head": current["implementation_head"],
                "source_row": source["row"], "source_section": source["section"],
                "source_queue_full_sha256": source["full_sha256"]}
    if request != {"batch_id": old_batch} and request != resolved:
        raise ValueError("completed source reference differs from live proof")
    return resolved

def _transfer_binding(candidate: dict, evidence: dict, rows: dict,
                      receipts: dict, manifest: dict, execute) -> str:
    source_id = candidate.get("release_task_id")
    if candidate.get("action_key") != "deploy_51" or not isinstance(source_id, str):
        raise ValueError("transfer requires deploy_51 and release_task_id")
    source = rows.get(source_id)
    source_receipt = receipts.get(source_id)
    carry = None
    if source is None and candidate.get("release_reference") is not None:
        carry = _completed_source(candidate, execute)
        source = {"row": carry["source_row"], "section": carry["source_section"]}
        source_receipt = {"full_sha256": carry["source_queue_full_sha256"]}
        candidate["release_reference"] = carry
    if source is None or source_receipt is None or source_id == candidate["task_id"]:
        raise ValueError("transfer source must be live in this batch or strictly completed in a prior batch")
    raw_path = candidate.get("transfer_binding")
    if not isinstance(raw_path, str) or not Path(raw_path).is_absolute():
        raise ValueError("external transfer binding file required")
    path = Path(raw_path).resolve()
    protected = [ROOT.resolve()]
    for workspace in manifest.get("workspaces", {}).values():
        if isinstance(workspace, str):
            protected.append(Path(workspace).resolve())
    if any(path == root or path.is_relative_to(root) for root in protected):
        raise ValueError("transfer binding must be outside repository and model workspaces")
    try:
        raw = path.read_bytes()
        binding = json.loads(raw.decode("utf-8-sig"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise ValueError("transfer binding invalid") from exc
    expected = {
        "source_task_id": source_id, "deploy_task_id": candidate["task_id"],
        "source_row": source["row"], "source_section": source["section"],
        "deploy_row": candidate["row"], "deploy_section": candidate["section"],
        "source_queue_full_sha256": source_receipt["full_sha256"],
        "deploy_queue_full_sha256": evidence["full_sha256"],
        "deploy_next_action": candidate["next_action"].strip(),
        "deploy_lane": candidate["lane"],
    }
    if carry is not None:
        expected.update(source_batch_id=carry["batch_id"],
                        source_plan_sha256=carry["source_plan_sha256"],
                        source_implementation_head=carry["source_head"])
    if (not isinstance(binding, dict) or
            any(binding.get(key) != value for key, value in expected.items()) or
            not isinstance(binding.get("text"), str) or not binding["text"].strip()):
        raise ValueError("transfer binding does not match both live queue rows")
    return hashlib.sha256(raw).hexdigest()


def _publish_plan(record: Path, plan: dict) -> None:
    """Write complete bytes, then publish exclusively; a crash never exposes partial JSON."""
    fd, raw = tempfile.mkstemp(prefix=record.stem + ".", suffix=".tmp", dir=record.parent)
    temp = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf8") as stream:
            json.dump(plan, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temp, record)
    finally:
        temp.unlink(missing_ok=True)


def _assert_plan_sources(plan: dict, manifest: dict, rows: list[dict],
                         receipts: list[dict], execute, prober) -> None:
    watch = Path(manifest["watch_piece"])
    if hashlib.sha256(watch.read_bytes()).hexdigest() != plan["watch_sha256"]:
        raise ValueError("watch-piece changed after lint/DryRun")
    by_receipt = {item["task_id"]: item for item in receipts}
    lan_receipts = {item["task_id"]: item["sha256"]
                    for item in plan["lan_evidence"]}
    for item in rows:
        _, current = _live_candidate(item, execute)
        if current != by_receipt[item["task_id"]]:
            raise ValueError("queue row changed after lint/DryRun")
        if (_external_lan_decision(item, current, manifest)
                != lan_receipts[item["task_id"]]):
            raise ValueError("LAN classification changed after lint/DryRun")
    if _execution_bindings(manifest) != plan["execution_bindings"]:
        raise ValueError("workspace or authorization binding changed after lint/DryRun")
    try:
        lan = prober()
    except Exception:
        lan = {"status": "unknown"}
    observed = lan.get("status") if isinstance(lan, dict) else "unknown"
    observed = observed if observed in ("on", "off", "unknown") else "unknown"
    if observed != plan["lan_observed"]:
        raise ValueError("LAN status changed after planning")


def _claim_execution(plan: dict) -> None:
    """Persist cross-batch ownership of live queue rows and active workspaces."""
    folder = Path(guardian.workflow_state.STATE)
    folder.mkdir(parents=True, exist_ok=True)
    registry_path = folder / "guardian-claims.json"
    mutex_path = folder / "guardian-claims.mutex"
    receipts = {item["task_id"]: item for item in plan["queue_evidence"]}
    workspace_paths = plan["execution_bindings"]["workspaces"]
    ownership = {}
    for task_id in [*plan["dispatchable_ids"],
                    *(item["task_id"] for item in plan["transfers"])]:
        item = receipts[task_id]
        key = f"row:{item['section']}:{item['row']}"
        ownership[key] = {"batch_id": plan["batch_id"], "task_id": task_id}
    for lane in dict.fromkeys([*plan["lane_ids"],
                               *(item["lane"] for item in plan["transfers"])]):
        ownership["lane:" + lane.casefold()] = {"batch_id": plan["batch_id"]}
    for task_id in plan["dispatchable_ids"]:
        path = workspace_paths.get(task_id)
        if not isinstance(path, str):
            raise ValueError(f"claim workspace missing for {task_id}")
        key = "workspace:" + str(Path(path).resolve()).casefold()
        if key in ownership and ownership[key]["task_id"] != task_id:
            raise ValueError("claim conflict: two tasks share one workspace")
        ownership[key] = {"batch_id": plan["batch_id"], "task_id": task_id}
    with guardian._recovery_mutex(mutex_path):
        batch_record = Path(guardian.workflow_state.STATE) / "guardian-batches" / (plan["batch_id"] + ".json")
        if batch_record.is_file():
            prior = guardian._read_batch_record(batch_record, plan["batch_id"])
            if prior.get("status") == "retired":
                raise ValueError("claim refused for retired batch")
        if registry_path.is_file():
            registry = json.loads(registry_path.read_text(encoding="utf-8-sig"))
        else:
            registry = {"schema_version": 1, "claims": {}}
        if (not isinstance(registry, dict) or registry.get("schema_version") != 1
                or not isinstance(registry.get("claims"), dict)):
            raise ValueError("claim registry invalid")
        claims = registry["claims"]
        for key, owner in ownership.items():
            current = claims.get(key)
            if current is not None and current != owner:
                raise ValueError(f"claim conflict for {key}")
        # The batch record is published before claims. A crash after ownership
        # is written can then be retired or resumed with evidence.
        batch_record = guardian._batch_record_path(plan["batch_id"])
        batch_record.parent.mkdir(parents=True, exist_ok=True)
        if batch_record.is_file():
            existing = guardian._read_batch_record(batch_record, plan["batch_id"])
            if existing.get("plan_sha256") != guardian._plan_sha256(plan):
                raise ValueError("claimed batch record differs from plan")
            if existing.get("status") == "retired":
                raise ValueError("retired batch cannot claim again")
        else:
            _publish_plan(batch_record, guardian.initial_batch_record(plan))
        claims.update(ownership)
        guardian.workflow_state._write_json(registry_path, registry)


def _release_completed_workspaces(plan: dict, result: dict) -> None:
    tasks = result.get("tasks", {})
    if (result.get("batch_phase") != "release_ready"
            or any(item.get("status") != "release_ready" for item in tasks.values())):
        return
    folder = Path(guardian.workflow_state.STATE)
    registry_path = folder / "guardian-claims.json"
    with guardian._recovery_mutex(folder / "guardian-claims.mutex"):
        registry = json.loads(registry_path.read_text(encoding="utf-8-sig"))
        claims = registry["claims"]
        for task_id, workspace in plan["execution_bindings"]["workspaces"].items():
            key = "workspace:" + str(Path(workspace).resolve()).casefold()
            if claims.get(key) == {"batch_id": plan["batch_id"], "task_id": task_id}:
                claims.pop(key)
        for lane in dict.fromkeys([*plan["lane_ids"],
                                   *(item["lane"] for item in plan["transfers"])]):
            key = "lane:" + lane.casefold()
            if claims.get(key) == {"batch_id": plan["batch_id"]}:
                claims.pop(key)
        guardian.workflow_state._write_json(registry_path, registry)

def _dry_run(plan: dict, execute) -> dict:
    file = Path(plan["file"]) if plan.get("file") else None
    if not file or not file.is_file():
        return _blocked("watch-piece plan missing")
    lint = execute([sys.executable, str(LINT), "--file", str(file), "--enforce"],
                   cwd=ROOT, timeout=120)
    if lint.get("exit") != 0:
        return _blocked("watch-piece lint failed", lint=lint)
    entries = {item["task_id"]: item for item in plan.get("entries", [])}
    receipts = []
    for wave in plan.get("waves", []):
        ids = wave["task_ids"]
        openers = [entries[task_id]["opener_id"] for task_id in ids]
        expected_lanes = list(dict.fromkeys(entries[task_id]["lane"] for task_id in ids))
        argv = ["pwsh", "-NoProfile", "-File", str(guardian.RUNNER), "-Plan", str(file),
                "-Only", ",".join(openers), "-Yes", "-MaxParallel", str(plan["max_parallel"]),
                "-StaggerSec", str(plan["stagger_seconds"]), "-DryRun"]
        dry = execute(argv, cwd=ROOT, timeout=120)
        if dry.get("exit") != 0:
            return _blocked("watch-piece DryRun failed", dry_run=dry)
        try:
            actual_lanes = guardian.parse_dry_run(dry.get("stdout", ""))
        except ValueError as exc:
            return _blocked(str(exc), dry_run=dry)
        actual = [(m.group(1), m.group(2).split("→"))
                  for line in dry.get("stdout", "").splitlines()
                  if (m := guardian._DRY_LANE.fullmatch(line))]
        expected = [(lane, [entries[task_id]["opener_id"] for task_id in ids
                            if entries[task_id]["lane"] == lane]) for lane in expected_lanes]
        if actual_lanes != expected_lanes or actual != expected:
            return _blocked("watch-piece lane/opener DryRun mismatch",
                            expected=expected, actual=actual)
        receipts.append({"task_ids": ids, "lanes": actual_lanes,
                         "stdout_sha256": hashlib.sha256(dry["stdout"].encode("utf8")).hexdigest()})
    return {"status": "dry_run_verified", "receipts": receipts,
            "lint_stdout_sha256": hashlib.sha256(lint.get("stdout", "").encode("utf8")).hexdigest()}


def _prepared_workspaces(manifest: dict, plan: dict) -> tuple[dict, dict]:
    workspace_map = manifest.get("workspaces", {})
    authorization_map = manifest.get("authorizations", {})
    if not isinstance(workspace_map, dict) or not isinstance(authorization_map, dict):
        raise ValueError("prepared workspaces/authorizations must be mappings")
    candidates = {row["task_id"]: row for row in manifest["candidates"]}
    live_receipts = {item["task_id"]: item for item in plan["queue_evidence"]}
    workspaces, authorizations = {}, {}
    for task_id in plan["dispatchable_ids"]:
        candidate = candidates[task_id]
        workspace = workspace_map.get(task_id)
        if not isinstance(workspace, str) or not Path(workspace).is_dir():
            raise ValueError(f"prepared workspace missing for {task_id}")
        state_file = Path(guardian.workflow_state.STATE) / "runs" / task_id / "state.json"
        if not state_file.is_file():
            raise ValueError(f"prepared task state missing for {task_id}")
        try:
            state = json.loads(state_file.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError, TypeError) as exc:
            raise ValueError(f"prepared task state invalid for {task_id}") from exc
        if (not isinstance(state, dict) or state.get("id") != task_id
                or state.get("row") != candidate["row"]
                or state.get("section") != candidate["section"]
                or state.get("action_key") != candidate["action_key"]):
            raise ValueError(f"prepared task binding mismatch for {task_id}")
        queue_ref = state.get("queue_ref")
        if not isinstance(queue_ref, dict) or not isinstance(queue_ref.get("path"), str):
            raise ValueError(f"prepared queue anchor missing for {task_id}")
        sealed_path = Path(queue_ref["path"])
        try:
            sealed_bytes = sealed_path.read_bytes()
            if hashlib.sha256(sealed_bytes).hexdigest() != queue_ref.get("sha256"):
                raise ValueError("sealed query hash mismatch")
            sealed = json.loads(json.loads(sealed_bytes.decode("utf-8-sig"))["stdout"])
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise ValueError(f"prepared queue anchor invalid for {task_id}") from exc
        live = live_receipts[task_id]
        if (sealed.get("found") is not True or sealed.get("carrier") != "live"
                or sealed.get("done") is not False
                or str(sealed.get("row")) != str(candidate["row"])
                or sealed.get("section") != candidate["section"]
                or sealed.get("file") != live["file"] or sealed.get("line") != live["line"]
                or state.get("queue_full_sha256") != live["full_sha256"]):
            raise ValueError(f"prepared queue anchor differs from live row for {task_id}")
        resolved_workspace = Path(workspace).resolve()
        bound_workspace = state.get("workspace")
        if bound_workspace and Path(bound_workspace).resolve() != resolved_workspace:
            raise ValueError(f"prepared workspace binding mismatch for {task_id}")
        driver = guardian._load("driver", BASE / "workflow_driver.py")
        identity_error = driver._isolated_project_worktree(resolved_workspace, state)
        if identity_error:
            raise ValueError(f"prepared workspace invalid for {task_id}: {identity_error}")
        workspaces[task_id] = resolved_workspace
        authorization = authorization_map.get(task_id)
        if authorization is not None:
            if not isinstance(authorization, str) or not Path(authorization).is_file():
                raise ValueError(f"authorization path invalid for {task_id}")
            authorizations[task_id] = Path(authorization)
    return workspaces, authorizations


def start(manifest: dict, *, executor=None, lan_prober=None, run: bool = False) -> dict:
    """A business-bus wake. --run is an execution switch, never an authorization."""
    execute = (executor if executor is not None else
               guardian._load("driver", BASE / "workflow_driver.py").default_executor)
    if not isinstance(manifest, dict):
        return _blocked("guardian manifest must be an object")
    candidates = manifest.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return _blocked("guardian candidates missing")
    watch = manifest.get("watch_piece")
    if not isinstance(watch, str) or not Path(watch).is_file():
        return _blocked("watch-piece plan missing")
    try:
        rows, evidence = [], []
        seen_queue_rows = set()
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise ValueError("queue candidate must be an object")
            locator = (candidate.get("section"), candidate.get("row"))
            if locator in seen_queue_rows:
                raise ValueError("duplicate queue row in one guardian batch")
            seen_queue_rows.add(locator)
            item, receipt = _live_candidate(candidate, execute)
            rows.append(item)
            evidence.append(receipt)
        by_id = {item["task_id"]: item for item in rows}
        by_receipt = {item["task_id"]: item for item in evidence}
        lan_receipts = []
        for item in rows:
            digest = _external_lan_decision(item, by_receipt[item["task_id"]], manifest)
            lan_receipts.append({"task_id": item["task_id"], "sha256": digest})
        for item in rows:
            if item.get("action_key") == "deploy_51" and item.get("release_task_id") is not None:
                item["transfer_binding_sha256"] = _transfer_binding(
                    item, by_receipt[item["task_id"]], by_id, by_receipt, manifest, execute)
        prober = lan_prober or guardian.lane_machine.lan_status
        try:
            lan = prober()
        except Exception:
            lan = {"status": "unknown", "effective": "unknown"}
        observed = lan.get("status") if isinstance(lan, dict) else "unknown"
        observed = observed if observed in ("on", "off", "unknown") else "unknown"
        plan = guardian.plan_batch(
            manifest.get("batch_id"), rows, {"effective": observed, "status": observed},
            plan_file=Path(watch))
        plan["queue_evidence"] = evidence
        plan["lan_evidence"] = lan_receipts
        plan["execution_bindings"] = _execution_bindings(manifest)
        plan["watch_sha256"] = hashlib.sha256(Path(watch).read_bytes()).hexdigest()
        plan["candidates_sha256"] = hashlib.sha256(
            json.dumps(candidates, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")).encode("utf8")).hexdigest()
        dry = _dry_run(plan, execute)
        if dry["status"] != "dry_run_verified":
            return dry
        plan["dry_run"] = dry
        _assert_plan_sources(plan, manifest, rows, evidence, execute, prober)
        record = Path(guardian.workflow_state.STATE) / "guardian-plans" / (plan["batch_id"] + ".json")
        record.parent.mkdir(parents=True, exist_ok=True)
        try:
            _publish_plan(record, plan)
        except FileExistsError:
            prior = json.loads(record.read_text(encoding="utf-8-sig"))
            if guardian._plan_sha256(prior) != guardian._plan_sha256(plan):
                return _blocked("batch plan changed since first human wake",
                                batch_id=plan["batch_id"])
        if not run:
            return {"status": "planned", "plan": plan, "plan_record": str(record),
                    "delivery_accepted": False}
        batch_record = Path(guardian.workflow_state.STATE) / "guardian-batches" / (plan["batch_id"] + ".json")
        if batch_record.is_file():
            prior_batch = guardian._read_batch_record(batch_record, plan["batch_id"])
            if prior_batch.get("status") == "retired":
                return {"status": "retired", "batch_id": plan["batch_id"],
                        "delivery_accepted": False}
        workspaces, authorizations = _prepared_workspaces(manifest, plan)
        _authorization_seal(plan, manifest, append=True)
        _assert_plan_sources(plan, manifest, rows, evidence, execute, prober)
        if not plan["dispatchable_ids"] and not plan["transfers"]:
            return {"status": ("lan_hold_only" if plan["lan_holds"]
                               else "no_dispatchable_candidates"), "plan": plan,
                    "plan_record": str(record), "delivery_accepted": False}
        def validate_transfer(transfer: dict) -> bool:
            try:
                _assert_plan_sources(plan, manifest, rows, evidence, execute, prober)
                _authorization_seal(plan, manifest, append=False)
                _claim_execution(plan)
                source_id = transfer["release_task_id"]
                deploy_id = transfer["task_id"]
                source = by_id.get(source_id)
                deploy = by_id[deploy_id]
                if (_transfer_binding(deploy, by_receipt[deploy_id], by_id,
                                      by_receipt, manifest, execute) != transfer["binding_sha256"]):
                    return False
                for item in (deploy,) if source is None else (source, deploy):
                    if (_external_lan_decision(item, by_receipt[item["task_id"]], manifest)
                            != next(x["sha256"] for x in lan_receipts if x["task_id"] == item["task_id"])):
                        return False
                    _, current = _live_candidate(item, execute)
                    if current != by_receipt[item["task_id"]]:
                        return False
                if source is None:
                    return deploy.get("release_reference") == transfer.get("release_reference")
                source_state = guardian.workflow_state.load_state(source_id)
                return source_state.get("queue_full_sha256") == by_receipt[source_id]["full_sha256"]
            except (OSError, ValueError, TypeError, KeyError):
                return False
        _claim_execution(plan)
        def validate_stage(_task_id: str) -> bool:
            _assert_plan_sources(plan, manifest, rows, evidence, execute, prober)
            _authorization_seal(plan, manifest, append=False)
            _claim_execution(plan)
            return True
        result = guardian.dispatch_batch(plan, True, execute, workspaces=workspaces,
                                         authorizations=authorizations,
                                         transfer_validator=validate_transfer,
                                         stage_validator=validate_stage)
        _release_completed_workspaces(plan, result)
        return {**result, "plan_record": str(record)}
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return _blocked(str(exc))



def retire_batch(batch_id: str, evidence_path: Path | None) -> dict:
    """Human-reviewed abandonment; never release a running or completed queue row."""
    if evidence_path is None:
        return _blocked("external batch retirement evidence required")
    try:
        record_path = guardian._batch_record_path(batch_id)
        plan_path = Path(guardian.workflow_state.STATE) / "guardian-plans" / (batch_id + ".json")
        plan = json.loads(plan_path.read_text(encoding="utf-8-sig"))
        path = Path(evidence_path).resolve()
        workspaces = [Path(p).resolve() for p in
                      plan["execution_bindings"]["workspaces"].values()]
        if path.is_relative_to(ROOT.resolve()) or any(
                path.is_relative_to(workspace) for workspace in workspaces):
            raise ValueError("retirement evidence must be outside repository and model workspaces")
        raw = path.read_bytes()
        proof = json.loads(raw.decode("utf-8-sig"))
        if (not isinstance(proof, dict) or proof.get("batch_id") != batch_id
                or proof.get("plan_sha256") != guardian._plan_sha256(plan)
                or proof.get("decision") != "retire_stalled_batch"
                or not isinstance(proof.get("text"), str) or not proof["text"].strip()):
            raise ValueError("retirement evidence does not bind this batch and plan")
        settlements = proof.get("settle_not_transferred", {})
        if not isinstance(settlements, dict):
            raise ValueError("transfer settlement evidence must be a mapping")
        lock_path = record_path.with_suffix(".lock")
        with lock_path.open("x", encoding="utf8") as lock:
            json.dump({"batch_id": batch_id, "pid": os.getpid(), "purpose": "retire"}, lock)
        try:
            # The batch record may change while the human evidence is read.
            # Read it only after owning the same exclusive lock as run_foreground.
            record = guardian._read_batch_record(record_path, batch_id)
            if record.get("plan_sha256") != guardian._plan_sha256(plan):
                raise ValueError("batch record and reviewed plan differ")
            if record.get("status") == "retired":
                retirement = record.get("retirement", {})
                if retirement.get("evidence_sha256") != hashlib.sha256(raw).hexdigest():
                    raise ValueError("retired batch evidence differs from original decision")
            if record.get("status") == "running":
                raise ValueError("running batch cannot be retired")
            tasks = record["tasks"]
            completed = set()
            release = guardian._load("release", BASE / "workflow_release.py")
            for task_id, task in tasks.items():
                if task.get("status") == "running":
                    raise ValueError(f"task {task_id} still running")
                folder = Path(guardian.workflow_state.STATE) / "runs" / task_id
                if (folder / "running.lock").exists():
                    raise ValueError(f"task {task_id} attempt unresolved")
                current = guardian.workflow_state.load_state(task_id)
                if current.get("phase_status") == "running":
                    raise ValueError(f"task {task_id} phase unresolved")
                verified, _reason = release._verified(task_id)
                if (task.get("status") == "release_ready" or verified is not None
                        or current.get("phase") == "review"
                        and current.get("review_evidence")):
                    completed.add(task_id)
            transfers = record.get("transfers", [])
            attempts = record.get("transfer_attempts")
            if attempts is not None and not isinstance(attempts, dict):
                raise ValueError("transfer attempt ledger invalid")
            legacy = attempts is None
            if legacy and transfers and record.get("status") != "claimed":
                lane_path = guardian.lane_machine._state_path()
                if not lane_path.is_file() or not lane_path.read_text(encoding="utf8").strip():
                    raise ValueError("authoritative lane transfer state unavailable")
            lane_snapshot = guardian.lane_machine._read_state() if legacy and transfers else {"lanes": {}}
            if (not isinstance(lane_snapshot, dict)
                    or not isinstance(lane_snapshot.get("lanes", {}), dict)):
                raise ValueError("authoritative lane transfer state invalid")
            known_transfers = {item["task_id"] for item in transfers}
            if set(settlements) - known_transfers:
                raise ValueError("settlement references an unknown transfer")
            settled = []
            lane_state_path = guardian.lane_machine._state_path()
            for transfer in transfers:
                task_id = transfer["task_id"]
                receipt = record.get("transfer_receipts", {}).get(
                    task_id, {}).get("status") == "transferred"
                if not legacy:
                    attempt = attempts.get(task_id)
                    if attempt is not None and (not isinstance(attempt, dict)
                            or attempt.get("status") not in ("calling", "transferred")):
                        raise ValueError("transfer attempt ledger entry invalid")
                    settlement = settlements.get(task_id)
                    if settlement is not None:
                        if (receipt or not isinstance(attempt, dict)
                                or attempt.get("status") != "calling"
                                or not isinstance(settlement, dict)
                                or settlement.get("decision") != "not_transferred"
                                or settlement.get("task_id") != task_id
                                or settlement.get("lane") != transfer["lane"]
                                or settlement.get("item") != transfer["item"]
                                or settlement.get("attempt_at") != attempt.get("at")
                                or not isinstance(settlement.get("text"), str)
                                or not settlement["text"].strip()
                                or not lane_state_path.is_file()):
                            raise ValueError("item-specific no-transfer settlement invalid")
                        lane_raw = lane_state_path.read_bytes()
                        if (not lane_raw.strip() or
                                hashlib.sha256(lane_raw).hexdigest() != settlement.get("lane_state_sha256")):
                            raise ValueError("authoritative lane state differs from settlement")
                        lane_current = json.loads(lane_raw.decode("utf-8-sig"))
                        if (not isinstance(lane_current, dict)
                                or not isinstance(lane_current.get("lanes", {}), dict)):
                            raise ValueError("settled lane state invalid")
                        lane_record = lane_current.get("lanes", {}).get(transfer["lane"], {})
                        if not isinstance(lane_record, dict):
                            raise ValueError("settled lane state invalid")
                        history = lane_record.get("transfers", [])
                        if not isinstance(history, list) or any(
                                not isinstance(item, dict) for item in history):
                            raise ValueError("settled lane transfer history invalid")
                        note = transfer["release_task_id"] + ":" + transfer["item"]
                        if any(item.get("batch") == batch_id
                               and item.get("action_key") == "deploy_51"
                               and item.get("note") == note for item in history):
                            raise ValueError("authoritative transfer contradicts settlement")
                        settled.append(task_id)
                    elif attempt is not None or receipt:
                        # A calling attempt may have committed the authoritative
                        # transfer before a crash. Retain the row if uncertain.
                        completed.add(task_id)
                    continue
                lane_state = lane_snapshot.get("lanes", {}).get(transfer["lane"])
                if lane_state is None and record.get("status") == "claimed":
                    lane_state = {}
                if not isinstance(lane_state, dict):
                    raise ValueError("authoritative lane transfer history invalid")
                history = lane_state.get("transfers", [])
                if not isinstance(history, list) or any(
                        not isinstance(item, dict) for item in history):
                    raise ValueError("authoritative lane transfer history invalid")
                expected_note = transfer["release_task_id"] + ":" + transfer["item"]
                authoritative = any(
                    item.get("batch") == batch_id
                    and item.get("action_key") == "deploy_51"
                    and item.get("note") == expected_note
                    for item in history)
                if authoritative or receipt:
                    completed.add(task_id)
            folder = Path(guardian.workflow_state.STATE)
            registry_path = folder / "guardian-claims.json"
            with guardian._recovery_mutex(folder / "guardian-claims.mutex"):
                registry = json.loads(registry_path.read_text(encoding="utf-8-sig"))
                claims = registry["claims"]
                released, retained = [], []
                for item in plan["queue_evidence"]:
                    key = f"row:{item['section']}:{item['row']}"
                    if claims.get(key) == {"batch_id": batch_id, "task_id": item["task_id"]}:
                        if item["task_id"] in completed:
                            retained.append(key)
                        else:
                            claims.pop(key)
                            released.append(key)
                for task_id, workspace in plan["execution_bindings"]["workspaces"].items():
                    key = "workspace:" + str(Path(workspace).resolve()).casefold()
                    if claims.get(key) == {"batch_id": batch_id, "task_id": task_id}:
                        claims.pop(key)
                        released.append(key)
                for lane in dict.fromkeys([*plan["lane_ids"],
                                           *(item["lane"] for item in plan["transfers"])]):
                    key = "lane:" + lane.casefold()
                    if claims.get(key) == {"batch_id": batch_id}:
                        claims.pop(key)
                        released.append(key)
                if settled:
                    current_lane_sha = hashlib.sha256(lane_state_path.read_bytes()).hexdigest()
                    if any(current_lane_sha != settlements[task_id]["lane_state_sha256"]
                           for task_id in settled):
                        raise ValueError("authoritative lane state changed during settlement")
                record["status"] = "retired"
                record["retirement"] = {
                    "evidence_path": str(path), "evidence_sha256": hashlib.sha256(raw).hexdigest(),
                    "settled_not_transferred": sorted(set(settled + record.get("retirement", {}).get("settled_not_transferred", []))),
                    "released_claims": sorted(set(released + record.get("retirement", {}).get("released_claims", []))),
                    "retained_completed_rows": sorted(set(retained + record.get("retirement", {}).get("retained_completed_rows", [])))}
                guardian._save_batch_record(record_path, record)
                guardian.workflow_state._write_json(registry_path, registry)
            return {"status": "retired", "batch_id": batch_id,
                    "retirement": record["retirement"], "delivery_accepted": False}
        finally:
            lock_path.unlink(missing_ok=True)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return _blocked("batch retirement blocked: " + str(exc))

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    start_cmd = sub.add_parser("start")
    start_cmd.add_argument("--manifest", required=True, type=Path)
    start_cmd.add_argument("--run", action="store_true")
    observe = sub.add_parser("observe")
    observe.add_argument("--batch", required=True)
    recover = sub.add_parser("recover")
    recover.add_argument("--batch", required=True)
    retire = sub.add_parser("retire")
    retire.add_argument("--batch", required=True)
    retire.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == "observe":
        result = guardian.observe_batch(args.batch)
    elif args.command == "recover":
        result = guardian.recover_batch(args.batch)
    elif args.command == "retire":
        result = retire_batch(args.batch, args.evidence)
    else:
        try:
            data = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            result = _blocked("manifest cannot be read: " + str(exc))
        else:
            result = start(data, run=args.run)
    print(json.dumps(result, ensure_ascii=False))
    return 1 if result.get("status") in ("blocked", "blocked_unknown") else 0


if __name__ == "__main__":
    raise SystemExit(main())
