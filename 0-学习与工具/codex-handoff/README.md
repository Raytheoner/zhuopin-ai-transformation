> 2026-09-26 现时状态：主仓普通身份 sandbox、正常信任 hooks、新工作树继承及三条模型消费者规定范围原生 E2E 已通过；轮询任务采用已登录账户 InteractiveToken，任务仍 Disabled。追加的 intent→deploy 前台 guardian 与阶段驱动已在隔离分支实现，并发 claim 锁复审修复后控制器 241 项、Aibot 接缝相关 110 项通过；最终源码的新原生 intent→OpenSpec→实现→CI→独立 review→release-prep 链仍待运行，业务开工闸关闭。真实业务自动消费及五项 Codex 自动化保持暂停，Off LAN 不连接 .51。现时证据见 OpenSpec acceptance.md 末节；以下历史记录不代替现时状态。

## 2026-09-30 六业务入口与验收分层

本节记录 Codex 入口及已知停点，不把文档完成、单测或一个任务通过等同于六入口原生端到端验收。

| 用户入口 | 当前 Codex 路径 | 现有证据与未闭合项 |
|---|---|---|
| 开启泳道看护 | 读技能并用 `invoke.ps1 -Mode Guardian start --manifest $manifest` 生成/核验计划；满足任务级设计、工作树、LAN 与原始授权后，才对同一 manifest 加 `--run`。 | Guardian wrapper 固定走共享 driver；派生任务显式 Luna。启动业务结果仍待原生验收。 |
| 看看泳道 | 状态机 `show --json`（无需 lane）→批次去重→`invoke.ps1 -Mode Guardian observe --batch`→对每个 `task_id` 执行 `invoke.ps1 -Mode Workflow status --id`。 | 用返回的批次与 task_id 做只读查询；报告 phase、last attempt、busy、thread 与证据。无 thread 标为尚未形成/未知；不估百分比、不启动/恢复、不扫私有 state。 |
| 机器人监听 | 将 listener 心跳、`patrol.enabled` 与实际派发/消费分开核。 | 最近只读观察为 `listenerRunning=true`、`patrol.enabled=false`：监听进程运行不表示模型自动消费已开启。生产 consumer 保持关闭；隔离原生回灌联验未由本次文档修改证明。 |
| 跟进信回件回灌、归档拆件、入队及 Guardian 选入 | 按 `zhuopin-send-followup` 正本与 Aibot 实际 bridge/provider/watcher 接缝，在脱敏 fixture 验证；入队后用正式队列查询并生成 manifest。 | 本文不宣称实际 Codex 模型整链已通过；生产回件消费者不因入口存在而启用，真实发信仍须具体对象和发送闸授权。 |
| 值周计划 | 读 `.agents/skills/weekly-status-update/SKILL.md`，通过队列审计后按锁、登记和反查流程留档。 | 计划已生成，§II批次 `B-0930_周计划入档` 已由官方查询回读；早先一次release因5,598项现存脏路径未登记而被守卫拒绝；随后官方回读确认本计划批次done、CommitSweep提交cd7fcb62已落库、当前编辑锁无锁（详见acceptance.md）。`zhuopinai` 自动化保持暂停。 |
| 回 LAN 收口 | 读 `.agents/skills/zhuopin-lan-closeout/SKILL.md`；当次先跑 `工具-泳道看护状态机.py lan-status --json`。 | 2026-09-30 19:35 本机只读探针为 `on`（ping、8091/8093均HTTP 200）；本次未做 `.51` 部署。`off`、`unknown` 或探针异常即留步；`on` 仍须逐项授权、串行快照/执行/冒烟/回写，失败回滚停项。 |

**模型路由要求：**所有子代理/子会话及 Workflow/Guardian 派生模型任务必须显式使用 `gpt-6-luna`。Workflow `advance` 调用仍传 `--model gpt-6-luna`；共享 driver 会把缺省模型强制解析为 Luna 并拒绝非 Luna，因此 Guardian wrapper 无模型参数时，只有确认目标版本包含该强制路由后才能 `start` / `--run`；旧版本不得继承会话默认。只读 `observe` / `status` 查询不创建模型任务。既有周期自动化也须在 `view` 后显式设为 Luna；生产开关与自动化保持暂停直至各自单独获准。

