"""跟进信 README 登记 CLI（`followup-readme-phase2` D1，队列 §一 `#490`）。

## 它解决的问题

登记/改状态跟进信 README 此前只能靠人工 `Edit` 直改——而工具约束下 `Edit`
前必须先 `Read` 全文，每登记一封信就吞掉一次全表字节（改造前 177.7 KB）。
本 CLI 是唯一登记入口：`append`（新增一行，写前列数校验、写后回读、字段
长度上限）与 `set-status`（改写既有行状态列，状态值受 `followup_gate` 权威
判据集合校验）。两者都经 `工具-共享文档编辑锁.py --file <README>` 单文件
锁，用完立刻释放。

## 复用而非重造

- 表格解析／写单元格：`aibot_service.readme_table`（`iter_rows`／
  `write_cells`／`_join_row`）——**不新造第二份 README 解析器**。
- 状态判据：`zhuopin_platform.shared_tools.followup_gate`（`classify_status`
  ／`normalize_status`）——**不自持一份独立于权威判据的状态字面量枚举**，
  避免与 `followup_gate` 漂移（同 `wecom-followup-review-state` 能力既有
  教训）。
- 部门下一个可用号：importlib 复用 `工具-跟进闸查询.py::_next_available_number`
  ——同一件事只应有一份算法，本工具不重算。
- 编辑锁：以子进程调用 `工具-共享文档编辑锁.py acquire/release`，把它当
  作真实外部依赖使用，不深入其内部实现细节（同人工调用方式一致）。

## 用法

    python 0-学习与工具/工具-跟进信README登记.py append \\
        --who "CC-OP0906A" --department 采购部 --recipient-cell "采购部 · 姚祖怡" \\
        --date 2026-09-06 --topic "…" --deadline-note "…"

    python 0-学习与工具/工具-跟进信README登记.py set-status \\
        --who "CC-OP0906A" --number 采购部#19 --status "📥 已回件并回灌（…）"

两个子命令均支持 `--dry-run`（不取锁、不写文件，只跑校验并打印结果）。
"""
from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
_REPO_GUESS = _TOOLS_DIR.parent

_EDIT_LOCK_SCRIPT = _TOOLS_DIR / "工具-共享文档编辑锁.py"
_editlock_spec = importlib.util.spec_from_file_location(
    "_followup_registry_editlock_reuse", _EDIT_LOCK_SCRIPT
)
editlock = importlib.util.module_from_spec(_editlock_spec)
sys.modules[_editlock_spec.name] = editlock  # dataclass 在 Python 3.14 下需要能在 sys.modules 解析到所属模块
_editlock_spec.loader.exec_module(editlock)

