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
