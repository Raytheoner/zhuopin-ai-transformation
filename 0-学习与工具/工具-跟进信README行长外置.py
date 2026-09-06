"""跟进信 README 行长外置迁移工具（`followup-readme-phase2` D3，队列 §一 `#490`）。

## 判据（正本＝ `openspec/changes/followup-readme-phase2/design.md` D3 及其
「续棒补充 D3-1/2/3」，Shao Peishen 2026-09-06 经环境总线拍板）

一行的两列各自独立判定，命中即外置（可同一行两列都命中）：

- **「发送状态」列** > `ROW_LENGTH_CAP_BYTES`（4 KB，UTF-8 字节，与跨桌任务
  队列同一套判据常量，不另立数值）——按 `━━━` 分段取首段＋末段＋指针，
  原文原样迁 `跟进信行日志/<编号>.md`。
- **「主要事项」列** > `README_TOPIC_CAP_BYTES`（600 B）——压缩为「首句或
  前 200 字＋指针」的确定性摘要（不做语义压缩），原文原样迁同一行日志文件。

## 复用而非重造

表格解析用 `aibot_service.readme_table`（同登记 CLI／归档工具）；行长常量
与逃生阀判定从 `工具-共享文档编辑锁.py` 复用（同一份 `ROW_LENGTH_CAP_
BYTES`／`README_TOPIC_CAP_BYTES`／`ROW_LENGTH_WAIVER_MARKER`／
`_has_genuine_row_length_waiver`），不新造第二套判据常量或逃生阀识别逻辑
——release 时的行长**判据**（编辑锁 release 校验族）与本工具的行长**外置
执行**必须认得同一个阈值与同一个逃生阀标记，否则会出现"外置工具认为已
达标、release 判据却仍拦"或反过来的口径漂移。

## 幂等

候选判定＝"当前列内容是否仍超阈值"，纯读时点取值，不依赖任何标记位：
外置一次后该列已在阈值内，下次运行自然不再是候选（同
`工具-跟进信README归档.py` 对已归档行天然不再是候选同一手法）。若该行
带逃生阀标记 `行长豁免：<理由>`（真实非占位符引用），本工具**跳过**该列
——豁免的意图是"暂留在主表"，外置会违背这个意图。

## 用法

    python 0-学习与工具/工具-跟进信README行长外置.py --dry-run
    python 0-学习与工具/工具-跟进信README行长外置.py --who "CC-OP0906D"

`--dry-run` 只打印计划、不取锁、不写文件。`--file` 可指向某份
`README-归档-YYYYMM.md` 归档件（同队列查询工具既有 `--file` 用法）——
🔴 但编辑锁 release 时的行长**判据**只挂在主表路径（`FOLLOWUP_README_
TARGET`）上，对归档件本工具只提供**外置执行**，不提供 release 时的
自动拦截兜底，须知悉。
"""
from __future__ import annotations

import argparse
import datetime
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
_REPO_GUESS = _TOOLS_DIR.parent

_EDIT_LOCK_SCRIPT = _TOOLS_DIR / "工具-共享文档编辑锁.py"
_editlock_spec = importlib.util.spec_from_file_location(
    "_followup_rowlength_editlock_reuse", _EDIT_LOCK_SCRIPT
)
editlock = importlib.util.module_from_spec(_editlock_spec)
sys.modules[_editlock_spec.name] = editlock
_editlock_spec.loader.exec_module(editlock)

_GATE_QUERY_SCRIPT = _TOOLS_DIR / "工具-跟进闸查询.py"
_gate_query_spec = importlib.util.spec_from_file_location(
    "_followup_rowlength_gatequery_reuse", _GATE_QUERY_SCRIPT
)
gate_query = importlib.util.module_from_spec(_gate_query_spec)
sys.modules[_gate_query_spec.name] = gate_query
_gate_query_spec.loader.exec_module(gate_query)

REPO_ROOT: Path = editlock.REPO_ROOT
README_REL = gate_query.README_REL

