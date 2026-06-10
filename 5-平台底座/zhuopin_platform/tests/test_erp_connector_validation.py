"""ERP 连接器 Pydantic 边界校验测试（P2 加固 · 先写测试）。"""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from zhuopin_platform.shared_tools.connector_errors import ConnectorValidationError
from zhuopin_platform.shared_tools.erp_connector.connector import ZpConnector


def _make_zp(tmp_path: Path) -> ZpConnector:
    return ZpConnector(
        base_url="https://mock.zp.test:4445",
        user_code="u", ent_code="001", org_code="Z",
        client_id="cid", client_secret="csec",
        fallback_dir=tmp_path,
        po_cache_file=tmp_path / "po_cache.json",
    )


class TestZpPurOrderValidation:

    def test_po_row_missing_item_code_raises(self, tmp_path):
        """PO 行 itemCode 为 None 时抛 ConnectorValidationError。"""
        zp = _make_zp(tmp_path)
        rows = [{"erpNo": "PO001", "itemCode": None, "qty": 10,
                 "rcvQtyTU": 0, "makeDate": "2099-01-01", "supplyCode": "S01"}]
        with patch.object(zp, "_zp_post", return_value=rows):
            with pytest.raises(ConnectorValidationError) as exc_info:
                zp.get_purchase_orders()
            assert exc_info.value.source == "zp_ERP"
            assert "itemCode" in exc_info.value.field

    def test_po_row_valid_passes(self, tmp_path):
        """格式正确的 PO 行正常产生 PurchaseOrder。"""
        zp = _make_zp(tmp_path)
        rows = [{"erpNo": "PO001", "itemCode": "MAT001", "qty": "10",
                 "rcvQtyTU": "0", "makeDate": "2099-01-01", "supplyCode": "S01"}]
        with patch.object(zp, "_zp_post", return_value=rows):
            pos = zp.get_purchase_orders()
            assert len(pos) == 1
            assert pos[0].material_id == "MAT001"

    def test_validation_error_has_raw_context(self, tmp_path):
        """ConnectorValidationError 的 raw 属性含原始行 dict。"""
        zp = _make_zp(tmp_path)
        # makeDate 必须足够近才能过 cutoff 过滤，然后才到 Pydantic 校验
        bad_row = {"erpNo": "PO001", "itemCode": None, "makeDate": "2099-01-01"}
        with patch.object(zp, "_zp_post", return_value=[bad_row]):
            with pytest.raises(ConnectorValidationError) as exc_info:
                zp.get_purchase_orders()
            assert exc_info.value.raw == bad_row


class TestU9cBomComponentValidation:

    def test_bom_component_valid_passes(self, tmp_path):
        """格式正确的 BOM component 行正常产生 BomRow。"""
        zp = _make_zp(tmp_path)
        bom_data = [{
            "m_bOMComponents": [{
                "m_itemMaster": {"m_code": "COMP001", "m_name": "电容"},
                "m_issueUOM": {"m_code": "PCS"},
                "m_usageQty": 2,
                "m_scrap": 0,
            }]
        }]
        with patch.object(zp, "_u9c_bom_post", return_value=bom_data):
            rows = zp.get_bom_for_products(["PROD001"])
            assert len(rows) == 1
            assert rows[0].component_id == "COMP001"

    def test_bom_component_missing_code_skipped(self, tmp_path):
        """child_code 为空的 BOM component 跳过（不产生行），不抛异常。"""
        zp = _make_zp(tmp_path)
        bom_data = [{
            "m_bOMComponents": [{
                "m_itemMaster": {"m_code": "", "m_name": "无码件"},
                "m_issueUOM": {},
                "m_usageQty": 1,
                "m_scrap": 0,
            }]
        }]
        with patch.object(zp, "_u9c_bom_post", return_value=bom_data):
            rows = zp.get_bom_for_products(["PROD001"])
            assert rows == []
