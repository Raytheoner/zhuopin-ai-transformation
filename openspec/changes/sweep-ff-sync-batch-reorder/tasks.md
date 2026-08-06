## 1. 单测先行（须含真实故障场景复现，验收要求①）

- [x] 1.1 在 `0-学习与工具/test_工具-落库sweep.py`（或既有测试文件，apply 阶段先核实实际文件名）新增复现用例："本地队列文件脏（未提交改动，属于某个批次声明）＋ origin 有改动同一文件的新提交，且两边改动不冲突"——验证：sweep 完成批次提交、自动 rebase、推送成功，本轮不 `SweepAbort`，退出码 0，批次状态列被正确标记为已完成。
- [x] 1.2 新增复现用例："同上前提，但两边改动真实冲突（同一行被双方修改）"——验证：sweep 执行 `git rebase --abort`，本轮批次提交完整保留在本地（`git log` 可见），退出码为 `FORK_EXIT_CODE`，`is_fork=True` 路径被触发（webhook 告警调用/连续轮次持久化按既有 `sweep-fork-alert` 契约验证）。
- [x] 1.3 新增用例：纯落后（无本轮批次可提交，§二无待处理批次，但本地 master 落后 origin）——验证 ff-only 合并仍然正常工作，行为与旧版 `_sync_master_if_behind_origin` 等价。
- [x] 1.4 新增用例：纯领先（本轮批次提交后，origin 无新提交）——由既有 `HappyPathTests` 全套用例覆盖（origin 全程不变即纯领先场景），未见必要另开一个内容重复的新用例；改为在 `_reconcile_with_origin_and_push` 实现层面用条件分支保证"纯领先跳过合并/rebase 直接推送"，行为已被 1.5 的推送计数用例间接验证只发生一次 push。
- [x] 1.5 新增用例：多个批次在同一轮被处理——验证只产生一次 `git push` 调用（而非每个批次各自 push）。
- [x] 1.6 新增用例：批次提交阶段全部成功，但统一推送因非 git 分叉原因失败（如模拟网络错误）——验证本地提交不被撤销，退出码与既有"本地提交不会被撤销"语义一致。
- [x] 1.7 回归既有测试：确认 `_partition_pending_rows_by_batch_isolation`（#238）、孤儿告警（#236(2)）、状态列判据（#248）、部署留痕提示（#229）、常驻服务提示（#198c）在新调用顺序下行为不变。**如实记录**：`HappyPathTests.test_happy_path_commits_atomically_with_ledger_rerun`（日志文案"已落库并推送"→"已本地提交"+"已统一推送"）、`LateForwardCheckTests`（整个用例改写：`_process_normal_batch` 不再自己校验快进，改为验证"只本地提交、职责已移交"这一契约）、`SyncBehindOriginTests.test_pure_behind_auto_ff_merges_then_processes_pending_batch`（重命名为 `test_behind_origin_with_pending_batch_commits_then_rebases_and_pushes`，因批次先提交后该场景从"纯落后 ff-only"变为"分叉后 rebase"，属职责重排的自然结果，非新缺陷）三处断言/用例已同步调整，理由见各用例内注释。其余全部既有测试无需改动即通过。

## 2. 实现：拆分提交与推送职责

