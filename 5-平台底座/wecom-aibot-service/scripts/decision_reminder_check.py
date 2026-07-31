"""需 Shao Peishen 决策项/待领 opener 主动提醒——一次性触发工具（队列 #172）。

两层提醒共用本脚本、同一套判定（见 `aibot_service.decision_reminder` 模块
docstring）：
  ① 事件驱动即时提醒——拆件巡逻收工时调用本脚本一次，新登的 §四 项/新增
     的 P0/P1 待领行因从未见过而立即触发。
  ② 每日超期汇总——独立 Windows 计划任务（见 `register-decision-reminder-
     task.ps1`）每日固定时点调用本脚本一次，捕捉"已过截止"/"待领超期"的
     升级提醒（1/3/7 天递减间隔，同一天两层都调用也不会重复提醒）。

**分工边界（写在这里，供 Cowork 侧协作者一眼看到）**：巡逻侧的调用点在
拆件巡逻定时任务 prompt（仓库外，`C:\\Users\\Paul Shao\\Claude\\Scheduled\\
huijian-chaijian-patrol\\SKILL.md`），本脚本无法从仓库内触达——巡逻收工段
补一句 `python <本脚本路径>` 调用，需 Cowork 侧改动该 prompt 本体。本脚本
只负责把"调用后会做什么"实现好、可被稳定调用。

用法：
  python scripts/decision_reminder_check.py
  python scripts/decision_reminder_check.py --dry-run   # 只打印将发送的内容，不实际发送/不落状态文件

环境变量（同 `push_followup_letter.py`/`alert_webhook.py` 既有约定）：
  WECOM_AIBOT_QUEUE_PATH   可选，仓库根解析锚点，默认 <本 checkout 根>/
                           1-转型规划/0-全景路线图/跨桌任务队列.md
  WECOM_AIBOT_REPO_ROOT    可选，显式指定仓库根，绕开动态 git 解析
  WECOM_AIBOT_AUDIT_PATH   可选，直接指定审计文件路径
  WECOM_WEBHOOK_URL        可选，主通道（智能机器人私信）失败时的兜底群 webhook
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

SERVICE_DIR = Path(__file__).resolve().parent.parent
NAIVE_REPO_ROOT = SERVICE_DIR.parents[1]  # 5-平台底座/wecom-aibot-service -> 本 checkout 自身的根
sys.path.insert(0, str(SERVICE_DIR))

from zhuopin_platform.audit import AuditLogger  # noqa: E402
from zhuopin_platform.shared_tools.notifiers import wecom  # noqa: E402
from zhuopin_platform.shared_tools.notifiers.wecom_aibot import AibotConnector  # noqa: E402
from zhuopin_platform.shared_tools.secrets import EnvSecretsProvider  # noqa: E402

from aibot_service.connection import BOTID_KEY, SECRET_KEY  # noqa: E402
from aibot_service.constants import PAUL_USERID  # noqa: E402
from aibot_service.decision_reminder import (  # noqa: E402
    DEFAULT_STATE_REL,
    evaluate_candidates,
    format_digest_message,
    load_state,
    save_state,
    send_decision_reminder,
)
from aibot_service.repo_paths import (  # noqa: E402
    DEFAULT_QUEUE_RELATIVE_PATH,
    resolve_audit_path,
    resolve_repo_root,
)

QUEUE_REL = DEFAULT_QUEUE_RELATIVE_PATH


async def _run(dry_run: bool) -> int:
    load_dotenv(SERVICE_DIR.parent / ".env")

    queue_anchor = Path(
        os.environ.get("WECOM_AIBOT_QUEUE_PATH", NAIVE_REPO_ROOT / QUEUE_REL)
    )
    resolved_repo_root = resolve_repo_root(queue_anchor, fallback=NAIVE_REPO_ROOT)
    queue_path = resolved_repo_root / QUEUE_REL
    state_path = resolved_repo_root / "5-平台底座" / "wecom-aibot-service" / DEFAULT_STATE_REL

    if not queue_path.exists():
        print(f"[SKIP] 队列文件不存在：{queue_path}", file=sys.stderr)
        return 1

    queue_text = queue_path.read_text(encoding="utf-8")
    today = date.today()
    state = load_state(state_path)
    items, new_state = evaluate_candidates(queue_text, today, state)
    message = format_digest_message(items)

    if message is None:
        print("[OK] 无新增/超期决策项，本次不发送。")
        if not dry_run:
            save_state(state_path, new_state)
        return 0

    print(message)
    if dry_run:
        print("[dry-run] 以上内容不实际发送，状态文件不落地。")
        return 0

    save_state(state_path, new_state)  # 先落状态，即便发送失败也不重复计入下次判定

    audit_path = Path(
        os.environ.get("WECOM_AIBOT_AUDIT_PATH", resolve_audit_path(resolved_repo_root))
    )
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit = AuditLogger.jsonl(audit_path)

    secrets = EnvSecretsProvider()
    bot_id = secrets.get(BOTID_KEY)
    secret = secrets.get(SECRET_KEY)
    connector = AibotConnector(bot_id, secret, max_reconnect_attempts=3)
    await connector.connect()
    await asyncio.sleep(1)  # 等 aibot_subscribe 认证完成

    webhook_url = os.environ.get("WECOM_WEBHOOK_URL")
    fallback_send = (
        (lambda text: wecom.send_text(webhook_url, f"⚠️ {text}")) if webhook_url else None
    )
    try:
        await send_decision_reminder(connector, audit, message, PAUL_USERID, fallback_send=fallback_send)
    finally:
        connector.disconnect()

    print(f"[OK] 已发送提醒（{len(items)} 项）。")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="需 Shao Peishen 决策项/待领 opener 主动提醒")
    parser.add_argument("--dry-run", action="store_true", help="只打印将发送的内容，不实际发送/不落状态文件")
    args = parser.parse_args()
    sys.exit(asyncio.run(_run(args.dry_run)))


if __name__ == "__main__":
    main()
