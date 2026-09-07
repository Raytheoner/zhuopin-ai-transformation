"""口径点台账命令行入口（tasks §2bis 的 2b.1）。

## 为什么必须有它

`OP-0906-Z` 把台账建成了，但**写盘只有 Python 入口**（`LedgerStore.append`）。
拆件巡逻是**无头会话**（`~/Claude/Scheduled/huijian-chaijian-patrol`，`〇bis`
非交互班次），它能跑命令、不能 import 一个包再拼 dataclass ——于是 2026-09-07
`采购部#21` 回件 14:03 到、30 分钟自动拆完，**台账零回写**：不是故障，是这一段
路根本没建。本文件就是那一段路。

## 用法

    python -m zhuopin_platform.coverage_point_ledger.cli transition \\
        --id FI10-G-07 --status 已签认 --fact-date 2026-09-12 --by OP-0912-B \\
        --letters 财务部#17 \\
        --evidence 7-外部文档/财务部/财务部-回复-财务部#17-2026-09-12.md

    python -m zhuopin_platform.coverage_point_ledger.cli points-by-letter \\
        --letter 财务部#17

## 退出码（判据，勿改语义）

| 码 | 含义 |
|---|---|
| 0 | 成功。**`points-by-letter` 查到 0 个点也是 0** —— 「这封信不投影任何点」是正常形态（`采购部#21`），不是错误 |
| 2 | argparse 用法错误（缺必填参数等，argparse 自带） |
| 3 | 台账拒绝：契约不满足或写入被拒（**含 D5「`已签认` 缺 `--evidence`」**） |
| 4 | 台账读取失败（坏行／`id` 前缀与域文件不符） |
| 5 | 定位不到台账目录 |

## 🔴 三条刻意

  · **不新增写盘路径**：写只经 `LedgerStore.append_many`，本文件里没有任何
    `open(..., "w"/"a")`／`write_text`。tasks §1.5 的
    `test_D5_全包只有一处写台账内容的代码` 用 AST 扫全包，本文件一旦长出第二处
    写盘那条断言立刻红 —— 它扫的就是本包这个目录。
  · **不在 CLI 侧重写 D5 判据**：`--status 已签认` 缺 `--evidence` 的拒绝，靠的是
    `LedgerEvent` 构造期的不变式 ⑸（见 `models.py`），本文件只负责把那个异常
    转成退出码 3 并把话说清楚。**CLI 侧若另写一份检查，就会有两份可能不一致的
    D5**，而两份不一致时松的那份说了算。
  · **不提供 `建点`**：建点行有五个必填字段（判例原文／拟改判定等），那是起草
    与 grill 的产物、不是回件回写时能就地编出来的。要建点走 Python 入口或
    Cowork 落档，本 CLI 只做转态 —— 少一个能在无头会话里被"顺手补全"的入口。
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .errors import LedgerContractError, LedgerReadError, LedgerWriteRejected
from .letters import NON_PROJECTION_REPORT_LINE, points_for_letter
from .models import Event, LedgerEvent, Status
from .store import LEDGER_DIR_RELPATH, LedgerStore

EXIT_OK = 0
EXIT_REJECTED = 3
EXIT_READ_FAILED = 4
EXIT_NO_LEDGER = 5

#: 本 CLI 允许写的状态 —— `待问` 是建点行的事，`已落码`／`已作废` 各有自己的流程。
TRANSITIONABLE = (Status.IN_FLIGHT.value, Status.SIGNED.value, Status.FED_BACK.value)

#: 项目时区。`recorded_on` 必须带偏移（`models._RECORDED_ON_RE`）——没有偏移的
#: 时间戳在「UTC 还是本地」上永远说不清，而它正是算「补记滞后」的那一半。
_TZ_SHANGHAI = timezone(timedelta(hours=8), name="+08:00")


def now_recorded_on() -> str:
    """当场取本机时刻，落成 `+08:00` 的 ISO 串（秒精度）。

    🔴 取的是**当前瞬间**再表示成 +08:00，不是"把本地墙上时间贴一个 +08:00"——
    后者在机器时区不是东八区时会写出一个不存在的时刻，而且不报错。
    """
    return datetime.now(tz=_TZ_SHANGHAI).isoformat(timespec="seconds")


def resolve_ledger_dir(explicit: str | None) -> Path:
    """定位台账目录：显式给就用显式的；否则从本文件向上找仓库根。

    找不到即抛 —— **不回落到当前工作目录下新建一个**：那会在某个临时目录里
    长出第二本账，而且写入全部成功、没有任何东西会报错。
    """
    if explicit:
        return Path(explicit)
    for parent in Path(__file__).resolve().parents:
        candidate = parent / LEDGER_DIR_RELPATH
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(
        f"从 {Path(__file__).resolve()} 向上找不到 `{LEDGER_DIR_RELPATH}`。"
        f"请显式传 `--ledger-dir`。🔴 本命令不会替你新建一个目录顶上——"
        f"那样写入会全部成功，而写进去的是第二本账。"
    )


def _cmd_transition(args: argparse.Namespace) -> int:
    ledger_dir = resolve_ledger_dir(args.ledger_dir)
    store = LedgerStore(ledger_dir)

    # 🔴 构造在前、写入在后，两步分开：构造期抛的是「这一行本身不合法」
    # （D5 缺 evidence 即在此处），写入期抛的是「这一行放在这条链上不合法」
    # （无建点行、无因倒退、串域）。两类原因合并成一个 try 会让报错话说不清。
    event = LedgerEvent(
        id=args.id,
        event=Event.TRANSITION,
        status=args.status,
        fact_date=args.fact_date,
        recorded_on=now_recorded_on(),
        by=args.by,
        letters=tuple(args.letters or ()),
        evidence=args.evidence,
        note=args.note,
        carrier=tuple(args.carrier or ()),
        due=args.due,
    )

    paths = store.append_many([event])
    print(
        f"[OK] {event.id} → {event.status.value}"
        f"（fact_date={event.fact_date}，recorded_on={event.recorded_on}）"
        f" 已追加至 {paths[0]}"
    )
    return EXIT_OK


def _cmd_points_by_letter(args: argparse.Namespace) -> int:
    ledger_dir = resolve_ledger_dir(args.ledger_dir)
    points = points_for_letter(LedgerStore(ledger_dir), args.letter)

    if not points:
        # 🔴 退出码 0：不投影任何点是**正常形态**（`采购部#21` 即此形态）。
        # 非零会让拆件巡逻把一封正常的信当成失败去重试／报警。
        print(f"[NONE] {NON_PROJECTION_REPORT_LINE}（{args.letter}）")
        return EXIT_OK

    for point in points:
        evidence = point.current.evidence or "-"
        print(f"[POINT] {point.id}\t{point.status.value}\t{point.domain.label}域\t{evidence}")
    print(f"[OK] {args.letter} 投影 {len(points)} 个点")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m zhuopin_platform.coverage_point_ledger.cli",
        description="口径点台账命令行（tasks §2bis 2b.1）——转态写入 ＋ 按信查点。",
    )
    parser.add_argument(
        "--ledger-dir",
        help=f"台账目录；不传则从本包向上找 `{LEDGER_DIR_RELPATH}`。",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    t = sub.add_parser("transition", help="给一个已建点的口径点追加一行转态")
    t.add_argument("--id", required=True, help="口径点 id，如 FI10-G-07")
    t.add_argument("--status", required=True, choices=TRANSITIONABLE)
    t.add_argument(
        "--fact-date",
        required=True,
        help="该状态**实际发生**的日期 YYYY-MM-DD（回件日／发出日），"
        "不可考写 `事实日未知`；🔴 不得用今天顶替（成因见 tasks 3.3 的 12 封信）",
    )
    t.add_argument("--by", required=True, help="写入者：会话编号 OP-… 或人名")
    t.add_argument("--letters", nargs="*", help="该点由哪封信投影，如 财务部#17，可多封")
    t.add_argument(
        "--evidence",
        help="落档回件路径（仓库根相对）。🔴 `已签认`／`已回灌` 必填，缺即退出码 3（D5）",
    )
    t.add_argument("--note", help="回退原因／补记说明；状态倒退时必填")
    t.add_argument("--carrier", nargs="*", help="承接载体，如 openspec:<change>")
    t.add_argument("--due", help="回复期限 YYYY-MM-DD，非空则进超期扫描")
    t.set_defaults(func=_cmd_transition)

    q = sub.add_parser(
        "points-by-letter",
        help="查一封信投影了哪些点（只读）——回件侧 4bis 的第一步",
    )
    q.add_argument("--letter", required=True, help="信编号，如 财务部#17（带括注亦可）")
    q.set_defaults(func=_cmd_points_by_letter)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print(f"[NO-LEDGER] {exc}")
        return EXIT_NO_LEDGER
    except (LedgerContractError, LedgerWriteRejected) as exc:
        print(f"[REJECTED] {exc}")
        return EXIT_REJECTED
    except LedgerReadError as exc:
        print(f"[READ-FAILED] {exc}")
        return EXIT_READ_FAILED


if __name__ == "__main__":
    sys.exit(main())
