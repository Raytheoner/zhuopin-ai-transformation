"""跟进信 README 已闭环归档迁移工具（`followup-readme-phase2` D2，队列 §一 `#490`）。

## 判据（正本＝派单件 §二 与 `followup-readme-archive` spec）

一行 SHALL 被迁移，当且仅当：①「发送状态」列（归一化后）以 `📥 已回件并回灌`
或 `❌ 已作废` 开头；②「日期」列（派单件原文「发送日」——信最初登记/发出的
日期）距运行时刻已超过 30 天。**判据只读「日期」列这一个结构化字段，不解析
状态列自由文本里的任何时间戳**（大量历史行不具备、且格式不统一）。

## 复用而非重造

表格解析用 `aibot_service.readme_table.iter_rows`（同登记 CLI）；状态归一化
用 `followup_gate.normalize_status`；编辑锁经子进程调用
`工具-共享文档编辑锁.py`（同登记 CLI 手法，均不深入其内部实现）。

## 用法

    python 0-学习与工具/工具-跟进信README归档.py --dry-run
    python 0-学习与工具/工具-跟进信README归档.py --who "CC-OP0906A"

`--dry-run` 只打印计划、不取锁、不写文件。归档目标文件按**本次运行时刻的
年月**命名（`README-归档-YYYYMM.md`）——同一批迁移落在同一份归档件里；
文件已存在时按编号去重后追加（重复运行幂等，不会把同一行迁两次）。
"""
from __future__ import annotations

import argparse
import datetime
import importlib.util
import subprocess
import sys
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
_REPO_GUESS = _TOOLS_DIR.parent

_EDIT_LOCK_SCRIPT = _TOOLS_DIR / "工具-共享文档编辑锁.py"
_editlock_spec = importlib.util.spec_from_file_location(
    "_followup_archive_editlock_reuse", _EDIT_LOCK_SCRIPT
)
editlock = importlib.util.module_from_spec(_editlock_spec)
sys.modules[_editlock_spec.name] = editlock
_editlock_spec.loader.exec_module(editlock)

_GATE_QUERY_SCRIPT = _TOOLS_DIR / "工具-跟进闸查询.py"
_gate_query_spec = importlib.util.spec_from_file_location(
    "_followup_archive_gatequery_reuse", _GATE_QUERY_SCRIPT
)
gate_query = importlib.util.module_from_spec(_gate_query_spec)
sys.modules[_gate_query_spec.name] = gate_query
_gate_query_spec.loader.exec_module(gate_query)

REPO_ROOT: Path = editlock.REPO_ROOT
README_REL = gate_query.README_REL

_PLATFORM_PATH = _REPO_GUESS / "5-平台底座" / "zhuopin_platform"
if not _PLATFORM_PATH.is_dir():
    _PLATFORM_PATH = REPO_ROOT / "5-平台底座" / "zhuopin_platform"
if _PLATFORM_PATH.is_dir() and str(_PLATFORM_PATH) not in sys.path:
    sys.path.insert(0, str(_PLATFORM_PATH))
from zhuopin_platform.shared_tools import followup_gate  # noqa: E402

_AIBOT_PATH = _REPO_GUESS / "5-平台底座" / "wecom-aibot-service"
if not _AIBOT_PATH.is_dir():
    _AIBOT_PATH = REPO_ROOT / "5-平台底座" / "wecom-aibot-service"
if _AIBOT_PATH.is_dir() and str(_AIBOT_PATH) not in sys.path:
    sys.path.insert(0, str(_AIBOT_PATH))
from aibot_service.readme_table import (  # noqa: E402
    MAIN_TABLE_SECTION,
    ReadmeTableError,
    column_index,
    iter_rows,
)

ARCHIVE_THRESHOLD_DAYS = 30
ARCHIVABLE_STATUS_PREFIXES = ("📥 已回件并回灌", "❌ 已作废")

MAIN_TABLE_HEADER_BLOCK = (
    f"## {MAIN_TABLE_SECTION}\n\n"
    "| 编号 | 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |\n"
    "|--------|------|--------|---------|---------|---------|\n"
)


