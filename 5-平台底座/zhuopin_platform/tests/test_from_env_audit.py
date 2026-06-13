"""连接器 from_env 审计强制化（B4 / 审计报告 §2.4 P1 · 先写测试）。

生产构造路径未注入 audit → UserWarning（不留痕的显式告警）；注入则不告警。
"""
from __future__ import annotations

import warnings

import pytest

from zhuopin_platform.shared_tools.connector_audit import ConnectorAudit
from zhuopin_platform.shared_tools.erp_connector.connector import ZpConnector
from zhuopin_platform.shared_tools.srm_connector.connector import XkySrmConnector


@pytest.fixture
def _zp_env(monkeypatch):
    for k, v in {
        "U9C_API_BASE": "https://mock:4443", "U9C_USER_CODE": "u",
        "U9C_ENT_CODE": "e", "U9C_ORG_CODE": "o",
        "U9C_CLIENT_ID": "cid", "U9C_CLIENT_SECRET": "csec",
    }.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("U9C_TLS_INSECURE", raising=False)


@pytest.fixture
def _srm_env(monkeypatch):
    for k, v in {
        "XKY_APP_KEY": "k", "XKY_APP_SECRET": "s",
        "XKY_OWNER_COMPANY_CODE": "ZP", "XKY_ERP_CODE": "ZP",
    }.items():
        monkeypatch.setenv(k, v)


def test_zp_from_env_warns_without_audit(_zp_env):
    with pytest.warns(UserWarning, match="未注入 audit"):
        ZpConnector.from_env()


def test_zp_from_env_no_warn_with_audit(_zp_env, tmp_path):
    from zhuopin_platform.audit.sinks import JsonlSink
    with warnings.catch_warnings():
        warnings.simplefilter("error")           # 有 audit 时不应有任何 UserWarning
        ZpConnector.from_env(audit=ConnectorAudit(sink=JsonlSink(tmp_path / "t.jsonl")))


def test_srm_from_env_warns_without_audit(_srm_env):
    with pytest.warns(UserWarning, match="未注入 audit"):
        XkySrmConnector.from_env()


def test_srm_from_env_no_warn_with_audit(_srm_env, tmp_path):
    from zhuopin_platform.audit.sinks import JsonlSink
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        XkySrmConnector.from_env(audit=ConnectorAudit(sink=JsonlSink(tmp_path / "t.jsonl")))
