# SDD ledger — plan: openspec/changes/codex-mechanism-migration/tasks.md

记录时间：2026-09-24T16:13:19.7619625+08:00（本地 +08:00）。队列 #648。分支 codex/mechanism-migration-648。

Task 1: in progress — provider 15 tests RED→GREEN（provider-red.txt/provider-green.txt）；原生只读探针真实Get-Date、tool exit0、turn.completed，thread 01a0d273-3cfb-7e63-9123-1c65ec56f710。hook关联、会话恢复和上下文仍未验收，不能标complete。
Task 2: in progress — 原测试5 failed/1 passed，隔离错误作废；修复夹具后正在重跑。
Task 3–6: pending。

Ruling: source-spec 中 Claude 回退被用户最新封存指令覆盖；恢复方式只允许停止自动消费并保留信号。
Ruling: 现有 Spec 足以授权接续；按用户不重复确认要求补实施清单后直接执行，不重新发起设计批准。
Ruling: Windows inline流程使用本台账记录，未运行bash专属sdd辅助脚本；不降低测试、独立review和验收闸。
Pre-flight: provider argv/result被三消费者共用；原exit=0与delivery验收分开。轮询全局锁保留，测试副本Local。native thread与业务ID分开。聚合usage不得填当前上下文。

## 测试隔离事故（不得删改为成功）

本会话原始poll-red和poll-red2夹具仅传新增ProviderScript参数；旧PS脚本未声明该参数且将其忽略，回落Get-Command claude，实际启动了封存的CLI。日志为组织禁用访问；未获得成功模型消费。当前进程查询无claude.exe。违反用户明确要求，已当场告知。
补救：测试源码在复制旧guard时硬替换旧CLI查找为不存在哨兵命令；后续实现删除全部旧CLI启动分支。原测试结果作废，poll-red-safe重新建立RED证据。生产任务/入口未切换、业务未开工。

## 未闭合与证据边界

原生CLI与上层exec沙箱初始化表现不同：上层exec默认helper_unknown_error，提权只用于明确批准的外层命令；子Codex仍read-only/never，无危险绕过。现时调度8项启用。服务旧模型路径尚未阻断，需受控切换，不得宣称Claude执行路径已清除。

## Incremental evidence 2026-09-24T16:48:28.322795+08:00

Provider 27 assertions/tests implemented (15 process/protocol, 5 telemetry, 4 thresholds, 3 routes); combined regression running. Native Get-Date remains output_needs_review, no correlated hook acceptance.
Poll six adapter fixtures and two scheduler wrapper tests passed; old full regression had 28 pass, 2 fail, 2 skip; both sticky defects repaired, targeted 3 pass; full repeat running.
Batch isolated fake chain: default paused, isolated write, nonzero+DONE rejected, missing sentinel resumes once passed. Native batch delivery not accepted. Old entry paused; generator route compatibility passed, broader regression pending.
Patrol fake process suite 28 passed across new adapter and old state machine selected classes; no production switch or native chain acceptance.
Portable hook synthetic subdirectory invocation passed and found shared runtime; this is not /hooks trust nor native dispatch. User normal project + /hooks trust remains pending.
Model policy routine/design explicitly inherit user configuration; no cost/equivalence claim. Native actual model observed gpt-6-astra.
CommitSweep VBS isolated exit7 fixture passed. No live task modified.
New finding: standard opener still emits source-only title API; native generator/lint contract must close before batch end-to-end acceptance.
Evidence files: reports/mechanism-migration-648 (local, ignored); branch review in progress.

## Latest checkpoint

2026-09-24T17:25:47.122389+08:00

