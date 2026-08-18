"""三级重启退避耗尽后的故障告警——借道**现有 webhook 通道**（`wecom.py`），
不依赖本服务自身的智能机器人长连接（自身故障时不能指望自己的通道通知，见
design.md D2 第三道防线）。

用法：python alert_webhook.py "告警正文"
凭据：读 `5-平台底座/.env`（与 SC8 同层级）的 `WECOM_WEBHOOK_URL`——这是项目
**既有**群 webhook 凭据，与本服务自身的 `WECOM_AIBOT_BOTID`/`SECRET` 是两套
互不相关的凭据（并存不改，见 design.md D1）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

SERVICE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(SERVICE_DIR.parent / ".env")

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

from zhuopin_platform.shared_tools.notifiers import wecom  # noqa: E402


def main() -> None:
    message = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "企微智能机器人服务重启退避耗尽，请人工核查"
    )
    webhook_url = os.environ.get("WECOM_WEBHOOK_URL")
    if not webhook_url:
        print("WECOM_WEBHOOK_URL 未配置，无法发告警", file=sys.stderr)
        sys.exit(1)
    wecom.send_text(webhook_url, f"⚠️ 企微智能机器人服务告警\n{message}")


if __name__ == "__main__":
    main()