_GATE_QUERY_SCRIPT = _TOOLS_DIR / "工具-跟进闸查询.py"
_gate_query_spec = importlib.util.spec_from_file_location(
    "_followup_registry_gatequery_reuse", _GATE_QUERY_SCRIPT
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
from aibot_service import readme_table  # noqa: E402
from aibot_service.readme_table import (  # noqa: E402
    MAIN_TABLE_SECTION,
    ReadmeTableError,
    column_index,
    iter_rows,
    split_department_and_name,
    write_cells,
)

DRAFT_STATUS = "⏳ 待你审"
TOPIC_MAX_BYTES = 600
DEADLINE_NOTE_MAX_BYTES = 400
UNNUMBERED_ANNOTATION = "（待你审，暂不占号）"

# 归档件命名（`followup-readme-archive` 能力，2.3 落地后生效；本文件先兼容
# 「归档件尚不存在」的现状，`glob` 命中 0 个文件属正常）。
_ARCHIVE_GLOB = "README-归档-*.md"


class RegistryError(RuntimeError):
    """校验失败、拒绝写入——不区分子类，调用方统一按退出码 1 处理。"""


class LockAcquireFailedError(RuntimeError):
    """编辑锁获取失败（他人持锁），未做任何改动。"""


class ReadbackMismatchError(RuntimeError):
    """写后回读比对失败——按 spec 要求保留锁，不自动释放、不自动重试。"""


def _readme_path() -> Path:
    return REPO_ROOT / README_REL


def _byte_len(text: str) -> int:
    return len(text.encode("utf-8"))


def _assert_field_lengths(topic: str, deadline_note: str) -> None:
    topic_bytes = _byte_len(topic)
    if topic_bytes > TOPIC_MAX_BYTES:
        raise RegistryError(
            f"「主要事项」{topic_bytes} B，超 {TOPIC_MAX_BYTES} B 上限——"
            "请改用行长外置（`followup-readme-row-length-guard` 能力：压成摘要，"
            "原文写入 `跟进信行日志/<部门#N>.md`）后再登记摘要。"
        )
    note_bytes = _byte_len(deadline_note)
    if note_bytes > DEADLINE_NOTE_MAX_BYTES:
        raise RegistryError(
            f"「交期要点」{note_bytes} B，超 {DEADLINE_NOTE_MAX_BYTES} B 上限——"
            "请精简后再登记。"
        )


def _parse_rows(text: str, section: str | None = None) -> list:
    """解析表头与数据行；只保证表头可解析，**不对历史行的列数做任何断言**
    ——校验范围限定为本次触碰的行，见 spec「写前列数校验与写后回读」
    2026-09-06 补充说明（`采购部#14` 历史行因未转义 `|` 被朴素分列多出一列，
    早于本能力存在，不应阻塞其它行的登记）。"""
    try:
        rows = iter_rows(text, section)
    except ReadmeTableError as exc:
        raise RegistryError(f"README 表格解析失败：{exc}") from exc
    if not rows:
        raise RegistryError("README 主表没有任何数据行，拒绝在此基础上继续")
    return rows


def _assert_row_column_count(cells: list[str], header: list[str], row_label: str) -> None:
    """本次待写入/待改写的那一行列数须与表头一致——只查这一行，不查全表。"""
    if len(cells) != len(header):
        raise RegistryError(
            f"「{row_label}」列数校验失败：{len(cells)} 列，表头 {len(header)} 列——"
            "拒绝写入"
        )


def _find_in_archives(number: str) -> str | None:
    """在归档件中查找编号，命中返回归档文件相对路径，未命中返回 None。

    `followup-readme-archive` 能力（2.3）落地前，归档件尚不存在，
    `glob` 天然返回空——本函数此时恒返回 None，行为等价于「archive 查找
    这一步暂时是空操作」，不是特殊分支。
    """
    readme_dir = _readme_path().parent
    for archive_path in sorted(readme_dir.glob(_ARCHIVE_GLOB)):
        try:
            text = archive_path.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            rows = iter_rows(text, MAIN_TABLE_SECTION)
        except ReadmeTableError:
            continue
        header = rows[0].header_cells if rows else []
        number_col = column_index(header, "编号")
        if number_col is None:
            continue
        for row in rows:
            if len(row.cells) <= number_col:
                continue
            parsed = followup_gate.parse_letter_number(row.cells[number_col])
            target_parsed = followup_gate.parse_letter_number(number)
            if parsed and target_parsed and parsed == target_parsed:
                return str(archive_path.relative_to(REPO_ROOT))
    return None


def _run_lock(action: str, who: str, note: str | None = None) -> bool:
    """返回是否成功。`acquire` 失败直接抛异常（未做任何改动，无需返回值）；
    `release` 被拒绝返回 `False`，由调用方决定如何呈现（不得报告成功）。"""
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
        # release 被拒绝——文件已写入，锁仍占用，调用方 MUST NOT 报告成功
        # （见 spec「编辑锁 release 失败不得报告为成功」，2026-09-06 实测发现：
        # 新增行触发既有「跟进信串行原则」release 校验时会走到这里）。
        print(f"✗ 编辑锁 release 被拒绝：\n{result.stdout}\n{result.stderr}", file=sys.stderr)
        return False
    print(result.stdout, end="")
    return True


def _write_readback(new_text: str, expected_cells: list[str], locate) -> None:
    """写盘后立即回读并比对，比对失败抛 `ReadbackMismatchError`（不释放锁）。"""
    _readme_path().write_text(new_text, encoding="utf-8")
    reread = _readme_path().read_text(encoding="utf-8")
    row = locate(reread)
    if row is None or row.cells != expected_cells:
        raise ReadbackMismatchError(
            "写后回读比对失败——文件内容与预期不一致，编辑锁保留，请人工排查"
            "（不自动重试、不自动回滚）。"
        )


def _assert_gate_open(recipient_cell: str, text: str) -> None:
    """append 前置串行闸检查——判据与 `工具-跟进闸查询.py` 同一份
    （`gate_query.build_report`，本身即 `followup_gate.classify_status`）。
    2026-09-06 实测发现补入：编辑锁 release 时的「跟进信串行原则」结构校验
    只在写入之后拦截，会留下「文件已改、release 被拒、锁未释放」的中间态；
    把同一判据前移到写入前可避免这种情形。"""
    _, name = split_department_and_name(recipient_cell)
    if not name:
        return  # 收信人姓名解析不出，交由既有 release 校验与人工判断兜底
    try:
        report = gate_query.build_report(name, text)
    except gate_query.GateQueryError:
        return  # 该收信人此前无任何行——视为闸开，无在途信可挡
    if not report.gate_open:
        raise RegistryError(
            f"收信人「{name}」当前闸锁——最新一封「{report.letter_number}」"
            f"（{followup_gate.normalize_status(report.letter_status)[:40]}）尚未闭环，"
            "拒绝新增草稿行。请先处理该在途信使其闭环，或改在队列登记"
            "「待前信闭环后发」。（同 `python 0-学习与工具/工具-跟进闸查询.py "
            f"--to {name}` 的判据）"
        )


def _catches_registry_errors(func):
    """`RegistryError`／`LockAcquireFailedError` 统一在这里落成「打印 + 退出码
    1」——`cmd_append`／`cmd_set_status` 本身可被直接调用（单测既定手法），
    不依赖只在 `main()` 里包一层 try/except（那样直接调用 `cmd_*` 的测试会
    看到裸异常，而不是真实 CLI 用户会看到的行为）。"""
    def _wrapped(args: argparse.Namespace) -> int:
        try:
            return func(args)
        except (RegistryError, LockAcquireFailedError) as exc:
            print(f"✗ {exc}", file=sys.stderr)
            return 1
    _wrapped.__name__ = func.__name__
    return _wrapped


# ---------------------------------------------------------------------------
# append
# ---------------------------------------------------------------------------

@_catches_registry_errors
def cmd_append(args: argparse.Namespace) -> int:
    _assert_field_lengths(args.topic, args.deadline_note)

    text = _readme_path().read_text(encoding="utf-8")
    _assert_gate_open(args.recipient_cell, text)
    rows = _parse_rows(text)
    header = rows[0].header_cells
    number_col = column_index(header, "编号")
    if number_col is None:
        raise RegistryError("README 表头缺「编号」列")

    next_number = gate_query._next_available_number(rows, number_col, args.department)
    if next_number is None:
        raise RegistryError(f"无法为部门「{args.department}」推算下一个可用号")
    number_cell = f"{next_number}{UNNUMBERED_ANNOTATION}"

    new_cells = [number_cell, args.date, args.recipient_cell, args.topic, args.deadline_note, DRAFT_STATUS]
    _assert_row_column_count(new_cells, header, number_cell)

    print(
        f"[PLAN] append：{number_cell} ｜ {args.date} ｜ {args.recipient_cell} ｜"
        f" 状态={DRAFT_STATUS}"
    )
    if args.dry_run:
        print("[DRY-RUN] 未取锁、未写入。")
        return 0

    _run_lock("acquire", args.who, note=f"登记 append：{next_number}")
    try:
        lines = text.splitlines()
        insert_at = rows[-1].line_index + 1
        lines.insert(insert_at, readme_table._join_row(new_cells))
        newline = "\n" if text.endswith("\n") else ""
        new_text = "\n".join(lines) + newline

        def _locate(t: str):
            try:
                for r in iter_rows(t):
                    if r.cells[number_col] == number_cell:
                        return r
            except ReadmeTableError:
                return None
            return None

        _write_readback(new_text, new_cells, _locate)
    except ReadbackMismatchError as exc:
        print(f"[READBACK-FAILED] {exc}", file=sys.stderr)
        return 1
    else:
        if not _run_lock("release", args.who):
            print(
                f"[WRITTEN-LOCK-HELD] 已写入 {number_cell}，但编辑锁 release 被拒绝"
                "（见上方原因）——锁仍占用，请人工核实并处理后再 release，"
                "不得视为登记已完成。",
                file=sys.stderr,
            )
            return 1
        print(f"[OK] 已追加：{number_cell}")
        return 0


# ---------------------------------------------------------------------------
# set-status
# ---------------------------------------------------------------------------

@_catches_registry_errors
def cmd_set_status(args: argparse.Namespace) -> int:
    normalized = followup_gate.normalize_status(args.status)
    if followup_gate.classify_status(normalized) == "unknown":
        raise RegistryError(
            f"状态值「{args.status}」归一化后不属于 followup_gate 已知状态前缀"
            "（CLOSED_STATUS_PREFIXES／IN_FLIGHT_STATUS_PREFIXES／REPLY_ARRIVED_STATUS）"
            "，拒绝写入。"
        )

    text = _readme_path().read_text(encoding="utf-8")
    rows = _parse_rows(text)
    header = rows[0].header_cells
    number_col = column_index(header, "编号")
    if number_col is None:
        raise RegistryError("README 表头缺「编号」列")

    target_parsed = followup_gate.parse_letter_number(args.number)
    match = None
    for row in rows:
        if len(row.cells) <= number_col:
            continue
        cell = row.cells[number_col]
        if cell == args.number or (
            target_parsed and followup_gate.parse_letter_number(cell) == target_parsed
        ):
            match = row
            break

    if match is None:
        archived_at = _find_in_archives(args.number)
        if archived_at:
            raise RegistryError(
                f"编号「{args.number}」已归档（{archived_at}），不可再用本命令改状态——"
                "该行已进入终态历史，如需订正请人工处理归档件。"
            )
        raise RegistryError(f"编号「{args.number}」在主表与归档件中均不存在")

    _assert_row_column_count(match.cells, header, match.cells[number_col])

    print(f"[PLAN] set-status：{args.number} → {args.status}")
    if args.dry_run:
        print("[DRY-RUN] 未取锁、未写入。")
        return 0

    _run_lock("acquire", args.who, note=f"登记 set-status：{args.number}")
    try:
        new_text = write_cells(text, match, {match.status_col_index: args.status})
        expected_cells = match.cells.copy()
        expected_cells[match.status_col_index] = args.status

        def _locate(t: str):
            try:
                for r in iter_rows(t):
                    if len(r.cells) > number_col and r.cells[number_col] == match.cells[number_col]:
                        return r
            except ReadmeTableError:
                return None
            return None

        _write_readback(new_text, expected_cells, _locate)
    except ReadbackMismatchError as exc:
        print(f"[READBACK-FAILED] {exc}", file=sys.stderr)
        return 1
    else:
        if not _run_lock("release", args.who):
            print(
                f"[WRITTEN-LOCK-HELD] 已改写 {args.number}，但编辑锁 release 被拒绝"
                "（见上方原因）——锁仍占用，请人工核实并处理后再 release，"
                "不得视为登记已完成。",
                file=sys.stderr,
            )
            return 1
        print(f"[OK] 已改写：{args.number} → {args.status}")
        return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="跟进信 README 登记 CLI（唯一登记入口，取代裸手 Edit 直改）"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_append = sub.add_parser("append", help="新增一行（发送状态恒为待审草稿态）")
    p_append.add_argument("--who", required=True, help="会话标识，透传给编辑锁")
    p_append.add_argument("--department", required=True, help="如 采购部")
    p_append.add_argument("--recipient-cell", required=True, help='如 "采购部 · 姚祖怡"')
    p_append.add_argument("--date", required=True, help="YYYY-MM-DD")
    p_append.add_argument("--topic", required=True, help="主要事项（≤600 B）")
    p_append.add_argument("--deadline-note", required=True, help="交期要点（≤400 B）")
    p_append.add_argument("--dry-run", action="store_true")
    p_append.set_defaults(func=cmd_append)

    p_status = sub.add_parser("set-status", help="按编号改写发送状态列")
    p_status.add_argument("--who", required=True)
    p_status.add_argument("--number", required=True, help="如 采购部#19")
    p_status.add_argument("--status", required=True, help="新的发送状态值")
    p_status.add_argument("--dry-run", action="store_true")
    p_status.set_defaults(func=cmd_set_status)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
