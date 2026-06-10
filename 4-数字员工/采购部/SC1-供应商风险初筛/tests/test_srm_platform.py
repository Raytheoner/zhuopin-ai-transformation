"""
test_srm_platform.py — 验证 SRM 连接器切底座后的行为等价性。

D1=A：只改 SRMProvider._get_connector() 内部，接口层不变。
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.data_providers import DataProvider, ManualProvider, SRMProvider, get_delivery_data, DeliveryData


class TestManualProviderEquivalence:
    """ManualProvider 接口行为等价（切换前后无变化）。"""

    def test_with_rate_returns_delivery_data(self):
        provider = ManualProvider(delivery_rate=92.0)
        data = provider.get_delivery_rate("任意供应商")
        assert data.rate == 92.0
        assert data.source == "人工录入"

    def test_none_rate_returns_data_insufficient(self):
        provider = ManualProvider(delivery_rate=None)
        data = provider.get_delivery_rate("任意供应商")
        assert data.rate is None
        assert data.source == "数据不足"

    def test_custom_source(self):
        provider = ManualProvider(delivery_rate=85.0, source="人工覆盖")
        data = provider.get_delivery_rate("供应商X")
        assert data.source == "人工覆盖"

    def test_implements_data_provider_interface(self):
        assert issubclass(ManualProvider, DataProvider)


class TestGetDeliveryDataFallbackEquivalence:
    """get_delivery_data() 回退行为等价。"""

    def test_override_bypasses_srm(self):
        data = get_delivery_data("供应商X", override_rate=88.5)
        assert data.rate == 88.5
        assert data.source == "人工覆盖"

    def test_srm_unavailable_falls_back_to_insufficient(self):
        with patch.object(SRMProvider, '_get_connector', side_effect=RuntimeError("SRM 不可用")):
            data = get_delivery_data("供应商X")
        assert data.rate is None
        assert data.source == "数据不足"

    def test_custom_override_source(self):
        data = get_delivery_data("X", override_rate=90.0, override_source="ERP覆盖")
        assert data.source == "ERP覆盖"


class TestSRMProviderWithMockConnector:
    """SRMProvider 使用注入 connector 的行为验证。"""

    def _make_mock_orders(self, supplier_code: str, total: int, delivered: int):
        orders = []
        for i in range(total):
            o = MagicMock()
            o.supplier_id = supplier_code
            o.status = "delivered" if i < delivered else "pending"
            orders.append(o)
        return orders

    def test_connector_called_returns_delivery_rate(self):
        mock_connector = MagicMock()
        mock_connector.get_delivery_orders.return_value = self._make_mock_orders("S001", 4, 4)
        provider = SRMProvider(connector=mock_connector)
        data = provider.get_delivery_rate("X", supplier_code="S001")
        assert data.rate == 100.0
        assert data.source == "SRM自动"

    def test_partial_delivery_calculates_rate(self):
        mock_connector = MagicMock()
        mock_connector.get_delivery_orders.return_value = self._make_mock_orders("S002", 10, 9)
        provider = SRMProvider(connector=mock_connector)
        data = provider.get_delivery_rate("X", supplier_code="S002")
        assert data.rate == 90.0

    def test_no_orders_raises_runtime_error(self):
        mock_connector = MagicMock()
        mock_connector.get_delivery_orders.return_value = []
        provider = SRMProvider(connector=mock_connector)
        with pytest.raises(RuntimeError, match="未找到供应商"):
            provider.get_delivery_rate("未知供应商", supplier_code="S999")


class TestNoSysPathResidue:
    """data_providers.py 不含 sys.path 操作或跨工程引用（grep 验证）。"""

    def test_no_sys_path_in_data_providers(self):
        src_path = Path(__file__).parent.parent / "src" / "data_providers.py"
        content = src_path.read_text(encoding="utf-8")
        assert "sys.path" not in content, "data_providers.py 仍包含 sys.path 操作"

    def test_no_supplychain_reference_in_data_providers(self):
        src_path = Path(__file__).parent.parent / "src" / "data_providers.py"
        content = src_path.read_text(encoding="utf-8")
        assert "supplychain" not in content, "data_providers.py 仍包含跨工程引用"
