"""三级重启退避耗尽后的故障告警——借道**现有 webhook 通道**（`wecom.py`），
不依赖本服务自身的智能机器人长连接（自身故障时不能指望自己的通道通知，见
design.md D2 第三道防线）。

用法：python alert_webhook.py "告警正文"

凭据：读**仓库根 `.env`** 的 `WECOM_WEBHOOK_URL_OPS`（运维逃生通道），与本服务
自身的 `WECOM_AIBOT_BOTID`/`SECRET` 是两套互不相关的凭据（并存不改，见 design.md D1）。

🔴 **2026-08-20 修正（队列 #282 ⑴ 包，变更包 `sweep-ops-webhook-cutover` 决策点 4a）**：
本脚本此前读 `5-平台底座/.env` 的裸 `WECOM_WEBHOOK_URL`，而**该文件里这个键的值长度
为 0**（主工作区那份 mtime 停在 2026-07-16 建服务当天，`ops/wecom-service-home` 生产
载体副本同样为空，两份均无 `_OPS`）⇒ 这条"第三道防线"**从建成起就没活过**：退避耗尽时
它只会打印"未配置"并 `exit 1`，告警永远发不出去。**它恰好坏在自己被设计出来的那个场合**
（2026-07-16 企微机器人停摆 24h49m 正是它该响的时候）。改读仓库根 `.env` 的 `_OPS`
恰好绕开"要再做一次配置动作"这个前置——根 `.env` 里 `_OPS` 已就位且已真实验通
（2026-08-19 `.51` 生产真发出过一条完整消息，企微 `errcode=0`）。

⚠️ **本项未经真实验证，且在 §四 `#68` 生产载体（worktree `ops/wecom-service-home`，
实测落后 `origin/master` 246 个提交）同步前不在生产生效。** 其触发条件是"企微服务三级
重启退避耗尽"，属天然罕见事件、无法按需构造，故本批只做代码修正、不计入已验收项。
"""
from __future__ import annotations

import os
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

from zhuopin_platform.shared_tools.notifiers import wecom  # noqa: E402

# 去向键只此一份，其余位置（日志文案、docstring）一律从本常量派生，不留字面量副本
# ——同 `0-学习与工具/工具-落库sweep.py::WECOM_WEBHOOK_ENV_KEY` 的取向。
OPS_WEBHOOK_ENV_KEY = "WECOM_WEBHOOK_URL_OPS"


def find_repo_root(start: Path) -> Path | None:
    """向上找到含 `5-平台底座/zhuopin_platform` 的那一层＝仓库根。

    刻意不复用上方引导块的 `_p`：那五行是 CI `bootstrap-stub-lint` 硬门禁强制的
    定型样板（不得含判断分支、不得改写），本函数另立以免动它。
    """
    for parent in start.resolve().parents:
        if (parent / "5-平台底座" / "zhuopin_platform").is_dir():
            return parent
    return None


def resolve_alert_webhook(repo_root: Path | None = None) -> str | None:
    """取运维逃生通道的 webhook URL；取不到即 None。

    🔴 **MUST NOT 回退到裸 `WECOM_WEBHOOK_URL`**——裸键指向业务部门群（采购内部
    工作群），回退命中即为发错群，而"发错群"正是队列 `#282` 拍板要消灭的事
    （「业务部门此后不从任何 webhook 收消息」）。同款语义见 FI2
    `scripts/scan_tax_export_scheduled.py::resolve_alert_webhook`（commit `30d1736`）
    与 `0-学习与工具/工具-落库sweep.py::_load_webhook_url`。
    """
    root = repo_root if repo_root is not None else find_repo_root(_HERE)
    if root is not None:
        load_dotenv(root / ".env")
    value = os.environ.get(OPS_WEBHOOK_ENV_KEY)
    return value or None


def main() -> None:
    message = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "企微智能机器人服务重启退避耗尽，请人工核查"
    )
    webhook_url = resolve_alert_webhook()
    if not webhook_url:
        print(f"{OPS_WEBHOOK_ENV_KEY} 未配置，无法发告警", file=sys.stderr)
        sys.exit(1)
    wecom.send_text(webhook_url, f"⚠️ 企微智能机器人服务告警\n{message}")


if __name__ == "__main__":
    main()
