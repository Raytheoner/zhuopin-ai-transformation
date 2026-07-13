## ADDED Requirements

### Requirement: BOM 取数按生效日期区间过滤当前版本（B3，2026-07-10 会议定稿，字段更正）
`get_bom_for_products` SHALL 对同一物料返回的多条 BOM 主记录，按 `m_effectiveDate ≤ 今天 < m_disableDate` 区间判定，只保留当前生效的那一条版本；该条内的子件行才纳入返回结果。`BomRow` 字段结构不变。

#### Scenario: 单一版本母件行为不变
- **WHEN** 某母件只有一条 BOM 主记录（无版本历史）
- **THEN** 该条记录正常参与 `get_bom_for_products` 结果，行为与本变更包实施前一致

#### Scenario: 多版本母件只取当前生效版本
- **WHEN** 某母件存在多条 BOM 主记录（版本历史），其中恰好一条满足 `m_effectiveDate ≤ 今天 < m_disableDate`
- **THEN** 只使用该条记录的子件行构造 `BomRow`，其余版本（含已失效的历史版本）不参与结果

#### Scenario: 修复现状"无条件取第一条"的活 bug
- **WHEN** 某母件的多条 BOM 主记录中，当前生效版本不是返回列表的第一条（生产环境实测确认存在此情况）
- **THEN** 系统正确选中区间判定满足的那一条，不再无条件使用列表第一条

#### Scenario: 无任何版本满足区间时 fail-safe 回退
- **WHEN** 某母件的全部 BOM 主记录都不满足 `m_effectiveDate ≤ 今天 < m_disableDate`（数据异常或版本空档期）
- **THEN** 回退选取 `m_disableDate` 最大的一条作为兜底，并写 audit 记录该异常，不静默返回空 BOM

### Requirement: 采购单到货日接真实 SRM 确认数据（A1 扩展，2026-07-10 会议定稿）
`get_purchase_orders` SHALL 对已取得的采购单，按 `(erpNo, supplyCode)` 配对查询携客云 SRM 的答交确认日期，查到则将 `PurchaseOrder.supplier_confirmed_date` 设为该真实确认日期；查不到则退回 `expected_date`。

#### Scenario: SRM 有确认日期时使用真实值
- **WHEN** 某采购单按 PO+供应商配对能在 SRM 查到确认交期
- **THEN** `supplier_confirmed_date` 设为该 SRM 确认日期，不再等于 `expected_date` 的占位值

#### Scenario: SRM 无确认记录时退回预期到货日
- **WHEN** 某采购单在 SRM 查不到对应确认记录
- **THEN** `supplier_confirmed_date` 退回 `expected_date`（与本变更包实施前行为一致）

#### Scenario: SRM 查询失败不阻断其他采购单
- **WHEN** 部分采购单的 SRM 查询发生异常（超时/接口错误）
- **THEN** 其余采购单的取数与确认日期查询不受影响，异常采购单退回 `expected_date` 并留痕，不中断整体流程
