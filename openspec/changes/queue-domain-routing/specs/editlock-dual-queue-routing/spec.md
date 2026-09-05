## RENAMED Requirements

- FROM: `### Requirement: 锁粒度——每份队列文件各持一把独立锁`
- TO: `### Requirement: 锁粒度——两份队列文件共用一把协作锁，锚点恒为机制环境文件`

## MODIFIED Requirements

### Requirement: acquire/append-row 按域路由
`acquire`（当目标为默认队列文件时）与 `append-row --section 一|二` SHOULD 要求调用方显式
声明 `--domain 机|业`，据此路由到 `queue_table.resolve_queue_path()` 解析出的对应物理
文件；未声明域且未显式 `--file` 覆盖目标时，SHALL 默认解析到机制环境文件，并 MUST 向调用
方回显"本次使用了默认值"这一信号（不得完全静默）。`--section 四` 恒定路由到机制环境文件，
不受本 Requirement 约束（该分区体量小、不纳入域字段范围，沿用 `queue-authoritative-path-
resolution` 既有 Non-Goals）。

> 📌 **来源**：`queue-dual-file-split` design 决策点 3 原定"未声明域时 MUST 拒绝执行"，
> apply 阶段实测放宽为本条描述的默认值行为（2026-08-17 归档时的实测佐证即 §一 `#336`）；
> `queue-domain-routing`（本包）2026-09-05 复核后收编为目标态，移除此前"归档
> 时如实登记的实现差异"临时标注。若未来改为真拒绝，需先完成调用点普查与迁移（见本包
> design.md 决策点 1 备选项），届时本 Requirement 需另行修订。

#### Scenario: 未声明域时默认解析到机制环境文件
- **WHEN** 调用 `acquire` 且既未传 `--domain` 也未传 `--file`
- **THEN** 锁与后续读写操作作用于机制环境文件，命令输出中包含一行提示说明"使用了默认值，
  建议显式指定 `--domain 机|业`"，不静默隐藏这一事实

#### Scenario: 声明域后正确路由
- **WHEN** 调用 `acquire --domain 机`
- **THEN** 锁与后续读写操作作用于机制环境文件；`--domain 业` 时作用于业务场景文件

### Requirement: 锁粒度——两份队列文件共用一把协作锁，锚点恒为机制环境文件
编辑锁 SHALL 对"队列系统目标"（即 `acquire`/`release`/`status`/`append-row` 在未显式
`--file` 覆盖时的正常队列操作）统一把锁锚点解析为机制环境文件，不论调用方声明的 `--domain`
是"机"还是"业"；两份物理队列文件的写入方 SHALL 串行化持锁，MUST NOT 各自独立加锁并发写入。
`--file` 显式覆盖为其它共享文件（如跟进信 README）时，锁粒度仍按目标文件独立派生，不受本
Requirement 约束。

> 📌 **来源**：`queue-dual-file-split` design 决策点 7 当年对"两份文件各自独立锁"提出
> 唯一顾虑——"改高水位线时业务场景文件的写入者感知不到"；apply 阶段（早于 2026-08-17
> 归档）已选择共享锁作为规避该竞态的保守方案（`QUEUE_LOCK_ANCHOR = QUEUE_MECHANISM_
> PATH_REL`），2026-08-28 队列 `#420` 止血时进一步把这一不变式显式写入代码注释。**归档
> 时 tasks.md 6.5 的复核结论"独立锁已是既成实现"是一处分析遗漏**（只核对了 `_lock_path()`
> 通用派生函数本身，未追踪 `cmd_acquire`/`cmd_release`/`cmd_status`/`_append_row_
> ownership_violation` 四处调用点对"队列系统目标"的锚点覆盖逻辑）；`queue-domain-routing`
> （本包）2026-09-05 复核代码后更正本 Requirement 与实际行为一致。**这不是
> 重新拍板锁粒度，是订正一处此前未被登记的 spec/实现分叉**，详见本包 design.md 决策点 3。

#### Scenario: 两份队列文件的写入方互相阻塞
- **WHEN** 一方已持有队列系统的协作锁（无论其 `--domain` 是"机"还是"业"），另一方对队列
  系统本体（机制环境或业务场景文件）发起 `acquire`
- **THEN** 后者返回"占用中"，不得成功获得锁，直至前者 `release` 或锁陈旧超时

#### Scenario: 高水位线读写天然串行
- **WHEN** 两个身份先后对 `--section 一|四` 发起 `--reserve` 请求（域不论相同或不同）
- **THEN** 由于二者共用同一把锁，高水位线的"读→分配→回写"临界区不会被并发进入，不产生
  跨文件竞态，无需额外的跨文件同步/广播机制

#### Scenario: 显式 `--file` 覆盖为其它共享文件时锁粒度不受影响
- **WHEN** 调用方对非队列系统目标（如跟进信 README）显式传 `--file`
- **THEN** 锁按该目标文件自身派生路径，与队列系统的共享锁互不影响，行为与本次改动前完全
  一致
