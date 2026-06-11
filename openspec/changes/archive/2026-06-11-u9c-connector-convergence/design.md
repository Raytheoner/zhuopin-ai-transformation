# Design — U9C 连接器收敛（u9c-connector-convergence）

> 审阅对象：Paul。收敛设计四点已审过拍板（采纳方案 A）；本文是 openspec 化的实现设计。
> 背景/方案对比见 `5-平台底座/连接器收敛设计-ZpConnector与U9CConnector.md`（含 U9C 实体映射附录 A）。

## Context

- 同一台 ERP（`erp.equalitytec.com:4443`）两个 API 面：U9C 标准 webapi `/U9C/webapi/*`（权威）+ 卓品自建 REST `/zp/api/*`（视图层）。
- `ZpConnector`（`erp_connector` 包）**真实在用**：OAuth2 `/U9C/webapi/OAuth2/AuthLogin`→JWT→header `token`、`/U9C/webapi/BOM/Query`、`/zp/api/ZpViewXxx/Query`。消费方 = SC8 + 3 测试。
- `U9CConnector`（`u9c_connector` 包）= 纯骨架，5 个 `get_*` 全 CSV 回退，鉴权 docstring 过时（RSA），**零场景消费方**（仅 `test_u9c_connector.py` 4 测试 import）。
- 外网探活：鉴权 = OAuth2(client_id/secret，无需 admin 密码)；外网只开 `AuthLogin`+`BOM/Query`，`CommonEntity/Query` 404。

## Goals / Non-Goals

**Goals:**
- ZpConnector = U9C/ERP 唯一规范连接器（单一可信源），文档讲清职责边界。
- 删 U9CConnector 骨架 + 测试（实体映射已抢救进收敛 md 附录 A）。
- `U9C_DATA_SOURCE` 开关 + CSV mock 回退；审计如实标真实源。
- BOM 真实路径（`get_bom_for_products`）整定为唯一来源，外网集成测试。

**Non-Goals:**
- 不实现 CommonEntity 类方法（库存/PO/MO/价格）——外网 404，留 TODO + 解锁条件。
- 不改类名为 `ErpConnector`（低峰期单独 PR）。
- 不做 DB 直连（192.168.6.2 / airead，LAN/VPN 备选）。
- 不碰 SC8（已用 ZpConnector，零改动）。

## Decisions

### ⭐ D1. ZpConnector 为唯一规范连接器，删除 U9CConnector  〔已拍板·方案 A〕
- ZpConnector 已含 OAuth + BOM/Query（真实验证）+ zp 视图；U9CConnector 零消费方、鉴权错。
- 删 `u9c_connector/`（connector + `__init__`）+ `test_u9c_connector.py`。**删前 grep 确认零场景 import**（现仅该测试 + 包 `__init__` 引用）。
- U9CConnector 直接删（不留别名）—— 零消费方，别名无收益。
- 收敛 md 附录 A 已保全 U9C 实体名映射 → ZpConnector 未来 CommonEntity TODO 的输入。

### ⭐ D2. `U9C_DATA_SOURCE` 开关 + **real 模式 fail-loud（默认）** 〔Q3 已拍板〕
- `U9C_DATA_SOURCE=mock|real`（默认 mock）。
- **mock 模式**：无真实端点的方法（生产计划；`get_bom()` 无 id 兜底）走 CSV 回退，审计标 `CSV_mock`。
- **real 模式 fail-loud（默认）**：无真实端点的方法 → **显式抛 `RealEndpointNotReadyError`「真实端点未就绪」，绝不静默回退 CSV**。理由：静默 mock 混进 real 决策是合规+正确性双重风险（SC8 对客尤忌）。
- **过渡期显式 opt-in 回退**（非默认，需主动开 `allow_mock_fallback`/`U9C_ALLOW_MOCK_FALLBACK`）：允许 CSV，但**必须**①审计标 `CSV_mock` ②结果标「非权威/mock」③**禁止进入任何对客/L2 决策路径**。
- **有真实端点的方法**（`get_bom_for_products` BOM、`get_purchase_orders`/`get_inventory`/`get_suppliers` zp 视图）：照常走真实，不受影响（SC8 只用 `get_bom_for_products`，全程真实）。
- 审计来源：删骨架 `U9C_CSV回退`；BOM(U9C webapi)→`U9C_webapi`、zp 视图→`zp_ERP`、回退→`CSV_mock`（Q1 按实际端点分别标）。

