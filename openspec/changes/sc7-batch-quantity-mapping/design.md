# Design: SC7 标准化批量数量证据入口

## Context

已批准业务口径是料品级 `purchaseBatchQty` 同时作为 MOQ/MPQ，使用现有补货算法；真实 ItemMaster schema、原始字段路径、类型/单位、权限和异常语义未证实。SC7 共享 ERP connector 文件同时承载尚未 ff 的 SC2 receipt 兼容变更。因此本 change 将 Stage 0 放在 SC7 私有模块，不接共享 connector、旧 `get_suppliers()` 或 `run_sc7()`。

本 change 只建立一个有明确 synthetic 来源标签的标准化映射证据入口。它不把 `Mapping` 当作原始行集：构造 Python map 前若 raw source 有重复物料行，重复可能已经被覆盖或折叠；Stage 0 无法观察并声称检测这些重复。未来 raw adapter 必须在压缩为 map 前检测重复/冲突并 fail closed。

## Goals / Non-Goals

### Goals

- 将已标准化、合成的料品批量值映射到现有 Supplier 记录，并维持输入不变。
- 用全字段、确定性 JSON/hash 和真实 JSONL audit 证明 synthetic 输入与结果。
- 校验合同失配时 fail closed，不产生成功结果；真实持久化失败时不返回成功。

### Non-Goals

- 不解析或查询未知 ERP raw ItemMaster schema，不验证组织、权限、单位换算或真实数据。
- 不修改 `get_suppliers()`、`run_sc7()`、`Supplier` 定义、引擎算法、价格、`is_approved`、`lead_time_days`、认证与建议流程。
- 不实现 K2 统计，不产生真实 lead-time 值，不改默认 30 天。
- 不替代采购建议业务审批、R1/R2、L2 或专业签认。

## Proposed Architecture

### 1. 私有纯映射函数

候选新增 `sc7_inventory/batch_quantity.py`，提供两个分层 API：

```python
apply_purchase_batch_qty(
    suppliers: Sequence[Supplier],
    batch_by_material: Mapping[str, int],
) -> list[Supplier]

run_synthetic_batch_evidence(
    suppliers: Sequence[Supplier],
    batch_by_material: Mapping[str, int],
    *, fixture_id: str, revision: str, evaluator: str, audit: AuditLogger,
) -> BatchQuantityEvidence
```

具体名称可在正式 design 审阅中调整。`apply_purchase_batch_qty` 是纯函数，可直接单测且不要求 audit；Stage 0 的唯一证据交付入口为 `run_synthetic_batch_evidence`，它必须强制接收真实 `AuditLogger` 并验证 `audit.sink` 是平台 `JsonlSink`。不得接入旧生产入口或以 MemorySink/no-op sink 替代。

### 2. 标准化输入合同

- `batch_by_material` 的内部合同是 `Mapping[str, int]`：非空白的字符串物料 ID → 严格正整数批量（`type(q) is int` 且 q > 0）。纯空白 ID 拒绝；带首尾空格但非空白的 ID 原样比较、原样快照，不 trim。`bool`、浮点、字符串、`None`、0 和负数均拒绝；不 round、不转换单位、不补 1。
- mapping 的 key 集合必须与 Supplier 输入中出现的唯一 `material_id` 集合完全相等。空/非字符串 ID、缺 key、多余 key均拒绝。重复 Supplier 物料 ID 是允许情形（同料多供应商），每条记录使用同一批量值。
- Mapping 自身无法表示原始 duplicate key 事实。Stage 0 不承诺识别被 map 折叠的重复；后续 raw adapter 的独立前置责任是先检查原始行集重复/冲突，再生成 mapping。
- 不接受 ERP JSON、组织参数、source aliases 或单位信息作为本入口输入；fixture 标签必须标注 `source_kind="synthetic_normalized"`，不得伪装成真实 source。

### 3. 不可变变换

逐条按输入顺序调用 `dataclasses.replace(row, moq=q, mpq=q)`，返回新列表。输入 Supplier 和来源序列不修改。输出记录除 `moq`/`mpq` 外的全部字段须与输入相同，包括 `supplier_id`、`material_id`、`unit_price`、`lead_time_days`、`is_approved`；不排序、不去重、不改变记录数。

纯函数只验证新映射合同和 snapshot 可表示性，不对价格、审批状态或 lead time 添加新的业务有效性判定。输入每条必须是当前平台 `Supplier` 类型，完整七字段快照采用以下严格运行时类型；不隐式转换。`supplier_id` 为 str（不另增业务非空规则），`material_id` 为上述非空白 str；`unit_price` 为有限的内置 int 或 float，拒绝 bool；`moq`、`mpq`、`lead_time_days` 为内置 int，拒绝 bool，但原值不新增正负业务判定；`is_approved` 为内置 bool。Decimal、嵌套容器、任意对象、NaN/Infinity 或类型失配均拒绝。输入价格为 int 时快照保留 int，不转 float；负价格、负原交期等合法类型值仅原样记录，本入口不因此作业务判定。Supplier 字段集合变更时先修订合同，不静默丢掉新字段。

### 4. 证据封套与 canonical hash

Stage 0 evidence envelope 固定包含：

- `evidence_contract="sc7-batch-quantity-evidence-v1"`；
- `fixture_id`、`revision`、`source_kind="synthetic_normalized"`；
- 完整 Supplier 输入顺序和每个 Supplier 的全部字段；
- 完整 batch map（按 key 排序的 JSON 表示）；
- 完整 Supplier 输出顺序和全部字段；
- 输入 hash、结果 hash、审计内容 hash；摘要的前像如下逐层定义。

