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
from zhuopin_platform.shared_tools import followup_gate
from zhuopin_platform.shared_tools.notifiers.wecom_aibot import AibotConnector

from .constants import PAUL_USERID
from .gates import assert_finalized, FINALIZED_STATUS_MARKER, DeliveryNotFinalizedError
from .readme_table import (
    build_closure_form_snapshot,
    column_index,
    extract_closure_form,
    locate_row,
    write_status,
    RowLocation,
)
from .repo_paths import resolve_repo_root

DELIVERED_STATUS_PREFIX = "✅ 已推送"

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


# ---------------------------------------------------------------------------
# 回填：保留式 ＋ 闭环形态快照（队列 #353；openspec
# `followup-closure-form-survives-backfill`，Shao Peishen 2026-08-25 签认六点）
# ---------------------------------------------------------------------------
#
# ## 改掉的是什么
#
# 回填此前是**整格覆盖**（`write_status` 直接 `cells[i] = new_status`），于是
# 起草时写在状态格里的任何东西，在发送那一刻一律消失。`质量部#7` 那格「两态
# 并列」正是人手工补上的补丁，而那时机器已经抹过一次了。
#
# 现改为**保留式**，形态**逐字沿用 S4 桥一已在生产上跑着的范式**
# （`followup_readme_bridge.build_reply_arrived_status`）：新前缀在最前（闭环
# 判据一律按前缀比对），既有内容以 `　━━━　` 分段接在其后。**不新造第二种
# 分段范式**——两个分隔字面量都从 `followup_gate` 取。
#
# ## 决策点 2(a)：标注合法 ⇒ 回填首段直接写闭环态
#
# Shao Peishen 2026-08-24 夜答、08-25 登记：**(a) 发出即闭环、串行闸当场开**，
# 并一并签认护栏「只有标注在批准那一刻已存在时才生效」。⇒ 起草时判定为
# `✅ 无需回复` 的信，回填后 `质量部#7 → #8` 那次的 `串行豁免：` 不再需要。
# 🔴 **`✅ 已推送 <UTC>` 这个事实不丢**——它作为一个独立分段留在格内，因为
# 「这封信是什么时候推送的」在这一格之外没有任何副本（同桥一 docstring 的
# 理由）。
#
# ## 决策点 5(c)：快照即防线
#
# 快照是**回填那一刻**从「主要事项」列复制过来的。此后闸只读状态格，信发出
# 之后再往「主要事项」补写标注 ⇒ 对闸零效果。**不新增任何拒绝写入的门禁。**
#
# ## 两条如实登记的边界（apply 中实测发现，未自行改判）
#
# 1. **「保留式」在 `push_followup` 这条路径上实际不可达**：门禁②
#    （`gates.assert_finalized`）按**等值**断言，`status_value.strip()` 必须
#    恰为 `🆕 待发` 才走得到回填 ⇒ 到回填时原状态格里**不可能**有附加内容。
#    ⇒ proposal「已知未闭合 2」写的「决策点 3 签认后 `⏸ 暂缓` 的暂缓理由
#    顺带被治好」**不成立**：那条理由是在「人工把 `⏸ 暂缓` 改回 `🆕 待发`」
#    那一步被抹掉的，根本轮不到回填。保留式仍照实现（本函数是通用的、并配
#    单测），但它在当前链路上是**空转**的。**不自行改判**——治它必须动
#    `assert_finalized` 的等值断言（D8 红线）或 `approval.py`，两者都在本包
#    design「不做的事」里。
# 2. **护栏文字与结构实现之间有一个窗口**：签认文本是「标注在**批准**那一刻
#    已存在」，而快照发生在**回填**那一刻 ⇒ 「批准 → 投递」之间补写的标注
#    仍会被采信。在批准那一步写快照同样要放宽 `assert_finalized`（D8 红线），
#    故本包不做，如实登记。


