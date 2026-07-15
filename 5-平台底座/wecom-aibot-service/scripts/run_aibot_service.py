"""企微智能机器人服务入口——读 .env → 建连接 → 阻塞运行（部署层用计划任务
包起来常驻，见 ../deploy-server.ps1）。

环境变量：
  WECOM_AIBOT_BOTID / WECOM_AIBOT_SECRET   必填，凭据（见 SecretsProvider）
  WECOM_AIBOT_EXTERNAL_DOCS_ROOT           可选，默认 <repo_root>/7-外部文档
  WECOM_AIBOT_QUEUE_PATH                   可选，默认 <repo_root>/1-转型规划/0-全景路线图/跨桌任务队列.md
  WECOM_AIBOT_AUDIT_PATH                   可选，默认 <service_dir>/reports/wecom_aibot_audit.jsonl
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.shared_tools.secrets import EnvSecretsProvider

SERVICE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SERVICE_DIR.parents[1]  # 5-平台底座/wecom-aibot-service -> 仓库根

sys.path.insert(0, str(SERVICE_DIR))
from aibot_service.connection import build_connector  # noqa: E402


async def _run_forever(connector) -> None:
    await connector.connect()
    await asyncio.Event().wait()


def main() -> None:
    load_dotenv(SERVICE_DIR.parent / ".env")  # 5-平台底座/.env（照 SC8 .env 放置层级）

    external_docs_root = Path(
        os.environ.get("WECOM_AIBOT_EXTERNAL_DOCS_ROOT", REPO_ROOT / "7-外部文档")
    )
    queue_path = Path(
        os.environ.get(
            "WECOM_AIBOT_QUEUE_PATH",
            REPO_ROOT / "1-转型规划" / "0-全景路线图" / "跨桌任务队列.md",
        )
    )
    audit_path = Path(
        os.environ.get("WECOM_AIBOT_AUDIT_PATH", SERVICE_DIR / "reports" / "wecom_aibot_audit.jsonl")
    )
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    secrets = EnvSecretsProvider()
    audit = AuditLogger.jsonl(audit_path)

    connector = build_connector(
        secrets=secrets,
        audit=audit,
        external_docs_root=external_docs_root,
        queue_path=queue_path,
    )

    asyncio.run(_run_forever(connector))


if __name__ == "__main__":
    main()
