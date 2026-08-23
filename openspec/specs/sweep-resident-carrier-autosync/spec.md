# sweep-resident-carrier-autosync Specification

## Purpose
TBD - created by archiving change carrier-health-guard. Update Purpose after archive.
## Requirements
### Requirement: 常驻执行体名单 SHALL 由计划任务反查得出

sweep SHALL 枚举本机计划任务，取其 Action 的可执行路径与参数，**凡路径落在 `<repo_root>/.claude/worktrees/<name>/` 之下者，该 `<name>` SHALL 被判为常驻执行体**。

名单 MUST NOT 硬编码，MUST NOT 依赖仓库内维护的白名单——新增指向 worktree 的常驻任务须被自动纳入。

#### Scenario: 三个任务指向同一 worktree
- **WHEN** `ZhuopinAibotDevListener`／`ZhuopinDecisionReminderDaily`／`ZhuopinFollowupDispatchDaily` 的 Action 路径均在 `.claude/worktrees/wecom-service-home/` 之下
- **THEN** 执行体名单为 `{wecom-service-home}`，且记录其被哪几个任务引用

#### Scenario: 指向主工作区的任务不计为执行体
- **WHEN** `ZhuopinCommitSweep` 的 Action 路径在主工作区而非 `.claude/worktrees/` 之下
- **THEN** 该任务不产生执行体条目

### Requirement: 名单取不到时 MUST NOT 推断为零，且 MUST NOT 执行任何 ff

计划任务查询失败、不可用或无权限时，sweep MUST 输出「**执行体名单未取到**」及具体原因，MUST NOT 返回空名单后判为「零执行体、一切正常」，且 MUST NOT 对任何 worktree 执行 ff。

「查询成功且零执行体」与「查询失败」SHALL 是两种可区分的输出，MUST NOT 合并为同一措辞。

#### Scenario: 非 Windows 环境
- **WHEN** 计划任务查询命令不存在或执行失败
- **THEN** 日志明写「执行体名单未取到」及失败原因，本轮不执行任何 ff，且不产生「零落后」结论

#### Scenario: 查询成功但无任务指向 worktree
- **WHEN** 查询成功返回任务列表，但无任一 Action 路径落在 `.claude/worktrees/` 下
- **THEN** 日志明写「计划任务查询成功，无任务指向 worktree」，措辞与查询失败可区分

### Requirement: sweep SHALL 每轮把常驻执行体 `--ff-only` 对齐到 master

每轮 sweep（非 dry-run）SHALL 对每个常驻执行体执行 `--ff-only` 对齐，**不依赖任何阈值、不等待人工触发**。

理由 SHALL 记录在实现中：落后是**持续过程**（实测约 70 提交/天），一次性对齐动作无法治理持续过程——无论触发人是「自己想起来」还是「被机器提醒」。

对齐目标 SHALL 为本地 `master`（取不到时退 `origin/master`）。

#### Scenario: 落后的执行体被自动对齐
- **WHEN** 某常驻执行体落后 309 个提交、ahead ＝ 0、已跟踪文件干净
- **THEN** 本轮对其执行 `--ff-only`，对齐后落后为 0，且不产生告警

#### Scenario: 已对齐的执行体不做任何操作
- **WHEN** 某常驻执行体落后 0
- **THEN** 只在日志回显「已对齐」，不执行 merge

### Requirement: ahead > 0 时 MUST 停手告警，MUST NOT 强推

执行 ff 之前，sweep MUST 确认该执行体 `ahead`（相对 master 的独有提交数）为 0。

`ahead > 0` 时 MUST 停手、MUST NOT 执行 merge、MUST NOT 执行 rebase／reset／revert／cherry-pick 或任何会改写该执行体历史的操作，并 MUST 进入告警集合。

执行体内**已跟踪文件**有未提交改动时，MUST 停手告警，MUST NOT 执行 ff。

#### Scenario: 执行体有本地提交
- **WHEN** 某常驻执行体 ahead ＝ 2
- **THEN** 本轮不对其执行任何写操作，并告警「执行体领先 2 个提交，已停手不 ff」

#### Scenario: 执行体已跟踪文件脏
- **WHEN** 某常驻执行体 `git status --porcelain` 非空
- **THEN** 本轮不执行 ff，并告警说明是哪一条改动挡住了

#### Scenario: ff 被未跟踪文件挡住
- **WHEN** `git merge --ff-only` 因「未跟踪文件将被覆盖」而非零退出
- **THEN** 该执行体进入告警集合，正文含 git 的原始失败原因，且 MUST NOT 重试或强制覆盖

### Requirement: 重启 SHALL 按需触发，判据 SHALL 复用既有常驻服务白名单

