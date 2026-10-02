# Codex 业务 Workflow 全量收口差距表

记录日期：2026-09-30（本机 UTC+8）。本表根据 Shao Peishen 当前会话的六入口验收要求整理；不是新的实施授权，也不把历史或 mock 证据当本次完整验收。

## 结论

基础 Codex provider、原生 hooks、隔离工作树与三消费者已有规定范围历史验收。候选分支具备通用阶段驱动和人守 Guardian，但最终源码的原生建造整链、业务口令观察入口、值周计划、机器人新回件自动消费尚未形成一套完整验收。主仓与候选入口仍不同步。当前不能称业务 Workflow MVP 已跑通。

## 六入口

| 用户入口 | 已有能力 | 本次必须补齐的证据/交付 |
|---|---|---|
| 开启泳道看护 | 候选skill已映射Guardian start；队列/LAN/manifest/暂停恢复/原生stage驱动已有实现 | 从业务口令真实启动批准任务，经设计停点/答复、实施、CI、独立review到release-prep；任务与代码版本全程一致；正式交付候选入口 |
| 看看泳道 | 现有状态机show --json与Guardian observe --batch | 自然语言入口能找到当前批次，输出任务实际phase/停点/失败/下一动作；无旧Claude transcript依赖；只读且不额外触发构建 |
| 机器人监听 | 本机ZhuopinAibotDevListener计划任务Running（2026-09-30 11:39 +08:00读取）；监听启动时间2026-09-28 06:00:11 +08:00 | 核对单监听及消费者身份，启停/恢复可追溯；计划任务运行不等于模型消费通过 |
| 跟进信回灌自动归档拆件 | intake/匹配/归档/队列追加与Codex provider已有接缝；历史110项脱敏联测包含测试替身 | 当前patrol.enabled=false、model=inherit；需用脱敏回件跑实际Codex模型并验证归档/拆件/入队/重复抑制，再按批准启用实际消费，保留失败信号；不能擅自发送真实消息 |
| 值周计划 | 源weekly-status-update任务规则和队列审计工具存在 | 明确Codex手动口令入口及实际调度归属，生成一份基于现时队列的计划并验证有主/截止/承接；不把保存技能当已调度 |
| 回LAN收口 | 源收口skill、LAN探针、转出/逐项部署授权/串行快照冒烟回滚规则已有 | Codex入口映射与off/unknown拒绝/转出证据；真实On LAN时针对明确对象验收快照→执行→冒烟→回写；生产与外发仍单独授权 |

## 本机只读快照

- ZhuopinAibotDevListener：Running；只证明监听任务运行。
- ZhuopinPollGuard：Disabled。
- ZhuopinFollowupDispatchDaily：Ready，2026-09-30 09:30 +08:00 最近退出码0。
- ZhuopinDecisionReminderDaily：Ready，2026-09-30 08:30:01 +08:00 最近退出码0。
- ZhuopinCommitSweep：Ready，2026-09-30 11:17:02 +08:00 最近退出码0。
- 主仓 .codex/consumers.local.json 的 patrol.enabled=false；本次只读，没有启用。
- 原始筛选快照：C:/Users/Paul Shao/AppData/Local/Temp/workflow-mvp-0930-task-snapshot.json。未输出启动参数、令牌或密钥。

## 当前修复与验收进度

四文件自举修复完成首轮38项定点验证，解决后续授权正文、Luna路由、有限失败摘要和gate恢复判断。独立审查P2敏感摘要出口已修；另发现P1：timeout并不等于进程树已确认终止，恢复前必须验证终止证据。P1仍修复中；完整回归已明确中止保留日志，不能宣称通过。

旧v5保留。最终候选须以修复后的bootstrap基线承接原字节已批准v5设计，再建立真实新任务/HEAD绑定并验收。不得混用旧HEAD的CI/review报告。

## 下一份集中批准包应包含

1. 实际bootstrap与承接任务版本、固定设计哈希、精确允许路径及同阶段有界重试。
2. 六入口缺口的最小适配文件与验收矩阵；区分已有授权和新语义变更。
3. 自动回件消费的确切开关及单消费者/停止开关/失败信号留存验证。
4. 可审阅的具体ff对象；生产部署和对外发送仅在具体对象与动作明确后提请，不预签未知未来动作。

原批准文件、旧工作树、原任务/attempt与运行证据全部保留；本表不关闭#648、不打开业务开工闸。