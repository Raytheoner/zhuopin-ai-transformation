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
