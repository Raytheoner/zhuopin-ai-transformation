"""跨 checkout 的仓库根/审计路径解析（队列 #126，两处同根因缺陷共用修法）。

企微机器人常驻服务跑在 `ops/wecom-service-home` worktree、一次性脚本
（`push_followup_letter.py` 等）按惯例在主工作区跑——同一份代码在两个不同
checkout 里执行，若各自以 `__file__` 反推 repo 根，解出两个不同（但都合法）
的 worktree 根，导致两处独立缺陷：

① `queue_git_sync` 拿服务自己的 checkout 根去校验队列文件（固定指向主工
   作区）的 subpath，直接抛异常，git 同步整条降级（见 `queue_git_sync.py`）。
② 两边各自的 `reports/wecom_aibot_audit.jsonl` 落在不同物理文件里，收发
   留痕分处两处，IATF 16949 可追溯性打折。

两处统一改为：以调用方已知的某个"锚点路径"（队列文件、README 等——始终
落在同一个逻辑仓库里）为准，用 `git -C <锚点父目录> rev-parse --show-toplevel`
动态解析其真正所属的 repo 根，而不信任调用方自己 `__file__` 反推的根（与
2026-07-23 编辑锁 `--git-common-dir` 修法同源思路）。`WECOM_AIBOT_REPO_ROOT`
环境变量提供显式覆盖口（优先级最高，绕开 git 解析，给独立 clone/异常环境
兜底）。解析失败（锚点根本不在任何 git 工作树里）才回落调用方传入的
`fallback`——即修复前的行为，不引入新的失败模式。
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Mapping, Optional

REPO_ROOT_OVERRIDE_ENV = "WECOM_AIBOT_REPO_ROOT"

# 队列文件在生产环境里被显式固定指向主工作区（见
# start-aibot-service-dev.ps1 的 WECOM_AIBOT_QUEUE_PATH），是两个 checkout
# 都能读到路径配置、且始终落在主工作区的稳定锚点。
DEFAULT_QUEUE_RELATIVE_PATH = Path("1-转型规划") / "0-全景路线图" / "跨桌任务队列.md"
AUDIT_RELATIVE_PATH = Path("5-平台底座") / "wecom-aibot-service" / "reports" / "wecom_aibot_audit.jsonl"


def resolve_repo_root(
    anchor_path: Path,
    *,
    fallback: Path,
    env: Optional[Mapping[str, str]] = None,
) -> Path:
    """解析 `anchor_path` 实际所属的 git 仓库根。

    优先级：`WECOM_AIBOT_REPO_ROOT` 环境变量显式覆盖 > 动态 git 解析（以
    `anchor_path` 所在目录为起点问 git "你的工作树根在哪"）> `fallback`
    （调用方按自身 `__file__` 反推的根，仅在前两者都不可用时使用——"解析
    失败才回落现状"）。

    `env` 默认读 `os.environ`（生产用法）；测试注入自定义 dict，避免依赖/
    污染真实进程环境变量。
    """
    if env is None:
        env = os.environ
    override = env.get(REPO_ROOT_OVERRIDE_ENV)
    if override:
        return Path(override)

    anchor_dir = anchor_path if anchor_path.is_dir() else anchor_path.parent
    result = subprocess.run(
        ["git", "-C", str(anchor_dir), "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode == 0:
        toplevel = result.stdout.strip()
        if toplevel:
            return Path(toplevel)
    return fallback


def resolve_audit_path(repo_root: Path) -> Path:
    """统一的审计文件物理位置——常驻服务与一次性脚本共用同一份文件，
    消除收发留痕分裂（队列 #126 缺陷②）。"""
    return repo_root / AUDIT_RELATIVE_PATH
