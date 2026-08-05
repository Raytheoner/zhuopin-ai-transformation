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
sys.path.insert(0, str(SERVICE_DIR))

from zhuopin_platform.audit import AuditLogger  # noqa: E402
from zhuopin_platform.shared_tools.notifiers.wecom_aibot import AibotConnector  # noqa: E402
from zhuopin_platform.shared_tools.secrets import EnvSecretsProvider  # noqa: E402

from aibot_service.connection import BOTID_KEY, SECRET_KEY  # noqa: E402
from aibot_service.delivery import (  # noqa: E402
    push_followup,
    DeliveryNotFinalizedError,
    BackfillWriteError,
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


async def _run(args: argparse.Namespace) -> int:
    load_dotenv(SERVICE_DIR.parent / ".env")
    secrets = EnvSecretsProvider()
    bot_id = secrets.get(BOTID_KEY)
    secret = secrets.get(SECRET_KEY)

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

    connector = AibotConnector(bot_id, secret, max_reconnect_attempts=3)
    await connector.connect()
    await asyncio.sleep(1)  # 等 aibot_subscribe 认证完成

    match_topic = args.match_topic

    # 队列 #270：群 cc 改走机器人 chatid 通道——本 CLI 是"人工在命令行显式
    # 指定要发给谁"的工具，天然不像 dispatch_followup_letters 那样能从
    # README 行结构里自动推导部门（调用方本就是显式指定一切的操作者），
    # 故新增 `--department` 可选参数，由操作者显式声明；未传则不尝试群 cc
    # （与不传 `--docx` 时不发附件同一精神，非"配置缺失"，只是"这次没要
    # 这个功能"，不产生审计噪音）。传了才走 fail-closed 判定+留痕。
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
        )
        print(f"[OK] 推送成功，README 已回填：{result.new_status}")
        if result.media_ids:
            print(f"[OK] {len(result.media_ids)} 份附件已上传并发送，media_ids={result.media_ids}")
        return 0
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
        "--department",
        help=(
            "队列 #270：归属部门（如 财务部/质量部/采购部），提供后额外把同一份"
            "内容经机器人 chatid 通道抄送该部门群（部门→群 chatid 映射未配置"
            "/为空时 fail-closed 跳过并记审计，不报错）；不传则不尝试群 cc。"
        ),
    )
    args = parser.parse_args()

    sys.exit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
