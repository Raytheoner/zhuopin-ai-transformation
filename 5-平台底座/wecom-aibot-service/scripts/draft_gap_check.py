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
  python scripts/draft_gap_check.py --window-days 14 --json

环境变量（同 push_followup_letter.py/decision_reminder_check.py 既有约定）：
  WECOM_AIBOT_REPO_ROOT   可选，显式指定仓库根，绕开动态 git 解析

队列 §一 #382⑵（2026-09-05，OP-0905-I）后续：`--json` 是给
`0-学习与工具/工具-落库sweep.py` 第 11 类常驻告警（原巡逻章程 §一.4
「起草缺口检测」下放）子进程调用用的结构化出口——同 `工具-跟进信
README查询.py --digest --json` 已验证过的范式（sweep 刻意不在自身
进程内 import `aibot_service`，见该文件里那段"零依赖"长注）。默认
文本输出（供人读、供巡逻章程未摘除前继续调用）**行为不变、一字未改**。
"""
from __future__ import annotations

import argparse
import json
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
    parser.add_argument(
        "--json", action="store_true",
        help="输出结构化 JSON（{window_days, gaps:[{recipient,scenario_prefix,"
             "event_date,commit_sha}]}）供 sweep 子进程解析，取代人读文本；"
             "README 不存在时输出 {\"error\": \"...\"} 到 stdout、退出码仍为 1，"
             "不与非 --json 分支共用 stderr+exit(1) 那条路径（子进程调用方按"
             "退出码/JSON 解析失败即视为不可用，不解析 stderr 文案）。",
    )
    args = parser.parse_args()

    queue_anchor = resolve_default_queue_anchor(NAIVE_REPO_ROOT)
    repo_root = resolve_repo_root(queue_anchor, fallback=NAIVE_REPO_ROOT)
    readme_path = repo_root / FOLLOWUP_README_RELATIVE_PATH

    if not readme_path.exists():
        if args.json:
            print(json.dumps({"error": f"跟进信 README 不存在：{readme_path}"}, ensure_ascii=False))
        else:
            print(f"[SKIP] 跟进信 README 不存在：{readme_path}", file=sys.stderr)
        sys.exit(1)

    today = date.today()
    events = find_recent_scenario_commits(repo_root, today, args.window_days)
    readme_text = readme_path.read_text(encoding="utf-8")
    gaps = find_missing_drafts(readme_text, events, today)

    if args.json:
        payload = {
            "window_days": args.window_days,
            "gaps": [
                {
                    "recipient": gap.recipient,
                    "scenario_prefix": gap.scenario_prefix,
                    "event_date": gap.event_date.isoformat(),
                    "commit_sha": gap.commit_sha,
                }
                for gap in gaps
            ],
        }
        print(json.dumps(payload, ensure_ascii=False))
        return

    print(build_gap_report(gaps, args.window_days))


if __name__ == "__main__":
    main()
