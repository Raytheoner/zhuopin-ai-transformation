"""规则表装载：V3.2 JSON（正本搬运件）＋ 已签认覆盖层 ⇒ 生效规则集。

覆盖层只做她 2026-09-01 逐字签认的事（M4／M6／M10／M15／M16／M18），每条改动都从 `config.CRITERIA` 取值，
本文件不写死任何分值。**V3.2 原表一字不改**，改动以 `Rule.overlay_note` 留痕，报告里可回溯。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path

from . import config

_HERE = Path(__file__).resolve().parent
RULES_JSON_PATH = _HERE.parent / config.RULES_JSON_RELPATH


@dataclass(frozen=True)
class Rule:
    rule_id: str
    step: str
    dimension: str
    judge_method: str
    score: float
    scene: str
    criteria: str
    our_tier: str
    deduct_cap: float          # 单条扣分上限（M6／M15：≤ 满分）
    overlay_note: str = ""

    @property
    def is_semantic(self) -> bool:
        return any(m in self.judge_method for m in config.SEMANTIC_MARKERS)


@dataclass(frozen=True)
class Redline:
    redline_no: int
    step: str
    description: str
    judge_method: str
    logic: str
    overlay_note: str = ""

    @property
    def is_semantic(self) -> bool:
        return any(m in self.judge_method for m in config.SEMANTIC_MARKERS)


@dataclass(frozen=True)
class RuleSet:
    rules: tuple[Rule, ...]
    redlines: tuple[Redline, ...]
    grade_bands: tuple[tuple[str, float], ...]   # 左闭右开（M5）
    source_version: str
    sha256: str

    def for_scene(self, scene: str) -> tuple[Rule, ...]:
        return tuple(r for r in self.rules if r.scene in (config.SCENE_GENERAL, scene))

    def max_score(self, scene: str) -> float:
        return round(sum(r.score for r in self.for_scene(scene)), 2)

    def grade_of(self, score: float) -> str:
        for grade, floor in self.grade_bands:
            if score >= floor:
                return grade
        return self.grade_bands[-1][0]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_raw() -> dict:
    data = json.loads(RULES_JSON_PATH.read_text(encoding="utf-8"))
    if data.get("source", {}).get("version") != "V3.2":
        raise ValueError(f"规则表版本不是 V3.2：{data.get('source')}")
    return data


def _apply_overlay(rules: list[Rule], redlines: list[Redline]) -> tuple[list[Rule], list[Redline]]:
    c = config.CRITERIA
    out: list[Rule] = []
    m18 = c.value_of("M18_DOWNGRADE_TO_KEYWORD")
    m4 = c.value_of("M4_D3_SUBFIELD_DEDUCTION")
    m16 = c.value_of("M16_D7_03_NO_EXPANSION_DEDUCT")
    dedup = c.value_of("M10_DEDUP_GENERIC_ONLY")
    for r in rules:
        if r.rule_id in m18:
            r = replace(r, judge_method=m18[r.rule_id], overlay_note=f"M18 降级为{m18[r.rule_id]}（陈忱 2026-09-01）")
        if r.rule_id == "D3-03" and m4["merge_d3_03"]:
            # M4：D3-03 并入 D3-06（子字段完整度），其 1 分转为 D3-06 的完整度基础分（design D4）
            continue
        if r.rule_id == "D7-03":
            r = replace(r, deduct_cap=min(r.score, float(m16)), overlay_note=f"M16 无展开扣 {m16} 分（对齐权重）")
        if dedup == "a" and r.scene == config.SCENE_GENERAL and r.rule_id in _M10_GENERIC_IDS:
            r = replace(r, overlay_note=(r.overlay_note + "；" if r.overlay_note else "") + "M10(a) 通用条只判场景无关判据")
        out.append(r)
    d3_03 = next(x for x in rules if x.rule_id == "D3-03")
    out.append(Rule(
        rule_id="D3-06", step="D3", dimension="D3 子字段完整度（判例 4）", judge_method="规则引擎",
        score=d3_03.score, scene=config.SCENE_GENERAL,
        criteria="客户端＋供应商端各自：区域／数量／措施／结果／负责人／计划日／完成日／状态；缺 1 个扣 1 分、封顶 8 分（D3 段内）",
        our_tier="乙", deduct_cap=float(m4["cap"]),
        overlay_note=f"M4 新增；步长 {m4['step']}／封顶 {m4['cap']}（陈忱 2026-09-01）；D3-03 并入",
    ))
    rl_out: list[Redline] = []
    for rl in redlines:
        if rl.redline_no == 3 and "REDLINE_3" in m18:
            rl = replace(rl, judge_method=m18["REDLINE_3"], overlay_note="M18 升为纯规则引擎（但判例 11：本批不验收）")
        if rl.redline_no == 2 and c.value_of("M2_REDLINE2_ANY_MISPLACEMENT"):
            rl = replace(rl, description="章节内容与该章节主题不符（含 D3/D5 混淆）", overlay_note="M2 扩为任意错位（判例 3）；语义类，P1 转人工")
        rl_out.append(rl)
    return out, rl_out


# M10 六组里的通用条（判据内含场景分支的那一侧）
_M10_GENERIC_IDS = frozenset({"D1-02", "D2-01", "D2-02", "D4-03", "D5-02", "D6-01", "D7-01"})


def load() -> RuleSet:
    raw = load_raw()
    sha = _sha256(RULES_JSON_PATH)
    if sha != config.RULES_JSON_SHA256:
        raise ValueError(f"规则表搬运件 sha256 与 config 不符：{sha}")
    cap_on = config.CRITERIA.value_of("M6_DEDUCT_CAP_PER_RULE")
    rules = [
        Rule(
            rule_id=r["rule_id"], step=r["step"], dimension=r["dimension"], judge_method=r["judge_method"],
            score=float(r["score"]), scene=r["scene"], criteria=r["criteria"], our_tier=r["our_tier"],
            deduct_cap=float(r["score"]) if cap_on else float("inf"),
        )
        for r in raw["rules"]
    ]
    redlines = [
        Redline(redline_no=int(x["redline_no"]), step=x["step"], description=x["description"],
                judge_method=x["judge_method"], logic=x["logic"])
        for x in raw["redlines"]
    ]
    rules, redlines = _apply_overlay(rules, redlines)
    bands = tuple((g, float(f)) for g, f in config.CRITERIA.value_of("M5_GRADE_BANDS"))
    return RuleSet(rules=tuple(rules), redlines=tuple(redlines), grade_bands=bands,
                   source_version=raw["source"]["version"], sha256=sha)
