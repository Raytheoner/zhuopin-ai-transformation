# 供审执行边界（根会话收敛）

本件是具体计划供审。D1–D10设计已批准，SHA `38E3BB0CE2DB024BF85BBC543E8997D14827C1CEBD679F75B9F6DCA017FE624D` 不变；本件不重问#277或已批设计。

1. 起点固定主仓 HEAD `28337c0ebb52afdbf61e955ecdbc22d151bcd185`；获批后用 app 原生 `create_worktree(allowAsync=true, name=sc2-biztype316-1010, ref=28337c0ebb52afdbf61e955ecdbc22d151bcd185)` 新建并附着隔离候选。当前没有可复用的合适附着树；历史树不扩写。批准包括原生工具返回的仓库外新checkout/必要Git元数据，创建后登记真实绝对路径；随后仅修改正文14个产品/测试文件。Native与显式gpt-6-luna沿用。
2. 所有产品代码和定向测试使用实际返回的CandidateRoot；计划/已批OpenSpec从主仓只读。正式tasks/队列/证据由根按共享锁更新，主仓产品不覆盖、不复制历史dirty、不手动commit。候选diff/SHA留证，实际候选提交/ff另按既有治理闭合，不在候选裸跑主仓CommitSweep。
3. 测试仅SC2四个现存测试文件与平台新增test_erp_biztype316.py，分别在各子项目cwd运行，不做根混跑；baseline仅清单内的现存文件。Task6命令显式CandidateRoot参数，报告留主仓ignored `reports/sc2-biztype316-1010/runs/<UUID>/`，每次独立basetemp/JUnit/stdout/stderr/退出码，fixtures及cache/snapshots/审计都留此新basetemp。不删除/覆盖旧证据、不安装全局依赖。
4. 只使用合成数据。真实ERP字段映射未知时完整316范围仍不成立；B过滤未证禁启。mock通过不证明现网过滤或字段语义，#538/#539各保持既有范围。ff/push、真实源、专业口径、生产/外发均另审。

---

# SC2 收货 BizType316 子集 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. All steps are unchecked; none was implemented or tested in this planning turn.

**Goal:** 为 SC2 新建显式 `biztype316-v1` 收货范围，使四项已批准指标及对应明细只用可证的 BizType316 cohort，同时保留普通共享收货集、旧冻结和旧缓存。

**Architecture:** Connector 提供带原始字段缺口与分页证据的 receipt batch；SC2 只用完整、语义经证的逐行类型走本地派生 A，B 在本变更仅保留 fail-closed guard 与合成分支测试，现无服务端过滤证据时不从 SC2 真实源发过滤请求。新的 `fetch_scoped()` 在一次取数中成对返回普通全量 `FrozenDataset` 与 `ReceiptScopeResult`；三窗口各自按现有 inclusive `Window.start <= receipt_date <= Window.end` 过滤 scope。显式 scope refresh 写 versioned dataset/report pair；HTML/API/detail/CSV 仅读取该版本且绝不 fallback。普通 report/cache identity 与旧序列化保持原样。

**Tech Stack:** Python dataclass、现有 ERP Connector、SC2 纯函数指标/明细层、pytest 合成 fixtures、JSON snapshot/cache。

**Spec:** `openspec/changes/sc2-biztype316-receipts/design.md`（Shao Peishen 已明确批准 D1–D10；approved 内容 SHA-256 `38E3BB0CE2DB024BF85BBC543E8997D14827C1CEBD679F75B9F6DCA017FE624D`，计划准备时只读复核一致；设计文件状态行不由本计划修改）、`openspec/changes/sc2-biztype316-receipts/specs/sc2-receipts-biztype316/spec.md`、`openspec/changes/sc2-biztype316-receipts/tasks.md`。

## Global Constraints

- API 省略 `bizType` 仍不筛选；不得把 unfiltered response 称为 316。
- A 仅在请求未过滤（`requested_biz_type is None`、`filter_applied is not True`）、所有候选行均有语义经证且可按批准的 `int | str | None` contract 规范化的逐行类型（原生整数除 `bool`，或严格完整 ASCII 整数字符串）、窗口成员资格完整且分页完整时按 `BizType == 316` 本地派生；不得把任意字符串/浮点强转或按单号前缀推断。
- B 在独立服务端过滤能力证据和全分页验证都缺失时默认禁用；mock 不能证明现网过滤生效。
- 只有 `receipt_line_count`、`receipt_qty`、`receipt_amount`、`receipt_supplier_count` 及对应明细读取 316 subset；共享 `dataset.receipts` 与其它收货派生指标继续保持全量旧语义。
- 缺数量影响数量/金额；缺单价只影响金额；缺供应商名只影响供应商数。类型成员资格、BusinessDate 窗口成员资格或分页不完整会使受影响范围的四指标及明细不完整；不得把缺项折为 0。
- 不改旧共享 `ReceiptRecord` 字段、类型或默认值；不回填旧 schema，不重算、覆盖或重命名旧冻结/缓存。新范围显式使用 `__biztype316-v1` identity，旧 `DATASET_SCHEMA=1` 数据不得被当成 316。
- 保持 GR/Query 当前返回行与 BusinessDate 纳入行为；不新增退货、作废、冲销或状态排除规则，不硬编码 `Org=Z`。
- 新连接器批次仍经现有 `_fi_request` 与 ConnectorAudit 入口；不旁路现有入口审计，也不另造专业/业务签认标准。scope UI 只复用 SC2 已有访问与复核边界，不改发布复核流程。
- 只使用 `MOCK-*` 合成数据，不查询 ERP/SRM 真实库、不读取凭据。不得把真实快照写进仓库。
- Native mock 实施仍要求 formal design 审批记录写回、获批的具体实施计划/文件白名单及项目规定的隔离执行授权；此计划本身不授权产品代码或测试。
- 不处理 SC2 恢复候选、发布、ff、部署、外发或 #538 收口；这些事项不属于本变更。
- 不手工 commit。实施完成后按规则 acquire lock 并登记 §二；只在项目已配置的正式执行环境确实提供受支持的 `CommitSweep` 时才交给它承接。不得在候选树或临时工作目录直接运行主仓 `CommitSweep`；若正式登记/承接入口不可用，停在已登记状态并交由 Shao Peishen 裁定。

## Review Focus

1. **类型/过滤成员资格不完整**：省略参数、缺 BizType、语义未证、filter-not-applied 或分页不完整时必须标 scope 未证，不能产完整 316 值。由 Task 2 的 source contract 与 Task 1 的 connector batch tests 覆盖。
2. **混合业务类型与共享指标串污染**：316/326/449 混合 rows 时仅四项及匹配 detail 使用316，其它收货指标仍消费 `dataset.receipts` 全量。由 Task 3 的 metrics tests 与 Task 4 的 detail tests 覆盖。
3. **字段缺失和窗口边界**：数量/单价/供应商缺失分别局限到依赖指标；缺 BusinessDate 或窗口/分页成员资格不明时不静默丢行、不输出完整合计。由 Task 2 的 source tests 和 Task 3 的 metric tests 覆盖。
4. **旧 schema、冻结文件和旧 cache**：schema 1、无类型缓存、同周期旧 snapshot 不得满足新 scope、被回写或重算。由 Task 1 的 cache tests 和 Task 5 的 snapshot/cache/report tests 覆盖。
5. **组织、状态、日期和 UI 明示**：scope 记录观察到的组织来源、沿用当前返回行/BusinessDate 规则；缺失证据按范围标记，不应用 Org=Z 或新状态排除；现 UI 明确标 316 与不足原因。由 Task 2 的 source tests、Task 4 的 detail tests、Task 5 的 web tests 覆盖。

## Exact File Scope

实施计划最多触碰以下 14 个产品文件；未列文件不因方便而顺手修改。范围数固定：platform 2 个产品模块+1个测试；SC2 7 个产品模块+4个既有测试。新增分页测试仍放入已列 platform 测试文件，不增加第15路径。

**Platform connector**

- Modify `5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/models.py`：给 `ReceiptLine` 增加可空业务类型字段及分页/批次证据类型；旧构造调用保持有效。旧 `get_receipt_lines()` JSON 序列化仍显式写原字段集合，不得将新 `biz_type` 写入旧缓存。
- Modify `5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/erp_connector/connector.py`：提供 receipt batch/分页证据和隔离 cache identity；本 change 的真实源调用不传 `biz_type`，避免无证过滤。`get_receipt_batch` 可为合成 B 分支接受请求参数，但生产 source 不调用该分支；旧 `get_receipt_lines(days=...)` 默认行为、旧键和旧 JSON 字段集合保持原样。
- Create `5-平台底座/zhuopin_platform/tests/test_erp_biztype316.py`：专用合成测试文件。已读 `pyproject.toml` 确认 pytest dev dependency 且无自定义 pytest 配置；已读 `tests/conftest.py` 确认它负责 bootstrap 路径并自动拦截真实网络。该路径在既有测试收集目录内。

**SC2 scene**

- Modify `4-数字员工/采购部/SC2-采购周报自动生成/sc2/models.py`：新增 scope evidence/result 类型，不更改 `ReceiptRecord`、`FrozenDataset.receipts` 的既有字段/默认语义。
- Modify `4-数字员工/采购部/SC2-采购周报自动生成/sc2/sources.py`：构建 typed batch、A 本地派生、B fail-closed、缺口与字段完整性证据。
- Modify `4-数字员工/采购部/SC2-采购周报自动生成/sc2/metrics.py`：仅四个目标指标可读取可选 scope；其余 `_SPECS` 保持 `dataset.receipts`。
- Modify `4-数字员工/采购部/SC2-采购周报自动生成/sc2/detail.py`：316收货明细、对账和 scoped dataset snapshot 使用同一 subset/window；保留旧 serializer 和旧 `DATASET_SCHEMA=1` reader。
- Modify `4-数字员工/采购部/SC2-采购周报自动生成/sc2/config.py`：在 scope 参数非空时返回版本化新 snapshot/cache identity；默认参数仍返回原路径。
- Modify `4-数字员工/采购部/SC2-采购周报自动生成/sc2/report.py`：在明确 scope 下生成四指标 scoped report、版本化 snapshot 和可读缺口标注；旧路径仍按原参数保存。
- Modify `4-数字员工/采购部/SC2-采购周报自动生成/sc2/webapp.py`：增加显式 `scope=biztype316-v1` 读取/明细链接与标签；缺 scope 参数时保持普通既有报表，不重设计页面。
- Modify `4-数字员工/采购部/SC2-采购周报自动生成/tests/test_sources.py`。
- Modify `4-数字员工/采购部/SC2-采购周报自动生成/tests/test_metrics.py`。
- Modify `4-数字员工/采购部/SC2-采购周报自动生成/tests/test_detail.py`。
- Modify `4-数字员工/采购部/SC2-采购周报自动生成/tests/test_report.py`。

### Interfaces Shared Between Tasks

以这组 additive interfaces 串联后续任务；实现时名称/类型只允许在 design 与本计划获批后共同更新：

```python
@dataclass(frozen=True)
class ReceiptPageEvidence:
    pages_read: int
    rows_read: int
    reported_total: int | None
    pagination_complete: bool


@dataclass(frozen=True)
class ReceiptSourceFieldMap:
    map_id: str
    biz_type_key: str


@dataclass(frozen=True)
class ReceiptBatchRow:
    line: ReceiptLine
    missing_fields: frozenset[str]     # raw-source gaps captured before ReceiptLine defaults


@dataclass(frozen=True)
class ReceiptBatch:
    rows: tuple[ReceiptBatchRow, ...]
    requested_biz_type: int | None
    filter_applied: bool | None
    page_evidence: ReceiptPageEvidence
    source_field_map_id: str | None
    capability_id: str | None
    organization_source: str | None


@dataclass(frozen=True)
class ReceiptScopeCapability:
    capability_id: str                 # approved, evidence-backed source capability
    source_field_map_id: str | None
    type_semantics_verified: bool
    server_filter_verified: bool


@dataclass(frozen=True)
class ReceiptScopeRow:
    record: ReceiptRecord
    missing_fields: frozenset[str]     # names from qty_received/unit_price/supplier_name


@dataclass(frozen=True)
class ReceiptScopeEvidence:
    scope_id: str                    # exactly "biztype316-v1"
    method: str                      # exactly "typed_rows" or "verified_server_filter"
    type_semantics_verified: bool
    filter_verified: bool
    pagination_complete: bool
    organization_source: str | None
    missing_fields: tuple[str, ...]    # batch/global gaps only; row gaps stay per ReceiptScopeRow
    completeness_reason: str


@dataclass(frozen=True)
class ReceiptScopeResult:
    rows: tuple[ReceiptScopeRow, ...]  # exact 316 rows; empty if membership incomplete
    evidence: ReceiptScopeEvidence
    complete: bool


class ReceiptBatchSource(Protocol):
    def get_receipt_batch(
        self, days: int = 90, *, biz_type: int | None = None,
        field_map: ReceiptSourceFieldMap | None = None,
        capability_id: str | None = None,
    ) -> ReceiptBatch: ...


def derive_receipt_scope_316(
    batch: ReceiptBatch, capability: ReceiptScopeCapability | None = None,
) -> ReceiptScopeResult: ...


class Feed(Protocol):
    def fetch(self, windows: WindowSet) -> FrozenDataset: ...
    def fetch_scoped(
        self, windows: WindowSet, *,
        capability: ReceiptScopeCapability | None = None,
    ) -> tuple[FrozenDataset, ReceiptScopeResult]: ...
```

`ReceiptSourceFieldMap`, `ReceiptBatchRow`, `ReceiptPageEvidence`, and `ReceiptBatch` belong to platform `shared_tools/models.py`; SC2 `ReceiptScopeCapability`, `ReceiptScopeRow`, `ReceiptScopeEvidence`, and `ReceiptScopeResult` belong to `sc2/models.py`. Current live setup passes no source field map, so raw BizType is not inferred. `ReceiptScopeCapability` is an **evidence input**, not a conclusion inferred from request success. `fetch_scoped()` never invents or loads a real mapping/capability: its default is no map/no capability, hence incomplete scope; it issues no BizType-filtered ERP request. Synthetic tests may construct a map/capability to exercise A and the isolated B guard, but those values never enter runtime defaults or authorize live use. `ReceiptScopeRow.missing_fields` preserves per-row field gaps so metric completeness can be decided independently.

