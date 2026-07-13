"""BOM 生效日期区间过滤（B3，shortage-baoguan-criteria-v3，2026-07-10 会议定稿）。

背景：`get_bom_for_products` 现状对 U9C `BOM/Query` 返回的多条 BOM 主记录
无条件取第一条（`bom_data[0]`），生产环境实测确认部分母件多版本时第一条
是已失效的旧版本。本测试覆盖：单版本不变 / 多版本取当前生效 / 全部不生效
fail-safe 回退，均 mock `_u9c_bom_post`，不触网。
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from zhuopin_platform.audit.sinks import JsonlSink
from zhuopin_platform.shared_tools.connector_audit import ConnectorAudit
from zhuopin_platform.shared_tools.erp_connector.connector import ZpConnector


def _make_zp(tmp_path: Path, audit: ConnectorAudit | None = None) -> ZpConnector:
    return ZpConnector(
        base_url="https://mock.zp.test:4445", user_code="u", ent_code="001",
        org_code="Z", client_id="cid", client_secret="csec",
        fallback_dir=tmp_path, po_cache_file=tmp_path / "po.json", audit=audit,
    )


def _bom_master(version: str, effective: str, disable: str, components: list[dict]) -> dict:
    return {
        "m_bOMVersionCode": version,
        "m_effectiveDate": f"{effective}T00:00:00",
        "m_disableDate": f"{disable}T00:00:00",
        "m_bOMComponents": components,
    }


def _comp(code: str, name: str = "", qty: float = 1.0, scrap: float = 0.0) -> dict:
    return {
        "m_itemMaster": {"m_code": code, "m_name": name},
        "m_usageQty": qty, "m_scrap": scrap,
        "m_issueUOM": {"m_code": "PCS"},
    }


def test_single_version_unchanged(tmp_path, monkeypatch):
    """单一版本母件：只有一条 BOM 主记录，行为与改造前一致。"""
    zp = _make_zp(tmp_path)
    bom_data = [_bom_master("A01", "2026-01-01", "2099-12-30", [_comp("R001")])]
    monkeypatch.setattr(zp, "_u9c_bom_post", lambda body: bom_data)

    rows, failed = zp.get_bom_for_products(["PROD001"], today=date(2026, 7, 10))
    assert not failed
    assert [r.component_id for r in rows] == ["R001"]


def test_multi_version_picks_currently_effective(tmp_path, monkeypatch):
    """多版本：真实抓到的 S02Y.0162 结构——第一条(索引0)是已失效的旧版本，
    第二条才是当前生效版本；改造前会错误取到第一条(R_OLD)。"""
    zp = _make_zp(tmp_path)
    bom_data = [
        _bom_master("A01", "2026-01-27", "2026-02-04", [_comp("R_OLD")]),   # 已失效
        _bom_master("A02", "2026-02-05", "2099-12-30", [_comp("R_NEW")]),   # 当前生效
    ]
    monkeypatch.setattr(zp, "_u9c_bom_post", lambda body: bom_data)

    rows, failed = zp.get_bom_for_products(["PROD001"], today=date(2026, 7, 10))
    assert not failed
    assert [r.component_id for r in rows] == ["R_NEW"], "必须取当前生效版本，不能无条件取第一条"


def test_multi_version_order_independent(tmp_path, monkeypatch):
    """即便返回顺序反过来（当前生效版本在前），结果仍应一致——验证不是靠位置取巧。"""
    zp = _make_zp(tmp_path)
    bom_data = [
        _bom_master("A02", "2026-02-05", "2099-12-30", [_comp("R_NEW")]),   # 当前生效，排第一
        _bom_master("A01", "2026-01-27", "2026-02-04", [_comp("R_OLD")]),   # 已失效，排第二
    ]
    monkeypatch.setattr(zp, "_u9c_bom_post", lambda body: bom_data)

    rows, failed = zp.get_bom_for_products(["PROD001"], today=date(2026, 7, 10))
    assert not failed
    assert [r.component_id for r in rows] == ["R_NEW"]


def test_no_version_matches_falls_back_to_latest_disable_date(tmp_path, monkeypatch):
    """全部版本都不满足生效区间（数据异常/版本空档期）→ fail-safe 回退取失效日期最晚的一条。"""
    zp = _make_zp(tmp_path)
    sink = JsonlSink(tmp_path / "trace.jsonl")
    audit = ConnectorAudit(sink=sink)
    zp2 = _make_zp(tmp_path, audit=audit)
    bom_data = [
        _bom_master("A01", "2020-01-01", "2020-06-01", [_comp("R_OLDEST")]),
        _bom_master("A02", "2020-06-02", "2020-12-01", [_comp("R_OLD")]),
    ]
    monkeypatch.setattr(zp2, "_u9c_bom_post", lambda body: bom_data)

    rows, failed = zp2.get_bom_for_products(["PROD001"], today=date(2026, 7, 10))
    assert not failed
    assert [r.component_id for r in rows] == ["R_OLD"], "回退取 m_disableDate 最大的一条"
    records = sink.read_all()
    assert any(r["action"] == "bom_version_fallback" for r in records), \
        "fail-safe 触发时应写 audit 留痕"


def test_real_world_multi_version_samples(tmp_path, monkeypatch):
    """用本 session 生产环境实测抓到的真实多版本结构核对（S04Y.0112，4 版本）。"""
    zp = _make_zp(tmp_path)
    bom_data = [
        _bom_master("A01", "2026-01-04", "2026-01-12", [_comp("R_V1")]),
        _bom_master("A02", "2026-01-13", "2026-02-11", [_comp("R_V2")]),
        _bom_master("A03", "2026-02-12", "2026-03-26", [_comp("R_V3")]),
        _bom_master("A04", "2026-03-27", "2099-12-30", [_comp("R_V4")]),
    ]
    monkeypatch.setattr(zp, "_u9c_bom_post", lambda body: bom_data)

    rows, failed = zp.get_bom_for_products(["PROD001"], today=date(2026, 7, 10))
    assert not failed
    assert [r.component_id for r in rows] == ["R_V4"], "2026-07-10 应落在 A04 区间(3/27~至今)内"
