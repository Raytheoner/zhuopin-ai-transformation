## ADDED Requirements

### Requirement: BOM 取数提取项次与替代料关系（C-1，2026-07-14 口径定稿）
`get_bom_for_products` SHALL 对每条 U9C BOM 主件行提取其项次（`m_sequence`）与子项类型（`m_componentType`），并读取其嵌套的替代料列表（`m_bOMCompSubstituteDTO4CreateSv`），为每条替代料生成对等的 `BomRow`（与主件行共享同一 `sequence`、`is_substitute=True`）。`BomRow` 新增的 `sequence`/`is_substitute` 字段 MUST 为可选（默认值 `""`/`False`），不改变现有调用方在不使用这两个字段时的行为。

#### Scenario: 主件行提取项次与类型
- **WHEN** BOM 主件行的 `m_componentType` 为标准（0）
- **THEN** 对应 `BomRow.sequence` 设为该行 `m_sequence`，`BomRow.is_substitute=False`

#### Scenario: 替代料嵌套列表生成对等 BomRow
- **WHEN** 某主件行携带非空的 `m_bOMCompSubstituteDTO4CreateSv` 列表
- **THEN** 为列表中每一条替代料生成一条 `BomRow`，`sequence` 与其所属主件行相同，`is_substitute=True`

#### Scenario: 无替代料时行为不变
- **WHEN** 某主件行的 `m_bOMCompSubstituteDTO4CreateSv` 为空或缺失
- **THEN** 只生成该主件行自身的 `BomRow`（`is_substitute=False`），不产生额外行，与本变更包实施前行为一致

#### Scenario: 现有调用方不受新增字段影响
- **WHEN** O2/SC7 等既有场景代码构造或消费 `BomRow` 但不读取 `sequence`/`is_substitute`
- **THEN** 其现有逻辑正常运行，字段新增不引发签名不兼容或行为变化
