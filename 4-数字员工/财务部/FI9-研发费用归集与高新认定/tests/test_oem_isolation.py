"""FI9 · OEM 隔离层接法测试 —— `EE-3` 五条定夺项（Shao Peishen 2026-09-03 裁决）的落地校验。

覆盖（看护批 `B-0903_70` §三 A1 步骤 7）：
  ⑴ 三态形态（`oem_customer`：None／注册 OEM 名／`NON_OEM_PROJECT`）；
  ⑵ 未判归属不进汇总（③(b)）；
  ⑶ 禁止从项目号/项目名推导归属（④(a)）；
  ⑷ E2.2：guard 在入口对每个项目调一次，不在每行费用记录上调；
  ⑸ ②(c) 跨 OEM 汇总开关默认 OFF、fail-loud，且照 D2.4 做两层
     （一次性变异实测 ＋ 常驻元测试）证明"关掉守卫即失败"不是碰巧通过。
"""
from __future__ import annotations

import pytest

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.data_isolation_layer import CrossOEMAccessError, OEMRouter

from fi9_rd_cost import config, oem_isolation
from fi9_rd_cost.models import NON_OEM_PROJECT, RdProject


def _project(project_id: str, oem_customer=None, project_name: str = "示例项目") -> RdProject:
    return RdProject(project_id, project_name, "2026-01-01", oem_customer=oem_customer)


# ══ ⑴ 三态形态 ══════════════════════════════════════════════════════════════
def test_oem_customer_defaults_to_none():
    """未判是默认态，不是需要显式传参才能拿到的态。"""
    assert RdProject("RD-X", "示例", "2026-01-01").oem_customer is None


def test_oem_customer_accepts_registered_name():
    p = _project("RD-1", oem_customer="比亚迪")
    assert p.oem_customer == "比亚迪"


def test_non_oem_project_sentinel_is_distinct_from_unjudged():
    """🔴 `NON_OEM_PROJECT` 与 `None`（未判）绝不能是同一个值——两者语义相反。"""
    assert NON_OEM_PROJECT is not None
    p = _project("RD-2", oem_customer=NON_OEM_PROJECT)
    assert p.oem_customer == NON_OEM_PROJECT
    assert p.oem_customer is not None


# ══ ⑵+⑷ resolve_project_source：入口层判定，一态一分支 ═══════════════════════
def test_resolve_project_source_unjudged_returns_none():
    router = OEMRouter()
    assert oem_isolation.resolve_project_source(_project("RD-1"), router) is None


def test_resolve_project_source_non_oem_returns_sentinel():
    router = OEMRouter()
    result = oem_isolation.resolve_project_source(_project("RD-2", oem_customer=NON_OEM_PROJECT), router)
    assert result == NON_OEM_PROJECT


def test_resolve_project_source_registered_oem_returns_display_name():
    """返回值是客户显示名（"比亚迪"），不是内部 collection key（"oem_byd"）——
    与 `AuditEvent.oem_context` 的既有填法保持一致。"""
    router = OEMRouter()
    result = oem_isolation.resolve_project_source(_project("RD-3", oem_customer="比亚迪"), router)
    assert result == "比亚迪"


def test_resolve_project_source_unregistered_oem_fails_closed_and_audited(tmp_path):
    """未注册/拼写变体（如 "BYD" 而非 "比亚迪"）在入口层 fail-closed 并写审计（规范 §3.1/§3.2）。"""
    audit = AuditLogger.jsonl(tmp_path / "iso.jsonl")
    router = OEMRouter(audit=audit)
    with pytest.raises(CrossOEMAccessError):
        oem_isolation.resolve_project_source(_project("RD-4", oem_customer="BYD"), router)
    recs = audit.query_by(scenario="DATA_ISOLATION")
    assert len(recs) == 1
    assert recs[0]["decision"]["oem"] == "BYD"


# ══ ⑵+⑶ partition_by_ownership：未判排除、禁推导 ═════════════════════════════
def test_partition_by_ownership_excludes_unjudged():
    router = OEMRouter()
    projects = [
        _project("RD-1", oem_customer="比亚迪"),
        _project("RD-2", oem_customer=None),
        _project("RD-3", oem_customer=NON_OEM_PROJECT),
    ]
    partition = oem_isolation.partition_by_ownership(projects, router)
    assert [p.project_id for p in partition.eligible] == ["RD-1", "RD-3"]
    assert [p.project_id for p in partition.excluded_unjudged] == ["RD-2"]


