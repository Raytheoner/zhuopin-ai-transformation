## ADDED Requirements

### Requirement: 回件到达 SHALL 在 README 打第九态
企微机器人处理一条入站消息、完成归档与队列追行后，SHALL 尝试把该回件对应的跟进信在 README「发送状态」列改写为第九态 `📨 回件已到，待拆件 <UTC>`。

第九态 SHALL 语义为「回件物理到达、尚未拆件回灌」，MUST 仍被判为**在途**——串行闸 MUST NOT 因此打开。真正开闸仍须人拆件回灌后转闭环四态。

写入的时间戳 MUST 为 UTC 并显式带 `Z`。

#### Scenario: 在途信被标为第九态
- **WHEN** 收到一条能确定配对到某封在途信的文件类回件
- **THEN** 该信 README 状态列被改写为以 `📨 回件已到，待拆件` 开头、含 UTC 时间戳的值

#### Scenario: 第九态不开闸
- **WHEN** 某收信人最近一封的状态为第九态
- **THEN** 闸判定为锁

### Requirement: 原状态 SHALL 原样保留
改写 MUST 为「新前缀在前、原状态原样接在后」的追加形态，MUST NOT 覆盖原状态——「这封信何时推送」在该单元格之外没有任何副本，且转闭环态时仍要引用它。

新状态 MUST 写明溯源（触发本次改写的入信归档文件名）。

#### Scenario: 推送时间不被冲掉
- **WHEN** 原状态为 `✅ 已推送 2026-08-20 12:20 UTC`
- **THEN** 改写后的单元格仍逐字含该原状态，且以第九态前缀开头

### Requirement: 匹配不上 SHALL 不动 README 且 fail-loud
入信归档件与跟进信的配对 MUST 用与 `release` 侧同一份权威判据（归一化后 stem 逐字相等）。配对不上时 MUST NOT 修改 README、MUST NOT 尝试取锁，且 MUST 记审计事件并打印可见 WARN，MUST NOT 静默跳过。

#### Scenario: 纯文本回件不动 README
- **WHEN** 入信归档文件名主题段为 `文本反馈`
- **THEN** README 内容逐字未变，且输出一条 WARN、审计中出现未匹配事件

#### Scenario: README 行未带目标文件标注
- **WHEN** 无任何 README 行带 `目标文件：` 标注可与该回件配对
- **THEN** 同上

### Requirement: 写入 SHALL 走编辑锁并重试
写入 MUST 经协议〇.7 共享编辑锁（复用既有锁实现，MUST NOT 直接写文件绕开）。锁目标 MUST 以仓库相对、正斜杠形式传入，否则锁工具的 README 专属 `release` 校验会静默不执行。

`acquire` 失败 SHALL 按指数退避重试（默认上限 3 次）。重试用尽时 MUST 记审计事件、打印 WARN 并发出告警，MUST NOT 静默放弃；此时 README MUST 保持未修改。

锁不可用（未启用编辑锁）时 MUST 不写 README，MUST NOT 裸写。

#### Scenario: 锁忙重试后成功
- **WHEN** 前两次 `acquire` 报忙、第三次成功
- **THEN** 第九态被写入，且共尝试三次

#### Scenario: 重试用尽后告警且不改文件
- **WHEN** 所有重试均报锁忙
- **THEN** README 内容逐字未变，输出 WARN，告警通道收到一条消息，审计中出现锁忙事件

### Requirement: 幂等，且 SHALL 不覆盖更晚的状态
目标行当前状态已属闭环四态或已是第九态时，MUST 不做任何修改。

取锁成功后 MUST 重新读取并重新定位目标行再写入，MUST NOT 用取锁前读到的行位置直接写回——取锁前后之间该行可能已被他人改动。

#### Scenario: 同一回件重投不叠加
- **WHEN** 对同一份归档件连续调用两次
- **THEN** 第二次不修改文件

#### Scenario: 持锁后发现已被转闭环则不覆盖
- **WHEN** 取锁瞬间该行已被他人改为 `📥 已回件并回灌`
- **THEN** 不写入第九态，文件保留他人的闭环态

### Requirement: 桥一 MUST NOT 破坏归档主流程
本桥 SHALL 为归档主流程的旁路增强，任何失败 MUST NOT 向上抛出、MUST NOT 使一条已成功归档的回件被判为处理失败。告警通道自身抛出异常时同样 MUST 被吞掉并不影响返回。

本桥 MUST NOT 放开任何发送权限——它只写一个明确不开闸的中间态，两态语义与人工批准流程不受影响。

#### Scenario: 告警通道故障不影响返回
- **WHEN** 告警回调抛出异常
- **THEN** 函数正常返回锁忙结果，不向上抛
