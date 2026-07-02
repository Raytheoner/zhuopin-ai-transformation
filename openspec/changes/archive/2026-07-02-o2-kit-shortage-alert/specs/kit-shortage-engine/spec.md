## ADDED Requirements

### Requirement: BOM 递归展开（explode_bom）
引擎 SHALL 接受 `list[BomRow]` 与 `list[ProductionPlan]`，递归展开多层 BOM，返回 `dict[str, float]`（物料ID → 毛需求量）。每层毛需求 = 父层传入量 × `qty_per_unit` × (1 + `loss_rate`)。中间件（product_id 列有记录）继续向下递归，自身不计入结果。遇循环引用时跳过，不抛异常。

#### Scenario: 单层 BOM 毛需求计算正确
- **WHEN** 生产计划 100 件成品 FIN001，BOM 含 MAT001（用量 2，损耗 0.05）
- **THEN** 返回 `{"MAT001": 210.0}`（100 × 2 × 1.05）

#### Scenario: 两层 BOM 递归展开叶节点
- **WHEN** FIN001 → SUB001（用量 1，损耗 0）→ MAT002（用量 3，损耗 0）
- **THEN** SUB001 不在结果中，返回 `{"MAT002": 300.0}`（100 × 1 × 3）

#### Scenario: 多成品需求合并同一物料
- **WHEN** FIN001 和 FIN002 各计划 50 件，均依赖 MAT001（各用量 2，损耗 0）
- **THEN** 返回 `{"MAT001": 200.0}`（50×2 + 50×2，合并同物料需求）

#### Scenario: 循环引用不死循环
- **WHEN** BOM 中 A → B → A（循环），生产计划要求 A 10 件
- **THEN** 函数正常返回，不抛异常，不无限递归

### Requirement: 缺口计算（calc_shortage）
引擎 SHALL 接受毛需求 dict、`list[InventoryRow]`、`list[PurchaseOrder]`，返回 `dict[str, float]`（只含缺口 > 0 的物料）。可用量 = 现有库存 - 安全库存 + Σ(在途未到货)，在途未到货 = `qty_ordered - qty_received`（按物料汇总所有 PO）。

#### Scenario: 库存充足无缺口
- **WHEN** 毛需求 100，库存 200，安全库存 50，无在途
- **THEN** 可用量 150 ≥ 100，该物料不在返回结果中

#### Scenario: 库存不足有缺口
- **WHEN** 毛需求 200，库存 100，安全库存 20，在途 50
- **THEN** 可用量 = 100-20+50 = 130，缺口 = 200-130 = 70.0

#### Scenario: 物料无库存记录视为零库存
- **WHEN** 毛需求中有物料 MAT999，但 inventory 列表中没有该物料记录
- **THEN** 可用量 = 0，缺口 = 全额毛需求

### Requirement: 底座 models 单一可信源
引擎 SHALL 使用 `zhuopin_platform.shared_tools.models` 的 `BomRow / InventoryRow / PurchaseOrder / ProductionPlan`，禁止定义重复的本地 dataclass。

#### Scenario: import 路径正确
- **WHEN** 读取 `kit_shortage_engine.py` 源码
- **THEN** 无 `from src.data_loader` 或 `from supplychain` 的 import，所有 dataclass import 来自 `zhuopin_platform.shared_tools.models`
