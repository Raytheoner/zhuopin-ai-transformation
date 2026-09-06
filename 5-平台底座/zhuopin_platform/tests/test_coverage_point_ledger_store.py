"""tasks §1.3 —— 台账读写模块本体（含 append-only 审计：谁改的／何时／依据哪封回件）。

SCHEMA §三 六条约束的落点分布：

| 约束 | 落在哪 |
|---|---|
| 1. 行序 ＝ 时间序、状态单向、倒退须留 `note` | 本文件 |
| 2. `已签认` 缺 `evidence` ⇒ 拒 | `test_coverage_point_ledger_signoff.py`（D5） |
| 3. `fact_date` 不得被后续行改写、`补记` 只能加行 | 本文件（断言测试正本 ＝ tasks §3.3，本轮先把执行面做出来） |
| 4. 目录下不得有子目录 | `test_coverage_point_ledger_lint.py`（D8） |
| 5. 跨域聚合不落盘 | `test_coverage_point_ledger_aggregate.py`（D3） |
| 6. `id` 前缀与域文件不符 ⇒ 拒 | 本文件 |

🔴 本文件全部数据造在 `tmp_path`，**不碰仓库内那五份 0 字节 `.jsonl`**。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _coverage_point_ledger_helpers import (  # noqa: E402
    create_event,
    make_store,
    transition_event,
)

from zhuopin_platform.coverage_point_ledger import (  # noqa: E402
    FACT_DATE_UNKNOWN,
    Domain,
    Event,
    LedgerContractError,
    LedgerEvent,
    LedgerReadError,
    LedgerStore,
    LedgerWriteRejected,
    Status,
)


# ------------------------------------------------------------- 域与 id 前缀（§三.6）

@pytest.mark.parametrize(
    "point_id, expected",
    [
        ("SC8-D19-01", Domain.PROCUREMENT),
        ("FI10-NRV_ESTIMATION_BASIS", Domain.FINANCE),
        ("QD-B-D07-02", Domain.QUALITY),   # `QD-` 比 `Q` 长 ⇒ 质量
        ("Q9-D01-01", Domain.QUALITY),
        ("S3-D04-01", Domain.SALES),
        ("IT5-D02-01", Domain.IT),
        ("D-IT2-D01-01", Domain.IT),
    ],
)
def test_id前缀定域_最长前缀胜(point_id, expected):
    """🔑 `SC8-…` 同时命中 `SC`(采购) 与 `S`(销售)，必须由**最长前缀**裁决。

    若按声明顺序匹配，「哪个域先写在枚举里」就成了一条看不见的判据，
    而调整枚举顺序不会报任何错。
    """
    assert Domain.for_id(point_id) is expected


def test_未知前缀直接抛_不猜域():
    with pytest.raises(LedgerContractError):
        Domain.for_id("ZZ9-D01-01")


def test_写错域文件的行在读取期被抓出(tmp_path):
    """SCHEMA §三.6 的读侧：质量域的点混进财务域文件 ⇒ 抛，**不静默计入**。

    🔴 OEM 隔离红线的直接后果：串域在 `git diff` 里只是多了一行，看不出越界。
    """
    store = make_store(tmp_path)
    smuggled = create_event("QD-B-D07-02", scene="QD-B").to_json_line()
    with (store.ledger_dir / Domain.FINANCE.filename).open(
        "a", encoding="utf-8", newline="\n"
    ) as fh:
        fh.write(smuggled + "\n")

    with pytest.raises(LedgerReadError) as exc:
        store.read_domain(Domain.FINANCE)
    assert "隔离" in str(exc.value)


def test_append自动落到id对应的域文件(tmp_path):
    store = make_store(tmp_path)
    path = store.append(create_event("SC8-D19-01", scene="SC8"))
    assert path.name == Domain.PROCUREMENT.filename
    assert store.read_domain(Domain.FINANCE) == []
    assert len(store.read_domain(Domain.PROCUREMENT)) == 1


# ------------------------------------------------------------- append-only（§1.3 本体）

def test_模块不提供任何改行删行的入口():
    """🔴 「历史行永不改写」不是纪律，是**没有那个函数**。"""
    for banned in ("update", "delete", "rewrite", "replace_line", "truncate", "set_status"):
        assert not hasattr(LedgerStore, banned), f"LedgerStore 不该有 {banned}()"


def test_审计三问齐全_谁改的_何时_依据哪封回件(tmp_path):
    """tasks §1.3 括号里那三件必须逐行可查，且**不另建审计文件**（台账自己就是审计轨）。"""
    store = make_store(tmp_path)
    store.append(create_event("FI2-D19-03", scene="FI2", by="OP-0906-W"))
    store.append(
        transition_event(
            "FI2-D19-03",
            Status.IN_FLIGHT,
            by="ZhuopinFollowupDispatchDaily",
            letters=("财务部#17",),
        )
    )
    store.append(
        transition_event(
            "FI2-D19-03",
            Status.SIGNED,
            fact_date="2026-09-12",
            recorded_on="2026-09-12T14:02:00+08:00",
            by="OP-0912-B",
            evidence="7-外部文档/财务部/财务部-回复-财务部#17-2026-09-12.md",
        )
    )

    chain = store.chain("FI2-D19-03")
    assert [e.by for e in chain] == ["OP-0906-W", "ZhuopinFollowupDispatchDaily", "OP-0912-B"]
    assert all(e.recorded_on.endswith("+08:00") for e in chain)          # 何时
    assert chain[-1].evidence.startswith("7-外部文档/")                    # 依据哪封回件
    assert chain[1].letters == ("财务部#17",)

    # 不另建审计文件：目录里仍然只有五份域文件
    assert sorted(p.name for p in store.ledger_dir.iterdir()) == sorted(
        d.filename for d in Domain
    )


def test_重复建点被拒(tmp_path):
    store = make_store(tmp_path)
    store.append(create_event("FI2-D19-03", scene="FI2"))
    with pytest.raises(LedgerWriteRejected):
        store.append(create_event("FI2-D19-03", scene="FI2"))


def test_未建点直接转态被拒(tmp_path):
    store = make_store(tmp_path)
    with pytest.raises(LedgerWriteRejected) as exc:
        store.append(transition_event("FI2-D19-03", Status.IN_FLIGHT))
    assert "建点" in str(exc.value)


def test_首行不是建点则聚合期报错(tmp_path):
    """绕过 `append` 直接写文件也逃不掉：`aggregate()` 会在首行不是 `建点` 时抛。"""
    from zhuopin_platform.coverage_point_ledger import aggregate

    store = make_store(tmp_path)
    orphan = transition_event("FI2-D19-03", Status.IN_FLIGHT).to_json_line()
    with (store.ledger_dir / Domain.FINANCE.filename).open(
        "a", encoding="utf-8", newline="\n"
    ) as fh:
        fh.write(orphan + "\n")
    with pytest.raises(LedgerReadError):
        aggregate(store)


# ------------------------------------------------------------- 状态单向与倒退（§三.1）

def test_状态倒退无note被拒_有note放行(tmp_path):
    """🔑 倒退本身不禁止（现实里确有推翻重来），**无因倒退**才禁止。"""
    store = make_store(tmp_path)
    store.append(create_event("FI2-D19-03", scene="FI2"))
    store.append(
        transition_event(
            "FI2-D19-03",
            Status.SIGNED,
            evidence="7-外部文档/财务部/回复.md",
        )
    )

    with pytest.raises(LedgerWriteRejected) as exc:
        store.append(transition_event("FI2-D19-03", Status.IN_FLIGHT))
    assert "note" in str(exc.value)

    store.append(
        transition_event(
            "FI2-D19-03", Status.IN_FLIGHT, note="专员回件后又提出新反例，退回重问"
        )
    )
    assert store.current_status("FI2-D19-03") is Status.IN_FLIGHT
    # 🔴 倒退不删旧行：三行全在
    assert len(store.chain("FI2-D19-03")) == 3


def test_作废是链外终态_复活须留因(tmp_path):
    store = make_store(tmp_path)
    store.append(create_event("FI2-D19-03", scene="FI2"))
    store.append(
        LedgerEvent(
            id="FI2-D19-03",
            event=Event.VOID,
            status=Status.VOIDED,
            fact_date="2026-09-08",
            recorded_on="2026-09-08T10:00:00+08:00",
            by="OP-0906-Z-test",
            note="该点与 FI2-D19-01 重复",
        )
    )
    with pytest.raises(LedgerWriteRejected):
        store.append(transition_event("FI2-D19-03", Status.IN_FLIGHT))
    store.append(transition_event("FI2-D19-03", Status.IN_FLIGHT, note="复议，重新启用"))
    assert store.current_status("FI2-D19-03") is Status.IN_FLIGHT


def test_作废事件与已作废状态必须成对():
    with pytest.raises(LedgerContractError):
        LedgerEvent(
            id="FI2-D19-03",
            event=Event.VOID,
            status=Status.IN_FLIGHT,
            fact_date="2026-09-08",
            recorded_on="2026-09-08T10:00:00+08:00",
            by="t",
        )


# ------------------------------------------------------------- 字段契约（§二）

def test_建点行缺必填字段即抛():
    with pytest.raises(LedgerContractError) as exc:
        LedgerEvent(
            id="FI2-D19-03",
            event=Event.CREATE,
            status=Status.ASKING,
            fact_date="2026-09-06",
            recorded_on="2026-09-06T21:30:00+08:00",
            by="t",
        )
    assert "建点" in str(exc.value)


def test_建点行id与scene必须一致():
    with pytest.raises(LedgerContractError):
        create_event("FI2-D19-03", scene="FI5")


def test_建点行carrier可为空_载体缺失走度量不走写入拒绝(tmp_path):
    """⚠️ SCHEMA §二 表写 `carrier` ≥1，但同节示例的 `转态` 行都没有 —— 见 `models.py` 首部。

    本模块两类行都不在写入期强制，两条硬理由：
      ⑴ 强制会让 tasks 6.3 的质量型指标「承接载体缺失数量」**结构性恒为 0**，
         基线与「目标归零」一起失去意义；
      ⑵ 强制会逼 tasks §2 回溯拆点**编一个载体**才写得进去，而编出来的载体不产生任何信号。
    🔴 本条不是裁决，两包合审时定死。
    """
    from zhuopin_platform.coverage_point_ledger import aggregate

    store = make_store(tmp_path)
    store.append(create_event("FI2-D19-03", scene="FI2", carrier=()))
    assert store.current("FI2-D19-03").carrier == ()
    assert [p.id for p in aggregate(store).missing_carrier] == ["FI2-D19-03"]


@pytest.mark.parametrize("bad", ["2026-13-45", "20260906", "2026/09/06", "昨天", ""])
def test_fact_date形态非法即抛(bad):
    with pytest.raises(LedgerContractError):
        create_event("FI2-D19-03", scene="FI2", fact_date=bad)


def test_fact_date可写事实日未知_但不得用补记日顶替():
    """SCHEMA §二：不可考时写字面量 `事实日未知`。

    成因（tasks §3.3 实证）：2026-08-23 有 12 封信被批量补转态，真实回件日在补记
    那一刻被**覆盖式销毁**；度量中位数由 2 天变成 7 天，而底层事实一天没变。
    ⇒ 「不知道」必须有一个能被写下来的表示，否则人只会随手填一个补记日。
    """
    event = create_event("FI2-D19-03", scene="FI2", fact_date=FACT_DATE_UNKNOWN)
    assert event.fact_date == FACT_DATE_UNKNOWN
    assert json.loads(event.to_json_line())["fact_date"] == FACT_DATE_UNKNOWN


@pytest.mark.parametrize("bad", ["2026-09-06T21:30:00", "2026-09-06", "21:30:00+08:00"])
def test_recorded_on必须带时区偏移(bad):
    """🔑 没有偏移的时间戳说不清是 UTC 还是本地，而它正是算「补记滞后」的那一半。"""
    with pytest.raises(LedgerContractError):
        create_event("FI2-D19-03", scene="FI2", recorded_on=bad)


def test_carrier写成裸字符串即抛():
    """🔑 `carrier="openspec:x"` 遍历起来会逐字符跑，且不报错——必须在构造期挡掉。"""
    with pytest.raises(LedgerContractError):
        create_event("FI2-D19-03", scene="FI2", carrier="openspec:coverage-point-ledger")


# ------------------------------------------------------------- 序列化往返

def test_json往返不丢字段_未知键原样保留(tmp_path):
    """未知键**保留而不是静默丢弃** —— 丢弃一个未知键 ＝ 悄悄改写了别人写下的事实。"""
    raw = json.loads(create_event("FI2-D19-03", scene="FI2").to_json_line())
    raw["未来新增字段"] = {"a": 1}
    event = LedgerEvent.from_dict(raw)
    assert event.extra == {"未来新增字段": {"a": 1}}
    assert json.loads(event.to_json_line())["未来新增字段"] == {"a": 1}


def test_落盘行尾恒为LF_且中文不转义(tmp_path):
    """行尾唯一是「一行一事件」可比对的前提；Windows 默认会把 `\\n` 翻成 `\\r\\n`。"""
    store = make_store(tmp_path)
    store.append(create_event("FI2-D19-03", scene="FI2"))
    raw = (store.ledger_dir / Domain.FINANCE.filename).read_bytes()
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n")
    assert "判例原文".encode("utf-8") in raw


def test_坏行不跳过_直接抛(tmp_path):
    """🔴 跳过一行 ＝ 少算一个点，而少算不产生任何信号。"""
    store = make_store(tmp_path)
    with (store.ledger_dir / Domain.FINANCE.filename).open(
        "a", encoding="utf-8", newline="\n"
    ) as fh:
        fh.write("{这不是 JSON}\n")
    with pytest.raises(LedgerReadError):
        store.read_domain(Domain.FINANCE)


def test_initialize幂等且不截断已有文件(tmp_path):
    store = make_store(tmp_path)
    store.append(create_event("FI2-D19-03", scene="FI2"))
    before = (store.ledger_dir / Domain.FINANCE.filename).read_bytes()
    store.initialize()
    assert (store.ledger_dir / Domain.FINANCE.filename).read_bytes() == before


def test_五份域文件与SCHEMA一致():
    """域文件名／前缀是 SCHEMA §一 的表，改动须两边同改。"""
    assert sorted(d.filename for d in Domain) == sorted(
        ["采购域.jsonl", "财务域.jsonl", "质量域.jsonl", "销售域.jsonl", "IT域.jsonl"]
    )
