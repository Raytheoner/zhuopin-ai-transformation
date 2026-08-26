"""落库 sweep 定时任务（队列 #68③，Paul 2026-07-24 拍板五条硬要求）。

背景：跨桌任务队列.md §二"待 commit 批次"是 Cowork/专线登记、CC 手工取活提交的
唯一载体——《构建自动化workflow设计-2026-07-21.md》§三 指出"⑤落地"环节虽已半自动，
但仍要等 Paul 逐条转述"交 CC 取活"，是两大堵点之一。本脚本把这一步 sweep 化：
定时扫 §二，把已就绪（文件确已落盘、无关改动不干扰）的待 commit 批次自动
git add + commit + push，并把队列自身的销行标记与批次内容**合进同一个 commit**，
从机制上消灭"内容已提交、销行还没跟上"的慢一拍尾巴（历史上曾靠 CC 手工逐行核对
git 历史才救回，见协议〇.7 背景）。

五条硬要求（Paul 2026-07-24）与本脚本对应实现：
① 只 `git add` 各批次行列出的文件，绝不 `git add -A`——见 _resolve_batch_files()，
   仅对已在批次"文件清单"列中以反引号标出的路径做 add，其余任何脏文件一律不碰。
② 改队列销行前 acquire 编辑锁、改完 release；销行标记与批次文件同一 commit——
   见 _process_batch()：git add 批次文件 → 加锁改队列 → 一次 commit 两者一起进。
③ 主工作区非 master / 非 clean / 推送非快进时跳过本轮并告警，不强推——见
   _check_preconditions() 与 _reconcile_with_origin_and_push()。
④ 计划任务 Action 指主工作区稳定路径（非建造 worktree）+ SYSTEM + AtStartup +
   绝对路径烘焙——本脚本运行时另有 MAIN_WORKSPACE 断言兜底（见 _resolve_repo_root），
   注册脚本见 `register-commit-sweep-task.ps1`。
⑤ 台账随 sweep 重跑一次（仅当本轮确有批次被处理时才重跑，见 main() 末尾）。

"非 clean" 的定义（关键设计决策，非字面"git status 必须全空"）：
    §二 待 commit 批次的存在本身就意味着主工作区必然有未提交改动（那正是
    "待 commit"的含义）——若把"clean"理解成"git status 完全无输出"，sweep 将
    永远无法处理任何批次，自相矛盾。本脚本把"clean"定义为：
    **git status 里的每一处脏改动，都能对应到当前某条待 commit 批次的"文件清单"
    声明——如果存在声明之外的脏文件/未跟踪文件，视为"非 clean"，整轮跳过。**
    这与要求①同源：只处理"账面对得上"的批次，账面之外的任何东西（哪怕看起来
    无害）都交给人工判断，不猜。2026-07-24 实测：主工作区当时确有 CLAUDE.md 的
    未提交改动 + 4 个未跟踪文件，均不属于任何待 commit 批次声明——sweep 据此正确
    整轮跳过，是本设计决策的第一次真实验证（见收工报告）。

退出码：0=本轮正常结束（无论是"处理了批次"还是"安全跳过"）；
        2=出现需要人工介入的异常（本地已提交但推送不了/非快进，不会自动强推；
          含起跑前置分叉检测，见下）；
        1=脚本自身参数或环境错误（不应在正常运行中出现）。

分叉静默停摆告警（队列 #171，2026-07-30 Antigravity 评审 triage 核证发现）：
起跑前置检查 `_verify_fast_forward(refetch=False, ...)` 此前失败时退出码固定
为 0——计划任务看到的是"成功"，而本脚本全文此前无任何 webhook/notify，唯一
留痕是 `reports/sweep-commit.log`，只有人工翻日志才会发现。真实触发条件：PR
在本脚本运行窗口内（早期 fetch 与提交后 push 之间）被并发合并，本地提交已落、
origin 已前移，此后每轮都在这个前置检查处跳过，永久静默直到人工介入（PR 在
本脚本空闲时合并不会触发——下一轮 `_sync_master_if_behind_origin` 会自动
`--ff-only` 追上，不构成分叉）。修法：① 前置检查改用 `is_fork=True` 标记
（见 `SweepAbort.is_fork`），退出码由 0 改为 2（人工介入语义），并复用
`发企微.py` 同款零依赖 webhook 推送主动告警一次（见 `_handle_fork_detected`）；
② 连续多轮仍分叉时，告警文案带上连续轮次（见 `_read_fork_state`/
`_write_fork_state` 持久化到 `reports/sweep-fork-state.json`），分叉一旦解除
（前置检查转为通过）立即清空该状态，不与"偶发跳过"（非 master/非 clean/
无待处理批次等健康跳过路径，退出码仍为 0，不触发告警）混淆。**勿采信"拦
协调文件 PR 可解此问题"**——非快进由 commit 祖先关系决定，与改哪个文件无关，
只有主动告警才能让"静默"变"有人知道"。

陈旧 `.git/index.lock` 前置自愈（#121(b)，2026-07-27 补）：起跑第一步先查
`.git/index.lock`——超过 STALE_INDEX_LOCK_MINUTES（默认 10 分钟）未清的判定
为异常退出残留，自动清除后继续；新鲜的（大概率是真实并发 git 进程）不抢占，
优雅跳过本轮并写日志。见 _heal_stale_index_lock()——修复前该文件残留会让
后续 `_run_git`（check=True）抛未捕获异常，表现正是"计划任务 LastTaskResult=1
但日志无新条目"。

批次判据显式化（2026-07-28 补，根治静默失效）：原判据 `"✅" not in
status_cell` 把"待处理"定义成"不含✅"——登记方一旦图省事在状态列说明性
文字里带了✅（如"✅ 已完成（本次登记，待 sweep 落库）"），该批次就被永久
判定为"已处理"而跳过，且没有任何日志提示。2026-07-27 深夜已实测命中两条
批次（队列 §二 顶部登记说明记有 `B-0728财务专线核实`/`B-0728队列#125回填`
两例），当时全靠人工肉眼发现、手改回不含✅的写法才追上。根治：判据改为
显式"待"字样（见 _classify_section_two_rows()）——只有状态列含"待"（待
处理/待取活/待 sweep 落库等）才算待处理，不论是否同时误带"✅"；状态列
既不含"✅"也不含"待"的模糊状态，不再被默默漏过，改为输出告警日志、不纳入
本轮处理，交人工核查（宁可吵不可哑）。

本地 master 落后 origin 前置自愈（2026-07-28 补）：主工作区本地 `master`
分支指针不会随"其他 worktree 把改动推去 origin/master"自动前进——`git
fetch` 只更新 `origin/master` 远程跟踪分支，本地分支需要显式 merge 才会
移动。2026-07-27 一天内三次出现这一情形，若不处理，下一步"能否快进推送"
检查会把纯粹的"落后"误判为"跳过本轮"。见 _sync_master_if_behind_origin()：
本地是 origin/master 祖先（纯落后、可快进）即自动 `git merge --ff-only
origin/master` 追上再继续干活；两边已分叉（互不为祖先）则不动手，仍按原
语义告警跳过本轮，不强推、不自动 rebase。

批次文件匹配精确相等优先（队列 #234(1)，2026-08-04 值周巡检取证）：
`_resolve_batch_files` 原按后缀匹配（`d == frag or d.endswith("/" + frag)`）
把片段对到脏路径，同名文件出现在两处时（如根 `CLAUDE.md` 与某场景目录下
也有一份 `CLAUDE.md`）会各算一次命中而判 ambiguous——即便其中一个是精确
相等，也会被同一片段的其它候选连累，导致早已正确声明的批次被
`unaccounted` 全局门槛一并跳过（08-04 实测 20 批积压）。现改为存在精确
相等命中时唯一采用它，不再把同一轮的后缀命中一并计入歧义；无精确命中
时仍按原逻辑处理（≥2 个后缀命中依然判 ambiguous，安全边界不变）。

启动即写日志首行（队列 #222，2026-08-04）：main() 起跑最开头（`_heal_
stale_index_lock` 等任何有风险的代码执行之前）就把"=== sweep 运行 ... ==="
这一行单独落盘一次，不再等到收尾统一 flush——否则"启动后立刻发生连
`except Exception` 都接不住的崩溃"与"计划任务压根没触发"在日志上表现
完全相同（`sweep-commit.log` 均无新内容），判据失去分辨力（#121(b) 遗留
未做项）。此后各退出路径改用 `_flush_remaining_log`，只落盘首行之后
新增的内容，不重复写入这一行。

决策提醒第二载体（队列 #219，2026-08-04）：`ZhuopinDecisionReminderDaily`
是决策提醒的唯一载体——每日仅一次、需已登录、错过不补、失败无告警，
2026-08-03 真实丢过一轮。起跑段新增 `_run_decision_reminder_second_
carrier`，走子进程调用 `decision_reminder_check.py`（每小时随 sweep 一并
触发，去重沿用其自身既有 `ESCALATION_INTERVALS_DAYS`，双载体不会重复
打扰），须排在 sweep 自己取编辑锁窗口之外（main() 接线固定顺序，见其内
注释）。

批次隔离——unaccounted 从"全局门"改为"逐批次判定"（队列 #238，合并
#234(2) 与 #230-2d，2026-08-05）：原实现只要 `git status` 里存在一个不属于
任何批次声明的脏路径，`main()` 就整轮 `return 0`——已正确声明、彼此毫无
关系的批次被连带跳过（08-04 实测 17-20 批积压，堵点常常只有几个真文件，
详见 #234/#236 取证）。改为 `_partition_pending_rows_by_batch_isolation`：
一个批次是否被阻塞，只取决于它**自己**的声明片段解析是否命中
`ambiguous`（即该片段在当前脏路径中有 ≥2 个候选、且无精确相等命中，见
`_resolve_batch_files` 队列 #234(1)）——`ambiguous` 片段对应的候选路径
必然不在 `declared_all` 里，这正是"声明片段与未声明脏文件有交集"的精确
含义。与它无关的其它批次不受影响，照常落库；被阻塞的批次逐条写明因
哪个片段命中几处候选而暂缓（可解释日志，回应 #234 附带要求：08-03 本
项目正因缺这行日志而误判为 bug、白花一轮取证）。真正"没人声明"的孤儿
脏文件（不出现在任何批次的 resolved 或 ambiguous 候选里）不阻塞任何
批次，只作为独立提示列出——持续存在则交给 #236(2) 的孤儿脏文件告警去
处理，sweep 主流程本身不再因它们停摆。

孤儿脏文件告警（队列 #236(2)，2026-08-05）：#238 解除"孤儿阻塞全局"后，
孤儿脏文件仍需要"被人看见"——2026-08-04 实测 4 个无主孤儿文件（原
session 随 Claude Desktop 重启失联）挡住 20 个批次跨天不落库，根因是
"收工登记批次没有触发点"（协议〇.1/〇.3 要求认领即声明，但回合制
session 没有回合可用来执行）；sweep 只说"不属于任何批次声明"，既不
追溯也不告警。`_track_and_alert_orphan_paths` 持久化每个孤儿路径的
首次发现时刻（`reports/sweep-orphan-state.json`），超过
`ORPHAN_ALERT_THRESHOLD_HOURS` 才复用 #171 的 webhook 通道点名一次，
此后每满一个阈值周期再提醒一次（不逐轮/每小时重复打扰——#147
`gap_alert` 的"狼来了"教训：过密提醒会被无视）；孤儿一旦被声明或消失
即从状态里清除。

发布收口第②关：部署留痕检查（队列 #229，Shao Peishen 2026-08-03 拍板
选 (a)，2026-08-05）：同族本周复发三次的"收口最后一段没人记得"——#204
问题已解决但载体未更正／#221 代码未并 master 而生产已部署／#228 通知
已送达而生产未更新。`_find_missing_deployment_trace` 在批次落库后检查
本轮 touched_paths 是否命中已部署场景白名单（初版宁窄勿宽，仅
SC8/QD-B/FI2 三场景目录 + 命令中心，判据落在各自 CLAUDE.md／仓库根
CLAUDE.md 是否同批改动这一可机检事实，不解析内容语义、不判断"是否
真的部署了"），命中且未见留痕即在日志与 webhook 附一句提示——纯提示，
不阻断、不改退出码（同 #198(c) 范式）。

判据锚定状态列开头片段（队列 #248，openspec 变更包
`sweep-editlock-status-keyword-anchoring`，2026-08-05）：2026-07-28 那次
"批次判据显式化"修法（见上）解决了"状态列误带✅"，但仍是对整个状态列做
子串扫描——#248 真实事故：一条状态列开头是`✅ 已完成`、但说明文字里引用
了本判据原文（含"待"字）的批次被误判为待处理，取活提交、覆写了原说明。
改为只依据 `_leading_status_segment()` 返回的"开头片段"（状态列去除前导
`*`/空白后、第一个句级分隔符"。"/"——"/"━━━"之前的文本）判定，分隔符
之后的说明/引用/复述文字不再参与判定。**为什么不是简单地"只看第一个
字符"**：现存回归测试固化的 2026-07-27 真实误写场景——"✅ 已完成（本次
登记，待 sweep 落库）"——"待"字紧跟在同一个短促、无分隔符的括注里，若
把"开头"收窄到"第一个字符"会让这条误写重新被判成"已完成"而漏处理，
等于用本次修法重新引入 2026-07-28 要根治的旧问题；用句级分隔符界定
"开头片段"边界，两个真实事故场景（本次 #248 与 2026-07-27 旧误写）均已
用回归测试固化验证不冲突，见 `_leading_status_segment()` 与
`ClassifySectionTwoRowsUnitTests`。同批同源修法见编辑锁 ④断言门槛
（`工具-共享文档编辑锁.py` 的 `QUOTED_SPAN_RE`）——两处判据历史上都经历
过"整行扫描→只查状态列"这一次收窄，本次是该收窄路径的下一步，但两处
的具体实现不同（本处锚定开头，编辑锁排除引号片段），design.md 完整
论证了原因（sweep 状态列是短符号前缀，编辑锁状态列是多分句长叙述，
"只看开头"这一具体规则对后者不成立）。

批次先提交、后统一对齐 origin/master（队列 #288，openspec 变更包
`sweep-ff-sync-batch-reorder`，2026-08-06）：本节修法的既有实现里，`main()`
在**批次处理之前**调用 `_sync_master_if_behind_origin`（`git merge
--ff-only origin/master`）——但 §二 待 commit 批次的存在本身就意味着工作区
必然脏（见上"非 clean 的定义"一节），一旦 origin 上有提交也改了同一个
文件（跨桌任务队列.md 是 sweep 的核心工作对象，2026-08-06 实测近 20 个
提交 100% 触碰它），git 会因"本地未提交改动将被合并覆盖"拒绝这次 ff
合并，函数据此 `SweepAbort`，**排在其后的批次处理整轮走不到**——2026-08-06
当日已两次真实卡死需人工介入（先 `git commit`，再 `git pull --rebase`，
再 `git push`）。

三个候选修法（A·先提交再同步再 rebase／B·stash 保护式 ff／C·失败降级为
告警但继续，完整分析见队列 #288）中选定并加强了 A，否掉 B（挡住 ff 的
常常正是"已被批次声明、不能 stash"的那个文件）与单独的 C（只解决"不
整轮跳过"，不解决"最终仍需人工 rebase"）——完整取舍见 design.md「决策点
1」。改法：`_process_normal_batch`/遗留尾巴批次/`_rerun_ledger` 均改为
**只本地提交，不再各自校验快进或推送**；`main()` 在这些提交全部完成、
工作区因此恢复干净之后，调用新增的 `_reconcile_with_origin_and_push`
统一对齐一次——按本地 HEAD 与 origin/master 的关系分派：相等则无事可做；
纯落后则 `--ff-only` 合并追上；纯领先则跳过合并直接推送；**已分叉则
`git rebase origin/master`**（提交完成后本地必然领先，origin 若同期也有
新提交即构成分叉，这在旧设计里是"绝不尝试、直接跳过"的场景，本次改为
主动尝试自动对齐）——rebase 失败即 `git rebase --abort` 回滚到批次已提交
的干净状态（本地提交完整保留，不丢失），复用既有 #171 分叉告警（含
`is_fork=True`／`FORK_EXIT_CODE`／webhook／连续轮次持久化），不自动解
冲突、不强推。对齐成功后统一 `git push` 一次，覆盖本轮全部提交（不再是
每个批次各自 push）。旧的 `_sync_master_if_behind_origin` 与
`_verify_fast_forward` 两个函数在重构后调用点清零，已整体删除。

**是打破了自锁循环，还是只是让它不再阻塞批次？——两者都是，取决于是否
发生真实冲突**（design.md「决策点 2」完整论证，此处摘要结论）：队列文件
是追加型文件，不同会话通常编辑不同行——对这**绝大多数不冲突**的并发编辑
场景，是真正打破了"越需要同步越同步不了"的自锁循环（提交→rebase→推送
一次跑完，不会自我延续、不会越拖越大）；对**少数真实内容冲突**（同一行
被双方修改）的场景，不是打破循环，而是让循环不再阻塞其它批次——本地
提交安全保留、告警主动发出，但仍需人工介入才能真正解除，这与候选 C 的
止血效果相同。**不追求消灭一切需要人工介入的情形**，是把"需要人工介入
的情形"从"20/20 的必然"收窄到"真实内容冲突的少数概率事件"。

起跑段前置守卫不再整轮中止（队列 #309 子项 F，2026-08-08）：`_push_any_
unpushed_commits`（起跑段①之后，批次处理之前）此前一旦发现"本地领先
且不可快进"（已分叉）即 `SweepAbort(is_fork=True)`，与本节修法的旧
`_sync_master_if_behind_origin` 犯的是**同一个错**——前置检查排在批次
处理之前、且检测到分叉就整轮退出，把排在收尾段、自带 rebase 能力的
`_reconcile_with_origin_and_push` 挡在门外，走不到。2026-08-08 02:35
UTC 起连续 4 轮整轮跳过、连发 4 条分叉告警即实测坐实（本地环境总线的
提交 / origin CC 的提交两侧都改了队列文件），期间已登记的 §二 批次
始终落不了库。修法：检测到分叉时不再 `SweepAbort`，只记录日志后
`return`，把对齐统一交给收尾段——批次照常本地提交，工作区恢复干净后
`_reconcile_with_origin_and_push` 重新 fetch 一次并按当时的 ahead/behind
关系自动 `git rebase origin/master`；真无法自动解决（真实内容冲突）时
仍会落回既有的 `git rebase --abort` + 分叉告警路径，语义不变，只是
判定时机从"起跑段一律拦"收窄为"收尾段确认真无法自动解决才拦"，与
本节上方"决策点 2"的既有结论（少数真实冲突场景止血、多数场景真正
打破自锁循环）一致——本次只是把该结论应用到另一处犯了同样错误的
前置检查上。

起跑段中止判据立为通则（队列 #328，2026-08-17，变更包
`sweep-startup-nonblocking`）：上面两段（#288／#309 子项 F）各自修的
是"自己撞见的那一处"，而 #309-F 行内已自陈识别出**「起跑段不得整轮
return」这条通则、却只写在一行队列正文里，没有任何机制拿它去扫剩下的
起跑段检查**——于是第三例（`_fetch` 网络失败即整轮中止）原地不动，实测
`reports/sweep-commit.log` 全量 715 轮命中 20 轮（2.8%、11 个不同日期）。
本次因此不只修那一处：

  判据（通则本体）——**一处起跑段检查是否该中止整轮，取决于它挡住的
  那些本地工作，是否真的依赖它所检查的那个前提。** 依赖（仓库物理状态
  不可用，继续会失败或有害）⇒ 拦；不依赖（外部依赖暂时不可用，本地
  工作与之无关）⇒ 记录后继续，把该前提的职责交给真正需要它的那一段。

按此判据把起跑段现存**九个** `raise SweepAbort` 位点逐一过了一遍，结论
**7 处维持拦截、2 处降级**（`_fetch` 与 `_push_any_unpushed_commits` 的
补推失败；后者不在派单件字面范围内，是扫描扫出来的"第四例"）。逐位点
判定表见变更包 design §2。**通则本身由 `test_工具-落库sweep.py::
StartupAbortSiteInventoryTests` 做成机制守**——AST 静态扫描起跑段六个
函数的全部 `raise SweepAbort`，与冻结清单逐项比对，新增/删除/移位即
失败，强制作者显式分类。刻意用 AST 而非正则：注释、字符串字面量与跨行
调用会让正则给出假阴性，那正是本项目"用正则猜代码"要收敛的家族。

定时任务真身↔镜像自动核对（队列 #235/#188，2026-08-06）：#169 已实现
`工具-定时任务源码备份.py`（规范化逐行比对+差异自动写回镜像，见其文件头
说明），但"挂载到自动触发器"这一半此前未做——真身漂移因此只能靠人想起来
手动跑一次，而 #188 已实证这类漂移"不报错、只是安静地给出反向答案"。
`_run_scheduled_task_mirror_sync` 在起跑段（与 #192-A/#219 同一批、须排在
sweep 自己取编辑锁窗口之外）走子进程调用该脚本（零依赖隔离，理由同
`_flush_pending_lock_appends`）。与 #192-A/#219 两个"纯记日志"子进程不同，
本次调用**自身会写文件**（更正镜像内容）——若不处理，这些改动会在
`dirty_paths = _status_paths(...)` 那一刻变成"没人声明的孤儿脏文件"（同
#289 指出的"自动机制改了文件、没人负责让它落库"）。故本函数仿照
`_rerun_ledger` 的做法：调用脚本后立即检查镜像目录的 git 状态，有变化即
就地 `git add`+本地 commit（不单独 push，随本轮末尾的
`_reconcile_with_origin_and_push` 一并推送），使 `dirty_paths` 捕获时这些
文件已经是 clean 的——不产生新孤儿。检出真实差异（脚本报 `updated`）或
命中凭据扫描拦截（脚本退出码 1）时复用 #171 的 webhook 通道各发一次告警
（满足 #188 原始诉求"不一致即告警"）；无变化时静默，不产生噪音。

每轮落库批次数计数（队列 #257，2026-08-06，P3，先计数不告警）：判断"该
转场了"目前全靠人的主观感觉，2026-08-05 单 session 实证错误集中在第 6 次
落库之后。在把"批次数 ≥N 即提示"这类阈值机制化之前，样本量只有 1、不足以
定阈值——本轮只做 `_record_batch_landing_count`：每轮 sweep 把本轮实际落库
的批次数与批次 ID 写入 `reports/sweep-batch-landing-count.jsonl`，不告警、
不阻断、不改变任何既有行为，纯粹积累数据供后续（样本足够时）另行评估阈值。

孤儿脏文件解除通知（队列 #301，2026-08-07，Shao Peishen 选 (b)）：
`_track_and_alert_orphan_paths` 此前只在孤儿"出现且跨阈值"时告警，孤儿
消失（被声明或已处理）后无任何通知——2026-08-07 实测：孤儿告警送达
Shao Peishen 前它已自愈，他只能凭消息本身判断不了当前是否还成立，被迫
转人查证（成本落在他身上）。修法：孤儿从状态清除时，若其 `last_alerted`
非空（即真的告警过），补发一条"✅ 已解除"通知（路径+存续时长+"无需
处置"）；`last_alerted` 为空（从未跨过阈值即消失）不补发——为一件对方
根本没听说过的事发解除通知，本身就是新噪音（#147 教训）。复用既有
webhook 通道，不新起通道。

抄近路后补全欠账机制化（队列 #298，2026-08-07，Shao Peishen「推广到所有
域和所有任务」当日扩容拍板）：完工即归档是人守规则（CLAUDE.md §5），无
任何机制检查——#295 实证：FI2 已部署 `.51:8094` 并接新建造，但其
`fi2-recon-mvp` 变更包 90% 完成、3 天未归档，5 个 capability delta 全部
躺在 `openspec/changes/` 进不了 `openspec/specs/`，可追溯链断在此。两项
检测，纯提示不阻断，挂 sweep 每小时随批次处理一并跑（与本轮是否有批次
落库无关，检测对象是仓库整体 openspec 状态，不依赖 touched_paths）：
M1 · 已建造场景 spec 覆盖缺口——扫描域按 Shao Peishen 当日扩容拍板由
"已部署场景白名单"（#229 `DEPLOYED_SCENARIO_PREFIXES`）扩为
`4-数字员工/*/*/` 全部场景：已建造（≥1 个 .py）、未标退役（CLAUDE.md
含"退役"字样即豁免）的场景，按其目录名短代码前缀（`_scenario_short_code`
——兼容 `QD-A`/`QD-B` 这类代码本身含连字符的写法）查 `openspec/specs/`
是否至少有一个同前缀 capability，零命中即缺口，并顺带查
`openspec/changes/*/specs/` 指出 delta 躺在哪个未归档包（形态甲）还是
压根没写过（形态乙，归档也救不了，须重新补写）。`5-平台底座/*/` 全部包
无短代码前缀约定可循（`platform-*`/`aibot-*`/`sweep-*` 等 capability 名称
与包目录名之间没有机械对应关系），改用弱信号（spec.md 内容是否提及
包名字面）且只列入日志、不触发 webhook——`deploy-tools` 是当前唯一
"零提及"实例，与本行原始判断一致，见 `_find_platform_packages_without_
spec_mention`。
M2 · 在途变更包滞留提示——完成率（`tasks.md` 勾选比例）≥
`STALE_CHANGE_COMPLETION_THRESHOLD` 且距最后一次改动≥
`STALE_CHANGE_MIN_DAYS_IDLE` 天即滞留；⚠️ 行内原文示例阈值写「≥80% 且
≥7 天」，但同段给出的命中案例 `fi2-recon-mvp`（90%/3天）与该阈值本身
矛盾（3<7，按字面不会命中，已用 `git log -1 --format=%ct` 核实其真实
最后改动确为 3 天前）——判定为行文疏漏，天数阈值改取与给出的最小真实
命中案例一致的下界（3 天），完成率阈值不变；两个真实命中案例
（90%/3天、82%/16天）与放过案例（19%/`wecom-listener-macos-migration`，
明显没做完）在新阈值下判定结果不变，已实测核对。降噪：包自身
`proposal.md`/`design.md`/`tasks.md` 含"暂不归档"字样即跳过（不入
"滞留"清单）——`aibot-queue-sync-checkout-guard` 即为此类（`tasks.md`
第 29 行原文引用"暂不归档"，#287 明写须先观察真实生产流量）。
队列 #314②（2026-08-09，Shao Peishen 拍板 (c)）：命中上述条件后，若
包内声明了"预期观察窗口"（`OBSERVATION_WINDOW_RE`，同一扫描范围），
且未超窗，改报"观察中（已等 N 天／窗口 M 天）"、不计入"疑似遗忘归档"
异常 key 集合（`_announce_stale_in_flight_changes` 内 `observing`/
`escalate` 两分支）——立论：这三个包不是被遗忘，是在等真实场景自然
发生，"疑似遗忘归档"这个措辞与事实不符、没有信息量，久而久之会训练
人忽略这一整类告警。超窗、或未声明窗口的（后者即向后兼容：维持现状
报法，不因未声明而报错），一律走原有"疑似遗忘归档"路径不变。
两项检测均持久化"已告警过的 key"（`SCENARIO_SPEC_GAP_STATE_REL`/
`STALE_CHANGE_STATE_REL`），24 小时内不重复推送同一 key（同 #236(2) 的
"狼来了"防线——M1/M2 检测的都是标准长期存在的结构性状态，逐轮/每小时
重复推送必被无视）；只提示、不阻断、不改退出码、不自动归档（归档要跑
`/opsx:archive` 并做完工判断，机制只负责让欠账不静默）；只判"spec
存不存在"，不判"spec对不对"（空壳 capability 也能让 M1 静音，拦不住
"同步得不对"）；存量缺口的实际补齐是队列 #299 的另一项工作，本节只管
"机制不让它再发生"。

批量派活前状态核对（队列 #302，2026-08-07，Shao Peishen「这个问题需要
马上解决」P1）：2026-08-07 一次批量派活扫描撞出 4 条状态滞后行（#205-A/
#258/#236(1)/#188——均已被别的批次"顺带做完"，做的人不知道要回写哪
一行，回写因此无人执行）。新增只读 CLI `--check-stale-pending-rows`
（不写入任何状态，只作派活前核对清单）：扫 §一 状态列开头片段含"待"的
行，与近 `--stale-lookback-days`（默认 `STALE_ROW_LOOKBACK_DAYS`）天的
commit 交叉——主判据（高精度低召回）＝commit 首行 `type(scope):` 里的
scope 含该行号（`_extract_commit_scope` 用 `rfind` 定位右括号，兼容
scope 内自带嵌套括号的行号写法；`_extract_row_numbers` 用 `#(\\d+)`
提取完整数字游程，天然不会把 `#22` 误判命中 `#225`——词边界由数字游程
本身保证，不依赖显式的正则边界断言）；副判据（高召回低精度）＝行的
"触碰区"列路径与 commit 改动文件路径交叉（`_touch_zone_path_matches`，
判据同 `_resolve_batch_files` 的后缀匹配）。三个已实测坐实的误报源均已
在设计层面堵住：子串误命中——按完整数字游程提取，非子串搜索；正文
提及不算完成——只解析 `git log --format=%s` 的首行，不碰 commit body；
校准 commit 自我污染——`_extract_commit_scope` 只认冒号前的 scope 括号
内容，"四行滞后状态校准(#205A.../...)" 这类描述性文字出现在冒号之后，
不在 scope 提取范围内，天然被排除。纯只读、纯提示，不改任何状态，判定
权留给人。

队列 #306（转义与列数校验收归权威模块，openspec 变更包
queue-table-shared-parser-consolidation）：`_parse_section_two`/
`_parse_section_one` 的列数校验改从
`zhuopin_platform.shared_tools.queue_table.SECTION_COLUMN_COUNTS` 读取，
不再本地硬编码 4/8。

用法：
  python 0-学习与工具/工具-落库sweep.py            # 真跑
  python 0-学习与工具/工具-落库sweep.py --dry-run   # 只打印计划动作，不落地
  python 0-学习与工具/工具-落库sweep.py --check-stale-pending-rows  # 队列 #302 只读核对
  # --repo-root 仅供单测覆盖 MAIN_WORKSPACE 断言，生产不要传
"""
from __future__ import annotations

