## ADDED Requirements

### Requirement: 场景入口执行
Agent 通过 mock CSV connector 调用引擎，输出风险摘要，写审计留痕。

#### Scenario: 正常执行
- **WHEN** 以 mock CSV 目录调用 `run_sc3(mock_dir, today)`
- **THEN** 返回 `list[SupplierRisk]`，且在平台 audit 写入一条 SC3 in_transit_risk_eval 事件

#### Scenario: 审计内容
- **WHEN** 执行完成
- **THEN** audit event 包含 `scenario=SC3`、`action=in_transit_risk_eval`、`automation_level=L1`、`details` 含 `total_pos / high_count / medium_count / low_count`

#### Scenario: automation_level 合规
- **WHEN** automation_level=L1（内部只读看板）
- **THEN** 不触发 L2 人工确认门禁（L2 门禁限采购金额>50万/新供应商场景，SC3 不涉及）
