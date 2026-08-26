"""outbox 中继体检（队列 `#394`）—— **只读、绝不发送、绝不建连接**。

用途：在真发之前回答三个问题，且**不惊动任何人**：

  ⑴ 配的那几份 outbox，本机现在**读得到吗**（`.51` → 笔记本那条文件通路通不通）；
  ⑵ 里面积压着几条、分别是哪个场景哪一期；
  ⑶ 每一条会被投到**哪个 chatid/userid**，或者会因为什么原因投不出去。

🔴 **本脚本刻意没有发送路径。** 两条理由，任一单独成立：

- **单实例约束**：真发就得建一条自己的长连接，而全局唯一那条长连接归常驻
  服务（同 BotID 多处长连接互相踢线，2026-08-06 已真实复现）。一个"顺手看
  一眼"的体检工具不该有把常驻服务踢下线的能力。
- **`#394` 硬约束③**：首条真实送达须有人对着收件群看一眼——chatid 采集只
  证明「机器人收到过来自该 chatid 的消息」，**不证明它就是采购部群**。那一
  步是人的动作，不该被一个 CLI 顺手做掉。

⇒ 真实投递只发生在常驻服务里（`run_aibot_service.py` 的后台中继任务）。

用法：
  python scripts/check_outbox_relay.py
  python scripts/check_outbox_relay.py --path "\\\\192.168.100.51\\sc2\\reports\\sc2_group_outbox.jsonl"

不传 `--path` 时读环境变量 `WECOM_AIBOT_OUTBOX_PATHS`（同常驻服务）。

退出码：0 ＝ 全部 outbox 可读且没有结构性投不出去的记录；
        1 ＝ 有 outbox 读不到（🔴 通路问题，**不等于"没有待发"**）；
        2 ＝ 全部可读，但存在结构性投不出去的记录（配置/契约问题）。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

SERVICE_DIR = Path(__file__).resolve().parent.parent

# —— 平台底座路径引导（队列 #345 收拢；唯一被允许的样板，实现见
# `5-平台底座/zhuopin_platform/zhuopin_platform/bootstrap.py`）。必须放在本文件任何
# zhuopin_platform / 场景包 import 之前。下方五行只负责让 bootstrap 自身可被 import、
# 不含任何判断分支；开发机 monorepo 与 `.51` 扁平部署两种布局的分歧由 ensure_paths 处理。——
_HERE = Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        sys.path.insert(0, str(_p / "5-平台底座" / "zhuopin_platform"))
        break
from zhuopin_platform.bootstrap import ensure_paths  # noqa: E402
ensure_paths(__file__, SERVICE_DIR)  # noqa: E402

from aibot_service.department_group_chatid_mapping import (  # noqa: E402
    load_department_group_chatid_mapping,
)
from aibot_service.outbox_relay import (  # noqa: E402
    OUTBOX_PATHS_ENV,
    SKIP_EXPLANATIONS,
    OutboxReadError,
    iter_pending,
    resolve_outbox_paths,
    resolve_target,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="outbox 中继体检（只读，不发送）")
    parser.add_argument(
        "--path", action="append",
        help=f"outbox 路径，可重复传入；不传则读 {OUTBOX_PATHS_ENV}",
    )
    args = parser.parse_args()

    load_dotenv(SERVICE_DIR.parent / ".env")

    if args.path:
        paths = resolve_outbox_paths(os.pathsep.join(args.path))
    else:
        paths = resolve_outbox_paths(os.environ.get(OUTBOX_PATHS_ENV))

    if not paths:
        print(f"[关闭] 未配置 {OUTBOX_PATHS_ENV}，也未传 --path。")
        print("       ⇒ 常驻服务此刻**不会**代发任何 outbox 消息："
              "SC2/FI2 写进去的会一直积压。")
        sys.exit(0)

    mapping = load_department_group_chatid_mapping()
    unreadable = 0
    undeliverable = 0

    for path in paths:
        print(f"\n=== {path} ===")
        try:
            pending, corrupt = iter_pending(path)
        except OutboxReadError as exc:
            unreadable += 1
            print(f"  🔴 读不到：{exc}")
            print("     ⚠️ 读不到 **不等于** 没有待发消息——请先确认这条文件通路。")
            continue

        for index, _raw in corrupt:
            undeliverable += 1
            print(f"  🔴 第 {index + 1} 行：{SKIP_EXPLANATIONS['corrupt_line']}")

        if not pending:
            print("  ✅ 无积压（0 条待投递）。")
            continue

        print(f"  积压 {len(pending)} 条待投递：")
        for entry in pending:
            target, reason = resolve_target(entry.record, mapping)
            if target is None:
                undeliverable += 1
                print(f"  🔴 {entry.describe()} → 投不出去：{SKIP_EXPLANATIONS[reason]}")
            else:
                print(f"  ⏳ {entry.describe()} → {target.kind}:{target.target}")

    print()
    if unreadable:
        print(f"[退出 1] {unreadable} 份 outbox 读不到——先修文件通路。")
        sys.exit(1)
    if undeliverable:
        print(f"[退出 2] {undeliverable} 条结构性投不出去——先修配置/契约。"
              "这些记录会**留在 outbox 里**，不会被丢弃。")
        sys.exit(2)
    print("[退出 0] 全部 outbox 可读，且没有结构性投不出去的记录。")
    sys.exit(0)


if __name__ == "__main__":
    main()
