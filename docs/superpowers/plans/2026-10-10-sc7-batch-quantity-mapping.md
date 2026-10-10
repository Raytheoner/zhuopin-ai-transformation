# SC7 标准化批量数量证据入口实施计划

**状态：** 正式具体实施计划；待 Shao Peishen 审阅批准。已批准 design SHA256 为 `921FC0E4B60E50D44F51B452E87A29DAB80058DA7B077AD56DFC319A2977118A`。design 的批准不自动批准本计划、隔离 checkout 创建、逐文件白名单或代码实施。正式登记后仍须本次具体计划审批，才能执行。

**Goal：** 在 SC7 私有模块中实现严格的标准化 `purchaseBatchQty`→MOQ/MPQ 映射，并用完整 synthetic snapshot/hash 与真实 JSONL 单事件回读及链验证证明映射结果。

**Architecture：** 新增 `sc7_inventory/batch_quantity.py`，不接现有生产调用图。纯映射函数校验完整 Supplier 和 mapping 合同并用 `dataclasses.replace` 产生新 Supplier 副本；evidence 入口生成 canonical 三层 hash，要求真实、独立、空的 `AuditLogger(JsonlSink)`，写入完整 L1 事件后直接回读原始 JSONL，并验证事件全字段与链 `ok=True,total=1` 后才返回成功结果。

**Tech Stack：** Python 3、现有平台 `Supplier`、`AuditLogger`、`AuditEvent`、`JsonlSink`、pytest、标准库 `dataclasses/json/hashlib/math/uuid`。

**Spec inputs：**

1. `openspec/changes/sc7-batch-quantity-mapping/design.md`
2. `openspec/changes/sc7-batch-quantity-mapping/specs/sc7-batch-quantity-evidence/spec.md`
3. `openspec/changes/sc7-batch-quantity-mapping/proposal.md`
4. `openspec/changes/sc7-batch-quantity-mapping/tasks.md`

已批准 design 源字节 SHA256：`921FC0E4B60E50D44F51B452E87A29DAB80058DA7B077AD56DFC319A2977118A`。本次只读所得 companion SHA256：spec `5383F3583567BDA7A7B87EA2B116D424FD7807E18857F2BA0C9024C54F2EE725`；proposal `4C55B1AB683BEBD9438E7186029CDF47BF031FB8AE732B3183600D64F90374F5`；tasks `B26055A4F8BC82F83F63128D2DAB84448A55F7ED24A03A23D96BC5A6BA9AF129`。实施者必须在隔离 checkout 的只读执行输入目录核对四份文档的 SHA；源缺失/哈希不符即停止。不得默认依赖 Native 主仓未提交文件，也不得自行复制或改写 design。由 root 以受控方式将已批准输入传到新 checkout ignored `reports/sc7-batch-quantity-1010/design-input/` 并记录源/目标 SHA；产品源码只能在 checkout 中改。

## 隔离 Native 与批准边界

批准请求绑定的新 Native 起点为已观察的 committed HEAD `310f54de71149b0cb0281749619ee3cd84f97bca`；创建时显式传此 ref，返回的实际路径必须位于 `C:/Users/Paul Shao/.codex/worktrees/` 下并记录到本次消费件。主仓历史其它 dirty 保留；不得带入主仓未提交产品差异。四份已批准文档按本计划走 ignored 受控输入运输。

1. 实施方式为新隔离 Native checkout，不在 `C:\Dev\zhuopin-ai` 主仓工作树中实施。此刻不创建 checkout；只有本计划和白名单获 Shao Peishen 明确批准后，root 才通过 Codex Native worktree 能力创建 checkout，并把工具返回的真实绝对路径写入证据。若 Native 返回路径、checkout 类型或源 HEAD 不符正式批准绑定，立即停止；不得臆造路径、ref 或基线。
2. 工作开始时对 checkout 和源 design-input 双重绑定：`git rev-parse --show-toplevel` 等于工具返回 checkout 路径；记录 `git rev-parse HEAD`、branch/ref、`git status --porcelain=v1 -z`；四份源文档 SHA 与上方批准值完全相同。记录来源主仓 HEAD 和 Native checkout HEAD 的差异，不做 rebase/ff/同步。若已批准 design/spec 未包含于选定 HEAD，由 root 受控搬运批准文档到 ignored design-input；不复制其他主仓源代码、测试或用户工作树差异。
3. 实施白名单严格为新隔离 checkout 内两个产品文件：
   1. 新增 `4-数字员工/采购部/SC7-库存优化建议/sc7_inventory/batch_quantity.py`。
   2. 新增 `4-数字员工/采购部/SC7-库存优化建议/tests/test_batch_quantity.py`。
4. 执行前核两目标在 checkout 中不存在且无其他工作者修改；若任一已存在/dirty，保留原状并停止。执行后目标产品 status 只能含上述两条新增路径。禁止修改模型、`__init__.py`、conftest、共享 connector、`get_suppliers()`、`run_sc7()`、采购引擎/规则、K2、其它 tests、依赖、正式文档或队列。
5. 不取真实 ItemMaster/SRM/ERP 数据或 schema，不做 API、权限、组织、单位、缺值、重复行判定；mapping 无法识别压缩前折叠的 raw duplicate，未来 raw adapter 必须另行设计并在映射前校验冲突重复。所有证据标 `source_kind="synthetic_normalized"`；不得宣称生产准备、采购建议批准、R1/R2、L2 或专业签认。K2 不运行，`lead_time_days=30` 不变。
6. 本计划不授权 commit、`git add`、分支发布、rebase、fast-forward、push、PR、删除或清理。Native worktree 创建会新增本地 Git worktree 元数据/checkout ref，必须由 Shao Peishen 在批准此计划时明确接受；代码实施在该 Native checkout 形成未提交文件。没有任何主仓产品写入。整合和提交另需单独授权。

## Global Constraints

