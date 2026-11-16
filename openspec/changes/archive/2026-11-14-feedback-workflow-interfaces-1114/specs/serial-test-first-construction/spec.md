## ADDED Requirements

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
