# Why
Claude 执行端已由用户封存；三个在用模型消费者、原生工作树守卫和调度仍不能形成可验收的 Codex 接力链。现有安装与单次工具成功不能证明迁移完成。

本包已有一项真实调用接缝缺陷：Guardian `start` 未注入 executor 时默认走 `handoff.execute`，在 Windows 上将裸 `openspec` 交给子进程并触发 WinError 2；同目录、同参数经既有 `workflow_driver.default_executor` 解析到 `openspec.cmd` 后，strict validation 退出 0。该证据来自 `reports/workflow-mvp-native-1002/inputs/guardian-executor-proof-1002.json`。需修复默认接线，使普通 Guardian CLI 复用既有 executor。

# What Changes
统一有边界的 Codex provider；替换轮询、opener 批处理、回件拆件的模型接缝；保留暂停、去重、失败恢复和审计。补模型路由、原生会话绑定、上下文停机、新工作树资产继承、技能插件处置与调度验收。源端只作历史资料。

在既有迁移包内将 `guardian_entry.start` 的默认 executor 指向 `workflow_driver.default_executor`。显式注入 executor 的行为保持不变。实施严格限于 `0-学习与工具/codex-handoff/guardian_entry.py` 与 `0-学习与工具/codex-handoff/tests/test_guardian_entry.py`，不新增解析器或执行层，不改路由、gate、provider、state 或信任机制。先以回归测试证明默认路径失败，再实现最小修复并运行受影响 handoff 的完整 CI。

# Capabilities
## New Capabilities
- `codex-mechanism-consumers`: 三条消费者共用安全模型接缝及证据合同。
## Modified Capabilities
无新增规格变更；本次仅修正既有工具的 Windows 默认 executor 接线，沿用包内现有规格并保持其 strict 校验有效。原业务规则与人工授权边界保持。

# Impact
机制工具、aibot 事件拆件、Codex 项目资产、Windows 既有任务包装。无业务功能开发；无自动 ff、生产部署或真实外发授权。现有 dirty files 与旧 worktrees 保留。
