"""BOM/Query 返回体产品码自校验（跨桌任务队列 #66，姚祖怡 07-21 真实试用问题 1/6）。

背景：姚祖怡 07-21 报"S07Y.0137 显示瓶颈 R02A.0019，实为 S02Y.0035 的瓶颈料"/
"S02Y.0087 瓶颈 R03C.0210，ERP 无此料号"。07-22 CC 用真实 API 复验：3 轮并发批量
拉取（与生产 `_BOM_MAX_WORKERS=5` 同规模）未见任何 product_id↔component_id 串号，
`get_bom_for_products` 本身按 `code`（本地闭包变量）逐条打标、线程安全，代码层
未发现可复现的关联错位 bug；07-19~07-22 每小时刷新审计日志亦无中断/失败窗口
（fail-loud 设计下真出错会保留旧缓存，不会产出半错快照）。最可能解释：ERP 母件
BOM/预测订单状态在她观察与复验之间已变化（如 U9C BOM 版本被工程/PMC 编辑）。

但即便未能锁定当次根因，仍存在一个真实防御缺口：`BOM/Query` 响应体本身自带
`m_itemMaster.m_code`（母件自证码），代码此前完全不核对它与本次请求的 `code`
是否一致——如果服务端在任何未来时点（并发响应错位/缓存串号/未知 bug）返回了
错误母件的数据，我方会**静默信任**并把错误子件挂到错误成品上，正是姚描述的
症状。本测试覆盖新增自校验：响应自证码与请求码不符 → 视为该料号拉取失败
（不静默使用），而非放行。
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


def _comp(code: str, name: str = "", qty: float = 1.0, scrap: float = 0.0) -> dict:
    return {
        "m_itemMaster": {"m_code": code, "m_name": name},
        "m_usageQty": qty, "m_scrap": scrap,
        "m_issueUOM": {"m_code": "PCS"},
    }


def _bom_master(product_code: str, components: list[dict], *,
                version: str = "A01", effective: str = "2026-01-01",
                disable: str = "2099-12-30") -> dict:
    """真实响应结构：母件行自带 `m_itemMaster.m_code`（本次新增校验依据）。"""
    return {
        "m_itemMaster": {"m_code": product_code, "m_name": ""},
        "m_bOMVersionCode": version,
        "m_effectiveDate": f"{effective}T00:00:00",
        "m_disableDate": f"{disable}T00:00:00",
        "m_bOMComponents": components,
    }


def test_matching_product_code_passes_through(tmp_path, monkeypatch):
    """响应自证码与请求码一致（正常情况）：照常返回，不受影响。"""
    zp = _make_zp(tmp_path)
    bom_data = [_bom_master("PROD001", [_comp("R001")])]
    monkeypatch.setattr(zp, "_u9c_bom_post", lambda body: bom_data)

    rows, failed = zp.get_bom_for_products(["PROD001"], today=date(2026, 7, 22))
    assert not failed
    assert [r.component_id for r in rows] == ["R001"]
    assert [r.product_id for r in rows] == ["PROD001"]


def _requested_code(body: list) -> str:
    return body[0]["ItemMaster"]["Code"]


def test_mismatched_product_code_treated_as_failure(tmp_path, monkeypatch):
    """服务端对本次请求 `code=PROD001` 返回了另一母件（PROD999）的 BOM，PROD002 正常——
    响应自证码不符，必须视为该料号拉取失败（不静默采用错误数据），不牵连其他正常料号。"""
    zp = _make_zp(tmp_path)

    def fake_post(body):
        req = _requested_code(body)
        if req == "PROD001":
            return [_bom_master("PROD999", [_comp("R_WRONG_PRODUCT")])]   # 错配
        return [_bom_master(req, [_comp("R_OK")])]                        # 正常

    monkeypatch.setattr(zp, "_u9c_bom_post", fake_post)

    rows, failed = zp.get_bom_for_products(
        ["PROD001", "PROD002"], today=date(2026, 7, 22),
    )
    assert failed == ["PROD001"]
    assert all(r.component_id != "R_WRONG_PRODUCT" for r in rows)
    assert [r.component_id for r in rows] == ["R_OK"]
    assert [r.product_id for r in rows] == ["PROD002"]


def test_mismatch_writes_audit_trace(tmp_path, monkeypatch):
    """错配须留痕（IATF 可追溯 + 供未来批量核查是否复发），即便触发全失败 fail-loud 也不例外。"""
    sink = JsonlSink(tmp_path / "trace.jsonl")
    audit = ConnectorAudit(sink=sink)
    zp = _make_zp(tmp_path, audit=audit)
    bom_data = [_bom_master("PROD999", [_comp("R_WRONG")])]
    monkeypatch.setattr(zp, "_u9c_bom_post", lambda body: bom_data)

    with pytest.raises(RuntimeError):
        zp.get_bom_for_products(["PROD001"], today=date(2026, 7, 22))
    records = sink.read_all()
    assert any(r["action"] == "bom_product_code_mismatch" for r in records)


def test_missing_item_master_code_does_not_regress(tmp_path, monkeypatch):
    """响应体缺 `m_itemMaster.m_code`（未知边缘情况）：无法校验时不误伤，维持现状放行
    （避免因响应结构缺失字段导致大面积误判失败）。"""
    zp = _make_zp(tmp_path)
    bom_data = [{
        "m_itemMaster": {},   # 无 m_code
        "m_bOMVersionCode": "A01",
        "m_effectiveDate": "2026-01-01T00:00:00",
        "m_disableDate": "2099-12-30T00:00:00",
        "m_bOMComponents": [_comp("R001")],
    }]
    monkeypatch.setattr(zp, "_u9c_bom_post", lambda body: bom_data)

    rows, failed = zp.get_bom_for_products(["PROD001"], today=date(2026, 7, 22))
    assert not failed
    assert [r.component_id for r in rows] == ["R001"]


def test_multi_version_mismatch_checked_after_version_selection(tmp_path, monkeypatch):
    """多版本场景：先选出当前生效版本，再校验该版本自证码——校验不应绕过 B3 版本选择逻辑。
    PROD002 正常单版本作对照，确认错配不牵连其他料号（否则全失败会掩盖这一验证点）。"""
    zp = _make_zp(tmp_path)
    mismatched = [
        _bom_master("PROD999", [_comp("R_OLD_WRONG")],
                    version="A01", effective="2020-01-01", disable="2020-06-01"),
        _bom_master("PROD999", [_comp("R_NEW_WRONG")],
                    version="A02", effective="2020-06-02", disable="2099-12-30"),
    ]

    def fake_post(body):
        req = _requested_code(body)
        if req == "PROD001":
            return mismatched
        return [_bom_master(req, [_comp("R_OK")])]

    monkeypatch.setattr(zp, "_u9c_bom_post", fake_post)

    rows, failed = zp.get_bom_for_products(
        ["PROD001", "PROD002"], today=date(2026, 7, 22),
    )
    assert failed == ["PROD001"]
    assert all(r.component_id not in ("R_OLD_WRONG", "R_NEW_WRONG") for r in rows)
    assert [r.product_id for r in rows] == ["PROD002"]
