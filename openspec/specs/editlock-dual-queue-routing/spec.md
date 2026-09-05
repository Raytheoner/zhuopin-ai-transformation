# editlock-dual-queue-routing Specification

## Purpose

定义 `工具-共享文档编辑锁.py` 在双队列文件拓扑下的域路由行为，以及配套的幽灵副本（worktree 本地影子副本与锁 CLI 解析目标不一致）检测能力，直接承接 2026-08-10 队列 #315 子项⑥（#321 真实事故）。

## Requirements

### Requirement: acquire/append-row 按域路由
`acquire`（当目标为默认队列文件时）与 `append-row --section 一|二` SHOULD 要求调用方显式声明 `--domain 机|业`，据此路由到 `queue_table.resolve_queue_path()` 解析出的对应物理文件；未声明域且未显式 `--file` 覆盖目标时，SHALL 默认解析到机制环境文件，并 MUST 向调用方回显"本次使用了默认值"这一信号（不得完全静默）。`--section 四` 恒定路由到机制环境文件，不受本 Requirement 约束（该分区体量小、不纳入域字段范围，沿用 `queue-authoritative-path-resolution` 既有 Non-Goals）。

> 📌 **来源**：`queue-dual-file-split` design 决策点 3 原定"未声明域时 MUST 拒绝执行"，apply 阶段实测放宽为本条描述的默认值行为（2026-08-17 归档时的实测佐证即 §一 `#336`）；`queue-domain-routing`（2026-09-05，Shao Peishen 拍板采纳决策点 1 默认项）复核后收编为目标态，移除此前那条"归档时如实登记的目标态/现状分叉"临时标注。若未来改为真拒绝，需先完成调用点普查与迁移（见该变更包 design.md 决策点 1 备选项），届时本 Requirement 需另行修订。

#### Scenario: 未声明域时默认解析到机制环境文件
- **WHEN** 调用 `acquire` 且既未传 `--domain` 也未传 `--file`
- **THEN** 锁与后续读写操作作用于机制环境文件，命令输出中包含一行提示说明"使用了默认值，建议显式指定 `--domain 机|业`"，不静默隐藏这一事实

#### Scenario: 声明域后正确路由
- **WHEN** 调用 `acquire --domain 机`
- **THEN** 锁与后续读写操作作用于机制环境文件；`--domain 业` 时作用于业务场景文件

### Requirement: 绝对路径可见性
`acquire` 与 `status` 子命令的输出 SHALL 包含本次操作所解析出的物理文件绝对路径，不得只输出相对路径或文件名。

#### Scenario: acquire 输出含绝对路径
- **WHEN** 调用 `acquire --domain 机` 并成功获得锁
- **THEN** 命令输出中出现一行完整的绝对文件系统路径，供调用方核对其编辑器即将打开的路径是否与之一致

### Requirement: 本地影子副本漂移检测
`acquire` 与 `status` SHALL 检测当前工作目录所在 worktree 下是否存在与解析目标同相对路径、但物理路径不同（`os.path.samefile` 判定为否）且内容不一致的文件；命中时 MUST 打印醒目警告，说明存在幽灵副本风险，但不得自动删除、覆盖或合并任何一方内容。

#### Scenario: 检测到内容不一致的本地影子副本
- **WHEN** 当前 worktree 本地存在一份与权威文件同相对路径、内容不同的队列文件副本
- **THEN** `acquire`/`status` 输出中出现警告，指出两个路径及"可能正在编辑错误文件"的提示，但两份文件的内容均保持不变

#### Scenario: 主工作区内运行时不误报
- **WHEN** 命令在主工作区（而非 linked worktree）内运行，本地路径与权威路径物理相同
- **THEN** 不触发影子副本警告

#### Scenario: 本地无副本或内容一致时不误报
- **WHEN** 当前 worktree 本地不存在同相对路径文件，或存在但内容与权威文件完全一致
- **THEN** 不触发影子副本警告

### Requirement: 锁粒度——两份队列文件共用一把协作锁，锚点恒为机制环境文件
编辑锁 SHALL 对"队列系统目标"（即 `acquire`/`release`/`status`/`append-row` 在未显式 `--file` 覆盖时的正常队列操作）统一把锁锚点解析为机制环境文件，不论调用方声明的 `--domain` 是"机"还是"业"；两份物理队列文件的写入方 SHALL 串行化持锁，MUST NOT 各自独立加锁并发写入。`--file` 显式覆盖为其它共享文件（如跟进信 README）时，锁粒度仍按目标文件独立派生，不受本 Requirement 约束。

> 📌 **来源**：`queue-dual-file-split` design 决策点 7 当年对"两份文件各自独立锁"提出唯一顾虑——"改高水位线时业务场景文件的写入者感知不到"；apply 阶段（早于 2026-08-17 归档）已选择共享锁作为规避该竞态的保守方案（`QUEUE_LOCK_ANCHOR = QUEUE_MECHANISM_PATH_REL`），2026-08-28 队列 `#420` 止血时进一步把这一不变式显式写入代码注释。**归档时 tasks.md 6.5 的复核结论"独立锁已是既成实现"是一处分析遗漏**（只核对了 `_lock_path()` 通用派生函数本身，未追踪 `cmd_acquire`/`cmd_release`/`cmd_status`/`_append_row_ownership_violation` 四处调用点对"队列系统目标"的锚点覆盖逻辑）；`queue-domain-routing`（2026-09-05，Shao Peishen 拍板采纳决策点 3 默认项）复核代码后更正本 Requirement 与实际行为一致。**这不是重新拍板锁粒度，是订正一处此前未被登记的 spec/实现分叉**，详见该变更包 design.md 决策点 3。

#### Scenario: 两份队列文件的写入方互相阻塞
- **WHEN** 一方已持有队列系统的协作锁（无论其 `--domain` 是"机"还是"业"），另一方对队列系统本体（机制环境或业务场景文件）发起 `acquire`
- **THEN** 后者返回"占用中"，不得成功获得锁，直至前者 `release` 或锁陈旧超时

#### Scenario: 高水位线读写天然串行
- **WHEN** 两个身份先后对 `--section 一|四` 发起 `--reserve` 请求（域不论相同或不同）
- **THEN** 由于二者共用同一把锁，高水位线的"读→分配→回写"临界区不会被并发进入，不产生跨文件竞态，无需额外的跨文件同步/广播机制

#### Scenario: 显式 `--file` 覆盖为其它共享文件时锁粒度不受影响
- **WHEN** 调用方对非队列系统目标（如跟进信 README）显式传 `--file`
- **THEN** 锁按该目标文件自身派生路径，与队列系统的共享锁互不影响，行为与本次改动前完全一致
