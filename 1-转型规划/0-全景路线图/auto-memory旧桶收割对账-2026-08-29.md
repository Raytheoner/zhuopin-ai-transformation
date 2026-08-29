---
status: 生效
title: "auto-memory 旧路径桶收割对账（26 件三分类）"
created: 2026-08-29
执行方: Cowork 构建环境方案线（OP-0829-E · T6）
来源: Shao Peishen 2026-08-29 改判 §四 #135（启用 CC 侧 auto-memory）后的配套收割
---

# auto-memory 旧路径桶收割对账（26 件三分类）

> **对象**：`C:\Users\Paul Shao\.claude\projects\C--Users-Paul-Shao-OneDrive-Projects---AI--\memory\`
> —— 仓库从 OneDrive 迁到 `C:\Dev` 那天 auto-memory 静默换桶留下的旧桶（成因见 §四 #135）。
> **纪律**：🔴 **本次全程只读，旧桶文件一个不删、不改、不移**；本件只做分类与承接登记。
> **取证手段（守「验证声明须写手段」）**：`Get-ChildItem -Recurse -File` 点数 ＝ **26 件**（与 #135 自陈底数一致，**未被证伪**）；逐件读用 `Get-Content -Raw`（`project_sc8_real_cutover.md` 用 `-TotalCount 42` 读至文件自然结尾）；「repo 是否已有承接」一律用 `Grep`(ripgrep) 实际检索，**不凭印象**，命中与未命中都在下表如实标注。

---

## 〇、🔴 三条改变结论的发现（先看这个）

### ⓵ 旧桶里有**两条已被现行口径取代、却仍写成现行做法**的纪律件

| 文件 | 旧桶写的 | 现行真实口径 | 若被自动注入的后果 |
|---|---|---|---|
| `project_wecom_aibot_authorization_model.md` | README 状态列标 **「🆕 待发」＝ Shao Peishen 预授权，标准四专员流程内发送无需再确认** | 根 CLAUDE.md §5 场景固定流程第 8 步：起草产物**只能**写 `⏳ 待你审`；发送还须过**串行闸** ＋ **发送硬前置三条**（ff 合入／`.51` 冒烟／原始案例端到端复现） | 🔴 **把一套已废止的发信授权模型带回现场**——按旧标记直发＝跳过串行闸与硬前置，而跟进信**发出撤不回**（`财务部#14` 已有实证） |
| `project_sales_dashboard_git_history_pii.md` | commit `6ebf962` 的历史 PII「Paul 认可不紧急，**改天做全面清理**」 | 队列 §四 **#33 已于 2026-07-24 拍板：①登记风险接受**（private 仓库、访问面小），并注明「若未来仓库开放协作或对外须重评」 | 让一条**已闭环**的决策在 memory 里停在中间态，后续会话可能重新提议改写 git 历史（破坏性操作） |

🔑 **这两条正是边界②「纪律口径判据一律不入 memory」的实证**：旧桶出问题**不是因为它记错了**——两条在写下的当天都是对的；是因为**纪律口径会被后续决策推翻，而 memory 没有任何机制跟着改**。判据类内容一旦离开 CLAUDE.md／队列这两个会被持续维护的载体，就只会越放越旧，且**旧得毫无信号**（同族＝root §5「工具静默回退」：读起来完全正常的旧数据，没有任何东西告诉你它是旧的）。

### ⓶ 有一条真判据，repo 里**只活在归档件里**，无常驻载体

`feedback_historical_check_must_include_tests.md`——「改判据前只查生产数据不够，必须同时对照既有回归测试套件」。
**Grep 实测**：全库仅命中 `openspec/changes/archive/2026-08-05-sweep-editlock-status-keyword-anchoring/design.md:76`（**归档变更包**，属历史记录、不是常驻判据载体）；根 CLAUDE.md 与两份队列**零命中**。
⇒ 这条判据目前**谁都读不到**。建议登记队列一行（见收工报告定夺项）。

### ⓷ 三条 Shao Peishen 偏好表述，repo 里 Grep **零命中** —— 而这恰好是对的

