# 连接器收敛设计 — ZpConnector 与 U9CConnector（ERP/U9C 唯一规范连接器）

> 调研/设计，先于 openspec 提案。审阅对象：Paul。**待你拍板后**再 propose「连接器收敛 + U9C cutover」。
> 触发：U9C 外网探活（2026-06-11）发现 BOM 已由 ZpConnector 实拉、SC8 在用，再写 `U9CConnector.get_bom` 是同端点重复，违反单一可信源。

## 1. 现状：两个连接器各打什么

同一台 ERP 主机 `erp.equalitytec.com:4443`，**两个 API 面**：

| | **ZpConnector**（`shared_tools/erp_connector/`）| **U9CConnector**（`shared_tools/u9c_connector/`）|
|---|---|---|
| 状态 | ✅ **真实在用**（SC8 经 `from_env().get_bom_for_products` 拉真实 BOM）| 🔧 **纯骨架**：5 个 `get_*` 全 CSV 回退，无真实实现 |
| 鉴权 | ✅ OAuth2 `/U9C/webapi/OAuth2/AuthLogin` → JWT → header `token`（已验证可用）| ❌ docstring 写 RSA+admin 密码流程（**过时、与 IT 实测不符**）；`from_env` 还强制要 `U9C_API_PASSWORD` |
| 打的端点 | ① zp 自建 REST `/zp/api/ZpViewXxx/Query`（PO/物料/供应商）② U9C 标准 webapi `/U9C/webapi/BOM/Query`（BOM）| 占位 `/webapi/CommonEntity/Query`（实体查询，**外网 404**）|
| base 约定 | **host 不带 /U9C**（自拼 `/U9C` 和 `/zp`）| base **带 /U9C**（base + webapi_path）|
| 消费方 | SC8（`sources.load_real_bom`）+ 3 个测试 | **零场景消费方**，仅 `test_u9c_connector.py` 4 个骨架测试 |

**重叠点 = BOM**：ZpConnector.`get_bom_for_products` 与 U9CConnector 计划中的 `get_bom` 打的是**同一个** `/U9C/webapi/BOM/Query`。两边各写一份 = 单一可信源违例。

## 2. 根因

不是「两个系统」，是**一套 ERP（U9C）的两个 API 面**：U9C 标准 webapi（`/U9C/webapi/*`，权威）+ 卓品自建 REST 视图层（`/zp/api/*`，补标准 API 不便取的数据）。**命名错位**：`erp_connector` 里叫 `ZpConnector`、却也打 U9C 标准 webapi；`u9c_connector` 叫 `U9CConnector`、却从没真打过。名字没映射到 API 面。

外网探活补充的现实：外网网关**只暴露 `OAuth2/AuthLogin` + `BOM/Query`**；`CommonEntity/Query` 外网 **404**。所以 U9CConnector 设想的实体查询，本轮外网根本走不通。

## 3. 方案对比

**方案 A（推荐）：ZpConnector 即唯一规范 ERP 连接器，退役 U9CConnector 骨架。**
- BOM 单一来源 = `ZpConnector.get_bom_for_products`（SC8 已在用，**零改动**）。
- OAuth/transport 单一实现（ZpConnector 已有 `_get_token`）。
- CommonEntity 类实体方法（库存 WhQoh / PO+Receivement / MO / 价格表）→ IT 外网开放 CommonEntity 或走 LAN/VPN 后，**新增到 ZpConnector 内**（加 `_u9c_entity_query` helper），不另起类。
- U9CConnector（零消费方）→ 删除 or 降为 `DeprecationWarning` 薄别名；连带删/改 `test_u9c_connector.py`（4 骨架测试）。
- 命名收敛：本轮**保留 ZpConnector 名**（SC8+测试在用，改名爆炸面大），但在 docstring/类注释讲清「它是 U9C ERP 的唯一连接器，前置 zp-REST + U9C-webapi 两个面」。可选后续把类改名 `ErpConnector`（留 `ZpConnector = ErpConnector` 别名），低峰期再做。
- **代价**：最小。SC8 不动；只动 U9CConnector + 其测试。
- **缺点**：`Zp` 名义上仍含糊（已用注释缓解）。

