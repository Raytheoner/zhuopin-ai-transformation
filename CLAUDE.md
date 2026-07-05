# CLAUDE.md — 卓品智能 AI 转型（项目级记忆）

> 本文件是项目级上下文/记忆（Hermes L1）。Claude Code / Cowork 进入本仓库先读它恢复上下文。
> 全局身份/偏好见 `~/.claude/CLAUDE.md`（不重复）；本文件只写**本项目**的背景、架构、工作流与红线。
> 代码与注释用中文，技术术语保留英文；用供应链业务语言描述功能（如"齐套分析""承诺交期""在途跟踪"）。

> **当前进度（2026-06-11）**：**supplychain 收割全部完成，收割队列清空。** 已合 master —— **SC8 收割式 MVP**、§1 平台加固 P2、**O2 齐套**、**SC1 收尾**、**SC3 在途跟踪**（PR #6 rebase-merge）、**SC5 采购建议与供应商遴选 + kit_engine 底座化**（PR #7 已合 master；kit_engine 提升到 `zhuopin_platform/agents/`——SC5 是第 2 消费方、rule-of-three 真触发，O2 改 import 回归零变更；底座 114 + O2 20 + SC5 41 = 175 tests 全绿（合并时点快照，PR #8/#9 后底座实测 117，以 CI 为准不再手工滚动）；黄金值对齐 auto_total=35850/review_total=640000；IATF L1/L2 分桶审计，M015 触发 R1≥50万 待人工审核）。**supplychain 已打 tag `harvested-archive-v1` 转只读存档**（O2/SC3/SC5 三引擎 + 连接器/通知器/business_rules 已迁入全景平台）。**Phase 1 真实接入进展（2026-06-11，IT 提前供数）**：**SC8 真实切换已合 master（PR #8）**——FO+BOM 真实、内部验证不外发（CUSTOMER_OUTBOUND_ENABLED=False）、SRM 降级；**U9C 连接器收敛已合 master（PR #9）**——ZpConnector 确立为 U9C/ERP 唯一规范连接器、退役 U9CConnector、外网 OAuth2+BOM/Query 验证通可拉真实 BOM、real 模式 fail-loud（RealEndpointNotReadyError）。**未结项（详见 `1-转型规划/U9C接入与连接器收敛-待办追踪.md`）**：① 🔴 轮换 U9C client_secret（明文在归档仓 history，活凭据）；② SRM 凭据迁入本仓库 `.env` 解 900401；③ 外网开放 `CommonEntity/Query` 才能做 U9C 全量 cutover（库存/PO/MO/价格），否则 LAN/VPN；④ SC8 对客上线仍待 SRM 接通 + L2 签字（置信度/人工确认/回滚 SOP）；⑤ ErpConnector 改名（低峰期）。续工作先读上述待办追踪 + `1-转型规划/0-全景路线图/supplychain收割与全景推进策略.md`。引擎默认场景本地，第 2 消费方出现才提升（rule of three）。

