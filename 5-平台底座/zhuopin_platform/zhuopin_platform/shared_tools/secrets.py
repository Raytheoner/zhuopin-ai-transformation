"""凭证抽象层（P2 加固 · 切库红线④）。

提供 SecretsProvider Protocol（`get(key) -> str`）和 EnvSecretsProvider（.env 实现）。
未来接 Vault / K8s Secrets 时只需新增实现类，连接器代码不变。
"""
from __future__ import annotations

import os
from typing import Protocol, runtime_checkable


@runtime_checkable
class SecretsProvider(Protocol):
    """凭证提供者接口。

    实现者：`get(key)` 返回对应凭证字符串；key 不存在时 MUST 抛 `KeyError`。
    """

    def get(self, key: str) -> str: ...


class EnvSecretsProvider:
    """从 os.environ 读取凭证（Phase 1 默认实现）。

    Args:
        override: 可选的覆盖字典（优先于 os.environ），主要用于测试注入假凭证。
    """

    def __init__(self, override: dict[str, str] | None = None) -> None:
        self._override = override or {}

    def get(self, key: str) -> str:
        if key in self._override:
            return self._override[key]
        val = os.environ.get(key)
        if val is None:
            raise KeyError(key)
        return val
