"""场景①：按指定跟进信推送（design.md 对应 spec wecom-followup-delivery）。

不做自动扫描触发（Non-Goal，见 design.md）——调用方显式传入定位该行的
`match` 函数，本模块只负责单行的"门禁②断言 → 推送 → 回填"。
"""
from __future__ import annotations

from dataclasses import dataclass, field
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
    media_id: Optional[str]  # 向后兼容：首个附件的 media_id（无附件为 None）
    new_status: str
    media_ids: list[str] = field(default_factory=list)  # 全部附件的 media_id，含首个


async def push_followup(
    *,
    readme_path: Path,
    md_path: Path,
    docx_path: Optional[Path] = None,
    connector: AibotConnector,
    chatid: str,
    match: Callable[[list[str]], bool],
    audit: AuditLogger,
    evaluator: str = "system",
    cc_to_paul: bool = True,
    extra_attachments: Optional[list[Path]] = None,
    cc_group_chatid: Optional[str] = None,
) -> DeliveryResult:
    """定位 README 中一行跟进信、断言已定稿、推送、抄送 Paul、回填。

    `cc_to_paul`（Paul 拍板，出站跟进信固定抄送逻辑）：主推送成功后，额外把
    同一份 markdown 正文 + 全部附件私聊发一份给 `PAUL_USERID`，供其掌握
    发送全貌；主送目标本身就是 Paul 时跳过（避免自己抄送自己）。CC 失败
    不影响主推送已成功的事实，只记审计不抛异常（见 `followup_cc_failed`）。

    `cc_group_chatid`（队列 #270，群 cc 改走机器人通道）：此前"归属部门群
    也要看一眼"这件事走的是另一套机制——`group_notify.py` + 群机器人
    **webhook**（`department_group_mapping.yaml` keyed，真实 URL 落 `.env`），
    调用点在 `connection.py::on_message` 里的 `notify_department_group(...)`
    （归档成功后通报，与本函数是两条独立路径）。webhook 是单向的——群成员
    的回复进不到任何地方；而智能机器人已是这些群的成员、群里也确实回复过，
    只是 chatid 值本身尚未采集（见 `department_group_chatid_mapping.py`，
    另一条正在并行推进的依赖，与本次改动无关）。故新增本参数：主推送成功
    后，用**同一条机器人 chatid 通道**（`AibotConnector`，而非 webhook）把
    同一份内容再发一份到 `cc_group_chatid`，与 `cc_to_paul` 完全相同的隔离
    模式——群 cc 失败不影响主推送已成功的事实，只记审计（
    `followup_group_cc_delivered`/`followup_group_cc_failed`）不抛异常；主送
    目标本身就是该群时跳过（避免重复发送）。**本参数只负责"给了就发"**——
    是否该发、发到哪个 chatid（部门→群 chatid 映射未配置/为空时的 fail-closed
    跳过判据），由消费 `department_group_chatid_mapping.py` 映射表的调用方
    （`scripts/push_followup_letter.py`/`scripts/dispatch_followup_letters.py`）
    决定并记审计，本函数不重复该判断。**旧 webhook 路径本次未动**——待
    aibot 群 cc 路径真实验证可用后再谈下线 `group_notify.py`。

    `docx_path`/`extra_attachments`（队列 #93，多附件支持）：`docx_path` 保留
    作首个附件的向后兼容位；`extra_attachments` 是额外附件列表（docx/其他
    文件均可），二者按顺序拼接后逐个上传+发送，互不影响彼此成败（单个
    附件上传失败会中断本次推送，同旧行为——附件是正文的一部分，不做"部分
    发送"的静默降级）。

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

    attachments = list(([docx_path] if docx_path is not None else []) + list(extra_attachments or []))
    media_ids: list[str] = []
    for attachment in attachments:
        if attachment is None or not attachment.exists():
            continue
        upload = await connector.upload_media(attachment.read_bytes(), attachment.name)
        media_ids.append(upload.media_id)
        await connector.send_file(chatid, upload.media_id)
    media_id = media_ids[0] if media_ids else None

    audit.record(
        AuditEvent(
            scenario="wecom-aibot",
            action="followup_delivered",
            evaluator=evaluator,
            automation_level="L1",
            decision={"sent": True, "backfilled": False, "media_id": media_id, "media_ids": media_ids},
            data_sources={
                "md": str(md_path),
                "docx": str(docx_path) if docx_path else "",
                "attachments": [str(p) for p in attachments],
            },
        )
    )

    if cc_to_paul and chatid != PAUL_USERID:
        try:
            await connector.send_markdown(PAUL_USERID, f"【抄送】{content}")
            for mid in media_ids:
                await connector.send_file(PAUL_USERID, mid)
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

    if cc_group_chatid and cc_group_chatid != chatid:
        try:
            await connector.send_markdown(cc_group_chatid, f"【抄送】{content}")
            for mid in media_ids:
                await connector.send_file(cc_group_chatid, mid)
            audit.record(
                AuditEvent(
                    scenario="wecom-aibot",
                    action="followup_group_cc_delivered",
                    evaluator=evaluator,
                    automation_level="L1",
                    decision={"sent": True, "recipient": cc_group_chatid, "cc_of": chatid},
                    data_sources={"md": str(md_path)},
                )
            )
        except Exception as exc:  # noqa: BLE001 —— 群抄送失败不影响主推送已成功
            audit.record(
                AuditEvent(
                    scenario="wecom-aibot",
                    action="followup_group_cc_failed",
                    evaluator=evaluator,
                    automation_level="L1",
                    decision={"recipient": cc_group_chatid, "cc_of": chatid},
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

    return DeliveryResult(location=loc, media_id=media_id, new_status=new_status, media_ids=media_ids)
