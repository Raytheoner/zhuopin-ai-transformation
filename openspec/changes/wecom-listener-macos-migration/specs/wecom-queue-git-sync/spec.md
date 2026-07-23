## ADDED Requirements

### Requirement: 队列本地追加后自动同步到远端 master
系统在 `queue_appender.append_pending_task()` 于本地队列文件成功写入一行"待领"任务后，SHALL 自动尝试将该次改动提交并推送到 GitHub `origin/master`，提交信息 SHALL 采用 `bot(队列): 自动追行 #<task_id>` 格式，提交作者身份 SHALL 使用独立于 Paul 本人账号的本地 git 身份配置，不与人工提交混淆。

#### Scenario: 推送成功
- **WHEN** 本地追加成功且远端 `origin/master` 未在此期间被其他写手推进
- **THEN** 系统提交并推送成功，写入一条 `queue_sync_pushed` 审计事件，记录对应的 commit sha 与任务编号

### Requirement: 推送冲突时重新计算插入点与编号，不重放旧提交
当推送被 GitHub 拒绝（非 fast-forward，说明 `origin/master` 已被其他写手（人工/CC/另一次 bot 调用）推进）时，系统 SHALL 拉取远端最新内容、以最新内容为基准重新计算队列表格的插入点与任务编号，SHALL NOT 简单重放（rebase/cherry-pick）此前基于旧内容计算出的提交，以避免两个写手各自基于过期内容算出相同编号导致的编号冲突。

#### Scenario: 检测到远端已前进，重新计算后成功推送
- **WHEN** 推送被拒绝，且 `git fetch` 后确认 `origin/master` 相比推送时的本地基线有新提交
- **THEN** 系统将本地队列文件对齐到 `origin/master` 最新内容，重新调用队列追加逻辑计算出的任务编号 SHALL 大于该最新内容中已存在的最大编号，重新提交并推送

#### Scenario: 重算重试次数受限
- **WHEN** 连续 3 次"拉取→重算→提交→推送"均失败
- **THEN** 系统停止重试，进入降级路径（见下一需求），不无限重试阻塞后续消息处理

### Requirement: 同步失败时降级为本地暂存，不阻塞归档主流程
当远端同步在重试上限内未能成功时，系统 SHALL NOT 丢弃该条待追加任务信息，且 SHALL NOT 因同步失败而阻塞或回滚已完成的归档、门禁判定、部门群通报等既有动作。系统 SHALL 将该条任务信息写入本地暂存文件，并通过既有告警通道私信 Paul 说明"队列同步失败，一行待人工核对合并"。

#### Scenario: 重试耗尽后降级
- **WHEN** 重算重试已达上限（3 次）仍失败
- **THEN** 系统将任务描述/领取方/输入指针/期望产出等字段写入本地暂存文件（如 `reports/pending_queue_appends.jsonl`），记一条 `queue_sync_degraded` 审计事件，并调用告警通道发送私信

#### Scenario: 归档等其他动作不受同步失败影响
- **WHEN** 某条专员消息触发了归档 + 队列追加 + 远端同步三个步骤，且远端同步失败
- **THEN** 归档文件与本地队列文件的写入结果保持不变（不回滚），门禁判定与部门群通报按各自既有逻辑独立执行，不因同步失败而跳过或重复
