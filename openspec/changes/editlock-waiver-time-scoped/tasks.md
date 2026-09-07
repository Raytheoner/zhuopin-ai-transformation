# Tasks · editlock-waiver-time-scoped

## 0. 状态：出件即停（派单件 `OP-0907-AM` 步骤 1）

- [x] 0.1 命中 CLAUDE.md §5 openspec 门槛第③条判定完成——同一接口、同一输入，`release` 结果由**放行**变**拒绝**（方向与 `editlock-aibot-registration-completeness-exemption` 相反）
- [x] 0.2 现状取证（只读）：判据裸子串、取材面含触碰行整行、`#382` 行内真实残留、2026-09-07 16:21 sweep 21 个孤儿——见 design.md §一
- [x] 0.3 `.gitignore` 覆盖核实（`git check-ignore -v` 实测，非推断）——见 proposal.md
- [x] 0.4 propose ＋ design 出件，`openspec validate --strict` 绿
- [x] 0.5 ✅ **Shao Peishen 2026-09-07 拍板 `1a／2b／3a`**（⟨就地答⟩）：① 批准 D1–D4 一次 apply；② 窗口内逃生 ＝ 给 `release` 加 `--waiver`（**本项使 spec delta 新增一条 Requirement**「release 时可就地声明本次一用的豁免」）；③ `到期` 缺省 ＝ 当日有效

## 1. 实现 · 编辑锁侧（D1–D3 ＋ 决策 2b，`0-学习与工具/工具-共享文档编辑锁.py`）

- [x] 1.1 **apply 前置已核，且结论与派单件原定处置不同——如实记在这里**：`#455`（Y-A5 编辑锁写侧，分支 `claude/op0905n-editrow-guard-455`＠`7bd70b5`）**尚未 ff 入 master**（`git merge-base --is-ancestor 7bd70b5 origin/master` 为假），但它同时**落后 origin/master 150 个提交**（merge-base ＝ `860dda2`，2026-09-05）。⇒ 派单件写的「rebase 到其分支之上做」在此处不可取：那会把本包一并拖回 09-05 的基线，且要求本会话先替 `#455` 完成它自己的 ff（该动作是 🟡、且带「脏文件 ∩ 带入文件为空」前置，`#455` 行内明写）。**改为 rebase 到 `origin/master`＠`44af737`**，并把重叠登记为收工待办：两分支都改 `工具-共享文档编辑锁.py`，**后 ff 的一方须解冲突**；实测重叠面很小——`#455` 的改动集中在 `_build_append_row_line`／`cmd_edit_row`／`cmd_append_row` 与 `main()` 里 edit-row/append-row 两个子解析器，本包集中在 `_registration_completeness_violations`／`cmd_release`／`p_release`
- [x] 1.2 D1：`_registration_completeness_violations` 的第四个形参由 `waiver_sources: list[str]` 改为 `acquire_note: str`。🔴 **签名收成字符串是判据的一部分**：传列表进来就总有人往里多塞一个来源，而 `#416` ⑶ 的整个病灶就是"取材面多了一个会落盘的来源"；收成字符串之后，**想加来源必须改签名**。`_auto_sync_followup_reply_state`（`转态豁免：`）与 `_opener_guard_violations`（`opener豁免：`）的 `waiver_sources` **一个字未动**
- [x] 1.3 D2：`_parse_registration_waiver_clauses`（纯文本解析，不碰文件系统）＋ `_valid_waiver_paths`（有效性判定）。分隔符 `；`／`;`／`、` 全接受，反引号可选，正文在第一个左括号处截断；有效路径＝工作树内存在 **或** 出现在本次脏文件集合中
- [x] 1.4 D2：只放行点名件；拒绝文案写出「已点名放行 M 个、下列 N 个未被点名」
- [x] 1.5 D2 ＋ 决策 3a：`_resolve_waiver_due_date`——缺 `到期` ⇒ 当日有效；年份按「早于今日 180 天以上则解为次年」判。🔴 **用本机本地日期、刻意不用 `_now()`**（它返回 UTC）：note 里的 `MM-DD` 是人按本机 `Get-Date` 写的，用 UTC 比会在每天 16:00–24:00 那一段整整差一天
- [x] 1.6 D3：泛豁免拒绝，文案与「未写豁免」可区分（明说"检测到标记但没有点名任何有效路径"），只给两条出路
- [x] 1.7 fail-closed 分支：点名豁免仍放行（有效性只按"工作树内存在"判），**泛豁免在该分支同样被拒**——取数失败叠加一句谁也没点名的豁免，正是最该停下的组合
- [x] 1.8 删掉拒绝文案里「或本次触碰的队列行内写…」——留着一条已不生效的出路比没有出路更坏
- [x] 1.9 在 `_dirty_path_is_covered` 与 `REGISTRATION_WAIVER_MARKER` 之间写清判据来源（时间维 vs 空间维）、`#382` 那条实证、以及"只收窄 ⑹ 一项"的红字
- [x] 1.10 **决策 2b**：`release --waiver`。调用点把 note 与 `--waiver` 拼成一段 `registration_waiver_scope` 只喂给 ⑹；放行原文按 `进度豁免：` 既有惯例落进锁 `history` 留痕（不进 git——本次放行的理由本就不该长期生效，但下一次 acquire 的回显会打出来）

