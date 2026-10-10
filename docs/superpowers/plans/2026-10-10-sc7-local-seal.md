# SC7 合成批量数量首项本地封存计划

**状态：** 根正式登记的具体供审计划；尚未获本地封存批准。

**目标：** 将已复审的 SC7 `synthetic_normalized` 首项两文件实现封存为一个可追溯的本地普通 commit，不合入主分支、不发布。

**基线：** `310f54de71149b0cb0281749619ee3cd84f97bca`。正式结果记录为 detached Native；文件 SHA-256 为 `batch_quantity.py=DB97E8682D5D0966FBB47030451614B94B1099DE33B9970CE15D2F0417672972`、`test_batch_quantity.py=BAFBC7F80DFDBA56A6789B429BA7621DD7AA8D586C54BA2AE2620FBC352B8412`；既有定向 GREEN 为 57 passed，0 error/failure/skip，exit 0；独立复审记录 SHA `6E54F5E16B3748698C7143DA83A810446EA346239B3F259F93F1B5B329DF13A1`。本封存不重跑测试。

**候选：** `C:/Users/Paul Shao/.codex/worktrees/sc7-batch-quantity-1010/zhuopin-ai`，HEAD `310f54de71149b0cb0281749619ee3cd84f97bca`，当前 detached，当前状态所见仅两项未跟踪产品路径。`git rev-parse --git-common-dir` 实测为 `C:/Dev/zhuopin-ai/.git`，意味着候选分支引用与对象库共享主仓 common Git 元数据。不要误称为私有 Git 仓库。

## 需单独批准的动作与效果

既有具体实现批准明确写有 `commit/ff/production` 不在范围。执行此计划前必须取得一次新的明确批准，绑定候选绝对路径、固定 HEAD、目标分支名、两个文件的准确内容 SHA、普通单 commit、证据目录副作用及禁止 ff 的边界。此计划本身不构成批准。

经新批准后才可在同一 Native checkout 做以下可逆但真实的本地 Git 写入：

1. 创建并切换到建议分支 `codex/candidate-sc7-1010`；它会更新候选 checkout 的 `HEAD`/worktree 元数据，并在共享 `C:/Dev/zhuopin-ai/.git` 中创建或更新分支引用/reflog。若分支名已存在、已被其他 worktree 使用或 checkout 身份/基线有漂移，立即停止，不覆盖既有引用。
2. 只 stage 清单中的两条路径，并生成一个普通 commit；提交对象/树对象进入共享 object database，分支引用推进一次。不得 amend、force、rebase、cherry-pick、push、开 PR 或合入任何主线。
3. 在主仓 ignored 目录 `C:/Dev/zhuopin-ai/reports/sc7-batch-quantity-1010/seal/<newUUID>/` 保存命令、前后检查、原始 Git stdout/stderr/exit、父/树/路径/blob/mode/SHA 与分支状态证据。运行前以 Test-Path 确认该 UUID 目录不存在；不得覆盖旧证据。

`ZhuopinCommitSweep` 面向队列 §二批次；它不能代替这次 detached Native 中精确限定两条未跟踪文件的本地封存。不得通过制造/改写队列任务或调用 sweep 代替批准的例外。新批准前不运行任何 Git 写命令。提交后状态干净只是封存核验，不会自动取得 ff、集成、发布、真实 ERP 或专业 L2 批准。

## 受控步骤

### 1. 前置检查（只读）

在原 Native 路径运行并逐条保存真实输出：

```powershell
$Git = 'C:/Program Files/Git/cmd/git.exe'
$Native = 'C:/Users/Paul Shao/.codex/worktrees/sc7-batch-quantity-1010/zhuopin-ai'
& $Git -C $Native rev-parse --show-toplevel
& $Git -C $Native rev-parse HEAD
& $Git -C $Native rev-parse --git-common-dir
& $Git -C $Native status --porcelain=v1
& $Git -C $Native branch --show-current
& $Git -C $Native worktree list --porcelain
```

门槛：top-level 必须精确等于 `$Native`；HEAD 必须仍为固定基线；branch 仍为空（detached）；status 必须恰好是指定两文件的 `??`，无其他改动/暂存；`worktree list` 不得显示目标分支已被占用。另用 `Get-FileHash -LiteralPath` 对两个文件重算 SHA-256，与正式实现结果 JSON 完全相等。根已用两条单独、针对精确Native路径的Get-FileHash核SHA一致；未来仍须核读，若工具真拒则停止，不绕读。验证 base tree 中两个路径均不存在，避免把新增误当覆盖：

```powershell
& $Git -C $Native ls-tree HEAD -- '4-数字员工/采购部/SC7-库存优化建议/sc7_inventory/batch_quantity.py' '4-数字员工/采购部/SC7-库存优化建议/tests/test_batch_quantity.py'
```

输出必须为空。若上述任一事实不成立，停止，不调整源文件、stage 或分支名。

### 2. 创建唯一目标分支并核验

仅在新批准后执行：

```powershell
& $Git -C $Native switch -c 'codex/candidate-sc7-1010'
```

要求 exit 0；随后复核 `branch --show-current` 精确为 `codex/candidate-sc7-1010`，HEAD 仍等于固定 base，`status --porcelain=v1` 仍恰为两条目标 `??`。否则停止并保存现状，不自动删除/回退引用。

### 3. 精确暂存并核对提交前差异

只执行一次有路径白名单的暂存：

