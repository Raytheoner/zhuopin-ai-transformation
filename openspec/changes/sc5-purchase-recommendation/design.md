## Context

**现状**：supplychain 已有完整采购建议算法（`purchase_recommendation.py`，依赖 `kit_analysis.explode_bom` + `business_rules.BusinessRulePolicy`）。本次是 `explode_bom`/`calc_shortage` 的第 2 个真实消费方（O2 为 #1），rule-of-three 触发，需先提升 kit_engine 到底座，再收割 SC5 场景。

**约束**：
- IATF 红线：`"待人工审核"` 建议不可自动执行（R1 ≥50万 / R2 无认证供应商），必须 L2 人工确认
- 底座 models（PurchaseOrder/InventoryRow/BomRow/ProductionPlan/Supplier）已就绪，不重建
- supplychain 只读，mock CSV 独立复制（主 mock 数据而非 logistics 子目录）

---

## Goals / Non-Goals

**Goals:**
- kit_engine 提升底座，O2 改 import，底座 + O2 tests 全绿
- SC5 场景收割完整采购建议算法，import 全走底座
- L1/L2 分桶 audit 留痕；L2 桶在 mock 模式标记 `human_required=True`（不实际阻塞，真实门禁是后续）
- mock CSV 验证：5 条缺料建议 / auto_total≈35850 / review_total≈640000
- 测试含与 supplychain `test_purchase_recommendation.py` 等价的黄金对照

**Non-Goals:**
- 真实 SRM/ERP 接入（后续任务）
- R3/R4/R5 规则（占位，Phase 3c）
- 实际自动下单执行（mock 阶段只输出建议）
- 企微通知（本 PR 不接 notifiers）
- 修改 supplychain 任何文件

---

## Decisions

### D1：kit_engine 提升到 `zhuopin_platform/agents/`（已核查，结论确定）

**事实依据**：`purchase_recommendation.py` 第 3 行 `from src.agents.kit_analysis import explode_bom`，直接调用。SC5 agent 胶水层还需 `calc_shortage`。O2 是消费方 #1，SC5 是消费方 #2，rule-of-three 触发。

**实施**：
1. 新建 `zhuopin_platform/agents/__init__.py`（如不存在）
2. 新建 `zhuopin_platform/agents/kit_engine.py`（从 O2 `o2_kit_shortage/kit_engine.py` 原样搬移）
3. O2 `o2_kit_shortage/kit_engine.py` 改为：
   ```python
   # kit_engine 已提升到底座，此文件保持为薄转发层（兼容现有 import）
   from zhuopin_platform.agents.kit_engine import explode_bom, calc_shortage  # noqa: F401
   ```
   或直接更新 O2 agent.py / test 的 import 路径。
4. 底座 tests 新增 `test_kit_engine.py`；O2 tests 保持，改 import 指向底座。

**接口对照**（O2 现有 vs 底座新增，完全一致）：
- `explode_bom(bom: list[BomRow], plans: list[ProductionPlan]) -> dict[str, float]`
- `calc_shortage(gross: dict[str, float], inventory: list[InventoryRow], purchase_orders: list[PurchaseOrder]) -> dict[str, float]`

---

### D2：business_rules（BusinessRulePolicy）场景本地（已核查，结论确定）

**事实依据**：`BusinessRulePolicy` 只被 `purchase_recommendation.py` import，无第 2 消费方，rule-of-three 未触发。放 SC5 场景本地 `sc5_purchase/business_rules.py`。

---

### D3：L2 门禁实现方式

`review_status == "待人工审核"` 的建议，在 agent 胶水层：
- audit 写入 `automation_level="L2"`，`decision` 含 `human_required=True`、触发规则列表、原因
- mock 阶段：打印人工审核清单但不阻塞（真实门禁需前端审批流，Phase 2 实现）
- `review_status == "可自动下单"` → `automation_level="L1"`

分两次 audit 事件（或一次事件含 L1/L2 分桶摘要），对齐 SC8 模式：一次 `in_transit_risk_eval` 写摘要，SC5 写 `purchase_recommendation_eval`。

---

### D4：文件结构

```
4-数字员工/采购部/SC5-采购建议与供应商遴选/
├── pyproject.toml
├── sc5_purchase/
│   ├── __init__.py
│   ├── purchase_engine.py     # 纯算法：build_recommendations + 遴选 + MOQ/MPQ + 下单日 + calc_material_earliest_dates
│   ├── business_rules.py      # BusinessRulePolicy（R1/R2），场景本地
│   └── agent.py               # 场景胶水：调用引擎，L1/L2 分桶，写 audit
├── tests/
│   ├── __init__.py
│   ├── mock_data/             # 从 supplychain/data/mock/ 复制（主目录，非 logistics）
│   │   ├── purchase_orders.csv
│   │   ├── inventory.csv
│   │   ├── bom.csv
│   │   ├── production_plan.csv
│   │   └── suppliers.csv
│   ├── test_purchase_engine.py   # MOQ/MPQ + 遴选 + 下单日 + cost 汇总（Golden Baseline）
│   └── test_sc5_agent.py         # agent 执行 + L1/L2 audit 留痕验证
└── README.md

# 底座同步修改：
5-平台底座/zhuopin_platform/zhuopin_platform/agents/
├── __init__.py
└── kit_engine.py              # explode_bom + calc_shortage（从 O2 搬移）

5-平台底座/zhuopin_platform/tests/
└── test_kit_engine.py         # 底座 kit_engine 单测

4-数字员工/运营部/O2-物料齐套预警/o2_kit_shortage/
└── kit_engine.py              # 改为薄转发：from zhuopin_platform.agents.kit_engine import ...
```

---

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| O2 import 路径变更导致 O2 tests 失败 | 搬移后立即跑 O2 tests，失败则修 import，不往下推 SC5 |
| BusinessRulePolicy 阈值与生产不一致（50万=mock值）| 注释标注"阈值来自 business_rules.AMOUNT_THRESHOLD，生产环境从配置读" |
| L2 门禁 mock 模式无实际阻塞 | audit 留痕 + human_required=True 标记，前端门禁 Phase 2 实现 |
| suppliers.csv 列名差异 | 已确认 supplychain 主 mock 与平台 fixtures 完全一致，直接复制 |

---

## Migration Plan

1. 新建分支 `feat/sc5-purchase-recommendation`
2. **先动底座**：新增 `zhuopin_platform/agents/kit_engine.py` + 底座 test → 底座 tests 全绿
3. **O2 改 import** → O2 tests 全绿（回归对照：O2 行为不变）
4. 新建 SC5 场景工程，先写测试再实现（TDD）
5. `pip install -e` 底座 + SC5
6. pytest 全绿（底座 + O2 + SC5 三套）
7. `/opsx:archive` → git commit + push

---

## Open Questions

无需拍板的开放问题（以上 D1-D4 均已凭代码事实确定）。实施前需快速确认底座 `agents/` 目录是否存在（已有骨架 `__init__.py`）。
