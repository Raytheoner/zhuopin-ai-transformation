## ADDED Requirements

### Requirement: 物料到货估算按多层递归展开取叶子件（B1，2026-07-13 定稿，无开关无条件生效）
`estimate_material_arrivals` SHALL 通过复用 `kit_engine.explode_bom` 递归展开 BOM，取叶子件（非任何 BOM 行 `product_id` 的最终物料）作为估算对象，取代现状"仅取 `level==1` 直接子件"的推导。半成品/子装配不出现在估算对象中，不被误查 SRM 承诺。本行为无条件生效（非开关控制）。

#### Scenario: 单层 BOM（无半成品）结果不变
- **WHEN** 某成品的 BOM 只有直接子件、无半成品嵌套
- **THEN** 估算对象与改造前的 `level==1` 推导结果一致

#### Scenario: 含半成品的 BOM 展开到真正原材料
- **WHEN** 某成品的直接子件是半成品（其下还有自己的 BOM）
- **THEN** 估算对象是该半成品下的叶子件（真正原材料），半成品本身不出现在估算对象或 SRM 查询清单里
