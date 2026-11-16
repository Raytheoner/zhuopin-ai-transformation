## ADDED Requirements

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