ROW_LENGTH_CAP_BYTES = editlock.ROW_LENGTH_CAP_BYTES
TOPIC_CAP_BYTES = editlock.README_TOPIC_CAP_BYTES
LOG_DIR_REL = editlock.README_ROW_LOG_DIR
WAIVER_MARKER = editlock.ROW_LENGTH_WAIVER_MARKER
_has_genuine_waiver = editlock._has_genuine_row_length_waiver
SEGMENT_SEP = editlock.CONCLUSION_SEGMENT_SEPARATOR

_PLATFORM_PATH = _REPO_GUESS / "5-平台底座" / "zhuopin_platform"
if not _PLATFORM_PATH.is_dir():
    _PLATFORM_PATH = REPO_ROOT / "5-平台底座" / "zhuopin_platform"
if _PLATFORM_PATH.is_dir() and str(_PLATFORM_PATH) not in sys.path:
    sys.path.insert(0, str(_PLATFORM_PATH))

_AIBOT_PATH = _REPO_GUESS / "5-平台底座" / "wecom-aibot-service"
if not _AIBOT_PATH.is_dir():
    _AIBOT_PATH = REPO_ROOT / "5-平台底座" / "wecom-aibot-service"
if _AIBOT_PATH.is_dir() and str(_AIBOT_PATH) not in sys.path:
    sys.path.insert(0, str(_AIBOT_PATH))
from aibot_service.readme_table import (  # noqa: E402
    ReadmeTableError,
    column_index,
    iter_rows,
    write_cells,
)

STATUS_LABEL = "发送状态"
TOPIC_LABEL = "主要事项"

# 🔴 表格单元格必须是单一物理行——真实生产数据里的分段视觉分隔符从来
# 不是字面换行符（那样写会把一行 markdown 表格行拆成多行、当场撑坏表格
# 结构），而是全角空格包裹的 `━━━`（真实样本见 `财务部#16` 发送状态列
# 原文 `…　━━━　原状态 ━━━　…`）。本工具拼接压缩产物时必须
# 遵守同一约定，绝不能在单元格值里插入 `\n`。
CELL_SEGMENT_JOIN = "　"

# D3-2：首句切分标点——句号／叹号／问号／换行，取第一个命中位置（含该标点）。
_SENTENCE_END_RE = re.compile(r"[。！？\n]")
SUMMARY_FIRST_SENTENCE_CHAR_CAP = 200


class ExternalizeError(RuntimeError):
    pass


class LockAcquireFailedError(RuntimeError):
    pass


class ExternalizeAction:
    __slots__ = ("row_number", "column", "size", "original", "new_cell", "cell_index")

    def __init__(self, row_number, column, size, original, new_cell, cell_index):
        self.row_number = row_number
        self.column = column
        self.size = size
        self.original = original
        self.new_cell = new_cell
        self.cell_index = cell_index


def _log_path(row_number: str) -> Path:
    return REPO_ROOT / LOG_DIR_REL / f"{row_number}.md"


def _pointer_note(row_number: str) -> str:
    return f"（详见 `{LOG_DIR_REL}/{row_number}.md`）"


def _truncate_to_fit(base: str, suffix: str, cap_bytes: int) -> str:
    """从 `base` 尾部逐字符收缩，直到 `base(去尾空白) + suffix` 的 UTF-8
    字节数不超过 `cap_bytes`——保证外置产物本身不会在写入瞬间又撞上同一
    条行长判据（D3-2 明文要求）。`base` 收缩到空串仍超限（`suffix` 本身
    就超过上限）是判据配置错误，交给上层 `assert` 暴露，不在此处静默。
    """
    candidate = base
    while candidate and len((candidate.rstrip() + suffix).encode("utf-8")) > cap_bytes:
        candidate = candidate[:-1]
    result = candidate.rstrip() + suffix
    assert len(result.encode("utf-8")) <= cap_bytes, (
        f"外置产物本身超过上限（{cap_bytes} B）：指针/后缀文本过长，"
        "属判据配置问题，需要人工核实 LOG_DIR_REL 路径长度或后缀措辞。"
    )
    return result