**方案 B：U9CConnector 升为标准 webapi 规范连接器，ZpConnector 退到只管 zp-REST 视图。**
- 把 OAuth+BOM/Query 搬进 U9CConnector，ZpConnector 删 BOM。
- SC8 `sources.load_real_bom` 改指 U9CConnector → 触碰 SC8（PR #8 在审中，会冲突）。
- **代价**：大。要重写 U9CConnector 鉴权（现是错的 RSA）、迁 BOM、改 SC8、改多处测试；而 U9CConnector 主卖点（CommonEntity 实体查询）外网正好 404，本轮拿不到收益。
- **否决理由**：高改动、撞 SC8 PR、收益被外网 404 抵消。

## 4. 推荐方案 A 的落点（待 propose 实现）

1. **唯一规范连接器 = ZpConnector**（`erp_connector` 包）。文档明确其职责边界（zp-REST + U9C-webapi 两面、OAuth、BOM）。
2. **BOM 统一走** `ZpConnector.get_bom_for_products`（`/U9C/webapi/BOM/Query`）。U9CConnector 不再计划 BOM。
3. **CommonEntity 实体方法归属 ZpConnector**：本轮**不实现**（外网 404），留 TODO + 明确解锁条件（IT 开放外网 CommonEntity / 专用端点，或 LAN/VPN）。
4. **退役 U9CConnector**：删骨架类 + `u9c_connector/` 包 + 4 骨架测试；或保留薄别名发 `DeprecationWarning`（建议直接删，零消费方）。
5. **`U9C_DATA_SOURCE` 开关 + CSV mock 回退**（同 `SC8_DATA_SOURCE` 模式）：`real` 走 ZpConnector，`mock` 走 CSV；审计来源从 `U9C_CSV回退` 改标真实源（`U9C_webapi` / `zp_ERP`）。
6. **DB 直连**（192.168.6.2 / airead）= LAN/VPN 备选，本轮不实现。

## 5. 迁移影响（量化）

- **SC8**：零改动（已用 ZpConnector；PR #8 不受影响）。✅
- **退役 U9CConnector**：仅 `test_u9c_connector.py`（4 测试）+ `u9c_connector/__init__.py` 受影响；**无场景消费方**。低风险。
- **⚠️ .env base 约定修正（关键）**：ZpConnector 要 **host-only base**（自拼 `/U9C`、`/zp`）。所以本仓库 `.env` 的 `U9C_API_BASE` 应填 **`https://erp.equalitytec.com:4443`（不带 /U9C）**。
  （此前探活报告里说"base 带 /U9C"是 U9CConnector 骨架的约定；既然收敛到 ZpConnector，**带 /U9C 会变成 `/U9C/U9C/...` 404**。请按 host-only 填。）
- **可选改名** ZpConnector→ErpConnector：会触 SC8 `sources.py` + 4 测试的 import，建议**本轮不做**，低峰期单独小 PR。

## 6. 外网范围现实（记录进设计）

外网网关当前只暴露 `OAuth2/AuthLogin` + `BOM/Query`。**全量 U9C cutover**（库存 WhQoh / PO+Receivement / MO / 价格表，均走 CommonEntity 或专用端点）需要 IT 在外网反代上**开放 CommonEntity/Query + 对应专用端点**，或改走 LAN/VPN。**本轮（纯外网）不在外网硬试这些**——范围限定 BOM。

## 7. 待你拍板
1. 采纳**方案 A**（ZpConnector 唯一规范、退役 U9CConnector）？
2. U9CConnector **直接删** vs 留 `DeprecationWarning` 别名？（建议直接删，零消费方）
3. 本仓库 `.env` 的 `U9C_API_BASE` 按 **host-only**（不带 /U9C）填，认可？
4. 类改名 ErpConnector：本轮跳过、低峰期再做，认可？

