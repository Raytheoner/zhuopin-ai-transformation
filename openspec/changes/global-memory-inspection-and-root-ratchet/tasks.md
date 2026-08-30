# tasks — global-memory-inspection-and-root-ratchet

> **✅ design 审已过（Shao Peishen 2026-08-29，答「审过」，D1-D6 六个决策点整体通过、无点名修改）。** 执行环境：**CC**（写生产码、自行 commit+push、一任务一 worktree）。
> ✅ **可开工**：2026-08-30 分诊改判 8 行后机制类可动 WIP 27 → 19，`#435` 已摘 🛑 转待领（现 20／22）。

## 0. 前置

- [x] 0.1 design 审通过（Shao Peishen 2026-08-29 答「审过」，记录于队列 §一 `#435`）
- [x] 0.2 WIP 回落至上限内，`#435` 摘 🛑 转待领（2026-08-30 分诊改判 8 行，27→19，实测用闸自身 `_count_mechanism_wip`）

## 1. 实现

- [x] 1.1 `工具-落库sweep.py` 新增常量：`GLOBAL_MEMORY_TARGETS` / `GLOBAL_MEMORY_BYTE_CAP` / `ROOT_RATCHET_SLACK_BYTES` / `ROOT_RATCHET_MARGIN_BYTES`
- [x] 1.2 `CLAUDE_MD_ROOT_BYTE_CAP`：`90 * 1024` → `48 * 1024`，常量处注释写明棘轮语义与「只降不升」
- [x] 1.3 新增 `_check_global_memory_files()`：A1 路径存在性 / A2 尺寸 / A3 版本快照，三判据各自可独立关停
- [x] 1.4 路径抽取器 `_extract_local_paths_from_line()`：认 `C:\…` 与 `~/…`；`~/` 按 `USERPROFILE` 展开；含空格片段整段取（本机用户目录含空格）
- [x] 1.5 版本快照匹配器：排除路径内版本段（`Python314`／`nodejs`）与队列编号（`#NNN`）
- [x] 1.6 受检对象缺失 ⇒ 告警且不中止整轮（D4）
- [x] 1.6b **A4 备份堆积**（2026-08-30 并入，rebase 后发现）：`_find_backup_files()` 按目标自身文件名动态拼接 `<basename>*.bak*`（不写死字面量 `CLAUDE.md`，见常量段注释），超 `GLOBAL_MEMORY_BAK_CAP`（默认 3）告警并列最旧件名/日期；🔴 **只报不删**（函数只 `glob`+`stat`，不 `open`/`read`/`unlink` 任何匹配文件）
- [x] 1.7 棘轮提示行接入既有回显；告警去重**改用独立状态文件 `GLOBAL_MEMORY_STATE_REL`**（非原计划的 `CLAUDE_MD_SIZE_STATE_REL` 新增键——实测坐实两者共享一份状态文件会因 `_track_and_alert_standing_state` 的"未传入即判已解除"语义互相清除对方的 key，见 `工具-落库sweep.py` 常量段注释与本行下方"回归排查"记录）

## 2. 测试（零回归为硬门槛）

- [x] 2.1 A1 单测：真路径存在 / 真路径已迁走 / 散文误认 / `~` 展开 / 含空格路径（`GlobalMemoryPathExtractionUnitTests`，另补裸写遇中文标点即止、双引号定界符两条回归锁）
- [x] 2.2 A3 单测：命中 `v2.1.x`；**不**命中 `Python314`、`nodejs`、`#422`（`GlobalMemoryVersionSnapshotUnitTests`）
- [x] 2.3 D4 单测：受检文件不存在时告警且后续检查照跑（`GlobalMemoryMissingTargetUnitTests`，另补三判据独立关停开关的验收）
- [x] 2.3b A4 单测（`GlobalMemoryBackupPileupUnitTests`）：4 个 `.bak` 超阈值告警并列最旧件名/日期；3 个（=阈值）只回显不告警；备份内容用**不可解码的随机二进制**验证判据从不读取文件内容（若误读会直接抛异常）；按目标自身文件名动态匹配（非 `CLAUDE.md` 的目标同样生效）；判据可独立关停
- [x] 2.4 棘轮单测：低于阈值 1,024 B 以上出提示；超阈值出告警（`RootRatchetHintUnitTests`，另补边界值与 scene 不适用两条）
- [x] 2.5 全量回归绿、零回归（对照当前基线数）——**回归排查发现并修复一处真实问题**：`_check_global_memory_files` 首版直接读模块常量 `GLOBAL_MEMORY_TARGETS`（默认指向真实 `~/.claude/CLAUDE.md`），CLI 级用例走子进程、monkeypatch 对子进程无效，本机该文件恰好现存一处真实失真（见 3.1），导致 17 个既有 webhook 计数类用例转红（1 != 0 / 2 != 1 形态）；修法＝新增 `GLOBAL_MEMORY_TARGETS_ENV_OVERRIDE` 环境变量间接层（同 `_site_packages_dirs()` 已验证模式）＋ `SweepTestBase` 夹具改指向自建干净占位文件。**最终实测**：`test_工具-落库sweep.py` 337 passed（0 failed，含本次新增 20 项）；`test_工具-共享文档编辑锁.py` 294 run，仅 1 个失败且与本包无关（`GenderPronounLintTests.test_roster_stays_in_sync_with_root_claude_md`——根 `CLAUDE.md` §1 人名/性别标注已迁至独立正本文件，该既有用例的抽取正则随之失效，属本机既存漂移，未触碰、未掩饰）。**rebase 后发现 A4 待补，见 1.6b/2.3b。**