JSON 用 UTF-8、排序 key、固定分隔符、`ensure_ascii=False` 与 `allow_nan=False` 做确定性序列化；hash 使用 SHA-256。设 `meta` 为 evidence_contract/fixture_id/revision/source_kind。`input_hash` 对 `{meta, suppliers_input, batch_by_material}` 求摘要；`result_hash` 对 `{meta, input_hash, suppliers_output}` 求摘要；`audit_content_hash` 对包含 meta、evaluator、完整输入/map/输出及前两个 hash 的 evidence body 求摘要。这个 body 不包含 audit_content_hash 本身，也不包含每次事件 UUID、平台 timestamp 或 prev_hash。摘要求出后才添加 audit_content_hash 到返回封套，并将相同值写进 `AuditEvent.content_hash`。平台 prev_hash 是原始 JSONL 字节链，和应用层内容摘要分别验证，不互相替代。所有输出均标 synthetic；不记录不存在的 raw payload、API version、IT owner 或专业批准。

### 5. Audit 与失败语义

Stage 0 成功入口必须：

1. 要求非空白 fixture/revision；必填 evaluator 为 `synthetic:` 前缀且后缀非空白的合成操作者标签，原样记录。该标签不声称人员实名或专业签认，不从 fixture 推断身份。
2. 仅接受真实平台 `AuditLogger` + `JsonlSink`。由调用方提供独立空 JSONL 目标，单进程单调用拥有该目标；写前确认无非空记录且链有效。写一条平台 `AuditEvent`：scenario=SC7、action=synthetic_batch_quantity_evidence、automation_level=L1、evaluator 使用必填标签，decision 含 evidence 封套与本次新 UUID evidence_id，data_sources 明示 synthetic_normalized/fixture/revision，content_hash 使用上述应用摘要。UUID 与 timestamp 用于定位本次事件，不参与内容摘要。
3. `record()` 成功返回后同时回读磁盘原始 JSONL 和调用 `verify_chain()`：恰有一条非空、可解析记录；链 ok 且 total=1；记录的 evidence_id、scenario/action/L1/evaluator、完整 decision/data_sources、content_hash 与本次预期逐项相等。空文件、错误事件、重复事件、坏 JSON、链错或值失配均拒绝成功；不只依赖会跳过坏 JSON 的 read_all()。验证后才返回 `BatchQuantityEvidence`，返回同时携带 evidence_id 和摘要便于查验。此合同不提供多调用复用同一审计目标的并发保证。Stage 0 不调用 L2 人工批准或作业务建议。

失败边界：已能安全识别的合同错误可用固定错误码、fixture/revision/source 标签及必要的安全物料 ID 写入失败 audit；未通过 JSON-safe 检查的任意对象原值不得塞进 audit。若最小失败事件也无法安全序列化/持久化，则保留异常并不返回成功，不能承诺一定落下一条 audit。这个 Stage 0 约束不声称原始 ERP 行可被审计，因为其尚未接入。

## Alternatives

1. **接入共享 `get_suppliers()` 并加 provider**：不采纳于 Stage 0。它把未证实的 raw contract 引入共享 connector，且和未合并 SC2 receipt 变更共享文件，扩大兼容面并容易因旧基线覆盖 SC2。
2. **只写纯映射函数，不提供证据入口**：不足。纯函数适合单元验证，但不能满足 Stage 0 输出需可追溯的 IATF 证据要求。
3. **继续使用 MOQ/MPQ=1 作为缺省并仅标日志**：不采纳。缺失/非法批量会变成看似有效的补货建议，违背 fail-closed 和已批业务口径。

## Compatibility and Future Integration

- 生产 `Supplier` defaults 和 `get_suppliers()` 行为不变；Stage 0 是显式 synthetic 新入口，不会被旧生产流程自动调用。
- SC2 candidate 中 `get_receipt_batch()`、旧 `get_receipt_lines()` 缓存/兼容逻辑和 receipt scope/version pairing 完全在本 change 之外。若未来 K1 真实接 connector，必须先基于包含 SC2 兼容改动的当前基线另行 design；不得复制旧 connector 整文件覆盖 SC2。
- 未来 raw ItemMaster adapter 是独立后续阶段：需 IT 证实 endpoint/request/response、物料自证、组织/权限、原始类型、单位、缺值和重复行语义，并由独立批准列明触碰范围。Stage 0 mapping 不证明 API 实现。
- K2 保持现有 `lead_time_days=30`；既有统计器仅为未来数据阶段候选，须真实数据卫生核验和采购专业人员签认之后再独立审批参数采用。

## Risks

- 仅 Stage 0 synthetic evidence 不能证明真实 ERP mapping 正确；必须在输出/审计/report 中醒目标 synthetic。
- Mapping 无法暴露其创建前的 raw duplicate keys；未来 adapter 必须先检查 raw rows。
- shared connector 的 SC2 candidate 尚未 ff；未来真实整合须确认新基线并保护其收货行为。
- JSON 序列化无法表示未受限任意对象；输入快照失败时不得伪造 hash 或成功 audit。
- K2 原统计器实际取数前需单独复核连接配置、缓存/落盘范围和 TLS 证书校验；专业签认未获得前不变更生产 30 天。

## Open Decisions for Written Design Review

- 是否接受以 `sc7_inventory/batch_quantity.py` 为唯一 Stage 0 实现模块、以 proposal 所列一个新测试文件为候选白名单。
- 是否接受合同错误的安全失败事件尽力审计、但无法规范化的任意原对象不进入 audit 且审计本身失败即整体失败的语义。
- 是否接受明确区分“L1 synthetic 结构证据”与“采购建议/L2/真实 ERP readiness”。
