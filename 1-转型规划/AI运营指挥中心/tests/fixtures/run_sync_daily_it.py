#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
run_sync_daily.py -- rotation-safe daily orchestrator for the
SalesEasy (sales-xiaoshouyi) -> portal data pipeline on 192.168.100.51.

WHY THIS EXISTS
  The existing 08:00 task runs xiaoshouyi_data_sync_fixed.py, which:
    * uses a STATIC access token from .env and never refreshes it, and
    * logs an error but still exits 0 when the API rejects that token.
  Consequence: it failed silently every day from 2026-07-05 (the day the
  access token expired) while Task Scheduler kept reporting success.
  Separately, nothing on this server publishes crm_data\\dashboard_data.json
  to the portal file C:\\command-center\\data\\sales_dashboard_data.json --
  that step used to be done by hand from a laptop.

WHAT IT DOES (in order)
  1. refresh : exchange the .env refresh_token for a fresh access_token.
               A rotated refresh_token, if the vendor returns one, is
               persisted immediately (refresh tokens can be single-use).
  2. sync    : run the UNCHANGED xiaoshouyi_data_sync_fixed.py.
  3. verify  : prove the sync actually wrote fresh data (mtime advanced),
               so "exit 0 but wrote nothing" can no longer pass.
  4. publish : redact PII (high_risk_leads[].contact / .phone / .email -> the
               "already redacted" marker) and write the portal data file atomically.
  5. exit    : 0 only if every step succeeded, non-zero otherwise.

BOUNDARIES
  * Does NOT modify xiaoshouyi_data_sync_fixed.py.
  * Does NOT create or modify any scheduled task -- the task action is changed
    by hand, once, during the maintenance window.
  * Writes exactly two files: .env (step 1) and the portal JSON (step 4).
    Both go through temp-file + os.replace, with the ACL applied to the temp
    file first, so the replacement keeps SYSTEM + Administrators only.
  * Never logs credential values -- lengths and error codes only.
  * No TLS verification is bypassed.

USAGE
  Scheduled-task action becomes:
    C:\\salesmarketing\\.venv\\Scripts\\python.exe C:\\salesmarketing\\run_sync_daily.py
  with working directory C:\\salesmarketing.

  Useful flags:
    --self-test        exercise redaction + atomic write on synthetic data
    --skip-refresh     do not touch .env (test the sync/verify/publish half)
    --skip-sync        do not run the sync (test refresh + publish only)
    --base DIR         override C:\\salesmarketing      (testing)
    --portal FILE      override the portal JSON path   (testing)
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# --------------------------------------------------------------------- config

BASE = Path(r"C:\salesmarketing")
ENV_FILE = BASE / ".env"
SYNC_SCRIPT = BASE / "xiaoshouyi_data_sync_fixed.py"
RAW_JSON = BASE / "crm_data" / "raw_data.json"
DASH_JSON = BASE / "crm_data" / "dashboard_data.json"
PORTAL_JSON = Path(r"C:\command-center\data\sales_dashboard_data.json")
LOG_FILE = BASE / "xiaoshouyi_sync.log"

TOKEN_URL = "https://login.xiaoshouyi.com/auc/oauth2/token"
REDACTED = "\u5df2\u8131\u654f"          # the marker meaning "already redacted"
REDACT_FIELDS = ("contact", "phone", "email")
SYNC_TIMEOUT_S = 900

EXIT_OK = 0
EXIT_REFRESH = 10
EXIT_SYNC = 11
EXIT_PUBLISH = 12
EXIT_ENV = 13

# ------------------------------------------------------------------ utilities


def now_stamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]


def scrub(text):
    """Best-effort removal of anything that looks like a secret."""
    if not text:
        return ""
    text = re.sub(r"[0-9a-fA-F]{32,}", "<SECRET>", text)
    text = re.sub(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        "<GUID>", text)
    text = re.sub(r"[A-Za-z0-9+/=_.\-]{40,}", "<SECRET>", text)
    return text[:400]


