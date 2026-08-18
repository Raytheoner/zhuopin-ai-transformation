"""B 段验收（tasks.md §7.1）：测试群 echo——收到消息原样回，不接两个业务场景。

同时打印完整原始 WsFrame（json），用于核实 `frame_parsing.py` 里未经验证的
字段路径假设（发送人/chatid 实际取值），真实联调后按观察结果修正该文件。

用法：python scripts/echo_test.py [--duration 300]
"""
from __future__ import annotations

import argparse
import asyncio
import json
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
from aibot_service.frame_parsing import parse_inbound_frame  # noqa: E402


def _guess_chatid(frame: dict) -> str | None:
    body = frame.get("body", {}) or {}
    if body.get("chatid"):
        return body["chatid"]
    from_field = body.get("from")
    if isinstance(from_field, dict):
        return from_field.get("userid")
    return from_field or None


async def run(duration: float) -> None:
    load_dotenv(SERVICE_DIR.parent / ".env")
    secrets = EnvSecretsProvider()
    bot_id = secrets.get(BOTID_KEY)
    secret = secrets.get(SECRET_KEY)

    connector_holder: dict = {}

    async def on_message(frame: dict) -> None:
        print("[RAW FRAME] " + json.dumps(frame, ensure_ascii=False))
        msg = parse_inbound_frame(frame)
        print(f"[PARSED] sender={msg.sender!r} msgtype={msg.msgtype!r}")

        chatid = _guess_chatid(frame)
        if msg.msgtype == "text" and chatid:
            reply = f"echo: {msg.text_content}"
            try:
                await connector_holder["connector"].send_markdown(chatid, reply)
                print(f"[SENT] echo 回复已发往 chatid={chatid!r}")
            except Exception as exc:  # noqa: BLE001
                print(f"[SEND FAILED] chatid={chatid!r} error={exc}")
        else:
            print(f"[SKIP] 非文本消息或未取到 chatid（chatid={chatid!r}），仅记录不回复")

    connector = AibotConnector(
        bot_id,
        secret,
        max_reconnect_attempts=3,
        on_connected=lambda: print("[EVT] connected"),
        on_authenticated=lambda: print("[EVT] authenticated —— 已就绪，等待测试群 @消息"),
        on_disconnected=lambda r: print(f"[EVT] disconnected: {r}"),
        on_reconnecting=lambda n: print(f"[EVT] reconnecting attempt {n}"),
        on_error=lambda e: print(f"[EVT] error: {e}"),
        on_message=on_message,
    )
    connector_holder["connector"] = connector

    await connector.connect()
    print(f"[INFO] 监听中，最长 {duration:.0f} 秒（Ctrl+C 可提前结束）...")
    try:
        await asyncio.wait_for(asyncio.Event().wait(), timeout=duration)
    except asyncio.TimeoutError:
        print("[INFO] 达到最长监听时长，结束。")
    connector.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description="企微智能机器人 echo 测试（B 段验收，不接业务）")
    parser.add_argument("--duration", type=float, default=300.0)
    args = parser.parse_args()
    asyncio.run(run(args.duration))


if __name__ == "__main__":
    main()
