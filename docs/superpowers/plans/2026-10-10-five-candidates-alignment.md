# 五候选串行对齐具体实施计划（待本人批准）

状态：仅供复审；正式审批载体是 `docs/superpowers/plans/2026-10-10-five-candidates-alignment.md`。本 ignored 草稿不构成正式批准；本轮没有新树、cherry-pick、测试或发布授权。
目标：在新建 Native worktree 中，以固定 FrozenBaseSHA `310f54de71149b0cb0281749619ee3cd84f97bca` 为基线，将五个已封存候选按 SC2 → SC4 → SC10 → SC11 → O4 顺序正常 cherry-pick；逐项核对提交来源、白名单和 41 个最终文件 blob 与正式封存 manifest 一致；仅运行本稿列出的六组整合定向测试候选，且需新的明确批准。EE5 当前 active，SC10/SC11 的对齐和测试必须待 EE5 完成后再按顺序进行。旧单 lane 测试授权不延伸至整合树。结果限于新 Native 和 ignored 证据，不进入 master，不 ff，不部署，不取真实数据。

## 1. 当前事实与执行边界

封存计划：docs/superpowers/plans/2026-10-10-five-candidates-seal.md，SHA-256 F9489E7A1729476F4068E80CA205F3AFE6A981C26F92D1278E3BED15C5953819。
封存 manifest：docs/superpowers/plans/five-candidates-seal-1010/manifest.json，SHA-256 A4996E4758B4A36326D95D87524EAC63F02135AF57A126135CF2CBA5C51D12DB。

旧批准消费件 0-学习与工具/codex-handoff/五候选本地提交批准消费-2026-10-10.json，SHA-256 AA487190423E44493A7004DB487545B89B9B85D2C898F6E219A77C2BB1FAD665。授权类型是 native_detached_candidate_commit_preservation，绑定共同父提交 28337c0ebb52afdbf61e955ecdbc22d151bcd185、旧封存计划/manifest 与五个精确路径白名单。该授权不覆盖 Native 整合、cherry-pick 或整合后复测；不能作为本次 authSHA。

本稿提出的新范围标识为 `sealed_candidate_alignment_verification_only`：仅对五个已经封存的提交和封存清单中的 41 个路径做合成对齐，并在全量对齐后运行本稿逐项列明的定向测试。该例外不重新解释或回查旧 global §三，不扩大或撤销旧冻结，不包含新场景建造、新参数、新默认值、业务口径变更、真实数据或额外测试。正式计划与新 auth 都须明确记录该范围，审核人须针对正式计划和这个有限例外另行批准；旧 seal 授权不延伸。

冻结基线固定为 committed SHA `310f54de71149b0cb0281749619ee3cd84f97bca`；这是本计划的固定输入，不在执行时另行挑选。主仓有其他既存 dirty，全部保留且不得带入 Native。本计划不要求主仓整体 clean。执行前须分别校验：41 个产品路径按 seal manifest 的原父提交状态应当在主仓 clean、无 index/worktree/untracked/conflict/ignored overlap；控制文件则按新 auth 逐项绑定的 expected porcelain status 与 SHA 检查，允许计划/授权文件自身处于已知 dirty 或 untracked 状态。控制文件只有缺失、冲突、状态与绑定不符或 SHA 漂移才停止；不能把控制文件的预期 dirty/untracked 误判为产品 dirty。非控制、非 41 路径的历史 dirty 保留并记录，不触碰、不复制。新 Native 必须从上述固定 committed SHA 创建且自身 clean；不能从主仓 working-tree snapshot 创建。

## 2. 已封存候选与证据绑定

五提交的共同父提交均为 28337c0ebb52afdbf61e955ecdbc22d151bcd185。每份实际 summary 显示提交、父提交、预检与提交后校验成功，实际 exit 为 0；它证明 seal，不证明 integration 已批准。

