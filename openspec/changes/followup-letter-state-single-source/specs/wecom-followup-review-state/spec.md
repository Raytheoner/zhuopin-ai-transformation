## ADDED Requirements

### Requirement: 串行原则闸的闭环判据为闭环四态
`_validate_followup_readme_release` 的串行原则闸在回查「前一封」时，SHALL 按**闭环四态**（`📥 已回件并回灌`／`✅ 无需回复`／`📨 已确认闭环`／`❌ 已作废`）判定是否已闭环，MUST NOT 只认 `📥 已回件并回灌` 单一前缀。

该判定 MUST 取自权威实现 `zhuopin_platform.shared_tools.followup_gate`，编辑锁 MUST NOT 自持一套闭环状态字面量（隔离环境的兜底取值除外，且其取值须与权威实现逐字一致）。

在途五态（`✅ 已推送`／`✅ 已发`／`⏳ 待你审`／`🆕 待发`／`⏸ 暂缓`）SHALL 一律仍视为未闭环。

#### Scenario: 前一封为「无需回复」即放行
- **WHEN** 新增某收信人登记行，其前一封发送状态为 `✅ **无需回复**（发出即闭环）`
- **THEN** release 通过，且不需要写 `串行豁免：`

#### Scenario: 前一封为「已推送」仍被拦
- **WHEN** 前一封发送状态为 `✅ 已推送 2026-08-20 12:20 UTC`
- **THEN** release 被拒绝，提示中列出闭环四态的全部取值
