"""场景④每日批处理发信——一次性触发工具（design.md D2/D3，队列 #124 阶段
二）。由独立计划任务 `ZhuopinFollowupDispatchDaily`（工作日 09:30，见
`register-followup-dispatch-task.ps1`）每日调用一次；也可手动运行做端到
端验证。

不承诺准点，只承诺"下次开机即处理"（`-StartWhenAvailable`，同
`ZhuopinDecisionReminderDaily`/#189/#199 先例）——本脚本本身不做任何重试
/心跳设计，可靠性完全交给计划任务的运行时机制。

用法：
  python scripts/dispatch_followup_letters.py
  python scripts/dispatch_followup_letters.py --dry-run   # 只打印将处理的行，不实际发送/不回填

环境变量（同 push_followup_letter.py/decision_reminder_check.py 既有约定）：
  WECOM_AIBOT_QUEUE_PATH   可选，仓库根解析锚点，默认 <本 checkout 根>/
                           1-转型规划/0-全景路线图/跨桌任务队列.md
  WECOM_AIBOT_REPO_ROOT    可选，显式指定仓库根，绕开动态 git 解析
  WECOM_AIBOT_AUDIT_PATH   可选，直接指定审计文件路径
  WECOM_WEBHOOK_URL        可选，"疑似漏标硬截止"告警的兜底群 webhook 通道
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
README_RELATIVE_PATH = Path("6-人才与组织") / "部门AI专员跟进" / "README-跟进机制与命名约定.md"

# —— worktree 隔离引导（队列 #300／#313 补漏）：把本 worktree 的平台底座与本服务
# 自身路径插到 sys.path 最前，使 import 结果与全局 editable 安装当前指向谁无关。
# 必须放在下方任何 zhuopin_platform / aibot_service import 之前。——
_HERE = Path(__file__).resolve()
for _p in (_HERE, *_HERE.parents):
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        for _entry in (_p / "5-平台底座" / "zhuopin_platform", SERVICE_DIR):
            if str(_entry) not in sys.path:
                sys.path.insert(0, str(_entry))
        break
else:
    # 🔴 找不到仓库根标记时**不得硬失败**（2026-08-18 实测事故，队列 #345）：#300 要防的是
    # "N 个平等 worktree 共用一套全局 site-packages、谁装的 editable 指针谁说了算"——
    # **该前提只在开发机成立**。`.51` 的部署布局是扁平的 `C:/<svc>/app` ＋
    # `C:/<svc>/zhuopin_platform`（后者已由 deploy 脚本 pip install -e 进 venv，全机唯一
    # 一份、无歧义），**没有也不需要 `5-平台底座/` 这层目录**。原实现在此直接 raise，等于
    # 把入口在生产布局上钉死（现象：计划任务 LastResult=0 但进程秒退、端口无监听）。
    # ⇒ 找到标记 → 按 #300 前插（开发机，确定性优先）；找不到 → 只插自身包路径、平台底座
    # 交由环境解析（生产机，唯一一份）。**不引入静默失败**：环境里也没有 zhuopin_platform
    # 时仍然明确报错。——
    if str(SERVICE_DIR) not in sys.path:
        sys.path.insert(0, str(SERVICE_DIR))
    from importlib.util import find_spec
    if find_spec("zhuopin_platform") is None:
        raise RuntimeError(
            f"既未找到仓库根标记 5-平台底座/zhuopin_platform（从 {_HERE} 向上查找），"
            "环境中也没有可导入的 zhuopin_platform——请检查部署或安装平台底座包")

from zhuopin_platform.audit import AuditLogger  # noqa: E402
from zhuopin_platform.shared_tools.notifiers import wecom  # noqa: E402
from zhuopin_platform.shared_tools.notifiers.wecom_aibot import AibotConnector  # noqa: E402
from zhuopin_platform.shared_tools.secrets import EnvSecretsProvider  # noqa: E402

from aibot_service.connection import BOTID_KEY, SECRET_KEY  # noqa: E402
from aibot_service.constants import PAUL_USERID  # noqa: E402
from aibot_service.department_group_chatid_mapping import (  # noqa: E402
    load_department_group_chatid_mapping,
)
from aibot_service.dispatch import dispatch_followup_letters  # noqa: E402
from aibot_service.readme_table import iter_rows  # noqa: E402
from aibot_service.repo_paths import (  # noqa: E402
    resolve_audit_path,
    resolve_default_queue_anchor,
    resolve_repo_root,
)


def _print_dry_run(readme_path: Path) -> int:
    from aibot_service.gates import FINALIZED_STATUS_MARKER

    rows = iter_rows(readme_path.read_text(encoding="utf-8"))
    candidates = [r for r in rows if r.cells[r.status_col_index].strip() == FINALIZED_STATUS_MARKER]
    if not candidates:
        print("[dry-run] 无「🆕 待发」行，本轮不会发送任何消息。")
        return 0
    print(f"[dry-run] 发现 {len(candidates)} 行「🆕 待发」（实际是否发送还需过 🔒人工发送/临近截止判定）：")
    for r in candidates:
        print(f"  - {' / '.join(c for c in r.cells[:3] if c)}")
    return 0


async def _run(dry_run: bool) -> int:
    load_dotenv(SERVICE_DIR.parent / ".env")

    queue_anchor = resolve_default_queue_anchor(NAIVE_REPO_ROOT)
    resolved_repo_root = resolve_repo_root(queue_anchor, fallback=NAIVE_REPO_ROOT)
    readme_path = resolved_repo_root / README_RELATIVE_PATH

    if not readme_path.exists():
        print(f"[SKIP] README 不存在：{readme_path}", file=sys.stderr)
        return 1

    if dry_run:
        return _print_dry_run(readme_path)

    audit_path = Path(
        os.environ.get("WECOM_AIBOT_AUDIT_PATH", resolve_audit_path(resolved_repo_root))
    )
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit = AuditLogger.jsonl(audit_path)

    webhook_url = os.environ.get("WECOM_WEBHOOK_URL")
    fallback_send = (
        (lambda text: wecom.send_text(webhook_url, text)) if webhook_url else None
    )

    secrets = EnvSecretsProvider()
    bot_id = secrets.get(BOTID_KEY)
    secret = secrets.get(SECRET_KEY)
    connector = AibotConnector(bot_id, secret, max_reconnect_attempts=3)
    await connector.connect()
    await asyncio.sleep(1)  # 等 aibot_subscribe 认证完成

    # 队列 #270：群 cc 改走机器人 chatid 通道——加载部门→群 chatid 映射表
    # （真实值尚未采集，多数/全部部门当前会解析成占位空值，`dispatch_
    # followup_letters` 内部按行 fail-closed 判定并留痕，不因此中断批处理）。
    group_chatid_mapping = load_department_group_chatid_mapping()

    try:
        outcome = await dispatch_followup_letters(
            readme_path=readme_path, connector=connector, audit=audit, today=date.today(),
            group_chatid_mapping=group_chatid_mapping,
        )

        if outcome.skipped_unmarked_deadline:
            # design 追加要求②："结构性跳过并告警"——告警走既有企微私信主
            # 通道（连接仍存活，在 finally 断开之前发出），失败降级群
            # webhook 兜底（同 gap_alert.py/decision_reminder.py 既有范式）。
            lines = "\n".join(f"- {p}" for p in outcome.skipped_unmarked_deadline)
            alert_text = (
                "⚠️ 以下跟进信「交期要点」含临近明确日期，但未标 🔒人工发送，"
                f"本轮自动发信已结构性跳过，请人工核实处理：\n{lines}"
            )
            try:
                await connector.send_markdown(PAUL_USERID, alert_text)
            except Exception:  # noqa: BLE001 —— 告警失败不应影响批次已完成的事实
                if fallback_send is not None:
                    try:
                        await asyncio.to_thread(fallback_send, alert_text)
                    except Exception:  # noqa: BLE001
                        pass
    finally:
        connector.disconnect()

    print(f"[OK] 本轮发送成功 {len(outcome.sent)} 行、失败 {len(outcome.failed)} 行、"
          f"跳过（🔒人工发送）{len(outcome.skipped_manual)} 行、"
          f"跳过（疑似漏标硬截止）{len(outcome.skipped_unmarked_deadline)} 行、"
          f"跳过（⏸ 暂缓）{len(outcome.skipped_paused)} 行")
    for preview, reason in outcome.failed:
        print(f"  [FAILED] {preview} —— {reason}")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="场景④：每日批处理扫描并发送已批准跟进信")
    parser.add_argument(
        "--dry-run", action="store_true", help="只打印将处理的「🆕 待发」行，不实际发送/不回填"
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(_run(args.dry_run)))


if __name__ == "__main__":
    main()
