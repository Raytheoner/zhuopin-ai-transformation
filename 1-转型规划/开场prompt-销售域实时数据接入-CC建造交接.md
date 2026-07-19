---
title: "开场prompt-销售域实时数据接入-CC建造交接"
status: 待发
创建: 2026-07-19（Cowork 总线）
用途: 把 AI 运营指挥中心「销售域」从 2026-06-25 快照升级为同源实时——命令中心 fetch SalesMarketing 同一份 dashboard_data.json。客户端 fetch 已由 Cowork 接好，本交接是 CC 建造侧的「让数据源在 .51 可达 + 刷新」部分。
领取方: CC 采购/平台落地
---

# 销售域实时数据接入 · CC 建造交接

## 一、已完成（Cowork 侧，原型内）

`1-转型规划/AI运营指挥中心/AI运营指挥中心-框架原型-v0.1.html` 销售域已接客户端 `fetch`：

- 常量 `SALES_DATA_URL`（默认 `'data/sales_dashboard_data.json'`）→ `fetch(...,{cache:'no-store'})`。
- `renderSalesData(d)` 按 SalesMarketing `dashboard_data.json` 的**原样 schema** 重建 5 个数据容器（`#salesKpis` / `#salesFunnel` / `#salesScore` / `#salesTopCust` / `#salesRisk`）+ 顶部 `#salesBadge`/`#salesSync`。
- **兜底**：fetch 失败（如本地 file:// 直开、或路径未部署）→ 静默保留页面内 2026-06-25 快照，徽标显示「快照数据（未接实时源）」；成功→徽标变「● 实时 · 同步 <sync_time>」。
- 数据 schema（勿改字段名，改了要同步 `renderSalesData`）：
  `kpis{pipeline_amount, design_win_count, design_win_contribution, total_leads, total_customers, total_contacts, high_risk_leads_count, sales_cycle_avg_days, marketing_penetration_rate, triangle_control_completeness}`、`funnel[{stage,count,rate}]`、`score_distribution{"0-20":n,...}`、`channels[{name,amount,count}]`、`high_risk_leads[{company,contact,phone,score}]`、`sync_time`。

源看板与数据：`C:\Users\Paul Shao\OneDrive\Projects\SalesMarketing\ecu_sales_dashboard_live.html`（Chart.js 版）、数据 `SalesMarketing\crm_data\dashboard_data.json`（3.9KB，同步脚本产出）。

## 二、CC 要做（让数据源在 .51 可达 + 保持新鲜）

1. **选数据供给方式**（三选一，建议 A）：
   - **A 拷贝（最简、同源、推荐）**：把 `dashboard_data.json` 拷到命令中心部署目录下的 `data/sales_dashboard_data.json`（与 `SALES_DATA_URL` 默认一致，无需改 HTML）。拷贝动作挂到 SalesMarketing 那边生成 JSON 的同步脚本之后（一步 copy），或 .51 上加一个定时同步。
   - **B 反向代理**：.51 web 服务把 `/data/sales_dashboard_data.json` 反代到 SalesMarketing 的 `crm_data/`（同源、免拷贝，但要保证 .51 能读到该目录）。
   - **C API 端点**：平台底座出一个 `/api/sales/dashboard` 只读端点读该 JSON 返回；把 `SALES_DATA_URL` 改成该端点。
2. **同源/CORS**：三种方式都优先做到**与命令中心同源**（免 CORS）。若跨源，服务端加 `Access-Control-Allow-Origin` 白名单，勿开 `*`。
3. **刷新节奏**：如需页面自动刷新，可在 `fetch` 那段加轮询（例如每 5–10 分钟）——原看板用 `cache:'no-store'` 已避免缓存；确认 SalesMarketing 的 `dashboard_data.json` 是**定时产出**还是手动跑，决定轮询是否有意义。
4. **落地后自检**：`SALES_DATA_URL` 指向真实可达路径 → 打开命令中心销售域，徽标应变「● 实时 · 同步 …」、数字与 `dashboard_data.json` 一致；断源时应回落快照不报错。

## 三、约束与提醒

- **只读**：命令中心对该数据源只读展示，不回写 CRM。
- **隐私**：`high_risk_leads` 含线索**联系人姓名/电话/邮箱**。在 .51 面向部门成员展示属内部销售数据，一般可接受，但**谁能访问销售域**需与销售接口人（泓钦）/ Paul 对齐访问范围（是否限销售团队），避免线索联系方式过度扩散。
- **发布即收口纪律（CLAUDE.md §5）**：本项若上 .51 供试用，按四关走（冒烟 + 回滚 + 可常驻 + 灰度反馈）。这是「让部门用上销售看板」的收口，不是放开任何自动执行。
- 本交接不改 SalesMarketing 项目本体（它在本仓库外，只读引用其 JSON）。

## 开场词（复制即用）

```
【设置】分支：master ｜ worktree：☑（.51 数据供给属新建造，新起独立 worktree）
读 1-转型规划/开场prompt-销售域实时数据接入-CC建造交接.md，执行「销售域实时数据接入」：按 §二 选 A 方案（把 SalesMarketing/crm_data/dashboard_data.json 供到命令中心可达的 data/sales_dashboard_data.json，挂同步脚本后一步拷贝），保证与命令中心同源免 CORS；落地后打开销售域自检徽标转「实时」、数字与 JSON 一致、断源回落快照不报错。隐私范围（线索联系方式谁可见）如需拍板报 Paul。收工按队列 §二登记批次 + push + 重跑台账。
```
