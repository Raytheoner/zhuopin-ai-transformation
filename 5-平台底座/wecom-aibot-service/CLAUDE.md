# CLAUDE.md — 企微智能机器人双向通道服务（场景级记忆）

> 本文件是本服务的本地记忆/进度笔记，隔离于其他场景。
> 项目级上下文见仓库根 `CLAUDE.md`；权威规划见 `openspec/changes/wecom-aibot-channel/`
> （proposal.md/design.md/specs/tasks.md）+ `1-转型规划/开场prompt-企微智能机器人双向通道-CC建造交接.md`。
> 本服务 = CC 建造车间产物；**不改规划文档**（那是 Cowork 的活）。

## 1. 定位

- **不是**某个部门场景（不像 SC1-SC8/FI1-FI10 归属单一部门），是**平台侧独立常驻服务**，
  服务四域专员（采购姚祖怡/财务唐燕萍/质量陈忱/销售泓钦）的企微双向通道基础设施。
- v1 两场景：①推送跟进信（`aibot_send_msg`，md+docx）②收专员反馈自动归档（R6 自动化）。
- 与现有 webhook 群机器人（`0-学习与工具/发企微.py` + 平台 `wecom.py`，只发不收）**并存不改**。

## 2. 关键决策记录（design.md 完整版，此处摘要）

| 决策 | 结论 | 依据 |
|------|------|------|
| D1：代码归属 | 连接器薄封装入 `zhuopin_platform/shared_tools/notifiers/wecom_aibot.py`；常驻服务独立目录 `5-平台底座/wecom-aibot-service/`（不挂靠任何部门场景） | 服务四域，非单一部门场景 |
| D1：部署位置 | LAN 服务器 192.168.100.51（已跑 SC8 保供看板），纯出站 WS 客户端、无入站端口/防火墙——**⚠️ 已改判（Shao Peishen 2026-08-13）：永不部署 `.51`**，本服务是开发期专员协同工具、系统上线后不再需要，后续开发迁往 Mac Studio 重建；本行原文历史记录不追改，实际执行以本次改判为准 | Paul 2026-07-11 拍板；2026-08-13 改判见 §5 状态时间线 |
| D2：单连接看门狗 | 三道防线：①Windows 计划任务 `-MultipleInstances IgnoreNew`（主防）②SDK 断线均审计留痕（无法精确识别"被踢"，见下）③三级重启退避 1min/5min/15min（`start-aibot-service.ps1` 自实现，Task Scheduler 原生不支持分级） | B 段读 SDK 源码核实修正 |
| D3：心跳/重连 | 采纳官方 SDK 内置默认（心跳 30s/2次未响判死；重连指数退避，**封顶硬编码 30s，非早前设想的可配 5min**）；`max_reconnect_attempts=6`，累计约 90s 耗尽交部署层 | 读 `aibot` SDK `ws.py` 源码核实 |
| D4：WS 库选型 | 采纳官方 SDK `wecom-aibot-python-sdk`（PyPI，v1.0.2）；outbound 素材上传 SDK 未封装，自行按官方文档三步协议（`aibot_upload_media_init/_chunk/_finish`）实现，复用 SDK 内部 `send_reply` ack 原语 | 实测源码，无需退化 `websockets` |
| D7：部门映射 | `department_mapping.yaml` 静态配置（姚祖怡→采购部/唐燕萍→财务部/陈忱→质量部/泓钦→销售部）；持有人 Paul、backup 孙涛；未命中 fail-closed 归 `7-外部文档/待分拣/`，队列行领取方=Paul | Paul 2026-07-11 三问拍板确认 |
| D8：门禁① | 结构性——`pyproject.toml` 依赖清单不含 `erp_connector`/`srm_connector`；`intake.py` 代码路径仅归档/登记/回执三类，无第四条路径；有单测 AST 扫描 + 依赖清单文本扫描双重核查 | design.md，不得放宽 |
| D8：门禁② | `delivery.py` 推送前强制断言 README 目标行「发送状态」列严格等于 `🆕 待发`，非此值一律拒绝 | design.md，不得放宽 |
| Non-Goal | 场景①不做自动扫描触发——推送由调用方显式指定具体某一行，服务只负责"断言+发送+回填" | 换取门禁②实现简单可靠 |

