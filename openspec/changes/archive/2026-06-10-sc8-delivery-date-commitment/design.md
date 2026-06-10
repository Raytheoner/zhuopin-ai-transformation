# Design — SC8 客户订单交期智能承诺（收割式 MVP）

> 审阅对象：Paul。本文 7 个技术决策（D1–D7）请逐条拍板；标 ⭐ 的影响算法正确性/合规门禁。
> 背景已在 proposal + 两份 spec + 《SC8 上线前置门禁》，此处只列"怎么做"与需你拍板项。

## Context

- 平台底座已就绪（PR #1/#3 合入 master）：连接器（zp/SRM/CSV）、`crm_notifier`（DelayNoticeInput/generate_draft）、`Notifier`（L2 fail-closed + PendingApprovalSink 钩子）、`audit`。SC8 是**首个消费方**。
- supplychain 已验证的 SC8 管线（`run_delivery_forecast.compute_forecasts`）：订单聚合 → SRM 承诺交期/BOM 关键路径 → 物料到货 → SMT 完工 → 交付日 + 三色风险。**但收割代码尚无**门禁文档要求的两块：**置信度** 与 **无反馈+30天/委外+10天启发式**——这是 SC8 要补的核心增量。
- 收割边界（沿用 D1/Q1）：业务引擎 + `SalesOrder`/`ForecastOrder`/`DeliveryForecast` 进**场景层**，不进平台底座。
- 硬约束：《SC8 上线前置门禁》——黄金基准 + 错误/回滚 SOP 两道闸未过，**只出草稿/内部看板，不对真实客户自动外发**。

## Goals / Non-Goals

**Goals:**
- 收割三引擎 + 编排进 SC8 工程，import 平台连接器/模型；补置信度 + 启发式。
- 接平台 `Notifier` 做对客 L2 门禁（fail-closed）、`PendingApprovalSink` 落待审批、`audit` 全链留痕。
- mock 跑通端到端 + 黄金基准回归框架；真实切换留任务 N.1（6/12）。

**Non-Goals:**
- 不连真实 zp ERP/携客云 SRM（留任务 N.1）。
- 不实现完整 DelayCase 状态机（见 D4）；不建审批 UI（队列实现见 D5）。
- 不碰 SC9/O1/O2（各自场景）；不改平台底座契约（只消费）。

## Decisions

### ⭐ D1. 置信度模型：二级（高/低），按"是否全部物料有 SRM 承诺交期"判定
门禁文档要求带置信度。收割代码无此概念。
- **选 A（推荐）**：二级置信度。**高** = 该成品全部直接子件都有 SRM 承诺交期；**低** = 含任一无反馈物料（走 +30 天）或含委外估算。简单、可解释、对齐门禁"有承诺=高/默认假设=低"。
- 选 B：三级（高/中/低）或 0-100 分。更细但阈值难定、6/12 前无数据校准，过度设计。
- **理由**：A 够用且可解释（IATF 要可追溯）；细化等真实数据进来再说。

### ⭐ D2. 启发式参数：无反馈 +30 天、委外 +10 天，设为**可配置常量**（不硬编码散落）
门禁文档定的 v0 启发式。
- **选 A（推荐）**：集中到 SC8 配置（如 `config.py`：`NO_FEEDBACK_LEAD_DAYS=30`、`OUTSOURCE_EXTRA_DAYS=10`、`LOGISTICS_DAYS=1`、`DEVIATION_ALERT_DAYS=3`）。黄金基准校验时按真实数据回填调参，不改代码逻辑。
- 选 B：散在各函数里写死。否决——门禁文档明说"阈值定稿后回填"，必须可配。
- **理由**：阈值是业务参数不是逻辑，集中可配 + 审计可追"用了哪组参数"。

### ⭐ D3. "委外"判定来源：本期用料号规则/标记，留接口待真实工艺路线
收割代码没有委外标记。+10 天要先知道哪些成品委外。
- **选 A（推荐）**：MVP 用**显式委外清单/料号前缀规则**（配置可维护），判定 `is_outsourced(product_id)`；预留接口，6/12 真实工艺路线（U9C 工艺路由）到位后替换。
- 选 B：等真实工艺路线才做委外逻辑。否决——会阻塞 MVP，且 supplychain 已有委外概念。
- **需你确认**：卓品的委外成品当前怎么识别最准？料号规则 / 一张维护清单 / 别的标记？（见 Open Q1）

### ⭐ D4. CRM 通报输入：`DeliveryForecast → DelayNoticeInput` 直接适配，**MVP 不收割 DelayCase 状态机**
平台 `crm_notifier` 收 `DelayNoticeInput` Protocol。
- **选 A（推荐）**：写一个轻适配器 `forecast_to_notice(DeliveryForecast) -> DelayNoticeInput`（customer/so/product/原交期=target/新交期=forecast/delay_days/reasons=[瓶颈]）。MVP 不需要 DelayCase/CaseStore（那是延期案例随时间跟踪的状态机）。
- 选 B：收割 `delay_case.py`（DelayCase + CaseStore SQLite 状态机）。重，且 MVP 不需要跨时间案例跟踪。
- **理由**：A 最小可用，直接喂平台 Protocol；案例状态机等"偏差监控/更正流程"要长期跟踪时再收割（可作后续增量）。**但更正流程要关联原记录 ID**——MVP 用 audit 记录 + forecast 的 so_id 做关联键即可，不必上状态机。

