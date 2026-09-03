## Purpose

把公司报销政策（差旅标准／招待限额等）维护成数据驱动的规则注册表，并据此对报销明细逐行判定是否超标。
🔴 政策判据属知识型资产，须财务侧实名签认；本能力的核心约束是**未签认判据一律不得默认生效**。

## ADDED Requirements

### Requirement: 未签认判据不得默认生效

系统 SHALL 把差旅标准、招待限额等报销政策判据登记在平台判据签认注册表（`zhuopin_platform.criteria_signoff.CriteriaRegistry`，本场景声明于 `fi5_expense_audit/config.py`），且在财务侧实名签认前**一律未签认**。规则引擎读取未签认判据时 MUST 抛 `CriterionNotSignedOffError`，MUST NOT 回退到任何内置默认值、经验值或"合理估计"。读值路径 MUST NOT 提供 `default` 参数或任何等价旁路。

> 理由：一个看起来合理的默认阈值不会报错、不产生任何信号，却已经在替财务部做判断；填上去之后没有任何机制会发现它是编的。本要求与本项目「工具静默回退」事故同族。
>
> 判据签认收进底座的依据是 rule-of-three（`FI5/FI6/FI8/FI9/FI10` 五份手抄，5 > 3）。**未签认判据的值恒为空、读取即抛**这条行为在收编前后完全一致，变的只是它写在哪。

#### Scenario: 判据未签认时引擎拒绝判定
- **WHEN** 读取 `TRAVEL_STANDARD_TABLE` 或 `ENTERTAINMENT_LIMIT_TABLE`
- **THEN** 引擎抛出显式异常并指明缺哪一项判据、须谁签认，**不返回任何判定结论**

#### Scenario: CI 守住未签认状态
- **WHEN** 任何人把未签认判据签成实数而未同步升 `RULE_VERSION`、未附签认落档
- **THEN** `tests/test_scaffold.py::test_criteria_registry_all_unsigned` 失败，CI 变红

#### Scenario: 版本号与签认状态不得互相撒谎
- **WHEN** 尚有判据未签认而 `RULE_VERSION` 不自陈 `unsigned`，或判据已全部签认而版本号仍带 `unsigned`
- **THEN** 配置模块在**导入期**即抛，MUST NOT 等到引擎跑到某条分支才发现

#### Scenario: 签认后按四步落地
- **WHEN** 财务侧交付判据表并实名签认
- **THEN** 依次「`Criterion.signed(值, Signoff(实名＋日期＋落档凭据＋版本))` → 升 `RULE_VERSION` → 同步改守护用例 → 登记知识资产台账」四步齐做，缺一步不得合入

### Requirement: 数据驱动的报销政策规则注册表

系统 SHALL 把报销政策规则维护为数据驱动的注册表，每条 `{规则ID, 条件, 结论, 严重度, 是否触发 L2}`，并随版本登记（IATF 单一可信源）。引擎按注册表判定，MUST NOT 把政策标准写死在判定代码里。

#### Scenario: 差旅住宿超标
- **WHEN** 某行费用科目属差旅住宿，且 `amount / nights` 超出该职级的每日上限
- **THEN** 命中超标规则，记录规则 ID 与所用 `RULE_VERSION`，标记需人工复核

#### Scenario: 招待人均超限
- **WHEN** 某行属招待费且 `amount / headcount` 超出该场合类型的人均上限
- **THEN** 命中超限规则并标记需人工复核

#### Scenario: 招待人数缺失
- **WHEN** 招待类明细行未填 `headcount`（或填 0）
- **THEN** 引擎 MUST NOT 用任何假定人数计算人均；该行直接标记需人工复核并说明缺失字段

#### Scenario: 场合类型未登记
- **WHEN** 明细行的场合类型不在限额表内
- **THEN** 标记需人工复核并提示该场合类型待补进判据表，MUST NOT 套用最接近的类型
