---
title: "验收小结 · wecom-aibot-channel 8.5（真实群运行观察）"
created: 2026-09-12
status: ⏳ 待签字（可签字态；不代签、不转常驻）
用途: 对 openspec/changes/wecom-aibot-channel tasks.md 8.5 的观察期逐条取数核验，产出供 Shao Peishen 签字的验收小结
配套: 1-转型规划/0-全景路线图/派单件-【CC】wecom8.5验收小结-2026-09-12.md（派单）；openspec/changes/wecom-aibot-channel/proposal.md（晋档条件）；openspec/changes/wecom-aibot-channel/tasks.md（8.5／9.5）
派出线: Cowork 环境总线 OP-0912-E（批 B-0912_第二波两泳道）；本件由 CC 无头泳道 OP-0912-M 产出
---

# 验收小结 · `wecom-aibot-channel` 8.5 真实群运行观察

> **结论一句**：观察期 **预期 7 天／实际 30 天 18 小时（2026-08-13 00:00 → 2026-09-12 18:5x 本地）**，期间 **0 误归档、0 归档损坏、0 漏推送（应推 28 封／实发 27 封＋1 封已批准待人工发）**；但 **「连续 7 天不中断」从未达成**（最长连续无中断 2.49 天，仍在延续）、**audit hash-chain 窗口内 269 处断点**（全部归因于跨进程并发写分叉、非篡改；修复 `#564` 已成分支、未合入未上线）。**三条晋档判据两条实测通过、一条（audit 全程可查）部分通过**。是否据此转常驻，由 Shao Peishen 在 §五 签字区裁。

## 〇、口径来源与取数手段（先读这段再看表）

- **判据原文**：`proposal.md`「验收与晋档条件」第 3 条＝「真实群跑一周无事故（无误归档、无漏推送、audit 全程留痕可查）」；`tasks.md` 8.5＝「真实群运行满一周，观察无误归档/无漏推送/audit 全程可查，产出验收小结供签字批准转常驻」。本件**不重新定义标准**，只把这三句拆成 §一 的核验项。
- **观察时钟**：`tasks.md` 顶部声明基准日 2026-08-13（Shao Peishen 2026-08-13 拍板「不必等 `.51`、在当前开发环境起算」，队列 §四 #62 选 (a)）；本件窗口取 **2026-08-13 00:00 本地（UTC+8）→ 2026-09-12 18:5x 本地**。
- **数据源（只读，未改任何实现代码、未重启、未发消息）**：
  1. 权威审计 `5-平台底座/wecom-aibot-service/reports/wecom_aibot_audit.jsonl`（6657 行，首行 2026-07-18T11:51Z、末行 2026-09-12T10:40Z；窗口内 4785 行）。运行中的服务进程（PID 6332，2026-09-11 21:22 起，执行体 `.claude/worktrees/wecom-service-home` @ `735bc74`）经 `resolve_audit_path` 写的正是这一份（末行 10:40Z ＝ 本地 18:40，与该 worktree `reports/aibot_liveness.json` 的 `alive_at` 同分钟，两处互证）。
  2. 服务包装日志 `.claude/worktrees/wecom-service-home/5-平台底座/wecom-aibot-service/reports/service-dev-2026MMDD.log`（进程启动／退出／退避）。
  3. 归档产物 `7-外部文档/<部门>/`（逐条 `Path.exists()`）；两份队列真身（归档文件名子串核对）。
  4. 跟进信 README（只经 `工具-跟进信README查询.py --digest／--row`，未直读）。
  5. 计划任务：`Get-ScheduledTask`（`ZhuopinAibotDevListener` Running，触发器＝Logon＋Boot；`ZhuopinFollowupDispatchDaily` 周一至周五 09:30）。
- **核验脚本**：全部为一次性只读 Python（`json` 逐行解析 audit → 按 `action` 计数／差集／时序；hash-chain 用 `zhuopin_platform.audit.AuditLogger.verify_chain()` ＋ `JsonlSink.find_prev_hash_forks()`，断点归因另用 `hashlib.sha256(行原始字节+b"\n")` 逐行重算并回查 `prev_hash` 指向哪一物理行）。脚本未入库（临时目录 `%TEMP%\wecom85\analyze*.py`）；本件每个数字旁都写了它是怎么算出来的，可按同法复算。

