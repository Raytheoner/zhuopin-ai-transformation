## ADDED Requirements

### Requirement: 多层 BOM 递归展开 + 逐层现货抵扣（B1）
引擎 SHALL 提供纯函数 `explode_bom_with_netting(bom, plans, inventory, *, net_at_each_level=True)`，递归展开多层 BOM；展开中间节点（子装配/半成品）前，若该节点有现货，先用现货抵扣需求，只有净缺口（现货不足部分）才继续递归展开其子件需求。叶子件（非子装配的最终物料）不做现货抵扣，直接累加进返回的毛需求字典。本函数不修改 `explode_bom`/`calc_shortage` 现有签名与默认行为。

#### Scenario: 半成品现货充足时不展开其子件
- **WHEN** 某中间节点（半成品）的现货可用量 ≥ 该节点的毛需求
- **THEN** 不递归展开该节点的子件需求，其子件不出现在返回的毛需求字典里

#### Scenario: 半成品现货不足时按净缺口展开
- **WHEN** 某中间节点现货可用量 < 毛需求（净缺口 > 0）
- **THEN** 按净缺口（毛需求-现货，而非原始毛需求）递归展开该节点的子件需求

#### Scenario: 半成品无现货记录时按原始毛需求展开
- **WHEN** 某中间节点在 `inventory` 中无记录
- **THEN** 视为现货=0，按原始毛需求全额展开子件（保守兜底，不因数据缺失漏报缺料）

#### Scenario: 叶子件不做现货抵扣
- **WHEN** 某物料不是任何 BOM 行的 `product_id`（即最终叶子件）
- **THEN** 直接按计算出的毛需求累加进返回字典，不查询/抵扣其现货（是否够用交由下游判断）

#### Scenario: 不调用本函数时 explode_bom/calc_shortage 行为零变化
- **WHEN** 调用方继续使用现有 `explode_bom`/`calc_shortage`（不调用本函数）
- **THEN** 行为与本变更包实施前完全一致，O2/SC7 零影响
