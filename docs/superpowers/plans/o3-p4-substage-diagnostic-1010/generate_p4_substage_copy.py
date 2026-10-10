#!/usr/bin/env python3
"""Prepare (never execute) an stderr-instrumented O3 status-card copy."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import subprocess
import uuid
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
STATE_SHA = "BC774E0C9965BE22981390AF7B3255525C87B07038ECB87E2CAB46FDF34A35DF"
TEST_SHA = "4990DDB836775D92DA18FC41998271FA77DDC5AF2BFCE305D30A18A77DAFB360"
RUNS_REL = Path("reports/o3-fourth-ci-1010/runs")
PREVIOUS_TIMED_OUT_RUN = "16ec8e3f9f3d4daab2218aad0ff1aee2"
DIAGNOSTIC_GENERATION = "p4-substage-v1"
EXPECTED_MARKERS = [
    "P0", "P1", "P2", "P3", "P4", "P4_READ_DONE", "P4_PARSE_START",
    "P4_PARSE_DONE", "P4_CLASSIFY_DONE", "P4_AGGREGATE_DONE", "P5", "P6", "P7",
]

# Reviewed exact CRLF/LF-only pair for this one closure module.
CLOSURE_EOL_PAIR = {
    Path("5-平台底座/zhuopin_platform/zhuopin_platform/__init__.py"): (
        "E76FDE183BF790D6CB3462FA0E90F334060C97426CA9F30152CC6738C4288D63",
        "E7BA40C8B09F5839D2189DDF1EE6372E6FA7EB435DD1CA2C4E902082E9F86621",
    ),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip()


def assert_ignored(path: Path) -> None:
    relative = path.resolve().relative_to(REPO.resolve()).as_posix()
    subprocess.run(
        ["git", "-C", str(REPO), "check-ignore", "--quiet", "--", relative],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def marker(label: str) -> str:
    suffix = ""
    if label == "P0":
        suffix = " + '|ps=' + $PSVersionTable.PSVersion.ToString()"
    elif label == "P3":
        suffix = " + '|py=' + $pyExe"
    return (
        "[Console]::Error.WriteLine('O3_DIAG|"
        + label
        + "|utc=' + [DateTime]::UtcNow.ToString('o') + '|pid=' + $PID"
        + suffix
        + ")"
    )


def instrument(text: str) -> str:
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)
    anchors: list[tuple[str, object]] = [
        ("P0", re.compile(r"^\s*\$root\s*=\s*'C:\\Dev\\zhuopin-ai'\s*$")),
        ("P1", re.compile(r"^\s*\$queue=Get-Content -LiteralPath \$pq -Raw -Encoding UTF8\s*$")),
        ("P2", re.compile(r"^\s*foreach\(\$hl in @\(Get-Content -LiteralPath \$of\.FullName")),
        ("P3", re.compile(r"^\s*\$pyOut=@\(& \$pyExe @pyArgs 2>&1 \| ForEach-Object \{ \"\$_\" \}\); \$pyRc=\$LASTEXITCODE\s*$")),
        ("P4", re.compile(r"^\s*\$sl=Get-Content -LiteralPath \$sp -Encoding UTF8\s*$")),
        ("P5", re.compile(r"^\$gl=@\(\); \$gitWhy=''\s*$")),
        ("P6", re.compile(r"^\$ips=@\(\); \$ipsWhy=''; try\{ \$ips=@\(Get-NetIPAddress")),
        ("P7", re.compile(r"^Write-Output \('\@\@JSON\@\@' \+ \(ConvertTo-Json \$out -Compress -Depth 8\)\)\s*$")),
        ("P4_READ_DONE", re.compile(r"^\s*\$sweep=\(\(\$sl\|Select-Object -Last 6\) -join \"`n\"\)\s*$")),
        ("P4_PARSE_START", re.compile(r"^  foreach\(\$ln in \$sl\)\{\s*$")),
        ("P4_PARSE_DONE", re.compile(r"^  if\(\$null -ne \$ct\)\{ \$rr\.Add\(\[pscustomobject\]@\{ts=\$ct;body=\$cb\}\) \}\s*$")),
        ("P4_CLASSIFY_DONE", re.compile(r"^  \$mk=\{ param\(\$s\) \$o=\[ordered\]@\{\}; foreach\(\$k in @\('落库','空转','让路','锁忙','推送失败','其他'\)\)\{ \$c=@\(\$s\|Where-Object\{\$_.kind -eq \$k\}\)\.Count; if\(\$c -gt 0\)\{\$o\[\$k\]=\$c\} \}; \$o \}\s*$")),
        ("P4_AGGREGATE_DONE", re.compile(r"^  \$sstat=\[ordered\]@\{ total=\$ks\.Count; last=\$L\.kind;.*$")),
    ]
    found: dict[str, int] = {}
    for label, pattern in anchors:
        matches = [i for i, line in enumerate(lines) if pattern.search(line.rstrip("\r\n"))]
        if len(matches) != 1:
            raise RuntimeError(f"Anchor {label} matched {len(matches)} lines; refuse generation")
        found[label] = matches[0]
    if len(set(found.values())) != len(found):
        raise RuntimeError("Multiple phases resolved to the same source line")
    for label, line_no in sorted(found.items(), key=lambda item: item[1], reverse=True):
        original = lines[line_no]
        prefix = original[: len(original) - len(original.lstrip())]
        marker_line = prefix + marker(label) + newline
        if label == "P7":
            if not original.endswith(("\n", "\r")):
                lines[line_no] = original + newline
            lines.insert(line_no + 1, marker_line)
        elif label == "P4_READ_DONE":
            # Insert before the preview-construction anchor: Get-Content has completed.
            lines.insert(line_no, marker_line)
        elif label in {"P4_PARSE_DONE", "P4_CLASSIFY_DONE", "P4_AGGREGATE_DONE"}:
            lines.insert(line_no + 1, marker_line)
        else:
            lines.insert(line_no, marker_line)
    return "".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-root", type=Path, default=CANDIDATE)
    args = parser.parse_args()
    candidate = args.candidate_root.resolve()
    if run_git(candidate, "rev-parse", "HEAD") != EXPECTED_HEAD:
        raise SystemExit("Candidate HEAD mismatch; refuse generation")

    source_path = candidate / STATE_REL
    test_path = candidate / TEST_REL
    source_raw = source_path.read_bytes()
    test_raw = test_path.read_bytes()
    closure_raw = {relative: (candidate / relative).read_bytes() for relative in IMPORT_CLOSURE_RELS}
    if sha256(source_raw) != STATE_SHA or sha256(test_raw) != TEST_SHA:
        raise SystemExit("Candidate source/test SHA mismatch; refuse generation")
    for relative, expected in ((STATE_REL, STATE_SHA), (TEST_REL, TEST_SHA)):
        if sha256((REPO / relative).read_bytes()) != expected:
            raise SystemExit(f"Main-tree source mismatch for {relative}; refuse generation")
    for relative, data in closure_raw.items():
        main_raw = (REPO / relative).read_bytes()
        exact_pair = CLOSURE_EOL_PAIR.get(relative)
        if exact_pair is None:
            if sha256(main_raw) != sha256(data):
                raise SystemExit(f"Candidate and main-tree import-closure file differs: {relative}")
        elif (sha256(data), sha256(main_raw)) != exact_pair:
            raise SystemExit(f"Reviewed exact EOL pair changed: {relative}")
        elif data.replace(b"\r\n", b"\n") != main_raw.replace(b"\r\n", b"\n"):
            raise SystemExit(f"Reviewed module differs beyond CRLF/LF: {relative}")

    source_text = source_raw.decode("utf-8-sig")
    instrumented = instrument(source_text)
    bom = source_raw.startswith(b"\xef\xbb\xbf")
    encoded = (b"\xef\xbb\xbf" if bom else b"") + instrumented.encode("utf-8")
    run_id = uuid.uuid4().hex
    if run_id == PREVIOUS_TIMED_OUT_RUN:
        raise SystemExit("Generated UUID collides with the consumed diagnostic; refuse reuse")
    relative_run = RUNS_REL / run_id
    run_dir = REPO / relative_run
    diagnostic_state_rel = Path("0-学习与工具/工具-项目状态卡数据层.ps1")
    assert_ignored(run_dir / diagnostic_state_rel)
    for relative in IMPORT_CLOSURE_RELS:
        assert_ignored(run_dir / relative)
    assert_ignored(run_dir / "source-manifest.json")
    assert_ignored(run_dir / "markers.diff")
    run_dir.mkdir(parents=True, exist_ok=False)

    output = run_dir / diagnostic_state_rel
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(encoded)
    for relative, data in closure_raw.items():
        target = run_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    diff = "".join(
        difflib.unified_diff(
            source_text.splitlines(keepends=True),
            instrumented.splitlines(keepends=True),
            fromfile="candidate-original.ps1",
            tofile="diagnostic-copy.ps1",
        )
    )
    additions = [line for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")]
    deletions = [line for line in diff.splitlines() if line.startswith("-") and not line.startswith("---")]
    added_labels = [
        match.group(1)
        for line in additions
        if (match := re.search(r"\[Console\]::Error\.WriteLine\('O3_DIAG\|([^|]+)\|", line))
    ]
    if (
        deletions
        or len(additions) != len(EXPECTED_MARKERS)
        or len(added_labels) != len(additions)
        or added_labels != EXPECTED_MARKERS
    ):
        raise SystemExit("Diff must contain zero deletions and exactly one insertion for each ordered expected marker")
    (run_dir / "markers.diff").write_text(diff, encoding="utf-8", newline="")
    manifest = {
        "candidate_root": str(candidate),
        "candidate_head": EXPECTED_HEAD,
        "main_root": str(REPO),
        "state_card_relative_path": STATE_REL.as_posix(),
        "diagnostic_copy_relative_path": diagnostic_state_rel.as_posix(),
        "state_card_source_sha256": STATE_SHA,
        "test_node_relative_path": TEST_REL.as_posix(),
        "test_node_sha256": TEST_SHA,
        "reviewed_eol_identity_pairs": {relative.as_posix(): {"candidate_sha256": pair[0], "main_sha256": pair[1]} for relative, pair in CLOSURE_EOL_PAIR.items()},
        "p3_import_closure": [
            {"relative_path": relative.as_posix(), "sha256": sha256(data)}
            for relative, data in closure_raw.items()
        ],
        "diagnostic_copy_sha256": sha256(encoded),
        "run_id": run_id,
        "run_dir": str(run_dir),
        "diagnostic_generation": DIAGNOSTIC_GENERATION,
        "predecessor_timed_out_run_id": PREVIOUS_TIMED_OUT_RUN,
        "stdout_contract": "@@JSON@@ + compressed JSON; unmodified",
        "markers": EXPECTED_MARKERS,
        "execution_state": "prepared",
    }
    (run_dir / "source-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"run_dir": str(run_dir), "diagnostic_copy": str(output), "copy_sha256": manifest["diagnostic_copy_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