## 3. 复用底座资产

- **AibotConnector**（`zhuopin_platform.shared_tools.notifiers.wecom_aibot`）：连接生命周期事件转发 + `send_markdown`/`send_file`/`upload_media`/`download_file`；底层官方 SDK 懒加载（`client_factory` 可注入测试替身，未装 `[aibot]` extra 时模块仍可导入）。
- **SecretsProvider**：`zhuopin_platform.shared_tools.secrets.EnvSecretsProvider`，读 `WECOM_AIBOT_BOTID`/`WECOM_AIBOT_SECRET`（服务本地 `.env`，不入库）。
- **AuditLogger**：`zhuopin_platform.audit.AuditLogger.jsonl("reports/wecom_aibot_audit.jsonl")`，`scenario="wecom-aibot"`，`automation_level="L1"`（本服务无 L2 人工确认环节，专员均内部人员，见 proposal.md Impact）。
- **告警兜底**：`scripts/alert_webhook.py` 借道既有 `wecom.py` webhook（`WECOM_WEBHOOK_URL`，与本服务自身 BotID/Secret 是两套凭据）。

## 4. 红线（建造时守住）

> ⚠️ 两道门禁写死进代码结构，Paul 拍板不得放宽（见 §2 D8）。

- 🔴 归档服务（`intake.py`）**不得**依赖任何 ERP/SRM/CRM 连接器——`pyproject.toml` 刻意不含这些 extra，缺依赖即 `pip install` 失败，结构性拦截。
- 🔴 推送服务（`delivery.py`）**仅**发送 README 已标记"🆕 待发"（已定稿）的跟进信，草稿一律拒绝。
- 先 mock 跑通（`AibotConnector(client_factory=fake)` 全套单测）→ 再接真实凭据（F 段，待 Paul 完成队列 §四#10 前置动作）。
- 全部收发/归档动作写平台 `audit`（append-only，`AuditLogger.jsonl`）。
- OEM 隔离：本服务不涉及研发/OEM 技术数据，不适用。
- L2 门禁：不适用（专员均内部人员，`CUSTOMER_OUTBOUND_ENABLED` 不涉及本服务）。

## 5. 状态时间线

