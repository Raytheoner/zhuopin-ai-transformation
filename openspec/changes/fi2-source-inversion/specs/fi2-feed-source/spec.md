## ADDED Requirements

### Requirement: u9c 源第三种驱动模式——按会计期间取全部未立账 AP

系统 SHALL 在 `data_source="u9c"` 下支持第三种 AP 驱动模式：调用方给定会计期间范围口径后，由系统自行取该范围内全部未立账 AP 明细行，**调用方无需预先知道任何 AP 单号或供应商编码**。

该模式与既有两种驱动模式（按 AP 单号清单、按供应商编码）SHALL 互斥择一；三者同时注入时 MUST 以显式的优先级择一并留痕，MUST NOT 静默合并成一个更大的集合。

新模式 MUST NOT 改变 `load_po_lines()` / `load_grn()` / `load_ap_lines()` 三个方法的零参数调用签名，也 MUST NOT 改变它们共享同一次 AP 拉取缓存的既有行为。

#### Scenario: 未立账驱动模式取数

- **WHEN** `data_source="u9c"`、已注入连接器，且选择未立账驱动模式
- **THEN** 系统自行拉取该会计期间范围内全部未立账 AP 明细行，并据其去重后的来源单号拉取对应 PO 与收货单

#### Scenario: 三种驱动模式互斥

- **WHEN** 同时注入了未立账驱动、供应商清单与单号清单
- **THEN** 系统按既定优先级只采用其中一种，并在留痕中写明采用了哪一种

## MODIFIED Requirements

### Requirement: 数据源三态切换（mock / csv / u9c）与 fail-loud

系统 SHALL 支持 `data_source` 参数在 `mock`（夹具）/ `csv`（应急桥接）/ `u9c`（直读）三态间切换，切换 MUST 不改变匹配引擎与分类逻辑。`u9c` 源在端点不可用期间 MUST 以 `RealEndpointNotReadyError`（复用平台 `shared_tools.connector_errors`）fail-loud，不得静默回退到 mock 或 csv。

**本次新增的约束**：新增未立账驱动模式 MUST NOT 改变既有两种驱动模式（按 AP 单号清单、按供应商编码）在相同输入下的任何行为——包括返回的行集合、缓存复用方式、以及未注入连接器时的 fail-loud 表现。该「行为不变」MUST 由回归用例覆盖，MUST NOT 仅凭代码审阅认定。

#### Scenario: mock 源加载
- **WHEN** `data_source="mock"`
- **THEN** 系统从本地 mock 夹具目录读取各表 CSV

#### Scenario: u9c 源未就绪
- **WHEN** `data_source="u9c"` 且未注入连接器
- **THEN** 系统 SHALL 抛出 `RealEndpointNotReadyError`，不返回部分数据、不静默降级

#### Scenario: 既有驱动模式行为零变化
- **WHEN** 以与本次变更前完全相同的参数使用按单号或按供应商驱动
- **THEN** 返回结果与变更前逐行一致
