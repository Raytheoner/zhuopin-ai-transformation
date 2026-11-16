#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""OpenSpec 需求索引、四态和双轨构建门禁。

OpenSpec 1.7.0 的 validate 不执行 config.yaml 中的 rules.proposal；本工具在 CI
独立阻断机器可判的缺口。存量缺节只由精确包指纹 baseline 冻结；任何触碰均重新受守。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[1]
BASELINE_REL = Path("0-学习与工具/需求与变更包门禁lint-baseline.json")
INITIAL_LEGACY_SHA256 = "3aac21cdb3d9df66a93b760f15500ca7a60a50bb056778967e1075338eaa90fa"
INDEX_REL = Path("docs/requirements/INDEX.md")
CONFIG_REL = Path("openspec/config.yaml")
REGISTRY_REL = Path("1-转型规划/0-全景路线图/场景registry-规划倒逼扫描器.jsonl")
STATES = {"archive", "blocked_external", "frozen_by_prd", "active_mvp"}
MODES = {"feature", "refinement"}
PACKAGE_CODES = {"FEATURE_PROPOSAL", "FEATURE_ARTIFACTS", "REFINEMENT_DELTA", "REFINEMENT_TEST"}
CHECKBOX = re.compile(r"^\s*[-*]\s+\[([ xX])\]", re.M)
DELTA_HEADER = re.compile(r"^##\s+(?:ADDED|MODIFIED|REMOVED|RENAMED) Requirements\s*$", re.M)


class Finding(NamedTuple):
    code: str
    subject: str
    detail: str


def package_fingerprint(folder: Path) -> str:
    """对包的全部普通文件取稳定指纹；文本行尾归一化以兼容 Windows CI。"""
    digest = hashlib.sha256()
    for path in sorted(p for p in folder.rglob("*") if p.is_file()):
        rel = path.relative_to(folder).as_posix()
        data = path.read_bytes()
        if path.suffix.lower() in {".md", ".yaml", ".yml", ".json", ".txt"}:
            data = data.replace(b"\r\n", b"\n")
        digest.update(rel.encode("utf-8") + b"\0" + data + b"\0")
    return digest.hexdigest()


def _section_rows(text: str, heading: str) -> list[list[str]]:
    marker = re.search(rf"^##\s+{re.escape(heading)}[^\n]*$", text, re.M)
    if not marker:
        return []
    tail = text[marker.end():]
    next_heading = re.search(r"^##\s+", tail, re.M)
    section = tail[:next_heading.start()] if next_heading else tail
    result = []
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip().strip("`").strip() for cell in line.strip().strip("|").split("|")]
        if not cells or all(re.fullmatch(r":?-+:?", cell) for cell in cells):
            continue
        if cells[0] in {"能力/场景ID", "变更包名", "场景ID"}:
            continue
        result.append(cells)
    return result


def _safe_file(root: Path, value: str) -> bool:
    if not value or value == "—":
        return False
    rel = Path(value)
    if rel.is_absolute() or ".." in rel.parts:
        return False
    resolved = (root / rel).resolve()
    return resolved.is_relative_to(root.resolve()) and resolved.is_file()


def _has_content_under(text: str, heading: str) -> bool:
    match = re.search(rf"^##\s+{re.escape(heading)}[^\n]*\n(.*?)(?=^##\s+|\Z)",
                      text, re.M | re.S)
    if not match:
        return False
    body = re.sub(r"<!--.*?-->", "", match.group(1), flags=re.S).strip()
    return len(body) >= 15 and not re.fullmatch(r"(?:TODO|TBD|待补)[\s。.!！]*", body, re.I)


