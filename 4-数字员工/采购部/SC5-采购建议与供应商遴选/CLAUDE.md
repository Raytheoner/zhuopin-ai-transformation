# CLAUDE.md — SC5 采购建议与供应商遴选（场景级记忆）

> 本文件是 SC5 场景的本地记忆/进度笔记，隔离于其他场景。
> 项目级上下文见仓库根 `CLAUDE.md`；SC5 规划权威见全景规划 §2.1.3 采购部 SC5 行、
> 实施计划 §一采购表、`1-转型规划/0-全景路线图/session接力-Phase1收口.md`。
> 本场景 = CC 建造车间产物；**不改规划文档**（那是 Cowork 的活）。

## 1. 场景定位

- **场景**：SC5 = 采购部第 5 个数字员工，采购建议生成与供应商遴选。
- **全景编号**：全景规划 §2.1.3 采购部 SC5（S1 筑基期场景）。
- **自动化等级**：L1/L2 分桶 — L1（可自动下单，≤50万，认证供应商）；L2（待人工审核，≥50万/新供应商）。
- **MVP 范围**：采购建议生成（MOQ/MPQ + 下单日 + 供应商遴选）+ L1/L2 分桶 audit 留痕；mock 阶段只输出建议，不实际下单。真实 SRM/ERP 接入为后续任务。
- **底座贡献**：SC5 是 `kit_engine`（explode_bom + calc_shortage）的第 2 消费方（O2 为 #1），rule-of-three 触发 → kit_engine 已提升至 `zhuopin_platform/agents/kit_engine.py`。

## 2. 关键决策记录（Paul 拍板）

| 决策 | 结论 | 依据 |
|------|------|------|
| D1：kit_engine 提升到底座 | **✅ 提升至 `zhuopin_platform/agents/`** | SC5 是第 2 消费方，rule-of-three 触发；O2 改为薄转发层（from zhuopin_platform.agents.kit_engine import） |
| D2：BusinessRulePolicy 放哪 | **SC5 场景本地** `sc5_purchase/business_rules.py` | 无第 2 消费方，rule-of-three 未触发 |
| D3：L2 门禁实现 | mock 阶段打标 human_required=True、打印清单不阻塞 | 真实门禁需前端审批流，Phase 2 实现；分桶 audit 记录 automation_level=L1/L2 |
| L2 触发条件 | R1（金额 ≥50万）+ R2（新供应商/无认证）→ 待人工审核 | IATF L2 门禁红线；M015 阈值 50万 已落 business_rules.py |
| 黄金基准目标值 | auto_total=35850 / review_total=640000 / 合计=675850（精确相等） | B6 安全修复后改为精确对比（非近似），防黄金值漂移 |

## 3. 复用底座资产

- **kit_engine（底座）**：`zhuopin_platform.agents.kit_engine` — `explode_bom(bom, plans)` / `calc_shortage(gross, inventory, purchase_orders)`（SC5 提升、O2 兼容）。
- **模型**：`zhuopin_platform.shared_tools.models` — `PurchaseOrder / InventoryRow / BomRow / ProductionPlan / Supplier`。
- **CSV 连接器**：`zhuopin_platform.shared_tools.csv_connector`（mock 阶段数据源）。
- **审计**：`zhuopin_platform.audit.AuditLogger`（scenario="SC5"，L1/L2 分桶，action=purchase_recommendation_eval，automation_level=L1/L2）。
- **场景本地**：`sc5_purchase/business_rules.py`（BusinessRulePolicy，R1/R2 规则，阈值 50万）；`sc5_purchase/purchase_engine.py`（build_recommendations + 遴选 + MOQ/MPQ）。

## 4. 红线（建造时守住）

- **L2 门禁必须执行**：金额 ≥ 50 万（R1）或新供应商/无认证（R2）→ `review_status="待人工审核"`，标 `human_required=True`，不可自动下单（IATF L2 人工确认门禁）。
- 先 mock/脱敏跑通逻辑，再切真实 SRM/ERP。
- 每次采购建议写平台 `audit`（L1/L2 分桶 + 完整触发规则列表，IATF 3 年留存）。
- 黄金基准数值精确相等（auto_total=35850 / review_total=640000），禁止用近似比较放宽约束。
- 零 `from supplychain` / `sys.path` 残留。

## 5. 状态时间线

| 日期 | 状态 |
|------|------|
| 2026-06 | O2 kit_engine 落场景本地（第 1 消费方）。 |
| 2026-07-02 | SC5 变更包完成：kit_engine 提升底座（`zhuopin_platform/agents/kit_engine.py`）；O2 改为薄转发层；SC5 场景工程收割完成（TDD，pytest 全绿，底座 114 + O2 20 + SC5 41 = 175 tests 全绿）；L1/L2 分桶 audit 留痕；黄金值对齐 35850/640000。 |
| 2026-07-02 | `/opsx:archive` 完成 → 变更归档至 `openspec/changes/archive/2026-07-02-sc5-purchase-recommendation/`（含 SHALL/MUST 关键词修复，见待办 #9）。 |
| **当前** | **✅ SC5 MVP 完成**，等待真实 SRM/ERP 接入（独立后续任务）。 |

**待办 #9**（预先存在，非阻塞）：sc5 openspec specs 中 SHALL/MUST 关键词已在 archive 时补全（archival 前的遗留）。

## 6. 关键依赖/前置（解锁条件）

- 🟡 真实 SRM 接入（携客云 SRM，获取供应商价格/认证状态）— 真实遴选前置；mock 阶段不阻断。
- 🟡 真实 ERP 接入（U9C ZpConnector，MRP 需求/库存数据）— 真实建议生成前置。
- 🟡 L2 前端审批流 — Phase 2 实现；mock 阶段 human_required=True 打标兜底。
- 🟡 业务规则校准：50万阈值与"认证供应商"判定标准（当前来自 business_rules.py，生产环境须从配置/SRM 读取）。
- 运行：`python -m sc5_purchase.agent`（mock 模式）。
