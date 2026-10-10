# 供审执行边界（根会话收敛）

本计划供审，不授权立即执行。D1–D7已批design SHA 04F3A5FA07F21BA7FD8ED0C9B31EF0A322827CF3B540F6A926C788FF76C544D6 不变；新增具体八路径/单测试文件/Native副作用审。

1. 起点固定 `28337c0ebb52afdbf61e955ecdbc22d151bcd185`。获批后 app 原生 `create_worktree(allowAsync=true, name=o4-stage0-evidence-1010, ref=28337c0ebb52afdbf61e955ecdbc22d151bcd185)` 创建并附着新候选；批准包含返回的仓库外新checkout/必要Git元数据，实际绝对路径留证，旧树/dirty/证据保留。
2. 实现仅正文八路径，不加依赖/服务；定向测试唯一 `tests/test_stage0.py`。每次主仓 ignored `reports/o4-single-class-1010/<new-uuid>/` 保存独立basetemp（synthetic JSONL/lock）、JUnit、stdout/stderr及exit，-B/nocache。无旧目录覆盖/清理。
3. 计划和批准OpenSpec从主仓读取，产品在新树；下面命令显式CandidateRoot并核起点，根锁内维护正式tasks/队列。候选提交整合/ff/push、专业签认、真实资料、生产、外发、晋档/归档另审。
4. Stage0单scope类别无关八例，所有预测/维护/OEE及professional_signoff为空。审计L1仅标结构检查，不代表Stage2维护工程师L2业务签认。首期1类/类别后定/完整intent/D1–D7不重问，真实类别与Owner/资料留后阶段。

---

# O4 Stage0 合成证据结构实施计划

> 执行入口：Native 隔离候选树；由父会话提供创建后返回的 `CandidateRoot`。本计划只描述未来获批后如何实现，不创建工作树、不运行命令。

**目标：**为 O4 建立类别无关、只接收显式 synthetic 单 scope 输入的冻结证据封套、结构问题检查、`not_evaluated` 输出与真实平台 JSONL 审计。

**架构：**在 O4 自有 Python 包内分离模型/冻结、canonical hash、结构检查、审计运行器；纯结构检查不读外部 source_ref，唯一完整运行入口强制非空 actor 与平台 `JsonlSink`，事件写入失败不得返回成功。所有预测、维护建议、备件建议和 OEE 数值保持空。

**技术栈：**Python 标准库 dataclass、hashlib、json、datetime；现有 `zhuopin_platform.audit.AuditEvent` / `AuditLogger`；pytest。不得新增 ML、IoT、数据库或服务依赖。

**Spec：**`openspec/changes/o4-single-class-maintenance/specs/o4-maintenance-evidence/spec.md`；批准设计：`openspec/changes/o4-single-class-maintenance/design.md`（D1–D7 批准原件 SHA256：`04F3A5FA07F21BA7FD8ED0C9B31EF0A322827CF3B540F6A926C788FF76C544D6`）；完整业务意图：`4-数字员工/运营部/O4-设备预测性维护/intent.md`。

## 根审补充

资产自身来源版本纳入AssetEvidence/hash（可空则原样保留，不造真实版号）；公共canonical_input_sha256一并re-export。同一scope/source_event_id跨asset冲突生成明确issue，不依第一个输入行决定issue资产；两次换序保持输入/output hash和issues相同。对应新增两个具名技术测试。Stage0事件固定L1表示结构检查，Stage2业务维护工程师L2仍后置；该字段不会生成专业签认。

## 全局约束

- 完整intent与D1–D7已批准；本计划仍须单独审核，formal tasks 1.5 未完成，当前不授权产品实现或测试。
- Stage0 仅是类别无关的合成结构证据；不得输出健康分、故障概率/模式、RUL、风险级别、维护时机、备件建议或 OEE 实绩。
- 每个完整封套必须明确 `synthetic=true`、非空 bundle/revision/schema/scope；只容纳一个 scope。类别可以未选；不得默认设备类别、阈值、单位或时区。
- 冻结资产、测量、维护输入的所有原值和 source_ref；缺失 `None` 与 `0` 分开；记录顺序 canonical 排序但重复记录不得去重。
- 来源引用只是标识，Stage0 不访问 source_ref；不接 IoT、PLC、ERP、维修系统、文件或真实数据库。
- 原值/冲突/关联/时区问题只形成结构 issue，不补值、换算、推故障或选择“最新正确版本”。
- `AuditEvent` 不得含原始测量值、维护原文或完整长文本；完整运行须使用平台 `AuditLogger` 且 `audit.sink` 是 `JsonlSink`，必须在真实 sink 写成功后才返回结果。
- 本阶段 actor 是合成结构核验操作者标识，不代表 Owner、backup、维护工程师或专业签认人；`professional_signoff` 永远为空。
- 所有变更限于下列 O4 包与测试文件；不修改 intent、OpenSpec、平台、队列、runtime、忽略规则、其他场景或已有共享数据。

## 复核重点

1. 同一个 source event 多 revision 冲突时两行均保留，并产生冲突 issue；没有任何 last-write 选择。
2. 缺值 `None`、原值 `0`、未声明单位、单位不一致和无时区必须分别可见；任何 issue 都不变成设备故障判断。
3. 相同 `asset_id` 或显示标签在两个 scope 中必须彼此隔离；scope 不同的封套分别运行、分别 hash。
4. 输入中的嵌套 dict/list 在冻结后变化不影响已冻结快照、输入 hash 或结果。
5. 缺 audit、非 JSONL sink、空 actor、非法输入、NaN/Inf 或真实 sink 写失败，均不得得到完整成功结果。

---

## 现状与实施触碰区

- 定点目录核验：`4-数字员工/运营部/O4-设备预测性维护/` 当前只有 `CLAUDE.md` 与 `intent.md`，没有既有产品包或测试目录；本次会创建新包。
- 已批准设计将现有 O4-C01–C08 明确作为合成结构样例，`actual_run=null`、`professional_signoff=null` 不计为已运行或已签认。样例来源为 `0-学习与工具/codex-handoff/运营O3O4合成证据对照包-2026-10-04.json` 的 `o4_cases`。
- 旧样例记录用 `oem_scope` 表示范围；新增合成测试封套将该既有 mock 值原样映射为显式 `scope`，不代表读取或处理任何实际 OEM 资料。
- 平台真实审计接口已按定点源码核验：`5-平台底座/zhuopin_platform/zhuopin_platform/audit/events.py` 的 `AuditEvent` 必填 `scenario/action/evaluator/automation_level`，`decision` 与 `data_sources` 默认为 dict，`content_hash` 是字符串；`logger.py` 中 `AuditLogger.jsonl(path)` 构造 logger、`record(event)` 调用 sink 的 `write`、`query_by` 读回 JSONL、`verify_chain()` 返回含 `ok` 和 `total` 的 `ChainVerifyResult`。`sinks.py` 的 `JsonlSink` 执行真实 append-only JSONL 写入并创建旁侧 `.lock`；logger 构造本身不证明写入成功。
- `tests/conftest.py` 按 `5-平台底座/zhuopin_platform/zhuopin_platform/bootstrap.py` 的唯一样板严格引导本场景包和平台路径；不新增服务入口、端口或安装/依赖配置。

