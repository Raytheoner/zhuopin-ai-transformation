"""白名单反向代理（design.md 决策1/2/3，spec portal-gateway-routing）。

路由表是显式白名单（域/场景 → 后端 base URL），不是通用透明代理——只转发到
已知的内部服务，从设计上排除"代理请求被诱导访问非预期内网地址"这一类
SSRF 风险（design.md 决策1）。

本次试点（design.md 决策3）路由表只有一条：`/` → 门户首页（命令中心，8092），
`domain="portal"`、`required_tier=PUBLIC_READ`（门户首页面向全体企微成员）。
未来收编 8091/8093/8094（决策件线③）时按同一结构追加条目，`webapp.py`/
鉴权链路均无需改动。
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import requests

from portal_gateway.permissions import PermissionTier

# 转发时不透传的请求头（逐跳头 + Host + 由 requests 自行按 body 重算的头）。
_HOP_BY_HOP_HEADERS = {
    "host", "connection", "content-length", "transfer-encoding",
    "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "upgrade", "cookie",
}


@dataclass(frozen=True)
class Route:
    prefix: str                              # URL 前缀，"/" 为全量兜底
    backend_base_url: str                    # 如 "http://127.0.0.1:8092"
    domain: str                              # 权限判定用域名（"portal"=公开门户本体）
    required_tier: PermissionTier
    backend_gate_password_env: str | None = None  # 该后端仍启用 simple_gate 时的口令环境变量名（决策6）


def default_route_table() -> list[Route]:
    """本次交付的路由表——仅门户首页（8092）一条（design.md 决策3）。"""
    backend = os.environ.get("PORTAL_GATEWAY_HOME_BACKEND", "http://127.0.0.1:8092")
    return [
        Route(prefix="/", backend_base_url=backend, domain="portal",
              required_tier=PermissionTier.PUBLIC_READ,
              backend_gate_password_env="ZP_GATE_PASSWORD"),
    ]


def match_route(routes: list[Route], path: str) -> Route | None:
    """最长前缀匹配；"/" 视为兜底（匹配一切）。"""
    best: Route | None = None
    best_len = -1
    for route in routes:
        prefix = route.prefix
        matches = path == prefix or (prefix != "/" and path.startswith(prefix.rstrip("/") + "/"))
        if prefix == "/":
            matches = True
        if matches and len(prefix) > best_len:
            best, best_len = route, len(prefix)
    return best


def build_forward_headers(original_headers: dict[str, str], *, backend_gate_password: str | None) -> dict[str, str]:
    """过滤逐跳头，按需注入 X-Auth-Token（决策6：代理仍启用 simple_gate 的后端时避免双重拦截）。"""
    headers = {k: v for k, v in original_headers.items() if k.lower() not in _HOP_BY_HOP_HEADERS}
    if backend_gate_password:
        headers["X-Auth-Token"] = backend_gate_password
    return headers


def resolve_backend_gate_password(route: Route) -> str | None:
    if not route.backend_gate_password_env:
        return None
    value = (os.environ.get(route.backend_gate_password_env) or "").strip()
    return value or None


def forward_request(route: Route, remainder_path: str, *, method: str, headers: dict[str, str],
                     query_string: str = "", data: bytes | None = None,
                     timeout: int = 30):
    """把请求转发到 `route.backend_base_url + remainder_path`，流式返回响应。

    `remainder_path` 须以 "/" 开头（调用方负责拼接，本函数不做路径规范化猜测）。
    `query_string` 原样透传（不经二次编码），避免重复值/特殊字符参数在
    dict 化过程中失真。
    """
    url = route.backend_base_url.rstrip("/") + remainder_path
    if query_string:
        url = f"{url}?{query_string}"
    forward_headers = build_forward_headers(headers, backend_gate_password=resolve_backend_gate_password(route))
    return requests.request(
        method, url, headers=forward_headers, data=data,
        stream=True, timeout=timeout, allow_redirects=False,
    )
