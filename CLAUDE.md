# CLAUDE.md — 卓品智能 AI 转型（项目级记忆）

> 本文件是项目级上下文/记忆（Hermes L1）。Claude Code / Cowork 进入本仓库先读它恢复上下文。
> 全局身份/偏好见 `~/.claude/CLAUDE.md`（不重复）；本文件只写**本项目**的背景、架构、工作流与红线。
> 代码与注释用中文，技术术语保留英文；用供应链业务语言描述功能（如"齐套分析""承诺交期""在途跟踪"）。

> **当前进度（2026-06-11）**：**supplychain 收割全部完成，收割队列清空。** 已合 master —— **SC8 收割式 MVP**、§1 平台加固 P2、**O2 齐套**、**SC1 收尾**、**SC3 在途跟踪**（PR #6 rebase-merge）、**SC5 采购建议与供应商遴选 + kit_engine 底座化**（PR #7 已合 master；kit_engine 提升到 `zhuopin_platform/agents/`——SC5 是第 2 消费方、rule-of-three 真触发，O2 改 import 回归零变更；底座 114 + O2 20 + SC5 41 = 175 tests 全绿（合并时点快照，PR #8/#9 后底座实测 117，以 CI 为准不再手工滚动）；黄金值对齐 auto_total=35850/review_total=640000；IATF L1/L2 分桶审计，M015 触发 R1≥50万 待人工审核）。**supplychain 已打 tag `harvested-archive-v1` 转只读存档**（O2/SC3/SC5 三引擎 + 连接器/通知器/business_rules 已迁入全景平台）。**Phase 1 真实接入进展（2026-06-11，IT 提前供数）**：**SC8 真实切换已合 master（PR #8）**——FO+BOM 真实、内部验证不外发（CUSTOMER_OUTBOUND_ENABLED=False）、SRM 降级；**U9C 连接器收敛已合 master（PR #9）**——ZpConnector 确立为 U9C/ERP 唯一规范连接器、退役 U9CConnector、外网 OAuth2+BOM/Query 验证通可拉真实 BOM、real 模式 fail-loud（RealEndpointNotReadyError）。**未结项（详见 `1-转型规划/U9C接入与连接器收敛-待办追踪.md`）**：① 🔴 轮换 U9C client_secret（明文在归档仓 history，活凭据）；② SRM 凭据迁入本仓库 `.env` 解 900401；③ 外网开放 `CommonEntity/Query` 才能做 U9C 全量 cutover（库存/PO/MO/价格），否则 LAN/VPN；④ SC8 对客上线仍待 SRM 接通 + L2 签字（置信度/人工确认/回滚 SOP）；⑤ ErpConnector 改名（低峰期）。续工作先读上述待办追踪 + `1-转型规划/supplychain收割与全景推进策略.md`。引擎默认场景本地，第 2 消费方出现才提升（rule of three）。

