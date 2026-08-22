"""判例回灌黄金基准（2026-08-22，变更包 `sc2-caseback-fix`）。

**被测的是一件很具体的事**：姚祖怡 2026-08-21 判例批改回件里自算的 8 个周行数，
我方能不能用改后的口径复现出来。这套断言存在的理由是——那五条环比之所以全部
对不上，不是某个算式写错，而是**两条口径**同时偏了：

1. **周序编号**：ISO 8601 的 W1 是「含首个周四的那一周」（2026 年即 2025-12-29 起，
   主体落在上一年），采购从本年首个周一 2026-01-05 起算 W1 ⇒ **2026 全年 ISO 比
   采购口径大 1**。
2. **行集边界**：全程委外订单不算采购下单行；订单侧端点按**交货计划行**返回，
   采购数的是**订单行**（28,345 行里只有 27,874 个唯一 `(单号, 行号)`）。

🔴 **两条残差如实钉在测试里，不调参去凑**（他的 W17 与 W21）：他的 W17=38，而
本端点该周全部单据类型、不去重的总行数就是 **37** ⇒ **38 在本端点内不可达**。
把它写成断言而不是注释，是为了让「我们知道这里差 2 行、且知道为什么」成为一个
会被 CI 一直守着的事实——而不是某份报告里一句迟早被读丢的话。

夹具 `fixtures/real_order_lines_2026W17-W28.json` 是真实 ERP 行（2026-08-22 取），
只含周序与行集判定用得到的四个字段，不含供应商、料号、价格与数量。
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest

from sc2.sources import OUTSOURCE_DOC_TYPES
from sc2.windows import procurement_week, week_of

FIXTURE = Path(__file__).parent / "fixtures" / "real_order_lines_2026W17-W28.json"

#: 姚祖怡 2026-08-21 判例批改回件中**他自己算的**周行数，逐字誊录。
#: 来源：`7-外部文档/采购部/采购部-YaoZuYi-回复-2026-08-21-…-SC2采购周报口径判例批改-*.docx`
HIS_WEEK_LINE_COUNTS = {17: 38, 18: 92, 19: 79, 20: 164, 21: 107,
                        25: 106, 26: 553, 27: 241}

#: 两条查明原因、不可复现的残差（design「三、残差」）。**留在这里是为了不被忘记。**
KNOWN_RESIDUALS = {17: "本端点该周全部类型不去重共 37 行 ⇒ 38 不可达",
                   21: "无任何单一过滤规则能同时让本周与其余 7 周都对上"}


def _load_rows():
    if not FIXTURE.exists():                     # pragma: no cover - 夹具缺失即跳过
        pytest.skip(f"缺少真实数据夹具：{FIXTURE}")
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["行"]


def _weekly_counts(rows, *, drop_outsource=True, dedupe=True):
    """按**采购口径周号**统计下单行数。"""
    seen: set[tuple[str, int]] = set()
    counts: dict[int, int] = {}
    for erp_no, line_no, make_date, doc_type in rows:
        if drop_outsource and doc_type in OUTSOURCE_DOC_TYPES:
            continue
        key = (str(erp_no), line_no)
        if dedupe:
            if key in seen:
                continue
            seen.add(key)
        day = datetime.date.fromisoformat(make_date)
        _, week = procurement_week(week_of(day).start)
        counts[week] = counts.get(week, 0) + 1
    return counts


def test_六个周的行数与他的自算数逐字相等():
    """8 周中 6 周精确命中——这是"口径对上了"的硬证据，不是近似。"""
    counts = _weekly_counts(_load_rows())
    exact = {w: v for w, v in HIS_WEEK_LINE_COUNTS.items() if w not in KNOWN_RESIDUALS}
    for week, expected in sorted(exact.items()):
        assert counts.get(week) == expected, (
            f"采购口径 W{week}：我方 {counts.get(week)}，他 {expected}")
    assert len(exact) == 6


def test_两条残差仍是残差且量未变():
    """残差本身也要被守住：**它变大了要知道，它悄悄变没了更要知道**。

    若哪天这两个数对上了，说明取数口径又动过一次——那时该回头核实是真修好了，
    还是把别的周弄错了才凑上的。
    """
    counts = _weekly_counts(_load_rows())
    assert counts.get(17) == 36, "W17 残差量变了（原为 36 vs 他的 38）"
    assert counts.get(21) == 112, "W21 残差量变了（原为 112 vs 他的 107）"


def test_他的W17在本端点内确实不可达():
    """把「38 不可达」证明成一个可执行的事实，而不是一句注释。"""
    rows = _load_rows()
    ceiling = _weekly_counts(rows, drop_outsource=False, dedupe=False).get(17)
    assert ceiling == 37
    assert ceiling < HIS_WEEK_LINE_COUNTS[17], (
        "本端点该周的行数上限低于他给的数 ⇒ 差额不可能由过滤条件解释")


def test_不做行集边界处理时误差大一个数量级():
    """反例：证明那两条边界不是可有可无的调参，而是结论成立的前提。"""
    rows = _load_rows()
    good = _weekly_counts(rows)
    bad = _weekly_counts(rows, drop_outsource=False, dedupe=False)
    err = lambda c: sum(abs(c.get(w, 0) - v)                       # noqa: E731
                        for w, v in HIS_WEEK_LINE_COUNTS.items())
    assert err(good) < err(bad) / 3


def test_按ISO周号统计则五条环比全错():
    """还原事故本身：不改周序、只改行集，五个环比仍然与他对不上。

    这条是本次修复的**因果证据**——它证明周序那一步不是顺手改的，而是不改就错。
    """
    rows = _load_rows()
    seen, iso_counts = set(), {}
    for erp_no, line_no, make_date, doc_type in rows:
        if doc_type in OUTSOURCE_DOC_TYPES:
            continue
        key = (str(erp_no), line_no)
        if key in seen:
            continue
        seen.add(key)
        w = datetime.date.fromisoformat(make_date).isocalendar().week
        iso_counts[w] = iso_counts.get(w, 0) + 1
    hits = sum(1 for w, v in HIS_WEEK_LINE_COUNTS.items() if iso_counts.get(w) == v)
    assert hits == 0, "按 ISO 周号竟命中了他的数，说明本测试的前提已不成立"


@pytest.mark.parametrize("week,expected_pct", [
    (19, -14.13),      # 79 vs 92
    (26, +421.70),     # 553 vs 106
    (27, -56.42),      # 241 vs 553
])
def test_他给的环比在我方口径下逐字复现(week, expected_pct):
    """他信里写死的环比百分比，用我方改后的口径重算，须落在 ±0.05 个百分点内。

    🔴 **他一共给了五条环比，这里只测三条**——另外两条（W18／W21）的**行数**本身
    就是上面那两条残差，环比自然跟着差（W18 我方 +155.6% 对他 +142.11%；W21 我方
    −31.7% 对他 −34.76%）。**不把它们塞进来假装全过**：派单件 §五.1 那条「五条
    全部一致」的硬判据，本包只达成 3/5，如实登记在 design「三、残差」。
    """
    counts = _weekly_counts(_load_rows())
    cur, prev = counts[week], counts[week - 1]
    pct = (cur - prev) / prev * 100
    assert pct == pytest.approx(expected_pct, abs=0.05)