| 顺序 | 场景 / ref | commit | summary.json | summary SHA-256 | 路径数 |
|---|---|---|---|---|---:|
| 1 | SC2 / codex/candidate-sc2-1010 | fe49e42a05b63ee41948be93c19a24989453d184 | reports/candidate-integration-1010/seal-evidence/d0f5d6cd-adb6-4e48-ae08-f8870711bb1f/summary.json | 71FE6B43E3429E0C5418D07113AD1CE3C7B2AA07F5DFA1099F013C333FE574D5 | 14 |
| 2 | SC4 / codex/candidate-sc4-1010 | 91faf5b4c56e162011a5b56796170e9b212f1359 | reports/candidate-integration-1010/seal-evidence/10a42159-e7f3-431e-84e5-82871b8832fb/summary.json | 01C92606EDF5913FCDA5709EB4E5396E6CBBD9FF06542CB853AEDE2486CBB95D | 8 |
| 3 | SC10 / codex/candidate-sc10-1010 | 25eb192258fcd6ce51e654ec01c62918486c7736 | reports/candidate-integration-1010/seal-evidence/10ddd9f3-4826-4d47-9f4e-915e32b403ec/summary.json | 8FA930C2797219F0DBB598B28EFA3EB90E5510C661E53A1E447EC65B5BC107AF | 4 |
| 4 | SC11 / codex/candidate-sc11-1010 | 6990139aca37e1252684ef051685198bc7e0c9a1 | reports/candidate-integration-1010/seal-evidence/67e48ba4-69a0-4289-a232-7ce283965e21/summary.json | C19C9376BC6111C5E59945B170D1F5E5C923ED7DBD07C5A2C3B57A6A891941FD | 7 |
| 5 | O4 / codex/candidate-o4-1010 | 6a11819da67902eaa9ae934e061c607c24fcc624 | reports/candidate-integration-1010/seal-evidence/9ddc9bd3-3238-483c-93d3-aab368ead274/summary.json | FE893CC955746A96B2033FE8398A9E86361FC127A95761D7ABB2E496C4F265A1 | 8 |

Formal seal plan §6 和 manifest 是 41 路径、每项 candidate_git_blob_oid / mode / 原始父提交状态的权威白名单；共 27 tracked replacements/updates 与 14 additions，五组不重叠。执行前须重新逐项读核，不能手工补减或以摘要代替文件级核验。SC2 有两个共享平台文件，影响边界见第 6 节。SC10/SC11 summary 标记 freezeverificationlimit=unverifiable_by_official_query，表示官方队列工具不提供该冻结核验；不扩大整合授权。

## 3. 目标基线、审核输入与允许的主仓 dirty

`FrozenBaseSHA` 固定为 committed `310f54de71149b0cb0281749619ee3cd84f97bca`。执行前解析该 SHA 并核验对象存在；Native 只从这个固定 commit 创建，不从主仓 working-tree snapshot 创建。正式计划、批准消费件和原始来源文件均从主仓绝对路径读取，不要求也不尝试让这些未提交控制文件出现在 Native HEAD。

### 3.1 从主仓绝对路径读取的受控输入

实际来源读取根固定为 `C:\Dev\zhuopin-ai`；任何解析结果不在该根下都停止。以下观察 SHA 是本稿撰写时的已知值，执行前全部重算并由新批准消费件逐项绑定：

