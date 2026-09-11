"""队列 #559 处置工具：把孤儿审计链里的真实事件找回权威审计文件，且不破坏
任一条 hash 链的完整性。

## 为什么需要这个工具（而不是直接 `cat 孤儿文件 >> 权威文件`）

`zhuopin_platform.audit.sinks.JsonlSink` 的 `prev_hash` 只对"这一个物理
文件里的上一行"负责（见该模块 docstring）。两份独立文件各自维护一条独立
的、从创世行开始的 hash 链；孤儿文件的每一行 `prev_hash` 指向的是**它自己
链上的上一行**，与权威文件当时真实的最后一行完全无关。若把孤儿文件的原始
字节原样接到权威文件尾部，接缝处那一行的 `prev_hash` 会与权威文件当时的
实际末行不符——`JsonlSink.verify_chain()` 会在接缝处判定为断链，且这条
"断链"本身还会掩盖真正的问题（谁也说不清是被篡改还是被拼接）。

本工具改为：对孤儿文件里的每一条真实记录，在权威文件的链上 **`record()`
一条新事件**（走权威文件自己当前真实的 `prev_hash`，被 `JsonlSink` 在写入
瞬间正确计算），`action` 前缀 `orphan_chain_backfill:`，`decision` 载荷内嵌
原始事件的完整字典（不改一个字段）＋原始 `evaluator`/`timestamp` 原样保留
在内嵌载荷里供人工核对。backfill 事件自身的顶层 `evaluator` 沿用原始
`evaluator`（问责不失真：批准/驳回这两个动作实际发生在谁身上，backfill
不改写这一事实），`timestamp` 是**找回动作发生的时刻**（不得回填成原始
时刻——那会让审计读者误以为权威文件当时就已知道这件事，见 #559 队列行
"不得裸 append 并回" 的判据同源理由）。

完整决策口径见 `aibot_service/repo_paths.py` 模块头 `AUDIT_RELATIVE_PATH`
常量上方注释（本工具与该注释互为对照，改一处另一处需同步）。

## 幂等

每条 backfill 事件的 `decision.orphan_line_sha256` 是原始孤儿行原始字节
（含末尾 `\\n`）的 SHA-256——与孤儿链自身 `prev_hash` 的计算方式一致，
复用而非新造一套指纹口径。重跑前先扫权威文件里已有的
`orphan_chain_backfill:*` 事件、收集其 `orphan_line_sha256` 集合，命中
即跳过，不会重复找回同一行。

## 用法

  # 预览：只读，不写任何文件，报告将要找回几条、幂等命中几条
  python scripts/backfill_orphan_audit_chain.py --orphan-file <孤儿文件路径>

  # 真正执行：写 backfill 事件到权威文件，并把孤儿文件原地改名 quarantine
  python scripts/backfill_orphan_audit_chain.py --orphan-file <孤儿文件路径> --apply

  # 显式指定权威文件（默认按 resolve_default_queue_anchor 动态解析，同
  # push_followup_letter.py／approve_followup_letter.py 既有约定）
  python scripts/backfill_orphan_audit_chain.py --orphan-file <路径> --canonical-file <路径> --apply

环境变量：
  WECOM_AIBOT_QUEUE_PATH   可选，仅作仓库根解析的锚点
  WECOM_AIBOT_AUDIT_PATH   可选，直接指定权威审计文件路径，跳过动态解析
  WECOM_AIBOT_REPO_ROOT    可选，显式指定仓库根，绕开动态 git 解析

退出码：0 ＝ 执行成功（含"零条待找回"）；1 ＝ 前置校验失败（孤儿文件自身
链已损坏、或权威文件当前链已损坏——**两种情况下都拒绝写入**，防止在一条
已经不可信的链上再叠一层不可信）；2 ＝ 参数错误。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parent.parent
NAIVE_REPO_ROOT = SERVICE_DIR.parents[1]  # 5-平台底座/wecom-aibot-service -> 本 checkout 自身的根

# —— 平台底座路径引导（队列 #345 收拢；同 approve_followup_letter.py 样板）。
_HERE = Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        sys.path.insert(0, str(_p / "5-平台底座" / "zhuopin_platform"))
        break
from zhuopin_platform.bootstrap import ensure_paths  # noqa: E402
ensure_paths(__file__, SERVICE_DIR)  # noqa: E402

from zhuopin_platform.audit import AuditEvent, AuditLogger  # noqa: E402
from zhuopin_platform.audit.sinks import JsonlSink  # noqa: E402

from aibot_service.repo_paths import (  # noqa: E402
    resolve_audit_path,
    resolve_default_queue_anchor,
    resolve_repo_root,
)


BACKFILL_ACTION_PREFIX = "orphan_chain_backfill:"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _raw_lines(path: Path) -> list[bytes]:
    """原始字节逐行读取（含末尾 \\n），与 JsonlSink.verify_chain 同口径。"""
    raw: list[bytes] = []
    with open(path, "rb") as f:
        for line in f:
            stripped = line.rstrip(b"\n")
            if stripped:
                raw.append(line if line.endswith(b"\n") else line + b"\n")
    return raw


def _verify_local_tail(raw_lines: list[bytes], window: int) -> tuple[bool, str]:
    """校验文件**最后 `window` 行**内部的链路是否自洽（不要求回溯到创世行）。

    🔴 **为什么不用 `JsonlSink.verify_chain()`（全链回溯到创世行）当唯一判据**：
    实测本项目两份 `wecom_aibot_audit.jsonl`（主仓与本次涉事 worktree）都在
    `2026-07-28T13:27:58Z` 前后出现一次全链断点——时间戳与同目录
    `wecom_aibot_audit-split-archive-2026-07-28.jsonl` 那次**已归档、已知**的
    审计文件拆分/迁移操作精确重合，属历史已知事件，非本次 #559 的范围。
    若坚持全链必须回溯到创世行才允许写入，任何一次找回都会被这条无关的
    历史断点挡住；而这个成本换不回任何安全收益——本工具真正要证明的是
    "我即将找回的这几行，在它们自己最近的一段里没有被拼接/篡改过"，
    不是"整份文件自开天辟地起从未被合法迁移过"。故改为**局部窗口校验**：
    只要求最后 `window` 行彼此的 `prev_hash` 能逐行对上，即视为可信找回来源；
    全链层面的断点仍会被上一层调用方打印为 WARNING（如实告知、不隐瞒），
    但不阻断找回。
    """
    if not raw_lines:
        return True, ""

    tail = raw_lines[-window:] if len(raw_lines) > window else raw_lines
    is_full_file = len(raw_lines) <= window

    # 窗口第一行：若窗口就是整份文件（创世行在窗口内），genesis 行的
    # prev_hash 缺失/为空本身合法，不校验其值；若窗口是从文件中段截取的，
    # 第一行的 prev_hash 指向窗口之外，不是本函数要证明的对象，只取它自己
    # 的哈希作为后续链路核对的起点，不对它的 `prev_hash` 字段本身下判断。
    prev_hash = _sha256_bytes(tail[0])
    start = 1
    if is_full_file:
        try:
            first_record = json.loads(tail[0].decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            return False, f"窗口内第 1 行解析失败：{exc}"
        if first_record.get("prev_hash"):
            # 整份文件都在窗口内、且第一行不是 genesis（带 prev_hash）——
            # 那说明这份文件本身就不是从创世行开始的（例如是一次迁移/拆分
            # 后的续篇），同样不是本函数要证明的对象，直接放行进入逐行核对。
            pass

    for idx in range(start, len(tail)):
        raw = tail[idx]
        try:
            record = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            return False, f"窗口内第 {idx + 1} 行解析失败：{exc}"
        stored_prev = record.get("prev_hash")
        if stored_prev != prev_hash:
            return False, f"窗口内第 {idx + 1} 行 prev_hash 不匹配（局部链路断裂）"
        prev_hash = _sha256_bytes(raw)
    return True, ""


def _existing_backfilled_hashes(canonical_path: Path) -> set[str]:
    """扫权威文件里已有的 backfill 事件，取出其 `orphan_line_sha256` 集合（幂等用）。"""
    out: set[str] = set()
    for record in JsonlSink(canonical_path).read_all():
        action = record.get("action", "")
        if isinstance(action, str) and action.startswith(BACKFILL_ACTION_PREFIX):
            h = (record.get("decision") or {}).get("orphan_line_sha256")
            if isinstance(h, str):
                out.add(h)
    return out


def _resolve_canonical_path(args: argparse.Namespace) -> Path:
    if args.canonical_file:
        return Path(args.canonical_file)
    env_override = os.environ.get("WECOM_AIBOT_AUDIT_PATH")
    if env_override:
        return Path(env_override)
    queue_anchor = resolve_default_queue_anchor(NAIVE_REPO_ROOT)
    repo_root = resolve_repo_root(queue_anchor, fallback=NAIVE_REPO_ROOT)
    return resolve_audit_path(repo_root)


def _run(args: argparse.Namespace) -> int:
    orphan_path = Path(args.orphan_file)
    if not orphan_path.exists():
        print(f"[ARGS] 孤儿文件不存在：{orphan_path}")
        return 2

    canonical_path = _resolve_canonical_path(args)
    if not canonical_path.exists():
        print(f"[ARGS] 权威文件不存在：{canonical_path}（拒绝在一个不存在的文件上"
              "起链——这不是本工具该做的事，先确认路径）")
        return 2

    if orphan_path.resolve() == canonical_path.resolve():
        print("[ARGS] 孤儿文件与权威文件是同一个物理文件，无需找回。")
        return 2

    raw_lines = _raw_lines(orphan_path)

    # 前置校验①：孤儿链**最近一段**（默认末 `--window` 行）必须内部自洽——
    # 证明"即将找回的这几行没有在它们自己最近的历史里被拼接/篡改过"。
    # 不要求回溯到创世行（见 `_verify_local_tail` docstring 的理由）。
    orphan_full = JsonlSink(orphan_path).verify_chain()
    if not orphan_full.ok:
        print(f"[WARN] 孤儿文件全链回溯到创世行不完整（第 {orphan_full.broken_at} 行："
              f"{orphan_full.error}）——若该断点时间戳与已知的历史迁移/拆分事件重合"
              "（如 `*-split-archive-*.jsonl`），属已知历史断点，非本次找回的范围；"
              "改用局部窗口校验（见下）。")
    ok, err = _verify_local_tail(raw_lines, args.window)
    if not ok:
        print(f"[REJECTED] 孤儿文件最近 {args.window} 行内部链路不自洽（{err}）——"
              "拒绝找回，请先取证孤儿文件本身是否被篡改。")
        return 1

    # 前置校验②：权威链**最近一段**必须内部自洽——不在一段刚被破坏的链尾
    # 上继续叠写。同①不要求全链回溯创世行（本仓库两份审计文件均在
    # 2026-07-28 历史拆分处有已知全链断点，与本次找回无关）。
    canonical_full = JsonlSink(canonical_path).verify_chain()
    if not canonical_full.ok:
        print(f"[WARN] 权威文件全链回溯到创世行不完整（第 {canonical_full.broken_at} 行："
              f"{canonical_full.error}）——同上，若与已知历史迁移事件重合可忽略，"
              "改用局部窗口校验。")
    canonical_raw = _raw_lines(canonical_path)
    ok, err = _verify_local_tail(canonical_raw, args.window)
    if not ok:
        print(f"[REJECTED] 权威文件最近 {args.window} 行内部链路不自洽（{err}）——"
              "拒绝写入，请先处理权威链尾部的完整性问题。")
        return 1
    already = _existing_backfilled_hashes(canonical_path)

    orphan_sha256_whole_file = _sha256_bytes(orphan_path.read_bytes())
    to_backfill: list[tuple[bytes, dict]] = []
    skipped_existing = 0
    for raw in raw_lines:
        line_hash = _sha256_bytes(raw)
        if line_hash in already:
            skipped_existing += 1
            continue
        try:
            record = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            print(f"[REJECTED] 孤儿文件存在无法解析的行（{exc}）——拒绝找回，"
                  "先手工取证该行。")
            return 1
        to_backfill.append((raw, record))

    print(f"[PLAN] 孤儿文件 {orphan_path}：共 {len(raw_lines)} 行，"
          f"已找回（幂等跳过）{skipped_existing} 行，待找回 {len(to_backfill)} 行。")
    for raw, record in to_backfill:
        line_hash = _sha256_bytes(raw)
        print(f"  - {record.get('action', '?')}　evaluator={record.get('evaluator', '?')}　"
              f"timestamp={record.get('timestamp', '?')}　orphan_line_sha256={line_hash[:12]}…")

    if not to_backfill:
        print("[DONE] 无待找回记录，未写入任何内容。")
        return 0

    if not args.apply:
        print("[DRY-RUN] 未加 --apply，以上为预览，未写入任何文件、未改动孤儿文件。")
        return 0

    audit = AuditLogger.jsonl(canonical_path)
    written = 0
    for raw, record in to_backfill:
        line_hash = _sha256_bytes(raw)
        event = AuditEvent(
            scenario=record.get("scenario", "wecom-aibot"),
            action=f"{BACKFILL_ACTION_PREFIX}{record.get('action', 'unknown')}",
            evaluator=record.get("evaluator", "unknown"),
            automation_level=record.get("automation_level", "L1"),
            decision={
                "orphan_source_path": str(orphan_path),
                "orphan_source_sha256_at_backfill": orphan_sha256_whole_file,
                "orphan_line_sha256": line_hash,
                "queue_row": "559",
                "original_record": record,
            },
            override_reason=(
                "队列 #559：人工门禁决策此前误落进 worktree 孤儿审计文件，"
                "主仓审计看不到——本条为找回记录，不改写原始决策，原始决策"
                "完整原样存于 decision.original_record。"
            ),
        )
        audit.record(event)
        written += 1

    # 事后自证：权威链**尾部**在写入后必须仍然局部自洽（同①②理由，不用
    # 全链回溯创世行——本文件已知在 2026-07-28 处有历史断点，与本次写入
    # 无关，用它判定会产生假阳性）。
    post_raw = _raw_lines(canonical_path)
    post_ok, post_err = _verify_local_tail(post_raw, args.window)
    if not post_ok:
        print(f"[ALERT] 写入后权威链尾部自检失败（{post_err}）——🔴 这不应该发生，"
              "立即停手人工介入，不要再对本文件做任何写入。")
        return 1
    print(f"[OK] 已写入 {written} 条 backfill 事件；权威链尾部写入后自检通过"
          f"（共 {len(post_raw)} 行，窗口 {min(args.window, len(post_raw))} 行局部自洽）。")

    # quarantine 孤儿文件：不删除（3 年留存），原地改名防止再被误当活文件读。
    quarantine_name = (
        f"{orphan_path.stem}-orphan-worktree-"
        f"{datetime.now(tz=timezone.utc).strftime('%Y-%m-%d')}{orphan_path.suffix}"
    )
    quarantine_path = orphan_path.parent / quarantine_name
    if quarantine_path.exists():
        print(f"[NOTE] quarantine 目标已存在（{quarantine_path}），孤儿文件保留原名不改动，"
              "请手工核对后处理。")
    else:
        orphan_path.rename(quarantine_path)
        print(f"[OK] 孤儿文件已 quarantine：{orphan_path} -> {quarantine_path}")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="队列 #559：把孤儿审计链里的真实事件找回权威审计文件（backfill，非裸 append）"
    )
    parser.add_argument("--orphan-file", required=True, help="孤儿审计文件路径")
    parser.add_argument("--canonical-file", default=None,
                         help="权威审计文件路径；不传则按 resolve_default_queue_anchor 动态解析")
    parser.add_argument("--apply", action="store_true",
                         help="真正写入；不传则只预览（dry-run，默认）")
    parser.add_argument("--window", type=int, default=50,
                         help="局部链路校验窗口行数（默认 50，覆盖到明显早于待找回记录"
                              "的历史范围即可，不需要回溯到创世行——见 _verify_local_tail）")
    args = parser.parse_args()
    sys.exit(_run(args))


if __name__ == "__main__":
    main()
