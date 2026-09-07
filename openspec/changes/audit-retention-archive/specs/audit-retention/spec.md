## ADDED Requirements

### Requirement: 留存类别 SHALL 由写方显式声明，工具 MUST NOT 推断
每一个审计 sink MUST 在构造时携带一个留存类别：`COMPLIANCE`（AI 决策审计，IATF 红线 2 覆盖）／`TRACE`（连接器访问痕迹）／`OPS`（机制遥测）。留存工具 MUST NOT 从文件名、路径或文件内容推断类别。对未声明类别的文件，封存与删除接口 MUST 拒绝执行并抛出错误（fail-closed），MUST NOT 采取任何"尽力而为"的降级行为。

#### Scenario: 未声明类别的文件被拒绝
- **WHEN** 对一个未携带留存类别的 JSONL 文件调用封存或删除接口
- **THEN** 接口抛出错误、不产生任何文件系统副作用

#### Scenario: 名字像审计但未声明，同样被拒绝
- **WHEN** 目标文件名为 `xxx_audit.jsonl` 但未声明留存类别
- **THEN** 接口照样拒绝，证明实现未依据文件名做任何推断

#### Scenario: 存量构造点靠默认值兜住
- **WHEN** 既有业务代码以 `AuditLogger.jsonl(path)` 或 `ConnectorAudit(sink=JsonlSink(path))` 构造
- **THEN** 前者默认 `COMPLIANCE`、后者默认 `TRACE`，业务代码无需改动

### Requirement: `COMPLIANCE` 类审计 SHALL 永不被删除或截断
`COMPLIANCE` 类文件 MUST NOT 被按大小截断、按时间删行、或整份删除。实现中 MUST NOT 存在任何指向 `COMPLIANCE` 类的删除、截断或覆盖写代码路径；该约束 MUST 由静态断言测试守住，MUST NOT 仅以文档形式存在。

#### Scenario: 无删除函数
- **WHEN** 对留存模块做 AST 扫描
- **THEN** `COMPLIANCE` 分支下不存在 `unlink`／`remove`／`truncate`／覆盖写模式打开文件的调用

#### Scenario: 磁盘紧张不构成例外
- **WHEN** 磁盘余量不足且 `COMPLIANCE` 文件持续增长
- **THEN** 系统执行封存（roll-and-seal）而非删除；若封存后仍不足，MUST 告警而非删除

### Requirement: 归档 SHALL 采用滚动封存，MUST NOT 移动或改写任何一行
达到阈值时，系统 MUST 将整份热文件原子改名为不可变段文件，并另起一份新热文件。封存过程 MUST NOT 从任何文件中移动、改写或删除任何一行；段文件 MUST 是原热文件的逐字节副本。封存 MUST NOT 跨文件合并——每个热文件封存为自己独立的段序列，MUST NOT 把多个场景或多个 OEM 上下文的审计并成一份。

#### Scenario: 封存前后逐字节相同
- **WHEN** 对一份热文件执行封存
- **THEN** 段文件内容的 sha256 与封存前热文件的 sha256 全等

#### Scenario: 拒绝跨文件合并
- **WHEN** 两个不同场景的热文件先后达到阈值
- **THEN** 产生两个独立的段序列，不产生任何合并产物

#### Scenario: 按自然月成段以便举证
- **WHEN** 审计员询问某个自然月的全部记录位置
- **THEN** 答案是一个段文件名，而非"分散在若干段中"

### Requirement: 封存 MUST NOT 重算 `prev_hash`
封存实现 MUST NOT 包含任何重新计算既有记录 `prev_hash` 的代码路径。重算后的链在 `verify_chain()` 下恒为通过，因而对"由持有写权限者执行的整理动作"不具备任何防御力；本项目 2026-07-28 已实际发生过一次链重算且校验通过。

#### Scenario: 实现中不存在重算路径
- **WHEN** 审查封存实现
- **THEN** 不存在任何对既有行重新计算并写回 `prev_hash` 的分支

#### Scenario: 重算过的段被检出
- **WHEN** 某个已封存段被整段重算 `prev_hash` 后重写
- **THEN** 跨段校验返回 `ok=False`，因为封条中记录的段首行／末行 sha256 已对不上

### Requirement: 每个封存段 SHALL 产出封条，封条自身成链
封存时 MUST 产出封条文件，含 `segment`、`line_count`、`first_line_sha256`、`last_line_sha256`、`first_ts`、`last_ts`、`sealed_at`、`sealed_by`、`prev_segment_seal_sha256`。封条之间 MUST 通过 `prev_segment_seal_sha256` 成链，使"整段被删除"可被检出。

#### Scenario: 整段被删除时检出
- **WHEN** 一个段文件被整个删除后执行跨段校验
- **THEN** 返回 `ok=False`，封条链在该处断裂

#### Scenario: 封条被篡改时检出
- **WHEN** 某个封条的字段被修改后执行跨段校验
- **THEN** 返回 `ok=False`，下一封条的 `prev_segment_seal_sha256` 对不上

### Requirement: 封存 SHALL 在写方进程内、写锁内完成
封存 MUST 在持有该 sink 写锁的进程内完成。系统 MUST NOT 提供由外部定时任务、sweep 或独立 CLI 对运行中审计文件执行封存的入口；对不属于本进程 sink 的路径调用封存 MUST 被拒绝。`JsonlSink` 的锁与 `prev_hash` 缓存仅进程内有效，跨进程操作同一文件产生的断链无法与真实篡改区分。

#### Scenario: 外部路径调用被拒绝
- **WHEN** 对一个不属于当前进程任何 sink 的审计文件路径调用封存
- **THEN** 调用被拒绝

#### Scenario: 封存步骤原子且可回退
- **WHEN** 封存过程中任意一步失败
- **THEN** 整体回退，不留下"热文件不存在但续接记录未写"这类半封存状态

### Requirement: 检索 SHALL 默认跨全段
`read_all()` 与 `query_by()` MUST 默认跨热文件与全部封存段返回结果；只读热文件 MUST 为显式 opt-in。否则封存那一刻起「查不到」与「没发生过」不可区分。

#### Scenario: 封存不减少可查记录数
- **WHEN** 对同一 sink 在封存前后各调用一次 `query_by()`
- **THEN** 封存后返回的记录数不少于封存前

#### Scenario: 只读热文件须显式指定
- **WHEN** 调用方只想读热文件
- **THEN** 必须显式传入对应的 scope 参数，默认行为不是这个

### Requirement: 删除 `TRACE` 或 `OPS` 数据 SHALL 自身写一条 `COMPLIANCE` 记录
系统删除任何 `TRACE` 或 `OPS` 类数据时，MUST 写一条 `COMPLIANCE` 类审计记录，含被删文件、行数、时间跨度与执行者。删除动作本身即一次可审计事件。

#### Scenario: 删除留痕
- **WHEN** 按 `OPS` 类策略删除超期的机制遥测行
- **THEN** 产生一条 `COMPLIANCE` 记录，写明被删文件、行数、时间跨度、执行者

#### Scenario: 留痕失败即不删
- **WHEN** `COMPLIANCE` 记录写入失败
- **THEN** 删除动作不执行