1. `purchaseBatchQty` 是料品级 MOQ 与 MPQ 同值，沿用既有补货算法；不新增采购规则。
2. Mapping key 是非空白 `str`；带首尾空格但非空白的 ID 原样比较、原样快照。value 必须 `type(q) is int and q > 0`；拒绝 bool、float、str、None、0、负数，不 round、不换算、不补 1。
3. mapping key 集合与 Supplier 唯一 material ID 集合完全相等；同料多供应商合法且各记录共用数量；输出顺序/条数保留。
4. 使用新 `Supplier` 副本，只改 `moq`/`mpq`；输入序列及原 Supplier 不变。价格、旧交期和审批状态不增加业务判定。
5. Supplier 当前七字段严格快照：`supplier_id:str`、`material_id:非空白str`、`unit_price:有限内置int或float且非bool`、`moq/mpq/lead_time_days:内置int且非bool`、`is_approved:内置bool`。不转换值；拒绝 Decimal、任意对象、嵌套容器、NaN/Infinity、类型漂移。Supplier 字段名集合变化时 fail closed。
6. Canonical JSON：UTF-8、`sort_keys=True`、`separators=(",", ":")`、`ensure_ascii=False`、`allow_nan=False`；SHA-256 对该 UTF-8 字节计算。按 design 计算 input/result/audit hashes；audit 前像含 evaluator，不含自身 hash、UUID、timestamp、平台 `prev_hash`。
7. Evidence 成功要求当前平台真实 `AuditLogger` 且 sink 是 `JsonlSink`、sink 目标独立空 JSONL、链起始 `ok=True,total=0`。写入后直接解析原始文件：恰一条合法事件、无空/坏/重复额外行；完整核对事件身份和负载，再核 `verify_chain().ok=True,total=1`。`read_all()` 忽略坏 JSON，不作为唯一验收。
8. 对已安全识别的合同错误尽力写一条最小失败事件；仅记录固定错误码、来源标签和有效 synthetic evaluator，不记录原始异常、无效值、对象 repr 或不可信 raw payload。失败审计无法安全序列化、写入或验链时保留并重抛原合同错误；从不返回成功证据。

## Review Focus

1. Python 的 bool 是 int 子类，需拒绝 `True`/`False` 批量值和 Supplier 数值误类型；唯一测试文件固定每个字段及所有无效数量类型。
2. `strip()` 可能意外改写料号；测试全空白拒绝、首尾空格保留、mapping keys 精确一致与同料多 Supplier。
3. 序列化可能丢字段/改类型；测试完整七字段、输入输出顺序、int price JSON 数字类型、有限浮点和不修改旧 Supplier。
4. evaluator 或 event UUID/timestamp/prev_hash 可能进错摘要；测试 evaluator 变化只影响 audit 内容 hash，event identity 与字节链另行核验。
5. `AuditLogger.read_all()` 会跳过坏行；测试 real JsonlSink 唯一原始行、空/已有/损坏/重复/字段篡改/写失败/链失败、错误 sink 以及安全失败审计失败不掩盖原始错误。

## Files and Interfaces

1. 唯一产品模块定义 `BatchQuantityContractError(ValueError)`（带固定 `code`，错误文本不嵌入不可信值）、`BatchQuantityPersistenceError(RuntimeError)`、frozen `BatchQuantityEvidence`，以及下列接口：

   `apply_purchase_batch_qty(suppliers: Sequence[Supplier], batch_by_material: Mapping[str, int]) -> list[Supplier]`

   `run_synthetic_batch_evidence(suppliers: Sequence[Supplier], batch_by_material: Mapping[str, int], *, fixture_id: str, revision: str, evaluator: str, audit: AuditLogger) -> BatchQuantityEvidence`

2. `BatchQuantityEvidence` 字段：`suppliers` 为新建 Supplier 对象组成的 tuple（tuple 容器不能改长度，但 Supplier 本身仍是可变 dataclass；不宣称深不可变）；内部 envelope 以 canonical JSON string 保存，`envelope` 属性每次 `json.loads` 返回新的 dict 副本；另含 `evidence_id`、`input_hash`、`result_hash`、`audit_content_hash` 字符串。
3. 不改 SC7 package `__init__.py`。导入 `Supplier` 自 `zhuopin_platform.shared_tools.models`，审计类型自 `zhuopin_platform.audit`。测试使用现有 `tests/conftest.py` 的 `ensure_paths(__file__, SC7_PROJECT_ROOT, strict=True)` 引导，不造 sys.path workaround。
4. 完整 evidence envelope 字段：`evidence_contract`、`fixture_id`、`revision`、`source_kind`、`evaluator`、`suppliers_input`、按物料 key 排序的 `batch_by_material`、`suppliers_output`、`input_hash`、`result_hash`、`audit_content_hash`。每 Supplier snapshot 显式含当前七字段。
5. hash 前像固定：
   1. `input_hash = SHA256(canonical_json({meta, suppliers_input, batch_by_material}))`，其中 `meta={evidence_contract,fixture_id,revision,source_kind}`。
   2. `result_hash = SHA256(canonical_json({meta,input_hash,suppliers_output}))`。
   3. `audit_body={meta,evaluator,suppliers_input,batch_by_material,suppliers_output,input_hash,result_hash}`；`audit_content_hash=SHA256(canonical_json(audit_body))`。把 evaluator 放进 envelope 便于核对，但它按批准 design 仅进入第三层摘要，不进入前两层。
6. 成功 event：`AuditEvent(scenario="SC7", action="synthetic_batch_quantity_evidence", evaluator=evaluator, automation_level="L1", decision={"evidence_id": evidence_id, "evidence": envelope}, data_sources={"source_kind":"synthetic_normalized","fixture_id":fixture_id,"revision":revision}, content_hash=audit_content_hash)`。生成 envelope/evidence_id 后 event 中的完整 envelope 必须和函数返回值一致。

## Execution plan — 批准后执行

本计划使用 Native 隔离 checkout。root 完成 worktree 创建和受控 design/spec transport 后，返回 checkout 真实路径；执行者把此路径放入 `$WorktreeRoot`，不得写死或猜测 worktree 名称。

1. **创建审阅完整测试文件并确认 RED。** 只新建白名单 `tests/test_batch_quantity.py`，使用附录的完整测试代码。切换当前目录到 `$Sc7Root`，运行附录唯一 pytest 命令，预期因尚无 `batch_quantity.py` 导入而非零；记录原始 stdout/stderr/exit/JUnit。不得将此预期 RED 误报为通过。
2. **新增唯一产品模块。** 按附录完整代码新增 `sc7_inventory/batch_quantity.py`。不改测试/代码范围外文件。
3. **运行 GREEN 与验收。** 仍从 `$Sc7Root` 只运行 `tests/test_batch_quantity.py`，要求所有合同/evidence/sink/failure 用例通过；核 JUnit 统计和 shell exit 一致。
4. **只读审查与留证。** 在 worktree 路径上复核 diff、路径集合与 source SHA；确认只有 2 项产品文件，证据目录属 ignored。保留当前 worktree HEAD/ref 和 after-status，不 commit。

