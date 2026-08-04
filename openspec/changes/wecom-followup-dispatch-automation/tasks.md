> ✅ **design 审已于 2026-08-04 由 Shao Peishen 通过，D1-D5 全部批准**，
> 附加两条追加要求（D6 批准冷却窗口 / D7 疑似漏标硬截止机器判据，见
> design.md），现进入 apply 阶段。

## 0. apply 前置核对

- [x] 0.1 核对 `wecom-aibot-channel` 变更包剩余 8 项未完成任务（7.2/8.5/9.1-9.5/10.5）与本变更文件级交集——均为测试/观察/部署文档/收工动作，未触碰 `readme_table.py`/`gates.py`/`delivery.py`，无冲突，可并行推进

## 1. README 两态语义落地（D1，硬前置，必须先做）

- [x] 1.1 `readme_table.py` 新增 `assert_draft_pending_review`（风格对齐 `gates.assert_finalized`）：断言目标行「发送状态」列严格等于 `⏳ 待你审`
- [x] 1.2 新增 `scripts/approve_followup_letter.py`：`--readme`/`--match-topic`/`--quote`（必填）参数；前置断言 1.1；成功则原子改写状态列为 `🆕 待发` 并写入 `AuditEvent(action="followup_approved", ...)`
- [x] 1.3 单测覆盖：目标行为 `⏳ 待你审` 时批准成功／非此值时拒绝／未提供 `--quote` 时拒绝／审计事件字段完整性
- [x] 1.4（D6 追加）`aibot_service/approval.py::check_cooldown` 批准冷却窗口（默认 10 分钟）：首次观测记录时刻并拒绝／窗口内重复调用仍拒绝／满窗口后正常批准；`scripts/approve_followup_letter.py` 接入，单测覆盖三态

## 2. 结构性拦截"新建即终态"（D1）

- [x] 2.1 `工具-共享文档编辑锁.py::_validate_followup_readme_release`（新增独立分支，`--file` 指向跟进信 README 时触发）
- [x] 2.2 实现"acquire 快照 vs release 快照"比对：新增行（身份=除状态列外全部单元格）+ 状态列为 `🆕 待发` → 拒绝 release
- [x] 2.3 单测覆盖：新增行写终态被拒／新增行写草稿态放行／既有行草稿态→终态（批准脚本产物）放行／非终态行编辑不受影响

## 3. 硬截止豁免（D3）+ 机器判据兜底（D7）

- [x] 3.1 `aibot_service/dispatch.py` 扫描逻辑新增 `🔒人工发送` 标记识别，命中即跳过
- [x] 3.2 单测覆盖：标记行即使状态为 `🆕 待发` 也不被处理
- [x] 3.3（D7 追加）`has_unmarked_imminent_deadline`：交期要点列含严格 `YYYY-MM-DD` 明确日期且距今 < 3 天、未标 `🔒人工发送` → 结构性跳过 + 审计留痕；批处理脚本对命中行汇总私信告警
- [x] 3.4 单测覆盖：临近未标记命中／已标记不命中／远期日期不命中／纯相对表述（"本周五"等）不命中

## 4. 每日批处理发信任务（D2）

- [x] 4.1 新增 `aibot_service/dispatch.py::dispatch_followup_letters` + `scripts/dispatch_followup_letters.py`：扫描 README 全表「发送状态」严格等于 `🆕 待发` 且无 `🔒人工发送`/未命中 D7 判据的行，按 R4 命名律从收信人+日期推导 md/docx 路径与 chatid，逐行调用既有 `delivery.push_followup`
- [x] 4.2 单行失败（收件人/文件不可解析、推送失败）捕获+记录（审计+日志），继续处理后续行，不中断整批
- [x] 4.3 批次结束汇总本轮成功/失败/跳过清单（日志/审计 `dispatch_batch_summary`）
- [x] 4.4 单测覆盖：多行混合成功失败场景、无待发行场景、`🔒人工发送` 行跳过场景、收件人/文件解析失败场景

## 5. 规范文本更新（apply 阶段必做，非代码）

- [x] 5.1 README-跟进机制与命名约定.md 新增"两态语义"章节：状态值定义、编辑锁用法、批准脚本用法（含冷却窗口）、`🔒人工发送` 标记约定、机器兜底判据说明、每日批处理任务说明
- [x] 5.2 根 CLAUDE.md §5 场景固定流程第8步措辞更新（起草→写 `⏳ 待你审`；引用批准脚本）

## 6. 全量回归与真实部署验证

- [ ] 6.1 `pytest` 全量跑 wecom-aibot-service + 平台底座，零回归
- [x] 6.2 apply 前核对 `wecom-aibot-channel` 变更包剩余 8 项未完成任务与本变更是否有文件级交集（见 0.1，已确认无交集）
- [ ] 6.3 真实部署：新增 `ZhuopinFollowupDispatchDaily` 计划任务（工作日 **09:30**，`LogonType=Interactive` + `-StartWhenAvailable` + VBS 隐藏启动器，同 `ZhuopinDecisionReminderDaily`/#231 先例）；如涉及需管理员权限设置，整理提权代码块交 Shao Peishen 执行；复核 `Actions[0].Execute` 应为 `wscript.exe`
- [ ] 6.4 端到端真实验证：构造一封测试用 `⏳ 待你审` 信 → 跑批准脚本确认冷却窗口生效+审计留痕 → 满冷却窗口后批准成功 → 手动触发一次 `ZhuopinFollowupDispatchDaily` → 确认真实发送 + README 回填 + 一条 `🔒人工发送` 行确认被跳过

## 7. 收工

- [ ] 7.1 队列 #124 回写（阶段二状态由"已拍板启动"更新为"已交付"）
- [ ] 7.2 CLAUDE.md 当前进度段更新
- [ ] 7.3 commit + push + 收工重跑文档台账 + §二 登记批次
- [ ] 7.4 `/opsx:archive` 本变更包
