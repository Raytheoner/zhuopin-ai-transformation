---
status: 在办
title: "Claude Code Desktop 衔接与全景开发启动指南"
created: 2026-06-08
audience: VP（Paul）+ AIOps
用途: 从 Cowork（规划）无缝接到 Claude Code Desktop（建造），开始全景开发
---

> 一句话：**Cowork 已把"规划 + 地基设计"做完，现在去 Claude Code Desktop"动手建"。两边是同一个 git 仓库，衔接零成本。**

---

## 1. 衔接原理：同一个仓库，不用搬运

- `企业AI转型/` 文件夹本身就是 git 仓库（GitHub `Raytheoner/zhuopin-ai-transformation`）。
- **Claude Code Desktop 打开这个文件夹，就直接看到 Cowork 这几天产出的全部**——规划文档、`5-平台底座/zhuopin_platform` 骨架、《supplychain收割与全景推进策略》、《Phase1架构设计》、U9C 接口申请、md转Word工具、岗位/招聘材料……无需任何"导入/搬运"。
- `supplychain/` 是另一个仓库。**收割时让 Claude Code 同时能访问两个文件夹**（在 Claude Code 工作区把 `supplychain` 也加进来，或从两者的父目录启动）。

## 2. Day 0：固化 Cowork 产出（一次）

在 `企业AI转型/` 目录：
```bash
git add -A
git commit -m "Cowork 阶段产出：平台底座骨架/收割策略/Phase1设计/U9C申请/规划重排/工具"
git push
```
之后 Claude Code 与 Cowork 通过 git 双向同步。

## 3. Day 1：让 Claude Code 恢复上下文

1. 确认已配（之前都装好了）：全局 `~/.claude/CLAUDE.md`、3 个全局 agents、SuperPowers v5.1、OpenSpec v1.4。
2. 打开 `企业AI转型/`，让 Claude Code 先读这几份恢复上下文：
   - 项目 `CLAUDE.md`（如无则参考 supplychain 的 CLAUDE.md 风格补一份）
   - `1-转型规划/0-全景路线图/supplychain收割与全景推进策略.md`（最重要——三张映射表）
   - `1-转型规划/0-全景路线图/Phase1-基础设施与智能体架构设计.md`
   - `1-转型规划/0-全景路线图/卓品智能AI转型实施计划（最新版）.md` 第七节

## 4. 开发顺序：地基 → 核心 → 铺开

| 序 | 任务 | 说明 | 何时切真实库 |
|---|------|------|------------|
| 1 | **平台底座收割（地基）** | supplychain 连接器/通知器 → `zhuopin_platform/shared_tools`，作废 stub；统一接平台 `audit`，预留 `data_isolation_layer` | 连接器本就是真实的 |
| 2 | **SC8 交期承诺 MVP（核心目标）** | 收割 `delivery_forecast`+`crm_notifier`+`sales_order_intake`+`smt_scheduling`，按启发式跑成品交付预期 | 先 mock；6/12 真实需求+供应商反馈到位切真实 |
| 3 | **SC1 收尾** | 先 mock 跑通；改 import 平台连接器 | 6/12 真实数据 → v1.0 上线 |
| 4 | **SC3/SC5/O1/O2 落位** | 引擎已就绪（supplier_tracking/purchase_recommendation/smt_scheduling/kit_analysis），落成各自数字员工 | 数据就绪后 |

> 启发式（SC8 v0）：无供应商反馈物料→需求日+30天（低置信）；成品齐套日=最晚到货物料日（关键路径）；委外→齐套日+10天；带置信度；真实反馈进来重算，变化超阈值才推 CRM。

## 5. 每个场景的固定流程（已建立，沿用）

```
1. 新建/进入 4-数字员工/部门/场景名/
2. pip install -e ../../../../5-平台底座/zhuopin_platform   # 依赖平台底座
3. openspec init（首次）
4. /opsx:propose "场景描述"   → proposal + design + tasks
5. Paul 审查 design.md（15-30 分钟拍技术决策）
6. /opsx:apply → SuperPowers subagent-driven-development（先写测试）
7. 真实数据验证（任务 N.1）
8. /opsx:archive → git commit + push
```

## 6. Cowork ↔ Claude Code 分工与同步规则

| | Cowork（规划治理桌） | Claude Code Desktop（建造车间）|
|--|--------------------|------------------------------|
| 干什么 | 规划/路线图/治理合规/岗位招聘/对外汇报/架构梳理；改 `.md` 规划文档、出 Word | 写并运行数字员工代码、连真实 SRM/ERP、跑真实数据、收割 supplychain |
| 不干什么 | 不碰真实库、不写生产代码 | 不改规划文档（避免与 Cowork 冲突）|

**同步纪律**：开工先 `git pull`，收工 `git push`；**同一个文件别两边同时改**——规划改在 Cowork，代码改在 Claude Code，井水不犯河水。

## 7. 给 Claude Code 的开场 Prompt（可直接复制）

```
你是卓品智能 AI 转型的首席 AI 架构师。先读项目 CLAUDE.md、
1-转型规划/0-全景路线图/supplychain收割与全景推进策略.md、
1-转型规划/0-全景路线图/Phase1-基础设施与智能体架构设计.md、
1-转型规划/0-全景路线图/卓品智能AI转型实施计划（最新版）.md 第七节，恢复上下文。

本次目标：平台底座收割。把 supplychain 的 xky_srm_connector / zp_connector /
u9c_connector / crm_notifier / wecom / DataConnector 抽象，迁入
5-平台底座/zhuopin_platform/shared_tools，作废现有 stub；统一接入平台 audit，
预留 data_isolation_layer。

用 OpenSpec 工作流：openspec init →
/opsx:propose "平台底座收割：迁入 supplychain 真连接器替换 stub，统一审计+OEM隔离" →
等我审 design.md → /opsx:apply。先不碰真实库，用 supplychain 现有测试夹具验证。
```

## 8. 收割/开发时的合规红线（别漏）

- **审计统一**：所有 AI 决策写平台 `audit`（JSONL→9月 ClickHouse），3 年留存。
- **OEM 数据隔离**：涉 OEM 技术数据按客户路由，禁跨库（supplychain 原来没做，收割时补）。
- **人工门禁**：交付预测要推客户、采购金额>50万、新供应商——必须 L2 人工确认。
- **先 mock 后真实**：逻辑用脱敏/mock 跑通，再切真实库。

---

*衔接的本质：同一个 git 仓库 + 同一套工作流。Cowork 谋划，Claude Code 建造，git 缝合。*
