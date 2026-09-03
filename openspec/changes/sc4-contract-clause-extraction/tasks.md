# 任务 · SC4 合同条款自动提取与审核（队列 §一 #467）

> 🔴 **1.0 是硬闸**：本包 `design.md` 尚未撰写、design 审未过（`openspec_design_review` 属 🟡 档）。
> 第 2 组之后各项**在 design 审通过前不得开工**；第 1 组已完成的部分是 `OP-0903-B2` 泳道按
> 「不依赖前置的部分照做」判据先行落地的骨架，其范围已逐条列明、未越界。

> 🔴 **本包 `暂不归档`（文本标记，机器认得的三条入口之一——`工具-落库sweep.py::STALE_CHANGE_DEFER_MARKER`）** —— 2026-09-03 `OP-0903-C1` 留。
> **理由**：本包已跑 `/opsx:sync`（增量 spec 已并入 `openspec/specs/sc4-clause-extraction/spec.md`），但 tasks **10/28 项已勾**，第 2 组前置到位闸整组未满足：`design.md` 未写且 design 审未过（🟡 档）；两项知识型前置（标准合同条款库、合同风险条款判据）**至今零开工动作**、backup「采购合同岗」仍待点名。
> ⚠️ **不是遗忘归档，是它还没完工** —— 最早能重议归档的时点，取决于 §四 待定项 8 那个「法务侧实际开工承诺日」，**该日期至今未知**，故**刻意不写「预期观察窗口：N 天」**（估不出来就不该编一个天数，那会把一条真声明降格成噪音）。

## 1. 骨架期（不依赖法务前置，`OP-0903-B2` 已完成）

- [x] 1.1 前置逐项实读并落进代码：`sc4_contract/pending.py` 登记两项前置（Owner／判据源行／实读状态原文）
- [x] 1.2 结构模型：`ClauseType`（四类逐字取自全景规划）／`ClauseSpan`（带原文偏移量）／`ContractDocument`／`ExtractionResult`
- [x] 1.3 取文层：`TextSource` Protocol ＋ `PlainTextSource`；PDF/Word 后缀当场拒绝并指向底座 `doc_parser`
- [x] 1.4 定位词表：`ClauseLexicon` ＋ `MOCK_LEXICON`（`lexicon_id="mock-v0"`，**无默认参数**，一路进 audit）
- [x] 1.5 切分与定类：`segment()` 按条款标题行切段；多类命中不猜退回 `OTHER`；整篇无标题行返回**空结果**而非整篇塞成一段
- [x] 1.6 覆盖概览：`summarize_coverage()` 只陈述命中，**刻意不含 `missing_types`**
- [x] 1.7 前置闸：`review.py` 三个函数调用即抛 `PendingPrerequisiteError`，错误里带 Owner／判据源／实读状态
- [x] 1.8 入口与留痕：`run_extraction()`，`evaluator` 非空强校验，audit 标 `review_status="待前置到位"` ＋ `blocked_by`
- [x] 1.9 测试：19 tests 全绿（含「判据类能力必须抛」一组——它是"本泳道未自拟法务判据"的可执行证据）
- [x] 1.10 场景 `CLAUDE.md` 六段式（定位/决策/底座/红线/时间线/依赖）＋ `README.md`

## 2. 前置到位闸（🔴 未满足即不开工第 3 组之后）

- [ ] 2.1 公司标准合同条款库已交付，前置总表 §一 `SC4` 行状态格回填
- [ ] 2.2 合同风险条款判据首轮工作坊完成；**backup「采购合同岗」实名点名**（双人制成立）
- [ ] 2.3 SC4 顺延目标月 —— ✅ **已拍定 ＝ 2026-11**（Shao Peishen 2026-09-03 `EE-6=(a)`，取算术下界 2026-10-29 之后第一个整月留缓冲；移交单 §一.bis）。🔴 **本项仍未勾**：九文档重排**尚未执行**，权威排期表（`卓品智能AI转型全景规划.md:948`）与场景块（`:249`）现仍写 2026-10，排期与本包 tasks 尚未对齐。⚠️ **另须留意 8 周算术**：启动取 2026-11-01 ⇒ 两项知识型前置最迟开工 **2026-09-06**；取 2026-11-30 ⇒ **2026-10-05**（移交单 §四 待定项 8）。
- [ ] 2.4 本包 `design.md` 撰写并过 design 审（🟡 档，须 Shao Peishen 拍板）

## 3. 取文层接真（依赖底座 doc_parser）

- [ ] 3.1 平台底座 `shared_tools/doc_parser` 落地后，新增 `DocParserSource` 实现 `TextSource`，`PlainTextSource` 保留作测试替身
- [ ] 3.2 SRM 合同文档库**只读**接入，`ContractDocument.source` 记录真实文档号
- [ ] 3.3 单测：扫描版 PDF（无文本层）须 fail-loud，不得静默产出空文本

## 4. 审核层（TDD：先测后码；判据来自 2.1/2.2，不得自拟）

- [ ] 4.1 标准条款库载入与版本化（条款库会升版，旧结论须能被认出是旧版产的，同 `lexicon_id` 做法）
- [ ] 4.2 `compare_with_standard()`：按 2.1 交付的比对基准实现，移除 `pending.require`
- [ ] 4.3 `grade_risk()`：按 2.2 交付的风险判据实现，移除 `pending.require`
- [ ] 4.4 `detect_missing_clauses()`：按 2.1 的必备条款清单实现，移除 `pending.require`
- [ ] 4.5 🔴 单测须断言：判据文件缺失/版本不匹配时 fail-loud，**不得回退到任何内置默认**
- [ ] 4.6 LLM 判据黄金集首版入库（条款语义等价判定 ＋ 偏差严重度分级），冻结输入 + 专家认可输出

## 5. 审核摘要与检索库（全景规划点名、本包骨架期未起）

- [ ] 5.1 合同审核摘要与风险提示清单输出（L2：法务/采购经理确认后方可外用）
- [ ] 5.2 条款检索库与自然语言查询（🔴 须先判定是否复用底座 Chroma 及其 OEM 归属结论，见队列 §一 OEM 隔离层 Chroma 重判行）

## 6. 收口

- [ ] 6.1 真实数据验证（档2）→ `/opsx:archive` → commit + push
- [ ] 6.2 场景 `CLAUDE.md` 更新（含部署状态段）
- [ ] 6.3 发布收口：统一门户路由 `/procurement/sc4`（🔴 不新起端口）＋ 部署段基本测试 ＋ 回滚 SOP ＋ 灰度反馈入口
