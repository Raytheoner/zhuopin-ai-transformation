---
name: weekly-status-update
description: Use when Shao Peishen asks for the weekly plan ("值周计划") or asks to inspect or change its recurring Codex automation.
---

# 值周计划：Codex入口

值周业务判据以 `0-学习与工具/定时任务源码/weekly-status-update.SKILL.md` 为正本；队列审计细节以 `.agents/skills/zhuopin-queue-audit/SKILL.md` 和其指向的源技能为准。先读它们，再按当前 Codex 工具执行，不复制或改写原业务规则。

用户请求本周计划时：

1. 在仓库根使用项目 Windows PowerShell 与正式只读队列工具：先按正本运行 `zhuopin-queue-audit`，扫池用 `工具-队列查询.py --digest`，判行时按来源选择 `--row N --section 一 --field all` 或 `--row N --section 四 --field all`；PowerShell 中 `|` 是管道符，不能把 `一|四` 写成一个参数；禁止通读或 grep 两份队列真身。
2. 周期节奏遵循原章程的每周一 10:00（避开早会）；计划日期用本机 PowerShell 当场读取 `Get-Date -Format 'yyyy-MM-dd'`，写入 `1-转型规划/0-全景路线图/本周计划-YYYY-MM-DD.md`，frontmatter 保留 `status: 在办`。每期不超过 10,000 B，按原章程保持 A 本周应启动/续推、B 决策/动作、C 临期红线日、D 异常与流程自检四节。
3. 在仓库根读取 `.codex/runtime.local.json` 取得隔离 Python；先用 `工具-共享文档编辑锁.py status` 查看共享锁，再以本次唯一的 Codex session 标识运行 `acquire --who <session> --note <本周计划路径>`。紧接着读取 `$LASTEXITCODE`，非 0 即停止且不写文件。拿锁后写计划，并用同一 `$who` 调用 `append-row --who <session> --section 二 --domain 机 --cell 'B-<YYYYMMDD>_本周计划' --cell '`1-转型规划/0-全景路线图/本周计划-<YYYY-MM-DD>.md`;`1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md`' --cell 'docs: 周计划 <YYYY-MM-DD>' --cell '待处理（登记，待 sweep 落库）'`；路径须用仓库根相对路径并按协议加反引号，登记清单包含计划文件和机制环境队列文件。立即检查 `$LASTEXITCODE`；成功后 `release --who <session>` 并检查退出码。§II登记后等待现有 `ZhuopinCommitSweep` 按计划自动取活；只有按根队列规则确认 CommitSweep 不可用时才由CC责任端兜底；Codex不得调用旧CC/Claude接口或手动启动 sweep，此时报告并交回责任端。PollGuard 与 CommitSweep 是不同任务，业务预警恢复不等于 PollGuard 恢复，禁止据此启用或重跑 PollGuard。最后运行 `工具-写后反查.ps1 -Path <计划绝对路径> -Keyword <独有文本>`，再用 `工具-队列查询.py --row <批次号> --section 二 --field all` 回读。每个写命令之后立刻取 `$LASTEXITCODE`；任何非 0 都停止后续写入并保留现场。命令参数以这三个工具的 `--help` 和队列协议为准；不得用 PowerShell 裸 `|` 表示“二选一”。
4. 回复计划文件指针与需决策项；没有例外时如实说明。本次手动生成不代表周期调度已创建或启用。

只有用户明确要求查看或修改周期调度时，才先定位并 `view` 既有 `zhuopinai` 自动化，再用 Codex automation 工具处理；保留原项目、周期及时区，模型显式设为 `gpt-6-luna`，未获单独启用授权时保持 `PAUSED`。若当前接口不能设定 Luna，则保持暂停、报告路由限制并等待修复。不得新建重复自动化，也不得因本 skill 文件存在而声称计划已自动运行。

如本次计划需要子代理、子会话或 Workflow/Guardian 派生模型任务，也必须显式指定 `gpt-6-luna`；入口不能指定时停止该派生任务并报告，禁止静默继承其他模型。纯只读队列与状态查询不创建模型任务。