### D5. 待审批队列：MVP 用**文件型** `PendingApprovalSink` 实现（落 JSONL），接平台钩子
平台只暴露了 `PendingApprovalSink` 接口（Blocker2）。SC8 要给个实现。
- **选 A（推荐）**：SC8 实现 `FilePendingQueue`（落 `data/pending_approvals.jsonl`，append + 状态字段），责任人可读、可标确认；`approve(id, confirmed_by)` 再触发 `Notifier.send(confirmed_by=...)`。轻量、零外部依赖、满足门禁"草稿持久化可二次放行"。
- 选 B：上 SQLite/DB 状态机。MVP 偏重，文件型够验证闭环。
- **理由**：A 满足门禁《L2 持久化待审批队列》最小闭环；DB/审批 UI 等切真实库或规模化再升级。

### D6. 工程结构与数据模型落位
```
4-数字员工/采购部/SC8-客户订单交期智能承诺/
├── pyproject.toml                # pip install -e 平台底座
├── sc8/
│   ├── config.py                 # D2 可配参数（启发式/阈值）
│   ├── models.py                 # SalesOrder/ForecastOrder/DeliveryForecast（D1/Q1 留 SC8）
│   ├── loaders.py                # SO/FO 加载（CSV/Excel/ERP导出/FO API，收割自 data_loader 的 SC8 部分）
│   ├── intake.py                 # sales_order_intake（聚合需求）
│   ├── scheduling.py             # smt_scheduling（齐料+工时→完工）
│   ├── forecast.py               # delivery_forecast + 置信度 + 启发式（核心增量）
│   ├── pipeline.py               # compute_forecasts 编排（SRM承诺→到货→关键路径→SMT→预测）
│   ├── notify.py                 # forecast→DelayNoticeInput 适配 + Notifier 门禁接线
│   └── pending_queue.py          # D5 文件型 PendingApprovalSink
├── tests/                        # 先测试后实现；mock 夹具
└── data/golden/                  # 黄金基准回归样本（门禁要求）
```
- `ProductionPlan` 用平台 `models`（连接器返回 shape，已在底座）；`SalesOrder/ForecastOrder/DeliveryForecast` 留 SC8（符合 D1/Q1）。

### D7. CRM 邮件 prompt 下放场景层（采纳评审 Medium 6b）
评审指出平台 `draft.py` 的邮件 prompt/business copy 属业务策略，应下放。
- **选 A（推荐）**：SC8 的 `notify.py` 提供 SC8 专属 prompt/措辞（交付承诺口径），调用平台 `generate_draft` 时注入；平台层保留通用 LLM 调用 + 模板降级引擎。后续把平台 `draft.py` 的 prompt 标记为"默认模板，场景可覆盖"。
- 选 B：维持 prompt 在平台。否决——评审已指出过界，且对客口径应由业务（你）掌控。
- **注**：本批先在 SC8 侧注入；平台 `draft.py` 的 prompt 参数化（允许场景覆盖）作为配套小改，是否纳入本变更见 Open Q3。

## Risks / Trade-offs

- **[启发式失真] +30/+10 是拍的初值** → 缓解：D2 设可配；黄金基准校验用真实样本回填校准；确定性逻辑（关键路径/日期加减）必须零偏差，启发式部分按约定核对。
- **[首次承诺判定] "首次给某客户承诺"需要历史** → 缓解：MVP 从 audit 历史查该客户是否有过承诺记录；无历史即视为首次（fail-closed 偏保守，符合门禁）。
- **[委外识别不准] D3 用规则可能漏判** → 缓解：留 `is_outsourced` 接口，真实工艺路线到位即换；漏判委外会少算 10 天 → 体现在黄金基准核对，且低置信兜底。
- **[文件队列并发] D5 文件型队列多进程写** → 缓解：复用平台已加锁的 JSONL 写法（High4 已修）。
- **[mock→真实偏差] 真实 SRM/BOM 数据形态差异** → 缓解：切换为独立任务 N.1，先过黄金基准再切；连接器已在收割阶段 mock 验证。

## Migration Plan

1. 建工程 + pip install 平台底座 → 冒烟 import。
2. 收割 models/loaders/三引擎/编排（改 import 指向平台）→ 各自 mock 测试。
3. 补置信度 + 启发式（D1/D2/D3）→ 单测覆盖（含关键路径/无反馈/委外三类）。
4. 接 notify（D4/D7 适配）+ Notifier 门禁 + D5 文件队列 → 门禁测试（低置信/首次/延期必拦、确认才发）。
5. 全链审计（预测/更正/确认）→ 审计测试。
6. 黄金基准框架 + mock 样本回归 → 端到端 mock 跑通。
7. 任务 N.1（6/12 后）：切 zp ERP BOM + 携客云 SRM 真实，跑黄金基准（确定性偏差=0）→ 内部企微通道验证 → 过门禁检查表才开真实客户外发。
- 回滚：SC8 是独立工程，不改平台；回滚直接停用场景，无副作用。

## Open Questions

1. **(D3) 委外成品怎么识别最准**：料号规则 / 一张维护清单 / ERP 某标记？MVP 先用哪种？（我建议先维护清单 + 留 U9C 工艺路线接口）
2. **(D1/置信度) 二级够不够**：高/低两级 vs 你想要中间档（如"中=有反馈但晚于目标日"）？我建议先二级。
3. **(D7) 平台 draft.py prompt 参数化**：本变更顺带把平台草稿 prompt 改为"场景可覆盖"（小改平台），还是只在 SC8 侧注入、平台改单列一个后续 PR？我建议本变更只在 SC8 注入，平台参数化另开小 PR 不混入。
4. **(门禁) 偏差阈值初值**：默认 3 天（门禁文档建议值）是否直接用作 MVP 初值？真实校准后回填。