**本节时点状态：**五份入口/说明文件正在本包中补齐；随后本计划登记及Sweep落库已由官方证据确认。真实模型回灌、Guardian 选入、实际 LAN 收口和六入口完整验收仍未闭合。本节不构成生产启动、发送、部署或 ff 授权。

## intent→deploy 新驱动（隔离分支实施中，尚未整体验收）

每次 `advance` 最多运行一个已过闸阶段；返回 `ready` 只表示下一阶段可被再次调用，返回 `paused` 表示等待该任务该版设计批准，`blocked` 保留现场。此入口不替代真实 guardian 调度。只在干净隔离 worktree 使用：

    & ".\0-学习与工具\codex-handoff\invoke.ps1" -Mode Workflow advance --id "任务slug" --workspace "隔离工作树绝对路径" --model "gpt-6-luna"
    & ".\0-学习与工具\codex-handoff\invoke.ps1" -Mode Workflow status --id "任务slug"
    & ".\0-学习与工具\codex-handoff\invoke.ps1" -Mode Workflow recover --id "任务slug"

发布准备与 LAN 转出只生成待审证据，不执行 ff 或生产：

    & ".\0-学习与工具\codex-handoff\invoke.ps1" -Mode Workflow release --id "任务slug" --branch "codex/任务分支"
    & ".\0-学习与工具\codex-handoff\invoke.ps1" -Mode Workflow transfer --id "任务slug" --batch "批次" --lane "泳道" --item "本次部署项"

新任务先用 `prepare --id "任务slug" --row N --section "一" --action-key "worktree_local_build" --intent "明确意图"` 写入真实队列行与原状态机动作分类；缺失或未知动作不会启动模型。隔离 E2E 夹具使用随机任务和假队列，不代表真实队列授权。失败 CI 修正原因后须显式 `advance --retry-failed-ci`；首轮 attempt 与独立机器报告保留，重试只针对同一干净 implementation HEAD，并按每个改动最具体的 CI 项目根逐项运行，pytest 从该子项目目录启动。旧成功报告若缺原文，或 review 已指出 CI cwd/命令证据不符，可显式 `advance --refresh-ci-evidence` 重跑；旧报告保留，review 驳回项会先归档，重跑后重新 review。release gate 校验每项 CI 的项目 cwd、命令及 stdout/stderr 哈希。`release` 先核 CI/review 原始报告哈希和 patch-id；已在 master 则记录 skip，否则产出绑定本任务 implementation HEAD 的 ff 授权请求。`transfer` 仅调用原泳道状态机记录 `deploy_51` 转出并给 LAN 收口正本指针，明确禁止默认企微通知；它不探测或连接 .51。同一项重复调用返回既有转出。两者均不生成授权，也不触发真实对外发送。
proposal 阶段由 Codex 在隔离工作树写出 OpenSpec 三件，严格校验后驱动记录 `design_head` 和 SHA256 并停止等待书面批准。批准后，人工提供工作树外的 JSON 证据文件给 `advance --authorization "绝对路径"`，字段为 `task_id`、`design_head`、`design_sha256`、`text`、`allowed_paths`（获准提交的仓库相对文件路径白名单）；文件本身不生成批准。模型只写文件，外层驱动从干净设计 HEAD 起核对改动只落在白名单内后提交。历史非零工具保留原始 `tool_failed` 与匹配事件计数，后续 CI 和独立 review 必须判断是否恢复。实施阶段只接受实际原生 thread、工具和对应 hook 审计、改动产物哈希、当次事件哨兵。测试逐受影响子项目执行；review 使用另一 Codex thread，报告必须绑定 implementation HEAD。退出码或模型自述均不代表交付通过。ff、生产 .51、真实外发仍逐项授权；本驱动不执行这些动作。
## 2026-09-24 机制迁移实施状态（队列 #648）

