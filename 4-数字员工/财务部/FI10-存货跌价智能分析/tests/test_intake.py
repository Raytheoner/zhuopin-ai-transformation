"""FI10 · `fi10-inventory-intake` 采集层测试 —— `tasks.md` §3（本轮唯一开工节，design `D1`）。

覆盖 `tasks.md` 3.1／3.2／3.3 三条必测项，以及 design 审定形的两条隔离形态：

  · **3.1** real 模式（真实源通道未核实）fail-loud，🔴 **不得回退 mock**；
  · **3.2** 在途量 ＝ 已订 − 已收，与 `kit_engine` 口径一致 —— 🔴 **不是重抄一遍公式，
    而是拿 `kit_engine.calc_shortage` 真跑一次做交叉核对**（同一个概念在两个场景里算出
    两个数是最难查的一类不一致，光重写公式测不出这个）；
  · **3.3** OEM 跨库访问抛 `CrossOEMAccessError`（**须实测**）；
  · **D5** guard 调在取数入口、归属校验用 `OEMRouter.resolve()`；
  · **D11** 物料归属 ＝ 关联项目客户的集合，多值按最严；
    🔴 「无关联项目」与「归属未判」**两个哨兵不得合并**（design 风险表第三行点名的返工点）。

🔴 **本节不读任何判据**（账龄／在途／BOM／OEM 项目全是取数）——末尾有一条元测试钉住这件事：
采集层一旦读判据，本轮「唯一能端到端真测」的前提就没了（`D1` 的成因）。
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.data_isolation_layer import CrossOEMAccessError, OEMRouter
from zhuopin_platform.data_isolation_layer.router import REGISTERED_OEMS

from fi10_inventory_writedown import config, intake
from fi10_inventory_writedown.models import InTransitPo, OemProjectPhase


def _phase(project_id: str, oem_customer: str, materials: list[str],
           phase: str = "量产") -> OemProjectPhase:
    return OemProjectPhase(project_id, oem_customer, phase, materials, "2026-03-01")


# ══ 3.1 real 模式 fail-loud，不得回退 mock ═════════════════════════════════════
def test_real_mode_fails_loud():
    """🔴 U9C 库存通道与 PLM 取数通道**两条都未核实、且都无主**（design Open Questions B-1）。

    ⇒ real 模式一律 fail-loud。这条用例守的是「通道没核实」这个事实本身不被静默绕过。
    """
    with pytest.raises(intake.ChannelNotVerifiedError) as exc:
        intake.collect(as_of_date="2026-09-07", mode=intake.MODE_REAL)
    msg = str(exc.value)
    assert "U9C" in msg          # 库存账龄／在途采购通道
    assert "PLM" in msg          # OEM 项目生命周期通道
    assert "不得回退 mock" in msg


def test_real_mode_does_not_touch_mock_files(monkeypatch):
    """🔴 「fail-loud」与「先读了 mock 再报错」是两件事 —— 后者会把假数据带进 real 调用方。

    把读文件这一步换成"被调用即失败"，real 模式仍须抛通道未核实错。
    """
    def _boom(*_a, **_kw):
        raise AssertionError("real 模式不得读取任何 mock 夹具")

    monkeypatch.setattr(intake, "_read_csv", _boom)
    with pytest.raises(intake.ChannelNotVerifiedError):
        intake.collect(as_of_date="2026-09-07", mode=intake.MODE_REAL)


def test_real_mode_message_is_the_config_text_not_a_paraphrase():
    """通道未核实的说明只有一处正本（`config`），采集层不另写一份会漂的措辞。"""
    with pytest.raises(intake.ChannelNotVerifiedError) as exc:
        intake.collect(as_of_date="2026-09-07", mode=intake.MODE_REAL)
    assert config.U9C_INVENTORY_NOT_READY in str(exc.value)
    assert config.PLM_PROJECT_CHANNEL_NOT_READY in str(exc.value)


def test_unknown_mode_fails_loud():
    """未知模式不得被当成 mock 兜底 —— 拼错 `real` 就静默拿到假数据是同族事故。"""
    with pytest.raises(ValueError):
        intake.collect(as_of_date="2026-09-07", mode="prod")


def test_default_mode_comes_from_config():
    """默认模式取 `config.DATA_SOURCE_DEFAULT`（骨架期 ＝ mock），采集层不自定第二个默认值。"""
    assert intake._resolve_mode(None) == config.DATA_SOURCE_DEFAULT


# ══ 3.2 在途量口径与 kit_engine 一致（交叉核对，不是重抄公式）═══════════════════
def test_qty_in_transit_by_material_aggregates_per_material():
    pos = [
        InTransitPo("PO-1", "MAT-001", 2000, 500, 37.90, "2026-09-25"),
        InTransitPo("PO-2", "MAT-001", 300, 300, 37.50, "2026-09-30"),   # 已全收 ⇒ 在途 0
        InTransitPo("PO-3", "MAT-003", 1000, 0, 12.60, "2026-10-10"),
    ]
    assert intake.qty_in_transit_by_material(pos) == {
        "MAT-001": pytest.approx(1500.0),
        "MAT-003": pytest.approx(1000.0),
    }


def test_qty_in_transit_matches_kit_engine_convention():
    """🔴 拿 `kit_engine.calc_shortage` 真跑一次，反解它眼里的在途量，与本层结果比对。

    `calc_shortage` 的可用量 ＝ 当前库存 − 安全库存 + 在途；把库存与安全库存都置 0，
    缺口 ＝ 毛需求 − 在途 ⇒ **在途 ＝ 毛需求 − 缺口**。这样比的是两边**真实运行**出来的数，
    而不是两处各写一遍 `qty_ordered - qty_received`（后者两边一起写错也照样通过）。
    """
    from zhuopin_platform.agents import kit_engine
    from zhuopin_platform.shared_tools.models import InventoryRow, PurchaseOrder

    fi10_pos = [
        InTransitPo("PO-1", "MAT-001", 2000, 500, 37.90, "2026-09-25"),
        InTransitPo("PO-2", "MAT-001", 300, 300, 37.50, "2026-09-30"),
        InTransitPo("PO-3", "MAT-003", 1000, 0, 12.60, "2026-10-10"),
    ]
    kit_pos = [
        PurchaseOrder(p.po_no, p.material_id, int(p.qty_ordered), int(p.qty_received),
                      p.eta, "", "SUP-X", "in_transit")
        for p in fi10_pos
    ]
    gross = {"MAT-001": 9999.0, "MAT-003": 9999.0}      # 取一个必然缺口的毛需求
    inventory = [
        InventoryRow("MAT-001", "示例芯片 A", 0, 0, "PCS", "2026-09-07"),
        InventoryRow("MAT-003", "示例连接器 C", 0, 0, "PCS", "2026-09-07"),
    ]
    shortages, _missing = kit_engine.calc_shortage(gross, inventory, kit_pos)

    kit_engine_view = {m: gross[m] - gap for m, gap in shortages.items()}
    fi10_view = intake.qty_in_transit_by_material(fi10_pos)
    assert fi10_view == pytest.approx(kit_engine_view)


# ══ 3.3 ＋ D5 OEM 隔离：取数入口一次判定，跨库实测抛错 ════════════════════════
def test_resolve_phase_owner_returns_display_name(mock_router):
    """归属校验走 `OEMRouter.resolve()`（**不是** `guard()`，D5-2），返回客户显示名。"""
    owner = intake.resolve_phase_owner(_phase("PRJ-A", "OEM-占位甲", ["MAT-001"]), mock_router)
    assert owner == "OEM-占位甲"


def test_resolve_phase_owner_unregistered_fails_closed_and_audited(tmp_path):
    """未注册／拼写变体的客户名在取数入口即 fail-closed 并留痕（规范 §3.1／§3.2）。"""
    audit = AuditLogger.jsonl(tmp_path / "iso.jsonl")
    router = OEMRouter(registered=dict(intake.MOCK_OEM_REGISTRY), audit=audit)
    with pytest.raises(CrossOEMAccessError):
        intake.resolve_phase_owner(_phase("PRJ-X", "OEM-没注册的", ["MAT-001"]), router)
    recs = audit.query_by(scenario="DATA_ISOLATION")
    assert len(recs) == 1
    assert recs[0]["decision"]["oem"] == "OEM-没注册的"


def test_cross_oem_project_read_is_denied(tmp_path):
    """🔴 3.3 必测项：以某客户身份读另一客户的项目数据 ⇒ `CrossOEMAccessError` ＋ 留痕。"""
    audit = AuditLogger.jsonl(tmp_path / "iso.jsonl")
    router = OEMRouter(registered=dict(intake.MOCK_OEM_REGISTRY), audit=audit)
    other = _phase("PRJ-B", "OEM-占位乙", ["MAT-003"])
    with pytest.raises(CrossOEMAccessError):
        intake.read_phase_as("OEM-占位甲", other, router)
    denied = audit.query_by(scenario="DATA_ISOLATION")
    assert len(denied) == 1
    assert denied[0]["decision"]["reason"] == "跨客户专属库访问"


def test_same_oem_project_read_is_allowed(mock_router):
    own = _phase("PRJ-A", "OEM-占位甲", ["MAT-001"])
    assert intake.read_phase_as("OEM-占位甲", own, mock_router) is own


def test_isolated_view_only_shows_own_customer(mock_router):
    """逐客户隔离视图：只出现本客户的项目，不靠调用方自己记得过滤。"""
    phases = [
        _phase("PRJ-A", "OEM-占位甲", ["MAT-001"]),
        _phase("PRJ-B", "OEM-占位乙", ["MAT-003"]),
    ]
    view = intake.isolated_view("OEM-占位甲", phases, mock_router)
    assert [p.project_id for p in view] == ["PRJ-A"]


def test_shared_material_appears_in_every_owner_view(mock_router):
    """🔴 D11「多值按最严」：共用料进**任一** OEM 的隔离视图都要出现，明细逐客户拆行。"""
    phases = [
        _phase("PRJ-A", "OEM-占位甲", ["MAT-009"]),
        _phase("PRJ-B", "OEM-占位乙", ["MAT-009"]),
    ]
    for oem in ("OEM-占位甲", "OEM-占位乙"):
        view = intake.isolated_view(oem, phases, mock_router)
        assert any("MAT-009" in p.material_ids for p in view)


# ══ D11 两个哨兵不得合并 ══════════════════════════════════════════════════════
def test_two_ownership_sentinels_are_distinct():
    """🔴 「无关联项目（通用料）」与「关联项目归属未判」语义相反，共用表示即错。

    与 FI9 `None` vs `NON_OEM_PROJECT` 是同族错误：一旦合并，「这个料谁都不专属」和
    「压根没人看过这个料属于谁」就变成同一件事，后者会被静默当通用料放行。
    """
    assert intake.NO_LINKED_PROJECT != intake.OWNERSHIP_UNJUDGED
    assert intake.NO_LINKED_PROJECT is not None
    assert intake.OWNERSHIP_UNJUDGED is not None
    assert intake.NO_LINKED_PROJECT.strip() != ""
    assert intake.OWNERSHIP_UNJUDGED.strip() != ""
    # 两个哨兵都不得与任何真实注册 OEM 名冲突
    assert intake.NO_LINKED_PROJECT not in REGISTERED_OEMS
    assert intake.OWNERSHIP_UNJUDGED not in REGISTERED_OEMS


def test_no_linked_project_material_goes_to_general_layer(mock_router):
    """通用料（无关联项目）⇒ 空集哨兵，走通用层，不是错误。"""
    own = intake.classify_material_ownership("MAT-002", [_phase("PRJ-A", "OEM-占位甲", ["MAT-001"])],
                                             mock_router)
    assert own.state == intake.NO_LINKED_PROJECT
    assert own.owners == ()
    assert own.is_general is True
    assert intake.require_owners(own) == ()


def test_unjudged_material_is_not_silently_general(mock_router):
    """🔴 关联项目归属未判 ⇒ 另一个哨兵 ＋ fail-loud，**不得静默当通用料**。"""
    phases = [_phase("PRJ-Z", "", ["MAT-007"])]      # 源里客户名为空 ＝ 归属未判
    own = intake.classify_material_ownership("MAT-007", phases, mock_router)
    assert own.state == intake.OWNERSHIP_UNJUDGED
    assert own.state != intake.NO_LINKED_PROJECT
    assert own.is_general is False
    with pytest.raises(intake.OwnershipUnjudgedError):
        intake.require_owners(own)


def test_single_owner_material(mock_router):
    own = intake.classify_material_ownership("MAT-001", [_phase("PRJ-A", "OEM-占位甲", ["MAT-001"])],
                                             mock_router)
    assert own.state == intake.OWNERSHIP_OEM
    assert own.owners == ("OEM-占位甲",)


def test_multi_owner_material_keeps_the_whole_set(mock_router):
    """🔴 否决「强制一料一主项目」：多个 OEM 就是多个，取用量最大的那个 ＝ 制造假数据。"""
    phases = [
        _phase("PRJ-A", "OEM-占位甲", ["MAT-009"]),
        _phase("PRJ-B", "OEM-占位乙", ["MAT-009"]),
        _phase("PRJ-C", "OEM-占位甲", ["MAT-009"]),      # 同一客户两个项目 ⇒ 去重
    ]
    own = intake.classify_material_ownership("MAT-009", phases, mock_router)
    assert own.state == intake.OWNERSHIP_OEM
    # 🔴 「字典序」＝ Python `sorted()` 的码位序（沿用 FI9 `covered_oems` 的既有实现），
    # **不是拼音序也不是笔画序**：中文里码位序常与直觉相反（"乙" U+4E59 < "甲" U+7532），
    # 这条断言刻意把实际次序钉死，免得后来者"顺手改成拼音序"而两个场景的审计串不一致。
    assert own.owners == ("OEM-占位乙", "OEM-占位甲")


def test_unjudged_wins_over_judged_when_material_is_shared(mock_router):
    """一个料同时挂着已判与未判项目 ⇒ 按最严：整体算未判，fail-loud。

    否则「已判的那半」会让这个料看起来归属清楚，未判的那半就此消失。
    """
    phases = [
        _phase("PRJ-A", "OEM-占位甲", ["MAT-009"]),
        _phase("PRJ-Z", "", ["MAT-009"]),
    ]
    own = intake.classify_material_ownership("MAT-009", phases, mock_router)
    assert own.state == intake.OWNERSHIP_UNJUDGED


# ══ D5-3 AuditEvent.oem_context 填法 ═════════════════════════════════════════
def test_audit_oem_context_is_sorted_deduped_and_comma_joined():
    """次序 ＝ 码位序（同 FI9 `covered_oems`），非拼音序——见上一条用例的注。"""
    assert intake.audit_oem_context(("OEM-占位甲", "OEM-占位乙", "OEM-占位甲")) == \
        "OEM-占位乙,OEM-占位甲"
    assert intake.audit_oem_context(("比亚迪", "上汽", "上汽")) == "上汽,比亚迪"


def test_audit_oem_context_empty_is_the_general_sentinel():
    """空集不得填成空串 —— 空串在审计里读不出「这是通用料」还是「忘填了」。"""
    assert intake.audit_oem_context(()) == intake.NO_LINKED_PROJECT


# ══ mock 模式端到端：三类输入齐备、各带来源引用 ═══════════════════════════════
def test_collect_mock_bundle_has_three_inputs_with_sources():
    bundle = intake.collect(as_of_date="2026-09-03", mode=intake.MODE_MOCK)
    assert bundle.as_of_date == "2026-09-03"
    assert len(bundle.aging) == 3
    assert len(bundle.in_transit) == 2
    assert len(bundle.bom_usage) == 2
    assert len(bundle.oem_phases) == 2
    # spec「三类输入齐备」场景：各带来源引用
    for key in ("inventory_aging", "in_transit_po", "bom_usage", "oem_project_phase"):
        assert key in bundle.data_sources
        assert bundle.data_sources[key].startswith("mock:")
    assert bundle.mode == intake.MODE_MOCK


def test_collect_mock_bundle_parses_types_and_derivations():
    bundle = intake.collect(as_of_date="2026-09-03", mode=intake.MODE_MOCK)
    aging = {a.material_id: a for a in bundle.aging}
    assert aging["MAT-001"].book_cost == pytest.approx(46200.0)
    assert aging["MAT-001"].aging_days == 296
    assert isinstance(aging["MAT-001"].aging_days, int)
    transit = {p.po_no: p for p in bundle.in_transit}
    assert transit["PO-0201"].qty_in_transit == pytest.approx(1500.0)
    bom = {b.material_id: b for b in bundle.bom_usage}
    assert bom["MAT-003"].active is False        # 机型已停产：不能被读成字符串 "False"
    assert bom["MAT-001"].active is True


def test_collect_builds_ownership_index_at_the_entry():
    """🔴 D5-1：guard 调在**取数入口**，采集完即带好归属索引。

    散在每一行的 guard 漏掉一处不会有任何信号；入口只有一处，漏了整条路不通。
    """
    bundle = intake.collect(as_of_date="2026-09-03", mode=intake.MODE_MOCK)
    assert bundle.ownership["MAT-001"].owners == ("OEM-占位甲",)
    assert bundle.ownership["MAT-003"].owners == ("OEM-占位乙",)
    assert bundle.ownership["MAT-002"].state == intake.NO_LINKED_PROJECT   # 通用料


def test_collect_fails_loud_on_unjudged_ownership_in_source(mock_fixture_copy):
    """🔴 源里客户名为空 ⇒ 取数入口即 fail-loud，不静默当通用料带进下游。"""
    csv_path = mock_fixture_copy / "oem_project_phase.csv"
    csv_path.write_text(
        "project_id,oem_customer,phase,material_ids,phase_date\n"
        "PRJ-A,,量产,MAT-001,2026-03-01\n",
        encoding="utf-8",
    )
    with pytest.raises(intake.OwnershipUnjudgedError):
        intake.collect(as_of_date="2026-09-03", mode=intake.MODE_MOCK, base_dir=mock_fixture_copy)


def test_collect_parses_multi_material_projects(mock_fixture_copy):
    """一个项目挂多个料用 `;` 分隔（CSV 的 `,` 已被列分隔占用）。"""
    (mock_fixture_copy / "oem_project_phase.csv").write_text(
        "project_id,oem_customer,phase,material_ids,phase_date\n"
        "PRJ-A,OEM-占位甲,量产,MAT-001;MAT-002,2026-03-01\n",
        encoding="utf-8",
    )
    bundle = intake.collect(as_of_date="2026-09-03", mode=intake.MODE_MOCK,
                            base_dir=mock_fixture_copy)
    assert bundle.oem_phases[0].material_ids == ["MAT-001", "MAT-002"]
    assert bundle.ownership["MAT-002"].owners == ("OEM-占位甲",)


# ══ mock 夹具与 mock 注册表：不得沾真实 OEM 名 ═════════════════════════════════
def test_mock_fixture_carries_no_real_oem_name(mock_dir):
    """spec 场景「夹具不得含真实客户名」—— 夹具里放真名 ＝ 把隔离边界的第一道口子开在测试数据上。"""
    text = (mock_dir / "oem_project_phase.csv").read_text(encoding="utf-8")
    for real_oem in REGISTERED_OEMS:
        assert real_oem not in text


def test_mock_registry_is_disjoint_from_the_real_one():
    """🔴 mock 注册表只为 mock 夹具而存在，与平台真实注册表**没有交集**。

    夹具用占位客户名（spec 要求），而占位名在平台注册表里必然未注册 ⇒ 若不另给一份
    mock 注册表，`resolve()` 会把 mock 模式整条打死；而若把占位名塞进平台注册表，
    就等于在生产注册表里凭空多出两个"客户"。
    """
    assert set(intake.MOCK_OEM_REGISTRY) & set(REGISTERED_OEMS) == set()
    assert set(intake.MOCK_OEM_REGISTRY) == {"OEM-占位甲", "OEM-占位乙", "OEM-占位丙"}


def test_real_mode_router_uses_the_platform_registry():
    """real 模式的 router 用平台注册表，绝不带上 mock 占位客户。"""
    router = intake.build_router(intake.MODE_REAL)
    assert set(router.registered) == set(REGISTERED_OEMS)
    for placeholder in intake.MOCK_OEM_REGISTRY:
        assert placeholder not in router.registered


# ══ 元测试：采集层不读任何判据（D1 的成因）═══════════════════════════════════
def test_intake_layer_reads_no_criteria():
    """🔴 §3 是本轮唯一能端到端真测的部分，前提就是它不读判据。

    一旦这里出现 `CRITERIA.value_of(...)`，采集层就只剩 fail-loud 分支可测，
    `D1`（只做 §3）这条路线本身就失效了。
    """
    src = inspect.getsource(intake)
    assert "value_of" not in src
    assert "CRITERIA" not in src


def test_intake_produces_no_writedown_or_alert():
    """§4／§5 未开工 ⇒ 采集层不得旁路产出跌价测试结果或预警。"""
    src = inspect.getsource(intake)
    for forbidden in ("WritedownTest", "WritedownAlert", "ProvisionAdvice"):
        assert forbidden not in src
