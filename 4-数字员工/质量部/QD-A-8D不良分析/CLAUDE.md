# CLAUDE.md — QD-A 8D不良分析预填脚本

## 定位
质量部旗舰场景（与 QD-B 立项门禁并列）。输入：陈忱团队提供的 8D 报告（docx/pdf）；输出：12 字段预填录入表 + 脱敏令牌建议表。截止日期 2026-08-01（陈忱批改会前可用）。

## 技术决策
- **纯规则提取，不调 LLM**：12 字段中 5 个可确定性提取（日期/关键词），其余 MED/LOW 标注需人工确认，避免产生"AI 幻觉字段"入库。
- **脱敏不自动替换**：scrubber 只输出映射建议表，陈忱手动确认后替换——OEM 数据合规红线。
- **doc_parser rule-of-three 评估（2026-07-04）**：当前 2 个消费方（QD-B xlsx/QD-A docx），未触发三法则；本地实现 `qda_prefill/doc_reader.py`，接口与未来平台 `shared_tools/doc_parser.py` 等价，第三方消费方出现时零改动迁移。触发点：合同/RFQ 解析（预计 2026-10 Q2 前）。

## 平台底座依赖
- `zhuopin_platform`：无直接依赖（规则提取不接 audit，OEM 隔离通过 scrubber 令牌建议实现）。
- 未来：校准通过（>60% 命中率）后，高置信字段可接 `audit.record` 记录批量预填事件（IATF 可追溯）。

## 红线
1. **真实 8D 原文一律 gitignore**：`data/golden/*.docx/pdf/csv/json`、`tests/fixtures/real_*`、`results/` 全在 `.gitignore`，`git check-ignore` 自查后入库。
2. **OEM 技术数据硬隔离**：含 OEM 信息的 8D（比亚迪/上汽/理想）禁止混库，scrubber 令牌化前不得传出系统，映射关系存机密映射表（不入 git）。
3. **安全相关低置信必须人工确认**：`safety_related=否 + LOW` 是有意设计（漏标 ASIL 有 ISO 26262 合规风险），工程师不得跳过该字段。
4. **ASIL C/D 绝对禁区**：脚本不得用于含 ASIL C/D 安全证据的 8D 归档，那部分必须 FSE 双签、不走 AI 预填。

## 时间线
- **2026-08-01**：陈忱 7 份黄金样本校准完成，命中率 ≥ 60%（MVP 门槛）— 批改会前可演示。
- **2026-09**：高置信字段接 audit 记录（与 QD-B 同批 ClickHouse 汇聚）。
- **触发 doc_parser 平台化**：第三个 docx 解析场景出现（合同/RFQ，预计 2026-10）。

## 依赖
- `python-docx`（docx 读取）、`pdfplumber`（pdf 回退）：已在 `pyproject.toml`。
- 陈忱提供 7 份黄金样本（`data/golden/`，不入库）+ 对应 12 字段人工标注 CSV（`data/golden/golden.csv`）。
- 校准阈值 60% 由 Paul 拍板（见 design.md §三），后续可据实测调整。