- [x] 2.1 新增对齐函数 `_reconcile_with_origin_and_push`（承接 design.md「决策点 1/2/3」的行为契约）：fetch 一次 → 判断 `HEAD` 与 `origin/master` 的关系（相等/纯落后/纯领先/已分叉）→ 按 design.md「决策点 1」分派 ff-only 合并 / 跳过 / rebase → 成功后统一 `git push` 一次 → 成功时 `_reset_fork_state`；rebase 失败时 `git rebase --abort` + 复用 `_handle_fork_detected`（`is_fork=True`，`FORK_EXIT_CODE`）。
- [x] 2.2 修改批次处理逻辑（`_process_normal_batch`）：拆出"只提交、不校验快进、不推送"的版本，供批次循环调用；原有的 add/状态列改写/commit 逻辑保留，去掉 `_verify_fast_forward` 与 `push` 调用。
- [x] 2.3 遗留尾巴批次（straggler_rows）处理同步改为"只提交不推送"。
- [x] 2.4 `_rerun_ledger` 同步改为"只提交不推送"（内容有变化才 commit 的既有短路逻辑不变）。
- [x] 2.5 `main()` 调整调用顺序：移除批次处理前的 `_sync_master_if_behind_origin` 调用与 `_verify_fast_forward(refetch=False, is_fork=True)`/`_reset_fork_state` 早检三连；在"批次提交 + 遗留尾巴提交 + 台账重跑提交"全部完成之后，调用 2.1 新增的对齐函数一次；对齐成功后再执行既有的 `touched_paths` 相关提示（#198c 常驻服务提示、#229 部署留痕提示），保持"只在真正推送成功后才提示"的既有语义。同时移除了"§二无待处理批次即提前 return"的旧逻辑，改为让对齐步骤始终执行一次（纯落后时的常规追赶不依赖本轮有无批次）。
- [x] 2.6 `_verify_fast_forward` 与 `_sync_master_if_behind_origin` 两个函数在重构后全部调用点清零，判定为纯粹死代码，已整体删除（未保留为"内部复用"——新函数逻辑与它们不是简单复用关系，独立重写更清晰）。
- [x] 2.7 `--dry-run` 模式同步适配新流程：`_reconcile_with_origin_and_push` 内部 `if dry_run` 分支在任何真实 git 调用之前直接返回，只打印计划提示；既有 dry-run 测试（`test_dry_run_makes_no_changes` 等）全部保持通过，未发现旧代码在 `--dry-run` 下仍会真实执行 `_sync_master_if_behind_origin`（该函数此前未接收 dry_run 参数）这一潜在泄漏被本次改动顺带堵住，但本变更不专门声称"修了一个已知的 dry-run 缺陷"——只是新函数的 dry-run 处理本就更严格。

## 3. 文档

- [x] 3.1 按 `工具-落库sweep.py` 文件头部既有体例（"背景+根因+修法+日期"段落格式）追加本次修法说明，含决定性取证摘要与"打破自锁循环 vs 止血少数情形"的结论（对齐 design.md「决策点 2」）。
- [ ] 3.2 队列 #288 行回填：修法定案（先提交再对齐，含 rebase）、被否方案（B/C）及理由指针（指向本变更包 design.md）、测试数、真实验证证据、明确回答"是否打破了自锁循环"（对齐 design.md「决策点 2」的精确结论，不笼统写"已解决"）。

## 4. 验证

- [x] 4.1 全量回归：`工具-落库sweep.py` 自身既有测试套件全绿，零漂移（78 passed，含 6 个新增用例 + 3 处既有用例的必要调整）。
- [ ] 4.2 真实主工作区验证（须在 A 会话——队列 #288 手工解卡——完成之后进行，且须在主工作区而非本 worktree 执行）：真实制造一次"本地队列文件脏（有对应 §二 批次声明）＋ origin 有改动同一文件的新提交"状态，触发一次真实（非 `--dry-run`）sweep 运行，确认批次被正常处理、推送成功，`sweep-commit.log` 无 `SweepAbort` 整轮跳过记录。
- [ ] 4.3 如实记录验证范围边界：若受限于时间/环境未能真实构造"内容真实冲突"这一子场景（该场景概率低、真实触发需要精心构造），须在收工记录中明确写"冲突分支仅经单测覆盖，未经真实主工作区验证"，不得笼统写"已验证"。

## 5. 收工

- [ ] 5.1 `/opsx:archive sweep-ff-sync-batch-reorder -y`（tasks 全部勾选后当场归档，不拖延）。
- [ ] 5.2 队列 §二 登记待 commit 批次，文件清单必须含队列文件自身（协议〇.7 惯例 + #284 计数台账 ① 条）。
- [ ] 5.3 commit + push；收工重跑一次文档台账。
- [ ] 5.4 worktree 收工自删；删不掉则 `git worktree prune` 并如实登记待清。
