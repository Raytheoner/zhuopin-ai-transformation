#!/usr/bin/env python3
"""Narrow, fail-closed local sealing helper for the five frozen candidates.

This is a draft. Default invocation is read-only preflight. --seal is gated by
an externally registered, human-approved binding JSON and by the formal script
path; this source-report copy can never seal candidates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import uuid


MAIN = Path(r"C:\Dev\zhuopin-ai")
REPORT = MAIN / "reports" / "candidate-integration-1010"
PLAN = REPORT / "seal-plan-preparation" / "plan.md"
MANIFEST = Path(__file__).with_name("manifest.json")
FORMAL_SCRIPT = MAIN / "docs" / "superpowers" / "plans" / "five-candidates-seal-1010" / "seal_candidates.py"
FORMAL_PLAN = MAIN / "docs" / "superpowers" / "plans" / "2026-10-10-five-candidates-seal.md"
AUTHORIZATION = MAIN / "0-学习与工具" / "codex-handoff" / "五候选本地提交批准消费-2026-10-10.json"
EE5_STATUS_RECORD = MAIN / "0-学习与工具" / "codex-handoff" / "EE5根作业状态-2026-10-10.json"
QUEUE_QUERY = MAIN / "0-学习与工具" / "工具-队列查询.py"
BASE = "28337c0ebb52afdbf61e955ecdbc22d151bcd185"
MANIFEST_SHA256 = "A4996E4758B4A36326D95D87524EAC63F02135AF57A126135CF2CBA5C51D12DB"
AUTH_SCHEMA = "candidate-seal-approval/v1"

LANES = {
    "SC2": {
        "root": Path(r"C:\Users\Paul Shao\.codex\worktrees\sc2-biztype316-1010\zhuopin-ai"),
        "git_dir": MAIN / ".git" / "worktrees" / "zhuopin-ai",
        "ref": "codex/candidate-sc2-1010",
    },
    "SC4": {
        "root": Path(r"C:\Users\Paul Shao\.codex\worktrees\sc4-source-evidence-1010\zhuopin-ai"),
        "git_dir": MAIN / ".git" / "worktrees" / "zhuopin-ai23",
        "ref": "codex/candidate-sc4-1010",
    },
    "SC10": {
        "root": Path(r"C:\Users\Paul Shao\.codex\worktrees\sc10-versioned-facts-1010\zhuopin-ai"),
        "git_dir": MAIN / ".git" / "worktrees" / "zhuopin-ai22",
        "ref": "codex/candidate-sc10-1010",
    },
    "SC11": {
        "root": Path(r"C:\Users\Paul Shao\.codex\worktrees\sc11-inventory-transfer-1010\zhuopin-ai"),
        "git_dir": MAIN / ".git" / "worktrees" / "zhuopin-ai24",
        "ref": "codex/candidate-sc11-1010",
    },
    "O4": {
        "root": Path(r"C:\Users\Paul Shao\.codex\worktrees\o4-stage0-evidence-1010\zhuopin-ai"),
        "git_dir": MAIN / ".git" / "worktrees" / "zhuopin-ai25",
        "ref": "codex/candidate-o4-1010",
    },
}
ORDER = ("SC2", "SC4", "SC10", "SC11", "O4")
PATH_COUNTS = {"SC2": 14, "SC4": 8, "SC10": 4, "SC11": 7, "O4": 8}
TRACKED_MODIFIED_COUNTS = {"SC2": 13, "SC4": 7, "SC10": 2, "SC11": 5, "O4": 0}
UNTRACKED_COUNTS = {"SC2": 1, "SC4": 1, "SC10": 2, "SC11": 2, "O4": 8}


class Stop(Exception):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def check_git_environment(evidence: "Evidence") -> None:
    # GIT_PAGER is harmless here because every Git argv explicitly uses --no-pager.
    allowed = {"GIT_OPTIONAL_LOCKS", "GIT_TERMINAL_PROMPT", "GIT_PAGER"}
    blocked = sorted(
        name for name, value in os.environ.items()
        if name.upper().startswith("GIT_") and name.upper() not in allowed and value != ""
    )
    if blocked:
        evidence.summary["rejected_git_environment_names"] = blocked
        raise Stop(f"non-empty Git control environment variables are disallowed: {', '.join(blocked)}")


def canonical(path: Path) -> str:
    return os.path.normcase(str(path.resolve(strict=True))).replace("/", "\\")


def normalized(path: Path) -> str:
    return os.path.normcase(str(path.resolve(strict=False))).replace("/", "\\")


class Evidence:
    def __init__(self) -> None:
        parent = REPORT / "seal-evidence"
        parent.mkdir(parents=True, exist_ok=True)
        self.root = parent / str(uuid.uuid4())
        self.root.mkdir(exist_ok=False)
        self.count = 0
        self.current_lane: dict | None = None
        self.summary: dict = {"lanes": [], "actualexit": None, "error": None, "rejected_git_environment_names": []}

    def begin_lane(self, lane: str) -> dict:
        item = {
            "lane": lane,
            "head": None,
            "ref": LANES[lane]["ref"],
            "current_ref": None,
            "parent": None,
            "tree": None,
            "preflightchecks": {},
            "actualexit": None,
            "error": None,
            "freezeverificationlimit": "not_applicable" if lane not in ("SC10", "SC11") else "unverifiable_by_official_query",
        }
        self.summary["lanes"].append(item)
        self.current_lane = item
        return item

    def write_summary(self) -> None:
        (self.root / "summary.json").write_text(json.dumps(self.summary, ensure_ascii=False, indent=2), encoding="utf-8")

    def record(self, label: str, argv: list[str], cwd: Path, result: subprocess.CompletedProcess[bytes]) -> None:
        self.count += 1
        prefix = self.root / f"{self.count:03d}-{label}"
        prefix.with_suffix(".stdout.bin").write_bytes(result.stdout or b"")
        prefix.with_suffix(".stderr.bin").write_bytes(result.stderr or b"")
        (self.root / f"{self.count:03d}-{label}.json").write_text(
            json.dumps({"argv": argv, "cwd": str(cwd), "returncode": result.returncode}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


class Runner:
    def __init__(self, evidence: Evidence):
        self.evidence = evidence

    def run(self, label: str, argv: list[str], cwd: Path, expected: tuple[int, ...] = (0,)) -> bytes:
        env = os.environ.copy()
        env["GIT_OPTIONAL_LOCKS"] = "0"
        result = subprocess.run(argv, cwd=str(cwd), env=env, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.evidence.record(label, argv, cwd, result)
        self.evidence.summary["actualexit"] = result.returncode
        if self.evidence.current_lane is not None:
            self.evidence.current_lane["actualexit"] = result.returncode
            self.evidence.current_lane.setdefault("subprocesses", []).append({"label": label, "exit": result.returncode})
            self.evidence.write_summary()
        if result.returncode not in expected:
            raise Stop(f"{label}: exit {result.returncode}; raw stdout/stderr saved in {self.evidence.root}")
        return result.stdout


def git(runner: Runner, lane: str, root: Path, label: str, args: list[str], expected: tuple[int, ...] = (0,)) -> bytes:
    return runner.run(f"{lane}-{label}", ["git", "--no-pager", "-C", str(root), *args], root, expected)


def read_manifest() -> dict:
    if MANIFEST.is_symlink() or not MANIFEST.is_file():
        raise Stop("frozen manifest is missing or a symlink")
    if sha256_file(MANIFEST) != MANIFEST_SHA256:
        raise Stop("frozen manifest SHA256 mismatch")
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if (value.get("manifest") != "candidate-integration-freeze-inventory"
            or value.get("base", {}).get("commit") != BASE or value.get("candidate_count") != 5
            or value.get("approved_path_count_total") != 41
            or value.get("tracked_modified_total") != 27 or value.get("untracked_total") != 14):
        raise Stop("manifest base/candidate count mismatch")
    frozen_main = value.get("main", {})
    if (canonical(Path(frozen_main.get("root", ""))) != canonical(MAIN)
            or canonical(Path(frozen_main.get("git_dir", ""))) != canonical(MAIN / ".git")
            or canonical(Path(frozen_main.get("common_git_dir", ""))) != canonical(MAIN / ".git")
            or frozen_main.get("current_branch") != "master"
            or frozen_main.get("head") != frozen_main.get("refs_heads_master")
            or frozen_main.get("approved_scope_path_count") != 41
            or frozen_main.get("approved_scope_dirty_overlap") != []
            or frozen_main.get("approved_scope_committed_delta_from_base") != []):
        raise Stop("manifest frozen main identity/scope fields do not match the approved snapshot schema")
    actual = [x.get("lane") for x in value.get("candidates", [])]
    if tuple(actual) != ORDER:
        raise Stop(f"manifest lane order mismatch: {actual}")
    for candidate in value["candidates"]:
        if candidate.get("approved_path_count") != PATH_COUNTS[candidate["lane"]] or len(candidate.get("files", [])) != PATH_COUNTS[candidate["lane"]]:
            raise Stop(f"manifest frozen path count mismatch for {candidate['lane']}")
        spec = LANES[candidate["lane"]]
        if canonical(Path(candidate["root"])) != canonical(spec["root"]):
            raise Stop(f"manifest root mismatch for {candidate['lane']}")
        if canonical(Path(candidate["git_dir"])) != canonical(spec["git_dir"]):
            raise Stop(f"manifest git_dir mismatch for {candidate['lane']}")
        if canonical(Path(candidate["common_git_dir"])) != canonical(MAIN / ".git"):
            raise Stop(f"manifest common git dir mismatch for {candidate['lane']}")
        if candidate.get("head") != BASE or candidate.get("detached_head") is not True or candidate.get("branch") is not None:
            raise Stop(f"manifest candidate HEAD/detached state mismatch for {candidate['lane']}")
        for item in candidate["files"]:
            if item.get("worktree_status") not in (" M", "??"):
                raise Stop(f"manifest status outside frozen schema: {candidate['lane']}:{item.get('path')}")
            if bool(item.get("tracked_in_index")) != bool(item.get("baseline", {}).get("present")):
                raise Stop(f"manifest tracked/baseline presence mismatch: {candidate['lane']}:{item.get('path')}")
            if item.get("baseline") != item.get("main_current"):
                raise Stop(f"manifest main-current entry differs from baseline: {candidate['lane']}:{item.get('path')}")
            if not re_full_hex(item.get("candidate_worktree_sha256"), 64):
                raise Stop(f"manifest raw SHA missing/invalid: {candidate['lane']}:{item.get('path')}")
            if not re_full_hex(item.get("candidate_git_blob_oid"), 40):
                raise Stop(f"manifest clean OID missing/invalid: {candidate['lane']}:{item.get('path')}")
        modified_count = sum(x["worktree_status"] == " M" for x in candidate["files"])
        untracked_count = sum(x["worktree_status"] == "??" for x in candidate["files"])
        if modified_count != candidate.get("tracked_modified") or modified_count != TRACKED_MODIFIED_COUNTS[candidate["lane"]]:
            raise Stop(f"manifest modified count mismatch for {candidate['lane']}")
        if untracked_count != candidate.get("untracked") or untracked_count != UNTRACKED_COUNTS[candidate["lane"]]:
            raise Stop(f"manifest untracked count mismatch for {candidate['lane']}")
    all_paths = [item["path"] for candidate in value["candidates"] for item in candidate["files"]]
    if len(all_paths) != 41 or len(set(all_paths)) != 41:
        raise Stop("manifest does not contain 41 unique approved paths")
    return value


def selected_plan() -> Path:
    current = normalized(Path(__file__))
    if current == normalized(FORMAL_SCRIPT):
        return FORMAL_PLAN
    source_script = REPORT / "seal-plan-preparation" / "seal_candidates.py"
    if current == normalized(source_script):
        return PLAN
    raise Stop("preflight/approval script path is neither the source draft nor the registered formal script")


def re_full_hex(value: object, length: int) -> bool:
    return isinstance(value, str) and len(value) == length and all(c in "0123456789abcdefABCDEF" for c in value)


def bytes_lines(data: bytes) -> list[bytes]:
    return [part for part in data.split(b"\0") if part]


def status_map(data: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    fields = data.split(b"\0")
    i = 0
    while i < len(fields) and fields[i]:
        entry = fields[i]
        if len(entry) < 4 or entry[2:3] != b" ":
            raise Stop("unparseable porcelain-v1 status")
        code = entry[:2].decode("ascii", "strict")
        path = entry[3:].decode("utf-8", "strict").replace("\\", "/")
        if code in ("R ", " R", "C ", " C"):
            raise Stop("rename/copy status is outside the frozen status schema")
        if path in result:
            raise Stop(f"duplicate status path: {path}")
        result[path] = code
        i += 1
        if "R" in code or "C" in code:
            i += 1
    return result


def ensure_inside_no_reparse(root: Path, rel: str) -> Path:
    root_abs = Path(canonical(root))
    candidate = root_abs.joinpath(*rel.split("/"))
    current = root_abs
    parts = rel.split("/")
    for part in parts:
        if part in ("", ".", ".."):
            raise Stop(f"unsafe relative path: {rel}")
        current = current / part
        if not current.exists() and not current.is_symlink():
            raise Stop(f"frozen candidate path missing: {rel}")
        st = current.lstat()
        if current.is_symlink() or (getattr(st, "st_file_attributes", 0) & 0x400):
            raise Stop(f"symlink/reparse component rejected: {rel}")
        if not str(current.resolve(strict=True)).casefold().startswith((str(root_abs) + "\\").casefold()):
            raise Stop(f"path escapes candidate root: {rel}")
    return candidate


def check_config(runner: Runner, lane: str, root: Path) -> None:
    # Query only relevant key names/booleans; never capture remote URL credentials.
    fsmonitor = git(runner, lane, root, "fsmonitor-config", ["config", "--get", "core.fsmonitor"], (0, 1)).decode("utf-8", "replace").strip().lower()
    if fsmonitor not in ("", "false", "off", "no", "0"):
        raise Stop(f"core.fsmonitor is enabled/configured for {lane}")
    filter_keys = git(runner, lane, root, "filter-config-keys", ["config", "--name-only", "--get-regexp", r"^filter\."], (0, 1))
    configured_filter_keys = sorted({line.decode("utf-8", "strict").strip().lower() for line in filter_keys.splitlines() if line.strip()})
    if any(not key.startswith("filter.") for key in configured_filter_keys):
        raise Stop(f"unparseable filter configuration key listing for {lane}")
    if runner.evidence.current_lane is not None:
        runner.evidence.current_lane.setdefault("configured_filter_keys", {})[lane] = configured_filter_keys
    hookspath = git(runner, lane, root, "hookspath-config", ["config", "--get", "core.hooksPath"], (0, 1))
    if hookspath.strip():
        raise Stop(f"custom hooksPath detected for {lane}")
    sign = git(runner, lane, root, "signing-config", ["config", "--bool", "--get", "commit.gpgsign"], (0, 1))
    if sign.strip().lower() in (b"true", b"yes", b"on", b"1"):
        raise Stop(f"commit signing is enabled for {lane}")
    signing_keys = git(runner, lane, root, "signing-key-names", ["config", "--name-only", "--get-regexp", r"^(user\.signingkey|gpg\.program|gpg\.format)$"], (0, 1))
    if signing_keys.strip():
        raise Stop(f"signing configuration detected for {lane}")
    hooks_dir = git(runner, lane, root, "hooks-dir", ["rev-parse", "--git-path", "hooks"]).decode().strip()
    hook_path = Path(hooks_dir)
    if not hook_path.is_absolute():
        hook_path = root / hook_path
    if not hook_path.is_dir():
        raise Stop(f"effective hooks directory missing/unreadable for {lane}")
    active_hooks = [x.name for x in hook_path.iterdir() if x.is_file() and not x.name.endswith(".sample")]
    if active_hooks:
        raise Stop(f"active hook files detected: {active_hooks}; no hook bypass permitted")
    ident = git(runner, lane, root, "author-ident", ["var", "GIT_AUTHOR_IDENT"]).decode("utf-8", "strict").strip()
    git(runner, lane, root, "committer-ident", ["var", "GIT_COMMITTER_IDENT"])
    if not ident or " <" not in ident or "> " not in ident:
        raise Stop(f"invalid Git author identity for {lane}")


def effective_filter_paths(runner: Runner, lane: str, root: Path, paths: list[str], label: str) -> None:
    """Fail closed unless effective filter attributes are unset for tracked and approved paths."""
    unique = sorted(set(paths))
    for batch_start in range(0, len(unique), 64):
        batch = unique[batch_start:batch_start + 64]
        raw = git(
            runner, lane, root, f"{label}-{batch_start // 64 + 1}",
            ["check-attr", "-z", "filter", "--", *batch],
        )
        fields = raw.split(b"\0")
        if fields and fields[-1] == b"":
            fields.pop()
        if len(fields) % 3:
            raise Stop(f"malformed NUL check-attr output for {lane}:{label}")
        observed: dict[str, str] = {}
        for index in range(0, len(fields), 3):
            path = fields[index].decode("utf-8", "strict").replace("\\", "/")
            attribute = fields[index + 1].decode("ascii", "strict")
            value = fields[index + 2].decode("utf-8", "strict").strip().lower()
            if path not in batch or attribute != "filter" or path in observed:
                raise Stop(f"unexpected or duplicate check-attr record for {lane}:{label}")
            if value not in ("unspecified", "unset"):
                raise Stop(f"effective clean filter is active or unknown for {lane}:{path}")
            observed[path] = value
        if set(observed) != set(batch):
            raise Stop(f"check-attr omitted approved/tracked paths for {lane}:{label}")


def check_tree_effective_filters(runner: Runner, lane: str, root: Path, approved_paths: list[str]) -> None:
    tracked_raw = git(runner, lane, root, "tracked-paths-for-filter-check", ["ls-files", "-z"])
    tracked = [item.decode("utf-8", "strict").replace("\\", "/") for item in bytes_lines(tracked_raw)]
    effective_filter_paths(runner, lane, root, tracked + approved_paths, "effective-filter-attr")


def tree_entries(runner: Runner, lane: str, root: Path, rev: str, paths: list[str]) -> dict[str, tuple[str, str]]:
    out = git(runner, lane, root, f"tree-{rev[:8]}", ["ls-tree", "-r", "-z", "--full-tree", rev, "--", *paths])
    found: dict[str, tuple[str, str]] = {}
    for record in bytes_lines(out):
        meta, path_b = record.split(b"\t", 1)
        mode, kind, oid = meta.decode("ascii").split(" ")
        if kind != "blob":
            raise Stop(f"non-blob tree entry for {lane}")
        path = path_b.decode("utf-8", "strict").replace("\\", "/")
        found[path] = (mode, oid)
    return found


def raw_digest(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def verify_main_identity(runner: Runner, lane: str) -> tuple[str, str]:
    for label, args, expected in (
        ("main-root", ["rev-parse", "--show-toplevel"], MAIN),
        ("main-git-dir", ["rev-parse", "--git-dir"], MAIN / ".git"),
        ("main-common-dir", ["rev-parse", "--git-common-dir"], MAIN / ".git"),
    ):
        value = git(runner, lane, MAIN, label, args).decode("utf-8", "strict").strip()
        observed = Path(value)
        if not observed.is_absolute():
            observed = MAIN / observed
        if canonical(observed) != canonical(expected):
            raise Stop(f"main Git identity mismatch: {label}")
    branch = git(runner, lane, MAIN, "main-branch", ["symbolic-ref", "--short", "HEAD"]).decode().strip()
    if branch != "master":
        raise Stop(f"main worktree is not on master: {branch}")
    main_head = git(runner, lane, MAIN, "main-head", ["rev-parse", "HEAD"]).decode().strip()
    master_ref = git(runner, lane, MAIN, "main-master-ref", ["rev-parse", "refs/heads/master"]).decode().strip()
    if main_head != master_ref:
        raise Stop("main HEAD does not match refs/heads/master")
    if runner.evidence.current_lane is not None:
        runner.evidence.current_lane["main_head"] = main_head
        runner.evidence.current_lane["main_ref_head"] = master_ref
    return main_head, master_ref


def check_main_overlap(runner: Runner, candidate: dict) -> None:
    lane = candidate["lane"]
    paths = [item["path"] for item in candidate["files"]]
    main_head, master_ref = verify_main_identity(runner, lane)
    check_config(runner, lane, MAIN)
    check_tree_effective_filters(runner, lane, MAIN, paths)
    main_status = status_map(git(runner, lane, MAIN, "main-status", ["status", "--porcelain=v1", "-z", "--untracked-files=all"]))
    overlap = sorted(set(paths) & set(main_status))
    if overlap:
        raise Stop(f"main has dirty approved-scope paths for {lane}: {overlap}")
    for item in candidate["files"]:
        p = item["path"]
        attr = git(runner, lane, MAIN, "main-filter-attr", ["check-attr", "filter", "--", p]).decode("utf-8", "replace").rstrip()
        if not (attr.endswith(": filter: unspecified") or attr.endswith(": filter: unset")):
            raise Stop(f"main approved path has a custom clean filter: {p}")
    current = tree_entries(runner, lane, MAIN, "HEAD", paths)
    baseline = tree_entries(runner, lane, MAIN, BASE, paths)
    for item in candidate["files"]:
        p = item["path"]
        expected_main = item["main_current"]
        actual = current.get(p)
        if expected_main["present"]:
            if actual != (expected_main["mode"], expected_main["blob_oid"]):
                raise Stop(f"main HEAD path differs from frozen current blob: {p}")
        elif actual is not None:
            raise Stop(f"main HEAD unexpectedly contains candidate-only path: {p}")
        base = baseline.get(p)
        expected_base = item["baseline"]
        if expected_base["present"]:
            if base != (expected_base["mode"], expected_base["blob_oid"]):
                raise Stop(f"base path differs from frozen baseline: {p}")
        elif base is not None:
            raise Stop(f"base unexpectedly contains candidate-only path: {p}")
        live = MAIN.joinpath(*p.split("/"))
        cursor = MAIN
        for part in p.split("/"):
            cursor = cursor / part
            if cursor.is_symlink() or (cursor.exists() and (getattr(cursor.lstat(), "st_file_attributes", 0) & 0x400)):
                raise Stop(f"main approved path has symlink/reparse component: {p}")
        if expected_main["present"]:
            if not live.is_file() or not stat.S_ISREG(live.stat().st_mode) or (live.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)):
                raise Stop(f"main approved tracked path is missing: {p}")
            worktree_oid = git(runner, lane, MAIN, "main-clean-oid", ["hash-object", f"--path={p}", "--", p]).decode().strip()
            if worktree_oid != expected_main["blob_oid"]:
                raise Stop(f"main approved path worktree content differs from current tree: {p}")
        elif live.exists() or live.is_symlink():
            raise Stop(f"main has an untracked/ignored file at candidate-only path: {p}")


def check_lane(runner: Runner, manifest: dict, lane: str) -> list[str]:
    if runner.evidence.current_lane is not None:
        runner.evidence.current_lane["preflightchecks"]["candidate_git_identity"] = "in_progress"
    candidate = next(x for x in manifest["candidates"] if x["lane"] == lane)
    spec = LANES[lane]
    root = spec["root"]
    if canonical(root) != canonical(Path(candidate["root"])):
        raise Stop(f"candidate root identity changed: {lane}")
    for args, expected in (
        (["rev-parse", "--show-toplevel"], canonical(root)),
        (["rev-parse", "--git-dir"], canonical(spec["git_dir"])),
        (["rev-parse", "--git-common-dir"], canonical(MAIN / ".git")),
    ):
        observed = git(runner, lane, root, "identity", args).decode("utf-8", "strict").strip()
        observed_path = Path(observed)
        if not observed_path.is_absolute():
            observed_path = root / observed_path
        if canonical(observed_path) != expected:
            raise Stop(f"Git identity mismatch for {lane}: {args[1]}")
    check_config(runner, lane, root)
    candidate_paths = [item["path"] for item in candidate["files"]]
    check_tree_effective_filters(runner, lane, root, candidate_paths)
    verify_main_identity(runner, lane)
    check_config(runner, lane, MAIN)
    main_approved_paths = [item["path"] for entry in manifest["candidates"] for item in entry["files"]]
    check_tree_effective_filters(runner, lane, MAIN, main_approved_paths)
    head = git(runner, lane, root, "head", ["rev-parse", "HEAD"]).decode().strip()
    if head != BASE:
        raise Stop(f"candidate HEAD not frozen detached base: {lane}")
    if runner.evidence.current_lane is not None:
        runner.evidence.current_lane["head"] = head
        runner.evidence.current_lane["preflightchecks"]["candidate_head_base"] = "passed"
    tree_at_base = git(runner, lane, root, "base-tree", ["rev-parse", f"{BASE}^{{tree}}"])
    tree_at_base = tree_at_base.decode().strip()
    if runner.evidence.current_lane is not None:
        runner.evidence.current_lane["tree"] = tree_at_base
    branch = git(runner, lane, root, "branch", ["symbolic-ref", "-q", "HEAD"], (1,)).decode().strip()
    if branch:
        raise Stop(f"candidate is not detached: {lane}")
    index = git(runner, lane, root, "index", ["diff", "--no-ext-diff", "--cached", "--name-only", "-z"])
    if bytes_lines(index):
        raise Stop(f"candidate index is not empty: {lane}")
    statuses = status_map(git(runner, lane, root, "status", ["status", "--porcelain=v1", "-z", "--untracked-files=all"]))
    expected_status = {x["path"]: x["worktree_status"] for x in candidate["files"]}
    if statuses != expected_status:
        raise Stop(f"candidate status set differs from frozen manifest: {lane}")
    if runner.evidence.current_lane is not None:
        runner.evidence.current_lane["preflightchecks"]["exact_status_set"] = "passed"
    paths = sorted(expected_status)
    tracked = {x["path"]: (x["baseline"]["mode"], x["baseline"]["blob_oid"], "0") for x in candidate["files"] if x["baseline"]["present"]}
    index_entries: dict[str, tuple[str, str, str]] = {}
    if tracked:
        staged_inventory = git(runner, lane, root, "tracked-index-inventory", ["ls-files", "--stage", "-z", "--", *tracked])
        for record in bytes_lines(staged_inventory):
            meta, path_b = record.split(b"\t", 1)
            mode, oid, stage = meta.decode("ascii").split(" ")
            index_entries[path_b.decode("utf-8", "strict").replace("\\", "/")] = (mode, oid, stage)
    if index_entries != tracked:
        raise Stop(f"tracked index path/mode/OID inventory differs from frozen baseline: {lane}")
    if runner.evidence.current_lane is not None:
        runner.evidence.current_lane["preflightchecks"]["index_empty_and_tracked_inventory"] = "passed"
    for item in candidate["files"]:
        path = ensure_inside_no_reparse(root, item["path"])
        if raw_digest(path) != item["candidate_worktree_sha256"]:
            raise Stop(f"raw SHA256 changed: {lane}:{item['path']}")
        if not stat.S_ISREG(path.stat().st_mode) or (path.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)):
            raise Stop(f"candidate is not a regular non-executable file: {lane}:{item['path']}")
        if item["baseline"].get("mode") not in (None, "100644"):
            raise Stop(f"unexpected frozen baseline mode: {lane}:{item['path']}")
    for item in candidate["files"]:
        attr = git(runner, lane, root, "filter-attr", ["check-attr", "filter", "--", item["path"]]).decode("utf-8", "replace").rstrip()
        if not (attr.endswith(": filter: unspecified") or attr.endswith(": filter: unset")):
            raise Stop(f"path-specific clean filter is set: {lane}:{item['path']}")
    if runner.evidence.current_lane is not None:
        runner.evidence.current_lane["preflightchecks"]["hooks_filters_signing_identity"] = "passed"
    check_main_overlap(runner, candidate)
    for item in candidate["files"]:
        clean_oid = git(runner, lane, root, "clean-oid", ["hash-object", f"--path={item['path']}", "--", item["path"]]).decode().strip()
        if clean_oid != item["candidate_git_blob_oid"]:
            raise Stop(f"normal Git clean OID changed: {lane}:{item['path']}")
    cached = git(runner, lane, root, "ref-check", ["show-ref", "--verify", "--quiet", f"refs/heads/{spec['ref']}"], (1,))
    if cached:
        raise Stop(f"planned branch already exists: {lane}")
    if runner.evidence.current_lane is not None:
        runner.evidence.current_lane["preflightchecks"].update({
            "candidate_git_identity": "passed",
            "planned_ref_absent": "passed",
            "main_master_clean_scope_and_baselines": "passed",
            "raw_sha_and_clean_oids": "passed",
        })
    return paths


def check_ee5_gate(runner: Runner, lane: str) -> str:
    if lane not in ("SC10", "SC11"):
        return "not_applicable"
    # Current official query helper cannot read §三, where the freeze marker lives.
    # Log the supported query output for evidence, but never infer freeze state from §一.
    runner.run(f"{lane}-ee5-query-limited", [sys.executable, str(QUEUE_QUERY), "--digest", "--grep", "EE-5"], MAIN)
    return "unverifiable_by_official_query"


def check_authorization(path: Path, lane: str, paths: list[str]) -> None:
    if not path.is_absolute() or path.is_symlink() or normalized(path) != normalized(AUTHORIZATION):
        raise Stop("authorization path is not the registered formal consumption file")
    if normalized(Path(__file__)) != normalized(FORMAL_SCRIPT):
        raise Stop("--seal is allowed only from the registered formal script path")
    if FORMAL_PLAN.is_symlink() or not FORMAL_PLAN.is_file():
        raise Stop("registered formal plan is absent")
    if not path.is_file():
        raise Stop("registered human authorization file is absent")
    if sha256_file(MANIFEST) != MANIFEST_SHA256:
        raise Stop("frozen manifest changed before the first Git write")
    auth = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(auth, dict):
        raise Stop("authorization JSON root must be an object")
    required = {
        "schema": AUTH_SCHEMA,
        "decision": "approve",
        "approved_by": "Shao Peishen",
        "local_commit_exception": "native_detached_candidate_commit_preservation",
        "plan_sha256": sha256_file(FORMAL_PLAN),
        "script_sha256": sha256_file(Path(__file__)),
        "manifest_sha256": MANIFEST_SHA256,
        "base_commit": BASE,
    }
    for key, value in required.items():
        if auth.get(key) != value:
            raise Stop(f"authorization binding mismatch: {key}")
    if not auth.get("human_approval_evidence"):
        raise Stop("authorization lacks pointer to human approval evidence")
    lane_approvals = auth.get("lane_approvals")
    if not isinstance(lane_approvals, dict):
        raise Stop("authorization lane_approvals must be an object")
    approval = lane_approvals.get(lane)
    if not isinstance(approval, dict):
        raise Stop(f"authorization has no lane-specific approval for {lane}")
    for key, value in {"lane": lane, "ref": LANES[lane]["ref"], "paths": paths}.items():
        if approval.get(key) != value:
            raise Stop(f"authorization lane binding mismatch: {lane}.{key}")
    if lane in ("SC10", "SC11"):
        if approval.get("freeze_scope_exception") != "completed_candidate_preservation_only":
            raise Stop(f"EE-5 freeze exception is not approved for {lane}")
        if auth.get("ee5_root_operation_active") is not False:
            raise Stop("EE-5 root operation must be explicitly recorded inactive")
        binding = approval.get("ee5_status_binding")
        if not isinstance(binding, dict) or binding.get("status") not in ("not_started", "completed"):
            raise Stop(f"missing supported EE-5 status binding for {lane}")
        record = Path(binding.get("record_path", ""))
        if normalized(record) != normalized(EE5_STATUS_RECORD):
            raise Stop(f"EE-5 status record path is not the fixed root operation record for {lane}")
        resolved_record = record.resolve(strict=False)
        if not record.is_absolute() or record.is_symlink() or not record.is_file() or not str(resolved_record).casefold().startswith(str(MAIN.resolve()).casefold() + "\\"):
            raise Stop(f"EE-5 root operation record path is missing/outside main repository for {lane}")
        record_bytes = record.read_bytes()
        if sha256_bytes(record_bytes) != binding.get("record_sha256"):
            raise Stop(f"EE-5 root operation record SHA256 mismatch for {lane}")
        record_value = json.loads(record_bytes.decode("utf-8"))
        if not isinstance(record_value, dict):
            raise Stop(f"EE-5 root operation record must be a JSON object for {lane}")
        if record_value.get("status") != binding["status"] or record_value.get("ee5_root_operation_active") is not False:
            raise Stop(f"EE-5 record status/active flag does not match approved binding for {lane}")


def stage_verify(runner: Runner, manifest: dict, lane: str, paths: list[str]) -> None:
    candidate = next(x for x in manifest["candidates"] if x["lane"] == lane)
    root = LANES[lane]["root"]
    staged_names = bytes_lines(git(runner, lane, root, "staged-names", ["diff", "--cached", "--name-only", "-z"]))
    wanted_names = [p.encode("utf-8") for p in paths]
    if sorted(staged_names) != sorted(wanted_names):
        raise Stop(f"staged path set differs from exact whitelist for {lane}")
    out = git(runner, lane, root, "staged-tree", ["ls-files", "--stage", "-z", "--", *paths])
    staged: dict[str, tuple[str, str, str]] = {}
    for rec in bytes_lines(out):
        meta, path_b = rec.split(b"\t", 1)
        mode, oid, stage = meta.decode("ascii").split(" ")
        staged[path_b.decode("utf-8", "strict").replace("\\", "/")] = (mode, oid, stage)
    expected = {x["path"]: ("100644", x["candidate_git_blob_oid"], "0") for x in candidate["files"]}
    if staged != expected:
        raise Stop(f"staged paths/modes/OIDs differ from exact whitelist for {lane}")
    for item in candidate["files"]:
        if raw_digest(ensure_inside_no_reparse(root, item["path"])) != item["candidate_worktree_sha256"]:
            raise Stop(f"raw SHA changed after staging: {lane}:{item['path']}")
    git(runner, lane, root, "cached-check", ["diff", "--no-ext-diff", "--cached", "--check"])


def seal_one(runner: Runner, manifest: dict, lane: str, authorization: Path) -> None:
    candidate = next(x for x in manifest["candidates"] if x["lane"] == lane)
    paths = check_lane(runner, manifest, lane)
    check_ee5_gate(runner, lane)
    check_authorization(authorization, lane, paths)
    root = LANES[lane]["root"]
    ref = LANES[lane]["ref"]
    git(runner, lane, root, "switch-create", ["switch", "-c", ref, BASE])
    current_ref = git(runner, lane, root, "verify-current-ref", ["symbolic-ref", "--short", "HEAD"]).decode().strip()
    if current_ref != ref:
        raise Stop(f"created branch does not match approved ref: {lane}")
    if runner.evidence.current_lane is not None:
        runner.evidence.current_lane["ref"] = current_ref
        runner.evidence.current_lane["current_ref"] = current_ref
        runner.evidence.current_lane["head"] = git(runner, lane, root, "branch-head", ["rev-parse", "HEAD"]).decode().strip()
    git(runner, lane, root, "add-exact", ["add", "--", *paths])
    stage_verify(runner, manifest, lane, paths)
    # The commit is intentionally a normal Git commit: hooks and user identity remain enabled.
    git(runner, lane, root, "commit", ["-c", "maintenance.auto=false", "-c", "gc.auto=0", "commit", "-m", f"Seal {lane} candidate from frozen {BASE[:12]} inventory"])
    head = git(runner, lane, root, "verify-head", ["rev-parse", "HEAD"]).decode().strip()
    if runner.evidence.current_lane is not None:
        runner.evidence.current_lane["head"] = head
    parents = git(runner, lane, root, "verify-parents", ["rev-list", "--parents", "-n", "1", head]).decode().strip().split()
    if len(parents) != 2 or parents[0] != head or parents[1] != BASE:
        raise Stop(f"commit does not have exactly the frozen base as its sole parent: {lane}")
    parent = parents[1]
    tree = git(runner, lane, root, "verify-tree-oid", ["rev-parse", f"{head}^{{tree}}"]).decode().strip()
    if runner.evidence.current_lane is not None:
        runner.evidence.current_lane.update({"parent": parent, "tree": tree})
    delta = bytes_lines(git(runner, lane, root, "verify-commit-paths", ["diff-tree", "--no-ext-diff", "--no-commit-id", "--no-renames", "-r", "--name-only", "-z", BASE, head]))
    if sorted(delta) != sorted(p.encode("utf-8") for p in paths):
        raise Stop(f"commit changed paths outside or short of the exact whitelist: {lane}")
    entries = tree_entries(runner, lane, root, head, paths)
    wanted = {x["path"]: ("100644", x["candidate_git_blob_oid"]) for x in candidate["files"]}
    if entries != wanted:
        raise Stop(f"committed tree differs from exact frozen paths/OIDs: {lane}")
    status = status_map(git(runner, lane, root, "verify-status", ["status", "--porcelain=v1", "-z", "--untracked-files=all"]))
    if status:
        raise Stop(f"post-commit worktree is not clean: {lane}")
    if bytes_lines(git(runner, lane, root, "verify-index", ["diff", "--no-ext-diff", "--cached", "--name-only", "-z"])):
        raise Stop(f"post-commit index is not empty: {lane}")
    for item in candidate["files"]:
        if raw_digest(ensure_inside_no_reparse(root, item["path"])) != item["candidate_worktree_sha256"]:
            raise Stop(f"post-commit raw SHA changed: {lane}:{item['path']}")
    summary = runner.evidence.current_lane
    if summary is not None:
        summary.update({"head": head, "ref": ref, "parent": parent, "tree": tree, "actualexit": 0, "error": None})
        summary["preflightchecks"].update({"authorization_binding": "passed", "staged_exact_paths_modes_oids": "passed", "commit_parent_tree_paths": "passed", "post_commit_clean_and_raw_sha": "passed"})
        runner.evidence.write_summary()
    print(f"{lane}: sealed {head}; parent={parent}; exact paths verified")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true", help="explicit read-only preflight (default)")
    parser.add_argument("--seal", action="store_true", help="seal exactly one lane; requires external human authorization")
    parser.add_argument("--lane", choices=ORDER)
    parser.add_argument("--authorization", type=Path)
    args = parser.parse_args()
    if args.seal and (not args.lane or not args.authorization):
        parser.error("--seal requires exactly one --lane and --authorization")
    if not args.seal and args.authorization:
        parser.error("--authorization is valid only with --seal")
    if args.seal and args.preflight:
        parser.error("--seal and --preflight are mutually exclusive")
    evidence = Evidence()
    runner = Runner(evidence)
    try:
        # Reject Git redirection, config injection, and trace-file variables before any subprocess.
        check_git_environment(evidence)
        plan_path = selected_plan()
        if plan_path.is_symlink() or not plan_path.is_file():
            raise Stop(f"selected plan is missing or a symlink: {plan_path}")
        plan_sha = sha256_file(plan_path)
        (evidence.root / "run-binding.json").write_text(
            json.dumps({
                "mode": "seal" if args.seal else "preflight",
                "script_path": str(Path(__file__).resolve()),
                "script_sha256": sha256_file(Path(__file__)),
                "manifest_path": str(MANIFEST.resolve()),
                "manifest_sha256": sha256_file(MANIFEST),
                "plan_path": str(plan_path.resolve()),
                "plan_sha256": plan_sha,
                "base_commit": BASE,
                "draft_source_copy": normalized(Path(__file__)) != normalized(FORMAL_SCRIPT),
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        manifest = read_manifest()
        lanes = (args.lane,) if args.lane else ORDER
        for lane in lanes:
            evidence.begin_lane(lane)
            if args.seal:
                # seal_one performs fresh prechecks and validates the exact formal authorization before writing.
                seal_one(runner, manifest, lane, args.authorization)
                evidence.write_summary()
                continue
            paths = check_lane(runner, manifest, lane)
            freeze_check = check_ee5_gate(runner, lane)
            evidence.current_lane["preflightchecks"].update({"candidate_preflight": "passed", "freeze_check": freeze_check})
            evidence.current_lane["actualexit"] = 0
            evidence.write_summary()
            print(f"{lane}: preflight passed ({len(paths)} frozen paths); freeze_check={freeze_check}")
        print(f"Evidence: {evidence.root}")
        evidence.summary["actualexit"] = 0
        evidence.write_summary()
        return 0
    except (Stop, OSError, ValueError, json.JSONDecodeError) as exc:
        evidence.summary["actualexit"] = 2
        evidence.summary["error"] = str(exc)
        if evidence.current_lane is not None:
            evidence.current_lane["error"] = str(exc)
            evidence.current_lane["actualexit"] = 2
        evidence.write_summary()
        print(f"BLOCKED: {exc}\nEvidence: {evidence.root}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
