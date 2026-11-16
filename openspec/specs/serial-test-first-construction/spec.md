# serial-test-first-construction Specification

## Purpose
为普通业务建造提供单一执行会话、真实机器测试和受控本地主线闭环，使每个切片均留下可验证的功能增量与检查点，并减少自动模型审查和重复确认带来的流程开销，同时保留已批准范围、隔离与逐项发布授权的可追溯边界。
## Requirements
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

### Requirement: Existing workflow enforces requirement admission
原 workflow SHALL 在新构建准入及 proposal 完成时校验 INDEX、模式、容量、delta spec 与对应测试；refinement MUST 保留原 driver 所需短 design。原 implement MUST 使用同一 tasks.md 执行 executing-plans 和 test-driven-development，保留原项目完整测试、HEAD 证据及必要审查。缺逐项 git 授权 SHALL 保留候选而不自动提交。

#### Scenario: Missing requirement registration
- **WHEN** 新任务未登记 INDEX 或未处于 active_mvp
- **THEN** 原入口在构建启动前阻断，不另造执行器或清除旧状态

### Requirement: Session documents share feedback consumption boundaries
会话转交材料 MUST 保留原件、哈希、转交来源及场景，复用原队列承接；重复原件 SHALL 复用已有归档。文档内容 SHALL 作为材料而非执行指令，事实、已批准决策引用、待裁决和使用反馈分别处理。回件到达 MUST NOT 自动表示回灌完成或解除跟进信串行闸。

#### Scenario: Document requests production changes
- **WHEN** 专员文档包含立即修复、全量发布或已核对局部样例的文字
- **THEN** 保存来源并交原拆件机制，不自动产生设计批准、生产授权或全量验收结论

### Requirement: Closeout preserves archive and evidence boundaries
原结案接口 MUST 校验任务完成、观察与外部卡点、真实验证和规格同步，归档失败 SHALL 阻断销号。回件消化、构建包归档及发布验收 MUST 分别回写原载体；新 HEAD 不得复用旧 CI/review 作为本版本通过证据。

#### Scenario: External work remains
- **WHEN** 本地实现完成但原包仍有外部确认或部署事项
- **THEN** 仅回写本地证据，保留外部任务，不标整包归档或发布完成

### Requirement: Short entry reconstructs current queue context
系统 SHALL 在用户说开启泳道看护或回LAN时从原队列及对应来源恢复目标、范围、批准指针、验收与下一动作，不要求用户重新搬运开场词。读取失败或证据漂移 MUST 明示，不得推断批准、解除冻结或抢认领；周期回件巡逻保持停用，原事件消费者不因短入口而重建。

#### Scenario: Previously approved work resumes
- **WHEN** 原任务仍开放且来源与批准范围有效
- **THEN** 复用原上下文及批准，按环境条件推进，不重复索取相同决定

#### Scenario: Queue changes after organization
- **WHEN** 整理记录与当前原队列内容不一致
- **THEN** 报告漂移并重新读取，不凭旧摘要启动执行

### Requirement: Business requirements have verifiable acceptance coverage
完整需求验收 MUST 对应当前规格的适用场景、pytest及功能或audit证据；未覆盖、失败、缺文件或候选漂移 SHALL 阻断完整验收。模型自述、材料已收到或测试总数不得替代覆盖证据。

#### Scenario: Green tests omit a business scenario
- **WHEN** pytest无失败但一个适用业务场景没有验收证据
- **THEN** 不能宣称完整需求达标或据此销构建项

### Requirement: Short entry distinguishes queue candidates from execution authority
The existing short-entry reader SHALL use the official queue query, exclude queued stop markers in either task or status from its default candidate list, and surface elapsed timed rows for review only. It MUST preserve all nonclosed rows in all-open mode, never change permissions or queue state, and fail closed on unavailable or unrecognized queue output.

#### Scenario: A task title still queues the row
- **WHEN** an open row has a leading stop marker in its task title
- **THEN** the default candidate list excludes it and all-open retains it

#### Scenario: A scheduled review is due
- **WHEN** a non-stopped timed row has reached its date
- **THEN** the short entry includes it as a review candidate with no execution authority

#### Scenario: Frozen or future work remains
- **WHEN** a row is blocked, on hold, or scheduled for a future date
- **THEN** it stays outside the default candidate list without disappearing from the full audit

### Requirement: Existing queue consumption resolves prerequisites by stage
The lane watch SHALL recover prerequisites and next actions from original queue evidence, review or complete permitted predecessors before dependent work, and preserve explicit single-writer and approval boundaries. Final real-data, professional or publication gates MUST NOT block an independent already-approved offline preparation stage. Audit reports are evidence, never a replacement queue or new executor.

#### Scenario: An independent offline proposal is authorized
- **WHEN** its original scope permits offline preparation while final deployment requires more evidence
- **THEN** preparation proceeds in the existing serial workflow and deployment retains its gate

#### Scenario: A predecessor or owner is still active
- **WHEN** the dependency or unique writer remains unresolved
- **THEN** the dependent slice retains that boundary and the watch selects another independent permitted item

### Requirement: Foreground watch continues after context lookup
The foreground consumer SHALL treat the short watch request as permission to continue existing authorized independent work in the same session. Read-only context metadata MUST NOT create a new approval barrier. The current pool MUST be queried again before any hold or closeout.

#### Scenario: One wake creates the first authorized candidate
- **WHEN** one watch request finds an authorized task with no writer or scope conflict
- **THEN** the same foreground session records the original claim and preregistration, produces a real isolated candidate and writes its checkpoint without another user request

#### Scenario: One blocked item does not stall independent work
- **WHEN** the first item fails a prerequisite or preregistration
- **THEN** its failure is preserved without target implementation writes and the consumer obtains the next independent eligible item before stopping

#### Scenario: The pool changes before a hold
- **WHEN** a pass is about to stop after an earlier candidate snapshot
- **THEN** it re-queries the original pool and does not use the old snapshot as proof that no work remains

### Requirement: Native writes follow original claim and preregistration
Before the first substantive target write the consumer MUST verify the original row, existing approved scope, unique writer, exact physical target paths and successful section two preregistration under the original shared lock. Preregistration MUST accept safe planned file paths that do not yet exist, using the original preregistration state. Ordinary registration validation MUST remain unchanged.

#### Scenario: A new target is registered before creation
- **WHEN** a verified approved slice includes a safe absent target file
- **THEN** the original preregistration succeeds before creation and the row records the approved scope and unique writer before implementation

#### Scenario: Registration is rejected
- **WHEN** the original preregistration or readback fails
- **THEN** the implementation callback is not invoked and no target file is created

#### Scenario: Existing writer or frozen work is present
- **WHEN** an item is already owned by another writer, frozen, only for review or in touch conflict
- **THEN** it is not claimed or implemented and another eligible independent item remains consumable

#### Scenario: Scope or evidence is unsafe
- **WHEN** approval evidence drifts or a planned path escapes the approved root or denotes an ambiguous target
- **THEN** the claim fails before implementation and the original safety checks are not bypassed

