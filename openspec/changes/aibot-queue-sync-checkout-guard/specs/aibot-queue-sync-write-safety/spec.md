## Purpose

定义企微机器人队列 git 同步（`queue_git_sync.append_task_and_sync_to_git`）在非快进冲突重算时，对工作区队列文件执行销毁性操作（`reset --mixed` + `checkout --`）前必须满足的安全前提——防止协议〇.7/〇.8 允许存在的"人类会话已释放编辑锁但内容尚未提交"这一合法状态，被机器人的冲突重算逻辑静默销毁（队列 #287）。

## ADDED Requirements

### Requirement: 销毁性重算前必须校验预期差异
`append_task_and_sync_to_git` 在非快进冲突触发的重算路径中，MUST 在执行 `reset --mixed` / `checkout --` 之前，比较"本次追加预期产生的差异规模"（新增行数 ≤ 2 且删除行数 ≤ 1）与"磁盘内容相对已提交内容的实际差异规模"；实际差异超出预期规模时 MUST NOT 执行 `reset`/`checkout`。

#### Scenario: 磁盘只含本次追加的正常差异
- **WHEN** 冲突重算前磁盘上队列文件相对刚完成的本地 commit 的差异恰好是"新增一行任务＋高水位线自增"
- **THEN** `append_task_and_sync_to_git` 正常执行 `reset --mixed` + `checkout --` 并继续重算，行为与护栏引入前一致

#### Scenario: 磁盘含与本次追加无关的外来未提交内容
- **WHEN** 冲突重算前磁盘上队列文件的差异规模明显超出"新增一行＋高水位线自增"（如同时存在其他会话已 release 但未 commit 的多行改动）
- **THEN** `append_task_and_sync_to_git` MUST NOT 执行 `reset`/`checkout`，工作区文件内容保持不变

### Requirement: 护栏命中时不得丢弃已插入的本次追加内容
护栏判定磁盘存在外来内容时，MUST 撤销机器人自己刚创建的本地 commit（`reset --soft`，不改动工作区），使工作区恢复为"外来内容 ＋ 本次追加已插入的那一行"的混合未提交状态，MUST NOT 清空或覆盖工作区文件。

#### Scenario: 护栏命中后本次追加的行仍在磁盘上
- **WHEN** 护栏判定磁盘有外来内容并放弃本地 commit
- **THEN** 队列文件工作区内容中，本次追加算出的新任务行与判定前磁盘上的外来内容同时存在，均未丢失

### Requirement: 护栏命中必须留痕
护栏命中时 MUST 记录一条 audit 降级事件（复用 `queue_sync_degraded` 事件形状，`reason` 标注为区别于网络/冲突失败的独立取值），MUST 写入暂存记录供人工核对，MUST 发送私信告警且告警文案须说明"磁盘存在其它未提交内容、已跳过自动同步"，不得与网络/冲突类失败使用相同文案（避免人工误判为可通过重试解决）。

#### Scenario: 护栏命中产生可区分的降级记录
- **WHEN** 护栏拦截了一次销毁性重算
- **THEN** audit 日志、暂存文件记录、私信告警文案三处均可明确区分"因外来内容被拦截"与"因网络/编号冲突失败"两类降级原因

### Requirement: 护栏不改变既有三类失败语义的对外契约
护栏未命中时，`append_task_and_sync_to_git` 的行为（非快进重算成功推送、网络类失败保留本地 commit、重试耗尽 `reset --hard` 回到远端一致状态）MUST 与护栏引入前完全一致；函数签名与 `GitSyncOutcome` 返回值形状 MUST NOT 改变。

#### Scenario: 无外来内容时既有失败语义不受影响
- **WHEN** 磁盘不存在外来内容，且推送因网络原因失败（非非快进）
- **THEN** 函数行为与护栏引入前相同——本地 commit 被保留，不触发护栏逻辑