## 一、核验表（每条一行：项／判据／实测值／手段／通过与否）

| # | 核验项 | 判据（原文口径） | 实测值（窗口 2026-08-13 → 09-12） | 手段 | 通过 |
|---|---|---|---|---|---|
| 1 | 无误归档 · 归档动作落地 | 场景② 收到的专员消息／文件 100% 落 `7-外部文档/<部门>/`，零遗漏 | `archived` **55** 件（陈忱 20／唐燕萍 14／姚祖怡 13／陈承 IT 5／李姣龙 1／ShaoPeiShen 自发 2）；**55/55 文件在磁盘**（迁库前 OneDrive 路径按 2026-08-26 迁移映射到 `C:/Dev/zhuopin-ai` 后逐条 `exists()`）；`archive_corruption_detected` **0** | audit `action=archived` 逐条取 `decision.archived_path` 核磁盘 | ✅ |
| 2 | 无误归档 · 部门映射 | 未命中映射一律 fail-closed 归「待分拣」，不猜部门 | `mapping_unmatched` **2**，均为 `sender=ShaoPeiShen`（决策人自发消息，映射表本就不含他；两件落 `7-外部文档/待分拣/`，符合 D7 设计） | audit `mapping_unmatched` ＋ 对应 `archived.decision.department` | ✅ |
| 3 | 无误归档 · 归档↔队列对账 | 每件归档在队列 §一 有「待领」行 | 55 件归档文件名在两份队列真身里命中 **54**；差集 **1**＝`待分拣-ShaoPeiShen-回复-2026-08-26-文本反馈-565bedf4….md`，对应 audit `queue_append_skipped{reason:sender_is_paul}`（决策人自发不立行，设计如此）。锁忙推迟 `queue_append_deferred_lock_busy` 10 次 → `queue_append_pending_flushed` 12 次，无滞留 | 归档文件名子串 ∈ `跨桌任务队列*.md` 全文；audit `queue_append*` 计数 | ✅ |
| 4 | 无误归档 · 入站失败件 | 失败不得静默；须回执并可追 | `message_dispatch_failed` **10**（08-26 13:19 唐燕萍附件 1 次；09-10 09:21–10:15 陈忱附件 9 次，`MediaTransferError: download_inbound 重试 3 次仍失败 TimeoutError`），每次均发 `media_resend_notice_sent`（9 次）；**两批全部重发后落档**：唐燕萍附件 08-26 13:55 `archived`、陈忱 3 个 zip 09-10 13:39 `archived`（服务 13:31 重启后）。根因已立行：`#416`⑴／`#545`（内层 SDK `request_timeout` 10 s 未透传，`#545` 修复在分支 `claude/op0910j…` 待 ff） | audit 时序对读（§三 抽样 D 附行号） | ✅（fail-closed 成立；根因修复未上线，见 §五 Q3） |
| 5 | 无漏推送 · 应推 vs 实推 | 已批准（`🆕 待发`）的跟进信全部送达 | `followup_approved` **29** 次＝**28 封**（财务部#14 08-22 双批准）；`followup_delivered` **27**（26 封正文＋1 封补件）。差集 **1 封＝质量部#14**（09-11 15:43 批准，尚 `🆕 待发`；他 09-11 答 1a「明早手动发」，`#557` 追记；发信任务周六不跑，下一自动轮 09-14 09:30）。**漏推 0** | `followup_approved.row_match_topic` ↔ `followup_delivered.data_sources.md` 逐封对；README `--digest` 现取 `🆕 待发×2`（质量部#14、财务部#18） | ✅ |
| 6 | 无漏推送 · 发送失败件 | 失败须留痕、须最终送达 | `followup_delivery_failed` **2**，同一封（采购部#19，08-27 17:02／17:14，`Reply ack timeout 5.0s`，超长信）→ 08-28 00:31 以「-推送摘要」降级版送达（`followup_delivered`＋cc＋群 cc＋回填＋commit 全链）；`OP-0828-B` 长度守卫即由此案立 | audit 时序（§三 抽样 E） | ✅ |
| 7 | 无漏推送 · 回填与落库 | 送达后 README 状态列回填 `✅ 已推送` 并 commit | `followup_backfilled` **26**／`followup_backfill_committed` 20／`followup_backfill_commit_failed` **6**（4 次 github 不可达、1 次 push 非 ff 冲突「已回滚保留本地提交」、1 次 `index.lock`）——6 封的 README 状态现均已在 `📥 已回件并回灌`／`✅ 无需回复` 后续态（`--digest` 现取），即回填内容未丢、仅当时 push 未成。**1 封（采购部#21，08-31 21:46）`followup_delivered` 后主 audit 无 `followup_backfilled`**，README 现为 `📥 已回件并回灌 2026-09-07`（后续人工推进过），疑落入 `#559` 所述第二份孤儿 audit 或脚本发送后中断，本件未深查 | audit 计数＋README `--digest` | ⚠️ 部分（送达无漏；回填留痕 1 封缺口） |
| 8 | audit 全程可查 · 事件链完整 | 任取事件可从入口追到落盘，附标识 | 抽样 **5 条**（§三）：入站 docx 归档／出站跟进信全链（approved→delivered→backfilled→committed→cc→群 cc）／断线自愈（预算耗尽→包装层第 2、3 次重启→重连→`gap_alert_sent`）／入站失败 fail-closed→重发落档／超长信降级；每条附 audit 行号 `L####`、`media_id`／`reqId`／归档文件名／git commit | `analyze5.py` 按时间窗切片打印 | ✅ |
| 9 | audit 全程可查 · hash-chain 防篡改 | `verify_chain()` 应 ok | **ok=False**：全量 **340** 处断点、窗口内 **269**；`find_prev_hash_forks()` 210 对相邻同 `prev_hash`。**归因：269/269 断点的 `prev_hash` 都能在其前 500 行内找到对应真实行**（＝多进程各自缓存链尾的分叉形态），**0 处无法归因（即无篡改／丢行迹象）**；断点行 action 分布 `disconnected` 223／`outbox_relay_scan_failed` 33／其它 13，即 SDK 回调线程与主循环、定时任务子进程并发写同一文件所致。修复 `#564`（`JsonlSink` 跨进程文件锁＋链尾现读）commit `59b54f7` 在分支 `claude/op0912a-audit-hash-race-564`，**已 push、未 ff、未上线**（运行中执行体 @ `735bc74` 不含） | `AuditLogger.verify_chain()`＋`find_prev_hash_forks()`＋逐行 sha256 回查 | ❌（记录齐全可查，但防篡改链不成立；修复待合入＋重启） |
| 10 | 观察期跨度 | 满一周 | 实际 **30 天 18 小时**；audit 零事件日期 **0 天**（每天都有事件） | 窗口首末行时间戳 | ✅（累计口径）／❌（连续口径，见 §二） |