def test_partition_excluded_project_ids_is_prominent_and_correct():
    """③ 裁决原文：排除清单须可在报告显要位置直接展示，不是要从对象里深挖。"""
    router = OEMRouter()
    partition = oem_isolation.partition_by_ownership(
        [_project("RD-1"), _project("RD-2", oem_customer="上汽")], router
    )
    assert partition.excluded_project_ids == ("RD-1",)


def test_no_derivation_from_project_name_or_id():
    """🔴 ④(a) 核心反例：项目名字面上"看起来像"比亚迪项目，但 `oem_customer` 未判，
    仍必须落入"未判被排除"，绝不能被项目名/项目号静默推导成"比亚迪"。

    本用例即便 `oem_isolation.py` 一行都不检视 `project_name`/`project_id` 也会自然
    通过（因为代码结构上根本不读这两个字段做归属判定）——它钉住的是"未来有人手滑
    加了一条 `if '比亚迪' in project.project_name: ...` 式推导"这种回归。
    """
    lookalike = RdProject(
        project_id="RD-2026-BYD-LOOKALIKE-001",
        project_name="比亚迪某车型 ECU 平台预研",
        start_date="2026-01-01",
        oem_customer=None,  # 🔴 未判——即便项目名强烈暗示归属
    )
    router = OEMRouter()
    assert oem_isolation.resolve_project_source(lookalike, router) is None

    partition = oem_isolation.partition_by_ownership([lookalike], router)
    assert lookalike in partition.excluded_unjudged
    assert lookalike not in partition.eligible
    assert partition.excluded_project_ids == ("RD-2026-BYD-LOOKALIKE-001",)


def test_guard_called_once_per_project_not_per_row():
    """🔴 E2.2：入口层对每个项目调一次，不因该项目名下有多条费用记录就调多次。"""
    calls: list[str] = []
    router = OEMRouter()
    original_resolve = router.resolve

    def counting_resolve(oem):
        calls.append(oem)
        return original_resolve(oem)

    router.resolve = counting_resolve  # type: ignore[method-assign]

    projects = [
        _project("RD-1", oem_customer="比亚迪"),
        _project("RD-2", oem_customer="比亚迪"),
        _project("RD-3", oem_customer="上汽"),
    ]
    # 即便每个项目背后有多条 CostEntry（本函数不接触 CostEntry，只按项目粒度调用），
    # resolve 的调用次数也必须恰好等于项目数，不随费用行数变化。
    oem_isolation.partition_by_ownership(projects, router)
    assert calls == ["比亚迪", "比亚迪", "上汽"]


# ══ ⑸ ②(c) 跨 OEM 汇总闸：开关默认 OFF + 三道锁 ═══════════════════════════════
def _eligible_partition() -> oem_isolation.OwnershipPartition:
    return oem_isolation.OwnershipPartition(
        eligible=[
            _project("RD-1", oem_customer="比亚迪"),
            _project("RD-2", oem_customer="上汽"),
            _project("RD-3", oem_customer=NON_OEM_PROJECT),
        ],
        excluded_unjudged=[_project("RD-9", oem_customer=None)],
    )


def test_cross_oem_aggregation_disabled_by_default():
    """🔴 不依赖任何 monkeypatch——本用例证明真实默认环境下开关就是 OFF。"""
    assert config.cross_oem_aggregation_enabled() is False


def test_cross_oem_gate_fails_loud_when_switch_off():
    """开关 OFF ⇒ fail-loud（抛异常），不是静默返回空结果。"""
    with pytest.raises(oem_isolation.CrossOemAggregationDisabledError):
        oem_isolation.cross_oem_filing_gate(
            filing_period="2026H2", operator="示例经办人", approver="示例审批人",
            partition=_eligible_partition(),
        )


def test_switch_off_gate_is_load_bearing(monkeypatch):
    """🔴 证明"开关 OFF ⇒ 拒绝"是靠 `cross_oem_filing_gate` 里那行真检查成立的，
    不是碰巧通过（同既有 D2.4 做法：一次性变异实测 ＋ 常驻元测试）。

    做法：把开关判定 monkeypatch 成"永远算开着"（模拟"有人嫌这行检查碍事，顺手删掉/
    绕过"），复刻上一条"开关 OFF 必须拒绝"的调用——它必须**不再拒绝**。若它仍然拒绝，
    说明上一条用例根本不是靠这行检查通过的，那条绿灯是假的。
    """
    monkeypatch.setattr(oem_isolation.config, "cross_oem_aggregation_enabled", lambda: True)

    # 真实环境变量仍是默认 OFF（未设置），但守卫被绕过后，同一次调用不再抛
    # CrossOemAggregationDisabledError——证明原先的拒绝确实来自这行检查。
    receipt = oem_isolation.cross_oem_filing_gate(
        filing_period="2026H2", operator="示例经办人", approver="示例审批人",
        partition=_eligible_partition(),
    )
    assert receipt.filing_period == "2026H2"


