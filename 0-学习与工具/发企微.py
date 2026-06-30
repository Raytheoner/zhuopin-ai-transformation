#!/usr/bin/env python3
"""发企微 —— 本项目自包含的企业微信群机器人推送（零外部依赖，纯标准库）。

与 supplychain 脱钩：webhook 从【本项目】根目录 .env 的 WECOM_WEBHOOK_URL 读取。
在公网 HTTPS（qyapi.weixin.qq.com）上发送，**在不在公司内网都能用**（off-LAN 亦可，有互联网即可）。

用法（在装了 Python 的机器上）：
    python 0-学习与工具/发企微.py
        → 默认发送 1-转型规划/企微推送正文-今日同步.md
    python 0-学习与工具/发企微.py 路径/某正文.md
        → 发送指定的 markdown 正文文件

前置（一次性）：把 supplychain/.env 里那行 WECOM_WEBHOOK_URL=... 拷到
本项目根目录 .env（同一个群机器人）。.env 已被 .gitignore，凭据不入库。

企微 markdown 子集：**加粗** / <font color="warning|info">…</font> / > 引用 / [链接](url) / --- 分割线；
不支持 # 标题与表格，正文上限约 4096 字符。
"""
import json
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent  # 0-学习与工具/ 的上一级 = 项目根
DEFAULT_MSG = REPO_ROOT / "1-转型规划" / "企微推送正文-今日同步.md"


def load_webhook() -> str:
    env = REPO_ROOT / ".env"
    if not env.exists():
        sys.exit(f"❌ 未找到 {env}；请在项目根 .env 添加 WECOM_WEBHOOK_URL=...")
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("WECOM_WEBHOOK_URL="):
            url = line.split("=", 1)[1].strip().strip('"').strip("'")
            if url:
                return url
    sys.exit("❌ .env 里没有 WECOM_WEBHOOK_URL=（把 supplychain/.env 那行拷过来即可）")


def send_markdown(webhook_url: str, content: str) -> None:
    payload = json.dumps(
        {"msgtype": "markdown", "markdown": {"content": content}},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        webhook_url, data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if result.get("errcode", 0) != 0:
        sys.exit(f"❌ 推送失败 errcode={result.get('errcode')} errmsg={result.get('errmsg')}")


def main() -> None:
    msg_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_MSG
    if not msg_path.exists():
        sys.exit(f"❌ 正文文件不存在：{msg_path}")
    content = msg_path.read_text(encoding="utf-8")
    if len(content) > 4096:
        sys.exit(f"❌ 正文 {len(content)} 字符，超企微 4096 上限；请拆分或精简。")
    send_markdown(load_webhook(), content)
    print(f"✅ 已发送：{msg_path.name}（{len(content)} 字符）")


if __name__ == "__main__":
    main()
