# 回件与需求构建三个接口实施计划

> 使用 executing-plans 在本主会话串行实现；不派子代理、不自动 commit/push。唯一任务清单见变更包 tasks.md。

**Goal:** 保留原回件、拆件、队列、claim、看护和 workflow 阶段，在准入、实现、结案三个位置接入 OpenSpec 与 Superpowers，并承接会话转交文档。

**Architecture:** 原 `handoff.py` / `workflow_driver.py` / `workflow_release.py` 仍是工作流入口；新辅助函数只做确定性校验或调用原队列/归档工具，不调度模型、不复制状态机。来源文件保留，回件消化、构建完成、发布完成分别记账。

**Tech Stack:** Python stdlib、原 OpenSpec CLI、既有 pytest、共享编辑锁及队列工具。

**Spec:** `openspec/changes/archive/2026-11-14-feedback-workflow-interfaces-1114/design.md`。

## 已批准范围

Shao Peishen 在本会话批准“三个接口落地＋已有回件 fixture 承接现有场景 refinement”；追加要求会话转交的新材料、决策确认和使用反馈共用此机制。批准不含业务代码、真实业务任务认领、恢复后台消费者、真实源、生产、外发或 git 提交。本计划只细化已批准方案，不引入新评测体系。

## 文件职责

- `0-学习与工具/codex-handoff/workflow_requirements.py`：复用现有需求 lint 的阶段适配，准入、构建契约、归档前后只读检查。
- `handoff.py`、`workflow_driver.py`、`workflow_release.py`：原入口调用适配，不改变既有 HEAD、review、claim 合同。旧已封存阶段保留，新 proposal 必须入 INDEX；refinement 保留短 design。
- `0-学习与工具/codex-handoff/feedback_intake.py`：会话文件归档及来源清单，使用原队列工具回灌已有行；不解析执行文档指令、不新建业务执行器。
- `codex-handoff/tests/test_feedback_workflow.py`：已有回件样本与原 workflow fixture 集成；反例涵盖缺 INDEX、冻结、缺 delta/test、重复来源、冒充批准、外部未闭与证据漂移。
- 原 `test_workflow_e2e.py`、`test_workflow_driver.py`、`test_workflow_state.py` 按新增契约补 fixture 输入，原断言保留。
- `docs/requirements/INDEX.md`、本变更包、主规格 `serial-test-first-construction`、`docs/codex/rules/跟进信与专员.md`、原拆件章程：说明两入口共用后续链。

## 验证与边界

每片先写失败测试再实现。最终在 `0-学习与工具/codex-handoff` 独立跑完整 pytest；需求 lint 单测在工具目录独立跑指定文件；三个 lint 和 OpenSpec strict 单独执行。fixture 可在临时 Git 仓库生成原测试需要的提交，不操作主仓提交；fixture 模型替身只证明确定性接口，不能冒充真实模型、生产或专员验收。

归档变更若改变候选 HEAD，保留旧 CI/review 原证据，不复用其冒充新 HEAD 通过。外部卡点保留原队列；只有本地范围与归档条件实际满足才销对应项。

SC7 11.12 原件只读用于接口需求核对：包含 UI 反馈、计算规则、有限样例确认和真实全量发布诉求，不能整体视为实施批准。本轮不消化 SC7 业务任务、不更新其业务规格、不解除相关跟进信闸。

## Review Focus

1. 同一文件重复转交、改名转交及失败后重试不重复开业务任务；已存在原件不得覆盖。
2. 文档内“全部修复/立即发布”与“已核对”不得转成主会话批准、L2 签认或全量验收。
3. INDEX 或 delta/test 缺失、冻结/外部阻塞不得启动 provider。
4. 归档前 tasks 未完、合法观察窗口及外部未闭须保留；归档失败不销号。
5. 旧完整 pytest、独审与 HEAD 绑定不被新摘要或模型自述替代。

## 执行顺序

按 `tasks.md` 四片执行：准入→实现→回灌/结案→完整回归与持锁落库。每片记录 RED/GREEN 命令及实际退出码，最终记录到 `docs/codex/feedback-workflow-acceptance-20261114.md`。
