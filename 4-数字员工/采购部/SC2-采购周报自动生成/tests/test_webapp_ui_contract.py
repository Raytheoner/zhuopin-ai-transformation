"""Mock display contract: no ERP, report generation, review or audit writes."""
from datetime import date
from html.parser import HTMLParser

import pytest

from sc2.models import Metric, MetricValue, WeeklyReport
from sc2 import webapp


class Text(HTMLParser):
    def __init__(self, document):
        super().__init__()
        self.parts = []
        self.feed(document)

    def handle_data(self, data):
        self.parts.append(data)

    def __str__(self):
        return " ".join(self.parts)


def report(**kwargs):
    fields = dict(period="2026-W40", base_date=date(2026, 10, 9), mode="mock",
                  fetched_at="2026-10-08T18:12:00+08:00",
                  source_notes={"mock": "构造资料，非真实周报"}, metrics=(),
                  window_text={"current": "2026-09-28~2026-10-04",
                               "previous": "2026-09-21~2026-09-27",
                               "month_ago": "2026-08-31~2026-09-06"})
    fields.update(kwargs)
    return WeeklyReport(**fields)


def render(value, **kwargs):
    return webapp._render_page(value, detail_links="", backlog="", **kwargs)


def test_source_time_and_missing_metadata_are_not_filled_with_today():
    text = str(Text(render(report())))
    assert "2026-10-08T18:12:00+08:00" in text
    assert "构造资料，非真实周报" in text
    missing = str(Text(render(report(period="", fetched_at="", source_notes={}))))
    assert "未提供" in missing
    assert "2026-W40" not in missing
    assert "暂无周报记录" in missing


def test_zero_missing_values_and_caveats_remain_distinct():
    metric = Metric(key="order_count", name="订单数量", group="下单",
                    current=MetricValue(0, "条", "口径尚未签认"),
                    previous=MetricValue(None, "条"), month_ago=MetricValue(4, "条"))
    text = str(Text(render(report(metrics=(metric,)))))
    assert "0条" in text
    assert "资料不足" in text
    assert "口径待核" in text
    assert "口径尚未签认" in text


def test_long_source_text_is_escaped_and_pure_render_does_no_io(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("pure display performed I/O")
    for name in ("build_feed", "save_snapshot", "load_snapshot", "confirm",
                 "_detail_links_html", "_backlog_text"):
        monkeypatch.setattr(webapp, name, forbidden)
    name = "长供应商名称" * 30 + "<script>alert(1)</script>"
    page = render(report(source_notes={"供应商": name}))
    assert name in str(Text(page))
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


def test_read_failure_is_503_and_does_not_show_valid_report(monkeypatch, tmp_path):
    monkeypatch.setenv("ZP_GATE_PASSWORD", "")
    monkeypatch.setattr(webapp.config, "access_log_path", lambda: None)
    def unavailable(*args, **kwargs):
        raise TimeoutError("mock timeout")
    monkeypatch.setattr(webapp, "load_snapshot", unavailable)
    monkeypatch.setattr(webapp, "build_feed", lambda *a: pytest.fail("unexpected source read"))
    response = webapp.create_app(base_date=date(2026, 10, 9)).test_client().get("/procurement/sc2/")
    assert response.status_code == 503
    text = str(Text(response.get_data(as_text=True)))
    assert "当次结果不可用" in text
    assert "确认发布" not in text
    assert '卓品智能 · 采购门户 · SC2' in text
    assert '#f5f8fc' in response.get_data(as_text=True)
    assert '<form' not in response.get_data(as_text=True)


def test_existing_actions_keep_prefix_and_human_review():
    page = render(report())
    assert 'action="/procurement/sc2/api/confirm"' in page
    assert 'name="confirmed_by" required' in page
    assert "事后复核" in str(Text(page))


def test_review_button_does_not_claim_to_publish_and_schedule_is_unverified():
    page = render(report())
    buttons = __import__('re').findall(r'<button[^>]*>(.*?)</button>', page, __import__('re').S)
    assert buttons == ['记录事后复核']
    text = str(Text(page))
    assert '定时推送运行状态未核验' in text
    assert '每周五 20:00 自动生成并自动推送' not in text


def test_old_source_time_is_age_unclassified_without_new_threshold():
    page = render(report(fetched_at='2020-01-01T00:00:00+08:00'))
    text = str(Text(page))
    assert '2020-01-01T00:00:00+08:00' in text
    assert '数据时效' in text and '年龄未分类' in text
    assert '陈旧判据未提供' in text
