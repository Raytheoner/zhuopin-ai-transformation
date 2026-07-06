# stock-api-inventory-source Design

## Context

`ZpConnector.get_inventory`（`shared_tools/erp_connector/connector.py:404`）现为桩：读 `ZpViewItemMaster` 物料主档，`current_stock`/`safety_stock` 恒 0（zp webapi 无库存余量端点）。用友标准 `Invtrans/QueryQohAndAvailable` 有原厂 SQL bug、`CommonEntity/Query` 404、`ItemQty` SOAP 取不到数——三条已排除。IT 2026-07-05 在 `/zp` 面交付库存查询 `GET /zp/api/Stock/Query`（与 SC8 已用的 FO 接口同范式），测试库 192.168.100.49:6666 验收：分仓 `StoreQty` 与 DB `InvTrans_WhQoh` 现存量逐一精确一致。消费方：`kit_engine.calc_shortage`（O2/SC5 已收 `InventoryRow`）+ SC8 保供看板（`baoguan.assess_supply_risk` 目前**无库存入参**）。

## Goals / Non-Goals

**Goals:**
- `get_inventory` real 模式经 Stock API 取真实现货，六仓白名单口径，替换恒零桩。
- SC8 保供看板具备"现货净额"能力消除 P0 误判，但**默认关、零黄金漂移**，翻开需专员签字。
- 全回归不漂移（平台/O2/SC5/SC8，SC5 黄金 35850/640000/675850）。

**Non-Goals:**
- 不把 O2/SC5 从 mock 切真实（9 月场景，保持 mock 夹具；仅确保 real 路可用）。
- 不翻开 SC8 `SC8_NET_INVENTORY`（本包只交付代码+默认关；翻开是后续+专员黄金重核）。
- 不接生产（本包联调测试库；生产 base/key 属晋档 3 前置）。
- 不碰对客闸、不改 L2 门禁、不动 SOAP/DB 直连（已排除）。

## Decisions

- **D1 取数落点 = 扩展 ZpConnector，不另起类。** `get_inventory` 内改走 Stock API（`/zp` apiKey 面，独立于 U9C OAuth）。理由：单一规范连接器（连接器收敛方案 A），复用 FO loader 已验证的 apiKey/`Data.Rows`/脱敏 URL 范式；避免第二个 ERP 入口脱离审计。备选（新 StockConnector）被否：增入口、破单一可信源。
- **D2 查询策略 = 逐料号 + 精确匹配 + 跨白名单仓聚合，并发。** 因 `itemCode` 模糊、不支持逗号多值、`limit≤1000` 实测无分页（page/pageSize/offset 被忽略，整仓拉取截断于 1000）。故 `get_inventory(material_ids)` 对每料 `GET ?itemCode=<code>&whCode=WW01,ZP01,ZP21,ZP22,ZP02,ZP23&limit=…`，响应按 `ItemCode==code` 精确过滤（剔模糊他料），跨返回仓求和 `StoreQty`/`AvailQty`。并发用既有 `ThreadPoolExecutor` 范式（同 PO 拉取）。备选（整仓一把拉本地索引）被否：>1000 行截断、无分页、拿不全。
- **D3 InventoryRow 映射。** `material_id=ItemCode`、`material_name=ItemName`、`current_stock=Σ StoreQty(白名单仓)`、`safety_stock=0`（Stock API 无安全库存；安全库存口径单列后续）。**可用量**：`AvailQty` 已由 ERP 服务端算好（净预留），为避免与 `calc_shortage` 的"现存−安全"口径双减，本包 `current_stock` 取 `AvailQty`（可用量）作为"可投产现货"，`safety_stock=0`——即让 ERP 的可用量口径作准（Paul 定"仓口径"、IT 封"可用量口径"）。`InventoryRow` 复用现模型，不加字段（保留 `StoreQty` 供审计/诊断可另存，不入 InventoryRow）。
- **D4 SC8 保供接入加开关。** `baoguan.assess_supply_risk`/`build_dashboard` 增可选 `inventory`（`dict[material_id]→可用量`）入参；`config.SC8_NET_INVENTORY`（默认 OFF）。OFF：入参不传/忽略，逻辑=现状（`estimate_material_arrivals` 不变），黄金零漂移。ON：某直接子件"白名单仓可用量 ≥ 其毛需求"→视为已齐、不进 `no_feedback`/待催/瓶颈。理由：P0 修复必须可回滚、且改保供四色须专员重核黄金，故 flag-gated。
- **D5 real fail-loud + apiKey 脱敏。** 沿用 FO loader：报错用不含 apiKey 的 `safe_url`；real 模式 Stock API 失败抛错，不回退 mock、不以 0 冒充。`U9C_DATA_SOURCE`/mock 时可用 CSV 夹具回退（供测试/O2/SC5）。
- **D6 白名单仓为显式常量。** `ALLOWED_STOCK_WAREHOUSES = ("WW01","ZP01","ZP21","ZP22","ZP02","ZP23")` 单处定义，注释标各仓中文名与 Paul 2026-07-05 决策来源。

## Risks / Trade-offs

- [逐料号 N 次调用，保供全量子件可能数百次] → 并发（8–16）+ 单料响应小（≤~20 行）；后续可请 IT 加 `itemCode` 逗号多值或分页做批量优化（记入 tasks 可选项）。
- [Stock API 无分页，未来若单料白名单仓>limit] → 单料跨 6 仓行数远小于 1000，无近期风险；整仓拉取已弃用。
- [`AvailQty` 作 current_stock 改变 calc_shortage 语义（原设计现存−安全）] → 安全库存本就无来源（恒 0），用 ERP 可用量更贴业务；黄金回归覆盖，SC5 值不漂移即证无副作用。
- [SC8 netting 翻开改保供四色] → 默认 OFF + 专员黄金重核签字门；本包不翻开。
- [测试库数据新鲜度/与生产差异] → 本包联调测试库、晋档 3 切生产 base/key 时复验。

## Migration Plan

1. 实现 `get_inventory` real（Stock API）+ 白名单/聚合/精确匹配/并发；单测（夹具，含模糊剔除、跨仓聚合、fail-loud、apiKey 脱敏）。
2. 测试库真实联调：查若干真实料号，对 DB 现存量校验一致（R01A.0012 等）。
3. SC8 `inventory` 入参 + `SC8_NET_INVENTORY`（默认 OFF）+ netting；OFF 路径全回归零漂移。
4. 全回归（平台/O2/SC5/SC8）绿、SC5 黄金不漂移 → 归档。
- **回滚**：`SC8_NET_INVENTORY` 保持 OFF 即等同接入前；`U9C_DATA_SOURCE=mock` 或不配 STOCK_* 时走夹具/桩。

## Open Questions

- 安全库存口径（是否从别处引入、是否从可用量再扣）——本包 `safety_stock=0`，待专员/PMC 定后另议。
- 批量优化（IT 是否加 `itemCode` 逗号多值/分页）——非阻塞，先逐料号并发。
- SC8 netting 翻开时间 + 保供黄金重核——依赖采购专员，属晋档 3、本包外。
