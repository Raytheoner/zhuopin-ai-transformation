---
status: 在办
title: "Claude Code Desktop 开场 Prompt — 平台底座收割（全景构建第一步）"
created: 2026-06-08
用法: 在 Claude Code Desktop 新开 session，确认已打开 `企业AI转型` 与 `supplychain` 两个文件夹后，复制下方整段粘贴。
---

# 开场 Prompt（复制下方整段）

```
角色：你是卓品智能（汽车 ECU Tier 1 供应商）AI 转型的首席 AI 架构师。我是分管供应链与质量的 VP（Paul，CS + 供应链背景）。请全程用中文、供应链业务语言，代码加中文注释。

第一步——恢复上下文（不要跳过，读完先别写代码）。按序读：
1. 项目根目录 CLAUDE.md（若没有，先照 supplychain/CLAUDE.md 的风格，给 企业AI转型 补一份项目级 CLAUDE.md）
2. 1-转型规划/0-全景路线图/supplychain收割与全景推进策略.md   ← 最重要，含三张映射表
3. 1-转型规划/0-全景路线图/Phase1-基础设施与智能体架构设计.md
4. 1-转型规划/0-全景路线图/卓品智能AI转型实施计划（最新版）.md 的「第七节」
5. 0-学习与工具/Claude_Code_Desktop启动衔接指南.md
读完用 3-5 句话回我你的理解，我确认无误再动手。

确认环境：本次需要同时访问 `企业AI转型` 和 `supplychain` 两个文件夹（收割要从 supplychain 搬连接器）。若只看到一个，提醒我把另一个加进工作区。

本次任务——平台底座收割（地基，先做这个）：
把 supplychain 已用真实数据验证的数据层/通知层，收割进全景平台底座，作废我在 Cowork 里搭的占位 stub：
  · xky_srm_connector（携客云 SRM 承诺交期）
  · zp_connector（卓品 zp REST API，真实 ERP，2.4 万 PO）
  · u9c_connector（骨架，待 7/1 MCP 接口补真实）
  · crm_notifier + notifiers/wecom（CRM/企微通报）
  · connector.py + csv_connector.py（DataConnector 抽象 + CSV 回退）
目标位置：5-平台底座/zhuopin_platform/shared_tools/。
同时：统一接入平台 audit（JSONL，IATF 留痕）；预留 data_isolation_layer（OEM 隔离）接口。

工作流（沿用，别跳步）：
openspec init → /opsx:propose "平台底座收割：迁入 supplychain 真连接器替换 stub，统一审计、预留 OEM 隔离" → 生成 proposal+design+tasks → 停下让我审 design.md（技术决策我拍板）→ 我确认后 /opsx:apply → 用 SuperPowers 先写测试再实现 → 用 supplychain 现有测试夹具验证（先不碰真实库）→ /opsx:archive → git commit。

合规红线（建造时守住）：
  · 先 mock/脱敏跑通逻辑，再切真实库。
  · 所有 AI 决策写平台 audit，3 年留存。
  · 涉 OEM 技术数据按客户路由、禁跨库。
  · 采购金额 > 50 万、新供应商、交付预测推客户：必须 L2 人工确认。

现在开始第一步：读上面 5 份文档 → 回我你的理解 → 确认两个文件夹都在。先不要写代码。
```

---

## 用完这一步之后（后续 session 的接力顺序）

1. ✅ 平台底座收割（本 Prompt）
2. **SC8 交期承诺 MVP**：收割 `delivery_forecast`+`crm_notifier`+`sales_order_intake`+`smt_scheduling`，按启发式跑成品交付预期；6/12 真实数据切换；变化超阈值推 CRM。
3. **SC1 收尾**：mock 跑通 → 改 import 平台连接器 → 6/12 真实数据 → v1.0 上线。
4. **SC3/SC5/O1/O2 落位**：supplier_tracking / purchase_recommendation / smt_scheduling / kit_analysis 落成各自数字员工。

> 每步都用同一套 OpenSpec + SuperPowers 流程；每个新场景的开场 Prompt 照本 Prompt 的结构改任务段即可。
