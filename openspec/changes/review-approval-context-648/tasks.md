# 【Codex】Review Approval Context Implementation Plan

**Goal:** 向独立只读 reviewer 传递经过 task/design/path/外部文件哈希绑定的最小批准摘要，无效或漂移即停止。

**Architecture:** driver 封存实施批准引用，review 边界重新验证并投影字段，结果接纳及复用时复验；保持现有 CI 和 findings 门禁。

**Tech Stack:** Python 标准库、pytest、disposable Git worktree、现有 Codex workflow driver。

**Spec:** 同目录 `design.md` 与 `proposal.md`。本计划承接用户明确的已批准三文件任务，不代表任何勾选项已执行。外层核验当前设计版本与既有批准绑定后，沿既有逐阶段执行器推进；本阶段仅写三份文档，不派实施或 review 子任务。实施阶段按 executing-plans 逐项执行，独立 review 另开只读 thread。

## Global Constraints

- 源 §一 #648，task_id `review-approval-context-648`，action_key `worktree_local_build`。
- 实现仅修改 `0-学习与工具/codex-handoff/workflow_driver.py`；测试仅修改 `0-学习与工具/codex-handoff/tests/test_workflow_driver.py` 和 `0-学习与工具/codex-handoff/tests/test_workflow_release.py`。
- 前一阶段证据不满足立即停止。保留他人修改；模型不 commit，提交由获准的外层驱动处理。
- 不绕过 sandbox、hook trust、编辑锁、队列工具或测试；不 ff、不连 .51、不外发、不代签。
- 以下复选框是 OpenSpec 机读任务格式；用户待办仍以纯编号交付。

## Review Focus

1. 外部文件与 task/design/paths 绑定错位、哈希漂移，包括合法 JSON 内容相同但字节改变。
2. Windows 盘符、路径跳转、symlink/junction 或同仓另一 worktree 内伪装外部批准。
3. review 执行期间漂移、旧 approved 结果复用和 optional probe adjudication 绕过验证。
4. 批准文本越权、未知 JSON 字段泄漏、CI 勘误与无关缺陷同时出现。
5. 有效摘要并不替代新 thread、HEAD、真实 CI 原文与 findings gate。

## 1. 外层 strict 与设计审批（前置）

- [ ] 1.1 外层对 `review-approval-context-648` 执行 `openspec validate review-approval-context-648 --strict`，记录实际命令、退出码和报告；本模型不运行 CLI。
- [ ] 1.2 外层核对本包 design_head/design_sha256 与既有三文件 allowed_paths 的仓库外批准证据；有效已有授权直接沿用，缺失或版本不符则停在 design_pause，不自行补签、不进入下组。
- [ ] 1.3 外层通过队列专用工具核现时 #648，检查同仓独立 linked worktree、干净设计 HEAD、触碰范围、正常 hooks trust 和适用锁状态。保护其他工作树和他人修改，不清理、不搬运；本阶段不自行调用 Probe 或读取私有状态。

## 2. 批准封存和摘要校验的 TDD

- [ ] 2.1 在 driver 测试文件扩展隔离 fixture：设计文件及 HEAD、明确 allowlist、tmp_path 仓库外批准 JSON，封存原始 bytes 的 SHA256；不使用本机私有状态。新增 `test_review_approval_context_valid_binding` 与参数化 `test_review_approval_context_rejects_invalid_binding`。
- [ ] 2.2 从 codex-handoff cwd，以 invoke.ps1 所解析的隔离 Python 执行 `-m pytest "tests/test_workflow_driver.py::test_review_approval_context_valid_binding" "tests/test_workflow_driver.py::test_review_approval_context_rejects_invalid_binding" -q -p no:cacheprovider`，保留预期红灯，确认失败来自待实现行为。
- [ ] 2.3 在 driver 增加 design.md 定义的校验/投影 helper，并在 `_implement` 模型启动前封存引用和绑定。解析及 hash 使用同一 bytes；已有封存值不被替换。仅原文 text 与白名单字段可进摘要。
- [ ] 2.4 参数化断言覆盖：无引用、文件丢失/不可读、相对/目录/仓库内路径、另一个同仓 worktree、链接回仓库、非法 JSON/非对象、空或非字符串 text、错误 task_id/design_head/design_sha256、设计字节改变、批准字节改变、空/错类型/重复/绝对/盘符/glob/遍历/越界 allowed_paths、列表漂移、实现改动越界。每例均无 reviewer 调用、无有效摘要，失败理由不泄漏原文。链接测试按平台能力明确 skip，不能伪称已覆盖。
- [ ] 2.5 重跑上述精确 node-id 至绿，核对实施原有越界路径拦截仍成立。

## 3. 独立 review 输入及接纳的 TDD

