# sweep-manifest-scoped-stage Tasks

> 🔴 **本包尚未通过 design 审 —— 0.1 之前的任何一项都不得开工。**
> 本次（`OP-0907-I`【CC】，分支 `claude/op0907i-sweep-manifest-479`，worktree）范围＝**只到 propose＋design 起草**（队列 §一 `#479` 状态列明写）。
> 下方 0.x 之后的全部条目是 **apply 期待办清单**，由 design 审通过后另起 session 执行。
> 执行环境：**CC**（写生产码、跑测试、自行 commit+push，一任务一 worktree）。
> 来源：队列 §一 `#479`（§四 `#127` ⒜ 裁决 ＋ §四 `#126` 另立的真风险）。

## 0. 前置闸（design 审后、动手前）

- [ ] 0.1 design 审六个决策点已全部拍板，结论回填 `design.md` 文首（新增结论表）与队列 §一 `#479` 行
- [ ] 0.2 触碰区核对 —— 手段：遍历 `git for-each-ref refs/heads/`，对每个分支跑 `git log master..<branch> -- 0-学习与工具/工具-落库sweep.py` 与 `-- 0-学习与工具/test_工具-落库sweep.py`，逐个判断是领先还是落后于 master（**只报"有提交"不够，须给 `git diff --stat` 方向**）
- [ ] 0.3 确认 `#479` 触碰区（`工具-落库sweep.py`、其单测、`openspec/changes/`）无其它在办行占用；`ZhuopinCommitSweep` 定时任务在 apply 窗口内的行为已评估（**本包改的正是 sweep 自身，apply 期须防"改到一半被自己的定时任务跑到"**）

## 1. 取证与口径（🔴 必须先于实现，且不得引用 propose 期数字）

- [ ] 1.1 重跑 propose 期的 AST 扫描，确认 `git add`／`git commit` 落点数与行号未漂移（propose 期快照：6 处 add／5 处 commit，L1936·1938／2685·2686／5067·5072·5075／6306·6307／6488·6489）
- [ ] 1.2 重跑受控复现（`git commit --dry-run --short` 两侧对照），确认 pathspec 的 `--only` 语义在本机 git 版本上与 propose 期结论一致；**记录本机 `git --version`**
- [ ] 1.3 决策点① 若选 ⒜：实测 `git commit -- <path>` 在「路径无改动」「路径是目录」「路径含中文」「`core.autocrlf` 造成的伪改动」四种边角上的行为，逐条记录
- [ ] 1.4 决策点① 若选 ⒞：实测临时 index 落在 `.git/` 下时 `git status --porcelain` 不报告它（**实跑，不是推断**）；确认 hooks／`commit.gpgsign` 的绕过是否可接受
- [ ] 1.5 🔴 **下游消费者核实（本次重跑，不得引用 proposal 的"未发现依赖"结论）** —— proposal 里那条只覆盖**提交标题含"收容"**的 8 个提交；本次换手段：对最近 N 轮 sweep 提交逐个 `git show --name-only` 与当时的批次清单比对，得出"实际夹带率"，并 grep 谁在解析 sweep 提交内容／提交数
- [ ] 1.6 重跑宽 except 的 AST 归属统计，确认 `design.md` 分诊表未漂移（propose 期快照：66 个 except 分支／31 个宽捕获／7 个关键路径候选函数 0 分支）

## 2. 实现 ⑴（提交范围收紧）

- [ ] 2.1 按决策点① 的形态改造 `_process_normal_batch` 的提交（预期集合 ＝ L5067／L5072 两处 add 的并集，**不另起计算**）
- [ ] 2.2 按决策点② 的作用面，同形改造其余提交点（`_commit_uncovered_queue_changes`／`main()` 补销尾巴／`_rerun_ledger`／`_run_scheduled_task_mirror_sync`）；若拍板取窄，未覆盖点须写明"本点尚未收紧"及理由
- [ ] 2.3 空提交／无改动路径的处置（沿用既有"本轮无内容可提交"路径，不新造分支语义）
- [ ] 2.4 提交后校验（`git show --name-only --format=`）＋ 按决策点④ 的处置
- [ ] 2.5 按决策点③ 处置清单外 index 内容（静默／点名／跳过）

## 3. 实现 ⑵（关键路径 fail-loud）

- [ ] 3.1 新增关键路径函数清单常量，按决策点⑤ 的范围；旁注写明"新增任何会 `git commit`／`git push` 的函数必须进本清单"
- [ ] 3.2 `main()` 步骤指纹接线；L6438 兜底的日志行与企微文案点名当前步骤
- [ ] 3.3 🔴 **确认未改动任何既有宽 except**（`git diff` 自查：`_run_git` 编解码、L6242 `#136` fail-open、告警／加载类捕获全部零改动）

## 4. 测试

- [ ] 4.1 反例单测（`#479` 期望产出明列）：清单外的**已暂存**文件不得被带进该批提交
- [ ] 4.2 正例单测：清单内路径全部进入该批提交，且只有它们
- [ ] 4.3 🔴 **非恒真自证**：旁路收紧逻辑后，同一输入由"未带入"变回"带入"
- [ ] 4.4 空提交／无改动路径的边角单测
- [ ] 4.5 提交后校验的两侧单测（一致时静默／不一致时点名）
- [ ] 4.6 ⑵ AST 守卫单测（清单内函数无宽捕获），**逐字仿照** `LocalOnlyCommitGuardTests::test_本类不做任何git写动作`（L6827）
- [ ] 4.7 ⑵ 反向检查单测（写 git 历史的函数漏进清单时报出）
- [ ] 4.8 ⑵ 守卫单测文档字符串逐条写明三类已知不覆盖形态
- [ ] 4.9 步骤指纹在兜底告警文案里真的出现（CLI 级，不只是函数级）
- [ ] 4.10 全量 `test_工具-落库sweep.py` 绿、零回归

## 5. 现网回归与收口

- [ ] 5.1 `--dry-run` 跑一轮，比对日志与收紧前的行为差异
- [ ] 5.2 生产首轮观察：确认批次照常落库、孤儿告警照常接住清单外内容
- [ ] 5.3 §验收 里那条质量型基线现取（最近 N 轮 sweep 提交的"文件数 ≠ 清单声明数"占比）
- [ ] 5.4 文档同步：`工具-落库sweep.py` 文件头「五条硬要求」① 补一句「add 与 commit 现已同为清单范围」
- [ ] 5.5 §四 `#127` 行追加「建议 ⒞（改措辞）已因机制落地而无必要」指针（**只追加、不改历史正文**）
- [ ] 5.6 队列 §一 `#479` 回填 apply 结论并转态；§二 登记批次
- [ ] 5.7 openspec 归档（`openspec archive`）＋ specs 同步

## 🔴 本包明确不做（每一项都须在收工自查时逐条确认零改动）

- [ ] N.1 `_run_git` 的 `encoding=`／`errors=` 零改动（§四 `#126` ⒜ 维持现状）
- [ ] N.2 31 处宽 except 零改动（只登记在 `design.md` 分诊表）
- [ ] N.3 `#136` L6242 fail-open 零改动
- [ ] N.4 `工具-共享文档编辑锁.py` 零改动（含 `登记豁免` 措辞）
- [ ] N.5 `_resolve_batch_files`／`_manifest_coverage_gap`／`_looks_like_declared_path`／`_partition_pending_rows_by_batch_isolation` 零改动
- [ ] N.6 不触碰 `.51`／企微机器人配置／定时任务注册
