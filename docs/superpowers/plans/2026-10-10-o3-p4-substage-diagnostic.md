# O3 第四 CI 状态卡诊断：P4 子阶段标记方案

**状态：** 正式具体供审计划；未获新一轮诊断授权。不得运行本方案脚本、PowerShell 状态卡或 pytest。

**目标：** 对已经一次执行并在 P4 区间超时的 O3 状态卡诊断，准备一个新的 180 秒只读诊断入口，仅在原 P4 区段边界新增 stderr 时间标记，以区分日志读取、运行头解析、分类和聚合耗时。

**架构：** 复用已获准的一次诊断执行逻辑、P0–P7 标记、源身份、CI 等价 cwd、LAN 条件探测、Windows Job Object 进程归属和定向清理。新生成器仅向新 ignored UUID 副本插入五个 P4 子阶段标记；新 runner 仅扩展标记解析、检查新标记身份并汇总阶段间隔，不变更进程启动和超时路径。

**技术栈：** Python 标准库（`argparse`, `ast` 静态检查, `hashlib`, `json`, `re`, `subprocess`, `uuid`, `ctypes`）；PowerShell 仅在将来获得明确新授权后由冻结 runner 调用。

**源身份：** 已批准的一次性基础诊断绑定候选 HEAD `0ad830234af70585d359df23123973eceeace3a3`、状态卡 SHA256 `BC774E0C9965BE22981390AF7B3255525C87B07038ECB87E2CAB46FDF34A35DF`、CI 节点 SHA256 `4990DDB836775D92DA18FC41998271FA77DDC5AF2BFCE305D30A18A77DAFB360`、五个 P3 import 闭包文件和原八个阶段标记。已批准 EOL 配对保持冻结：候选 `__init__.py` SHA `E76FDE183BF790D6CB3462FA0E90F334060C97426CA9F30152CC6738C4288D63`、主仓对应 SHA `E7BA40C8B09F5839D2189DDF1EE6372E6FA7EB435DD1CA2C4E902082E9F86621`，仅允许该已审 CRLF/LF 差异。

静态候选以冻结生成器 SHA256 `9422AA656EF6795EE34235C5BB7D27C2C1DFEAA99221ADEC6EA071F1081D6B68` 与冻结 runner SHA256 `B36EFB5895820453FC29A53F2AFAED014214B891D405729F1F74C8A7B87CE38F` 为唯一基底；候选脚本的差异仅限本文逐项列出的 P4 子阶段 marker/identity parser 扩展。

**前次观察：** 前次 UUID `16ec8e3f9f3d4daab2218aad0ff1aee2` 已 claim 且消费，不得再调用。其 runner metadata 记载 `execution_state=timed-out`、`observed_exit_code=124`、`elapsed_ms=181333`、`stdout_bytes=0`；metadata 阶段记录到 P4 区间。没有读取 stdout/stderr 正文。此观察只说明已进入 P4 并在 180 秒诊断中超时，不把时间归因给某一条 P4 语句。

## 本轮写入边界

本轮静态材料仅允许写在此 ignored 目录：

1. `plan.md`：本方案。
2. `generate_p4_substage_copy.py`：冻结原生成器的完整候选副本，新增五个精确锚点与五条 P4 子阶段 stderr 标记；仍核候选 HEAD、状态卡、测试节点、五文件 import 闭包和 EOL 配对身份，仍只创建新 ignored UUID 副本。
3. `run_p4_substage_once.py`：冻结原 runner 的完整候选副本，保持一次 claim、180000 ms 超时、原 shell 选择和 cwd、Windows Job 归属/只清理本 Job、原日志保留方式；新增 P4 marker 解析和新/旧 UUID/manifest marker-set 约束。

不改正式计划、两份冻结脚本、候选/主仓源、测试、队列、Git refs/index/config、既有 UUID。新执行时只能由生成器产生 `reports/o3-fourth-ci-1010/runs/<新 UUID>`；旧超时 UUID `16ec8e3f9f3d4daab2218aad0ff1aee2` 在生成器和 runner 中双重拒绝。

## P4 标记及时间区间

保持源代码中的旧 P4 标记（位于读取 `$sp` 之前），新增以下五个标记，每个只调用 `[Console]::Error.WriteLine`，仅附阶段名、UTC、当前 PID；不输出读取行、计数、路径或业务数据：

