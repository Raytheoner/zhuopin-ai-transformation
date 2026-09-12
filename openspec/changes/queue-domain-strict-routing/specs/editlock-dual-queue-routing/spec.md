## MODIFIED Requirements

### Requirement: acquire/append-row 按域路由
`acquire`（当目标为默认队列文件时）与 `append-row --section 一|二` SHALL 要求调用方显式声明 `--domain 机|业`，据此路由到 `queue_table.resolve_queue_path()` 解析出的对应物理文件；未声明域且未显式 `--file` 覆盖目标时，MUST 拒绝执行，不静默选择任一份文件。

> ⚠️ **归档时如实登记的实现差异（2026-08-17，随 `queue-dual-file-split` 归档；2026-09-05 随 `queue-domain-strict-routing` design 补充收口计划）**：本 Requirement 的「未声明域时拒绝执行」在 apply 阶段**未按字面实现**——实际按 design 决策点 3 的「迁移期妥协」落为**未声明域时默认解析到机制环境文件**，见该变更包 `tasks.md` 2.4／3.7。**本条描述的是目标态，当前实现尚未达成**；2026-08-17 归档时的实测佐证即 §一 `#336`（`[D:业]` 却位于机制环境文件，系机器人 `queue_appender` 统一落机制环境文件所致——该根因已由 `queue-domain-strict-routing` 处理机器人默认值另行解决，见下）。
>
> **收口计划（`queue-domain-strict-routing` design.md 决策点 1）**：两阶段收紧——阶段 (a)（软警告升级 ＋ `专线opener模板库.md` §〇.7 由可选改必需 ＋ 巡查现网调用点）；阶段 (b)（design 批准日 +7 天，观察满一个值周巡检节拍后）`_resolve_append_target()` 改为 fail-loud 拒绝，届时本 Requirement 的目标态真正达成，本标注由承接 apply 的变更包移除，届时现有软提示分支（`工具-共享文档编辑锁.py` 行 1924／2036）应一并退休（见 `queue-domain-strict-routing` proposal.md「本次退休哪一个既有守卫」）。

#### Scenario: 未声明域时拒绝
- **WHEN** 调用 `acquire` 且既未传 `--domain` 也未传 `--file`
- **THEN** 命令以非 0 退出码失败，提示须显式声明 `--domain 机` 或 `--domain 业`

#### Scenario: 声明域后正确路由
- **WHEN** 调用 `acquire --domain 机`
- **THEN** 锁与后续读写操作作用于机制环境文件；`--domain 业` 时作用于业务场景文件

## REMOVED Requirements

### Requirement: 锁粒度——每份队列文件各持一把独立锁
**Reason**：本 Requirement 与其"📌 来源"标注均误述为既成事实——2026-09-05 `queue-domain-strict-routing` design 白盒核实 `0-学习与工具/工具-共享文档编辑锁.py::QUEUE_LOCK_ANCHOR = QUEUE_MECHANISM_PATH_REL`（模块行 386）：队列系统模式下 `acquire`／`append-row`／`release`／`status` 的锁路径**全部**取该锚点（机制环境文件的锁），不因 `--domain` 传"机"或"业"而改变，即实际实现是**统一锚点锁**，不是"两份文件各持一把互相独立的锁"。该模块自身注释原文明确记录了这一选择：为避免"域机/域业两个并发 acquire 各自进入临界区、对高水位线产生真实竞态"，主动选择了统一锚点这一保守项，`queue-dual-file-split` design.md 决策点 7 原是"独立锁倾向、留待真实数据验证"的 Open Question，2026-08-17 归档时被误记为"已拍板独立锁、已是既成实现"。**这不是需要 apply 阶段代码追上的目标态缺口，而是 spec 从写入起就未准确描述代码**，故不留"实现差异"标注、直接移除并以下方 ADDED Requirement 取代。

**Migration**：无代码迁移动作——本次移除的只是 spec 对不存在的独立锁行为的描述，`_lock_path()` 与 `QUEUE_LOCK_ANCHOR` 代码本身不改动（本变更包不做任何代码改动，见 proposal.md Non-Goals）。下方新增 Requirement 描述现有代码的真实行为。apply 阶段承接方须新增单测钉住"队列系统模式下两个域的锁路径逐字相同"，防止未来有人按本次移除前的旧表述"修复"回独立锁、重新引入决策点 7 担心的高水位线竞态。

## ADDED Requirements

### Requirement: 锁粒度——队列系统模式下统一锚点锁
队列系统模式（`acquire`／`append-row --section 一|二|四`／`release`／`status` 未显式 `--file` 覆盖到其它共享文件）下，编辑锁 SHALL 统一锚定到机制环境文件（`QUEUE_LOCK_ANCHOR`），不因 `--domain` 声明的域为"机"或"业"而改变实际获取的锁；两份物理队列文件的**内容**仍按 `--domain` 精确路由到各自对应的物理文件（见「acquire/append-row 按域路由」Requirement），但**锁**本身不逐文件独立。

本选择的理由：跨文件唯一共享的可变状态——编号高水位线——只维护在机制环境文件；统一锚点锁天然把所有队列系统写入串行化进同一临界区，从根本上消除"两个域各自持锁并发写入、高水位线被并发读改写"这一竞态，且现网队列写入频率（人工/CC/定时任务节奏）未观察到因此产生的排队问题。此为永久设计，不是待真实数据验证后决定去留的临时保守项。

显式 `--file` 指向其它共享文件（如跟进信 README）时不受本 Requirement 约束，`_lock_path()` 按该目标文件独立派生锁路径的既有行为不变。

#### Scenario: 队列系统模式下两个域共享同一把锁
- **WHEN** 一方已对队列系统（默认目标）以 `--domain 机` 持锁，另一方随即以 `--domain 业` 发起 `acquire`
- **THEN** 后者被现有锁阻塞（等待/失败，行为与同域两次并发 acquire 一致），不因域不同而获得一把独立的锁

#### Scenario: 显式 --file 指向其它共享文件时不受影响
- **WHEN** 调用方显式传 `--file` 指向跟进信 README 等非队列系统文件
- **THEN** 锁路径按该目标文件独立派生，与队列系统模式下的统一锚点锁互不影响