def _feature_missing(folder: Path, department: str) -> list[Finding]:
    result = []
    files = ("proposal.md", "design.md", "tasks.md")
    delta_files = list((folder / "specs").glob("*/spec.md"))
    if any(not (folder / name).is_file() for name in files) or not delta_files:
        result.append(Finding("FEATURE_ARTIFACTS", folder.name,
                              "feature 需要 proposal/design/specs delta/tasks 完整产物"))
    proposal = folder / "proposal.md"
    if not proposal.is_file():
        return result
    text = proposal.read_text(encoding="utf-8", errors="replace")
    knowledge = _has_content_under(text, "知识资产三问")
    tier = _has_content_under(text, "验收与晋档条件")
    ignore = ".gitignore" in text and ("git check-ignore" in text or
                                      "不新增" in text or "不适用" in text)
    guard = department != "机制/平台" or bool(re.search(r"守卫.{0,80}退休|退休.{0,80}守卫", text, re.S))
    if not (knowledge and tier and ignore and guard):
        missing = [label for label, okay in (("知识资产三问", knowledge), ("验收与晋档条件", tier),
                                            (".gitignore", ignore), ("机制守卫退休", guard)) if not okay]
        result.append(Finding("FEATURE_PROPOSAL", folder.name, "缺 MANDATORY：" + "、".join(missing)))
    return result


def _refinement_missing(folder: Path, spec_tests: dict[str, str], root: Path) -> list[Finding]:
    deltas = list((folder / "specs").glob("*/spec.md"))
    if not deltas or any(not DELTA_HEADER.search(p.read_text(encoding="utf-8", errors="replace"))
                         for p in deltas):
        return [Finding("REFINEMENT_DELTA", folder.name, "refinement 缺有效 specs/ delta")]
    missing_tests = [p.parent.name for p in deltas
                     if p.parent.name not in spec_tests or
                     not _safe_file(root, spec_tests[p.parent.name]) or
                     Path(spec_tests[p.parent.name]).name == "test_scaffold.py"]
    if missing_tests:
        return [Finding("REFINEMENT_TEST", folder.name,
                        "delta 缺对应真实 pytest：" + "、".join(missing_tests))]
    return []


def _legal_hold(folder: Path) -> bool:
    text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in
                     (folder / "intent.md", folder / "proposal.md", folder / "design.md",
                      folder / "tasks.md") if p.is_file())
    return bool(re.search(r"暂不归档\s*[:：]\s*\S", text) or
                re.search(r"预期观察窗口\s*[:：]\s*\d+\s*天", text) or
                re.search(r"🟡.{0,30}未做[·、].{0,30}(?:已停手|已交看护者)", text))


def _config_findings(root: Path) -> list[Finding]:
    path = root / CONFIG_REL
    if not path.is_file():
        return [Finding("INPUT_MISSING", str(CONFIG_REL), "config.yaml 不存在")]
    text = path.read_text(encoding="utf-8", errors="replace")
    modes = re.search(r"^modes:\s*$([\s\S]*?)(?=^[^\s#][^\n]*:|\Z)", text, re.M)
    section = modes.group(1) if modes else ""
    found = set()
    for name in MODES:
        block = re.search(rf"^  {name}:\s*$([\s\S]*?)(?=^  [a-z_]+:|\Z)", section, re.M)
        required = ({"intent", "proposal", "design", "specs", "tasks", "pytest"}
                    if name == "feature" else {"proposal", "specs", "tasks", "pytest"})
        requires = re.search(r"^    requires:\s*(.+)$", block.group(1), re.M) if block else None
        if (block and re.search(rf"^    mode:\s*{name}\s*$", block.group(1), re.M)
                and requires and all(word in requires.group(1).lower() for word in required)):
            found.add(name)
    findings = []
    if found != MODES:
        findings.append(Finding("CONFIG_MODES", str(CONFIG_REL),
                                "须有 feature/refinement 的 mode 定义及完整 requires 链"))
    rules = re.search(r"^rules:\s*$([\s\S]*?)(?=^[^\s#][^\n]*:|\Z)", text, re.M)
    proposal = (re.search(r"^  proposal:\s*$([\s\S]*?)(?=^  [a-z_]+:|\Z)",
                          rules.group(1), re.M) if rules else None)
    body = ("\n".join(line for line in proposal.group(1).splitlines()
                      if not line.lstrip().startswith("#")) if proposal else "")
    required = ("MANDATORY", "知识资产三问", "验收与晋档条件",
                "退休哪一个既有守卫", ".gitignore", "intent.md",
                "docs/codex/rules/场景建造与合规.md")
    missing = [marker for marker in required if marker not in body]
    if missing:
        findings.append(Finding("CONFIG_MANDATORY", str(CONFIG_REL),
                                "rules.proposal 缺既有强制口径：" + "、".join(missing)))
    return findings


