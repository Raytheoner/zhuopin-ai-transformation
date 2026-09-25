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

## 初始交付记录（历史，非现时验收）


# zhuopinAI · Codex 接力

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
    & ".\0-学习与工具\codex-handoff\invoke.ps1" -Mode Workflow run --id "实际任务slug" --phase plan --workspace "C:\Dev\zhuopin-ai"

implement 阶段要求指定独立、干净、同 HEAD 的 git worktree，并通过 --authorization 指向已有的该任务设计授权证据；此文件仅是证据引用，不会生成授权。执行器使用 codex exec -a never、明确 sandbox，不指定模型，不绕过 hook trust。review 是只读阶段。真实模型调用尚未验收；命令可用/单测通过不等于已完成端到端无人值守构建。

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