### pytest 命令及运行边界

从目标子项目目录执行测试，不从 repo root 指定跨项目路径：

```powershell
$Sc7Root = Join-Path $WorktreeRoot '4-数字员工/采购部/SC7-库存优化建议'
$EvidenceDir = $MainEvidenceDir
$RuntimeConfig = if ($env:ZHUOPIN_CODEX_RUNTIME) { $env:ZHUOPIN_CODEX_RUNTIME } else { Join-Path $WorktreeRoot '.codex/runtime.local.json' }
if (-not (Test-Path -LiteralPath $RuntimeConfig)) {
    $CommonGitDir = & git --no-pager -c "safe.directory=$($WorktreeRoot.Replace('\','/'))" -C $WorktreeRoot rev-parse --git-common-dir
    if ($LASTEXITCODE -ne 0) { throw '不能解析隔离 checkout 的共享 Git runtime 路径' }
    $CommonPath = if ([IO.Path]::IsPathRooted($CommonGitDir)) { $CommonGitDir } else { Join-Path $WorktreeRoot $CommonGitDir }
    $RuntimeConfig = Join-Path (Split-Path ([IO.Path]::GetFullPath($CommonPath)) -Parent) '.codex/runtime.local.json'
}
if (-not (Test-Path -LiteralPath $RuntimeConfig)) { throw "缺少本机隔离 runtime 配置：$RuntimeConfig" }
$Runtime = Get-Content -LiteralPath $RuntimeConfig -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not (Test-Path -LiteralPath $Runtime.python)) { throw '隔离 runtime 的 Python 不存在' }
Push-Location $Sc7Root
$Phase = 'RED' # GREEN 重跑同一命令块前只改为 'GREEN'
$RunId = [guid]::NewGuid().ToString()
$BaseTemp = Join-Path $EvidenceDir "pytest-tmp/$RunId"
$Junit = Join-Path $EvidenceDir "pytest-$RunId.xml"
$Stdout = Join-Path $EvidenceDir "pytest-$RunId.stdout.txt"
$Stderr = Join-Path $EvidenceDir "pytest-$RunId.stderr.txt"
& $Runtime.python -B -m pytest -p no:cacheprovider 'tests/test_batch_quantity.py' -q --basetemp $BaseTemp --junitxml $Junit 1> $Stdout 2> $Stderr
$ActualExit = $LASTEXITCODE
Set-Content -LiteralPath (Join-Path $EvidenceDir "pytest-$RunId.exit.txt") -Value $ActualExit -NoNewline
Pop-Location
if ($Phase -eq 'RED' -and $ActualExit -eq 0) { throw 'RED 阶段意外通过；停止并复核测试/实现状态' }
if ($Phase -eq 'GREEN' -and $ActualExit -ne 0) { throw "SC7 targeted GREEN failed with exit $ActualExit" }
```

RED 与 GREEN 使用同一命令块和同一目标参数；仅将 `$Phase` 设为相应阶段并为每次运行生成新 UUID basetemp/JUnit/log 文件。RED 预期非零，GREEN 必须零；分别按阶段核对实际 exit，不能把 RED 的预期失败当成 GREEN 失败。`-B` 禁止 Python bytecode，`-p no:cacheprovider` 禁止 pytest 写 `.pytest_cache`；测试的临时 JSONL 与 `.lock` 在独立 basetemp 中。不复用、不手动删除目录。

## Native / Git / 主仓 UUID 证据与副作用

1. root 创建独立 Native worktree 会新增 checkout 和共享 Git worktree 元数据/ref；执行前须先由 Shao Peishen 批准此具体副作用。工具返回的 checkout 真实路径、起始 HEAD/ref、创建时间、正式 plan SHA 和完整 design SHA写入审计 manifest。
2. worktree 内只新增两项产品文件；测试只在独立 pytest UUID basetemp 写临时 JSONL/JUnit/stdout/stderr。主仓 `C:\Dev\zhuopin-ai` 产品树不实施；root 会在主仓 `reports/sc7-batch-quantity-1010/evidence/<UUID>/` 创建另一个 UUID evidence folder，保存 worktree manifest、design/spec source/target SHA、Git identity/status、受控测试原始结果哈希和静态 diff review。该目录必须是 ignored。
3. 主仓 UUID evidence 的具体创建命令（仅 root 在获批后执行）：

   ```powershell
   $MainEvidenceId = [guid]::NewGuid().ToString()
   $MainEvidenceDir = Join-Path 'C:\Dev\zhuopin-ai\reports\sc7-batch-quantity-1010\evidence' $MainEvidenceId
   New-Item -ItemType Directory -Path $MainEvidenceDir -ErrorAction Stop | Out-Null
   ```

   该目录只收证据和受控 design-input 副本，不落产品文件。每个 test run 再用新的 `$RunId` 创建 worktree 自己的 pytest basetemp/JUnit/log，路径在主仓 UUID evidence 目录下由 root 定义的共享 evidence destination；不可因为 worktree 的 `reports/` 是 ignored 就留在错误 checkout 的非正式目录。
4. 具体 checkout 尚未创建，因此所有命令只接受由 Native 工具返回的 `$WorktreeRoot`，不包含猜测路径。完成 checkout 后先保存这些只读 identity 命令结果：

   ```powershell
   git -C $WorktreeRoot rev-parse --show-toplevel
   git -C $WorktreeRoot rev-parse HEAD
   git -C $WorktreeRoot symbolic-ref --short HEAD
   git -C $WorktreeRoot status --porcelain=v1 -z
   Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $WorktreeRoot 'openspec/changes/sc7-batch-quantity-mapping/design.md')
   Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $WorktreeRoot 'openspec/changes/sc7-batch-quantity-mapping/specs/sc7-batch-quantity-evidence/spec.md')
   ```

   如 source docs 由 root 以受控副本放进 ignored `design-input`，则同时对主仓原文件与 worktree 副本运行 `Get-FileHash` 并绑定批准值；不将它们加到产品文件白名单。
