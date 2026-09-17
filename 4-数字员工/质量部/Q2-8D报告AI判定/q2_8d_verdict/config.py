"""Q2 配置 —— 档位正本指针 ＋ 已签认覆盖层（criteria_signoff） ＋ 待签认注册表 ＋ 常量。

🔴 **档位不得自定（队列 §一 #612 ⑴）**：51 条规则、6 条红线、四档分级带的**唯一来源**＝陈忱 V3.2
（`data/rules/8D评审规则库V3.2-结构化清单.json`，为 `1-转型规划/0-全景路线图/8D评审规则库V3.2-结构化清单-2026-08-28.json`
的搬运件，sha256 见 `RULES_JSON_SHA256`，用例守两份一致）。`1-转型规划/8D报告AI评审规则库.md` 是**判例签认台账、
不是档位来源**（2026-09-02 已降格）。

V3.2 之上有两层**已签认**的覆盖（她 2026-09-01 `质量部#11` 回件逐字答复 M1–M18／P1–P3，与 2026-09-14 `质量部#14`
回件签认判例 7–11）——她末句原文「以上全部判断均为判据类，已逐条确认。请按此修改 V3.2 并推进开发」。
**改后的 V3.3 尚不存在**，故本包把这些修改以 `Criterion.signed(...)` 逐条登记为覆盖层（`CRITERIA`），
引擎从注册表取值、**不在任何引擎文件里写死数字**。

🔴 仍未签认、且**本包不代填**的项，登记在 `PENDING`（读取即抛）：
  · `MEASURE_VERIFIABILITY_STANDARD` —— 判例台账 §3 开放点 1「措施可验证性的判定标准」（什么算「包含可量化的
    验证标准」），至今未单独发问。它同时是 M11／M13 补判条件的落点；签认前 `D5-03`／`D5-M1` 停在语义层待人工。
  · `SEMANTIC_LAYER_ACCEPTANCE` —— 语义类 24 条规则 ＋ 语义红线的上线放行（V1–V5 口径 2026-09-02 已认可，
    但验收集校准**尚未跑**）。签认前语义层没有自动判定实现，一律输出「待人工」。

🔴 **自动化等级恒 L2**（AI 评审并输出评分报告，质量工程师最终确认；陈忱 2026-08-25 亲勾）：所有「退回」「归档」
措辞一律是**建议**（M3 ③），退回决定由质量工程师签发，引擎不执行任何流程动作。
"""
from __future__ import annotations

import os

from zhuopin_platform.criteria_signoff import CriteriaRegistry, Criterion, Signoff

# ── 数据源开关（档 1 只有 mock；qda 接 QD-A 抽取层但 fail-loud 标置信度，见 feed_source）──
DATA_SOURCE_DEFAULT = os.environ.get("Q2_DATA_SOURCE", "mock").strip().lower()

AUTOMATION_LEVEL = "L2"
SCENARIO = "Q2"

# ── 规则版本 ──
RULE_VERSION = "q2-v3.2-chenchen-2026-08-28+signoff-2026-09-14"
RULES_JSON_RELPATH = "data/rules/8D评审规则库V3.2-结构化清单.json"
RULES_JSON_SHA256 = "7907d78415e5fc4d16cfca6ee7c8b762b3567c28ae17af944d87a8cf70bb863b"
RULES_JSON_CANON_RELPATH = "1-转型规划/0-全景路线图/8D评审规则库V3.2-结构化清单-2026-08-28.json"