def _load_baseline(root: Path) -> tuple[dict, list[Finding]]:
    path = root / BASELINE_REL
    if not path.is_file():
        return {}, [Finding("INPUT_MISSING", str(BASELINE_REL), "baseline 缺失，拒绝静默放行")]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if (data.get("schema_version") != 1 or not isinstance(data.get("legacy"), dict)
                or not isinstance(data.get("initial_legacy"), dict)):
            raise ValueError("schema_version/initial_legacy/legacy 无效")
        initial = data["initial_legacy"]
        if root.resolve() == ROOT.resolve():
            canonical = json.dumps(initial, sort_keys=True, ensure_ascii=False,
                                   separators=(",", ":")).encode("utf-8")
            if hashlib.sha256(canonical).hexdigest() != INITIAL_LEGACY_SHA256:
                return data["legacy"], [Finding("BASELINE_GROWTH", str(BASELINE_REL),
                                                "initial_legacy 初始锚点不可改写；只允许缩减 legacy")]
        growth = [name for name, record in data["legacy"].items()
                  if name not in initial or not set(record.get("missing", [])).issubset(
                      set(initial.get(name, [])))]
        if growth:
            return data["legacy"], [Finding("BASELINE_GROWTH", str(BASELINE_REL),
                                            "不得新增存量豁免：" + "、".join(sorted(growth)))]
        return data["legacy"], []
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return {}, [Finding("INPUT_MISSING", str(BASELINE_REL), f"baseline 无法解析：{exc}")]


def reviewed_change_states(root: Path) -> dict[str, dict]:
    """Reuse the original triage evidence; any mismatch removes managed status.

    This is not an ACK: all package files and the current INDEX must still match.
    Completed packages always retain their independent archive gate.
    """
    index = (root / INDEX_REL).read_text(encoding="utf-8")
    rows = _section_rows(index, "表二：在途变更包四态表")
    counts = Counter(c[0] for c in rows if len(c) == 6)
    records = json.loads((root / "reports/openspec-triage-20261113.json").read_text(encoding="utf-8"))["changes"]
    names = Counter(record["name"] for record in records)
    indexed = {c[0]: c for c in rows if len(c) == 6}
    result = {}
    for record in records:
        name = record["name"]
        cells = indexed.get(name)
        folder = root / "openspec/changes" / name
        if (not cells or counts[name] != 1 or names[name] != 1
                or Path(name).name != name or not folder.is_dir() or folder.is_symlink()
                or cells[3] not in {"frozen_by_prd", "blocked_external"}
                or cells[3] != record.get("state") or cells[4] != record.get("tasks_progress")
                or not record.get("reason") or not record.get("queue_pointers")
                or not all(re.fullmatch(r"#[1-9]\d*", p) and p in cells[5]
                           for p in record["queue_pointers"])
                or record.get("reviewed_fingerprint") != package_fingerprint(folder)):
            continue
        checks = CHECKBOX.findall((folder / "tasks.md").read_text(encoding="utf-8"))
        done = sum(c.lower() == "x" for c in checks)
        if not checks or done == len(checks) or cells[4] != f"{done}/{len(checks)}":
            continue
        result[name] = {"state": cells[3], "pointers": record["queue_pointers"],
                        "reason": record["reason"]}
    return result


