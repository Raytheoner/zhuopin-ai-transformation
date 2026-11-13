
"""Codex event adapter. Business predicates remain in the original PowerShell guards."""
from __future__ import annotations
import hashlib, importlib.util, json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = Path(__file__).resolve().parent / "guards"

def targets(tool, data):
    """Parse native apply_patch grammar, including both rename endpoints."""
    if tool in ("apply_patch", "functions.apply_patch"):
        patch = data if isinstance(data, str) else data.get("command", data.get("patch", data.get("input", "")))
        if not isinstance(patch, str):
            raise ValueError("apply_patch payload is not text")
        result, current = [], None
        for line in patch.splitlines():
            if line.startswith(("*** Add File: ", "*** Update File: ", "*** Delete File: ")):
                current = {"path": line.split(": ", 1)[1], "text": ""}
                result.append(current)
            elif line.startswith("*** Move to: "):
                current = {"path": line.split(": ", 1)[1], "text": ""}
                result.append(current)
            elif current is not None and line.startswith("+"):
                current["text"] += line[1:] + "\n"
        if not result:
            raise ValueError("apply_patch has no recognized file targets")
        return result
    if tool in ("Edit", "Write", "MultiEdit"):
        if not isinstance(data, dict) or not data.get("file_path"):
            raise ValueError("missing file_path")
        text = data.get("content", data.get("new_string", ""))
        if tool == "MultiEdit":
            text = "\n".join(e.get("new_string", "") for e in data.get("edits", []))
        return [{"path": data["file_path"], "text": text}]
    return []

def execution_cwd(event, data):
    """Resolve native exec cwd without hiding invalid explicit input."""
    base = event.get("cwd", str(ROOT))
    if not isinstance(base, str) or not base.strip():
        raise ValueError("invalid event cwd")
    base_path = Path(base)
    if not base_path.is_absolute():
        raise ValueError("event cwd must be absolute")
    value = next((data[key] for key in ("workdir", "cwd") if key in data), base)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("invalid execution cwd")
    path = Path(value)
    if not path.is_absolute():
        path = base_path / path
    path = Path(os.path.abspath(path))
    if not path.is_dir():
        raise ValueError("execution cwd is not an existing directory")
    return str(path)


def legacy_payload(event, tool, data):
    return {"session_id": event.get("session_id", "codex"), "cwd": event.get("cwd", str(ROOT)),
            "hook_event_name": event["hook_event_name"], "tool_name": tool, "tool_input": data,
            "_zhuopin_codex_adapter": "native-v1"}

def calls(event):
    name, tool = event["hook_event_name"], event.get("tool_name", "")
    data = event.get("tool_input", {})
    result = []
    if name not in ("PreToolUse", "PostToolUse"):
        return result
    for target in targets(tool, data):
        full = Path(target["path"])
        if not full.is_absolute():
            full = Path(event.get("cwd", str(ROOT))) / full
        payload = legacy_payload(event, "Edit", {"file_path": str(full.resolve()),
                                                "new_string": target["text"], "old_string": ""})
        scripts = ["hooks-pretooluse-editlock-guard.ps1"] if name == "PreToolUse" else [
            "sentinel-mojibake.ps1", "sentinel-pronoun.ps1"]
        result.extend((script, payload) for script in scripts)
    if name == "PreToolUse" and tool in ("exec_command", "functions.exec_command", "Bash", "Read", "Grep"):
        if tool in ("exec_command", "functions.exec_command", "Bash"):
            cwd = execution_cwd(event, data)
            data = {"command": data.get("cmd", data.get("command", "")), "cwd": cwd}
            event = dict(event, cwd=cwd)
            tool = "Bash"
        payload = legacy_payload(event, tool, data)
        result.extend((script, payload) for script in [
            "hooks-pretooluse-queue-read-guard.ps1", "hooks-pretooluse-dedup-guard.ps1"])
    return result

