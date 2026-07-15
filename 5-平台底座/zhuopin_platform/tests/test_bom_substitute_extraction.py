"""BOM 项次与替代料关系提取（C-1，sc8-baoguan-substitute-partial-kit，2026-07-15）。

背景：`get_bom_for_products` 现状完全不提取 `m_sequence`/`m_componentType`，也不读取
主件行嵌套的 `m_bOMCompSubstituteDTO4CreateSv` 替代料列表。口径定稿（`保供看板v2-
口径定稿.md` §2 C-1·①）生产只读实测确认：替代料嵌套在主件行自己的
`m_bOMCompSubstituteDTO4CreateSv` 子列表里（不是同级平铺重复序号的兄弟行），
与主件行共享同一 `m_sequence`。

⚠️ 本文件用的替代料 DTO 内部字段结构（是否自带独立 `m_usageQty`/`m_scrap`/
`m_itemMaster`，还是完全继承主件行）**未经真实验证**（design.md Open Question #1，
tasks.md 1.1）——本沙箱环境无 LAN 访问 U9C，无法做生产只读实测。本测试按 design.md
D2 的假设建模：替代料 DTO 自带 `m_itemMaster`（自己的料号/名称），若其自带
`m_usageQty`/`m_scrap` 则优先使用，否则回退继承主件行的值。真实数据验证为独立
后续任务，验证结果如与本假设不符需回来调整实现，不阻塞 mock/脱敏先行。
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from zhuopin_platform.shared_tools.erp_connector.connector import ZpConnector


def _make_zp(tmp_path: Path) -> ZpConnector:
    return ZpConnector(
        base_url="https://mock.zp.test:4445", user_code="u", ent_code="001",
        org_code="Z", client_id="cid", client_secret="csec",
        fallback_dir=tmp_path, po_cache_file=tmp_path / "po.json",
    )


def _bom_master(components: list[dict]) -> dict:
    return {
        "m_bOMVersionCode": "A01",
        "m_effectiveDate": "2026-01-01T00:00:00",
        "m_disableDate": "2099-12-30T00:00:00",
        "m_bOMComponents": components,
    }


def _substitute(code: str, name: str = "", *, usage_qty: float | None = None,
                 scrap: float | None = None) -> dict:
    """替代料 DTO——按 design.md D2 假设，可能自带独立用量/损耗，也可能没有。"""
    d: dict = {"m_itemMaster": {"m_code": code, "m_name": name}}
    if usage_qty is not None:
        d["m_usageQty"] = usage_qty
    if scrap is not None:
        d["m_scrap"] = scrap
    return d


def _comp(code: str, name: str = "", *, qty: float = 1.0, scrap: float = 0.0,
          sequence: str = "10", component_type: int = 0,
          substitutes: list[dict] | None = None) -> dict:
    d = {
        "m_itemMaster": {"m_code": code, "m_name": name},
        "m_usageQty": qty, "m_scrap": scrap,
        "m_issueUOM": {"m_code": "PCS"},
        "m_sequence": sequence,
        "m_componentType": component_type,
    }
    if substitutes is not None:
        d["m_bOMCompSubstituteDTO4CreateSv"] = substitutes
    return d


def test_main_row_extracts_sequence_and_not_substitute(tmp_path, monkeypatch):
    """主件行（componentType=0）提取 sequence，is_substitute=False。"""
    zp = _make_zp(tmp_path)
    bom_data = [_bom_master([_comp("R001", sequence="10", component_type=0)])]
    monkeypatch.setattr(zp, "_u9c_bom_post", lambda body: bom_data)

    rows, failed = zp.get_bom_for_products(["PROD001"], today=date(2026, 7, 15))
    assert not failed
    assert len(rows) == 1
    assert rows[0].component_id == "R001"
    assert rows[0].sequence == "10"
    assert rows[0].is_substitute is False


def test_no_substitute_list_yields_only_main_row(tmp_path, monkeypatch):
    """无替代料列表（缺失/空）：只产出主件行，行为与本变更包实施前一致。"""
    zp = _make_zp(tmp_path)
    bom_data = [_bom_master([
        _comp("R001", sequence="10", substitutes=[]),
        _comp("R002", sequence="20"),  # 完全无该字段
    ])]
    monkeypatch.setattr(zp, "_u9c_bom_post", lambda body: bom_data)

    rows, failed = zp.get_bom_for_products(["PROD001"], today=date(2026, 7, 15))
    assert not failed
    assert [r.component_id for r in rows] == ["R001", "R002"]
    assert all(not r.is_substitute for r in rows)


def test_substitute_list_generates_paired_rows(tmp_path, monkeypatch):
    """主件行携带替代料列表：为每条替代料生成对等 BomRow，sequence 继承主件行、is_substitute=True。"""
    zp = _make_zp(tmp_path)
    bom_data = [_bom_master([
        _comp("R001", "主料", sequence="10", qty=2.0, scrap=0.05,
              substitutes=[_substitute("R002", "替代料一")]),
    ])]
    monkeypatch.setattr(zp, "_u9c_bom_post", lambda body: bom_data)

    rows, failed = zp.get_bom_for_products(["PROD001"], today=date(2026, 7, 15))
    assert not failed
    assert len(rows) == 2
    main, sub = rows[0], rows[1]
    assert main.component_id == "R001" and main.is_substitute is False
    assert sub.component_id == "R002" and sub.is_substitute is True
    assert sub.sequence == main.sequence == "10"
    # 替代料 DTO 未带独立用量/损耗时，回退继承主件行的值（design.md D2）
    assert sub.qty_per_unit == main.qty_per_unit == 2.0
    assert sub.loss_rate == main.loss_rate == 0.05


def test_substitute_with_own_usage_prefers_its_own_value(tmp_path, monkeypatch):
    """替代料 DTO 自带独立 m_usageQty/m_scrap 时，优先使用其自身值（不继承主件行）。"""
    zp = _make_zp(tmp_path)
    bom_data = [_bom_master([
        _comp("R001", sequence="10", qty=2.0, scrap=0.05,
              substitutes=[_substitute("R002", usage_qty=3.0, scrap=0.1)]),
    ])]
    monkeypatch.setattr(zp, "_u9c_bom_post", lambda body: bom_data)

    rows, failed = zp.get_bom_for_products(["PROD001"], today=date(2026, 7, 15))
    assert not failed
    sub = next(r for r in rows if r.is_substitute)
    assert sub.qty_per_unit == 3.0
    assert sub.loss_rate == 0.1


def test_multiple_substitutes_same_sequence(tmp_path, monkeypatch):
    """一个料位多条替代料：全部继承同一 sequence，均标 is_substitute=True。"""
    zp = _make_zp(tmp_path)
    bom_data = [_bom_master([
        _comp("R001", sequence="10", substitutes=[
            _substitute("R002"), _substitute("R003"),
        ]),
    ])]
    monkeypatch.setattr(zp, "_u9c_bom_post", lambda body: bom_data)

    rows, failed = zp.get_bom_for_products(["PROD001"], today=date(2026, 7, 15))
    assert not failed
    assert [r.component_id for r in rows] == ["R001", "R002", "R003"]
    assert all(r.sequence == "10" for r in rows)
    assert [r.is_substitute for r in rows] == [False, True, True]


def test_substitute_missing_item_code_skipped(tmp_path, monkeypatch):
    """替代料 DTO 缺料号（脏数据）：跳过该条，不因此整条主件行失败。"""
    zp = _make_zp(tmp_path)
    bom_data = [_bom_master([
        _comp("R001", sequence="10", substitutes=[
            {"m_itemMaster": {"m_code": "", "m_name": "坏数据"}},
            _substitute("R002"),
        ]),
    ])]
    monkeypatch.setattr(zp, "_u9c_bom_post", lambda body: bom_data)

    rows, failed = zp.get_bom_for_products(["PROD001"], today=date(2026, 7, 15))
    assert not failed
    assert [r.component_id for r in rows] == ["R001", "R002"]


def test_existing_callers_unaffected_by_new_fields(tmp_path, monkeypatch):
    """无 sequence/componentType/substitute 字段的旧式响应（O2/SC7 mock 结构）仍正常工作。"""
    zp = _make_zp(tmp_path)
    bom_data = [{
        "m_bOMVersionCode": "A01",
        "m_effectiveDate": "2026-01-01T00:00:00",
        "m_disableDate": "2099-12-30T00:00:00",
        "m_bOMComponents": [{
            "m_itemMaster": {"m_code": "R001", "m_name": "料"},
            "m_usageQty": 1.0, "m_scrap": 0.0,
            "m_issueUOM": {"m_code": "PCS"},
        }],
    }]
    monkeypatch.setattr(zp, "_u9c_bom_post", lambda body: bom_data)

    rows, failed = zp.get_bom_for_products(["PROD001"], today=date(2026, 7, 15))
    assert not failed
    assert rows[0].sequence == ""
    assert rows[0].is_substitute is False
