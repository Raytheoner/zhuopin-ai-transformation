# sweep-startup-resilience Specification

## Purpose
定义 `工具-落库sweep.py`（每小时定时任务）起跑段新增的四个前置动作（编辑锁探测、未推送提交补推、锁忙推迟暂存 flush、通用异常兜底）与常驻服务改动部署提示的行为契约，确保"失败/推迟已发生"不再静默无痕。
## Requirements
### Requirement: 起跑段编辑锁前置探测
sweep SHALL 在 `_check_preconditions` 之后、任何 git 写动作（`git add`/`git commit`/改队列文件）之前探测协议〇.7 共享编辑锁；锁占用中时 MUST 整轮跳过且不执行任何 git 写动作。

#### Scenario: 编辑锁被占用时零 git 动作
- **WHEN** sweep 起跑时探测到跨桌任务队列编辑锁处于占用状态
- **THEN** sweep 本轮不执行任何 `git add`/`git commit`/队列文件写入，记录跳过原因后正常结束（退出码 0）

### Requirement: 起跑段无条件补推未推送提交
sweep MUST 在每轮起跑时无条件检查本地 `HEAD` 相对 `origin/master` 是否存在未推送提交（`git rev-list --count origin/master..HEAD`），不得仅在"§二 有无待处理批次"为真时才检查；存在且可快进时 SHALL 先补推成功后再继续本轮其余流程；不可快进（已分叉）时 MUST NOT 在此处 `SweepAbort` 整轮中止——SHALL 记录一行日志说明本轮不在此处提前中止，并继续执行本轮其余流程（含 §二 批次处理），把分叉的最终判定、自动对齐尝试与告警职责统一移交给收尾段（`sweep-sync-reconciliation` capability 定义的 `_reconcile_with_origin_and_push`）。

#### Scenario: 提交成功推送失败，下一轮自动补推
- **WHEN** 上一轮 sweep 已在本地完成 commit 但 push 因网络等原因失败
- **THEN** 下一轮 sweep 起跑时必须检测到该未推送提交并尝试补推，补推成功后继续正常批次处理

#### Scenario: 非快进时不强推
- **WHEN** 本地 HEAD 与 origin/master 已分叉（互不为祖先）
- **THEN** sweep 不得在 `_push_any_unpushed_commits` 处强推或 `SweepAbort`，MUST 记录日志后继续执行本轮其余流程（含 §二 批次处理），分叉是否最终导致本轮以非 0 退出码结束，由收尾段的对齐尝试结果决定，而不是在此处一律以非 0 退出码结束

#### Scenario: 分叉但可自动对齐时批次仍正常落库
- **WHEN** 本地 HEAD 与 origin/master 已分叉，且本轮存在待处理的 §二 批次，且分叉双方的改动互不冲突
- **THEN** sweep 完成批次本地提交后，由收尾段自动 `git rebase origin/master` 对齐并统一推送成功，本轮以退出码 0 结束，不触发分叉告警

#### Scenario: 分叉且真实冲突时仍以既有告警语义结束
- **WHEN** 本地 HEAD 与 origin/master 已分叉，且分叉双方的改动存在真实内容冲突（无法自动合并）
- **THEN** 收尾段执行 `git rebase --abort` 回滚，sweep 以 `is_fork=True`、`FORK_EXIT_CODE` 结束本轮，触发既有 webhook 分叉告警通道与连续轮次持久化，语义与本次修法前完全一致

### Requirement: 锁忙推迟暂存文件的定时 flush
sweep MUST 在取得自身编辑锁的窗口之外，每轮尝试 flush 一次 `pending_queue_lock_appends.jsonl`（锁忙推迟的机器人写队列暂存），flush 过程中的异常 MUST 被捕获并记入日志后继续跑后续批次处理，不得让 flush 异常中断整轮 sweep。

#### Scenario: 锁忙推迟到下一轮自动补录
- **WHEN** 企微机器人写队列时因编辑锁占用而将内容暂存至 `pending_queue_lock_appends.jsonl`
- **THEN** 下一轮 sweep 起跑时必须自动把该暂存内容补录进队列文件，且哨兵不得因此产生误报

#### Scenario: flush 异常不中断主干
- **WHEN** flush `pending_queue_lock_appends.jsonl` 过程中抛出异常（如目标文件被并发写入损坏）
- **THEN** sweep 必须捕获该异常、记入日志，并继续执行后续的批次处理流程

### Requirement: main() 通用异常兜底
sweep 的 `main()` MUST 包住一个通用异常处理层，捕获所有未被 `SweepAbort` 覆盖的未预期异常；捕获后 SHALL 记一行含 UTC 时间戳的日志（格式如 `✗ 未预期异常：<类型>: <消息>` + traceback 末几行）、通过既有 webhook 告警通道发出告警，并以一个与"健康跳过（退出码0）"、"分叉（`FORK_EXIT_CODE`）"均不同的独立退出码结束。

#### Scenario: 未预期异常被捕获并留痕
- **WHEN** sweep 运行过程中抛出未被 `SweepAbort` 覆盖的异常
- **THEN** sweep 必须写入含 UTC 标注的日志行、发出 webhook 告警，并以独立退出码（非 0、非 `FORK_EXIT_CODE`）结束，不得让异常无痕退出

### Requirement: 常驻服务改动部署提示
当本轮 sweep 处理的批次命中有常驻服务副本的路径（如 `5-平台底座/wecom-aibot-service/`）时，SHALL 在日志与 webhook 告警中附加一句提示，说明该改动需经部署脚本同步并重启对应计划任务后才在生产生效；该提示仅为纯提示，不得阻断本轮处理，不得改变本轮退出码。

#### Scenario: 命中常驻服务路径时附加提示
- **WHEN** 本轮落库的批次文件清单中包含 `5-平台底座/wecom-aibot-service/` 下的路径
- **THEN** sweep 在日志与告警中附加部署提示，且本轮仍按原有逻辑正常完成、退出码不受影响

