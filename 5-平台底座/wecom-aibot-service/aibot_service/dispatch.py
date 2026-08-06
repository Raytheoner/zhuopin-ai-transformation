"""场景④（新增）：每日批处理扫描并发送已批准跟进信（design.md D2/D3，
对应 spec wecom-followup-auto-dispatch）。

扫描 README 全表「发送状态」严格等于 `🆕 待发` 的行，跳过标注
`🔒人工发送` 的行，逐行复用既有 `delivery.push_followup` 完成发送与状态
回填；单行失败（含收件人/文件解析失败）不阻塞其余行。不做自动扫描是
`delivery.py` 自身的 Non-Goal（该模块本就要求"调用方显式指定"），本模块
正是那个调用方——只不过调用方是批处理循环，逐行推导出 `chatid`/
`md_path`/`docx_path` 后再调用，而非人工在 CLI 上敲一次。

队列 #294 修法⑴：`⏸ 暂缓` 态（`readme_table.PAUSED_STATUS`）单独识别并
留痕（见 `DispatchOutcome.skipped_paused`），与草稿态等其它非终态的静默
跳过区分开——该状态曾经历过批准，更容易被后续读者误当"待发"沿用旧
假设，值得单独可观测。

**行→文件/收件人的推导**（README 本身不存字面路径/chatid，只有约定俗成
的命名律）：
- 收件人 userid：从"收信人"列（如"质量部 · 陈忱（可分担朱映桦）"）取
  "·"后、遇"（"/"("截断前的主名，映射到已知的五位专员/IT userid（同
  `whitelist.py`/`department_mapping.yaml` 既有真实值）。未知姓名一律
  跳过+记失败原因，不臆造。
- 文件路径：**优先**读"主要事项"列里队列 #241 标注的目标文件名
  （`readme_table.extract_target_filename`，起草时统一写入）直接定位；
  未标注的历史行回落按 R4 命名律 `<部门>-<姓名>-跟进-<日期>-*.md` 在
  README 同目录下 glob——零匹配或多于一个匹配（歧义）一律跳过+记失败
  原因，不猜（这条兜底判据本身在同日多封时必然歧义，正是 #241 要根治
  的场景，标注优先后只作向后兼容）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

from zhuopin_platform.audit import AuditEvent, AuditLogger
from zhuopin_platform.shared_tools.notifiers.wecom_aibot import AibotConnector

from .delivery import BackfillWriteError, DeliveryNotFinalizedError, push_followup
from .department_group_chatid_mapping import resolve_group_cc_chatid
from .gates import FINALIZED_STATUS_MARKER
from .readme_table import (
    PAUSED_STATUS,
    column_index,
    extract_target_filename,
    iter_rows,
    split_department_and_name,
)

# design.md D3（既有）：硬截止交付的跟进信显式标注，自动任务结构性跳过。
MANUAL_ONLY_MARKER = "🔒人工发送"

# design 审通过后 Shao Peishen 追加要求②：交期要点列若含"明确日期"（严格
# YYYY-MM-DD，不识别"本周五"/"8月初"等相对表述——那类表述本身不构成"明确
# 日期"，是本函数刻意收窄的边界，写在此处供未来扩展参考）且距今 < 此天数、
# 而该行未标 `🔒人工发送`，视为疑似漏标硬截止，结构性跳过并告警。
IMMINENT_DEADLINE_WINDOW_DAYS = 3
_EXPLICIT_DATE_RE = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")

# 已知收件人姓名 → 企微 userid（与 whitelist.py/department_mapping.yaml
# 现有真实值保持同源，不新造第二套映射维护）。
KNOWN_RECIPIENT_USERIDS = {
    "姚祖怡": "YaoZuYi",
    "唐燕萍": "tangyanping",
    "陈忱": "ChenChen",
    "王泓钦": "Hongqin.Wang",
    "泓钦": "Hongqin.Wang",
    "陈承": "2023458",
}


@dataclass
class DispatchOutcome:
    sent: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    skipped_manual: list[str] = field(default_factory=list)
    skipped_unmarked_deadline: list[str] = field(default_factory=list)
    skipped_paused: list[str] = field(default_factory=list)


def _extract_explicit_dates(text: str) -> list[date]:
    dates: list[date] = []
    for m in _EXPLICIT_DATE_RE.finditer(text):
        try:
            dates.append(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
        except ValueError:
            continue
    return dates


def has_unmarked_imminent_deadline(
    deadline_cell: str,
    today: date,
    window_days: int = IMMINENT_DEADLINE_WINDOW_DAYS,
) -> bool:
    """交期要点列含临近（含已过期，用绝对值判定——已过期未标记的行更需
    要人工介入，而非静默当自动行处理）明确日期、但未标 `🔒人工发送`。"""
    if MANUAL_ONLY_MARKER in deadline_cell:
        return False
    return any(
        abs((d - today).days) < window_days for d in _extract_explicit_dates(deadline_cell)
    )


def _resolve_letter_files(
    letters_dir: Path, department: str, name: str, date_str: str,
) -> tuple[Optional[Path], Optional[Path]]:
    """按 R4 命名律 `<部门>-<姓名>-跟进-<日期>-*.md` 唯一匹配；零匹配/多
    匹配均视为无法解析（返回 (None, None)），不猜哪个是正确文件。

    队列 #241：仅在 README 行未标注目标文件名（`readme_table.extract_
    target_filename` 返回 None）时才走到这条 glob 判据——同日多封给同一
    收信人时，这条判据本身就会命中多个候选、必然歧义，这正是 #241 的
    触发场景，判据侧的根治是标注优先，本函数只作向后兼容的兜底。"""
    pattern = f"{department}-{name}-跟进-{date_str}-*.md"
    matches = sorted(letters_dir.glob(pattern))
    if len(matches) != 1:
        return None, None
    md_path = matches[0]
    docx_path = md_path.with_suffix(".docx")
    return md_path, (docx_path if docx_path.exists() else None)


def _resolve_letter_file_by_name(
    letters_dir: Path, filename: str,
) -> tuple[Optional[Path], Optional[Path]]:
    """队列 #241：README 行标注了目标文件名时按文件名直接定位，不再走
    「收信人＋日期」glob 猜测。文件不存在即视为无法解析（标注失效——如
    被改名/移动），不静默回退到旧的猜测逻辑：「标注说是这个、实际发的是
    猜出来的另一个」比"安全跳过"更危险，不可取。"""
    md_path = letters_dir / filename
    if not md_path.exists():
        return None, None
    docx_path = md_path.with_suffix(".docx")
    return md_path, (docx_path if docx_path.exists() else None)


def _record(audit: AuditLogger, action: str, evaluator: str, preview: str, **extra) -> None:
    audit.record(
        AuditEvent(
            scenario="wecom-aibot",
            action=action,
            evaluator=evaluator,
            automation_level="L1",
            decision={"row_preview": preview, **extra},
            data_sources={},
        )
    )


async def dispatch_followup_letters(
    *,
    readme_path: Path,
    connector: AibotConnector,
    audit: AuditLogger,
    today: date,
    evaluator: str = "system",
    group_chatid_mapping: Optional[dict[str, str]] = None,
) -> DispatchOutcome:
    """扫描一遍 README，逐行处理，单行失败不阻塞其余行（design.md 既有
    Requirement）。返回本轮成功/失败/两类跳过的汇总——批次结束后由调用方
    （脚本）决定是否需要告警（如疑似漏标硬截止时通知人工）。

    `group_chatid_mapping`（队列 #270，可选）：调用方（
    `scripts/dispatch_followup_letters.py`）从
    `department_group_chatid_mapping.load_department_group_chatid_mapping()`
    加载后传入，本函数据此按行推导出的 `department` 调用
    `resolve_group_cc_chatid` 决定是否给 `push_followup()` 传
    `cc_group_chatid`——未配置该映射表（保持默认 `None`）时不做任何群 cc
    尝试、不产生额外审计噪音（同旧调用方行为完全一致，向后兼容）；传入
    映射表（即便是空 dict）则按行 fail-closed 判定并留痕。"""
    outcome = DispatchOutcome()
    text = readme_path.read_text(encoding="utf-8")
    rows = iter_rows(text)
    if not rows:
        return outcome

    header_cells = rows[0].header_cells
    deadline_idx = column_index(header_cells, "交期要点")
    date_idx = column_index(header_cells, "日期")
    recipient_idx = column_index(header_cells, "收信人")
    topic_idx = column_index(header_cells, "主要事项")
    letters_dir = readme_path.parent

    for row in rows:
        status_value = row.cells[row.status_col_index].strip()
        preview = " / ".join(c for c in row.cells[:3] if c)

        if status_value == PAUSED_STATUS:
            # 队列 #294：批准后又主动暂缓发送的行——显式识别并留痕，不与
            # 草稿等其它非终态混在同一条静默 continue 里。#294 真实事故：
            # "暂不发"这个决定只写在队列文件里，README 状态列却仍是
            # FINALIZED_STATUS_MARKER，机制照发；此状态存在正是让这个
            # 决定本身也能被机制读到，故单独可观测（区别于草稿态——那
            # 从未被批准过，没有"曾经以为已批准"的误用风险）。
            outcome.skipped_paused.append(preview)
            _record(audit, "dispatch_skipped_paused", evaluator, preview)
            continue
        if status_value != FINALIZED_STATUS_MARKER:
            continue

        deadline_cell = (
            row.cells[deadline_idx] if deadline_idx is not None and deadline_idx < len(row.cells) else ""
        )
        if MANUAL_ONLY_MARKER in deadline_cell:
            outcome.skipped_manual.append(preview)
            _record(audit, "dispatch_skipped_manual", evaluator, preview)
            continue
        if has_unmarked_imminent_deadline(deadline_cell, today):
            outcome.skipped_unmarked_deadline.append(preview)
            _record(
                audit, "dispatch_skipped_unmarked_deadline", evaluator, preview,
                deadline_cell=deadline_cell,
            )
            continue

        recipient_cell = (
            row.cells[recipient_idx] if recipient_idx is not None and recipient_idx < len(row.cells) else ""
        )
        date_cell = row.cells[date_idx] if date_idx is not None and date_idx < len(row.cells) else ""
        topic_cell = row.cells[topic_idx] if topic_idx is not None and topic_idx < len(row.cells) else ""
        department, name = split_department_and_name(recipient_cell)
        chatid = KNOWN_RECIPIENT_USERIDS.get(name) if name else None

        # 队列 #241：标注优先——README 行若在"主要事项"列携带目标文件名
        # （起草时统一由 readme_table.build_target_file_annotation 写入），
        # 直接按文件名定位，不再仅凭「收信人＋日期」猜测（同日多封必然
        # 歧义）。未标注的历史行回落旧判据，向后兼容。
        target_filename = extract_target_filename(topic_cell)
        if target_filename:
            md_path, docx_path = _resolve_letter_file_by_name(letters_dir, target_filename)
        else:
            md_path, docx_path = (
                _resolve_letter_files(letters_dir, department, name, date_cell)
                if department and name and date_cell
                else (None, None)
            )

        if chatid is None:
            reason = f"无法解析收件人 chatid（收信人列：{recipient_cell!r}）"
            outcome.failed.append((preview, reason))
            _record(audit, "dispatch_row_skipped_unresolvable", evaluator, preview, reason=reason)
            continue
        if md_path is None:
            if target_filename:
                reason = f"标注的目标文件不存在：{target_filename!r}"
            else:
                reason = f"无法唯一定位对应 .md 文件（部门={department}/姓名={name}/日期={date_cell}）"
            outcome.failed.append((preview, reason))
            _record(audit, "dispatch_row_skipped_unresolvable", evaluator, preview, reason=reason)
            continue

        # 身份判据用"除状态列外全部单元格"——与 approval.py._row_identity/
        # 编辑锁 README 结构校验分支一致，跨迭代（前面行已改写文本、行号
        # 已偏移）仍能稳定重新定位到同一行。
        identity_cells = tuple(c for i, c in enumerate(row.cells) if i != row.status_col_index)

        def _match(cells: list[str], _identity=identity_cells, _idx=row.status_col_index) -> bool:
            return tuple(c for i, c in enumerate(cells) if i != _idx) == _identity

        # 队列 #270：group_chatid_mapping 未传入（默认 None）时完全不触碰
        # 群 cc 判据，向后兼容旧调用方；传入后按本行推导出的 department
        # fail-closed 判定（未配置/为空一律跳过并由 resolve_group_cc_chatid
        # 记审计），不静默假装"这行不该有群 cc"。
        cc_group_chatid = (
            resolve_group_cc_chatid(
                department=department, mapping=group_chatid_mapping, audit=audit, evaluator=evaluator,
            )
            if group_chatid_mapping is not None
            else None
        )

        try:
            await push_followup(
                readme_path=readme_path,
                md_path=md_path,
                docx_path=docx_path,
                connector=connector,
                chatid=chatid,
                match=_match,
                audit=audit,
                evaluator=evaluator,
                cc_group_chatid=cc_group_chatid,
            )
            outcome.sent.append(preview)
        except (DeliveryNotFinalizedError, BackfillWriteError) as exc:
            # push_followup 内部已就这两类失败各自记过审计，此处只汇总批次结果
            outcome.failed.append((preview, str(exc)))
        except Exception as exc:  # noqa: BLE001 —— 单行失败不得阻塞其余行
            outcome.failed.append((preview, str(exc)))
            _record(audit, "dispatch_row_failed", evaluator, preview, error=str(exc))

    _record(
        audit, "dispatch_batch_summary", evaluator, "",
        sent=len(outcome.sent), failed=len(outcome.failed),
        skipped_manual=len(outcome.skipped_manual),
        skipped_unmarked_deadline=len(outcome.skipped_unmarked_deadline),
    )
    return outcome
