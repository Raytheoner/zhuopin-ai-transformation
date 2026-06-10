"""SRM 连接器 Pydantic 边界校验测试（P2 加固 · 先写测试）。"""
import pytest
from unittest.mock import MagicMock, patch

from zhuopin_platform.shared_tools.connector_errors import ConnectorValidationError
from zhuopin_platform.shared_tools.srm_connector.connector import XkySrmConnector


def _make_connector() -> XkySrmConnector:
    return XkySrmConnector(
        api_base="https://mock.xky.test",
        app_key="k", app_secret="s",
        owner_company_code="OC", erp_code="EC",
    )


class TestSrmAnswerLineValidation:

    def test_missing_v_expected_date_field_raises(self):
        """lineList 行缺少 vExpectedDate 仍应正常（None 返回），不崩溃。"""
        conn = _make_connector()
        raw_resp = {
            "errorCode": "0",
            "data": {"lineList": [{}]}   # 无 vExpectedDate
        }
        with patch.object(conn, "_post", return_value=raw_resp):
            result = conn.get_confirmed_date("PO001", "V001")
            assert result is None  # 无交期字段 → None，不抛

    def test_invalid_timestamp_type_raises_validation_error(self):
        """lineList 行 vExpectedDate 类型非法时抛 ConnectorValidationError。"""
        conn = _make_connector()
        raw_resp = {
            "errorCode": "0",
            "data": {"lineList": [{"vExpectedDate": "NOT_A_NUMBER"}]}
        }
        with patch.object(conn, "_post", return_value=raw_resp):
            with pytest.raises(ConnectorValidationError) as exc_info:
                conn.get_confirmed_date("PO001", "V001")
            assert exc_info.value.source == "SRM"
            assert "vExpectedDate" in exc_info.value.field

    def test_valid_response_returns_date_string(self):
        """有效时间戳正常转为日期字符串。"""
        conn = _make_connector()
        raw_resp = {
            "errorCode": "0",
            "data": {"lineList": [{"vExpectedDate": 1750000000}]}
        }
        with patch.object(conn, "_post", return_value=raw_resp):
            result = conn.get_confirmed_date("PO001", "V001")
            assert result is not None
            assert len(result) == 10  # YYYY-MM-DD

    def test_error_message_contains_source_and_field(self):
        """ConnectorValidationError 异常消息含 source 和 field。"""
        conn = _make_connector()
        raw_resp = {
            "errorCode": "0",
            "data": {"lineList": [{"vExpectedDate": "bad"}]}
        }
        with patch.object(conn, "_post", return_value=raw_resp):
            with pytest.raises(ConnectorValidationError) as exc_info:
                conn.get_confirmed_date("PO001", "V001")
            msg = str(exc_info.value)
            assert "SRM" in msg
            assert "vExpectedDate" in msg


class TestSrmItemRowValidation:

    def test_item_row_missing_board_date_handled(self):
        """itemList 行 boardDate 缺失时用降级处理（空字符串），不崩溃。"""
        conn = _make_connector()
        raw_resp = {
            "errorCode": "0",
            "data": {
                "dataList": [{
                    "productCode": "MAT001",
                    "itemList": [{"answerQty": 10}]   # 无 boardDate
                }]
            }
        }
        with patch.object(conn, "get_receive_board", return_value=raw_resp.get("data", {}).get("dataList", [])):
            orders = conn.get_delivery_orders()
            # boardDate 为空字符串，订单仍产生
            assert isinstance(orders, list)

    def test_item_row_valid_answer_qty(self):
        """answerQty > 0 的有效行正常产生 SrmDeliveryOrder。"""
        conn = _make_connector()
        board_data = [{
            "productCode": "MAT001",
            "innerVendorCode": "V001",
            "itemList": [{
                "answerQty": 5,
                "deliveriedQty": 0,
                "boardDate": "1750000000",
                "scheduleBatch": "BATCH001",
            }]
        }]
        with patch.object(conn, "get_receive_board", return_value=board_data):
            orders = conn.get_delivery_orders()
            assert len(orders) == 1
            assert orders[0].material_id == "MAT001"
