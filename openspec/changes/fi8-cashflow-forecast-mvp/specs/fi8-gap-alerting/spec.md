## Purpose

在预测序列上识别并高亮资金缺口窗口，并对满足门限的大额逾期应收触发催收 escalation。
🔴 资金调度是 CFO 的决策，本能力 MUST NOT 自行发起任何调度动作。

## ADDED Requirements

### Requirement: 资金缺口窗口高亮

系统 SHALL 在预测序列上识别并高亮资金缺口窗口（起止周、最低余额、缺口额）。判定门限登记在平台判据签认注册表（`zhuopin_platform.criteria_signoff.CriteriaRegistry`，本场景声明于 `fi8_cashflow_forecast/config.py`），未签认时读取即抛 `CriterionNotSignedOffError`，读值路径 MUST NOT 提供 `default` 参数或任何等价旁路。

#### Scenario: 门限未签认
- **WHEN** 读取 `CASH_GAP_THRESHOLD`
- **THEN** 引擎抛出显式异常，MUST NOT 以"余额小于 0"或任何其他默认口径代替签认门限

#### Scenario: 版本号与签认状态不得互相撒谎
- **WHEN** 尚有判据未签认而 `RULE_VERSION` 不自陈 `unsigned`，或判据已全部签认而版本号仍带 `unsigned`
- **THEN** 配置模块在**导入期**即抛

#### Scenario: 窗口可追溯
- **WHEN** 识别出一个缺口窗口
- **THEN** 结果记录起止周、最低余额、缺口额与所用 `RULE_VERSION`

### Requirement: L2 门禁——资金调度由 CFO 决策

系统 MUST NOT 自行发起任何资金调度动作。缺口窗口的默认状态是"未经 CFO 确认"。

#### Scenario: 默认未确认
- **WHEN** 构造一个 `GapWindow`
- **THEN** 其 `confirmed_by_cfo` 为假

### Requirement: 大额逾期应收催收 escalation

系统 SHALL 对满足签认门限的大额逾期应收触发催收 escalation，经平台 notifier 推送。

#### Scenario: 门限未签认
- **WHEN** `COLLECTION_ESCALATION_CRITERIA` 为空
- **THEN** 引擎 fail-loud，MUST NOT 默认触发、也 MUST NOT 默认不触发

#### Scenario: 推送走平台通道
- **WHEN** 触发一笔催收 escalation
- **THEN** 经 `zhuopin_platform.shared_tools.notifiers` 推送，MUST NOT 自建通知通道

### Requirement: 判定全链写平台 audit

系统 SHALL 把每次缺口判定与催收触发写入平台 `audit`（append-only，3 年留存）。

#### Scenario: 留痕
- **WHEN** 产生一次缺口判定或催收触发
- **THEN** 一条含判定依据、门限值、`RULE_VERSION` 与时刻的审计事件被追加写入