def build_backfill_status(
    previous_status: str,
    closure: Optional[followup_gate.ClosureForm],
    *,
    timestamp: str,
) -> str:
    """算出回填后「发送状态」格的新值。纯函数、无副作用，便于直接单测。

    - **无合法标注** ⇒ 返回 `✅ 已推送 <UTC>`，与本变更前**逐字相同**
      （不多出空分隔符）——53 行历史行与全部未标注的新信走的都是这条。
    - **有合法标注** ⇒ 首段写该闭环态（决策点 2(a)），其后依次接
      **发出时快照** 与 `✅ 已推送 <UTC>` 事实段。
    - `previous_status` 去掉装饰后不等于 `🆕 待发` 时，整段原状态以
      `　━━━　原状态 ━━━　` 接在最后（保留式；见上文边界 1）。
    """
    delivered = f"{DELIVERED_STATUS_PREFIX} {timestamp}"
    if closure is None:
        parts = [delivered]
    else:
        parts = [
            f"{closure.form} {timestamp}"
            f"（企微机器人自动回填：起草时已判定本封**发出即闭环**，串行闸当场开"
            f"——队列 #353 决策点 2(a)；闸采信的是下面那段**发出时快照**，"
            f"发出后再改「主要事项」列的标注对闸零效果）",
            build_closure_form_snapshot(closure.form, closure.basis),
            delivered,
        ]

    kept = (previous_status or "").strip()
    if kept and kept != FINALIZED_STATUS_MARKER:
        # 与桥一／桥二逐字同形：`　━━━　原状态 ━━━　<原状态>`。
        parts.append(f"{followup_gate.PREVIOUS_STATUS_LABEL} ━━━　{kept}")

    return followup_gate.PRESERVED_SEGMENT_SEPARATOR.join(parts)


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
                decision={"reason": "not_finalized", "status_value": status_value},
                data_sources={"readme": str(readme_path)},
                error=str(exc),
            )
        )
        raise

    content = _strip_frontmatter(md_path.read_text(encoding="utf-8"))
    attachments = list(([docx_path] if docx_path is not None else []) + list(extra_attachments or []))
    media_ids: list[str] = []
    acks: list[dict] = []

    # 队列 #326：主推送与附件整段包在一个 try 里——此前主推送失败**在本模块内
    # 不留任何审计事件**（只有 `dispatch.py` 批处理侧记 `dispatch_row_failed`，
    # 而人工 CLI `push_followup_letter.py` 那条路径连这个都没有，异常直接冒到
    # 终端、审计日志上一片空白）。现改为在 delivery 这一层就记
    # `followup_delivery_failed`（含观测到的 errcode/errmsg），再原样向上抛，
    # 既不改变调用方看到的异常类型/传播行为，也不再让"发送失败"这件事只存在
    # 于某一条调用路径的记账里。
    try:
        acks.append(
            {"step": "markdown", "chatid": chatid,
             **_assert_ack_accepted(
                 await connector.send_markdown(chatid, content), what="跟进信正文推送")}
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
                          "acks": acks, "media_ids": media_ids},
                data_sources={
                    "md": str(md_path),
                    "readme": str(readme_path),
                    "attachments": [str(p) for p in attachments],
                },
                error=str(exc),
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
                      "media_ids": media_ids, "acks": acks},
            data_sources={
                "md": str(md_path),
                "docx": str(docx_path) if docx_path else "",
                "attachments": [str(p) for p in attachments],
            },
        )
    )

    if cc_to_paul and chatid != PAUL_USERID:
        try:
            # 队列 #326：抄送同样观测回执码——非零即走下面既有的
            # `followup_cc_failed` 分支（抄送失败本就不影响主推送已成功的
            # 事实，此处只是让"抄送成功"这个断言也有回执作证）。
            cc_acks = [_assert_ack_accepted(
                await connector.send_markdown(PAUL_USERID, f"【抄送】{content}"),
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
                              "acks": cc_acks},
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
            # 队列 #326：同上，群抄送的回执码也观测、也进审计。
            group_acks = [_assert_ack_accepted(
                await connector.send_markdown(cc_group_chatid, f"【抄送】{content}"),
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
                              "acks": group_acks},
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

    # 队列 #353：从「主要事项」列取起草时写下的闭环形态标注，回填时按决策点
    # 2(a) 直接写闭环态并把标注**快照**进状态格。取不到（历史行常态）时下面
    # 算出来的 `new_status` 与本变更前逐字相同。
    # 🔴 **越界/缺依据不静默**：`parse_closure_form` 返回 violation 时按无标注
    # 处理（闸仍锁，保守方向），但把它记进审计——否则一条写错的标注会以
    # 「什么都没发生」的形态消失，正是本包要治的那种静默。
    topic_col = column_index(loc.header_cells, "主要事项")
    topic_cell = (
        loc.cells[topic_col]
        if topic_col is not None and len(loc.cells) > topic_col else ""
    )
    closure_parse = extract_closure_form(topic_cell)
    if closure_parse.violation:
        audit.record(
            AuditEvent(
                scenario="wecom-aibot",
                action="followup_closure_form_rejected",
                evaluator=evaluator,
                automation_level="L1",
                decision={"reason": "invalid_closure_form_annotation",
                          "treated_as": "unannotated"},
                data_sources={"readme": str(readme_path)},
                error=closure_parse.violation,
            )
        )
        print(f"⚠ 闭环形态标注未生效：{closure_parse.violation}")

    new_status = build_backfill_status(
        status_value, closure_parse.form, timestamp=timestamp
    )

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
            decision={"sent": True, "backfilled": True, "new_status": new_status,
                      # 队列 #353：快照写没写、写的是什么，进审计（IATF 可追溯）。
                      "closure_form": closure_parse.form.form if closure_parse.form else None,
                      "closure_form_basis": closure_parse.form.basis if closure_parse.form else None},
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
            decision={"committed": committed},
            data_sources={"readme": str(readme_path)},
            error=commit_error,
        )
    )

    return DeliveryResult(
        location=loc, media_id=media_id, new_status=new_status, media_ids=media_ids,
        backfill_committed=committed, backfill_commit_error=commit_error,
    )