### 精确文件白名单

创建：

1. `4-数字员工/运营部/O4-设备预测性维护/o4_maintenance_evidence/__init__.py`
2. `4-数字员工/运营部/O4-设备预测性维护/o4_maintenance_evidence/models.py`
3. `4-数字员工/运营部/O4-设备预测性维护/o4_maintenance_evidence/canonical.py`
4. `4-数字员工/运营部/O4-设备预测性维护/o4_maintenance_evidence/checks.py`
5. `4-数字员工/运营部/O4-设备预测性维护/o4_maintenance_evidence/agent.py`
6. `4-数字员工/运营部/O4-设备预测性维护/tests/conftest.py`
7. `4-数字员工/运营部/O4-设备预测性维护/tests/o4_cases.py`
8. `4-数字员工/运营部/O4-设备预测性维护/tests/test_stage0.py`

运行证据只落在主仓 `reports/o4-single-class-1010/<execution-uuid>/` 下的 `junit.xml`、`stdout.log`、`stderr.log`、`basetemp/`。已执行只读 `git check-ignore -v`，真实命中 `.gitignore:59:**/reports/`；拟定报告路径也命中该规则。不得创建或修改 `.gitignore`。不改 O4 CLAUDE、intent、OpenSpec、平台 audit、全景规划、队列或其他场景。

## API 与数据合同

公共入口只暴露：`freeze_bundle(raw: Mapping[str, object]) -> FrozenEvidenceBundle`、`canonical_input_sha256(bundle) -> str`、`check_structure(bundle) -> tuple[EvidenceIssue, ...]`、`run_synthetic_evidence(raw, *, actor: str, audit: AuditLogger) -> Stage0Run`。前 3 项是可复用的确定性数据/检查函数；只有最后一项表示一次完整、真实 JSONL 留痕的 Stage0 run。

固定常量：`SCENARIO = "O4"`、`ACTION = "stage0_synthetic_evidence"`、`SCHEMA_VERSION = "o4-evidence-v1"`、`RULES_VERSION = "o4-structure-checks-v1"`、`CANONICAL_VERSION = "o4-canonical-json-v1"`、`PREDICTION_STATUS = "not_evaluated"`。任何预测或业务建议字段用 `None`，而不是 0、空文本或默认等级。

`automation_level` 固定为 `L1`，只表明这是无业务动作的结构检查事件；该合成 actor 不代表 L2 人工确认。事件 `decision` 仅记录身份、schema、synthetic 标记、输入/输出/来源引用摘要 hash、结构规则版本、issue code 计数、`not_evaluated` 与空签认。事件 `data_sources` 保持 `dict[str, str]`，只存封套 identity/hash/规则版本，不存原始 source_ref 列表或原值。

## Task 1：新增冻结类型和 canonical hashing

**文件：**创建 `o4_maintenance_evidence/models.py`、`canonical.py`、`__init__.py`；测试在 `tests/test_stage0.py`。本 Task 只建立显式 schema、深冻结、拒绝非法 JSON 数和字节级 hash；不做关联业务结论。

**接口：**`freeze_bundle` 将普通映射/list 输入复制成嵌套冻结 dataclass/tuple； `canonical_input_sha256` 对完整冻结封套作 canonical hash。canonical 只改变数组顺序以稳定字节，不删除重复行。

`models.py` 的完整类型与深冻结基线：

