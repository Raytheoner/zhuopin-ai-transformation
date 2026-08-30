## Purpose

在共享文档编辑锁的 `release` 咽喉上校验本次持锁期间触碰的 `.md` 文件中的 opener
代码块，防止缺 `set_session_title` 或缺子任务例外句的 opener 被派出——事后 lint
只扫已跟踪文件、看不见刚写出还未 commit 的高危时刻，本能力补上这个缺口。

## Requirements

### Requirement: release SHALL 校验本次触碰的 .md 中的 opener 块
`release` MUST 取本次持锁期间触碰的 `.md` 文件，扫其中的 opener 代码块（含 `【设置】` 的 fenced block），按块声明的执行环境分流校验；不过 MUST 拒绝 release（fail-closed），MUST NOT 静默放行。

#### Scenario: CC 块缺 set_session_title
- **WHEN** 本次触碰的 `.md` 含一个 `【设置】执行环境：CC` 的 opener 块，块内无 `set_session_title`
- **THEN** 拒绝 release，指出文件与块，提示补第 3 行

#### Scenario: CC 块有 title 但无子任务例外句
- **WHEN** 块内有 `set_session_title` 而无「例外／跳过本行」字样
- **THEN** 拒绝 release（该写法会让 Task/Agent 子任务把父 session 改名，2026-08-28 实撞）

#### Scenario: 写对的 opener 放行
- **WHEN** CC 块含 `set_session_title` 且含子任务例外句
- **THEN** 通过，不产生告警

### Requirement: 校验 SHALL 按执行环境分流，Cowork 块 SHALL NOT 被要求 set_session_title
`mcp__ccd_session_mgmt__set_session_title` 在 Cowork 侧不存在（2026-08-27 实测）。环境为 `Cowork` 的块 MUST NOT 被校验该项；`【设置】` 未声明环境的块 MUST NOT 被校验（宁可漏，不误伤）。

#### Scenario: Cowork opener 不被误伤
- **WHEN** 本次触碰的 `.md` 含 `【设置】执行环境：Cowork` 的 opener 块且无 `set_session_title`
- **THEN** 通过，不拒绝

### Requirement: 判据 SHALL 复用 opener lint 的实现，SHALL NOT 另写一份
本守卫 MUST 复用 `工具-opener块lint.py` 的块解析与判据函数；MUST NOT 复制或重写判据逻辑。改判据 MUST 同时更新两处调用点，并在两处各留指针。

#### Scenario: 判据变更
- **WHEN** 形态判据需要修改
- **THEN** 只改一处正本，lint 与 release 两处行为同步变化

### Requirement: 回显 SHALL 如实声明覆盖边界
无论有无发现，MUST 打印一行「已校验本次触碰的 N 个 `.md`，其中含 opener 块 M 个」。MUST NOT 使用「opener 已全部合规」一类暗示全覆盖的措辞——本守卫**只覆盖走队列登记流程的 opener**，未登记路径仍是人守。

#### Scenario: 零发现时
- **WHEN** 本次触碰的 `.md` 中没有任何 opener 块
- **THEN** 仍打印回显（N 个 `.md`／0 个 opener 块），使「没问题」与「没跑」可区分

### Requirement: 逃生阀 SHALL 为行内标记，SHALL NOT 提供命令行开关
确需放行时，MUST 在本次 note 或本次触碰的队列行内写 `opener豁免：<理由>`。MUST NOT 提供单独的 `--force` 开关——opener 漏 title 无正当紧急场景，加开关会让豁免变廉价。

#### Scenario: 带理由放行
- **WHEN** note 内含 `opener豁免：<理由>`
- **THEN** 放行并把理由随本次记录落盘、进入版本历史
