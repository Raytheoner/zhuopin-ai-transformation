"""A 类确定性规则 —— 纯函数判定（design.md D1/D2）。

每条规则一个纯函数：输入 (ProposalDocument, Rule) → RuleResult。判定逻辑在代码，
元数据在注册表。本批先实现模块一字段规则（规则 1–16 中可由已解析字段判定的），
其余规则随对应模块解析逐步补齐，未实现者引擎标 PENDING（不冒判）。
"""
from __future__ import annotations

from datetime import date
from typing import Callable

from ..models import ExtractStatus, ProposalDocument, RuleResult, Verdict
from .registry import Rule

# rule_id -> 判定函数
_RULES: dict[str, Callable[[ProposalDocument, Rule], RuleResult]] = {}


def rule(rule_id: str):
    def deco(fn):
        _RULES[str(rule_id)] = fn
        return fn
    return deco


def implemented_ids() -> set[str]:
    return set(_RULES)


def _info(doc: ProposalDocument, name: str):
    return doc.get(f"一、项目信息/{name}")


def _result(r: Rule, verdict: Verdict, evidence: str = "", suggestion: str = "") -> RuleResult:
    return RuleResult(
        rule_id=r.rule_id, check_item=r.check_item, verdict=verdict,
        severity_level=r.severity_level if verdict in (Verdict.FAIL, Verdict.WARN) else "",
        evidence=evidence, suggestion=suggestion, impl_class=r.impl_class,
    )


def _required(doc, r, name, allow_slash=True, suggest=None) -> RuleResult:
    """通用必填项判定：present→PASS；空→FAIL。allow_slash 时 '/'/'NA' 视为已填。"""
    fv = _info(doc, name)
    if fv.status == ExtractStatus.NOT_FOUND:
        return _result(r, Verdict.PENDING, evidence="解析未命中该字段（待人工核）")
    if fv.is_present:
        return _result(r, Verdict.PASS, evidence=f"已填写: {fv.value!r}")
    return _result(r, Verdict.FAIL, evidence="必填项为空",
                   suggestion=suggest or f"请填写「{r.check_item}」")


# ---- 模块一：完整性必填 ----
@rule(1)
def r1_project_name(doc, r):
    return _required(doc, r, "项目名称")


@rule(2)
def r2_project_order(doc, r):
    # 项目令：系统自动生成，不做判断
    return _result(r, Verdict.NA, evidence="系统自动生成，不做判断")


@rule(3)
def r3_cts_sor(doc, r):
    return _required(doc, r, "客户CTS/SOR版本号")     # 可填 '/'/'NA'


@rule(4)
def r4_project_code(doc, r):
    # 产品类必填；技术服务类不适用
    if doc.project_type == "技术服务类":
        return _result(r, Verdict.NA, evidence="技术服务类项目无需项目代号")
    return _required(doc, r, "项目代号", suggest="产品类项目须填项目代号")


@rule(5)
def r5_pm(doc, r):
    return _required(doc, r, "项目经理")


@rule(6)
def r6_platform(doc, r):
    return _required(doc, r, "目标车型/车辆平台")


@rule(7)
def r7_customer(doc, r):
    return _required(doc, r, "客户名称")


@rule(8)
def r8_division(doc, r):
    return _required(doc, r, "项目所属事业部")


@rule(9)
def r9_sop(doc, r):
    return _required(doc, r, "SOP目标年份/项目结项时间")


@rule(10)
def r10_start_date(doc, r):
    fv = _info(doc, "开始日期")
    if fv.is_present:
        return _result(r, Verdict.PASS, evidence=f"已填写: {fv.value}")
    return _result(r, Verdict.FAIL, evidence="开始日期未填写", suggestion="请填写项目开始日期")


@rule(11)
def r11_end_date(doc, r):
    """结束日期必填，且需晚于开始日期。"""
    end = _info(doc, "结束日期")
    start = _info(doc, "开始日期")
    if not end.is_present:
        return _result(r, Verdict.FAIL, evidence="结束日期未填写",
                       suggestion="请填写项目结束日期（须晚于开始日期）")
    d_end, d_start = _parse_iso(end.value), _parse_iso(start.value)
    if d_end and d_start and d_end <= d_start:
        return _result(r, Verdict.FAIL,
                       evidence=f"结束日期 {end.value} ≤ 开始日期 {start.value}",
                       suggestion="结束日期须晚于开始日期")
    return _result(r, Verdict.PASS, evidence=f"已填写: {end.value}")