```python
from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypeAlias


class InvalidEvidenceInput(ValueError):
    pass


SCHEMA_VERSION = "o4-evidence-v1"


@dataclass(frozen=True, slots=True)
class FrozenObject:
    items: tuple[tuple[str, "FrozenJSON"], ...]


@dataclass(frozen=True, slots=True)
class FrozenArray:
    items: tuple["FrozenJSON", ...]


FrozenJSON: TypeAlias = None | bool | int | float | str | FrozenObject | FrozenArray


def freeze_json(value: object, *, path: str = "value") -> FrozenJSON:
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise InvalidEvidenceInput(f"{path}: NaN/Inf 不允许进入 canonical evidence")
        return value
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise InvalidEvidenceInput(f"{path}: JSON object key 必须是字符串")
        return FrozenObject(tuple(
            (key, freeze_json(value[key], path=f"{path}.{key}"))
            for key in sorted(value)
        ))
    if type(value) in (list, tuple):
        return FrozenArray(tuple(
            freeze_json(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ))
    raise InvalidEvidenceInput(f"{path}: unsupported JSON value type {type(value).__name__}")


def _required_text(row: Mapping[str, object], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InvalidEvidenceInput(f"{key} 必须是非空字符串")
    return value


def _optional_text(row: Mapping[str, object], key: str) -> str | None:
    value = row.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidEvidenceInput(f"{key} 必须是字符串或 None")
    return value


def _preserved_text(row: Mapping[str, object], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str):
        raise InvalidEvidenceInput(f"{key} 必须显式为字符串")
    return value


def _rows(raw: Mapping[str, object], key: str) -> tuple[Mapping[str, object], ...]:
    rows = raw.get(key)
    if type(rows) not in (list, tuple):
        raise InvalidEvidenceInput(f"{key} 必须显式为 list/tuple")
    if any(not isinstance(row, Mapping) for row in rows):
        raise InvalidEvidenceInput(f"{key} 每项必须为 mapping")
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class AssetEvidence:
    scope: str
    asset_id: str
    source_revision: str | None
    display_label: str
    device_category: str | None
    source_ref: str


@dataclass(frozen=True, slots=True)
class MeasurementEvidence:
    scope: str
    source_event_id: str
    source_revision: str | None
    asset_id: str
    metric_key: str
    raw_value: FrozenJSON
    declared_unit: str
    occurred_at: str
    retrieved_at: str
    source_ref: str


@dataclass(frozen=True, slots=True)
class MaintenanceEvidence:
    scope: str
    record_id: str
    source_revision: str | None
    asset_id: str
    occurred_at: str
    raw_report: str
    source_ref: str
    professional_fault_label: str | None


@dataclass(frozen=True, slots=True)
class FrozenEvidenceBundle:
    bundle_id: str
    revision: str
    schema_version: str
    synthetic: bool
    scope: str
    assets: tuple[AssetEvidence, ...]
    measurements: tuple[MeasurementEvidence, ...]
    maintenance: tuple[MaintenanceEvidence, ...]


@dataclass(frozen=True, slots=True)
class EvidenceIssue:
    code: str
    scope: str
    asset_id: str
    record_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Stage0Report:
    bundle_id: str
    revision: str
    schema_version: str
    scope: str
    synthetic: bool
    rules_version: str
    canonical_version: str
    input_sha256: str
    source_refs_sha256: str
    output_sha256: str
    issues: tuple[EvidenceIssue, ...]
    structural_status: str
    prediction_status: str
    health_score: None
    failure_probability: None
    failure_mode: None
    risk_level: None
    risk_score: None
    remaining_useful_life: None
    maintenance_recommendations: None
    spare_parts_recommendations: None
    oee_actual: None
    professional_signoff: None


@dataclass(frozen=True, slots=True)
class Stage0Run:
    report: Stage0Report


def _same_scope(row: Mapping[str, object], bundle_scope: str, group: str) -> None:
    row_scope = _required_text(row, "scope")
    if row_scope != bundle_scope:
        raise InvalidEvidenceInput(
            f"{group} row scope differs from bundle scope; split into separate runs"
        )


def freeze_bundle(raw: Mapping[str, object]) -> FrozenEvidenceBundle:
    if not isinstance(raw, Mapping):
        raise InvalidEvidenceInput("bundle 必须是 mapping")
    if raw.get("synthetic") is not True:
        raise InvalidEvidenceInput("Stage0 只接受显式 synthetic=true")
    bundle_id = _required_text(raw, "bundle_id")
    revision = _required_text(raw, "revision")
    schema_version = _required_text(raw, "schema_version")
    if schema_version != SCHEMA_VERSION:
        raise InvalidEvidenceInput(f"unsupported schema_version: {schema_version}")
    scope = _required_text(raw, "scope")

    assets = []
    for row in _rows(raw, "assets"):
        _same_scope(row, scope, "assets")
        assets.append(AssetEvidence(
            scope=scope,
            asset_id=_required_text(row, "asset_id"),
            source_revision=_optional_text(row, "source_revision"),
            display_label=_preserved_text(row, "display_label"),
            device_category=_optional_text(row, "device_category"),
            source_ref=_required_text(row, "source_ref"),
        ))

    measurements = []
    for row in _rows(raw, "measurements"):
        _same_scope(row, scope, "measurements")
        if "raw_value" not in row:
            raise InvalidEvidenceInput("measurements.raw_value 必须显式提供；None 表示原值缺失")
        measurements.append(MeasurementEvidence(
            scope=scope,
            source_event_id=_required_text(row, "source_event_id"),
            source_revision=_optional_text(row, "source_revision"),
            asset_id=_required_text(row, "asset_id"),
            metric_key=_required_text(row, "metric_key"),
            raw_value=freeze_json(row["raw_value"], path="measurements.raw_value"),
            declared_unit=_preserved_text(row, "declared_unit"),
            occurred_at=_preserved_text(row, "occurred_at"),
            retrieved_at=_preserved_text(row, "retrieved_at"),
            source_ref=_required_text(row, "source_ref"),
        ))

    maintenance = []
    for row in _rows(raw, "maintenance"):
        _same_scope(row, scope, "maintenance")
        maintenance.append(MaintenanceEvidence(
            scope=scope,
            record_id=_required_text(row, "record_id"),
            source_revision=_optional_text(row, "source_revision"),
            asset_id=_required_text(row, "asset_id"),
            occurred_at=_preserved_text(row, "occurred_at"),
            raw_report=_preserved_text(row, "raw_report"),
            source_ref=_required_text(row, "source_ref"),
            professional_fault_label=_optional_text(row, "professional_fault_label"),
        ))

    # 新 dataclass 均冻结，集合转 tuple；raw_value 的嵌套 object/list 已递归冻结。
    return FrozenEvidenceBundle(
        bundle_id=bundle_id, revision=revision, schema_version=schema_version,
        synthetic=True, scope=scope, assets=tuple(assets),
        measurements=tuple(measurements), maintenance=tuple(maintenance),
    )
```

`canonical.py` 的完整基线：

```python
from __future__ import annotations

import hashlib
import json
import math

from .models import FrozenArray, FrozenObject, FrozenEvidenceBundle, Stage0Report

CANONICAL_VERSION = "o4-canonical-json-v1"


def to_json_value(value):
    if isinstance(value, FrozenObject):
        return {key: to_json_value(item) for key, item in value.items}
    if isinstance(value, FrozenArray):
        return [to_json_value(item) for item in value.items]
    if type(value) is float and not math.isfinite(value):
        raise ValueError("NaN/Inf cannot be canonicalized")
    if type(value) in (list, tuple):
        return [to_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: to_json_value(value[key]) for key in sorted(value)}
    return value


def canonical_bytes(value) -> bytes:
    return json.dumps(
        to_json_value(value), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def sha256_hex(value) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def canonical_bundle_value(bundle: FrozenEvidenceBundle) -> dict:
    # 输入schema字段显式列出；增删字段必须审查hash合同并更新版本。
    value = {
        "bundle_id": bundle.bundle_id,
        "revision": bundle.revision,
        "schema_version": bundle.schema_version,
        "synthetic": bundle.synthetic,
        "scope": bundle.scope,
        "assets": [{
            "scope": row.scope, "asset_id": row.asset_id,
            "source_revision": row.source_revision,
            "display_label": row.display_label, "device_category": row.device_category,
            "source_ref": row.source_ref,
        } for row in bundle.assets],
        "measurements": [{
            "scope": row.scope, "source_event_id": row.source_event_id,
            "source_revision": row.source_revision, "asset_id": row.asset_id,
            "metric_key": row.metric_key, "raw_value": to_json_value(row.raw_value),
            "declared_unit": row.declared_unit, "occurred_at": row.occurred_at,
            "retrieved_at": row.retrieved_at, "source_ref": row.source_ref,
        } for row in bundle.measurements],
        "maintenance": [{
            "scope": row.scope, "record_id": row.record_id,
            "source_revision": row.source_revision, "asset_id": row.asset_id,
            "occurred_at": row.occurred_at, "raw_report": row.raw_report,
            "source_ref": row.source_ref,
            "professional_fault_label": row.professional_fault_label,
        } for row in bundle.maintenance],
    }
    # D5：按每一行自身canonical bytes排序，保留完全重复项，不依赖调用方顺序。
    for key in ("assets", "measurements", "maintenance"):
        value[key] = sorted(value[key], key=canonical_bytes)
    return value


def canonical_report_value(report: Stage0Report, *, include_output_hash: bool = False) -> dict:
    # 输出schema同样显式列出，避免 dataclass 新字段被无审查地并入旧hash。
    value = {
        "bundle_id": report.bundle_id, "revision": report.revision,
        "schema_version": report.schema_version, "scope": report.scope,
        "synthetic": report.synthetic, "rules_version": report.rules_version,
        "canonical_version": report.canonical_version,
        "input_sha256": report.input_sha256,
        "source_refs_sha256": report.source_refs_sha256,
        "issues": [{
            "code": issue.code, "scope": issue.scope,
            "asset_id": issue.asset_id, "record_refs": list(issue.record_refs),
        } for issue in report.issues],
        "structural_status": report.structural_status,
        "prediction_status": report.prediction_status,
        "health_score": report.health_score,
        "failure_probability": report.failure_probability,
        "failure_mode": report.failure_mode,
        "risk_level": report.risk_level,
        "risk_score": report.risk_score,
        "remaining_useful_life": report.remaining_useful_life,
        "maintenance_recommendations": report.maintenance_recommendations,
        "spare_parts_recommendations": report.spare_parts_recommendations,
        "oee_actual": report.oee_actual,
        "professional_signoff": report.professional_signoff,
    }
    if include_output_hash:
        value["output_sha256"] = report.output_sha256
    return value


def canonical_input_sha256(bundle: FrozenEvidenceBundle) -> str:
    return hashlib.sha256(canonical_bytes(canonical_bundle_value(bundle))).hexdigest()
```

