"""测试全局守卫：禁止任何真实网络连接（合规红线"先 mock 后真实"）。

收割阶段全程使用 mock/夹具，绝不触真实 SRM/ERP/U9C/企微端点。本守卫拦截一切
出站 socket 连接——若某测试漏 mock 而尝试真实连接，立即失败而非静默打真实库。

例外：回环地址（127.0.0.1 / ::1）放行。Windows 上 `asyncio.run()`
（`ProactorEventLoop`/`SelectorEventLoop` 均如此）会经 `socket.socketpair()`
的 fallback 实现内部 connect 一个回环 socket 搭"self-pipe"用于事件循环唤醒
——这是 Python 自身的事件循环管线，不是业务代码在打真实网络，放行不削弱本
守卫拦截真实 SRM/ERP/U9C/企微出站请求的原意（wecom_aibot 连接器测试需要）。
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
            "测试期间禁止真实网络连接：请 mock urlopen/_post/_zp_post 等。"
            "（收割阶段不连真实 SRM/ERP/U9C/企微）"
        )

    def _blocked_ex(self, *args, **kwargs):
        if _is_loopback_addr(args):
            return original_connect_ex(self, *args, **kwargs)
        raise _NoNetworkError(
            "测试期间禁止真实网络连接：请 mock urlopen/_post/_zp_post 等。"
            "（收割阶段不连真实 SRM/ERP/U9C/企微）"
        )

    # 拦截底层 socket 连接（回环例外）；mock 过的 urlopen 不会走到这里
    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked_ex)
