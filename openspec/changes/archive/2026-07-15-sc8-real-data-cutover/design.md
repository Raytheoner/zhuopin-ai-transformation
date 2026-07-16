# Design — SC8 真实库切换（sc8-real-data-cutover）

> 审阅对象：Paul。本文是 6/11 提前开工的切换设计，承接 SC8 MVP（已归档 2026-06-10）。
> 请逐条拍板 D1–D6；标 ⭐ 的影响合规门禁/算法正确性。
> 背景见 proposal.md / tasks.md / 《SC8 真实库切换就绪检查清单》。**本文据 6/11 只读冒烟实测落定**。

## Context（含 6/11 冒烟实测）

用真实凭据（supplychain `.env`）对三源各拉 1-2 条真实数据，只读核查 schema：

| 源 | 结果 | 实测 |
|----|------|------|
| **FO API** 客户预测订单（需求输入）| ✅ PASS | `192.168.100.51:8800/api/forecast-orders` 通；真实单 `FO2026050001`（料号 `S02Y.0162`/`F02N.0184`，ShipPlanDate 2026-06-30）。字段全。**只返回 Customer_Name，无 customer_id。** |
| **U9C/zp ERP** BOM | ✅ PASS | 连**生产库** `erp.equalitytec.com:4443`，认证通；`S02Y.0162` 拉到 117 行直接子件，与 `BomRow` 对得上。 |
| **携客云 SRM** 承诺交期 | ❌ **BLOCKED** | 凭证被接受（企业 59578100），但返回 **`900401`：该企业未开启携客云 OpenAPI**。携客云侧权限问题，非代码 bug，重试无用。 |

**关键约束**：SRM 承诺交期是 SC8 核心真实输入；缺它则所有物料落「无反馈 +30 天 / 低置信」启发式，按门禁全部触发人工确认、不该对客。**故真正端到端真实切换在 SRM 开通前跑不起来。** Paul 6/11 拍板：**部分切换 + 内部验证**（见 D1），SRM 开通另线推进（找携客云确认 59578100 OpenAPI 状态，与 CLAUDE.md「SRM 已接通」记录冲突）。

**已就绪的底座前置**：`platform-hardening-p2`（Pydantic 边界校验 / SRM 限流退避 / SecretsProvider / audit hash-chain）**4 项任务已全部完成**（active，待归档）。本变更 tasks.md §1 与之重复 —— 改为**依赖 platform-hardening-p2 归档**，不重做。

**切换点性质**：`pipeline.compute_forecasts(orders, bom, srm_deliveries, lead_time_map, …)` 是**纯依赖注入** —— 真实化改动**只落加载层**，预测/门禁/审计逻辑零改。

## Goals / Non-Goals

**Goals:**
- FO + BOM 切真实源（两源已 PASS）；SRM 暂留 mock/降级，审计按源如实标记。
- 用 1-2 张真实订单 + 真实 BOM 验证**确定性逻辑**（关键路径齐套、日期加减）零偏差。
- L2 对客门禁由 MVP「标记」升级为**真阻塞**；草稿只进内部企微，**绝不对客**。
- 全链审计（scenario=SC8，含置信度/参数版本/数据源/是否触发人工确认）。

**Non-Goals:**
- 不开真实客户自动外发开关（SRM 未通 + 黄金基准未过，门禁未满足）。
- 不做 SRM 真实接入（阻塞于携客云 OpenAPI 开通）。
- 不改平台底座契约；不上数据库审批 UI。

## Decisions

### ⭐ D1. 切换策略：部分切换（FO+BOM 真实 / SRM 降级），内部验证不外发  〔Paul 已拍板〕
- **选 A（已采纳）**：FO+BOM 接真实，SRM 留 mock。用真实 BOM 跑 1-2 张真实订单，核对确定性逻辑；草稿只推内部企微给 Paul/销售，绝不对客。SRM 通后再切第三源、做真实黄金对账、才谈对客。
- 否决 B（硬停等 SRM）/ C（只做加固+黄金准备）：A 能在 SRM 缺席下验证真实 ERP/BOM 管线 + 确定性逻辑，红线零风险（无对客路径）。
- **理由**：切换点是 DI 加载层，部分切换零额外耦合；审计按源标记保证不撒谎。

