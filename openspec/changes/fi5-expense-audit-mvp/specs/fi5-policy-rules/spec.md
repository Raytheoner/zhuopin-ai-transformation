## ADDED Requirements

### Requirement: 未签认判据不得默认生效

系统 SHALL 把差旅标准、招待限额等报销政策判据维护在配置层（`fi5_expense_audit/config.py`），且在财务侧实名签认前**一律为空值**。规则引擎读到空判据时 MUST fail-loud，MUST NOT 回退到任何内置默认值、经验值或"合理估计"。

> 理由：一个看起来合理的默认阈值不会报错、不产生任何信号，却已经在替财务部做判断；填上去之后没有任何机制会发现它是编的。本要求与本项目「工具静默回退」事故同族。

#### Scenario: 判据未签认时引擎拒绝判定
- **WHEN** `TRAVEL_STANDARD_TABLE` 或 `ENTERTAINMENT_LIMIT_TABLE` 为空
- **THEN** 引擎抛出显式异常并指明缺哪一项判据、须谁签认，**不返回任何判定结论**

#### Scenario: CI 守住空值
- **WHEN** 任何人把未签认判据填成实数而未同步升 `RULE_VERSION`、未附签认落档
- **THEN** `tests/test_scaffold.py::test_unsigned_criteria_stay_none` 失败，CI 变红

#### Scenario: 签认后按三步落地
- **WHEN** 财务侧交付判据表并实名签认
- **THEN** 依次「改 `config` 实数 → 升 `RULE_VERSION` → 同步改守护用例」三步齐做，缺一步不得合入

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
