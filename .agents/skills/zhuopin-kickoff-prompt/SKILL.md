---
name: zhuopin-kickoff-prompt
description: "zhuopinAI 项目 zhuopin-kickoff-prompt 工作流；用户请求相关任务时使用。"
---

先读根 AGENTS.md，再读仓库正本 0-学习与工具/skills源码/zhuopin-kickoff-prompt/SKILL.md，遵守其中业务判据、授权及取证要求。

Codex 映射：文件与命令使用当前可用工具；Task/Agent 仅在本技能实际需要且当前权限允许时映射到 collaboration；不存在的 Claude/Cowork API 不执行。定时任务由 Codex automation 工具管理，不能将保存脚本当作已调度。对外发送仍需用户明确指示。状态/队列按原专用工具读取和持锁登记。

涉及 .51 收口时仅引用 zhuopin-lan-closeout 正本，不复制程序。源码中的 Claude transcript、save_skill、set_session_title 不是 Codex 接口。若相关步骤无可用等价接口，记录缺口并继续独立可执行步骤。

## Codex 开工词执行映射

源正文的任务分类、必填字段、队列查询/锁与人工闸继续生效；其中 CC/Cowork 骨架、旧标题 API 和执行环境限定，按已批准 `openspec/changes/codex-mechanism-migration/design.md` 的原生执行契约替换，不机械复制为 Codex 指令。

1. 只生成时，使用仓库 `0-学习与工具/工具-opener生成.py --env Codex --variant standard --out <批准工作树内相对.md>`（子任务用 `subtask_lane`），完整提供必填字段，混合文档另传唯一完整标题 `--anchor`。返回/输出必须是同一次调用实际落盘回读的块；聊天只逐字引用，不得手打、削短或改写。输入指针仍为仓库根相对路径，取号/声明仍走生成器；使用隔离 Python，路径加引号。
2. 原生生成器与 `工具-opener块lint.py` 是 Codex 文本的执行格式判据；不得为满足旧正文的逐行骨架约束，补回 `mcp__ccd_session_mgmt__set_session_title`。源文业务判据不由此放宽。
3. 顶层桌面任务仅在真实工具可用时设置标题；headless 由 provider 记录 source_id/thread_id；子任务不改父任务标题。
4. 生成与 lint 通过不授权执行；普通任务仍在主会话串行。没有针对 guardian/headless 的新明确授权，不交付该执行流程，也不用 standard/subtask_lane 冒充；生成器具有变体能力不代表后台消费者已启用。
5. 模型路由用当前 policy 支持值；不把源端模型名传给 Codex。业务开工仍受本轮机制验收总闸约束。

## #503 出件段覆盖（仓内候选）

本节替换旧源码步骤9的聊天另写正文及步骤10的临时.md自检：只能消费生成器同次实际落盘回读结果；需改内容则改参数重跑，不能手填指纹。共享派单/接力须已有本人有效锁和精确§二预登记，并用 --who/--registration-batch 绑定。射程边界只见 工具-opener块lint.py 文件头。仓外已安装版未同步，由 #503 独立列欠账；未经精确批准不安装、不声称现役生效。
