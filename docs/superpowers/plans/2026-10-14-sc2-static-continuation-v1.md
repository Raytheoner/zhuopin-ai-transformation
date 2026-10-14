# SC2 原树分段静态续作差量 v1

状态：待 Shao Peishen 明确批准。2026-10-14（北京时间，Get-Date 实取）。唯一执行chat：`01a137cf-b51b-7ca1-8993-6b0af41f8845`。

## 1 目标、事实与唯一新增决定

目标仍为已批准的三指标可打开 MOCK 页面、API、来源明细、audit 与同一 snapshot_id 验证。307/308/309、SC2 原 design 和 12 路径继续有效；组件58fd1e9和四件ebe2f1e不重做。

当前 implement attempt `c760b03b97be4feeb5afd21a83f33069` 缺原始 outer seal，D3_only，busy/锁保留。现有 `settle-approved-stop` 仅支持原 mechanism task；`accept-sc2-proposal` 只支持非busy proposal。本差量不修复历史终止证明，也不把原 Workflow 记成功。

新增权限只有一项：将309中只授予kernel的受控静态作业例外，精确扩展到此次SC2 stopped/busy implement。允许本chat在原树原12路径中串行完成业务实现、测试、独审、受控outer commit与本地MOCK验收；本次静态作业由本chat编排，替代本次Guardian implement/test/review调度，不启动或恢复旧attempt。无需新增kernel代码、恢复入口、业务/恢复task或工作树。

此例外未经批准不能使用。它改变执行路径及对未结算busy树的写入许可，不扩大业务需求、数据权限或交付定义。

## 2 精确绑定与允许写入范围

- 原task：`sc2-three-metric-cold-1013v5`；原thread：`01a13668-0fd1-7962-9c4a-efe85cd9ce7b`；attempt见第1节。
- 原树：`C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v4-sc2-continuation/zhuopin-ai`；起始HEAD：`ebe2f1ed87ec721d1c330dc23c0cb4b05a3bd71c`。
- design SHA256：`9b8b7c9438a7ef309a2cecab10e64781b9f6c31e782699359d13b5e11c70959e`。
- 12路径逐字取 `C:/Dev/Codex/runtimes/zhuopin-ai/approvals/1013-pc-mvp-bootstrap-kernel-v1/sc2-implementation-309.json`，SHA256 `a6df24f2da20fa4a5b9494cba8be67466673ebe48220e4650806ffef815195b9`。不修改此批准文件。
- 停点manifest：`reports/pc-mvp-correction-1013/sc2-stop-preservation-e2351c32/manifest.json`，SHA256 `c1543f9cbef1a9efb4d5c00b853c3c1ffaff176b35a9161be2e0ce18da039a61`。
- 允许原树内12个产品/测试文件变更，以及该树正常git提交元数据；模型不自行commit，父chat核白名单后提交。不ff、不push作为本次验收前提。
- 执行输入、分段prompt、patch、测试stdout/JUnit/checkpoint、独审、最终静态验收收据及MOCK临时数据只新增于主仓 `reports/sc2-static-continuation-1014/`。测试缓存禁写业务树；使用独立basetemp及 `PYTHONDONTWRITEBYTECODE=1`、`-p no:cacheprovider`。
- 审批及进度登记只写本计划、原R5卡、既有队列#654与本项§四/§二；不改旧intent、四件、旧批准、任何旧state/lock/claim或309组件记录。共享文档按既有锁工具操作。
- 仓库外写入仅上述原树12路径及其正常git元数据，按工具正常审批运行；不改ACL、sandbox、hook信任、全局环境或运行保护阈值。不新增外部runtime写入。

## 3 写前与逐段门禁

1. 校验第2节全部版本/哈希、同仓common-dir、原树dirty范围、保全的12路径及7件原生证据。2026-10-14本chat实测19项全部相符；写前重取，不把本次检查当未来授权。
2. `wait_threads(timeoutMs=0)`复核原thread未运行；从原process/result读PID与可用进程树，核对所有可识别writer/后代的当前PID、创建时间、父子关系；对原树、task、attempt的当前进程命令行做定向只读核验，过滤本检查自身。原result的taskkill输出列出51820、63100、69644、53088、60260、38056及父driver40652，本chatCIM现查这些PID及其直接子代均无结果；原thread为interrupted/notLoaded。**这些仅是当前并发检查，不证明历史完整终止。** 若来源不足以核对可识别writer、发现无法排除的存活脱离子代、缺访问能力或身份不明，停在写前；不能仅凭单PID不存在放行。
3. 本chat为唯一owner，旧chat不写SC2；原Guardian仍blocked，禁止resume。串行派生任务一段只有一个writer，显式 `gpt-6-luna/high`；不继承长历史，不派生子子任务。自然结束并核对checkpoint后才能开下一段。
4. 正常hooks/文件白名单/sandbox均保留。若现有守卫拒绝这条静态写入路径，原样留证据，停止依赖，不改守卫或再生恢复task。本批准不授权技术绕过。
5. 每段前后校验原state/lock/claim及原生停止证据身份、字节未变；只允许本段拥有文件变更。每段checkpoint写输入/输出SHA、模型/thread、命令/cwd/退出/JUnit、未闭合项。不能把退出0或子代理自述单独当验收。

