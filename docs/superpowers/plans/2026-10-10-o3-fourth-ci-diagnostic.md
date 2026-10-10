# 根会话正式供审入口

本件仅保存未执行的具体诊断方案。配套冻结脚本位于 `docs/superpowers/plans/o3-fourth-ci-1010/generate_diagnostic_copy.py` 与 `run_diagnostic_once.py`；AST静态解析不执行脚本。运行必须本人对本计划明确授权，前三CI批准不延伸。

1. 获批后固定主仓隔离Python执行冻结生成器，保存新UUID；根核生成diff恰八个stderr标记及五闭包字节身份。
2. 随后仅一次执行冻结runner（同一UUID），180秒主超时＋各次最多5秒清理等待；可能继承原四LAN GET；新UUID原stdout/stderr仅本机保留不打印外发。
3. 进程树仅本次Windows Job Object归属；失败记录自身PID与清理状态，不全机杀进程、不清锁、不删除证据。
4. 仅诊断，不跑pytest、不修改候选或生产源、不对齐/ff；实际第四pytest节点/修复另按诊断结果供审。

---

# O3 第四 CI 节点：只读定向诊断供审稿

## 状态与边界

本目录仅保存未执行诊断方案与脚本。它不构成第四 CI 执行许可，也不扩张已批准的前三节点范围。脚本目前未运行；没有调用 pytest、状态卡、网络、队列工具或真实数据。

诊断目标是确认第四节点 `test_real_queue_reminder_equals_kanban_ps1_pool()` 卡在哪里。定向运行的是该节点所调用的状态卡 PowerShell 数据层，使用只在 ignored UUID 目录生成的诊断副本。它可以定位该真实只读脚本在 P0–P7 的耗时，不验证 pytest 断言、不冒充第四节点通过，也不证明全 O3 CI 通过。

## 已核对身份与真实执行链

候选工作树：`C:/Users/Paul Shao/.codex/worktrees/o3-recovery-fix-1006/zhuopin-ai`，HEAD `0ad830234af70585d359df23123973eceeace3a3`。当前主工作树 HEAD `28337c0ebb52afdbf61e955ecdbc22d151bcd185`。父审通过单路径只读 `Get-FileHash -Algorithm SHA256 -LiteralPath ...` 核实两树该状态卡源码及测试节点内容一致：

| 文件 | 候选 SHA-256 | 主树 SHA-256 |
|---|---|---|
| `0-学习与工具/工具-项目状态卡数据层.ps1` | `BC774E0C9965BE22981390AF7B3255525C87B07038ECB87E2CAB46FDF34A35DF` | 相同 |
| `5-平台底座/wecom-aibot-service/tests/test_open_pool_alignment.py` | `4990DDB836775D92DA18FC41998271FA77DDC5AF2BFCE305D30A18A77DAFB360` | 相同 |

节点为 `test_real_queue_reminder_equals_kanban_ps1_pool()`。`.github/workflows/ci.yml` 的 `test` job 用 `matrix.project` 设 `working-directory`，执行 `python -m pytest -q --tb=short --junit-xml=pytest-result.xml`。矩阵由 `0-学习与工具/工具-CI矩阵发现.py` 根据已跟踪测试文件推导；`wecom-aibot-service/tests/test_open_pool_alignment.py` 的项目根是 `5-平台底座/wecom-aibot-service`，故第四节点 CI cwd 为仓库根下该目录。测试选 PowerShell 时先 `pwsh`、再 `powershell`；子进程继承该 cwd；用 `[Console]::OutputEncoding=[System.Text.Encoding]::UTF8` 调用仓库脚本，`capture_output=True`、UTF-8 `errors="replace"`，超时 `180` 秒；只解析 stdout 中 `@@JSON@@`。状态卡自身 stdout 契约是一行 `@@JSON@@` + 压缩 JSON。

