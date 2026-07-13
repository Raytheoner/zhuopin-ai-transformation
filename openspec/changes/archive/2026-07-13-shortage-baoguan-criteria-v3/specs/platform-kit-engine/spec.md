## ADDED Requirements

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