ff 成功后，sweep SHALL 取本轮实际前进的提交所触碰的路径集合（`git diff --name-only <ff前HEAD>..<ff后HEAD>`），并 SHALL 用**既有** `_touches_resident_service`（队列 `#87` ⑶⑷ 的常驻服务运行体白名单）判定是否需要重启。

判定 MUST NOT 另写一套白名单或路径判据。

未触碰常驻服务代码路径时 MUST NOT 重启，MUST NOT 告警。

#### Scenario: ff 未触碰服务代码路径
- **WHEN** 本轮 ff 前进的提交只触碰了 `1-转型规划/` 下的文档
- **THEN** 不重启、不告警，日志回显「未触碰常驻服务代码路径 ⇒ 无需重启」

#### Scenario: ff 触碰服务代码路径
- **WHEN** 本轮 ff 前进的提交触碰了 `5-平台底座/wecom-aibot-service/` 下的文件
- **THEN** 判定为需要重启，并按自动重启开关决定是自动执行还是转人工

### Requirement: 自动重启 SHALL 由开关控制且缺省关闭

自动重启 SHALL 由 `.env` 中的 `CARRIER_AUTO_RESTART_ENABLED` 控制。

**键缺失、`.env` 不存在、读取失败或取值不可识别时 SHALL 一律视为关闭**——这是「重启生产服务」的开关，缺省必须是关的。

开关关闭且本轮需要重启时，sweep MUST 告警「代码已新、进程仍旧，需人工重启」并给出处置命令，MUST NOT 自行重启。

#### Scenario: 开关缺失即关闭
- **WHEN** `.env` 中不存在 `CARRIER_AUTO_RESTART_ENABLED`
- **THEN** 自动重启视为关闭，需重启时转为告警而非执行

#### Scenario: 开关关闭时需重启
- **WHEN** ff 触碰了服务代码路径且开关关闭
- **THEN** 该执行体进入告警集合，正文写明「代码已新、进程仍旧」并给出 `-RestartOnly` 命令

### Requirement: 自动重启 SHALL 委托既有重启脚本，MUST NOT 另写一套

开关开启且需要重启时，sweep SHALL 调用 `0-学习与工具/工具-执行体对齐重启.ps1 -RestartOnly` 执行重启与验活。

sweep MUST NOT 在自身内重新实现停服／验重启／验活的任一步骤。

退出码 SHALL 直接取自被调进程，MUST NOT 经由管道或 `cmd /c` 取得。

重启失败时 MUST 进入告警集合。

#### Scenario: 自动重启走同一实现
- **WHEN** 开关开启且本轮需要重启
- **THEN** 调用该脚本并以其退出码判定成败，人工执行与机器执行走同一实现

#### Scenario: 自动重启失败即告警
- **WHEN** 该脚本以非零退出码返回
- **THEN** 该执行体进入告警集合，正文含退出码与最后一行摘要

### Requirement: 告警语义 SHALL 是「有例外」而非「落后了」

告警集合 SHALL 只包含**需要人介入**的状态：ahead > 0 停手、工作区脏、ff 失败、名单/计数取不到、需重启但自动重启关闭、自动重启失败。

ff 成功且无需重启的正常路径 MUST NOT 产生任何推送。

告警 SHALL 复用 `_track_and_alert_standing_state`，MUST NOT 新增通知通道；再提醒间隔 SHALL 为 24 小时；告警 key SHALL 为 worktree 名，MUST NOT 包含任何会变的数值。

例外消除时 SHALL 自动推送解除通知。

#### Scenario: 正常对齐不推送
- **WHEN** 本轮把某执行体从落后 12 ff 到 0，且未触碰服务代码路径
- **THEN** 只在日志回显，不推送任何 webhook 消息

#### Scenario: 例外消除后自动解除
- **WHEN** 某执行体此前因 ahead > 0 告警过，本轮 ahead 归零并成功 ff
- **THEN** 推送解除通知，且该 key 从状态文件中移除

### Requirement: 每轮 SHALL 回显同步结果与开关状态

无论是否有例外，sweep SHALL 在日志中回显执行体个数、自动重启开关状态，以及每个执行体本轮的处置结果。

该回显 MUST NOT 因「本轮零例外」而被省略。

#### Scenario: 零例外时仍有回显
- **WHEN** 本轮所有执行体均已对齐或成功 ff
- **THEN** 日志仍逐项列出各执行体的处置结果，并写明自动重启开关当前状态

### Requirement: 本变更 MUST NOT 改动既有事件型部署提示

`_announce_resident_service_deployment_hint` 的判据、正文与触发时机 MUST 保持不变。

#### Scenario: 既有提示行为不变
- **WHEN** 某批 commit 触碰 `5-平台底座/wecom-aibot-service` 下的文件
- **THEN** 既有事件型部署提示照原样发出，与本变更新增的同步逻辑互不影响

