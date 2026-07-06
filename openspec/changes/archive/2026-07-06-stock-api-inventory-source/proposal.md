# stock-api-inventory-source Proposal

## Why

缺料预警 / SC8 保供看板此前**读不到卓品现货**——`ZpConnector.get_inventory` 是桩、恒返回 `current_stock=0`，SC8 保供看板架构上**根本没有库存入参**，导致"库存充足、无订单无请购"的子件被误判为缺料 / 待催 / 追料（采购域 P0，动摇 AI 可信度）。用友标准 webapi 库存端点 `Invtrans/QueryQohAndAvailable` 有原厂 SQL bug（`IsProdCancel` 拼 SQL）不可用、ETA 不可控。Paul 2026-07-05 定路：走**卓品自建 REST `GET /zp/api/Stock/Query`**（apiKey，vendor-independent，与 SC8 现有 FO 接口同范式），已在测试库 192.168.100.49:6666 验收——分仓 `StoreQty` 与 DB `InvTrans_WhQoh` 现存量逐一精确一致。现在把它落成平台规范取数路，消除 P0 的数据根因。

## What Changes

- **新增库存实时取数**：`ZpConnector.get_inventory(material_ids)` 走 `/zp/api/Stock/Query`，替换恒 0 桩；apiKey 从 env 注入、脱敏不入日志/审计、接平台 `audit`、只读。
- **齐套可用仓口径（Paul 定）**：只计入 `whCode ∈ {WW01 委外仓, ZP01 物料仓, ZP21 半成品库, ZP22 委外半成品库, ZP02 成品库, ZP23 委外成品库}`，其余仓（不良品仓 / 委外线边仓等）一律排除；请求侧用 `whCode` 逗号多值过滤。
- **查询策略**：`itemCode` 模糊且不支持逗号多值、`limit≤1000` 且**实测无分页**（page/pageSize/offset 被忽略）——故**按 BOM 子件逐料号查询**（`itemCode`+`whCode` 六仓），响应按 `ItemCode` **精确匹配**过滤，跨允许仓聚合 `StoreQty`(现存)/`AvailQty`(可用) → `InventoryRow`；多料号并发查询。
- **消费方接入**：`kit_engine.calc_shortage`（O2/SC5）获得真实 `current_stock`；**SC8 保供看板新增 `inventory` 入参 + 现货净额逻辑**——现货净额≥毛需求的子件退出待催/催货（P0 修复）。
- **保供行为变更加开关（关键，防静默漂移）**：SC8 现货净额逻辑挂 `SC8_NET_INVENTORY` 开关，**默认 OFF = 现行为、零黄金漂移**；ON（改变保供四色）**须先由采购专员重核保供黄金基准 + 登记原因 + Paul/专员签字**方可翻开。
- `real` 模式 API 不可用 **fail-loud**（不静默回退 mock）。

## Capabilities

### New Capabilities
- `stock-inventory-source`: 卓品自建 `/zp/api/Stock/Query` 库存实时取数（六仓口径、逐料号查询+精确匹配+跨仓聚合、`StoreQty/AvailQty→InventoryRow`、apiKey 脱敏、real fail-loud、audit 留痕、只读）。

### Modified Capabilities
- `platform-data-connectors`: `get_inventory` 契约由"桩恒返回 current_stock=0"改为"real 模式经 Stock API 取真实现货 / 缺端点 fail-loud"。

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

1. **本流程哪些判断是人脑默会经验？**
   - "齐套可用现货算哪些仓" —— 曾在采购/PMC 脑中；**已由 Paul 2026-07-05 显性化为 6 仓白名单**（WW01/ZP01/ZP21/ZP22/ZP02/ZP23，排除不良品仓/委外线边仓）。
   - "可用量口径（现存减哪些占用）" —— 曾需 PMC 定；**现由 IT 在 Stock API 服务端封装为 `AvailQty` 直接返回**，口径下沉到 ERP、不再靠人脑。
   - "缺料判定阈值" = 净需求（毛需求 − 可用现货）> 0，规则明确。
2. **由谁显性化？** 采购 AI 专员（姚祖怡）+ backup（部门指定）为持有人；仓口径由 Paul 拍板存档（本 proposal + `7-外部文档/U9C库存取数-侦察结果与推荐-2026-07-05.md`）。登记进《跨场景前置数据与知识库任务总表》§一.2 知识资产台账。
3. **用什么方法提取？** ① 仓口径 / 可用量口径 = AI 起草·专家批改（Paul + 专员确认）；② 保供误判 = L2 改判判例累积（专员核对误判子件 → 校准判定）。

## 验收与晋档条件（强制，四档口径）

- **本变更包交付后场景所处档位**：**档 2（真实数据跑通，测试库）**——get_inventory 在测试库 192.168.100.49 真实取数、分仓对 DB 校验一致；SC8 netting 代码就位但默认 OFF。
- **晋下一档（档 3 内部服务）的条件**：① 生产 `STOCK_API_BASE` + 生产 apiKey 配置就位；② SC8 `SC8_NET_INVENTORY` 翻 ON 前，**采购专员重核保供黄金基准 + 登记原因 + 签字**（保供四色行为将改变）；③ 全回归不漂移（平台/O2/SC5/SC8，SC5 黄金值 35850/640000/675850）；④ 误判子件真实清零经专员确认。
- **价值指标（D-4 两级验收）**：**风险型**——缺料误判率↓（P0：库存充足却被追料的子件清零）；**工时型**——保供/缺料人工核对耗时↓。基线由采购 AI 专员（业务 Champion）启动前确认存档。
- **LLM 判据黄金集**：本场景为**确定性取数 + 计算**（无 LLM 运行时判断），不适用。

## Impact

- **specs**：新增 `stock-inventory-source`；修改 `platform-data-connectors`。
- **代码**：`zhuopin_platform/shared_tools/erp_connector/connector.py`（get_inventory 实现）、可能新增 `stock_loaders`/复用 FO loader 范式、`shared_tools/models.py`（InventoryRow 复用，可选加 available 字段）、SC8 `sc8/baoguan.py`+`forecast.py`（inventory 入参 + netting + flag）、`sc8/config.py`（SC8_NET_INVENTORY）；O2/SC5 real 取数为可选（默认仍 mock，9 月切）。
- **配置**：`.env.test`/`.env` 新增 `STOCK_API_BASE` / `STOCK_API_KEY`（gitignore，不入库）。
- **红线核对**：mock/测试库先行 ✓；每次判定写 audit ✓；apiKey 脱敏不入日志 ✓；OEM 隔离不适用采购/库存数据 ✓；L2 门禁不动 ✓；对客闸 `CUSTOMER_OUTBOUND_ENABLED` 全程 False ✓；ISO 26262 不适用（采购非安全相关代码）✓。