## 3. 真实验活（不是 mock）

- [x] 3.1 对**真实** `~/.claude/CLAUDE.md`（2026-08-29 已订正版）跑一次：**零版本快照红**；路径存在性 **1 处真红**——`~/.claude/skills/rare-earth-research` 目录已不存在（L57，本机实测 `ls ~/.claude/skills/` 只有 `download-images-skill`／`setup-sound-notifications-windows` 两个，无 `rare-earth-research`）。**这不是本包缺陷，是本包上线首轮即抓到的一处真实失真**——`OP-0829-W` 手工零基审计当时未覆盖到这一处（人工审计天然会漏，正是本包要补的半径）；只报不改，已如实告知 Shao Peishen，是否/如何订正由他定。
- [x] 3.2 造一次真阳性复验：临时副本（同目录）注入 `C:\此路径已失效\op0830c验证`，确认报出 `L143` 与原文一致，**已删副本**（`tmp_copy.unlink()` 后 `exists()` 复核为 `False`）。
- [x] 3.3 root 棘轮回显核对：当前 47,863 B / 阈值 49,152 B，差额 1,289 B（＞ `ROOT_RATCHET_SLACK_BYTES`=1024）⇒ 提示行 `可将 cap 下调至 48,375`，实测与预期逐字一致。
- [x] 3.4 连跑两轮确认 24h 去重生效：状态文件时间戳两轮完全相同（`2026-08-30T00:14:19...`），回显每轮均照常打印（"零红亦不省略"），无重复告警动作。
- [x] 3.5 A4 真实验活：对**真实** `~/.claude/` 跑一次，实测 `CLAUDE.md.bak`/`CLAUDE.md.20260624-111954.bak` 共 **2 个**（阈值 3，未超限，只回显不告警）。🔴 **如实登记一处与 proposal 原文的数字差异**：proposal 记「已攒 5 个备份」，本机此刻实测仅 2 个——推断是 Shao Peishen 问「能不能删」之后、本行落地前，他本人或另一会话已先行清理了 3 个（他自己动手，不是本判据代删——本判据全程只读，未删除/移动任何文件）；未再造真阳性覆盖超限分支（会需要在其真实 `~/.claude` 目录下新增文件，超出「只报不改」的授权边界），超限分支已由 2.3b 隔离环境单测覆盖。

## 5. 子项 E — 状态字段与自陈一致性检查（2026-08-30 并入，`工具-共享文档编辑锁.py`）

- [x] 5.1 措辞集常量 `STALE_STATUS_PHRASES`：硬阻塞／已押后／待 Shao Peishen／待拍板／需人在场／留步／常驻不销，**可增不可删**，每条注释附真实来源行号（`#413`/`#282`/`#398`/`#387`/`#380`&`#399`/`#98`，逐条核对自 `git show 178979c^`，见 5.6）
- [x] 5.2 `_suggest_status_reclassification()`：扫 `open`/`partial` 行，命中即产出 `(行号, 现字段, 建议字段, 命中原话片段)`；每行只取第一个命中措辞（避免同一行重复列出）
- [x] 5.3 接入 release 的 WIP 阻断消息：仅接在"两条出路"主拒绝分支后（另两个已选定逃生阀路径的分支刻意不附，见函数 docstring 取舍说明）
- [x] 5.4 🔴 只建议不自动改（函数纯只读，配「入参文本不被改变」单测锁死）；🔴 不改 `_count_mechanism_wip` 计入口径（该函数一字未动）
- [x] 5.5 单测：命中 `#380`/`#387` 等真实原话；**不**命中 `#96` 反例短标题；另补"非 open/partial 状态不入选"与"同行多措辞只列一条"两条边界
- [x] 5.6 真实回归（**唯一验收判据**）：对逐字取自 `git show 178979c^`（改判落地提交的父提交）的 8 行真实文本跑，`RealSnapshotReclassificationRegressionTests.test_列全当天人工分诊出的八行` 确认全部 8 个行号（`#282`/`#413`/`#419`/`#398`/`#380`/`#387`/`#399`/`#98`）齐全、零漏报，且建议字段方向正确（7 行 `blocked`、`#98` 因"常驻不销"建议 `timed=`）。**如实登记一处已知边界**（另有单测锁死该行为，非缺陷）：`#96` 完整正文（6,000+ 字）里有一处已解决的历史提及"待 Shao Peishen"会被列为候选，短标题本身不会误报——按 D2/D7 同族取舍，宁可多列不可漏列。

## 4. 收口

- [x] 4.1 值周巡检清单加一行「全局记忆巡检有红即当周处理，不跨周」（D6）——写入 `0-学习与工具/定时任务源码/weekly-status-update.SKILL.md` 步骤 2.D（未发现本机另有已安装副本需同步）
- [ ] 4.2 §二 批次登记 ＋ commit+push（ff-only）
- [ ] 4.3 队列行回写：状态列开头 ✅ ＋ 实测数字
- [ ] 4.4 全部 [x] 后**当场** `/opsx:archive global-memory-inspection-and-root-ratchet -y`
