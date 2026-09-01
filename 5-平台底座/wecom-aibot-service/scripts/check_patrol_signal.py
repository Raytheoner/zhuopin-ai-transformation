"""队列 #382⑴：拆件巡逻「桥一打标即开班」——轻量高频探测入口。

## 它替代的是什么

拆件巡逻此前工作日固定双班，回件到手到有人拆件之间天然隔半个班次。本
脚本把「有没有新回件到达」的判断从「扫 2 MB 队列真身」降到「看一个几
百字节的信号文件在不在」——空跑（无信号）成本近乎零，可以比双班频繁
得多地探测，把「打标到开班」的延迟从半个班次压到分钟级。

## 分工边界（写在这里，供 Cowork 侧协作者一眼看到）

巡逻侧的调用点在拆件巡逻定时任务 prompt（仓库外，`C:\\Users\\Paul Shao\\
Claude\\Scheduled\\huijian-chaijian-patrol\\SKILL.md`），本脚本无法从
仓库内触达或触发它——同 `draft_gap_check.py`（#245）文首已记录的同一条
边界，本次实测再次证实：`mcp__scheduled-tasks__list_scheduled_tasks`
从 CC worktree 能看到的只是另一个互不相干的任务库（`.claude\\
scheduled-tasks\\`，当前仅 2 个一次性任务），看不见、也碰不到
`huijian-chaijian-patrol`。**需 Cowork 在其能触达该 store 的会话里用
MCP `update_scheduled_task` 完成两步**：

1. 章程最前面（§一「扫描」之前）插入一段「〇ter、事件驱动开班判据」：
   先跑 `python 5-平台底座/wecom-aibot-service/scripts/check_patrol_signal.py`；
   输出以 `[NO-SIGNAL]` 开头 → 聊天回一句「空巡（事件驱动，无信号）」，
   本班到此结束，§一~§四 全部不跑；输出以 `[SIGNAL]` 开头 → 按章程原有
   §一~§四 全套流程正常执行，**执行完毕、报告已登记 §二 批次之后**，
   再跑一次 `python .../check_patrol_signal.py --clear --before <CHECKPOINT
   值>`（`CHECKPOINT=` 那一行原样取值）消费信号；🔴 探测脚本本身报错/
   找不到/输出不认得 → 一律当作 `[SIGNAL]` 处理（**fail-open，宁可多扫
   一次空跑，不可因为探测脚本本身坏了而让一条真实回件被漏判**，同本仓
   OP-0819-F「探针通了 ≠ 机制通了」一族的反面：机制原本是通的，不能因
   为新加的旁路探测坏了而被拖累一起哑掉）。
2. 把 cron 频率从「工作日双班固定时刻」调高到分钟级轻量轮询（建议
   `*/10 * * * *`，即每 10 分钟一次；无信号时的探测成本只是一次文件是否
   存在的判断，7×24 常跑亦可）。**旧的「工作日双班」那句描述性文字本次
   不改**——`huijian-chaijian-patrol/SKILL.md` 第 8 行已明写「落地验活
   前本章程照旧执行，任何步骤的摘除由总线改本章程」，摘除动作留给
   Cowork 在完成上述两步、确认真实运行无误后执行。

## 信号从哪来

`aibot_service.followup_readme_bridge.mark_reply_arrived` 在把回件标为
第九态（`ACTION_MARKED`，真实发生了状态变化的那一刻）的同一把编辑锁内，
调用 `patrol_signal.raise_signal` 落一条信号（见该模块文首设计取舍）。

用法（只读探测，随时可跑；`--clear` 会真的删信号，仅供开班收工时调用）：
  python scripts/check_patrol_signal.py
  python scripts/check_patrol_signal.py --check
  python scripts/check_patrol_signal.py --clear --before 2026-09-01T05:30:00Z
  python scripts/check_patrol_signal.py --clear            # 整份清空，供手工重置

环境变量（同 draft_gap_check.py/push_followup_letter.py 既有约定）：
  WECOM_AIBOT_REPO_ROOT   可选，显式指定仓库根，绕开动态 git 解析

退出码：0 ＝ 探测/清空动作本身执行成功（不论有没有信号）；1 ＝ 脚本自身
出错（如仓库根解析失败）——**SKILL.md 里的探测判据只认 stdout 文本前缀，
不认退出码**，本仓库对 `%ERRORLEVEL%`/管道吞退出码已有过真实事故
（OP-0819-F ⑵），机器判据不再叠加第二套依据退出码的分支。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parent.parent
NAIVE_REPO_ROOT = SERVICE_DIR.parents[1]  # 5-平台底座/wecom-aibot-service -> 本 checkout 自身的根
sys.path.insert(0, str(SERVICE_DIR))

from aibot_service import patrol_signal  # noqa: E402
from aibot_service.repo_paths import resolve_default_queue_anchor, resolve_repo_root  # noqa: E402


def _format_check(snapshot: "patrol_signal.SignalSnapshot") -> str:
    if snapshot.corrupted:
        return (
            "[SIGNAL] 信号文件损坏，按有信号处理（fail-open，见 patrol_signal.py "
            "文首设计取舍 1）——请正常开班；收工后用不带 --before 的 --clear 整份重置。"
        )
    if not snapshot.present:
        return "[NO-SIGNAL] 空巡（事件驱动，无待处理信号）"
    timestamps = sorted(str(item.get("at", "")) for item in snapshot.pending)
    earliest, latest = timestamps[0], timestamps[-1]
    lines = [
        f"[SIGNAL] 待处理 {len(snapshot.pending)} 条，最早 {earliest}，最新 {latest}",
    ]
    for item in snapshot.pending:
        lines.append(
            f"   - {item.get('letter_number') or '（未配对）'}　"
            f"{item.get('archived_filename', '')}　{item.get('at', '')}"
        )
    lines.append(f"CHECKPOINT={latest}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="拆件巡逻事件驱动开班——信号探测/消费（#382⑴）")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="只读探测（默认动作）")
    group.add_argument("--clear", action="store_true", help="消费信号")
    parser.add_argument(
        "--before", default=None,
        help="配合 --clear：只移除 at<=此时间戳的条目（取自 --check 输出的 CHECKPOINT 值）；"
             "不传则整份清空",
    )
    args = parser.parse_args()

    queue_anchor = resolve_default_queue_anchor(NAIVE_REPO_ROOT)
    repo_root = resolve_repo_root(queue_anchor, fallback=NAIVE_REPO_ROOT)

    if args.clear:
        removed = patrol_signal.clear_signal(repo_root, before=args.before)
        remaining = patrol_signal.read_signal(repo_root)
        note = (
            f"（扫描期间又有 {len(remaining.pending)} 条新到，原样保留、下次探测仍会命中）"
            if remaining.present else ""
        )
        print(f"[CLEARED] 已消费 {removed} 条信号{note}")
        return 0

    snapshot = patrol_signal.read_signal(repo_root)
    print(_format_check(snapshot))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