| 日期 | 状态 |
|------|------|
| 2026-07-11 | A 段完成：openspec `wecom-aibot-channel` 四件套（proposal/design/specs/tasks）产出，`validate --strict` 通过，Paul 审核批准（3 个 Open Questions 拍板：backup=孙涛/告警走现有项目群/待分拣兜底=Paul）。 |
| 2026-07-14 | 代码首次持久化合入 master（独立分支 `claude/wechat-robot-channel-setup-07e0f8` 全库溯源确认此前"代码已提交"表述与实际不符，从零重建等价实现后合入）；补齐 07-13 拍板的"进件全量转发 Paul"（`forwarding.py`）与出站抄送 Paul（`delivery.py::push_followup(cc_to_paul=True)`）。 |
| 2026-07-15 | **归档后部门群通报改用真实机制 + 三部门群真实凭据接入**：Paul 澄清群通报走的是**既有企微群机器人 webhook**（`https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...`），不是智能机器人 chatid 通道——两者是企微两套不同能力。`department_group_mapping.yaml` 从"部门→占位 chatid"改为"部门→**环境变量名**"（表本身不含秘密、可安全提交，真实 webhook URL 只落 `5-平台底座/.env`，已核实 gitignore 覆盖+未入任何 commit/日志/audit 明文）。Paul 提供财务部/质量部/采购部三个真实群 webhook；**销售部 Paul 拍板暂不启用**，故意不建映射（sender 命中销售部时 fail-closed 跳过，见 `group_not_configured`）。 |
| 2026-07-16 | **进件白名单落地（队列 #35，Paul 口头需求）**：新增 `whitelist.py`（`WHITELISTED_SENDER_USERIDS` 五人：`2023458` 陈承/`ChenChen` 陈忱/`tangyanping` 唐燕萍/`YaoZuYi` 姚祖怡/`Hongqin.Wang` 王泓钦），未命中→只回一条礼貌回复（说明机器人尚未正式开通）、记一条 `whitelist_rejected` 审计，不落档/不转发/不占用队列行/不发群通报。 |
| 2026-07-19 | **gap_alert 主通道发送失败无兜底 bug 修复（Paul 报告）**：新增 `aibot_service.gap_alert.send_gap_alert()`：主通道失败时，若提供 `fallback_send`（同步函数，走独立的群 webhook 通道，不依赖同一条故障连接），在线程池里尝试兜底发送一次；全程失败也不向上抛出。`run_aibot_service.py` 接入：webhook 取自既有 `WECOM_WEBHOOK_URL`（与 `alert_webhook.py` 同一凭据），未配置则维持原样。 |
| 2026-07-19 | **计划任务隐藏窗口不可靠问题修复（Paul 报告可见终端）**：**修复**：新增 `run-hidden.vbs`（`WScript.Shell.Run(cmd, 0, True)`，Win32 `SW_HIDE` 真正隐藏，业界公认比 PowerShell 自身 `-WindowStyle Hidden` 更可靠，等待完成以保持任务"运行中"状态语义不变）作计划任务新 Action（`wscript.exe run-hidden.vbs`，替换原直接调用 `powershell.exe -WindowStyle Hidden`），内部逻辑（`start-aibot-service-dev.ps1`/`Start-Transcript`/三级退避）完全不变。 |
| 2026-07-19 | **每次(重)连接都发通报（Paul 明确要求）**：新增 `gap_alert.build_reconnect_notice()`：包装既有 `format_alert()`（其"None=无需警示"语义保留不动，供其他调用方沿用）——超阈值沿用原有详细警示文案（含"消息可能丢失"提醒）；未超阈值时改发一条轻量确认文案（无历史可比对时"监听已启动"，短间隔时"监听已恢复，距上次活动约 X 秒，无明显中断"，不带警示措辞）。`run_aibot_service.py` 去掉此前"仅超阈值才发送"的门槛判断，每次连接成功后都调用。 |
| 2026-07-19 | **孤儿进程根治（验证上一条改动时复现更严重情形，Paul 收到重复通报）**：**根治**：`Stop-OrphanServiceInstances` 扩展为脚本启动时同时清理残留 `python.exe`（run_aibot_service.py）**与**残留外层脚本本体（排除自身 `$PID`），不再只清子进程。`start-aibot-service-dev.ps1` 本机专属硬编码路径，遵循既有惯例不入 git，此修复仅记录于此供未来接手者知悉。 |
| 2026-07-22 | **归档链路健壮性补强（队列 #69/#70，design D18）**：**两层补强**：① 该函数加乐观并发重试（写入前重读核验磁盘未变，变了则按最新内容重算插入点/编号再试，`max_retries` 耗尽显式报错）；② 新增 `queue_reconcile_sentinel.py`（归档↔队列对账哨兵，每次连接成功后扫描近 7 天 `archived` 事件核对文件名是否出现在队列全文里，疑似漏行只私信 Paul 一条汇总报告，**本次只做 dry-run，不自动写队列**）。**顺带**：`department_mapping.yaml` 补入陈承（IT，2023458）→ `IT`，此前白名单内但不在部门映射、命中后落"待分拣"，此后直接归档进 `7-外部文档/IT/`（IT 非四域专线，队列行领取方沿用默认值 Paul）。 |
| 2026-07-24 | **常驻监听迁移 Mac Studio · D1 队列 git 同步能力落地（Windows 侧可完成部分，队列 #90，openspec `wecom-listener-macos-migration`）**：**新增 `aibot_service/queue_git_sync.py`**（D1）：本地追加成功后 git 层乐观并发重试推送——非快进拒绝时 `fetch`+`reset --mixed` 对齐分支指针到远端最新+`checkout --` 只重置队列文件工作区内容+重新调用 `append_pending_task()` 对最新内容重算插入点/编号（而非 `rebase` 式重放旧 diff，因历史事故模式是"两写手各自算出同一编号"而非文本冲突）；**未做（Mac 侧，待 Paul 提供测试 BotID/Secret、Mac Studio SSH 访问方式、细粒度 PAT 后动手）**：tasks.md §1 Mac 环境搭建、§3 launchd 常驻自愈、§4 归档单向同步、§5 独立测试环境 E2E、§6 生产切换、§7 观察期与冷备收口、§8.1/8.2 文档收口（本条即 8.1 的一部分先行落笔，8.2 根 CLAUDE.md 表述更新留待生产切换真正发生时再改，避免"文档已改、实际仍是 Windows 收件口"的表里不一）。 |
| 2026-07-27 | **队列 #99：清扫适配两处修复（首次归档清扫的下游 gap）**：(a) `queue_appender._next_task_id` 此前只取 §一 可见最大号+1、不读顶部"编号高水位线"标注行——07-24 首次清扫（协议〇.8）把已完成行整行迁出正文后，若表格暂时清空/只剩较小号，新行会与已归档的历史编号撞车；改为 `max(§一可见最大号, 高水位线)+1`，标注行缺失/格式漂移时回落"仅取可见最大号"并在提供 `audit` 时留痕 `queue_high_water_mark_parse_failed`。(b) `queue_reconcile_sentinel` 此前只扫队列正文——已完成行迁入同目录《跨桌任务队列-归档-YYYYMM.md》后必产生假阳性"疑似漏行"私信（07-24 16:40 CST 那次即因此触发）；新增 `_collect_reconciliation_text`，同时扫描同目录严格匹配命名律的归档件。 |
| 2026-07-28 | **队列 #126：跨 checkout 失效 + 审计文件分裂双缺陷修复**：根因＝`queue_git_sync` 隐含假设"服务进程的 repo 根 == 队列文件所在 repo 根"，实际服务常驻 `ops/wecom-service-home` worktree、队列固定指向主工作区。**修法①**：新增 `aibot_service/repo_paths.py::resolve_repo_root()`——不再信任调用方传入的 `repo_root`，改用 `git -C <锚点父目录> rev-parse --show-toplevel` 动态解析队列文件真正所属的仓库根（与 07-23 编辑锁 `--git-common-dir` 修法同源思路），`WECOM_AIBOT_REPO_ROOT` 环境变量提供显式覆盖口，解析失败才回落调用方传入值；**追加落盘但同步最终失败时**，新增 `_mark_row_unsynced()` 在队列文件该行内追加显式"⏳未同步"标记（沿用协议〇.7「⏳」类标记既有约定——机器只标记，核实已同步后人工手动删除），使只看文件的读取方也能察觉，不再需要跨查 audit 才知道。**修法②（审计文件分裂）**：两脚本审计路径改用同一套 `resolve_repo_root`+`repo_paths.resolve_audit_path()` 动态解析统一落点。 |
| 2026-07-30 | **队列 #168+#147：编辑锁集成 + gap_alert 存活戳判据（同批，CC，独立 worktree `queue-numbering-alert-criteria-855665`）**：**#168**——`queue_appender.append_pending_task` 之前完全绕过协议〇.7 共享编辑锁，人类持锁编辑期间机器人直接写盘会被稍后的整文件写回静默覆盖。新增 `queue_edit_lock.py`（`SubprocessQueueEditLock`，复用既有 CLI 工具当子进程调用）+ `queue_lock_pending.py`（推迟暂存 JSONL + `flush_pending_queue_appends`，每条新消息到达时先补录积压）；`intake.py`/`connection.py` 接入（`enable_queue_edit_lock`/`pending_lock_path`，默认关闭、零影响既有调用方）。**#147**——`gap_alert` 判据此前用"距上次审计事件"当"中断时长"，但审计"有事才写"非"活着就写"，07-29"中断约 79 分钟"即误报。新增 `liveness.py`：连接存活期间每 5 分钟覆写一次独立存活戳文件（刻意不进审计 JSONL）。判据改为"距上次确认存活"，"距上次有人发消息"降级为纯信息展示，不再触发告警。协议〇.7 已补"机器人亦为受锁写入方"一句。 |
| 2026-07-31 | **队列 #172+#180（同批，CC，独立 worktree `loving-mestorf-98749e`，随 #171/#164 一并交付）**：**#180**——`queue_git_sync.py` 的"⏳未同步"标记（队列 #126 引入）此前只加不清，2026-07-31 转正首日复核实证 #149/#175 两行早已同步成功、标记仍挂着堆积成假警报；新增 `_clear_unsynced_markers`（即将提交前清掉文件里此刻残留的**全部**旧标记，不局限本次追加行——即将发生的这次推送会让文件当下全部内容一并确认同步），`_mark_row_unsynced` 插入位置由"编号列之后"（顶偏任务描述开头）改为"行末尾、闭合竖线之前"；`UNSYNCED_MARKER` 文案同步更新为"下次同步成功自动清除"。**#172（服务侧能力，主体完成，巡逻侧调用点待 Cowork 补）**：新增 `aibot_service/decision_reminder.py`——拆件巡逻已能把"需 Shao Peishen 项"登进队列 §四，但两次巡检之间新产生的项与高优先待领行无任何主动推送。§四表无独立状态列，逐行核证 #33-#40 八行得出判据"截止列含✅即已关闭，不能看整行"（#38 活样本：事项列开头带✅描述子问题①已收口，截止列仍写"建议…前给结论"指向子问题②，整行判✅会误判已关闭）；`evaluate_candidates` 一个函数同时承载"新增即时提醒"（首次出现即到期）与"超期每日汇总"（1/3/7 天递减间隔升级），状态持久化 `reports/decision_reminder_state.json`，解除后自动清空升级计数。新增 `scripts/decision_reminder_check.py`（一次性触发，主通道企微私信失败降级群 webhook，同 `gap_alert.py` 范式）+ `register-decision-reminder-task.ps1`（每日 08:30 `ZhuopinDecisionReminderDaily`）。① `LogonType S4U` 在本机注册**新**任务报 `Access denied`（S4U 需"以批处理作业登录"权限，赋予该权限本身要求管理员权限，即便运行期不需要，已隔离验证），改用同 `ZhuopinAibotDevListener` 既有先例的 `LogonType Interactive`（代价：任务触发时需当前用户已登录）；包装脚本现显式设置 `WECOM_AIBOT_QUEUE_PATH` 指向主工作区队列文件修正。**⚠️ 真实观察（未修复，留痕供参考）**：触发瞬间主监听出现一次 `disconnected`→`reconnecting`→`connection_established`/`authenticated`，约 2 秒内 SDK 自愈完成、无消息丢失（`gap_alert` 3 分钟阈值未触发告警属预期）——与 #90 D5/#110 提及的"同 BotID 双连接"风险同源，此次是首次真实观测到其发生，影响轻微（一次性脚本短连接，非持续并行）；每日一次、~2 秒窗口的残余风险已知可接受，若未来观察到真实消息丢失需重评架构（如独立测试 BotID 或改走纯 webhook）。**🔴 分工缺口（未做，需 Cowork 补）**："巡逻收工即时提醒"半边的调用点在拆件巡逻定时任务 prompt（仓库外 `C:\Users\Paul Shao\Claude\Scheduled\huijian-chaijian-patrol\SKILL.md`，CC 改不了）——建议在该 prompt §四步骤 5（sweep 触发）之后新增步骤 6：`python 5-平台底座/wecom-aibot-service/scripts/decision_reminder_check.py`（不像 sweep 依赖 `Start-ScheduledTask`，是直接 python 调用；若巡逻执行环境确无本地 shell 能力，每日定时任务仍提供兜底覆盖，只是首次提醒延迟到当天 08:30）。补上后①②两层才算完整闭环。 |
| 2026-08-06 | **队列 #294 修法⑴：跟进信发送状态两态语义扩为三态（新增 `⏸ 暂缓`，CC，独立 worktree `three-state-semantics-tests-0f1cc1`）**：**修法**：`readme_table.py` 新增 `PAUSED_STATUS = "⏸ 暂缓"`（第三态，只能从 `🆕 待发` 手工改写而来，不经任何脚本，与草稿态语义不同——草稿是"内容未审"，暂缓是"内容已审、主动不发"）；**⚠️ 语义未闭合（如实登记）**：本行范围经业务总线 2026-08-06 拆分后只做"暂缓态存在且门禁认它"（修法⑴），"队列侧决定与 README 状态列是否一致"的强制校验（修法⑵，编辑锁 `release` 增校验）已划归 #258（P2，待领，未开工，须走 openspec）——#258 落地前，"决定写进队列却忘改 README"这一失效模式仍可能发生，只是从"没有状态可写"变成"有状态可写、但无人强制检查是否真的写了"。 |
| 2026-08-09 | **队列 #305：队列写入侧裸拼注入口止血（CC，独立 worktree `focused-blackwell-4e0f0c`）**：**修法（两层止血，范围极小，仅改 `queue_appender.py`）**：①新增 `_normalize_row_field`，拼行前对每个插值字段做竖线归一化（半角 `|` → 全角 `／`，与 #164 既有约定 `一｜四`→`一／四` 同口径）；②新增 `_assert_row_column_count`，写回前对拼好的整行做结构自检（§一应为 9 条边界/分隔竖线），不符即抛 `RowColumnIntegrityError`（新增异常类）拒绝写入、不落盘——正常路径下①已消掉全部裸竖线，②理论上恒真，留作"未来新增插值字段忘做归一化"的 fail-loud 兜底；**范围内已核实未触及**（按队列 #305 行内"⚠️边界"声明）：#305 行文本内一并登记的"sweep `git add` 范围越界"第二方向（2026-08-08 同日真实 CI 全灭事故）不在本次 opener 授权触碰区（`工具-落库sweep.py`），留给后续领取方另行处置。 |
| 2026-08-13 | **队列 #314②收口：7.2 断网重连自愈真实验证 + 9.1-9.4 记账补齐 + 8.5 观察窗口声明（CC，独立 worktree `env-alert-wording-a批`）**：**7.2**——开发环境真实杀进程测试（Shao Peishen 当场拍板"不必等 `.51`"）：全链路自愈约 66 秒，零人工干预，形式化验证补齐（此前只有真实事故观察、无主动构造测试）。**8.5**——Shao Peishen 2026-08-13 拍板解除阻塞：本服务永不部署 `.51`（开发期专员协同工具，系统上线后不用；后续迁 Mac Studio 重建），满周观察时钟即日起在开发环境起算（基准日 2026-08-13，预期 2026-08-20），`tasks.md` 已按 #314② 机制声明 7 天观察窗口——**待满周后回填验收小结才可勾选，未观察先勾**。`tasks.md` 完成率 37/45→42/45（82%→93%），仅剩 8.5（观察中）与 10.5（二期延后，范围外）未勾，尚未达 `/opsx:archive` 前置条件。 |
| 2026-08-19 | **队列 #312 两个缺口一次修掉（CC，独立 worktree `open-pool-reminder-fix`，openspec 变更包 `open-pool-reminder-dual-file-and-staleness`）**：**缺口一 · 读侧只跟了一份队列文件**——`repo_paths.DEFAULT_QUEUE_RELATIVE_PATH` 是单文件常量，而 `#315`（2026-08-11）拆分后**采购／财务／质量三域的构建任务全住在 `跨桌任务队列-业务场景.md` 里，从未进过池**；实测生产状态 `known_open_ids` 五个全是机制环境行。新增 `build_pool_items_from_repo()` 按 `queue_table.iter_queue_paths()` **逐份解析后合并**（🔴 **绝不拼接文本再解析一次**——`_parse_table_rows` 用 `find` 只取第一个 `## 一、`，拼接会静默丢掉第二份的 §一，**症状与本缺口一模一样且更难发现**，已配反例单测锁死）；**对生产队列实证：`#334`／`#344` 首次进池。** **缺口二 · 只在新增时推、对「一直有活没人开」结构性沉默**——新增「陈化催办」（末次触碰 > 7 天、每周一催，Shao Peishen 2026-08-19 答定夺 1(a)、N＝7），与「新增即推」**分别计指纹、独立成一条消息、audit action 名单独区分**（`open_pool_stale_reminder_*`）。「该行动没动」**用 git 不用 mtime**（`git log -1 --format=%cI -G` 按行首编号匹配增删行；mtime 反映的是「文件被写过」，而队列文件几乎每天被写 ⇒ 用它判这一行动没动恒为假），**也不用 `-L`／`git blame`**（那两者追的是「当前第 n 行」，而队列行的物理行号随上方增删不断漂移，会静默给出另一行的历史）。**交付时未闭合、如实登记**：当日池中最久的 `#240` 只滞留 6 天，**全部 9 条都 < 7 天 ⇒ 陈化候选为空**，真实陈化催办最快 2026-08-20 08:30 定时任务才会首次推出，**那一次才是本判据的真实首验**。 |
| **当前** | **场景①②（文本+文档路径，含 outbound 推送与 inbound 归档）+连通性+echo+部门映射（五源含 IT）+审计+队列追加（乐观并发重试+编辑锁保护+推迟补录）+归档↔队列对账哨兵（dry-run，兜底链最后一道网）+进件全量转发 Paul+出站抄送 Paul+归档后部门群通报（财务/质量/采购三部门，webhook 机制，真实发送已验证）+进件白名单（陈承/陈忱/唐燕萍/姚祖怡/王泓钦五人，白名单外只礼貌回复）+gap_alert 主通道失败兜底 webhook+存活戳判据（真断线 vs 空闲不再混淆）+计划任务真隐藏（VBS SW_HIDE）+每次(重)连接都发通报+孤儿进程根治（子进程+外层脚本双重清理）+ queue_git_sync ⏳未同步标记自愈+需 Shao Peishen 决策提醒（decision_reminder.py，每日 08:30 定时任务 `ZhuopinDecisionReminderDaily`，真实发送已验证）+跟进信发送三态语义（`⏸ 暂缓`，队列 #294 修法⑴，2026-08-06 落地——README↔队列一致性校验半边待 #258）+队列写入侧竖线归一化与列数自检（队列 #305，2026-08-09 落地，堵住文件名裸竖线撑列注入口），均已在开发环境用真实数据验证通过（白名单/对账哨兵为 mock 单测覆盖，尚未真实群验证）；六个真实生产 bug 已发现并修复**（归档文件覆盖/队列越界写入/素材上传字段名错误/二进制归档误判损坏/gap_alert 无兜底/队列追加并发覆盖），另有两个部署层可靠性问题已修复（计划任务窗口隐藏不可靠、孤儿进程导致重复实例）。销售部群通报暂不启用（Paul 拍板）。断网重连自愈（7.2）已于 2026-08-13 真实杀进程测试验证通过。仍待：白名单/对账哨兵真实群验证、满周灰度（8.5，观察窗口进行中，预期 2026-08-20）、对账哨兵二期自动补行（观察 1-2 周误报率后再评估）、队列锁补录目前逐条独立 acquire/release（未批量化，积压场景本应罕见，正确性不受影响）。**本服务永不部署 `.51`**（Shao Peishen 2026-08-13 拍板，开发期专员协同工具，系统上线后不用，后续迁 Mac Studio 重建）——§6 范围澄清已按此更新。未 `/opsx:archive`（tasks 未全 [x]，仅剩 8.5 观察窗口与 10.5 二期延后两项）。 |

