"""`scripts/alert_webhook.py` 凭据来源单测（队列 #282 ⑴ 包，变更包
`sweep-ops-webhook-cutover` 决策点 4a）。

背景：这条"第三道防线"从建成起就没活过——它读 `5-平台底座/.env` 的裸
`WECOM_WEBHOOK_URL`，而该文件里这个键的值长度为 0（两份副本口径一致），
故退避耗尽时只会打印"未配置"并 `exit 1`。本批把凭据来源改为**仓库根 `.env`**
的 `WECOM_WEBHOOK_URL_OPS`（运维逃生通道，已真实验通）。

⚠️ 本批只做代码修正：真实触发条件是"企微服务三级重启退避耗尽"，属天然罕见
事件、无法按需构造；且在 §四 `#68` 生产载体同步前不在生产生效。故本文件覆盖的
是**取值语义**，不是端到端投递。
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from unittest import mock

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "alert_webhook.py"

_spec = importlib.util.spec_from_file_location("alert_webhook", _SCRIPT)
alert_webhook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(alert_webhook)

OPS_KEY = "WECOM_WEBHOOK_URL_OPS"
BARE_KEY = "WECOM_WEBHOOK_URL"


@pytest.fixture
def clean_env():
    """把两个同族键从进程环境里摘干净并在退出时精确还原。

    必须用 `patch.dict`：`load_dotenv` 直接写 `os.environ`，pytest 的
    `monkeypatch.setenv` 撤不掉它写进去的键。
    """
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop(OPS_KEY, None)
        os.environ.pop(BARE_KEY, None)
        yield


def _write_env(root: Path, *lines: str) -> None:
    (root / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_常量指向运维逃生通道而非业务群():
    assert alert_webhook.OPS_WEBHOOK_ENV_KEY == OPS_KEY, (
        "本脚本的告警主题是『企微服务自己挂了』＝机制自陈，按通知通道架构决策件 §4.2 "
        "须发运维群；改回裸键即把服务故障告警发进业务部门群（#282 拍板明禁）"
    )


def test_只有运维键时正常取到(tmp_path, clean_env):
    _write_env(tmp_path, f"{OPS_KEY}=https://qyapi.example.com/ops")
    assert alert_webhook.resolve_alert_webhook(tmp_path) == "https://qyapi.example.com/ops"


def test_只有裸键时返回None且绝不回退(tmp_path, clean_env):
    """本项最硬的一条：裸键指向采购内部工作群，静默回退＝把服务故障告警发错人。"""
    _write_env(tmp_path, f"{BARE_KEY}=https://qyapi.example.com/business")
    assert alert_webhook.resolve_alert_webhook(tmp_path) is None


def test_两者并存时只取运维键(tmp_path, clean_env):
    _write_env(
        tmp_path,
        f"{BARE_KEY}=https://qyapi.example.com/business",
        f"{OPS_KEY}=https://qyapi.example.com/ops",
    )
    assert alert_webhook.resolve_alert_webhook(tmp_path) == "https://qyapi.example.com/ops"


def test_互为前缀的两键不跨行误命中(tmp_path, clean_env):
    """`WECOM_WEBHOOK_URL` 是 `WECOM_WEBHOOK_URL_OPS` 的真前缀。此处把裸键放在
    **后**一行：顺序颠倒时仍必须各取各的，不因前缀关系读到业务群那一行。"""
    _write_env(
        tmp_path,
        f"{OPS_KEY}=https://qyapi.example.com/ops",
        f"{BARE_KEY}=https://qyapi.example.com/business",
    )
    assert alert_webhook.resolve_alert_webhook(tmp_path) == "https://qyapi.example.com/ops"


def test_运维键为空值视同未配置(tmp_path, clean_env):
    _write_env(tmp_path, f"{OPS_KEY}=", f"{BARE_KEY}=https://qyapi.example.com/business")
    assert alert_webhook.resolve_alert_webhook(tmp_path) is None


def test_env文件缺失时返回None(tmp_path, clean_env):
    assert alert_webhook.resolve_alert_webhook(tmp_path) is None


def test_find_repo_root定位到含平台底座的那一层(tmp_path):
    (tmp_path / "5-平台底座" / "zhuopin_platform").mkdir(parents=True)
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    assert alert_webhook.find_repo_root(deep / "x.py") == tmp_path


def test_find_repo_root找不到标记时返回None(tmp_path):
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)
    assert alert_webhook.find_repo_root(deep / "x.py") is None
