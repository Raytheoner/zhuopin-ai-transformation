
"""Codex event adapter. Business predicates remain in the original PowerShell guards."""
from __future__ import annotations
import hashlib, json, os, subprocess, sys, uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / "0-学习与工具" / "hooks"

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

def legacy_payload(event, tool, data):
    return {"session_id": event.get("session_id", "codex"), "cwd": event.get("cwd", str(ROOT)),
            "hook_event_name": event["hook_event_name"], "tool_name": tool, "tool_input": data}

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
            data = {"command": data.get("cmd", data.get("command", ""))}
            tool = "Bash"
        payload = legacy_payload(event, tool, data)
        result.extend((script, payload) for script in [
            "hooks-pretooluse-queue-read-guard.ps1", "hooks-pretooluse-dedup-guard.ps1"])
    return result

def audit(event, results, error=None):
    # No prompt, tool input, command, transcript or secret values are recorded.
    state = Path(os.environ.get("ZHUOPIN_CODEX_STATE", str(ROOT / ".codex" / "state")))
    folder = state / "hooks"
    folder.mkdir(parents=True, exist_ok=True)
    row = {"utc": datetime.now(timezone.utc).isoformat(), "event": event.get("hook_event_name"),
           "tool": event.get("tool_name"), "results": results, "error": error,
           "session_id": event.get("session_id"), "turn_id": event.get("turn_id"),
           "cwd": event.get("cwd"), "model": event.get("model"),
           "bridge_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           "input_sha256": hashlib.sha256(json.dumps(event, ensure_ascii=False).encode()).hexdigest()}
    (folder / (uuid.uuid4().hex + ".json")).write_text(json.dumps(row, ensure_ascii=False), encoding="utf8")

def deny_pretool(reason):
    # Native JSON denial does not depend on shell exit-code propagation.
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
        "permissionDecision": "deny", "permissionDecisionReason": reason}}, ensure_ascii=False))
    return 0


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
        if name in ("SessionStart", "UserPromptSubmit"):
            context = ("遵守根 AGENTS.md、CLAUDE.md 和适用 .claude/rules。队列只走工具-队列查询.py；"
                       "先读批准的 intent/design/tasks；ff、生产部署、对外发送保留逐项授权。"
                       "Codex 迁移状态见 0-学习与工具/codex-handoff/README.md。")
            print(json.dumps({"hookSpecificOutput": {"hookEventName": name,
                                                     "additionalContext": context}}, ensure_ascii=False))
        for script, payload in calls(event):
            proc = subprocess.run(["pwsh", "-NoProfile", "-File", str(HOOKS / script)],
                                  input=json.dumps(payload, ensure_ascii=False), text=True, encoding="utf8",
                                  capture_output=True, cwd=payload["cwd"], timeout=20)
            results.append({"script": script, "exit": proc.returncode})
            if proc.returncode:
                audit(event, results)
                # Original guard reason is feedback only; never persist raw payload.
                reason = proc.stderr or proc.stdout or ("Guard failed: " + script)
                if name == "PreToolUse":
                    return deny_pretool(reason)
                sys.stderr.write(reason)
                return 2
        if name == "Stop":
            # Native transcript format is not assumed. Decision formatting is instruction-only.
            results.append({"native_last_message_available": "last_assistant_message" in event,
                            "claude_token_meter": "unsupported"})
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
