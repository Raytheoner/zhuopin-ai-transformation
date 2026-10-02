## Purpose

本能力规定卓品项目六类业务入口在Codex中的可观察行为、只读进度和验收边界，让已批准任务从启动到实际产物可追踪，并区分隔离模型验收、运行开关启用与生产交付，避免把旧引擎指令、静态源码或替身测试当作新引擎可用证据。

## ADDED Requirements

### Requirement: Explicit user entry routing
系统 SHALL 将开启泳道看护、看看泳道、值周计划和回LAN收口路由到当前可用的Codex机制，并保留原批准及业务边界。

#### Scenario: Human starts an approved task
- **WHEN** 用户发出开启泳道看护且候选与阶段批准满足条件
- **THEN** 系统从当前队列启动对应Codex任务，遇设计/发布停点保留真实状态，不转用旧引擎

#### Scenario: Progress request has no batch identifier
- **WHEN** 用户只说看看泳道
- **THEN** 系统通过正式只读接口发现相关批次及任务并报告真实阶段、停点、失败和可用证据，不启动或恢复任务，不扫描私有state目录

### Requirement: Current weekly plan uses existing governance
系统 SHALL 基于现时队列和原值周章程生成计划，区分手动完成和真实调度。

#### Scenario: Weekly plan is requested
- **WHEN** 用户请求值周计划
- **THEN** 系统生成或核实本期计划的任务负责人、截止和承接，遵守长度/四节/锁登记，不把旧文件或已暂停调度宣称为当前自动执行

### Requirement: Native reply intake evidence
系统 SHALL 用真实Codex模型和实际派发/监听接缝验证脱敏回件归档拆件，保留任务与产物追踪。

#### Scenario: Synthetic reply is processed in isolation
- **WHEN** 隔离fixture收到合法脱敏回件
- **THEN** 实际派发器调用Luna完成档案与队列产物并留下原生工具/hooks证据，所有状态和队列留在fixture，重复回件不重复处理

#### Scenario: Production consumer remains unapproved
- **WHEN** 只有隔离验收完成且生产开关尚未针对实际范围放行
- **THEN** 系统保持生产消费者原状态并明确区分监听运行与自动消费通过

### Requirement: Version bound acceptance and guarded LAN closeout
系统 SHALL 将建造/CI/review/发布证据绑定最终候选版本；LAN与外发保留具体对象授权。

#### Scenario: Approved design is adopted on a repaired baseline
- **WHEN** 原批准设计被承接到修复后基线
- **THEN** 系统核原设计字节不变并记录新任务与实际HEAD绑定，不使用旧任务批准文件或旧HEAD报告冒充

#### Scenario: LAN is unavailable or unknown
- **WHEN** 用户要求回LAN收口但当前探针不是on
- **THEN** 系统保留待办和转出证据，不执行生产部署或声明部署完成

#### Scenario: Six entry acceptance is incomplete
- **WHEN** 通用建造链通过而回灌或其它入口仍缺证
- **THEN** 系统报告具体未闭合入口，不宣称完整workflow MVP通过