`__init__.py` 固定 re-export：

```python
from .agent import ACTION, SCENARIO, run_synthetic_evidence
from .canonical import canonical_input_sha256
from .checks import RULES_VERSION, check_structure
from .models import SCHEMA_VERSION, InvalidEvidenceInput, freeze_bundle

__all__ = [
    "ACTION", "SCENARIO", "RULES_VERSION", "SCHEMA_VERSION", "InvalidEvidenceInput",
    "canonical_input_sha256", "check_structure", "freeze_bundle", "run_synthetic_evidence",
]
```

**Step-by-step future test cycle：**先在 `tests/test_stage0.py` 加 `test_freeze_copies_nested_values`、`test_canonical_hash_changes_when_raw_value_changes`、`test_record_order_is_canonical_but_duplicates_remain` 三项；分别从 O4 子项目 cwd 执行 `pytest tests/test_stage0.py::test_freeze_copies_nested_values -q`、`pytest tests/test_stage0.py::test_canonical_hash_changes_when_raw_value_changes -q`、`pytest tests/test_stage0.py::test_record_order_is_canonical_but_duplicates_remain -q`。每项先因待实现模块/函数失败，再实现最小模型/hash 后通过。最后仅从 O4 子项目 cwd 执行本计划末尾的完整命令，不在仓库根混跑。

## Task 2：C01–C08 deterministic 结构检查

**文件：**创建 `checks.py`、`tests/o4_cases.py`，扩展 `tests/test_stage0.py`。所有 issue 仅包含 code、scope、asset/record refs；不带原始值或维护长文本。`check_structure` 是纯函数，结果只说明结构证据，不代表预测就绪。

`checks.py` 完整基线：

```python
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from .canonical import canonical_bytes
from .models import EvidenceIssue, FrozenEvidenceBundle

RULES_VERSION = "o4-structure-checks-v1"


def _timestamp_issue(value: str) -> str | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return "timestamp_invalid"
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return "timestamp_timezone_missing"
    return None


def _issue(code: str, scope: str, asset_id: str, refs) -> EvidenceIssue:
    return EvidenceIssue(code, scope, asset_id, tuple(sorted(refs)))


def check_structure(bundle: FrozenEvidenceBundle) -> tuple[EvidenceIssue, ...]:
    issues = []
    registered_assets = {(row.scope, row.asset_id) for row in bundle.assets}
    measurement_assets = set()
    maintenance_assets = set()

    unit_groups = defaultdict(list)
    event_groups = defaultdict(list)

    for row in bundle.measurements:
        key = (row.scope, row.asset_id)
        measurement_assets.add(key)
        if key not in registered_assets:
            issues.append(_issue("asset_reference_unmatched", row.scope, row.asset_id, [row.source_ref]))
        if row.raw_value is None:
            issues.append(_issue("raw_value_missing", row.scope, row.asset_id, [row.source_ref]))
        if row.source_revision is None or not row.source_revision.strip():
            issues.append(_issue("source_revision_missing", row.scope, row.asset_id, [row.source_ref]))
        if not row.declared_unit.strip():
            issues.append(_issue("unit_declaration_missing", row.scope, row.asset_id, [row.source_ref]))
        unit_groups[(row.scope, row.asset_id, row.metric_key)].append(row)
        event_groups[(row.scope, row.source_event_id)].append(row)
        for time_field in (row.occurred_at, row.retrieved_at):
            code = _timestamp_issue(time_field)
            if code:
                issues.append(_issue(code, row.scope, row.asset_id, [row.source_ref]))

    for row in bundle.maintenance:
        key = (row.scope, row.asset_id)
        maintenance_assets.add(key)
        if key not in registered_assets:
            issues.append(_issue("asset_reference_unmatched", row.scope, row.asset_id, [row.source_ref]))
        code = _timestamp_issue(row.occurred_at)
        if code:
            issues.append(_issue(code, row.scope, row.asset_id, [row.source_ref]))

    for (scope, asset_id, _metric), rows in unit_groups.items():
        units = {row.declared_unit for row in rows}
        if len(units) > 1:
            issues.append(_issue(
                "unit_declaration_conflict", scope, asset_id,
                [row.source_ref for row in rows],
            ))

    for (scope, _event_id), rows in event_groups.items():
        distinct_values = {canonical_bytes(row.raw_value) for row in rows}
        asset_ids = {row.asset_id for row in rows}
        issue_asset = next(iter(asset_ids)) if len(asset_ids) == 1 else ""
        if len(asset_ids) > 1:
            issues.append(_issue(
                "source_event_asset_conflict", scope, "",
                [row.source_ref for row in rows],
            ))
        if len(rows) > 1 and len(distinct_values) > 1:
            issues.append(_issue(
                "source_event_revision_conflict", scope, issue_asset,
                [row.source_ref for row in rows],
            ))

    # 结构提示而非业务结论：当本包的测量与维护资产集合完全分离，保留两边并提示不可互作标签。
    if measurement_assets and maintenance_assets and measurement_assets.isdisjoint(maintenance_assets):
        refs = [row.source_ref for row in (*bundle.measurements, *bundle.maintenance)]
        issues.append(_issue("cross_asset_evidence_not_joined", bundle.scope, "", refs))

    return tuple(sorted(
        issues,
        key=lambda issue: (issue.code, issue.scope, issue.asset_id, issue.record_refs),
    ))
```

冲突值以冻结后 JSON bytes 比较，避免 Python `True == 1` 被当成同一原值；不使用 repr/stringified values。不得比较 display label 作关联键。

`tests/o4_cases.py` 完整合成 builder（C08 的两个 scope 各自独立成输入）：

