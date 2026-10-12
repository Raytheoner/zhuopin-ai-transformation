# FI14 PC端 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在仅合成 JSON 输入的 MOCK 模式下交付 FI14 PC 闭环：来源校验、同截止勾稽与 unknown、只读付款草稿、带理由的新人工演示版本、历史比较、受控导出及可验证审计。

**Architecture:** 建立独立 Flask 场景包和 `/finance/fi14` Blueprint，领域计算与存储完全确定性，不连接共享平台之外的财务系统。场景结果对象保存受权限控制的完整财务值；平台 `AuditLogger` 仅接收状态、opaque IDs、hash 和非敏感原因码。所有业务对象不可变，先写未提交对象并核对 audit 链，再原子发布可见引用。

**Tech Stack:** Python（仓库隔离 runtime）、Flask、stdlib `decimal.Decimal`、canonical UTF-8 JSON、pytest、现有 `AuditEvent`/`AuditLogger`。

**Spec:** `reports/pc-mvp-1012/v2-review/fi14/design.md`、`specs/fi14-payment-plan-pc-mvp/spec.md`、`docs/superpowers/specs/2026-10-12-fi14-pc-mvp-technical-addendum.md`。设计批准绑定 design HEAD `cd1c154800945f6fe6c756bd60474bb8fe082783` / SHA256 `73a79dae37c75e8d09f862655212deae645fff4715cd2c72b109b554bcc47e37`；附录 v1 SHA256 `5f022c8ad5fbd00603e4996b70ab88c7425a0f30f2e0546c3c3c199d99959c63`。该计划不代表产品实现或测试批准。

## Global Constraints

- 本计划未来实现严格限于下列17个文件；不改现存 intent、共享平台、FI2/FI3、旧四件、网关、部署脚本或其它场景。
- 首期只接受 `mode="MOCK"` 的版本化 UTF-8 JSON。缺失 mode 或任何非 `MOCK` 模式必须拒绝；不支持 CSV/XLSX、OCR、真实脱敏源、ERP、银行或外部 API。
- FI14-G01 至 G06 全部保持 `PENDING`；synthetic fixture 不进入 CriteriaRegistry，不作为业务规则签认或付款依据。
- 截止日、组织和币种一致才可比较；异币种不合计；金额只以十进制字符串解析为 `Decimal`，禁止 float；缺值为 `UNKNOWN`，绝不补零。
- 输出只表示 `MOCK`/`DRAFT`，不产生审批、付款、记账、供应商通知或 ERP 写回能力。
- 只复用现存 Flask app factory / Blueprint 及平台 audit 接口；不新起端口、不改 SSO、网关、平台权限或现有 auth。
- `AccessDecisionProvider` 未注入、身份或决策来源未知时拒绝。合成身份只能由测试显式注入；不得信任请求 header 或共享口令作为真实组织权限。
- audit 仅写 `scenario/action/actor/automation_level/operation_id/run_id/plan_id/status/version/hash/reason_code` 等非敏感值。金额、余额、原单、附件、before/after 金额及未脱敏理由只存在受控场景结果对象；`decision` 仅状态/opaque IDs/hash，`override_reason` 为空或非敏感原因码，`data_sources/report_path/error/oem_context` 不得携带敏感原值。
    - audit 或提交失败不得确认成功或发布对象；重试按 canonical `idempotency_key -> operation_id` 恢复同一操作，不重复创建版本。失败对象保留，不增加清理/删除逻辑。
- 未来执行使用隔离 Python `C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe`，不对全局 site-packages 做 editable 安装。bootstrap 复用唯一现存 stub，不复制引导算法。
- 下列测试代码是未来实现内容，本轮不运行。仅在未来授权后，从 FI14 子项目根目录执行 `python -m pytest -q --tb=short --junit-xml="pytest-result.xml"`，测试范围聚焦五个目标测试文件。
- Guardian 应在正式阶段使用显式 `gpt-6-luna`；其只做独立审查，不自行 commit/push。CI 与 review 完成不授权 ff、真实取数、生产、付款或外发。
- 未来唯一实现 cwd 为 `C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-fi14/zhuopin-ai/4-数字员工/财务部/FI14-应付账龄与付款计划分析`。所有命令通过 `& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" ...` 调用；不得在主工作树执行计划内实现或测试。

## Review Focus

- 输入 JSON 有重复键、额外字段、畸形 UTF-8、路径/宏/附件等执行载荷时，拒绝且不产生任何可见结果。
- 同一快照的截止日、组织、币种或覆盖不一致时必须 `NOT_COMPARABLE`/缺口；unknown 不得伪装为零或可付金额。
- audit 的任一文本字段、嵌套扩展字段、异常消息和拒绝消息均不得泄露财务原值或请求体。
- 同幂等键并发导入、旧父版本并发调整、audit/原子发布中断时，不出现重复版本、覆盖或半提交可见对象。
- 未注入/未知身份不得读取、计算、调整、比较或导出；客户端 header 即使伪造合成身份也不得改变决策。

---

## 文件责任（严格17文件）

| 文件 | 单一责任 |
|---|---|
| `4-数字员工/财务部/FI14-应付账龄与付款计划分析/pyproject.toml` | FI14 包元数据及仓内既有 Flask 依赖；不做全局安装 |
| `4-数字员工/财务部/FI14-应付账龄与付款计划分析/fi14_payment_plan/__init__.py` | 包版本与公开符号 |
| `4-数字员工/财务部/FI14-应付账龄与付款计划分析/fi14_payment_plan/models.py` | 不可变领域类型、状态枚举、结果/差异结构 |
| `4-数字员工/财务部/FI14-应付账龄与付款计划分析/fi14_payment_plan/config.py` | MOCK-only 配置、schema 版本和场景结果/audit 根路径 |
| `4-数字员工/财务部/FI14-应付账龄与付款计划分析/fi14_payment_plan/sources.py` | JSON 字节解析、严格字段合同与快照标识 |
| `4-数字员工/财务部/FI14-应付账龄与付款计划分析/fi14_payment_plan/engine.py` | 勾稽、unknown、草稿与人工演示版本的确定性规则 |
| `4-数字员工/财务部/FI14-应付账龄与付款计划分析/fi14_payment_plan/storage.py` | canonical codec、内容 hash、幂等、锁、提交屏障和历史读取 |
| `4-数字员工/财务部/FI14-应付账龄与付款计划分析/fi14_payment_plan/access.py` | 默认拒绝的可信授权协议与合成测试身份 |
| `4-数字员工/财务部/FI14-应付账龄与付款计划分析/fi14_payment_plan/webapp.py` | Flask factory、Blueprint、请求验证及审计投影 |
| `4-数字员工/财务部/FI14-应付账龄与付款计划分析/fi14_payment_plan/templates/index.html` | MOCK 导入、勾稽、草稿、调整和历史操作视图 |
| `4-数字员工/财务部/FI14-应付账龄与付款计划分析/data/mock/fi14_bundle.json` | 全合成且显式标记的示范输入 |
| `4-数字员工/财务部/FI14-应付账龄与付款计划分析/tests/conftest.py` | 复用现存唯一 bootstrap stub，strict=True |
| `4-数字员工/财务部/FI14-应付账龄与付款计划分析/tests/test_sources.py` | 输入合同/字段/范围/截止/币种/覆盖测试 |
| `4-数字员工/财务部/FI14-应付账龄与付款计划分析/tests/test_engine.py` | 同截止勾稽、unknown、草稿与调整测试 |
| `4-数字员工/财务部/FI14-应付账龄与付款计划分析/tests/test_storage.py` | canonical、幂等、版本冲突、失败屏障测试 |
| `4-数字员工/财务部/FI14-应付账龄与付款计划分析/tests/test_access.py` | 默认拒绝与显式合成身份边界测试 |
| `4-数字员工/财务部/FI14-应付账龄与付款计划分析/tests/test_webapp.py` | 页面流程、审计、拒绝和导出集成测试 |

## 精确领域接口

以下接口作为跨任务契约，字段在实现中不得用无类型字典替代。所有 dataclass 均 `frozen=True, slots=True`。