`compute_metrics(dataset, windows, *, receipt_scope=None, thresholds=None, thresholds_confirmed=False, caliber_confirmed=False) -> tuple[Metric, ...]` is the Task 3 implementation signature; it remains a pure function. `build_report` and persistence signatures are specified exactly in Task 5.

---

### Task 1: Connector receipt batch, BizType propagation, and isolated cache identity

**Files:**

- Modify: `5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/models.py`
- Modify: `5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/erp_connector/connector.py`
- Create: `5-平台底座/zhuopin_platform/tests/test_erp_biztype316.py`

**Interfaces:**

- Consumes: existing `ZpConnector._gr_query_all()` pagination and `ReceiptLine` fields; legacy `get_receipt_lines(days=90)` remains callable as before.
- Produces: platform `ReceiptBatch` from `get_receipt_batch(days=90, *, biz_type=None, field_map=None, capability_id=None)`. This change's SC2 source always passes all three evidence/request values as `None`; synthetic connector tests may supply them. An omitted `biz_type` emits no type-filter parameter. Any explicit filter is only a request and cannot imply `filter_applied=True`. `ReceiptBatchRow.missing_fields` captures raw gaps before legacy defaults. Preserve the approved `ReceiptLine.biz_type: int | str | None` interface: accept native integers excluding `bool`, or a complete ASCII base-10 integer string such as `"316"` and normalize it to `int`; do not trim/coerce arbitrary strings, floats, decimals, booleans, malformed values, or fractional values. Those become a BizType evidence gap. Missing quantity/price is recorded before the legacy row's zero default; malformed, boolean, NaN/infinite, or nonnumeric quantity/price is rejected with `ValueError`, never converted to zero. A supplied `ReceiptSourceFieldMap(map_id, biz_type_key)` controls mapping; absent map returns `ReceiptLine.biz_type=None` and `source_field_map_id=None`. `organization_source` records only the connector's configured source org; it must never synthesize `Org=Z`.

- [ ] **Step 1: Add failing synthetic connector tests**

The test module imports `json`, `pytest`, `ZpConnector` from `zhuopin_platform.shared_tools.erp_connector.connector`, and receipt evidence models from `zhuopin_platform.shared_tools.models`. Batch mapping/cache unit tests may monkeypatch the typed reader. The separate pagination tests below exercise the actual `_gr_query_all_with_evidence()` loop and replace only `_fi_request`; they must not monkeypatch the page reader. Factories use `ZpConnector.__new__`, `_po_cache_file = tmp_path / "po-cache.json"`, `_org_code = "SYNTHETIC-ORG"`, and `_gr_cache = {}`; they never construct live credentials or use network/runtime data.

```python
def _connector(monkeypatch, tmp_path):
    connector = ZpConnector.__new__(ZpConnector)
    connector._gr_cache = {}
    connector._po_cache_file = tmp_path / "po-cache.json"
    connector._org_code = "SYNTHETIC-ORG"
    calls = []
    rows = [
        {"RcvDocNo": "MOCK-A", "DocLineNo": "1", "SrcDocNo": "PO-A",
         "SrcDocLineNo": "1", "ItemCode": "ITEM-A", "ItemName": "Item A",
         "BusinessDate": "2026-10-01", "RcvQtyTU": 2, "FinalPriceTC": 3,
         "SupplierName": "Supplier A", "BizType": 316},
        {"RcvDocNo": "MOCK-B", "DocLineNo": "1", "SrcDocNo": "PO-B",
         "SrcDocLineNo": "1", "ItemCode": "ITEM-B", "ItemName": "Item B",
         "BusinessDate": "2026-10-02", "RcvQtyTU": 4, "FinalPriceTC": 5,
         "SupplierName": "Supplier B", "BizType": 316},
    ]
    def query_all(**kwargs):
        calls.append(kwargs)
        return rows, ReceiptPageEvidence(1, len(rows), len(rows), True)
    monkeypatch.setattr(connector, "_gr_query_all", lambda: rows)
    monkeypatch.setattr(connector, "_gr_query_all_with_evidence", query_all)
    return connector, calls


def test_省略biztype保持全表请求且旧接口仍可用(monkeypatch, tmp_path):
    connector, calls = _connector(monkeypatch, tmp_path)
    batch = connector.get_receipt_batch(days=90)
    assert batch.requested_biz_type is None
    assert calls[0]["biz_type_request"] is None
    assert batch.page_evidence.pagination_complete
    assert batch.source_field_map_id is None
    assert batch.rows[0].line.biz_type is None
    assert "biz_type" in batch.rows[0].missing_fields


def test_只按显式字段映射读取合成BizType(monkeypatch, tmp_path):
    connector, _ = _connector(monkeypatch, tmp_path)
    field_map = ReceiptSourceFieldMap("synthetic-field-map-v1", "BizType")
    batch = connector.get_receipt_batch(days=90, field_map=field_map)
    assert batch.source_field_map_id == "synthetic-field-map-v1"
    assert batch.rows[0].line.biz_type == 316
    assert "biz_type" not in batch.rows[0].missing_fields


def test_更换fieldmap或capability不会命中旧映射缓存(monkeypatch, tmp_path):
    connector, _ = _connector(monkeypatch, tmp_path)
    first = connector.get_receipt_batch(
        days=90, field_map=ReceiptSourceFieldMap("map-a", "BizType"),
        capability_id="cap-a")
    second = connector.get_receipt_batch(
        days=90, field_map=ReceiptSourceFieldMap("map-b", "OtherType"),
        capability_id="cap-b")
    assert first.rows[0].line.biz_type == 316
    assert second.rows[0].line.biz_type is None
    assert second.source_field_map_id == "map-b"
    assert len(list(tmp_path.glob("gr_lines_90d__biztype316-v1__*.json"))) == 2


def test_显式316参数仅记录请求不伪称服务端已过滤(monkeypatch, tmp_path):
    connector, calls = _connector(monkeypatch, tmp_path)
    batch = connector.get_receipt_batch(days=90, biz_type=316)
    assert calls[0]["biz_type_request"] == 316
    assert batch.filter_applied is None


@pytest.mark.parametrize("raw_type", ["316", "+316"])
def test_严格整数字符串BizType规范化(monkeypatch, tmp_path, raw_type):
    connector, _ = _connector(monkeypatch, tmp_path)
    connector._gr_query_all_with_evidence = lambda **_kwargs: ([{
        "RcvDocNo": "MOCK-STRING-TYPE", "DocLineNo": "1", "BusinessDate": "2026-10-01",
        "RcvQtyTU": 1, "FinalPriceTC": 2, "SupplierName": "Synthetic", "BizType": raw_type,
    }], ReceiptPageEvidence(1, 1, 1, True))
    batch = connector.get_receipt_batch(
        days=90, field_map=ReceiptSourceFieldMap("synthetic-field-map-v1", "BizType"))
    assert batch.rows[0].line.biz_type == 316
    assert "biz_type" not in batch.rows[0].missing_fields


@pytest.mark.parametrize("raw_type", ["bad", "316.0", " 316", "316 ", "٣١٦", True, 316.0, 316.5])
def test_非法或非整数合同BizType保留缺口不静默当作非316(monkeypatch, tmp_path, raw_type):
    connector, _ = _connector(monkeypatch, tmp_path)
    field_map = ReceiptSourceFieldMap("synthetic-field-map-v1", "BizType")
    connector._gr_query_all_with_evidence = lambda **_kwargs: ([{
        "RcvDocNo": "MOCK-BAD-TYPE", "DocLineNo": "1", "BusinessDate": "2026-10-01",
        "RcvQtyTU": 1, "FinalPriceTC": 2, "SupplierName": "Synthetic",
        "BizType": raw_type,
    }], ReceiptPageEvidence(1, 1, 1, True))
    batch = connector.get_receipt_batch(days=90, field_map=field_map)
    assert batch.rows[0].line.biz_type is None
    assert "biz_type" in batch.rows[0].missing_fields


@pytest.mark.parametrize("raw_number", [True, "NaN", float("nan"), "Infinity", "not-a-number", 1e309])
@pytest.mark.parametrize("source_field", ["RcvQtyTU", "FinalPriceTC"])
def test_坏数量单价拒绝而不伪造零(monkeypatch, tmp_path, raw_number, source_field):
    connector, _ = _connector(monkeypatch, tmp_path)
    connector._gr_query_all_with_evidence = lambda **_kwargs: ([{
        "RcvDocNo": "MOCK-BAD-NUMBER", "DocLineNo": "1", "BusinessDate": "2026-10-01",
        "RcvQtyTU": 1, "FinalPriceTC": 2, "SupplierName": "Synthetic",
        "BizType": 316, source_field: raw_number,
    }], ReceiptPageEvidence(1, 1, 1, True))
    field_map = ReceiptSourceFieldMap("synthetic-field-map-v1", "BizType")
    with pytest.raises(ValueError, match="非有限或不可解析"):
        connector.get_receipt_batch(days=90, field_map=field_map)


@pytest.mark.parametrize("source_field,expected_gap", [
    ("RcvQtyTU", "qty_received"), ("FinalPriceTC", "unit_price")])
@pytest.mark.parametrize("raw_number", [None, ""])
def test_缺数量或单价保留缺口而非宣称零证据(
        monkeypatch, tmp_path, source_field, expected_gap, raw_number):
    connector, _ = _connector(monkeypatch, tmp_path)
    connector._gr_query_all_with_evidence = lambda **_kwargs: ([{
        "RcvDocNo": "MOCK-MISSING-NUMBER", "DocLineNo": "1", "BusinessDate": "2026-10-01",
        "RcvQtyTU": 1, "FinalPriceTC": 2, "SupplierName": "Synthetic",
        "BizType": 316,
        source_field: raw_number,
    }], ReceiptPageEvidence(1, 1, 1, True))
    field_map = ReceiptSourceFieldMap("synthetic-field-map-v1", "BizType")
    batch = connector.get_receipt_batch(days=90, field_map=field_map)
    assert expected_gap in batch.rows[0].missing_fields


@pytest.mark.parametrize("raw_date", ["0000-01-01", "bad-ISO", "2026-02-30", None, ""])
def test_缺失或非法BusinessDate保留为候选并带缺口(monkeypatch, tmp_path, raw_date):
    connector, _ = _connector(monkeypatch, tmp_path)
    connector._gr_query_all_with_evidence = lambda **_kwargs: ([{
        "RcvDocNo": "MOCK-BAD-DATE", "DocLineNo": "1", "BusinessDate": raw_date,
        "RcvQtyTU": 1, "FinalPriceTC": 2, "SupplierName": "Synthetic", "BizType": 316,
    }], ReceiptPageEvidence(1, 1, 1, True))
    field_map = ReceiptSourceFieldMap("synthetic-field-map-v1", "BizType")
    batch = connector.get_receipt_batch(days=90, field_map=field_map)
    assert len(batch.rows) == 1
    assert batch.rows[0].line.receipt_date is None
    assert "BusinessDate" in batch.rows[0].missing_fields


def test_旧cache与316scope使用不同身份(monkeypatch, tmp_path):
    connector, _ = _connector(monkeypatch, tmp_path)
    connector.get_receipt_lines(days=90)
    connector.get_receipt_batch(days=90, biz_type=316)
    assert (tmp_path / "gr_lines_90d.json").exists()
    assert len(list(tmp_path.glob("gr_lines_90d__biztype316-v1__*.json"))) == 1


def test_cache_identity绑定days_type_fieldmap_capability():
    identities = [
        ZpConnector._receipt_batch_cache_identity(90, None, "map-a", "cap-a"),
        ZpConnector._receipt_batch_cache_identity(30, None, "map-a", "cap-a"),
        ZpConnector._receipt_batch_cache_identity(90, 316, "map-a", "cap-a"),
        ZpConnector._receipt_batch_cache_identity(90, None, "map-b", "cap-a"),
        ZpConnector._receipt_batch_cache_identity(90, None, "map-a", "cap-b"),
    ]
    assert len(set(identities)) == 5


def test_旧ReceiptLine缓存仍只写旧字段集合(monkeypatch, tmp_path):
    connector, _ = _connector(monkeypatch, tmp_path)
    connector._gr_query_all = lambda: [{
        "RcvDocNo": "MOCK-OLD", "DocLineNo": "1", "SrcDocNo": "PO-OLD",
        "SrcDocLineNo": "1", "ItemCode": "ITEM-OLD", "ItemName": "Old item",
        "BusinessDate": "2099-01-01", "RcvQtyTU": 2, "FinalPriceTC": 3,
        "SupplierName": "Supplier old", "BizType": 316,
    }]
    connector.get_receipt_lines(days=99999)
    payload = json.loads((tmp_path / "gr_lines_99999d.json").read_text(encoding="utf-8"))
    assert set(payload[0]) == {
        "receipt_doc_no", "line_no", "po_id", "po_line_no", "material_id",
        "material_name", "qty_received", "receipt_date", "supplier_name", "unit_price",
    }
    assert "biz_type" not in payload[0]


def _page_reader(monkeypatch, pages, *, page_size=2):
    connector = ZpConnector.__new__(ZpConnector)
    connector._GR_PAGE_SIZE = page_size
    calls = []
    def fake_fi_request(endpoint, params):
        calls.append((endpoint, dict(params)))
        item = pages[params["page"] - 1]
        if isinstance(item, Exception):
            raise item
        return {"Data": item}
    monkeypatch.setattr(connector, "_fi_request", fake_fi_request)
    return connector, calls


def test真实分页循环_稳定Total多页精确匹配才完整(monkeypatch):
    connector, calls = _page_reader(monkeypatch, [
        {"Rows": [{"id": "A"}, {"id": "B"}], "Total": 3},
        {"Rows": [{"id": "C"}], "Total": 3},
    ])
    rows, evidence = connector._gr_query_all_with_evidence()
    assert [row["id"] for row in rows] == ["A", "B", "C"]
    assert evidence.pages_read == 2 and evidence.rows_read == 3
    assert evidence.reported_total == 3 and evidence.pagination_complete is True
    assert len(calls) == 2 and all(path == "/zp/api/GR/Query" for path, _ in calls)


def test真实分页循环_Total缺失短页结束但不完整(monkeypatch):
    connector, _ = _page_reader(monkeypatch, [{"Rows": [{"id": "A"}]}])
    rows, evidence = connector._gr_query_all_with_evidence()
    assert len(rows) == 1
    assert evidence.reported_total is None and evidence.pagination_complete is False


def test真实分页循环_提前空页或Total变化均不完整(monkeypatch):
    early, _ = _page_reader(monkeypatch, [
        {"Rows": [{"id": "A"}, {"id": "B"}], "Total": 3},
        {"Rows": [], "Total": 3},
    ])
    assert not early._gr_query_all_with_evidence()[1].pagination_complete
    changed, _ = _page_reader(monkeypatch, [
        {"Rows": [{"id": "A"}, {"id": "B"}], "Total": 3},
        {"Rows": [{"id": "C"}], "Total": 4},
    ])
    assert not changed._gr_query_all_with_evidence()[1].pagination_complete


def test真实分页循环_明确空Total为零完整且请求异常传播(monkeypatch):
    empty, _ = _page_reader(monkeypatch, [{"Rows": [], "Total": 0}])
    rows, evidence = empty._gr_query_all_with_evidence()
    assert rows == [] and evidence.reported_total == 0
    assert evidence.pagination_complete is True
    failing, _ = _page_reader(monkeypatch, [RuntimeError("synthetic connector failure")])
    with pytest.raises(RuntimeError, match="synthetic connector failure"):
        failing._gr_query_all_with_evidence()
```