> **全盘审计 + 文档治理（2026-06-13，Cowork）**：根目录已出《全盘审计与差距分析报告-2026-06-13.md》（底座/场景合规/规划依赖三路审计，发现均带文件:行号）。**P0 四项**：① TLS 校验全局关闭（erp_connector `CERT_NONE`，须先于 secret 轮换修复）；② SC8 `submit_commitment` 低风险自动外发旁路（违反 SOP §4.1/4.2，休眠炸弹，被 test_low_risk_auto_sends 正向固化）；③ audit verify_chain genesis 绕过（任意行缺 prev_hash 被当合法 genesis）；④ client_secret 轮换需硬截止。**代码修复划归 CC 三个变更包**（A 安全 P0 / B 数据正确性+审计强制化 / C SC8 上线前置：偏差监控+真实黄金回归），SC8 对客外发开关在 A2/C1/C2 完成前不得开启。**规划文档修订已由 Cowork 完成**：11 项文档不一致修正、全景规划建立 §0 修订记录机制（"正文不改"改为"可修正+强制登记"）、Phase1 架构文档加过时声明、实施计划新增 §七.2 执行治理（外部依赖红线日+10/12 月砍单规则+Q2 顺延预案+S3 缓冲管理）、新建 `3-治理与合规/OEM数据隔离规范.md`（待签发）与 `1-转型规划/0-全景路线图/待决策清单-2026-06.md`——**清单 4 项已于 2026-06-13 全部拍板（均选 A）**：D-1 SC8 深化不消费 SC6/SC7（"芯片风险→交期→通报客户"闭环移 S3，前提 SC6 稳定≥3 个月）；D-2 Q2 过渡期客诉人工录入 SOP（质量部接口人+校验脚本）；D-3 SC9 降范围 MVP（OEM 历史订单+公开车市数据）；D-4 全场景两级验收（上线验收+3 个月价值验收，指标写进 openspec proposal），落点均已回填对应文档。**阶段命名定稿（全仓统一，见全景规划 §0.1）**：Phase 1 内部 = S1 筑基期（2026-07~12）/ S2 扩面期（2027-01~06）/ S3 深化期（2027-07~12，显式缓冲）；Phase 2 = 产品工程跃升期（2028 H1）；部门内月度节奏 M1/M2/M3；"第N阶段"称谓废止。
>
> **代码修复 A/B/C 已全量并入 master（2026-06-18，ff-only，master→`3afe318`；PR #10 MERGED，#11/#12 因 ff 后零 diff 无法走合并按钮、已带说明 CLOSED，内容均已落 master 非废弃；文档收口 md/docx/xlsx/审计报告同批并入）**：**A 安全 P0（已修，PR#10）**——A1 erp_connector TLS 默认校验 + `U9C_TLS_INSECURE` 逃生开关(real 硬禁) / A2 `submit_commitment` 首道一律入队 + Notifier 第二道总开关 `outbound_enabled`(SC8 接 `CUSTOMER_OUTBOUND_ENABLED`) + 改写 test_low_risk + 修 approve 持锁重入死锁 / A3 verify_chain genesis 豁免限定第1行。**B 数据正确性+审计强制化 P1（已修，PR#11）**——B1 BOM 失败不静默(返回 (rows,failed_ids)/全失败抛错)+get_bom 走 fail-loud 闸门 / B2 SRM get_confirmed_dates 区分失败与未答交 / B3 审批分级(VP_APPROVERS+KEY_CUSTOMERS，重点客户/首次承诺→VP；金额条件 SC8 暂不可得) / B4 from_env 无 audit→warn + SC8 sources/loaders 注入审计 / B5 OEMRouter 跨库拒绝前留痕 / B6 kit_engine 在途盲区(缺快照仍计在途)+SC5 黄金值改精确相等(35850/640000/675850)。**C SC8 上线前置 P1（PR#12）**——C1 偏差监控 `sc8/deviation.py`(消费 DEVIATION_ALERT_DAYS=3，告警+重算回调+审计)**已修**；**C2 真实黄金回归＝✅已落地（2026-06-18 回 LAN，commit `d77ef4c`）**：FO 已恢复，`build_golden_real.py` 真实跑通——3 张真实订单全部 partial-无反馈→低置信🔴（SRM 看板对 BOM 子件覆盖 17/117、9/90、37/126）、无高置信/无委外样本、确定性日期逻辑手工抽验偏差=0；`real_frozen/` 自包含 `.gitignore=*` 绝不入库；启发式 v0 未改、SRM 取数口径+置信度 2级vs3级待 Paul+PMC 裁。回归：平台136/SC8 51/O2 20/SC1/SC3/SC5 全绿，黄金值不漂移。接口变更(已贯通调用方)：get_bom_for_products/get_confirmed_dates/calc_shortage 均改返回二元组。**🔴 A1（TLS 校验）已在 master，信道已修——IT 轮换 U9C client_secret 定于下周一 2026-06-22（已过 6/20 名义红线，Paul 已知并改约周一）**，先修信道再换钥匙。SC8 对客外发开关仍全程关闭，待 SRM 接通 + L2 签字方可开。
>
> **质量域规划启动（2026-06-11，Cowork off-LAN，纯规划未碰真实库）**：Paul 第二管辖域转入质量。已出 4 份文档（均在 `1-转型规划/`，AIOps 件在 `6-人才与组织/`）：①《质量域AI数字员工路线图》(8 候选 QD-A..H 打分排序、分层、§5 Q 序列修订)；②《质量旗舰PRD-Q2-8D不良分析与根因》；③《质量旗舰PRD-项目立项审核门禁》；④《AIOps第2名-Onboarding（30-60-90）与团队结构》。**旗舰选定**：QD-A 8D（全景 Q2）+ QD-B 立项门禁（全景 Q6），均 off-LAN 友好、风险可控。**已落地决策**：全景 2.1.3 Q 序列已回填修订（旗舰前置、新增 Q7 IQC/Q8 SPC、FMEA/PPAP 后置，md+docx 同步）；两 PRD 的 D1–D6 全采纳推荐（选 A），8D D3=ISO26262 安全相关走功能安全工程师额外门禁、立项 D2=财务"可机器核规则"边界待财务共识；OEM 隔离边界已扩展（见 §4，质量域含 OEM 信息的 8D/客诉按客户隔离）。质量场景开发排期与 AIOps 第 2 人到位强绑定。
>
> **SC8/SC1 真实数据口径收口（2026-06-18 回 LAN，已合 master 073117f；PR#13 recalib + PR#14 connector）**：FO 恢复后黄金基准全真实跑通（确定性偏差=0）。① SC8 承诺取数改**分层口径**（/purchase/answer 按 PO 主源 + 看板辅 + 无反馈+30 兜底，见 SOP §4.6）——子件覆盖 9/90→58/90，并暴露 S02Y.0188 瓶颈子件真实承诺 → 延期 +61→+184（看板低估被纠正，**待 PMC 核实 + 对客沟通**）；真实数据仍只命中"无反馈"类、全低置信🔴（成品全子件都有承诺不现实，低置信是对的，未为凑高置信伪造）。② SC1 交付维度过渡修正：数据不足→不评分+权重归一化（ZB0022 5→4级、0% 假象消除）；真实历史准时率待 U9C 收货历史(Receivement)（待办 #7）。③ connector 修复（PR#14）：get_demand_orders `pdrNo`→`poErpNo`（旧测试夹具同错掩盖 bug，已改真实字段+加回归）。④ FO 健康告警随 PR#13 合入（内部运维告警→audit+企微采购/值班群，非对客）。回归全绿（平台 138/SC1 53/SC8 64，含 test_golden_real 真实夹具零漂移）；**对客闸 CUSTOMER_OUTBOUND_ENABLED 全程 False**，real_frozen/+reports/+.env 经 git check-ignore 不入库。置信度仍 2 级（签字版未动）。新增待办 #9（sc5 openspec 缺 SHALL/MUST，预先存在、非阻塞）。
>
> **FO 正式库接通 + 保供看板四色 + 保供 Web 服务（2026-06-24）**：① **FO 取数口径纠错并接通正式库**——旧 `.env` 误把 `FO_API_BASE` 指向 supplychain 验证库(192.168.100.51:8800,5月陈旧数据)；正式库 webapi 原无 FO 查询接口，IT 同日交付 `GET /zp/api/ForecastOrder/Query`(apiKey 走 URL query、非 OAuth2)；loaders 已改造(新端点/分页/`Data.Rows`/PascalCase 字段/apiKey 不入异常日志/fail-loud)，真实跑通 FO2026060001/2 共 126 行/36 成品(status=2)、携客云承诺覆盖 341/1042。② **保供四色口径**(Paul 2026-06-24 定，剔除无答复估算、只看确定承诺缺口)：🔴 真延期(有承诺仍晚>3天) / 🟠 待催(子件未答复无确定承诺) / 🟡 偏紧(确定1-3天) / 🟢 按期；真实 49🔴/77🟠。③ **保供预警 Web 服务**(openspec `sc8-baoguan-web-console` 已 apply)：Flask+waitress(`sc8/webapp.py`+`scripts/run_baoguan_web.py`,默认 `0.0.0.0:8090` **LAN 无鉴权**)、进程内 `compute_snapshot`+`SnapshotStore` 缓存(reports/JSON)、手动刷新(非阻塞锁串行,防携客云限流击穿)+6h 定时后台刷新、🔴 真延期去重(稳定键 料号+单号+出货日=案例账本)推保供运维群、**保供案例处置中心**(催货→协调→改期/确认→关闭 状态机+SLA 24/48/72h,SQLite)、AI 催货/协调/对客草稿(`case_draft.py`,对客落 `CUSTOMER_OUTBOUND_ENABLED=False` 仅草稿不外发)。回归 **102 passed/2 skipped**(SC8 +27 新测试)，reports/*.db/*.json/.env 经 git check-ignore 不入库。**未结**：7.2 LAN 真实联调=Paul 现场验收(手动刷新打真实三源、🔴 推企微)；验收后加登录/Token 鉴权再开外网(待办 #10,真实客户名红线)。
> **财务域场景重编号（2026-07-03，全景路线图 Task 执行）**：财务专线定稿（Paul 确认小抄 13 项全通过）后，全景规划/实施计划/前置数据总表/甘特图已同步重排——原 FI2 智能月结拆分为 **FI2 三单匹配自动对账**（提前至 09 月）+ FI4 月结其余（2027-Q1）；原 FI4 异常交易拆分为 **FI3 付款申请自动校验**（提前至 11 月）+ FI6 异常交易其余（2027-Q2）；原 FI3/FI5/FI6/FI7/FI8 顺延为 FI5/FI7/FI8/FI9/FI10；财务 8→10、全景 40→42；FI2/FI3 治理 L3→L4 分期，FI3 的 L4 晋级 Paul+CFO 会签。前置卡口挂 7/15 双反馈门（U9C CommonEntity/Query + SRM 900401 + OCR 选型）。
> *注：本项目跨会话记忆以本 CLAUDE.md 当前进度为准（可写、每会话载入）；`.auto-memory/MEMORY.md` 自动索引在本环境只读锁定、写不进，勿依赖。*

---

## 1. 公司与项目背景

- **公司**：卓品智能科技股份 — 汽车 ECU 设计研发制造 Tier 1，直供比亚迪 / 上汽 / 理想等 OEM。
- **本项目**：18 个月企业 AI 转型（2026-07 启动），六部门并行（采购/财务/质量/销售/运营/工程研发），共 **42 个数字员工场景**（原 38，2026-06-11 质量域新增 Q7 IQC / Q8 SPC → 40；2026-07-03 财务域场景重编号，原 FI2 月结/FI4 异常交易各拆分为二 → 42，财务 8→10）。
- **决策人**：Paul（分管供应链与质量的 VP，CS + 供应链背景）。技术决策由其拍板。
- **节奏原则**：先跑通最小验证，再规模化；先 mock/脱敏，再切真实库。

## 2. 全景目标与时间线（指针）

- 权威总纲：`1-转型规划/0-全景路线图/卓品智能AI转型全景规划.md`（2026-06-13 起：正文可修正，但**必须**在其 §0.2 修订记录登记，否则视为无效修改）。
- 最新时间线 + Phase 1 修正：`1-转型规划/0-全景路线图/卓品智能AI转型实施计划（最新版）.md` 第七节。
- **U9C 已覆盖的标准功能直接用，不建 AI**；AI 只做 U9C 不覆盖或需智能增强的场景。
- Phase 1（→2026-07 底）真正能上线的只有 **SC1**（供应商风险初筛）与 **SC8**（客户订单交期智能承诺，**收割式 MVP**，7-8 月上线 — 复用 supplychain 已验证引擎，不从零搭）；其余场景被 U9C MCP（7/1 申请）/外部 API/知识库三类依赖阻塞，先在底座上做 mock 原型。
- **阶段框架（命名 2026-06-13 定稿，见全景规划 §0.1）**：当前 18 个月（2026-07 → 2027-12）= **Phase 1**（底座 + 六部门流程提速 + 供应链/质量减负，42 场景，2026-07-03 由 40 更新），内分 **S1 筑基期（2026-07~12）/ S2 扩面期（2027-01~06）/ S3 深化期（2027-07~12，显式规划缓冲）**；部门内月度节奏用 M1/M2/M3，"第N阶段"称谓废止。**Phase 2 = 产品工程跃升期（月 19-24 / 2028 H1）** = 产品工程深化候选（APQP 数字网关[质量,Paul域]、ASPICE 追溯链、HIL 日志诊断、NRE 深化），**统一 Phase-1 末（2027-12，底座稳定）评估立项、Phase 2 实现，不并入 40、不打乱 Phase 1**。详见全景规划 "Phase 2 · 产品工程跃升期" 章节 + `1-转型规划/0-全景路线图/AI候选场景增补-backlog（产品工程方向）.md`。

## 3. 仓库结构

```
企业AI转型/                         # 本仓库（GitHub: Raytheoner/zhuopin-ai-transformation）
├── 0-学习与工具/                   # 学习路径、U9C申请、衔接指南、md转Word工具（实施计划/规划审查已迁 0-全景路线图/）
├── 1-转型规划/                     # 各域转型规划、就绪、口径、专线接力/prompt
│   └── 0-全景路线图/               # ★全景规划及构建路线图档单一归集：全景规划(权威)+实施计划+甘特+前置总表+S1复盘+Phase1架构+收割策略+backlog+待决策+全盘审计+规划审查+路线图线接力/prompt；机制见《全景路线图重组机制与变更日志》
├── 2-试点项目/                     # 从采购部启动（权威路线图）
├── 3-治理与合规/                   # IATF/ISO26262/OEM隔离规范、错误回滚SOP
├── 4-数字员工/部门/场景名/          # 各场景独立 Python 工程，import 平台底座包
├── 5-平台底座/zhuopin_platform/    # 可安装 Python 包（pip install -e），见 §4
└── 6-人才与组织/                   # AIOps 岗位说明书、面试打分卡、招聘话术
```

## 4. 平台底座架构（zhuopin_platform）

可编辑安装的 Python 包，**一份代码处处复用**，是 IATF「单一可信源」审计的载体。各场景 `pip install -e` 后 `from zhuopin_platform... import`，彻底消除跨工程引用。

| 子系统 | 作用 | 现状 |
|--------|------|------|
| `audit/` | IATF 可追溯审计：`AuditLogger`+`AuditEvent`，JSONL 先行 / 9月 ClickHouse 汇聚（同接口切换） | ✅ 真骨架，对接它、勿重建 |
| `data_isolation_layer/` | OEM 隔离：`OEMRouter` 按客户路由、跨库抛 `CrossOEMAccessError` | ✅ 路由可用；RAG 待接 Chroma |
| `shared_tools/` | 连接器 / 通知器 / doc_parser 等共享件 | ✅ 已收割：连接器（zp/SRM/CSV）、`notifiers/`（企微 `wecom.send_markdown` + L2 `Notifier`）、`crm_notifier`；doc_parser 待质量旗舰落地 |
| `agents/` | 跨部门智能体逻辑 | 🔧 骨架 |

> **OEM 隔离边界**：只针对**研发/OEM 技术数据**（R 系列、知识库），**不针对采购的 SRM/ERP/CRM 供应商数据**。采购连接器不强加 OEM 路由；平台层把 `data_isolation_layer` 接口预留给后续研发/知识库场景即可。
> **质量域扩展（2026-06-11，Paul 认可）**：质量域 PPAP/FMEA 等 OEM 技术数据 = **硬隔离**（走 `data_isolation_layer`）；IQC/SPC 等公司自有制造数据 = **不隔离**；8D/客诉中**含特定 OEM 信息的部分按客户隔离**（RAG 检索/历史库分客户分库，比亚迪历史 8D 不进上汽检索结果）。即隔离边界从"研发技术数据"扩展到"含 OEM 信息的质量数据"，但仍不含公司自有制造/供应商数据。详见 `1-转型规划/质量域AI数字员工路线图.md`。

## 5. 工作流（OpenSpec + SuperPowers + Hermes，不跳步）

- **会话接力（Paul 2026-06-25 定，固定方式）**：本项目**每次新开 session 都用"读上下文文件"交接，不靠粘贴长 prompt**。新会话开场：读 ① 本 `CLAUDE.md`（当前进度）→ ② `1-转型规划/0-全景路线图/session接力-Phase1收口.md`（【下一会话主攻】+ 状态快照）→ ③ 全景规划 / 实施计划第七节（权威）恢复上下文，开干前问 Paul 2-3 个澄清。**收工纪律**：把本次进展 + 下一步**滚动更新进 `session接力-Phase1收口.md`**（覆盖旧版、标日期），使下一会话读完即接上。Paul 开新会话只需说一句"读接力文件 + CLAUDE.md 继续"。
- **Cowork（规划治理桌）**：规划/路线图/治理合规/招聘/汇报；**默认只改/出 `.md`，Word 仅在 Paul 明确要求时才用 md-to-word 转**（平时不转）；**不碰真实库、不写生产代码**。
- **Claude Code Desktop（建造车间）**：写并运行场景代码、连真实 SRM/ERP、跑真实数据、收割 supplychain；**不改规划文档**。
- **同步纪律**：开工先跑 `git fsck --connectivity-only`（秒级，确认对象库健康——2026-07-04 实证 OneDrive 曾 NUL 损伤 `.git/config`、云端副本尾截断，fsck 是早发现哨兵；报错即停，勿 pull/push，报 Paul 走恢复流程——**先把工作区未 commit 的改动手工备份到仓库外临时目录**，再 GitHub 重 clone，最后拷回未提交件与 .env/reports 等 gitignore 件（评审整改 2026-07-04：防重 clone 吞掉未提交成果）），再 `git pull`；收工 `git push`（GitHub=权威备份，.git 损毁可十分钟恢复）；同一文件别两边同时改。**OneDrive 配合（Paul 惯例，2026-07-04 确认）**：CC 做 git 密集操作时段暂停 OneDrive 同步、收工 push 后再恢复——注意 `.env`/`real_frozen/`/reports/*.db 等 gitignore 件不在 GitHub，OneDrive 是它们唯一备份，同步不可长关。**乱码文件夹哨兵（2026-07-04 二次事故后强制）**：CC 开工与收工各查一次上级目录——`Projects\` 下 `*AI转*` 目录**应且仅应 1 个**（PowerShell：`Get-ChildItem ..\ -Directory | ? Name -like '*AI转*'`）；出现含 U+FFFD 乱码重名的兄弟文件夹即停手，按既例处置（整树移入 `_乱码重复文件夹隔离-日期\` 隔离夹、逐文件哈希比对真项目、**不直删**），并记录当刻哪个工具在写中文路径。根因指纹（2026-07-04 实证）：写入端 UTF-8 损坏，路径与文件内容**同现 U+FFFD**（11:42 QD-A 测试文件写入事故，每个汉字变 2 个 U+FFFD）；CC 写含中文路径的关键文件后，**读回抽验一处中文完整性**再继续。
- **合并策略（2026-07-04 定）**：本仓库所有 PR 均走 **ff-only**（fast-forward only）合并。若 PR 分支与 master 完全一致（已被直接 ff push 先入），PR diff 为零 → GitHub 无法走合并按钮 → **带说明直接 CLOSE**（不算废弃，内容已在 master）。下次遇到 "This branch has no changes" 状态的 PR，正确处理是验证 `git log master..branch` 为空后 CLOSE，不要强 push 或 rebase。
- **排期同步纪律（Paul 定，2026-06-19，强制）**：任何业务场景的**实现时间一旦变更**，必须**同步更新所有规划与四阶段路线图**——`全景规划`（§2.1.3 场景块 + §加速启动总览权威排期表 + 四阶段/第四阶段 + 各甘特指针）、`实施计划（最新版）`（§一总清单 + §二时间线 + Phase 2）、相关路线图/前置数据总表，并**重生成对应 docx**。**零残差、不留旧档**；改完 grep 自检一致。单一可信源 = 全景规划 §加速启动总览排期表。
- **全景路线图重组循环 + 归集地（2026-07-03 定，机制固化）**：全景规划及构建路线图相关档已统一归集于 **`1-转型规划/0-全景路线图/`**（单一归集地，含全景规划/实施计划/甘特/前置总表/复盘/审计/backlog/待决策/路线图线接力与 prompt）。当某域专线或 CC 建造出现**需求变更（场景增/减/细化）或构建时序变更**，走固定闭环：① 域专线本域内重梳、出**局部定稿 + 移交单**（不直接改全景）；② 局部变更**触发全景路线图重组**，由全景路线图 Task 据移交单跨文档重排（§2.1.4/排期表/四阶段/甘特/实施计划/前置总表/CLAUDE.md）；③ 守上条排期同步纪律（§0.2 登记 + 单一可信源 + **grep 全库零残差** + 场景总数校对）；④ 每次循环登记进 `1-转型规划/0-全景路线图/全景路线图重组机制与变更日志.md`。**分工红线**：域专线不直接改全景、全景路线图线不重开域口径。首例=财务 FI 重排（2026-07-03，财务 8→10、全景 40→42，待路线图线执行）。
- **企微同步推送（自包含，不依赖 supplychain）**：Cowork 把通报写成 `.md` 正文 → 本机跑 `python 0-学习与工具/发企微.py [正文.md]` 一条命令发群。脚本零外部依赖（纯标准库），读**本项目 `.env` 的 `WECOM_WEBHOOK_URL`**，走公网 HTTPS（qyapi.weixin.qq.com）——**off-LAN 亦可，有互联网即可**（区别于 FO/U9C 内网服务）。底座亦有 `shared_tools/notifiers/wecom.send_markdown`。凭据只在 `.env`（gitignore，不入库）。**发送由 CC（Claude Code，跑在本机/LAN、网络通）执行——对 CC 说一句"把 X.md 发企微"即发；Cowork 云端沙箱出网受限（实测 qyapi.weixin.qq.com 403），发不出去，只负责写正文。** 分工：Cowork 写 `.md` 正文 → CC 一句话发。
- **专员跟进纪律（Paul 2026-07-04 定，新 session 一律遵守）**：对部门 AI 专员/对接人的跟进信**统一归集** `6-人才与组织/部门AI专员跟进/`，命名 `部门-姓名-跟进-YYYY-MM-DD-主要事项.md`（实名前用角色代称），每封必含三要素**做什么/怎么做/什么时候交**、随附《部门AI专员协同一页纸》对应域节，发一封在该文件夹 README 清单追加一行。**节奏**＝事件驱动为主 + 月度固定触点（月初 Cowork 刷新一页纸 / 月底专员一句话进展），交付密集期升为每周。**三层文档结构**：总则层（各域就绪包/收口单，口径或方法变化才改）→ 导航层（协同一页纸，月初刷新，专员唯一快捷入口）→ 跟踪层（本文件夹跟进信 + 审核报告 + 各域 session 接力）；给专员的口径类任务一律走"AI 起草·专家批改"三步法（专家只批改不写作业），不再布置写文档式作业。
- **完工即归档纪律（2026-07-02 定，强制）**：变更包的所有 tasks 全 [x] 后，**当场**跑 `/opsx:archive <change-name> -y`，不拖到"下次 session 再归档"。归档完成才算该变更包完工。理由：拖延归档是 SDD 流程最常见的单一可信源漂移根因（本次 hygiene 专项就是为收口这一问题）。**不允许"代码完成但变更包未归档"的中间态持续超过 1 个工作 session**。
- **外部对抗性评审纪律（Paul 2026-07-02 定）**：每个 S 阶段收口前，安排一次独立外部只读评审（沿用 Antigravity 或同类工具），覆盖该阶段新落地场景与平台底座变更；产出评审清单 → 首席 AI 架构师 triage → P0/P1/P2/P3 分桶 → 转 openspec 变更包（fix-x 命名沿用既有惯例），流程同 2026-06-08 那次收割评审。提醒节点：**S1 收口前 ≈2026-11 中旬**（S1 于 2026-12 底收尾）/ **S2 收口前 ≈2027-05 中旬** / **S3 收口前 ≈2027-11 中旬**（亦是 Phase 1 整体收官）。理由：2026-06-08 那次 Antigravity 只读评审（见 `3-治理与合规/外部评审/`）验证了"拉第二双眼睛做对抗性审查"能捕捉内部自审漏掉的 P0 安全项（TLS 默认不校验、L2 门禁 fail-open 等），进而催生 fix-a/b/c 三个整改变更包，值得固化为常态动作而非一次性。**Cowork 负责在上述节点前主动提醒 Paul 排期**。
- **每个场景固定流程**：
  1. 进入 `4-数字员工/部门/场景名/` → `pip install -e .../5-平台底座/zhuopin_platform`
  2. `openspec init`（首次）→ `/opsx:propose "场景描述"` → 生成 proposal + design + tasks
  3. **停下，Paul 审 design.md（技术决策拍板）**
  4. `/opsx:apply` → SuperPowers 先写测试再实现
  5. 真实数据验证（任务 N.1）→ `/opsx:archive` → git commit + push
  6. **当场写/更新场景 CLAUDE.md**（六段式：定位/决策/底座/红线/时间线/依赖）→ git commit

## 6. supplychain 收割策略（指针）

- 详见 `1-转型规划/0-全景路线图/supplychain收割与全景推进策略.md`（含模块迁移表/场景映射表/重排表）。
- **方针**：supplychain 是真实数据验证过的单体试验田，**收割（harvest）可复用件进底座，不整体并入**；收割完打 git tag 转只读存档。
- 源仓库：`C:\Users\Paul Shao\OneDrive\Projects\supplychain`（收割时需同时在工作区）。
- **首批收割（地基）**：`src/data/{xky_srm_connector, zp_connector, u9c_connector, connector, csv_connector}.py` + `src/{crm_notifier}.py` + `src/notifiers/wecom.py` → `shared_tools/`，统一接 `audit`，预留 `data_isolation_layer`。
- 收割时**必补两块**（supplychain 当初没做）：① 审计统一进平台 `audit`；② OEM 隔离接口预留。

## 7. 合规红线（建造时守住，IATF 16949 / ISO 26262）

1. **先 mock/脱敏跑通逻辑，再切真实库。**
2. **所有 AI 决策写平台 `audit`**（append-only，3 年留存，可追溯）。
3. **OEM 数据隔离**：涉 OEM 技术数据按客户路由、禁跨库（研发/知识库 + 质量域 PPAP/FMEA/含 OEM 信息的 8D 客诉，见 §4 边界扩展）。
4. **L2 人工确认门禁**：采购金额 > 50 万、新供应商、交付预测推客户 —— 必须人工确认，不可自动执行。
5. **ISO 26262 安全相关**：AI 生成不得直接合入，须人工审核（R3 等）。**ASIL C/D = AI 绝对禁区**（LLM 过不了 TCL 工具资质，禁止 AI 参与 C/D 自动修改/最终判定、不进安全证据链，FSE 双签）；ASIL A/B 可 AI 辅助+资质人员签字。详见 `3-治理与合规/ISO26262-AI安全使用规范（草案）.md`。

---
**Last Updated**: 2026-07-04（§5 新增：同步纪律加 git fsck 哨兵 + OneDrive 配合惯例；专员跟进纪律【跟进信归集/三要素/三层文档结构/三步法】。前序 2026-07-03 财务域重编号 42 场景）｜ 维护：本文件随架构/红线变更更新，时间线细节以实施计划第七节为准。