已确认状态卡的数据访问链：P1 读取两份队列文件并解析；P2 扫描路线图中的派单/周计划 opener；P3 从 PATH 找 `python`/`py`，运行同目录 `工具-可Open池.py --repo-root C:\Dev\zhuopin-ai --json-b64`；P4 读取并汇总 `reports/sweep-commit.log`；P5 执行 `git -C C:\Dev\zhuopin-ai log -10 ...`；P6 执行 `Get-NetIPAddress -AddressFamily IPv4`，仅本机在 `192.168.100.*` 网段时向原有 `192.168.100.51:8091–8094/api/ping` 各发一个最多 3 秒 GET；P7 生成 JSON stdout。脚本声明只读，stdout 与这些原分支/请求/错误处理保持不变。

环境事实：父审已实测 bundled PowerShell 7.6.5 与 Windows PowerShell 5.1.26100.9549 可执行文件版本。后续 runner 将记录本次实际选中的路径/版本；不预设 PATH 选择结果。

## P0–P7 标记副本

`generate_diagnostic_copy.py` 只读候选源码与测试节点，要求 HEAD 与两份 SHA 均匹配；对状态卡每个唯一锚点插入一条仅写 stderr 的 UTC 时间标记。锚点依次位于：硬编码 `$root` 行之前；`$queue=Get-Content ... $pq` 之前；路线图 opener `foreach($hl...)` 之前；`$pyOut=@(& $pyExe...)` 之前；sweep log 读取之前；`git log` 之前；`Get-NetIPAddress` 之前；在 `@@JSON@@` 的 `Write-Output` 行之后。P7 表示 JSON 序列化并写出已完成；找不到或重复命中任何锚点时拒绝生成。

每条标记只包含 `O3_DIAG|Pn|UTC 时间|父 PID`；P0 另记录 PowerShell 版本，P3 记录解析出的 `$pyExe`。它们写到 stderr，不触碰 stdout。诊断 PowerShell 副本位于 UUID 下 `0-学习与工具/工具-项目状态卡数据层.ps1`，与 helper `0-学习与工具/工具-可Open池.py` 保持原目录关系，使 `$PSScriptRoot` 仍指向其所属工具目录；脚本调用 helper 的相对路径因此保持有效。helper 的 `_SEARCH_ROOT = Path(__file__).resolve().parents[1]`，只复制 helper 会把平台 import 根改到 `runs/`，不成立；因此生成器在 UUID 下按原始相对布局逐字节复制最小 import 闭包：`0-学习与工具/工具-可Open池.py`、`5-平台底座/zhuopin_platform/zhuopin_platform/__init__.py`、`shared_tools/__init__.py`、`shared_tools/open_pool.py`、`shared_tools/queue_table.py`。已静态读过这五份文件的 import 与 `Path(__file__)` 使用：`open_pool.py` 只 import `queue_table.py`；二者只用标准库与相互依赖；包 `__init__` 无额外 import；这组布局使 helper 计算的 `_PLATFORM_PATH` 正好指向复制的包，不依赖全局 editable 安装。复制源路径/hash 写入 manifest；各文件候选与主树必须相同，且输出全部在 ignored UUID。生成器保存各源/副本 SHA、诊断副本 SHA 和 unified diff，便于核实主脚本 diff 只有八条标记、每个闭包文件逐字节一致。

## 未执行 runner 计划与副作用

`run_diagnostic_once.py` 只接受生成器创建的 UUID 目录。它复核候选 HEAD、测试节点 SHA、原状态卡 SHA、五文件 P3 import 闭包 SHA、诊断副本 SHA、UUID 路径及 ignored 状态。执行命令与节点内层调用一致：按 `pwsh` → `powershell` 选择；`-NoProfile -ExecutionPolicy Bypass -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; & '<diagnostic copy>'"`；`CreateProcessW` 的 cwd 固定为 `C:/Users/Paul Shao/.codex/worktrees/o3-recovery-fix-1006/zhuopin-ai/5-平台底座/wecom-aibot-service`，与 CI matrix 项目目录等价；唯一超时为 180 秒。runner 不依赖调用者 cwd，cwd 写入结果元数据。

