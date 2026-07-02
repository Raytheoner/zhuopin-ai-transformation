# o2-kit-shortage-alert Specification

## Purpose
TBD - created by archiving change o2-kit-shortage-alert. Update Purpose after archive.
## Requirements
### Requirement: O2 数字员工入口（run_kit_alert）
数字员工 SHALL 提供 `run_kit_alert(bom, plans, inventory, purchase_orders, audit_logger) -> KitAlertResult` 函数，内部调用 `explode_bom` + `calc_shortage`，把本次齐套决策（成品列表/缺口汇总/缺口物料数/运行时间戳）写 `AuditLogger`，返回结构化结果。

#### Scenario: mock 数据端到端跑通
- **WHEN** 传入脱敏 BOM/库存/在途/生产计划 fixture（两个成品、三层 BOM）
- **THEN** 函数正常返回 `KitAlertResult`，shortages 字段包含期望的缺口物料

#### Scenario: 审计记录写入
- **WHEN** 调用 `run_kit_alert` 后查看 `AuditLogger` sink
- **THEN** 有一条记录，含 `event_type="kit_shortage_analysis"`、`products` 列表、`shortage_count` 整数、`timestamp`

#### Scenario: 无缺口时返回空 shortages
- **WHEN** 库存充足覆盖全部毛需求，无需在途补充
- **THEN** `KitAlertResult.shortages == {}`，审计记录 `shortage_count == 0`

### Requirement: KitAlertResult 数据契约
`KitAlertResult` SHALL 是 dataclass，含以下字段：`products: list[str]`（本次分析的成品 ID 列表）、`gross_demand: dict[str, float]`（物料毛需求）、`shortages: dict[str, float]`（缺口 > 0 的物料）、`shortage_count: int`、`analyzed_at: str`（ISO 8601 时间戳）。

#### Scenario: 结果字段完整
- **WHEN** `run_kit_alert` 正常返回
- **THEN** `result.products`、`result.gross_demand`、`result.shortages`、`result.shortage_count`、`result.analyzed_at` 均非空/已填充

### Requirement: 齐套精度黄金对照
数字员工 SHALL 在至少一个黄金测试中与手工计算结果对照，偏差 < 1%（即每个缺口值的相对误差 < 0.01）。

#### Scenario: 黄金对照零偏差
- **WHEN** 使用固定两成品/三层 BOM 的 fixture 运行
- **THEN** 所有缺口值与手工预算结果的绝对偏差 / 手工值 < 0.01

