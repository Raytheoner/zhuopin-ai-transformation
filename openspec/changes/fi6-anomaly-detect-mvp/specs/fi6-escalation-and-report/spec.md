## ADDED Requirements

### Requirement: L2 升级推送——AI 标记不处置

系统 SHALL 对高风险交易触发审批并推送财务主管，但 MUST NOT 自行处置任何交易。判定结论的默认侧是"需人工复核、未升级"，升级须由签认门限显式证成。

#### Scenario: 默认侧
- **WHEN** 构造一条尚未经判定的 `AnomalyFinding`
- **THEN** `needs_manual_review` 为真且 `escalated` 为假

#### Scenario: 门限未签认
- **WHEN** `L2_ESCALATION_CRITERIA` 为空
- **THEN** 引擎抛出显式异常，MUST NOT 默认推送、也 MUST NOT 默认不推送

#### Scenario: 推送走平台通道
- **WHEN** 一笔交易被升级
- **THEN** 经 `zhuopin_platform.shared_tools.notifiers` 推送，MUST NOT 自建通知通道

### Requirement: 判定全链写平台 audit

系统 SHALL 把每笔异常判定写入平台 `audit`（append-only，3 年留存）。

#### Scenario: 每笔留痕
- **WHEN** 检测器对任一交易作出判定
- **THEN** 一条含交易号、命中模式、风险等级、`RULE_VERSION` 与判定时刻的审计事件被追加写入

### Requirement: 月度系统性内控漏洞分析

系统 SHALL 输出月度异常交易分析报告，识别**系统性**内控漏洞（反复出现的同类异常、集中在某单位/科目/经办的模式），而不仅罗列个案。

#### Scenario: 汇总而非罗列
- **WHEN** 生成某月报告
- **THEN** 报告按模式与维度聚合出重复出现的问题，并标注「AI 分析建议，处置在财务主管」
