## Context

见 proposal.md — Why/What Changes。本节只记支撑设计选择的现状约束：

- `工具-落库sweep.py` 是零外部依赖的独立脚本（刻意不 import `zhuopin_platform`/`aibot_service`，见其 `_send_wecom_markdown` 注释——原因是本仓库多 worktree 共享全局 `pip install -e` 目标，裸包名 import 可能被静默劫持到别的 checkout，参见跨会话记忆 `project_shared_python_editable_install_collision`）。任何需要 `aibot_service`/`zhuopin_platform` 能力的新增动作必须走子进程，不能在 sweep 自身进程内 `import`。
- `工具-共享文档编辑锁.py` 提供 `acquire`/`release`/`status` 三个子命令；`status` 无副作用，输出文本里"（有效）"三字唯一标出"当前被人类/机器人有效持锁"，其余两态（无锁/已陈旧可接管）不含此三字——探锁前置可直接复用，不需要改锁工具本身。
- `flush_pending_queue_appends`（`aibot_service.queue_lock_pending`）已是"显式入参 + `connector=None` 可选"的纯编排函数，不强依赖企微实时连接，可从独立进程调用（队列 #192 行内已核实）。
- 队列 #192 行内 2026-08-02 拍板：flush `pending_queue_lock_appends.jsonl` 走**双载体**——sweep（每小时，主）+ `ZhuopinDecisionReminderDaily`（每日，第二道），两处各调一次，不新建后台常驻逻辑。
- 企微 SDK（`aibot` 包）重连退避公式已读源码确认：`delay_ms = min(base_delay_ms * 2**(attempt-1), 30000)`（`aibot/ws.py::_schedule_reconnect`），该值不经 `AibotConnector` 构造参数暴露，只能按已知实现在本仓库内独立复现。
- `ZhuopinDecisionReminderDaily` 计划任务的 `AllowStartIfOnBatteries`/`DontStopIfGoingOnBatteries` 已通过真实 `Get-ScheduledTask` 核实生效（`DisallowStartIfOnBatteries=False`/`StopIfGoingOnBatteries=False`），只有 `StartWhenAvailable=False` 需要修——#199 的改动范围比队列行文本描述的更窄。
- Task Scheduler 操作日志（`Microsoft-Windows-TaskScheduler/Operational`）当前**未启用**（本机核实），`0x800710E0` 08-01 那次的触发条件因此**没有历史事件可查**，无法回溯——只能如实标注"未查清"，并顺带把启用该日志（供未来同类问题追查）纳入需 Shao Peishen 提权执行的那个代码块。

## Goals / Non-Goals

**Goals:**
- 五行队列项（#192-A/B/C、#193、#194、#198(a)(b)(c)、#199）在同一变更包内交付，覆盖 proposal.md 列出的全部行为契约。
- `工具-落库sweep.py` 起跑段严格按队列 #192 行内写死的顺序改造，不自行调整。
- 所有新增行为向后兼容：未触发新增分支时，既有行为（含现有测试断言）不变。

**Non-Goals:**
- 不做 git push 失败的重试/退避机制（#194 行内明确"本次只做补推这一半"，重试退避留给一周观察后再评估）。
- 不新建后台常驻定时逻辑（#192-A 双载体复用两个已存在的计划任务，不新增第三个）。
- 不追加多级"进行中"提示升级梯度（#193 spec 只要求"同一次断连不重复"，不做类似 #172 的 1/3/7 天多级升级——断连episode 通常是秒级/分钟级，不适用天级梯度）。
- 不回溯诊断 `0x800710E0` 08-01 那次的根因（操作日志当时未启用，物理上不可能回溯）。

## Decisions

### D1 · sweep 起跑段新增步骤一律走子进程/文本探测，不在主进程 import aibot_service

`_flush_pending_lock_appends`（#192-A）通过 `subprocess.run([sys.executable, <独立脚本>], cwd=repo_root)` 调用一个新增的一次性触发脚本 `5-平台底座/wecom-aibot-service/scripts/flush_pending_lock_appends.py`（复用 `decision_reminder_check.py` 已确立的路径解析样板：`sys.path.insert(0, SERVICE_DIR)` + `resolve_repo_root`），子进程失败只降级记日志，不影响 sweep 自身。`_abort_if_edit_lock_held`（#198b）复用现有 `_edit_lock(repo_root, "status")` 子进程调用，解析 stdout 文本判断。两者均不新增 sweep 对 `zhuopin_platform`/`aibot_service` 的 import 依赖——与 sweep 现有"零依赖"设计保持一致，规避多 worktree editable-install 劫持风险。

替代方案：直接在 sweep 进程内 `sys.path.insert` 后 `import aibot_service...`。放弃理由：`zhuopin_platform` 包本身仍经全局 site-packages editable-install 解析，无法用 `sys.path.insert(SERVICE_DIR)` 规避（`SERVICE_DIR` 只能让 `aibot_service` 自身解析正确，管不到它依赖的 `zhuopin_platform`）；一旦某次有人从别的 worktree 重跑 `pip install -e`，sweep（每小时生产任务）会静默加载错误 checkout 的审计/连接逻辑，风险不对称地高于多起一个子进程的成本。