## 4 串行小段和可验收增量

子任务仅携带：本段目的、已批版本/边界、必要函数/测试、上一checkpoint、当前失败与结束条件。单次读取先量大小，再按函数/字段窗口；不注入旧proposal intent、全景或84KB冷计划。原完整计划继续作为审计依据，需要时只定位当前小节。

1. **计算四失败**：首段文件所有权只给 `sc2/metrics.py`，确证依赖缺陷时可在原12路径内使用models/sources/windows；不改业务断言去迎合结果。现有失败：`test_arrival_excludes_receipt_after_positive_promise_date`、`test_signed_order_formula_calculates_with_complete_evidence`、`test_signed_schedule_formula_uses_deadline_time_unanswered_evidence`、`test_unrelated_source_capability_does_not_block_arrival_metric`。先同命令重现，再最小修复，四项全过并检查有效零/unknown/pending相邻用例后自然结束。
2. **不可变快照与audit**：models/detail/config及必要sources接口、原白名单tests/fixture串行归属。检验canonical hash、显式ID、不覆盖、冲突拒绝、audit回读验链与失败关闭、legacy金样字节未变；本段完成后结束子任务。
3. **report/webapp**：只围绕已有页面/API接入三态、分子分母/原因码、来源下钻，所有视图返回同snapshot_id/hash，默认关闭、显式opt-in、无最新指针或隐式刷新。必要测试仍在原白名单测试文件，段末返回checkpoint。
4. **最终候选回归/独审/演示**：只在SC2项目根运行全部 `tests/` 必要完整回归，固定原隔离Python；关联平台仅对实际受影响合同跑既有定向验证，不在仓库根混跑。独立只读Luna High审查实际diff、定义绑定、CI原文/覆盖和SHA；有finding回到对应小段。本次批准包含独审通过后一次受控原树outer commit，不再单独询问同一提交动作；提交后核commit blob与已审候选一致，若字节有差异重验受影响部分并重审。不自动放宽skip、断言或环境门禁。

首段定向验证命令形态（实施时取唯一证据目录；不在批准前执行）：

```powershell
# cwd固定为原树/4-数字员工/采购部/SC2-采购周报自动生成
& 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -B -m pytest 'tests/test_three_metric_evidence.py' -k 'arrival_excludes or signed_order or signed_schedule or unrelated_source' -q -p no:cacheprovider --basetemp 'C:/Dev/zhuopin-ai/reports/sc2-static-continuation-1014/segment1-temp' --junitxml 'C:/Dev/zhuopin-ai/reports/sc2-static-continuation-1014/segment1.xml'
```

各段未通过不进入下一依赖；能做的无冲突只读准备可继续。正常完成即分段，不以150k或超时作交接节点。

## 5 验收与保留事项

以原307已批 `127.0.0.1:8096` 临时MOCK演示范围验收；占用者非本任务时不抢占。实际启动后才提供可打开链接。页面、API、来源明细、audit及快照文件逐项实测同snapshot_id/hash；截图/HTTP/audit证据落第2节报告目录。仅合成 `MOCK-` 数据。

最终收据标 `static_mock_delivery`，绑定实际commit、设计/批准、完整测试/审查、三指标展示/明细/audit证据；原Workflow仍busy、termination unknown/D3_only、原attempt未成功，不能冒充其 `delivery_accepted=true` 或通用release-ready。静态MOCK交付和原调度历史债分开写明。

G01–G04未签仍pending；真实源未知仍unknown；有效零按已签公式计算。真实取数、生产、ff、外发另批。旧锁与其他任务不属于本方案修复目标。

## 6 一次决定

1A（推荐）：批准本v1第2–5节，以及第1节明确的仅本次SC2静态续作例外；原307/308/309继续有效。影响：本chat可在原树原12路径完成分段实现及独立MOCK验收，历史停止记录与锁保持原样。批准不替代并发实测或正常工具权限检查。

1B：不批准该例外。影响：保全现有产物和锁，业务代码不续写，三指标MOCK继续未完成；不另开恢复任务。

无默认授权；答复绑定本文件完整SHA256。
