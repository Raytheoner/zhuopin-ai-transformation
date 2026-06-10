## Why

SC8 交期承诺 MVP（内部闭环·门禁就绪）已合入 master 并归档（2026-06-10），但**只跑 mock、未对真实客户外发**。要让 SC8 真正对 OEM 客户（比亚迪/上汽/理想）自动通报交付承诺，必须完成"真实切换"：接真实 zp ERP BOM + 携客云 SRM 承诺交期、用真实数据过黄金基准、补平台底座切库前加固项，并逐条过《SC8 上线前置门禁》6 项检查表。本变更独立另起，避免 MVP 分支挂数周等 6/12 数据。

> **阻塞依赖**：① U9C MCP（7/1 申请）/ 真实 BOM 数据；② 6/12 全量物料清单与真实订单到位；③ 携客云 SRM 真实承诺交期。数据到位前本变更只做加固项（不依赖真实数据的部分），真实切换待数据到位执行。

## What Changes

- **真实连接器接入**：SC8 `loaders`/`pipeline` 从 mock 夹具切换到平台 `ZpConnector`（U9C ERP BOM）+ `XkySrmConnector`（携客云 SRM 承诺交期）；委外识别从维护清单切换到 U9C 工艺路线 `Operations[].IsSubContract`（实现 `is_outsourced_by_routing` 喂入路径）。
- **平台底座切库前加固（加固清单 P2，本变更前置）**：
  - 连接器输入/输出边界 **Pydantic 强 Schema 校验**（挡 U9C/SRM 改字段或脏数据）。
  - 携客云 SRM **限流退避**（30s 重复限制、查询跨度≤60天、错误码 `900301`）：令牌桶 + 退避。
  - **凭证管理**：生产对接 Vault / K8s Secrets 动态注入，不在 `.env` 明文存生产密钥。
  - 审计 **hash-chaining**（每条含上条哈希，防篡改可检测）。
- **真实数据黄金基准**：采购经理/PMC 取 5–10 张真实订单（覆盖有反馈/无反馈/含委外三类），手工核对，与 SC8 输出确定性逻辑**零偏差**；沉淀替换 mock 样本。
- **委外维护清单填真实料号**（U9C 工艺路线接通前的过渡口径）。
- **内部企微通道验证**：先推内部群验证，再切真实客户。
- **过《SC8 上线前置门禁》6 项检查表** → 全勾选后才开真实客户自动外发。

## Capabilities

### Modified Capabilities
<!-- 复用 delivery-date-forecast / delivery-commitment-gate（已上线）；本变更不改需求契约，
     仅把数据源从 mock 切真实 + 补切库前加固，行为受门禁约束。 -->

## Impact

- **平台底座加固**：`shared_tools` 连接器边界校验/限流/凭证；`audit` hash-chain（P2 项）。
- **SC8 工程**：`loaders`/`pipeline`/`config.is_outsourced` 切真实源，黄金基准回填真实样本。
- **合规红线**：真实客户外发须先过门禁 6 项；先内部企微验证再切真实；所有 AI 决策写 audit。
- **状态**：**BLOCKED until 6/12 数据到位 + U9C MCP**；加固项可先行。
