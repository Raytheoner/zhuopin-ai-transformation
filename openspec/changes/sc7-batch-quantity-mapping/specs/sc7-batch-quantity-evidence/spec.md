# sc7-batch-quantity-evidence Specification

## Purpose

本能力为 SC7 已批准的 `purchaseBatchQty` 业务语义建立一个隔离的合成证据入口：对明确标准化的物料批量映射执行严格校验，按物料生成 Supplier 副本，并以确定性快照/hash 和平台 JSONL 审计记录输入、结果及来源标签。它不实现真实 ERP ItemMaster 查询，也不产生采购业务签认。

## ADDED Requirements

### Requirement: 标准化批量映射合同

系统 MUST 对每个 Supplier material ID 使用同一个正整数批量值，并将其写入该输出记录的 MOQ 与 MPQ。输入必须是明确提供的标准化物料 ID 到批量整数映射；不得将未知 ERP raw schema 当作该合同。

#### Scenario: 合法的多供应商同料映射

- **GIVEN** 多条 Supplier 记录共享同一非空 material ID，且标准化映射对该物料给出严格正整数
- **WHEN** 调用纯映射函数
- **THEN** 每条对应记录的 MOQ 与 MPQ 都等于该值
- **AND** 输出记录数和原始顺序保持不变
- **AND** 除 MOQ 与 MPQ 外所有 Supplier 字段与输入相同

#### Scenario: 每种物料使用各自批量值

- **GIVEN** Supplier 记录含不同 material ID，映射对每个 ID 给出不同的严格正整数
- **WHEN** 调用纯映射函数
- **THEN** 每条记录只采用其自身 material ID 的映射值
- **AND** 不以 supplier ID 拆分或重新关联批量值

### Requirement: 合同错误必须 fail closed

系统 MUST 在 key 集合与 Supplier 物料集合不完全一致、key 为空白或非字符串、value 不是内置严格正整数（包括 bool、浮点、字符串、null、0 或负数）时拒绝成功结果。带首尾空格但非空白的 ID MUST 原样比较和快照。系统 MUST NOT trim、round、换算、补默认值或静默回退到 `1`。本标准化 mapping 已无法表示被创建前折叠的重复 raw key；该能力 MUST NOT 声称识别此类重复，未来 raw adapter MUST 在转换成 mapping 之前检查并拒绝冲突重复行。

#### Scenario: 批量映射缺少物料 key

- **GIVEN** Supplier 输入包含某个 material ID，但 mapping 没有该 ID
- **WHEN** 调用映射函数或 Stage 0 证据入口
- **THEN** 操作以可识别的合同错误失败
- **AND** 不产生成功的 Supplier 列表或证据对象

#### Scenario: 批量映射含额外 key 或非法 value

- **GIVEN** mapping 含 Supplier 输入未出现的物料 key，或任一 value 不是严格正整数
- **WHEN** 调用映射函数或 Stage 0 证据入口
- **THEN** 操作 fail closed，不忽略该 key、不转换 value、不回退为 `1`

#### Scenario: 原始重复数据不在 mapping 能力范围

- **GIVEN** 上游 raw 行在压缩成 mapping 前存在重复物料 ID
- **WHEN** 后续真实 adapter 准备构造标准化 mapping
- **THEN** adapter 在压缩前检测重复并按批准规则拒绝冲突
- **AND** Stage 0 mapping 本身不声称能恢复已折叠的 raw 重复事实

### Requirement: 输入不可变且来源可追溯

Stage 0 evidence entry MUST 要求显式非空白 fixture ID、revision 和 `source_kind="synthetic_normalized"`，为完整 Supplier 输入、完整 mapping 和完整输出生成确定性 JSON-safe 快照及 SHA-256 身份。系统 MUST 产生 Supplier 新对象，且不修改调用方的 Supplier 对象或输入序列。当前七字段 MUST 按严格类型记录：supplier_id 为 str，material_id 为非空白 str，unit_price 为有限内置 int/float 且非 bool，moq/mpq/lead_time_days 为内置 int 且非 bool，is_approved 为内置 bool；Decimal、嵌套容器、任意对象、NaN/Infinity 或类型失配 MUST fail closed。系统 MUST 保留原数值类型，不新增价格、认证或交期业务判定。input_hash/result_hash/audit_content_hash MUST 按 design 的分层前像计算；audit_content_hash 前像不含自身摘要、事件 UUID、timestamp 或 prev_hash，应用摘要与 JSONL 字节链分别核验。

#### Scenario: synthetic 快照身份可复核

- **GIVEN** 同一 fixture ID/revision/source 标签、同一完整输入及同一 mapping
- **WHEN** Stage 0 构建 evidence envelope
- **THEN** 规范化输入与结果 hash 可重复计算
- **AND** envelope 含完整 Supplier 字段、完整 mapping、完整输出及 evidence contract/source 标签

#### Scenario: 序列化输入不受支持

- **GIVEN** Supplier 输入包含 NaN、Infinity 或无法安全 JSON 规范化的对象
- **WHEN** Stage 0 尝试生成证据
- **THEN** 操作 fail closed，不返回成功证据或伪造 hash
- **AND** 不对原始任意对象承诺成功写入失败 audit

### Requirement: Stage 0 成功结果必须有真实 JSONL 审计

Stage 0 evidence entry MUST 使用平台真实 `AuditLogger` 和 `JsonlSink` 持久写入审计事件；纯映射函数可以无 audit。入口 MUST 显式接收 `synthetic:` 前缀且后缀非空白的 evaluator 标签，不从 fixture 推断。证据入口 MUST NOT 使用 memory/no-op sink 返回成功。调用方 MUST 提供独立空 JSONL 目标且单调用拥有该目标；写后 MUST 严格回读恰一条原始可解析记录，核对本次唯一 evidence_id、SC7/action/L1/evaluator、完整 decision/data_sources/content_hash，且 verify_chain() 为 ok/total=1 后才返回成功。空文件、重复或错误事件、坏 JSON、写入/sink/链/值失配 MUST 阻止成功返回。此合成 L1 结构审计 MUST NOT 被解释成采购业务批准或 L2 签认，亦不提供多调用共用同一目标的并发保证。

#### Scenario: 合成证据写入真实审计链

- **GIVEN** 输入合同有效、snapshot 可安全规范化，且 audit 使用真实平台 JsonlSink
- **WHEN** Stage 0 生成 synthetic evidence
- **THEN** 平台 JSONL 中持久存在对应场景/动作/source 标签、snapshot/hash 与合成操作者信息
- **AND** 审计链核验成功后才返回 evidence

#### Scenario: audit 写入失败

- **GIVEN** 输入有效，但真实 JSONL sink 无法写入或链校验失败
- **WHEN** 调用 Stage 0 evidence entry
- **THEN** 调用失败并不返回成功 evidence
- **AND** 纯映射函数语义与 Supplier 值不因此被重新解释为已审计

#### Scenario: 链空或落盘事件不匹配

- **GIVEN** record() 返回但文件为空，或落盘事件的 UUID/内容不匹配，或多于一条记录
- **WHEN** 入口严格回读并校验 JSONL
- **THEN** 操作失败，即使某次 verify_chain().ok 为 true 也不返回成功 evidence

#### Scenario: 业务签认保持人工

- **GIVEN** synthetic evidence 已写入 L1 结构审计
- **WHEN** evidence 被下游查看
- **THEN** 记录仍明确标为 synthetic，不声称真实 ERP 接通、采购建议获批、R1/R2 满足或 L2 已签认
