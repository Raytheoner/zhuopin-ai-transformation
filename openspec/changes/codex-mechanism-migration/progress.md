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

## 用户收窄范围 — 2026-09-24T18:19:57.794936+08:00

本线仅覆盖 zhuopinAI 项目的必要技能、配置和机制。中英文 last30days 属于行业研报项目，与本线无关，保留现状，不再检查、补测或配置；其他无关项目资产同样留待所属项目处理，不计入本次验收门槛。排除不代表已验收，也不删除或禁用原资产。 已同步 intent/design/tasks、资产台账、验收矩阵和发布准备件；既有历史证据不追改。此次仅文档范围修正，未运行无关测试、未修改技能或配置。三消费者、原生hook和项目现场切换的必要验收保持不变。

## Continued acceptance preparation — 2026-09-24T23:27:51.532215+08:00

User explicitly requested continuing all four open areas. Normal project/hooks trust question sent; user replied “正在处理”. No completion confirmation and no matching recent native hook audit at time of check; dependent model runs not started.

Prepared .test-temp/native-acceptance-648: native apply_patch positive and no-lock negative (fake queue only); poll fixture changes only Global to Local test mutex, uses fake probe/charter but real provider; patrol fixture substitutes policy/path resolvers only, keeps real Popen/provider/watcher and checks duplicate PID. Inputs/hashes in native-acceptance-inputs.json; launchers are preparations, not acceptance.

Created actual batch worktree .claude/worktrees/mechanism-native-648 on codex/op0924z-mechanism-native-648 at7c9a3a0f. Initial checkout failed Windows path length and auto-cleaned its partial directory; preserved branch, retried with per-command core.longpaths=true, succeeded. No global setting or old worktree changed. Native opener generated and lint passed. DryRun parses exactly one A1 lane, no real queue row ref; evidence native-batch-dryrun.txt. Real model not launched.

Main advanced toa707dca2 through only the two governance files since8c66. main-asset-overlap.json lists108 installed/candidate overlaps,7 differing; no overwrite orff. Aibot actual task working directory is persistent service worktree; start script uses main queue anchor and code imports persistent checkout. aibot-cutover-preparation.json records old/new module hashes and separate main runtime dependency; no restart or deployment authorized/executed.

writing-skills baseline pressure review found kickoff precedence unclear, default guardian unsupported, and no explicit native activation gate. Updated only three native project entries (kickoff/lane-watch/handoff), preserving source business rules, giving explicit Codex-generator precedence and fail-closed mode/trust rules, fixing historical-memory lookup to references/README.md. Independent GREEN pressure review resolves those three instruction ambiguities; it does NOT validate guardian or live execution. Default guardian remains a real unsupported project capability and cannot be replaced by headless without explicit mode choice.

Official hooks reference rechecked: https://learn.chatgpt.com/docs/hooks (project layer and exact-hook trust required); no documented blanket worktree trust guarantee assumed. No bypass used. No unrelated project skills/configurations changed.


## 2026-09-25T07:23:37.251788+08:00 原生接缝实测增量

正常信任已确认，早先因旧audit缺少session/cwd误判未运行，已向用户更正。真实apply_patch envelope为tool_input.command；解析修复RED两项→GREEN25项。v2负例发现editlock退出2但目标仍被写，保留失败证据，不能验收。改为PreToolUse显式JSON deny，正常拒绝和异常分支RED两项→全模块GREEN27项。主仓活动bridge两次备份后精确同步，未改hooks.json或trust。v3正例和负例、轮询随机凭据读取、事件拆件真实回执/假信号消费/重复派发去重/watchers结束联合核验均PASS，详见native-acceptance-verification.json。批处理运行中；现场和发布闸未通过。

## 2026-09-25T07:39:57+08:00 增量复审与启动失败保护

独立 reviewer review_mechanism_seams 发现畸形事件输入与非Pre错误反馈两项P2，均已复现并修复。bridge七种畸形输入保守deny；invoke在Hook模式固定UTF8解码与管道、仅Pre/未知失败deny，已知非Pre保留stderr/exit2，普通模式不被伪装为成功。test_handoff最终34项；与launcher前6项合跑40通过，新增UTF8透传后launcher7项通过。证据native-hook-final-green.txt、native-hook-launcher-utf8-final.txt。独立静态复审无新的确定性缺陷，建议的中文透传边界已实测通过。主仓活动bridge/invoke按既有迁移授权逐文件检查旧hash、备份、同步；hooks.json和trust未改，备份manifest见active-hook-final-install.json。

