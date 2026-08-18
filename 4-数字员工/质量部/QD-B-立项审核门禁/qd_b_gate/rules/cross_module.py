"""C01–C10 跨模块一致性校验（openspec 变更包 qd-b-cross-module-check，档一＋档二）。

判据单一可信源＝工作汇总.xlsx「规则说明（开发）」§三 跨模块一致性校验规则（第 213–224 行），
原文逐条落在 `CROSS_CHECKS` 的 `rule_text` / `deviation` 两列，代码不另立口径。

三条设计约束（design.md 决策 1/2/3，改动前先读那份）：

1. **不并进 `results`**——本模块产出走 `GateReport.cross_module_items` 独立列表。
   `scoring.py::score()` 只遍历 `registry.rules`（82 条），C01–C10 不在注册表内，
   故只要不并进 `results`，总分与档位**在数学上不可能变**（"零分数漂移可证"的全部依据）。
2. **C09/C10 不重算**——公式与规则 59/60 逐字相同，改为查表复用其判定结果；
   重算等于同一判据两份实现，日后改一处漏一处，正是 IATF「单一可信源」要防的形态。
3. **等价规则并列标注**——「立项门禁」82 条表判"精确相等＋重要级扣分"，
   而 §三 判"10% 容差＋警告"（Q1 冲突，待陈忱裁定）。本模块按 §三 判，
   但对等价条目同时标注该规则的判定结果，使两套口径的差异**在报告上可见**，
   不静默取一边。扣分仍只由 82 条规则决定，故并列呈现不产生二义性后果。

未实现的 C05/C06/C07 判 PENDING 并各写**具体**阻塞原因——本变更包要修的正是
"一句笼统文案把已核的说成没核"，换成另一句笼统的"扩容期补齐"只是把谎话换成含糊话。
"""
from __future__ import annotations

from dataclasses import dataclass

from ..models import ProposalDocument, RuleResult, Verdict
from .deterministic import (
    _cb_income_scale,
    _cb_total,
    _info,
    _num_of,
    _personnel_total,
    _to_date,
)

IMPL_CLASS = "Cross"

#: §三 数值偏差类的容差（相对偏差 >10% → 警告）
NUMERIC_TOLERANCE = 0.10


@dataclass(frozen=True)
class CrossCheck:
    """一条跨模块校验的元数据（§三 原文照录，不改写）。"""
    check_id: str          # C01…C10
    name: str              # 校验内容
    rule_text: str         # §三「规则」列原文
    deviation: str         # §三「偏差处理」列原文
    equivalent: str = ""   # 等价/近等价的既有 82 条规则编号（Q1 冲突可见性）


CROSS_CHECKS: tuple[CrossCheck, ...] = (
    CrossCheck("C01", "人员一致性",
               '模块一人员安排"合计"人月数 ≈ 模块九各阶段"人月数①"之和',
               "偏差 > 10% → 警告", equivalent="14+68"),
    CrossCheck("C02", "开发成本一致性",
               '模块八"项目开发本身"成本合计 ≈ 模块九"小计⑩"合计',
               "偏差 > 10% → 警告"),
    CrossCheck("C03", "收入一致性",
               '模块八"项目收入依据"合计金额 ≈ 模块九"项目收入预算估计⑪"合计',
               "偏差 > 10% → 警告"),
    CrossCheck("C04", "时间一致性",
               '模块一"开始日期"/"结束日期" = 模块九首阶段开始/末阶段结束',
               "不一致 → 警告", equivalent="66"),
    CrossCheck("C05", "风险与里程碑对应",
               '模块六风险"所属里程碑"必须在模块九已填写的阶段中存在',
               "不存在 → 错误"),
    CrossCheck("C06", "ASIL与功能安全",
               '模块一"功能安全目标ASIL"非"NA"时，模块四必须有"功能安全目标"',
               "缺失 → 错误"),
    CrossCheck("C07", "ISO21434与信息安全",
               '模块一"适用法规"勾选ISO21434时，模块四必须有"信息安全目标"',
               "缺失 → 错误"),
    CrossCheck("C08", "预算工时与里程碑",
               '模块一"预算总工时" ≈ 模块九各阶段"人月数①"之和',
               "偏差 > 10% → 警告", equivalent="68"),
    CrossCheck("C09", "收益计算自洽",
               '模块八"项目本身毛利率" = 模块八利润F / 收入D（如D>0）',
               "计算不匹配 → 错误", equivalent="59"),
    CrossCheck("C10", "全生命周期毛利率",
               '模块八"全生命周期毛利率" = P / (D+J)（如D+J>0）',
               "计算不匹配 → 错误", equivalent="60"),
)

