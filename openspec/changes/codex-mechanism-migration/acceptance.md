# 机制侧验收矩阵（未通过总闸）

检查点：6c2c041bd89d3ef7a8d4ea626609c3126884a897，分支codex/mechanism-migration-648。历史检查点时间：2026-09-24T18:04:50.338984+08:00；最新原生增量：2026-09-25T07:23:37.251788+08:00

**业务开发闸：关闭。轮询与事件拆件的隔离原生端到端已通过，批处理新工作树链亦已通过；现场调度/服务与主线合入尚未完成，Aibot现场仍有旧模型启动路径。**

| 必要项 | 状态 | 实证 / 剩余动作 |
|---|---|---|
| 统一provider及安全权限、失败/超时/清理、路由 | 单测通过；原生部分通过 | provider-final.txt：32；native-review-1和native-resume-1真实thread/工具/turn/计量；当前 hook 正负例已通过，三消费者产物分项验收 |
| 轮询守静默/sticky/失败/注册器 | 隔离验证通过 | provider-poll-final.txt：57通过2跳过（含当时provider）；原生轮询通过：thread 01a0d5b0-5abe-7d33-9f63-964c834d74e6，真实读取随机凭据，五事件全部关联 |
| opener生成/lint/旧入口/批处理 | 隔离及原生新工作树链通过 | 新套件已回归原入口，保留行为11、验证/并发7、合法生成/身份/PS5.1共3、变异/错峰及相关核心7；不能相加冒充独立总数；v4 thread 01a0d5cc-1edd-74b2-9e19-e2c714263641：6工具0失败、pytest2通过、三个产物哈希、15hook、独立内容review均通过 |
| 收工探针与原生占号审计 | 针对性回归通过 | downstream-green.txt：136通过25子测试，包含生成器回归；新状态不得静默漏报 |
| 事件拆件 | 模块及隔离原生链通过；现场未切换 | patrol-final.txt：34；包含无进展退避/三次停链/信号保留；native-patrol：真实模型写回执、消费假信号、同PID重复派发拒绝、watcher结束；真实服务尚未切换 |
| 接力runner | 单测通过 | handoff-provider-green.txt：20；末轮修复后受影响集合182通过/15子测试，另异常分支1通过；记录实施HEAD供review，额外漂移拒绝 |
| 原生hook与apply_patch负例 | 当前桥接正负例通过 | 用户正常 /hooks 已信任主仓项目配置；v3 正例真实写入，负例 editlock拒绝且文件未变、无PostToolUse；关联会话与桥接SHA，native-acceptance-verification.json |
| 可版本化资产继承 | 检查点及全新checkout通过 | fresh-worktree-inheritance.json：6个核心blob一致，34技能，无runtime副本，共享runtime解析成功，工作树干净；不等于native hook生效 |
| Windows旧任务 | 三项已暂停 | runtime scheduler-export/pause-648-admin-*：XML、SHA256和enabled=false；轮询守、Claude体检、Claude插件补丁 |
| 单消费者调度/现场切换 | 未完成 | 五项Codex自动化PAUSED；Aibot受控切换、实际触发到证据闭环未验 |
| zhuopinAI 必要技能/配置 | 部分验证 | asset-disposition.md 是历史全量索引；只核验本项目依赖。中英文last30days属行业研报项目，连同其他无关配置移出本线门槛，保留现状 |
| 独立代码审查 | 两轮审查修复通过 | 初审四项、终审两项均复现修复；final-review-green.txt：182通过/15子测试；另HEAD取证失败分支1通过 |
| 发布/ff | 未授权执行 | 实现与审查证据已在候选分支提交，并同步当时主线a707dca2的两份治理文档；未push/ff/业务部署。具体发布件见release-readiness.md，现场执行前核对现时主线和逐项授权 |
| 历史覆盖 | 边界明示 | 原26份记忆保留主仓；复制被自动审批拒绝，本分支仅检索指针。Cowork主对话完整覆盖仍是已知证据缺口，不重启Claude |

## 不得隐去的测试事故

早期两次poll RED夹具被旧脚本忽略新参数后实际拉起封存CLI，日志报组织禁用访问；无成功消费。已即时告知并留档，原结果作废。后续夹具硬阻断旧CLI查找，当前实现移除旧调用路径。详见progress.md。此事故不能用后续通过覆盖。

## 继续验收所需

正常信任、原生apply_patch正负例、轮询和事件拆件隔离原生链已完成。批处理新工作树真实写入→测试→独立内容review→交接也已通过。按tasks.md继续获准主线合入、portable配置正常信任与现场调度切换。再把可审查发布件交逐项ff及现场切换授权。任何一项未闭合，都不得以计划、exit0、OPENER_DONE或本表存在为由启动业务开发。

## 原生接缝增量（2026-09-25T07:23:37.251788+08:00）

当前桥接SHA256：572a7df9f5908da2fc3fb2bd7743f324a396a7a71744f9ef68f60b9675e315d3。解析真实 tool_input.command；PreToolUse失败输出原生permissionDecision=deny。受影响 test_handoff.py 27项通过。v2负例曾出现守卫exit2但文件仍被改，明确作废并保留日志；修复后v3负例保留原文。主仓活动桥接已按迁移授权备份并精确同步，未改hooks配置或trust。证据：active-hook-deny-install.json、native-hook-deny-green.txt、native-acceptance-verification.json及各会话correlated-hook-audit.json。provider的accepted=false保持不变，外层仅按产物和事件联合验收。

## 2026-09-25T08:01:37.053690+08:00 三消费者隔离原生链闭合

轮询和拆件证据沿用native-acceptance-verification.json（桥接572a7d）；新增异常输入/启动器修复后，最新桥接69fe2333+启动器99afd63b的原生负例与batch正向写入链见native-final-verification.json。未将旧运行冒充最新哈希重测。v4从实现c2e8c9d5新建工作树；真实工具、测试、审计、产物均核验，独立审查方式见native-batch-v4-independent-review.md。provider/batch内部accepted=false保持不变，外层验收独立留证。

候选portable hooks最外层新增exit $LASTEXITCODE，真实pwsh非零传播RED→GREEN，launcher8通过；当前主仓固定-File hooks无需此包装。候选配置尚未在主线正常信任和现场验证，合入后不得沿用旧hash冒充新信任。必要现场项仍阻塞总闸。
