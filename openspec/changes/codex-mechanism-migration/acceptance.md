# 机制侧验收矩阵（未通过总闸）

检查点：6c2c041bd89d3ef7a8d4ea626609c3126884a897，分支codex/mechanism-migration-648。历史检查点时间：2026-09-24T18:04:50.338984+08:00；最新原生增量：2026-09-25T07:23:37.251788+08:00

**业务开发闸：仍关闭。末轮注册器修复已由本地CommitSweep于2026-09-25 11:20+08:00实际提交为08428d42，更新后-WhatIf定向回归1通过、任务仍Disabled。三条消费者规定范围验收通过；用户追加的intent→deploy全自动阶段接力尚无编排器与端到端验收，不以原#648的消费者通过冒充整套流程通过。真实业务自动消费仍停用，未借验收发送消息。**

| 必要项 | 状态 | 实证 / 剩余动作 |
|---|---|---|
| 统一provider及安全权限、失败/超时/清理、路由 | 单测通过；原生部分通过 | provider-final.txt：32；native-review-1和native-resume-1真实thread/工具/turn/计量；当前 hook 正负例已通过，三消费者产物分项验收 |
| 轮询守静默/sticky/失败/注册器 | 隔离验证通过 | provider-poll-final.txt：57通过2跳过（含当时provider）；原生轮询通过：thread 01a0d5b0-5abe-7d33-9f63-964c834d74e6，真实读取随机凭据，五事件全部关联 |
| opener生成/lint/旧入口/批处理 | 隔离及原生新工作树链通过 | 新套件已回归原入口，保留行为11、验证/并发7、合法生成/身份/PS5.1共3、变异/错峰及相关核心7；不能相加冒充独立总数；v4 thread 01a0d5cc-1edd-74b2-9e19-e2c714263641：6工具0失败、pytest2通过、三个产物哈希、15hook、独立内容review均通过 |
| 收工探针与原生占号审计 | 针对性回归通过 | downstream-green.txt：136通过25子测试，包含生成器回归；新状态不得静默漏报 |
| 事件拆件 | 安装切换及现场模块隔离消费通过 | patrol-final.txt：34；包含无进展退避/三次停链/信号保留；native-patrol：真实模型写回执、消费假信号、同PID重复派发拒绝、watcher结束；现场模块已切换且实际Python验证paused、信号不变；安装模块实际Python隔离消费/去重/watcher已通过（release-fixed-verification.json）；未注入真实业务回件 |
| 接力runner | 单测通过 | handoff-provider-green.txt：20；末轮修复后受影响集合182通过/15子测试，另异常分支1通过；记录实施HEAD供review，额外漂移拒绝 |
| 原生hook与apply_patch负例 | 主仓与发布工作树均通过 | 用户正常 /hooks 已信任主仓项目配置；v3 正例真实写入，负例 editlock拒绝且文件未变、无PostToolUse；关联会话与桥接SHA，native-acceptance-verification.json |
| 可版本化资产继承 | 主线及发布工作树原生继承通过 | fresh-worktree-inheritance.json：6个核心blob一致，34技能，无runtime副本，共享runtime解析成功，工作树干净；后续已完成正常信任和原生正负例；release-fixed-verification.json |
| Windows旧任务 | 三项已暂停 | runtime scheduler-export/pause-648-admin-*：XML、SHA256和enabled=false；轮询守、Claude体检、Claude插件补丁 |
| 单消费者调度/现场切换 | 规定范围实测通过；自动消费停用 | 同任务已获准改InteractiveToken；真实调度读取随机凭据、1工具0失败、5hooks和恢复Disabled已核验（interactive-scheduled-verification.json）；仅账户登录时运行。Aibot安装模块隔离链通过，五项Codex自动化PAUSED |
| zhuopinAI 必要技能/配置 | 本线必要路径通过；范围外未宣称通过 | asset-disposition.md 是历史全量索引；只核验本项目依赖。中英文last30days属行业研报项目，连同其他无关配置移出本线门槛，保留现状 |
| 独立代码审查 | 两轮审查修复通过 | 初审四项、终审两项均复现修复；final-review-green.txt：182通过/15子测试；另HEAD取证失败分支1通过 |
| 发布/ff | 用户已授权；主线ff完成 | 实现与审查证据已在候选分支提交，并同步当时主线a707dca2的两份治理文档；主线已ff到ce8443b6，原件备份和哈希证据见authorized-ff-result.json；其他脏文件保留 |
| 历史覆盖 | 边界明示 | 原26份记忆保留主仓；复制被自动审批拒绝，本分支仅检索指针。Cowork主对话完整覆盖仍是已知证据缺口，不重启Claude |

