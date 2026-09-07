# sweep-manifest-scoped-stage Tasks

> ✅ **design 审已过 —— Shao Peishen 2026-09-07（合审 §1，答 (a)＝全部按起草方推荐）。**
> 结论：**① ⒜ ／ ② ⒝ ／ ③ ⒝ ／ ④ ⒝ ／ ⑤ ⒜（＋反向检查）／ ⑥ ⒜**（见 `design.md` 文首结论表）。
> propose＋design 起草＝`OP-0907-I`【CC】，分支 `claude/op0907i-sweep-manifest-479`。
> apply＝`OP-0907-AI`【CC】，分支 `claude/op0907ai-sweep-manifest-479-apply`（rebase 到 master `6f37608` 后施工）。
> 执行环境：**CC**（写生产码、跑测试、自行 commit+push，一任务一 worktree）。
> 来源：队列 §一 `#479`（§四 `#127` ⒜ 裁决 ＋ §四 `#126` 另立的真风险）。

## 0. 前置闸（design 审后、动手前）

- [x] 0.1 design 审六个决策点已全部拍板，结论回填 `design.md` 文首（结论表已写）。🔴 **队列 §一 `#479` 行本泳道未写**——`OP-0907-AI` 派单件第 4 条明写「不写队列文件」，回写留给看护线（见下 5.6）
- [x] 0.2 触碰区核对 —— 手段：遍历 `git for-each-ref refs/heads/ refs/remotes/origin/`（97 个 ref），逐个跑 `git log master..<ref> -- <sweep> <单测>` 与反向 `git log <ref>..master -- …` 再取 `git diff --stat master...<ref>`。结论：**17 个 ref（去重后 9 条实分支）仍压着这两个文件**，其中**只有 2 条与 master 同基（即真正在办、必然与本包同触碰）**：
  - `claude/op0907ah-plan-scanner-462`（＝泳道 A6／`#462`，落后 master 0 个提交；sweep 侧 hunk＠旧行 6172／6248／6514／6523／6542）
  - `claude/op0907am-editlock-waiver-bcbc97`（＝`#416`⑶／`OP-0907-AM`，落后 master 0 个提交；sweep 侧 hunk＠旧行 660／3076／6514）
  - 其余 7 条（`queue-315-apply` 落后 36、`worktree-agent-ab0d5363…` 落后 17、`op0828g-local-master-divergence-alert` 落后 21、`queue-410-editable-probe` 落后 12、`editable-import-guard-0902` 落后 8、`tmp-rebase3-editable-guard` 落后 5、`op0905i-pth-impl-459` 落后 4、`happy-thompson-017679` 落后 2）**均已显著落后 master**，是历史残留而非在办，不构成本包的合入次序约束
- [x] 0.3 触碰区无其它在办行占用（同 0.2：只 `#462`／`#416`⑶ 两条同基）；`ZhuopinCommitSweep` 在 apply 窗口内的行为已评估 —— **本泳道全程在隔离 worktree 内施工，不改主仓工作区、不 ff master**，定时任务跑的是主仓的旧版 sweep，与本分支互不影响；风险落在**合入之后的首轮**（见 5.2）

## 1. 取证与口径（不引用 propose 期数字，全部本次重取）

- [x] 1.1 AST／grep 重扫落点：**6 处 `git add` ／ 5 处 `git commit`，数量与 propose 期一致；行号已漂移**（propose 快照 → apply 实测：`1936·1938`→不变；`2685·2686`→不变；`5067·5072·5075`→`5161·5166·5169`；`6306·6307`→`6400·6401`；`6488·6489`→`6582·6583`）
- [x] 1.2 受控复现重跑（10 组实验，脚本一次性、不入库）。**本机 `git version 2.53.0.windows.2`**。核心两条复现：
  - 实验 1：index 里有孤儿 ⇒ 裸 commit dry-run 报 `M a.txt / A orphan.txt`（孤儿**进**提交）；带 pathspec 报 `M a.txt / ?? orphan.txt`（孤儿**不进**，且提交后仍留在 index）
  - 实验 2：add 后工作树被改写 ⇒ `MM a.txt`，pathspec commit 提交的是**改写后的 v2**、提交后工作树转干净 ⇒ **`--only` 语义与 propose 期结论一致**
