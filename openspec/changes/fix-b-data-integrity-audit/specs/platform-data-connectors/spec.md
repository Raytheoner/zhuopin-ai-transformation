## ADDED Requirements

### Requirement: BOM 拉取失败显式信号，不静默吞错
`ZpConnector.get_bom_for_products` SHALL 在单品 BOM 查询失败时收集失败料号清单，不得静默丢弃返回残缺 BOM。部分失败 MUST 返回 `(rows, failed_ids)` 并写审计痕迹；全部产品查询失败 MUST 抛出带失败明细的错误，绝不返回空结果当成功。下游齐套据此不再因残缺 BOM 算出虚低毛需求。

#### Scenario: 部分子件查询失败返回失败清单
- **WHEN** 查询多个产品 BOM，其中部分产品查询抛异常
- **THEN** 返回已成功的 rows 与失败料号清单 `failed_ids`，并写 `bom_partial_failure` 审计痕迹

#### Scenario: 全部失败抛错
- **WHEN** 所有产品 BOM 查询均失败
- **THEN** 抛出带失败明细的异常，不返回空 BOM

### Requirement: get_bom 回退走 fail-loud 闸门
`ZpConnector.get_bom()` 在真实 BOM 为空时的 CSV 回退 MUST 经 `_fallback_or_failloud` 闸门：`real` 模式未显式 opt-in → fail-loud（`RealEndpointNotReadyError`）；显式 opt-in → CSV 但审计标 `CSV_mock` + `UserWarning`（非权威、禁入对客/L2），消除 mock BOM 静默混入且审计错标 `CSV` 的旁路。

#### Scenario: real 模式真实 BOM 空时 fail-loud
- **WHEN** `data_source=real` 且未 opt-in，真实 BOM 为空，调用 `get_bom()`
- **THEN** 抛 `RealEndpointNotReadyError`，不静默回退 mock CSV

### Requirement: SRM 承诺交期区分查询失败与未答交
`XkySrmConnector.get_confirmed_dates` SHALL 区分"查询失败"（异常）与"供应商未答交"（正常返回 None）。单 PO 查询异常 MUST 计入失败 PO 清单并写 audit error 痕迹，返回 `(confirmed, failed_pos)`；"未答交"不计入失败。在途三色清单据此不再把查询失败误当无延期。

#### Scenario: 单 PO 查询失败计入失败清单
- **WHEN** 批量查询承诺交期，其中一个 PO 查询抛异常、一个未答交、一个有交期
- **THEN** 返回 confirmed 仅含有交期者、failed_pos 含异常 PO，并写 `confirmed_date_query_failed` 审计；未答交者既不在 confirmed 也不在 failed

### Requirement: 连接器 from_env 审计缺失 fail-loud 告警
`ZpConnector.from_env` / `XkySrmConnector.from_env` 生产构造路径在未注入 `audit` 时 MUST 触发 `UserWarning`（生产访问将不留痕的显式告警），保留向后兼容（不抛错）。

#### Scenario: from_env 无 audit 触发告警
- **WHEN** 调用 `ZpConnector.from_env()` 未传 `audit`
- **THEN** 触发 `UserWarning`；注入 audit 时不告警