```python
from copy import deepcopy

BASE_TIME = "2026-10-01T10:00:00+08:00"
RETRIEVED = "2026-10-01T11:00:00+08:00"


def asset(asset_id, scope="MOCK-OEM-A", label=None):
    return {
        "scope": scope, "asset_id": asset_id,
        "source_revision": "r1",  # 新合成asset材料自身的显式版本，非真实源证明
        "display_label": label or asset_id,
        "device_category": None,
        "source_ref": f"mock://O4-common/{scope}/asset/{asset_id}",
    }


def measurement(event_id, asset_id, value, *, revision="r1", scope="MOCK-OEM-A",
                unit="unit_unassigned", occurred=BASE_TIME, retrieved=RETRIEVED):
    return {
        "scope": scope, "source_event_id": event_id, "source_revision": revision,
        "asset_id": asset_id, "metric_key": "synthetic_signal", "raw_value": value,
        "declared_unit": unit, "occurred_at": occurred, "retrieved_at": retrieved,
        "source_ref": f"mock://O4-common/{scope}/{event_id}/{revision}",
    }


def maintenance(record_id, asset_id, *, scope="MOCK-OEM-A", occurred="2026-10-01T09:00:00+08:00"):
    return {
        "scope": scope, "record_id": record_id, "source_revision": None,
        "asset_id": asset_id, "occurred_at": occurred,
        "raw_report": "synthetic maintenance record; no fault label confirmed",
        "source_ref": f"mock://O4-common/{scope}/maintenance/{record_id}",
        "professional_fault_label": None,
    }


def make_bundle(case_id, scope, assets, measurements, maintenance_rows):
    return {
        "bundle_id": f"O4-{case_id}", "revision": "r1",
        "schema_version": "o4-evidence-v1", "synthetic": True, "scope": scope,
        "assets": assets, "measurements": measurements, "maintenance": maintenance_rows,
    }


def eight_cases():
    a = "MOCK-OEM-A"
    c01 = make_bundle("C01", a, [asset("MOCK-ASSET-01")],
        [measurement("M01", "MOCK-ASSET-01", 10.0)],
        [maintenance("MAINT-MOCK-ASSET-01", "MOCK-ASSET-01")])
    c02 = make_bundle("C02", a, [], [measurement("M02", "MOCK-ASSET-02", 11.0)], [])
    c03 = make_bundle("C03", a, [asset("MOCK-ASSET-03")],
        [measurement("M03", "MOCK-ASSET-03", None)], [])
    c04 = make_bundle("C04", a, [asset("MOCK-ASSET-04")], [
        measurement("M04-A", "MOCK-ASSET-04", 12.0, unit="unit_A"),
        measurement("M04-B", "MOCK-ASSET-04", 13.0, unit="unit_B"),
    ], [])
    c05 = make_bundle("C05", a, [asset("MOCK-ASSET-05")],
        [measurement("M05", "MOCK-ASSET-05", 14.0, occurred="2026-10-01T10:00:00")], [])
    c06 = make_bundle("C06", a, [asset("MOCK-ASSET-06")], [
        measurement("M06", "MOCK-ASSET-06", 15.0, revision="r1"),
        measurement("M06", "MOCK-ASSET-06", 16.0, revision="r2"),
    ], [])
    c07 = make_bundle("C07", a,
        [asset("MOCK-ASSET-07A"), asset("MOCK-ASSET-07B")],
        [measurement("M07", "MOCK-ASSET-07A", 17.0)],
        [maintenance("MAINT-MOCK-ASSET-07B", "MOCK-ASSET-07B")])
    c08a = make_bundle("C08-A", "MOCK-OEM-A", [asset("MOCK-ASSET-08", "MOCK-OEM-A", "same mock label")],
        [measurement("M08-A", "MOCK-ASSET-08", 18.0, scope="MOCK-OEM-A")], [])
    c08b = make_bundle("C08-B", "MOCK-OEM-B", [asset("MOCK-ASSET-08", "MOCK-OEM-B", "same mock label")],
        [measurement("M08-B", "MOCK-ASSET-08", 19.0, scope="MOCK-OEM-B")], [])
    return {"C01": c01, "C02": c02, "C03": c03, "C04": c04,
            "C05": c05, "C06": c06, "C07": c07, "C08-A": c08a, "C08-B": c08b}


def clone_case(case):
    return deepcopy(case)
```

`tests/test_stage0.py` 的结构验收基线：

```python
import pytest

from o4_maintenance_evidence.checks import check_structure
from o4_maintenance_evidence.canonical import canonical_input_sha256, to_json_value
from o4_maintenance_evidence.models import freeze_bundle
from o4_cases import eight_cases


def test_freeze_copies_nested_values():
    case = eight_cases()["C01"]
    case["measurements"][0]["raw_value"] = {"samples": [10, {"quality": "synthetic"}]}
    frozen = freeze_bundle(case)
    before = canonical_input_sha256(frozen)
    case["measurements"][0]["raw_value"]["samples"][1]["quality"] = "mutated"
    case["measurements"].append(dict(case["measurements"][0]))
    assert to_json_value(frozen.measurements[0].raw_value) == {
        "samples": [10, {"quality": "synthetic"}]
    }
    assert canonical_input_sha256(frozen) == before


def test_canonical_hash_changes_when_raw_value_changes():
    cases = eight_cases()
    first = freeze_bundle(cases["C01"])
    cases["C01"]["measurements"][0]["raw_value"] = 10.5
    second = freeze_bundle(cases["C01"])
    assert len(check_structure(first)) == len(check_structure(second))
    assert canonical_input_sha256(first) != canonical_input_sha256(second)


def test_record_order_is_canonical_but_duplicates_remain():
    case = eight_cases()["C04"]
    reordered = {**case, "measurements": list(reversed(case["measurements"]))}
    first, second = freeze_bundle(case), freeze_bundle(reordered)
    assert canonical_input_sha256(first) == canonical_input_sha256(second)
    duplicated = {**case, "measurements": case["measurements"] + [dict(case["measurements"][0])]}
    third = freeze_bundle(duplicated)
    assert len(third.measurements) == len(first.measurements) + 1
    assert canonical_input_sha256(third) != canonical_input_sha256(first)


@pytest.mark.parametrize("case_id", ["C01", "C02", "C03", "C04", "C05", "C06", "C07"])
def test_c01_to_c07_expected_structural_findings(case_id):
    cases = eight_cases()
    issues = check_structure(freeze_bundle(cases[case_id]))
    codes = {issue.code for issue in issues}
    expected = {
        "C01": set(),
        "C02": {"asset_reference_unmatched"},
        "C03": {"raw_value_missing"},
        "C04": {"unit_declaration_conflict"},
        "C05": {"timestamp_timezone_missing"},
        "C06": {"source_event_revision_conflict"},
        "C07": {"cross_asset_evidence_not_joined"},
    }
    assert codes == expected[case_id]


def test_c06_keeps_both_conflicting_revisions():
    frozen = freeze_bundle(eight_cases()["C06"])
    assert [row.source_revision for row in frozen.measurements] == ["r1", "r2"]
    assert [row.raw_value for row in frozen.measurements] == [15.0, 16.0]


def test_zero_is_not_missing_and_duplicate_records_are_retained():
    case = eight_cases()["C01"]
    case["measurements"][0]["raw_value"] = 0
    case["measurements"].append(dict(case["measurements"][0]))
    frozen = freeze_bundle(case)
    assert len(frozen.measurements) == 2
    assert all(row.raw_value == 0 for row in frozen.measurements)
    assert "raw_value_missing" not in {item.code for item in check_structure(frozen)}


def test_c08_same_asset_id_and_label_remain_separate_scope_runs():
    from o4_maintenance_evidence.canonical import canonical_input_sha256
    cases = eight_cases()
    a, b = freeze_bundle(cases["C08-A"]), freeze_bundle(cases["C08-B"])
    assert (a.scope, a.assets[0].asset_id) != (b.scope, b.assets[0].asset_id)
    assert a.assets[0].display_label == b.assets[0].display_label
    assert canonical_input_sha256(a) != canonical_input_sha256(b)
```

