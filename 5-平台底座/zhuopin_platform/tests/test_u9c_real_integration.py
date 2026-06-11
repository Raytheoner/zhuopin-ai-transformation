"""U9C 外网真实集成测试（任务 4.2，BOM via /U9C/webapi/BOM/Query）。

默认跳过：仅 `U9C_RUN_REAL=1` 且凭据就位（.env 注入）才运行。CI / 普通 pytest 不触网。
本轮范围仅 BOM（外网只开 AuthLogin + BOM/Query；CommonEntity/Query 外网 404）。
"""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("U9C_RUN_REAL") != "1",
    reason="U9C 真实集成：置 U9C_RUN_REAL=1 且凭据就位才运行",
)


def test_real_oauth_and_bom():
    """OAuth2 鉴权 + /U9C/webapi/BOM/Query 拉真实直接子件，BomRow schema 正确。"""
    from zhuopin_platform.shared_tools.erp_connector import ZpConnector

    zp = ZpConnector.from_env()
    token = zp._get_token()
    assert token and len(token) > 100            # JWT

    # 真实母件（外网已验证）；取直接子件
    bom = zp.get_bom_for_products(["S02Y.0162"], max_depth=1)
    assert bom, "应拉到真实 BOM 直接子件"
    for r in bom:
        assert r.product_id and r.component_id
        assert r.level == 1