def build_topic_summary(topic_text: str, row_number: str) -> str:
    """D3-2：首句或前 200 字＋指针，不做语义压缩。"""
    pointer = _pointer_note(row_number)
    match = _SENTENCE_END_RE.search(topic_text)
    first_sentence = topic_text[: match.end()].strip() if match else topic_text.strip()
    base = first_sentence if len(first_sentence) <= SUMMARY_FIRST_SENTENCE_CHAR_CAP else (
        topic_text[:SUMMARY_FIRST_SENTENCE_CHAR_CAP]
    )
    return _truncate_to_fit(base, pointer, TOPIC_CAP_BYTES)


def build_status_compact(status_text: str, row_number: str) -> str:
    """外置「发送状态」列：≥2 段（按 `━━━` 切分）时留首段＋指针＋末段；
    否则（连续文本、无分段结构）退化为「前 500 字＋指针」，与 D3-2 摘要
    同一确定性截断思路（本项目现网 25 个候选行全部 ≥2 段，退化分支为
    尚未真实撞见的防御路径，供单测覆盖）。
    """
    pointer = _pointer_note(row_number)
    segments = status_text.split(SEGMENT_SEP)
    if len(segments) >= 2:
        first = segments[0].strip()
        last = segments[-1].strip()
        # 先各自收缩到不超过一半上限，再拼合，确保总长不超上限——两段
        # 独立收缩比"整体再收缩一次"更能保留首尾各自的完整语义边界。
        half_cap = (ROW_LENGTH_CAP_BYTES - len(pointer.encode("utf-8"))) // 2
        first = _truncate_to_fit(first, "", max(half_cap, 0))
        last_fit = _truncate_to_fit(last, "", max(half_cap, 0))
        j = CELL_SEGMENT_JOIN
        candidate = f"{first}{j}{SEGMENT_SEP}{j}{pointer}{j}{SEGMENT_SEP}{j}{last_fit}"
        if len(candidate.encode("utf-8")) <= ROW_LENGTH_CAP_BYTES:
            return candidate
        # 极端兜底（首尾各自收缩后仍超限，理论上不会发生，half_cap 已预留
        # 足够余量）——退回纯截断分支。
    j = CELL_SEGMENT_JOIN
    return _truncate_to_fit(status_text[:500], f"{j}{SEGMENT_SEP}{j}{pointer}", ROW_LENGTH_CAP_BYTES)


def plan_externalization(text: str, section: str | None = None) -> list[ExternalizeAction]:
    """纯函数，不碰磁盘、不取锁——`--dry-run` 与真实执行共用同一份判定。"""
    try:
        rows = iter_rows(text, section)
    except ReadmeTableError as exc:
        raise ExternalizeError(f"README 表格解析失败：{exc}") from exc
    if not rows:
        return []
    header = rows[0].header_cells
    topic_idx = column_index(header, TOPIC_LABEL)
    if topic_idx is None:
        raise ExternalizeError(f"README 表头缺「{TOPIC_LABEL}」列")

    actions: list[ExternalizeAction] = []
    for row in rows:
        row_number = row.cells[0] if row.cells else "?"
        status_idx = row.status_col_index
        checks = [(STATUS_LABEL, status_idx, ROW_LENGTH_CAP_BYTES, build_status_compact)]
        checks.append((TOPIC_LABEL, topic_idx, TOPIC_CAP_BYTES, build_topic_summary))
        for label, idx, cap, builder in checks:
            if idx is None or len(row.cells) <= idx:
                continue
            cell = row.cells[idx]
            size = len(cell.encode("utf-8"))
            if size <= cap:
                continue
            if _has_genuine_waiver(cell):
                continue  # 逃生阀齐备：意图是暂留主表，本工具不越权外置
            new_cell = builder(cell, row_number)
            actions.append(ExternalizeAction(row_number, label, size, cell, new_cell, idx))
    return actions