### D2 · sweep 起跑段最终执行顺序

严格按队列 #192 行内写死顺序实现（`main()` 内，`_check_preconditions` 之后）：
1. `_abort_if_edit_lock_held`（#198b）—— 命中"（有效）"文本立即 `SweepAbort(exit_code=0)`，不做任何 git 动作。
2. `_push_any_unpushed_commits`（#194）—— `_fetch` 后查 `rev-list --count origin/master..HEAD`；>0 且可快进则补推；不可快进复用 `is_fork=True` 分叉告警通道（#171）+ `FORK_EXIT_CODE`；补推 push 失败则 `exit_code=2`。
3. `_flush_pending_lock_appends`（#192-A 主载体）—— 子进程调用，失败只记日志不中断。
4. 原有流程不变：`_sync_master_if_behind_origin` → `_verify_fast_forward`（起跑分叉检测）→ `_reset_fork_state` → 批次解析与处理。
5. `#198(c)` 部署提示挂在批次处理**之后**（commit 落库后，与队列行内"部署提示在批次落库后触发"一致）——检查本轮 `_process_normal_batch`/尾巴批次实际 `git add` 过的路径是否命中常驻服务前缀，命中则在 `log`/webhook 追加一句提示。
6. `main()` 整体包一层 `except Exception`（#198a，架在既有 `except SweepAbort` 之外层），写 UTC 日志行 + 复用 #171 webhook 告警 + 独立退出码 `UNEXPECTED_EXIT_CODE = 3`。

### D3 · #192-B 配对不变式：修哨兵而非改写路径

在 `find_unreconciled_archives` 里把 `queue_append_pending_flushed` 与 `queue_appended` 一并视为"清空 pending"的配对事件（一行 `elif` 分支扩展），不改 `queue_lock_pending.py` 的写入内容。

替代方案：在 `flush_pending_queue_appends` 补录成功时额外记一条 `queue_appended`。放弃理由：会让同一条消息在审计流里产生两个语义相近但触发路径不同的 action（`queue_append_pending_flushed` 与补记的 `queue_appended`），增加下游任何按 action 计数/统计的读者的解释成本；哨兵是唯一消费这条不变式的读者，改哨兵是最小影响面的修法。

### D4 · #192-C pending 路径对齐 + 历史残留处置

`run_aibot_service.py` 的 `pending_queue_appends_path`/`pending_lock_path` 改为基于 `resolved_repo_root` 计算（与 `audit_path` 同一套解析结果），不再用 `SERVICE_DIR / "reports"`。`pending_queue_appends.jsonl` 的消费方选**最小可行方案**——在新增的 `flush_pending_lock_appends.py` 脚本里顺带检查该文件是否非空，非空则在日志/webhook 里报一条"N 条历史队列同步失败记录待人工核对"（不自动重放，只提醒；理由：重放需要重新计算队列编号，存在与已发生的正常提交冲突的风险，超出本批"消解可见性"的范围）。已核实现存 6 条记录中 4 条为 #126 已修复的 subpath bug 残留、2 条经 grep 队列文件确认对应的 #149/#175 行内容已存在（`7cb2bcf...`/`51efeabe...` 均命中），清空该文件（6 条全部确认可清，过程见任务记录）。

### D5 · #193 断连"进行中"提示：基于连接生命周期回调，不复用 liveness.py 心跳文件本身

新增 `aibot_service/disconnect_inprogress_alert.py`：`DisconnectInProgressMonitor` 挂在 `connection.py::build_connector` 内部，用 `on_disconnected`/`on_reconnecting`/`on_authenticated` 三个既有回调驱动状态机（断开→计时器 `asyncio.create_task`→超阈值 `fallback_send` 一次；重新认证成功→取消计时器，为下一次断连重置去重状态）。阈值 `DEFAULT_THRESHOLD_SECONDS=75`（60~90 秒区间取中值，可通过 `build_connector` 新增可选参数覆盖）。

`liveness.py` 心跳文件是 5 分钟粒度的**进程存活**信号（与连接状态无关，见其模块 docstring），粒度上无法支撑 60~90 秒阈值判断——本设计只复用其"轻量、刻意不进审计链"的设计取向（`DisconnectInProgressMonitor` 发送提示不写审计事件，理由与心跳一致：这是运行时状态通知，不是 AI 决策），不复用心跳文件本身作触发信号。触发信号改用 `connection.py` 已有的、精度以秒计的连接生命周期回调，是本设计与"字面复用 liveness.py"相比更贴合 60~90 秒阈值精度要求的选择，属队列行文本"判据可直接复用"的合理技术落地（其表述的核心诉求是"轻量+不进审计链"，非"必须读同一个文件"）。

