## Why

平台底座 `zhuopin_platform/shared_tools/` 目前是空占位（仅 `__init__.py`），而 supplychain 已用真实数据验证过一整套数据层/通知层连接器（zp ERP 2.4 万 PO、携客云 SRM 承诺交期、CRM/企微通报，267 测试全绿）。继续两套并行会造成重复维护与跨工程引用痛点；正确动作是把 supplychain 已验证的真连接器**收割**进平台底座，作为后续 SC1/SC8/SC3/SC5 等全部采购+运营场景的单一可信数据/通知基座。现在做，是因为 7 月 SC1 上线与 SC8 收割式 MVP 都要 import 这套基座。

## What Changes

- 把 supplychain 真连接器**填入** `zhuopin_platform/shared_tools/`（此前为空占位，非替换已有实现）：
  - `data/connector.py` + `csv_connector.py` → DataConnector 抽象 + CSV 回退（Provider 模式）
  - `data/xky_srm_connector.py` → 携客云 SRM 只读（承诺交期 vExpectedDate）
  - `data/zp_connector.py` → 卓品 zp REST API（真实 ERP：PO/物料）
  - `data/u9c_connector.py` → U9C 骨架（CSV 回退，待 7/1 MCP 接口补真实）
  - `crm_notifier.py` → CRM 延期通知草稿生成
  - `notifiers/wecom.py` → 企业微信推送
- **对接已有 audit 骨架**：所有连接器/通知器的数据访问与 AI 决策通过 `zhuopin_platform.audit.AuditLogger` 统一留痕（JSONL append-only，3 年）。**不重建** audit。
- **预留 OEM 隔离接口**：在平台层保留 `data_isolation_layer` 接入点供后续研发/知识库场景使用；**采购连接器不强加 OEM 路由**（SRM/ERP/CRM 供应商数据不属 OEM 技术数据隔离范围）。**不重建** router。
- 收割迁移采用脱敏/mock 优先：用 supplychain 现有测试夹具验证逻辑，本次**不连真实库**。
- 不在本次范围：业务智能体（delivery_forecast/kit_analysis/supplier_tracking 等）、ClickHouse sink、RAG/Chroma 接入、SC1 场景改造 import（后续变更）。

## Capabilities

### New Capabilities
- `platform-data-connectors`: 平台共享数据连接器——DataConnector 抽象 + CSV 回退、携客云 SRM、zp ERP、U9C 骨架；统一审计留痕、脱敏/mock 优先、采购数据不加 OEM 路由（仅预留隔离接口）。
- `platform-notification-channels`: 平台共享通知通道——CRM 延期通报草稿、企业微信推送；推客户/外发前置 L2 人工门禁、动作留痕。

### Modified Capabilities
<!-- 无既有 spec 的需求变更：audit 与 data_isolation_layer 为已写骨架，本次仅对接、不改其需求契约。 -->

## Impact

- **新增代码**：`zhuopin_platform/shared_tools/{connector.py, csv_connector.py, srm_connector/, erp_connector/, u9c_connector/, crm_notifier/, notifiers/}`。
- **依赖**：`requests`（已在 pyproject）、`python-dotenv`（凭据从环境/.env 读，不入库）；连接器凭据通过环境变量注入。
- **对接已有**：`zhuopin_platform.audit`（AuditLogger/AuditEvent）、`zhuopin_platform.data_isolation_layer`（OEMRouter，预留不强用）。
- **测试**：迁入 supplychain 对应测试夹具到 `zhuopin_platform/tests/`，全程 mock，不触真实 SRM/ERP/CRM/企微端点。
- **源仓库**：supplychain 为收割来源，本次后续打 tag 转只读存档（不在本变更内执行）。
- **合规**：满足 IATF 审计留痕、ISO 26262 不直接合入安全相关代码（本批均为数据/通知工具，非安全相关）。