class ArchiveError(RuntimeError):
    pass


class LockAcquireFailedError(RuntimeError):
    pass


def _readme_path() -> Path:
    return REPO_ROOT / README_REL


def _archive_path(today: datetime.date) -> Path:
    return _readme_path().parent / f"README-归档-{today.strftime('%Y%m')}.md"


def _readme_line(row) -> str:
    return "| " + " | ".join(row.cells) + " |"


def plan_migration(text: str, today: datetime.date):
    """返回 (待迁行的 `RowLocation` 列表, 日期列索引, 发送状态列索引)。

    纯函数，不碰磁盘、不取锁——`--dry-run` 与真实执行共用同一份判定，
    不允许两条路径各算一遍、算出不同的候选集合。
    """
    try:
        rows = iter_rows(text)
    except ReadmeTableError as exc:
        raise ArchiveError(f"README 表格解析失败：{exc}") from exc
    if not rows:
        raise ArchiveError("README 主表没有任何数据行")
    header = rows[0].header_cells
    date_idx = column_index(header, "日期")
    if date_idx is None:
        raise ArchiveError("README 表头缺「日期」列")

    candidates = []
    for row in rows:
        if len(row.cells) <= date_idx:
            continue  # 列数异常的历史行（如 2026-09-06 实测的 采购部#14）不参与判定
        status = row.cells[row.status_col_index]
        normalized = followup_gate.normalize_status(status)
        if not any(normalized.startswith(p) for p in ARCHIVABLE_STATUS_PREFIXES):
            continue
        date_str = row.cells[date_idx].strip()
        try:
            sent_date = datetime.date.fromisoformat(date_str)
        except ValueError:
            continue  # 日期列不是合法 ISO 日期——不猜，跳过不迁
        if (today - sent_date).days > ARCHIVE_THRESHOLD_DAYS:
            candidates.append(row)
    return candidates


def _existing_archive_numbers(archive_text: str, number_col: int) -> set[str]:
    try:
        rows = iter_rows(archive_text, MAIN_TABLE_SECTION)
    except ReadmeTableError:
        return set()
    return {row.cells[number_col] for row in rows if len(row.cells) > number_col}


def build_new_texts(readme_text: str, archive_text: str | None, candidates: list,
                     number_col: int) -> tuple[str, str, list]:
    """返回 (新主表文本, 新归档文本, 实际被迁移的行列表)。

    幂等：候选行编号若已存在于归档件中（重复运行场景），跳过、不重复追加，
    但仍需从主表移除（正常路径下不会出现——一行一旦迁走就不再是候选——
    这里只是防御同一行被迁移两次的极端情形）。
    """
    move_line_indexes = {row.line_index for row in candidates}
    lines = readme_text.splitlines()
    new_lines = [line for i, line in enumerate(lines) if i not in move_line_indexes]
    newline = "\n" if readme_text.endswith("\n") else ""
    new_readme_text = "\n".join(new_lines) + newline

    existing_numbers = (
        _existing_archive_numbers(archive_text, number_col) if archive_text else set()
    )
    moved = [r for r in candidates if r.cells[number_col] not in existing_numbers]
    appended_lines = "".join(_readme_line(r) + "\n" for r in moved)

    if archive_text is None:
        new_archive_text = MAIN_TABLE_HEADER_BLOCK + appended_lines
    else:
        archive_lines = archive_text.splitlines()
        arch_newline = "\n" if archive_text.endswith("\n") else ""
        new_archive_text = "\n".join(archive_lines) + arch_newline + appended_lines

    return new_readme_text, new_archive_text, moved


def _run_lock(action: str, who: str, note: str | None = None) -> bool:
    cmd = [
        sys.executable, str(_EDIT_LOCK_SCRIPT), "--file", README_REL,
        action, "--who", who,
    ]
    if note and action == "acquire":
        cmd.extend(["--note", note])
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        if action == "acquire":
            raise LockAcquireFailedError(
                f"编辑锁获取失败（README）：\n{result.stdout}\n{result.stderr}"
            )
        print(f"✗ 编辑锁 release 被拒绝：\n{result.stdout}\n{result.stderr}", file=sys.stderr)
        return False
    print(result.stdout, end="")
    return True