## 6. 关键依赖/前置（解锁条件）

> **范围澄清（Paul 2026-07-13；Shao Peishen 2026-08-13 更新）**：192.168.100.51 是**正式发布服务器**，本节以下条目全部在**开发环境构建系统**（本机）完成验证，与 .51 无关。**本服务永不部署 `.51`**（2026-08-13 拍板：开发期专员协同工具，系统上线后不再需要；后续开发迁往 Mac Studio，届时在 Mac 重建一套）——原"独立后续发布动作、另行安排时间"的表述已过时，不存在需另行安排的 `.51` 部署动作。

- ~~🔴 队列 §四#10：Paul 企微后台建智能机器人 + BotID/Secret 交 CC~~ **✅ 2026-07-13 已解除**。
- ~~🔴 **`department_mapping.yaml` 需换真实 userid**~~ **✅ 2026-07-13 已换**。
- ~~🟡 开发环境本机对 `wss://openws.work.weixin.qq.com` 的实际出站可行性~~ **✅ 已验证**。
- ~~🟡 场景②的企微消息发送人字段路径（userid vs 显示名）未经真实抓包验证~~ **✅ 已确认**。
- ~~🟡 素材上传三步协议（`upload_media`）未经真实凭据验证~~ **✅ 已验证**（2026-07-13）：首次真实调用暴露请求体字段名错误（`type`/`total_chunks`/`base64_data`/`md5`），修正后 docx 附件真三步分片上传+发送成功，见 tasks.md §8.3。
- ~~🟡 生产路径（`connection.py`/`intake.py`/`delivery.py` 的审计+归档+队列追加全链路）未跑通~~ **✅ 已跑通**。
- ~~🟡 **inbound 文件附件路径仍未验证**~~ **✅ 已验证**。
- ~~🟡 断网重连自愈（tasks.md 7.2）~~ **✅ 2026-08-13 已验证**（真实杀进程测试，见状态时间线）。
- 🟡 满周灰度（8.5）观察中，预期 2026-08-20 满周（基准日 2026-08-13，开发环境起算）。
- 运行：`python scripts/run_aibot_service.py`（读 `.env`，本机/服务器均可跑）；测试：`pytest`（全程 mock，不触真实企微端点）。

