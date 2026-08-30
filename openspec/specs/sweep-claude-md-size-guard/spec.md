# sweep-claude-md-size-guard Specification

## Purpose
TBD - created by archiving change carrier-health-guard. Update Purpose after archive.
## Requirements
### Requirement: 落库 sweep SHALL 守卫必载 `CLAUDE.md` 的尺寸

每轮 sweep SHALL 量取仓库内 `CLAUDE.md` 的**字节数**并与阈值比对。

覆盖范围 SHALL 为：根 `CLAUDE.md`、`4-数字员工/**/CLAUDE.md`、`5-平台底座/*/CLAUDE.md`。

阈值 SHALL 为：根文件 **48 KB**（49,152 字节，只降不升的棘轮——见下一条 Requirement）；场景与底座文件 **50 KB**（51,200 字节）。

量取对象 SHALL 是 sweep 自身 `repo_root` 下的文件真身；`.claude/worktrees/**` 下的副本 MUST NOT 被纳入——它们是历史版本，对其告警既无意义又会持续误报。

尺寸 MUST 以字节计，MUST NOT 以字符数或行数替代。

#### Scenario: 根文件超限
- **WHEN** 根 `CLAUDE.md` 字节数 > 49,152
- **THEN** 该文件被判为超限并进入告警集合

#### Scenario: 场景文件超限
- **WHEN** `4-数字员工/财务部/FI2-三单匹配自动对账/CLAUDE.md` 字节数 > 51,200
- **THEN** 该文件被判为超限并进入告警集合

#### Scenario: worktree 副本不参与判定
- **WHEN** `.claude/worktrees/<任一>/CLAUDE.md` 字节数超过任一阈值
- **THEN** 该文件不进入告警集合，且不出现在回显中

### Requirement: root `CLAUDE.md` 尺寸阈值 SHALL 为只降不升的棘轮
根文件阈值（`CLAUDE_MD_ROOT_BYTE_CAP`）SHALL 只降不升——调高阈值 MUST 在提交里显式说明理由，MUST NOT 为容纳新增内容而顺手调高。该棘轮语义 MUST NOT 施用于场景与底座文件（后者阈值维持经验值，不随棘轮收紧）。

每轮回显 SHALL 在根文件实测值低于阈值 1,024 字节以上时，额外提示「可将 cap 下调至 <实测值 + 512>」，使瘦身成果被机器记住而非依赖人记得目标值。

#### Scenario: 瘦身后阈值可收紧
- **WHEN** `#381` 落地后 root 降至 42,000 B（低于阈值超过 1,024 B）
- **THEN** 回显提示「可将 cap 下调至 42,512」，下一次触碰时收紧

#### Scenario: 有人让 root 变大
- **WHEN** 某次改动使 root 超过 48 KB
- **THEN** 当轮告警，要求同批 one-in-one-out 或显式说明理由调高

### Requirement: 根文件顶部进度段跨批次日期 SHALL 同为超限判据

根 `CLAUDE.md` 顶部进度段内出现 **> 1 个不同批次日期**时，SHALL 与尺寸超限同等对待、进入同一告警集合。

该判据 SHALL 只施用于根文件，MUST NOT 施用于场景与底座文件——后者顶部段结构不统一，本变更不为此新造结构判定。

顶部段解析 MUST 委托 `工具-CLAUDE进度段lint.py` 的既有实现，MUST NOT 在 sweep 内另写一套正则。

该 lint 模块导入失败或解析失败时，sweep MUST 输出「顶部段判据不可用（原因）」并跳过该半条，MUST NOT 将其静默计为「未超限」。

#### Scenario: 顶部段含两个批次日期
- **WHEN** 根 `CLAUDE.md` 顶部进度段的条目分属 `2026-08-19` 与 `2026-08-22` 两个日期
- **THEN** 根文件进入告警集合，且告警正文写明命中的是批次跨度判据而非尺寸判据

#### Scenario: lint 模块不可用时不静默放过
- **WHEN** `工具-CLAUDE进度段lint.py` 无法导入
- **THEN** sweep 输出「顶部段判据不可用」及原因，且不因此把根文件判为合规

### Requirement: 告警 SHALL 走既有常驻状态骨架与既有出口

告警 SHALL 复用 `_track_and_alert_standing_state`，MUST NOT 新增通知通道。

再提醒间隔 SHALL 为 24 小时；状态文件 SHALL 为 `reports/sweep-claude-md-size-state.json`。

告警 key SHALL 为**文件相对路径**，MUST NOT 包含尺寸数值——把变动的数值放进 key 会使每次涨落都被当成新问题重复告警。

超限项消失时 SHALL 自动推送解除通知。

#### Scenario: 尺寸回落后自动解除
- **WHEN** 某文件此前已告警，本轮字节数回落到阈值内
- **THEN** 推送解除通知，且该 key 从状态文件中移除

#### Scenario: 同一文件持续超限不重复轰炸
- **WHEN** 某文件持续超限且距上次告警不足 24 小时
- **THEN** 本轮不推送该文件的告警

### Requirement: 守卫 SHALL 每轮回显自身读到的值，即使不告警

无论是否触发告警，sweep SHALL 在日志中逐项回显「文件相对路径 / 当前字节数 / 适用阈值 / 距阈值差额」。

该回显 MUST NOT 因「本轮零超限」而被省略。

#### Scenario: 全部合规时仍有回显
- **WHEN** 本轮所有受检文件均未超限
- **THEN** 日志仍逐项列出各文件的当前值、阈值与差额

#### Scenario: 回显覆盖全部受检文件
- **WHEN** 受检文件共 14 份
- **THEN** 回显行数为 14，不因合规而缩减