- [x] 1.3 决策点① ⒜ 的四种边角逐条实测：
  - **路径无改动** ⇒ `git commit -m x -- b.txt` 退出码 **1**、`nothing to commit`（⇒ 必须前置判空，否则 `_run_git(check=True)` 会把常态抬成整轮崩溃）
  - **pathspec 是目录** ⇒ 正常，展开为目录下全部有差异的文件
  - **路径含中文与空格** ⇒ `-c core.quotepath=false` 只关八进制转义、**不关加引号**；`-z` 才是稳的（实测 `'中文 目录/文件.txt\x00'`）⇒ 实现改用 `-z`
  - **多 pathspec 混合** ⇒ 其中一个无改动：正常提交其余；其中一个**不存在**：整条命令退出码 **1**、`pathspec did not match`，**哪怕同命令里别的路径确有改动** ⇒ 实现改为「用算出来的 `expected` 当 pathspec」，绕开该边角
  - 补测：新增文件／删除文件／清单内路径只改工作树未 add（`--only` 会带走它，故预期集合必须用 `git diff HEAD` 而非 `--cached`）
- [~] 1.4 决策点① 未选 ⒞，本条不适用（临时 index 未实现）
- [x] 1.5 下游消费者核实（本次重跑，手段换成 `git grep` 全仓＋逐个读文件，不引用 proposal 的"未发现依赖"结论）：**无任何下游解析 sweep 提交的文件清单／文件数**。全部命中只有三类——
  - `工具-落库sweep.py` 自身与其单测（34／24 处）
  - 计数类：`hooks-sessionstart-context.ps1`／`工具-主工作区安全同步.ps1` 用 `git rev-list --count origin/master..master`，数的是**提交个数**、不看内容；本包唯一影响提交个数的是新增的"无内容可提交 ⇒ 不产生 commit"路径，对 ahead/behind 判据无害
  - 日志解析类：`工具-项目状态卡数据层.ps1` 按 `^✗ ` / `^⚠ 非 clean：` / `^✓ 批次 .*已落库并推送` 等**行首前缀**给轮次分类。本包改动的两行仍以 `✗ ` 开头（只在中间插入「于步骤『…』」），新增行以 `⚠ <label>：` 或 4 空格缩进开头，**均不命中它的任何一条正则** ⇒ 分类口径零变化
  - 其余全是 `.md`（队列、归档、看护件、openspec 文档）＝ 叙述性引用，非消费者
- [x] 1.6 宽 except 归属重扫：与 `design.md` 分诊表一致——**关键路径候选函数今天分支数全部为 0**，`_run_scheduled_task_mirror_sync` 3 个、`main()` 5 个，取向与 design 记载相同 ⇒ ⑵ 的落点确认为**回归守卫＋兜底告警点名**，不是修一个正在出血的 bug

## 2. 实现 ⑴（提交范围收紧）

- [x] 2.1 `_process_normal_batch` 的提交按决策点① ⒜ 改造；预期集合 ＝ 两处 add 的并集 `[*resolved_files, row["queue_path"]]`，**逐字同源、不另起计算**
- [x] 2.2 决策点② ⒝：其余四处同形改造 —— `_run_scheduled_task_mirror_sync`／`_commit_uncovered_queue_changes`／`main()` 补销尾巴／`_rerun_ledger`。**五处全部走同一个 `_commit_scoped()`**，无未覆盖点
- [x] 2.3 空提交／无改动路径：`_commit_scoped` 返回 `None`，日志走既有"本轮无内容可提交"语义，**不新造分支语义**；调用方据此决定要不要写"已提交"那句话（否则日志会说谎）
- [x] 2.4 提交后校验：`git show --name-only --format= -z <sha>` 与预期集合比对，按决策点④ ⒝ **不一致即点名告警、不 abort**
- [x] 2.5 决策点③ ⒝：清单外的**已暂存**内容点名告警（`⚠ …未被带入本提交（仍留在工作区…）`）但照常落库；**不替别人 `restore --staged`**（那正是 ⒝ 被否的边界）

