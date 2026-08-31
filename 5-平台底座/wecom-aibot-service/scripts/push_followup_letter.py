"""场景①手动触发工具（design.md Non-Goal：不做自动扫描，必须由调用方显式
指定具体某一封信）。CC/专线人工判断某封跟进信已就绪（README 状态列为
"🆕 待发"）后，用本脚本触发推送——读 md 正文（+ 可选 docx 附件）经智能
机器人发到指定会话，成功后自动回填 README 状态列。

用法：
  python scripts/push_followup_letter.py \
    --readme "<README-跟进机制与命名约定.md 路径>" \
    --md "<跟进信 .md 路径>" \
    [--docx "<跟进信 .docx 路径>"] \
    [--attachment "<其它附件路径>" [--attachment "<第三个附件路径>" ...]] \
    --chatid "<企微群/用户 chatid>" \
    --match-topic "<README「主要事项」列的唯一定位关键字>" \
    [--department "<归属部门，如 财务部/质量部/采购部>"]

队列 #93（多附件支持）：一次推送若需带多份材料，`--docx` 仍是首个附件的
向后兼容位，`--attachment` 可重复传入以追加更多附件（docx/其他文件均
可），不必再像此前那样拆成多次推送。

队列 #326 新形态（`OP-0831-U`）：加 `--verify-only` 且其余参数不变地重跑
同一条命令，可核验上一次针对该 `--md` 的推送尝试是否四条链路（私信+docx／
回填README／抄送ShaoPeiShen／部门群抄送）齐全——不发送，只读审计文件，
缺哪条就报哪条并非零退出（exit 3）。用于怀疑上一次调用中途被外部杀死
（如工具调用超时把子进程一起杀掉）之后的事后核验；正常推送成功后也会
自动跑一遍同样的核验（exit 0＝齐全，exit 3＝有缺口）。

队列 #270（群 cc 改走机器人通道）：`--department` 可选，提供后额外把同一份
内容经机器人 chatid 通道抄送该部门群（取代旧的群机器人 webhook 单向通报，
见 `department_group_chatid_mapping.py`）；部门→群 chatid 映射未配置/为空
（真实值尚未采集）时 fail-closed 跳过并记审计，不报错、不中断本次推送；
不传 `--department` 则完全不尝试群 cc。

环境变量（审计路径解析，队列 #126）：
  WECOM_AIBOT_QUEUE_PATH   可选，仅作仓库根解析的锚点（本脚本本身不读队列），
                           默认 <本 checkout 根>/1-转型规划/0-全景路线图/跨桌任务队列.md
  WECOM_AIBOT_AUDIT_PATH   可选，直接指定审计文件路径，跳过下方解析
  WECOM_AIBOT_REPO_ROOT    可选，显式指定仓库根，绕开动态 git 解析

本脚本按惯例在主工作区跑、常驻监听服务跑在独立 worktree——两者若各自按
`__file__` 反推仓库根会解出两个不同 checkout，审计留痕因此分裂成两个物理
文件（队列 #126 缺陷②）。现改为以 `WECOM_AIBOT_QUEUE_PATH` 锚点动态解析
所属仓库根，据此定位与监听服务共用的同一份 `wecom_aibot_audit.jsonl`。
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

SERVICE_DIR = Path(__file__).resolve().parent.parent
NAIVE_REPO_ROOT = SERVICE_DIR.parents[1]  # 5-平台底座/wecom-aibot-service -> 本 checkout 自身的根

# —— 平台底座路径引导（队列 #345 收拢；唯一被允许的样板，实现见
# `5-平台底座/zhuopin_platform/zhuopin_platform/bootstrap.py`）。必须放在本文件任何
# zhuopin_platform / 场景包 import 之前。下方五行只负责让 bootstrap 自身可被 import、
# 不含任何判断分支；开发机 monorepo 与 `.51` 扁平部署两种布局的分歧由 ensure_paths 处理。——
_HERE = Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        sys.path.insert(0, str(_p / "5-平台底座" / "zhuopin_platform"))
        break
from zhuopin_platform.bootstrap import ensure_paths  # noqa: E402
ensure_paths(__file__, SERVICE_DIR)  # noqa: E402

from zhuopin_platform.audit import AuditLogger  # noqa: E402
from zhuopin_platform.shared_tools.notifiers.wecom_aibot import AibotConnector  # noqa: E402
from zhuopin_platform.shared_tools.secrets import EnvSecretsProvider  # noqa: E402

from aibot_service.connection import BOTID_KEY, SECRET_KEY  # noqa: E402
from aibot_service.constants import PAUL_USERID  # noqa: E402
from aibot_service.delivery import (  # noqa: E402
    push_followup,
    check_delivery_completeness,
    slice_latest_attempt,
    DeliveryNotFinalizedError,
    BackfillWriteError,
)
from aibot_service.readme_table import (  # noqa: E402
    MAIN_TABLE_SECTION,
    ReadmeTableError,
    SUPPLEMENT_TABLE_SECTION,
)
from aibot_service.department_group_chatid_mapping import (  # noqa: E402
    load_department_group_chatid_mapping,
    resolve_group_cc_chatid,
)
from aibot_service.repo_paths import (  # noqa: E402
    resolve_audit_path,
    resolve_default_queue_anchor,
    resolve_repo_root,
)


# 队列 #399：`--table` 取值 → README 章节标题。
_TABLE_SECTIONS = {"主表": MAIN_TABLE_SECTION, "补件": SUPPLEMENT_TABLE_SECTION}


def _verify_completeness(
    audit: AuditLogger, *, md_path: Path, expect_cc_paul: bool, expect_group_cc: bool,
) -> int:
    """队列 #326 新形态（`OP-0831-U`）：读已落盘的审计文件核四条链路是否
    齐全——与"这次是否成功发送过"是两件事，本函数只管"审计里有没有留下
    交代"。独立于本次调用是否被中断：无论是正常跑完后的自查（`_run` 成功
    路径也会调它），还是怀疑上一次调用被杀之后单独重跑 `--verify-only`，
    走的都是这一份逻辑，不重复实现判据。"""
    records = audit.query_by(scenario="wecom-aibot")
    attempt = slice_latest_attempt(records, md_path=str(md_path))
    if not attempt:
        print(f"[INCOMPLETE] 审计里找不到「{md_path}」的任何推送记录——"
              "从没跑过，还是审计路径/参数不对，需人工确认")
        return 3
    report = check_delivery_completeness(
        attempt, expect_cc_paul=expect_cc_paul, expect_group_cc=expect_group_cc,
    )
    if report.ok:
        print(f"[OK] 完整性自检通过：{len(report.expected)} 条链路齐全")
        return 0
    print(
        f"[INCOMPLETE] 缺 {len(report.missing)}/{len(report.expected)} 条链路："
        f"{report.describe_missing()}——审计只记已完成动作，这几步「本应发生而"
        "未发生」，需人工核实是否已实际送达并手工补齐（尤其是 README 回填，"
        "否则下一班会当成待发重发）"
    )
    return 3


async def _run(args: argparse.Namespace) -> int:
    # 队列 #126 缺陷②：本脚本按惯例在主工作区跑，常驻监听服务跑在
    # `ops/wecom-service-home` worktree——各自以 `__file__` 反推仓库根会解出
    # 两个不同的 checkout，审计留痕因此分裂成两个物理文件。统一改为以队列
    # 文件（`WECOM_AIBOT_QUEUE_PATH`，两边都读同一个环境变量约定）为锚点动态
    # 解析所属仓库根，据此定位与监听服务共用的同一份审计文件。队列 #269：
    # 未设该环境变量时的默认锚点也不再停留在"本 checkout 自身"（CC 从临时
    # worktree 跑本脚本时会解出与主工作区不同的物理位置），见
    # `resolve_default_queue_anchor`。
    queue_anchor = resolve_default_queue_anchor(NAIVE_REPO_ROOT)
    resolved_repo_root = resolve_repo_root(queue_anchor, fallback=NAIVE_REPO_ROOT)
    audit_path = Path(
        os.environ.get("WECOM_AIBOT_AUDIT_PATH", resolve_audit_path(resolved_repo_root))
    )
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit = AuditLogger.jsonl(audit_path)

    # 队列 #270：群 cc 改走机器人 chatid 通道——本 CLI 是"人工在命令行显式
    # 指定要发给谁"的工具，天然不像 dispatch_followup_letters 那样能从
    # README 行结构里自动推导部门（调用方本就是显式指定一切的操作者），
    # 故新增 `--department` 可选参数，由操作者显式声明；未传则不尝试群 cc
    # （与不传 `--docx` 时不发附件同一精神，非"配置缺失"，只是"这次没要
    # 这个功能"，不产生审计噪音）。传了才走 fail-closed 判定+留痕。
    #
    # 🔴 群映射解析不需要活连接，`--verify-only` 与正常发送路径共用这一次
    # 计算——两条路径判断"这次期望发生哪几步"必须是同一份逻辑，否则会把
    # "这次本就不该抄"误报成"缺了"。
    cc_group_chatid = (
        resolve_group_cc_chatid(
            department=args.department,
            mapping=load_department_group_chatid_mapping(),
            audit=audit,
            evaluator="cli-push_followup_letter",
        )
        if args.department
        else None
    )
    # 队列 #326 新形态（`OP-0831-U`）：与 `push_followup` 内部
    # `cc_paul_active`/`cc_group_active` 逐字同一份判据（见 delivery.py
    # 该处注释），供完整性自检知道"这次到底该有几条链路"。
    expect_cc_paul = args.chatid != PAUL_USERID
    expect_group_cc = bool(cc_group_chatid and cc_group_chatid != args.chatid)

    if args.verify_only:
        return _verify_completeness(
            audit, md_path=Path(args.md),
            expect_cc_paul=expect_cc_paul, expect_group_cc=expect_group_cc,
        )

    load_dotenv(SERVICE_DIR.parent / ".env")
    secrets = EnvSecretsProvider()
    bot_id = secrets.get(BOTID_KEY)
    secret = secrets.get(SECRET_KEY)

    connector = AibotConnector(bot_id, secret, max_reconnect_attempts=3)
    await connector.connect()
    await asyncio.sleep(1)  # 等 aibot_subscribe 认证完成

    match_topic = args.match_topic

    try:
        result = await push_followup(
            readme_path=Path(args.readme),
            md_path=Path(args.md),
            docx_path=Path(args.docx) if args.docx else None,
            extra_attachments=[Path(p) for p in args.attachment] if args.attachment else None,
            connector=connector,
            chatid=args.chatid,
            # 2026-07-31 起 README 表格新增"编号"列（协议见 README-跟进机制与命名约定.md），
            # 列序随之整体后移一位；改为跨全部单元格搜索而非硬编码列序号，
            # 对未来表格加/减列天然免疫（match_topic 本就要求"唯一定位关键字"）。
            match=lambda cells: any(match_topic in cell for cell in cells),
            audit=audit,
            cc_group_chatid=cc_group_chatid,
            section=_TABLE_SECTIONS[args.table],
        )
        print(f"[OK] 推送成功，README 已回填：{result.new_status}")
        if result.media_ids:
            print(f"[OK] {len(result.media_ids)} 份附件已上传并发送，media_ids={result.media_ids}")
        # 队列 #326 新形态：即便本次一路正常跑完（未被外部中断），也顺手
        # 核一遍四条链路——若某一步的审计写入本身出了问题（与"进程被杀"
        # 是不同的故障，但同样会造成"缺了却看起来正常"），在这里就能截住，
        # 不必等到下一次人工核验才发现。
        return _verify_completeness(
            audit, md_path=Path(args.md),
            expect_cc_paul=expect_cc_paul, expect_group_cc=expect_group_cc,
        )
    except ReadmeTableError as exc:
        # 章节标题匹配不到＝ fail-loud，不静默落到另一张表（队列 #399）。
        print(f"[TABLE] 定位目标表失败（--table {args.table}）：{exc}")
        return 4
    except DeliveryNotFinalizedError as exc:
        print(f"[REJECTED] 门禁②拒绝发送：{exc}")
        return 1
    except BackfillWriteError as exc:
        print(f"[WARN] 已发送成功，但 README 回填失败：{exc}")
        return 2
    finally:
        connector.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description="场景①：手动触发推送指定跟进信")
    parser.add_argument("--readme", required=True)
    parser.add_argument("--md", required=True)
    parser.add_argument("--docx")
    parser.add_argument(
        "--attachment",
        action="append",
        help="额外附件路径，可重复传入以追加多份材料（队列 #93）",
    )
    parser.add_argument("--chatid", required=True)
    parser.add_argument(
        "--match-topic", required=True, help='README「主要事项」列的唯一定位关键字'
    )
    parser.add_argument(
        "--table", choices=("主表", "补件"), default="主表",
        help=(
            "队列 #399：目标表——`主表`＝《现有跟进信清单》，`补件`＝《补件登记》。"
            "表格按章节标题定位，匹配不到即报错，MUST NOT 回退到「文件里第一个"
            "含发送状态的表」。"
        ),
    )
    parser.add_argument(
        "--department",
        help=(
            "队列 #270：归属部门（如 财务部/质量部/采购部），提供后额外把同一份"
            "内容经机器人 chatid 通道抄送该部门群（部门→群 chatid 映射未配置"
            "/为空时 fail-closed 跳过并记审计，不报错）；不传则不尝试群 cc。"
        ),
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help=(
            "队列 #326 新形态（OP-0831-U）：不发送，只核验上一次针对 --md 的"
            "推送尝试审计里「私信+docx／回填README／抄送ShaoPeiShen／部门群抄送」"
            "四条链路是否齐全——缺则非零退出并点名缺哪条。用于怀疑上一次调用"
            "被外部中断（如工具调用超时把子进程一起杀掉）之后的事后核验；"
            "其余参数仍按常规传（就是原样重跑一次那条命令、加这一个开关）。"
        ),
    )
    args = parser.parse_args()

    sys.exit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