5. 最终只读核验在 `$WorktreeRoot`：

   ```powershell
   git -C $WorktreeRoot status --short -- '4-数字员工/采购部/SC7-库存优化建议/sc7_inventory/batch_quantity.py' '4-数字员工/采购部/SC7-库存优化建议/tests/test_batch_quantity.py'
   git -C $WorktreeRoot diff --check
   Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $WorktreeRoot '4-数字员工/采购部/SC7-库存优化建议/sc7_inventory/batch_quantity.py')
   Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $WorktreeRoot '4-数字员工/采购部/SC7-库存优化建议/tests/test_batch_quantity.py')
   git -C 'C:\Dev\zhuopin-ai' status --short -- '4-数字员工/采购部/SC7-库存优化建议/sc7_inventory/batch_quantity.py' '4-数字员工/采购部/SC7-库存优化建议/tests/test_batch_quantity.py'
   ```

   新文件的 `git diff --check` 未跟踪前不显示内容；实际 whitespace review 必须查看两个新文件文本并由完整测试输出作证，不能把空 diff 当成无错误。主仓最后两条产品路径仍应未改。
6. 除 Native worktree 本身、两项白名单产品文件、ignored design-input copy、pytest UUID basetemp/JUnit/log 和主仓 ignored UUID evidence 外，不应有任何文件/refs/index 变化。无 add/commit/rebase/ff/push/network/cleanup。若工具在 checkout 后产生意外内容，保留状态并报告，不删除。

## Approval gate

请 Shao Peishen 审阅并明确批准：

1. 新建 Native 隔离 worktree及其本地 Git 元数据/ref 副作用，源 HEAD 由 root 在具体批准请求中绑定。
2. 仅上述两个产品文件的代码实施与唯一 SC7 定向测试。
3. 主仓 ignored UUID evidence 与 worktree ignored design-input transport 的路径和证据副作用。
4. 本文附录代码/测试合同。任何代码/测试/执行路径变化须返回重新审阅，不自动扩张白名单。

design 已批 SHA 不替代上述具体计划批准。审批前不得建 worktree、复制设计、建产品文件、运行测试或创建 evidence UUID 目录。

## Appendix A — 完整候选 `batch_quantity.py`

以下为拟实施完整模块文本；只在批准后写入白名单模块。

