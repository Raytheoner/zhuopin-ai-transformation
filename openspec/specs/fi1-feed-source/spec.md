# fi1-feed-source Specification

## Purpose
TBD - synced from change fi1-warehouse-reconcile (change remains active, not yet archived; §1 前置收口项与真实数据验证仍未定稿，见 tasks.md). Update Purpose after archive.

## Requirements

### Requirement: BOM 理论用量加载（复用 ZpConnector）

系统 SHALL 通过平台 `ZpConnector.get_bom_for_products(product_ids, max_depth)` 加载指定成品的直接子件 BOM，消费其 `(rows, failed_ids)` 二元组；每个 `BomRow` 提供 `qty_per_unit`（`m_usageQty`）与 `loss_rate`（`m_scrap`）。系统 MUST NOT 自建第二套 BOM 读路径（单一可信源 = ZpConnector）。

#### Scenario: 成功加载子件 BOM
- **WHEN** 给定一组对账期成品料号
- **THEN** 返回每个成品的直接子件清单，含 `component_id` / `qty_per_unit` / `loss_rate` / `unit`

#### Scenario: BOM 部分拉取失败不静默通过
- **WHEN** `get_bom_for_products` 返回的 `failed_ids` 非空
- **THEN** 对应成品/子件在对账中标记"BOM 残缺·待人工核"，不按残缺 BOM 计算理论用量而当成功
- **AND** 该残缺事实写入审计痕迹

### Requirement: 投料/产出加载（三源统一接口：mock / CSV 应急 / U9C 直读）

系统 SHALL 提供投料与产出数据的统一加载接口，对"产出数量 / 实际投料数量"做统一记录抽象，背后由 `data_source` 切三个 loader，**切源 MUST NOT 改变下游对账引擎与门禁逻辑**：
- `mock`（默认）：读贴 U9C 实体 schema 的夹具，供单测/回归。
- `csv`（过渡期真实路径）：从 ERP 定期导出的投料/产出 CSV 加载，字段贴 U9C `MO.FinishedQty`/`MOPickList` 语义，Pydantic 边界校验。
- `u9c`（最终目标）：取 U9C MO 实体 `UFIDA.U9.MO.MO.MO`（`FinishedQty`）+ 领料 `MOPickList`（或经收口-4 确认的权威投料源），经 `CommonEntity/Query`；端点不可达时 MUST fail-loud 抛 `RealEndpointNotReadyError`，MUST NOT 静默回退 mock/csv。

#### Scenario: 开发期 mock 加载
- **WHEN** `data_source=mock`
- **THEN** 从贴 U9C 实体 schema 的夹具加载产出（`FinishedQty`）与实际投料数量，供对账引擎消费

#### Scenario: 过渡期 CSV 应急桥接加载真实数据
- **WHEN** `data_source=csv` 且提供 ERP 导出的投料/产出 CSV
- **THEN** 按贴 U9C 语义的字段加载真实产出/投料，经 Pydantic 边界校验后供对账引擎消费

#### Scenario: u9c 直读端点未开放 fail-loud
- **WHEN** `data_source=u9c` 且 U9C MO/领料 `CommonEntity/Query` 端点不可达（当前外网 404）
- **THEN** 抛 `RealEndpointNotReadyError`，不返回空、不回退 mock/csv、不产出对账结论

#### Scenario: 端点开放后切 u9c 直读零改对账逻辑
- **WHEN** IT 开放 MO/领料 webapi 端点（或经 LAN/VPN）后 `data_source=u9c`
- **THEN** 加载层返回真实产出/投料，下游对账引擎与门禁逻辑零改即可消费

### Requirement: 数据边界校验

系统 SHALL 对加载的投料/产出原始行做 Pydantic 边界校验，缺关键字段（料号/数量/工单号）或类型不符时显式报错，脏数据不进对账下游。

#### Scenario: 脏数据挡在接入层
- **WHEN** 投料/产出原始行缺料号或数量字段、或类型非法
- **THEN** 抛校验错误，明确指出违例字段，不把脏数据传入对账引擎