def planning_findings(root: Path, index: str) -> list[Finding]:
    """Registry -> INDEX -> original queue, without declaring business acceptance."""
    records = [json.loads(line) for line in (root / REGISTRY_REL).read_text(encoding="utf-8").splitlines()
               if line.strip() and not line.lstrip().startswith("//")]
    rows = _section_rows(index, "表三：全景规划与原队列承接")
    valid = [r for r in rows if len(r) == 5]
    indexed = {r[0]: r for r in valid}
    findings = [Finding("PLAN_ROUTE", str(INDEX_REL), "表三列数须为5") for r in rows if len(r) != 5]
    duplicates = [k for k, n in Counter(r[0] for r in valid).items() if n > 1]
    findings.extend(Finding("PLAN_ROUTE", k, "全景承接重复") for k in duplicates)
    for record in records:
        if record.get("retired"):
            continue
        code = record["code"]
        row = indexed.get(code)
        if not row:
            findings.append(Finding("PLAN_ROUTE", code, "缺全景规划承接行"))
            continue
        _, domain, month, route, boundary = row
        if (domain != record.get("domain") or month != record.get("planned_month", "—")
                or not re.search(r"#[1-9]\d*", route)
                or (record.get("suspended") and record["suspended"] not in boundary)
                or (record.get("start_condition") and record["start_condition"] not in boundary)
                or not boundary.strip() or boundary == "—"):
            findings.append(Finding("PLAN_ROUTE", code, "域/排期/原队列/暂缓与验收边界不完整或漂移"))
    return findings


