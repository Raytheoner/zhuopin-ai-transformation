## Context

**现状**：supplychain 仓库已有经真实 SRM 数据验证的在途跟踪引擎（`supplier_tracking.py`，123 行）。该引擎依赖 `compute_dos`（`data_loader.py:207`），后者计算各物料库存可用天数（DOS = 可用库存 / 日均需求）。

**目标**：将引擎收割进全景平台，落成采购部 SC3 数字员工场景，消除跨仓库引用，接入审计留痕。结构对齐 O2-物料齐套预警的既有模式（pyproject + 场景模块 + tests + mock CSV）。

**约束**：
- `PurchaseOrder / InventoryRow / BomRow / ProductionPlan / Supplier` 已在 `zhuopin_platform.shared_tools.models`，不建重复契约（IATF 单一可信源）
- `zhuopin_platform.shared_tools.csv_connector` 和 `zhuopin_platform.audit` 可直接 import
- supplychain 只读参考，mock CSV fixture 独立复制，不保留运行时依赖
- Phase 1 阶段：mock CSV 跑通，真实 SRM/ERP 接入是后续任务

---

## Goals / Non-Goals

**Goals:**
- 收割 `analyze` + `_classify_risk` + `SupplierRisk` + `compute_dos`，保持算法与 supplychain 原测试等价
- 场景工程 import 全走 `zhuopin_platform`，零 sys.path hack，零 supplychain 运行时依赖
- 在途风险结果写 `zhuopin_platform.audit`（scenario=SC3，automation_level=L1）
- mock CSV fixture 独立、测试全绿

**Non-Goals:**
- 真实 SRM / ERP 接入（后续任务）
- 供应商绩效历史统计 / 评分（后续 SC3 迭代，本 MVP 只做实时在途风险）
- 企微通知（L1 内部看板，无对外推送，本 PR 不接 notifiers）
- 修改 supplychain 仓库任何文件

---

## Decisions

### D1：引擎文件结构（对齐 O2 模式）

```
4-数字员工/采购部/SC3-供应商在途跟踪与绩效/
├── pyproject.toml
├── sc3_intransit/
│   ├── __init__.py
│   ├── intransit_engine.py     # 纯算法：SupplierRisk + _classify_risk + analyze + compute_dos
│   └── agent.py                # 场景胶水：调用引擎，写 audit，格式化输出
├── tests/
│   ├── __init__.py
│   ├── mock_data/              # 独立 CSV fixture（从 supplychain/data/mock/logistics/ 复制）
│   │   ├── purchase_orders.csv
│   │   ├── inventory.csv
│   │   ├── bom.csv
│   │   └── production_plan.csv
│   ├── test_intransit_engine.py    # 三色分级 + 边界 + 等价对照
│   └── test_sc3_agent.py           # agent 调用 + audit 留痕验证
└── README.md
```

**理由**：引擎（纯算法）与胶水（audit/通知）分离，未来搬移/复用引擎不拖带场景依赖；与 O2 `kit_engine.py` / `agent.py` 拆分模式一致。

---

### D2：`compute_dos` 放哪？—— **已决策：A（SC3 场景本地）**

**决策**：`compute_dos` 放在 `sc3_intransit/intransit_engine.py` 内，与引擎一起，不提升底座。

**更正依据**（proposal 阶段的建议 B 基于错误前提，此处修正）：
- 原建议 B 的前提"O2 是消费方 #1"**有误**——查 O2 的 `kit_engine.py` 实际代码，O2 用的是 `calc_shortage`（缺口分析），**根本不使用 `compute_dos`**。
- `compute_dos` 当前唯一消费方是本次 SC3，不是"第 2 消费方"，而是**第 1 消费方**。
- 项目约定（`supplychain收割与全景推进策略.md` §引擎落位）明确：**第 2 个真实消费方出现前不抽象**（rule of three）。SC3 是第 1 消费方，提升底座属于过早抽象。

**实施**：`compute_dos` 放场景本地，代码注释标注"**待第 2 消费方出现时提升到 `zhuopin_platform/shared_tools/supply_metrics.py`**"，届时照两份具体实现定接口。

---

### D3：引擎接口保持原样（不重写）

`analyze` / `_classify_risk` / `SupplierRisk` 签名、风险判定阈值（≤3天 high、≤7天 medium；DOS<5 high、DOS<10 medium）、排序逻辑全部保留，确保与 supplychain `test_supplier_tracking.py` 等价。

connector 接口：`get_purchase_orders() / get_inventory() / get_bom() / get_production_plan()` 已是底座 `csv_connector.py` 的标准接口，直接用。

---

### D4：审计集成（L1，不阻塞）

agent.py 调用 `analyze()` 后，将结果摘要（风险计数 + 高风险 PO 列表）写入 `AuditLogger`：
- `scenario = "SC3"`
- `action = "in_transit_risk_eval"`
- `automation_level = "L1"` — 内部只读看板，无 L2 人工确认门禁触发
- `details` 含 `total_pos`、`high_count`、`medium_count`、`low_count`

审计不在引擎内，只在 agent 胶水层，保持引擎纯算法。

---

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| compute_dos 仅 SC3 一个消费方，未来第 2 消费方出现时需手动提升 | 代码注释标注提升触发条件；策略文档已记录 rule-of-three 约定 |
| mock CSV 格式与底座 csv_connector 期望不一致 | 从 supplychain 复制原始 fixture，不重写；先跑平台 csv_connector 测试确认格式 |
| 底座 csv_connector 加载列名与 supplychain CSVConnector 不同 | 收割前先比对两边列名，若有差异在 mock_data 修正 CSV 而非改引擎 |
| 引擎 SupplierRisk 的 `risk_reasons` 在 audit details 序列化时含中文 | JSONL 写入时 ensure_ascii=False，底座 audit 已处理此场景 |

---

## Migration Plan

1. 新建分支 `feat/sc3-intransit-tracking`
2. 新建 SC3 场景工程，收割引擎
4. 复制 mock CSV fixture，对齐列名
5. 先写测试（等价对照 + 新审计验证），再实现
6. `pip install -e ../../../5-平台底座/zhuopin_platform && pip install -e .`
7. pytest 全绿
8. `/opsx:archive` → git commit + push

---

## Open Questions

1. ~~compute_dos 放哪？~~ → **已决策 A，见 D2**。
2. ~~底座 `csv_connector` 的 `get_bom()` / `get_production_plan()` 是否已实现？~~ → **已确认**，`csv_connector.py` 四个方法均已实现，O2 在用。
