"""tasks §2bis 的 2b.1 断言测试 —— **台账写入 CLI**。

判据（tasks 2b.1 原文）四条，逐条一个用例：

| # | 判据 | 用例 |
|---|---|---|
| ⑴ | 转态写得进去，`recorded_on` 由 CLI 当场取、带 `+08:00` | `test_transition_写入成功_recorded_on带东八区偏移` |
| ⑵ | `--status 已签认` 缺 `--evidence` ⇒ exit≠0（D5 不开口子） | `test_2b1_已签认缺evidence退出码3且零字节变化` |
| ⑶ | 唯一写盘仍经 `LedgerStore.append_many` | `test_2b1_CLI没有自己的写盘路径` |
| ⑷ | `points-by-letter` 认信编号、括注容忍 | `test_points_by_letter_*` |

🔴 全部数据造在 `tmp_path`，一律显式传 `--ledger-dir`；**没有任何一条会碰到仓库内
那五份真台账**（另有 `test_默认台账目录解析指向仓库真身_只读不写` 一条只读地验证
默认解析确实指向真身，但它不调 `transition`）。
"""
from __future__ import annotations

import ast

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _coverage_point_ledger_helpers import (  # noqa: E402
    REAL_LEDGER_DIR,
    create_event,
    make_store,
    transition_event,
    tree_fingerprint,
)

import zhuopin_platform.coverage_point_ledger as cpl  # noqa: E402
from zhuopin_platform.coverage_point_ledger import PointType, Status  # noqa: E402
from zhuopin_platform.coverage_point_ledger import cli as ledger_cli  # noqa: E402

_PKG_DIR = Path(cpl.__file__).resolve().parent


@pytest.fixture
def ledger(tmp_path):
    """一份 tmp 台账，里面有一个已建点的 `FI10-G-07`（`材料索取`，当前 `待问`）。"""
    store = make_store(tmp_path)
    store.append(
        create_event(
            "FI10-G-07",
            scene="FI10",
            point_type=PointType.MATERIAL_REQUEST,
            fact_date="2026-09-06",
        )
    )
    return store


def run_cli(ledger_dir: Path, *argv: str) -> int:
    return ledger_cli.main(["--ledger-dir", str(ledger_dir), *argv])


# ---------------------------------------------------------------- ⑴ 写得进去

def test_transition_写入成功_recorded_on带东八区偏移(ledger, capsys):
    code = run_cli(
        ledger.ledger_dir,
        "transition",
        "--id", "FI10-G-07",
        "--status", "在途",
        "--fact-date", "2026-09-07",
        "--by", "OP-0907-AK-test",
        "--letters", "财务部#17",
    )
    assert code == 0
    assert "[OK]" in capsys.readouterr().out

    current = ledger.current("FI10-G-07")
    assert current.status is Status.IN_FLIGHT
    assert current.letters == ("财务部#17",)
    assert current.fact_date == "2026-09-07"
    assert current.recorded_on.endswith("+08:00"), (
        "recorded_on 必须带偏移——没有偏移的时间戳说不清是 UTC 还是本地，"
        "而它正是算「补记滞后」的那一半"
    )


def test_2b1_recorded_on是当场取的本机时刻_不是事实日(ledger):
    """`recorded_on` ≠ `fact_date`：前者由 CLI 当场取，后者由调用方给。

    🔑 这一条是 tasks 3.3 那 12 封信的反面：一旦 CLI 图省事把 `fact_date` 也
    当成"今天"，事实日就在写入那一刻被今天顶替了，且**不产生任何信号**。
    """
    before = datetime.now(tz=timezone(timedelta(hours=8)))
    run_cli(
        ledger.ledger_dir,
        "transition",
        "--id", "FI10-G-07", "--status", "在途",
        "--fact-date", "2023-01-01",  # 一个绝不可能等于"今天"的事实日
        "--by", "OP-0907-AK-test",
    )
    after = datetime.now(tz=timezone(timedelta(hours=8)))

    current = ledger.current("FI10-G-07")
    assert current.fact_date == "2023-01-01", "事实日必须原样落，不得被写入日顶替"
    recorded = datetime.fromisoformat(current.recorded_on)
    assert before.replace(microsecond=0) <= recorded <= after, (
        "recorded_on 应当落在本次调用的时间窗内（当场取本机时刻）"
    )


def test_2b1_事实日未知是合法字面量(ledger):
    assert run_cli(
        ledger.ledger_dir,
        "transition", "--id", "FI10-G-07", "--status", "在途",
        "--fact-date", "事实日未知", "--by", "OP-0907-AK-test",
    ) == 0
    assert ledger.current("FI10-G-07").fact_date == "事实日未知"


def test_2b1_编出来的事实日形态被拒(ledger):
    """**反向对照组**：形态不对的 `--fact-date` 必须退出码 3，不得被静默接受。"""
    assert run_cli(
        ledger.ledger_dir,
        "transition", "--id", "FI10-G-07", "--status", "在途",
        "--fact-date", "2026年9月7日", "--by", "OP-0907-AK-test",
    ) == ledger_cli.EXIT_REJECTED


