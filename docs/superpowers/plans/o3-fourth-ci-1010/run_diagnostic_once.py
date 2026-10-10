#!/usr/bin/env python3
"""Run only the O3 status-card diagnostic copy once; this is not the pytest node."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Dev\zhuopin-ai")
CANDIDATE = Path(r"C:\Users\Paul Shao\.codex\worktrees\o3-recovery-fix-1006\zhuopin-ai")
EXPECTED_HEAD = "0ad830234af70585d359df23123973eceeace3a3"
STATE_REL = Path("0-学习与工具/工具-项目状态卡数据层.ps1")
TEST_REL = Path("5-平台底座/wecom-aibot-service/tests/test_open_pool_alignment.py")
HELPER_REL = Path("0-学习与工具/工具-可Open池.py")
IMPORT_CLOSURE_RELS = [
    HELPER_REL,
    Path("5-平台底座/zhuopin_platform/zhuopin_platform/__init__.py"),
    Path("5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/__init__.py"),
    Path("5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/open_pool.py"),
    Path("5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/queue_table.py"),
]
CI_CWD = CANDIDATE / "5-平台底座/wecom-aibot-service"
STATE_SHA = "BC774E0C9965BE22981390AF7B3255525C87B07038ECB87E2CAB46FDF34A35DF"
TEST_SHA = "4990DDB836775D92DA18FC41998271FA77DDC5AF2BFCE305D30A18A77DAFB360"
RUNS_REL = Path("reports/o3-fourth-ci-1010/runs")
TIMEOUT_MS = 180_000

GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
CREATE_NEW = 1
FILE_ATTRIBUTE_NORMAL = 0x00000080
HANDLE_FLAG_INHERIT = 0x00000001
STARTF_USESTDHANDLES = 0x00000100
CREATE_SUSPENDED = 0x00000004
CREATE_NO_WINDOW = 0x08000000
CREATE_UNICODE_ENVIRONMENT = 0x00000400
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 258
CLEANUP_WAIT_MS = 5_000
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
JOB_OBJECT_BASIC_PROCESS_ID_LIST = 3
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace"
    ).stdout.strip()


def assert_ignored(path: Path) -> None:
    relative = path.resolve().relative_to(REPO.resolve()).as_posix()
    subprocess.run(
        ["git", "-C", str(REPO), "check-ignore", "--quiet", "--", relative],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
    )


def assert_identity(run_dir: Path) -> dict:
    resolved = run_dir.resolve()
    expected_root = (REPO / RUNS_REL).resolve()
    if resolved.parent != expected_root or not re.fullmatch(r"[0-9a-f]{32}", resolved.name):
        raise RuntimeError("Run directory must be exactly reports/o3-fourth-ci-1010/runs/<UUID>")
    assert_ignored(resolved / "runner-metadata.json")
    manifest_path = resolved / "source-manifest.json"
    diagnostic_rel = Path("0-学习与工具/工具-项目状态卡数据层.ps1")
    copy_path = resolved / diagnostic_rel
    if not manifest_path.is_file() or not copy_path.is_file():
        raise RuntimeError("Run directory lacks generator manifest or diagnostic copy")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("execution_state") != "prepared" or (resolved / ".runner-claimed").exists():
        raise RuntimeError("This UUID run directory has already been claimed; generate a fresh UUID")
    candidate = Path(manifest["candidate_root"]).resolve()
    if candidate != CANDIDATE.resolve() or manifest["candidate_head"] != EXPECTED_HEAD:
        raise RuntimeError("Candidate identity mismatch")
    if git(candidate, "rev-parse", "HEAD") != EXPECTED_HEAD:
        raise RuntimeError("Candidate HEAD moved; refuse execution")
    if sha256(candidate / STATE_REL) != STATE_SHA or sha256(REPO / STATE_REL) != STATE_SHA:
        raise RuntimeError("Original status-card SHA changed; refuse execution")
    if sha256(candidate / TEST_REL) != TEST_SHA or sha256(REPO / TEST_REL) != TEST_SHA:
        raise RuntimeError("Actual CI-node SHA changed; refuse execution")
    if manifest.get("diagnostic_copy_relative_path") != diagnostic_rel.as_posix():
        raise RuntimeError("Diagnostic copy is not alongside its helper in the original relative directory")
    if sha256(copy_path) != manifest["diagnostic_copy_sha256"]:
        raise RuntimeError("Generated diagnostic copy SHA mismatch")
    expected_closure = {item["relative_path"]: item["sha256"] for item in manifest["p3_import_closure"]}
    if set(expected_closure) != {path.as_posix() for path in IMPORT_CLOSURE_RELS}:
        raise RuntimeError("Manifest P3 import closure does not match reviewed five-file closure")
    for relative in IMPORT_CLOSURE_RELS:
        expected_sha = expected_closure[relative.as_posix()]
        copy = resolved / relative
        if not copy.is_file() or sha256(copy) != expected_sha:
            raise RuntimeError(f"P3 import-closure copy SHA mismatch: {relative}")
        if sha256(candidate / relative) != expected_sha or sha256(REPO / relative) != expected_sha:
            raise RuntimeError(f"P3 import-closure source changed or differs between trees: {relative}")
    assert_ignored(copy_path)
    for relative in IMPORT_CLOSURE_RELS:
        assert_ignored(resolved / relative)
    return manifest


class SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("nLength", wintypes.DWORD), ("lpSecurityDescriptor", wintypes.LPVOID), ("bInheritHandle", wintypes.BOOL)]


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR), ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR), ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD), ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD), ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD), ("lpReserved2", ctypes.POINTER(ctypes.c_ubyte)),
        ("hStdInput", wintypes.HANDLE), ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE), ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD)]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD),
    ]


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount"
    )]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION), ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def win_api():
    if os.name != "nt":
        raise RuntimeError("Windows Job Object runner required; refuse on non-Windows host")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        ctypes.POINTER(SECURITY_ATTRIBUTES), wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE
    ]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CreateJobObjectW.argtypes = [ctypes.POINTER(SECURITY_ATTRIBUTES), wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.GetStdHandle.argtypes = [wintypes.DWORD]
    kernel.GetStdHandle.restype = wintypes.HANDLE
    kernel.CreateProcessW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
        wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
        ctypes.POINTER(STARTUPINFOW), ctypes.POINTER(PROCESS_INFORMATION)
    ]
    kernel.CreateProcessW.restype = wintypes.BOOL
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
    kernel.QueryInformationJobObject.restype = wintypes.BOOL
    kernel.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel.ResumeThread.restype = wintypes.DWORD
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.TerminateJobObject.restype = wintypes.BOOL
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.TerminateProcess.restype = wintypes.BOOL
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetExitCodeProcess.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.SetHandleInformation.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD]
    kernel.SetHandleInformation.restype = wintypes.BOOL
    kernel.GetLastError.argtypes = []
    kernel.GetLastError.restype = wintypes.DWORD
    return kernel


def win_error(api: str) -> OSError:
    return ctypes.WinError(ctypes.get_last_error(), api)


def create_log_file(kernel, path: Path) -> int:
    security = SECURITY_ATTRIBUTES(ctypes.sizeof(SECURITY_ATTRIBUTES), None, True)
    handle = kernel.CreateFileW(
        str(path), GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
        ctypes.byref(security), CREATE_NEW, FILE_ATTRIBUTE_NORMAL, None
    )
    if handle == wintypes.HANDLE(-1).value:
        raise win_error("CreateFileW")
    return handle


def save_metadata(path: Path, metadata: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def save_metadata_best_effort(path: Path, metadata: dict) -> None:
    try:
        save_metadata(path, metadata)
    except Exception as error:
        failures = metadata.setdefault("metadata_write_failures", [])
        failures.append(f"{type(error).__name__}: {error}")


def terminate_suspended(kernel, process: PROCESS_INFORMATION, metadata: dict) -> None:
    """Terminate only the process created by this runner and prove it exited."""
    metadata["cleanup_action"] = "TerminateProcess(exact suspended PID)"
    if not kernel.TerminateProcess(process.hProcess, 125):
        error = ctypes.get_last_error()
        metadata["cleanup_result"] = f"TerminateProcess failed: WinError {error}"
        save_metadata_best_effort(Path(metadata["metadata_path"]), metadata)
        raise OSError(error, f"Failed to terminate suspended diagnostic PID {process.dwProcessId}")
    wait_result = kernel.WaitForSingleObject(process.hProcess, CLEANUP_WAIT_MS)
    metadata["cleanup_wait_result"] = int(wait_result)
    if wait_result != WAIT_OBJECT_0:
        metadata["cleanup_unconfirmed_pid"] = int(process.dwProcessId)
        save_metadata_best_effort(Path(metadata["metadata_path"]), metadata)
        raise RuntimeError(f"Suspended diagnostic PID {process.dwProcessId} termination was not confirmed")
    metadata["cleanup_result"] = "terminated and process handle signaled"
    metadata["process_state"] = "terminated-before-resume"
    save_metadata_best_effort(Path(metadata["metadata_path"]), metadata)


def job_pids(kernel, job) -> list[int]:
    pointer_size = ctypes.sizeof(ctypes.c_size_t)
    capacity = 256
    buffer = ctypes.create_string_buffer(8 + pointer_size * capacity)
    if not kernel.QueryInformationJobObject(job, JOB_OBJECT_BASIC_PROCESS_ID_LIST, buffer, len(buffer), None):
        raise win_error("QueryInformationJobObject(JobObjectBasicProcessIdList)")
    assigned, returned = ctypes.cast(buffer, ctypes.POINTER(wintypes.DWORD * 2)).contents
    values = ctypes.cast(ctypes.addressof(buffer) + 8, ctypes.POINTER(ctypes.c_size_t * capacity)).contents
    return [int(values[index]) for index in range(min(returned, capacity))]


class VS_FIXEDFILEINFO(ctypes.Structure):
    _fields_ = [(name, wintypes.DWORD) for name in (
        "dwSignature", "dwStrucVersion", "dwFileVersionMS", "dwFileVersionLS",
        "dwProductVersionMS", "dwProductVersionLS", "dwFileFlagsMask", "dwFileFlags",
        "dwFileOS", "dwFileType", "dwFileSubtype", "dwFileDateMS", "dwFileDateLS"
    )]


def executable_file_version(path_text: str | None) -> str | None:
    """Read the selected child interpreter's PE version resource without launching it."""
    if not path_text or os.name != "nt":
        return None
    version = ctypes.WinDLL("version", use_last_error=True)
    version.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    version.GetFileVersionInfoSizeW.restype = wintypes.DWORD
    version.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
    version.GetFileVersionInfoW.restype = wintypes.BOOL
    version.VerQueryValueW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.UINT)]
    version.VerQueryValueW.restype = wintypes.BOOL
    ignored = wintypes.DWORD()
    size = version.GetFileVersionInfoSizeW(path_text, ctypes.byref(ignored))
    if not size:
        return None
    buffer = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(path_text, 0, size, buffer):
        return None
    value = ctypes.c_void_p()
    length = wintypes.UINT()
    if not version.VerQueryValueW(buffer, "\\", ctypes.byref(value), ctypes.byref(length)):
        return None
    fixed = ctypes.cast(value, ctypes.POINTER(VS_FIXEDFILEINFO)).contents
    if fixed.dwSignature != 0xFEEF04BD:
        return None
    return ".".join(str(part) for part in (
        fixed.dwFileVersionMS >> 16, fixed.dwFileVersionMS & 0xFFFF,
        fixed.dwFileVersionLS >> 16, fixed.dwFileVersionLS & 0xFFFF
    ))


