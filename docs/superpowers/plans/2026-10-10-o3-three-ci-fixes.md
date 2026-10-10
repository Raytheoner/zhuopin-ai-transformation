# O3 前三项 CI 修复实施计划

> **For agentic workers:** 执行采用 subagent-driven-development 或 executing-plans，须先取得本计划所列修改与验证的具体批准；当前只交付计划。

**Goal:** 在现有恢复候选中修复三处 CI 局部行为并保留所有原失败证据。

**Architecture:** 保持锁 helper 与生产门禁协议。仅规范成功扫描后的数组投影、隔离测试进程计数和精确 Gate 行断言。

**Tech Stack:** 项目隔离 Python/pytest、PowerShell 7.6.5、Windows PowerShell 5.1。

**Spec:** 已批准 O3 intent/design/18路径计划及两项已验收恢复；本增量以三处静态证据为依据，第四节点另审。

**Review Focus:** 0/1 git 进程；有效空集合；扫描异常；含2b的短SHA；中断后自建fixture/PID清理，逐一由下文用例或停止规则覆盖。

日期：2026-10-10  
状态：供审；尚非代码修改、测试执行、CI豁免或发布授权。  
范围：仅前三个已知 CI 节点。aibot 状态卡180秒超时是单独的后续诊断问题，不在本稿，不承诺四CI全绿。

## 1. 基线与批准沿用

沿用已批准的 O3 business intent、design、18路径计划，以及已完成并验收的两项技术恢复。原失败矩阵、失败日志和封包保留；四CI仍是单独的发布阻断，不能以本稿或单测通过销项。

父审通过正常只读路径补证了现有恢复候选：`C:\Users\Paul Shao\.codex\worktrees\o3-recovery-fix-1006\zhuopin-ai` 的 HEAD 是 `0ad830234af70585d359df23123973eceeace3a3`；父审对下列拟改三件、锁判定 helper、产品执行体PS1共五件的 `git status --short` 复核为空。该证据解除此前“候选版本无法读取”的暂时限制。此前失败批不能替代这个候选树上的验证。

父审另核：该候选 `test_工具-执行体对齐重启.py:195–196` 仍有短SHA子串断言；产品PS1的 `Write-Gate` 输出固定为 `[{Verdict}] {Gate} —— ...`，本节点Gate实际名为 `2b 进程新鲜度`。bundled PowerShell 7.6.5 路径为 `C:\Users\Paul Shao\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe`；Windows PowerShell 5.1 路径为 `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`，版本 `5.1.26100.9549`。上述是父审静态/版本核验；本稿未运行测试。

## 2. 精确候选修改范围

仅申请以下三个文件；不改锁helper、产品执行体PS1、aibot代码、正式OpenSpec、队列、runtime或CI配置。

1. `0-学习与工具/工具-worktree体检.ps1`：只规范成功锁扫描后的留痕字段 `locks_clearable`，显式输出合法数组。保持清理判据、锁判定调用、删除行为、失败传播均不变。
2. `0-学习与工具/test_工具-worktree体检.py`：通过测试调用作用域内的 `Get-Process` 函数mock注入Git进程数0/1，覆盖CLI清理门槛和空/非空留痕数组；保留现有helper函数测试，不增加生产参数、不杀宿主git进程。
3. `0-学习与工具/test_工具-执行体对齐重启.py`：将目标负例的整个stdout子串断言改为精确ASCII gate行matcher；新增纯文本matcher正/负例，至少包含短HEAD文本 `HEAD=eb1102b`；保留现有正例rc与PID断言。

八路径只读核查清单不转为修改白名单。任何需要修改第四件、增加生产参数、改变锁清理规则或调整门禁的证据均停下另审。

## 3. 节点设计

### 3.1 `test_ClearStaleLocks只删三条齐备的`

**证据与目标。** 旧配对显示锁未被清理；共享helper已有 `GitProcessCount` 参数和相应单测，但worktree CLI调用接线用宿主真实 `Get-Process git`，导致集成测试对全机瞬时状态敏感。本修复不把历史失败归因为某个未留存的Git进程数；目标是让集成用例确定性验证原有0/非0两种语义。

