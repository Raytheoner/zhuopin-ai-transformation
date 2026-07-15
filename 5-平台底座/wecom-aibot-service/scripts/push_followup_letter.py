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
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

SERVICE_DIR = Path(__file__).resolve().parent.parent
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


async def _run(args: argparse.Namespace) -> int:
    load_dotenv(SERVICE_DIR.parent / ".env")
    secrets = EnvSecretsProvider()
    bot_id = secrets.get(BOTID_KEY)
    secret = secrets.get(SECRET_KEY)

    audit_path = SERVICE_DIR / "reports" / "wecom_aibot_audit.jsonl"
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
            match=lambda cells: match_topic in cells[2],
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