### ⭐ D2. mock→真实切换点：`SC8_DATA_SOURCE` 环境开关，保留 mock 回退，审计按源标记
- **选 A（推荐）**：加载层加 `SC8_DATA_SOURCE=mock|real`（默认 mock）。`real` 走 FO 连接器 + `ZpConnector.get_bom_for_products` + `XkySrmConnector.get_delivery_orders`；**SRM 单独子开关**（`SC8_SRM_SOURCE=mock|real`，本期固定 mock）。`pipeline._record_forecast` 的 `data_sources` 由写死 `mock` 改为**按源真实标记**（`bom=real, fo=real, srm_committed=mock`）。异常时一键回退 mock，mock 黄金样本继续回归。
- **理由**：开关切换 + 保留回退 = 红线 §7.1「先 mock 后真实」+ 可回滚；审计如实反映数据来源（IATF）。

### ⭐ D3. FO 连接器收割：把 `load_forecast_orders_from_api` 收割进 SC8 loaders（带 Pydantic 边界校验）
- **现状缺口**：FO API 加载器 `load_forecast_orders_from_api`（命中 ZpViewSO）还在 supplychain `data_loader.py`，**未收割**；SC8 `loaders.py` 只有 CSV + `fo_to_sales_orders`。
- **选 A（推荐）**：收割成 SC8 `loaders.load_forecast_orders_from_api`，对响应做 **Pydantic 边界校验**（对齐 platform-hardening-p2 口径：缺 DocNo/ItemCode/ShipPlanDate → 显式报错挡脏数据），保留 `MVP_ITEM_PREFIXES`（F/S/Y/X）过滤。料号前缀过滤 + 委外清单同步真实料号（如 `F02N.0184`）。
- **理由**：FO 是真实需求入口，必须收割且强校验；否则上游改字段脏数据直灌预测。

### ⭐ D4. 客户数据隔离：以**客户名**为隔离 key  〔Paul 已拍板〕
- **选 A（已采纳）**：FO API 只返回 Customer_Name → 按**客户名**分组算交付日、做 A/B 客户隔离；门禁 `is_first_commitment` 查 audit 也按客户名匹配（现 `gate.py` 已按 `recipient==customer_name`，一致）。
- **风险与缓解**：客户名作主键有重名/改名风险 → 在审计记录冗余 `customer_name` 原值；后续 IT 在 forecast-orders 接口补 customer_id 后切更稳的 key（留 Open Q1）。
- **注**：SC8 是采购/交付域客户订单数据，**非 OEM 研发技术数据** → 不强加 `data_isolation_layer` OEM 路由（符合 CLAUDE.md §4 边界）；隔离在场景层按客户名分组保证。

### ⭐ D5. L2 对客门禁真阻塞 + CRM 草稿形态  〔红线 §7.4〕
- **CRM 形态（结构性保证）**：平台 CRM 层**只有草稿生成、无任何「发客户」函数**（`generate_draft`/`template_draft` 产出文本 + `requires_confirmation=True`）。形态锁定：**草稿 → 推内部企微给 Paul/销售 → 人工确认后由人手发客户**。
- **真阻塞实现**：MVP 是「标记不阻塞」；本期升级 —— 派发/外发路径遇 `requires_confirmation=True` 且无 `confirmed_by` 时**拒发**（fail-closed），补强制校验 + 测试。本期 `SC8_DATA_SOURCE=real` 下**对客外发路径直接禁用**（仅内部企微/待审批队列），不依赖人不犯错。
- **置信度「阈值」澄清**：SC8 置信度是**分类（高/低）非数值分**，无「阈值数字」。规则锁定：**低置信 → 必人工确认、不自动外发**（`gate.py` 已强制）。需校准的是**启发式参数**（无反馈 +30 / 委外 +10 / 物流 +1 / 偏差告警 3 天，现 v0）—— 依赖真实黄金基准，**SRM 通 + 真实对账后回填**，本期不动数值、只锁规则。

