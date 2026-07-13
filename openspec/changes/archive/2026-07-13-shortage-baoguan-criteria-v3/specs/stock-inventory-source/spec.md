## ADDED Requirements

### Requirement: 共用子件现货占用挂钩点（B4 框架）
净额快照计算 SHALL 提供可选的 `priority_resolver` 挂钩点，用于未来按 PMC 月度优先级对共用子件现货做占用分配；默认（`priority_resolver=None`）行为与现状完全一致（各成品行独立判断现货是否满足自身毛需求，不做跨行占用扣减）。

#### Scenario: 未传 priority_resolver 时行为不变
- **WHEN** 调用净额快照计算时不传 `priority_resolver`（默认 None）
- **THEN** 计算行为与本变更包实施前完全一致，多个成品行共享同一子件现货时各自独立判断，不发生占用扣减

#### Scenario: 预留挂钩点供未来接入
- **WHEN** 未来 PMC 月度优先级数据源到位、传入实现了 `priority_resolver` 的解析器
- **THEN** 净额快照计算调用该解析器决定共用子件在多个竞争成品行间的占用顺序（本次不实现具体解析器逻辑，仅保证接口存在且可插拔）
