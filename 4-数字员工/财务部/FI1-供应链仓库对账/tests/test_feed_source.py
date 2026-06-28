"""数据接入层单测（spec: fi1-feed-source）。"""
from __future__ import annotations

import pytest

from zhuopin_platform.shared_tools.connector_errors import RealEndpointNotReadyError
from zhuopin_platform.shared_tools.models import BomRow

from fi1.feed_source import FeedSource, parse_feeds, parse_outputs


def test_mock_loads_outputs_feeds_bom(mock_dir):
    fs = FeedSource("mock", mock_dir=mock_dir)
    outs = fs.load_outputs()
    feeds = fs.load_feeds()
    bom, failed = fs.load_bom(["F001", "F002"])
    assert {o.product_id for o in outs} == {"F001", "F002"}
    assert {f.component_id for f in feeds} == {"C001", "C002"}
    assert failed == []
    assert {r.component_id for r in bom} == {"C001", "C002"}


def test_csv_bridge_loads_real_interim(tmp_path):
    (tmp_path / "outputs.csv").write_text(
        "product_id,product_name,finished_qty,period\nP1,成品,100,2026-08\n", encoding="utf-8")
    (tmp_path / "feeds.csv").write_text(
        "component_id,component_name,actual_qty,unit,period\nC1,件,200,PCS,2026-08\n", encoding="utf-8")
    fs = FeedSource("csv", csv_dir=tmp_path)
    assert fs.load_outputs()[0].finished_qty == 100
    assert fs.load_feeds()[0].actual_qty == 200


def test_u9c_fail_loud_outputs():
    fs = FeedSource("u9c")
    with pytest.raises(RealEndpointNotReadyError):
        fs.load_outputs()


def test_u9c_fail_loud_feeds():
    fs = FeedSource("u9c")
    with pytest.raises(RealEndpointNotReadyError):
        fs.load_feeds()


def test_dirty_output_row_rejected():
    with pytest.raises(ValueError):
        parse_outputs([{"product_id": "", "finished_qty": 10}])      # 缺料号
    with pytest.raises(ValueError):
        parse_outputs([{"product_id": "P1", "finished_qty": ""}])    # 缺数量


def test_dirty_feed_row_rejected():
    with pytest.raises(ValueError):
        parse_feeds([{"component_id": "", "actual_qty": 10}])
    with pytest.raises(ValueError):
        parse_feeds([{"component_id": "C1", "actual_qty": "abc"}])   # 类型非法


def test_bom_connector_injection_consumes_failed_ids():
    class _FakeZp:
        def get_bom_for_products(self, ids, max_depth=1):
            return ([BomRow("F001", "C1", "件", 1, 2, 0.05, "PCS")], ["F999"])
    fs = FeedSource("csv", bom_connector=_FakeZp())
    rows, failed = fs.load_bom(["F001", "F999"])
    assert failed == ["F999"]
    assert rows[0].component_id == "C1"
