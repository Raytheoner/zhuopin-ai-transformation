## Purpose

为普通业务建造提供单一执行会话、真实机器测试和受控本地主线闭环，使每个切片均留下可验证的功能增量与检查点，并减少自动模型审查和重复确认带来的流程开销，同时保留已批准范围、隔离与逐项发布授权的可追溯边界。

## ADDED Requirements

### Requirement: Serial execution by default
系统 SHALL 默认由一个主会话串行建造；未经用户针对该任务明确要求，不启动实现子代理、独立reviewer或并发泳道。新看护计划与启动入口 MUST 拒绝大于1的并行度；读取历史记录不得改写其计划或锁。

#### Scenario: Multiple eligible items
- **WHEN** 多项任务具备条件
- **THEN** 单主会话按优先级逐项处理，当前切片验证及检查点完成后才进入下一片

#### Scenario: Parallel legacy plan
- **WHEN** 调用者尝试启动并行度大于1的旧计划
- **THEN** 启动前明确返回本次串行政策不支持，并且不派生模型或修改原记录

### Requirement: Machine tests determine ordinary code acceptance
普通非安全相关业务代码 MUST 通过批准范围要求的真实pytest。切片执行定向测试，最终候选执行受影响项目完整回归；机器结果 MUST 绑定实际候选及测试源。模型自述或形式review不得覆盖失败、缺模块或未解释的skip。默认 SHALL 不增加模型独审；已明确要求独审的冻结旧合同、安全相关人工审核及授权事实检查不由测试代替。

#### Scenario: Green scoped tests and runnable evidence
- **WHEN** 最终候选的完整对应项目测试全绿且所需功能/审计自动验收通过
- **THEN** 普通任务进入本地整合准备，不自动开另一review会话

#### Scenario: Passing tests obtained by reducing scope
- **WHEN** 仅过滤子集、擅改断言或增加skip后得到退出0
- **THEN** 不标记最终代码验收通过，不进入合入

### Requirement: Bounded slices with preserved checkpoints
每片 MUST 只携带批准目标、版本、必要函数、失败用例、下一步及禁项；不得把完整历史intent、全景与长计划重新作为默认模型输入。每片在自然完成时保留文件/版本、实际测试、未完成项和下一节点，不能等到保护阈值才交接。

#### Scenario: Current calculation fails
- **WHEN** 当前片计算用例失败
- **THEN** 当前会话在同范围修复并验证，不重做已验收设计或新增通用恢复任务

### Requirement: Local integration requires exact authorization and safe Git state
本地主线采用仓库实际主分支名，当前为master。系统 MUST 在每个具体ff已有授权、候选scope/测试绑定有效、目标干净且可快进时仅执行ff-only；更新R5后继续下一步。系统 SHALL 不自动push或部署生产；测试全绿不生成对外授权。

#### Scenario: Authorized local fast-forward
- **WHEN** 用户已针对本项候选明确授权，目标干净、关系可快进且验证有效
- **THEN** 执行本地ff-only并更新接力，不执行push/生产部署

#### Scenario: Dirty target or divergent history
- **WHEN** 主线有既有修改或不可快进
- **THEN** 报告具体阻碍，保留已有文件，不stash/reset/强推或声称已合入
