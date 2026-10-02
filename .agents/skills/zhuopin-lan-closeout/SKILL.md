---
name: zhuopin-lan-closeout
description: Use when Shao Peishen returns to LAN and asks to close out LAN-pending .51 work.
---

先读根 AGENTS.md，再读仓库正本 0-学习与工具/skills源码/zhuopin-lan-closeout/SKILL.md，遵守其中业务判据、授权及取证要求。

Codex 映射：文件与命令使用当前可用工具；Task/Agent 仅在本技能实际需要且当前权限允许时映射到 collaboration；不存在的 Claude/Cowork API 不执行。定时任务由 Codex automation 工具管理，不能将保存脚本当作已调度。对外发送仍需用户明确指示。状态/队列按原专用工具读取和持锁登记。

涉及 .51 收口时仅引用 zhuopin-lan-closeout 正本，不复制程序。源码中的 Claude transcript、save_skill、set_session_title 不是 Codex 接口。若相关步骤无可用等价接口，记录缺口并继续独立可执行步骤。

## Codex工具映射与停止条件

在仓库根用当前可用的 Windows PowerShell 执行器，并先读 `.claude/rules/场景建造与合规.md`、`.claude/rules/队列与落库.md` 和本目录指向的规则正本。Shao Peishen 说“回LAN”只是触发检查，不证明设备已在内网。每次收口都先现跑 LAN 探针：

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
& $runtime.python ".\0-学习与工具\工具-泳道看护状态机.py" lan-status --json
```

`off`、`unknown`、探针报错或结果无法绑定当前环境时，保留留步项和证据并停止；不得连接 `.51`、调用部署命令或报告部署完成。结果为 `on` 时，再按 `zhuopin-lan-closeout` 源正本逐项处理 `.51` 清单：每次只处理一项，按快照→执行→冒烟→回写证据推进；冒烟失败立即回滚并停止该项。实际执行必须有针对该项目的明确授权，读到其他项的授权不能类推。

队列与泳道状态只经各自专用查询/状态机读取；不得读取或 grep 队列真身，也不得直接扫描私有 state。使用 Codex 当前 PowerShell、文件与工具接口，不调用 Claude/Cowork 专属命令，不以绕过 sandbox 或 hook 信任的方式连接生产。`Workflow transfer` 只登记转出，不是部署。只有当次探针、逐项授权和规定的冒烟证据均完整，才可报告该项完成；这份映射本身不代表 LAN 探针、`.51` 部署或生产收口已验收。

任何子代理、子会话或 Workflow/Guardian 派生模型任务都显式指定 `gpt-6-luna`。入口不能指定时不启动该模型任务，报告路由限制并等待路由修复；不得静默继承其他模型。纯 LAN 探针和只读状态查询不创建模型任务。