# 签认落档凭据（docx 原件在 `7-外部文档/质量部/`，该目录不入库、主 checkout 存证；转写件入库可 grep）
_EV_0901 = (
    "质量部#11 回件（陈忱 2026-09-01 08:54:57Z 到件），逐条签认原文见队列 §一 #451（归档 202609）；"
    "问题原文＝1-转型规划/0-全景路线图/8D评审规则库V3.2-可行性评估与修改清单-2026-08-28.md"
)
_EV_0914 = (
    "7-外部文档/质量部/质量部-ChenChen-回复-质量部#14-2026-09-14-…-bc204082a30dcac73ce953e577dc5e83.docx"
    "（落档 2026-09-14T06:25:32Z）；转写＝1-转型规划/8D报告AI评审规则库.md §1 判例 7–11 ＋ "
    "4-数字员工/质量部/QD-A-8D不良分析/Q2-8D验收集-标签与退回理由-2026-09-17.md"
)
_EV_0825 = "质量部#9 回件 docx（陈忱 2026-08-25 w14:checkbox ☒）；转写＝1-转型规划/8D报告AI评审规则库.md §1 判例 1/3/4/5/6"
_EV_0828 = "7-外部文档/质量部/质量部-ChenChen-回复-2026-08-28-文本反馈-5035641b5511c3afad927a6635cd7bc7.md（判例 2）"


def _s(evidence: str, signed_on: str) -> Signoff:
    return Signoff(signed_by="陈忱", signed_on=signed_on, evidence=evidence, rule_version=RULE_VERSION)


# 场景标签（编制人填、AI 不猜；J7）
SCENE_MFG = "制造"
SCENE_RND = "研发"
SCENE_GENERAL = "通用"

# 四档分级字面（V3.2 grade_bands 的 grade 字段前缀）
GRADE_A, GRADE_B, GRADE_C, GRADE_D = "A", "B", "C", "D"

# 判定方式分流（#612 ⑵）：含「语义」「LLM」字样 ⇒ 语义层，本批不自动判
SEMANTIC_MARKERS = ("语义", "LLM")

