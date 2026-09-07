## MODIFIED Requirements

### Requirement: verify_chain() 可检测篡改
`JsonlSink` SHALL 提供 `verify_chain() -> ChainVerifyResult` 方法，逐行重算 `prev_hash` 并与记录中存储值比对。`ChainVerifyResult` 含 `ok: bool`、`total: int`、`broken_at: int | None`（首个不匹配的行号，1-based）、`error: str`。无 `prev_hash` 字段的 genesis 豁免 MUST 仅对**第 1 段的第 1 行**生效；第 2 行起任何缺 `prev_hash` 字段的记录 MUST 判为断链（`ok=False, broken_at=idx`），杜绝"删光全文件 prev_hash 字段重写即整链通过"的防篡改绕过。

🔴 引入滚动封存后，genesis 豁免 MUST NOT 被放宽为"每个段的第 1 行"。第 2 段起的热文件首行 MUST 是续接记录且其 `prev_hash` 非空；该行缺失或 `prev_hash` 为空 MUST 判为断链。

`verify_chain()` SHALL 支持跨段校验：沿封条链回溯逐段重算，并对每段核对封条中记录的 `first_line_sha256`／`last_line_sha256`／`line_count`。段文件缺失、段内容被改、封条被篡改，三者 MUST 均返回 `ok=False` 并指出段名。

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
- **THEN** 返回 `ok=True`（仅第 1 段第 1 行 genesis 豁免保留向后兼容）

#### Scenario: 剥光 prev_hash 字段的整链重写被检测
- **WHEN** 一个 ≥3 条的正常链文件被删除全部 `prev_hash` 字段后重写，再调用 `verify_chain()`
- **THEN** 返回 `ok=False` 且 `broken_at == 2`

#### Scenario: 第 2 段首行不得当 genesis 放行
- **WHEN** 第 2 段起的热文件首行缺 `prev_hash` 或 `prev_hash` 为空字符串
- **THEN** 返回 `ok=False`——段边界 MUST NOT 成为 genesis 豁免的新入口

#### Scenario: 已封存段内某行被删除时跨段检出
- **WHEN** 从一个已封存段中删掉一行后执行跨段校验
- **THEN** 返回 `ok=False`，且报出段名与该段内行号

#### Scenario: 整段文件缺失时跨段检出
- **WHEN** 一个段文件被整个删除后执行跨段校验
- **THEN** 返回 `ok=False`，封条链在该处断裂

## ADDED Requirements

### Requirement: 段边界 SHALL 由续接记录保持链的数学连续
封存后新起的热文件，其首行 MUST 是一条 `action="audit_segment_continuation"` 的记录，其 `prev_hash` MUST 等于上一段末行原始字节的 sha256。据此，跨段的哈希链在段边界处保持连续，无需对任何既有行重新计算。

#### Scenario: 续接记录接住上一段末行
- **WHEN** 一份热文件被封存为段并新起热文件
- **THEN** 新热文件首行的 `prev_hash` 等于该段末行原始字节的 sha256

#### Scenario: 续接记录不携带业务内容
- **WHEN** 检查续接记录内容
- **THEN** 它只含段标识与链接哈希，不含 `decision`／`payload` 等业务字段

### Requirement: 封条摘要 SHALL 可被锚定到审计写方改不动的位置
链尾指纹 MUST 可被导出为只含哈希、行数与时刻的摘要，用于锚定到审计文件写方不具备写权限的位置。摘要 MUST NOT 含 `decision`／`evaluator`／`payload` 或任何业务字段。锚点载体的具体形态由 design Open Question O2 定。

#### Scenario: 摘要不含业务数据
- **WHEN** 导出封条摘要
- **THEN** 内容仅为段名、行数、首末行哈希、时刻与上一封条哈希

#### Scenario: 锚点载体须真的进得了版本控制
- **WHEN** 锚点台账落盘
- **THEN** 其路径经 `git check-ignore` 实测确认未被忽略；落在 `reports/` 下或使用 `.jsonl` 扩展名 MUST 视为配置错误（实测均被静默忽略且不报错）
