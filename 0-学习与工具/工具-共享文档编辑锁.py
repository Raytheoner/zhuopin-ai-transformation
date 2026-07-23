"""共享文档编辑锁（协议〇.7，Paul 2026-07-23 定）。

背景：跨桌任务队列.md 是 Cowork（总线/域专线）× CC 两桌共享的唯一协调文件，
但两桌各自的"开工读→改→收工写"是本地文件读写，不经 git、没有互斥——
2026-07-23 QD-B 极简版发布收口当天，先后撞了两次：财务专线（FI2）与 QD-B
各自不知情地把 #79 用掉；随后采购专线一次会话在编辑期间被另一处 `git stash`
重置了工作区文件，它没感知到、继续用内存里的旧内容写回，导致自己刚追加的
"已完成"实质内容被当占位符覆盖——两次都靠 CC 收工时手工读 git 历史逐行
比对、按"真实最大号之后续排"重新编号才救回内容，未丢失但过程繁琐易错。

本工具把"编辑前占一个位、编辑完立刻让位"这件事固化下来，效果上等价于
"发现对方在场就等一等"，不需要人工介入修复：

  acquire  编辑跨桌任务队列.md 前先占锁；被占用（且新鲜）则拒绝——本次改为把
           要登记的内容写进自己的域接力文件，注明"队列更新待补"，不要硬写
  release  编辑完立刻释放（持锁窗口应短——只包住"读入→改→写出"这一小段，
           不要跨整个 session 持有）。带 --who 且与当前持有者不符时拒绝删除
           （只告警不删，防误传 --who 删掉别人的在办锁）；不带 --who 则无条件释放
  status   查看当前锁状态，不产生副作用

锁本地存在于文件系统（gitignore，不入库、不需要 git commit 才生效）。
REPO_ROOT 按 `git rev-parse --git-common-dir` 定位——所有 git worktree
共享同一个 `.git`，故不论从主工作区还是任一 `.claude/worktrees/<name>/`
里跑本脚本，锁都落在同一个物理文件上，彼此可见（2026-07-23 曾用
`Path(__file__).resolve()` 推算，会按各 worktree 自己的 checkout 路径
各算各的锁、互相看不见，已修复，见交接说明）。

用法：
  python 0-学习与工具/工具-共享文档编辑锁.py acquire --who "CC-QD-B" --note "登记#87完成"
  python 0-学习与工具/工具-共享文档编辑锁.py release
  python 0-学习与工具/工具-共享文档编辑锁.py status

  # 默认锁跨桌任务队列.md；--file 可指向其他高频撞车的共享文件复用本机制
  python 0-学习与工具/工具-共享文档编辑锁.py acquire --file 1-转型规划/其他共享文件.md --who "..."

陈旧锁判定：超过 STALE_MINUTES（默认 30 分钟）未释放的锁视为会话异常退出的
遗留物，下一个 acquire 会打印警告后接管，不会死锁。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _resolve_repo_root() -> Path:
    """定位主工作区根目录（所有 git worktree 共享同一把锁的关键）。

    `git rev-parse --git-common-dir` 不论在主工作区还是任一 linked
    worktree 里跑，都会解到同一个共享 `.git` 目录，其父目录即为主工作区
    根——由此不同 worktree 里的本脚本都算出同一个锁文件路径。跑不了 git
    （非仓库/未装 git）时退回按脚本自身路径推算，保底不崩。
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True, text=True, check=True,
        )
        return Path(result.stdout.strip()).parent
    except (subprocess.CalledProcessError, OSError, FileNotFoundError):
        return Path(__file__).resolve().parents[1]


REPO_ROOT = _resolve_repo_root()
DEFAULT_TARGET = "1-转型规划/0-全景路线图/跨桌任务队列.md"
STALE_MINUTES = 30


def _lock_path(target: str) -> Path:
    target_path = (REPO_ROOT / target).resolve()
    return target_path.with_name(target_path.name + ".editlock")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _read_lock(lock_path: Path) -> dict | None:
    if not lock_path.exists():
        return None
    try:
        return json.loads(lock_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _age_minutes(lock: dict) -> float:
    try:
        held_since = datetime.fromisoformat(lock["held_since"])
    except (KeyError, ValueError):
        return float("inf")  # 格式都读不出来，直接当陈旧处理
    return (_now() - held_since).total_seconds() / 60


def cmd_acquire(args: argparse.Namespace) -> int:
    lock_path = _lock_path(args.file)
    existing = _read_lock(lock_path)
    if existing is not None:
        age = _age_minutes(existing)
        if age < STALE_MINUTES:
            print(f"✗ 占用中：{existing.get('who', '未知')}"
                  f"（{existing.get('note', '')}），"
                  f"{age:.0f} 分钟前开始持锁（<{STALE_MINUTES} 分钟视为有效）。")
            print("  本次请不要直接改队列文件——把要登记的内容先写进你自己的域接力文件，"
                  "注明「队列更新待补」，下次开工/收工时再回补。")
            return 1
        print(f"⚠ 发现陈旧锁（{existing.get('who', '未知')}，{age:.0f} 分钟前，"
              f"超过 {STALE_MINUTES} 分钟未释放，判定为异常退出遗留）——已接管。")

    lock_path.write_text(
        json.dumps(
            {"who": args.who, "note": args.note or "",
             "held_since": _now().isoformat()},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    print(f"✓ 已占锁：{args.who}（{args.note or '无备注'}）→ {lock_path.name}")
    print("  改完请立刻 release，不要跨整个 session 持有。")
    return 0


def cmd_release(args: argparse.Namespace) -> int:
    lock_path = _lock_path(args.file)
    existing = _read_lock(lock_path)
    if existing is None:
        print("（无锁，无需释放）")
        return 0
    if args.who and existing.get("who") != args.who:
        print(f"✗ 当前锁持有者是「{existing.get('who')}」，与你传入的「{args.who}」不同——"
              f"未释放（避免误传 --who 时删掉别人的在办锁）。若确认对方已异常退出，"
              f"等其自然陈旧（{STALE_MINUTES} 分钟）由下一次 acquire 自动接管；"
              f"或确认后不带 --who 强制释放。")
        return 1
    lock_path.unlink()
    print("✓ 已释放")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    lock_path = _lock_path(args.file)
    existing = _read_lock(lock_path)
    if existing is None:
        print("（无锁，可直接编辑）")
        return 0
    age = _age_minutes(existing)
    state = "有效" if age < STALE_MINUTES else "已陈旧（可接管）"
    print(f"占用方：{existing.get('who', '未知')}")
    print(f"备注　：{existing.get('note', '')}")
    print(f"已持锁：{age:.0f} 分钟（{state}）")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--file", default=DEFAULT_TARGET,
                        help=f"目标文件相对仓库根路径（默认 {DEFAULT_TARGET}）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_acquire = sub.add_parser("acquire", help="编辑前占锁")
    p_acquire.add_argument("--who", required=True, help="会话标识，如 'CC-QD-B'/'Cowork-财务专线'")
    p_acquire.add_argument("--note", default="", help="简短备注，便于其他会话看到占用原因")
    p_acquire.set_defaults(func=cmd_acquire)

    p_release = sub.add_parser("release", help="编辑完立刻释放")
    p_release.add_argument("--who", default="", help="可选：校验释放的是自己占的锁")
    p_release.set_defaults(func=cmd_release)

    p_status = sub.add_parser("status", help="查看锁状态，无副作用")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