### ⭐ D3. BOM 单一来源 = `ZpConnector.get_bom_for_products`（`/U9C/webapi/BOM/Query`）
- 外网已验证（母件 S02Y.0162 → 真实直接子件）。SC8 `sources.load_real_bom` 已调用它，零改动。
- 不再有第二处 BOM 实现（U9CConnector.get_bom 计划取消）。

### D4. CommonEntity 类方法留 TODO + 解锁条件（外网 404）
- `get_inventory`(WhQoh `IQueryBinAvailableQty`) / `get_purchase_orders`(PO `UFIDA.U9.PM.PO.PurchaseOrder` + Receivement join) / `get_production_plan`(MO `UFIDA.U9.MO.MO.MO`) / `get_suppliers`(`IQueryPurPriceListSRV`)。
- 本轮 ZpConnector 这些方法维持现状（zp 视图或 CSV 回退），加 TODO 注释 + 解锁条件引用附录 A。
- 解锁条件：IT 在外网反代开放 `CommonEntity/Query` + 专用端点，或走 LAN/VPN。

### D5. `.env` 约定：`U9C_API_BASE` host-only
- ZpConnector 自拼 `/U9C`、`/zp` → base 必须 host-only（`https://erp.equalitytec.com:4443`）。带 `/U9C` 会 `/U9C/U9C/...` 404。
- 鉴权 OAuth2，不需要 `U9C_API_PASSWORD`；`.env.example` 只列变量名不放值。

## Risks / Trade-offs

- **[误删有用骨架]** → 缓解：实体映射已抢救进收敛 md 附录 A；删前 grep 零 import 双确认；U9CConnector 从无真实实现，删的是占位。
- **[ZpConnector 名义含糊]**（它也打 U9C webapi）→ 缓解：本轮文档澄清；改名 `ErpConnector` 留待低峰期单独 PR（已记待办）。
- **[外网范围受限]** 只 BOM 可真实 → 缓解：明确 Non-Goal + TODO 解锁条件；不在外网硬试 CommonEntity。
- **[开关回退]** real 异常 → `U9C_DATA_SOURCE=mock` 一键回退，mock 黄金/回归不退化。

## Migration Plan

1. grep 复核 `U9CConnector` 零场景 import（仅测试 + 包 `__init__`）。
2. 删 `shared_tools/u9c_connector/`（connector.py + `__init__.py`）+ `tests/test_u9c_connector.py`。
3. ZpConnector：加 `U9C_DATA_SOURCE` 开关支持 + 类/方法文档澄清职责边界 + CommonEntity 方法 TODO/解锁条件注释 + 审计来源标真实源。
4. 先写测试后实现：数据源开关单测（mock/real 选择、审计标源）+ 外网 BOM 真实集成测试（默认跳过，凭据下跑）+ ZpConnector 既有测试回归不退化。
5. `.env.example` 补 `U9C_API_BASE`(host-only) 等变量名（不放值）；确认 `.env` gitignored。
6. archive → 开 PR，停下等 Paul 审，先不合 master。
- **回滚**：删除是平台底座内变更，ZpConnector 行为对 SC8 不变（BOM 同方法）；`U9C_DATA_SOURCE=mock` 可回退真实路径。

## Open Questions（均已拍板 2026-06-11）

1. **审计来源命名** → ✅ **按实际端点分别标**：BOM→`U9C_webapi`、zp 视图→`zp_ERP`、回退→`CSV_mock`，不混一个。
2. **`.env.example` 纳入本变更** → ✅ **纳入**：补 U9C 变量名注释（只名字、不放值），明确 host-only 约定。
3. **real 模式无真实端点的方法** → ✅ **fail-loud 为默认**：显式报「真实端点未就绪」，不静默回退 CSV（静默 mock 进 real 决策 = 合规+正确性风险）。CSV 回退仅留给 `mock` 模式；过渡期允许**显式 opt-in** 回退，但须审计 `CSV_mock` + 标「非权威/mock」+ **禁入对客/L2 决策路径**。（见 D2）
