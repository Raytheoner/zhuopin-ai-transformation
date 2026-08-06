# aibot-queue-sync-checkout-guard Proposal

## Why

`5-平台底座/wecom-aibot-service/aibot_service/queue_git_sync.py::append_task_and_sync_to_git` 在推送遇非快进冲突（origin 已前进，日常高频场景，2026-08-06 单日近 20 个提交 100% 触碰队列文件）时，走"对齐后重算"路径：

```
_run_git(resolved_repo_root, "fetch", remote)
_run_git(resolved_repo_root, "reset", "--mixed", f"{remote}/{branch}")
_run_git(resolved_repo_root, "checkout", "--", relative_path)
```

`checkout -- relative_path` 把队列文件的**工作区内容**整体替换成 `reset --mixed` 刚写入索引的 origin 版本。协议〇.7/〇.8 的既有设计前提是：人类会话 `acquire` 编辑锁→写盘→`release` 后，改动**只落工作区、尚未 commit**，要等 sweep 处理 §二 批次时才真正提交——即"工作区脏但未提交"是这份文件的**正常、预期**状态，可持续数分钟到数小时。`_commit` 的 `git add relative_path` 会把这一刻磁盘上的**全部**内容（含任何人类会话已释放但未提交的成果）一并暂存进机器人的本地 commit；一旦该 commit 推送失败（几乎必然，见上），`reset --mixed` + `checkout --` 会把这个混合了人类成果的本地 commit 连根拔起、工作区回退到 origin 版本——人类的成果既不在工作区，也不在任何可达的 git 历史里（本地 commit 变为悬空对象，未被引用，终将被 gc）。

2026-08-06 拆件巡逻第二班取证（队列 #287）：第一班 09:19 `--reserve-multi` 写入的 §一 #280/#281、§四 #53、一个 §二 批次全部消失，其 `release` 回执与 diff 校验当时均显示成功；时间窗收敛到与机器人 `bot(队列): 自动追行 #280`（`4907dd7`，09:25:55）同一执行体。`4907dd7` 的 diff 相对其父提交 `c852883` 仅为"新增一行＋高水位线自增"（2 行插入/1 行删除），不含第一班的任何内容，且第一班保留的编号 #280/#281 被机器人以完全不同的内容"二次分配"——与"工作区先被 reset/checkout 抹回 `c852883` 基线、机器人再据此基线重新计算出同一个编号"完全吻合。

本变更包用真实 git 子进程 + 真实调用生产函数复现了该机制（`tests/test_queue_git_sync.py::test_conflict_recompute_destroys_uninvolved_uncommitted_edits`，非 mock）：clone 中先写入一段代表"人类已 release 未 commit"的工作区改动，再由另一 clone 制造非快进冲突，调用 `append_task_and_sync_to_git` 后该改动从工作区与推送结果中彻底消失——根因已用代码路径坐实，不再是推断。

它比同日 #286（队列行经"锁忙补录"两个暂存文件分裂而遗失，好歹留有暂存记录与 4 次告警）更严重：本次没有任何暂存记录、没有告警——锁与结构校验都正常工作，只是它们保护的那份文件在其之外被整体替换。

## What Changes

- **`append_task_and_sync_to_git` 在执行任何会覆盖工作区文件内容的操作（`reset --mixed` 之后紧跟的 `checkout --`）之前，新增一道"预期 vs 实际"护栏**：把"本次追加应当产生的最小差异"（新增一行＋可能的高水位线自增，至多几行）与"磁盘相对当次已提交内容的实际差异"比对，实际差异明显超出预期即判定磁盘上存在与本次追加无关的外来未提交内容，**放弃这次销毁性 reset/checkout**，转入暂存/告警路径（复用 #286 统一后的暂存通道），工作区原样不动。
- **新增"已 release 的改动被抹"检出判据**：在 sweep（`工具-落库sweep.py`）或对账哨兵（`queue_reconcile_sentinel.py`）一侧补一条"§二 存在待处理批次却整轮消失"或"归档件数/queue_appended 计数↔队列可见行数不等"的检出（与 #286 的对账判据合并落地，避免重复造轮子）。
- **不改变** `append_task_and_sync_to_git` 的对外函数签名、返回值形状（`GitSyncOutcome`）、"非快进重算/网络失败保留本地 commit/重试耗尽 reset --hard"三类既有失败语义的调用方契约——只在"即将执行销毁性操作"这一个时刻插入一道新的安全检查，检查未命中时行为与现状完全一致。
- 本变更**不**扩大编辑锁的持有范围、**不**要求机器人在追加前抢占式持锁数分钟（design.md「候选方案对比」记录了为何持锁类方案对本场景无效——协议〇.7/〇.8 本身允许"锁已释放但内容未提交"这一合法状态持续存在，锁语义解决不了这个问题）。

