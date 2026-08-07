## Purpose

把陈忱团队提供的 8D 报告原文（docx/pdf/pptx 任一格式）解析为按 D1-D8 步骤索引的结构化段落，供下游字段提取器消费，接口与未来平台 `shared_tools/doc_parser.py` 保持同构以便日后零改动迁移。

## ADDED Requirements

### Requirement: 多格式统一读取入口
系统 SHALL 提供统一入口函数，按文件扩展名路由到对应解析器：`.docx`/`.doc` → docx 解析、`.pdf` → pdf 解析、`.pptx`/`.ppt` → pptx 解析；不支持的扩展名 MUST 显式抛出 `ValueError`，不得静默返回空结果。

#### Scenario: docx 输入
- **WHEN** 传入 `.docx` 文件路径
- **THEN** 系统按段落逐一提取文本并拼接为全文，供后续段落切分消费

#### Scenario: pdf 输入
- **WHEN** 传入 `.pdf` 文件路径
- **THEN** 系统逐页提取文本并按行拼接为全文

#### Scenario: pptx 输入（幻灯片按 D 步骤组织）
- **WHEN** 传入 `.pptx` 文件路径，且报告以一张幻灯片对应一个 D 步骤的形式组织
- **THEN** 系统按幻灯片内形状的空间顺序（先上后左）提取文本框与表格内容并拼接

#### Scenario: 不支持的格式
- **WHEN** 传入扩展名不属于 docx/doc/pdf/pptx/ppt 的文件路径
- **THEN** 系统 SHALL 抛出 `ValueError`，明确说明支持的格式范围

### Requirement: D1-D8 段落切分（含标题回退识别）
系统 SHALL 从全文中识别 D1-D8 各步骤的段落边界并切分为独立段落，支持两种标头形式：① 显式「Dn:」/「Dn：」/「第N步：」/「Step N:」前缀行；② 无编号前缀、仅以 8D 标准步骤中英文标题命名的短标题行（如"团队成员"/"问题描述"/"根本原因"），按标题语义回退映射到对应 D 编号。全文前 500 字额外保留为 `header_text` 供标题类字段（如案例编号）提取使用。

#### Scenario: 显式编号前缀识别
- **WHEN** 全文中存在形如 `D4: 根本原因：电容降额不足。` 的行
- **THEN** 系统将其后续内容切入 `sections["D4"]`，且该内容不再重复出现于其他段落

#### Scenario: 无编号前缀的标题行回退识别
- **WHEN** 报告某短标题行（≤40 字）内容为"问题描述"或"Root cause"等 8D 标准步骤中英文名，且未带「Dn.」前缀
- **THEN** 系统 SHALL 将其识别为对应 D 编号的段落起点，正文从下一行开始归入该段落

#### Scenario: 无任何可识别段落标头
- **WHEN** 全文不含任何 D 编号前缀或标准步骤标题
- **THEN** `sections` 返回空字典，`full_text` 仍保留完整原文，不抛异常

#### Scenario: 同一 D 编号不重复覆盖
- **WHEN** 无前缀标题回退识别已命中过某 D 编号
- **THEN** 后续再次出现同一 D 编号的标题回退匹配 MUST 被忽略，不覆盖已切分的段落内容