`C08` 是两个独立 bundle/run，不调用能接受多 scope 的聚合 API；同名/同 asset id 不构成跨 scope 键。对其分别执行 Stage0 后比较不同 input/output hash、两个 audit 行且各自仅引用对应 scope。C02 到 C07 的 source_ref 均为现有 synthetic mock URI，无网络/外部访问。

## Task 3：not_evaluated 报告、单一完整入口与真实 JSONL

**文件：**创建 `agent.py`；扩展 `test_stage0.py`。任何结构问题均可形成一份“有 issues 的合成检查结果”，但不能变成预测或维护结论。完整入口在写审计前验证 actor/audit/synthetic/scope；只在 `record` 成功后返回 `Stage0Run`。

`EvidenceIssue`、`Stage0Report`、`Stage0Run` 已在 Task 1 的 `models.py` 中定义；`checks.py` 只导入 `EvidenceIssue`，避免循环依赖。

`agent.py` 完整入口/审计基线：

```python
from __future__ import annotations

from collections import Counter
from dataclasses import replace
import hashlib

from zhuopin_platform.audit import AuditEvent, AuditLogger, JsonlSink

from .canonical import (
    CANONICAL_VERSION, canonical_bytes, canonical_input_sha256,
    canonical_report_value,
)
from .checks import RULES_VERSION, check_structure
from .models import Stage0Report, Stage0Run, freeze_bundle

SCENARIO = "O4"
ACTION = "stage0_synthetic_evidence"
PREDICTION_STATUS = "not_evaluated"


class AuditRequiredError(ValueError):
    pass


def run_synthetic_evidence(raw, *, actor: str, audit: AuditLogger) -> Stage0Run:
    if not isinstance(actor, str) or not actor.strip():
        raise AuditRequiredError("完整合成run需要非空actor")
    if not isinstance(audit, AuditLogger) or not isinstance(audit.sink, JsonlSink):
        raise AuditRequiredError("完整合成run必须使用真实平台JsonlSink")

    bundle = freeze_bundle(raw)
    issues = check_structure(bundle)
    input_sha = canonical_input_sha256(bundle)
    refs_value = {
        "assets": sorted(row.source_ref for row in bundle.assets),
        "measurements": sorted(row.source_ref for row in bundle.measurements),
        "maintenance": sorted(row.source_ref for row in bundle.maintenance),
    }
    source_refs_sha = hashlib.sha256(canonical_bytes(refs_value)).hexdigest()
    report_without_output_hash = Stage0Report(
        bundle_id=bundle.bundle_id, revision=bundle.revision,
        schema_version=bundle.schema_version, scope=bundle.scope, synthetic=True,
        rules_version=RULES_VERSION, canonical_version=CANONICAL_VERSION,
        input_sha256=input_sha, source_refs_sha256=source_refs_sha, output_sha256="",
        issues=issues,
        structural_status="issues_present" if issues else "no_structural_issues",
        prediction_status=PREDICTION_STATUS,
        health_score=None, failure_probability=None, failure_mode=None,
        risk_level=None, risk_score=None,
        remaining_useful_life=None, maintenance_recommendations=None,
        spare_parts_recommendations=None, oee_actual=None, professional_signoff=None,
    )
    output_sha = hashlib.sha256(
        canonical_bytes(canonical_report_value(report_without_output_hash))
    ).hexdigest()
    report = replace(report_without_output_hash, output_sha256=output_sha)
    issue_counts = dict(sorted(Counter(issue.code for issue in issues).items()))
    event = AuditEvent(
        scenario=SCENARIO, action=ACTION, evaluator=actor.strip(),
        automation_level="L1",
        decision={
            "stage": "stage0", "bundle_id": bundle.bundle_id,
            "revision": bundle.revision, "schema_version": bundle.schema_version,
            "synthetic": True, "input_sha256": input_sha,
            "source_refs_sha256": source_refs_sha, "output_sha256": output_sha,
            "canonical_version": CANONICAL_VERSION, "rules_version": RULES_VERSION,
            "issue_counts": issue_counts,
            "structural_status": report.structural_status,
            "prediction_status": PREDICTION_STATUS,
            "professional_signoff": None, "health_score": None,
            "failure_probability": None, "failure_mode": None,
            "risk_level": None, "risk_score": None,
            "remaining_useful_life": None, "maintenance_recommendations": None,
            "spare_parts_recommendations": None, "oee_actual": None,
        },
        data_sources={
            "bundle": f"{bundle.bundle_id}@{bundle.revision}",
            "input_sha256": input_sha, "source_refs_sha256": source_refs_sha,
            "canonical_version": CANONICAL_VERSION, "rules_version": RULES_VERSION,
        },
        content_hash=output_sha,
        oem_context="", override_reason="", report_path="", error="",
    )
    # JsonlSink.write 是真实 JSONL append；异常直接传播，绝不返回成功 Stage0Run。
    audit.record(event)
    return Stage0Run(report=report)
```

保持 `AuditEvent` 的 `scenario/action/evaluator/automation_level` 显式赋值，`decision` 仅含 hash/issue code counts/空预测，不写 raw_value、raw_report、source_ref 清单或真实姓名。`automation_level=L1` 表示确定性的类别无关结构检查，不表述 L2 审批；如与平台既定 L1/L2 解释不符，必须在合入前由专业审阅指出，不能悄悄改成“已 L2”。

Task 3 必须加入以下真实 JSONL 用例：

