---
title: "supplychain 收割与全景推进策略"
created: 2026-06-08
updated: 2026-06-08
status: 草案 — 待 VP 确认
authoritative_sources:
  - 卓品智能AI转型全景规划.md
  - 从采购部启动.md
  - supplychain/PROJECT_STATUS.md
  - supplychain/CLAUDE.md
---

> 一句话结论：**supplychain 不是"另一个项目"，它是全景规划采购线 + 运营两个场景 + 销售交付通报的"已验证真实原型"。正确动作是"收割进全景平台底座与场景"，而不是把单体整体并入，也不是继续两套并行。**

---

## 0. 盘点结论：supplychain 已经做了多少

supplychain 用**真实 ERP 数据**（卓品自建 zp REST API，24,629 条 PO + 12,902 条物料）+ **携客云 SRM**（承诺交期 vExpectedDate）跑通了一条端到端链路，267 项测试全绿。它对 12 环节订单履约的覆盖约 35%，但这些已实现的引擎**映射到全景的多个场景**：

- 数据层（生产级）：携客云 SRM 连接器、卓品 zp ERP 连接器（真实数据）、U9C 骨架、DataConnector 抽象 + CSV 回退。
- 智能体（算法完整或 MVP）：齐套分析、采购建议/遴选、供应商交期跟踪、SRM 风险预警、销售订单接入、SMT 排产、**交付日预测**、采购审核业务规则。
- 通知层：**CRM 延期通知草稿**、企业微信推送。
- 可视化：预警看板（HTML）。

**你说的"成品交付预期 → CRM 通报"= supplychain 的 `delivery_forecast.py` + `crm_notifier.py`，已经实现。** 它对应全景的 **SC8 客户订单交期智能承诺**（原排 2027-02）。

---

## 1. 工具分工：Claude Code Desktop 建造，Cowork 规划治理

| 环境 | 角色 | 干什么 |
|------|------|--------|
| **Claude Code Desktop** | 建造车间 | 连内网/公网 SRM/ERP（凭据在此）、跑真实数据、写并运行数字员工代码。**全景的开发与真实验证主战场。** |
| **Cowork（本会话）** | 规划治理桌 | 全景规划、路线图、治理/合规文档、岗位招聘、对外汇报、架构梳理。不碰真实库。 |

**两者共用同一个 `企业AI转型` Git 仓库**：Cowork 改规划/文档，Claude Code 建代码，git 同步。

> 答你的问题："是否可以直接在 Claude Code Desktop 推进整个全景规划？" —— **是，而且应该。** 开发和真实跑数都在那里；Cowork 做它做不好的规划与治理。

---

## 2. 处理方针：收割（harvest），不整体并入

supplychain 是为学习快速搭的**单体试验田**。整体并入全景会把它的临时结构和技术债带进来，污染干净的模块化架构（平台底座 + 单场景数字员工 + IATF 审计 + OEM 隔离）。因此：

1. **把已验证的可复用件"收割"进平台底座**（连接器、通知器、业务规则、抽象层）。
2. **把已验证的智能体"落位"成对应全景场景的引擎**（每个场景一个数字员工，import 平台底座）。
3. **收割完成后，supplychain 打 git tag 作只读参考存档**，不再并行开发。

---

## 3. 表① 模块 → 平台底座迁移清单

目标：把 supplychain 的真实连接器**替换**掉我先前在 `zhuopin_platform` 里搭的 stub（stub 作废，用 supplychain 验证过的真货）。

