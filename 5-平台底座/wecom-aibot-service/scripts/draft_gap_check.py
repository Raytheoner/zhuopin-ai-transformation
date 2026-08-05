"""队列 #245：跟进信"该起草而没起草"缺口盘点——一次性可执行入口。

design.md D5 明确本变更（队列 #124 阶段二）只保证"起草了就必然留痕"，
"该起草而没起草"的检测留作后续独立评估——本脚本正是那个后续评估的第一
步：把"近 N 天已部署场景 vs README 已起草跟进信行"这半交叉比对交给
确定性代码完成（`aibot_service.draft_gap_detection`），供拆件巡逻 live
prompt「待发信盘点」步骤调用，替代目前"仅读 README 🆕 待发 行"的纯人工
判断。

**分工边界（写在这里，供 Cowork 侧协作者一眼看到）**：巡逻侧的调用点在
拆件巡逻定时任务 prompt（仓库外，`C:\\Users\\Paul Shao\\Claude\\Scheduled\\
huijian-chaijian-patrol\\SKILL.md`），本脚本无法从仓库内触达——需 Cowork
经 MCP `update_scheduled_task` 把「待发信盘点」步骤的扫描范围从"仅读
README 🆕 待发 行"扩展为"额外调用 `python 5-平台底座/wecom-aibot-service/
scripts/draft_gap_check.py`，把输出并入报告"。本脚本只负责把"调用后会
产出什么"实现好、可被稳定调用；**本脚本不发送任何通知**——纯只读检测，
通知载体/时机是 design D5 明确留白的独立评估项，不在本脚本范围内。

用法：
  python scripts/draft_gap_check.py
  python scripts/draft_gap_check.py --window-days 14

环境变量（同 push_followup_letter.py/decision_reminder_check.py 既有约定）：
  WECOM_AIBOT_REPO_ROOT   可选，显式指定仓库根，绕开动态 git 解析
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parent.parent
NAIVE_REPO_ROOT = SERVICE_DIR.parents[1]  # 5-平台底座/wecom-aibot-service -> 本 checkout 自身的根
sys.path.insert(0, str(SERVICE_DIR))

from aibot_service.draft_gap_detection import (  # noqa: E402
    DEFAULT_WINDOW_DAYS,
    build_gap_report,
    find_missing_drafts,
    find_recent_scenario_commits,
)
from aibot_service.repo_paths import resolve_default_queue_anchor, resolve_repo_root  # noqa: E402

FOLLOWUP_README_RELATIVE_PATH = (
    Path("6-人才与组织") / "部门AI专员跟进" / "README-跟进机制与命名约定.md"
)


def main() -> None:
    parser = argparse.ArgumentParser(description="跟进信「该起草而没起草」缺口盘点（纯检测，不发送通知）")
    parser.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    args = parser.parse_args()

    queue_anchor = resolve_default_queue_anchor(NAIVE_REPO_ROOT)
    repo_root = resolve_repo_root(queue_anchor, fallback=NAIVE_REPO_ROOT)
    readme_path = repo_root / FOLLOWUP_README_RELATIVE_PATH

    if not readme_path.exists():
        print(f"[SKIP] 跟进信 README 不存在：{readme_path}", file=sys.stderr)
        sys.exit(1)

    today = date.today()
    events = find_recent_scenario_commits(repo_root, today, args.window_days)
    readme_text = readme_path.read_text(encoding="utf-8")
    gaps = find_missing_drafts(readme_text, events, today)

    print(build_gap_report(gaps, args.window_days))


if __name__ == "__main__":
    main()
