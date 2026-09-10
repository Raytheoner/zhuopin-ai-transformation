r"""三级重启退避耗尽后的故障告警——借道**现有 webhook 通道**（`wecom.py`），
不依赖本服务自身的智能机器人长连接（自身故障时不能指望自己的通道通知，见
design.md D2 第三道防线）。

用法：python alert_webhook.py "告警正文"

凭据：读**承载 `.env` 的那一层**（开发机 monorepo ＝ 仓库根；`.51` 扁平部署 ＝
`C:\wecom-aibot`）的 `WECOM_WEBHOOK_URL_OPS`（运维逃生通道），与本服务自身的
`WECOM_AIBOT_BOTID`/`SECRET` 是两套互不相关的凭据（并存不改，见 design.md D1）。

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

🔴 **2026-09-10 二次修正（队列 §一 `#419`，`OP-0910-F`）**：上面那次修正**并没有把这条
防线救活**——2026-08-26 复核实测出取值在两个真实载体上**仍然**为 `None`，死因只是从
"键值长 0"换成了"`find_repo_root()` 在生产布局上恒为 `None`"。本次按 Shao Peishen
2026-09-09 拍板的修法 (a) 给 `find_repo_root()` 增补扁平布局分支（详见该函数 docstring）。

**本次实测（非 mock，`OP-0910-F`）**：按 `deploy-server.ps1` 实证布局在盘上搭出
`<base>/{app,zhuopin_platform,.env}`、把本脚本原样放进 `<base>/app/scripts/`、`.env` 内
写真实形态的 `_OPS`，**真实 import 本模块并调 `resolve_alert_webhook()`，取到该值**；
改前同一副盘返回 `None`（对照跑，见队列 `#419` 回写）。

🔴 **仍未闭合的一半（D1，如实写明、不假装完工）**：本服务的生产载体是**笔记本**上的
worktree `ops/wecom-service-home`，它是 monorepo 布局、走第一趟分支返回自身 worktree
根 —— 而 `.env` 属 `.gitignore` 件、**不随 worktree 生成**⇒ 该载体上仍取不到值。这是
**配置落位问题、不是代码缺陷**，须在该 worktree 根放一份含 `_OPS` 的 `.env`（凭据动作，
只能由 Shao Peishen 本人做），已登记队列 `#419`。
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
from zhuopin_platform.bootstrap import MARKER_PARTS, ensure_paths  # noqa: E402
ensure_paths(__file__, SERVICE_DIR)  # noqa: E402

from zhuopin_platform.shared_tools.notifiers import wecom  # noqa: E402

# 去向键只此一份，其余位置（日志文案、docstring）一律从本常量派生，不留字面量副本
# ——同 `0-学习与工具/工具-落库sweep.py::WECOM_WEBHOOK_ENV_KEY` 的取向。
OPS_WEBHOOK_ENV_KEY = "WECOM_WEBHOOK_URL_OPS"

# 扁平部署布局的平台底座标记 ＝ monorepo 标记去掉 `5-平台底座` 那一层后剩下的包目录名。
# **从 `MARKER_PARTS` 派生、不留字面量副本**：两种布局认的是同一个包目录，差别只在它上面
# 有没有 `5-平台底座`（`bootstrap.py` 模块 docstring 的两种布局对照表即此意）；写成字面量
# 就会在日后改名时静默漂成两份。
FLAT_MARKER_PART = MARKER_PARTS[-1]


def find_repo_root(start: Path) -> Path | None:
    """向上找到**承载 `.env` 的那一层**：monorepo 优先，`.51` 扁平部署兜底。

    | 布局 | 标记 | 返回 | `.env` 位置 |
    |---|---|---|---|
    | 开发机 monorepo | `<repo>/5-平台底座/zhuopin_platform` | `<repo>` | `<repo>/.env` |
    | `.51` 扁平部署 | `<base>/zhuopin_platform`（与 `app` 兄弟） | `<base>` | `<base>/.env` |

    🔴 **两趟扫描必须分开、且 monorepo 那趟必须先整趟走完，不得合成一个循环逐层双判**
    ——合并写法在 monorepo 里会给出**反向错误答案**：从
    `<repo>/5-平台底座/wecom-aibot-service/scripts/` 往上走，先到达的是 `5-平台底座`
    这一层，它底下确实有 `zhuopin_platform`，扁平判据在此**为真**，于是函数返回
    `<repo>/5-平台底座` —— 正好是 `#282` 拍板要弃用的那份 `5-平台底座/.env`
    （其裸键值长 0、且无 `_OPS`）。这不是"少认一种布局"，是**认回了被退役的那一份**。

    刻意不复用上方引导块的 `_p`：那五行是 CI `bootstrap-stub-lint` 硬门禁强制的
    定型样板（不得含判断分支、不得改写），本函数另立以免动它。

    🔴 **2026-09-10 增补扁平分支（队列 §一 `#419` 第①问，Shao Peishen 2026-09-09
    定 (a)；`OP-0910-F`）**：原实现只认 monorepo 标记，而据 `bootstrap.py` 模块
    docstring，那层目录**正是扁平部署本就没有的**⇒ 在 `.51` 布局下 `find_repo_root()`
    恒返回 `None`、`load_dotenv` 从不执行、取值恒为 `None`。这条"第三道防线"因此
    **从建成起就没活过**（先是键值长 0，改读 `_OPS` 后换成本缺陷），且它恰好坏在自己
    被设计出来的那个场合（2026-07-16 企微机器人停摆 24h49m）。
    """
    start = start.resolve()
    # 第一趟：monorepo 标记（权威）——整趟走完再考虑扁平，理由见 docstring。
    for parent in start.parents:
        if parent.joinpath(*MARKER_PARTS).is_dir():
            return parent
    # 第二趟：扁平部署兜底（`<base>/zhuopin_platform` 与 `app` 兄弟）。
    for parent in start.parents:
        if (parent / FLAT_MARKER_PART).is_dir():
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