```python
class Mode(str, Enum):
    MOCK = "MOCK"

class AgingStatus(str, Enum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    NOT_COMPARABLE = "NOT_COMPARABLE"

class PlanStatus(str, Enum):
    PENDING_RULES = "PENDING_RULES"
    DRAFT = "DRAFT"

class AccessAction(str, Enum):
    IMPORT = "import"
    COMPUTE = "compute"
    VIEW = "view"
    ADJUST = "adjust"
    EXPORT = "export"

@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str

@dataclass(frozen=True, slots=True)
class Manifest:
    mode: Mode
    schema_version: str
    source_id: str
    source_version: str
    source_sha256: str
    extracted_at_utc: datetime
    org_scope: str
    as_of_date: date
    currencies: tuple[str, ...]
    coverage: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class APLine:
    line_id: str
    supplier_ref: str
    amount: Money | None
    currency: str
    due_date: date | None
    paid_status: str | None
    source_ref: str
    coverage_status: str
    fi3_risk_status: str

@dataclass(frozen=True, slots=True)
class AgingTotal:
    currency: str
    ap_total: Decimal | None
    standard_total: Decimal | None
    difference: Decimal | None
    status: AgingStatus
    missing_fields: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class StandardAging:
    source_id: str
    source_version: str
    source_sha256: str
    org_scope: str
    as_of_date: date
    currencies: tuple[str, ...]
    coverage: tuple[str, ...]
    bucket_totals: tuple[tuple[str, str, Decimal], ...]  # currency,bucket,amount

@dataclass(frozen=True, slots=True)
class Bundle:
    manifest: Manifest
    ap_lines: tuple[APLine, ...]
    standard_aging: StandardAging | None
    funds_by_currency: tuple[tuple[str, Decimal | None], ...]
    constraints_status: str

@dataclass(frozen=True, slots=True)
class PlanRow:
    line_id: str
    supplier_ref: str
    amount: Money | None
    currency: str
    due_date: date | None
    paid_status: str | None
    source_ref: str
    fi3_risk_status: str
    coverage_status: str
    disposition: str
    reason_code: str

@dataclass(frozen=True, slots=True)
class PlanVersion:
    plan_id: str
    version: int
    parent_version: int | None
    run_id: str
    status: PlanStatus
    mode: Mode
    rows: tuple[PlanRow, ...]
    changed_fields: tuple[str, ...]
    reason_code: str | None
    reason_text: str | None
    # run_id resolves to the immutable stored Bundle, which retains manifest,
    # source comparator, funds snapshot, and constraints status.

@dataclass(frozen=True, slots=True)
class Actor:
    actor_id: str
    org_scope: str
    synthetic: bool

@dataclass(frozen=True, slots=True)
class AccessDecision:
    allowed: bool
    actor_id: str | None
    org_scope: str | None
    source_version: str | None
    reason_code: str

class AccessDecisionProvider(Protocol):
    def decide(self, actor: Actor | None, org_scope: str,
               object_id: str | None, action: AccessAction) -> AccessDecision: ...

def parse_bundle(raw: bytes) -> Bundle: ...
def canonical_json(value: object) -> bytes: ...
def content_hash(value: object) -> str: ...
def import_key(manifest: Manifest) -> str: ...
def run_id_for_import(manifest: Manifest) -> str: ...
def reconcile(bundle: Bundle) -> tuple[AgingTotal, ...]: ...
def create_draft(run_id: str, bundle: Bundle,
                 totals: tuple[AgingTotal, ...]) -> PlanVersion: ...
def adjust_demo(parent: PlanVersion, *, expected_parent_version: int,
                changed_rows: tuple[tuple[str, str], ...], actor: Actor,
                reason_code: str, reason_text: str) -> PlanVersion: ...
class ResultStore(Protocol):
    def commit(self, *, operation_id: str, idempotency_key: str,
               payload: object, audit_event: AuditEvent) -> str: ...
    def commit_version(self, *, plan_id: str, expected_parent_version: int,
                       operation_id: str, idempotency_key: str,
                       payload: object, audit_event: AuditEvent) -> str: ...
    def register_parent(self, plan_id: str, current_version: int) -> None: ...
    def visible_ids(self) -> tuple[str, ...]: ...
    def failed_operation_exists(self, operation_id: str) -> bool: ...
    def compare_history(self, left_id: str, right_id: str) -> tuple[tuple[str, str], ...]: ...
    def get(self, object_id: str) -> object: ...
    def get_run(self, run_id: str) -> Bundle: ...
    def history(self, run_id: str) -> tuple[object, ...]: ...
```

JSON schema `fi14_mock_bundle/v1` 必需键为 `mode,schema_version,source_id,source_version,extracted_at_utc,org_scope,as_of_date,currencies,coverage,ap_lines,standard_aging,funds,constraints`；每个金额必须是十进制字符串，缺失金额用 JSON null 表示并解析为 `APLine.amount=None`，不得构造 `Money(None)`。`standard_aging` 独立包含自身 `source_id,source_version,source_sha256,org_scope,as_of_date,currencies,coverage,bucket_totals`；比较必须使用两侧元数据，不能由 AP manifest 推断 comparator 截止/组织/币种。标准报表已给的 bucket totals 只读保存和展示；G01/G02 未签仅禁止自行分桶。每个 AP 行保留 source_ref、coverage_status、fi3_risk_status（无证据时 `UNKNOWN`）。资金及限制保留 unknown。资金未知或 G03/G04 未签时不得排序、称最优。source hash 由原始上传字节 SHA-256 取得。

Persisted business result is exactly `schema_version="fi14_result/v1"` and uses `run_id` plus positive integer `plan_version` as its identity. It contains `mode`, immutable AP manifest, complete normalized `ap_lines`, standard comparator metadata and bucket values, per-currency reconciliation, funds and constraints states, and PlanVersion rows/reason code. `get_run(run_id)` reconstructs the immutable `Bundle` from base version `1.json`; later plan versions reference this run snapshot and cannot replace it. `RESULT_ROOT` resolves to `reports/fi14_pc_mvp`; each business version must be published at `reports/fi14_pc_mvp/<run_id>/<plan_version>.json`. Internal operation journals and pending bytes live under `reports/fi14_pc_mvp/.control/`, and are never exposed as business result paths or exports.

## Task 1: 建立类型、MOCK输入合同及场景骨架

**Files:**
- Create: `4-数字员工/财务部/FI14-应付账龄与付款计划分析/pyproject.toml`
- Create: `4-数字员工/财务部/FI14-应付账龄与付款计划分析/fi14_payment_plan/__init__.py`
- Create: `4-数字员工/财务部/FI14-应付账龄与付款计划分析/fi14_payment_plan/models.py`
- Create: `4-数字员工/财务部/FI14-应付账龄与付款计划分析/fi14_payment_plan/config.py`
- Create: `4-数字员工/财务部/FI14-应付账龄与付款计划分析/fi14_payment_plan/sources.py`
- Create: `4-数字员工/财务部/FI14-应付账龄与付款计划分析/data/mock/fi14_bundle.json`
- Create: `4-数字员工/财务部/FI14-应付账龄与付款计划分析/tests/conftest.py`
- Create: `4-数字员工/财务部/FI14-应付账龄与付款计划分析/tests/test_sources.py`

**Step 1: Future test — reject non-MOCK and noncanonical amounts.** Add to `tests/test_sources.py`:

```python
import json
from decimal import Decimal
import pytest
from fi14_payment_plan.sources import parse_bundle, BundleError

def bundle_bytes(**overrides):
    value = {
        "mode": "MOCK", "schema_version": "fi14_mock_bundle/v1",
        "source_id": "synthetic-ap-01", "source_version": "1",
        "extracted_at_utc": "2026-10-12T00:00:00Z", "org_scope": "SYNTH-ORG",
        "as_of_date": "2026-09-30", "currencies": ["CNY"],
        "coverage": ["ap_lines", "standard_aging"],
        "ap_lines": [{"line_id": "L1", "supplier_ref": "SYNTH-S1",
                       "amount": "125.10", "currency": "CNY",
                       "due_date": None, "paid_status": "UNKNOWN",
                       "source_ref": "ap:L1", "coverage_status": "COMPLETE",
                       "fi3_risk_status": "UNKNOWN"}],
        "standard_aging": {"source_id":"synthetic-standard", "source_version":"1",
                           "source_sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                           "as_of_date": "2026-09-30", "org_scope": "SYNTH-ORG",
                           "currencies": ["CNY"], "coverage": ["standard_aging"],
                           "bucket_totals": [{"currency":"CNY", "bucket":"UNCLASSIFIED_SOURCE_BUCKET",
                                              "amount":"125.10"}]},
        "funds": {"status": "UNKNOWN", "amount": None},
        "constraints": {"status": "SYNTHETIC_DEMO_ONLY"},
    }
    value.update(overrides)
    return json.dumps(value, separators=(",", ":")).encode("utf-8")

def test_accepts_mock_decimal_without_float_conversion():
    bundle = parse_bundle(bundle_bytes())
    assert bundle.manifest.mode.value == "MOCK"
    assert bundle.ap_lines[0].amount.amount == Decimal("125.10")

@pytest.mark.parametrize("mode", [None, "MASKED", "PRODUCTION", "mock"])
def test_rejects_any_mode_other_than_exact_mock(mode):
    data = {"mode": mode}
    with pytest.raises(BundleError):
        parse_bundle(bundle_bytes(**data))

@pytest.mark.parametrize("amount", [125.1, "NaN", "Infinity", "1e3", "-1.00"])
def test_rejects_float_nonfinite_exponent_and_negative_amount(amount):
    with pytest.raises(BundleError):
        parse_bundle(bundle_bytes(ap_lines=[{
            "line_id": "L1", "supplier_ref": "SYNTH-S1", "amount": amount,
            "currency": "CNY", "due_date": None, "paid_status": "UNKNOWN",
            "source_ref":"ap:L1", "coverage_status":"COMPLETE", "fi3_risk_status":"UNKNOWN"}]))

def test_rejects_unknown_keys_and_duplicate_json_keys():
    with pytest.raises(BundleError):
        parse_bundle(bundle_bytes(unexpected="value"))
    raw = b'{"mode":"MOCK","mode":"PRODUCTION"}'
    with pytest.raises(BundleError):
        parse_bundle(raw)

def test_rejects_invalid_utf8_and_path_like_payload():
    with pytest.raises(BundleError):
        parse_bundle(b"\xff")
    with pytest.raises(BundleError):
        parse_bundle(bundle_bytes(ap_lines=[{
            "line_id": "../outside", "supplier_ref": "SYNTH-S1", "amount": "1",
            "currency": "CNY", "due_date": None, "paid_status": "UNKNOWN",
            "source_ref":"ap:L1", "coverage_status":"COMPLETE", "fi3_risk_status":"UNKNOWN"}]))
```

