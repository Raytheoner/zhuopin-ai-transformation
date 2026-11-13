# Codex 执行入口

默认当前主会话串行：已批目标/design/tasks → 实现 → 定向验证 → 受影响项目完整 pytest 与功能/audit 验收。根 `AGENTS.md` 负责规则路由，规则正本在 `docs/codex/rules/`，技能正本在 `.agents/skills/`；不读取旧 Claude 配置或旧技能源码作为执行依据。

| 操作 | 现役入口与边界 |
|---|---|
| 规则与技能 | 先读根 AGENTS.md，只展开命中路由；按 skills-index.json 找到原生完整技能。 |
| 状态与证据 | invoke.ps1 / workflow_driver.py 的 status，以及现役队列查询工具；以各入口 --help 和实际回执为准。 |
| 已授权派生 | 仅用户明确要求时使用 gpt-6-luna/high；默认不启动 Guardian、headless 或并发泳道。 |
| Hook 配置 | hook_configuration.py、hook_policy.ps1、guards/ 与 .codex/hooks.json；配置/守卫缺失即失败，不回退旧引擎或旧全局 hook。 |
| 安装与回退 | 受保护文件走既有人工变更流程；保留前后 SHA、原文和回读证据，不修改 trust 或放宽保护策略。 |

已有泳道看护和唯一写方保留；不恢复暂停的业务消费者，不修改旧锁或把失败写成成功。安全审核、用户明确独审与旧冻结合同仍满足。无真实触发器不宣称自动继续。

不自动 commit/push、切分支、ff、部署或外发。ff 仅在具体授权、目标干净且可快进时使用 ff-only。ERP 永远只读，OEM 隔离、L2 不代签及专业签认边界不变。

原 README 及其时点证据完整保存在 docs/codex/retired-evidence/README.md.txt，仅供定向历史核对；其中旧 API、模型及启动说明不再作为执行入口。本文不把静态迁移或单测等同于安装、自动加载、真实模型或自然运行验收。