## 二、观察期实际跨度与中断情况（如实）

- **预期 7 天／实际 30 天 18 小时**（2026-08-13 00:00 → 2026-09-12 18:5x 本地，UTC+8）。
- **这 30.8 天不是连续运行**。本服务常驻在开发用 Windows 笔记本（Shao Peishen 2026-08-13 拍板永不部署 `.51`；队列 #138 已留痕「继续常驻 Win 笔记本 · 残留风险」），笔记本合盖／关机即断：
  - **网络断线段** 445 段（`disconnected`→下一 `connection_established`），绝大多数 <1 分钟由 SDK 自动重连；**>5 分钟 14 段，累计 1190.6 分钟（19.8 小时，占窗口 2.69%）**，最长 300 分钟（09-02 01:22→06:22）、259 分钟（08-24 03:07→07:26）、211 分钟（08-23 03:32→07:03）、178 分钟（08-18 04:07→07:05）。
  - **进程启停**（包装日志）：窗口内启动 **52 次**＝冷启动 45 次（计划任务 Logon／Boot 触发或人工 `Start-ScheduledTask`）＋退避重启 7 次；记录到的退出 14 次＝`exit=1`（SDK 重连预算耗尽，`fatal_disconnect_detected` 7 次：08-19 ×3、08-25 ×2、09-08 ×2）8 次＋`exit=-1`（人为杀进程／部署换代）6 次。其余启动前的「退出」没有日志行——即机器休眠或关机、进程未及落笔。
  - **audit 静默 >3 小时**：2026-08-31 起 outbox 中继每 5 分钟写一条 `outbox_relay_scan_failed`（`#556`），之后的静默 >3 小时**一定是机器不在线**，共 **12 段**（09-01 01:00→07:27、09-01 17:19→23:38、09-02 01:22→06:22、09-02 15:23→19:18、09-02 23:26→09-03 07:23、09-03 13:19→21:25、09-05 22:51→09-06 07:11、09-07 14:04→19:17、09-08 01:43→08:12、09-08 12:21→16:17、09-09 11:20→14:56、09-10 01:48→07:03）；08-31 之前的夜间静默无法区分「空闲」与「离线」，本件不计入。
  - **最长连续无中断跨度＝2.49 天（09-10 07:03 → 本件写就时，仍在延续）**；其次 1.41 天（09-03 21:43→09-05 07:34）、1.29 天（09-06 07:11→09-07 14:04）。**「连续 7 天」在本机形态下从未达成、也不可能达成**。