- [ ] **Step 2: Run only the new connector tests**

Run from `5-平台底座/zhuopin_platform`:

```powershell
& 'C:\Dev\Codex\runtimes\zhuopin-ai\venv\Scripts\python.exe' -B -m pytest -p no:cacheprovider 'tests/test_erp_biztype316.py' -q
```

Expected: initial tests fail on missing `get_receipt_batch` / isolated cache identity; there are no ERP credentials or network calls in these tests.

- [ ] **Step 3: Add optional row type and evidence without changing legacy reads**

Add `biz_type: int | str | None = None` to platform `ReceiptLine`; add immutable `ReceiptBatchRow`, `ReceiptPageEvidence`, and `ReceiptBatch`. Capture raw absence of BizType, BusinessDate, quantity, unit price, and supplier name before legacy defaults. Accept a mapped BizType only when it is an exact native integer excluding `bool`, or a full ASCII base-10 integer string matching `[+-]?[0-9]+`; normalize that string to integer. Do not trim arbitrary input or coerce floats/decimals. Any other nonempty raw type becomes `biz_type=None` plus `missing_fields += {"biz_type"}` so it cannot be silently treated as a known non-316 value. For quantity and price, `None`/empty remains an explicit missing-field gap (the legacy `ReceiptLine` placeholder may remain zero only for old shared consumers; no complete scoped metric may use that placeholder). Reject boolean, unparseable, NaN/infinite, or float-overflow numeric input with `ValueError`. Keep `_gr_query_all()` unchanged. Add `_gr_query_all_with_evidence(*, biz_type_request=None)` with an explicit loop: request `{page, pageSize}` from `/zp/api/GR/Query` and add `bizType` only when explicitly given; every response must contain a list `Rows`; count every requested page; preserve `Total` only if every page has the same non-negative integer; stop at total reached, explicit zero total, empty page, or short page. Mark complete only when every page agrees on explicit total and `rows_read == Total`. Missing/invalid/changing Total, early empty/short page, over-count, or request exception never marks complete; exceptions propagate. Do not fall back to the legacy reader.

Add `get_receipt_batch(days=90, *, biz_type=None, field_map=None, capability_id=None)` as a versioned path. Preserve unknown-BusinessDate candidates in evidence and map type only through the passed `ReceiptSourceFieldMap`. Cache identity is the canonical tuple `(scope_id, days, biz_type, field_map.map_id or "unmapped", capability_id or "unverified")`; use its SHA-256 prefix in both memory key and filename `gr_lines_{days}d__biztype316-v1__{identity_sha256[:16]}.json`. Thus alternate days/type/map/capability never share mapped results. SC2's real-source call passes `None` for filter/map/capability. Keep old cache key and exact JSON field list by replacing legacy `r.__dict__` cache serialization with an explicit mapping of its pre-change fields; do not rewrite/rename/clear old cache files. A filter request in synthetic tests remains only a request, never proof of application.

Use this exact identity and old serializer implementation (add `import hashlib`; `json` is already used by connector):

```python
@staticmethod
def _receipt_batch_cache_identity(days, biz_type, field_map_id, capability_id):
    identity = ["biztype316-v1", int(days), biz_type,
                field_map_id or "unmapped", capability_id or "unverified"]
    payload = json.dumps(identity, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

@staticmethod
def _legacy_receipt_dict(row):
    return {
        "receipt_doc_no": row.receipt_doc_no, "line_no": row.line_no,
        "po_id": row.po_id, "po_line_no": row.po_line_no,
        "material_id": row.material_id, "material_name": row.material_name,
        "qty_received": row.qty_received, "receipt_date": row.receipt_date,
        "supplier_name": row.supplier_name, "unit_price": row.unit_price,
    }
```

The in-memory key is `gr_batch:{identity_sha256}` and filename is `gr_lines_{days}d__biztype316-v1__{identity_sha256[:16]}.json`. New-cache JSON stores the `ReceiptBatch` evidence and mapped rows for that exact identity; a cache hit reconstructs that same identity, never merely by `days`.

The page-reader loop contract is pinned by the tests above; its complete control flow is:

```python
def _gr_query_all_with_evidence(self, *, biz_type_request=None):
    all_rows = []
    page = 1
    total_seen = False
    total_consistent = True
    agreed_total = None
    while True:
        params = {"page": page, "pageSize": self._GR_PAGE_SIZE}
        if biz_type_request is not None:
            params["bizType"] = biz_type_request
        body = self._fi_request("/zp/api/GR/Query", params)
        data = body.get("Data")
        if not isinstance(data, dict) or not isinstance(data.get("Rows"), list):
            raise ValueError("GR/Query 响应缺少 Data.Rows 列表")
        rows = data["Rows"]
        page_total = data.get("Total") if "Total" in data else None
        valid_total = (isinstance(page_total, int) and not isinstance(page_total, bool)
                       and page_total >= 0)
        if not valid_total:
            total_consistent = False
        elif not total_seen:
            agreed_total = page_total
            total_seen = True
        elif page_total != agreed_total:
            total_consistent = False
        all_rows.extend(rows)
        if valid_total and page_total == 0 and not rows:
            break
        if valid_total and len(all_rows) >= page_total:
            break
        if not rows or len(rows) < self._GR_PAGE_SIZE:
            break
        page += 1
    reported_total = agreed_total if total_seen and total_consistent else None
    complete = (reported_total is not None and len(all_rows) == reported_total)
    evidence = ReceiptPageEvidence(
        pages_read=page, rows_read=len(all_rows), reported_total=reported_total,
        pagination_complete=complete)
    return all_rows, evidence
```

`get_receipt_lines()` must call `_legacy_receipt_dict()` when writing its old cache; do not change old filenames or cached row interpretation.

The new cache is versioned and mapped, so serialize its identity and every evidence field explicitly:

```python
def _receipt_batch_to_dict(batch, identity):
    return {
        "schema": 1, "identity": identity,
        "requested_biz_type": batch.requested_biz_type,
        "filter_applied": batch.filter_applied,
        "page_evidence": {
            "pages_read": batch.page_evidence.pages_read,
            "rows_read": batch.page_evidence.rows_read,
            "reported_total": batch.page_evidence.reported_total,
            "pagination_complete": batch.page_evidence.pagination_complete,
        },
        "source_field_map_id": batch.source_field_map_id,
        "capability_id": batch.capability_id,
        "organization_source": batch.organization_source,
        "rows": [{"line": _receipt_line_to_dict(row.line),
                  "missing_fields": sorted(row.missing_fields)} for row in batch.rows],
    }


def _receipt_line_to_dict(line):
    return {
        "receipt_doc_no": line.receipt_doc_no, "line_no": line.line_no,
        "po_id": line.po_id, "po_line_no": line.po_line_no,
        "material_id": line.material_id, "material_name": line.material_name,
        "qty_received": line.qty_received, "receipt_date": line.receipt_date,
        "supplier_name": line.supplier_name, "unit_price": line.unit_price,
        "biz_type": line.biz_type,
    }


def _receipt_batch_from_dict(data, expected_identity):
    if data.get("schema") != 1 or data.get("identity") != expected_identity:
        raise ValueError("receipt batch cache identity/schema mismatch")
    evidence = data["page_evidence"]
    return ReceiptBatch(
        rows=tuple(ReceiptBatchRow(
            line=ReceiptLine(**row["line"]),
            missing_fields=frozenset(row["missing_fields"])) for row in data["rows"]),
        requested_biz_type=data["requested_biz_type"],
        filter_applied=data["filter_applied"],
        page_evidence=ReceiptPageEvidence(
            pages_read=evidence["pages_read"], rows_read=evidence["rows_read"],
            reported_total=evidence["reported_total"],
            pagination_complete=evidence["pagination_complete"]),
        source_field_map_id=data["source_field_map_id"],
        capability_id=data["capability_id"],
        organization_source=data["organization_source"],
    )


def get_receipt_batch(self, days=90, *, biz_type=None, field_map=None,
                      capability_id=None):
    map_id = None if field_map is None else field_map.map_id
    identity = self._receipt_batch_cache_identity(
        days, biz_type, map_id, capability_id)
    cache_key = f"gr_batch:{identity}"
    cache_file = self._po_cache_file.parent / (
        f"gr_lines_{days}d__biztype316-v1__{identity[:16]}.json")
    now = time.time()
    cached = self._gr_cache.get(cache_key)
    if cached and now - cached[0] < self._GR_CACHE_TTL:
        return cached[1]
    if cache_file.exists() and now - cache_file.stat().st_mtime < self._GR_CACHE_TTL:
        try:
            batch = _receipt_batch_from_dict(
                json.loads(cache_file.read_text(encoding="utf-8")), identity)
            self._gr_cache[cache_key] = (now, batch)
            return batch
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass  # 新scope缓存损坏只影响该版本；保留旧全量缓存不动
    raw_rows, page_evidence = self._gr_query_all_with_evidence(
        biz_type_request=biz_type)
    cutoff = (datetime.now().date() - timedelta(days=days))
    rows = []
    for raw in raw_rows:
        raw_date = raw.get("BusinessDate")
        day = _strict_business_date(raw_date)
        date_missing = raw_date is None or str(raw_date).strip() == ""
        date_invalid = not date_missing and day is None
        if day is not None and day < cutoff:
            continue  # only a strictly parsed valid date can be excluded as outside lookback
        gaps = set()
        source_keys = {
            "biz_type": None if field_map is None else field_map.biz_type_key,
            "BusinessDate": "BusinessDate", "qty_received": "RcvQtyTU",
            "unit_price": "FinalPriceTC", "supplier_name": "SupplierName",
        }
        for field_name, source_key in source_keys.items():
            if source_key is None or source_key not in raw or raw[source_key] is None or raw[source_key] == "":
                gaps.add(field_name)
        if date_missing or date_invalid:
            gaps.add("BusinessDate")
        raw_type = None
        if field_map is not None and field_map.biz_type_key in raw:
            candidate_type = raw[field_map.biz_type_key]
            if type(candidate_type) is int:
                raw_type = candidate_type
            elif isinstance(candidate_type, str) and re.fullmatch(r"[+-]?[0-9]+", candidate_type):
                raw_type = int(candidate_type)
            else:
                gaps.add("biz_type")
        qty = _legacy_number_with_gap(raw.get("RcvQtyTU"), "RcvQtyTU", gaps, "qty_received")
        price = _legacy_number_with_gap(raw.get("FinalPriceTC"), "FinalPriceTC", gaps, "unit_price")
        line = ReceiptLine(
            receipt_doc_no=str(raw.get("RcvDocNo") or ""),
            line_no=str(raw.get("DocLineNo") or ""),
            po_id=str(raw.get("SrcDocNo") or ""),
            po_line_no=str(raw.get("SrcDocLineNo") or ""),
            material_id=str(raw.get("ItemCode") or ""),
            material_name=str(raw.get("ItemName") or ""),
            qty_received=qty,
            receipt_date=(day.isoformat() if day is not None else None),
            supplier_name=str(raw.get("SupplierName") or ""),
            unit_price=price, biz_type=raw_type)
        rows.append(ReceiptBatchRow(line=line, missing_fields=frozenset(gaps)))
    batch = ReceiptBatch(
        rows=tuple(rows), requested_biz_type=biz_type, filter_applied=None,
        page_evidence=page_evidence,
        source_field_map_id=map_id, capability_id=capability_id,
        organization_source=getattr(self, "_org_code", None))
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        cache_file.write_text(json.dumps(
            _receipt_batch_to_dict(batch, identity), ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass  # 缓存写失败不掩盖已完成的源查询结果
    self._gr_cache[cache_key] = (now, batch)
    return batch


def _strict_business_date(raw):
    """Return a real calendar date from an ISO date/datetime, else None; never slice malformed text."""
    if raw is None or str(raw).strip() == "":
        return None
    text = str(raw).strip()
    try:
        if len(text) == 10:
            return date.fromisoformat(text)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.date()
    except (TypeError, ValueError, OverflowError):
        return None


def _legacy_number_with_gap(raw, source_name, gaps, field_name):
    """Keep legacy missing-value storage, but preserve the gap; reject malformed numeric evidence."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        gaps.add(field_name)
        return 0.0  # legacy shared-row placeholder only; scope consumers must honor missing_fields
    if isinstance(raw, bool):
        raise ValueError(f"{source_name} 非有限或不可解析")
    try:
        value = float(raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{source_name} 非有限或不可解析") from exc
    if not math.isfinite(value):
        raise ValueError(f"{source_name} 非有限或不可解析")
    return value
```

`get_receipt_batch` is a class method placed on `ZpConnector`, not a module-level dotted `def`. Add `import hashlib`, `import math`, `import re`, and `from datetime import date`; the other listed imports (`json`, `time`, `datetime`, `timedelta`) are already used in this connector. This code keeps the scope endpoint call under the existing `_fi_request` audit path.