def run_under_job(exe: str, args: list[str], cwd: Path, stdout_path: Path, stderr_path: Path, metadata: dict) -> tuple[int | None, bool, int, list[int], str, str]:
    kernel = win_api()
    out_handle = None
    err_handle = None
    job = None
    process = PROCESS_INFORMATION()
    started = now_utc()
    started_clock = time.monotonic()
    assigned = False
    process_created = False
    process_exit_confirmed = False
    observed: set[int] = set()
    try:
        out_handle = create_log_file(kernel, stdout_path)
        err_handle = create_log_file(kernel, stderr_path)
        startup = STARTUPINFOW()
        startup.cb = ctypes.sizeof(STARTUPINFOW)
        startup.dwFlags = STARTF_USESTDHANDLES
        startup.hStdInput = kernel.GetStdHandle(0xFFFFFFF6)
        startup.hStdOutput = out_handle
        startup.hStdError = err_handle
        cmdline = ctypes.create_unicode_buffer(subprocess.list2cmdline([exe, *args]))
        flags = CREATE_SUSPENDED | CREATE_NO_WINDOW | CREATE_UNICODE_ENVIRONMENT
        if not kernel.CreateProcessW(exe, cmdline, None, None, True, flags, None, str(cwd), ctypes.byref(startup), ctypes.byref(process)):
            raise win_error("CreateProcessW(CREATE_SUSPENDED)")
        process_created = True
        observed.add(int(process.dwProcessId))
        metadata.update({"process_pid": int(process.dwProcessId), "process_state": "suspended", "process_created_utc": now_utc()})
        save_metadata(Path(metadata["metadata_path"]), metadata)
        job = kernel.CreateJobObjectW(None, None)
        if not job:
            error = ctypes.get_last_error()
            terminate_suspended(kernel, process, metadata)
            process_exit_confirmed = True
            raise OSError(error, "CreateJobObjectW failed; suspended child was terminated and confirmed")
        limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.get_last_error()
            terminate_suspended(kernel, process, metadata)
            process_exit_confirmed = True
            raise OSError(error, "SetInformationJobObject failed; suspended child was terminated and confirmed")
        if not kernel.AssignProcessToJobObject(job, process.hProcess):
            error = ctypes.get_last_error()
            terminate_suspended(kernel, process, metadata)
            process_exit_confirmed = True
            raise OSError(error, "AssignProcessToJobObject failed; suspended child was terminated and confirmed")
        assigned = True
        metadata.update({"job_assigned": True, "process_state": "job-owned-suspended", "job_assigned_utc": now_utc()})
        save_metadata(Path(metadata["metadata_path"]), metadata)
        if kernel.ResumeThread(process.hThread) == 0xFFFFFFFF:
            error = ctypes.get_last_error()
            if not kernel.TerminateJobObject(job, 125):
                metadata.update({"process_state": "resume-failed-job-termination-failed", "termination_error": ctypes.get_last_error()})
                save_metadata_best_effort(Path(metadata["metadata_path"]), metadata)
                raise OSError(error, f"ResumeThread and owned-job termination failed; PID {process.dwProcessId} retained in metadata")
            wait_result = kernel.WaitForSingleObject(process.hProcess, CLEANUP_WAIT_MS)
            metadata.update({"process_state": "resume-failed-terminated", "termination_wait_result": int(wait_result)})
            process_exit_confirmed = wait_result == WAIT_OBJECT_0
            if not process_exit_confirmed:
                metadata["cleanup_unconfirmed_pids"] = sorted(observed)
            save_metadata_best_effort(Path(metadata["metadata_path"]), metadata)
            if wait_result != WAIT_OBJECT_0:
                raise RuntimeError(f"ResumeThread failed; termination of PID {process.dwProcessId} not confirmed")
            raise OSError(error, "ResumeThread failed; owned suspended process termination confirmed")
        if not kernel.SetHandleInformation(out_handle, HANDLE_FLAG_INHERIT, 0):
            raise win_error("SetHandleInformation(stdout)")
        if not kernel.SetHandleInformation(err_handle, HANDLE_FLAG_INHERIT, 0):
            raise win_error("SetHandleInformation(stderr)")
        metadata.update({"process_state": "running", "process_resumed_utc": now_utc()})
        save_metadata(Path(metadata["metadata_path"]), metadata)

        deadline = time.monotonic() + (TIMEOUT_MS / 1000)
        timed_out = False
        while True:
            observed.update(job_pids(kernel, job))
            remaining_ms = max(0, int((deadline - time.monotonic()) * 1000))
            wait_ms = min(250, remaining_ms)
            wait = kernel.WaitForSingleObject(process.hProcess, wait_ms)
            if wait == WAIT_OBJECT_0:
                break
            if wait != WAIT_TIMEOUT:
                raise win_error("WaitForSingleObject")
            if time.monotonic() >= deadline:
                timed_out = True
                if not kernel.TerminateJobObject(job, 124):
                    metadata.update({"process_state": "timeout-job-termination-failed", "owned_pid_observations": sorted(observed), "termination_error": ctypes.get_last_error()})
                    save_metadata_best_effort(Path(metadata["metadata_path"]), metadata)
                    raise win_error("TerminateJobObject; ownership was assigned but termination failed")
                cleanup_wait = kernel.WaitForSingleObject(process.hProcess, CLEANUP_WAIT_MS)
                if cleanup_wait != WAIT_OBJECT_0:
                    metadata.update({"process_state": "timeout-termination-wait-unconfirmed", "owned_pid_observations": sorted(observed)})
                    metadata["cleanup_unconfirmed_pids"] = sorted(observed)
                    metadata["cleanup_wait_result"] = int(cleanup_wait)
                    save_metadata_best_effort(Path(metadata["metadata_path"]), metadata)
                    raise RuntimeError("Owned-job termination wait exceeded bounded cleanup interval")
                process_exit_confirmed = True
                metadata.update({"process_state": "timed-out-job-terminated", "owned_pid_observations": sorted(observed)})
                save_metadata_best_effort(Path(metadata["metadata_path"]), metadata)
                break
        exit_code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(process.hProcess, ctypes.byref(exit_code)):
            raise win_error("GetExitCodeProcess")
        process_exit_confirmed = True
        metadata.update({"process_state": "completed", "owned_pid_observations": sorted(observed), "observed_exit_code": int(exit_code.value)})
        save_metadata(Path(metadata["metadata_path"]), metadata)
        return (None if timed_out else int(exit_code.value), timed_out, int(process.dwProcessId), sorted(observed), started, now_utc())
    except BaseException as exc:
        metadata.update({
            "process_pid": int(process.dwProcessId) if process_created else None,
            "job_assigned": assigned,
            "process_state": metadata.get("process_state", "before-process-create"),
            "runner_error": f"{type(exc).__name__}: {exc}",
        })
        if process_created and not process_exit_confirmed:
            try:
                if assigned and job:
                    metadata["failure_cleanup_action"] = "TerminateJobObject(exact assigned job)"
                    if kernel.TerminateJobObject(job, 125):
                        wait_result = kernel.WaitForSingleObject(process.hProcess, CLEANUP_WAIT_MS)
                        metadata["failure_cleanup_wait_result"] = int(wait_result)
                        process_exit_confirmed = wait_result == WAIT_OBJECT_0
                        metadata["failure_cleanup_confirmed"] = process_exit_confirmed
                    else:
                        metadata["failure_cleanup_error"] = f"WinError {ctypes.get_last_error()}"
                elif metadata.get("process_state") == "suspended" and not metadata.get("cleanup_result"):
                    metadata["failure_cleanup_action"] = "TerminateProcess(exact suspended PID)"
                    if kernel.TerminateProcess(process.hProcess, 125):
                        wait_result = kernel.WaitForSingleObject(process.hProcess, CLEANUP_WAIT_MS)
                        metadata["failure_cleanup_wait_result"] = int(wait_result)
                        process_exit_confirmed = wait_result == WAIT_OBJECT_0
                        metadata["failure_cleanup_confirmed"] = process_exit_confirmed
                    else:
                        metadata["failure_cleanup_error"] = f"WinError {ctypes.get_last_error()}"
                if not process_exit_confirmed:
                    metadata["cleanup_unconfirmed_pids"] = sorted(observed)
            except Exception as cleanup_error:
                metadata["failure_cleanup_exception"] = f"{type(cleanup_error).__name__}: {cleanup_error}"
                metadata["cleanup_unconfirmed_pids"] = sorted(observed)
        save_metadata_best_effort(Path(metadata["metadata_path"]), metadata)
        raise
    finally:
        if job:
            if assigned and process.hProcess and not process_exit_confirmed:
                metadata["job_handle_close_kill_on_close"] = True
                try:
                    closed = bool(kernel.CloseHandle(job))
                    if not closed:
                        metadata["job_handle_close_error"] = f"WinError {ctypes.get_last_error()}"
                except Exception as close_error:
                    closed = False
                    metadata["job_handle_close_error"] = f"{type(close_error).__name__}: {close_error}"
                if closed:
                    try:
                        wait_result = kernel.WaitForSingleObject(process.hProcess, CLEANUP_WAIT_MS)
                        metadata["post_job_close_wait_result"] = int(wait_result)
                        metadata["post_job_close_termination_confirmed"] = wait_result == WAIT_OBJECT_0
                        if wait_result != WAIT_OBJECT_0:
                            metadata["cleanup_unconfirmed_pids"] = sorted(observed or {int(process.dwProcessId)})
                    except Exception as wait_error:
                        metadata["post_job_close_wait_error"] = f"{type(wait_error).__name__}: {wait_error}"
                        metadata["cleanup_unconfirmed_pids"] = sorted(observed or {int(process.dwProcessId)})
                    job = None
            if job:
                try:
                    if not kernel.CloseHandle(job):
                        metadata["job_handle_close_error"] = f"WinError {ctypes.get_last_error()}"
                    else:
                        job = None
                        if assigned and process.hProcess and not process_exit_confirmed:
                            try:
                                wait_result = kernel.WaitForSingleObject(process.hProcess, CLEANUP_WAIT_MS)
                                metadata["post_job_retry_close_wait_result"] = int(wait_result)
                                process_exit_confirmed = wait_result == WAIT_OBJECT_0
                                if not process_exit_confirmed:
                                    metadata["cleanup_unconfirmed_pids"] = sorted(observed or {int(process.dwProcessId)})
                            except Exception as wait_error:
                                metadata["post_job_retry_close_wait_error"] = f"{type(wait_error).__name__}: {wait_error}"
                                metadata["cleanup_unconfirmed_pids"] = sorted(observed or {int(process.dwProcessId)})
                except Exception as close_error:
                    metadata["job_handle_close_error"] = f"{type(close_error).__name__}: {close_error}"
            if job and assigned and process.hProcess and not process_exit_confirmed:
                try:
                    metadata["final_job_termination_action"] = "TerminateJobObject(exact assigned job)"
                    if kernel.TerminateJobObject(job, 125):
                        wait_result = kernel.WaitForSingleObject(process.hProcess, CLEANUP_WAIT_MS)
                        metadata["final_job_termination_wait_result"] = int(wait_result)
                        process_exit_confirmed = wait_result == WAIT_OBJECT_0
                    if not process_exit_confirmed:
                        metadata["cleanup_unconfirmed_pids"] = sorted(observed or {int(process.dwProcessId)})
                except Exception as final_cleanup_error:
                    metadata["final_job_termination_error"] = f"{type(final_cleanup_error).__name__}: {final_cleanup_error}"
                    metadata["cleanup_unconfirmed_pids"] = sorted(observed or {int(process.dwProcessId)})
                try:
                    if kernel.CloseHandle(job):
                        job = None
                except Exception as close_error:
                    metadata["job_handle_final_close_error"] = f"{type(close_error).__name__}: {close_error}"
        for label, handle in (("process_thread", process.hThread), ("process", process.hProcess), ("stdout", out_handle), ("stderr", err_handle)):
            if handle:
                try:
                    if not kernel.CloseHandle(handle):
                        metadata[f"{label}_handle_close_error"] = f"WinError {ctypes.get_last_error()}"
                except Exception as close_error:
                    metadata[f"{label}_handle_close_error"] = f"{type(close_error).__name__}: {close_error}"
        save_metadata_best_effort(Path(metadata["metadata_path"]), metadata)