**测试设计。** 新增测试私有的 `_run_with_mock_git_process_count(repo, count, *args)`，通过 `pwsh -NoProfile -Command` 启动fixture内的目标脚本。命令作用域先定义同名 `Get-Process` 函数：`-Name git` 时只返回指定数量的合成对象；非git参数转交 `Microsoft.PowerShell.Management\Get-Process`。计数与调用哨兵留在该独立PowerShell子进程的global scope（不影响父shell）。随后用调用运算符 `& <fixture目标脚本>` 执行 `工具-worktree体检.ps1 -Repo <tmp_path/repo> ...`，执行结束后断言mock调用哨兵大于0。

PowerShell子脚本通过动态作用域查找当前命令会话中可见的函数；函数优先于同名cmdlet，因而目标脚本中既有 `Get-Process git` 语句会走测试mock。每次测试都在**独立pwsh子进程**中定义mock；不会改写共享shell函数、注册系统mock、改生产源码或终止宿主git进程。哨兵断言防止测试因作用域未传入而静默退回宿主真实进程列表。

**用例与验收。**

- count=0：临时仓库中45分钟、0字节的 `stale.lock` 可清；5分钟的 `fresh.lock` 与45分钟但非0字节的 `inuse.lock` 均保留。只删除fixture锁文件。
- count=1：同样的陈旧零字节 `stale.lock` 仍保留；不得出现“已清”，另外两锁仍保留。
- 既有纯helper用例保持并继续检查年龄、字节数、注入进程数三条件AND；没有加参数或削弱清理判定。

### 3.2 `test_留痕带锁扫描字段` / null到数组

**证据与目标。** 已读helper在成功扫描后返回有效Locks集合和GitProcessCount；record管道对空输出直接赋值会变成null。根因不是helper扫描错误。修复仅规范留痕投影，不把扫描失败翻译成“没有可清锁”。

**产品改法。** 在 `工具-worktree体检.ps1` 既有成功扫描的record构造点，仅从其现有可清集合投影record字段；不新增扫描守卫、失败兜底或helper改动，例如在既有record构造点使用带数组上下文的 `[string[]]@($clearableLocks | ForEach-Object { $_.path })`。变量必须来自已成功、形状有效的扫描结果；不要用 `@($null)`、`?? @()` 或catch后空数组兜底去吞扫描异常。删除逻辑继续使用原对象/判据，不从新格式化的record字段反推清理动作。

**用例与验收。**

- valid scan + count=1，或有效扫描得到空可清集合：jsonl中的 `locks_clearable` 必须是空数组 `[]`，而非null；测试解析JSON并断言它是list且为空。
- valid scan + count=0且仅有陈旧零字节锁：字段为单元素数组 `['stale.lock']`。
- 注入扫描失败：命令保留既有失败行为；不得产出一个表示成功且 `locks_clearable=[]` 的正常record。若现有扫描失败路径无法在这三文件内区分“扫描失败”与“成功空集合”，停下另审，不能扩改helper或新增状态。
- 不加 `-ClearStaleLocks` 的字段测试不得删fixture锁；加清理开关的第3.1测试只删除fixture内唯一满足三条件的锁。

### 3.3 `ProcessFreshnessTests::test_落后大于0_路径不变_干跑退出0`

**证据与目标。** 父审确认 `0ad830…` 中目标测试仍用 `assertNotIn("2b", stdout)`；随机短HEAD `eb1102b` 因含字符子串而误命中。产品gate协议已经核实，Gate字段为 `2b 进程新鲜度`，完整行形式为 `[{Verdict}] {Gate} —— ...`。

**测试改法。** 在同一个测试文件定义并使用纯文本predicate，仅匹配完整gate行。候选正则：

```python
_TWO_B_GATE = re.compile(r"(?m)^\[[^\]\r\n]+\] 2b 进程新鲜度 —— [^\r\n]*$")

def _has_two_b_gate(stdout: str) -> bool:
    return _TWO_B_GATE.search(stdout) is not None
```

在原负例用 `assertFalse(_has_two_b_gate(r.stdout), r.stdout)` 取代整个stdout上的宽泛 `assertNotIn("2b", ...)`。新增matcher级纯文本用例：短SHA行如 `HEAD=eb1102b` 不匹配；符合 `[{Verdict}] 2b 进程新鲜度 —— ...` 的真实格式匹配；其他Gate名称不匹配。原有进程新/旧的正例退出码和 `pid=<pid>` 断言原样保留，不将仅有字母子串当作正例契约。

