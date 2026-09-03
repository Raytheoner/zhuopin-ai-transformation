## ADDED Requirements

### Requirement: 三类异常报销风险分级

系统 SHALL 对报销行做风险分级，覆盖**超标／频繁／关联交易**三类异常。分级边界 `RISK_GRADE_BOUNDARIES` 须财务侧签认，未签认时 MUST fail-loud。

> 「频繁」是几次/几天、「关联交易」如何识别（供应商主数据比对？亲属关系？），本项目当前**均无成文口径**，故不得由实现方自定义。

#### Scenario: 边界未签认
- **WHEN** `RISK_GRADE_BOUNDARIES` 为空
- **THEN** 引擎抛出显式异常，MUST NOT 自行定义"频繁"或"关联"的判定口径

#### Scenario: 分级结果可追溯
- **WHEN** 任一行被判定为某风险等级
- **THEN** 结论记录命中的规则 ID、所用 `RULE_VERSION` 与判定依据，写入平台 `audit`

### Requirement: LLM 判断须有黄金集方可晋档 3

若关联交易识别或发票真伪/合规校验落在 LLM 侧，系统 SHALL 为该判断任务累积黄金集（冻结输入 ＋ 专家认可输出）。**无黄金集不晋档 3**（全景规划 §4.0）。

#### Scenario: 无黄金集阻断晋档
- **WHEN** 场景申请晋入档 3（内部服务）而 LLM 判断任务尚无黄金集
- **THEN** 晋档被阻断，黄金集缺口须先补齐