@rule(12)
def r12_asil(doc, r):
    """ASIL ∈ {A,B,C,D,不涉及}；'/'/'NA'/'不适用' 视为不涉及。"""
    fv = _info(doc, "功能安全目标ASIL")
    if not fv.is_present:
        return _result(r, Verdict.FAIL, evidence="未勾选 ASIL 等级或填写不涉及")
    v = str(fv.value).strip()
    if v in {"A", "B", "C", "D"} or v in {"/", "NA", "N/A", "不涉及", "不适用"}:
        return _result(r, Verdict.PASS, evidence=f"已填写: {v}")
    return _result(r, Verdict.WARN, evidence=f"ASIL 取值非常规: {v!r}",
                   suggestion="应为 A/B/C/D 或不涉及")


@rule(13)
def r13_budget_hours(doc, r):
    return _required(doc, r, "预算总工时", suggest="请填写项目预算总工时（人月/人年）")


def _sum_personnel(doc) -> float | None:
    rows = doc.table("人员安排")
    vals = [x["人月"] for x in rows if x.get("人月") is not None]
    return round(sum(vals), 4) if vals else None


def _personnel_total(doc):
    t = doc.table("人员安排合计")
    return t[0]["合计人月"] if t and t[0].get("合计人月") is not None else None


@rule(14)
def r14_budget_hours_consistency(doc, r):
    """人员安排合计人月 需与预算总工时一致。"""
    total = _personnel_total(doc)
    budget = _num_of(_info(doc, "预算总工时").value)
    if total is None or budget is None:
        return _result(r, Verdict.PENDING, evidence="预算总工时或人员合计缺数，待人工核")
    if abs(total - budget) < 0.05:
        return _result(r, Verdict.PASS, evidence=f"一致：预算 {budget} 人月 = 人员合计 {total} 人月")
    return _result(r, Verdict.FAIL, evidence=f"不一致：预算 {budget} vs 人员合计 {total}",
                   suggestion="人员安排合计人月须与预算总工时一致")


@rule(18)
def r18_personnel_rows_sum(doc, r):
    """各角色人力投入合计 需与合计行一致。"""
    s = _sum_personnel(doc)
    total = _personnel_total(doc)
    if s is None or total is None:
        return _result(r, Verdict.PENDING, evidence="人员安排表缺数，待人工核")
    if abs(s - total) < 0.05:
        return _result(r, Verdict.PASS, evidence=f"各行合计 {s} = 合计行 {total} 人月")
    return _result(r, Verdict.FAIL, evidence=f"各行合计 {s} ≠ 合计行 {total}",
                   suggestion="人员安排各行人力投入之和须等于合计")


def _textlen(doc, module) -> int:
    fv = doc.text_areas.get(module)
    return len(str(fv.value)) if fv and fv.is_present else 0


@rule(19)
def r19_basis_wordcount(doc, r):
    """立项依据 ≥50 字。"""
    n = _textlen(doc, "二、立项依据")
    if n == 0:
        return _result(r, Verdict.FAIL, evidence="立项依据未填写")
    if n >= 50:
        return _result(r, Verdict.PASS, evidence=f"已填写（{n}字）")
    return _result(r, Verdict.WARN, evidence=f"字数偏少（{n}字 < 50）",
                   suggestion="立项依据需说明产品是什么/什么用途，不少于50字")


@rule(22)
def r22_purpose_wordcount(doc, r):
    """项目目的与意义 ≥50 字。"""
    n = _textlen(doc, "三、项目的目的和意义")
    if n == 0:
        return _result(r, Verdict.FAIL, evidence="项目目的与意义未填写")
    if n >= 50:
        return _result(r, Verdict.PASS, evidence=f"已填写（{n}字）")
    return _result(r, Verdict.WARN, evidence=f"字数偏少（{n}字 < 50）",
                   suggestion="项目目的与意义不少于50字")


@rule(16)
def r16_project_type(doc, r):
    fv = _info(doc, "项目类型")
    if fv.is_present and str(fv.value).strip() in {"产品类", "技术服务类"}:
        return _result(r, Verdict.PASS, evidence=f"已填写: {fv.value}")
    if fv.is_present:
        return _result(r, Verdict.FAIL, evidence=f"项目类型取值非法: {fv.value!r}",
                       suggestion="须为 产品类 或 技术服务类")
    return _result(r, Verdict.FAIL, evidence="未选择项目类型")


def _parse_iso(s):
    try:
        y, m, d = str(s).split("-")
        return date(int(y), int(m), int(d))
    except Exception:
        return None


def _num_of(v):
    """从字段值取首个数值（如预算总工时「4人月/0.33人年」→ 4.0）。"""
    import re
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"-?\d+(?:\.\d+)?", str(v or ""))
    return float(m.group()) if m else None