```python
import json
import pytest

from zhuopin_platform.audit import AuditLogger
from o4_maintenance_evidence.agent import ACTION, SCENARIO, AuditRequiredError, run_synthetic_evidence


def test_complete_stage0_writes_real_jsonl_and_keeps_every_prediction_empty(tmp_path):
    path = tmp_path / "o4-audit.jsonl"
    logger = AuditLogger.jsonl(path)
    run = run_synthetic_evidence(eight_cases()["C01"], actor="synthetic-test-operator", audit=logger)
    report = run.report
    assert report.synthetic is True
    assert report.structural_status == "no_structural_issues"
    assert report.prediction_status == "not_evaluated"
    assert all(value is None for value in (
        report.health_score, report.failure_probability, report.failure_mode,
        report.risk_level, report.risk_score,
        report.remaining_useful_life, report.maintenance_recommendations,
        report.spare_parts_recommendations, report.oee_actual,
        report.professional_signoff,
    ))
    events = AuditLogger.jsonl(path).query_by(scenario=SCENARIO, action=ACTION)
    assert len(events) == 1
    event = events[0]
    assert event["evaluator"] == "synthetic-test-operator"
    assert event["decision"]["input_sha256"] == report.input_sha256
    assert event["decision"]["output_sha256"] == report.output_sha256
    assert event["decision"]["prediction_status"] == "not_evaluated"
    assert event["decision"]["professional_signoff"] is None
    assert "raw_value" not in json.dumps(event, ensure_ascii=False)
    assert "raw_report" not in json.dumps(event, ensure_ascii=False)
    chain = AuditLogger.jsonl(path).verify_chain()
    assert chain.ok is True
    assert chain.total == 1


def test_c08_two_independent_runs_create_distinct_hashes_and_two_audit_rows(tmp_path):
    path = tmp_path / "o4-c08.jsonl"
    logger = AuditLogger.jsonl(path)
    results = [
        run_synthetic_evidence(eight_cases()[key], actor="synthetic-test-operator", audit=logger)
        for key in ("C08-A", "C08-B")
    ]
    assert results[0].report.scope == "MOCK-OEM-A"
    assert results[1].report.scope == "MOCK-OEM-B"
    assert results[0].report.input_sha256 != results[1].report.input_sha256
    assert results[0].report.output_sha256 != results[1].report.output_sha256
    events = AuditLogger.jsonl(path).query_by(scenario=SCENARIO, action=ACTION)
    assert len(events) == 2
    chain = AuditLogger.jsonl(path).verify_chain()
    assert chain.ok is True and chain.total == 2


def test_equal_issue_counts_with_changed_input_have_different_hashes(tmp_path):
    path = tmp_path / "changed-value.jsonl"
    cases = eight_cases()
    first = run_synthetic_evidence(cases["C01"], actor="synthetic-test-operator", audit=AuditLogger.jsonl(path))
    cases["C01"]["measurements"][0]["raw_value"] = 10.25
    second = run_synthetic_evidence(cases["C01"], actor="synthetic-test-operator", audit=AuditLogger.jsonl(path))
    assert len(first.report.issues) == len(second.report.issues)
    assert first.report.input_sha256 != second.report.input_sha256
    assert first.report.output_sha256 != second.report.output_sha256
    events = AuditLogger.jsonl(path).query_by(scenario=SCENARIO, action=ACTION)
    assert len(events) == 2
    assert events[0]["content_hash"] != events[1]["content_hash"]
    chain = AuditLogger.jsonl(path).verify_chain()
    assert chain.ok is True and chain.total == 2


@pytest.mark.parametrize("actor", ["", "   ", None])
def test_missing_actor_fails_before_returning_a_complete_run(tmp_path, actor):
    with pytest.raises(AuditRequiredError, match="非空actor"):
        run_synthetic_evidence(
            eight_cases()["C01"], actor=actor,
            audit=AuditLogger.jsonl(tmp_path / "actor.jsonl"),
        )


def test_missing_or_non_jsonl_audit_fails_closed(tmp_path):
    with pytest.raises(AuditRequiredError, match="JsonlSink"):
        run_synthetic_evidence(eight_cases()["C01"], actor="synthetic-test-operator", audit=None)
    with pytest.raises(AuditRequiredError, match="JsonlSink"):
        run_synthetic_evidence(
            eight_cases()["C01"], actor="synthetic-test-operator",
            audit=AuditLogger(object()),
        )


def test_jsonl_write_failure_does_not_return_success(tmp_path):
    blocked = tmp_path / "audit-is-a-directory.jsonl"
    blocked.mkdir()
    logger = AuditLogger.jsonl(blocked)  # 构造不写文件；失败在 record/write 阶段。
    with pytest.raises(OSError):
        run_synthetic_evidence(eight_cases()["C01"], actor="synthetic-test-operator", audit=logger)
```

同一测试文件再加入以下完整输入失败用例；都在 `freeze_bundle` 边界拒绝，不写审计成功行：

```python
from copy import deepcopy

from o4_maintenance_evidence.models import InvalidEvidenceInput, freeze_bundle


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_json_numbers_are_rejected(bad_value):
    case = deepcopy(eight_cases()["C01"])
    case["measurements"][0]["raw_value"] = {"nested": [bad_value]}
    with pytest.raises(InvalidEvidenceInput, match="NaN/Inf"):
        freeze_bundle(case)


def test_invalid_identity_scope_and_missing_value_field_are_rejected(tmp_path):
    base = eight_cases()["C01"]
    cases = []
    non_synthetic = deepcopy(base)
    non_synthetic["synthetic"] = False
    cases.append(non_synthetic)
    missing_bundle_id = deepcopy(base)
    del missing_bundle_id["bundle_id"]
    cases.append(missing_bundle_id)
    missing_scope = deepcopy(base)
    del missing_scope["scope"]
    cases.append(missing_scope)
    unsupported_schema = deepcopy(base)
    unsupported_schema["schema_version"] = "o4-evidence-unknown"
    cases.append(unsupported_schema)
    wrong_nested_scope = deepcopy(base)
    wrong_nested_scope["measurements"][0]["scope"] = "MOCK-OEM-B"
    cases.append(wrong_nested_scope)
    missing_raw_field = deepcopy(base)
    del missing_raw_field["measurements"][0]["raw_value"]
    cases.append(missing_raw_field)
    empty_source_ref = deepcopy(base)
    empty_source_ref["assets"][0]["source_ref"] = " "
    cases.append(empty_source_ref)

    for bad in cases:
        with pytest.raises(InvalidEvidenceInput):
            run_synthetic_evidence(
                bad, actor="synthetic-test-operator",
                audit=AuditLogger.jsonl(tmp_path / "invalid.jsonl"),
            )
    assert not (tmp_path / "invalid.jsonl").exists()


def test_missing_revision_or_unit_is_reported_without_defaulting():
    missing_revision = deepcopy(eight_cases()["C01"])
    missing_revision["measurements"][0]["source_revision"] = None
    revision_issues = check_structure(freeze_bundle(missing_revision))
    assert "source_revision_missing" in {issue.code for issue in revision_issues}

    missing_unit = deepcopy(eight_cases()["C01"])
    missing_unit["measurements"][0]["declared_unit"] = ""
    unit_issues = check_structure(freeze_bundle(missing_unit))
    assert "unit_declaration_missing" in {issue.code for issue in unit_issues}
```

以上是純 synthetic `tmp_path`；既不访问真实数据，也不将 invalid input 解释成设备故障。`None` 与 `0` 的不同语义由 Task 2 的具名用例验证。

## Task 4：严格测试引导、完整回归执行与证据包

**文件：**创建 `tests/conftest.py`，最终审查白名单和产物边界。

`tests/conftest.py` 必须逐字按当前 bootstrap 唯一样板：

```python
from pathlib import Path
import sys

_HERE = Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        sys.path.insert(0, str(_p / "5-平台底座" / "zhuopin_platform"))
        break
from zhuopin_platform.bootstrap import ensure_paths  # noqa: E402
ensure_paths(__file__, _HERE.parent.parent, strict=True)  # noqa: E402
```

实现前逐条核正式 tasks 2.1–2.6，测试后只消费 Stage0 准备/实现证据，不改 formal tasks。实际实现 diff 仅可包含白名单八文件。平台 audit 包只读复用；不能新增共享平台模型或更改其 JSONL 格式。