def _format_plan_line(row, date_idx: int, today: datetime.date) -> str:
    date_str = row.cells[date_idx].strip()
    age = (today - datetime.date.fromisoformat(date_str)).days
    status_brief = followup_gate.normalize_status(
        row.cells[row.status_col_index]
    ).split("\n")[0][:30]
    return f"  {row.cells[0]}｜{date_str}（{age} 天）｜{status_brief}"


def run(args: argparse.Namespace, today: datetime.date | None = None) -> int:
    today = today or datetime.date.today()
    readme_text = _readme_path().read_text(encoding="utf-8")
    try:
        candidates = plan_migration(readme_text, today)
    except ArchiveError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1

    if not candidates:
        print("[PLAN] 没有满足归档判据（终态 + 日期列 >30 天）的行。")
        return 0

    header = iter_rows(readme_text)[0].header_cells
    number_col = column_index(header, "编号")
    date_idx = column_index(header, "日期")

    print(f"[PLAN] {len(candidates)} 行满足归档判据，目标：{_archive_path(today).name}")
    for row in candidates:
        print(_format_plan_line(row, date_idx, today))

    if args.dry_run:
        print("[DRY-RUN] 未取锁、未写入。")
        return 0

    try:
        if not _run_lock("acquire", args.who, note=f"归档迁移：{len(candidates)} 行"):
            return 1
    except LockAcquireFailedError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1

    # 持锁后重读重定位（同登记 CLI/桥一既有惯例）：从上面 plan 到这里，
    # 别的会话可能已经改过 README。
    fresh_text = _readme_path().read_text(encoding="utf-8")
    try:
        fresh_candidates = plan_migration(fresh_text, today)
    except ArchiveError as exc:
        print(f"✗ 持锁后重新判定失败：{exc}", file=sys.stderr)
        _run_lock("release", args.who)
        return 1

    archive_path = _archive_path(today)
    archive_text = archive_path.read_text(encoding="utf-8") if archive_path.exists() else None
    new_readme_text, new_archive_text, moved = build_new_texts(
        fresh_text, archive_text, fresh_candidates, number_col
    )

    if not moved:
        print("[PLAN] 持锁后重新判定：候选均已迁移，无需操作。")
        _run_lock("release", args.who)
        return 0

    _readme_path().write_text(new_readme_text, encoding="utf-8")
    archive_path.write_text(new_archive_text, encoding="utf-8")

    # 写后回读校验：被迁行不再出现在主表，且逐字出现在归档件里。
    reread_readme = _readme_path().read_text(encoding="utf-8")
    reread_archive = archive_path.read_text(encoding="utf-8")
    ok = True
    for row in moved:
        line = _readme_line(row)
        if line in reread_readme or line not in reread_archive:
            ok = False
            break
    if not ok:
        print(
            "✗ 写后回读比对失败——文件内容与预期不一致，编辑锁保留，"
            "请人工排查（不自动重试、不自动回滚）。", file=sys.stderr,
        )
        return 1  # 🔴 刻意不 release——回读失败时锁必须保留供人工排查

    if not _run_lock("release", args.who):
        print(
            f"[WRITTEN-LOCK-HELD] 已迁移 {len(moved)} 行，但编辑锁 release 被拒绝"
            "（见上方原因）——锁仍占用，请人工核实并处理后再 release，"
            "不得视为归档已完成。", file=sys.stderr,
        )
        return 1

    print(f"[OK] 已迁移 {len(moved)} 行 → {archive_path.relative_to(REPO_ROOT)}")
    print(f"[OK] 主表大小：{len(new_readme_text.encode('utf-8'))} B")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="跟进信 README 已闭环归档迁移")
    parser.add_argument("--who", help="会话标识，透传给编辑锁（非 --dry-run 时必填）")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not args.dry_run and not args.who:
        parser.error("--who 为必填（--dry-run 除外）")
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