> **全盘审计 + 文档治理（2026-06-13，Cowork）**：根目录已出《全盘审计与差距分析报告-2026-06-13.md》（底座/场景合规/规划依赖三路审计，发现均带文件:行号）。**P0 四项**：① TLS 校验全局关闭（erp_connector `CERT_NONE`，须先于 secret 轮换修复）；② SC8 `submit_commitment` 低风险自动外发旁路（违反 SOP §4.1/4.2，休眠炸弹，被 test_low_risk_auto_sends 正向固化）；③ audit verify_chain genesis 绕过（任意行缺 prev_hash 被当合法 genesis）；④ client_secret 轮换需硬截止。**代码修复划归 CC 三个变更包**（A 安全 P0 / B 数据正确性+审计强制化 / C SC8 上线前置：偏差监控+真实黄金回归），SC8 对客外发开关在 A2/C1/C2 完成前不得开启。**规划文档修订已由 Cowork 完成**：11 项文档不一致修正、全景规划建立 §0 修订记录机制（"正文不改"改为"可修正+强制登记"）、Phase1 架构文档加过时声明、实施计划新增 §七.2 执行治理（外部依赖红线日+10/12 月砍单规则+Q2 顺延预案+S3 缓冲管理）、新建 `3-治理与合规/OEM数据隔离规范.md`（待签发）与 `1-转型规划/待决策清单-2026-06.md`——**清单 4 项已于 2026-06-13 全部拍板（均选 A）**：D-1 SC8 深化不消费 SC6/SC7（"芯片风险→交期→通报客户"闭环移 S3，前提 SC6 稳定≥3 个月）；D-2 Q2 过渡期客诉人工录入 SOP（质量部接口人+校验脚本）；D-3 SC9 降范围 MVP（OEM 历史订单+公开车市数据）；D-4 全场景两级验收（上线验收+3 个月价值验收，指标写进 openspec proposal），落点均已回填对应文档。**阶段命名定稿（全仓统一，见全景规划 §0.1）**：Phase 1 内部 = S1 筑基期（2026-07~12）/ S2 扩面期（2027-01~06）/ S3 深化期（2027-07~12，显式缓冲）；Phase 2 = 产品工程跃升期（2028 H1）；部门内月度节奏 M1/M2/M3；"第N阶段"称谓废止。
>
> **代码修复 A/B/C 已落地（2026-06-13，CC，三个 stacked PR：A #10 → B #11 → C #12，待 Paul 审合）**：**A 安全 P0（已修，PR#10）**——A1 erp_connector TLS 默认校验 + `U9C_TLS_INSECURE` 逃生开关(real 硬禁) / A2 `submit_commitment` 首道一律入队 + Notifier 第二道总开关 `outbound_enabled`(SC8 接 `CUSTOMER_OUTBOUND_ENABLED`) + 改写 test_low_risk + 修 approve 持锁重入死锁 / A3 verify_chain genesis 豁免限定第1行。**B 数据正确性+审计强制化 P1（已修，PR#11）**——B1 BOM 失败不静默(返回 (rows,failed_ids)/全失败抛错)+get_bom 走 fail-loud 闸门 / B2 SRM get_confirmed_dates 区分失败与未答交 / B3 审批分级(VP_APPROVERS+KEY_CUSTOMERS，重点客户/首次承诺→VP；金额条件 SC8 暂不可得) / B4 from_env 无 audit→warn + SC8 sources/loaders 注入审计 / B5 OEMRouter 跨库拒绝前留痕 / B6 kit_engine 在途盲区(缺快照仍计在途)+SC5 黄金值改精确相等(35850/640000/675850)。**C SC8 上线前置 P1（PR#12）**——C1 偏差监控 `sc8/deviation.py`(消费 DEVIATION_ALERT_DAYS=3，告警+重算回调+审计)**已修**；**C2 真实黄金回归＝🟡待 LAN**(off-LAN 不可达 FO/U9C，未伪造夹具，回 LAN 跑 `scripts/build_golden_real.py` 生成 `data/golden/real_frozen/` 后 test_golden_real 自动脱 skip)。回归：平台136/SC8 50/O2 20/SC1 50/SC3 29/SC5 41 全绿，黄金值不漂移。接口变更(本会话已贯通调用方)：get_bom_for_products/get_confirmed_dates/calc_shortage 均改返回二元组。**🔴 A1 合入后立即催 IT 轮换 U9C client_secret（6/20 红线日）**——先修信道再换钥匙。SC8 对客外发开关仍待 A/C1 合入 + C2 待 LAN + SRM 接通 + L2 签字方可开。
>
> **质量域规划启动（2026-06-11，Cowork off-LAN，纯规划未碰真实库）**：Paul 第二管辖域转入质量。已出 4 份文档（均在 `1-转型规划/`，AIOps 件在 `6-人才与组织/`）：①《质量域AI数字员工路线图》(8 候选 QD-A..H 打分排序、分层、§5 Q 序列修订)；②《质量旗舰PRD-Q2-8D不良分析与根因》；③《质量旗舰PRD-项目立项审核门禁》；④《AIOps第2名-Onboarding（30-60-90）与团队结构》。**旗舰选定**：QD-A 8D（全景 Q2）+ QD-B 立项门禁（全景 Q6），均 off-LAN 友好、风险可控。**已落地决策**：全景 2.1.3 Q 序列已回填修订（旗舰前置、新增 Q7 IQC/Q8 SPC、FMEA/PPAP 后置，md+docx 同步）；两 PRD 的 D1–D6 全采纳推荐（选 A），8D D3=ISO26262 安全相关走功能安全工程师额外门禁、立项 D2=财务"可机器核规则"边界待财务共识；OEM 隔离边界已扩展（见 §4，质量域含 OEM 信息的 8D/客诉按客户隔离）。质量场景开发排期与 AIOps 第 2 人到位强绑定。
> *注：本项目跨会话记忆以本 CLAUDE.md 当前进度为准（可写、每会话载入）；`.auto-memory/MEMORY.md` 自动索引在本环境只读锁定、写不进，勿依赖。*

---

## 1. 公司与项目背景

- **公司**：卓品智能科技股份 — 汽车 ECU 设计研发制造 Tier 1，直供比亚迪 / 上汽 / 理想等 OEM。
- **本项目**：18 个月企业 AI 转型（2026-07 启动），六部门并行（采购/财务/质量/销售/运营/工程研发），共 **40 个数字员工场景**（原 38，2026-06-11 质量域新增 Q7 IQC / Q8 SPC）。
- **决策人**：Paul（分管供应链与质量的 VP，CS + 供应链背景）。技术决策由其拍板。
- **节奏原则**：先跑通最小验证，再规模化；先 mock/脱敏，再切真实库。

