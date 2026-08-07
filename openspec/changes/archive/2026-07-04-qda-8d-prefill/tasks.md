# Tasks: qda-8d-prefill

## 1. Design
- [x] 1.1 写 design.md（字段提取策略 + doc_parser rule-of-three 评估结论）
- [x] 1.2 Paul 审 design.md — 结论：本地实现，rule-of-three 尚未触发，接口与未来平台模块等价

## 2. 核心实现
- [x] 2.1 `qda_prefill/doc_reader.py` — docx/pdf 读取 + D1-D8 节解析（DocumentSections）
- [x] 2.2 `qda_prefill/field_extractor.py` — 12 字段提取（HIGH/MED/LOW 置信度）
- [x] 2.3 `qda_prefill/scrubber.py` — 实体识别 + TokenState 令牌建议
- [x] 2.4 `qda_prefill/calibrate.py` — 逐字段准确率对比 + batch 报告生成
- [x] 2.5 `scripts/run_prefill.py` — CLI 入口（--input/--output/--golden/--report/--preview）

## 3. 测试
- [x] 3.1 `tests/conftest.py` — 合成 docx + golden CSV fixture（无真实数据）
- [x] 3.2 `tests/test_doc_reader.py` — 4 tests（节解析 / 标头 / 空文档 / docx 读取）
- [x] 3.3 `tests/test_field_extractor.py` — 11 tests（12 字段覆盖，含安全关键词正/负例）
- [x] 3.4 `tests/test_scrubber.py` — 6 tests（料号/同实体同令牌/oem_level/空文本）
- [x] 3.5 `tests/test_calibrate.py` — 5 tests（精确匹配/关键词覆盖率/批报告）
- [x] 3.6 26 tests 全绿，CLI smoke test 通过，`test_smoke.docx` 已清理

## 4. 文档 & 合规
- [x] 4.1 `.gitignore` — 真实 8D docx/pdf/csv/json 一律不入库
- [x] 4.2 场景 `CLAUDE.md` — 六段式（定位/决策/底座/红线/时间线/依赖）
- [x] 4.3 commit + push

## 5. 补记：spec 缺口回溯补写（2026-08-07，队列 #299，CC）

> 本变更原始 4 节内容不追改（历史记录不追改）。归档时（2026-07-04）proposal.md 未声明 `## Capabilities` 段，`/opsx:archive` 因而未产出任何 delta spec，`openspec/specs/` 长期对本场景零覆盖——2026-08-07 队列 #299 全域实扫发现（形态乙：包已归档但当初就没写 spec，归档流程本身无问题）。

- [x] 5.1 反向读现有代码（`doc_reader.py`/`field_extractor.py`/`scrubber.py`/`calibrate.py`）+ 既有测试断言，补写 4 个 capability spec：`qd-a-doc-reader`/`qd-a-field-extractor`/`qd-a-scrubber`/`qd-a-calibrate`
- [x] 5.2 delta spec 补录至本归档目录 `specs/`（历史存档补全，非当初漏交付的重新计价）+ 合并进 `openspec/specs/`
- [x] 5.3 `openspec validate` 四项 `--strict` 通过；`openspec validate --all --strict` 复核不引入新失败
- [x] 5.4 如实登记：本次仅补 spec 文档，未反向修改任何 `qda_prefill/` 代码；spec 内容与代码当前行为一致性核对方式＝逐函数对照源码与既有测试（非独立复跑真实数据校准），不代表已重新验证真实 8D 样本上的提取准确率
