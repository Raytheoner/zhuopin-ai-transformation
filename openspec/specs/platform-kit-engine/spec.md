# platform-kit-engine Specification

## Purpose
平台齐套计算引擎：给定 BOM 展开需求与库存/在途快照，计算各物料缺口，输出齐套能否满足的判定与缺料清单。是 SC5 / O2 等多场景的共享底座（rule-of-three 触发后提升至平台）。
## Requirements
### Requirement: 齐套计算在途量不因缺库存快照被忽略
`kit_engine.calc_shortage` SHALL 在物料不在库存快照（`inventory` 无对应行）时**仍计入其在途量**（`available = 在途`），不得把 available 当 0 而高估缺口。缺库存快照的物料 MUST 输出到告警清单（`missing_snapshot`），供下游提示数据缺口。真实库存端点未就绪（`get_inventory` 恒返回 0 库存项）时该路径不再误报虚高缺口。

#### Scenario: 缺库存快照仍计在途量
- **WHEN** 某物料在 BOM 需求中存在，但不在库存快照
- **THEN** available = 在途量（而非 0），缺口正确计算；该物料出现在 `missing_snapshot` 告警清单

#### Scenario: 库存快照有该物料时正常计算
- **WHEN** 物料既有库存快照也有在途量
- **THEN** `available = 库存 + 在途`，缺口 = max(0, need - available)

#### Scenario: 全量零库存快照时不虚报缺口
- **WHEN** `get_inventory` 返回空（真实库存端点未就绪）
- **THEN** 缺口以在途量抵扣，不因库存快照缺失而把全部需求报为缺料

### Requirement: 黄金值精确相等，不浮点近似
`kit_engine.calc_shortage` 的黄金基准断言 MUST 使用精确相等（`==`）而非近似比较（`pytest.approx` / 允差）。auto_total=35850 / review_total=640000 / grand_total=675850 为当前黄金值快照，任何逻辑变更导致偏差 MUST 回归失败，不得静默通过。

#### Scenario: 黄金值不漂移
- **WHEN** 对标准黄金基准样本运行 `calc_shortage`
- **THEN** 结果与黄金值精确相等（auto_total=35850, review_total=640000）

### Requirement: 在途 PO 到货日过滤（A1）
引擎 SHALL 提供纯函数 `filter_transit_by_arrival(purchase_orders, cutoff_date)`，只保留预期到货日 ≤ `cutoff_date` 的采购单，供调用方在传入 `calc_shortage` 之前自行过滤在途量。本函数不修改 `calc_shortage`/`explode_bom` 现有签名与默认行为。

#### Scenario: 超期未到的在途单不计入可用
- **WHEN** 调用方传入一批采购单，其中部分单据的预期到货日晚于 `cutoff_date`
- **THEN** `filter_transit_by_arrival` 返回的列表剔除这些超期单据，调用方据此再调用 `calc_shortage` 时超期在途不再计入可用量

#### Scenario: 到货日≤截止日的在途单正常保留
- **WHEN** 采购单预期到货日 ≤ `cutoff_date`
- **THEN** 该采购单保留在返回列表中，行为与现状一致

#### Scenario: 不调用本函数时行为零变化
- **WHEN** 调用方不调用 `filter_transit_by_arrival`、直接把原始采购单列表传给 `calc_shortage`（现有 O2/SC7 调用方式）
- **THEN** `calc_shortage` 的计算结果与改造前完全一致，不产生任何行为差异

### Requirement: 追料 L/T 分桶（A2）
引擎 SHALL 提供纯函数 `bucket_shortage_by_lead_time(shortages, demand_dates, lead_times, today)`，把 `calc_shortage` 输出的缺口按"是否临近需要追料"分为 `urgent`（临近，需追）与 `observe`（未临近，观察不追）两个字典。

#### Scenario: 需求日临近且有缺口 → 归入 urgent
- **WHEN** 某物料存在缺口，且 `需求日 - today < 该物料采购提前期(L/T)`
- **THEN** 该物料计入 `urgent` 字典

#### Scenario: 需求日未临近 → 归入 observe
- **WHEN** 某物料存在缺口，但 `需求日 - today ≥ 该物料采购提前期(L/T)`
- **THEN** 该物料计入 `observe` 字典，不进入 `urgent`（即不触发即时追料动作）

#### Scenario: 缺 L/T 数据时兜底为立即追料
- **WHEN** 某物料存在缺口，但 `lead_times` 中无该物料的 L/T 数据
- **THEN** 该物料兜底计入 `urgent`（净需求>0 即追，与现状行为一致，不因缺数据漏判）

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

