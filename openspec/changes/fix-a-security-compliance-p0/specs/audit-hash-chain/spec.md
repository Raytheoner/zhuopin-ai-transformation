## MODIFIED Requirements

### Requirement: verify_chain() 可检测篡改
`JsonlSink` SHALL 提供 `verify_chain() -> ChainVerifyResult` 方法，逐行重算 `prev_hash` 并与记录中存储值比对。`ChainVerifyResult` 含 `ok: bool`、`total: int`、`broken_at: int | None`（首个不匹配的行号，1-based）、`error: str`。无 `prev_hash` 字段的 genesis 豁免 MUST 仅对**第 1 行（`idx==1`）**生效；第 2 行起任何缺 `prev_hash` 字段的记录 MUST 判为断链（`ok=False, broken_at=idx`），杜绝"删光全文件 prev_hash 字段重写即整链通过"的防篡改绕过。

#### Scenario: 完整链校验通过
- **WHEN** 对未被篡改的 JSONL 文件调用 `verify_chain()`
- **THEN** 返回 `ChainVerifyResult(ok=True, total=N, broken_at=None)`

#### Scenario: 单条记录被删除时检测
- **WHEN** JSONL 文件中某行被删除后调用 `verify_chain()`
- **THEN** 返回 `ChainVerifyResult(ok=False, broken_at=<行号>)`

#### Scenario: 单条记录内容被篡改时检测
- **WHEN** JSONL 文件中某行的 `decision` 字段被修改后调用 `verify_chain()`
- **THEN** 返回 `ChainVerifyResult(ok=False, broken_at=<行号>)`

#### Scenario: 首行旧文件无 prev_hash 仍合法
- **WHEN** 单行旧格式文件（首条无 `prev_hash` 字段）调用 `verify_chain()`
- **THEN** 返回 `ok=True`（仅首行 genesis 豁免保留向后兼容）

#### Scenario: 剥光 prev_hash 字段的整链重写被检测
- **WHEN** 一个 ≥3 条的正常链文件被删除全部 `prev_hash` 字段后重写，再调用 `verify_chain()`
- **THEN** 返回 `ok=False` 且 `broken_at == 2`（第 2 行起缺字段即判篡改，不再被当 genesis 放行）
