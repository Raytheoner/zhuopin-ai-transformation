## Why

采购部缺少在途 PO 风险可见性——现有 ERP 看不到承诺交期临近/逾期信号，催货靠人工刷新，断料预警滞后。supplychain 已用真实数据验证过三色风险引擎，可直接收割进全景平台，避免重复建设。

## What Changes

- 新增 `4-数字员工/采购部/SC3-供应商在途跟踪与绩效/` Python 场景工程
- 收割 `supplier_tracking.analyze` + `_classify_risk` + `SupplierRisk`（来自 supplychain，保持算法原样）
- 收割 `compute_dos`（来自 supplychain/src/data_loader.py），放置位置待 Paul 拍板（见 design.md §决策点）
- 场景工程 import 全走 `zhuopin_platform`（connector/models/audit），消除跨工程引用与 sys.path hack
- 在途风险评估结果写平台 `audit`（scenario=SC3, action=in_transit_risk_eval, automation_level=L1）
- mock CSV fixture 独立复制进场景，不依赖 supplychain 路径
- 测试覆盖：三色分级逻辑、排序、received 跳过、srm_dates 覆盖、与 supplychain 原行为等价对照

## Capabilities

### New Capabilities
- `sc3-intransit-engine`: 在途 PO 三色风险分级引擎（analyze + _classify_risk + compute_dos），纯算法自包含，不掺审计/通知胶水
- `sc3-intransit-agent`: 场景入口，调用引擎，结果写 audit，mock CSV 跑通 L1 看板

### Modified Capabilities
<!-- 本次无存量 spec 级行为变更 -->

## Impact

- **新增文件**：`4-数字员工/采购部/SC3-供应商在途跟踪与绩效/`（pyproject.toml + 引擎 + agent + tests + mock CSV）
- **底座依赖**：`zhuopin_platform.shared_tools.models`（PurchaseOrder/InventoryRow/BomRow/ProductionPlan）、`zhuopin_platform.shared_tools.csv_connector`、`zhuopin_platform.audit`
- **compute_dos 归属**：待决策（场景本地 vs 提升到 shared_tools）——见 design.md
- **不修改**：supplychain 仓库（只读参考）、平台底座已有文件（除非 compute_dos 入底座）
- **测试影响**：新增 SC3 独立测试套件；底座现有测试不受影响
