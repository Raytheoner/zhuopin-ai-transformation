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

批次文件匹配精确相等优先（队列 #234(1)，2026-08-04 值周巡检取证）：
`_resolve_batch_files` 原按后缀匹配（`d == frag or d.endswith("/" + frag)`）
把片段对到脏路径，同名文件出现在两处时（如根 `CLAUDE.md` 与某场景目录下
也有一份 `CLAUDE.md`）会各算一次命中而判 ambiguous——即便其中一个是精确
相等，也会被同一片段的其它候选连累，导致早已正确声明的批次被
`unaccounted` 全局门槛一并跳过（08-04 实测 20 批积压）。现改为存在精确
相等命中时唯一采用它，不再把同一轮的后缀命中一并计入歧义；无精确命中
时仍按原逻辑处理（≥2 个后缀命中依然判 ambiguous，安全边界不变）。

启动即写日志首行（队列 #222，2026-08-04）：main() 起跑最开头（`_heal_
stale_index_lock` 等任何有风险的代码执行之前）就把"=== sweep 运行 ... ==="
这一行单独落盘一次，不再等到收尾统一 flush——否则"启动后立刻发生连
`except Exception` 都接不住的崩溃"与"计划任务压根没触发"在日志上表现
完全相同（`sweep-commit.log` 均无新内容），判据失去分辨力（#121(b) 遗留
未做项）。此后各退出路径改用 `_flush_remaining_log`，只落盘首行之后
新增的内容，不重复写入这一行。

决策提醒第二载体（队列 #219，2026-08-04）：`ZhuopinDecisionReminderDaily`
是决策提醒的唯一载体——每日仅一次、需已登录、错过不补、失败无告警，
2026-08-03 真实丢过一轮。起跑段新增 `_run_decision_reminder_second_
carrier`，走子进程调用 `decision_reminder_check.py`（每小时随 sweep 一并
触发，去重沿用其自身既有 `ESCALATION_INTERVALS_DAYS`，双载体不会重复
打扰），须排在 sweep 自己取编辑锁窗口之外（main() 接线固定顺序，见其内
注释）。

批次隔离——unaccounted 从"全局门"改为"逐批次判定"（队列 #238，合并
#234(2) 与 #230-2d，2026-08-05）：原实现只要 `git status` 里存在一个不属于
任何批次声明的脏路径，`main()` 就整轮 `return 0`——已正确声明、彼此毫无
关系的批次被连带跳过（08-04 实测 17-20 批积压，堵点常常只有几个真文件，
详见 #234/#236 取证）。改为 `_partition_pending_rows_by_batch_isolation`：
一个批次是否被阻塞，只取决于它**自己**的声明片段解析是否命中
`ambiguous`（即该片段在当前脏路径中有 ≥2 个候选、且无精确相等命中，见
`_resolve_batch_files` 队列 #234(1)）——`ambiguous` 片段对应的候选路径
必然不在 `declared_all` 里，这正是"声明片段与未声明脏文件有交集"的精确
含义。与它无关的其它批次不受影响，照常落库；被阻塞的批次逐条写明因
哪个片段命中几处候选而暂缓（可解释日志，回应 #234 附带要求：08-03 本
项目正因缺这行日志而误判为 bug、白花一轮取证）。真正"没人声明"的孤儿
脏文件（不出现在任何批次的 resolved 或 ambiguous 候选里）不阻塞任何
批次，只作为独立提示列出——持续存在则交给 #236(2) 的孤儿脏文件告警去
处理，sweep 主流程本身不再因它们停摆。

孤儿脏文件告警（队列 #236(2)，2026-08-05）：#238 解除"孤儿阻塞全局"后，
孤儿脏文件仍需要"被人看见"——2026-08-04 实测 4 个无主孤儿文件（原
session 随 Claude Desktop 重启失联）挡住 20 个批次跨天不落库，根因是
"收工登记批次没有触发点"（协议〇.1/〇.3 要求认领即声明，但回合制
session 没有回合可用来执行）；sweep 只说"不属于任何批次声明"，既不
追溯也不告警。`_track_and_alert_orphan_paths` 持久化每个孤儿路径的
首次发现时刻（`reports/sweep-orphan-state.json`），超过
`ORPHAN_ALERT_THRESHOLD_HOURS` 才复用 #171 的 webhook 通道点名一次，
此后每满一个阈值周期再提醒一次（不逐轮/每小时重复打扰——#147
`gap_alert` 的"狼来了"教训：过密提醒会被无视）；孤儿一旦被声明或消失
即从状态里清除。

发布收口第②关：部署留痕检查（队列 #229，Shao Peishen 2026-08-03 拍板
选 (a)，2026-08-05）：同族本周复发三次的"收口最后一段没人记得"——#204
问题已解决但载体未更正／#221 代码未并 master 而生产已部署／#228 通知
已送达而生产未更新。`_find_missing_deployment_trace` 在批次落库后检查
本轮 touched_paths 是否命中已部署场景白名单（初版宁窄勿宽，仅
SC8/QD-B/FI2 三场景目录 + 命令中心，判据落在各自 CLAUDE.md／仓库根
CLAUDE.md 是否同批改动这一可机检事实，不解析内容语义、不判断"是否
真的部署了"），命中且未见留痕即在日志与 webhook 附一句提示——纯提示，
不阻断、不改退出码（同 #198(c) 范式）。

判据锚定状态列开头片段（队列 #248，openspec 变更包
`sweep-editlock-status-keyword-anchoring`，2026-08-05）：2026-07-28 那次
"批次判据显式化"修法（见上）解决了"状态列误带✅"，但仍是对整个状态列做
子串扫描——#248 真实事故：一条状态列开头是`✅ 已完成`、但说明文字里引用
了本判据原文（含"待"字）的批次被误判为待处理，取活提交、覆写了原说明。
改为只依据 `_leading_status_segment()` 返回的"开头片段"（状态列去除前导
`*`/空白后、第一个句级分隔符"。"/"——"/"━━━"之前的文本）判定，分隔符
之后的说明/引用/复述文字不再参与判定。**为什么不是简单地"只看第一个
字符"**：现存回归测试固化的 2026-07-27 真实误写场景——"✅ 已完成（本次
登记，待 sweep 落库）"——"待"字紧跟在同一个短促、无分隔符的括注里，若
把"开头"收窄到"第一个字符"会让这条误写重新被判成"已完成"而漏处理，
等于用本次修法重新引入 2026-07-28 要根治的旧问题；用句级分隔符界定
"开头片段"边界，两个真实事故场景（本次 #248 与 2026-07-27 旧误写）均已
用回归测试固化验证不冲突，见 `_leading_status_segment()` 与
`ClassifySectionTwoRowsUnitTests`。同批同源修法见编辑锁 ④断言门槛
（`工具-共享文档编辑锁.py` 的 `QUOTED_SPAN_RE`）——两处判据历史上都经历
过"整行扫描→只查状态列"这一次收窄，本次是该收窄路径的下一步，但两处
的具体实现不同（本处锚定开头，编辑锁排除引号片段），design.md 完整
论证了原因（sweep 状态列是短符号前缀，编辑锁状态列是多分句长叙述，
"只看开头"这一具体规则对后者不成立）。

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

# 队列 #219：决策提醒第二载体——原 `ZhuopinDecisionReminderDaily` 是唯一
# 载体，每日仅一次、需已登录、错过不补、失败无告警，2026-08-03 真实丢过
# 一轮。同 `FLUSH_PENDING_LOCK_SCRIPT_REL` 一样走子进程隔离（零依赖设计，
# async 边界完全留在子进程内，sweep 自身不需要 `asyncio.run()`）。
DECISION_REMINDER_SCRIPT_REL = (
    "5-平台底座/wecom-aibot-service/scripts/decision_reminder_check.py"
)
DECISION_REMINDER_TIMEOUT_SECONDS = 120

# 队列 #198(c)：本轮 commit 若命中这些前缀下的路径，视为"涉常驻服务"，
# 需部署脚本同步+重启对应计划任务才在生产生效（现状全靠人记得）。
RESIDENT_SERVICE_PATH_PREFIXES = ("5-平台底座/wecom-aibot-service/",)

# 队列 #236(2)：孤儿脏文件（不属于任何批次声明）状态持久化 + 告警阈值。
# 与 sweep 每小时一轮对齐，约 3 轮仍孤儿才点名，避免"批次登记与实际改动
# 之间几分钟时间差"这类偶发情形被误报（#147 gap_alert 的"狼来了"教训）。
ORPHAN_STATE_REL = "reports/sweep-orphan-state.json"
ORPHAN_ALERT_THRESHOLD_HOURS = 3

# 队列 #229：发布收口第②关——已部署场景白名单（初版宁窄勿宽）。
# key＝场景目录前缀，value＝该场景的部署留痕文件——本批 touched_paths 命中
# 前缀下的其它文件、但未同时命中这个留痕文件，即视为"未见留痕"。命令中心
# （AI运营指挥中心）没有独立场景 CLAUDE.md，其部署历史落在仓库根 CLAUDE.md，
# 沿用同一判据（宁可因根 CLAUDE.md 被顺手一并改动而漏报，也不误报）。
DEPLOYED_SCENARIO_PREFIXES = {
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/":
        "4-数字员工/采购部/SC8-客户订单交期智能承诺/CLAUDE.md",
    "4-数字员工/质量部/QD-B-立项审核门禁/":
        "4-数字员工/质量部/QD-B-立项审核门禁/CLAUDE.md",
    "4-数字员工/财务部/FI2-三单匹配自动对账/":
        "4-数字员工/财务部/FI2-三单匹配自动对账/CLAUDE.md",
    "1-转型规划/AI运营指挥中心/": "CLAUDE.md",
}


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


def _run_decision_reminder_second_carrier(repo_root: Path, log: list[str]) -> None:
    """队列 #219：决策提醒第二载体（每小时，随 sweep 一并触发）。

    背景：`ZhuopinDecisionReminderDaily` 是唯一载体——每日仅一次、需
    `LogonType=Interactive`（要求已登录）、错过不补（`NumberOfMissedRuns`
    不会自动补跑）、失败无任何告警。2026-08-03 真实丢了一轮（机器在 08:30
    触发窗口处于休眠恢复中），直到环境保障线手工核查才发现。判定逻辑本身
    （`decision_reminder.py::evaluate_candidates`）已用 `ESCALATION_INTERVALS_
    DAYS` 去重，双载体同一天各调一次不会重复打扰，故可安全复用、不改判据。

    走独立子进程调用 `scripts/decision_reminder_check.py`（与 #192-A
    `_flush_pending_lock_appends` 同一理由：本脚本刻意不 import
    `aibot_service`/`zhuopin_platform`，规避多 worktree 共享 editable
    install 被静默劫持到别的 checkout 的风险；async 事件循环边界因此完全
    留在子进程内，sweep 自身不需要 `asyncio.run()`——用进程隔离满足"async
    边界"这条实现约束，而非在 sweep 内直接 import 该异步函数）。

    **须在 sweep 自己的编辑锁窗口之外调用**（实现约束①）：被调脚本内部会
    走一遍 `queue_git_sync`/编辑锁 flush（同 #192-A 第二道载体），与
    `_strike_off_rows` 的持锁窗口重叠会构成重入；main() 接线固定排在批次
    处理开始之前调用，不与之重叠。

    路径解析走被调脚本自身的 `resolve_repo_root()`（#126）——本函数只按
    绝对路径 `repo_root / DECISION_REMINDER_SCRIPT_REL` 调用，不额外硬编码
    `SERVICE_DIR/reports` 之类的路径（实现约束④）。

    异常（含超时）必须捕获+记日志（标 UTC）后继续跑主流程，不得把 sweep
    带崩（实现约束③）。"""
    script = repo_root / DECISION_REMINDER_SCRIPT_REL
    if not script.exists():
        return  # 本 checkout 未部署机器人服务（如独立测试环境），静默跳过
    try:
        result = subprocess.run(
            [sys.executable, str(script)], cwd=repo_root, capture_output=True,
            text=True, encoding="utf-8", timeout=DECISION_REMINDER_TIMEOUT_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001 —— 第二载体失败不得影响 sweep 主流程
        log.append(
            f"⚠ 决策提醒第二载体调用异常（{_now_utc_str()}，不影响本轮批次处理）：{exc}"
        )
        return
    if result.returncode != 0:
        log.append(
            f"⚠ 决策提醒第二载体退出码 {result.returncode}（{_now_utc_str()}，不影响本轮批次处理）："
            f"{(result.stderr or result.stdout).strip()[:500]}"
        )
        return
    stdout = result.stdout.strip()
    if stdout and "无新增/超期决策项" not in stdout:
        log.append(f"✓ 决策提醒第二载体：{stdout.splitlines()[-1]}")


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


# 队列 #248（2026-08-05）：判据锚定状态列"开头片段"——见 _leading_status_segment()。
# 前导字符剥离集合：半角 `*`（含单/双星号强调）、半角空格、制表符、全角空格
# （U+3000，中文输入法环境下的防御性收纳，现存行未实测命中但成本近零）。
LEADING_STRIP_CHARS = "* \t　"
# 界定"开头片段"边界的句级分隔符——现存生产队列文件里"。"996 次、"——"573 次、
# "━━━"199 次，是稳定且高频的句/段落分隔惯例，用其中最早出现的一个切开状态列，
# 分隔符之前的文本视为"当前生效结论"，之后的文本（多为补充说明/引用/复述）不参与判定。
LEADING_SEGMENT_SEPARATORS = ("。", "——", "━━━")


def _leading_status_segment(status_cell: str) -> str:
    """返回状态列去除前导强调符/空白后、第一个句级分隔符之前的"开头片段"。

    队列 #248 真实事故：sweep 把一条状态列开头是 `✅ 已完成`、但说明文字里
    引用了判据原文（含"待"字）的 §二 批次误判为待处理，取活提交、覆写了
    原说明（详见 openspec 变更包 `sweep-editlock-status-keyword-anchoring`）。

    **为什么边界不是"第一个字符"而是"第一个句级分隔符之前"**：现存回归测试
    （`ClassifySectionTwoRowsUnitTests::test_classifies_four_status_forms`）
    固化了一个 2026-07-27 实测事故的防御用例——登记方误写"✅ 已完成（本次
    登记，待 sweep 落库）"，"待"字紧跟在同一个不含任何句级分隔符的短括注
    里，若把"开头"收窄到"第一个字符"（即只看 `✅`），会让这条误写被判成
    "已完成"而漏处理，正是 2026-07-28 那次判据修法要根治的问题——等于用
    #248 的修法重新引入 2026-07-27 的旧事故。用句级分隔符（句号/破折号/
    分隔线）界定"开头片段"，既能保留这类短促、无分隔符的误写场景里"待"
    仍被检出，又能把 #248 那种"完成标记后另起一段引用/说明"的长文本排除
    在判定范围之外——已用现存生产队列文件全部 §二 行 + 本函数下方四个
    回归用例验证一致，见 openspec 变更包 design.md「历史兼容核对」。
    """
    stripped = status_cell.lstrip(LEADING_STRIP_CHARS)
    cut = len(stripped)
    for sep in LEADING_SEGMENT_SEPARATORS:
        idx = stripped.find(sep)
        if idx != -1:
            cut = min(cut, idx)
    return stripped[:cut]


def _classify_section_two_rows(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """按状态列"开头片段"把 §二 行分类为 (待处理, 模糊状态)（队列 #248 改判据
    锚定范围，2026-07-28 版判据见文件头部说明"批次判据显式化"一节）。

    显式判据（均只依据 `_leading_status_segment()` 返回的开头片段，不再对
    开头片段之后的文本做任何匹配）：
    - 开头片段含"待"字样 → 待处理，纳入本轮（不论是否同时误带"✅"——登记方
      按惯例应避免带✅，但即便带了也不能让批次因此石沉大海）。
    - 开头片段既不含"✅"也不含"待" → 模糊状态，不纳入本轮，但调用方必须把它
      写进日志（宁可吵不可哑），不能像"未命中待"一样被默默略过。
    - 开头片段只含"✅"、不含"待" → 视为已完成，两个返回列表都不包含，无需告警。
    """
    pending, ambiguous = [], []
    for r in rows:
        leading = _leading_status_segment(r["status_cell"])
        if "待" in leading:
            pending.append(r)
        elif "✅" not in leading:
            ambiguous.append(r)
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

    队列 #234(1)（2026-08-04 值周巡检取证）：**精确相等优先**——若脏路径集合里
    存在与片段字面完全相等的路径，即唯一采用它，不再把同一轮里其它仅"后缀匹配"
    的候选一并计入歧义。根因实例：根 `CLAUDE.md` 与
    `4-数字员工/采购部/SC8-.../CLAUDE.md` 同时脏时，片段 `` `CLAUDE.md` ``
    在原实现下对根 `CLAUDE.md`（精确命中）与 SC8 那份（`endswith` 命中）各算一次，
    被判 ambiguous，进而使这个早已正确声明的批次被彼时的 `unaccounted` 全局
    门槛连带跳过——已声明齐全的批次不该因为"另一个 session 同时改了一个同名
    文件"而遭殃。本函数当时只做了这一处收窄，**按批次隔离**（结构性改动，
    #230-2d 评估结论）已于队列 #238 落地，见 `_partition_pending_rows_by_
    batch_isolation` 与 `main()`。

    返回 (resolved, not_dirty, ambiguous)：
      resolved   — 恰好命中 1 个脏路径的片段，对应的真实路径（用于 git add）
      not_dirty  — 0 个命中（可能已被别处提交，见"遗留尾巴"处置）
      ambiguous  — 命中 ≥2 个脏路径且无精确相等命中（无法安全判定，本片段对应的
                   候选路径会保留在全局脏路径集合里，从而让上层"非 clean"整体
                   门禁自然拦截，不需要在此单独报错）
    """
    fragments = re.findall(r"`([^`]+)`", files_cell)
    resolved, not_dirty, ambiguous = [], [], []
    for frag in fragments:
        exact = [d for d in dirty_paths if d == frag]
        if exact:
            resolved.append(exact[0])
            continue
        matches = [d for d in dirty_paths if d.endswith("/" + frag)]
        if len(matches) == 1:
            resolved.append(matches[0])
        elif len(matches) == 0:
            not_dirty.append(frag)
        else:
            ambiguous.append(frag)
    return resolved, not_dirty, ambiguous


def _explain_ambiguous_candidates(frag: str, dirty_paths: list[str]) -> list[str]:
    """返回某片段在当前脏路径中命中的全部候选（队列 #238 可解释日志）。

    与 `_resolve_batch_files` 内部同一套匹配规则（精确相等或按 "/" 前缀的
    后缀匹配），这里不做优先级取舍、原样列出候选，只为把"为什么判为歧义"
    说清楚——2026-08-03 本项目正因缺这行可解释日志而把一次正常判定误认成
    bug、白花一轮取证（见文件头部 #234 相关说明）。
    """
    return [d for d in dirty_paths if d == frag or d.endswith("/" + frag)]


def _check_dirty_paths_against_pending_batches(
    repo_root: Path, paths: list[str],
) -> list[tuple[str, str | None]]:
    """队列 #101①：只读核验——给定路径是否命中 §二 待处理批次的"文件清单"声明。

    供 `工具-主工作区安全同步.ps1` 在建议 `git checkout --` 弃改前先调用（走
    `--check-dirty-in-pending-batch` CLI 模式）：命中即不得建议丢弃，应改为
    提示触发 sweep 落库（协议〇.8"批次即扫＋checkout 前核对 §二"）。复用
    `_resolve_batch_files` 同一套匹配规则（精确相等优先，否则按 "/" 后缀），
    不另起一套判据，避免两处独立实现随时间漂移出不一致结论。

    返回 [(path, batch_id_or_None), ...]；batch_id 为 None 表示未命中任何
    待处理批次（可以放心按现有逻辑处理，不属于本检查的管辖范围）。
    """
    queue_text = _read_queue(repo_root)
    rows = _parse_section_two(queue_text)
    pending_rows, _ = _classify_section_two_rows(rows)
    results: list[tuple[str, str | None]] = []
    for path in paths:
        matched_batch = None
        for row in pending_rows:
            resolved, _, _ = _resolve_batch_files(row["files_cell"], [path])
            if resolved:
                matched_batch = row["batch_id"]
                break
        results.append((path, matched_batch))
    return results


def _partition_pending_rows_by_batch_isolation(
    pending_rows: list[dict], dirty_paths: list[str], log: list[str],
) -> tuple[list[dict], dict[str, tuple[list[str], list[str], list[str]]], list[str]]:
    """队列 #238：sweep 批次隔离——把"任一脏文件未声明即整轮 return 0"的
    全局门，改为"只阻塞自身声明存在歧义的批次，其余批次照常落库"。

    背景（详见文件头部说明）：旧实现里，凡 `git status` 存在一个不属于任何
    批次声明的脏路径——哪怕只有一个、哪怕与在办批次毫无关系——`main()`
    就整轮 `return 0`，已正确声明、彼此互不相关的批次被连带跳过（08-04
    实测 17-20 批积压，堵点常常只有 1-5 个真文件）。

    新判据：一个批次是否被阻塞，只取决于**它自己**的声明片段解析结果是否
    存在 `ambiguous`（该片段在当前脏路径中命中 ≥2 个候选、且无精确相等
    命中——见 `_resolve_batch_files` 队列 #234(1) 的精确相等优先收窄）。
    `ambiguous` 片段对应的候选路径必然不在 `declared_all` 里（未被计入
    resolved），这正是"声明片段与未声明脏文件有交集"这句话的精确含义——
    该批次自己声明的一部分，客观上无法安全判定它是不是这些脏文件之一，
    此时**整个批次**（含它其它已能干净解析的片段）都暂缓，不做部分提交
    ——批次内容仍要求原子提交，不拆半。

    与它无关的其它批次（resolved/not_dirty 均已确定、`ambiguous` 为空）
    不受影响，正常进入后续 normal_rows/straggler_rows 处理。

    真正"没人声明"的孤儿脏文件（不出现在任何批次的 resolved 或 ambiguous
    候选里）不阻塞任何批次，只作为独立提示列出（不写入 `log` 之外的任何
    地方）——这类文件的持续存在交给调用方接线的 #236(2) 孤儿脏文件告警去
    处理，sweep 主流程本身不再因它们停摆。

    返回 (clean_rows, row_resolution, orphan_paths)：
      clean_rows     — 未被阻塞、可继续按原逻辑分流 normal/straggler 的批次
      row_resolution — {batch_id: (resolved, not_dirty, ambiguous)}，
                        供调用方复用（避免重复调用 `_resolve_batch_files`）
      orphan_paths   — 不属于任何批次任何片段（含歧义候选）的脏路径，
                        按字典序排列，供调用方接线孤儿告警
    """
    row_resolution: dict[str, tuple[list[str], list[str], list[str]]] = {}
    declared_all: set[str] = set()
    for row in pending_rows:
        resolved, not_dirty, ambiguous = _resolve_batch_files(row["files_cell"], dirty_paths)
        row_resolution[row["batch_id"]] = (resolved, not_dirty, ambiguous)
        declared_all.update(resolved)

    ambiguous_candidates: set[str] = set()
    clean_rows: list[dict] = []
    for row in pending_rows:
        resolved, not_dirty, ambiguous = row_resolution[row["batch_id"]]
        if not ambiguous:
            clean_rows.append(row)
            continue
        explain_parts = []
        for frag in ambiguous:
            candidates = _explain_ambiguous_candidates(frag, dirty_paths)
            ambiguous_candidates.update(candidates)
            explain_parts.append(
                f"`{frag}` 命中 {len(candidates)} 处（{'、'.join(candidates)}），判为歧义"
            )
        log.append(
            f"⚠ 批次 {row['batch_id']} 因声明片段未能唯一判定而暂缓（不影响其它批次）："
            + "；".join(explain_parts)
        )

    orphan_paths = sorted(
        p for p in dirty_paths if p not in declared_all and p not in ambiguous_candidates
    )
    if orphan_paths:
        log.append(
            "⚠ 以下脏路径不属于任何待 commit 批次声明（孤儿，不阻塞其它批次，"
            "长期未认领由 #236 孤儿告警另行点名）："
        )
        log.extend(f"    - {p}" for p in orphan_paths)

    return clean_rows, row_resolution, orphan_paths


def _read_orphan_state(repo_root: Path) -> dict:
    path = repo_root / ORPHAN_STATE_REL
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_orphan_state(repo_root: Path, state: dict) -> None:
    path = repo_root / ORPHAN_STATE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _track_and_alert_orphan_paths(
    repo_root: Path, orphan_paths: list[str], log: list[str],
) -> None:
    """队列 #236(2)：孤儿脏文件（不属于任何批次声明）持续超过阈值即主动
    告警——#238 批次隔离后 sweep 不再因孤儿文件整轮停摆，但"安静地跳过"
    本身仍是问题（#236 取证：4 个孤儿文件挡住 20 个批次跨天不落库，根因
    正是"没人知道"）。复用 #171 已建的 webhook 通道。

    去重：每个路径只在跨过 `ORPHAN_ALERT_THRESHOLD_HOURS` 阈值时首次告警，
    此后每满一个阈值周期再提醒一次，不逐轮（每小时）重复打扰——#147
    `gap_alert` 的"狼来了"教训：过密的提醒会被无视。路径一旦不再是孤儿
    （被声明或已消失）即从状态里清除，不留陈旧记录误导下一次真实孤儿的
    "已孤儿多久"文案。
    """
    state = _read_orphan_state(repo_root)
    now = datetime.now(timezone.utc)
    current = set(orphan_paths)
    for path in list(state.keys()):
        if path not in current:
            del state[path]

    to_alert: list[tuple[str, float]] = []
    for path in orphan_paths:
        entry = state.get(path)
        if entry is None:
            state[path] = {"first_seen": now.isoformat(), "last_alerted": None}
            continue
        first_seen = datetime.fromisoformat(entry["first_seen"])
        age_hours = (now - first_seen).total_seconds() / 3600
        if age_hours < ORPHAN_ALERT_THRESHOLD_HOURS:
            continue
        last_alerted = entry.get("last_alerted")
        if last_alerted is not None:
            since_last = (now - datetime.fromisoformat(last_alerted)).total_seconds() / 3600
            if since_last < ORPHAN_ALERT_THRESHOLD_HOURS:
                continue
        to_alert.append((path, age_hours))
        entry["last_alerted"] = now.isoformat()

    _write_orphan_state(repo_root, state)

    if not to_alert:
        return

    lines = "\n".join(f"- `{p}`（已孤儿 {age:.1f} 小时）" for p, age in to_alert)
    alert_text = (
        f"🧭 落库sweep 检测到 {len(to_alert)} 个脏文件持续未被任何批次声明"
        f"（阈值 {ORPHAN_ALERT_THRESHOLD_HOURS} 小时）：\n{lines}\n"
        "若确认无主，请登记 §二 批次代为声明入库；若仍在编辑中，登记一条"
        "占位批次即可解除本告警。"
    )
    log.append(
        f"🧭 孤儿脏文件告警：{len(to_alert)} 个文件超过 "
        f"{ORPHAN_ALERT_THRESHOLD_HOURS} 小时未声明"
    )
    webhook_url = _load_webhook_url(repo_root)
    if webhook_url is None:
        log.append("⚠ 未在 .env 找到 WECOM_WEBHOOK_URL，跳过孤儿脏文件告警推送（仅留痕日志与状态文件）。")
        return
    try:
        _send_wecom_markdown(webhook_url, alert_text)
    except Exception as exc:  # noqa: BLE001 —— 告警失败不应影响本轮退出码
        log.append(f"⚠ 孤儿脏文件告警推送失败（不影响本轮退出码）：{exc}")
        return
    log.append("✓ 孤儿脏文件告警已推送。")


def _find_missing_deployment_trace(touched_paths: set[str]) -> list[str]:
    """队列 #229：发布收口第②关——本轮 touched_paths 是否命中已部署场景
    白名单、却未同时改动该场景的部署留痕文件。返回命中但缺留痕的场景前缀
    清单（可能为空）。

    三条边界（Shao Peishen 2026-08-03 拍板选 (a)）：
    ① 纯提示，调用方不得据此改变退出码或阻断提交；
    ② 不判断"是否真的部署了"——sweep 拿不到 `.51` 状态，只判"留痕文件是否
       同批改动"这一可机检事实，是否需要补部署留给人判断；
    ③ 初版宁窄勿宽——命中判据是路径前缀白名单，不做内容语义解析（如判断
       CLAUDE.md 的 diff 是否真的更新了"部署状态"段落），避免 #147
       `gap_alert` 式的过度触发反被无视。
    """
    hits = []
    for prefix, trace_file in DEPLOYED_SCENARIO_PREFIXES.items():
        touches_scenario = any(
            p.startswith(prefix) and p != trace_file for p in touched_paths
        )
        if touches_scenario and trace_file not in touched_paths:
            hits.append(prefix)
    return hits


def _announce_missing_deployment_trace(
    repo_root: Path, hits: list[str], log: list[str],
) -> None:
    """队列 #229：命中 `_find_missing_deployment_trace` 时在日志与 webhook
    附一句部署留痕提示——同 #198(c) 范式，纯提示、不阻断、不改退出码。"""
    for prefix in hits:
        log.append(
            f"⚠ 本批改动涉及已部署场景 `{prefix}`，但未见部署留痕行——"
            "若已部署请补留痕；若未部署，请勿对专员宣称已上线"
            "（见 CLAUDE.md §5 第 8 步发送硬前置）"
        )
    webhook_url = _load_webhook_url(repo_root)
    if webhook_url is None:
        log.append("⚠ 未在 .env 找到 WECOM_WEBHOOK_URL，跳过部署留痕提示推送（仅留痕日志）。")
        return
    try:
        _send_wecom_markdown(
            webhook_url,
            "🔧 落库sweep：以下已部署场景本批改动未见部署留痕，请核实：\n"
            + "\n".join(f"- `{p}`" for p in hits),
        )
    except Exception as exc:  # noqa: BLE001 —— 提示推送失败不应影响本轮退出码
        log.append(f"⚠ 部署留痕提示推送失败（不影响本轮退出码）：{exc}")
        return
    log.append("✓ 部署留痕提示已推送。")


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
    parser.add_argument(
        "--check-dirty-in-pending-batch", nargs="+", metavar="PATH", default=None,
        help="#101①：只读核验给定路径（相对仓库根）是否命中§二待处理批次声明，"
             "不做任何写操作、不跑 sweep 主流程。每个路径输出一行 "
             "'MATCH <batch_id> <path>' 或 'NOMATCH <path>'，供"
             "工具-主工作区安全同步.ps1 在建议 git checkout -- 前调用。")
    args = parser.parse_args()

    repo_root = _resolve_repo_root(args.repo_root)

    if args.check_dirty_in_pending_batch is not None:
        # 只读检查模式：不写日志、不碰队列、不动 git 状态，独立于下方主流程。
        results = _check_dirty_paths_against_pending_batches(
            repo_root, args.check_dirty_in_pending_batch)
        for path, batch_id in results:
            if batch_id:
                print(f"MATCH\t{batch_id}\t{path}")
            else:
                print(f"NOMATCH\t{path}")
        return 0
    start_line = f"=== sweep 运行 {_now_utc_str()} ==="
    log: list[str] = [start_line]
    # 队列 #222：启动即写日志首行——不等收尾统一 flush，避免"启动后立刻
    # 崩溃"与"压根没启动"在日志上表现完全相同（#121(b) 遗留未做项；判据
    # 基础设施，见 #96 清单）。此后各退出路径改用 `_flush_remaining_log`，
    # 只落盘首行之后新增的内容，不重复写入这一行。
    if not args.dry_run:
        _flush_log(repo_root, [start_line], dry_run=False)

    try:
        _heal_stale_index_lock(repo_root, log)
        _check_preconditions(repo_root, production=args.repo_root is None)
        # 队列 #192/#194/#198/#219 起跑段写死顺序（勿自行调整，详见各函数 docstring）：
        # ① #198(b) 编辑锁前置探测（任何 git 写动作之前）
        _abort_if_edit_lock_held(repo_root, log)
        # ② #194 无条件补推未推送提交
        _push_any_unpushed_commits(repo_root, log, dry_run=args.dry_run)
        # ③ #192-A flush 锁忙推迟暂存 + #219 决策提醒第二载体（均须在 sweep
        #   自己取锁窗口之外，此处批次处理尚未开始，安全）；dry-run 不做
        #   真实动作，避免副作用。
        if not args.dry_run:
            _flush_pending_lock_appends(repo_root, log)
            _run_decision_reminder_second_carrier(repo_root, log)
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

        # 队列 #238：批次隔离——即便本轮无待处理批次，脏路径也可能全部是
        # 孤儿（没有任何批次登记），仍需纳入 #236(2) 孤儿告警的追踪范围，
        # 故这一步不依赖 `pending_rows` 是否非空，early return 挪到其后。
        clean_rows, row_resolution, orphan_paths = _partition_pending_rows_by_batch_isolation(
            pending_rows, dirty_paths, log,
        )
        if not args.dry_run:
            _track_and_alert_orphan_paths(repo_root, orphan_paths, log)

        if not pending_rows:
            log.append("§二无待处理批次，本轮空转。")
            _flush_remaining_log(repo_root, log, args.dry_run)
            print("\n".join(log))
            return 0

        straggler_rows = []
        normal_rows = []
        for row in clean_rows:
            resolved, not_dirty, ambiguous = row_resolution[row["batch_id"]]
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
        elif not processed_any:
            log.append("本轮无批次可落库（全部暂缓或声明片段当前均无对应脏改动）。")

        # #198(c)：批次落库之后，检查本轮实际 add 过的路径是否命中常驻服务——
        # 纯提示，不影响下方的正常返回。
        if touched_paths and not args.dry_run:
            if _touches_resident_service(touched_paths):
                _announce_resident_service_deployment_hint(repo_root, log)
            # 队列 #229：发布收口第②关——命中已部署场景却未见部署留痕，纯
            # 提示，不影响下方的正常返回。
            missing_trace_hits = _find_missing_deployment_trace(touched_paths)
            if missing_trace_hits:
                _announce_missing_deployment_trace(repo_root, missing_trace_hits, log)

        _flush_remaining_log(repo_root, log, args.dry_run)
        print("\n".join(log))
        return 0

    except SweepAbort as exc:
        log.append(str(exc))
        if exc.is_fork and not args.dry_run:
            _handle_fork_detected(repo_root, log)
        _flush_remaining_log(repo_root, log, args.dry_run)
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
            _flush_remaining_log(repo_root, log, args.dry_run)
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
    if not log:
        return
    log_path = repo_root / LOG_REL
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(log) + "\n\n")


def _flush_remaining_log(repo_root: Path, log: list[str], dry_run: bool) -> None:
    """把本轮 log 中"启动首行之后"新增的部分落盘（队列 #222）——首行已在
    main() 起跑时单独 `_flush_log` 过一次，各退出路径改调本函数而非直接
    调 `_flush_log(repo_root, log, ...)`，避免同一行被重复写入日志文件。"""
    _flush_log(repo_root, log[1:], dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
