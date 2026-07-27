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
        2=出现需要人工介入的异常（本地已提交但推送不了/非快进，不会自动强推）；
        1=脚本自身参数或环境错误（不应在正常运行中出现）。

陈旧 `.git/index.lock` 前置自愈（#121(b)，2026-07-27 补）：起跑第一步先查
`.git/index.lock`——超过 STALE_INDEX_LOCK_MINUTES（默认 10 分钟）未清的判定
为异常退出残留，自动清除后继续；新鲜的（大概率是真实并发 git 进程）不抢占，
优雅跳过本轮并写日志。见 _heal_stale_index_lock()——修复前该文件残留会让
后续 `_run_git`（check=True）抛未捕获异常，表现正是"计划任务 LastTaskResult=1
但日志无新条目"。

用法：
  python 0-学习与工具/工具-落库sweep.py            # 真跑
  python 0-学习与工具/工具-落库sweep.py --dry-run   # 只打印计划动作，不落地
  # --repo-root 仅供单测覆盖 MAIN_WORKSPACE 断言，生产不要传
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
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

SECTION_TWO_HEADING = "## 二、"
NEXT_SECTION_PREFIX = "## "


class SweepAbort(Exception):
    """安全门未过或运行中出现需要人工介入的异常，携带退出码与提示。"""

    def __init__(self, message: str, exit_code: int = 0):
        super().__init__(message)
        self.exit_code = exit_code


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


def _verify_fast_forward(repo_root: Path, *, refetch: bool, on_fail_exit_code: int) -> None:
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
        )


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
    args = [sys.executable, str(repo_root / EDIT_LOCK_SCRIPT_REL), action, "--who", LOCK_WHO]
    if extra:
        args.extend(extra)
    return subprocess.run(args, cwd=repo_root, capture_output=True, text=True, encoding="utf-8")


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
        _verify_fast_forward(repo_root, refetch=True, on_fail_exit_code=0)

        dirty_paths = _status_paths(repo_root)
        queue_text = _read_queue(repo_root)
        rows = _parse_section_two(queue_text)
        pending_rows = [r for r in rows if "✅" not in r["status_cell"]]

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

        for row, resolved in normal_rows:
            _process_normal_batch(repo_root, row, resolved, args.dry_run, log)

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

        _flush_log(repo_root, log, args.dry_run)
        print("\n".join(log))
        return 0

    except SweepAbort as exc:
        log.append(str(exc))
        _flush_log(repo_root, log, args.dry_run)
        print("\n".join(log))
        return exc.exit_code


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
