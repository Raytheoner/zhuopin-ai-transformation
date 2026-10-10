# 五候选串行对齐具体实施计划（修订供审）

状态：根正式登记的完整修订计划，尚未取得本版本执行批准。原2E3EEB…317C2待审稿及其问答不能启动本修订范围；必须针对本版本SHA及正式amendment/script取得新的明确批准。
目标：在新建 Native worktree 中，以固定 FrozenBaseSHA `310f54de71149b0cb0281749619ee3cd84f97bca` 为基线，将五个已封存候选按 SC2 → SC4 → SC10 → SC11 → O4 顺序正常 cherry-pick；逐项核对提交来源、白名单和 41 个最终文件 blob 与正式封存 manifest 一致；仅运行本稿列出的六组整合定向测试候选。SC10/SC11 的对齐和测试在真实执行时按当前 EE5 根作业状态和官方队列查询重新核验，只有 root status completed/inactive、Word QA/恢复闭环且本次独立 preflight 通过后才可串行执行；本稿不把旧观察 SHA/status 固定为常量。旧单 lane 测试授权不延伸至整合树。结果限于新 Native 和 ignored 证据，不进入 master，不 ff，不 push，不部署，不取真实数据。

## 1. 当前事实与执行边界

封存计划：docs/superpowers/plans/2026-10-10-five-candidates-seal.md，SHA-256 F9489E7A1729476F4068E80CA205F3AFE6A981C26F92D1278E3BED15C5953819。
封存 manifest：docs/superpowers/plans/five-candidates-seal-1010/manifest.json，SHA-256 A4996E4758B4A36326D95D87524EAC63F02135AF57A126135CF2CBA5C51D12DB。

旧批准消费件 0-学习与工具/codex-handoff/五候选本地提交批准消费-2026-10-10.json，SHA-256 AA487190423E44493A7004DB487545B89B9B85D2C898F6E219A77C2BB1FAD665。授权类型是 native_detached_candidate_commit_preservation，绑定共同父提交 28337c0ebb52afdbf61e955ecdbc22d151bcd185、旧封存计划/manifest 与五个精确路径白名单。该授权不覆盖 Native 整合、cherry-pick 或整合后复测；不能作为本次 authSHA。

本稿提出的新范围标识为 `sealed_candidate_alignment_verification_only`：仅对五个已经封存的提交和封存清单中的 41 个路径做合成对齐，并在全量对齐后运行本稿逐项列明的六组定向测试。该例外不重新解释或回查旧 global §三，不扩大或撤销旧冻结，不包含新场景建造、新参数、新默认值、业务口径变更、真实数据或额外测试。正式计划与新 auth 都须明确记录该范围，并由 Shao Peishen 对本完整计划所列 exact operations 单独批准；旧 seal 授权不延伸。

冻结基线固定为 committed SHA `310f54de71149b0cb0281749619ee3cd84f97bca`；这是本计划的固定输入，不在执行时另行挑选。主仓有其他既存 dirty，全部保留且不得带入 Native。本计划不要求主仓整体 clean。执行前须分别校验：41 个产品路径按 seal manifest 的原父提交状态应当在主仓 clean、无 index/worktree/untracked/conflict/ignored overlap；控制文件则按新 auth 逐项绑定的 expected porcelain status 与 SHA 检查，允许计划/授权文件自身处于已知 dirty 或 untracked 状态。控制文件只有缺失、冲突、内容 SHA 漂移或未列明状态变化才停止；唯一允许的状态变化是已绑定文档由 EE5 Sweep 从 dirty/untracked 转为 clean，且原始字节 SHA 不变、无冲突、HEAD blob 等于 filter 属性已核为 unset 后 `hash-object --path=<relative>` 得到的 Git 规范化 OID。不能把控制文件的预期 dirty/untracked 误判为产品 dirty。非控制、非 41 路径的历史 dirty 保留并记录，不触碰、不复制。新 Native 必须从上述固定 committed SHA 创建且自身 clean；不能从主仓 working-tree snapshot 创建。

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

正式对齐计划与本轮 auth 是控制文件，不属于 41 个产品路径。新 auth 必须逐个列明控制文件的绝对/相对路径、存在性、预期 Git porcelain-v2 状态、SHA256 和读取时点；允许正式计划处于预先声明的 dirty/untracked 状态，允许新 auth 在注册后为 untracked，不能把这类已绑定状态强制改成 clean。正式计划写入后、auth 登记后，root 必须把各自实际状态与 SHA 记入独立 after-registration evidence；auth 自身 SHA 由该独立证据绑定，避免自引用。正式计划当前缺失或冲突时不得批准；新 auth 只在真实批准后创建，不是批准前置。执行前须核 auth 存在、状态与独立哈希绑定；缺失或内容 SHA 漂移一律停止。若 EE5 Sweep 仅把已批准控制文档从 dirty/untracked 转为 clean，仍须核验原始字节 SHA 不变、无冲突，且 HEAD blob 等于已核 filter 属性 unset 后运行 `git hash-object --path=<relative> -- <exact-file>` 得到的 canonical OID；只接受这一明确转换，不接受其它状态变化。seal plan、manifest、summaries 等其余控制文件同样逐个绑定自己的预期状态与 SHA；它们的状态不要求与控制文件通用状态相同。

41 个产品路径则必须与第 2 节 seal manifest 的原父提交状态完全吻合：原有路径在主仓无 index/worktree dirty，无 untracked/ignored/conflict overlap；manifest 标为新增的 14 项在主仓应保持不存在。任何产品路径被修改、暂存、冲突、意外出现或与控制文件交叠都停止。控制文件允许状态与产品路径 clean 门槛严格分开。

执行前，对 41 个产品路径与所有控制文件分别核验绝对路径、存在性/预期不存在、expected porcelain status 与 SHA。Git 状态证据使用精确路径参数及 `--porcelain=v2 --untracked-files=all --ignored=matching`，并分别核未暂存与已暂存差异；该 status 必须在 §3.3 的 config/filter/hooks gates 后执行。控制文件按其 auth 声明的预期状态检查，允许计划/auth 的精确 dirty/untracked；若其状态因已绑定 Sweep 转 clean，仅在原始字节SHA不变、无冲突且HEAD blob等于已核filter属性unset后的规范化OID时接受。产品路径必须 clean、无冲突且与控制文件无 overlap。其它控制文件或产品路径任何意外缺失、漂移、冲突、未允许状态变化或 hash 不符都停止。FrozenBaseSHA 固定为 `310f54de71149b0cb0281749619ee3cd84f97bca` 并写入证据；检查其对 41 路径的 tree blob/mode 与共同父提交：新增项仍不存在，既存项 blob/mode 相同；另检查共同父提交至 FrozenBaseSHA 的 committed path diff 与 41 路径交集为空。主仓其它历史 dirty 原样保留，只记录审查所需状态摘要，不触碰、不复制、不要求整体 clean。

