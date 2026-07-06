## ADDED Requirements

### Requirement: 场景入口执行
Agent SHALL通过 mock CSV connector 调用引擎，输出风险摘要，写审计留痕。本能力原为 SC3 场景入口，2026-07-06 v2.3 重排后迁移为 SC8 内部答交可信度评估入口；audit `scenario` 字段由退役编号 "SC3" 改标存续场景 "SC8"，其余审计字段结构不变。

#### Scenario: 正常执行
- **WHEN** 以 mock CSV 目录调用 `run_answer_confidence(mock_dir, today)`
- **THEN** 返回 `list[SupplierRisk]`，且在平台 audit 写入一条 `scenario=SC8` 的 `in_transit_risk_eval` 事件

#### Scenario: 审计内容
- **WHEN** 执行完成
- **THEN** audit event 包含 `scenario=SC8`、`action=in_transit_risk_eval`、`automation_level=L1`、`decision` 含 `total_pos / high_count / medium_count / low_count`

#### Scenario: automation_level 合规
- **WHEN** automation_level=L1（内部只读看板）
- **THEN** 不触发 L2 人工确认门禁（L2 门禁限采购金额>50万/新供应商场景，本子模块不涉及）
