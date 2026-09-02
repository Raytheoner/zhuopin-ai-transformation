#!/usr/bin/env python3
"""工具-泳道看护状态机 —— lane-watch-mode §3 停/续状态机（队列 §一 `#452`，design.md D1-D7，`OP-0902-B` 实现）。

## 它解决的问题

`zhuopin-lane-watch` 是「他在场、自动排波推进、跑到决策点即停等他一个字母」
的第三种泳道模式（另两种：`zhuopin-lane-clearpool` 无人在场全零确认、
`zhuopin-lan-closeout` 他在场逐项串行）。本包**唯一新建的代码**就是这个
停/续状态机——判一个动作该不该停（D1）、命中即落档＋推「等人」通知、
他答复后解除暂停、以及待答超时 4 小时自动收回（D5 解法 3）。

## 权威判据正本

**D1-D7 全部判据以 `openspec/changes/lane-watch-mode/design.md` 为准**，本文件
是它的可执行落地，与 design 冲突时以 design 为准。D1 三档表**逐字转录**在
下方 `GREEN_ACTIONS` / `YELLOW_ACTIONS` / `RED_ACTIONS` 三个字典里——
**不得在本文件之外的地方（opener 正文、SKILL.md）再抄一遍**，一律用
`criteria` 子命令现取，避免两处判据表漂移。

## 为什么不复用 `工具-共享文档编辑锁.py` 的 acquire/release

那把锁面向**被跟踪的 markdown 文档**（队列表格行级结构、reserve 编号、
release 时的 git dirty-status 结构校验），本状态文件是 gitignore 的高频小
JSON（多个 worktree 里的无头 CC 泳道并发写），两者形状不同——借用重量级
markdown 行锁会引入与本场景无关的校验开销与耦合。本文件自建一把最小独占
锁（`_StateLock`，原子 `O_CREAT|O_EXCL` 建锁文件＋陈旧接管），只做互斥，
不做内容语义校验。

## 跨 worktree 可见性

状态文件落 `<主工作区>/reports/lane-watch-state.json`——`REPO_ROOT` 复用
`工具-共享文档编辑锁.py` 的 `git rev-parse --git-common-dir` 解析（与
`工具-跟进闸查询.py` 同一手法）：各无头 CC 泳道各在自己的 worktree 里运行，
若按 `Path(__file__)` 各算各的路径会写进 N 份互相看不见的文件——同队列
#321 幽灵副本事故的成因。

## 用法

    python 0-学习与工具/工具-泳道看护状态机.py criteria
    python 0-学习与工具/工具-泳道看护状态机.py classify --action-key merge_to_master
    python 0-学习与工具/工具-泳道看护状态机.py pause --batch 2026-09-02-看护批A \\
        --wave 2 --lane A --action-key deploy_51 --waiting-for "是否现在部署 .51" \\
        --option 部署 --option 先不部署
    python 0-学习与工具/工具-泳道看护状态机.py resume --lane A --answer "部署"
    python 0-学习与工具/工具-泳道看护状态机.py check-timeout
    python 0-学习与工具/工具-泳道看护状态机.py summary --batch 2026-09-02-看护批A
    python 0-学习与工具/工具-泳道看护状态机.py show

退出码：`classify`/`criteria`/`check-timeout`/`summary`/`show` 恒 0（只读/
判定类，不代表业务失败）；`pause` 对 🟢 动作或参数有误返回 1；`resume` 对
不在 paused 态的泳道返回 1。全部时间戳为**真 UTC**
（`datetime.now(timezone.utc)`，格式 `YYYY-MM-DDTHH:MM:SSZ`），非本地时间。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

_TOOLS_DIR = Path(__file__).resolve().parent

# 复用编辑锁已验证的主工作区解析（同 `工具-跟进闸查询.py` 手法）：按文件
# 路径 importlib 加载，不走 `import 工具-...` 的包名解析（文件名含中文/
# 连字符）。
_EDIT_LOCK_SCRIPT = _TOOLS_DIR / "工具-共享文档编辑锁.py"
_spec = importlib.util.spec_from_file_location("_lane_watch_editlock_reuse", _EDIT_LOCK_SCRIPT)
_editlock = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _editlock
_spec.loader.exec_module(_editlock)

REPO_ROOT: Path = _editlock.REPO_ROOT

STATE_PATH_REL = "reports/lane-watch-state.json"
LOCK_STALE_SECONDS = 120
LOCK_TIMEOUT_SECONDS = 15
DEFAULT_TIMEOUT_HOURS = 4.0  # D5 解法 3：待答超时自动收工

# ---------------------------------------------------------------------------
# D1 · 决策点判据表（design.md D1 逐字转录，键名仅为程序内标识符，中文标签
# 才是判据原文；🔴 不得自行增删动作类型——未覆盖的一律走 fail-safe）。
# ---------------------------------------------------------------------------

TIER_GREEN = "🟢"
TIER_YELLOW = "🟡"
TIER_RED = "🔴"

GREEN_ACTIONS = {
    "queue_writeback": "队列回灌",
    "doc_edit": "文档改动",
    "readonly_evidence": "只读取证",
    "unit_regression_tests": "单测与回归",
    "worktree_local_build": "worktree 内本地建造",
    "openspec_draft": "openspec proposal 与 tasks 起草",
}

YELLOW_ACTIONS = {
    "merge_to_master": "① 生产代码 ff 合入 master",
    "deploy_51": "② `.51` 部署",
    "change_criteria": "③ 改口径/判据/阈值",
    "openspec_design_review": "④ openspec design 审",
    "close_others_queue_row": "⑤ 关闭他人在办队列行",
}

RED_ACTIONS = {
    "external_send": "对外发送（跟进信／企微群／专员）",
    "l2_gate_signoff": "L2 门禁签字",
    "compliance_redline_change": "合规红线变更",
    "asil_cd_related": "ASIL C-D 相关",
}

_ALL_TIERS = {TIER_GREEN: GREEN_ACTIONS, TIER_YELLOW: YELLOW_ACTIONS, TIER_RED: RED_ACTIONS}

FAIL_SAFE_NOTE = (
    "本动作判据未覆盖，按 🟡 停（fail-safe：宁可多停一次，不可少停一次）；"
    "请在续跑请求里裁定它该进哪一档，答复将回灌 design.md D1 表作为新判例。"
)


@dataclass
class Classification:
    action_key: str
    tier: str
    label: str
    covered: bool
    note: str = ""


def classify(action_key: str) -> Classification:
    """D1 三档判据：命中已知表即返回对应档；未命中按 🟡 fail-safe（3.4）。"""
    for tier, table in _ALL_TIERS.items():
        if action_key in table:
            return Classification(action_key, tier, table[action_key], covered=True)
    return Classification(action_key, TIER_YELLOW, action_key, covered=False, note=FAIL_SAFE_NOTE)


# ---------------------------------------------------------------------------
# 时间：全部真 UTC，避免根 CLAUDE.md「时间戳必判 UTC vs Win 本地」踩坑。
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# 状态文件 I/O ＋ 最小独占锁
# ---------------------------------------------------------------------------

def _state_path() -> Path:
    return REPO_ROOT / STATE_PATH_REL


class _LockTimeout(RuntimeError):
    pass


class _StateLock:
    """最小自建独占锁：原子 `O_CREAT|O_EXCL` 建锁文件；持锁超过
    `LOCK_STALE_SECONDS` 视为异常退出遗留，接管（同编辑锁陈旧锁接管的思路，
    但不复用其实现——见模块文档「为什么不复用」）。"""

    def __init__(self, target: Path, timeout: float = LOCK_TIMEOUT_SECONDS):
        self.lock_path = Path(str(target) + ".lock")
        self.timeout = timeout

    def __enter__(self) -> "_StateLock":
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                self.lock_path.parent.mkdir(parents=True, exist_ok=True)
                fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode("ascii"))
                os.close(fd)
                return self
            except FileExistsError:
                try:
                    age = time.time() - self.lock_path.stat().st_mtime
                except OSError:
                    age = LOCK_STALE_SECONDS + 1  # 文件在检查瞬间消失，按可接管处理
                if age > LOCK_STALE_SECONDS:
                    try:
                        self.lock_path.unlink()
                    except OSError:
                        pass
                    continue
                if time.monotonic() >= deadline:
                    raise _LockTimeout(
                        f"锁 {self.lock_path} 被占用超过 {self.timeout}s，放弃"
                        "（内部互斥等待超时，不代表业务上真的冲突，出现即说明并发压力异常）。"
                    )
                time.sleep(0.1)

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            self.lock_path.unlink()
        except OSError:
            pass
        return False


def _read_state() -> dict:
    path = _state_path()
    if not path.exists():
        return {"lanes": {}}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {"lanes": {}}
    return json.loads(text)


def _atomic_write_state(data: dict) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _iso(_now())
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _with_state(mutate: Callable[[dict], None]) -> dict:
    """加锁读→改→写；`mutate` 就地修改 `data`（可 raise 以中止本次写入，
    锁仍会在 `__exit__` 正常释放）。返回写入后的最终 `data`。"""
    with _StateLock(_state_path()):
        data = _read_state()
        data.setdefault("lanes", {})
        mutate(data)
        _atomic_write_state(data)
        return data


# ---------------------------------------------------------------------------
# 企微「等人」通知（4.2：接入既有推送通道，不新建）
# ---------------------------------------------------------------------------

def _format_wait_notice(
    *, batch: str, lane: str, wave: int, tier: str, action_label: str,
    waiting_for: str, options: list, covered: bool,
) -> str:
    lines = [
        "**泳道看护 · 等人**",
        f"批次：{batch}　波次：{wave}　泳道：`{lane}`",
        f"档位：{tier}　动作：{action_label}",
        f"在等：{waiting_for}",
    ]
    if options:
        lines.append("选项：" + "／".join(options))
    if not covered:
        lines.append(f'<font color="warning">{FAIL_SAFE_NOTE}</font>')
    lines.append("> 请回到 Cowork 会话回一个字母（本期仅认 Cowork 侧答复，D5/§8.1）。")
    return "\n".join(lines)


def _load_wecom_sender() -> Optional[Callable[[str], None]]:
    """按文件路径加载 `发企微.py`，返回 `content -> None` 的发送函数；找不到
    脚本时返回 `None`（调用方降级为仅落状态，同清池「未上线则降级仅心跳」
    既例）。"""
    script = _TOOLS_DIR / "发企微.py"
    if not script.exists():
        return None
    spec = importlib.util.spec_from_file_location("_lane_watch_wecom_reuse", script)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    def _send(content: str) -> None:
        module.send_markdown(module.load_webhook(), content)

    return _send


def _notify_best_effort(message: str, notify_fn: Optional[Callable[[str], None]]) -> None:
    """通知失败绝不能拖垮状态落档——状态文件写入是本函数调用前就已完成的
    临界操作，这里只做尽力而为的推送。"""
    fn = notify_fn if notify_fn is not None else _load_wecom_sender()
    if fn is None:
        print(
            "⚠ 未找到 发企微.py，等人通知降级为仅落状态（同清池"
            "「未上线则降级仅心跳」既例）。",
            file=sys.stderr,
        )
        return
    try:
        fn(message)
    except SystemExit as exc:
        print(f"⚠ 企微推送未完成（{exc}），已降级为仅落状态；状态文件已如实写入不受影响。", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 —— 通知是尽力而为，任何异常都不得向上传播
        print(f"⚠ 企微推送异常（{exc}），已降级为仅落状态。", file=sys.stderr)


# ---------------------------------------------------------------------------
# 核心动作：pause / resume / check-timeout / summary
# ---------------------------------------------------------------------------

def pause_lane(
    *, batch: str, wave: int, lane: str, action_key: str, waiting_for: str,
    options: Optional[list] = None, notify_fn: Optional[Callable[[str], None]] = None,
) -> dict:
    """泳道命中 🟡/🔴 决策点：落续跑状态＋推「等人」企微通知（3.1/3.2/3.4/4.2）。

    🟢 档动作不需要停，调用即报错（调用方逻辑错误，非运行时可恢复场景）。
    """
    cls = classify(action_key)
    if cls.tier == TIER_GREEN:
        raise ValueError(f"🟢 档动作（{action_key}：{cls.label}）不需要停，不接受 pause。")

    now = _now()

    def _mutate(data: dict) -> None:
        lanes = data["lanes"]
        lane_state = lanes.setdefault(lane, {"status": "running", "history": []})
        if lane_state.get("status") != "paused":
            # 仅在「当前不是已暂停」时刷新 original_status——避免重复 pause
            # 把 original_status 误写成 "paused" 自身。
            lane_state["original_status"] = lane_state.get("status", "running")
        lane_state.update({
            "status": "paused",
            "batch": batch,
            "wave": wave,
            "tier": cls.tier,
            "action_key": action_key,
            "action_label": cls.label,
            "covered": cls.covered,
            "waiting_for": waiting_for,
            "options": options or [],
            "paused_at": _iso(now),
            "answer": None,
            "answered_at": None,
        })
        lane_state.setdefault("history", []).append({
            "batch": batch, "wave": wave, "tier": cls.tier,
            "action_key": action_key, "action_label": cls.label,
            "waiting_for": waiting_for, "options": options or [],
            "paused_at": _iso(now), "answer": None, "answered_at": None,
            "resolved_by": None,
        })

    data = _with_state(_mutate)

    message = _format_wait_notice(
        batch=batch, lane=lane, wave=wave, tier=cls.tier, action_label=cls.label,
        waiting_for=waiting_for, options=options or [], covered=cls.covered,
    )
    _notify_best_effort(message, notify_fn)
    return data["lanes"][lane]


def resume_lane(*, lane: str, answer: str) -> dict:
    """记录答复、解除暂停（3.3）。只接受当前确为 paused 态的泳道——防止对
    未暂停/已续过的泳道重复 resume 把历史记录写乱。"""
    now = _now()

    def _mutate(data: dict) -> None:
        lane_state = data["lanes"].get(lane)
        if lane_state is None or lane_state.get("status") != "paused":
            current = lane_state.get("status") if lane_state else "不存在"
            raise ValueError(f"泳道 `{lane}` 当前不在 paused 状态，无法 resume（现状：{current}）。")
        lane_state["status"] = "resumed"
        lane_state["answer"] = answer
        lane_state["answered_at"] = _iso(now)
        history = lane_state.get("history", [])
        if history and history[-1].get("resolved_by") is None:
            history[-1]["answer"] = answer
            history[-1]["answered_at"] = _iso(now)
            history[-1]["resolved_by"] = "answered"

    data = _with_state(_mutate)
    return data["lanes"][lane]


def check_timeouts(*, hours: float = DEFAULT_TIMEOUT_HOURS) -> list:
    """D5 解法 3：任一泳道停在决策点超过 `hours` 未获答复 ⇒ 降回
    `original_status`，history 对应条目按 `resolved_by="timeout"` 收口。
    降回是无损的——他回来仍可重新触发该泳道。"""
    threshold = timedelta(hours=hours)
    now = _now()
    reverted: list = []

    def _mutate(data: dict) -> None:
        for lane, lane_state in data.get("lanes", {}).items():
            if lane_state.get("status") != "paused":
                continue
            paused_at = lane_state.get("paused_at")
            if not paused_at:
                continue
            elapsed = now - _parse_iso(paused_at)
            if elapsed < threshold:
                continue
            original = lane_state.get("original_status", "running")
            lane_state["status"] = original
            lane_state["reverted_at"] = _iso(now)
            lane_state["revert_reason"] = "因超时未获答复而收回"
            history = lane_state.get("history", [])
            if history and history[-1].get("resolved_by") is None:
                history[-1]["resolved_by"] = "timeout"
                history[-1]["answer"] = None
                history[-1]["answered_at"] = _iso(now)
            reverted.append({
                "lane": lane,
                "waited_hours": round(elapsed.total_seconds() / 3600, 1),
                "reverted_to": original,
            })

    _with_state(_mutate)
    return reverted


def _format_wait_duration(paused_at: Optional[str], answered_at: Optional[str]) -> str:
    if not paused_at:
        return "未知"
    start = _parse_iso(paused_at)
    end = _parse_iso(answered_at) if answered_at else _now()
    minutes = (end - start).total_seconds() / 60
    if minutes < 60:
        return f"{minutes:.0f} 分钟"
    return f"{minutes / 60:.1f} 小时"


def build_summary(*, batch: Optional[str] = None) -> list:
    """D6：每次停顿摊平成一行素材——`<泳道>／<档位>／<停在什么动作>／
    <他答了什么>／<等了多久>`。「仍在等」的条目也列入，不因未收口而漏计
    （D6 的意义正是让"该停没停"与"全程零停"在外观上不再一样）。"""
    data = _read_state()
    rows = []
    for lane, lane_state in data.get("lanes", {}).items():
        for h in lane_state.get("history", []):
            if batch and h.get("batch") != batch:
                continue
            resolved_by = h.get("resolved_by")
            if resolved_by == "answered":
                answer_text = h.get("answer")
            elif resolved_by == "timeout":
                answer_text = "超时收回"
            else:
                answer_text = "仍在等"
            rows.append({
                "lane": lane,
                "tier": h.get("tier"),
                "action": h.get("action_label"),
                "answer": answer_text,
                "waited": _format_wait_duration(h.get("paused_at"), h.get("answered_at")),
            })
    return rows


def format_summary_line(rows: list) -> str:
    if not rows:
        return "本批停 0 次"
    parts = [f"{r['lane']}／{r['tier']}／{r['action']}／{r['answer']}／{r['waited']}" for r in rows]
    return f"本批停 {len(rows)} 次｜逐次：" + "；".join(parts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_criteria(args: argparse.Namespace) -> int:
    if args.json:
        print(json.dumps(
            {TIER_GREEN: GREEN_ACTIONS, TIER_YELLOW: YELLOW_ACTIONS, TIER_RED: RED_ACTIONS},
            ensure_ascii=False, indent=2,
        ))
        return 0
    for tier, table in _ALL_TIERS.items():
        print(tier)
        for key, label in table.items():
            print(f"  {key}：{label}")
    return 0


def _cmd_classify(args: argparse.Namespace) -> int:
    cls = classify(args.action_key)
    suffix = "" if cls.covered else "（未覆盖，fail-safe）"
    print(f"{cls.tier} {cls.label}{suffix}")
    if not cls.covered:
        print(cls.note)
    if args.json:
        print(json.dumps(asdict(cls), ensure_ascii=False))
    return 0


def _cmd_pause(args: argparse.Namespace) -> int:
    notify_fn = (lambda _msg: None) if args.no_notify else None
    try:
        state = pause_lane(
            batch=args.batch, wave=args.wave, lane=args.lane, action_key=args.action_key,
            waiting_for=args.waiting_for, options=args.option or None, notify_fn=notify_fn,
        )
    except ValueError as exc:
        print(f"✗ {exc}")
        return 1
    print(f"⏸ 已落状态：泳道 `{args.lane}` {state['tier']} 停在「{state['action_label']}」，等：{args.waiting_for}")
    if args.json:
        print(json.dumps(state, ensure_ascii=False))
    return 0


def _cmd_resume(args: argparse.Namespace) -> int:
    try:
        state = resume_lane(lane=args.lane, answer=args.answer)
    except ValueError as exc:
        print(f"✗ {exc}")
        return 1
    waited = _format_wait_duration(state.get("paused_at"), state.get("answered_at"))
    print(f"▶ 泳道 `{args.lane}` 已续：答复「{args.answer}」，等了 {waited}。下一步：Cowork 据此起下一段泳道。")
    if args.json:
        print(json.dumps(state, ensure_ascii=False))
    return 0


def _cmd_check_timeout(args: argparse.Namespace) -> int:
    reverted = check_timeouts(hours=args.hours)
    if not reverted:
        print(f"✓ 无超过 {args.hours} 小时未答复的暂停泳道。")
    else:
        for r in reverted:
            print(
                f"⏮ 泳道 `{r['lane']}` 等了 {r['waited_hours']} 小时未获答复，"
                f"已收回至「{r['reverted_to']}」（因超时未获答复而收回）。"
            )
    if args.json:
        print(json.dumps(reverted, ensure_ascii=False))
    return 0


def _cmd_summary(args: argparse.Namespace) -> int:
    rows = build_summary(batch=args.batch)
    print(format_summary_line(rows))
    if args.json:
        print(json.dumps(rows, ensure_ascii=False))
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    data = _read_state()
    lanes = data.get("lanes", {})
    if args.lane:
        lanes = {args.lane: lanes[args.lane]} if args.lane in lanes else {}
    if args.json:
        print(json.dumps(lanes, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if not lanes:
        print("（当前无泳道记录）")
        return 0
    for lane, s in lanes.items():
        extra = ""
        if s.get("status") == "paused":
            extra = f"　{s.get('tier', '')} 停在「{s.get('action_label', '')}」，等：{s.get('waiting_for', '')}"
        print(f"{lane}：{s.get('status')}{extra}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="泳道看护模式 §3 停/续状态机（design.md D1 判据表的可执行落地）。")
    sub = p.add_subparsers(dest="command", required=True)

    p_criteria = sub.add_parser("criteria", help="打印 D1 三档判据表（单一可信源，opener 引用本命令而非复述）")
    p_criteria.add_argument("--json", action="store_true")
    p_criteria.set_defaults(func=_cmd_criteria)

    p_classify = sub.add_parser("classify", help="给一个动作 key 判定档位")
    p_classify.add_argument("--action-key", required=True)
    p_classify.add_argument("--json", action="store_true")
    p_classify.set_defaults(func=_cmd_classify)

    p_pause = sub.add_parser("pause", help="泳道命中 🟡/🔴 决策点：落状态＋推等人通知")
    p_pause.add_argument("--batch", required=True)
    p_pause.add_argument("--wave", type=int, required=True)
    p_pause.add_argument("--lane", required=True)
    p_pause.add_argument("--action-key", required=True)
    p_pause.add_argument("--waiting-for", required=True)
    p_pause.add_argument("--option", action="append", default=[], help="可重复，给出候选答案")
    p_pause.add_argument("--no-notify", action="store_true", help="跳过企微推送（联调/测试用）")
    p_pause.add_argument("--json", action="store_true")
    p_pause.set_defaults(func=_cmd_pause)

    p_resume = sub.add_parser("resume", help="记录 Shao Peishen 的答复，解除该泳道暂停")
    p_resume.add_argument("--lane", required=True)
    p_resume.add_argument("--answer", required=True)
    p_resume.add_argument("--json", action="store_true")
    p_resume.set_defaults(func=_cmd_resume)

    p_timeout = sub.add_parser("check-timeout", help="D5 解法 3：收回超时未答复的暂停泳道")
    p_timeout.add_argument("--hours", type=float, default=DEFAULT_TIMEOUT_HOURS)
    p_timeout.add_argument("--json", action="store_true")
    p_timeout.set_defaults(func=_cmd_check_timeout)

    p_summary = sub.add_parser("summary", help="D6：本批停 N 次｜逐次…一行")
    p_summary.add_argument("--batch", default=None)
    p_summary.add_argument("--json", action="store_true")
    p_summary.set_defaults(func=_cmd_summary)

    p_show = sub.add_parser("show", help="只读查看当前状态文件")
    p_show.add_argument("--lane", default=None)
    p_show.add_argument("--json", action="store_true")
    p_show.set_defaults(func=_cmd_show)

    return p


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
