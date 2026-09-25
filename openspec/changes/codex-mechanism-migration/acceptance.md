# 机制侧验收矩阵（未通过总闸）

检查点：6c2c041bd89d3ef7a8d4ea626609c3126884a897，分支codex/mechanism-migration-648。历史检查点时间：2026-09-24T18:04:50.338984+08:00；最新原生增量：2026-09-25T07:23:37.251788+08:00

**业务开发闸：仍关闭，等待末轮注册器修复自动落库收口。必要机制与三条消费者的规定范围运行验收均已通过；主仓普通身份 sandbox、新工作树 hook、现场安装模块隔离消费和已登录模式真实调度均有产物与审计证据。真实业务自动消费仍停用，未借验收发送消息。**

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
