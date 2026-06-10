"""SRM 令牌桶限流退避测试（P2 加固 · 先写测试）。"""
import datetime
import pytest
from unittest.mock import MagicMock, patch, call

from zhuopin_platform.shared_tools.connector_errors import RateLimitError
from zhuopin_platform.shared_tools.srm_connector.connector import XkySrmConnector, _TokenBucket


def _make_connector() -> XkySrmConnector:
    return XkySrmConnector(
        api_base="https://mock.xky.test",
        app_key="k", app_secret="s",
        owner_company_code="OC", erp_code="EC",
    )


class TestTokenBucket:

    def test_first_consume_passes_immediately(self):
        """首次消耗令牌立即通过，无等待。"""
        bucket = _TokenBucket(rate=1/30, capacity=1)
        # 第一次消耗不应 sleep
        with patch("time.sleep") as mock_sleep:
            bucket.consume()
        mock_sleep.assert_not_called()

    def test_second_consume_waits(self):
        """30s 内第二次消耗时会计算出需等待的时长 > 0。"""
        bucket = _TokenBucket(rate=1/30, capacity=1)
        bucket.consume()  # 耗尽令牌

        sleep_args: list[float] = []

        def _fake_sleep(t: float) -> None:
            sleep_args.append(t)
            # 模拟时间流逝：补充令牌，让循环退出
            bucket._tokens = 1.0

        with patch("time.sleep", side_effect=_fake_sleep):
            bucket.consume()

        assert len(sleep_args) == 1
        assert sleep_args[0] > 0

    def test_multiple_instances_share_bucket(self):
        """同 endpoint 的两个 XkySrmConnector 实例共享令牌桶（类变量）。"""
        XkySrmConnector._buckets.clear()

        conn1 = _make_connector()
        conn2 = _make_connector()

        path = "/purchase/answer.json"
        conn1._get_bucket(path).consume()  # conn1 耗尽桶

        sleep_args: list[float] = []

        def _fake_sleep(t: float) -> None:
            sleep_args.append(t)
            conn2._get_bucket(path)._tokens = 1.0  # 补充令牌

        with patch("time.sleep", side_effect=_fake_sleep):
            conn2._get_bucket(path).consume()

        assert len(sleep_args) == 1  # 确认等待了一次


class TestSrmRateLimitingIntegration:

    def setup_method(self):
        """每个测试前清空类级令牌桶，避免残留。"""
        XkySrmConnector._buckets.clear()

    def test_900301_triggers_backoff_retry(self):
        """SRM 返回 900301 时触发退避重试。"""
        conn = _make_connector()
        call_count = {"n": 0}

        def _fake_urlopen(req, timeout=15):
            call_count["n"] += 1
            if call_count["n"] < 3:
                # 前两次返回 900301
                resp = MagicMock()
                resp.read.return_value = b'{"errorCode":"900301","errorMsg":"rate limit"}'
                resp.__enter__ = lambda s: s
                resp.__exit__ = MagicMock(return_value=False)
                return resp
            else:
                # 第三次返回成功
                resp = MagicMock()
                resp.read.return_value = b'{"errorCode":"0","data":{"lineList":[]}}'
                resp.__enter__ = lambda s: s
                resp.__exit__ = MagicMock(return_value=False)
                return resp

        with patch("urllib.request.urlopen", side_effect=_fake_urlopen), \
             patch("time.sleep"):
            result = conn._post("/purchase/answer.json", {"poErpNo": "PO001"})
        assert call_count["n"] == 3  # 调用了 3 次

    def test_three_900301_raises_rate_limit_error(self):
        """连续三次 900301 后抛 RateLimitError。"""
        conn = _make_connector()

        def _always_900301(req, timeout=15):
            resp = MagicMock()
            resp.read.return_value = b'{"errorCode":"900301","errorMsg":"rate limit"}'
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            return resp

        with patch("urllib.request.urlopen", side_effect=_always_900301), \
             patch("time.sleep"):
            with pytest.raises(RateLimitError):
                conn._post("/purchase/answer.json", {"poErpNo": "PO001"})

    def test_get_receive_board_span_over_60_days_raises(self):
        """查询跨度超过 60 天时抛 ValueError，不发 HTTP 请求。"""
        conn = _make_connector()
        start = "2026-01-01"
        end = "2026-03-15"   # 73 天

        with patch("urllib.request.urlopen") as mock_http:
            with pytest.raises(ValueError, match="60"):
                conn.get_receive_board(start_date=start, end_date=end)
        mock_http.assert_not_called()

    def test_get_receive_board_span_exactly_60_days_passes(self):
        """查询跨度恰好 60 天时不抛 ValueError。"""
        conn = _make_connector()
        start = datetime.date(2026, 1, 1)
        end = start + datetime.timedelta(days=60)

        success_resp = MagicMock()
        success_resp.read.return_value = b'{"errorCode":"0","dataList":[]}'
        success_resp.__enter__ = lambda s: s
        success_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=success_resp), \
             patch("time.sleep"):
            result = conn.get_receive_board(
                start_date=start.isoformat(),
                end_date=end.isoformat(),
            )
        assert isinstance(result, list)
