"""落库 sweep 定时任务（队列 #68③，Paul 2026-07-24 拍板五条硬要求）。

背景：跨桌任务队列.md §二"待 commit 批次"是 Cowork/专线登记、CC 手工取活提交的
唯一载体——《构建自动化workflow设计-2026-07-21.md》§三 指出"⑤落地"环节虽已半自动，
但仍要等 Paul 逐条转述"交 CC 取活"，是两大堵点之一。本脚本把这一步 sweep 化：
定时扫 §二，把已就绪（文件确已落盘、无关改动不干扰）的待 commit 批次自动
git add + commit + push，并把队列自身的销行标记与批次内容**合进同一个 commit**，
从机制上消灭"内容已提交、销行还没跟上"的慢一拍尾巴（历史上曾靠 CC 手工逐行核对
git 历史才救回，见协议〇.7 背景）。

五条硬要求（Paul 2026-07-24）与本脚本对应实现：
① 只 `git add` 各批次行列出的文件，绝不 `git add -A`——见 _resolve_batch_files()，
   仅对已在批次"文件清单"列中以反引号标出的路径做 add，其余任何脏文件一律不碰。
② 改队列销行前 acquire 编辑锁、改完 release；销行标记与批次文件同一 commit——
   见 _process_batch()：git add 批次文件 → 加锁改队列 → 一次 commit 两者一起进。
③ 主工作区非 master / 非 clean / 推送非快进时跳过本轮并告警，不强推——见
   _check_preconditions() 与 _verify_fast_forward()。
④ 计划任务 Action 指主工作区稳定路径（非建造 worktree）+ SYSTEM + AtStartup +
   绝对路径烘焙——本脚本运行时另有 MAIN_WORKSPACE 断言兜底（见 _resolve_repo_root），
   注册脚本见 `register-commit-sweep-task.ps1`。
⑤ 台账随 sweep 重跑一次（仅当本轮确有批次被处理时才重跑，见 main() 末尾）。

"非 clean" 的定义（关键设计决策，非字面"git status 必须全空"）：
    §二 待 commit 批次的存在本身就意味着主工作区必然有未提交改动（那正是
    "待 commit"的含义）——若把"clean"理解成"git status 完全无输出"，sweep 将
    永远无法处理任何批次，自相矛盾。本脚本把"clean"定义为：
    **git status 里的每一处脏改动，都能对应到当前某条待 commit 批次的"文件清单"
    声明——如果存在声明之外的脏文件/未跟踪文件，视为"非 clean"，整轮跳过。**
    这与要求①同源：只处理"账面对得上"的批次，账面之外的任何东西（哪怕看起来
    无害）都交给人工判断，不猜。2026-07-24 实测：主工作区当时确有 CLAUDE.md 的
    未提交改动 + 4 个未跟踪文件，均不属于任何待 commit 批次声明——sweep 据此正确
    整轮跳过，是本设计决策的第一次真实验证（见收工报告）。

退出码：0=本轮正常结束（无论是"处理了批次"还是"安全跳过"）；
        2=出现需要人工介入的异常（本地已提交但推送不了/非快进，不会自动强推；
          含起跑前置分叉检测，见下）；
        1=脚本自身参数或环境错误（不应在正常运行中出现）。

分叉静默停摆告警（队列 #171，2026-07-30 Antigravity 评审 triage 核证发现）：
起跑前置检查 `_verify_fast_forward(refetch=False, ...)` 此前失败时退出码固定
为 0——计划任务看到的是"成功"，而本脚本全文此前无任何 webhook/notify，唯一
留痕是 `reports/sweep-commit.log`，只有人工翻日志才会发现。真实触发条件：PR
在本脚本运行窗口内（早期 fetch 与提交后 push 之间）被并发合并，本地提交已落、
origin 已前移，此后每轮都在这个前置检查处跳过，永久静默直到人工介入（PR 在
本脚本空闲时合并不会触发——下一轮 `_sync_master_if_behind_origin` 会自动
`--ff-only` 追上，不构成分叉）。修法：① 前置检查改用 `is_fork=True` 标记
（见 `SweepAbort.is_fork`），退出码由 0 改为 2（人工介入语义），并复用
`发企微.py` 同款零依赖 webhook 推送主动告警一次（见 `_handle_fork_detected`）；
② 连续多轮仍分叉时，告警文案带上连续轮次（见 `_read_fork_state`/
`_write_fork_state` 持久化到 `reports/sweep-fork-state.json`），分叉一旦解除
（前置检查转为通过）立即清空该状态，不与"偶发跳过"（非 master/非 clean/
无待处理批次等健康跳过路径，退出码仍为 0，不触发告警）混淆。**勿采信"拦
协调文件 PR 可解此问题"**——非快进由 commit 祖先关系决定，与改哪个文件无关，
只有主动告警才能让"静默"变"有人知道"。

陈旧 `.git/index.lock` 前置自愈（#121(b)，2026-07-27 补）：起跑第一步先查
`.git/index.lock`——超过 STALE_INDEX_LOCK_MINUTES（默认 10 分钟）未清的判定
为异常退出残留，自动清除后继续；新鲜的（大概率是真实并发 git 进程）不抢占，
优雅跳过本轮并写日志。见 _heal_stale_index_lock()——修复前该文件残留会让
后续 `_run_git`（check=True）抛未捕获异常，表现正是"计划任务 LastTaskResult=1
但日志无新条目"。

批次判据显式化（2026-07-28 补，根治静默失效）：原判据 `"✅" not in
status_cell` 把"待处理"定义成"不含✅"——登记方一旦图省事在状态列说明性
文字里带了✅（如"✅ 已完成（本次登记，待 sweep 落库）"），该批次就被永久
判定为"已处理"而跳过，且没有任何日志提示。2026-07-27 深夜已实测命中两条
批次（队列 §二 顶部登记说明记有 `B-0728财务专线核实`/`B-0728队列#125回填`
两例），当时全靠人工肉眼发现、手改回不含✅的写法才追上。根治：判据改为
显式"待"字样（见 _classify_section_two_rows()）——只有状态列含"待"（待
处理/待取活/待 sweep 落库等）才算待处理，不论是否同时误带"✅"；状态列
既不含"✅"也不含"待"的模糊状态，不再被默默漏过，改为输出告警日志、不纳入
本轮处理，交人工核查（宁可吵不可哑）。

本地 master 落后 origin 前置自愈（2026-07-28 补）：主工作区本地 `master`
分支指针不会随"其他 worktree 把改动推去 origin/master"自动前进——`git
fetch` 只更新 `origin/master` 远程跟踪分支，本地分支需要显式 merge 才会
移动。2026-07-27 一天内三次出现这一情形，若不处理，下一步"能否快进推送"
检查会把纯粹的"落后"误判为"跳过本轮"。见 _sync_master_if_behind_origin()：
本地是 origin/master 祖先（纯落后、可快进）即自动 `git merge --ff-only
origin/master` 追上再继续干活；两边已分叉（互不为祖先）则不动手，仍按原
语义告警跳过本轮，不强推、不自动 rebase。

用法：
  python 0-学习与工具/工具-落库sweep.py            # 真跑
  python 0-学习与工具/工具-落库sweep.py --dry-run   # 只打印计划动作，不落地
  # --repo-root 仅供单测覆盖 MAIN_WORKSPACE 断言，生产不要传
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

MAIN_WORKSPACE = Path(r"C:\Users\Paul Shao\OneDrive\Projects\企业AI转型")
QUEUE_REL = "1-转型规划/0-全景路线图/跨桌任务队列.md"
LEDGER_SCRIPT_REL = "0-学习与工具/工具-文档台账生成.py"
LEDGER_OUTPUT_REL = "1-转型规划/0-全景路线图/文档台账-自动生成.md"
EDIT_LOCK_SCRIPT_REL = "0-学习与工具/工具-共享文档编辑锁.py"
LOG_REL = "reports/sweep-commit.log"
LOCK_WHO = "sweep-commit"
STALE_INDEX_LOCK_MINUTES = 10

# 队列 #171：分叉静默停摆告警。
ENV_REL = ".env"
WECOM_WEBHOOK_ENV_KEY = "WECOM_WEBHOOK_URL"
FORK_STATE_REL = "reports/sweep-fork-state.json"
FORK_EXIT_CODE = 2  # 复用既有"需要人工介入"语义，不新造一套退出码

SECTION_TWO_HEADING = "## 二、"
NEXT_SECTION_PREFIX = "## "

# 队列 #198(a)：main() 通用异常兜底的独立退出码——与"健康跳过（0）"、
# "分叉/需人工介入（FORK_EXIT_CODE=2）"均不同，使 sweep-commit.log 零新增行
# 此后只剩一个含义（任务根本没启动），"跑了但崩了"改为走这个退出码 + 有
# 日志留痕，判据不再二义（见队列 #198(a) 验收物）。
UNEXPECTED_EXIT_CODE = 3

# 队列 #192-A：flush `pending_queue_lock_appends.jsonl` 的子进程触发脚本
# （sweep 刻意不 import aibot_service/zhuopin_platform，见文件头部"零依赖"
# 设计说明——多 worktree 共享全局 editable install，进程内 import 有被
# 静默劫持到别的 checkout 的风险，走子进程规避）。
FLUSH_PENDING_LOCK_SCRIPT_REL = (
    "5-平台底座/wecom-aibot-service/scripts/flush_pending_lock_appends.py"
)

# 队列 #198(c)：本轮 commit 若命中这些前缀下的路径，视为"涉常驻服务"，
# 需部署脚本同步+重启对应计划任务才在生产生效（现状全靠人记得）。
RESIDENT_SERVICE_PATH_PREFIXES = ("5-平台底座/wecom-aibot-service/",)


class SweepAbort(Exception):
    """安全门未过或运行中出现需要人工介入的异常，携带退出码与提示。

    `is_fork`（队列 #171）：仅起跑前置分叉检测这一处会置 True——main() 据此
    触发主动告警（`_handle_fork_detected`），与其余"健康跳过"（非 master/
    非 clean/无待处理批次等，退出码仍为 0、不告警）区分开。
    """

    def __init__(self, message: str, exit_code: int = 0, is_fork: bool = False):
        super().__init__(message)
        self.exit_code = exit_code
        self.is_fork = is_fork


def _run_git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    # -c core.quotepath=false：不加此项时 git 会把中文路径转成八进制转义的带引号
    # 字符串（如 "1-\350\275\254..."），本项目路径几乎全是中文，不关掉这个
    # 会让 status/show/diff 的路径解析全部失真。生产仓库大概率已在全局配置里
    # 关闭过（未观察到该现象），但脚本自身不应依赖这一假设——每次调用显式带上。
    return subprocess.run(
        ["git", "-c", "core.quotepath=false", *args], cwd=cwd, capture_output=True,
        text=True, encoding="utf-8", check=check,
    )


def _resolve_repo_root(override: str | None) -> Path:
    if override is not None:
        return Path(override).resolve()
    return MAIN_WORKSPACE


def _assert_not_a_linked_worktree(repo_root: Path) -> None:
    """`.git` 是文件夹=主工作区；是文件（指向别处 gitdir）=linked worktree。

    要求④"勿指建造 worktree"——即便计划任务配置写错指到了某个
    `.claude/worktrees/<name>`，运行时也应在此处硬失败，而不是悄悄在一次性
    建造分支上做出提交（该分支任务完工后可能被 `git worktree remove` 连同
    未推送的提交一起丢弃，参见协议〇.5 收工自删 worktree）。
    """
    git_path = repo_root / ".git"
    if not git_path.is_dir():
        raise SweepAbort(
            f"✗ {repo_root} 的 .git 不是目录（可能是 linked worktree 或非仓库路径）——"
            "sweep 只允许在主工作区运行，本轮不做任何改动。",
            exit_code=1,
        )


def _heal_stale_index_lock(repo_root: Path, log: list[str]) -> None:
    """起跑前自愈陈旧的 `.git/index.lock`（#121(b) 根因排查产出）。

    背景：`.git/index.lock` 残留期间，本脚本后续任何 `_run_git`（默认
    check=True）调用都会抛未捕获的 CalledProcessError——它不是 SweepAbort，
    main() 的 `except SweepAbort` 接不住，_flush_log 也就没机会写盘。这正是
    #121(b) 实测到的现象："LastTaskResult=1 但 sweep-commit.log 无任何新行"
    （11:37/11:39 两次手动触发疑似与短时间内重复触发/index.lock 残留有关）。

    只清"陈旧"（mtime 超过 STALE_INDEX_LOCK_MINUTES 分钟）的锁；新鲜的锁大概率
    对应正在跑的真实 git 进程（含本脚本另一实例的并发触发），不抢占、不误杀，
    改为优雅跳过本轮并把原因写进日志——把"未捕获异常静默失败"变成"有记录的
    安全跳过"，即便暂时不清锁，这本身也修复了 #121(b) 的核心症状（日志无新行）。
    """
    lock_file = repo_root / ".git" / "index.lock"
    if not lock_file.exists():
        return
    age_minutes = (time.time() - lock_file.stat().st_mtime) / 60
    if age_minutes < STALE_INDEX_LOCK_MINUTES:
        raise SweepAbort(
            f"⚠ 检测到新鲜的 .git/index.lock（{age_minutes:.1f} 分钟前，"
            f"<{STALE_INDEX_LOCK_MINUTES} 分钟视为可能仍在运行的真实 git 进程）——"
            "跳过本轮，不抢占，等其自然结束或下一轮重试。",
        )
    lock_file.unlink()
    log.append(
        f"⚠ 已自愈陈旧 .git/index.lock（{age_minutes:.1f} 分钟前遗留，"
        "判定为异常退出残留，已清除）。"
    )


def _check_preconditions(repo_root: Path, production: bool) -> None:
    if production and repo_root != MAIN_WORKSPACE:
        raise SweepAbort(
            f"✗ repo_root={repo_root} 与约定的主工作区路径 {MAIN_WORKSPACE} 不符——"
            "拒绝运行（防止计划任务配置误指到 worktree）。",
            exit_code=1,
        )
    _assert_not_a_linked_worktree(repo_root)

    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root).stdout.strip()
    if branch != "master":
        raise SweepAbort(f"⚠ 主工作区当前分支是「{branch}」非 master——跳过本轮，不强切分支。")

    for marker in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "rebase-merge", "rebase-apply"):
        if (repo_root / ".git" / marker).exists():
            raise SweepAbort(f"⚠ 检测到未完成的 git 操作（{marker} 存在）——跳过本轮，不强行处理。")

    status = _run_git(["status", "--porcelain=v1"], repo_root).stdout
    if any(line[:2].strip().upper() == "U" or line[:2] in ("AA", "DD") for line in status.splitlines()):
        raise SweepAbort("⚠ git status 显示存在未合并冲突路径——跳过本轮，不强行处理。")


def _fetch(repo_root: Path) -> None:
    result = _run_git(["fetch", "origin", "master", "--quiet"], repo_root, check=False)
    if result.returncode != 0:
        raise SweepAbort(f"⚠ git fetch origin master 失败（{result.stderr.strip()}）——跳过本轮。")


def _verify_fast_forward(
    repo_root: Path, *, refetch: bool, on_fail_exit_code: int, is_fork: bool = False,
) -> None:
    """确保把当前 HEAD 推去 master 会是快进。不是快进时绝不强推，交人工处理。"""
    if refetch:
        _fetch(repo_root)
    check = _run_git(
        ["merge-base", "--is-ancestor", "origin/master", "HEAD"], repo_root, check=False,
    )
    if check.returncode != 0:
        raise SweepAbort(
            "⚠ 推送非快进（origin/master 不是当前 HEAD 的祖先，本地落后或已分叉）——"
            "跳过本轮，不强推、不自动 rebase。",
            exit_code=on_fail_exit_code,
            is_fork=is_fork,
        )


def _push_any_unpushed_commits(repo_root: Path, log: list[str], dry_run: bool = False) -> None:
    """队列 #194：起跑段无条件检查是否存在未推送的本地提交，不绑定"§二
    有无待处理批次"（正是这个绑定让 07-31/08-01 多次真实复现"本地已提交、
    下一轮判定'无待处理批次'直接空转，提交就此滞留"）。

    覆盖"任何一处 push 失败后的未推送提交"——已实证至少两个独立出口
    （批次主流程与 `_rerun_ledger` 台账重跑），本函数在起跑段统一兜底，
    不依赖具体是哪个出口造成的滞留。

    存在且可快进即先补推（推成功再继续本轮其余流程）；不可快进（已分叉）
    复用 #171 已建的分叉告警通道（`is_fork=True`，main() 据此触发
    `_handle_fork_detected`）+ `FORK_EXIT_CODE`，不强推、不自动 rebase；
    补推本身失败（网络/鉴权等）以 exit_code=2（人工介入语义）收尾——本地
    提交不会被撤销。"""
    _fetch(repo_root)
    ahead_raw = _run_git(["rev-list", "--count", "origin/master..HEAD"], repo_root).stdout.strip()
    ahead = int(ahead_raw) if ahead_raw.isdigit() else 0
    if ahead == 0:
        return
    check = _run_git(["merge-base", "--is-ancestor", "origin/master", "HEAD"], repo_root, check=False)
    if check.returncode != 0:
        raise SweepAbort(
            f"⚠ 起跑发现 {ahead} 个未推送的本地提交，且推送非快进"
            "（origin/master 不是当前 HEAD 的祖先，已分叉）——跳过本轮，不强推、不自动 rebase。",
            exit_code=FORK_EXIT_CODE,
            is_fork=True,
        )
    if dry_run:
        log.append(f"[dry-run] 起跑将补推 {ahead} 个此前未推送的本地提交（本次不实际 push）。")
        return
    push = _run_git(["push", "origin", "HEAD:refs/heads/master"], repo_root, check=False)
    if push.returncode != 0:
        raise SweepAbort(
            f"✗ 起跑发现 {ahead} 个未推送的本地提交，补推失败：{push.stderr.strip()}——"
            "本地提交不会被撤销，需人工核查后手动 push，本轮就此停止。",
            exit_code=2,
        )
    log.append(f"✓ 起跑补推 {ahead} 个此前未推送的本地提交。")


def _sync_master_if_behind_origin(repo_root: Path, log: list[str]) -> None:
    """本地 master 落后 origin/master 且可快进时自动追上（2026-07-28 补，见文件头部说明）。

    只处理"本地是 origin/master 祖先"（纯落后、直线历史）这一种情形；两边
    已分叉（互不为祖先）本函数不动手，交给后续 `_verify_fast_forward` 按
    既有语义告警跳过——不强推、不自动 rebase。假设调用方已在此之前 fetch
    过（本函数自身也会 fetch 一次，保证独立调用时行为完整）。
    """
    _fetch(repo_root)
    head = _run_git(["rev-parse", "HEAD"], repo_root).stdout.strip()
    origin_head = _run_git(["rev-parse", "origin/master"], repo_root).stdout.strip()
    if head == origin_head:
        return
    is_behind = _run_git(
        ["merge-base", "--is-ancestor", "HEAD", "origin/master"], repo_root, check=False,
    )
    if is_behind.returncode != 0:
        return  # 本地未落后（领先或已分叉），交后续 _verify_fast_forward 处理
    merge = _run_git(["merge", "--ff-only", "origin/master"], repo_root, check=False)
    if merge.returncode != 0:
        raise SweepAbort(
            f"⚠ 本地 master 落后 origin/master 但 --ff-only 合并失败"
            f"（{merge.stderr.strip()}）——跳过本轮，不强推、不 rebase。",
        )
    log.append(f"✓ 本地 master 落后 origin/master，已 git merge --ff-only 同步至 {origin_head[:7]}。")


def _flush_pending_lock_appends(repo_root: Path, log: list[str]) -> None:
    """队列 #192-A（主载体，每小时）：flush `pending_queue_lock_appends.jsonl`
    ——机器人因编辑锁占用被推迟的补录，此前只能"等下一条消息到达"才会
    重试，07-31 真实一例滞留 4 小时 2 分。

    走子进程调用独立脚本（见 `FLUSH_PENDING_LOCK_SCRIPT_REL`），不在 sweep
    自身进程内 `import aibot_service`/`zhuopin_platform`——本脚本刻意零
    依赖（见文件头部注释），多 worktree 共享全局 editable install 存在被
    静默劫持到别的 checkout 的风险，子进程隔离规避这一风险，也天然满足
    "flush 异常不得影响 sweep 主流程"（子进程崩溃不会传染到 sweep 自身）。

    必须在 sweep 自己取编辑锁的窗口之外调用——flush 内部会走一遍完整的
    `queue_git_sync.sync_after_archive`，同样要 acquire 编辑锁，若与
    `_strike_off_rows` 的持锁窗口重叠会构成重入；本函数固定排在批次处理
    之前调用（main() 接线顺序），不与之重叠。"""
    script = repo_root / FLUSH_PENDING_LOCK_SCRIPT_REL
    if not script.exists():
        return  # 本 checkout 未部署机器人服务（如独立测试环境），静默跳过
    result = subprocess.run(
        [sys.executable, str(script)], cwd=repo_root, capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode != 0:
        log.append(
            "⚠ pending_queue_lock_appends.jsonl flush 失败（不影响本轮批次处理）："
            f"{(result.stderr or result.stdout).strip()[:500]}"
        )
        return
    if result.stdout.strip():
        log.append(f"✓ pending 锁忙暂存 flush：{result.stdout.strip()}")


def _load_webhook_url(repo_root: Path) -> str | None:
    """读 `<repo_root>/.env` 的 `WECOM_WEBHOOK_URL`（同 `发企微.py::load_webhook`
    同款零依赖读法，唯一区别：找不到时返回 None 而非 sys.exit——告警发不出去
    不应让 sweep 本身失败退出，只应降级为"跳过告警、留痕"（见 `_handle_fork_detected`）。
    """
    env_path = repo_root / ENV_REL
    if not env_path.exists():
        return None
    prefix = WECOM_WEBHOOK_ENV_KEY + "="
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(prefix):
            url = line[len(prefix):].strip().strip('"').strip("'")
            if url:
                return url
    return None


def _send_wecom_markdown(webhook_url: str, content: str) -> None:
    """向企业微信群机器人推送 Markdown 消息（同 `发企微.py::send_markdown`
    同款纯标准库实现，本脚本刻意不 import `zhuopin_platform`——保持零依赖，
    不受多 worktree 共享全局 editable install 指向哪个 checkout 的影响）。
    """
    payload = json.dumps(
        {"msgtype": "markdown", "markdown": {"content": content}}, ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        webhook_url, data=payload, headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if result.get("errcode", 0) != 0:
        raise RuntimeError(f"企业微信推送失败 errcode={result.get('errcode')} errmsg={result.get('errmsg')}")


def _read_fork_state(repo_root: Path) -> dict:
    path = repo_root / FORK_STATE_REL
    if not path.exists():
        return {"consecutive": 0, "first_detected_at": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"consecutive": 0, "first_detected_at": None}
    if not isinstance(data, dict) or "consecutive" not in data:
        return {"consecutive": 0, "first_detected_at": None}
    return data


def _write_fork_state(repo_root: Path, state: dict) -> None:
    path = repo_root / FORK_STATE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _reset_fork_state(repo_root: Path) -> None:
    """分叉解除（前置检查转为通过）后清空连续计数——防止陈旧计数误导下一次
    真实分叉的"连续轮次"文案，也避免状态文件无限堆积历史分叉的旧数据。"""
    path = repo_root / FORK_STATE_REL
    if path.exists():
        path.unlink()


def _handle_fork_detected(repo_root: Path, log: list[str]) -> None:
    """分叉告警主流程（队列 #171）：更新连续轮次计数 + 尝试主动推送企微告警。
    告警发送失败（.env 缺失/网络异常/webhook 拒绝）只降级记日志，不向上抛出
    ——告警本身不应阻塞 sweep 正常返回其应有的（非 0）退出码。
    """
    state = _read_fork_state(repo_root)
    consecutive = int(state.get("consecutive") or 0) + 1
    first_detected_at = state.get("first_detected_at") or _now_utc_str()
    _write_fork_state(
        repo_root, {"consecutive": consecutive, "first_detected_at": first_detected_at},
    )

    local_head = _run_git(["rev-parse", "--short", "HEAD"], repo_root, check=False).stdout.strip() or "?"
    origin_head = _run_git(
        ["rev-parse", "--short", "origin/master"], repo_root, check=False,
    ).stdout.strip() or "?"

    if consecutive == 1:
        streak_note = f"首次检测到（{_now_utc_str()}）"
    else:
        streak_note = f"已连续第 {consecutive} 轮检测到（自 {first_detected_at} 起，仍未解除）"

    alert_text = (
        f"🔱 落库sweep 检测到主工作区与 origin/master 已分叉，{streak_note}。\n"
        f"本地 HEAD={local_head}，origin/master={origin_head}，均不是对方的祖先。\n"
        "需人工核实是否有并发提交冲突（如某次推送恰好落在本次 sweep 运行窗口内），"
        "不会自动强推/rebase，详见 reports/sweep-commit.log。"
    )
    log.append(f"🔱 分叉告警：{streak_note}（本地 {local_head} / origin {origin_head}）")

    webhook_url = _load_webhook_url(repo_root)
    if webhook_url is None:
        log.append("⚠ 未在 .env 找到 WECOM_WEBHOOK_URL，跳过分叉告警推送（仅留痕日志与状态文件）。")
        return
    try:
        _send_wecom_markdown(webhook_url, alert_text)
    except Exception as exc:  # noqa: BLE001 —— 告警失败不应影响 sweep 自身退出码
        log.append(f"⚠ 分叉告警推送失败（不影响本轮退出码）：{exc}")
        return
    log.append(f"✓ 分叉告警已推送（连续第 {consecutive} 轮）。")


def _touches_resident_service(paths: set[str]) -> bool:
    return any(p.startswith(RESIDENT_SERVICE_PATH_PREFIXES) for p in paths)


def _announce_resident_service_deployment_hint(repo_root: Path, log: list[str]) -> None:
    """队列 #198(c)：本轮 commit 命中常驻服务路径时，在日志与 webhook 附一句
    部署提示——纯提示、不阻断、不改变本轮退出码（sweep 无权也不该去重启
    服务）。成因＝"代码已提交但生产未生效"的失配长期全靠人记得（#126／
    #193 同族），本提示只负责把这件事说出来。"""
    hint = (
        "⚠ 本批改动涉及常驻服务，需 sync-to-server.ps1 同步 ops/wecom-service-home "
        "并重启 ZhuopinAibotDevListener 后才在生产生效"
    )
    log.append(hint)
    webhook_url = _load_webhook_url(repo_root)
    if webhook_url is None:
        log.append("⚠ 未在 .env 找到 WECOM_WEBHOOK_URL，跳过部署提示推送（仅留痕日志）。")
        return
    try:
        _send_wecom_markdown(webhook_url, f"🔧 落库sweep：{hint}")
    except Exception as exc:  # noqa: BLE001 —— 提示推送失败不应影响本轮退出码
        log.append(f"⚠ 部署提示推送失败（不影响本轮退出码）：{exc}")
        return
    log.append("✓ 常驻服务部署提示已推送。")