- [ ] **Step 4: Run the focused connector tests again**

Run the Task 1 command above. Expected: all batch, cache identity, legacy serializer, and actual page-loop tests pass; old no-parameter values, cache key, and serialized key set remain unchanged. Page-loop tests replace only `_fi_request`.

---

### Task 2: SC2 typed source wrapper and fail-closed scope derivation

**Files:**

- Modify: `4-数字员工/采购部/SC2-采购周报自动生成/sc2/models.py`
- Modify: `4-数字员工/采购部/SC2-采购周报自动生成/sc2/sources.py`
- Modify: `4-数字员工/采购部/SC2-采购周报自动生成/tests/test_sources.py`

**Interfaces:**

- Consumes: `ReceiptBatch` and `ReceiptLine.biz_type`; existing `RealFeed._fetch_receipts(windows)` and `FrozenDataset` remain available for legacy mode.
- Produces: `derive_receipt_scope_316(batch, capability=None) -> ReceiptScopeResult` and `Feed.fetch_scoped(windows, capability=None) -> tuple[FrozenDataset, ReceiptScopeResult]`. `RealFeed.fetch_scoped` calls `_fetch_order_lines` once and `get_receipt_batch(days=ERP_LOOKBACK_DAYS, field_map=None, capability_id=None)` once without a BizType filter. It converts that same batch to the unchanged full `dataset.receipts` and derives scope from the untrimmed batch so unknown-date candidates fail closed. A accepts only an unfiltered full batch (`requested_biz_type is None` and `filter_applied is not True`) with every mapped BizType normalizable from the approved `int | str | None` contract: native `int` excluding `bool`, or a full ASCII base-10 integer string such as `"316"`; B accepts only a requested `316` batch with `filter_applied is True` and independently verified, batch-matched server-filter capability. A filtered batch can never use A, and unfiltered rows can never be relabeled as B. Any unparseable type makes membership unknown and the complete scope stays closed. `MockFeed.fetch_scoped` returns its normal dataset plus an explicit incomplete result because its fixture has no typed evidence. Neither path replaces `FrozenDataset.receipts`.

- [ ] **Step 1: Add failing source tests using synthetic ReceiptBatch values**

Extend existing imports in `tests/test_sources.py` with `date` from `datetime`, `replace` from `dataclasses`, `ReceiptLine`, `ReceiptBatchRow`, `ReceiptBatch`, `ReceiptPageEvidence`, and `ReceiptScopeCapability` / `ReceiptScopeRow` / `ReceiptScopeEvidence` / `ReceiptScopeResult`; import `ERP_LOOKBACK_DAYS`, `MockFeed`, `RealFeed`, and `derive_receipt_scope_316` from `sc2.sources`, plus `build_windows`. All test inputs below are local synthetic objects; no ERP adapter is instantiated with credentials.

```python
from dataclasses import replace
import pytest


def _line(doc, biz_type, date="2026-10-01", qty=2, price=3, supplier="Supplier A",
          missing_fields=frozenset()):
    line = ReceiptLine(receipt_doc_no=doc, line_no="1", po_id="PO-" + doc,
                       po_line_no="1", material_id="ITEM-" + doc,
                       material_name="Synthetic item", qty_received=qty,
                       receipt_date=date, supplier_name=supplier, unit_price=price,
                       biz_type=biz_type)
    return ReceiptBatchRow(line=line, missing_fields=missing_fields)


def _batch(rows, *, verified=True, requested=None, applied=None, capability_id=None, pages=1,
           total=None, complete=True):
    return ReceiptBatch(
        rows=tuple(rows), requested_biz_type=requested, filter_applied=applied,
        page_evidence=ReceiptPageEvidence(
            pages, len(rows), len(rows) if total is None else total, complete),
        source_field_map_id="synthetic-field-map-v1" if verified else None,
        capability_id=capability_id,
        organization_source="synthetic-org",
    )


def _typed_capability():
    return ReceiptScopeCapability(
        capability_id="synthetic-typed-map-v1",
        source_field_map_id="synthetic-field-map-v1",
        type_semantics_verified=True, server_filter_verified=False)


def test_A按完整typed行派生316但共享receipts保留全量():
    typed_batch_mixed = _batch([_line("MOCK-316-A", 316), _line("MOCK-316-B", "316"),
                                _line("MOCK-326", 326), _line("MOCK-449", 449)])
    scope = derive_receipt_scope_316(typed_batch_mixed, _typed_capability())
    assert scope.complete
    assert {r.record.receipt_doc_no for r in scope.rows} == {"MOCK-316-A", "MOCK-316-B"}
    assert len(typed_batch_mixed.rows) == 4  # input batch remains mixed and unmodified


def test_A只能消费未过滤全量批次而不能冒充B():
    cap = replace(_typed_capability(), server_filter_verified=True)
    assert not derive_receipt_scope_316(
        _batch([_line("MOCK-316-A", 316)], requested=316, applied=False), cap).complete
    assert not derive_receipt_scope_316(
        _batch([_line("MOCK-316-A", 316)], requested=None, applied=True), cap).complete


@pytest.mark.parametrize("bad_type", ["bad", "316.0", True, 316.0, 316.5])
def test_无法解释的BizType不静默排除并标记完整性不足(bad_type):
    scope = derive_receipt_scope_316(
        _batch([_line("MOCK-INVALID-TYPE", bad_type)]), _typed_capability())
    assert not scope.complete and scope.rows == ()
    assert "BizType" in scope.evidence.completeness_reason


def test_缺任一候选BizType时scope关闭():
    batch_with_missing_type = _batch([_line("MOCK-316-A", 316), _line("MOCK-UNKNOWN", None)])
    scope = derive_receipt_scope_316(batch_with_missing_type, _typed_capability())
    assert not scope.complete
    assert scope.rows == ()
    assert "BizType" in scope.evidence.completeness_reason


def test_A字段虽存在但语义未验证仍关闭():
    unverified = replace(_typed_capability(), type_semantics_verified=False)
    assert not derive_receipt_scope_316(
        _batch([_line("MOCK-316-A", 316)]), unverified).complete


def test_B请求成功本身不构成已过滤证据():
    requested_only = _batch([_line("MOCK-316-A", 316)], verified=False,
                            requested=316, applied=None)
    b_capability = replace(_typed_capability(), server_filter_verified=True)
    assert not derive_receipt_scope_316(requested_only, b_capability).complete


def test_B需已验证过滤能力与filter_applied和完整分页():
    verified_filter_batch = _batch(
        [_line("MOCK-316-A", None, missing_fields=frozenset({"biz_type"}))],
        verified=False, requested=316, applied=True,
        capability_id="synthetic-verified-filter-v1", pages=1, total=1)
    capability = ReceiptScopeCapability(
        capability_id="synthetic-verified-filter-v1",
        source_field_map_id=None,
        type_semantics_verified=False, server_filter_verified=True)
    assert derive_receipt_scope_316(verified_filter_batch, capability).complete
    assert not derive_receipt_scope_316(verified_filter_batch).complete
    unverified_capability = replace(capability, server_filter_verified=False)
    incomplete_pages = replace(
        verified_filter_batch,
        page_evidence=ReceiptPageEvidence(1, 1, 2, False))
    assert not derive_receipt_scope_316(verified_filter_batch, unverified_capability).complete
    assert not derive_receipt_scope_316(incomplete_pages).complete


def test_真实source默认只取全量typed批次且共享集与scope同源(monkeypatch):
    windows = build_windows(date(2026, 10, 8))
    typed = _batch([_line("MOCK-316", 316, date=windows.current.start.isoformat()),
                    _line("MOCK-326", 326, date=windows.current.end.isoformat())])
    calls = []
    class FakeERP:
        def get_receipt_batch(self, **kwargs):
            calls.append(kwargs)
            return typed
    feed = RealFeed.__new__(RealFeed)
    feed._erp = FakeERP()
    feed.max_status_materials = 0
    feed.notes = []
    monkeypatch.setattr(feed, "_fetch_order_lines", lambda _windows: ())
    dataset, scope = feed.fetch_scoped(windows, capability=_typed_capability())
    assert calls == [{"days": ERP_LOOKBACK_DAYS, "field_map": None,
                      "capability_id": None}]
    assert {r.receipt_doc_no for r in dataset.receipts} == {"MOCK-316", "MOCK-326"}
    assert {r.record.receipt_doc_no for r in scope.rows} == {"MOCK-316"}


def test_mockfeed无类型证据时保存明确不完整scope而不补造316():
    windows = build_windows(date(2026, 10, 8))
    dataset, scope = MockFeed().fetch_scoped(windows)
    assert dataset.mode == "mock"
    assert not scope.complete and scope.rows == ()
    assert "BizType" in scope.evidence.completeness_reason


@pytest.mark.parametrize("bad_date", ["", None, "0000-01-01", "bad-ISO", "2026-02-30"])
def test_缺失或非法BusinessDate或分页不完整不得静默丢弃为完整scope(bad_date):
    batch_missing_date = _batch([_line("MOCK-316-A", 316, date=bad_date,
                                       missing_fields=frozenset({"BusinessDate"}))])
    scope = derive_receipt_scope_316(batch_missing_date, _typed_capability())
    assert not scope.complete
    assert "BusinessDate" in scope.evidence.completeness_reason
    incomplete_page = _batch([_line("MOCK-316-A", 316)], pages=1, total=2, complete=False)
    assert not derive_receipt_scope_316(incomplete_page).complete


```

- [ ] **Step 2: Run focused SC2 source tests**

Start from the approved candidate root `C:\Dev\zhuopin-ai`; the command itself resolves the scene directory absolutely so it cannot double-append the relative path:

```powershell
& 'C:\Dev\Codex\runtimes\zhuopin-ai\venv\Scripts\python.exe' -B -m pytest -p no:cacheprovider 'tests/test_sources.py' -q
```

Expected initially: the new `ReceiptScopeResult`/derivation tests fail; all existing legacy source tests remain in the same target file and must still pass after implementation.

- [ ] **Step 3: Implement immutable scope/evidence types and derivation**

Add only `ReceiptScopeCapability`, `ReceiptScopeRow`, `ReceiptScopeEvidence`, and `ReceiptScopeResult` to `sc2/models.py`; platform page/batch records stay in platform `shared_tools/models.py`. Add `fetch_scoped` to the Feed protocol and both feed implementations. Ensure `sc2/sources.py` imports `date`, `datetime`, and `re` from the standard library for its strict date and BizType parsers. `RealFeed.fetch_scoped` fetches orders once and one unfiltered typed batch; that batch is the sole receipt read used to produce both legacy shared rows and scope. Pass no production field map, capability ID, or filter; optional capability is supplied only by synthetic tests and is not loaded from environment/files/user assertions. A requires an unfiltered full batch, each candidate type normalizable from the approved `int | str | None` contract (native integer excluding `bool` or strict full ASCII integer string), a capability matching the batch map ID with verified semantics, valid BusinessDate membership, and complete pagination. B's pure guard branch is exclusive to `requested_biz_type == 316`, `filter_applied is True`, a capability whose ID matches `batch.capability_id` and whose server-filter behavior is verified, plus complete pagination; no source path invokes B and no runtime switch enables it. If either candidate type is not interpretable, membership is unknown and the complete scope stays closed instead of silently excluding that row. If neither route is proven, return `complete=False`, empty target rows, and a reason; never infer from prefixes or old untyped `ReceiptRecord`.

Record `batch.organization_source` and missing `BusinessDate` before any date-window discard. Do not claim an approved organization total unless the source org boundary is verified; do not synthesize Org=Z. Do not declare 316 completeness if an unknown-date candidate prevents proving membership. Keep missing quantity, unit price, and supplier name as explicit field gaps for Task 3. Keep the scope as the complete source candidate set across the three windows; do not pre-trim to one week. `dataset.receipts` remains the original unfiltered frozen collection for all legacy consumers.

Implement these complete source helpers in `sc2/sources.py`. `_receipt_record` copies the existing fields without changing shared model types. `_incomplete_scope` always returns empty rows, keeps the observed organization and named missing fields, and does not turn missing evidence into a value.

