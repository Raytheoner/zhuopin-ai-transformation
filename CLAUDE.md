# CLAUDE.md — 卓品智能 AI 转型（项目级记忆）

> 本文件是项目级上下文/记忆（Hermes L1）。Claude Code / Cowork 进入本仓库先读它恢复上下文。
> 全局身份/偏好见 `~/.claude/CLAUDE.md`（不重复）；本文件只写**本项目**的背景、架构、工作流与红线。
> 代码与注释用中文，技术术语保留英文；用供应链业务语言描述功能（如"齐套分析""承诺交期""在途跟踪"）。

> **当前进度（2026-06-11）**：已合 master —— **SC8 收割式 MVP**、§1 平台加固 P2、**O2 齐套**、**SC1 收尾**、**SC3 在途跟踪**（PR #6 rebase-merge）、**kit_engine 底座化**（PR #7 feat/sc5-purchase-recommendation，SC5 是第 2 消费方触发提升，底座 114 + O2 20 + SC5 41 = 175 tests）。**SC5 采购建议与供应商遴选已完成**（PR #7 待 review 合 master；41 tests 全绿，黄金值对齐 auto_total=35850/review_total=640000，IATF L1/L2 分桶审计）。**下一步：supplychain 打 tag `harvested-archive-v1` 存档（SC3+SC5 均已收割）**。续工作先读 `1-转型规划/supplychain收割与全景推进策略.md`。

---

## 1. 公司与项目背景

- **公司**：卓品智能科技股份 — 汽车 ECU 设计研发制造 Tier 1，直供比亚迪 / 上汽 / 理想等 OEM。
- **本项目**：18 个月企业 AI 转型（2026-07 启动），六部门并行（采购/财务/质量/销售/运营/工程研发），共 **38 个数字员工场景**。
- **决策人**：Paul（分管供应链与质量的 VP，CS + 供应链背景）。技术决策由其拍板。
- **节奏原则**：先跑通最小验证，再规模化；先 mock/脱敏，再切真实库。

## 2. 全景目标与时间线（指针）

- 权威总纲：`1-转型规划/卓品智能AI转型全景规划.md`（不改）。
- 最新时间线 + Phase 1 修正：`0-学习与工具/卓品智能AI转型实施计划（最新版）.md` 第七节。
- **U9C 已覆盖的标准功能直接用，不建 AI**；AI 只做 U9C 不覆盖或需智能增强的场景。
- Phase 1（→2026-07 底）真正能上线的只有 **SC1**（供应商风险初筛）与 **SC8**（客户订单交期智能承诺，**收割式 MVP**，7-8 月上线 — 复用 supplychain 已验证引擎，不从零搭）；其余场景被 U9C MCP（7/1 申请）/外部 API/知识库三类依赖阻塞，先在底座上做 mock 原型。

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

## 5. 工作流（OpenSpec + SuperPowers + Hermes，不跳步）

- **Cowork（规划治理桌）**：规划/路线图/治理合规/招聘/汇报；改 `.md`、出 Word；**不碰真实库、不写生产代码**。
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
3. **OEM 数据隔离**：涉 OEM 技术数据按客户路由、禁跨库（仅研发/知识库，见 §4 边界）。
4. **L2 人工确认门禁**：采购金额 > 50 万、新供应商、交付预测推客户 —— 必须人工确认，不可自动执行。
5. **ISO 26262 安全相关代码**：AI 生成不得直接合入，须人工审核（R3 代码审查等）。

---
**Last Updated**: 2026-06-10 ｜ 维护：本文件随架构/红线变更更新，时间线细节以实施计划第七节为准。