import argparse
import fnmatch
import importlib.util
import json
import re
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# 队列 #306：本脚本自身所在的 worktree 本地路径找 zhuopin_platform（同
# 工具-共享文档编辑锁.py 既有引导，与队列 #300 conftest.py 同一原则）。
# 仅当目录真实存在时才尝试 import，缺失时（隔离环境）用本地兜底桩，import
# 本身失败（包损坏）则如实抛出，不静默吞掉。
_QUEUE_TABLE_SEARCH_ROOT = Path(__file__).resolve().parents[1]
_PLATFORM_PATH = _QUEUE_TABLE_SEARCH_ROOT / "5-平台底座" / "zhuopin_platform"
if _PLATFORM_PATH.is_dir():
    if str(_PLATFORM_PATH) not in sys.path:
        sys.path.insert(0, str(_PLATFORM_PATH))
    from zhuopin_platform.shared_tools import queue_table  # noqa: E402
else:
    class queue_table:  # type: ignore[no-redef]
        """隔离环境兜底桩——取值须与 zhuopin_platform.shared_tools.queue_table
        保持一致，见该模块。"""

        SECTION_COLUMN_COUNTS = {"一": 8, "二": 4, "四": 4}
        # 队列 #315：拆分后两份物理文件路径，隔离桩同样须与权威实现保持一致。
        QUEUE_MECHANISM_PATH_REL = "1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md"
        QUEUE_BUSINESS_PATH_REL = "1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md"

        # 简化近似，非逐字节镜像——权威实现按 CommonMark 反引号游程规则
        # 配对（见 queue_table.py::_mask_backtick_spans，队列 #314 apply
        # 阶段真实数据踩坑后从单反引号正则升级而来）；本桩只保证隔离环境
        # 不崩，不追求对双反引号转义单反引号这类少见写法字节级一致。
        _BACKTICK_SPAN_RE = re.compile(r"`[^`]*`")
        _PROTECTED_PIPE_SENTINEL = ""

        @staticmethod
        def split_row_cells(line: str) -> list[str] | None:
            s = line.strip()
            if not s.startswith("|"):
                return None
            sentinel = queue_table._PROTECTED_PIPE_SENTINEL
            protected = queue_table._BACKTICK_SPAN_RE.sub(
                lambda m: m.group(0).replace("|", sentinel), s,
            )
            return [
                c.replace(sentinel, "|").strip()
                for c in protected.strip("|").split("|")
            ]

MAIN_WORKSPACE = Path(r"C:\Dev\zhuopin-ai")
# 队列 #315（apply，2026-08-11）：拆分后本路径转为纯指针文件，不再是权威
# 内容承载——sweep 自身不再用它做任何读写，只在极少数"报告曾经的单一
# 文件路径"式提示文案里可能出现，保留常量本身不删（避免破坏尚未清理的
# 引用），但 `_read_queue`/`_write_queue` 一律改用下方 `_iter_queue_paths()`
# 返回的两份真实内容文件。
QUEUE_REL = "1-转型规划/0-全景路线图/跨桌任务队列.md"
# 本模块局部绑定（同 `工具-共享文档编辑锁.py` 既有惯例，非直接处处引用
# `queue_table` 模块本身）——测试用例按既有 `QUEUE_REL` monkeypatch 惯例
# 也可以同样 monkeypatch 这两个名字，隔离到临时目录。
QUEUE_MECHANISM_PATH_REL = queue_table.QUEUE_MECHANISM_PATH_REL
QUEUE_BUSINESS_PATH_REL = queue_table.QUEUE_BUSINESS_PATH_REL
LEDGER_SCRIPT_REL = "0-学习与工具/工具-文档台账生成.py"
LEDGER_OUTPUT_REL = "1-转型规划/0-全景路线图/文档台账-自动生成.md"
EDIT_LOCK_SCRIPT_REL = "0-学习与工具/工具-共享文档编辑锁.py"
LOG_REL = "reports/sweep-commit.log"
LOCK_WHO = "sweep-commit"
STALE_INDEX_LOCK_MINUTES = 10

# 队列 #171：分叉静默停摆告警。
ENV_REL = ".env"
# 队列 #282 ⑴ 包（变更包 sweep-ops-webhook-cutover，Shao Peishen 2026-08-19 审核通过
# design、决策点 1a）：sweep 的告警全部是"某个自动化机制自己出问题了"，按
# `3-治理与合规/通知通道架构决策件-webhook退役与aibot单一出口-2026-08-06.md` §4.2
# 判据一律发运维逃生通道，MUST NOT 发业务部门群。本模块内该键名只此一份，
# 其余位置（日志文案、docstring）一律从本常量派生，不留字面量副本。
WECOM_WEBHOOK_ENV_KEY = "WECOM_WEBHOOK_URL_OPS"
FORK_STATE_REL = "reports/sweep-fork-state.json"
FORK_EXIT_CODE = 2  # 复用既有"需要人工介入"语义，不新造一套退出码

SECTION_TWO_HEADING = "## 二、"
NEXT_SECTION_PREFIX = "## "

# 队列 #198(a)：main() 通用异常兜底的独立退出码——与"健康跳过（0）"、
# "分叉/需人工介入（FORK_EXIT_CODE=2）"均不同，使 sweep-commit.log 零新增行
# 此后只剩一个含义（任务根本没启动），"跑了但崩了"改为走这个退出码 + 有
# 日志留痕，判据不再二义（见队列 #198(a) 验收物）。
UNEXPECTED_EXIT_CODE = 3

# 队列 #192-A：flush `pending_queue_lock_appends.jsonl` 的子进程触发脚本
# （sweep 刻意不 import aibot_service/zhuopin_platform，见文件头部"零依赖"
# 设计说明——多 worktree 共享全局 editable install，进程内 import 有被
# 静默劫持到别的 checkout 的风险，走子进程规避）。
FLUSH_PENDING_LOCK_SCRIPT_REL = (
    "5-平台底座/wecom-aibot-service/scripts/flush_pending_lock_appends.py"
)

# 队列 #219：决策提醒第二载体——原 `ZhuopinDecisionReminderDaily` 是唯一
# 载体，每日仅一次、需已登录、错过不补、失败无告警，2026-08-03 真实丢过
# 一轮。同 `FLUSH_PENDING_LOCK_SCRIPT_REL` 一样走子进程隔离（零依赖设计，
# async 边界完全留在子进程内，sweep 自身不需要 `asyncio.run()`）。
DECISION_REMINDER_SCRIPT_REL = (
    "5-平台底座/wecom-aibot-service/scripts/decision_reminder_check.py"
)
DECISION_REMINDER_TIMEOUT_SECONDS = 120

# 队列 #235/#188：定时任务真身↔镜像自动核对——脚本本身零依赖（不 import
# zhuopin_platform/aibot_service），走子进程调用同 #192-A/#219 一样的隔离
# 理由；镜像目录常量供本轮"检出变化即本地提交"复用，避免遗留孤儿脏文件。
SCHEDULED_TASK_BACKUP_SCRIPT_REL = "0-学习与工具/工具-定时任务源码备份.py"
SCHEDULED_TASK_MIRROR_DIR_REL = "0-学习与工具/定时任务源码"
SCHEDULED_TASK_MIRROR_TIMEOUT_SECONDS = 60

# 队列 #257（P3，先计数不告警）：每轮落库批次数记录，供后续攒样本定阈值。
SESSION_BATCH_COUNT_LOG_REL = "reports/sweep-batch-landing-count.jsonl"

# 队列 §四 #87 ⑶⑷（2026-08-22）：常驻服务告警判据。
#
# 🔴 本节整体取代了 #198(c) 的 `RESIDENT_SERVICE_PATH_PREFIXES`（单条路径
# 前缀 startswith）——那条判据两个方向同时不准：**多报**（2026-08-22 14:52
# 批次 `B-0822_17` 在服务目录下只改了一份 CLAUDE.md、零行代码，照样告警）
# 与**漏报**（常驻服务运行时导入 `zhuopin_platform`，改底座却一声不吭）。
# 是"退休并取代"而非"叠加过滤层"：前缀常量已删除、不保留兜底分支，判据
# 只有一条实现路径，避免两套判据各自为政（同 #80 一期"切分器只留一份权威
# 实现"的取法）。
#
# 判据＝"该路径是否属于常驻服务的**运行体集合**"，集合由三个来源合并：
#   ① 该服务 `sync-to-server.ps1` 的 `-AppFiles` 显式部署清单（现读现算）
#   ② 同脚本 `-LocalPlatformDir` 指向的平台底座（除其 tests/）
#   ③ 计划任务的执行入口与注册脚本（见 `RESIDENT_SERVICE_ENTRYPOINT_GLOBS`）
# 排除项（文档/tests/sync 脚本自身）**不写黑名单**——它们本就不在①②③任一
# 集合内，靠白名单天然排除。黑名单会漏，白名单只会多报。
RESIDENT_SERVICE_DIR_REL = "5-平台底座/wecom-aibot-service"
RESIDENT_SERVICE_SYNC_SCRIPT_REL = f"{RESIDENT_SERVICE_DIR_REL}/sync-to-server.ps1"
# 解析不出 `-LocalPlatformDir` 时的兜底底座路径（与 `_PLATFORM_PATH` 同源）。
RESIDENT_SERVICE_PLATFORM_FALLBACK_REL = "5-平台底座/zhuopin_platform"
# 底座内不参与运行时的子目录——`scp -r` 确实会把它推上去，但它不被服务导入。
RESIDENT_SERVICE_PLATFORM_EXCLUDED_SUBDIRS = ("tests/",)
#
# 🔴 ③ 只能写成常量，没有任何仓库内文件可读——**计划任务的真实设置不在仓库
# 里**（#199 的核心教训）。本组值取自 2026-08-22 本机 `Get-ScheduledTask`
# 直读实测：`ZhuopinAibotDevListener`(Running)／`ZhuopinDecisionReminderDaily`
# ／`ZhuopinFollowupDispatchDaily` 三个任务的 Action 均为 `wscript.exe` +
# worktree `wecom-service-home` 下本服务目录内的 `run-*.vbs`。
# **复核方式**（勿凭记忆改动本组值）：
#   Get-ScheduledTask | ? TaskName -like 'Zhuopin*' | % { $_.Actions }
# 该复核已列入月度环境体检 #98 核对项——这是本判据明知而接受的残余风险：
# 任务 Action 改了而本常量没跟上，会重新出现漏报，且没有任何自动信号。
#
# ⚠️ 两类的**处置动作不同**，故分开（#199 已实证"改注册脚本源码 ≠ 改了在跑
# 的任务"）：入口类改完下次触发即生效；注册脚本类必须重跑该脚本才生效，对它
# 印"同步并重启"等于给出一个做了也没用的处置——比不发更糟。
RESIDENT_SERVICE_ENTRYPOINT_GLOBS = ("run-*.vbs",)
RESIDENT_SERVICE_REGISTRAR_GLOBS = ("register-*.ps1",)

# 命中来源标签 → 告警正文里的处置措辞。键同时用作日志/正文的"命中原因"。
RESIDENT_SERVICE_REMEDY_BY_SOURCE = {
    "部署清单": "同步 ops/wecom-service-home 后重启 ZhuopinAibotDevListener 才在生产生效",
    "平台底座": "同步 ops/wecom-service-home 后重启 ZhuopinAibotDevListener 才在生产生效",
    "执行入口": "同步 ops/wecom-service-home 后**下次触发即生效**（无需重跑注册脚本）",
    "任务注册脚本": "🔴 须**重跑该注册脚本**，仅同步重启不生效（#199）",
    "保守判定": "部署清单未解析出，已按命中保守判定——请人工确认是否需要同步重启",
}

# `-AppFiles @( ... )` 可跨行（FI2 那份即在续行符后），故 DOTALL 到右括号。
# `-LocalPlatformDir (Join-Path $REPO "5-平台底座\zhuopin_platform")`——脚本内
# 写作反斜杠，解析后须统一转正斜杠再与 touched_paths 比对。
# 🔴 本组正则一律用 r-string：`\z`/`\a`/`\f` 在普通字符串里的行为不一致，
# 其中 `\a`/`\f` 是**合法转义、不报错、静默变成控制字符**（同族教训见
# CLAUDE.md「heredoc 吃反斜杠」那条——真正咬人的是下游的静默转义）。
_APP_FILES_RE = re.compile(r"-AppFiles\s*@\((.*?)\)", re.DOTALL)
_LOCAL_PLATFORM_DIR_RE = re.compile(r"-LocalPlatformDir\s*\(\s*Join-Path\s+\$\w+\s+\"([^\"]+)\"")
_PS_DOUBLE_QUOTED_RE = re.compile(r"\"([^\"]+)\"")

# 队列 #236(2)：孤儿脏文件（不属于任何批次声明）状态持久化 + 告警阈值。
# 与 sweep 每小时一轮对齐，约 3 轮仍孤儿才点名，避免"批次登记与实际改动
# 之间几分钟时间差"这类偶发情形被误报（#147 gap_alert 的"狼来了"教训）。
ORPHAN_STATE_REL = "reports/sweep-orphan-state.json"
ORPHAN_ALERT_THRESHOLD_HOURS = 3

# 队列 #229：发布收口第②关——已部署场景白名单（初版宁窄勿宽）。
# key＝场景目录前缀，value＝该场景的部署留痕文件——本批 touched_paths 命中
# 前缀下的其它文件、但未同时命中这个留痕文件，即视为"未见留痕"。命令中心
# （AI运营指挥中心）没有独立场景 CLAUDE.md，其部署历史落在仓库根 CLAUDE.md，
# 沿用同一判据（宁可因根 CLAUDE.md 被顺手一并改动而漏报，也不误报）。
DEPLOYED_SCENARIO_PREFIXES = {
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/":
        "4-数字员工/采购部/SC8-客户订单交期智能承诺/CLAUDE.md",
    "4-数字员工/质量部/QD-B-立项审核门禁/":
        "4-数字员工/质量部/QD-B-立项审核门禁/CLAUDE.md",
    "4-数字员工/财务部/FI2-三单匹配自动对账/":
        "4-数字员工/财务部/FI2-三单匹配自动对账/CLAUDE.md",
    "1-转型规划/AI运营指挥中心/": "CLAUDE.md",
}

# 队列 #298（2026-08-07 当日扩容）：M1 场景 spec 覆盖缺口检测的扫描域。
SCENARIO_ROOT_REL = "4-数字员工"
PLATFORM_PACKAGES_ROOT_REL = "5-平台底座"
OPENSPEC_SPECS_REL = "openspec/specs"
OPENSPEC_CHANGES_REL = "openspec/changes"
# 场景目录名短代码前缀：首个 `-` 前的字母数字段；兼容 `QD-A`/`QD-B` 这类
# 代码本身含连字符的写法（贪婪尝试再吞一段 `-字母数字`，仍要求其后紧跟
# `-` 才采信，见 `_scenario_short_code` 用例）。
SCENARIO_SHORT_CODE_RE = re.compile(r"^([A-Za-z0-9]+(?:-[A-Za-z0-9]+)?)-")
SCENARIO_RETIREMENT_MARKER = "退役"
SCENARIO_SPEC_GAP_STATE_REL = "reports/sweep-scenario-spec-gap-state.json"
SCENARIO_SPEC_GAP_ALERT_INTERVAL_HOURS = 24

# 队列 #298 M2：在途变更包滞留判据——完成率阈值与本行给出的两个真实
# 命中案例一致；天数阈值见文件头部本节说明（已更正原文"≥7天"与其自身
# 举例"fi2-recon-mvp 90%/3天"的矛盾）。
STALE_CHANGE_COMPLETION_THRESHOLD = 0.80
STALE_CHANGE_MIN_DAYS_IDLE = 3
STALE_CHANGE_DEFER_MARKER = "暂不归档"
STALE_CHANGE_STATE_REL = "reports/sweep-stale-change-state.json"
STALE_CHANGE_ALERT_INTERVAL_HOURS = 24
# 队列 #308 子项 D2：判断型告警的指纹确认状态（`--ack-stale-change`），
# 与上面的 STALE_CHANGE_DEFER_MARKER（文本标记，永久生效）是两套独立
# 机制，见 `cmd_ack_stale_change`/`_find_stale_in_flight_changes` 文档。
STALE_CHANGE_ACK_STATE_REL = "reports/sweep-stale-change-ack.json"
# 队列 #314②（2026-08-09，Shao Peishen 拍板 (c)）：告警在说谎——三个
# 高完成率变更包（`queue-status-machine-field`/`fi2-recon-mvp`/
# `wecom-aibot-channel`）不是被遗忘，是在等真实场景自然发生，报"疑似
# 遗忘归档"与事实不符。改法：变更包可在 proposal.md/design.md/tasks.md
# 任一处用本正则声明"预期观察窗口"（如"预期观察窗口：14 天"），与
# STALE_CHANGE_DEFER_MARKER 同一扫描范围/顺序，复用既有"文本标记声明"
# 惯例，不新造载体——这是刻意选择，非偷懒：判据本身不猜"是否仅剩被动
# 观察项"（那正是 #308 要根治的"关键词猜中文"家族），只认"是否声明了
# 窗口"这一显式信号，把"是不是观察项"的判断权交给声明方自己。窗口内
# 报"观察中"（不计异常，不进 `_track_and_alert_standing_state` 的
# 异常 key 集合）；超窗才升级为"疑似遗忘归档"（现有行为不变）；未声明
# 窗口的包维持现状（现有行为不变，向后兼容）。
OBSERVATION_WINDOW_RE = re.compile(r"预期观察窗口[:：]\s*(\d+(?:\.\d+)?)\s*天")

# ============================================================
# 队列 §一 #338 子项 A（2026-08-23，OP-0823-G）：必载 `CLAUDE.md` 尺寸／
# 批次跨度守卫 —— 第 4 类常驻状态告警
# ============================================================
# 共同命题（#338）：**必载载体的健康度此前没有任何机器守卫，全靠人事后
# 发现。** 实测（2026-08-16 memory 体系审核）：根 `CLAUDE.md` 08-09 瘦身
# 到 84,399 B 后 7 天回涨到 106,353 B（+26%），全程无人察觉。
#
# 🔴 **本守卫上线当天预计零告警**（2026-08-23 实测：根 56,002 B、场景最大
# 40,867 B，均在阈值内；顶部段只有一个批次日期）。而「零告警」正是这类
# 守卫最危险的状态 —— `OP-0819-F` 的第一句教训是「**一个告警机制建成 9 天、
# 每天在跑，却从来没有真正发出过一条消息**」。故本守卫**每轮必须回显
# 「当前值/阈值/差额」，零超限时也不省略**：那行日志是它每天唯一的存在
# 证明，不是调试输出。
#
# 阈值为 2026-08-16 定的经验值，**首月只告警、不调参**（守 #257 先攒样本
# 纪律）；实现方不得自行调参（#338 预授权①）。
CLAUDE_MD_ROOT_REL = "CLAUDE.md"
CLAUDE_MD_SCENE_GLOBS = ("4-数字员工/*/*/CLAUDE.md", "5-平台底座/*/CLAUDE.md")
CLAUDE_MD_ROOT_BYTE_CAP = 90 * 1024      # 92,160
CLAUDE_MD_SCENE_BYTE_CAP = 50 * 1024     # 51,200
CLAUDE_MD_SIZE_STATE_REL = "reports/sweep-claude-md-size-state.json"
CLAUDE_MD_SIZE_ALERT_INTERVAL_HOURS = 24
# 顶部段解析**委托** lint 那份唯一权威实现，本文件不另写正则：同一个
# 「顶部段条目」判据，lint 自己的模块注释记着裸正则数出 4 条、区间判据
# 数出 2 条，而错的那个「看起来很确定」。再写第二套 = 再造一次同样的
# 漂移，且两套的分歧不会有任何报错。
CLAUDE_PROGRESS_LINT_REL = "0-学习与工具/工具-CLAUDE进度段lint.py"

# ============================================================
# 队列 §一 #338 子项 B（2026-08-23，OP-0823-G）：常驻执行体落后守卫 ——
# 第 5 类常驻状态告警
# ============================================================
# 🔴 **为什么既有的 `_announce_resident_service_deployment_hint` 挡不住这
# 件事**（2026-08-23 实测，数字是本守卫存在的全部理由）：
#   git rev-list --count 33c5d18..master                     → 305
#   同上 -- 5-平台底座/wecom-aibot-service zhuopin_platform   →   6
# **305 个提交里只有 6 个触碰常驻服务运行体** ⇒ 那条事件型提示在四天里
# 最多响过 6 次，**另外 299 个提交零信号**（其中 161 个触碰队列文件，正是
# 这三个任务每天读的东西）。
#
# ⇒ 两条结论：**⑴ 事件型提示无法承担常驻状态的职责** —— 六句各自都对的
# 「你该同步了」，加起来也不会变成一句「你现在欠了 305」；**⑵ 判据的覆盖
# 面错了** —— 执行体是整个仓库的一份 checkout，它落后与否跟本批碰了哪个
# 目录无关。故本守卫直接量这份 checkout 落后多少，与批次内容无关。
#
# 两者并存、互不取代（proposal 已论证）：事件型回答「这一批改动需不需要
# 部署」，本守卫回答「此刻执行体欠了多少没对齐」。**本次不改动既有那条。**
RESIDENT_CARRIER_LAG_STATE_REL = "reports/sweep-carrier-lag-state.json"
RESIDENT_CARRIER_LAG_ALERT_INTERVAL_HOURS = 24
WORKTREES_DIR_REL = ".claude/worktrees"
# 🔴🔴 **解法改版（Shao Peishen 2026-08-23 补进 #338 行首，优先级高于原派单
# 说明）：④ 必须是「持续同步」，不是「检测＋提醒＋人工对齐」。**
#
# 被推翻的是本文件作者当天给出的 (c) 档建议。推翻的理由一句话：
# **检测＋提醒只是把触发人从「自己想起来」换成「被机器提醒」，对齐本身
# 仍是一次性动作** ⇒ `#68` 的历史会原样重演——08-19 五项验收全过、四天后
# 落后 305。**根因是「落后是持续过程，约 70 提交/天」，一次性动作治不了
# 持续过程，无论触发人是谁。**
#
# ⇒ **分两级，因为 ff 与重启的风险完全不同**：
#   ① **ff 每轮做** —— sweep 每小时已在 `_reconcile_with_origin_and_push`
#      对齐 master，顺带把执行体 worktree 一并 `--ff-only` 对齐是同类低风险
#      操作。
#   ② **重启按需、不随 ff 每轮做** —— 只在本轮 ff **真的动了常驻服务代码
#      路径**时才重启验活，判据**复用 `#87` ⑶⑷ 那套白名单
#      （`_touches_resident_service`），刻意不另写一套**。
#
# 🔴 由此消掉了一个数：原方案里的「落后 ≥100 才告警」阈值**整条作废**。
# 自动 ff 之后落后恒为 0，「落后多少算该管」这个问题不再需要一个阈值来
# 回答——**这是本次改版的一个附带收益：一个没人写下来过的经验值，被一个
# 结构性做法取消了，而不是被另一个经验值取代。**
#
# 告警的语义随之从「落后了」改为**「有例外」**：ahead>0 停手／ff 失败／
# 已 ff 但需重启而自动重启关着。三者都是**人必须介入**的状态。