def _status_paths(repo_root: Path) -> list[str]:
    """解析 `git status --porcelain=v1 --untracked-files=all` 为脏路径清单（重命名取新路径）。"""
    result = _run_git(["status", "--porcelain=v1", "--untracked-files=all"], repo_root)
    paths = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        rest = line[3:]
        if " -> " in rest:
            rest = rest.split(" -> ", 1)[1]
        paths.append(rest.strip('"'))
    return paths


def _parse_section_two(queue_text: str) -> list[dict]:
    """解析队列 §二"待 commit 批次"表格，返回每行的原始文本+四列内容。"""
    start = queue_text.find(SECTION_TWO_HEADING)
    if start == -1:
        return []
    rest = queue_text[start + len(SECTION_TWO_HEADING):]
    next_heading = rest.find("\n" + NEXT_SECTION_PREFIX)
    section = rest if next_heading == -1 else rest[:next_heading]

    rows = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) != 4:
            continue
        if cells[0] in ("批次", ""):
            continue
        if set(cells[0]) <= {"-", " "}:
            continue  # 分隔行 |------|------|...|
        rows.append({
            "raw_line": line,
            "batch_id": cells[0],
            "files_cell": cells[1],
            "message_cell": cells[2],
            "status_cell": cells[3],
        })
    return rows


