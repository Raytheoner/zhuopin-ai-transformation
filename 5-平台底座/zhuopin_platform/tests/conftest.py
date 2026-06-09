"""测试全局守卫：禁止任何真实网络连接（合规红线"先 mock 后真实"）。

收割阶段全程使用 mock/夹具，绝不触真实 SRM/ERP/U9C/企微端点。本守卫拦截一切
出站 socket 连接——若某测试漏 mock 而尝试真实连接，立即失败而非静默打真实库。
"""
import socket

import pytest


class _NoNetworkError(RuntimeError):
    pass


@pytest.fixture(autouse=True)
def _block_real_network(monkeypatch):
    def _blocked(*args, **kwargs):
        raise _NoNetworkError(
            "测试期间禁止真实网络连接：请 mock urlopen/_post/_zp_post 等。"
            "（收割阶段不连真实 SRM/ERP/U9C/企微）"
        )
    # 拦截底层 socket 连接；mock 过的 urlopen 不会走到这里
    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