def log(level, message):
    line = "%s - [%s] - %s" % (now_stamp(), level, message)
    try:
        print(line, flush=True)
    except Exception:
        pass
    try:
        with open(str(LOG_FILE), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def restrict_acl(path):
    """Grant only SYSTEM + Administrators, breaking inheritance.

    Well-known SIDs are used so this works on any display language.
    """
    try:
        proc = subprocess.run(
            ["icacls", str(path), "/inheritance:r",
             "/grant:r", "*S-1-5-18:(F)", "*S-1-5-32-544:(F)"],
            capture_output=True, text=True, timeout=60)
        return proc.returncode == 0
    except Exception:
        return False


def inheritance_blocked(path):
    try:
        proc = subprocess.run(["icacls", str(path)],
                              capture_output=True, text=True, timeout=60)
        out = proc.stdout or ""
        return ("(I)" not in out)
    except Exception:
        return False


def write_atomic(path, data_bytes, restrict=True, must_restrict=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(str(tmp), "wb") as fh:
        fh.write(data_bytes)
        fh.flush()
        os.fsync(fh.fileno())

    acl_ok = True
    if restrict:
        acl_ok = restrict_acl(tmp) and inheritance_blocked(tmp)
        if not acl_ok and must_restrict:
            try:
                os.remove(str(tmp))
            except Exception:
                pass
            raise RuntimeError(
                "could not restrict permissions on %s -- aborted and removed the "
                "temporary file, refusing to leave credentials readable by others"
                % path)

    os.replace(str(tmp), str(path))
    return acl_ok


def read_env(path):
    data = {}
    path = Path(path)
    if not path.exists():
        return data
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        s = raw.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, value = s.split("=", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def update_env_file(path, updates, restrict=True):
    """Rewrite .env replacing/adding the given keys, preserving everything else."""
    path = Path(path)
    lines = []
    if path.exists():
        lines = path.read_text(encoding="utf-8-sig").splitlines()

    seen = set()
    out = []
    for raw in lines:
        m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", raw)
        if m and m.group(1) in updates:
            out.append("%s=%s" % (m.group(1), updates[m.group(1)]))
            seen.add(m.group(1))
        else:
            out.append(raw)
    for key, value in updates.items():
        if key not in seen:
            out.append("%s=%s" % (key, value))

    payload = ("\n".join(out) + "\n").encode("utf-8")
    return write_atomic(path, payload, restrict=restrict, must_restrict=restrict)


# ------------------------------------------------------------------- pipeline


def refresh_access_token(env):
    """Return (token_dict, None) on success or (None, reason) on failure."""
    client_id = env.get("XIAOSHOUYI_CLIENT_ID")
    client_secret = env.get("XIAOSHOUYI_CLIENT_SECRET")
    refresh_tok = env.get("XIAOSHOUYI_REFRESH_TOKEN")
    if not (client_id and client_secret and refresh_tok):
        return None, "client_id / client_secret / refresh_token missing from .env"

    try:
        import requests
    except ImportError:
        return None, "the 'requests' package is not installed in this interpreter"

    try:
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_tok,
            },
            timeout=30,
        )
    except Exception as exc:
        return None, "transport error: %s" % type(exc).__name__

    try:
        body = resp.json()
    except Exception:
        return None, "HTTP %s but the response body was not JSON" % resp.status_code

    if isinstance(body, dict) and body.get("access_token"):
        return body, None

    # The vendor reports OAuth failures as HTTP 200 plus an error object.
    code = "-"
    message = "-"
    if isinstance(body, dict):
        code = body.get("scode") or body.get("error") or body.get("error_code") or "-"
        message = (body.get("error_msg") or body.get("error_description")
                   or body.get("message") or "-")
    return None, "HTTP %s, vendor error scode=%s msg=%s" % (
        resp.status_code, code, scrub(str(message)))


def run_sync(python_exe):
    command = [python_exe, str(SYNC_SCRIPT)]
    try:
        proc = subprocess.run(command, cwd=str(BASE), capture_output=True,
                              text=True, errors="replace",
                              timeout=SYNC_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return None, "sync timed out after %s s" % SYNC_TIMEOUT_S
    except Exception as exc:
        return None, "could not start the sync script: %s" % type(exc).__name__

    # The sync script logs INFO to stderr, so stderr is NOT an error signal, and it
    # writes console text in the locale code page (not utf-8).
    combined = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    for line in combined.splitlines()[-8:]:
        log("INFO", "sync| " + scrub(line))
    if proc.returncode != 0:
        log("ERROR", "sync exit code = %s" % proc.returncode)
    else:
        log("INFO", "sync exit code = 0")
    return proc.returncode, None


def verify_fresh(started_at):
    problems = []
    for path in (RAW_JSON, DASH_JSON):
        if not path.exists():
            problems.append("%s is missing" % path.name)
            continue
        stat = path.stat()
        if stat.st_size <= 0:
            problems.append("%s is empty" % path.name)
        if stat.st_mtime <= started_at - 2:
            problems.append("%s was NOT rewritten (mtime still %s)" % (
                path.name,
                datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")))
    if not problems:
        try:
            obj = json.loads(DASH_JSON.read_text(encoding="utf-8-sig"))
            total = (obj.get("kpis") or {}).get("total_leads")
            if not total:
                problems.append("dashboard_data.json has kpis.total_leads = %r" % (total,))
        except Exception as exc:
            problems.append("dashboard_data.json is not valid JSON: %s" % type(exc).__name__)
    return problems


def redact_and_publish(src, dst, restrict=True):
    """Redact PII from src and write the result to dst atomically."""
    obj = json.loads(Path(src).read_text(encoding="utf-8-sig"))
    rows = obj.get("high_risk_leads") or []
    redacted = 0
    for row in rows:
        if isinstance(row, dict):
            for field in REDACT_FIELDS:
                if field in row:
                    row[field] = REDACTED
                    redacted += 1
    payload = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    write_atomic(dst, payload, restrict=restrict)
    return redacted, len(rows)


# ------------------------------------------------------------------ self test


def self_test(work_dir=None):
    created = False
    if work_dir:
        tmpdir = Path(work_dir)
        tmpdir.mkdir(parents=True, exist_ok=True)
    else:
        tmpdir = Path(tempfile.mkdtemp(prefix="xsy_selftest_"))
        created = True
    src = tmpdir / "dashboard_data.json"
    dst = tmpdir / "sales_dashboard_data.json"
    sample = {
        "kpis": {"total_leads": 1675, "total_customers": 833},
        "funnel": [{"stage": "MQL", "count": 1675, "rate": "100%"}],
        "score_distribution": {"0-20": 1017},
        "channels": [{"name": "Some Company Ltd", "amount": 1.0, "count": 2}],
        "high_risk_leads": [
            {"id": 1, "company": "ACME", "contact": "Sandra Su",
             "phone": "025-85809089", "email": "a@b.com", "score": 100},
            {"id": 2, "company": "MOTORY", "contact": "Jiayongfei",
             "phone": "021-1232222", "email": "c@d.com", "score": 100},
        ],
        "sync_time": "2026-07-04T08:00:17.310923",
    }
    src.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")

    redacted, rows = redact_and_publish(src, dst, restrict=False)
    out = json.loads(dst.read_text(encoding="utf-8-sig"))

    checks = []
    checks.append(("2 rows processed", rows == 2))
    checks.append(("6 fields redacted", redacted == 6))
    checks.append(("contact redacted",
                   all(r["contact"] == REDACTED for r in out["high_risk_leads"])))
    checks.append(("phone redacted",
                   all(r["phone"] == REDACTED for r in out["high_risk_leads"])))
    checks.append(("email redacted",
                   all(r["email"] == REDACTED for r in out["high_risk_leads"])))
    checks.append(("company NOT redacted",
                   out["high_risk_leads"][0]["company"] == "ACME"))
    checks.append(("channels[].name NOT redacted",
                   out["channels"][0]["name"] == "Some Company Ltd"))
    checks.append(("kpis preserved", out["kpis"]["total_leads"] == 1675))
    checks.append(("sync_time preserved",
                   out["sync_time"] == "2026-07-04T08:00:17.310923"))
    checks.append(("no leak of the original phone",
                   "025-85809089" not in dst.read_text(encoding="utf-8-sig")))
    checks.append(("no .tmp left behind", not (tmpdir / "sales_dashboard_data.json.tmp").exists()))

    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print("  %-32s %s" % (name, "OK" if ok else "*** FAIL ***"))

    try:
        for child in tmpdir.iterdir():
            if child.is_file():
                child.unlink()
        if created:
            tmpdir.rmdir()
    except Exception:
        pass

    if failed:
        print("SELF-TEST FAILED: %s" % ", ".join(failed))
        return 1
    print("SELF-TEST: ALL CHECKS PASS")
    return 0


# ----------------------------------------------------------------------- main


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--work-dir", default=None)
    parser.add_argument("--skip-refresh", action="store_true")
    parser.add_argument("--skip-sync", action="store_true")
    parser.add_argument("--base", default=None)
    parser.add_argument("--portal", default=None)
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--sync-script", default=None)
    args = parser.parse_args()

    if args.self_test:
        return self_test(args.work_dir)

    global BASE, ENV_FILE, SYNC_SCRIPT, RAW_JSON, DASH_JSON, PORTAL_JSON, LOG_FILE
    if args.base:
        BASE = Path(args.base)
        ENV_FILE = BASE / ".env"
        RAW_JSON = BASE / "crm_data" / "raw_data.json"
        DASH_JSON = BASE / "crm_data" / "dashboard_data.json"
        LOG_FILE = BASE / "xiaoshouyi_sync.log"
    if args.env_file:
        ENV_FILE = Path(args.env_file)
    if args.sync_script:
        SYNC_SCRIPT = Path(args.sync_script)
    if args.portal:
        PORTAL_JSON = Path(args.portal)

    log("INFO", "=== run_sync_daily start ===")
    started_at = time.time()

    # ---- step 1: refresh -------------------------------------------------
    if args.skip_refresh:
        log("INFO", "step 1 SKIPPED (--skip-refresh); .env untouched")
    else:
        env = read_env(ENV_FILE)
        token, reason = refresh_access_token(env)
        if reason:
            log("ERROR", "step 1 refresh FAILED: " + reason)
            log("ERROR", "the sync was NOT started; this task must exit non-zero")
            return EXIT_REFRESH
        updates = {"XIAOSHOUYI_ACCESS_TOKEN": token["access_token"]}
        if token.get("refresh_token"):
            updates["XIAOSHOUYI_REFRESH_TOKEN"] = token["refresh_token"]
        try:
            update_env_file(ENV_FILE, updates, restrict=True)
        except Exception as exc:
            log("ERROR", "step 1 could not write .env safely: %s" % exc)
            return EXIT_ENV
        old_refresh = env.get("XIAOSHOUYI_REFRESH_TOKEN") or ""
        if "XIAOSHOUYI_REFRESH_TOKEN" not in updates:
            note = "not returned by the vendor (old value kept)"
        elif updates["XIAOSHOUYI_REFRESH_TOKEN"] == old_refresh:
            note = "re-issued with the SAME value (vendor does not rotate)"
        else:
            note = "ROTATED - new value persisted"
        log("INFO", "step 1 OK: access_token updated (len=%d); refresh_token %s" % (
            len(token["access_token"]), note))

    # ---- step 2: sync ----------------------------------------------------
    if args.skip_sync:
        log("INFO", "step 2 SKIPPED (--skip-sync)")
    else:
        code, error = run_sync(sys.executable)
        if error:
            log("ERROR", "step 2 sync FAILED: " + error)
            return EXIT_SYNC
        if code != 0:
            log("ERROR", "step 2 sync returned exit code %s" % code)
            return EXIT_SYNC

        # ---- step 3: verify ---------------------------------------------
        problems = verify_fresh(started_at)
        if problems:
            log("ERROR", "step 3 verification FAILED (the sync did not produce fresh data):")
            for item in problems:
                log("ERROR", "   - " + item)
            return EXIT_SYNC
        log("INFO", "step 3 OK: crm_data json files were rewritten")

    # ---- step 4: redact + publish ---------------------------------------
    try:
        redacted, rows = redact_and_publish(DASH_JSON, PORTAL_JSON, restrict=True)
    except Exception as exc:
        log("ERROR", "step 4 publish FAILED: %s: %s" % (type(exc).__name__, exc))
        return EXIT_PUBLISH
    log("INFO", "step 4 OK: redacted %d field(s) across %d row(s) -> %s" % (
        redacted, rows, PORTAL_JSON))

    log("INFO", "=== run_sync_daily finished OK in %.1fs ===" % (time.time() - started_at))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