# ⑵ 重启是有风险动作，**须可一键关闭**（#338 边界⑵）。缺省 **OFF**：
# 首月只 ff、重启仍走人工确认，攒够样本再放开（同 #257 先攒样本纪律）。
# 🔴 **读不到即视为 OFF**（fail-safe）：一个「重启生产服务」的开关，
# 在配置缺失时必须是关的——这与 `_load_webhook_url` 取不到就跳过推送是
# 同一条取舍，只是代价更高。
CARRIER_AUTO_RESTART_ENV_KEY = "CARRIER_AUTO_RESTART_ENABLED"
CARRIER_AUTO_RESTART_TRUE_VALUES = ("1", "true", "yes", "on")
RESIDENT_CARRIER_REALIGN_SCRIPT_REL = "0-学习与工具/工具-执行体对齐重启.ps1"
# 执行体名单**从计划任务反查**（Shao Peishen 2026-08-23 拍板 (a)），不硬
# 编码、不靠仓库内白名单：新增一个指向 worktree 的常驻任务须被自动纳入，
# 白名单本身就是一个新的人守点，而本包的立意是减少人守点。
# ⚠️ 这不推翻 `RESIDENT_SERVICE_*` 那组常量注释里「计划任务的真实设置不在
# 仓库里」（#199）那句：那组服务于「本批路径是否命中服务目录」这个**静态**
# 判据，本组是**运行时反查**，两者并存，本次不改那组。
_SCHEDULED_TASK_QUERY_PS = (
    "$ErrorActionPreference='Stop'; "
    "Get-ScheduledTask | ForEach-Object { $t = $_.TaskName; foreach ($a in $_.Actions) { "
    "[pscustomobject]@{ Task = $t; Execute = [string]$a.Execute; "
    "Arguments = [string]$a.Arguments } } } | ConvertTo-Json -Compress -Depth 3"
)


# 队列 #302：批量派活前状态核对——近期 commit 扫描窗口默认天数。
STALE_ROW_LOOKBACK_DAYS = 14
# 副判据在高频改动的文件（如本脚本自身）上天然命中大量 commit——真实
# 验证实测某些行触碰区含 `工具-落库sweep.py` 时单行可命中 300+ 个 commit
# sha，全量列出会让输出不可读。只截断"展示"的 sha 数量，不改变
# `primary`/`secondary` 判定本身（判定仍是"是否非空"这一布尔结果）。
STALE_ROW_MAX_DISPLAYED_COMMITS = 5
SECTION_ONE_HEADING = "## 一、"
COMMIT_TYPE_PREFIX_RE = re.compile(r"^[A-Za-z]+\(")
ROW_NUMBER_RE = re.compile(r"#(\d+)")


class SweepAbort(Exception):
    """安全门未过或运行中出现需要人工介入的异常，携带退出码与提示。

    `is_fork`（队列 #171）：仅起跑前置分叉检测这一处会置 True——main() 据此
    触发主动告警（`_handle_fork_detected`），与其余"健康跳过"（非 master/
    非 clean/无待处理批次等，退出码仍为 0、不告警）区分开。
    """

    def __init__(self, message: str, exit_code: int = 0, is_fork: bool = False):
        super().__init__(message)
        self.exit_code = exit_code
        self.is_fork = is_fork


def _run_git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    # -c core.quotepath=false：不加此项时 git 会把中文路径转成八进制转义的带引号
    # 字符串（如 "1-\350\275\254..."），本项目路径几乎全是中文，不关掉这个
    # 会让 status/show/diff 的路径解析全部失真。生产仓库大概率已在全局配置里
    # 关闭过（未观察到该现象），但脚本自身不应依赖这一假设——每次调用显式带上。
    return subprocess.run(
        ["git", "-c", "core.quotepath=false", *args], cwd=cwd, capture_output=True,
        text=True, encoding="utf-8", check=check,
    )


def _resolve_repo_root(override: str | None) -> Path:
    if override is not None:
        return Path(override).resolve()
    return MAIN_WORKSPACE


def _assert_not_a_linked_worktree(repo_root: Path) -> None:
    """`.git` 是文件夹=主工作区；是文件（指向别处 gitdir）=linked worktree。

    要求④"勿指建造 worktree"——即便计划任务配置写错指到了某个
    `.claude/worktrees/<name>`，运行时也应在此处硬失败，而不是悄悄在一次性
    建造分支上做出提交（该分支任务完工后可能被 `git worktree remove` 连同
    未推送的提交一起丢弃，参见协议〇.5 收工自删 worktree）。
    """
    git_path = repo_root / ".git"
    if not git_path.is_dir():
        raise SweepAbort(
            f"✗ {repo_root} 的 .git 不是目录（可能是 linked worktree 或非仓库路径）——"
            "sweep 只允许在主工作区运行，本轮不做任何改动。",
            exit_code=1,
        )


def _heal_stale_index_lock(repo_root: Path, log: list[str]) -> None:
    """起跑前自愈陈旧的 `.git/index.lock`（#121(b) 根因排查产出）。

    背景：`.git/index.lock` 残留期间，本脚本后续任何 `_run_git`（默认
    check=True）调用都会抛未捕获的 CalledProcessError——它不是 SweepAbort，
    main() 的 `except SweepAbort` 接不住，_flush_log 也就没机会写盘。这正是
    #121(b) 实测到的现象："LastTaskResult=1 但 sweep-commit.log 无任何新行"
    （11:37/11:39 两次手动触发疑似与短时间内重复触发/index.lock 残留有关）。

    只清"陈旧"（mtime 超过 STALE_INDEX_LOCK_MINUTES 分钟）的锁；新鲜的锁大概率
    对应正在跑的真实 git 进程（含本脚本另一实例的并发触发），不抢占、不误杀，
    改为优雅跳过本轮并把原因写进日志——把"未捕获异常静默失败"变成"有记录的
    安全跳过"，即便暂时不清锁，这本身也修复了 #121(b) 的核心症状（日志无新行）。
    """
    lock_file = repo_root / ".git" / "index.lock"
    if not lock_file.exists():
        return
    age_minutes = (time.time() - lock_file.stat().st_mtime) / 60
    if age_minutes < STALE_INDEX_LOCK_MINUTES:
        raise SweepAbort(
            f"⚠ 检测到新鲜的 .git/index.lock（{age_minutes:.1f} 分钟前，"
            f"<{STALE_INDEX_LOCK_MINUTES} 分钟视为可能仍在运行的真实 git 进程）——"
            "跳过本轮，不抢占，等其自然结束或下一轮重试。",
        )
    lock_file.unlink()
    log.append(
        f"⚠ 已自愈陈旧 .git/index.lock（{age_minutes:.1f} 分钟前遗留，"
        "判定为异常退出残留，已清除）。"
    )


def _check_preconditions(repo_root: Path, production: bool) -> None:
    if production and repo_root != MAIN_WORKSPACE:
        raise SweepAbort(
            f"✗ repo_root={repo_root} 与约定的主工作区路径 {MAIN_WORKSPACE} 不符——"
            "拒绝运行（防止计划任务配置误指到 worktree）。",
            exit_code=1,
        )
    _assert_not_a_linked_worktree(repo_root)

    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root).stdout.strip()
    if branch != "master":
        raise SweepAbort(f"⚠ 主工作区当前分支是「{branch}」非 master——跳过本轮，不强切分支。")

    for marker in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "rebase-merge", "rebase-apply"):
        if (repo_root / ".git" / marker).exists():
            raise SweepAbort(f"⚠ 检测到未完成的 git 操作（{marker} 存在）——跳过本轮，不强行处理。")

    status = _run_git(["status", "--porcelain=v1"], repo_root).stdout
    if any(line[:2].strip().upper() == "U" or line[:2] in ("AA", "DD") for line in status.splitlines()):
        raise SweepAbort("⚠ git status 显示存在未合并冲突路径——跳过本轮，不强行处理。")


def _fetch(repo_root: Path, log: list[str], phase: str) -> bool:
    """队列 #328（2026-08-17）：本函数**不再中止整轮**，失败只记录并返回 False，
    由调用方按起跑段通则自行判定后续。

    退休说明（协议〇.9 措施 B 的 one-in-one-out，本变更包的"一出"）：本函数
    原有唯一职责就是"fetch 失败即 `SweepAbort` 整轮跳过"，是全文件唯一一处
    网络类守卫。实测 `reports/sweep-commit.log` 全量 715 轮：**起跑段那次
    fetch 失败致整轮跳过 20 轮（2.8%），分布 11 个不同日期**（收尾段另有 3
    轮，2 个日期）——而本轮真正需要网络的只有收尾段的 push，起跑段挡掉的
    批次落库/台账重跑/flush 暂存/孤儿告警/openspec 检测**没有一项依赖网络**；
    其中 3 轮的批次在紧邻下一轮立刻落库，即被白推迟一个完整周期。

    ⚠️ 统计口径提醒（原队列行记的"16 轮/567/10 个日期"混淆了两个调用点）：
    起跑段 fetch 排在 `_flush_pending_lock_appends` **之前**，故其命中的日志块
    内**不含**"pending 锁忙暂存 flush"与"§二…"行；收尾段命中块必含。按字面
    grep "fetch 失败"统计会把两处合计，据此判断"要改几处"会漏掉收尾段。

    `phase` 只用于日志措辞（"起跑段"/"收尾段"），使日志能直接分辨是哪一处
    失败，不必再靠上下文行反推。
    """
    result = _run_git(["fetch", "origin", "master", "--quiet"], repo_root, check=False)
    if result.returncode != 0:
        log.append(
            f"⚠ {phase} git fetch origin master 失败（{result.stderr.strip()}）"
            "——不中止本轮，按起跑段通则记录后继续。"
        )
        return False
    return True


def _push_any_unpushed_commits(repo_root: Path, log: list[str], dry_run: bool = False) -> None:
    """队列 #194：起跑段无条件检查是否存在未推送的本地提交，不绑定"§二
    有无待处理批次"（正是这个绑定让 07-31/08-01 多次真实复现"本地已提交、
    下一轮判定'无待处理批次'直接空转，提交就此滞留"）。

    覆盖"任何一处 push 失败后的未推送提交"——已实证至少两个独立出口
    （批次主流程与 `_rerun_ledger` 台账重跑），本函数在起跑段统一兜底，
    不依赖具体是哪个出口造成的滞留。

    存在且可快进即先补推（推成功再继续本轮其余流程）；补推本身失败
    （网络/鉴权等）以 exit_code=2（人工介入语义）收尾——本地提交不会被
    撤销。

    队列 #309 子项 F（2026-08-08）：不可快进（已分叉）时**不再** `SweepAbort`
    整轮中止——旧实现在此处直接退出，排在其后的批次处理（§二待 commit）与
    收尾段 `_reconcile_with_origin_and_push`（#288 新增、自带 rebase 能力）
    整轮走不到，与 #288 当初治的"`_sync_master_if_behind_origin` 排在批次
    处理之前、前置守卫挡住后置修复"完全同构复发（2026-08-08 02:35 UTC 起
    连续 4 轮整轮跳过实测坐实）。改为记录 + 降级：本轮继续处理待落库批次，
    分叉对齐统一交给收尾段 `_reconcile_with_origin_and_push` 处理——它会在
    批次全部本地提交、工作区恢复干净后重新 fetch 一次最新状态，按彼时的
    ahead/behind 关系自动 `git rebase origin/master`；绝大多数不冲突的
    并发编辑（同 #288 观察）可自动对齐并推送成功，只有真实内容冲突才会
    落回既有的 `git rebase --abort` + 分叉告警路径（`is_fork=True`／
    `FORK_EXIT_CODE`），与此前语义一致，只是判定时机从"起跑段一律拦"
    收窄为"收尾段确认真无法自动解决才拦"。

    队列 #328（2026-08-17）：本函数**任何路径都不再中止整轮**，补齐 #309 子项 F
    只修了自己撞见的那一处所留下的两个缺口——

    ⑴ `_fetch` 失败：记录后直接返回，**跳过 ahead 计算与推送**。刻意不"用可能
       陈旧的 origin/master 引用凑合算一下"——那会得出一个基于过期引用的
       ahead，据此推送属于拿旧判据做写动作（同"工具静默回退"家族：返回值正常
       但读的不是我以为的那个对象）。补推交收尾段，它会重新 fetch 到最新状态。

    ⑵ 补推自身失败（原 `SweepAbort(exit_code=2)`）：记录后继续。它与 ⑴ 同因
       （网络/鉴权），同样不影响本轮任何本地工作；本地提交本就不会被撤销，
       推送交收尾段重试，**收尾段推送失败仍以 `exit_code=2` 收尾，对外语义不丢**，
       只是判定时机后移——与 #309-F 当初"起跑段一律拦 → 收尾段确认真不行才拦"
       的收窄完全同构。
       📌 这一处**不在 #328 派单件的字面范围内**，是按本包新立的起跑段通则
       逐位点扫描时发现的"第四例"（九个位点判定表见变更包 design §2），
       即通则存在的意义所在——它不在任何人"撞见"的路径上。"""
    if not _fetch(repo_root, log, "起跑段"):
        log.append("⚠ 起跑段未能刷新 origin/master，本轮跳过补推判断（不依据陈旧引用推送），"
                   "未推送提交交收尾段重试。")
        return
    ahead_raw = _run_git(["rev-list", "--count", "origin/master..HEAD"], repo_root).stdout.strip()
    ahead = int(ahead_raw) if ahead_raw.isdigit() else 0
    if ahead == 0:
        return
    check = _run_git(["merge-base", "--is-ancestor", "origin/master", "HEAD"], repo_root, check=False)
    if check.returncode != 0:
        log.append(
            f"⚠ 起跑发现 {ahead} 个未推送的本地提交，且推送非快进"
            "（origin/master 不是当前 HEAD 的祖先，已分叉）——本轮不在此处提前中止，"
            "继续处理待落库批次；分叉对齐交给收尾段 `_reconcile_with_origin_and_push` "
            "统一处理（自带 rebase 能力，真无法自动解决时才走既有分叉告警路径）。"
        )
        return
    if dry_run:
        log.append(f"[dry-run] 起跑将补推 {ahead} 个此前未推送的本地提交（本次不实际 push）。")
        return
    push = _run_git(["push", "origin", "HEAD:refs/heads/master"], repo_root, check=False)
    if push.returncode != 0:
        # 队列 #328：原为 SweepAbort(exit_code=2) 整轮中止，见本函数 docstring ⑵。
        log.append(
            f"⚠ 起跑发现 {ahead} 个未推送的本地提交，补推失败（{push.stderr.strip()}）"
            "——不中止本轮，本地提交完整保留、不会被撤销，推送交收尾段重试；"
            "收尾段仍失败时以既有『需人工核查』语义与退出码收尾。"
        )
        return
    log.append(f"✓ 起跑补推 {ahead} 个此前未推送的本地提交。")


def _reconcile_with_origin_and_push(repo_root: Path, log: list[str], dry_run: bool = False) -> None:
    """队列 #288（openspec 变更包 `sweep-ff-sync-batch-reorder`，2026-08-06）：
    批次已在本地提交、工作区已干净之后，统一对齐 `origin/master` 并推送
    一次——取代原先排在批次处理**之前**的 `_sync_master_if_behind_origin`
    （只会 ff-only、且要求工作区干净这一隐含前提恰恰与"§二 待 commit 批次
    必然导致工作区脏"这一 sweep 自身的设计假设冲突，是本次故障的根因，
    见文件头部本节说明）。

    调用时机：main() 在批次提交 + 遗留尾巴提交 + 台账重跑提交全部完成之后
    才调用本函数一次——此时工作区里"已被批次声明的脏改动"均已转为本地
    提交，只可能残留 #238 判定为孤儿/歧义、本函数不该也不会去动的脏文件。

    fetch 一次后按本地 HEAD 与 origin/master 的关系分派：
    - 相等：无事可做。
    - 纯落后（HEAD 是 origin/master 祖先）：`git merge --ff-only` 追上；
      工作区仍有未声明的脏文件挡住合并时，按既有语义告警跳过（不强推、
      不 rebase），退出码沿用健康跳过语义（0），不当作分叉处理。
    - 纯领先（origin/master 是 HEAD 祖先，即本轮只有本地新提交、origin
      未变）：跳过合并，直接推送。
    - 已分叉（互不为对方祖先——本轮批次提交后本地必然领先，origin 若同期
      也有新提交即构成分叉）：`git rebase origin/master`；rebase 冲突时
      `git rebase --abort` 回滚到批次已提交的干净状态（本地提交不丢），
      复用既有 #171 分叉告警（`is_fork=True`／`FORK_EXIT_CODE`／webhook／
      连续轮次持久化），不自动解冲突、不强推。

    对齐成功（含"无事可做"）后如需推送，统一执行一次 `git push`；推送本身
    失败（非分叉，如网络/权限）以 exit_code=2（既有"本地提交不会被撤销，
    需人工核查"语义）收尾。对齐/推送成功时清空任何陈旧的分叉连续计数
    （`_reset_fork_state`）——即便本轮压根没有分叉过，调用也是幂等的。
    """
    if dry_run:
        log.append("[dry-run] 将 fetch 并按需 ff-only 合并/rebase，随后统一 push 一次（本次不实际执行）。")
        return

    # 队列 #328（2026-08-17）：收尾段 fetch 失败同样不再中止整轮。此前由
    # `_fetch` 抛 SweepAbort 统一处理，其副作用是**连带跳过其后一批纯本地
    # 检测**——#198(c) 常驻服务部署提示、#229 部署留痕检查、#298 openspec
    # 覆盖与滞留检测，这三者只读本地仓库、不依赖网络，属同一个错误的第四
    # 个表现面（实测 3 轮命中，2 个日期）。退出码维持 0，与此前 `_fetch` 抛出的
    # SweepAbort 默认退出码一致，对外语义不变。
    if not _fetch(repo_root, log, "收尾段"):
        ahead_probe = _run_git(
            ["rev-list", "--count", "origin/master..HEAD"], repo_root, check=False)
        if ahead_probe.returncode == 0 and ahead_probe.stdout.strip().isdigit():
            pending = int(ahead_probe.stdout.strip())
            detail = (f"，本轮有 {pending} 个本地提交未能推送、将由下一轮重试"
                      if pending else "，本轮无未推送的本地提交")
        else:
            # 不猜：origin/master 引用本身读不到时如实说读不到，不填 0
            # （填 0 会让"没东西要推"和"不知道有没有东西要推"在日志上同形）。
            detail = "，且 origin/master 引用不可读、未推送提交数不可知"
        log.append(
            f"⚠ 收尾段跳过与 origin/master 的对齐与推送{detail}；"
            "本地提交完整保留，其余本地检测照常执行。"
        )
        return

    head = _run_git(["rev-parse", "HEAD"], repo_root).stdout.strip()
    origin_head = _run_git(["rev-parse", "origin/master"], repo_root).stdout.strip()
    if head == origin_head:
        _reset_fork_state(repo_root, log)
        return

    ahead_raw = _run_git(["rev-list", "--count", "origin/master..HEAD"], repo_root).stdout.strip()
    behind_raw = _run_git(["rev-list", "--count", "HEAD..origin/master"], repo_root).stdout.strip()
    ahead = int(ahead_raw) if ahead_raw.isdigit() else 0
    behind = int(behind_raw) if behind_raw.isdigit() else 0

    if ahead == 0 and behind > 0:
        merge = _run_git(["merge", "--ff-only", "origin/master"], repo_root, check=False)
        if merge.returncode != 0:
            raise SweepAbort(
                f"⚠ 本地 master 落后 origin/master 但 --ff-only 合并失败"
                f"（{merge.stderr.strip()}）——跳过本轮，不强推、不 rebase。",
            )
        log.append(f"✓ 本地 master 落后 origin/master，已 git merge --ff-only 同步至 {origin_head[:7]}。")
        _reset_fork_state(repo_root, log)
        return

    if ahead > 0 and behind > 0:
        rebase = _run_git(["rebase", "origin/master"], repo_root, check=False)
        if rebase.returncode != 0:
            _run_git(["rebase", "--abort"], repo_root, check=False)
            raise SweepAbort(
                f"⚠ 本轮批次已本地提交，但与 origin/master 分叉且自动 rebase 失败"
                f"（{rebase.stderr.strip()}）——已 git rebase --abort 回滚，本地提交完整保留、"
                "不丢失、不强推，需人工介入手动 rebase。",
                exit_code=FORK_EXIT_CODE,
                is_fork=True,
            )
        log.append(f"✓ 本轮批次提交后与 origin/master 分叉，已 git rebase 自动对齐至 {origin_head[:7]}。")

    push = _run_git(["push", "origin", "HEAD:refs/heads/master"], repo_root, check=False)
    if push.returncode != 0:
        raise SweepAbort(
            f"✗ 本轮已提交但推送失败：{push.stderr.strip()}——"
            "本地提交不会被撤销，需人工核查后手动 push，本轮就此停止。",
            exit_code=2,
        )
    log.append("✓ 本轮全部提交已统一推送。")
    _reset_fork_state(repo_root, log)


