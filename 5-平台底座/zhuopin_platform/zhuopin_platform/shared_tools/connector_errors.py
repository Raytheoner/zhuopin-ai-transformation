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


class RealEndpointNotReadyError(RuntimeError):
    """`U9C_DATA_SOURCE=real` 下调用了无真实端点的方法（fail-loud，绝不静默回退 mock）。

    合规红线（Paul 拍板 Q3）：静默 mock 混进 real 决策是合规+正确性双重风险（SC8 对客尤忌）。
    过渡期如需回退，调用方必须**显式 opt-in**（`allow_mock_fallback`），且结果标非权威、
    禁入对客/L2 决策路径。

    Attributes:
        method: 触发的方法名（如 "get_production_plan"）
        reason: 为何无真实端点（如 "zp 无生产计划端点，待 U9C MO CommonEntity 外网开放"）
    """

    def __init__(self, method: str, reason: str = "") -> None:
        self.method = method
        self.reason = reason
        msg = f"真实端点未就绪：{method}（U9C_DATA_SOURCE=real）"
        if reason:
            msg += f" —— {reason}"
        super().__init__(msg)