### 3.3 SC10/SC11 前置门、正式对象与证据契约

本次 auth 是独立批准消费件 `0-学习与工具/codex-handoff/五候选整合批准消费-2026-10-10.json`。它必须绑定批准原话和证据SHA、正式对齐计划 SHA、正式 amendment SHA、正式 preflight 脚本 SHA、封存 manifest/五份 summaries/各 source ref+commit+tree、FrozenBaseSHA、41 项 path/blob/mode、固定测试矩阵/runtime、Native 能力及允许根、scope exception 和四项 SC10/SC11 操作。auth 仅在真实批准后创建；批准前不需要预先存在，也不以旧候选提交批准扩权。其 `ee5_gate` 在消费时以真实状态文件内容为准，冻结两个 JSON 的 SHA 和字段：root `status=completed`、`ee5_root_operation_active=false`；冻结执行记录 `word_qa_completed=true`、`restored=true`、`total_table_written=true`；`scope_limit` 只证明该根作业状态，不证明 §三 无冻结或解冻。字节数与 mtime 只作消费时观察证据，非内容身份常量。每次运行检查当前文件 SHA/字段仍吻合消费快照；不把本稿早前旧观察 SHA/status 当约束。

新 auth 的 `controls[]` 精确列出控制路径、原始文件 SHA、消费时预期 porcelain-v2 与状态来源。auth 自身不自引；auth SHA/status 由其 `after_registration_evidence_path` 指向的独立 registration JSON 绑定。registration JSON 必须列明 auth 绝对路径/SHA/porcelain、正式计划SHA、正式amendment SHA及与 auth controls 一一对应的路径/SHA/status。preflight 必须显式接收 `-RegistrationEvidencePath` 并核对该 JSON。若控制文件 status 在 EE5 Sweep 后由冻结 dirty/untracked 变 clean，只在原始内容SHA仍不变、无冲突且 HEAD blob 等于 `git hash-object --path=<relative> -- <exact-file>` 的 Git 内建 text/eol canonical OID 时接受；此前已逐 path 核对 `filter` 属性为 unspecified/unset，无外部 filter。其它状态变化 fail closed。

Native 返回路径事先未知，auth 的 `native.returned_root` 初值必须为 null；Native 创建后根独立登记 after-create checkpoint，精确绑定工具返回的实际 root、HEAD、branch、status、Git selected-config inventory SHA、hooks inventory SHA。每个操作完成后根写新 checkpoint，`operation` 指向下一个动作。SC10/SC11 preflight 只读并核对该 checkpoint 的实际 root、固定 expected branch、HEAD/ref/status、config/hooks SHA。checkpoint 是执行证据，不得扩大授权。

每次 SC10/SC11 cherry-pick 前及每次相应测试前，都重新调用官方队列工具：固定 `--file C:/Dev/zhuopin-ai/1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md`、指定 `--row 468/469 --section 一`；默认 `--format json` 不附 `--field`，核验 JSON `found=true`、`row` 为对应字符串、存在 `status_field` 并保存完整输出；另以独立 `--field status` 查询保存状态字段文本和真实 exit。每次查询输出保存至本次新 evidence UUID 下唯一文件并取 SHA。只使用官方查询，不读/grep 队列真身；无法查询或信息不足即停，不猜测 §三 已解冻。

正式执行副本固定为 `C:\Dev\zhuopin-ai\docs\superpowers\plans\five-candidates-seal-1010\preflight_ee5_and_git.ps1`；正式 amendment 为同 pack 的 `alignment-amendment.md`。两件正式成件供审阅后，auth 绑定正式计划、正式 amendment、正式脚本各自实际 SHA。ignored 合并稿及 ignored amendment/script 不是执行来源。preflight 参数含 Lane、Step、AuthorizationPath、RegistrationEvidencePath、NativeRoot、最新 checkpoint path 和新 evidence JSON path；每次只向新 evidence 路径写一份 preflight JSON。Gate 必须成功才进入对应 Git mutation/test；失败保留证据与原状态并停止。

Git 固定绝对 executable `C:\Program Files\Git\cmd\git.exe`；批准消费时重新取SHA与 `--version`，未取得或与绑定不符即停。不得换到其他安装路径。preflight 仅读取选定 `core.hookspath`、`core.fsmonitor`、`commit.gpgsign`、`gpg.program`、`include.path`、`includeif.*.path` 及 `filter.*` 配置；记录来源文件路径/SHA，filter 命令值只记 SHA，不展开 credentials/config全文。`core.fsmonitor` 必须 unset/false/0/no；signing 若显式存在仅允许 false/0/no，未批准未知值一律失败，不关闭签名、不绕 hook。逐项检查 41 产品路径与主仓 controls/auth/registration 的有效 `filter` 属性，只接受 unspecified/unset；查中文路径时仅以单条命令 `-c core.quotepath=false`，不写配置。环境只允许 GIT_PAGER（Git argv 均显式 `--no-pager`）、值恰为0的 GIT_OPTIONAL_LOCKS/GIT_TERMINAL_PROMPT；其他非空 GIT_* 控制环境变量 fail closed。

任何 `git status` 之前，preflight 顺序必须是：auth/registration/formal SHA/EE5闭环字段核验；Git exe/config来源和 fsmonitor/signing gate；41 路径与主仓控制文件 filter attributes gate；main/native hooks 有效目录逐文件 SHA inventory。未知/非 `.sample` hook 文件、reparse point、解析失败或inventory变化全部停交人审，不执行、不删除、不关闭。所有 Git argv 用 `--no-pager --no-optional-locks`。这些 gate 通过后才可运行 Native 完整 worktree `status --porcelain=v2 --untracked-files=all` 并要求为空，然后核 controls/auth 的逐路径 status及清洁转换，最后记录 Native 的41路径状态。全树clean不能由41路径检查替代；不可另在 gate 外预跑 status。读命令失败同样停并留新 UUID 证据。

## 4. 新 Native 与串行整合方案