- **离线的业务后果（必须写明）**：`gap_alert.py` 模块头原文——「企微 aibot 协议没有离线消息补推能力——监听断线期间发来的消息永久丢失，无法找回」。本方**无法从 audit 证明离线期间没有专员发过消息**（那些消息不会在本方任何地方留痕）；现有兜底＝每次（重）连接给 Shao Peishen 发 `gap_alert_sent`（窗口内 48 次成功、5 次失败）提示「距上次确认存活 X 分钟，期间消息可能丢失」，以及归档↔队列对账哨兵（窗口内报告 1 次，08-26）。**这是 8.5「无漏归档」判据上的结构性盲区，不是本窗口的实测缺陷**——签字时须知情。
- **窗口内其它噪音（不影响 8.5 判据但污染 audit）**：`outbox_relay_scan_failed` **1541** 条（08-31 22:10 起每 5 分钟一条，`\\192.168.100.51\C$\...\sc2_group_outbox.jsonl` 不可读 `OSError 22`，`#556` 已立行、`B-0911_U` 已出修法设计）；它贡献了 33 处链断点。

## 三、抽样追溯（≥3 条，从入口到 audit 落盘，附标识）

行号 `L####`＝`wecom_aibot_audit.jsonl` 物理行号（1 起）；时刻为本地 UTC+8。

**A · 入站文件归档（采购部 姚祖怡 2026-09-10 08:22）**
`L5748 archived`（`sender=YaoZuYi, msgtype=file, chattype=single`，`archived_path=7-外部文档/采购部/采购部-YaoZuYi-回复-采购部#22-2026-09-10-…-0a87e5b7dd4fd969a48263b864f356c3.docx`，`letter_number=采购部#22`）→ 磁盘存在、89,529 B → `L5749 queue_append_deferred_lock_busy{owner:采购专线}`（锁忙推迟）→ `L5751 followup_readme_bridge_marked{采购部#22 → 📨 回件已到，待拆件}` → `L5752 group_notified{采购部, chatid wrvDL_DAAAH7IL…}` → `L5753 inbound_forwarded_to_paul` → 归档文件名命中 `跨桌任务队列-业务场景.md` 第 59／69／70／72 行（待领行已在）。

**B · 出站跟进信全链（采购部#22，2026-09-09 15:07）**
`L5599 followup_approved`（`quote`＝Shao Peishen 原话「采购部#22批准并发送」）→ `L5601 followup_delivered{sent:true, media_id 3ztVOej7WBo7O7chgi8OV…}` → `L5602 followup_backfilled{new_status:"✅ 已推送 2026-09-09 07:07 UTC"}` → `L5603 followup_backfill_committed{committed:true}`（git：`ce0172a 2026-09-09 15:07:35 bot(跟进信): 回填「采购部#22」发送状态`）→ `L5604 followup_cc_delivered{recipient:ShaoPeiShen, acks errcode 0×2}` → `L5605 followup_group_cc_delivered{recipient wrvDL_DAAAH7IL…}` → `L5606 followup_ledger_writeback{letter:采购部#22}`。同一分钟另一封 IT部#12 被 `followup_approval_rejected{cooldown_not_elapsed}` 两次拦下（10 分钟冷却窗口机制在工作），15:16 才批准发出（git `91838be`）。