## 3. 实现 ⑵（关键路径 fail-loud）

- [x] 3.1 新增 `CRITICAL_GIT_WRITE_FUNCTIONS`（决策点⑤ ⒜ 窄清单）＋ `CRITICAL_GIT_WRITE_EXEMPT_FUNCTIONS`（每项须写理由）；旁注写明"新增任何会 commit／push 的函数必须进本清单"。
  🔑 **反向检查第一次真跑就报出一个漏项：`_ff_carrier`（`git merge --ff-only` 常驻执行体 worktree）**——起草时按"直接 commit/push"的直觉扫漏了 merge 这一支，已补进清单。**这不是改判据，恰恰是判据按设计生效**
- [x] 3.2 步骤指纹 `_mark_step()`／`_current_step()`：`main()` 十处接线（起跑前置检查／编辑锁前置探测／补推未推送提交／本地独有提交扫描／起跑段子进程／队列未覆盖改动单独落库／逐批次落库／补销尾巴／台账重跑／与 origin 对齐并推送）；**两个兜底分支（`except SweepAbort` 与 `#198(a)` 通用兜底）的日志行与企微文案均点名当前步骤**。
  实证（CLI 真跑，非结构断言）：`python 工具-落库sweep.py --dry-run --repo-root <worktree>` 输出 `✗ …的 .git 不是目录…` 后紧跟 `（早退于步骤：起跑前置检查）`
- [x] 3.3 未改动任何既有宽 except —— 手段：`git diff -U0 | grep -E "^[-+].*except "`，命中的 7 行**全部是注释与 docstring**，零个 `except` 子句被增删；`git diff` 全部删除行共 15 行，逐行核对＝5 处 commit 调用 ＋ 2 行兜底日志文案，`_run_git` 编解码／`#136` L6242 fail-open／31 处宽 except 均零改动

## 4. 测试

- [x] 4.1 反例单测：`test_清单外的已暂存文件不得被带进该批提交`（真 git 仓库，路径含中文与空格）
- [x] 4.2 正例单测：`test_清单内路径全部进入提交且只有它们`
- [x] 4.3 **非恒真自证**：`test_非恒真自证_旁路收紧逻辑后同一输入由未带入变回带入` —— 同一夹具跑两侧，收紧侧 `{声明件}`、旁路侧（逐字还原收紧前那句裸 commit）含 `无关.md`，并**反向断言旁路侧必须带得进来**（带不进来说明夹具根本没构造出病灶，那么另一侧那条绿什么都没证明）
- [x] 4.4 边角单测：`test_清单路径无改动时不产生提交且不抛异常`／`test_清单含不存在路径时不因pathspec不匹配而崩`／`test_目录pathspec与删除文件均被正确纳入`
- [x] 4.5 提交后校验两侧：`test_提交后校验一致时静默`／`test_提交后校验不一致时点名告警且不回滚`
- [x] 4.6 AST 守卫：`CriticalGitWritePathGuardTests::test_清单内函数体内不得出现宽捕获`，逐字仿照 `LocalOnlyCommitGuardTests::test_本类不做任何git写动作` 的源码切片＋`ast.walk` 范式；另加 `test_清单里的函数名都真实存在`（防守卫静默退化成"零个函数被检查"＝恒绿）
- [x] 4.7 反向检查单测：`test_反向检查_写git历史的函数漏进清单即报出`（＋`test_豁免名单每一项都写了理由且函数真实存在`＋`test_五处自动提交全部走了收紧后的入口`：AST 数残余裸 commit，不数字符串）
- [x] 4.8 守卫单测 docstring 逐条写明三类已知不覆盖形态（挪窝逃逸／窄而同样吞掉真问题／捕获之外的静默），并写死交付措辞边界：只支持说「清单内函数不会出现宽捕获」，**不得**说成「关键路径此后不会被静默吞掉」
- [x] 4.9 步骤指纹 CLI 级：`StepFingerprintTests`（接线断言＋两个兜底分支文案＋残值归零＋CLI 真跑一轮退出码 0）；`ScopedCommitCliWiringTests::test_端到端_别的会话暂存的孤儿不进批次提交` 走真实 `main()` 全链路
- [x] 4.10 全量 `test_工具-落库sweep.py` 见收工报告实测（新增 18 用例全绿）

