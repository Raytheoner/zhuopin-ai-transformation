## ADDED Requirements

### Requirement: 收口 SHALL 先实证在网再动手
触发后 skill MUST 先以可核验探针（ping `.51` 关键端点与源系统）实证当前确在 LAN；探针不过 MUST 如实报告并停止，MUST NOT 以触发词本身为在网依据。

#### Scenario: 声称回网但探针不过
- **WHEN** 他说「我已回Lan」而 `.51` 探针不可达
- **THEN** 不起任何泳道，回报探针结果

### Requirement: `.51` 触碰项 SHALL 串行且逐项冒烟回滚
同一批内触碰 `.51` 的泳道 MUST 串行执行；每项 MUST 动前留快照、部署后过冒烟三件套（`/api/ping`／关键页 200／一次全量重算），不过 MUST 按回滚 SOP 退回并停该项，MUST NOT 带伤推进下一项。

#### Scenario: 冒烟失败即回滚停项
- **WHEN** 某项部署后关键页非 200
- **THEN** 执行回滚、该项降回留步态并注明失败原因，后续 `.51` 项暂停待人

### Requirement: 选件 SHALL 只收有可执行判据的留步登记
入批项 MUST 来自三源登记（扫描器形态 1／队列「LAN 留步：」标注／看护件 LAN 留步节）且含可执行判据；模糊登记 MUST 归入「登记不合格」节点名补判据。对外发送、请人动作、L2 代签、合规红线变更 MUST NOT 入批；专员复核类 MUST 收口至可复核态即停。

#### Scenario: 模糊登记不入批
- **WHEN** 某留步登记只写「回 LAN 再处理」
- **THEN** 该项不入批，出现在「登记不合格」节

### Requirement: 收口 SHALL 区别于销号且失败项 SHALL 降回留步态
泳道完成 MUST 以该项登记判据满足＋证据回写为准；所在队列行是否销号仍由行内原纪律决定。任何失败或中断项 MUST 更新留步登记（含失败原因）后退出，MUST NOT 留"半收口"状态。

#### Scenario: 行内尚有非 LAN 半边
- **WHEN** 某行的 LAN 半边已收口而另一半边未完成
- **THEN** 行状态保持 🟡，仅 LAN 半边标注完成与证据

### Requirement: 骨架纪律 SHALL 整体继承 clearpool
看护件必落档入 git、心跳与企微四类事件推送、无头批处理链（Task 子代理限只读，#138 裁定）、硬边界十条、首跑灰度上限 2 且 Shao Peishen 在场——MUST 全部继承，不另造变体。

#### Scenario: 落档失败即全停
- **WHEN** 看护件写盘失败
- **THEN** 不起任何泳道并告警