| 主仓相对路径 | 用途 | 本稿观察 SHA-256 |
|---|---|---|
| `docs/superpowers/plans/2026-10-10-five-candidates-seal.md` | seal 来源/边界 | `F9489E7A1729476F4068E80CA205F3AFE6A981C26F92D1278E3BED15C5953819` |
| `docs/superpowers/plans/five-candidates-seal-1010/seal_candidates.py` | 只核来源 SHA，不执行 | `6CAB74E0FA2E336C531E25FB62432D15C76A5998805D6818830EB6224D1A1277` |
| `docs/superpowers/plans/five-candidates-seal-1010/manifest.json` | 正式封存 manifest；41 路径权威 | `A4996E4758B4A36326D95D87524EAC63F02135AF57A126135CF2CBA5C51D12DB` |
| 第 2 节五份 `summary.json` | 原 sealed commit 证据 | 各自 SHA 见第 2 节 |
| `0-学习与工具/codex-handoff/五候选本地提交批准消费-2026-10-10.json` | seal 授权边界；不扩权 | `AA487190423E44493A7004DB487545B89B9B85D2C898F6E219A77C2BB1FAD665` |
| `docs/superpowers/plans/2026-10-10-sc2-biztype316-receipts.md` | SC2 测试范围来源 | `6B52F00872654AD407C931BCEEE12309500A13EACF93C42BC1A145E674219B9C` |
| `docs/superpowers/plans/2026-10-10-sc4-source-evidence.md` | SC4 测试范围来源 | `8EB31234EEA4B7F70D929E94AB326F9F5FBCCE8C35C8B983EAC6ECBADC565228` |
| `docs/superpowers/plans/2026-10-10-sc10-versioned-facts.md` | SC10 测试范围来源 | `F7A61C74916A0F380A04931170076DFB2C4E6CCA2769D1BD51A23AFCF8D076A3` |
| `docs/superpowers/plans/2026-10-10-sc11-shared-stock-versioned-confirmation.md` | SC11 测试范围来源 | `07CD85B01B8FB0A50C642613BCAFE36C023C96AFD9F5FE69ABDF66B6992B6678` |
| `docs/superpowers/plans/2026-10-10-o4-stage0-evidence.md` | O4 测试范围来源 | `316175B4F5FDF04616C760819020A90232DA33B4AC60231B5BBEDBB5382D749F` |
| `docs/superpowers/plans/2026-10-10-five-candidates-alignment.md` | 正式对齐计划及审批载体；当前 ignored 草案不是正式载体 | 正式稿形成后，绑定其精确 SHA 与预期 porcelain status |
| `reports/candidate-integration-1010/alignment-plan-candidate.md` | ignored 供审稿，仅供形成正式稿 | 不作为 approval carrier；不以本稿 SHA 替代正式稿 SHA |
| `0-学习与工具/codex-handoff/五候选整合批准消费-2026-10-10.json` | 本轮 auth；真实明确批准后才创建 | 创建后记录其精确 SHA 与预期 porcelain status |