```python
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, replace
import hashlib
import json
import math
from pathlib import Path
import uuid
from typing import Any

from zhuopin_platform.audit import AuditEvent, AuditLogger, JsonlSink
from zhuopin_platform.shared_tools.models import Supplier


EVIDENCE_CONTRACT = "sc7-batch-quantity-evidence-v1"
SOURCE_KIND = "synthetic_normalized"
SUPPLIER_FIELDS = (
    "supplier_id",
    "material_id",
    "unit_price",
    "moq",
    "mpq",
    "lead_time_days",
    "is_approved",
)


class BatchQuantityContractError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class BatchQuantityPersistenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class BatchQuantityEvidence:
    suppliers: tuple[Supplier, ...]
    _envelope_json: str
    evidence_id: str
    input_hash: str
    result_hash: str
    audit_content_hash: str

    @property
    def envelope(self) -> dict[str, Any]:
        return json.loads(self._envelope_json)


def _canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, OverflowError):
        raise BatchQuantityContractError("snapshot_not_json_safe") from None


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _supplier_snapshot(row: Supplier) -> dict[str, Any]:
    if type(row) is not Supplier:
        raise BatchQuantityContractError("supplier_type_invalid")
    declared = tuple(item.name for item in fields(Supplier))
    if set(declared) != set(SUPPLIER_FIELDS) or set(vars(row)) != set(SUPPLIER_FIELDS):
        raise BatchQuantityContractError("supplier_schema_changed")
    if type(row.supplier_id) is not str:
        raise BatchQuantityContractError("supplier_id_type_invalid")
    if type(row.material_id) is not str or not row.material_id.strip():
        raise BatchQuantityContractError("material_id_invalid")
    if type(row.unit_price) not in (int, float):
        raise BatchQuantityContractError("unit_price_type_invalid")
    if type(row.unit_price) is float and not math.isfinite(row.unit_price):
        raise BatchQuantityContractError("unit_price_not_finite")
    for name in ("moq", "mpq", "lead_time_days"):
        if type(getattr(row, name)) is not int:
            raise BatchQuantityContractError("supplier_integer_field_invalid")
    if type(row.is_approved) is not bool:
        raise BatchQuantityContractError("is_approved_type_invalid")
    return {name: getattr(row, name) for name in SUPPLIER_FIELDS}


def _supplier_rows(suppliers: Sequence[Supplier]) -> tuple[tuple[Supplier, ...], list[dict[str, Any]]]:
    if isinstance(suppliers, (str, bytes, bytearray)) or not isinstance(suppliers, Sequence):
        raise BatchQuantityContractError("supplier_sequence_invalid")
    rows = tuple(suppliers)
    snapshots = [_supplier_snapshot(row) for row in rows]
    return rows, snapshots


def _batch_map(batch_by_material: Mapping[str, int], material_ids: set[str]) -> dict[str, int]:
    if not isinstance(batch_by_material, Mapping):
        raise BatchQuantityContractError("mapping_type_invalid")
    try:
        pairs = list(batch_by_material.items())
    except Exception:
        raise BatchQuantityContractError("mapping_unreadable") from None
    normalized: dict[str, int] = {}
    for key, quantity in pairs:
        if type(key) is not str or not key.strip():
            raise BatchQuantityContractError("mapping_key_invalid")
        if type(quantity) is not int or quantity <= 0:
            raise BatchQuantityContractError("batch_quantity_invalid")
        if key in normalized:
            raise BatchQuantityContractError("mapping_duplicate_key")
        normalized[key] = quantity
    if set(normalized) != material_ids:
        raise BatchQuantityContractError("mapping_key_set_mismatch")
    return {key: normalized[key] for key in sorted(normalized)}


def apply_purchase_batch_qty(
    suppliers: Sequence[Supplier],
    batch_by_material: Mapping[str, int],
) -> list[Supplier]:
    rows, snapshots = _supplier_rows(suppliers)
    material_ids = {snapshot["material_id"] for snapshot in snapshots}
    batch = _batch_map(batch_by_material, material_ids)
    _canonical_json({"suppliers_input": snapshots, "batch_by_material": batch})
    return [replace(row, moq=batch[row.material_id], mpq=batch[row.material_id]) for row in rows]


def _safe_label(value: object) -> str | None:
    if type(value) is str and value.strip():
        return value
    return None


def _empty_jsonl_sink(audit: object) -> tuple[AuditLogger, JsonlSink, Path]:
    if not isinstance(audit, AuditLogger) or not isinstance(audit.sink, JsonlSink):
        raise BatchQuantityPersistenceError("audit_sink_type_invalid")
    sink = audit.sink
    path = sink.log_path
    if path.is_symlink():
        raise BatchQuantityPersistenceError("audit_target_symlink")
    if path.exists() and (not path.is_file() or path.read_bytes()):
        raise BatchQuantityPersistenceError("audit_target_not_empty_regular_file")
    chain = audit.verify_chain()
    if chain.ok is not True or chain.total != 0:
        raise BatchQuantityPersistenceError("audit_target_chain_not_empty")
    return audit, sink, path


def _verify_single_event(audit: AuditLogger, path: Path, expected: dict[str, Any]) -> None:
    try:
        raw = path.read_bytes()
        if not raw.endswith(b"\n"):
            raise BatchQuantityPersistenceError("audit_jsonl_missing_final_newline")
        lines = raw.splitlines()
        if len(lines) != 1 or not lines[0].strip():
            raise BatchQuantityPersistenceError("audit_jsonl_record_count_mismatch")
        record = json.loads(lines[0].decode("utf-8"))
        if type(record) is not dict:
            raise BatchQuantityPersistenceError("audit_jsonl_record_not_object")
        if set(record) != set(expected) | {"prev_hash"}:
            raise BatchQuantityPersistenceError("audit_jsonl_fields_mismatch")
        if any(record.get(key) != value for key, value in expected.items()):
            raise BatchQuantityPersistenceError("audit_jsonl_event_mismatch")
        if record.get("prev_hash") != "":
            raise BatchQuantityPersistenceError("audit_jsonl_genesis_mismatch")
        chain = audit.verify_chain()
        if chain.ok is not True or chain.total != 1:
            raise BatchQuantityPersistenceError("audit_chain_verification_failed")
    except BatchQuantityPersistenceError:
        raise
    except Exception:
        raise BatchQuantityPersistenceError("audit_jsonl_readback_failed") from None


def _append_failure_event_best_effort(
    audit: object,
    *,
    fixture_id: object,
    revision: object,
    evaluator: object,
    error_code: str,
) -> None:
    try:
        valid_audit, _, path = _empty_jsonl_sink(audit)
        safe_fixture = _safe_label(fixture_id)
        safe_revision = _safe_label(revision)
        safe_evaluator = evaluator if type(evaluator) is str and evaluator.startswith("synthetic:") and evaluator[len("synthetic:"):].strip() else "synthetic:unidentified"
        decision = {"status": "rejected", "error_code": error_code, "source_kind": SOURCE_KIND}
        sources = {"source_kind": SOURCE_KIND}
        if safe_fixture is not None:
            sources["fixture_id"] = safe_fixture
        if safe_revision is not None:
            sources["revision"] = safe_revision
        body = {"scenario": "SC7", "action": "synthetic_batch_quantity_evidence_rejected", "evaluator": safe_evaluator, "decision": decision, "data_sources": sources}
        event = AuditEvent(
            scenario="SC7",
            action="synthetic_batch_quantity_evidence_rejected",
            evaluator=safe_evaluator,
            automation_level="L1",
            decision=decision,
            data_sources=sources,
            content_hash=_sha256(_canonical_json(body)),
        )
        expected_record = event.to_dict()
        valid_audit.record(event)
        _verify_single_event(valid_audit, path, expected_record)
    except Exception:
        # A best-effort failure audit must never replace the original contract error.
        return


def _validated_tags(fixture_id: str, revision: str, evaluator: str) -> None:
    if type(fixture_id) is not str or not fixture_id.strip():
        raise BatchQuantityContractError("fixture_id_invalid")
    if type(revision) is not str or not revision.strip():
        raise BatchQuantityContractError("revision_invalid")
    if type(evaluator) is not str or not evaluator.startswith("synthetic:") or not evaluator[len("synthetic:"):].strip():
        raise BatchQuantityContractError("evaluator_invalid")


def run_synthetic_batch_evidence(
    suppliers: Sequence[Supplier],
    batch_by_material: Mapping[str, int],
    *,
    fixture_id: str,
    revision: str,
    evaluator: str,
    audit: AuditLogger,
) -> BatchQuantityEvidence:
    try:
        _validated_tags(fixture_id, revision, evaluator)
        rows, input_snapshot = _supplier_rows(suppliers)
        material_ids = {row["material_id"] for row in input_snapshot}
        batch = _batch_map(batch_by_material, material_ids)
        output_rows = tuple(replace(row, moq=batch[row.material_id], mpq=batch[row.material_id]) for row in rows)
        output_snapshot = [_supplier_snapshot(row) for row in output_rows]
        meta = {
            "evidence_contract": EVIDENCE_CONTRACT,
            "fixture_id": fixture_id,
            "revision": revision,
            "source_kind": SOURCE_KIND,
        }
        input_hash = _sha256(_canonical_json({
            **meta,
            "suppliers_input": input_snapshot,
            "batch_by_material": batch,
        }))
        result_hash = _sha256(_canonical_json({
            **meta,
            "input_hash": input_hash,
            "suppliers_output": output_snapshot,
        }))
        audit_body = {
            **meta,
            "evaluator": evaluator,
            "suppliers_input": input_snapshot,
            "batch_by_material": batch,
            "suppliers_output": output_snapshot,
            "input_hash": input_hash,
            "result_hash": result_hash,
        }
        audit_content_hash = _sha256(_canonical_json(audit_body))
        evidence_id = str(uuid.uuid4())
        envelope = {
            **meta,
            "evaluator": evaluator,
            "suppliers_input": input_snapshot,
            "batch_by_material": batch,
            "suppliers_output": output_snapshot,
            "input_hash": input_hash,
            "result_hash": result_hash,
            "audit_content_hash": audit_content_hash,
        }
        envelope_json = _canonical_json(envelope).decode("utf-8")
    except BatchQuantityContractError as exc:
        _append_failure_event_best_effort(
            audit,
            fixture_id=fixture_id,
            revision=revision,
            evaluator=evaluator,
            error_code=exc.code,
        )
        raise
    except Exception:
        error = BatchQuantityContractError("input_contract_unreadable")
        _append_failure_event_best_effort(
            audit,
            fixture_id=fixture_id,
            revision=revision,
            evaluator=evaluator,
            error_code=error.code,
        )
        raise error from None

    try:
        valid_audit, _, path = _empty_jsonl_sink(audit)
        event = AuditEvent(
            scenario="SC7",
            action="synthetic_batch_quantity_evidence",
            evaluator=evaluator,
            automation_level="L1",
            decision={"evidence_id": evidence_id, "evidence": json.loads(envelope_json)},
            data_sources={
                "source_kind": SOURCE_KIND,
                "fixture_id": fixture_id,
                "revision": revision,
            },
            content_hash=audit_content_hash,
        )
        expected_record = event.to_dict()
        valid_audit.record(event)
        _verify_single_event(valid_audit, path, expected_record)
    except BatchQuantityPersistenceError:
        raise
    except Exception:
        raise BatchQuantityPersistenceError("audit_persistence_failed") from None

    return BatchQuantityEvidence(
        suppliers=output_rows,
        _envelope_json=envelope_json,
        evidence_id=evidence_id,
        input_hash=input_hash,
        result_hash=result_hash,
        audit_content_hash=audit_content_hash,
    )
```