def _write_log_sections(actions: list[ExternalizeAction], today: str) -> None:
    grouped: dict[str, list[ExternalizeAction]] = {}
    for action in actions:
        grouped.setdefault(action.row_number, []).append(action)

    for row_number, row_actions in grouped.items():
        path = _log_path(row_number)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            frontmatter = (
                "---\n"
                f'title: "跟进信行日志 {row_number}"\n'
                f"created: {today}\n"
                "status: 生效\n"
                "用途: 跟进信 README 主表编号 "
                f"{row_number} 的列历史外置件（followup-readme-phase2 D3 口径："
                "单格超阈值即外置，原文原样、可 grep）。行内只留首段＋末段＋"
                "指针。\n"
                "---\n"
            )
            path.write_text(frontmatter, encoding="utf-8")
        with path.open("a", encoding="utf-8") as fh:
            for action in row_actions:
                fh.write(
                    f"\n---\n\n# {row_number} · {action.column}列外置前原文"
                    f"（{today} 外置，{action.size} B）\n\n{action.original}\n"
                )


def _run_lock(target_file: str, action: str, who: str, note: str | None = None) -> bool:
    cmd = [
        sys.executable, str(_EDIT_LOCK_SCRIPT), "--file", target_file,
        action, "--who", who,
    ]
    if note and action == "acquire":
        cmd.extend(["--note", note])
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        if action == "acquire":
            raise LockAcquireFailedError(
                f"编辑锁获取失败（{target_file}）：\n{result.stdout}\n{result.stderr}"
            )
        print(f"✗ 编辑锁 release 被拒绝：\n{result.stdout}\n{result.stderr}", file=sys.stderr)
        return False
    print(result.stdout, end="")
    return True


def _format_plan_line(action: ExternalizeAction) -> str:
    return f"  {action.row_number}｜{action.column}列 {action.size} B → {_log_path(action.row_number).relative_to(REPO_ROOT)}"


SERIAL_WAIVER_REASON = "D3 行长外置压缩摘要，非新起草跟进信"


def _find_serial_gate_conflicts(snapshot_text: str, current_text: str) -> list[str]:
    """复刻跟进信串行原则闸（队列 #308 子项 G，
    `_validate_followup_readme_release`）的检测逻辑本身、直接返回需要
    豁免的行编号列表——**不解析它产出的违规文案**：文案是给人读的自由
    文本，可能内嵌全角冒号等标点（真实撞见：`长事项："` 这类前缀会让朴素
    的按冒号切分取错子串），从文案反解行编号是脆弱的。判据源必须与
    `_validate_followup_readme_release` 逐字一致（直接调用其内部同一批
    私有函数，不重新誊写一份逻辑），否则本工具"以为已解决"而 release 时
    判据不认，或反过来。"""
    old_rows = editlock._followup_readme_rows(snapshot_text)
    old_identities = {
        editlock._followup_row_identity(cells, idx) for _, cells, idx in old_rows
    }
    recipient_col_index = editlock._followup_header_col_index(current_text, "收信人")
    if recipient_col_index < 0:
        return []
    current_rows = editlock._followup_readme_rows(current_text)
    conflicts: list[str] = []
    for idx, (_line, cells, status_col_index) in enumerate(current_rows):
        identity = editlock._followup_row_identity(cells, status_col_index)
        if identity in old_identities:
            continue  # 既有行的状态转换不受本项约束
        if len(cells) <= recipient_col_index:
            continue
        recipient = cells[recipient_col_index]
        prior_status = None
        for j in range(idx - 1, -1, -1):
            prior_cells = current_rows[j][1]
            if len(prior_cells) <= recipient_col_index:
                continue
            if prior_cells[recipient_col_index] == recipient:
                prior_status = prior_cells[current_rows[j][2]]
                break
        if prior_status is None:
            continue  # 该收信人历史上首次出现，不受串行原则约束
        if editlock._followup_status_is_closed(prior_status):
            continue  # 前一封已闭环
        if any(editlock.FOLLOWUP_SERIAL_WAIVER_MARKER in c for c in cells):
            continue  # 已带真实豁免（如既有豁免或本函数上一轮已写入）
        conflicts.append(cells[0] if cells else "?")
    return conflicts