# ---------------------------------------------------------------- ⑵ D5 不开口子

def test_2b1_已签认缺evidence退出码3且零字节变化(ledger, capsys):
    """**2b.1 主断言**：`--status 已签认` 没有 `--evidence` ⇒ exit≠0，台账一个字节没长。

    🔑 断言两件而不是一件：退出码非零**且**台账指纹不变。只断言退出码的话，
    一个"先写进去再报错"的实现同样能让它绿——而那正是 D5 要防的事本身。
    """
    before = tree_fingerprint(ledger.ledger_dir)
    code = run_cli(
        ledger.ledger_dir,
        "transition", "--id", "FI10-G-07", "--status", "已签认",
        "--fact-date", "2026-09-12", "--by", "OP-0907-AK-test",
    )
    assert code == ledger_cli.EXIT_REJECTED != 0
    out = capsys.readouterr().out
    assert "evidence" in out and "D5" in out
    assert tree_fingerprint(ledger.ledger_dir) == before, "被拒的行不得留下任何痕迹"
    assert ledger.current_status("FI10-G-07") is Status.ASKING


def test_2b1_已回灌缺evidence同样被拒(ledger):
    assert run_cli(
        ledger.ledger_dir,
        "transition", "--id", "FI10-G-07", "--status", "已回灌",
        "--fact-date", "2026-09-20", "--by", "OP-0907-AK-test",
    ) == ledger_cli.EXIT_REJECTED


def test_2b1_带evidence的已签认写得进去_正向对照组(ledger):
    """**正向对照组**：有落档回件时必须写得进去。

    🔑 没有这一条，上面那两条"拒绝"可能只是因为**这个 CLI 谁也写不进去**——
    一个把所有输入都拒掉的实现同样能让拒绝类断言全绿。
    """
    run_cli(
        ledger.ledger_dir, "transition", "--id", "FI10-G-07", "--status", "在途",
        "--fact-date", "2026-09-07", "--by", "OP-0907-AK-test", "--letters", "财务部#17",
    )
    code = run_cli(
        ledger.ledger_dir,
        "transition", "--id", "FI10-G-07", "--status", "已签认",
        "--fact-date", "2026-09-12", "--by", "OP-0907-AK-test",
        "--letters", "财务部#17",
        "--evidence", "7-外部文档/财务部/财务部-回复-财务部#17-2026-09-12.md",
    )
    assert code == 0
    current = ledger.current("FI10-G-07")
    assert current.status is Status.SIGNED
    assert current.evidence == "7-外部文档/财务部/财务部-回复-财务部#17-2026-09-12.md"


def test_2b1_状态choices不含待问与已落码():
    """CLI 只开三个状态口 —— `建点` 与终态各有自己的流程，不在无头会话里就地补。"""
    assert ledger_cli.TRANSITIONABLE == ("在途", "已签认", "已回灌")
    with pytest.raises(SystemExit) as exc:
        ledger_cli.build_parser().parse_args(
            ["transition", "--id", "X", "--status", "待问", "--fact-date", "2026-09-07",
             "--by", "t"]
        )
    assert exc.value.code == 2


def test_2b1_未建点的id写转态被拒(ledger):
    assert run_cli(
        ledger.ledger_dir,
        "transition", "--id", "FI10-NOT-CREATED", "--status", "在途",
        "--fact-date", "2026-09-07", "--by", "OP-0907-AK-test",
    ) == ledger_cli.EXIT_REJECTED


# ---------------------------------------------------------------- ⑶ 不新增写盘路径

def test_2b1_CLI没有自己的写盘路径():
    """`cli.py` 的源码里不得出现任何写文件的调用 —— 写只经 `LedgerStore.append_many`。

    🔑 与 tasks §1.5 的 `test_D5_全包只有一处写台账内容的代码` 是**两条**而非重复：
    那条断言"全包只有一处"，本条断言"新增的这个文件不是第二处"，且指名点姓地说
    清楚该走哪个函数。两条一起红时，读的人立刻知道是新加的 CLI 越界了。
    """
    tree = ast.parse((_PKG_DIR / "cli.py").read_text(encoding="utf-8"))
    write_calls = []
    append_many_calls = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name in ("write_text", "write_bytes", "open"):
            write_calls.append(name)
        if name == "append_many":
            append_many_calls += 1
    assert write_calls == [], f"cli.py 长出了自己的写盘路径：{write_calls}"
    assert append_many_calls == 1, "写入必须且只能经 LedgerStore.append_many 一次"