`feedback_yield_on_resource_contention`（能让则让）、`feedback_manual_file_edits_full_replacement`（一次粘贴覆盖）、`feedback_action_list_numbering`（编号可见不用勾选）——全库无承接。
**但它们不该进 CLAUDE.md**：按新边界的判别一问「**违反了会怎样**」——违反只是让他多不舒服一次／多操作一步，**不会做错事** ⇒ 属技巧与偏好层，**正是 CC 侧 auto-memory 该装的东西**。⓶ 与 ⓷ 合起来说明新边界切得准：它把「不改会出错的」逼回 CLAUDE.md，把「不知道只是别扭的」留给 memory。

---

## 一、三分类对账表（25 件正文 ＋ `MEMORY.md` 索引 ＝ 26）

出路：**留**＝仍真且属技巧/环境坑/偏好，合新边界①，CC 侧可继续用 ｜ **封**＝过时，封存不动、不据此行动 ｜ **纪**＝涉纪律口径，须确认 CLAUDE.md/队列已有承接

### A. 仍真（12 件）——写明 repo 承接载体或如实标「无、且不需要」

| # | 文件 | 内容一句 | repo 承接载体（Grep 实测） | 出路 |
|---|---|---|---|---|
| 1 | `feedback_action_list_numbering` | 行动清单用纯数字编号，不用 `[ ]`（已复现 4 次） | **零命中**——属偏好，不需要 | 留 |
| 2 | `feedback_clarify_ambiguous_prompts` | 指令有歧义先问清再动手 | 零命中；与 opener 纪律精神一致，未单列条 | 留 |
| 3 | `feedback_desktop_session_terms` | new chat／new task／new session ＝ Chat／Cowork／Code | 部分承接：`专线opener模板库.md` §〇.15「线 vs session 术语与别名表」 | 留 |
| 4 | `feedback_language_simplified_chinese` | 一律简体中文，含过程反馈 | 零命中——属偏好 | 留 |
| 5 | `feedback_manual_file_edits_full_replacement` | 需他手工改的文件一律给完整全文，不给拼接指令 | **零命中**——属偏好（成因＝`settings.json` 被拼坏事故） | 留 |
| 6 | `feedback_scheduled_task_visibility` | 断言定时任务不存在须查四套系统（含 claude.ai 云端，本地工具看不到） | 判据面已承接 root §5「工具静默回退」（太干净的阴性先问是否没读到对象）；**四套系统清单本身零命中**，属技巧 | 留 |
| 7 | `feedback_wecom_internal_group` | 内部工作群简报直接放行，无需二次确认 | 部分承接：root §5「企微同步推送」条 ＋ `0-学习与工具/发企微.py` | 留 |
| 8 | `project_queue_lock_worktree_self_delete_fails` | worktree 删不掉自身所在会话，属预期限制、勿强删 | 零命中——属环境坑 | 留 |
| 9 | `project_server_only_env_switches` | 功能开关只在 `.51` 的 `.env`，本机跑真实数据静默走另一套口径 | 零命中——属环境坑；⚠️ 实测差异极大（1493 物料 vs 596），验收一律以生产载荷为准 | 留 |
| 10 | `project_shared_python_editable_install_collision` | 全局 Python 无 venv，`pip install -e` 会被别的 checkout 静默劫持 | 旁注承接：root §4／队列 `#300`（`pip install -e` 可选） | 留 |
| 11 | `project_u9c_external_webapi` | U9C 外网 ＝ OAuth2、base 须 host-only、CommonEntity 外网 404 | 承接：`0-学习与工具/携客云SRM-OpenAPI核实与申请要点.md`、平台底座 `ZpConnector` | 留（⚠️ 内含「spike 里 client_secret 明文、建议轮换」安全债，另见下方定夺项） |
| 12 | `MEMORY.md` | 25 条索引 | ——（索引本身） | 留（⚠️ 新边界③ 索引须守 ≤200 行／25 KB；**当前 5,611 B／27 行，远未触限**） |

### B. 过时（7 件）——封存不动

