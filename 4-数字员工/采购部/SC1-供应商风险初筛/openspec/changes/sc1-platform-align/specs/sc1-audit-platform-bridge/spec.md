## ADDED Requirements

### Requirement: SC1AuditAdapter 保留 append_record() 接口
SC1 SHALL 提供 `SC1AuditAdapter`（替换本地 `AuditLogger`），其 `append_record(evaluator, supplier_name, supplier_code, result, delivery_source, ai_text_hash, report_path, error)` 签名与旧版完全一致，内部委托给 `zhuopin_platform.audit.AuditLogger.record(AuditEvent(...))`。`main.py` 无需修改调用侧代码。

#### Scenario: append_record 写入 AuditEvent 格式
- **WHEN** 调用 `adapter.append_record(evaluator="张三", supplier_name="供应商A", ...)`
- **THEN** JSONL 文件有一条记录，含 `scenario="SC1"`、`action="supplier_risk_eval"`、`evaluator="张三"`、`decision.supplier_name="供应商A"`、`decision.risk_level=<整数>`

#### Scenario: 红色数据不落盘
- **WHEN** 注册资本 1000.0 万、IQC 合格率 97.5% 传入 ScoringResult
- **THEN** JSONL 原始内容中不含字符串 "1000.0" 也不含 "97.5"

### Requirement: verify_chain() 委托平台 hash-chain
`SC1AuditAdapter` SHALL 暴露 `verify_chain()` 方法，委托给平台 `AuditLogger.verify_chain()`，返回 `ChainVerifyResult`。

#### Scenario: 多条记录 verify_chain 通过
- **WHEN** 连续写入 3 条记录后调用 `adapter.verify_chain()`
- **THEN** 返回 `ChainVerifyResult(ok=True, total=3)`

#### Scenario: 篡改文件后 verify_chain 失败
- **WHEN** 手动修改 JSONL 中一条记录的内容后调用 `verify_chain()`
- **THEN** 返回 `ok=False`，`broken_at` 非空

### Requirement: query_by_supplier() 委托平台 query_by
`SC1AuditAdapter.query_by_supplier(supplier_name)` SHALL 委托给 `platform_logger.query_by(supplier_name=...)` 并返回相同格式的摘要列表。

#### Scenario: 查询指定供应商历史记录
- **WHEN** 写入 3 条同一供应商记录 + 1 条其他供应商记录后查询
- **THEN** 返回 3 条，每条含 `timestamp`、`risk_level`

### Requirement: import 全走平台，无本地 AuditLogger 主体
切换后 `src/audit_log.py` SHALL 不包含自造的 JSON 写入逻辑，所有写入经 `zhuopin_platform.audit`。

#### Scenario: grep 无本地 json.dumps 写入
- **WHEN** grep `src/audit_log.py` 中 `json.dumps`
- **THEN** 无匹配（写入逻辑已移至平台）