## 不得隐去的测试事故

早期两次poll RED夹具被旧脚本忽略新参数后实际拉起封存CLI，日志报组织禁用访问；无成功消费。已即时告知并留档，原结果作废。后续夹具硬阻断旧CLI查找，当前实现移除旧调用路径。详见progress.md。此事故不能用后续通过覆盖。

## 历史待办快照（由末节现时结果覆盖）

正常信任、原生apply_patch正负例、轮询和事件拆件隔离原生链已完成。批处理新工作树真实写入→测试→独立内容review→交接也已通过。按tasks.md继续获准主线合入、portable配置正常信任与现场调度切换。再把可审查发布件交逐项ff及现场切换授权。任何一项未闭合，都不得以计划、exit0、OPENER_DONE或本表存在为由启动业务开发。

## 原生接缝增量（2026-09-25T07:23:37.251788+08:00）

当前桥接SHA256：572a7df9f5908da2fc3fb2bd7743f324a396a7a71744f9ef68f60b9675e315d3。解析真实 tool_input.command；PreToolUse失败输出原生permissionDecision=deny。受影响 test_handoff.py 27项通过。v2负例曾出现守卫exit2但文件仍被改，明确作废并保留日志；修复后v3负例保留原文。主仓活动桥接已按迁移授权备份并精确同步，未改hooks配置或trust。证据：active-hook-deny-install.json、native-hook-deny-green.txt、native-acceptance-verification.json及各会话correlated-hook-audit.json。provider的accepted=false保持不变，外层仅按产物和事件联合验收。

## 2026-09-25T08:01:37.053690+08:00 三消费者隔离原生链闭合

轮询和拆件证据沿用native-acceptance-verification.json（桥接572a7d）；新增异常输入/启动器修复后，最新桥接69fe2333+启动器99afd63b的原生负例与batch正向写入链见native-final-verification.json。未将旧运行冒充最新哈希重测。v4从实现c2e8c9d5新建工作树；真实工具、测试、审计、产物均核验，独立审查方式见native-batch-v4-independent-review.md。provider/batch内部accepted=false保持不变，外层验收独立留证。

候选portable hooks最外层新增exit $LASTEXITCODE，真实pwsh非零传播RED→GREEN，launcher8通过；当前主仓固定-File hooks无需此包装。候选配置尚未在主线正常信任和现场验证，合入后不得沿用旧hash冒充新信任。必要现场项仍阻塞总闸。

## 2026-09-25T08:25:39.213884+08:00 现场状态增量

逐项授权已获得。ff完成；CommitSweep调用的VBS已随ff更新，尚需现场任务返回核验。Aibot单进程重启并恢复持续心跳，新模块保持暂停且真实信号未变。轮询已安装Codex包装、仍Disabled。发布后新工作树核心blob继承一致。新portable项目hooks正常信任与UAC任务触发均在等待用户环境动作；没有结果文件不当通过。业务开工闸继续关闭。


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


### 2026-09-25T10:33:53.085413+08:00 主仓 sandbox 普通身份验收闭合

正常UAC执行官方 codex sandbox -P :workspace 初始化后，管理员夹具实际写入并回读。随后确认父进程 ParentIsAdministrator=false，以正常 workspace-write 原生复验：正例thread 01a0d660-9b1e-7983-89dc-e736f7376520 实际写入、1工具0失败、五类hook完整；负例thread 01a0d662-1bd5-7e11-8bca-caa03d5c42f2 明确PreToolUse拒绝、假队列未变、四类hook完整。按当前bridge SHA、cwd、thread和产物机器断言通过。主仓sandbox写入缺陷PASS，证据 reports/mechanism-migration-648/main-sandbox-repair-verification.json；没有放宽sandbox或代写信任。

S4U环境修复后复验thread 01a0d665-d642-7b80-a935-17bd3af105fc仍工具管道连接超时，0工具、随机凭据未读，FAIL；已恢复任务Disabled和paused wrapper。这是与主仓ACL修复独立的调度问题，不能用普通身份PASS替代。正在使用原S4U任务无模型直接sandbox短诊断定位，诊断结束同样恢复Disabled；不启业务，五项Codex自动化仍PAUSED。


