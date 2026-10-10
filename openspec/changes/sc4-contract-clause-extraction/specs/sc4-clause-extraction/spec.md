## Purpose

从采购合同文本中定位并切分条款、按四类（价格/交付/质保/违约责任）归类、保留可回指原文的偏移量，
并把「与标准条款库比对、风险分级、缺失条款识别」三项**依赖法务判据的能力挡在前置闸之后**。
本能力只回答「文档里有什么」，不回答「它算不算风险」。

## MODIFIED Requirements

### Requirement: 条款切分与定类
系统 SHALL 把一份合同文本切分为条款片段，每个片段 MUST 携带其在源文档中的起止偏移量，
使审核产出的任何一句都能回指原文。系统 SHALL 依据一份**由调用方显式传入**的词表对片段定类，
MUST NOT 为词表提供默认值。

#### Scenario: 四类条款各自被定位
- **WHEN** 合同含价格、交付、质保、违约责任四类条款各一段
- **THEN** 系统为每类各产出一个片段，且片段类型与规划点名的四类一一对应

#### Scenario: 偏移量可回指原文
- **WHEN** 系统产出任一条款片段
- **THEN** 以该片段的起止偏移量截取源文档所得文本，与片段自身记录的文本一致

#### Scenario: 多类命中不猜
- **WHEN** 某条款标题同时命中两类词表条目
- **THEN** 系统将其归为「未归类」交人判定，而不是任选其一

#### Scenario: 切不出类别的段落如实留痕
- **WHEN** 某段落的标题不命中任何词表条目
- **THEN** 系统仍为其产出片段并标为「未归类」，MUST NOT 丢弃该段落

#### Scenario: 整篇无条款标题
- **WHEN** 文档中不存在任何条款标题行
- **THEN** 系统返回空的片段集合，MUST NOT 把全文合并为单个片段

### Requirement: 覆盖概览只陈述事实
系统 SHALL 提供一份抽取概览，包含片段总数、命中的条款类别、未归类数量与所用词表标识。
该概览 MUST NOT 包含任何形式的「缺失条款」字段。

#### Scenario: 概览不提供缺失结论
- **WHEN** 一份合同只命中价格与交付两类
- **THEN** 概览如实列出这两类，且不出现「缺少质保/违约责任」之类的结论字段

#### Scenario: 所用词表可追溯
- **WHEN** 系统产出概览
- **THEN** 概览携带本次所用词表的标识，使词表升版后旧结论仍能被识别为旧词表产物

### Requirement: 法务判据前置闸
在「公司标准合同条款库」与「合同风险条款判据」两项前置到位前，系统 MUST NOT 提供
标准条款比对、风险等级判定、缺失条款识别三项能力的任何默认实现。调用这三项能力时
系统 SHALL 失败，且错误信息 MUST 指明卡在哪一项前置、其 Owner 与判据源。

#### Scenario: 比对能力被调用
- **WHEN** 调用方请求与标准条款库比对
- **THEN** 系统抛出前置未到位错误，信息中含「公司标准合同条款库」及其判据源出处

#### Scenario: 风险分级被调用
- **WHEN** 调用方请求风险等级判定
- **THEN** 系统抛出前置未到位错误，信息中含「合同风险条款判据」及其判据源出处

#### Scenario: 未登记的前置键
- **WHEN** 调用方以一个未登记的前置键请求闸判定
- **THEN** 系统报错，MUST NOT 静默放行

### Requirement: 取文层边界
系统 SHALL 通过可替换取文接口获取合同文本，MUST NOT 自建PDF/Word解析实现。
已批准的合成TXT/DOCX证据路径 SHALL 仅对受控合成目录一次捕获源字节；TXT按UTF-8保留原换行，
DOCX从该次字节快照委托平台doc_parser.extract_text(include_extra_parts=False)。旧PlainTextSource合同保留。
PDF、旧.doc、扫描件及OCR不属于本阶段，SHALL 明确拒绝；平台解析错误MUST传播，不当空文本成功。

#### Scenario: 纯文本取文
- **WHEN** 传入受控合成.txt或.md样例
- **THEN** 返回该次字节按UTF-8解码的原文本、来源身份/修订及hash，保留CRLF

#### Scenario: 合成DOCX经共享解析器取文
- **WHEN** 传入受控合成.docx且平台parser可用
- **THEN** 从同一已捕获字节的独立snapshot取文，记录显式extractor profile/version和canonical text hash

#### Scenario: 非支持二进制后缀被拒绝
- **WHEN** 传入.pdf、.doc、扫描件或非受控真实合同
- **THEN** 明确拒绝，不按文本读取、不自建解析/OCR、不默认为合成来源

#### Scenario: DOCX解析失败
- **WHEN** 已捕获的DOCX无法由平台parser读取
- **THEN** 传播解析失败，MUST NOT 等同于无标题的合法空片段集合

### Requirement: L2 留痕与可归责
本期完整来源证据入口run_source_evidence的每次抽取 SHALL 写入平台审计，记录场景、动作、可归责人、自动化等级 L2、所用词表与来源。
可归责人为空时系统 MUST 拒绝执行。审计记录 SHALL 标明审核尚未开始及其被哪些前置阻塞。

#### Scenario: 缺可归责人
- **WHEN** 调用方未提供可归责人
- **THEN** 系统拒绝执行并说明 L2 场景须留可归责人

#### Scenario: 审计如实标注审核未开始
- **WHEN** 系统完成一次抽取并写入审计
- **THEN** 该条记录的审核状态为「待前置到位」，并列出被阻塞的两项前置键

#### Scenario: 历史入口兼容不计完整来源验收
- **WHEN** 调用旧run_extraction(...,audit=None)或直接segment
- **THEN** 保留获批具体计划的兼容行为，但MUST NOT记作六项完整来源run或业务审核验收

## ADDED Requirements

### Requirement: 版本化抽取证据
合成完整run SHALL 非空artifact_id/revision、lexicon_id、源字节SHA256、canonical text SHA256、
extractor profile/version及offset scheme；offset SHALL 为Python codepoint的0-based半开区间。
每片段text MUST 等于raw_text[start:end]；展示trim MUST与证据字段分离。DOCX offset只回指canonical text，不冒称Word页码/XML位置。

#### Scenario: 空白与CRLF可回指
- **WHEN** 合成条款含前后空白及CRLF
- **THEN** raw_slice严格等于记录text，展示清理不改写原片段/偏移量

#### Scenario: 相同覆盖不同来源修订
- **WHEN** 两份输入覆盖概览相同但artifact revision或源字节不同
- **THEN** 对应证据身份/hash可区分，不能以同覆盖代替同输入

### Requirement: 合成证据审计失败关闭
完整合成run SHALL 使用可写平台audit记录真实持久化事件，保留L2/evaluator、审核未开始及blocked_by。
审计仅记录来源引用/hash/版本和摘要，不写原合同；纯segment函数可无IO，但不得被称为完整run。

#### Scenario: 审计缺失或写失败
- **WHEN** 完整run没有可写audit或sink写入失败
- **THEN** 不返回完整run成功，传播失败，不开启专业审核

#### Scenario: 六项证据对照
- **WHEN** 执行已批准六项合成场景
- **THEN** 对照TXT/DOCX同canonical输入、四类及多类OTHER、未命中、无标题、空白/CRLF、同覆盖换版本；保留每项输入身份/预期/实际差异

