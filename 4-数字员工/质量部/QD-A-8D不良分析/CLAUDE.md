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
- **2026-07-04（轨 A 校准跑通）**：原始 8D 为 .pptx（原 reader 仅 docx/pdf），已打通：pptx 解析 + 段落识别加「D1.」点号 & 无前缀标题回退（files 4-7）；xlsx「8D历史库录入表」黄金加载；12 字段可信度地图（候选）+ 逐字段 diff。**7/7 可校准**（案例1/2 曾源文件截断——交付 zip 内即 10MB/20MB 整、缺 EOCD，非本机/OneDrive；已由质量部重取完整原件替换、重跑通过）。脱敏加固：邮箱泄漏堵住（原全漏）、平台误匹配 362→1-4、供应商前缀修复。**校准结果在 `results/`（gitignore/LAN）交陈忱校准会审定档位终版**。31→41 tests。可信度地图（7份）：🟢安全相关/FMEA、🟡D2/D5-D7段落抓取、🔴其余（含**不良分类仅3/7、关键词分类器不可靠、建议降需人工**）。3 个坑（根因验证口径矛盾/案例4-5 安全相关复核/分类分歧）脚本只标不判、待陈忱。
- **2026-08-01**：陈忱 7 份黄金样本校准完成，命中率 ≥ 60%（MVP 门槛）— 批改会前可演示。
- **2026-09**：高置信字段接 audit 记录（与 QD-B 同批 ClickHouse 汇聚）。
- **触发 doc_parser 平台化**：第三个 docx 解析场景出现（合同/RFQ，预计 2026-10）。

## 依赖
- `python-docx`（docx 读取）、`pdfplumber`（pdf 回退）：已在 `pyproject.toml`。
- 陈忱提供 7 份黄金样本（`data/golden/`，不入库）+ 对应 12 字段人工标注 CSV（`data/golden/golden.csv`）。
- 校准阈值 60% 由 Paul 拍板（见 design.md §三），后续可据实测调整。
