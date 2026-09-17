"""六条红线的判定流（顺序在 engine 里：判例 9 结构闸 → 本文件 → 评分）。

  ①D4 根因未到底层   语义 ⇒ P1：关键词预筛（判例 8 范式的表面原因词）出「疑似」，否则待语义层；永不自动判 D
  ②章节错位（M2 扩） 语义 ⇒ 判例 11 本批不验收，一律转人工
  ③D2 无客观数据     M18 升纯规则引擎，但判例 11 本批不验收 ⇒ 规则引擎结果只作证据、状态恒转人工
  ④关键追溯信息缺失   规则引擎 ⇒ P2：仅 HIGH 置信＋确认为空 ≥2 项才触发；有抽取未命中 ⇒ 转人工核
  ⑤D4 根因未经验证   语义 ⇒ 同①（验证词预筛）
  ⑥D7 未固化流程资产 关键词 ⇒ 判例 7：填 N／无更新语义视同未提及 ⇒ 自动判 D
"""
from __future__ import annotations

from . import config
from . import vocab as V
from .checks import d7_fixed_to_process_assets
from .models import Confidence, EightDInput, RedlineFinding, RedlineStatus, TraceField
from .rules_loader import Redline
from .semantic import SemanticSource

_TRACE_MFG = (("产品型号/零件号", V.OBJECT_WORDS_MFG), ("批次号/Lot", ("批次", "Lot", "LOT")), ("发生时间", ()))
_TRACE_RND = (("ECU型号/软硬件版本", V.OBJECT_WORDS_RND + V.SW_VERSION_WORDS + V.HW_VERSION_WORDS), ("发生时间", ()))


def derive_trace_fields(scene: str, d2: str) -> tuple[TraceField, ...]:
    """从 D2 文本派生追溯字段：命中＝HIGH 有值；未命中＝LOW 空（＝抽取未命中，不是真为空）。"""
    spec = _TRACE_RND if scene == config.SCENE_RND else _TRACE_MFG
    out = []
    for name, words in spec:
        if name == "发生时间":
            m = V.DATE_RE.search(d2)
            val = m.group(0) if m else ""
        else:
            h = V.hits(d2, words)
            val = "、".join(h)
        out.append(TraceField(name, val, Confidence.HIGH if val else Confidence.LOW))
    return tuple(out)


def _semantic_redline(rl: Redline, doc: EightDInput, src: SemanticSource, prescreen: tuple[bool, str]) -> RedlineFinding:
    verdict = src.redline_triggered(rl.redline_no, doc)
    if verdict is True:
        st = RedlineStatus.TRIGGERED if src.kind == "human" else RedlineStatus.SUSPECTED
        return RedlineFinding(rl.redline_no, rl.step, rl.description, st, f"{src.kind} 裁决：触发")
    if verdict is False:
        return RedlineFinding(rl.redline_no, rl.step, rl.description, RedlineStatus.CLEAR, f"{src.kind} 裁决：未触发")
    hit, ev = prescreen
    if hit:
        return RedlineFinding(rl.redline_no, rl.step, rl.description, RedlineStatus.SUSPECTED, "关键词预筛：" + ev)
    return RedlineFinding(rl.redline_no, rl.step, rl.description, RedlineStatus.MANUAL_CHECK, "语义层未上线（PENDING.SEMANTIC_LAYER_ACCEPTANCE）；" + ev)


def evaluate_redlines(rules_redlines: tuple[Redline, ...], doc: EightDInput, sections: dict[str, str],
                      scene: str, src: SemanticSource) -> tuple[RedlineFinding, ...]:
    not_accepted = set(config.CRITERIA.value_of("J11_REDLINES_2_3_NOT_ACCEPTED_THIS_BATCH"))
    auto_d = set(config.CRITERIA.value_of("P1_SEMANTIC_REDLINE_MANUAL")["auto_d_redlines"])
    d2, d4, d7 = sections.get("D2", ""), sections.get("D4", ""), sections.get("D7", "")
    out: list[RedlineFinding] = []
    for rl in rules_redlines:
        n = rl.redline_no
        if n in not_accepted:
            ev = "判例 11：本批反例为 0，不验收、转人工"
            if n == 3:
                has_data = bool(V.NUMBER_RE.search(d2)) or bool(V.hits(d2, ("批次", "Lot", "检测数据")))
                ev += f"；规则引擎预判＝{'有客观数据' if has_data else '无数字/无批次'}（仅作证据）"
            out.append(RedlineFinding(n, rl.step, rl.description, RedlineStatus.NOT_ACCEPTED, ev))
        elif n == 1:
            surf = V.hits(d4, V.SURFACE_CAUSE_WORDS)
            out.append(_semantic_redline(rl, doc, src, (bool(surf), f"D4 含表面原因词 {surf}" if surf else "D4 无表面原因词")))
        elif n == 5:
            ver = V.hits(d4, V.VERIFY_WORDS)
            out.append(_semantic_redline(rl, doc, src, (not ver, "D4 无任何验证词" if not ver else f"D4 含验证词 {ver}")))
        elif n == 4:
            fields = doc.trace_fields or derive_trace_fields(scene, d2)
            empties = [f.name for f in fields if f.confirmed_empty]
            misses = [f.name for f in fields if f.extraction_miss]
            if len(empties) >= 2 and n in auto_d:
                st, ev = RedlineStatus.TRIGGERED, f"确认为空（HIGH）≥2 项：{empties}"
            elif misses and len(empties) + len(misses) >= 2:
                st, ev = RedlineStatus.MANUAL_CHECK, f"抽取未命中 {misses}、确认为空 {empties}——P2 不当真为空，转人工核"
            else:
                st, ev = RedlineStatus.CLEAR, f"追溯字段齐：{[f.name for f in fields if f.value]}"
            out.append(RedlineFinding(n, rl.step, rl.description, st, ev))
        elif n == 6:
            if doc.template == "客户模板" and not d7.strip():
                out.append(RedlineFinding(n, rl.step, rl.description, RedlineStatus.MANUAL_CHECK, "客户模板 D7 无对应段，转人工核"))
                continue
            ok, ev = d7_fixed_to_process_assets(d7, scene)
            st = RedlineStatus.CLEAR if ok else (RedlineStatus.TRIGGERED if n in auto_d else RedlineStatus.SUSPECTED)
            out.append(RedlineFinding(n, rl.step, rl.description, st, ev))
        else:
            out.append(RedlineFinding(n, rl.step, rl.description, RedlineStatus.MANUAL_CHECK, "未知红线号，转人工"))
    return tuple(out)
