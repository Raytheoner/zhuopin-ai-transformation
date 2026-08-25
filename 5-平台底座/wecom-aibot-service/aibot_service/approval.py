"""场景③（新增）：跟进信批准——把 README 状态列从待审草稿态原子转换为
终态（design.md D1，对应 spec wecom-followup-review-state）。

本脚本不发送任何消息——只做状态跃迁；发送仍分别由人工路径
（push_followup_letter.py）或自动路径（dispatch.py 场景④）消费"🆕 待发"
这一终态，职责单一。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from zhuopin_platform.audit import AuditEvent, AuditLogger

from .gates import FINALIZED_STATUS_MARKER
from .readme_table import (
    MAIN_TABLE_SECTION,
    SUPPLEMENT_REPLY_REQUIRED_COLUMN,
    SUPPLEMENT_TABLE_SECTION,
    DraftNotPendingReviewError,
    RowLocation,
    assert_draft_pending_review,
    column_index,
    locate_row,
    strip_unnumbered_annotation,
    write_cells,
)


class SupplementReplyRequiredMissingError(RuntimeError):
    """批准被拒绝：补件行的「需回复」列为空（队列 #399 决策点 5(b)）。

    补件分通知型与签认型两类，**这不是补件形态的属性、而是逐封的属性**
    （2026-08-25 那封同时含「通知（不用回）」与「签认（必须回）」两半，
    正是它逼出这条判据）。它决定发送成功后回填哪个终态，故起草时必填；
    留空即无法判定终态，MUST NOT 猜。
    """

# design 审通过后 Shao Peishen 追加要求①：冷却窗口——拒绝在"首次观测到该
# 行"后 N 分钟内批准，逼出一个独立、蓄意的等待动作，堵住"起草→release→
# 立刻批准"这种同一 actor、中间没有真人的两步连做（见本模块 check_cooldown
# 文档）。
DEFAULT_COOLDOWN_MINUTES = 10


class ApprovalCooldownError(RuntimeError):
    """批准被拒绝：距首次观测到该行仍处于冷却窗口内。"""


@dataclass
class ApprovalResult:
    location: RowLocation
    new_status: str


def _row_identity(loc: RowLocation) -> str:
    """行身份＝除状态列外全部单元格拼接——与 D1 结构性拦截（编辑锁 README
    分支）用的"非状态列身份"判据一致：只要行的其余内容不变，状态列如何
    转换都指向同一行。"""
    return "|".join(c for i, c in enumerate(loc.cells) if i != loc.status_col_index)


def _load_first_seen(state_path: Path) -> dict[str, str]:
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_first_seen(state_path: Path, data: dict[str, str]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def check_cooldown(
    state_path: Path,
    row_identity: str,
    *,
    now: datetime,
    cooldown_minutes: int = DEFAULT_COOLDOWN_MINUTES,
) -> None:
    """冷却窗口检查（Shao Peishen 审 design 追加要求①）。

    不追溯真实起草时刻——本项目没有可靠信源记录"这行是几点几分被起草
    的"（README 编辑不经任何脚本，直接改文件）。改为以"批准脚本第一次
    观测到这一行"作为观测时刻：首次调用必然被拒绝（同时把此刻记为观测
    时刻），第二次调用须距首次观测满 `cooldown_minutes` 分钟才放行。

    这不精确等于真实起草时间，但已达成设计目的——批准动作不能与起草
    动作在同一次连续操作序列里一步做完，必须至少往返调用两次、间隔
    一段刻意的等待。**对存心等够时间的人无效**（design.md 明确接受此
    局限："冷却窗口挡不住刻意等待，但把顺手一起做掉变成必须刻意等"）。
    """
    data = _load_first_seen(state_path)
    seen_at_str = data.get(row_identity)
    if seen_at_str is None:
        data[row_identity] = now.isoformat()
        _save_first_seen(state_path, data)
        raise ApprovalCooldownError(
            f"首次观测到该行，已记录时间戳；请在 {cooldown_minutes} 分钟后重试批准"
            "（冷却窗口机制，防止起草-批准一步到位）"
        )
    seen_at = datetime.fromisoformat(seen_at_str)
    elapsed_minutes = (now - seen_at).total_seconds() / 60
    if elapsed_minutes < cooldown_minutes:
        remaining = cooldown_minutes - elapsed_minutes
        raise ApprovalCooldownError(
            f"距首次观测该行仅 {elapsed_minutes:.1f} 分钟，未满 {cooldown_minutes} "
            f"分钟冷却窗口，还需等待约 {remaining:.1f} 分钟"
        )


def approve_followup_letter(
    *,
    readme_path: Path,
    match: Callable[[list[str]], bool],
    quote: str,
    audit: AuditLogger,
    cooldown_state_path: Path,
    now: datetime,
    cooldown_minutes: int = DEFAULT_COOLDOWN_MINUTES,
    evaluator: str = "human",
    section: str = MAIN_TABLE_SECTION,
) -> ApprovalResult:
    """定位 README 中一行跟进信、断言处于待审草稿态、过冷却窗口、批准转
    终态、留痕。

    `section`（队列 #399）：目标表所属章节标题——主表或《补件登记》表。
    🔴 **补件行复用与正式信完全相同的判据链**（草稿态断言／依据必填／冷却
    窗口／审计留痕），一条都不放宽；补件多出的唯一一条是「需回复」列必填。
    未能确定目标表时 `locate_row` 内部即抛错，MUST NOT 静默落到另一张表。

    Raises:
        ValueError: 未提供批准依据摘录。
        ReadmeTableError: 章节标题匹配不到（fail-loud，不回退到第一个表）。
        DraftNotPendingReviewError: 目标行「发送状态」列非待审草稿标记。
        SupplementReplyRequiredMissingError: 补件行「需回复」列为空。
        ApprovalCooldownError: 距首次观测该行未满冷却窗口。
    """
    if not quote or not quote.strip():
        raise ValueError("批准依据摘录（--quote）不得为空")

    text = readme_path.read_text(encoding="utf-8")
    loc = locate_row(text, match, section)
    status_value = loc.cells[loc.status_col_index]

    try:
        assert_draft_pending_review(status_value)
    except DraftNotPendingReviewError as exc:
        audit.record(
            AuditEvent(
                scenario="wecom-aibot",
                action="followup_approval_rejected",
                evaluator=evaluator,
                automation_level="L1",
                decision={"reason": "not_draft_pending_review", "status_value": status_value},
                data_sources={"readme": str(readme_path)},
                error=str(exc),
            )
        )
        raise

    # 队列 #399 决策点 5(b)：补件表专有判据——「需回复」列必填。放在冷却窗口
    # **之前**：一行内容本身就不合法的补件不该先把冷却计时器跑起来，否则修好
    # 内容后还得再等一轮。
    if section == SUPPLEMENT_TABLE_SECTION:
        reply_idx = column_index(loc.header_cells, SUPPLEMENT_REPLY_REQUIRED_COLUMN)
        reply_value = (
            loc.cells[reply_idx].strip()
            if reply_idx is not None and reply_idx < len(loc.cells)
            else ""
        )
        if not reply_value:
            exc = SupplementReplyRequiredMissingError(
                f"批准被拒绝：补件行「{SUPPLEMENT_REPLY_REQUIRED_COLUMN}」列为空——"
                "它决定发送成功后回填哪个终态（否→`✅ 无需回复`／是→`✅ 已推送 <日期>`），"
                "起草时必填，MUST NOT 由脚本猜测。"
            )
            audit.record(
                AuditEvent(
                    scenario="wecom-aibot",
                    action="followup_approval_rejected",
                    evaluator=evaluator,
                    automation_level="L1",
                    decision={
                        "reason": "supplement_reply_required_missing",
                        "kind": "supplement",
                        "section": section,
                    },
                    data_sources={"readme": str(readme_path)},
                    error=str(exc),
                )
            )
            raise exc

    row_identity = _row_identity(loc)
    try:
        check_cooldown(cooldown_state_path, row_identity, now=now, cooldown_minutes=cooldown_minutes)
    except ApprovalCooldownError as exc:
        audit.record(
            AuditEvent(
                scenario="wecom-aibot",
                action="followup_approval_rejected",
                evaluator=evaluator,
                automation_level="L1",
                decision={"reason": "cooldown_not_elapsed", "row_identity": row_identity},
                data_sources={"readme": str(readme_path)},
                error=str(exc),
            )
        )
        raise

    # 🔴 队列 #400（并入本包）：状态列转终态 ＋ 编号列剥括注 **必须在同一次
    # 写入内完成**。分两次写就多出一个「状态改了、括注没改」的中间态——而那
    # 正是 #400 这个缺陷本身（`采购部#18` 一行两格自相矛盾：编号列自称
    # 「待你审，暂不占号」，状态列已是 `🆕 待发`）。
    #
    # 补件表的首列叫「承接编号」不叫「编号」，`column_index` 取不到，
    # `updates` 里天然只剩状态列一格——补件本就不占号、无括注可剥，
    # 这不是特判，是列名不同带来的结构性结果。
    updates: dict[int, str] = {loc.status_col_index: FINALIZED_STATUS_MARKER}
    number_idx = column_index(loc.header_cells, "编号")
    number_before = ""
    number_after = ""
    if (
        number_idx is not None
        and number_idx != loc.status_col_index
        and number_idx < len(loc.cells)
        and loc.header_cells[number_idx].strip().startswith("编号")
    ):
        number_before = loc.cells[number_idx]
        number_after = strip_unnumbered_annotation(number_before)
        if number_after != number_before:
            updates[number_idx] = number_after

    new_text = write_cells(text, loc, updates)
    readme_path.write_text(new_text, encoding="utf-8")

    audit.record(
        AuditEvent(
            scenario="wecom-aibot",
            action="followup_approved",
            evaluator=evaluator,
            automation_level="L1",
            decision={
                "quote": quote,
                "row_match_topic": row_identity,
                "new_status": FINALIZED_STATUS_MARKER,
                "section": section,
                # 决策点 6(b)：审计并回正式 action 名，补件靠 `kind` 区分，
                # 不另起 action 前缀分裂时间线。
                "kind": "supplement" if section == SUPPLEMENT_TABLE_SECTION else "letter",
                # #400：把「这次到底剥没剥」写进审计——只写「已批准」而不写
                # 编号列前后值，事后无从复核那一格有没有跟着变。
                "number_annotation_stripped": bool(
                    number_after and number_after != number_before
                ),
                "number_before": number_before,
                "number_after": number_after or number_before,
            },
            data_sources={"readme": str(readme_path)},
        )
    )

    return ApprovalResult(location=loc, new_status=FINALIZED_STATUS_MARKER)
