"""场景①手动触发工具（design.md Non-Goal：不做自动扫描，必须由调用方显式
指定具体某一封信）。CC/专线人工判断某封跟进信已就绪（README 状态列为
"🆕 待发"）后，用本脚本触发推送——读 md 正文（+ 可选 docx 附件）经智能
机器人发到指定会话，成功后自动回填 README 状态列。

用法：
  python scripts/push_followup_letter.py \
    --readme "<README-跟进机制与命名约定.md 路径>" \
    --md "<跟进信 .md 路径>" \
    [--docx "<跟进信 .docx 路径>"] \
    --chatid "<企微群/用户 chatid>" \
    --match-topic "<README「主要事项」列的唯一定位关键字>"

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
from aibot_service.repo_paths import (  # noqa: E402
    DEFAULT_QUEUE_RELATIVE_PATH,
    resolve_audit_path,
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
    # 解析所属仓库根，据此定位与监听服务共用的同一份审计文件。
    queue_anchor = Path(
        os.environ.get("WECOM_AIBOT_QUEUE_PATH", NAIVE_REPO_ROOT / DEFAULT_QUEUE_RELATIVE_PATH)
    )
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
    try:
        result = await push_followup(
            readme_path=Path(args.readme),
            md_path=Path(args.md),
            docx_path=Path(args.docx) if args.docx else None,
            connector=connector,
            chatid=args.chatid,
            # 2026-07-31 起 README 表格新增"编号"列（协议见 README-跟进机制与命名约定.md），
            # 列序随之整体后移一位；改为跨全部单元格搜索而非硬编码列序号，
            # 对未来表格加/减列天然免疫（match_topic 本就要求"唯一定位关键字"）。
            match=lambda cells: any(match_topic in cell for cell in cells),
            audit=audit,
        )
        print(f"[OK] 推送成功，README 已回填：{result.new_status}")
        if result.media_id:
            print(f"[OK] docx 素材已上传并发送，media_id={result.media_id}")
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
    parser.add_argument("--chatid", required=True)
    parser.add_argument(
        "--match-topic", required=True, help='README「主要事项」列的唯一定位关键字'
    )
    args = parser.parse_args()

    sys.exit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