**Step 2: Future check — confirm the source tests fail before implementation.** Run from the exact bound worktree FI14 root `C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-fi14/zhuopin-ai/4-数字员工/财务部/FI14-应付账龄与付款计划分析`:

```powershell
Set-Location -LiteralPath "C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-fi14/zhuopin-ai/4-数字员工/财务部/FI14-应付账龄与付款计划分析"
& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest tests/test_sources.py -q
```

Expected: collection fails because `fi14_payment_plan.sources` is not implemented.

**Step 3: Implement the minimal typed source contract.** `models.py` defines the enums/dataclasses above. Implement the parser's rejection primitives exactly as follows; schema-specific constructors then populate `Bundle` only after field validation:

```python
import json
import re
from decimal import Decimal, InvalidOperation

AMOUNT_RE = re.compile(r"^(0|[1-9][0-9]*)(\.[0-9]{1,4})?$")

def _pairs_no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise BundleError("DUPLICATE_JSON_KEY")
        out[key] = value
    return out

def _reject_float(value):
    raise BundleError("JSON_FLOAT_FORBIDDEN")

def _decimal_or_unknown(value):
    if value is None:
        return None
    if not isinstance(value, str) or not AMOUNT_RE.fullmatch(value):
        raise BundleError("INVALID_DECIMAL_STRING")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise BundleError("INVALID_DECIMAL_STRING") from exc
    if not amount.is_finite() or amount < 0:
        raise BundleError("INVALID_AMOUNT")
    return amount

def parse_bundle(raw: bytes) -> Bundle:
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs_no_duplicates,
                         parse_float=_reject_float, parse_constant=_reject_float)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleError("INVALID_JSON") from exc
    _require_exact_keys(obj, BUNDLE_KEYS)
    if obj["mode"] != "MOCK" or obj["schema_version"] != "fi14_mock_bundle/v1":
        raise BundleError("MOCK_SCHEMA_REQUIRED")
    manifest = _parse_manifest(obj, sha256(raw).hexdigest())
    lines = tuple(_parse_ap_line(item, manifest) for item in _require_list(obj["ap_lines"]))
    standard = _parse_standard_aging(obj["standard_aging"])
    funds = _parse_funds(obj["funds"], manifest.currencies)
    return Bundle(manifest, lines, standard, funds, _parse_constraints_status(obj["constraints"]))
```

`_require_exact_keys` raises on unknown or missing keys. `_parse_standard_aging` independently validates its own source ID/version/hash, organization, cutoff, currencies, coverage and Decimal-string bucket amounts; it never copies those values from the AP manifest. `_parse_ap_line` preserves `source_ref`, `coverage_status`, `fi3_risk_status`, `due_date`, and `paid_status`; null amount becomes `None`, otherwise `Money(decimal, currency)`. `Bundle` preserves funds by currency (including `None`) and constraints status. Validate currency `[A-Z]{3}`, hash lowercase 64 hex, timezone-aware UTC timestamps, unique currency lists, and line IDs without path separators. `config.py` exports `SCHEMA_VERSION`, `RESULT_ROOT`, `AUDIT_PATH`, `load_config(env)`; missing/other `FI14_MODE` raises `ValueError`. `__init__.py` exports `__version__ = "0.1.0"`; `pyproject.toml` declares metadata and Flask version consistent with existing FI3 manifest, with no editable global install.

`tests/conftest.py` must reproduce the approved FI3 bootstrap sample, changing only the resulting scenario package names as needed. The entire bootstrap block is:

```python
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        sys.path.insert(0, str(_p / "5-平台底座" / "zhuopin_platform"))
        break
from zhuopin_platform.bootstrap import ensure_paths  # noqa: E402
ensure_paths(__file__, _HERE.parent.parent, strict=True)  # noqa: E402
```

来源：`4-数字员工/财务部/FI3-付款申请自动校验/tests/conftest.py` 第8–18行；`ensure_paths` 实现位于 `5-平台底座/zhuopin_platform/zhuopin_platform/bootstrap.py`，只调用，不复制算法。Fixture包含合成 IDs、AP evidence/risk fields、同截止标准桶、funds `UNKNOWN`、constraints `SYNTHETIC_DEMO_ONLY`。

**Step 4: Future verification.** Re-run the command in Step 2; expected: all source tests pass. Do not run it in this plan-writing phase.

**Step 5: Future review checkpoint.** Inspect `git diff --check` and confirm this task created only its eight listed files; no commit is part of the plan.

## Task 2: Deterministic勾稽、unknown及草稿/演示版本

**Files:**
- Create: `4-数字员工/财务部/FI14-应付账龄与付款计划分析/fi14_payment_plan/engine.py`
- Create: `4-数字员工/财务部/FI14-应付账龄与付款计划分析/tests/test_engine.py`

**Step 1: Future test — same-cutoff comparison and unknown behavior.** Add to `tests/test_engine.py`:

```python
from datetime import date, datetime, timezone
from decimal import Decimal
from fi14_payment_plan.models import (Manifest, Mode, APLine, Money, AgingStatus,
    PlanStatus, Actor, Bundle, StandardAging)
from fi14_payment_plan.engine import (reconcile, create_draft, adjust_demo, EngineError,
    import_key, run_id_for_import)
import pytest

def manifest(as_of=date(2026, 9, 30), org="SYNTH-ORG", currencies=("CNY",)):
    return Manifest(Mode.MOCK, "fi14_mock_bundle/v1", "s1", "1", "a"*64,
                    datetime(2026,10,12,tzinfo=timezone.utc), org, as_of,
                    currencies, ("ap_lines", "standard_aging"))

def line(amount=Decimal("10.25"), currency="CNY"):
    value = None if amount is None else Money(amount, currency)
    return APLine("L1", "SYNTH-S1", value, currency, None, "UNKNOWN", "ap:L1", "COMPLETE", "UNKNOWN")

def standard(org, as_of, currencies, total):
    return StandardAging("std-1", "1", "b"*64, org, as_of, currencies,
                         ("standard_aging",), ((currencies[0], "UNCLASSIFIED_SOURCE_BUCKET", total),))

def test_matching_scope_cutoff_and_currency_reconciles_exact_decimal():
    bundle = Bundle(manifest(), (line(),), standard("SYNTH-ORG", date(2026,9,30), ("CNY",), Decimal("10.20")), (), "SYNTHETIC_DEMO_ONLY")
    result = reconcile(bundle)
    assert result[0].difference == Decimal("0.05")
    assert result[0].status is AgingStatus.READY

@pytest.mark.parametrize("changed", [
    {"as_of": date(2026, 9, 29)}, {"org": "OTHER"}, {"currencies": ("USD",)}])
def test_mismatch_never_produces_comparable_totals(changed):
    ap = manifest(**changed)
    bundle = Bundle(ap, (line(),), standard("SYNTH-ORG", date(2026,9,30), ("CNY",), Decimal("10.25")), (), "SYNTHETIC_DEMO_ONLY")
    result = reconcile(bundle)
    assert result[0].status is AgingStatus.NOT_COMPARABLE
    assert result[0].difference is None

def test_missing_comparator_and_missing_amount_remain_unknown_not_zero():
    bundle = Bundle(manifest(), (line(None),), None, (("CNY", None),), "UNKNOWN")
    result = reconcile(bundle)
    assert result[0].status is AgingStatus.PARTIAL
    assert result[0].ap_total is None
    assert result[0].standard_total is None
    assert result[0].difference is None

def test_unruled_draft_is_pending_and_mock_adjustment_adds_version():
    bundle = Bundle(manifest(), (line(),), standard("SYNTH-ORG", date(2026,9,30), ("CNY",), Decimal("10.25")), (("CNY", None),), "SYNTHETIC_DEMO_ONLY")
    aging = reconcile(bundle)
    draft = create_draft("run-1", bundle, aging)
    assert draft.status is PlanStatus.PENDING_RULES
    assert len(draft.rows) == 1
    assert draft.rows[0].currency == "CNY"
    assert draft.rows[0].due_date is None and draft.rows[0].fi3_risk_status == "UNKNOWN"
    actor = Actor("synthetic-reviewer", "SYNTH-ORG", True)
    updated = adjust_demo(draft, expected_parent_version=1,
                          changed_rows=(("L1", "DEMO_INCLUDE"),), actor=actor,
                          reason_code="DEMO_REASON", reason_text="合成演示")
    assert updated.version == 2 and updated.parent_version == 1
    assert updated.mode is Mode.MOCK
    assert updated.reason_text == "合成演示"

def test_same_source_snapshot_has_stable_import_identity_and_plan_id():
    first = manifest()
    second = manifest()
    assert import_key(first) == import_key(second)
    run_id = run_id_for_import(first)
    assert run_id == run_id_for_import(second)
    bundle = Bundle(first, (line(),), None, (), "UNKNOWN")
    assert create_draft(run_id, bundle, reconcile(bundle)).plan_id == create_draft(
        run_id, bundle, reconcile(bundle)).plan_id

def test_adjustment_rejects_stale_parent_and_blank_reason():
    bundle = Bundle(manifest(), (line(),), None, (), "UNKNOWN")
    draft = create_draft("run-1", bundle, reconcile(bundle))
    actor = Actor("synthetic-reviewer", "SYNTH-ORG", True)
    with pytest.raises(EngineError):
        adjust_demo(draft, expected_parent_version=0, changed_rows=(), actor=actor,
                    reason_code="DEMO_REASON", reason_text="演示")
    with pytest.raises(EngineError):
        adjust_demo(draft, expected_parent_version=1, changed_rows=(), actor=actor,
                    reason_code="DEMO_REASON", reason_text=" ")
```