### 2026-09-25T10:36:51.649093+08:00 S4U 无模型对照定位与待决配置

原任务在Session 0（S4U）直接执行官方sandbox的cmd /c ver和pwsh只读输出，两者均exit1、15000ms connecting runner pipe-in超时；不涉及模型、MCP、业务脚本。普通登录身份同类sandbox命令成功。证据 poll-authorized-cutover/s4u-direct-result.json、s4u-direct-cmd.txt、s4u-direct-pwsh.txt。诊断已恢复Disabled及原paused wrapper，恢复记录s4u-diagnostic-task-result.json。

已准备未应用的 task-interactive-proposed-disabled.xml，仅将Principal.LogonType从S4U改InteractiveToken，账户/动作/触发器均不变，Enabled=false。该候选需正常授权后先隔离验收，不能提前声称已解决；其代价是该账户未登录时不能执行。已向用户询问是否同意该运行条件变化；未获答复前不改正式任务。不通过放宽sandbox或启动Claude解决Session 0问题。


### 2026-09-25T10:50:15.436601+08:00 用户批准 InteractiveToken 后真实调度通过

用户明确同意“同意，改已登录模式并验收”。原任务仅登录方式S4U→InteractiveToken，账户/动作/周期保留；退出Windows登录后不执行。真实计划运行thread 01a0d670-f39c-77e1-a8aa-cb9bcbcb026c，1次成功工具读取随机凭据，凭据同时存在工具输出和最终答复，5类hook同thread/current bridge关联，测试结束恢复Disabled及paused wrapper。机器核验见interactive-scheduled-verification.json。该通过不覆盖真实业务探针/回件/对外发送，也不使五个Codex自动化自动启用。

版本化注册器同步采用Interactive，避免重注册回退S4U。注册回归RED→GREEN1通过；旧注册器路径/执行别名保护6通过2环境跳过；独立窄审阅无具体缺陷发现（已读diff、实际Principal传参及验收记录，未重跑测试）。注意：原注册器仍为注销重建，完整注册会重建任务启用状态；默认ConsumerEnabled仍关闭，不得将测试恢复Disabled误解为该脚本永久保持任务Disabled。

必要机制规定范围与三模型消费者端到端实测已齐；末轮注册器源码/文档登记自动落库后再关闭#648和最终业务开工闸。当前不启用真实业务自动消费；不调用Claude、不改五个PAUSED自动化、不做真实发送。之前失败证据保留。
## intent→deploy Task 1–5 隔离分支阶段证据（2026-09-25，待 Task 6 原生验收）

分支 `codex/intent-deploy-648` 的阶段状态、证据闸、单任务驱动和前台 guardian 已分别提交；Task 4 的 handoff + 原 opener/等待/解析回归 144 通过。脱敏看护件 `reports/mechanism-migration-648/guardian-dryrun-fixture.md` 通过原 lint 零违规，原批处理器 `-DryRun -Yes -Only A1` 实际解析出 `fixture-lane/A1`，未启动模型。Task 5 发布边界只准备 ff 请求与 LAN 转出：CI/review 缺证据或哈希漂移阻断，patch-id 已在 master 则记 skip，转出抑制默认企微通知且不连接 .51。此段是源码/离线回归与只读 DryRun 证据；尚未完成随机任务的原生 intent→deploy E2E，也未验收后台触发器。原三消费者既有验收不重跑，业务开发闸继续关闭。真实 ff、生产 .51、外发仍逐项授权。

## intent→deploy Task 6 现时增量（2026-09-25，仍未通过总闸）