def _flush_pending_lock_appends(repo_root: Path, log: list[str]) -> None:
    """队列 #192-A（主载体，每小时）：flush `pending_queue_lock_appends.jsonl`
    ——机器人因编辑锁占用被推迟的补录，此前只能"等下一条消息到达"才会
    重试，07-31 真实一例滞留 4 小时 2 分。

    走子进程调用独立脚本（见 `FLUSH_PENDING_LOCK_SCRIPT_REL`），不在 sweep
    自身进程内 `import aibot_service`/`zhuopin_platform`——本脚本刻意零
    依赖（见文件头部注释），多 worktree 共享全局 editable install 存在被
    静默劫持到别的 checkout 的风险，子进程隔离规避这一风险，也天然满足
    "flush 异常不得影响 sweep 主流程"（子进程崩溃不会传染到 sweep 自身）。

    必须在 sweep 自己取编辑锁的窗口之外调用——flush 内部会走一遍完整的
    `queue_git_sync.sync_after_archive`，同样要 acquire 编辑锁，若与
    `_strike_off_rows` 的持锁窗口重叠会构成重入；本函数固定排在批次处理
    之前调用（main() 接线顺序），不与之重叠。"""
    script = repo_root / FLUSH_PENDING_LOCK_SCRIPT_REL
    if not script.exists():
        return  # 本 checkout 未部署机器人服务（如独立测试环境），静默跳过
    result = subprocess.run(
        [sys.executable, str(script)], cwd=repo_root, capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode != 0:
        log.append(
            "⚠ pending_queue_lock_appends.jsonl flush 失败（不影响本轮批次处理）："
            f"{(result.stderr or result.stdout).strip()[:500]}"
        )
        return
    if result.stdout.strip():
        log.append(f"✓ pending 锁忙暂存 flush：{result.stdout.strip()}")


def _run_decision_reminder_second_carrier(repo_root: Path, log: list[str]) -> None:
    """队列 #219：决策提醒第二载体（每小时，随 sweep 一并触发）。

    背景：`ZhuopinDecisionReminderDaily` 是唯一载体——每日仅一次、需
    `LogonType=Interactive`（要求已登录）、错过不补（`NumberOfMissedRuns`
    不会自动补跑）、失败无任何告警。2026-08-03 真实丢了一轮（机器在 08:30
    触发窗口处于休眠恢复中），直到环境保障线手工核查才发现。判定逻辑本身
    （`decision_reminder.py::evaluate_candidates`）已用 `ESCALATION_INTERVALS_
    DAYS` 去重，双载体同一天各调一次不会重复打扰，故可安全复用、不改判据。

    走独立子进程调用 `scripts/decision_reminder_check.py`（与 #192-A
    `_flush_pending_lock_appends` 同一理由：本脚本刻意不 import
    `aibot_service`/`zhuopin_platform`，规避多 worktree 共享 editable
    install 被静默劫持到别的 checkout 的风险；async 事件循环边界因此完全
    留在子进程内，sweep 自身不需要 `asyncio.run()`——用进程隔离满足"async
    边界"这条实现约束，而非在 sweep 内直接 import 该异步函数）。

    **须在 sweep 自己的编辑锁窗口之外调用**（实现约束①）：被调脚本内部会
    走一遍 `queue_git_sync`/编辑锁 flush（同 #192-A 第二道载体），与
    `_strike_off_rows` 的持锁窗口重叠会构成重入；main() 接线固定排在批次
    处理开始之前调用，不与之重叠。

    路径解析走被调脚本自身的 `resolve_repo_root()`（#126）——本函数只按
    绝对路径 `repo_root / DECISION_REMINDER_SCRIPT_REL` 调用，不额外硬编码
    `SERVICE_DIR/reports` 之类的路径（实现约束④）。

    异常（含超时）必须捕获+记日志（标 UTC）后继续跑主流程，不得把 sweep
    带崩（实现约束③）。"""
    script = repo_root / DECISION_REMINDER_SCRIPT_REL
    if not script.exists():
        return  # 本 checkout 未部署机器人服务（如独立测试环境），静默跳过
    try:
        result = subprocess.run(
            [sys.executable, str(script)], cwd=repo_root, capture_output=True,
            text=True, encoding="utf-8", timeout=DECISION_REMINDER_TIMEOUT_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001 —— 第二载体失败不得影响 sweep 主流程
        log.append(
            f"⚠ 决策提醒第二载体调用异常（{_now_utc_str()}，不影响本轮批次处理）：{exc}"
        )
        return
    if result.returncode != 0:
        log.append(
            f"⚠ 决策提醒第二载体退出码 {result.returncode}（{_now_utc_str()}，不影响本轮批次处理）："
            f"{(result.stderr or result.stdout).strip()[:500]}"
        )
        return
    stdout = result.stdout.strip()
    if stdout and "无新增/超期决策项" not in stdout:
        log.append(f"✓ 决策提醒第二载体：{stdout.splitlines()[-1]}")


def _run_scheduled_task_mirror_sync(repo_root: Path, log: list[str]) -> None:
    """队列 #235/#188：定时任务真身↔镜像自动核对（每小时，随 sweep 一并触发）。

    走子进程调用 `工具-定时任务源码备份.py`（#169，规范化逐行比对+差异自动
    写回镜像，理由同 `_flush_pending_lock_appends`/`_run_decision_reminder_
    second_carrier`：多 worktree 共享全局 editable install 存在被静默劫持
    到别的 checkout 的风险，子进程隔离规避）。

    **与另外两个起跑段子进程不同：本次调用自身会写文件**（脚本检出真身与
    镜像不一致时直接把镜像内容改正）。若放任不管，这些改动会在下方
    `dirty_paths = _status_paths(...)` 捕获时变成"没人声明的孤儿脏文件"
    （同 #289 指出的"自动机制改了文件、没人负责让它落库"——本函数不能重蹈
    覆辙）。故仿照 `_rerun_ledger` 的做法：调用后检查镜像目录的 git 状态，
    有变化即就地 `git add`+本地 commit，不在此处单独推送，随本轮末尾的
    `_reconcile_with_origin_and_push` 一并对齐 origin 并推送——由此
    `dirty_paths` 捕获时这些文件已经是 clean 的，不产生新孤儿。

    检出真实差异（脚本报 `updated`）或命中凭据扫描拦截（脚本退出码 1，见其
    `credential_blocked` 状态）时，复用 #171 的 webhook 通道各发一次告警，
    满足 #188 原始诉求"不一致即告警"；无变化时静默，不产生 #147 式噪音。

    须在 sweep 自己的编辑锁窗口之外调用（main() 接线固定顺序，同
    #192-A/#219）；异常（含超时）必须捕获+记日志后继续跑主流程，不得把
    sweep 带崩。"""
    script = repo_root / SCHEDULED_TASK_BACKUP_SCRIPT_REL
    if not script.exists():
        return  # 本 checkout 未部署该脚本（如独立测试环境），静默跳过
    try:
        result = subprocess.run(
            [sys.executable, str(script)], cwd=repo_root, capture_output=True,
            text=True, encoding="utf-8", timeout=SCHEDULED_TASK_MIRROR_TIMEOUT_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001 —— 本检查失败不得影响 sweep 主流程
        log.append(f"⚠ 定时任务镜像核对调用异常（{_now_utc_str()}，不影响本轮批次处理）：{exc}")
        return

    stdout = result.stdout.strip()
    changed = _run_git(
        ["status", "--porcelain=v1", "--", SCHEDULED_TASK_MIRROR_DIR_REL], repo_root,
    ).stdout.strip()
    if changed:
        _run_git(["add", "--", SCHEDULED_TASK_MIRROR_DIR_REL], repo_root)
        _run_git(
            ["commit", "-m", "docs(定时任务镜像): sweep 自动核对并更正真身↔镜像差异"],
            repo_root,
        )
        log.append("✓ 定时任务真身↔镜像核对：检出差异并已自动更正+本地提交，等待本轮末尾统一对齐并推送。")
        webhook_url = _load_webhook_url(repo_root)
        if webhook_url is None:
            log.append(f"⚠ 未在 .env 找到 {WECOM_WEBHOOK_ENV_KEY}，跳过定时任务镜像差异告警推送（仅留痕日志）。")
        else:
            try:
                _send_wecom_markdown(
                    webhook_url,
                    f"🪞 定时任务真身↔镜像核对：检出并已自动更正差异\n{stdout[:800]}",
                )
                log.append("✓ 定时任务镜像差异告警已推送。")
            except Exception as send_exc:  # noqa: BLE001 —— 告警失败不应影响主流程
                log.append(f"⚠ 定时任务镜像差异告警推送失败（不影响本轮）：{send_exc}")

    if result.returncode != 0:
        log.append(
            f"⚠ 定时任务镜像核对退出码 {result.returncode}（疑似命中凭据扫描被拒绝写入，需人工核实）："
            f"{stdout[:500]}"
        )
        webhook_url = _load_webhook_url(repo_root)
        if webhook_url is None:
            log.append(f"⚠ 未在 .env 找到 {WECOM_WEBHOOK_ENV_KEY}，跳过凭据拦截告警推送（仅留痕日志）。")
        else:
            try:
                _send_wecom_markdown(
                    webhook_url,
                    f"🔴 定时任务真身↔镜像核对：命中凭据扫描，已拒绝写入镜像，需人工核实\n{stdout[:800]}",
                )
                log.append("✓ 凭据拦截告警已推送。")
            except Exception as send_exc:  # noqa: BLE001
                log.append(f"⚠ 凭据拦截告警推送失败（不影响本轮）：{send_exc}")


def _record_batch_landing_count(repo_root: Path, landed_batch_ids: list[str]) -> None:
    """队列 #257（P3，先计数不告警）：记录每轮 sweep 落库的批次数，供后续
    攒样本判断"该转场了"的定量阈值——现阶段样本量不足以定阈值，本函数只
    落数据，不做任何告警/阻断，不改变既有行为。"""
    if not landed_batch_ids:
        return
    log_path = repo_root / SESSION_BATCH_COUNT_LOG_REL
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts_utc": _now_utc_str(),
        "batch_count": len(landed_batch_ids),
        "batch_ids": landed_batch_ids,
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _load_webhook_url(repo_root: Path) -> str | None:
    """读 `<repo_root>/.env` 中 `WECOM_WEBHOOK_ENV_KEY` 常量所指的那个键（同
    `发企微.py::load_webhook` 同款零依赖读法，唯一区别：找不到时返回 None 而非
    sys.exit——告警发不出去不应让 sweep 本身失败退出，只应降级为"跳过告警、留痕"
    （见 `_handle_fork_detected`）。

    🔴 队列 #282 ⑴ 包：该常量指向运维逃生通道。取不到时返回 None，**绝不回退到
    业务部门群那个裸键**——回退命中即为发错群，而"发错群"正是本次切换要消灭的事
    （spec `sweep-alert-audience-routing`）。本 docstring 刻意只写常量名、不复制
    其值：docstring 不能是 f-string（那会使 `__doc__` 变 None），故用"命名常量"
    而非"派生"实现同一个目的——副本归零。
    """
    env_path = repo_root / ENV_REL
    if not env_path.exists():
        return None
    prefix = WECOM_WEBHOOK_ENV_KEY + "="
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(prefix):
            url = line[len(prefix):].strip().strip('"').strip("'")
            if url:
                return url
    return None


def _send_wecom_markdown(webhook_url: str, content: str) -> None:
    """向企业微信群机器人推送 Markdown 消息（同 `发企微.py::send_markdown`
    同款纯标准库实现，本脚本刻意不 import `zhuopin_platform`——保持零依赖，
    不受多 worktree 共享全局 editable install 指向哪个 checkout 的影响）。
    """
    payload = json.dumps(
        {"msgtype": "markdown", "markdown": {"content": content}}, ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        webhook_url, data=payload, headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if result.get("errcode", 0) != 0:
        raise RuntimeError(f"企业微信推送失败 errcode={result.get('errcode')} errmsg={result.get('errmsg')}")


def _read_fork_state(repo_root: Path) -> dict:
    path = repo_root / FORK_STATE_REL
    if not path.exists():
        return {"consecutive": 0, "first_detected_at": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"consecutive": 0, "first_detected_at": None}
    if not isinstance(data, dict) or "consecutive" not in data:
        return {"consecutive": 0, "first_detected_at": None}
    return data


def _write_fork_state(repo_root: Path, state: dict) -> None:
    path = repo_root / FORK_STATE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _reset_fork_state(repo_root: Path, log: list[str] | None = None) -> None:
    """分叉解除（前置检查转为通过）后清空连续计数——防止陈旧计数误导下一次
    真实分叉的"连续轮次"文案，也避免状态文件无限堆积历史分叉的旧数据。

    队列 #308 子项 D1：若重置前状态存在（即此前确实告警过至少一轮，
    `_handle_fork_detected` 每次检测到都会尝试发送），补发一条"✅ 分叉
    已解除"通知——治 2026-08-08 真实实证：分叉已解除但此前发出的告警
    消息无解除通道，读者只能凭空猜测是否仍成立。`log` 为 None（如既有
    调用点未传入）时静默跳过通知，只做原有的状态清空，向后兼容。
    """
    path = repo_root / FORK_STATE_REL
    was_alerted = path.exists()
    if path.exists():
        path.unlink()
    if not was_alerted or log is None:
        return
    log.append("✅ 分叉已解除")
    webhook_url = _load_webhook_url(repo_root)
    if webhook_url is None:
        log.append(f"⚠ 未在 .env 找到 {WECOM_WEBHOOK_ENV_KEY}，跳过分叉解除通知推送（仅留痕日志）。")
        return
    try:
        _send_wecom_markdown(webhook_url, "✅ 落库sweep：此前告警的主工作区与 origin/master 分叉已解除。")
        log.append("✓ 分叉解除通知已推送。")
    except Exception as exc:  # noqa: BLE001 —— 告警失败不应影响本轮退出码
        log.append(f"⚠ 分叉解除通知推送失败（不影响本轮退出码）：{exc}")


def _handle_fork_detected(repo_root: Path, log: list[str]) -> None:
    """分叉告警主流程（队列 #171）：更新连续轮次计数 + 尝试主动推送企微告警。
    告警发送失败（.env 缺失/网络异常/webhook 拒绝）只降级记日志，不向上抛出
    ——告警本身不应阻塞 sweep 正常返回其应有的（非 0）退出码。
    """
    state = _read_fork_state(repo_root)
    consecutive = int(state.get("consecutive") or 0) + 1
    first_detected_at = state.get("first_detected_at") or _now_utc_str()
    _write_fork_state(
        repo_root, {"consecutive": consecutive, "first_detected_at": first_detected_at},
    )

    local_head = _run_git(["rev-parse", "--short", "HEAD"], repo_root, check=False).stdout.strip() or "?"
    origin_head = _run_git(
        ["rev-parse", "--short", "origin/master"], repo_root, check=False,
    ).stdout.strip() or "?"

    if consecutive == 1:
        streak_note = f"首次检测到（{_now_utc_str()}）"
    else:
        streak_note = f"已连续第 {consecutive} 轮检测到（自 {first_detected_at} 起，仍未解除）"

    alert_text = (
        f"🔱 落库sweep 检测到主工作区与 origin/master 已分叉，{streak_note}。\n"
        f"本地 HEAD={local_head}，origin/master={origin_head}，均不是对方的祖先。\n"
        "需人工核实是否有并发提交冲突（如某次推送恰好落在本次 sweep 运行窗口内），"
        "不会自动强推/rebase，详见 reports/sweep-commit.log。"
    )
    log.append(f"🔱 分叉告警：{streak_note}（本地 {local_head} / origin {origin_head}）")

    webhook_url = _load_webhook_url(repo_root)
    if webhook_url is None:
        log.append(f"⚠ 未在 .env 找到 {WECOM_WEBHOOK_ENV_KEY}，跳过分叉告警推送（仅留痕日志与状态文件）。")
        return
    try:
        _send_wecom_markdown(webhook_url, alert_text)
    except Exception as exc:  # noqa: BLE001 —— 告警失败不应影响 sweep 自身退出码
        log.append(f"⚠ 分叉告警推送失败（不影响本轮退出码）：{exc}")
        return
    log.append(f"✓ 分叉告警已推送（连续第 {consecutive} 轮）。")


def _parse_resident_service_manifest(repo_root: Path) -> tuple[list[str], str, str | None]:
    """读常驻服务 `sync-to-server.ps1`，取 `-AppFiles` 清单与 `-LocalPlatformDir`。

    返回 `(app_files, platform_rel, parse_error)`。`parse_error` 非 None 即
    表示"清单没取到"，调用方必须**从低取值**（按命中处理），不得静默当作
    未命中——静默不报正是队列 §四 #87 ⑷ 那类漏报的成因，而漏报不产生任何
    信号、会一直漏下去。

    两条解析契约（实测得来，勿凭直觉简化）：
    ① **编码用 `utf-8-sig`**——6 份 sync 脚本 BOM 并不一致（实测 aibot 那份
       无 BOM、FI2 那份有 BOM），用 `utf-8` 读有 BOM 的那份会在首行多出
       `﻿` 而使正则错位；
    ② `-AppFiles` 的路径**相对 `-LocalAppDir`，而它恒等于 `$PSScriptRoot`**
       ⇒ 仓库相对路径 ＝ sync 脚本所在目录 + 条目。**不能认变量名**：SC8 那
       份用的是 `$SC8` 而非 `$APP`（认 `$PSScriptRoot` 这个语义、不认拼写）。
    """
    script = repo_root / RESIDENT_SERVICE_SYNC_SCRIPT_REL
    if not script.is_file():
        return [], RESIDENT_SERVICE_PLATFORM_FALLBACK_REL, f"未找到 {RESIDENT_SERVICE_SYNC_SCRIPT_REL}"
    try:
        text = script.read_text(encoding="utf-8-sig")
    except OSError as exc:  # noqa: BLE001 —— 读不到即从低取值，不吞成"未命中"
        return [], RESIDENT_SERVICE_PLATFORM_FALLBACK_REL, f"读取 sync 脚本失败：{exc}"

    platform_match = _LOCAL_PLATFORM_DIR_RE.search(text)
    platform_rel = (
        platform_match.group(1).replace("\\", "/").strip("/")
        if platform_match
        else RESIDENT_SERVICE_PLATFORM_FALLBACK_REL
    )

    app_files_match = _APP_FILES_RE.search(text)
    if app_files_match is None:
        return [], platform_rel, "sync 脚本内未解析出 -AppFiles 清单"
    entries = [
        e.replace("\\", "/").strip("/")
        for e in _PS_DOUBLE_QUOTED_RE.findall(app_files_match.group(1))
    ]
    entries = [e for e in entries if e]
    if not entries:
        return [], platform_rel, "-AppFiles 清单解析结果为空"
    return entries, platform_rel, None


def _resident_service_hit_source(
    path: str, repo_root: Path, app_files: list[str], platform_rel: str,
) -> str | None:
    """判定单条路径属于常驻服务运行体的哪个来源；不属于则返回 None。"""
    # ② 平台底座——常驻服务运行时导入它（队列 §四 #87 ⑷ 补的漏报面）。
    platform_prefix = f"{platform_rel}/"
    if path.startswith(platform_prefix):
        tail = path[len(platform_prefix):]
        if any(tail.startswith(sub) for sub in RESIDENT_SERVICE_PLATFORM_EXCLUDED_SUBDIRS):
            return None
        return "平台底座"

    service_prefix = f"{RESIDENT_SERVICE_DIR_REL}/"
    if not path.startswith(service_prefix):
        return None
    tail = path[len(service_prefix):]

    # ③ 计划任务的执行入口与注册脚本——限该服务目录**一层内**（`/` not in tail），
    # 两类处置动作不同，故分别标注。
    if "/" not in tail:
        if any(fnmatch.fnmatch(tail, g) for g in RESIDENT_SERVICE_ENTRYPOINT_GLOBS):
            return "执行入口"
        if any(fnmatch.fnmatch(tail, g) for g in RESIDENT_SERVICE_REGISTRAR_GLOBS):
            return "任务注册脚本"

    # ① `-AppFiles` 白名单：条目在仓库内是目录则前缀匹配、是文件则精确匹配
    # （`ZhuopinDeploy.psm1` 对目录走 `scp -r`、对文件走 `scp`）。取不到实体
    # （如本批正是删除该文件）时按精确匹配处理。
    for entry in app_files:
        entry_rel = f"{service_prefix}{entry}"
        if (repo_root / entry_rel).is_dir():
            if path.startswith(f"{entry_rel}/"):
                return "部署清单"
        elif path == entry_rel:
            return "部署清单"
    return None


def _touches_resident_service(
    paths: set[str], repo_root: Path,
) -> list[tuple[str, str]]:
    """队列 §四 #87 ⑶⑷：返回本批命中常驻服务运行体的 `(路径, 命中来源)`
    清单，按路径排序（保证告警正文可复现）；无命中返回空列表。

    🔴 由 `bool` 改为返回命中明细，是为了让告警正文能**回显命中了什么**——
    2026-08-22 那次误报之所以要靠人反查批次内容才发现，正是因为告警自己
    只印一句写死的话、不说命中原因，判据无法被现场证伪。
    """
    app_files, platform_rel, parse_error = _parse_resident_service_manifest(repo_root)
    hits: list[tuple[str, str]] = []
    for path in paths:
        if parse_error is not None and path.startswith(f"{RESIDENT_SERVICE_DIR_REL}/"):
            # 从低取值：清单没取到时，服务目录下任何路径一律按命中处理。
            hits.append((path, "保守判定"))
            continue
        source = _resident_service_hit_source(path, repo_root, app_files, platform_rel)
        if source is not None:
            hits.append((path, source))
    return sorted(hits)


def _announce_resident_service_deployment_hint(
    repo_root: Path, hits: list[tuple[str, str]], log: list[str],
) -> None:
    """队列 #198(c)（判据于 §四 #87 ⑶⑷ 重写）：本轮 commit 命中常驻服务
    运行体时，在日志与 webhook 附部署提示——纯提示、不阻断、不改变本轮
    退出码（sweep 无权也不该去重启服务）。成因＝"代码已提交但生产未生效"
    的失配长期全靠人记得（#126／#193 同族），本提示只负责把这件事说出来。

    正文**逐条回显命中路径与命中原因**，并按来源给出对应处置——入口类与
    任务注册脚本类的处置动作不同，不得一律印"同步并重启"。
    """
    log.append("⚠ 本批改动涉及常驻服务运行体，需部署后才在生产生效：")
    for path, source in hits:
        log.append(f"    - {path}（命中：{source}）⇒ {RESIDENT_SERVICE_REMEDY_BY_SOURCE[source]}")
    webhook_url = _load_webhook_url(repo_root)
    if webhook_url is None:
        log.append(f"⚠ 未在 .env 找到 {WECOM_WEBHOOK_ENV_KEY}，跳过部署提示推送（仅留痕日志）。")
        return
    body = "🔧 落库sweep：本批改动涉及常驻服务运行体，需部署后才在生产生效：\n" + "\n".join(
        f"- `{path}`（命中：{source}）\n  ⇒ {RESIDENT_SERVICE_REMEDY_BY_SOURCE[source]}"
        for path, source in hits
    )
    try:
        _send_wecom_markdown(webhook_url, body)
    except Exception as exc:  # noqa: BLE001 —— 提示推送失败不应影响本轮退出码
        log.append(f"⚠ 部署提示推送失败（不影响本轮退出码）：{exc}")
        return
    log.append("✓ 常驻服务部署提示已推送。")


def _status_paths(repo_root: Path) -> list[str]:
    """解析 `git status --porcelain=v1 --untracked-files=all` 为脏路径清单（重命名取新路径）。"""
    result = _run_git(["status", "--porcelain=v1", "--untracked-files=all"], repo_root)
    paths = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        rest = line[3:]
        if " -> " in rest:
            rest = rest.split(" -> ", 1)[1]
        paths.append(rest.strip('"'))
    return paths


def _parse_section_two(queue_text: str, queue_path: str) -> list[dict]:
    """解析队列 §二"待 commit 批次"表格，返回每行的原始文本+四列内容。

    队列 #314（openspec 变更包 `queue-table-backtick-aware-split`）：切列
    改为委托 `queue_table.split_row_cells`（反引号感知）——但本函数"行首
    行尾都必须是 `|`"这一行首行尾双检查**保持不变**，不随 #314① 对
    `工具-共享文档编辑锁.py::_table_data_rows` 的放宽而放宽：那是刻意的
    设计取舍（"命中不了整八列即静默跳过、不崩溃、不误判"，见 `_parse_
    section_one` 文档），sweep 需要在无人值守场景下绝不误判，与编辑锁
    "原样返回交调用方判"的既有策略是两种不同、都各自成立的取舍，本次
    只升级切列算法本身，不改变这一判断。

    队列 #315：每行附带 `queue_path`（本次解析的物理文件相对路径）——
    批次现分散在两份文件里，下游写回（`_strike_off_rows`/`_process_
    normal_batch`）需要知道该写去哪一份，不能再假设只有一份队列文件。
    """
    start = queue_text.find(SECTION_TWO_HEADING)
    if start == -1:
        return []
    rest = queue_text[start + len(SECTION_TWO_HEADING):]
    next_heading = rest.find("\n" + NEXT_SECTION_PREFIX)
    section = rest if next_heading == -1 else rest[:next_heading]

    rows = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = queue_table.split_row_cells(line)
        if len(cells) != queue_table.SECTION_COLUMN_COUNTS["二"]:
            continue
        if cells[0] in ("批次", ""):
            continue
        if set(cells[0]) <= {"-", " "}:
            continue  # 分隔行 |------|------|...|
        rows.append({
            "raw_line": line,
            "batch_id": cells[0],
            "files_cell": cells[1],
            "message_cell": cells[2],
            "status_cell": cells[3],
            "queue_path": queue_path,
        })
    return rows


# 队列 #248（2026-08-05）：判据锚定状态列"开头片段"——见 _leading_status_segment()。
# 前导字符剥离集合：半角 `*`（含单/双星号强调）、半角空格、制表符、全角空格
# （U+3000，中文输入法环境下的防御性收纳，现存行未实测命中但成本近零）。
LEADING_STRIP_CHARS = "* \t　"
# 界定"开头片段"边界的句级分隔符——现存生产队列文件里"。"996 次、"——"573 次、
# "━━━"199 次，是稳定且高频的句/段落分隔惯例，用其中最早出现的一个切开状态列，
# 分隔符之前的文本视为"当前生效结论"，之后的文本（多为补充说明/引用/复述）不参与判定。
LEADING_SEGMENT_SEPARATORS = ("。", "——", "━━━")


def _leading_status_segment(status_cell: str) -> str:
    """返回状态列去除前导强调符/空白后、第一个句级分隔符之前的"开头片段"。

    队列 #248 真实事故：sweep 把一条状态列开头是 `✅ 已完成`、但说明文字里
    引用了判据原文（含"待"字）的 §二 批次误判为待处理，取活提交、覆写了
    原说明（详见 openspec 变更包 `sweep-editlock-status-keyword-anchoring`）。

    **为什么边界不是"第一个字符"而是"第一个句级分隔符之前"**：现存回归测试
    （`ClassifySectionTwoRowsUnitTests::test_classifies_four_status_forms`）
    固化了一个 2026-07-27 实测事故的防御用例——登记方误写"✅ 已完成（本次
    登记，待 sweep 落库）"，"待"字紧跟在同一个不含任何句级分隔符的短括注
    里，若把"开头"收窄到"第一个字符"（即只看 `✅`），会让这条误写被判成
    "已完成"而漏处理，正是 2026-07-28 那次判据修法要根治的问题——等于用
    #248 的修法重新引入 2026-07-27 的旧事故。用句级分隔符（句号/破折号/
    分隔线）界定"开头片段"，既能保留这类短促、无分隔符的误写场景里"待"
    仍被检出，又能把 #248 那种"完成标记后另起一段引用/说明"的长文本排除
    在判定范围之外——已用现存生产队列文件全部 §二 行 + 本函数下方四个
    回归用例验证一致，见 openspec 变更包 design.md「历史兼容核对」。
    """
    stripped = status_cell.lstrip(LEADING_STRIP_CHARS)
    cut = len(stripped)
    for sep in LEADING_SEGMENT_SEPARATORS:
        idx = stripped.find(sep)
        if idx != -1:
            cut = min(cut, idx)
    return stripped[:cut]


# 队列 #308（2026-08-09，openspec 变更包 queue-status-machine-field，决策点
# 4）：§一 消费者切换——106 行存量已回填 `[S:...][D:...]` 机器字段，本文件
# 与 `工具-共享文档编辑锁.py` 各自独立实现一份解析（同 `_leading_status_
# segment` 既有的"跨文件不 import"惯例，避免多 worktree 共享 editable
# install 的静默劫持风险）。仅用于 §一；§二 的 `_classify_section_two_rows`
# 不在本次范围内，继续使用既有"待/✅"开头片段判据（design.md Non-Goals）。
STATUS_FIELD_RE = re.compile(
    r"^\[S:(done|open|partial|hold|blocked|timed=\d{4}-\d{2}-\d{2})\]"
    r"(?:\[D:(机|业)\])?"
)


def _parse_status_domain_fields(status_cell: str) -> tuple[str | None, str | None, str]:
    """解析 §一 状态列开头的机器字段，返回 (状态取值或 None, 域取值或
    None, 字段之后的自然语言正文)。缺失/非法时返回 (None, None, 原文)——
    调用方须走非静默降级（记录一条降级提示），不得静默回退旧判据而不
    留痕。"""
    stripped = status_cell.lstrip(LEADING_STRIP_CHARS)
    m = STATUS_FIELD_RE.match(stripped)
    if not m:
        return None, None, status_cell
    return m.group(1), m.group(2), stripped[m.end():]


def _classify_section_two_rows(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """按状态列"开头片段"把 §二 行分类为 (待处理, 模糊状态)（队列 #248 改判据
    锚定范围，2026-07-28 版判据见文件头部说明"批次判据显式化"一节）。

    显式判据（均只依据 `_leading_status_segment()` 返回的开头片段，不再对
    开头片段之后的文本做任何匹配）：
    - 开头片段含"待"字样 → 待处理，纳入本轮（不论是否同时误带"✅"——登记方
      按惯例应避免带✅，但即便带了也不能让批次因此石沉大海）。
    - 开头片段既不含"✅"也不含"待" → 模糊状态，不纳入本轮，但调用方必须把它
      写进日志（宁可吵不可哑），不能像"未命中待"一样被默默略过。
    - 开头片段只含"✅"、不含"待" → 视为已完成，两个返回列表都不包含，无需告警。
    """
    pending, ambiguous = [], []
    for r in rows:
        leading = _leading_status_segment(r["status_cell"])
        if "待" in leading:
            pending.append(r)
        elif "✅" not in leading:
            ambiguous.append(r)
    return pending, ambiguous


def _extract_commit_message(message_cell: str) -> str:
    match = re.search(r"`([^`]+)`", message_cell)
    return match.group(1) if match else message_cell.strip()


def _resolve_batch_files(files_cell: str, dirty_paths: list[str]) -> tuple[list[str], list[str], list[str]]:
    """把批次"文件清单"列里反引号标出的每个片段，对到 git status 里实际的脏路径。

    不去猜测"§二 表格里的路径默认省略 1-转型规划/ 前缀、写"根"才是仓库根相对"这类
    约定——直接拿片段去匹配当前真实脏路径的**后缀**（`dirty_path == frag` 或
    `dirty_path.endswith("/" + frag)`），天然兼容"根 CLAUDE.md"与省略前缀两种写法，
    且只会对到真实存在的脏文件,不会凭空造出一个不存在的 add 目标。

    队列 #234(1)（2026-08-04 值周巡检取证）：**精确相等优先**——若脏路径集合里
    存在与片段字面完全相等的路径，即唯一采用它，不再把同一轮里其它仅"后缀匹配"
    的候选一并计入歧义。根因实例：根 `CLAUDE.md` 与
    `4-数字员工/采购部/SC8-.../CLAUDE.md` 同时脏时，片段 `` `CLAUDE.md` ``
    在原实现下对根 `CLAUDE.md`（精确命中）与 SC8 那份（`endswith` 命中）各算一次，
    被判 ambiguous，进而使这个早已正确声明的批次被彼时的 `unaccounted` 全局
    门槛连带跳过——已声明齐全的批次不该因为"另一个 session 同时改了一个同名
    文件"而遭殃。本函数当时只做了这一处收窄，**按批次隔离**（结构性改动，
    #230-2d 评估结论）已于队列 #238 落地，见 `_partition_pending_rows_by_
    batch_isolation` 与 `main()`。

    返回 (resolved, not_dirty, ambiguous)：
      resolved   — 恰好命中 1 个脏路径的片段，对应的真实路径（用于 git add）
      not_dirty  — 0 个命中（可能已被别处提交，见"遗留尾巴"处置）
      ambiguous  — 命中 ≥2 个脏路径且无精确相等命中（无法安全判定，本片段对应的
                   候选路径会保留在全局脏路径集合里，从而让上层"非 clean"整体
                   门禁自然拦截，不需要在此单独报错）
    """
    fragments = re.findall(r"`([^`]+)`", files_cell)
    resolved, not_dirty, ambiguous = [], [], []
    for frag in fragments:
        exact = [d for d in dirty_paths if d == frag]
        if exact:
            resolved.append(exact[0])
            continue
        matches = [d for d in dirty_paths if d.endswith("/" + frag)]
        if len(matches) == 1:
            resolved.append(matches[0])
        elif len(matches) == 0:
            not_dirty.append(frag)
        else:
            ambiguous.append(frag)
    return resolved, not_dirty, ambiguous


def _explain_ambiguous_candidates(frag: str, dirty_paths: list[str]) -> list[str]:
    """返回某片段在当前脏路径中命中的全部候选（队列 #238 可解释日志）。

    与 `_resolve_batch_files` 内部同一套匹配规则（精确相等或按 "/" 前缀的
    后缀匹配），这里不做优先级取舍、原样列出候选，只为把"为什么判为歧义"
    说清楚——2026-08-03 本项目正因缺这行可解释日志而把一次正常判定误认成
    bug、白花一轮取证（见文件头部 #234 相关说明）。
    """
    return [d for d in dirty_paths if d == frag or d.endswith("/" + frag)]


def _check_dirty_paths_against_pending_batches(
    repo_root: Path, paths: list[str],
) -> list[tuple[str, str | None]]:
    """队列 #101①：只读核验——给定路径是否命中 §二 待处理批次的"文件清单"声明。

    供 `工具-主工作区安全同步.ps1` 在建议 `git checkout --` 弃改前先调用（走
    `--check-dirty-in-pending-batch` CLI 模式）：命中即不得建议丢弃，应改为
    提示触发 sweep 落库（协议〇.8"批次即扫＋checkout 前核对 §二"）。复用
    `_resolve_batch_files` 同一套匹配规则（精确相等优先，否则按 "/" 后缀），
    不另起一套判据，避免两处独立实现随时间漂移出不一致结论。

    返回 [(path, batch_id_or_None), ...]；batch_id 为 None 表示未命中任何
    待处理批次（可以放心按现有逻辑处理，不属于本检查的管辖范围）。

    队列 #315：批次分散在两份物理文件里，须都查——遗漏任一份会让本检查
    对该份文件里的待处理批次失明，复现"建议 checkout 前未核对 §二"这一
    本检查本来要防的事故。
    """
    pending_rows: list[dict] = []
    for queue_path in _iter_queue_paths():
        queue_text = _read_queue(repo_root, queue_path)
        rows = _parse_section_two(queue_text, queue_path)
        file_pending, _ = _classify_section_two_rows(rows)
        pending_rows.extend(file_pending)
    results: list[tuple[str, str | None]] = []
    for path in paths:
        matched_batch = None
        for row in pending_rows:
            resolved, _, _ = _resolve_batch_files(row["files_cell"], [path])
            if resolved:
                matched_batch = row["batch_id"]
                break
        results.append((path, matched_batch))
    return results


# ============================================================
# 队列 #302（2026-08-07）：批量派活前状态核对
# ============================================================


def _parse_section_one(queue_text: str) -> list[dict]:
    """解析队列 §一"任务看板"表格，返回每行的原始文本+八列内容。与
    `_parse_section_two` 同一套简单表格解析取舍——命中不了整八列即静默
    跳过该行，不崩溃、不误判；行首行尾双检查刻意保持不变，见
    `_parse_section_two` 文档（队列 #314，仅切列算法本身升级为反引号
    感知，不改变这一取舍）。"""
    start = queue_text.find(SECTION_ONE_HEADING)
    if start == -1:
        return []
    rest = queue_text[start + len(SECTION_ONE_HEADING):]
    next_heading = rest.find("\n" + NEXT_SECTION_PREFIX)
    section = rest if next_heading == -1 else rest[:next_heading]

    rows = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = queue_table.split_row_cells(line)
        if len(cells) != queue_table.SECTION_COLUMN_COUNTS["一"]:
            continue
        if cells[0] in ("#", ""):
            continue
        if set(cells[0]) <= {"-", " "}:
            continue  # 分隔行 |---|---|...|
        rows.append({
            "raw_line": line,
            "row_id": cells[0],
            "task_cell": cells[1],
            "owner_cell": cells[2],
            "input_cell": cells[3],
            "output_cell": cells[4],
            "status_cell": cells[5],
            "touch_zone_cell": cells[6],
            "registered_cell": cells[7],
        })
    return rows


def _extract_commit_scope(subject: str) -> str | None:
    """从 commit 首行提取 `type(scope):` 里的 scope 文本（队列 #302 主
    判据）。只认紧随消息开头的 `type(`（`COMMIT_TYPE_PREFIX_RE`），用
    `rfind` 而非贪婪/非贪婪正则定位冒号前最后一个右括号——兼容 scope 内
    自带嵌套括号的行号写法（如 `队列#236(1)`：字面按普通"找第一个)"的
    正则会在内层 `)` 处提前截断，`rfind` 从冒号往回找则能正确定位到
    外层右括号）。不满足 `type(...):` 结构时返回 None，调用方据此判定
    该 commit 不参与主判据匹配（不误判为"scope 为空"）。"""
    if not COMMIT_TYPE_PREFIX_RE.match(subject):
        return None
    paren_start = subject.find("(")
    colon_idx = subject.find(":", paren_start)
    if colon_idx == -1:
        return None
    paren_end = subject.rfind(")", paren_start, colon_idx)
    if paren_end == -1 or paren_end + 1 != colon_idx:
        return None
    return subject[paren_start + 1:paren_end]


def _extract_row_numbers(text: str) -> set[int]:
    """从文本中提取全部 `#数字` 形式的队列行号引用。用 `ROW_NUMBER_RE`
    （`#(\\d+)`）按完整数字游程提取——`\\d+` 贪婪匹配整串数字，`#220` 只会
    被提取为整数 220，不会被"#22 是否为其子串"这类朴素子串搜索误判命中
    （2026-08-07 实测坐实：`git log --grep="#22"` 命中 29 条，因 `#22` 是
    `#220`/`#221`/`#223`/`#225`/`#227` 的子串——本函数按数字游程而非字符
    子串比对，天然规避这一误报源，不依赖额外的正则单词边界断言）。"""
    return {int(n) for n in ROW_NUMBER_RE.findall(text)}


def _touch_zone_path_matches(file_path: str, frag: str) -> bool:
    """触碰区片段与 commit 实际改动文件路径的匹配判据（队列 #302 副
    判据）——目录型片段（以 `/` 结尾）用前缀匹配；文件型片段沿用
    `_resolve_batch_files` 同一套精确相等/`/` 后缀匹配规则，不另起一套
    判据。"""
    if frag.endswith("/"):
        return file_path.startswith(frag)
    return file_path == frag or file_path.endswith("/" + frag)


def _recent_commit_records(repo_root: Path, days: int) -> list[dict]:
    """队列 #302：扫近 `days` 天全部 commit，返回 [{sha, subject, scope,
    row_numbers, files}, ...]。只读 `git log`，不修改任何状态。

    只解析 `%s`（commit 首行/subject），不碰 commit body——"正文提及不算
    完成"这一误报源由此在数据源头就被排除，不需要在 scope 提取之后再
    额外过滤（本项目 commit 习惯把讨论性文字也写进单行 subject 的冒号
    之后，`_extract_commit_scope` 只取冒号之前的括号内容，同样把这部分
    排除在外，两层防线共同生效）。"""
    result = _run_git(
        ["log", f"--since={days} days ago", "--name-only", "--format=%x01%H%x02%s%x03"],
        repo_root, check=False,
    )
    if result.returncode != 0:
        return []
    records = []
    for block in result.stdout.split("\x01"):
        block = block.strip("\n")
        if not block or "\x02" not in block or "\x03" not in block:
            continue
        header, _, rest = block.partition("\x03")
        sha, _, subject = header.partition("\x02")
        files = [line.strip() for line in rest.splitlines() if line.strip()]
        scope = _extract_commit_scope(subject)
        row_numbers = _extract_row_numbers(scope) if scope else set()
        records.append({
            "sha": sha.strip(), "subject": subject.strip(),
            "scope": scope, "row_numbers": row_numbers, "files": files,
        })
    return records


def _find_stale_pending_rows(repo_root: Path, days: int = STALE_ROW_LOOKBACK_DAYS) -> list[dict]:
    """队列 #302：批量派活前核对——§一 待处理行（含在办中，即机器字段
    `open`/`partial`，队列 #308 决策点 4 起改读字段），是否已被近 `days`
    天内的 commit 明确声称做过（主判据）或触碰过其"触碰区"列声明的路径
    （副判据）。纯只读、纯提示，不改任何状态，判定权留给人（"触碰区被动
    过"不等于"那件事做完了"，副判据必然有误报，它的定位是把"逐行凭记忆
    判断"变成"只核这几条被标红的"，不是判定器）。

    `blocked`/`timed=`/`hold`/`done` 结构性排除（受外部阻塞/触发日未到/
    我方主动搁置/已完成——均非"看起来待处理、实则可能已被顺手做完"这一
    误报形态的目标），队列 #308 E1 子项指出的正是这类误报（如 #129 曾被
    仅凭"待"字样误标为待处理，其实是定时触发型）。

    队列 #315：§一 现分散在两份物理文件里（按 `[D:机/业]` 拆分），编号
    空间单一（决策点2），聚合两份文件的行不会撞号，直接合并处理。"""
    rows: list[dict] = []
    for queue_path in _iter_queue_paths():
        queue_text = _read_queue(repo_root, queue_path)
        rows.extend(_parse_section_one(queue_text))
    pending = []
    for r in rows:
        status_value, _, _ = _parse_status_domain_fields(r["status_cell"])
        if status_value is None:
            # 非静默降级：字段缺失/非法（未来绕锁写入等场景），回退旧的
            # "开头片段含待"关键词判据，但显式留痕，不装作字段一直存在。
            print(f"⚠ §一 #{r.get('row_id', '?')} 状态字段缺失/非法，"
                  "已回退旧关键词判据（非静默降级，见队列 #308）")
            if "待" in _leading_status_segment(r["status_cell"]):
                pending.append(r)
            continue
        if status_value in ("open", "partial"):
            pending.append(r)
    commits = _recent_commit_records(repo_root, days)

    results = []
    for row in pending:
        try:
            row_id = int(row["row_id"])
        except ValueError:
            continue
        primary_hits = [c for c in commits if row_id in c["row_numbers"]]
        touch_fragments = re.findall(r"`([^`]+)`", row["touch_zone_cell"])
        secondary_hits = []
        if touch_fragments:
            for c in commits:
                if any(
                    _touch_zone_path_matches(f, frag)
                    for f in c["files"] for frag in touch_fragments
                ):
                    secondary_hits.append(c)
        results.append({
            "row_id": row["row_id"],
            "primary": bool(primary_hits),
            "secondary": bool(secondary_hits),
            "primary_commits": _format_commit_shas(primary_hits),
            "secondary_commits": _format_commit_shas(secondary_hits),
        })
    return results


def _format_commit_shas(hits: list[dict]) -> list[str]:
    """把命中 commit 列表格式化为展示用的短 sha 列表——`git log` 输出本就
    是新→旧序，截断只保留最近 `STALE_ROW_MAX_DISPLAYED_COMMITS` 个（对
    "这行最近是不是刚被动过"这一问题最有信息量），超出部分折成一条
    `+N more` 提示，不静默丢弃计数（同"不留无过滤清单"的一贯纪律）。"""
    shas = [c["sha"][:7] for c in hits]
    if len(shas) <= STALE_ROW_MAX_DISPLAYED_COMMITS:
        return shas
    kept = shas[:STALE_ROW_MAX_DISPLAYED_COMMITS]
    kept.append(f"+{len(shas) - STALE_ROW_MAX_DISPLAYED_COMMITS} more")
    return kept


def _partition_pending_rows_by_batch_isolation(
    pending_rows: list[dict], dirty_paths: list[str], log: list[str],
) -> tuple[list[dict], dict[str, tuple[list[str], list[str], list[str]]], list[str]]:
    """队列 #238：sweep 批次隔离——把"任一脏文件未声明即整轮 return 0"的
    全局门，改为"只阻塞自身声明存在歧义的批次，其余批次照常落库"。

    背景（详见文件头部说明）：旧实现里，凡 `git status` 存在一个不属于任何
    批次声明的脏路径——哪怕只有一个、哪怕与在办批次毫无关系——`main()`
    就整轮 `return 0`，已正确声明、彼此互不相关的批次被连带跳过（08-04
    实测 17-20 批积压，堵点常常只有 1-5 个真文件）。

    新判据：一个批次是否被阻塞，只取决于**它自己**的声明片段解析结果是否
    存在 `ambiguous`（该片段在当前脏路径中命中 ≥2 个候选、且无精确相等
    命中——见 `_resolve_batch_files` 队列 #234(1) 的精确相等优先收窄）。
    `ambiguous` 片段对应的候选路径必然不在 `declared_all` 里（未被计入
    resolved），这正是"声明片段与未声明脏文件有交集"这句话的精确含义——
    该批次自己声明的一部分，客观上无法安全判定它是不是这些脏文件之一，
    此时**整个批次**（含它其它已能干净解析的片段）都暂缓，不做部分提交
    ——批次内容仍要求原子提交，不拆半。

    与它无关的其它批次（resolved/not_dirty 均已确定、`ambiguous` 为空）
    不受影响，正常进入后续 normal_rows/straggler_rows 处理。

    真正"没人声明"的孤儿脏文件（不出现在任何批次的 resolved 或 ambiguous
    候选里）不阻塞任何批次，只作为独立提示列出（不写入 `log` 之外的任何
    地方）——这类文件的持续存在交给调用方接线的 #236(2) 孤儿脏文件告警去
    处理，sweep 主流程本身不再因它们停摆。

    返回 (clean_rows, row_resolution, orphan_paths)：
      clean_rows     — 未被阻塞、可继续按原逻辑分流 normal/straggler 的批次
      row_resolution — {batch_id: (resolved, not_dirty, ambiguous)}，
                        供调用方复用（避免重复调用 `_resolve_batch_files`）
      orphan_paths   — 不属于任何批次任何片段（含歧义候选）的脏路径，
                        按字典序排列，供调用方接线孤儿告警
    """
    row_resolution: dict[str, tuple[list[str], list[str], list[str]]] = {}
    declared_all: set[str] = set()
    for row in pending_rows:
        resolved, not_dirty, ambiguous = _resolve_batch_files(row["files_cell"], dirty_paths)
        row_resolution[row["batch_id"]] = (resolved, not_dirty, ambiguous)
        declared_all.update(resolved)

    ambiguous_candidates: set[str] = set()
    clean_rows: list[dict] = []
    for row in pending_rows:
        resolved, not_dirty, ambiguous = row_resolution[row["batch_id"]]
        if not ambiguous:
            clean_rows.append(row)
            continue
        explain_parts = []
        for frag in ambiguous:
            candidates = _explain_ambiguous_candidates(frag, dirty_paths)
            ambiguous_candidates.update(candidates)
            explain_parts.append(
                f"`{frag}` 命中 {len(candidates)} 处（{'、'.join(candidates)}），判为歧义"
            )
        log.append(
            f"⚠ 批次 {row['batch_id']} 因声明片段未能唯一判定而暂缓（不影响其它批次）："
            + "；".join(explain_parts)
        )

    orphan_paths = sorted(
        p for p in dirty_paths if p not in declared_all and p not in ambiguous_candidates
    )
    if orphan_paths:
        log.append(
            "⚠ 以下脏路径不属于任何待 commit 批次声明（孤儿，不阻塞其它批次，"
            "长期未认领由 #236 孤儿告警另行点名）："
        )
        log.extend(f"    - {p}" for p in orphan_paths)

    return clean_rows, row_resolution, orphan_paths


def _read_orphan_state(repo_root: Path) -> dict:
    path = repo_root / ORPHAN_STATE_REL
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_orphan_state(repo_root: Path, state: dict) -> None:
    path = repo_root / ORPHAN_STATE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _track_and_alert_orphan_paths(
    repo_root: Path, orphan_paths: list[str], log: list[str],
) -> None:
    """队列 #236(2)：孤儿脏文件（不属于任何批次声明）持续超过阈值即主动
    告警——#238 批次隔离后 sweep 不再因孤儿文件整轮停摆，但"安静地跳过"
    本身仍是问题（#236 取证：4 个孤儿文件挡住 20 个批次跨天不落库，根因
    正是"没人知道"）。复用 #171 已建的 webhook 通道。

    去重：每个路径只在跨过 `ORPHAN_ALERT_THRESHOLD_HOURS` 阈值时首次告警，
    此后每满一个阈值周期再提醒一次，不逐轮（每小时）重复打扰——#147
    `gap_alert` 的"狼来了"教训：过密的提醒会被无视。路径一旦不再是孤儿
    （被声明或已消失）即从状态里清除，不留陈旧记录误导下一次真实孤儿的
    "已孤儿多久"文案。

    队列 #301（2026-08-07，Shao Peishen 选 (b)）：路径从状态清除时，若其
    `last_alerted` 非空（即真的对它告警过），补发一条"✅ 已解除"通知——
    2026-08-07 实测：告警送达前孤儿已自愈，读者只能凭消息本身判断不了
    是否还成立，被迫转人查证。`last_alerted` 为空（从未跨阈值即消失）不
    补发——为一件对方根本没听说过的事发解除通知，本身就是新噪音（#147
    教训）。
    """
    state = _read_orphan_state(repo_root)
    now = datetime.now(timezone.utc)
    current = set(orphan_paths)
    resolved: list[tuple[str, float]] = []
    for path in list(state.keys()):
        if path not in current:
            entry = state[path]
            if entry.get("last_alerted") is not None:
                first_seen = datetime.fromisoformat(entry["first_seen"])
                resolved.append((path, (now - first_seen).total_seconds() / 3600))
            del state[path]

    to_alert: list[tuple[str, float]] = []
    for path in orphan_paths:
        entry = state.get(path)
        if entry is None:
            state[path] = {"first_seen": now.isoformat(), "last_alerted": None}
            continue
        first_seen = datetime.fromisoformat(entry["first_seen"])
        age_hours = (now - first_seen).total_seconds() / 3600
        if age_hours < ORPHAN_ALERT_THRESHOLD_HOURS:
            continue
        last_alerted = entry.get("last_alerted")
        if last_alerted is not None:
            since_last = (now - datetime.fromisoformat(last_alerted)).total_seconds() / 3600
            if since_last < ORPHAN_ALERT_THRESHOLD_HOURS:
                continue
        to_alert.append((path, age_hours))
        entry["last_alerted"] = now.isoformat()

    _write_orphan_state(repo_root, state)

    # 队列 #301：解除通知与"出现"告警相互独立——即便本轮没有新的
    # to_alert，此前告警过的孤儿一旦解除仍要补发通知，反之亦然，两条
    # 分支不得用同一个 early return 互相挡住。
    if resolved:
        lines = "\n".join(f"- `{p}`（存续 {age:.1f} 小时，无需处置）" for p, age in resolved)
        resolved_text = (
            f"✅ 落库sweep：{len(resolved)} 个此前告警过的孤儿脏文件已解除：\n{lines}"
        )
        log.append(f"✅ 孤儿脏文件解除通知：{len(resolved)} 个文件")
        webhook_url = _load_webhook_url(repo_root)
        if webhook_url is None:
            log.append(f"⚠ 未在 .env 找到 {WECOM_WEBHOOK_ENV_KEY}，跳过孤儿解除通知推送（仅留痕日志）。")
        else:
            try:
                _send_wecom_markdown(webhook_url, resolved_text)
                log.append("✓ 孤儿脏文件解除通知已推送。")
            except Exception as exc:  # noqa: BLE001 —— 告警失败不应影响本轮退出码
                log.append(f"⚠ 孤儿脏文件解除通知推送失败（不影响本轮退出码）：{exc}")

    if not to_alert:
        return

    lines = "\n".join(f"- `{p}`（已孤儿 {age:.1f} 小时）" for p, age in to_alert)
    alert_text = (
        f"🧭 落库sweep 检测到 {len(to_alert)} 个脏文件持续未被任何批次声明"
        f"（阈值 {ORPHAN_ALERT_THRESHOLD_HOURS} 小时）：\n{lines}\n"
        "若确认无主，请登记 §二 批次代为声明入库；若仍在编辑中，登记一条"
        "占位批次即可解除本告警。"
    )
    log.append(
        f"🧭 孤儿脏文件告警：{len(to_alert)} 个文件超过 "
        f"{ORPHAN_ALERT_THRESHOLD_HOURS} 小时未声明"
    )
    webhook_url = _load_webhook_url(repo_root)
    if webhook_url is None:
        log.append(f"⚠ 未在 .env 找到 {WECOM_WEBHOOK_ENV_KEY}，跳过孤儿脏文件告警推送（仅留痕日志与状态文件）。")
        return
    try:
        _send_wecom_markdown(webhook_url, alert_text)
    except Exception as exc:  # noqa: BLE001 —— 告警失败不应影响本轮退出码
        log.append(f"⚠ 孤儿脏文件告警推送失败（不影响本轮退出码）：{exc}")
        return
    log.append("✓ 孤儿脏文件告警已推送。")


def _find_missing_deployment_trace(touched_paths: set[str]) -> list[str]:
    """队列 #229：发布收口第②关——本轮 touched_paths 是否命中已部署场景
    白名单、却未同时改动该场景的部署留痕文件。返回命中但缺留痕的场景前缀
    清单（可能为空）。

    三条边界（Shao Peishen 2026-08-03 拍板选 (a)）：
    ① 纯提示，调用方不得据此改变退出码或阻断提交；
    ② 不判断"是否真的部署了"——sweep 拿不到 `.51` 状态，只判"留痕文件是否
       同批改动"这一可机检事实，是否需要补部署留给人判断；
    ③ 初版宁窄勿宽——命中判据是路径前缀白名单，不做内容语义解析（如判断
       CLAUDE.md 的 diff 是否真的更新了"部署状态"段落），避免 #147
       `gap_alert` 式的过度触发反被无视。
    """
    hits = []
    for prefix, trace_file in DEPLOYED_SCENARIO_PREFIXES.items():
        touches_scenario = any(
            p.startswith(prefix) and p != trace_file for p in touched_paths
        )
        if touches_scenario and trace_file not in touched_paths:
            hits.append(prefix)
    return hits


def _announce_missing_deployment_trace(
    repo_root: Path, hits: list[str], log: list[str],
) -> None:
    """队列 #229：命中 `_find_missing_deployment_trace` 时在日志与 webhook
    附一句部署留痕提示——同 #198(c) 范式，纯提示、不阻断、不改退出码。"""
    for prefix in hits:
        log.append(
            f"⚠ 本批改动涉及已部署场景 `{prefix}`，但未见部署留痕行——"
            "若已部署请补留痕；若未部署，请勿对专员宣称已上线"
            "（见 CLAUDE.md §5 第 8 步发送硬前置）"
        )
    webhook_url = _load_webhook_url(repo_root)
    if webhook_url is None:
        log.append(f"⚠ 未在 .env 找到 {WECOM_WEBHOOK_ENV_KEY}，跳过部署留痕提示推送（仅留痕日志）。")
        return
    try:
        _send_wecom_markdown(
            webhook_url,
            "🔧 落库sweep：以下已部署场景本批改动未见部署留痕，请核实：\n"
            + "\n".join(f"- `{p}`" for p in hits),
        )
    except Exception as exc:  # noqa: BLE001 —— 提示推送失败不应影响本轮退出码
        log.append(f"⚠ 部署留痕提示推送失败（不影响本轮退出码）：{exc}")
        return
    log.append("✓ 部署留痕提示已推送。")


# ============================================================
# 队列 #298（2026-08-07）：M1 场景 spec 覆盖缺口检测
# ============================================================


def _scenario_short_code(dir_name: str) -> str | None:
    """从场景目录名提取短代码前缀（`SCENARIO_SHORT_CODE_RE`），供匹配
    `openspec/specs/` 里同前缀的 capability。已用现存全部场景目录验证：
    `SC1-供应商风险初筛`→`SC1`、`QD-A-8D不良分析`→`QD-A`（代码本身含
    连字符也能正确取到）、`FI2-三单匹配自动对账`→`FI2`。取不到时返回
    None（目录名不含预期的"代码-中文"结构）。"""
    match = SCENARIO_SHORT_CODE_RE.match(dir_name)
    return match.group(1).lower() if match else None


def _scenario_dirs(repo_root: Path) -> list[Path]:
    root = repo_root / SCENARIO_ROOT_REL
    if not root.is_dir():
        return []
    dirs = []
    for dept_dir in sorted(root.iterdir()):
        if not dept_dir.is_dir():
            continue
        for scenario_dir in sorted(dept_dir.iterdir()):
            if scenario_dir.is_dir():
                dirs.append(scenario_dir)
    return dirs


def _scenario_is_retired(scenario_dir: Path) -> bool:
    claude_md = scenario_dir / "CLAUDE.md"
    if not claude_md.exists():
        return False
    try:
        return SCENARIO_RETIREMENT_MARKER in claude_md.read_text(encoding="utf-8")
    except OSError:
        return False


def _spec_capability_names(repo_root: Path) -> set[str]:
    specs_dir = repo_root / OPENSPEC_SPECS_REL
    if not specs_dir.is_dir():
        return set()
    return {p.name for p in specs_dir.iterdir() if p.is_dir()}


def _in_flight_change_capability_names(repo_root: Path) -> dict[str, list[str]]:
    """{capability_name: [尚未归档、含该 capability delta 的变更包名, ...]}
    ——只扫 `openspec/changes/` 顶层（不含 `archive/`）里带 `specs/` 子目录
    的包，供 M1"顺带指出未归档包名"使用（形态甲：躺在这里；形态乙：
    这里也找不到，须重新补写）。"""
    changes_dir = repo_root / OPENSPEC_CHANGES_REL
    result: dict[str, list[str]] = {}
    if not changes_dir.is_dir():
        return result
    for change_dir in sorted(changes_dir.iterdir()):
        if not change_dir.is_dir() or change_dir.name == "archive":
            continue
        specs_subdir = change_dir / "specs"
        if not specs_subdir.is_dir():
            continue
        for cap_dir in specs_subdir.iterdir():
            if cap_dir.is_dir():
                result.setdefault(cap_dir.name, []).append(change_dir.name)
    return result


def _find_scenario_spec_coverage_gaps(repo_root: Path) -> list[dict]:
    """队列 #298 M1（2026-08-07 当日扩容，扫描域由已部署场景白名单扩为
    `4-数字员工/*/*/` 全部场景）：已建造（≥1 个 .py）、未标退役的场景，
    若其短代码前缀在 `openspec/specs/` 零命中即视为缺口，区分形态甲
    （delta 躺在某未归档包）与形态乙（压根没写过，归档也救不了）。

    边界（同 #229/#236(2) 先例）：只判"spec 存不存在"，不判"spec 对不
    对"——空壳/仅覆盖新分支的 capability 也能让本函数静音，这是刻意的
    粗粒度取舍，见文件头部本节说明。"""
    spec_names = _spec_capability_names(repo_root)
    in_flight = _in_flight_change_capability_names(repo_root)
    gaps = []
    for scenario_dir in _scenario_dirs(repo_root):
        short_code = _scenario_short_code(scenario_dir.name)
        if short_code is None:
            continue
        if not any(scenario_dir.rglob("*.py")):
            continue  # 未建造，谈不上 spec 缺口
        if _scenario_is_retired(scenario_dir):
            continue
        has_spec = any(
            name == short_code or name.startswith(short_code + "-") for name in spec_names
        )
        if has_spec:
            continue
        pending_delta_packages = sorted({
            pkg for cap, pkgs in in_flight.items()
            if cap == short_code or cap.startswith(short_code + "-")
            for pkg in pkgs
        })
        gaps.append({
            "scenario": scenario_dir.name,
            "short_code": short_code,
            "form": "甲" if pending_delta_packages else "乙",
            "pending_delta_packages": pending_delta_packages,
        })
    return gaps


def _spec_dirs_mentioning(repo_root: Path, needle: str) -> list[str]:
    specs_dir = repo_root / OPENSPEC_SPECS_REL
    if not specs_dir.is_dir():
        return []
    hits = []
    for cap_dir in sorted(specs_dir.iterdir()):
        spec_file = cap_dir / "spec.md"
        if not spec_file.is_file():
            continue
        try:
            if needle in spec_file.read_text(encoding="utf-8"):
                hits.append(cap_dir.name)
        except OSError:
            continue
    return hits


def _find_platform_packages_without_spec_mention(repo_root: Path) -> list[str]:
    """队列 #298（2026-08-07 当日扩容）：`5-平台底座/*/` 全部包无短代码
    前缀约定可循（`platform-*`/`aibot-*`/`sweep-*` 等 capability 名称与
    包目录名之间没有机械对应关系），改用弱信号——`openspec/specs/*/
    spec.md` 内容是否字面提及包目录名。精度低于场景的短代码前缀匹配，
    故调用方只把结果列入日志、不触发 webhook（`deploy-tools` 是当前唯一
    "零提及"实例，与队列行原始判断"待判，只列不报"一致）。"""
    root = repo_root / PLATFORM_PACKAGES_ROOT_REL
    if not root.is_dir():
        return []
    hits = []
    for pkg_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        # 与场景侧不同：平台底座包不保证是 Python（如 `deploy-tools` 纯
        # PowerShell），"是否已建造"改判目录内是否有任何文件，不锁定 `.py`。
        if not any(p.is_file() for p in pkg_dir.rglob("*")):
            continue
        if not _spec_dirs_mentioning(repo_root, pkg_dir.name):
            hits.append(pkg_dir.name)
    return hits


def _read_json_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_json_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _track_and_alert_standing_state(
    repo_root: Path, label: str, state_rel_path: str, current_keys: set,
    realert_interval_hours: float, render_alert_text, render_resolved_text, log: list[str],
) -> None:
    """队列 #308 子项 D1：标准长期存在状态类告警的出现→告警／消失→解除
    通用骨架，复刻 `_track_and_alert_orphan_paths`（#301）已验证的模式，
    供场景 spec 缺口（M1）／在途变更包滞留（M2）复用（分叉告警状态形状
    不同，单独在 `_handle_fork_detected`/`_reset_fork_state` 处理，未纳入
    本函数）。

    与孤儿脏文件那版的一处不同：本函数面向的两类 retrofit 对象现状均为
    "发现即告警"，不设首次出现的存续阈值，只保留"多久后允许再提醒一次"
    这一节流维度（`realert_interval_hours`）；resolved 消息也不携带
    "存续了多久"（孤儿脏文件的 `first_seen`/`last_alerted` 双字段状态形状
    更丰富，本函数保持与既有 `SCENARIO_SPEC_GAP_STATE_REL`/
    `STALE_CHANGE_STATE_REL` 单时间戳状态形状兼容，不做 schema 迁移）。

    `render_alert_text(to_alert_keys) -> str` / `render_resolved_text(resolved_keys) -> str`
    由调用方提供，负责把 key 列表渲染成具体消息正文（各调用方的详情信息
    不在本函数持有的 key 集合里，闭包捕获）。
    """
    state_path = repo_root / state_rel_path
    state = _read_json_state(state_path)
    now = datetime.now(timezone.utc)

    resolved = [key for key in state if key not in current_keys]
    for key in resolved:
        del state[key]

    to_alert = []
    for key in current_keys:
        last_alerted = state.get(key)
        if last_alerted is not None:
            since = (now - datetime.fromisoformat(last_alerted)).total_seconds() / 3600
            if since < realert_interval_hours:
                continue
        to_alert.append(key)
        state[key] = now.isoformat()
    _write_json_state(state_path, state)

    webhook_url = _load_webhook_url(repo_root)

    if resolved:
        log.append(f"✅ {label}解除通知：{len(resolved)} 项")
        if webhook_url is None:
            log.append(f"⚠ 未在 .env 找到 {WECOM_WEBHOOK_ENV_KEY}，跳过{label}解除通知推送（仅留痕日志）。")
        else:
            try:
                _send_wecom_markdown(webhook_url, render_resolved_text(resolved))
                log.append(f"✓ {label}解除通知已推送。")
            except Exception as exc:  # noqa: BLE001 —— 告警失败不应影响本轮退出码
                log.append(f"⚠ {label}解除通知推送失败（不影响本轮退出码）：{exc}")

    if not to_alert:
        return
    if webhook_url is None:
        log.append(f"⚠ 未在 .env 找到 {WECOM_WEBHOOK_ENV_KEY}，跳过{label}告警推送（仅留痕日志与状态文件）。")
        return
    try:
        _send_wecom_markdown(webhook_url, render_alert_text(to_alert))
        log.append(f"✓ {label}告警已推送。")
    except Exception as exc:  # noqa: BLE001 —— 告警失败不应影响本轮退出码
        log.append(f"⚠ {label}告警推送失败（不影响本轮退出码）：{exc}")


# ============================================================
# 队列 §四 #87⑴（2026-08-21，OP-0821-G）：告警正文里的队列行指针改为
# 动态解析
# ============================================================
# 原文把「存量补齐见队列 #299」写成硬编码字符串，而 §一 #299 已于
# 2026-08-07 `[S:done]` 销号 ⇒ 该告警此后每天都在把读者指向一个已经
# 关闭的行。这与本文件反复记的那一族问题同源：**一个指针写死在代码
# 里，它指向的对象却会自己变状态，而变了不会有任何报错。**
#
# 改法取「发出时动态查」而非「换指一个长期有效的载体」——后者仍是硬
# 编码，只是把过期时间推后。三条分支均显式措辞、不静默沿用旧文案：
#   - 该行仍在办（open/partial/hold/blocked/timed） → 照旧指路；
#   - 该行已 `[S:done]` → 改口为「原承接行已销号，需另行派单」；
#   - 查不到该行（被迁走／队列文件缺失／状态字段缺失） → 如实说
#     「状态未取到」，不假装它还在办（同本文件「非静默降级」纪律）。
STOCK_BACKFILL_QUEUE_ROW_ID = "299"


def _render_stock_backfill_pointer(repo_root) -> str:
    """返回场景 spec 缺口告警里那句「存量补齐……」的当前措辞。

    刻意不缓存、不在模块导入期求值——队列行状态随时可能被别的 session
    改写，本函数的全部价值就在于「每次发出时重新看一眼」。"""
    status = _lookup_section_one_status(repo_root, STOCK_BACKFILL_QUEUE_ROW_ID)
    row_ref = f"队列 §一 #{STOCK_BACKFILL_QUEUE_ROW_ID}"
    if status == "done":
        return (
            f"存量补齐的原承接行 {row_ref} 已销号（`[S:done]`），"
            "本批缺口需另行派单"
        )
    if status is None:
        return (
            f"存量补齐原记于 {row_ref}（**该行当前状态未取到**，"
            "请先核实它是否仍是有效承接行）"
        )
    return f"存量补齐见{row_ref}（当前 `[S:{status}]`）"


def _lookup_section_one_status(repo_root, row_id: str) -> str | None:
    """跨两份物理队列文件查 §一 某行的机器状态字段取值。

    返回 `done`/`open`/`partial`/`hold`/`blocked`/`timed=YYYY-MM-DD`
    之一；行不存在、或存在但状态列没有合法机器字段时返回 None——两种
    情形调用方一律走「如实说未取到」，不猜。"""
    for queue_path in _iter_queue_paths():
        for row in _parse_section_one(_read_queue(repo_root, queue_path)):
            if row["row_id"] != row_id:
                continue
            status, _domain, _rest = _parse_status_domain_fields(row["status_cell"])
            return status
    return None


def _announce_scenario_spec_coverage_gaps(
    repo_root: Path, gaps: list[dict], log: list[str],
) -> None:
    """队列 #298 M1：日志逐条列出全部缺口（不论是否跨过告警节流）；
    webhook 每个场景 24 小时内只推一次（同 #236(2) 的"狼来了"防线——
    这是标准长期存在的结构性状态，逐轮/每小时重复推送必被无视）。
    队列 #308 子项 D1：alert/resolve 记账部分改用通用骨架
    `_track_and_alert_standing_state`。"""
    for gap in gaps:
        pkgs = "、".join(f"`{p}`" for p in gap["pending_delta_packages"]) or "无（需重新补写 spec delta）"
        log.append(
            f"⚠ 场景 `{gap['scenario']}` 已建造但 openspec/specs/ 零命中 "
            f"`{gap['short_code']}` 前缀 capability（形态{gap['form']}，"
            f"delta 所在未归档包：{pkgs}）"
        )

    gaps_by_scenario = {g["scenario"]: g for g in gaps}

    def render_alert(keys):
        lines = []
        for key in keys:
            gap = gaps_by_scenario[key]
            pkgs = "、".join(f"`{p}`" for p in gap["pending_delta_packages"]) or "需重新补写"
            lines.append(f"- `{key}`（形态{gap['form']}，{pkgs}）")
        return (
            f"📋 落库sweep：{len(keys)} 个已建造场景在 openspec/specs/ 零命中（可追溯链断），"
            # §四 #87⑴：此处原为硬编码 "存量补齐见队列 #299"，该行已销号
            # ⇒ 改为发出时动态查，见 `_render_stock_backfill_pointer`。
            f"{_render_stock_backfill_pointer(repo_root)}：\n" + "\n".join(lines)
        )

    def render_resolved(keys):
        lines = "\n".join(f"- `{key}`（已重新命中 capability，无需处置）" for key in keys)
        return f"✅ 落库sweep：{len(keys)} 个此前告警过的场景 spec 缺口已解除：\n{lines}"

    _track_and_alert_standing_state(
        repo_root, "场景 spec 缺口", SCENARIO_SPEC_GAP_STATE_REL,
        set(gaps_by_scenario), SCENARIO_SPEC_GAP_ALERT_INTERVAL_HOURS,
        render_alert, render_resolved, log,
    )


# ============================================================
# 队列 #298（2026-08-07）：M2 在途变更包滞留提示
# ============================================================

TASK_DONE_RE = re.compile(r"^\s*-\s*\[x\]", re.MULTILINE | re.IGNORECASE)
TASK_TODO_RE = re.compile(r"^\s*-\s*\[ \]", re.MULTILINE)


def _parse_tasks_completion(tasks_md_path: Path) -> tuple[int, int] | None:
    """返回 (done, total)；`tasks.md` 不存在或零任务项时返回 None。"""
    if not tasks_md_path.exists():
        return None
    try:
        text = tasks_md_path.read_text(encoding="utf-8")
    except OSError:
        return None
    done = len(TASK_DONE_RE.findall(text))
    todo = len(TASK_TODO_RE.findall(text))
    total = done + todo
    return (done, total) if total else None


def _change_package_last_touched_days(repo_root: Path, change_dir_rel: str) -> float | None:
    result = _run_git(["log", "-1", "--format=%ct", "--", change_dir_rel], repo_root, check=False)
    ts = result.stdout.strip()
    if not ts.isdigit():
        return None
    last_commit = datetime.fromtimestamp(int(ts), tz=timezone.utc)
    return (datetime.now(timezone.utc) - last_commit).total_seconds() / 86400


def _change_package_has_defer_marker(change_dir: Path) -> bool:
    for name in ("proposal.md", "design.md", "tasks.md"):
        p = change_dir / name
        if not p.exists():
            continue
        try:
            if STALE_CHANGE_DEFER_MARKER in p.read_text(encoding="utf-8"):
                return True
        except OSError:
            continue
    return False


def _change_package_observation_window_days(change_dir: Path) -> float | None:
    """队列 #314②：在 proposal.md/design.md/tasks.md（同 `_change_package_
    has_defer_marker` 一致的扫描范围与顺序，取第一处命中）里查找显式声明
    的"预期观察窗口"，返回声明的天数；三处均未声明则返回 None（未声明
    时调用方须维持现状报法，不得当错误处理）。"""
    for name in ("proposal.md", "design.md", "tasks.md"):
        p = change_dir / name
        if not p.exists():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        m = OBSERVATION_WINDOW_RE.search(text)
        if m:
            return float(m.group(1))
    return None


def _read_stale_change_acks(repo_root: Path) -> dict:
    return _read_json_state(repo_root / STALE_CHANGE_ACK_STATE_REL)


def _write_stale_change_acks(repo_root: Path, acks: dict) -> None:
    _write_json_state(repo_root / STALE_CHANGE_ACK_STATE_REL, acks)


def cmd_ack_stale_change(repo_root: Path, change_name: str, note: str) -> int:
    """队列 #308 子项 D2：记录一次对"疑似遗忘归档"候选的人工判定，连同
    判定当时的完成度指纹（done/total）——与 `STALE_CHANGE_DEFER_MARKER`
    （"暂不归档"文本标记，变更作者对未来的永久声明）不同，本确认是复核者
    对过去某一刻状态的确认："我在 X 指纹下判定过这是合理的，指纹变了要
    重新看"，不是永久白名单。"""
    if not note.strip():
        print("✗ --note 不能为空——须提供本次判定依据摘录，不得留空确认（同 approve_followup_letter.py 的既有强制惯例）。")
        return 1
    change_dir = repo_root / OPENSPEC_CHANGES_REL / change_name
    tasks_path = change_dir / "tasks.md"
    if not tasks_path.exists():
        print(f"✗ 未找到 {tasks_path}，拒绝记录确认（无法计算指纹）。")
        return 1
    completion = _parse_tasks_completion(tasks_path)
    if completion is None:
        print(f"✗ {tasks_path} 未解析出任何任务勾选项，拒绝记录确认（无法计算指纹）。")
        return 1
    done, total = completion
    acks = _read_stale_change_acks(repo_root)
    acks[change_name] = {
        "fingerprint": [done, total],
        "acked_at": datetime.now(timezone.utc).isoformat(),
        "note": note,
    }
    _write_stale_change_acks(repo_root, acks)
    print(f"✓ 已记录确认：{change_name}（指纹 {done}/{total}），指纹未变期间本变更包不再触发"
          "「疑似遗忘归档」告警；tasks.md 有新的勾选变化后自动失效、恢复正常告警流程。")
    return 0


def _find_stale_in_flight_changes(repo_root: Path) -> list[dict]:
    """队列 #298 M2：在途 openspec 变更包滞留——完成率≥
    `STALE_CHANGE_COMPLETION_THRESHOLD` 且距最后一次改动≥
    `STALE_CHANGE_MIN_DAYS_IDLE` 天，且未在自身 proposal/design/tasks 内
    声明"暂不归档"（降噪，见文件头部本节说明——天数阈值已更正原文
    "≥7天"与其自身举例"fi2-recon-mvp 90%/3天"的矛盾，改取 3 天）。

    队列 #308 子项 D2：命中上述条件后，若存在对该变更包的确认记录
    （`--ack-stale-change`）且其指纹（done/total）与当前完全一致，本候选
    完全静默（不出现在返回列表里，不进日志、不进 webhook）——"已判定 ＋
    指纹未变"双条件，区别于 `STALE_CHANGE_DEFER_MARKER` 那种一次性永久
    白名单。"""
    changes_dir = repo_root / OPENSPEC_CHANGES_REL
    if not changes_dir.is_dir():
        return []
    acks = _read_stale_change_acks(repo_root)
    hits = []
    for change_dir in sorted(changes_dir.iterdir()):
        if not change_dir.is_dir() or change_dir.name == "archive":
            continue
        completion = _parse_tasks_completion(change_dir / "tasks.md")
        if completion is None:
            continue
        done, total = completion
        rate = done / total
        if rate < STALE_CHANGE_COMPLETION_THRESHOLD:
            continue
        rel_path = f"{OPENSPEC_CHANGES_REL}/{change_dir.name}"
        days_idle = _change_package_last_touched_days(repo_root, rel_path)
        if days_idle is None or days_idle < STALE_CHANGE_MIN_DAYS_IDLE:
            continue
        if _change_package_has_defer_marker(change_dir):
            continue
        ack = acks.get(change_dir.name)
        if ack is not None and ack.get("fingerprint") == [done, total]:
            continue  # D2：已判定且指纹未变，完全静默
        hits.append({
            "change": change_dir.name, "done": done, "total": total,
            "rate": rate, "days_idle": days_idle,
            "observation_window_days": _change_package_observation_window_days(change_dir),
        })
    return hits


def _load_change_classifier(log: list[str]):
    """加载完工形态判定器（变更包 auto-archive-substantive-complete，OP-0823-F）。

    🔴 **从低取值**：加载失败时返回 None，调用方退回原有单一措辞并把原因记进日志——
    不静默、不抛异常、不中断 sweep 主流程。一条告警的措辞变精确是改进，为它把整轮
    落库拖挂则是倒退。
    """
    path = Path(__file__).resolve().with_name("工具-变更包自动归档.py")
    try:
        spec = importlib.util.spec_from_file_location("_change_classifier", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module  # dataclass 处理注解时会回查 sys.modules
        spec.loader.exec_module(module)
        return module
    except Exception as exc:  # noqa: BLE001 —— 任何加载失败都只降级，不上抛
        log.append(f"⚠ 完工形态判定器加载失败（{type(exc).__name__}: {exc}），本轮滞留告警退回原措辞")
        return None


def _classify_change_package(classifier, repo_root: Path, change_name: str):
    """读该包 tasks.md 并判定；判定器不可用或读不到时返回 None（调用方退回原措辞）。"""
    if classifier is None:
        return None
    tasks = repo_root / OPENSPEC_CHANGES_REL / change_name / "tasks.md"
    try:
        return classifier.classify_tasks(tasks.read_text(encoding="utf-8"), change_name)
    except OSError:
        return None


def _announce_stale_in_flight_changes(repo_root: Path, hits: list[dict], log: list[str]) -> None:
    """队列 #298 M2：日志逐条列出，webhook 每个包 24 小时内只推一次
    （同 M1/`_track_and_alert_orphan_paths` 的节流理由）。队列 #308 子项
    D1：alert/resolve 记账部分改用通用骨架 `_track_and_alert_standing_
    state`。

    队列 #314②（2026-08-09 拍板 (c)）：`hits` 内每条已带
    `observation_window_days`——声明了窗口且未超窗的，划入 `observing`：
    只记一行"观察中"日志，不进异常 key 集合、不进 `_track_and_alert_
    standing_state`（即不告警、不节流记账，因为它本就不是异常）。声明
    了窗口但已超窗的、以及未声明窗口的（维持现状），一律划入
    `escalate`，走原有"疑似遗忘归档"告警路径，逻辑不变。"""
    observing = [
        h for h in hits
        if h["observation_window_days"] is not None and h["days_idle"] <= h["observation_window_days"]
    ]
    observing_names = {h["change"] for h in observing}
    escalate = [h for h in hits if h["change"] not in observing_names]

    for hit in observing:
        log.append(
            f"🔭 在途变更包 `{hit['change']}` 观察中（已等 {hit['days_idle']:.1f} 天／"
            f"窗口 {hit['observation_window_days']:.0f} 天），不计异常"
        )

    # 变更包 auto-archive-substantive-complete（OP-0823-F）：分三类各自措辞。
    # 判定器不可用时从低取值——退回原单一措辞并记明原因，不静默、不中断 sweep。
    classifier = _load_change_classifier(log)
    classes: dict[str, str] = {}
    for hit in escalate:
        window_note = (
            f"，超出其声明的观察窗口 {hit['observation_window_days']:.0f} 天"
            if hit["observation_window_days"] is not None else ""
        )
        verdict = _classify_change_package(classifier, repo_root, hit["change"])
        if verdict is None:
            log.append(
                f"⚠ 在途变更包 `{hit['change']}` 完成率 {hit['rate']:.0%}"
                f"（{hit['done']}/{hit['total']}）但已 {hit['days_idle']:.1f} 天无改动{window_note}，"
                "疑似遗忘归档"
            )
            continue
        classes[hit["change"]] = classifier.alert_class(verdict)
        log.append(classifier.alert_phrase(verdict, hit["days_idle"]) + window_note)

    hits_by_change = {h["change"]: h for h in escalate}

    def render_alert(keys):
        # 逐条回显包名／结论／理由——只印一句写死的话、不说命中了什么，判据就无法被
        # 现场证伪（队列 §四 #87 教训）。
        # 🔴 判定器不可用时 `classes` 为空、且**不得**去取 classifier 的常量——
        # 「一条告警措辞变精确」的改进不该有能力让整轮落库抛异常。
        what_by_kind = {} if classifier is None else {
            classifier.ALERT_FORGOTTEN: "只差归档这一步（未勾项只剩 archive 本身、无人留说明）",
            classifier.ALERT_UNDECLARED: "作者已写明理由，但未用机器认得的入口",
            classifier.ALERT_UNFINISHED: "尚有真未完项——它没完工，不属遗忘归档",
        }
        lines = []
        for k in sorted(keys):
            h = hits_by_change[k]
            what = what_by_kind.get(classes.get(k), "高完成率但长期无改动，疑似遗忘归档")
            lines.append(f"- `{k}`（{h['done']}/{h['total']}，{h['days_idle']:.1f} 天无改动）：{what}")
        body = f"📋 落库sweep：{len(keys)} 个在途 openspec 变更包长期无改动：\n" + "\n".join(lines)
        # 🔴 「作者已写明理由但没声明」这一类，正文必须给出声明方式——告警若只说
        # 「你没声明」而不给出口，等于把同一个缺口原样留在那里（#87 的真根因）。
        if classifier is not None and any(
            classes.get(k) == classifier.ALERT_UNDECLARED for k in keys
        ):
            body += (
                "\n\n📝 上列标注「未用机器认得的入口」的包，理由已写在 tasks 行内但机器读不到。"
                "三条现成入口任选其一即可让它不再被误报：\n"
                + classifier.declare_entries_block()
            )
        return body

    def render_resolved(keys):
        lines = "\n".join(f"- `{k}`（已归档或完成率/滞留天数不再满足条件）" for k in keys)
        return f"✅ 落库sweep：{len(keys)} 个此前告警过的在途变更包滞留已解除：\n{lines}"

    _track_and_alert_standing_state(
        repo_root, "在途变更包滞留", STALE_CHANGE_STATE_REL,
        set(hits_by_change), STALE_CHANGE_ALERT_INTERVAL_HOURS,
        render_alert, render_resolved, log,
    )


# ============================================================
# 队列 §一 #338 子项 A 实现（第 4 类常驻状态告警）
# ============================================================

def _claude_md_targets(repo_root: Path) -> list[tuple[str, int]]:
    """返回受检的 `[(相对路径, 字节阈值)]`，按路径排序（正文可复现）。

    🔴 **刻意排除 `.claude/worktrees/**` 下的副本**：那 13 份是历史版本的
    尺寸，对它们告警既无意义又会天天响。两个 glob 本身够不到 worktree 目录
    （它在 `.claude/` 下），这道排除是**显式防御**——万一将来 glob 被放宽，
    这里会挡住，而不是静默多出 13 个告警对象。
    """
    targets: list[tuple[str, int]] = []
    root = repo_root / CLAUDE_MD_ROOT_REL
    if root.is_file():
        targets.append((CLAUDE_MD_ROOT_REL, CLAUDE_MD_ROOT_BYTE_CAP))
    seen: set[str] = set()
    for pattern in CLAUDE_MD_SCENE_GLOBS:
        for path in sorted(repo_root.glob(pattern)):
            if not path.is_file():
                continue
            rel = path.relative_to(repo_root).as_posix()
            if rel.startswith(f"{WORKTREES_DIR_REL}/") or f"/{WORKTREES_DIR_REL}/" in rel:
                continue
            if rel in seen:
                continue
            seen.add(rel)
            targets.append((rel, CLAUDE_MD_SCENE_BYTE_CAP))
    return targets


def _load_progress_lint(repo_root: Path):
    """动态导入 `工具-CLAUDE进度段lint.py`（文件名含中文与连字符，不是合法
    Python 标识符，只能走 `spec_from_file_location`）。

    返回 `(module, None)` 或 `(None, 失败原因)`——**失败一律显式返回原因，
    绝不吞成「顶部段合规」**（CLAUDE.md §5「工具静默回退」：当一个只读操作
    返回了「太干净」的结果，先问它是不是根本没读到我以为的那个对象）。
    """
    script = repo_root / CLAUDE_PROGRESS_LINT_REL
    if not script.is_file():
        return None, f"未找到 {CLAUDE_PROGRESS_LINT_REL}"
    module_name = "_sweep_claude_progress_lint"
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(module_name, script)
        if spec is None or spec.loader is None:
            return None, "spec_from_file_location 返回空"
        module = importlib.util.module_from_spec(spec)
        # 🔴 **必须先注册进 sys.modules 再 exec_module**，不是可选的洁癖：
        # lint 模块里有 `@dataclass`，而 CPython 的 `dataclasses._is_type`
        # 执行 `sys.modules.get(cls.__module__).__dict__` —— 这一句**没有
        # 空值保护**。模块未注册时 `.get()` 返回 None，当场
        # `AttributeError: 'NoneType' object has no attribute '__dict__'`。
        # 实测于 Python 3.14.4（2026-08-23，本机）。
        # ⚠️ 这一坑值得记住的地方在于**它是被本函数的「不静默放过」设计捞
        # 出来的**：若当初把导入失败写成「视同未超限」，顶部段批次跨度这半
        # 条判据会从上线第一天起就永久失效，而日志一切正常、无人会发现。
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(module_name, None)
            raise
    except Exception as exc:  # noqa: BLE001 —— 导入失败不应影响本轮退出码
        return None, f"导入失败：{type(exc).__name__}: {exc}"
    return module, None


def _root_progress_batch_dates(repo_root: Path) -> tuple[list[str] | None, str | None]:
    """返回根 `CLAUDE.md` 顶部进度段内出现的**批次日期**去重列表。

    一条条目的批次日期 = 其正文里**第一个** `（YYYY-MM-DD` 形态的匹配
    （条目自身的批次标注紧跟标题，后续日期是正文引用的其它时点）。
    """
    lint, reason = _load_progress_lint(repo_root)
    if lint is None:
        return None, reason
    root = repo_root / CLAUDE_MD_ROOT_REL
    try:
        text = root.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"读取根 {CLAUDE_MD_ROOT_REL} 失败：{exc}"
    try:
        parsed = lint.parse_structure_a(text)
    except Exception as exc:  # noqa: BLE001
        return None, f"顶部段解析失败：{type(exc).__name__}: {exc}"
    if parsed is None:
        return None, "顶部段未命中结构 A（缺 `> **当前进度**` 头行）"
    dates: list[str] = []
    for entry in parsed.entries:
        match = lint.ENTRY_DATE_RE.search(entry.body)
        if match is None:
            continue
        # ENTRY_DATE_RE 连左括号一起匹配（`[（(]20\d\d-\d\d-\d\d`），去掉首字符。
        date = match.group(0)[1:]
        if date not in dates:
            dates.append(date)
    return sorted(dates), None


def _check_claude_md_carrier_size(repo_root: Path, log: list[str]) -> None:
    """第 4 类常驻状态告警：必载 `CLAUDE.md` 尺寸/批次跨度超限。

    🔴 **回显不是可选项**：本函数无论是否有超限项，都逐项打印「当前值/
    阈值/差额」。理由见常量段注释——上线当天预计零告警，若连回显都没有，
    这个守卫就与「建成 9 天从未发出过一条消息」那个反面教材无法区分。
    """
    breaches: dict[str, str] = {}
    log.append("📏 必载 CLAUDE.md 巡检（每轮回显，零超限时亦不省略）：")
    for rel, cap in _claude_md_targets(repo_root):
        try:
            size = (repo_root / rel).stat().st_size
        except OSError as exc:
            log.append(f"    ⚠ {rel}：尺寸未取到（{exc}）——**不据此判为合规**")
            continue
        if size > cap:
            log.append(f"    🔴 {rel}：{size:,} B / 阈值 {cap:,} B（超出 {size - cap:,} B）")
            breaches[rel] = f"尺寸 {size:,} B，超阈值 {cap:,} B 共 {size - cap:,} B"
        else:
            log.append(f"    · {rel}：{size:,} B / 阈值 {cap:,} B（尚余 {cap - size:,} B）")

    dates, reason = _root_progress_batch_dates(repo_root)
    if dates is None:
        log.append(f"    ⚠ 顶部段批次跨度判据不可用：{reason}——**不据此判为合规**")
    else:
        shown = "、".join(dates) if dates else "无"
        log.append(f"    · {CLAUDE_MD_ROOT_REL} 顶部段批次日期：{len(dates)} 个（{shown}）/ 阈值 1 个")
        if len(dates) > 1:
            note = f"顶部进度段跨 {len(dates)} 个批次日期（{shown}）"
            prior = breaches.get(CLAUDE_MD_ROOT_REL)
            breaches[CLAUDE_MD_ROOT_REL] = f"{prior}；{note}" if prior else note

    def render_alert(keys):
        lines = "\n".join(f"- `{key}`：{breaches[key]}" for key in sorted(keys))
        return (
            f"📏 落库sweep：{len(keys)} 份必载 `CLAUDE.md` 超限"
            "（会话开场必载，越大越挤占每个新 session 的注意力预算）：\n"
            f"{lines}\n"
            "⇒ 处置：原文原样迁 `进度编年-CHANGELOG.md`，迁出前守 J1"
            "（须先有承接载体：队列行号，或具名文件＋章节号）"
        )

    def render_resolved(keys):
        lines = "\n".join(f"- `{key}`（已回落至阈值内）" for key in sorted(keys))
        return f"✅ 落库sweep：{len(keys)} 份此前告警过的 `CLAUDE.md` 已回落：\n{lines}"

    _track_and_alert_standing_state(
        repo_root, "必载 CLAUDE.md 超限", CLAUDE_MD_SIZE_STATE_REL,
        # 🔴 key = 文件相对路径，**刻意不含尺寸数值**：把会变的数放进 key，
        # 每涨一个字节就是一个新 key、天天被当成新问题重新告警，且旧 key
        # 会被判为「已解除」——常驻状态与事件的分界线就在这里。
        set(breaches), CLAUDE_MD_SIZE_ALERT_INTERVAL_HOURS,
        render_alert, render_resolved, log,
    )


# ============================================================
# 队列 §一 #338 子项 B 实现（第 5 类常驻状态告警）
# ============================================================

def _normalize_path_text(text: str) -> str:
    """路径文本归一：反斜杠转正斜杠 + 去尾斜杠。**不做大小写折叠**——
    折叠后再切出来的 worktree 名会全变小写，与真实目录名不符。大小写
    不敏感的比较由调用方对**副本**做，切名一律从原文切。"""
    return text.replace("\\", "/").rstrip("/")


def _query_scheduled_task_actions() -> tuple[list[dict] | None, str | None]:
    """查本机计划任务的 Action 清单，返回 `([{task, execute, arguments}], None)`。

    🔴 **查询失败一律返回 `(None, 原因)`，绝不返回空列表**——空列表的含义
    是「查询成功且本机确实没有任何计划任务」，与「查不到」是两件事。把后者
    冒充成前者，就会得出「零执行体、一切正常」这个看起来完全正常的错误
    结论（同 CLAUDE.md §5「工具静默回退」那一族：**错误不产生任何信号**）。
    """
    last_reason = "未尝试任何 PowerShell 宿主"
    for exe in ("powershell.exe", "pwsh"):
        try:
            result = subprocess.run(
                [exe, "-NoProfile", "-NonInteractive", "-Command", _SCHEDULED_TASK_QUERY_PS],
                capture_output=True, text=True, encoding="utf-8", timeout=120,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            last_reason = f"{exe} 调用失败：{type(exc).__name__}: {exc}"
            continue
        if result.returncode != 0:
            detail = (result.stderr or "").strip().splitlines()
            last_reason = f"{exe} 退出码 {result.returncode}：{detail[0] if detail else '无 stderr'}"
            continue
        raw = (result.stdout or "").strip()
        if not raw:
            # 查询成功但本机零计划任务——这是合法的「成功且为空」。
            return [], None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            last_reason = f"{exe} 输出非 JSON：{exc}"
            continue
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            last_reason = f"{exe} 输出结构非预期：{type(data).__name__}"
            continue
        actions = []
        for item in data:
            if not isinstance(item, dict):
                continue
            actions.append({
                "task": str(item.get("Task") or ""),
                "execute": str(item.get("Execute") or ""),
                "arguments": str(item.get("Arguments") or ""),
            })
        return actions, None
    return None, last_reason


def _registered_worktrees(repo_root: Path) -> list[dict]:
    """解析 `git worktree list --porcelain` 为 `[{path, head}]`。

    🔴 判 worktree 身份**只认注册项**，不看 `git -C <目录>` 的输出——#98
    实测：对非注册目录跑 `git -C`，git 会静默向上找到主工作区的 `.git` 并
    返回**主工作区**的状态（当时返回「分支=master／落后 0／脏 0」，照抄就
    会把一个该清的空壳记成「干净、无需处理」）。
    """
    result = _run_git(["worktree", "list", "--porcelain"], repo_root, check=False)
    entries: list[dict] = []
    current: dict = {}
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            if current:
                entries.append(current)
            current = {"path": _normalize_path_text(line[len("worktree "):].strip()), "head": None}
        elif line.startswith("HEAD ") and current:
            current["head"] = line[len("HEAD "):].strip()
    if current:
        entries.append(current)
    return entries


def _master_ref(repo_root: Path) -> str | None:
    """对齐目标 ref：优先本地 `master`（ff 的目标就是它），退 `origin/master`。"""
    for ref in ("master", "origin/master"):
        result = _run_git(["rev-parse", "--verify", "--quiet", ref], repo_root, check=False)
        if result.returncode == 0 and result.stdout.strip():
            return ref
    return None


def _rev_count(repo_root: Path, rev_range: str, pathspec: list[str]) -> int | None:
    """`git rev-list --count <range> [-- <pathspec>]`；失败返回 None（不返回 0）。"""
    args = ["rev-list", "--count", rev_range]
    if pathspec:
        args.extend(["--", *pathspec])
    result = _run_git(args, repo_root, check=False)
    if result.returncode != 0:
        return None
    text = result.stdout.strip()
    return int(text) if text.isdigit() else None


def _carrier_lag_counts(repo_root: Path, head: str | None) -> tuple[int | None, int | None]:
    """返回 `(HEAD 落后总提交数, 其中触碰 CLAUDE.md 的提交数)`。

    🔴 **用 git 提交计数，不用 mtime**（#338 预授权④，A9 教训）；也不用
    `git log -L`／`blame`——队列行号随上方增删漂移，那两者会静默给出另一
    行的历史。
    """
    if not head or set(head) == {"0"}:
        return None, None
    base = _master_ref(repo_root)
    if base is None:
        return None, None
    rev_range = f"{head}..{base}"
    return (
        _rev_count(repo_root, rev_range, []),
        _rev_count(repo_root, rev_range, [CLAUDE_MD_ROOT_REL]),
    )


def _resident_carriers(repo_root: Path) -> tuple[list[dict] | None, str | None]:
    """从计划任务反查常驻执行体：Action 路径落在 `<repo>/.claude/worktrees/<name>/`
    之下者，`<name>` 即执行体。返回 `([{name, tasks, registered, head}], None)`
    或 `(None, 失败原因)`。"""
    actions, reason = _query_scheduled_task_actions()
    if actions is None:
        return None, reason
    registered = {entry["path"]: entry for entry in _registered_worktrees(repo_root)}
    registered_lower = {path.lower(): entry for path, entry in registered.items()}
    prefix = _normalize_path_text(str(repo_root / WORKTREES_DIR_REL)) + "/"
    prefix_lower = prefix.lower()
    carriers: dict[str, dict] = {}
    for action in actions:
        raw = _normalize_path_text(f"{action['execute']} {action['arguments']}")
        index = raw.lower().find(prefix_lower)
        if index == -1:
            continue
        tail = raw[index + len(prefix):]
        name = tail.split("/", 1)[0].strip().strip('"').strip("'")
        if not name:
            continue
        entry = registered_lower.get((prefix + name).lower())
        carrier = carriers.setdefault(name, {
            "name": name, "tasks": [], "registered": entry is not None,
            "head": entry["head"] if entry else None,
        })
        if action["task"] and action["task"] not in carrier["tasks"]:
            carrier["tasks"].append(action["task"])
    return sorted(carriers.values(), key=lambda c: c["name"]), None


def _carrier_auto_restart_enabled(repo_root: Path) -> bool:
    """自动重启开关（#338 边界⑵：重启须可一键关闭）。

    🔴 **读不到、读错、值不认识，一律返回 False**——这是「重启生产服务」
    的开关，缺省必须是关的。
    """
    env_path = repo_root / ENV_REL
    if not env_path.exists():
        return False
    prefix = CARRIER_AUTO_RESTART_ENV_KEY + "="
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    for line in lines:
        line = line.strip()
        if line.startswith(prefix):
            value = line[len(prefix):].strip().strip('"').strip("'").lower()
            return value in CARRIER_AUTO_RESTART_TRUE_VALUES
    return False


def _carrier_worktree_path(repo_root: Path, name: str) -> Path:
    return repo_root / WORKTREES_DIR_REL / name


def _carrier_tracked_dirty(repo_root: Path, name: str) -> str | None:
    """执行体内**已跟踪文件**是否有未提交改动；有则返回首行摘要。

    未跟踪／被 ignore 的内容**不在此判**——它们不该阻止 ff，且 git 自己会
    在「ff 会覆盖某个未跟踪文件」时拒绝（见 `_ff_carrier` 的注释）。
    """
    # 🔴 **必须显式 `--untracked-files=no`**：`--porcelain=v1` 缺省**连未跟踪件
    # 一起报**（`??` 行）。2026-08-24 首次实跑当场撞上——执行体里那个唯一的
    # 未跟踪 wrapper `run-followup-dispatch-check.ps1` 把 ff 整个挡住了，而
    # 本函数的文档字符串明写「未跟踪／被 ignore 的内容**不在此判**」。
    # ⇒ **文档说的和命令做的是两回事，而两者都「看起来很确定」。** 同族＝
    # 「判据看起来很确定但错了」。所幸失败方向是保守的（停手不 ff），
    # 若判反了就会是「该停手时动了手」。
    result = _run_git(["status", "--porcelain=v1", "--untracked-files=no"],
                      _carrier_worktree_path(repo_root, name), check=False)
    if result.returncode != 0:
        return f"status 查询失败：{result.stdout.strip()[:120]}"
    first = result.stdout.strip().splitlines()
    return first[0].strip() if first else None


def _ff_carrier(repo_root: Path, carrier: dict) -> dict:
    """把一个常驻执行体 worktree `--ff-only` 对齐到 master。

    返回 `{outcome, detail, before, after, changed_paths}`，`outcome` ∈
    `aligned`（本来就齐）／`ffed`（本轮 ff 了）／`ahead`（有本地提交，停手）／
    `dirty`／`failed`／`unknown`。

    🔴 **绝不强推**（#338 边界⑴）：`ahead > 0` 一律停手告警——执行体上有
    本地提交意味着有人在那里直接改过东西，强 ff 会把它冲掉，而那正是
    `#68` 反复强调的「不在生产载体上造出第三种代码状态」。

    ⚠️ **不做每轮备份，这是刻意的**：`--ff-only` 若会覆盖某个未跟踪文件，
    **git 自己就会拒绝并非零退出**（"untracked working tree files would be
    overwritten by merge"），我们据此告警即可。每轮把 26 个 reports 文件复制
    一遍既无必要、又会自己制造一堆需要清理的目录。#267 那次事故的动作是
    `worktree remove`（真删），不是 ff——两者的风险不同，不该套同一套防护。
    """
    name = carrier["name"]
    wt = _carrier_worktree_path(repo_root, name)
    before = carrier.get("head")
    if not carrier.get("registered") or not before or set(before) == {"0"}:
        return {"outcome": "unknown", "detail": "不在注册项内或 HEAD 无效",
                "before": before, "after": None, "changed_paths": []}
    if not (wt / ".git").exists():
        return {"outcome": "unknown", "detail": "目录内无 .git 条目",
                "before": before, "after": None, "changed_paths": []}

    base = _master_ref(repo_root)
    if base is None:
        return {"outcome": "unknown", "detail": "master/origin/master 均不可解",
                "before": before, "after": None, "changed_paths": []}

    ahead = _rev_count(repo_root, f"{base}..{before}", [])
    if ahead is None:
        return {"outcome": "unknown", "detail": "ahead 计数取不到",
                "before": before, "after": None, "changed_paths": []}
    if ahead > 0:
        return {"outcome": "ahead", "detail": f"执行体领先 {ahead} 个提交，已停手不 ff",
                "before": before, "after": None, "changed_paths": []}

    behind = _rev_count(repo_root, f"{before}..{base}", [])
    if behind is None:
        return {"outcome": "unknown", "detail": "落后计数取不到",
                "before": before, "after": None, "changed_paths": []}
    if behind == 0:
        return {"outcome": "aligned", "detail": "已对齐", "before": before,
                "after": before, "changed_paths": []}

    dirty = _carrier_tracked_dirty(repo_root, name)
    if dirty:
        return {"outcome": "dirty", "detail": f"已跟踪文件有未提交改动（{dirty}），已停手不 ff",
                "before": before, "after": None, "changed_paths": []}

    merged = _run_git(["merge", "--ff-only", base], wt, check=False)
    if merged.returncode != 0:
        head_line = (merged.stdout or "").strip().splitlines()
        return {"outcome": "failed",
                "detail": f"ff 失败：{head_line[0] if head_line else '无输出'}",
                "before": before, "after": None, "changed_paths": []}

    after = _run_git(["rev-parse", "HEAD"], wt, check=False).stdout.strip()
    diff = _run_git(["diff", "--name-only", f"{before}..{after}"], repo_root, check=False)
    changed = [p.strip() for p in diff.stdout.splitlines() if p.strip()]
    return {"outcome": "ffed", "detail": f"已 ff {behind} 个提交",
            "before": before, "after": after, "changed_paths": changed}


def _restart_carrier(repo_root: Path, name: str) -> tuple[bool, str]:
    """调 `工具-执行体对齐重启.ps1 -RestartOnly` 重启并验活。

    🔴 **刻意不在本文件里再实现一遍那三个坑**（先杀父后杀子／验进程链
    `CreationTime`／验心跳戳刷新）——#338 明写「勿另写一套」。人工执行与
    机器执行走**同一个实现**，是这条纪律真正的兑现方式：两套实现迟早会
    分叉，而分叉不会有任何报错。

    🔴 退出码只认脚本自身 `exit` 的那个值（`subprocess` 直接拿到），
    **不经管道、不经 `cmd /c`**——`%ERRORLEVEL%` 在 cmd 解析期就被展开，
    读到的是命令还没跑时的值（OP-0819-F 实测读到 0、真值是 2）。
    """
    script = repo_root / RESIDENT_CARRIER_REALIGN_SCRIPT_REL
    if not script.is_file():
        return False, f"未找到 {RESIDENT_CARRIER_REALIGN_SCRIPT_REL}"
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", str(script), "-WorktreeName", name, "-RestartOnly"],
            capture_output=True, text=True, encoding="utf-8", timeout=600,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"调用失败：{type(exc).__name__}: {exc}"
    tail = [ln for ln in (result.stdout or "").splitlines() if ln.strip()][-1:]
    detail = tail[0].strip() if tail else "无输出"
    return result.returncode == 0, f"退出码 {result.returncode}：{detail}"


def _sync_resident_carriers(repo_root: Path, log: list[str]) -> None:
    """第 5 类：常驻执行体**持续同步**（ff 每轮做，重启按需）。

    与本项目既有告警的关键差别：**本函数会动手**（`--ff-only`），不只是
    报告。这是 #338 改版的核心——落后是持续过程，只有每轮都做的动作才治
    得住它。

    告警语义是**「有例外」**，不是「落后了」：ahead>0 停手／ff 失败／脏／
    已 ff 但需重启而自动重启关着。**正常路径（ff 成功且无需重启）不产生
    任何推送**，只在日志回显。
    """
    carriers, reason = _resident_carriers(repo_root)
    if carriers is None:
        # 🔴 三态里最要紧的一态：**未取到 ≠ 零执行体**。
        log.append(f"⚠ 常驻执行体名单**未取到**（{reason}）——本轮不做任何 ff，也不产生「零落后」结论。")
        return
    if not carriers:
        log.append("🚚 常驻执行体同步：计划任务查询成功，无任务指向 worktree（零执行体）。")
        return

    auto_restart = _carrier_auto_restart_enabled(repo_root)
    log.append(f"🚚 常驻执行体持续同步（{len(carriers)} 个；自动重启开关＝"
               f"{'ON' if auto_restart else 'OFF（缺省，重启走人工确认）'}）：")

    exceptions: dict[str, str] = {}
    for carrier in carriers:
        name = carrier["name"]
        tasks = "、".join(carrier["tasks"]) or "（无）"
        result = _ff_carrier(repo_root, carrier)
        outcome, detail = result["outcome"], result["detail"]

        if outcome == "aligned":
            log.append(f"    · {name}：已对齐（落后 0）／引用任务：{tasks}")
            continue
        if outcome in ("ahead", "dirty", "failed", "unknown"):
            log.append(f"    🔴 {name}：{detail}／引用任务：{tasks}")
            exceptions[name] = f"{detail}（引用任务：{tasks}）"
            continue

        # outcome == "ffed"
        hits = _touches_resident_service(set(result["changed_paths"]), repo_root)
        if not hits:
            log.append(f"    · {name}：{detail}，未触碰常驻服务代码路径 ⇒ 无需重启"
                       f"／引用任务：{tasks}")
            continue

        hit_text = "、".join(f"`{p}`（{src}）" for p, src in hits[:5])
        if len(hits) > 5:
            hit_text += f" 等 {len(hits)} 处"
        if not auto_restart:
            log.append(f"    🔴 {name}：{detail}，**触碰常驻服务代码路径 {len(hits)} 处，"
                       f"需人工重启**（自动重启开关 OFF）／{hit_text}")
            exceptions[name] = (f"{detail}，触碰常驻服务代码路径 {len(hits)} 处，"
                                f"**代码已新、进程仍旧** ⇒ 需人工重启验活；{hit_text}")
            continue

        ok, restart_detail = _restart_carrier(repo_root, name)
        if ok:
            log.append(f"    ✓ {name}：{detail}，触碰 {len(hits)} 处 ⇒ 已自动重启并验活（{restart_detail}）")
        else:
            log.append(f"    🔴 {name}：{detail}，触碰 {len(hits)} 处 ⇒ **自动重启失败**（{restart_detail}）")
            exceptions[name] = f"{detail}，自动重启失败（{restart_detail}）；{hit_text}"

    def render_alert(keys):
        lines = "\n".join(f"- `{key}`：{exceptions[key]}" for key in sorted(keys))
        return (
            f"🚚 落库sweep：{len(keys)} 个常驻执行体**同步有例外，需人介入**：\n{lines}\n"
            f"⇒ 处置：`powershell -NoProfile -File "
            f"\"{RESIDENT_CARRIER_REALIGN_SCRIPT_REL}\" -WorktreeName <名字> -RestartOnly`"
            "（只重启验活；需要连 ff 一起做时去掉 `-RestartOnly`，先 `-DryRun` 干跑）"
        )

    def render_resolved(keys):
        lines = "\n".join(f"- `{key}`（例外已消除，同步恢复正常）" for key in sorted(keys))
        return f"✅ 落库sweep：{len(keys)} 个此前告警过的常驻执行体已恢复：\n{lines}"

    _track_and_alert_standing_state(
        repo_root, "常驻执行体同步例外", RESIDENT_CARRIER_LAG_STATE_REL,
        # 🔴 key = worktree 名，**刻意不含任何会变的数值**（同子项 A 的理由）。
        set(exceptions), RESIDENT_CARRIER_LAG_ALERT_INTERVAL_HOURS,
        render_alert, render_resolved, log,
    )


def _edit_lock(repo_root: Path, action: str, extra: list[str] | None = None) -> subprocess.CompletedProcess:
    # 队列 #198(b)：`status` 子命令不接受 `--who`（无副作用查询，不需要
    # 身份）——传了会被 argparse 当"unrecognized arguments"直接拒绝（exit
    # code 2），故只在 acquire/release 这两个需要身份的动作上带 --who。
    args = [sys.executable, str(repo_root / EDIT_LOCK_SCRIPT_REL), action]
    if action != "status":
        args.extend(["--who", LOCK_WHO])
    if extra:
        args.extend(extra)
    return subprocess.run(args, cwd=repo_root, capture_output=True, text=True, encoding="utf-8")


def _edit_lock_is_actively_held(status_stdout: str) -> bool:
    """解析 `工具-共享文档编辑锁.py status` 的 stdout，判断锁当前是否被
    有效持有（队列 #198(b)）。该工具三种输出态中，只有"占用中且未陈旧"
    才含"（有效）"三字（见 `cmd_status`）——无锁态是"（无锁，可直接编辑）"，
    陈旧态是"已陈旧（可接管）"，均不含"（有效）"。陈旧锁本轮不必因此跳过
    ——后续 `_strike_off_rows` 自身的 acquire 调用会自动接管陈旧锁，探锁
    这一步只需要拦住"确实有人/有机器人正在编辑"这一种情形。"""
    return "（有效）" in status_stdout


def _abort_if_edit_lock_held(repo_root: Path, log: list[str]) -> None:
    """队列 #198(b)：起跑段编辑锁前置探测，须排在 `_check_preconditions`
    之后、任何 git 写动作之前——占用中直接跳过本轮、一个 git 动作都不做。

    现状（修复前）：`_process_normal_batch` 先 `git add` 再由
    `_strike_off_rows` 去 acquire 锁，锁占用时暂存区里已经是半成品；本函数
    把探测提到最前面，锁占用时连第一个 `git add` 都不会发生。"""
    result = _edit_lock(repo_root, "status")
    if _edit_lock_is_actively_held(result.stdout):
        raise SweepAbort(
            f"⚠ 起跑探测到共享编辑锁被有效占用中，跳过本轮，零 git 动作：{result.stdout.strip()}",
        )


def _replace_status_cell(raw_line: str, old_status_cell: str, new_status_cell: str) -> str:
    """只替换该行"状态"这一列的内容，其余原样保留（不重排空白、不动其他三列）。"""
    idx = raw_line.rfind("| " + old_status_cell + " |")
    if idx != -1:
        return raw_line[:idx] + "| " + new_status_cell + " |" + raw_line[idx + len("| " + old_status_cell + " |"):]
    # 空白格式不完全一致时退化为窄匹配，仍要求原样保留其余三列
    idx = raw_line.rfind(old_status_cell)
    if idx == -1:
        raise SweepAbort(f"✗ 无法在原始行中定位状态列文本，拒绝改写：{raw_line!r}", exit_code=1)
    return raw_line[:idx] + new_status_cell + raw_line[idx + len(old_status_cell):]


def _now_utc_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _straggler_status(now: str) -> str:
    """补销"遗留尾巴"批次时写入状态列的文案（队列 #328，2026-08-26 修）。

    🔴 **本函数的产出必须无法再被 `_classify_section_two_rows` 判为待处理**
    ——否则补销就不幂等：写完即再次满足触发条件，下一轮又补销一次，且因
    文案里带当前时刻，每一轮都是一条 diff 恰 1 行的纯噪音 commit。

    2026-08-26 实测事故：旧文案

        `**✅ 已完成**（sweep 自动补销遗留尾巴 <时刻> UTC，未发现对应待落库改动）`

    整句**不含任何句级分隔符**（`LEADING_SEGMENT_SEPARATORS` 里的
    "。"／"——"／"━━━"），`_leading_status_segment()` 因此把整句都当作
    "开头片段"；而句尾"未发现对应**待**落库改动"里的"待"字命中了
    `_classify_section_two_rows` 的待处理判据 ⇒ 触发条件恒真、永不收敛。
    量级：08-26 本地 15:00–20:52 不到 6 小时 33 个提交里，18 个是
    `B-0825_A23_354env锚定收拢apply` 与 `B-0825_A26_340签认落地_EQ17基准100`
    两行被反复重写（每轮各 1 条）＋ 随之被拖着重跑的文档台账。

    修法两重保险（缺一都会在对方被后人改动时重新破功）：
    ⑴ 紧跟完成标记落一个句级分隔符"。"，把开头片段收窄到 `✅ 已完成`；
    ⑵ 说明文字里把"待落库"改写成不含"待"字的"未落库"。
    时刻**保留**（落库溯源需要它）——修法⑴ 之后它已在开头片段之外，不
    再参与判定，不构成非幂等的来源。

    末尾的自检不是装饰：它把"文案与判据必须保持一致"这条隐性契约变成
    改文案当场就会炸的显式失败，而不是等下一次上线后靠日志噪音发现。
    往返回归见 `StragglerStatusIdempotenceTests`。
    """
    # `now` 由 `_now_utc_str()` 提供，其格式已自带 " UTC" 后缀——此处不得再补
    # 一个，否则写出 "… 14:15 UTC UTC …"（2026-08-26 首轮实测踩到）。
    status = (
        f"**✅ 已完成**。（sweep 自动补销遗留尾巴 {now}，"
        "未发现对应的未落库改动）"
    )
    probe = [{"batch_id": "_straggler_status_selfcheck", "status_cell": status}]
    pending, ambiguous = _classify_section_two_rows(probe)
    if pending or ambiguous:
        raise SweepAbort(
            "✗ 补销状态文案自身仍会被判为待处理/模糊，写下去必然每轮重写"
            f"（队列 #328 的非幂等事故）——拒绝执行：{status!r}",
        )
    return status


def _iter_queue_paths() -> list[str]:
    """队列 #315：遍历两份物理队列文件的仓库相对路径——机制环境／业务
    场景，替代拆分前"只有一份队列文件"的假设。"""
    return [QUEUE_MECHANISM_PATH_REL, QUEUE_BUSINESS_PATH_REL]


def _read_queue(repo_root: Path, queue_path: str) -> str:
    """队列 #315：文件不存在时返回空串而非抛错——两份物理文件里若有一份
    尚不存在（如测试夹具只搭了单文件场景，或迁移过渡期个别环境未同步）
    ，下游 `_parse_section_two`/`_parse_section_one` 对空文本天然返回零行，
    等价于"这份文件当前没有需要处理的内容"，不应让 sweep 整轮崩溃。"""
    try:
        with open(repo_root / queue_path, "r", encoding="utf-8", newline="") as f:
            return f.read()
    except FileNotFoundError:
        # 非静默降级（同 #302/#308 一贯纪律）：留痕但不 abort——测试夹具与
        # 迁移过渡期的合法单文件场景需要这条路径可用，真实生产环境下两份
        # 文件长期缺失才是异常，留痕即可让值周巡检/日志复核发现。
        print(f"⚠ {queue_path} 不存在，本轮按空内容处理（若非预期请核实文件是否遗失）。")
        return ""


def _write_queue(repo_root: Path, queue_path: str, text: str) -> None:
    with open(repo_root / queue_path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def _strike_off_rows(
    repo_root: Path, rows: list[dict], new_status_fn, lock_note: str, dry_run: bool,
) -> bool:
    """对给定行批量替换状态列并写回队列文件；调用方负责 add/commit。返回是否真的改了内容。

    队列 #315：`rows` 须全部来自同一份物理队列文件（`row["queue_path"]`
    一致）——调用方（本文件内均按物理文件分组处理批次）保证这一点，这里
    仅做断言，不静默兼容跨文件混合，避免"写对了一半、另一半找不到行"这
    类难排查的部分失败。
    """
    if dry_run:
        for row in rows:
            print(f"  [dry-run] 将标记 {row['batch_id']} → {new_status_fn(row)}")
        return True

    queue_paths = {row["queue_path"] for row in rows}
    if len(queue_paths) > 1:
        raise SweepAbort(
            f"✗ _strike_off_rows 收到跨物理文件混合的行（{queue_paths}），"
            "调用方须按 queue_path 分组后分别调用——拒绝执行，避免部分写入。"
        )
    queue_path = next(iter(queue_paths))

    lock = _edit_lock(repo_root, "acquire", ["--note", lock_note])
    if lock.returncode != 0:
        raise SweepAbort(f"⚠ 编辑锁占用中，跳过本轮：{lock.stdout.strip()}")
    try:
        text = _read_queue(repo_root, queue_path)
        for row in rows:
            new_line = _replace_status_cell(row["raw_line"], row["status_cell"], new_status_fn(row))
            if row["raw_line"] not in text:
                raise SweepAbort(
                    f"✗ 队列文件内容已变化，找不到批次 {row['batch_id']} 的原始行——"
                    "可能被并发编辑，跳过本轮不强写。",
                )
            text = text.replace(row["raw_line"], new_line, 1)
        _write_queue(repo_root, queue_path, text)
        return True
    finally:
        _edit_lock(repo_root, "release")


def _process_normal_batch(repo_root: Path, row: dict, resolved_files: list[str], dry_run: bool, log: list[str]) -> None:
    """队列 #288（2026-08-06 起）：只负责把批次内容落成本地提交，不再自己
    校验快进或推送——是否能与 origin/master 对齐、何时推送，统一交给批次
    提交阶段结束后调用一次的 `_reconcile_with_origin_and_push`（main() 接
    线顺序），原因见该函数与文件头部本节说明。"""
    batch_id = row["batch_id"]
    if dry_run:
        print(f"[dry-run] 批次 {batch_id}：会 git add {resolved_files}，"
              f"提交信息「{_extract_commit_message(row['message_cell'])}」，标记销行后本地提交。")
        log.append(f"[dry-run] {batch_id} 待落库：{resolved_files}")
        return

    _run_git(["add", "--", *resolved_files], repo_root)

    new_status = f"**✅ 已完成**（sweep 自动落库 {_now_utc_str()}）"
    _strike_off_rows(repo_root, [row], lambda r: new_status, f"sweep 落库 {batch_id}", dry_run=False)
    _run_git(["add", "--", row["queue_path"]], repo_root)

    message = _extract_commit_message(row["message_cell"])
    _run_git(["commit", "-m", message], repo_root)
    sha = _run_git(["rev-parse", "--short", "HEAD"], repo_root).stdout.strip()
    log.append(f"✓ 批次 {batch_id} 已本地提交（{sha}），等待本轮末尾统一对齐并推送。")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="只打印计划动作，不 add/commit/push/改队列")
    parser.add_argument("--repo-root", default=None, help="仅测试用：覆盖主工作区路径断言")
    parser.add_argument(
        "--check-dirty-in-pending-batch", nargs="+", metavar="PATH", default=None,
        help="#101①：只读核验给定路径（相对仓库根）是否命中§二待处理批次声明，"
             "不做任何写操作、不跑 sweep 主流程。每个路径输出一行 "
             "'MATCH <batch_id> <path>' 或 'NOMATCH <path>'，供"
             "工具-主工作区安全同步.ps1 在建议 git checkout -- 前调用。")
    parser.add_argument(
        "--check-stale-pending-rows", action="store_true",
        help="#302：只读核验 §一 状态列开头片段含'待'的行是否已被近期 commit "
             "顺带做掉（批量派活前核对清单），不做任何写操作、不跑 sweep "
             "主流程。每行输出 'STALE_SUSPECT <row_id> primary=<Y/N> "
             "secondary=<Y/N> primary_commits=<...> secondary_commits=<...>' "
             "或 'PENDING_CLEAN <row_id>'。")
    parser.add_argument(
        "--stale-lookback-days", type=int, default=STALE_ROW_LOOKBACK_DAYS,
        help="#302：--check-stale-pending-rows 的近期 commit 扫描窗口天数，默认 %(default)s。")
    parser.add_argument(
        "--ack-stale-change", default=None, metavar="CHANGE_NAME",
        help="队列 #308 子项 D2：记录一次对指定 openspec 变更包「疑似遗忘归档」"
             "候选的人工确认（须同时提供 --note），只写确认状态文件，不做任何"
             "写操作、不跑 sweep 主流程。指纹（done/total）未变期间不再告警，"
             "tasks.md 有新勾选变化后自动失效。")
    parser.add_argument(
        "--note", default="", help="--ack-stale-change 配套：本次判定依据摘录，必填。")
    args = parser.parse_args()

    repo_root = _resolve_repo_root(args.repo_root)

    if args.ack_stale_change is not None:
        # 只读写确认状态文件：不碰队列、不动 git 状态，独立于下方主流程。
        return cmd_ack_stale_change(repo_root, args.ack_stale_change, args.note)

    if args.check_dirty_in_pending_batch is not None:
        # 只读检查模式：不写日志、不碰队列、不动 git 状态，独立于下方主流程。
        results = _check_dirty_paths_against_pending_batches(
            repo_root, args.check_dirty_in_pending_batch)
        for path, batch_id in results:
            if batch_id:
                print(f"MATCH\t{batch_id}\t{path}")
            else:
                print(f"NOMATCH\t{path}")
        return 0

    if args.check_stale_pending_rows:
        # 只读检查模式：不写日志、不碰队列、不动 git 状态，独立于下方主流程。
        for result in _find_stale_pending_rows(repo_root, days=args.stale_lookback_days):
            if result["primary"] or result["secondary"]:
                print(
                    f"STALE_SUSPECT\t{result['row_id']}\t"
                    f"primary={'Y' if result['primary'] else 'N'}\t"
                    f"secondary={'Y' if result['secondary'] else 'N'}\t"
                    f"primary_commits={','.join(result['primary_commits'])}\t"
                    f"secondary_commits={','.join(result['secondary_commits'])}"
                )
            else:
                print(f"PENDING_CLEAN\t{result['row_id']}")
        return 0

    start_line = f"=== sweep 运行 {_now_utc_str()} ==="
    log: list[str] = [start_line]
    # 队列 #222：启动即写日志首行——不等收尾统一 flush，避免"启动后立刻
    # 崩溃"与"压根没启动"在日志上表现完全相同（#121(b) 遗留未做项；判据
    # 基础设施，见 #96 清单）。此后各退出路径改用 `_flush_remaining_log`，
    # 只落盘首行之后新增的内容，不重复写入这一行。
    if not args.dry_run:
        _flush_log(repo_root, [start_line], dry_run=False)

    try:
        _heal_stale_index_lock(repo_root, log)
        _check_preconditions(repo_root, production=args.repo_root is None)
        # 队列 #192/#194/#198/#219/#235 起跑段写死顺序（勿自行调整，详见各函数 docstring）：
        # ① #198(b) 编辑锁前置探测（任何 git 写动作之前）
        _abort_if_edit_lock_held(repo_root, log)
        # ② #194 无条件补推未推送提交
        _push_any_unpushed_commits(repo_root, log, dry_run=args.dry_run)
        # ③ #192-A flush 锁忙推迟暂存 + #219 决策提醒第二载体 + #235/#188 定时
        #   任务真身↔镜像核对（均须在 sweep 自己取锁窗口之外，此处批次处理
        #   尚未开始，安全；#235/#188 的核对若检出差异会当场本地提交，须排在
        #   下方 dirty_paths 捕获之前，使更正后的镜像文件不留作孤儿脏文件）；
        #   dry-run 不做真实动作，避免副作用。
        if not args.dry_run:
            _flush_pending_lock_appends(repo_root, log)
            _run_decision_reminder_second_carrier(repo_root, log)
            _run_scheduled_task_mirror_sync(repo_root, log)
        # ④ 队列 #288（2026-08-06 起）：不再在批次处理之前尝试同步/分叉早检
        # ——`_sync_master_if_behind_origin` 的 `git merge --ff-only` 要求工作区
        # 干净，而"§二 待 commit 批次的存在本身就意味着工作区必然脏"是 sweep
        # 自身的设计前提，两者直接冲突，是本次故障的根因（见文件头部本节
        # 说明）。改为：先把批次提交到本地（工作区因此变干净），再统一对齐
        # origin/master 并推送一次——见本函数末尾对 `_reconcile_with_origin_
        # and_push` 的调用。

        # 队列 #315：批次分散在两份物理文件里（机制环境／业务场景），逐份
        # 文件独立完成"解析→隔离判定→落库→补销尾巴"整套流程后再进入下一
        # 份——`dirty_paths` 在每份文件处理前重新取（上一份文件的批次落库
        # 会改变工作区状态，须用最新状态判定这一份文件的孤儿/批次关系）；
        # ledger 重跑与最终的对齐推送只在两份文件都处理完后统一做一次。
        all_pending_rows: list[dict] = []
        all_normal_rows: list[tuple[dict, list[str]]] = []
        all_straggler_ids: list[str] = []
        touched_paths: set[str] = set()

        for queue_path in _iter_queue_paths():
            queue_text = _read_queue(repo_root, queue_path)
            rows = _parse_section_two(queue_text, queue_path)
            pending_rows, ambiguous_status_rows = _classify_section_two_rows(rows)
            all_pending_rows.extend(pending_rows)
            for row in ambiguous_status_rows:
                log.append(
                    f"⚠ 状态列模糊（既不含✅也不含待字样），未纳入本轮处理，人工核查："
                    f"[{queue_path}] {row['batch_id']} | {row['status_cell']}"
                )

            # 队列 #238：批次隔离——即便本轮无待处理批次，脏路径也可能全部是
            # 孤儿（没有任何批次登记），仍需纳入 #236(2) 孤儿告警的追踪范围，
            # 故这一步不依赖 `pending_rows` 是否非空。
            dirty_paths = _status_paths(repo_root)
            clean_rows, row_resolution, orphan_paths = _partition_pending_rows_by_batch_isolation(
                pending_rows, dirty_paths, log,
            )
            if not args.dry_run:
                _track_and_alert_orphan_paths(repo_root, orphan_paths, log)

            straggler_rows = []
            normal_rows = []
            for row in clean_rows:
                resolved, not_dirty, ambiguous = row_resolution[row["batch_id"]]
                if resolved:
                    normal_rows.append((row, resolved))
                elif not_dirty:
                    straggler_rows.append(row)
                else:
                    # 队列 #328②（2026-08-26）：resolved 与 not_dirty 同时为空
                    # ⟺ 文件清单列里**一个反引号片段都没有**（进了 clean_rows
                    # 就说明 ambiguous 为空，而每个片段必落入三者之一）。旧实现
                    # 这里没有 else 分支，这类行既不落库也不补销、且**一行日志
                    # 都不留**，就此永久隐身。
                    # 实测：`B-0825_巡逻2_404_405陈忱回件拆件_质量部9转态` 登记
                    # 时把路径写成了裸文本（未加反引号），"待处理"超 24 小时，
                    # 期间每轮 sweep 都读到它、每轮都无声跳过。
                    # ⚠ 这里**只报不动**：文件清单解析不出来就无从判断它是"内容
                    # 早已落库、只差销行"还是"真有改动尚未提交"，自动补销会把
                    # 后者连同真实待落库内容一起销掉。登记格式错误由人订正
                    # （给片段补上反引号），sweep 的职责到"喊出来"为止。
                    log.append(
                        f"⚠ 批次 {row['batch_id']} 的文件清单列解析不出任何反引号"
                        f"片段，既无法落库也不能安全补销，本轮跳过（登记格式错误："
                        f"路径须用反引号标出，订正后下一轮自动生效）："
                        f"[{queue_path}] {row['files_cell'][:120]}"
                    )

            for row, resolved in normal_rows:
                _process_normal_batch(repo_root, row, resolved, args.dry_run, log)
                touched_paths.update(resolved)

            if straggler_rows:
                ids = "/".join(r["batch_id"] for r in straggler_rows)
                note = f"✓ 补销遗留尾巴批次 {ids}"
                if args.dry_run:
                    print(f"[dry-run] {note}")
                    log.append(f"[dry-run] {note}")
                else:
                    # 队列 #328：文案与幂等自检统一收进 `_straggler_status()`，
                    # 不在此处内联拼串——内联正是上一版把"待落库"写进状态、
                    # 使补销每轮重触发的来路。
                    new_status = _straggler_status(_now_utc_str())
                    _strike_off_rows(repo_root, straggler_rows, lambda r: new_status,
                                      f"sweep 补销尾巴 {ids}", dry_run=False)
                    _run_git(["add", "--", queue_path], repo_root)
                    _run_git(["commit", "-m", f"docs(队列): sweep 补销遗留尾巴批次 {ids}"], repo_root)
                    log.append(note)  # 队列 #288：只本地提交，不在此处单独推送

            all_normal_rows.extend(normal_rows)
            all_straggler_ids.extend(r["batch_id"] for r in straggler_rows)

        if not all_pending_rows:
            # 队列 #288：不再在此处提前 return——即便本轮无批次可提交，末尾
            # 的统一对齐步骤仍要跑一次（纯落后时把本地 master 追上 origin
            # 这一常规维护动作，不依赖"本轮有没有内容要提交"）。
            log.append("§二无待处理批次，本轮空转。")

        processed_any = bool(all_normal_rows) or bool(all_straggler_ids)
        if processed_any and not args.dry_run:
            # 队列 #257：先记数据（不告警），再重跑台账——两者均只在真实
            # 落库时才有意义，dry-run 不产生持久化副作用。
            landed_batch_ids = [r["batch_id"] for r, _ in all_normal_rows] + all_straggler_ids
            _record_batch_landing_count(repo_root, landed_batch_ids)
            _rerun_ledger(repo_root, log)
        elif not processed_any and all_pending_rows:
            log.append("本轮无批次可落库（全部暂缓或声明片段当前均无对应脏改动）。")

        # 队列 #288：批次提交（含遗留尾巴、台账重跑）全部完成、工作区已干净
        # 之后，统一对齐 origin/master 并推送一次——纯落后/纯领先/已分叉三种
        # 关系的分派与失败处理见 `_reconcile_with_origin_and_push` 自身
        # docstring；对齐失败（含 rebase 冲突/推送失败）会抛出 SweepAbort，
        # 由外层 except 统一处理，下面的部署提示不会执行（只在真正推送
        # 成功后才提示，语义与此前一致）。
        _reconcile_with_origin_and_push(repo_root, log, dry_run=args.dry_run)

        # #198(c)：批次落库之后，检查本轮实际 add 过的路径是否命中常驻服务——
        # 纯提示，不影响下方的正常返回。
        if touched_paths and not args.dry_run:
            resident_hits = _touches_resident_service(touched_paths, repo_root)
            if resident_hits:
                _announce_resident_service_deployment_hint(repo_root, resident_hits, log)
            # 队列 #229：发布收口第②关——命中已部署场景却未见部署留痕，纯
            # 提示，不影响下方的正常返回。
            missing_trace_hits = _find_missing_deployment_trace(touched_paths)
            if missing_trace_hits:
                _announce_missing_deployment_trace(repo_root, missing_trace_hits, log)

        # 队列 #298：M1/M2 openspec 覆盖/滞留检测——检测对象是仓库整体
        # openspec 状态，与本轮是否有批次落库无关，故不依赖 touched_paths，
        # 每轮真跑（非 dry-run）都检查一次；告警本身按 key 做 24 小时节流
        # （见 `_announce_scenario_spec_coverage_gaps`/`_announce_stale_
        # in_flight_changes`），不会逐轮刷屏。
        if not args.dry_run:
            spec_gaps = _find_scenario_spec_coverage_gaps(repo_root)
            if spec_gaps:
                _announce_scenario_spec_coverage_gaps(repo_root, spec_gaps, log)
            undetermined_packages = _find_platform_packages_without_spec_mention(repo_root)
            if undetermined_packages:
                log.append(
                    "🟡 以下平台底座包在 openspec/specs/ 内容里零提及包名（弱信号，"
                    "只列不报，是否需要 capability 待人工判断）："
                    + "、".join(f"`{p}`" for p in undetermined_packages)
                )
            stale_changes = _find_stale_in_flight_changes(repo_root)
            if stale_changes:
                _announce_stale_in_flight_changes(repo_root, stale_changes, log)

            # 队列 §一 #338（2026-08-23，OP-0823-G）：第 4／第 5 类常驻状态
            # 告警——必载载体健康度。与 #298 那两类同理，检测对象是仓库/本机
            # 的整体状态，**与本轮是否有批次落库无关**，故不依赖 touched_paths。
            # 🔴 两者都**每轮回显**，即使零超限/零落后：上线当天预计零告警，
            # 而「建成 9 天从未发出过一条消息」是本项目已经吃过的亏。
            _check_claude_md_carrier_size(repo_root, log)
            # 🔴 本行会**动手 ff**，不只是报告——#338 改版：落后是持续过程，
            # 只有每轮都做的动作才治得住它。重启按需、且缺省走人工确认。
            _sync_resident_carriers(repo_root, log)

        _flush_remaining_log(repo_root, log, args.dry_run)
        print("\n".join(log))
        return 0

    except SweepAbort as exc:
        log.append(str(exc))
        if exc.is_fork and not args.dry_run:
            _handle_fork_detected(repo_root, log)
        _flush_remaining_log(repo_root, log, args.dry_run)
        print("\n".join(log))
        return exc.exit_code

    except Exception as exc:  # noqa: BLE001 —— 队列 #198(a) 通用异常兜底
        # main() 此前只有 `except SweepAbort`，任何其它异常（子进程异常/
        # 编码错误/FileNotFoundError 等）会直接冒泡，_flush_log 根本没机会
        # 执行——sweep-commit.log 零新增行，与"任务根本没启动"外观完全相同
        # （#96 清单 ⑦判据据此失效）。本层兜底后，日志零新增行只剩一个
        # 含义："任务根本没启动"；"跑了但崩了"改为走这里，有日志+告警+
        # 独立退出码，判据恢复单义（见 #198(a) 验收物）。
        tb_tail = traceback.format_exc().strip().splitlines()[-6:]
        log.append(f"✗ 未预期异常（{_now_utc_str()}）：{type(exc).__name__}: {exc}")
        log.extend(f"    {line}" for line in tb_tail)
        if not args.dry_run:
            webhook_url = _load_webhook_url(repo_root)
            if webhook_url is None:
                log.append(f"⚠ 未在 .env 找到 {WECOM_WEBHOOK_ENV_KEY}，跳过未预期异常告警推送（仅留痕日志）。")
            else:
                try:
                    _send_wecom_markdown(
                        webhook_url,
                        f"🔱 落库sweep 遇到未预期异常：{type(exc).__name__}: {exc}\n"
                        "详见 reports/sweep-commit.log。",
                    )
                    log.append("✓ 未预期异常告警已推送。")
                except Exception as send_exc:  # noqa: BLE001 —— 告警失败不应影响退出码
                    log.append(f"⚠ 未预期异常告警推送失败（不影响本轮退出码）：{send_exc}")
        try:
            _flush_remaining_log(repo_root, log, args.dry_run)
        except Exception:  # noqa: BLE001 —— 日志落盘本身失败也不应掩盖原始异常的退出码
            pass
        print("\n".join(log))
        return UNEXPECTED_EXIT_CODE


def _rerun_ledger(repo_root: Path, log: list[str]) -> None:
    """队列 #288（2026-08-06 起）：只负责生成台账并按需本地提交，不再自己
    校验快进或推送——原因同 `_process_normal_batch`，统一交给
    `_reconcile_with_origin_and_push`。"""
    result = subprocess.run(
        [sys.executable, str(repo_root / LEDGER_SCRIPT_REL)],
        cwd=repo_root, capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode != 0:
        log.append(f"⚠ 台账重跑失败（不影响已落库批次）：{result.stderr.strip()}")
        return
    changed = _run_git(["status", "--porcelain=v1", "--", LEDGER_OUTPUT_REL], repo_root).stdout.strip()
    if not changed:
        log.append("台账重跑：内容无变化，不产生新 commit。")
        return
    _run_git(["add", "--", LEDGER_OUTPUT_REL], repo_root)
    _run_git(["commit", "-m", "docs(队列): 收工重跑文档台账（sweep 自动）"], repo_root)
    log.append("✓ 台账已重跑并本地提交，等待本轮末尾统一对齐并推送。")


def _flush_log(repo_root: Path, log: list[str], dry_run: bool) -> None:
    if dry_run:
        return
    if not log:
        return
    log_path = repo_root / LOG_REL
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(log) + "\n\n")


def _flush_remaining_log(repo_root: Path, log: list[str], dry_run: bool) -> None:
    """把本轮 log 中"启动首行之后"新增的部分落盘（队列 #222）——首行已在
    main() 起跑时单独 `_flush_log` 过一次，各退出路径改调本函数而非直接
    调 `_flush_log(repo_root, log, ...)`，避免同一行被重复写入日志文件。"""
    _flush_log(repo_root, log[1:], dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
