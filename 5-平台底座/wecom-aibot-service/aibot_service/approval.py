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
    DraftNotPendingReviewError,
    RowLocation,
    assert_draft_pending_review,
    locate_row,
    write_status,
)

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
) -> ApprovalResult:
    """定位 README 中一行跟进信、断言处于待审草稿态、过冷却窗口、批准转
    终态、留痕。

    Raises:
        ValueError: 未提供批准依据摘录。
        DraftNotPendingReviewError: 目标行「发送状态」列非待审草稿标记。
        ApprovalCooldownError: 距首次观测该行未满冷却窗口。
    """
    if not quote or not quote.strip():
        raise ValueError("批准依据摘录（--quote）不得为空")

    text = readme_path.read_text(encoding="utf-8")
    loc = locate_row(text, match)
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

    new_text = write_status(text, loc, FINALIZED_STATUS_MARKER)
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
            },
            data_sources={"readme": str(readme_path)},
        )
    )

    return ApprovalResult(location=loc, new_status=FINALIZED_STATUS_MARKER)
