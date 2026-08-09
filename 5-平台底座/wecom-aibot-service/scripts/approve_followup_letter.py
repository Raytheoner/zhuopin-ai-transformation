"""场景③手动触发工具（design.md D1，对应 spec wecom-followup-review-state）。

把 README 中一行跟进信的「发送状态」列从待审草稿态 `⏳ 待你审` 原子转换为
终态 `🆕 待发`——这是唯一合法的批准转换路径。不发送任何消息，只做状态
跃迁；发送仍分别由人工路径（push_followup_letter.py）或自动路径
（dispatch_followup_letters.py）消费"🆕 待发"这一终态。

用法：
  python scripts/approve_followup_letter.py \
    --readme "<README-跟进机制与命名约定.md 路径>" \
    --match-topic "<README「主要事项」列的唯一定位关键字>" \
    --quote "<批准依据摘录，如 Shao Peishen 的放行原话>"

**冷却窗口**（design 审通过后追加要求①）：本脚本第一次"看到"某一行时只
记录观测时刻并拒绝执行；须在 10 分钟（默认，`--cooldown-minutes` 可覆盖，
仅供测试/特殊场景使用）后再次调用才会真正批准——逼出一个独立、蓄意的
等待动作，堵住"起草→release→立刻批准"这种同一 actor 一步做完的反模式。

环境变量（审计路径解析，同 push_followup_letter.py，队列 #126）：
  WECOM_AIBOT_QUEUE_PATH   可选，仅作仓库根解析的锚点，默认
                           <本 checkout 根>/1-转型规划/0-全景路线图/跨桌任务队列.md
  WECOM_AIBOT_AUDIT_PATH   可选，直接指定审计文件路径，跳过下方解析
  WECOM_AIBOT_REPO_ROOT    可选，显式指定仓库根，绕开动态 git 解析
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

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

from aibot_service.approval import (  # noqa: E402
    ApprovalCooldownError,
    DEFAULT_COOLDOWN_MINUTES,
    approve_followup_letter,
)
from aibot_service.readme_table import DraftNotPendingReviewError  # noqa: E402
from aibot_service.repo_paths import (  # noqa: E402
    DEFAULT_QUEUE_RELATIVE_PATH,
    resolve_audit_path,
    resolve_followup_approval_cooldown_state_path,
    resolve_repo_root,
)


def _run(args: argparse.Namespace) -> int:
    queue_anchor = Path(
        os.environ.get("WECOM_AIBOT_QUEUE_PATH", NAIVE_REPO_ROOT / DEFAULT_QUEUE_RELATIVE_PATH)
    )
    resolved_repo_root = resolve_repo_root(queue_anchor, fallback=NAIVE_REPO_ROOT)
    audit_path = Path(
        os.environ.get("WECOM_AIBOT_AUDIT_PATH", resolve_audit_path(resolved_repo_root))
    )
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit = AuditLogger.jsonl(audit_path)

    cooldown_state_path = resolve_followup_approval_cooldown_state_path(resolved_repo_root)
    match_topic = args.match_topic

    try:
        result = approve_followup_letter(
            readme_path=Path(args.readme),
            # 2026-07-31 起 README 表格新增"编号"列，列序随之整体后移一位；
            # 跨全部单元格搜索而非硬编码列序号，对未来表格加/减列天然免疫
            # （match_topic 本就要求"唯一定位关键字"，同 push_followup_letter.py 惯例）。
            match=lambda cells: any(match_topic in cell for cell in cells),
            quote=args.quote,
            audit=audit,
            cooldown_state_path=cooldown_state_path,
            now=datetime.now(tz=timezone.utc),
            cooldown_minutes=args.cooldown_minutes,
        )
        print(f"[OK] 批准成功，README 已回填：{result.new_status}")
        return 0
    except DraftNotPendingReviewError as exc:
        print(f"[REJECTED] 批准被拒绝：{exc}")
        return 1
    except ApprovalCooldownError as exc:
        print(f"[COOLDOWN] {exc}")
        return 2
    except ValueError as exc:
        print(f"[ARGS] {exc}")
        return 3


def main() -> None:
    parser = argparse.ArgumentParser(description="场景③：批准指定跟进信（草稿态→终态）")
    parser.add_argument("--readme", required=True)
    parser.add_argument(
        "--match-topic", required=True, help='README「主要事项」列的唯一定位关键字'
    )
    parser.add_argument(
        "--quote", required=True, help="批准依据摘录（如 Shao Peishen 的放行原话），必填"
    )
    parser.add_argument(
        "--cooldown-minutes", type=int, default=DEFAULT_COOLDOWN_MINUTES,
        help=f"冷却窗口分钟数（默认 {DEFAULT_COOLDOWN_MINUTES}，仅供测试/特殊场景调整）",
    )
    args = parser.parse_args()

    sys.exit(_run(args))


if __name__ == "__main__":
    main()
