"""一次性连接自检：读 `.env` → `aibot_subscribe` → 报告认证成功/失败 → 断开。

不做任何收发测试（echo 见后续真实群联调 tasks.md §7），只验证 BotID/Secret
有效、当前机器能完成 WSS 握手 + 认证。**绝不打印凭据本身**，只报告布尔结果。

用法：python scripts/check_connection.py [--timeout 15]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

SERVICE_DIR = Path(__file__).resolve().parent.parent

# —— 平台底座路径引导（队列 #345 收拢；唯一被允许的样板，实现见
# `5-平台底座/zhuopin_platform/zhuopin_platform/bootstrap.py`）。必须放在本文件任何
# zhuopin_platform / 场景包 import 之前。下方五行只负责让 bootstrap 自身可被 import、
# 不含任何判断分支；开发机 monorepo 与 `.51` 扁平部署两种布局的分歧由 ensure_paths 处理。——
_HERE = Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        sys.path.insert(0, str(_p / "5-平台底座" / "zhuopin_platform"))
        break
from zhuopin_platform.bootstrap import ensure_paths  # noqa: E402
ensure_paths(__file__, SERVICE_DIR)  # noqa: E402

from zhuopin_platform.shared_tools.notifiers.wecom_aibot import AibotConnector  # noqa: E402
from zhuopin_platform.shared_tools.secrets import EnvSecretsProvider  # noqa: E402

from aibot_service.connection import BOTID_KEY, SECRET_KEY  # noqa: E402


async def _check(timeout: float) -> bool:
    load_dotenv(SERVICE_DIR.parent / ".env")
    secrets = EnvSecretsProvider()
    try:
        bot_id = secrets.get(BOTID_KEY)
        secret = secrets.get(SECRET_KEY)
    except KeyError as exc:
        print(f"[FAIL] 凭据缺失：{exc}（检查 5-平台底座/.env 是否有 {BOTID_KEY}/{SECRET_KEY}）")
        return False

    result: dict = {"authenticated": False, "error": None}
    done = asyncio.Event()

    def on_authenticated() -> None:
        result["authenticated"] = True
        done.set()

    def on_error(err: Exception) -> None:
        result["error"] = str(err)
        done.set()

    def on_disconnected(reason: str) -> None:
        if not result["authenticated"] and not done.is_set():
            result["error"] = f"连接断开（未认证）：{reason}"
            done.set()

    connector = AibotConnector(
        bot_id,
        secret,
        max_reconnect_attempts=0,  # 自检只测一次，不重连
        on_authenticated=on_authenticated,
        on_error=on_error,
        on_disconnected=on_disconnected,
    )

    await connector.connect()
    try:
        await asyncio.wait_for(done.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        print(f"[FAIL] 超时（{timeout}s）未收到认证成功/失败信号")
        connector.disconnect()
        return False

    connector.disconnect()
    if result["authenticated"]:
        print("[OK] aibot_subscribe 订阅认证成功 —— BotID/Secret 有效，WSS 长连接可用。")
        return True
    print(f"[FAIL] 认证未成功：{result['error']}")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="企微智能机器人连接自检（仅订阅，不收发）")
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()

    ok = asyncio.run(_check(args.timeout))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
