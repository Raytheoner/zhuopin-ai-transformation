## Purpose

支持在基线预测上叠加情景调整（如「某客户延迟付款 30 天」）并输出其对现金流与缺口窗口的影响。
🔴 what-if 结果恒标记为假设情景且标记不可关闭——把假设当预测报给 CFO 是这类工具最典型的误用。

## ADDED Requirements

### Requirement: what-if 情景影响分析

系统 SHALL 支持在基线预测上叠加情景调整（如「某客户延迟付款 30 天」）并输出其对现金流与缺口窗口的影响。

#### Scenario: 情景叠加
- **WHEN** 给定一个基线预测与一组情景调整
- **THEN** 输出调整后的预测序列，并标出与基线的差异及新增/消失的缺口窗口

#### Scenario: 情景可追溯到基线
- **WHEN** 输出一个 what-if 结果
- **THEN** 结果记录其 `baseline_ref`，可复原对照的基线预测

### Requirement: what-if 结果恒为假设，不得与基线混同

系统 SHALL 把 what-if 结果恒标记为假设情景，且该标记不可关闭。呈现层 MUST 在视觉与措辞上区隔假设情景与基线预测。

> 把假设情景当成预测报给 CFO，是这类工具最典型的误用。

#### Scenario: 标记不可关闭
- **WHEN** 构造任一 `WhatIfScenario`
- **THEN** 其 `is_hypothetical` 为真

#### Scenario: 呈现层区隔
- **WHEN** 在报表或门户上同时展示基线与 what-if
- **THEN** 两者显著区隔，what-if 侧标注「假设情景，非预测」
