---
name: zhuopin-codex-handoff
description: "zhuopinAI 的 Codex 项目接力、环境检查、任务准备、构建验证和迁移缺口核验。"
---

读 0-学习与工具/codex-handoff/README.md 与根 AGENTS.md。运行 invoke.ps1 -Mode Probe 查现况；任务必须绑定现时队列与批准的 intent/design。用 handoff.py prepare 建立任务证据，再按原项目授权进入单个阶段。技能/代码存在不代表 hooks 已信任、任务已调度或生产已部署。遇权限缺口保留失败证据，不旁路。

历史记忆按需查 .codex/references/claude-memory/MEMORY.md 及引用项；这是迁移时的历史快照，现时正本优先。此前检查报告不是当前 HEAD 的 CI 结论。
