## 1. #192-C 路径对齐（硬前置，必须先做）

- [x] 1.1 `run_aibot_service.py`：`pending_queue_appends_path`/`pending_lock_path` 改用 `resolved_repo_root` 计算，不再用 `SERVICE_DIR / "reports"`
- [x] 1.2 清理 `pending_queue_appends.jsonl` 历史 6 条残留（4 条 subpath bug 已核实过时；2 条经队列文件 grep 确认对应 #149/#175 行内容已存在，确认后清空）
- [x] 1.3 单测覆盖：pending 路径解析结果与 `resolve_audit_path` 同源

## 2. sweep 起跑段改造（#198b → #194 → #192-A → 原流程）

- [x] 2.1 新增 `_abort_if_edit_lock_held`（#198b）：调用编辑锁 `status`，命中"（有效）"文本即 `SweepAbort(exit_code=0)`，零 git 动作；单测覆盖"占用中零 git 动作"
- [x] 2.2 新增 `_push_any_unpushed_commits`（#194）：起跑无条件查未推送提交数，>0 且可快进则补推，不可快进复用 `is_fork` 分叉告警通道；单测覆盖"提交成功推送失败→下一轮自动补推"与"非快进不强推"
- [x] 2.3 新建 `5-平台底座/wecom-aibot-service/scripts/flush_pending_lock_appends.py`（子进程触发脚本，connector=None，git+文件层操作，顺带检查 `pending_queue_appends.jsonl` 是否非空并提示）
- [x] 2.4 sweep 新增 `_flush_pending_lock_appends`（#192-A 主载体）：子进程调用 2.3 脚本，异常捕获记日志不中断；单测覆盖"flush 异常不中断主干"
- [x] 2.5 `main()` 按 D2 顺序接线四步 + 原有流程；新增 `except Exception`（#198a）通用兜底，UTC 日志 + webhook 告警 + 独立退出码 `UNEXPECTED_EXIT_CODE=3`；单测覆盖"注入异常必写日志"
- [x] 2.6 新增 `#198(c)` 常驻服务部署提示：批次落库后检查本轮 add 过的路径是否命中常驻服务前缀；单测覆盖命中/不命中两种

## 3. #192-A 第二道载体：decision_reminder_check.py 接入 flush

- [x] 3.1 `decision_reminder_check.py::_run()` 新增调用 `flush_pending_queue_appends`（复用已建立的 connector/audit/repo_root），失败降级记日志不影响原有决策提醒逻辑
- [x] 3.2 单测覆盖新增调用路径（成功/异常两种）

## 4. #192-B 配对不变式恢复

- [x] 4.1 `find_unreconciled_archives` 新增 `queue_append_pending_flushed` 视为配对清空事件
- [x] 4.2 单测覆盖"推迟→补录→哨兵零误报"

## 5. #193 断连"进行中"提示

- [x] 5.1 新增 `aibot_service/disconnect_inprogress_alert.py`：`compute_next_retry_delay_seconds` + `DisconnectInProgressMonitor`
- [x] 5.2 `connection.py::build_connector` 新增可选参数 `disconnect_alert_fallback_send`，接线 `on_disconnected`/`on_reconnecting`/`on_authenticated`
- [x] 5.3 `run_aibot_service.py` 生产接线：传入已有 `fallback_send`
- [x] 5.4 单测覆盖：超阈值触发一次、同一次断连不重复、恢复后重置去重状态、恢复后仍发既有 gap_alert（不受影响）

## 6. #199 计划任务设置对齐

- [x] 6.1 `register-decision-reminder-task.ps1` 的 `New-ScheduledTaskSettingsSet` 补 `-StartWhenAvailable`
- [x] 6.2 准备自包含的提权命令块（`Set-ScheduledTask` 对齐 `ZhuopinDecisionReminderDaily` 设置 + `wevtutil sl` 启用 Task Scheduler 操作日志），交付给 Shao Peishen
- [ ] 6.3 （待 Shao Peishen 执行后）用 `Get-ScheduledTask`/`Get-ScheduledTaskInfo` 三任务并列输出复核

## 7. 全量回归与真实部署验证

- [x] 7.1 `pytest` 全量跑 wecom-aibot-service + 平台底座，零回归
- [x] 7.2 真实部署 `ops/wecom-service-home` + 重启 `ZhuopinAibotDevListener`（含 `AtStartup` 触发器 + `RestartCount`/`RestartInterval` 二层兜底设置），文件哈希/进程启动时间交叉确认
- [x] 7.3 合入 master 后手动触发 `ZhuopinCommitSweep` 一轮，核 `reports/sweep-commit.log` 新增行
- [x] 7.4 #192-A 场景验证（**未在真实生产队列注入合成测试行**——改用独立 scratch 仓库对真实 `flush_pending_lock_appends.py` 脚本端到端烟测[真实锁获取/队列写入/git commit/推送失败暂存全链路通过]+ 生产 sweep 手动/自动各触发一轮确认新起跑段真实运行[当前无待补录记录，健康态]，详见队列 #192 行内说明）

## 8. 收工

- [x] 8.1 队列 #192/#193/#194/#198/#199 逐行回填（含 #194 一周观察项承接方标注）
- [x] 8.2 CLAUDE.md 当前进度段更新
- [x] 8.3 commit + push + 收工重跑文档台账
- [x] 8.4 openspec archive 本变更包