| supplychain 模块 | 职责 | 迁入平台底座位置 | 处理 |
|------------------|------|------------------|------|
| `data/xky_srm_connector.py` | 携客云 SRM 只读（承诺交期） | `shared_tools/srm_connector/` | 收割（生产级，替换 stub）|
| `data/zp_connector.py` | 卓品 zp REST API（真实 ERP：PO/物料）| `shared_tools/erp_connector/`（zp）| 收割（真实数据源）|
| `data/u9c_connector.py` | U9C 骨架（回退 CSV，待真实接口）| `shared_tools/u9c_connector/` | 收割骨架，等 7/1 MCP 接口补真实 |
| `data/connector.py` + `csv_connector.py` | DataConnector 抽象 + CSV 回退 | `shared_tools/`（数据抽象层）| 收割（Provider 模式与 SC1 一致）|
| `crm_notifier.py` | CRM 延期通知草稿生成 | `shared_tools/crm_notifier/` | 收割（SC8 通报用）|
| `notifiers/wecom.py` | 企业微信推送 | `shared_tools/notifiers/` | 收割（通用通知通道）|
| `agents/business_rules.py` | 采购审核规则（金额阈值等）| `agents/` 或场景内 | 收割（SC5 规则 + 治理红线）|
| `data/audit`（SRM 连接器内审计日志）| 调用留痕 | `audit/`（已建）| 合并到平台统一审计 |

> 注意：收割时把审计统一到平台 `audit`（JSONL→ClickHouse）、补 OEM 隔离层——这是 supplychain 当初没做、但全景合规必须有的两块。

---

## 4. 表② supplychain 功能 → 全景 38 场景映射

| supplychain 智能体/功能 | supplychain 状态 | 对应全景场景 | 全景原排期 | 收割后可提前到 |
|------------------------|------------------|--------------|-----------|---------------|
| `delivery_forecast.py`（SMT完工+物流→交付日+风险）| MVP 已实现 | **SC8 客户订单交期智能承诺** ⭐你的核心目标 | 2027-02 | **2026-07/08 MVP** |
| `crm_notifier.py`（延期→客户通知草稿）| 已实现 | SC8 的 CRM 通报环节 | 2027-02 | 随 SC8 |
| `sales_order_intake.py`（订单→生产需求）| MVP | SC8 输入 / 客户订单接入 | — | 随 SC8 |
| `smt_scheduling.py`（到货+工时→完工日）| MVP | O1 生产排程 / SMT 委外（link 11）| 2026-11 | 2026-09 |
| `kit_analysis.py`（BOM 展开+齐套+缺口）| 算法完整 | O2 物料齐套预警（运营）| 2026-10 | 2026-09 |
| `purchase_recommendation.py`（MRP+遴选+下单日）| 算法完整 | SC5 供应商自动评分/采购建议 | 2026-10 | 2026-09 |
| `supplier_tracking.py`（在途+三色风险）| Phase 3b 完整 | SC3 供应商绩效看板 / 在途跟踪 | 2026-09 | 可即用 |
| `srm_risk_monitor.py`（SRM 三色催货预警）| 半实现 | SC1 风险维度 + 断料预警（与 SC6 相关）| SC1=07 | 复用进 SC1/SC6 |
| `web_app.py` + dashboard.html | 完整 | 运营看板 / 半年度汇报可视化 | — | 即用 |

**结论**：采购线（SC1/SC3/SC5/SC8）+ 运营线（O1/O2）+ 销售交付通报的**核心引擎已在真实数据上验证**。全景"从 7 月起逐场景从零搭"的假设需要修正——大半采购+运营核心是**收割+加固**，不是从零。

### 引擎落位与"提升触发"约定（避免过早抽象 / 也避免永久重复）

收割来的引擎**默认落在各自场景本地**（同 SC8 forecast、O2 kit_engine 的做法），保持**纯算法自包含**（不掺审计/通知/场景胶水），便于将来"搬移而非重写"。

> **提升触发（rule of three）**：当某引擎出现**第 2 个真实消费方**时，才提取到 `zhuopin_platform/agents/` 作共享引擎，照两份具体实现定接口，不靠猜。
> - `kit_engine.py`（齐套）→ **✅ 已提升（2026-06-11，PR #7）**：SC5 是第 2 消费方，触发 rule-of-three；`explode_bom + calc_shortage` 落 `zhuopin_platform/agents/kit_engine.py`，O2 改薄转发层，底座 18 tests + O2 20 回归测试全绿。
> - `compute_dos`（DOS 可用天数）→ **SC3 已落场景本地（PR #6，2026-06-10）**。D2 拍板 A：核查发现 O2 实际用 `calc_shortage` 非 DOS，`compute_dos` 当前**仅 SC3 一个消费方**，未到第 2 消费方，不提升底座；代码注释已标提升触发条件。
> - 其余引擎同理：第 2 消费方出现前不抽象。