拍板后我 `/opsx:propose` 写正式提案（连接器收敛 + `U9C_DATA_SOURCE` 开关 + CommonEntity 留 TODO/解锁条件），design 细化实现与测试。

---

## 附录 A — U9C 实体映射（抢救自 U9CConnector 骨架 + supplychain 字段映射表）

> 删 U9CConnector 前抢救：这些 `EntityFullName`/字段是后续在 ZpConnector 补 CommonEntity 方法的输入。
> 权威全表见（已归档）`supplychain/docs/U9C_API字段映射表.md`（含 18 项待 IT 确认）。
> **外网现状**：CommonEntity/Query + 专用服务**外网 404**，下列除 BOM 外均需 IT 外网开放或 LAN/VPN 才能实现。

| 模块（未来 `get_*`） | 端点 / EntityFullName | 关键 ReturnFields | 外网 |
|---|---|---|---|
| **BOM**（`get_bom`，本轮唯一实现）| `/webapi/BOM/Query`（专用，**非** CommonEntity）| `m_itemMaster`/`m_bOMComponents[].{m_itemMaster,m_usageQty,m_scrap,m_issueUOM,m_isPhantomPart}` | ✅ 可用 |
| BOM（CommonEntity 备选）| `UFIDA.U9.BM.BOM.BOM` | `ItemMaster.Code/Name`、`BOMComponents.ItemMaster.Code`、`.Level`⚠️、`.UsageQty`、`.Scrap`、`.IssueUOM.Code`、`DocStatus=生效` | ❌ 404 |
| **库存**（`get_inventory`）| 专用服务 `UFIDA.U9.ISV.InvTrans.WhQoh.IQueryBinAvailableQty`（**异于通用查询**）| `ItemMaster.Code/Name`、`Wh.m_code`/`BinCode`；安全/冻结/质检/批次⚠️待 IT | ❌ 404 |
| **采购 PO**（`get_purchase_orders`）| `UFIDA.U9.PM.PO.PurchaseOrder` + 二次查 `UFIDA.U9.PM.Rcv.Receivement`（按 `RcvLines.SrcDoc.SrcDocNo` join 求已收量）| PO：`DocNo`、`Supplier.Code`、`POLines.ItemInfo.ItemCode`、`POLines.PurQtyTU`、`POLines.RequireDeliverDate`⚠️、`DocStatus`；Rcv：`RcvLines.PurQtyTU`、`BusinessDate` | ❌ 404 |
| **生产工单**（`get_production_plan`）| `UFIDA.U9.MO.MO.MO`（+ 备料 `UFIDA.U9.MO.MO.MOPickList`）| `DocNo`、`ItemMaster.Code`、`PlanQty`⚠️、`FinishedQty`⚠️、`PlanStartDate/PlanEndDate`⚠️、`DocStatus`、`BOMVersion.Code` | ❌ 404 |
| **供应商价格**（`get_suppliers`）| 专用服务 `UFIDA.U9.ISV.PM.IQueryPurPriceListSRV` | `Supplier.Code`、`ItemMaster.Code`、`Price`⚠️、`MinOrderQty`⚠️、`MinPackageQty`⚠️、`LeadTime`⚠️、`IsApproved`⚠️ | ❌ 404 |

**通用查询模板**（CommonEntity/Query body）：`{PageSize, PageIndex, Orders, Filters:[{Field,Operator,Value,Logic}], EntityFullName, ReturnFields:[...]}`；鉴权 `GET /webapi/OAuth2/AuthLogin`（OAuth2，JWT 放 header `token`）。

> 注：⚠️ 标记的字段名/枚举值仍待 IT 确认（供应商价格/库存/生产计划字段、在途状态枚举、分页上限、token 有效期等共 18 项，见归档全表）。本轮只做 BOM，这些到「IT 外网开放 CommonEntity + 专用端点」或 LAN/VPN 阶段再逐个落实。
