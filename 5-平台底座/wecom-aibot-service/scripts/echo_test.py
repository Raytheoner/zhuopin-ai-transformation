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
