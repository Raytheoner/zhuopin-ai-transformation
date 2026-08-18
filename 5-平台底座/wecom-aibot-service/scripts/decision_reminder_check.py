"""需 Shao Peishen 决策项/待领 opener 主动提醒——一次性触发工具（队列 #172，
2026-08-10 起同进程并入队列 #312 可 Open 池提醒）。

两条互补的提醒共用本脚本、共用同一次 aibot 连接，各自独立判定/独立状态
文件/独立发送与否（互不阻塞——一条有内容另一条没有也照常各自处理）：

  **① 决策提醒（队列 #172，见 `aibot_service.decision_reminder` 模块
  docstring）**——管"待你定夺"：拆件巡逻收工时调用本脚本一次，新登的
  §四 项/新增的 P0/P1 待领行因从未见过而立即触发（事件驱动即时提醒）；
  独立 Windows 计划任务每日固定时点再调用一次，捕捉"已过截止"/"待领
  超期"的升级提醒（1/3/7 天递减间隔，同一天两层都调用也不会重复提醒）。

  **② 可 Open 池提醒（队列 #312，见 `aibot_service.open_pool_reminder`
  模块 docstring）**——管"待你开工"：§一 状态字段为 `[S:open]` 的行即
  "可立即开工"，指纹（当前可 Open 行号集合）出现新行号才推一次，池子
  缩小或维持不变均静默（队列 #147「狼来了」教训，不做"存在即提醒"）。

**两者为何同进程（而非各开一个脚本/各注册一个定时任务）**：队列 #312
行内设计明确"两者互补，可同进程"——巡逻侧的调用点在拆件巡逻定时任务
prompt（仓库外，`C:\\Users\\Paul Shao\\Claude\\Scheduled\\huijian-chaijian-
patrol\\SKILL.md`），本脚本无法从仓库内触达，需 Cowork 侧改动该 prompt
本体才能新增一个调用点；把 ② 并进本脚本本体，巡逻/每日定时任务侧维持
"调用本脚本一次"不变，零新增仓库外改动面，同时省下一次多余的 WS 连接
握手。

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
from aibot_service.decision_reminder import (  # noqa: E402
    DEFAULT_STATE_REL,
    evaluate_candidates,
    format_digest_message,
    send_decision_reminder,
)
from aibot_service.decision_reminder import load_state as load_decision_state  # noqa: E402
from aibot_service.decision_reminder import save_state as save_decision_state  # noqa: E402
from aibot_service.open_pool_reminder import (  # noqa: E402
    build_pool_items,
    compute_new_ids,
    format_pool_reminder_message,
    new_known_state,
    send_open_pool_reminder,
)
from aibot_service.open_pool_reminder import load_state as load_pool_state  # noqa: E402
from aibot_service.open_pool_reminder import save_state as save_pool_state  # noqa: E402
from aibot_service.queue_edit_lock import AIBOT_LOCK_WHO, SubprocessQueueEditLock  # noqa: E402
from aibot_service.queue_lock_pending import flush_pending_queue_appends  # noqa: E402
from aibot_service.repo_paths import (  # noqa: E402
    DEFAULT_QUEUE_RELATIVE_PATH,
    resolve_audit_path,
    resolve_default_queue_anchor,
    resolve_open_pool_reminder_state_path,
    resolve_pending_queue_appends_path,
    resolve_pending_queue_lock_appends_path,
    resolve_repo_root,
)

QUEUE_REL = DEFAULT_QUEUE_RELATIVE_PATH


async def _flush_pending_lock_appends_second_carrier(
    resolved_repo_root: Path, queue_path: Path, audit: AuditLogger, fallback_send,
) -> None:
    """队列 #192-A 第二道载体（主载体＝`工具-落库sweep.py` 每小时子进程调用，
    见其 `_flush_pending_lock_appends`）——两处各调一次，互为冗余，成本近乎
    为零；`#199` 的 `0x800710E0` 间歇性失败正说明单一载体不可靠。

    刻意不建 WS 长连接（`connector=None`，同独立脚本
    `flush_pending_lock_appends.py` 用法）——本函数只在决策提醒判定之前
    调用一次，不因新增这一步而让原有决策提醒逻辑多等一次连接握手。失败
    只降级记 audit（`flush_pending_queue_appends` 内部已有），不向上抛出，
    不得影响本脚本原有的决策提醒判定与发送。"""
    pending_lock_path = Path(
        os.environ.get(
            "WECOM_AIBOT_PENDING_LOCK_PATH", resolve_pending_queue_lock_appends_path(resolved_repo_root)
        )
    )
    pending_queue_appends_path = Path(
        os.environ.get(
            "WECOM_AIBOT_PENDING_APPENDS_PATH", resolve_pending_queue_appends_path(resolved_repo_root)
        )
    )

    def _lock_factory():
        return SubprocessQueueEditLock(
            resolved_repo_root, queue_path, who=AIBOT_LOCK_WHO, note="每日提醒兜底补录",
        )

    try:
        flushed = await flush_pending_queue_appends(
            pending_path=pending_lock_path,
            queue_path=queue_path,
            repo_root=resolved_repo_root,
            audit=audit,
            lock_factory=_lock_factory,
            connector=None,
            recipient=PAUL_USERID,
            fallback_send=fallback_send,
            git_sync_pending_path=pending_queue_appends_path,
        )
    except Exception as exc:  # noqa: BLE001 —— 第二道载体失败不应影响本脚本主流程
        print(f"[WARN] pending_queue_lock_appends.jsonl flush 失败（不影响决策提醒本身）：{exc}", file=sys.stderr)
        return
    if flushed:
        print(f"[OK] 兜底 flush：已补录 {flushed} 条")


async def _run(dry_run: bool) -> int:
    load_dotenv(SERVICE_DIR.parent / ".env")

    queue_anchor = resolve_default_queue_anchor(NAIVE_REPO_ROOT, QUEUE_REL)
    resolved_repo_root = resolve_repo_root(queue_anchor, fallback=NAIVE_REPO_ROOT)
    queue_path = resolved_repo_root / QUEUE_REL
    decision_state_path = resolved_repo_root / "5-平台底座" / "wecom-aibot-service" / DEFAULT_STATE_REL
    pool_state_path = resolve_open_pool_reminder_state_path(resolved_repo_root)

    if not queue_path.exists():
        print(f"[SKIP] 队列文件不存在：{queue_path}", file=sys.stderr)
        return 1

    audit_path = Path(
        os.environ.get("WECOM_AIBOT_AUDIT_PATH", resolve_audit_path(resolved_repo_root))
    )
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit = AuditLogger.jsonl(audit_path)

    webhook_url = os.environ.get("WECOM_WEBHOOK_URL")
    fallback_send = (
        (lambda text: wecom.send_text(webhook_url, f"⚠️ {text}")) if webhook_url else None
    )

    # 队列 #192-A 第二道载体：dry-run 不做真实动作（会真实 commit/push），
    # 与主载体 sweep 的 dry-run 处理方式一致。
    if not dry_run:
        await _flush_pending_lock_appends_second_carrier(
            resolved_repo_root, queue_path, audit, fallback_send,
        )

    queue_text = queue_path.read_text(encoding="utf-8")
    today = date.today()

    # ① 队列 #172：需 Shao Peishen 决策项/待领 opener 主动提醒。
    decision_state = load_decision_state(decision_state_path)
    decision_items, new_decision_state = evaluate_candidates(queue_text, today, decision_state)
    decision_message = format_digest_message(decision_items)

    # ② 队列 #312：可 Open 池事件驱动提醒——判据与 ① 均读 #308 同一份
    # 机器字段，互不依赖，各自独立算、独立决定是否有内容要发。
    pool_state = load_pool_state(pool_state_path)
    pool_items = build_pool_items(queue_text, resolved_repo_root)
    new_pool_ids = compute_new_ids(pool_items, pool_state)
    pool_message = format_pool_reminder_message(pool_items, new_pool_ids)
    new_pool_state = new_known_state(pool_items)

    if decision_message is None and pool_message is None:
        print("[OK] 无新增/超期决策项，可 Open 池亦无新增行号，本次不发送。")
        if not dry_run:
            save_decision_state(decision_state_path, new_decision_state)
            save_pool_state(pool_state_path, new_pool_state)
        return 0

    if decision_message:
        print(decision_message)
    if pool_message:
        print(pool_message)

    if dry_run:
        print("[dry-run] 以上内容不实际发送，状态文件不落地。")
        return 0

    # 先落两份状态，即便发送失败也不重复计入下次判定（同既有决策提醒惯例）。
    save_decision_state(decision_state_path, new_decision_state)
    save_pool_state(pool_state_path, new_pool_state)

    secrets = EnvSecretsProvider()
    bot_id = secrets.get(BOTID_KEY)
    secret = secrets.get(SECRET_KEY)
    connector = AibotConnector(bot_id, secret, max_reconnect_attempts=3)
    await connector.connect()
    await asyncio.sleep(1)  # 等 aibot_subscribe 认证完成

    try:
        if decision_message:
            await send_decision_reminder(
                connector, audit, decision_message, PAUL_USERID, fallback_send=fallback_send,
            )
        if pool_message:
            await send_open_pool_reminder(
                connector, audit, pool_message, PAUL_USERID, fallback_send=fallback_send,
            )
    finally:
        connector.disconnect()

    sent_summary = []
    if decision_message:
        sent_summary.append(f"决策提醒 {len(decision_items)} 项")
    if pool_message:
        sent_summary.append(f"可 Open 池新增 {len(new_pool_ids)} 项")
    print(f"[OK] 已发送：{'；'.join(sent_summary)}。")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="需 Shao Peishen 决策项/待领 opener 主动提醒")
    parser.add_argument("--dry-run", action="store_true", help="只打印将发送的内容，不实际发送/不落状态文件")
    args = parser.parse_args()
    sys.exit(asyncio.run(_run(args.dry_run)))


if __name__ == "__main__":
    main()