| 检查点 | 现时状态 | 可复核证据与边界 |
|---|---|---|
| 离线阶段链及负例 | PASS（隔离） | `C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe -m pytest 0-学习与工具/codex-handoff -q -p no:cacheprovider`：152 passed；包含设计停点、批准路径、CI/review、ff/LAN转出停止点。独立代码审查提出的模型自行提交绕白名单、动作分类未绑定批准 intent、review 运行中可 release、旧 CI 无原文四缺口均修复并加负例。 |
| 原生脱敏单任务 | PARTIAL PASS | `native-task6-e75a/state/runs/native-fixture-e75a/`：proposal 原生 thread `01a0d7d4-1da9-7f50-a572-f99f72e912dd`，strict 有效；implement thread `01a0d7d8-2246-71a3-b0ad-815cdc18b9d4`，授权两文件由外层提交 `aa35d5646b145e304443e041a4c35ef7b507e56a`、20 条 hook；目标子项目 CI 原文 `ci-6bf4cee5dd4140c48d9495003d134be5-0.stdout.txt`：143 passed，SHA256 `c8b6be80135f6f271895d38f4dcac901cf0cc77eecdfa4028daa1080ac0350eb`。前四次 review 分别因工具非零/上下文超限受阻，记录未抹除。第五次 read-only thread `01a0d80d-72a8-7fe0-9023-bd0a636d4412` 的 3 工具中 1 条可选路径探测 exit1，经严格分类复核并单列审计，原 blocked attempt 保留。最终 release 仅返回 `paused` 与逐项 ff key，没有执行 ff。此样例从早于最新分类/并发加固的候选 HEAD 起步，不能冒充最终源码的整链原生验收。 |
| 真实自动唤醒与业务消费 | BLOCKED | guardian 前台能正确返回 `needs_manual_wake`；本线未注册并实测新的后台触发器。旧三个模型消费者的既有规定范围验收仍有效、仍停用；五项 Codex 自动化仍 PAUSED。不可声称无人值守继续。 |
| `.51` 与真实对外动作 | BLOCKED / 未授权 | 用户当前 Off LAN；未执行生产连接、ff、真实发送、L2 代签或 ASIL C/D 动作。仅有 LAN 转出与拒绝负例，生产验收须 On LAN 且逐项授权。 |
| OpenSpec / Superpowers 版本 | 决策已定，未升级 | 项目 Superpowers 技能包为 6.4.1，与当时官方最新一致；OpenSpec 本机 1.7.0、CI 锁定 1.7.0，官方已到 1.13.2。当前 Task6 基线不换版本；整链验收后在独立工作树 canary 1.13.2，再同步 CLI/CI/生成指令。 |

**总判定：#648 仍 open，业务开发闸仍关闭。** 后续须以最终源码重新通过原生 intent/分类批准→proposal→implement→目标 CI→独立 review→release-ready；再验真实后台触发器的账户、周期、停止开关及单消费者产物。不能把该夹具通过、计划勾选或 exit 0 写成机制整体验收。

### Task 6 最终源码夹具 f6a1 的失败记录（2026-09-25）

`native-task6-f6a1/` 使用脱敏外部 intent 批准和隔离队列替身，`prepare` 成功。首轮 proposal 因模型在 sandbox 内访问私有状态受阻；调整提示后，次轮原生 thread `01a0d842-2a3b-71b2-bbf5-da04ace0da4b` 写出四个 OpenSpec 文件，外层 strict 校验通过并提交设计 `1634a0946b4ba3b55d4d7e114fabf22bcc7d3b0d`。但该轮一条复合读取命令中的 `rg` 因不存在的 `workflow.py` 返回非零，驱动误把它归类为 OpenSpec CLI 不可访问，返回设计审核暂停。该暂停**不是有效的原生 proposal 验收**；未进入实现。无设计批准的负例仍停在原闸且 attempt 数不变。原生事件与失败输出保留在 `native-task6-f6a1/state/runs/native-fixture-f6a1/`。

误分类已加 RED→GREEN 回归：只有单一 `openspec validate` 命令的受限失败可委托外层 strict 复验；普通读取失败及含其他命令的复合命令均阻断。修复后 `test_workflow_driver.py` 27 passed。f6a1 历史尝试不改写为通过；仍需在此修复版重新取得原生整链证据。

### Task 6 f6a1 review R1：CI cwd 证据不足（2026-09-25）

第一次独立 review thread `01a0d8a1-e04b-7f01-a237-a698bc58d9fc` 对 implementation `7275f5eec40611a4c420c912cbd0c31c39d05294` 返回 `changes_required`。R1 指出 CI 把 pytest 子项目路径作为参数、但 cwd 留在 repo root，且报告未记录 cwd；因此旧“153 passed”不能证明按项目矩阵从子项目目录执行。原 review report SHA256 `fa2a7a4c97ddd86a358223c20658b21e20a0d586e4461b0bd8dda50b1f9c627c`，旧 CI raw stdout SHA256 `56d1103da8b1c56e88a4e40ac9ef3ec583c8e22651ef9d20bee5f7a84da99a0b`，均留存，不能改写为通过。

