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
QUEUE_PATH_ANCHOR_ENV = "WECOM_AIBOT_QUEUE_PATH"

# 队列文件在生产环境里被显式固定指向主工作区（见
# start-aibot-service-dev.ps1 的 WECOM_AIBOT_QUEUE_PATH），是两个 checkout
# 都能读到路径配置、且始终落在主工作区的稳定锚点。
#
# 队列 #315（2026-08-11，最小止血）：拆分为两份物理文件后，旧路径已改为
# 1237 字节的纯指针文件——不含 "## 一、任务看板" 标题行，`queue_appender.
# _section_bounds` 找不到 TABLE_HEADER_MARKER 即抛 LookupError；
# `intake.py` 只接 QueueLockBusy，接不住该异常，上抛后被 `connection.py`
# 的通用兜底捕获——消息仍正常归档进 7-外部文档，但**队列行不会生成**，
# 而拆件巡逻只认队列行，等同于这条回件在调度视野里从未发生（同 #286
# 「队列行真实丢失」的形态）。当时改指向机制环境文件，是与
# `工具-共享文档编辑锁.py::_resolve_append_target` 未声明域时默认落机制
# 环境文件一致的"迁移期妥协"（#315 design 决策点 3），非目标态。
#
# 🔴 队列 #341（2026-09-05，openspec 变更包 `queue-domain-routing` 决策点 2，
# Shao Peishen 拍板采纳默认项）：**改回指向业务场景文件**——机器人的产出
# 场景（专员反馈归档 → 登记队列行）恒定归属业务域，`queue-dual-file-split`
# design 决策点 4 项 6 早已采纳"机器人 100% 盲写业务场景队列"，只是被上述
# 止血覆盖了 25 天。2026-09-05 实测复核：当时那个阻塞条件（"业务场景文件
# 刚拆分完、是否已具备合法表格标题存疑"）已不成立，业务场景文件 §一 现有
# 完整表格与 44 行数据。
#
# 🔴 **本常量只承担两件事：①机器人新行的写入目标；②仓库根解析的锚点。**
# **它不是"§四／协议〇／编号高水位线在哪"的答案**——那三样按章节归属
# Requirement 恒在机制环境文件，见下方 `QUEUE_MECHANISM_RELATIVE_PATH`。
# 每日决策提醒（`scripts/decision_reminder_check.py`）读的是 §四，必须用
# 机制环境那个常量：本常量一旦被它误用，那条链路会读到一份**没有 §四** 的
# 文件，结果是"零条待决策"——与"今天真的没有待决策"在输出上逐字相同，
# 属本项目反复点名的"只读命令结果太干净"失效形态。
DEFAULT_QUEUE_RELATIVE_PATH = Path("1-转型规划") / "0-全景路线图" / "跨桌任务队列-业务场景.md"
# 队列 #341：机制环境物理队列文件——协议〇正文／§三口径冻结标／§四"需
# Shao Peishen 的动作"／编号高水位线声明行的权威载体（章节归属 Requirement，
# 见 `queue-dual-file-topology` spec）。读这四样的消费者一律用本常量，
# **不得**用 `DEFAULT_QUEUE_RELATIVE_PATH`。
QUEUE_MECHANISM_RELATIVE_PATH = Path("1-转型规划") / "0-全景路线图" / "跨桌任务队列-机制环境.md"
AUDIT_RELATIVE_PATH = Path("5-平台底座") / "wecom-aibot-service" / "reports" / "wecom_aibot_audit.jsonl"
# 队列 #192-C：此前 `run_aibot_service.py` 用 `SERVICE_DIR / "reports"`
# （机器人常驻 checkout 自身）硬编码这两个 pending 暂存文件落点，与
# AUDIT_RELATIVE_PATH 早已按 #126 解析到的主工作区分处两地——sweep 跑在
# 主工作区，找不到这两个文件，flush 永远空转且不报错。改与 audit 同一套
# `resolve_repo_root()` 解析结果，统一落盘位置。
PENDING_QUEUE_APPENDS_RELATIVE_PATH = (
    Path("5-平台底座") / "wecom-aibot-service" / "reports" / "pending_queue_appends.jsonl"
)
PENDING_QUEUE_LOCK_APPENDS_RELATIVE_PATH = (
    Path("5-平台底座") / "wecom-aibot-service" / "reports" / "pending_queue_lock_appends.jsonl"
)
# 队列 #124 阶段二追加要求①：approval.py 冷却窗口"首次观测到该行"时间戳
# 存放位置，与 audit/pending 系列文件同一套 repo_root 解析、同一目录。
FOLLOWUP_APPROVAL_COOLDOWN_STATE_RELATIVE_PATH = (
    Path("5-平台底座") / "wecom-aibot-service" / "reports" / "followup_approval_cooldown_state.json"
)
# 队列 #312：可 Open 池指纹状态（当前已提醒过的行号集合），与 audit/
# pending 系列文件同一套 repo_root 解析、同一目录。
OPEN_POOL_REMINDER_STATE_RELATIVE_PATH = (
    Path("5-平台底座") / "wecom-aibot-service" / "reports" / "open_pool_reminder_state.json"
)
# 队列 #382⑴：拆件巡逻事件驱动开班信号，与 audit/pending 系列文件同一套
# repo_root 解析、同一目录（见 patrol_signal.py）。
PATROL_SIGNAL_RELATIVE_PATH = (
    Path("5-平台底座") / "wecom-aibot-service" / "reports" / "patrol_signal.json"
)
# 队列 #382⑴bis：桥一落信号后直接起无头 CC 拆件（零轮询）——并发守卫锁
# 文件与输出日志目录，与 audit/pending 系列文件同一套 repo_root 解析、
# 同一目录（见 patrol_dispatch.py）。
PATROL_DISPATCH_LOCK_RELATIVE_PATH = (
    Path("5-平台底座") / "wecom-aibot-service" / "reports" / "patrol_dispatch.lock.json"
)
PATROL_DISPATCH_LOG_DIR_RELATIVE_PATH = (
    Path("5-平台底座") / "wecom-aibot-service" / "reports" / "patrol-headless-logs"
)
# 拆件巡逻章程正本——已由 #382⑴bis 从仓库外 `C:\Users\Paul Shao\Claude\
# Scheduled\huijian-chaijian-patrol\SKILL.md` 原文照搬迁入仓库（无头 CC
# 读不到仓库外路径，见 patrol_dispatch.py 文首取舍 1）。
PATROL_CHARTER_RELATIVE_PATH = (
    Path("0-学习与工具") / "skills源码" / "huijian-chaijian-patrol" / "SKILL.md"
)