**Step 2: Future check — confirm tests fail.** From the bound FI14 worktree cwd, run `& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest tests/test_engine.py -q`; expected import failure for `engine`.

**Step 3: Implement minimal deterministic engine.** `import_key(manifest)` hashes canonical JSON of the complete normalized manifest, including extraction timestamp, mode, schema, source ID/version/hash, organization, cutoff, sorted currencies and coverage; `run_id_for_import(manifest)` returns `uuid5(NAMESPACE_URL, "fi14:run:" + import_key(manifest)).hex`. Thus a retry of the same exact source snapshot creates byte-identical base payload and preserves storage idempotency even when the HTTP operation ID differs. `reconcile(bundle)` compares the AP manifest to the independent standard comparator’s org, cutoff, currency set and coverage; missing comparator is `PARTIAL`, any mismatch is `NOT_COMPARABLE`, and missing AP amount is `PARTIAL` with totals/difference `None`. Otherwise calculate exact totals per currency and compare against each standard bucket sum; never add currencies together or clear nonzero differences with tolerance. Retain comparator buckets unchanged as read-only display evidence; never derive aging buckets because G01/G02 remain pending. `create_draft(run_id,bundle,totals)` emits one PlanRow per source AP line and carries supplier, amount, due date, paid status, source_ref, coverage, FI3 risk, and unknown funds/constraints. It has no rank/sort/optimal property and is `PENDING_RULES` while required funds/constraints or G03/G04 are unknown/pending. `adjust_demo` accepts only MOCK, synthetic actor, matching parent version, allowlisted synthetic row action values, nonempty reason code/text, and creates immutable version+1; it never changes source or amount.

Core reconciliation implementation (return types are the immutable models defined above):

```python
from collections import defaultdict
from decimal import Decimal

def reconcile(bundle: Bundle) -> tuple[AgingTotal, ...]:
    currencies = bundle.manifest.currencies
    standard = bundle.standard_aging
    if standard is None:
        return tuple(AgingTotal(c, None, None, None, AgingStatus.PARTIAL,
                                ("standard_aging",)) for c in currencies)
    mismatches = []
    if standard.org_scope != bundle.manifest.org_scope: mismatches.append("org_scope")
    if standard.as_of_date != bundle.manifest.as_of_date: mismatches.append("as_of_date")
    if set(standard.currencies) != set(currencies): mismatches.append("currencies")
    if "ap_lines" not in bundle.manifest.coverage: mismatches.append("ap_coverage")
    if "standard_aging" not in standard.coverage: mismatches.append("coverage")
    if mismatches:
        return tuple(AgingTotal(c, None, None, None, AgingStatus.NOT_COMPARABLE,
                                tuple(mismatches)) for c in currencies)
    ap = defaultdict(Decimal)
    missing = set()
    for line in bundle.ap_lines:
        if line.amount is None:
            missing.add(line.currency)
        else:
            ap[line.amount.currency] += line.amount.amount
    buckets = defaultdict(Decimal)
    for currency, _bucket, amount in standard.bucket_totals:
        buckets[currency] += amount
    rows = []
    for currency in currencies:
        if currency in missing:
            rows.append(AgingTotal(currency, None, buckets.get(currency), None,
                                   AgingStatus.PARTIAL, ("ap_amount",)))
            continue
        ap_total = ap[currency] if currency in ap else None
        std_total = buckets[currency] if currency in buckets else None
        if ap_total is None or std_total is None:
            rows.append(AgingTotal(currency, ap_total, std_total, None,
                                   AgingStatus.PARTIAL, ("coverage",)))
        else:
            rows.append(AgingTotal(currency, ap_total, std_total, ap_total-std_total,
                                   AgingStatus.READY, ()))
    return tuple(rows)
```

`APLine.currency` is required even when amount is null; parser cross-checks it against manifest currencies. `create_draft` copies every line into a PlanRow with source fields intact and sets disposition `UNREVIEWED`, reason `RULES_PENDING`; no amount or due date is inferred. `adjust_demo` verifies expected parent and creates the new frozen PlanVersion; it changes only the allowed synthetic disposition and records a reason code, keeping financial values immutable.

The plan creation and adjustment core must follow this implementation shape:

```python
from dataclasses import replace
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

def import_key(manifest: Manifest) -> str:
    identity = {"mode": manifest.mode.value, "schema": manifest.schema_version,
        "source_id": manifest.source_id, "source_version": manifest.source_version,
        "source_sha256": manifest.source_sha256, "org_scope": manifest.org_scope,
        "as_of_date": manifest.as_of_date.isoformat(),
        "extracted_at_utc": manifest.extracted_at_utc.isoformat(),
        "currencies": sorted(manifest.currencies), "coverage": sorted(manifest.coverage)}
    return sha256(canonical_json(identity)).hexdigest()

def run_id_for_import(manifest: Manifest) -> str:
    return uuid5(NAMESPACE_URL, "fi14:run:" + import_key(manifest)).hex

def create_draft(run_id: str, bundle: Bundle,
                 totals: tuple[AgingTotal, ...]) -> PlanVersion:
    plan_id = uuid5(NAMESPACE_URL, "fi14:plan:" + run_id).hex
    rows = tuple(PlanRow(
        line_id=line.line_id, supplier_ref=line.supplier_ref, amount=line.amount,
        currency=line.currency,
        due_date=line.due_date, paid_status=line.paid_status,
        source_ref=line.source_ref, fi3_risk_status=line.fi3_risk_status,
        coverage_status=line.coverage_status, disposition="UNREVIEWED",
        reason_code="RULES_PENDING") for line in bundle.ap_lines)
    return PlanVersion(plan_id, 1, None, run_id, PlanStatus.PENDING_RULES,
                       bundle.manifest.mode, rows, (), None, None)

def adjust_demo(parent: PlanVersion, *, expected_parent_version: int,
                changed_rows: tuple[tuple[str, str], ...], actor: Actor,
                reason_code: str, reason_text: str) -> PlanVersion:
    if parent.mode is not Mode.MOCK or not actor.synthetic:
        raise EngineError("MOCK_SYNTHETIC_ACTOR_REQUIRED")
    if parent.version != expected_parent_version:
        raise EngineError("PARENT_VERSION_CONFLICT")
    if not reason_code or not reason_text.strip():
        raise EngineError("REASON_REQUIRED")
    allowed = {"DEMO_INCLUDE", "DEMO_EXCLUDE", "UNREVIEWED"}
    updates = dict(changed_rows)
    if len(updates) != len(changed_rows) or any(value not in allowed for value in updates.values()):
        raise EngineError("INVALID_DEMO_ADJUSTMENT")
    if not set(updates).issubset({row.line_id for row in parent.rows}):
        raise EngineError("UNKNOWN_PLAN_ROW")
    rows = tuple(replace(row, disposition=updates[row.line_id])
                  if row.line_id in updates else row for row in parent.rows)
    return PlanVersion(parent.plan_id, parent.version + 1, parent.version, parent.run_id,
        parent.status, parent.mode, rows, tuple(sorted({"disposition"} if updates else set())),
        reason_code, reason_text)
```

`PlanRow.currency` is copied from APLine even when amount is null. Each PlanVersion's immutable `run_id` is a foreign reference to the separately stored immutable `Bundle`; `get_run(run_id)` returns that exact manifest, source comparator, funds snapshot, and constraints status. Do not infer any of those from plan rows. `run_id` and base `plan_id` are deterministic UUID5 values derived from the immutable source identity and run ID; reason text remains in the protected result object and is never copied into `AuditEvent.override_reason`.

**Step 4: Future verification.** Re-run `tests/test_engine.py`; expected all pass and prove no sort/optimal field is emitted.

## Task 3: Canonical immutable storage, idempotency and audit commit barrier

**Files:**
- Create: `4-数字员工/财务部/FI14-应付账龄与付款计划分析/fi14_payment_plan/storage.py`
- Create: `4-数字员工/财务部/FI14-应付账龄与付款计划分析/tests/test_storage.py`

**Step 1: Future test — codec, same-key idempotency, conflict and audit failure.** Add to `tests/test_storage.py`:

```python
import json
from decimal import Decimal
import pytest
from zhuopin_platform.audit import AuditEvent
from fi14_payment_plan.storage import FileResultStore, canonical_json, content_hash, StoreError
from fi14_payment_plan.models import PlanStatus

def safe_event(action="mock_import", content_hash_value="a"*64):
    return AuditEvent(scenario="FI14", action=action, evaluator="synthetic-reviewer",
        automation_level="L1", decision={"status":"MOCK", "operation_id":"op-test"},
        data_sources={"bundle":"sha256:" + content_hash_value},
        content_hash=content_hash_value, oem_context="", override_reason="", report_path="", error="")

class VerifyResult:
    def __init__(self, ok): self.ok=ok

class FakeAudit:
    def __init__(self, fail=False): self.events=[]; self.fail=fail
    def record(self, event):
        if self.fail: raise OSError("audit unavailable")
        self.events.append(event)
    def verify_chain(self): return VerifyResult(not self.fail)
    def query_by(self, **filters):
        return [event.to_dict() for event in self.events
                if all(event.to_dict().get(key) == value for key, value in filters.items())]

def test_canonical_json_decimal_string_and_stable_hash():
    assert canonical_json({"b": Decimal("1.20"), "a": "x"}) == b'{"a":"x","b":"1.20"}'
    assert content_hash({"a": 1}) == content_hash({"a": 1})

def result_payload(run_id="11111111111141118111111111111111", plan_version=1,
                   amount="12.00", reason_text=""):
    return {"schema_version":"fi14_result/v1", "mode":"MOCK",
        "run_id":run_id, "plan_version":plan_version,
        "manifest":{"schema_version":"fi14_mock_bundle/v1", "source_id":"synthetic-ap", "source_version":"1",
            "source_sha256":"a"*64, "org_scope":"SYNTH-ORG", "as_of_date":"2026-09-30",
            "extracted_at_utc":"2026-10-12T00:00:00Z", "currencies":["CNY"], "coverage":["ap_lines"]},
        "ap_lines":[{"line_id":"L1", "supplier_ref":"SYNTH-S1", "currency":"CNY",
            "amount":amount, "due_date":None, "paid_status":"UNKNOWN",
            "source_ref":"ap:L1", "coverage_status":"COMPLETE", "fi3_risk_status":"UNKNOWN"}],
        "standard_aging":{"source_id":"synthetic-standard", "source_version":"1", "source_sha256":"b"*64,
            "org_scope":"SYNTH-ORG", "as_of_date":"2026-09-30", "currencies":["CNY"],
            "coverage":["standard_aging"], "bucket_totals":[{"currency":"CNY",
                "bucket":"UNCLASSIFIED_SOURCE_BUCKET", "amount":amount}]},
        "aging":[{"currency":"CNY", "ap_total":amount, "standard_total":amount,
            "difference":"0", "status":"READY"}],
        "funds":{"CNY":None}, "constraints_status":"PENDING",
        "plan":{"plan_id":"99999999999949998999999999999999",
            "status":"PENDING_RULES", "rows":[{"line_id":"L1", "currency":"CNY",
            "amount":amount, "reason_text":reason_text}]}}

def test_commit_is_idempotent_and_published_object_is_immutable(tmp_path):
    audit = FakeAudit()
    store = FileResultStore(tmp_path, audit)
    first = store.commit(operation_id="op-1", idempotency_key="key-1",
                         payload=result_payload(), audit_event=safe_event())
    again = store.commit(operation_id="op-1", idempotency_key="key-1",
                         payload=result_payload(), audit_event=safe_event())
    assert again == first
    assert len(audit.events) == 1
    assert audit.events[0].decision["operation_id"] == "op-1"
    assert audit.events[0].decision["object_id"] == first
    assert audit.events[0].decision["payload_hash"] == content_hash(result_payload())
    duplicate_operation = store.commit(operation_id="op-duplicate", idempotency_key="key-1",
        payload=result_payload(), audit_event=safe_event())
    assert duplicate_operation == first and len(audit.events) == 1
    state = json.loads((tmp_path / ".control" / "operations.json").read_text(encoding="utf-8"))
    assert state["keys"]["key-1"]["operation_id"] == "op-1"
    business_path_text = state["keys"]["key-1"]["business_path"].replace("\\", "/")
    assert business_path_text.endswith("/11111111111141118111111111111111/1.json")
    assert len(list(tmp_path.glob("*/1.json"))) == 1
    with pytest.raises(StoreError):
        store.commit(operation_id="op-2", idempotency_key="key-1",
                     payload=result_payload(amount="13.00"), audit_event=safe_event())

def test_audit_failure_never_publishes_and_retry_reuses_operation(tmp_path):
    audit = FakeAudit(fail=True)
    store = FileResultStore(tmp_path, audit)
    with pytest.raises(StoreError):
        store.commit(operation_id="op-2", idempotency_key="key-2",
                     payload=result_payload("22222222222242228222222222222222"), audit_event=safe_event())
    assert store.visible_ids() == ()
    assert store.failed_operation_exists("op-2")

def test_parent_version_conflict_does_not_overwrite(tmp_path):
    store = FileResultStore(tmp_path, FakeAudit())
    store.register_parent("plan-1", current_version=2)
    with pytest.raises(StoreError, match="PARENT_VERSION_CONFLICT"):
        store.commit_version(plan_id="plan-1", expected_parent_version=1,
                             operation_id="op-3", idempotency_key="key-3",
                             payload=result_payload("33333333333343338333333333333333", 3),
                             audit_event=safe_event("mock_adjustment"))

def test_concurrent_same_key_returns_one_published_object(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    store = FileResultStore(tmp_path, FakeAudit())
    def submit(_):
        return store.commit(operation_id=f"op-shared-{_}", idempotency_key="key-shared",
                            payload=result_payload("44444444444444448444444444444444"),
                            audit_event=safe_event())
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(submit, range(16)))
    assert len(set(ids)) == 1
    assert len(store.visible_ids()) == 1

@pytest.mark.parametrize("boundary", ["after_pending_write", "after_fsync",
    "after_readback", "after_audit", "before_publish", "after_publish_before_state"])
def test_interruption_at_each_commit_boundary_keeps_object_invisible(tmp_path, boundary):
    def interrupt(at):
        if at == boundary: raise StoreError("INJECTED_FAILURE")
    store = FileResultStore(tmp_path, FakeAudit(), fault_injector=interrupt)
    with pytest.raises(StoreError):
        store.commit(operation_id="op-boundary", idempotency_key="key-boundary",
                     payload=result_payload("55555555555545558555555555555555"), audit_event=safe_event())
    assert store.visible_ids() == ()
    assert store.failed_operation_exists("op-boundary")

@pytest.mark.parametrize("boundary", ["after_audit", "after_publish_before_state"])
def test_restart_recovers_same_id_and_does_not_duplicate_audit(tmp_path, boundary):
    audit = FakeAudit()
    def interrupt(at):
        if at == boundary: raise StoreError("INJECTED_FAILURE")
    first_store = FileResultStore(tmp_path, audit, fault_injector=interrupt)
    with pytest.raises(StoreError):
        first_store.commit(operation_id="op-recover", idempotency_key="key-recover",
                           payload=result_payload("66666666666646668666666666666666"), audit_event=safe_event())
    prior_count = len(audit.events)
    assert prior_count == (1 if boundary in {"after_audit", "after_publish_before_state"} else 0)
    if prior_count:
        assert audit.events[0].decision["operation_id"] == "op-recover"
    restarted = FileResultStore(tmp_path, audit)
    recovered_id = restarted.commit(operation_id="op-recover", idempotency_key="key-recover",
                                    payload=result_payload("66666666666646668666666666666666"),
                                    audit_event=safe_event())
    assert len(audit.events) == prior_count
    assert restarted.visible_ids() == (recovered_id,)
    business_path = tmp_path / "66666666666646668666666666666666" / "1.json"
    assert business_path.exists()
    assert json.loads(business_path.read_text(encoding="utf-8")) == result_payload(
        "66666666666646668666666666666666")
    assert restarted.get(recovered_id) == result_payload("66666666666646668666666666666666")

def test_existing_target_with_different_bytes_is_never_overwritten(tmp_path, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr("fi14_payment_plan.storage.uuid4", lambda: SimpleNamespace(hex="fixed-id"))
    target = tmp_path / "77777777777747778777777777777777" / "1.json"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"foreign-object")
    store = FileResultStore(tmp_path, FakeAudit())
    with pytest.raises(StoreError, match="PUBLISHED_OBJECT_CONFLICT"):
        store.commit(operation_id="op-collision", idempotency_key="key-collision",
                     payload=result_payload("77777777777747778777777777777777"), audit_event=safe_event())
    assert target.read_bytes() == b"foreign-object"
    assert store.visible_ids() == ()

def test_history_diff_returns_field_names_and_hashes_only(tmp_path):
    store = FileResultStore(tmp_path, FakeAudit())
    left = store.commit(operation_id="op-left", idempotency_key="key-left",
        payload=result_payload("88888888888848888888888888888888", 1, "125.10", "sensitive"), audit_event=safe_event())
    right = store.commit(operation_id="op-right", idempotency_key="key-right",
        payload=result_payload("88888888888848888888888888888888", 2, "130.00", "different sensitive"), audit_event=safe_event())
    diff = store.compare_history(left, right)
    serialized = repr(diff)
    assert "amount" in serialized and "reason_text" in serialized
    assert "125.10" not in serialized and "130.00" not in serialized
    assert "sensitive" not in serialized
```