def audit(event, results, error=None):
    # No prompt, tool input, command, transcript or secret values are recorded.
    state = Path(os.environ.get("ZHUOPIN_CODEX_STATE", str(ROOT / ".codex" / "state")))
    folder = state / "hooks"
    row = {"utc": datetime.now(timezone.utc).isoformat(), "event": event.get("hook_event_name"),
           "tool": event.get("tool_name"), "results": results, "error": error,
           "session_id": event.get("session_id"), "turn_id": event.get("turn_id"),
           "cwd": event.get("cwd"), "model": event.get("model"),
           "bridge_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           "input_sha256": hashlib.sha256(json.dumps(event, ensure_ascii=False).encode()).hexdigest()}
    if event.get('tool_name') in ('functions.exec', 'exec'):
        row['coverage'] = 'opaque_orchestration; nested host events unverified'
    spec = importlib.util.spec_from_file_location('local_hook_audit', Path(__file__).with_name('hook_audit_store.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.append(folder, row)


def effective_calls(event):
    """Preserve guard predicates while avoiding processes that cannot apply."""
    for script, payload in calls(event):
        if script == 'hooks-pretooluse-dedup-guard.ps1' and payload['tool_name'] == 'Bash':
            # The legacy Bash branch only counts, never blocks or validates.
            continue
        if script == 'sentinel-pronoun.ps1':
            path = payload['tool_input']['file_path'].replace('\\', '/')
            if '/6-人才与组织/部门AI专员跟进/' not in path or not path.lower().endswith('.md'):
                continue
        yield script, payload

def deny_pretool(reason):
    # Native JSON denial does not depend on shell exit-code propagation.
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
        "permissionDecision": "deny", "permissionDecisionReason": reason}}, ensure_ascii=False))
    return 0


def native_guard_environment(event_name):
    # Preserve all shared-lock, repository and roster roots. The native helper
    # binds only audit output and mode configuration to the reviewed checkout.
    env = dict(os.environ)
    env['ZHUOPIN_SENTINEL_AUDIT_ROOT'] = str(ROOT)
    return env


def main():
    event, results = {}, []
    known_events = {"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"}
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
        if not isinstance(event, dict):
            raise ValueError("hook payload must be an object")
        name = event.get("hook_event_name")
        if not isinstance(name, str) or name not in known_events:
            raise ValueError("missing or unsupported hook event")
        if name in ('UserPromptSubmit', 'Stop'):
            return 0
        if name == "SessionStart":
            context = "按根 AGENTS.md 路由；仅明确接续才读对应接力。"
            print(json.dumps({"hookSpecificOutput": {"hookEventName": name,
                                                     "additionalContext": context}}, ensure_ascii=False))
        pending = list(effective_calls(event))
        if name == 'PostToolUse' and not pending:
            return 0
        if pending:
            config_spec = importlib.util.spec_from_file_location(
                'native_guard_readiness', Path(__file__).with_name('hook_configuration.py'))
            configuration = importlib.util.module_from_spec(config_spec)
            config_spec.loader.exec_module(configuration)
            try:
                configuration.verify_native_guard_bundle(ROOT)
            except (OSError, ValueError) as exc:
                audit(event, results, 'native_guard_bundle_incomplete')
                reason = str(exc)
                if name == 'PreToolUse':
                    return deny_pretool(reason)
                sys.stderr.write(reason+'\n')
                return 2
        for script, payload in pending:
            proc = subprocess.run(["pwsh", "-NoProfile", "-File", str(HOOKS / script)],
                                  input=json.dumps(payload, ensure_ascii=False), text=True, encoding="utf8",
                                  capture_output=True, cwd=payload["cwd"], timeout=20,
                                  env=native_guard_environment(name))
            results.append({"script": script, "exit": proc.returncode})
            if proc.returncode:
                audit(event, results)
                # Original guard reason is feedback only; never persist raw payload.
                reason = proc.stderr or proc.stdout or ("Guard failed: " + script)
                if name == "PreToolUse":
                    return deny_pretool(reason)
                sys.stderr.write(reason)
                return 2
        audit(event, results)
        return 0
    except Exception as exc:
        try:
            audit(event, results, type(exc).__name__)
        except Exception:
            pass
        reason = "Codex hook adapter error: " + type(exc).__name__ + "; inspect runtime and hook audit."
        # An unclassifiable input must never turn a PreToolUse error into permission.
        event_name = event.get("hook_event_name") if isinstance(event, dict) else None
        if not isinstance(event_name, str) or event_name == "PreToolUse" or event_name not in known_events:
            return deny_pretool(reason)
        sys.stderr.write(reason + "\n")
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
