## ADDED Requirements

### Requirement: 三单四表统一接入

系统 SHALL 提供统一加载接口，分别加载 `po_lines`（PO 明细行）/ `grn`（入库单）/ `invoice`（发票）/ `payment`（付款凭证）四表，并按 `(po_no, line_no)` 关联 PO↔GRN↔Invoice、按 `inv_no` 关联 Invoice↔Payment。加载 MUST 不依赖具体数据源实现（mock/csv/u9c 对上层调用方透明）。

#### Scenario: 四表按锚点关联
- **WHEN** 传入 PO 明细行 + GRN + Invoice + Payment 四张表
- **THEN** 系统 SHALL 能沿 `(po_no, line_no)` 找出同一 PO 行对应的 GRN 行与 Invoice 行，并沿 `inv_no` 找出该 Invoice 对应的 Payment 记录

#### Scenario: 字段边界校验（Pydantic）
- **WHEN** 原始行数据缺少必填字段（如 `item_code` 为空、`qty`/`amount` 非数值）
- **THEN** 该行加载 SHALL 显式抛出校验错误，不得静默跳过或以默认值填充

### Requirement: 数据源三态切换（mock / csv / u9c）与 fail-loud

系统 SHALL 支持 `data_source` 参数在 `mock`（夹具）/ `csv`（应急桥接）/ `u9c`（直读，未就绪）三态间切换，切换 MUST 不改变匹配引擎与分类逻辑。`u9c` 源在端点未开放期间 MUST 以 `RealEndpointNotReadyError`（复用平台 `shared_tools.connector_errors`）fail-loud，不得静默回退到 mock 或 csv。

#### Scenario: mock 源加载
- **WHEN** `data_source="mock"`
- **THEN** 系统从本地 mock 夹具目录读取四表 CSV

#### Scenario: u9c 源未就绪
- **WHEN** `data_source="u9c"` 且 U9C 财务接口尚未开放
- **THEN** 系统 SHALL 抛出 `RealEndpointNotReadyError`，不返回部分数据、不静默降级

### Requirement: 缺字段/缺单据显式拒收

系统 SHALL 对完整性不足的数据（必填字段缺失、单据孤立无法关联锚点）显式标记退回，不得进入匹配引擎当作"正常齐套"处理。

#### Scenario: 发票缺少可关联的 PO 行
- **WHEN** Invoice 行的 `(po_no, line_no)` 在 `po_lines` 表中找不到对应记录
- **THEN** 该发票行 SHALL 被标记为待处理的孤立单据，不进入四维比对流程当作正常匹配对象
