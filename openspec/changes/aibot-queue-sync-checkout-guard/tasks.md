# Tasks

## 0. 前置：design 审批（阻塞，须 Shao Peishen 审核通过后再进入下列任务）

- [ ] 0.1 Shao Peishen 审核 design.md 决策点 1-4，确认候选 A（预期差异校验护栏）+ 决策点 2/3/4 的默认结论，或给出改判

## 1. 实现护栏

- [ ] 1.1 `queue_git_sync.py` 新增 `_diff_exceeds_expected(repo_root, relative_path, *, max_insertions=2, max_deletions=1) -> bool`：用 `git diff --numstat HEAD -- relative_path` 判断磁盘相对当次已提交内容的差异规模
- [ ] 1.2 冲突重算分支在 `reset --mixed`/`checkout --` 之前调用该函数；命中时 `git reset --soft HEAD~1` 撤销本地 commit，不执行 reset/checkout，`break` 出重试循环并返回一个新的降级结果（不同于 `exhausted_conflict`）
- [ ] 1.3 `GitSyncOutcome`/`sync_after_archive` 接入护栏命中路径：记录 `queue_sync_degraded`（`reason="foreign_dirty_content_detected"`）audit 事件、写入 #286 统一后的暂存通道、发送区分文案的私信告警

## 2. 测试

- [ ] 2.1 `test_conflict_recompute_destroys_uninvolved_uncommitted_edits`（已作为根因复现用例存在，当前标 `xfail(strict=True)`）——护栏实现后移除 `xfail`，断言人类内容与机器人本次追加均保留在磁盘且被正确处理（不再要求"必须丢失"）
- [ ] 2.2 新增护栏未命中场景用例：磁盘只有本次追加自身差异时，行为与护栏引入前完全一致（复用既有 `test_conflict_recomputes_higher_id_instead_of_replaying` 断言不变）
- [ ] 2.3 新增护栏命中后 audit/暂存/告警三处留痕的用例
- [ ] 2.4 全量回归：`tests/test_queue_git_sync.py`、`test_intake.py`、`test_connection.py` 全部保持通过，零回归

## 3. 真实验证（档2晋级条件）

- [ ] 3.1 常驻服务部署后，观察至少一次真实非快进冲突场景，确认护栏未命中时机器人仍能顺利重算并推送（无外来内容的正常路径不受影响）
- [ ] 3.2 若观察期内出现真实的"护栏命中"场景，核实降级记录/告警文案清晰可读、人工能据此找到磁盘上待处理的内容

## 4. 收尾

- [ ] 4.1 `queue_git_sync.py` 文件头部机制说明按既有体例补充本次背景与决策
- [ ] 4.2 根 `CLAUDE.md` 队列 #287 行回填
- [ ] 4.3 `/opsx:archive aibot-queue-sync-checkout-guard -y`