def test_2b1_定位不到台账目录时不新建目录顶上(tmp_path, capsys):
    """显式传一个**不存在**的目录 ⇒ 写入不得"顺手建一个"。

    🔴 `LedgerStore.append` 自己会 `mkdir(parents=True)`——那是给真台账目录用的，
    此处要断言的是：传错路径时长出来的**不是**一本静悄悄的第二本账。本例走
    「无建点行」被拒这条路，故目录不会被建出内容；断言写入被拒即可。
    """
    missing = tmp_path / "不存在的台账"
    code = run_cli(
        missing, "transition", "--id", "FI10-G-07", "--status", "在途",
        "--fact-date", "2026-09-07", "--by", "OP-0907-AK-test",
    )
    assert code == ledger_cli.EXIT_REJECTED
    assert "建点" in capsys.readouterr().out


def test_默认台账目录解析指向仓库真身_只读不写():
    """不传 `--ledger-dir` 时，默认解析必须落在仓库那份真台账上。

    🔴 只做路径比对，**不调 `transition`** —— 本文件不往真台账写一个字节。
    """
    assert ledger_cli.resolve_ledger_dir(None).resolve() == REAL_LEDGER_DIR.resolve()


# ---------------------------------------------------------------- ⑷ 按信查点

def test_points_by_letter_查到投影点(ledger, capsys):
    ledger.append(transition_event("FI10-G-07", Status.IN_FLIGHT, letters=("财务部#17",)))
    assert run_cli(ledger.ledger_dir, "points-by-letter", "--letter", "财务部#17") == 0
    out = capsys.readouterr().out
    assert "[POINT] FI10-G-07" in out
    assert "投影 1 个点" in out


def test_points_by_letter_起草期括注也认得(ledger, capsys):
    """台账里的真实写法带括注（`财务部#17（待你审，暂不占号）`，`OP-0907-L` 真身实例）。

    🔑 字面量比较会把它与干净的 `财务部#17` 判成两封信，而判错之后的外观是
    「这封信不投影任何点」——与真的不投影一模一样，不产生任何信号。
    """
    ledger.append(
        transition_event(
            "FI10-G-07", Status.IN_FLIGHT, letters=("财务部#17（待你审，暂不占号）",)
        )
    )
    assert run_cli(ledger.ledger_dir, "points-by-letter", "--letter", "财务部#17") == 0
    assert "[POINT] FI10-G-07" in capsys.readouterr().out


def test_points_by_letter_非投影信退出码0且报固定一句(ledger, capsys):
    """`采购部#21` 形态：不投影任何点 ⇒ **退出码 0**，报固定一句。

    🔑 非零会让拆件巡逻把一封正常的信当成失败去重试／报警——把"正常"报成"故障"
    与把"故障"报成"正常"同样是失真。
    """
    assert run_cli(ledger.ledger_dir, "points-by-letter", "--letter", "采购部#21") == 0
    out = capsys.readouterr().out
    assert cpl.NON_PROJECTION_REPORT_LINE in out
    assert "[POINT]" not in out


def test_points_by_letter_认不出的编号是报错_不是零投影(ledger, capsys):
    """**反向对照组**：认不出的东西必须报错，不得与"零投影"共用同一个外观。"""
    code = run_cli(ledger.ledger_dir, "points-by-letter", "--letter", "随便一串字")
    assert code == ledger_cli.EXIT_REJECTED
    out = capsys.readouterr().out
    assert cpl.NON_PROJECTION_REPORT_LINE not in out


def test_points_by_letter_不写盘(ledger):
    ledger.append(transition_event("FI10-G-07", Status.IN_FLIGHT, letters=("财务部#17",)))
    before = tree_fingerprint(ledger.ledger_dir)
    run_cli(ledger.ledger_dir, "points-by-letter", "--letter", "财务部#17")
    assert tree_fingerprint(ledger.ledger_dir) == before


# ---------------------------------------------------------------- 文档一致性

def test_2b1_用法与tasks判据同形():
    """CLI 的参数面必须与 tasks 2b.1 写死的那一行同形（漂了就是两份口径）。"""
    help_text = ledger_cli.build_parser().format_help()
    assert "transition" in help_text and "points-by-letter" in help_text

    # tasks 2b.1 逐字写死的那七个开关，一个不少地能被解析（不是"源码里出现过"）。
    parsed = ledger_cli.build_parser().parse_args(
        [
            "transition", "--id", "FI10-G-07", "--status", "已签认",
            "--fact-date", "2026-09-12", "--by", "OP-0912-B",
            "--letters", "财务部#17", "财务部#18",
            "--evidence", "7-外部文档/财务部/回复.md",
            "--note", "一句话",
        ]
    )
    assert parsed.id == "FI10-G-07"
    assert parsed.status == "已签认"
    assert parsed.fact_date == "2026-09-12"
    assert parsed.by == "OP-0912-B"
    assert parsed.letters == ["财务部#17", "财务部#18"], "`--letters` 须收多封"
    assert parsed.evidence == "7-外部文档/财务部/回复.md"
    assert parsed.note == "一句话"
