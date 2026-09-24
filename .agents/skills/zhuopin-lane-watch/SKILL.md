---
name: zhuopin-lane-watch
description: "zhuopinAI 项目 zhuopin-lane-watch 工作流；用户请求相关任务时使用。"
---

先读根 AGENTS.md，再读仓库正本 0-学习与工具/skills源码/zhuopin-lane-watch/SKILL.md，遵守其中业务判据、授权及取证要求。

Codex 映射：文件与命令使用当前可用工具；Task/Agent 仅在本技能实际需要且当前权限允许时映射到 collaboration；不存在的 Claude/Cowork API 不执行。定时任务由 Codex automation 工具管理，不能将保存脚本当作已调度。对外发送仍需用户明确指示。状态/队列按原专用工具读取和持锁登记。

涉及 .51 收口时仅引用 zhuopin-lan-closeout 正本，不复制程序。源码中的 Claude transcript、save_skill、set_session_title 不是 Codex 接口。若相关步骤无可用等价接口，记录缺口并继续独立可执行步骤。

## Codex 模式选择与执行闸

源正文的排波、依赖、暂停状态机、心跳、审计及人工闸继续生效；旧 CLI、旧标题和源端编排接口不能执行。当前原生格式与 provider 接缝依据 `openspec/changes/codex-mechanism-migration/design.md`，不能把改名当作等价编排。

- 用户只说“开启泳道看护”时，仍按源规则视为看护者模式；Codex `guardian` 尚未迁移，停在启动之前并明确缺口。可独立整理看护范围，不擅自切到无头、不宣称已看护，也不为等待手动请求创建自动化。
- 只有用户明确要求无头、且计划和该任务设计已有授权时，才采用 `工具-opener批处理执行v2.ps1`。先用 `--env Codex` 生成并 lint，按源流程 `-DryRun -Yes` 核对实际解析的泳道，再核对正常项目/hooks信任、隔离worktree及授权证据。`-ConsumerEnabled` 是执行开关，不是授权来源；前置未满足不能加开关起活。
- 原生 hook 必须在正常 `/hooks` 流程信任，并用同 thread/cwd 的实际事件确认生效；仅配置文件存在、用户已开 CLI 或生成器通过都不算。不要代写信任或使用旁路参数。
- 真实开启命令保留 `-Plan`、限定的 `-Only`、日志目录与原并发/错峰纪律。source_id 不当作原生 resume ID，续棒从 provider session/result 取得 thread_id，经现有执行器接缝恢复，不运行旧 CLI。
- 读取 summary.json 的状态及证据；OUTPUT-NEEDS-REVIEW、进程0、OPENER_DONE都不标交付成功。失败停止依赖项，恢复到停止模型消费、保留信号；具体ff/部署/对外发送仍逐项授权。

本入口说明支持和停点，不表示 guardian、调度或现场部署已完成验收。
