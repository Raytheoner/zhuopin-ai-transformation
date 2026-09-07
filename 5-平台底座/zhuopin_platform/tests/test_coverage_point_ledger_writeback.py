"""tasks §2bis 的 2b.4 断言测试 —— **回件 → 台账回写（拆件 skill §三 4bis）两组**。

判据（tasks 2b.4 原文）：

| 组 | 断言 | 反向对照 |
|---|---|---|
| ⑴ 负样本 | 非投影信跑 4bis ⇒ **五份域文件字节数前后相等** | 投影信跑同一段逻辑 ⇒ 字节数**必须**变（否则上一条只是因为这段逻辑什么都不做） |
| ⑵ 正样本 | `FI10-G-07` 模拟回件 ⇒ 恰**一行** `已签认` 且带 `evidence`，`fact_date` ＝ 回件日而非写入日 | 同一回件缺 `evidence` ⇒ 拒、零字节变化、全库无 `已签认` |

🔴 **本文件里的「跑 4bis」＝ 逐字调 SKILL.md §三 4bis 写的那两条命令**（经
`cli.main`，与无头拆件会话跑的是同一段代码）。不另写一份"测试专用的 4bis 逻辑"
——那样测的就是测试自己，而不是那个会在凌晨自动跑起来的东西。

🔴 全部数据造在 `tmp_path`；仓库内那五份真台账一个字节都不碰。
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _coverage_point_ledger_helpers import (  # noqa: E402
    create_event,
    make_store,
    transition_event,
)

from zhuopin_platform.coverage_point_ledger import (  # noqa: E402
    NON_PROJECTION_REPORT_LINE,
    Domain,
    PointType,
    Status,
)
from zhuopin_platform.coverage_point_ledger import cli as ledger_cli  # noqa: E402

#: 回件落档日 —— 刻意取一个**绝不可能等于测试运行日**的过去日期，
#: 好让「`fact_date` ＝ 回件日而非写入日」这条断言无条件成立，而不是
#: 「今天恰好不是那一天」才成立。
REPLY_FILED_ON = "2023-05-18"
EVIDENCE = "7-外部文档/财务部/财务部-唐燕萍-回复-财务部#17-2023-05-18-跌价计提底稿.md"


def domain_sizes(ledger_dir: Path) -> dict[str, int]:
    """五份域文件的字节数 —— 2b.4 原文的判据就是这个。"""
    return {d.filename: (ledger_dir / d.filename).stat().st_size for d in Domain}


@pytest.fixture
def ledger(tmp_path):
    """`FI10-G-07` 已建点、已 `在途`（投影信 ＝ `财务部#17`）的一份 tmp 台账。"""
    store = make_store(tmp_path)
    store.append(
        create_event(
            "FI10-G-07",
            scene="FI10",
            point_type=PointType.MATERIAL_REQUEST,
            fact_date="2026-09-06",
        )
    )
    store.append(
        transition_event("FI10-G-07", Status.IN_FLIGHT, letters=("财务部#17",))
    )
    return store


def run_4bis_step1(ledger_dir: Path, letter: str) -> int:
    """SKILL.md §三 4bis ⑴：`points-by-letter`（只读）。"""
    return ledger_cli.main(
        ["--ledger-dir", str(ledger_dir), "points-by-letter", "--letter", letter]
    )


def run_4bis_signoff(
    ledger_dir: Path, point_id: str, letter: str, *, evidence: str | None
) -> int:
    """SKILL.md §三 4bis ⑶「已答」那条：`transition --status 已签认`。"""
    argv = [
        "--ledger-dir", str(ledger_dir),
        "transition", "--id", point_id, "--status", "已签认",
        "--fact-date", REPLY_FILED_ON,
        "--by", "huijian-chaijian-patrol",
        "--letters", letter,
    ]
    if evidence is not None:
        argv += ["--evidence", evidence]
    return ledger_cli.main(argv)


def signed_rows(store) -> list:
    """全库（五个域）里所有 `已签认` 行 —— 断言"恰一行"用。"""
    return [e for e in store.iter_events() if e.status is Status.SIGNED]


# ============================================================ ⑴ 负样本

def test_2b4_负样本_非投影信跑4bis_五份域文件字节数不变(ledger, capsys):
    """**2b.4 组⑴ 主断言**：`采购部#21` 形态 —— 走完 4bis，台账一个字节没长。

    🔑 断言的是**字节数**而不是"没报错"：一次"顺手建个点""顺手补一行在途"
    在退出码上与什么都没干完全一样，只有字节数会说实话。
    """
    before = domain_sizes(ledger.ledger_dir)

    code = run_4bis_step1(ledger.ledger_dir, "采购部#21")

    assert code == 0, "非投影信是正常形态，不得报错——否则巡逻会把它当故障重试"
    out = capsys.readouterr().out
    assert NON_PROJECTION_REPORT_LINE in out, "报告里那句固定话必须出自代码常量"
    assert "[POINT]" not in out
    assert domain_sizes(ledger.ledger_dir) == before
    # 4bis ⑵ 明写「本步到此结束、不写台账」：此处不再跑 transition，正是断言那一条。


def test_2b4_负样本反向对照_投影信跑同一段逻辑字节数必须变(ledger):
    """**组⑴ 反向对照**：换成投影信 `财务部#17`，同一段逻辑必须真的写进去。

    🔑 没有这一条，上面那条"字节数不变"可能只是因为**这段逻辑什么都不做**——
    一个空实现能让所有"没有副作用"的断言全绿。
    """
    before = domain_sizes(ledger.ledger_dir)

    assert run_4bis_step1(ledger.ledger_dir, "财务部#17") == 0
    assert run_4bis_signoff(
        ledger.ledger_dir, "FI10-G-07", "财务部#17", evidence=EVIDENCE
    ) == 0

    after = domain_sizes(ledger.ledger_dir)
    assert after["财务域.jsonl"] > before["财务域.jsonl"], "投影信必须真的写得进去"
    assert {k: v for k, v in after.items() if k != "财务域.jsonl"} == {
        k: v for k, v in before.items() if k != "财务域.jsonl"
    }, "🔴 只该动财务域那一份——写串域即 OEM 隔离越界（D2 派生）"


def test_2b4_负样本_只读一步本身不写盘(ledger):
    """`points-by-letter` 对**投影信**也必须只读 —— 查一下不该改变任何东西。"""
    before = domain_sizes(ledger.ledger_dir)
    run_4bis_step1(ledger.ledger_dir, "财务部#17")
    assert domain_sizes(ledger.ledger_dir) == before


# ============================================================ ⑵ 正样本

def test_2b4_正样本_模拟回件恰一行已签认且带evidence_事实日是回件日(ledger):
    """**2b.4 组⑵ 主断言**：`FI10-G-07` 收到回件 ⇒ 恰一行 `已签认`。

    四件一起断，缺一条都留得下一个能装作通过的实现：
      ⑴ 全库 `已签认` 行**恰一行**（不是"至少一行"——重复写两行同样是错的）；
      ⑵ 那一行带 `evidence`，且就是传进去的落档件路径；
      ⑶ `fact_date` ＝ **回件落档日**，不是写入日；
      ⑷ `recorded_on` ＝ **今天**（写入日照常记下来，两者并存 ＝ 补记滞后可算）。
    """
    assert run_4bis_signoff(
        ledger.ledger_dir, "FI10-G-07", "财务部#17", evidence=EVIDENCE
    ) == 0

    rows = signed_rows(ledger)
    assert len(rows) == 1, f"应恰一行 `已签认`，实得 {len(rows)} 行"
    row = rows[0]
    assert row.id == "FI10-G-07"
    assert row.evidence == EVIDENCE
    assert row.letters == ("财务部#17",)
    assert row.fact_date == REPLY_FILED_ON, "事实日必须是回件落档日"
    assert row.recorded_on[:10] == date.today().isoformat(), "写入日必须是今天"
    assert row.fact_date != row.recorded_on[:10], (
        "🔴 事实日与写入日一旦合流，`补记滞后` 就永远算成 0——"
        "而 tasks 3.3 那 12 封信被覆盖掉的正是这个差值"
    )
    assert ledger.current_status("FI10-G-07") is Status.SIGNED


def test_2b4_正样本反向对照_同一回件缺evidence则拒且全库无已签认(ledger):
    """**组⑵ 反向对照**：同一封回件，只把 `--evidence` 去掉 ⇒ 必须拒。

    🔑 变量只有一个（`--evidence` 有无），所以这条红了就一定是 D5 那道闸松了，
    不会是"别的什么变了"。断三件：退出码非 0、字节数不变、全库找不出 `已签认`。
    """
    before = domain_sizes(ledger.ledger_dir)

    code = run_4bis_signoff(ledger.ledger_dir, "FI10-G-07", "财务部#17", evidence=None)

    assert code == ledger_cli.EXIT_REJECTED != 0
    assert domain_sizes(ledger.ledger_dir) == before, "被拒的行不得留下任何痕迹"
    assert signed_rows(ledger) == []
    assert ledger.current_status("FI10-G-07") is Status.IN_FLIGHT, (
        "🔑 没有回件就让它留在 `在途`——超期只出催办草稿，不改状态（D5）"
    )


def test_2b4_正样本_未答的点保持在途_零写入(ledger):
    """4bis ⑶「未答 ⇒ 什么都不写」：不跑 `transition` 就该一个字节都不动。

    这条看着像废话，但它是 4bis 那三个分支里**唯一没有命令要跑**的一支——
    正因为没有命令，最容易被实现成"顺手记一行 `在途` 表示看过了"。
    """
    before = domain_sizes(ledger.ledger_dir)
    assert run_4bis_step1(ledger.ledger_dir, "财务部#17") == 0
    assert domain_sizes(ledger.ledger_dir) == before
    assert ledger.current_status("FI10-G-07") is Status.IN_FLIGHT


def test_2b4_正样本_已签认后重复跑一次不产生第二行(ledger):
    """幂等边界如实登记：**重复跑会产生第二行 `已签认`**（append-only 的必然）。

    🔴 本条**不是**在断言"它是幂等的"——它不是。台账是事件账，同一条命令跑两次
    就是记下了两次事件。断言写在这里是为了让这件事**被看见**：4bis 的调用方
    （拆件巡逻）必须按信只跑一次，重跑要先看 `points-by-letter` 的当前状态。
    """
    run_4bis_signoff(ledger.ledger_dir, "FI10-G-07", "财务部#17", evidence=EVIDENCE)
    run_4bis_signoff(ledger.ledger_dir, "FI10-G-07", "财务部#17", evidence=EVIDENCE)
    assert len(signed_rows(ledger)) == 2, (
        "append-only：跑两次就是两行。若这里变成 1，说明有人加了去重／改前行的逻辑，"
        "那正是本包在防的东西"
    )
