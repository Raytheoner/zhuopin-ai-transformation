"""生产真身冒烟：对**当前 README** 跑一遍回件配对判定，只读、不写任何文件。

派单件 `OP-0823-D` §五.4 要求的那条验收——它防的是一个具体形态：
**机制上线当天就是哑的**（同「`#82` 建成 9 天、每天在跑，却从来没真正发出
过一条消息」那一族）。单测跑的是自己造的夹具，夹具永远长得刚刚好；只有拿
生产真身跑一遍，才知道那 20 封从未闭环的历史信会不会把每一次配对都堵死。

用法（只读，随时可跑）：
  python scripts/smoke_followup_pairing.py
  python scripts/smoke_followup_pairing.py --expect IT部#9      # 断言某封信必须被命中
  python scripts/smoke_followup_pairing.py --readme <路径>       # 指定另一份 README

退出码：0 ＝ 全部断言通过；1 ＝ 有断言失败（含 `--expect` 未命中）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parent.parent

# —— 平台底座路径引导（队列 #345 收拢；唯一被允许的样板）。必须放在本文件任何
# zhuopin_platform / 场景包 import 之前。——
_HERE = Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        sys.path.insert(0, str(_p / "5-平台底座" / "zhuopin_platform"))
        break
from zhuopin_platform.bootstrap import ensure_paths  # noqa: E402
ensure_paths(__file__, SERVICE_DIR)  # noqa: E402

from zhuopin_platform.shared_tools import followup_gate  # noqa: E402

from aibot_service.followup_readme_bridge import (  # noqa: E402
    FOLLOWUP_README_REL,
    _letter_rows,
)


def _repo_root() -> Path:
    for parent in _HERE.parents:
        if (parent / FOLLOWUP_README_REL).is_file():
            return parent
    raise SystemExit(f"✗ 未能从 {_HERE} 向上找到含跟进信 README 的仓库根。")


def main() -> int:
    parser = argparse.ArgumentParser(description="回件配对生产真身冒烟（只读）")
    parser.add_argument("--readme", default=None, help="README 路径（默认自动定位）")
    parser.add_argument(
        "--expect", action="append", default=[],
        help="断言这封信必须被其部门的通道②命中（可重复，如 --expect IT部#9）",
    )
    args = parser.parse_args()

    readme_path = (Path(args.readme).resolve() if args.readme
                   else _repo_root() / FOLLOWUP_README_REL)
    text = readme_path.read_text(encoding="utf-8")
    letters, _ = _letter_rows(text)

    print(f"📍 README：{readme_path}")
    print(f"   共 {len(letters)} 行\n")

    # 🔴 2026-08-23 `OP-0823-D` 实测踩到的坑，值得留成一道常驻提示：
    # 从 worktree 里跑本脚本时，`_repo_root()` 找到的是**该 worktree 自己的
    # README**——它冻结在分支点，与主工作区的真身可能相差几个小时。当天
    # `财务部#15` 在 worktree 副本里是 `⏳ 待你审`，主工作区真身已是
    # `✅ 已推送 08:26 UTC`，**同一个相对路径、两个不同的事实**，而两边都
    # 读得出结果、都不报错。「生产真身冒烟」这五个字里，"真身"是关键。
    if ".claude" in readme_path.parts and "worktrees" in readme_path.parts:
        print("⚠ 本次读的是 **worktree 副本**，不是主工作区真身——它冻结在分支点。")
        print("  生产冒烟请显式指定：--readme <主工作区>/"
              f"{FOLLOWUP_README_REL}\n")

    # —— §3.1bis 健康检查（只报数，不参与判定）——
    unclosed = followup_gate.unclosed_dispatched_by_department(letters)
    total_unclosed = sum(len(v) for v in unclosed.values())
    print(f"§3.1bis 健康检查：已发出未闭环共 {total_unclosed} 封")
    for dept, items in sorted(unclosed.items()):
        print(f"   {dept}：{len(items)} 封 —— {'、'.join(i.number for i in items)}")
    print()

    # —— 逐部门跑一次通道②（用一个必然配不上 stem 的纯文字回件名）——
    departments = sorted({r.department for r in letters if r.department})
    hits: dict[str, str] = {}
    failures: list[str] = []

    print("通道② 逐部门判定（输入＝纯文字回件，stem 必然不命中）：")
    for dept in departments:
        archive = f"{dept}部-某某-回复-2026-08-23-文本反馈-smoke01"
        outcome = followup_gate.pair_reply_to_letter(
            archive_filename=archive, department=dept, rows=letters,
        )
        mark = "✓ 命中" if outcome.matched else "· 未命中"
        target = outcome.letter.number if outcome.letter else "—"
        print(f"   {mark}　{dept}　→ {target}　[{outcome.channel}]")
        print(f"        {outcome.detail}")
        if outcome.matched:
            hits[dept] = outcome.letter.number
        # 🔴 这一条是本脚本的核心断言：不论命中与否，**都必须得出一个确定的
        # 结论**。方案 B（唯一在途）在这里会因为「≥2 封」而对四个部门全部
        # 拒绝判定——那正是「上线即哑」的可观测形态。
        if outcome.channel not in (
            followup_gate.PAIR_CHANNEL_STEM,
            followup_gate.PAIR_CHANNEL_LATEST,
            followup_gate.PAIR_MISS_LATEST_CLOSED,
            followup_gate.PAIR_MISS_NO_DISPATCHED,
            followup_gate.PAIR_MISS_NO_DEPARTMENT,
        ):
            failures.append(f"{dept}：出现未知配对通道 {outcome.channel!r}")
    print()

    # —— 断言：历史未闭环信没有阻塞任何一次配对 ——
    for dept, items in sorted(unclosed.items()):
        if len(items) < 2:
            continue
        outcome = followup_gate.pair_reply_to_letter(
            archive_filename=f"{dept}部-某某-回复-2026-08-23-文本反馈-smoke02",
            department=dept, rows=letters,
        )
        if outcome.channel == followup_gate.PAIR_MISS_NO_DISPATCHED:
            failures.append(
                f"{dept}：有 {len(items)} 封已发出未闭环信，却判为「无已发出的信」"
                f"——历史积压阻塞了配对"
            )
        else:
            print(f"✓ {dept} 有 {len(items)} 封历史未闭环信，配对仍得出确定结论"
                  f"（{outcome.channel}）——未被阻塞")
    print()

    for expected in args.expect:
        dept = followup_gate.recipient_department(f"{expected} · x") or ""
        parsed = followup_gate.parse_letter_number(expected)
        dept = followup_gate.normalize_department(parsed[0]) if parsed else dept
        if hits.get(dept) != expected:
            failures.append(
                f"--expect {expected} 未满足：{dept} 实际命中 {hits.get(dept)!r}"
            )
        else:
            print(f"✓ --expect {expected} 满足")

    if failures:
        print("\n✗ 冒烟未通过：")
        for f in failures:
            print(f"   - {f}")
        return 1
    print("\n✓ 冒烟通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