def marker_summary(stderr_path: Path) -> dict:
    text = stderr_path.read_bytes().decode("utf-8", errors="replace")
    pattern = re.compile(r"O3_DIAG\|(P[0-7])\|utc=([^|\r\n]+)\|pid=(\d+)(?:\|ps=([^|\r\n]+))?(?:\|py=([^|\r\n]*))?")
    marks = []
    for label, timestamp, pid, ps_version, python_exe in pattern.findall(text):
        marks.append({"phase": label, "utc": timestamp, "pid": int(pid), "powershell_version": ps_version or None, "python_exe": python_exe or None})
    intervals = []
    for left, right in zip(marks, marks[1:]):
        left_dt = datetime.fromisoformat(left["utc"].replace("Z", "+00:00"))
        right_dt = datetime.fromisoformat(right["utc"].replace("Z", "+00:00"))
        intervals.append({"from": left["phase"], "to": right["phase"], "elapsed_ms": int((right_dt - left_dt).total_seconds() * 1000)})
    return {"markers": marks, "intervals": intervals}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path, help="UUID directory emitted by generate_diagnostic_copy.py")
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    manifest = assert_identity(run_dir)
    metadata_path = run_dir / "runner-metadata.json"
    assert_ignored(metadata_path)
    claim_path = run_dir / ".runner-claimed"
    assert_ignored(claim_path)
    reserved_outputs = [
        metadata_path, run_dir / "stdout.bin", run_dir / "stderr.bin",
        metadata_path.with_name(metadata_path.name + ".tmp"),
        (run_dir / "source-manifest.json").with_name("source-manifest.json.tmp"),
    ]
    if any(path.exists() for path in reserved_outputs):
        raise SystemExit("Output already exists; refuse to overwrite or rerun this UUID")
    try:
        claim_fd = os.open(claim_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise SystemExit("This UUID was already claimed; generate a fresh UUID") from error
    with os.fdopen(claim_fd, "w", encoding="utf-8") as claim_stream:
        json.dump({"claimed_utc": now_utc(), "runner_pid": os.getpid()}, claim_stream)
        claim_stream.write("\n")
    manifest["execution_state"] = "claimed"
    manifest["execution_claimed_utc"] = now_utc()
    temporary_manifest = run_dir / "source-manifest.json.tmp"
    temporary_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary_manifest, run_dir / "source-manifest.json")
    save_metadata(metadata_path, {
        "execution_state": "claimed",
        "runner_pid": os.getpid(),
        "claimed_utc": manifest["execution_claimed_utc"],
        "candidate_head": EXPECTED_HEAD,
        "ci_test_node_sha256": TEST_SHA,
    })
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        save_metadata(metadata_path, {"execution_state": "failed-before-start", "error": "No PowerShell executable found", "manifest": manifest})
        raise SystemExit("No PowerShell executable found by the original node's pwsh-then-powershell lookup")
    diagnostic_rel = Path("0-学习与工具/工具-项目状态卡数据层.ps1")
    copy_path = run_dir / diagnostic_rel
    if manifest.get("diagnostic_copy_relative_path") != diagnostic_rel.as_posix():
        raise SystemExit("Diagnostic script is not in the expected UUID/0-学习与工具 layout")
    escaped_path = str(copy_path).replace("'", "''")
    command = f"[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; & '{escaped_path}'"
    args_ps = [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command]
    stdout_path = run_dir / "stdout.bin"
    stderr_path = run_dir / "stderr.bin"
    assert_ignored(stdout_path)
    assert_ignored(stderr_path)
    if not CI_CWD.is_dir():
        save_metadata(metadata_path, {"execution_state": "failed-before-start", "error": f"CI working directory missing: {CI_CWD}", "manifest": manifest})
        raise SystemExit(f"CI working directory missing: {CI_CWD}")
    metadata = {
        "execution_state": "starting",
        "metadata_path": str(metadata_path),
        "candidate_head": EXPECTED_HEAD,
        "ci_test_node": "test_real_queue_reminder_equals_kanban_ps1_pool",
        "ci_test_node_sha256": TEST_SHA,
        "state_card_source_sha256": STATE_SHA,
        "diagnostic_copy_sha256": manifest["diagnostic_copy_sha256"],
        "powershell_executable": str(Path(shell).resolve()),
        "ci_equivalent_cwd": str(CI_CWD),
        "timeout_ms": TIMEOUT_MS,
        "runner_python_executable": sys.executable,
        "runner_python_version": sys.version,
        "runner_pid": os.getpid(),
        "command": args_ps,
        "started_utc": now_utc(),
    }
    save_metadata(metadata_path, metadata)
    try:
        outcome = run_under_job(shell, args_ps[1:], CI_CWD, stdout_path, stderr_path, metadata)
    except BaseException as error:
        metadata.update({"execution_state": "failed-with-preserved-evidence", "exception": f"{type(error).__name__}: {error}"})
        save_metadata_best_effort(metadata_path, metadata)
        manifest["execution_state"] = "failed-with-preserved-evidence"
        manifest["execution_error"] = f"{type(error).__name__}: {error}"
        try:
            temporary_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary_manifest, run_dir / "source-manifest.json")
        except Exception as manifest_error:
            metadata.setdefault("metadata_write_failures", []).append(
                f"source-manifest: {type(manifest_error).__name__}: {manifest_error}"
            )
            save_metadata_best_effort(metadata_path, metadata)
        raise
    exit_code, timed_out, parent_pid, owned_pids, started, ended = outcome
    stdout_bytes = stdout_path.read_bytes()
    metadata.update({
        "classification": "status-card diagnostic only; not pytest and not CI pass/fail",
        "candidate_head": EXPECTED_HEAD,
        "candidate_source_sha256": STATE_SHA,
        "ci_test_node": "test_real_queue_reminder_equals_kanban_ps1_pool",
        "ci_test_node_sha256": TEST_SHA,
        "diagnostic_copy_sha256": manifest["diagnostic_copy_sha256"],
        "powershell_executable": str(Path(shell).resolve()),
        "powershell_version_from_P0_marker": None,
        "command": args_ps,
        "timeout_ms": TIMEOUT_MS,
        "started_utc": started,
        "ended_utc": ended,
        "elapsed_ms": int((datetime.fromisoformat(ended) - datetime.fromisoformat(started)).total_seconds() * 1000),
        "powershell_pid": parent_pid,
        "job_owned_pid_observations": owned_pids,
        "timed_out": timed_out,
        "exit_code": exit_code,
        "stdout_bytes": len(stdout_bytes),
        "stdout_prefix_is_json_marker": stdout_bytes.startswith(b"@@JSON@@"),
        "stdout_line_count": len(stdout_bytes.splitlines()),
        "stderr_bytes": stderr_path.stat().st_size,
        "phase_timing": marker_summary(stderr_path),
        "output_notice": "Raw stdout/stderr remain inside this ignored UUID directory; contents are never printed by runner.",
    })
    p0 = next((m for m in metadata["phase_timing"]["markers"] if m["phase"] == "P0"), None)
    if p0:
        metadata["powershell_version_from_P0_marker"] = p0["powershell_version"]
    p3 = next((m for m in metadata["phase_timing"]["markers"] if m["phase"] == "P3"), None)
    if p3:
        metadata["python_child_executable_from_P3_marker"] = p3["python_exe"]
        metadata["python_child_file_version_resource"] = executable_file_version(p3["python_exe"])
    metadata["execution_state"] = "timed-out" if timed_out else "completed"
    save_metadata(metadata_path, metadata)
    manifest["execution_state"] = metadata["execution_state"]
    manifest["execution_ended_utc"] = ended
    temporary_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary_manifest, run_dir / "source-manifest.json")
    print(json.dumps({"run_dir": str(run_dir), "timed_out": timed_out, "exit_code": exit_code, "stdout_bytes": len(stdout_bytes), "phase_count": len(metadata["phase_timing"]["markers"])}))
    return 124 if timed_out else int(exit_code or 0)


if __name__ == "__main__":
    raise SystemExit(main())
