---
title: "Antigravity 评审 triage 与分桶（默会知识纠正与批次制机制）"
created: 2026-07-04
triage: 首席 AI 架构师（Cowork）；逐条核证后分桶，1 条驳回附证据
流程: 评审清单 → 本 triage → P0/P1 转 openspec 变更包 fix-d（CC）+ Cowork 当场修复
---

# Antigravity 评审 triage 与分桶

## 分桶结果（评审 12 条 + 排期表 8 项）

| 评审条目 | 核证结果 | 判定 | 去向 | 状态 |
|---------|---------|:---:|------|:---:|
| P0 · 8D 预填 `result.json` 未 gitignore | ✅ 实测 QD-A .gitignore 只挡 data/golden/reports，根目录 `*.json` 裸奔 | 采纳 P0 | **fix-d ①**（CC，下次 commit 前） | ⏳ |
| P0 · Scrubber 中文裸名 OEM 漏洗 | ✅ 实测 `_ORG_RE` 要求后缀词，"比亚迪/上汽/理想"不中（"BYD"英文规则反而能中）| 采纳 P0 | **fix-d ②**（CC，含负例测试，7/10 前） | ⏳ |
| P0 · FI1 无 override_reason 录入路径 | ✅ 实测 fi1/ 全包 grep override_reason=0 | 采纳 P0 | **fix-d ③**（CC，`fi1/confirm.py`，7/15 前） | ⏳ |
| P1 · openspec 模板缺失（知识三问/晋档条件无载体） | ✅ 全仓无模板实体 | 采纳 P1 | Cowork 建 `openspec/templates/proposal-template.md`；CC 在 fix-d ④ 接线进 /opsx:propose 流程 | ✅ 模板已建 / ⏳ 接线 |
| P1 · 复盘闸缺执行逻辑（谁裁/缩谁/下游链） | ✅ 原文确无 | 采纳 P1 | Cowork 当场补实施计划 §七.2 裁决规则 | ✅ |
| P2 · 复盘闸与砍单规则关系未理顺 | ✅ | 采纳 P2 | 并入上条：复盘闸=砍单动作输入源，统一走砍单优先序 | ✅ |
| P1 · 跟进信文件名"陈嵚"错别字 | ❌ **驳回**：文件名码点实测 `陈(U+9648) 忱(U+5FF1)`，无误 | 驳回 | 附证据存档，无动作 | ✅ |
| P1 · 专员占位符未实名 | ✅ | 采纳（已知在办） | Paul P0 三件之一，实名后 Cowork 全局替换 | ⏳ Paul |
| P2 · 前置总表列头仍写"~6周" | ✅ | 采纳 P2 | Cowork 当场改列头 | ✅ |
| P2 · 四档口径用词微漂移 | 部分：一页纸/全景规划均含规范词"档3 内部服务"；体检报告为当日快照 | 部分采纳 | 快照类按惯例不回溯；活文档已含规范词，无动作 | ✅ |
| P2 · fsck 恢复未保护未提交工作区 | ✅ 好发现 | 采纳 P2 | Cowork 当场补 CLAUDE.md 恢复步骤 | ✅ |
| P2 · scrubber 缺漏判负例测试 | ✅ | 采纳 P2 | 并入 fix-d ②（同一变更包） | ⏳ |
| P2 · 知识资产 backup 待点名 | ✅ | 采纳（已知在办） | 各域专线 7 月底 Review 前报名单 | ⏳ 域专线 |

## 结论

评审置顶两问的回答：① 3 个月内会造成实际损害的漏洞=**3 个 P0 全在工程侧**（数据泄漏两条 + FI1 判例采集空转），已打包 fix-d 交 CC，2 条限 7/10、1 条限 7/15；② 承诺 vs 落地缝隙=2 处（openspec 模板、复盘闸执行逻辑），Cowork 已当场补齐载体，模板接线随 fix-d。机制设计方向未被推翻，无需回滚任何 2026-07-04 拍板项。

---
*fix-d 交接 prompt：同目录《开场prompt-fix-d-评审整改-CC交接.md》。驳回项证据：python 码点枚举，2026-07-04。*