| # | 文件 | 为何过时 | 承接／处置 |
|---|---|---|---|
| 13 | `project_wecom_aibot_authorization_model` | 🔴 见 ⓵：「🆕 待发＝预授权」已被第 8 步两态语义＋发送硬前置三条取代 | **封**，🔴 勿据旧标记发信 |
| 14 | `project_sales_dashboard_git_history_pii` | 🔴 见 ⓵：队列 §四 `#33` 已拍板「风险接受」，非「改天清理」 | **封**，以 §四 `#33` 为准 |
| 15 | `feedback_edit_tool_onedrive_silent_failure` | 主体（OneDrive 路径下 Edit 静默失效）随**仓库迁出 OneDrive** 失效（队列 `#407`／`#413`） | **封**；其 2026-08-06 addendum（worktree 路径错配）判据面已承接 root §5「直读原则」 |
| 16 | `project_queue_file_worktree_divergence_incident` | 2026-07-17 撞号事故的修法**已固化为机制**＝编辑锁工具 ＋ 协议〇.7 | **封**（事故叙事已被机制取代） |
| 17 | `project_sc3_complete` | SC3/SC5/supplychain 收割完成状态（2026-06-11 快照） | **封**；结论已在 root §6 指针 ＋《supplychain收割与全景推进策略》 |
| 18 | `project_sc8_real_cutover` | 12 KB 的 2026-06 过程状态（含多条「待 Paul 裁」，早已推进） | **封**；现状以全景规划 §加速启动总览排期表 ＋ 场景 CLAUDE.md 为准 |
| 19 | `project_ai_zhuanyuan_individual_webhook` | 通道已建成属实，但**「开发环境手动起的进程、非 7×24 常驻」这一边界写于 `.51` 上线前** | **封**（部分过时）；现状以 `5-平台底座/wecom-aibot-service/` ＋ 跟进信 README《企微 chatid 名录》为准 |

### C. 涉纪律（6 件）——逐条确认 CLAUDE.md／队列已有承接

| # | 文件 | 判据 | CLAUDE.md／队列承接 | 结论 |
|---|---|---|---|---|
| 20 | `feedback_pipe_masks_exit_code` | 退出码只认被执行进程自己那一层 | ✅ root 顶部 **OP-0819-F 判据 ⑵ 逐字在 root**（含 `%ERRORLEVEL%` 解析期展开一例） | 已承接 |
| 21 | `feedback_bash_heredoc_backslash_mangling` | 写入端静默损坏、返回值正常 ⇒ 一律回读验证 | ✅ root §5「工具静默回退」硬提示 ＋「乱码文件夹哨兵」写后读回抽验 ＋ `取证方法知识库` §二 | 已承接（落盘扫控制字符的**手法**属技巧，可留 memory） |
| 22 | `project_worktree_uncommitted_input_gap` | worktree 读到分支点旧版；第二形态「读起来正常却已过时、且不报错」 | ✅ root §5「直读原则」＋「工具静默回退」（坏消息会让人追根因，好消息不会） | 已承接 |
| 23 | `feedback_worktree_vs_direct_edit_scope` | 代码走隔离 worktree，纯文档靠编辑锁直接改，冲突时安全优先 | ✅ root §5「执行环境标注」＋ 队列协议〇.7 编辑锁 | 已承接 |
| 24 | `project_yao_zuyi_pronoun` | 姚祖怡是男性；「记忆存在 ≠ 写作时会被调用」，须写完 grep 自查 | ✅ **已承接且已升格**：名录正本 `6-人才与组织/人员名录-称谓与性别-正本.md` ＋ root §1「禁从名字推断」（七名含**祖怡**）＋「读到规则≠执行规则」代词自检 | 已承接；**封存旧版**，一律以名录正本为准 |
| 25 | `feedback_historical_check_must_include_tests` | 改判据前须同时对照生产数据与既有回归测试 | 🔴 **仅命中归档 design.md**，root 与两份队列**零命中** | **缺常驻载体** ⇒ 见定夺项 |

---

## 二、收割结论（三句）

1. **26 件底数与 §四 #135 自陈一致，未被证伪**；分类结果＝**仍真 12／过时 7／涉纪律 6**（＋`MEMORY.md` 索引计入仍真第 12 行）。
2. **涉纪律 6 件中 5 件已在 CLAUDE.md／队列有承接**（其中 `姚祖怡` 那条现行版本比 memory 版更强），**1 件（`historical_check`）无常驻载体**，须补登记。
3. **过时 7 件中 2 件与现行口径正面冲突**（发信授权模型、PII 处置），**这两条是启用 CC 侧 auto-memory 的头号风险**——它们不是错的记录，是**过期的正确记录**，且过期得没有任何信号。⇒ 建议 CC 侧首次启用时**先按本表把「封」类 9 件（B 类 7 ＋ C 类 24 旧版 ＋ 其余）排除出注入面**，再谈增量。

🔴 **旧桶文件本次一个未删、未改、未移**（本件只做登记）。
