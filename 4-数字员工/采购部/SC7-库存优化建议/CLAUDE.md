# CLAUDE.md — SC7 库存优化建议（场景级记忆）

> 本文件是 SC7 场景的本地记忆/进度笔记，隔离于其他场景。
> 项目级上下文见仓库根 `CLAUDE.md`；SC7 规划权威见全景规划 §2.1.2 采购段 SC7 行、
> `1-转型规划/采购域场景v2.3-局部定稿.md`、`1-转型规划/0-全景路线图/采购域重排-移交全景路线图Task.md`。
> 本场景 = CC 建造车间产物；**不改规划文档**（那是 Cowork 的活）。

## 1. 场景定位

- **场景**：SC7 = 采购部数字员工「库存优化建议」，采购域 v2.3 重排（2026-07-06）后**承接原 SC5「采购建议与供应商遴选」全部功能**（SC5 场景编号已退役）。
- **全景编号**：全景规划 §2.1.2 采购部 SC7（v2.3 大幅扩写场景，两期制：①2026-09 承接 SC5 引擎部署位 / ②2027-01 深化）。
- **本次交付范围（①期起点）**：MOQ/MPQ 采购量计算 + 最低价已认证供应商遴选 + R1/R2 业务规则（>50万金额 / 无认证供应商 → L2 人工审核）+ L1/L2 分桶 audit 留痕。mock 阶段只输出建议，不实际下单。
- **尚未落地（②期 2027-01 深化，v2.3 局部定稿描述的扩写范围）**：动态安全库存、呆滞库存处置、委外排程释放——本次迁移不涉及，留待深化阶段单独 openspec。
- **底座贡献**：沿用 `kit_engine`（explode_bom + calc_shortage，`zhuopin_platform/agents/kit_engine.py`），与 O2/SC8 共同复用，本次迁移不改动底座。

## 2. 关键决策记录（Paul 拍板，随 SC5 引擎迁移原样继承）

| 决策 | 结论 | 依据 |
|------|------|------|
| D1：kit_engine 归属 | 底座件，SC7 只消费不改 | 原 SC5 时期已提升至 `zhuopin_platform/agents/`，O2/SC8/SC7 三方共用 |
| D2：BusinessRulePolicy 放哪 | SC7 场景本地 `sc7_inventory/business_rules.py` | 沿用原 SC5 决策，无第 2 消费方需求 |
| D3：L2 门禁实现 | mock 阶段打标 human_required=True、打印清单不阻塞 | 真实门禁需前端审批流，Phase 2 实现；分桶 audit 记录 automation_level=L1/L2 |
| L2 触发条件 | R1（金额 ≥50万）+ R2（新供应商/无认证）→ 待人工审核 | IATF L2 门禁红线，随功能迁移继承（阈值不变） |
| 黄金基准目标值 | auto_total=35850 / review_total=640000 / grand_total=675850（精确相等） | 原 SC5 B6 修复后的口径，迁移后逐位保留，禁止漂移 |
| 包命名 | `sc7_inventory`（不沿用 `sc5_purchase`） | 场景编号已变更为 SC7，沿用旧包名会误导后来者；内部模块名（business_rules/purchase_engine/agent）不变，描述的是算法职责非场景编号 |

## 3. 复用底座资产

- **kit_engine（底座）**：`zhuopin_platform.agents.kit_engine` — `explode_bom(bom, plans)` / `calc_shortage(gross, inventory, purchase_orders)`。
- **模型**：`zhuopin_platform.shared_tools.models` — `PurchaseOrder / InventoryRow / BomRow / ProductionPlan / Supplier`。
- **CSV 连接器**：`zhuopin_platform.shared_tools.csv_loaders`（mock 阶段数据源，沿用原 SC5 mock 数据集）。
- **审计**：`zhuopin_platform.audit.AuditLogger`（`scenario="SC7"`，L1/L2 分桶，`action=purchase_recommendation_eval`）。
- **场景本地**：`sc7_inventory/business_rules.py`（BusinessRulePolicy，R1/R2 规则，阈值 50万）；`sc7_inventory/purchase_engine.py`（build_recommendations + 遴选 + MOQ/MPQ）；`sc7_inventory/agent.py`（`run_sc7` 入口）。

## 4. 红线（建造时守住）

