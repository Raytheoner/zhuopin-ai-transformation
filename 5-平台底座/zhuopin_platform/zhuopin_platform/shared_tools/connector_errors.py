"""连接器标准异常（P2 加固）。

所有平台连接器边界校验失败 / 限流超限，统一使用此模块的异常类型，
确保 AIOps 可按类型捕获并路由告警，不再用裸 RuntimeError/ValueError。
"""
from __future__ import annotations


class ConnectorValidationError(ValueError):
    """连接器 Pydantic 边界校验失败。

    在连接器入口/出口处捕获 pydantic.ValidationError 后转换为此类型，
    保证脏数据在边界被拦截，不漏入下游预测引擎。

    Attributes:
        source: 数据源标识（"SRM" / "zp_ERP"）
        field:  首个校验失败的字段名
        raw:    原始响应行 dict（用于 debug，不含敏感数据）
    """

    def __init__(self, source: str, field: str, raw: dict | None = None) -> None:
        self.source = source
        self.field = field
        self.raw = raw or {}
        super().__init__(f"{source} validation error: field={field}")


class RateLimitError(RuntimeError):
    """连接器限流退避耗尽后抛出（SRM 900301 连续 3 次）。

    调用方（场景层 pipeline）应捕获此异常并告警，不得静默丢失。
    """

    def __init__(self, source: str = "SRM", attempts: int = 3) -> None:
        self.source = source
        self.attempts = attempts
        super().__init__(f"{source} rate limit exceeded after {attempts} retries")
