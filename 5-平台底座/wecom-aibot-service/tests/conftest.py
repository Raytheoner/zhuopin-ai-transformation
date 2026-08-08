"""测试全局守卫：禁止任何真实网络连接（与平台 zhuopin_platform/tests/conftest.py
同规则）。本服务的连接层测试一律走 `AibotConnector(client_factory=...)` 注入
假客户端，不应触真实 socket；此守卫用于在漏 mock 时快速报错，而非静默连真实
企微端点。回环地址放行——Windows `asyncio.run()` 走 `socket.socketpair()`
fallback 需要一次回环 connect 搭 self-pipe，与业务代码是否连了真实网络无关。
"""
# —— worktree 隔离引导（队列 #300）：把本 worktree 的平台底座与场景自身路径插到
# sys.path 最前，使 import 结果与全局 editable 安装当前指向谁无关。必须放在本文件
# 任何 zhuopin_platform / 场景包 import 之前。——
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
for _p in (_HERE, *_HERE.parents):
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        for _entry in (_p / "5-平台底座" / "zhuopin_platform", _HERE.parent.parent):
            if str(_entry) not in sys.path:
                sys.path.insert(0, str(_entry))
        break
else:
    raise RuntimeError(f"未找到仓库根标记 5-平台底座/zhuopin_platform（从 {_HERE} 向上查找）")

import socket

import pytest


class _NoNetworkError(RuntimeError):
    pass


def _is_loopback_addr(args) -> bool:
    if not args:
        return False
    target = args[0]
    host = target[0] if isinstance(target, tuple) else target
    return isinstance(host, str) and host in ("127.0.0.1", "::1", "localhost")


@pytest.fixture(autouse=True)
def _block_real_network(monkeypatch):
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def _blocked(self, *args, **kwargs):
        if _is_loopback_addr(args):
            return original_connect(self, *args, **kwargs)
        raise _NoNetworkError(
            "测试期间禁止真实网络连接：请用 AibotConnector(client_factory=fake) 注入假客户端。"
        )

    def _blocked_ex(self, *args, **kwargs):
        if _is_loopback_addr(args):
            return original_connect_ex(self, *args, **kwargs)
        raise _NoNetworkError(
            "测试期间禁止真实网络连接：请用 AibotConnector(client_factory=fake) 注入假客户端。"
        )

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked_ex)