**Step 2: Future check — confirm tests fail.** From the bound FI14 worktree cwd, run `& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest tests/test_storage.py -q`; expected import failure.

**Step 3: Implement storage to this concrete contract.** `FileResultStore(root: Path, audit: AuditLogger, fault_injector: Callable[[str], None] | None = None)` exposes the exact `ResultStore` methods above plus `visible_ids`, `failed_operation_exists`, `register_parent`, `get_run`, and `compare_history`; `root` resolves to `reports/fi14_pc_mvp`. Injected fault points are `after_pending_write`, `after_fsync`, `after_readback`, `after_audit`, `before_publish`, and `after_publish_before_state`. Persist the canonical operation/key/hash/path journal before pending bytes. `commit`/`commit_version` validate the business `fi14_result/v1` document; `_exact_object_paths` creates the internal pending path in `.control/objects/` and business path `<run_id>/<plan_version>.json`. After audit append, query it back and require exactly one matching event plus valid chain before no-replace publication. Keep pending bytes on success/failure, and do not add deletion. The idempotency key maps to its first canonical operation ID; same-key/same-hash retries return or resume that exact operation/result, regardless of newly supplied operation IDs; same-key/different-hash fails. Per-key/per-plan locks serialize calls; `commit_version` checks parent before audit or publication. `get(object_id)` verifies state-index path/hash/schema/run/version; history comparison returns field names and before/after hashes. `safe_event` constructs an allowlisted real `AuditEvent` projection with actual transaction IDs and only safe status/hash values.

Implement the commit critical section with this concrete sequence (the surrounding store owns the declared locks and JSON state files):

```python
def _commit_locked(self, operation_id, idempotency_key, payload, audit_event):
    payload_bytes = canonical_json(payload)
    payload_hash = sha256(payload_bytes).hexdigest()
    state = self._read_state()
    key_prior = state["keys"].get(idempotency_key)
    if key_prior is not None and key_prior["payload_hash"] != payload_hash:
        raise StoreError("IDEMPOTENCY_CONFLICT")
    if key_prior is not None:
        # A repeated identical key belongs to its first operation, even if the caller retries
        # with a newly allocated operation ID.
        operation_id = key_prior["operation_id"]
    prior = state["operations"].get(operation_id)
    if prior is not None:
        if prior["payload_hash"] != payload_hash or prior["idempotency_key"] != idempotency_key:
            raise StoreError("OPERATION_CONFLICT")
        if prior["published"]:
            return prior["object_id"]
    object_id = prior["object_id"] if prior else uuid4().hex
    pending, target = self._exact_object_paths(object_id, payload)
    if prior is None:
        state["operations"][operation_id] = {
            "idempotency_key": idempotency_key, "payload_hash": payload_hash,
            "object_id": object_id, "business_path": str(target), "published": False}
        state["keys"][idempotency_key] = {"payload_hash": payload_hash,
            "object_id": object_id, "operation_id": operation_id,
            "business_path": str(target), "published": False}
        self._atomic_write_state(state)  # durable journal before pending object or audit
    object_bytes = payload_bytes
    object_hash = payload_hash
    if target.exists() and sha256(target.read_bytes()).hexdigest() != object_hash:
        raise StoreError("PUBLISHED_OBJECT_CONFLICT")
    if not target.exists():
        pending.parent.mkdir(parents=True, exist_ok=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        if pending.exists():
            if sha256(pending.read_bytes()).hexdigest() != object_hash:
                raise StoreError("PENDING_HASH_MISMATCH")
        else:
            with pending.open("xb") as stream:
                stream.write(object_bytes)
                stream.flush()
                os.fsync(stream.fileno())
    self._fault("after_pending_write")
    self._fault("after_fsync")
    object_path = target if target.exists() else pending
    if sha256(object_path.read_bytes()).hexdigest() != object_hash:
        raise StoreError("PENDING_HASH_MISMATCH")
    document = json.loads(object_path.read_text(encoding="utf-8"))
    expected_pending, expected_target = self._exact_object_paths(object_id, document)
    if expected_pending != pending or expected_target != target:
        raise StoreError("OBJECT_IDENTITY_CONFLICT")
    self._fault("after_readback")
    matches = self._matching_audit_events(operation_id, object_id, payload_hash)
    if len(matches) > 1:
        raise StoreError("DUPLICATE_AUDIT_EVENT")
    if not matches:
        safe_event = self._safe_event(audit_event, operation_id, object_id, payload_hash, payload)
        try:
            self.audit.record(safe_event)
        except Exception as exc:
            raise StoreError("AUDIT_WRITE_FAILED") from exc
    try:
        chain_valid = self.audit.verify_chain().ok
    except Exception as exc:
        raise StoreError("AUDIT_CHAIN_UNAVAILABLE") from exc
    if not chain_valid:
        raise StoreError("AUDIT_CHAIN_INVALID")
    # Re-read by top-level scenario, then match all opaque IDs in each event's decision.
    matches = self._matching_audit_events(operation_id, object_id, payload_hash)
    if len(matches) != 1:
        raise StoreError("AUDIT_EVENT_NOT_READABLE")
    try:
        chain_valid = self.audit.verify_chain().ok
    except Exception as exc:
        raise StoreError("AUDIT_CHAIN_UNAVAILABLE") from exc
    if not chain_valid:
        raise StoreError("AUDIT_COMMIT_NOT_VERIFIED")
    self._fault("after_audit")
    self._fault("before_publish")
    # Hard-link creation is atomic and fails when target already exists; pending is retained.
    if not target.exists():
        try:
            os.link(pending, target)
        except FileExistsError:
            pass
    self._fault("after_publish_before_state")
    if not target.exists() or sha256(target.read_bytes()).hexdigest() != object_hash:
        raise StoreError("PUBLISHED_OBJECT_CONFLICT")
    published = json.loads(target.read_text(encoding="utf-8"))
    if (published.get("run_id") != document.get("run_id")
            or published.get("plan_version") != document.get("plan_version")
            or published.get("schema_version") != "fi14_result/v1"):
        raise StoreError("PUBLISHED_OBJECT_CONFLICT")
    state["operations"][operation_id] = {
        "idempotency_key": idempotency_key, "payload_hash": payload_hash,
        "object_id": object_id, "business_path": str(target), "published": True}
    state["keys"][idempotency_key] = {"payload_hash": payload_hash,
        "object_id": object_id, "operation_id": operation_id,
        "business_path": str(target), "published": True}
    self._atomic_write_state(state)
    return object_id
```

Helper contracts are fixed: `_read_state() -> dict` reads `RESULT_ROOT/.control/operations.json` and returns validated `{"operations": {}, "keys": {}}`; key entries additionally hold canonical `operation_id`, payload hash, object ID, exact business path, and published flag. `_atomic_write_state(state: dict) -> None` writes/flushed/fsyncs a same-volume temp and atomically replaces only that mutable control index. `_exact_object_paths(object_id: str, payload: Mapping[str, object]) -> tuple[Path, Path]` validates `schema_version == "fi14_result/v1"`, `mode == "MOCK"`, a lowercase 32-hex server `run_id`, and positive integer `plan_version`, then returns `RESULT_ROOT/.control/objects/<object_id>.pending` and `RESULT_ROOT/<run_id>/<plan_version>.json`; because `RESULT_ROOT` resolves to `reports/fi14_pc_mvp`, the latter is exactly `reports/fi14_pc_mvp/<run_id>/<plan_version>.json`. The plan version is never replaced by the UUID operation/object ID. `_matching_audit_events(operation_id, object_id, payload_hash) -> list[dict]` uses `AuditLogger.query_by(scenario="FI14")`, then caller code matches all three values in decision (query_by only filters top-level fields). `_safe_event(context, operation_id, object_id, payload_hash) -> AuditEvent` uses `context.evaluator/action/automation_level`, but constructs a new event with this actual operation ID/object ID/hash and status, opaque source hash only, and empty `override_reason/report_path/error/oem_context`. `_fault(boundary: str) -> None` invokes the test-only callback. The durable key and operation journal is persisted before pending bytes. If an existing idempotency key has the same hash and is published, return its canonical operation's existing result; if it has the same hash and is unfinished, resume that canonical operation/object ID; if the hash differs, conflict. This prevents a second operation ID from creating a second run/version for a duplicate import. After `audit.record`, re-query actual events and require exactly one matching operation/object/hash tuple plus `verify_chain().ok`; an empty but valid chain cannot pass the commit barrier. If a crash occurs after `audit.record`, recovery re-reads actual audit rows and skips duplicate append only when the unique matching event and chain verify. If it crashes after hard-link publication before state update, retry reuses same canonical ID and business path. `os.link(pending,business_target)` is the no-replace primitive; existing target can be reused only when exact schema, run ID, plan version, and hash match. Keep pending link as evidence. Visible lookup trusts only published state index. `get_run(run_id)` returns immutable Bundle with manifest, comparator, funds and constraints.

