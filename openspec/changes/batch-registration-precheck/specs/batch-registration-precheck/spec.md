## ADDED Requirements

### Requirement: §二 批次登记文件清单须通过双重预检
`append-row --section 二` 与 `edit-row`（针对 §二 行）写入前，SHALL 对"文件清单"字段内每一个反引号 `` `...` `` 包裹的字符串做形态校验与 git 归属校验；任一字符串未通过 SHALL 拒绝整次写入并保持原文件不变。

拒绝时 MUST 逐一打印不合格的反引号串原文及其不合格原因（fail-loud），不得只给一句笼统提示。

#### Scenario: 合格文件清单通过预检
- **WHEN** 文件清单内每个反引号串都是仓库根相对路径，且在主仓 git 脏集内、或为未跟踪新文件、或在最近 3 个 commit 内被触碰
- **THEN** 预检通过，`append-row`／`edit-row` 照常写入

#### Scenario: 路径形态但文件不存在
- **WHEN** 反引号串是仓库根相对路径的形态，但该路径在文件系统中不存在
- **THEN** 拒绝写入，提示该串因"路径不存在"不合格

#### Scenario: 非路径的自然语言描述
- **WHEN** 反引号串是一段自然语言描述而非路径（不属于既有豁免的通配符/目录前缀/CLI 参数/代码引用形态）
- **THEN** 拒绝写入

#### Scenario: 速记拒绝
- **WHEN** 反引号串含"同上"或"同名"字样
- **THEN** 拒绝写入，不论其是否恰好指向一个真实存在的路径

#### Scenario: git 状态不可得时的部分 fail-open
- **WHEN** 目标目录不是 git 工作区，或 git 调用本身失败
- **THEN** 形态校验与速记校验仍然生效；仅 git 归属校验这一半放行，不因整体 git 异常而拒绝全部写入

### Requirement: 队列文件自身改动须在批次处理前即刻兜底落库
sweep 的 `main()` SHALL 在处理 §二 待处理批次之前，检查两份队列文件中是否存在"当前无任何待处理 §二 行"却仍处于 git 脏集内的文件；若存在，SHALL 先以固定 commit message `docs(队列): 锁流程自带改动即刻落库` 单独提交这些改动，再继续批次处理主循环。

该判断 MUST NOT 提前提交一份仍有待处理（含暂缓/阻塞）§二 行的队列文件——即便该行未被任何批次清单字面覆盖，只要该文件还有待处理行，就视为"仍有批次在盯着它"。

#### Scenario: 队列文件改动未被任何批次覆盖，即刻兜底提交
- **WHEN** 两份队列文件中某一份存在改动，且该文件当前没有任何待处理 §二 行
- **THEN** sweep 在处理批次前先单独提交该文件改动，commit message 精确等于固定字符串

#### Scenario: 存在暂缓批次时不提前冲掉暂缓状态
- **WHEN** 队列文件存在改动，且该文件当前有一个因自身歧义暂缓（待处理）的 §二 行
- **THEN** sweep 不对该文件执行即刻兜底提交；该行按批次处理主循环的既有暂缓逻辑处理，日志给出"本轮无批次可落库"一类说明

### Requirement: reconcile 阶段按批次归属对脏文件分流 autostash
`_reconcile_with_origin_and_push` 在需要 rebase（`behind > 0`）时，SHALL 将当前脏文件分为"本轮批次清单内"与"清单外"两组：清单外文件 SHALL 被 `git stash push -u` 按路径精确 stash，并在 rebase／ff-only 或 push 成功后 pop 回来；清单内文件 SHALL NOT 被 stash，但 SHALL 被记录为告警。

stash pop 发生冲突时，SHALL 保留 stash 现场并 abort 当次 reconcile，SHALL 通过既有告警通道报错，MUST NOT 静默吞掉冲突。

#### Scenario: 清单外脏文件被 stash 并在 rebase 后还原
- **WHEN** rebase 前发现某个脏文件不在本轮任何批次的文件清单集合内
- **THEN** 该文件被按路径 stash；rebase／push 完成后被 pop 回工作区，内容与 stash 前一致

#### Scenario: 清单内脏文件不被 stash 仍发告警
- **WHEN** rebase 前发现某个脏文件在本轮某个批次的文件清单集合内
- **THEN** 该文件不出现在被 stash 的文件列表里；reconcile 仍对其发出告警

#### Scenario: pop 冲突时中止而非吞掉
- **WHEN** stash pop 时发生合并冲突
- **THEN** reconcile abort，stash 保留不丢，告警通道收到一条错误记录

### Requirement: sweep 日志按周轮转，保留 4 周
`reports/sweep-commit.log` SHALL 按"一次 sweep 运行"块（以 `=== sweep 运行 ... ===` 起始标记切分）轮转，`reports/hooks-audit.jsonl` SHALL 按每行的 `ts` 字段轮转；两者均 SHALL 只保留最近 4 周的内容，且 SHALL 各自独立运作（一个文件的轮转异常不影响另一个）。无法解析的块或行 MUST 被保守保留，MUST NOT 被当作"过期"直接丢弃。

#### Scenario: 超过 4 周的运行块被轮转掉
- **WHEN** `sweep-commit.log` 中存在早于当前时间 4 周以上的完整运行块
- **THEN** 轮转后该运行块不再出现在文件中，4 周以内的运行块原样保留

#### Scenario: 无法解析的内容不被误删
- **WHEN** 日志中存在一段无法按既定格式解析出时间戳的内容
- **THEN** 轮转逻辑保留该内容，不因解析失败而将其视为过期删除