### D6. 错误 / 回滚机制（SOP，任务 4.2，待 Paul 确认触发人）
- （a）**数据源回退**：`SC8_DATA_SOURCE=mock` 一键回退，无副作用（SC8 独立工程不改平台）。
- （b）**预测更正**：推送后发现算错 → 走已有 `build_correction_draft`（强制 critical + 人工确认 + 注明更正原因，按 so_id 关联原审计记录全链可追）。
- （c）**偏差监控**：`DEVIATION_ALERT_DAYS=3` 触发重算/告警。
- **需 Paul 确认**：谁有权触发回退/更正（建议：Paul 或指定 PMC），SOP 文档化进 `3-治理与合规/`。

## Risks / Trade-offs

- **[SRM 缺席致全低置信]** 本期真实 BOM + mock SRM → 预测均低置信、不可对客 → 缓解：本期目标只验证确定性逻辑 + 真实管线，不追求可对客预测；对客等 SRM。
- **[连生产 ERP]** BOM 走生产库 `erp.equalitytec.com:4443` → 只读 BOM/Query/OAuth，无写操作；BOM 查询有并发（5 worker）→ 小样本验证限 1-2 料号，不全量。
- **[客户名作隔离 key]** 重名/改名 → 审计留原值 + 待 customer_id 补充（Open Q1）。
- **[FO 真实数据脱敏]** 测试/日志不得落真实客户名 → 测试用脱敏夹具；审计客户名属合规留痕（append-only，受控），日志层脱敏。
- **[确定性偏差]** 真实 BOM 多级/委外形态与 mock 差异 → 关键路径/日期加减必须零偏差，黄金基准用真实 BOM 样本回填后做回归。

## Migration Plan

1. 依赖 `platform-hardening-p2` 归档（§1 加固已完成，不重做）。
2. 收割 FO 连接器进 SC8 `loaders`（D3，Pydantic 校验）+ 测试。
3. 加 `SC8_DATA_SOURCE`/`SC8_SRM_SOURCE` 开关 + 审计按源标记（D2）+ 测试。
4. L2 门禁真阻塞（D5）+ 对客路径在 real 下禁用 + 测试。
5. 委外维护清单填真实料号（如 `F02N.0184`）；保留 `is_outsourced_by_routing` 接口待 U9C 工艺路线。
6. 真实集成测试（FO+BOM 真实、SRM mock）+ **保留 mock 黄金对照做回归**（先写测试后实现）。
7. 小样本验证：1-2 张真实订单跑预测 → 只进内部草稿/待审批队列 → Paul 核对确定性逻辑。
8. archive + 开 PR，停下等 Paul 审。
- **门禁边界**：对真实客户自动外发开关 **保持关闭**，直到 SRM 开通 + 真实黄金基准零偏差 + 门禁 6 项全勾。

## Open Questions

1. **(D4) customer_id 补充**：是否要 IT 在 `u9c_service/app.py` forecast-orders 接口补返回客户编码？补了切 customer_id 作隔离 key 更稳。建议本期先用客户名，并行提需求。
2. **(SRM) 开通时点**：携客云 59578100 OpenAPI 何时能开？这决定第三源切换 + 对客上线时间（与「SRM 已接通」历史记录冲突，需核实）。
3. **(D6) 回退触发人 + SOP 归档**：回退/更正授权人是谁？SOP 放 `3-治理与合规/` 哪个文档？
4. **(启发式校准)** 无反馈 +30 / 委外 +10 / 物流 +1 / 偏差 3 天 —— 是否维持 v0 初值到 SRM 通后真实对账再回填？建议是。