controller 已修正为逐项目 cwd 启动 pytest、机器报告记录 cwd/argv、release gate 验 cwd 与命令；新增工作目录及过期 review 归档/重开 review 闸的回归。完整 codex-handoff suite 在允许的 Windows 用户上下文中 **159 passed in 129.87s**。普通 sandbox 复跑出现两个 Windows 系统组件拒绝访问项（cscript 用户设置、ScheduledTasks action 构造），提权复跑只运行验证；注册测试为 `-WhatIf`，未启用或注册任务。

该完整 suite 仅验证 controller，不替代 f6a1 对应目标 workspace 的 CI。下一步必须用 `--refresh-ci-evidence` 显式重跑目标 CI、保留并归档旧 review、取得 fresh independent review；在这两步完成前，R1 与 f6a1 release gate 仍未闭合。
f6a1 按修复版驱动显式刷新：CI report `ci-report-318289def26243bd95e374ef2221c09b.json` SHA256 `d60bbc6c828843d9710c4464e060428a0cbca56cb4856e62f3c6c698c8b22bbf`；唯一目标 `0-学习与工具/codex-handoff` 的 cwd 为目标 worktree 内同名项目目录，argv 为隔离 Python `-m pytest -q -p no:cacheprovider`，exit 0，原文 **153 passed in 106.09s**，stdout SHA256 `45cc85308eaa4ff12bcfc2c38d1ff6f54c53552154a0811abdfb83faa486100e`，stderr empty SHA256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。旧 review 归档为 `review-history-d548fbe7c10648189f887d88596cff6c.json`，SHA256 保持原值 `fa2a7a4c97ddd86a358223c20658b21e20a0d586e4461b0bd8dda50b1f9c627c`。

刷新后独立 read-only review thread `01a0d8c8-7dbd-7292-ba68-fc450eaecdb8` 对 HEAD `7275f5eec40611a4c420c912cbd0c31c39d05294` 返回 `approved`，findings=[]，报告 SHA256 `a59ecc1d77d273732bece5b75b295289ebc0d046c1d5bef50a7278961db294a8`，核对 CI 与两个白名单文件的哈希。该结论只覆盖 f6a1 两个文件及其 CI，不覆盖完整机制或业务消费者。

Release-prep 已验证证据链并写出 `release-request.json`：patch-id `needs_merge`（15 unique commits，0 matched）；请求状态 `paused`，授权键 `ff:native-fixture-f6a1:7275f5eec40611a4c420c912cbd0c31c39d05294`，`delivery_accepted=false`、`ff_executed=false`。没有执行 ff。f6a1 样例现到 item-specific ff 授权闸，#648/业务开工总闸仍不因此自动通过。
### Controller follow-up review：CI 报告 fail-open 与刷新竞态（2026-09-25）

对首轮修复 commit `5e61f996d1dbd1dd1855dd846a7680662ea8a22e` 的只读 review 发现：release gate 可接受 `nodeid="."` / `service/..` 作为根目录 CI；driver/release 只检查部分 argv，可将 `--collect-only` 或空匹配 `-k` 当绿 CI；review 刷新先改状态、后取得独占锁，有并发覆盖风险。另有一条 Minor 建议要求把自由文本 finding 匹配改为结构码。以上均已按 RED→GREEN 补回归并修复：state 提供共同严格校验，拒绝根/穿越路径且只接受完整六项 Python pytest argv；driver 与 release 共用；`begin_attempt` 先创建独占锁再重读和核对状态快照，refresh 回调只在锁内归档旧 review、转阶段和保存 attempt；review refresh 只接受结构码 `CI_TARGET_SCOPE`，无该码的负例保持原 review 与 attempt 不变。

回归证据：driver/release/state 三模块 **58 passed**；完整 `0-学习与工具/codex-handoff` **169 passed in 126.68s**（正常 Windows 用户上下文，pytest basetemp 指向本地 workspace；普通 sandbox 对 cscript 用户设置与 ScheduledTasks action 的两个系统调用会拒绝访问，提权复验只运行测试，任务注册仍为 `-WhatIf`）。`diff --check` 通过。该修复 commit 的独立复审及基于最新 driver 的 release-prep 重核仍待完成；不能把这次 controller suite 作为总体机制验收。
在 controller follow-up commit `860ecf7d` 后用最新严格 gate 重核 f6a1 `release`：再次返回 `paused`，授权键仍精确绑定 `ff:native-fixture-f6a1:7275f5eec40611a4c420c912cbd0c31c39d05294`，`release-request.json` 已由最新 driver 重写。即严格 cwd/argv 校验、CI raw hashes、当前 approved review 均通过；patch-id 仍 `needs_merge`，delivery_accepted=false、ff_executed=false，未合入。controller follow-up 的独立代码复审进行中。