runner 不运行 pytest 节点，不产生 CI pass/fail 结论。它保存 stdout/stderr 原始字节、shell 命令、cwd、开始/结束 UTC、墙钟耗时、退出码/超时状态、runner Python 路径与版本、PowerShell 可执行路径/版本、P3 解析到的 Python 路径及其 Windows PE 版本资源（不另启 Python 进程）、父 PID 与 Windows Job Object 中观察到的成员 PID，以及 P0–P7 的标记与相邻阶段耗时。若解释器无 PE 版本资源则明确记 null。stdout 可能包含工作数据，所有运行产物都留在该 ignored UUID 目录，runner 不向终端打印正文，只打印 UUID 路径和不含正文的摘要。

UUID 目录只可运行一次：runner 先用 `O_CREAT|O_EXCL` 原子创建 `.runner-claimed`，拒绝已有 claim/输出/metadata；状态 manifest 从 `prepared` 更新为 `claimed`，`stdout.bin`/`stderr.bin` 以 Win32 `CREATE_NEW` 创建，禁止 `CREATE_ALWAYS` 覆盖。两个日志 handle 在同一个受保护的 `try/finally` 生命周期内创建并先置空；若第二个创建失败，异常记录尽力写入 metadata，且 finally 仍关闭已创建的第一个 handle。进程启动使用 Windows `CREATE_SUSPENDED`，先创建仅本次的 Job Object 并设置 `KILL_ON_JOB_CLOSE`，再将 suspended PowerShell 进程加入 Job，最后恢复执行。任一步不能创建/设置/赋值 Job 时，在脚本开始前仅对精确 suspended PID 调 `TerminateProcess` 并用有界 5 秒等待检查该 process handle 是否 signaled；失败时把 PID/WinError/未确认状态写进 ignored metadata，不转为全机查杀。恢复后遇异常只对确切 Job 调 `TerminateJobObject`；Job 关闭后的存活确认等待同样最多 5 秒。180 秒主超时只调用 `TerminateJobObject` 清理明确加入此 Job 的树；每次清理等待均有界为 5 秒，不使用无限等待，未确认时记录该 Job/PID 观察集并 fail closed。异常路径尽力记录清理和 handle 关闭失败；metadata 写入失败作为附加证据错误记录，不得遮蔽原始异常或跳过进程/handle 清理。任何进程启动后的异常都保留增量生命周期 metadata、PID和日志。P3 导入可能生成的 `__pycache__` 也被限制在 UUID 副本包目录。若归属不可证明，不运行或不清理全机进程，保留证据并报告失败。关闭 Job 句柄只影响本次已加入的成员。

P6 的四个 LAN GET 是原状态卡既有行为，本诊断没有加端口/路径/重试或业务请求。即使运行也可能在原条件下对 `192.168.100.51` 发送四个只读 ping GET；本准备没有发送请求。队列文件、sweep 日志、项目文档和 IP 信息由原脚本读取；stdout 原始文件留在本机 ignored 路径，不外发、不显示。

## 执行前批准与验收

需 Shao Peishen 对“在 CI 等价 cwd 执行一次上述状态卡诊断，可能触发原 LAN ping GET，并在 ignored UUID 目录保存原 stdout/stderr”的**本次执行**作具体授权。前三节点既有批准不包含该项。授权后先生成副本并检查 diff 只有 stderr 标记；再执行一次 runner。验收只确认：身份复核通过、脚本完成或产生 180 秒超时证据、P0–P7 中已到达的标记有时间、原 stdout `@@JSON@@` 结构仍存在（如脚本正常结束），不评价 pytest 断言，不改生产源、不重跑测试、不清理旧树/锁/临时目录。要真正执行第四 pytest node，另需单独范围批准并设计一个能让原 node 调用诊断副本而不改测试语义的隔离方法；此稿不声称已解决该替换接线。

## 未闭合点

此轮未读真实队列/日志数据，也未运行 PowerShell/Python/pytest或网络请求。候选与主树源码哈希相同是源身份核验，不证明先前 CI 的 runner、cwd、PATH 或外部状态相同。标记副本/runner尚未执行验证；Windows Job API实现需代码审查，任何 ctypes/API 结构错误均必须导致执行前失败关闭。未授权前不得运行。
