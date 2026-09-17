# design · fi3-payment-validation-mvp

> **design 审：🟡 待 Shao Peishen**（本包由无头泳道 `OP-0917-J` 2026-09-17 建造到档 1；业务判据 R1–R8 已由唐燕萍签认，本 design 只审**工程决策 D1–D8**）。
> 🔴 业务口径的来源与出处以 `4-数字员工/财务部/FI3-付款申请自动校验/intent.md` §二 为准，本文件不重抄。
> 🔴 本泳道未连真实库、未部署、未触碰 `.51`、未发任何信、未改任何规划文档、未改排期、未消费 `#339`。

---

## Context

- **档位**：本包交付后 ＝ **档 1（mock 验证）**，25 passed。
- **判据现状**：`CriteriaRegistry("FI3")` 八条 R1–R8 **全部已签认**（`Signoff(signed_by="唐燕萍", signed_on="2026-07-10"／R1 "2026-07-14", evidence=就绪清单回复件)`），`RULE_VERSION="fi3-v1-tangyanping-2026-07-10"`；`PENDING` 两条未签认（账龄天数／L4 会签）。
- **拦截落点**：乙方案旁路清单（L3）。付款执行永远人工。

## 🔴 就绪包 §二 两段落字（propose 时必须照抄的正本，此处为落字）

**2.1 审批层级口径**：**审批层级口径已完整确认，来源＝财务总监唐燕萍圈定的 R1–R8，不设待复核标记。** 配套三条：① 不标「待复核」、不设待补标记（Shao Peishen 2026-08-21「手续我们线下弥补，你就当已完整处理」）；② 不再对接 CFO 办公室（§四 #93：唐燕萍为财务总监，其圈定即权威签认；就绪清单 §一 第 7 项不是 FI3 前置）；③ ⚠️ 本条不放松 R8——L3→L4 晋级仍须 **Shao Peishen ＋ CFO 会签**（D2 已裁），两件事不得互相引用着一起松掉。

**2.2 节假日日历口径**：① 数据源＝745 行 xlsx（唯一权威，`data/holidays/holiday_calendar.csv` 为其搬运件，源 md5 `8e5295e84d310477722b5bfc353e88be`）；**旧 33 天表已作废**，design 与代码不再出现「2026 全年 33 天」口径；② 工作日判定＝直查 `是否工作日` 列，不自行推导（`HolidayCalendar.is_workday`）；③ 覆盖上界 **2028-01-15** 为显式边界失败：`CalendarOutOfRangeError`，不静默外推、不回落自然日（用例 `test_calendar_out_of_range_fails_loud`／`test_due_date_beyond_calendar_fails_loud`）。

## Decisions（工程决策，待审）

| # | 决策 | 备选／代价 |
|---|---|---|
| **D1** | **FI2 结果消费口径**：FI3-1「配齐」＝ 发票在 FI2 结果里且类别 ∈ `{完全匹配}`（FI2 `_NEEDS_REVIEW_CLASSES` 的补集）；缺结果或其它四类＝未配齐。常量 `config.FI2_MATCHED_CLASSES`，**不是业务判据、不进注册表** | (b) 把「金额微差」也算配齐——会让 FI2 尚需人工的单据在 FI3 侧被放行，否 |
| **D2** | **主数据缺失＝拦截，不＝通过**：无生效收款账户／合同号查不到 ⇒ 拦截级发现（fail-loud 同族） | (b) 跳过该项——静默放行，否 |
| **D3** | **R7 特批只豁免 FI3-1**：拦截项全部为「三单未配齐」且申请标紧急才转 🟣；账户不符／超合同等不受紧急标记影响（用例 `test_urgent_does_not_bypass_non_three_way_blocks`） | (b) 紧急标记豁免全部拦截——与 R1「账户不一致＝拦截」冲突，否 |
| **D4** | **两项未签认另立 `PENDING` 注册表**而不混进 `CRITERIA`：让 `RULE_VERSION` 能如实不带 `unsigned`（R1–R8 确实全签了），同时未签认项仍读即抛。账龄只出度量（天数）不判预警 | (b) 单表混放——版本号被迫带 `unsigned`，下游会把已定稿的 R1–R8 误当骨架，否 |
| **D5** | **框架合同汇总**：子订单 `parent_contract_no` 指向父合同，上限记父合同，累计取父＋全部子的已付（R4 `framework_rollup`） | (b) 子订单各自设上限——U9C 侧框架合同子订单常为 0 上限，否 |
| **D6** | **账期解析＝正则四类**（`验收后N天／到货后N天／月结N天／票到后[N天]`，票到后缺 N 取 R6 默认 10）；解析不出或锚点缺失 ⇒ 提醒级「到期日算不出」，不猜、不回落 | (b) LLM 解析条款——引入运行时判断即须黄金集，档 1 不值，否 |
| **D7** | **仪表盘档 1 ＝ 汇总结构 ＋ Markdown 清单**；门户页 `/finance/fi3` 留档 2（不新起端口，预留网关 auth 接入点） | (b) 档 1 就做页面——超出「mock 验证」范围 |
| **D8** | **审计**：每张申请一条 `AuditEvent(scenario="FI3", action="payment_request_validate", automation_level="L3")`，`decision` 走 `config.audit_decision()` 恒带版本；`evaluator` 默认「待指定」直到财务侧指定清单复核人（`FI3-G-03`） | — |

### 三条实施约束（档 2 起照做）
1. 🔴 引擎任何数字只能来自 `CRITERIA.value_of(...)`；发现新口径先立 `Criterion` 再用。
2. 🔴 `AUTOMATION_LEVEL` 改 `L4` 的唯一前提 ＝ `PENDING.L4_PROMOTION_COSIGN` 签认落档（凭据＝会签底稿路径）。
3. 🔴 报告／审计／日志里账号只留尾 4 位（`mask_account`）。

## Open Questions（不阻断档 1）
- `FI3-G-01` 账龄预警天数 → 待闸开后并进下一封财务信；`FI3-G-02` L4 会签流程 → Shao Peishen；`FI3-G-03` 持有人/backup → 人事。
- 付款申请单乙方案的导出字段形态（`payment_requests.csv` 列为本包假设）须与财务侧对表后再接真实数据。
