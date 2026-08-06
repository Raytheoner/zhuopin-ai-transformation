# Tasks

## 0. 前置：design 审批（阻塞，须 Shao Peishen 审核通过后再进入下列任务）

- [x] 0.1 Shao Peishen 审核 design.md 决策点 1-4，确认候选 A（预期差异校验护栏）+ 决策点 2/3/4 的默认结论，或给出改判 —— 2026-08-06 批准候选 A（原话："(a) 批准候选 A，下个 CC session 直接 apply"）

## 1. 实现护栏

- [x] 1.1 `queue_git_sync.py` 新增 `_diff_exceeds_expected(repo_root, relative_path, *, max_insertions=2, max_deletions=1) -> bool`：用 `git diff --numstat HEAD~1 HEAD -- relative_path` 判断本次本地 commit 相对其父提交的差异规模
- [x] 1.2 冲突重算分支在 `reset --mixed`/`checkout --` 之前调用该函数；命中时 `git reset --soft HEAD~1` 撤销本地 commit，不执行 reset/checkout，`break` 出重试循环并返回一个新的降级结果（`foreign_content_detected=True`，不同于 `exhausted_conflict`）
- [x] 1.3 `GitSyncOutcome`/`sync_after_archive` 接入护栏命中路径：记录 `queue_sync_degraded`（`reason="foreign_dirty_content_detected"`）audit 事件、写入 #286 统一后的暂存通道（`pending_queue_appends.jsonl`，design 决策点2：不新增第三个文件）、发送区分文案的私信告警

## 2. 测试

- [x] 2.1 原 `test_conflict_recompute_destroys_uninvolved_uncommitted_edits` 已重命名为 `test_conflict_recompute_guard_preserves_uninvolved_uncommitted_edits` 并移除 `xfail`——断言人类内容与机器人本次追加均保留在磁盘（工作区未提交状态），origin 不出现任何一方内容，另一写手的推送不受影响
- [x] 2.2 新增护栏未命中场景用例（`test_diff_exceeds_expected_false_for_single_row_insertion`）+ 复用既有 `test_conflict_recomputes_higher_id_instead_of_replaying`（无外来内容时行为与护栏引入前完全一致，仍能重算成功推送）
- [x] 2.3 新增护栏命中后 audit/暂存/告警三处留痕的用例（`test_sync_after_archive_guard_uses_distinct_audit_reason_and_alert_text`），另加 `_diff_exceeds_expected` 直接单测 3 个（命中/未命中/无 `HEAD~1` 保守放行）
- [x] 2.4 全量回归：`tests/test_queue_git_sync.py`（34 个，含 5 个新增护栏用例）/`test_intake.py`/`test_connection.py` 全部保持通过，零回归；`zhuopin_platform` 全量同步核验零回归

## 3. 真实验证（档2晋级条件）——**部署已完成，观察窗口已打开；两项本身仍未做，如实登记**

- [ ] 3.1 常驻服务部署后，观察至少一次真实非快进冲突场景，确认护栏未命中时机器人仍能顺利重算并推送（无外来内容的正常路径不受影响）——**部署已于 2026-08-06 21:51 本地/13:51 UTC 完成**（CC `deployment-debt-cleanup-c70663`：`ops/wecom-service-home` ff-merge 至 `6854f8a`，`ZhuopinAibotDevListener` 重启，PID 110768→110944，`aibot_liveness.json` 心跳戳 `2026-08-06T13:51:26Z` 确认真实建连），观察窗口自此打开；本项仍需等待真实非快进冲突场景实际发生才能核实，留待下次巡逻/CC session
- [ ] 3.2 若观察期内出现真实的"护栏命中"场景，核实降级记录/告警文案清晰可读、人工能据此找到磁盘上待处理的内容——同上，需观察期内真实出现该场景才能核实，非可主动构造（构造真实冲突场景需侵扰生产队列文件，风险不可控）

## 4. 收尾

- [x] 4.1 `queue_git_sync.py` 文件头部机制说明按既有体例补充本次背景与决策
- [x] 4.2 根 `CLAUDE.md`/队列 #287 行回填
- [ ] 4.3 `/opsx:archive aibot-queue-sync-checkout-guard -y` —— **暂不归档**：§3 真实验证两项未完成，按 CLAUDE.md「完工即归档纪律」（tasks 全 [x] 才归档）暂缓，待 §3 两项经真实观察确认后再归档
