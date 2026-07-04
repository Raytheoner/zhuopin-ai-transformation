# delivery-deviation-monitor Specification

## Purpose
SC8 承诺交期偏差监控：对已对客承诺的交付日与最新实际进展推算日比对，超阈值告警 PMC/采购、触发重算回调、写审计。纯函数 + 依赖注入，不直接对客外发。

## Requirements

### Requirement: 承诺交期偏差监控与告警
SC8 SHALL 提供偏差监控：对一条已对客承诺的交付日与最新"实际进展"推算交付日比对，消费阈值 `config.DEVIATION_ALERT_DAYS`（VP 签字=3 天）。偏差**严格大于**阈值（或最新已无法预测交付日）→ MUST 标记告警（`breached=True`、`requires_recompute=True`）、写 `delivery_deviation_alert` 审计（含 so_id/承诺日/实际日/偏差天数/阈值）、并触发注入的重算回调（`on_breach`，缺省仅告警+留痕）。本能力为纯函数 + 依赖注入，不直接对客发送（更正经既有 L2 门禁）。

#### Scenario: 偏差超阈值触发告警与回调
- **WHEN** 实际进展推算日与承诺日偏差严格大于 `DEVIATION_ALERT_DAYS`
- **THEN** `breached=True`，写 `delivery_deviation_alert` 审计，触发 `on_breach` 回调

#### Scenario: 偏差未超阈值不告警
- **WHEN** 实际进展推算日与承诺日偏差 ≤ 阈值
- **THEN** `breached=False`，不写告警审计，不触发回调

#### Scenario: 无法预测交付日时告警
- **WHEN** 最新进展无法推算出有效交付日
- **THEN** `breached=True`，`requires_recompute=True`，写审计标注无法预测

#### Scenario: 重算回调不对客外发
- **WHEN** `on_breach` 触发重算
- **THEN** 重算结果写内部看板/PMC 群，不触发对客外发（对客更正须经 L2 门禁）

### Requirement: 偏差阈值由 VP 签字确认
`DEVIATION_ALERT_DAYS` 默认值 3 天，须经 VP（Paul）签字后方可修改。配置变更 MUST 写审计留痕（谁改/改成多少/原因）。

#### Scenario: 阈值修改留痕
- **WHEN** `DEVIATION_ALERT_DAYS` 被更新
- **THEN** 变更写 `config_change` 审计事件，含旧值/新值/操作人
