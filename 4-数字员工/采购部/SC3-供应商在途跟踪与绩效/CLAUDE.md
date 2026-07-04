# CLAUDE.md — SC3 供应商在途跟踪与绩效（场景级记忆）

> 本文件是 SC3 场景的本地记忆/进度笔记，隔离于其他场景。
> 项目级上下文见仓库根 `CLAUDE.md`；SC3 规划权威见全景规划 §2.1.3 采购部 SC3 行、
> 实施计划 §一采购表、`1-转型规划/0-全景路线图/session接力-Phase1收口.md`。
> 本场景 = CC 建造车间产物；**不改规划文档**（那是 Cowork 的活）。

## 1. 场景定位

- **场景**：SC3 = 采购部第 3 个数字员工，供应商在途跟踪与绩效评分。
- **全景编号**：全景规划 §2.1.3 采购部 SC3（S1 筑基期场景）。
- **自动化等级**：L1 — 内部只读看板，无 L2 人工确认门禁触发，无对外推送。
- **MVP 范围**：在途风险实时评估（三色分级：高/中/低）+ 审计留痕。
  供应商绩效历史统计/评分、企微通知为后续迭代，不在本 MVP。
- **OEM 隔离**：不适用（SC3 读 SRM/ERP 内部采购数据，按根 CLAUDE.md §4 不强加 OEM 路由）。

## 2. 关键决策记录（Paul 拍板）

| 决策 | 结论 | 依据 |
|------|------|------|
| D2：`compute_dos` 放哪 | **A — SC3 场景本地** | O2 不消费 compute_dos；SC3 是第 1 消费方，rule-of-three 未触发；代码注释标注"第 2 消费方出现时提升到 `shared_tools/supply_metrics.py`" |
| D3：引擎接口 | 原样收割，不重写签名 | 确保与 supplychain `test_supplier_tracking.py` 等价；阈值保留（≤3天 high，≤7天 medium；DOS<5 high，DOS<10 medium） |
| D4：审计集成 | L1 写平台 audit | scenario=SC3，action=in_transit_risk_eval，automation_level=L1；引擎不含审计逻辑（纯算法），audit 只在 agent 胶水层 |
| 企微通知 | 本 MVP **不接 notifiers** | L1 内部看板，无对外推送需求；后续迭代加 |

## 3. 复用底座资产

- **模型**：`zhuopin_platform.shared_tools.models` — `PurchaseOrder / InventoryRow / BomRow / ProductionPlan / Supplier`（直接 import，不重建）。
- **CSV 连接器**：`zhuopin_platform.shared_tools.csv_connector` — `get_purchase_orders / get_inventory / get_bom / get_production_plan`（O2 已在用，SC3 沿用）。
- **审计**：`zhuopin_platform.audit.AuditLogger`（scenario="SC3"，append-only hash-chain，IATF 3 年留存）。
- **不使用**：连接器（SRM/ZpConnector，真实接入是后续任务）、Notifier（L1 无需）。

## 4. 红线（建造时守住）

- 先 mock/脱敏跑通逻辑，再切真实 SRM/ERP；真实接入是独立后续任务。
- 风险评估结果写平台 `audit`（automation_level=L1，scenario=SC3）。
- 零 `from supplychain` / `sys.path` 残留 — SC3 工程独立，不保留 supplychain 运行时依赖。
- `compute_dos` 放场景本地，**第 2 消费方出现前禁止提升底座**（rule-of-three，见 D2）。
- L1 场景无 L2 人工确认门禁；若未来升级到对外推送/自动催货，必须先过门禁评审。

## 5. 状态时间线

| 日期 | 状态 |
|------|------|
| 2026-06-10 | OpenSpec propose + design 审核通过（Paul 拍板 D2=A，compute_dos 场景本地）。 |
| 2026-06-10 | `/opsx:apply` 完成 MVP 核心（TDD 先写测试）：`intransit_engine.py`（SupplierRisk + _classify_risk + analyze + compute_dos）+ `agent.py`（写 audit）；mock CSV fixture 独立；pytest 全绿（等价对照 + 审计留痕验证）。 |
| 2026-06-10 | `/opsx:archive` 完成 → 变更归档至 `openspec/changes/archive/2026-06-10-sc3-intransit-tracking/`。 |
| 2026-07-02 | 进度完整性核实（阶段2 hygiene）：20/20 tasks 验证通过，含引擎算法、audit 写入、零依赖 supplychain。 |
| **当前** | **✅ SC3 MVP 完成**，等待真实 SRM/ERP 接入（独立后续任务）。 |

**Tasks 完成度**：`openspec/changes/archive/2026-06-10-sc3-intransit-tracking/tasks.md` 全部 [x]（7.5 git push 除外，已合 master）。

## 6. 关键依赖/前置（解锁条件）

- 🟡 真实 SRM 接入（携客云 SRM API）— 真实在途数据验证的前置；mock 阶段不阻断。
- 🟡 真实 ERP 接入（U9C ZpConnector，LAN/VPN）— 真实库存/BOM 数据的前置；mock 阶段不阻断。
- 🟡 供应商绩效历史数据（历史准时率等）— 绩效评分迭代的前置；本 MVP 不含。
- 运行：`python -m sc3_intransit.agent`（mock 模式，无需真实网络）。
