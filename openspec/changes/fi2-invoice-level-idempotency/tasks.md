# fi2-invoice-level-idempotency Tasks

> 🔴 **本包零代码改动、无 apply 阶段**——建造侧已于 2026-08-24 落地并在 `.51` 生产运行（队列 §一 `#371`）。本文件只有「转写核对」与「收口」两段。
> 🔴 **design 审通过前不得开工 1.x 之后的任何一步。** 0.x 是前置闸。
> 执行环境：**CC**（纯库内文档，不触碰 `.51`／企微机器人／定时任务）。

## 0. 前置闸（design 审后、动手前）

- [ ] 0.1 确认 design 决策点 **6**（`known_invoice_nos` 半开状态收不收紧）与 **7**（门槛张力沉不沉淀成判据）的拍板结果已白纸黑字回填队列 §四 `#106`，不凭记忆
  - [ ] 0.1.1 若 6 答 (b) 或 (c)：**本包不扩范围**，另开变更包并登记队列行；本包照旧只补 spec
  - [ ] 0.1.2 若 7 答 (a)：**本包不执行沉淀**，只在 §四 `#106` 登记一行「待总线另行派单落地（触碰区＝`.claude/rules/场景建造与合规.md` openspec 门槛段）」
- [ ] 0.2 复核 `openspec/changes/fi2-source-inversion` 仍**未 apply** 且其 delta 目标仍**不含 `fi2-tax-export-ingest`**（design「触碰区核对」里标为「写作时只读核对」的那项，在此销账）——若已 apply 或已覆盖该 capability，**停手并回报**

## 1. 转写核对（🔴 事后补包的核心工序：证明 spec 没写超过代码）

- [ ] 1.1 白盒重读 `fi2/tax_export_ingest.py` 的模块 docstring「发票级幂等」段、`IngestResult` 的两个重复计数字段、`load_ingested_invoice_nos()`、`ingest_directory()` 的 `known_invoice_nos` 参数与**两处** `seen_before_this_file` 快照（常规 pass 与 `_retry_unresolved` 重试 pass），确认 spec 各条 Requirement 与实现逐条对得上
- [ ] 1.2 🔴 **逐条销账：spec 里每一条 SHALL/MUST 必须指得出一处代码或一条测试断言背书。** 对照表附进本包（新建 `转写对照表.md`），逐行写「Requirement → 代码位置／测试用例名」
  - [ ] 1.2.1 **凡指不出背书的条目，删掉，不留在 spec 里**（`retroactive-mechanism-specs` 确立的转写纪律）
  - [ ] 1.2.2 反向也要过一遍：**代码里有、spec 里漏掉的行为**如实补记（补进 spec 或在对照表里写明「有意不写入 spec，理由＝…」）
- [ ] 1.3 🔴 **MODIFIED 那条逐字比对**：`specs/fi2-tax-export-ingest/spec.md` 里「发票源目录扫描与幂等去重」的**首段原文与三个 Scenario 必须与 `openspec/specs/fi2-tax-export-ingest/spec.md` 现行版本一字不差**，本次只允许多出「本次新增的作用域限定」那一段
- [ ] 1.4 🔴 **补做 propose 期标为「未做穷尽推演」的那项**（proposal 残余风险 4）：`invoice.csv` 被误删或截断时，闸失忆与 ledger 仍记得源文件 SHA 之间的交互面——**重试 pass 捞回的行会不会重复入库？** 用现有夹具推演一遍并记进对照表；若确有重复路径，**这是一条独立发现，须登记队列行**，不在本包修
- [ ] 1.5 销 propose 期标为「未核」的两项：
  - [ ] 1.5.1 `scripts/rebuild_invoice_csv.py` 是否写备份副本；若写，其文件名形态是否已被 `.gitignore` 覆盖（用 `git check-ignore -v` 实测，**不是推断**）
  - [ ] 1.5.2 摄取通道是否写 `zhuopin_platform.audit`（proposal §Impact 红线核对里那项）
- [ ] 1.6 跑一次 `python -m pytest tests/test_tax_export_ingest.py -k "duplicate or invoice_nos or ONE_file"`（在 `4-数字员工/财务部/FI2-三单匹配自动对账/` 下），确认 proposal §Impact 列出的 7 个用例**全绿且确实存在**（用例名若已漂移，以实测名为准更新 proposal，不留错引用）

## 2. 验证

- [ ] 2.1 `openspec validate fi2-invoice-level-idempotency --strict` 通过
- [ ] 2.2 `openspec validate --all --strict` 复核**不引入新失败**（与本包 propose 前的基线对比，不是「全绿」）
- [ ] 2.3 本包零代码改动，**无需跑 FI2 全量回归**；1.6 那次针对性跑已足够

## 3. 收口

- [ ] 3.1 队列 §四 `#106` 回填：变更包路径、design 审结论（决策点 6/7）、转写对照表要点；**该行原题（三选一）自 2026-09-03 起已由 (b) 结案，本次补包完成即可整体销号**
- [ ] 3.2 队列 §一 `#371` 回填一行指针（本包 ＝ 该行修法的 spec 载体），便于 `fi2-source-inversion` 的硬前置 **F3** 追溯
- [ ] 3.3 队列 §一 `#483` ⑵ 回填并标已完成（⑴ 另见 `sweep-manifest-coverage-guard` 包；**两子项都完才销 `#483` 整行**）
- [ ] 3.4 §二 批次登记 ＋ 触发一次 sweep，**看一眼 `reports/sweep-commit.log` 末几行确认真落库**（协议〇.8：触发不等于一定会落库）
- [ ] 3.5 `/opsx:archive fi2-invoice-level-idempotency -y`
  - [ ] 3.5.1 archive 后确认 `openspec/specs/fi2-tax-export-ingest/spec.md` 里 MODIFIED 那条**只多了那一段**，既有三个 Scenario 未被合并工具改写
