"""Thin Codex guardian seam over existing lane state, opener runner and wait tool."""
from __future__ import annotations

import importlib.util
import errno
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
RUNNER = ROOT / "0-学习与工具" / "工具-opener批处理执行v2.ps1"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location("guardian_" + name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


lane_machine = _load("lane", ROOT / "0-学习与工具" / "工具-泳道看护状态机.py")
wait_tool = _load("wait", ROOT / "0-学习与工具" / "工具-泳道看护等待.py")
workflow_state = _load("workflow_state", BASE / "workflow_state.py")

_DRY_LANE = re.compile(r"^\s*◆\s+(\S+)\s+：\s*(A\d+(?:→A\d+)*)（泳道内串行）\s*$")


def parse_dry_run(stdout: str) -> list[str]:
    """Only parse the runner's actual lane listing; malformed output fails closed."""
    lanes = []
    for line in stdout.splitlines():
        if "◆" not in line:
            continue
        match = _DRY_LANE.fullmatch(line)
        if not match:
            raise ValueError("unparseable DryRun lane line")
        lanes.append(match.group(1))
    if not lanes or len(lanes) != len(set(lanes)):
        raise ValueError("DryRun lane list missing or duplicated")
    return lanes


def _validate_row(row: dict) -> None:
    if not isinstance(row, dict):
        raise ValueError("queue row must be a mapping from the dedicated query")
    if (not isinstance(row.get("task_id"), str) or not row["task_id"]
            or not re.fullmatch(r"A\d+", str(row.get("opener_id", "")))
            or not re.fullmatch(r"[^\s]+", str(row.get("lane", "")))
            or not isinstance(row.get("touches"), list) or not row["touches"]
            or not all(isinstance(x, str) and x.strip() for x in row["touches"])):
        raise ValueError("task/lane/touch evidence incomplete")


def _touch_overlap(left: str, right: str) -> bool:
    a = left.replace("\\", "/").strip("/").casefold()
    b = right.replace("\\", "/").strip("/").casefold()
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def _held_item(row: dict, reason: str) -> dict:
    if (not isinstance(row.get("row"), int) or row["row"] < 1
            or row.get("section") not in ("一", "四")
            or not isinstance(row.get("next_action"), str)
            or not row["next_action"].strip()):
        raise ValueError("LAN hold/transfer requires live queue locator and next action")
    return {"task_id": row["task_id"], "row": row["row"],
            "section": row["section"], "next_action": row["next_action"].strip(),
            "reason": reason}


PLAN_FINGERPRINT_VERSION = 2

def _plan_sha256(plan: dict) -> str:
    version = plan.get("plan_fingerprint_version", 1)
    if type(version) is not int or version not in (1, PLAN_FINGERPRINT_VERSION):
        raise ValueError("unknown plan fingerprint version")
    fields = ("batch_id", "mode", "file", "lan", "lan_observed", "dispatchable_ids",
              "excluded", "lan_holds", "transfers", "waves", "lane_ids", "opener_ids",
              "entries", "queue_evidence", "lan_evidence", "execution_bindings",
              "watch_sha256", "candidates_sha256", "max_items", "max_parallel",
              "stagger_seconds")
    payload = {key: plan.get(key) for key in fields}
    dry_run = plan.get("dry_run")
    if version == 1:
        # Exact legacy payload: no version key and full DryRun evidence included.
        payload["dry_run"] = dry_run
    else:
        payload["plan_fingerprint_version"] = version
        normalized = _semantic_dry_run(plan, dry_run)
        payload["dry_run"] = normalized
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf8")).hexdigest()


def _semantic_dry_run(plan: dict, dry_run):
    """Drop only volatile stdout hashes after verifying exact planned semantics."""
    if not isinstance(dry_run, dict) or dry_run.get("status") != "dry_run_verified":
        return dry_run
    receipts = dry_run.get("receipts")
    entries = {item.get("task_id"): item for item in plan.get("entries", [])
               if isinstance(item, dict)}
    expected = []
    try:
        for wave in plan.get("waves", []):
            task_ids = wave["task_ids"]
            lanes = list(dict.fromkeys(entries[task_id]["lane"] for task_id in task_ids))
            expected.append({"task_ids": task_ids, "lanes": lanes})
    except (KeyError, TypeError):
        return dry_run
    if not isinstance(receipts, list) or len(receipts) != len(expected):
        return dry_run
    for receipt, semantic in zip(receipts, expected):
        if (not isinstance(receipt, dict)
                or receipt.get("task_ids") != semantic["task_ids"]
                or receipt.get("lanes") != semantic["lanes"]
                or not re.fullmatch(r"[0-9a-f]{64}", str(receipt.get("stdout_sha256", "")))):
            return dry_run
    if not re.fullmatch(r"[0-9a-f]{64}", str(dry_run.get("lint_stdout_sha256", ""))):
        return dry_run
    normalized = copy.deepcopy(dry_run)
    normalized.pop("lint_stdout_sha256")
    for receipt in normalized["receipts"]:
        receipt.pop("stdout_sha256")
    return normalized


def plan_batch(batch_id: str, queue_rows: list[dict], lan: dict, *,
               mode: str = "guardian", plan_file: Path | None = None,
               max_items: int = 10, max_parallel: int = 4,
               stagger_seconds: int = 90) -> dict:
    if not batch_id or "/" in batch_id or "\\" in batch_id:
        raise ValueError("invalid batch ID")
    if mode not in ("guardian", "headless"):
        raise ValueError("unknown guardian mode")
    if max_items < 1 or max_items > 10 or max_parallel < 1 or max_parallel > 4 or stagger_seconds < 90:
        raise ValueError("guardian capacity exceeds approved source limits")
    if not isinstance(lan, dict) or lan.get("effective") not in ("on", "off", "unknown"):
        raise ValueError("LAN result unavailable")
    selected, excluded, lan_holds, transfers = [], {}, [], []
    held_ids = set()
    seen_tasks, seen_openers = set(), set()
    for row in queue_rows:
        _validate_row(row)
        task_id = row["task_id"]
        if task_id in seen_tasks or row["opener_id"] in seen_openers:
            raise ValueError("duplicate task or opener ID")
        seen_tasks.add(task_id)
        seen_openers.add(row["opener_id"])
        tier = lane_machine.classify(row.get("action_key", "")).tier
        if tier == lane_machine.TIER_TRANSFER:
            if len(selected) + len(transfers) >= max_items:
                excluded[task_id] = "batch capacity"
                lan_holds.append(_held_item(row, "batch capacity; next human batch"))
                held_ids.add(task_id)
                continue
            release_task_id = row.get("release_task_id")
            if row.get("action_key") == "deploy_51" and release_task_id is None:
                lan_holds.append(_held_item(row, "deploy_51 requires release binding and LAN closeout"))
                held_ids.add(task_id)
                excluded[task_id] = "transfer binding required"
                continue
            if not isinstance(release_task_id, str) or not release_task_id.strip():
                raise ValueError("transfer release_task_id invalid")
            binding_digest = row.get("transfer_binding_sha256")
            if not isinstance(binding_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", binding_digest):
                raise ValueError("transfer binding evidence missing")
            transfer = _held_item(row, "transfer")
            transfer.update(release_task_id=release_task_id, lane=row["lane"],
                            item=f"§{row['section']} #{row['row']} {row['next_action'].strip()}",
                            binding_sha256=binding_digest)
            reference = row.get("release_reference")
            if reference is not None:
                if (not isinstance(reference, dict)
                        or not isinstance(reference.get("batch_id"), str)
                        or not reference["batch_id"]
                        or not isinstance(reference.get("source_wave"), int)
                        or reference["source_wave"] < 1
                        or not re.fullmatch(r"[0-9a-f]{64}", str(reference.get("source_plan_sha256", "")))
                        or not re.fullmatch(r"[0-9a-f]{40}", str(reference.get("source_head", "")))
                        or not isinstance(reference.get("source_row"), int)
                        or reference["source_row"] < 1
                        or reference.get("source_section") not in ("一", "四")
                        or not re.fullmatch(r"[0-9a-f]{64}", str(reference.get("source_queue_full_sha256", "")))):
                    raise ValueError("completed source release reference invalid")
                transfer["release_reference"] = reference
            transfers.append(transfer)
            excluded[task_id] = "transfer"
            if row.get("action_key") == "deploy_51" and lan["effective"] != "on":
                lan_holds.append(_held_item(row, "deploy_51 awaits LAN closeout"))
                held_ids.add(task_id)
            continue
        if row.get("lan_required") and lan["effective"] != "on":
            lan_holds.append(_held_item(row, "LAN unavailable"))
            held_ids.add(task_id)
            excluded[task_id] = "LAN unavailable"
            continue
        if tier != lane_machine.TIER_GREEN:
            excluded[task_id] = ("human_decision" if tier == lane_machine.TIER_YELLOW
                                 else "prohibited")
            continue
        if len(selected) + len(transfers) >= max_items:
            excluded[task_id] = "batch capacity"
            continue
        selected.append(row)
    selected.sort(key=lambda r: int(r["opener_id"][1:]))
    runnable = list(selected)
    while True:
        selected_ids = {r["task_id"] for r in runnable}
        missing = []
        for row in runnable:
            deps = row.get("depends_on", [])
            if not isinstance(deps, list) or any(not isinstance(d, str) for d in deps):
                raise ValueError("invalid dependencies")
            if any(d not in selected_ids for d in deps):
                missing.append(row)
        if not missing:
            break
        for row in missing:
            excluded[row["task_id"]] = "dependency unavailable"
            if any(dep in held_ids for dep in row.get("depends_on", [])):
                lan_holds.append(_held_item(row, "LAN dependency unavailable"))
                held_ids.add(row["task_id"])
            runnable.remove(row)
    normal = [r for r in runnable if r.get("kind") != "lock_tools"]
    locks = [r for r in runnable if r.get("kind") == "lock_tools"]
    waves: list[dict] = []
    placed: set[str] = set()
    pending = list(normal)
    while pending:
        wave_rows, touched = [], set()
        for row in list(pending):
            if any(dep not in placed for dep in row.get("depends_on", [])):
                continue
            current_touches = set(row["touches"])
            if any(_touch_overlap(a, b) for a in touched for b in current_touches):
                continue
            wave_rows.append(row)
            touched.update(current_touches)
            pending.remove(row)
            if len(wave_rows) >= max_parallel:
                break
        if not wave_rows:
            raise ValueError("dependency cycle or lock-tool dependency in ordinary wave")
        waves.append({"kind": "ordinary", "task_ids": [r["task_id"] for r in wave_rows]})
        placed.update(r["task_id"] for r in wave_rows)
    for row in locks:
        if any(d not in placed for d in row.get("depends_on", [])):
            raise ValueError("lock-tool dependency cycle")
        waves.append({"kind": "lock_tools", "task_ids": [row["task_id"]]})
        placed.add(row["task_id"])
    ids = [r["task_id"] for r in runnable]
    for transfer in transfers:
        release_task_id = transfer.get("release_task_id")
        if release_task_id is not None and release_task_id not in ids:
            if not transfer.get("release_reference"):
                raise ValueError("transfer release task is not dispatchable in this batch")
    lanes = list(dict.fromkeys(r["lane"] for r in runnable))
    return {"plan_fingerprint_version": (PLAN_FINGERPRINT_VERSION if mode == "guardian" else 1),
            "batch_id": batch_id, "mode": mode, "file": str(Path(plan_file).resolve()) if plan_file else None,
            "lan": lan["effective"], "lan_observed": lan.get("status", lan["effective"]),
            "dispatchable_ids": ids, "excluded": excluded,
            "lan_holds": lan_holds, "transfers": transfers,
            "waves": waves, "lane_ids": lanes, "opener_ids": [r["opener_id"] for r in runnable], "entries": [{"task_id": r["task_id"], "lane": r["lane"], "opener_id": r["opener_id"], "depends_on": r.get("depends_on", [])} for r in runnable],
            "max_items": max_items, "max_parallel": max_parallel,
            "stagger_seconds": stagger_seconds, "needs_manual_wake": mode == "guardian"}


def _advance_task(task_id, workspace, authorization, executor, model_runner):
    driver = _load("driver", BASE / "workflow_driver.py")
    kwargs = {"model_runner": model_runner} if model_runner else {}
    return driver.advance(task_id, workspace, authorization, executor,
                          model="gpt-6-luna", **kwargs)


def _batch_record_path(batch_id: str) -> Path:
    if (not isinstance(batch_id, str) or not batch_id or batch_id in (".", "..")
            or "/" in batch_id or "\\" in batch_id or "\x00" in batch_id):
        raise ValueError("invalid batch ID")
    return Path(workflow_state.STATE) / "guardian-batches" / (batch_id + ".json")


def initial_batch_record(plan: dict) -> dict:
    """Persistable pre-dispatch owner record; no model attempt has started."""
    task_waves = {}
    for index, wave in enumerate(plan.get("waves", []), start=1):
        for task_id in wave.get("task_ids", []):
            task_waves[task_id] = index
    entries = {entry["task_id"]: entry for entry in plan.get("entries", [])}
    return {
        "schema_version": 1, "batch_id": plan["batch_id"], "mode": plan.get("mode"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "claimed", "delivery_accepted": False,
        "plan_sha256": _plan_sha256(plan), "lan_holds": plan.get("lan_holds", []),
        "transfers": plan.get("transfers", []), "transfer_receipts": {},
        "transfer_failures": {}, "transfer_attempts": {}, "notifications_suppressed": True,
        "tasks": {
            task_id: {"lane": entry["lane"], "opener_id": entry["opener_id"],
                      "depends_on": entry.get("depends_on", []),
                      "wave": task_waves.get(task_id), "status": "pending"}
            for task_id, entry in entries.items()
        },
    }


def _save_batch_record(path: Path, record: dict) -> None:
    record["updated_at"] = datetime.now(timezone.utc).isoformat()
    workflow_state._write_json(path, record)


def _lane_states_for_batch(batch_id: str, tasks: dict) -> dict:
    try:
        lanes = lane_machine._read_state().get("lanes", {})
    except (OSError, ValueError, TypeError):
        return {}
    names = {entry.get("lane") for entry in tasks.values() if entry.get("lane")}
    return {name: lanes[name] for name in names
            if isinstance(lanes.get(name), dict) and lanes[name].get("batch") == batch_id}


def _batch_result(record: dict, reason: str | None = None) -> dict:
    return {
        "status": ("release_ready" if record.get("status") == "release_ready"
                   else "needs_manual_wake"),
        "reason": reason or "foreground review or item authorization",
        "batch_id": record.get("batch_id"),
        "tasks": record.get("tasks", {}),
        "lan_holds": record.get("lan_holds", []),
        "transfers": record.get("transfers", []),
        "transfer_receipts": record.get("transfer_receipts", {}),
        "transfer_failures": record.get("transfer_failures", {}),
        "batch_phase": record.get("status"),
        "lane_states": _lane_states_for_batch(record.get("batch_id", ""), record.get("tasks", {})),
        "delivery_accepted": False,
    }


def _read_batch_record(path: Path, batch_id: str) -> dict:
    record = json.loads(path.read_text(encoding="utf-8-sig"))
    if (not isinstance(record, dict) or record.get("batch_id") != batch_id
            or not isinstance(record.get("tasks"), dict)
            or record.get("delivery_accepted") is not False):
        raise ValueError("guardian batch record invalid")
    return record


def _can_resume_record(record: dict) -> bool:
    if record.get("status") == "retired":
        return False
    if record.get("status") in ("claimed", "recovered"):
        return True
    if record.get("status") == "blocked" and record.get("transfer_failures"):
        return True
    lanes = _lane_states_for_batch(record["batch_id"], record["tasks"])
    return any(task.get("status") == "paused"
               and isinstance(lanes.get(task.get("lane")), dict)
               and lanes[task["lane"]].get("status") == "resumed"
               for task in record["tasks"].values())


_HEARTBEAT_INTERVAL_SECONDS = 300


@contextmanager
def _heartbeat_while(batch_id: str, task_id: str, lane: str):
    stop = threading.Event()
    errors = []
    def tick():
        while not stop.wait(_HEARTBEAT_INTERVAL_SECONDS):
            try:
                lane_machine.write_heartbeat(
                    lane=lane, text=f"batch={batch_id} task={task_id} still running; ETA unknown",
                    done=False)
            except (OSError, ValueError, TypeError) as exc:
                errors.append(type(exc).__name__ + ": " + str(exc))
                return
    worker = threading.Thread(target=tick, name=f"guardian-heartbeat-{task_id}", daemon=True)
    worker.start()
    try:
        yield errors
    finally:
        stop.set()
        worker.join(timeout=1)


def _transfer_deploy(task_id: str, batch: str, lane: str, item: str, *, wave: int) -> dict:
    release = _load("release", BASE / "workflow_release.py")
    return release.transfer_deploy(task_id, batch, lane, item, wave=wave)



def _carry_source_verified(transfer: dict) -> bool:
    reference = transfer.get("release_reference")
    if not isinstance(reference, dict):
        return False
    release = _load("release", BASE / "workflow_release.py")
    current, _reason = release._verified(transfer["release_task_id"])
    return isinstance(current, dict) and current.get("implementation_head") == reference.get("source_head")

def _record_ready_transfers(record: dict, record_path: Path, validator) -> None:
    receipts = record.setdefault("transfer_receipts", {})
    failures = record.setdefault("transfer_failures", {})
    attempts = record.get("transfer_attempts")
    legacy_without_ledger = attempts is None
    if legacy_without_ledger:
        attempts = {}
    if not isinstance(attempts, dict):
        raise ValueError("transfer attempt ledger invalid")
    for transfer in record.get("transfers", []):
        transfer_id = transfer["task_id"]
        if transfer_id in receipts:
            continue
        source = record["tasks"].get(transfer["release_task_id"], {})
        reference = transfer.get("release_reference")
        if source.get("status") != "release_ready" and not reference:
            continue
        try:
            if reference and not _carry_source_verified(transfer):
                result = {"status": "blocked", "reason": "completed source release proof changed"}
            elif validator is None or validator(transfer) is not True:
                result = {"status": "blocked", "reason": "live queue/transfer binding changed"}
            else:
                previous = attempts.get(transfer_id)
                if previous is not None or legacy_without_ledger:
                    # Prior calls and legacy records without a per-item ledger
                    # may have written the lane state before a batch receipt.
                    lane_state = lane_machine._read_state().get("lanes", {}).get(transfer["lane"])
                    if not isinstance(lane_state, dict):
                        raise ValueError("prior transfer outcome unknown; human review required")
                    history = lane_state.get("transfers", [])
                    if not isinstance(history, list) or any(
                            not isinstance(t, dict) for t in history):
                        raise ValueError("prior transfer history invalid")
                    note = transfer["release_task_id"] + ":" + transfer["item"]
                    found = any(t.get("batch") == record["batch_id"]
                                and t.get("action_key") == "deploy_51"
                                and t.get("note") == note for t in history)
                    if not found:
                        raise ValueError("prior transfer outcome unknown; human review required")
                record["transfer_attempts"] = attempts
                attempts[transfer_id] = {
                    "status": "calling", "at": datetime.now(timezone.utc).isoformat()}
                _save_batch_record(record_path, record)
                result = _transfer_deploy(
                    transfer["release_task_id"], record["batch_id"], transfer["lane"],
                    transfer["item"], wave=(source.get("wave") or reference["source_wave"]))
        except (OSError, ValueError, TypeError, KeyError) as exc:
            result = {"status": "blocked", "reason": type(exc).__name__ + ": " + str(exc)}
        if not isinstance(result, dict):
            result = {"status": "blocked", "reason": "transfer returned no result"}
        receipt = {"status": result.get("status", "blocked"), "item": transfer["item"],
                   "source_task_id": transfer["release_task_id"],
                   "production_executed": False}
        for key in ("reason", "pointer", "already_recorded"):
            if key in result:
                receipt[key] = result[key]
        if receipt["status"] == "transferred":
            receipts[transfer_id] = receipt
            attempts[transfer_id] = {
                "status": "transferred", "at": datetime.now(timezone.utc).isoformat()}
            failures.pop(transfer_id, None)
        else:
            failures[transfer_id] = receipt
        _save_batch_record(record_path, record)


def _process_alive(pid: int) -> bool | None:
    """True means still active; None means process state cannot be established."""
    if not isinstance(pid, int) or isinstance(pid, bool) or pid < 1:
        return None
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.GetExitCodeProcess.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return False if ctypes.get_last_error() in (87, 1168) else None
        try:
            code = wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                return None
            return code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return None
    return True


@contextmanager
def _recovery_mutex(path: Path, *, timeout_seconds: float = 5.0):
    """OS byte-range lock; wait briefly for normal contention, then fail closed."""
    if timeout_seconds < 0:
        raise ValueError("mutex timeout must be nonnegative")
    with path.open("a+b") as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"\x00")
            stream.flush()
        deadline = time.monotonic() + timeout_seconds
        while True:
            stream.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if (exc.errno not in (errno.EACCES, errno.EAGAIN)
                        and getattr(exc, "winerror", None) not in (32, 33)):
                    raise
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"mutex busy: {path}") from exc
                time.sleep(min(0.05, remaining))
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def recover_batch(batch_id: str) -> dict:
    """Own batch reconciliation exclusively; never remove another owner's lock."""
    try:
        path = _batch_record_path(batch_id)
        mutex = path.with_suffix(".recovery.lock")
        with _recovery_mutex(mutex):
            return _recover_batch_locked(batch_id)
    except (OSError, ValueError) as exc:
        return {"status": "blocked_unknown", "reason": "recovery mutex unavailable: " + str(exc),
                "delivery_accepted": False}


def _recover_batch_locked(batch_id: str) -> dict:
    """Reconcile a dead foreground owner only after task-level attempts are settled."""
    try:
        record_path = _batch_record_path(batch_id)
        lock_path = record_path.with_suffix(".lock")
        lock = json.loads(lock_path.read_text(encoding="utf-8-sig"))
        record = _read_batch_record(record_path, batch_id)
    except (OSError, ValueError, TypeError) as exc:
        return {"status": "blocked_unknown", "reason": "batch recovery evidence unavailable: " + str(exc),
                "delivery_accepted": False}
    if not isinstance(lock, dict) or lock.get("batch_id") != batch_id:
        return {"status": "blocked_unknown", "reason": "batch lock identity mismatch",
                "delivery_accepted": False}
    alive = _process_alive(lock.get("pid"))
    if alive is not False:
        return {"status": "blocked_unknown", "reason": "batch owner active or cannot be proven exited",
                "delivery_accepted": False}
    if lock.get("purpose") == "retire":
        # Never reinterpret an interrupted retirement as a resumable build.
        try:
            lock_path.unlink()
        except OSError as exc:
            return {"status": "blocked_unknown", "reason": "retirement lock removal failed: " + str(exc),
                    "delivery_accepted": False}
        return {"status": ("retired" if record.get("status") == "retired" else "retire_retry_ready"),
                "batch_id": batch_id, "delivery_accepted": False}
    if lock.get("purpose") not in (None, "run"):
        return {"status": "blocked_unknown", "reason": "unknown batch lock purpose",
                "delivery_accepted": False}
    running = [(task_id, task) for task_id, task in record["tasks"].items()
               if task.get("status") == "running"]
    for task_id, task in running:
        folder = Path(workflow_state.STATE) / "runs" / task_id
        if (folder / "running.lock").exists():
            return {"status": "blocked_unknown",
                    "reason": f"task {task_id} attempt still unresolved; use workflow recover with terminal evidence",
                    "delivery_accepted": False}
        try:
            current = workflow_state.load_state(task_id)
        except (OSError, ValueError, TypeError):
            return {"status": "blocked_unknown", "reason": f"task {task_id} state unavailable",
                    "delivery_accepted": False}
        if current.get("phase_status") == "running":
            return {"status": "blocked_unknown", "reason": f"task {task_id} terminal state unavailable",
                    "delivery_accepted": False}
        if not task.get("lane") or not isinstance(task.get("wave"), int):
            return {"status": "blocked_unknown", "reason": f"task {task_id} lane evidence unavailable",
                    "delivery_accepted": False}
    for task_id, task in running:
        try:
            lane_machine.pause_lane(
                batch=batch_id, wave=task["wave"], lane=task["lane"],
                action_key="codex_workflow_human_gate",
                waiting_for=f"Task {task_id}: foreground owner exited; task attempt settled. Review before resume.",
                options=[], notify_fn=lambda _message: None)
        except (OSError, ValueError, TypeError) as exc:
            return {"status": "blocked_unknown", "reason": "recovery lane pause failed: " + str(exc),
                    "delivery_accepted": False}
        task["status"] = "paused"
        task["reason"] = "foreground owner exited; explicit lane resume required"
    record["status"] = "recovered"
    record["recovery"] = {"pid": lock["pid"], "at": datetime.now(timezone.utc).isoformat(),
                          "task_ids": [task_id for task_id, _ in running]}
    _save_batch_record(record_path, record)
    try:
        lock_path.unlink()
    except OSError as exc:
        return {"status": "blocked_unknown", "reason": "batch lock removal failed: " + str(exc),
                "delivery_accepted": False}
    return _batch_result(record, "batch owner exited; reconciled tasks require explicit review")


_stagger_sleep = time.sleep


def run_foreground(plan: dict, workspaces: dict, executor, *,
                   authorizations: dict | None = None, model_runner=None,
                   transfer_validator=None, stage_validator=None) -> dict:
    """Persist one foreground batch and use lane state for pauses and explicit resume."""
    batch_id = plan.get("batch_id")
    try:
        record_path = _batch_record_path(batch_id)
    except ValueError as exc:
        return {"status": "blocked", "reason": str(exc), "delivery_accepted": False}
    record_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = record_path.with_suffix(".lock")
    try:
        with lock_path.open("x", encoding="utf8") as lock:
            lock.write(json.dumps({"batch_id": batch_id, "pid": os.getpid(),
                                   "started_at": datetime.now(timezone.utc).isoformat()}))
    except FileExistsError:
        if record_path.is_file():
            try:
                return _batch_result(_read_batch_record(record_path, batch_id), "batch already running; observe before retry")
            except (OSError, ValueError, TypeError):
                pass
        return {"status": "blocked", "reason": "guardian batch already running", "delivery_accepted": False}

    try:
        existing = None
        if record_path.is_file():
            try:
                existing = _read_batch_record(record_path, batch_id)
            except (OSError, ValueError, TypeError) as exc:
                return {"status": "blocked", "reason": "guardian batch record invalid: " + str(exc),
                        "delivery_accepted": False}
            if existing.get("plan_sha256") != _plan_sha256(plan):
                return {"status": "blocked", "reason": "batch plan changed since first run",
                        "batch_id": batch_id, "delivery_accepted": False}
            if not _can_resume_record(existing):
                return _batch_result(existing, "batch is persisted; explicit lane resume is required before continuing")
            record = existing
            if record.get("status") == "claimed":
                # Persist dispatch intent before any model stage or transfer side effect.
                record["status"] = "running"
                _save_batch_record(record_path, record)
        else:
            record = initial_batch_record(plan)
            record["status"] = "running"
            _save_batch_record(record_path, record)

        entries = {entry["task_id"]: entry for entry in plan.get("entries", [])}
        prior_lane_task = {}
        last_by_lane = {}
        for scheduled_wave in plan.get("waves", []):
            for scheduled_id in scheduled_wave.get("task_ids", []):
                scheduled_entry = entries.get(scheduled_id, {})
                lane = scheduled_entry.get("lane")
                prior_lane_task[scheduled_id] = last_by_lane.get(lane)
                if lane:
                    last_by_lane[lane] = scheduled_id
        authorizations = authorizations or {}
        def run_stages(task_id, entry):
            outcome, release_head = None, None
            with _heartbeat_while(batch_id, task_id, entry["lane"]) as heartbeat_errors:
                for _ in range(5):
                    try:
                        if stage_validator is not None and stage_validator(task_id) is not True:
                            outcome = {"status": "blocked", "reason": "stage source validation refused"}
                            break
                        outcome = _advance_task(task_id, Path(workspaces[task_id]),
                                                authorizations.get(task_id), executor, model_runner)
                        if stage_validator is not None and stage_validator(task_id) is not True:
                            outcome = {"status": "blocked", "reason": "stage source changed during execution"}
                    except Exception as exc:
                        outcome = {"status": "blocked", "reason": type(exc).__name__ + ": " + str(exc)}
                    if not isinstance(outcome, dict):
                        outcome = {"status": "blocked", "reason": "stage advance returned no result"}
                    if outcome.get("status") == "ready" and outcome.get("next_phase") == "release_ready":
                        release_head = outcome.get("implementation_head")
                        outcome = {"status": "release_ready"}
                        break
                    if outcome.get("status") == "ready" and outcome.get("next_phase") in (
                            "proposal", "implement", "test", "review"):
                        continue
                    break
                else:
                    outcome = {"status": "blocked", "reason": "stage advance bound reached"}
            if heartbeat_errors:
                outcome = {"status": "blocked", "reason": "periodic heartbeat failed: " + heartbeat_errors[0]}
            return outcome, release_head

        for wave_index, wave in enumerate(plan.get("waves", []), start=1):
            lane_queues = {}
            for task_id in wave.get("task_ids", []):
                lane = entries.get(task_id, {}).get("lane")
                if not isinstance(lane, str):
                    return {"status": "blocked", "reason": "guardian batch/task plan mismatch",
                            "batch_id": batch_id, "delivery_accepted": False}
                lane_queues.setdefault(lane, []).append(task_id)
            while any(lane_queues.values()):
                round_ids = [queue.pop(0) for queue in lane_queues.values() if queue]
                jobs = []
                # No worker mutates the shared batch record. One task per lane
                # runs per round; the owner publishes results after all join.
                with ThreadPoolExecutor(max_workers=min(plan["max_parallel"], len(round_ids))) as pool:
                    for task_id in round_ids:
                        task_record = record["tasks"].get(task_id)
                        entry = entries.get(task_id)
                        if not isinstance(task_record, dict) or not isinstance(entry, dict):
                            return {"status": "blocked", "reason": "guardian batch/task plan mismatch",
                                    "batch_id": batch_id, "delivery_accepted": False}
                        if task_record.get("status") not in ("pending", "paused", "waiting_lane"):
                            continue
                        predecessor = prior_lane_task.get(task_id)
                        if predecessor:
                            previous = record["tasks"].get(predecessor, {})
                            if previous.get("status") != "release_ready":
                                waiting_status = ("waiting_lane" if previous.get("status") in
                                                  ("paused", "waiting_lane", "running", "pending") else
                                                  "blocked_dependency")
                                task_record.update(status=waiting_status,
                                    reason=f"lane serial predecessor {predecessor} is {previous.get('status', 'unknown')}")
                                _save_batch_record(record_path, record)
                                continue
                        if task_record.get("status") in ("paused", "waiting_lane"):
                            lane_state = _lane_states_for_batch(batch_id, record["tasks"]).get(entry["lane"], {})
                            if lane_state.get("status") != "resumed":
                                continue
                        deps = entry.get("depends_on", [])
                        if any(record["tasks"].get(dep, {}).get("status") != "release_ready" for dep in deps):
                            task_record.update(status="blocked_dependency", reason="dependency has no release-ready proof")
                            _save_batch_record(record_path, record)
                            continue
                        if task_id not in workspaces:
                            task_record.update(status="blocked", reason="workspace missing")
                            _save_batch_record(record_path, record)
                            continue
                        if jobs:
                            _stagger_sleep(plan["stagger_seconds"])
                        task_record.update(status="running", workspace=str(Path(workspaces[task_id]).resolve()),
                                           started_at=datetime.now(timezone.utc).isoformat())
                        record["status"] = "running"
                        _save_batch_record(record_path, record)
                        try:
                            lane_machine.write_heartbeat(lane=entry["lane"],
                                text=f"batch={batch_id} task={task_id} status=running", done=False)
                        except (OSError, ValueError, TypeError) as exc:
                            task_record.update(status="blocked", reason="heartbeat write failed: " + str(exc))
                            _save_batch_record(record_path, record)
                            continue
                        jobs.append((task_id, entry, pool.submit(run_stages, task_id, entry)))
                    for task_id, entry, future in jobs:
                        task_record = record["tasks"][task_id]
                        try:
                            outcome, release_head = future.result()
                        except Exception as exc:
                            outcome, release_head = (
                                {"status": "blocked", "reason": type(exc).__name__ + ": " + str(exc)}, None)
                        if not isinstance(outcome, dict):
                            outcome = {"status": "blocked", "reason": "stage advance returned no result"}
                        task_record["status"] = outcome.get("status", "blocked")
                        if task_record["status"] == "release_ready" and isinstance(release_head, str):
                            task_record["implementation_head"] = release_head
                        for key in ("reason", "next_phase", "authorization_required"):
                            value = outcome.get(key)
                            if isinstance(value, str):
                                task_record[key] = value[:2000]
                        task_record["finished_at"] = datetime.now(timezone.utc).isoformat()
                        _save_batch_record(record_path, record)
                        status = task_record.get("status")
                        try:
                            lane_machine.write_heartbeat(lane=entry["lane"],
                                text=f"batch={batch_id} task={task_id} status={status}", done=False)
                        except (OSError, ValueError, TypeError):
                            pass
                        if status == "paused":
                            waiting_for = (
                                f"Task {task_id} paused: {task_record.get('reason', 'human decision required')}. "
                                "Resume only answers the lane prompt; it does not grant design, merge, deployment, "
                                "or external-send authorization required by the workflow gate.")
                            try:
                                lane_machine.pause_lane(
                                    batch=batch_id, wave=wave_index, lane=entry["lane"],
                                    action_key="codex_workflow_human_gate", waiting_for=waiting_for,
                                    options=[], notify_fn=lambda _message: None)
                            except (OSError, ValueError, TypeError) as exc:
                                task_record.update(status="blocked", reason="lane pause persistence failed: " + str(exc))
                                _save_batch_record(record_path, record)
        _record_ready_transfers(record, record_path, transfer_validator)
        task_statuses = [task.get("status") for task in record["tasks"].values()]
        transfers_ready = all(
            record.get("transfer_receipts", {}).get(t["task_id"], {}).get("status") == "transferred"
            for t in record.get("transfers", []))
        record["status"] = (
            "release_ready" if (task_statuses or record.get("transfers"))
            and all(x == "release_ready" for x in task_statuses) and transfers_ready
            else "paused" if "paused" in task_statuses
            else "blocked" if any(x in ("blocked", "blocked_dependency") for x in task_statuses)
                 or record.get("transfer_failures")
            else "waiting_for_review_or_authorization"
        )
        _save_batch_record(record_path, record)
        return _batch_result(record)
    finally:
        # Unexpected exceptions preserve the owner's PID lock for later evidence-based recovery.
        if sys.exc_info()[0] is None:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass

def dispatch_batch(plan: dict, enabled: bool, executor, *, workspaces: dict | None = None,
                   authorizations: dict | None = None, model_runner=None,
                   transfer_validator=None, stage_validator=None) -> dict:
    if plan.get("mode") != "headless":
        if not enabled:
            return {"status": "paused", "reason": "consumer disabled"}
        if workspaces is not None:
            return run_foreground(plan, workspaces, executor, authorizations=authorizations,
                                  model_runner=model_runner,
                                  transfer_validator=transfer_validator,
                                  stage_validator=stage_validator)
        return {"status": "needs_manual_wake", "reason": "foreground guardian requires task workspaces"}
    file = Path(plan["file"]) if plan.get("file") else None
    if not file or not file.is_file():
        return {"status": "blocked", "reason": "watch-piece plan missing"}
    entries = {e["task_id"]: e for e in plan.get("entries", [])}
    if not entries:
        return {"status": "paused", "reason": "no dispatchable lanes"}
    outcomes, deferred = [], []
    # A runner exit or sentinel is only model output. It cannot satisfy downstream dependencies.
    accepted: set[str] = set()
    for wave_index, wave in enumerate(plan["waves"]):
        runnable = []
        for task_id in wave["task_ids"]:
            entry = entries[task_id]
            if any(dep not in accepted for dep in entry["depends_on"]):
                deferred.append(entry["opener_id"])
            elif wave["kind"] == "lock_tools" and outcomes:
                deferred.append(entry["opener_id"])
            else:
                runnable.append(entry)
        if not runnable:
            continue
        opener_ids = [e["opener_id"] for e in runnable]
        lanes = list(dict.fromkeys(e["lane"] for e in runnable))
        base = ["pwsh", "-NoProfile", "-File", str(RUNNER), "-Plan", str(file),
                "-Only", ",".join(opener_ids), "-Yes", "-MaxParallel", str(plan["max_parallel"]),
                "-StaggerSec", str(plan["stagger_seconds"])]
        dry = executor([*base, "-DryRun"], cwd=ROOT, timeout=120)
        if dry.get("exit") != 0:
            return {"status": "blocked", "reason": "runner DryRun failed",
                    "wave": wave_index, "dry_run": dry, "outcomes": outcomes}
        try:
            parsed = parse_dry_run(dry.get("stdout", ""))
        except ValueError as exc:
            return {"status": "blocked", "reason": str(exc), "wave": wave_index,
                    "dry_run": dry, "outcomes": outcomes}
        observed_entries = [(m.group(1), m.group(2).split("→"))
                            for line in dry.get("stdout", "").splitlines()
                            if (m := _DRY_LANE.fullmatch(line))]
        expected_entries = [(lane, [e["opener_id"] for e in runnable if e["lane"] == lane])
                            for lane in lanes]
        if parsed != lanes or observed_entries != expected_entries:
            return {"status": "blocked", "reason": "lane parse mismatch", "wave": wave_index,
                    "parsed": observed_entries, "outcomes": outcomes}
        if not enabled:
            outcomes.append({"wave": wave_index, "status": "dry_run_verified", "openers": opener_ids})
            continue
        actual = executor([*base, "-ConsumerEnabled"], cwd=ROOT, timeout=7200)
        outcomes.append({"wave": wave_index, "status": "output_needs_review"
                         if actual.get("exit") == 0 else "blocked",
                         "openers": opener_ids, "runner": actual})
    if not enabled:
        return {"status": "paused", "reason": "consumer disabled", "waves": outcomes,
                "deferred_openers": deferred}
    return {"status": "output_needs_review" if outcomes and all(
                x["status"] == "output_needs_review" for x in outcomes) else "blocked",
            "reason": "runner outputs require per-task evidence review",
            "waves": outcomes, "deferred_openers": deferred, "delivery_accepted": False}


def _wait_once(batch_id: str) -> dict:
    return wait_tool.wait_for_batch(batch=batch_id, max_wait=0)


def observe_batch(batch_id: str) -> dict:
    try:
        record_path = _batch_record_path(batch_id)
    except ValueError as exc:
        return {"status": "blocked", "reason": str(exc), "delivery_accepted": False}
    if record_path.is_file():
        try:
            record = _read_batch_record(record_path, batch_id)
        except (OSError, ValueError, TypeError) as exc:
            return {"status": "blocked", "reason": "guardian batch record invalid: " + str(exc),
                    "delivery_accepted": False}
        return _batch_result(record)
    observed = _wait_once(batch_id)
    status = observed.get("status")
    if status == "max_wait":
        return {"status": "needs_manual_wake", "observation": observed}
    if status == "done":
        return {"status": "output_needs_review", "observation": observed,
                "delivery_accepted": False}
    if status in ("paused", "no_heartbeat", "timeout"):
        return {"status": "blocked", "observation": observed}
    return {"status": "blocked", "reason": "unknown wait status", "observation": observed}
