# fi9-capitalization-rules Specification

## Purpose

按会计准则 ＋ 企业会计政策把研发成本判为资本化或费用化，并分别按准则口径与高新口径计算研发费用占比。
🔴 判错的代价与其余财务场景不同：编出来的判据不会报错，但会写进报给政府的申报材料里。

## Requirements

### Requirement: 未签认判据不得默认生效

系统 SHALL 把资本化/费用化判据、高新认定政策库、研发费用占比口径登记在平台判据签认注册表（`zhuopin_platform.criteria_signoff.CriteriaRegistry`，本场景声明于 `fi9_rd_cost/config.py`），签认前**一律未签认**，引擎读取未签认判据时 MUST 抛 `CriterionNotSignedOffError`，MUST NOT 回退到任何准则条文的通用解读或"行业惯例"，读值路径 MUST NOT 提供 `default` 参数或任何等价旁路。

> 本场景判错的代价与其余财务场景不同：编出来的判据不会报错，但会写进报给政府的申报材料里。

#### Scenario: 判据未签认时引擎拒绝判定
- **WHEN** 读取 `CAPITALIZATION_CRITERIA`
- **THEN** 抛出显式异常并指明缺哪一项、须谁签认，**不返回任何判定**

#### Scenario: CI 守住未签认状态
- **WHEN** 任何人把未签认判据签成实值而无签认落档
- **THEN** `test_criteria_registry_all_unsigned` 失败

#### Scenario: 版本号与签认状态不得互相撒谎
- **WHEN** 尚有判据未签认而 `RULE_VERSION` 不自陈 `unsigned`，或判据已全部签认而版本号仍带 `unsigned`
- **THEN** 配置模块在**导入期**即抛

### Requirement: 准则口径与高新口径不得混用

系统 SHALL 把会计准则口径与高新认定口径的研发费用占比分别定义、分别计算，MUST NOT 以一套口径同时充当两者。

> 两者分子分母并不一致，混用即出错，且结果看起来完全正常。

#### Scenario: 两套口径分别输出
- **WHEN** 计算研发费用占比
- **THEN** 分别输出准则口径与高新口径的结果，各自标注所依据的口径定义

### Requirement: 数据驱动的资本化规则注册表

系统 SHALL 把资本化/费用化规则维护为数据驱动的注册表并随版本登记，引擎按注册表判定，MUST NOT 把判定标准写死在代码里。每条判定 MUST 记录其所依据的准则条款或企业政策条目。

#### Scenario: 判定可追溯到条款
- **WHEN** 引擎对一条成本作出资本化/费用化判定
- **THEN** 结论的 `basis` 指向具体的准则条款或企业政策条目，并记录 `RULE_VERSION`

#### Scenario: 无法判定时标待定
- **WHEN** 某条成本不落在任何已签认规则的覆盖范围内
- **THEN** 判定为"待定"并标记需人工复核，MUST NOT 归入默认档

### Requirement: 项目高新口径归属不得预设

系统 MUST NOT 预设研发项目是否纳入高新口径。未按签认政策库判定前，该归属为"未判"而非"不纳入"。

#### Scenario: 默认未判
- **WHEN** 构造一个 `RdProject` 而未指定高新归属
- **THEN** 其 `is_high_tech_scope` 为空（未判），而非假（判了不纳入）