批处理首轮真实创建三个隔离产物并pytest2通过，但Get-Item检查尚不存在文件返回1，provider tool_failed、外层FAIL(98)、DeliveryAccepted=false；失败保留，不能以OPENER_DONE验收。独立产物审查无发现。已由生成器重建v4夹具，用Test-Path表达预期缺失，将在新工作树复验。


## 2026-09-25T08:01:37.053690+08:00 三链隔离验收收口与发布准备

v4批处理机器核验通过，独立产物内容审查无发现（审查通道限制及替代方式完整记录于native-batch-v4-independent-review.md）。三条消费者的隔离原生链已闭合；现场服务/调度、获准ff、主线portable配置正常信任仍未闭合。候选同步主线两份治理文档至75c65c82，未改已测实现。portable配置最外层退出码缺陷真实pwsh复现修复，启动器8通过。主仓108同名未跟踪资产、8差异已有逐文件hash清单，非本轮旧资产原位保留。#648已更新并登记B-0925_Codex原生机制验收075041，锁已释放；状态继续open。

## 2026-09-25T08:25:39.213884+08:00 已获授权的现场执行

主线a707dca2已ff至ce8443b6；108个重名未跟踪原件逐hash核对后保存在reports/mechanism-migration-648/authorized-ff-backup-20260925T081037，其他脏文件保留。后续既有sweep追加治理提交42be8dd3；6个核心blob不变，发布后新工作树mechanism-release-648已实际继承，未复制runtime。证据authorized-ff-result.json、release-worktree-inheritance.json。

Aibot实际服务工作树仅替换patrol_dispatch.py，新hash1c76a6f9；旧模块已备份。仅停止核实的子进程30900，原看门狗2692按原60秒退避起新PID31792，服务心跳从00:15:27Z更新至00:20:27Z。新增本机consumers.local.json令patrol.enabled=false；实际服务Python导入现场模块返回paused且原信号hash不变，证据aibot-cutover-start.json、aibot-installed-pause-proof.json。这不是实际入站回件的全链验收，暂不启用消费。

轮询旧模型wrapper已备份并由正式注册器WhatIf输出生成的Codex默认暂停wrapper替换；原任务仍Disabled，原XML/账户/周期保存。管理员真实触发非零夹具脚本已通过PS语法检查，并发起正常UAC；截至本记录无结果文件，不能判通过。新portable hooks配置hash变化，已请求用户正常/hooks审阅信任，没有代写trust。两个用户环境动作未完成前，原生守卫/调度验收和业务总闸继续关闭。


### 2026-09-25 完整外层 shell 回归补漏（#648 未闭合）

用户五事件正常信任已落盘，但发布工作树原生负例 thread `01a0d60f-a3bc-7870-9c9b-78763755abee` 未被拦截，隔离假队列实际变化；本轮 FAIL，真实队列未触及。主项目对照 thread `01a0d613-8cb9-7881-ab79-5a2efc039185` 遇 Windows sandbox helper 初始化失败，没有完成守卫验收。

复现配置缺陷：此前 test_portable_hook_wrapper_preserves_child_exit 拆掉了外层命令，只测试内层；完整命令经 PowerShell 解析时，双引号内 `$r` 提前展开，守卫启动前语法失败。现改用 UTF-16LE EncodedCommand 传递同一脚本，外层显式 `exit $LASTEXITCODE`；编码只用于避免 shell 重解析，不含凭据，不改变信任策略。测试覆盖 pwsh 与 Windows PowerShell 完整命令、非零退出、stdin 和原生 deny JSON；RED 2 failed，修复后 launcher 11 passed。证据 reports/mechanism-migration-648/portable-hook-shell-fix.json 和 portable-hook-shell-regression.txt。修复后五项目事件须重新正常审阅，尚未通过原生验收，消费者停用、业务闸关闭。

可审阅的编码命令原文（五事件相同）：
```powershell
& { $r = Get-Item -LiteralPath .; while ($r -and -not (Test-Path -LiteralPath (Join-Path $r.FullName '.git'))) { $r = $r.Parent }; if (-not $r) { exit 2 }; & (Join-Path $r.FullName '0-学习与工具/codex-handoff/invoke.ps1') -Mode Hook; exit $LASTEXITCODE }
```