| 标记 | 唯一锚点位置 | 所度量区间 |
|---|---|---|
| `P4_READ_DONE` | 整文件 `Get-Content -LiteralPath $sp -Encoding UTF8` 完成之后、末六行预览之前 | 旧 P4 → 此标记：全文件读取耗时 |
| `P4_PARSE_START` | `foreach($ln in $sl)` 运行头解析循环之前 | 上一标记 → 此标记：末六行预览和解析器初始化 |
| `P4_PARSE_DONE` | 运行头循环完成且最后一个批次写入 `$rr` 之后 | parse start → parse done：全文件运行头/正文分段解析 |
| `P4_CLASSIFY_DONE` | 完整 `foreach($r in $rr)` 分类循环之后、`$mk` 统计闭包之前 | parse done → classify done：逐次运行的 regex 分类和分类记录构造 |
| `P4_AGGREGATE_DONE` | `$sstat` 最终汇总对象赋值完成后、离开 P4 块之前 | classify done → aggregate done：类别计数、连续让路及 1/7 天聚合 |

`P4_READ_DONE` 的生成器锚点是 `$sweep=(($sl|Select-Object -Last 6) -join "`n")` 行；生成器显式在该锚点行之前插入。因此 marker 实际位于完整 `$sl=Get-Content ...` 读取之后、末六行预览构造之前，`P4 → P4_READ_DONE` 才表示读取区间。若未来修改插入分支，必须重新核对实际顺序，不能只凭锚点行名称推断。

（表内 `$foreach` 表示源中的 PowerShell `foreach`，不新增语法。）完整路径仍是：`$sp=Join-Path $root 'reports\sweep-commit.log'`；不加过滤、不截短输入、不改变循环/regex/业务计算。P5 的既有标记紧随 P4 块闭合，因而可核 aggregate done 到 P5 的边界。锚点均按冻结源精确行唯一匹配；任何零命中、多命中或重合都在写 UUID 前 fail closed。

## 文件与接口

1. `generate_p4_substage_copy.py` 沿用冻结生成器的 CLI：可选 `--candidate-root`，缺省绑定批准 Native 候选路径。身份门仍在任何新 UUID 创建前执行。源副本保留 BOM/EOL 原始样式；import 闭包逐字节复制，只有已审 EOL 配对仍依原冻结 pair 比对。状态卡 diff guard 必须显式要求零删除行、恰好 13 条新增行，新增 label 序列与预期 P0–P7 加五个 P4 子阶段完全相等（因此每个各一次且顺序固定）；替换/业务行改动会因存在删除行而 fail closed。
2. `run_p4_substage_once.py` 沿用冻结 runner CLI：位置参数为生成器返回的新 UUID 目录。除了既有 HEAD/SHA/忽略状态/候选/副本/闭包/claim 检查，需核 `diagnostic_generation=p4-substage-v1`、前次已消费 UUID 指针及完整 marker 列表；副本嵌入标记也必须按源顺序精确匹配。副本内标记身份缺项/重复/乱序时，在进程创建前拒绝。运行时 stderr marker 是观测结果，异常不会改变已执行的进程路径，也不会被视为通过。
3. marker summary 保留 P0–P7 原字段；新增 P4 子标记作为独立 phase，按 stderr 原顺序计算相邻 UTC 间隔。由于 P1/P2 在源循环中可重复，解析器不把旧 phase 数量固定为 1。metadata 增加 `timing_valid` 与 `timing_errors`：UTC 无效/缺时区/倒退、P4 起始标记不恰一次、P4 标记重复、P4 marker PID 不一致、P4 子阶段不是唯一有序前缀或缺失任一预期子阶段时，`timing_valid=false`，列出具体错误及 `missing_substages`，且不计算任何 `intervals`。还必须验证筛出的实际 P4 序列严格等于 `P4 → 五个完整子阶段 → P5`；P4 必须先于全部子阶段，每个子阶段依次且各一次，P5 必须恰一次并在五阶段之后。超时留下的 `P4 + 子阶段有序前缀` 可作为观测顺序，但因缺阶段或缺 P5 而计时无效；原始 marker 留存供核验，不补造时间、不归因、不重试。仅所有时间和序列校验通过时才计算相邻 interval。

