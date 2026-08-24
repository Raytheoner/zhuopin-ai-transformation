"""C01–C10 跨模块一致性校验（变更包 qd-b-cross-module-check 档一＋档二
＋ qd-b-cross-module-tier3 档三）。

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

🔴 **档三（C05/C06/C07）已于 2026-08-25 落地**（队列 #340③，陈忱 2026-08-21 答齐 Q1–Q4）。
三条**同样走 `cross_module_items`、同样不计入总分**——这一点与 2026-08-18 归档件里
"C05/C06/C07 的阻断效力待口径裁定时一并落到规则侧"那句预期**不同**，是本次的显式改判：
EQ17 的 C05 实测判「错误」（3 条风险里程碑对不上），而 EQ17 是评审委员会判**合格**的那一份，
把它接进扣分即当场把合格项目打成不合格。⇒ 档三仍只作**呈现**，阻断与否留待陈忱另行裁定。
论证见 `openspec/changes/qd-b-cross-module-tier3/design.md` 决策 4。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ..models import ExtractStatus, ProposalDocument, RuleResult, Verdict
from .deterministic import (
    _cb_income_scale,
    _cb_total,
    _info,
    _num_of,
    _personnel_total,
    _to_date,
)
from .vocab import is_as_not_filled, is_na_synonym

IMPL_CLASS = "Cross"

#: C05 两份表的落盘位置（陈忱 Q1 两条护栏的载体，与 registry.json 同目录便于他一并查看）。
C05_TABLE_PATH = Path(__file__).resolve().parents[2] / "data" / "rules" / "cross_module_c05.json"

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

#: 档三落地后已无挂起项。**保留这个空表不是冗余**——`implemented_ids()`／`status_label()`／
#: `summarize()` 三处的"已实现 vs 口径未定"分流都读它，日后若再有条目挂起，填这里即可，
#: 不必改那三处逻辑；而清空它就是"三条已落地"这件事在代码里唯一的开关。
_BLOCKED_REASONS: dict[str, str] = {}


def check_meta(check_id: str) -> CrossCheck | None:
    """按编号取 §三 元数据（供报告呈现层引用原文规则与偏差处理，不复制文案）。"""
    return _BY_ID.get(check_id)


def implemented_ids() -> set[str]:
    """已实现判定逻辑的校验编号。档三落地后＝全部 10 条（`_BLOCKED_REASONS` 已空）。"""
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


# ---------- C05：风险「所属里程碑」↔ 模块九阶段（陈忱 2026-08-21 Q1） ----------

@lru_cache(maxsize=1)
def _c05_tables() -> tuple[frozenset[str], dict[str, tuple[str, ...]], bool]:
    """读 `data/rules/cross_module_c05.json` → (豁免词集, 映射表, 是否已确认)。

    表缺失时**返回空表而不是抛异常**：空表意味着豁免与白名单都不生效，C05 退化为
    "严格相等 ＋ 包含匹配"，判得比口径更严 —— 宁可多报几条错误让人来看，也不要因为
    读不到表就静默放行。⚠️ 反过来说，**这条兜底本身会让 EQ17 的 C05 结论变化**，
    故读不到表时在证据里明写，不当作正常路径。
    """
    try:
        raw = json.loads(C05_TABLE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return frozenset(), {}, False
    exempt = frozenset(_norm_ms(w) for w in raw.get("贯穿性豁免词", {}).get("词表", []))
    mapping = {
        _norm_ms(k): tuple(v)
        for k, v in raw.get("里程碑阶段映射表", {}).get("映射", {}).items()
    }
    confirmed = bool(raw.get("_已确认", False))
    return exempt, mapping, confirmed


def _norm_ms(s) -> str:
    """里程碑/阶段名规范化：去空白与全角空格。**不做同义改写**——那是映射表的职责。"""
    return str(s or "").replace("　", "").replace(" ", "").strip()


def _fuzzy_candidate(value: str, stages: list[str]) -> str:
    """2-gram 词重叠最高的阶段名（**仅用于把"相似度指向了谁"写进证据**，不作判定依据）。

    🔴 这个函数的返回值**永远不能单独让一条 C05 通过** —— 陈忱对第 8 条判 ❌ 的正是
    "`软硬件开发设计` 仅因共有「设计」二字被配到 `G1质量阀/概念设计`"这种自信的错映射。
    保留它是为了让报告能说清"我看见了这个相似，但按白名单不予采信"，而不是假装没看见。
    """
    def grams(s: str) -> set[str]:
        return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 1 else {s}

    v = grams(value)
    best, best_score = "", 0.0
    for st in stages:
        g = grams(_norm_ms(st))
        if not g or not v:
            continue
        sc = len(v & g) / len(v | g)
        if sc > best_score:
            best, best_score = st, sc
    return best if best_score > 0 else ""


def _match_one_milestone(raw_value: str, stages: list[str]) -> tuple[str, str]:
    """单条风险的里程碑匹配 → (结论, 说明)。结论 ∈ {通过, 豁免, 漏填, 错误}。

    判定次序与 `cross_module_c05.json::_判定次序` 逐条对应（那份 JSON 是给陈忱看的正本）。
    """
    exempt, mapping, _ = _c05_tables()
    v = _norm_ms(raw_value)
    if not v:
        return "漏填", "「所属里程碑」为空"

    # ⑴ 护栏一：非阶段值／贯穿性描述豁免（EQ17「全项目周期」＝他 ❌ 掉「错误」的那一条）
    if v in exempt:
        return "豁免", f"「{raw_value}」属贯穿性描述、非阶段值，按豁免词表不参与匹配"

    norm_stages = {_norm_ms(s): s for s in stages}
    if v in norm_stages:
        return "通过", f"「{raw_value}」与阶段「{norm_stages[v]}」严格相等"

    for ns, orig in norm_stages.items():
        if v in ns or ns in v:
            return "通过", f"「{raw_value}」与阶段「{orig}」互为子串"

    # ⑵ 护栏二：白名单校验——只有映射表确认过的对应才算数
    for target in mapping.get(v, ()):
        nt = _norm_ms(target)
        for ns, orig in norm_stages.items():
            if nt == ns or nt in ns:
                return "通过", f"「{raw_value}」经映射表确认对应阶段「{orig}」"
        return "错误", (f"「{raw_value}」映射表指向「{target}」，但模块九未填该阶段"
                        f"（已填：{'／'.join(stages)}）")

    cand = _fuzzy_candidate(v, stages)
    if cand:
        return "错误", (f"「{raw_value}」在模块九已填阶段中不存在；字符相似度指向「{cand}」，"
                        f"但映射表未确认此对应，按白名单校验不予采信")
    return "错误", f"「{raw_value}」在模块九已填阶段中不存在（已填：{'／'.join(stages)}）"


def _c05(doc, check, results_by_id) -> RuleResult:
    """模块六风险「所属里程碑」必须在模块九已填阶段中存在；不存在 → 错误。

    口径＝陈忱 2026-08-21 Q1：总口径选 (c) 模糊匹配，**但附两条强制护栏**——豁免词表
    与里程碑-阶段映射表白名单。⇒ 实际落地形态是「(c)＋两条护栏」，**超出原信 (a)–(d) 选项集**，
    两份表的内容仍待他确认（见 `cross_module_c05.json::_确认状态`）。
    """
    stages = [row["阶段"] for row in _stage_rows(doc) if _norm_ms(row.get("阶段"))]
    risks = doc.table("风险")
    _, _, confirmed = _c05_tables()
    tail = "" if confirmed else "｜⚠ 判定用的豁免词表与里程碑-阶段映射表为按 Q1 反推的草拟版，待陈忱确认"

    if not stages:
        return _item(check, Verdict.PENDING,
                     evidence="缺数，待人工核：模块九未解析到已填阶段，无从比对" + tail)
    if not risks:
        return _item(check, Verdict.NA,
                     evidence="模块六无风险行，本条不适用" + tail)

    verdicts = [(row, *_match_one_milestone(row.get("所属里程碑", ""), stages)) for row in risks]
    bad = [(r, why) for r, res, why in verdicts if res == "错误"]
    lack = [(r, why) for r, res, why in verdicts if res == "漏填"]
    exempted = [(r, why) for r, res, why in verdicts if res == "豁免"]
    ok = [r for r, res, _ in verdicts if res == "通过"]

    def _label(row) -> str:
        return f"风险{row.get('序号', '?')}(r{row.get('行号', '?')})"

    parts = [f"{len(risks)} 条风险：通过 {len(ok)}"]
    if exempted:
        parts.append(f"豁免 {len(exempted)}")
    if lack:
        parts.append(f"漏填 {len(lack)}")
    if bad:
        parts.append(f"对不上 {len(bad)}")
    head = "、".join(parts)
    detail = "；".join(f"{_label(r)} {why}" for r, why in bad + lack + exempted)

    if bad:
        return _item(check, Verdict.FAIL, severity="错误",
                     evidence=f"{head}——{detail}{tail}",
                     suggestion="风险「所属里程碑」应填模块九已列出的阶段名；"
                                "若确为贯穿全程的风险，请填「全项目周期」一类贯穿性描述")
    if lack:
        return _item(check, Verdict.FAIL, severity="错误",
                     evidence=f"{head}——{detail}{tail}",
                     suggestion="请补填风险的「所属里程碑」")
    return _item(check, Verdict.PASS, evidence=f"{head}"
                 + (f"——{detail}" if detail else "") + tail)


# ---------- C06/C07：模块四目标存在性（陈忱 2026-08-21 Q2/Q3/Q4） ----------

def _module4_goal(doc, label_prefix: str) -> tuple[str, str | None]:
    """取模块四某类目标的「详细指标」→ (状态, 原值)。状态 ∈ {未解析, 无此行, 已取}。

    🔴 **「未解析」与「没填」必须分开**（场景红线：解析未命中 ≠ 业务空）——前者转人工，
    后者才是业务缺陷。C07 的华丰案例就是这一族被压平后判反的实例。
    """
    rows = doc.table("项目目标")
    if not rows:
        return "未解析", None
    for row in rows:
        if str(row.get("目标类型", "")).startswith(label_prefix):
            return "已取", row.get("详细指标")
    return "无此行", None


def _goal_verdict(doc, check: CrossCheck, label_prefix: str, trigger_note: str) -> RuleResult:
    state, detail = _module4_goal(doc, label_prefix)
    if state == "未解析":
        return _item(check, Verdict.MANUAL,
                     evidence=f"转人工核：{trigger_note}，但模块四「四、项目目标」未解析到目标行，"
                              f"无法判定是否已填「{label_prefix}」——解析未命中不等于业务未填，不冒判")
    if state == "无此行":
        return _item(check, Verdict.MANUAL,
                     evidence=f"转人工核：{trigger_note}，但模块四目标表中未见「{label_prefix}」行"
                              f"（该行属模板固定标签，缺失更像模板改版而非填报缺陷）")
    if is_as_not_filled(detail):
        shown = f"填「{str(detail).strip()}」" if str(detail or "").strip() else "为空"
        return _item(check, Verdict.FAIL, severity="错误",
                     evidence=f"{trigger_note}，但模块四「{label_prefix}」{shown}"
                              f"——按陈忱 2026-08-21 Q3 选 (b)，该组写法视为没填",
                     suggestion=f"请在模块四补填「{label_prefix}」的详细指标")
    excerpt = str(detail).strip().replace("\n", " ")[:40]
    return _item(check, Verdict.PASS,
                 evidence=f"{trigger_note}，模块四「{label_prefix}」已填：{excerpt}…")


def _c06(doc, check, results_by_id) -> RuleResult:
    """模块一「功能安全目标ASIL」非 NA 时，模块四必须有「功能安全目标」；缺失 → 错误。

    同义词集走 `vocab.ASIL_NA_SYNONYMS`（陈忱 Q2 封闭词表，与规则 12 同一份）。
    🔴 **空单元格判「漏填」、不视同 NA**（Q2 后半句）——但"漏填"这件事的扣分归规则 12，
    本条只能说"因此判不了"，转人工，不替他把空悄悄归成 NA 从而静默跳过整条校验。

    **ISO 26262 红线**：本条只做「模块四是否存在功能安全目标」的存在性校验，
    **不对安全内容本身作任何判定**，故自身不越 ASIL C/D 禁区；文档一旦出现 ASIL=C/D
    仍按现行红线整体转功能安全工程师，本条不改变它。
    """
    fv = _info(doc, "功能安全目标ASIL")
    if fv.status == ExtractStatus.NOT_FOUND:
        return _item(check, Verdict.MANUAL,
                     evidence="转人工核：模块一「功能安全目标ASIL」字段未解析到，"
                              "无法判定本条是否适用（解析未命中 ≠ 业务未填）")
    if not fv.is_present:
        return _item(check, Verdict.MANUAL,
                     evidence="转人工核：模块一 ASIL 为空——按陈忱 2026-08-21 Q2，"
                              "空单元格判「漏填」而非视同 NA，故无从判定本条是否适用；"
                              "该字段本身的扣分由规则 12 承担")
    v = str(fv.value).strip()
    if is_na_synonym(v):
        return _item(check, Verdict.NA,
                     evidence=f"模块一 ASIL＝「{v}」，按 Q2 封闭同义词表视同 NA，本条不适用")
    return _goal_verdict(doc, check, "功能安全目标", f"模块一 ASIL＝「{v}」非 NA")


def _c07(doc, check, results_by_id) -> RuleResult:
    """模块一「适用法规」勾选 ISO21434 时，模块四必须有「信息安全目标」；缺失 → 错误。

    🔴 **取数读不出勾选 → 转人工核**（陈忱 Q4 选 (b)，他并注明「这条和我们红线原则一致」）。
    华丰实证：其第 8 行 `N8` 整格缺失，解析器按「True/False 后跟选项文本」成对扫描时
    **ISO21434 这个选项直接从表里消失**——`checked_options` 返回的不是「没勾」而是
    「这个选项不存在」，两件事被压成同一个结果。按字面实现会静默判「不适用」跳过，
    而真相是根本没读出来（「工具静默回退」同族：返回值完全正常，结论却是反的）。
    """
    options = doc.checkboxes.get("适用法规/体系")
    if not options:
        return _item(check, Verdict.MANUAL,
                     evidence="转人工核：模块一「适用法规/体系」勾选行未解析到任何选项，"
                              "读不出 ISO21434 的勾选状态")
    present = [(name, ck) for name, ck in options if "21434" in _norm_ms(name)]
    if not present:
        listed = "／".join(name for name, _ in options) or "（空）"
        return _item(check, Verdict.MANUAL,
                     evidence=f"转人工核：模块一适用法规选项表里**没有 ISO21434 这一项**"
                              f"（实际读到：{listed}）——这是「读不出勾选状态」，"
                              f"不是「未勾选」，按陈忱 2026-08-21 Q4 选 (b) 不作判定",
                     suggestion="请核对该行复选格是否缺失或改用了非标准打勾方式（如手打「√」）")
    if not any(ck for _, ck in present):
        return _item(check, Verdict.NA,
                     evidence="模块一未勾选 ISO21434，本条不适用")
    return _goal_verdict(doc, check, "信息安全目标", "模块一已勾选 ISO21434")


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


_IMPLS = {"C01": _c01, "C02": _c02, "C03": _c03, "C04": _c04, "C05": _c05,
          "C06": _c06, "C07": _c07, "C08": _c08}


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


def status_label(item: RuleResult) -> str:
    """跨模块段专用状态标签（三处呈现载体共用）。

    通用 `STATUS_LABELS` 把 PENDING 一律显示为"未实现"，但本段的 PENDING 有两种来历：
    **判定口径未定、逻辑确实没写**（C05/C06/C07）与 **逻辑已写、这份文件缺数比不了**
    （如华丰的 C04：起半边一致、止半边因项目结束日期未填无从比对）。
    把后者也标成"未实现"，正是本变更包要消灭的"把已核的说成没核"，只是尺度更小。
    """
    from ..report_items import STATUS_LABELS  # noqa: PLC0415 —— 避免与展示层循环导入

    if item.verdict != Verdict.PENDING:
        return STATUS_LABELS.get(item.verdict, item.verdict.value)
    return "待人工核" if item.rule_id in implemented_ids() else "未实现"


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

    # ⚠️ MANUAL 必须在册：档三落地后 C06/C07 的"读不出来→转人工"是常态结论，
    # 漏掉它会让抬头的计数与下表条数对不上（华丰即 1 条 MANUAL）。
    counts = {v: sum(1 for i in judged if i.verdict == v)
              for v in (Verdict.PASS, Verdict.WARN, Verdict.FAIL,
                        Verdict.NA, Verdict.MANUAL)}
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