## 4. 批准后的验证节点与隔离副作用

执行前只读确认既有候选HEAD仍等于 `0ad830234af70585d359df23123973eceeace3a3`，且候选仅有本稿授权的三文件差异；不新建/切换worktree，不对齐main、不提交、不推送。运行环境固定为项目隔离Python `C:\Dev\Codex\runtimes\zhuopin-ai\venv\Scripts\python.exe`，从候选worktree根执行；使用新的UUID目录 `C:\Dev\zhuopin-ai\reports\o3-ci-plan-1010\verify-<UUID>\` 保存JUnit和basetemp，使用 `-B`、`-p no:cacheprovider` 防止pyc/pytest cache写回候选树。测试fixture临时根设置到该basetemp，结束后保留报告目录，不自动清理既有历史目录。

### PowerShell 7.6.5：锁定向测试

执行前创建主仓ignored报告目录 `C:\Dev\zhuopin-ai\reports\o3-ci-plan-1010\verify-<UUID>\`；JUnit放该目录，`--basetemp` 指向其 `basetemp` 子目录。执行时从候选worktree根运行，PATH前置已核实的PowerShell 7目录，使测试的 `shutil.which("pwsh")` 命中该版本；TEMP/TMP设为新basetemp。PATH/TEMP/TMP只在当前PowerShell命令作用域覆盖并在 `finally` 恢复。按下方精确test nodes选择，不跑整个测试文件：

- `0-学习与工具/test_工具-git锁诊断.py::test_陈旧_零字节_无进程_三条齐备才clearable`
- `0-学习与工具/test_工具-git锁诊断.py::test_未过阈值_不clearable`
- `0-学习与工具/test_工具-git锁诊断.py::test_非零字节_不clearable`
- `0-学习与工具/test_工具-git锁诊断.py::test_有git进程_不clearable`
- `0-学习与工具/test_工具-git锁诊断.py::test_无锁文件_locks为空`
- `0-学习与工具/test_工具-worktree体检.py::test_ClearStaleLocks只删三条齐备的`（mock count=0）
- 新增 `0-学习与工具/test_工具-worktree体检.py::test_ClearStaleLocks有git进程时保留`（mock count=1）
- `0-学习与工具/test_工具-worktree体检.py::test_留痕带锁扫描字段`（mock count=0，非空数组）
- 新增 `0-学习与工具/test_工具-worktree体检.py::test_留痕空可清锁集合序列化为空数组`（mock count=1，空数组）
- 新增 `0-学习与工具/test_工具-worktree体检.py::test_锁扫描失败不记录为空数组`（mock失败，保持失败闭合）

锁helper现有测试在 `tmp_path` 建小仓库/锁文件，并显式传 `GitProcessCount`；worktree集成测试也只传临时 `-Repo`。mock处理确保不读取全机git进程。每个fixture和jsonl仅在pytest basetemp下创建；`-ClearStaleLocks`仅删fixture内的 `stale.lock`。不触碰共享队列/runtime/真实工作树/宿主git进程。完整运行命令如下，十个node逐项列出：

```powershell
$ErrorActionPreference = 'Stop'
$oldPath, $oldTemp, $oldTmp = $env:PATH, $env:TEMP, $env:TMP
$oldLocation = Get-Location
$run = Join-Path 'C:\Dev\zhuopin-ai\reports\o3-ci-plan-1010' ('verify-' + [guid]::NewGuid().ToString('N'))
if (Test-Path -LiteralPath $run) { throw "run path already exists: $run" }
$reportRoot = [System.IO.Path]::GetFullPath('C:\Dev\zhuopin-ai\reports\o3-ci-plan-1010')
$resolvedRun = [System.IO.Path]::GetFullPath($run)
if (-not $resolvedRun.StartsWith($reportRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'run path is outside approved report root' }
New-Item -ItemType Directory -Path $run | Out-Null
$bt = Join-Path $run 'basetemp'
New-Item -ItemType Directory -Path $bt | Out-Null
$junit = Join-Path $run 'junit-locks.xml'
$lockNodes = @(
    '0-学习与工具/test_工具-git锁诊断.py::test_陈旧_零字节_无进程_三条齐备才clearable',
    '0-学习与工具/test_工具-git锁诊断.py::test_未过阈值_不clearable',
    '0-学习与工具/test_工具-git锁诊断.py::test_非零字节_不clearable',
    '0-学习与工具/test_工具-git锁诊断.py::test_有git进程_不clearable',
    '0-学习与工具/test_工具-git锁诊断.py::test_无锁文件_locks为空',
    '0-学习与工具/test_工具-worktree体检.py::test_ClearStaleLocks只删三条齐备的',
    '0-学习与工具/test_工具-worktree体检.py::test_ClearStaleLocks有git进程时保留',
    '0-学习与工具/test_工具-worktree体检.py::test_留痕带锁扫描字段',
    '0-学习与工具/test_工具-worktree体检.py::test_留痕空可清锁集合序列化为空数组',
    '0-学习与工具/test_工具-worktree体检.py::test_锁扫描失败不记录为空数组'
)
$pytestExit = $null
try {
    Set-Location 'C:\Users\Paul Shao\.codex\worktrees\o3-recovery-fix-1006\zhuopin-ai'
    $env:PATH = 'C:\Users\Paul Shao\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell;' + $oldPath
    $env:TEMP = $bt; $env:TMP = $bt
    & 'C:\Dev\Codex\runtimes\zhuopin-ai\venv\Scripts\python.exe' -B -m pytest -q -ra -p no:cacheprovider --basetemp $bt --junitxml $junit @lockNodes 1> (Join-Path $run 'stdout.log') 2> (Join-Path $run 'stderr.log')
    $pytestExit = $LASTEXITCODE
} finally {
    $env:PATH = $oldPath; $env:TEMP = $oldTemp; $env:TMP = $oldTmp
    Set-Location -LiteralPath $oldLocation.Path
}
if ($pytestExit -ne 0) { throw "targeted pytest failed: $pytestExit" }
[xml]$junitXml = Get-Content -LiteralPath $junit -Raw
$suites = $junitXml.SelectNodes('//testsuite')
if ($suites.Count -eq 0) { throw 'JUnit has no testsuite' }
$totalTests, $totalSkipped, $totalFailures, $totalErrors = 0, 0, 0, 0
foreach ($suite in $suites) {
    $totalTests += [int]$suite.tests
    $totalSkipped += [int]$suite.skipped
    $totalFailures += [int]$suite.failures
    $totalErrors += [int]$suite.errors
}
if ($totalTests -ne 10 -or $totalSkipped -ne 0 -or $totalFailures -ne 0 -or $totalErrors -ne 0) {
    throw "JUnit mismatch: tests=$totalTests skipped=$totalSkipped failures=$totalFailures errors=$totalErrors"
}
```

### Windows PowerShell 5.1：matcher与短SHA回归

前置PATH指向已核实的 `C:\Windows\System32\WindowsPowerShell\v1.0`，令 `shutil.which("powershell.exe")` 命中版本 `5.1.26100.9549`；PATH/TEMP/TMP作用域临时覆盖并恢复。仅运行：

- 新增 `0-学习与工具/test_工具-执行体对齐重启.py::test_2b_gate_matcher精确识别完整Gate行`（纯文本、不起进程）。
- `0-学习与工具/test_工具-执行体对齐重启.py::ProcessFreshnessTests::test_落后大于0_路径不变_干跑退出0`（目标真实fixture路径回归）。
改动保持原有正例rc/PID断言不变；matcher级纯文本测试覆盖真实Gate格式匹配与短SHA/其他Gate不匹配。本批只执行上列两个精确node，不猜测或补列未由父审确认的其他正例node名称。若供审人要求同时重跑其余正例，须先静态确认确切node ID，再另行补充验证命令与进程副作用，不从本稿推定。

matcher纯文本测试不启动子进程。ProcessFreshness目标用例会在TMP/TEMP重定向到新basetemp后建立临时Git repo、detached worktree和 `.env`，启动一个测试自建的 `powershell.exe Start-Sleep -Seconds 600` carrier；产品脚本以 `-DryRun` 针对该临时Repo/Worktree执行。正常 `tearDown` 只杀/wait该测试保存的Popen PID，并 `git worktree remove --force` 后删自己的 `TemporaryDirectory`。测试基于精确PID清理，不按名称/全局筛选杀进程。若pytest被强制中断，carrier可能留到600秒；此时停止后续运行，只能按该测试日志/测试进程PID定向处理，不运行通配清理。真实用户worktree、计划任务、队列和runtime不作写入。

目标测试后要求 `passed`、`skipped=0`；未解析到对应PowerShell版本或产生skip时该次验证无效，不得记通过。每个批次保存JUnit和stdout/stderr；报告目录保留不自动删除。

### 不包含的第四节点与完整矩阵

第四节点 `test_real_queue_reminder_equals_kanban_ps1_pool` 的状态卡没有fixture root。父审静态核对表明它直接调用硬编码主仓脚本，读取真实主仓队列/资料、启动PATH解析的Python子进程、读取git log与网卡地址，并可能对LAN `.51` 四端口发GET；因此本稿不运行、不采样，也不推测其180秒超时根因。另做安全分阶段采样设计需要独立提案与精确授权。本稿也不含原baseline/replay完整矩阵、其他项目测试、主仓对齐、ff、发布准备、部署/.51/外发或业务验收。前三节点定向测试全绿只验证这三处局部行为，不能宣布四CI解除。

## 5. 最窄待裁决项

请只裁决是否批准：在现有 clean `0ad830…` 隔离候选中，仅改上述三文件，并执行第4节列出的前三节点定向验证；副作用限于ignored报告验证目录、测试自建fixture，以及短SHA测试自建/自行清理的单个 `Start-Sleep` 子进程。此批准不含第四个aibot节点、不含完整CI矩阵或发布/合并/部署。已批准O3 intent/design/18路径计划和两项已验收技术恢复均不重问。

若不批准含短时子进程的短SHA目标回归，可只批前三文件设计中的锁节点修改和锁定向测试；短SHA matcher纯文本测试可独立验证，但不能以它替代真实目标回归，也不能把候选0ad原失败节点称为已通过。

### Windows PowerShell 5.1 完整命令

此批创建全新的ignored验证目录，不复用/覆盖任何历史验证目录；显式创建basetemp，避免把未创建路径作为TEMP/TMP。PATH/TEMP/TMP仅在当前PowerShell作用域内覆盖并在finally恢复。目录与JUnit保留，不自动删除。

```powershell
$ErrorActionPreference = 'Stop'
$oldPath, $oldTemp, $oldTmp = $env:PATH, $env:TEMP, $env:TMP
$oldLocation = Get-Location
$run = Join-Path 'C:\Dev\zhuopin-ai\reports\o3-ci-plan-1010' ('verify-' + [guid]::NewGuid().ToString('N'))
if (Test-Path -LiteralPath $run) { throw "run path already exists: $run" }
$reportRoot = [System.IO.Path]::GetFullPath('C:\Dev\zhuopin-ai\reports\o3-ci-plan-1010')
$resolvedRun = [System.IO.Path]::GetFullPath($run)
if (-not $resolvedRun.StartsWith($reportRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'run path is outside approved report root' }
New-Item -ItemType Directory -Path $run | Out-Null
$bt = Join-Path $run 'basetemp'
New-Item -ItemType Directory -Path $bt | Out-Null
$junit = Join-Path $run 'junit-process-freshness.xml'
$pytestExit = $null
try {
    Set-Location 'C:\Users\Paul Shao\.codex\worktrees\o3-recovery-fix-1006\zhuopin-ai'
    $env:PATH = 'C:\Windows\System32\WindowsPowerShell\v1.0;' + $oldPath
    $env:TEMP = $bt; $env:TMP = $bt
    & 'C:\Dev\Codex\runtimes\zhuopin-ai\venv\Scripts\python.exe' -B -m pytest -q -ra -p no:cacheprovider --basetemp $bt --junitxml $junit '0-学习与工具/test_工具-执行体对齐重启.py::test_2b_gate_matcher精确识别完整Gate行' '0-学习与工具/test_工具-执行体对齐重启.py::ProcessFreshnessTests::test_落后大于0_路径不变_干跑退出0' 1> (Join-Path $run 'stdout.log') 2> (Join-Path $run 'stderr.log')
    $pytestExit = $LASTEXITCODE
} finally {
    $env:PATH = $oldPath; $env:TEMP = $oldTemp; $env:TMP = $oldTmp
    Set-Location -LiteralPath $oldLocation.Path
}
if ($pytestExit -ne 0) { throw "targeted pytest failed: $pytestExit" }
[xml]$junitXml = Get-Content -LiteralPath $junit -Raw
$suites = $junitXml.SelectNodes('//testsuite')
if ($suites.Count -eq 0) { throw 'JUnit has no testsuite' }
$totalTests, $totalSkipped, $totalFailures, $totalErrors = 0, 0, 0, 0
foreach ($suite in $suites) {
    $totalTests += [int]$suite.tests
    $totalSkipped += [int]$suite.skipped
    $totalFailures += [int]$suite.failures
    $totalErrors += [int]$suite.errors
}
if ($totalTests -ne 2 -or $totalSkipped -ne 0 -or $totalFailures -ne 0 -or $totalErrors -ne 0) {
    throw "JUnit mismatch: tests=$totalTests skipped=$totalSkipped failures=$totalFailures errors=$totalErrors"
}
```

## 6. 独立文档审查消费

Luna只读复核指出数组未定义、skip未强制、输出日志未落盘及matcher字段不完整四项；已补精确node数组、JUnit10/2且零skip/failure/error、stdout/stderr独立文件、完整Gate字段/分隔符。未以文档复核替代产品执行结果。

## 7. 逐文件实施步骤与可直接使用的内容（待批准，未执行）

### Task 1：失败用例与测试私有mock

文件：仅test_工具-worktree体检.py。沿现有repo/TOOL/_touch_lock，保留其他测试与helper，添加下列函数并替换两个目标测试。Step1写入测试；Step2只执行第4节十个PS7 node，empty数组应在旧record上失败；Step3修改Task2单处投影；Step4重复同一批准命令并核JUnit10/0。这里的代码仅为计划内容，未写进测试文件。

Mock计数哨兵采用该独立pwsh子进程的global scope，避免script scope随被调用脚本改变；不触碰父shell/全局机器环境。其他参数转发真实cmdlet，只有-Name git在该fixture中合成。

```python
def _ps_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _run_with_mock_git_process_count(
    repo: Path, count: int, *, clear: bool = False, fail: bool = False
):
    if count not in (0, 1):
        raise ValueError("this fixture only permits count 0 or 1")
    ps = "\n".join([
        "$ErrorActionPreference = 'Stop'",
        "$global:O3CiMockSeen = 0",
        "$global:O3CiMockCount = " + str(count),
        "$global:O3CiMockFail = " + ("$true" if fail else "$false"),
        r"""
function Get-Process {
    [CmdletBinding()]
    param([string[]]$Name)
    if ($Name.Count -eq 1 -and $Name[0] -eq 'git') {
        $global:O3CiMockSeen += 1
        if ($global:O3CiMockFail) { throw 'O3 synthetic lock scan failure' }
        for ($i = 0; $i -lt $global:O3CiMockCount; $i++) {
            [pscustomobject]@{ Id = 990000 + $i; ProcessName = 'git' }
        }
        return
    }
    Microsoft.PowerShell.Management\Get-Process @PSBoundParameters
}
try {
""",
        "& " + _ps_literal(str(TOOL))
        + " -Repo " + _ps_literal(str(repo))
        + " -StaleLockMinutes 30 -ClearStaleLocks:"
        + ("$true" if clear else "$false"),
        r"""
} finally {
    if ($global:O3CiMockSeen -lt 1) {
        throw 'O3 mock was not called; host fallback is forbidden'
    }
    Write-Output ('__O3_CI_MOCK_CALLS=' + $global:O3CiMockSeen)
}
""",
    ])
    return subprocess.run(
        ["pwsh", "-NoProfile", "-Command", ps],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def _lock_trace_rows(repo: Path):
    rows = []
    for trace in sorted((repo / "reports" / "worktree-guard").glob("*.jsonl")):
        rows.extend(
            json.loads(line)
            for line in trace.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    return rows


def test_ClearStaleLocks只删三条齐备的(repo: Path):
    _touch_lock(repo, "stale.lock", age_minutes=45, size_bytes=0)
    _touch_lock(repo, "fresh.lock", age_minutes=5, size_bytes=0)
    _touch_lock(repo, "inuse.lock", age_minutes=45, size_bytes=8)
    result = _run_with_mock_git_process_count(repo, 0, clear=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "__O3_CI_MOCK_CALLS=" in result.stdout
    assert "已清 stale.lock" in result.stdout
    assert not (repo / ".git" / "stale.lock").exists()
    assert (repo / ".git" / "fresh.lock").exists()
    assert (repo / ".git" / "inuse.lock").exists()


def test_ClearStaleLocks有git进程时保留(repo: Path):
    _touch_lock(repo, "stale.lock", age_minutes=45, size_bytes=0)
    _touch_lock(repo, "fresh.lock", age_minutes=5, size_bytes=0)
    _touch_lock(repo, "inuse.lock", age_minutes=45, size_bytes=8)
    result = _run_with_mock_git_process_count(repo, 1, clear=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "__O3_CI_MOCK_CALLS=" in result.stdout
    assert "已清 stale.lock" not in result.stdout
    for name in ("stale.lock", "fresh.lock", "inuse.lock"):
        assert (repo / ".git" / name).exists()


def test_留痕带锁扫描字段(repo: Path):
    _touch_lock(repo, "stale.lock", age_minutes=45)
    result = _run_with_mock_git_process_count(repo, 0)
    assert result.returncode == 0, result.stdout + result.stderr
    rows = _lock_trace_rows(repo)
    assert rows[-1]["locks_total"] == 1
    assert rows[-1]["locks_clearable"] == ["stale.lock"]
    assert (repo / ".git" / "stale.lock").exists()


def test_留痕空可清锁集合序列化为空数组(repo: Path):
    _touch_lock(repo, "stale.lock", age_minutes=45)
    result = _run_with_mock_git_process_count(repo, 1)
    assert result.returncode == 0, result.stdout + result.stderr
    value = _lock_trace_rows(repo)[-1]["locks_clearable"]
    assert isinstance(value, list) and value == []
    assert (repo / ".git" / "stale.lock").exists()


def test_锁扫描失败不记录为空数组(repo: Path):
    _touch_lock(repo, "stale.lock", age_minutes=45)
    result = _run_with_mock_git_process_count(repo, 0, fail=True)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "__O3_CI_MOCK_CALLS=" in result.stdout
    assert _lock_trace_rows(repo) == []
    assert (repo / ".git" / "stale.lock").exists()

```

### Task 2：成功扫描后的record投影

文件：仅工具-worktree体检.ps1。将现有record字段表达式替换为以下行；锁helper、clearable判据、删除调用和异常传播均不改。成功空集合必须序列化[]，不是null。若失败用例表明原扫描异常被吞，停止另审；本计划不准扩改helper。

```powershell
locks_clearable = [string[]]@($clearableLocks | ForEach-Object { $_.path })
```

### Task 3：完整Gate字段matcher

文件：仅test_工具-执行体对齐重启.py。加入下列predicate/纯文本测试，把原目标方法中的assertNotIn("2b", r.stdout)替成self.assertFalse(_has_two_b_gate(r.stdout), r.stdout)，保留其rc/PID等其他断言。先跑第4节两个PS5 node，添加matcher用例后再改目标宽泛断言，再用同一命令复核JUnit2/0；不运行额外节点。

```python
import re

_TWO_B_GATE = re.compile(
    r"(?m)^\[[^\]\r\n]+\] 2b 进程新鲜度 —— [^\r\n]*$"
)


def _has_two_b_gate(stdout: str) -> bool:
    return _TWO_B_GATE.search(stdout) is not None


def test_2b_gate_matcher精确识别完整Gate行():
    assert not _has_two_b_gate("HEAD=eb1102b\n")
    assert not _has_two_b_gate("[OK] 2b arbitrary log\n")
    assert not _has_two_b_gate("[OK] 2c 进程新鲜度 —— pid=42\n")
    assert _has_two_b_gate("[OK] 2b 进程新鲜度 —— pid=42\n")

```

### Task 4：review与登记

完成获准节点后保存同候选HEAD/三文件diff/12节点JUnit及stdout/stderr，做一次Luna独立只读review；更新承接记录和§二，交CommitSweep。不得手工合并/ff/推送或把四CI整体标绿；第四状态卡节点仍另审。

