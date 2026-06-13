"""ZpConnector TLS 证书校验（A1 / 审计报告 §2.4 P0 · 先写测试）。

覆盖：
  - 默认实例开启证书+主机名校验（CERT_REQUIRED / check_hostname）；
  - U9C_TLS_INSECURE=1（mock）→ 关闭校验 + UserWarning + audit 留 TLS_INSECURE 痕迹；
  - real 模式 + U9C_TLS_INSECURE=1 → InsecureTLSError（对客权威路径禁裸信道）。
"""
from __future__ import annotations

import ssl

import pytest

from zhuopin_platform.shared_tools.connector_audit import ConnectorAudit
from zhuopin_platform.shared_tools.connector_errors import InsecureTLSError
from zhuopin_platform.shared_tools.erp_connector.connector import ZpConnector


class _CapturingSink:
    """捕获 ConnectorAudit.trace 写入的访问痕迹（验证 TLS_INSECURE 留痕）。"""

    def __init__(self) -> None:
        self.records: list = []

    def write(self, event) -> None:
        self.records.append(event)


def _make(data_source: str = "mock", audit: ConnectorAudit | None = None) -> ZpConnector:
    return ZpConnector(
        base_url="https://erp.example.com:4443",
        user_code="u", ent_code="e", org_code="o",
        client_id="cid", client_secret="csecret",
        data_source=data_source, audit=audit,
    )


def test_default_context_verifies_cert(monkeypatch):
    """未设逃生开关 → 证书+主机名校验开启。"""
    monkeypatch.delenv("U9C_TLS_INSECURE", raising=False)
    conn = _make()
    assert conn._ctx.verify_mode == ssl.CERT_REQUIRED
    assert conn._ctx.check_hostname is True


def test_insecure_escape_hatch_warns_and_traces(monkeypatch):
    """U9C_TLS_INSECURE=1（mock）→ 关闭校验 + UserWarning + audit 留痕。"""
    monkeypatch.setenv("U9C_TLS_INSECURE", "1")
    sink = _CapturingSink()
    audit = ConnectorAudit(sink)
    with pytest.warns(UserWarning, match="TLS 证书校验已关闭"):
        conn = _make(data_source="mock", audit=audit)
    assert conn._ctx.verify_mode == ssl.CERT_NONE
    assert conn._ctx.check_hostname is False
    assert any(getattr(r, "source", "") == "TLS_INSECURE" for r in sink.records)


def test_real_mode_rejects_insecure(monkeypatch):
    """real 模式 + 逃生开关 → InsecureTLSError（强制证书校验）。"""
    monkeypatch.setenv("U9C_TLS_INSECURE", "1")
    with pytest.raises(InsecureTLSError):
        _make(data_source="real")