def _classify_section_two_rows(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """按状态列文本把 §二 行分类为 (待处理, 模糊状态)（2026-07-28 补，见文件头部说明）。

    显式判据：
    - 状态列含"待"字样 → 待处理，纳入本轮（不论是否同时误带"✅"——登记方
      按惯例应避免带✅，但即便带了也不能让批次因此石沉大海）。
    - 状态列既不含"✅"也不含"待" → 模糊状态，不纳入本轮，但调用方必须把它
      写进日志（宁可吵不可哑），不能像"未命中待"一样被默默略过。
    - 状态列只含"✅"、不含"待" → 视为已完成，两个返回列表都不包含，无需告警。
    """
    pending = [r for r in rows if "待" in r["status_cell"]]
    ambiguous = [r for r in rows if "✅" not in r["status_cell"] and "待" not in r["status_cell"]]
    return pending, ambiguous


def _extract_commit_message(message_cell: str) -> str:
    match = re.search(r"`([^`]+)`", message_cell)
    return match.group(1) if match else message_cell.strip()


def _resolve_batch_files(files_cell: str, dirty_paths: list[str]) -> tuple[list[str], list[str], list[str]]:
    """把批次"文件清单"列里反引号标出的每个片段，对到 git status 里实际的脏路径。

    不去猜测"§二 表格里的路径默认省略 1-转型规划/ 前缀、写"根"才是仓库根相对"这类
    约定——直接拿片段去匹配当前真实脏路径的**后缀**（`dirty_path == frag` 或
    `dirty_path.endswith("/" + frag)`），天然兼容"根 CLAUDE.md"与省略前缀两种写法，
    且只会对到真实存在的脏文件,不会凭空造出一个不存在的 add 目标。

    返回 (resolved, not_dirty, ambiguous)：
      resolved   — 恰好命中 1 个脏路径的片段，对应的真实路径（用于 git add）
      not_dirty  — 0 个命中（可能已被别处提交，见"遗留尾巴"处置）
      ambiguous  — 命中 ≥2 个脏路径（无法安全判定，本片段对应的候选路径会
                   保留在全局脏路径集合里，从而让上层"非 clean"整体门禁自然拦截，
                   不需要在此单独报错）
    """
    fragments = re.findall(r"`([^`]+)`", files_cell)
    resolved, not_dirty, ambiguous = [], [], []
    for frag in fragments:
        matches = [d for d in dirty_paths if d == frag or d.endswith("/" + frag)]
        if len(matches) == 1:
            resolved.append(matches[0])
        elif len(matches) == 0:
            not_dirty.append(frag)
        else:
            ambiguous.append(frag)
    return resolved, not_dirty, ambiguous


def _edit_lock(repo_root: Path, action: str, extra: list[str] | None = None) -> subprocess.CompletedProcess:
    # 队列 #198(b)：`status` 子命令不接受 `--who`（无副作用查询，不需要
    # 身份）——传了会被 argparse 当"unrecognized arguments"直接拒绝（exit
    # code 2），故只在 acquire/release 这两个需要身份的动作上带 --who。
    args = [sys.executable, str(repo_root / EDIT_LOCK_SCRIPT_REL), action]
    if action != "status":
        args.extend(["--who", LOCK_WHO])
    if extra:
        args.extend(extra)
    return subprocess.run(args, cwd=repo_root, capture_output=True, text=True, encoding="utf-8")


def _edit_lock_is_actively_held(status_stdout: str) -> bool:
    """解析 `工具-共享文档编辑锁.py status` 的 stdout，判断锁当前是否被
    有效持有（队列 #198(b)）。该工具三种输出态中，只有"占用中且未陈旧"
    才含"（有效）"三字（见 `cmd_status`）——无锁态是"（无锁，可直接编辑）"，
    陈旧态是"已陈旧（可接管）"，均不含"（有效）"。陈旧锁本轮不必因此跳过
    ——后续 `_strike_off_rows` 自身的 acquire 调用会自动接管陈旧锁，探锁
    这一步只需要拦住"确实有人/有机器人正在编辑"这一种情形。"""
    return "（有效）" in status_stdout


def _abort_if_edit_lock_held(repo_root: Path, log: list[str]) -> None:
    """队列 #198(b)：起跑段编辑锁前置探测，须排在 `_check_preconditions`
    之后、任何 git 写动作之前——占用中直接跳过本轮、一个 git 动作都不做。

    现状（修复前）：`_process_normal_batch` 先 `git add` 再由
    `_strike_off_rows` 去 acquire 锁，锁占用时暂存区里已经是半成品；本函数
    把探测提到最前面，锁占用时连第一个 `git add` 都不会发生。"""
    result = _edit_lock(repo_root, "status")
    if _edit_lock_is_actively_held(result.stdout):
        raise SweepAbort(
            f"⚠ 起跑探测到共享编辑锁被有效占用中，跳过本轮，零 git 动作：{result.stdout.strip()}",
        )


def _replace_status_cell(raw_line: str, old_status_cell: str, new_status_cell: str) -> str:
    """只替换该行"状态"这一列的内容，其余原样保留（不重排空白、不动其他三列）。"""
    idx = raw_line.rfind("| " + old_status_cell + " |")
    if idx != -1:
        return raw_line[:idx] + "| " + new_status_cell + " |" + raw_line[idx + len("| " + old_status_cell + " |"):]
    # 空白格式不完全一致时退化为窄匹配，仍要求原样保留其余三列
    idx = raw_line.rfind(old_status_cell)
    if idx == -1:
        raise SweepAbort(f"✗ 无法在原始行中定位状态列文本，拒绝改写：{raw_line!r}", exit_code=1)
    return raw_line[:idx] + new_status_cell + raw_line[idx + len(old_status_cell):]


def _now_utc_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _read_queue(repo_root: Path) -> str:
    with open(repo_root / QUEUE_REL, "r", encoding="utf-8", newline="") as f:
        return f.read()


def _write_queue(repo_root: Path, text: str) -> None:
    with open(repo_root / QUEUE_REL, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def _strike_off_rows(
    repo_root: Path, rows: list[dict], new_status_fn, lock_note: str, dry_run: bool,
) -> bool:
    """对给定行批量替换状态列并写回队列文件；调用方负责 add/commit。返回是否真的改了内容。"""
    if dry_run:
        for row in rows:
            print(f"  [dry-run] 将标记 {row['batch_id']} → {new_status_fn(row)}")
        return True

    lock = _edit_lock(repo_root, "acquire", ["--note", lock_note])
    if lock.returncode != 0:
        raise SweepAbort(f"⚠ 编辑锁占用中，跳过本轮：{lock.stdout.strip()}")
    try:
        text = _read_queue(repo_root)
        for row in rows:
            new_line = _replace_status_cell(row["raw_line"], row["status_cell"], new_status_fn(row))
            if row["raw_line"] not in text:
                raise SweepAbort(
                    f"✗ 队列文件内容已变化，找不到批次 {row['batch_id']} 的原始行——"
                    "可能被并发编辑，跳过本轮不强写。",
                )
            text = text.replace(row["raw_line"], new_line, 1)
        _write_queue(repo_root, text)
        return True
    finally:
        _edit_lock(repo_root, "release")


def _process_normal_batch(repo_root: Path, row: dict, resolved_files: list[str], dry_run: bool, log: list[str]) -> None:
    batch_id = row["batch_id"]
    if dry_run:
        print(f"[dry-run] 批次 {batch_id}：会 git add {resolved_files}，"
              f"提交信息「{_extract_commit_message(row['message_cell'])}」，标记销行后 push。")
        log.append(f"[dry-run] {batch_id} 待落库：{resolved_files}")
        return

    _run_git(["add", "--", *resolved_files], repo_root)

    new_status = f"**✅ 已完成**（sweep 自动落库 {_now_utc_str()}）"
    _strike_off_rows(repo_root, [row], lambda r: new_status, f"sweep 落库 {batch_id}", dry_run=False)
    _run_git(["add", "--", QUEUE_REL], repo_root)

    message = _extract_commit_message(row["message_cell"])
    _run_git(["commit", "-m", message], repo_root)
    sha = _run_git(["rev-parse", "--short", "HEAD"], repo_root).stdout.strip()

    try:
        _verify_fast_forward(repo_root, refetch=True, on_fail_exit_code=2)
    except SweepAbort as exc:
        # 到这一步本地提交已经做完——比通用的 _verify_fast_forward 消息更进一步，
        # 明确告知"有一个不会被撤销的本地提交在等人工处理"，而不是泛泛的"跳过"。
        raise SweepAbort(
            f"✗ 批次 {batch_id} 本地已提交（{sha}）但{str(exc)}"
            "本地提交不会被撤销，需人工核查后手动 push 或走 cherry-pick 路线，本轮就此停止。",
            exit_code=2,
        ) from exc
    push = _run_git(["push", "origin", "HEAD:refs/heads/master"], repo_root, check=False)
    if push.returncode != 0:
        raise SweepAbort(
            f"✗ 批次 {batch_id} 本地已提交（{sha}）但推送失败：{push.stderr.strip()}——"
            "本地提交不会被撤销，需人工核查后手动 push 或走 cherry-pick 路线，本轮就此停止。",
            exit_code=2,
        )
    log.append(f"✓ 批次 {batch_id} 已落库并推送（{sha}）")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="只打印计划动作，不 add/commit/push/改队列")
    parser.add_argument("--repo-root", default=None, help="仅测试用：覆盖主工作区路径断言")
    args = parser.parse_args()

    repo_root = _resolve_repo_root(args.repo_root)
    log: list[str] = [f"=== sweep 运行 {_now_utc_str()} ==="]

    try:
        _heal_stale_index_lock(repo_root, log)
        _check_preconditions(repo_root, production=args.repo_root is None)
        # 队列 #192/#194/#198 起跑段写死顺序（勿自行调整，详见各函数 docstring）：
        # ① #198(b) 编辑锁前置探测（任何 git 写动作之前）
        _abort_if_edit_lock_held(repo_root, log)
        # ② #194 无条件补推未推送提交
        _push_any_unpushed_commits(repo_root, log, dry_run=args.dry_run)
        # ③ #192-A flush 锁忙推迟暂存（须在 sweep 自己取锁窗口之外，此处
        #   批次处理尚未开始，安全）；dry-run 不做真实动作，避免副作用。
        if not args.dry_run:
            _flush_pending_lock_appends(repo_root, log)
        # ④ 原有前置检查与批次处理
        _sync_master_if_behind_origin(repo_root, log)
        _verify_fast_forward(repo_root, refetch=False, on_fail_exit_code=FORK_EXIT_CODE, is_fork=True)
        if not args.dry_run:
            _reset_fork_state(repo_root)  # 前置检查通过=未分叉，清空任何陈旧的连续计数

        dirty_paths = _status_paths(repo_root)
        queue_text = _read_queue(repo_root)
        rows = _parse_section_two(queue_text)
        pending_rows, ambiguous_status_rows = _classify_section_two_rows(rows)
        for row in ambiguous_status_rows:
            log.append(
                f"⚠ 状态列模糊（既不含✅也不含待字样），未纳入本轮处理，人工核查："
                f"{row['batch_id']} | {row['status_cell']}"
            )

        if not pending_rows:
            log.append("§二无待处理批次，本轮空转。")
            _flush_log(repo_root, log, args.dry_run)
            print("\n".join(log))
            return 0

        declared_all: set[str] = set()
        row_resolution = {}
        for row in pending_rows:
            resolved, not_dirty, ambiguous = _resolve_batch_files(row["files_cell"], dirty_paths)
            row_resolution[row["batch_id"]] = (resolved, not_dirty, ambiguous)
            declared_all.update(resolved)

        unaccounted = [p for p in dirty_paths if p not in declared_all]
        if unaccounted:
            log.append("⚠ 非 clean：以下脏路径不属于任何待 commit 批次声明，跳过本轮：")
            log.extend(f"    - {p}" for p in unaccounted)
            _flush_log(repo_root, log, args.dry_run)
            print("\n".join(log))
            return 0

        straggler_rows = []
        normal_rows = []
        for row in pending_rows:
            resolved, not_dirty, ambiguous = row_resolution[row["batch_id"]]
            if ambiguous:
                # 理论上应已被 unaccounted 拦截；防御性兜底，不在此处强行判断。
                continue
            if resolved:
                normal_rows.append((row, resolved))
            elif not_dirty:
                straggler_rows.append(row)

        touched_paths: set[str] = set()
        for row, resolved in normal_rows:
            _process_normal_batch(repo_root, row, resolved, args.dry_run, log)
            touched_paths.update(resolved)

        if straggler_rows:
            ids = "/".join(r["batch_id"] for r in straggler_rows)
            note = f"✓ 补销遗留尾巴批次 {ids}"
            if args.dry_run:
                print(f"[dry-run] {note}")
                log.append(f"[dry-run] {note}")
            else:
                new_status = f"**✅ 已完成**（sweep 自动补销遗留尾巴 {_now_utc_str()}，未发现对应待落库改动）"
                _strike_off_rows(repo_root, straggler_rows, lambda r: new_status,
                                  f"sweep 补销尾巴 {ids}", dry_run=False)
                _run_git(["add", "--", QUEUE_REL], repo_root)
                _run_git(["commit", "-m", f"docs(队列): sweep 补销遗留尾巴批次 {ids}"], repo_root)
                _verify_fast_forward(repo_root, refetch=True, on_fail_exit_code=2)
                push = _run_git(["push", "origin", "HEAD:refs/heads/master"], repo_root, check=False)
                if push.returncode != 0:
                    raise SweepAbort(f"✗ 补销尾巴提交推送失败：{push.stderr.strip()}", exit_code=2)
                log.append(note)

        processed_any = bool(normal_rows) or bool(straggler_rows)
        if processed_any and not args.dry_run:
            _rerun_ledger(repo_root, log)

        # #198(c)：批次落库之后，检查本轮实际 add 过的路径是否命中常驻服务——
        # 纯提示，不影响下方的正常返回。
        if touched_paths and not args.dry_run and _touches_resident_service(touched_paths):
            _announce_resident_service_deployment_hint(repo_root, log)

        _flush_log(repo_root, log, args.dry_run)
        print("\n".join(log))
        return 0

    except SweepAbort as exc:
        log.append(str(exc))
        if exc.is_fork and not args.dry_run:
            _handle_fork_detected(repo_root, log)
        _flush_log(repo_root, log, args.dry_run)
        print("\n".join(log))
        return exc.exit_code

    except Exception as exc:  # noqa: BLE001 —— 队列 #198(a) 通用异常兜底
        # main() 此前只有 `except SweepAbort`，任何其它异常（子进程异常/
        # 编码错误/FileNotFoundError 等）会直接冒泡，_flush_log 根本没机会
        # 执行——sweep-commit.log 零新增行，与"任务根本没启动"外观完全相同
        # （#96 清单 ⑦判据据此失效）。本层兜底后，日志零新增行只剩一个
        # 含义："任务根本没启动"；"跑了但崩了"改为走这里，有日志+告警+
        # 独立退出码，判据恢复单义（见 #198(a) 验收物）。
        tb_tail = traceback.format_exc().strip().splitlines()[-6:]
        log.append(f"✗ 未预期异常（{_now_utc_str()}）：{type(exc).__name__}: {exc}")
        log.extend(f"    {line}" for line in tb_tail)
        if not args.dry_run:
            webhook_url = _load_webhook_url(repo_root)
            if webhook_url is None:
                log.append("⚠ 未在 .env 找到 WECOM_WEBHOOK_URL，跳过未预期异常告警推送（仅留痕日志）。")
            else:
                try:
                    _send_wecom_markdown(
                        webhook_url,
                        f"🔱 落库sweep 遇到未预期异常：{type(exc).__name__}: {exc}\n"
                        "详见 reports/sweep-commit.log。",
                    )
                    log.append("✓ 未预期异常告警已推送。")
                except Exception as send_exc:  # noqa: BLE001 —— 告警失败不应影响退出码
                    log.append(f"⚠ 未预期异常告警推送失败（不影响本轮退出码）：{send_exc}")
        try:
            _flush_log(repo_root, log, args.dry_run)
        except Exception:  # noqa: BLE001 —— 日志落盘本身失败也不应掩盖原始异常的退出码
            pass
        print("\n".join(log))
        return UNEXPECTED_EXIT_CODE


def _rerun_ledger(repo_root: Path, log: list[str]) -> None:
    result = subprocess.run(
        [sys.executable, str(repo_root / LEDGER_SCRIPT_REL)],
        cwd=repo_root, capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode != 0:
        log.append(f"⚠ 台账重跑失败（不影响已落库批次）：{result.stderr.strip()}")
        return
    changed = _run_git(["status", "--porcelain=v1", "--", LEDGER_OUTPUT_REL], repo_root).stdout.strip()
    if not changed:
        log.append("台账重跑：内容无变化，不产生新 commit。")
        return
    _run_git(["add", "--", LEDGER_OUTPUT_REL], repo_root)
    _run_git(["commit", "-m", "docs(队列): 收工重跑文档台账（sweep 自动）"], repo_root)
    _verify_fast_forward(repo_root, refetch=True, on_fail_exit_code=2)
    push = _run_git(["push", "origin", "HEAD:refs/heads/master"], repo_root, check=False)
    if push.returncode != 0:
        raise SweepAbort(f"✗ 台账重跑提交推送失败：{push.stderr.strip()}", exit_code=2)
    log.append("✓ 台账已重跑并推送。")


def _flush_log(repo_root: Path, log: list[str], dry_run: bool) -> None:
    if dry_run:
        return
    log_path = repo_root / LOG_REL
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(log) + "\n\n")


if __name__ == "__main__":
    raise SystemExit(main())
