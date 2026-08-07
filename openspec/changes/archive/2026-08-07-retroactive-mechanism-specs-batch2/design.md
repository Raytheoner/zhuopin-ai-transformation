# Design — 机制/工具类模块补写 openspec capability（第二批）

## 背景

`retroactive-mechanism-specs`（2026-08-04 归档）补齐了队列 #195 八个候选中的 5 个，明确延后 `--reserve`（#163）与 `queue_lock_pending.py`（#168）两项，理由是"近期仍在演进，补完即过时"。2026-08-07 队列 #299/#195 同车批复核这两项是否已稳定，可以补写。

## D1：稳定性复核判据——近期有无改变对外行为契约的提交

判据不是"有无任何提交"（任何模块都可能有零星提交），而是"近期提交是否改变了本模块对外暴露的行为契约"：

- **`--reserve`**：`_reserve_ids`/`cmd_acquire`/`_parse_reserve_multi` 三处核心逻辑自 #185（2026-08-04，新增 `--reserve-multi` 与竞态防护）后无进一步改动；协议〇.7 已据其更新为正式口径（"此后新行编号一律用 `--reserve` 取"），不再是临时方案。**判定：稳定，可补写。**
- **`queue_lock_pending.py`**：自 #168（2026-07-30）落地后，#286（2026-08-06）新增了 `pending_jsonl.py` 并让本模块内部改为复用其 `append_record`/`read_records`/`rewrite_records`——但这是**内部实现的复用重构**，`record_deferred_append`/`read_deferred_appends`/`flush_pending_queue_appends` 三个对外函数的签名与行为契约（暂存格式、FIFO 补录顺序、独立 acquire/release、成功后复用完整同步路径）**未变**。**判定：对外契约稳定，可补写；本次 spec 只描述对外契约，不涉及内部是否复用 `pending_jsonl` 这一实现细节。**

## D2：编写方法——沿用第一批方法论，只转写已验证行为

同 `retroactive-mechanism-specs` D2：逐条对照①现有实现代码（读函数签名与关键分支）②现有测试断言，只有代码与测试同时确认的行为才写入 SHALL/MUST。核对结果：

- `--reserve` 的全部行为分支（单/多分区互斥、fail-loud 三种触发条件、竞态碰撞检测、release 时预留集合校验）均有对应单测覆盖（`test_工具-共享文档编辑锁.py` 内 `--reserve`/`--reserve-multi`/`_reserve_ids`/`_validate_release_structure` 相关用例）。
- `queue_lock_pending.py` 的暂存/FIFO 补录/独立锁/停止条件均有 `test_queue_lock_pending.py` 覆盖（含 #286 更新后的复用路径回归）。

未发现"代码有、测试无"的关键分支需要排除。

## D3：不做的事

- 不新建 `data_isolation_layer`/OEM 相关接口位——两个模块均不涉及 OEM 技术数据。
- 不因补写 spec 而反向修改代码——本变更包对代码的定位是**只读取证来源**，代码零改动（见 proposal.md Impact 段）。
- 不把 `pending_jsonl.py`（#286 引入的内部复用模块）单独列为第三个 capability——它是 `queue_lock_pending.py` 与 `queue_git_sync.py` 共同复用的内部实现细节，不构成独立的对外行为契约，写入独立 capability 会与"避免内部实现细节进入 spec"的既有写作原则冲突。
- 不追加 FI2 的占位 spec——FI2 已由同日队列 #299 行走 `/opsx:sync`（不归档）单独处理，不属于本批范围，避免重复劳动或口径冲突。

## 验收

`openspec validate --all --strict` 在本变更包归档后应新增 2 个绿色 capability，累计覆盖队列 #195 原始 8 候选中的 7 项（FI2 走独立 sync 路径不计入本批统计口径，但其 spec 事实上也已存在于 `openspec/specs/`）。