```python
def _incomplete_scope(reason, *, organization_source=None, missing_fields=(),
                      pagination_complete=False):
    evidence = ReceiptScopeEvidence(
        scope_id="biztype316-v1", method="typed_rows",
        type_semantics_verified=False, filter_verified=False,
        pagination_complete=pagination_complete,
        organization_source=organization_source,
        missing_fields=tuple(sorted(set(missing_fields))),
        completeness_reason=reason)
    return ReceiptScopeResult(rows=(), evidence=evidence, complete=False)


def _receipt_record(line):
    day = _to_date(line.receipt_date)
    return ReceiptRecord(
        receipt_doc_no=str(line.receipt_doc_no), line_no=str(line.line_no),
        po_id=str(line.po_id), po_line_no=str(line.po_line_no),
        material_id=str(line.material_id), supplier_name=str(line.supplier_name or ""),
        receipt_date=day, qty_received=float(line.qty_received or 0),
        unit_price=float(line.unit_price or 0))


def _to_date(value):
    """Return only a valid ISO calendar date/datetime; invalid values stay unknown."""
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    try:
        if len(text) == 10:
            return date.fromisoformat(text)
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except (TypeError, ValueError, OverflowError):
        return None


def _normalize_biz_type(value):
    """Honor ReceiptLine's int|string contract without truthiness or lossy coercion."""
    if type(value) is int:
        return value
    if isinstance(value, str) and re.fullmatch(r"[+-]?[0-9]+", value):
        return int(value)
    return None


def derive_receipt_scope_316(batch, capability=None):
    reasons = []
    gaps = set()
    if not batch.page_evidence.pagination_complete:
        reasons.append("GR/Query 分页完整性未证")
    if any(_to_date(row.line.receipt_date) is None for row in batch.rows):
        reasons.append("存在 BusinessDate 未知的候选行")
        gaps.add("BusinessDate")
    for row in batch.rows:
        gaps.update(row.missing_fields & {"qty_received", "unit_price", "supplier_name"})
    typed_ok = (
        batch.requested_biz_type is None
        and batch.filter_applied is not True
        and capability is not None
        and capability.type_semantics_verified
        and capability.source_field_map_id is not None
        and capability.source_field_map_id == batch.source_field_map_id
        and all(_normalize_biz_type(row.line.biz_type) is not None
                and "biz_type" not in row.missing_fields
                for row in batch.rows)
    )
    filter_ok = (
        capability is not None
        and capability.capability_id is not None
        and capability.capability_id == batch.capability_id
        and capability.server_filter_verified
        and batch.requested_biz_type == 316
        and batch.filter_applied is True
    )
    common_ok = batch.page_evidence.pagination_complete and not any(
        _to_date(row.line.receipt_date) is None for row in batch.rows)
    if not common_ok or not (typed_ok or filter_ok):
        if not typed_ok:
            reasons.append("BizType逐行语义或字段映射未证")
        if batch.requested_biz_type == 316 and batch.filter_applied is not True:
            reasons.append("请求参数不证明服务端已应用BizType过滤")
        return _incomplete_scope(
            "；".join(dict.fromkeys(reasons)),
            organization_source=batch.organization_source,
            missing_fields=gaps | ({"BizType"} if not typed_ok and not filter_ok else set()),
            pagination_complete=batch.page_evidence.pagination_complete)
    method = "typed_rows" if typed_ok else "verified_server_filter"
    selected = []
    for row in batch.rows:
        if method == "typed_rows" and _normalize_biz_type(row.line.biz_type) != 316:
            continue
        selected.append(ReceiptScopeRow(
            record=_receipt_record(row.line),
            missing_fields=frozenset(row.missing_fields & {
                "qty_received", "unit_price", "supplier_name"})))
    evidence = ReceiptScopeEvidence(
        scope_id="biztype316-v1", method=method,
        type_semantics_verified=typed_ok, filter_verified=filter_ok,
        pagination_complete=True, organization_source=batch.organization_source,
        missing_fields=(), completeness_reason="")
    return ReceiptScopeResult(rows=tuple(selected), evidence=evidence, complete=True)


def _shared_receipts_from_batch(batch, windows):
    lo, hi = windows.overall_range()
    rows = []
    for batch_row in batch.rows:
        record = _receipt_record(batch_row.line)
        if record.receipt_date is None or not (lo <= record.receipt_date <= hi):
            continue
        rows.append(record)
    return tuple(rows)


def _untyped_mock_scope():
    return _incomplete_scope("MOCK feed未提供可证的BizType逐行字段")


def fetch_scoped(feed, windows, capability=None):
    return feed.fetch_scoped(windows, capability=capability)
```

