"""锁忙推迟暂存（`pending_queue_lock_appends.jsonl`）的独立触发脚本
（队列 #192-A，主载体＝`工具-落库sweep.py` 每小时子进程调用；第二道载体见
`decision_reminder_check.py` 同名调用，每日 08:30）。

背景：机器人写队列时若协议〇.7 共享编辑锁被人类持有，`queue_lock_pending.py`
把追加参数原样暂存，此前**唯一**的补录触发点是"下一条新消息到达"
（`connection.py::on_message`）——07-31 真实一例因当日下午无人再发消息，
暂存滞留 **4 小时 2 分**才被下一条无关消息意外带出。本脚本把 flush 独立
成一次性触发点，不依赖"凑巧有下一条消息"。

刻意不建 WS 长连接（`connector=None`）——`flush_pending_queue_appends` 本就
支持这一用法（见其文档），补录失败只降级为 audit `queue_sync_degraded` +
队列文件"⏳未同步"标记（既有机制），不因为多起一次连接增加复杂度/失败面；
若确需私信告警，`fallback_send`（webhook）已够用，同 `queue_git_sync.py`
既有范式。

顺带（队列 #192-C）：检查 `pending_queue_appends.jsonl`（git 推送失败暂存，
`queue_git_sync._append_pending_record`，此前全库无任何读取方）是否非空，
非空则在 stdout 报一条数量提示——不自动重放（重放需要重新计算队列编号，
存在与已发生的正常提交冲突的风险，超出本次"消解可见性"的范围），只做到
"有人能看见"。

用法：
  python scripts/flush_pending_lock_appends.py

环境变量（同 `decision_reminder_check.py`/`push_followup_letter.py` 既有约定）：
  WECOM_AIBOT_QUEUE_PATH   可选，仓库根解析锚点
  WECOM_AIBOT_REPO_ROOT    可选，显式指定仓库根，绕开动态 git 解析
  WECOM_AIBOT_AUDIT_PATH   可选，直接指定审计文件路径
  WECOM_WEBHOOK_URL        可选，flush 失败时的兜底群 webhook 告警
"""
from __future__ import annotations

import asyncio
import os
import sys
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
    raise RuntimeError(f"未找到仓库根标记 5-平台底座/zhuopin_platform（从 {_HERE} 向上查找）")

from zhuopin_platform.audit import AuditLogger  # noqa: E402
from zhuopin_platform.shared_tools.notifiers import wecom  # noqa: E402

from aibot_service.constants import PAUL_USERID  # noqa: E402
from aibot_service.queue_edit_lock import AIBOT_LOCK_WHO, SubprocessQueueEditLock  # noqa: E402
from aibot_service.queue_lock_pending import flush_pending_queue_appends, read_deferred_appends  # noqa: E402
from aibot_service.repo_paths import (  # noqa: E402
    DEFAULT_QUEUE_RELATIVE_PATH,
    resolve_audit_path,
    resolve_default_queue_anchor,
    resolve_pending_queue_appends_path,
    resolve_pending_queue_lock_appends_path,
    resolve_repo_root,
)


async def _run() -> int:
    load_dotenv(SERVICE_DIR.parent / ".env")

    queue_anchor = resolve_default_queue_anchor(NAIVE_REPO_ROOT)
    resolved_repo_root = resolve_repo_root(queue_anchor, fallback=NAIVE_REPO_ROOT)
    queue_path = resolved_repo_root / DEFAULT_QUEUE_RELATIVE_PATH

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
    audit_path = Path(
        os.environ.get("WECOM_AIBOT_AUDIT_PATH", resolve_audit_path(resolved_repo_root))
    )
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit = AuditLogger.jsonl(audit_path)

    webhook_url = os.environ.get("WECOM_WEBHOOK_URL")
    fallback_send = (
        (lambda text: wecom.send_text(webhook_url, f"⚠️ 企微智能机器人服务：{text}"))
        if webhook_url else None
    )

    def _lock_factory():
        return SubprocessQueueEditLock(
            resolved_repo_root, queue_path, who=AIBOT_LOCK_WHO, note="独立触发脚本兜底补录",
        )

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
    if flushed:
        print(f"已补录 {flushed} 条")
    else:
        print("无待补录记录")

    unresolved = read_deferred_appends(pending_queue_appends_path)
    if unresolved:
        print(f"⚠ {len(unresolved)} 条历史队列 git 同步失败记录待人工核对：{pending_queue_appends_path}")

    return 0


def main() -> None:
    sys.exit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
