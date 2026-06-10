## ADDED Requirements

### Requirement: 采购建议生成
引擎接收缺料字典、供应商列表、物料最早需求日期，生成完整采购建议清单。

#### Scenario: 已认证供应商选价最低
- **WHEN** 某物料有多个 is_approved=True 的供应商
- **THEN** 选 unit_price 最低者作为推荐供应商

#### Scenario: MOQ/MPQ 约束采购量
- **WHEN** 计算建议采购量
- **THEN** qty = max(ceil(shortage / mpq) * mpq, moq)

#### Scenario: 最迟下单日推算
- **WHEN** 有供应商且有计划生产日期
- **THEN** latest_order_date = planned_date - lead_time_days - 3（安全提前期）

#### Scenario: 无认证供应商物料不静默跳过
- **WHEN** 某物料无 is_approved=True 的供应商
- **THEN** 该物料仍出现在建议清单中，supplier_id=None，purchase_qty=0，review_status="待人工审核"，触发 R2_unapproved_supplier 规则

### Requirement: 审核规则评估（BusinessRulePolicy）
集中评估 R1/R2 规则，返回结构化决策。

#### Scenario: R1 金额阈值
- **WHEN** purchase_qty × unit_price ≥ 500,000 元
- **THEN** review_status="待人工审核"，triggered_rules 含 "R1_amount_threshold"

#### Scenario: R2 无认证供应商
- **WHEN** supplier_id is None
- **THEN** review_status="待人工审核"，triggered_rules 含 "R2_unapproved_supplier"

#### Scenario: 可自动下单
- **WHEN** 金额 < 500,000 且供应商已认证
- **THEN** review_status="可自动下单"，triggered_rules=[]

### Requirement: 成本汇总
#### Scenario: 分桶汇总
- **WHEN** 给定建议列表
- **THEN** 返回 auto_total / review_total / grand_total（与 supplychain 黄金值一致：auto≈35850，review≈640000）
