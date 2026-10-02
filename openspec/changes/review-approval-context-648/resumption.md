# OP-0926-A 接力核验与待审设计

记录时间：2026-09-26T19:37:57+08:00（本机 Get-Date）。队列 §一 #648；当前分支 `codex/op0926a-intent-deploy-closure`。

## 已完成的恢复

开工基线 `02d8227632d5f1bea4f7bc495cb485ac1c064745`、指定分支和干净工作区已核对。`invoke.ps1 -Mode Probe` 八项检查 exit 0。首次普通 sandbox 写运行时探针受权限限制，按正常审批升级运行成功；未改变 sandbox 或 hook trust。

将旧分支 `codex/intent-deploy-648` 的 25 个已提交变更通过 `git cherry-pick -x 02d82276..24987fa3` 接入当前分支，现有实现落点 `7caf7c8885b88662e40c7b0caf1adaf74f391de3`。来源与接力提交的 tree 均为 `2f9cfd6931eae3ed173ec124361a95bfda80c9d5`，`git diff --exit-code 24987fa3 HEAD` 返回 0。没有更改主工作区或旧分支，没有 ff 或 push。历史 241 项控制器回归与三消费者验收仅沿用原记录，本次没有重跑或宣称新的测试通过。

Task 1–5 已有实施台账；最早未完成项为 Task 6 原生整链。`native-checkout-guard-648` 已有 proposal、获批 implement、目标 CI 与独立 review；原 review 为 `changes_required`。逐字核验外部批准文件可见：本任务早已批准 CI 使用规范命令，`--tb=short --junit-xml` 不属于正式验收条件。现有 driver 给 reviewer 的输入缺少该批准上下文。这个判断不改写或自动豁免原 review。

`review-approval-context-648` 的 intent 及两文件候选范围已有用户批准，设计尚未批准。两次原生 proposal 的工具检索失败均保留为 blocked；本次没有将其转换为成功、补写 design_head 或启动实现。

## 当前可审阅产物与人工接续建议（未批准）

从 `native-guard-model-648` worktree 原样复制 `.openspec.yaml`、`proposal.md`、`design.md`、`tasks.md`；四文件 SHA256 逐一匹配。设计 SHA256 为 `c6cd8dd1cb761407574a73086eb76c16a78cb61587c74f9cf5b6de49a15051c3`。

外层实际执行：`C:/Users/Paul Shao/AppData/Roaming/npm/openspec.cmd validate review-approval-context-648 --strict`，exit 0，输出 `Change 'review-approval-context-648' is valid`。普通 sandbox 下 PATH 找不到 openspec 的首次失败保留在本会话工具记录；未重装或升级 CLI。结构有效只表明该草案可以送审，不构成原生 proposal 或设计批准。

建议 Shao Peishen 审阅并明确批准本设计及本次人工接续方式：在当前接力分支按现有 inline/TDD 流程执行设计，原生失败尝试仍为失败；不另建“容忍 proposal 工具失败”的新机制。此项人工批准须另行保存原文、当前设计哈希和提交 HEAD，不由助手自签或重写旧 task state。

实施范围仅为 `0-学习与工具/codex-handoff/workflow_driver.py` 与 `0-学习与工具/codex-handoff/tests/test_workflow_driver.py`。设计要求封存并重核 task/design/allowed_paths 与批准文件哈希，将最小批准上下文传给独立 reviewer；漂移阻断，其他 findings 不豁免。若实际证明两文件范围不足，则呈现具体差异后再修订，不暗中扩大范围。

代价：设计采用 fail-closed，缺少新批准引用的旧任务不能自动复用，需要明确重新审查。批准后仍需 TDD、受影响子项目 CI、独立 review 与原生整链；本次不请求 ff、生产部署、对外发送或启用任何消费者/自动化。

设计人工闸来源为根 AGENTS.md、`.claude/rules/场景建造与合规.md` 及已批准 `intent-deploy-design.md` 的 design_pause。现有 intent 授权不等同于这个具体设计版本已获批准。

## 证据与未闭合

本机详细核验：`reports/mechanism-migration-648/op0926a/resume-verification.json`。设计文件哈希、批准 task/head/design 绑定、CI report、review report、CI stdout/stderr 八项均匹配。

原生记录仍位于 `C:/Dev/Codex/runtimes/zhuopin-ai/state/native-final-648/`。原 review SHA256 为 `e4b94b28516c52a915da66ee0c22164d11f96da3889b283752c871f3a81953e7`；原 CI report SHA256 为 `e310a4e540e1792f2b300f6c4a41726d0b55ed46e1db9594dc70b84b40fcabfa`。本次只读核验，没有复制私有批准原文入库或修改历史运行记录。

#648 保持 open，业务开发闸关闭，Task 6 未完成。五项自动化及既有消费者未启用。主仓队列本次仅通过专用工具查询，按当前派工“不写主工作区”约束未回写；本接力记录作为分支待归并证据，不冒充主仓落库。

暂不归档：设计待批准，实施及完整端到端验收未完成。