# ── 🔴 已签认覆盖层（唯一声明处；引擎不得另写数字）──
CRITERIA = CriteriaRegistry(SCENARIO, [
    Criterion(
        key="TIER_STRUCTURE",
        question="三档（红线／扣分／建议）还算不算数",
        owner="质量部（陈忱）",
    ).signed({"tiers": ("红线", "扣分"), "basis": "V3.2"}, _s(_EV_0901, "2026-09-01")),
    Criterion(
        key="M1_FMEA_PER_V32",
        question="D7-02 FMEA 更新与红线⑥ 与判例 1 冲突时以哪份为准",
        owner="质量部（陈忱）",
        note="判例 1（建议项）作废，按 V3.2 扣分＋红线执行",
    ).signed({"d7_02_active": True, "redline_6_active": True}, _s(_EV_0901, "2026-09-01")),
    Criterion(
        key="M2_REDLINE2_ANY_MISPLACEMENT",
        question="红线②是否扩为「任意章节内容错位」",
        owner="质量部（陈忱）",
        note="语义类，适用 P1 转人工",
    ).signed(True, _s(_EV_0901, "2026-09-01")),
    Criterion(
        key="M3_SAFETY_ROUTING",
        question="安全相关件是否不走自动退回、处置措辞是否加「建议」",
        owner="质量部（陈忱）",
    ).signed({"safety_manual_only": True, "advice_wording": True, "asil_cd_excluded": True}, _s(_EV_0901, "2026-09-01")),
    Criterion(
        key="M4_D3_SUBFIELD_DEDUCTION",
        question="D3 子字段缺失按个数递增扣分：步长、封顶",
        owner="质量部（陈忱）",
        note="子字段全集＝客户端＋供应商端各自：区域／数量／措施／结果／负责人／计划日／完成日／状态（07-22 拆分）",
    ).signed({"step": 1.0, "cap": 8.0, "merge_d3_03": True}, _s(_EV_0901, "2026-09-01")),
    Criterion(
        key="M5_GRADE_BANDS",
        question="等级区间改左闭右开",
        owner="质量部（陈忱）",
    ).signed(((GRADE_A, 90.0), (GRADE_B, 75.0), (GRADE_C, 60.0), (GRADE_D, 0.0)), _s(_EV_0901, "2026-09-01")),
    Criterion(
        key="M6_DEDUCT_CAP_PER_RULE",
        question="单条扣分是否封顶该条满分（D2-R2 0.5 分写扣 1 分）",
        owner="质量部（陈忱）",
    ).signed(True, _s(_EV_0901, "2026-09-01")),
    Criterion(
        key="M10_DEDUP_GENERIC_ONLY",
        question="6 组通用/场景特有重复计分如何二选一",
        owner="质量部（陈忱）",
        note="她答「逐组二选一」；本包按评估件推荐 (a)＝通用条只判场景无关判据，场景差异下沉到场景特有条（design D3，🟡 Shao Peishen 审）",
    ).signed("a", _s(_EV_0901, "2026-09-01")),
    Criterion(
        key="M14_D7_KEYWORD_THRESHOLD",
        question="D7-01／D7-02 命中几个关键词算过",
        owner="质量部（陈忱）",
    ).signed({"d7_01_min_hits": 1, "d7_02_min_hits": 1, "d7_02_requires_update_semantic": True}, _s(_EV_0901, "2026-09-01")),
    Criterion(
        key="M15_SCORING_GENERAL_RULE",
        question="「不得分」与「扣 N 分」总则",
        owner="质量部（陈忱）",
    ).signed({"default": "all_or_nothing", "deduction_capped_at_rule_score": True, "total_floor": 0.0}, _s(_EV_0901, "2026-09-01")),
    Criterion(
        key="M16_D7_03_NO_EXPANSION_DEDUCT",
        question="D7-03 无横向展开扣几分",
        owner="质量部（陈忱）",
    ).signed(4.0, _s(_EV_0901, "2026-09-01")),
    Criterion(
        key="M18_DOWNGRADE_TO_KEYWORD",
        question="哪几条由 LLM 语义降级为关键词／规则引擎",
        owner="质量部（陈忱）",
        note="她认可 4 条、具体由我方按附件清单落改：D7-M3／D2-R3／D6-R1 → 关键词；红线③ → 规则引擎（但判例 11 定本批不验收）",
    ).signed({"D7-M3": "关键词", "D2-R3": "关键词", "D6-R1": "关键词", "REDLINE_3": "规则引擎"}, _s(_EV_0901, "2026-09-01")),
    Criterion(
        key="P1_SEMANTIC_REDLINE_MANUAL",
        question="语义类红线是否只输出「疑似触发·转人工裁决」不自动判 D",
        owner="质量部（陈忱）",
        note="她明示同意「宁可漏报不可误报」；确定性红线④可自动判 D",
    ).signed({"semantic_redlines_manual": True, "auto_d_redlines": (4, 6)}, _s(_EV_0901, "2026-09-01")),
    Criterion(
        key="P2_EXTRACTION_MISS_NOT_EMPTY",
        question="「解析未命中」是否不得当「真为空」触发红线",
        owner="质量部（陈忱）",
    ).signed({"trigger_only_when": "HIGH_confidence_and_empty", "else": "转人工核"}, _s(_EV_0901, "2026-09-01")),
    Criterion(
        key="P3_NO_D0_ICA_IN_D3",
        question="D0 装什么、遏制动作写在哪",
        owner="质量部（陈忱）",
    ).signed({"has_d0": False, "ica_section": "D3"}, _s(_EV_0901, "2026-09-01")),
    Criterion(
        key="SCENE_LABEL_SOURCE",
        question="一份 8D 走制造还是研发场景由谁定",
        owner="质量部（陈忱）",
        note="09-01 答「引擎推断为主、人工选为辅」；09-14 J7 改为模板 D2 页勾选行由编制人显式勾选、AI 按勾选取值，未勾选按制造评并标「场景未标注」——以 09-14 为准",
    ).signed({"source": "编制人勾选", "default_when_missing": SCENE_MFG, "flag_when_missing": "场景未标注"}, _s(_EV_0914, "2026-09-14")),
    Criterion(
        key="J2_D0_D8_EXEMPT",
        question="D0／D8 两章是否整体豁免",
        owner="质量部（陈忱）",
    ).signed(("D0", "D8"), _s(_EV_0828, "2026-08-28")),
    Criterion(
        key="J5_DEFECT_CATEGORY_NOT_SCORED",
        question="不良分类是否参与百分制评分",
        owner="质量部（陈忱）",
    ).signed(False, _s(_EV_0825, "2026-08-25")),
    Criterion(
        key="J6_SAFETY_MANUAL_ROUTE",
        question="安全相关件是否不走自动退回",
        owner="质量部（陈忱）",
    ).signed(True, _s(_EV_0825, "2026-08-25")),
    Criterion(
        key="J7_D7_FILLED_N_IS_UNFIXED",
        question="D7 固化表填 N／留空是否视同未固化",
        owner="质量部（陈忱）",
    ).signed(True, _s(_EV_0914, "2026-09-14")),
    Criterion(
        key="J8_REDLINE1_D4_ONLY",
        question="红线①是否只评 D4 表述层级、D5 到位不豁免",
        owner="质量部（陈忱）",
    ).signed(True, _s(_EV_0914, "2026-09-14")),
    Criterion(
        key="J9_STRUCTURAL_RETURN_SECTIONS",
        question="哪些 D 段整段为空即结构性退回、且先于红线语义判定",
        owner="质量部（陈忱）",
    ).signed(("D3", "D4", "D5", "D6", "D7"), _s(_EV_0914, "2026-09-14")),
    Criterion(
        key="J10_TEMPLATE_MAPPING",
        question="七步法／客户模板如何映射到 D 段",
        owner="质量部（陈忱）",
        note="七步法 一→D2、二→D4初步、三→D3、四→D4、五→D5、六→D6、七→D7；客户模板 D6 无对应不扣分、不触红线",
    ).signed(
        {"七步法": {"一": "D2", "二": "D4", "三": "D3", "四": "D4", "五": "D5", "六": "D6", "七": "D7"},
         "客户模板缺D6不扣分": True},
        _s(_EV_0914, "2026-09-14"),
    ),
    Criterion(
        key="J11_REDLINES_2_3_NOT_ACCEPTED_THIS_BATCH",
        question="红线②③本批是否验收",
        owner="质量部（陈忱）",
        note="反例为 0，暂按 P1 全部转人工；校准指标须排除这两条",
    ).signed((2, 3), _s(_EV_0914, "2026-09-14")),
])
CRITERIA.assert_rule_version(RULE_VERSION)