## 2. 单测 · 编辑锁侧（`test_工具-共享文档编辑锁.py`）

`RegistrationCompletenessTests`（白盒）＋ 新增 `ReleaseWaiverCliTests`（真 CLI ＋ 真 git 仓库）。

- [x] 2.1 泛豁免拒（`test_blanket_waiver_is_rejected`）＋ 文案可区分（`test_blanket_waiver_message_differs_from_no_waiver`）
- [x] 2.2 点名豁免只放点名件（`test_named_waiver_releases_only_named_files`，断言含「已点名放行 1 个」且未点名的那个仍在拒绝清单里）
- [x] 2.3 点名全部 ⇒ 放行（`test_named_waiver_in_note_passes`）
- [x] 2.4 🔴 **行内旧豁免不再生效**（`test_stale_inline_waiver_in_touched_row_no_longer_passes`）——用 `#382` 任务列那句**真实残留原文**做 fixture。⚠️ 它**点了名、格式也不难看**，正因如此旧口径下任何一次碰了那行的持锁都会捡到它
- [x] 2.5 到期已过失效／未过生效／缺省当日有效／跨年不误判（四条：`test_expired_waiver_does_not_pass`、`test_unexpired_waiver_passes`、`test_waiver_without_due_defaults_to_today`、`test_due_year_inference_survives_year_boundary`）
- [x] 2.6 反例：机器人身份 ＋ 未覆盖脏文件 ＋ 无任何豁免文本 ⇒ 仍放行（既有 `test_aibot_identity_is_exempt_from_others_dirty_files`，本次未改、保持绿）
- [x] 2.7 反例：机器人身份 ＋ 取数失败 ⇒ 仍 fail-closed（既有 `test_aibot_still_fail_closed_when_status_unavailable`，保持绿）
- [x] 2.8 反例：`opener豁免：` 写在本次触碰的队列行内 ⇒ 照旧放行（`OpenerGuardReleaseTests::test_waiver_in_touched_queue_row_passes`，已补写"这是只收窄 ⑹ 一项的反例锚点"的文档字符串）
- [x] 2.9 补充判据锚定与格式容错：`test_registration_waiver_scope_excludes_touched_rows`（形参名断言）、`test_waiver_separator_and_backtick_variants`（三种分隔符 subTest）、`test_waiver_naming_nonexistent_path_is_not_valid`、`test_deleted_dirty_file_can_be_named`（删除形态）、`test_named_waiver_also_covers_status_failure`、`test_blanket_waiver_still_rejected_on_status_failure`
- [x] 2.10 决策 2b 的真 CLI 端到端 `ReleaseWaiverCliTests` 五条：中途脏文件可在 release 点名放行／CLI 泛豁免仍拒／只放点名件／理由落进锁 history／**上一把锁用过的 `--waiver` 对下一把锁不生效**（一次一用的核心断言）
- [ ] 2.11 🔴 **反向对照**：把脚本换回 master 版跑这一批，新增用例必须变红、反例必须保持绿——否则证明不了它咬住的是本次改动

## 3. 实现 · sweep 侧（D4，`0-学习与工具/工具-落库sweep.py`）