## Capabilities

### New Capabilities

- `aibot-queue-sync-write-safety`：`queue_git_sync.append_task_and_sync_to_git` 在冲突重算时对工作区文件执行销毁性操作前的安全契约——预期差异校验、护栏命中时的降级路径、与既有失败语义（非快进重试/网络失败保留/重试耗尽清空）的边界。

### Modified Capabilities

（无——本变更不改变 `append_task_and_sync_to_git` 现有对外契约的既有三类失败语义，只在其中"非快进重算"分支内新增一个前置检查点。）

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

1. **本流程哪些判断是人脑默会经验？** "多大的意外差异算『有外来内容』"目前是一个经验阈值（本次追加至多产生"新增一行 ＋ 高水位线自增一行"共 2-3 行差异，超出此规模即判定异常），不是从协议文本直接推导出的唯一正确数字；design.md「决策点」记录了阈值选择的依据与边界情况。
2. **由谁显性化？** CC 平台（本变更包设计与实现）；持有人＝本次执行 session；backup/仲裁＝Shao Peishen（design.md 须经其审核批准方可 `/opsx:apply`，命中 CLAUDE.md §5「机制/工具类模块的 openspec 触发门槛」第③条「改变既有模块的对外语义（冲突时如何取舍变了）」）。
3. **用什么方法提取？** 真实事故复盘＋真实代码路径复现——队列 #287 第二班取证给出完整时间线与 commit 级证据，本变更包在其基础上用真实 bare origin + 真实 git 子进程写出可复现用例，不依赖 mock，也不依赖对生产环境的二次猜测。

## 验收与晋档条件（强制，四档口径）

- **本变更包交付后场景所处档位**：跨项目治理机制（企微机器人是平台侧公共基础设施，非独立业务场景），套用最接近档位＝**档1 mock 验证**（design 审通过、代码与单测完成，含真实 git 子进程的确定性复现用例，但尚未在生产常驻服务的真实并发场景下验证一次"人类 release 未 commit 与机器人冲突重算恰好重叠"）。
- **晋下一档的条件**：晋**档2 真实数据跑通**——① 单测覆盖护栏命中（拦截销毁）与未命中（现状行为不变）两条路径；② 全量回归零漂移（`tests/test_queue_git_sync.py`/`test_intake.py`/`test_connection.py` 既有用例全部保持通过）；③ 常驻服务部署后观察至少一次真实非快进冲突场景，确认护栏未误伤正常重算（即"无外来内容"时仍能顺利重算并推送）。
- **价值指标**（风险型）：消除"机器人冲突重算销毁人类已 release 未 commit 内容"这一数据丢失路径——基线＝2026-08-06 当日 #287 一次真实发生（若非第一班报告文件恰好已被后续手工提交带入 git 历史，将完全无痕），目标＝护栏命中时旧内容零丢失、有告警留痕。
- **LLM 判据黄金集**：不适用（纯 git 操作控制流修法，不含 LLM 运行时判断）。

## Impact

- 受影响代码：`5-平台底座/wecom-aibot-service/aibot_service/queue_git_sync.py`（`append_task_and_sync_to_git` 冲突重算分支新增护栏）；如护栏命中路径复用 #286 统一后的暂存通道，`queue_lock_pending.py`/`repo_paths.py` 可能有少量接线改动。
- 受影响测试：`tests/test_queue_git_sync.py`（新增护栏命中/未命中两类用例；`test_conflict_recompute_destroys_uninvolved_uncommitted_edits` 作为根因复现用例，`/opsx:apply` 后应由 `xfail` 转为正常通过）。
- 受影响文档：本变更包归档后，`queue_git_sync.py` 文件头部机制说明按既有体例补充本次背景；根 `CLAUDE.md` 队列 #287 行回填。
- 红线核对：mock 先行——不适用（无新数据源接入）；audit 留痕——护栏命中时新增一条降级/告警 audit 事件，复用既有 `queue_sync_degraded` 事件形状；OEM 隔离——不适用；L2 人工确认门禁——不适用（内部机制工具）；ISO 26262——不适用。
