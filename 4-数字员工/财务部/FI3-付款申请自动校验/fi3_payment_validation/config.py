"""FI3 配置 —— 数据源开关 ＋ 规则版本 ＋ **已签认判据注册表（R1–R8）** ＋ 待签认注册表。

与 FI5/FI6/FI8/FI9/FI10 五个骨架包的不同之处（也是本场景能直接到档 1 的原因）：
FI3 的业务判据 **R1–R8 已由财务总监唐燕萍 2026-07-10 三步法圈改定稿**（R1 暂估价统一口径
2026-07-14 回件再确认），`1-转型规划/FI3-付款校验-就绪清单与MVP细化.md` §二 明写
「R1-R8 至此零开放项、全部闭环（2026-07-19 核实）」。⇒ 本文件把 R1–R8 **逐条以 `Signoff`
实名落档**登记进底座 `criteria_signoff`，引擎读 `CRITERIA.value_of(...)` 取值，**不在任何
引擎文件里写死数字**。

🔴 仍未签认、且**本包不代填**的两项，单独登记在 `PENDING` 注册表（读取即抛）：
  · `PREPAY_AGEING_WARN_DAYS` —— R1 只说「账龄/催票＝预警」，未给天数；引擎只出账龄度量、不判预警。
  · `L4_PROMOTION_COSIGN`     —— R8 的 L3→L4 晋级须 **Shao Peishen ＋ CFO 会签**；会签落档前
    `AUTOMATION_LEVEL` 恒为 `L3`（本模块常量 ＋ 用例守），任何拦截结论都只是「建议」。

🔴 **AI 不碰钱**：本场景全部子场景只输出校验结果与拦截建议，付款指令的发起与执行永远由人在
U9C／银企系统完成（就绪清单 §三 第一条）。这一条不是判据、不进注册表，是不可配置的红线。
"""
from __future__ import annotations

import os
from typing import Any

from zhuopin_platform.criteria_signoff import CriteriaRegistry, Criterion, Signoff

# ── 数据源开关（档 1 只有 mock；u9c 一律 fail-loud，见 feed_source）──
DATA_SOURCE_DEFAULT = os.environ.get("FI3_DATA_SOURCE", "mock").strip().lower()

# ── 自动化等级：L3 旁路校验清单（拦截落点定乙方案，唐燕萍 2026-07-10 圈定）──
# 🔴 升 L4 的唯一通道 ＝ `PENDING.value_of("L4_PROMOTION_COSIGN")`，未签认即抛。
AUTOMATION_LEVEL = "L3"

# ── 规则版本 ──
RULE_VERSION = "fi3-v1-tangyanping-2026-07-10"

# 签认落档凭据（R6 纪律只认文件）。docx 原件在 `7-外部文档/财务部/`（该目录不入库、主 checkout 存证），
# md 转写件在 `1-转型规划/`（入库，可 grep）。
_EVIDENCE = (
    "7-外部文档/财务部/FI3-付款校验-就绪清单与MVP细化-回复.docx（唐燕萍 2026-07-10 圈改）；"
    "1-转型规划/FI3-付款校验-就绪清单与MVP细化.md §二"
)
_EVIDENCE_R1 = (
    _EVIDENCE + "；暂估价按 R4 统一＝财务部-tangyanping-回复-2026-07-14-…-回复-*.docx（原文「按R4统一全文即可」）"
)


def _signoff(evidence: str = _EVIDENCE, signed_on: str = "2026-07-10") -> Signoff:
    return Signoff(signed_by="唐燕萍", signed_on=signed_on, evidence=evidence, rule_version=RULE_VERSION)


# 校验结果的三个「非通过」等级（R1 分级用词，引擎与仪表盘共用同一套字面）。
LEVEL_BLOCK = "拦截"
LEVEL_REMIND = "提醒"
LEVEL_WARN = "预警"
LEVEL_PASS = "通过"