- **L2 门禁必须执行**：金额 ≥ 50 万（R1）或新供应商/无认证（R2）→ `review_status="待人工审核"`，标 `human_required=True`，不可自动下单（IATF L2 人工确认门禁）。
- 先 mock/脱敏跑通逻辑，再切真实 SRM/ERP（与原 SC5 前置一致，未因迁移改变）。
- 每次采购建议写平台 `audit`（`scenario="SC7"`，L1/L2 分桶 + 完整触发规则列表，IATF 3 年留存）。
- 黄金基准数值精确相等（auto_total=35850 / review_total=640000 / grand_total=675850），禁止用近似比较放宽约束。
- 零 `from supplychain` / `sys.path` 残留；零 `sc5_purchase` 残留 import。
- ②期深化（动态安全库存/呆滞处置/委外排程）落地前须先过 openspec propose/design，不得在本 MVP 基础上直接堆功能。

## 5. 状态时间线

| 日期 | 状态 |
|------|------|
| 2026-06 ~ 2026-07-02 | 前身 SC5「采购建议与供应商遴选」MVP 完成（`kit_engine` 底座化 + L1/L2 分桶 audit + 黄金值对齐），详见 SC5 旧场景目录 `CLAUDE.md`（历史记录）。 |
| 2026-07-06 | **SC5 场景编号退役，能力原样迁移为 SC7**（采购域 v2.3 重排，`sc-v23-engine-migration` 变更包）：包名 `sc5_purchase`→`sc7_inventory`，audit `scenario` "SC5"→"SC7"，函数 `run_sc5`→`run_sc7`，41 tests（含黄金基准三项）逐位保留，pytest 全绿，逻辑/阈值零变更。 |
| 2026-07-10 | 底座 `kit_engine.py` 新增 A1/A2 纯函数 + `ZpConnector.get_purchase_orders` 新增真实 SRM 确认日期查询（`shortage-baoguan-criteria-v3`，缺料口径改造）——**均为纯增量，SC7 本次不接入**，`calc_shortage`/`explode_bom` 签名/行为零变化；黄金基准（`auto_total=35850`/`review_total=640000`/`grand_total=675850`）8 项测试逐一核验精确不漂移，41 tests 全绿零回归。 |
| **当前** | **✅ SC7①期（承接位）完成**，等待真实 SRM/ERP 接入（独立后续任务，与原 SC5 前提一致）；②期深化（2027-01）待单独 openspec。 |

## 6. 关键依赖/前置（解锁条件）

- 🟡 真实 SRM 接入（携客云 SRM，获取供应商价格/认证状态）— 真实遴选前置；mock 阶段不阻断。
- 🟡 真实 ERP 接入（U9C ZpConnector，MRP 需求/库存数据）— 真实建议生成前置。
- 🟡 L2 前端审批流 — Phase 2 实现；mock 阶段 human_required=True 打标兜底。
- 🟡 业务规则校准：50万阈值与"认证供应商"判定标准（当前来自 business_rules.py，生产环境须从配置/SRM 读取）。
- 🟡 ②期深化范围确认（动态安全库存/呆滞处置/委外排程释放）— 2027-01 前需 openspec propose，业务口径待姚祖怡确认。
- 运行：`python -m sc7_inventory.agent`（mock 模式）。

## 路径引导（队列 #345，2026-08-18）—— 扁平部署布局下不再硬失败

- **改了什么**：本组件下列入口顶部的 #300 worktree 隔离引导，**找不到 `5-平台底座/zhuopin_platform` 标记时不再无条件 `raise`**：`sc7_inventory/agent.py`
- **为什么**：`.51` 的部署布局是扁平的 `C:/<svc>/app` ＋ `C:/<svc>/zhuopin_platform`（后者已由 deploy 脚本 `pip install -e` 进该服务 venv，全机唯一一份），**本就没有 `5-平台底座/` 这层目录**。原实现在此直接 raise，等于把入口在生产布局上钉死。2026-08-18 SC8（8091）与 QD-B（8093）当天各自被它打挂过一次。
- **改法**（同 QD-B `dcc4162` / SC8 `a858769` 已验证范式）：找到标记 → 按 #300 原样前插（开发机 N 个平等 worktree 需确定性）；找不到 → 只插自身包路径、平台底座交环境解析（生产机唯一一份、无歧义）；**只有当环境里也没有 `zhuopin_platform` 时才 raise** —— 不引入静默失败。
- 🔑 **为什么这类雷本地测不出来**：**本地永远能找到仓库根标记**，全量测试全绿与它毫无关系。凡"引导/路径解析"类改动，**本地绿 ≠ 生产可启动**。
- ⚠️ **`tests/conftest.py` 刻意不改**：在 monorepo 内 fail-loud 是**有价值的**——测试就该跑在仓库里，找不到标记说明环境真错了，此时静默回退才是隐患。
- **收拢为平台底座共享函数** 见 `openspec/changes/platform-bootstrap-ensure-paths/`（已 propose，待 Shao Peishen 审 design，本次未 apply）。