### 2026-09-25 Whole-branch controller review：三项 Important 已修复

独立 whole-branch review 对 codex/intent-deploy-648 报告 **0 Critical、3 Important**。三项均已按 RED→GREEN 落地：

1. proposal/implement 属于工作树写入阶段；现在拒绝当前 source checkout，并在 attempt 锁内首次绑定 workspace，后续拒绝同 HEAD 换路径继续。新增根工作树 proposal/implement 负例和同 HEAD alternate worktree 负例。
2. 普通 test→review 与 review→release-ready 过去只检查摘要字段；现在 driver、review gate 与 release gate 共用严格 CI 验证，校验精确项目 cwd、六项 canonical pytest argv、exit、stdout/stderr 绝对路径与 SHA256、机器报告 task/head/targets 绑定；review gate 还核验独立线程及原始 review report。新增 collect-only、根目录 cwd、缺失 raw、报告漂移四类×两个阶段负例。
3. guardian 原先只在内存保留批次结果；现在持久化 batch/task/lane 关联与状态，复用既有 lane heartbeat/pause/resume，人工 resume 才能同批续跑；同泳道后续任务等待前序 release-ready。批次观察直接读取持久状态，delivery_accepted=false 始终保留，企微通知被显式抑制，原始模型输出不拷入批次记录。新增暂停重建、重复派发防重、人工 resume 和同泳道停点负例。

RED 证据：工作树隔离 3 项失败、CI 8 项失败、guardian 持久状态 1 项失败、同泳道停点 1 项失败，均为预期行为断言未满足；修复后目标集合 **82 passed**，guardian 最终集合 **13 passed**，完整 0-学习与工具/codex-handoff/tests **182 passed in 147.32s**。完整命令：C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe -m pytest 0-学习与工具/codex-handoff/tests -q -p no:cacheprovider，在隔离 worktree、提权 Windows 用户上下文运行；测试不启用计划任务、业务消费者、发送或部署。

当前实现位于候选分支 `codex/intent-deploy-648`；全分支复审基点为 HEAD `860ecf7d`，本轮控制器修复已提交为 `b1ead52fae1a02e1e5cbdc30b36c9bd20ccf6190`，本地分支干净，未做 ff。复审中的低优先级建议（approval source 原文密封、真正并发 advance 回归、README 摘要与后文对齐）记录为后续非阻断项。本轮无需重复复审；依据为 RED→GREEN、完整套件及最终静态差异检查。

**总闸仍未通过**：在控制器提交 `b1ead52fae1a02e1e5cbdc30b36c9bd20ccf6190` 上用现有脱敏夹具重新执行 `advance`，strict CI + 独立 review 判定 `ready / release_ready`；重做 `release` 后精确停在 `ff:native-fixture-f6a1:7275f5eec40611a4c420c912cbd0c31c39d05294` 授权闸，`ff_executed=false`。这验证了最新控制器可核验真实原生阶段证据，但这些模型阶段运行仍早于本轮修复，不能冒称最终源码的全新 intent→proposal→implement→CI→independent review→release-prep 原生链已验收。仍须完成该原生整链及真实后台唤醒/停止开关验收。现有三消费者 E2E 证据沿用，不重跑；自动消费仍停用。用户 Off LAN 时不连接 .51，不做 ff、不做外发，也不启动业务开发。

### 2026-09-26 Task 6 末轮缺口复核（本地验收仍未闭合）

候选分支 `codex/intent-deploy-648` 当前 HEAD `2a87128e`，审计开始时 worktree clean。隔离分支现时探针报告 `C:/Dev/Codex/runtimes/zhuopin-ai/state/probe.json`（2026-09-26 05:20 +08）记录本地 HEAD、worktree/status、Python、Codex、OpenSpec、CI 矩阵与专用队列摘要；探针自身明确不推断 `/hooks` 信任或 Windows 注册任务状态，因此这些字段不替代功能验收，也不以 exit 0 作为完成结论。

