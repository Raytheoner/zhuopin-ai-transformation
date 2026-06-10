## ADDED Requirements

### Requirement: 在途风险分级
引擎接收 connector 提供的 PO/库存/BOM/生产计划数据，对每笔未收货 PO 计算剩余天数和 DOS，返回三色风险列表，按 high→medium→low 排序。

#### Scenario: 已逾期或临近到期（high）
- **WHEN** 承诺交期剩余天数 ≤ 3（含负数逾期）或库存 DOS < 5 天
- **THEN** 该 PO 风险等级为 `high`，`risk_reasons` 包含触发原因文字

#### Scenario: 临近提醒（medium）
- **WHEN** 承诺交期剩余天数 ≤ 7（且 > 3）或库存 DOS < 10 天（且 ≥ 5）
- **THEN** 该 PO 风险等级为 `medium`

#### Scenario: 正常（low）
- **WHEN** 剩余天数 > 7 且 DOS ≥ 10 天
- **THEN** 该 PO 风险等级为 `low`

#### Scenario: 跳过已收货
- **WHEN** PO 的 `status == "received"`
- **THEN** 该 PO 不出现在结果中

#### Scenario: SRM 承诺交期覆盖
- **WHEN** 传入 `srm_dates = {po_id: confirmed_date_str}`
- **THEN** 对应 PO 的承诺交期以 SRM 日期为准，覆盖 connector 原始数据

#### Scenario: srm_only 模式
- **WHEN** `srm_only=True` 且某 PO 在 `srm_dates` 中无对应记录
- **THEN** 该 PO 被跳过（不进入风险列表）

### Requirement: compute_dos 计算
根据库存（current_stock - safety_stock）和 BOM × 生产计划推算的日均需求，计算各物料可用天数。

#### Scenario: 有需求物料
- **WHEN** 某物料在 BOM（level=1）× 生产计划中有毛需求
- **THEN** DOS = max(current_stock - safety_stock, 0) / (毛需求 / planning_days)，精确到小数点后 2 位

#### Scenario: 无需求物料
- **WHEN** 某物料无对应 BOM/生产计划需求
- **THEN** DOS = float('inf')（不触发低库存风险）