## 路径引导（队列 #345，2026-08-18）—— 扁平部署布局下不再硬失败

- **改了什么**：本组件下列入口顶部的 #300 worktree 隔离引导，**找不到 `5-平台底座/zhuopin_platform` 标记时不再无条件 `raise`**：`scripts/` 下 9 个入口（`run_aibot_service`／`alert_webhook`／`approve_followup_letter`／`check_connection`／`decision_reminder_check`／`dispatch_followup_letters`／`echo_test`／`flush_pending_lock_appends`／`push_followup_letter`）—— **常驻服务 ＋ 每日批处理定时任务，起不来会静默吃掉跟进信投递与告警**
- **为什么**：`.51` 的部署布局是扁平的 `C:/<svc>/app` ＋ `C:/<svc>/zhuopin_platform`（后者已由 deploy 脚本 `pip install -e` 进该服务 venv，全机唯一一份），**本就没有 `5-平台底座/` 这层目录**。原实现在此直接 raise，等于把入口在生产布局上钉死。2026-08-18 SC8（8091）与 QD-B（8093）当天各自被它打挂过一次。
- **改法**（同 QD-B `dcc4162` / SC8 `a858769` 已验证范式）：找到标记 → 按 #300 原样前插（开发机 N 个平等 worktree 需确定性）；找不到 → 只插自身包路径、平台底座交环境解析（生产机唯一一份、无歧义）；**只有当环境里也没有 `zhuopin_platform` 时才 raise** —— 不引入静默失败。
- 🔑 **为什么这类雷本地测不出来**：**本地永远能找到仓库根标记**，全量测试全绿与它毫无关系。凡"引导/路径解析"类改动，**本地绿 ≠ 生产可启动**。
- ⚠️ **`tests/conftest.py` 刻意不改**：在 monorepo 内 fail-loud 是**有价值的**——测试就该跑在仓库里，找不到标记说明环境真错了，此时静默回退才是隐患。
- **收拢为平台底座共享函数** 见 `openspec/changes/platform-bootstrap-ensure-paths/`（已 propose，待 Shao Peishen 审 design，本次未 apply）。
