## ADDED Requirements

### Requirement: 承诺交期偏差监控与告警
SC8 SHALL 提供偏差监控：对一条已对客承诺的交付日与最新"实际进展"推算交付日比对，消费阈值 `config.DEVIATION_ALERT_DAYS`（VP 签字=3 天）。偏差**严格大于**阈值（或最新已无法预测交付日）→ MUST 标记告警（`breached=True`、`requires_recompute=True`）、写 `delivery_deviation_alert` 审计（含 so_id/承诺日/实际日/偏差天数/阈值）、并触发注入的重算回调（`on_breach`，缺省仅告警+留痕）。本能力为纯函数 + 依赖注入，不直接对客发送（更正经既有 L2 门禁）。

#### Scenario: 偏差超阈值告警并触发重算
- **WHEN** 承诺交付日与实际进展推算交付日相差 5 天（> 3）
- **THEN** `breached=True`、写 `delivery_deviation_alert` 审计、调用注入的 `on_breach` 回调

#### Scenario: 偏差在阈值内不告警
- **WHEN** 相差 ≤ 3 天（含恰好 3 天）
- **THEN** `breached=False`、不写审计、不调回调

#### Scenario: 承诺后变为无法预测视为重大偏差
- **WHEN** 最新实际进展无法推算交付日（actual_date 为 None）
- **THEN** `breached=True`、`requires_recompute=True`、写审计告警

#### Scenario: 无审计/无回调注入仍可运行
- **WHEN** 调用时未注入 audit 与 on_breach 且偏差超阈值
- **THEN** 返回 `breached=True` 的结果、不抛错（留痕/重算为可选注入）