## 2. 全景目标与时间线（指针）

- 权威总纲：`1-转型规划/卓品智能AI转型全景规划.md`（2026-06-13 起：正文可修正，但**必须**在其 §0.2 修订记录登记，否则视为无效修改）。
- 最新时间线 + Phase 1 修正：`0-学习与工具/卓品智能AI转型实施计划（最新版）.md` 第七节。
- **U9C 已覆盖的标准功能直接用，不建 AI**；AI 只做 U9C 不覆盖或需智能增强的场景。
- Phase 1（→2026-07 底）真正能上线的只有 **SC1**（供应商风险初筛）与 **SC8**（客户订单交期智能承诺，**收割式 MVP**，7-8 月上线 — 复用 supplychain 已验证引擎，不从零搭）；其余场景被 U9C MCP（7/1 申请）/外部 API/知识库三类依赖阻塞，先在底座上做 mock 原型。
- **阶段框架（命名 2026-06-13 定稿，见全景规划 §0.1）**：当前 18 个月（2026-07 → 2027-12）= **Phase 1**（底座 + 六部门流程提速 + 供应链/质量减负，40 场景），内分 **S1 筑基期（2026-07~12）/ S2 扩面期（2027-01~06）/ S3 深化期（2027-07~12，显式规划缓冲）**；部门内月度节奏用 M1/M2/M3，"第N阶段"称谓废止。**Phase 2 = 产品工程跃升期（月 19-24 / 2028 H1）** = 产品工程深化候选（APQP 数字网关[质量,Paul域]、ASPICE 追溯链、HIL 日志诊断、NRE 深化），**统一 Phase-1 末（2027-12，底座稳定）评估立项、Phase 2 实现，不并入 40、不打乱 Phase 1**。详见全景规划 "Phase 2 · 产品工程跃升期" 章节 + `1-转型规划/AI候选场景增补-backlog（产品工程方向）.md`。

## 3. 仓库结构

```
企业AI转型/                         # 本仓库（GitHub: Raytheoner/zhuopin-ai-transformation）
├── 0-学习与工具/                   # 实施计划、学习路径、U9C申请、衔接指南、md转Word工具
├── 1-转型规划/                     # 全景规划(权威) + Phase1架构 + supplychain收割策略
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
| `shared_tools/` | 连接器 / 通知器 / doc_parser 等共享件 | 🔧 空占位，**待收割填入**（见 §6） |
| `agents/` | 跨部门智能体逻辑 | 🔧 骨架 |

> **OEM 隔离边界**：只针对**研发/OEM 技术数据**（R 系列、知识库），**不针对采购的 SRM/ERP/CRM 供应商数据**。采购连接器不强加 OEM 路由；平台层把 `data_isolation_layer` 接口预留给后续研发/知识库场景即可。
> **质量域扩展（2026-06-11，Paul 认可）**：质量域 PPAP/FMEA 等 OEM 技术数据 = **硬隔离**（走 `data_isolation_layer`）；IQC/SPC 等公司自有制造数据 = **不隔离**；8D/客诉中**含特定 OEM 信息的部分按客户隔离**（RAG 检索/历史库分客户分库，比亚迪历史 8D 不进上汽检索结果）。即隔离边界从"研发技术数据"扩展到"含 OEM 信息的质量数据"，但仍不含公司自有制造/供应商数据。详见 `1-转型规划/质量域AI数字员工路线图.md`。

## 5. 工作流（OpenSpec + SuperPowers + Hermes，不跳步）

- **Cowork（规划治理桌）**：规划/路线图/治理合规/招聘/汇报；**默认只改/出 `.md`，Word 仅在 Paul 明确要求时才用 md-to-word 转**（平时不转）；**不碰真实库、不写生产代码**。
- **Claude Code Desktop（建造车间）**：写并运行场景代码、连真实 SRM/ERP、跑真实数据、收割 supplychain；**不改规划文档**。
- **同步纪律**：开工 `git pull`，收工 `git push`；同一文件别两边同时改。
- **每个场景固定流程**：
  1. 进入 `4-数字员工/部门/场景名/` → `pip install -e .../5-平台底座/zhuopin_platform`
  2. `openspec init`（首次）→ `/opsx:propose "场景描述"` → 生成 proposal + design + tasks
  3. **停下，Paul 审 design.md（技术决策拍板）**
  4. `/opsx:apply` → SuperPowers 先写测试再实现
  5. 真实数据验证（任务 N.1）→ `/opsx:archive` → git commit + push

## 6. supplychain 收割策略（指针）

- 详见 `1-转型规划/supplychain收割与全景推进策略.md`（含模块迁移表/场景映射表/重排表）。
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
**Last Updated**: 2026-06-11 ｜ 维护：本文件随架构/红线变更更新，时间线细节以实施计划第七节为准。