# ── 🔴 已签认判据注册表 R1–R8（**唯一**声明处；引擎不得另写数字）──
CRITERIA = CriteriaRegistry("FI3", [
    Criterion(
        key="R1_SEVERITY_MAP",
        question="哪些校验命中＝拦截、哪些＝提醒确认、哪些＝预警",
        owner="财务侧（唐燕萍）",
        note="暂估价三处矛盾已按 R4 统一（30%=预警／50%=拦截），07-14 回件原文确认",
    ).signed(
        {
            "account_mismatch": LEVEL_BLOCK,          # 账户三字段不一致
            "over_contract_cap": LEVEL_BLOCK,         # 累计超合同
            "over_invoice_total": LEVEL_BLOCK,        # 累计超发票额
            "prepay_no_support": LEVEL_BLOCK,         # 无单据预付
            "three_way_unmatched": LEVEL_BLOCK,       # 三单未配齐
            "new_account_first_use": LEVEL_REMIND,    # 新账户首用
            "suspected_duplicate": LEVEL_REMIND,      # 疑似重复
            "prepay_unwrittenoff": LEVEL_REMIND,      # 存在未核销预付款、本次应扣回
            "provisional_warn": LEVEL_WARN,           # 暂估价 30% 线
            "provisional_block": LEVEL_BLOCK,         # 暂估价 50% 线
            "prepay_ageing": LEVEL_WARN,              # 账龄/催票（天数未签认，见 PENDING）
            "due_date_unresolved": LEVEL_REMIND,      # 账期条款解析不出／锚点日期缺失
        },
        _signoff(_EVIDENCE_R1, "2026-07-14"),
    ),
    Criterion(
        key="R2_ACCOUNT_RULES",
        question="收款账户比对哪几个字段、账户变更如何管控、新账户首用谁确认",
        owner="财务侧（唐燕萍）",
    ).signed(
        {
            "fields": ("account_name", "bank_account", "bank_name"),   # 户名／账号／开户行
            "any_mismatch_blocks": True,
            "change_parallel_days": 30,           # 变更生效前 30 天新旧并行
            "first_use_confirmer": "财务主管",    # 新账户首用须财务主管确认
        },
        _signoff(),
    ),
    Criterion(
        key="R3_DUPLICATE_PARAMS",
        question="疑似重复付款如何判、回溯多久、发票级累计如何算",
        owner="财务侧（唐燕萍）",
    ).signed(
        {
            "same_supplier_same_amount_days": 3,   # 同供应商＋同金额＋±3 天＝疑似
            "lookback_months": 12,
            "invoice_level_cumulative": True,      # 已付＋本次 ≤ 发票额，允许分次付款
        },
        _signoff(),
    ),
    Criterion(
        key="R4_CONTRACT_CAP",
        question="超合同拦截按什么口径、框架合同如何汇总、暂估价预警/拦截线",
        owner="财务侧（唐燕萍）",
        note="较 strawman 90%/100% 大幅收紧",
    ).signed(
        {
            "basis": "含税",                      # 含税口径对含税累计
            "framework_rollup": True,              # 框架合同子订单自动汇总
            "provisional_warn_pct": 0.30,
            "provisional_block_pct": 0.50,
        },
        _signoff(),
    ),
    Criterion(
        key="R5_PREPAY_TIERS",
        question="预付款按金额分几档、各档最低单据支撑与审批人、例外通道",
        owner="财务侧（唐燕萍）",
        note="≥100 万须正式合同（总经理批）为唐新增档；财务内部共识达成",
    ).signed(
        {
            # (下限含, 上限不含, 最低单据支撑, 审批人)；单位：元
            "tiers": (
                (0, 10_000, "仅申请", "采购经理"),
                (10_000, 100_000, "有PO", "采购总经理"),
                (100_000, 1_000_000, "有合同", "CFO"),
                (1_000_000, None, "有合同", "总经理"),
            ),
            "support_rank": ("无单据", "仅申请", "有PO", "有合同"),  # 由低到高
            "exception_approver": "CFO",
            "exception_backfill_workdays": 15,
            "exception_overdue_escalate_to": "审计部",
        },
        _signoff(),
    ),
    Criterion(
        key="R6_TERM_CLAUSES",
        question="账期条款解析哪几类、票到后默认几天、落节假日如何顺延",
        owner="财务侧（唐燕萍）",
        note="「工作日」直查节假日日历 `是否工作日` 列，不自拼三段（就绪包 §二.2）",
    ).signed(
        {
            "kinds": ("验收后", "到货后", "月结", "票到后"),
            "invoice_default_days": 10,
            "holiday_roll": "next_workday",
        },
        _signoff(),
    ),
    Criterion(
        key="R7_URGENT_CHANNEL",
        question="三单未配齐的紧急付款走什么通道、限期多久补齐",
        owner="财务侧（唐燕萍）",
    ).signed(
        {
            "approver": "CFO",
            "tag": "紧急特批",
            "backfill_workdays": 7,
            "tracking_list": "未匹配付款跟踪清单",
        },
        _signoff(),
    ),
    Criterion(
        key="R8_L4_PROMOTION_GATE",
        question="L3 建议升 L4 自动拦截要跑多久、误拦率与漏拦上限、谁会签",
        owner="财务侧（唐燕萍）＋ D2 裁决",
        note="这是晋级门槛本身；会签事件另在 PENDING.L4_PROMOTION_COSIGN，未签前 AUTOMATION_LEVEL 恒 L3",
    ).signed(
        {
            "min_run_months": 2,
            "max_false_block_rate": 0.02,
            "max_major_miss": 0,
            "cosign": ("Shao Peishen", "CFO"),
        },
        _signoff(),
    ),
])
CRITERIA.assert_rule_version(RULE_VERSION)   # 全签认 ⇒ 版本号不得带 unsigned，导入期即校验