Native 名称固定 `five-candidates-align-1010`；分支名固定 `codex/five-candidates-align-1010`。新授权绑定 Native 工具能力、FrozenBaseSHA 与 allowed root `C:\Users\Paul Shao\.codex\worktrees\`；实际 returned root 仅在创建后的 identity evidence 中绑定。新树只从授权记录绑定的 FrozenBaseSHA 创建。原五个 candidate worktree/ref/证据全程只读保留，不 reset/rebase/clean/覆盖/归档。

新 Native 创建后，先记录工具返回的 WorktreeRoot、HEAD、branch 和绝对路径；实际路径必须在授权 allowed root 下，HEAD 必须等于 FrozenBaseSHA。首次读取 Git status 前，先按本计划的 Git config/fsmonitor、41+control filter attributes 和有效 hooks inventory gates 检查主仓与 Native，再读取 Native 完整 status 并要求为空；不能由 Native API之外的裸 status 提前检查。将路径/HEAD/branch/status/config SHA/hooks inventory SHA写入首个 after-create checkpoint，operation 指向下一个步骤。确认固定分支名不存在后再切换到它并再次遵守 status 前置 gates。不得把主仓 dirty snapshot 复制进 Native。

EE5 是 SC10/SC11 的串行前置闸。SC2、SC4 可按顺序进行；SC4 后必须停在检查点。SC10/SC11 每次 cherry-pick 和每次对应测试之前，均重新以当前官方查询与两份 EE5 状态 JSON核验，且须通过绑定当前 operation checkpoint 的preflight。只有 root status completed/inactive、执行记录 Word QA/restore/total table 字段闭环、SHA仍匹配本次 auth消费冻结值且官方查询可读，才允许此步。SC10 完成后再进行 SC11；不得并行。六组测试只在所有前置闸闭合、五项对齐完成后按第5节逐组执行。不据历史状态或旧观察SHA下结论，不读取或改写队列真身。

Git executable 固定绝对路径 `$GitExe='C:\Program Files\Git\cmd\git.exe'`，并在 auth 中绑定 SHA/version；所有命令使用固定可执行文件，不调用 PATH 中裸 `git`。按 SC2、SC4、SC10、SC11、O4 五提交顺序执行普通 `cherry-pick`，不 squash、不 rebase、不用 `-X ours/theirs`、不手工应用 patch。全部五个 SHA 是第 2 节表内固定字面值；每次只对当前一个 commit 执行，紧接捕获 exit 并留完整 stdout/stderr/命令证据，exit 非零立即停止。Git config/hooks/filter gates 通过后方可 status。SC10、SC11 的调用前必须执行 `Invoke-AlignmentGate`；若 query/preflight 任一退出码非零，停止且绝不进入 Git mutation。gate 输出证据位于本次新 UUID `$PreflightEvidenceDir`，checkpoint 必须指向正执行的 `Lane:Step`：

```powershell
$GitExe = 'C:\Program Files\Git\cmd\git.exe'
$AuthPath = 'C:\Dev\zhuopin-ai\0-学习与工具\codex-handoff\五候选整合批准消费-2026-10-10.json'
$Auth = Get-Content -LiteralPath $AuthPath -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
$QueueQuery = 'C:\Dev\zhuopin-ai\0-学习与工具\工具-队列查询.py'
$QueueFile = 'C:\Dev\zhuopin-ai\1-转型规划\0-全景路线图\跨桌任务队列-业务场景.md'
$QueuePython = 'C:\Dev\Codex\runtimes\zhuopin-ai\venv\Scripts\python.exe'
$PwshExe = 'C:\Users\Paul Shao\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe'
$PreflightScript = 'C:\Dev\zhuopin-ai\docs\superpowers\plans\five-candidates-seal-1010\preflight_ee5_and_git.ps1'
$RegistrationEvidencePath = [IO.Path]::GetFullPath($Auth.after_registration_evidence_path)
if (-not (Test-Path -LiteralPath $PwshExe -PathType Leaf) -or (Get-FileHash -LiteralPath $PwshExe -Algorithm SHA256).Hash -cne $Auth.runtime.pwsh_sha256 -or $Auth.runtime.pwsh_path -cne $PwshExe) { throw 'PowerShell runtime identity differs from auth; stop' }
if (-not (Test-Path -LiteralPath $QueuePython -PathType Leaf) -or (Get-FileHash -LiteralPath $QueuePython -Algorithm SHA256).Hash -cne $Auth.runtime.python_sha256) { throw 'queue/test Python runtime identity differs from auth; stop' }
$PreflightRunId=[guid]::NewGuid().ToString()
$PreflightEvidenceDir=Join-Path 'C:\Dev\zhuopin-ai\reports\candidate-integration-1010' $PreflightRunId
if(Test-Path -LiteralPath $PreflightEvidenceDir){throw 'preflight evidence UUID exists; never overwrite'}
New-Item -ItemType Directory -Path $PreflightEvidenceDir -ErrorAction Stop|Out-Null