Definitive helper contract (this supersedes shorthand signatures in the preceding summary): `_exact_object_paths` rejects boolean `plan_version`, validates `plan_id`, and resolves the business target under `RESULT_ROOT/<run_id>/<plan_version>.json`; `_safe_event` signature is `_safe_event(context, operation_id, object_id, payload_hash, payload)` and adds payload `run_id`, `plan.plan_id`, and `plan_version` to its safe decision. `_read_state`/`_atomic_write_state` create/read `.control/operations.json` and map idempotency keys to canonical operation ID, hash, object ID, business path, and published state. `get_run(run_id)` reconstructs the Bundle from immutable base result version `1.json`, including the complete normalized `ap_lines` array.

`_safe_event` must construct, rather than reuse, the incoming event so system IDs cannot be stale or caller-controlled:

```python
def _safe_event(self, context, operation_id, object_id, payload_hash, payload):
    if context.action not in {"mock_import", "mock_compute", "mock_adjustment",
                              "mock_view", "mock_export", "access_denied"}:
        raise StoreError("AUDIT_ACTION_NOT_ALLOWED")
    return AuditEvent(
        scenario="FI14", action=context.action, evaluator=context.evaluator,
        automation_level=context.automation_level,
        decision={"status":"MOCK", "operation_id":operation_id,
                  "object_id":object_id, "payload_hash":payload_hash,
                  "run_id":payload["run_id"], "plan_id":payload["plan"]["plan_id"],
                  "version":payload["plan_version"]},
        data_sources={"bundle_sha256":payload["manifest"]["source_sha256"]}, content_hash=payload_hash,
        oem_context="", override_reason="", report_path="", error="")
```

Operation/object IDs and payload hash are stored in `.control/operations.json`; the immutable business file remains the exact `fi14_result/v1` document. The full business payload stays in that controlled object, never in `AuditEvent`. State index writes are replaceable metadata; object publication uses no-replace hard-link creation.

**Step 4: Future verification.** Re-run storage tests, including interruption injection around each commit boundary; expected invisible pending objects and one published ID per operation.

## Task 4: Default-deny permission adapter and Flask PC flow with audit-safe projection

**Files:**
- Create: `4-数字员工/财务部/FI14-应付账龄与付款计划分析/fi14_payment_plan/access.py`
- Create: `4-数字员工/财务部/FI14-应付账龄与付款计划分析/fi14_payment_plan/webapp.py`
- Create: `4-数字员工/财务部/FI14-应付账龄与付款计划分析/fi14_payment_plan/templates/index.html`
- Create: `4-数字员工/财务部/FI14-应付账龄与付款计划分析/tests/test_access.py`
- Create: `4-数字员工/财务部/FI14-应付账龄与付款计划分析/tests/test_webapp.py`

**Step 1: Future test — identity defaults to deny and request headers cannot grant access.** Add to `tests/test_access.py`:

```python
from fi14_payment_plan.models import AccessAction, Actor
from fi14_payment_plan.access import DenyAllProvider, SyntheticFixtureProvider

def test_missing_provider_denies_every_action():
    provider = DenyAllProvider()
    for action in AccessAction:
        assert not provider.decide(None, "SYNTH-ORG", None, action).allowed

def test_synthetic_provider_requires_explicit_actor_and_matching_scope():
    provider = SyntheticFixtureProvider()
    actor = Actor("synthetic-reviewer", "SYNTH-ORG", True)
    assert provider.decide(actor, "SYNTH-ORG", None, AccessAction.IMPORT).allowed
    assert not provider.decide(actor, "OTHER", None, AccessAction.IMPORT).allowed
    assert not provider.decide(Actor("real-user", "SYNTH-ORG", False),
                               "SYNTH-ORG", None, AccessAction.EXPORT).allowed
```

**Step 2: Future test — complete MOCK request flow and audit redaction.** Add to `tests/test_webapp.py`:

```python
import json
from fi14_payment_plan.webapp import create_app
from fi14_payment_plan.access import SyntheticFixtureProvider, DenyAllProvider
from fi14_payment_plan.models import Actor
import pytest
from pathlib import Path
from zhuopin_platform.audit import AuditEvent

class FailedChain:
    ok = False
class FailingAudit:
    def record(self, event: AuditEvent): raise OSError("audit unavailable")
    def verify_chain(self): return FailedChain()

@pytest.fixture
def failing_audit():
    return FailingAudit()

def demo_actor_resolver():
    return Actor("synthetic-reviewer", "SYNTH-ORG", True)

@pytest.fixture
def mock_bundle():
    return (Path(__file__).parents[1] / "data" / "mock" / "fi14_bundle.json").read_bytes()

def test_mock_import_result_adjust_history_export_and_sensitive_audit(tmp_path, mock_bundle):
    app = create_app({"TESTING": True, "MODE": "MOCK", "RESULT_ROOT": tmp_path,
                      "AUDIT_PATH": tmp_path / "audit.jsonl"},
                     access_provider=SyntheticFixtureProvider(), actor_resolver=demo_actor_resolver)
    client = app.test_client()
    response = client.post("/finance/fi14/import", data=mock_bundle,
                           content_type="application/json")
    assert response.status_code == 201
    run_id = response.json["run_id"]
    assert response.json["mode"] == "MOCK"
    result = client.get(f"/finance/fi14/runs/{run_id}")
    assert result.status_code == 200
    assert result.json["aging"][0]["status"] in {"READY", "PARTIAL"}
    assert result.json["plan"]["status"] == "PENDING_RULES"
    adjusted = client.post(f"/finance/fi14/runs/{run_id}/adjust", json={
        "parent_version": 1, "operation_id": "op-demo-1", "reason_code": "DEMO",
        "reason_text": "synthetic demonstration", "rows": [["L1", "DEMO_INCLUDE"]]})
    assert adjusted.status_code == 201 and adjusted.json["version"] == 2
    history = client.get(f"/finance/fi14/runs/{run_id}/history")
    assert len(history.json["versions"]) == 2
    first_id, second_id = [v["id"] for v in history.json["versions"]]
    comparison = client.get(f"/finance/fi14/runs/{run_id}/compare/{first_id}/{second_id}")
    assert comparison.status_code == 200
    assert "125.10" not in comparison.get_data(as_text=True)
    assert all(set(row) == {"field", "before_hash", "after_hash"}
               for row in comparison.json["differences"])
    exported = client.get(f"/finance/fi14/runs/{run_id}/export")
    assert exported.status_code == 200
    assert exported.json["label"] == "MOCK/DRAFT"
    audit_lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in audit_lines]
    for event in events:
        assert event["override_reason"] == ""
        assert event["report_path"] == ""
        assert event["error"] == ""
        assert event["oem_context"] == ""
        assert all(key not in event["decision"] for key in
                   ("amount", "before", "after", "reason_text"))
    audit_text = "\n".join(audit_lines)
    for sensitive in ("125.10", "synthetic demonstration", "SYNTH-S1", "ap:L1",
                      "source file raw", "before_amount", "after_amount"):
        assert sensitive not in audit_text

def test_unknown_actor_and_forged_identity_header_are_denied(tmp_path, mock_bundle):
    app = create_app({"TESTING": True, "MODE": "MOCK", "RESULT_ROOT": tmp_path,
                      "AUDIT_PATH": tmp_path / "audit.jsonl"},
                     access_provider=DenyAllProvider())
    response = app.test_client().post("/finance/fi14/import", data=mock_bundle,
        content_type="application/json", headers={"X-Zp-Identity":"synthetic-reviewer"})
    assert response.status_code == 403
    assert "125.10" not in response.get_data(as_text=True)

def test_audit_failure_returns_failure_without_visible_success(tmp_path, mock_bundle, failing_audit):
    app = create_app({"TESTING": True, "MODE": "MOCK", "RESULT_ROOT": tmp_path,
                      "AUDIT_PATH": tmp_path / "audit.jsonl"},
                     access_provider=SyntheticFixtureProvider(), actor_resolver=demo_actor_resolver,
                     audit_logger=failing_audit)
    response = app.test_client().post("/finance/fi14/import", data=mock_bundle,
                                      content_type="application/json")
    assert response.status_code == 503
    assert response.json["status"] == "NOT_COMMITTED"
    assert app.extensions["fi14_store"].visible_ids() == ()
```

**Step 3: Implement minimal web/auth boundary.** `access.py` provides `DenyAllProvider.decide(...)` and `SyntheticFixtureProvider.decide(...)` (only synthetic actor, exact `SYNTH-ORG`, allowlisted actions). `create_app(config: Mapping[str, object], *, access_provider: AccessDecisionProvider | None = None, actor_resolver: Callable[[], Actor | None] | None = None, audit_logger: AuditLogger | None = None) -> Flask` defaults provider to deny-all and resolver to `lambda: None`. Its MOCK-only app factory may be explicitly supplied the synthetic provider and resolver to run the approved demo; these injections are the sole demonstration identity path, are visibly labeled “合成演示身份”, and are never inferred from a request header/shared password or registered as an employee/role. Routes are `GET /finance/fi14`, `POST /finance/fi14/import`, `GET /finance/fi14/runs/<run_id>`, `POST /finance/fi14/runs/<run_id>/adjust`, history, compare, and export. Authorize before object lookup. Import enforces JSON byte limit/MOCK, then parse/reconcile/draft and commit using `run_id_for_import(bundle.manifest)` and `import_key(bundle.manifest)` as its stable key; operation IDs identify attempts but do not alter the source-snapshot identity. Adjustment checks operation ID, parent, allowed demo field/action, reason code; sensitive reason text stays only in protected result. Export requires authorization and emits MOCK/DRAFT metadata; no path argument. Compare returns names/hash only. Append audit to every operation/denial using status/opaque IDs/hash/reason code only; assert no financial amount, source row, raw reason, request body, report path, exception string or OEM context appears in any event field. Error responses use fixed code/message enums. Template labels synthetic MOCK draft and does not expose payment/approval/writeback controls.