# ── 🔴 待签认注册表（本包不代填；读取即抛）──
PENDING = CriteriaRegistry("FI3", [
    Criterion(
        key="PREPAY_AGEING_WARN_DAYS",
        question="预付款未核销超过多少天进入「账龄预警／催票」",
        owner="财务侧（唐燕萍）",
        note="R1 只定了等级（预警），未定天数；签认前引擎只出账龄度量、不判预警",
    ),
    Criterion(
        key="L4_PROMOTION_COSIGN",
        question="L3→L4 晋级会签落档（Shao Peishen ＋ CFO，凭据＝会签底稿路径）",
        owner="Shao Peishen ＋ CFO",
        note="会签流程至今未提前对齐（前置总表 FI3 行 v10）；本包停在档 1，不代联络 CFO 办公室",
    ),
])
PENDING_VERSION = "fi3-pending-unsigned-2026-09-17"
PENDING.assert_rule_version(PENDING_VERSION)

# ── FI2 结果消费口径（工程约定，非业务判据；design D-1，供 Shao Peishen 审）──
# FI2 五类里唯一不需人工复核的是「完全匹配」（fi2/result_classify.py `_NEEDS_REVIEW_CLASSES` 的补集）。
# FI3-1「未配齐」＝ 该发票在 FI2 结果里不存在、或类别不在此集合。
FI2_MATCHED_CLASSES = frozenset({"完全匹配"})


def audit_decision(**fields: Any) -> dict[str, Any]:
    """构造写审计用的 `decision`，**恒带当时生效的 `RULE_VERSION` 与自动化等级**。

    G-5 反向依赖（Shao Peishen 2026-09-03 拍板 `(a)`）：判据底座不接 `AuditLogger`；由场景引擎
    在 `record(AuditEvent(...))` 时把版本写进 `decision`。审计日志指向判据版本，不是反过来。
    """
    return {**fields, "rule_version": RULE_VERSION, "automation_level": AUTOMATION_LEVEL}


# ── fail-loud 文案 ──
U9C_NOT_WIRED = (
    "FI3 的 U9C 取数（Supplier/Query 收款账户、Pay/Trace 已付款、AP/Query 核销、采购合同/预付款）"
    "端点 IT 已于 2026-07 给齐，但本包档 1 只接 mock；u9c 模式一律 fail-loud，不得回退 mock。"
)
