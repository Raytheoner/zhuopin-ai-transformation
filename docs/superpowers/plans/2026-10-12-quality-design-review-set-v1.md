# Q2、Q9 实际设计供审集合 v1

## 1 供审范围

只请求批准下表两项**真实已封存 actual design**，并继续编写具体实施计划。产品代码/测试、语义线上启用、真实校准/取数、专业签认、ff、生产或外发不在本次范围。QD-A formal admission仍blocked，本集合不含QD-A设计批准。

| 场景 | task_id | design HEAD | design SHA256 |
|---|---|---|---|
| Q2 | q2-semantic-offline-source-1012v2 | 31270c3dc9ff165eec85553f0e26df6ca8b26b5b | 8fbb2dcc1094f58886c47b7fce12f77b0af0a83cfb1b9638a2450ae1ab86c909 |
| Q9 | q9-apqp-evidence-pilot-1012v2 | 1df48365385cf3a2e1c436fbe77466caaae80cd2 | fce1a7c85a7c5414985c36b21fd3b38178c319524084fcfa32f9db2a7f7da3c5 |

## 2 原件与核验

Q2原件：`C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-q2/zhuopin-ai/openspec/changes/q2-semantic-offline-source-1012v2/design.md`。

Q9原件：`C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-q9/zhuopin-ai/openspec/changes/q9-apqp-evidence-pilot-1012v2/design.md`。

同字节供审副本分别在 `reports/pc-mvp-1012/v2-review/q2/`、`q9/`；正式 Workflow strict、HEAD及四件hash见 `quality-receipt.json`。独立Luna审查见 `reports/pc-mvp-1012/v2-review/quality-group-review.md`，未发现本轮聚焦范围内 Important/Critical 问题。严格校验与审查不等于产品测试或业务验收，本轮未跑产品测试。

## 3 保留的业务边界

- Q2只为离线语义来源/证据合同：线上 `PendingSemantic`、未签门禁、ASIL C/D人工边界不变；不增加上传UI。质量16所述上传→判定报告阻碍需独立PC切片，不能记为本提案已修。
- Q9只为客户/项目/文档/版本/位置的候选追溯与人工裁决合同；G01–G06保持PENDING，与Q4规则/裁决/audit分域。
- 真实8D与OEM原文不进入通用audit；技术候选关系不升为专业签认。

## 4 答复与后续

本会话第5项：5A（推荐）批准本v1两design，仅继续写实施计划；5B保留成果暂不批准。无默认，未答不实施。批准后仍按具体实施计划另审；既有prepared task、设计HEAD及原树保留，不重做已成功提案。