发送通道**必须是 `fallback_send`（独立 webhook）**，不能是 `connector.send_markdown`——断连期间该连接本身就是坏的，尝试用它发送必然失败（与 `gap_alert.py` 2026-07-19 事故同一教训）。`build_connector` 新增可选参数 `disconnect_alert_fallback_send`（默认 `None` → 功能关闭，向后兼容），生产接线复用 `run_aibot_service.py` 已有的 `fallback_send`（同一个 webhook）。

次要项（`AtStartup` 触发器 + `RestartCount`/`RestartInterval`）在部署阶段直接对 `ZhuopinAibotDevListener` 计划任务设置调整，不新增代码。

### D6 · #199 分两步，(1) 停在"如实留白"，(2) 只改 `-StartWhenAvailable`

(1) 已用真实 `Get-ScheduledTask`/`Get-ScheduledTaskInfo` 核实：`AllowStartIfOnBatteries`/`DontStopIfGoingOnBatteries` 已生效，唯一缺口是 `StartWhenAvailable=False`；`Microsoft-Windows-TaskScheduler/Operational` 日志当前未启用（本机核实，启用本身需管理员权限，已确认 Access denied），`0x800710E0` 08-01 那次无历史事件可查，**如实标注"未查清，物理上不可回溯"**，不编造解释。启用该日志（供未来同类问题追查，非本次可用）纳入 (2) 的提权代码块一并做。

(2) 改 `register-decision-reminder-task.ps1` 的 `New-ScheduledTaskSettingsSet` 调用补 `-StartWhenAvailable`；准备一个自包含的 `Set-ScheduledTask` 单命令块（不依赖 worktree/python 路径，直接对活跃任务生效）+ `wevtutil sl ... /e:true`（启用操作日志）一并交给 Shao Peishen 执行；执行后用 `Get-ScheduledTask`/`Get-ScheduledTaskInfo` 三任务并列输出复核，不采信"他说跑过了"。

## Risks / Trade-offs

- [风险] `_abort_if_edit_lock_held` 依赖对 `工具-共享文档编辑锁.py status` 子命令 stdout 文本的字符串匹配（"（有效）"），锁工具措辞变化会静默破坏这一判断 → 缓解：新增单测直接断言真实脚本的 `status` 输出格式，锁工具改动时会被测试捕获；且探锁失败的最坏后果是"多跳过一轮"（保守方向），不会误伤。
- [风险] `_push_any_unpushed_commits` 在极端情况下（HEAD 恰好等于 origin/master 但网络分区导致 fetch 返回陈旧数据）可能误判 ahead=0 而跳过 → 缓解：与既有 `_verify_fast_forward` 面临的是同一类风险（fetch 本身失败已有前置 `_fetch` 的 `SweepAbort`），不引入新的风险面。
- [权衡] `#193` 的"进行中提示"选择单次触发（同一次断连只发一次），不做多级升级 → 若断连持续数小时，用户只在第 75 秒收到一次提示，此后无更新，直至恢复才收到 `gap_alert`。可接受：队列行本身未要求多级升级，且断连超过几分钟本就是罕见事件（历史仅一例真实 6 分钟断连）。
- [风险] `flush_pending_lock_appends.py` 走子进程，若 `zhuopin_platform` 编辑安装当前指向的 checkout 恰好落后/不一致，子进程仍可能读到错误代码 → 与 D1 已知的多 worktree editable-install 风险同源，本变更不新增也不消除这一既有风险，只是不放大它（不引入新的进程内 import）。
- [已知限制] `0x800710E0` 08-01 触发条件无法回溯（操作日志当时未启用）——已在 D6 中显式列为不可解决项，验收时不得要求给出成因结论。

## Migration Plan

1. TDD 实现全部代码改动（sweep + aibot_service 各模块 + 新增脚本），全量回归零漂移。
2. 更新 `register-decision-reminder-task.ps1` 源码；不在本地/CI 环境执行需管理员权限的 `Set-ScheduledTask`（留给 Shao Peishen 手动执行的独立代码块）。
3. 合入 master。
4. 真实部署 `ops/wecom-service-home`（`sync-to-server.ps1` 或等效同步）+ 重启 `ZhuopinAibotDevListener`，文件哈希/进程启动时间交叉确认新代码已加载。
5. 手动触发一轮 `ZhuopinCommitSweep`（`Start-ScheduledTask`），核 `reports/sweep-commit.log` 新增行——本轮是新起跑段代码的真实首跑。
6. 交付提权代码块给 Shao Peishen；其执行后用 `Get-ScheduledTask`/`Get-ScheduledTaskInfo` 复核。
7. 真实构造一次"锁忙推迟 → 下一轮 sweep 自动补录"场景（#192-A 验收物）。

**回滚**：均为在既有函数/文件内新增前置检查与告警路径，未改变任何既有正常路径的输出结构；回滚即 `git revert` 本批合并提交，重新部署/重启对应服务即可，无数据迁移、无需额外清理步骤。

## Open Questions

（无——五行范围与验收标准已在队列行内+ proposal.md 写清，无遗留需要在实现中途升级决策的未知项。）
