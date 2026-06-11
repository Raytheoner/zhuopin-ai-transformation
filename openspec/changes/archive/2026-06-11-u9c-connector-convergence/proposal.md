## Why

U9C 外网 webapi 探活（2026-06-11）发现：BOM 已由 `ZpConnector`（`erp_connector` 包）经 `/U9C/webapi/BOM/Query` **实拉、SC8 在用**；而 `U9CConnector`（`u9c_connector` 包）是**零场景消费方的纯骨架**（5 个 `get_*` 全 CSV 回退、鉴权 docstring 写的是过时的 RSA+admin 密码流程）。两者在 **BOM** 上打同一端点 → 再实现 `U9CConnector.get_bom` 是同端点重复，**违反单一可信源**（IATF）。本变更收敛连接器：确立 ZpConnector 为 U9C/ERP 唯一规范连接器，退役 U9CConnector。

收敛设计与方案对比见 `5-平台底座/连接器收敛设计-ZpConnector与U9CConnector.md`（Paul 已审，四点拍板采纳方案 A）。

> **外网现实**：外网网关只暴露 `/webapi/OAuth2/AuthLogin` + `/webapi/BOM/Query`；`/webapi/CommonEntity/Query` 与专用服务**外网 404**。故本轮真实化范围 = **仅 BOM**；其余实体类查询留 TODO（解锁条件：IT 外网开放 CommonEntity + 专用端点，或走 LAN/VPN）。

## What Changes

- **确立唯一规范连接器**：`ZpConnector`（`erp_connector` 包）为 U9C/ERP 唯一规范连接器；类注释讲清其职责边界（前置 zp-REST `/zp/api/*` + U9C 标准 webapi `/U9C/webapi/*`、OAuth2、BOM）。
- **删除 U9CConnector**：删 `u9c_connector` 包（连接器 + `__init__`）+ `test_u9c_connector.py`（4 骨架测试）。删前 grep 确认零场景 import。其 U9C 实体名映射（BOM/库存 WhQoh/PO+Receivement/MO/价格 IQueryPurPriceListSRV 的 EntityFullName + 字段）**已抢救**进收敛设计 md 附录 A。
- **`U9C_DATA_SOURCE=mock|real` 开关 + CSV mock 回退**（同 `SC8_DATA_SOURCE` 模式）：`real` 走 ZpConnector 真实 webapi，`mock` 走 CSV 回退；审计来源从骨架的 `U9C_CSV回退` 改为**如实标真实源**（`zp_ERP` / `U9C_webapi`）。
- **BOM 单一来源** = `ZpConnector.get_bom_for_products`（`/U9C/webapi/BOM/Query`，外网已验证）。
- **CommonEntity 类方法留 TODO + 解锁条件**：`get_inventory`(WhQoh) / `get_purchase_orders`(PO+Receivement) / `get_production_plan`(MO) / `get_suppliers`(IQueryPurPriceListSRV) 本轮**不实现**（外网 404）。
- **`.env` 约定修正**：`U9C_API_BASE` = **host-only**（`https://erp.equalitytec.com:4443`，不带 `/U9C`）—— ZpConnector 自拼 `/U9C` 与 `/zp`，带 `/U9C` 会 404。鉴权 = OAuth2(client_id/secret)，**不需要 `U9C_API_PASSWORD`**。

## Capabilities

### Modified Capabilities
<!-- platform-data-connectors：收敛 ERP/U9C 连接器为单一规范实现，退役重复骨架，
     补 U9C_DATA_SOURCE 开关与如实数据源审计；BOM 单一来源；CommonEntity 留解锁条件。 -->

## Impact

- **平台底座**：删 `shared_tools/u9c_connector/`；`erp_connector/ZpConnector` 加 `U9C_DATA_SOURCE` 开关 + 文档；审计来源标真实源。
- **测试**：删 `test_u9c_connector.py`（4）；ZpConnector 既有测试不退化；新增数据源开关测试。
- **SC8**：**零改动**（已用 ZpConnector；PR #8 不受影响）。
- **配置**：`.env` `U9C_API_BASE` 用 host-only；凭据只进 `.env`（gitignored），OAuth2 无需 admin 密码。
- **不做（本轮）**：CommonEntity 实体方法真实实现（外网 404，留 TODO）；类改名 `ErpConnector`（低峰期单独 PR）；DB 直连（LAN/VPN 备选）。
- **红线**：只读、凭据不进 git、保留 mock 回退、审计如实标源。