```powershell
& $Git -C $Native add -- '4-数字员工/采购部/SC7-库存优化建议/sc7_inventory/batch_quantity.py' '4-数字员工/采购部/SC7-库存优化建议/tests/test_batch_quantity.py'
```

检查并保存以下输出，所有条件均满足才允许 commit：

```powershell
& $Git -C $Native diff --cached --check
& $Git -C $Native diff --cached --name-status
& $Git -C $Native diff --cached --raw
& $Git -C $Native diff --cached --summary
& $Git -C $Native diff --cached --numstat
& $Git -C $Native status --porcelain=v1
& $Git -C $Native ls-files --stage -- '4-数字员工/采购部/SC7-库存优化建议/sc7_inventory/batch_quantity.py' '4-数字员工/采购部/SC7-库存优化建议/tests/test_batch_quantity.py'
```

预期：cached name-status 恰好两行且均 `A`；原始差异是新增 blob、模式均 `100644`；cached 与 worktree 无其他路径；两文件 SHA-256 仍与正式 JSON 相等。检查失败就停，不用 `git add -A`、`git add .` 或补加文件。

### 4. 单次普通 commit

所有提交前证据通过并且具体提交批准仍有效时，执行一次：

```powershell
& $Git -C $Native commit -m 'feat(sc7): seal synthetic batch quantity evidence'
$CommitExit = $LASTEXITCODE
```

立即记录此进程的真实退出码、stdout、stderr；若非 0，保留现场与 index，不 amend、不重置、不自动重试。

### 5. 提交后绑定

只读回核并保存：

```powershell
& $Git -C $Native rev-parse HEAD
& $Git -C $Native show -s --format='%H%n%P%n%T%n%an%n%ae%n%aI%n%s' HEAD
& $Git -C $Native diff-tree --no-commit-id --name-status -r HEAD
& $Git -C $Native diff-tree --no-commit-id --raw -r HEAD
& $Git -C $Native ls-tree -r HEAD -- '4-数字员工/采购部/SC7-库存优化建议/sc7_inventory/batch_quantity.py' '4-数字员工/采购部/SC7-库存优化建议/tests/test_batch_quantity.py'
& $Git -C $Native status --porcelain=v1 --branch
Get-FileHash -LiteralPath 'C:/Users/Paul Shao/.codex/worktrees/sc7-batch-quantity-1010/zhuopin-ai/4-数字员工/采购部/SC7-库存优化建议/sc7_inventory/batch_quantity.py' -Algorithm SHA256
Get-FileHash -LiteralPath 'C:/Users/Paul Shao/.codex/worktrees/sc7-batch-quantity-1010/zhuopin-ai/4-数字员工/采购部/SC7-库存优化建议/tests/test_batch_quantity.py' -Algorithm SHA256
```

要求新 commit 的 parent 恰为固定基线，message 精确匹配，tree 仅增加指定两路径，blob 对应模式 `100644`，文件 SHA-256 等于批准结果 JSON，branch 指向该 commit，status 干净。任一不符均记录并停；不修复、不 amend。

## 不在本封存范围

不重跑已有 57 项测试，不修改/扩展文件，不把正式设计输入 transport 到 Native，不更改 OpenSpec/队列/主仓产品，不执行合并、ff、push、PR、部署或真实 ERP/ItemMaster 查询，不作采购建议或 L2 专业签认。K2 `lead_time_days` 和共享 connector 均保持封存前状态；真实数据、业务采用、集成与后续发布要另行审批。

## 正式执行件与根前检

2026-10-10T23:50:15.891331+08:00：正式pack docs/superpowers/plans/sc7-local-seal-1010/ 内仅 seal_sc7.py（SHA AE1B922E536B9638B0D6D4A2CBCA543DA39B759736A3CCF9527ADBB59CDE23D3）和manifest.json（SHA 6374EA681EB86C0AC52FA8D00ED578D50F7DD7CCE79CAC8821D61BE8ED186987）。只允许本正式执行件消费真实本人批准。其默认调用只读；--seal必须同时核schema=sc7-seal-approval/v1、approved/explicit_human_answer=true、plan/script/manifest三SHA、Native/base/branch/两字节SHA及精确sc7_completed_candidate_preservation_only例外，不扩用旧五棵批准。

实际只读前检actual0见 reports/sc7-batch-quantity-1010/seal/7e169a58-d81b-46de-9d05-ad5eee144cec/summary.json；top-level/HEAD/detached/commonGit/新ref不存在/两新增路径/空index/hash/check-attr均核，配置core.hooksPath与commit.gpgsign未设置，core.fsmonitor唯一主仓config来源false。执行前反复核固定Git executableSHA 37C572…0BC9、无非sample hooks/未知config/filter；不关闭hooks、不改config，不执行fsmonitor/gpg/filter。前检第一次因false被过严拒绝保留在1c920f14…，随后仅允许该实测精确false。

批准后正式唯一命令：已核Python -B加本正式seal_sc7.py绝对路径及 --seal。先形成0-学习与工具/codex-handoff/SC7两文件本地封存批准消费-2026-10-10.json；新一次claim为同目录SC7两文件本地封存-执行.claim.json，仅允许创建一次，已存在停止。主仓新UUID seal证据、批准消费/claim及共同Git/Native元数据属于此次声明副作用；不修改其他Native文件。commit启动前committed=null，非零记录只读HEAD并明确需复核，绝不自动重试/回退。静态独立复审见seal-executor-final-review.md；只读前检不是测试重跑，原57项结果保留。