def resolve_default_queue_anchor(
    naive_repo_root: Path,
    relative_path: Path = DEFAULT_QUEUE_RELATIVE_PATH,
    *,
    env: Optional[Mapping[str, str]] = None,
) -> Path:
    """计算 `WECOM_AIBOT_QUEUE_PATH` 未显式设置时的默认锚点（队列 #269，
    2026-08-06，真实事故：跟进信批准脚本的 10 分钟冷却窗口状态文件误判
    丢失，根因见下）。

    此前各脚本未设该环境变量时，直接用 `naive_repo_root / relative_path`
    （即"本 checkout 自身"）当锚点——`resolve_repo_root` 据此把 repo_root
    正确地解到锚点自己所在的那个 checkout（这是 `resolve_repo_root` 自身
    的既定契约，见 `test_resolve_repo_root_cross_worktree`，未变、不能变）。
    但当调用方是 CC 从临时 worktree 里跑的一次性脚本（本项目常规工作方式，
    一任务一 worktree）、且没人记得手工设这个环境变量时，"本 checkout"
    就是这个用完即删的临时 worktree——`resolve_audit_path`/
    `resolve_followup_approval_cooldown_state_path` 等据此算出的落点全部
    物理落在这个临时 worktree 的 `reports/` 里（`.gitignore` 覆盖，worktree
    一删就丢）。批准脚本的 10 分钟冷却窗口状态因此每次从新 worktree 调用
    都"重新观测"，永远等不到窗口过期——真实复现见队列 #269。

    修法（与 `工具-共享文档编辑锁.py::_resolve_repo_root` 的 2026-07-23 修法
    同源）：未显式设置该环境变量时，不再默认"本 checkout 自身"，改为先用
    `git rev-parse --git-common-dir` 找到所有 linked worktree 共享的那个
    `.git` 目录、取其父目录作为"规范仓库根"（对非 linked-worktree 场景，
    即只有一个普通 clone 时，`--git-common-dir` 的父目录就是这个 clone
    自己，行为不变）；解析失败（非 git 目录等极端环境）才回落
    `naive_repo_root / relative_path`（修复前的既有行为，不引入新失败模式）。
    机器人常驻服务的启动脚本显式设置了该环境变量，优先级不变、不受本次
    改动影响。
    """
    if env is None:
        env = os.environ
    override = env.get(QUEUE_PATH_ANCHOR_ENV)
    if override:
        return Path(override)
    try:
        result = subprocess.run(
            ["git", "-C", str(naive_repo_root),
             "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, encoding="utf-8", check=True,
        )
        common_dir = result.stdout.strip()
        if common_dir:
            return Path(common_dir).parent / relative_path
    except (subprocess.CalledProcessError, OSError, FileNotFoundError):
        pass
    return naive_repo_root / relative_path


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


def resolve_pending_queue_appends_path(repo_root: Path) -> Path:
    """队列 #192-C：git 推送失败暂存（`queue_git_sync._append_pending_record`）
    的统一落点，与 `resolve_audit_path` 同一套 `repo_root`。"""
    return repo_root / PENDING_QUEUE_APPENDS_RELATIVE_PATH


def resolve_pending_queue_lock_appends_path(repo_root: Path) -> Path:
    """队列 #192-C：编辑锁忙推迟暂存（`queue_lock_pending.py`）的统一落点，
    与 `resolve_audit_path` 同一套 `repo_root`。"""
    return repo_root / PENDING_QUEUE_LOCK_APPENDS_RELATIVE_PATH


def resolve_followup_approval_cooldown_state_path(repo_root: Path) -> Path:
    """队列 #124 阶段二追加要求①：approval.py 冷却窗口状态文件的统一落点，
    与 `resolve_audit_path` 同一套 `repo_root`。"""
    return repo_root / FOLLOWUP_APPROVAL_COOLDOWN_STATE_RELATIVE_PATH


def resolve_open_pool_reminder_state_path(repo_root: Path) -> Path:
    """队列 #312：可 Open 池指纹状态文件的统一落点，与 `resolve_audit_path`
    同一套 `repo_root`。"""
    return repo_root / OPEN_POOL_REMINDER_STATE_RELATIVE_PATH


def resolve_patrol_signal_path(repo_root: Path) -> Path:
    """队列 #382⑴：拆件巡逻事件驱动开班信号文件的统一落点，与
    `resolve_audit_path` 同一套 `repo_root`。"""
    return repo_root / PATROL_SIGNAL_RELATIVE_PATH


def resolve_patrol_dispatch_lock_path(repo_root: Path) -> Path:
    """队列 #382⑴bis：无头 CC 并发守卫锁文件的统一落点，与
    `resolve_audit_path` 同一套 `repo_root`。"""
    return repo_root / PATROL_DISPATCH_LOCK_RELATIVE_PATH


def resolve_patrol_dispatch_log_dir(repo_root: Path) -> Path:
    """队列 #382⑴bis：事件驱动起活的无头 CC 输出日志目录，与
    `resolve_audit_path` 同一套 `repo_root`。"""
    return repo_root / PATROL_DISPATCH_LOG_DIR_RELATIVE_PATH


def resolve_patrol_charter_path(repo_root: Path) -> Path:
    """队列 #382⑴bis：拆件巡逻章程正本（已迁入仓库，原文照搬）的统一
    落点，与 `resolve_audit_path` 同一套 `repo_root`。"""
    return repo_root / PATROL_CHARTER_RELATIVE_PATH