调度独立项已 PASS：ZhuopinPollGuard 08:59:32 实际启动隔离夹具，LastTaskResult=7，回执 model_started=false/business_probe_started=false；已恢复 Disabled 和 canonical paused wrapper，SHA256=9C2B53F1DD5B6D4BB9A5309B630FDDFC5472AC2CB286B0BFF2E039B44456F453。证据 poll-authorized-cutover/scheduled-nonzero-result.json、scheduled-fixture-receipt.json。该通过仅覆盖真实计划任务非零透传，不代表计划任务模型链通过。


### 2026-09-25 09:35+08 新信任后的现场验证

新配置已由用户正常信任。发布验收工作树已快进 e7fe8aea；原生正例 thread 01a0d62d-54e2-7e61-b6c8-645ad0de5540 实际写出预期内容，五类 hook 完整；负例 thread 01a0d62e-d63e-7ed3-83d4-2985020eed8e 原生明确拒绝无锁修改，假队列原文不变，四类 hook 无 Post。同会话 ID、当前 bridge 哈希与守卫码均已机器核验，发布工作树 hook 继承 PASS。主仓负例 01a0d62a-0f38-7062-a1f5-1a23fc55a884 也明确拦截。

现场服务实际 Python314 + 已安装 patrol_dispatch.py（SHA 1c76a6f9）隔离消费验证 PASS：thread 01a0d62f-a2c7-7490-93d3-351ee03a4b9c，3工具0失败、9条同会话hook、回执 PATROL_NATIVE_648、假信号清空、重复触发 skipped_busy 同PID41332、watcher结束。只替换路径/策略解析器；未向实际监听服务注入业务事件，真实信号未参与验收。详见 reports/mechanism-migration-648/release-fixed-verification.json。

仍未闭合：主仓正例 01a0d62b-249c-7352-b014-c452ec098c60 被守卫允许后写入失败。sandbox日志复现主仓 write ACE / .git deny ACE 更新 error5；ACL root Owner Administrators，当前用户有Modify而非FullControl；隔离工作树有CodexSandboxUsers ACE。休眠前已有同类错误，不能归因于休眠。未绕过sandbox、未改ACL，诊断见 main-sandbox-acl-diagnosis.json。需正常提权完成环境修复再实测主仓。

真实调度模型隔离验收脚本已准备：poll-authorized-cutover/invoke-scheduled-model-admin.ps1；仅隔离探针及随机凭据，临时无触发器，结束恢复Disabled和paused wrapper。本次 Start-Process RunAs 返回“操作已被用户取消”，脚本未启动、无模型回执；已询问是否重新弹UAC，未获答复前不重弹。此前真实调度非零7已通过，不重复。业务闸仍关闭，patrol.enabled=false，五个Codex自动化PAUSED。


### 2026-09-25 10:16+08 实际 S4U 调度模型验收未通过

用户要求重新弹出后正常UAC通过。ZhuopinPollGuard 10:08:00以原S4U身份及VBS动作实际运行隔离模型，thread 01a0d651-d7c2-7820-b92e-4c63f0e42814；模型turn完成但工具创建报 connecting runner pipe-in 超时，tool_events=0，随机凭据未读到。因此 FAIL，虽计划任务返回0也不验收。10:09:17恢复Disabled及原Codex paused wrapper。普通登录会话 codex sandbox -P :read-only cmd /c ver 成功，只构成环境对照，不能替代S4U验证。证据 scheduled-model-verification.json 和 poll-authorized-cutover/scheduled-model-result.json。

主目录sandbox修复：首版管理员脚本因当前CLI要求 --permission-profile 提前退出，未启动sandbox；已用无修改命令验证 -P :workspace 正确入口。v2保持官方sandbox约束，但其UAC返回“用户取消”，尚未执行，未擅自重弹。脚本 invoke-sandbox-repair-admin-v2.ps1 已准备，待正常提权后还须普通身份原生正负例验证。未手工放宽ACL或绕过sandbox。

e7fe8aea窄独立审阅无具体缺陷发现；审阅范围仅两文件diff与已有机器验收记录，未重跑模型/测试，不覆盖主仓ACL或S4U运行时；见 portable-hook-independent-review.md。#648仍open，所有业务开工闸仍关闭。