| 检查点 | 现时判定 | 边界 |
|---|---|---|
| 最终 controller 的严格证据闸 | PASS（重核旧状态） | `b1ead52f` 后用现 controller 检查既有 `native-fixture-f6a1` 的 CI 原文与独立 review，并由 release-prep 停在逐项 `ff` 授权闸；旧模型阶段早于该 controller，不等于最终源码新原生整链。 |
| 最终源码新原生链 | BLOCKED | f6a1/e75a 的 intent/design 批准、task id、implementation HEAD 与白名单均绑定旧 fixture；不得复制/改写这些记录。新一轮必须有与当前 live #648、intent/action 和实际 design HEAD/hash 匹配的人工批准记录，按 proposal→设计批准→implement→CI→独立 review→release-prep 逐阶段取证。当前没有伪造或启动新 attempt。 |
| Guardian 后台触发及停止开关 | BLOCKED | 当前实现只给 `needs_manual_wake`，无 task-driven guardian 的已注册触发器。旧 `ZhuopinPollGuard` InteractiveToken 调度验收仅覆盖旧轮询器，不覆盖 guardian。若采用后台路径，须在常驻调度设计明确后实测触发器、账户、停止开关、单消费者与产物；五个既有 Codex 自动化仍 PAUSED。 |
| 旧三消费者验收、生产与发送 | 已沿用既有通过 / 未执行 | 按用户指示不重跑三消费者；Off LAN 不连 `.51`；本轮未 ff、未启用自动消费、未对外发送。 |

因此 Task 6.3、#648 与业务开发闸继续保持未完成/关闭。此前 182 项 controller suite、3 消费者 E2E、`ZhuopinPollGuard` 调度通过均保留原结论，不重复执行或挪作本轮证据。闭环仍需：最终源码上的新原生链，以及已定义并实际触发的后台看护路径；后者当前缺少调度策略（具名触发器及运行周期），未擅自新建或启用。


### 2026-09-26 人守 guardian 审阅修复增量（仍未过总闸）

隔离分支 `codex/intent-deploy-648` 的独立只读代码审查在首次人守实现 `f55c6ae9` 上发现多 opener PowerShell 绑定、进程死亡后批次锁、.51 清单未落权威转出、队列/看护件漂移与首次规划竞态。修复遵循 RED→GREEN：双 opener 参数传 `-Only A1,A2`，真实 `pwsh -File 工具-opener批处理执行v2.ps1 ... -DryRun` 输出两条泳道；未启动模型。prepare 要求人工批准的队列全文 SHA256，guardian 重新查 live/full row 并核已封存摘要；看护件字节、候选清单进入计划哈希，首次计划用排他创建。同批漂移停止而不覆盖。批次 `recover` 只在原 PID 已退出、task attempt 锁已结算时恢复；未知进程/未结算任务保留锁。release-ready 后有明确 `release_task_id` 的 .51 项才调用既有 `transfer_deploy`；隔离状态机实测转出存在且 off LAN 的 `deploy-authorize` 拒绝，未连接生产。前台长阶段每五分钟续写状态机心跳。

本轮代码审阅仍指出前台按波次串行，尚未覆盖批准设计中的跨泳道并发与错峰现场语义；LAN 变化时同批计划哈希会拒绝，需要新批人工复核。Aibot 真实脱敏回件→拆件→队列登记、最终源码新原生 intent→OpenSpec→批准→implement→CI→独立 review→release-prep 尚未完成；此前 f6a1/e75a 的授权与原生模型记录不能挪用。已有三消费者通过证据沿用，五个 PAUSED 自动化保持暂停。Task 6.3、#648、业务开发闸继续未闭合；不做 ff、.51 连接或真实外发。


### 2026-09-26 人守 guardian 增量（控制器证据，非总闸）

批准的触发策略已改为业务总线人守启动、当前会话内有界推进与下次显式恢复；本线不新增后台轮询器，五项 PAUSED 自动化不启用。旧 needs_manual_wake 只表示会话外不会自行运行，不再是本次人守模式的失败条件。