## Appendix B — 完整候选 `tests/test_batch_quantity.py`

以下测试文本只在计划获批后写入上述唯一测试文件。运行路径是 SC7 子项目本地目录，target 为 `tests/test_batch_quantity.py`。

```python
from __future__ import annotations

from dataclasses import asdict, replace
from decimal import Decimal
import hashlib
import json

import pytest

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.audit.sinks import ChainVerifyResult, JsonlSink
from zhuopin_platform.shared_tools.models import Supplier
from sc7_inventory.batch_quantity import (
    BatchQuantityContractError,
    BatchQuantityPersistenceError,
    apply_purchase_batch_qty,
    run_synthetic_batch_evidence,
)


def row(supplier_id="S1", material_id="M1", unit_price=2.5, moq=1, mpq=1, lead_time_days=30, is_approved=True):
    return Supplier(supplier_id, material_id, unit_price, moq, mpq, lead_time_days, is_approved)


def call_evidence(tmp_path, suppliers=None, mapping=None, *, evaluator="synthetic:test", fixture_id="fixture-1", revision="r1", audit=None):
    rows = [row()] if suppliers is None else suppliers
    batches = {"M1": 4} if mapping is None else mapping
    sink_logger = AuditLogger.jsonl(tmp_path / "event.jsonl") if audit is None else audit
    return run_synthetic_batch_evidence(
        rows, batches, fixture_id=fixture_id, revision=revision, evaluator=evaluator, audit=sink_logger
    )


class MemorySink:
    def write(self, event):
        self.event = event

    def read_all(self):
        return []


def test_maps_each_material_to_new_supplier_copies_without_mutating_inputs():
    rows = [
        row("S2", " A ", 2, 1, 1, 30, True),
        row("S1", " A ", 3, 4, 5, -2, False),
        row("S3", "B", 4, 7, 8, 30, True),
    ]
    before = [asdict(item) for item in rows]
    result = apply_purchase_batch_qty(rows, {" A ": 6, "B": 9})
    assert [(item.supplier_id, item.material_id, item.moq, item.mpq) for item in result] == [
        ("S2", " A ", 6, 6), ("S1", " A ", 6, 6), ("S3", "B", 9, 9)
    ]
    assert len(result) == len(rows)
    assert all(new is not old for new, old in zip(result, rows))
    for index, item in enumerate(result):
        after = asdict(item)
        after["moq"] = before[index]["moq"]
        after["mpq"] = before[index]["mpq"]
        assert after == before[index]
    assert [asdict(item) for item in rows] == before


@pytest.mark.parametrize("mapping", [{}, {"M1": 2, "EXTRA": 3}])
def test_rejects_missing_or_extra_material_key(mapping):
    with pytest.raises(BatchQuantityContractError):
        apply_purchase_batch_qty([row()], mapping)


@pytest.mark.parametrize("bad_mapping", [None, [], "M1", 7])
def test_rejects_non_mapping_input(bad_mapping):
    with pytest.raises(BatchQuantityContractError):
        apply_purchase_batch_qty([row()], bad_mapping)


@pytest.mark.parametrize("bad_key", [None, 7, "", "   "])
def test_rejects_invalid_mapping_key(bad_key):
    with pytest.raises(BatchQuantityContractError):
        apply_purchase_batch_qty([row()], {bad_key: 2})


@pytest.mark.parametrize("bad_quantity", [True, False, 1.0, "1", None, 0, -1])
def test_rejects_non_strict_positive_integer_quantity(bad_quantity):
    with pytest.raises(BatchQuantityContractError):
        apply_purchase_batch_qty([row()], {"M1": bad_quantity})


@pytest.mark.parametrize("bad_id", [None, 1, "", "   "])
def test_rejects_invalid_supplier_material_id(bad_id):
    with pytest.raises(BatchQuantityContractError):
        apply_purchase_batch_qty([row(material_id=bad_id)], {bad_id: 2})


def test_rejects_wrong_supplier_type_and_sequence_type():
    with pytest.raises(BatchQuantityContractError):
        apply_purchase_batch_qty([object()], {"M1": 2})
    with pytest.raises(BatchQuantityContractError):
        apply_purchase_batch_qty("not rows", {"M1": 2})


@pytest.mark.parametrize("field,value", [
    ("supplier_id", None),
    ("material_id", 8),
    ("unit_price", True),
    ("unit_price", Decimal("1.25")),
    ("unit_price", float("nan")),
    ("unit_price", float("inf")),
    ("moq", True),
    ("mpq", 2.0),
    ("lead_time_days", False),
    ("is_approved", 1),
])
def test_rejects_supplier_snapshot_type_drift(field, value):
    with pytest.raises(BatchQuantityContractError):
        apply_purchase_batch_qty([replace(row(), **{field: value})], {"M1": 2})


def test_rejects_supplier_dynamic_extra_field():
    item = row()
    item.extra = {"unsafe": "nested"}
    with pytest.raises(BatchQuantityContractError):
        apply_purchase_batch_qty([item], {"M1": 2})


def test_rejects_non_utf8_surrogate_in_snapshot_text():
    with pytest.raises(BatchQuantityContractError):
        apply_purchase_batch_qty([row(supplier_id="\ud800")], {"M1": 2})


def test_evidence_has_complete_seven_field_snapshots_and_valid_hashes(tmp_path):
    source = row(unit_price=1, lead_time_days=-3, is_approved=False)
    evidence = call_evidence(tmp_path, [source])
    envelope = evidence.envelope
    assert envelope["evidence_contract"] == "sc7-batch-quantity-evidence-v1"
    assert envelope["source_kind"] == "synthetic_normalized"
    assert envelope["evaluator"] == "synthetic:test"
    assert set(envelope["suppliers_input"][0]) == {
        "supplier_id", "material_id", "unit_price", "moq", "mpq", "lead_time_days", "is_approved"
    }
    assert type(envelope["suppliers_input"][0]["unit_price"]) is int
    assert envelope["suppliers_input"][0]["lead_time_days"] == -3
    assert envelope["suppliers_input"][0]["is_approved"] is False
    assert evidence.suppliers[0].moq == evidence.suppliers[0].mpq == 4
    assert source.moq == source.mpq == 1
    assert len(evidence.input_hash) == len(evidence.result_hash) == len(evidence.audit_content_hash) == 64


def test_hashes_match_independently_built_canonical_preimages(tmp_path):
    source = row("S1", "M1", 2.5, 1, 1, 30, True)
    evidence = call_evidence(tmp_path, [source], {"M1": 4}, evaluator="synthetic:hash-check")
    envelope = evidence.envelope
    meta = {
        "evidence_contract": "sc7-batch-quantity-evidence-v1",
        "fixture_id": "fixture-1",
        "revision": "r1",
        "source_kind": "synthetic_normalized",
    }
    fields = ("supplier_id", "material_id", "unit_price", "moq", "mpq", "lead_time_days", "is_approved")
    independent_input = [{field: getattr(source, field) for field in fields}]
    independent_output = [{**independent_input[0], "moq": 4, "mpq": 4}]
    independent_mapping = {"M1": 4}

    def independent_sha256(value):
        payload = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    expected_input_hash = independent_sha256({
        **meta, "suppliers_input": independent_input, "batch_by_material": independent_mapping,
    })
    expected_result_hash = independent_sha256({
        **meta, "input_hash": expected_input_hash, "suppliers_output": independent_output,
    })
    expected_audit_hash = independent_sha256({
        **meta,
        "evaluator": "synthetic:hash-check",
        "suppliers_input": independent_input,
        "batch_by_material": independent_mapping,
        "suppliers_output": independent_output,
        "input_hash": expected_input_hash,
        "result_hash": expected_result_hash,
    })
    assert envelope["suppliers_input"] == independent_input
    assert envelope["suppliers_output"] == independent_output
    assert envelope["batch_by_material"] == independent_mapping
    assert evidence.input_hash == envelope["input_hash"] == expected_input_hash
    assert evidence.result_hash == envelope["result_hash"] == expected_result_hash
    assert evidence.audit_content_hash == envelope["audit_content_hash"] == expected_audit_hash
    assert envelope["evaluator"] == "synthetic:hash-check"


def test_hashes_are_stable_and_evaluator_is_bound_to_audit_hash(tmp_path):
    first = call_evidence(tmp_path / "one")
    second = call_evidence(tmp_path / "two")
    other_evaluator = call_evidence(tmp_path / "three", evaluator="synthetic:other")
    assert (first.input_hash, first.result_hash, first.audit_content_hash) == (
        second.input_hash, second.result_hash, second.audit_content_hash
    )
    assert first.evidence_id != second.evidence_id
    assert first.input_hash == other_evaluator.input_hash
    assert first.result_hash == other_evaluator.result_hash
    assert first.audit_content_hash != other_evaluator.audit_content_hash
    assert first.envelope["evaluator"] == "synthetic:test"
    assert other_evaluator.envelope["evaluator"] == "synthetic:other"


def test_fixture_revision_and_mapping_changes_change_content_identity(tmp_path):
    baseline = call_evidence(tmp_path / "base")
    changed_fixture = call_evidence(tmp_path / "fixture", fixture_id="fixture-2")
    changed_revision = call_evidence(tmp_path / "revision", revision="r2")
    changed_mapping = call_evidence(tmp_path / "mapping", mapping={"M1": 5})
    assert baseline.input_hash != changed_fixture.input_hash
    assert baseline.input_hash != changed_revision.input_hash
    assert baseline.input_hash != changed_mapping.input_hash
    assert baseline.result_hash != changed_fixture.result_hash
    assert baseline.result_hash != changed_revision.result_hash
    assert baseline.result_hash != changed_mapping.result_hash


def test_envelope_property_returns_a_fresh_copy(tmp_path):
    evidence = call_evidence(tmp_path)
    first = evidence.envelope
    first["suppliers_input"][0]["supplier_id"] = "tampered"
    assert evidence.envelope["suppliers_input"][0]["supplier_id"] == "S1"


def test_requires_real_jsonl_audit_logger(tmp_path):
    with pytest.raises(BatchQuantityPersistenceError):
        call_evidence(tmp_path, audit=AuditLogger(MemorySink()))


def test_rejects_nonempty_audit_target_without_appending(tmp_path):
    path = tmp_path / "used.jsonl"
    path.write_bytes(b"prior record\n")
    audit = AuditLogger.jsonl(path)
    with pytest.raises(BatchQuantityPersistenceError):
        call_evidence(tmp_path, audit=audit)
    assert path.read_bytes() == b"prior record\n"


def test_accepts_an_existing_empty_jsonl_target(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_bytes(b"")
    audit = AuditLogger.jsonl(path)
    result = call_evidence(tmp_path, audit=audit)
    assert result.evidence_id
    assert audit.verify_chain().ok is True
    assert audit.verify_chain().total == 1


def test_writes_one_complete_event_and_verifies_raw_record_and_chain(tmp_path):
    path = tmp_path / "single.jsonl"
    audit = AuditLogger.jsonl(path)
    result = call_evidence(tmp_path, audit=audit)
    raw = path.read_bytes()
    assert raw.endswith(b"\n")
    lines = raw.splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0].decode("utf-8"))
    assert record["scenario"] == "SC7"
    assert record["action"] == "synthetic_batch_quantity_evidence"
    assert record["automation_level"] == "L1"
    assert record["evaluator"] == "synthetic:test"
    assert record["decision"]["evidence_id"] == result.evidence_id
    assert record["decision"]["evidence"] == result.envelope
    assert record["data_sources"] == {
        "source_kind": "synthetic_normalized", "fixture_id": "fixture-1", "revision": "r1"
    }
    assert record["content_hash"] == result.audit_content_hash
    chain = audit.verify_chain()
    assert chain.ok is True and chain.total == 1


@pytest.mark.parametrize("fixture_id,revision,evaluator", [
    ("", "r1", "synthetic:test"),
    ("fixture", "  ", "synthetic:test"),
    ("fixture", "r1", "person"),
    ("fixture", "r1", "synthetic:   "),
])
def test_rejects_invalid_source_tags_and_best_effort_audits_safe_failure(tmp_path, fixture_id, revision, evaluator):
    path = tmp_path / "rejected.jsonl"
    audit = AuditLogger.jsonl(path)
    with pytest.raises(BatchQuantityContractError):
        call_evidence(tmp_path, fixture_id=fixture_id, revision=revision, evaluator=evaluator, audit=audit)
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(records) == 1
    assert records[0]["action"] == "synthetic_batch_quantity_evidence_rejected"
    assert records[0]["decision"]["status"] == "rejected"
    assert records[0]["decision"]["error_code"] in {
        "fixture_id_invalid", "revision_invalid", "evaluator_invalid"
    }
    assert audit.verify_chain().ok is True


def test_safe_failure_audit_never_records_invalid_quantity_payload(tmp_path):
    path = tmp_path / "safe-failure.jsonl"
    audit = AuditLogger.jsonl(path)
    with pytest.raises(BatchQuantityContractError):
        call_evidence(tmp_path, mapping={"M1": True}, audit=audit)
    raw = path.read_bytes()
    record = json.loads(raw.decode("utf-8").splitlines()[0])
    assert record["decision"]["error_code"] == "batch_quantity_invalid"
    assert "True" not in record["decision"]
    assert "batch_by_material" not in record["decision"]
    assert audit.verify_chain().ok is True


def test_unsafe_supplier_value_is_not_repr_logged_in_failure_audit(tmp_path):
    path = tmp_path / "unsafe-failure.jsonl"
    audit = AuditLogger.jsonl(path)
    unsafe = object()
    with pytest.raises(BatchQuantityContractError):
        call_evidence(tmp_path, suppliers=[row(unit_price=unsafe)], audit=audit)
    raw = path.read_bytes()
    assert b"object at" not in raw
    assert b"supplier_snapshot_type_invalid" in raw or b"unit_price_type_invalid" in raw


def test_failure_audit_write_error_preserves_original_contract_error(tmp_path, monkeypatch):
    def fail_write(self, event):
        raise OSError("synthetic sink failure")

    monkeypatch.setattr(JsonlSink, "write", fail_write)
    with pytest.raises(BatchQuantityContractError) as caught:
        call_evidence(tmp_path, mapping={"M1": False})
    assert caught.value.code == "batch_quantity_invalid"


def test_success_does_not_return_if_sink_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(AuditLogger, "record", lambda self, event: None)
    with pytest.raises(BatchQuantityPersistenceError):
        call_evidence(tmp_path)


def test_success_does_not_return_if_sink_write_raises(tmp_path, monkeypatch):
    def fail_write(self, event):
        raise OSError("synthetic sink failure")

    monkeypatch.setattr(JsonlSink, "write", fail_write)
    with pytest.raises(BatchQuantityPersistenceError):
        call_evidence(tmp_path)


def test_success_does_not_return_if_sink_writes_duplicate_records(tmp_path, monkeypatch):
    original = AuditLogger.record

    def write_twice(self, event):
        original(self, event)
        original(self, event)

    monkeypatch.setattr(AuditLogger, "record", write_twice)
    with pytest.raises(BatchQuantityPersistenceError):
        call_evidence(tmp_path)


def test_success_does_not_return_if_raw_jsonl_contains_bad_line(tmp_path, monkeypatch):
    original = AuditLogger.record

    def append_bad_line(self, event):
        original(self, event)
        self.sink.log_path.write_bytes(self.sink.log_path.read_bytes() + b"{bad json}\n")

    monkeypatch.setattr(AuditLogger, "record", append_bad_line)
    with pytest.raises(BatchQuantityPersistenceError):
        call_evidence(tmp_path)


def test_success_does_not_return_if_event_is_changed_before_persistence(tmp_path, monkeypatch):
    original = AuditLogger.record

    def tamper_event(self, event):
        event.decision["evidence"]["source_kind"] = "real_erp"
        original(self, event)

    monkeypatch.setattr(AuditLogger, "record", tamper_event)
    with pytest.raises(BatchQuantityPersistenceError):
        call_evidence(tmp_path)


def test_success_does_not_return_if_chain_verification_fails(tmp_path, monkeypatch):
    original = AuditLogger.verify_chain
    calls = 0

    def fail_after_write(self):
        nonlocal calls
        calls += 1
        if calls == 1:
            return original(self)
        return ChainVerifyResult(ok=False, total=1, error="forced synthetic chain failure")

    monkeypatch.setattr(AuditLogger, "verify_chain", fail_after_write)
    with pytest.raises(BatchQuantityPersistenceError):
        call_evidence(tmp_path)
```

## 根静态审阅补记

2026-10-10T21:57:15.000+08:00。独立Luna复核64AD候选的API/hash/cache边界；根随后补正测试附录缺失hashlib导入、删除产品附录重复导入，并绑定Native起点310f54de71149b0cb0281749619ee3cd84f97bca与设计已批后的tasks SHA。两Python附录仅AST解析及导入静态核对，无测试或实现执行。具体实施仍须本人批准。