# ── 🔴 待签认注册表（本包不代填；读取即抛）──
PENDING = CriteriaRegistry(SCENARIO, [
    Criterion(
        key="MEASURE_VERIFIABILITY_STANDARD",
        question="什么算「包含可量化的验证标准」（D5-03／D5-M1／D6-02 的可判条件：正反例）",
        owner="质量部（陈忱）",
        note="判例台账 §3 开放点 1，未单独发问；M11–M13 她答「各补可判条件」但条件本身未随回件给出",
    ),
    Criterion(
        key="SEMANTIC_LAYER_ACCEPTANCE",
        question="语义层（24 条语义规则＋红线①②③⑤）按 V1–V5 校准通过、可上线自动判的签认",
        owner="质量部（陈忱）＋ Shao Peishen",
        note="V1–V5 口径 2026-09-02 已认可；验收集 10 份已到但校准未跑；签认前语义层一律输出待人工",
    ),
])
PENDING_VERSION = "q2-pending-unsigned-2026-09-17"
PENDING.assert_rule_version(PENDING_VERSION)


def audit_decision(payload: dict) -> dict:
    """审计 `decision` 恒带规则版本与自动化等级（criteria_signoff G-5 反向依赖）。"""
    return {"rule_version": RULE_VERSION, "automation_level": AUTOMATION_LEVEL, **payload}
