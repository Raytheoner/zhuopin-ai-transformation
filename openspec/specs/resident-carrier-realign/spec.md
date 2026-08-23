# resident-carrier-realign Specification

## Purpose
TBD - created by archiving change carrier-health-guard. Update Purpose after archive.
## Requirements
### Requirement: 本脚本 SHALL 是「停服→重启→验活」的唯一实现

停服（先父后子＋复查零残留）、验重启（进程链 `CreationTime` 比对）、验活（心跳时间戳刷新）三步 SHALL 只有本脚本一处实现。

sweep 在自动重启开关开启时 SHALL **调用本脚本**完成重启，MUST NOT 在自身内重新实现上述任一步骤——人工执行与机器执行走同一实现。

#### Scenario: 机器与人走同一实现
- **WHEN** sweep 在自动重启开关开启时需要重启某执行体
- **THEN** 它调用本脚本的 `-RestartOnly` 模式，而不是自行实现停服与验活

#### Scenario: 开关关闭时 sweep 不代跑
- **WHEN** 自动重启开关关闭且本轮需要重启
- **THEN** sweep 只告警并给出本脚本的调用命令，不执行任何重启动作

### Requirement: 脚本 SHALL 提供 `-RestartOnly` 模式

`-RestartOnly` SHALL 跳过可 ff 校验、固化备份与 ff 三关，直接执行停服→启动→验重启→验活。

该模式下 MUST NOT 执行任何 merge，MUST NOT 因「已对齐（落后 0）」而提前退出——落后 0 正是它的常态（ff 已由 sweep 每轮做掉）。

#### Scenario: 落后为 0 时仍执行重启
- **WHEN** 以 `-RestartOnly` 调用，且该执行体落后 0
- **THEN** 脚本继续执行停服与重启验活，不提前退出

#### Scenario: RestartOnly 不做 ff
- **WHEN** 以 `-RestartOnly` 调用
- **THEN** 摘要写明可 ff 校验／固化备份／ff 三关均已跳过，且工作区未发生 merge

### Requirement: 对齐前 SHALL 校验身份与可 ff 性

（可 ff 性与备份两关只在**非** `-RestartOnly` 模式下适用；身份校验两模式均适用。）

脚本 SHALL 先校验目标目录内 `.git` 条目存在且在 `git worktree list --porcelain` 注册项内，MUST NOT 依据 `git -C` 的输出判定身份。

脚本 SHALL 校验目标 `HEAD` 是 `master` 的祖先且 ahead ＝ 0；不满足时 MUST 停止并以非零退出码返回，MUST NOT 执行 revert、cherry-pick 或任何会造出第三种代码状态的操作。

#### Scenario: 非注册目录被拒绝
- **WHEN** 目标目录不在 `git worktree list --porcelain` 注册项内
- **THEN** 脚本停止，非零退出码，且未执行任何写操作

#### Scenario: 不可 ff 时停止
- **WHEN** 目标 `HEAD` 不是 `master` 的祖先，或 ahead > 0
- **THEN** 脚本停止并报告原因，MUST NOT 尝试 merge、rebase 或 revert

### Requirement: ff 前 SHALL 固化备份仓库外内容

脚本 SHALL 在任何写操作之前，把目标 worktree 内**未跟踪**与**被 gitignore 命中**的内容复制到**仓库外**目录，并回显备份清单与件数。

备份目录 MUST 在仓库之外，MUST NOT 落在仓库内任何路径。

备份失败时 MUST 停止，MUST NOT 继续 ff。

#### Scenario: 备份清单被回显
- **WHEN** 目标 worktree 含 1 个未跟踪文件与 20 项 ignored 内容
- **THEN** 输出列出全部条目并给出件数，备份目录路径在仓库之外

#### Scenario: 备份失败即停止
- **WHEN** 备份过程发生错误
- **THEN** 脚本停止并以非零退出码返回，未执行 ff

### Requirement: 停服 SHALL 杀整条进程链且先父后子

脚本 SHALL 在 `Stop-ScheduledTask` 之后枚举该 worktree 关联的整条进程链（脚本宿主 → shell → 解释器），**先终止父进程再终止子进程**，随后**复查零残留**才继续。

MUST NOT 仅依赖 `Stop-ScheduledTask` 的返回值判定服务已停——实测它只终止脚本宿主进程，遗留 shell 与解释器子进程。

MUST NOT 先杀子进程——父进程带自愈，先杀子会被立刻拉起。

复查发现残留时 MUST 停止并报告，MUST NOT 继续 ff。

#### Scenario: 遗留子进程被清理
- **WHEN** `Stop-ScheduledTask` 后仍存在 shell 与解释器子进程
- **THEN** 脚本按先父后子顺序终止它们，并在复查零残留后才继续

#### Scenario: 残留未清干净即停止
- **WHEN** 复查仍发现关联进程存活
- **THEN** 脚本停止并以非零退出码返回

### Requirement: 重启 SHALL 以进程链 CreationTime 变化为准

脚本 SHALL 记录重启前后进程链各进程的 `CreationTime` 并比对，**以时间戳确已变化为重启成功的判据**。

MUST NOT 以「已重启」之类的打印输出或 `Start-ScheduledTask` 的返回值作为重启成功的判据。

#### Scenario: CreationTime 未变判为失败
- **WHEN** 重启后进程链的 `CreationTime` 与重启前一致
- **THEN** 判为重启失败，非零退出码

#### Scenario: CreationTime 变化判为成功
- **WHEN** 重启后各进程 `CreationTime` 均晚于重启动作发起时刻
- **THEN** 该关通过

### Requirement: 验活 SHALL 以心跳时间戳刷新为准

脚本 SHALL 读取心跳文件 `5-平台底座/wecom-aibot-service/reports/aibot_liveness.json` 的 `alive_at`，并确认其**晚于本次进程启动时刻**。

MUST NOT 以「服务进程存在」作为验活判据。

心跳时间基准 SHALL 被显式处理：`alive_at` 为 UTC，比对前 MUST 统一基准，输出 MUST 同时标注 UTC 与本地时刻。

目标执行体内**存在** `5-平台底座/wecom-aibot-service` 目录时，心跳文件缺失、损坏或时间戳未刷新 MUST 判为验活失败。

目标执行体内**不存在**该服务目录时（该执行体承载的不是本服务），本关 SHALL 标记为「不适用」并如实写入摘要，MUST NOT 计为通过、MUST NOT 计为失败。

#### Scenario: 残留旧戳不算通过
- **WHEN** 心跳 `alive_at` 早于本次进程启动时刻
- **THEN** 判为验活失败，非零退出码

#### Scenario: 时间基准被显式标注
- **WHEN** 输出心跳时刻
- **THEN** 同时给出 UTC 与本地两种表示

#### Scenario: 执行体不含该服务时本关不适用
- **WHEN** 目标 worktree 内不存在 `5-平台底座/wecom-aibot-service` 目录
- **THEN** 摘要写明本关「不适用」，且不因此把整体判为通过或失败

### Requirement: 退出码 SHALL 由脚本自身给出

脚本 SHALL 以自身的 `exit <code>` 返回结果；调用方 SHALL 读取 `$LASTEXITCODE`。

MUST NOT 经由管道、`cmd /c` 或任何会在解析期展开的机制取得退出码。

任一关未通过时退出码 MUST 非零。

#### Scenario: 任一关失败即非零
- **WHEN** 九步中任一关未通过
- **THEN** 脚本以非零退出码返回，且摘要写明是哪一关

#### Scenario: 全关通过为零
- **WHEN** 全部关口通过
- **THEN** 退出码为 0，且摘要逐关列出证据