Add `fetch_scoped()` to `Feed(Protocol)` with signature `fetch_scoped(self, windows, *, capability=None)`. `MockFeed.fetch_scoped()` is exactly `return self.fetch(windows), _untyped_mock_scope()` (accept the protocol's optional keyword but do not use it). `RealFeed.fetch_scoped()` obtains `lines = self._fetch_order_lines(windows)`, then calls only `self._erp.get_receipt_batch(days=ERP_LOOKBACK_DAYS, field_map=None, capability_id=None)` inside the same error wrapper used for ERP receipts; it does not pass `biz_type`. It creates `FrozenDataset(order_lines=lines, receipts=_shared_receipts_from_batch(batch, windows), mode="real", fetched_at=_now_iso(), range_start=windows.month_ago.start, range_end=windows.current.end, source_notes=dict(_REAL_SOURCE_NOTES))`, then returns `(dataset, derive_receipt_scope_316(batch, capability))`. When scope is incomplete, append an explicit source note naming BizType/pagination evidence gap; do not hide it behind a default. `fetch()` remains byte/value compatible and continues calling `_fetch_receipts()` for no-scope mode.

- [ ] **Step 4: Run the focused SC2 source tests again**

Run the Task 2 command above. Expected: tests pass, including all existing no-network/fail-loud tests; the new `ReceiptScopeResult` is complete only for synthetic verified inputs.

---

### Task 3: Four metrics consume the scope without filtering shared metrics

**Files:**

- Modify: `4-数字员工/采购部/SC2-采购周报自动生成/sc2/metrics.py`
- Modify: `4-数字员工/采购部/SC2-采购周报自动生成/tests/test_metrics.py`

**Interfaces:**

- Consumes: `compute_metrics(dataset, windows, *, receipt_scope=None, thresholds=None, thresholds_confirmed=False, caliber_confirmed=False)`.
- Produces: unchanged metric keys/labels/formulas; four target keys use scope rows filtered separately by each window's inclusive `start <= receipt_date <= end`. Every other metric, including `receipt_doc_count`, `receipt_material_count`, and `receipt_match_rate`, uses `dataset.receipts` and its existing `_in` predicate.

- [ ] **Step 1: Add failing mixed-subset and missing-field tests**

Extend imports in `tests/test_metrics.py` with `ReceiptScopeRow`, `ReceiptScopeEvidence`, and `ReceiptScopeResult`; use its `_ds`/`_receipt` helpers and `build_windows(date(2026, 10, 8))` for a stable cross-window fixture. That fixture has two 316 lines on each of the month-ago, previous, and current window boundaries, one same-window non-316 row per window in the shared dataset, and target lines just outside the overall range. Every target metric must be 2 per slot; the shared `receipt_doc_count` must be 3 per slot.

```python
def _scope(rows, *, complete=True, reason=""):
    evidence = ReceiptScopeEvidence(
        scope_id="biztype316-v1", method="typed_rows", type_semantics_verified=True,
        filter_verified=False, pagination_complete=True, organization_source="synthetic",
        missing_fields=(), completeness_reason=reason)
    return ReceiptScopeResult(tuple(rows) if complete else (), evidence, complete)


def test_四个316指标隔离但共享收货指标仍使用全量():
    r316a = _receipt(receipt_doc_no="MOCK-316-A", line_no="1", qty_received=10, unit_price=2)
    r316b = _receipt(receipt_doc_no="MOCK-316-B", line_no="1", qty_received=20, unit_price=3,
                     supplier_name="供应商B")
    r326 = _receipt(receipt_doc_no="MOCK-326", line_no="1", qty_received=4, unit_price=7)
    r449 = _receipt(receipt_doc_no="MOCK-449", line_no="1", qty_received=5, unit_price=11)
    dataset_mixed = _ds(receipts=(r316a, r316b, r326, r449))
    scope_316 = _scope([ReceiptScopeRow(r316a, frozenset()),
                        ReceiptScopeRow(r316b, frozenset())])
    got = {m.key: m for m in compute_metrics(dataset_mixed, WS, receipt_scope=scope_316)}
    assert got["receipt_line_count"].current.value == 2
    assert got["receipt_qty"].current.value == 30
    assert got["receipt_amount"].current.value == 80
    assert got["receipt_supplier_count"].current.value == 2
    assert got["receipt_doc_count"].current.value == 4
    assert got["receipt_material_count"].current.value == 1


def test_缺数量只让数量金额不完整():
    r = _receipt(receipt_doc_no="MOCK-316-QTY-GAP", line_no="1", qty_received=0,
                 unit_price=3)
    dataset_missing_qty = _ds(receipts=(r,))
    scope_316 = _scope([ReceiptScopeRow(r, frozenset({"qty_received"}))])
    got = {m.key: m for m in compute_metrics(dataset_missing_qty, WS,
                                             receipt_scope=scope_316)}
    assert got["receipt_qty"].current.value is None
    assert got["receipt_amount"].current.value is None
    assert got["receipt_line_count"].current.value == 1
    assert got["receipt_supplier_count"].current.value == 1


def test_单价和供应商缺口只影响各自依赖指标():
    r_price = _receipt(receipt_doc_no="MOCK-316-PRICE-GAP", line_no="1",
                       qty_received=10, unit_price=0)
    r_supplier = _receipt(receipt_doc_no="MOCK-316-SUPPLIER-GAP", line_no="1",
                          qty_received=20, unit_price=2, supplier_name="")
    dataset = _ds(receipts=(r_price, r_supplier))
    scope = _scope([ReceiptScopeRow(r_price, frozenset({"unit_price"})),
                    ReceiptScopeRow(r_supplier, frozenset({"supplier_name"}))])
    got = {m.key: m for m in compute_metrics(dataset, WS, receipt_scope=scope)}
    assert got["receipt_line_count"].current.value == 2
    assert got["receipt_qty"].current.value == 30
    assert got["receipt_amount"].current.value is None
    assert got["receipt_supplier_count"].current.value is None


def test_不完整scope四个目标值均不能以全量值或零伪装():
    dataset_mixed = _ds(receipts=(_receipt(receipt_doc_no="MOCK-326"),))
    scope_unknown = _scope([], complete=False, reason="BizType candidate missing")
    got = {m.key: m for m in compute_metrics(dataset_mixed, WS,
                                             receipt_scope=scope_unknown)}
    assert all(got[key].current.value is None for key in
               ("receipt_line_count", "receipt_qty", "receipt_amount",
                "receipt_supplier_count"))


def test_三自然周各自按闭区间过滤scope且共享指标仍用全量():
    from datetime import timedelta
    windows = build_windows(date(2026, 10, 8))
    target = []
    shared = []
    for slot, window in (("ago", windows.month_ago), ("previous", windows.previous),
                         ("current", windows.current)):
        for edge, day in (("start", window.start), ("end", window.end)):
            target.append(_receipt(receipt_doc_no=f"MOCK-316-{slot}-{edge}",
                                   receipt_date=day, qty_received=10, unit_price=2,
                                   supplier_name=f"S-{slot}-{edge}"))
        shared.append(_receipt(receipt_doc_no=f"MOCK-326-{slot}",
                               receipt_date=window.start, qty_received=99,
                               unit_price=9, supplier_name="S-326"))
    outside = [
        _receipt(receipt_doc_no="MOCK-316-before", receipt_date=windows.month_ago.start
                 - timedelta(days=1)),
        _receipt(receipt_doc_no="MOCK-316-after", receipt_date=windows.current.end
                 + timedelta(days=1)),
    ]
    dataset = _ds(receipts=tuple(target + shared + outside))
    scope = _scope([ReceiptScopeRow(row, frozenset()) for row in target + outside])
    got = {m.key: m for m in compute_metrics(dataset, windows, receipt_scope=scope)}
    for slot in ("current", "previous", "month_ago"):
        assert getattr(got["receipt_line_count"], slot).value == 2
        assert getattr(got["receipt_qty"], slot).value == 20
        assert getattr(got["receipt_amount"], slot).value == 40
        assert getattr(got["receipt_supplier_count"], slot).value == 2
        assert getattr(got["receipt_doc_count"], slot).value == 3
```

- [ ] **Step 2: Run focused SC2 metric tests**

```powershell
& 'C:\Dev\Codex\runtimes\zhuopin-ai\venv\Scripts\python.exe' -B -m pytest -p no:cacheprovider 'tests/test_metrics.py' -q
```

- [ ] **Step 3: Add an optional scoped context without changing the legacy branch**

Keep `_Ctx.receipts` as the shared rows. For each slot, build a scoped tuple with the existing inclusive `_in(window, record.receipt_date)` predicate over `receipt_scope.rows`; never reuse one current-window tuple for all slots. Preserve all `_SPECS` except the four exact keys: for those, calculate from that slot's scoped rows when scope is complete; when incomplete, produce `MetricValue(value=None, caveat=receipt_scope.evidence.completeness_reason)`. When `receipt_scope is None`, retain current legacy behavior exactly. For complete scope with missing quantity, amount/quantity are incomplete while line count and distinct non-empty supplier count remain available; missing price affects amount only; missing supplier name affects supplier count only. Missing date is rejected earlier as a membership gap.

Use this pure helper to keep the four target metrics separate from `_Ctx.receipts`; invoke it only for those four keys. Existing non-target `_SPECS` must continue using the original context unchanged:

```python
_RECEIPT_SCOPE_KEYS = {
    "receipt_line_count", "receipt_qty", "receipt_amount", "receipt_supplier_count",
}

def _receipt_scope_value(key, scope, window):
    if not scope.complete:
        return None, scope.evidence.completeness_reason
    rows = tuple(row for row in scope.rows
                 if _in(window, row.record.receipt_date))
    missing = set().union(*(row.missing_fields for row in rows)) if rows else set()
    if key == "receipt_line_count":
        return float(len(rows)), ""
    if key == "receipt_qty":
        if "qty_received" in missing:
            return None, "316收货数量字段不完整"
        return float(sum(row.record.qty_received for row in rows)), ""
    if key == "receipt_amount":
        if missing & {"qty_received", "unit_price"}:
            return None, "316收货数量或单价字段不完整"
        return float(sum(row.record.qty_received * row.record.unit_price for row in rows)), ""
    if key == "receipt_supplier_count":
        if "supplier_name" in missing:
            return None, "316供应商名称字段不完整"
        return float(len({row.record.supplier_name for row in rows
                          if row.record.supplier_name})), ""
    raise KeyError(f"不是316 scope指标：{key}")


def _value_for_key(key, name, group, fn, unit, caveat, context, window,
                   receipt_scope, *, caliber_confirmed):
    if receipt_scope is None or key not in _RECEIPT_SCOPE_KEYS:
        value = fn(context)
        note = "" if caliber_confirmed else caveat
        return MetricValue(value=value, unit=unit, caveat=note)
    value, scope_note = _receipt_scope_value(key, receipt_scope, window)
    notes = [note for note in (("" if caliber_confirmed else caveat), scope_note) if note]
    return MetricValue(value=value, unit=unit, caveat="；".join(notes))
```

In `compute_metrics`, retain the existing `buckets` from `_ctx()`; pair each slot with `windows.current`, `windows.previous`, or `windows.month_ago` and call `_value_for_key` for each spec. Build `Metric` and call `_flag_anomaly` exactly as today. This means `receipt_doc_count`, `receipt_material_count`, and `receipt_match_rate` stay full-dataset; incomplete scope makes only the four target metric values `None` with an explicit reason. Do not replace `_Ctx.receipts` globally or add new threshold/caliber confirmations.

- [ ] **Step 4: Run `tests/test_metrics.py` again**

Expected: new tests pass, original tests still pass, and all non-target shared metrics retain their old values under mixed fixtures.

---

### Task 4: Same-subset detail, completeness and reconciliation

**Files:**

- Modify: `4-数字员工/采购部/SC2-采购周报自动生成/sc2/detail.py`
- Modify: `4-数字员工/采购部/SC2-采购周报自动生成/tests/test_detail.py`

**Interfaces:**

- Consumes: `receipt_table(dataset, window, slot="current", *, receipt_scope=None)` and `reconcile(dataset, windows, report, *, receipt_scope=None)`.
- Produces: the 316 receipt detail uses exactly the metric subset and inclusive per-window date predicate as metrics; incomplete membership refuses reconciliation and CSV; the legacy three-section detail is unchanged without scope.

- [ ] **Step 1: Add failing receipt detail tests**

Extend imports in `tests/test_detail.py` with `ReceiptScopeRow`, `ReceiptScopeEvidence`, `ReceiptScopeResult`, and `ScopeIncomplete`; `BASE`, `_receipt`, `MockFeed`, `FrozenDataset`, and `build_windows` are existing test helpers/imports.

```python
def _scope(rows, *, complete=True):
    evidence = ReceiptScopeEvidence(
        scope_id="biztype316-v1", method="typed_rows", type_semantics_verified=True,
        filter_verified=False, pagination_complete=True, organization_source="synthetic",
        missing_fields=(), completeness_reason="" if complete else "BizType membership incomplete")
    return ReceiptScopeResult(tuple(rows) if complete else (), evidence, complete)


def test_316明细仅含窗口内316且行数与四指标对齐():
    windows = build_windows(BASE)
    cur = windows.current
    r1 = _receipt("MOCK-316-A", "1", cur.start, "PO-A", "1", qty=10)
    r2 = _receipt("MOCK-316-B", "1", cur.end, "PO-B", "1", qty=20)
    shared_326 = _receipt("MOCK-326", "1", cur.start, "PO-C", "1", qty=30)
    dataset_mixed = FrozenDataset(order_lines=(), receipts=(r1, r2, shared_326),
                                  mode="mock", fetched_at="2026-08-19T10:00:00+08:00",
                                  range_start=windows.month_ago.start, range_end=cur.end)
    scope_316 = _scope([ReceiptScopeRow(r1, frozenset()),
                        ReceiptScopeRow(r2, frozenset())])
    table = receipt_table(dataset_mixed, cur, receipt_scope=scope_316)
    assert {row[0] for row in table.rows} == {"MOCK-316-A", "MOCK-316-B"}
    assert table.counted == 2


def test_成员资格或窗口不完整时不导出完整316明细():
    windows = build_windows(BASE)
    dataset = MockFeed().fetch(windows)
    scope_unknown = _scope([], complete=False)
    with pytest.raises(ScopeIncomplete):
        receipt_table(dataset, windows.current, receipt_scope=scope_unknown)


def test_字段缺口明示而不伪装零且行成员仍保留():
    windows = build_windows(BASE)
    r = _receipt("MOCK-316-QTY-GAP", "1", windows.current.start, "PO-A", "1", qty=0)
    dataset = FrozenDataset(order_lines=(), receipts=(r,), mode="mock",
                            fetched_at="2026-08-19T10:00:00+08:00",
                            range_start=windows.month_ago.start, range_end=windows.current.end)
    scope = _scope([ReceiptScopeRow(r, frozenset({"qty_received"}))])
    table = receipt_table(dataset, windows.current, receipt_scope=scope)
    assert table.counted == 1
    assert table.rows[0][7] == "未取到"
    assert table.rows[0][9] == "未取到"


def test_三窗口明细逐格使用同一scope并与报告对账():
    windows = build_windows(BASE)
    target = []
    shared = []
    for slot, window in (("ago", windows.month_ago), ("previous", windows.previous),
                         ("current", windows.current)):
        target.extend([
            _receipt(f"MOCK-316-{slot}-start", "1", window.start, "PO-A", "1"),
            _receipt(f"MOCK-316-{slot}-end", "2", window.end, "PO-B", "1"),
        ])
        shared.append(_receipt(f"MOCK-326-{slot}", "3", window.start, "PO-C", "1"))
    dataset = FrozenDataset(order_lines=(), receipts=tuple(target + shared), mode="mock",
                            fetched_at="2026-08-19T10:00:00+08:00",
                            range_start=windows.month_ago.start,
                            range_end=windows.current.end)
    scope = _scope([ReceiptScopeRow(row, frozenset()) for row in target])
    report = build_report(dataset, windows, receipt_scope=scope)
    counts = reconcile(dataset, windows, report, receipt_scope=scope)
    assert counts["receipt"] == {"current": 2, "previous": 2, "month_ago": 2}
    for slot, window in (("current", windows.current), ("previous", windows.previous),
                         ("month_ago", windows.month_ago)):
        table = receipt_table(dataset, window, slot, receipt_scope=scope)
        assert table.counted == 2
        assert all(row[0].startswith("MOCK-316-") for row in table.rows)
```

- [ ] **Step 2: Run the focused SC2 detail tests**

```powershell
& 'C:\Dev\Codex\runtimes\zhuopin-ai\venv\Scripts\python.exe' -B -m pytest -p no:cacheprovider 'tests/test_detail.py' -q
```

- [ ] **Step 3: Route the scoped receipt table and reconciliation through one object**

Add `ScopeIncomplete` as an explicit detail failure. Exact signatures: `receipts_in(dataset, window, receipt_scope=None)`, `receipt_table(dataset, window, slot="current", *, receipt_scope=None)`, `build_table(dataset, windows, section, slot, *, receipt_scope=None)`, and `reconcile(dataset, windows, report, *, receipt_scope=None)`. Only receipt detail consumes scope; each window applies the existing inclusive `_in_window` date predicate. The functions do not derive separate subsets. CSV is returned only after membership is complete and reconciliation confirms row counts against the same scoped `WeeklyReport`; incomplete membership raises before a table or file response is returned. For scoped rows, show `未取到` instead of legacy default 0/empty wherever row `missing_fields` identifies qty, unit price, or supplier; line membership/count remains visible when only a dependent field is missing. Keep the no-scope formatter unchanged. Preserve old `DATASET_SCHEMA=1`, `dataset_to_dict`, `dataset_from_dict`, `save_dataset`, and `load_dataset` behavior for legacy files.

Add separate `SCOPED_DATASET_SCHEMA = 1` serialization for `biztype316-v1` snapshots. The scoped JSON records the shared `FrozenDataset` once, the typed 316 rows/scope evidence, scope id, and schema version. A legacy `schema=1` file always decodes as ordinary shared data and never acquires scope evidence by default.

Implement receipt-scope filtering and serialization with these explicit functions in `detail.py`:

```python
class ScopeIncomplete(RuntimeError):
    pass


class ScopeSnapshotMismatch(ValueError):
    pass


def scoped_receipt_rows_in(scope, window):
    if not scope.complete:
        raise ScopeIncomplete(scope.evidence.completeness_reason)
    return tuple(row for row in scope.rows
                 if _in_window(window, row.record.receipt_date))


def receipts_in(dataset, window, receipt_scope=None):
    if receipt_scope is None:
        return [row for row in dataset.receipts
                if _in_window(window, row.receipt_date)]
    return [row.record for row in scoped_receipt_rows_in(receipt_scope, window)]


def receipt_table(dataset, window, slot="current", *, receipt_scope=None):
    order_index = {(line.po_id, line.line_no) for line in dataset.order_lines}
    if receipt_scope is None:
        items = tuple(ReceiptScopeRow(record=record, missing_fields=frozenset())
                      for record in receipts_in(dataset, window))
    else:
        items = scoped_receipt_rows_in(receipt_scope, window)
    items = tuple(sorted(items, key=lambda item: (
        item.record.receipt_date or date.min, item.record.receipt_doc_no,
        _line_sort_key(item.record.line_no))))
    rows = []
    for item in items:
        record = item.record
        missing = item.missing_fields
        qty = "未取到" if "qty_received" in missing else _fmt_num(record.qty_received)
        price = "未取到" if "unit_price" in missing else _fmt_num(record.unit_price)
        amount = ("未取到" if missing & {"qty_received", "unit_price"}
                  else _fmt_num(record.qty_received * record.unit_price))
        supplier = "未取到" if "supplier_name" in missing else record.supplier_name
        rows.append((record.receipt_doc_no, record.line_no,
                     _fmt_date(record.receipt_date), record.po_id, record.po_line_no,
                     record.material_id, supplier, qty, price, amount,
                     "是" if (record.po_id, record.po_line_no) in order_index else "否"))
    rows = tuple(rows)
    return DetailTable("receipt", slot, _RECEIPT_COLUMNS, rows, counted=len(rows))


def build_table(dataset, windows, section, slot, *, receipt_scope=None):
    if section not in SECTIONS:
        raise ValueError(f"未知明细节：{section!r}（只接受 {'/'.join(SECTIONS)}）")
    if slot not in WINDOWS:
        raise ValueError(f"未知窗口：{slot!r}（只接受 {'/'.join(WINDOWS)}）")
    window = getattr(windows, slot)
    if section == "receipt":
        return receipt_table(dataset, window, slot, receipt_scope=receipt_scope)
    return _BUILDERS[section](dataset, window, slot)


def reconcile(dataset, windows, report, *, receipt_scope=None):
    metrics = {metric.key: metric for metric in report.metrics}
    counts = {}
    problems = []
    for section, (name, metric_key) in SECTIONS.items():
        counts[section] = {}
        metric = metrics.get(metric_key)
        for slot in WINDOWS:
            table = build_table(dataset, windows, section, slot,
                                receipt_scope=receipt_scope)
            counts[section][slot] = table.counted
            reported = None if metric is None else getattr(metric, slot).value
            if reported is None or int(round(reported)) != table.counted:
                problems.append(f"{name}节·{WINDOWS[slot]}：明细计入 {table.counted} 行，"
                                 f"周报「{metric_key}」＝{reported}")
    if problems:
        raise DetailMismatch("明细与周报指标不一致，拒绝导出：" + "；".join(problems))
    return counts


SCOPED_DATASET_SCHEMA = 1


def save_scoped_dataset(dataset, scope, period, *, run_id):
    payload = {
        "schema": SCOPED_DATASET_SCHEMA, "scope_id": "biztype316-v1",
        "period": period, "run_id": run_id,
        "dataset": dataset_to_dict(dataset),
        "scope": {
            "complete": scope.complete,
            "evidence": {
                "scope_id": scope.evidence.scope_id, "method": scope.evidence.method,
                "type_semantics_verified": scope.evidence.type_semantics_verified,
                "filter_verified": scope.evidence.filter_verified,
                "pagination_complete": scope.evidence.pagination_complete,
                "organization_source": scope.evidence.organization_source,
                "missing_fields": list(scope.evidence.missing_fields),
                "completeness_reason": scope.evidence.completeness_reason,
            },
            "rows": [{"record": _receipt_to_dict(row.record),
                      "missing_fields": sorted(row.missing_fields)} for row in scope.rows],
        },
    }
    path = dataset_path(period, "biztype316-v1")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_scoped_dataset(period, scope_id="biztype316-v1"):
    if scope_id != "biztype316-v1":
        raise ValueError(f"未知收货范围：{scope_id}")
    payload = json.loads(dataset_path(period, scope_id).read_text(encoding="utf-8"))
    if (payload.get("schema") != SCOPED_DATASET_SCHEMA
            or payload.get("scope_id") != scope_id or payload.get("period") != period
            or not payload.get("run_id")):
        raise ScopeSnapshotMismatch("316数据集schema、范围、期次或run_id不匹配")
    source = payload["scope"]
    raw = source["evidence"]
    evidence = ReceiptScopeEvidence(
        scope_id=raw["scope_id"], method=raw["method"],
        type_semantics_verified=raw["type_semantics_verified"],
        filter_verified=raw["filter_verified"],
        pagination_complete=raw["pagination_complete"],
        organization_source=raw["organization_source"],
        missing_fields=tuple(raw["missing_fields"]),
        completeness_reason=raw["completeness_reason"])
    scope = ReceiptScopeResult(
        rows=tuple(ReceiptScopeRow(
            record=_receipt_from_dict(row["record"]),
            missing_fields=frozenset(row["missing_fields"])) for row in source["rows"]),
        evidence=evidence, complete=source["complete"])
    dataset = dataset_from_dict(payload["dataset"])
    return dataset, scope, payload["run_id"]
```

The serialization stores ordinary receipt rows once under `dataset`, then only the selected 316 subset under `scope.rows`; it is not a second full data set. Keep old `dataset_to_dict`/`dataset_from_dict` and old `DATASET_SCHEMA=1` paths untouched.

- [ ] **Step 4: Run `tests/test_detail.py` again**

Expected: new tests pass; old CSV/reconciliation/schema rejection tests pass with no legacy file rewrite.

---

### Task 5: Versioned snapshot/cache paths and explicit UI scope selection

**Files:**

- Modify: `4-数字员工/采购部/SC2-采购周报自动生成/sc2/config.py`
- Modify: `4-数字员工/采购部/SC2-采购周报自动生成/sc2/report.py`
- Modify: `4-数字员工/采购部/SC2-采购周报自动生成/sc2/webapp.py`
- Modify: `4-数字员工/采购部/SC2-采购周报自动生成/tests/test_report.py`
- Modify: `4-数字员工/采购部/SC2-采购周报自动生成/tests/test_detail.py`

**Interfaces:**

- Consumes: `Feed.fetch_scoped(windows)`, `build_report(dataset, windows, *, thresholds=None, thresholds_confirmed=True, thresholds_confirmed_by=THRESHOLDS_CONFIRMED_BY, caliber_confirmed=False, receipt_scope=None)`, `config.snapshot_path(period, scope_id=None)`, `detail.dataset_path(period, scope_id=None)`, `detail.save_scoped_dataset(dataset, scope, period, *, run_id)`, `detail.load_scoped_dataset(period, scope_id="biztype316-v1") -> (dataset, scope, run_id)`, `save_snapshot(report, scope_id=None, *, run_id=None)`, and exact query `scope=biztype316-v1`.
- Produces: one explicit POST build path that writes a paired versioned dataset/report with a matching run ID; GET scope routes read only that pair and never regenerate or fall back. Paths are `sc2_weekly_{period}__biztype316-v1.json`, `sc2_dataset_{period}__biztype316-v1.json`, and hashed `gr_lines_{days}d__biztype316-v1__{identity[:16]}.json`; default/no-scope paths and payloads remain `sc2_weekly_{period}.json`, `sc2_dataset_{period}.json`, `gr_{days}` and `gr_lines_{days}d.json`.

- [ ] **Step 1: Add failing snapshot, HTML, API, and CSV tests with temporary directories**

Put the existing path/schema tests and the helper/route tests below in `tests/test_detail.py` (it already imports `date`, `detail`, `create_app`, `MockFeed`, `build_report`, and `save_snapshot`; add `re`, `load_snapshot`, `ReceiptScopeRow`, `ReceiptScopeEvidence`, and `ReceiptScopeResult`). Keep the test fixtures under `SC2_REPORTS_DIR=tmp_path`; do not instantiate a real connector. Add `config`, `detail`, and scope report save/load imports to `tests/test_report.py` for path and report-run-ID tests.

```python
def test_scope路径有版本且普通路径完全保持旧名(tmp_path, monkeypatch):
    monkeypatch.setenv("SC2_REPORTS_DIR", str(tmp_path))
    assert config.snapshot_path("2026-W36").name == "sc2_weekly_2026-W36.json"
    assert config.snapshot_path("2026-W36", "biztype316-v1").name == \
        "sc2_weekly_2026-W36__biztype316-v1.json"
    assert detail.dataset_path("2026-W36").name == "sc2_dataset_2026-W36.json"
    assert detail.dataset_path("2026-W36", "biztype316-v1").name == \
        "sc2_dataset_2026-W36__biztype316-v1.json"


def test_旧schema不能满足316scope且旧文件字节不变(tmp_path, monkeypatch):
    monkeypatch.setenv("SC2_REPORTS_DIR", str(tmp_path))
    old = tmp_path / "sc2_dataset_2026-W36.json"
    old.write_bytes(b'{"schema":1,"period":"2026-W36"}')
    before = old.read_bytes()
    with pytest.raises(FileNotFoundError):
        detail.load_scoped_dataset("2026-W36", scope_id="biztype316-v1")
    assert old.read_bytes() == before
    scoped = detail.dataset_path("2026-W36", "biztype316-v1")
    scoped.write_bytes(b'{"schema":1,"period":"2026-W36"}')
    with pytest.raises(ValueError):
        detail.load_scoped_dataset("2026-W36", scope_id="biztype316-v1")
    assert old.read_bytes() == before


def _store_complete_scoped_mock_pair(monkeypatch):
    from sc2 import detail
    from sc2.models import ReceiptScopeEvidence, ReceiptScopeResult, ReceiptScopeRow
    from sc2.report import build_report, save_snapshot
    from sc2.sources import MockFeed
    from sc2.windows import build_windows
    base = date(2026, 8, 19)
    windows = build_windows(base)
    dataset = MockFeed().fetch(windows)
    # This is a test-only typed synthetic fixture; no live type mapping is configured.
    rows = tuple(ReceiptScopeRow(row, frozenset()) for row in dataset.receipts)
    scope = ReceiptScopeResult(rows, ReceiptScopeEvidence(
        scope_id="biztype316-v1", method="typed_rows", type_semantics_verified=True,
        filter_verified=False, pagination_complete=True, organization_source="synthetic",
        missing_fields=(), completeness_reason=""), True)
    run_id = "synthetic-scoped-run-001"
    report = build_report(dataset, windows, receipt_scope=scope)
    detail.save_scoped_dataset(dataset, scope, report.period, run_id=run_id)
    save_snapshot(report, scope_id="biztype316-v1", run_id=run_id)
    return report.period


def test_旧报表存在但没有scopedpair时不fallback(tmp_path, monkeypatch):
    from sc2.report import build_report, save_snapshot
    from sc2.sources import MockFeed
    from sc2.windows import build_windows
    monkeypatch.setenv("SC2_REPORTS_DIR", str(tmp_path))
    windows = build_windows(date(2026, 8, 19))
    save_snapshot(build_report(MockFeed().fetch(windows), windows))
    client = create_app(base_date=date(2026, 8, 19), mode="mock").test_client()
    response = client.get("/?scope=biztype316-v1")
    assert response.status_code == 404
    assert "316" in response.get_data(as_text=True)


def test_未知scope在HTML和API均明确拒绝(tmp_path, monkeypatch):
    monkeypatch.setenv("SC2_REPORTS_DIR", str(tmp_path))
    client = create_app(base_date=date(2026, 8, 19), mode="mock").test_client()
    assert client.get("/?scope=biztype316-v2").status_code == 400
    assert client.get("/procurement/sc2/api/report?scope=biztype316-v2").status_code == 400
    assert client.get("/procurement/sc2/api/detail?scope=biztype316-v2").status_code == 400


def test_scopedHTML页面显示范围并且每条明细和CSV链接带scope(tmp_path, monkeypatch):
    monkeypatch.setenv("SC2_REPORTS_DIR", str(tmp_path))
    _store_complete_scoped_mock_pair(monkeypatch)
    client = create_app(base_date=date(2026, 8, 19), mode="mock").test_client()
    html_text = client.get("/?scope=biztype316-v1").get_data(as_text=True)
    assert "BizType 316" in html_text
    links = re.findall(r'href="([^"]+)"', html_text)
    scoped_detail_links = [url for url in links if "/api/detail" in url]
    assert scoped_detail_links
    assert all("scope=biztype316-v1" in url for url in scoped_detail_links)


def test_scopedReportDetailAPI与CSV使用同一版本快照(tmp_path, monkeypatch):
    monkeypatch.setenv("SC2_REPORTS_DIR", str(tmp_path))
    period = _store_complete_scoped_mock_pair(monkeypatch)
    client = create_app(base_date=date(2026, 8, 19), mode="mock").test_client()
    legacy = client.get("/procurement/sc2/api/report").get_json()
    assert "receipt_scope" not in legacy
    report = client.get("/procurement/sc2/api/report?scope=biztype316-v1").get_json()
    assert report["receipt_scope"]["id"] == "biztype316-v1"
    assert report["receipt_scope"]["complete"] is True
    index = client.get("/procurement/sc2/api/detail?scope=biztype316-v1").get_json()
    assert index["ok"] is True
    urls = [slot["csv"] for section in index["sections"].values()
            for slot in section["windows"].values()]
    assert urls and all("scope=biztype316-v1" in url for url in urls)
    csv_response = client.get(
        "/procurement/sc2/api/detail/receipt.csv?window=current&scope=biztype316-v1")
    assert csv_response.status_code == 200
    assert csv_response.mimetype == "text/csv"
    dataset, _, _ = detail.load_scoped_dataset(period)
    windows = build_windows(date(2026, 8, 19))
    for section in ("order", "open"):
        scoped_csv = client.get(
            f"/procurement/sc2/api/detail/{section}.csv?window=current&scope=biztype316-v1")
        assert scoped_csv.status_code == 200
        expected = detail.render_csv(detail.build_table(dataset, windows, section, "current"))
        assert scoped_csv.data == expected.encode("utf-8")


def test_scopedpair的period_scope和runid必须成对(tmp_path, monkeypatch):
    monkeypatch.setenv("SC2_REPORTS_DIR", str(tmp_path))
    period = _store_complete_scoped_mock_pair(monkeypatch)
    raw_report = load_snapshot(period, scope_id="biztype316-v1")
    dataset, scope, dataset_run_id = detail.load_scoped_dataset(period)
    assert raw_report["scope_id"] == "biztype316-v1"
    assert raw_report["run_id"] == dataset_run_id == "synthetic-scoped-run-001"
    assert scope.complete is True
    assert config.snapshot_path(period).exists() is False
    assert detail.dataset_path(period).exists() is False


def test_incomplete_scopedReport保留缺口且明细拒绝完整导出(tmp_path, monkeypatch):
    monkeypatch.setenv("SC2_REPORTS_DIR", str(tmp_path))
    client = create_app(base_date=date(2026, 8, 19), mode="mock").test_client()
    refresh = client.post("/procurement/sc2/api/refresh?scope=biztype316-v1")
    assert refresh.status_code == 200 and refresh.get_json()["complete"] is False
    report = client.get("/procurement/sc2/api/report?scope=biztype316-v1").get_json()
    assert report["receipt_scope"]["complete"] is False
    assert "BizType" in " ".join(report["receipt_scope"]["reasons"])
    html_text = client.get("/?scope=biztype316-v1").get_data(as_text=True)
    assert "BizType 316" in html_text and "资料不足" in html_text
    html_links = re.findall(r'href="([^"]+)"', html_text)
    scoped_links = [url for url in html_links if "/api/detail" in url]
    assert scoped_links and all("scope=biztype316-v1" in url for url in scoped_links)
    detail_response = client.get("/procurement/sc2/api/detail?scope=biztype316-v1")
    assert detail_response.status_code == 409
    csv_response = client.get(
        "/procurement/sc2/api/detail/receipt.csv?window=current&scope=biztype316-v1")
    assert csv_response.status_code == 409
```

- [ ] **Step 2: Run focused report and detail endpoint tests**

```powershell
& 'C:\Dev\Codex\runtimes\zhuopin-ai\venv\Scripts\python.exe' -B -m pytest -p no:cacheprovider 'tests/test_report.py' 'tests/test_detail.py' -q
```

- [ ] **Step 3: Add scope identity without changing default paths**

In `webapp.py`, add `import uuid`. Add one closed-set validator: `None` means legacy; the only accepted new ID is exactly `biztype316-v1`; every other ID raises `ValueError` and HTTP routes translate it to 400. `config.snapshot_path(period, scope_id=None)` and `detail.dataset_path(period, scope_id=None)` append `__biztype316-v1` only for that ID. Do not change legacy path names, schema, or serializers.

In `config.py` and `detail.py`, implement this same closed suffix helper and use it to build paths; the no-scope branch returns the exact current filename. In `report.py`, append `receipt_scope=None` to `build_report` and pass it to `compute_metrics`. Keep `report_to_dict()` output unchanged for ordinary reports. Scoped snapshots add only two top-level metadata keys; run IDs are mandatory only for scoped writes:

```python
def _scope_suffix(scope_id):
    if scope_id is None:
        return ""
    if scope_id == "biztype316-v1":
        return "__biztype316-v1"
    raise ValueError(f"未知收货范围：{scope_id}")
```

```python
def save_snapshot(report, scope_id=None, *, run_id=None):
    data = report_to_dict(report)
    if scope_id is None:
        path = config.snapshot_path(report.period)
    else:
        if scope_id != "biztype316-v1" or not run_id:
            raise ValueError("版本化周报必须有已知scope和run_id")
        path = config.snapshot_path(report.period, scope_id)
        data["scope_id"] = scope_id
        data["run_id"] = run_id
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_snapshot(period, scope_id=None):
    path = config.snapshot_path(period, scope_id)
    if not path.exists():
        raise FileNotFoundError(f"未找到 {period} 期快照：{path}")
    return json.loads(path.read_text(encoding="utf-8"))
```

No-scope `save_snapshot` preserves the current `report_to_dict` key set and legacy path. The scoped code does not create a second report format; `snapshot_to_report()` continues reading the metric body and ignores the two pair metadata keys.

Add `detail.save_scoped_dataset(dataset, scope, period, *, run_id)` and `detail.load_scoped_dataset(period, scope_id="biztype316-v1") -> tuple[FrozenDataset, ReceiptScopeResult, str]`. The scoped JSON has `schema=SCOPED_DATASET_SCHEMA`, exact `scope_id`, `run_id`, one serialized shared dataset, scope evidence, and only the selected scoped rows. `load_scoped_dataset` rejects old schema, wrong scope, malformed payload, and missing run ID. Extend `save_snapshot(report, scope_id=None, *, run_id=None)` and `load_snapshot(period, scope_id=None)`; scoped report JSON stores the same `scope_id` and `run_id`, while legacy JSON remains byte-shape compatible. In a scope request, load both versioned files and reject if either is missing or `(scope_id, run_id, period)` differs. The pair can never be satisfied by legacy files. Sequential write failure leaves a mismatch/missing pair that reads fail closed; do not attempt a partial legacy fallback.

Keep ordinary `_regenerate()` and `_current_report(scope_id=None)` unchanged for `scope_id is None`. The current `sources.build_feed` signature is `build_feed(mode: str, max_status_materials: int | None = None)`; its second argument is positional-or-keyword (not keyword-only). Add `_regenerate_scoped()` called only by explicit `POST /api/refresh?scope=biztype316-v1`: build windows once; call `build_feed(mode, max_status_materials).fetch_scoped(windows)` once; call `build_report(dataset, windows, receipt_scope=scope)`; generate `run_id = uuid.uuid4().hex`; save the scoped dataset and scoped report using the same run ID; return the report/scope. It does not register or confirm publication and does not send. In `mode="mock"`, `fetch_scoped` returns an explicit incomplete scope because the existing fixture has no type evidence. In `mode="real"`, implementation uses only an unfiltered batch; current no-map/no-capability configuration therefore remains incomplete. No test or plan step runs this real path.

Make every read path select by the explicit query parameter:

```python
def _requested_scope():
    value = request.args.get("scope")
    if value is None:
        return None
    if value != "biztype316-v1":
        raise ValueError(f"未知收货范围：{value}")
    return value

def _current_report(scope_id=None):
    base = base_date if base_date is not None else date.today()
    period = build_windows(base).current.label()
    if scope_id is None:
        try:
            return snapshot_to_report(load_snapshot(period))
        except FileNotFoundError:
            return _regenerate()
    raw = load_snapshot(period, scope_id=scope_id)  # no scoped GET regeneration
    dataset, scope, dataset_run_id = detail.load_scoped_dataset(period, scope_id)
    if (raw.get("period") != period or raw.get("run_id") != dataset_run_id
            or raw.get("scope_id") != scope_id):
        raise detail.ScopeSnapshotMismatch("周报与316数据集版本不一致")
    return snapshot_to_report(raw)
```

`POST /api/refresh` calls `_regenerate()` only when the query has no `scope`; with the exact scope it calls `_regenerate_scoped()`. `GET /?scope=biztype316-v1`, `GET /api/report?scope=...`, detail index, and CSV routes only read the matching paired snapshot. If the scoped pair is absent, GET returns 404 with a scoped-refresh instruction and never invokes legacy `_regenerate()`. With no scope, page/API/detail behavior and URLs are exactly the old behavior.

Update the real HTML `index()` path, not only JSON endpoints. It parses `_requested_scope()`, calls `_current_report(scope_id)`, and for scoped mode also loads validated scope metadata. `_render_page(..., scope_id=None, receipt_scope=None)` shows a visible `BizType 316` badge plus complete/incomplete reason and a link back to the ordinary page; ordinary mode has an explicit link to `/?scope=biztype316-v1` when the scoped pair exists. `_detail_links_html(report, scope_id=None, receipt_scope=None)` creates an index link and every section/window CSV URL; for scoped mode each URL contains `scope=biztype316-v1`. Do not change auth, review/publish workflows, route prefix, dashboard layout, or #538 state.

`api_report` returns old keys unchanged with no scope; for explicit scope it adds `receipt_scope={id, complete, reasons}` from the validated paired dataset. `_detail_context(scope_id=None)` loads only the selected pair, returns `(report, dataset, windows, counts, scope)`, and reconciles using that same scope. `api_detail_index` returns the existing sections plus scope metadata and scoped CSV links only when complete; for incomplete scope return HTTP 409 with reason and no rows/complete CSV links. `api_detail_csv(section)` reads scope from its query and calls `detail.build_table(dataset, windows, section, slot, receipt_scope=(scope if section == "receipt" else None))`. The real `build_table(dataset, windows, section, slot, *, receipt_scope=None)` applies scope only in the `section == "receipt"` branch; `order` and `open` keep their existing builders/rows even when the CSV URL carries a scope query. `ScopeIncomplete` returns 409 for the receipt branch, and the route never builds from the ordinary snapshot as fallback. Unknown scope returns 400 in HTML/API/detail routes.

The scoped refresh and pair-check code is fixed to this orchestration; keep ordinary route calls separate:

```python
def _regenerate_scoped():
    base = base_date if base_date is not None else date.today()
    windows = build_windows(base)
    feed = build_feed(mode, max_status_materials)
    dataset, scope = feed.fetch_scoped(windows)
    report = build_report(dataset, windows, receipt_scope=scope)
    run_id = uuid.uuid4().hex
    detail.save_scoped_dataset(dataset, scope, report.period, run_id=run_id)
    save_snapshot(report, scope_id="biztype316-v1", run_id=run_id)
    return report, scope


@bp.post("/api/refresh")
def api_refresh():
    try:
        scope_id = _requested_scope()
    except ValueError as error:
        return jsonify(ok=False, error=str(error)), 400
    if scope_id is None:
        report = _regenerate()
        return jsonify(ok=True, period=report.period,
                       anomalies=[metric.key for metric in report.anomalies])
    report, scope = _regenerate_scoped()
    return jsonify(ok=True, period=report.period, scope=scope.evidence.scope_id,
                   complete=scope.complete,
                   reasons=[] if scope.complete else [scope.evidence.completeness_reason])
```

In `index()`, parse `scope`; when absent call existing `_current_report()` and render existing page plus a scoped-view link only if both versioned files exist and their scope/run ID/period tuple validates. When scope is present, call `_current_report(scope)` and `detail.load_scoped_dataset`; if either file is missing or scope/run ID/period mismatches, return a dedicated 404 scoped-not-generated page with a POST refresh instruction. Never invoke `_regenerate()` for a scoped GET. Pass scope to `_render_page` and `_detail_links_html`. In API/detail routes catch unknown scope as 400, absent pair as 404, `ScopeIncomplete` as 409 and `DetailMismatch` as existing 500. The CSV route checks the same pair and `reconcile()` result before returning bytes.

- [ ] **Step 4: Run focused report and detail tests again**

Expected: old route tests still use legacy paths; new explicit-scope tests use only versioned files; same-period legacy bytes remain unchanged.

---

### Task 6: Full scoped acceptance, code review, and formal handoff

**Files:** No additional product paths; review only the exact files listed above.

**Interfaces:** All tests consume the previously defined immutable scope/evidence contracts. No public behavior is enabled for real `bizType=316` requests unless its external capability evidence is separately approved and present.

- [ ] **Step 1: Run the complete SC2 focused suite**

从原生工具实际返回的 CandidateRoot 开始，命令参数显式接收此路径并进入场景cwd：

```powershell
param([Parameter(Mandatory = $true)][string]$CandidateRoot)
$candidateRoot = (Resolve-Path -LiteralPath $CandidateRoot -ErrorAction Stop).Path
$sc2Head = (& git -C $candidateRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $sc2Head -ne '28337c0ebb52afdbf61e955ecdbc22d151bcd185') { throw 'SC2 candidate HEAD differs from approved starting point' }
$runId = [guid]::NewGuid().ToString('N')
$sc2EvidenceRelative = Join-Path 'reports\sc2-biztype316-1010\runs' $runId
$sc2Evidence = Join-Path 'C:/Dev/zhuopin-ai' $sc2EvidenceRelative
Push-Location $candidateRoot
try {
  git check-ignore --quiet -- (Join-Path $sc2EvidenceRelative 'stdout.txt')
  if ($LASTEXITCODE -ne 0) { throw "Evidence path is not ignored: $sc2Evidence" }
  New-Item -ItemType Directory -Path $sc2Evidence -ErrorAction Stop | Out-Null
  Push-Location (Join-Path $candidateRoot '4-数字员工/采购部/SC2-采购周报自动生成')
  try {
  & 'C:\Dev\Codex\runtimes\zhuopin-ai\venv\Scripts\python.exe' -B -m pytest -p no:cacheprovider 'tests/test_sources.py' 'tests/test_metrics.py' 'tests/test_detail.py' 'tests/test_report.py' -q --basetemp (Join-Path $sc2Evidence 'pytest-temp') --junitxml (Join-Path $sc2Evidence 'junit.xml') 1> (Join-Path $sc2Evidence 'stdout.txt') 2> (Join-Path $sc2Evidence 'stderr.txt')
  $code = $LASTEXITCODE
  [IO.File]::WriteAllText((Join-Path $sc2Evidence 'exit-code.txt'), "$code`n", [Text.UTF8Encoding]::new($false))
  if ($code -ne 0) { throw "pytest failed with exit code $code; preserve $sc2Evidence" }
  } finally { Pop-Location }
} finally { Pop-Location }
```

Expected: all legacy tests and the added `MOCK-*` scope tests pass; no service or real query is launched.

- [ ] **Step 2: Run the new connector test independently**

从原生工具实际返回的 CandidateRoot 开始，命令参数显式接收此路径并进入平台cwd：

```powershell
param([Parameter(Mandatory = $true)][string]$CandidateRoot)
$candidateRoot = (Resolve-Path -LiteralPath $CandidateRoot -ErrorAction Stop).Path
$sc2Head = (& git -C $candidateRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $sc2Head -ne '28337c0ebb52afdbf61e955ecdbc22d151bcd185') { throw 'SC2 candidate HEAD differs from approved starting point' }
$runId = [guid]::NewGuid().ToString('N')
$sc2EvidenceRelative = Join-Path 'reports\sc2-biztype316-1010\runs' $runId
$sc2Evidence = Join-Path 'C:/Dev/zhuopin-ai' $sc2EvidenceRelative
Push-Location $candidateRoot
try {
  git check-ignore --quiet -- (Join-Path $sc2EvidenceRelative 'stdout.txt')
  if ($LASTEXITCODE -ne 0) { throw "Evidence path is not ignored: $sc2Evidence" }
  New-Item -ItemType Directory -Path $sc2Evidence -ErrorAction Stop | Out-Null
  Push-Location (Join-Path $candidateRoot '5-平台底座/zhuopin_platform')
  try {
  & 'C:\Dev\Codex\runtimes\zhuopin-ai\venv\Scripts\python.exe' -B -m pytest -p no:cacheprovider 'tests/test_erp_biztype316.py' -q --basetemp (Join-Path $sc2Evidence 'pytest-temp') --junitxml (Join-Path $sc2Evidence 'junit.xml') 1> (Join-Path $sc2Evidence 'stdout.txt') 2> (Join-Path $sc2Evidence 'stderr.txt')
  $code = $LASTEXITCODE
  [IO.File]::WriteAllText((Join-Path $sc2Evidence 'exit-code.txt'), "$code`n", [Text.UTF8Encoding]::new($false))
  if ($code -ne 0) { throw "pytest failed with exit code $code; preserve $sc2Evidence" }
  } finally { Pop-Location }
} finally { Pop-Location }
```

Expected: focused new connector tests pass. Plan preparation already confirmed `5-平台底座/zhuopin_platform/pyproject.toml` declares pytest in the dev dependency set and `tests/conftest.py` bootstraps imports and blocks real network calls; `tests/test_erp_biztype316.py` is directly under the existing collected `tests/` directory. Do not rerun test discovery separately.

- [ ] **Step 3: Perform the five Review Focus checks against task-owned assertions**

Confirm Review Focus 1 in Tasks 1/2; Focus 2 in Tasks 3/4; Focus 3 in Tasks 2/3; Focus 4 in Tasks 1/5; Focus 5 in Tasks 2/4/5. Review must verify default legacy path and shared dataset remain byte/value stable under no-scope calls.

- [ ] **Step 4: Review against every spec scenario and write back formal status**

Map every scenario in `specs/sc2-receipts-biztype316/spec.md` to the test names above before any implementation is considered complete. Record the approved D1–D10 decisions in the formal OpenSpec package under the existing task 1.2; record test/code results and task status there. Do not mark task 1.4 as product completion and do not close #538.

- [ ] **Step 5: Register touched files and let CommitSweep handle commits**

Use the project's normal lock and §二 registration sequence for the implementation work; do not run manual `git commit` and do not invoke the main-repository `CommitSweep` from a candidate tree. Hand registered changes to `CommitSweep` only through its configured, supported execution environment. If that handoff cannot be established, stop after registration and ask Shao Peishen to choose the supported next step. Any ff, deployment, real-data query, external message or release remains outside this plan and requires separate scope-specific approval.

---

## External Evidence and Stage Gates

| Evidence | Current plan behavior | Stage it blocks |
|---|---|---|
| GR/Query `BizType` row field name and semantics | Connector returns `biz_type=None` unless a verified field map is supplied. Synthetic typed rows exercise A; no guessed field key. | Real-source A acceptance. |
| Server `bizType=316` filter behavior across all pages | B remains disabled; tests can only prove request construction and fail-closed guard behavior. | Enabling B / real-source acceptance. |
| ERP raw receipt type field name and its confirmed semantics | Field map defaults absent; the real scoped result stays incomplete and A cannot run against production rows. Synthetic field-map tests can proceed. | Mapping real rows and real-data acceptance for A. |
| Actual organization request source | Record unknown/observed context; do not hardcode `Org=Z`. | Claiming a target-organization full value if organization boundary is required. |
| GR/Query row status, return, void, reversal semantics | Preserve current rows and BusinessDate inclusion. | Only a later separately approved exclusion change, not this implementation. |
| BusinessDate, stable line identity, quantity, unit price, supplier, pagination completeness | Missing data becomes a scope/metric-specific incompleteness reason. | Full corresponding real metric/detail acceptance. |
| Knowledge holder/Owner, Backup, and value baseline | Remain unknown; not inferred from IT/采购 replies. | Professional signoff, real business acceptance and baseline claims; not Native synthetic work after plan approval. |
| SC2 reports/cache directory overrides | Tests use `tmp_path`; implementation rechecks resolved default and explicit override paths before writing. | Real deployment/runtime enablement if override is configured. |

## Plan Self-Review

- **Spec coverage:** explicit filter verified; A restricted to an unfiltered full batch; B restricted to independently verified applied filtering; BizType follows approved `int | str | None` normalization (native integer excluding bool or strict ASCII integer string); bad strings, booleans, floats, and fractional values fail closed; strict date parsing preserves invalid/unknown candidates as missing BusinessDate; invalid bool/NaN/infinite/nonnumeric quantity/price is rejected and missing numeric fields remain explicit gaps; 4 metrics/detail use the same subset; no Org=Z/status exclusions; old frozen report/schema/cache preservation. Each maps to Tasks 1–5 and Review Focus 1–5.
- **Compatibility:** `ReceiptRecord`, default `FrozenDataset.receipts`, old paths, schema 1, legacy connector method/cache JSON key set, and old report links remain the no-scope path. New scope uses explicit optional interfaces and identity bound to days/type/map/capability.
- **Scope construction:** explicit POST refresh constructs one `(FrozenDataset, ReceiptScopeResult)` from a single receipt batch, then persists report/dataset with a matching run ID; GET scope reads the pair only, and incomplete scope remains recordable while detail export returns 409.
- **Window/UI coverage:** metric and detail tests cover inclusive start/end of each of the three windows plus rows outside the overall range; HTML/index emits scope on every section/window CSV URL; receipt CSV consumes the validated scope, while scoped order/open CSV responses match the existing no-scope table builder byte-for-byte.
- **Pagination/cache:** actual page-loop tests replace only `_fi_request`, never the page reader; absent/mismatched totals and premature page termination fail closed. Every mapped receipt batch cache identity binds days, requested type, map ID, and capability ID.
- **Scope-source guards:** typed A input with `requested_biz_type=316` or `filter_applied=True` is rejected; B needs the exact requested filter, `filter_applied=True`, and the verified capability ID matching the batch. Native integer and strict integer-string BizType rows normalize to the same membership; invalid values remain unknown. The real-feed pairing and MockFeed incomplete-scope tests each have one definition. Invalid BusinessDate candidates remain represented in the batch and make scope incomplete; only strictly parsed valid dates may be excluded as outside the lookback. Missing numeric placeholders remain marked as gaps and cannot produce complete scoped metrics; malformed numeric values raise before a batch is cached.
- **Scope:** no broad UI redesign, generic snapshot service, production query, filter enablement, real-data acceptance, release, or recovery-candidate work.
- **Known planning limitation:** No verified raw ERP BizType field mapping or server-filter evidence is present in the source contract read for this plan. Production source therefore passes no map/capability and never requests BizType filtering; this blocks real-source completeness, not the fail-closed interfaces or synthetic tests. No real query, product test, or service action is part of plan preparation.
- **Status:** written as an implementation plan only. No product code/tests were edited or run during planning. Formal D1–D10 approval writeback and task 1.2 status remain Root-managed before code implementation; this plan does not itself authorize code or execution.
