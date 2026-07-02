# CLAUDE.md — O2 物料齐套预警（场景级记忆）

> 本文件是 O2 场景的本地记忆/进度笔记，隔离于其他场景。
> 项目级上下文见仓库根 `CLAUDE.md`；O2 规划权威见全景规划 §2.1.3 运营部 O2 行、
> 实施计划 §一运营表、`1-转型规划/session接力-Phase1收口.md`。
> 本场景 = CC 建造车间产物；**不改规划文档**（那是 Cowork 的活）。

## 1. 场景定位

- **场景**：O2 = 运营部第 2 个数字员工，物料齐套缺口预警。
- **全景编号**：全景规划 §2.1.3 运营部 O2（S1 筑基期场景）。
- **自动化等级**：L1 — 内部缺口预警看板，结果供运营/PMC 查看，无对外推送，无 L2 门禁。
- **MVP 范围**：齐套引擎（explode_bom + calc_shortage）+ 审计留痕；mock 模式跑通，真实 BOM/库存连接为后续任务。企微推送/告警通知为 O2 v2 范围。
- **底座贡献**：O2 是 `kit_engine` 的第 1 消费方（SC5 为 #2，rule-of-three 触发后提升）。当前 O2 的 `o2_kit_shortage/kit_engine.py` 已改为**薄转发层**（`from zhuopin_platform.agents.kit_engine import ...`）。
- **OEM 隔离**：不适用（O2 读内部 BOM/库存/生产计划，不涉 OEM 技术数据）。

## 2. 关键决策记录（Paul 拍板）

| 决策 | 结论 | 依据 |
|------|------|------|
| D1：引擎放哪（初始） | **A — O2 场景本地**（MVP 时 rule-of-three 未触发） | SC5 尚未设计，不预判接口形状；80行引擎重复代价极低 |
| D1 升级（SC5 后）：kit_engine 提升底座 | **已提升至 `zhuopin_platform/agents/kit_engine.py`**；O2 改为薄转发层 | SC5 是消费方 #2，rule-of-three 触发（2026-07-02 执行） |
| D2：收割方式 | 复制+改 import，不包装，不改函数签名 | 保留已验证算法原样，保持 explode_bom/calc_shortage 接口稳定 |
| D3：agent 入口 | `run_kit_alert()` 薄包装，audit_logger 可选（None = 静默） | 单测不依赖 sink，保持引擎纯算法 |
| D4：mock 夹具 | inline Python dict 夹具（三层 BOM），不用 CSV | 夹具自包含，不依赖外部文件；手工核对注释写结果 |
| 黄金基准目标值 | FIN001 缺口 = explode_bom 展开值；黄金对照偏差 < 1% | B6 修复后：kit_engine calc_shortage 空库存快照时 available=float(on_way)，不静默盲区 |
| 在途盲区修复（B6） | 无库存快照时显式标注 missing_snapshot=True，available=float(on_way) | 保守估算：以在途量为可用量，不静默；返回 (shortages, missing_snapshot) 二元组 |

## 3. 复用底座资产

- **kit_engine（底座）**：`zhuopin_platform.agents.kit_engine` — `explode_bom(bom, plans)` / `calc_shortage(gross, inventory, purchase_orders)` — 接口返回 `(shortages, missing_snapshot)` 二元组（B6 修复后）。
- **模型**：`zhuopin_platform.shared_tools.models` — `BomRow / InventoryRow / PurchaseOrder / ProductionPlan`。
- **审计**：`zhuopin_platform.audit.AuditLogger`（scenario="O2"，event_type="kit_shortage_analysis"，audit_logger 可选）。
- **不使用**：CSV 连接器（O2 用 inline 夹具）、Notifier（L1，企微推送为 v2 范围）。

## 4. 红线（建造时守住）

- 先 mock/脱敏跑通，再切真实 BOM/库存/在途数据；真实接入是独立后续任务。
- 齐套决策写平台 `audit`（automation_level=L1，IATF 3 年留存）。
- `calc_shortage` 无库存快照时，**不静默、不假装 available=0**：明确 missing_snapshot=True + available=float(on_way)（B6 修复红线，防在途盲区）。
- O2 `kit_engine.py` 保持薄转发层，禁止在其中写业务逻辑（底座化后的不变量）。
- L1 场景无 L2 人工确认门禁；若未来升级到自动补货建议，必须先过门禁评审。

## 5. 状态时间线

| 日期 | 状态 |
|------|------|
| 2026-06-早期 | O2 场景工程建立，kit_engine 收割为场景本地，pytest 全绿（20 tests），归档 `openspec/changes/archive/`（早期归档）。 |
| 2026-07-02 | SC5 执行时：kit_engine 提升底座（`zhuopin_platform/agents/kit_engine.py`），O2 `kit_engine.py` 改为薄转发层，O2 tests 回归零变更（20 tests 保持全绿）；B6 修复（calc_shortage 返回二元组，missing_snapshot）同批落入底座。 |
| 2026-07-02 | 变更包归档至 `openspec/changes/archive/2026-07-02-o2-kit-shortage-alert/`（Stage1 hygiene 清理）。 |
| 2026-07-02 | hygiene 核实：O2 tests 全绿（B6 修复后兼容），底座 kit_engine 接口稳定。 |
| **当前** | **✅ O2 MVP 完成**（底座提升同步完成），等待真实 BOM/库存接入（独立后续任务）。 |

## 6. 关键依赖/前置（解锁条件）

- 🟡 真实 BOM 接入（U9C ZpConnector.get_bom_for_products，LAN）— 真实齐套分析前置；mock 阶段不阻断。
- 🟡 真实库存/在途数据接入（U9C 库存/SRM 在途）— 真实预警前置。
- 🟡 `CommonEntity/Query` 外网开放（IT）— 生产计划/库存完整接入前置。
- 🟡 企微推送（O2 v2）— v1 不含，v2 接 Notifier + 运营群通知。
- 运行：`python -m o2_kit_shortage.agent`（mock 模式，inline 夹具，无需网络）。