function Write-UniqueUtf8([string]$Path,[string]$Text) {
    $bytes=[Text.UTF8Encoding]::new($false).GetBytes($Text)
    $stream=[IO.File]::Open($Path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try { $stream.Write($bytes,0,$bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
    return [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes))
}
function Invoke-AlignmentGate([string]$Lane,[string]$Step,[string]$CheckpointPath) {
    $script:GateExitCode=$null
    $script:LastGateQueryIndex=$null; $script:LastGatePreflightPath=$null; $script:LastGateStage='queue_query_started'
    $queryEvidence=@()
    $GateId=[guid]::NewGuid().ToString()
    foreach ($row in @(468,469)) {
        $json=@(& $QueuePython -B $QueueQuery --file $QueueFile --row $row --section '一' --format json 2>&1)
        $jsonExit=$LASTEXITCODE
        $script:GateExitCode=$jsonExit
        if ($jsonExit -ne 0) { throw "official full-row query failed for $row; stop before $Lane $Step" }
        $parsed=(($json -join "`n") | ConvertFrom-Json)
        if ($parsed.found -ne $true -or [string]$parsed.row -cne [string]$row -or $null -eq $parsed.PSObject.Properties['status_field']) { throw "official row JSON identity/schema invalid for $row" }
        $jsonPath=Join-Path $PreflightEvidenceDir "queue-$Lane-$Step-$GateId-$row-all.json"
        $jsonSha=Write-UniqueUtf8 $jsonPath (($json -join "`n")+"`n")
        $queryEvidence += [ordered]@{ row=[string]$row; kind='full_json'; path=$jsonPath; sha256=$jsonSha; actual_exit=$jsonExit }
        $status=@(& $QueuePython -B $QueueQuery --file $QueueFile --row $row --section '一' --field status 2>&1)
        $statusExit=$LASTEXITCODE
        $script:GateExitCode=$statusExit
        if ($statusExit -ne 0) { throw "official status-field query failed for $row; stop before $Lane $Step" }
        $statusPath=Join-Path $PreflightEvidenceDir "queue-$Lane-$Step-$GateId-$row-status.txt"
        $statusSha=Write-UniqueUtf8 $statusPath (($status -join "`n")+"`n")
        $queryEvidence += [ordered]@{ row=[string]$row; kind='status_text'; path=$statusPath; sha256=$statusSha; actual_exit=$statusExit }
    }
    $queryIndex=Join-Path $PreflightEvidenceDir "queue-$Lane-$Step-$GateId-readback.json"
    $null=Write-UniqueUtf8 $queryIndex (($queryEvidence | ConvertTo-Json -Depth 5)+"`n")
    $script:LastGateQueryIndex=$queryIndex; $script:LastGateStage='queue_query_recorded'
    $evidence=Join-Path $PreflightEvidenceDir "preflight-$Lane-$Step-$GateId.json"
    $script:LastGatePreflightPath=$evidence; $script:LastGateStage='preflight_started'
    & $PwshExe -NoProfile -File $PreflightScript -Lane $Lane -Step $Step `
      -AuthorizationPath $AuthPath -RegistrationEvidencePath $RegistrationEvidencePath `
      -NativeRoot $ActualWorktreeRoot -CheckpointPath $CheckpointPath -EvidencePath $evidence
    $gateExit=$LASTEXITCODE
    $script:GateExitCode=$gateExit
    if ($gateExit -ne 0) { throw "$Lane $Step preflight failed; preserve state and stop" }
    $script:LastGateStage='preflight_passed'
    return $evidence
}

function Invoke-RecordedCherryPick([string]$Lane,[string]$Commit) {
    $outPath=Join-Path $PreflightEvidenceDir "cherry-pick-$Lane.stdout.txt"
    $errPath=Join-Path $PreflightEvidenceDir "cherry-pick-$Lane.stderr.txt"
    $exitPath=Join-Path $PreflightEvidenceDir "cherry-pick-$Lane.exit.txt"
    $recordPath=Join-Path $PreflightEvidenceDir "cherry-pick-$Lane.argv.json"
    foreach($path in @($outPath,$errPath,$exitPath,$recordPath)){if(Test-Path -LiteralPath $path){throw 'cherry-pick evidence path exists; never overwrite'}}
    $argv=@($GitExe,'--no-pager','--no-optional-locks','-C',$ActualWorktreeRoot,'cherry-pick',$Commit)
    & $GitExe --no-pager --no-optional-locks -C $ActualWorktreeRoot cherry-pick $Commit 1> $outPath 2> $errPath
    $actualExit=$LASTEXITCODE
    $record=[ordered]@{lane=$Lane;argv=$argv;actual_exit=$actualExit;stdout_path=$outPath;stdout_sha256=(Get-FileHash -LiteralPath $outPath -Algorithm SHA256).Hash;stderr_path=$errPath;stderr_sha256=(Get-FileHash -LiteralPath $errPath -Algorithm SHA256).Hash;recorded_utc=[DateTime]::UtcNow.ToString('o')}
    $null=Write-UniqueUtf8 $recordPath (($record|ConvertTo-Json -Depth 5)+"`n")
    $null=Write-UniqueUtf8 $exitPath ([string]$actualExit+"`n")
    if($actualExit -ne 0){throw "$Lane cherry-pick failed; preserve Native/index and stop"}
}
```

checkpoint schema至少包含 `operation`、`native.returned_root`、`native.head`、`native.branch`、`native.expected_branch`、`native.status`、`native.config_sha256`、`native.hook_inventory_sha256`。在每个 lane 操作前，root 单独创建新的唯一 checkpoint 文件，写明该操作并把新绝对路径作为当次调用参数；调用成功后保留该 checkpoint，下一动作另建文件，绝不原位覆写或依赖 shell 变量。SC4 后指向 `SC10:cherry-pick`，SC10 cherry-pick 后指向 `SC11:cherry-pick`；五提交结束后分别指向 `SC10:tests`、`SC11:tests`。checkpoint更新不改变授权。每次调用都须在该调用文本中重新提供绝对 Git 路径、实际 NativeRoot、证据 UUID 与对应 helper 定义，不依赖上一 PowerShell 进程。

```powershell
# 每个命令单独调用；每次调用前 root 写一个新的、唯一且不可覆盖的 checkpoint 路径。
Invoke-RecordedCherryPick -Lane 'SC2' -Commit 'fe49e42a05b63ee41948be93c19a24989453d184'
Invoke-RecordedCherryPick -Lane 'SC4' -Commit '91faf5b4c56e162011a5b56796170e9b212f1359'
# root 先登记 SC10:cherry-pick checkpoint；将新路径传给此 gate。
Invoke-AlignmentGate -Lane 'SC10' -Step 'cherry-pick' -CheckpointPath $Sc10PickCheckpointPath
Invoke-RecordedCherryPick -Lane 'SC10' -Commit '25eb192258fcd6ce51e654ec01c62918486c7736'
# root 先登记 SC11:cherry-pick checkpoint；将新路径传给此 gate。
Invoke-AlignmentGate -Lane 'SC11' -Step 'cherry-pick' -CheckpointPath $Sc11PickCheckpointPath
Invoke-RecordedCherryPick -Lane 'SC11' -Commit '6990139aca37e1252684ef051685198bc7e0c9a1'
Invoke-RecordedCherryPick -Lane 'O4' -Commit '6a11819da67902eaa9ae934e061c607c24fcc624'
```

上面列出执行顺序；每个 lane 命令作为独立 PowerShell invocation 执行，不能依赖前一次进程的函数或变量。实际执行时把前一代码块中 `Invoke-RecordedCherryPick` 的完整定义、其所需固定绝对 Git/Native/evidence 参数和本次单独动作放进同一 invocation；SC10/SC11 还须把新的唯一路径传给 `Invoke-AlignmentGate`。每步之间必须完成以下前后核验与留证。
- 源 commit 可解析，唯一 parent 是共同父提交。
- 表中每个 source ref 必须解析到对应的固定 commit SHA；只证明 commit SHA 可解析不够。
- source tree 等于 formal plan 记录：SC2 8ce16b268ebe8ce5dc4418a0aab0063b782aae8c；SC4 ad1163674ded48a52bfaced0288f35637e1d78a0；SC10 4b5097ac312adf338eca91d41eab5ef9d0751515；SC11 cf0ee4b32951869ea10c206b4274cfaa4f49d75c；O4 e92b623448a4478bd4f1e8033c2f7bfd7c723e09。
- source commit 的 diff-tree 路径集与本 lane manifest 白名单完全相等，数量依次为 14/8/4/7/8；逐项 candidate blob OID 与 manifest 相等，mode 相同。
- cherry-pick 后 HEAD 的唯一 parent 是执行前 HEAD；新提交路径仅为此 lane 白名单；逐项 HEAD blob/mode 与 manifest 相等；新 Native status 为空。

最后验证 FrozenBaseSHA 是整合 HEAD 祖先；FrozenBaseSHA..HEAD 路径集合恰等于 41 白名单；所有 41 blob/mode 与 manifest 相等；first-parent 新增提交顺序恰为五 lane 顺序；新 Native 干净。命令完整 argv、stdout/stderr、exit 都进审核证据。

任何产品路径 dirty/overlap、控制文件状态/hash 与 auth 绑定不符、源 ref/OID/tree/path 漂移、目标路径基线变动、冲突或非零退出，均在该步停止并保留新 Native/index 状态供复审；控制文件只有偏离自身预期状态才停止，不因其已绑定的 dirty/untracked 状态停止。不运行 cherry-pick --abort、不手改冲突、不跳 lane、不重试覆盖。原候选树永不更改。

## 5. 精确定向测试矩阵（须新批准后才运行）

每个候选已在各自 sealed tree 验证；这不证明新整合树。alignment 人批记录须显式授权下面六组，不扩展到本表外测试。测试文件字面值从五份原具体计划逐项核取；SC10 四个文件沿用其批准范围，不能因 sealed commit 触及较少测试就自行缩减整合验收。

SC10/SC11 测试每次启动前都以当时根作业状态和官方查询重新核验；必须已完成 EE5 根作业、`ee5_root_operation_active=false`、执行记录 QA/恢复/总表字段闭环、状态 SHA 与消费授权快照相符，并由正式 preflight 通过。仅在 SC10 对齐完成且相应检查点更新后运行 SC10 测试；SC10 测试成功并更新检查点后，才可通过新一轮 gate 运行 SC11 测试。不以其他场景测试已通过代替此闸。

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

唯一测试入口固定为下方 PowerShell 模板。调用方每次显式提供 `$SuiteId`、`$CheckpointPath`、`$WorktreeRoot`、`$MainEvidenceRoot`、`$CampaignId`、`$ApprovedPlanSha256`、`$ApprovedAuthorizationSha256` 与 runtime identity；每次 invocation 仅执行一个 suite，不依赖持久 PowerShell 变量。首次 SC2 调用用批准后生成的 CampaignId 初始化 campaign；后续调用从同 CampaignId 的 manifest 与 readback JSONL 读回并校验内容 SHA、最后 ledger SHA、suite 状态和完整固定 targets，再执行唯一下一组。root 按 suite 逐次发起新 invocation；SC10/SC11 suite 前分别重新取得 EE5/官方队列结果和新的唯一 checkpoint 文件路径。SC10 suite 完成后本次 invocation 正常退出；root 更新 checkpoint，再以新 invocation 启动 SC11 suite。任何中断、manifest/readback 不一致、suite 不处于 pending 或前置 suite 未 passed 时 fail closed，不覆盖已有证据。`$SuiteId` 是本次唯一目标，必须从六个固定 Id 中精确选择；`$WorktreeRoot` 只能取 Native 工具返回的实际路径，且必须解析位于 `C:\Users\Paul Shao\.codex\worktrees\` 下；`$MainEvidenceRoot` 固定为主仓 ignored 根 `C:\Dev\zhuopin-ai\reports\candidate-integration-1010`；`$CampaignId` 与每组新 `$RunId` 均为批准后生成的 GUID。每组 cwd 和 target 是固定字面值，不得目录枚举、自动发现或补测。审批绑定此命令文本的 SHA、六组固定矩阵、runtime 与 evidence root。批准前不建目录、不运行测试。

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
if($SuiteId -in @('SC10','SC11')){$CheckpointPath=[IO.Path]::GetFullPath($CheckpointPath);if(-not(Test-Path -LiteralPath $CheckpointPath -PathType Leaf)){throw 'required unique suite checkpoint missing'}}elseif(-not[string]::IsNullOrWhiteSpace($CheckpointPath)){throw 'non-gated suite must not receive a checkpoint path'}
$IsNewCampaign = -not (Test-Path -LiteralPath $CampaignDir)
if ($IsNewCampaign -and $SuiteId -cne 'SC2') { throw 'only first SC2 invocation may create a campaign' }
$ActualRuntime = [IO.Path]::GetFullPath($ExpectedRuntime)
if (-not (Test-Path -LiteralPath $ActualRuntime -PathType Leaf)) { throw 'approved runtime missing' }
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $ActualRuntime).Hash -ne $ExpectedRuntimeSha256) { throw 'approved runtime SHA mismatch' }
$ActualPythonVersion = & $ActualRuntime -B --version
if ($LASTEXITCODE -ne 0 -or $ActualPythonVersion.Trim() -ne $ExpectedPythonVersion) { throw 'Python version mismatch' }
$ActualPytest = & $ActualRuntime -B -c "import importlib.metadata as m; print(m.version('pytest'))"
if ($LASTEXITCODE -ne 0 -or $ActualPytest.Trim() -ne $ExpectedPytestVersion) { throw 'pytest version mismatch' }
if ($IsNewCampaign) { New-Item -ItemType Directory -Path $CampaignDir -ErrorAction Stop | Out-Null }

$Suites = @(
    @{ Id='SC2'; Cwd='4-数字员工/采购部/SC2-采购周报自动生成'; Targets=@('tests/test_detail.py','tests/test_metrics.py','tests/test_report.py','tests/test_sources.py') },
    @{ Id='PLATFORM'; Cwd='5-平台底座/zhuopin_platform'; Targets=@('tests/test_erp_biztype316.py') },
    @{ Id='SC4'; Cwd='4-数字员工/采购部/SC4-合同条款自动提取与审核'; Targets=@('tests/test_text_source.py','tests/test_clause_extract.py','tests/test_agent_audit.py') },
    @{ Id='SC10'; Cwd='4-数字员工/采购部/SC10-BOM评审与物料库管控'; Targets=@('tests/test_evidence.py','tests/test_review_facts.py','tests/test_agent_audit.py','tests/test_pending_gates.py') },
    @{ Id='SC11'; Cwd='4-数字员工/采购部/SC11-库存智能调拨'; Targets=@('tests/test_shared_reservation.py','tests/test_versioned_audit_gate.py','tests/test_pmc_gate.py') },
    @{ Id='O4'; Cwd='4-数字员工/运营部/O4-设备预测性维护'; Targets=@('tests/test_stage0.py') }
)
$CampaignManifestPath = Join-Path $CampaignDir 'campaign-manifest.json'
$CampaignManifestTemp = $CampaignManifestPath + '.tmp'
$CampaignReadbackPath = Join-Path $CampaignDir 'campaign-manifest-readbacks.jsonl'
$SelectedSuites=@($Suites | Where-Object { $_.Id -ceq $SuiteId })
if($SelectedSuites.Count -ne 1){throw 'SuiteId must exactly match one fixed suite Id'}
if(Test-Path -LiteralPath $CampaignManifestTemp){throw 'campaign manifest temp exists; preserve and stop'}
if($IsNewCampaign){
    if ((Test-Path -LiteralPath $CampaignManifestPath) -or (Test-Path -LiteralPath $CampaignReadbackPath)) { throw 'campaign files exist without campaign directory initialization; stop' }
$CampaignRecord = [ordered]@{
        schema='five-candidate-alignment-campaign/v1'; campaign_id=$CampaignId
        plan_sha256=$ApprovedPlanSha256; authorization_sha256=$ApprovedAuthorizationSha256
        interpreter=$ActualRuntime; interpreter_sha256=$ExpectedRuntimeSha256; worktree_root=$ActualWorktreeRoot
        python_version=$ActualPythonVersion.Trim(); pytest_version=$ActualPytest.Trim()
        suites=@($Suites | ForEach-Object { [ordered]@{ id=$_.Id; cwd=$_.Cwd; targets=@($_.Targets); status='pending'; run_id=$null; argv=$null; basetemp=$null; junit=$null; stdout=$null; stderr=$null; exit_file=$null; run_manifest=$null; gate_query_index=$null; preflight_json=$null; gate_stage=$null; gate_exit=$null; actual_exit=$null; error_type=$null } })
    }
    $readbackInit=[IO.File]::Open($CampaignReadbackPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
    $readbackInit.Dispose()
    $script:CampaignReadbackSequence=0
}else{
    if(-not(Test-Path -LiteralPath $CampaignManifestPath -PathType Leaf) -or -not(Test-Path -LiteralPath $CampaignReadbackPath -PathType Leaf)){throw 'campaign manifest/readback missing; preserve and stop'}
    $CampaignRecord=Get-Content -LiteralPath $CampaignManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
    if($CampaignRecord.schema -cne 'five-candidate-alignment-campaign/v1' -or $CampaignRecord.campaign_id -cne $CampaignId -or $CampaignRecord.plan_sha256 -cne $ApprovedPlanSha256 -or $CampaignRecord.authorization_sha256 -cne $ApprovedAuthorizationSha256 -or $CampaignRecord.interpreter -cne $ActualRuntime -or $CampaignRecord.interpreter_sha256 -cne $ExpectedRuntimeSha256 -or $CampaignRecord.worktree_root -cne $ActualWorktreeRoot -or $CampaignRecord.python_version -cne $ActualPythonVersion.Trim() -or $CampaignRecord.pytest_version -cne $ActualPytest.Trim()){throw 'campaign identity differs from approved continuation inputs'}
    if($CampaignRecord.suites.Count -ne $Suites.Count){throw 'campaign suite count differs from fixed matrix'}
    for($i=0;$i -lt $Suites.Count;$i++){if($CampaignRecord.suites[$i].id -cne $Suites[$i].Id -or $CampaignRecord.suites[$i].cwd -cne $Suites[$i].Cwd -or (ConvertTo-Json -Compress -InputObject @($CampaignRecord.suites[$i].targets)) -cne (ConvertTo-Json -Compress -InputObject @($Suites[$i].Targets))){throw 'campaign suite target binding differs from fixed matrix'}}
    $events=@(Get-Content -LiteralPath $CampaignReadbackPath -Encoding UTF8 | Where-Object { $_.Length -gt 0 } | ForEach-Object { $_ | ConvertFrom-Json -AsHashtable })
    if($events.Count -lt 1){throw 'campaign readback has no initialization evidence'}
    for($i=0;$i -lt $events.Count;$i++){if($events[$i].sequence -ne ($i+1) -or $events[$i].readback_matches_serialized_bytes -ne $true){throw 'campaign readback sequence/content claim invalid'}}
    $currentSha=(Get-FileHash -LiteralPath $CampaignManifestPath -Algorithm SHA256).Hash
    if($events[-1].manifest_sha256 -cne $currentSha){throw 'campaign latest manifest SHA does not match last readback event'}
    $script:CampaignReadbackSequence=$events.Count
}
$script:CampaignTransition='campaign_initialized'; $script:CampaignSuiteId=$null; $script:CampaignSuiteExit=$null
$script:GateExitCode=$null
function Write-CampaignManifest {
    if (Test-Path -LiteralPath $CampaignManifestTemp) { throw 'campaign manifest temp exists; preserve and stop' }
    $json=($CampaignRecord | ConvertTo-Json -Depth 8)+"`n"
    $expectedBytes=[Text.UTF8Encoding]::new($false).GetBytes($json)
    $manifestStream=[IO.File]::Open($CampaignManifestTemp,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try{$manifestStream.Write($expectedBytes,0,$expectedBytes.Length);$manifestStream.Flush($true)}finally{$manifestStream.Dispose()}
    [IO.File]::Move($CampaignManifestTemp,$CampaignManifestPath,$true)
    $actualBytes=[IO.File]::ReadAllBytes($CampaignManifestPath)
    if ([Convert]::ToBase64String($actualBytes) -cne [Convert]::ToBase64String($expectedBytes)) { throw 'campaign manifest readback bytes differ; preserve and stop' }
    $manifestSha=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($actualBytes))
    $event=[ordered]@{
        schema='campaign-manifest-readback/v1'; sequence=($script:CampaignReadbackSequence+1)
        transition=$script:CampaignTransition; suite_id=$script:CampaignSuiteId; suite_gate_or_test_exit=$script:CampaignSuiteExit
        suite_state=@($CampaignRecord.suites | ForEach-Object { [ordered]@{ id=$_.id; status=$_.status; basetemp=$_.basetemp; junit=$_.junit; stdout=$_.stdout; stderr=$_.stderr; exit_file=$_.exit_file; run_manifest=$_.run_manifest; gate_query_index=$_.gate_query_index; preflight_json=$_.preflight_json; gate_stage=$_.gate_stage; gate_exit=$_.gate_exit; actual_exit=$_.actual_exit } })
        manifest_path=$CampaignManifestPath; manifest_bytes=$actualBytes.Length; manifest_sha256=$manifestSha
        readback_matches_serialized_bytes=$true; recorded_utc=[DateTime]::UtcNow.ToString('o')
    }
    $line=($event | ConvertTo-Json -Depth 8 -Compress)+"`n"
    $eventBytes=[Text.UTF8Encoding]::new($false).GetBytes($line)
    $stream=[IO.File]::Open($CampaignReadbackPath,[IO.FileMode]::Append,[IO.FileAccess]::Write,[IO.FileShare]::Read)
    try { $stream.Write($eventBytes,0,$eventBytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
    $script:CampaignReadbackSequence++
    return $manifestSha
}
if($IsNewCampaign){$null=Write-CampaignManifest}

$script:LastGateQueryIndex=$null; $script:LastGatePreflightPath=$null; $script:LastGateStage=$null
$selectedIndex=-1
for($i=0;$i -lt $CampaignRecord.suites.Count;$i++){if($CampaignRecord.suites[$i].id -ceq $SuiteId){$selectedIndex=$i;break}}
if($selectedIndex -lt 0){throw 'selected suite missing from persisted fixed matrix'}
if($CampaignRecord.suites[$selectedIndex].status -cne 'pending'){throw 'selected suite is not pending; never rerun or overwrite a suite'}
for($i=0;$i -lt $selectedIndex;$i++){if($CampaignRecord.suites[$i].status -cne 'passed'){throw 'a preceding suite is not passed; stop campaign progression'}}

$Suite=$SelectedSuites[0]
    if ($Suite.Id -in @('SC10','SC11')) {
        $PreflightEvidenceDir=$CampaignDir
        try { Invoke-AlignmentGate -Lane $Suite.Id -Step 'tests' -CheckpointPath $CheckpointPath }
        catch {
            $idx=-1; for($i=0;$i -lt $CampaignRecord.suites.Count;$i++){if($CampaignRecord.suites[$i].id -eq $Suite.Id){$idx=$i;break}}
            if($idx -lt 0){throw 'preflight suite missing from campaign manifest'}
            $CampaignRecord.suites[$idx].status='preflight_failed'
            $CampaignRecord.suites[$idx].gate_query_index=if($script:LastGateQueryIndex -and (Test-Path -LiteralPath $script:LastGateQueryIndex -PathType Leaf)){$script:LastGateQueryIndex}else{$null}
            $CampaignRecord.suites[$idx].preflight_json=if($script:LastGatePreflightPath -and (Test-Path -LiteralPath $script:LastGatePreflightPath -PathType Leaf)){$script:LastGatePreflightPath}else{$null}
            $CampaignRecord.suites[$idx].gate_stage=if($script:LastGatePreflightPath -and -not(Test-Path -LiteralPath $script:LastGatePreflightPath)){'preflight_no_result'}else{$script:LastGateStage}
            $CampaignRecord.suites[$idx].gate_exit=$script:GateExitCode
            $CampaignRecord.suites[$idx].actual_exit=$null
            $CampaignRecord.suites[$idx].error_type=$_.Exception.GetType().FullName
            $script:CampaignTransition='preflight_failed'; $script:CampaignSuiteId=$Suite.Id; $script:CampaignSuiteExit=$script:GateExitCode
            $null=Write-CampaignManifest
            throw "$($Suite.Id) preflight failed; preserve evidence and stop before pytest"
        }
    }
    $RunId=[guid]::NewGuid().ToString()
    $SuiteParent=Join-Path $CampaignDir $Suite.Id
    if((Test-Path -LiteralPath $SuiteParent -PathType Container) -and @(Get-ChildItem -LiteralPath $SuiteParent -Directory -Force).Count -gt 0){throw 'suite has prior run evidence while persisted state is pending; preserve and stop'}
    if(-not(Test-Path -LiteralPath $SuiteParent -PathType Container)){New-Item -ItemType Directory -Path $SuiteParent -ErrorAction Stop|Out-Null}
    $SuiteDir=Join-Path $SuiteParent $RunId
    if(Test-Path -LiteralPath $SuiteDir){throw 'suite evidence path exists; never overwrite'}
    New-Item -ItemType Directory -Path $SuiteDir -ErrorAction Stop|Out-Null
    $BaseTemp=Join-Path $SuiteDir 'basetemp'; $Junit=Join-Path $SuiteDir 'junit.xml'
    $Stdout=Join-Path $SuiteDir 'stdout.txt'; $Stderr=Join-Path $SuiteDir 'stderr.txt'; $ExitFile=Join-Path $SuiteDir 'exit-code.txt'; $RunManifestPath=Join-Path $SuiteDir 'run-manifest.json'
    $Cwd=Join-Path $ActualWorktreeRoot $Suite.Cwd
    if(-not(Test-Path -LiteralPath $Cwd -PathType Container)){throw "approved suite cwd missing: $Cwd"}
    $TargetArgs=@($Suite.Targets)
    $Argv=@($ActualRuntime,'-B','-m','pytest','-q','-ra','-p','no:cacheprovider')+$TargetArgs+@('--basetemp',$BaseTemp,'--junitxml',$Junit)
    $RunManifest=[ordered]@{suite=$Suite.Id;run_id=$RunId;cwd=[IO.Path]::GetFullPath($Cwd);interpreter=$ActualRuntime;interpreter_sha256=$ExpectedRuntimeSha256;python_version=$ActualPythonVersion.Trim();pytest_version=$ActualPytest.Trim();argv=$Argv;basetemp=$BaseTemp;junit=$Junit;stdout=$Stdout;stderr=$Stderr;exit_file=$ExitFile}
    $runBytes=[Text.UTF8Encoding]::new($false).GetBytes(($RunManifest|ConvertTo-Json -Depth 6)+"`n")
    $runStream=[IO.File]::Open($RunManifestPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try{$runStream.Write($runBytes,0,$runBytes.Length);$runStream.Flush($true)}finally{$runStream.Dispose()}
    $idx=-1; for($i=0;$i -lt $CampaignRecord.suites.Count;$i++){if($CampaignRecord.suites[$i].id -eq $Suite.Id){$idx=$i;break}}
    if($idx -lt 0){throw 'suite absent from fixed campaign manifest'}
    $CampaignRecord.suites[$idx].status='running';$CampaignRecord.suites[$idx].run_id=$RunId;$CampaignRecord.suites[$idx].argv=$Argv
    $CampaignRecord.suites[$idx].basetemp=$BaseTemp;$CampaignRecord.suites[$idx].junit=$Junit;$CampaignRecord.suites[$idx].stdout=$Stdout;$CampaignRecord.suites[$idx].stderr=$Stderr;$CampaignRecord.suites[$idx].exit_file=$ExitFile;$CampaignRecord.suites[$idx].run_manifest=$RunManifestPath
    $CampaignRecord.suites[$idx].gate_query_index=$script:LastGateQueryIndex;$CampaignRecord.suites[$idx].preflight_json=$script:LastGatePreflightPath;$CampaignRecord.suites[$idx].gate_stage=$script:LastGateStage
    $CampaignRecord.suites[$idx].gate_exit=$script:GateExitCode
    $script:CampaignTransition='suite_running';$script:CampaignSuiteId=$Suite.Id;$script:CampaignSuiteExit=$null
    $null=Write-CampaignManifest
    $ActualExit=$null;$LaunchError=$null
    Push-Location -LiteralPath $Cwd
    try{
        $PSNativeCommandUseErrorActionPreference=$false
        & $ActualRuntime -B -m pytest -q -ra -p no:cacheprovider @TargetArgs --basetemp $BaseTemp --junitxml $Junit 1> $Stdout 2> $Stderr
        $ActualExit=$LASTEXITCODE
    }catch{$LaunchError=$_.Exception.GetType().FullName}finally{Pop-Location}
    if($null -ne $LaunchError){
        $CampaignRecord.suites[$idx].status='process_start_failed';$CampaignRecord.suites[$idx].error_type=$LaunchError;$CampaignRecord.suites[$idx].actual_exit=$null
        $exitText='process_start_failed'
    }elseif($null -eq $ActualExit){
        $CampaignRecord.suites[$idx].status='exit_code_unavailable';$CampaignRecord.suites[$idx].error_type='LASTEXITCODE_missing';$CampaignRecord.suites[$idx].actual_exit=$null
        $exitText='exit_code_unavailable:LASTEXITCODE_missing'
    }else{
        $CampaignRecord.suites[$idx].actual_exit=[int]$ActualExit
        $CampaignRecord.suites[$idx].status=if($ActualExit -eq 0){'passed'}else{'failed'}
        $exitText=[string]$ActualExit
    }
    $exitBytes=[Text.UTF8Encoding]::new($false).GetBytes($exitText+"`n")
    $exitStream=[IO.File]::Open($ExitFile,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try{$exitStream.Write($exitBytes,0,$exitBytes.Length);$exitStream.Flush($true)}finally{$exitStream.Dispose()}
    $script:CampaignTransition=$CampaignRecord.suites[$idx].status;$script:CampaignSuiteId=$Suite.Id;$script:CampaignSuiteExit=$CampaignRecord.suites[$idx].actual_exit
    $null=Write-CampaignManifest
    if($null -ne $LaunchError -or $null -eq $ActualExit){throw "$($Suite.Id) process start/exit capture failed; preserve state and stop"}
    if($ActualExit -ne 0){throw "$($Suite.Id) failed with actual exit $ActualExit; preserve state and stop"}
$FinalCampaignManifestSha=(Get-FileHash -LiteralPath $CampaignManifestPath -Algorithm SHA256).Hash
```

每组单独新 UUID 目录，保留准确 cwd、完整 argv、stdout/stderr、实际 exit、JUnit、basetemp、exit 文件、run manifest，以及 gate 的 query-index/preflight JSON 路径；在无损 UTF-8 campaign manifest 中逐组记账。每个状态变化后都读回 manifest 字节并核对 SHA，再将 manifest SHA、byte count、含上述路径的 suite 状态快照和真实 exit 追加到独立 JSONL readback sidecar；顺序包含初始化 pending、每组 gate 失败、running、passed/failed/process_start_failed/exit_code_unavailable。gate 失败记录 query-index 路径；尚未写成的 query-index/preflight 路径为 null 并记录 gate stage，不伪造文件。若任何写入、读回或 JSONL append 失败，立即停止并保留现场；不能把没通过读回的 manifest 当作证据。每次 invocation 只运行一组，任何失败立即停止，不清理、不重试、不继续下一组；下一组由 root 在新 invocation 中读取已绑定 campaign，重新取唯一 checkpoint 和 gate 结果。上表六组是完整且唯一的授权候选；改变或增加 target 必须修订计划并重新获得明确批准。

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

## 来源与审阅状态

本文件为根正式登记的完整供审计划，来源ignored合并审阅稿；它不构成授权或结果记录。正式 pack 路径固定为 `docs/superpowers/plans/2026-10-10-five-candidates-alignment.md`、`docs/superpowers/plans/five-candidates-seal-1010/alignment-amendment.md`、`docs/superpowers/plans/five-candidates-seal-1010/preflight_ee5_and_git.ps1`；root 须先登记完整成件并独立复审，实际 SHA/status 在登记后绑定。批准需针对完整正式 plan/amendment/script 和这里列明的 Native、五次 cherry-pick、六组测试及证据副作用另行取得。当前 ignored 合并稿不证明正式登记、批准或执行已发生。

## 根修订登记与当前EE5事实

2026-10-11T01:12:13.649064+08:00：本完整稿由 ignored candidate SHA FBE0D135C572512A77C28AC9D5CF366C92308EE7E02E970C21A2BB09C50A2649 正式成件，独立静审 reports\candidate-integration-1010\alignment-amendment\final-consolidated-review.json SHA AE1F4A8DB3782498DEE4922A949ED730E00A7DBB9E91B8E2A0DAEF0DCA434F2D。正式化只更改状态标题并补本登记说明，原可执行代码块/targets未更改。EE5本次残余切片completed/inactive、两Word67/26页全页QA、本次468/469完整partial恢复官方4查询actual0已证；旧§三冻结不动。供审JSON中的状态SHA仅为现时观察，执行auth要在真实明确批准后重新冻结。尚无整合Native/cherry-pick/六组测试/ff，原封存及单lane批准不延伸。

## 补充静审纠偏：唯一Native路径续跑绑定

C9E7D25F90264AD6F90A759625CEACE734677C86E31486881C08656B6C832F15版补充静审发现：campaign初始化未保存Native路径，SC2/PLATFORM/SC4/O4续跑仅检查允许前缀，不能阻止同campaign换树。该旧版不得作为执行批准载体；前述1:12登记和FBE静审保留为历史。

本修订仅在campaign初始化保存 `worktree_root=$ActualWorktreeRoot`，并在每次续跑身份比较中强制精确相等；不一致或缺字段立即throw，先于后续目录创建、gate和pytest。SC10/SC11原checkpoint根路径校验保留。六suite、五提交/41路径、正常hooks、EE5限定例外及副作用边界不扩大。正式最新SHA须在独立复审及根静态Parser检查后重新绑定，旧C9供审问题由最新版本替代。
