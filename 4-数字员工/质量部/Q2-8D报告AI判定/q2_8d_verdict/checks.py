"""确定性规则体：每条「规则引擎／关键词／关键词+规则」规则一个检查函数。

签名统一 ``check(rule, sections, scene) -> (ratio, evidence)``，``ratio ∈ [0,1]`` 为得分比例
（全或无＝0/1；写「扣 N 分」的条目由检查器按 M15 总则算出比例，上限封顶在 `rule.deduct_cap`）。
语义类规则**不在本文件**（`semantic.py`，签认前一律待人工）。
"""
from __future__ import annotations

from collections.abc import Callable

from . import config
from . import vocab as V
from .rules_loader import Rule

Check = Callable[[Rule, dict[str, str], str], tuple[float, str]]
_REG: dict[str, Check] = {}


def register(rule_id: str):
    def deco(fn: Check) -> Check:
        _REG[rule_id] = fn
        return fn
    return deco


def has_check(rule_id: str) -> bool:
    return rule_id in _REG


def run_check(rule: Rule, sections: dict[str, str], scene: str) -> tuple[float, str]:
    return _REG[rule.rule_id](rule, sections, scene)


def _sec(sections: dict[str, str], key: str) -> str:
    return sections.get(key, "") or ""


def _all_or_nothing(ok: bool, ev: str) -> tuple[float, str]:
    return (1.0 if ok else 0.0), ev


def _kw(rule: Rule, sections: dict[str, str], words: tuple[str, ...], min_hits: int = 1) -> tuple[float, str]:
    h = V.hits(_sec(sections, rule.step), words)
    return _all_or_nothing(len(h) >= min_hits, f"命中 {len(h)}/{min_hits}：{h}")


# ── D1 ──
@register("D1-01")
def _d1_01(rule, sections, scene):
    pairs = V.NAME_ROLE_PAIR_RE.findall(_sec(sections, "D1"))
    return _all_or_nothing(len(pairs) >= 2, f"姓名／角色配对 {len(pairs)} 条（判据：≥2）")


@register("D1-02")
def _d1_02(rule, sections, scene):
    # M10(a)：通用条只判「跨职能 ≥2 领域」，研发 ≥3 的加严在 D1-R1
    return _kw(rule, sections, V.FUNCTIONS_ALL, 2)


@register("D1-R1")
def _d1_r1(rule, sections, scene):
    return _kw(rule, sections, V.FUNCTIONS_RND, 3)


# ── D2 ──
@register("D2-01")
def _d2_01(rule, sections, scene):
    return _kw(rule, sections, V.OBJECT_WORDS_MFG + V.OBJECT_WORDS_RND)


@register("D2-02")
def _d2_02(rule, sections, scene):
    return _kw(rule, sections, V.LOCATION_WORDS_MFG + V.LOCATION_WORDS_RND)


@register("D2-03")
def _d2_03(rule, sections, scene):
    t = _sec(sections, "D2")
    ok = bool(V.DATE_RE.search(t)) or bool(V.hits(t, V.PHASE_WORDS))
    return _all_or_nothing(ok, "日期格式或阶段描述" + ("命中" if ok else "未命中"))


@register("D2-04")
def _d2_04(rule, sections, scene):
    t = _sec(sections, "D2")
    h = V.hits(t, V.WHO_WORDS) + (["脱敏令牌"] if V.SCRUB_TOKEN_RE.search(t) else [])
    return _all_or_nothing(bool(h), f"涉及方标识：{h}（乙档：阈值按≥1 实装，令牌化客户名亦算）")


@register("D2-M1")
def _d2_m1(rule, sections, scene):
    return _kw(rule, sections, V.TRACE_WORDS_MFG)


@register("D2-M2")
def _d2_m2(rule, sections, scene):
    return _kw(rule, sections, V.POSITION_WORDS_MFG)


@register("D2-R1")
def _d2_r1(rule, sections, scene):
    return _kw(rule, sections, V.SW_VERSION_WORDS)


@register("D2-R2")
def _d2_r2(rule, sections, scene):
    # M6：满分 0.5、原写扣 1 ⇒ 封顶为不得分
    return _kw(rule, sections, V.HW_VERSION_WORDS)


@register("D2-R3")
def _d2_r3(rule, sections, scene):
    return _kw(rule, sections, V.RND_EVIDENCE_WORDS)


# ── D3 ──
@register("D3-02")
def _d3_02(rule, sections, scene):
    words = V.CONTAIN_SCOPE_RND if scene == config.SCENE_RND else V.CONTAIN_SCOPE_MFG
    return _kw(rule, sections, words, 2)


