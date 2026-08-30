## ADDED Requirements

### Requirement: 状态列 SHALL 支持机器字段 `[A:…]` 且字段顺序 SHALL 为 S→D→A
§一 状态列 MAY 在 `[D:…]` **之后**带 `[A:…]`（assigned），取值 `已派出`（含「已派出未认领」与「在办」两态）。字段顺序 MUST 为 `[S:…][D:…][A:…]`；`[A:…]` 出现在 `[D:…]` 之前 MUST 被告警，MUST NOT 静默接受。

#### Scenario: 合法顺序
- **WHEN** 状态列为 `[S:open][D:机][A:已派出] 正文`
- **THEN** 既有解析器仍返回 `('open','机')`，池子排除该行

#### Scenario: 顺序写反必须被发现
- **WHEN** 状态列为 `[S:open][A:已派出][D:机] 正文`
- **THEN** 告警——该写法会使域字段解析为 `None`、被 WIP 计数静默跳过，MUST NOT 静默通过

### Requirement: 可 Open 池与看板卡 SHALL 排除带 `[A:…]` 的行
两处 MUST 使用同一判据：行含 `[A:` 即排除，不解析取值（向前兼容取值扩展）。

#### Scenario: 已派出的行不再被报为可开工
- **WHEN** `#435` 为 `[S:open][D:机][A:已派出]` 且已被 CC 认领
- **THEN** 推送与看板卡均不列出它

#### Scenario: 撤销派出
- **WHEN** 某行的 `[A:…]` 被删除且仍为 `[S:open]`
- **THEN** 该行重新进入池子

### Requirement: opener 路径 SHALL 按执行环境过滤，不符 SHALL 不给
候选 opener 块内 `【设置】` 的执行环境须等于该队列行领取方环境；不符 MUST NOT 给出该路径，改为提示「opener 未定位，见队列行」。宁可漏给，MUST NOT 给错。

#### Scenario: Cowork 接力卡不得充当 CC 行的 opener
- **WHEN** `#435`（领取方 CC）的候选文件里只有一个 `【设置】执行环境：Cowork` 的 opener 块
- **THEN** 不给路径；MUST NOT 把该 Cowork 块当作 opener 报出

#### Scenario: 环境相符正常给出
- **WHEN** 候选块为 `【设置】执行环境：CC` 且行领取方为 CC
- **THEN** 给出该路径

### Requirement: 存量回填 SHALL 只出候选、SHALL NOT 自动写
MUST 产出「疑似已派出／在办但仍为 `[S:open]` 且无 `[A:…]`」的候选清单（形状判据：正文以 `🔄` 起首必列）。MUST NOT 自动写入任何行。MUST NOT 把「正文以 🔄 起首」用作池子的排除判据（2026-08-30 实测 22 个 `[S:open]` 行首符号有 9 种，🔄 覆盖率 2/22）。

#### Scenario: 出候选不落笔
- **WHEN** `#381` 为 `[S:open]` 且正文以 🔄 起首
- **THEN** 列入候选清单，行本身不被改动
