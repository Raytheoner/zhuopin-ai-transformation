## Why

采购部缺少系统化的采购建议生成能力——当前 MRP 运算、供应商遴选、MOQ/MPQ 约束计算、最迟下单日推算全靠人工。supplychain 已用真实数据验证过完整算法（`purchase_recommendation.py` + `business_rules.py`），可直接收割进全景平台。同时，本次是 `kit_engine`（explode_bom + calc_shortage）的第 2 个真实消费方，rule-of-three 触发，需同步把 kit_engine 提升到底座。

## What Changes

- 提升 `kit_engine`（explode_bom + calc_shortage）到 `zhuopin_platform/agents/kit_engine.py`（新建）
- O2 齐套场景改一行 import → 从底座取，回归测试全绿
- 新建 `4-数字员工/采购部/SC5-采购建议与供应商遴选/` 场景工程
- 收割 `build_recommendations` + `select_supplier` + `calc_purchase_qty` + `calc_order_date` + `calc_material_earliest_dates`（保持算法原样）
- 收割 `BusinessRulePolicy`（R1 金额阈值 ≥50万 / R2 无认证供应商）放场景本地
- 场景 import 全走 `zhuopin_platform`（connector/models/audit），零 supplychain 运行时依赖
- `review_status == "待人工审核"` → automation_level=L2（IATF 红线：金额 >50万 或 新供应商 必须人工确认）
- `review_status == "可自动下单"` → automation_level=L1
- 采购建议结果写平台 `audit`（scenario=SC5）

## Capabilities

### New Capabilities
- `sc5-kit-engine-platform`: kit_engine（explode_bom + calc_shortage）提升到底座 `zhuopin_platform/agents/`，O2 改 import
- `sc5-purchase-engine`: 采购建议纯算法引擎（build_recommendations + 遴选 + MOQ/MPQ + 下单日 + BusinessRulePolicy），场景本地
- `sc5-purchase-agent`: 场景入口，调用引擎，L1/L2 分桶写 audit，mock CSV 验证

### Modified Capabilities
- `platform-kit-engine`: O2 从场景本地 kit_engine 改 import `zhuopin_platform.agents.kit_engine`（接口不变，无行为变更）

## Impact

- **底座新增**：`zhuopin_platform/agents/kit_engine.py`（约 60 行，explode_bom + calc_shortage）
- **O2 修改**：`o2_kit_shortage/kit_engine.py` 改一行 import，逻辑零变更；O2 + 底座 tests 须全绿
- **新增文件**：`4-数字员工/采购部/SC5-采购建议与供应商遴选/`（pyproject + 引擎 + agent + tests + mock CSV）
- **底座依赖**：`zhuopin_platform.agents.kit_engine`（新）、`zhuopin_platform.shared_tools.models`、`zhuopin_platform.shared_tools.csv_connector`、`zhuopin_platform.audit`
- **不修改**：supplychain 仓库；SC3 / SC8 / SC1 任何文件