- [x] 3.1 **apply 前置已核**：`#479`（Y-A7 sweep-manifest）状态 `[S:partial]`，本次激活范围**只到 propose＋design 起草、不 apply** ⇒ `工具-落库sweep.py` 上无其分支代码，零冲突
- [x] 3.2 `ORPHAN_SECTION_FOUR_HOURS = 6` ＋ `ORPHAN_SECTION_FOUR_LOGGED_KEY`，**独立于** `ORPHAN_ALERT_THRESHOLD_HOURS = 3`（受众不同：企微推送打给还在场的人，§四 打给总线排期）
- [x] 3.3 `_escalate_long_lived_orphans_to_section_four` ＋ 辅助 `_parse_reserved_section_four_number`；自读 `reports/sweep-orphan-state.json`，**未改** `_track_and_alert_orphan_paths` 的签名与返回值
- [x] 3.4 一处调用，排在两份队列文件的循环**之后**、且在本轮**全部 git 操作之后**（含 `_reconcile_with_origin_and_push`）——它会 acquire 锁并把队列文件改脏，放在推送前会与 autostash 抢同一批文件
- [x] 3.5 当日去重＝在既有 orphan-state 条目上加字段；跨天仍孤儿则再登（「登过一次即永久静默」是 `gap_alert` 教训的另一面）
- [x] 3.6 走既有 CLI 三步；🔴 **用位置式 `--cell` 而非 `--set`**——`--set` 走 `queue_table.SECTION_COLUMN_NAMES`，而编辑锁取不到平台包时回落的内建隔离桩**没有**这个属性 ⇒ `--set` 在隔离环境当场 AttributeError；本函数是**无人值守**路径（每 27 分钟自跑一轮），不能依赖一条在部分环境必崩的入口
- [x] 3.7 §四 行：文件清单（≤10 条，超出写「…等 N 个」）＋ 每个文件的首见时间与存续小时数 ＋ (a) 代登 / (b) 丢弃；等谁＝Shao Peishen；**行内明写「本项无默认」**
- [x] 3.8 acquire／取号／追行／release 四处失败各自只留一行日志、不改本轮退出码；`--dry-run` 只打印；**零命中每轮回显**
- [x] 3.9 🔴 **顺带发现、如实登记、本包不修**：编辑锁的「隔离环境兜底桩」（`工具-共享文档编辑锁.py` 里的 `class queue_table`）**缺 `has_unbalanced_backtick_run` 与 `SECTION_COLUMN_NAMES`**，而 master 的权威模块两者都有、且 `_build_append_row_line`／`_content_cells_from_named` 直接调用 ⇒ **任何没有 `5-平台底座/zhuopin_platform` 的 checkout 跑 `append-row` 都会 AttributeError 崩溃**。生产不撞只因生产恒有那个包。该桩 docstring 明写「取值须与权威模块保持一致」——这是一次真实漂移。本包不顺手扩范围去修，交总线派单

## 4. 单测 · sweep 侧（`test_工具-落库sweep.py::OrphanSectionFourEscalationTests`，10 passed）

- [x] 4.1 跨阈值孤儿 ⇒ §四 一行；断言含文件名、`已孤儿`／`首见`、`(a) 代登`／`(b) 丢弃`、`本项无默认`、`Shao Peishen`
- [x] 4.2 未跨阈值 ⇒ 不登
- [x] 4.3 同日多轮 ⇒ 只一行；跨天仍孤儿 ⇒ 再一行
- [x] 4.4 反例：升格后孤儿文件**仍在 `git status` 里**，且 §二 未被代写声明
- [x] 4.5 反例：§四 分区被拿掉 ⇒ 追行必被拒，本轮退出码仍为 0
- [x] 4.6 `--dry-run` 不写队列 ＋ 零命中回显（`本轮待升格 0 个`）
- [x] 4.7 判据锚定：两个阈值常量必须不同且升格阈值更大；预留号只解析不猜（解析不出即 `None`）
- [x] 4.8 **夹具补齐（本类 setUp）**：还原 `5-平台底座/zhuopin_platform`（`queue_table`／`followup_gate` ＋ 两个纯文档 `__init__`）与 `工具-密钥扫描lint.py`，并给队列夹具补「编号高水位线」标注行。⚠️ 三处都是**夹具缺件**、不是本次改动的问题：`acquire --reserve` 与 `append-row` 缺任一即失败——同 `SweepTestBase` 复制 `工具-opener块lint.py` 的既有惯例，**夹具还原真实布局才测得出真实行为**

## 5. 验收与收尾

