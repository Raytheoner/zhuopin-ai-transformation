## ADDED Requirements

### Requirement: kit_engine 底座化
平台SHALL将 explode_bom + calc_shortage 提升至 `zhuopin_platform/agents/kit_engine.py`，作为跨场景共享算法引擎。

#### Scenario: explode_bom 递归展开
- **WHEN** 给定 BOM 列表和生产计划列表
- **THEN** 递归展开至叶节点，返回 `{material_id: 合计毛需求}`（子件不计入结果，损耗率累乘）

#### Scenario: calc_shortage 缺口计算
- **WHEN** 给定毛需求、库存、在途 PO
- **THEN** 返回 `{material_id: 缺口数量}`（仅含缺口 > 0 的物料）；可用量 = 当前库存 - 安全库存 + 在途未收货

#### Scenario: O2 兼容性
- **WHEN** O2 从底座 import kit_engine
- **THEN** O2 所有现有测试保持全绿，行为零变更

#### Scenario: 防循环引用
- **WHEN** BOM 中存在循环引用关系
- **THEN** 不进入死循环，使用 visited 集合保护