**C · 断线自愈（2026-09-08 08:12–08:22）**
`L5216–L5228` 六次 `connection_error: ConnectionRefusedError [WinError 1225]`＋`reconnecting attempt 1–6` → `L5229 connection_error: Max reconnect attempts exceeded` → `L5230 fatal_disconnect_detected` → `L5231 gap_alert_send_failed{sent:false}`（连接本身不通，告警发不出，符合 gap_alert 模块头描述的形态）→ 包装日志 `[2026-09-08 08:14:08] 服务退出（exit=1，本次运行 109 秒）`→`[08:15:08] 启动…第 2 次` → 再一轮 6 次失败 `L5233–L5247` → `[08:16:55] 服务退出（exit=1，107 秒）`→`[08:21:55] 启动…第 3 次` → `L5251 connection_established` → `L5252 authenticated` → `L5253 gap_alert_sent{sent:true, recipient:ShaoPeiShen, last_event_at 2026-09-07T17:42:52Z}`。零人工干预，三级退避第 1→2→3 级如设计。

**D · 入站失败 fail-closed → 重发落档（质量部 陈忱 2026-09-10）**
`L5774 archived`（同一人的文本消息正常落档）→ `L5780–L5785 media_transfer_retry{stage:download_inbound, attempt 1..3, timeout 20.0s, TimeoutError}` → `L5786 message_dispatch_failed{msgtype:file, sender:ChenChen}` → `L5787 media_resend_notice_sent{target:ChenChen}`（自动回执请其重发）；09:22／10:14 同形态再 8 次 → 服务 13:31 重启（包装日志 `exit=-1`）→ `L5896／L5897 archived＋queue_appended`（`质量部-ChenChen-回复-质量部#13-2026-09-10-合格-f3b7edae….zip`）及后续两个 zip（13:40:07、13:40:55）。失败没有静默、没有假成功；根因见 `#545`。

**E · 超长信两次失败 → 降级摘要（采购部#19，2026-08-27→28）**
`L3172 followup_approved`（Shao Peishen「两封信都通过；发」）→ `L3178 followup_delivery_failed{sent:false, acks:[], reqId aibot_send_msg_1787821342066_e75362ec, Reply ack timeout 5.0s}`（17:14 同样再失败一次）→ `L3193 followup_delivered`（`md=…-三条判例再送与六件一次问齐-推送摘要.md`，`media_id 3oyHyLTZtWteGgoj…`）→ `L3194 cc` → `L3195 group cc` → `L3196 followup_backfilled{✅ 已推送 2026-08-27 16:31 UTC}` → `L3197 followup_backfill_committed`。

## 四、与晋档条件的逐条对照

| proposal 晋档条件（档2→档3） | 状态 |
|---|---|
| 1. 前置动作（后台建机器人／凭据交接／拉进真实群） | ✅ 2026-07-13 完成（tasks 8.1） |
| 2. 测试群验收全通过（echo／断网重连／两场景各一次／门禁单测） | ✅ 7.1–7.3、8.3、8.4 已勾（7.2 于 2026-08-13 真实杀进程验证） |
| 3. 真实群跑一周无事故（无误归档／无漏推送／audit 全程留痕可查） | **无误归档 ✅（55/55，0 损坏，失败件 fail-closed 且已补齐）／无漏推送 ✅（28 应推：27 已发＋1 已批准待人工发，1 封降级摘要送达）／audit 可查 ⚠️（事件链齐全可追；hash-chain 269 处并发分叉断点，修复未上线）**；「一周」＝累计 30.8 天 ✅、连续 ≤2.49 天 ❌ |
| 4. Shao Peishen 签字批准转常驻 | ⏳ 本件即为签字件，见 §五 |

## 五、签字区（待 Shao Peishen 裁；每问给选项＋代价＋〔荐〕；🔴 本节全部为 🟡 档决策，本方不代答、不默认生效）

**Q1 · 「满一周」的判定口径（决定 8.5 能否勾）**
- (a) **累计口径**：接受「累计 30.8 天、三条判据两过一部分过」为满足 8.5 观察意图，8.5 可勾；连续性不作为判据（本服务是开发期专员协同工具、常驻笔记本，proposal 未写「连续」二字）。代价：离线窗口内专员消息永久丢失这一结构性盲区被正式接受，靠 `gap_alert` 提示＋专员重发兜底。〔荐〕
- (b) **连续口径**：要求真正连续 7 天不中断，本机形态不可能达成 ⇒ 8.5 挂到 Mac Studio 常开主机迁移（队列 #220，hold）之后再判。代价：8.5／9.5 继续悬置数周到数月，本包无法归档，「疑似遗忘归档」告警持续。
- (c) **折中**：以当前正在延续的连续段（09-10 07:03 起）为准，若跑到 09-17 07:03 满 7 天且无新增失败件，即勾 8.5；否则回到 (a)/(b) 再裁。代价：再等 5 天，且笔记本一次合盖即前功尽弃、判定权重回到运气。

