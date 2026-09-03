## ADDED Requirements

### Requirement: L2 门禁——AI 不自动结案

系统 SHALL 保证被标记 `needs_manual_review` 的行**一律不自动结案**，结案权在财务经理。审核结论的默认侧是"需人工"，放行须由签认判据显式证成。

#### Scenario: 默认需人工
- **WHEN** 构造一条尚未经任何规则判定的 `AuditFinding`
- **THEN** 其 `needs_manual_review` 为真

#### Scenario: 报告标注非终局
- **WHEN** 输出部门费用分析报告
- **THEN** 报告显著标注「AI 初审建议，结案在财务经理」

### Requirement: 判定全链写平台 audit

系统 SHALL 把每笔审核判定写入 `zhuopin_platform.audit`（append-only，3 年留存），满足 IATF 16949 可追溯要求。

#### Scenario: 每笔判定留痕
- **WHEN** 引擎对任一报销行作出判定
- **THEN** 一条含单号、行号、命中规则、风险等级、`RULE_VERSION` 与判定时刻的审计事件被追加写入

### Requirement: 部门级费用分析聚合

系统 SHALL 按（部门 × 科目 × 期间）聚合费用并输出分析报告。

#### Scenario: 三键聚合
- **WHEN** 给定一个期间的报销明细集合
- **THEN** 输出按部门与科目聚合的金额、笔数、超标笔数与风险分布