基础安装与路径修复已验收，以下旧章节保留的是初始交付时状态；现况以本节、OpenSpec `codex-mechanism-migration/progress.md` 和本机证据为准。

统一 provider 及三消费者的隔离实现已具备；默认暂停。原生只读工具运行已产生 thread/turn/工具证据，正常 /hooks 信任已完成，linked worktree 实际加载主仓项目配置。两轮独立代码审查及修复已完成；原生hook正负例、轮询和事件拆件隔离端到端已通过；批处理全新工作树写入/测试/独立内容审查/交接也已通过；主线获准ff已完成；Aibot模块已切换并保持暂停、轮询Codex包装已安装且任务Disabled；portable配置正常信任及现场调度验收仍未闭合；业务开发不得启动。

- 原生 provider：`model_provider.py`，按 runtime.local.json 或显式环境定位 Codex；routine/design 路由明示继承用户模型，不虚构模型或价格。
- 轮询与批处理：显式 `-ConsumerEnabled` 才启动；旧入口转交 v2。原生 opener 使用生成器 `--env Codex`，旧 guardian 尚未验收会拒绝生成。
- 回件拆件：`.codex/consumers.local.json` 中 patrol.enabled 必须显式 true，否则保留信号且不启动；生产服务尚未切换。
- 结果：进程0、turn.completed、OPENER_DONE 都最多是 output_needs_review；summary.json 的 DeliveryAccepted=false，保留 SourceId/Session/Evidence。
- 计量：匹配原生 session/workspace 的最近请求 token_count，不使用累计 usage；新轮次或未知事件清空旧值。计量缺失 fail closed。须另做真实阈值及恢复验证。
- 守卫：portable hook 从 cwd 查根目录，再由 invoke.ps1 解析共享 runtime；本机配置、consumer 开关、state 不入版本库。正常 /hooks 信任不可代写。
- 恢复：停止自动模型消费并保留信号/日志；Claude 已封存，禁止执行和回退。

五项既有 Codex 自动化已查询，均为 PAUSED。OpenSpec CLI 实际位于用户 npm 目录并通过本变更 strict 结构校验；该结果不代表机制功能验收。三个旧任务（轮询守、Claude环境体检、Claude插件补丁）已通过正常UAC备份并停用；Aibot活动模块已切换到Codex适配并保持暂停，服务已重启和持续心跳；尚不宣称现场消费验收完成。

验证证据位于隔离分支 `reports/mechanism-migration-648/`（本机忽略目录）；阶段记录与测试隔离事故见 OpenSpec progress.md。后续提交/ff/现场切换分别取证，既有脏文件和历史工作树不清理。

## intent→deploy 阶段入口（2026-09-25 候选分支）

`prepare` 现要求仓库外的 `--intent-approval` JSON：`task_id`、`row`（整数）、`section`、原始 `--intent` UTF-8 SHA256、`action_key`、队列查询返回的 `queue_file`/`queue_line`、专用 `--row N --section ... --field all` 输出的 UTF-8 `queue_full_sha256`、非空 `text`。它必须与实际队列查询的 live/open 行及 CLI 参数逐项一致；查询 `error` 或 `read_errors` 非空即拒绝。准备后的完整 `intent.md` 也单独封存哈希，内容漂移即停止。单独传 `--action-key` 不构成已批准分类；证据改动后阶段闸会暂停。文件应由当次人工确认产生，不能让模型在实施工作树内自行写入。

```powershell
& ".\0-学习与工具\codex-handoff\invoke.ps1" -Mode Workflow prepare --id "实际任务slug" --row 实际行号 --section "一" --intent "批准的原始任务意图" --action-key "现有分类器中的动作键" --intent-approval "C:\已确认的外部证据\intent-approval.json"
& ".\0-学习与工具\codex-handoff\invoke.ps1" -Mode Workflow advance --id "实际任务slug" --workspace "C:\独立工作树\zhuopin-ai" --model "gpt-6-luna"
```

