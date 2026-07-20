"""A 类确定性规则 —— 纯函数判定（design.md D1/D2）。

每条规则一个纯函数：输入 (ProposalDocument, Rule) → RuleResult。判定逻辑在代码，
元数据在注册表。本批先实现模块一字段规则（规则 1–16 中可由已解析字段判定的），
其余规则随对应模块解析逐步补齐，未实现者引擎标 PENDING（不冒判）。
"""
from __future__ import annotations

import re
from datetime import date, datetime
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
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"-?\d+(?:\.\d+)?", str(v or ""))
    return float(m.group()) if m else None


def _to_date(v):
    """归一化任意日期表示（datetime/日期序列/"YYYY.M.D"/"YYYY-MM-DD"）为 date。"""
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, (int, float)):
        try:
            from openpyxl.utils.datetime import from_excel
            return from_excel(v).date()
        except Exception:
            return None
    m = re.match(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", str(v).strip())
    if not m:
        return None
    y, mo, d = (int(x) for x in m.groups())
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def _z(v) -> float:
    """财务表求和用：缺失单元格按 0 处理（合并/裁剪行常见，非"未知"语义）。"""
    return v if v is not None else 0.0


# ---- 模块六：项目风险分析 ----
_RISK_SEVERITY = {"轻微": 1, "不太严重": 2, "较严重": 3, "严重": 4, "灾难": 5, "非常严重": 5}
_RISK_FREQ = {"很少发生": 2, "不太可能": 3, "有时发生": 4, "经常发生": 5, "频繁": 6}


def _risk_level_of(coef: float, severity_score: int | None = None) -> str:
    """风险等级：系数分档，但严重度达「非常严重/灾难」（5级）时无论系数高低恒判高风险。

    经 EQ17 黄金样本核验（风险#1：非常严重×很少发生=10，落在系数"一般"区间但评审报告
    判定高风险且无异议）——灾难级后果的风险不应因发生频率低而降档，系数分档法需叠加
    此严重度兜底，否则会对真实高风险漏判为"一般"。
    """
    if severity_score is not None and severity_score >= 5:
        return "高风险"
    if coef <= 4:
        return "低风险"
    if coef <= 14:
        return "一般风险"
    return "高风险"


@rule(35)
def r35_risk_count(doc, r):
    rows = doc.table("风险")
    if not rows:
        return _result(r, Verdict.FAIL, evidence="未识别项目风险", suggestion="必须识别项目风险，不少于3项")
    n = len(rows)
    if n >= 3:
        return _result(r, Verdict.PASS, evidence=f"识别{n}项风险")
    return _result(r, Verdict.FAIL, evidence=f"仅识别{n}项风险（需≥3项）",
                   suggestion="必须识别项目风险，不少于3项")


def _risk_item_complete(r, doc, idx):
    rows = doc.table("风险")
    if len(rows) < idx:
        return _result(r, Verdict.PENDING, evidence=f"风险项#{idx}不存在，待人工核")
    row = rows[idx - 1]
    required = ["类别", "描述", "严重度", "频率", "系数", "等级", "应对措施"]
    missing = [k for k in required if not row.get(k) and row.get(k) != 0]
    if missing:
        return _result(r, Verdict.FAIL, evidence=f"风险项#{idx}缺失字段：{missing}",
                       suggestion="逐项填写风险描述、严重度、频率、系数、等级、应对措施")
    coef = row["系数"]
    return _result(r, Verdict.PASS,
                   evidence=f"{row['类别']} | {row['严重度']}×{row['频率']}={coef:g} ({row['等级']})")


@rule(36)
def r36_risk_item_1(doc, r):
    return _risk_item_complete(r, doc, 1)


@rule(37)
def r37_risk_item_2(doc, r):
    return _risk_item_complete(r, doc, 2)


@rule(38)
def r38_risk_item_3(doc, r):
    return _risk_item_complete(r, doc, 3)


@rule(39)
def r39_risk_coefficient(doc, r):
    rows = doc.table("风险")
    if not rows:
        return _result(r, Verdict.PENDING, evidence="风险表未解析，待人工核")
    errors = []
    for row in rows:
        sev, freq, coef = (_RISK_SEVERITY.get(row["严重度"]), _RISK_FREQ.get(row["频率"]),
                            row["系数"])
        if sev is None or freq is None or coef is None:
            errors.append(f"第{row['序号']}项缺数据待人工核")
            continue
        expected = sev * freq
        if abs(expected - coef) > 1e-6:
            errors.append(f"第{row['序号']}项\"{row['描述'][:12]}\": 系数={coef:g}(应为{expected}), "
                          f"{row['严重度']}({sev})×{row['频率']}({freq})")
    if errors:
        n_ok = len(rows) - len(errors)
        return _result(r, Verdict.WARN,
                       evidence=f"{n_ok}/{len(rows)}项正确; 错误: " + "; ".join(errors),
                       suggestion="风险系数须等于严重度×发生频率")
    return _result(r, Verdict.PASS, evidence=f"全部{len(rows)}项系数计算正确(严重度×频率=系数)")


@rule(40)
def r40_risk_level_consistency(doc, r):
    rows = doc.table("风险")
    if not rows:
        return _result(r, Verdict.PENDING, evidence="风险表未解析，待人工核")
    mismatches = []
    for row in rows:
        coef, level = row["系数"], row["等级"]
        if coef is None or not level:
            mismatches.append(f"第{row['序号']}项缺数据")
            continue
        expected = _risk_level_of(coef, _RISK_SEVERITY.get(row["严重度"]))
        if expected != level:
            mismatches.append(f"第{row['序号']}项系数{coef:g}应为{expected}，实填{level}")
    if mismatches:
        return _result(r, Verdict.WARN, evidence="; ".join(mismatches),
                       suggestion="风险等级须与系数匹配：≤4为低、5-14为一般、≥15为高")
    return _result(r, Verdict.PASS, evidence=f"全部{len(rows)}项风险等级与系数一致")


@rule(41)
def r41_high_risk_mitigation(doc, r):
    rows = doc.table("风险")
    if not rows:
        return _result(r, Verdict.PENDING, evidence="风险表未解析，待人工核")
    high = [row for row in rows if (row["系数"] or 0) >= 15]
    if not high:
        return _result(r, Verdict.NA, evidence="无高风险项（系数≥15）")
    missing = [row for row in high if not row["应对措施"]]
    if missing:
        return _result(r, Verdict.FAIL,
                       evidence=f"高风险项#{[m['序号'] for m in missing]}缺应对措施",
                       suggestion="高风险项（系数≥15）必须制定应对措施")
    names = ", ".join(f"#{row['序号']}{row['描述'][:10]}" for row in high)
    return _result(r, Verdict.PASS, evidence=f"共{len(high)}项高风险均已制定应对措施({names})")


@rule(42)
def r42_mitigation_presence(doc, r):
    """C 类：应对措施有效性——只验「在否」，不判有效性（design.md 转人工4条 Requirement）。

    "有效覆盖风险"需业务/评审判断，AI 只能核实每项风险是否已填应对措施；
    全部已填 → 转人工核实有效性；有缺项 → 按 J 列严重度（重要→警告）标待改进。
    """
    rows = doc.table("风险")
    if not rows:
        return _result(r, Verdict.PENDING, evidence="风险表未解析，待人工核")
    missing = [row for row in rows if not row.get("应对措施")]
    if missing:
        return _result(r, Verdict.WARN,
                       evidence=f"{len(missing)}/{len(rows)}项风险应对措施未填：#{[m['序号'] for m in missing]}",
                       suggestion="逐项风险须填写应对措施，有效性由评审委员会人工核实")
    return _result(r, Verdict.MANUAL,
                   evidence=f"全部{len(rows)}项风险均已填写应对措施，内容有效性交评审委员会人工核实")


# ---- 模块七：项目所需资源采购计划 ----
@rule(43)
def r43_resource_count(doc, r):
    rows = doc.table("资源")
    n = len(rows)
    if n >= 2:
        return _result(r, Verdict.PASS, evidence=f"共{n}项资源")
    return _result(r, Verdict.FAIL, evidence=f"仅{n}项资源（需≥2项）", suggestion="资源条目不少于2项")


def _resource_item_complete(r, doc, idx):
    rows = doc.table("资源")
    if len(rows) < idx:
        return _result(r, Verdict.PENDING, evidence=f"资源项#{idx}不存在，待人工核")
    row = rows[idx - 1]
    missing = [k for k in ("类型", "原因", "配置", "获取方式") if not row.get(k)]
    if row.get("数量") is None:
        missing.append("数量")
    if not row.get("预算文本"):
        missing.append("预算")
    if missing:
        return _result(r, Verdict.FAIL, evidence=f"资源项#{idx}缺失字段：{missing}",
                       suggestion="逐项填写资源类型、原因、主要配置、数量、获取方式、预算")
    return _result(r, Verdict.PASS,
                   evidence=f"{row['类型']} | {row['原因']} | 数量={row['数量']:g} | "
                            f"{row['获取方式']} | 预算={row['预算文本']}")


@rule(44)
def r44_resource_item_1(doc, r):
    return _resource_item_complete(r, doc, 1)


@rule(45)
def r45_resource_item_2(doc, r):
    return _resource_item_complete(r, doc, 2)


@rule(46)
def r46_resource_budget_total(doc, r):
    rows = doc.table("资源")
    if not rows:
        return _result(r, Verdict.PENDING, evidence="资源表未解析，待人工核")
    vals = [row["预算"] for row in rows if row["预算"] is not None]
    if not vals:
        return _result(r, Verdict.FAIL, evidence="资源预算未填写", suggestion="资源预算合计需填写")
    return _result(r, Verdict.PASS, evidence=f"约{sum(vals):g}万元({len(rows)}项)")


# ---- 模块八：成本及收益分析 ----
_CB_SUM_KEYS = ["收入D", "成本E", "利润F", "数量G", "收入J", "成本K", "三包L", "利润M", "利润小计P"]


def _cb_total(doc):
    for row in doc.table("成本效益"):
        if row.get("is_total"):
            return row
    return None


def _cb_first(doc):
    for row in doc.table("成本效益"):
        if not row.get("is_total"):
            return row
    return None


def _cb_income_scale(doc) -> float:
    """成本效益表存在「元/万元」量纲不统一的真实数据问题（模板未强制标注单位）；

    用「收入依据」表（各样本均恒定标注万元）作可信锚点，反推成本效益表实际量纲：
    若收入D合计相对锚点呈 ~10000 倍，判定该表以「元」计价，换算为万元再跨表比对。
    """
    total = _cb_total(doc)
    basis = doc.table("收入依据合计")
    if not total or total.get("收入D") is None:
        return 1.0
    raw = total["收入D"]
    if not basis or not basis[0].get("合计"):
        return 10000.0 if abs(raw) > 100000 else 1.0
    trusted = basis[0]["合计"]
    ratio = raw / trusted if trusted else None
    return 10000.0 if ratio and ratio > 1000 else 1.0


@rule(47)
def r47_cb_field_completeness(doc, r):
    total = _cb_total(doc)
    if not total:
        return _result(r, Verdict.PENDING, evidence="成本效益表未解析，待人工核")
    missing = [k for k in ("收入D", "成本E", "利润F", "利润小计P") if total.get(k) is None]
    if missing:
        return _result(r, Verdict.FAIL, evidence=f"核心字段缺失：{missing}",
                       suggestion="核心字段需填写：收入D、成本E、利润F、利润小计P")
    return _result(r, Verdict.PASS, evidence="核心字段(收入D/成本E/利润F/利润小计P)已填写")


@rule(48)
def r48_cb_mass_production_data(doc, r):
    if doc.project_type != "产品类":
        return _result(r, Verdict.NA, evidence="非产品类项目, 量产数据为可选")
    rows = [row for row in doc.table("成本效益") if not row.get("is_total")]
    if not rows:
        return _result(r, Verdict.PENDING, evidence="成本效益表未解析，待人工核")
    keys = ("数量G", "单价H", "成本单价I", "收入J", "成本K")
    filled = [row for row in rows if all(row.get(k) is not None for k in keys)]
    if not filled:
        return _result(r, Verdict.FAIL, evidence="未填写量产产品数据",
                       suggestion="产品类项目必须填写量产产品数据（数量G/销售单价H/成本单价I/收入J/成本K）")
    return _result(r, Verdict.PASS, evidence=f"已填写{len(filled)}行量产产品数据")


@rule(49)
def r49_cb_first_year(doc, r):
    row = _cb_first(doc)
    if not row:
        return _result(r, Verdict.PENDING, evidence="成本效益表未解析，待人工核")
    missing = [k for k in ("收入D", "成本E", "利润F", "利润小计P") if row.get(k) is None]
    if missing:
        return _result(r, Verdict.FAIL, evidence=f"{row['年份']}缺失：{missing}",
                       suggestion="按表格逐项填写各阶段/各产品的收入D、成本E、利润F、利润小计P")
    return _result(r, Verdict.PASS,
                   evidence=f"D={row['收入D']:g}, E={row['成本E']:g}, F={row['利润F']:g}, "
                            f"P={row['利润小计P']:g}")


@rule(50)
def r50_cb_formula_accuracy(doc, r):
    rows = doc.table("成本效益")
    if not rows:
        return _result(r, Verdict.PENDING, evidence="成本效益表未解析，待人工核")
    data_rows = [row for row in rows if not row.get("is_total")]
    total_row = _cb_total(doc)
    errors = []
    for row in data_rows:
        d, e, f, m, p = (_z(row.get("收入D")), _z(row.get("成本E")), _z(row.get("利润F")),
                          _z(row.get("利润M")), _z(row.get("利润小计P")))
        if abs((d - e) - f) > 0.05:
            errors.append(f"{row['年份']}: F≠D-E({f:g}≠{d - e:g})")
        if abs((f + m) - p) > 0.05:
            errors.append(f"{row['年份']}: P≠F+M({p:g}≠{f + m:g})")
    if total_row:
        for key in _CB_SUM_KEYS:
            s = round(sum(_z(row.get(key)) for row in data_rows), 4)
            t = total_row.get(key)
            if t is not None and abs(s - t) > 0.05:
                errors.append(f"合计行{key}={t:g}≠各行累加{s:g}")
    if errors:
        return _result(r, Verdict.WARN, evidence="; ".join(errors),
                       suggestion="验证计算公式：F=D-E（效益），P=F+M（利润小计），合计行=各行累加")
    return _result(r, Verdict.PASS, evidence="所有计算公式验证通过")


@rule(51)
def r51_cb_total_row(doc, r):
    rows = doc.table("成本效益")
    data_rows = [row for row in rows if not row.get("is_total")]
    total_row = _cb_total(doc)
    if not total_row or not data_rows:
        return _result(r, Verdict.PENDING, evidence="成本效益表未解析，待人工核")
    mismatches = []
    for key in _CB_SUM_KEYS:
        s = round(sum(_z(row.get(key)) for row in data_rows), 4)
        t = total_row.get(key)
        if t is not None and abs(s - t) > 0.05:
            mismatches.append(f"{key}: 合计{t:g}≠累加{s:g}")
    if mismatches:
        return _result(r, Verdict.WARN, evidence="; ".join(mismatches),
                       suggestion="成本效益分析表合计行需与各行累加值一致")
    return _result(r, Verdict.PASS, evidence="合计与各行累加一致")


@rule(52)
def r52_revenue_basis_table(doc, r):
    rows = doc.table("收入依据")
    if not rows:
        return _result(r, Verdict.FAIL, evidence="未找到收入依据表格",
                       suggestion="必须包含项目收入依据表格，列出各阶段节点及商务标志、收款金额")
    return _result(r, Verdict.PASS, evidence=f"已找到({len(rows)}个阶段节点)")


@rule(53)
def r53_revenue_basis_flags(doc, r):
    rows = doc.table("收入依据")
    if not rows:
        return _result(r, Verdict.PENDING, evidence="收入依据表未解析，待人工核")
    missing = [row["阶段"] for row in rows if not row["商务标志"]]
    if missing:
        return _result(r, Verdict.FAIL, evidence=f"未填写商务标志：{missing}",
                       suggestion='各阶段"商务阶段标志（必选）"必须填写；填"NA"表示该阶段被裁剪')
    filled = [row for row in rows if row["商务标志"] not in ("NA", "/")]
    return _result(r, Verdict.PASS,
                   evidence=f"已填{len(filled)}个有效商务标志, 裁剪{len(rows) - len(filled)}个(NA)")


@rule(54)
def r54_revenue_basis_amount(doc, r):
    rows = doc.table("收入依据")
    if not rows:
        return _result(r, Verdict.PENDING, evidence="收入依据表未解析，待人工核")
    active = [row for row in rows if row["商务标志"] not in ("NA", "/", "")]
    missing = [row["阶段"] for row in active if row["收款金额"] is None]
    if missing:
        return _result(r, Verdict.FAIL, evidence=f"商务标志已填但收款金额未填：{missing}",
                       suggestion='商务标志填写后，"合同约定/预计收款金额"必须同步填写')
    return _result(r, Verdict.PASS,
                   evidence=f"{len(active)}个节点已填写收款金额, 裁剪{len(rows) - len(active)}个(NA)")


@rule(55)
def r55_revenue_basis_consistency(doc, r):
    total = _cb_total(doc)
    basis = doc.table("收入依据合计")
    if not total or not basis or total.get("收入D") is None:
        return _result(r, Verdict.PENDING, evidence="收入依据或成本效益表未解析，待人工核")
    scale = _cb_income_scale(doc)
    d, trusted = total["收入D"] / scale, basis[0]["合计"]
    if abs(d - trusted) > 0.5:
        return _result(r, Verdict.FAIL,
                       evidence=f"收入依据合计={trusted:g}万, 与成本效益表收入D={d:g}万不一致",
                       suggestion="收入依据合计金额需与成本效益分析表收入D一致")
    return _result(r, Verdict.PASS, evidence=f"收入依据合计={trusted:g}万, 与成本效益表收入D={d:g}万一致 ✓")


def _income_scalar(doc, key):
    return doc.fields.get(f"八、（二）收益分析说明/{key}")


def _scalar_completeness(r, doc, key, label):
    fv = _income_scalar(doc, key)
    if fv is None or fv.status == ExtractStatus.NOT_FOUND:
        return _result(r, Verdict.PENDING, evidence=f"{label}未定位，待人工核")
    if not fv.is_present:
        return _result(r, Verdict.FAIL, evidence=f"{label}未填写",
                       suggestion=f"产品类项目必须填写{label}，填NA则跳过")
    v = str(fv.value).strip()
    if v in ("NA", "/", "N/A"):
        return _result(r, Verdict.PASS, evidence="已填写，不适用(NA)")
    return _result(r, Verdict.PASS, evidence=f"已填写: {v}")


@rule(56)
def r56_scale_basis(doc, r):
    return _scalar_completeness(r, doc, "量纲预估依据", "产品量纲预估依据")


@rule(57)
def r57_price_basis(doc, r):
    return _scalar_completeness(r, doc, "售价预估依据", "产品售价预估依据")


@rule(58)
def r58_cost_basis(doc, r):
    return _scalar_completeness(r, doc, "量产成本预估依据", "产品量产成本预估依据")


@rule(59)
def r59_gross_margin(doc, r):
    fv = _income_scalar(doc, "项目本身毛利率")
    total = _cb_total(doc)
    if fv is None or fv.status == ExtractStatus.NOT_FOUND or not total:
        return _result(r, Verdict.PENDING, evidence="毛利率或成本效益表未解析，待人工核")
    v = str(fv.value).strip() if fv.is_present else ""
    if v in ("NA", "/", ""):
        return _result(r, Verdict.PASS, evidence="已填写NA，跳过")
    filled, d, f = _num_of(v), total.get("收入D"), total.get("利润F")
    if filled is None or d is None or f is None or not d:
        return _result(r, Verdict.PENDING, evidence="毛利率无法验证，待人工核")
    expected = round(f / d, 2)
    if abs(round(filled, 2) - expected) > 0.02:
        return _result(r, Verdict.FAIL, evidence=f"{filled:.2f} (验证: F/D={expected:.2f}) 不一致",
                       suggestion="毛利率=F/D（效益/收入）")
    return _result(r, Verdict.PASS, evidence=f"{expected:.2f} (验证: F/D={expected:.2f})")


@rule(60)
def r60_lifecycle_margin(doc, r):
    fv = _income_scalar(doc, "全生命周期毛利率")
    total = _cb_total(doc)
    if not total:
        return _result(r, Verdict.PENDING, evidence="成本效益表未解析，待人工核")
    v = str(fv.value).strip() if fv and fv.is_present else ""
    p, d, j = total.get("利润小计P"), total.get("收入D"), total.get("收入J")
    denom = _z(d) + _z(j)
    if v in ("NA", "/", ""):
        if doc.project_type == "产品类" and denom:
            return _result(r, Verdict.WARN, evidence="产品类项目全生命周期毛利率未填写",
                           suggestion="产品类项目必须能计算全生命周期毛利率")
        return _result(r, Verdict.NA, evidence="无量产数据, 无法计算全生命周期毛利率(填NA)")
    filled = _num_of(v)
    if filled is None or p is None or not denom:
        return _result(r, Verdict.PENDING, evidence="全生命周期毛利率无法验证，待人工核")
    expected = round(p / denom, 2)
    if abs(round(filled, 2) - expected) > 0.02:
        return _result(r, Verdict.FAIL, evidence=f"{filled:.2f} (P/(D+J)={expected:.2f}) 不一致",
                       suggestion="全生命周期毛利率=P/(D+J)")
    return _result(r, Verdict.PASS, evidence=f"{expected:.2f} (P/(D+J)={expected:.2f})")


def _income_ratio(doc):
    """收益指标 = 技术服务类 D/E；产品类 (D+M)/E。返回 (ratio, label) 或 (None, None)。"""
    total = _cb_total(doc)
    if not total:
        return None, None
    d, e, m = total.get("收入D"), total.get("成本E"), total.get("利润M")
    if d is None or not e:
        return None, None
    if doc.project_type == "产品类":
        return (d + _z(m)) / e, "产品类"
    return d / e, "技术服务类"


@rule(61)
def r61_income_ratio(doc, r):
    ratio, label = _income_ratio(doc)
    if ratio is None:
        return _result(r, Verdict.PENDING, evidence="收益指标无法验证，待人工核")
    formula = "(D+M)/E" if label == "产品类" else "D/E"
    return _result(r, Verdict.PASS, evidence=f"{ratio:.2f} (验证: {formula}={ratio:.2f})")


@rule(62)
def r62_income_ratio_threshold(doc, r):
    ratio, label = _income_ratio(doc)
    if ratio is None:
        return _result(r, Verdict.PENDING, evidence="收益指标无法验证，待人工核")
    threshold = 5.0 if label == "产品类" else 1.5
    if ratio >= threshold:
        return _result(r, Verdict.PASS, evidence=f"{label}≥{threshold:g}达标({ratio:.2f})")
    return _result(r, Verdict.WARN, evidence=f"{ratio:.2f} < {threshold:g}({label}标准未达标)",
                   suggestion=f"{label}收益指标需≥{threshold:g}")


# ---- 模块九：开发期限及预算 ----
def _budget_total(doc):
    for row in doc.table("预算表"):
        if row.get("is_total"):
            return row
    return None


@rule(65)
def r65_milestone_budget(doc, r):
    rows = [row for row in doc.table("预算表") if not row.get("is_total")]
    if not rows:
        return _result(r, Verdict.FAIL, evidence="未填写时间节点表",
                       suggestion="必须包含里程碑节点及对应预算")
    return _result(r, Verdict.PASS, evidence=f"有时间节点表({len(rows)}个节点)")


@rule(66)
def r66_last_milestone_end_date(doc, r):
    rows = [row for row in doc.table("预算表") if not row.get("is_total")]
    end_field = _info(doc, "结束日期")
    if not rows:
        return _result(r, Verdict.PENDING, evidence="时间节点表未解析，待人工核")
    if not end_field.is_present:
        return _result(r, Verdict.NA, evidence="项目结束日期未填写，无法比对")
    last = rows[-1]
    last_end, proj_end = _to_date(last.get("结束")), _to_date(end_field.value)
    if last_end is None:
        return _result(r, Verdict.PENDING, evidence=f"最后节点({last['阶段']})结束时间未解析，待人工核")
    if proj_end is None:
        return _result(r, Verdict.NA, evidence="项目结束日期格式无法解析，无法比对")
    if last_end != proj_end:
        return _result(r, Verdict.FAIL,
                       evidence=f"最后节点({last['阶段']})结束时间={last_end} 与项目结束日期{proj_end}不一致",
                       suggestion="时间节点表最后一个节点的结束时间需与项目结束日期一致")
    return _result(r, Verdict.PASS,
                   evidence=f"最后节点({last['阶段']})结束时间={last_end} 与项目结束日期一致")


@rule(67)
def r67_depreciation(doc, r):
    total = _budget_total(doc)
    if not total:
        return _result(r, Verdict.PENDING, evidence="预算表未解析，待人工核")
    dep, staff = total.get("折旧⑦"), total.get("人员成本②")
    if dep is None or staff is None:
        return _result(r, Verdict.FAIL, evidence="折旧摊销&福利费未填写",
                       suggestion="折旧摊销&福利费⑦（=②×15%）无论项目类型均需填写")
    expected = round(staff * 0.15, 3)
    if abs(dep - expected) > 0.02:
        return _result(r, Verdict.FAIL,
                       evidence=f"已填写={dep:.3f}万，不符合②×15%={expected:.3f}万",
                       suggestion="折旧摊销&福利费⑦须等于②×15%")
    return _result(r, Verdict.PASS, evidence=f"已填写={dep:.3f}万，符合②×15%={expected:.3f}万")


@rule(68)
def r68_manmonth_consistency(doc, r):
    total = _budget_total(doc)
    budget = _num_of(_info(doc, "预算总工时").value)
    if not total or budget is None or total.get("人月") is None:
        return _result(r, Verdict.PENDING, evidence="预算总工时或节点表缺数，待人工核")
    if abs(total["人月"] - budget) < 0.05:
        return _result(r, Verdict.PASS,
                       evidence=f"一致: 预算总工时{budget:g}人月 = 节点表合计{total['人月']:g}人月")
    return _result(r, Verdict.FAIL,
                   evidence=f"不一致: 预算总工时{budget:g} vs 节点表合计{total['人月']:g}",
                   suggestion="时间节点表合计人月数需与预算总工时一致")


@rule(69)
def r69_budget_cashflow_vs_profit(doc, r):
    """现金流合计（⑪-⑩）须与成本效益利润F一致。

    经 EQ17/邦奇真实黄金基准核验：无论产品类/技术服务类，比对基准均为「利润F」，
    不含全生命周期量产利润M（模块九/十只覆盖开发期现金流，量产利润在开发周期外实现）——
    与工作汇总.xlsx pass_condition 文本「产品类=F+M」的字面表述不符，
    此处以两份评审报告(v5.0)的实际判定口径为准（评审报告为权威黄金基准，非文本推测）。
    """
    total, cb_total = _budget_total(doc), _cb_total(doc)
    if not total or not cb_total or total.get("现金流") is None or cb_total.get("利润F") is None:
        return _result(r, Verdict.PENDING, evidence="预算表或成本效益表缺数，待人工核")
    scale = _cb_income_scale(doc)
    profit, cashflow = cb_total["利润F"] / scale, total["现金流"]
    if abs(cashflow - profit) > 0.5:
        return _result(r, Verdict.FAIL,
                       evidence=f"现金流合计={cashflow:.2f}万 ≠ 成本效益利润F={profit:.2f}万，"
                                f"相差{abs(cashflow - profit):.2f}万",
                       suggestion="现金流合计（⑪-⑩）须与成本效益利润F一致")
    return _result(r, Verdict.PASS,
                   evidence=f"现金流合计={cashflow:.2f}万，与成本效益利润F={profit:.2f}万一致")


# ---- 模块十：项目现金流分析 ----
_CF_TO_BUDGET = {
    "收入": "收入⑪", "人力": "人员成本②", "设备": "设备③", "委外": "委外④",
    "材料": "材料⑤", "差旅": "差旅⑥", "折旧摊销": "折旧⑦", "其他": "其他⑧", "售后": "售后⑨",
}


@rule(70)
def r70_cashflow_table_presence(doc, r):
    rows = doc.table("现金流表")
    if not rows:
        return _result(r, Verdict.FAIL, evidence="未填写项目现金流分析表",
                       suggestion="必须填写项目现金流分析表，含月净现金流和累计现金流列")
    return _result(r, Verdict.PASS, evidence=f"已填写{len(rows)}个月份的现金流数据")


@rule(71)
def r71_cashflow_coverage(doc, r):
    rows = doc.table("现金流表")
    if not rows:
        return _result(r, Verdict.PENDING, evidence="现金流表未解析，待人工核")
    start, end = _info(doc, "开始日期"), _info(doc, "结束日期")
    d_start = _to_date(start.value) if start.is_present else None
    d_end = _to_date(end.value) if end.is_present else None
    if not d_start or not d_end:
        return _result(r, Verdict.PASS, evidence=f"已填写{len(rows)}期（项目日期未填无法计算应填月数）")
    expected = (d_end.year - d_start.year) * 12 + (d_end.month - d_start.month) + 1
    if len(rows) >= expected:
        return _result(r, Verdict.PASS, evidence=f"项目周期{expected}个月，已填写{len(rows)}期，覆盖完整")
    return _result(r, Verdict.WARN,
                   evidence=f"项目周期{expected}个月，仅填写{len(rows)}期，覆盖不完整",
                   suggestion="现金流必须覆盖项目全周期，从立项开始到结项结束的每个月")


@rule(72)
def r72_monthly_net_cashflow(doc, r):
    rows = doc.table("现金流表")
    if not rows:
        return _result(r, Verdict.PENDING, evidence="现金流表未解析，待人工核")
    errors = []
    for row in rows:
        income = _z(row.get("收入"))
        expense = sum(_z(row.get(k)) for k in
                      ("人力", "设备", "委外", "材料", "差旅", "折旧摊销", "其他", "售后"))
        expected = round(income - expense, 4)
        actual = row.get("月净现金流")
        if actual is None or abs(actual - expected) > 0.02:
            errors.append(f"{row['月份']}: 实填{actual} ≠ 应为{expected:.2f}")
    if errors:
        return _result(r, Verdict.WARN, evidence="; ".join(errors),
                       suggestion="每月净现金流=收入-（人力+设备+委外+材料+差旅+折旧摊销+其他+售后）")
    return _result(r, Verdict.PASS, evidence=f"全部{len(rows)}行月净现金流计算正确")


@rule(73)
def r73_cashflow_vs_budget(doc, r):
    rows = doc.table("现金流表")
    budget_total = _budget_total(doc)
    if not rows or not budget_total:
        return _result(r, Verdict.PENDING, evidence="现金流表或预算表缺数，待人工核")
    mismatches = []
    for cf_key, bud_key in _CF_TO_BUDGET.items():
        s = round(sum(_z(row.get(cf_key)) for row in rows), 2)
        t = budget_total.get(bud_key)
        if t is not None and abs(s - t) > 0.5:
            mismatches.append(f"{cf_key}: 现金流汇总{s:g} ≠ 预算{t:g}")
    if mismatches:
        return _result(r, Verdict.WARN, evidence="; ".join(mismatches),
                       suggestion="现金流各列逐项汇总需与模块九立项预算基准一致")
    return _result(r, Verdict.PASS, evidence="收入/各支出项汇总均与模块九预算基准一致")


@rule(74)
def r74_final_cashflow_vs_profit(doc, r):
    """累计现金流末期须与成本效益利润F一致（同 rule69 注：比对基准恒为F，含产品类）。"""
    rows, cb_total = doc.table("现金流表"), _cb_total(doc)
    if not rows or not cb_total or cb_total.get("利润F") is None:
        return _result(r, Verdict.PENDING, evidence="现金流表或成本效益表缺数，待人工核")
    last = rows[-1].get("累计现金流")
    if last is None:
        return _result(r, Verdict.PENDING, evidence="累计现金流末期未解析，待人工核")
    scale = _cb_income_scale(doc)
    profit = cb_total["利润F"] / scale
    if abs(last - profit) > 0.5:
        return _result(r, Verdict.FAIL,
                       evidence=f"累计现金流末期={last:.2f}万 != 成本效益利润F={profit:.2f}万，"
                                f"相差{abs(last - profit):.2f}万",
                       suggestion="现金流最终累计值需与成本效益分析利润一致")
    return _result(r, Verdict.PASS,
                   evidence=f"累计现金流末期={last:.2f}万，与成本效益利润F={profit:.2f}万一致")


# ---- 模块十二/十三：C 类转人工 4 条中的 3 条（第 4 条见上 rule 42）----
# design.md「转人工 4 条只验在否不下结论」Requirement：签字/决议真伪与有效性交人工，
# AI 只核实字段「在/不在、已填/未填」。真实签名是图章/手写图片，openpyxl 读不到像素，
# 以签字行下方日期是否已填作「在场」代理指标（parser._parse_summary_signatures）。
def _summary(doc, name):
    return doc.get(f"十二、总结/{name}")


@rule(80)
def r80_pm_signature(doc, r):
    fv = _summary(doc, "项目经理签字及日期")
    if fv.status == ExtractStatus.NOT_FOUND:
        return _result(r, Verdict.PENDING, evidence="解析未命中该字段（待人工核）")
    if fv.is_present:
        return _result(r, Verdict.MANUAL, evidence=f"已签字并填写日期: {fv.value!r}（真伪人工核）")
    return _result(r, Verdict.FAIL, evidence="项目经理未签字/未填日期",
                   suggestion="请项目经理签字并填写日期")


@rule(81)
def r81_gm_signature(doc, r):
    fv = _summary(doc, "总经理签字及日期")
    if fv.status == ExtractStatus.NOT_FOUND:
        return _result(r, Verdict.PENDING, evidence="解析未命中该字段（待人工核）")
    if fv.is_present:
        return _result(r, Verdict.MANUAL, evidence=f"已签字并填写日期: {fv.value!r}（真伪人工核）")
    return _result(r, Verdict.FAIL, evidence="事业部总经理未签字/未填日期",
                   suggestion="请事业部总经理签字并填写日期")


@rule(82)
def r82_decision(doc, r):
    """立项决议在立项会评审后填写，申请阶段不做判断（design.md 场景「立项决议申请阶段不判」）。"""
    return _result(r, Verdict.NA, evidence="立项决议在立项会评审后填写，申请阶段不做评价")
