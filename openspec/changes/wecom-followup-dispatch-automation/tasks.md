> ⛔ **停止线**：本变更包本轮只做 propose + design。以下任务全部未开始，
> 须等 Shao Peishen 明确批准 design.md 后才可进入 `/opsx:apply`（同队列
> #159／#162 既例）。design 审通过前，任何人不得勾选或执行以下任务。

## 1. README 两态语义落地（D1，硬前置，必须先做）

- [ ] 1.1 `readme_table.py` 新增 `assert_draft_pending_review`（风格对齐 `gates.assert_finalized`）：断言目标行「发送状态」列严格等于 `⏳ 待你审`
- [ ] 1.2 新增 `scripts/approve_followup_letter.py`：`--readme`/`--match-topic`/`--quote`（必填）参数；前置断言 1.1；成功则原子改写状态列为 `🆕 待发` 并写入 `AuditEvent(action="followup_approved", ...)`
- [ ] 1.3 单测覆盖：目标行为 `⏳ 待你审` 时批准成功／非此值时拒绝／未提供 `--quote` 时拒绝／审计事件字段完整性

## 2. 结构性拦截"新建即终态"（D1）

- [ ] 2.1 `工具-共享文档编辑锁.py::_validate_release_structure` 新增 README 专属分支（`--file` 指向跟进信 README 时触发）
- [ ] 2.2 实现"acquire 快照 vs release 快照"比对：新增行 + 状态列为 `🆕 待发` → 拒绝 release
- [ ] 2.3 单测覆盖：新增行写终态被拒／新增行写草稿态放行／既有行草稿态→终态（批准脚本产物）放行

## 3. 硬截止豁免（D3）

- [ ] 3.1 `scripts/dispatch_followup_letters.py` 扫描逻辑新增 `🔒人工发送` 标记识别，命中即跳过
- [ ] 3.2 单测覆盖：标记行即使状态为 `🆕 待发` 也不被处理

## 4. 每日批处理发信任务（D2）

- [ ] 4.1 新增 `scripts/dispatch_followup_letters.py`：扫描 README 全表「发送状态」严格等于 `🆕 待发` 且无 `🔒人工发送` 的行，逐行调用既有 `delivery.push_followup`
- [ ] 4.2 单行失败捕获+记录（审计+日志），继续处理后续行，不中断整批
- [ ] 4.3 批次结束汇总本轮成功/失败清单（日志/审计）
- [ ] 4.4 单测覆盖：多行混合成功失败场景、无待发行场景、`🔒人工发送` 行跳过场景

## 5. 规范文本更新（apply 阶段必做，非代码）

- [ ] 5.1 README-跟进机制与命名约定.md 新增"两态语义"章节：状态值定义、批准脚本用法、`🔒人工发送` 标记约定
- [ ] 5.2 根 CLAUDE.md §5 场景固定流程第8步措辞更新（起草→写 `⏳ 待你审`；引用批准脚本）

## 6. 全量回归与真实部署验证

- [ ] 6.1 `pytest` 全量跑 wecom-aibot-service + 平台底座，零回归
- [ ] 6.2 apply 前核对 `wecom-aibot-channel` 变更包剩余 8 项未完成任务与本变更是否有文件级交集
- [ ] 6.3 真实部署：新增 `ZhuopinFollowupDispatchDaily` 计划任务（`LogonType=Interactive` + `-StartWhenAvailable` + VBS 隐藏启动器，同 `ZhuopinDecisionReminderDaily`/#231 先例）；如涉及需管理员权限设置，整理提权代码块交 Shao Peishen 执行
- [ ] 6.4 端到端真实验证：构造一封测试用 `⏳ 待你审` 信 → 跑批准脚本确认审计留痕 → 手动触发一次 `ZhuopinFollowupDispatchDaily` → 确认真实发送 + README 回填 + 一条 `🔒人工发送` 行确认被跳过

## 7. 收工

- [ ] 7.1 队列 #124 回写（阶段二状态由"已拍板启动"更新为"已交付"）
- [ ] 7.2 CLAUDE.md 当前进度段更新
- [ ] 7.3 commit + push + 收工重跑文档台账
- [ ] 7.4 `/opsx:archive` 本变更包
