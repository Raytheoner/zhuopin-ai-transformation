## ADDED Requirements

### Requirement: 队列 MUST NOT 复述信状态
跨桌任务队列 SHALL NOT 复述一封跟进信的状态（「等某某#N 闭环」「待某某回件」这类快照），只允许写指针。`工具-队列结构lint.py` SHALL 新增一条判据检出此形态。

违规提示 MUST 给出替代写法（跑 `工具-跟进闸查询.py --to <收信人>`），MUST NOT 只说「不要写」。

#### Scenario: §一 未完成行的复述被检出
- **WHEN** §一 某 `[S:open]` 行状态列含「等姚祖怡采购部#16 闭环」
- **THEN** 输出一条告警，含该行号与替代指针命令

#### Scenario: §四 行的复述被检出
- **WHEN** §四 某行事项列含「等采购部#15 闭环」
- **THEN** 输出一条告警

#### Scenario: 写成指针的合规形态不被告警
- **WHEN** 行内写的是「串行闸状态跑 工具-跟进闸查询.py --to 姚祖怡」
- **THEN** 不告警

### Requirement: 历史记录 SHALL 豁免但 MUST NOT 静默
§二（commit 批次行）SHALL 完全不在扫描范围；§一 中 `[S:done]` 的行 SHALL 按「历史记录不追改」豁免。

两类豁免 MUST 被计数并打印，MUST NOT 静默跳过——静默豁免与本判据要治的毛病同族。

#### Scenario: §二 批次行不被误报
- **WHEN** §二 某历史批次行的 message 列含「等采购部#10 回件闭环」
- **THEN** 不产生告警，且该行不计入历史豁免计数（§二 根本不扫）

#### Scenario: §一 已完成行豁免但计数
- **WHEN** §一 某 `[S:done]` 行含复述形态
- **THEN** 不产生告警，但历史豁免计数加一并在输出中可见

### Requirement: 判据 SHALL 只命中紧凑的判据式引用
匹配窗口 SHALL 限于「等/待」与「部门#N」之间 ≤8 字、「部门#N」与「闭环/回件/回灌」之间 ≤8 字。放宽窗口会把**事后陈述**（如「其判例包已作为 采购部#16 发出、现等回件」）一并卷入，那类文字不是判据快照。

#### Scenario: 事后陈述不被误报
- **WHEN** 行内写的是「其判例包已作为 采购部#16 发出、现等回件，留在 open 会冒充可开工」
- **THEN** 不产生告警

### Requirement: 一期 SHALL 只告警，不影响退出码
本判据的命中 MUST NOT 计入 `lint()` 的违规列表、MUST NOT 改变进程退出码。输出 SHALL 含「二期基线」两个数（活行违规数、历史豁免数）。

上线时存量非零，一期即硬拦会立刻挡住所有人的 push；此策略与 `claude-progress-section-lint` 一致，与 `bootstrap-stub-lint`（上线前存量已实测清零、故直接 `--enforce`）的差别在于**存量是不是真的 0**，不在于严不严。

#### Scenario: 有告警时 lint 仍返回 0
- **WHEN** 队列中存在一处活行复述
- **THEN** `lint()` 返回空违规列表，进程退出码为 0，但告警与基线两数已打印

### Requirement: 权威判据模块可 import SHALL 被断言
`queue-structure-lint` 的既有「权威模块可 import」断言 SHALL 扩至 `zhuopin_platform.shared_tools.followup_gate`，并核验其关键符号存在。

理由与 `queue_table` 那条逐字相同：编辑锁对该模块有兜底，**那条降级路径本身是静默的**，本断言存在的唯一目的是让它红。

#### Scenario: 模块缺失时 CI 红
- **WHEN** 权威判据模块不可 import 或缺少关键符号
- **THEN** lint 报违规、退出码非 0