def d3_missing_subfields(d3: str) -> list[str]:
    """判例 4：客户端＋供应商端各 8 项子字段，缺哪几项。段内未区分两端时按单端计。"""
    low = d3.lower()
    sides = [s for s in V.D3_SIDES if s in d3] or ["（未分端）"]
    missing: list[str] = []
    for side in sides:
        seg = low
        if side != "（未分端）":
            start = low.find(side.lower())
            ends = [low.find(o.lower(), start + 1) for o in V.D3_SIDES if o != side]
            ends = [e for e in ends if e > start]
            seg = low[start:min(ends)] if ends else low[start:]
        for f in V.D3_SUBFIELDS:
            if not any(a.lower() in seg for a in V.D3_SUBFIELD_ALIASES[f]):
                missing.append(f"{side}·{f}")
    return missing


@register("D3-06")
def _d3_06(rule, sections, scene):
    m4 = config.CRITERIA.value_of("M4_D3_SUBFIELD_DEDUCTION")
    missing = d3_missing_subfields(_sec(sections, "D3"))
    deduction = min(len(missing) * float(m4["step"]), float(m4["cap"]))
    # 本条自身满分（D3-03 并入的 1 分）为完整度基础分；超出部分作为 D3 段内扣分（engine 按 deduct_cap 扣）
    ratio = 1.0 if not missing else 0.0
    return ratio, f"缺 {len(missing)} 项：{missing}；段内扣 {deduction} 分（步长 {m4['step']}／封顶 {m4['cap']}）"


# ── D4 ──
@register("D4-01")
def _d4_01(rule, sections, scene):
    return _kw(rule, sections, V.TOOL_WORDS)


@register("D4-02")
def _d4_02(rule, sections, scene):
    n = len(V.WHY_RE.findall(_sec(sections, "D4")))
    return _all_or_nothing(n >= 3, f"追问词 {n} 次（判据：≥3）")


@register("D4-M1")
def _d4_m1(rule, sections, scene):
    t = _sec(sections, "D4")
    dims = [d for d, ws in V.M5E1_DIMS.items() if V.hits(t, ws)]
    return _all_or_nothing(len(dims) >= 4, f"5M1E 覆盖 {len(dims)} 维：{dims}（判据：≥4）")


# ── D5 ──
@register("D5-04")
def _d5_04(rule, sections, scene):
    t = _sec(sections, "D5")
    has_person = bool(V.NAME_ROLE_PAIR_RE.search(t)) or any(w in t for w in ("负责人", "责任人"))
    has_date = bool(V.DATE_RE.search(t)) or "计划" in t and "日" in t
    missing = [n for n, ok in (("负责人", has_person), ("计划日期", has_date)) if not ok]
    # 「缺失任一扣 1 分」，满分 2 ⇒ 比例 = 1 − 缺项×1/2（M15 封顶）
    ratio = max(0.0, 1.0 - len(missing) * 1.0 / rule.score)
    return ratio, f"缺：{missing or '无'}"


# ── D6 ──
@register("D6-R1")
def _d6_r1(rule, sections, scene):
    return _kw(rule, sections, V.REGRESSION_WORDS)


# ── D7 ──
def d7_fixed_to_process_assets(d7: str, scene: str) -> tuple[bool, str]:
    """红线⑥／D7-02 共用：D7 是否「提及更新」了流程资产（判例 7：填 N／留空／无更新语义 ＝ 未固化）。"""
    words = V.FMEA_WORDS if scene == config.SCENE_MFG else V.RND_FIX_WORDS
    h = V.hits(d7, words)
    if not h:
        return False, "未提及 " + "/".join(words)
    if V.FILLED_N_RE.search(d7):
        return False, f"提及 {h} 但填 N／留空（判例 7 视同未固化）"
    if not V.hits(d7, V.UPDATE_WORDS):
        return False, f"提及 {h} 但无更新语义（判例 7）"
    return True, f"提及 {h} 且含更新语义"


@register("D7-01")
def _d7_01(rule, sections, scene):
    n = config.CRITERIA.value_of("M14_D7_KEYWORD_THRESHOLD")["d7_01_min_hits"]
    return _kw(rule, sections, V.DOC_WORDS_MFG + V.DOC_WORDS_RND, n)


@register("D7-02")
def _d7_02(rule, sections, scene):
    ok, ev = d7_fixed_to_process_assets(_sec(sections, "D7"), scene)
    return _all_or_nothing(ok, ev)


@register("D7-M1")
def _d7_m1(rule, sections, scene):
    return _kw(rule, sections, V.DOC_WORDS_MFG)


@register("D7-M2")
def _d7_m2(rule, sections, scene):
    return _kw(rule, sections, V.CP_WORDS)


@register("D7-M3")
def _d7_m3(rule, sections, scene):
    return _kw(rule, sections, V.TRAIN_WORDS)


@register("D7-R1")
def _d7_r1(rule, sections, scene):
    return _kw(rule, sections, V.TESTCASE_WORDS)


@register("D7-R2")
def _d7_r2(rule, sections, scene):
    return _kw(rule, sections, V.STATIC_WORDS)