设计批准 JSON 另需 `allowed_paths`；实现模型只写文件，外层驱动核对路径后提交，模型自行提交会阻断。`advance` 每次只运行一个阶段：proposal strict、批准后 implement、目标子项目 CI、独立只读 review。目标 CI 留存每次 stdout/stderr 原文与 SHA256；旧成功报告若缺原文，只能显式用 `--refresh-ci-evidence` 补跑，失败测试则用 `--retry-failed-ci`，两者均保留旧尝试。review 的可选路径探针非零仅在原生事件逐条匹配后记录分类复核，其他失败不放行。`release` 只生成 patch-id 预检及逐项 ff 授权请求，`transfer` 只记录 LAN 转出；都不执行 ff、`.51` 或外发。

前台 guardian 可返回 `needs_manual_wake`；尚无本线已注册且验收通过的后台触发器。因此当前需要人工唤醒，不能称无人值守自动继续。生产 `.51`、真实业务自动消费、ff 仍按各自授权闸执行。历史安装记录见下，现时状态以验收矩阵为准。

## 初始交付记录（历史，非现时验收）


# zhuopinAI · Codex 接力

## 2026-09-26 当前候选分支入口

用户在业务总线说“开启泳道看护”即由本次 Codex 会话人守启动；Aibot 回件的事件驱动拆件消费者沿用已验收链，落队列后由相同候选入口选入。不要把人守启动解释成新的 Windows 轮询或 24/7 后台服务。当前候选入口：

```powershell
# Read-only routes remain available without creating a model task.
& ".\0-学习与工具\codex-handoff\invoke.ps1" -Mode Guardian observe --batch "本批ID"
& ".\0-学习与工具\codex-handoff\invoke.ps1" -Mode Guardian recover --batch "本批ID"
& ".\0-学习与工具\codex-handoff\invoke.ps1" -Mode Guardian retire --batch "本批ID" --evidence "C:\绝对路径\本批退役审批.json"
```

当前 Guardian `start` wrapper 没有逐任务模型参数；只有核实目标版本共享 driver 已强制缺省路由为 `gpt-6-luna`、并拒绝非 Luna 后，才可按原授权调用 `start` 或 `--run`。不含该强制路由的旧版本不得继承会话默认。`observe` 是只读；`recover` / `retire` 仍须各自满足原证据和授权闸。

recover 仅在批次原进程已退出且相关 task attempt 已由 Workflow recover 用终态证据结算后对账；活进程、未知 PID、残留 task lock 均保留锁并报 blocked_unknown。领取队列 claim 前会先原子发布可恢复的批次初始记录；对账后的中断任务需核对泳道状态再显式 resume。计划排他创建；同批看护件字节、候选清单、队列原文或 LAN 观察变化会停在计划漂移，不自动重规划。无法继续的批次须以工作树外、绑定 batch_id 和 plan_sha256 的逐项退役证据调用 retire；已完成源行和权威状态机已转出的部署行 claim 保留，状态机不可读时保守拒绝释放。

manifest 至少包含 batch_id、watch_piece 绝对路径、candidates 数组。每项都需 task_id、row、section、由专用队列查询 --row N --field all 核对的 task_excerpt 与 next_action、opener_id、lane、touches、action_key、显式布尔 lan_required、工作树外的 lan_decision JSON 绝对路径；可另填 depends_on。LAN 判定文件逐项绑定行号、section、action、全文 SHA256、next_action、lane、touches 和人工分类原文。首次规划就给可执行任务的 workspaces 绝对路径映射，后补工作树会触发计划漂移；prepare 封存 source_checkout 与 Git common-dir，模型写入阶段必须是同仓、不同于源 checkout 的 linked worktree；设计批准可在 proposal 停点后按同一批次追加 authorizations 文件映射，外层封存每项路径与 SHA256，修改原批准会阻断。生成 manifest/看护件沿源技能的锁、队列与 §二 登记流程；入口复核 live/open 行、LAN、lint/DryRun 与 prepared state。生成器入口说明也以本节为准。