_BY_ID = {c.check_id: c for c in CROSS_CHECKS}

#: 档三三条的**具体**阻塞原因（不是"扩容期补齐"）——见 proposal.md「What Changes · 档三」。
_BLOCKED_REASONS: dict[str, str] = {
    "C05": "口径未定，暂不实现：风险表「所属里程碑」与模块九阶段名不是一套词汇体系"
           "（样本实测填的是「需求确认与资料交付」「软硬件开发设计」，模块九是「立项评审」"
           "「G1–G4质量阀」「结项评审」，严格相等与包含匹配均 0 命中）；"
           "按 §三 字面实现会把评审报告判合格的样本判成阻断错误。待质量部裁定匹配口径（Q2）。",
    "C06": "口径未定 ＋ 解析缺口，暂不实现：① ASIL「不适用」的写法在样本中出现 `/`、`无`、`A` 三种，"
           "需先定同义词表（若把「无」当作 ≠NA，模块四填「不涉及」的样本会从合格翻成不合格，Q3）；"
           "② 模块四「四、项目目标」当前完全未解析，需新增三列表解析。",
    "C07": "解析缺口，暂不实现：判据本身无歧义（模块一勾选 ISO21434 → 模块四须有信息安全目标），"
           "但模块四「四、项目目标」当前完全未解析，需与 C06 同批新增三列表解析。",
}


def check_meta(check_id: str) -> CrossCheck | None:
    """按编号取 §三 元数据（供报告呈现层引用原文规则与偏差处理，不复制文案）。"""
    return _BY_ID.get(check_id)


def implemented_ids() -> set[str]:
    """已实现判定逻辑的校验编号（C05/C06/C07 不在其中）。"""
    return {c.check_id for c in CROSS_CHECKS} - set(_BLOCKED_REASONS)


def _item(check: CrossCheck, verdict: Verdict, evidence: str,
          suggestion: str = "", severity: str = "") -> RuleResult:
    return RuleResult(
        rule_id=check.check_id,
        check_item=check.name,
        verdict=verdict,
        severity_level=severity if verdict in (Verdict.FAIL, Verdict.WARN) else "",
        evidence=evidence,
        suggestion=suggestion,
        impl_class=IMPL_CLASS,
    )


def _equivalence_note(check: CrossCheck, results_by_id: dict[str, RuleResult]) -> str:
    """等价规则的判定结果并列标注（Q1 两套口径可见，design 决策 3）。"""
    if not check.equivalent:
        return ""
    parts = []
    for rid in check.equivalent.split("+"):
        r = results_by_id.get(rid)
        parts.append(f"规则{rid}={r.verdict.value}" if r else f"规则{rid}=本次未判定")
    return "｜等价既有规则：" + "、".join(parts)


# ---------- 数值偏差类通用比对（C01/C02/C03/C08） ----------

def _compare_numeric(check: CrossCheck, left: float | None, right: float | None,
                     left_label: str, right_label: str, unit: str,
                     note: str = "") -> RuleResult:
    """§三 数值偏差类：相对偏差 > 10% → 警告。

    **偏差的分母取左侧（模块一/模块八的声明值）**——§三 每条都写成
    "模块一/模块八 X ≈ 模块九 Y"，左侧是被核对的声明值，右侧是明细表的重算值，
    故按"相对声明值的偏差"计。左侧为 0 时退回两侧较大者，避免除零。
    ⚠️ §三 原文只写"偏差 > 10%"、**未规定分母**——#340 评估件那支一次性探针取的是
    右侧为分母，同一份邦奇样本因此报 54.7%（本实现报 35.4%，绝对差同为 46.662 万、
    判定同为警告）。分母口径已随 Q1 一并列为待陈忱裁定项，此处先取左侧并写明，不静默择一。

    任一侧缺数判 PENDING 并写明缺哪一侧——**不按 0 处理**：按 0 会把"没填"变成
    "偏差 100%"，是把解析问题伪装成业务问题（场景红线：解析未命中 ≠ 业务空）。
    """
    missing = [lbl for lbl, v in ((left_label, left), (right_label, right)) if v is None]
    if missing:
        return _item(check, Verdict.PENDING,
                     evidence=f"缺数，待人工核：{'、'.join(missing)} 未取到值" + note)

    diff = round(abs(left - right), 6)   # 浮点求和噪声（如 1.78e-15）不当作真实差异展示
    base = abs(left) or max(abs(left), abs(right))
    ratio = diff / base if base else 0.0
    shown = (f"{left_label}={left:g}{unit} ↔ {right_label}={right:g}{unit}"
             f"，差 {diff:g}{unit}（相对{left_label} {ratio:.1%}）")
    if ratio > NUMERIC_TOLERANCE:
        return _item(check, Verdict.WARN, evidence=f"不一致：{shown}" + note,
                     suggestion=f"{check.rule_text}（{check.deviation}）", severity="警告")
    return _item(check, Verdict.PASS, evidence=f"一致：{shown}" + note)


