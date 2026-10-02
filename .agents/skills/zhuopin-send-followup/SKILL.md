---
name: zhuopin-send-followup
description: Use when Shao Peishen asks to prepare, approve, send, verify, or close out a specific follow-up letter.
---

先读根 AGENTS.md，再读仓库正本 0-学习与工具/skills源码/zhuopin-send-followup/SKILL.md，遵守其中业务判据、授权及取证要求。

Codex 映射：文件与命令使用当前可用工具；Task/Agent 仅在本技能实际需要且当前权限允许时映射到 collaboration；不存在的 Claude/Cowork API 不执行。定时任务由 Codex automation 工具管理，不能将保存脚本当作已调度。对外发送仍需用户明确指示。状态/队列按原专用工具读取和持锁登记。

涉及 .51 收口时仅引用 zhuopin-lan-closeout 正本，不复制程序。源码中的 Claude transcript、save_skill、set_session_title 不是 Codex 接口。若相关步骤无可用等价接口，记录缺口并继续独立可执行步骤。

## Codex执行映射与发送闸

发送业务判据以 `0-学习与工具/skills源码/zhuopin-send-followup/SKILL.md` 和 `.claude/rules/跟进信与专员.md` 为正本；起草使用 `zhuopin-followup-letter`。Codex 中通过当前可用的 Windows PowerShell 执行器运行原有工具，路径加引号，不用沙箱 Bash 发送。

查信件时只用 `工具-跟进信README查询.py --digest --json` 或 `工具-跟进闸查询.py --to <收信人>`；不得读取或 grep 跟进信 README 主表全文。起草前先查收信人串行闸；发送前同时核对信件编号、收信人、标题及状态列，按源正本完成称谓自检、读回，并等待 Shao Peishen 对读回内容明确回复“发”。只有 `🆕 待发` 可进入发送步骤；源规则要求的批准冷却、已合入 master、`.51` 冒烟和真实案例复现条件仍逐项适用。草稿、已批准状态或 skill 存在本身都不是发送授权。

实际发送和审计核验只走源正本指定的 `push_followup_letter.py`、批准与查询工具；发生中断或结果不明时先用 `--verify-only` 核对四条审计链路，不凭猜测重发。不要把当前 Codex 工具可用性解释为已发送，也不要代替用户补授权或确认。

需要子代理、子会话、自动化或 Workflow/Guardian 派生模型任务时，模型一律显式指定 `gpt-6-luna`；无法指定时停止该派生任务，报告路由限制并等待路由修复，禁止静默继承其他模型。