## 5. 现网回归与收口

- [~] 5.1 `--dry-run` 只读回归：**在本泳道 worktree 上跑通**（证实步骤指纹端到端生效）；**未对主仓跑** —— `OP-0907-AI` 派单件第 4 条明写「不碰主仓工作区」，而 `--dry-run` 仍会执行 `_heal_stale_index_lock`（会删陈旧 `.git/index.lock`＝一次写动作）。CLI 级真 git 夹具用例已覆盖同一条路径
- [ ] 5.2 生产首轮观察（合入 master 之后）：确认批次照常落库、孤儿告警照常接住清单外内容。🟡 **合入 master 属看护者决策，本泳道不做**
- [x] 5.3 质量型基线**现取**（不引用 propose 期任何数字）：扫 master 最近 400 个提交里**固定标题类** sweep 自动提交（台账重跑 85 ／ 补销尾巴 19 ／ 镜像核对 2 ＝ 106 个），按各自写死的预期集合逐个比对 `git show --name-only`，**夹带 0 个（0.0%）**。
  ⚠️ **如实标注该基线的覆盖边界，不粉饰**：本基线只覆盖"预期集合写死"的那一支；**批次标题类提交的预期集合要回溯当时的批次清单才能判定，本次未回溯，故不在基线内**——而 `OP-0827-A` 实撞的恰恰是批次标题类。⇒ 该 0.0% 只能读作「固定标题这三类在最近 400 个提交的窗口里没出过血」，**不能**读作「病灶不存在」
- [x] 5.4 文档同步：`工具-落库sweep.py` 文件头「五条硬要求」① 已补「add 与 commit 现已同为清单范围」，并写清此前「只挡住 stage、挡不住提交」的出血形态与 `_commit_scoped()` 指针
- [ ] 5.5 §四 `#127` 行追加「建议 ⒞ 已因机制落地而无必要」指针 —— 🔴 **本泳道不写队列文件**（派单件第 4 条），留给看护线
- [ ] 5.6 队列 §一 `#479` 回填 apply 结论并转态；§二 登记批次 —— 🔴 **同上，本泳道不写队列文件**
- [ ] 5.7 openspec 归档（`openspec archive`）＋ specs 同步 —— 前置＝5.2／5.5／5.6 闭合，留给看护线

## 🔴 本包明确不做（收工逐条自查，手段＝`git diff -U0` 全量删除行核对）

- [x] N.1 `_run_git` 的 `encoding=`／`errors=` 零改动（§四 `#126` ⒜ 维持现状）
- [x] N.2 31 处宽 except 零改动（只登记在 `design.md` 分诊表）
- [x] N.3 `#136` L6242 fail-open 零改动
- [x] N.4 `工具-共享文档编辑锁.py` 零改动（本次 `git status` 未出现该文件）
- [x] N.5 `_resolve_batch_files`／`_manifest_coverage_gap`／`_looks_like_declared_path`／`_partition_pending_rows_by_batch_isolation` 零改动
- [x] N.6 未触碰 `.51`／企微机器人配置／定时任务注册
