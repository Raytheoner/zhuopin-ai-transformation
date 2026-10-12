# 首批实际设计供审集合 · v1

本集合冻结后不原位改SHA。来源3A六项离线提案恢复，先生成实际design，现提交SC2/FI14两项。独审依据reports/pc-mvp-1012/v2-review/first-group-review.md。不是产品实施/测试批准。

## 1 逐项实际版本

| 场景 | 原生task/工作树 | design HEAD | design SHA256 | 补充件 |
|---|---|---|---|---|
| SC2 | sc2-three-metric-evidence-1012v2 / C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-sc2/zhuopin-ai | b2933132b733756b30b94e309e2066bbd50d6e43 | 9b8b7c9438a7ef309a2cecab10e64781b9f6c31e782699359d13b5e11c70959e | 无 |
| FI14 | fi14-payment-plan-pc-mvp-1012v2 / C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-fi14/zhuopin-ai | cd1c154800945f6fe6c756bd60474bb8fe082783 | 73a79dae37c75e8d09f862655212deae645fff4715cd2c72b109b554bcc47e37 | docs/superpowers/specs/2026-10-12-fi14-pc-mvp-technical-addendum.md v1 SHA 5f022c8ad5fbd00603e4996b70ab88c7425a0f30f2e0546c3c3c199d99959c63 |

原四件正式strict已通过、实际Luna及原生attempt/thread绑定已核；原HEAD/设计文件不原位修订。FI14原design与附录作为整体审，附录精确工程接缝及敏感财务值投影优先适用。

## 2 拍板内容与推荐

SC2：已签到货分母/闭区间/算术平均、unknown/PENDING/零、不可变snapshot/API/audit、权威日历、旧格式回退及12文件候选白名单；G01–G04不代签。
FI14：Python/Flask的同截止账龄/草稿/人工版本/审计mock PC闭环，JSON/Decimal/幂等/原子发布、注入权限默认拒绝、17文件候选白名单与audit不落财务敏感原值；G01–G06不代签，首期不接真实财务源，不生成付款。
4A（推荐）：批准本集合两份实际design以及FI14绑定附录，仅据此编写详细实施计划；4B：保留成件，暂不批准设计。无默认，必须明确答复。

## 3 答复后由本会话继续

4A仅形成两个独立design审结论，并记录到仓内队列/证据。按Superpowers写详细实施计划并继续供审，具体产品实施与测试未包含；既有范围内读取/计划准备由本会话完成，无须本人搬运。ff、生产、真实取数、付款和新增外发另审。FI5正式格式接续与质量三项另件，不被本集合批准。
