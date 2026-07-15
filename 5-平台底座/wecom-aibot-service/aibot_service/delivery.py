"""场景①：按指定跟进信推送（design.md 对应 spec wecom-followup-delivery）。

不做自动扫描触发（Non-Goal，见 design.md）——调用方显式传入定位该行的
`match` 函数，本模块只负责单行的"门禁②断言 → 推送 → 回填"。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from zhuopin_platform.audit import AuditEvent, AuditLogger
from zhuopin_platform.shared_tools.notifiers.wecom_aibot import AibotConnector

from .constants import PAUL_USERID
from .gates import assert_finalized, DeliveryNotFinalizedError
from .readme_table import locate_row, write_status, RowLocation

DELIVERED_STATUS_PREFIX = "✅ 已推送"


class BackfillWriteError(RuntimeError):
    """推送已成功但 README 回填写入失败——不得静默吞掉，需人工核实避免重复推送。"""


@dataclass
class DeliveryResult:
    location: RowLocation
    media_id: Optional[str]
    new_status: str


async def push_followup(
    *,
    readme_path: Path,
    md_path: Path,
    docx_path: Optional[Path],
    connector: AibotConnector,
    chatid: str,
    match: Callable[[list[str]], bool],
    audit: AuditLogger,
    evaluator: str = "system",
    cc_to_paul: bool = True,
) -> DeliveryResult:
    """定位 README 中一行跟进信、断言已定稿、推送、抄送 Paul、回填。

    `cc_to_paul`（Paul 拍板，出站跟进信固定抄送逻辑）：主推送成功后，额外把
    同一份 markdown 正文 + docx 附件私聊发一份给 `PAUL_USERID`，供其掌握
    发送全貌；主送目标本身就是 Paul 时跳过（避免自己抄送自己）。CC 失败
    不影响主推送已成功的事实，只记审计不抛异常（见 `followup_cc_failed`）。

    Raises:
        DeliveryNotFinalizedError: 门禁②拒绝（状态列非"🆕 待发"）。
        BackfillWriteError: 已发送成功但 README 回填失败。
    """
    text = readme_path.read_text(encoding="utf-8")
    loc = locate_row(text, match)
    status_value = loc.cells[loc.status_col_index]

    try:
        assert_finalized(status_value)
    except DeliveryNotFinalizedError as exc:
        audit.record(
            AuditEvent(
                scenario="wecom-aibot",
                action="delivery_rejected",
                evaluator=evaluator,
                automation_level="L1",
                decision={"reason": "not_finalized", "status_value": status_value},
                data_sources={"readme": str(readme_path)},
                error=str(exc),
            )
        )
        raise

    content = md_path.read_text(encoding="utf-8")
    await connector.send_markdown(chatid, content)

    media_id = None
    if docx_path is not None and docx_path.exists():
        upload = await connector.upload_media(docx_path.read_bytes(), docx_path.name)
        media_id = upload.media_id
        await connector.send_file(chatid, media_id)

    audit.record(
        AuditEvent(
            scenario="wecom-aibot",
            action="followup_delivered",
            evaluator=evaluator,
            automation_level="L1",
            decision={"sent": True, "backfilled": False, "media_id": media_id},
            data_sources={"md": str(md_path), "docx": str(docx_path) if docx_path else ""},
        )
    )

    if cc_to_paul and chatid != PAUL_USERID:
        try:
            await connector.send_markdown(PAUL_USERID, f"【抄送】{content}")
            if media_id is not None:
                await connector.send_file(PAUL_USERID, media_id)
            audit.record(
                AuditEvent(
                    scenario="wecom-aibot",
                    action="followup_cc_delivered",
                    evaluator=evaluator,
                    automation_level="L1",
                    decision={"sent": True, "recipient": PAUL_USERID, "cc_of": chatid},
                    data_sources={"md": str(md_path)},
                )
            )
        except Exception as exc:  # noqa: BLE001 —— 抄送失败不影响主推送已成功
            audit.record(
                AuditEvent(
                    scenario="wecom-aibot",
                    action="followup_cc_failed",
                    evaluator=evaluator,
                    automation_level="L1",
                    decision={"recipient": PAUL_USERID, "cc_of": chatid},
                    data_sources={"md": str(md_path)},
                    error=str(exc),
                )
            )

    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    new_status = f"{DELIVERED_STATUS_PREFIX} {timestamp}"

    try:
        new_text = write_status(text, loc, new_status)
        readme_path.write_text(new_text, encoding="utf-8")
    except OSError as exc:
        audit.record(
            AuditEvent(
                scenario="wecom-aibot",
                action="followup_backfill_failed",
                evaluator=evaluator,
                automation_level="L1",
                decision={"sent": True, "backfilled": False},
                data_sources={"readme": str(readme_path)},
                error=str(exc),
            )
        )
        raise BackfillWriteError(
            f"跟进信已推送成功，但 README 回填写入失败（{exc}）——"
            "请人工核对状态列，避免下次误判为待发重复推送"
        ) from exc

    audit.record(
        AuditEvent(
            scenario="wecom-aibot",
            action="followup_backfilled",
            evaluator=evaluator,
            automation_level="L1",
            decision={"sent": True, "backfilled": True, "new_status": new_status},
            data_sources={"readme": str(readme_path)},
        )
    )

    return DeliveryResult(location=loc, media_id=media_id, new_status=new_status)