**Step 4: Future verification.** From the bound FI14 worktree cwd run `& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest tests/test_access.py tests/test_webapp.py -q`; expected all endpoints fail closed and the full mock demonstration round-trips with no sensitive audit values.

## Task 5: Fixture completion, independent validation and implementation handoff

**Files:**
- Modify: `4-数字员工/财务部/FI14-应付账龄与付款计划分析/data/mock/fi14_bundle.json`
- Modify: `4-数字员工/财务部/FI14-应付账龄与付款计划分析/tests/conftest.py`
- Modify: `4-数字员工/财务部/FI14-应付账龄与付款计划分析/tests/test_sources.py`
- Modify: `4-数字员工/财务部/FI14-应付账龄与付款计划分析/tests/test_engine.py`
- Modify: `4-数字员工/财务部/FI14-应付账龄与付款计划分析/tests/test_storage.py`
- Modify: `4-数字员工/财务部/FI14-应付账龄与付款计划分析/tests/test_access.py`
- Modify: `4-数字员工/财务部/FI14-应付账龄与付款计划分析/tests/test_webapp.py`

**Step 1: Future test — add boundary matrix assertions.** Add these tests to their owning files:

```python
# test_sources.py
@pytest.mark.parametrize("field,value", [
    ("org_scope", ""), ("as_of_date", "2026-02-30"),
    ("currencies", ["CNY", "CNY"]), ("coverage", [])])
def test_rejects_incomplete_manifest(field, value):
    with pytest.raises(BundleError): parse_bundle(bundle_bytes(**{field: value}))

# test_engine.py
def test_currencies_reconcile_independently_without_overall_total():
    ap = manifest(currencies=("CNY", "USD"))
    std = StandardAging("std", "1", "c"*64, "SYNTH-ORG", ap.as_of_date,
        ("CNY", "USD"), ("standard_aging",),
        (("CNY", "UNCLASSIFIED_SOURCE_BUCKET", Decimal("10")),
         ("USD", "UNCLASSIFIED_SOURCE_BUCKET", Decimal("2"))))
    bundle = Bundle(ap, (line(Decimal("10"), "CNY"),
        APLine("L2", "SYNTH-S2", Money(Decimal("2"), "USD"), "USD", None, "UNKNOWN",
               "ap:L2", "COMPLETE", "UNKNOWN")), std, (), "SYNTHETIC_DEMO_ONLY")
    result = reconcile(bundle)
    assert {item.currency: item.ap_total for item in result} == {
        "CNY": Decimal("10"), "USD": Decimal("2")}
    assert all(item.difference == Decimal("0") for item in result)
    assert not hasattr(result[0], "overall_total")

# test_storage.py
def test_reused_operation_id_with_different_payload_is_conflict(tmp_path):
    store = FileResultStore(tmp_path, FakeAudit())
    store.commit(operation_id="op-x", idempotency_key="key-x",
        payload=result_payload("aaaaaaaaaaaa4aaa8aaaaaaaaaaaaaaa", 1, "1.00"), audit_event=safe_event())
    with pytest.raises(StoreError):
        store.commit(operation_id="op-x", idempotency_key="key-y",
            payload=result_payload("aaaaaaaaaaaa4aaa8aaaaaaaaaaaaaaa", 1, "2.00"), audit_event=safe_event())

# test_access.py
def test_non_synthetic_actor_is_denied_even_with_matching_org():
    provider = SyntheticFixtureProvider()
    actor = Actor("employee-1", "SYNTH-ORG", False)
    assert not provider.decide(actor, "SYNTH-ORG", "run-1", AccessAction.VIEW).allowed

# test_webapp.py
def test_non_mock_mode_is_rejected_before_processing(tmp_path, mock_bundle):
    app = create_app({"TESTING": True, "MODE": "MOCK", "RESULT_ROOT": tmp_path,
                      "AUDIT_PATH": tmp_path / "audit.jsonl"},
                     access_provider=SyntheticFixtureProvider(), actor_resolver=demo_actor_resolver)
    body = mock_bundle.replace(b'"mode":"MOCK"', b'"mode":"MASKED"')
    response = app.test_client().post("/finance/fi14/import", data=body,
                                      content_type="application/json")
    assert response.status_code == 400
    assert app.extensions["fi14_store"].visible_ids() == ()
```

**Step 2: Future check — run the exact CI command from the scenario root.** The only test targets are the five files listed above; write JUnit output to `pytest-result.xml`. Expected: all pass. If this scenario root is excluded from current CI dynamic matrix, report that fact; do not run repository-root pytest or add unrelated test projects.

```powershell
Set-Location -LiteralPath "C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-fi14/zhuopin-ai/4-数字员工/财务部/FI14-应付账龄与付款计划分析"
& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest -q --tb=short --junit-xml="pytest-result.xml"
```

**Step 3: Future independent review.** A separate formal Guardian using explicit `gpt-6-luna` reviews the implementation HEAD, all 17-file scope, spec traceability, test evidence, PENDING G01–G06, audit redaction, default-deny behavior, operation idempotency, concurrency and failure visibility. Record findings against that exact HEAD; the Guardian does not commit or push.

**Step 4: Future completion evidence.** Preserve the exact isolated interpreter path, command, stdout/stderr, exit code, JUnit result, reviewed HEAD and review findings in the approved project evidence location. Do not modify queue state as part of this plan; outer execution owns queue/lock workflow.

**Step 5: Stop at implementation review.** A passing implementation and review may be presented for the next concrete approval. No fast-forward, real source access, production deployment, payment, or external sending follows automatically.

## Self-review

- **Spec coverage:** input provenance and strict MOCK-only parsing (Tasks 1, 4); same cutoff/org/currency reconciliation and unknown (Task 2); draft/PENDING_RULES and versioned synthetic demonstration (Task 2); history and controlled export (Task 4); immutable JSON, operation idempotency, parent conflicts and audit barrier (Task 3); authorization default deny (Task 4); audit projection and redaction (Task 4); CI and independent review gates (Task 5).
- **Placeholder scan:** no TODO, TBD, generic “handle errors” instruction, or unowned function name. No implementation code is run by this plan.
- **Type consistency:** `Manifest`, `APLine` (including currency with null amounts), `StandardAging`, `Bundle`, `AgingTotal`, `PlanRow`, `PlanVersion`, `Actor`, `AccessDecision`, `AccessDecisionProvider`, `ResultStore`, `parse_bundle`, `reconcile`, `create_draft`, `adjust_demo`, and `FileResultStore` signatures are shared consistently. PlanVersion.run_id resolves to the immutable persisted Bundle via `get_run`.
- **Bootstrap provenance:** the complete `strict=True` sample matches `4-数字员工/财务部/FI3-付款申请自动校验/tests/conftest.py` lines 8–18 and points to the actual platform implementation path; no bootstrap discovery algorithm is copied.
- **Core implementation detail:** parser rejection/Bundle construction, reconciliation, draft creation, adjustment validation, and storage commit barrier include concrete implementation blocks; model/API declarations remain contracts and do not claim to be executable implementations.
- **Review Focus coverage:** malformed/active payload is pinned in `test_sources.py`; independent comparator mismatch/unknown and per-currency totals in `test_engine.py`; sensitive audit values and fixed empty audit fields in `test_webapp.py`; duplicate/concurrent/idempotent publication, journal-first recovery after audit and after hard-link publication, no-overwrite collision, and stale parent in `test_storage.py`; spoofed identity/default deny in `test_access.py` and `test_webapp.py`.
- **Idempotency and result-path coverage:** same key/hash with a new operation ID reuses the first canonical ID and publishes one `fi14_result/v1` file at `<run_id>/<plan_version>.json`; different hashes conflict. Recovery tests reopen the store and read that exact business path after audit append and after hard-link publication.
- **Commit-barrier review:** initial operation/key/object/path journal is durable before pending data or audit; `before_publish` is an injected and exercised fault; audit append is read back and matched uniquely by decision operation/object/hash before chain verification can release publication; business result hard-link is no-replace and keeps the pending link as evidence.
- **Design constraint:** the plan retains only the explicitly approved MOCK loop. The original design allowed a future MASKED mode; this plan intentionally does not include it because the approved technical addendum narrows the first implementation to MOCK and separately requires authorization for real masked sources.

---

本计划仅供下一具体审阅；批准不包含产品实施、测试、真实取数、合入、部署、付款或外发。