Provider final32 passed (provider-final.txt); native opener + generator/lint287 passed/40 subtests; poll+prior provider57 passed/2 skipped; batch initial9 passed; patrol watcher14 passed. These are scoped suites, not a summed acceptance total.
Native review native-review-1 completed with7 successful tool calls, thread01a0d2a8-51d4-7a13-82d4-b54ee1c8f0c7. Found P1 owned-child leak on audit error and P2 zero-grace/detach quoting/no-progress looping. All reproduced, repaired and targeted tests passed (review-red/green and patrol-no-progress-red/green). First collaboration reviewer read no files and is not counted.
Native resume kept the same thread and returned exact REVIEW_RECEIPT_648. Latest request context76763, cumulative input432771; no hook acceptance claimed.
OpenSpec strict structure valid using actual user npm CLI. Git fsck --no-dangling exit0, empty output. Neither substitutes for function acceptance.
Five Codex automation views queried and local metadata confirms all PAUSED. Three legacy tasks disabled via normal UAC after direct ACL denial: ZhuopinPollGuard, Claude-Env-HealthCheck, Claude-Plugin-QuotePatch; all enabled=false. Original XML+SHA256+results in runtime scheduler-export/pause-648-admin-*.
Aibot service untouched: legacy event-driven launch path remains pending controlled cutover. Business development remains gated.
Research CN47 offline tests pass; EN selected offline dates/normalize/dedupe/render suite passes. Online data sources and skill invocation not yet accepted. Full34/9 status in asset-disposition.md.
New assets scanned for credential patterns without printing content; no matches. Automatic approval review rejected copying26 historical memory originals into this worktree: pattern checks insufficient to establish absence of sensitive content. No copy occurred. Safer disposition: preserve originals in main checkout and use retrieval references; do not bypass rejection or claim new-worktree history copied.
User explicitly deferred normal project + /hooks trust. Correlated native hook positive/negative and three consumer end-to-end acceptance remain pending.
Old batch tests rely on legacy CLI and some mutate real-repo worktrees; not executed. Retained behaviors are being ported to isolated temporary Git fixtures. Do not skip old coverage or count nine new tests as all behavior acceptance. New retained-behavior suite is running.

## Additional completed independent implementation

2026-09-24T17:45:17.679248+08:00

Retained batch behaviors11 passed (retained-batch.txt); validation/concurrency7 passed (batch-validation.txt); legal generator→lint→fake provider, unique source/thread IDs and PS5.1 entry3 passed (native-batch-integration.txt). Canonical tests migrated into 0-学习与工具/test_工具-opener批处理执行v2.py; duplicate new entry removed; correspondence and remaining coverage explicitly recorded in batch-test-migration.md. Guard mutation/stagger plus affected core7 passed (batch-canonical-guards.txt). No real repo worktree remove/prune/branch deletion in current test fixture.
Handoff runner now reuses provider instead of separate subprocess.run: native status, thread, context, cleanup and acceptance remain separate;20 tests passed (handoff-provider-green.txt), including incomplete/tool-failed with process0 fail-stop.
Downstream probe previously missed OUTPUT-NEEDS-REVIEW and named failures; native opener claims previously recorded CC. Five failing cases reproduced and fixed;136 passed/25 subtests in downstream-green.txt (generator regression plus focused probe/native tests). These interface fixes occurred after initial independent review and must be included in final review scope.
Original 26 history memory files NOT copied, per automatic review rejection. Only retrieval pointer added.
Still no native hook acceptance, three production end-to-end acceptance, ff or Aibot deployment. No business work started.

## Final review repairs and release preparation — 2026-09-24T18:17:26.952685+08:00

Native final review completed: thread01a0d2da-8023-7330-94e5-809135df4f8c,9 tool calls,0 failed; latest context91976, cumulative input560369. Two P2 findings (native lint whitespace recursion; implementation commit blocked by source HEAD review guard), no P1 reported. Both reproduced: final-review-red.txt had5 failed/1 passed. Repairs: same horizontal-whitespace regex detects and normalizes native env; newline is invalid, cannot recurse. Handoff records successful implementation HEAD while preserving source HEAD; review compares that head, unrelated drift still rejected. final-review-green.txt:182 passed,15 subtests. Additional head-capture-failure.txt:1 passed; failure to capture HEAD fails closed, does not mark review-ready. No process result becomes delivery acceptance.

Public MIT Superpowers-LICENSE copied separately; historical memory originals remain uncopied. Release preparation is documented in release-readiness.md; no activation, ff, push or deployment performed. User deferred hook trust; dependent native end-to-end tests remain unrun. All reported passing tests are scoped; counts from overlapping suites must not be summed.
