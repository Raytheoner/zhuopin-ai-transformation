# fi2-feed-source Specification

## Purpose
TBD - synced from change fi2-recon-mvp (change remains active, not yet archived). Update Purpose after archive.

## Requirements

> **v3 口径修正（2026-07-09，design D10/D11）**：核对对象改 AP 单 vs INV，新增 `ap_lines`（应付单明细行）表；发票改挂载 `ap_no`（U9C 应付单附件语义，不再挂 `(po_no, line_no)`）；`po_lines`/`grn` 保留加载（PO 作 AP-PO 单价前置参照，GR 本次匹配数学暂不消费）。

### Requirement: 三单五表统一接入

系统 SHALL 提供统一加载接口，分别加载 `po_lines`（PO 明细行）/ `grn`（入库单）/ `ap_lines`（应付单明细行）/ `invoice`（发票）/ `payment`（付款凭证）五表，并按 `(po_no, line_no)` 关联 AP↔PO（价格前置参照）、按 `ap_no` 关联 AP↔Invoice、按 `inv_no` 关联 Invoice↔Payment。加载 MUST 不依赖具体数据源实现（mock/csv/u9c 对上层调用方透明）。

#### Scenario: 表间按锚点关联
- **WHEN** 传入 PO 明细行 + GRN + AP 明细行 + Invoice + Payment 五张表
- **THEN** 系统 SHALL 能沿 `(po_no, line_no)` 找出 AP 行对应的前置 PO 行，沿 `ap_no` 找出该 AP 单对应的 Invoice 行，并沿 `inv_no` 找出该 Invoice 对应的 Payment 记录

#### Scenario: 字段边界校验（Pydantic）
- **WHEN** 原始行数据缺少必填字段（如 `item_code` 为空、`qty`/`untaxed_amount` 非数值）
- **THEN** 该行加载 SHALL 显式抛出校验错误，不得静默跳过或以默认值填充

### Requirement: 数据源三态切换（mock / csv / u9c）与 fail-loud

系统 SHALL 支持 `data_source` 参数在 `mock`（夹具）/ `csv`（应急桥接）/ `u9c`（直读，未就绪）三态间切换，切换 MUST 不改变匹配引擎与分类逻辑。`u9c` 源在端点未开放期间 MUST 以 `RealEndpointNotReadyError`（复用平台 `shared_tools.connector_errors`）fail-loud，不得静默回退到 mock 或 csv。

#### Scenario: mock 源加载
- **WHEN** `data_source="mock"`
- **THEN** 系统从本地 mock 夹具目录读取四表 CSV

#### Scenario: u9c 源未就绪
- **WHEN** `data_source="u9c"` 且 U9C 财务接口尚未开放
- **THEN** 系统 SHALL 抛出 `RealEndpointNotReadyError`，不返回部分数据、不静默降级

### Requirement: u9c 源发票加载——人工誊录小样例外路径（D19，2026-08-03）

系统在 `data_source="u9c"` 下 MAY 接受一个可选的人工誊录发票小样目录；调用方显式提供该目录时，`load_invoice()` SHALL 改为从该目录读取并按既有 `_InvoiceRow` 边界校验解析，不再对该次调用 fail-loud；调用方未提供该参数（默认）时，`load_invoice()` MUST 维持原有 fail-loud 行为（`RealEndpointNotReadyError`），不得静默变化。本例外路径 MUST NOT 影响 `load_po_lines`/`load_grn`/`load_ap_lines`/`load_payment` 四个 loader 的既有行为。

#### Scenario: 已提供人工誊录小样目录
- **WHEN** `data_source="u9c"` 且调用方显式提供了人工誊录发票小样目录（该目录含符合既有 schema 的 `invoice.csv`）
- **THEN** `load_invoice()` SHALL 从该目录读取并解析，不抛 `RealEndpointNotReadyError`

#### Scenario: 未提供人工誊录小样目录（默认）
- **WHEN** `data_source="u9c"` 且调用方未提供该参数
- **THEN** `load_invoice()` MUST 维持现状 fail-loud，行为与本次变更前完全一致

### Requirement: 缺字段/缺单据显式拒收

系统 SHALL 对完整性不足的数据（必填字段缺失、单据孤立无法关联锚点）显式标记退回，不得进入匹配引擎当作"正常齐套"处理。

#### Scenario: 发票缺少可关联的 AP 单
- **WHEN** Invoice 行挂载的 `ap_no` 在 `ap_lines` 表中找不到对应记录
- **THEN** 该发票行 SHALL 被标记为待处理的孤立单据，不进入料品汇总归集流程当作正常匹配对象
