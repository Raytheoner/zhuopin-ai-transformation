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
import subprocess
import sys
import urllib.request
from pathlib import Path


def _resolve_repo_root() -> Path:
    """定位主工作区根目录（`git rev-parse --git-common-dir`，逐字复用
    `工具-共享文档编辑锁.py::_resolve_repo_root` 同一判据，不重写第二份）。

    🔴 2026-09-05 实撞修复：本文件曾用 `Path(__file__).resolve().parent.parent`
    按脚本自身路径推算——`工具-泳道看护状态机.py` 的 `pause` 在隔离 worktree
    内跑时，会从该 worktree 本地的 `0-学习与工具/发企微.py` 副本加载本模块，
    `__file__` 于是解到 worktree 根而非主工作区根；`.env` 已被 `.gitignore`、
    只存在于主工作区，worktree 根下找不到 ⇒ `load_webhook()` 直接 `sys.exit`，
    被调用方 `_notify_best_effort` 的 `except SystemExit` 吞掉、静默降级为
    「仅落状态」——凡从 CC worktree 里发起的 pause「等你」企微通知全部悄悄
    丢失，Shao Peishen 收不到提醒。跑不了 git（非仓库/未装 git）时退回按脚本
    自身路径推算，保底不崩。
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True, text=True, check=True,
        )
        return Path(result.stdout.strip()).parent
    except (subprocess.CalledProcessError, OSError, FileNotFoundError):
        return Path(__file__).resolve().parent.parent


REPO_ROOT = _resolve_repo_root()  # 恒指主工作区根，不论从哪个 worktree 加载本模块
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