## 获批后唯一执行次序（本轮不执行）

1. 先由 Shao Peishen 对新的 180 秒状态卡诊断及精确副作用单独授权。原一次批准只消费过前 UUID；不自动延展到这次副本/执行。授权记录需绑定本方案 SHA、生成器 SHA、runner SHA、候选 HEAD、源/测试 SHA、五个新阶段、四个既有 .51 `/api/ping` 条件 GET、原 stdout/stderr 仅本机保存和 Job 定向清理范围。
2. 获批后只运行生成器一次，输出新 UUID。逐项审 manifest、忽略状态、五份副本 SHA、状态卡 diff 恰 13 条标记插入且旧 P0–P7 完整、五个新增 P4 锚点顺序正确。任何身份/差异不符，保留失败材料并停 runner；不重跑生成器以外的诊断。
3. 审核通过后只对该新 UUID 运行 runner 一次。cwd 固定为原 CI 等价目录 `C:/Users/Paul Shao/.codex/worktrees/o3-recovery-fix-1006/zhuopin-ai/5-平台底座/wecom-aibot-service`；选择逻辑、PowerShell UTF-8 stdout 编码、180000 ms 主超时、原有四个条件 GET、同一 Windows Job 加入/终止流程均沿用。严格只创建本次进程 Job，任何 Job 归属无法确认则不恢复执行，只清理此挂起 PID并保留 metadata。
4. runner 仅保存 stdout/stderr bytes、manifest、metadata、marker diff、实际退出码/超时/阶段时间有效性及清理证据到同一新 ignored UUID。不向终端展示原始输出；不读取或打印原始 stdout/stderr 正文。无论结果完成或超时都不重用此 UUID、不二次运行、不跑 pytest、不改脚本/产品、不触队列/真实数据、不清理旧锁/目录、不 commit/ff/push。
5. 审阅只把 P4 marker 区间用来判断下一步是否有足够定位信息。若只显示“整个文件读入慢”或仍无阶段终点，应将结论标为粒度不足并另行提更精确的静态/诊断方案；本方案不自动启动第二次诊断或提出修复。

## 当前静态验收

本轮只允许对候选 Python 文件做 `ast.parse`、生成器锚点文本/正则静态核对、runner marker parser 静态核对、源文件与候选文件 diff 审查及 SHA256 记录；不得 import/调用它们，不调用 git 写命令，不启动任何 PowerShell 子进程，不跑 pytest/状态卡/网络。计划完整性不等于新一轮授权，候选脚本不得被视为已执行。

静态复核更正记录：`independent-review.md` 首版曾误将“锚到末六行预览赋值”推断成“marker 在该赋值之后”。实际生成器在该锚点行前插入，当前实现已显式写出这一插入方向。本版本保留该历史报告原文及其 SHA，不把历史报告当作对本版修改的复核；上述位置说明以源代码插入方向为准。

最终静态复审修订：runner 计时合同要求实际筛出序列严格为 `P4 → 五个 P4 子阶段 → P5`，并在全部 UTC/PID/序列校验通过前不生成 interval。生成器 diff guard 显式拒绝任何删除行，新增行必须恰为预期 13 marker labels 的完整有序序列；本段是方案要求，不表示脚本已运行。

## 根正式执行件绑定

2026-10-10T23:04:38.448112+08:00：供审原稿45C8…8AE2及最终独立复审以静态源码核两项缺口闭合。正式冻结执行件位于 docs/superpowers/plans/o3-p4-substage-diagnostic-1010/，生成器SHA 4AD3BE7691D4DA768720F130AA79CBEDE0FAF53E9B4372048FF4442D31849E8E；runner SHA 0026B2FB6D23271FE6B1C5B0F5FF7ED11EE2B7C2004C3AFF572A258906DB9320。批准后命令唯一为已核Python -B加正式生成器绝对路径（--candidate-root为本文固定Native），生成新UUID后以已核Python -B加正式runner绝对路径和该唯一新UUID路径。正常timeout才有phase_timing；Job异常分支保留异常/原证据但没有phase_timing，不宣称测量有效。新一次180秒诊断仍需本人批准，旧一次已消费不得重跑；无第四pytest/修复/ff。
