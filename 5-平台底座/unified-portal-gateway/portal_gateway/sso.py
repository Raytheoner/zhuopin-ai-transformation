"""企微 OAuth2 SSO + 会话签发（design.md 决策 4，队列 #162）。

三条登录路径，均落到同一份会话签发逻辑（`make_session_cookie_value`）：

1. **真实企微 OAuth2 网页授权**（生产目标态）——`build_wecom_authorize_url` /
   `exchange_code_for_userid`。需要 `CorpID`/`AgentID`/`Secret`（企微自建应用，
   与现有智能机器人 BotID 体系是两套独立注册，见 design.md Open Question①）。
   **本次 apply 时凭据尚未到位**（Shao Peishen 2026-08-04 拍板：先 mock，凭据
   走队列 #240 另行申请），故本模块的真实 OAuth 路径已按官方文档实现但未经
   真实凭据验证——一旦 `.env` 配上 `WECOM_GATEWAY_CORP_ID`/`WECOM_GATEWAY_AGENT_ID`/
   `WECOM_GATEWAY_SECRET`，`webapp.py` 会自动切换到真实路径，无需改代码。

2. **开发/试点 mock 登录**——`PORTAL_GATEWAY_MOCK_LOGIN=1` 时启用，任意
   userid 直接签发会话，**不做任何身份核验**。⚠️ 仅供开发/试点期打通"登录→
   权限判定→访问日志"全链路使用，**绝不能在有敏感数据的路由前打开**；本次
   试点路由（门户首页/8092）本就零敏感数据，风险可接受，真实 OAuth 凭据到位
   后须显式关闭本开关（见 design.md Risks）。

3. **应急本地口令通道**——`PORTAL_GATEWAY_EMERGENCY_PASSWORD` 配置后启用，
   仅 Shao Peishen 与运维知悉；口令核验通过后签发固定身份
   （`PORTAL_GATEWAY_EMERGENCY_USERID`，默认 `ShaoPeiShen`）的会话，
   **不允许调用方自报任意身份**（否则退化成 mock 登录的等价物，丧失"应急"
   本应具备的最小信任面）。企微 OAuth 服务不可用时使用。

会话 Cookie（`zp_portal_sso`）签名机制沿用 `simple_gate.py` 的 HMAC-SHA256
+ 无服务端存储范式，但载荷多带一个 userid 字段——两者是独立 Cookie，本模块
不读写 `zp_gate`。
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from dataclasses import dataclass
from urllib.parse import quote, urlencode

import requests

COOKIE_NAME = "zp_portal_sso"
DEFAULT_COOKIE_DAYS = 30

WECOM_AUTHORIZE_BASE = "https://open.weixin.qq.com/connect/oauth2/authorize"
WECOM_GETTOKEN_URL = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
WECOM_GETUSERINFO_URL = "https://qyapi.weixin.qq.com/cgi-bin/user/getuserinfo"

_REQUEST_TIMEOUT = 5


# ── 会话 Cookie：HMAC 签名，无服务端存储（design.md 决策4） ────────────────


def _sign(secret: str, payload: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def make_session_cookie_value(secret: str, userid: str, *, days: int = DEFAULT_COOKIE_DAYS,
                               now: int | None = None) -> str:
    """签发会话 Cookie 值：`{userid}.{过期时间戳}.{签名}`。"""
    if not userid:
        raise ValueError("userid 不得为空")
    exp_ts = (now if now is not None else int(time.time())) + days * 86400
    payload = f"{userid}.{exp_ts}"
    return f"{payload}.{_sign(secret, payload)}"


def verify_session_cookie_value(secret: str, value: str | None, *, now: int | None = None) -> str | None:
    """校验会话 Cookie：签名匹配且未过期则返回 userid，否则返回 None（fail-closed）。"""
    if not value or value.count(".") != 2:
        return None
    userid, exp_str, sig = value.split(".")
    if not userid:
        return None
    try:
        exp_ts = int(exp_str)
    except ValueError:
        return None
    current = now if now is not None else int(time.time())
    if exp_ts < current:
        return None
    payload = f"{userid}.{exp_ts}"
    expected = _sign(secret, payload)
    if not hmac.compare_digest(sig, expected):
        return None
    return userid


# ── 真实企微 OAuth2 网页授权（未经真实凭据验证，见模块顶部说明） ──────────


@dataclass(frozen=True)
class WecomOAuthConfig:
    corp_id: str
    agent_id: str
    secret: str


def load_wecom_oauth_config() -> WecomOAuthConfig | None:
    """从环境变量读取企微 OAuth 凭据；任一缺失即视为未配置（返回 None）。"""
    corp_id = (os.environ.get("WECOM_GATEWAY_CORP_ID") or "").strip()
    agent_id = (os.environ.get("WECOM_GATEWAY_AGENT_ID") or "").strip()
    secret = (os.environ.get("WECOM_GATEWAY_SECRET") or "").strip()
    if not (corp_id and agent_id and secret):
        return None
    return WecomOAuthConfig(corp_id=corp_id, agent_id=agent_id, secret=secret)


def build_wecom_authorize_url(*, corp_id: str, agent_id: str, redirect_uri: str, state: str) -> str:
    """构造企微网页授权跳转 URL（`snsapi_base`，静默授权，无需用户确认）。"""
    params = {
        "appid": corp_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "snsapi_base",
        "state": state,
        "agentid": agent_id,
    }
    return f"{WECOM_AUTHORIZE_BASE}?{urlencode(params, quote_via=quote)}#wechat_redirect"


def _get_access_token(corp_id: str, secret: str) -> str | None:
    try:
        resp = requests.get(WECOM_GETTOKEN_URL, params={"corpid": corp_id, "corpsecret": secret},
                             timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None
    if data.get("errcode", 0) != 0:
        return None
    return data.get("access_token")


def _get_userid_from_code(access_token: str, code: str) -> str | None:
    try:
        resp = requests.get(WECOM_GETUSERINFO_URL, params={"access_token": access_token, "code": code},
                             timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None
    if data.get("errcode", 0) != 0:
        return None
    # 内部成员返回 UserId；外部联系人/游客返回 OpenId/DeviceId——本门户只服务
    # 内部员工，UserId 缺失一律视为不可用身份（fail-closed，不误接受外部访客）。
    return data.get("UserId") or None


def exchange_code_for_userid(config: WecomOAuthConfig, code: str) -> str | None:
    """完整 OAuth2 换取流程：code → access_token → userid。任一步失败返回 None。"""
    token = _get_access_token(config.corp_id, config.secret)
    if not token:
        return None
    return _get_userid_from_code(token, code)


# ── mock 登录（开发/试点期，见模块顶部红线说明） ────────────────────────


def mock_login_enabled() -> bool:
    return (os.environ.get("PORTAL_GATEWAY_MOCK_LOGIN") or "").strip() not in ("", "0", "false", "False")


# ── 应急本地口令通道 ─────────────────────────────────────────────────


DEFAULT_EMERGENCY_USERID = "ShaoPeiShen"


def emergency_login_enabled() -> bool:
    return bool((os.environ.get("PORTAL_GATEWAY_EMERGENCY_PASSWORD") or "").strip())


def emergency_userid() -> str:
    return (os.environ.get("PORTAL_GATEWAY_EMERGENCY_USERID") or "").strip() or DEFAULT_EMERGENCY_USERID


def verify_emergency_password(password: str | None) -> bool:
    """核验应急口令；未配置该通道时恒返回 False（fail-closed）。"""
    secret = (os.environ.get("PORTAL_GATEWAY_EMERGENCY_PASSWORD") or "").strip()
    if not secret or not password:
        return False
    return hmac.compare_digest(password, secret)
