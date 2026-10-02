---
name: zhuopin-lane-watch
description: Use when Shao Peishen asks to start lane watch ("开启泳道看护") or requests read-only progress ("看看泳道").
---

先读根 AGENTS.md，再读仓库正本 0-学习与工具/skills源码/zhuopin-lane-watch/SKILL.md，遵守其中业务判据、授权及取证要求。

Codex 映射：文件与命令使用当前可用工具；Task/Agent 仅在本技能实际需要且当前权限允许时映射到 collaboration，并显式使用 `gpt-6-luna`。所有 Workflow/Guardian 派生模型任务都必须落到 `gpt-6-luna`：共享 driver 会把缺省模型解析为该值并拒绝非 Luna；wrapper 未暴露模型参数时，先确认目标版本已包含此强制路由，旧版不得继承会话默认。不存在的 Claude/Cowork API 不执行。定时任务由 Codex automation 工具管理，不能将保存脚本当作已调度。对外发送仍需用户明确指示。状态/队列按原专用工具读取和持锁登记。

涉及 .51 收口时仅引用 zhuopin-lan-closeout 正本，不复制程序。源码中的 Claude transcript、save_skill、set_session_title 不是 Codex 接口。若相关步骤无可用等价接口，记录缺口并继续独立可执行步骤。

## 看看泳道：只读进度路由

用户只说“看看泳道”时，不要求先提供 lane 或 batch，也不启动或恢复任何任务。使用当前仓库根的 Windows PowerShell 和正式入口：

```powershell
# Resolve the same isolated interpreter as invoke.ps1; do not use global python.
$repo = (Resolve-Path -LiteralPath '.').Path
$common = & git -c "safe.directory=$($repo.Replace('\','/'))" -C $repo rev-parse --git-common-dir
if ($LASTEXITCODE -ne 0) { throw '不能解析共享仓库runtime' }
$commonPath = if ([IO.Path]::IsPathRooted($common)) { $common } else { Join-Path $repo $common }
$runtimePath = Join-Path (Split-Path ([IO.Path]::GetFullPath($commonPath)) -Parent) '.codex/runtime.local.json'
$localRuntime = Join-Path $repo '.codex/runtime.local.json'
if (Test-Path -LiteralPath $localRuntime) { $runtimePath = $localRuntime }
$runtime = Get-Content -LiteralPath $runtimePath -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not (Test-Path -LiteralPath $runtime.python)) { throw "运行时不存在：$($runtime.python)" }
$showJson = & $runtime.python ".\0-学习与工具\工具-泳道看护状态机.py" show --json
$showExit = $LASTEXITCODE
if ($showExit -ne 0) { throw "show --json 失败，退出码 $showExit" }
$laneRecords = $showJson | ConvertFrom-Json
$batches = @($laneRecords.PSObject.Properties | Where-Object { $_.Value.status -ne 'done' -and $_.Value.batch } | ForEach-Object { [string]$_.Value.batch } | Sort-Object -Unique)
$batches
& ".\0-学习与工具\codex-handoff\invoke.ps1" -Mode Guardian observe --batch "<show返回的batch_id>"
& ".\0-学习与工具\codex-handoff\invoke.ps1" -Mode Workflow status --id "<observe返回的task_id>"
```

`show --json` 返回的顶层对象是泳道名到记录的映射；只从非终态记录的 `batch` 字段提取并去重批次号。先捕获输出并在本地结构化筛选 `lane/status/batch`，不要把整份大型 JSON 倾倒到会话；再对每个批次调用 `Guardian observe`，对每个返回的 `task_id` 调用 `Workflow status`。批次进度与任务现时状态分开报告：任务状态包含可见的 `phase`、最新 attempt、`busy`、原生 thread 与证据引用。没有 `thread_id` 时写“尚未形成/当前证据未知”，不估百分比、不根据文件时间猜进度。只读查看不创建模型任务；之后若要启动 Workflow/Guardian 派生任务，必须先确认目标版本的共享 driver 强制缺省路由为 `gpt-6-luna`。Guardian wrapper 无模型参数，目标版本未确认包含该规则时不得启动。旧引擎泳道没有 Guardian 批次绑定；`observe` 查无批次时说明“旧引擎/无 Codex 批次绑定”，不要报成状态损坏或空进度。