@pytest.mark.parametrize("missing_field", ["filing_period", "operator", "approver"])
def test_cross_oem_gate_requires_all_lock_fields(monkeypatch, missing_field):
    monkeypatch.setattr(oem_isolation.config, "cross_oem_aggregation_enabled", lambda: True)
    fields = {"filing_period": "2026H2", "operator": "示例经办人", "approver": "示例审批人"}
    fields[missing_field] = ""
    with pytest.raises(oem_isolation.CrossOemFilingLockError):
        oem_isolation.cross_oem_filing_gate(partition=_eligible_partition(), **fields)


def test_cross_oem_gate_succeeds_and_excludes_unjudged(monkeypatch):
    monkeypatch.setattr(oem_isolation.config, "cross_oem_aggregation_enabled", lambda: True)
    partition = _eligible_partition()
    receipt = oem_isolation.cross_oem_filing_gate(
        filing_period="2026H2", operator="示例经办人", approver="示例审批人",
        partition=partition,
    )
    assert receipt.covered_oems == ("上汽", "比亚迪")  # 字典序，NON_OEM_PROJECT 不计入
    assert set(receipt.covered_project_ids) == {"RD-1", "RD-2", "RD-3"}
    assert "RD-9" not in receipt.covered_project_ids  # 未判项目绝不进汇总
    assert receipt.scope_disclaimer == config.EXTERNAL_FILING_GATE  # 锁①：指认既有红线


def test_cross_oem_gate_oem_context_is_non_oem_sentinel_when_no_registered_oem(monkeypatch, tmp_path):
    """边界：本次覆盖只有 NON_OEM_PROJECT、不含任何已注册 OEM 时，`oem_context` 填哨兵本身。"""
    monkeypatch.setattr(oem_isolation.config, "cross_oem_aggregation_enabled", lambda: True)
    partition = oem_isolation.OwnershipPartition(eligible=[_project("RD-1", oem_customer=NON_OEM_PROJECT)])
    audit = AuditLogger.jsonl(tmp_path / "iso.jsonl")
    oem_isolation.cross_oem_filing_gate(
        filing_period="2026H2", operator="示例经办人", approver="示例审批人",
        partition=partition, audit=audit,
    )
    recs = audit.query_by(scenario="FI9", action="cross_oem_aggregation")
    assert recs[-1]["oem_context"] == NON_OEM_PROJECT


def test_cross_oem_gate_writes_audit_with_full_decision(monkeypatch, tmp_path):
    monkeypatch.setattr(oem_isolation.config, "cross_oem_aggregation_enabled", lambda: True)
    audit = AuditLogger.jsonl(tmp_path / "cross_oem.jsonl")
    partition = _eligible_partition()
    oem_isolation.cross_oem_filing_gate(
        filing_period="2026H2", operator="示例经办人", approver="示例审批人",
        partition=partition, audit=audit,
    )
    recs = audit.query_by(scenario="FI9", action="cross_oem_aggregation")
    assert len(recs) == 1
    rec = recs[0]
    assert rec["evaluator"] == "示例审批人"
    assert rec["automation_level"] == "L2"
    assert rec["oem_context"] == "上汽,比亚迪"
    decision = rec["decision"]
    assert decision["filing_period"] == "2026H2"
    assert decision["operator"] == "示例经办人"
    assert decision["approver"] == "示例审批人"
    assert set(decision["covered_project_ids"]) == {"RD-1", "RD-2", "RD-3"}
    assert decision["excluded_unjudged_project_ids"] == ["RD-9"]
    assert decision["rule_version"] == config.RULE_VERSION  # G-5 反向依赖同样适用于本场景新事件


def test_cross_oem_gate_no_audit_still_succeeds(monkeypatch):
    """未注入 audit 仍可过闸（与 `OEMRouter` 的"无 audit 时仅抛错/放行"先例一致）——
    但三道锁②③的强制性不因此松动，本用例只确认不因缺 audit 而报错。"""
    monkeypatch.setattr(oem_isolation.config, "cross_oem_aggregation_enabled", lambda: True)
    receipt = oem_isolation.cross_oem_filing_gate(
        filing_period="2026H2", operator="示例经办人", approver="示例审批人",
        partition=_eligible_partition(),
    )
    assert receipt.approver == "示例审批人"