off/unknown LAN 留步项保留真实队列定位和下一动作。已有源任务要转出 .51 时，部署候选须指定 release_task_id 及工作树外的 transfer_binding JSON，后者绑定源/部署两行、全文哈希、LAN 动作和人工原文。源可在本批达到 release-ready；旧批已完成时只给 release_reference 的 batch_id，入口将只读重核旧批 plan/record、源行 claim、现时队列全文和 release gate 后解析引用，新批只领部署行且不重新启动源模型。转出写既有泳道状态机，调用前先持久记 transfer_attempt=calling，回执与 claim 分开留痕；重醒遇 calling 不自动再调用。退役时默认保留该部署行 claim；确经人工逐项核对未转交时，工作树外退役证据可含 settle_not_transferred，逐项绑定 task/lane/item/attempt_at、权威泳道状态文件 SHA256 与人工原文，只有状态未变且无匹配转出才释放该行。.51 真正发布仍需回 LAN 后当次探针和逐项授权。前台按波次推进，同泳道串行；独立泳道最多按 max_parallel 并行，启动按 stagger_seconds 错峰。此机制已有隔离并发用例，原生整链仍以验收矩阵为准。

脱敏联接测试已把桥一回件标记、信号、事件派发、确定性拆件落队列、专用查询及 guardian 选入串起；拆件模型本身沿用既有原生消费者验收，这项确定性联测不能单独证明新模型整链。以上是候选实现说明，**不代表**最终源码原生 intent→proposal→implement→CI→独立 review 整链或 .51 生产发布已经验收。当前证据及阻断见 `openspec/changes/codex-mechanism-migration/acceptance.md`。

## 初始安装说明（历史）

本说明描述安装后的布局；实际安装状态以 installed-manifest.json 为准。当前环境写入受阻，交付包尚未安装到源仓库。

本次是原仓库原位接力，文档、代码、OpenSpec、路线图、队列、历史分支及原 .claude 配置继续原位保留。没有创建第二份业务正本、删除 Claude 环境或批准发布。

## 安装后入口

- 根 AGENTS.md：Codex 行为入口，指向原业务规则。
- .codex/config.toml：子目录 CLAUDE.md fallback、UTF-8、hooks 功能。
- .agents/skills：6 个项目技能、7 个 Cowork 业务流程适配入口、15 个 Superpowers 6.4.1 原生技能、1 个接力技能。原本的5个 source-command-opsx 入口保留。
- .codex/references/claude-memory：26 份历史记忆快照，原文来源与哈希见迁移清单。只作参考，不能覆盖现时正本。
- .codex/hooks.json + hook_bridge.py：协议适配入口。
- 本机 Python：C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe；独立 CPython 3.14.5 与 CI 依赖闭包。无全局 editable 指针。
- runtime.local.json 存本机路径、不存凭据；状态与日志位于 C:/Dev/Codex/runtimes/zhuopin-ai/state。

## 使用

从仓库根在 PowerShell 运行，路径必须加引号：

    & ".\0-学习与工具\codex-handoff\invoke.ps1" -Mode Probe
    & ".\0-学习与工具\codex-handoff\invoke.ps1" -Mode Test

先通过原队列查询选择真实任务，再执行：

    & ".\0-学习与工具\codex-handoff\invoke.ps1" -Mode Workflow prepare --id "实际任务slug" --row 实际行号 --section "一" --intent "已明确的任务意图"
& ".\0-学习与工具\codex-handoff\invoke.ps1" -Mode Workflow run --id "实际任务slug" --phase plan --workspace "C:\Dev\zhuopin-ai" --model "gpt-6-luna"

implement 阶段要求指定独立、干净、同 HEAD 的 git worktree，并通过 --authorization 指向已有的该任务设计授权证据；此文件仅是证据引用，不会生成授权。执行器使用 codex exec -a never、明确 sandbox，并显式指定 `gpt-6-luna`，不绕过 hook trust。review 是只读阶段。真实模型调用尚未验收；命令可用/单测通过不等于已完成端到端无人值守构建。

