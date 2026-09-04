---
status: 在办
title: "进度编年 · CHANGELOG（CLAUDE.md 进度段季度迁移件）"
created: 2026-07-07
用途: R5 接力瘦身——根 CLAUDE.md 顶部"当前进度"区块只留最近一批段落，完全收口（已完成/已合并/已验收）的更早段落季度迁入本文件，按原时间顺序保留，不改写内容。CLAUDE.md 正文留一行指针到本文件。
关联: 根 CLAUDE.md（现行·当前进度）
---

# 进度编年 · CHANGELOG

> 本文件是历史记录，内容不回溯改写。查最新进度请看根 `CLAUDE.md` 顶部"当前进度"区块。

## 2026-06-11 ～ 2026-06-24（首批迁移，2026-07-07）

> **当前进度（2026-06-11）**：**supplychain 收割全部完成，收割队列清空。** 已合 master —— **SC8 收割式 MVP**、§1 平台加固 P2、**O2 齐套**、**SC1 收尾**、**SC3 在途跟踪**（PR #6 rebase-merge）、**SC5 采购建议与供应商遴选 + kit_engine 底座化**（PR #7 已合 master；kit_engine 提升到 `zhuopin_platform/agents/`——SC5 是第 2 消费方、rule-of-three 真触发，O2 改 import 回归零变更；底座 114 + O2 20 + SC5 41 = 175 tests 全绿（合并时点快照，PR #8/#9 后底座实测 117，以 CI 为准不再手工滚动）；黄金值对齐 auto_total=35850/review_total=640000；IATF L1/L2 分桶审计，M015 触发 R1≥50万 待人工审核）。**supplychain 已打 tag `harvested-archive-v1` 转只读存档**（O2/SC3/SC5 三引擎 + 连接器/通知器/business_rules 已迁入全景平台）。**Phase 1 真实接入进展（2026-06-11，IT 提前供数）**：**SC8 真实切换已合 master（PR #8）**——FO+BOM 真实、内部验证不外发（CUSTOMER_OUTBOUND_ENABLED=False）、SRM 降级；**U9C 连接器收敛已合 master（PR #9）**——ZpConnector 确立为 U9C/ERP 唯一规范连接器、退役 U9CConnector、外网 OAuth2+BOM/Query 验证通可拉真实 BOM、real 模式 fail-loud（RealEndpointNotReadyError）。**未结项（详见 `1-转型规划/U9C接入与连接器收敛-待办追踪.md`）**：① 🔴 轮换 U9C client_secret（明文在归档仓 history，活凭据）；② SRM 凭据迁入本仓库 `.env` 解 900401；③ 外网开放 `CommonEntity/Query` 才能做 U9C 全量 cutover（库存/PO/MO/价格），否则 LAN/VPN；④ SC8 对客上线仍待 SRM 接通 + L2 签字（置信度/人工确认/回滚 SOP）；⑤ ErpConnector 改名（低峰期）。续工作先读上述待办追踪 + `1-转型规划/0-全景路线图/supplychain收割与全景推进策略.md`。引擎默认场景本地，第 2 消费方出现才提升（rule of three）。

> **全盘审计 + 文档治理（2026-06-13，Cowork）**：根目录已出《全盘审计与差距分析报告-2026-06-13.md》（底座/场景合规/规划依赖三路审计，发现均带文件:行号）。**P0 四项**：① TLS 校验全局关闭（erp_connector `CERT_NONE`，须先于 secret 轮换修复）；② SC8 `submit_commitment` 低风险自动外发旁路（违反 SOP §4.1/4.2，休眠炸弹，被 test_low_risk_auto_sends 正向固化）；③ audit verify_chain genesis 绕过（任意行缺 prev_hash 被当合法 genesis）；④ client_secret 轮换需硬截止。**代码修复划归 CC 三个变更包**（A 安全 P0 / B 数据正确性+审计强制化 / C SC8 上线前置：偏差监控+真实黄金回归），SC8 对客外发开关在 A2/C1/C2 完成前不得开启。**规划文档修订已由 Cowork 完成**：11 项文档不一致修正、全景规划建立 §0 修订记录机制（"正文不改"改为"可修正+强制登记"）、Phase1 架构文档加过时声明、实施计划新增 §七.2 执行治理（外部依赖红线日+10/12 月砍单规则+Q2 顺延预案+S3 缓冲管理）、新建 `3-治理与合规/OEM数据隔离规范.md`（待签发）与 `1-转型规划/0-全景路线图/待决策清单-2026-06.md`——**清单 4 项已于 2026-06-13 全部拍板（均选 A）**：D-1 SC8 深化不消费 SC6/SC7（"芯片风险→交期→通报客户"闭环移 S3，前提 SC6 稳定≥3 个月）；D-2 Q2 过渡期客诉人工录入 SOP（质量部接口人+校验脚本）；D-3 SC9 降范围 MVP（OEM 历史订单+公开车市数据）；D-4 全场景两级验收（上线验收+3 个月价值验收，指标写进 openspec proposal），落点均已回填对应文档。**阶段命名定稿（全仓统一，见全景规划 §0.1）**：Phase 1 内部 = S1 筑基期（2026-07~12）/ S2 扩面期（2027-01~06）/ S3 深化期（2027-07~12，显式缓冲）；Phase 2 = 产品工程跃升期（2028 H1）；部门内月度节奏 M1/M2/M3；"第N阶段"称谓废止。

> **代码修复 A/B/C 已全量并入 master（2026-06-18，ff-only，master→`3afe318`；PR #10 MERGED，#11/#12 因 ff 后零 diff 无法走合并按钮、已带说明 CLOSED，内容均已落 master 非废弃；文档收口 md/docx/xlsx/审计报告同批并入）**：**A 安全 P0（已修，PR#10）**——A1 erp_connector TLS 默认校验 + `U9C_TLS_INSECURE` 逃生开关(real 硬禁) / A2 `submit_commitment` 首道一律入队 + Notifier 第二道总开关 `outbound_enabled`(SC8 接 `CUSTOMER_OUTBOUND_ENABLED`) + 改写 test_low_risk + 修 approve 持锁重入死锁 / A3 verify_chain genesis 豁免限定第1行。**B 数据正确性+审计强制化 P1（已修，PR#11）**——B1 BOM 失败不静默(返回 (rows,failed_ids)/全失败抛错)+get_bom 走 fail-loud 闸门 / B2 SRM get_confirmed_dates 区分失败与未答交 / B3 审批分级(VP_APPROVERS+KEY_CUSTOMERS，重点客户/首次承诺→VP；金额条件 SC8 暂不可得) / B4 from_env 无 audit→warn + SC8 sources/loaders 注入审计 / B5 OEMRouter 跨库拒绝前留痕 / B6 kit_engine 在途盲区(缺快照仍计在途)+SC5 黄金值改精确相等(35850/640000/675850)。**C SC8 上线前置 P1（PR#12）**——C1 偏差监控 `sc8/deviation.py`(消费 DEVIATION_ALERT_DAYS=3，告警+重算回调+审计)**已修**；**C2 真实黄金回归＝✅已落地（2026-06-18 回 LAN，commit `d77ef4c`）**：FO 已恢复，`build_golden_real.py` 真实跑通——3 张真实订单全部 partial-无反馈→低置信🔴（SRM 看板对 BOM 子件覆盖 17/117、9/90、37/126）、无高置信/无委外样本、确定性日期逻辑手工抽验偏差=0；`real_frozen/` 自包含 `.gitignore=*` 绝不入库；启发式 v0 未改、SRM 取数口径+置信度 2级vs3级待 Paul+PMC 裁。回归：平台136/SC8 51/O2 20/SC1/SC3/SC5 全绿，黄金值不漂移。接口变更(已贯通调用方)：get_bom_for_products/get_confirmed_dates/calc_shortage 均改返回二元组。**🔴 A1（TLS 校验）已在 master，信道已修——IT 轮换 U9C client_secret 定于下周一 2026-06-22（已过 6/20 名义红线，Paul 已知并改约周一）**，先修信道再换钥匙。SC8 对客外发开关仍全程关闭，待 SRM 接通 + L2 签字方可开。

> **质量域规划启动（2026-06-11，Cowork off-LAN，纯规划未碰真实库）**：Paul 第二管辖域转入质量。已出 4 份文档（均在 `1-转型规划/`，AIOps 件在 `6-人才与组织/`）：①《质量域AI数字员工路线图》(8 候选 QD-A..H 打分排序、分层、§5 Q 序列修订)；②《质量旗舰PRD-Q2-8D不良分析与根因》；③《质量旗舰PRD-项目立项审核门禁》；④《AIOps第2名-Onboarding（30-60-90）与团队结构》。**旗舰选定**：QD-A 8D（全景 Q2）+ QD-B 立项门禁（全景 Q6），均 off-LAN 友好、风险可控。**已落地决策**：全景 2.1.3 Q 序列已回填修订（旗舰前置、新增 Q7 IQC/Q8 SPC、FMEA/PPAP 后置，md+docx 同步）；两 PRD 的 D1–D6 全采纳推荐（选 A），8D D3=ISO26262 安全相关走功能安全工程师额外门禁、立项 D2=财务"可机器核规则"边界待财务共识；OEM 隔离边界已扩展（见 §4，质量域含 OEM 信息的 8D/客诉按客户隔离）。质量场景开发排期与 AIOps 第 2 人到位强绑定。

> **SC8/SC1 真实数据口径收口（2026-06-18 回 LAN，已合 master 073117f；PR#13 recalib + PR#14 connector）**：FO 恢复后黄金基准全真实跑通（确定性偏差=0）。① SC8 承诺取数改**分层口径**（/purchase/answer 按 PO 主源 + 看板辅 + 无反馈+30 兜底，见 SOP §4.6）——子件覆盖 9/90→58/90，并暴露 S02Y.0188 瓶颈子件真实承诺 → 延期 +61→+184（看板低估被纠正，**待 PMC 核实 + 对客沟通**）；真实数据仍只命中"无反馈"类、全低置信🔴（成品全子件都有承诺不现实，低置信是对的，未为凑高置信伪造）。② SC1 交付维度过渡修正：数据不足→不评分+权重归一化（ZB0022 5→4级、0% 假象消除）；真实历史准时率待 U9C 收货历史(Receivement)（待办 #7）。③ connector 修复（PR#14）：get_demand_orders `pdrNo`→`poErpNo`（旧测试夹具同错掩盖 bug，已改真实字段+加回归）。④ FO 健康告警随 PR#13 合入（内部运维告警→audit+企微采购/值班群，非对客）。回归全绿（平台 138/SC1 53/SC8 64，含 test_golden_real 真实夹具零漂移）；**对客闸 CUSTOMER_OUTBOUND_ENABLED 全程 False**，real_frozen/+reports/+.env 经 git check-ignore 不入库。置信度仍 2 级（签字版未动）。新增待办 #9（sc5 openspec 缺 SHALL/MUST，预先存在、非阻塞）。

> **FO 正式库接通 + 保供看板四色 + 保供 Web 服务（2026-06-24）**：① **FO 取数口径纠错并接通正式库**——旧 `.env` 误把 `FO_API_BASE` 指向 supplychain 验证库(192.168.100.51:8800,5月陈旧数据)；正式库 webapi 原无 FO 查询接口，IT 同日交付 `GET /zp/api/ForecastOrder/Query`(apiKey 走 URL query、非 OAuth2)；loaders 已改造(新端点/分页/`Data.Rows`/PascalCase 字段/apiKey 不入异常日志/fail-loud)，真实跑通 FO2026060001/2 共 126 行/36 成品(status=2)、携客云承诺覆盖 341/1042。② **保供四色口径**(Paul 2026-06-24 定，剔除无答复估算、只看确定承诺缺口)：🔴 真延期(有承诺仍晚>3天) / 🟠 待催(子件未答复无确定承诺) / 🟡 偏紧(确定1-3天) / 🟢 按期；真实 49🔴/77🟠。③ **保供预警 Web 服务**(openspec `sc8-baoguan-web-console` 已 apply)：Flask+waitress(`sc8/webapp.py`+`scripts/run_baoguan_web.py`,默认 `0.0.0.0:8090` **LAN 无鉴权**)、进程内 `compute_snapshot`+`SnapshotStore` 缓存(reports/JSON)、手动刷新(非阻塞锁串行,防携客云限流击穿)+6h 定时后台刷新、🔴 真延期去重(稳定键 料号+单号+出货日=案例账本)推保供运维群、**保供案例处置中心**(催货→协调→改期/确认→关闭 状态机+SLA 24/48/72h,SQLite)、AI 催货/协调/对客草稿(`case_draft.py`,对客落 `CUSTOMER_OUTBOUND_ENABLED=False` 仅草稿不外发)。回归 **102 passed/2 skipped**(SC8 +27 新测试)，reports/*.db/*.json/.env 经 git check-ignore 不入库。**未结**：7.2 LAN 真实联调=Paul 现场验收(手动刷新打真实三源、🔴 推企微)；验收后加登录/Token 鉴权再开外网(待办 #10,真实客户名红线)。

## 2026-07-03 ～ 2026-08-02（第二批迁移，2026-08-05）

> **迁移依据**：R5 文档治理规则「CLAUDE.md 本段完全收口的旧段落季度迁本文件」——上次执行 2026-07-07，本次为逾期补做（队列 #253 / C4）。**原文原样迁入，未改写一字**；根 CLAUDE.md 进度段此后只留最近一批（2026-08-04 ～ 2026-08-05 共 5 条）＋ 一行指针。**本节内条目按原 CLAUDE.md 中的排列顺序保留（该顺序本身非严格时间序，未重排）。**

> **队列 #206：proposal 强制门禁段迁 `openspec/config.yaml` rules（2026-08-02，CC，独立 worktree `openspec-config-proposal-rules-f452d3`，openspec 变更包 `openspec-config-proposal-rules`，commit `e912434`，已归档 `archive/2026-08-02-openspec-config-proposal-rules`）**：2026-08-02 #205-A 实证 `openspec update`（1.4.1→1.7.0）会把硬写在 `.claude/commands/opsx/propose.md` 里的《知识资产三问》《验收与晋档条件》两个强制节**整段静默删除**（当时已手工还原+加警示注释，但那只是把同一颗雷埋回原处）。Shao Peishen 拍板走「选项 A」根治：走 openspec 变更包 + design 审，把两节的规则文本迁进不受 `openspec update` 覆盖的 `openspec/config.yaml` 的 `rules.proposal`。**A1 可行性验证（关键产出）**：源码定位到字节级——`dist/core/update.js` 全部写/删动作只落 `skillFile`/`commandFile` 两类，`config.yaml`/`schemas` 结构性地不在覆盖范围内；`rules` 是运行时读取（`instruction-loader.js::generateInstructions()`），非构建时烘焙。**用两个互相独立、事先均不知情"这是在测 rules 机制"的子代理做盲测**：仅按标准流程执行 `openspec instructions proposal --json`，盲测 1（propose.md 留指针注释）与盲测 2（propose.md **完全不含**任何本项目定制内容、纯上游文案）**均成功生成完整两节**，盲测 2 里子代理还自主识别并正确解决了"rules 不进产出"与"该条 rule 显式要求成文"的语义张力——**结论：rules 语义匹配，不需要转 A2 自定义 schema 载体**（已在 design.md 记为备选方案，未采纳：自建 schema 会与上游永久分叉、需手工跟 diff，A1 已证明不必要）。**C3 抗覆盖验证（本件目的）**：固化改前 SHA256 → 真跑 `openspec update --force`（比普通 update 更严格，强制重写而非"已最新跳过"）→ `config.yaml` 哈希改前改后**完全一致**，`propose.md` 指针注释按预期被删除（已重新补回，design.md 已记录这是防御性冗余、非机制必需）。**顺带验证 #195 相关观察**：`--force` 同时重写了另外 4 个 opsx 命令文件 + 5 个 skill 文件，`git diff` 显示除 propose.md 外均无内容差异——证实截至本次，本仓库只有 propose.md 一处带定制内容，其余暂无同类风险（现状确认，非未来免疫承诺，已记入 #195 行）。openspec 变更包 `skip_specs: true`（零 capability 变更），Shao Peishen 已批准 design 决策 (a)，`/opsx:archive` 归档完毕。**未做**：本仓库其他 `.claude/commands/opsx/*.md`（apply/archive/explore/sync）是否也存在同类硬编码定制风险——本次未系统排查，只确认 propose.md 这一个已实锤命中的点；3 个现存长驻 worktree（`musing-pascal-68d14e`／`qd-b-grayscale-improvements-9dbe6f`／`wecom-service-home`）尚未快进到含本次改动的 commit，按各自任务节奏自然同步，未特意提前对齐。顺带发现一个既有缺陷（与本件无关，已 spawn_task 登记）：`openspec/specs/platform-oem-isolation/spec.md` 一条 Requirement 缺 SHALL/MUST 关键词，`openspec validate --all --strict` 报 1 个既有失败。详见队列 #206 与本变更包 `openspec/changes/archive/2026-08-02-openspec-config-proposal-rules/design.md`。

> **sweep 与机器人机制五行同批修复：#192/#193/#194/#198/#199（2026-08-02，CC，openspec `sweep-aibot-reliability-batch`，commit `5601c0e`）**：环境保障线派单件五行整批交付（详见队列 #192/#193/#194/#198/#199 各行回填）——**A/B/C（#192）**：`工具-落库sweep.py` 起跑段新增 flush `pending_queue_lock_appends.jsonl`（子进程隔离调用新建 `scripts/flush_pending_lock_appends.py`，不在 sweep 进程内 import aibot_service/zhuopin_platform，规避多 worktree 共享 editable install 劫持风险）作**双载体**主载体（每小时，`decision_reminder_check.py` 每日调用为第二道）；`find_unreconciled_archives` 新增识别 `queue_append_pending_flushed` 为配对事件，修复推迟补录路径被哨兵误判"未配对"；`run_aibot_service.py` 两个 pending 暂存文件路径改走 `resolve_repo_root()`（与 #126 对齐），历史 6 条残留已确认清空。**#194**：sweep 起跑段无条件检查未推送提交并补推，不再绑定"§二有无待处理批次"（07-31/08-01 多次真实复现"提交成功推送失败、下一轮空转"，230 轮 7 次 schannel 失败）。**#198**：(a) `main()` 新增通用异常兜底（独立退出码 3+UTC 日志+webhook 告警，日志零行判据恢复单义）；(b) 起跑段编辑锁前置探测（占用即零 git 动作跳过——**过程中发现并修复一个既有 bug**：`_edit_lock()` 此前对 `status` 子命令也无条件带 `--who`，会被 argparse 拒绝，探锁功能原会静默失效）；(c) 批次落库后命中常驻服务路径给部署提示。**#193（P2）**：新增 `disconnect_inprogress_alert.py`，断连超 75 秒经独立 webhook 发"进行中"提示（同一次断连不重复）；接线时发现"无条件构造 monitor 会在既有同步测试场景下报 `no running event loop`"，已改为特性开关模式规避。全量回归零漂移：wecom-aibot-service 240 passed 1 skipped（+18 新测试）、sweep 30 passed（+13 新测试）。**真实部署+验证**：`ops/wecom-service-home` 已 ff 到最新提交，重启 `ZhuopinAibotDevListener`（新 PID，文件哈希+审计新事件交叉确认生效）；合入 master 后手动+自动各触发一轮 `ZhuopinCommitSweep`，日志确认新起跑段真实运行。**#199**：`register-decision-reminder-task.ps1` 源码已补 `-StartWhenAvailable`；`0x800710E0` 触发条件如实标注"物理上不可回溯"（Task Scheduler 操作日志当时未启用，无历史事件可查）；对齐在跑任务设置+#193 次要项（`AtStartup`+`RestartCount`）+启用诊断日志三件合一，整理为提权代码块 `1-转型规划/0-全景路线图/提权代码块-队列199与193次要项-2026-08-02.md`，待 Shao Peishen 执行。**⚠️ 过程事故如实登记**：本次 session 前段因路径构造习惯性使用主工作区路径而非按开场词要求新建的 worktree 路径，导致所有源码 Read/Edit/Write 与测试运行实际发生在主工作区（而非 `qd-b-grayscale-improvements-9dbe6f` worktree）——已及时发现（git status 交叉核对），通过"worktree 侧 `git switch --detach` 让出分支名 → 主工作区 `git checkout` 到该分支承接已有未提交改动 → 提交推送"补救，内容无损失，全程测试均针对含真实改动的物理文件，未受影响；该 worktree 现为 0 提交 detached HEAD 空壳，物理目录删除因句柄占用失败（同 #125/#207 已知模式），已 `git worktree prune`，物理空壳留待下期体检清理（同 `sweep-criteria-sync-fix-7eb8a7` 先例）。

> **台面清理执行清单收尾：队列 #165／#101②③／#166／#125／#207（2026-08-02，CC，主工作区直接执行，无 worktree）**：按 `台面清理执行清单-worktree与stash-2026-07-31.md` 执行「执行前重跑核验三连」后，发现台面早已比 07-31 快照小很多——07-31 记录的 10 个 A 类空壳 worktree 目录里 8 个已被此前某 session 清理（未留痕，本次不重复计功），实际只需再清 2 个（`queue-numbering-alert-criteria-855665`／`fi2-regression-queue-reconcile-07bab3`）。**B 类两个有内容 worktree**（`fi2-validation-prep-66ed2c`=#165(b)/#207⑤同一目标、`sweep-criteria-sync-fix-7eb8a7`=08-02 追加"#197用完可清"）核验 `status --porcelain`/ahead 计数干净后删除；`fi2-validation-prep-66ed2c` 额外按 B3 补注独立复核 `git diff`，确认其唯一脏文件是 #79 行早已被 master 取代的陈旧副本，非丢失。**⚠️ 新发现：`Remove-Item -Recurse -Force` 与 `git worktree remove`（#125 已记录的旧教训）一样非原子**——两次删除都在中途遇句柄占用；`fi2-validation-prep-66ed2c` 最终整体删除成功，`sweep-criteria-sync-fix-7eb8a7` 内部文件清空但目录外壳本身连续两次重试仍 `Permission denied`（排查非 OneDrive/非并发 claude.exe 占用，`SearchIndexer` 在跑，疑为其瞬时扫描所致）——**跳过强删，留 1 个 0 文件空壳待下期体检顺手清**，已如实登记不隐瞒。`git worktree prune` 清除 3 条陈旧 `.git/worktrees` 元数据（含 #125 的 `affectionate-herschel-c26958`）；**#125 随之执行销行**（连同分支 `claude/md2word-checkbox-control-089198` 一并 `git branch -D`）。**3 条 stash** 已导出 patch 备份至本机沙箱临时目录（未入库）；`git stash drop` 首次尝试被 Claude Code 自动模式安全分类器当场拦截（判定为不可逆销毁操作），**Shao Peishen 会话内重发命令明确授权后重试成功，三条全部 drop、`git stash list` 核验为空——#101②③ 随之销行**（①仍未动，维持待领）。**#166** 按 Shao Peishen 会话内指示"默认只落③判定口径、不动协议〇.5"结案——只采纳"worktree 身份判定一律以 `git branch --show-current` 当刻实测为准、不依赖目录名"这条原则性口径，未落地 WHOAMI.md 刷新机制（②）、未改协议〇.5 文本。**#207 五个长驻 worktree 纪律滞后问题的最后一个（⑤ `fi2-validation-prep-66ed2c`，此前 4/5 会话刻意搁置移交本行处置）随本次删除自然解决，5/5 全部处置完毕**。**收尾核验**：`git worktree list`＝3 linked（`musing-pascal-68d14e`／`qd-b-grayscale-improvements-9dbe6f`／`wecom-service-home`，服务全程未动）＝`.git/worktrees` 元数据数，一致；物理目录数比注册多 1（上述删不掉的空壳）；主工作区 `git status` 干净。**跨期未收口项（如实登记，非隐瞒）**：仅剩 1 个空壳目录（`sweep-criteria-sync-fix-7eb8a7`）待重试删除，无数据/安全风险，纯待办；stash 已随 Shao Peishen 后续授权清零，不再挂账。详见队列 #165／#101／#125／#166／#207 各行回填。

> **队列 #171/#172/#180/#164 四件套：sweep分叉告警／决策提醒机制／未同步标记自愈／裸竖线清理（2026-07-31，CC，独立 worktree `loving-mestorf-98749e`）**：四项同族——"该让人知道的事没人知道"。**#171（P1）**：`工具-落库sweep.py` 起跑前置分叉检测此前失败即静默退出码 0（计划任务看到"成功"），且全文无任何告警通道；新增 `SweepAbort.is_fork` 标记，命中时退出码改 2 + 复用 `发企微.py` 同款零依赖 webhook 主动推送、连续分叉按 `reports/sweep-fork-state.json` 记轮次、分叉解除自动清空，5 个新测试（含本地 HTTP 桩验证真实 webhook POST 内容）。**#172（P2，服务侧能力）**：新增 `aibot_service/decision_reminder.py`——§四"需 Shao Peishen 的动作"表无独立状态列，实证（对 #33-#40 八行逐行核证）得出判据"截止列含✅即已关闭，不看整行"；统一判定函数同时承载"新增即时提醒"与"超期每日汇总"两层，按 1/3/7 天递减间隔升级去重；新增 `scripts/decision_reminder_check.py`（一次性触发）+ `register-decision-reminder-task.ps1`（注册每日 08:30 `ZhuopinDecisionReminderDaily`），26 个新测试覆盖新增/超期/去重/静默期四类。**🔴 分工缺口**："巡逻收工即时提醒"调用点在拆件巡逻定时任务 prompt（仓库外，CC 改不了），需 Cowork 在该 prompt §四步骤 5 后加一句调用，详见队列 #172 行。**#180（P2）**：`queue_git_sync.py` 的"⏳未同步"标记此前只加不清（实证 #149/#175 两行早已同步成功、标记仍挂着）——新增 `_clear_unsynced_markers`（即将提交前清掉文件内全部残留标记），插入位置由"编号列后"改"行末尾"，5 个新测试，顺带清理 #149/#175 两条过时标记。**#164（P3）**：队列 #111/#112/#115/#125/#130/#144 六行裸竖线致列数偏离标准 8 列（#125 达 10 列）改写为全角／，协议〇.8 补一句禁写裸竖线，`工具-文档台账生成.py` 新增列数≠8 自检（7 个新测试）。全量回归：sweep 17 + 台账 7 + aibot-service 222(+31) + 平台 244 passed 1 skip，零回归。**真实部署验证**：①sweep——push 后主工作区触发 `Start-ScheduledTask -TaskName ZhuopinCommitSweep`（当时主工作区恰有另一并行 CC session 未提交改动，`sweep-commit.log` 新增 `2026-07-31 05:43 UTC` 时间戳，正确因"本地落后 origin 但 --ff-only 合并失败（未提交改动会被覆盖）"优雅跳过、未强推不误伤，验证了新代码路径在真实环境不崩溃且安全门依旧生效）；②`ops/wecom-service-home` 同步（`git merge --ff-only`）+ 重启 `ZhuopinAibotDevListener`（先清理 `Stop-ScheduledTask` 未级联杀死的孤儿进程，单实例干净重连，文件哈希比对确认 `decision_reminder.py` 新代码已部署）；③注册 `ZhuopinDecisionReminderDaily`（每日 08:30）——**过程中两次真实踩坑并修正**：(a) 注册脚本最初用 `LogonType S4U`，实测在本机注册新任务报 `Access denied`（S4U 需要"以批处理作业登录"权限，赋予该权限本身要求管理员权限，即便任务运行期不需要，已隔离验证 S4U 失败/Interactive 成功），改用 `LogonType Interactive`（同 `ZhuopinAibotDevListener` 既有先例），代价是任务触发时需当前用户已登录本机；(b) 脚本不显式指定队列锚点时按自身 `__file__` 反推仓库根，会读到 `ops/wecom-service-home` worktree 自己的队列文件副本（需手动同步、可能滞后）而非主工作区实时内容，审计也分裂写入这个 worktree 自己的 `reports/`——与 #126 修过的同类问题同源，包装脚本现显式设置 `WECOM_AIBOT_QUEUE_PATH` 指向主工作区队列文件后修正。修正后真实触发一次，`decision_reminder_sent` 审计事件（`2026-07-31T05:56:56 UTC`）与主工作区 `reports/decision_reminder_state.json`（9 项候选）均落在正确位置，企微私信 Shao Peishen 真实送达。**⚠️ 一个真实观察，未修复，留痕供参考**：触发瞬间主监听 `disconnected`（reason: no close frame received or sent）→ `reconnecting` → `connection_established`/`authenticated`，约 2 秒内 SDK 自愈完成，无消息丢失（企微协议本无离线补推能力，`gap_alert` 阈值 3 分钟未触发告警属预期）——与 #90 D5/#110 此前多次提及的"同 BotID 双连接"风险同源，此次是首次真实观测到其发生但影响轻微（仅一次性脚本短连接触发，非持续并行）；每日一次、~2 秒窗口的残余风险已知且可接受，若未来观察到实际消息丢失需重新评估架构（如改走独立测试 BotID 或纯 webhook 通道）。

> **队列取号与告警判据三件套（2026-07-30，CC，独立 worktree `queue-numbering-alert-criteria-855665`，队列 #168／#163／#147）**：环境保障线取证发现的三处"把需要判断的事交给拿不到判断依据的执行者"同构缺陷，一批修完。**#168（P1，已部署）**：企微机器人 `queue_appender.append_pending_task` 此前完全绕过协议〇.7 共享编辑锁，人类持锁编辑期间机器人直接写盘会被稍后整文件写回静默覆盖——新增 `queue_edit_lock.py`（复用既有 CLI 工具当子进程调用）+ `queue_lock_pending.py`（锁忙时消息仍正常归档、只推迟队列行，暂存 JSONL，下条消息到达时自动补录+续走 git 同步），14 个新测试含真实子进程复现"持锁方读入→机器人追加→持锁方写回"场景。**#163（P1）**：编辑锁 `acquire` 增 `--reserve N --section 一／四`——2026-07-29 #162 撞号证明"回显高水位线让人 +1 续排"不足以防错（回显打在眼前，人仍看漏），改为工具直接分配并原子回写字面编号，12 个新测试；顺带闭合 #146 遗留的"人工取号路径无消费方兜底"死角。**#147（P2，已部署）**：`gap_alert` 此前用"距上次审计事件"当"中断时长"，但审计"有事才写"非"活着就写"，07-29"中断约 79 分钟"即误报（服务全程健康只是无人说话）——新增 `liveness.py`（每 5 分钟覆写独立存活戳文件，刻意不进审计链），判据改为"距上次确认存活"，"距上次有人发消息"降级为纯信息展示，23 个新/改测试。#168/#147 均真实部署 `ops/wecom-service-home`+重启验证（文件哈希/进程启动时间/存活戳生成三种方式交叉确认新代码确已生效，而非"运气型"未改动假象）；#163 为独立 CLI 工具、无需部署。全量回归 191(本服务)+22(编辑锁工具)+245(平台) passed 1 skip，零回归；commit `56577d8`/`0c96982`/`16135b1` 已 push master。07-29 15:38 触发来源未定位（发生在修复前，无新证据），如实留白。协议〇.7 已补机器人受锁写入方一句；协议条文改写与两份 skill 源码同步留给 Cowork（分工红线）。详见队列 #168/#163/#147 与 `5-平台底座/wecom-aibot-service/CLAUDE.md`。

> **FI2 三单匹配面板 v8 改造（2026-07-31，CC，独立 worktree `fi2-web-service-16da2a`，队列 #182/#183，Shao Peishen 拍板高优先插队）**：唐燕萍 07-31 回件权威规格书（`7-外部文档/财务部/...FI2面板改造指令及效果图-382fedaf...docx`，用 python-docx 解压全文+两张效果图逐字比对，非文字脑补；同批发错的《改造后的FI2三单匹配面板效果》已由她本人声明作废）驱动的展示层重建——六段式平铺 → 结论看板 + 展开/并拢主表（10 列窄表，点击行号展开三张单据卡片 + 六个校验块）。**红线（她原话“信息全保留，只换看法”，Shao Peishen 已拍板本次跳过 openspec design 审）：只改 `fi2/webapp.py` 一个文件**——新增 `_run_with_detail()` 是 `fi2.run.run()` 同一套函数调用序列的原样复用，只多返回中间产出的原始明细行供展开详情用；`match_engine.py`/`result_classify.py`/`price_check.py`/`recon_report.py`/`config.py`/`models.py` 零改动，判据/容差/五类判定优先级不变。#183 免责声明按其给定文案+浅黄底加粗样式上线（结论看板下方、主表上方）；#175⑤口头指令：“超差不代表一定是记账错误”提示语从独立第五段改为跟随“四维匹配”校验块，仅 PO↔AP 有差异时才在展开详情底部自动带出；孤立发票并入主表一行（规格 3.8），不再单列区块。**诚实边界（不伪装已判定，FI2 一贯红线）**：v8 规格新增的 OCR 字段校验/重复发票检测/税率合规/PO变更检测四维，本引擎均未实现（税率合规·重复检测明确属本场景“二期”范围、OCR 选型未就绪、PO变更检测已于队列 #80 评估后明确不采纳），面板如实标注“二期未接入”灰色徽标，不杜撰判定结果；展开卡片内的原始单据金额仅当次会话即时展示，不落审计/报告持久化（金额脱敏红线 D7 约束的是落盘，`build_report()` 调用与落盘内容较改造前完全一致）。`test_webapp.py` 全量重写匹配 v8 结构，FI2 99 passed+7 skip（原95+7）、平台 244 passed+1 skip（零改动，验证判据零漂移）。真实部署 `.51:8094`，冒烟三件套全绿（`/api/ping`/首页经 `X-Auth-Token` 访问/真实 POST `/run` 跑通 mock 全链路，v8 结构关键字逐项核对命中）。**未做**：交付后需财务专线按 #144 范式请唐燕萍/李姣龙抽验确认（登记待办见队列 §四）；“已补充待审核”态本引擎真实计算结果中不存在（无 ERP 回流自动感知机制），故当前只有 BLOCK 初始态的“退回原因”信息按钮，无“确认通过/退回”可操作按钮。详见队列 #182/#183 与`4-数字员工/财务部/FI2-三单匹配自动对账/CLAUDE.md`。

> **企微智能机器人 · 队列 #126 跨 checkout 失效+审计文件分裂双缺陷修复（2026-07-28，CC，独立 worktree `queue-git-sync-worktree-fbc10f`）**：机器人常驻 `ops/wecom-service-home` worktree、队列文件固定指向主工作区，`queue_git_sync` 此前无条件信任调用方传入的 `repo_root`，07-28 真实命中"队列文件 is not in the subpath of worktrees\wecom-service-home"报错，git 同步整条降级（audit `queue_sync_degraded`），当日两轮队列撞号（#126/#127/#128）即由此而来（详见队列 #126 行内记录）。**修法①**：新增 `5-平台底座/wecom-aibot-service/aibot_service/repo_paths.py::resolve_repo_root()`——以队列文件为锚点动态问 git "你真正所属的仓库根在哪"（`git -C <锚点父目录> rev-parse --show-toplevel`，与 07-23 编辑锁 `--git-common-dir` 修法同源思路），`WECOM_AIBOT_REPO_ROOT` 环境变量提供显式覆盖口，解析失败才回落原有行为；同步失败时新增队列文件内"⏳未同步"显式标记，不再只留审计事件+私信告警。**顺带发现并修复一个从未被端到端测试覆盖的隐藏 bug**：`intake.py` 已独立落盘一行后，`sync_after_archive` 内部此前又无条件重新调用 `append_pending_task` 二次追加同一内容——checkout 校验此前每次都提前抛异常掩盖了这个问题，修法①一旦生效即会在生产暴露"同一条消息两行"，新增 `already_appended_row` 参数堵住。**修法②**：常驻服务与一次性脚本 `push_followup_letter.py`（跑主工作区）此前各自反推仓库根，`reports/wecom_aibot_audit.jsonl` 分裂成两个物理文件（worktree 版 636 行/主工作区版 41 行），发信与回件留痕从未同处一份，IATF 可追溯性打折——两脚本改用同一套动态解析统一落点，历史两份按 timestamp 归并为一份（677 行，原件另存 `-split-archive-2026-07-28` 保留不删），hash 防篡改链按合并后顺序重新计算，`verify_chain()` 核验通过。TDD 全程新增 18 个测试（覆盖同 worktree/跨 worktree/跨 repo 三种拓扑），全量回归 153(本服务,+17)+218(平台) passed 1 skip，零回归。详见队列 #126 与 `5-平台底座/wecom-aibot-service/CLAUDE.md`。

> **FI2 v3 引擎收尾归位入 master（2026-07-18，CC，队列 #2/#16/#51）**：`feat/fi2-v3-recon-engine` 分支上已完工的 FI2 v3 引擎重构（R1/R5/R7 定稿真值+R5 门禁+料品编码归一化，Paul 已两拍板收口 D14 开放点）此前因主工作区长期停在 detached HEAD 未同步 master、落后 44 提交。Paul 拍板"现在就归位，选最稳妥办法"——不做整支 rebase，改走临时 worktree + 精准 cherry-pick（预检确认 master 分叉点后未改动过 FI2 目录，零冲突），FI2 场景 61 tests + 平台底座 193 tests+1 skip 全绿零回归。**发现一个结构性副作用并已根治（队列 #52）**：`master` 分支曾被长驻 worktree `wecom-service-home`（企微机器人服务，见下方队列 #49 条）独占 checkout，导致主工作区一度无法字面 checkout `master`（先用分支指针复用变通）。Paul 拍板"要用最规范方式，主工作区未来仍以字面 master 呈现"——已将 `wecom-service-home` 迁至新分支 `ops/wecom-service-home`（同 commit checkout，零文件改动、零服务中断，计划任务路径不受影响），`master` 随即释放，主工作区现字面持有 `master`；临时指代用的本地 `feat/fi2-v3-recon-engine` 分支已删除，`origin/feat/fi2-v3-recon-engine` 远程存档保留不动。新惯例：长驻服务类 worktree 统一用 `ops/<用途>` 前缀命名。真实数据验证仍按 8 月底排期不变。详见队列 #51/#52。

> **销售域实时数据接入 · 数据管道落地（2026-07-20，CC，队列 #53）**：AI 运营指挥中心销售域此前只有 Cowork 接好的客户端 `fetch(SALES_DATA_URL)`，数据源尚未落地。**开工前先问 Paul 两点歧义**（遵《歧义先确认再动手》全局纪律）：①命令中心目前只是仓库内静态原型（从未部署 .51），本次是否要一并把它也部署成 .51 新服务——Paul 选**只搭数据管道**，命令中心本身正式部署到 .51（新端口/服务/计划任务）留作后续独立发布任务；②`high_risk_leads` 联系人姓名/电话/邮箱面向谁展示（原型无任何访问控制）——Paul 选**先脱敏展示**，范围待与销售域接口人（泓钦）后续对齐再放开。据此新增 `1-转型规划/AI运营指挥中心/sync_sales_data.py`：把 SalesMarketing/crm_data/dashboard_data.json 同步到同目录 `data/sales_dashboard_data.json`（同源相对路径，免 CORS），**脱敏在数据落盘前做**（而非只在前端隐藏——直接 fetch 该 JSON 端点也拿不到真实联系方式），静态快照表格与实时渲染两条路径同步改过。本地起 `python -m http.server` 真实验证：徽标由「骨架接入·快照数据」正确转「● 实时 · 同步 2026-06-25 18:08」、数字与源 JSON 一致；断源（临时移走数据文件）时正确回落 2026-06-25 静态快照、控制台无报错。`1-转型规划/AI运营指挥中心/data/` 已加入 `.gitignore`（含客户线索数据，不入库）。**⚠️ 顺带发现一个预存问题**：本文件更早一版（commit `6ebf962`，07-06）已把这批高危线索的真实姓名/电话硬编码进静态快照 HTML 并推送 master——即脱敏前，这些客户联系方式已经躺在 git 历史里；本次只修正了"当前文件内容"，未处理 git 历史中已存在的旧版本记录（改写历史属破坏性操作，需 Paul 另行拍板是否要清，已在收工报告提醒）。

> **采购域 v2.3 场景重排（2026-07-06，重组循环第 2 例，总线执行完成）**：姚祖怡 v2.3 需求经采购专线三步法梳理（Paul 三处裁决+链冲突裁决+批改回灌全认可）→ 总线跨域四裁决（SC6 **注销**并入 O2 作链 A 首节点、SC9 **并入 S6** 波动子功能、SC7 **两期制** ①2026-09 承接原 SC5 引擎/②2027-01 深化、SC10=2027-03/SC11=2027-04）→ 全景/实施计划/前置总表/甘特/四链端点零残差重排，**采购 9→7、全景 42→40**。SC11 加 PMC 确认门禁（AI 不自动落 ERP/不自动外发）。CC 移交：SC3/SC5 引擎（29/41 tests）+SC5 黄金基准迁移小 openspec。甘特图改名去数字化（`全景甘特图-场景排期.html`）。同日 U9C 通道整体打通（`Stock/Query` 库存实时源，体检 P0-1 关闭）；治理两件生效（数据分级路由表·法务签发 / 年度达标线·CEO 对齐）；四域专员实名（姚祖怡/唐燕萍/陈忱/泓钦）。**财务域 v2（同日，重组循环第 3 例，轻量）**：FI1 条件复启暂缓（封存不废弃——mock 30 tests+confirm.py 留库，复启三条件见全景 §2.1.4；唐燕萍批改回灌全认可+首轮重编号补签），编号 FI1-FI10 与全景 40 不变；批次2 摘 FI1 试点、收口-1 批改会取消；7/15 双反馈门焦点当时转 FI2/FI3（SRM 900401+OCR+U9C 财务侧端点覆盖待 IT 核）——**此句已于 2026-07-09 财务域 v3 口径修正后过时，财务侧数据闸已实质解除，见下段**，财务 2026 价值兑现主打 FI2/FI3。

> **SC3/SC5 引擎归属迁移已完成（2026-07-06，CC，`sc-v23-engine-migration` 已归档，commit `8d8bde7`）**：上述 v2.3 重排移交给 CC 的引擎迁移任务已执行——SC3「供应商在途跟踪」引擎（29 tests）原样迁入 SC8 作内部子模块 `sc8/answer_confidence_engine.py`/`answer_confidence.py`（答交可信度评分，SC8 置信度 2→3 级化判据源，本次只搬代码未接线现有承诺流水线，未碰 `sc8-real-data-cutover` 变更包）；SC5「采购建议/供应商遴选」引擎（41 tests）原样迁入新场景目录 `4-数字员工/采购部/SC7-库存优化建议/`（`sc7_inventory` 包），黄金基准 35850/640000/675850 精确保留不漂移；`kit_engine` 底座件不动，O2/SC7/SC8 继续共同复用；审计 `scenario` 标签随新场景改写（SC3→SC8、SC5→SC7）。旧 SC3/SC5 场景目录清空为 README 指针+CLAUDE.md 退役说明，environment 同步卸载/新装。全量回归：SC7 41 passed，SC8 143 passed + 2 skipped，零回归。openspec specs 落盘 4 个新 capability，4 个退役 capability 因 CLI 限制改为归档后手工移除（内容已 100% 承接，非丢弃）。**未做**：开场 prompt D 段（FI1/缺料批改会备料，两场日期均已约）、E 段小件（VP_APPROVERS 加孙涛等）留下次会话。

> **财务域场景重编号（2026-07-03，全景路线图 Task 执行）**：财务专线定稿（Paul 确认小抄 13 项全通过）后，全景规划/实施计划/前置数据总表/甘特图已同步重排——原 FI2 智能月结拆分为 **FI2 三单匹配自动对账**（提前至 09 月）+ FI4 月结其余（2027-Q1）；原 FI4 异常交易拆分为 **FI3 付款申请自动校验**（提前至 11 月）+ FI6 异常交易其余（2027-Q2）；原 FI3/FI5/FI6/FI7/FI8 顺延为 FI5/FI7/FI8/FI9/FI10；财务 8→10、全景 40→42；FI2/FI3 治理 L3→L4 分期，FI3 的 L4 晋级 Paul+CFO 会签。前置卡口挂 7/15 双反馈门（U9C CommonEntity/Query + SRM 900401 + OCR 选型）。

> **库存实时源落地 + 缺料/保供 P0 数据根治（2026-07-06，CC）**：卓品现货此前读不到（`get_inventory` 桩恒 0 / SC8 保供无库存入参）→"有货却被追料"误判（采购 P0）。用友标准库存端点 `Invtrans/QueryQohAndAvailable` 有**原厂 SQL bug**（`IsProdCancel` 拼 SQL，已提原厂修、ETA 不可控）——**改走卓品自建 `GET /zp/api/Stock/Query`**（apiKey，vendor-independent，与 FO 同范式；IT 2026-07-05 测试库交付）作库存实时源。**DB 直连 / SOAP 均侦察后弃用**（DB=sa 超管+明文口令不安全 + 有写回诉求；SOAP `IBatchQueryItemQtySVR` 喂确有货料号仍回 0，已证伪）。**已合 openspec `stock-api-inventory-source`（归档 `archive/2026-07-06-*`；branch `feat/stock-api-inventory-source` 已推 GitHub，未合 master）**：`ZpConnector.get_inventory(material_ids)` 逐料号并发 + 按 ItemCode 精确匹配 + **六仓白名单**（WW01/ZP01/ZP21/ZP22/ZP02/ZP23，排除不良品仓/委外线边仓，Paul 2026-07-05 定）聚合 `AvailQty`（ERP 可用量口径，Paul 认可 D3）→`current_stock`；apiKey 脱敏、real fail-loud、audit 留痕、旧无参接口向后兼容；测试库验收 R01A.0012=3,153,195 逐仓对 DB `InvTrans_WhQoh` 精确一致。SC8 保供**现货净额**入参 + **`SC8_NET_INVENTORY` 开关默认关（零四色漂移）**；翻 ON（消除现场误判）须**采购专员重核保供黄金基准 + 登记原因 + 签字**（档2→档3 晋档条件）。全回归绿：平台 146 / O2 20 / SC5 41（黄金 35850/640000/675850 不漂移）/ SC8 114。**未结**：① 翻 SC8 开关排期（专员黄金重核）+ 生产 `STOCK_API_BASE`/key；② ✅ **两条独立安全隐患已收口（2026-07-31 Shao Peishen 拍板结案，源 IT 陈承 07-30 回件）**——(a) `supplychain/.env` 的 **sa 超管 + 明文口令**（生产库 192.168.6.2）：IT 以**补偿控制替代口令轮换**，Shao Peishen **拍板接受该残余风险**（原验收口径为「轮换或禁用 sa」，本次按 IT 处置方式变更结案）；**✅ 本地明文口令已删除（2026-07-31）**：经取证确认 DB 直连确已无人使用（supplychain 仓库为只读存档 tag `harvested-archive-v1`、最后提交 2026-06-30；企业AI转型 走 `Stock/Query` API 与 U9C 连接器，DB 直连当初即因本安全问题被弃用），Shao Peishen 拍板按**精确删除**（非整文件删）执行——`supplychain/.env` 中 `U9C_DB_HOST/NAME/USER/PASSWORD` 四行已删（33→29 行），`FO_API_BASE`／`XKY_*`／`WECOM_WEBHOOK_URL` 等仍在用的键完整保留；`.env` 未被 git 跟踪，删除不留历史痕迹。**残留（已知、经判断可接受）**：`scripts/spike_u9c_sql.py`（DB 直连侦察脚本）**被 git 跟踪**，其历史中是否曾提交明文口令**未查**（Shao Peishen 2026-07-31 定「暂时不查」）——同 §四#33 的处置逻辑：private 仓库、访问面受限，登记留痕即为处置；若仓库开放协作须重评。另 `.env` 内尚存一行**已注释**的 `# U9C_API_BASE=http://192.168.6.2:6666`（仅主机地址、非凭据，未删）。(b) U9C **`/Services` SOAP 免鉴权越权**：IT 已在 U9C Portal **IIS 层**加限制，**两处残余经 Shao Peishen 确认接受**，本项结案。**结案不等于零风险**——两项均为「登记风险接受」型收口，若访问面变化（仓库开放协作、SOAP 端点重新对外）须重评。细节见 `7-外部文档/U9C库存取数-侦察结果与推荐-2026-07-05.md`（本地，7-外部文档 gitignore）+ `1-转型规划/开场prompt-U9C库存实时读取攻关-CC交接.md`。

> **D1 缺料口径批改会材料 + 文档治理落地（2026-07-07，CC）**：D1 真实数据（真实FO/BOM/PO/Stock 四源）跑现状 kit_engine 引擎，63 条疑似误判案例+§9 决策点建议已产出（`缺料预警校准-误判案例对照表与批改会材料-2026-07-07.md`，commit `420fd9c`），供姚祖怡批改会用；D2(FI1批改会)因财务v2暂缓已跳过。同日执行《文档治理规范与规整执行清单-2026-07-07》：`feat/fi2-recon-mvp` rebase 后 ff-merge 入 master（FI2 三单匹配 MVP 32 tests）+ 删分支；1-转型规划/0-全景路线图 各建 `z-已执行归档/` 收 12 份已执行文档（5 份因活引用密集改 status 不搬）；R2 文档台账脚本 `0-学习与工具/工具-文档台账生成.py` 首跑（133 md，收工重跑一次）；R5 四条 session 接力首次瘦身（Phase1收口/财务域/质量域三份建归档件，采购域已达标免搬）+ CLAUDE.md 本段六旧段迁 `进度编年-CHANGELOG.md`。

> **财务域场景 v3 · FI2 口径修正（2026-07-09，重组循环第 4 例·轻量，Cowork 总线执行完成）**：唐燕萍团队数据闸回复（应付会计实操细化）+ Paul 三裁决 → 全景规划 §2.1.4 FI2 段修正 1-7 落字（痛点补实际配票流程，核对对象改 **AP 单 vs INV**、FI2-2 改**按同一料品汇总归集比合计**、发票源改 **U9C 应付单附件+OCR**、新增 **AP-PO 单价强制比对**、FI2-6 初期缩范围）+ §0.2 登记；前置总表 FI2 行 🟢**财务域数据闸实质解除**（U9C 财务侧 10 端点 IT 时间表 7/10-7/15 回填、SRM 900401 对财务域出局、OCR 选型 IT 7/12 定 ≥99%）；实施计划同步改写 + 两份 docx 重转；移交单/开场 prompt/机制日志第 4 行回填。**编号 FI1-FI10、FI2@09/FI3@11 排期、全景 40 均不变。** 本批 10 份文档 + 收工台账已由 CC commit+push（`1030e37`/`b0e7e28`）。**待办（CC，登记）**：FI2 三单匹配 MVP（已合 master，32 tests，按旧"逐行四维匹配"口径所建）需按 v3 新口径（AP vs INV/料品汇总归集/U9C 附件发票源/AP-PO 单价比对）评估改造——交接见 `1-转型规划/开场prompt-FI2口径修正-CC引擎调整交接.md`，真实验证仍按 8 月底排期不变。

> **企微智能机器人双向通道服务 · 代码首次持久化合入（2026-07-15，CC）**：队列看板 #18。核心功能（场景①跟进信直达+docx附件、场景②收专员反馈自动归档）此前已在 07-12~07-14 用真实数据反复验证跑通，但**实现代码从未被 git 提交**（全库全分支溯源确认）——历次真实成功都是运行期临时代码产生的结果，队列文档记的是"结果"不是"代码"。本次在独立 worktree 分支 `claude/wechat-robot-channel-setup-07e0f8` 里补建等价实现（`5-平台底座/wecom-aibot-service/`：`connection.py`/`delivery.py`/`intake.py`/`frame_parsing.py`/`department_mapping.py`/`queue_appender.py`/`gates.py`/`readme_table.py`；平台新增 `shared_tools/notifiers/wecom_aibot.py`），补齐 07-13 拍板但同样未落地代码的**进件全量转发 Paul**（`forwarding.py`）与出站抄送 Paul（`delivery.py::push_followup` 的 `cc_to_paul`），59+186=245 tests，**首次真正合入 master**。**未做**：07-12 认可的"归档成功后回部门群通报"（群内留痕）、断网重连自愈单测、.51 正式发布部署（另行安排）。详见队列 #18 行内注记与 `5-平台底座/wecom-aibot-service/CLAUDE.md`。

> **企微智能机器人双向通道服务 · 归档后部门群通报补建（2026-07-14，CC）**：上一条"未做"里的"归档成功后回部门群通报"，Paul 当日确认要建。新增 `group_notify.py`+`department_group_mapping.py`/`.yaml`（部门→群 chatid 独立映射表，区别于既有的发送人→部门映射表），接入 `connection.py::on_message` 第三条独立分发路径（归档/转发Paul/群通报三者各自 try/except，互不影响）。四部门（财务/质量/采购/销售）群 chatid 均先落占位符，`resolve_group_chatid` fail-closed——未配置真实值一律跳过并留痕 `group_notify_skipped`，不会误发到无效 chatid。**真实群 chatid 与群结构均未接**：队列 #18 行提过"三部门群已 ready（07-12）：财务/质量沿用，采购新建小群"，但（a）"沿用"指沿用哪个群、"采购独立小群"是否也已确认，均未见 Paul 明确拍板；（b）已查 `reports/wecom_aibot_audit.jsonl` 全量真实审计记录，从未捕获过任何群 chatid（`test_forwarding.py` 里的示例 chatid 是测试合成值，非真实抓包结果，不可当真值用）。已登记队列 §四#18，建议 Paul 澄清群结构或让各群发条测试消息由 CC 抓真实 chatid 回填。全量回归 186(平台)+73(本服务)=259 passed 2 skipped；commit `055ed8b` 已 push master。

> **企微智能机器人双向通道服务 · 群通报改走 webhook + 三部门真实凭据接入（2026-07-15，CC）**：Paul 澄清群通报走**既有企微群机器人 webhook**（非智能机器人 chatid 通道，两者是企微两套不同能力）——"财务/质量沿用、采购独立小群"实为**三个部门各自独立小群**（不含销售，Paul 拍板暂不启用）。改造 `group_notify.py`：从 `AibotConnector.send_markdown(chatid,...)` 换成复用既有 `shared_tools/notifiers/wecom.py::send_markdown(webhook_url,...)`（同步 urllib 调用丢 `asyncio.to_thread`）；`department_group_mapping.yaml` 从"部门→占位 chatid"改为"部门→**环境变量名**"（表本身不含秘密、可安全提交），真实 webhook URL 三个（财务/质量/采购）已写入 `5-平台底座/.env`（gitignore 已核实覆盖，未入任何 commit/日志/audit 明文）。全量回归 186(平台)+72(本服务)=258 passed 2 skipped，commit `ec6ee92` 已 push master。**同日续（Paul 确认后）**：一次性脚本给三个部门群各发一条明确标注【测试，可忽略】的真实通报，**均发送成功**——功能闭环，无需再等下次真实归档自然验证。"陈承回复邮件如何入档"一问系 Paul 自己表述混淆（"IT 不需要直接回复机器人，是 IT/SRM 决策项提供给我即可"），已确认不需要任何改动。**Paul 同日追加全局工作方式指令**：凡指令有歧义/交代不清，须先跟 Paul 确认清楚再动手，不要猜测执行——已存入跨会话记忆 `feedback_clarify_ambiguous_prompts`（全局，非仅本项目）。

> **企微智能机器人双向通道服务 · 进件白名单（2026-07-16，队列 #35，CC）**：机器人此前对任何发件人一律走归档+转发 Paul+群通报三条路径，导致同事发来的无关项目消息被误当业务内容处理、污染队列与 Paul 私信。Paul 口头要求**只处理陈承（IT，`2023458`）/陈忱（`ChenChen`）/唐燕萍（`tangyanping`）/姚祖怡（`YaoZuYi`）/王泓钦（`Hongqin.Wang`）五人**的消息与文件——命中→现有三路径不变；未命中→仅收一条礼貌回复（说明机器人尚未正式开通），不落档/不转发/不占用队列行/不发群通报。**开工前按 `feedback_clarify_ambiguous_prompts` 纪律先向 Paul 确认两点歧义**：①陈承是否也要同时开通场景①（跟进信直达）推送对象——Paul 确认**是**（经查 `delivery.py::push_followup` 本就按调用方传入 `chatid` 直接发送、不经白名单表过滤，故无需为此额外改代码，用 `push_followup_letter.py --chatid 2023458` 即可）；②礼貌回复文案是否需 Paul 过目定稿——Paul 确认**不需要**，CC 直接写合理默认。新增 `aibot_service/whitelist.py`（五人 userid 常量+`is_whitelisted()`+默认回复文案），`connection.py::on_message` 加前置分流。陈承不在 `department_mapping.yaml`（现有四部门口径不含 IT）——命中白名单后仍按现有 fail-closed 逻辑落"待分拣"，未做特殊化。新增 14 单测，全量回归 193(平台)+84(本服务)=277 passed 2 skipped，零回归。详见 `5-平台底座/wecom-aibot-service/CLAUDE.md`。

> **跨桌任务队列编辑锁 + 采购域V2撞号收口（2026-07-23，CC）**：QD-B 极简版发布收口收工时发现，同日财务专线（FI2 round-1）与采购专线（姚祖怡V2回灌）两条线各自不知情地把跨桌任务队列.md 的 #79 及后续号段用掉两次；更隐蔽的一次，采购专线一次会话编辑期间工作副本被 `git stash` 重置、未感知继续用旧内容写回，导致自己刚追加的"已完成"实质内容被降级为占位符——均靠逐行比对 git 历史手工救回、按"真实最大号之后续排"重排为 #83-87（详见队列 §一各行注记），无内容丢失但过程繁琐。**根治**：新增 `0-学习与工具/工具-共享文档编辑锁.py`（协议〇.7）——改队列文件前 `acquire`（占用中则改写自己的域接力文件待回补，不硬写）、改完立刻 `release`，本地文件锁、30 分钟陈旧自动可接管；协议正文见队列 §〇.7、CLAUDE.md §5 已同步一句话引用。**⚠️ 后续发现并修复一处 gap（2026-07-23 当日，保供看板批1 worktree 会话顺带发现，另一 CC session 收口）**：`REPO_ROOT` 原按 `Path(__file__).resolve().parents[1]` 推算，只解到脚本自身所在 checkout 的根——本仓库同时存活多个 `.claude/worktrees/*`（CLAUDE.md §5"一任务一分支一 worktree"是 CC 建造标准做法），故锁此前只能防"同一 checkout 内先后编辑"，防不住其本要解决的"两桌/两 worktree 同时改队列文件"核心场景。已改用 `git rev-parse --git-common-dir`（所有 worktree 共享同一个 `.git`，不论从哪个 checkout 跑都解到同一个主工作区根）；新增回归测试用真实 `git worktree add` 建主+linked 两个 checkout 验证跨 worktree 可见性，并用 `git stash` 切回旧代码正反两向确认测试有效，全绿零回归。详见队列 §一 #89。

> **QD-B 立项审核门禁·极简版发布收口（2026-07-23，CC，队列 #79）**：Paul 拍板"质量部要尽快用起来，不等陈忱/朱映桦回灌"——极简版口径已全清（权威表 20260717 定版 + EQ17/邦奇/华丰三真实样本黄金一致 + 54 tests 全绿），缺的只是 CC 收尾四件。本次完成：① 黄金基准三样本结构化清单入库（`data/golden/manifest.md`，脱敏元数据，不含财务数字）+ openspec `qd-b-project-gate-review` 阶段性归档（`archive/2026-07-23-*`，C01-C10/B类真实语义/OEM附件隔离等扩容项逐项标注🧭不阻塞发布）；② 新建最小 Web 服务 `qd_b_gate/webapp.py`+`scripts/run_qd_b_web.py`（上传立项书 xlsx→六段式《立项审核报告》，如实标注"B类转人工/C01-C10未实现"不伪装已判定），54→60 tests 全绿；③ 真实部署 `.51`（`QdBWebServer` 计划任务，SYSTEM+AtStartup+防火墙 `QdB-WebServer-8093`），真实黄金三样本上传冒烟全部通过（判定与 manifest 完全一致：EQ17 合格 98.80 分、邦奇/华丰 不合格 一票否决，driving rule 分别为 74/11）；④ AI 运营指挥中心门户质量域卡从样例数据表替换为真实入口 http://192.168.100.51:8093/ ；⑤ 灰度开闸（陈忱+朱映桦，一页 SOP `1-转型规划/QD-B立项门禁试用版灰度SOP-2026-07-23.md`）。**⚠️ 顺带发现并修复一个部署层生产事故**：为推送门户页更新触发命令中心 `CommandCenterWeb` 计划任务重启，暴露其原注册方式（AtLogOn 交互式登录+裸命令"python"）在 Administrator 会话"已断开"状态下无法启动新进程（0x80070002 找不到文件），服务短暂中断——已改注册为 SYSTEM+AtStartup+`Get-Command` 解析绝对路径烘焙进任务定义（同 SC8/QD-B 惯例），真实验证 End+Run 重启可靠。详见队列 #79 与 QD-B 场景 CLAUDE.md §7「部署状态」。

> **命令中心正式部署 .51（2026-07-21，CC，队列 #65）**：AI 运营指挥中心命令中心（此前只是仓库内静态原型，见 §5"发布即收口纪律"及队列 #53 备注"命令中心本身部署 .51 留独立后续任务"）本次正式上线——`sync-to-server.ps1` 脱敏管道对齐（先跑 `sync_sales_data.py` 落盘脱敏产物再 scp，删除原始 `dashboard_data.json` 直接 scp 分支防 PII 泄露）+ `.51` 上跑 `deploy-server.ps1` 注册计划任务 `CommandCenterWeb`（端口 8092，登录启动+失败重启）。真实部署过程中发现并修复两个此前未经真实验证暴露的问题：① 脚本无 UTF-8 BOM，.51 内建 Windows PowerShell 5.1 按系统 ANSI 误读中文导致语法错误，对齐 SC8 既有 BOM 惯例补齐；② 防火墙入站规则缺失（漏抄 SC8 `Baoguan-WebServer-8091` 那段），本机冒烟 200 但外部全部超时，补齐 `CommandCenter-WebServer-8092`（LAN 全网段）入站规则后外部访问恢复正常；顺带修了 SSH 非交互会话下 `Invoke-WebRequest` 控制台句柄假阳性。冒烟验证：`http://192.168.100.51:8092/` 200，远端 `data/sales_dashboard_data.json` 核验 10 条高危线索均已脱敏，回滚 SOP（`schtasks /End`/`/Delete`）在位。地址：**http://192.168.100.51:8092/**。详见队列 #65。

> **保供看板功能批1建造+部署完成（2026-07-23，CC，队列 #87④/§四#31，独立 worktree 建造）**：Paul 拍板批1=功能4项（明细导出CSV/Excel+成品明细分页10/50/100/200默认10+料品名称列+图例入界面）+ #12 子件供给状态全展示 + #14 需求日可齐套数量，均为 SC8 保供看板场景内**纯展示/派生列**，不改四色判定/净额/缺料计算口径（红线守住）。共享基础＝新增 `sc8/sources.py::load_purchase_orders_by_material`（复用 `ZpConnector.get_purchase_orders` 按料号汇总在途未清量）+ `SC8_PO_TRANSIT` 开关（默认 ON，端点异常时降级为无数据、不阻断整体重算，与 FO/BOM/SRM 强 fail-loud 语义有意区分）；`BaoguanRow` 新增 `component_names`/`component_status`/`demand_kittable_qty` 等字段，`row_to_dict`/看板 HTML/JS 同步扩展。TDD 全程新增 33 个测试，全量回归零漂移：SC8 226 passed+4 skip、平台 218+1skip（零改动）、SC1 53、SC7 41（黄金基准精确不漂移）、O2 20。**真实部署+真实数据验证**：`sync-to-server.ps1` 推送成功，`/api/ping`/首页/`/cases` 均 200，触发 `/api/refresh` 全量重算成功（116 行）；抓取线上快照核验新字段真实生效（116 行均有需求日可齐套数据、105 行有子件供给状态含真实品名/在途量/答交日期）。**未做**：#13 需求关闭列（批2，待姚祖怡定 3 口径，另起）；姚祖怡本人对线上看板的抽验反馈仍待其确认（发布=供试用，非等同验收完成）。详见队列 #87 与 SC8 场景 CLAUDE.md 状态时间线。

> **四服务共享口令门禁上线（临时止血，2026-07-30，CC，队列 #160，Paul 直接派单，独立 worktree `four-services-temp-auth`）**：`.51` 上四个跨部门服务（保供看板8091/命令中心8092/QD-B8093/FI2 8094，均由 CC 各自独立建造上线）此前**零鉴权代码、全部绑 0.0.0.0**——LAN 内任何一台机器打开浏览器即可看到 QD-B 真实立项书财务数据、保供看板真实客户名/订单量/交期、FI2 真实供应商单价，100 人公司内网真实暴露；此为 SC8 CLAUDE.md 长期悬而未决的"待办 #10"。**方案（非正式鉴权，临时止血）**：共享口令+Cookie，刻意不用 HTTP Basic（8092 iframe 嵌 8091 会弹两次系统认证框、体验崩）；利用浏览器 Cookie 按 host 隔离不分端口的特性，一次登录四服务全通。新增平台底座 `zhuopin_platform/shared_tools/simple_gate.py`（HMAC 签名 Cookie 30 天有效期 + `X-Auth-Token` 程序化访问头 + Flask `before_request` 集成 + 登录页，密码来自 `ZP_GATE_PASSWORD` 环境变量、**未配置时门禁自动 no-op**，保证既有测试零改动），SC8/QD-B/FI2 三个 Flask 场景接入；命令中心 `serve.py`（纯标准库、"零三方依赖"是既定设计原则）自包含复制同一套 cookie 名/签名算法，不引入平台依赖也能跨端口共享。**开工前先做程序化访问清单核实**（Paul 明确要求"漏一个就是一次静默中断"）：① 三服务 `deploy-server.ps1` 健康检查固定打 `/api/ping`——已豁免门禁；② SC8"每小时全量重算"核实为**进程内后台线程直接调用 Python 函数、从未经过 HTTP**，与本次门禁无关；③ 命令中心 `sync_sales_data.py` 只做本地文件读写+scp，不发 HTTP 请求；④ Cowork/CC 既有"PowerShell 直读 `/api/baoguan` 取证"用法今后需改用 `X-Auth-Token` 请求头。TDD 全程新增 41 个测试（平台26+SC8/QD-B/FI2 各5），全量回归零漂移：平台 244 passed+1 skip、SC8 290 passed+4 skip、QD-B 96 passed+25 skip、FI2 95 passed+7 skip。**真实部署+验证**：四服务逐一 `sync-to-server.ps1` 推送+重启确认新进程存活，远程 curl 验证 `/api/ping` 放行/未登录302/Token放行/登录Cookie放行，且**用保供看板(8091)登录的 Cookie 直接请求命令中心(8092)成功、反之亦然**——实测验证跨端口共享在真实服务器上成立（即 8092 iframe 嵌 8091 场景一次登录全通）；确认 SC8 重启前快照完整存活，后台重算线程未受扰动。**已知限制**：Claude Browser 工具对 LAN 私网 IP 触发访问限制，未能补做真实浏览器截图，以上均为 curl+响应头逐字段验证（HttpOnly/SameSite=Lax/Path=/），机制上等价于浏览器行为。**回滚**：清空 `.51` 上四份 `.env` 里 `ZP_GATE_PASSWORD=` 的值+对应计划任务 `schtasks /End`+`/Run` 即恢复零鉴权原状，无需回滚代码。口令已通过会话回复直接告知 Paul 转达使用者，**未写入任何会被提交入库的文件**（吸取 07-06 销售域 PII 入 git 历史的教训）。**未做**：正式身份鉴权（企微 OAuth SSO）需另出架构决策件，本次门禁不区分人员、不留访问痕迹、口令 LAN 内明文传输——这些边界已显式写入 `simple_gate.py`/`serve.py` 顶部注释。详见队列 #160 与 SC8/QD-B/FI2 场景 CLAUDE.md。

## 2026-08-04 ～ 2026-08-08（第三批迁移，2026-08-09）

> **迁移依据**：R5 文档治理规则「CLAUDE.md 本段完全收口的旧段落季度迁本文件」＋ Shao Peishen 2026-08-09 拍板 (a)（承载性核查发现「记忆偏差」根因链之一：**根 `CLAUDE.md` 每会话必载入，而顶部进度流水账占到 49%（75 KB／154 KB），把真正的规则稀释到注意力边缘**）。本批迁 **18 条**，原文原样、一字未改写；迁后根 CLAUDE.md 顶部只留最近一批（2026-08-09 三条）。

> **队列 #309——CI 基线三步骤全部收口，含真实故障排查三轮＋一处基线勘误（2026-08-08，CC，独立 worktree 三个：`ci-baseline-step2`/`ci-matrix-guardrail`，commit `17078d4`/`4a36768`/`ff885ff`/`daaab4b`/`8f53c3c`）**：**步骤 1（干净环境实跑）**——独立 detached worktree（无 `.env`）＋实测确认无法连通内网 `.51`，逐子项目 `cd` 后跑 pytest（root 一次性跑会因 20 处同名 `tests/test_golden.py` 等模块名冲突报 collection error），13 个子项目本机首次记为 1704 passed/40 skipped/0 failed（**该数字后经真实 CI 证伪并勘误为 1698/46，见下**）。**步骤 2（.github/workflows/ci.yml 上线）**——push/PR 触发四项检查（可离线测试矩阵／`openspec validate --all --strict`／队列结构 lint／凭据扫描）。**过程中撞上一次真实并发冲突**：Cowork「环境总线」并发 session 把本 session 尚在验证中的 ci.yml 早期草稿（缺 `ci-requirements.txt`、缺平台底座安装步骤）提交推送，随后一次常规 sweep 自动提交即真实触发线上 CI 首次亮红（`gh run 31246578987`，13 测试矩阵全灭）。**三轮真实 CI 故障逐一诊断修复**（均为仅在真实 `windows-latest` runner 上才暴露、本机环境差异掩盖掉的问题）：①`zhuopin_platform` 在本机能 import 是靠历史遗留全局 editable 指针兜底（同 #300 机制），全新 CI VM 无此指针，8 个子项目会 `ModuleNotFoundError`，补 `pip install --no-deps -e 5-平台底座/zhuopin_platform`（`--no-deps` 因其 `chromadb` 依赖树本地实测装一次要数分钟且 13 个子项目零处实际 import）；②`windows-latest` 默认 `cp1252` 编码而非本机默认 UTF-8，本仓库大量脚本 print 中文/✓✗ 触发 `UnicodeEncodeError` 致 5 作业全灭，workflow 顶层加 `env: PYTHONUTF8: "1"` 一次性覆盖修复；③自写的凭据扫描脚本漏传 `-c core.quotepath=false`，本机全局 git 配置恰好已设为 false（本地测试从未暴露），CI runner 用 git 默认值会把中文路径八进制转义+加引号致白名单正则失效误报，补该参数（与 `工具-落库sweep.py::_run_git` 同款设置对齐）。三轮修复后首次 16/16 全绿（`gh run 31249407072`）。**步骤 3（退休等量 sweep 检查）**——逐一核对 sweep.py 现有全部 8 类 webhook 告警/守卫（分叉／孤儿脏文件／定时任务镜像差异／凭据拦截／场景 spec 缺口／在途变更包滞留／部署留痕／未预期异常）与 CI 四项检查是否真重复，**审计结论：全部不重复**（时机不同——sweep 多数是实时拦截、CI 是事后检测；主题不同——`openspec validate` 经 `--help` 核实无场景-spec 覆盖面检查能力，#298 M1/M2 治的是这个真空）。**Shao Peishen 拍板"接受审计结论，不强行退休"**——协议〇.9 措施 B 的立法精神（不让 CI 变成第 9 个平行守卫）已因 CI 四项检查从设计之初就精准填补此前 0 覆盖的真空而满足，不为凑字面"退休"数字牺牲真实防护点。**同批顺带完成 Cowork「环境总线」步骤 2 追加设计输入的两项 guardrail**（用户拍板"现在加"）：`工具-CI矩阵发现.py`（矩阵改自动发现，替代硬编码 13 项清单这一"隐性白名单"，内容级过滤排除 `echo_test.py` 类假阳性）＋ `工具-CI覆盖率护栏.py`（独立于发现规则完美与否的第二道防线，聚合 JUnit XML 断言 passed/skipped/子项目数三条硬下界）。**真实 CI 运行中意外坐实一处本机基线记录错误**：首次带 guardrail 的真实运行显示真实聚合为 1698 passed/46 skipped，非本机早前记的 1704/40；排查坐实——QD-A/QD-B 各一处依赖真实立项书样本（`7-外部文档/`／`data/golden/`，从未进入 git 历史）的测试，在真正干净的 checkout 下会跳过，本机早前"干净 worktree"记录环境实际不够干净（具体哪次验证残留了什么状态未能完全回溯），已修正 guardrail 阈值与全部文档引用（历史记录不追改，另行登记勘误）。**顺带修复 QD-A `pyproject.toml` 两处真实 bug**（build-backend 无效值 + setuptools flat-layout 把 `data/` 占位目录误判为第二个顶层包，均此前未暴露因 QD-A 零 `zhuopin_platform` 依赖、从未被真正 `pip install -e` 过）：已真实验证 `pip install -e --no-deps` 成功+41 passed+uninstall 清理干净。**最终状态**：5 轮真实 GitHub Actions 运行、18/18 作业全绿（`gh run 31253244493`），#309 三步骤（含子项 F）全部收口，行状态转为 ✅ 已完成。详见队列 #309、`.github/workflows/ci.yml`、`.github/ci-requirements.txt`、`0-学习与工具/{工具-队列结构lint.py,工具-密钥扫描lint.py,工具-CI矩阵发现.py,工具-CI覆盖率护栏.py}`。
>
> **队列 #309 子项 F——sweep 起跑段硬 return 挡住 #288 收尾 rebase 根治，另解一次主工作区 master/origin 真实分叉（2026-08-08，CC，独立 worktree `sweep-startup-guard-fix`，commit `e75d02e`，openspec 变更包 `sweep-startup-fork-defer-to-reconcile` 已 apply+归档 `archive/2026-08-08-sweep-startup-fork-defer-to-reconcile/`）**：**开工先解一次真实阻塞**——主工作区 master（`e3e7f34`）与 origin（`2ae585f`）已分叉，两侧均改了跨桌任务队列.md；未使用 `git checkout --`/`git restore`（工作区还有一处未提交的 WIP，已在 §二 批次 `B-0808_可动WIP口径修订与三条并行放行` 声明），改为直接 `git commit` 落地该 WIP（用批次自带的 commit message）→ `git rebase origin/master`（仅 1 处自动生成台账文件冲突，属预期的时间戳/计数差异，人工取较新值解决）→ push，`rev-list --left-right --count` 确认 0 0；顺带发现并回填了该批次行此前状态列滞后于实际内容的遗留（内容早前已被落库但行未标 ✅）。**根因坐实**：`_push_any_unpushed_commits`（起跑段②，队列 #194）发现分叉即 `SweepAbort(is_fork=True)` 整轮退出，排在 §二 批次处理与 #288 新增、自带 `git rebase` 能力的收尾段 `_reconcile_with_origin_and_push` 之前，与 #288 当初治的 `_sync_master_if_behind_origin`（前置守卫排在批次处理之前、挡住后置修复）**完全同构复发**——#288 只修了自己撞见的那一处，未把"起跑段检查不得整轮 return"立为通则，2026-08-08 02:35 UTC 起同一形态在另一函数复发，sweep 连续 4 轮整轮跳过、连发 4 条分叉告警，已登记批次落不了库。**修法**：检测到分叉时不再 `SweepAbort`，记录日志后 `return`，继续批次处理；分叉的最终判定、自动 `git rebase` 对齐与告警职责统一移交收尾段——真无法自动解决（真实内容冲突）才落回既有 `is_fork=True`／`FORK_EXIT_CODE` 告警路径，语义不变，只是判定时机从"起跑段一律拦"收窄为"收尾段确认真无法自动解决才拦"（design.md 记录被否两候选：①起跑段就地 rebase——此刻工作区可能仍脏，会重蹈 `_sync_master_if_behind_origin` 覆辙；②维持起跑段 abort 但挪调用顺序——判定出的 ahead/behind 快照会被批次提交过时化，等于两处各维护一套"是否已分叉"判断）。新增/改写 4 个测试：`StartupGuardDoesNotBlockBatchProcessingTests` 两个新用例真实复现"预先未推送提交＋origin 同期分叉＋待处理批次"三要素叠加的真实故障形态（真实 bare origin + 真实 git 子进程，非 mock）；`ForkAlertTests._diverge()`／`SyncBehindOriginTests` 原用各自独立文件构造分叉、在新逻辑下会被自动 rebase 吃掉走不到告警，已改用两侧冲突同一处内容确保仍能验证"真正无法自动解决"分支。全量回归 **125 passed 零漂移**。`openspec validate --specs --strict` 67/67 通过（`sweep-startup-resilience` capability「非快进时不强推」Scenario 已同步改写+新增 2 个场景）。**真实验证边界（如实登记）**：本机主工作区当前有 10+ 个并行 CC worktree 活跃，未额外人为构造一次真实分叉演练去驱动新分支（风险判断同 #288 design 的既有权衡：真实性收益 vs 对共享 origin 的时序竞争风险，两次都判断后者更高）；开工时手工解卡的那次真实分叉发生在本修法生效**之前**，是本次修法要解决的问题本身，不构成对修法效果的验证；新分支已用真实 git 子进程单测覆盖，且测试构造场景比本次真实故障更严格，留待下一次真实分叉自然发生时被动观察一次并回填。**CI 基线主体（#309 步骤 1-3）仍未开工，#309 行整体状态不变（待领）**，本次只完成其子项 F。详见队列 #309、`0-学习与工具/工具-落库sweep.py`、`openspec/changes/archive/2026-08-08-sweep-startup-fork-defer-to-reconcile/`。
>
> **队列 #300——并行 CC 建造隔离根治：worktree 隔离引导（2026-08-08，CC，独立 worktree `followup-dispatch-apply-25679f`，openspec 变更包 `worktree-import-path-bootstrap` 已 apply+归档 `archive/2026-08-08-worktree-import-path-bootstrap/`）**：根因＝本机无 venv、系统 `site-packages` 全局唯一，`pip install -e` 把"哪份源码权威"写成全机指针，与 `git worktree`"N 份平等副本"前提矛盾——任一 worktree 跑一次 `pip install -e` 会**静默**顶替其余 worktree 的 `import` 解析（测试全绿，测的却是别人的代码），与既有 #98／#208 实证同族。开工实测坐实了活样本：全局指针当时指向 `fi2-tax-export-excel-d3938b`；`5-平台底座/wecom-aibot-service/scripts/run_aibot_service.py` 此前对自身包 `aibot_service` 已有路径保护、却漏了 `zhuopin_platform`。**选定候选丙**（design 三决策点获 Shao Peishen 会话内批准默认项）：`tests/conftest.py`/服务入口脚本顶部插入自包含引导代码（从 `__file__` 向上 walk 找 `5-平台底座/zhuopin_platform` 标记、插入 `sys.path` 最前），否掉 venv（候选甲，换个新人守点不划算）与共享 `_bootstrap.py`+indirection（本逻辑极简稳定，不构成 #306 那类会演化的重复）。**范围经逐文件核实收窄**：proposal 原写 7 份 conftest.py，**实测 QD-A 一份不在冲突面**（5 份测试文件零 `zhuopin_platform` 依赖 + 自身包从未 editable 安装）——实改 6 份 conftest.py + 5 个服务入口脚本；`AI运营指挥中心/serve.py` 实测零平台依赖同样不改。新增 4 个专项回归测试（`test_worktree_import_bootstrap.py`，核心用例：真实 subprocess + 合成哨兵值验证"全局指针指向另一 worktree 时本 worktree 仍解析到自己代码"，被测代码从生产 `conftest.py` 原样抽取避免测试与生产漂移）。**真实并行验证已完成**：`git worktree add` 真实创建第二 worktree（`origin/master`）并真实 `pip install -e` 其平台包污染全局指针（`pip show` 核实生效），本 worktree 全程指针污染未复原状态下跑 `pytest`（新测试4项+SC8全量377项）全绿，证明结果与全局指针指向谁无关；验证后临时 worktree 已清理、指针复原。**全量回归零漂移**：zhuopin_platform 262+1skip／SC8 377+4skip／FI1 33 passed／FI2 128+9skip（skip 数差异经核实为本地环境缺失 gitignore 数据文件所致，与本次改动无关）／QD-B 83+25skip／wecom-aibot-service 344+1skip，均与既有基线一致。**部署影响结论**：conftest.py 改动零部署影响；`.51` 三服务各自独立 venv 不受此故障影响，不需紧急重新部署；企微机器人常驻服务（与本机其它 CC session 共享全局 site-packages）是唯一真实受益方，建议随下次常规重启带上（本机不在 LAN，本次未做该重启）。根 CLAUDE.md §3/§4/§5 三处同步改写"`pip install -e` 可选，利于 IDE"；`专线opener模板库.md` 实测零相关提及，无需改写。两条 Non-Goal（不为 `git push` 并发造机制、不引 venv）均已遵守。详见队列 #300、`openspec/changes/archive/2026-08-08-worktree-import-path-bootstrap/`。
>
> **队列 #299＋#195 同车——spec 缺口补齐批：三个已建造场景 + 编辑锁/机器人两项机制模块的 openspec capability 全部补齐（2026-08-07，CC，独立 worktree `musing-pascal-68d14e`）**：**#299**——FI2/FI1（形态甲：spec 已写好、包未归档）开工先判定各自 13/12 项未完成任务是否真该完成，**结论均为真实未完工**（FI2 卡在 15.11"本次完工不代表可归档"与 8.3 真实验证门未过；FI1 proposal.md 顶部明写"条件复启暂缓"），**不得假装勾完**——改用 `/opsx:sync`（非 `/opsx:archive`）把已随 v3/D14/D19 等历次迭代同步更新的 5+4 个 delta spec 合入 `openspec/specs/`，两包本身维持在办、不归档；`wecom-aibot-channel` 同判（8 项未完成含"待 Paul 定"），同样只 sync（3 个 delta）。**QD-A**（形态乙：包已归档但当初就没写 spec delta）——反向读 4 个源文件（`doc_reader.py`/`field_extractor.py`/`scrubber.py`/`calibrate.py`）+ 既有测试断言，补写 `qd-a-doc-reader`/`qd-a-field-extractor`/`qd-a-scrubber`/`qd-a-calibrate` 四个 capability，回填进已归档包 `archive/2026-07-04-qda-8d-prefill/specs/`（历史正文不追改，另加 tasks.md §5 说明补写事实）并合入主 specs；**场景代码全程零改动**。`wecom-listener-macos-migration`（7/30，#220 已知在途）按既定判断不催、只登记；SC3/SC5/`deploy-tools` 按范围排除。**#195**——复核延后的 `--reserve`（#163，编辑锁取号）与 `queue_lock_pending.py`（#168，机器人写队列语义）是否已稳定：`--reserve-multi` 自 #185（2026-08-04）后核心逻辑无进一步改动、协议〇.7 已据其定为正式口径；`queue_lock_pending.py` 自 #286（2026-08-06）后仅内部改为复用 `pending_jsonl.py`、对外契约未变——**两者均判定稳定，可补写**（均涉"改变全项目口径"，未标 `skip_specs`）。新增变更包 `retroactive-mechanism-specs-batch2`（同"知识资产三问"+"验收晋档四档口径"格式，已归档），补写 `editlock-queue-number-reservation`（7 条 Requirement：单/多分区预留、fail-loud 不回落替代计算、竞态防护、release 时预留集合校验）与 `aibot-queue-append-lock-deferral`（5 条 Requirement：锁忙暂存不丢弃、FIFO 保序补录、复用完整同步降级路径、独立 acquire/release、与 git 失败暂存物理隔离）。**至此 #195 原始 8 候选累计 7 项已补写为真 spec**（FI2 走 #299 独立 sync 路径，spec 已存在但统计口径不重复计入本行，避免两行邀功同一份产出）。**全程零代码改动**（两行合计新增 12 个 capability spec：fi2×5/fi1×4/wecom-aibot-channel×3 走 sync，qd-a×4/editlock-queue-number-reservation/aibot-queue-append-lock-deferral 走新变更包补写归档），`openspec validate --all --strict` 由 49 capability/38 items 升至 66 capability/71 items（0 failed）。一致性核对方式如实登记：逐 Requirement 对照现有实现与既有测试断言转写（同 08-04 首批方法论），非重新真实数据验证——spec 存在只代表可追溯，不代表已重新核实与当前代码逐字一致。详见队列 #299／#195、`openspec/changes/archive/2026-08-07-retroactive-mechanism-specs-batch2/`、`openspec/changes/archive/2026-07-04-qda-8d-prefill/`。
>
> **队列 #295——FI2 发票源改道：税务导出 Excel 接入建成（2026-08-07，CC，独立 worktree `fi2-tax-export-excel-d3938b`，openspec 变更包 `fi2-tax-export-ingest` 已 apply+archive）**：唐燕萍 2026-08-04 拍板 OCR 方案作废（8 张发票货物名称/规格精确匹配仅 65.8%），改税务系统导出 Excel；2026-08-06 回件把落盘目录（`.51:D:\airead`）／导出责任人时点（李姣龙工作日10点前）／新增文件判据（我方自记已处理清单，不看文件名/mtime）／完整性校验口径（漏票/跨期/红冲作废三维**先都不设**，她的选择非遗漏）四个决策点全部定死，并放入她做 65.8% 比对用的 8 张真实发票导出件。**开工第一步真实探测即推翻 #249 局部定稿的字面 join 假设**：`AP/Query.InvoiceNo` 实测 5/6 只存「数电发票号码」后 8 位截断值（非全串），且该字段服务端过滤是 CONTAINS 语义非精确匹配（哨兵值验证过）——改用「后 8 位查询 + 客户端 suffix 二次校验」，8 个真实样本 **8/8 唯一命中正确 ap_no**（含 round-1 因 302 重定向/182行合并大票失败的两单，本次 Excel 路径天然绕开两个失败原因）。新增 `fi2/tax_export_ingest.py`（Excel解析+ap_no反查+item_code反查——用已确定 ap_no 反查该 AP 单行项目，按(数量,含税单价)唯一匹配时赋值我方真实料号，命中0/≥2行不猜测留痕待人工核对+内容哈希已处理清单幂等）+ `scripts/ingest_tax_export.py`（手动触发CLI）+ `ZpConnector.get_ap_lines_by_invoice_no`（平台连接器新增方法）；**三单核对判定六文件+展示层 `webapp.py` 全部零改动**，产出 `invoice.csv` 走既有 `invoice_sample_dir` 通道原样消费。**真实数据如实观察（不预设通过率）**：item_code 反查 40/198（约20%）唯一命中，未命中集中在182行合并结算大票（151/182），正常大小发票仅6行未解析——低命中率是「同一AP单下数量+单价组合易重复」的真实数据特征，非bug。全量回归零漂移：FI2 128passed+7skip（+21）、平台 262passed+1skip（+3）。真实部署 `.51:8094` 冒烟三件套全绿+**在 `.51` 服务器本机（非笔记本非本地拷贝）直接对真实 `D:\airead` 跑通摄取**（40行成功+幂等验证+UTF-8字节级核验）。**未做（如实登记）**：本次未改 `webapp.py`，摄取产出**未接入面板默认展示路径**（u9c模式仍固定读D19的`data/real_round1/`），仅交付摄取能力本身；第2层（定时扫描+失败告警）按拍板默认后置未做。详见队列 #295／#249、`4-数字员工/财务部/FI2-三单匹配自动对账/CLAUDE.md`。
>
> **队列 #294 修法⑴——跟进信发送状态两态语义扩为三态，新增 `⏸ 暂缓`（2026-08-06，CC，独立 worktree `three-state-semantics-tests-0f1cc1`，commit `ef0725e`/`a2bf8f6`）**：真实事故根治——队列 #150（07-29 批2判例包）2026-08-04 拍板"暂不发"，但两态语义下 README 状态列无法表达"已批准但暂缓"，只能原样留在 `🆕 待发`，`ZhuopinFollowupDispatchDaily` 照字面值执行，2026-08-06 01:30 UTC 机制照发了已决定暂缓的信（详见 #150／#294 两行）。**修法**：新增 `readme_table.PAUSED_STATUS`（`⏸ 暂缓`，只能从 `🆕 待发` 手工改写而来，不经任何脚本，语义区别于草稿态"内容未审"——暂缓是"内容已审、主动不发"）；`gates.assert_finalized`（`delivery.py` 门禁②）与 `dispatch.py` 候选行筛选均按等值断言实现（只认 `FINALIZED_STATUS_MARKER` 一个值），新状态天然被结构性排除，无需改判断逻辑本身；`dispatch.py` 额外新增 `DispatchOutcome.skipped_paused` 字段 + 审计事件 `dispatch_skipped_paused`，单独识别留痕（区别于草稿态的静默跳过——暂缓行"曾经批准过"，更容易被误当待发沿用旧假设）；README「发送状态两态语义」节改写为「三态语义」，补状态转换规则与已知边界说明。新增 6 个单测（`readme_table`×2/`gates`×1/`delivery`×1/`dispatch`×1），全量回归 wecom-aibot-service **344 passed+1 skip**（原 338+1，零回归）。**范围经业务总线 2026-08-06 拆分**只做修法⑴（本行），修法⑵（README↔队列一致性校验，编辑锁 `release` 增校验）划归 **#258**（已扩容升 P2、待领）——**⚠️ 语义未闭合（如实登记）**：#258 完工前，"决定写进队列却忘改 README"这一失效模式仍可能发生，只是从"没有状态可写"变成"有状态可写、但无人强制检查是否真的写了"，本行不重复登记该风险，交 #258 收口。**范围内未触碰** `工具-共享文档编辑锁.py`（按拆分明确排除，属 #258 触碰区）。详见队列 #294／#150／#258 与 `5-平台底座/wecom-aibot-service/aibot_service/{readme_table.py,gates.py,delivery.py,dispatch.py}`、`6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md`。
>
> **队列 #110/#112 同批——保供看板反馈按钮+判例包网页表单化 + 四服务访问日志采集框架（2026-08-06，CC，独立 worktree `followup-dispatch-apply-25679f`，commit `774cdee` 已 ff 合入 master）**：**派单开局即拦下一次错误指令**——原派单写"发采购部群 webhook、勿重新设计"，读队列行全文后发现该参数已被 Shao Peishen 同日拍板的 webhook 退役决策推翻，且新口径落点 #282 尚未开工、代码侧无本地代发端点可接，遂将范围收窄为"只建采集、通道留白"（经 Shao Peishen 会话内确认，见 §四路由判据实例）。**#110**：SC8 看板每行加 ✅/❌+原因 反馈按钮写 `reports/baoguan_feedback.jsonl`；判例包网页表单化（`/cases/review` 列表 + 表单页），07-28 三条硬约束（✏️独立记录/自由补充区/追加新问题）全部满足，判例包定义改为 Cowork 手写 JSON（`sc8/case_reviews/`，已开 `.gitignore` 例外）；"每周五 16:00 机器人汇总报送"明确留白，等 #282 收口后接。**#112**：新增平台底座 `zhuopin_platform.shared_tools.access_log`，SC8/QD-B/FI2/命令中心四服务均接入，记时间/来源IP/动作，不采集个人身份，周汇总/告警等正式统计按既定范围不做。全量回归零漂移：SC8 360+4skip（+27）/平台259+1skip（+11）/QD-B 83+25skip（+3）/FI2 110+7skip（+3）/命令中心14（+5）/SC1 53/SC7 41(黄金基准精确不漂移)/O2 20。**真实部署+真实验证**：四服务 `sync-to-server.ps1` 推送成功（四个 `NEW_PID` 均 2026-08-06 20:44-20:46 创建）；真实 `POST /api/baoguan/feedback` 200 且 SSH 核验落盘完整；`/cases/review` 真实 200、不存在包真实 404；四份访问日志文件 SSH 核验真实落盘、`/api/ping` 确认零记录（豁免生效）。顺带修复 `1-转型规划/AI运营指挥中心/serve.py` 一处潜在崩溃 bug（`PORT` 模块级读 `sys.argv[1]`，import 时若 `sys.argv` 携带其它参数会崩溃）。**如实留白**：判例包机制本身已用真实生产环境验证路由行为，但尚无真实判例包内容跑过完整提交流程（Cowork 尚未用新 JSON schema 起草过真实判例包）。详见队列 #110/#112、SC8 场景 CLAUDE.md 2026-08-06 行。
>
> **队列 #287＋#286＋#289＋#283 同车（企微机器人队列同步四件套，2026-08-06，CC，独立 worktree `musing-pascal-68d14e`，commit `b606000`+`4b660ba` 类，openspec 变更包 `aibot-queue-sync-checkout-guard` 已 apply、design 获 Shao Peishen 批准候选 A，暂不归档见下）**：**#287（P1，最严重）根因真实坐实**——`queue_git_sync.py::append_task_and_sync_to_git` 冲突重算前的 `_commit` 用 `git add` 暂存磁盘上当次**全部**内容，协议〇.7/〇.8 允许"人类已 release 编辑锁但尚未 commit"这一合法状态持续数分钟到数小时，一旦此时机器人处理另一条消息且推送撞上非快进冲突（日常高频场景），`reset --mixed`+`checkout --` 会把混入了人类内容的本地 commit 连根拔起——工作区回退到 origin 版本，人类成果既不在工作区也不在任何可达历史里；用真实 bare origin+真实 git 子进程+真实调用生产函数复现坐实（非 mock/推断），2026-08-06 拆件巡逻第一班 09:19 的改动即因此被机器人 09:25 的一次追行整体抹掉。**修法（design 候选 A，否掉候选 B「全程持锁」——已证实锁语义解决不了本问题：协议本身允许锁已释放、内容未提交这一合法态，机器人拿到锁时锁本就是空的；候选 C「纯 git 对象级重写」登记为更彻底但改动面更大的后续候选）**：新增 `_diff_exceeds_expected`，销毁性 `reset`/`checkout` 前校验刚提交的本地 commit 相对父提交的实际改动是否超出"仅本次追加"的预期规模（插入≤2行/删除≤1行，只判行数量级不解析表格语义）；超出即判定磁盘混入外来内容，改为 `reset --soft HEAD~1` 撤销本地 commit（不动工作区），人类内容与机器人本次算出的行原样保留在工作区待人工/sweep 处理；`GitSyncOutcome` 新增 `foreign_content_detected` 字段，`sync_after_archive` 据此用与网络/冲突类失败明确区分的 audit reason（`foreign_dirty_content_detected`）与告警文案，避免人工误判为可通过重试解决。**#286**——同一次故障的另一半症状：`pending_queue_appends.jsonl`（git 层真实失败暂存）此前完全没有 flush 通道，`QueueLockBusy` 与"真实 git 失败"混用同一文件导致"同一种失败从两个不同层抛出，只有一层暂存会被补录"；新增中立 `pending_jsonl.py` 模块避免 `queue_git_sync`/`queue_lock_pending` 两模块互相 import 成环，`QueueLockBusy` 专门路由进锁忙暂存文件复用既有 `flush_pending_queue_appends`，新增 `flush_pending_git_sync_appends` 补上缺口，告警文案补暂存路径+`input_pointer`。**#289**——`delivery.py::push_followup` 回填 README 后此前只落磁盘从不 `git commit`，`ZhuopinFollowupDispatchDaily` 每发一封信就稳定产出一个孤儿脏文件；采纳候选甲（自行 commit，同机器人自动追行队列范式，否掉候选乙「赋予自动机制写 §二 批次的能力」与候选丙「sweep 白名单，按规则退休制不采纳新人守清单」），新增 `_commit_readme_backfill`：`git add`+`commit`+`push`，非快进冲突改用 `fetch`+`rebase`+失败 `--abort` 保留本地提交（**不采用 #287 揭示的销毁性 reset/checkout 路径**），提交失败不影响已成功的发送本身。**#283**——`push_followup` 此前把整份跟进信 md 原样发送，专员私信开头泄漏我方内部记账（`status:`/`编号:`/`配套:`/`合并说明:` 等字段，长期存在、自机器人推送机制启用以来所有信件均受影响）；新增 `_strip_frontmatter`，一处改动同时覆盖主送/CC Paul/群 CC 三条路径（三者共用同一 `content` 变量），只改发送内容不动源文件。**全量回归**：wecom-aibot-service 338 passed+1 skip（含 18 个新测试）、platform 248 passed+1 skip，零回归。**部署债已收口（2026-08-06 21:51 本地/13:51 UTC，CC，独立 worktree `deployment-debt-cleanup-c70663`）**：三项代码修复（#286/#289/#283）与 #287 护栏此前均已合入 master 但未部署——本次已部署：`ops/wecom-service-home` worktree 由 `101ec2f` ff-merge 至 master `6854f8a`（含四项修复全部），worktree 内独立复跑全量回归 `338 passed+1 skip` 通过；`ZhuopinAibotDevListener` 计划任务重启（旧 python PID 110768→新 PID 110944），`aibot_liveness.json` 心跳戳 `2026-08-06T13:51:26Z` 确认新进程真实建连；`_strip_frontmatter`/`_commit_readme_backfill`/`_diff_exceeds_expected`/`pending_jsonl.py` 四项均经 grep 核验已在磁盘生效。**如实边界（仍未闭环的两类）**：① 真实企微私信发送验证（#283 的"下一封信实物核对开头即正文"）需下次真实 dispatch 命中本场景才能核对，本次未做；② `aibot-queue-sync-checkout-guard` 变更包 §3 真实验证（观察真实非快进冲突场景／真实护栏命中场景）性质是被动观察真实生产流量，本次部署只是打开观察窗口而非完成观察，按「完工即归档纪律」仍暂不归档。详见队列 #287／#286／#289／#283 与 `5-平台底座/wecom-aibot-service/aibot_service/{queue_git_sync.py,pending_jsonl.py,queue_lock_pending.py,connection.py,delivery.py}`、openspec 变更包 `aibot-queue-sync-checkout-guard`。
>
> **队列 #288——sweep 落库卡死机制化：批次先本地提交后统一对齐 origin/master（2026-08-06，CC，独立 worktree `sweep-ffblock-fix`，openspec 变更包 `sweep-ff-sync-batch-reorder` 已归档，commit `3a8fae7` apply， design 已获 Shao Peishen 批准选项 (a)）**：**根因**——`_sync_master_if_behind_origin` 排在批次处理之前，其 `git merge --ff-only` 要求工作区干净，与「§二待commit批次必然导致工作区脏」这一 sweep 自身设计前提冲突——origin 一旦也改了队列文件（近 20 个提交 100% 触碰它），ff 合并被 git 拒绝，`SweepAbort`，批次处理整轮走不到，2026-08-06 当日已两次真实卡死需人工介入。**修法**（design.md「决策点1」选定并加强候选 A，否掉候选 B「stash 保护式 ff」与单独候选 C「失败降级告警」）：`_process_normal_batch`／遗留尾巴批次／`_rerun_ledger` 均改为只本地提交，不再各自校验快进或推送；新增 `_reconcile_with_origin_and_push`，批次全部提交、工作区恢复干净后统一对齐一次——纯落后 ff-only／纯领先直推／已分叉改用 `git rebase`（旧代码在此场景直接跳过，本次改为主动尝试自动对齐），rebase 冲突即 `abort` 回滚（本地提交完整保留不丢失）+ 复用既有 #171 分叉告警，不强推不自动解冲突；对齐成功后统一 push 一次。旧 `_verify_fast_forward`／`_sync_master_if_behind_origin` 两函数调用点清零已删除。**design.md「决策点2」诚实结论**：对绝大多数不冲突的并发编辑（队列文件是追加型文件），真正打破了自锁循环；对少数真实内容冲突，退化为止血（本地提交不丢+主动告警），仍需人工介入解除，不劣于现状。**单测**新增 6 个（含验收要求①核心复现场景，覆盖不冲突自动 rebase 与真实冲突安全回滚两个子场景），全量回归 78 passed 零漂移。**真实主工作区验证**两轮均已完成：第一轮真实触发 sweep 恰好一次性处理了 4 个此前被本 bug 卡住的真实积压批次，验证修复直接解除生产积压；第二轮用另一真实 worktree checkout 对队列文件做一次真实并发推送，精确复现「本地脏+origin改动同一文件」故障链本身，日志实测「已 git rebase 自动对齐」「已统一推送」，退出码 0 无 SweepAbort，双向完全同步——**如实边界**：真实内容冲突导致 rebase 失败这一子场景仅经单测覆盖，未做真实主工作区构造（风险权衡后判断不必要）。详见队列 #288 与 `0-学习与工具/工具-落库sweep.py`、openspec 变更包 `archive/2026-08-06-sweep-ff-sync-batch-reorder/`。
>
> **队列 #262＋#263 同车（D 批·SC8 答交口径 v3 与替代料多层穿透，2026-08-05，CC，独立 worktree `unified-portal-design-8a2ce3`，commit `654dc5c`/`19f1e39`/`10bd987`/`3ad0026`）**：**#262**——姚祖怡 2026-08-05 第三度举证 `F02N.0224`/`R01A.1028` 答交数量/日期均显示「无」，08-03 批次（#211/#212/#213/#173）留下的「窗口会自然打开、无需改动」判断本次被证伪。**根因真实坐实**：`load_material_commitments` 查询窗口固定 `[今天,今天+60]`，receiveType 筛选/累计算法本身正确，问题是窗口结构性排除更远期确认批次（真实探测 `R01A.1028` 命中于延伸窗口 `[+60,+120)`，与截图逐位吻合）。**修复**：新增 `config.material_commitment_lookahead_days()`（默认180天，窗口分布探测坐实——`[+120,+180)` 仍71条已答交记录，`[+180,+240)` 边际收益趋零）+ `sources._chunk_date_windows`（拆分≤60天不重叠窗口，SRM硬性单次跨度限制）+ `load_material_commitments` 分段查询后合并，范围仅限本函数，不改既有四色判定口径。全量真实数据核验（1421个真实料号，264个命中新窗口，抽样31个料号对照零重复计数）；`.51:8091` 部署冒烟通过，`R01A.1028` 端到端复现精确匹配 `10000/2026-11-25`。**#263**——根因由 #213（08-03）真实举证坐实：`_substitute_groups` 只扫描成品直属行，替代关系若定义在半成品子件自己的 BOM 里（真实案例 `F02N.0233`：`R01A.0707`↔`R01A.0012` 定义在半成品 `S02Y.0207` 自己的 BOM 里）则永远看不到，误判为缺口。**Shao Peishen 2026-08-05 拍板 (a) 先建后签**（她的授权带前提「无需决策项」而前提不成立，签字改到改完之后做）。**修复**：新增 `_bom_subtree_product_ids`（沿主料路径递归收集半成品闭包，不沿替代料路径下钻）+ `_substitute_groups` 改跨层级扫描（分组键 `(product_id,sequence)` 防序号碰撞误并组），单层 BOM 场景零漂移。**交付强制含两份对照材料**：① 30个真实成品中11个（均F02N前缀，实测确诊数）替代分组变化，真正受益字段是 `_covered_by_stock`（如实记录 `_kittable_qty` 因既有第一层直接子件限制数字不变，已登记为新发现的独立待办 #266）；② 黄金基准重跑与差异说明（counts与修复前完全一致98红/5绿，如实说明这些成品另有其它真实瓶颈；197项抽样中195项正确移除，2项例外经诊断为既有跨订单库存分配机制#118正确协同、非缺陷）。`.51:8091` 部署冒烟通过。**两行合计全量回归零漂移**：SC8 333 passed+4 skip（原313+20新测试）、平台248+1skip、SC1 53、SC7 41（黄金基准精确不漂移）、O2 20。详见队列 #262／#263／#266／#267 与 SC8 场景 CLAUDE.md 2026-08-05 两行、`4-数字员工/采购部/SC8-客户订单交期智能承诺/docs/queue_{262,263}_*.md`（已入库，含完整对照表；原落 `reports/` 因 worktree 清理丢失、已改落此路径重建，见 #267）。**待办**：跟进信合并 #262/#263 一并发（§四#52 已拍板(b)），本批未发。
>
> **队列 #248——sweep 与编辑锁状态列关键词判据锚定（2026-08-05，CC，独立 worktree `serene-boyd-2a5ba2`，commit `568d8b2` apply／`46138db` 归档／`21cd770` 队列回填）**：**问题**——`工具-落库sweep.py::_classify_section_two_rows`（§二待处理判定）与 `工具-共享文档编辑锁.py::_validate_release_structure`④断言门槛（§一 P0/P1+未核实共现检测）均对状态列做整体子串扫描，真实事故：一条状态列开头 `✅ 已完成`、但说明文字引用了判据原文（含"待"字）的 §二 批次被误判为待处理，取活提交覆写原说明——同族第三次（#164/#225/#248），达 CLAUDE.md §5 规则退休制阈值，须走 openspec 含 design 审。**openspec propose 阶段额外发现**：队列 §一 #221 行状态列当前就带着未加引号保护的 P1 定级 token 与被「」包裹的"未做的核实"字样（引用/复述规则本身，非断言当前判断），是编辑锁侧一个尚未真实触发但已确认会触发的同族潜伏案例。**design 四个决策点**（Shao Peishen 本会话内批复"全部按默认执行"，均 (a)）：①sweep 判据锚定状态列"开头片段"（非整体子串）；②编辑锁④扫描前剔除「」/『』引号包裹片段；③引号字符集仅「」/『』（英文直引号 1000 次高频但不成对，纳入有误伤真实断言的风险，不采纳）；④sweep 前导剥离字符集含全角空格。**⚠️ apply 阶段发现并修正一处实现细节**：字面"锚定开头"理解成"只看第一个字符"会让既有回归测试固化的 2026-07-27 真实误写场景（"✅ 已完成（本次登记，待 sweep 落库）"）从待处理误判为已完成，重新引入 2026-07-28 那次判据修法要根治的旧问题——根因是 propose 阶段的历史兼容核对只对照了生产队列文件实时内容，没有对照既有回归测试套件里固化的历史边界场景。改用"开头片段＝去除前导 `*`/空白后、第一个句级分隔符（"。"/"——"/"━━━"，现存队列文件里分别 996/573/199 次高频使用）之前的文本"，两个真实场景（本次事故与旧误写）均已用回归测试双向验证，不冲突，design.md 已如实补记这一 apply 阶段修正（非重新征询决策，是同一决策方向下的边界精确化）。**新增单测**：sweep 5 个（4 纯函数级+1 端到端，走真实 subprocess CLI+真实 git commit/push，非 mock）；编辑锁 2 个（正反各一）。**全量回归零漂移**：sweep 73 passed（含新增 5 个，532s）、编辑锁 71 passed（含新增 2 个，52s）。**历史兼容核对**（现存生产队列文件实测）：§二 17 行 0 分歧；§一 63 行仅 #221 一处分歧，修法后不再命中、与人工判断一致。**openspec**：变更包 `sweep-editlock-status-keyword-anchoring` 已归档至 `openspec/changes/archive/2026-08-05-sweep-editlock-status-keyword-anchoring/`，新增 2 个 capability（`sweep-batch-status-classification`/`editlock-assertion-gate-scope`）已同步进 `openspec/specs/`，`openspec validate --specs --strict` 43/43 通过。**真实验证范围说明（如实登记）**：因 apply 期间主工作区处于高频并发状态（起跑后 master 数分钟内推进 6+ 提交），未额外对生产共享队列文件做一次手工验证，改用真实 subprocess CLI + 真实临时 git 仓库 + 生产代码路径级测试作为等效验证，风险与确信度评估见 design.md/tasks.md「真实验证」节。详见队列 #248 与 `0-学习与工具/{工具-落库sweep.py,工具-共享文档编辑锁.py}`。
>
> **队列 #208＋#223＋#101① 同车（B 批·SC8 与平台杂项，2026-08-05，CC，独立 worktree `zealous-meitner-6a3325`）**：**#208**——`test_po_srm_confirmed_date.py` 5 个失败 triage（业务总线派发，先 triage 再修）：**A1 单跑 vs 全量跑结果完全一致**（均 5 个失败），直接排除测试污染/运行顺序；**A2 根因锁定** `get_purchase_orders(days=60)`（`connector.py:408-410`）按 `datetime.now()-60天` 对 `makeDate` 做滚动窗口过滤，测试夹具把 `makeDate` 写死 `"2026-06-01"`，随日历推进于 **2026-08-01 起恒定滑出窗口**（精确验证：`cutoff(07-31)="06-01"` 险过、`cutoff(08-01)="06-02"` 起失败），与 #197/#207 观察到的"07-31 后"时间点几乎吻合、但归因判断有误——**不是任何代码提交引入，是测试夹具自身绝对日期到期**；**A3 冻结时间复现**（把 `datetime` mock 冻结到窗口内的 2026-07-20，未改一行生产代码）五个用例全部通过，**证实代码逻辑从未有问题**，(甲)共用 helper 改动、(乙)测试污染均被实证排除。**B 段修复**：测试夹具改用相对"当前时刻"计算的 `_days_ago`/`_days_ahead`，不再写死绝对日期；**零生产代码改动**（`connector.py` 未动一字节，不触发 SC8 `.51:8091` 部署）。**顺带发现并更正一处既有文档表述**：`pip install -e` 的 editable 安装实测当前指向的是 `unified-portal-design-8a2ce3` worktree 而非"主工作区"——即该目标会随"谁最后跑过 `pip install -e`"静默漂移，不固定是主工作区（既有文档"从任意 worktree 跑 pytest 会测到主工作区代码"这一表述不精确，已在 #98 更正，本次经字节级比对确认该 worktree 代码与主工作区一致、未构成本次成因）。**#223**——SC8 客户改期草稿在瓶颈子件"无任何供应商答复"时仍写死"确定延期"（对客承诺口径失真的合规隐患，L2 门禁关心范畴）：新增 `SupplyCase.bottleneck_unanswered` 字段（`case_store.py`，含旧库 `ALTER TABLE` 幂等迁移，兼容已有 `reports/*.db`），`alert_dispatch.py::dispatch_new_reds` 建案时复用既有 `_alert_markdown` 的"瓶颈是否在无答复明细里"同一判据自动写入（抽出 `_is_bottleneck_unanswered` 共享，不另起一套判据），`webapp.py` 手动建案表单新增勾选覆盖；`case_draft.py` 的 customer 措辞分支据此二选一（"预计调整至…"vs"交期未确认…存在延期风险"），**只改对客口径，内部催货/协调模板与四色判定逻辑零改动**（红线守住）。**风险低不为零、本批未部署 `.51`**（对客闸全程关闭无客户可见改动，留待需要时随其它改动一并部署）。**#101①**——三连事故根治收尾：`工具-落库sweep.py` 新增只读 CLI `--check-dirty-in-pending-batch`（复用既有 `_resolve_batch_files`/`_parse_section_two`/`_classify_section_two_rows`，不另起一套匹配判据），`工具-主工作区安全同步.ps1` 步骤 2 命中脏文件后先调用该 CLI 核验：命中 §二 待处理批次 → 改印"禁止 checkout，请触发 sweep"；核验脚本失败 → 从低取值按已命中处理（不放行危险操作）；把协议〇.8"批次即扫+checkout 前核对 §二"这条纸面规则落到工具上（规则退休制"挂到不可绕过的咽喉上"）。**全量回归零漂移**：SC8 313 passed+4 skip（原303+10 新测试）、平台 248 passed+1 skip（原243+5 修复，零新增回归）、SC1 53、SC7 41（黄金基准精确不漂移）、O2 20、`工具-落库sweep.py` 自身 68 passed（原63+5 新测试）。详见队列 #208／#223／#101① 与 `5-平台底座/zhuopin_platform/tests/test_po_srm_confirmed_date.py`、`4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/{case_store.py,case_draft.py,alert_dispatch.py,webapp.py}`、`0-学习与工具/{工具-落库sweep.py,工具-主工作区安全同步.ps1}`。
>
> **队列 #241＋#245 同车——dispatch 行→文件判据补维度 ＋「该起草而没起草」检测仓库内半（2026-08-05，CC，独立 worktree `elated-bartik-d8482e`）**：**#241**——dispatch 此前只凭「收信人＋日期」定位跟进信 `.md` 文件，同日多封必然歧义（2026-08-04 #124 阶段二首次真实触发命中，见 #150 行）。采纳修法⑴：`readme_table.py` 新增 `extract_target_filename`／`build_target_file_annotation`——README「主要事项」列末尾追加固定格式的目标文件标注（形如「→ 目标文件：」后接反引号包裹的文件名），只在既有单元格内追加文本、不新增列，`_validate_followup_readme_release` 等编辑锁结构校验因此无需同步改动；`split_department_and_name` 从 `dispatch.py` 迁出成共享函数，供 #245 同用。`dispatch.py` 改为标注优先、未标注行回落旧的部门+姓名+日期 glob（向后兼容）。**真实验证**：对生产 README 里 #150 那行原样不改，直接跑解析函数，成功唯一定位到磁盘上确实存在的目标文件（只验证定位、未真发，它按串行原则仍暂不发）。**#245**——补 #124 design D5 明确标注为 Non-Goal 的另一半检测：新增 `aibot_service/draft_gap_detection.py`，`find_recent_scenario_commits` 扫近 N 天 commit 是否触碰已部署场景白名单（同 #229 `DEPLOYED_SCENARIO_PREFIXES` 白名单精神独立维护一份，不跨包 import sweep），`find_missing_drafts` 与 README 已起草行按收信人交叉比对，缺口即"该起草而没起草"；纯检测不发通知。过程中修了一个真实 bug：git `--name-only` 对含中文场景目录路径默认按 `core.quotepath=true` 八进制转义，前缀匹配全部落空，已加 `-c core.quotepath=false`。新增 CLI `scripts/draft_gap_check.py`，真实针对生产仓库跑一次输出"无缺口"（与 SC8/QD-B/FI2 近期均有跟进信行的实况相符）。**🔴 仓库外半未做**：拆件巡逻定时任务 prompt 真身在仓库外，需 Cowork 经 `update_scheduled_task` 把「待发信盘点」步骤扩展为额外调用该 CLI，已在队列 #245 行写明，不假装做完。**全量回归**：wecom-aibot-service 288 passed 1 skipped（+23 新测试）；`test_工具-共享文档编辑锁.py` 全量 69 passed 零回归（未改该文件一行）。详见队列 #241／#245 与 `5-平台底座/wecom-aibot-service/aibot_service/{readme_table.py,dispatch.py,draft_gap_detection.py}`。
>
> **队列 #238／#236／#229／#227② 四件同车——sweep 批次隔离安全内核收尾（2026-08-05，CC，独立 worktree `sweep-batch-isolation-22f7b1`，commit `3794d81`/`7daf232`/`15ce6e6`）**：**#238**——`工具-落库sweep.py` main() 的 `unaccounted` 全局门改为逐批次判定，新增 `_partition_pending_rows_by_batch_isolation`：一个批次是否被阻塞只取决于它自己的声明片段是否命中 `ambiguous`（#234(1) 精确相等优先收窄后仍剩的真实歧义），与它无关的其它批次照常落库；被阻塞批次逐条打印可解释日志（片段命中几处候选、候选路径全列出）；真正无人声明的孤儿路径不阻塞任何批次，只作独立提示。**#236(2)**——新增 `_track_and_alert_orphan_paths`，孤儿脏文件超过 3 小时阈值复用 #171 webhook 通道点名，此后每满一个阈值周期再提醒（回应 #147「狼来了」教训），孤儿消失即从状态清除。**#229**——新增 `_find_missing_deployment_trace`，批次命中已部署场景白名单（SC8/QD-B/FI2+命令中心）却未同批改动部署留痕文件即日志+webhook提示，纯提示不阻断不改退出码。**#227②**——新增独立脚本 `工具-仓库外载体扫描.py`，覆盖 Cowork artifacts／`.51` 四服务页面／已安装版 skill／定时任务真身四类仓库外活载体，供协议〇.8「已复检」逐项过一遍（①协议文本改写仍待 Cowork）。**#236(1)**——评估为改变全项目口径的机制变更，按 CLAUDE.md §5 触发门槛走 openspec 变更包 `queue-claim-time-batch-preregistration`，propose+design+specs+tasks 四件已产出并 `openspec validate --strict` 通过，design.md 四个技术决策点（预登记粒度／陈旧检测路径／工具化程度／与编辑锁〇.7 交互）均已给出推荐方案+默认项，**待 Shao Peishen 审核后再 apply**，本次未直接改协议〇.1/〇.3 文本。**全量回归零漂移**：sweep 63 passed（+21 新测试）、仓库外载体扫描 10 passed（新文件）、编辑锁+台账工具零改动回归通过。**真实验证**：主工作区同步后真实触发两轮 sweep（2026-08-04 09:10 UTC）——当时工作区恰好非 clean（并行 session `CC-统一门户网关-apply` 刚更新 §四 编号高水位线、尚未提交），旧实现下会整轮 `return 0` 拦截一切，新实现正确识别该文件为孤儿、不阻塞任何东西、日志留痕，第二轮确认状态正确持久化（first_seen 不变、未过阈值不告警）；「部分批次落库+部分暂缓」这一核心场景已由单测 `test_ambiguous_batch_deferred_while_unrelated_clean_batch_proceeds` 完整覆盖。详见队列 #238／#236／#229／#227② 与 `0-学习与工具/工具-落库sweep.py`、`0-学习与工具/工具-仓库外载体扫描.py`、`openspec/changes/queue-claim-time-batch-preregistration/`。
>
> **队列 #124 阶段二 apply 交付：跟进信发送机制化安全内核（2026-08-05，CC，独立 worktree `followup-dispatch-apply-25679f`，commit `5742407`，openspec 变更包已归档 `archive/2026-08-04-wecom-followup-dispatch-automation`）**：design D1-D5（Shao Peishen 2026-08-04 审批通过）+ 两条审批追加要求（补1 批准冷却窗口／补2 漏标硬截止机器判据）全部落地，触发时刻已按拍板由默认建议 17:30 改定 09:30（避开 17:30 发出后专员已下班、误发无人补救的风险）。**① README 两态语义（D1）**——`readme_table.py` 新增 `assert_draft_pending_review`（`⏳ 待你审`草稿态断言）；新增 `aibot_service/approval.py` + `scripts/approve_followup_letter.py`（唯一合法转态路径，`--quote` 必填批准依据、写入独立审计事件 `followup_approved`）；**新增批准冷却窗口**（默认 10 分钟，`check_cooldown`：脚本首次"观测"某行只记录时刻并拒绝，须满窗口后再调用才放行——不追溯真实起草时刻，以"脚本首次调用"为观测锚点，堵住"起草→release→立刻批准"同一 actor 一步做完的反模式）；`工具-共享文档编辑锁.py` 新增跟进信 README 专属 `_validate_followup_readme_release` 结构性拦截分支（起草物理上不能一步到位写终态）。**② 每日批处理 `ZhuopinFollowupDispatchDaily`（D2/D3）**——新增 `aibot_service/dispatch.py` + `scripts/dispatch_followup_letters.py`，扫描"🆕 待发"行，`🔒人工发送` 标记结构性跳过；**新增机器判据兜底**（`has_unmarked_imminent_deadline`：交期要点含严格 `YYYY-MM-DD` 明确日期且距今 <3 天、未标 `🔒人工发送` → 结构性跳过并私信告警——漏标安全网，不替代人工判断，不识别"本周五"等相对表述）；行→文件/收件人按 R4 命名律从"收信人+日期"glob 解析，零匹配/多匹配一律记失败原因、不猜。**规范文本**：README-跟进机制与命名约定.md 新增"两态语义"章节；根 CLAUDE.md（本文件）§5 场景固定流程第8步措辞同步更新。**apply 前置核对**：`wecom-aibot-channel` 变更包剩余 8 项未完成任务（测试/观察/部署文档/收工动作）与本变更无文件级交集，已并行推进。**全量回归零漂移**：wecom-aibot-service 265 passed+1 skip；平台 243 passed+1 skip（`test_po_srm_confirmed_date.py` 5 个失败为既有日历漂移缺陷，与本变更无关，已见 2026-08-04"平台杂项批"条目登记，非本次引入）；新增 63 个测试。**⚠️ apply 期间 master 快速前进两次（其他并行 CC 会话落地 #200 绕锁检测/#185 多分区预留/#93 多附件支持等，均触碰同一 `工具-共享文档编辑锁.py`/`delivery.py`），两次 `git rebase master` 均自动合并零冲突**（改动区域互不重叠），仅需补齐一处测试 `argparse.Namespace` 缺 `reserve_multi` 字段。**真实部署+真实端到端验证（2026-08-04，真实凭据+真实网络，scratch README 隔离生产数据）**：`ZhuopinFollowupDispatchDaily` 已注册（工作日09:30，`Actions[0].Execute` 复核确认 `wscript.exe`，`LogonType Interactive` 当前用户即注册成功、无需管理员权限）；全链路真实验证——冷却窗口首次调用真实拒绝→真实等待 65 秒后重试成功（审计留痕含 `--quote`）→用真实 `Start-ScheduledTask`（非直接调库函数，走完整 wscript→VBS→PowerShell 包装→python 链路，`LastTaskResult=0`）真实推送经真实 WebSocket 送达（README 回填"✅ 已推送"，`followup_delivered`/`followup_cc_delivered`/`followup_backfilled` 审计齐全）→`🔒人工发送`行确认跳过→机器判据行确认跳过。**⚠️ 真实触发时的副产物发现（如实登记）**：`Start-ScheduledTask` 真实运行时一并扫描到生产 README 里唯一现存的历史积压"🆕 待发"行（本行 07-27 痛点描述提到的"姚祖怡判例首封"，实际日期 07-29），因该日期下存在 3 个候选 `.md` 文件、无法唯一定位，按设计安全降级为 `dispatch_row_skipped_unresolvable`（未发送、未回填、零副作用）——**该积压行仍需人工消歧才能被自动机制处理**，本轮不代为决定改哪个文件、留给内容归属方核实。详见队列 #124 与 `openspec/changes/archive/2026-08-04-wecom-followup-dispatch-automation/`{design.md,tasks.md}、`5-平台底座/wecom-aibot-service/aibot_service/{approval.py,dispatch.py}`。
>
> **平台杂项批七行同车：#92/#93/#108/#188/#209/#233/#96（2026-08-04，CC，独立 worktree `platform-misc-batch-0804-c36831`，本批刻意不含任何触碰 `工具-落库sweep.py`/`工具-共享文档编辑锁.py` 的行，与机制加固批并行）**：**#92（P3）**——`start-aibot-service-dev.ps1`（`ops/wecom-service-home` 本机专属文件，不入 git）的 `Start-Transcript` 中文重复两遍 bug 根因＝该机制靠轮询 Win32 控制台屏幕缓冲区取文本，全角字符占两个 cell，隐藏窗口下缓冲区状态不标准触发尾随 cell 重复取值；改为 `Write-Log` 用 `[System.IO.File]::AppendAllText` 直写文件，绕开控制台渲染管线，已直接编辑该本机文件（未重启常驻服务验证，P3 非阻塞）。**#93（P3）**：`delivery.py::push_followup` 新增 `extra_attachments` 参数支持多附件（`docx_path` 仍为首个附件向后兼容位），`DeliveryResult` 新增 `media_ids`；CLI `push_followup_letter.py` 新增可重复 `--attachment`。**#108（P3）**：`sync_sales_data.py` 路径改 `SALES_CRM_DATA_PATH` 环境变量+脱敏逻辑边界单测（脏 JSON/缺字段/嵌套异常）；QD-B `webapp.py` 新增 `_secure_filename()`（类 `secure_filename` 但保留中文可读性）过滤上传文件名。**#188（P2）**：核实其核心机制已被同日早些时候的 #169（`工具-定时任务源码备份.py`）实质覆盖——`Path.read_text()` 的通用换行符转换已满足"不得裸哈希、须规范化比对"判据，补一个 CRLF vs LF 内容一致场景的回归测试固化该判据；sweep 每小时自动检查半边仍留白（非本行遗漏，#169 README 已注明留待 #200/#185/#229 落地后再接）。**#233（P3）**：`platform-data-connectors` 主 spec 补齐 fix-a/fix-b 已落地代码但未同步的 4 个 Requirement（`不安全 TLS 仅经显式逃生开关并留痕`/`get_bom 回退走 fail-loud 闸门`/`SRM 承诺交期区分查询失败与未答交`/`连接器 from_env 审计缺失 fail-loud 告警`），并修正一处 Scenario 描述与代码不符（real 模式 TLS 逃生阀实为硬拒绝 `InsecureTLSError`，非原文"忽略并继续"）。**#96 CC 半边（deploy-server.ps1 统一收编）**：`ZhuopinDeploy.psm1` 新增 5 个共享函数（口令 env/防火墙规则/计划任务注册/Web 健康检查/模块自我推送），五份 `deploy-server.ps1`（SC8/FI2/QD-B/命令中心/wecom-aibot-service）改薄封装，各自独有部分保留；顺带发现并补 `ZhuopinDeploy.psm1` 自身缺 UTF-8 BOM（此前只被笔记本侧使用未暴露，现也被 .51 内建 PowerShell 5.1 侧 `Import-Module`，同已知坑同族）；机器人脚本 BOM 缺口（=#167）已在 A6 批完成，存量端口收编（依赖统一门户网关中间件，见队列 #162）解耦为独立后续、本行不能全销。**全程未触碰 `.51`/生产**（本工作区约束）；全量回归零漂移：wecom-aibot-service 242 passed+1 skip、QD-B 80 passed+25 skip、AI运营指挥中心新测试 9 passed、平台连接器相关测试 12 passed（`test_po_srm_confirmed_date.py` 5 个失败为既有日历漂移缺陷，与本批无关，已有独立 spawn_task 登记不重复处理）；全部 10 个 ps1 + psm1 逐一语法核验通过。详见队列 #92/#93/#108/#188/#209/#233/#96 与 `5-平台底座/deploy-tools/ZhuopinDeploy.psm1`。
>
> **机制加固五件同车 + 队列#234(1)紧急插队（2026-08-04，CC，独立 worktree `mechanism-hardening-batch-c5f073`，commit `a1e34b2`）**：**#234(1)（P1，紧急插队，Shao Peishen 拍板"按紧急任务优先原则插队"）**——`工具-落库sweep.py::_resolve_batch_files` 新增精确相等优先：脏路径集合里存在与片段字面完全相等的路径即唯一采用，不再把同一轮 `endswith` 后缀命中一并计入歧义，解除同名文件（如根 `CLAUDE.md` 与场景目录下同名 `CLAUDE.md`）撞名致批次连带跳过（08-04 实测曾致 19-20 批积压）；(2) 批次隔离（改 `main()` 控制流）本轮明确不做，按拍板留给独立 session（见队列 #234/#230-2d）。**#219（P1）**：sweep 起跑段新增决策提醒第二载体（子进程调用 `decision_reminder_check.py`，零依赖隔离，排在编辑锁窗口外），真实触发一轮验证端到端生效（真实发送提醒 3 项）；`NumberOfMissedRuns` 判据补进 #96《.51 部署标准清单》§四⑥bis。**#222（P3）**：main() 启动即写日志首行，不等收尾统一 flush，避免"启动后立刻崩溃"与"压根没启动"在日志上表现相同；三次历史触发根因证据不足，如实留白。**#225（P2）**：编辑锁 `release` 时对队列文件新增四项结构校验（列数／§二批次自声明队列文件路径／编号唯一且属预留集合／状态列 P0-P1 定级+未核断言门槛），仅对本次持锁期间新增或修改的行生效。**⚠️ 真实 dogfooding 过程中发现并修正④的一处设计缺陷**：初版按整行扫描 P0/P1+"未核"字样，导致 #225/#230 两行（其任务描述本身就在讨论这条规则、天然含"P1"与"未核"）在只改状态列为"已完成"时被自己的新校验误拦——三条现存行（#219/#225/#234）逐一核对后确认本项目约定优先级标注写在**状态列**，改为只检查状态列本身，问题解决且更贴合真实约定，已补两个回归用例。**#230-1c（P2）**：`acquire` 回显最近 120 分钟内其它 acquire 身份，复用 `.editlock` 自身 `history` 字段，零新增状态文件；校验④随 #225 同车交付；2d 评估结论同 #234(2) 合并留待独立 session。**#226（P2）**：`run-decision-reminder-check.ps1` 定性为本地生成物（`register-decision-reminder-task.ps1` 机械生成，含机器专属绝对路径），加入 `.gitignore`。**#231（P3）**：两个计划任务改用 `wscript.exe` + VBS 启动器（同 `run-hidden.vbs` 既有范式）避免弹窗，代码就绪但本 session 未触碰常驻服务、未重新注册生产任务，需后续同步后重跑注册脚本。全量回归 sweep 44 + 编辑锁 49 passed，零漂移，38 个新测试。**真实验证**：主工作区同步本次改动后真实触发一轮生产 sweep（2026-08-04 05:47 UTC，退出码 0，无误报），决策提醒第二载体真实发送；队列 #219/#222/#225/#226/#230/#231/#234 七行状态已用新落地的 `release` 校验本身回填（dogfooding）。详见队列各行与 `0-学习与工具/工具-落库sweep.py`／`0-学习与工具/工具-共享文档编辑锁.py`。**同 session 续跑（2026-08-04，commit `89a1d52`/`6549754`）**：**#231 真实部署验证**——`ZhuopinDecisionReminderDaily`（LogonType Interactive）重跑注册脚本非提权环境下成功，`Actions[0].Execute` 复核确认已为 `wscript.exe`；`ZhuopinCommitSweep`（LogonType S4U）`Unregister-ScheduledTask` 报拒绝访问（注销/修改现存 S4U 任务与"注册新 S4U 任务"是同一权限门槛的新数据点），已整理 `Set-ScheduledTask` 原地改 Action 的提权代码块待 Shao Peishen 执行。**#200（P2，已完成）**：`acquire` 授予时比对目标文件与上次 release 记录内容（`.editlock.lastknown`），检测到绕锁直接改写即回显警告（不阻断）+ 默认队列文件时落审计记录到 `reports/queue_edit_lock_bypass.jsonl`；已核实拆件巡逻镜像 prompt 本就走 acquire，无需改。**#185（P2，已完成）**：新增 `--reserve-multi 一:2 四:1` 一次性跨分区预留，与单分区 `--reserve`/`--section` 互斥；顺带修了 08-03/08-04 实测的竞态——`_reserve_ids` 写回高水位线前核对即将分配的号是否已存在于当前文件可见行，命中即 fail-loud。四处调用方措辞回改：协议〇.7 + 两份 skill 源码（`zhuopin-queue-audit`/`zhuopin-kickoff-prompt`）已更新，已安装版待 Cowork `save_skill` 同步；拆件巡逻 prompt 真身在仓库外、CC 无 `update_scheduled_task` 权限，留给 Cowork。22 个新测试，全量回归编辑锁 64 + sweep 44 passed 零漂移。
>
> **销售域 v5 排期重排 + R1 门禁日同步（2026-08-04，Cowork 全景路线图线，重组循环第 5 例，队列 #136／#201）**：**① 销售域（结构级）**——源 §四#37 Shao Peishen 07-28 拍板「销售域整体推迟到 2026-09 启动」，按前置总表 §三.6「知识型前置须启动前 8 周开工」反推得 **S1 最早 2026-11**（原 2026-09 排期不成立）。**新排期＝S1 2026-11／S2 2026-12／S3 2027-01／S4 2027-02／S5 2027-03（销售 6 场景收官）／S6 2027-02 本体不动**——S2-S5 同步 +2 月由 Shao Peishen 2026-08-04 当场拍板（否则 S2 会早于其数据底座 S1，形成排期倒置）。**场景总数仍 40、编号不变、场景内容不变、四链结构不变**（S6 本体不动故链 D 端点 L1/L5 无需改）。**已知并接受一处倒序**：S5(2027-03) 落于 S6(2027-02) 之后，两者无依赖关系（竞品监控 vs 销售预测），为保住「S6 本体不动」而接受。**S6 知识线一并评估（不留尾）**：2026-Q4 归集**不顺延**，但窗口实质收窄为 11-12 月（泓钦 9 月启动后才能确认数据源）；**若 2026-12 底未完成归集则 S6 本体顺延 2027-03**，该条件已写入前置总表 S6 行、本次不预改排期。**② R1 工程研发门禁日（轻量·口径同步）**——源 §四#35 Shao Peishen 08-01 重新拍板：门禁日 **8/31→9/30**、口径「聚焦现有部门和场景」。**按 (甲) 执行**：只统一散落各处的过时字样（含全景规划原「工程研发 AI Champion 7 月内指定」这一 07-27 遗留），**R1 排期 2026-10 与 R 系列 S1/S3 归属一律不动**；(乙)「正式顺延 R 系列入 S3」留待 **2026-09-30** 两前提（①Champion ②Chroma 就绪，**现已同日、可一并判定**）判定，未达再走完整重组循环。**九文档已重排**（全景规划含 §0.2 登记与 §2.1.5 新增 v5 段／实施计划含 §一§二§依赖表§批次视图／前置总表 R1 行·§三.4·§三.6·S6 行／甘特 m 值 S1-S5 各 +2／四链蓝图端点排期注／本 CLAUDE.md／变更日志第 5 行／session 接力／全景规划与实施计划两份 docx 同批重转），grep 全库零残差、场景总数 40 四处一致。**静默期未破**：§四#35 静默至 2026-09-25，本次只做文档口径同步、未就「Champion 指定」本身提醒；恢复载体 #202 定于 2026-09-28 值周巡检触发，本次未提前动。
>
---

## 附录 · 规则成因判例（2026-08-09 起，队列 #311 由 `CLAUDE.md` §5 迁入）

> **本附录是什么**：08-05《规则体检判定表》E 类判定——`CLAUDE.md` §5 有三条「巨型混装条目」合计 7,907 字、约占 §5 正文 1/3，其中**大量篇幅是事故成因叙述而非规则本体**（E1 单条 3,569 字里约 3,000 字是 2026-07-29 #151/#152 那次事故的过程）。规则本体留 §5、**成因叙述迁本附录**。
> **迁移方式**：**整条原文原样存档，不摘录、不改写一字**——摘录会引入「哪句算成因、哪句算规则」的判断，而判断正是这次要消除的东西；§5 侧给出拆分后的规则本体。**两边合起来才是完整历史。**
> **可查回**：`git show <2026-08-09 前任一 commit>:CLAUDE.md` 亦可取得同样原文；本附录只是让它**不必靠 git 考古就能读到**。

### 附录 A · 原 §5「建议未获答复须再次提醒」条（E1，3,569 字，2026-08-09 拆为 4 条）

> **拆分后落点**：建议未获答复本体／执行环境标注（含「改本机工具链＝CC」）／跨桌任务队列纪律（降指针指向协议〇）／机制优先大原则——四条均已在 §5。**以下为拆分前原文。**

- **建议未获答复须再次提醒（Shao Peishen 2026-07-29 定，两桌全局）**：给出建议后若 Paul 未明确答复，**而该建议牵动后续动作**，必须**主动再次提醒**——不得当作默认通过，更不得靠一句"建议…"就当已处置。**判据：建议 vs 状态，机制只认后者**——凡建议涉及任务归属/优先级/范围合并/排期变更，要么当场把**状态字段**改到位，要么显式标注"待 Paul 确认"并在下次交互重提，不留中间态。**收工自检**：本次说过的"建议…"里，哪些未获明确答复却已影响他处表述或他人行动？逐条重提。**成因（2026-07-29 真实教训）**：业务总线判断队列 #151 应并入 #152，在 #152 行与 CC opener 两处都写了"**建议**并入"，但 **#151 行状态仍为"待领"**——队列靠状态字段驱动，行只要还"待领"，任何 CC session 都可能取走它、只做那一个字段即交付，**又是一次分段交付**，而 #152 存在的全部意义正是终结分段（姚祖怡已三次说"仍不全"）。高危形态＝**在 A 处写"建议并入 B"但 A 的状态没改：读 B 的人以为已并、读 A 的人以为可领，两边都不会发现**。经 Paul 追问才暴露。**执行环境标注（Paul 2026-07-27 定，硬规则）**：凡对外呈现的任务/opener 标题，**必须在任务名处显式标注 `【Cowork】` 或 `【CC】`**，`【设置】` 行同步写 `执行环境：Cowork/CC`（两处冗余：标题供扫读挑活、设置行随 opener 复制进新 session）。**判别**：只产改 `.md`、不写生产码、不自行 commit（收工只登记 §二 批次）＝**Cowork**；写跑代码/连真实库与 `.51`/测试部署/自行 commit+push/一任务一 worktree＝**CC**；只读取证（PowerShell 直读接口、git 取证）仍属 Cowork，一旦要改代码或触发服务动作即转 CC。**🔴 补一类中间地带：改本机工具链＝CC（Shao Peishen 2026-08-02 定）**——全局 npm 包/插件/CLI 的**安装与版本升级**，以及 `openspec update` 一类**会重写生成物的命令**，**一律归 CC**，**即便其产出看上去只是 `.md`**。其原话：「本线不到紧急修复到了迫不得已，还是归 CC 让机制流程修复更加稳妥」。**理由（2026-08-02 #205-A 实证）**：这类操作改变的是**全项目构建环境**，且**可能静默覆盖本地定制**——本次 `openspec update` 把 `.claude/commands/opsx/propose.md` 里 2026-07-04 落地的强制门禁段（《知识资产三问》+《验收与晋档条件》）**整段删除、零提示零报错**，混在 10 个文件的上游 diff 里，若非逐文件过目会被 sweep 直接 commit 掉（详见队列 #205／#206）。**Cowork 仅在紧急且迫不得已、并经其明示授权时破例**；破例时**必须**：① 先固化升级前证据（版本三处交叉、受影响目录/文件基线）；② 逐文件过目 diff（**推荐判据＝中文行增删计数**，比逐行读快且可靠）；③ 事后如实登记为破例。**（Shao Peishen 2026-08-02 同日二次确认破例口径：「属于紧急情况只要我这样单独授权，可以即刻执行」——即**他在会话内的一次性明示授权即为充分**，不需另开派单或走变更包；但破例三条件不豁免。）** **⚠️ 但"已获授权"不等于"该照原方案执行"**：2026-08-02 他授权"立即给五个 worktree 同步警示注释"后，**动手前的取证推翻了方案本身**（Cowork 加了注释也提交不了、会变成五个永久脏文件；且真正的滞后是整份 `CLAUDE.md` 落后最多 338 提交，加注释治不了）——**正确动作是回报改判、另立 #207，而不是把已授权的动作照做完**。**授权解除的是"能不能动手"，不解除"该不该这么动手"。****四处落点一致**：值周巡检《本周计划》§A、拆件巡逻报告拟动作、队列 §一 新行"领取方"列、各类交接/开场 prompt 标题。成因＝2026-07-27 本周计划 A1/A2/A3 只写"财务/采购/质量专线"，需靠 `worktree：☐`、"只编 .md"、"勿自行 commit"等间接特征反推是哪张桌，Paul 反馈有歧义。细则与模板见 `1-转型规划/0-全景路线图/专线opener模板库.md` §〇。**prompt 呈现格式（Paul 2026-07-08 补）**：聊天中交给 Paul 的 prompt/口令，**≤500 字直接给完整原文、>500 字落 prompt 文件+单句开场词引用**；无论长短，一律放 **fenced 代码块**（```…```，渲染自带复制按钮，一键复制），不用引号段落。**跨桌任务队列纪律（Paul 2026-07-09 定，两桌强制）**：`1-转型规划/0-全景路线图/跨桌任务队列.md` 是两桌间任务流转唯一载体——所有 session **开工必读**（认领本线"待领"任务+登记触碰区）、**收工必写**（状态+产出路径+新冒出的下游任务当场追加待领行，替代 Paul 转述）；触碰区与他人在办重叠不得抢领，报总线裁决；**commit 一律由 CC 从队列 §二"待 commit 批次"取活销行**（一批一行，杜绝同一 merge 两处发起）；**口径冻结标（§三）**：某域进入口径重梳期即挂标，CC 见标停该场景在途建造，解除前不合入（防"按旧口径建完又改"）。值周巡检定时任务每周一 10:00（避早会，Paul 2026-07-24 定）读队列生成《本周计划》（任务开场词+需 Paul 决策清单+临期红线），Paul 周一批阅即可；**巡检开跑前先跑跨会话对账审计**（skill zhuopin-queue-audit，Paul 2026-07-11 定）——以文件真身校准队列后再出周计划，防止周计划催已完成/已删除事项。**（gap 收口纪律，Paul 2026-07-22 定）审计发现"设计↔执行 gap"时，确保 gap 被驱动到收口后再定稿《本周计划》，不把未解决 gap 埋进计划当普通行**：能当场校准的（队列失真）当场改；Cowork 解决不了的（git/代码/业务口径）置顶为阻塞项 + 当场发 CC 口令 / Paul 动作，确认其有主·有截止·已派单的收口路径后再让计划往下走。分工上"确保解决"＝移交并驱动到收口闭环（非 Cowork 亲手修完），如 2026-07-17 主工作区漂移→周计划登记→CC「台面收口」session 闭环。**本文件编辑锁（协议〇.7，Paul 2026-07-23 定）**：改队列文件前先 `python 0-学习与工具/工具-共享文档编辑锁.py acquire --who "<身份>" --note "<原因>"`，被占用（返回非0）则不改本文件、改写自己的域接力文件待回补；改完立刻 `release`——防止两桌各自不知情往同一份未提交文件里写导致静默覆盖（2026-07-23 财务/QD-B 撞 #79、采购专线一次追加内容被覆盖两起事故后补，详见队列 §〇.7）。**每周清扫与编号高水位线（协议〇.8，Paul 2026-07-24 定）**：已完成行每周由值周巡检（对账审计后）迁入同目录《跨桌任务队列-归档-YYYYMM.md》，新行编号一律以队列文件顶部"编号高水位线"+1 续排（不以文内可见最大号为准）；首次清扫 2026-07-24 由总线治理批执行（队列瘦身 88%，历史行见归档件），详见队列 §〇.8。**机制优先大原则（Paul 2026-07-24 定，两桌全局把关）**：能等的交给机制（对账审计/sweep/值周巡检按流程修复——机制修复自带证据链与留痕，且每次运行都是对机制本身的真实检验）；不能等的（紧急/阻塞/破坏风险）用机制的方式立即做（编辑锁、批次登记、队列留痕，不裸手改）。Cowork/CC 所有 session 以此把关，发现绕开机制的裸改（含自己）应拦下提醒；实证依据=2026-07-24 三连误弃事故（人工手快并发编辑是事故温床）与 #68 过时字样留审计自修的对照。

### 附录 B · 原 §5「会话接力」条（E2，2,341 字，2026-08-09 拆为 4 条）

> **拆分后落点**：会话接力本体／开场词与 prompt 纪律／**🔴 新场景一律不新起端口（独立成条——判定表点名它就是「混装条目里藏着的那条硬约束」）**／会话末显式罗列决策项——四条均已在 §5。**以下为拆分前原文。**

- **会话接力（Paul 2026-06-25 定，固定方式）**：本项目**每次新开 session 都用"读上下文文件"交接，不靠粘贴长 prompt**。新会话开场：读 ① 本 `CLAUDE.md`（当前进度）→ ② `1-转型规划/0-全景路线图/session接力-Phase1收口.md`（【下一会话主攻】+ 状态快照）→ ③ 全景规划 / 实施计划第七节（权威）恢复上下文，开干前问 Paul 2-3 个澄清。**收工纪律**：把本次进展 + 下一步**滚动更新进 `session接力-Phase1收口.md`**（覆盖旧版、标日期），使下一会话读完即接上。Paul 开新会话只需说一句"读接力文件 + CLAUDE.md 继续"。**开场词纪律（Paul 2026-07-06 定）**：凡产出交接/开场 prompt 文件（专线转场、CC 交接等），文件内必须内置一段**「开场词（复制即用）」**——单句、含目标文件完整路径引用，Paul 复制粘贴即可开新 session；聊天回复中同步给出该可复制块，不让 Paul 自己拼路径。**prompt 收工段必带 git 处置（Paul 2026-07-08 补）**：Cowork 专线/总线类 prompt 的收工段须写明"列出本次全部新产出/修改文件清单 + 建议 commit message + 提示 Paul 一句话交 CC：commit + push + 收工重跑台账"（Cowork 不擅自 commit，但必须交代去向，不留未提交悬置）；CC 类 prompt 本含 commit+push，另加"收工重跑台账"。zhuopin-kickoff-prompt skill 待 v1.1 补此段（skill 本体在 Cowork 环境只读，下次重打包时更新）。**🔴 新场景一律不新起端口（Shao Peishen 2026-07-29 定，硬约束，两桌全局）**：自本条生效起，**新增场景不得新起独立端口对外**，一律注册到统一门户路由 `/{域}/{场景}` 下（如 `/procurement/sc7`、`/quality/8d`）并预留网关 auth 接入点（中间件未就绪期间可为空壳，但路由与接入点必须留）。**成因**：现状是四个平级独立服务（8091 保供看板/8092 命令中心/8093 QD-B/8094 FI2）、**零鉴权代码且全部绑 `0.0.0.0`**，而采购域还有 SC1/SC2/SC4/SC7/SC10/SC11 待上、质量域还有 8D 与 IQC/SPC——按原惯性即再增 8+ 个端口，收编成本随场景数线性增长。**存量三个可慢慢收编，增量必须当天止住。** 目标态＝一个门户 + 一次企微 OAuth 登录 + 各域挂统一路由，**后端保持独立服务不合并进程**（保留故障隔离）。完整设计见 `3-治理与合规/统一门户架构决策件-SSO与权限-2026-07-29.md`（待 design 审）。**会话末显式罗列决策项（Shao Peishen 2026-07-31 定，两桌全局）**：每次回复**末尾**用固定小节「**需你定夺**」+ **编号清单**罗列需其定夺的决策项，每项须写清**选项之间的实际差异**（不是只写"要不要做"）+ 各自代价 + 建议；**临期项标日期并置顶**；**同时列出此前提出但尚未答复的悬置项**，不因换话题而消失；无决策项时明写"本次无需你决策"。**成因**：长会话里决策点散落各段，"藏在长会话中间容易疏忽"（其原话）。 **🔴 格式硬规则（Shao Peishen 2026-08-02 定，两桌全局）——每一项必须是可直接作答的「是非题」或「选择题」，不得是开放式陈述**。其原话：「需要我定夺事项语义不是很明确，以后可否都做成明确的是非题或选择题并全局记住？」**四条要求**：① **每项带编号 + 带字母标签的选项**（`(a)/(b)/(c)`），或明确写成"是/否"，使他能只回一个字母或"是"就完成决策；② **每个选项写清"选它会发生什么"与代价**，不是只写选项名；③ 🔴 **两栏各归各位，任一方向串栏都算违规（双向，2026-08-03 补齐另一半）**——(i) **禁止把纯状态汇报混进「需你定夺」**：状态另起小节「**状态同步（无需你答）**」，混进来会让他被迫为一个没有选项的条目"作答"（2026-08-02 实证：#204 那项只是状态陈述，他只能把原话抄回来，并当场指出该缺陷）；(ii) 🔴 **反过来同样禁止——不得把需他定夺的事塞进「状态同步（无需你答）」**（2026-08-03 实证：把队列 §四#44「专项清扫三选一、等你定」写进了状态同步栏，被他当场指出"好像跟这条有歧义"）。**成因值得记：当时只写明了 (i) 这一半，我守着写明的那半、照样从反方向犯了同样的错——单向规则拦不住双向问题。** 判据：**凡出现"等你定／请你选／待你拍板"字样，一律属「需你定夺」，不论它看起来多像顺带一提**；④ **每项标注「默认项」**——写明"若不答，我将按 (x) 执行"，**使"不答"也成为一种有效且可预期的输入**，与其"悬置项即刻受控"的要求配套。 **悬置项同样适用**：跨会话未答复的项**必须以选择题形式重提**，不得只陈述"仍未答复"。与下条「建议未获答复须再次提醒」是同一诉求的两个方向——那条管**跨会话**不丢，本条管**单次会话内**不漏；与队列 §四 互为呼应（会话末清单＝当次，§四＝跨会话台账，重要项两处都要有）。

### 附录 C · 原 §5「同步纪律」条（E3，1,995 字，2026-08-09 拆为 3 条 ＋ 2 段迁知识库）

> **拆分后落点**：同步纪律本体／乱码文件夹哨兵／时间戳必判 UTC vs 本地——三条在 §5；「排查『文件像是变旧了』的顺序」与「时间戳两个实测陷阱」两段属 D 类知识，迁 `0-学习与工具/取证方法知识库.md` §三.1／§一.2。**以下为拆分前原文。**

- **同步纪律**：开工先跑 `git fsck --connectivity-only`（秒级，确认对象库健康——2026-07-04 曾疑似 `.git/config` 损伤、云端副本尾截断；**根因已于 2026-07-07 更正**：并非 OneDrive 损坏文件，而是**沙箱文件桥滞后**（仅影响 Cowork 云端挂载读取到的滞后视图，本机桌面磁盘全程为真身、未损坏）；fsck 仍保留作早发现哨兵；报错即停，勿 pull/push，报 Paul 走恢复流程——**先把工作区未 commit 的改动手工备份到仓库外临时目录**，再 GitHub 重 clone，最后拷回未提交件与 .env/reports 等 gitignore 件（评审整改 2026-07-04：防重 clone 吞掉未提交成果）），再 `git pull`；收工 `git push`（GitHub=权威备份，.git 损毁可十分钟恢复）；同一文件别两边同时改。**排查"文件像是变旧了"的顺序（2026-07-07 定，先易后难，勿一上来就疑真损坏）**：① 先查 `git branch`/`git reflog`（是不是切错分支、或看的是旧提交）；② 再用桌面本机磁盘直读比对（桌面为真身，Cowork 挂载视图可能滞后）；③ 前两步都排除了，才怀疑真实损坏（走 fsck/重 clone 恢复流程）。**OneDrive 同步（Paul 实际惯例，2026-07-07 更正）**：OneDrive **平时全关**，每周趁其他程序休息手动开一次同步作纯离线备份，同步完即关；`.env`/`real_frozen/`/reports/*.db 等 gitignore 件不在 GitHub，其备份新鲜度按**最多一周旧**评估即可，当周产生重要新件时可提前加跑一次同步——不是"不可长关"。**乱码文件夹哨兵（2026-07-04 二次事故后强制）**：CC 开工与收工各查一次上级目录——`Projects\` 下 `*AI转*` 目录**应且仅应 1 个**（PowerShell：`Get-ChildItem ..\ -Directory | ? Name -like '*AI转*'`）；出现含 U+FFFD 乱码重名的兄弟文件夹即停手，按既例处置（整树移入 `_乱码重复文件夹隔离-日期\` 隔离夹、逐文件哈希比对真项目、**不直删**），并记录当刻哪个工具在写中文路径。根因指纹（2026-07-04 实证）：写入端 UTF-8 损坏，路径与文件内容**同现 U+FFFD**（11:42 QD-A 测试文件写入事故，每个汉字变 2 个 U+FFFD）；CC 写含中文路径的关键文件后，**读回抽验一处中文完整性**再继续。**时间戳必判 UTC vs Win 本地（Shao Peishen 2026-07-31 定，两桌全局硬规则）**：本机时区＝China Standard Time（**UTC+8**）。**引用任何时刻前，先答一句"这个值是 UTC 还是本地"，并在输出里显式标基准**（如 `09:04:31Z (17:04:31 本地)`）。**各证据源基准并不一致**——`reports/wecom_aibot_audit.jsonl` 存**真 UTC**（带 `+00:00`）；文件 mtime／计划任务 `LastRunTime`／Windows 事件日志／`LastBootUpTime` 是**本地**；企微机器人告警文案里的时刻是真 UTC。**两个实测陷阱（2026-07-31 同日各踩一次，均属误判前兆）**：① PowerShell 的 `ConvertFrom-Json`／`[datetime]::Parse` 会把 ISO 串解析成 `DateTime` 后**按本地时区显示**——同一批消息因此呈现 `09:07` 与 `17:07` 两种时刻，一度被误定性为"audit 时间基准不一致"（**险些多报一条不存在的缺陷**）；要真 UTC 须显式 `.ToUniversalTime()`，要对比就两个都打出来。② 时长差值**绝不用只含 `hh` 的格式串**（`.ToString("hh\:mm\:ss")` 会**丢掉 Days**，29 小时显示成 5 小时，差点据此误判"PC 今天重启过"），一律用 `TotalHours` 或 `d\.hh\:mm\:ss`。**为何是硬规则**：`#107` 归档↔队列配对判据、`#147` 存活戳、`#172` 的 1/3/7 天递减去重全部依赖时间戳，算错 8 小时即判据失效；本条是「取证先于定性」在时序推理上的具体化——**时序是取证最容易翻车的一环**。

### 附录 D · §5 指针化第一批（2026-08-22，OP-0822-B，队列 §四 #80 二期 ⑴）

> **与附录 A／B／C 的一处口径差别，须写明**：A／B／C 是**整条原文原样存档、§5 侧留拆分后的规则本体**；本附录**只搬「成因与实证」段，判据全文仍留在 §5**——因为 Shao Peishen 2026-08-22 当场裁定「判据全文优先于目标字节」，且方案件 §三 已划边界：**纯人守且已有违反记录的条目，判据不得指针化**。**⇒ 读本附录时不要以为 §5 那边只剩一句话；那边留着的是完整判据，这边是它为什么长成那样。**
> **本批搬运方式**：按行索引切片、一个字不重打；落盘后扫控制字符与 U+FFFD 均为 0。

#### D-1 · 原 §5「决策路由：在哪答」条的成因与实证（判据全文仍在 §5）

> **⑴ 旧判据（2026-08-04）两侧价值的论述与当日三例实证**（原文原样）：

**两者各自的价值，缺一不可**：⑴ **【原 session 答】**——决策与等待它的上下文在同一处，答完立刻能继续执行并自行收工，**不产生 #230 第二形态**（答复发生在别处、等待方不知道，2026-08-04 一天内三次）；⑵ **【总线答】**——**原 session 是当事人，它给的选项与推荐带着自己的视角**。2026-08-04 实证三例：A5 能否首发，是总线查 `git patch-id` 才发现 #221 的前提已被证伪；#234 该不该合并，是总线看到"五件同车尚未开工"才判出应拆开；#150 那封积压信，是总线核了跟进信串行原则（前一封未回件）才否掉当事 session 给的两个选项——**这三条当事人都看不到，因为它们不在它的上下文里**。

> **⑵ 「标注必须写具体 session 名」的成因**（原文原样）：

**成因（值得记，因为它不是笔误）**：2026-08-05 环境保障线 session 在**自己提出**的 #248 上标了 `【原 session 答】`，**既是废话、又标错了**——该项牵动 #164／#225／#230 三行、要派 CC、改的是 sweep 与编辑锁的**全项目口径**，按上文判据本应是 `【总线答】`。**根因与同日 #248 同源：规则被机械套用，没有先问一句「它在这个场合成立吗」。**

> **⑶ 2026-08-19 判据改版的成因——他的原话与那句洞察**（原文原样）：

**他的原话**：「如果 CC 已收口，后面又紧跟定夺选项，这样很容易引导我直接 CC 里回复，你却又希望我转场总线回复，有点绕，是否有更直接的做法和更明显的标注说明？」

🔑 **问题不在标注不够明显，在于「给了选项」本身就是邀请** —— 报告在哪，回复的引力就在哪；**加标注是在跟人的自然行为对抗，移除选项才是消除引力**。

> **⑷ 新旧判据当场可验的对照实例**（原文原样）：

**⚠️ 新判据比旧判据准，当场可验**：2026-08-19 `material-board-view-df54d1` 的收工报告两项——「#334 apply 接着做吗」答完它自己立刻执行 ⇒ ⟨就地答⟩ 标对了；「采购部#16 判例 3 虚构数据怎么处置」**它也标了本 session 答，但处置动作是对外发信／补判例、归 Cowork，它根本不会执行** ⇒ 按新判据应为「不给选项、登记待派」。**旧判据（按 session 活没活）判不出这一条。**

#### D-2 · 原 §5「会话末显式罗列决策项」条的「默认项两前提」三处实证（判据全文仍在 §5）

> ⚠️ **本条的可迁出量远小于方案件预估，如实登记**：方案件 §四 P0 表判「#204／#44 串栏实证已在 CHANGELOG 附录 B，正文那段是重复 ⇒ 删重复段」，**实测正文那处早已只是一行 25 字的指针，并无重复段可删**。该条 4,063 B 里绝大部分是格式四条与默认项两前提的**判据本体**，按 2026-08-22 裁定不得压缩 ⇒ **真实可迁出的只有下列三处实证，约 850 B**。

> **⑴ 前提一（有执行者在场）的实证**（原文原样）：

**实证**：§四 #71（`#334` 是否接着 apply）默认 (a)＝继续做，但提出它的 `material-board-view-df54d1` 已结束，`#334` 状态列至今停在 2026-08-17、零 apply 进展——**「不答按 (a)」在此从未生效过**。

> **⑵ 前提二（默认那一侧的代价是「暂时不变」）的实证**（原文原样）：

**实证**：§四 #73（`#282` 业务部门群此刻仍在收 sweep 机制告警）默认 (a)＝等 #282 整体做，而 #282 本身是 `[S:hold]`、无时间表 ⇒ **按默认＝让一个与既有拍板直接抵触的后果无限期持续**。

> **⑶ 「连带」——默认项冻住下游依赖的实证**（原文原样，原句以破折号承接上文「还须检查它有没有下游依赖被一起冻住」）：

——§四 #67（运维群 webhook URL）默认 (b)＝挂着，看似无害，但 #72／#73 均硬依赖它，**按默认等于三条一起冻**，且它已挂 12 天。

#### D-3 · 原 §5「每个场景固定流程」第 1 步内嵌的引导样板成因（判据与样板指针仍在 §5）

> §5 第 1 步现只留「唯一被允许的样板见 `bootstrap.py` 模块 docstring ＋ CI `bootstrap-stub-lint` 硬门禁强制」。**它为什么必须由机器守、而不是靠「照抄既有场景」**，原文原样如下——🔑 **这是本项目少见的「人守约定被遵守了、结果仍然错」的样本**：

「新场景 scaffold 的引导代码不再靠『照抄既有场景』」（该人守约定已于 2026-08-18 随队列 #345 第二步**机制化退休**——它曾被遵守却仍产出错误结果：SC2 照抄到的是无条件 `raise` 的 A 形态，抄到哪一种取决于作者当时看的是哪个文件，35 份副本已漂成 4 种彼此不等价的语义、其中一种在 `.51` 扁平布局下打挂过生产）

## 附录 · Last Updated 链历史（2026-08-16，memory 审核报告 P2 由根 `CLAUDE.md` 文末迁入）

> 迁移说明：根 `CLAUDE.md` 文末 `**Last Updated**` 链长期与顶部“当前进度”段双重记账（2026-08-16 实测 22,971 B，占全文 22%，是 08-09 瘦身后 7 天回涨 26% 的主因）。按 memory 审核报告 §四 P2：该行此后**只留最近 1 条 + 一行指针**，更早条目原文原样迁入本附录（不改写、不合并、不删减），共 30 条，按原顺序（新→旧）排列。

- **2026-08-18**（CC，worktree `fervent-jennings-46d4da`）：**SC2 部署 `.51:8096` 并冒烟通过**（commit `c39e33d`）——发布收口四关全过、tasks 9.5 完成；🔴 **design 审 ④(a) 定的 8095 被实测推翻**（已被 `ZhuopinRecruitAgent` 占用、8090 亦被 `UnifiedPortalGateway` 占用，原「顺延现网 8091-8094」的普查漏了两个口），Shao Peishen 当日改判 **8096**；部署当天修掉三件只在真部署才暴露的缺陷（#300 引导扁平布局硬失败／门禁把带前缀的健康检查挡在外面／页面「确认发布」按钮表单路径必然 400）；两条口径修正（服务端不再截断行级状态取数：830 料号 vs 缺省上限 200；**新增 O-7** 周中生成时本周窗口不完整致 21 个指标里 16 个被误打 🔴，已显式声明、根治属 D16-R 修改留待追认）；冒烟含**外部实测**与**进程 CreationDate 逐次核对**，服务器文件 SHA256 与 master 逐字节一致；回归 SC2 120／平台 295+1skip，`openspec validate --all --strict` 84/84；**9.2 archive 仍不做**（9.6/9.7 未完、tasks 未全 [x]），SC2 判例包归 Cowork 起草且串行闸阻塞源已变为 采购部#16（在途待审），详见上方"当前进度"段）｜ **更早**：本行历史条目（2026-07-31～2026-08-09 共 30 条）已于 2026-08-16 按 R5／memory 审核报告 P2 原文原样迁入 `1-转型规划/0-全景路线图/进度编年-CHANGELOG.md` §「附录 · Last Updated 链历史」；本行此后只留最近 1 条，更早查该附录与顶部"当前进度"段｜ 维护：本文件随架构/红线变更更新，时间线细节以实施计划第七节为准。　〔2026-08-19 由根 `CLAUDE.md` 文末按 R5「本行只留最近 1 条」迁入，原文原样未改写〕
- **同日更早**：2026-08-09（CC：队列#313——②本轮补齐 7+1 处 CLI 引导缺口（含新发现 SC1 main.py），commit `cc46fae` 直接 push master；真实 pip uninstall + 13 子项目全量回归发现 O2/SC1/SC7 三个场景 `tests/` 缺 conftest.py 导致 `ModuleNotFoundError`，已立即恢复全局指针原状，②仍不执行，详见上方"当前进度"段）
- **同日更早**：2026-08-09（CC：队列#308——F2命中处置收尾，§一/§二全量重跑F2得最新9行命中（非复用旧13行清单），逐条核实均为带日期子里程碑追记假阳性、非真实头尾矛盾，改用机器字段（决策点1权威源）退休⑧对§一的适用范围而非补引号剥离（避免新增第四例正则猜中文），新增2单测全量回归零漂移，`/opsx:archive`仍不做（7.3/7.5/8.3部分/8.4/9.4等既有未完成项超出本次授权范围未处理），commit `178624a`+`2668104`+`3621901`+`101b817`直接push master；详见上方"当前进度"段）
- **同日更早**：2026-08-09（CC：队列#313续第二三轮——②的两个已知前置（FI2路径引导/ops-worktree同步重启）已清，中途G2(#221)转done解除阻塞后重评②，系统性核查又发现FI1/FI2/SC7/SC8共7处新依赖，仍不满足故本轮未卸载全局editable指针，如实登记，commit `0e5fb96`直接push master；详见上方"当前进度"段）
- **同日更早**：2026-08-09（CC：队列#313——`queue_table`权威化收尾+一处正在发生的生产失效止血，①④⑤⑥已完成/②③评估后不做，commit `298c152`直接push master；详见上方"当前进度"段）
- **同日更早**：2026-08-09（Cowork 环境总线：**队列 #311 —— §5 正文瘦身 A/C/D/E 类 13 条按 08-05 判定表逐条执行**。**A 类 4 条降指针**（ff-only→`_reconcile_with_origin_and_push`／全景重组→skill `zhuopin-rebaseline`＋变更日志件／企微推送→`发企微.py`／文档治理 R1R2→`工具-文档台账生成.py`，R3-R6 保留正文）；**C 类 2 条采纳判定表自带反方意见**——正文各留「判别两分支」边界句、细则与成因迁环境总线 opener 新增 §六bis（理由：C1 的消费者恰恰不是本线，只留指针即复现 #311 根因链第②段）；**D 类 3 条**新建 `0-学习与工具/取证方法知识库.md` 承接（建在此处因它会被台账扫到、且刻意不并进 opener 模板库），**D3 工具静默回退在 §5 保留一行硬提示**；**E 类 3 条拆为 11 条单一职责条目**，三条原文整条存档进 `进度编年-CHANGELOG.md` 新增「附录 · 规则成因判例」，**🔴「新场景一律不新起端口」已从混装条目里拆出独立成条**（判定表点名的那条被埋硬约束）；B2 队列纪律段降为指向协议〇 的指针。**实测结果**：§5 23,886 → 20,028 字符（−16.2%），**单条最长 3,568 → 1,299 字**，顶层条目 22 → 30；CLAUDE.md 92,885 → 84,399 字节。全程占 `--file CLAUDE.md` 编辑锁；逐条写后反查（字节差／44 项关键词命中／指针两端互查／9 个目标文件存在性）通过，FFFD=0。**一处勘误**：判定表把 A1 机制写作 `_verify_fast_forward`，该函数已于 2026-08-06 队列 #288 重构中整体删除，指针改指现役 `_reconcile_with_origin_and_push`——**这正是判定表自己点名的「指针指向已不存在的东西」第二例**。详见队列 #311 与判定表回填）
- **同日更早**：2026-08-09（Cowork 环境总线：**「记忆偏差」根因整治第一步**——R5 第三批迁移，顶部进度段 18 条原文原样迁 CHANGELOG，**本文件 154 KB → 92 KB（−40%）**；同批执行 08-05 判定表的 B1（唯一判为"可直接删"的重复引块，其指针早已失效）。**根因链三段均已实测**：①规则不入法只活当次会话（「opener 须标 session 明细」全库零历史痕迹，而同族已入法三条至今在用）②入法但落在非必读载体仍会缺席（opener 模板库 12 条，出 opener 时不读）③落进必读载体也被稀释（迁移前流水账占 49%）。A/C/D/E 类 13 条正文瘦身**已立队列行承接、不再"另排"**。详见队列 #311）
- **同日更早**：2026-08-09（CC：队列#308——Shao Peishen批准design，apply核心实现完成，状态字段6值+域字段+措施B/C+D1/D2告警生命周期+F1/F2/G编辑锁校验+106行存量回填+六处消费者切换，全量回归零漂移(编辑锁124/sweep138/队列查询14/lint7/wecom-aibot-service357+1skip)，openspec validate --all --strict 73/73通过，变更包暂不archive(部分验证项如实未勾)。详见上方"当前进度"段）
- **同日更早**：2026-08-09（CC：队列#308——propose+design产出，openspec变更包queue-status-machine-field，状态机器字段(6值)+域字段(§4.5.1原样并入)+措施B守卫退休问询+措施C WIP超限提示+子项D告警生命周期(D1通用骨架+D2指纹抑制)+子项F编辑锁F1F2+子项G跟进信串行闸(带豁免逃生阀)，openspec validate --all --strict 73/73通过，仅propose+design，未apply，待Shao Peishen审核design.md十个决策点。详见上方"当前进度"段）
- **同日更早**：2026-08-09（CC：队列#267——签字材料真实丢失事故根治，`工具-孤儿worktree扫描.py`新增第三桶识别ahead=0且tracked干净但存在gitignore非空内容的worktree（`--ignored=matching`+文件系统复核排除空目录假阳性），报告标注「删除将永久销毁以下不在git里的文件」并逐路径列出；未加删除能力、未加协议人守条目（Shao Peishen拍板(a)，理由：人守正是退休制要淘汰的东西）；三处边界披露（脚本docstring/新桶报告文案/本行）均已落实"仅覆盖经工具走的路径，直接手敲git worktree remove仍无拦截"；新增2单测，全量回归7 passed零漂移；真实dry-run对当前共享主工作区命中6个真实worktree含1处真实数据目录，坐实修复前会被误判入安全可删桶。详见上方"当前进度"段队列#267条目）
- **更早**：2026-08-08（CC：队列#309——CI基线三步骤全部收口，含真实并发冲突排查+三轮真实CI故障修复(zhuopin_platform全局指针/PYTHONUTF8编码/git quotepath)+步骤3审计结论(8类sweep守卫逐一核对CI四项检查均不重复,Shao Peishen拍板不强行退休)+矩阵自动发现与覆盖率护栏(替代硬编码13项清单)+一处基线勘误(1704/40→1698/46,QD-A/QD-B各一处真实立项书样本依赖测试)+顺带修复QD-A pyproject.toml两处bug；5轮真实GitHub Actions验证18/18全绿，#309行状态转✅已完成。详见上方"当前进度"段）
- **更早**：2026-08-08（CC：队列#309子项F——sweep起跑段硬return挡住#288收尾rebase根治，与#288`_sync_master_if_behind_origin`完全同构复发（同一"前置检查阻断整轮"形态在`_push_any_unpushed_commits`复现）；开工先手工解一次主工作区master/origin真实分叉（未用checkout/restore，直接commit已声明WIP批次+rebase+push）；修法为检测到分叉时不再SweepAbort、记录日志后return继续批次处理，分叉判定/自动rebase/告警统一移交收尾段`_reconcile_with_origin_and_push`；新增/改写4个测试（真实bare origin+真实git子进程复现三要素叠加场景），全量回归125passed零漂移；openspec变更包`sweep-startup-fork-defer-to-reconcile`已apply+归档，`sweep-startup-resilience`capability同步更新；真实验证边界如实登记（未在共享主工作区人为构造分叉演练，风险判断同#288既有权衡）；#309整体状态不变（CI基线步骤1-3仍未开工）。详见上方"当前进度"段）
- **更早**：2026-08-08（CC：队列#300——并行CC建造隔离根治，openspec变更包`worktree-import-path-bootstrap`已apply+归档；根因=本机无venv、`pip install -e`把权威源码写成全机唯一site-packages指针，与git worktree"N份平等副本"前提矛盾，任一worktree跑一次会静默顶替其余worktree的import解析（测试全绿但测的是别人代码），与既有#98/#208同族；选定候选丙（conftest.py+服务入口统一sys.path引导），否掉venv与共享_bootstrap.py+indirection；范围经逐文件核实从7份conftest.py收窄为6份（QD-A实测不在冲突面，零zhuopin_platform依赖+自身包从未editable安装）+5个服务入口脚本；新增4个专项回归测试（真实subprocess+合成哨兵值验证核心场景）；真实并行验证已完成（真实创建第二worktree+真实pip install -e污染全局指针+本worktree测试全绿证明结果与指针无关，验证后已清理复原）；全量回归零漂移（zhuopin_platform 262+1skip/SC8 377+4skip/FI1 33/FI2 128+9skip/QD-B 83+25skip/wecom-aibot-service 344+1skip，均与既有基线一致）；`.51`三服务不需紧急重新部署（各自独立venv不受此故障影响），企微机器人常驻服务建议随下次常规重启带上（本机不在LAN未做）。详见上方"当前进度"段）
- **更早**：2026-08-07（CC：队列#299+#195同车——spec缺口补齐批；#299三个已建造场景（FI2/FI1形态甲判定13/12项未完成任务均真实未完工、不假装勾完，改`/opsx:sync`不归档合入5+4个delta；wecom-aibot-channel同判只sync3个；QD-A形态乙反向读4个源文件补写4个capability回填进已归档包，场景代码零改动；macos迁移/SC3/SC5/deploy-tools按范围排除或不催）+ #195剩余2项（`--reserve`/`queue_lock_pending`复核已稳定，新变更包`retroactive-mechanism-specs-batch2`补写`editlock-queue-number-reservation`7条Requirement+`aibot-queue-append-lock-deferral`5条Requirement并归档，累计7/8）；两行合计新增12个capability，全程零代码改动，`openspec validate --all --strict`由49capability/38items升至66capability/71items（0 failed）。详见上方"当前进度"段）
- **更早**：2026-08-06（CC：队列#294修法⑴——跟进信发送状态两态语义扩为三态，新增`⏸暂缓`；README状态列此前无法表达"已批准但暂缓"，`ZhuopinFollowupDispatchDaily`照字面值执行导致已决定暂缓的#150判例包信01:30 UTC被误发；新增`readme_table.PAUSED_STATUS`+`dispatch.py`新增`skipped_paused`可观测+README两态语义节改写为三态；全量回归wecom-aibot-service 344passed+1skip（原338+1，+6新测试零回归）；commit`ef0725e`/`a2bf8f6`已push master。范围按业务总线拆分只做修法⑴，修法⑵（README↔队列一致性校验）划归#258（P2待领）——语义未闭合，未触碰工具-共享文档编辑锁.py。详见上方"当前进度"段）
- **更早**：2026-08-06（CC：队列#287+#286+#289+#283同车——企微机器人队列同步四件套，openspec变更包aibot-queue-sync-checkout-guard已apply（design获Shao Peishen批准候选A），暂不归档；#287用真实git子进程+真实调用生产函数复现坐实根因（非mock）——冲突重算前`git add`会把磁盘上任何未提交内容(含协议〇.7/〇.8允许的"人类已release未commit"合法态)一并暂存进本地commit，非快进冲突后`reset`+`checkout`连根拔起；新增`_diff_exceeds_expected`护栏，销毁性重算前校验实际改动是否超出预期规模，超出即改用`reset --soft HEAD~1`保留工作区、否掉候选B"全程持锁"(已证实锁语义解决不了本问题)；#286补上`pending_queue_appends.jsonl`此前完全没有的flush通道+锁忙与真实git失败分流；#289让`delivery.py`回填README后自动commit+push(候选甲，非快进冲突改用安全的fetch+rebase+abort，非#287揭示的销毁性路径)；#283剥离跟进信私信泄漏的YAML frontmatter。全量回归零漂移(wecom-aibot-service 338passed+1skip含18新测试、平台248passed+1skip)；三项代码修复与护栏均已合入master；**部署债已于同日21:51本地由CC（独立worktree `deployment-debt-cleanup-c70663`）收口**——ops/wecom-service-home已ff-merge至6854f8a+worktree内独立复跑338passed+1skip+ZhuopinAibotDevListener重启(PID 110768→110944)+心跳戳13:51:26Z确认真实建连，真实企微发送验证与openspec §3被动观察仍留待后续。详见上方"当前进度"段）
- **更早**：2026-08-06（CC：队列#110/#112同批——保供看板反馈按钮+判例包网页表单化+四服务访问日志采集框架；开局拦下一次错误派单（webhook参数已被同日拍板推翻），范围收窄为只建采集、通道留白；全量回归零漂移（SC8 360+27/平台259+11/QD-B 83+3/FI2 110+3/命令中心14+5/SC1 53/SC7 41黄金基准精确不漂移/O2 20）；已ff合入master(commit `774cdee`)+四服务`.51`真实部署+真实POST/GET验证+SSH核验四份访问日志与反馈JSONL真实落盘；顺带修复命令中心serve.py一处PORT sys.argv潜在崩溃bug。详见上方"当前进度"段）
- **更早**：2026-08-06（CC：队列#288——sweep落库卡死机制化，openspec变更包sweep-ff-sync-batch-reorder已apply+归档；批次先本地提交后统一对齐origin/master（纯落后ff-only/纯领先直推/已分叉rebase，冲突即abort回滚+复用#171分叉告警），旧_sync_master_if_behind_origin/_verify_fast_forward已删；单测新增6个（含核心复现场景），全量回归78passed零漂移；真实主工作区验证两轮均完成——第一轮真实处理4个被本bug卡住的积压批次，第二轮用真实并发worktree推送精确复现故障链本身并确认已git rebase自动对齐推送成功；真实内容冲突子场景仅经单测覆盖未做真实构造，如实登记边界。详见上方"当前进度"段）
- **更早**：2026-08-05（CC：队列#262+#263同车（D批）——#262答交数量/日期查询窗口固定60天根治v3（新增分段前瞻查询，默认180天覆盖绝大多数真实答交记录，真实数据端到端复现精确匹配姚祖怡截图值10000/2026-11-25）；#263替代料关系多层穿透（识别定义在半成品子件BOM里的替代对，30个真实成品中11个F02N前缀受影响，Shao Peishen拍板先建后签，交付强制含缺口/齐套数字对照+黄金基准重跑差异说明两份材料，counts与修复前完全一致98红/5绿如实说明非唯一瓶颈）；顺带发现并登记新待办#266（kittable_qty对半成品结构成品恒为0的既有架构限制）；全量回归零漂移（SC8 333+20新测试/平台248/SC1 53/SC7 41黄金基准精确不漂移/O2 20）；两行均已ff合入master+`.51:8091`部署冒烟通过。详见上方"当前进度"段）
- **更早**：2026-08-05（CC：队列#248——sweep与编辑锁状态列关键词判据锚定，openspec变更包已apply+归档，design四决策点均按默认(a)获批；apply阶段发现并修正一处实现细节（"锚定开头"从"第一字符"改精确为"第一句级分隔符之前"，因会破坏既有回归测试固化的2026-07-27真实误写场景）；historically兼容核对§二17行0分歧/§一63行仅#221一处（已解决）；全量回归零漂移（sweep 73+5新测试/编辑锁71+2新测试）。详见上方"当前进度"段）
- **更早**：2026-08-05（CC：队列#208+#223+#101①同车（B批）——#208 triage确证`test_po_srm_confirmed_date.py`5个失败为测试夹具写死绝对日期到期（日历漂移，非回归/非污染/非helper改动，冻结时间复现证实代码逻辑从未有误），修复仅改测试文件零生产代码改动；#223 SC8客户草稿"确定延期"措辞在瓶颈子件无答复时改用"交期未确认"，新增`bottleneck_unanswered`字段贯穿建案/展示/措辞三层，只改对客口径不改判定逻辑；#101①`工具-落库sweep.py`新增只读CLI核验§二待批次声明、`工具-主工作区安全同步.ps1`据此禁止误建议checkout；全量回归零漂移（SC8 313+10新测试/平台248/sweep自身68+5新测试）。详见上方"当前进度"段）
- **更早**：2026-08-05（CC：队列#238/#236/#229/#227②四件同车——sweep批次隔离安全内核收尾：main() unaccounted全局门改逐批次判定（_partition_pending_rows_by_batch_isolation，只阻塞自身声明歧义的批次+可解释日志）+孤儿脏文件持续告警（3小时阈值+周期性再提醒）+发布收口第②关部署留痕检查（SC8/QD-B/FI2+命令中心白名单）+新增仓库外载体扫描脚本（Cowork artifacts/.51四服务/已安装skill/定时任务真身）；#236(1)认领即预登记批次因涉全项目口径已产出openspec propose+design待Shao Peishen审核；全量回归零漂移（sweep 63+21新测试、扫描脚本10新测试）；真实主工作区触发两轮sweep验证批次隔离与孤儿告警在真实并发场景下工作正常。详见上方"当前进度"段）
- **更早**：——跟进信发送机制化安全内核：README两态语义（批准脚本+10分钟冷却窗口）+编辑锁README结构性拦截+每日批处理ZhuopinFollowupDispatchDaily（09:30）+漏标硬截止机器判据兜底；apply期间master两次并行前进（#200/#185/#93等），rebase均零冲突自动合并；全量回归零漂移（aibot-service 265+1skip/平台243+1skip，63个新测试）；真实部署+真实端到端验证（真实凭据+真实WebSocket+真实Start-ScheduledTask触发，冷却窗口真实65秒等待验证生效，🔒人工发送与机器判据两类跳过均验证），发现生产唯一现存积压行因3个候选文件歧义被安全跳过（如实登记待人工消歧）。详见上方"当前进度"段）
- **更早**：2026-08-04（CC：同 session 续跑机制加固——#231真实部署验证（ZhuopinDecisionReminderDaily已确认Execute=wscript.exe生效，ZhuopinCommitSweep因LogonType S4U注销需管理员权限已备提权代码块）+ #200绕锁改写检测（.editlock.lastknown比对+审计留痕）+ #185多分区预留（--reserve-multi）与竞态防护（reserve前核对可见行避免分配已占用编号）；四处调用方措辞回改（协议〇.7+两份skill源码，已安装版/仓库外定时任务prompt留痕待办）；22个新测试，全量回归编辑锁64+sweep44 passed零漂移。详见上方"当前进度"段）
- **更早**：2026-08-04（CC：平台杂项批七行同车#92/#93/#108/#188/#209/#233/#96——transcript中文重复bug修复、push_followup多附件支持、sync_sales_data环境变量化+边界单测、QD-B上传文件名过滤、定时任务镜像核对判据验证（#169已覆盖+补回归测试）、platform-data-connectors spec补4个Requirement+修正TLS描述、五份deploy-server.ps1统一收编进ZhuopinDeploy.psm1(含补BOM)；全程未触碰.51/生产，全量回归零漂移。详见上方"当前进度"段）
- **更早**：2026-08-04（CC：机制加固五件同车 + 队列#234(1)紧急插队——sweep `_resolve_batch_files` 精确相等优先止血批次积压、决策提醒第二载体、启动即写日志首行、编辑锁 release 四项结构校验（含 dogfooding 中发现并修正 P0/P1 断言门槛的整行误判为状态列精确检查）、acquire 回显近场者、两计划任务 VBS 免弹窗；全量回归 sweep 44+编辑锁 49 passed 零漂移，38 个新测试；真实验证：主工作区同步后真实触发一轮生产 sweep 退出码 0，队列七行状态已用新校验本身回填。详见上方"当前进度"段）
- **更早**：2026-08-02（CC：队列 #206 proposal 强制门禁段迁 `openspec/config.yaml` rules——openspec 变更包 `openspec-config-proposal-rules`，commit `e912434`，已归档；双盲测证实 rules 语义匹配（不需自定义 schema），C3 强制 `openspec update --force` 验证 config.yaml 哈希改前改后完全一致，抗覆盖修复通过；详见上方"当前进度"段）
- **更早**：2026-08-02（CC：sweep 与机器人机制五行同批修复——队列 #192/#193/#194/#198/#199，openspec `sweep-aibot-reliability-batch`，commit `5601c0e`；sweep 起跑段新增编辑锁探测/未推送提交补推/pending flush/异常兜底/部署提示，机器人新增断连"进行中"提示，`0x800710E0` 如实标注不可回溯；全量回归零漂移+18/+13 新测试，真实部署 `ops/wecom-service-home` 重启验证，`ZhuopinCommitSweep` 手动+自动触发确认新代码生产运行；#199②+#193 次要项因需管理员权限整理为提权代码块待 Shao Peishen 执行。详见上方"当前进度"段）
- **更早**：2026-08-02（CC：台面清理执行清单收尾——队列 #165／#101②③／#166／#125／#207，A/B 类 worktree 清理 4 个+#125 销行+#207 补齐 5/5+#166 按裁定只落③+3 条 stash 经 Shao Peishen 授权已清零、#101②③随之销行；仅剩 1 个空壳目录因句柄占用未删，如实登记待下期体检）
- **更早**：2026-07-31（CC：FI2 三单匹配面板 v8 改造——队列 #182/#183，唐燕萍权威规格书驱动的展示层重建（六段式 → 结论看板+展开/并拢主表），只改 `fi2/webapp.py` 一个文件，`match_engine.py`/`result_classify.py`/`price_check.py`/`recon_report.py`/`config.py`/`models.py` 零改动；#183 免责声明+#175⑤提示语归并均已落地；OCR/重复检测/税率合规/PO变更检测四维如实标注“二期未接入”不伪装已判定。FI2 99 passed+7 skip、平台 244 passed+1 skip零回归；真实部署 `.51:8094` 冒烟三件套全绿。详见上方“当前进度”段与队列 #182/#183、`4-数字员工/财务部/FI2-三单匹配自动对账/CLAUDE.md`）
- **更早历史**：与"当前进度"段重复的旧条目（07-04～07-30）已删除，完整时间线见上方"当前进度"段（07-03 起）与 `1-转型规划/0-全景路线图/进度编年-CHANGELOG.md`（07-03 前，按 R5 规则迁档）


## 2026-08-09 ～ 2026-08-18（第四批迁移，2026-08-21）

> **迁移依据**：R5「根 CLAUDE.md 顶部进度段只留最近一批」＋ OP-0821-B 新增的前置判据——**迁出前须确认该条已有承接载体（队列行号，或具名文件＋章节）；无承接载体者不得迁**。本批 8 条全部满足（#308／#313／#267 各有队列 §一 行；全景 v6 重排的承接载体是《卓品智能AI转型全景规划》§0.2 的 2026-08-18 登记行）。**同期的 SC2 两条（2026-08-18）经核判定不可迁**——其正文自陈「按 design 审 5(a) 仍未立队列 §一 行，故本段与上一段是本任务仅有的跨会话载体」，迁走即丢掉 9.2 archive 与 9.6-9.7 跟进信两项未闭合事项，故原样留在根 CLAUDE.md 并另行登记为缺口。

> 🔴 **全景 v6 重排：销售域＋工程研发域整域顺延入 S3，Q5 提前，S1 目标 14-16→11-13（2026-08-18，Cowork 全景路线图线，重组循环第 7 例·结构级，本项目迄今范围最大的一次重排）**：源＝Shao Peishen 2026-08-18 拍板「**接公司新需求调整，销售域和工程研发域全部暂停延后，其他域尽量提前**」，落法与目标数由其在《S1中期对标-2026-08-17》§7.5 二选定死。**① 两域 11 场景整域顺延**：R1 2026-10→**2027-07**／R2→2027-08／R3→2027-09／R4→2027-10／R5→**2027-11**（工程研发收官）；销售 S1 2026-11→**2027-07**／S2→2027-08／S3→2027-09／S4→2027-10／S5→2027-11／S6 2027-02→**2027-12**（销售收官），顺带消解 v5 遗留的 S5 晚于 S6 倒序。**② Q5 IATF 2027-01→2026-12**（逐条核过 2027 全部场景，唯一真能提前的；SC7②／FI4／FI1 复启／O4／SC10／SC11 均判不可提前并写明理由）。**③ S1 目标场景数 14-16→11-13**——**算术而非执行**：顺延后 S1 期内只剩 13 个场景，14 已超总数。**④ 四条易漏的连带口径**：R 系列旧「Chroma 9/30 未就绪则顺延」条款**作废**（**本次成因是公司优先级、不是条件未达，两个成因不可混淆**）／Champion 门禁**挂起**（新门禁日约 2027-05）／🔴 **OEM 隔离层 Chroma 不随 R 系列停摆**——归属改挂「质量域 Q4 PPAP 前置 ＋ QD-B 已上线场景 OEM 红线」、截止放宽 **2027-01**（否则 QD-B 那条 IATF 红线会变成「写了但底层没有」）／S6 知识线 2026-Q4 窗口取消、改 2027-10 前，原「12 月底未完成则顺延 2027-03」条件自然失效。**⑤ 两处须在 2027 年初复盘盯住**：**S3 由「显式规划缓冲」变为「11 场景集中入轨收官期」，缓冲已被本次顺延占用**（此后 S1/S2 再顺延将无处消化，只能挤压 Phase 2）；**四链受影响**——链 D 起点 S6 后移约 10 个月、链 E 整条落入 S3 几无沉淀期，**S3 收官验收「四链至少两条达档3」应改从链 B／链 C 取**。**⑥ 不变**：全景总数仍 **40**（暂停≠注销，编号与内容一字未改）；**年度达标线三条按原值不动**（使用线卡的是周活跃埋点统计未启用、非场景数，不借重排顺手放宽）；四域 2026 排期除 Q5 外未动。**⑦ 沉没成本 ＝ 0**——受影响的 5 个 S1 内场景全部零产出，`4-数字员工/` 下本无「工程研发部」「销售部」目录。**九文档已零残差重排落档**（全景规划含 §0.2 登记／实施计划／甘特 HTML 月份轴 12→18 列／前置总表／四链蓝图／协同一页纸／本文件／接力／变更日志第 7 行）＋ 两份 docx 同批重转。详见 `1-转型规划/0-全景路线图/S1中期对标-2026-08-17.md` §七 与全景规划 §0.2 2026-08-18 行。

> **队列 #308——F2 命中处置收尾，`/opsx:archive` 仍不做（2026-08-09，CC，独立 worktree `queue-308-f2-cleanup`，commit `178624a`+`2668104`+`3621901`+`101b817`，直接 push master）**：处置 tasks.md 8.6 遗留项——§一/§二 全量重跑 F2（⑧头尾不一致），最新命中 9 行（均 §一：#22/#67/#96/#98/#118/#170/#234/#240/#264；旧 13 行清单因 #252/#267/#285/#308 同日已被改动而失真，不可复用）。**逐条核实结论与 8.6 原判断不符**：9 行均非「」/『』引号包裹的引用文本（与 #221/#248 不同源），而是**带日期的子里程碑追记**（如"✅ 节奏已定（日期）"），机器字段均诚实反映真实 partial/blocked/hold/open 状态，**无一行真头尾矛盾，未改动任何历史正文**。**未采用「加引号再剥离」**——那会在 #308 要消灭的「用正则猜中文」家族里新增第四例，而非收敛；**改为退休 ⑧ 对 §一 的适用范围**：字段解析成功即跳过（决策点 1 已确立字段为权威源），仅字段缺失/非法时回退旧判据，§二 无字段覆盖、⑧ 原样保留——`config.yaml`守卫退休问询规则本批 dogfooding 答案即此。新增 2 单测，全量回归零漂移（编辑锁 130、sweep+队列查询+lint 162+6subtests、wecom-aibot-service 357+1skip）；`release` 真实跑过一次新逻辑（真实主工作区 `acquire`/`release` 回写 #308 行）。**`/opsx:archive` 仍不做**：8.6 已收口不再是阻塞项，但 tasks.md 7.3／7.5／8.3（除本轮真实触发 F2 一项外其余未覆盖）／8.4／9.4 均为此前 session 已如实登记、本轮未处理的未完成项（超出本次授权范围，未擅自重开这些判断），archive 前置条件仍不满足，留待后续 session。**收工自删 worktree 实测复现 #267 已知限制**：`Permission denied`（自身会话锚定其上），但 git 侧已成功注销注册、物理目录清空为空壳，零数据风险，留待后续清理。详见队列 #308、`openspec/changes/queue-status-machine-field/tasks.md`。

> **队列 #313——②本轮补齐 7+1 处 CLI 引导缺口，真实 pip uninstall + 13 子项目全量回归后发现新一类缺口（O2/SC1/SC7 conftest.py 缺失），②仍不执行（2026-08-09，CC，独立 worktree `global-pointer-removal`，commit `cc46fae` 直接 push master）**：领取上一轮发现的 7 处缺口（`fi1/{run,confirm}.py`／`fi2/{run,confirm,dump_u9c_snapshot}.py`／`sc7_inventory/agent.py`／`sc8/answer_confidence.py`）均已补 #300 同款 sys.path 引导，**全库 `__main__` 穷举扫描（非仅直接 import 文本匹配，含间接依赖追踪）额外发现第 8 处**——SC1 `main.py`（通过 `src.audit_log`/`src.data_providers` 间接依赖，自身从不出现字面量 "zhuopin_platform"，上一轮方法必然漏扫），一并修复。45 个 `__main__` 候选全部确认引导 OK 或本就不依赖后，真实 `pip uninstall zhuopin_platform` + 按 `.github/workflows/ci.yml` 矩阵口径逐子项目（13 个）跑回归：**10/13 通过，O2/SC1/SC7 三个场景 collection 阶段 `ModuleNotFoundError`**——实测确认这三个场景的 `tests/` 目录从未有过 `conftest.py`，长期隐式依赖全局 editable 指针；CI 自身测不出此问题是因 CI 每子项目跑测试前会先 `pip install --no-deps -e` （干净 VM 无历史指针问题，刻意选择）。发现后已立即将全局指针恢复到卸载前原状（指向 `followup-dispatch-apply-25679f`，与 `pip show` 原记录逐字一致），未影响本机其它并发进程/常驻服务（事前已核实 `ZhuopinAibotDevListener` 入口本就有独立引导，不受影响）。**⇒ 本轮仍不执行②**，O2/SC1/SC7 补 `tests/conftest.py`（可照抄 FI1/FI2/QD-B/SC8 现有同款引导）留作 ② 新前置，供下一轮领取。**方法论结论**：CLI 入口维度的穷举已可确认，但 pytest collection 与 CLI 运行时是两条独立触发路径，各自需独立验证；下轮顺序：补 conftest.py → 重跑同款 uninstall+回归 → 全绿再执行②。详见队列 #313。

> **队列 #313——`queue_table` 权威化收尾，含一处正在发生的生产失效止血（2026-08-09，CC，commit `298c152`，直接 push master）**：①④⑤⑥已完成，②③评估后判定本次不做（如实登记，非遗漏）。**①止血**：`decision_reminder_check.py` 及同目录另 7 个入口脚本（`alert_webhook`/`approve_followup_letter`/`check_connection`/`dispatch_followup_letters`/`echo_test`/`flush_pending_lock_appends`/`push_followup_letter`）补 #300 同款 `zhuopin_platform` 路径引导，消除对可变全局 editable 指针的依赖；查清 `sweep-commit.log` 全部 23 次「第二载体退出码 1」——17 次（L43 整包缺失）与 6 次（L50 `queue_table` 子模块缺失）系同一根因两种症状，本次修复同时解决两者。审计中发现 FI2 `ingest_tax_export.py` 同族缺口（已 `spawn_task` 流出，不在本行范围直接改）。**④CI 兜底桩可见化**：`工具-队列结构lint.py` 新增权威模块可 import 断言（零依赖直接 sys.path 引导，未改 CI workflow），one-in-one-out 退休 `zhuopin-queue-audit` 类型⑧「预登记批次陈旧」（三独立信源复核零命中，`SKILL.md` v1.6→v1.8，**已安装版待 Cowork `save_skill --overwrite` 同步**）。**⑤路径收拢**：编辑锁/队列查询/台账三处 `DEFAULT_TARGET`/`QUEUE_PATH` 收进新增的 `queue_table.QUEUE_PATH_REL`，验证解析结果逐字节不变；sweep 自身另有一份独立 `QUEUE_REL`（第 4 处，超出派单件"3 处"范围，本次未动，如实登记）。**⑥** `MECHANISM_WIP_CAP_DEFAULT` 8→16（Shao Peishen 2026-08-09 拍板）；看板 artifact `zhuopin-project-status` WIP 分母因该 artifact 非本仓库文件、CC session 无法访问（`Artifact list` 零可见），未能核实，留 Cowork。**②除根未执行**：核查发现两处真实未迁移依赖——FI2 `ingest_tax_export.py`（已流出待办）与 **`ops/wecom-service-home` worktree 的 `decision_reminder_check.py` 副本仍未修复**（该 worktree 是生产/常驻服务部署载体），不满足派单件自身"先确认无其它进程依赖"前提，故未卸载全局 editable install，留待两处依赖迁移后重新评估。**③告警升级未做**：one-in-one-out 额度已被④用尽，且①已消除当前唯一已知触发源，判断新增常驻告警不值得。**openspec 判定**：①④⑥不改变既有函数在相同输入下行为，⑤经验证解析结果不变，均不触发；②③未执行。**全量回归零漂移**：编辑锁+队列查询+台账 149、队列结构lint 10（含 3 新增）、sweep 138、`wecom-aibot-service` 357+1skip、`zhuopin_platform` 平台 277+1skip；`openspec validate --all --strict` 74/74。**⚠️ 一处流程偏离，如实登记**：派单件开场词要求新建 worktree `queue-table-reachability`，但本 session 全程 `cd` 到的是共享主工作区根目录（而非其专属 worktree），故本次工作与 commit 均直接落在该共享工作区的 `master` 分支（提交前已核实与 `origin/master` 零分叉，push 为纯 fast-forward，未与任何人冲突）；该 session 自身专属 worktree（`.claude/worktrees/followup-dispatch-apply-25679f`，分支 `claude/queue-313-reachability-752fd7`）全程未被使用，仍停留在旧提交，如后续无需保留可按孤儿 worktree 常规流程清理。详见队列 #313。

> **队列 #313（续第二三轮）——②的两个已知前置已清，重评②又发现 7 处新依赖，本轮仍不卸载（2026-08-09，CC，独立 worktree `queue-table-reachability-2`，commit `0e5fb96`，直接 push master）**：本轮任务是清 ② 的两个已知前置并重新评估。**前置 1（FI2）已清**——`ingest_tax_export.py` 补齐同款 #300 路径引导，真实冒烟 exit 0，FI2 回归 128+9skip 零漂移。**前置 2（`ops/wecom-service-home`）已清**——该 worktree 落后 origin/master 27 提交，`ff-merge` 对齐，该 worktree 内 `wecom-aibot-service` 回归 357+1skip 零漂移，重启 `ZhuopinAibotDevListener`（顺带发现 `Stop-ScheduledTask` 会遗留孤儿子进程的坑，已手工补杀+验证心跳戳真实建连）。**中途 G2（#221）在写回后不久被 Shao Peishen 授权删分支、转 `[S:done]`**，解除阻塞，遂按派单指令续判 ②：**用 `git grep` 系统性核查全库 69 个消费 `zhuopin_platform` 的非测试文件、筛出 25 个含 `__main__` 的候选入口，逐一核对 sys.path 引导，新发现 7 处缺口**——`fi1/run.py`／`fi1/confirm.py`／`fi2/run.py`／`fi2/confirm.py`／`fi2/dump_u9c_snapshot.py`／`sc7_inventory/agent.py`／`sc8/answer_confidence.py`，均无引导、当前依赖全局 editable 指针；已实测坐实（FI1 场景目录内 `python -m fi1.run --help` 当场只靠陈旧 worktree 指针成功执行）。**⇒ ② 仍不满足「无其它进程依赖」，本轮未卸载、不勉强执行**，7 处新依赖已如实登记进 #313 行，留给下一轮按本轮 FI2 同款手法补引导。详见队列 #313。

> **队列 #308——Shao Peishen 批准 design，apply 核心实现已完成（2026-08-09，CC，同 worktree，commit 待补，§二批次 `B-0809_队列308apply核心实现`）**：状态字段 6 值＋域字段（决策点1/2，`[S:done/open/partial/hold/blocked/timed=YYYY-MM-DD][D:机/业]`，仅 §一）／措施B `openspec/config.yaml` 守卫退休问询规则（决策点5）／措施C 编辑锁 release 机制类可动 WIP 超限非阻断提示（决策点6）／子项D1 通用出现→解除骨架 `_track_and_alert_standing_state` retrofit 分叉+场景spec缺口+在途包滞留三类告警／D2 判断型告警指纹抑制（新增 `--ack-stale-change` CLI，指纹未变即静默、变了恢复告警，区别于永久白名单）／子项F1（§二新增批次不得以✅开头）F2（✅不在开头片段即报）／子项G 跟进信串行闸挪入 `_validate_followup_readme_release`（带 `串行豁免：` 逃生阀）——均已实现并配单测。**106 行存量回填**：脚本初筛（既有关键词启发式+人工复核已知特殊行，如 #129/#202/#217/#259 定时触发型、#67/#95/#155/#224/#81/#240/#251 受外部阻塞型）＋ 17 处新旧判据分歧清单逐条核对；用真实 git blob 逐行比对验证（非 diff 文本重建，因长行导致 git diff 文本切分有误导性artefact）：108/108 行正确、其余 7 列与回填前byte-identical。**七处消费者**：编辑锁/sweep（`_find_stale_pending_rows` 改读字段，非静默降级）/`工具-队列结构lint.py`（新增 CI 硬门禁：§一行缺字段即 lint 违规，已对真实生产文件验证通过）/`工具-队列查询.py`（§一展示解析结果，冲突检测收窄到字段后正文）/`decision_reminder.py`（`parse_priority_pending_rows` 改读字段+`RuntimeWarning`非静默降级）/`queue_appender.py`（写侧新增行同步补 `[S:open]`，否则会被新 CI 门禁拦下）六处已切换；`工具-文档台账生成.py`（只做文档状态头/列数自检，与状态语义无关）与 `draft_gap_detection.py`（只读 README 两态语义，不碰 §一）核实后确认无需改动；Cowork artifact `zhuopin-project-status`（JS）按 design 决策接受并登记为不可消除的第二实现，未改。**全量回归零漂移**：编辑锁 124、sweep 138（新增 D1/D2/§一切换共 18 个用例）、队列查询 14、队列结构lint 7（含真实生产文件回归）、wecom-aibot-service 357+1skip。`openspec validate --all --strict` 73/73 通过。**如实登记（档1 mock 验证，未晋档2）**：真实生产场景下的端到端观察（真实触发一次 WIP 超限提示/真实一次跟进信串行拦截或豁免/真实一类告警完整出现→解除周期）需等待自然发生，本次未人为构造；#306「路径解析收拢」剩余范围未做，留其自身独立后续。协议〇.9/〇.10 正文与 README-跟进机制与命名约定.md 已补说明确认落地。**openspec 变更包暂不 archive**（tasks.md 部分验证项如实未勾，不假装完工）。详见队列 #308、`openspec/changes/queue-status-machine-field/`。

> **队列 #308——propose＋design 已产出：状态机器字段消灭『正则猜中文』整族判据，openspec 变更包 `queue-status-machine-field`（2026-08-09，CC，独立 worktree `queue-status-machine-field`，commit 待补，§二批次 `B-0809_队列308propose设计产出`）**：队列 §一 状态语义长期靠自然语言承载（86:20 机制/业务比、19:9 未收口倒挂、4822 行守卫代码只增不减），#248/#302/#304/#306 及 2026-08-08 CLI 首跑第四误报源均为同一根因的衍生物。**措施 A（主体）**——§一 状态列开头新增定长机器字段 `[S:done/open/partial/hold/blocked/timed=YYYY-MM-DD]`（6 值，仅 §一，不动 §二/§四），字段之后自然语言正文一字不改，存量 106 行同批回填；**域字段**（决策点 2，`构建环境基建方案-2026-08-08.md` §4.5.1 原样并入 Decisions）`[D:机/业]` 并列声明，随 `acquire --reserve` 取号一并声明，供协议〇.9 措施 C 的可动 WIP 计数消费，替代关键词猜测。**措施 B**——`openspec/config.yaml` 新增守卫退休问询规则（新增机制类变更包须答『本次退休哪个既有守卫』），本变更自身已 dogfooding 作答：退休 #304、缩窄 #306 至读字段+路径解析收拢并省下其独立 design 审、不退休 #302 与④断言门槛（信源独立，机器字段不覆盖）。**措施 C**——编辑锁 release 时机制类可动 WIP 超上限（8）非阻断提示。**子项 D**——sweep 告警生命周期通用化：D1 抽取孤儿脏文件（#301）已验证的『出现→告警／消失→解除』骨架 retrofit 分叉/spec缺口/在途包滞留三类标准长期存在状态告警；D2 判断型告警（如『疑似遗忘归档』）新增指纹抑制（`--ack-stale-change`，指纹未变即静默、变了才重新告警，区别于会永久失明的静态白名单）。**子项 E**——E1（#129 类误报）随机器字段落地自动消解，不需代码；E2（scope 词表收窄）缺真实数据，列 Open Questions 暂不做。**子项 F**（2026-08-08 承载性核查拍板项 5）——编辑锁 release 新增 F1（§二 新增批次行状态列不得以 ✅ 开头，复现 `B-0728财务专线核实` 等真实事故）／F2（✅ 不在开头片段即报，复现 2026-08-03 六行头尾不一致事故）。**子项 G**（2026-08-08 同日追加）——跟进信串行原则挪入 `_validate_followup_readme_release` 咽喉：新增登记行时回查该收信人前一封是否已闭环（`📥 已回件并回灌`），非闭环即拒绝 release，除非行内写明 `串行豁免：`逃生阀；刻意不加 sweep 侧第 9 类告警（把人守动作挪进既有咽喉，不新增守卫，呼应措施 B）。design.md 含 10 个决策点，均给出推荐与默认项；`openspec validate queue-status-machine-field --strict` 与 `openspec validate --all --strict`（73/73）均已通过。**本次仅完成 propose＋design，未 apply**——已按派单指令要求停下等 Shao Peishen 审核（重点：决策点 2 域字段是否同批增设／决策点 1 状态取值集合／决策点 3 回填复核方式／决策点 4 七处消费者切换顺序与 JS 第二实现处理，均已给默认项，不答按默认执行）。详见队列 #308、`openspec/changes/queue-status-machine-field/`。

> **队列 #267——签字材料真实丢失事故根治：孤儿 worktree 扫描新增"gitignore 非空内容"第三桶（2026-08-09，CC，独立 worktree `worktree-evidence-guard`）**：真实事故——队列 #262/#263 两份审计报告落在某 worktree 本地 `reports/`（`.gitignore` 覆盖），该 worktree 因 `git rev-list --count origin/master..<branch>` 为 0 且 `git status --porcelain`（不带 `--ignored`）不识别 gitignore 命中内容而被误判"安全可删"，`git worktree remove` 后两份文件真实清空（详见 #227「仓库外活载体」新变种）。Shao Peishen 2026-08-07 三选一裁决 **(a)——只改工具、不加协议人守条目**（其原话：「协议再加一句人守正是退休制要淘汰的东西」），并附加强制条款：**"它只覆盖『经工具走』的路径，直接手敲 `git worktree remove` 仍无拦截"这一边界须原样出现在脚本 docstring／新桶报告输出文案／本行完工回写三处，缺一不算完工**（本次真实事故正是手敲触发，如实登记不假装闭合）。**实现**：`0-学习与工具/工具-孤儿worktree扫描.py::_ignored_content_paths` 新增 `git status --porcelain=v1 --ignored=matching` 取候选 + 逐路径文件系统复核（`_has_any_file`）过滤"目录存在但内容为空"的假阳性——**开发中实测坐实**一个未预料到的 git 行为：对显式匹配 ignore 规则的目录（如本仓库 `.gitignore` 的 `**/reports/`），即便目录内容为空，`--ignored=matching` 仍会原样报告该目录一行，必须再查一次磁盘才能兑现"非空内容"这个判据；`scan()` 新增第三个桶 `ignored_content_worktrees`（ahead=0 ＋ tracked 干净 ＋ 存在非空 gitignore 内容），`format_report` 标注「删除将永久销毁以下不在 git 里的文件」并逐路径列出。**未做任何删除；未加任何新规则；未触发 openspec**（CLAUDE.md §5 机制类三条门槛均不命中）。新增 2 个单测（真实事故复现场景 + 空目录假阳性排除场景），全量回归 **7 passed 零漂移**。**真实 dry-run 验证**（对当前共享主工作区实际运行，只读未删）：命中 **6 个真实 worktree** 存在未入库的 gitignore 内容（多为 `__pycache__`／`.pytest_cache`／`.claude/settings.local.json`，其中 `fi2-tax-export-excel-d3938b` 一处为真实数据目录 `data/real_tax_export_samples/`）——修复前均会被误判入①桶"安全可删"，坐实本行命题非孤例。**⚠️ 收工自删本任务专用 worktree 时如实复现了本行要根治的失败模式本身**：`git worktree remove` 报 `Permission denied`（该 worktree 正是当时会话活动 cwd），git 侧已成功注销注册，物理目录内容随之清空，只剩外层空壳删不掉——与本行原始事故触发方式完全同构；因自删前已核对 `ahead=0` 且 `git status` 干净（改动已推送），故无实质损失，仅登记为该缺口"仍会发生、只是这次未造成伤害"的又一实证，物理空壳留待后续会话/Paul 手动清理。详见队列 #267、`0-学习与工具/{工具-孤儿worktree扫描.py,test_工具-孤儿worktree扫描.py}`。


## 2026-08-18（第五批迁移，2026-08-21）—— SC2 两条，承接载体补立后方迁

> **迁移依据**：OP-0821-B 判据 J1「无承接载体者不得迁」。本两条在 2026-08-21 上午的第四批迁移中**被判定不可迁**——其正文自陈「按 design 审 5(a) 仍未立队列 §一 行，故本段与上一段是本任务仅有的跨会话载体」，迁走即丢掉 9.2 archive 与 9.6-9.7 跟进信两项未闭合事项。**同日 Shao Peishen 指示「台账上等我的三项都做」后，已补立业务场景队列 §一 `#361` 作为承接载体，J1 至此通过，方执行迁移。**
>
> 🔑 **这两条是 J1 判据的第一个真实用例**：它没有阻止迁移，而是把「机械迁移会丢东西」变成了「先补一个载体再迁」——**这正是本判据被设计出来的目的**。

> **SC2 部署 `.51:8096` 并冒烟通过，A2 的尾巴收掉大半；🔴 但 design 审 ④(a) 定的端口 8095 被实测推翻（2026-08-18，CC，worktree `fervent-jennings-46d4da`，commit `c39e33d`，直接 push master）**：G 节派单件。发布收口四关全过，**SC2 是采购域第二个真上线的场景**。 ━━━ 🔴 **① 本次最该被记住的一条：端口普查漏了两个口，与 D15-R 同型** ━━━ design 审 ④(a) 定端口 8095，依据是「顺延现网 8091-8094」；**部署前一探测，8095 已被 `ZhuopinRecruitAgent`（uvicorn/FastAPI，`C:\apps\zhuopin-recruit-agent`，计划任务已注册且 Running）占着，8090 还被 `UnifiedPortalGateway` 占着**——两个都在原普查视野外。**这与 A2 那次 D15/D16 被推翻是同一个形状：结论建立在一次没做实的核查上，直到真去碰它才塌。** Shao Peishen 当日改判 **8096**（实测 8096-8099 全空）。📌 **顺带查清一件与豁免直接相关的事**：`.51:8090` 上**已经有门户网关在跑**，但①源码只在未合入 master 的分支 `claude/unified-portal-design-8a2ce3`（#162/#335 已挂账）②路由表仍是试点单条（`/` → 8092）⇒ **SC2 现在还收编不进去**，端口豁免仍然成立、且注销条件要等它先合入 master 并具备多路由能力。 ━━━ 🔴 **② 部署当天修掉三件，全都只在真部署才暴露** ━━━ **⑴ #300 引导在扁平布局下无条件 `raise`**（队列 #345 同族，F 节预警命中）——`.51` 是 `C:\sc2\{app,zhuopin_platform,.venv}` 扁平布局、没有 `5-平台底座/` 标记，原实现直接把服务入口钉死；已照 QD-B/SC8 改法修好，**两个方向都实测**（扁平布局真跑出周报／平台真缺失时仍 fail-loud，用 `python -S` 复现）。**⑵ 门禁把健康检查挡在外面**——`install_flask_gate` 缺省豁免是裸 `/api/ping`，而本场景路由全在 `/procurement/sc2` 之下 ⇒ **没有任何路径命中豁免**，部署脚本健康检查与此后一切存活探测都会 302 到登录页、**误判一个好服务是坏的**。**⑶ 页面「确认发布」按钮在过渡期是坏的**——按钮提交的是**表单**，而 `api_confirm` 只认 JSON body 与网关身份，过渡期无网关下发身份 ⇒ 必然 400。**而那是本场景 L3 唯一的人工动作、也是部署的全部意义**（姚祖怡打开页面就是为了点它）。已改为「JSON → 表单 → 网关身份」三级取确认人，页面加姓名输入框，**未填仍拒绝**（无主语的确认在 IATF 审核时等于没有确认）。三件各配单测。 ━━━ 🔴 **③ 两条口径修正，都是页面上那些数的正确性问题** ━━━ **⑴ 服务端缺省不截断行级状态取数**——实测窗口内料号 **830 个**而 `RealFeed` 缺省上限 200 ⇒ **630 个拿不到状态、按「状态未知」计入在途**，在途类指标偏高；截断确实会写进取数说明（No silent caps），**但那只是「诚实地报告一个次优数」**，而这些数正是要请姚祖怡判例批改的对象。改为服务入口缺省 0（不限），慢由 D21 兜（重算 102 秒，页面读快照 0 秒）。**⑵ 新增 O-7：周中生成时本周窗口不完整**——三窗口同为一个自然周才使量纲可比（D16-R），**但基准日落在周中时本周只过了 N/7 天，上周与上月同期都是完整 7 天** ⇒ 量类指标环比同比系统性巨幅偏低。部署当天是周二（2/7 天），**21 个指标里 16 个被打 🔴，那不是业务波动**。**任何阈值调整都修不掉它，因为它不是阈值问题**——O-1/O-4 判例批改也解决不了。已按「不可算不呈现」同一精神在周报顶部**显式声明**（完整周运行时不出现，不构成噪音）；**根治属 D16-R 的修改、须走追认，留判例包与 Shao Peishen 定。** ━━━ **④ 冒烟七项与常驻核验** ━━━ ping 200／匿名被门禁 302／登录后关键页 200／`POST /api/refresh` 真实全量重算 200（102 秒）／重算后页面走快照 0 秒／重算全程进程未重启／**从笔记本外部实测 ping 200**（不是只在 `.51` 本机，根 CLAUDE.md 坑 5）。**进程 CreationDate 逐次核对真实刷新**（4584 → 4464 → 6256），非只信脚本打印「已重启」（SC8 2026-07-14 教训）。**服务器五个文件 SHA256 与 master 逐字节一致**（#221/#228 同族核验）。计划任务 `Sc2WebServer`（SYSTEM+AtStartup+失败重启 3 次）Running；防火墙 `Sc2-WebServer-8096`；`deploy-server.ps1`／`sync-to-server.ps1`／`smoke-server.ps1` 三件均带 UTF-8 BOM。 ━━━ **⑤ 一件刻意没做** ━━━ **L3「确认发布」未在生产上实跑**：那会往 `audit` 写一条「某人已确认发布」的真实记录，**而实际没有人确认过——IATF 审计轨迹里不能有编造的签认**。该路径由两个单测覆盖，留给姚祖怡本人首次真实确认。 ━━━ **⑥ 回归** ━━━ SC2 120 passed（新增 7）／平台 295+1skip 零漂移；`openspec validate --all --strict` 84/84。**rebase 到 origin/master（当时落后 11 提交）后重跑一遍才 push**，非只在 rebase 前测过。 ━━━ **⑦ 未完成，如实登记** ━━━ **9.2 `archive` 仍不做**——9.5 已解除但 9.6/9.7 未完，tasks 未全 [x]，**不假装完工**。**9.6/9.7 不由本 session 执行**：派单件明令「不要自行起草跟进信」，SC2 判例包（O-1/O-2/O-3/O-4，基线数 ＝ 4）归 Cowork 起草。🔴 **串行闸阻塞源已变，值得记**：原阻塞的 采购部#14/#15 已于 2026-08-18 闭环（📥 已回件并回灌），**但同日 采购部#16（齐料日期判例批改）已占用在途名额、状态 `⏳ 待你审`** ⇒ SC2 判例包须等 #16 闭环后作为 **采购部#17** 起草。**发送三条硬前置本次已全部满足**（① 已 ff 入 master ② 已部署且冒烟通过 ③ 真实案例端到端复现），**剩下的唯一门是串行闸。** **按 design 审 5(a) 仍未立队列 §一 行**，故本段与上一段是本任务仅有的跨会话载体。⚠️ **一处流程偏离，如实登记**：派单件要求新建 worktree `sc2-deploy-and-archive`，本 session 用的是自身已在的 worktree `fervent-jennings-46d4da`（当时正处 master HEAD、工作区干净、分支 `claude/sc2-weekly-report-mvp-8da6b2` 专用）——隔离与新基线两个目的均已满足，未另建以免再多一个孤儿 worktree。详见 `openspec/changes/sc2-weekly-report-mvp/tasks.md`、场景 `4-数字员工/采购部/SC2-采购周报自动生成/CLAUDE.md`「部署状态」段。>

> **SC2 采购周报自动生成——grill→propose→design 审→apply 一日走完，档 2 达成；🔴 但 design 的 D15/D16 被真实接口推翻并重定为 D15-R/D16-R（2026-08-18，CC，独立 worktree `sc2-weekly-report-build-a357dd`，commit `06fc715`+`0d347dc`，直接 push master）**：A2 派单件（opener 集业务开工批 A2 节）。需求一字未重想——A1 grill 产出件 §二 14 项 settled 原样进 `design.md` Decisions、§三 5 项原样进 Open Questions，兑现了 grill 机制接缝 2「消除一次重复劳动」的设计目的。**N3 的 SC2 半边（8/31 前出 propose）比截止早 13 天达成。** ━━━ 🔴 **① 本次最该被记住的一条：读封装 ≠ 读端点** ━━━ propose 阶段的 D15（收货侧走 SRM）与 D16（W-4 同期周）双双建立在两个未经真实接口验证的判断上，apply 一接就塌：**⑴ SRM 供应计划看板返回 `300234: 不允许查询当前时间 7 天之前的数据`**——它只能查未来区间，周报要的「上周」「四周前」两个历史窗口**结构性取不到**，SRM 在本场景路径上完全不可用（⚠️ 该限制其实早有记载，见 memory `project_sc8_real_cutover`「SC1任务9.1=SRM看板无法供历史准时率(300234,≤7天前禁)」——**是我 grill/propose 阶段没查到那条**）；**⑵ `GR/Query` 其实支持无过滤分页整表拉取**（27,785 行，服务端硬顶 500/页 ⇒ 56 次请求），每行自带 `BusinessDate`（真实入库过账日）＋`SrcDocNo/SrcDocLineNo`——**原判断错在把底座封装 `get_gr_lines(doc_no)` 的形状当成了端点本身的能力**；**⑶ `ZpViewPurOrder` 原始行有 `makeDate`／`finallyPriceTC`／`makeEmpName`**，金额与采购员维度本来就可算，是我误判为不可算。**⇒ D15-R：数据源边界由「ERP+SRM 双源」收敛为「ERP 单源双端点」，口径反而更硬（ERP 已入库过账 > 供应商 SRM 自报答交），且原 D15 那条必须一路带到周报上的口径警告随之消失。D16 结论不变但理由作废**（SRM 60 天上限已不适用，W-4 现完全建立在「三窗口同为一个自然周、量纲可直接比较」上）。 ━━━ 🔴 **② 新发现 O-6，首版最大能力缺口** ━━━ **`ZpViewPurOrder` 完全没有交期字段**——`deliveryDate`/`DeliveryDate`/`expectDate`/`planDate`/`demandDate`/`arrivalDate` 六个候选名在 28,274 行中**全部 0 命中** ⇒ 底座的 `expected_date` 与 `supplier_confirmed_date` 实际恒等于制单日 ⇒ **收货准时率无基准可比，已按 spec「不可算不呈现」撤下**（以制单日充当承诺交期算出的准时率恒为「几乎全部逾期」，**那是个看起来像指标的假数**）。**连带须记住**：「交付及时率」原本正是 grill D1 要引入 SRM 的主要理由，D1 被取代后 SRM 在本场景只剩「承诺交期来源」一项且未验证——**下一轮若验证失败，SC2 将长期没有任何准时率类指标**，应在判例包里让姚祖怡知情，而非等他自己发现。O-5 同批已结（三端点字段全查无工时字段）。 ━━━ **③ 底座改动：纯新增、零行为变更**（design 审 ③(a) 默认项明示允许） ━━━ `models.ReceiptLine`（新）＋`ZpConnector.get_receipt_lines(days)`（`GR/Query` 整表分页＋客户端过滤＋4h 磁盘缓存）＋`PurchaseOrder` 补 4 个**带缺省值**字段（`make_date`/`unit_price`/`supplier_name`/`buyer`）。⚠️ **实测坑**：`get_purchase_orders` 有 4h 磁盘缓存，**旧缓存不含新字段**，反序列化后取缺省值（金额显示 0、采购员 0 人）——改字段后须清 `erp_connector/cache/po_cache.json` 再验；这同时也证明了旧缓存向后兼容。 ━━━ **④ F14 两次命中，第二个端点更彻底** ━━━ `ZpViewPurOrder/Query` 与 `GR/Query` 参数名拼错**均静默返回全表**；`GR/Query` 对 `startDate`/`endDate`/`businessDate`/`beginDate` 四种写法返回的 `Total` 与无过滤基线**完全相同**（27,785），与故意拼错的参数名也相同 ⇒ **两侧一律整表取回后客户端按业务字段过滤，不信任任何服务端过滤**。探测同时撞出一条 IATF 红线 warning（连接器未注入 audit），已注入 `ConnectorAudit` 封住。 ━━━ **⑤ 真实数据实证（档 2）** ━━━ base 2026-08-18、812 料号全覆盖、2m19s：下单 76 行/183,071/¥627,992.20/32 单/71 料号/6 采购员；收货 40 行/137,236/¥493,213.58/14 单，可溯源比例 77.5%；在途 73 行未清/¥627,903.70/**已关闭 3 行**（D17 在全状态覆盖下生效，纯数量启发式会把短缺关闭行永久误判为在途）；供应商 21 家、首位集中度 54.0%。**D21**：页面改快照优先＋`POST /api/refresh` 显式重算（2m19s 不能挂 HTTP 请求上）。 ━━━ **⑥ 跨子项目回归零漂移** ━━━ 平台 295+1skip／SC8 402+4skip／SC1 53／SC7 41／O2 20／FI1 33／FI2 158+9skip／QD-A 41／QD-B 114+27skip／`wecom-aibot-service` 398+1skip／`0-学习与工具` 357+26subtests（该套整体跑超 10 分钟，拆两次取真实退出码）／SC2 113。`openspec validate --all --strict` 83/83。⚠️ **一条方法教训**：其中两次先拿到的是 `| tail` 之后的退出码——**那是 tail 的 0 不是 pytest 的**；改写文件再取 `$?` 才看到真值 `124`（超时），**差点把没跑完的测试当绿灯报出去**（同 memory `feedback_pipe_masks_exit_code`）。 ━━━ **⑦ Shao Peishen 2026-08-18 收口拍板 1a/2a/3b** ━━━ **1a 追认 D15-R**（改动的是 grill 已 settled 的 D1，属实质性改动，按 IATF 须留追认痕迹，已落 design「二之负一」）／**2a** O-6 作已知缺口、首版即发、不阻塞交付／**3b 暂不部署 `.51`**（主动推迟，非遗漏；`.51` 已探活可达、现网三服务均 302，部署条件具备）。 ━━━ **⑧ 未完成，如实登记** ━━━ 9.5 部署（3b 推迟）／9.2 `archive`（被 9.5 阻塞，tasks 未全 [x]，**不假装完工**）／9.6-9.7 跟进信（**串行闸硬阻塞**：姚祖怡采购部#14 于 2026-08-13 已推送未回件）。**按 design 审 5(a) 未立队列 §一 行**（WIP 仍超限），故本段是本任务唯一的跨会话载体。详见 `openspec/changes/sc2-weekly-report-mvp/`、场景 `4-数字员工/采购部/SC2-采购周报自动生成/CLAUDE.md`。

## 2026-08-19（第六批迁移，2026-08-22，OP-0822-D）—— J3 长度收口，两条压缩前原文全文存档

> 🔴 **本节是「压缩前原文」存档，不是迁出**：以下各条**仍留在活文件里**（根 CLAUDE.md 那两条是「只留最近一批」规定的当期两条；SC8 那条是 `**当前**` 行），只是活文件里的版本被压到 J3 上限 1,200 字符以内、只留结论与指针。**下面这份是一字未改的原文。**

### OP-0819-F 收口（压缩前原文）

```text
> **OP-0819-F 收口——FI2 断供告警 `.51` 部署补配 ＋ 首次真实企微调用冒烟通过 ＋ §四 #73 重评（2026-08-19，CC，共享主工作区 master，§二 `B-0819_21`）**：OP-0819-E 第二三步的续做，第一步（运维群 URL 验通）已由 Cowork 当日完成、未重跑。 ━━━ 🔴 **① 本次最该被记住的一条：一个「告警机制」建成 9 天、每天在跑，却从来没有真正发出过一条消息** ━━━ `#82` 的两类告警（文件级摄取失败 ／ 源头断供）**2026-08-10 建成、08-17 补齐第二类、08-19 修好键名**，但行内自陈「**至今未做任何真实企微 webhook 调用**」一直挂着——**中间任何一轮都没人察觉这个机制其实一次都没响过**。本轮在 `.51` 上构造真实断供条件跑生产脚本，**一条完整告警真的进了运维群**（`wecom.send_text` 对非零 errcode 抛异常 ⇒ 打印「已发送」等价于企微 `errcode=0`）。**这比 §四 #67 的 44004 残缺 payload 探针强一档**：那只证明 key 有效，这证明**消息真的到了人眼前**。⇒ **「探针通了」不等于「机制通了」，两者之间还隔着部署、配置、代码键名三层，本轮把三层一次走完。** ⚠️ fixture 目录名刻意取 `_SMOKE_TEST_…`——告警正文首行「目录：…」原样带出，运维群一眼可辨是冒烟、不是真断供。 ━━━ 🔴 **② 一处方法教训：第一次读到的退出码是假的，而它长得跟成功一模一样** ━━━ 冒烟首跑用 `cmd /c 「… & echo EXITCODE=%ERRORLEVEL%」` 读到 `EXITCODE=0`，真值应是 2——**`%ERRORLEVEL%` 在 cmd 解析期就被展开**，读到的是命令还没跑时的值。改用独立 `.ps1` 读 `$LASTEXITCODE` 才拿到 **2**。**与 memory `feedback_pipe_masks_exit_code` 同族第二形态**：那条是管道把退出码换成了 `tail` 的，这条是 cmd **把退出码在时间上取早了**——**两者都表现为「拿到一个看起来很正常的 0」**。⇒ **退出码只认被执行进程自己那一层；经 shell 转手的写法，先证明它转对了再采信。** 该次复核把 `_OPS` 置为哨兵值，**未向任何群发第二条消息**。 ━━━ 🔴 **③ 一条「更正」把一条本来正确的记录改错了** ━━━ OP-0819-E 曾「更正」OP-0819-C，称 `.51` 的 `.env` 内并无 `U9C_` 前缀键；**本轮实测那 9 行里含 6 个 `U9C_*` 键 ⇒ 原始记录是对的、那条「更正」才是错的。** 🔑 **值得记的不是这六个键，而是：更正本身也会错，且比原始错误更难被发现——因为它自带「我已经复核过」的语气。** ⇒ 推翻一条既有实测记录前，须与原记录**同口径**复测一次。 ━━━ **④ 部署与验活（四关全过）** ━━━ 服务器件 SHA256 与 master **逐字节一致**；`.51` 的 `.env` 由 9 行 305 字节 → 10 行 418 字节，新增 `WECOM_WEBHOOK_URL_OPS`（**值全程未回显**，走「临时文件 → scp → 字节级追加 → 删临时文件」，落文件的只有 SHA256 前 8 位 `4bf10217`；改前已备份）；`.51` 上 `WECOM*` 键只有 `_OPS` 一个、机器级与用户级环境变量均空 ⇒ **无错发风险**；`Fi2WebServer` 进程 `CreationDate` 真刷新（08-18 19:20:29 → 08-19 18:11:48，不只信脚本打印）；`Fi2TaxExportDailyScan` 以「新码 ＋ 已配 `_OPS`」组合手工触发 `LastTaskResult=0`；**笔记本外部** `/api/ping` 200、匿名 `/` 302 → `/_gate/login`（不是只在 `.51` 本机测，根 CLAUDE.md 坑 5），服务器侧带 `X-Auth-Token` 首页 200。⇒ **§四 #72 销号、§一 #82 销号**（其建造与部署范围至此全部完成）。 ━━━ **⑤ §四 #73 重评：三问全部翻面，但按指令只出结论、sweep 一行代码未改** ━━━ ⑴ (b) 的技术障碍**确已消除**；🔴 **连带死掉的还有上一轮那条「连你也不再收到」的顾虑**——那句话成立的前提正是 `_OPS` 无效，通了之后 (b) 的真实含义是「这些告警从采购内部工作群**搬到**运维群」，而运维群本就是他与陈承的群。⑵ 最小改动面已独立复核：`0-学习与工具/工具-落库sweep.py` **L437 一个常量**，10 处调用点全经 `_load_webhook_url()`、一处不用碰；**并查实一条上一轮没查的边界**——全库读裸键的还有 `发企微.py`（**业务内容通道，改它是反向错误**）与 aibot-service 五入口（读 `5-平台底座/.env` 裸键，**该键值长为 0**、mtime 停在建服务当天，属另一件事）。⑶ `#282` 前提① 至此**首次真正满足**。**⑷ 首次量化了「正在发生」的底数**：`sweep-commit.log` 全量统计，**采购内部工作群累计已收到 58 条机制告警（口径＝日志内以 ✓ 开头且含「已推送」的行。⚠️ 初次用一条只匹配「告警已推送」与「通知已推送」两种措辞的 grep 只数到 57，**漏掉了「常驻服务部署提示已推送」这一类** —— 同一份日志两种数法差一条，已取宽口径）**，今日两条——其中 `07:37Z` 那条**正文是一段 Python traceback**（`CalledProcessError: git add … exit 128`）。**一段 git 报错的调用栈落在业务同事的工作群里**，就是 `#282` 要消灭的那件事的具体形态。处置三选一交回定夺，**推荐 (c) 并进 `#282` ⑴ 包先做掉**（合协议〇.10 并入优先，又不必等 hold 解除）；**按「默认项两前提」明确不设默认项**（代价是「每天继续发生」而非「停在原地」）。 ━━━ 🐛 **⑥ 顺带修两处既有数据损坏，并在自己身上拦下第三处** ━━━ 两份队列文件里 `D:\airead` 的 `\a` 各有一处被写成真实 BEL 控制字符（0x07），系历史某次经 heredoc 写入时反斜杠被吞（memory `feedback_bash_heredoc_backslash_mangling`）；**本 session 起草时险些复现同一 bug（`\f` → 0x0C、`\a` → 0x07 已真的写进文件），落盘后立即扫控制字符查出并 `git checkout` 回滚重做**——🔑 **该 memory 记的是「heredoc 吃反斜杠」，但真正咬人的是下游：Python 把幸存的单反斜杠当转义序列，`\f`／`\a` 恰好都是合法转义、不报错、静默变成控制字符。** ⇒ 写含 Windows 路径的中文正文，一律用 r-string ＋ 落盘后扫一次控制字符。
```

### OP-0819-A 收口（压缩前原文）

```text
> **OP-0819-A 收口——`#312` 可 Open 池提醒两个缺口一次修掉 ＋ WIP 上限 16→24 ＋ 补立 #351-#354（2026-08-19，CC，worktree `wip-limit-open-pool-fix-c9d2ca`，commit `f339cbc`＋`aded2bc`，直接 push master）**：零时巡检批派单件。 ━━━ 🔴 **① 本次最该被记住的一条：「一份拆成两份，下游只跟了一份」，而这次的下游正是那个本该提醒他的机制** ━━━ `#312` 的可 Open 池提醒**建好了、在跑、今早 07:36 还写过状态文件**，但它读的是 `repo_paths.DEFAULT_QUEUE_RELATIVE_PATH` 这个**单文件常量**——而 `#315`（2026-08-11）拆分后**采购／财务／质量三域的构建任务全住在 `跨桌任务队列-业务场景.md` 里**。实测生产状态 `known_open_ids` ＝ `["240","337","338","341","98"]` **五个全是机制环境行**；采购 `#334` 的两个排队前置 2026-08-18 已全部完成、`#266` 还经姚祖怡本人抽查验收通过，**却没有任何机制会去重算它**——他今天是靠自己问一句才发现的。**⇒ 与 `#345`（35 份手抄副本漂成 4 种语义）、README「下一个可用号」段（改了下表没改上段）同族：副本增加时，没有任何机制保证所有消费者都跟上。** 修法＝新增 `build_pool_items_from_repo()` 走 `queue_table.iter_queue_paths()` **逐份解析后合并**；🔴 **绝不拼接文本再解析一次**——`_parse_table_rows` 用 `find` 只取第一个 `## 一、`，**拼接会静默丢掉第二份的 §一，症状与本缺口一模一样且更难发现**，已配反例单测把这个陷阱锁死。`DEFAULT_QUEUE_RELATIVE_PATH` **一字未动**（写侧按域路由属 `#341` 范围，派单件明写不并入、也不假设它会顺带解决）。 ━━━ 🔴 **② 缺口二：他要的是「催我」，而机制只会「通知我有新的」** ━━━ 原指纹＝可 Open 行号集合，**集合不新增即静默** ⇒ 对「一直有活、没人开」结构性沉默。新增**陈化催办**（末次触碰 > 7 天且距上次催办满 7 天即推，Shao Peishen 2026-08-19 答定夺 1(a)、N＝7），与「新增即推」**分别计指纹、独立成一条消息、audit action 名单独区分**。**「该行动没动」用 git 不用 mtime**（队列文件几乎每天被写，mtime 判它恒为假）；**也不用 `-L`／`git blame`**（那两者追「当前第 n 行」，而队列行的物理行号随上方增删漂移，**会静默给出另一行的历史**）。取不到时间 ⇒ **保守视为「刚触碰、不催」且不静默**（反之会让每条新行下一轮立刻被催，等于退化成已被否决的「池非空就推」）。 ━━━ 🔴 **③ 派单件的一处算术被实测推翻，上限由 20 改定 24** ━━━ 派单件按「真在办 15 ＋ 排队 4 ＝ 19，留 1 格」定 20，**其前提是 A 类四行（#68／#234／#270／#279）已销号**；而定夺 3 答 (a) 把销号交给了下周值周巡检、**尚未执行 ⇒ 当天实测 19 里仍含这 4 行**，四条新行全立进来是 **19+4=23**，按 20 会被 `release` 硬阻断。Shao Peishen 当日据此改定 **24**。**⇒ 不是又抬了一次杠，是原推荐值建立在一个尚未发生的前提上。** 🔑 **值周巡检须盯住**：A 类四行销号后本值应回落一档（20 即够）；**若销号做完而上限没跟着降，那就成了一个靠「忘了收回」维持的上限**。四处载体同批改完（编辑锁常量／`专线opener模板库` §⑵／`zhuopin-kickoff-prompt` SKILL **v1.10，已安装版待 Cowork `save_skill --overwrite` 同步**／`editlock-mechanism-wip-guard` spec）。 ━━━ **④ 补立四条 #351-#354，编号非派单件写的 #349** ━━━ #349／#350 在本 session 开工后被**企微机器人自动追行占用**（姚祖怡两条文本反馈），故从 #351 起。**#351 已按当日两次升级扩为 `append-row` 咽喉三修**（锁归属校验 ＋ 裸竖线诊断被 arity 遮蔽 ＋ §二 文件清单路径格式校验），⑵-b（`--row-md`）明标须 design 审、不得直接实现。**立完实测 23／24。** ⚠️ **起草 #351 时被两道守卫当场拦下，两次都是有效拦截**：正文里写了一个裸竖线举例被校验①拒绝；P1 行缺证伪命令被 release 拒绝——**后者补的那条命令跑出 `True`，当场坐实了 #351 自己的根因断言**。 ━━━ **⑤ 档 2 验收：真实推送已完成** ━━━ 对生产队列真身跑通，**`#334`／`#344` 首次进池**（池 7→9 条），2026-08-19 01:44:23Z（09:44:23 本地）真实推送到企微，audit 记 `open_pool_reminder_sent`。 ━━━ 🔴 **⑥ 未闭合两项，如实登记，不假装完工** ━━━ **⑴ 陈化催办今天推不出真实消息**——当日池中最久的 `#240` 只滞留 6 天，**9 条全部 < 7 天阈值 ⇒ 候选为空**（Shao Peishen 当日答「接受，真推『新增』那条即可」）；`#240` 明天即跨 7 天，**最快 2026-08-20 08:30 定时任务才是本判据的真实首验**。**⑵ `archive` 不做**（tasks 未全 [x]）。 ━━━ 🔴 **⑦ 收工时撞出一个更大的、不属本次范围的发现：生产载体落后 master 246 个提交** ━━━ `ZhuopinDecisionReminderDaily` 的实际执行体是 worktree `.claude/worktrees/wecom-service-home`，实测 **`git rev-list --count HEAD..origin/master` ＝ 246**。**⇒ 本次修复虽已 ff 入 master，但明天 08:30 那次仍会跑 10 天前的旧码**——实证就在眼前：我 09:30 立完四行后，**09:36:41 有一次旧码运行改写了状态文件**，写出的 `known_open_ids` 里只有机制环境行。**这不只影响本次**：这 246 个提交里所有落在 `wecom-aibot-service` 的修复同样都没生效。**本 session 未擅自 ff-merge 并重启该常驻服务**——上次同类操作只跨 27 个提交就撞出孤儿子进程、需手工补杀并验心跳，而 246 个提交且要连带部署他人 10 天的改动，**超出本派单件范围，列为定夺项。**
```


---

## 【附录 · Last Updated 链历史 —— 2026-08-22 迁入批（OP0822A）】

> 本节自根 `CLAUDE.md` 的 `**Last Updated**` 行迁入，**原文原样、一字未改写**。
> **迁出理由**：该行已长到 **8,674 B、占根文件 10%**，而它按定义只该是一个日期。**根文件此后该行只写日期与一行指针**（规则已同批写进该行本身）。
> **J1 承接载体**：本节即其承接载体；根文件那一行留有指向本节的指针，双向可达。
> ⚠️ **含两段此前以 HTML 注释形态保留的 2026-08-19 原文** —— 它们自己写明「保留一轮，下次写入时按『只留最近 1 条』删除」，本次一并迁入，注释标记原样保留。

**Last Updated**: 2026-08-22（Cowork，主工作区 master：**OP-0821-M 收口 —— 质量域同日两连改：v7 五场景全部下架（40 → 35，重组循环第 8 例·结构级）＋ v8 Q2 性质改变与 Q4 收敛（第 9 例·轻量，总数不变）**）。 ━━━ 🔴 **v8（2026-08-22，Shao Peishen 答「88-B、88-C 通过」）**：**Q2 由「8D 报告智能起草」改为「8D 报告 AI 自动判定」——这是场景性质改变，不是描述修订**：受益人由「**写** 8D 的人」换成「**审** 8D 的人」，AI 做什么整段换成七维评审（D2 5W2H／D4 5Why 深度／D5-D6 措施-根因匹配度／措施可验证性／章节与附件完整性／百分制评分与 A-D 分级／历史案例入库），价值指标由「输出 2 天→4 小时」换成「单份评审 2-4 小时→10-20 分钟 ＋ 根因不合格检出率 ≥90%」。**Q4 由 18 项文件包收敛为三文件（控制计划／PFMEA／过程流程图）一致性校验**，基准由「3-5 天/套」改「16 小时/套」。 🔑 **两条最值得记的**：**⑴ 一处净减少必须显式记下——「帮工程师起草 8D」这件事，改写后没有任何场景在做了**（旧版该能力至今零代码、无沉没成本，但它是被删掉、不是被搬到别处，不能以「Q2 保留」的名义悄悄消失）；**⑵ Q4 删掉的「对照各 OEM 要求清单」与「OEM 要求知识库」两条能力，连带把 `OEM 客户 PPAP 要求手册` 这项数据依赖也删了** ⇒ **v6 给 OEM 隔离层 Chroma 找的两个挂靠点被业务方拆掉一个**；**这不等于 Chroma 可停**（QD-B 那条 IATF 红线仍在、新 Q2 要批量处理含 OEM 信息的 8D 反而可能成为新挂靠点），**但必须显式重判一次**——已立 §一 `#374`，**重判出结论前 2027-01 硬截止不得放宽**。 **连带**：QD-A 由「Q2 的实现」降格为「**Q2 的前置抽取层**」（沉没成本 0、复用率反高于原设计，七维里三项基本现成），其场景 `CLAUDE.md` 定位段同批改并顺手修「输入 docx/pdf」这处与同文件时间线段自相矛盾的陈旧描述；新增非技术资产《8D 报告 AI 判定规则库》入前置总表。 ⚠️ **两处未闭合**：Q2「自动化等级」那行她原样留着旧版「AI **起草**」措辞、判为残留，**等级 L2 不动、括号描述已按判定语义改写，待 `质量部#9`（`⏳ 待你审`）回件确认**；Chroma 归属重判见上。 ⚠️ **一处我方加的合规把关**：新 Q2 的「C 级以下强制退回」是对供应商/内部团队的流程强制动作，按 §7 第 4 条**须走 L2 人工确认**——AI 只出评级与退回建议，退回决定由质量工程师签发。 ━━━ **v7（同日）**：**这是本项目第一次真正减少场景总数**——此前 38→40→42→40 全部由新增／拆分／并入所致，**v7 是真删除**。源＝质量部 2026-08-21 部门内部评审判 `Q1 客诉分流`／`Q3 FMEA`／`Q5 IATF`／`Q7 IQC`／`Q8 SPC` 五场景「我司当前阶段不适用」，Shao Peishen 拍板「全部下架处理，可以保留历史版本记录，不需要放入全景规划，除非我以后手动复苏」。**质量 8→3（Q2／Q4／Q6，Q6 已交付）⇒ 实际在建只剩 Q2／Q4**；历史只靠 git（不并入 backlog、不建暂缓清单、不设复活条件），**五个编号就此空置不得重新分配**。 ━━━ 🔴 **四处连带（本次最容易被漏掉、也最值得记的部分）**：**⑴ v6 那次「Q5 由 2027-01 三度提前至 2026-12」整条失效**——一个刚提前 3 天的场景直接被下架，**提前决策的成本沉在了前置排期上**（前置总表曾把 Q5 前置压到 2026-10 下旬并注明「须有人在 10 月认领」，该认领需求随之消失）；**⑵ S1 目标场景数 11-13 → 9-11**（算术：S1 期内原 14 个含 Q1 与 Q5，下架后只剩 12 个，13 已超总数；沿用 v6「留 1 个缓冲」取法）；**⑶ 链 C 质量闭环链由 3 节点降为 2 节点、联动点 12 → 11** —— **Q1 是链 C 的入口节点，下架后链 C 失去入口**，8D 来源退回人工受理；`L6 Q7 IQC→SC1` 整条撤销 ⇒ **SC1 供应商风险评分暂无来料质量输入**；`L7` 来源由「Q1/Q2」收窄为「Q2」单侧；**⑷ MES/QMS 内网接口治理失去承载行** —— Q7／Q8 此前是它在前置总表与质量域路线图内的**唯一业务理由**，日后若仍需推进须另立载体。 ━━━ ⚠️ **明确不在本次范围（写出来免得下一个读者误以为已处置）**：**Q2／Q4 的内容改写**（陈忱同批把 Q2 由「8D 智能起草」重写为「8D 报告 AI 自动判定」＝性质改变、把 Q4 由 18 项文件包收敛为三文件校验，并写「请参考是否可行」）走 `质量部#9`（`⏳ 待你审`）与 §四 #88 的 88-B／88-C，**两个场景块一字未动**，仅在 Q2 块后加一句「自动化等级待 `质量部#9` 回件确认」（她那份仍写 L2「AI 起草」，与新场景不符、疑为旧版残留）；**OEM 隔离层 Chroma 归属须随 Q4 收敛重判一次**（v6 把它改挂「Q4 PPAP 前置 ＋ QD-B 现行红线」，而收敛后的 Q4 不再需要按 OEM 分库检索要求手册 ⇒ **两个挂靠点被业务方拆掉一个**；**这不等于 Chroma 可停**，QD-B 那条 IATF 红线仍在、新 Q2 要批量处理含 OEM 信息的 8D 可能成为新挂靠点），**重判出结论前 2027-01 硬截止不得放宽**。 ━━━ **触碰九文档**：全景规划（§0.2 登记＋§2.1.3 五块删除＋已下架登记表＋目标表三行撤下＋排期表 4 行＋§1.4／§5 目标数＋链 C／联动点＋SC1 联动行）、实施计划、前置数据总表、甘特 HTML、四链蓝图、质量域路线图、根 CLAUDE.md、机制变更日志、session 接力件，**两份 docx 同批重转**。 ｜ **更早**：2026-08-19（CC，OP-0819-F：FI2 断供告警 `.51` 部署补配 ＋ 首次真实企微调用冒烟通过 ＋ §四 #73 重评；OP-0819-A：`#312` 可 Open 池提醒两缺口修复 ＋ WIP 上限 16→24）——**两条原文见上方「当前进度」段**，按本行「只留最近 1 条」规则此处不复述 ｜ **更早**：本行历史条目（2026-07-31～2026-08-09 共 30 条）已于 2026-08-16 迁入 `1-转型规划/0-全景路线图/进度编年-CHANGELOG.md` §「附录 · Last Updated 链历史」。

<!-- 以下为 2026-08-19 原 Last Updated 行原文，随 OP-0821-M 保留一轮，下次写入时按「只留最近 1 条」规则删除（其完整内容已在顶部「当前进度」段） -->
<!-- **Last Updated**: 2026-08-19（CC，共享主工作区 master：**OP-0819-F 收口**（§二 `B-0819_21`）——FI2 断供告警代码部署 `.51` ＋ `.env` 补配 `WECOM_WEBHOOK_URL_OPS`（值全程未回显，只落指纹 `4bf10217`）＋ **真冒烟通过：一条完整告警真的进了运维群**（企微 `errcode=0`），**补上 `#82` 建成 9 天却从未真实调用过企微这个缺口**；`Fi2TaxExportDailyScan` 新码组合下 `LastTaskResult=0`、进程 `CreationDate` 真刷新、笔记本外部 ping 200 ／ 匿名 302。**§四 #72 销号、§一 #82 销号**。**§四 #73 重评三问全部翻面**（(b) 障碍已消除、「连你也不再收到」的顾虑随之作废、最小改动面 ＝ sweep L437 一个常量、首次量化出「已发 58 条、今日 2 条含一段 traceback」），**按指令只出结论、sweep 一行代码未改**，三选一交回定夺且**不设默认项**。🔴 **三条方法教训**：`%ERRORLEVEL%` 在 cmd 解析期展开 ⇒ 第一次读到的退出码是假的（同 `feedback_pipe_masks_exit_code` 第二形态）；一条「更正」把 OP-0819-C 一条正确记录改错了 ⇒ 更正也需同口径复测；两份队列文件各有一处 `D:\airead` 被写成 BEL 控制字符已修，本 session 险些复现同一 bug、落盘后扫控制字符当场查出并回滚重做。**同日更早的 OP-0819-A 收口条目**按本行「只留最近 1 条」规则不再复述，原文见上方「当前进度」段）｜ **更早**：本行历史条目（2026-07-31～2026-08-09 共 30 条）已于 2026-08-16 按 R5／memory 审核报告 P2 原文原样迁入 `1-转型规划/0-全景路线图/进度编年-CHANGELOG.md` §「附录 · Last Updated 链历史」；本行此后只留最近 1 条，更早查该附录与顶部"当前进度"段｜ 维护：本文件随架构/红线变更更新，时间线细节以实施计划第七节为准。 -->


## 【附录 E · §5 规则论证迁入批 —— 2026-08-23（OP-0823-B，第三刀）】

> **迁入依据**：Shao Peishen 2026-08-23 拍板采纳补充判据「**留判据、迁论证**」——判据（做什么／怎么判／违反会怎样）留在根 `CLAUDE.md`；论证（为什么这么定、与哪条同族、代价权衡、实证细节）迁本附录。
> **本批只搬不改：以下三段为迁出当时的原文原样，根文件对应位置已改为一行指针。** 判据本身一字未迁、全部仍在根 `CLAUDE.md` §5。

### E-1 · 规则退休制 · 论证与首个清算案例（条『规则退休制』）

**问题在于规则语料单调增长而注意力预算不变**：每出一次事故就加一条人守规则，却**没有任何流程删掉一条**，于是每新增一条都在稀释所有既有条目的注意力份额；越过某个点之后，新加的规则**从诞生那天起就是惰性的**——它只在事后被引用来解释「本应如此」。**更隐蔽的副作用**：规则集足够大时，**总能找到一条规则为「已经想做的事」背书**（2026-08-03 实例：环境保障线援引 opener §七「出现质量信号即可转场」提议转场，而同一段里「**先压缩、后转场**」「上下文长 ≠ 该转场」两句被跳过）——**大规则集会催生合理化**。

### E-1（续）· 判据的道理与首个清算案例

**判据的道理**：**一条反复被违反、且每次都靠下游拦截的规则，它实际起的作用不是约束，是事后解释**；留着它只会继续稀释其余规则。 **违反计数落在队列对应行内，不另建台账**（不给这条规则自己再造一个需要人守的载体）。 **首个清算案例＝#164（裸竖线，2026-08-03 达第 3 次）并入 #225 由编辑锁 `release` 校验解决，#164 不再单独挂账**；同批达阈值的还有 #225 本身（批次清单须含队列文件自身，本 session 内 5 次）。

### E-2 · 次序与并行矩阵 · 成因与同族论证（条『一次会话产出多个任务』）

**成因**：2026-08-07 本线一次给出 B1-B5 五个 opener，**只标了各自的依赖类型、没有给出彼此之间的次序与并行关系**——他当场要求补齐。**这与 §〇.0「opener 代码块必须带标题行」是同一类问题的第二个形态**：前者管「这是哪件任务」，本条管「这几件任务之间是什么关系」，**两者都是「在 opener 外层补一个字段，使读者不必推断」**；opener 存在的全部意义就是复制即用、零判断，**让他做推断本身即违背设计目的**。

### E-3 · openspec 触发门槛 · 2026-07-31 断层取证（条『机制/工具类模块的 openspec 触发门槛』）

2026-07-31 取证证实这是一个真实断层：openspec 全库 182 个 `.md` 递归扫描，`simple_gate.py`（#160 四服务鉴权门禁）／编辑锁 `--reserve`（#163 全项目取号口径）／`queue_lock_pending.py`（#168 机器人写队列语义）／`repo_paths.py`（#126 仓库根解析）／`decision_reminder.py`（#172）／`liveness.py`（#147）／sweep 分叉告警（#171）**全部 0 命中**（已用 `kit_engine`→25 命中验证 grep 有效、排除假阴性）。


## 【附录 F · 第四刀整条原文存档 —— 2026-08-23（OP-0823-E，扩围：§5 残余＋§1 名录叙事＋顶部 meta）】

> **依据**：Shao Peishen 2026-08-23 本 session 答「(a) 放行·扩围做」——其「感觉太长」即为三刀后预留的第四刀反馈触发；判据沿用 §四 #80 ⑼「违反是否产生信号」＋「留判据迁论证」。**手法与 A/B/C 同口径：整条原文原样存档（程序化按行搬运、零重打字），§5/§1/顶部侧留压缩后的判据全文＋指针**——读本附录时注意：正文那边留的是完整判据，这边是它被压缩前的全文。共 25 条（含 1 条并入后整行退场）。

#### F-T1 · 顶部「当前进度」元段（第四刀前原文）

> **当前进度**：**历史进度已四批迁入** `1-转型规划/0-全景路线图/进度编年-CHANGELOG.md`（第一批 2026-07-07 迁／第二批 24 条 2026-08-05 迁／第三批 18 条 2026-08-09 迁／**第四批 8 条 ＋ 第五批 SC2 两条，均 2026-08-21 迁，OP-0821-B**）。本段**只留最近一批**（当前＝2026-08-19 共 2 条），更早查 CHANGELOG（同目录、可 grep、原文未改写）。 🔴 **2026-08-21 实测：这条人守规则两次瘦身两次失效**——08-09 瘦到 86,090 B，6 天回到 106,191 B（+3.4 KB/天）；08-16 再瘦到 83,883 B，5 天回到 122,509 B（**+7.7 KB/天，且已超过瘦身前水位 15%**）。**根因不是没人执行，而是本段同时被当作「未闭合项的跨会话载体」，迁走即丢**——故 OP-0821-B 起加一条前置判据：**迁出前须确认该条已有承接载体（队列行号，或具名文件＋章节），无承接载体者不得迁**（SC2 两条即因此在第四批被拦下；同日补立业务队列 §一 `#361` 作承接载体后，才在第五批迁出——这是 J1 的第一个真实用例）。机制化方案见 `1-转型规划/0-全景路线图/memory与上下文预算治理-审核与方案-2026-08-21.md`。

#### F-T2 · 顶部「📦 迁移批次」段（第四刀前原文）

> **📦 2026-08-02 及更早的 24 条进度条目已迁 CHANGELOG**（2026-08-05，队列 #253 / C4）：含 #206 propose 门禁段迁 config、sweep 五行同批、台面清理收尾、#171/#172/#180/#164 四件套、取号三件套、FI2 v8 面板、#126 双缺陷、四服务口令门禁、库存实时源、各次机器人通道建设等。**第四批 8 条已于 2026-08-21 迁**（OP-0821-B）：全景 v6 重排（承接＝全景规划 §0.2 的 2026-08-18 行）、队列 #308 三条（propose／apply／F2 收尾）、队列 #313 三条（queue_table 权威化／CLI 引导缺口补齐／②重评）、队列 #267 一条（孤儿 worktree gitignore 非空第三桶）。**原文原样保留在** `1-转型规划/0-全景路线图/进度编年-CHANGELOG.md`。 **第五批（同日）＝ SC2 两条**（2026-08-18 建造与部署），因原无承接载体而被 J1 拦在第四批之外，补立 §一 `#361` 后方迁。

#### F-T3 · 顶部「memory 层已收割并停用」段（第四刀前原文）

> **🔴 memory 层已收割并停用（2026-08-21，OP-0821-B）**：三种会话类型（本地 Cowork ／ claude.ai 网页版 chat ／ claude.ai 网页版 Cowork）逐一实测**均无 `project_memory_*`**，本项目那 42 件处于「**只被注入、无任何会话可写**」；`Write` 到 `spaces\*\memory\` **报 success 但不落盘**，而同一路径 `Read` 被 connected-folders 边界**正确拒绝** ⇒ 缺陷是 `Write` 少了那道检查且选了 fail-silent。**索引层已原文存档并逐条收割完毕**（8 条有效规则已分别落入本文件 §5 与各专题载体，20 条本已覆盖，13 条作废）⇒ **此后完全忽略 memory 层：不读、不写、不引用**。存档与三分类对账见 `1-转型规划/0-全景路线图/memory索引收割对账-2026-08-21.md`，判死实测见同目录 `memory与上下文预算治理-审核与方案-2026-08-21.md`。 🔑 **留一条教训**：2026-08-16 那份报告的**成果为真**（索引 6→42 全覆盖，有独立证据）、**验证声明为假**（「全部写入经 `project_memory_read` 回读逐字核对」，该工具不存在）——**⇒ 凡「已复核／已回读／已逐字比对」类自陈，必须同时写出用什么核的（工具名／命令／哈希值）；只有动作、没有手段的验证声明，等于没有验证。** 🔴 **不得新建第四份载体**（含在 chat 个人层建 `/areas/zhuopin-*.md`——Cowork 与 CC 都读不到，只会再造一个孤儿）。**跨会话纪律的权威载体只有本 CLAUDE.md 与队列。**

#### F-N1 · §1 职务（唐燕萍）（第四刀前原文）

  🔴 **职务（2026-08-21 Shao Peishen 口述补录，硬事实）**：**唐燕萍 ＝ 财务总监**，她同时是财务域 AI 专员。**⇒ 她对财务口径的圈定即权威签认，不需要再向上找一个「更权威的来源」**——2026-08-21 `§四 #93`（FI3 CFO 审批流 R1–R8 来源标注「唐圈定」被疑非签认件）正是因不知道这一点而卡住。⚠️ **本条与名录同族**：**人的属性（职务／汇报关系／审批权限）一律以本文件为准，载体里没有就问一次并当场落档，绝不从「他是某域 AI 专员」推断其职级**——把总监读成专员，会凭空造出一道并不存在的签认门槛。**其余八人的职务尚未落档，用到时问一次再写，不得类推。**

#### F-N2 · §1 财务部员工名录（第四刀前原文）

  🔴 **财务部员工（2026-08-22 Shao Peishen 一次性给全，原话「全部为女性」，硬事实）**：**唐燕萍（女）**（财务总监，兼财务域 AI 专员，见上）／**李姣龙（女）**／**钱婷（女）**／**孙国庆（女）**／**陶钰（女）**／**朱云澜（女）** —— **该部门在册六人全部为女性**，此后提到财务部任一同事一律用「她」。**企微 chatid 一并落档在** `6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md`《企微 chatid 名录》（**六个 chatid 中有两个是纯数字工号，不是姓名拼音**，绝不可推断）。

#### F-N3 · §1 IT 全员企微名录（含 PMC 教训与 --department 判据）（第四刀前原文）

  🔴 **IT 汇总的全员企微名录（2026-08-22 由 Shao Peishen 转来，含性别与部门，硬事实）** —— 落档在 `6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md`《企微 chatid 名录》全表，此处只记**本名录此前没有的人**：**叶燕（女，PMC部）**／**齐奇（女，采购部）**／**袁洋（男，仓储物流部）**／**刘伟（男，质量部）**／**聂鑫（男，运营支持）**／**汤丽萍（女，人力行政部）**。🔴 **另确认一条**：**`邵培申` ＝ Shao Peishen 本人**（企微账号 `ShaoPeiShen`，大供应链部）——发信脚本自动抄送的那个收件人就是他。 🔴 **组织事实：`PMC部` 是 `采购部` 的一个子部门**（Shao Peishen 2026-08-22 口述）⇒ **汤易水／叶燕虽标 PMC 部，实际都在采购部建制内**。✅ **采购域一线标注层已确认在位 ＝ 解植雅 ＋ 汤易水**（同日答定夺 (a)），`zhuopin-followup-letter` §8 那条「建议人选、是否已安排未确认」**至此解除**，写采购域判例包可明写请这两位先批量初标。 🔑 **顺带留一条方法教训**：我初次落这张表时，把「解植雅在采购部、汤易水在 PMC 部」标成了「**与既有记载不符**」——**其实两份记载都对，缺的是「PMC ⊂ 采购部」这条我不知道的事实**。**⇒ 判两份记载冲突之前先问一句：有没有一条我不知道的事实能让它们同时成立？**「矛盾」这个判词自带「其中一方是错的」的暗示，会催出不必要的改判（同「更正本身也会错」那一族）。 ✅ **PMC 人员的群抄送 ＝ 并入采购部大群**（Shao Peishen 2026-08-22 拍板）。🔴 **落到命令上是个反直觉写法：`--department` 要填 `采购部`、不能填 `PMC部`** —— 该参数取的不是「名片上的部门」，而是**「部门→群 chatid」映射表的键**，那张表只有 `财务部／质量部／采购部／跨部门` **四个键**；传 `PMC部` 会命中 `department_not_in_mapping` 分支，**fail-closed 静默跳过群抄送、不报错、命令行一切正常**（信发到本人、群里什么都没有）。**⇒ 与「只信 stdout 会被骗」同一个坑的第二个入口。** ⚠️ **三处缺口**：销售 **泓钦**、决策代理 **孙涛**、财务部除唐燕萍外五人，**均不在 IT 那张表内**，用到时须另问，**不得因不在表内就当作此人不存在**。

#### F-N4 · §1 带偏名单（含财务部#14 事故全文）（第四刀前原文）

  ⚠️ **本名录里有 7 个名字会把语言直觉带偏，正是它们害我错了 6 次以上**：`祖怡`／`燕萍`／`映桦`／`植雅`／`易水`／🔴 `姣龙`／🔴 `国庆` —— **字面观感与真实性别的对应关系在这份名单上接近随机，任何「读起来像」的判断都无效。** 🔴 **后两个是 2026-08-22 新增，且当天就已经咬过一次**：`财务部#14` 正文两处把**李姣龙**写成「他的企微账号」，**信已发出、撤不回**（03:51 UTC 发，04:4x 才拿到名录）。**⇒ 这次的教训不在「又猜错了」，而在「明知规则仍未执行」**——同一封信起草时，`#372` 行内白纸黑字写着「李姣龙…名录内无此人，一律用中性表述『该同事／其』，不得从名字推断性别」，我读过那一行、还在信里引用了 `#372` 的其它内容，**却仍然写了「他」**；同一天我甚至把这条规则亲手写进了新建的 `zhuopin-send-followup` skill。**读到规则 ≠ 执行规则**：真正的落点是**起草完成后扫一遍全文的第三人称代词**，逐个回到本名录核对——这一步在本次不存在，所以规则再多也拦不住。**⇒ 已作为一条起草期自检写入跟进信 README。**

#### F-N5 · §1 名录成因（244 处样本）（第四刀前原文）

  **成因（值得原样留下，因为它是一整族错误的样本）**：Shao Peishen 已当面纠正 **≥5 次**「姚祖怡是男性、陈忱是女性」，而**每次纠正都只修好了当次那一句话**——因为直到 2026-08-20 为止，**全库没有任何一处记录过任何一位专员的性别**（实测：本文件里「姚祖怡」出现 8 次、零性别信息；《部门AI专员协同一页纸》与跟进信 README 同样零命中）。于是**每个新 session 都从「祖怡」「忱」这两个名字重新推断一次**，而**推错不会有任何下游报错**。 🔑 **⇒ 这不是记性问题，是「他纠正的是输出，而我从未把它写进任何会被下一次载入的载体」**——与本文件反复记的「规则只活在报告文本里、没有承接行」「§二 批次行不是跨会话待办载体」完全同族。 **实测代价**：队列两份真身、跟进信 README、接力件里，涉及姚祖怡的行累计 **244 处**把他写成「她」。

#### F-R1 · §5 专员跟进纪律（第四刀前原文）

- **专员跟进纪律（Paul 2026-07-04 定，新 session 一律遵守）**：对部门 AI 专员/对接人的跟进信**统一归集** `6-人才与组织/部门AI专员跟进/`，命名 `部门-姓名-跟进-YYYY-MM-DD-主要事项.md`（实名前用角色代称），每封必含三要素**做什么/怎么做/什么时候交**、随附《部门AI专员协同一页纸》对应域节，发一封在该文件夹 README 清单追加一行。**节奏**＝事件驱动为主 + 月度固定触点，交付密集期升为每周。**口径类任务一律走"AI 起草·专家批改"三步法**（专家只批改不写作业），不布置写文档式作业。**三层文档结构（总则层／导航层＝协同一页纸／跟踪层）的分工与刷新节奏见该 README。****需求确认方式升级（Paul 2026-07-25 拍板，2026-07-27 周一起全域生效，不试点）**：口径/需求确认此后**唯一格式=判例批改法**——禁止抽象设问（"规则该怎么定"），一律转为 ≤10 条**真实**案例的"现状判定 vs 拟改判定"对照，专员只做 ✅对/❌错/✏️改判+一句话；规则条文由专线从判例反推、回发一行请专员确认。配套：**🔴 一信决策点无上限（2026-08-18 Shao Peishen 正式拍板取消原「≤3 个」上限，2026-08-22 复核并清除本处残留，OP0822A）——已完成、可交付的内容一次发完，不为凑数量而拆信；通报／告知／认错类内容不计入决策点**；默认预案分级（纯展示类可标 48h 默认生效，**判据/口径/阈值类永不默认生效**，超时升级 Paul 线下——IATF 显式签认红线）；**不加并行专员**（判定权威单点），人力加"一线标注层"（实操者批量初标、专员只裁分歧项）。**度量＝口径点提出到销点中位天数，目标 ≤1 周** —— ✅ **2026-08-23 到期复盘：达标，回退闸已摘**（Shao Peishen 当日答 (a)；实测代理指标中位 2 天／均值 4.5，复盘件与口径边界见 `6-人才与组织/部门AI专员跟进/度量复盘-判例批改法回退闸到期-2026-08-23.md`）。**微会节奏／开放点计数／度量口径细则规范见** `6-人才与组织/部门AI专员跟进/需求确认方式升级-判例批改法与微会机制-2026-07-25.md`+专员一页说明。**场景发布自动起草跟进信 + 跟进信按部门连续编号（Shao Peishen 2026-07-31 定，全局）**：CC 完成一个业务场景模块的“发布收口”（部署 `.51`+冒烟通过，见本节下方“发布即收口纪律”）后，**当场起草**一封通知归属部门 AI 专员“新版已上线请试用+反馈”的跟进信，**当次会话内提交 Shao Peishen 审核**，通过后由 CC 直接发送（企微机器人私信专员 + 抄送部门群 webhook）；未获审核不得发送。所有跟进信**自 2026-07-31 起按部门连续编号**（`部门#N`，跨收信人共用同一计数器，换人不重置；未发出/已作废的信不占号），历史 29 封已回溯编号，编号只落在 README 表格与信件抬头、不进文件名（“已发旧信不改名”仍是硬规则）；细则见 `6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md`。

#### F-R2a · §5 场景流程第 8 步（发布即刻起草跟进信）（第四刀前原文）

  8. **发布即刻起草跟进信（Shao Peishen 2026-07-31 定，全局规定动作，紧跟第 7 步；2026-08-05 随队列 #124 阶段二两态语义补丁措辞）**：第 7 步发布收口完成后，🔴 **先查串行闸，再决定起不起草（Shao Peishen 2026-08-20 答 §四 #74 选 (a) 改定；本条 2026-08-20 前写的是无条件「当场起草」）**——判据＝查 `6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md` 中**该收信人最近一封**的发送状态列是否已到闭环形态（`📥 已回件并回灌`／`✅ 无需回复`／`📨 已确认闭环`）：**⑴ 闸开** ⇒ **当场起草**一封通知归属部门 AI 专员“新版已上线请试用+反馈”的跟进信，README 登记行「发送状态」列**只写 `⏳ 待你审`**（唯一合法起草产物，不得直接写终态）；**⑵ 🔴 闸锁 ⇒ 不起草**，改为在队列对应行**登记「待前信闭环后发」并写明拟发内容要点**（这正是串行原则指定的替代动作），**本步到此为止，不进入下方审核与发送流程**。 **⑶ 闸开且已起草者的后续流程**：**提交 Shao Peishen 审核**，批准后方可发送——未经批准脚本转态不得发送。两态语义、批准脚本用法、`🔒人工发送` 硬截止标记约定见 `6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md`。**不得省略**——发布收口不因“专员还没空看”而跳过本步，通知与试用反馈是发布收口价值兑现的最后一环。 **本步「为什么必须先查闸」的完整辨析（与串行原则的正面冲突、机器闸站在哪一边、为何不得退到「起草但不登记 README」）与成因（2026-08-20 CC 主动停手／SC2 反向先例）**，见 `6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md`「第 8 步串行闸辨析」节。

#### F-R2b · §5 发送硬前置（第四刀前原文）

     🔴 **发送硬前置（Shao Peishen 2026-08-03 定，选项 (a)，两桌全局）——「部署冒烟通过」是发信的前置条件，不是并列步骤**：**第 7 步的部署与冒烟必须已真实通过，方可发送**该信；**代码尚未合入 master、或未部署、或冒烟未过，一律不得发送**（起草、送审可以先做，**发送必须等**）。**判据（三条全过才算满足，缺一即不得发）**：① 改动已 ff 合入 `master`（`git rev-list --count master..<分支>` ＝ 0）；② `.51` 已部署且冒烟通过（`/api/ping`／关键页 200／一次全量重算）；③ **用专员原始举证的那个真实案例做端到端复现**——看板/页面须显示修正后的值。 **配套机制侧强制见队列 #229**（sweep 检出“命中已部署场景目录却无部署留痕行”即告警，同 #198(c) 范式）；**本条与「跟进信串行原则」并列适用**——串行原则管“前一封是否已闭环”，本条管“这一封的内容是否已真的上线”，**两条都过才发**。 **本条成因（2026-08-03 队列 #228 真实事故与同族第三次复发）见同上 README 该节。**

#### F-R3 · §5 跨桌任务队列纪律（第四刀前原文）

- **跨桌任务队列纪律（Paul 2026-07-09 定，两桌强制；**B2 类 2026-08-09 降为指针**）**：`1-转型规划/0-全景路线图/跨桌任务队列.md` 是两桌间任务流转的**唯一载体**——所有 session **开工必读**（认领本线待领任务 + 登记触碰区）、**收工必写**（状态 + 产出路径 + 新冒出的下游任务当场追加待领行）；**触碰区与他人在办重叠不得抢领**，报总线裁决；**commit 一律由 CC 从 §二「待 commit 批次」取活销行**（一批一行）；**口径冻结标（§三）**：某域进入口径重梳期即挂标，CC 见标停该场景在途建造。 🔑 **编辑锁（协议〇.7）／每周清扫与编号高水位线（协议〇.8）／并入审核与可动 WIP（协议〇.9-〇.10）等全部细则，以队列文件顶部「协议〇」为正本**——**那份才是被编辑锁与 sweep 实际执行的版本**，此处不再复述（复述过就会与正本漂移）。 **值周巡检**每周一 10:00 读队列生成《本周计划》，**开跑前先跑跨会话对账审计**（skill `zhuopin-queue-audit`，Paul 2026-07-11 定）——以文件真身校准队列后再出周计划。**gap 收口纪律（Paul 2026-07-22 定）**：审计发现「设计↔执行 gap」时，须驱动到**有主·有截止·已派单**的收口路径后计划才往下走，不把未解决 gap 埋进计划当普通行。

#### F-R4 · §5 文档治理六规则（第四刀前原文）

- **文档治理六规则（2026-07-07 定，生效，见《文档治理规范与规整执行清单-2026-07-07.md》）**：**R1/R2 已机制守，降为指针（A 类，2026-08-09）**——md frontmatter 状态头六枚举（生效｜在办｜待发｜已执行归档｜已作废｜历史快照）由 `0-学习与工具/工具-文档台账生成.py::STATUS_ORDER` 强制，台账重跑已并入落库 sweep；**找文档先查 `0-全景路线图/文档台账-自动生成.md`、不翻目录**，唯 CC 不经 sweep 的收工动作（直接改文档、不走 §二批次）仍须手动重跑一次。**以下 R3-R6 仍属人守，正文保留**：R3 生命周期（开场prompt/移交单/批改单已执行回填即改 status，**每季度**批量搬运入 `z-已执行归档/` 夹并做全库引用清扫，禁止零星搬）；R4 命名四律（主题-对象-日期-事项、文件名不含会变数字、md/docx 同名视为一对、prompt 类统一 `开场prompt-` 前缀）；R5 接力瘦身（🔴 **2026-08-22 改版，OP0822A，Shao Peishen 提出**：四条 session 接力**不再是日志、是定长交接卡**——**硬上限 8 KB、固定六块、零日期节**，收工**覆盖**六块而非追加；进度叙事写 `进度编年-CHANGELOG.md`、方法教训写 `0-学习与工具/取证方法知识库.md` 或队列行、未闭合项写队列行，迁出前守 J1 承接载体判据。**已机器守 ＝ J6**（`0-学习与工具/工具-CLAUDE进度段lint.py` 超 8 KB 或出现日期节即告警）。**旧版「留最近 2 个日期节」为何执行了也不管用、顶部进度段同病的实测数据，见队列 §四 #80**）；R6 专员回复归档（专员正式材料落 `7-外部文档/<部门>/`，专线只认文件不认转述）。

#### F-R5a · §5 环境保障线派单边界（第四刀前原文）

- **环境保障线的派单边界（Shao Peishen 2026-08-02 定；**C 类 2026-08-09 采纳反方意见：正文留边界句、细则与成因迁 opener**）**：**对象是构建环境与自动化机制本身**（worktree/stash 台面、编辑锁、sweep、巡检巡逻、队列纪律、openspec 工作流、本机工具链、机器人链路）＝**环境整治，本线可备派单件并协同 CC 执行**；**对象是业务场景代码、平台底座功能、真实数据与 `.51` 现网服务**（即便入口是一个"测试失败"）＝**项目构建，交业务总线派发**。细则·边界个案·成因见 `1-转型规划/0-全景路线图/开场prompt-【Cowork】环境总线-接力交接-2026-08-08.md` §六bis。

#### F-R5b · §5 环境保障线机制收口交付形态（并入 R5a 后整行退场）（第四刀前原文）

- **🔴 环境保障线以「机制收口」为默认交付形态，不直接派活（Shao Peishen 2026-08-03 定；**C 类 2026-08-09 同上**）**：本线默认交付物＝**① 环境取证与梳理结论 ② 方案定稿 ③ 队列行写入**；**分发由值周巡检与拆件巡逻完成，不由本线推动**——"备一份派单件 + 请他粘贴开场词"属直接派活，仅在紧急且经他明示授权时才用，且须在队列行注明因何紧急而绕过机制分发。成因与两处实证见同一 opener §六bis。

#### F-R6 · §5 开场词与 prompt 纪律（第四刀前原文）

- **开场词与 prompt 纪律（Paul 2026-07-06／07-08 定；**E 类 2026-08-09 由「会话接力」拆出**）**：凡产出交接/开场 prompt 文件（专线转场、CC 交接等），文件内必须内置一段**「开场词（复制即用）」**——单句、含目标文件完整路径引用，复制粘贴即可开新 session；聊天回复中同步给出该可复制块，不让他自己拼路径。**收工段必带 git 处置**：Cowork 专线/总线类 prompt 的收工段须写明「列出本次全部新产出/修改文件清单 + 建议 commit message + 提示他一句话交 CC：commit + push + 收工重跑台账」（Cowork 不擅自 commit，但必须交代去向，不留未提交悬置）；CC 类 prompt 本含 commit+push，另加「收工重跑台账」。**呈现格式（2026-07-08 补）**：≤500 字直接给完整原文、>500 字落 prompt 文件 + 单句开场词引用；无论长短一律放 **fenced 代码块**（渲染自带复制按钮，一键复制），不用引号段落。**opener 十二条细则见 `1-转型规划/0-全景路线图/专线opener模板库.md` §〇**（含执行环境标注、标题行、工作区、session 字段、次序与并行矩阵、写后反查三件套等）。

#### F-R7 · §5 信状态唯一权威（第四刀前原文）

- **🔴 信状态唯一权威 ＝ 跟进信 README 的「发送状态」列（Shao Peishen 2026-08-21 答 §四 #85 选 (b) 确立，两桌全局）**：**跨桌任务队列不是信状态的载体**——队列行里「等某某#N 闭环／待某某回件／串行闸锁着」这类**复述**一律是会过时的快照，**不得作为判据**，队列只允许写指针。**判闸唯一入口**＝`python 0-学习与工具/工具-跟进闸查询.py --to <收信人>`（实现中，派单件见 `1-转型规划/0-全景路线图/派单件-【CC】跟进信状态单一可信源S2-S4-2026-08-21.md`）；**上线前一律直读 README 该收信人最近一行**。 🔑 **成因**：机器只写队列、闸只读 README，中间那一步一直是人 ⇒ **串行闸永远不会自己开**——2026-08-21 当天两次咬人（质量部#8 回灌全做完了闸还锁着；采购部#17 回件 13:13 到、13:15 队列已追行而 README 未动）。⚠️ **「合并成一个文件」已被实测否掉**：两者不是存同一份状态，而是双向交叉引用 506 处，合并后引用一处不减。设计正本 `1-转型规划/0-全景路线图/跟进信状态单一可信源-架构设计-2026-08-21.md`，机制行 §一 `#366`。

#### F-R8 · §5 执行环境标注（第四刀前原文）

- **执行环境标注（Paul 2026-07-27 定，硬规则；**E 类 2026-08-09 拆出**）**：凡对外呈现的任务/opener 标题，**必须在任务名处显式标注 `【Cowork】` 或 `【CC】`**，`【设置】` 行同步写 `执行环境：Cowork/CC`（两处冗余：标题供扫读挑活、设置行随 opener 复制进新 session）。**判别**：只产改 `.md`、不写生产码、不自行 commit（收工只登记 §二 批次）＝**Cowork**；写跑代码/连真实库与 `.51`/测试部署/自行 commit+push/一任务一 worktree＝**CC**；只读取证（PowerShell 直读接口、git 取证）仍属 Cowork，一旦要改代码或触发服务动作即转 CC。 **🔴 中间地带：改本机工具链＝CC（Shao Peishen 2026-08-02 定）**——全局 npm 包/插件/CLI 的**安装与版本升级**，以及 `openspec update` 一类**会重写生成物的命令**，**一律归 CC，即便其产出看上去只是 `.md`**（理由：改的是**全项目构建环境**且**可能静默覆盖本地定制**）。**Cowork 仅在紧急且迫不得已、并经其明示授权时破例**（他在会话内的一次性明示授权即为充分，不需另开派单或走变更包）；破例时**必须**①先固化升级前证据②逐文件过目 diff（**推荐判据＝中文行增删计数**）③事后如实登记为破例。 **⚠️「已获授权」不等于「该照原方案执行」——授权解除的是「能不能动手」，不解除「该不该这么动手」**：动手前的取证若推翻了方案本身，正确动作是回报改判、另立行，而不是把已授权的动作照做完。 **四处落点一致**：值周巡检《本周计划》§A、拆件巡逻报告拟动作、队列 §一 新行「领取方」列、各类交接/开场 prompt 标题。细则与模板见 `1-转型规划/0-全景路线图/专线opener模板库.md` §〇。 **成因**（2026-07-27 本周计划歧义；2026-08-02 #205-A `openspec update` 零提示删除 propose 门禁段；同日五 worktree 注释方案被取证推翻）见 `…进度编年-CHANGELOG.md` 附录 A。

#### F-R9 · §5 规则退休制（第四刀前原文）

- **规则退休制（Shao Peishen 2026-08-03 定，两桌全局；针对「规则只增不减」这一根因）**：本节与队列协议〇 的每一条纪律实质分两类——「**机制守**」（有代码／工具／门禁强制执行，**不记得也会被拦**）与「**人守**」（只靠人读过并记住）。**根问题＝规则语料单调增长而注意力预算不变**（每出一次事故就加一条，却没有任何流程删掉一条），且**大规则集会催生合理化**——总能找到一条规则为「已经想做的事」背书。**完整论证与 2026-08-03 那个实例见 CHANGELOG 附录 E-1。** **故立退休制**：**任一「人守」条目被违反 3 次即达阈值，必须二选一**——① **机制化**：挂到不可绕过的咽喉上（队列写入的咽喉＝协议〇.7 编辑锁 `acquire`／`release`；提交的咽喉＝落库 sweep）；**正文可降级为一行指针、不必删**——依据 #206：CC 把规则迁入 `openspec/config.yaml` 后，仍在 `propose.md` 保留了指针注释并标注「防御性冗余、非机制必需」。② **删除**（确无价值时）。 **违反计数落在队列对应行内，不另建台账**（不给这条规则自己再造一个需要人守的载体）。 **判据的道理（反复被违反的规则起的作用不是约束、是事后解释）与首个清算案例（#164 裸竖线并入 #225 由编辑锁 `release` 校验解决）见 CHANGELOG 附录 E-1。**

#### F-R10 · §5 同步纪律（第四刀前原文）

- **同步纪律（**E 类 2026-08-09 拆分**）**：开工先跑 `git fsck --connectivity-only`（秒级对象库健康哨兵），再 `git pull`；收工 `git push`（GitHub＝权威备份，`.git` 损毁可十分钟恢复）；**同一文件别两边同时改**。**fsck 报错即停**，勿 pull/push，报 Shao Peishen 走恢复流程——**先把工作区未 commit 的改动手工备份到仓库外临时目录**，再 GitHub 重 clone，最后拷回未提交件与 `.env`/reports 等 gitignore 件（2026-07-04 评审整改：防重 clone 吞掉未提交成果）。**OneDrive 惯例（2026-07-07 更正）**：平时全关，每周趁其他程序休息手动开一次作纯离线备份；`.env`/`real_frozen/`/reports/*.db 等 gitignore 件不在 GitHub，备份新鲜度按**最多一周旧**评估，当周有重要新件可提前加跑一次——**不是「不可长关」**。 **排查「文件像是变旧了」的顺序**（先查分支/reflog → 再本机磁盘直读比对 → 最后才疑真损坏）属取证方法，见 `0-学习与工具/取证方法知识库.md` §三.1。

#### F-R11 · §5 新场景不新起端口（第四刀前原文）

- **🔴 新场景一律不新起端口（Shao Peishen 2026-07-29 定，硬约束，两桌全局；**E 类 2026-08-09 拆出独立成条——判定表点名它就是「混装条目里藏着的那条硬约束」**）**：**新增场景不得新起独立端口对外**，一律注册到统一门户路由 `/{域}/{场景}` 下（如 `/procurement/sc7`、`/quality/8d`）并预留网关 auth 接入点（中间件未就绪期间可为空壳，但路由与接入点必须留）。**成因**：现状四个平级独立服务（8091 保供看板/8092 命令中心/8093 QD-B/8094 FI2）**零鉴权代码且全部绑 `0.0.0.0`**，而采购域还有 SC1/SC2/SC4/SC7/SC10/SC11 待上、质量域还有 8D 与 IQC/SPC——按原惯性即再增 8+ 个端口，收编成本随场景数线性增长。**存量三个可慢慢收编，增量必须当天止住。** 目标态＝一个门户 + 一次企微 OAuth 登录 + 各域挂统一路由，**后端保持独立服务不合并进程**（保留故障隔离）。完整设计见 `3-治理与合规/统一门户架构决策件-SSO与权限-2026-07-29.md`（待 design 审）。

#### F-R12 · §5 openspec 触发门槛（第四刀前原文）

- **机制/工具类模块的 openspec 触发门槛（Shao Peishen 2026-07-31 定，硬规则）**：下方「每个场景固定流程」字面只约束 `4-数字员工/<部门>/<场景>/` 里的**业务场景**，**不覆盖平台底座与机制/工具类模块**——2026-07-31 取证证实这是一个真实断层（七个机制模块在 openspec 全库 **0 命中**，而它们**影响面比某些业务场景更大**——改的是全项目口径与对外鉴权边界，却无 spec 约束）。**逐个模块的取证明细与假阴性排除见 CHANGELOG 附录 E-3。****故立触发式门槛——不搞一律，命中以下任一即必走 openspec（含 design 审）**：① **改变全项目口径**（取号／编号／判据／状态语义等跨场景生效的约定）；② **涉鉴权与数据可见性**（谁能看到什么，如 `simple_gate`）；③ **改变既有模块的对外语义**（同一函数/接口在相同输入下行为变了）。**不走**：纯 bugfix、告警文案、日志措辞、单测补充、纯文档清理。**判不准就走**——多一道 design 审的成本约半天，而 ①②③ 三类一旦无 spec，在 IATF「单一可信源/可追溯」审核下站不住（#160 是鉴权层，尤其如此）。

#### F-R13 · §5 决策路由 08-05 退休说明块（第四刀前原文）

> ⚠️ **2026-08-05 那两条（标注须写具体 session 名／`【原 session 答】` 作废）已被下方 2026-08-19 判据改版整体覆盖**——新体系只有 ⟨就地答⟩ 与「已登记 §N，待总线派发」两态，不再需要 session 名标注。**原文与成因见 CHANGELOG 附录 D，此处不再复述**（规则退休制：被取代的判据不留在正文，否则读者要自己判断哪条现行）。

#### F-R14 · §5 次序与并行矩阵（第四刀前原文）

- **🔴 一次会话产出多个任务时，必须指明「次序」与「能否并行」（Shao Peishen 2026-08-07 定，两桌全局）**：其原话——「**以后一个会话产生多个任务都请指明秩序和并行**」。**判据（可机械化）**：凡一次回复给出 **≥2 个 opener／派单件／可开工任务**，必须附一张**次序与并行矩阵**，逐项写明：① **能否立即开工**（零依赖／软序／硬阻塞／定时触发型四选一，**依赖判断以队列行状态列开头的括注自陈为准，本项目没有独立依赖表**）；② **能否与其它哪几项并行**，并写明**并行判据＝触碰区是否重叠**（重叠即软序，须串行或同车）；③ **若必须串行，谁先谁后及其理由**。**不得只把任务并列列出，让他自己推断先后。** **成因（2026-08-07 B1-B5 五个 opener 那次）与「它与 §〇.0 opener 标题行是同一问题的第二个形态」的论证，见 CHANGELOG 附录 E-2。** **自检一问**：*把这几个 opener 一起发给一个没读过本次会话的人，他能一眼说出该先开哪个、哪几个可以同时开吗？* 不能→矩阵没写够。

#### F-R15 · §5 memory 勘误退休块（第四刀前原文）

> ⚠️ **原挂此处的 memory 层勘误已退休（2026-08-23）**：memory 层已于 2026-08-21 整体判死停用（不读／不写／不引用），那段「本机旧层 vs 云端层」之争随之失去对象。**现行结论只有一句：跨会话纪律一律落本 `CLAUDE.md` 与两份队列，不落 memory** —— 判死实测与三分类收割见顶部 memory 段所指两份档。

---

## 【附录 G · §5 论证下沉第五刀 —— 2026-08-28（OP-0828-Q，队列 #433 A2「瘦身下沉」）】

> **依据**：Shao Peishen 2026-08-28 拍板方案 1a（P1 期「瘦身下沉」），派单件＝`1-转型规划/0-全景路线图/开场prompt-【Cowork】CLAUDE瘦身与名录下沉-2026-08-28.md` D 段。
> **方法（与第三刀 E、第四刀 F 一致）**：**判据句留根、论证与细则下沉**，本附录条目**原文原样**，不改写、不缩写；根 `CLAUDE.md` 对应位置留判据 ＋ 一行指针。
> 🔴 **守 J1**：本附录即承接载体，先建后迁。
> 🔴 **选段避让**：本刀刻意**不动**队列 §一 `#381`（§5 规则机制化降指针，one-in-one-out）所辖的四族——跟进信族／写侧日期／CC 复命取件／输出格式族（含会话末决策项、决策路由、次序矩阵、输出规范）。那四族须「先机制真实验活、后降指针」，与本刀的「论证下沉」是两条不同的路，**不得互相借名义**。

#### G-1 · §5「执行环境标注」条（下沉前原文）

> - **执行环境标注（Paul 2026-07-27 定，硬规则）**：凡对外呈现的任务/opener 标题**必须标注 `【Cowork】` 或 `【CC】`**，`【设置】` 行同步写 `执行环境：Cowork/CC`（两处冗余：标题供扫读挑活、设置行随 opener 复制进新 session）。**判别**：只产改 `.md`、不写生产码、不自行 commit（收工只登记 §二 批次）＝**Cowork**；写跑代码／连真实库与 `.51`／测试部署／自行 commit+push／一任务一 worktree＝**CC**；只读取证仍属 Cowork，一旦改代码或触发服务动作即转 CC。🔴 **中间地带：改本机工具链＝CC（Shao Peishen 2026-08-02 定）**——全局 npm 包/插件/CLI 的安装升级、`openspec update` 类会重写生成物的命令，一律归 CC（改的是全项目构建环境且可能静默覆盖本地定制）；**Cowork 仅紧急且经其明示授权时破例**（会话内一次性明示即充分），破例须①先固化升级前证据②逐文件过目 diff（推荐判据＝中文行增删计数）③事后如实登记。⚠️ **「已获授权」≠「该照原方案执行」**——动手前取证若推翻方案，正确动作是回报改判、另立行，不是把已授权动作照做完。四处落点与模板见 `1-转型规划/0-全景路线图/专线opener模板库.md` §〇；成因见 CHANGELOG 附录 A。

#### G-2 · §5「排期同步纪律」条（下沉前原文）

> - **排期同步纪律（Paul 定，2026-06-19，强制；2026-07-07 补：docx 重转范围扩大）**：任何业务场景的**实现时间一旦变更**，必须**同步更新所有规划与四阶段路线图**——`全景规划`（§2.1.3 场景块 + §加速启动总览权威排期表 + 四阶段/第四阶段 + 各甘特指针）、`实施计划（最新版）`（§一总清单 + §二时间线 + Phase 2）、相关路线图/前置数据总表，并**重生成对应 docx**。**零残差、不留旧档**；改完 grep 自检一致。单一可信源 = 全景规划 §加速启动总览排期表。**docx 重转纪律（2026-07-07 定，不限于排期变更）**：此后凡任何重排/重梳**触碰**了 `全景规划.md` 或 `实施计划（最新版）.md` 正文，**收工前必须**用 `0-学习与工具/md转Word工具/md2word.py` 把这两份 md 对应的 `.docx` 一并重转并入同一批 commit——不得只改 md、留 docx 滞后（用法：`python md2word.py <md路径> -o <docx路径> --org 卓品智能科技`，在 `md转Word工具` 目录下执行相对路径）。

#### G-3 · §5「文档治理六规则」条（下沉前原文）

> - **文档治理六规则（2026-07-07 定，正本＝《文档治理规范与规整执行清单-2026-07-07.md》）**：**R1/R2 已机制守**（状态头六枚举由 `工具-文档台账生成.py::STATUS_ORDER` 强制、台账重跑并入 sweep；**找文档先查 `0-全景路线图/文档台账-自动生成.md`、不翻目录**；唯 CC 不经 sweep 的直接改档仍须手动重跑一次）。**R3 生命周期**：已执行即回填 status，每季度批量搬 `z-已执行归档/` 并做全库引用清扫，禁止零星搬。**R4 命名四律**：主题-对象-日期-事项／文件名不含会变数字／md·docx 同名为一对／prompt 类统一 `开场prompt-` 前缀。**R5 接力瘦身（🔴 2026-08-22 改版，OP0822A）**：四条 session 接力＝**定长交接卡**——硬上限 8 KB、固定六块、零日期节，收工**覆盖**不追加；进度叙事写 CHANGELOG、方法教训写取证知识库或队列行、未闭合项写队列行，迁出守 J1；**已机器守＝J6**（lint 超限即告警）；旧版为何失效见队列 §四 #80。🔴 **尺寸半条已降指针（2026-08-23，OP-0823-G，队列 §一 #338⑤）**：「`CLAUDE.md` 多大算超限」此后**不再是人守**，由落库 sweep 第 4 类常驻告警承接（阈值与解除语义见 `0-学习与工具/工具-落库sweep.py` 的 `_check_claude_md_carrier_size`）——**本行只作指针，判据以代码为准**；人守条目由此净减一（守协议〇「规则退休制」：机制化优于新增人守）。**R6 专员回复归档**：正式材料落 `7-外部文档/<部门>/`，专线只认文件不认转述。

#### G-4 · §5「发布即收口纪律」条（下沉前原文）

> - **发布即收口纪律（Paul 2026-07-19 定，选项①拍板）**：AI 场景的基本目标是**尽快让部门成员用上、在工作中发挥作用并反馈迭代**——故把「具备发布条件的最小 MVP 及时部署到 `.51` + 部署段基本测试」确立为 CC 建造模块的**收口标准**（不是「代码跑通」即完）。**发布条件清单（四关）**：① **功能门槛**——全量测试绿 + 零回归 + 黄金基准不漂移 + openspec 归档 + 场景 CLAUDE.md 更新；② **部署段**——真部署 `.51` + 冒烟（`/api/ping`·关键页 200·一次全量重算）+ 回滚 SOP 在位 + **可常驻**（守护/自愈，非从临时 worktree 跑一次；企微机器人 07-16 停摆 24h49m 即反面教材）；③ **合规不放松**——两道门禁（只归档/通知不自动执行、L2 人工确认，见 §7）照旧，「发布」=部署供试用/反馈，**≠ 放开 AI 自动执行业务**；④ **先灰度后依赖**——部门成员试用 + 反馈入口先行，价值兑现后再谈正式生产依赖（呼应批次制复盘闸）。**部门成员统一入口 = AI 运营指挥中心**（`1-转型规划/AI运营指挥中心/`，深色指挥中心风门户，采购保供看板为首个旗舰入口，质量/财务/销售逐步填）。全景总纲 §0.2 已登记（2026-07-19）。

#### G-5 · §1 人员名录段（下沉前原文，OP-0828-Q A/B 段）

> **迁入地不是本附录，而是新建正本 `6-人才与组织/人员名录-称谓与性别-正本.md`**（名录是**现行硬事实**、不是历史叙事，故不入 CHANGELOG；本条只登记迁移事实与逐字核验方法）。
> **迁移核验（机器判据，非自陈）**：以正则 `([一-龥]{2,4})（(男|女)` 对迁前原段与迁后正本各取 name→gender 对集合作差集比对 —— **缺失 0、新增 0**；另对 21 人姓名列表与 7 个易错名清单逐项 `in` 检查，**缺 0**。
> **本次只搬不改**：名录内容为硬事实，本棒只有搬移权、没有修订权；若发现疑似错漏一律登记队列 §四 问一次，不得顺手改。
> **根 §1 留存形态**：4 行硬指针（正本路径／禁推断＋七易错名／「人的属性一律以载体为准」判据／起草期代词自检动作）。

## 【附录 H · 根 CLAUDE.md 去 provenance 瘦身（P1）前全文存档 —— 2026-09-03（OP-0903-G/H 探针后，环境总线瘦身线）】

> 承接载体（J1）：本附录承接 2026-09-03 P1 从根 CLAUDE.md 迁出的**全部**「谁定／何时定／成因／实证／改版史」文字。新版根文件每条只留「触发→动作→判据／指针」，其余以本附录为唯一原文来源。逐条映射见同批 `根CLAUDE.md瘦身-P1映射表-2026-09-03.md`。
> 存档对象＝git 中 `CLAUDE.md` 于 P1 换版前一提交的工作树全文（字节数 48,466 / 133 行）。

```markdown
# CLAUDE.md — 卓品智能 AI 转型（项目级记忆）

> 本文件是项目级上下文/记忆（Hermes L1）。Claude Code / Cowork 进入本仓库先读它恢复上下文。
> 全局身份/偏好见 `~/.claude/CLAUDE.md`（不重复）；本文件只写**本项目**的背景、架构、工作流与红线。
> 代码与注释用中文，技术术语保留英文；用供应链业务语言描述功能（如"齐套分析""承诺交期""在途跟踪"）。

> **当前进度**：历史进度已五批迁入 `1-转型规划/0-全景路线图/进度编年-CHANGELOG.md`（可 grep、原文未改写）。本段**只留最近一批**（当前＝2026-08-19 共 2 条）。🔴 **迁出前置判据 J1：迁出前须确认该条已有承接载体（队列行号，或具名文件＋章节），无承接载体者不得迁**——先分流、后迁移。 ⇒ **本段的条目数／单条长度／J1／字节尺寸／批次跨度已全部机器守**（`工具-CLAUDE进度段lint.py` ＋ `工具-落库sweep.py` 第 4 类常驻告警），阈值以代码为准、此处不复述。
>
> 🔴 **OP-0819-F（2026-08-19）三句判据**：⑴ **「探针通了」≠「机制通了」**——`#82` 告警建成 9 天每天在跑却一条都没真发出过，中间任何一轮都没人察觉；两者之间隔着部署、配置、代码键名三层。⑵ **退出码只认被执行进程自己那一层**——`cmd /c` 里的 `%ERRORLEVEL%` 在解析期就被展开，读到 0、真值是 2；改独立 `.ps1` 读 `$LASTEXITCODE` 才拿到真值（与「管道吃掉退出码」同族：**都表现为拿到一个看起来很正常的 0**）。⑶ **推翻一条既有实测记录前，须与原记录同口径复测一次**——一条「更正」把本来正确的记录改错了；更正自带「我已复核过」的语气，比原始错误更难被发现。 ⇒ 全文见 CHANGELOG §「2026-08-19（第六批迁移）」；未闭合处置项挂 §四 #73。
>
> **OP-0819-A（2026-08-19）四句判据**：⑴ **一份拆成两份，下游只跟了一份**——修法＝走 `queue_table.iter_queue_paths()` 逐份解析后合并，🔴 **绝不拼接文本再解析一次**（`_parse_table_rows` 只取第一个 `## 一、`，拼接会静默丢掉第二份的 §一），已配反例单测。⑵ **「通知我有新的」不等于「催我」**——集合不新增即静默，对「一直有活没人开」结构性沉默；**判「该行动没动」用 git，不用 mtime、不用 `-L`／`blame`**（队列行号随增删漂移，那两者会静默给出另一行的历史）。⑶ **算术前提须实测**——按「A 类四行已销号」定的 20，实测销号未执行 ⇒ 当日改定 24；后于 2026-08-20 销号后回落为 **22**（实测值，非预设）。⑷ **常驻执行体可能落后 master 数百提交**——`ZhuopinDecisionReminderDaily` 落后 246 个，其间所有修复均未生效。 ⇒ 全文见 CHANGELOG 同节。
>
> **📦 迁移批次内容指针**：各批条目名与**原文原样**均在 `1-转型规划/0-全景路线图/进度编年-CHANGELOG.md` 对应批次节（第五批＝SC2 两条，因无承接载体被 J1 拦于第四批之外、补立 §一 `#361` 后方迁——J1 首个真实用例）。本段被替换前的原文存档见 CHANGELOG 附录 F。
>
> *注：本项目跨会话记忆以本 CLAUDE.md 当前进度为准（可写、每会话载入）。*
> **🔴 memory 层两桌不同命（2026-08-29 Shao Peishen 改判 §四 #135；2026-08-21 OP-0821-B 的判死结论在 Desktop/Cowork 侧不变）**：**⑴ Desktop/Cowork 侧＝判死照旧**——**完全忽略：不读、不写、不引用**，容器内文件不删不并（MSIX 双树＝写侧落真路径、注入侧读包容器，两边永不相交）。**⑵ CC 侧 auto-memory＝2026-08-29 起启用，定位「技巧笔记层」**（真实 `~/.claude/projects/<cwd 编码>/memory/`，CC 直接读写；Cowork 沙箱 HOME 在容器内读不到 ⇒ 天生单桌）。🔴 **边界三条**：① **只记**工具技巧／环境坑／Shao Peishen 偏好表述；② **纪律口径判据一律不入**——**跨会话纪律的权威载体仍只有本 CLAUDE.md 与两份队列**，memory **不是**第四份权威载体，chat 个人层 `/areas/zhuopin-*` 同禁（两桌都读不到）；③ `MEMORY.md` 索引守 **≤200 行 / 25 KB**。
> 🔑 **①与②的判别只问一句「违反了会怎样」**：**违反会让人做错事** ⇒ 纪律口径，不入 memory；**不知道只是多走弯路、不会做错** ⇒ 技巧，可入。⇒ 判死实测与归因勘误见 `1-转型规划/0-全景路线图/构建环境自动纠错与上下文治理-方案-2026-08-28.md` §一 ＋ 同目录 `memory索引收割对账-2026-08-21.md`；旧路径桶 26 件三分类见同目录 `auto-memory旧桶收割对账-2026-08-29.md`。
> 🔑 **该次勘误留下的通用判据**：**凡「已复核／已回读／已逐字比对」类自陈，必须同时写出用什么核的（工具名／命令／哈希值）；只有动作、没有手段的验证声明，等于没有验证。**

---

## 1. 公司与项目背景

- **公司**：卓品智能科技股份 — 汽车 ECU 设计研发制造 Tier 1，直供比亚迪 / 上汽 / 理想等 OEM。
- **本项目**：18 个月企业 AI 转型（2026-07 启动），六部门并行（采购/财务/质量/销售/运营/工程研发），共 **35 个数字员工场景**（质量域实际在建只剩 Q2／Q4，Q6 已交付＝QD-B）。🔴 **编号 Q1／Q3／Q5／Q7／Q8 已空置、不得重新分配**（2026-08-21 v7 下架，避免同一编号在 git 历史中指向两个不同场景）；下架场景**历史只靠 git 保留**（不并入 backlog、不建暂缓清单、不设复活条件），**复苏由 Shao Peishen 手动触发**。 ⇒ 四次场景数变动（38→40→42→40→35）的沿革与 v7 下架决策全文见全景规划 §0.2 2026-08-21 行。
- **决策人**：**Shao Peishen**（分管供应链与质量的 OPVP，CS + 供应链背景）。技术决策由其拍板。**称呼纪律（2026-07-30 定，全局）**：一律称 `Shao Peishen`，不用 `Paul`——成因是 `Paul` 同时是 Windows 账户名（路径 `C:\Users\Paul Shao\...`）、英文名与决策人代称，三重含义混用（同《专线opener模板库》§〇.2「已有专属含义的词不得表达第二种含义」）。**🔴 绝不替换路径里的 `Paul Shao`**（改了路径即失效）；**历史记录不追改**——队列已完成行/归档件/进度编年/既往报告与 openspec design 里的 `Paul` 指同一人，保持原样。
- 🔴 **人的属性（姓名／性别／职务／部门）＝ 硬事实，正本 ＝ `6-人才与组织/人员名录-称谓与性别-正本.md`（全员 21 人，无一「未确认」）**：**提到任何一位具名人物前先读正本**；本文件不留第二份名录（复制即漂移）。企微 chatid／全员账号表／部门→群映射见 `6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md`《企微 chatid 名录》。
  🔴 **禁从名字推断**——`祖怡`／`燕萍`／`映桦`／`植雅`／`易水`／`姣龙`／`国庆` 七名已实际致错 ≥6 次（`财务部#14` 因 `姣龙` 写「他」翻车、信发出撤不回）：**字面观感与真实性别的对应接近随机**；正本之外的新人物一律用「该专员／其／对方」中性表述并当场问一次，**不得二选一猜**。
  🔑 **举一反三**：凡属「人的属性」——性别、职务、称谓、汇报关系、审批权限——**一律以权威载体为准；载体里没有就问一次并当场落档**，绝不从名字用字、职位名或上下文语气推断。**判别特征＝「能从字面猜出来、且猜错了不会当场报错」**，与「工具静默回退」同族——**错误不产生任何信号**。
  🔴 **读到规则 ≠ 执行规则**——落点是**起草完成后扫一遍全文第三人称代词、逐个回正本核对**（可执行判据见跟进信 README《起草期自检》节）。
- **节奏原则**：先跑通最小验证，再规模化；先 mock/脱敏，再切真实库。

## 2. 全景目标与时间线（指针）

- 权威总纲：`1-转型规划/0-全景路线图/卓品智能AI转型全景规划.md`（2026-06-13 起：正文可修正，但**必须**在其 §0.2 修订记录登记，否则视为无效修改）。
- 最新时间线 + Phase 1 修正：`1-转型规划/0-全景路线图/卓品智能AI转型实施计划（最新版）.md` 第七节。
- **U9C 已覆盖的标准功能直接用，不建 AI**；AI 只做 U9C 不覆盖或需智能增强的场景。
- Phase 1（→2026-07 底）真正能上线的只有 **SC1**（供应商风险初筛）与 **SC8**（客户订单交期智能承诺，**收割式 MVP**，7-8 月上线 — 复用 supplychain 已验证引擎，不从零搭）；其余场景被 U9C MCP（7/1 申请）/外部 API/知识库三类依赖阻塞，先在底座上做 mock 原型。
- **阶段框架（正本＝全景规划 §0.1，2026-06-13 定稿）**：当前 18 个月（2026-07 → 2027-12）＝ **Phase 1**，内分 **S1 筑基（2026-07~12）／S2 扩面（2027-01~06）／S3 深化（2027-07~12）**，月度节奏 M1/M2/M3（"第N阶段"称谓废止）；**Phase 2 ＝ 产品工程跃升期（月 19-24 / 2028 H1）**——产品工程深化候选**统一 Phase-1 末评估立项、不并入 Phase 1、不打乱其排期**，候选清单见全景规划 "Phase 2" 章节 ＋ `1-转型规划/0-全景路线图/AI候选场景增补-backlog（产品工程方向）.md`。⚠️ **场景数与 S3 性质不在本行留副本**（正本＝全景规划 §加速启动总览排期表 ＋ §0.2，沿革见其 2026-08-21 行）。

## 3. 仓库结构

~~~
企业AI转型/                         # 本仓库（GitHub: Raytheoner/zhuopin-ai-transformation）
├── 0-学习与工具/                   # 学习路径、U9C申请、衔接指南、md转Word工具（实施计划/规划审查已迁 0-全景路线图/）
├── 1-转型规划/                     # 各域转型规划、就绪、口径、专线接力/prompt
│   └── 0-全景路线图/               # ★全景规划及构建路线图档单一归集：全景规划(权威)+实施计划+甘特+前置总表+S1复盘+Phase1架构+收割策略+backlog+待决策+全盘审计+规划审查+路线图线接力/prompt；机制见《全景路线图重组机制与变更日志》
├── 2-试点项目/                     # 从采购部启动（权威路线图）
├── 3-治理与合规/                   # IATF/ISO26262/OEM隔离规范、错误回滚SOP
├── 4-数字员工/部门/场景名/          # 各场景独立 Python 工程，import 平台底座包
├── 5-平台底座/zhuopin_platform/    # 可安装 Python 包（pip install -e 可选，见 §4/队列 #300）
└── 6-人才与组织/                   # AIOps 岗位说明书、面试打分卡、招聘话术
~~~

## 4. 平台底座架构（zhuopin_platform）

🔴 **动 `5-平台底座/` 之前，先读 `5-平台底座/CLAUDE.md`** —— 子系统表／OEM 隔离边界（含质量域扩展）／context7 第三方库文档查询均在那里。

## 5. 工作流（OpenSpec + SuperPowers + Hermes，不跳步）

- **会话接力（Paul 2026-06-25 定，固定方式；**E 类 2026-08-09 拆分**）**：本项目**每次新开 session 都用「读上下文文件」交接，不靠粘贴长 prompt**。开场读 ① 本 `CLAUDE.md`（当前进度）→ ② `1-转型规划/0-全景路线图/session接力-Phase1收口.md`（【下一会话主攻】+ 状态快照）→ ③ 全景规划 / 实施计划第七节（权威）恢复上下文，开干前问 2-3 个澄清。**收工纪律**：把本次进展 + 下一步**滚动更新进 `session接力-Phase1收口.md`**（覆盖旧版、标日期），使下一会话读完即接上。
- **🔴 CC 复命零粘贴（Shao Peishen 2026-08-14 拍板 (a)，两桌全局；本条只管 CC→Cowork 这一棒）**：**Shao Peishen 不再需要把 CC 的收工报告复制粘贴回 Cowork。** 他只需在 Cowork 说一句「**CC 跑完了**」（不必指明是哪条 session、也不必记得哪条 CC 归哪条线），Cowork 即自行取件——**三条互相独立的信源，缺一不可**：① **CC 会话原文**＝`C:\Users\Paul Shao\.claude\projects\<路径编码>\*.jsonl`，逐行 `ConvertFrom-Json` 取 `type=assistant` 的 `message.content[].text`，**读到的是 CC 的原话全文**；② **队列行**（CC 收工应已回写）；③ **`git log` + `git rev-list --count origin/master..master`** 核实其自称的提交确已 push。**三者不一致时以队列与 git 为准，transcript 只作补全与追因。** 🔴 **三条边界须一并记住**：⑴ 这是 Claude Code 的**内部存储格式、非公开契约**，**版本升级可能变；一旦解析不出，立即退回粘贴，不得猜**；⑵ **只能读、不能反向发**——Cowork→CC 方向仍由他粘一句开场词（本条上方「开场词与 prompt 纪律」已保证那只是一句）；⑶ **目录名编码把中文吃掉**（`企业AI转型` → `---AI--`），任何「2 汉字＋AI＋2 汉字」的路径都会撞同名，**必须用 mtime ＋ 内容二次确认，不得只认目录名**。 **取件算法（时间窗全取／逐条归属／读 `派出线:` 只收本线／必须回报读到了哪几条）、三类兜底、「线 vs session」术语与别名表、`派出线:` 字段为何不能复用 `来源:`、以及本条的成因与取证**，见 `1-转型规划/0-全景路线图/专线opener模板库.md` §〇.15。
- **开场词与 prompt 纪律（Paul 2026-07-06／07-08 定）**：凡产出交接/开场 prompt 文件，必须内置**「开场词（复制即用）」**——单句、含目标文件完整路径，复制粘贴即可开新 session；聊天回复同步给出可复制块，不让他自己拼路径。**收工段必带 git 处置**：Cowork 类 prompt 写明「文件清单＋建议 commit message＋一句话交 CC（commit+push+收工重跑台账）」，不留未提交悬置；CC 类本含 commit+push＋收工重跑台账。**呈现格式**：≤500 字直接给完整原文、>500 字落 prompt 文件＋单句开场词引用；无论长短一律放 **fenced 代码块**。opener 十二条细则见 `1-转型规划/0-全景路线图/专线opener模板库.md` §〇。
- **🔴 新场景一律不新起端口（Shao Peishen 2026-07-29 定，硬约束，两桌全局）**：**新增场景不得新起独立端口对外**，一律注册到统一门户路由 `/{域}/{场景}` 下（如 `/procurement/sc7`、`/quality/8d`）并预留网关 auth 接入点（中间件未就绪期可为空壳，但路由与接入点必须留）。**存量三个可慢慢收编，增量必须当天止住**；目标态＝一个门户＋一次企微 OAuth 登录＋各域挂统一路由，**后端保持独立服务不合并进程**（保留故障隔离）。成因（四个平级服务零鉴权绑 `0.0.0.0`、收编成本随场景数线性增长）与完整设计见 `3-治理与合规/统一门户架构决策件-SSO与权限-2026-07-29.md`（待 design 审）。
- **🔴 会话末显式罗列决策项（Shao Peishen 2026-07-31 定，2026-08-02 加格式硬规则、2026-08-03 补齐双向，两桌全局）**：每次回复**末尾**用固定小节「**需你定夺**」+ **编号清单**罗列需其定夺的决策项，每项写清**选项之间的实际差异**（不是只写「要不要做」）+ 各自代价 + 建议；**临期项标日期并置顶**；**同时列出此前提出但尚未答复的悬置项**，不因换话题而消失；无决策项时明写「本次无需你决策」。 **🔴 格式四条——每一项必须是可直接作答的「是非题」或「选择题」，不得是开放式陈述**：① 每项带编号 + 带字母标签的选项 `(a)/(b)/(c)`，或明确写成「是/否」，使他只回一个字母即完成决策；② 每个选项写清**「选它会发生什么」与代价**，不是只写选项名；③ 🔴 **两栏各归各位，任一方向串栏都算违规**——状态另起小节「**状态同步（无需你答）**」；**既不得把纯状态汇报混进「需你定夺」，也不得把需他定夺的事塞进「状态同步」**。判据：**凡出现「等你定／请你选／待你拍板」字样，一律属「需你定夺」，不论它看起来多像顺带一提**；④ 每项标注**「默认项」**（写明「若不答，我将按 (x) 执行」），**使「不答」也成为一种有效且可预期的输入**。 **悬置项同样适用**：跨会话未答复的项**必须以选择题形式重提**，不得只陈述「仍未答复」。与「建议未获答复须再次提醒」是同一诉求的两个方向（那条管**跨会话**不丢，本条管**单次会话内**不漏）；与队列 §四 互为呼应（会话末清单＝当次，§四＝跨会话台账，重要项两处都要有）。 **成因**（长会话里决策点散落各段；2026-08-02 #204 与 2026-08-03 §四#44 两次反向串栏实证，及「单向规则拦不住双向问题」那句教训）见 `1-转型规划/0-全景路线图/进度编年-CHANGELOG.md` 附录 B。
> 🔴 **「默认项」只在两个前提下成立；不成立时不得设默认项（Shao Peishen 2026-08-19 问「所有没答复的定夺项是否还可以都按默认项定夺执行」后补）**——本段约束的是上文格式四条的第 ④ 条：**默认项不是每项都该有，它有前提。**
> **⇒ 判据（写报告方自检，不是让他判断）**：设默认项前问两句——**① 这一项若他不答，谁去执行？②「不答」的代价是「停在原地」还是「错误继续发生」？** **第 ① 问答不出执行者**（提出该项的 session 已收工 ⇒ 回合制无法自我唤醒，「按默认」实为停摆）、**或第 ② 问是后者**（等于用默认项给一个正在出血的口子背书）⇒ **一律不设默认项**，改为显式标注「**本项无默认，须你明确答复**」并登记 §四。**⚠️ 连带**：默认项若「按默认＝继续挂着」，还须查它有没有下游依赖被一起冻住。
> **两个前提的论证与三处实证（§四 #71／#73／#67）见** `1-转型规划/0-全景路线图/进度编年-CHANGELOG.md` **附录 D。**
- **🔴 一次会话产出多个任务时，必须指明「次序」与「能否并行」（Shao Peishen 2026-08-07 定，两桌全局）**：凡一次回复给出 **≥2 个 opener／派单件／可开工任务**，必须附**次序与并行矩阵**，逐项写明：① **能否立即开工**（零依赖／软序／硬阻塞／定时触发型四选一，依赖判断以队列行状态列开头括注自陈为准）；② **能否与哪几项并行**（判据＝触碰区是否重叠，重叠即软序，须串行或同车）；③ **若必须串行，谁先谁后及理由**。**不得只并列列出让他自己推断先后。** 自检一问：*发给没读过本会话的人，能一眼说出先开哪个、哪几个可同时开吗？* 成因见 CHANGELOG 附录 E-2。
- **🔴 输出规范三条（2026-08-21 由 memory 索引层收割而来，OP-0821-B；收割前 grep 实证本文件对这三条全部 0 命中）**：① **凡给出可粘贴的 prompt／指令，必须标注粘贴端** —— `▶ 粘贴端：Cowork` 或 `▶ 粘贴端：CC`，**一次给多条则各自标**。⚠️ 与上文「执行环境标注」**不是一回事**：那条管「opener 标题里这是哪类任务」，本条管「这段文字该粘到哪个窗口」。② **凡需要 Shao Peishen 亲自做的动作 ≥2 个，必须按执行顺序编号，并逐条标注「按序／可并行／可缓」**。⚠️ 与上一条「任务次序与并行矩阵」**也不是一回事**：那条管派出去的任务彼此之间的关系，本条管**他自己要动手的那几件**。③ **路径一律写仓库根相对路径**（🔴 唯一例外＝本机取证命令必须用绝对路径）；**每个问题给 1 个最优建议，不摆一堆等价选项让他挑**——与「需你定夺」的选择题不冲突：那里要给选项，但**必须同时给出推荐项**。
- **决策路由：在哪答（Shao Peishen 2026-08-04 定，2026-08-19 改版，两桌全局）**——**每一条「需你定夺」项都必须标注建议回复位置**：`【总线答】` 或 `【原 session 答】`。**判据（可机械化）**：决策项里出现**别的队列编号（#xxx）／别的线的名字／对外动作（发信·部署·专员）** → **【总线答】**；**只谈本变更包内部实现细节、不牵动他处** → **【原 session 答】**。 **配套动作（总线侧）**：凡走【总线答】的，答复后须①**结论写进对应队列行**（跨会话唯一可信载体）②**附一句「回原 session 收口词」**（含结论摘要 + 只做收工自检四项：产出是否已推送／队列行是否已回写且 ✅ 在状态列开头／§二 批次是否已落库／有无行内遗留需升格），使他的动作压到一次粘贴。**⚠️ 回合制 session 无法自我唤醒**——"结论已写队列"只解决**可见性**，**收口仍需一次输入**，这是机制边界、不是遗漏（见队列 #230 第二形态）。 **旧判据的两侧价值论述与 2026-08-04 三例实证** 见 `1-转型规划/0-全景路线图/进度编年-CHANGELOG.md` 附录 D。
> ⚠️ **2026-08-05 那两条标注规则已被下方 2026-08-19 判据改版整体覆盖并退休**（新体系只有 ⟨就地答⟩ 与「已登记 §N，待总线派发」两态），原文与成因见 CHANGELOG 附录 D。
> 🔴 **判据改版（Shao Peishen 2026-08-19 定，两桌全局）——由「谁提的／session 活没活」改为「答完之后由谁执行」，并取消已收工项的选项本身。**
> **⇒ 新判据（可机械执行，只问一句）**：**这一项答完之后，由谁动手？**
> - **本 session 接着就做** ⇒ **⟨就地答⟩**，正常给 (a)(b)(c) ＋ 默认项。
> - **要另起 session／归他线／对外发送／改他人触碰区** ⇒ **🔴 不给选项**。只写一行「**已登记 §一 #N（或 §四 #N），待总线派发**」＋ 一句结论摘要。**没有选项就没有引力，他不必判断去哪答。**
> **⇒ 报告顶部加一行汇总**（免得逐项扫）：`▶ 本报告 N 项定夺：X 项⟨就地答⟩，Y 项已登记队列待总线派发`。**判定责任在写报告的一方**——写的人知道自己接下来会不会执行，他不知道。
> **本判据的成因、「给了选项本身就是邀请」那句洞察、新旧判据对照实例，以及它已覆盖的那条中间态（「已收工 CC 一律走【总线答】」不另立规则），见** `1-转型规划/0-全景路线图/进度编年-CHANGELOG.md` **附录 D。**
- **建议未获答复须再次提醒（Shao Peishen 2026-07-29 定，两桌全局；**E 类 2026-08-09 拆分**）**：给出建议后若他未明确答复，**而该建议牵动后续动作**，必须**主动再次提醒**——不得当作默认通过，更不得靠一句「建议…」就当已处置。**判据：建议 vs 状态，机制只认后者**——凡建议涉及任务归属/优先级/范围合并/排期变更，要么当场把**状态字段**改到位，要么显式标注「待他确认」并在下次交互重提，不留中间态。**高危形态**＝**在 A 处写「建议并入 B」但 A 的状态没改：读 B 的人以为已并、读 A 的人以为可领，两边都不会发现**。**收工自检**：本次说过的「建议…」里，哪些未获明确答复却已影响他处表述或他人行动？逐条重提。 **成因**（2026-07-29 #151/#152 分段交付实证）见 `1-转型规划/0-全景路线图/进度编年-CHANGELOG.md` 附录 A。
- **执行环境标注（Paul 2026-07-27 定，硬规则）**：凡对外呈现的任务/opener 标题**必须标注 `【Cowork】` 或 `【CC】`**，`【设置】` 行同步写 `执行环境：Cowork/CC`。**判别**：只产改 `.md`、不写生产码、不自行 commit＝**Cowork**；写跑代码／连真实库与 `.51`／测试部署／自行 commit+push／一任务一 worktree＝**CC**；只读取证仍属 Cowork，**一旦改代码或触发服务动作即转 CC**。🔴 **中间地带：改本机工具链＝CC**（Shao Peishen 2026-08-02 定；全局 npm/插件/CLI 安装升级、`openspec update` 类会重写生成物的命令）；**Cowork 仅紧急且经其明示授权时破例**，破例须①先固化升级前证据②逐文件过目 diff③事后如实登记。⚠️ **「已获授权」≠「该照原方案执行」**——动手前取证若推翻方案，正确动作是回报改判、另立行。 ⇒ 细则与落点见 `1-转型规划/0-全景路线图/专线opener模板库.md` §〇，原文与成因见 CHANGELOG 附录 G-1／附录 A。
- **跨桌任务队列纪律（Paul 2026-07-09 定，两桌强制）**：`1-转型规划/0-全景路线图/跨桌任务队列.md`（现拆机制环境／业务场景两份真身，共用一把锁）是两桌任务流转的**唯一载体**——所有 session **开工必读**（认领本线待领任务＋登记触碰区）、**收工必写**（状态＋产出路径＋新冒出的下游任务当场追行）；**触碰区与他人在办重叠不得抢领**，报总线裁决；**commit 由落库 sweep 自动从 §二「待 commit 批次」取活销行**（一批一行）——🔴 **登记完 §二 即完事，不需要「一句话交 CC」**，CC 仅在 sweep 不可用时兜底。**2026-09-02 实测**：`ZhuopinCommitSweep` State=Ready／LastTaskResult=0／约每 27 分钟一轮，最近 8 批**全部**由 sweep 销号，本线 `B-0902_18` 登记后约 2 分钟即销。⚠️ **旧表述「commit 一律由 CC 取活销行」已与事实不符，2026-09-02 据实测改**——它曾让本线在收工段写出「交 CC 一句话」这种既多余又答不上「交哪个 CC」的指令（他当场指出）。**§5「开场词与 prompt 纪律」里那句「一句话交 CC」只适用于产出 opener/交接 prompt 文件的场景，不适用于本 session 自己登记 §二 批次。** 　**§三 口径冻结标**挂标即停该场景在途建造。🔑 **编辑锁／每周清扫与高水位线／并入审核与可动 WIP 等全部细则以队列顶部「协议〇」为正本**，此处不复述（复述即漂移）。**值周巡检**每周一 10:00 读队列出《本周计划》，开跑前先跑对账审计（skill `zhuopin-queue-audit`）；**gap 收口纪律（Paul 2026-07-22 定）**：设计↔执行 gap 须驱动到**有主·有截止·已派单**的收口路径后计划才往下走，不把未解决 gap 埋进计划当普通行。
- **机制优先大原则（Paul 2026-07-24 定，两桌全局把关；**E 类 2026-08-09 拆出**）**：**能等的交给机制**（对账审计/sweep/值周巡检按流程修复——机制修复自带证据链与留痕，且每次运行都是对机制本身的真实检验）；**不能等的**（紧急/阻塞/破坏风险）**用机制的方式立即做**（编辑锁、批次登记、队列留痕，不裸手改）。Cowork/CC 所有 session 以此把关，**发现绕开机制的裸改（含自己）应拦下提醒**；实证依据＝2026-07-24 三连误弃事故（人工手快并发编辑是事故温床）与 #68 过时字样留审计自修的对照。
- **环境保障线：派单边界与交付形态（Shao Peishen 2026-08-02／08-03 定）**：对象是**构建环境与自动化机制本身**（worktree／编辑锁／sweep／巡检巡逻／队列纪律／openspec 工作流／本机工具链／机器人链路）＝**环境整治**，本线可备派单件协同 CC 执行；对象是**业务场景代码、平台底座功能、真实数据与 `.51` 现网服务**（即便入口是一个「测试失败」）＝**项目构建，交业务总线派发**。本线默认交付形态＝**① 取证与梳理结论 ② 方案定稿 ③ 队列行写入**，分发由值周巡检与拆件巡逻完成、不由本线推动；「备派单件＋请他粘开场词」式直接派活仅限紧急且经其明示授权，并在队列行注明因何绕过机制分发。细则·边界个案·成因见 `1-转型规划/0-全景路线图/开场prompt-【Cowork】环境总线-接力交接-2026-08-08.md` §六bis。
- **规则退休制（Shao Peishen 2026-08-03 定，两桌全局）**：本节与协议〇的纪律分两类——「**机制守**」（有代码/工具/门禁强制执行，**不记得也会被拦**）与「**人守**」（只靠人读过并记住）。**任一「人守」条目被违反 3 次即达阈值，必须二选一**：① **机制化**——挂到不可绕过的咽喉上（队列写入＝协议〇.7 编辑锁 `acquire`/`release`；提交＝落库 sweep），**正文可降为一行指针、不必删**（依据 #206：指针属防御性冗余、非机制必需）；② **删除**（确无价值时）。**违反计数落在队列对应行内，不另建台账**。根问题（规则语料单调增长而注意力预算不变、大规则集催生合理化）、判据的道理与首个清算案例见 CHANGELOG 附录 E-1。

**Cowork（规划治理桌）**：规划/路线图/治理合规/招聘/汇报；**默认只改/出 `.md`，Word 仅在 Paul 明确要求时才用 md-to-word 转**（平时不转）；**不碰真实库、不写生产代码**。**文件链接纪律（Paul 2026-07-07 定）**：凡为 Paul 定位或产出文件，一律附**可达文件链接**（present_files 文件卡片，点击即开），不只写路径文本。　**定位＝项目总架构师**（守全景／把记忆落成文件／调度 CC），非执行工。
- **Claude Code Desktop（建造车间）**：写并运行场景代码、连真实 SRM/ERP、跑真实数据、收割 supplychain；**不改规划文档**。
- **同步纪律**：开工先跑 `git fsck --connectivity-only`（对象库健康哨兵）再 `git pull`；收工 `git push`（GitHub＝权威备份）；**同一文件别两边同时改**。**fsck 报错即停**，勿 pull/push，报 Shao Peishen 走恢复流程——**先把工作区未 commit 改动手工备份到仓库外**，再重 clone，最后拷回未提交件与 `.env`/reports 等 gitignore 件（防重 clone 吞成果）。**OneDrive 惯例（2026-07-07 更正）**：平时全关、每周手动开一次作纯离线备份；gitignore 件备份新鲜度按**最多一周旧**评估，当周有重要新件可提前加跑——**不是「不可长关」**。排查「文件像是变旧了」的顺序见 `0-学习与工具/取证方法知识库.md` §三.1。
- **🔴 乱码文件夹哨兵（2026-07-04 二次事故后强制；**E 类 2026-08-09 拆出独立成条**）**：CC 开工与收工**各查一次上级目录**——`Projects\` 下 `*AI转*` 目录**应且仅应 1 个**（PowerShell：`Get-ChildItem ..\ -Directory | ? Name -like '*AI转*'`）；出现含 U+FFFD 乱码重名的兄弟文件夹**即停手**，按既例处置（整树移入 `_乱码重复文件夹隔离-日期\` 隔离夹、逐文件哈希比对真项目、**不直删**），并记录当刻哪个工具在写中文路径。**根因指纹（2026-07-04 实证）**：写入端 UTF-8 损坏时**路径与文件内容同现 U+FFFD**（11:42 QD-A 测试文件写入事故，每个汉字变 2 个 U+FFFD）；**CC 写含中文路径的关键文件后，读回抽验一处中文完整性再继续**。
- **🔴 时间戳必判 UTC vs Win 本地（Shao Peishen 2026-07-31 定，2026-08-04／2026-08-15 两次补齐，两桌全局硬规则）**：本机时区＝China Standard Time（**UTC+8**）。**引用任何时刻前，先答一句「这个值是 UTC 还是本地」，并在输出里显式标基准**（如 `09:04:31Z (17:04:31 本地)`）。**各证据源基准并不一致**——`reports/wecom_aibot_audit.jsonl` 与企微机器人告警文案里的时刻是**真 UTC**；文件 mtime／计划任务 `LastRunTime`／Windows 事件日志／`LastBootUpTime` 是**本地**。 🔴 **⑵ 写侧硬规则（2026-08-04 定，2026-08-15 补机器判据；两次补齐的重复表述已于 2026-08-23 合并，判据无一删减）**：凡向**队列行／批次行／`Last Updated`／接力节标题**写入日期，**一律用本机 PowerShell `Get-Date -Format 'yyyy-MM-dd'` 当场重取** —— 不得估算、不得用 UTC 日期、不得写尚未到达的日期、**不得引用本会话早先的取值**；**禁用沙箱 `date`**（与本机可能不同步）。**本条只约束此后写入，已写的按「历史记录不追改」保留不动。** ⇒ **凡文本里出现可反推当前日期的相对表述（窗口、天数差、到期），应顺手做一次换算校验。** **成因（为何是硬规则）、两次补齐的实证（08-04 五处日期写错／08-15 跨日事故与被漏掉的那条线索）与两个实测陷阱**，见 `0-学习与工具/取证方法知识库.md` §一.2／§一.3。


> **取证方法已迁出（D 类，2026-08-09，队列 #311）**：**同族第二条**「判本机是否重启过只认 `ID=27 Kernel-Boot 引导类型`」（快速启动 hiberboot 会让 `LastBootUpTime`／`6006/6005`／`13/12` 三个直觉判据**全部静默失效**）与**元判据**「判据本身也需要被质疑一次」，正文见 `0-学习与工具/取证方法知识库.md` §一.1／§四.1。
>
> **🔴 同族第三条 · 工具静默回退（D 类 2026-08-09 正文迁出；**本行是硬提示，不得再降**）**：一类工具在参数不符合预期时**不报错**，而是静默回退到一个「看起来合理」的默认行为——返回值完全正常、结论却是反的。 **随身判据**：**当一个只读命令返回了「太干净」或「太正常」的结果，先问它是不是根本没读到我以为的那个对象**，而不是直接采信（坏消息会让人追根因，好消息不会）。已知实例（`[System.IO.File]::*` 相对路径按宿主 CWD 解析／`git -C` 向上找到祖先仓库／PowerShell 变量名大小写不敏感／混合换行符文件）见 `0-学习与工具/取证方法知识库.md` §二；写后反查三件套见 `1-转型规划/0-全景路线图/专线opener模板库.md` §〇.6。
> ⚠️ **原挂此处的 memory 层勘误已退休（2026-08-23）**：现行结论一句——**跨会话纪律一律落本 CLAUDE.md 与两份队列，不落 memory**；判死实测见顶部 memory 段所指两份档。
>
> **直读原则（Paul 2026-07-06 定）**：凡对数据新鲜度敏感的读取（状态页 Artifact 数据层、状态核验、完整性抽验），一律走**本机直读**（Windows-MCP PowerShell 只读 / 桌面侧 Read），不用沙箱挂载副本（有**沙箱文件桥滞后**与尾截断假象，2026-07-07 更正术语——非 OneDrive 本身滞后）；沙箱 bash 仅用于 git 取证、批量 grep 等对滞后不敏感的操作。状态页 Artifact=`zhuopin-project-status`（数据层=本机 PowerShell 只读，严禁 rd/RD 等可变更别名，只许 Get-Content/Test-Path 级 cmdlet 全名）。
- **合并策略 ff-only（2026-07-04 定；**A 类降指针 2026-08-09**）**：PR 一律 **ff-only**，由 `工具-落库sweep.py::_reconcile_with_origin_and_push` 每轮落库强制对齐。零 diff 的 PR（分支已被 ff push 先入）验证 `git log master..branch` 为空后**带说明直接 CLOSE**，不强 push、不 rebase。
- **排期同步纪律（Paul 定，2026-06-19，强制；2026-07-07 补 docx）**：任何业务场景的**实现时间一旦变更**，必须**同步更新全部规划与路线图档**（全景规划场景块＋权威排期表＋四阶段＋甘特指针、实施计划总清单＋时间线＋Phase 2、相关前置数据总表）并**重生成对应 docx**；**零残差、不留旧档**，改完 grep 自检一致。**单一可信源 ＝ 全景规划 §加速启动总览排期表。** 🔴 **docx 重转不限于排期变更**：凡触碰 `全景规划.md` 或 `实施计划（最新版）.md` 正文，**收工前必须**用 `0-学习与工具/md转Word工具/md2word.py` 重转两份 docx 并入同批 commit，不得只改 md 留 docx 滞后。 ⇒ 逐处落点清单与命令用法见 CHANGELOG 附录 G-2。
- **全景路线图重组循环 + 归集地（2026-07-03 定；**A 类降指针 2026-08-09**）**：全景规划及构建路线图相关档统一归集 **`1-转型规划/0-全景路线图/`**（单一归集地）。**分工红线**：域专线出局部定稿+移交单、不直接改全景；全景路线图线执行重排、不重开域业务口径。固定闭环（冻结标→九文档重排→§0.2 登记→grep 全库零残差→回填销号）与每次循环登记，见 skill `zhuopin-rebaseline` ＋ `1-转型规划/0-全景路线图/全景路线图重组机制与变更日志.md`。
- **文档治理六规则（2026-07-07 定，正本＝《文档治理规范与规整执行清单-2026-07-07.md》）**：**R1/R2 已机制守** —— **找文档先查 `0-全景路线图/文档台账-自动生成.md`、不翻目录**（状态头六枚举由 `工具-文档台账生成.py::STATUS_ORDER` 强制，台账重跑并入 sweep；唯 CC 不经 sweep 的直接改档须手动重跑一次）。**R3 生命周期**：已执行即回填 status，每季度**批量**搬 `z-已执行归档/` 并做全库引用清扫，禁止零星搬。**R4 命名四律**：主题-对象-日期-事项／文件名不含会变数字／md·docx 同名为一对／prompt 类统一 `开场prompt-` 前缀。**R5 接力瘦身**：四条 session 接力＝**定长交接卡**——硬上限 8 KB、固定六块、零日期节，收工**覆盖**不追加；进度叙事写 CHANGELOG、方法教训写取证知识库、未闭合项写队列行，迁出守 J1；**已机器守＝J6**。**R6 专员回复归档**：正式材料落 `7-外部文档/<部门>/`，专线只认文件不认转述。 🔴 **「`CLAUDE.md` 多大算超限」已非人守**，由落库 sweep 第 4 类常驻告警承接（判据以 `工具-落库sweep.py::_check_claude_md_carrier_size` 为准）。 ⇒ 原文与沿革见 CHANGELOG 附录 G-3，R5 旧版为何失效见队列 §四 #80。
- **企微同步推送（**A 类降指针 2026-08-09**）**：**分工＝Cowork 写 `.md` 正文 → 对 CC 说一句「把 X.md 发企微」即发**——Cowork 云端沙箱出网受限（实测 qyapi.weixin.qq.com 403）发不出去。用法与凭据见 `0-学习与工具/发企微.py`（纯标准库，读本项目 `.env` 的 `WECOM_WEBHOOK_URL`，走公网 HTTPS，off-LAN 亦可）；底座另有 `shared_tools/notifiers/wecom.send_markdown`。
- **专员跟进纪律（Paul 2026-07-04 定，新 session 一律遵守）**：跟进信归集 `6-人才与组织/部门AI专员跟进/`，命名 `部门-姓名-跟进-YYYY-MM-DD-主要事项.md`，每封必含三要素**做什么/怎么做/什么时候交**，发一封在 README 清单追加一行。**口径/需求确认唯一格式＝判例批改法（Paul 2026-07-25 拍板，全域生效）**——禁止抽象设问，一律转 ≤10 条**真实**案例「现状判定 vs 拟改判定」对照，专员只做 ✅对/❌错/✏️改判＋一句话。**🔴 判据/口径/阈值类永不默认生效**（IATF 显式签认红线；纯展示类可标 48h 默认生效）；**一信决策点无上限**；**不加并行专员**（判定权威单点），人力加「一线标注层」。**编号＝`部门#N`**（跨收信人共用计数器、未发出不占号、已发旧信不改名）。 ⇒ **节奏／配套／成因／细则全文见 `6-人才与组织/CLAUDE.md` §一**，正本＝该目录 README ＋ `需求确认方式升级-判例批改法与微会机制-2026-07-25.md`。
- **🔴 跟进信串行原则（Shao Peishen 2026-08-03 定，两桌全局，**优先于并节制任何触发点规则**）**：**同一收信人同时只能有一封在途跟进信**；下一封的起草前提是**前一封已收到回件且回灌消化完毕**，起草后**提交 Shao Peishen 审核后发出**。🔴 **它优先于任何「某动作完成即触发发信」的规则**（含 §5 场景固定流程第 8 步）：**触发条件满足 ≠ 可以发，还须前一封已闭环。** **判据（可机械化）**：跑 `python 0-学习与工具/工具-跟进闸查询.py --to <收信人>`；未到闭环形态即**不得起草下一封**，改为在队列登记一行「待前信闭环后发」并写明拟发内容要点。 ⇒ 论证与过渡期安排见 `6-人才与组织/CLAUDE.md` §二。
- **🔴 信状态唯一权威 ＝ 跟进信 README 的「发送状态」列（Shao Peishen 2026-08-21 答 §四 #85 选 (b)，两桌全局）**：**跨桌任务队列不是信状态的载体**——队列行里「等某某#N 闭环／待回件／闸锁着」类**复述**一律是会过时的快照，**不得作为判据**，队列只允许写指针。**判闸唯一入口**＝`工具-跟进闸查询.py --to <收信人>`。 ⇒ 成因（机器只写队列、闸只读 README，中间那步是人 ⇒ 闸永远不会自己开）与「合并成一个文件已被实测否掉」论证见 `6-人才与组织/CLAUDE.md` §三；设计正本 `1-转型规划/0-全景路线图/跟进信状态单一可信源-架构设计-2026-08-21.md`，机制行 §一 `#366`。
- **完工即归档纪律（2026-07-02 定，强制）**：变更包的所有 tasks 全 [x] 后，**当场**跑 `/opsx:archive <change-name> -y`，不拖到"下次 session 再归档"。归档完成才算该变更包完工。理由：拖延归档是 SDD 流程最常见的单一可信源漂移根因（本次 hygiene 专项就是为收口这一问题）。**不允许"代码完成但变更包未归档"的中间态持续超过 1 个工作 session**。🔴 **这次不归档时，理由必须写在机器认得的地方**（`暂不归档`／`预期观察窗口：N 天`／`--ack-stale-change`，三选一）——写在 tasks 行内不算，sweep 读不到会照报「疑似遗忘归档」；三条入口的用法、成因（2026-08-23 那轮 4 报 3 误）与已撤销的「archive 不写进 tasks」见 `1-转型规划/0-全景路线图/专线opener模板库.md` §〇.16，判定器＝`0-学习与工具/工具-变更包自动归档.py`（只判定、不归档）。
- **发布即收口纪律（Paul 2026-07-19 定，选项①拍板）**：CC 建造模块的**收口标准 ＝「具备发布条件的最小 MVP 已部署到 `.51` 且部署段基本测试通过」，不是「代码跑通」即完**。**四关**：① **功能门槛**——全量测试绿＋零回归＋黄金基准不漂移＋openspec 归档＋场景 CLAUDE.md 更新；② **部署段**——真部署 `.51`＋冒烟（`/api/ping`·关键页 200·一次全量重算）＋回滚 SOP 在位＋**可常驻**（守护/自愈，非从临时 worktree 跑一次）；③ **合规不放松**——两道门禁（只归档/通知不自动执行、L2 人工确认，见 §7）照旧，「发布」＝部署供试用/反馈，**≠ 放开 AI 自动执行业务**；④ **先灰度后依赖**——试用＋反馈入口先行，价值兑现后再谈生产依赖。**部门成员统一入口 ＝ AI 运营指挥中心**（`1-转型规划/AI运营指挥中心/`）。 ⇒ 原文与成因见 CHANGELOG 附录 G-4，全景总纲 §0.2 已登记（2026-07-19）。
- **外部对抗性评审纪律（Paul 2026-07-02 定）**：⏰ **2026-11 中旬前须主动提醒 Shao Peishen 排 S1 收口外部评审**（S2 ≈2027-05 中旬／S3 ≈2027-11 中旬）；细则与冷备架构师接手演练见 `1-转型规划/0-全景路线图/CLAUDE.md`。
- **决策代理（Paul 2026-07-05 定，Unknowns U6）**：Paul 缺席时由**孙涛**代理拍板——**可代**：design 审查、批间 Triage、L2 日常审批；**不可代**：对客外发开闸（CUSTOMER_OUTBOUND_ENABLED）、预算变更、合规红线变更（等 Paul 返回或升级 CEO）。CC 侧 `VP_APPROVERS` 配置须加入孙涛（待办，随下一次 CC session）。
- **机制/工具类模块的 openspec 触发门槛（Shao Peishen 2026-07-31 定，硬规则）**：「每个场景固定流程」只约束业务场景，**不覆盖平台底座与机制/工具类模块**（2026-07-31 取证坐实断层：七个机制模块 openspec 全库 0 命中，明细见 CHANGELOG 附录 E-3）。**命中以下任一即必走 openspec（含 design 审）**：① **改变全项目口径**（取号／编号／判据／状态语义等跨场景约定）；② **涉鉴权与数据可见性**（谁能看到什么）；③ **改变既有模块对外语义**（同一接口相同输入行为变了）。**不走**：纯 bugfix、告警文案、日志措辞、单测补充、纯文档清理。**判不准就走**——design 审成本约半天，而三类无 spec 在 IATF「单一可信源/可追溯」审核下站不住。
- **每个场景固定流程**：
  🔴 **第 1-7 步正文已下沉：动 `4-数字员工/` 下任何场景之前，先读 `4-数字员工/CLAUDE.md`**（含 scaffold 引导样板与 `.51` 发布收口）。**第 8 步不下沉，全文如下：**
  8. **发布即刻起草跟进信（Shao Peishen 2026-07-31 定，全局规定动作，紧跟第 7 步；🔴 本步不得省略）**：🔴 **先查串行闸，再决定起不起草**（2026-08-20 答 §四 #74 选 (a) 改定）——判据＝`工具-跟进闸查询.py --to <收信人>`（或直读跟进信 README 该收信人最近一封的发送状态列是否已到闭环形态 `📥 已回件并回灌`／`✅ 无需回复`／`📨 已确认闭环`）：**⑴ 闸开 ⇒ 当场起草**，README 登记行「发送状态」列**只写 `⏳ 待你审`**（唯一合法起草产物，不得直接写终态）；**⑵ 🔴 闸锁 ⇒ 不起草**，改为在队列对应行**登记「待前信闭环后发」并写明拟发内容要点**；**⑶ 已起草者提交 Shao Peishen 审核，批准后方可发送**。
     🔴 **发送硬前置（Shao Peishen 2026-08-03 定 (a)，两桌全局）——「部署冒烟通过」是发信的前置条件，不是并列步骤**：起草、送审可先做，**发送必须等三条判据全过、缺一即不得发**：① 改动已 ff 合入 `master`（`git rev-list --count master..<分支>` ＝ 0）；② `.51` 已部署且冒烟通过（`/api/ping`／关键页 200／一次全量重算）；③ **用专员原始举证的那个真实案例做端到端复现**——看板/页面须显示修正后的值。**本条与「跟进信串行原则」并列适用**——串行管前一封是否闭环，本条管这一封是否已上线，**两条都过才发**。机制侧强制见队列 #229。
     ⇒ **两态语义、批准脚本、`🔒人工发送` 硬截止标记、「为什么必须先查闸」与发送硬前置成因的完整辨析**：见 `6-人才与组织/CLAUDE.md` §四 ＋ 跟进信 README「第 8 步串行闸辨析」节。

## 6. supplychain 收割策略（指针）

- 收割已完成、源仓库已打 git tag 转只读存档；策略与模块迁移表见 `1-转型规划/0-全景路线图/supplychain收割与全景推进策略.md`。

## 7. 合规红线（建造时守住，IATF 16949 / ISO 26262）

1. **先 mock/脱敏跑通逻辑，再切真实库。**
2. **所有 AI 决策写平台 `audit`**（append-only，3 年留存，可追溯）。
3. **OEM 数据隔离**：涉 OEM 技术数据按客户路由、禁跨库（研发/知识库 + 质量域 PPAP/FMEA/含 OEM 信息的 8D 客诉，见 §4 边界扩展）。
4. **L2 人工确认门禁**：采购金额 > 50 万、新供应商、交付预测推客户 —— 必须人工确认，不可自动执行。
5. **ISO 26262 安全相关**：AI 生成不得直接合入，须人工审核（R3 等）。**ASIL C/D = AI 绝对禁区**（LLM 过不了 TCL 工具资质，禁止 AI 参与 C/D 自动修改/最终判定、不进安全证据链，FSE 双签）；ASIL A/B 可 AI 辅助+资质人员签字。详见 `3-治理与合规/ISO26262-AI安全使用规范（草案）.md`。

---
**Last Updated**: 2026-08-29　🔴 **本行只写日期与一行指针，不写进度叙事（2026-08-22 OP0822A 定）** —— 历史原文见 `1-转型规划/0-全景路线图/进度编年-CHANGELOG.md` §「附录 · Last Updated 链历史」。

维护：本文件随架构/红线变更更新，时间线细节以实施计划第七节为准。

```

## 【附录 I · 跨桌任务队列 协议〇 去 provenance（K4）前全文存档 —— 2026-09-04（Cowork 环境总线瘦身线，方案＝跨桌任务队列瘦身-方案-2026-09-04.md §二 K4）】

> 承接载体（J1）：本附录承接 2026-09-04 从 `跨桌任务队列-机制环境.md` 顶部「协议〇」迁出的全部成因／沿革／实证文字。新版协议〇（十一条判据版）留在队列顶部为正本；本附录为原文唯一来源，原文原样、可 grep（存档对象＝迁出前一刻的协议〇全文，45,854 B）。

~~~markdown
## 〇、协议（八条，所有 session 遵守）

1. **开工**：读本文件 → 认领属于本线的"待领"任务 → 状态改"在办" + 在"触碰区"列登记本次要动的文件/目录。**认领先于动手（Paul 2026-07-24 定，治理批入法）**：在办行登记（含触碰区）必须发生在任何实质工作开始**之前**；登记前先按触碰区关键词（文件路径/场景号/专员姓名）全文检索本文件与归档件，命中他人在办行或同主题待领行即并入或报 §四 裁决，严禁另起炉灶造成重复劳动（07-23 两份重复跟进信草稿即此类事故）。**认领即预登记批次（队列 #236(1)，2026-08-06 落地，openspec 变更包 `queue-claim-time-batch-preregistration`）**：认领的同一步，在 §二 登记一条预登记批次行——文件清单只需写清任务涉及的场景目录/功能范围（粗粒度即可，不要求预判每个具体文件），状态列固定文案"在办（预登记，收工时精确化）"（该文案既不含"待"也不含"✅"，sweep 天然不会把它当"待处理"去 add+commit，是有意为之的合法状态，不是误写——见协议〇.7 编辑锁⑤校验已放行该前缀）；收工时回到这一行做精确化（文件清单补全、写实际 commit message、状态改真正的完成态），**不新增第二行**。**为什么**：session 是回合制的，"收工登记"这个动作依赖 session 还活着才能执行——一旦中途失联（人转去开下一个任务/客户端重启），这个动作永远不会发生，其触碰的文件就成了没人认领的孤儿（2026-08-04 真实事故：4 个孤儿文件挡住 20 个批次跨天不落库，详见 #236）。把登记锚点从"收工"（不保证发生）移到"认领"（发生在实质工作之前，此时 session 一定还有回合），使中途失联也留下可追溯记录。**抢不到编辑锁时**：预登记内容按第 7 条既有降级路径处理（先记入自己域接力文件顶部「⏳ 队列更新待补」节，回补时再精确登记），不新造一套语义。
2. **防撞**：要动的触碰区与他人"在办"行重叠 → **不领**，写入 §四 报 Paul/总线裁决。域口径重梳期间对应场景挂 §三 冻结标，CC 见标即停该场景在途建造。
3. **收工**：状态改"待验收/完成" + 产出路径写入；本次冒出的下游任务**当场追加**为"待领"行（写明领取方）——这替代"Paul 转述"。**若开工时已按第 1 条预登记了 §二 批次行（队列 #236(1)）**：收工时回到那一行做精确化（文件清单补全为实际改动集合、建议 message 写实际 commit message、状态改为规范完成态如"待处理"/"✅ 已完成（CC 直接提交，未走 sweep）"），**不额外新增一行**——预登记行本身就是这次收工要精确化的对象。**（队列 #314②同车顺带，2026-08-09 补，凡本次改过本文件、走过第 7 条 acquire 的场合适用）**：报"收工"前必须确认第 7 条编辑锁已释放——跑 `python 0-学习与工具/工具-共享文档编辑锁.py status` 确认输出为"（无锁，可直接编辑）"；仍显示占用中则立即补 `release` 或如实登记未释放原因，不得带锁报收工。**复用第 7 条既有 `status` 子命令，不新增机制/不新增 sweep 告警**——2026-08-09 一天内两次"已报收工而锁未释放"（G3、G8），均让下一个 session 白等一轮，成因是人守遗忘、不是缺检测工具，故落点是补一步自检动作而非造一个新守卫。
4. **commit**：Cowork 不 commit；待提交批次登记 §二，由 CC 统一取活销行（一批一行，杜绝同一 merge 两处发起）。CC commit 后销行 + 收工重跑台账。
5. **分支/worktree（CC 侧强制，2026-07-16 入法）**：一任务一分支一 worktree；认领时把**分支/worktree 名写进触碰区列**；开工三查——`git worktree list` + `git branch --show-current` + 队列在办行比对，不匹配即停、报 §四；**完工即推送**——任务行改"待验收/完成"前必须 push（feature 分支推 origin；文档批走 `git push <sha>:refs/heads/master` 并**同步本地 master 指针**，两步缺一不可）；ahead=0 的废弃 worktree 由 CC 收工时清理（🔴 **2026-08-13 起禁用 `git worktree remove`，改用 PowerShell `Remove-Item -Recurse -Force` ＋ `git worktree prune`**，详见本条下方「收工自删」段与队列 #267）；严禁在他人在办分支/worktree 上做无关改动。**Paul 开 CC session 的 UI 选择口诀（07-16 补）**：看队列行"触碰区"列——写了分支名 → 分支选择器选该分支、**不勾 worktree**（续在办活，在途改动在主工作区）；没写分支的全新独立建造 → master + **勾 worktree**（新活新支）；拿不准就不勾，让 session 开工三查自行核对后报告。**固定结论制（Paul 2026-07-17 定）**：凡总线/专线/skill 交给 Paul 的开场词，上方必附一行 `【设置】分支：<名> ｜ worktree：☑/☐`——判断由出口令方完成，Paul 照抄零判断。**（执行环境标注，Paul 2026-07-27 定，硬规则——格式以 CLAUDE.md §5「执行环境标注」为准，勿另造）**：`【设置】` 行须同时写 `执行环境：Cowork/CC`，任务名/opener 标题处同步标 `【Cowork】` 或 `【CC】`（两处冗余：标题供扫读挑活、设置行随 opener 复制进新 session）。**聊天内交付口令时同样适用**（Paul 07-27 傍晚再次强调）：一次给多条口令**每条各自标注**，不得只在开头说一句"以下都发 CC"；同批分属两端时按端分组并在组标题注明。判别口径与四处落点见 CLAUDE.md §5 与 `专线opener模板库.md` §〇（规则真身，本条只作指针）。**⚠️ 07-27 教训**：本条曾被 CC 环境保障线以 `▶ 粘贴端：` 另起一套格式重复入法，随即发现同日早些时候已由值周巡检线按 `【Cowork】/【CC】` 落定——已改回对齐，**同一规则不得存两套格式**（多写一处指针，胜过多造一套约定）。**（含 CC 落库/commit 口令，Paul 2026-07-19 补）**：落库/提交类口令同样必附【设置】行；落库改动通常已在**主工作区**，默认 `分支：master ｜ worktree：☐`——**切勿为落库单开新 worktree**，否则新 worktree 看不到主工作区里未提交的改动、提交会落空。**收工自删 worktree（#68① 提前入法，2026-07-24；🔴 2026-08-13 按队列 #267 实测证据改写删除手法与前提，旧写法已作废）**：任务行改“待验收/完成”且 push 完成后，本任务专用 worktree 若 ahead=0 且工作树 clean，收工时一并清理——**但须同时满足以下三条，缺一不删**：⑴ 🔴 **禁用 `git worktree remove`**，一律用 PowerShell `Remove-Item -Recurse -Force` ＋ `git worktree prune`；⑵ 🔴 **不得删除本会话自身正锚定的那个 worktree**（必失败，且失败非原子）；⑶ 删前先 `Get-CimInstance Win32_Process` 核查目录是否被在跑进程占用，并跑一次 `python 0-学习与工具/工具-孤儿worktree扫描.py` 确认该 worktree 不落在**第三桶**（tracked 干净但存在非空 gitignore 内容——删它会永久销毁不在 git 里的文件）。 ⚠️ **旧口径「删不净只剩空壳、零数据风险」已于 2026-08-13 被实测证伪、不得再援引**：`git worktree remove` 报 `Permission denied` 之前**已删除 `commondir` 与 5 个真实文件**（#267／#308 各复现一次）。删不净的物理空壳仍按原办法保留并在队列行注明待 Paul 手删。
6. **共享文件漂移检测（CC 侧强制，2026-07-17 入法，2026-07-17 事故后补）**：第 5 条的"开工三查"能查出"分支/worktree 对不对"，但查不出"这个分支上的本文件内容是否已相对 master 静默漂移"——2026-07-17 曾出现：某长期分支（`feat/fi2-v3-recon-engine`）多日未同步 origin/master，又被多个 session 顺手拿来编辑本文件，导致它自己的行号续编和 master 主线独立续编撞了号（§一 #31-35、§四 #18-20 两边各自有一套完全不同的真实内容），险些在 push 时把该分支未审的私有提交也带入 master。**开工第四查**：若当前 checkout 分支不是 master 本身、且是存活超过一天的长期分支，动手改本文件前先跑 `git fetch origin && git diff origin/master -- 1-转型规划/0-全景路线图/跨桌任务队列.md`——有输出即说明已漂移，**不得**直接续编号/续写，改走"临时 worktree 拉 origin/master 最新版→编辑/cherry-pick→解决冲突（按内容新旧判断，不盲目全取一边；行号撞号一律在 master 真实最大号之后续排，不覆盖任何一方）→ push"路线。**push 前强制核验**：改动若在非 master 分支的 checkout 上做、准备推去 master，先跑 `git merge-base --is-ancestor origin/master <commit-sha>`；不是祖先关系时**严禁** `git push <sha>:refs/heads/master`，一律改走上述临时 worktree cherry-pick 路线。
7. **本文件编辑锁（Paul 2026-07-23 定，2026-07-23 两次撞号事故后补）**：第 6 条查的是”跨分支/跨 git 历史”的漂移，查不出”同一时段两个 session 各自在本地未提交的工作副本里直接改本文件、后写的静默覆盖先写的”——2026-07-23 当天先后撞了两次：financial 与 QD-B 两条线不知情各自把 #79 用掉；随后采购专线一次会话编辑期间，工作副本被另一处 `git stash` 重置，它没感知到、继续用内存里的旧内容写回，把自己刚追加的”已完成”实质内容变成了占位符覆盖，靠 CC 收工时手工逐行比对 git 历史才救回。**改本文件前**（无论 Cowork 还是 CC）：`python 0-学习与工具/工具-共享文档编辑锁.py acquire --who “<身份，如 CC-QD-B / Cowork-财务专线>” --note “<一句话原因>”`——返回非 0（占用中）**不得**继续改本文件，把要登记的内容先写进自己的域接力文件、注明”队列更新待补”，等锁解除或下次开工再回补；返回 0 才能改，**改完立刻**跑 `release`（持锁窗口只包住”读入→改→写出”这一小段，不跨整个 session 持有）。锁是协作性质而非硬互斥（本地文件，30 分钟无释放视为陈旧自动可接管，见工具内说明），解决不了”内容该怎么合并”，但能让”两边都在写”从静默覆盖变成后来者主动让步，不再需要人工事后修复。**（2026-07-27 补，#121(a)(c)/#97 同车修法，CC 环境保障线执行）**：① **编号一律在持锁后重算**——编号是在 acquire **之前**读队列算出来的，若仍用锁前读到的旧值续排，即便锁保护了”写”这一小段，仍会撞号（07-27 同日两次撞号即因此，见 #121(c)）；`acquire` 成功时会回显**持锁瞬间**实读的高水位线（见 `工具-共享文档编辑锁.py`），新行编号必须从这个回显值 +1 续排，不得用 acquire 之前读到的旧值。**（2026-07-31 补，队列 #163 落地后的正式口径，取代上一句的”回显值 +1”做法）**：`acquire` 现已支持 **`--reserve N --section 一|四` 预留取号**——在持锁窗口内**原子**完成「读高水位线→分配 N 个连续编号→回写高水位线」，直接返回**字面编号**，调用方**不再自己做加法**。理由：#162 已证明”回显正确、人仍会看错”，把加法从人手里拿走才是根治（详见 #163）。**此后新行编号一律用 `--reserve` 取**，例：`acquire --who “Cowork-采购专线” --note “v2.4 回灌” --reserve 2 --section 一`；预留多了无妨——**编号不复用，留空即可**，宁多勿少。**（2026-08-04 补，队列 #185 落地后的正式口径）**：同时需要 §一/§四 两套号时，改用 `--reserve-multi 一:N 四:M` 一次性跨分区预留（与单分区 `--reserve`/`--section` 互斥），不再需要「另一套取回显值 +1」的退路。② **抢不到锁时”队列更新待补”的内容，统一放在自己域接力文件顶部、固定小节名「⏳ 队列更新待补」**（便于机器识别与扫描回补缺口，见 #97）；回补完成后由回补方删除该小节，空节视为已清。**（2026-08-06 补，队列 #236(1)）**：第 1 条"认领即预登记批次"要写的预登记内容，本质上也是"改队列文件"的一种，天然遵守本条——抢不到锁时同样走这条既有降级路径，不为预登记再发明第二套语义。**（2026-07-30 补，队列 #168 修法生效）**：**企微智能机器人亦为受锁写入方**——此前本条锁只在 Cowork/CC 两类人类会话之间成立，机器人归档后本地追加队列行完全绕过它，人类持锁编辑期间机器人若直接写盘会被稍后人类的整文件写回静默覆盖；#168 已改为机器人追加前同样 `acquire`，占用中不写盘、改为推迟补录、下一条消息到达时自动补录（见 `queue_appender.py::append_pending_task` 的 `lock` 参数 + `queue_lock_pending.py`），不再是”人类互斥、机器裸写”的半吊子保护。**（2026-08-02 补，队列 #197 修法生效，保护强度描述同步）**：本条开头”锁是协作性质而非硬互斥”准确描述的是 acquire 的**原**实现——`existing = _read_lock(...)` 判断无锁→随后写入两步中间无任何互斥，两个进程可能在同一窗口内都读到”无锁”、都写入成功、都相信自己持锁（#197 只读审计取证）。**#197 已堵住这一具体缺口**：`acquire` 内部”读判定→写”整段现由一个独立的、生命周期仅限单次调用（创建→用完即删）的互斥标记文件（`.editlock.mutex`，`O_CREAT|O_EXCL` 原子创建）包住，同一时刻只有一个进程能执行这段逻辑；写入亦改为临时文件+`os.replace` 原子换入并写后回读校验（不信”写成功了”）。多进程并发单测（16 进程抢空锁、10 进程抢陈旧锁两组场景）验证均恰好一个成功——”两个进程都读到无锁、都写入成功”这一具体故障形态已由 OS 原子性保证消除，不再是纯靠”窗口很小”侥幸不撞。**仍需澄清的边界（未变，勿过度解读为分布式强锁）**：本条只保证”谁赢得 acquire”这一决策本身是原子的；它是本地文件锁，不能阻止绕过 acquire、直接改写目标文件的行为——本条开头”能让两边都在写从静默覆盖变成后来者主动让步”描述的正是”经由 acquire/release 协作的双方”这一前提，此前提未变。（未改动：`release` 仍是”改写为释放标记、不删除文件”——#121(a) 沙箱兼容考量；`--reserve` 取号逻辑未动，见 #185 另行处理其”单 section”已知限制。） **（2026-08-28 补，队列 §一 `#426` 拍板 ⒜，两桌全局）——🔴 worktree 隔离的 session 到底该怎么改队列，从此有明规则**：**权威副本恒定只有主工作区那一份**（`_resolve_repo_root()` 按 `git rev-parse --git-common-dir` 解出），而 **linked worktree 里的 agent 物理上够不着它**（隔离禁止，且去动主工作区会与 sweep 抢）。⇒ **正路只有一条，且它事实上早就在走**（`OP-0828-A`／`-B`／`-D`／`-E` 全部如此，只是从来没写下来）：**① 就在自己那个 worktree 内改自己那份队列文件 → ② 分支 ff 进 `master` → ③ 由落库 sweep 同步回主工作区**。**锁照占照放**——它的**协作信号**（`acquire` 回显最近 120 分钟内的其它身份、`status` 显示谁在改）完全有效，正是靠它才知道有没有并行线在动同一份文件；**不得据 `#426` 认为「编辑锁没用、可以不占锁」**。 🔴 **但「放」这一步 worktree 线做不到，本段初稿写「锁照占照放」是错的，同一次收工里就被实测推翻，如实改在这里**（`OP-0828-P` 2026-08-28 亲历）：`release` 的 **⑹ 登记完整性**度量的是**整个主工作区的脏文件**（`_local_git_status_paths`），而它给出的两条出路——登记 §二 批次、或写 `登记豁免：` ——**取材面只有「本次 note」＋「本次持锁期间在权威副本上触碰过的队列行」**（见 `工具-共享文档编辑锁.py` 的 `waiver_sources`）。⇒ **worktree 线两条都走不通**：note 在 `acquire` 那一刻就定死（`acquire` 对同一身份不可重入，改不了），而它触碰的行全在自己那份副本里、权威副本上一行没动 ⇒ **`release` 恒被拒，锁只能挂到 30 分钟自动陈旧才被接管，期间任何人写不了队列。** 🔑 **这与 `#426` 记的「守卫对你恒真通过」是同一枚硬币的另一面**：那一面是**该拦的拦不住**，这一面是**该放的放不过**——**同一个「权威副本只有一份、而你够不着它」，在两个方向上各错一次。** ⚠️ **本形态在本工具里早有先例且已被承认**：企微机器人曾因完全相同的原因被别的会话的脏文件挡住、全历史 5 次，修法是给它一条**身份豁免**（`AIBOT_LOCK_WHO`／`SWEEP_LOCK_WHO`，见该文件 `REGISTRATION_WAIVER_MARKER` 上下方注释）——**worktree 线目前没有对应的那一条。** ⇒ **给 worktree 线的现行操作建议（在有人修好之前）**：主工作区若已被别的线弄脏，**就不要为「只改自己副本」这件事去 acquire**——占了就放不掉。只在**确需读取权威副本当前状态**（如高水位线、并行线协作信号）时占，并**做好它会挂到陈旧**的准备；`status` 是只读的，随时可用、不占锁。 🔴 **但必须同时知道这条路的代价，否则会把「没被拦下」读成「写对了」**：`release` 的行身份守卫与 `:1063` 那道只认 `📥` 前缀的 G 闸，校验的是**主工作区那份你没动过的文件** ⇒ **对你恒真通过、零信息量**；新增行的编号归属、状态列机器字段、串行闸豁免，**一律须自行核对**。 ⚠️ **连带一条实测边界（2026-08-28 `OP-0828-P` 撞出，比 `#426` 原文更进一层）：worktree 里不要用 `acquire --reserve` 取号。** `--reserve` 把推高后的高水位线**写进主工作区那一份**，而你的新行落在**自己那一份**；分支 ff 进 master 之后 master 侧的高水位线是你那份（未推高）⇒ **这次预留当场作废，号可能被下一个人重复分配**——**与本条要防的静默覆盖同形，只是漂的不是内容、是计数器**。worktree 内确需新号时：**手工写字面号，并在同一份文件里把顶部高水位线一并推到位**（两处同改、同一次 ff，天然一致），`0-学习与工具/工具-队列结构lint.py` 的高水位线判据会在 CI 上核这一致性（`#426` 同批新增）。 ⚠️ **本段只适用于 worktree 隔离**；若你并非隔离、只是编辑器指错了文件，那是 2026-08-10 `#321` 幽灵副本事故形态——**两份都在改、后写的静默覆盖先写的**，须立刻停手核对，不适用本段。
8. **每周清扫与编号高水位线（Paul 2026-07-24 定，治理批入法）**：值周巡检（周一）对账审计完成后，将 §一/§二/§三/§四 全部已完成行整行迁入《跨桌任务队列-归档-YYYYMM.md》（同目录按月一档，编号永不复用），并同步更新本文件顶部”编号高水位线”；新行一律从对应高水位线 +1 续排——归档后本文件内看不到历史最大号，续号以高水位线为准，不得以文内可见最大号为准。首次清扫 2026-07-24 由总线执行。**批次即扫（2026-07-24 拍板落字批遗失事故后补）**：§二 登记新批次后，登记方应**立即触发一次 sweep**（`Start-ScheduledTask -TaskName ZhuopinCommitSweep`）当场落库，不把批次留在数小时敞口里（本日 B-0724拍板落字 批在敞口期被并行 session 的主工作区同步按”改动已过时”建议 `git checkout --` 误弃，靠会话记录重打恢复，见 #101）；任何 session 对主工作区共享文件执行 `git checkout --` 弃改前，**必须先核对 §二**——该文件出现在任何”待取活”批次声明里即不得丢弃，改为触发 sweep 落库。 🆕 **⚠️ 但「触发」不等于「一定会落库」（2026-08-08 承载性核查第三批实测，拍板项 6）**：若触发那一刻**本文件的编辑锁正被他人有效占用**，sweep 起跑段探锁后**整轮零 git 动作直接跳过**，且**只写日志、不发 webhook**（`SweepAbort` 分支只有分叉才告警）——**一个完全照本条做的动作，可能什么都没发生，而且没有任何信号**。批次不会丢（下一个整点轮会捡起），但**登记方会以为已落库然后就走了**，那正是本条要防的敞口本身。**触发后顺手看一眼 `reports/sweep-commit.log` 末几行**（有无本批次的「已本地提交」字样），没有就等下一个整点轮再确认一次。**登记状态列禁带 “✅”（2026-07-27 深夜 gotcha，队列 #125 附带发现）**：`工具-落库sweep.py` 用 `”✅” not in status_cell` 判定该批次是否”待处理”——登记新批次时若图省事把状态列写成”✅ 已完成（本次登记，待 sweep 落库）”，sweep 会误判其已处理而永久跳过，批次石沉大海（`B-0728财务专线核实`/`B-0728队列#125回填` 两批曾中招，07-27 深夜由 CC 发现并改回不含”✅”的”**待处理**（登记，待 sweep 落库）”后 sweep 才真正落库）。登记时状态列**不得**出现”✅”，只有 sweep 自己写回的”✅ 已完成（sweep 自动落库 时间戳）”才算数。**批次行须声明「本批变更参数 + 已复检」（Shao Peishen 2026-08-02 定，队列 #203）**：凡批次涉及**参数／周期／判据／架构**变更（如任务周期、触发方式、取号口径、鉴权边界、审计落点、锁语义、端口形态），批次行**首段须写一句**：「**本批变更参数：X（旧值→新值）；已 grep 复检、可能受影响：#A、#B ／ 无**」；不涉及则写「**本批变更参数：无**」。 🆕 **同一字段再加一问（Shao Peishen 2026-08-09 定，「记忆偏差」整治第③件，队列 #311）**：**凡本次会话中他说出「以后请…／以后都…／全局记住」这类立法请求，本批次行必须写明它落进了哪个载体**（形如「**本批新入法：〈规则一句话〉→ 落 `〈文件〉§〈节〉`**」）；**当次照做但未入法 ＝ 视同没做**。 **实测依据（2026-08-09）**：「opener 须标 session 明细」这条要求，他自陈提过几次、我也照做过几次，而**全库（含两份归档件与进度编年）grep 零历史痕迹**——**没入法的一条不剩，入法的三条（§〇 执行环境／§〇.0 标题行／§〇.1 工作区）至今在用**。 🔑 **为什么仍挂在这个字段上、不新立条目**：立法请求**必然伴随一次改动**，而改动**必然走批次**——这是现成的必经之路；新立一条人守条目，从诞生那天起就是惰性的（同 CLAUDE.md §5 规则退休制）。 **为何挂在批次上而不是新立一条纪律**——机制变更**本来就必须走批次、无一例外**，等于零成本地把复检挂在必经之路上，**不需要任何人额外记住一条新规则**（同"机制优先"大原则）。**实证依据（#203）**：2026-07-31 #189 把 sweep 周期 4h→1h 后无人复检，2026-08-02 只扫这一个参数就在活文档里扫出 **3 处**过时引用，**其中 1 处躺在一份尚未执行的迁移决策件里、照它配置会把周期静默配回 4 小时且对外表现完全正常**；同日扩扫 7 个变更再得 1 处**面向专员的 SOP 与鉴权门禁冲突**（#204，正阻断 QD-B 灰度试用）。**判据**：一个参数改动平均在活文档留约 3 处过时引用、其中约 1 处具静默错配能力。**优先扫"没有主人的活文档"**——场景 CLAUDE.md 每次都被顺手回填，而面向专员的 SOP/一页纸/灰度指引没有任何 session 的手会碰到，是系统性盲区。 **表格单元格正文禁写裸竖线（2026-07-31 补，队列 #164）**：正文（含引用的 PowerShell/CLI 片段）里出现 ASCII 竖线 `|` 会被朴素按列下标解析的工具误判为额外列分隔符，致使该行列数偏离标准 8 列、后续各列被顶偏（如”期望产出”被读成”状态”）——需要时改写为全角 `／`，不得直接书写裸竖线（参见 §一 #111/#112/#115/#125/#130/#144 六行 2026-07-31 修复实例）。 **「已复检」的扫描域必须覆盖仓库外载体（2026-08-03 补，#227①）**：全库 grep **结构上扫不到**四类仓库外活载体——① Cowork artifacts（`C:\Users\Paul Shao\Claude\Artifacts\`）；② `.51` 四服务页面内嵌文案；③ 已安装版 skill；④ `Claude\Scheduled\` 定时任务真身（库内仅镜像）。凡批次声明「已复检」，若变更参数可能落进这四类载体，**须逐项过一遍该清单并在批次行写明结果**（实证：sweep 周期 4h→1h 后，artifact `zhuopin-project-status` 内流程图错了 3 天无人发现，因为它不在任何 grep 域内，见 #227）；扫描脚本机制化见 #227②——**脚本已建成**：跑 `python 0-学习与工具/工具-仓库外载体扫描.py "<变更参数>"`（keyword 是**位置参数**、纯子串匹配非正则；`--skip-http` 可跳过 `.51` 四服务页面拉取；目录不存在／服务不可达均降级为「跳过并说明原因」、不视为失败），**不必再逐项手工过**。

9. **机制层总量控制——守卫 one-in-one-out ＋ 机制类未收口 WIP 上限（Shao Peishen 2026-08-08 拍板，措施 B＋C，队列 #308）**：**入法依据是实测，不是感觉**——§一 现存 **机制/环境类 : 业务场景类 ＝ 86 : 20（81%）**，未收口 **19 : 9** 倒挂，**08-07／08-08 两天新建 机制 12 ／ 业务 0**，守护本文件的工具代码合计 **4822 行**且只增不减。**⇒ 机制层已经变成产品本身，「建任务改正、建任务改正」的循环由此而来。** **(B) 守卫 one-in-one-out**：`规则退休制`（根 CLAUDE.md §5）只管**人守规则**，**守卫代码本身此前没有退休制**。此后**新增机制类变更包必须回答「本次退休哪一个既有守卫；若不能退，写明为何不能」**。🔴 **落点是 `openspec/config.yaml` 的 propose rules**（#206 已把强制门禁段迁至该处，是现成的机器咽喉）——**本条不写成人守条目，不新造载体**；未经该问即提交的机制类变更包，design 审时退回。 **(C) 机制类「可动 WIP」上限 ＝ 8**（**分母口径 2026-08-08 当日修订，见下**）：**期间新立机制行前须先关一条**（业务场景行不受本限制）。 🔴 **分母＝「可动 WIP」，不是未收口总数（Shao Peishen 2026-08-08 拍板修订）**——原口径把一切未收口机制行计入，**而实测发现绝大部分根本不消耗我们的产能**：13 条待领里 **4 条定时触发型**（#129／#217／#202／#259）、**4 条依赖外部方**（#67／#95／#155／#224）、**1 条永久关闭**（#220），**真正可立即构建收口的存量 ＝ 0**，剩下的只有本轮三条新方案。**旧口径的后果已真实发生**：同日立 #309（CI 基线）时按总量口径判为「15 > 8 超限」、被迫走特批例外，**而按可动口径当时仅 3 条、本不该撞限**——**一个会逼出例外的上限，例外多了规则就废了**（同根 CLAUDE.md §5 规则退休制的判断标准）。 **⇒ 三类明确排除、不计入可动 WIP**：① **定时触发型**（触发日未到，提前做无意义）；② **依赖外部方**（等专员签认／等 IT／等供应商数据——等人不等我们）；③ **永久关闭·仅手动唤醒**（如 #220）。 ⚠️ **机械实现暂缺一半，当前靠人工判定，如实登记不掩饰**：①已可由看板「定时触发型」桶自动排除、③已可由 `🛑` 首标记自动排除（两者均已落地）；**②「依赖外部方」目前没有可靠的机器判据**——🔴 **刻意不为它造关键词猜测**（那正是 #308 要根治的形态，也是本 session 反复踩过的坑），**改为并入 #308 的字段设计**（机器状态字段增加一个「受外部阻塞」态，落地后自动排除）。**在 #308 落地前，②由值周巡检在对账审计时人工核定，争议以其判断为准。****三处落点**：⑴ 看板 `zhuopin-project-status` 显示「机制类未收口 N／8」并在超限时标红（2026-08-08 已落地）；⑵ 编辑锁 `release` 在新增 §一 机制类行且超限时**提示不阻断**（随 #308 变更包实现）；⑶ 值周巡检《本周计划》固定列出该计数。**判据的已知模糊处（如实登记）**：「机制类 vs 业务类」按任务列关键词判定，边界行会有争议——**本上限的用途是给建行踩刹车，不是精确会计**，出现争议时以值周巡检的人工判断为准，不为它再造一套判据（那正是本条要防的事）。　━━━　**已实现（2026-08-09，CC，队列 #308 apply）**：机器状态字段 `blocked`取值已落地，②「依赖外部方」分母口径不再需要值周巡检人工核定；⑵ 编辑锁 `release` 的机制类可动 WIP 超限非阻断提示已随 #308 上线（读 `[D:机]` ＋ `[S:open/partial/hold]` 计数，`blocked`/`timed=`/`done`/`🛑` 结构性排除）。　━━━　**⑵ 已由「提示不阻断」改为「阻断 ＋ 双条件逃生阀」（2026-08-17，CC，openspec 变更包 `editlock-hold-scope-and-wip-block`，§四 #58 ⑶，commit `35266f8`）**：`release` 时若**本次持锁期间真正新增了 `[D:机]` 的 §一 行**且重算后可动 WIP 超上限，**拒绝 release、锁保持占用**。**逃生阀须两个条件同时到位**：① `release` 传 `--force-mechanism-wip` 开关（**不携带理由文本**，只表达「我知道我在越过一条规则」这个显式意图）；② **本次新增的那条机制行状态列内写明 `WIP豁免：〈理由〉`**，一次新增多条时**每条都要各自写**。**缺任一即仍拒绝。** 🔴 **理由的唯一真源是行内标记，不是命令行**——CLI 参数是会话级的、随窗口关闭即消失，而这条逃生阀要治的恰恰是「越过之后没人知道为什么」；写在行里则进 git、被 `工具-队列结构lint.py` 与值周巡检看得见。**工具刻意不新增任何自己改写队列正文的写盘路径**（#326／#322 两次教训）。 🔴 **触发条件保持原样、不改成「release 超限即拒绝」**：当前存量 24／16 已超限，若那样写则此后每一次 `release` 都会失败——编辑锁是全项目唯一写入咽喉，**连来关行降 WIP 的那个 session 也会被挡在门外，规则会把自己的解法一起锁死**。要压的是「新立机制行」这个动作，不是「改队列」这个动作。 **改为阻断的依据**：2026-08-10→08-16 观察周实测，可动 WIP 由 17／16 升至 24／16，周内新立机制行 6 条无一伴随关行；而该提示只在建行那一刻响 ⇒ **6 次每次都响了、每次都被越过，一个非阻断提示在连续 6 次被无视后信息量已经是零。** **上限 16 未动**（§四 #58 ⑴：第三次为迁就现状改口径即等于废掉措施 C）。**监测**：`WIP豁免：` 的出现次数可计数，批量出现即说明上限定错了，应回 §四 #58 重议上限而不是继续豁免。**⇒ 判据须写成两条合取，缺一都会读错**：① 该行状态列含 `WIP豁免：`；② **该标记在这一行「首次出现（新增）」的那个 commit 里就已存在**（`git log --diff-filter=A -p` 或该行首现 commit 可查）——因为逃生阀只在「新增机制行」那一刻生效，事后补写标记既不曾放行过什么、也不该被计入。**按此口径当前真实豁免次数 ＝ 0。** ⚠️ **本条的监测口径当场被自己证伪过一次，如实留痕（2026-08-17）**：本批原写「`WIP豁免：` 在队列全文的出现次数可 grep 计数」，写完当场实测——**整文件 grep 得 10，全部是本批新写的说明文字；改按「§一 状态列取数」得 1，仍是 #324 行自己的说明文字；真实豁免 0。** 三个数字、三种读法，**而「10」会让人读出「豁免已被用了 10 次 ⇒ 上限定错了」这个完全相反的结论**。这与同日 README「`grep` 得 13 ／ 表格数据行得 0」是**同一族计数陷阱的第二例**，且这次是**规则自己刚写下就踩中**——一条监测指令若不写明「在哪个结构位置取数」，它迟早会被在讲解自己的正文上执行一次。　━━━　**⑶ 上限 16 → 24（2026-08-19，Shao Peishen 两次拍板，CC 直接改值，同 #313⑥ 路径）**：《机制类可动 WIP 盘点-2026-08-18》§五 定夺 1 先答 **(a) 调到 20**；同日 CC 执行时实测报出差额后改定 **24**。**实测基数（用 `_count_mechanism_wip` 本身跑，非另写判据）**：加 `🛑` 前 23 → 同日按定夺 2(a) 给 #284／#170／#282／#122 四行加 `🛑` 首标记后 **19**。 🔴 **上调理由不是「超限就抬杠」**——光「真在办」就有 15 行，而排队待立的 4 条**各自对应一次真实事故或一个已确认的生产不可用缺陷**（`append-row` 咽喉三修 #351／队列 lint 称呼判据 #352／发送脚本抹掉闭环形态判定 #353／`parents[N]` 越界致某 CLI 在 `.51` 上从未可用 #354），**压着不立 ＝ 让那些事故保持可复发状态**，与措施 C 控风险的目的方向相反。 ⚠️ **为何是 24 而非盘点件推荐的 20——一处算术前提当天被实测推翻**：盘点件写「真在办 15 ＋ 排队 4 ＝ 19，留 1 格余量」，**其前提是 A 类四行（#68／#234／#270／#279）已销号**；而定夺 3 答 (a) 把销号交给了下周值周巡检、**尚未执行 ⇒ 当天的 19 里仍含这 4 行**，四条新行全立进来是 **19+4=23**，按 20 会被 release 硬阻断。**⇒ 不是又抬了一次杠，是原推荐值建立在一个尚未发生的前提上。** 🔑 **随之而来、值周巡检须盯住的一件事**：A 类四行销号后本值应回落一档（23−4＝19 ⇒ 20 即够）；**若销号做完而上限没跟着降，那就成了一个靠「忘了收回」维持的上限**——正是措施 C 要防的那类松弛。 **四处落点已同批改完**：`工具-共享文档编辑锁.py::MECHANISM_WIP_CAP_DEFAULT`、`专线opener模板库.md` §⑵、`zhuopin-kickoff-prompt` SKILL v1.10（**已安装版待 Cowork `save_skill --overwrite` 同步**）、openspec 变更包 `editlock-hold-scope-and-wip-block` 的 `editlock-mechanism-wip-guard` spec。**2026-08-19 立完四条后实测 23／24。**　━━━　**⑷ 上限 24 → 22（2026-08-20，CC OP-0820-A，Shao Peishen 2026-08-19 答「摘 🛑 ＋ 销 A 类四行 ＋ 按回收条款降上限」(a)）**：**⑶ 末尾那条回收条款已被兑现** —— A 类四行 #68／#234／#270／#279 当日**逐条复核后**全部销号（**未照抄 2026-08-12～08-17 的前序建议**：四行实证全部重跑，其中 #68③ 是直接查 Windows 任务计划实测 `ZhuopinCommitSweep` 当日 `State=Ready`／`LastTaskResult=0`，而非引用 07-30 的旧体检记录；四行复核结论均写在各自状态列开头），同批摘掉 #282 的 `🛑` 首标记（该行 ⑴ 包已 apply、**正在动**，`🛑`「结构性不可动」的原义不再成立，留着会让 WIP 判断持续偏松）。 🔴 **新值只取实测、不取预设** —— ⑶ 已记过一次教训：08-19 的推荐值 20 被推翻，正因为它建立在「A 类四行已销号」这个**尚未发生**的前提上；**故本次的三个数各自都有出处**：**N ＝ 21**（做完「摘 🛑 ＋ 销四行」后用 `_count_mechanism_wip` **自身**对两份队列真身实测，沿革 24 → 摘 🛑 后 25 → 销四行后 21）／**M ＝ 0**（排队待立但尚未落行的机制类行条数：08-19 排队的四条已取号落成 §一 #351-#354，08-20 拆件巡逻新建行 0 条，接力件「⏳ 队列更新待补」节无待补机制行）／**余量 1 格** ⇒ **22 ＝ 21 ＋ 0 ＋ 1**。 ⚠️ **本次亦设了退出条件，免得 22 又变成一个靠「忘了收回」维持的数**：若此后连续两周 `_count_mechanism_wip` 实测持续 ≤ 18，值周巡检应回本条重议是否再降一档；若 `WIP豁免：` 开始批量出现，则按 §四 #58 既有约定回去重议上限本身，**而不是继续加豁免**。 **五处落点已同批改完**：本正本、`工具-共享文档编辑锁.py::MECHANISM_WIP_CAP_DEFAULT`（并顺手修好其 `release` docstring ⑨ 段里一个停在 16 的陈旧字面量）、`专线opener模板库.md` §⑵、`zhuopin-kickoff-prompt` SKILL **v1.15**（**已安装版待 Cowork `save_skill --overwrite` 同步，CC 做不了**）、openspec 变更包 `editlock-hold-scope-and-wip-block` 的 `editlock-mechanism-wip-guard` spec。　━━━　**⑸ 新增 assigned 机器字段 `[A:...]`，字段顺序须为 `S→D→A`（2026-08-30，CC `OP-0830-D`，队列 #312）**：状态列 MAY 在 `[D:...]` **之后**再带 `[A:已派出]`（assigned，含"已派出未认领"与"在办"两态——对可 Open 池而言两者等价，都不该再被人领；撤销即删字段，不新增 `[S:...]` 枚举值，理由见 design D1：新增枚举会同时动到编辑锁／看板 JS／本模块三处各自独立的解析器）。**字段顺序是硬约束，且写反不报错，实测坐实**：`[S:open][D:机][A:已派出]` 经 `_parse_status_domain_fields` 解析仍得 `('open','机')`（未知尾字段被天然忽略，零改动向后兼容）；但 `[S:open][A:已派出][D:机]` 解析出 `('open', None)`——**域字段被静默解析为 None，且不产生任何异常**，WIP 计数等下游消费方会把该行当"域未知"悄悄跳过。写反了须被看见：解析阶段发 `RuntimeWarning`（不拦截、不修正，同本项目"非静默降级"既有惯例）。可 Open 池与看板卡两处**同一判据**：行含 `[A:` 即排除、不解析取值（向前兼容未来扩展取值）。详见 `openspec/changes/open-pool-assigned-field-and-opener-env-filter/`（design D1/D2）。

10. **建行前必须先做「并入审核」——并入优先，追加为例外（Shao Peishen 2026-08-08 定，两桌全局，适用所有人工 session）**：其原话——「**以后新建队列任务不管环境端还是业务端，不管 Co/CC，优先审核并入已有待领任务，实在无法并入任何已存在待领任务才追加序号新建**」。**⇒ 追加新号从「默认动作」降级为「例外动作」，须给出理由。** **判据（可机械化，挂在唯一入口上）**：🔴 **人工 session 新建行的唯一入口是 `工具-共享文档编辑锁.py acquire --reserve`**——取号那一刻正是「新建任务」发生的唯一时点，故并入审核挂在此处：`--reserve` 时**回显当前全部 §一 待领行（编号＋任务列首段）**，并要求随附一句**并入审核结论**（形如「已逐条过 N 条待领行，无可并入：〈一句话理由〉」或「拟并入 #X，故本次不取号」）；**未给结论即拒绝取号**。实现随 **#308 变更包**同车（同一文件 `工具-共享文档编辑锁.py`，与措施 C 的 `release` 提示同批），**本条不单独立行——那正是它自己要防的动作**。 🔴 **`--reserve` 完整用法须带 `--domain 机|业`（#308 tasks 7.3，2026-08-17 补）**：取 §一 号时**域随 `--reserve` 一并声明**，例 `acquire --who "Cowork-业务总线-0817" --note "…" --reserve 1 --section 一 --domain 机`；跨分区用 `--reserve-multi 一:1 四:2 --domain 业`。**该参数仅对 §一 预留请求生效**（域字段范围红线仅 §一），**传了却不含 §一 的请求会被直接拒绝、不静默忽略**。 ⚠️ **漏传的后果是「静默少算」而非被拦下——2026-08-17 实测，不要凭直觉推断成「反正会报错」**：⑴ 不传 `--domain` **不报错也不警告**，只是回显里那行「域声明」不打印；⑵ `工具-队列结构lint.py` 的 CI 硬门禁**只校验状态列以 `[S:` 开头、不校验 `[D:`** ⇒ **缺域字段的 §一 行照样过 lint**；⑶ 真正的代价在计数——`_count_mechanism_wip` 按 `[D:机]` 取数，**缺字段的行不进本协议 〇.9 措施 C 的机制类可动 WIP 分母**，上限提示因此偏松。**这正是「把行改成不计数就能让数字好看」的那类逃逸口**，与 2026-08-13 关于 `hold` 是否计入的拍板（拍 (b) 维持含 hold，理由是"线画在 blocked、不在 hold"）出于同一考虑。 📌 **另注意 `append-row --domain` 与本参数同名不同义**：后者决定**这一行写进哪份物理队列文件**（机制环境／业务场景，队列 #315 决策点 3/5），**不传则按向后兼容默认落机制环境文件**并打印提示——业务场景行漏传会写错文件。 **可行性已实测**：2026-08-08 §一 待领行 **12 条**，逐条扫读成本很低；且**与协议〇.9 措施 C 互相强化**——WIP 上限 8 让待领池保持在可一眼扫完的规模，池子小又反过来让并入审核不成为负担。 ━━━ **自动 session 的处置（Shao Peishen 明示「值周巡检和拆件巡逻如有困难请考虑方案」）** ━━━ **⑴ 值周巡检 —— 适用，且比人工 session 更容易**：它做对账审计时**本就通读全队列**，并入审核是顺带一步；在其 prompt 的建行环节加一句「新建前先对照待领池，能并入的并入」即可，无额外读取成本。 **⑵ 拆件巡逻 —— 适用于「升格」环节，不适用于「收件」环节**：需分清两件事——机器人对每条企微来件**自动追行**（`queue_appender.py::_next_task_id`，**不走编辑锁 `--reserve`，是另一条独立取号路径**）产生的是**收件登记**（形如「企微反馈自动归档：XX 发来文本反馈」），**不是任务**，且机器无法判断并入，**故豁免本条**；真正受本条约束的是拆件巡逻把某条收件**升格为正式任务**的那一步——**升格＝新建任务，须先过并入审核**。 **⑶ 机器人自动追行本身 —— 豁免，但须防它变成绕过口**：豁免理由是「收件登记≠建任务」；**若日后出现「为绕开并入审核而故意走机器人通道建任务」的用法，本豁免立即失效**，如实登记为已知风险，由值周巡检在对账审计时留意。 ━━━ **本条与 §5 规则退休制的关系（如实说明，不自欺）**：本条**刻意不写进根 `CLAUDE.md` §5**——§5 已 29 条、信噪比约 7.5%，再加一条人守条目从诞生那天起就是惰性的；本条落在**队列协议正文（开工必读）＋ 取号咽喉**两处，其中咽喉是机器强制的那一处。**判断标准仍是那句**：一条只靠人记得的规则，作用不是约束、是事后解释。

> 🔑 **实证补记（2026-08-19，Cowork 全景路线图线）——「并入审核」不只是省一个编号，它同时是 WIP 上限的正解；故它应明确前置于取号动作，而不是与之并列。**
> **同日两个 session 处理的是同两条发现，路径不同、结果截然不同：**
> **⑴ `B-0819_17` ＝ 先取号、后审核**：为两条只读取证发现（`alert_webhook.py` 读的裸 `WECOM_WEBHOOK_URL` 在 `5-平台底座/.env` 里值长为 0 ／ FI2 `scan_tax_export_scheduled.py` 的 `_find_env()` 被 worktree 内陈旧 `.env` 副本抢先命中）走 `--reserve 2 --section 一 --domain 机`，**撞上机制类可动 WIP 24／24 被 `release` 守卫阻断**；它**刻意未用 `--force-mechanism-wip` ＋ 行内 `WIP豁免：` 逃生阀**（守纪律，判断正确）⇒ **两条发现一条也没能落行，只活在它的收工报告文本里**。
> **⑵ `B-0819_18` ＝ 先做本条的并入审核、再决定要不要取号**：审完发现 **A 本就该并入 §一 #282**（该行「仍在 webhook 的调用点」清单里逐字列了这个脚本）、**B 本就该并入 §一 #354**（该行标题即 `_find_env()` ／ `parents[N]` 同族收拢）⇒ **一个新号都没取，那堵墙根本不必翻**；回写前后各实测一次，可动 WIP 仍 24／24 未变。
> 🔴 **结论两句**：① **并入审核不只是省编号，它同时是 WIP 上限的正解**——可并入的行并入之后，分母根本不会涨；② **「先取号、后审核」这个次序本身会把可并入的行逼成新行**，而新行又推高 WIP、逼出下一次豁免。 **⇒ `--reserve` 处的机器拦截是最后一道保险，不是审核发生的时点**；审核应在「决定要不要取号」之前完成，本条正文因此读作「并入优先**前置于**取号」，而非「取号时顺带审核」。
> **本条自身即按其结论处置——未新建任何队列行**（本洞察的内容恰恰是「不要动辄新建行」，为它单立一行即自相矛盾），直接追记于协议正本此处；同批未取号，高水位线不变。


~~~

---

## 【附录 J · opener 模板库 §〇 去 provenance 前全文存档 —— 2026-09-04（Cowork 环境总线瘦身线，方案＝构建环境瘦身第二轮-方案-2026-09-04.md §一 A2）】

> 承接载体（J1）：本附录承接 2026-09-04 从 `1-转型规划/0-全景路线图/专线opener模板库.md` §〇 迁出的全部成因／沿革／实证／原话文字。新版 §〇（判据版）留在模板库为正本，**可照抄的骨架正本另立 `1-转型规划/0-全景路线图/opener骨架.md`**；本附录为原文唯一来源，原文原样、可 grep（存档对象＝迁出前一刻的 §〇 全文，含 §〇.00～§〇.19，共 611 行）。行尾符按本文件既有格式统一为 LF，正文字符未改一字。

~~~markdown
## 〇、执行环境标注（硬规则，Shao Peishen 2026-07-27 定）

**凡对外呈现的任务/opener 标题，必须在任务名处显式标注执行环境 `【Cowork】` 或 `【CC】`；`【设置】` 行同步写 `执行环境：Cowork/CC`。** 两处都标是刻意冗余——标题用于扫读挑活，设置行随 opener 一起被复制进新 session。

- **成因**：2026-07-27 本周计划 §A 六条 opener 中，A4/A5/A6 因名字里自带"Cowork 总线""CC 建造"可辨，而 A1/A2/A3 只写"财务/采购/质量专线"，需要靠 `worktree：☐`、"只编 .md"、"收工登记 §二 批次、勿自行 commit"这些**间接特征**反推是哪张桌——Shao Peishen 反馈"有歧义，以后请在任务后注明"。
- **判别口径（写模板时自检）**：
  - **【Cowork】**＝只产/改 `.md`（口径、规划、跟进信、治理、汇报）；不写生产代码、不连真实库、不自行 `commit`（收工只登记 §二 批次，由 sweep 落库）；分支 master、worktree ☐。
  - **【CC】**＝写/跑生产代码、连真实库与 `.51`、跑测试与部署；自行 `commit + push`；新建造按协议〇.5 一任务一分支一 worktree（☑）。
  - **边界个案**：只读取证（如 PowerShell 直读 `.51` 接口、git 取证）Cowork 可做，仍标 **【Cowork】**；一旦需要改代码/部署/触发服务动作即转 **【CC】**。
  - 🔴 **边界个案二·改本机工具链＝【CC】（Shao Peishen 2026-08-02 定）**：全局 npm 包/插件/CLI 的**安装与版本升级**，以及 `openspec update` 一类**会重写生成物的命令**，**一律标【CC】——即便其产出看上去只是 `.md`**。其原话：「本线不到紧急修复到了迫不得已，还是归 CC 让机制流程修复更加稳妥」。**理由（2026-08-02 队列 #205-A 实证）**：这类操作改变的是**全项目构建环境**，且**可能静默覆盖本地定制**——那次 `openspec update` 把 `.claude/commands/opsx/propose.md` 里 2026-07-04 落地的强制门禁段整段删除、**零提示零报错**，混在 10 个文件的上游 diff 里；当场逐文件过目才抓住并还原（另立队列 #206 根治）。**归 CC 等于强制走"一任务一 worktree + 测试 + 自行 commit"的既有流程，把偶然的谨慎换成必然的流程。** **仍归 Cowork 的部分**：对工具链**只读核实**版本与状态、把差异登记成待领行。**破例条件**：紧急且迫不得已 + 其明示授权，且必须 ① 先固化升级前证据（版本三处交叉 + 受影响文件基线）② 逐文件过目 diff（**判据推荐"中文行增删计数"**，本次正是靠它抓到：删 13 增 0 且仅一个文件）③ 事后如实登记为破例。
- **落点**：值周巡检生成《本周计划》§A、拆件巡逻报告的"拟动作"、队列 §一 新行的"领取方"列、各类交接/开场 prompt 文件标题——四处一致。
- **本库自身已按本规则改写**（2026-07-27）：§一~§五 标题带环境标注、五个模板的【设置】行均含 `执行环境`。

### 〇.00 🔴 照抄骨架 —— **出 opener 一律从本节复制替换占位符，不得从下面各节重建**（Shao Peishen 2026-09-02 定，答 W-1 ＝ (c)）

> 🔴 **本节是本库唯一的「可照抄物」。下面 §〇.0～§〇.19 全是「为什么」，不是「长什么样」——读它们重建格式必然漂。**
> **成因**：2026-09-02 `OP-0902-X` 出 opener 时**专门读了 §〇.1 才动笔，照样写错**——因为 §〇.1 只讲「工作区」这一个字段的成因，且其正文当时写着「标准**四**字段」（真实为**六**字段，`session` 与 `派出线` 分别在 §〇.11 与根 `CLAUDE.md` §5，散落三处）。**读了权威节、按它写、结果错**，这是载体问题不是记性问题。**同类纠正此前已发生 ≥3 次** ⇒ 按规则退休制（2026-08-03）必须机制化，本节即第一步；生成器见队列 §一 相应行。

**🔴 六字段，一个都不能少，顺序固定**：`执行环境 ｜ 分支 ｜ worktree ｜ 工作区 ｜ session ｜ 派出线`

#### 【CC】骨架

```
[OP-MMDD-X]【CC】<短名，≤12字>
【设置】执行环境：CC ｜ 分支：master（从 master 起 `claude/opMMDDx-<短横线名>`）｜ worktree：☑（<worktree名>，新 worktree，收工自删）｜ 工作区：<无（纯库内，不触碰 `.51`／企微机器人／定时任务）｜ 或按 §〇.1 四种情形之一写全> ｜ session：新开 ｜ 派出线：<线名>
开工第一件事：调 mcp__ccd_session_mgmt__set_session_title（session_id 传字面量 "self"），标题：[Win]MMDDX-<短名>。🔴 例外：你若是被 Task/Agent 起的子任务，跳过本行不要执行——子任务没有自己的 session，"self" 会解析到父 session、把调度你的那条会话改名（2026-08-28 实撞）。
读 ① `<派单件或首要输入的完整仓库根相对路径>` → ② `CLAUDE.md` §<相关节> 恢复上下文，按<派单件/下述>执行。本件为 <A 类（口径已定、判据已写死），无需再问澄清，直接开工 ／ B 类，开工前问我 2-3 个澄清>。

做什么：
1. …
2. …

不做什么：
- …
```

#### 【Cowork】骨架

```
[OP-MMDD-X]【Cowork】<短名，≤12字>
【设置】执行环境：Cowork ｜ 分支：master ｜ worktree：☐（不建，只产改 `.md`）｜ 工作区：无 ｜ session：新开 ｜ 派出线：<线名>
读 ① `<完整仓库根相对路径>` → ② `CLAUDE.md` 恢复上下文，按<该件/下述>执行。本件为 <A/B> 类。

做什么：
1. …

收工：产出登记 §二 待 commit 批次（走 `0-学习与工具/工具-共享文档编辑锁.py`，勿裸改、勿自行 commit），由落库 sweep 取活。
```

#### 🔴 三处最常丢的结构（每次出 opener 前逐条对一遍）

| 易丢处 | 判据 |
|---|---|
| **`worktree：☑／☐`** | **必须是勾选符号**，不是「archive-414」这种裸名字。☑ 后跟括号写 worktree 名与是否收工自删；☐ 后跟括号写为什么不建 |
| **`session：新开`** | **字面必须出现**。没有它，拿到 opener 的人不知道该在当前窗口继续还是新开一个 |
| **`set_session_title` 整行 ＋ 子任务例外** | 🔴 **写真实工具名 `mcp__ccd_session_mgmt__set_session_title` 与 `"self"` 字面量**，不得简写成 `set_session_title("...")` 这种伪代码——CC 拿到伪代码不知道调什么。「Task/Agent 子任务跳过」那句也是整行的一部分，缺它会改错会话名 |

**另两条同样每次都要在（见 §〇.19／§〇.2）**：代码块**正上方**必写状态标记（`▶ 首次派出：` ／ `▶ 更新版（你尚未执行）：` ／ `▶ 重发（你已执行过）：`）；标题里 `CC`／`Cowork` 只能表示执行环境、且用方括号 `【】`。

---

### 〇.0 opener 代码块**必须带一行标题**，含「计划编号 ＋ 执行环境 ＋ 线名 ＋ 队列行号」（Shao Peishen 2026-08-04 定，硬规则）

**格式**：`### A<N> ·【Cowork/CC】<线名>（<优先级/时限>）——队列 #x／#y／#z`，**标题行必须紧挨在 opener 代码块之前**，聊天中重发单个 opener 时同样带上。

**成因（2026-08-04 他本人反馈）**：本周 A4／A6 两个 opener 因撞车与范围变更被重发过 v2，**重发时只给了代码块、没给标题行**——
他原话「**虽然我可以推断，第一张图是哪个任务的 Opener 不明晰**」。代码块内部只有"按队列 #218／#11／#137 三行开工"，
**要反推它是 A4 还是别的，得先记住本周计划 A 节的分配**；而 opener 存在的全部意义就是"复制即用、零判断"，**让他做推断本身即违背设计目的**。

**为什么是硬规则而不是建议**：opener 会被**多次重发**（撞车改版、范围收窄、前置解除各会触发一次），
**每次重发都是一次身份丢失的机会**；而标题行成本是一行字。**同类形态**＝〇（执行环境标注）与 〇.1（工作区字段）——
三者都是"在 opener 外层补一个字段，使读者不必推断"，本条是第三个。

**自检一问**：*把这个代码块单独发给一个没读过本周计划的人，他能一眼说出这是哪件任务吗？* 不能→标题行没写够。

#### 🔴 补充：标题与 session 名必须带「日期＋编号」（Shao Peishen 2026-08-26 定，硬规则）

**成因**：2026-08-26 本方连出数个 opener，标题只写主题、**不带 `OP-MMDD-X` 编号**；他调出旧格式对比后要求「像以前一样带日子和编号的 Session 名」。
**编号是 opener 在跨会话世界里的唯一身份**——收工报告、队列回写、`§二` 批次行、CC transcript 目录全靠它对齐；没有编号，同一天多件之间只能靠主题猜。

**两处都要带，缺一不可**：

1. **opener 代码块上方的标题行**：`[OP-MMDD-X] <主题短名>`，紧挨代码块之前。
2. **session 名**：🔴 **`[Win]MMDDX-<主题短名>`**（Shao Peishen 2026-08-27 改定三次，终稿如此）。**示例：`[Win]0827A-波次收口-解master分叉与四分支合入`**。
   **三次改定的轨迹**：`[CC] OP-MMDD-X <主题短名>` → `[Win] MMDD-X …`（`[CC]` 与 `OP-` 在 Code tab 里零信息量）→ 去掉全部空格 → **把连字符从「日期-序号」之间移到「序号-主题」之间**。
   🔑 **最后这一步是关键，它把一条「有条件的规则」变成了「无条件的规则」**：本方原写「主题以 ASCII 开头时须补 `-`，以汉字开头则直接接」—— 那要求起草时**先判断主题首字符是什么**。他的改法让横线**固定落在编号与主题之间**：`0827A` 本身无歧义（4 位日期＋1 位字母），中间那个连字符本来就是多余的。**⇒ 不必再判别任何东西，照写即可。**
   📌 **判据（比这条格式本身更值得记）**：**一条需要「先判断再选择」的规则，就是一条会被忘的规则。** 能把条件消掉的改法，优先于把条件写清楚的改法 —— 本条是现成例子：**同一天里，本方写「有条件」的版本，他改成「无条件」的版本。**
   🔴 **CC 与 Cowork 的设定手段不同，不要混用（2026-08-27 实测坐实）**：
   - **CC 侧**：代码块内调 `mcp__ccd_session_mgmt__set_session_title`（见补充三）。
   - **Cowork 侧**：**没有这个工具** —— 本方在 Cowork 会话内实测查找，返回的只有 `list_sessions`／`read_transcript`／`Task*`，**`mcp__ccd_session_mgmt__*` 一个都不存在**（Shao Peishen 提醒「`set_session_title` 好像对 Co 不适用，请小心」，实测属实）。**Cowork 的 session 名取自开场词首行** ⇒ **Cowork 开场词的第一行本身必须自带编号**。
   🔑 **⇒ 补充三那条「每个 opener 第 3 行必须有 set_session_title」只对 CC 侧成立**；Cowork 侧的等价要求是「**开场词首行带编号**」。**把 CC 的做法抄给 Cowork 会写出一个不存在的工具调用。**
   🔴 **⚠️ 本条 Cowork 部分的「格式规则」尚待补全，不得凭本方推断（2026-08-27 由 Shao Peishen 第四次纠正）**：本方原写「Cowork 侧一直没出问题，因为开场词首行本来就带编号」，并举 `环境总线 OP0823B`／`OP0822F-A档下沉`／`【OP-0821-B】环境总线 memory治理0821` 三条为证。**他纠正：Co 侧也出过问题，且为此花了很大力气制定规则，格式不是图上那样。**
   🔑 **回看那三条，它们本身就是反证**：**三条三种格式** —— 编号在后／编号在前／全角 `【】`；两种编号写法（`OP0823B` 与 `OP-0821-B`，前者缺连字符）；末条**日期还写了两遍**（`OP-0821-B` ＋ 结尾 `0821`）。⇒ **这是「乱过、正在被治理」的样本，不是「一直规范」的证据。** 本方把「都带编号」读成了「所以没出过问题」，**是同一天第四次把观察当成因果**。
   📌 **Cowork 侧格式 —— 据 Shao Peishen 2026-08-27 回忆 ＋ 本方交叉印证（🔴 仍非正本，见末段）**
   **他的原话**：「首行带编号，编号规则跟 CC 一样，但是要**语义提前、编号后缀**，又有总字节长度限制。」
   ⇒ **通式：`<语义短名>…<OP-MMDD-X>`（语义在前、编号在后）**，与 CC 侧 `[Win]MMDDX-<主题短名>`（编号在前）**方向相反**。
   ✅ **交叉印证（本方实测，与他的回忆一致且能解释不一致处）**：
   - **本会话开场词首行** ＝ `环境总线-接力OP-0826-C` → **语义前、编号后** ✓ —— **即本方每天都在照这条规则用，只是没意识到它是规则。**
   - `环境总线 OP0823B`（08-23）→ ✓
   - `【OP-0821-B】环境总线 memory治理0821`（08-21）／`OP0822F-A档下沉`（08-22）→ ✗ **编号在前**
   🔑 **不一致的两条恰好是更早的（0821／0822），一致的是更晚的（0823 及此后）** —— **与「规则是后来定的、早期样本正是治理对象」完全吻合**，也印证了他说的「Co 侧也出过问题、为此花了很大力气制定规则」。⇒ **本方此前把那几条早期样本当作规范证据，是把治理对象当成了治理成果。**
   🔴 **「总字节长度限制」这半条：未验证，不据以立任何规则。** 理由是今天刚栽过的同一个坑 —— CC 侧的长度假说被 32 字符实测推翻；而 **Cowork 的名字来自开场词首行、机制与 CC 不同，CC 的结论不能移植**。**5 分钟就能做的实验**：下次开 Cowork 会话时把首行语义段写长一些，看名字会不会被截 —— **在做完这个实验之前，本条不写任何长度数字。**
   ⚠️ **本段仍非正本**：来源是他的回忆（他自己也说「我好像记得」）＋ 本方交叉印证，**不是找到了规则文件**。全库 grep 未找到独立的 Cowork session 命名规则件。**若日后找到正本且与本段冲突，以正本为准。**
   **为什么改**：⑴ **`[CC]` 在 Code tab 里零信息量** —— 那个 tab 下每一条都是 CC，一个人人都有的前缀帮不了他区分；换成机器名 `[Win]` 才有分辨力，**且它为 Mac Studio 迁移（§一 #170）预留了 `[Mac]`**。⑵ **`OP-` 同理零信息量**，去掉后导航栏那一窄列能多显示几个字的主题短名 —— 而 session 名的唯一用途就是**给他一眼认出是哪条**。
   🔴 **一条必须守住的边界**：**只有 session 名用短形 `MMDD-X`；opener 标题行、队列行、§二 批次行、收工报告、CC transcript 目录一律仍用全称 `OP-MMDD-X`** —— 那是跨会话世界里的唯一身份，grep 要靠它对齐。**短形是给人眼的，全称是给机器的，两者不得互换。**
   **Cowork 侧同样用 `[Win]` 这个形状**（它也跑在这台机器上），**但设定手段不同，见上一段红字**；等 Mac 上线后若需再分 CC/Cowork，另议、不预先设计。

**取号规则**：`OP-` ＋ 月日（`MMDD`）＋ 当日流水（字母 `A/B/C…` 为主）。
- 取号前**先 grep 当日已用**：`grep -rho "OP-MMDD-[A-Za-z0-9]*" 1-转型规划/0-全景路线图/*.md | sort -u`，取未用的下一个。
- 🔴 **日期一律用本机 `Get-Date -Format 'yyyy-MM-dd'` 当场重取**，不得估算、不得沿用会话早先的取值（同根 `CLAUDE.md` §5 时间戳硬规则）。
- 历史上出现过非字母流水（`OP-0824-354`／`OP-0825-DRILL`／`OP-0826-M1`），**不追改**；新号优先用字母序。

**自检一问（在 §〇.0 那一问之后再加一问）**：*他把这个 session 的收工报告贴回来时，我能只凭标题就定位到是哪一件吗？* 不能→编号没带够。

#### 🔴 补充三：上面第 2 条（`set_session_title`）**当天就被违反了 17 次** —— 起草期自检位置在此（2026-08-27）

**事实**：`补充一` 2026-08-26 定，第 2 条白纸黑字写着「代码块内 `set_session_title` 的标题」。**当天此后本方手写的 opener —— `OP-0826-D/E/F/G/H/J`、`K/L/P/Q/R/S/T`、`U`、`V`、`0827-A/B/C`，共 17 条，一条都没有那一行。** 2026-08-27 他截图指出：导航栏里 `OP-0827-A` 那条 session 名叫「波次收口 2026-08-26」，**编号没了**。

🔴 **根因不是载体缺失，恰恰相反** —— 规则就写在**本方当天亲手编辑过两次的这个文件里**（同日新增了 §〇.17／§〇.18），位置在此条正上方约 40 行。**⇒ 这是「读到规则 ≠ 执行规则」的又一个实例**（同族＝根 `CLAUDE.md` 性别名录那条的原话）。

🔴 **一处必须更正的错误归因（2026-08-27 由 Shao Peishen 当场纠正）**：本条初稿写的是「`U`／`V` 的 session 名带上了编号、`0827-A` 没带 ⇒ CC Desktop 的自动命名有时保留编号有时丢、靠推断＝靠运气」。**这是编造的因果。** 他的原话：「**U/V 不是靠运气，是我无法分别 session，及时手工加的**」。
**⇒ 真相是：17 条里没有任何一条自动带上过编号，`U`／`V` 那两条是他自己手工补的。** 我把责任推给了 CC Desktop，而实际全责在起草方。
🔑 **这正是同日已记过的那条判据的又一次犯**：**先有结论、后找证据，而恰好有个看起来合理的他方可归因**（见接力卡「上一棒最该被继承的判据」第 6 条）。**代价是：如果不纠正，读到这条的人会以为「有时会自动带上」，于是继续不写那一行。**

**⇒ 结论只有一句：`set_session_title` 没有任何替代品。标题行以 `[…]` 开头不会自动变成 session 名。**

**⇒ 起草期自检（写在这里是因为它必须发生在「写完 opener、发出去之前」那一刻）**：
> **每写完一个 opener 代码块，回头看它第 3 行 —— 有没有那句 `开工第一件事：调 …set_session_title…`？没有就是没写完。**

🔴 **补充三之二：一个长度假说，提出后 2 分钟就被实测推翻 —— 连同它，本方当天在同一件事上第三次给出未经验证的因果（2026-08-27）**

**经过**：他观察「**带编号的标题好像有总字数限定，多了自动吃掉编号**」，本方查了 24 条 session 名，见到「带编号且 ≤ 约 20 字符的 8 条编号全部保住、丢编号那条 opener 首行最长」，便**写成了规则**并加了「证据与它一致且无反例」。
**⇒ 反例当场出现**：他用改名话术把 `0827-A` 设成 **`[Win] 0827-A 波次收口-解master分叉与四分支合入`（32 字符）**，**完整保留、一个字没被截**。

**⇒ 真因至此确定，且比长度假说简单得多**：
- **显式调 `set_session_title` 设的标题不会被截断**（实测 32 字符完好）。
- `0827-A` 之前叫「波次收口 2026-08-26」，**不是被截断，是根本没人设过标题** —— 那是自动命名生成的摘要，摘要里当然不会有编号。
- 🔑 **丢编号的原因**从头到尾**只有一个：没调 `set_session_title`**。长度假说是多余的。

🔴 **本方当天在这一件事上连续三次给出未经验证的因果**：⑴ 怪「CC Desktop 有时保留有时丢」（他纠正：U/V 是他手工加的）→ ⑵ 采纳长度假说并写进规则（32 字符实测推翻）→ **两次都是他用实测推翻的**。**同族＝接力卡判据第 6 条「先有结论、后找证据，而恰好有个看起来合理的解释可归因」。**
⚠️ **特别值得记的是第 ⑵ 次**：本方**明明写了「无法证明这个机制」**，却在同一段里写下「证据与它一致且无反例」并据此**立了三条规则** —— **标注了不确定性，不等于按不确定性行事**。**⇒ 判据：一个假说在写成规则之前，先问「有没有一个 5 分钟就能做的实验能推翻它」**；本例中那个实验就是「设一个长标题看看会不会被截」，成本几乎为零，而本方没做就写了规则。

**⇒ 下面两条仍然保留，但理由换了（不再是抗截断）**：

1. **opener 首行只放标题、正文从下一行起** —— 理由是**可读性与可复制性**，不是防截断。
2. **主题短名建议 ≤10 个汉字** —— 理由是**导航栏那一列窄，短名一眼可辨**；**这是建议不是硬限**，长标题不会被截。
3. 🔑 **编号放最前面**的理由也回到本来那条：**它是跨会话世界里的唯一身份，放在最显眼处便于一眼对齐**。

**标准写法（照抄；注意标题行用全称、session 名用短形）**：

```
[OP-MMDD-X]【CC】<主题短名>
【设置】执行环境：CC ｜ …
开工第一件事：调 mcp__ccd_session_mgmt__set_session_title（session_id 传字面量 "self"），标题：[Win]MMDDX-<主题短名>。🔴 例外：你若是被 Task/Agent 起的子任务，跳过本行不要执行——子任务没有自己的 session，"self" 会解析到父 session、把调度你的那条会话改名（2026-08-28 实撞）。
读 ① … → ② …
```

🔴 **那一行末尾的「例外」是正文的一部分，不得删、不得简写**（2026-08-28 加，成因见补充三之三）。**理由是它必须跟着被复制的那一行一起走** —— 写在别处的规则不会跟着走。

⚠️ **已在跑的 CC session 可以补救**：对它说一句「**请调 `mcp__ccd_session_mgmt__set_session_title`（session_id 传字面量 `"self"`），标题：`[Win]MMDDX-<主题短名>`**」即可，不必重开。
🔴 **Cowork session 无此补救路径**（工具不存在）—— 它的名字在开场词首行落定的那一刻就定了，**事后只能由 Shao Peishen 手工改**。⇒ **Cowork 开场词首行写错编号的代价比 CC 高**，起草时更要看一眼。

📌 **按规则退休制（根 `CLAUDE.md` §5）本条已远超阈值**（人守违反 3 次即须机制化或删除，本条一天 17 次）⇒ **须机制化，落点＝给 opener 集／波次计划／看护件加一条 lint：扫 `.md` 里的 opener 代码块，一次收两个失效形态** —— ① 块内含 `【设置】` 而**无** `set_session_title` ⇒ 告警（**旧形态**：编号丢失，一天欠 17 次）；② 块内**有** `set_session_title` 而**无**子任务例外句 ⇒ 告警（**新形态**：子任务会把父 session 改名，2026-08-28 实撞，见补充三之三）。 违反计数与本 lint 的建造需求已登记 §一 `#284`（阈值计数台账）。**在 lint 建成前，① 仍是人守；② 已由「前提焊进那一行」消掉条件**（见补充三之三根治节）。

🔴 **判据已挂 release 咽喉，正本仍在本节（2026-08-30，队列 §一 `#437`，CC `OP-0830-G`）**：`工具-opener块lint.py` 只扫 git 已跟踪的 `.md`，opener 派出恰在跟踪之前那几分钟，lint 结构性地看不到——`工具-共享文档编辑锁.py::release` 因此新增一道旁挂 ⑹ 的结构检查，本次持锁期间触碰的 `.md` 若含此处两个形态之一即拒绝 release（fail-closed，逃生阀 `opener豁免：<理由>`）；判据逐字复用本节判据的实现（`check_block`），**不重写第二份**。**覆盖边界如实声明**：只覆盖走了队列锁 acquire/release 流程的 opener，写完直接粘出去、从不经本工具的会话它仍看不到——`#284` 因此不销号。

#### 🔴 补充三之三：**Task/Agent 子任务的 prompt 里，绝不能带 `set_session_title` —— `"self"` 会解析到父 session**（2026-08-28 实地撞出，硬规则）

**事故**：`看护件-2026-08-28-落地后批.md` 要求看护者「把 opener 正文**原样**作为子任务的 prompt，🔴 不要改写」，而每条正文第 3 行都是那句 `set_session_title（session_id 传字面量 "self"）`。⇒ 子任务 `OP-0828-R` 一起活，**看护者 `[Win]0828W2-落地后批四条看护` 的标题当场变成 `[Win]0828R-416回件链路三缺陷`**（Shao Peishen 截图指出）。四条子任务会互相覆盖，**左栏里再也找不到看护者那一条**。

**机制**：**Task/Agent 子任务没有自己的 session**，它跑在父 session 的上下文里 ⇒ `session_id:"self"` 解析到的是**父 session**。**调用成功、无报错、返回值正常** —— 同族＝「工具静默回退：它没错，只是解析到了另一个对象」。

### 🔴 根治（Shao Peishen 2026-08-28 定「需要根治」后改定，选 ①）——**把前提焊进那一行，而不是写成一条规则**

**首版修法是人守、已判定必失守**：它要求「派工者在传给子任务前记得删掉那一行」，而这是**另一条规则（「原样传、不要改写」）的例外** —— 正是接力卡判据「**一条需要先判断再选择的规则，就是一条会被忘的规则**」所指的形态。

**⇒ 定案：那一行自带例外，一份正文两种用法都对，没有人需要记得删任何东西。** 标准写法见上方补充三「标准写法」块，全文照抄：

```
开工第一件事：调 mcp__ccd_session_mgmt__set_session_title（session_id 传字面量 "self"），标题：[Win]MMDDX-<主题短名>。🔴 例外：你若是被 Task/Agent 起的子任务，跳过本行不要执行——子任务没有自己的 session，"self" 会解析到父 session、把调度你的那条会话改名（2026-08-28 实撞）。
```

**为什么这样就够（这句是本条的核心）**：🔑 **被复制的单位是「那一行」，不是「那条规则」。** 把前提写在模板库或看护件里，它只在有人去读那份文件时才存在；写进那一行本身，**任何复制它的人都会连前提一起复制**，而执行者每次都会读到。⇒ **人守的位置从「派工者要记得删」挪成了「起草者要写对那一行」，而起草那一行本来就要照抄标准写法** —— 条件被消掉了。

**兜底（保留，但已降为冗余）**：派工者若仍想删掉那一行再传，也对；**但不再要求他记得**。

**机制守（待建，已登记 §一 `#284`）**：给 opener 块 lint 一次收两个失效形态 —— ① 块内含 `【设置】` 而**无** `set_session_title` ⇒ 告警（旧形态，一天欠 17 次）；② 块内**有** `set_session_title` 而**无**子任务例外句 ⇒ 告警（新形态）。

🔑 **本条真正要留下的判据（比这一行本身耐用）**：**一条「原样照搬」的指令，会把被搬内容里的隐含前提一起搬过去。** 那行 `set_session_title` 的隐含前提是「执行者拥有自己的 session」；换了执行形态，前提不再成立，而**原样照搬时没有任何一步会去检查这个前提**。⇒ **凡一条指令带隐含前提，就把前提写进那条指令本身，而不是写进一份可能不被读的规则** —— 指令会被复制，规则不会跟着走。

⚠️ **补救**：对被改名的 session 说一句「请调 `mcp__ccd_session_mgmt__set_session_title`（`session_id` 传字面量 `"self"`），标题：`[Win]MMDDX-<主题短名>`」即可改回；已在跑的子任务不必重开。

---

#### 🔴 补充二：开场词必带「开工前查同题 session」一步（Shao Peishen 2026-08-26 实地撞出，硬规则）

**成因**：`OP-0826-N` 的开场词被先后粘了两次（14:25 无编号版、14:52 带编号版），**两个 CC 各自建了 worktree、各自开始改同一批文件**——而那批文件正是 `工具-共享文档编辑锁.py` 与 `工具-队列结构lint.py`，**即它们自己回写队列时要用的工具**。
发现时两者恰好都还没写主工作区、没抢编辑锁，**零损失纯属发现得早**；再晚十分钟就是两份并发改动打架。

**⇒ 凡 CC opener，正文里必须含这一步（放在「开工第一件事」之后）**：

```
开工第二件事：查是否已有同题 session 在跑 —— `git worktree list` 看有无与本件同主题的 worktree，
并核 `git -C <该 worktree> status --porcelain` 是否已有改动。若有，**停下回报，不要另起一份**。
```

**判据（给发起方，比给 CC 更重要）**：**同一个 opener 被重发时，先问一句「上一次粘出去的那个还在跑吗」**——opener 天然会被多次重发（撞车改版、范围收窄、补编号各触发一次，§〇.0 成因段已列），**每次重发都是一次并发开工的机会**。

**处置口径（2026-08-26 实测）**：两个同题 session 若都已开工，**保留产出多的那个，停零产出的那个**——编号/标题只是标签，可让在跑的那个自己 `set_session_title` 改；**产出重做不划算**。半成品一律先 `commit` 到其特性分支保住（不合 master），下次续跑前先读一遍再判断接着改还是推倒。

### 〇.1 【设置】行第四字段「工作区」（Shao Peishen 2026-07-30 定，硬规则）

🔴 **勘误（2026-09-02 `OP-0902-X`）：本节原文写「标准四字段」，那是错的，且已实际致错 ≥3 次——真实为六字段 `执行环境 ｜ 分支 ｜ worktree ｜ 工作区 ｜ session ｜ 派出线`，完整骨架见 §〇.00，本节只讲其中「工作区」一个字段的成因。** 本节写下时（2026-07-30）确实只有四个，`session` 由 §〇.11（2026-08-09）追加、`派出线` 由根 `CLAUDE.md` §5 追加，**两次追加都没有回头改这一句**，于是本节从「权威」退化成了「过时的权威」——**比没有权威更危险，因为读的人会停在这里。**

**「工作区」字段本身**：前三个字段回答"在哪写"，**它回答"写完在哪生效"**——**缺它就会出现"改完不等于生效"**。

**「工作区」怎么填**：
- **不触碰常驻服务/已部署场景** → 填 `无`（多数 Cowork 任务与纯库内 CC 任务）。
- **触碰 `.51` 已部署服务**（保供看板 8091／命令中心 8092／QD-B 8093／FI2 8094）→ 写明「须 `sync-to-server.ps1` 推送 + 重启对应计划任务 + 冒烟三件套（`/api/ping`·关键页 200·一次全量重算）+ 回滚 SOP 在位」。
- **触碰企微机器人** → 🔴 写明「须同步 `ops/wecom-service-home` worktree 后重启 `ZhuopinAibotDevListener`，并确认单实例存活」。
- **触碰定时任务 prompt**（值周巡检／拆件巡逻等）→ 写明「改的是 `C:\Users\Paul Shao\Claude\Scheduled\<task>\SKILL.md`，**仓库外、不入 git**，四步走：① 用 `update_scheduled_task` 改真身（该目录对文件工具只读）→ ② **回归自检原有纪律未丢失**（该工具是整段替换 prompt、非局部编辑，重写时极易丢旧条款）→ ③ **回镜 `0-学习与工具/定时任务源码/<taskId>.SKILL.md` 并核对内容一致**（2026-07-30 建立的版本保护，见该目录 README；回镜前扫一遍凭据；**判据用规范化逐行/逐字符比对，不得用裸文件哈希**——2026-07-31 实测两份内容逐字一致但字节数差 1055（纯换行符差异），裸哈希必然不等会沦为狼来了噪音，见队列 #188——`工具-定时任务源码备份.py::mirror_one_task` 已用 `Path.read_text()` 的通用换行符转换实现此判据，直接跑该脚本即符合要求，不需手工核对）→ ④ 登 §二 批次 + 触发 sweep」。**⚠️ 方向单向：真身 → 镜像；改镜像不生效**——这与"机器人跑 `ops/wecom-service-home` 而非 master"是同一类陷阱的镜像形态，勿踩反方向。**（2026-08-06 补，队列 #235/#188）**：`工具-落库sweep.py` 起跑段已挂载 `工具-定时任务源码备份.py`（每小时随 sweep 一并触发），检出差异会自动更正镜像+告警——手工执行上述四步仍是**唯一改真身**的路径（真身在仓库外、无法自动化），但"回镜并核对一致"这一步此后由 sweep 每小时自动兜底，手工遗漏不再永久静默。

**成因（2026-07-30 真实取证）**：`#168` 的 CC opener 初稿【设置】行只写了 `执行环境／分支／worktree`，正文也只说"服务需真实重启验证"——**漏了"机器人跑的是 `ops/wecom-service-home` 那个 checkout、不是 master"这一步**。若照初稿执行：建造 worktree 内测试全绿 → push master → 直接重启服务 → 看到 `connection_established` 正常 → **如实报告"重启验证通过"，而验证的是未改动的旧代码**。实测当时 `ops/wecom-service-home` 落后 master **50 个提交**（ahead=0），只是这 50 个恰好全是文档提交、没碰机器人代码，`queue_appender.py` 与 master 哈希才相同——**这是运气不是机制，一旦改到该文件运气立刻失效**。同类步骤在服务 CLAUDE.md 已有两次正确记载（2026-07-22 #69/#70、2026-07-27 #99 均写明"`ops/wecom-service-home` 同步后重启"），**说明这一步一直靠 CC 记得，从未进过 opener 模板**——本条即为堵住它。

**自检一问（写任何 opener 时问自己）**：*本次改动，有没有任何一份"正在跑的副本"不在我改的这个 checkout 里？* 有→写进「工作区」字段；没有→填 `无`。

### 〇.2 命名不得与执行环境标注冲突（Shao Peishen 2026-07-30 定，硬规则）

**在文件名与标题里，`CC` 和 `Cowork` 这两个词是「执行环境」的保留标识——不得用于线名、角色名、服务名或任何其他含义。**

- **成因（真实事故）**：`开场prompt-CC环境保障线-接力交接-2026-07-30.md`——"CC 环境保障线"是**线名**（为 CC 保驾的线），执行环境实为 **Cowork**。Shao Peishen 拿到时即产生疑惑，**靠读正文 Context 才判断出该开 Cowork**。标注规则本是为消除歧义而立（§〇），却因线名里裸用了 `CC` 而**被自己的命名反噬**。2026-07-30 已改名为 `开场prompt-【Cowork】环境保障线-接力交接-2026-07-30.md`。
- **规则三条**：
  1. **文件名/标题里出现 `CC`/`Cowork`，一律且只能表示执行环境**；表示执行环境时用**方括号**形式 `【CC】`／`【Cowork】`，与普通词区分。
  2. **线名一律不带执行环境词**。本线今后统一称 **「环境保障线」**（不再叫"CC 环境保障线"）；同理，业务总线、域专线、值周巡检等均不得冠 `CC`/`Cowork`。**其"为谁服务"写进定义段，不写进名字。**
  3. **历史记录不追改**（队列已完成行、审计、既往报告里的旧称保持原样）——改历史的危害大于旧称本身的歧义，且会破坏可追溯性。**本规则只约束新产出。**（Shao Peishen 2026-07-30 明确同意此取舍。）
- **存量 opener 的处置＝自然收口（Shao Peishen 2026-07-30 定）**：全库扫描发现另有 **7 份 opener 的 frontmatter 无 `执行环境` 字段**（均建于 07-27 标注规则之前，**多数已执行完毕**）。**不批量补、不为此单独立任务**——已执行完的放着不管，仍待执行的**在被认领使用的那一刻由认领方顺手补齐**（补 `执行环境` 字段 + 标题带 `【CC】`/`【Cowork】`），领完即自然收口。**⚠️ 给未来的季度清扫（R3）**：勿把这 7 份当"命名不合规"批量改名——这是刻意决定，不是遗漏。
- **推广到一般情形（Shao Peishen 2026-07-30："以后但凡容易混淆的说法都尽量避免"）**：任何**已被赋予固定含义的词**（`CC`／`Cowork`／`master`／`live`／`dry-run`／`P0-P3`／场景号 `SC*`/`FI*`/`QD-*`／批次号 `B-*`／`#编号`），**不得在同一文档体系里被借去表达第二种含义**。命名前自检一问：*这个词在本项目里已经有专属含义了吗？* 有→换词。
- **落点**：新建文件命名、opener 标题、队列行任务名、《本周计划》§A、拆件巡逻报告拟动作、交接 prompt——与 §〇 四处落点一致。

### 〇.3 开场澄清问题分四类 + 两条形态规则（Shao Peishen 2026-07-31 定，硬规则）

**成因（Shao Peishen 原话）**：*"只是 Cowork 环境保障线转场继续的话，所有信息都应该完备，是否不是每次都必须问 2-3 个问题？我们的转场 Prompt 也应该分类别对待？"* —— 此前所有 opener 一律尾附"开干前问我 2-3 个澄清"，**无论哪种转场、无论接力是否完备，数量还写死成 2-3 个**，同线续做时沦为仪式。

**🔴 但不能简单改成"同线不问"**——2026-07-31 实证：07-30 那份接力的 §四 在办清单**在 24 小时内就全面过时**（#163/#147/#97/#98 均已完成），若不核就会照过时清单干活。**在本项目的推进速度下，接力过时是常态而非异常**，故 A 类的正解是「**先自检、再就差异发问**」，不是「不问」。

#### 两条形态规则（适用全部类别）

1. **禁止开放式提问**。一律给**带推荐项的选择题**，每项写清**选项之间的实际差异与各自代价**（同 CLAUDE.md §5「会话末显式罗列决策项」口径）。反例＝"你想让我做什么／有什么要补充的"。
2. **数量随差异数量走，不写死 2-3 个**。全部自检通过、无歧义 → **0 个，直接干**；有 N 处需拍板 → 就问 N 个。**"2-3 个"从此不再作为硬性数量要求，只作上限提醒**（超过 3 个说明 opener 本身没写清，应先补 opener 而不是连问一串）。

#### 四类及其提问策略

| 类别 | 判别 | 提问策略 |
|---|---|---|
| **A · 同线转场** | 本线接本线、无新任务（如环境保障线→环境保障线） | **先跑「开工自检三查」（见下），全通过即直接干、不问**；有差异则只就差异出选择题。**自检三查写在 opener 文件里**（Shao Peishen 2026-07-31 选此，非塞进 skill 统一注入——便于按线定制） |
| **B · 跨线交接** | Cowork→CC、A 线→B 线、总线派活 | **必问**。交接方与执行方对任务边界的理解常不同，且 CC 要动生产代码与部署 |
| **C · 新任务/新场景 opener** | 首次开做、无既有接力可依 | **必问**，且 opener 内应**预置候选问题**（不让执行方自己想） |
| **D · 定时任务 prompt** | 巡逻／巡检／每日提醒等 cron 驱动 | 🔴 **绝对禁止任何需要人当场回答的指令**——非交互 session **没人能回答**，写了即空转。这一类必须靠「**预案覆盖 + 歧义登 §四**」。**成因**：2026-07-31 sweep 非交互预案即同族——非交互班次没有本机 PowerShell 通道，靠踩到才补；巡逻 prompt 现状恰好没有提问句，**但那纯属惯例、规则从未写下**，若有人复制 A/B/C 类模板去建定时任务就会带进提问句 |

#### A 类「开工自检三查」（模板，A 类 opener 须内置此段）

1. **接力新鲜度**：`session接力-<本线>.md` 最新日期节 **是否等于上一次收工日**？不等 → 中间有别人动过，先读差异。
2. **清单一致性**：从 opener §四 在办清单里**抽 2 行**，与《跨桌任务队列》**实际状态列**逐字比对。不一致 → **以队列为准**，并在回复里列出差异后再问主攻方向。
3. **降级残留**：grep 四条接力文件顶部「⏳ 队列更新待补」小节，有内容 → 先回补（协议〇.7 降级路径）。

> **三查全通过** → 按 opener §四 优先级直接开工，**不提问**，只在首条回复里一句"自检三查通过，按 §四 优先级从 X 开始"。
> **任一不通过** → 就该差异出**带推荐项的选择题**，问完即干。

**落点**：本模板库 §一~§五 各范例、`zhuopin-kickoff-prompt` skill 步骤 1 与骨架、各 A 类 opener 文件正文。

### 〇.4 opener §四「在办清单」只写状态，**派单件是否存在一律开工现读**（Shao Peishen 2026-08-02 定，硬规则）

**规则**：opener 的 §四 在办清单，**只写"领取顺序 + 队列行状态 + 需要人判断的上下文"**；**凡"某某派单件已备／尚无派单件"这类可由文件系统直接回答的事实，一律不写进 opener**，改为在 §〇 自检里加一条**开工现读**：

```powershell
Get-ChildItem "1-转型规划\0-全景路线图" -Filter "开场prompt-【CC】*" -File | Select-Object Name,LastWriteTime
Get-ChildItem "1-转型规划\0-全景路线图" -Filter "opener素材*"          -File | Select-Object Name,LastWriteTime
```

**成因（2026-08-02 实证，同一形态两次）**：
- 第一次——08-02 开工自检发现 opener §四 **漏了整行 #205**（该行是 opener 写完后同一 session 内拍板产生的）。
- 第二次——同日晚 opener §四 写着"**#206 与 #208 尚无 opener，下一 session 的第一件事就是补这两份**"，而**三份派单件当时全部已在盘**（#206／#208／#205-B），队列两行正文也已写明"派单件已备"。**照它开工＝重写两份已存在的文件。**

🔴 **为什么抽查挡不住**：§〇 第 ② 条抽的是**队列状态列**，而这两次错的都是 **opener 的叙述段**——**状态列全对，过时照样躲过去**。**这是"抽查列的选法有盲区"的直接证据，不是执行不认真。**

**同源思路**：与 §〇bis「凡可由工具直读的字段一律不再写进 opener」是同一条原则，**本次证明该原则原先只覆盖到快照段（sweep 周期、高水位线），没覆盖到 §四**。

> **判据一句话**：**opener 里出现的每一个事实，先问"它会不会在我写完之后、开工之前发生变化"——会，就别写它，写"怎么现读"。**

### 〇.5 查队列行状态一律用只读 CLI，不裸读/裸截断（队列 #268，2026-08-06 业务总线自陈登记）

**成因**：2026-08-05 一天内业务总线自己 6 次"读状态列只读了一部分"（抽读行尾 420 字符 / 只读开头 40 字符），把已完成/已拍板的行当待办重提——其中两次发生在**同一天上午已把"读状态一律读完整个单元格"写进批次记录之后**。状态列动辄 800-2000 字符，任何截断读法都会在"头尾结论不一致"的行上系统性给出反向答案、且不报错（同 CLAUDE.md §5「工具静默回退」）。按规则退休制，6 次远超 3 次阈值，须机制化。

**规则**：查队列 §一/§四/§二 任意一行的当前状态，一律用：

```bash
python 0-学习与工具/工具-队列查询.py --row <编号或批次号> --section <一|二|四>
```

默认打印状态列（§四 无独立状态列，回落"事项"列）**全文、不截断**，并在开头片段与其余文本出现互斥关键词（已完成/已拍板类 vs 待领/待你审/在办类）时打印一行冲突警告。`--field all` 打印整行全部列（含领取方/触碰区等）。

**⚠️ 边界**：本条只新增只读查询通道，**不禁止**直接打开文件读——只是当"只想核对某一行现在是什么状态"时，优先用本工具而非裸 grep/裁剪片段。若未来要把它设为**强制读取通道**（禁止裸 grep 读状态），那属于改变全项目口径，须走 openspec（CLAUDE.md §5 机制类门槛第①条），本条不预先决定。

### 〇.6 写后反查三件套（队列 #255，2026-08-06）

**成因**：2026-08-05 环境保障线单 session 内 4 次违反"不信工具说成功了，写完必反查落盘"这条纯人守规则——`Edit` 对 `outputs` 报 success 但零落盘 / `Write` 对 Cowork memory 报 success 但零落盘 / 队列行插错分区。**凡是真反查了的都当场抓到了问题，凡是没反查的就漏过去了**——命中率完全取决于当时记不记得，按规则退休制须机制化。**（2026-08-06 补记）** 反查抓到的"写入位置不是预期文件"这类问题，根因不一定是工具本身失效——也可能是调用方给错了目标路径（如 git worktree 场景下，绝对路径少写了 worktree 子目录段，实际写进了另一个 checkout）。**反查的价值不因根因是哪一种而改变**，但归因时不要不假思索地默认是"工具静默失效"，先核对传给工具的路径本身对不对。**⚠️ 本节自身撰写时二度实证**（2026-08-06）：撰写本节所在这两个小节时，`Edit` 工具首次写入本文件报 success，但 `git diff` 为空、grep 找不到新内容，内容根本没落盘（同已知的"Edit 工具在 OneDrive 路径下静默失效"）——靠写后反查当场发现，改用 Python 直接读写文件才补救成功。

**轻量①（一行可复制 PowerShell 片段，任何写入动作后照抄）**：

```powershell
$before = if (Test-Path $path) { (Get-Item $path).Length } else { -1 }
# ...执行写入动作...
if (-not (Test-Path $path)) { throw "✗ 写后反查失败：$path 不存在" }
if (-not (Select-String -LiteralPath $path -Pattern ([regex]::Escape($keyword)) -Quiet)) {
    throw "✗ 写后反查失败：未在 $path 中找到预期关键词「$keyword」"
}
Write-Host "✓ 写后反查通过：$path"
```

**②工具化（可选）**：`0-学习与工具/工具-写后反查.ps1 -Path <文件> -Keyword <期望关键词> [-BeforeBytes <写前字节数>]`，返回非 0 即失败（文件不存在=1，关键词未命中=2）。已用真实场景验证：文件不存在（模拟"报 success 但零落盘"）与内容未变（模拟"写了却没写对"）两种失效均被正确拦下，返回非 0；撰写本节过程中的一次写入位置异常也是被写后反查间接捕获（见上，根因是 worktree 路径混淆，非工具本身失效）。

**⚠️ 边界**：本条只提供反查工具，**不是强制写入通道**——不要求所有写入都必须经过本脚本；若未来要把它设为绕过即拒写的强制门禁，属改变全项目口径，须走 openspec（CLAUDE.md §5 机制类门槛第①条），本条不预先决定。

### 〇.7 队列行追加一律用 `append-row` 子命令，不裸拼整行（队列 #258，2026-08-07）

**成因**：#248/#254 同一根因两次踩坑——用"全文最后一个 `# 数字` 形态的行"定位 §一 末尾，而 §四 用同样的行格式，新行插到了错的分区，且不报错，只有逐行核对分区归属才发现。

**规则**：追加一行到队列 §一/§二/§四，一律用：

```bash
python 0-学习与工具/工具-共享文档编辑锁.py append-row --who "<与 acquire 同一个 who>" --section <一|二|四> [--number N] [--domain 机|业]   --cell "字段1" --cell "字段2" ...
```

按分区列序传结构化 `--cell` 字段（不含首列编号，§一/§四 另用 `--number` 单独传，通常是 `acquire --reserve` 的返回值；§二 首个 `--cell` 即批次号）——工具负责定位分区真实末行、按分区规则拼装、校验列数，**字段值含任何竖线 `|`（不论是否反引号包裹）一律拒绝写入**，改用全角 `｜` 或改写措辞。

🔴 **取号与追行都要带 `--domain 机|业`（队列 #308 决策点 2 ／ #315 决策点 3/5；2026-08-17 补，此前本文件 `--domain` 出现 0 次）**：

```bash
# 取号（§一 新行）——域随 --reserve 一并声明
python 0-学习与工具/工具-共享文档编辑锁.py acquire --who "Cowork-业务总线-0817" --note "简短占用原因" --reserve 1 --section 一 --domain 机
# 跨分区取号
python 0-学习与工具/工具-共享文档编辑锁.py acquire --who "..." --note "..." --reserve-multi 一:1 四:2 --domain 业
```

**两处语义不同，别混**：`acquire --domain` 声明的是**新行状态列要写的 `[D:机]`／`[D:业]` 域字段**（仅对 §一 预留请求生效）；`append-row --domain` 决定的是**这一行写进哪份物理队列文件**（机制环境／业务场景）。

⚠️ **漏传的后果是"静默少算"、不是被拦下（2026-08-17 实测，勿凭直觉推断）**：
- `acquire --reserve --section 一` **不传 `--domain` 不报错、不警告**，只是回显里那行「域声明」不打印；
- `工具-队列结构lint.py` 的 CI 硬门禁**只校验状态列以 `[S:` 开头，不校验 `[D:`** ⇒ 缺域字段的 §一 行**能过 lint**；
- 真正的代价：`工具-共享文档编辑锁.py::_count_mechanism_wip` 按 `[D:机]` 计数，**缺字段的行不计入协议〇.9 措施 C 的机制类可动 WIP 分母** ⇒ 上限提示会**偏松**，而这恰恰是"改成不计数就能让数字好看"的那类逃逸口（同 2026-08-13 关于 `hold` 是否计入的拍板理由）。
- `append-row` 不传 `--domain` 则按**向后兼容默认值写入机制环境文件**并打印一行提示——业务场景行漏传会写错文件。

**反向是硬拒绝**：`acquire` 传了 `--domain` 但本次预留请求**不含 §一**，直接报用法错误并退出（不静默忽略）。

🔴 **`--who` 与三条新校验（队列 §一 #351 ⑴⑶⑷⑸，openspec 变更包 `editlock-chokepoint-six-fixes`，2026-08-23）**：

- **`--who`**：目标存在**有效锁**而 `--who` 缺失或与持锁人不符 ⇒ `append-row` **拒绝写入**。传 `acquire` 时用的同一个 `who`。**成因是 2026-08-18 那次事故**——`acquire`／`append-row`／`release` 打包成一条命令、中间不查退出码，`acquire` **已被正确拒绝**而脚本照跑照写，12 分钟内在他人锁下写入两次。**那次调用没有 `--who` 可比，所以「只在不符时拒绝」拦不住它**，故缺失也拒绝。**目标无有效锁时不要求本参数**（只打印一行提示）——本项修的是「锁归属不校验」，不是「无锁写入」，下方那条边界不变。
- **§二 文件清单路径格式**：反引号片段中形如路径者，**必须是仓库根相对完整路径**。裸文件名（如 `` `工具-落库sweep.py` ``）／绝对路径／反斜杠分隔符／`./`·`../` 前缀一律当场拒绝；**根目录文件的裸文件名放行**（`` `CLAUDE.md` `` 本身就是完整路径）；含通配的范围性写法（`` `X/tests/test_*.py` ``）放行，**不做存在性校验**。预登记批次行豁免。
- **§二 批次号前缀查重**：`B-<四位日期>_<第二段>` 撞号即拒绝，并给一个建议序号。**实测现存 174 个前缀里 27 个撞号（15.5%）**，远超立行时以为的「同族第三次」。
- **人的属性（性别代词）**：行内人名之后 25 字内出现与 `6-人才与组织/人员名录-称谓与性别-正本.md` 不符的第三人称代词 ⇒ **release 被拒绝**。逃生阀 `性别豁免：<理由>` 写在**被命中的那一行内**——**它是常态配套、不是异常出口**：实测残余命中里绝大多数是「引用规则条文本身」的行（`#351`／`§四 #75` 正文逐字写着那条判据）。

🔴 **`release` 另加一条会拦人的校验（⑹ 登记完整性）**：release 时**工作区全部脏文件都必须被某个待处理 §二 批次的文件清单覆盖**，否则**拒绝释放、锁保持占用**并逐个列出未覆盖路径。逃生阀 `登记豁免：<理由>`（写在本次 note 或本次触碰的队列行内，**不认队列全文里的历史行**）。**成因**：`OP-0822-E` 2026-08-22 acquire 的 note 写着「三份接力件定长化 分三批登记」，**那三条批次行从未出现在任何一个提交里**——`acquire` 的 note 是意图、不是事实，而 release 此前把意图当成事实放行了。⚠️ **它看的是主工作区**（编辑锁的 `REPO_ROOT` 恒解到主工作区，所有 worktree 共用一把锁），不是你当前 worktree。

**⚠️ 边界**：本条只新增结构化插入通道，**不强制**所有新行都必须走它——直接在编辑器里手写整行仍是允许的（改完仍会经既有 #225 release 校验事后把关）；若未来发现手写整行仍是高频事故来源、要把 `append-row` 提升为强制通道，属改变全项目口径，须走 openspec（CLAUDE.md §5 机制类门槛第①条），本条不预先决定。

### 〇.8 一次给出 ≥2 个 opener，必须附「次序与并行矩阵」（Shao Peishen 2026-08-07 定，两桌全局；**2026-08-08 补入本库**）

**他的原话**：「以后一个会话产生多个任务都请指明秩序和并行」。

🔴 **本条补入本库的成因值得记，它本身就是一次实证**：该规则 2026-08-07 立法、根 `CLAUDE.md` §5 已载，**但 2026-08-08 实测本库对「次序与并行」「并行矩阵」grep 全部 0 命中**——立法起从未进入 opener 的规范本身。**而这是一条关于「opener 该怎么写」的规则，规则最该在的地方没有它**；后果是除值周巡检外，所有按本库写 opener 的专线都不会知道要附矩阵。**详见 `3-治理与合规/协议与载体承载性核查-2026-08-08.md` §2.3。**

**规则（可机械化）**：凡一次回复给出 **≥2 个 opener／派单件／可开工任务**，必须附一张矩阵，逐项写明：

1. **能否立即开工** —— 零依赖／软序／硬阻塞／定时触发型**四选一**。
   ⚠️ **依赖判断以队列行状态列开头的括注自陈为准**——**本项目没有独立依赖表**，不要去找。
2. **能否与其它哪几项并行** —— 🔑 **并行判据 ＝ 触碰区是否重叠**；重叠即软序，须串行或同车。
3. **若必须串行，谁先谁后及其理由**。

**不得只把 opener 并列列出、让他自己推断先后。** opener 存在的全部意义就是复制即用、零判断，**让他做推断本身即违背设计目的**。

**自检一问**：把这几个 opener 一起发给一个没读过本次会话的人，**他能一眼说出该先开哪个、哪几个可以同时开吗？** 不能→矩阵没写够。

> **与 §〇.0 的关系**：§〇.0 管「这是哪件任务」（每个代码块前一行标题），本条管「这几件任务之间是什么关系」。**两者是同一类问题的两个形态**——都是在 opener 外层补一个字段，使读者不必推断。

### 〇.9 建行前先做「并入审核」；机制类还要看「可动 WIP」（协议〇.9／〇.10，2026-08-08 定，**同日补入本库**）

**同 §〇.8，本条也是 2026-08-08 承载性核查实测 0 命中后补入的**（本库此前对「并入审核」「可动 WIP」「〇.9」「〇.10」四组关键词全部 0 命中）。

**⑴ 并入审核（协议〇.10）—— 追加新号已由默认动作降为例外**

他的原话：「以后新建队列任务不管环境端还是业务端，不管 Co/CC，优先审核并入已有待领任务，实在无法并入任何已存在待领任务才追加序号新建」。

- **咽喉＝`acquire --reserve`**（取号那一刻正是"新建任务"发生的唯一时点）。取号前先逐条扫 §一 **全部"待领"行**（编号＋任务列首段即可），能并入的一律并入（在该行内追加子项，不新建行）。
- **无论并入还是新建，都要写一句审核结论**：「已逐条过 N 条待领行，无可并入：〈一句话理由〉」或「拟并入 #X，故本次不取号」。
- **可行性已实测**：待领池通常十余条，逐条扫读成本很低；且与 ⑵ 的 WIP 上限**互相强化**——池子小让审核不成为负担。
- **豁免**：企微机器人对来件的**自动追行属"收件登记"、不是建任务**，走独立取号路径，豁免本条；**但拆件巡逻把收件"升格为正式任务"那一步受约束**。

**⑵ 机制类可动 WIP 上限 ＝ 22（协议〇.9 措施 C；沿革 8 → 16（2026-08-09）→ 24（2026-08-19，Shao Peishen 拍板；盘点件推荐 20，同日实测「A 类四行尚未销号 ⇒ 立四条会到 23」后改定 24）→ **22（2026-08-20，A 类四行已销号、24 那条回收条款被兑现；22 ＝ 实测 N 21 ＋ 排队待立 M 0 ＋ 1 格余量，三个数都是实测不是预设）**，本库随每次调整同批更正）**

- **只约束机制/环境类行，业务场景行不受限。**
- **分母是「可动 WIP」，不是未收口总数** —— 减去三类排除：① **定时触发型**（触发日未到）；② **依赖外部方**（等专员签认／等 IT／等供应商数据）；③ **永久关闭·仅手动唤醒**（状态列以 🛑 起首）。
- 🔴 **超限时 `release` 会真的把你挡下来，不再是一行提示（2026-08-17 起生效，队列 §四 #58 ⑶，openspec 变更包 `editlock-hold-scope-and-wip-block`）**——**apply 当天的实测基数就是 23／16，已超限，所以这不是"将来某天"的事：此后任何新建机制行的 session 都会当场撞上这道门。这是预期效果，不是回归。**
  - **触发条件**：仅在**本次持锁期间真正新增了 `[D:机]` 的 §一 行**时才判。**只改既有行（含专为关行降 WIP 而做的编辑）不受影响**——若写成"release 超限即拒绝"，在存量已超限时连来关行的人都会被挡在门外，规则会把自己的解法锁死。
  - **两条出路，拒绝提示里会原样告诉你**：⑴ 先关一条既有机制类可动行（状态字段改 `[S:done]`，或让正文以 🛑 起首）使计数回到上限内；⑵ 确属紧急必须此时立行——**在本次新增行的状态列内写明 `WIP豁免：〈理由〉`，并给 `release` 加 `--force-mechanism-wip` 开关，两者缺一即仍拒绝**。
  - 🔑 **为什么理由必须写进行里、开关刻意不带理由文本**：命令行参数是会话级的、随窗口关闭即消失，而这条逃生阀要治的正是"越过之后没人知道为什么"；写在行里则进 git、被 `工具-队列结构lint.py` 与值周巡检看得见。开关只表达"我知道我在越过一条规则"这个显式意图。**一次新增多条机制行时，每条都要各自写明理由。**
- ⚠️ **② 目前无机器判据、由值周巡检人工核定**——协议〇.9 **刻意不为它造关键词猜测**（那正是 #308 要根治的形态），待 #308 机器字段落地后自动排除。
- 🔑 **旧口径的教训**：曾按"未收口总数"计，导致 #309 立行时判为「15 > 8」被迫走特批例外，**而按可动口径当时仅 3 条、本不该撞限**——**一个会逼出例外的上限，例外多了规则就废了**（同 §5 规则退休制的判断标准）。

**⑶ 守卫 one-in-one-out（协议〇.9 措施 B）** —— 新增**机制类**变更包必须回答「本次退休哪一个既有守卫；若不能退，写明为何不能」。**落点是 `openspec/config.yaml` 的 propose rules**（机器咽喉），本库只作指针、不重复入法。

### 〇.10 skill「两向同步」允许降级，但欠账必须当场登记、下一次开工必被扫出（承载性核查第三批拍板项 9，Shao Peishen 2026-08-08 定）

**背景**：队列 #45 立的纪律是「skill **源码** 与 **已安装版** 必须两向一致」，但它**默认一次改动能在同一个 session 内改完两边**。2026-08-08 一天之内**两个方向各破一次**——第 3 轮补了已安装版、源码欠着（单 session 上下文预算不足）；`zhuopin-followup-letter` 则是源码早已改、已安装版欠着（自 2026-07-30 起近十天）。**⇒ 破例不是偶发，是这条纪律的常态形态。**

**⑴ 允许只改一边，但必须当场留痕**：受预算/时机所限只能改一边时，**在本次 §二 批次行内写明「反向漂移：〈skill 名〉已改〈哪一边〉、待回补〈另一边〉」**，并指定回补批次或下一 session 任务。**不得默不作声地只改一边。**

**⑵ 欠账由开工自检兜底，不靠人记得**（这才是本条的真正保障）：已安装 skill 虽不在 Windows 磁盘上，但**在 Cowork 沙箱侧有只读挂载** `.claude/skills/<name>/SKILL.md`，与源码 `0-学习与工具/skills源码/<name>/SKILL.md` **可逐行 `diff`**（跳过各自 frontmatter 后比正文）。**环境总线 opener 的开工自检因此增设第 4 查**：四份 `zhuopin-*` 全量比对，**有差即说明上一轮只改了一边**，当场回补或登记。

- **成本实测**：四份全量 diff 约 1 分钟。
- **另有一条独立通道可交叉验证**：**系统提示注入的 skill description ＝ 已安装版的 description**，可与源码 frontmatter 逐字比对。**两条通道互不相关，交叉验证优于重复同一验证。**
- ⚠️ **该挂载的刷新时机（样本少，如实登记）**：2026-08-08 实测一次 `save_skill --overwrite` 后**挂载即时刷新**（同分钟内读到新内容），故它**可以**用作写后反查；但**样本仅 1 次**，重要场合仍建议叠加 description 通道交叉验证。

**⑶ 为什么写在这里而不新造载体**：本条要防的正是"规则只增不减"，故不新立文件——**检测挂在开工自检**（每次必跑）、**登记挂在 §二 批次行**（改动必经），两处都是既有咽喉。

**⑷ 🆕 「日期初筛」——核 skill 内容时的标准第一步（承载性核查第四批拍板项 12，Shao Peishen 2026-08-09 定，选 (a)）**

⑵ 管的是「两边**内容**是否一致」，**管不了「两边都缺同一条新规则」**——那是一种两向 diff 恒为 0 的漏法。

**⇒ 核某个 skill 是否跟上了机制时，先比两个日期，再决定要不要逐条 grep**：

| 要比的两个日期 | 从哪拿 |
|---|---|
| ① 该 skill 的**末次更新时间** | 其正文顶部的版本行（`v3.1（2026-08-09…）`），或 `git log -1 -- 0-学习与工具/skills源码/<name>/SKILL.md` |
| ② 相关规则/实现的**落地时间** | 队列行日期列、`openspec/changes/archive/` 目录名、协议条目的「（XXXX-XX-XX 定）」 |

**判据一句话：② 晚于 ① 的规则，必然不在这个 skill 里——不必 grep 也知道，直接去补。** ①之前的规则才需要逐条 grep 确认。

**为什么值得写下来（两次实证，成因完全相同）**：
- **第二批**：`zhuopin-kickoff-prompt` 缺「≥2 opener 须附次序与并行矩阵」——skill 末次重打包 **2026-08-04**，规则 **2026-08-07** 才立；
- **第四批**：`zhuopin-followup-letter` 缺「G 闸只认 `📥` 前缀」——skill v3 落 **2026-08-08**，G 闸 apply **2026-08-09**。

**两次都不是疏忽，是时间顺序决定的必然。** 🔑 **本条不是新增一条要遵守的纪律，是给既有动作（第 4 查、承载性核查）提速的方法**——它**不占人守预算**，这正是它可以被写进来的理由（同 §5 规则退休制）。

### 〇.11 【设置】行第五字段「session」——每个 opener 必须写明在哪个 session 执行（Shao Peishen 2026-08-09 定，硬规则）

他的原话：「**以后有 Opener 请同时告诉我 Opener 执行 Session 明细，免得我猜测**」。

**格式**：`【设置】执行环境：CC ｜ 分支：master ｜ worktree：☑/☐ ｜ session：新开 / 续用〈现存 session 名〉`

| 取值 | 何时用 | 判据 |
|---|---|---|
| **新开**（默认） | 独立队列行、独立触碰区、不依赖任何现存对话上下文 | 绝大多数建造/环境任务 |
| **续用〈名〉** | 任务是某个**仍开着**的 session 的收尾、勘误、或依赖它才知道的中间结论 | 例：让 E2 把自己 F2 命中的 13 行登记进它自己的变更包 |
| **皆可** | 罕见；**必须写明为何无所谓**，不得用它回避判断 | —— |

🔴 **成因（2026-08-09 实例）**：E4 的 opener 写了 `worktree：☐`（因为它要在既有的 `ops/wecom-service-home` 常驻 worktree 内操作、不新建），他随即问「E4 在 E2 完成后原 E2 Session 执行？」——**`worktree` 与 `session` 是两个不同维度**：前者是**文件空间**（在哪套工作副本上改），后者是**对话上下文**（谁的记忆里执行）。`worktree：☐` 完全不蕴含"续用某个 session"，但读者极易这样读。

🔑 **本条是同一形态的第四个**：§〇（执行环境）／§〇.0（标题行）／§〇.1（工作区）／本条（session）——**四者都是"在 opener 外层补一个字段，使读者不必推断"**。判断由出口令方完成，他照抄即可（同"固化结论制"）。

**自检一问**：*把这个 opener 单独发给他，他能一眼知道该点"新建对话"还是回到某个已开着的窗口吗？* 不能→ session 字段没写够。

### 〇.12 因果断言人守条目（原"防线4"）已机制化，正文降为指针（队列 #285，2026-08-09）

"下因果断言前先问有没有一个没核的变量能同样解释"这条人守规则曾以"反面清单·防线 4"之名写在环境保障线自己的滚动接力文件里（历次滚动替换，非本库正文），已达 CLAUDE.md §5 规则退休制 3/3 阈值。**Shao Peishen 2026-08-07 拍板选 (a)：机制化**——编辑锁 `_validate_release_structure` 新增校验⑩：§一 状态列出现 P0/P1 定级时，须在同一单元格内附一处反引号包裹的证伪命令片段，缺失即拒绝 release（见 `工具-共享文档编辑锁.py` 文件头队列 #285 说明）。**边界**：只判"有没有"，判不了"对不对"，见该处实现说明。本条即该规则退休后的一行指针，正文不再复述，历史讨论见队列 #285、`环境保障线-三行机制方案定稿-285规则退休-267签字材料-203前提复检-2026-08-07.md` §一。

### 〇.13 环境治理小任务走子代理，主线只收结论一句话（2026-08-21 由 memory 索引层收割而来，OP-0821-B）

**规则**：台面清扫、孤儿 worktree 扫描、批量 grep 取证、文档台账重跑一类**环境治理小任务，派子代理（Agent 工具）去做，主线只接收一句话结论**，不把中间过程与文件清单灌回主线上下文。

**为什么**：这类任务的中间产物（几十行扫描输出、几百行 grep 命中）**对决策零价值，却按全量计入主线预算**——与 `CLAUDE.md` 顶部流水账挤占规则注意力份额是同一个病。

⚠️ **边界**：**凡结论会被写进队列或权威载体的，主线必须拿到可复核的证据**（命令＋原始输出关键行），不能只要一句「已完成」——否则就成了本项目 2026-08-21 判死的那种「只有动作、没有手段的验证声明」。**子代理省的是过程，不是证据。**

### 〇.14 工具版本漂移主动报；`zhuopin-*` skill 超出清单当场提议升级（2026-08-21 由 memory 索引层收割而来，OP-0821-B）

**两条**：① **发现本机工具链版本与记录不一致（CLI、插件、skill 已安装版 vs 源码版），主动报出来**，不等他问；② **执行中发现某个 `zhuopin-*` skill 的实际做法已超出其 SKILL.md 清单，当场提议升级该 skill**，并说明超出的是哪一条。

⚠️ **升级动作本身归 CC**（改本机工具链＝CC，见根 `CLAUDE.md` §5「中间地带」）；**Cowork 只负责发现并提议**，`save_skill` 例外——那是 Cowork 能力、CC 做不了。

### 〇.15 CC 复命取件算法与「线 vs session」术语（原根 `CLAUDE.md` §5「CC 复命零粘贴」条，2026-08-22 随 OP-0822-B 迁入）

> **规则本体与三条边界仍在 §5，未迁**（他说一句「CC 跑完了」即取件；三信源交叉验证，不一致以队列与 git 为准）。以下是执行它时才需要读的手册层：取件算法、兜底、术语与字段约定。**本节与 opener 纪律直接咬合**——算法第 ⑶ 步读的正是派单件 frontmatter 的 `派出线:` 字段。

**取件算法**：🔴 **取件算法（2026-08-15 修订，Shao Peishen 拍板 (a)；替代初版「按 `LastWriteTime` 取最新」——那个写法在多 CC 并行时会静默漏读）**：**⑴ 时间窗全取，不取「最新一条」**——圈定本项目范围目录（`C--Users-Paul-Shao-OneDrive-Projects---AI--*`）下**自上次取件以来有新写入**的全部 `*.jsonl`；**⑵ 逐条归属**——读该会话**首条 `type=user` 消息**（＝他粘的开场词，实测必含【设置】行与派单件完整路径），正则提出派单件路径；**⑶ 读该派单件 frontmatter 的 `派出线:` 取得派出线名，只收与本线匹配的**；**⑷ 取件后必须回报「读到了哪几条、各自归属」**，使漏读与误收当场可见。 **三类兜底一律明说、禁止静默**：首条消息提不出派单件路径（他手打指令）／派单件无 `来源` 字段（实测覆盖 26＋2／35，早期件缺）⇒ 回落 `git log --diff-filter=A` 查该文件的建档 commit 与批次名、再不确定就问他一句／匹配到 0 条 ⇒ 明说「本线名下无新完工 CC」，不得沉默。 🔑 **归属粒度刻意定在「线」而不是「session 实例」**：`来源` 只记到线名（如 `Cowork 环境总线`），**这不是精度不足而是正确取舍**——他要的是「走到任一条本线 session 说一句就收本线的成果」，而**线级归属恰好使转场后的新 session 也能收到前任派出的 CC**；若键在 session id，一转场就断。**代价是同线两个并行实例会互相收到对方的 CC，已知并接受。** 📖 **术语（2026-08-15 定义，Shao Peishen 要求写死以免再对齐一次）**：**线＝长期职能岗位**（环境总线／业务总线／值周巡检／拆件巡逻／各域专线），**由一串 session 依次接力扮演**，身份载体是**文件**（接力件／队列行／派单件字段），不是 session id；**session＝一次对话实例**，有系统分配的 id、有自己的上下文窗口，**关掉即消失**。**一般情况下一条线同时只有一个 session 是 active 的**（Shao Peishen 2026-08-15 确认其实际用法）；**转场换的是 session 与接力件，线名不变**。⚠️ **`list_sessions` 显示的 `Cowork 环境总线 12` 是 session 的 UI 标签、不是线标识，不得用作归属判据**——实测 7 个拆件巡逻 session **名字完全相同、连序号都没有**，UI 名零区分度。⚠️ **线名极少数情况会改**：本项目发生过一次（`环境保障线` 2026-07-30～08-04 → `环境总线` 2026-08-08 起），**同一岗位改名、非新岗位**；归属匹配须带一张**别名表**，否则历史件归属不了。

**字段约定**：🔴 **⑶ 的字段是 `派出线:`，不是 `来源:`（2026-08-15 更正一处先前的过度断言）**：先前误以为 `来源:` 承载派出线，实测**35 份 opener 里 26 份有 `来源`，但其中只有约 7 份真正写的是 Cowork 线名**（`Cowork 环境总线 2026-08-13`／`Cowork 业务总线 2026-08-13`／`Cowork 财务专线 2026-08-06` 等），**其余写的是任务源头**（`队列 #208`／`姚祖怡 2026-08-06 回件`／`Shao Peishen … 提出`）——**`来源` 已被占用为「任务从哪来」的语义，不得一词二义**（同本节称呼纪律「已有专属含义的词不得表达第二种含义」）。**⇒ 新建派单件必须另写独立字段 `派出线:`**（值取线名，不带日期与括注）；**存量件回落两级**：先查 `来源`／`派发方` 是否恰好写了线名，否则 `git log --diff-filter=A` 取建档 commit → 批次名／编辑锁 `history.who`（实测其前缀即线名，如 `Cowork-环境总线-0815-…`）。⚠️ **本算法依赖「派单必经派单件、开场词内置其路径」这条既有纪律**（见本节「开场词与 prompt 纪律」）。

**为何是三条信源而不是一条（原 §5 同条内，同批迁入）**：**为何要三条而不是一条**：呼应「交叉验证优于重复同一验证」——且 ①②③ 恰好分别覆盖「它说了什么／它登记了什么／它真做成了什么」，正是 #221／#228／#310／#335／#162 那族事故（说部署了但没合入 master）反复漏掉的那一层。 **① 相对 ②③ 的独有价值**：**CC 中途失败或没走到收工时，队列行根本还没写，但 transcript 已经有了**——2026-08-13 即靠此读到 CC 自陈的 `git worktree remove` 非原子事故原文，成为当日改写协议〇.5 的依据来源。

**成因与取证（原 §5 同条内，同批迁入）**：📌 **成因与取证**：2026-08-13 他要求引入 Mac 端已实现的 session 通信以消除复命粘贴；**实测否掉了那条路**——官方文档 Availability 段明写「**Claude Code doesn't offer cross-session messaging on native Windows**」（仅 macOS/Linux 含 WSL2），而本机是原生 Windows 安装（`~/.local/bin/claude.exe`）；**且该功能是 CC↔CC，本就不覆盖 Cowork↔CC 这一棒**。真正可用的通道是上述磁盘直读，**零新增载体、零新增代码**（刻意不建 `.claude/handoff/` 与 `hoff.ps1`，避免制造第二份副本）。详见 `1-转型规划/0-全景路线图/session间通信通道-实测与方案定稿-2026-08-13.md` 与队列 #328⑥。

### 〇.16 收工时若某个变更包**这次不归档**，理由必须写在机器认得的地方（队列 §四 #87 ⑶，OP-0823-F，2026-08-23）

**规则**：收工时一个变更包 tasks 没勾完、这次不 archive，**光在 tasks 行内写「本次不做，前置条件未满足」是不够的** —— 那行字机器读不到，sweep 的滞留告警会照样把它报成「疑似遗忘归档」。**必须同时用下面三个入口之一声明**（三条现成、已实现良久，缺的只是没人知道有它们）：

| 入口 | 写法 | 语义 | 什么时候用 |
|---|---|---|---|
| **文本标记** | 在 `proposal.md`／`design.md`／`tasks.md` 任一处写 `暂不归档` | **作者对未来的永久声明** | 明知这包长期不会归档 |
| **观察窗口** | 同上三处写 `预期观察窗口：N 天` | 命中即报「🔭 观察中（已等 X 天／窗口 N 天）」、**不计异常**，超窗才升级 | 在等一件会自然发生的事（真实外网中断、真实拒绝一次），能估出大概多久 |
| **指纹确认** | 跑 `工具-落库sweep.py --ack-stale-change <包名> --note <依据>` | **复核者对过去某一刻的确认**，带 `done/total` 指纹，**tasks 一有新勾选即自动失效** | 你是复核者不是作者；或不确定要等多久，只想确认「我看过了，现在这样是对的」 |

🔴 **`--note` 不可省**（空则拒绝）——它就是这条声明的依据本身。

**成因（值得记住的是这一条，不是上面那张表）**：2026-08-23 那轮告警 **4 报 3 误**。查下去发现被误报的三个包**都把理由写了，写在 tasks 未勾项的行内，写得比机制要求的还详细，只是没写在机器认得的地方**；而 `暂不归档` 在这三个包里 **0 命中**。⇒ **机制是好使的，正反例就摆在同一轮告警里**（唯一没被误报的那个，正是因为它写了「预期观察窗口：14 天」）。**缺的从来不是机制，是「有这三个入口」这件事此前不在任何一份收工纪律里**——实测三个词在本库与根 `CLAUDE.md` 全部 0 命中。

⚠️ **不要指望靠写得更清楚来绕过** ——「本次不做」这种话随手就能写，若让机制去认自然语言，降噪就变成了默认。**要求一个特定字符串正是它有价值的地方。**

✅ **2026-08-23 起 sweep 已能分三类**（变更包 `auto-archive-substantive-complete`）：「只差归档这一步」（真遗忘）／「作者已写明理由但未用机器认得的入口」（会连同上表三条入口一起印在告警正文里）／「尚有 N 条真未完项」（不叫遗忘归档）。**判定器＝`0-学习与工具/工具-变更包自动归档.py`，它只判定、不归档。**

⚠️ **一条被撤销的规则，记在这里免得再被提出来**：原派单件曾要求「**archive 动作不写进 tasks**」（理由：它是流程动作不是交付项，写进去造成死锁）。**该前提已被实测推翻两次**——⑴ 归档一直在发生（`openspec/changes/archive/` 下 50 个包，39 个归档时是 N/N）；⑵ **那条 archive 行正是作者写「为什么还不能归档」的实际载体**。**禁掉它等于拆掉一个正在起作用的载体，故不禁。**

### 〇.17 多任务派发默认出「**CC Desktop 看护版**」，不出 headless 批处理版（Shao Peishen 2026-08-26 定，硬规则）

**规则**：凡一次要派出 **≥2 条 CC 任务**（波次／泳道批／建造批），**默认产出形态＝一份供他在 Claude Code Desktop 里粘贴执行的「看护件」**，**不再默认产出 `工具-opener批处理执行v2.ps1` 消费的无头波次计划**。他的原话：「**我希望以后出 CC 版看护，我希望在 CC Desktop 里执行**」。

**两种形态的实际差别**（不是包装差别，每一条都改变产出内容）：

| | headless 批处理（`工具-opener批处理执行v2.ps1`） | 🔴 **CC Desktop 看护版（此后默认）** |
|---|---|---|
| 谁在场 | 无人。凡需拍板处只能「登记后停在该点」 | **他在场** ⇒ 需拍板处**当场问**，不必登记后停 |
| 编号 | 必须 `A1…An`（runner 只认 `^###\s+(A\d+)`，自造编号解析为零条） | 用本库 §〇.0 的正常编号（`OP-MMDD-X`），无格式约束 |
| 权限 | `--dangerously-skip-permissions` 全自动 | 正常交互授权 |
| 并发 | 泳道并行，可同时 N 个写手 | **默认串行**；要并行由他自己再开一个 CC 窗口 |
| 成败判定 | 退出码 ＋ `OPENER_DONE`／`OPENER_PARTIAL` 哨兵双指标 | **不需要哨兵**——他看得见 |
| sweep | 🔴 **要先停**（并发写手会让整点 sweep 提交半成品；改 sweep／编辑锁的任务更会撞上正在跑的自己） | **不必停**——单写手、有人看着 |

🔑 **最后一行是这条规则最实际的收益**：2026-08-26 那一整套「停 sweep→跑波次→手动收口→提权恢复→建提醒任务防忘」的流程，**全部是 12 个并发无头写手逼出来的**。换成看护版，这条链子整根不需要存在。**⇒ 出看护版时不要顺手把「先停 sweep」也抄过去。**

**看护件应当包含**（形态待首次实际产出时定稿，先记要点）：① 全量任务表 ＋ 次序与并行矩阵（§〇.8 照旧适用）；② 每条任务的 opener 正文，按建议次序排列；③ 🔴 **硬序显式写在看护件里**（如「B 必须等 A 收工合入后再开」），因为看护版没有泳道机制替你保证——**次序此后靠他和看护 session 执行，不靠 runner**；④ 每条注明预计触碰区，便于他判断能否另开窗口并行。

⚠️ **例外**：他明示要无头批处理时才出波次计划（如长时间离机、off-LAN 夜间批）。**默认不问就是看护版。**

📌 **既有件**：`1-转型规划/0-全景路线图/建造波次-2026-08-26-泳道版.md` 是本规则**定下之前**的最后一份无头波次计划（12 条／9 泳道，`-DryRun` 通过但他决定「这次算了」不跑）。**保留作历史，不作模板**。

### 〇.18 命令块「执行端」标签 —— 默认 CC Desktop，**Terminal 只留给提权**（Shao Peishen 2026-08-26 定，硬规则）

**他的原话**：「**如果你 CC 启动我还可以 remote-control，下次一定记住，只有提权任务用 Terminal。**」

**⇒ 这是 §〇.17（多任务派发默认出 CC Desktop 看护版）背后的真正理由**，比那条规则本身更该被记住：**CC Desktop 起的 session 他可以远程接管**（Claude Code Remote Control，Max 订阅、可用性已在队列 §一 #170 确认），而**从 Terminal 敲出去的批处理谁也接管不了**——人不在机器旁边就只能等它跑完。**「能不能被远程接管」是这两种启动方式的实质差别，不是习惯差别。**

**规则**：凡给他命令块，一律带一行执行端标签，且**按下表选默认档**：

| 标签 | 什么时候用 | 备注 |
|---|---|---|
| **`▶ 执行端：CC`**（默认） | **凡不需要提权的动作，一律走这一档** —— 建造、测试、只读取证、跑脚本、git 操作、批量改档 | 🔴 **他可以 remote-control 接管**；这是默认，不必解释 |
| `▶ 执行端：管理员 PowerShell` | **只有真需要提权时** —— 计划任务 `Register`／`Enable`／`Disable`（S4U 任务需 SeTcbPrivilege）、`robocopy /COPYALL`（需 SeSecurityPrivilege）、改系统级配置 | 🔴 **必附一句理由**，写清是哪个特权 |
| `▶ 执行端：我来跑，你不用管` | 只读取证，我自己经本机通道跑完直接给结论 | 不要让他跑他不必跑的东西 |

🔴 **「普通 PowerShell」这一档此后基本不该出现** —— 一个不需要提权的命令，没有理由要他开一个不能被接管的终端窗口去敲。**若你正要写「▶ 执行端：普通 PowerShell」，先问一句：这件事为什么不能交给 CC？** 答不上来就改成 `▶ 执行端：CC`。

**自检一问**：*这条命令块如果跑到一半他离开电脑了，他还能接管吗？* 不能，且它并不需要提权 ⇒ 档位选错了。

📌 **成因（值得记一笔）**：本规则在 2026-08-26 之前**只活在每棒接力件的 §五 里**，而接力件是定长交接卡、每棒收工覆盖重写 —— 实测本库与根 `CLAUDE.md` 对「执行端」三字**全部 0 命中**。⇒ **它一直靠「上一棒恰好抄了下来」在传递**。本条把规则本体一并迁进正本，与「规则只活在报告文本、没有承接行」那一族同处置。

### 〇.19 **opener 是一次性动作，不是状态——已派出的 opener 不得在后续回复里重贴**（Shao Peishen 2026-09-01 当场拦下，`OP-0901-E` 实犯；人守违反计数 **1/3**）

🔴 **定性（Shao Peishen 2026-09-01 二次纠正，首版定性过轻，此处为准）**：**这不是「排版重复」或「呈现层问题」，这是一次真实的重复派工。** 那是一条**已经被他执行过的、完全合格的 CC opener**，我**原样又发了一遍** —— **一条指令发第二次，语义就是「再做一次」**。他的原话：「第一遍你给我，我已经发出，你还是原样再给我一遍，要我再次执行，**以前从来没有发生过，请你很重视**。」

🔑 **危害的真正落点不是「看着重复」，是他会真的再执行一遍** —— 因为**他对本项目每一个 opener 的默认前提是「给我的就是要我做的」**。那个前提是本项目全部派工得以低摩擦运转的基础；破坏它一次，此后他每收到一个 opener 都得先自己回想「这个是不是给过了」，**派工成本从此永久上升**。

⚠️ **「以前从来没有发生过」这句必须记下来**：本条是**新失效形态、不是老问题复发**，没有历史计数可参考 ⇒ **从严处理，不等 3/3 阈值**（见下方「提前机制化」）。

**事故经过**：`OP-0901-E` 在两次连续回复的「你要做的动作」小节里贴了同一个 `[OP-0901-G]`——编号、`【设置】` 行、正文**逐字相同**。**本次零损害**（他没开第二个，取证确认两条批次 commit 正常落地、工作区干净），但若照贴执行，就会出现**两个自称 `OP-0901-G` 的 session 抢同一批 §二 批次**。

🔑 **成因**：写「你要做的动作」这一节时，做法是**从头重新罗列当前所有待办**，于是 opener 作为「待办的一部分」跟着被重列。**但 opener 不是状态、是动作**——状态可以反复陈述而无害，**动作重述一次就是重派一次**。

🔴 **规则**：**一个 opener 只贴一次。** 后续回复要提它，**只许写一行状态**（如「`OP-0901-G` 已派出、等其回报」），**不得再出现代码块**。

**自检一问（写完「你要做的动作」这一节后问自己）**：*这一节里的每个代码块，他是不是还没做过？做过的，只留一行状态。*

⚠️ **与「编号是跨会话唯一身份」（本节补充三）互为表里**：**正因为编号唯一，重贴同一编号才格外危险**——两个 session 会带着同一个身份跑，**队列锁、批次行、`来源`／`派出线` 字段全都无法区分它们**，而 `#396` 已实证「同一件活被反复派出」这一族的代价。

### 🔴 提前机制化（不等 3/3 阈值）——**把「他执行了没有」变成一个必须填的字段**

**只写「自检一问」是不够的**：那要求写的人**记得去问自己**，而正是「从头重列待办」这个动作让人想不起来问。⇒ 按本库补充三之三已验证过的根治手法——**把前提焊进那一行**。

🔴 **凡给出 opener 代码块，块的正上方必须先写一行状态标记，四选一**：

```
▶ 首次派出：[OP-MMDD-X]
▶ 更新版（你尚未执行）：[OP-MMDD-X] —— 以这一份为准，上一版作废
▶ 重发（你已执行过）：[OP-MMDD-X]（原因：…）
```

（第四态不写标记：**判不准他执行了没有 ⇒ 先问一句，不发块。**）

🔑 **判据的参照物是「他执行了没有」，不是「这个编号出现过没有」**（Shao Peishen 2026-09-01 补正）：

| 情形 | 处置 | 为什么 |
|---|---|---|
| 新任务 | `▶ 首次派出` ＋ 新编号 ＋ 完整块 | —— |
| **已给出、他还没发出，因新情况需改内容** | **`▶ 更新版` ＋ 沿用老编号 ＋ 完整块** | 🔴 **完全正当**。**编号是「这件活」的身份，不是「这次发言」的身份**——活没变、只是描述更准了，编号就该沿用；反之若活本身变了，才该换编号 |
| **他已执行，内容一字未改** | 🔴 **禁止**，只写一行状态 | 本条事故形态：**已执行的指令再发一次 ＝ 要他再做一次** |
| 他已执行，但确需重跑（他说没收到／原 session 已死） | `▶ 重发` ＋ 正文首句写明「若你已跑过这条，忽略本次」 | 把幂等判断交回给他，不假设他记得 |
| **判不准他执行了没有** | **先问一句「G 你发出了吗」，不发块** | 不确定时发块 ＝ 赌他没执行，赌输的代价是重复派工 |

**为什么这样就够**：这一行**逼你对「他执行到哪一步」做一次显式断言**。第三态那行写不出来——你只能写「重发」，**而写下「重发」的那一刻，矛盾当场对你自己显形**（你会立刻想起他已经在跑了）。**判断从「要记得检查」变成了「必须填的字段」**，同 `set_session_title` 那一行的思路。

📌 **可 lint 化落点（写代码时用）**：同一会话内已出现过的 `[OP-MMDD-X]` 编号再次出现在代码块里、**且块前无状态标记** ⇒ 告警。纯文本匹配，成本极低；**注意不能一见重复编号就报**，否则会把正当的「更新版」一起拦掉——**这正是首版规则只写「不许做 X」、没写「但 Y 照旧」的同一个坑**。

🔴 **边界（本条立起来的当天就被反向滥用一次，Shao Peishen 当场问「为什么新开 CC 又不用 opener 模板了？」）**：

**本条只管「同一个 opener 的第二次」，完全不管「新任务的第一次」。**

- **同一编号第二次出现** ⇒ 禁，只写一行状态。
- **新任务、新编号** ⇒ **照常给完整 opener 块**（标题行 ＋ `【设置】` 五字段 ＋ `set_session_title` 整行 ＋ 正文），**一个字都不许省**。

**实犯**：`OP-0901-E` 在立完本条的同一次回复里，把一个全新批次的派单写成了一句散文「新开 CC，取 §二 批次 … commit + push」，**没有编号、没有 `【设置】` 行、没有 `set_session_title`** —— 等于把拼 opener 的活推给了他。

🔑 **判据（比本条更耐用的那一层）**：**为纠正一次违规而立的规则，最容易在下一次被过度适用** —— 因为立规则的人此刻对「违规方向」高度敏感，会不自觉地朝反方向多走一步。**⇒ 写下一条禁令时，必须同时写清「它不管什么」**；只写「不许做 X」而不写「但 Y 照旧」，下一次就会连 Y 一起停掉。

~~~

---

## 【附录 K · 跟进 README 机制正文去 provenance 前全文存档 —— 2026-09-04（Cowork 环境总线瘦身线，方案＝构建环境瘦身第二轮-方案-2026-09-04.md §一 A3）】

> 承接载体（J1）：本附录承接 2026-09-04 从 `6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md` 迁出的**机制正文**全部成因／沿革／实证／原话。判据版正本＝同目录 `跟进机制-判据版.md`；本附录为原文唯一来源，原文原样、可 grep。**表格一行未动**（12 个工具读它），`## 现有跟进信清单`／`## 补件登记`／`## 企微 chatid 名录`／`## 作废…` 四节连同其表与锚点标题全部留在 README 原位。
> 迁出两段：**⑴ L10–196**（`## 命名约定` ～ `## 与其他文档的关系`，含发送状态四态语义长注、跟进节奏、第 8 步串行闸辨析）；**⑵ L401–432**（`## 起草期自检` ～ `## 材料规范`）。行尾符按本文件既有格式统一为 LF，正文字符未改一字。
> ⚠️ **迁入时发现两处既有 U+FFFD 乱码，按「原文原样」未修，在此显式标注**：⑴「已机制化（2026-08-09…）」段内 `（���� 已回件并回灌` 应为 `📥`；⑵「与其他文档的关系」段内「导航层（本月�什么）」应为「做」。判据版已按正确字面重写，**原文段的修复另行处理、不在本批**。

~~~markdown
## 命名约定

`部门-姓名-跟进-YYYY-MM-DD-主要事项.md`

姓名未实名前用角色代称（专员/对接人），实名后新信用真名（已发旧信不改名）。

**输出格式（Paul 2026-07-06 定，标配）**：每封跟进信**同时出 `.md` + `.docx`**（`.docx` 用 md-to-word 生成，专员打开/打印/执行更友好）。Cowork 写好 `.md` 后当场跑 md2word 出同名 `.docx`。**（Paul 2026-07-23 补）凡发给唐燕萍的信及其附件一律 Word 格式；按标配所有专员信同此。**

**落款签名（Paul 2026-07-23 定，全局）**：凡以 Paul 名义发出的信，落款一律用 **「—— OPVP Shao Peishen」**（防重名），**不再用「—— Paul」**。已发出的信不追改（如 2026-07-22 及更早信保留原落款）。~~`zhuopin-followup-letter` skill 仍默认「Paul 落款」，下次重打包时更新为本签名。~~ ✅ **该欠账已清（2026-08-21 OP-0821-B 实测校正）**：skill 源码 `0-学习与工具/skills源码/zhuopin-followup-letter/SKILL.md` 中「OPVP Shao Peishen」命中 1、「—— Paul」命中 0。⚠️ **欠账早已清、这句话却一直挂着**——同属本项目反复记的载体漂移，**清欠账时须回改记录它的那一处**。

**跟进信按部门连续编号（Shao Peishen 2026-07-31 定，全局，2026-07-31 生效，回溯编号续接历史）**：每封**已发出**的跟进信在下表"编号"列标注 `部门#N`（如 `财务部#9`），按该部门实际发送时间连续递增，跨收信人共用同一计数器（同部门换人不重置）；**未发出/待发/已作废的信不占号**，等真正发出时才编号。历史 29 封已按发送时间回溯编号（财务部#1-8/采购部#1-9/质量部#1-5/IT部#1-5，销售部尚无已发信、暂无编号）。**文件名不追改**（"已发旧信不改名"仍是硬规则，编号只体现在本 README 表格与信件正文抬头，不进文件名，避免历史链接失效）；**新信正文抬头**建议注明"（部门跟进信第 N 封）"方便专员/Paul 口头引用。当前各部门下一个可用号（🔴 **2026-08-18 第三次校准，见本段末**）：**财务部#14**（#13 已于 2026-08-18 07:13 UTC 推送，**需回复、待唐燕萍回件，串行闸锁着**）、**采购部#20**（🔴 **2026-08-26 校准（CC/OP-0826-Q）**：`采购部#19` 已于本日起草、状态 `⏳ 待你审`，`python 0-学习与工具/工具-跟进闸查询.py --to 姚祖怡` 实测输出已推进到 **采购部#20**——该工具只按下表实际 `#N` 最大值推算、**不看是否已发出**，故起草即推号；⚠️ **若本信最终未发出或作废，#19 号位随之释放**，届时仍以该工具输出为准、勿据本段回填。 ━━━ 原 2026-08-25 校准原文保留 ━━━ 🔴 **2026-08-25 校准 —— 同族第六次复发，由队列 §一 #399／#400 apply 抓获**：`采购部#18` 已于 2026-08-24 22:16 UTC 推送**即已占号**，而本段仍写「下一个可用号＝采购部#18」、下表该行「编号」列仍挂着「（待你审，暂不占号）」括注 ⇒ **两份副本又一次互相印证着一起错**。本轮处置：⑴ 下表括注已由 #400 新判据 `strip_unnumbered_annotation` 实跑剥除（只剥括注、不改编号数值，剥后幂等已复验）；⑵ 本段值按 `python 0-学习与工具/工具-跟进闸查询.py --to 姚祖怡` 的实测输出校准为 **采购部#19**。🔴 **此后本段只作人读摘要，取号一律以该工具输出为准**——它只按下表实际 `#N` 最大值推算、不受括注影响，是本仓库唯一不会因「两份自由文本副本」而失真的口径。 ━━━ 原 2026-08-21 校准原文保留：**同族第四次复发**：#16 已于 2026-08-20 转 `📥 已回件并回灌`、串行闸开，**#17 随即于 2026-08-20 12:20 UTC 推送**，本段与下表 #17 行「编号」列却双双停在旧态、仍写「拟占 #17／待发暂不占号」 ⇒ 下一棒若照旧段取号会撞上已用号。前三次复发的成因诊断是「本段是自由文本、无机器判据覆盖」，**本次证明该诊断不完整——下表的「编号」列同样是自由文本、同样没被 `_validate_followup_readme_release` 覆盖，它只看「发送状态」列**；⇒ 失真的不是一处而是两处，且两处会互相印证着一起错。已并入本文件既有的 lint 评估建议。**现状**：#17 已推送、**需回复、待姚祖怡回件，串行闸重新锁上**）、**质量部#10**（🔴 **2026-08-25 拆件巡逻第二班校准——本段与下表编号列滞后同族第五次复发**：**#9 已于 2026-08-24 22:16 UTC 推送（即占号）、2026-08-25 回件并由本班回灌转 `📥`** ⇒ **陈忱串行闸开**，下一可用号 **质量部#10**；下表 #9 行头的「（待你审，暂不占号）」旧标签已同批摘除。原 2026-08-21 校准原文保留：**#8 已于 2026-08-20 03:01 UTC 推送、并于 2026-08-21 转 `📥 已回件并回灌`** ⇒ 已占号、**陈忱串行闸开**；**#9 已于 2026-08-21 起草、状态 `⏳ 待你审`，未发出故暂不占号**。 📌 **本次改本段是有意的、不是顺手**——本段与下表「编号」列是同一事实的两份副本，2026-08-10／08-12／08-18／08-21 已四次因「只改下表、漏改本段」而失真，**下表加行必改本段**。 ━━━ **原文保留供追溯**：#7 已于 2026-08-18 06:53 UTC 推送，形态＝`✅ 无需回复`、发出即闭环，串行闸对陈忱语义上已开；⚠️ 但机器判据 `_validate_followup_readme_release` 仍只认 `📥` 前缀，起草时须走 `串行豁免：`——**#9 起草时已无此需要**，因 #8 已是真 `📥`）、**IT部#10**（#9 已于 2026-08-18 07:23 UTC 推送，**需回复、待陈承回件，串行闸锁着**）、销售部#1（若销售部到岗欢迎信发出则占用 #1）。（2026-08-10 队列 #321 校准：此前财务部/采购部/质量部三处提示均滞后于下表实际发送状态，本次一并更新）（🔴 **2026-08-12 环境总线二次校准 —— 同族第二次复发**：采购部与 IT部 两处提示仍停留在「在途草稿预占／待发」的旧态，而两封均已于 2026-08-11 01:30 UTC 推送、2026-08-12 均已回件；同批把下表两行「编号」列的过时括注一并去掉——**该括注与状态列是同一事实的两份副本**。🔑 **本段与下表状态列同理，改一处必改另一处**；两次复发均为只改下表、漏改本段。）（🔴 **2026-08-18 Cowork 全景路线图线三次校准 —— 同族第三次复发，且这次一次错了四个部门**：08-18 当日六封信发出（质量部#7／IT部#9／财务部#13／采购部#15／#16 等），**下表六行均已如实登记，本段却一个字未动**，财务／采购／质量／IT 四处「下一个可用号」全部滞后 ⇒ **下一棒若照本段取号，财务、采购、IT 三处都会撞上已用号**。**⇒ 三次同形复发，机制侧一直拦不住的原因是：本段是自由文本，没有任何机器判据覆盖它**——与下表状态列不同，下表至少有 `_validate_followup_readme_release` 在 release 时看一眼。**建议随「`工具-队列结构lint.py` 加称呼判据」那条一并评估「本段 vs 下表 编号一致性」的机器校验**，两者同属「人写的自由文本进了机器要读的位置」这一族。）

**场景发布自动起草跟进信（Shao Peishen 2026-07-31 定，全局）**：CC 完成一个业务场景模块的"发布收口"（部署 `.51`+冒烟通过，见根 CLAUDE.md §5"发布即收口纪律"）后，**当场起草**一封通知该场景归属部门 AI 专员"新版已上线请试用+反馈"的跟进信（沿用本文件夹格式与编号规则），**在当次会话内提交 Shao Peishen 审核**——审核通过后由 CC 直接发送（企微机器人私信专员 + 抄送该部门群 webhook，同既有机制），不再默认转交财务/域专线代发；未获审核通过前不得发送。

**🔴 S1 · 本文件下表「发送状态」列 ＝ 一封信状态的唯一权威源（Shao Peishen 2026-08-21 答 §四 #85 选 (b) 确立，两桌全局）**：**跨桌任务队列不是信状态的载体。** 队列行里凡出现「等某某#N 闭环／待某某回件／串行闸锁着」这类**复述**，一律是**会过时的快照**，不得作为判据；队列只允许写**指针**。

- **判闸唯一入口**：`python 0-学习与工具/工具-跟进闸查询.py --to <收信人>`（S3，实现中，派单件见 `1-转型规划/0-全景路线图/派单件-【CC】跟进信状态单一可信源S2-S4-2026-08-21.md`）。**该 CLI 是派生的、不可写**，故永远不会与本表漂移。**在它上线前，判闸一律直读本表该收信人最近一行，不读队列里的任何转述。**
- **为什么不合并成一个文件**（他 2026-08-21 原议）：实测 README 与队列**不是存了同一份状态**，而是**双向交叉引用 506 处**（队列引用 `部门#N` 506 次、出现「串行闸」127 次；本文件反向引用 `§一 #N` 31 次）。**合并后那 506 处引用一处都不会消失，只是搬进同一个文件——引用只要是人写的文字就会过时，与它在哪个文件无关。** 完整论证见 `1-转型规划/0-全景路线图/跟进信状态单一可信源-架构设计-2026-08-21.md`。
- **成因（当日两次真实咬人）**：⑴ **质量部#8** 回件已拆件、已原样回灌 `§一 #340`、还派生 `§四 #83`，**而本表那格仍是 `✅ 已推送`、闸锁着**，直到被追问才由人转态；⑵ **采购部#17** 回件 2026-08-21 13:13:24 落盘、队列 13:15 自动追行，本表仍 `✅ 已推送`。🔑 **根因：机器只写队列、闸只读本表，中间那一步一直是人** ⇒ **串行闸永远不会自己开**（已立 `§一 #366`，S4 两座桥即修此）。

**🔴 跟进信串行原则（Shao Peishen 2026-08-03 定，全局，优先于并节制本文件内一切触发规则）**：**同一收信人同时只能有一封在途跟进信。** 下一封的起草前提是**前一封已收到回件且回灌消化完毕**；此时若业务判断仍需该专员或相关部门进一步反馈，才起草下一封并提交 Shao Peishen 审核后发出。**编号仍按部门连续编号**（见下条）。 **它节制上一条「场景发布自动起草跟进信」**：发布收口触发起草，但**若该专员手上仍有未回灌的在途信，则不得发出**，改为在跨桌任务队列登记「待前信闭环后发」并写明拟发要点，待前信闭环后再提交审核。 **判据（2026-08-08 拍板项 8 起可真正执行；🔴 2026-08-18 修订，见下「闭环三态」）**：本文件下方表格中该收信人**最近一封**的发送状态列**是否为 `📥 已回件并回灌 <日期>` ／ `✅ 无需回复` ／ `📨 已确认闭环 <日期>` ／ `❌ 已作废` 四者之一**——是则放行，其余四种取值（`⏳ 待你审`／`🆕 待发`／`⏸ 暂缓`／`✅ 已推送 …`）一律视为在途、**不得起草下一封**。

> 🔴 **闭环三态（Shao Peishen 2026-08-18 提出，本次修订）——原判据只认「已回件并回灌」一种闭环，在两种真实情形下失真：**
>
> **失真①：明示「不用回」的信会被永久锁死。** 实例＝**IT部#8**（2026-08-13 发出），信内明写「这件到此收口，**你不用再回了**」「不用做任何事……**不用回**」。这封信**从设计上就不会有回件**，于是永远不会转 `📥`，**陈承的串行闸被永久锁住**——而它**从来就没有占用过他**。
>
> **失真②：对方以其它形态响应、我方已确认收到，状态列却仍停在「✅ 已推送」。** 实例＝**财务部#12**（2026-08-07 发出，请她安排每日导出）：唐燕萍 **2026-08-10 已按约定投放文件并在财务部群知会**（「今天已经按要求将导出的文件放入 .51 服务器那个固定目录……请查收」，已归档 `7-外部文档/财务部/…-2026-08-10-文本反馈-7340bdb8….md`），我方机器人**当日即回**「第一份已经收到并入库了……**不用再单独知会我**」。**该信实质已闭环**，而状态列停在 `✅ 已推送`，导致 2026-08-18 值周复核误判为「已 11 天未回、我们在等她」——**方向正好反了**。
>
> 🔑 **根因是同一个：判据把「载体上的某个字样」当成了「这封信是否还占着收信人的待办」的代理，而该代理在边缘情形失真。** 真正要问的问题只有一个——**这封信现在还要不要收信人做事？** 不要，就是闭环。
>
> **⇒ 闭环合法形态扩为三种（`❌ 已作废` 另计）：**
> - **`📥 已回件并回灌 <日期>`** —— 对方正式回件、我方已消化（原有，不变）。
> - **`✅ 无需回复`（新）** —— **信件本身明示不要求对方任何动作**（纯知会／收口告知类）。**发出即闭环，从不占串行闸。**
> - **`📨 已确认闭环 <日期>`（新）** —— 对方以**其它形态**响应（群消息／放文件／口头／线下），**且我方已明确回复确认**。**以我方回复确认的那一刻为闭环时点。**
>
> 🔴 **防滥用硬约束（缺了它这套就废）**：**`✅ 无需回复` 只能在起草时判定并写进信件正文**（正文须含「不用回」类明示字样），**一律不得事后追认**。否则任何一封没人回的信都能被事后改成「无需回复」来解锁，串行闸形同虚设。**`📨 已确认闭环` 则必须能指出两样东西：对方响应的落档件（`7-外部文档/…`）＋ 我方确认的原话**，两者缺一不得转态。
>
> ⚠️ **本次只改口径，机制侧尚未跟上**：`工具-共享文档编辑锁.py::_validate_followup_readme_release` 目前仍**只认 `📥 已回件并回灌` 前缀**，新增两态在代码落地前**不会**解锁 release 门禁；过渡期确需起草时走既有逃生阀 `串行豁免：〈理由〉`。代码同步已登记为待办（属 §5 机制类触发门槛第③条「改变既有模块对外语义」，须走 openspec）。
>
> 🔑 **同批发现的一条独立教训（值得单记）**：财务部群里我方那句回复写的是「后面我们这边会做成每天自动取，**取不到会有告警**」——**说这句话的时候，那个告警还不存在**（源头断供检测 2026-08-17 才补齐，见 §四 #59）。她按「有问题你们会告警」的理解放手，结果 **08-10 之后 5 个工作日零投放而无人察觉**。⇒ **对外承诺一个机制之前，该机制必须已经存在并验证过；否则必须写成「计划中」。** 这是 #204／#221／#228 那一族（「说了但没做到」）的第四种形态——前三种是**做了没送达／没合入／没部署**，这一种是**机制还没建就先承诺了**。 ⚠️ **配套义务**：回件消化完后**必须手工把该行由 `✅ 已推送 <时刻>` 改为 `📥 已回件并回灌 <日期>`**（先占本文件编辑锁），否则下一封会被本判据无限期挡住。 **2026-08-08 之前发出的历史行**沿用旧口径（停在 `✅ 已推送`），**不追改**；判断这些历史行是否闭环时仍需人工核，遇到时**顺手改标**即可。 **成因**：多封并行会压低回件质量，并把"哪封先答"变成收信人的负担；串行也使「开放点计数」与「销点中位天数」两个度量口径保持单义。

**已机制化（2026-08-09，队列 #308 子项 G）**：上述判据此前只是文字约定，全靠人记住去查表格再动笔——现已挪进 `工具-共享文档编辑锁.py` 的 `release` 咽喉：本次持锁窗口内新增某收信人的登记行时，自动回查该收信人前一封是否已闭环（`📥 已回件并回灌` 前缀），非闭环即拒绝 release；确有必要并行时，在新增行内写明 `串行豁免：〈理由〉` 即可放行并留痕（逃生阀，避免硬拦逼出绕锁）。既有行的状态转换（如批准脚本产物）不受本项约束，历史行不追溯。

## 发送状态四态语义（跟进信发送机制化阶段二，design.md D1，2026-08-05 CC 落地；
## 2026-08-06 队列 #294 修法⑴由两态扩为三态，新增 `⏸ 暂缓`；
## 2026-08-08 承载性核查第三批拍板项 8 扩为四态，新增 `📥 已回件并回灌 <日期>`）

下表"发送状态"列此前是单态语义（起草者可直接写"🆕 待发"）——先改为两态
（design.md D1），`工具-共享文档编辑锁.py` 结构性拦截保证这条边界，不依赖
起草者自觉遵守；**2026-08-06 再扩为三态**（队列 #294）：批准后又需要暂缓
发送时，两态语义下唯一能写的只有 `🆕 待发`（终态、机制唯一认可的可发送
标记）——"暂不发"这个决定因此只能记在别处（如跨桌任务队列.md 的行内），
README 状态列却原样留在可发送标记上，`ZhuopinFollowupDispatchDaily` 照
状态列字面值执行、次日就照发了（2026-08-06 01:30 UTC 真实发生，见队列
#294）。三态语义堵的正是这个"决策与载体分离"的缺口：

- **`⏳ 待你审`** —— 草稿态，**唯一合法的起草产物**。CC 按根 CLAUDE.md §5
  第8步自动起草、Cowork 域专线手写、未来 #122 自动化起草，一律只能写这个
  值，**不得**在新增该行的同一次编辑中直接写终态。
- **`🆕 待发`** —— 终态，唯一被 `delivery.py`/`dispatch.py` 门禁②
  （`gates.assert_finalized`）认可的可发送标记，**仅能**通过批准脚本从
  `⏳ 待你审` 转换而来，不得手工改写。
- **`⏸ 暂缓`**（`readme_table.PAUSED_STATUS`，队列 #294 新增）—— 内容已
  批准、但主动暂缓发送（如同一收信人有在途未回灌的信，见上文"跟进信
  串行原则"）。**只能从 `🆕 待发` 手工改写而来**（先占本文件编辑锁，改完
  立刻 release；不经任何脚本，因为要暂缓的行此前已经过批准，不需要也
  不应该退回草稿态重走一遍审核流程）。`delivery.py`/`dispatch.py` 的
  门禁按等值断言实现（只认 `🆕 待发` 这一个值），此状态与草稿态一样被
  结构性排除在可发送范围之外——`dispatch.py` 额外把它单独识别并记入
  `DispatchOutcome.skipped_paused`+审计事件 `dispatch_skipped_paused`
  （区别于草稿态的静默跳过，因为这行"曾经批准过"，更容易被后续读者
  误当"待发"沿用旧假设）。**恢复发送时同样手工把状态列改回 `🆕 待发`**
  （先占编辑锁）——**改前建议**核实促成暂缓的前提是否已变化（如串行
  原则挡着的前一封信是否已回灌闭环），机制本身不代为判断。
  **⚠️ 已知边界（本次未做，见队列 #258）**：本次只保证"⏸ 暂缓"这个状态
  存在且被门禁结构性排除，**未**校验"队列侧决定暂缓"与"README 状态列
  确实已改成 ⏸ 暂缓"这两者是否一致——仍需操作者自觉同步两处，编辑锁
  release 时的一致性校验留给 #258。
- **`📥 已回件并回灌 <日期>`**（2026-08-08 新增，承载性核查第三批拍板项 8）
  —— **该信闭环**：专员已回件、且回件内容已回灌消化（判例已批改进口径、
  或事项已落队列/代码）。**由发出后的 `✅ 已推送 <UTC 时刻>` 手工改写而来**
  （先占本文件编辑锁），日期写本机本地日期。
  🔴 **它存在的唯一理由是让「跟进信串行原则」的判据可执行**：此前该判据写着
  "查该收信人最近一封是否已到『已回件并回灌』"，而状态列**根本没有这个态**
  ——信一推送就永久停在 `✅ 已推送 <时刻>`，判据要问的问题在载体上无法回答，
  规则看起来可机械执行、实际只能靠人记（承载性核查件 §3.6.4(2)：该形态的
  第三个变种——**规则自带的判据指向一个不存在的字段**）。
  **代价已知并接受**：每封信多一次人工改状态；**不改就等于串行原则无痕可查**。
  ⚠️ **机器侧无需改动，已实测确认**：`readme_table.py` 的状态词表只认
  `⏳ 待你审`/`🆕 待发`/`⏸ 暂缓` 三个值，**其余一律按"已推送类终态"处理**，
  故新增本态**不会**被误判为可发送（`delivery.py`/`dispatch.py` 门禁按等值
  断言只认 `🆕 待发`），也**不会**触发编辑锁 ⑥ 的暂缓一致性反向告警。

**起草前必须先占本文件的编辑锁**（否则结构性拦截不会被触发；改状态列到
`⏸ 暂缓`/从 `⏸ 暂缓` 恢复同样须先占锁，属于改本文件的一种）：
```
python 0-学习与工具/工具-共享文档编辑锁.py acquire \
  --file "6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md" \
  --who "<身份>" --note "起草跟进信"
```
改完（新增行状态列写 `⏳ 待你审`）立刻 `release`——若本次持锁窗口内新增
的行发送状态已是"🆕 待发"，release 会被直接拒绝并提示违反两态语义（该
结构校验只管"新增行"，`⏸ 暂缓` 相关的改写不受影响）。

**批准脚本 `approve_followup_letter.py`**（把草稿态转终态的唯一合法路径；
`⏳ 待你审` → `⏸ 暂缓` 或 `⏸ 暂缓` → `🆕 待发` 均不经此脚本，见上文）：
```
python 5-平台底座/wecom-aibot-service/scripts/approve_followup_letter.py \
  --readme "6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md" \
  --match-topic "<主要事项列的唯一定位关键字>" \
  --quote "<Shao Peishen 的放行原话>"
```
- `--quote` 必填——批准依据摘录写入独立于聊天记录的审计事件
  （`followup_approved`，`wecom_aibot_audit.jsonl`），即便聊天记录被压缩/
  丢失仍可核查。
- **冷却窗口**：脚本第一次"看到"某一行时只记录观测时刻并拒绝执行，须
  等 10 分钟（默认）后再次调用才会真正批准——堵住"起草→release→立刻
  批准"这种同一 actor、中间没有真人的两步连做。这挡不住存心等够时间的
  人，但把"顺手一起做掉"变成"必须刻意等一等"。

**`🔒人工发送` 标记**：硬截止交付的跟进信（起草时已知有硬性截止日期、
逾期会产生实质后果，如 #59 那类）**必须**在"交期要点"列内、紧跟截止
时间之前显式标注该标记（例如 `🔒人工发送 · 2026-07-31（本周五）前`）——
`ZhuopinFollowupDispatchDaily` 每日批处理任务对标注该标记的行结构性
跳过（即使状态已是"🆕 待发"），只能经现有人工触发路径
（`push_followup_letter.py`）发送，保证可控时限。

**机器兜底判据**（漏标安全网，不替代人工判断）：批处理任务同时会扫描
"交期要点"列，若含明确日期（严格 `YYYY-MM-DD` 格式——不识别"本周五"/
"8月初"等相对表述）且距今 < 3 天、而该行**未标** `🔒人工发送`，视为疑似
漏标硬截止，同样结构性跳过并私信 Shao Peishen 提醒核实。起草者仍须自觉
标注，机器判据只兜底"忘了标注"这一种失误，不是免责条款。

**目标文件标注（队列 #241，2026-08-05 CC 落地）**：dispatch 此前只凭
"收信人＋日期"定位对应 `.md` 文件，同一收信人同一天有多封信（如同一场景
多批交付）时必然歧义，机制会安全跳过但每天重复告警、需人工重新消歧。
**起草新行时，若同日同收信人可能有第二封（不确定也建议加）**，在"主要
事项"列末尾追加目标文件标注（固定格式，`readme_table.
build_target_file_annotation()` 生成）：

```
… → 目标文件：`部门-姓名-跟进-YYYY-MM-DD-主要事项.md`
```

dispatch 优先读取此标注直接定位；未标注的行仍回落旧的"收信人＋日期"
判据（向后兼容）。只在既有单元格内追加文本，不新增列，不影响本文件的
编辑锁结构校验。

**每日批处理任务** `ZhuopinFollowupDispatchDaily`（工作日 **09:30**，
笔记本本地，**不可迁 `.51`**——同 BotID 单实例约束）扫描全表"🆕 待发"且
未被上述规则跳过的行（🔒人工发送标记／疑似漏标硬截止／队列 #294 新增的
`⏸ 暂缓`），逐行复用 `push_followup` 发送并回填。采用"不承诺准点、只承诺
下次开机即处理"的可靠性模型（`-StartWhenAvailable`）。

## 跟进节奏（与协同一页纸配套）

- **事件驱动为主**：专员有交付 → 审核 → 需要跟进/催办/交代新事项时发一封，不为发而发。
- **月度固定触点**：月初《部门AI专员协同一页纸》刷新（Cowork 维护）+ 月底专员一句话进展；跟进信在两者之间按需穿插。
- **密集期可升为每周**：某专员进入交付密集期（如 8 月陈忱 8D 归集、8 月采购 CSV 试用）时，可按周发跟进信，命名照旧、日期区分。
- 每封信固定三要素：**做什么 / 怎么做 / 什么时候交**；随信默认附一页纸对应域节。

## 第 8 步串行闸辨析（原根 `CLAUDE.md` §5「每个场景固定流程」第 8 步内嵌长注，2026-08-22 随 OP-0822-B 迁入）

> **判据本体仍在 §5 第 8 步，未迁**（先查闸 → 闸开当场起草并只写 `⏳ 待你审` ／ 闸锁不起草改登队列；发送三条硬前置）。以下是它为什么长成这样——**两条上位规则曾在「起草」这个动作上正面对撞，本节是那次对撞的裁决记录**。

### ⑴ 为什么必须先查闸（原文原样）

🔑 **为什么必须先查闸**：旧措辞与同 §5「跟进信串行原则」（2026-08-03 定，明写优先于并节制一切触发点规则）**在「起草」这个动作上正面冲突**——一条说「当场起草」，另一条说「不得起草」；**而机器闸站在串行原则一边**：`_validate_followup_readme_release` 只认 `📥` 前缀，闸锁时往 README 加新行会被 `release` **拒绝**，除非编一条 `串行豁免：`——**那等于拿逃生阀去绕它本来要拦的那件事**。⚠️ **也不得退到「起草但不登记 README」**：skill 明确反对（写好的信会被后来的 session 当成「可以发了」）。 **成因**＝2026-08-20 CC 做队列 #334 物料看板发布收口时撞上并**主动停手**（按上位规则没起草，拟发要点写进 §一 #334）；**同族先例**＝SC2（2026-08-18）那次派单件反向明写「不要自行起草跟进信」——**说明模板口径此前已在两个方向上各写过一次，不是个别 session 的理解差异**。详见 §四 #74

### ⑶ 闸开后的送审与发送流程（原根 `CLAUDE.md` §5 第 8 步内嵌，2026-08-22 同批迁入；原文原样）

> §5 那边现在只留一句「批准后方可发送——未经批准脚本转态不得发送」。以下是被它替代的完整流程原文：

**提交 Shao Peishen 审核**，通过后由其经 `approve_followup_letter.py`（`--quote` 必填批准依据，10 分钟冷却窗口）批准转为 `🆕 待发`，此后由每日批处理任务 `ZhuopinFollowupDispatchDaily`（工作日 09:30）或人工 `push_followup_letter.py` 发送；未经批准脚本转态不得发送。

### ⑵ 发送硬前置的成因（原文原样）

**成因＝2026-08-03 队列 #228 真实事故**：SC8 修复批（#211/#212/#173）建造完成、跟进信（采购部#10）已发出并明写“打开看板看一眼即可”，但**分支与 master 已分叉 2/2 未合入、亦无任何部署留痕**——专员被请去复核的正是她自己举证的 `S04Y.0112 / R01B.0754`，**若生产仍是旧码，她看到的将是一模一样的错误数字，合理结论就是“说改好了其实没改”**，直接损伤 #67 试点反馈 loop 的信任基础。**这是同族第三次复发**：#204「问题已解决但载体未更正」／#221「代码未并 master 而生产已部署」／#228「通知已送达而生产未更新」——三者共因＝**收口最后一段（让改动真正到达使用者眼前）此前无任何机制强制，全靠执行方记得**。

> ⚠️ **迁入时发现一处称呼错误，按「原文原样」未改，在此显式标注**：上段「**专员被请去复现的正是她自己举证的 `S04Y.0112 / R01B.0754`**」中的「她」指**姚祖怡（男）**，写于名录建立（2026-08-20）之前。**本批为指针化批次，不在同一批里改规则内容**，故原文照搬；该处更正另行处理。

## 与其他文档的关系

- **总则层**（怎么做才合格）：各域就绪包/就绪清单/收口单——只在口径或方法变化时改。
- **导航层**（本月做什么）：《部门AI专员协同一页纸》——月初刷新。
- **跟踪层**（进展与催办）：本文件夹跟进信 + 各域审核报告 + `session接力-各域场景落地.md`。


## 起草期自检：第三人称代词逐个回名录核对（2026-08-22 立，血的教训）

**每封跟进信起草完成、转 docx 之前，全文搜一遍「他／她／他的／她的」，逐个回 `6-人才与组织/人员名录-称谓与性别-正本.md` 核对。**

🔴 **成因＝ 财务部#14 当天真实翻车**：正文两处把**李姣龙**写成「**他**的企微账号」，而她是女性；**信已发出、撤不回**（03:51 UTC 发出，约一小时后才拿到财务部名录）。

🔑 **这次的教训不是「又猜错了性别」，而是「明知规则仍未执行」** —— 起草那一刻，队列 `§一 #372` 行内白纸黑字写着「李姣龙…名录内无此人，按名录硬规则**一律用中性表述「该同事／其」，不得从名字推断性别**」；**我读过那一行、还在同一封信里引用了 #372 的其它内容**；同一天我甚至把这条规则亲手写进了新建的 `zhuopin-send-followup` skill 的禁止项。**规则齐备、被读到、被引用过，然后照样违反。**

**⇒ 因此本条不是「再加一条规则」，而是加一个**动作**：规则活在「知道」里没用，得活在一个**起草流程里必然会执行的检查步骤**里。判据可机械执行——**全文 `他/她` 命中数 ＞ 0 时，逐个列出并写明各自指谁、依据名录哪一行**；名录里没有这个人 ⇒ 改中性表述，不许二选一。

⚠️ **同族对照**：根 `CLAUDE.md` 记过「涉姚祖怡的行累计 244 处写成『她』」，那是**跨会话反复猜**；本次是**单次会话内、规则就在眼前**。**前者靠落档解决，后者只能靠自检动作解决**——两者是不同的病，别用同一副药。

## 材料格式路线（Paul 2026-07-26 定案，接续下节 07-22 规范）

- 🔴 **【硬约束·2026-08-20 起】凡发给 AI 专员的跟进信，一律 md ＋ docx 双件，docx 为必发项，不得只发 md**（Shao Peishen 2026-08-20 定，两桌全局）。**这条覆盖并作废下方「纯文字问答信不附 docx」那一条**（含其 2026-08-13 的「可以不附」松绑），**此后不存在「可不附」的情形**——起草即转 docx，发送即带 docx。
  - **成因（真实反馈，非预防性加规则）**：财务部#13（2026-08-18 07:13 UTC 已推送）**只发了 md**，唐燕萍无法在纯文本上批改、**也无法交给 AI 协助起草回复**；Shao Peishen 2026-08-20 原话——「财务部跟进信#13，你发了 md 版，**AI 不好编辑回复**，请重发一遍 word 版，以后的所有跟进信发 AI 专员都用 word 版」。已当日改发 Word 版补件（10:41:56 本地，aibot 私信 `tangyanping`，两帧 `errcode=0`）。
  - 🔑 **理由与 07-22「真复选框」那条不同，不要混为一谈**：那条管的是**能不能勾**（死字符点不动）；本条管的是**能不能改、能不能喂给 AI**——**纯文本信里没有任何勾选项，照样不合格**。⇒ 判据不是「这封信有没有勾选项」，而是「**有没有 docx**」。
  - ⚠️ **同族第三次复发，值得记**：采购部#16（2026-08-18）同样只发 md，姚祖怡 08-19 傍晚反馈「表内无法实现 ×和√ 的勾选」，已于 08-20 09:24 发可勾选版补件；财务部#13 是同一天、同一缺陷的**另一位专员、另一种症状**（他要勾、他要编辑）。**两次都是专员主动开口我方才发现** ⇒ 见下「机制化待办」。
  - 🔴 **存量不追补，本条只对 2026-08-20 之后起草的信生效（Shao Peishen 2026-08-20 拍板 (a)）**：当日按各信 frontmatter `编号:` 字段逐一核对后，在途且缺 docx 的**只有两封**——**IT部#9**（陈承，08-18 CommonEntity 外网开放请求）与 **质量部#6**（陈忱，08-03 未实现状态说明与 8D 归集随访）——**经拍板不补发 Word 版，维持现状**。 ⇒ 🔴 **后续 session 读到这两封缺 docx 时不要「顺手补上」**：那是**已拍板的现状，不是漏检的违规**（同下方 2026-08-13 那条「后续 session 读到时不要『纠正』」的处置精神——这类张力若不写明，只会在下一位读者眼里变成「有人没守规则」）。 📌 **财务部#13 与 采购部#16 已于 2026-08-20 当日各自补过 Word 版，不在此列**；**质量部#8 从来不缺 docx**（当日一份用「部门＋日期」配对的盘点把它与质量部#7 配错、误报为缺，已更正）。
  - 🔴 **机制化待办（尚未落地，如实登记）**：本条目前仍是**人守**规则。真正的咽喉在发送侧——`5-平台底座/wecom-aibot-service/scripts/{push_followup_letter,dispatch_followup_letters}.py`：应改为**无 docx 附件即 fail-closed 拒发**（同门禁②范式）。该改动触及既有模块对外语义，按根 `CLAUDE.md` §5「机制/工具类 openspec 触发门槛」③ **须走 openspec + design 审**，故本次未顺手改。
- **短期＝Word 真控件，能力做进 md2word 本身**（Paul 2026-07-26 定，**已落地 2026-07-27**）：md2word 识别 `☐`/`☑`/`☒`/`- [ ]`/`[x]`（含表格单元格内）直出 `w14:checkbox` 真复选框内容控件，**不另建并存工具**（队列 #76 已按此改写并完工）——专线照常写 md、照常转换即可，产出天生可勾选。真实 Word（COM 验证，非模拟）实测：Word 识别为 `wdContentControlCheckBox`、可真实点选切换、保存后状态持久化；`md2word.read_checkboxes()` 可从回收的 docx 精确解析勾选结果（含表格单元格场景）。**"死字符禁用"禁令自本次起正式作废**（不可能再产出死字符，无需再提醒过渡话术）。
- **中期＝网页表单**：判例包迁 `.51` 网页（企微点链接→按钮点选→提交入库），与看板内嵌反馈按钮同批建造（队列 #110）；届时 Word 真控件降为离线备选。
- ~~**纯文字问答信不附 docx**~~ 🔴 **本条及其下属细则自 2026-08-20 起整条作废**（被本节顶部硬约束覆盖，见上）。**原文保留在下方仅为存档**，不再具约束力；此后**不存在**「纯文字信可以不附 docx」这种情形。 ━━━ 以下为已作废原文 ━━━ **纯文字问答信不附 docx**：只需回一两句话的信（例：2026-07-26 陈承安全信）保持 md 正文即可。
  - 🔴 **本条是「可以不附」不是「不得附」（Shao Peishen 2026-08-13 拍板 (a)，随 IT部#8／采购部#14 同批）**：当次 opener 明写「输出 md＋docx 双格式」，与本条形成张力，业务总线**未自行裁决、提交定夺**，他选 (a)＝**docx 保留、照现状发**。⇒ **IT部#8（陈承）与 采购部#14（姚祖怡）两封纯文字答复信各带一份 docx，是经拍板的例外，不是漏检的违规——后续 session 读到时不要「纠正」、不要删 docx。** 与之对照，IT部#5／#6／#7 三封无 docx 的先例同样有效，**两种做法并存**：本条的约束力是「不强制附」，附与不附由起草时的 opener／场景决定。（成因：这类张力此前无落点，只会在下一位读者眼里变成「有人没守规则」。）
- 🔴 **【惯例·2026-08-22 起】每封跟进信默认抄送该收信人所属部门群**（Shao Peishen 2026-08-22 原话「把抄送相关群也做成惯例」，随 财务部#14 首发同批立）：发送时一律带 `--department <部门>`，由 `push_followup_letter.py` 经机器人 chatid 通道把同一份内容抄该部门群。**不带只在他明说「这封别抄群」时。** ⚠️ **该通道是 fail-closed 静默跳过**——部门→群 chatid 映射未配置或为空时**不报错、不打印失败**，只记一条审计就过去了；**⇒「命令跑通了」不等于「群抄送发生了」，必须到 `5-平台底座/wecom-aibot-service/reports/wecom_aibot_audit.jsonl` 看见 `followup_group_cc_delivered` 且 `errcode=0` 才算数**（同本项目「工具静默回退」那一族：只读结果太干净时，先问它是不是根本没做那件事）。📌 另有一条**自动**抄送 `ShaoPeiShen`（审计 `followup_cc_delivered`），不需传参、别重复配置。**首个实测＝财务部#14（2026-08-22 03:51 UTC），群 chatid `wrvDL_DAAAva1MWrKjLmuDWOu1BNxHaA`，四条链路 `errcode=0` 全绿。**
- 🔴 **【2026-08-22 起】发送入口新增「一句话发送」路径 —— skill `zhuopin-send-followup`**：此前发信只能由 Shao Peishen 自己开终端拼 5 个参数、或转 CC；实测 **Cowork 的本机 PowerShell 通道（Windows-MCP）跑的就是他那台机器**，脚本／Python／企微凭据／网络全在，**沙箱 bash 出网 403 的限制不适用于它**（财务部#14 即由此发出，`wss://openws.work.weixin.qq.com` 直连，**off-LAN 亦可**）。⇒ 他在 Cowork 说一句「发出财务部#14」即可，读回确认后由 Cowork 直接发送、自核审计四链路、自登记，**不需要他回帖贴执行结果**。 🔴 **该 skill 的第一条铁律是「绝不凭一句话直发」**：必须先读回「收信人＋编号＋标题＋要他办的事」等一个「发」字。**成因＝他提出该需求时的示范句就是错的**——「发出给姚祖怡的#14号信」，而 #14 是给唐燕萍的；**纯直通会把一封财务信发给采购部的人，且发信不可撤回。** 源码副本 `0-学习与工具/skills源码/zhuopin-send-followup/SKILL.md`（改动须两处同步：源码 ＋ `save_skill --overwrite`）。
- **不采纳**：PDF 表单 / Excel / 飞书·钉钉多维表（理由见《需求确认方式升级-判例批改法与微会机制-2026-07-25.md》§1.2b）。

## 材料规范：勾选类表单用真复选框控件（Paul 2026-07-22 定）

凡发给专员的**勾选/圈选类材料**（口径确认表、圈选表、预填件），docx 必须用 **Word 真复选框内容控件**（w14:checkbox，同姚祖怡 7-17 会材范式——CC 已有解析真值能力），**不得用"☐"文本字符充当**（md2word 直转的 ☐ 在 Word 里点不动，专员无法勾选——2026-07-22 对照表实例教训）。**生成能力已落地（队列 #76，2026-07-27）**：md2word 转换时原生识别 md 里的勾选标记直出真控件，专线写 md、跑 md2word 即可，无需再走过渡话术。

~~~

### 【附录 K 附篇 · `6-人才与组织/CLAUDE.md` 判据化前全文存档 —— 2026-09-04（同批 A3）】

> 承接载体（J1）：本篇承接 2026-09-04 A3 从 `6-人才与组织/CLAUDE.md`（10,499 B）迁出的全部论证、辨析、成因、原话。新版该文件只留判据与指针；本篇为原文唯一来源，原文原样、可 grep。行尾符统一为 LF，正文字符未改一字。

~~~markdown
---
status: 生效
title: "6-人才与组织 · 目录级 CLAUDE.md（跟进信纪律簇 ＋ 名录指针）"
created: 2026-08-28
用途: 承接根 `CLAUDE.md` §5 跟进信族四条的**论证、细则与成因**（判据句仍留根，全局可见）。OP-0828-Q（队列 #433 A2）建立
迁移原则: 判据句留根、论证下沉——本文件只增载体、不改判据；判据如需变更须回根 `CLAUDE.md` 改，并同步本文件
---

# 6-人才与组织 · 目录级 CLAUDE.md

> 🔴 **动本目录下任何文件（跟进信、名录、岗位说明书、招聘件）之前先读本文件。**
> 🔴 **判据句的真身仍在根 `CLAUDE.md` §5**——本文件承接的是**论证、细则、成因、辨析**。两处冲突时**以根为准**，并当场把本文件改齐。

---

## 〇、三份正本，各管一段（先认清去哪查）

| 要查什么 | 正本 |
|---|---|
| **人的属性**：姓名／性别／职务／部门／称谓 | `6-人才与组织/人员名录-称谓与性别-正本.md` |
| **发送侧**：企微 chatid、全员账号表、部门→群映射、起草期代词自检 | `6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md` |
| **信状态**：某封信到哪一步了、串行闸开没开 | 同上 README 的**「发送状态」列**（唯一权威，见 §三） |

🔴 **跨桌任务队列不是上表任何一栏的正本**——队列里出现的信状态、名录复述一律是会过时的快照，**只允许当指针，不得当判据**。

---

## 一、专员跟进纪律（Paul 2026-07-04 定，新 session 一律遵守）

**归集与命名**：跟进信统一归集 `6-人才与组织/部门AI专员跟进/`，命名 `部门-姓名-跟进-YYYY-MM-DD-主要事项.md`；每封必含三要素**做什么／怎么做／什么时候交**，随附《部门AI专员协同一页纸》对应域节，发一封在 README 清单追加一行。

**节奏**：事件驱动为主 ＋ 月度固定触点，交付密集期升每周。

**口径／需求确认唯一格式 ＝ 判例批改法（Paul 2026-07-25 拍板，全域生效）**——禁止抽象设问，一律转为 ≤10 条**真实**案例「现状判定 vs 拟改判定」对照，专员只做 ✅对／❌错／✏️改判 ＋ 一句话；规则条文由专线从判例反推、回发一行请专员确认。

**配套三条**：
- 🔴 **一信决策点无上限**（2026-08-18 拍板；通报／告知／认错类不计入决策点）。
- **默认预案分级**：纯展示类可标 48h 默认生效；**判据／口径／阈值类永不默认生效**——IATF 显式签认红线。
- **不加并行专员**（判定权威单点），人力加「一线标注层」。

**度量达标、回退闸已摘**（2026-08-23 复盘，中位 2 天）：复盘件＝`6-人才与组织/部门AI专员跟进/度量复盘-判例批改法回退闸到期-2026-08-23.md`。

**细则正本**：README-跟进机制与命名约定.md ＋ `需求确认方式升级-判例批改法与微会机制-2026-07-25.md`。

---

## 二、跟进信串行原则（Shao Peishen 2026-08-03 定，两桌全局，优先于并节制任何触发点规则）

### 判据（判据句真身在根 §5，此处复述供本目录内就地执行）

**同一收信人同时只能有一封在途跟进信。** 下一封的起草前提是**前一封已收到回件、且回灌消化完毕**；此时若从业务判断仍需该专员或相关部门进一步反馈，才起草下一封、**提交 Shao Peishen 审核后发出**。

**编号**：按部门连续编号（`部门#N`），跨收信人共用同一计数器，换人不重置，**未发出／已作废的信不占号**。

**机器判据**：跑 `python 0-学习与工具/工具-跟进闸查询.py --to <收信人>`，或直读 README 该收信人**最近一封**的发送状态列是否已到闭环形态；未到即**不得起草下一封**，改为在队列登记一行「待前信闭环后发」并写明拟发内容要点。

### 为什么它优先于「某动作完成即触发发信」类规则

**触发条件满足 ≠ 可以发，还须前一封已闭环。** 这条优先级是显式定的，不是推导出来的——因为「场景发布即起草跟进信」（根 §5 场景固定流程第 8 步）读起来像一条无条件触发规则，两条并列时如果不写明谁优先，实际执行会按后读到的那条走。

**完整辨析**见 README《第 8 步串行闸辨析》节（含过渡期安排）。

---

## 三、信状态唯一权威 ＝ 跟进信 README 的「发送状态」列（Shao Peishen 2026-08-21 答 §四 #85 选 (b)，两桌全局）

### 判据

**跨桌任务队列不是信状态的载体**——队列行里「等某某#N 闭环／待回件／闸锁着」类**复述**一律是会过时的快照，**不得作为判据**；队列只允许写指针。判闸唯一入口＝`python 0-学习与工具/工具-跟进闸查询.py --to <收信人>`（实现中，上线前一律直读 README 该收信人最近一行）。

### 成因（2026-08-21 两次咬人）

**机器只写队列、闸只读 README，中间那一步是人** ⇒ **闸永远不会自己开**。发送脚本回填的是 README，而队列行里的状态描述靠人手动同步；只要有一次没同步，队列就会告诉下一个 session 一个已经不成立的结论，而这个结论**不会报错**。

「合并成一个文件」已被实测否掉（两份载体的读写方、频率、锁粒度都不同）。**设计正本**＝`1-转型规划/0-全景路线图/跟进信状态单一可信源-架构设计-2026-08-21.md`，机制行＝队列 §一 `#366`。

---

## 四、场景发布第 8 步（起草跟进信）· 细则与辨析

> **判据句真身在根 `CLAUDE.md` §5「每个场景固定流程」第 8 步**，本节承接细则。

### 起草分支（2026-08-20 答 §四 #74 选 (a) 改定：先查闸，再决定起不起草）

判据＝查 README 中**该收信人最近一封**的发送状态列是否已到闭环形态（`📥 已回件并回灌`／`✅ 无需回复`／`📨 已确认闭环`）：

1. **闸开 ⇒ 当场起草**。README 登记行「发送状态」列**只写 `⏳ 待你审`**——**这是唯一合法的起草产物**，不得直接写终态。
2. 🔴 **闸锁 ⇒ 不起草**。改为在队列对应行**登记「待前信闭环后发」并写明拟发内容要点**，本步到此为止、不进入审核与发送流程。
3. **已起草者提交 Shao Peishen 审核，批准后方可发送**——未经批准脚本转态不得发送。

两态语义、批准脚本、`🔒人工发送` 硬截止标记与「为什么必须先查闸」的完整辨析：README《第 8 步串行闸辨析》节。

**本步不得省略**——通知与试用反馈是发布收口价值兑现的最后一环。

### 发送硬前置（Shao Peishen 2026-08-03 定 (a)，两桌全局）

**「部署冒烟通过」是发信的前置条件，不是并列步骤。** 起草、送审可先做，**发送必须等三条判据全过、缺一即不得发**：

1. 改动已 ff 合入 `master`（`git rev-list --count master..<分支>` ＝ 0）；
2. `.51` 已部署且冒烟通过（`/api/ping`／关键页 200／一次全量重算）；
3. **用专员原始举证的那个真实案例做端到端复现**——看板／页面须显示修正后的值。

⚠️ **冒烟判据本身也会骗人**：off-LAN 下 `curl` 照样返回 http_code、带口令门的服务「首页 200」返回的是登录页——**「拿到了状态码」≠「服务答了」**。判据须同时判正文形态。

机制侧强制见队列 `#229`。**本条与串行原则并列适用**——串行管前一封是否闭环，本条管这一封是否已上线，**两条都过才发**。成因见 README 该节。

---

## 五、起草期硬动作（不是规则，是步骤）

🔴 **每封跟进信起草完成、转 docx 之前，全文搜一遍「他／她／他的／她的」，逐个回 `6-人才与组织/人员名录-称谓与性别-正本.md` 核对。**

- 名录里有这个人 ⇒ **按名录写，不按名字的语感写**；
- 名录里没有 ⇒ **必须改中性表述**（「该同事／其／对方」），**不许二选一猜**，并当场问 Shao Peishen 一次补进正本。

🔑 **为什么这是一个步骤而不是一条规则**：`财务部#14` 当天，规则完整存在、被读到、被同一封信引用过，**然后照样被违反**，信已发出、撤不回。**规则约束的是「知道」，步骤约束的是「做」**；这一族错误（能猜、猜错不报错、下游无信号）只有靠步骤能拦。全文见 README《起草期自检》节。

⚠️ **一个固定泄漏点（2026-09-02 实测，连续两封命中）**：**跟进信 frontmatter 的 `源:` 字段**是代词自检的高频命中处——`质量部#12` 写「她 2026-09-01 回件…」、`IT部#11` 写「他 2026-08-24 回件…」，**指向均正确、名录均已核，但仍逐次改成实名**。⇒ **起草时那一行直接写实名，不写代词**，省掉一次自检往返。

---

### 5.2 🔴 称呼一律用全名，不用「姓＋工／总」（Shao Peishen 2026-09-02 定）

**规则**：跟进信正文的称呼（H1 标题那一句、以及正文中直呼收信人处）**一律写全名**——「陈承」「唐燕萍」「姚祖怡」「陈忱」，**不写「陈工」「唐工」「姚工」**。

**他的原话**：「以后跟进信专员的称呼『陈工』还是用全名吧，**避免同姓混淆**。」

🔑 **为什么**：本项目已有的两位专员就同姓——**陈承（IT 域，男）与陈忱（质量域，女）**，两人都是「陈工」。⚠️ 更麻烦的是**两人的名同音近形**（承／忱），一旦在群里或转述中出现「陈工」，**读的人无法从称呼本身判断是哪一位**，而两人的信内容（U9C 端点 vs 8D 评审规则）完全不相干。

**⇒ 判据**：**称呼的作用是指认一个人，不是表示客气**。当称呼在真实名单上不唯一时，它就不再指认任何人。

📌 **历史件不追改**（同根 `CLAUDE.md` 纪律）：`IT部#8`／`#10`、`财务部` 若干封已用「陈工」「唐工」发出，**保持原样**；本规则自 `IT部#11`（2026-09-02，起草期改）起生效。

⚠️ **落点在起草期，不在发送期**：发送侧的 §3 只查代词、不查称呼；**称呼错了发送流程拦不住**，所以它必须在起草时就写对。
~~~
