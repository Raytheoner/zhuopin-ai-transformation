---
title: "开场 Prompt · fix-d 评审整改（CC 交接）"
created: 2026-07-04
来源: 《Antigravity评审结果-默会知识纠正与批次制机制-2026-07-04》→《Antigravity评审triage与分桶-2026-07-04》（首席 AI 架构师已逐条核证，3 P0 + 1 P1 接线转本变更包）
执行方: CC（LAN）；命名沿用 fix-x 惯例=fix-d
---

# 开场 Prompt：fix-d 评审整改

> 用法：CC 新会话读本文件 + triage 文件恢复上下文。开工先跑 `git fsck --connectivity-only` + 乱码文件夹哨兵（CLAUDE.md §5，2026-07-04 新增），再 `git pull`（注意工作区有 Cowork 未提交改动，先 commit 入库：本文件 + triage + openspec/templates/ + 实施计划/CLAUDE.md/前置总表三处小修 + 6-人才与组织 跟进文件夹，message 建议 `docs(review): Antigravity评审triage+Cowork侧整改+专员跟进机制归集`）。

## 任务（一个 openspec 变更包 fix-d-review-remediation，四项）

### ① 🔴 QD-A .gitignore 堵根目录 JSON 泄漏口（立即，本次 commit 前）
现状实测：`4-数字员工/质量部/QD-A-8D不良分析/.gitignore` 只挡 `data/golden/*.json`、`reports/*.json`、`results/`；`run_prefill.py --output result.json` 落在场景根目录的输出**不设防**，含未脱敏 8D 原文字段。
改法：场景 .gitignore 改为默认拒 `*.json`，白名单放行必要配置（如 `!qda_prefill/**/registry*.json`、`!pyproject.toml` 类非 json 不受影响）；改完 `git check-ignore -v result.json tests/x.json` 自证 + 对现有必要 json 逐个确认仍被跟踪。**同步给 SC8/FI1/QD-B 场景做一次同类检查**（CLI 输出文件是否都有 ignore 兜底），有同类口子一并堵。

### ② 🔴 Scrubber 中文裸名 OEM 白名单 + 漏判负例测试（7/10 前）
现状实测：`qda_prefill/scrubber.py` `_ORG_RE` 中文分支要求"汽车/集团/科技…"后缀，**"比亚迪/上汽/理想"等裸名完全不中**（"BYD" 英文分支反而能中）。
改法：新增 `_OEM_ALIAS_RE` 客户简称白名单（比亚迪|BYD|上汽|SAIC|理想|Li ?Auto|蔚来|NIO|吉利|长城|奇瑞|特斯拉|Tesla 等，以公司实际客户清单为准、可读 env/配置扩充），与 `_ORG_RE` 合并进实体识别，命中一律生成 Token 建议。测试补**负例**：裸名"比亚迪""上汽"、混排（"比亚迪端 H 桥失效"）必须被捕获；现有 26 tests 不回退。注意：白名单只含公开客户名，机密映射表（OEM-级别-序号）仍由质量部本地保管、不入库。

### ③ 🔴 FI1 L2 改判录入路径 `fi1/confirm.py`（7/15 前，随对接人批改会节奏）
现状实测：fi1/ 全包 grep `override_reason` = 0——平台字段（4f5f0c9）在 FI1 是空转，判例采集器第三步断链。
改法：新增 `fi1/confirm.py` CLI（或等价入口）：输入=对账期+物料/差异项标识+人工结论（认可/改判分类/豁免）+ `--reason` 必填；写 `AuditEvent`（evaluator 实名必填、override_reason 落位、hash-chain 延续）；`needs_review` 项未经 confirm 不得标记结案（对齐 L2 红线：超阈不自动结案）。测试：改判一笔→audit 可查 override_reason；未 confirm 项结案被拒。QD-B 的 L2 路径将来复用同模式（本包只做 FI1，QD-B 随其报告聚合任务做，tasks 里留注）。

### ④ 🟠 openspec 模板接线（知识三问/晋档条件强制化）
Cowork 已建 `openspec/templates/proposal-template.md`（含两个强制段）。你把它接进流程：改 `.claude/commands/opsx/propose.md`（及对应 SKILL 文件如有）——生成 proposal 时按模板包含"知识资产三问"与"验收与晋档条件"两段；validate 环节缺段即提示不通过（做不到硬校验就在命令 prompt 里写死"缺任一段不得交审"）。用一个 dry-run 验证生成物含两段。

## 纪律
- 全程红线不变：mock 先行、audit 留痕、`CUSTOMER_OUTBOUND_ENABLED=False` 不动、真实数据 gitignore 自查。
- 回归：平台 + QD-A(26) + FI1(30) + 相关场景全绿；黄金值不漂移。
- **完工即归档** fix-d；收工滚动接力文件 + push；乱码哨兵收工再查一次。

---
*triage 依据与逐条证据见同目录《Antigravity评审triage与分桶-2026-07-04.md»。评审 P1"陈嵚 typo"已驳回（码点实测无误），勿动跟进信文件名。*
