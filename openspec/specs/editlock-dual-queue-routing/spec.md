# editlock-dual-queue-routing Specification

## Purpose

定义 `工具-共享文档编辑锁.py` 在双队列文件拓扑下的域路由行为，以及配套的幽灵副本（worktree 本地影子副本与锁 CLI 解析目标不一致）检测能力，直接承接 2026-08-10 队列 #315 子项⑥（#321 真实事故）。

## Requirements

### Requirement: acquire/append-row 按域路由
`acquire`（当目标为默认队列文件时）与 `append-row --section 一|二` SHALL 要求调用方显式声明 `--domain 机|业`，据此路由到 `queue_table.resolve_queue_path()` 解析出的对应物理文件；未声明域且未显式 `--file` 覆盖目标时，MUST 拒绝执行，不静默选择任一份文件。

> ⚠️ **归档时如实登记的实现差异（2026-08-17，随 `queue-dual-file-split` 归档）**：本 Requirement 的「未声明域时拒绝执行」在 apply 阶段**未按字面实现**——实际按 design 决策点 3 的「迁移期妥协」落为**未声明域时默认解析到机制环境文件**，见该变更包 `tasks.md` 2.4／3.7。**本条描述的是目标态，当前实现尚未达成**；2026-08-17 归档时的实测佐证即 §一 #336（`[D:业]` 却位于机制环境文件，系机器人 `queue_appender` 统一落机制环境文件所致）。补齐属 `tasks.md` 3.7 明列的独立后续。

#### Scenario: 未声明域时拒绝
- **WHEN** 调用 `acquire` 且既未传 `--domain` 也未传 `--file`
- **THEN** 命令以非 0 退出码失败，提示须显式声明 `--domain 机` 或 `--domain 业`

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

### Requirement: 锁粒度——每份队列文件各持一把独立锁
编辑锁 SHALL 按目标文件派生锁文件路径（`<目标文件名>.editlock`），使两份队列文件各持一把互相独立的锁；两份文件的写入方 SHALL 可并行持锁，不因另一份文件被占用而阻塞。

> 📌 **来源**：`queue-dual-file-split` design.md 决策点 7 原列为待验证项（design 推荐倾向独立锁），2026-08-17 归档时经复核拍板采用独立锁——`_lock_path()` 逐文件派生已是既成实现，快照与互斥体均在其上再派生，同样逐文件独立。**遗留**：跨文件高水位线同步的完整语义仍未实现（高水位线只维护在机制环境文件），属 `tasks.md` 3.7 明列的独立后续。

#### Scenario: 两份队列文件的锁互不阻塞
- **WHEN** 一方已持有机制环境文件的锁，另一方对业务场景文件发起 `acquire`
- **THEN** 后者成功获得锁，不被前者阻塞，且两把锁的状态互相独立