- [ ] 3.1 新增 `test_review_receives_verified_approval_context`：fake model 捕获 prompt；批准文本使用脱敏 CI 勘误样例；额外 JSON 字段放入哨兵字符串。断言摘要精确字段、无外部绝对路径/未知字段，prompt 与 review-input 的摘要一致，sandbox 为 read-only。
- [ ] 3.2 新增 `test_review_approval_drift_during_model_blocks_acceptance` 和 `test_approved_ci_context_preserves_unrelated_findings`；分别让 fake model 返回前改写批准文件、以及返回 changes_required 加无关 finding。按这三个精确 node-id 跑红并保留退出码。
- [ ] 3.3 修改 `_review` 与 `_run_model`：启动前验证、构造单一摘要对象、补充范围限定指令、返回后重核；成功时由 driver 把引用与摘要加入现有 review.json。失败不写成功 review_evidence。
- [ ] 3.4 将批准原文泛化/越权文本、摘要缺失、同 implementation thread、HEAD 漂移、无工具事件、错误 report HEAD 等纳入测试。不得自动删除 `CI_TARGET_SCOPE` 或其他 findings，不得把 changes_required 改成 approved。
- [ ] 3.5 重跑本组 node-id 至绿；正例验证真实 passed CI fixture 与新 reviewer thread 满足既有门禁，负例确认仍 blocked。

## 4. 审查结果复用与旧状态的 TDD

- [ ] 4.1 新增参数化 `test_cached_review_requires_unchanged_approval_context`，覆盖 driver 的 advance、adjudicate_review_probe、release_ready 三入口。旧报告无摘要、引用变化、绑定漂移、摘要/报告不一致均不得接纳；批准有效且报告一致的正例保持原行为。
- [ ] 4.2 按该精确 node-id 跑红，随后只在 driver 包装层补齐验证。旧状态缺证据返回可理解 blocked 原因，不自动从新传参数、intent 或 final.txt 回填批准。
- [ ] 4.3 重跑至绿，并更新 driver 测试文件中需要有效授权的旧 fixture；不放宽旧断言。验证 failed CI retry/refresh 的既有审计记录不被本变更覆盖。
- [ ] 4.4 在 `tests/test_workflow_release.py` 保留 `test_driver_exposes_reviewed_release_without_merging`，按 design 第5项补齐临时真实批准绑定 fixture；新增参数化 `test_driver_release_ready_rejects_invalid_approval_context`，覆盖缺批准、字节漂移、task/design 错绑和 review 摘要错配，失败时不得调用 fake `prepare_release`。
- [ ] 4.5 从 codex-handoff cwd 以隔离 Python 执行 `-m pytest "tests/test_workflow_release.py::test_driver_exposes_reviewed_release_without_merging" "tests/test_workflow_release.py::test_driver_release_ready_rejects_invalid_approval_context" -q -p no:cacheprovider`，记录 RED→GREEN。保留正例 `paused` 与原精确调用参数断言；不删除/skip/xfail、不 mock 新校验、不改 `workflow_release.py`。fixture 或实现未完成导致的失败不得忽略。

## 5. CI、独立 review 与发布准备（批准实施后）

- [ ] 5.1 外层核改动仅在三文件并确认实现 HEAD；按 `.github/workflows/ci.yml` 及 `工具-CI矩阵发现.py` 动态矩阵定位受影响子项目。在 `0-学习与工具/codex-handoff` cwd，以隔离 Python 执行 `-m pytest -q -p no:cacheprovider`，同时核验该规范命令与 CI 原文差异的已有逐项批准；保存完整 argv/cwd/退出码/stdout/stderr 路径及 SHA256，包含 release 测试收集/执行结果。批准或前阶段证据不足立即停止；失败不进入 review，不在根目录混跑。
- [ ] 5.2 外层以新 Codex thread 执行独立只读 review，绑定 implementation HEAD 与真实 CI 引用，确认本次批准摘要有效、无关缺陷仍可阻断。保留原始报告，不能仅凭模型自陈通过。若需修复，依批准范围回到 TDD/CI 后重新审查。
- [ ] 5.3 通过后执行既有 release-prep，记录 patch-id/HEAD/证据和未闭合项；只准备发布，不 ff、不转生产、不外发。部署如后续另获授权，入口仅引用 zhuopin-lan-closeout 正本。
- [ ] 5.4 按外层既有队列/锁协议回交证据并停止。当前设计阶段暂不归档；不得把上述尚未执行项标完成。

## 本阶段交付与证据边界

本阶段只修改本目录 proposal.md、design.md、tasks.md，保留现有 `.openspec.yaml` 的 `schema: spec-driven` / `skip_specs: true`，纯工具变更不新增规格文件。历史 resumption.md 不追改。只做文档差异、路径范围与必要章节检查；OpenSpec strict 由外层驱动执行，当前模型不运行 CLI、不 commit、不实施、不测试代码、不执行 review/release。后续各阶段以实际命令、退出码、HEAD、证据路径及哈希逐项登记；无实际回执的任务保持未勾选。
