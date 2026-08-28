## ADDED Requirements

### Requirement: 哨兵 SHALL 只对解析出的写入目标与本次新增内容判定
项目级哨兵 SHALL 从 hook 的 stdin JSON 中解析出本次工具调用的**写入目标路径**与**本次写入引入的内容**，
并 MUST 仅以这两者为判定输入。

哨兵 MUST NOT 对 stdin JSON 里的原始命令串（如 `command` 字段）做路径正则或内容正则——
**正文里提到一个路径不等于写入了那个路径**。

哨兵 MUST NOT 扫描目标文件中本次未改动的既有内容。

解析不出写入目标时，哨兵 MUST 放行（`exit 0`），并 MUST 在心跳里记为一次「无法判定」，
MUST NOT 静默当作「没有违规」。

#### Scenario: 正文提到受保护路径不被误判
- **WHEN** 一次 `Write` 的目标是 `1-转型规划/0-全景路线图/某报告.md`，而正文里引用了字符串 `~/.claude/hooks/audit-log.ps1`
- **THEN** 哨兵放行，且不产生任何拦截记录

#### Scenario: 只判新增内容，不为既有内容负责
- **WHEN** 一次 `Edit` 只改了某 `.md` 文件的一行，而该文件别处早已存在一个 U+FFFD
- **THEN** 哨兵放行（该 U+FFFD 不在本次新增内容内）

#### Scenario: 解析不出目标时放行且留痕
- **WHEN** stdin JSON 缺少可解析的写入目标
- **THEN** 退出码为 0，心跳中该次记为「无法判定」

### Requirement: 哨兵 SHALL fail-open 且 SHALL NOT 静默失败
哨兵脚本 MUST 用 `try{...}catch{ exit 0 }` 包裹全部逻辑：任何异常一律放行。

哨兵 MUST 配 `timeout` 10 秒（与既有 `pretooluse-guard.ps1` 同规格）。

异常放行 MUST 同时把异常摘要写进心跳——**放行可以，静默不行**。

#### Scenario: 脚本抛异常时放行
- **WHEN** 哨兵脚本内部抛出未预期异常
- **THEN** 退出码为 0，工具调用不被阻塞

#### Scenario: 异常仍留痕
- **WHEN** 哨兵因异常放行
- **THEN** 心跳文件中该次记录含异常摘要，且 `ok` 为假

### Requirement: 哨兵 SHALL 自证在岗
公共框架 MUST 在**每一次运行**（含放行、含异常）向 `reports/hooks-heartbeat.json` 覆盖写一条心跳，
内容 MUST 含：最后运行时刻（本机时区，且 MUST 显式标注基准）、触发的哨兵名、判定结果、异常摘要（若有）。

心跳文件 MUST 是单一定名文件，MUST NOT 按日期或会话分片。

MUST 存在一条「最近 N 天零心跳即告警」的检查；该告警 MUST 能被「心跳恢复」自动关掉，
MUST NOT 是一个只会出现、不会解除的告警。

#### Scenario: 放行也落心跳
- **WHEN** 哨兵判定放行
- **THEN** 心跳文件被更新，`lastRun` 为本次时刻

#### Scenario: 挂接被改坏时零心跳告警响
- **WHEN** `.claude/settings.json` 的挂接被改坏，连续 N 天无心跳
- **THEN** 「零心跳」告警触发

#### Scenario: 恢复后告警自动解除
- **WHEN** 挂接改回，心跳恢复
- **THEN** 该告警在下一轮检查中不再出现，无需人工清除

### Requirement: 拦截 SHALL 留痕于既有审计载体
哨兵拦截（`exit 2`）时 MUST 向 `~/.claude/audit-blocks-<date>.log` 追加一条记录，
复用既有格式（时刻、事件、工具、session_id、目标、命中规则）。

哨兵 MUST NOT 新造任何日志文件形态。

#### Scenario: 拦截进既有 audit-blocks
- **WHEN** 哨兵拦下一次写入
- **THEN** 当日 `audit-blocks` 日志新增一行，含目标路径与命中的哨兵名

### Requirement: 哨兵 SHALL 提供行内留痕式逃生阀
每个哨兵 MUST 支持一个写在**被检查文件内**的豁免标记（形如 `<哨兵名>豁免：<理由>`）。

豁免标记 MUST 携带理由文本；只有标记、没有理由的 MUST NOT 生效。

逃生阀 MUST NOT 通过新增任何写盘路径实现（不写状态文件、不写豁免清单文件）。

#### Scenario: 带理由的豁免生效
- **WHEN** 违规行同一处写有 `乱码豁免：本行原样引用 2026-07-04 事故字节`
- **THEN** 该行不判违规

#### Scenario: 无理由的豁免不生效
- **WHEN** 违规行只写 `乱码豁免：` 而无理由文本
- **THEN** 该行仍判违规