当前隔离分支已加队列全文复核、每项外部 LAN 分类证据、计划排他发布、后置设计批准 seal、跨批 claim、证据化退役与跨批旧源只读转出。新的入口级夹具确证旧批源 release-ready 后新批只领 deploy 行、start --run 真正进入 transfer validator、模型调用数不增加、off LAN 转出回执 production_executed=false、成功后释放 lane；源行 claim 漂移会阻断新批。另有权威转出已落盘而批次回执缺失的崩溃窗负例：退役保留 deploy 行 claim；预派工 claim 先落批次记录，可在 owner 退出后带外部证据退役。独立泳道并发/90 秒参数化错峰 RED→GREEN，主线程串行写 batch record，同泳道仍串行；这些是隔离控制器测试，不冒充 90 秒生产模型现场测量。

未闭合：最终源码上的全新原生 intent→OpenSpec proposal→该项设计批准→implement→目标 CI→独立 review→release-ready→ff 请求整链；Aibot 脱敏新回件→拆件→队列新行→人守选中的完整联接；真实业务队列 #648 的 item-specific intent/design 批准。原三消费者已验收结论沿用，不重跑。Off LAN 时 .51 保持 LAN 留步，未 ff、未连接生产、未外发，#648 与业务开发闸继续 open。


### 2026-09-26 人守接缝最终回归与原生新样例准备（总闸仍未通过）

在隔离分支当前未提交增量上，修复前台 guardian 的跨批旧源只读转出、首次 claim 的崩溃可恢复记录、独立泳道并发与错峰、部署项计入 max_items、calling 转交尝试防重及逐项人工结算。retire 仅在工作树外证据绑定 batch/plan、task/lane/item/attempt_at 与权威泳道状态 SHA256，且状态无匹配转出、结算期间未漂移时，允许释放该部署行 claim；哈希漂移及已有权威转出负例均阻断。回执缺失窗为测试模拟，不宣称做过真实进程 kill/recover。模型写入前另封存 source_checkout 与 Git common-dir，源 checkout 本身是 linked worktree 时也拒绝写入；入口在 claim 前执行相同检查。

本轮完整 0-学习与工具/codex-handoff/tests 为 **239 passed in 162.38s**；Aibot 桥一、派发、队列追加及新联接相关集合 **110 passed in 5.10s**；openspec validate codex-mechanism-migration --strict 有效，git diff --check 通过。新脱敏联测实际通过桥一第九态→信号→Codex provider 派发接缝→确定性拆件追加正式格式队列行→专用工具 digest/row live/open→off-LAN 下 guardian 将本地项选入计划，且 delivery_accepted=false。派发下游模型由测试替身承担；不能将这 110 项冒充新的原生模型运行。既有三消费者原生 E2E 结论保留，未重跑。

Shao Peishen 已针对 native-checkout-guard-648、队列 §一 #648、动作 worktree_local_build 和单一测试文件的脱敏原生样例明确回复“批准该 intent 与分类”。外部 intent 审批文件位于 C:/Dev/Codex/runtimes/zhuopin-ai/state/approvals/native-checkout-guard-648-intent.json，当前 live 行全文 SHA256 为 285fc313a73580172ab3e2e42c99bc66451c15de108cb889c4d44d82eacc181b。此批准只放行 prepare/proposal；新设计产出仍须该项审阅，不延伸到 ff、.51 或外发。最终源码的新原生整链仍待实测，Task 6.3、#648 与业务开工闸继续 open/关闭。用户 Off LAN，五项 Codex 自动化 PAUSED，业务消费者暂停。

### 2026-09-26 并发 claim 锁复审修复与原生首轮版本边界

独立只读代码 review 对 `4fb23c3d` 提出 P2：两条独立泳道正常并发争用同一 batch/claim 锁时，非阻塞锁会直接报错并把合法任务记为 blocked。先加正常短争用等待及超时 fail-closed 两项回归（修复前 2 failed），再让 OS byte-range 锁在 5 秒有界重试；超时仍拒绝，不吞掉其他 I/O 错误。完整 `invoke.ps1 -Mode Test` 结果 **241 passed in 164.70s**。此修复只改变互斥获取行为，不启用业务消费者或调度器。

已获批准的 `native-checkout-guard-648` 首轮 `prepare` 绑定旧 HEAD `4fb23c3d`；原生 proposal 产出设计 HEAD `48cea816` 并停在设计审。该轮早于并发锁修复，保留原始状态与事件，不计入最终源码原生整链验收。复审修复提交后将以同一用户批准的 task/intent/action 在独立状态目录、干净的最终源码 linked worktree 重新执行 proposal；两个状态目录明确区分，不迁移旧 attempt 或自签设计批准。
