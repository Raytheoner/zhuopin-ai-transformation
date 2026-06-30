---
title: "QD-B 立项门禁 · CC 开工便条"
created: 2026-06-27
用途: 在 Claude Code（LAN 建造车间）新会话开场用——读文件起活，不靠粘贴长 prompt
关联: 立项门禁QD-B-OpenSpec-design输入交接包 ｜ 质量就绪工作审核报告-2026-06-27 ｜ CLAUDE.md §4/§5/§7
---

# QD-B 立项门禁 · CC 开工便条

## CC 新会话开场，复制这句

> 读 `CLAUDE.md` + `1-转型规划/立项门禁QD-B-OpenSpec-design输入交接包.md`，按其 §11 起 QD-B（开发类）立项门禁的 OpenSpec propose。规则规格以 `7-外部文档/质量部/AI质量智能建设就绪工作汇总.xlsx`（「立项门禁」「规则说明（开发）」页）为准；取数锚点对照 `7-外部文档/质量部/EQQR8082立项申请书（开发类）-A2.1.xlsx`。

## 三个提醒（CC 易漏，开场点一下更稳）

1. **先读 CLAUDE.md 再动手**：拿到 §4 平台底座（audit / data_isolation_layer / shared_tools）、§5 工作流（OpenSpec + 先测后实现）、§7 红线，再起 propose。落位 `4-数字员工/质量部/QD-B-立项审核门禁/`，`pip install -e` 平台底座。

2. **生成 proposal/design 后停在 design，先交审**：交接包 §6 三处收口需业务输入，apply 前必须过 Paul（+陈忱/PMO）——
   - 收口-1 评分扣分细则（交质量部/PMO 定；MVP 先"错误项一票否决"两档起步）
   - 收口-2 10 条半自动规则的 LLM 判定准则（需陈忱给业务判据）
   - 收口-3 产品类立项书真实样本（陈忱补，现仅有技术服务类华丰 1 份）

3. **第一刀做 doc_parser 解析探针**：立项书是合并单元格 Excel 表单（A1:Z145、大量 merge），先验字段抽取准确率再写 82 条规则判定。取数**锚章节标题文本、不锚绝对单元格**（模板一月内改了 4 版）。doc_parser 按 rule-of-three：QD-A(8D) 第 1 消费方、QD-B 第 2，真复用才提升进 shared_tools。

## 范围与红线（一句话）

只做**开发类 EQQR8082 A2.1**（研发类二期）；L2——AI 出预审报告、决策权在评审委员会；所有判定写 audit；先 mock/脱敏再切真实；含 OEM 技术方案的附件走隔离层。

---
*这是建造侧（CC/LAN）开工便条。Cowork 已把需求规格备齐在交接包，CC 据此跑 OpenSpec。Last Updated 2026-06-27。*