intent → 规划/Spec → 设计确认 → 实现/逐项目测试 → review → 发布准备 → 原项目部署闸，按阶段接力。runner 有单任务互斥、HEAD 漂移检查、失败停止与运行证据；退出0只标 stage_output_needs_review，不标交付成功。当前没有无人值守自动跨越阶段的调度器。生产收口只执行既有 zhuopin-lan-closeout 正本，逐项授权不因本迁移取消。

## Hook 覆盖与限制

Codex 官方要求非托管 hooks 通过 /hooks 审阅信任；本项目不会代写信任数据库。项目本身也须在 Codex 中信任。信任未核验前，只能说已配置，不能说已生效。

适配器支持 native apply_patch（含多文件、删除、移动双端）、exec_command/Bash、旧结构 Read/Grep/Edit/Write/MultiEdit；复用原 editlock、queue-read、dedup 与两种写入哨兵。旧 Bash/Edit/Write matcher 在 Codex 有别名支持，真正迁移问题是 payload 字段和 transcript 格式。

functions.exec 内嵌工具、任意 Python/Node/PowerShell 文件写入、MCP 和不走该事件路径的工具不能保证完整拦截。shell 的业务读取判据仍是原脚本能力，不把它宣称为通用安全边界。原守卫内部 fail-open 语义未改；适配层PreToolUse解析/启动失败明确返回原生JSON deny；其他事件失败报错退出2。原生apply_patch读取tool_input.command；详情见当前验收矩阵。原守卫日志仍按原协议写入。

原 Claude context-meter、基于 Claude transcript 的 Stop 审核没有伪造等价迁移：本次用事件审计及 AGENTS 检查点承接，缺少精确 token 用量与最终回复硬拦截。Superpowers 安装形态是项目技能包，未宣称已在 Codex 插件商店安装。

## 调度与插件

Windows 已注册任务状态目前读取被系统拒绝；源码清单不是已注册任务清单。C:/Users/Paul Shao/Claude/Scheduled 本次查看为空，也不能据此推断云端/其他客户端没有任务。

export-scheduled-tasks.ps1 只读导出实际注册状态；完整 XML 留在本机 runtime 私有目录，summary 中参数仅保留 SHA256。核验同一任务原消费者停用之后，才启用新消费者。原业务服务、sweep、告警/跟进服务不批量重注册、不停服务。旧周期/时区/账户/权限/触发器必须以实际导出核验。

任务源码与旧 enabled 状态已归档；过期一次性密钥提醒、无关行业任务、已退休 lane-clearpool 不重新激活。last30days 中英两个插件是互补工具，均保留。其他源端禁用插件只做资产索引，不擅自启用 MCP/外部账号；文档工具可使用 Codex 现有原生技能。凭据继续引用原本机环境与凭据存放位置，不复制到仓库。

## 验证与恢复

新适配器测试见 tests。完整业务构建仍以原 .github/workflows/ci.yml 动态矩阵逐子项目执行。旧检查报告的 gateway、aibot 打包/测试与进度 lint 问题未在迁移中无依据修改；当前 HEAD 必须重新取证。

迁移证据目录含 installed-manifest.json 与 rollback.py。回滚逐文件比对安装时 SHA256，只恢复仍等于迁移版本的文件；任何后来改动都跳过并报告冲突。不删除原业务内容、工作树、插件或计划任务。安装文件未自动提交/合入，随正常评审落库。

## 本机额外检查结果

迁移时 codex doctor 的 config.load/auth 为正常；sandbox.helpers 为 helper_unknown_error；provider 连接失败；goals/memories 数据库为无法打开（code 14），不是已证实损坏。标准 shell 同时 setup refresh failed。不能删除数据库或绕过 sandbox 作为修复。OpenSpec 1.7.0 未找到，npm 恢复尝试超时；交付包附 Restore-OpenSpec.ps1 供恢复正常 shell 后执行。

5 个原任务对应的 Codex cron 已实际创建为 PAUSED，创建回执见 automations.json。旧时间来自源文档历史记录，并非当前原任务实测；月更09:00为暂定占位，启用前一并核验时区与触发器。手工启用前完成单消费者核验。