**Q2 · hash-chain 断点的处置（决定「audit 全程可查」怎么算过）**
- (a) **修复上线为转常驻前置**：`#564` 分支 `claude/op0912a-audit-hash-race-564`（`59b54f7`）ff 入 master → 服务执行体 `ops/wecom-service-home` 同步 → 重启进程；此后 `verify_chain()` 以修复后首行为新起点应零新增断点；历史 340 处只标注不回填（同 `#564` 已定口径）。代价：一次服务重启（≈66 秒自愈窗口，同 7.2 实测），且需 ff＋同步两步——ff 由看护者串行做或经『已授权待合』登记处机器做。〔荐〕
- (b) 不作为前置，转常驻后再修。代价：在修好前审计链对「谁改过日志」不提供任何保证，IATF 可追溯口径上是软肋。
- (c) 回填／重建历史链。代价：`#564` 已裁「只标注不回填」，重开需推翻既有拍板；且重建等于承认可以事后改写审计文件，得不偿失。

**Q3 · 附件超时根因修复（`#545`，分支 `claude/op0910j…` 待 ff）是否并入本次转常驻前置**
- (a) 并入：与 Q2(a) 同一次 ff＋重启完成，此后 >10 s 的附件下载不再恒败、专员不再被误导反复重发。代价：ff 前须重跑回归（`#562` 合入守卫 ④ 已机器化）。〔荐〕
- (b) 不并入，按队列既有节奏走。代价：下一个大附件（如 8D 样本 zip）大概率再触发一轮「9 次自动回执」。

**Q4 · 9.5 归档（`/opsx:archive wecom-aibot-channel`）**
- (a) Q1 答 (a)/(c) 且 8.5 勾选后，10.5（二期 dry-run 观察，明写不在本次范围）转独立待领行，本包归档。代价：需一次 `/opsx:archive` 执行（CC 可代执行）；10.5 起新行会撞机制类 WIP 上限（现 31/22），须 🛑 起首排队。〔荐〕
- (b) 10.5 允许挂账不阻档，直接归档。代价：违反「全部 [x] 才归档」字面纪律，需你明示豁免。
- (c) 不归档，8.5 勾了也留着。代价：「疑似遗忘归档」告警继续，与「状态去匹配告警」原话相悖。

**答复模板**（改字母即答）：

```
1a，2a，3a，4a
```

## 六、本件不做／未做（硬边界与留步）

- 未代签、未勾 8.5／9.5、未转常驻；`tasks.md` 8.5 条目下只追一行指向本件。
- 未碰 `.51`、未重启服务、未改机器人配置、未向任何真实群或个人发消息、未改实现代码。
- 未 ff master；本件在泳道分支 `claude/op0912m-wecom-85-acceptance`，只 push 分支。
- **留步／未深查**：① 采购部#21（08-31 21:46）送达后主 audit 无回填事件的去向（疑 `#559` 孤儿链，未搜遍全部 worktree）；② 08-31 之前夜间 audit 静默属空闲还是离线，无观测面、无法回溯；③ 离线期间是否有专员消息丢失——协议层不可知，只能靠专员事后反馈。
- **状态同步（无需你答）**：README 现取 `🆕 待发×2`（质量部#14、财务部#18），你 09-11 已答 1a「明早手动发」（`#557` 追记）；两封若不在 09-14（周一）09:30 前手动发出，`ZhuopinFollowupDispatchDaily` 会按机制自动发（`dispatch.py` 对 `🆕 待发` 行不设「须有 approve 事件」闸；财务部#18 由 `OP-0911-H` 直接登记为 `🆕 待发`、主 audit 无 `followup_approved`，与队列 `#518` 自陈「登记 ⏳ 待你审」不一致——**不是漏推，是登记口径不一致**，顺带如实记下）。