未来由父会话给出 Native 隔离返回的 `CandidateRoot`、当前主仓证据根 `EvidenceRoot`、本轮 fresh UUID 和当次 Probe 得到的 Python 路径。以下是单独 O4 子项目命令示例；执行前确认 `CandidateRoot` 是该隔离树，`EvidenceRoot` 是主仓，不能拿主仓根作为测试 cwd，也不能把多个场景测试混在同一 pytest 命令：

```powershell
param([Parameter(Mandatory = $true)][string]$CandidateRoot)
$o4ResolvedRoot = (Resolve-Path -LiteralPath $CandidateRoot -ErrorAction Stop).Path
$o4CandidateHead = (& git -C $o4ResolvedRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $o4CandidateHead -ne '28337c0ebb52afdbf61e955ecdbc22d151bcd185') { throw 'O4 candidate HEAD differs from approved start' }
$o4RunDir = Join-Path 'C:/Dev/zhuopin-ai/reports/o4-single-class-1010' ([guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $o4RunDir -ErrorAction Stop | Out-Null
Push-Location (Join-Path $o4ResolvedRoot '4-数字员工/运营部/O4-设备预测性维护')
try {
    & 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -B -m pytest -q -ra -p no:cacheprovider 'tests/test_stage0.py' --basetemp (Join-Path $o4RunDir 'basetemp') --junitxml (Join-Path $o4RunDir 'junit.xml') 1> (Join-Path $o4RunDir 'stdout.log') 2> (Join-Path $o4RunDir 'stderr.log')
    $o4TestExit = $LASTEXITCODE
    [IO.File]::WriteAllText((Join-Path $o4RunDir 'exit-code.txt'), [string]$o4TestExit, [Text.UTF8Encoding]::new($false))
}
finally { Pop-Location }
if ($o4TestExit -ne 0) { throw "O4 Stage0 pytest failed with exit code $o4TestExit; preserve $o4RunDir" }
```

执行前 `CandidatePython` 必须来自当次 `invoke.ps1 -Mode Probe` 的隔离 runtime 解析结果，不读取或复制 `runtime.local.json` 内容；`RunUuid` 由父会话在本次执行时新生成，不能重用。验证报告四件及文件 SHA、`git status --short --ignored` 仅限白名单与该 UUID 报告；仅在这些证据成功后独立 reviewer 再审。测试失败、JSONL 断链或白名单外变化时停止交付，不进行自动修复、归档或发布。

**真实报告路径忽略证据（只读核验）：**`git check-ignore -v 'reports/o4-stage0-1010/implementation-plan.md'` 与 `git check-ignore -v 'reports/o4-single-class-1010/22222222-2222-4222-8222-222222222222/stdout.log'` 均返回 `.gitignore:59:**/reports/`。后续真实 run 使用新 UUID；上述 fake UUID 仅用于证明规则匹配，不创建该目录或文件。

## 退出条件与业务阶段边界

- Stage0 2M 只在八例及非法/审计矩阵完成、真实 JSONL 可读回且链 `ok=True`、issue/hash/immutability 证据齐全后申请核验；不得把过去 `actual_run=null` 当通过。
- 所有输出仍是 synthetic `not_evaluated`，所有预测与业务建议仍为空；不宣称预测效果、设备健康、可维护性、停机改善、备件可用性、OEE 或专业验收。
- 不要求 Owner/backup/维护工程师姓名来阻断本次纯技术 mock；但也不虚构姓名或专业签认。Owner/backup、类别/资产、真实资料权限、阈值/标签和专业验收分别仍是 Stage1/Stage2 前置。
- Tasks 1.5 与 Stage0 2.1–2.6 未经独立任务/证据审核不得打勾；设计批准不是具体执行批准；只有本人明确批准本件八路径/定向测试/Native副作用后才开始候选实施。真实source/专业签认/部署/归档各自另审。
- 即使首个 Stage0 交付闭合，也不代表完整 O4 试点完工；保留正式 tasks 后续阶段，不归档全业务 change，不同步主 spec，不启用 IoT/PLC、告警、工单、采购、停机、服务或外发。

## 计划自检

- Spec coverage：身份/冻结/原值/冲突/关联/scope/hashes/not_evaluated/audit fail-closed 对应 Tasks 1–3；Native 隔离/白名单/JSONL/JUnit 证据对应 Task 4。
- Placeholder scan：计划不以 TODO、TBD、泛化“补错误处理”或省略号替代实现步骤；实施 API、代码基线、八例合成 builder、核心断言和执行命令均已列出。
- Type consistency：`check_structure` 返回 `EvidenceIssue`，由 `Stage0Report.issues` 消费；`run_synthetic_evidence` 返回 `Stage0Run`；审计链检查使用 `ChainVerifyResult.ok/total`。
- 未纳入五类额外输入契约：真实来源数据、实际类别选择、阈值/预测输出、同scope多类设备准入、生产审计留存策略。它们属于明确后续阶段，不由Stage0默认值代替。

## 根审新增测试（仍纳入唯一test_stage0.py）

```python

def test_asset_revision_is_preserved_and_changes_input_hash():
    case = eight_cases()["C01"]
    first = freeze_bundle(case)
    case["assets"][0]["source_revision"] = "r2"
    second = freeze_bundle(case)
    assert first.assets[0].source_revision == "r1"
    assert second.assets[0].source_revision == "r2"
    assert canonical_input_sha256(first) != canonical_input_sha256(second)


def test_conflicting_event_assets_are_order_independent_and_audited(tmp_path):
    from o4_cases import asset
    case = eight_cases()["C06"]
    case["assets"].append(asset("MOCK-ASSET-OTHER"))
    case["measurements"][1]["asset_id"] = "MOCK-ASSET-OTHER"
    reversed_case = {**case, "measurements": list(reversed(case["measurements"]))}
    audit = AuditLogger.jsonl(tmp_path / "order-conflict.jsonl")
    first = run_synthetic_evidence(case, actor="synthetic-test-operator", audit=audit)
    second = run_synthetic_evidence(reversed_case, actor="synthetic-test-operator", audit=audit)
    assert first.report.input_sha256 == second.report.input_sha256
    assert first.report.issues == second.report.issues
    assert first.report.output_sha256 == second.report.output_sha256
    assert "source_event_asset_conflict" in {issue.code for issue in first.report.issues}
    from collections import Counter
    events = AuditLogger.jsonl(audit.sink.log_path).query_by(scenario=SCENARIO, action=ACTION)
    assert len(events) == 2
    for event, result in zip(events, (first, second), strict=True):
        report = result.report
        counts = dict(sorted(Counter(issue.code for issue in report.issues).items()))
        assert counts["source_event_asset_conflict"] == 1
        assert event["decision"]["issue_counts"] == counts
        assert event["decision"]["input_sha256"] == report.input_sha256
        assert event["decision"]["output_sha256"] == report.output_sha256
        assert event["content_hash"] == report.output_sha256
    chain = AuditLogger.jsonl(audit.sink.log_path).verify_chain()
    assert chain.ok is True and chain.total == 2
```