def planning_source_findings(root: Path) -> list[Finding]:
    """Reuse the original planning parser; compare actual month/domain cells.

    Old registry lint checks code presence only. A code in a different month,
    or in a historical parenthesis, cannot validate the current schedule.
    """
    source = ROOT / "0-学习与工具/工具-规划倒逼扫描器.py"
    spec = importlib.util.spec_from_file_location("_requirements_original_plan", source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    try:
        scenarios = module.load_registry(root)
        table = module._plan_table_rows(root)
        errors = []
        for sc in scenarios:
            if sc.retired:
                continue
            col = module.DOMAIN_COLUMNS[sc.domain][0]
            months = re.findall(r"\d{4}-\d{2}", sc.planned_month)
            # FI1's explicit suspension is not a scheduled restart date.
            if "暂缓" in sc.planned_month:
                continue
            for month in months:
                matches = [cells[col] for cells in table
                           if len(cells) > col and month == cells[0].strip("* ")
                           and module._alias_hits(sc.aliases, module._BRACKET_NOTE_RE.sub("", cells[col]))]
                if not matches:
                    errors.append(Finding("PLAN_SOURCE", sc.code, f"权威表 {month}/{sc.domain} 无本场景"))
                elif any("不构成承诺" in cell for cell in matches):
                    index = (root / INDEX_REL).read_text(encoding="utf-8")
                    row = next((r for r in _section_rows(index, "表三：全景规划与原队列承接")
                                if len(r) == 5 and r[0] == sc.code), [])
                    if not row or "不构成承诺" not in row[4] or "前置到位" not in row[4]:
                        errors.append(Finding("PLAN_SOURCE", sc.code, "权威条件位被误写为无条件承诺"))
        return errors
    except (OSError, ValueError, KeyError) as exc:
        return [Finding("PLAN_SOURCE", "权威规划", str(exc))]


def check_repository(root: Path) -> list[Finding]:
    root = root.resolve()
    findings = _config_findings(root)
    legacy, base_errors = _load_baseline(root)
    findings.extend(base_errors)
    index_path = root / INDEX_REL
    if not index_path.is_file():
        return findings + [Finding("INPUT_MISSING", str(INDEX_REL), "INDEX.md 缺失")]
    index_text = index_path.read_text(encoding="utf-8", errors="replace")
    spec_rows = _section_rows(index_text, "表一：能力与主规格索引")
    change_rows = _section_rows(index_text, "表二：在途变更包四态表")
    if not spec_rows or not change_rows:
        return findings + [Finding("INDEX_FORMAT", str(INDEX_REL), "两张表须存在且包含数据行")]
    registry_path = root / REGISTRY_REL
    if not registry_path.is_file():
        findings.append(Finding("INPUT_MISSING", str(REGISTRY_REL), "场景 registry 缺失"))
    else:
        pool = {cells[0] for cells in spec_rows if len(cells) == 6}
        try:
            findings.extend(planning_findings(root, index_text))
            for line in registry_path.read_text(encoding="utf-8").splitlines():
                if not line.strip() or line.lstrip().startswith("//"):
                    continue
                code = json.loads(line)["code"]
                if code not in pool:
                    findings.append(Finding("SCENE_NOT_IN_POOL", code, "registry 场景须先登记 INDEX"))
        except (ValueError, KeyError, TypeError) as exc:
            findings.append(Finding("INDEX_FORMAT", str(REGISTRY_REL), f"registry 无法解析：{exc}"))
    spec_tests: dict[str, str] = {}
    indexed_specs = set()
    for cells in spec_rows:
        if len(cells) != 6:
            findings.append(Finding("INDEX_FORMAT", str(INDEX_REL), "表一列数不为 6"))
            continue
        cap, _, _, spec, test, status = cells
        # New capability deltas may precede their main-spec sync. Their actual
        # isolated candidate tests still need an explicit indexed mapping.
        if spec == "—" and test != "—" and "候选delta" in status:
            spec_tests.setdefault(cap, test)
        if spec != "—":
            if not re.fullmatch(r"openspec/specs/[^/]+/spec\.md", spec):
                findings.append(Finding("INDEX_SPEC_PATH", cap, spec))
            elif not _safe_file(root, spec):
                findings.append(Finding("INDEX_SPEC_MISSING", cap, spec))
            else:
                indexed_specs.add(spec)
                spec_tests.setdefault(Path(spec).parent.name, test)
        if test != "—":
            candidate_test = (test.startswith("reports/") and "/candidate/tests/" in test
                              and "候选delta" in status)
            if (not (test.startswith(("0-学习与工具/", "4-数字员工/", "5-平台底座/")) or candidate_test)
                    or not Path(test).name.startswith("test_") or Path(test).suffix != ".py"):
                findings.append(Finding("INDEX_TEST_PATH", cap, test))
            elif not _safe_file(root, test):
                findings.append(Finding("INDEX_TEST_MISSING", cap, test))
        if spec != "—" and test == "—" and "存量待补" not in status:
            findings.append(Finding("INDEX_TEST_MISSING", cap, "已建主规格缺测试路径"))
    for spec in sorted((root / "openspec/specs").glob("*/spec.md")):
        rel = spec.relative_to(root).as_posix()
        if rel not in indexed_specs:
            findings.append(Finding("INDEX_SPEC_UNLISTED", spec.parent.name, rel))
    indexed_changes: dict[str, list[str]] = {}
    active = Counter()
    for cells in change_rows:
        if len(cells) != 6:
            findings.append(Finding("INDEX_FORMAT", str(INDEX_REL), "表二列数不为 6"))
            continue
        name, department, mode, state, progress, _ = cells
        if name in indexed_changes:
            findings.append(Finding("INDEX_DUPLICATE", name, "变更包重复登记"))
        indexed_changes[name] = cells
        if mode not in MODES or state not in STATES:
            findings.append(Finding("INDEX_STATE", name, f"非法 mode/state：{mode}/{state}"))
        if not re.fullmatch(r"\d+/\d+", progress):
            findings.append(Finding("INDEX_PROGRESS", name, progress))
        if state == "active_mvp":
            active[department] += 1
    business_total = sum(count for dept, count in active.items() if dept != "机制/平台")
    if business_total > 20 or active["机制/平台"] > 10 or any(
        count > 5 for dept, count in active.items() if dept != "机制/平台"
    ):
        findings.append(Finding("ACTIVE_LIMIT", str(INDEX_REL),
                                f"业务 {business_total}/20，机制 {active['机制/平台']}/10，部门上限 5"))
    changes_root = root / "openspec/changes"
    if not changes_root.is_dir():
        return findings + [Finding("INPUT_MISSING", "openspec/changes", "变更包目录缺失")]
    for folder in sorted(changes_root.iterdir()):
        if not folder.is_dir() or folder.name == "archive":
            continue
        name = folder.name
        cells = indexed_changes.get(name)
        if not cells:
            findings.append(Finding("CHANGE_NOT_INDEXED", name, "propose 前须登记 INDEX"))
            continue
        _, department, mode, state, progress, _ = cells
        if state == "archive":
            findings.append(Finding("INDEX_STATE", name, "包仍在活跃目录却标 archive"))
        tasks = folder / "tasks.md"
        checks = CHECKBOX.findall(tasks.read_text(encoding="utf-8", errors="replace")) if tasks.is_file() else []
        done = sum(c.lower() == "x" for c in checks)
        if progress != f"{done}/{len(checks)}":
            findings.append(Finding("INDEX_PROGRESS", name,
                                    f"索引 {progress}；实际 {done}/{len(checks)}"))
        if checks and done == len(checks) and not _legal_hold(folder):
            findings.append(Finding("UNARCHIVED_COMPLETE", name, "N/N 且无合法暂缓标记"))
        if mode not in MODES:
            continue
        raw = (_feature_missing(folder, department) if mode == "feature" else
               _refinement_missing(folder, spec_tests, root))
        base = legacy.get(name)
        exact_legacy = (isinstance(base, dict) and
                        base.get("fingerprint") == package_fingerprint(folder) and
                        set(base.get("missing", [])) == {item.code for item in raw})
        if not exact_legacy:
            findings.extend(raw)
    return findings


def queue_route_findings(root: Path, execute=subprocess.run) -> list[Finding]:
    """Only the supported query reads queues, including legitimate archived rows."""
    text = (root / INDEX_REL).read_text(encoding="utf-8")
    rows = _section_rows(text, "表三：全景规划与原队列承接")
    numbers = sorted({n for row in rows if len(row) == 5
                      for n in re.findall(r"#([1-9]\d*)", row[3])}, key=int)
    errors = []
    for number in numbers:
        try:
            p = execute([sys.executable, str(ROOT / "0-学习与工具/工具-队列查询.py"),
                         "--row", number, "--section", "一", "--include-archive", "--format", "json"],
                        cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=90)
            record = json.loads(p.stdout)
            if (p.returncode or not record.get("found") or record.get("error")
                    or record.get("read_errors") != [] or str(record.get("row")) != number):
                raise ValueError("原队列行未核实")
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            errors.append(Finding("PLAN_QUEUE_LINK", "#" + number, str(exc)))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enforce", action="store_true")
    parser.add_argument("--verify-queue-links", action="store_true", help="经原队列查询逐行核表三指针")
    parser.add_argument("--repo-root", type=Path, default=ROOT, help="仅供隔离测试")
    args = parser.parse_args(argv)
    issues = check_repository(args.repo_root)
    if args.verify_queue_links:
        issues.extend(queue_route_findings(args.repo_root))
        issues.extend(planning_source_findings(args.repo_root))
    for item in issues:
        print(f"{item.code}: {item.subject}: {item.detail}")
    print(f"需求与变更包门禁：{len(issues)} 项问题")
    if any(item.code == "INPUT_MISSING" for item in issues):
        return 2
    return 1 if args.enforce and issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
