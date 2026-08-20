"""物料看板路由（/materials 与 /api/materials，队列 #334）—— Flask test_client，全 mock。

覆盖 tasks 5.5：两个路由 200、空态不报错、匿名访问被现有门禁拦截（不新起端口 ⇒
与既有页面同受同一门禁），以及页面确实把三列取数缺口与窗口口径写在脸上（D7）。
"""
from __future__ import annotations

from sc8 import webapp
from sc8.baoguan_service import Snapshot, SnapshotStore
from sc8.case_store import CaseStore
from sc8.material_board import FIELD_GAP


def _snap():
    return Snapshot(
        generated_at="2026-08-20T10:00:00", today="2026-08-20", rows=[],
        counts={"red": 0, "gap": 0, "yel": 0, "grn": 0}, ok=True,
        materials=[{"id": "R01B.0105", "name": "RPK-50V471MI5D#Q-F52", "brand": FIELD_GAP,
                    "st": "transit_confirmed", "sts": ["transit_confirmed"], "tq": 4000.0,
                    "m": [100.0, 300.0, 500.0], "total": 900.0, "out": 0.0,
                    "cb": [{"d": "2026-09-20", "q": 900.0}],
                    "sup": ["上海森和创电气有限公司"], "owner": FIELD_GAP,
                    "buyers": ["尤胤栋"], "hasSub": False, "nrow": 3}],
        materials_meta={"months": [{"ym": "2026-08", "label": "8月"},
                                   {"ym": "2026-09", "label": "9月"},
                                   {"ym": "2026-10", "label": "10月"}],
                        "window": "2026-08 ~ 2026-10",
                        "out_of_window_materials": 2, "out_of_window_qty": 50.0})


def _client(snap=None):
    store = SnapshotStore(None)
    if snap is not None:
        store.set(snap)
    app = webapp.create_app(snapshot_store=store, case_store=CaseStore(":memory:"),
                            audit=None, ops_webhook_url=None)
    app.config.update(TESTING=True)
    return app.test_client()


def test_materials_page_200():
    r = _client(_snap()).get("/materials")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "物料看板" in body


def test_materials_api_returns_rows_and_meta():
    j = _client(_snap()).get("/api/materials").get_json()
    assert j["ok"] is True and len(j["rows"]) == 1
    assert j["rows"][0]["id"] == "R01B.0105"
    assert j["meta"]["window"] == "2026-08 ~ 2026-10"
    assert j["today"] == "2026-08-20"


def test_materials_api_empty_state_is_not_an_error():
    j = _client().get("/api/materials").get_json()
    assert j["ok"] is False and j["rows"] == [] and j["meta"] == {}


def test_materials_page_empty_state_still_200():
    assert _client().get("/materials").status_code == 200


def test_page_states_the_three_data_gaps_and_the_window_rule():
    """D7：取数缺口与口径差异一律写在页面上，否则打开会以为是 bug。"""
    body = _client(_snap()).get("/materials").get_data(as_text=True)
    for phrase in ("品牌", "责任人", "取数缺口", "缺料视图", "不是全量物料台账",
                   "窗口之外", "累计口径", "齐料日期口径正在与采购部确认中"):
        assert phrase in body, phrase


def test_page_never_uses_buyer_to_fill_the_owner_column():
    """制单人已被真实数据证伪 ⇒ 不得出现在页面上冒充「责任人」。"""
    body = _client(_snap()).get("/materials").get_data(as_text=True)
    assert "尤胤栋" not in body       # buyers 只在 JSON 载荷里，页面不渲染它


def test_nav_links_to_materials_from_dashboard():
    body = _client(_snap()).get("/").get_data(as_text=True)
    assert 'href="/materials"' in body


def test_anonymous_access_is_blocked_by_the_existing_gate(monkeypatch):
    """不新起端口 ⇒ 与既有页面同受同一门禁；门禁只在配了口令时才装（见 simple_gate）。"""
    monkeypatch.setenv("ZP_GATE_PASSWORD", "s3cret")
    c = _client(_snap())
    page = c.get("/materials")
    assert page.status_code == 302 and "/_gate/login" in page.headers["Location"]
    api = c.get("/api/materials")
    assert api.status_code == 302
    assert c.get("/api/ping").status_code == 200      # 健康检查仍豁免


def test_authorized_access_passes_the_gate(monkeypatch):
    monkeypatch.setenv("ZP_GATE_PASSWORD", "s3cret")
    c = _client(_snap())
    assert c.get("/materials", headers={"X-Auth-Token": "s3cret"}).status_code == 200


def test_empty_supplier_is_not_shown_as_a_data_gap():
    """🔴 供应商为空 ≠ 取数缺口：那是「该物料当前没有未交采购订单」这个**准确答案**。

    生产实测 596 行里 100 行 `sup` 为空，与状态列 `no_transit`(82)+`confirmed_no_transit`(18)
    逐个对上——两者同义。若沿用品牌/责任人那套「取数缺口」措辞，就是把「查不到」和
    「确实没有」混为一谈（#296 那族缺陷的老路）。
    """
    body = _client(_snap()).get("/materials").get_data(as_text=True)
    assert "'无未交订单'" in body            # 供应商列空值的措辞
    # 品牌/责任人仍是取数缺口态，两者措辞必须不同
    assert FIELD_GAP in body