def _stage_rows(doc: ProposalDocument) -> list[dict]:
    """模块九预算表的各阶段行（剔除合计行）。

    §三 原文比对的是"各阶段人月数①之和"，故按各行求和而非取合计行；
    合计行与各行之和是否自洽属规则 18/68 的辖区，本段不重复判。
    """
    return [row for row in doc.table("预算表") if not row.get("is_total")]


def _stage_sum(doc: ProposalDocument, key: str) -> float | None:
    rows = _stage_rows(doc)
    vals = [row[key] for row in rows if row.get(key) is not None]
    return round(sum(vals), 4) if vals else None


# ---------- 逐条实现 ----------

def _c01(doc, check, results_by_id) -> RuleResult:
    return _compare_numeric(
        check, _personnel_total(doc), _stage_sum(doc, "人月"),
        "模块一人员安排合计", "模块九各阶段人月之和", "人月",
        note=_equivalence_note(check, results_by_id),
    )


def _c08(doc, check, results_by_id) -> RuleResult:
    return _compare_numeric(
        check, _num_of(_info(doc, "预算总工时").value), _stage_sum(doc, "人月"),
        "模块一预算总工时", "模块九各阶段人月之和", "人月",
        note=_equivalence_note(check, results_by_id),
    )


def _c02(doc, check, results_by_id) -> RuleResult:
    """成本 E ↔ 小计⑩之和。成本效益表存在元/万元不统一，须过 scale 换算（design 决策 6.1）。"""
    total = _cb_total(doc)
    cost_e = total.get("成本E") if total else None
    if cost_e is not None:
        cost_e = cost_e / _cb_income_scale(doc)
    return _compare_numeric(
        check, cost_e, _stage_sum(doc, "小计⑩"),
        "模块八成本E", "模块九小计⑩之和", "万",
    )


def _c03(doc, check, results_by_id) -> RuleResult:
    """收入依据合计 ↔ 收入⑪之和。收入依据表各样本恒定标注万元，无需换算。"""
    basis = doc.table("收入依据合计")
    left = basis[0].get("合计") if basis else None
    return _compare_numeric(
        check, left, _stage_sum(doc, "收入⑪"),
        "模块八收入依据合计", "模块九收入⑪之和", "万",
    )


def _c04(doc, check, results_by_id) -> RuleResult:
    """模块一起止日期 ↔ 首阶段开始/末阶段结束。

    §三 判"不一致 → 警告"；"止"半边已由规则 66（阻断级）覆盖并计入扣分，本段不重复否决
    （design 决策 5）。

    **起/止两半各自独立判**：华丰实测「起一致、止因项目结束日期未填而无从比对」——
    整条判 PENDING 会把已经核过的"起"半边也说成没核（本变更包要治的正是这个形态），
    故逐半边给结论，整条取"任一半不一致→警告；否则有半边缺数→PENDING（写明哪半已核）"。
    """
    rows = _stage_rows(doc)
    note = _equivalence_note(check, results_by_id)
    if not rows:
        return _item(check, Verdict.PENDING,
                     evidence="缺数，待人工核：模块九时间节点表未解析" + note)

    halves = (
        ("开始日期", _to_date(_info(doc, "开始日期").value),
         f"首阶段（{rows[0]['阶段']}）开始", _to_date(rows[0].get("开始"))),
        ("结束日期", _to_date(_info(doc, "结束日期").value),
         f"末阶段（{rows[-1]['阶段']}）结束", _to_date(rows[-1].get("结束"))),
    )

    mismatched, matched, unknown = [], [], []
    for name, left_val, right_name, right_val in halves:
        if left_val is None or right_val is None:
            lack = "模块一" + name if left_val is None else right_name
            unknown.append(f"{name}：缺数（{lack} 未取到有效日期）")
        elif left_val != right_val:
            mismatched.append(f"{name}：模块一={left_val} ↔ {right_name}={right_val}")
        else:
            matched.append(f"{name}：模块一={left_val} ↔ {right_name}={right_val} 一致")

    if mismatched:
        body = "不一致：" + "；".join(mismatched)
        if matched or unknown:
            body += "｜其余：" + "；".join(matched + unknown)
        return _item(check, Verdict.WARN, evidence=body + note,
                     suggestion=f"{check.rule_text}（{check.deviation}）", severity="警告")
    if unknown:
        return _item(check, Verdict.PENDING,
                     evidence="部分未能比对——" + "；".join(matched + unknown) + note)
    return _item(check, Verdict.PASS, evidence="一致：" + "；".join(matched) + note)


