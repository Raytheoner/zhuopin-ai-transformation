"""场景①：按指定跟进信推送（design.md 对应 spec wecom-followup-delivery）。

不做自动扫描触发（Non-Goal，见 design.md）——调用方显式传入定位该行的
`match` 函数，本模块只负责单行的"门禁②断言 → 推送 → 回填"。
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from zhuopin_platform.audit import AuditEvent, AuditLogger
from zhuopin_platform.shared_tools.notifiers.wecom_aibot import AibotConnector

from .error_text import describe_exception
from .constants import PAUL_USERID
from .gates import assert_finalized, DeliveryNotFinalizedError
from .message_length import (
    CC_PREFIX,
    OversizedMessageError,
    plan_body,
)
from .readme_table import (
    MAIN_TABLE_SECTION,
    NO_REPLY_NEEDED_STATUS,
    SUPPLEMENT_REPLY_REQUIRED_COLUMN,
    SUPPLEMENT_REPLY_REQUIRED_NO,
    SUPPLEMENT_TABLE_SECTION,
    column_index,
    locate_row,
    write_status,
    RowLocation,
)
from .repo_paths import resolve_repo_root

DELIVERED_STATUS_PREFIX = "✅ 已推送"


def resolve_backfill_status(loc: RowLocation, section: str, timestamp: str) -> str:
    """回填时该写哪个终态（队列 #399 决策点 5 答 (b)）。

    - 主表：一律 `✅ 已推送 <时刻>`（既有语义，未改）。
    - 补件表「需回复 ＝ 否」（通知型）：直接置 `✅ 无需回复` —— 它属闭环四态
      之一，**发出即了结，不再需要任何后续人工转态**。
    - 补件表「需回复 ＝ 是」（签认型）：置 `✅ 已推送 <时刻>`，等回件回灌后
      由人转 `📥 已回件并回灌`。

    🔴 读不到「需回复」列时按**签认型**处理（即仍需人来收尾）。两个方向代价
    不对称：误判成通知型会把一封还在等签认的补件直接标成「已了结」，那个签认
    从此在任何机器载体上都无迹可寻；误判成签认型最坏只是多一次人工转态。
    """
    if section != SUPPLEMENT_TABLE_SECTION:
        return f"{DELIVERED_STATUS_PREFIX} {timestamp}"
    reply_idx = column_index(loc.header_cells, SUPPLEMENT_REPLY_REQUIRED_COLUMN)
    reply_value = (
        loc.cells[reply_idx].strip()
        if reply_idx is not None and reply_idx < len(loc.cells)
        else ""
    )
    if reply_value == SUPPLEMENT_REPLY_REQUIRED_NO:
        return NO_REPLY_NEEDED_STATUS
    return f"{DELIVERED_STATUS_PREFIX} {timestamp}"


_NON_FAST_FORWARD_MARKERS = (
    "non-fast-forward", "fetch first", "[rejected]", "Updates were rejected",
)

# 队列 #283：跟进信 md 源文件题头 YAML frontmatter（`---`…`---`），非贪婪
# 匹配到第一个闭合 `---` 行为止；`\r?\n` 兼容 CRLF。
_FRONTMATTER_RE = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.DOTALL)


def _strip_frontmatter(content: str) -> str:
    """剥离**发送内容**里的题头 YAML frontmatter（`status`/`编号`/`配套`/
    `备注`/`合并说明`等内部记账字段），不改动源文件本身——队列 #283 真实
    缺陷：专员私信开头看到的是我方内部状态（如 `status: 待发` 会让她误以
    为这封信还没发出）与队列号/机制术语等内部内容，长期存在（自机器人
    推送机制启用以来所有跟进信都在泄漏）。**只改这里算出的发送内容**，
    `md_path` 指向的源文件不动——docx 附件不受影响（`md2word` 把
    frontmatter 当元数据解析而非正文渲染，本就是干净的，见队列 #283）。

    内容不以 `---` 开头，或找不到闭合的 `---` 行（格式不符合预期）时原样
    返回，不强行处理——宁可保留 frontmatter 这种保守失败，也不能因为解析
    错误把正文内容一起吞掉。"""
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return content
    return content[match.end():].lstrip("\n")


class BackfillWriteError(RuntimeError):
    """推送已成功但 README 回填写入失败——不得静默吞掉，需人工核实避免重复推送。"""


class DeliveryAckError(RuntimeError):
    """企微回执帧 `errcode` 非零——本次发送未被接受，不得回填、不得计入 sent。"""


# 队列 #326：把「已推送」从**假设**改成**观测**。
#
# 🔎 **先把该行原始诊断更正掉（读码取证，2026-08-17）**：#326 立行时判断
# 「企微若在 ACK 里回非零 errcode，当前代码照样记成功、照样回填 `✅ 已推送`」
# ——**这一半不成立**。官方 SDK `aibot/ws.py::WSManager._handle_reply_ack`
# （L511-521）在 `errcode != 0` 时给 ack future `set_exception(RuntimeError)`，
# 而 `client.send_message()` → `send_reply()` 是 await 该 future 的
# （`aibot/client.py` L286-302 / `ws.py` L382-430），**故非零 errcode 会在
# `await connector.send_markdown(...)` 处直接抛出**，根本走不到下面记
# `sent: True` 那一行。`send_file`／`upload_media` 的三个 cmd 走同一条
# `send_reply` ack 原语，同样抛（`upload_media` 另有 upload_id/media_id
# 缺失的显式检查）——这一并回答了 #326 期望产出④。
#
# 🔴 **但真正的缺陷仍然成立，只是位置不同**：`sent: True` 是**字面量**，它
# 今天为真纯属**第三方 SDK 的内部实现选择**（它选择 raise 而不是把帧返回
# 给调用方），本仓库既没有断言、也没有测试把这个前提钉住。SDK 一次升级把
# `set_exception` 改成 `set_result`，`sent: True` 当天就变成谎话，而**审计
# 里连回执体都没存**，事后无从复核——这正是 #326 那句"查出来的证据本身
# 就是错的"。故本函数族做两件事，都不依赖对失败样本的猜测：
#   ⑴ **把回执体存进审计**（`ack` 证据），使"已推送"事后可复核；
#   ⑵ **在本仓库这一侧独立断言 errcode**（纵深防御），SDK 哪天不再抛，
#      这里仍然拦得住，且拦截理由是**观测到的 errcode**，不是假设。
# **判不出就不判**：回执不是 dict、或不含 `errcode` 键时记 `None` 并放行
# ——不把"判不出"伪装成"判为失败"（同 ⑥ `status_map.get(...) is None`
# 不拦的既有惯例）。
def _ack_evidence(ack: object) -> dict:
    """从回执帧提取可写进审计的观测证据。

    返回 `{"errcode": int|None, "errmsg": str|None}`——`errcode` 为 `None`
    表示**判不出**（回执不是 dict，或没有这个键），不是"判为 0"。
    """
    if not isinstance(ack, dict):
        return {"errcode": None, "errmsg": None}
    code = ack.get("errcode")
    return {
        "errcode": code if isinstance(code, int) else None,
        "errmsg": ack.get("errmsg") if isinstance(ack.get("errmsg"), str) else None,
    }


def _assert_ack_accepted(ack: object, *, what: str) -> dict:
    """观测回执码；非零即拒（抛 `DeliveryAckError`）。返回该次的观测证据。"""
    evidence = _ack_evidence(ack)
    if evidence["errcode"] is not None and evidence["errcode"] != 0:
        raise DeliveryAckError(
            f"{what}未被企微接受：errcode={evidence['errcode']}，"
            f"errmsg={evidence['errmsg']!r}——不回填 README、不计入 sent"
        )
    return evidence


@dataclass
class DeliveryResult:
    location: RowLocation
    media_id: Optional[str]  # 向后兼容：首个附件的 media_id（无附件为 None）
    new_status: str
    media_ids: list[str] = field(default_factory=list)  # 全部附件的 media_id，含首个
    backfill_committed: bool = False  # 队列 #289：README 回填是否已自动提交推送
    backfill_commit_error: str = ""  # 未提交成功时的原因，供 audit/日志排查


def _run_git(repo_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo_root, capture_output=True, text=True, encoding="utf-8"
    )


def _is_non_fast_forward(stderr: str) -> bool:
    return any(marker in stderr for marker in _NON_FAST_FORWARD_MARKERS)


def _commit_readme_backfill(readme_path: Path, *, description: str) -> tuple[bool, str]:
    """队列 #289：`push_followup` 回填 README 后自动落库——此前只落磁盘，
    从不 `git commit`，`ZhuopinFollowupDispatchDaily` 每发一封信就稳定
    产出一个孤儿脏文件（#236(2) 孤儿告警的持续来源，而非一次性偶发）。

    与 `queue_appender`/机器人自动追行队列同一范式（"自动机制改文件后
    自己提交"）：`git add` + `git commit` + `git push`；push 遇非快进冲突
    （fetch 后 `git rebase origin/master`）——**不**使用 `queue_git_sync.py`
    那套"reset --mixed + checkout --"的冲突重算策略（队列 #287 已坐实
    那条路径会销毁工作区里与本次操作无关的未提交内容），rebase 失败即
    `git rebase --abort` 回滚到 rebase 前的本地提交状态，本次回填内容
    始终保留在本地这个 commit 里、绝不丢弃，只是暂时没推送成功，交后续
    （下一次 dispatch/人工/#236(2) 孤儿告警）处理。

    返回 `(committed, error)`——`committed=False` 时 `error` 是失败原因，
    调用方只记审计，**不**因此让已经成功的推送失败（磁盘上的回填内容
    本身已经正确、不会造成重复发送风险，未提交只是留痕/持久化层面的
    残留，风险级别低于 `BackfillWriteError`，不适用同等的"必须抛出"处理）。
    """
    repo_root = resolve_repo_root(readme_path, fallback=readme_path.parent)
    try:
        relative_path = readme_path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError as exc:
        return False, f"README 不在解析出的仓库根下：{exc}"

    add = _run_git(repo_root, "add", relative_path)
    if add.returncode != 0:
        return False, add.stderr.strip()
    commit = _run_git(repo_root, "commit", "-m", f"bot(跟进信): {description}")
    if commit.returncode != 0:
        return False, commit.stderr.strip()

    push = _run_git(repo_root, "push", "origin", "master")
    if push.returncode == 0:
        return True, ""
    if not _is_non_fast_forward(push.stderr):
        return False, push.stderr.strip()

    _run_git(repo_root, "fetch", "origin")
    rebase = _run_git(repo_root, "rebase", "origin/master")
    if rebase.returncode != 0:
        _run_git(repo_root, "rebase", "--abort")
        return False, f"推送冲突且 rebase 失败，已回滚保留本地提交：{push.stderr.strip()}"

    push_after_rebase = _run_git(repo_root, "push", "origin", "master")
    if push_after_rebase.returncode == 0:
        return True, ""
    return False, push_after_rebase.stderr.strip()


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
    section: str = MAIN_TABLE_SECTION,
) -> DeliveryResult:
    """定位 README 中一行跟进信、断言已定稿、推送、抄送 Paul、回填。

    `section`（队列 #399）：目标表所属章节标题——主表或《补件登记》表。补件
    走**完全相同**的门禁②与四链路，差别只有两处：① 回填终态按「需回复」列
    分流（见 `resolve_backfill_status`）；② 审计 `decision.kind="supplement"`
    （决策点 6 答 (b)：**并回正式 action 名，不另起前缀分裂时间线**——审计是
    给事后复核「这个人收到过什么」用的，按「用什么脚本发的」分家会逼复核者
    先懂实现细节）。

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

    **长度守卫与超限降级（队列 #416，`OP-0828-B`）**：正文在发出前先过
    `message_length.plan_body`——按**每条实际要发出去的串**（私信是 `content`，
    抄送两处是 `【抄送】`＋`content`，比原文长）算字节；任一条超限即整封降级
    为「提要＋附件」，三条通道发同一份提要；超限且无附件、或提要本身仍超限
    ⇒ 抛 `OversizedMessageError`，**一条都不发**（保住"干净失败、可安全重试"）。

    **执行顺序（队列 #326／`OP-0831-U`）**：主送 → **回填** → 抄送 ShaoPeiShen →
    群抄送——回填被提到两处抄送之前，理由见下方回填代码块前的注释。这意味着
    `BackfillWriteError` 一旦抛出，两处抄送**都不会被尝试**（函数在抄送之前
    就已中止）；这是刻意的取舍，不是遗漏——回填失败本就是本函数定义里最
    危险的状态（唯一防重发屏障没能落地），优先级高于"顺手多抄一份"。

    Raises:
        DeliveryNotFinalizedError: 门禁②拒绝（状态列非"🆕 待发"）。
        OversizedMessageError: 正文超限且无法降级——**发出任何一条之前**抛出，
            审计记 `followup_delivery_failed`（`sent:False／acks:[]`），README 不动。
        BackfillWriteError: 已发送成功但 README 回填写入失败——两处抄送不会
            被尝试（见上）。
    """
    text = readme_path.read_text(encoding="utf-8")
    loc = locate_row(text, match, section)
    status_value = loc.cells[loc.status_col_index]
    # 决策点 6(b)：补件与正式信共用同一套 action 名，靠本字段区分性质。
    kind = "supplement" if section == SUPPLEMENT_TABLE_SECTION else "letter"

    # 队列 #294 修法⑴：门禁②按等值断言实现——一行若处于 `⏸ 暂缓`
    # （readme_table.PAUSED_STATUS，批准后又主动暂缓发送）同样在此被拒绝，
    # 与草稿态一样被结构性排除，不需要为新状态单独加判断分支。
    try:
        assert_finalized(status_value)
    except DeliveryNotFinalizedError as exc:
        audit.record(
            AuditEvent(
                scenario="wecom-aibot",
                action="delivery_rejected",
                evaluator=evaluator,
                automation_level="L1",
                decision={"reason": "not_finalized", "status_value": status_value, "kind": kind},
                data_sources={"readme": str(readme_path)},
                error=describe_exception(exc),
            )
        )
        raise

    content = _strip_frontmatter(md_path.read_text(encoding="utf-8"))
    attachments = list(([docx_path] if docx_path is not None else []) + list(extra_attachments or []))
    media_ids: list[str] = []
    acks: list[dict] = []

    # 队列 #416（`OP-0828-B`）：长度守卫与超限降级——**在发出任何一条之前**
    # 一次性决定这一封发哪份正文，见 `message_length.plan_body` docstring。
    #
    # 🔴 两处边界，改这段前先读懂：
    # ⑴ `cc_channels` 传的是**本次真的会抄送**的通道，条件与下方两个 `if`
    #    逐字相同（不是「有没有传这个参数」）——抄送发的是 `【抄送】` ＋ 正文，
    #    **比原文长**；只按原文算，会出现「私信成功、群里什么都没有」，外观
    #    是发出去了（同族＝#270 那条 fail-closed 静默跳过）。
    # ⑵ 附件清单按**真实存在**的算，与下方上传循环的 `attachment.exists()`
    #    判据一致——降级正文里那句「完整内容在附件里」必须真的成立，
    #    否则降级就成了静默丢内容。
    # 🔴 这两个布尔量是**唯一判据**——下方两处抄送的 `if` 也用它们，绝不
    # 各写一份条件：守卫算的通道集与真正发出去的通道集一旦漂开，就退回到
    # 「只验了私信侧」那个最隐蔽的形态。
    cc_paul_active = bool(cc_to_paul and chatid != PAUL_USERID)
    cc_group_active = bool(cc_group_chatid and cc_group_chatid != chatid)
    cc_channels: list[str] = []
    if cc_paul_active:
        cc_channels.append("抄送ShaoPeiShen")
    if cc_group_active:
        cc_channels.append("群抄送")
    existing_attachments = [
        p for p in attachments if p is not None and p.exists()
    ]

    # 队列 #326：主推送与附件整段包在一个 try 里——此前主推送失败**在本模块内
    # 不留任何审计事件**（只有 `dispatch.py` 批处理侧记 `dispatch_row_failed`，
    # 而人工 CLI `push_followup_letter.py` 那条路径连这个都没有，异常直接冒到
    # 终端、审计日志上一片空白）。现改为在 delivery 这一层就记
    # `followup_delivery_failed`（含观测到的 errcode/errmsg），再原样向上抛，
    # 既不改变调用方看到的异常类型/传播行为，也不再让"发送失败"这件事只存在
    # 于某一条调用路径的记账里。
    try:
        # 守卫放在 try 内、第一条 send 之前：超限时走的是与"发送失败"同一条
        # 审计分支（`followup_delivery_failed`，`sent:False／acks:[]／
        # media_ids:[]／backfilled:False`），README 保持 `🆕 待发`——**这正是
        # #416 那条"失败必须是干净的、可安全重试"的性质，本次修复不得把它
        # 改成半发**（已配单测钉死）。
        plan = plan_body(
            content,
            cc_channels=cc_channels,
            attachment_names=[p.name for p in existing_attachments],
        )
        body = plan.body
        acks.append(
            {"step": "markdown", "chatid": chatid,
             **_assert_ack_accepted(
                 await connector.send_markdown(chatid, body), what="跟进信正文推送")}
        )
        for attachment in attachments:
            if attachment is None or not attachment.exists():
                continue
            upload = await connector.upload_media(attachment.read_bytes(), attachment.name)
            media_ids.append(upload.media_id)
            acks.append(
                {"step": "file", "chatid": chatid, "media_id": upload.media_id,
                 **_assert_ack_accepted(
                     await connector.send_file(chatid, upload.media_id),
                     what=f"附件「{attachment.name}」推送")}
            )
    except Exception as exc:  # noqa: BLE001 —— 记完审计原样重抛，不改变传播行为
        audit.record(
            AuditEvent(
                scenario="wecom-aibot",
                action="followup_delivery_failed",
                evaluator=evaluator,
                automation_level="L1",
                decision={"sent": False, "backfilled": False, "chatid": chatid,
                          "acks": acks, "media_ids": media_ids, "kind": kind},
                data_sources={
                    "md": str(md_path),
                    "readme": str(readme_path),
                    "attachments": [str(p) for p in attachments],
                },
                error=describe_exception(exc),
            )
        )
        raise
    media_id = media_ids[0] if media_ids else None

    audit.record(
        AuditEvent(
            scenario="wecom-aibot",
            action="followup_delivered",
            evaluator=evaluator,
            automation_level="L1",
            # `sent` 仍为 True，但它现在**有据可依**：同一条事件里带着每一步的
            # 回执观测（`acks`），事后可复核"当时企微到底回了什么"，而不是只
            # 留下一个无从证伪的断言（队列 #326）。
            decision={"sent": True, "backfilled": False, "media_id": media_id,
                      "media_ids": media_ids, "acks": acks, "kind": kind,
                      **plan.audit_fields()},
            data_sources={
                "md": str(md_path),
                "docx": str(docx_path) if docx_path else "",
                "attachments": [str(p) for p in attachments],
            },
        )
    )

    # 队列 #326 新形态（`OP-0831-U`，2026-08-31）：回填提到两处抄送**之前**、
    # 紧跟主送之后执行——此前的顺序是"主送→抄送 ShaoPeiShen→群抄送→回填"，
    # 四步之间没有任何事务性可言：调用方进程若在中途被外部杀死（真实实例＝
    # 采购部#21，Cowork 工具调用超时导致子进程随调用结束被杀），后面几步
    # 连同它们各自的审计事件一起静默消失，而"缺了几步"与"从没跑过"在审计
    # 文件里长得一模一样。回填是这条链路里**唯一**防重发的屏障——README
    # 状态列不从 `🆕 待发` 改走，下一班 `ZhuopinFollowupDispatchDaily` 就会
    # 把已经送达的这封信当成待发、再发一遍，专员收到两遍；两处抄送缺失
    # 只是少一份知会，事后能补。**⇒ 让回填成为"进程随时可能被杀也无法
    # 回退"的那一步，必须最先落地，抄送退居其后。**
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    new_status = resolve_backfill_status(loc, section, timestamp)

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
                decision={"sent": True, "backfilled": False, "kind": kind},
                data_sources={"readme": str(readme_path)},
                error=describe_exception(exc),
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
            decision={"sent": True, "backfilled": True, "new_status": new_status, "kind": kind},
            data_sources={"readme": str(readme_path)},
        )
    )

    # 队列 #289：回填成功后自动落库，避免每发一封信就积一个孤儿脏文件。
    # 提交/推送失败不影响本次推送已成功的事实（见 `_commit_readme_backfill`
    # docstring），只记审计，不抛出、不影响返回值语义。
    committed, commit_error = _commit_readme_backfill(
        readme_path, description=f"回填「{loc.cells[0] if loc.cells else ''}」发送状态"
    )
    audit.record(
        AuditEvent(
            scenario="wecom-aibot",
            action="followup_backfill_committed" if committed else "followup_backfill_commit_failed",
            evaluator=evaluator,
            automation_level="L1",
            decision={"committed": committed, "kind": kind},
            data_sources={"readme": str(readme_path)},
            error=commit_error,
        )
    )

    # 🔴 回填已经落地在前——此处往后若进程被杀，损失的至多是"少发一份
    # 抄送/群通报"，不会再触发误判待发、下一班重发。cc_paul/cc_group 各自
    # 独立 try/except，互不影响彼此、也不影响已经成立的主送+回填事实。
    if cc_paul_active:
        try:
            # 队列 #326：抄送同样观测回执码——非零即走下面既有的
            # `followup_cc_failed` 分支（抄送失败本就不影响主推送已成功的
            # 事实，此处只是让"抄送成功"这个断言也有回执作证）。
            cc_acks = [_assert_ack_accepted(
                await connector.send_markdown(PAUL_USERID, f"{CC_PREFIX}{body}"),
                what="抄送正文推送")]
            for mid in media_ids:
                cc_acks.append(_assert_ack_accepted(
                    await connector.send_file(PAUL_USERID, mid), what="抄送附件推送"))
            audit.record(
                AuditEvent(
                    scenario="wecom-aibot",
                    action="followup_cc_delivered",
                    evaluator=evaluator,
                    automation_level="L1",
                    decision={"sent": True, "recipient": PAUL_USERID, "cc_of": chatid,
                              "acks": cc_acks, "kind": kind},
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
                    decision={"recipient": PAUL_USERID, "cc_of": chatid, "kind": kind},
                    data_sources={"md": str(md_path)},
                    error=describe_exception(exc),
                )
            )

    if cc_group_active:
        try:
            # 队列 #326：同上，群抄送的回执码也观测、也进审计。
            group_acks = [_assert_ack_accepted(
                await connector.send_markdown(cc_group_chatid, f"{CC_PREFIX}{body}"),
                what="群抄送正文推送")]
            for mid in media_ids:
                group_acks.append(_assert_ack_accepted(
                    await connector.send_file(cc_group_chatid, mid), what="群抄送附件推送"))
            audit.record(
                AuditEvent(
                    scenario="wecom-aibot",
                    action="followup_group_cc_delivered",
                    evaluator=evaluator,
                    automation_level="L1",
                    decision={"sent": True, "recipient": cc_group_chatid, "cc_of": chatid,
                              "acks": group_acks, "kind": kind},
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
                    decision={"recipient": cc_group_chatid, "cc_of": chatid, "kind": kind},
                    data_sources={"md": str(md_path)},
                    error=describe_exception(exc),
                )
            )

    return DeliveryResult(
        location=loc, media_id=media_id, new_status=new_status, media_ids=media_ids,
        backfill_committed=committed, backfill_commit_error=commit_error,
    )


# ============================================================================
# 队列 #326 新形态（`OP-0831-U`，2026-08-31）：发送完整性自检
#
# 审计只记「已完成的动作」，不记「本应发生而未发生」——调用方进程被外部
# 杀死时，未及执行的步骤不会留下任何痕迹，"缺 N 条"与"从没跑过"在审计
# 文件里长得一模一样。下面两个函数把这条判据变成可编程的检查：给定
# "这次投递期望发生哪几步"（由调用方按 chatid/department 算出，与
# `push_followup` 内部 `cc_paul_active`/`cc_group_active` 必须同一份判据）
# 与"审计里实际留下了哪几步的记录"（成功、失败任一变体都算"有据可查"——
# 失败本身就是一种交代，只有一条记录都没有才是真正的静默缺口），报告
# 真正缺了什么。
#
# 🔴 刻意设计成**读已落盘的审计文件**、不依赖任何进程内状态——本函数族
# 存在的理由就是"调用方进程可能已经不在了"，所以必须能在一次完全独立的
# 后续调用里跑（见 `scripts/push_followup_letter.py --verify-only`），
# 而不是只在 `push_followup` 自己正常返回时才顺手查一遍那种"进程都被杀了
# 就跑不到"的自检——那种自检当然也做了（`_run` 成功路径同样会调它），
# 但它只能覆盖"跑完了但某步审计没写上"这类罕见情形，覆盖不了本行真正
# 在治的那种"跑到一半整个进程消失"。
# ============================================================================

# 每一步的 (成功 action, 失败 action)——出现任一个都算"有据可查"。
STEP_ACTIONS: dict[str, tuple[str, str]] = {
    "main": ("followup_delivered", "followup_delivery_failed"),
    "backfill": ("followup_backfilled", "followup_backfill_failed"),
    "cc_paul": ("followup_cc_delivered", "followup_cc_failed"),
    "cc_group": ("followup_group_cc_delivered", "followup_group_cc_failed"),
}

STEP_LABELS: dict[str, str] = {
    "main": "①私信+docx",
    "backfill": "④回填README",
    "cc_paul": "②抄送ShaoPeiShen",
    "cc_group": "③部门群抄送",
}


@dataclass
class CompletenessReport:
    expected: list[str]
    missing: list[str]

    @property
    def ok(self) -> bool:
        return not self.missing

    def describe_missing(self) -> str:
        return "、".join(STEP_LABELS[step] for step in self.missing)


def _normalize_for_comparison(path_text: str, repo_root: Path | None) -> str:
    """把路径字符串归一化为「仓库根相对路径＋正斜杠」，用于跨调用比较是否
    指向同一份文件——不依赖磁盘上文件是否仍存在（`Path.resolve()` 默认
    `strict=False`），只做字符串/分隔符层面的对齐。

    队列 #326 `OP-0831-V` 实证：`push_followup` 写审计时原样存调用方传入的
    `md_path`（可能是相对，也可能是绝对，取决于当次调用者的习惯），而
    `slice_latest_attempt` 原实现用字符串 `==` 精确匹配——只要两次调用的
    路径写法不是逐字节相同（最常见即"发送传相对、核验传绝对"），恒不相等，
    与"这个 md 从没被推送过"在返回值上完全无法区分（同"缺了"与"没跑过"
    长得一样的判据族）。

    `repo_root=None`（未知仓库根）时原样返回，保留旧行为——仅字符串比较，
    不因新增的归一化逻辑改变没有仓库根语境的既有调用方（如单测里直接
    构造记录、两侧本就用同一字面量）的判定结果。归一化本身失败（如路径
    确实不在仓库树内、或跨盘符）时也原样返回，不让"判断两个路径是否
    相同"这件事本身抛错中断自检。
    """
    if repo_root is None:
        return path_text
    candidate = Path(path_text)
    try:
        if not candidate.is_absolute():
            candidate = repo_root / candidate
        return candidate.resolve().relative_to(repo_root.resolve()).as_posix()
    except (ValueError, OSError):
        return path_text.replace("\\", "/")


def slice_latest_attempt(
    records: list[dict], *, md_path: str, repo_root: Path | None = None,
) -> list[dict]:
    """从全量审计记录（`audit.query_by(scenario="wecom-aibot")`，天然按落盘
    顺序＝时间顺序）里截出"最近一次"针对 `md_path` 的推送尝试切片。

    锚点＝最后一条 `data_sources.md == md_path`（按 `repo_root` 归一化后
    比较，见 `_normalize_for_comparison`）的 `followup_delivered`／
    `followup_delivery_failed`；切片范围＝从锚点起（含）到下一条**任意**
    md 的主送事件之前（不含），或到记录末尾——`zhuopin-send-followup`
    §0 的串行原则决定了同一时刻只应有一次在途推送，故"下一条主送事件"
    天然是下一次尝试的边界，不需要更复杂的相关性判据（如自造 attempt id）。
    找不到锚点（这个 md 从未被推送过，或 audit 路径不对）返回空列表。

    `repo_root` 应传调用方已解析好的仓库根（见 `push_followup_letter.py`
    的 `resolved_repo_root`）——本函数不自行解析，避免与调用方各解一遍
    可能解出两个不同仓库根（同队列 #126 缺陷②的教训）。不传时退化为原始
    字符串精确匹配，向后兼容不依赖本参数的既有调用方。
    """
    needle = _normalize_for_comparison(md_path, repo_root)
    anchor = None
    for i, r in enumerate(records):
        if r.get("action") not in STEP_ACTIONS["main"]:
            continue
        recorded = r.get("data_sources", {}).get("md")
        if recorded is not None and _normalize_for_comparison(recorded, repo_root) == needle:
            anchor = i  # 同一 md 若被重试过多次，取最后一次
    if anchor is None:
        return []
    end = len(records)
    for j in range(anchor + 1, len(records)):
        if records[j].get("action") in STEP_ACTIONS["main"]:
            end = j
            break
    return records[anchor:end]


def check_delivery_completeness(
    records: list[dict], *, expect_cc_paul: bool, expect_group_cc: bool,
) -> CompletenessReport:
    """`records` 须已是"这一次推送尝试"的审计切片（见 `slice_latest_attempt`）。

    `main`／`backfill` 恒为期望项——门禁②拒绝的行根本不会走到主送这一步，
    调用方不该对那种行跑本检查；`cc_paul`／`cc_group` 是否期望，由调用方
    按当次参数算出（是否传了 `--department`、主送目标是不是恰好就是
    ShaoPeiShen／该群本身），必须与 `push_followup` 内部
    `cc_paul_active`／`cc_group_active` 同一份判据，否则会把"这次本就不
    该抄"误报成"缺了"。
    """
    present = {r.get("action") for r in records}
    expected = ["main", "backfill"]
    if expect_cc_paul:
        expected.append("cc_paul")
    if expect_group_cc:
        expected.append("cc_group")
    missing = [step for step in expected if not (present & set(STEP_ACTIONS[step]))]
    return CompletenessReport(expected=expected, missing=missing)