---

## 5. 表③ 受影响场景重排（建议）

| 场景 | 全景原排期 | 建议新排期 | 依据 |
|------|-----------|-----------|------|
| 平台底座（收割 supplychain 连接器/通知器）| 7 月骨架 | **7 月：用 supplychain 真货替换 stub** | 真连接器已验证 |
| SC1 供应商风险初筛 | 7 月 | 7 月收尾（mock→6/12 真实）| 代码已完成 |
| **SC8 交期承诺 MVP** | 2027-02 | **2026-07/08 MVP** | delivery_forecast 已实现 ⭐ |
| O2 物料齐套预警 | 2026-10 | 2026-09 | kit_analysis 算法完整 |
| O1 生产排程 | 2026-11 | 2026-09/10 | smt_scheduling 已 MVP |
| SC5 采购建议/遴选 | 2026-10 | ✅ 已完成（2026-06-11，PR #7 待合并）| purchase_recommendation 收割完成；41 tests 全绿，黄金值对齐（35850/640000）|
| SC3 绩效看板/在途 | 2026-09 | ✅ 已完成（2026-06-10，PR #6 合 master）| supplier_tracking 收割完成；29 tests 全绿、8 项 golden 等价 |
| SC9 OEM 订单波动预测 | 2026-12 | 维持（需历史数据积累）| 预测类，数据未足 |

> SC2（采购周报）、SC4（合同提取）、SC6（芯片预警）、SC7（库存优化）等仍按原计划——supplychain 未覆盖。
> SC8 提前后，原"SC8 依赖 SC6/SC7"的顾虑改变：supplychain 用的是**真实供应商承诺交期 + BOM 齐套**直接算交付日，不依赖 SC6/SC7 的预测，因此可独立提前。

---

## 6. 收割时必须补的三块（supplychain 没有、全景合规要求）

1. **IATF 审计统一**：supplychain 各处分散留痕 → 并到平台 `audit`（append-only，3 年）。
2. **OEM 数据隔离**：supplychain 未做客户隔离 → 收割进平台 `data_isolation_layer`，凡涉 OEM 技术数据按客户路由。
3. **错误/回滚 SOP + 人工审查门禁**：交付日预测要推客户，错误代价高，必须定义置信度阈值与人工确认（L2）。

---

## 7. 下一步行动（建议顺序）

1. **平台底座收割（7 月，Claude Code Desktop）**：把 `xky_srm_connector` / `zp_connector` / `u9c_connector` / `crm_notifier` / `wecom` / 抽象层 迁入 `zhuopin_platform/shared_tools`，作废我先前的 stub；SC1 改 import 真连接器。
2. **SC8 交期承诺 MVP（7-8 月）**：收割 `delivery_forecast` + `sales_order_intake` + `smt_scheduling` + `crm_notifier` → 落成全景 SC8 数字员工。先按你的启发式（无反馈+30天、委外齐套+10天、关键路径定齐套日、带置信度），6/12 真实需求与供应商反馈到位后切真实，变化超阈值推 CRM。
3. **运营 O1/O2、采购 SC3/SC5 落位（9 月）**：把对应引擎从 supplychain 落成各自数字员工。
4. **supplychain 存档**：收割完成后打 tag，转只读参考。
5. **同步修订全景文档**：把上表②③并入《全景规划》与《实施计划》，重排采购+运营时间线。

---

## 8. 给 VP 的三个确认点

1. **方针**：收割进全景（推荐）/ 维持两套并行 / 整体并入 —— 建议"收割"。
2. **SC8 提前**：是否同意把交期承诺从 2027-02 提前到 7-8 月 MVP（核心价值、且已验证）。
3. **真连接器替换 stub**：是否授权用 supplychain 的 zp/SRM 连接器替换我在平台底座搭的占位 stub（强烈建议——那是真货）。

确认后，开发动作在 Claude Code Desktop 推进；本文表②③我可同步并入全景规划与实施计划。