新 auth 由 root 在真实明确批准后登记，绑定审核人批准原话/证据指针及其 SHA、正式对齐计划的 SHA、seal plan/正式 manifest/five summaries/五个源 ref+commit+tree、固定 FrozenBaseSHA、测试清单/runtime、Native capability 和 allowed root、限定例外及操作边界。JSON 不创造授权。auth 记录 `returned_root: null`；不得把创建前未知的 Native 实际路径伪装成审批前已知值。Native 创建后，以独立 after-create evidence 绑定 Native 工具返回的实际路径、HEAD/ref/status 和 identity；只在实际解析路径位于 `C:\Users\Paul Shao\.codex\worktrees\` 下且符合固定 name/capability、HEAD 与 status 要求时继续。若工具不能保证/验证 allowed root，停止并交审核人处理。计划与 auth 均从上述主仓绝对路径读取；不要求它们存在于 FrozenBaseSHA 或 Native HEAD，也不把它们复制进 Native。

### 3.2 控制文件状态绑定

正式对齐计划与本轮 auth 是控制文件，不属于 41 个产品路径。新 auth 必须逐个列明控制文件的绝对/相对路径、存在性、预期 Git porcelain-v2 状态、SHA256 和读取时点；允许正式计划处于预先声明的 dirty/untracked 状态，允许新 auth 在注册后为 untracked，不能把这类已绑定状态强制改成 clean。正式计划写入后、auth 登记后，root 必须把各自实际状态与 SHA 记入独立 after-registration evidence；auth 自身 SHA 由该独立证据绑定，避免自引用。正式计划当前缺失或冲突时不得批准；新 auth 只在真实批准后创建，不是批准前置。执行前须核 auth 存在、状态与独立哈希绑定；缺失、状态不符或 hash 漂移一律停止。seal plan、manifest、summaries 等其余控制文件同样逐个绑定自己的预期状态与 SHA；它们的状态不要求与控制文件通用状态相同。

41 个产品路径则必须与第 2 节 seal manifest 的原父提交状态完全吻合：原有路径在主仓无 index/worktree dirty，无 untracked/ignored/conflict overlap；manifest 标为新增的 14 项在主仓应保持不存在。任何产品路径被修改、暂存、冲突、意外出现或与控制文件交叠都停止。控制文件允许状态与产品路径 clean 门槛严格分开。

执行前，对 41 个产品路径与所有控制文件分别核验绝对路径、存在性/预期不存在、expected porcelain status 与 SHA。Git 状态证据使用精确路径参数及 `--porcelain=v2 --untracked-files=all --ignored=matching`，并分别核未暂存与已暂存差异。控制文件按其 auth 声明的预期状态检查，允许计划/auth 的精确 dirty/untracked；产品路径必须 clean、无冲突且与控制文件无 overlap。控制文件或产品路径任何意外缺失、漂移、冲突、状态不符或 hash 不符都停止。FrozenBaseSHA 固定为 `310f54de71149b0cb0281749619ee3cd84f97bca` 并写入证据；检查其对 41 路径的 tree blob/mode 与共同父提交：新增项仍不存在，既存项 blob/mode 相同；另检查共同父提交至 FrozenBaseSHA 的 committed path diff 与 41 路径交集为空。主仓其它历史 dirty 原样保留，只记录审查所需状态摘要，不触碰、不复制、不要求整体 clean。

## 4. 新 Native 与串行整合方案

Native 名称固定 `five-candidates-align-1010`；分支名固定 `codex/five-candidates-align-1010`。新授权绑定 Native 工具能力、FrozenBaseSHA 与 allowed root `C:\Users\Paul Shao\.codex\worktrees\`；实际 returned root 仅在创建后的 identity evidence 中绑定。新树只从授权记录绑定的 FrozenBaseSHA 创建。原五个 candidate worktree/ref/证据全程只读保留，不 reset/rebase/clean/覆盖/归档。

新 Native 创建后，先记录 WorktreeRoot、HEAD、branch、status 和绝对路径；实际路径必须在授权 allowed root 下，HEAD 必须等于 FrozenBaseSHA，porcelain 必须为空。确认固定分支名不存在后再切换到它。不得把主仓 dirty snapshot 复制进 Native。

EE5 当前为 active，是 SC10/SC11 的串行前置闸。SC2、SC4 可按顺序进行；SC4 后必须停在检查点。只有 EE5 有正式完成证据且根确认该闸已关闭，才继续 SC10 对齐；SC10 完成后再进行 SC11 对齐。不得并行处理 SC10 与 SC11。相应 SC10/SC11 定向测试也不得在 EE5 完成前运行；本计划的六组测试只在所有前置闸闭合、五项对齐完成后按第 5 节逐组执行。EE5 的完成判据/状态由其正式流程提供，本稿不读取或改写其队列状态。

按 SC2、SC4、SC10、SC11、O4 五提交顺序执行普通 `git cherry-pick`，不 squash、不 rebase、不用 `-X ours/theirs`、不手工应用 patch。全部五个 SHA 是第 2 节表内固定字面值；每次只对当前一个 commit 执行，紧接读取 exit 并留完整 stdout/stderr/命令证据，exit 非零立即停止。只有当下 lane 全部前检成功后才执行相应命令：

```powershell
& git --no-pager -C "$ActualWorktreeRoot" cherry-pick 'fe49e42a05b63ee41948be93c19a24989453d184' # SC2
$GitExit = $LASTEXITCODE
if ($GitExit -ne 0) { throw 'SC2 cherry-pick failed; preserve Native/index and stop' }
& git --no-pager -C "$ActualWorktreeRoot" cherry-pick '91faf5b4c56e162011a5b56796170e9b212f1359' # SC4
$GitExit = $LASTEXITCODE
if ($GitExit -ne 0) { throw 'SC4 cherry-pick failed; preserve Native/index and stop' }
& git --no-pager -C "$ActualWorktreeRoot" cherry-pick '25eb192258fcd6ce51e654ec01c62918486c7736' # SC10
$GitExit = $LASTEXITCODE
if ($GitExit -ne 0) { throw 'SC10 cherry-pick failed; preserve Native/index and stop' }
& git --no-pager -C "$ActualWorktreeRoot" cherry-pick '6990139aca37e1252684ef051685198bc7e0c9a1' # SC11
$GitExit = $LASTEXITCODE
if ($GitExit -ne 0) { throw 'SC11 cherry-pick failed; preserve Native/index and stop' }
& git --no-pager -C "$ActualWorktreeRoot" cherry-pick '6a11819da67902eaa9ae934e061c607c24fcc624' # O4
$GitExit = $LASTEXITCODE
if ($GitExit -ne 0) { throw 'O4 cherry-pick failed; preserve Native/index and stop' }
```

上面是依次单独执行的五个命令，不是整段无条件批跑；各步之间必须完成以下前后核验与留证。
- 源 commit 可解析，唯一 parent 是共同父提交。
- 表中每个 source ref 必须解析到对应的固定 commit SHA；只证明 commit SHA 可解析不够。
- source tree 等于 formal plan 记录：SC2 8ce16b268ebe8ce5dc4418a0aab0063b782aae8c；SC4 ad1163674ded48a52bfaced0288f35637e1d78a0；SC10 4b5097ac312adf338eca91d41eab5ef9d0751515；SC11 cf0ee4b32951869ea10c206b4274cfaa4f49d75c；O4 e92b623448a4478bd4f1e8033c2f7bfd7c723e09。
- source commit 的 diff-tree 路径集与本 lane manifest 白名单完全相等，数量依次为 14/8/4/7/8；逐项 candidate blob OID 与 manifest 相等，mode 相同。
- cherry-pick 后 HEAD 的唯一 parent 是执行前 HEAD；新提交路径仅为此 lane 白名单；逐项 HEAD blob/mode 与 manifest 相等；新 Native status 为空。

最后验证 FrozenBaseSHA 是整合 HEAD 祖先；FrozenBaseSHA..HEAD 路径集合恰等于 41 白名单；所有 41 blob/mode 与 manifest 相等；first-parent 新增提交顺序恰为五 lane 顺序；新 Native 干净。命令完整 argv、stdout/stderr、exit 都进审核证据。

任何产品路径 dirty/overlap、控制文件状态/hash 与 auth 绑定不符、源 ref/OID/tree/path 漂移、目标路径基线变动、冲突或非零退出，均在该步停止并保留新 Native/index 状态供复审；控制文件只有偏离自身预期状态才停止，不因其已绑定的 dirty/untracked 状态停止。不运行 cherry-pick --abort、不手改冲突、不跳 lane、不重试覆盖。原候选树永不更改。

## 5. 精确定向测试矩阵（须新批准后才运行）

每个候选已在各自 sealed tree 验证；这不证明新整合树。alignment 人批记录须显式授权下面六组，不扩展到本表外测试。测试文件字面值从五份原具体计划逐项核取；SC10 四个文件沿用其批准范围，不能因 sealed commit 触及较少测试就自行缩减整合验收。

EE5 仍 active 时，本测试矩阵不得启动 SC10/SC11 测试。只有 EE5 正式完成并由根确认前置闸关闭，且 SC10、SC11 已依次对齐后，才可按表中 SC10 后 SC11 的顺序运行对应测试；不以其他场景测试已通过代替此闸。

| 顺序 | WorktreeRoot 下 cwd | 唯一 targets |
|---|---|---|
| 1 | 4-数字员工/采购部/SC2-采购周报自动生成 | tests/test_detail.py tests/test_metrics.py tests/test_report.py tests/test_sources.py |
| 2 | 5-平台底座/zhuopin_platform | tests/test_erp_biztype316.py |
| 3 | 4-数字员工/采购部/SC4-合同条款自动提取与审核 | tests/test_text_source.py tests/test_clause_extract.py tests/test_agent_audit.py |
| 4 | 4-数字员工/采购部/SC10-BOM评审与物料库管控 | tests/test_evidence.py tests/test_review_facts.py tests/test_agent_audit.py tests/test_pending_gates.py |
| 5 | 4-数字员工/采购部/SC11-库存智能调拨 | tests/test_shared_reservation.py tests/test_versioned_audit_gate.py tests/test_pmc_gate.py |
| 6 | 4-数字员工/运营部/O4-设备预测性维护 | tests/test_stage0.py |

### 5.1 Runtime 身份前置核验

本轮只读观察：`C:\Dev\Codex\runtimes\zhuopin-ai\venv\Scripts\python.exe` 存在；SHA-256 `760E6890B3DB606715075976C3793BFCE092DC8BDF30D48C56CFCACCFDD07F25`；Python `3.14.5`；pytest `9.0.3`。观察通过文件 hash 与 `-B` 版本/metadata 查询取得，未运行产品测试。批准消费件须绑定 runtime 绝对路径、exe SHA、Python 版本、pytest 版本；执行前重核完全一致，否则停止并重新审阅/授权。不安装、不升级、不重装、不换 interpreter。每组都使用同一核验过的 runtime。

### 5.2 完整执行命令契约

唯一测试入口固定为下方 PowerShell 模板。$WorktreeRoot 只能取 Native 工具返回的实际路径，且必须解析位于 `C:\Users\Paul Shao\.codex\worktrees\` 下；$MainEvidenceRoot 固定为主仓 ignored 根 `C:\Dev\zhuopin-ai\reports\candidate-integration-1010`；$CampaignId 与每组新 $RunId 均为批准后生成的 GUID。每组 cwd 和 target 是固定字面值，不得目录枚举、自动发现或补测。审批绑定此命令文本的 SHA、六组固定矩阵、runtime 与 evidence root。批准前不建目录、不运行测试。

```powershell
$ExpectedRuntime = 'C:\Dev\Codex\runtimes\zhuopin-ai\venv\Scripts\python.exe'
$ExpectedRuntimeSha256 = '760E6890B3DB606715075976C3793BFCE092DC8BDF30D48C56CFCACCFDD07F25'
$ExpectedPythonVersion = 'Python 3.14.5'
$ExpectedPytestVersion = '9.0.3'
$AllowedWorktreeRoot = [IO.Path]::GetFullPath('C:\Users\Paul Shao\.codex\worktrees').TrimEnd('\') + '\'
$ActualWorktreeRoot = [IO.Path]::GetFullPath($WorktreeRoot)
if (-not $ActualWorktreeRoot.StartsWith($AllowedWorktreeRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Native path outside approved worktree root' }
if (-not (Test-Path -LiteralPath $ActualWorktreeRoot -PathType Container)) { throw 'Native worktree path missing' }
$EvidenceRoot = [IO.Path]::GetFullPath($MainEvidenceRoot)
if ($EvidenceRoot -ne [IO.Path]::GetFullPath('C:\Dev\zhuopin-ai\reports\candidate-integration-1010')) { throw 'evidence root differs from approved path' }
if (-not (Test-Path -LiteralPath $EvidenceRoot -PathType Container)) { throw 'main evidence root missing' }
if ($CampaignId -notmatch '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$') { throw 'campaign ID must be an approved UUID' }
$CampaignDir = Join-Path $EvidenceRoot $CampaignId
if (Test-Path -LiteralPath $CampaignDir) { throw 'campaign evidence directory exists; never overwrite' }
$ActualRuntime = [IO.Path]::GetFullPath($ExpectedRuntime)
if (-not (Test-Path -LiteralPath $ActualRuntime -PathType Leaf)) { throw 'approved runtime missing' }
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $ActualRuntime).Hash -ne $ExpectedRuntimeSha256) { throw 'approved runtime SHA mismatch' }
$ActualPythonVersion = & $ActualRuntime -B --version
if ($LASTEXITCODE -ne 0 -or $ActualPythonVersion.Trim() -ne $ExpectedPythonVersion) { throw 'Python version mismatch' }
$ActualPytest = & $ActualRuntime -B -c "import importlib.metadata as m; print(m.version('pytest'))"
if ($LASTEXITCODE -ne 0 -or $ActualPytest.Trim() -ne $ExpectedPytestVersion) { throw 'pytest version mismatch' }
New-Item -ItemType Directory -Path $CampaignDir -ErrorAction Stop | Out-Null

$Suites = @(
    @{ Id='SC2'; Cwd='4-数字员工/采购部/SC2-采购周报自动生成'; Targets=@('tests/test_detail.py','tests/test_metrics.py','tests/test_report.py','tests/test_sources.py') },
    @{ Id='PLATFORM'; Cwd='5-平台底座/zhuopin_platform'; Targets=@('tests/test_erp_biztype316.py') },
    @{ Id='SC4'; Cwd='4-数字员工/采购部/SC4-合同条款自动提取与审核'; Targets=@('tests/test_text_source.py','tests/test_clause_extract.py','tests/test_agent_audit.py') },
    @{ Id='SC10'; Cwd='4-数字员工/采购部/SC10-BOM评审与物料库管控'; Targets=@('tests/test_evidence.py','tests/test_review_facts.py','tests/test_agent_audit.py','tests/test_pending_gates.py') },
    @{ Id='SC11'; Cwd='4-数字员工/采购部/SC11-库存智能调拨'; Targets=@('tests/test_shared_reservation.py','tests/test_versioned_audit_gate.py','tests/test_pmc_gate.py') },
    @{ Id='O4'; Cwd='4-数字员工/运营部/O4-设备预测性维护'; Targets=@('tests/test_stage0.py') }
)
foreach ($Suite in $Suites) {
    $RunId = [guid]::NewGuid().ToString()
    $SuiteParent = Join-Path $CampaignDir $Suite.Id
    if (-not (Test-Path -LiteralPath $SuiteParent -PathType Container)) { New-Item -ItemType Directory -Path $SuiteParent -ErrorAction Stop | Out-Null }
    $SuiteDir = Join-Path $SuiteParent $RunId
    if (Test-Path -LiteralPath $SuiteDir) { throw 'suite evidence path already exists; never overwrite' }
    New-Item -ItemType Directory -Path $SuiteDir -ErrorAction Stop | Out-Null
    $BaseTemp = Join-Path $SuiteDir 'basetemp'
    $Junit = Join-Path $SuiteDir 'junit.xml'
    $Stdout = Join-Path $SuiteDir 'stdout.txt'
    $Stderr = Join-Path $SuiteDir 'stderr.txt'
    $ExitFile = Join-Path $SuiteDir 'exit-code.txt'
    $Cwd = Join-Path $ActualWorktreeRoot $Suite.Cwd
    if (-not (Test-Path -LiteralPath $Cwd -PathType Container)) { throw "suite cwd missing: $Cwd" }
    $TargetArgs = @($Suite.Targets)
    $RunManifest = [ordered]@{
        suite = $Suite.Id; run_id = $RunId; cwd = [IO.Path]::GetFullPath($Cwd)
        interpreter = $ActualRuntime; python_version = $ActualPythonVersion.Trim()
        interpreter_sha256 = $ExpectedRuntimeSha256; pytest_version = $ActualPytest.Trim()
        argv = @($ActualRuntime,'-B','-m','pytest','-q','-ra','-p','no:cacheprovider') + $TargetArgs + @('--basetemp',$BaseTemp,'--junitxml',$Junit)
        basetemp = $BaseTemp; junit = $Junit; stdout = $Stdout; stderr = $Stderr; exit_file = $ExitFile
    }
    [IO.File]::WriteAllText((Join-Path $SuiteDir 'run-manifest.json'), ($RunManifest | ConvertTo-Json -Depth 6), [Text.UTF8Encoding]::new($false))
    Push-Location $Cwd
    try {
        & $ActualRuntime -B -m pytest -q -ra -p no:cacheprovider @TargetArgs --basetemp $BaseTemp --junitxml $Junit 1> $Stdout 2> $Stderr
        $ActualExit = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    [IO.File]::WriteAllText($ExitFile, [string]$ActualExit, [Text.UTF8Encoding]::new($false))
    if ($ActualExit -ne 0) { throw "$($Suite.Id) failed with exit $ActualExit; preserve all state and stop" }
}
```

每组单独新 UUID 目录，保留准确 cwd、完整 argv、stdout/stderr、实际 exit、JUnit 与 basetemp；在无损 UTF-8 campaign manifest 中逐组记账。任何失败立即停止，不清理、不重试、不继续下一组。上表六组是完整且唯一的授权候选；改变或增加 target 必须修订计划并重新获得明确批准。

## 6. 共享平台影响及 JSONL 独立复审

SC2 的 14 项包含平台 shared_tools/erp_connector/connector.py、shared_tools/models.py 和平台 test。其余 lane 均为各场景私有路径。该平台变更触及 get_receipt_batch 与 ReceiptRecord 共享合同；平台新增 BizType 316 定向测试通过不能认证全部共享消费者。整合复审需只读查看实际消费者调用及旧 receipt/report/window 行为。发现额外受影响消费者时停止并提交影响路径给审核人，未经单独测试批准不扩 pytest 范围。不因新实现改写旧 frozen snapshots、其它指标、订单/open CSV 或触发真实 ERP。

独立 review 只查新 Native 测试所产合成临时 JSONL / mock 数据及对应路径：
- SC4：核 source/evidence/run identity、source/content/lexicon/parser/profile hash、offset/status、真实 JSONL sink 与链。
- SC10：核 canonical manifest、批准 design 固定 scenario/action/evidence_contract/run_mode、professional_rule_version=not_applied、actor 与 chain。
- SC11：核 versioned create/revise 的 approved=false、review_status、完整 blocked_by、status/version/hash、JSONL chain；legacy draft API 不构成批准。
- O4：核类别中性 synthetic Stage0、预测/维护/spares/OEE null 或 not_evaluated、professional_signoff=None、真实 JsonlSink 与链。
- SC2：核 316 scoped rows 与旧共享 receipt 语义隔离。
若预期 JSONL 缺失、不是真实 sink、chain/identity 不符，或出现真实业务数据，立即停审并留证；不能用重造数据替代证据。

## 7. 完成、保留与权限边界

可交独立复审的条件：整合树五个提交顺序与 parent/path/blob/mode 核验全通过；六组获批定向测试全通过，JUnit failures/errors/skips 均逐项解释；JSONL 审阅完成；diff/status 精确且干净；保存 FrozenBaseSHA、Native identity、41 项最终绑定、全部命令/cwd/exit/stdout/stderr/JUnit/JSONL SHA。任何失败按第 4/5/6 节停止规则处理。

此任务不包含 master merge/FF、push/tag、部署、真实源/API、队列写入、正式计划修改或原候选归档。五个原候选树、分支、提交和封存证据都保留，不清理、不重置、不改写。

## 8. 本稿与新的授权哈希

ignored 候选稿 SHA 不作为 `alignment_plan_sha256`，不构成正式审批载体。正式计划 `docs/superpowers/plans/2026-10-10-five-candidates-alignment.md` 完成后，必须对其精确内容与预期 status 取证；其最终 SHA 和状态由 root 在新 auth 中绑定。旧 seal approval SHA `AA487190423E44493A7004DB487545B89B9B85D2C898F6E219A77C2BB1FAD665` 不可扩权复用。只有正式计划经独立复审并由审核人另行明确批准，root 才可在主仓固定绝对路径 `C:\Dev\zhuopin-ai\0-学习与工具\codex-handoff\五候选整合批准消费-2026-10-10.json` 创建本轮 auth；该 auth 需绑定批准原话/证据指针 SHA、正式计划 SHA及其预期 status、seal plan/正式 manifest/five summary SHA、五源 ref/commit/tree、固定 FrozenBaseSHA、Native 名称/能力、allowed root、branch、41-path/OID规则、runtime 的路径/hash/version、六组完整测试命令与证据根、限定例外及不执行 master/生产动作的边界。auth 中实际 Native `returned_root` 初值必须为 `null`，实际值由创建后的 identity evidence 绑定；不能因其未知阻塞事先审批。新授权未形成前不创建 Native、不 cherry-pick、不跑测试。auth 必须位于 §3.1 主仓源路径，由 root 在真实明确批准后创建；不要求它属于 FrozenBaseSHA，不把它复制入 Native。auth 自身的最终 SHA/status 记入独立 after-registration evidence，避免自引用。

## 根正式登记补记

2026-10-10T23:04:38.448112+08:00：根将此完整计划正式登记，manifest以正式 docs/superpowers/plans/five-candidates-seal-1010/manifest.json 为权威。新auth仅在真实明确批准后形成；批准前不要求未来auth存在。SC10/11的本次限定例外须本人新批，且其操作必须等EE5根作业完成/inactive再串行。未创建整合树、未cherry-pick、未跑六组测试。