def _resolve_serial_gate_conflicts(snapshot_text: str, current_text: str) -> tuple[str, list[str]]:
    """本工具压缩「主要事项」列会改变 `_followup_row_identity`（该函数取
    「除状态列外全部单元格」为行身份）——跟进信串行原则闸因此可能把这类
    **纯历史内容压缩**误判成"新起草的跟进信"：只要该行不是其收信人当前
    最新一封、且该收信人真正最新一封仍未闭环，闸就会拒绝 release。

    这是 D3 外置动作与既有串行闸机制的一处真实交互缺口（design.md 撰写
    时未预见）——2026-09-06 对生产 README 真实执行时实测撞见（`采购部#12`／
    `IT部#8`／`质量部#10`／`质量部#12` 四行）。修法：复用串行闸自身已有的
    逃生阀 `串行豁免：`（不新造第二套判据），写在「交期要点」列（不动
    「主要事项」摘要本身的格式，D3-2 的摘要契约不受影响）。收尾再跑一次
    **官方**校验函数兜底——若本函数的复刻逻辑与官方判据出现漂移，或写入
    触发了其它类别的违规（理论上不会发生，本工具从不写终态状态值），一律
    原样上抛，不静默吞掉。"""
    waived_rows: list[str] = []
    text = current_text
    for _ in range(50):  # 防御性上限，真实候选行数远小于此
        conflicts = _find_serial_gate_conflicts(snapshot_text, text)
        if not conflicts:
            break
        rows = iter_rows(text)
        header = rows[0].header_cells if rows else []
        delivery_idx = column_index(header, "交期要点")
        if delivery_idx is None:
            raise ExternalizeError('README 表头缺「交期要点」列，无法写入串行豁免标注')
        for row in rows:
            if row.cells[0] not in conflicts or row.cells[0] in waived_rows:
                continue
            if len(row.cells) <= delivery_idx:
                continue
            new_delivery = (
                row.cells[delivery_idx].rstrip()
                + f"｜{editlock.FOLLOWUP_SERIAL_WAIVER_MARKER}{SERIAL_WAIVER_REASON}"
            )
            text = write_cells(text, row, {delivery_idx: new_delivery})
            waived_rows.append(row.cells[0])
            rows = iter_rows(text)  # 写入后位置已变，下一行前重新定位
    else:
        raise ExternalizeError("串行原则违规处理超过防御性上限，判据可能有误，请人工排查。")

    violations = editlock._validate_followup_readme_release(text, snapshot_text)
    if violations:
        raise ExternalizeError(
            "串行原则误判已尝试消解，但官方校验函数复核仍有违规残留——"
            "可能是本函数的复刻逻辑与官方判据出现漂移，或外置写入引入了"
            "其它类别的问题，已停止自动处理，请人工排查：\n" + "\n".join(violations)
        )
    return text, waived_rows


