# batch-registration-precheck Tasks

> 执行环境：**CC**（写生产码、跑测试、自行 commit+push，一任务一 worktree：`batch-precheck-0904`）。
> 本文件为补件式（实现已完成后回填任务清单），[x] 表示已核实完成，非计划占位。

## 0. 前置闸

- [x] 0.1 `--digest --grep 编辑锁` 与 `--grep sweep` 核触碰区，确认无在办（🔄）行冲突
- [x] 0.2 删除 UI 建 worktree 失败的空分支残留（`claude/op0904g-batch-precheck-1d8dca`／`-e9802f`／`claude/op0904e-batch-precheck-41f327`，均无独立提交、指向 master 历史某点）
- [x] 0.3 建 worktree `batch-precheck-0904`（分支 `claude/op0904g-batch-precheck`，从 master 分出）

## 1. ⓘ1 · 编辑锁批次登记预检

- [x] 1.1 `工具-共享文档编辑锁.py` 新增 `_file_list_git_state_violations`／`_git_known_relative_paths`／`_recent_commit_touched_paths`，复用既有主仓根目录定位逻辑
- [x] 1.2 `cmd_append_row`（§二 分支）与 `cmd_edit_row`（新增的 §二 分支，此前完全没有文件清单校验）接入新校验
- [x] 1.3 fail-loud：不合格项逐一打印，不合并成一句笼统提示
- [x] 1.4 单测 `FileListGitStateViolationTests`（20 例，白盒 `_load_module()` + monkeypatch `REPO_ROOT`）：合格通过／路径不存在／自然语言描述／"同上"「同名」速记／预登记豁免／既有豁免形态保留（wildcard／目录前缀／CLI 参数／代码引用）／git 状态不可得 fail-open／`cmd_append_row`＋`cmd_edit_row` 端到端

## 2. ⓘ2 · 队列文件改动即刻落库

- [x] 2.1 新增 `QUEUE_IMMEDIATE_COMMIT_MESSAGE` 常量与 `_commit_uncovered_queue_changes`
- [x] 2.2 判据：按"该队列文件当前有无待处理 §二 行"判断是否可即刻兜底 commit（判断点 3，design.md）
- [x] 2.3 `main()` 批次处理循环前调用
- [x] 2.4 单测 `ImmediateQueueChangeCommitTests`（2 例）：有未覆盖改动即单独 commit／有在途暂缓批次时不提前冲掉暂缓状态（回归 `BatchIsolationIntegrationTests`）

## 3. ⓘ3 · reconcile autostash

- [x] 3.1 `_reconcile_with_origin_and_push` 新增 `batch_files` 参数
- [x] 3.2 仅 `behind > 0` 时启用；按路径拆分 stash 目标（清单外 stash／清单内保留＋告警）
- [x] 3.3 `git stash push -u -m ... -- <files>`；rebase／ff-only 或 push 成功后 pop
- [x] 3.4 pop 冲突 ⇒ abort 当次 reconcile ＋ 既有告警通道，不静默吞
- [x] 3.5 单测 `ReconcileAutostashTests`（3 例）：清单外文件被 stash 且 pop 回来／清单内文件不被 stash 但发告警／冲突路径 abort

## 4. ⓘ4 · 日志周轮转

- [x] 4.1 `_rotate_sweep_commit_log`（按运行块）／`_rotate_hooks_audit_log`（按 `ts` 逐行）／`_rotate_weekly_logs`（保留 4 周，二者互相隔离）
- [x] 4.2 `main()` 内 `if not args.dry_run:` 段接入
- [x] 4.3 单测 `LogRotationTests`（7 例）

## 5. 回归与收口

- [x] 5.1 `test_工具-共享文档编辑锁.py` 全量：340 passed, 8 subtests passed
- [x] 5.2 `test_工具-落库sweep.py` 全量：382 passed, 51 subtests passed
- [x] 5.3 openspec propose 出件（本次同批，`openspec change validate batch-registration-precheck --strict` 通过）；不强制 design 审逐点拍板（已由 B1 方案批准，见 proposal.md 头部说明）
- [ ] 5.4 commit + `merge-base --is-ancestor` 核对可快进 + `git push origin HEAD:master`
- [ ] 5.5 队列 §二 批次登记 ＋ #381 ⑸ⓘ 回填
- [ ] 5.6 触发一次 sweep（或等待自动轮次），核 `reports/sweep-commit.log` 末几行确认真落库
- [ ] 5.7 `/opsx:archive batch-registration-precheck -y`