- [x] 5.1 🔴 **反向对照已实测（tasks 2.11）**：把 `工具-共享文档编辑锁.py` 换回 master 版（`git show origin/master:…`）跑同一批 —— **19 failed / 21 passed**，新增用例悉数变红（`test_blanket_waiver_is_rejected`、`test_named_waiver_releases_only_named_files`、`test_registration_waiver_scope_excludes_touched_rows`、`ReleaseWaiverCliTests` 全部等），而三条反例（机器人身份豁免两条 ＋ `opener豁免：` 触碰行放行一条）**保持绿** ⇒ 证明新增用例咬住的是本次改动、且未误伤身份通路与另两个逃生阀。已用 md5 核对还原（`5ae83a24…`）。
- [x] 5.2 ⚠️ **反向对照顺带证伪了一条本以为有效的用例，如实记在这里**：白盒的 `test_stale_inline_waiver_in_touched_row_no_longer_passes` 在 master 版上**同样是绿的** —— 因为「本次触碰过的队列行」是**调用点**拼进 `waiver_sources` 的，白盒直接调校验函数根本走不到那一步。⇒ 补 `ReleaseWaiverCliTests::test_stale_waiver_in_touched_queue_row_no_longer_passes_end_to_end`（真 CLI 完整时间线：acquire → 队列行里写下点了名的旧豁免 → 另有一个它没点名的脏文件 → release 必须拒），那条才是真证明；白盒那条保留、但文档字符串已写明它证明不了什么。**一条自我感觉良好的用例不该冒充证据。**
- [x] 5.3 全量 `python -m pytest 0-学习与工具/test_工具-共享文档编辑锁.py 0-学习与工具/test_工具-落库sweep.py` ⇒ **876 passed ＋ 73 subtests passed，0 失败**（39 分 30 秒）。含邻居工具整套——「跑邻居测试」这条是 2026-08-23 sweep 断链的教训。
- [x] 5.3b `openspec validate --all --strict` ⇒ **174 passed／0 failed**（本包新增 2 条 spec delta 后由 172 增至 174）
- [x] 5.4 push 分支，**不 ff master**（🟡，ff 由总线一字母）
- [x] 5.5 `#416` 状态列追加收工段（K2 ≤4 KB，超即外置）
- [x] 5.6 §二 登批次（commit 由 `ZhuopinCommitSweep` 自动取活）
- [x] 5.4b ✅ **ff 完成（Shao Peishen 答 `1a`）**：`22cbd15..8e8eb0c` 真 fast-forward。合入基线为含 `#479` 的 master——派单件担心的「同碰 `工具-落库sweep.py`」真实发生并解决：两次 rebase 各撞一处冲突，性质均为「两边各加各的」，两边保留。凭据档由他答 `a` 取定向档（sweep 全套 **462 passed ＋ 66 subtests**、编辑锁本包三组 **60 passed ＋ 3 subtests**、上一基线两文件全量 **904 passed ＋ 94 subtests**）。
- [x] 5.4c **生产实证**：用合入版代码对真实仓库 `--dry-run` ⇒ `孤儿升格 §四 扫描（阈值 6 小时，当日去重）：本轮待升格 10 个` ＋ `[dry-run] 本应升格 §四 一行（10 个孤儿），本次不写`，无异常。⚠️ **一次自我更正**：首次 dry-run 跑的是主 checkout 的**旧代码**（`git push origin HEAD:master` 只更新远端，本地 `master` 仍在 `22cbd15`），当时「无升格行」的结论无效——**「命令跑了」与「跑的是我以为的那份代码」是两件事**，同族于 rules/两桌同步与取证 §三「只读命令结果太干净先怀疑没读到对象」。
- [x] 5.4d 🔴 **新门禁在本次收工时当场咬住了作者本人——最好的验收**：K2 四次外置把 `1-转型规划/0-全景路线图/队列行日志/#416.md` 改脏，而本次 note 的点名豁免没有点它（**它是本线自己的文件、本就不该豁免**），`release` 直接拒绝并打印「本次豁免已点名放行 13 个，下列 1 个**未被点名**」。**旧代码会被同一句豁免把它一起放行、掉在地上。** 按规矩登 §二 `B-0907_AM3`，不是补一句豁免。
- [ ] 5.7 🔭 **预期观察窗口：1 天**（Shao Peishen 2026-09-07 答 `a`）——回填**下一轮 sweep 真实升格后的孤儿数**到 `#416`，这是唯一能证明「止血真的止住了」的生产信号。**当刻基线**：孤儿 13 个，其中 **10 个已 ≥6 小时**（最老 10.4 h），下一轮即应升格进 §四。回填后本包归档、`#416` ⑶ 方可销号（⑴⑵⑷⑸⑺ 与 ⑶ 无关、仍开）。
- [ ] 5.8 通知 Cowork：机器守已落地，可把 `.claude/rules/队列与落库.md` 的止血句降为一行指针
- [ ] 5.9 待派：⑴ 隔离桩漂移（tasks 3.9）；⑵ 本分支与 `#455` 分支同改 `工具-共享文档编辑锁.py`，**后 ff 的一方须解冲突**（tasks 1.1）
