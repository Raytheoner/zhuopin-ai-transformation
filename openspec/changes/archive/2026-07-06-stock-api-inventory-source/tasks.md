# stock-api-inventory-source Tasks

## 1. Stock API 库存取数（平台连接器）

- [x] 1.1 定义白名单仓常量 `ALLOWED_STOCK_WAREHOUSES = ("WW01","ZP01","ZP21","ZP22","ZP02","ZP23")`（含中文名注释 + Paul 2026-07-05 决策来源）
- [x] 1.2 新增 `_StockRow` Pydantic 边界模型（`ItemCode/ItemName/WhName/SupplierName/ProjectCode/StoreQty/AvailQty`）
- [x] 1.3 实现 `_stock_query(item_code, wh_codes)`：`GET /zp/api/Stock/Query`，apiKey 走 query、报错用不含 apiKey 的 safe_url、解析 `Data.Rows`
- [x] 1.4 实现 `get_inventory(material_ids)`：逐料号并发（ThreadPoolExecutor）→ 按 `ItemCode` 精确匹配 → 跨白名单仓聚合 `AvailQty`→`current_stock`、`safety_stock=0`
- [x] 1.5 base/key 从 env（`STOCK_API_BASE`/`STOCK_API_KEY`）；缺失且 real → fail-loud，mock 走 CSV 夹具回退
- [x] 1.6 每次取数写平台 `audit` 轻量痕迹（source=Stock，不含 apiKey）

## 2. 单元测试（夹具/mock，不触网）

- [x] 2.1 精确匹配剔模糊他料；2.2 跨白名单仓聚合、非白名单仓排除；2.3 real fail-loud；2.4 apiKey 脱敏；2.5 Success=false 抛错；+ 旧无参接口向后兼容（8 测试全绿）

## 3. 测试库真实联调（只读，192.168.100.49，未碰生产）

- [x] 3.1/3.2 真实 `get_inventory(["R01A.0012",…])` 白名单6仓聚合可用量 = 直连 API 实测值（R01A.0012=3,153,195 等，逐一一致）
- [x] 3.3 不良品仓/委外线边仓确被排除；假料号无库存行

## 4. SC8 保供看板现货净额接入（默认关，零漂移）

- [x] 4.1 `sc8/config.py` `net_inventory_enabled()`（`SC8_NET_INVENTORY`，默认 OFF）
- [x] 4.2 `baoguan.assess_supply_risk`/`build_dashboard` 增可选 `inventory`；OFF/空 → 与现状完全一致（零漂移测试通过）
- [x] 4.3 ON 时现货可用量≥毛需求的直接子件退出待催/瓶颈；全覆盖→🟢现货齐备；不足→仍待催（4 测试全绿）
- [x] 4.4 `baoguan_service.compute_snapshot` 在 flag ON 时经 `get_inventory` 备 inventory 注入（OFF 不影响输出）

## 5. 回归与收口

- [x] 5.1 全回归：平台 146 / O2 20 / SC5 41（黄金 35850/640000/675850 不漂移）/ SC8 114 全绿；保供黄金 flag OFF 零漂移
- [x] 5.2 `openspec validate stock-api-inventory-source` 通过
- [x] 5.3 更新 `.env.example`（STOCK_API_BASE/STOCK_API_KEY）、`7-外部文档/U9C库存取数-侦察结果与推荐-2026-07-05.md`（标"已落地"）、连接器 docstring
- [x] 5.4 `git commit`（branch feat/stock-api-inventory-source, 6e99b61；apiKey/reports 不入库）；archive
