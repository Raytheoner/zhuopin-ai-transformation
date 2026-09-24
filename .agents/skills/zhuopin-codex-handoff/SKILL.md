---
name: zhuopin-codex-handoff
description: "zhuopinAI 的 Codex 项目接力、环境检查、任务准备、构建验证和迁移缺口核验。"
---

读 0-学习与工具/codex-handoff/README.md 与根 AGENTS.md。运行 invoke.ps1 -Mode Probe 查现况；任务必须绑定现时队列与批准的 intent/design。用 handoff.py prepare 建立任务证据，再按原项目授权进入单个阶段。技能/代码存在不代表 hooks 已信任、任务已调度或生产已部署。遇权限缺口保留失败证据，不旁路。

历史资料先读 `.codex/references/README.md` 的检索边界；新工作树不携带历史原文，通过 git-common-dir 定位主仓后按需检索，不因本地无副本而推断历史不存在，不复制凭据或绕过审批。现时正本优先，此前检查报告不是当前 HEAD 的 CI 结论。

实施与评审用同一 task id：runner 保留 source_head，并在成功产出后记录 implementation_head；review 对照该实施HEAD，额外漂移仍拒绝。成功只记 stage_output_needs_review/delivery_accepted=false；测试、原生hook、产物复核和逐项发布授权仍须分别闭合。按最新 intent，仅处理 zhuopinAI 必要机制，无关项目技能配置保留现状。
