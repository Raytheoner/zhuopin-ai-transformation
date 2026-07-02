# audit-hash-chain Specification

## Purpose
TBD - created by archiving change platform-hardening-p2. Update Purpose after archive.
## Requirements
### Requirement: JsonlSink 写入时嵌入 hash-chain
`JsonlSink` SHALL 在每条写入记录中嵌入 `prev_hash` 字段（前一条记录完整 JSON 行的 SHA-256 十六进制摘要，`sort_keys=True`）。第一条记录（genesis）`prev_hash` 为空字符串 `""`。`prev_hash` 计算与写入 MUST 在同一线程锁内完成，保证多线程下链不断裂。实例变量 `_last_hash` 缓存上一条哈希，初次写时从文件末尾读取（文件不存在则 genesis）。

#### Scenario: 首条记录为 genesis
- **WHEN** JsonlSink 写入第一条 AuditEvent 且文件不存在
- **THEN** 写入的 JSON 行含 `prev_hash: ""`

#### Scenario: 后续记录链接前一条
- **WHEN** JsonlSink 连续写入第 N+1 条 AuditEvent
- **THEN** 第 N+1 条的 `prev_hash` 等于第 N 条完整 JSON 行的 SHA-256（sort_keys=True）

#### Scenario: 多线程并发写不断链
- **WHEN** 多个线程并发调用 `write()`
- **THEN** 所有记录形成完整的单链，无 `prev_hash` 指向错误记录

### Requirement: verify_chain() 可检测篡改
`JsonlSink` SHALL 提供 `verify_chain() -> ChainVerifyResult` 方法，逐行重算 `prev_hash` 并与记录中存储值比对。`ChainVerifyResult` 含 `ok: bool`、`total: int`、`broken_at: int | None`（首个不匹配的行号，1-based）、`error: str`。首条无 `prev_hash` 字段的记录视为合法 genesis。

#### Scenario: 完整链校验通过
- **WHEN** 对未被篡改的 JSONL 文件调用 `verify_chain()`
- **THEN** 返回 `ChainVerifyResult(ok=True, total=N, broken_at=None)`

#### Scenario: 单条记录被删除时检测
- **WHEN** JSONL 文件中某行被删除后调用 `verify_chain()`
- **THEN** 返回 `ChainVerifyResult(ok=False, broken_at=<行号>)`

#### Scenario: 单条记录内容被篡改时检测
- **WHEN** JSONL 文件中某行的 `decision` 字段被修改后调用 `verify_chain()`
- **THEN** 返回 `ChainVerifyResult(ok=False, broken_at=<行号>)`

### Requirement: AuditLogger 暴露 verify_chain 接口
`AuditLogger` SHALL 提供 `verify_chain() -> ChainVerifyResult` 方法，委托给底层 sink（非 JsonlSink 时返回 `ok=True, total=0, error="sink does not support chain verification"`）。

#### Scenario: AuditLogger 代理校验
- **WHEN** 调用 `audit.verify_chain()`
- **THEN** 结果与直接调用底层 `JsonlSink.verify_chain()` 一致