def run(args: argparse.Namespace, today: datetime.date | None = None) -> int:
    today = today or datetime.date.today()
    today_str = today.isoformat()
    target_rel = args.file
    target_path = REPO_ROOT / target_rel
    readme_text = target_path.read_text(encoding="utf-8")
    try:
        candidates = plan_externalization(readme_text)
    except ExternalizeError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1

    if not candidates:
        print(f"[PLAN] {target_rel} 没有满足行长外置判据（发送状态 >{ROW_LENGTH_CAP_BYTES} B "
              f"或 主要事项 >{TOPIC_CAP_BYTES} B）的行。")
        return 0

    print(f"[PLAN] {len(candidates)} 项外置：")
    for action in candidates:
        print(_format_plan_line(action))

    if args.dry_run:
        print("[DRY-RUN] 未取锁、未写入。")
        return 0

    try:
        if not _run_lock(target_rel, "acquire", args.who, note=f"行长外置：{len(candidates)} 项"):
            return 1
    except LockAcquireFailedError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1

    fresh_text = target_path.read_text(encoding="utf-8")
    try:
        fresh_candidates = plan_externalization(fresh_text)
    except ExternalizeError as exc:
        print(f"✗ 持锁后重新判定失败：{exc}", file=sys.stderr)
        _run_lock(target_rel, "release", args.who)
        return 1

    if not fresh_candidates:
        print("[PLAN] 持锁后重新判定：候选均已外置或已由他人处理，无需操作。")
        _run_lock(target_rel, "release", args.who)
        return 0

    rows = iter_rows(fresh_text)
    row_by_number = {r.cells[0]: r for r in rows if r.cells}
    new_text = fresh_text
    for action in fresh_candidates:
        loc = row_by_number.get(action.row_number)
        if loc is None:
            continue  # 持锁后该行已不在（极小概率并发场景），跳过不强改
        new_text = write_cells(new_text, loc, {action.cell_index: action.new_cell})
        # 后续行的 write_cells 需基于最新文本重新定位——同一行内两列都命中
        # 的情形（如 财务部#16）在下一轮迭代前须重新 iter_rows。
        rows = iter_rows(new_text)
        row_by_number = {r.cells[0]: r for r in rows if r.cells}

    try:
        new_text, waived_rows = _resolve_serial_gate_conflicts(fresh_text, new_text)
    except ExternalizeError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        _run_lock(target_rel, "release", args.who)
        return 1
    if waived_rows:
        print(
            f"⚠ 外置压缩改变了 {len(waived_rows)} 行的身份，触发跟进信串行原则闸"
            f"误判（历史内容压缩≠新起草）——已在「交期要点」列追加"
            f"「{editlock.FOLLOWUP_SERIAL_WAIVER_MARKER}{SERIAL_WAIVER_REASON}」："
            f"{'、'.join(waived_rows)}"
        )

    target_path.write_text(new_text, encoding="utf-8")
    _write_log_sections(fresh_candidates, today_str)

    # 写后回读校验：外置产物已落主表，且原文逐字出现在对应日志文件。
    reread_text = target_path.read_text(encoding="utf-8")
    ok = True
    for action in fresh_candidates:
        log_text = _log_path(action.row_number).read_text(encoding="utf-8")
        if action.new_cell not in reread_text or action.original not in log_text:
            ok = False
            break
    if not ok:
        print(
            "✗ 写后回读比对失败——文件内容与预期不一致，编辑锁保留，"
            "请人工排查（不自动重试、不自动回滚）。", file=sys.stderr,
        )
        return 1

    if not _run_lock(target_rel, "release", args.who):
        print(
            f"[WRITTEN-LOCK-HELD] 已外置 {len(fresh_candidates)} 项，但编辑锁 release "
            "被拒绝（见上方原因）——锁仍占用，请人工核实并处理后再 release，"
            "不得视为外置已完成。", file=sys.stderr,
        )
        return 1

    print(f"[OK] 已外置 {len(fresh_candidates)} 项")
    print(f"[OK] {target_rel} 大小：{len(new_text.encode('utf-8'))} B")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="跟进信 README 行长外置迁移")
    parser.add_argument("--who", help="会话标识，透传给编辑锁（非 --dry-run 时必填）")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--file", default=README_REL,
        help=f"目标文件相对仓库根路径（默认主表 {README_REL}；可指向某份 "
             "README-归档-YYYYMM.md 归档件——但 release 时的行长判据只挂在"
             "主表路径上，归档件外置无自动拦截兜底）",
    )
    args = parser.parse_args(argv)
    if not args.dry_run and not args.who:
        parser.error("--who 为必填（--dry-run 除外）")
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