区分“没有批次”“命令失败或无权限”“状态损坏”“task/workspace 绑定未知”；不要把它们统称为空或完成。整个查看过程只用上述只读接口：不遍历私有 state，不读取队列真身，不调用 `Guardian start`、`Workflow advance`、`resume`、`recover` 或 `retire`。若随后要启动或恢复，等待用户明确提出该动作，再按原规则重新核验授权与前置。

## Codex 模式选择与执行闸

源正文的排波、依赖、暂停状态机、心跳、审计及人工闸继续生效；旧 CLI、旧标题和源端编排接口不能执行。当前原生格式与 provider 接缝依据 `openspec/changes/codex-mechanism-migration/design.md`，不能把改名当作等价编排。

- 用户说“开启泳道看护”时，不把口令当作后台轮询授权。开始会派生模型任务的 Guardian 操作前，先确认目标版本共享 driver 已强制把缺省模型解析为 `gpt-6-luna` 并拒绝非 Luna；旧版本仍不得启动 `start` 或 `--run`、不得继承会话默认。确认版本后，按源规则先用专用队列查询 `--digest --actionable` 与选中行 `--row N --section 一 --field all` 核实候选、触碰区及原文；按源锁纪律生成并登记看护件和 §二 批次，并将生成后已核验的 manifest 绝对路径赋给 PowerShell 变量 `$manifest`。使用当前 Windows PowerShell wrapper 的明确入口 `& ".\0-学习与工具\codex-handoff\invoke.ps1" -Mode Guardian start --manifest $manifest`；先让 Guardian 生成/核验计划，只有任务级设计授权、工作树映射、LAN 判定与原始启动授权均通过后，才对同一 manifest 加 `--run` 启动派生模型任务，不用 collaboration 直接绕过 Guardian。manifest 的当前机器合同以 0-学习与工具/codex-handoff/README.md 为准：每项必须显式给布尔 lan_required、工作树外的 lan_decision 文件（绑定队列行全文 SHA256、动作、lane、touches 与人工分类），可执行项的 workspaces 在首次规划时固定；proposal 后才可把该项实际设计批准加入 authorizations，由入口封存路径与 SHA256。deploy_51 须以工作树外 transfer_binding 双行证据和 release_task_id 绑定本批 release-ready 源；跨批旧源另给仅含 batch_id 的 release_reference，入口只读重核旧源的 plan/record、claim、队列全文和 release gate。转出只登记现有泳道状态机，绝不连接 .51。重启先 observe，活锁或未知任务先证据化 recover；无法继续的批次以外部逐项证据 retire，不直接删 claim。`--run`、lane resume、计划通过均不是 intent、设计、ff、部署或外发授权。最终原生整链未通过前不得声称机制总闸完成。
- 只有用户明确要求无头、且计划和该任务设计已有授权时，才采用 `工具-opener批处理执行v2.ps1`。先用 `--env Codex` 生成并 lint，按源流程 `-DryRun -Yes` 核对实际解析的泳道，再核对正常项目/hooks信任、隔离worktree及授权证据。`-ConsumerEnabled` 是执行开关，不是授权来源；前置未满足不能加开关起活。
- 原生 hook 必须在正常 `/hooks` 流程信任，并用同 thread/cwd 的实际事件确认生效；仅配置文件存在、用户已开 CLI 或生成器通过都不算。不要代写信任或使用旁路参数。
- 旧无头 opener 路径的命令保留 `-Plan`、限定的 `-Only`、日志目录与原并发/错峰纪律；这些参数不属于 Guardian `start`。source_id 不当作原生 resume ID，续棒从 provider session/result 取得 thread_id，经现有执行器接缝恢复，不运行旧 CLI。
- 读取 summary.json 的状态及证据；OUTPUT-NEEDS-REVIEW、进程0、OPENER_DONE都不标交付成功。失败停止依赖项，恢复到停止模型消费、保留信号；具体ff/部署/对外发送仍逐项授权。

本入口说明支持和停点，不表示 guardian、调度或现场部署已完成验收。
