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

# —— worktree 隔离引导（队列 #300／#313 补漏）：把本 worktree 的平台底座与本服务
# 自身路径插到 sys.path 最前，使 import 结果与全局 editable 安装当前指向谁无关。
# 必须放在下方任何 zhuopin_platform / aibot_service import 之前。——
_HERE = Path(__file__).resolve()
for _p in (_HERE, *_HERE.parents):
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        for _entry in (_p / "5-平台底座" / "zhuopin_platform", SERVICE_DIR):
            if str(_entry) not in sys.path:
                sys.path.insert(0, str(_entry))
        break
else:
    # 🔴 找不到仓库根标记时**不得硬失败**（2026-08-18 实测事故，队列 #345）：#300 要防的是
    # "N 个平等 worktree 共用一套全局 site-packages、谁装的 editable 指针谁说了算"——
    # **该前提只在开发机成立**。`.51` 的部署布局是扁平的 `C:/<svc>/app` ＋
    # `C:/<svc>/zhuopin_platform`（后者已由 deploy 脚本 pip install -e 进 venv，全机唯一
    # 一份、无歧义），**没有也不需要 `5-平台底座/` 这层目录**。原实现在此直接 raise，等于
    # 把入口在生产布局上钉死（现象：计划任务 LastResult=0 但进程秒退、端口无监听）。
    # ⇒ 找到标记 → 按 #300 前插（开发机，确定性优先）；找不到 → 只插自身包路径、平台底座
    # 交由环境解析（生产机，唯一一份）。**不引入静默失败**：环境里也没有 zhuopin_platform
    # 时仍然明确报错。——
    if str(SERVICE_DIR) not in sys.path:
        sys.path.insert(0, str(SERVICE_DIR))
    from importlib.util import find_spec
    if find_spec("zhuopin_platform") is None:
        raise RuntimeError(
            f"既未找到仓库根标记 5-平台底座/zhuopin_platform（从 {_HERE} 向上查找），"
            "环境中也没有可导入的 zhuopin_platform——请检查部署或安装平台底座包")

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