def _reuse(check: CrossCheck, results_by_id: dict[str, RuleResult]) -> RuleResult:
    """C09/C10：复用规则 59/60 已产出的判定，不重算同一公式（design 决策 2）。"""
    src = results_by_id.get(check.equivalent)
    if src is None:
        return _item(check, Verdict.PENDING,
                     evidence=f"未实现：规则{check.equivalent}未在本次判定结果中，无可复用的判定"
                              f"（本条公式与规则{check.equivalent}逐字相同，按单一可信源不另行重算）")
    return _item(check, src.verdict,
                 evidence=f"复用规则{check.equivalent}判定：{src.evidence}",
                 suggestion=src.suggestion, severity=src.severity_level)


def _blocked(check: CrossCheck) -> RuleResult:
    return _item(check, Verdict.PENDING, evidence=_BLOCKED_REASONS[check.check_id])


_IMPLS = {"C01": _c01, "C02": _c02, "C03": _c03, "C04": _c04, "C08": _c08}


def build_cross_module_items(
    doc: ProposalDocument,
    results: list[RuleResult] | None = None,
) -> list[RuleResult]:
    """产出 C01–C10 十条跨模块校验条目（顺序固定为 C01→C10）。

    Args:
        doc: 已解析的立项书。
        results: 本次 82 条规则的判定结果——**只读**，用于 C09/C10 复用与等价规则标注；
                 本函数不修改它，产出也不并入其中（design 决策 1）。
    """
    by_id = {r.rule_id: r for r in (results or [])}
    items: list[RuleResult] = []
    for check in CROSS_CHECKS:
        if check.check_id in _BLOCKED_REASONS:
            items.append(_blocked(check))
        elif check.check_id in ("C09", "C10"):
            items.append(_reuse(check, by_id))
        else:
            items.append(_IMPLS[check.check_id](doc, check, by_id))
    return items


def summarize(items: list[RuleResult]) -> str:
    """④段抬头一句：实现进度 ＋ 各判定计数（供三处呈现载体共用）。

    🔑 **"判定逻辑未实现" 与 "已实现但本次缺数" 必须分开数**——按 `implemented_ids()`
    切分，而不是按"本次是否 PENDING"。否则 C04 这类"逻辑已实现、只是这份样本没填结束日期"
    的条目会被计进"未实现"，正是本变更包要消灭的那种"把已核的说成没核"，只是尺度更小。
    """
    impl_ids = implemented_ids()
    implemented = [i for i in items if i.rule_id in impl_ids]
    judged = [i for i in implemented if i.verdict != Verdict.PENDING]
    lacking = len(implemented) - len(judged)

    counts = {v: sum(1 for i in judged if i.verdict == v)
              for v in (Verdict.PASS, Verdict.WARN, Verdict.FAIL, Verdict.NA)}
    tail = "、".join(f"{v.value} {n} 条" for v, n in counts.items() if n)
    body = f"C01–C10 共 {len(items)} 条，判定逻辑已实现 {len(implemented)} 条"
    if tail:
        body += f"（本次{tail}）"
    if lacking:
        body += f"，其中 {lacking} 条因本份文件缺数未能比对"
    not_impl = len(items) - len(implemented)
    if not_impl:
        body += f"；判定口径待定、暂未实现 {not_impl} 条（逐条注明原因，见下表）"
    return body + "。本段不计入总分与一票否决，扣分仅由「立项门禁」82 条规则决定。"
