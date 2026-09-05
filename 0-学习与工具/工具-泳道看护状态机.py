#!/usr/bin/env python3
"""工具-泳道看护状态机 —— lane-watch-mode §3 停/续状态机（队列 §一 `#452`，design.md D1-D7，`OP-0902-B`/`OP-0902-C` 实现）。

## 它解决的问题

🔴 **2026-09-02 架构收敛**：workflow 由三个减为两个——`zhuopin-lane-watch`
（本包，吸收 `zhuopin-lane-clearpool`）＋ `zhuopin-lan-closeout`（专管 `.51`
部署与 LAN 留步）。本包＝「他在场、自动排波推进、开跑先判 LAN 状态定候选
范围、跑到决策点即停等他一个字母」。本包**唯一新建的代码**就是这个停/续
状态机——判一个动作该不该停（D1，现为**四档**）、命中即落档＋推「等人」
通知、他答复后解除暂停、待答超时 4 小时自动收回（D5 解法 3）、开跑前判
on/off-LAN（3.5）、波间无心跳看门狗（5.6，承接 clearpool 2.3）。

## 权威判据正本

**D1-D7 全部判据以 `openspec/changes/lane-watch-mode/design.md` 为准**，本文件
是它的可执行落地，与 design 冲突时以 design 为准。D1 **四档表**（🟢／🟡／
⏭️ 转出／🔴）**逐字转录**在下方 `GREEN_ACTIONS` / `YELLOW_ACTIONS` /
`TRANSFER_ACTIONS` / `RED_ACTIONS` 四个字典里——**不得在本文件之外的地方
（opener 正文、SKILL.md）再抄一遍**，一律用 `criteria` 子命令现取，避免
两处判据表漂移。🐕 看门狗（5.6）不是 D1 的第五档——它管"还有没有信号"而
非"这个动作该不该做"，故 `TIER_WATCHDOG` 刻意不进 `_ALL_TIERS`/`criteria`
现取列表，避免与 D1 四档混淆。

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

## §三 泳道解析／dry-run（构建环境瘦身第三轮方案-2026-09-05 P2；队列 §一 `#487`）

看护件 §三 每条泳道原先内嵌完整 opener（含「做什么」「不做什么」，可达 9-16
行），P2 把它精简为 3 行——首行 `[OP-…]【…】<短名>` ＋ `【设置】` ＋ 一行读指针，
「做什么／不做什么」改写进队列行正文。`dry-run` 子命令验证这个精简不会破坏
既有的"数一批有几条泳道"能力：解析器**只依赖两个锚点**——`### A<N>` 标题
＋ 其后围栏代码块内首行非空文本 ＋ 一行 `【设置】` 开头——不依赖代码块的行数、
不要求出现"做什么"字样，3 行版与旧的长版本同样能被正确数出。

## P4 · index.lock 撞击计数（同方案 P4；队列 §一 `#487`）

七条泳道并行 + sweep + 总线各自 commit 时会撞 `.git/index.lock`。`record-lock-hit`
供任一撞锁的泳道留痕一次；`summary` 现取汇总，报「本批 index.lock 撞击 N 次」，
不再靠人工回忆有没有撞过。

## 用法

    python 0-学习与工具/工具-泳道看护状态机.py criteria
    python 0-学习与工具/工具-泳道看护状态机.py classify --action-key merge_to_master
    python 0-学习与工具/工具-泳道看护状态机.py lan-status
    python 0-学习与工具/工具-泳道看护状态机.py pause --batch 2026-09-02-看护批A \\
        --wave 2 --lane A --action-key change_criteria --waiting-for "口径该怎么改" \\
        --option 方案一 --option 方案二
    python 0-学习与工具/工具-泳道看护状态机.py transfer-out --batch 2026-09-02-看护批A \\
        --wave 2 --lane A --action-key deploy_51 --note "需部署到 .51"
    python 0-学习与工具/工具-泳道看护状态机.py resume --lane A --answer "方案一"
    python 0-学习与工具/工具-泳道看护状态机.py check-timeout
    python 0-学习与工具/工具-泳道看护状态机.py check-heartbeat --batch 2026-09-02-看护批A \\
        --wave 2 --lane A --heartbeat-file reports/lane-heartbeat/OP-xxxx.md
    python 0-学习与工具/工具-泳道看护状态机.py summary --batch 2026-09-02-看护批A
    python 0-学习与工具/工具-泳道看护状态机.py show

退出码：`classify`/`criteria`/`lan-status`/`check-timeout`/`check-heartbeat`/
`summary`/`show` 恒 0（只读/判定类，不代表业务失败）；`pause` 对 🟢/⏭️ 动作
或参数有误返回 1；`transfer-out` 对非 ⏭️ 动作返回 1；`resume` 对不在 paused
态的泳道返回 1。全部时间戳为**真 UTC**（`datetime.now(timezone.utc)`，格式
`YYYY-MM-DDTHH:MM:SSZ`），非本地时间。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
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
TIER_TRANSFER = "⏭️"
TIER_RED = "🔴"
TIER_WATCHDOG = "🐕"  # 5.6 专用；不入 _ALL_TIERS——它管信号有无，不是 D1 动作分类

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
    "change_criteria": "② 改口径/判据/阈值",
    "openspec_design_review": "③ openspec design 审",
    "close_others_queue_row": "④ 关闭他人在办队列行",
}

# 2026-09-02 架构收敛新增第四档：`.51` 部署原列 🟡（design 初稿一处真矛盾，
# 见 design.md「为什么 `.51` 部署要单独设一档」）。本包不碰生产面，命中即
# 停下标注去向、不执行，且**不进 pause/resume 问答循环**（见 transfer_out_lane）。
TRANSFER_ACTIONS = {
    "deploy_51": "`.51` 部署及任何触碰生产服务的动作",
}

RED_ACTIONS = {
    "external_send": "对外发送（跟进信／企微群／专员）",
    "l2_gate_signoff": "L2 门禁签字",
    "compliance_redline_change": "合规红线变更",
    "asil_cd_related": "ASIL C-D 相关",
}

_ALL_TIERS = {
    TIER_GREEN: GREEN_ACTIONS, TIER_YELLOW: YELLOW_ACTIONS,
    TIER_TRANSFER: TRANSFER_ACTIONS, TIER_RED: RED_ACTIONS,
}

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
    """D1 四档判据：命中已知表即返回对应档；未命中按 🟡 fail-safe（3.4）。"""
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
# LAN 探针（3.5：开跑先跑 LAN 探针定候选范围）
# ---------------------------------------------------------------------------

def _load_lan_prober() -> Callable[[], dict]:
    """按文件路径加载 `工具-未闭合产出扫描.py` 的 `probe_lan`（只读引用其既
    有 on/off-LAN 探针实现——ping `.51` ＋ 两个业务端口的 HTTP 三项判据，
    全部由该模块实现与维护；本文件不重抄一遍，避免两处判据漂移）。"""
    script = _TOOLS_DIR / "工具-未闭合产出扫描.py"
    spec = importlib.util.spec_from_file_location("_lane_watch_scanner_reuse", script)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.probe_lan


def lan_status(*, prober: Optional[Callable[[], dict]] = None) -> dict:
    """3.5：开跑先跑 LAN 探针定候选范围。`status` 三态（on/off/unknown）原样
    透传自 `probe_lan`；`effective` 是本包 fail-safe 后的二态供调用方直接
    分支——`unknown`（探针本身没跑起来）与 `off` 一律按 off-LAN 处理
    （design：探针不过 ⇒ 按 off-LAN 处理，宁可少做几项，不可对着一个不可
    达的内网瞎跑）。"""
    prober = prober if prober is not None else _load_lan_prober()
    lan = prober()
    effective = "on" if lan.get("status") == "on" else "off"
    return {**lan, "effective": effective}


# ---------------------------------------------------------------------------
# §三 泳道解析（P2）：只认两个锚点，不认行数、不认"做什么"字样
# ---------------------------------------------------------------------------

#: `### A1`／`### A12` 这类泳道标题（模块文档「§三 泳道解析」节）。
LANE_HEADING_RE = re.compile(r"^###\s+(A\d+)\b", re.MULTILINE)
#: 围栏代码块（```…```），非贪婪匹配到最近的闭合围栏。
_FENCE_BLOCK_RE = re.compile(r"```[^\n]*\n(.*?)\n```", re.DOTALL)
_SETTINGS_LINE_RE = re.compile(r"^【设置】")


def parse_section_three_lanes(text: str) -> list[dict]:
    """§三 每条 `### A<N>` 泳道解析为一条记录，只依赖两个锚点：

    1. 该标题后最近一个围栏代码块的**首行**非空（骨架首行 `[OP-…]【…】<短名>`，
       本函数不强校验具体格式，那是 `工具-opener块lint.py` 的职责，本函数只
       判"识别得出来"这一件事）；
    2. 该代码块内存在至少一行以 `【设置】` 开头。

    **不**依赖代码块行数、**不**要求出现"做什么"/"不做什么"字样——3 行精简版
    与旧的长版本（含做什么/不做什么小节）同样能被正确识别，这正是 P2 的验收点。

    返回顺序＝文中出现顺序；每条含 `lane`／`recognized`／`title_line`／
    `settings_line`／（未识别时）`reason`。找不到任何 `### A<N>` 标题时返回
    空列表（由调用方决定这是"§三没有泳道"还是"格式已漂移到解析器认不出"）。
    """
    lanes: list[dict] = []
    headings = list(LANE_HEADING_RE.finditer(text))
    for i, m in enumerate(headings):
        lane_id = m.group(1)
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        segment = text[start:end]
        fence_match = _FENCE_BLOCK_RE.search(segment)
        if fence_match is None:
            lanes.append({
                "lane": lane_id, "recognized": False,
                "reason": "标题后未找到围栏代码块", "title_line": None, "settings_line": None,
            })
            continue
        block_lines = fence_match.group(1).splitlines()
        title_line = block_lines[0].strip() if block_lines else ""
        settings_line = next((ln for ln in block_lines if _SETTINGS_LINE_RE.match(ln.strip())), None)
        if not title_line:
            lanes.append({
                "lane": lane_id, "recognized": False, "reason": "代码块首行为空",
                "title_line": title_line, "settings_line": settings_line,
            })
        elif settings_line is None:
            lanes.append({
                "lane": lane_id, "recognized": False, "reason": "代码块内无 `【设置】` 行",
                "title_line": title_line, "settings_line": settings_line,
            })
        else:
            lanes.append({
                "lane": lane_id, "recognized": True, "reason": "",
                "title_line": title_line, "settings_line": settings_line,
            })
    return lanes


# ---------------------------------------------------------------------------
# 核心动作：pause / transfer-out / resume / check-timeout / check-heartbeat / summary
# ---------------------------------------------------------------------------

def pause_lane(
    *, batch: str, wave: int, lane: str, action_key: str, waiting_for: str,
    options: Optional[list] = None, notify_fn: Optional[Callable[[str], None]] = None,
) -> dict:
    """泳道命中 🟡/🔴 决策点：落续跑状态＋推「等人」企微通知（3.1/3.2/3.4/4.2）。

    🟢 档动作不需要停，调用即报错（调用方逻辑错误，非运行时可恢复场景）。
    """
    cls = classify(action_key)
    if cls.tier in (TIER_GREEN, TIER_TRANSFER):
        reason = "不需要停" if cls.tier == TIER_GREEN else "走 transfer-out，不进问答循环"
        raise ValueError(f"{cls.tier} 档动作（{action_key}：{cls.label}）{reason}，不接受 pause。")

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


def _format_transfer_notice(*, batch: str, wave: int, lane: str, action_label: str, note: str) -> str:
    lines = [
        "**泳道看护 · 转出**",
        f"批次：{batch}　波次：{wave}　泳道：`{lane}`",
        f"动作：{action_label}",
        "去向：须走 `zhuopin-lan-closeout`，本包不执行。",
    ]
    if note:
        lines.append(f"说明：{note}")
    lines.append("> 本项不进入决策问答，泳道继续其余不依赖它的任务。")
    return "\n".join(lines)


def transfer_out_lane(
    *, batch: str, wave: int, lane: str, action_key: str, note: str = "",
    notify_fn: Optional[Callable[[str], None]] = None,
) -> dict:
    """泳道命中 ⏭️ 转出档（3.5/D1 第四档）：本包不执行该动作，只记录去向＋
    推 FYI 通知。**不进 pause/resume 问答循环**——转出没有真正要等他裁的
    判断，答案恒定是「走 zhuopin-lan-closeout」，塞进决策问答只会制造一次
    不必要的等待；泳道自身的 `status` 不变，其余不依赖这一项的任务继续跑
    （若下游确实依赖被转出的这一项，那是 opener 正文自身的责任去查状态、
    同 D3 依赖链例外的处理方式，不由本函数判断）。
    """
    cls = classify(action_key)
    if cls.tier != TIER_TRANSFER:
        raise ValueError(
            f"{action_key}（{cls.tier} {cls.label}）不是 ⏭️ 转出档动作，不接受 transfer-out。"
        )

    now = _now()

    def _mutate(data: dict) -> None:
        lanes = data["lanes"]
        lane_state = lanes.setdefault(lane, {"status": "running", "history": []})
        lane_state.setdefault("transfers", []).append({
            "batch": batch, "wave": wave, "action_key": action_key,
            "action_label": cls.label, "note": note, "recorded_at": _iso(now),
        })

    data = _with_state(_mutate)

    message = _format_transfer_notice(
        batch=batch, wave=wave, lane=lane, action_label=cls.label, note=note,
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


HEARTBEAT_STALE_MINUTES_DEFAULT = 30.0


def check_heartbeat(
    *, batch: str, wave: int, lane: str, heartbeat_file: str,
    stale_minutes: float = HEARTBEAT_STALE_MINUTES_DEFAULT,
    notify_fn: Optional[Callable[[str], None]] = None,
) -> dict:
    """5.6（承接清池 2.3）：波间看门狗。心跳文件超过 `stale_minutes` 未更新
    ⇒ 暂停后续波＋告警＋等人——**与 D1/D3 是两条不同的轴**：D1 判「这个动作
    该不该做」，D3 管「做失败了怎么办」；本函数管「还有没有信号」——分不清
    它在跑长回归还是真挂了，故一律按 pause 同款落状态＋通知处理，`tier`
    标 🐕（看门狗），不进 `criteria` 现取的 D1 四档列表。

    已在 paused 态的泳道（正等他答 D1 决策点）不重复触发——那种「没心跳」
    是预期状态（他还没回），不是失联。
    """
    path = REPO_ROOT / heartbeat_file
    age_minutes = None
    if path.exists():
        age_minutes = (time.time() - path.stat().st_mtime) / 60.0
    stale = age_minutes is None or age_minutes > stale_minutes
    detail = (
        f"心跳文件不存在：{heartbeat_file}" if age_minutes is None
        else f"最后心跳 {age_minutes:.0f} 分钟前（{heartbeat_file}）"
    )

    already_paused = False
    now = _now()

    def _mutate(data: dict) -> None:
        nonlocal already_paused
        lanes = data["lanes"]
        lane_state = lanes.setdefault(lane, {"status": "running", "history": []})
        if lane_state.get("status") == "paused":
            already_paused = True
            return
        lane_state["original_status"] = lane_state.get("status", "running")
        label = f"{stale_minutes:.0f} 分钟无心跳"
        lane_state.update({
            "status": "paused", "batch": batch, "wave": wave, "tier": TIER_WATCHDOG,
            "action_key": "heartbeat_stale", "action_label": label,
            "covered": True, "waiting_for": detail, "options": [],
            "paused_at": _iso(now), "answer": None, "answered_at": None,
        })
        lane_state.setdefault("history", []).append({
            "batch": batch, "wave": wave, "tier": TIER_WATCHDOG,
            "action_key": "heartbeat_stale", "action_label": label,
            "waiting_for": detail, "options": [], "paused_at": _iso(now),
            "answer": None, "answered_at": None, "resolved_by": None,
        })

    if stale:
        _with_state(_mutate)
        if not already_paused:
            message = "\n".join([
                "**泳道看护 · 看门狗**",
                f"批次：{batch}　波次：{wave}　泳道：`{lane}`",
                detail,
                "分不清是在跑长回归还是真挂了，已暂停后续波，等你判断。",
                "> 请回到 Cowork 会话回一个字母（本期仅认 Cowork 侧答复，D5/§8.1）。",
            ])
            _notify_best_effort(message, notify_fn)

    return {
        "lane": lane, "heartbeat_file": heartbeat_file, "stale": stale,
        "age_minutes": None if age_minutes is None else round(age_minutes, 1),
        "already_paused": already_paused, "detail": detail,
    }


def record_lock_hit(*, batch: str, wave: int, lane: str) -> dict:
    """P4（构建环境瘦身第三轮方案；队列 §一 `#487`）：泳道撞 `.git/index.lock`
    时记一次——只做计数留痕，不做任何自动重试/退避（退避策略＝opener 生成器
    默认写入的「错峰 ≥90 秒」口径文本，属另一层，本函数不越界代管）。"""
    now = _now()

    def _mutate(data: dict) -> None:
        lanes = data["lanes"]
        lane_state = lanes.setdefault(lane, {"status": "running", "history": []})
        lane_state.setdefault("lock_hits", []).append({
            "batch": batch, "wave": wave, "recorded_at": _iso(now),
        })

    data = _with_state(_mutate)
    return data["lanes"][lane]


def count_lock_hits(*, batch: Optional[str] = None) -> int:
    """D6 邻接产出：本批撞 `.git/index.lock` 共几次——现取，不靠人工回忆。"""
    data = _read_state()
    total = 0
    for lane_state in data.get("lanes", {}).values():
        for hit in lane_state.get("lock_hits", []):
            if batch and hit.get("batch") != batch:
                continue
            total += 1
    return total


def format_lock_hit_line(count: int) -> str:
    return f"本批 index.lock 撞击 {count} 次"


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


def build_transfer_summary(*, batch: Optional[str] = None) -> list:
    """D6 邻接产出：本批 ⏭️ 转出了哪些项——同样「现取，不手工数」，避免转出
    记录只活在企微通知里、事后无处可查。"""
    data = _read_state()
    rows = []
    for lane, lane_state in data.get("lanes", {}).items():
        for t in lane_state.get("transfers", []):
            if batch and t.get("batch") != batch:
                continue
            rows.append({"lane": lane, "action": t.get("action_label"), "note": t.get("note") or ""})
    return rows


def format_transfer_line(rows: list) -> str:
    if not rows:
        return "本批转出 0 项"
    parts = []
    for r in rows:
        part = f"{r['lane']}／{r['action']}"
        if r["note"]:
            part += f"／{r['note']}"
        parts.append(part)
    return f"本批转出 {len(rows)} 项（须走 zhuopin-lan-closeout）｜逐项：" + "；".join(parts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_criteria(args: argparse.Namespace) -> int:
    if args.json:
        # 🔴 直接序列化 _ALL_TIERS，不逐个手写档位字典——手写过一次就漏过
        # TIER_TRANSFER，同族「加字段忘改所有读处」，见 lan_status 模块注释。
        print(json.dumps(_ALL_TIERS, ensure_ascii=False, indent=2))
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


_LAN_RAW_TEXT = {"on": "✅ on-LAN（三项齐备）", "off": "⛔ off-LAN（三项未齐）", "unknown": "⚠ 探针不可用"}
_LAN_EFFECTIVE_TEXT = {
    "on": "全部可领活入候选（`.51` 项除外，见 D1 ⏭️ 转出档）",
    "off": "排除依赖内网的活，其余照跑，被排除项列入收工汇总「待回内网」清单",
}


def _cmd_lan_status(args: argparse.Namespace) -> int:
    lan = lan_status()
    if args.json:
        print(json.dumps(lan, ensure_ascii=False))
        return 0
    raw = _LAN_RAW_TEXT.get(lan.get("status"), "⚠ 未知")
    print(f"{raw}（原始探测）→ effective={lan['effective']}：{_LAN_EFFECTIVE_TEXT[lan['effective']]}")
    return 0


def _cmd_transfer_out(args: argparse.Namespace) -> int:
    notify_fn = (lambda _msg: None) if args.no_notify else None
    try:
        state = transfer_out_lane(
            batch=args.batch, wave=args.wave, lane=args.lane, action_key=args.action_key,
            note=args.note, notify_fn=notify_fn,
        )
    except ValueError as exc:
        print(f"✗ {exc}")
        return 1
    label = TRANSFER_ACTIONS.get(args.action_key, args.action_key)
    print(f"⏭ 已记录转出：泳道 `{args.lane}`「{label}」须走 zhuopin-lan-closeout，本包不执行。")
    if args.json:
        print(json.dumps(state, ensure_ascii=False))
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


def _cmd_check_heartbeat(args: argparse.Namespace) -> int:
    result = check_heartbeat(
        batch=args.batch, wave=args.wave, lane=args.lane, heartbeat_file=args.heartbeat_file,
        stale_minutes=args.stale_minutes,
    )
    if not result["stale"]:
        print(f"✓ 泳道 `{args.lane}` 心跳正常（{result['detail']}）。")
    elif result["already_paused"]:
        print(f"⏸ 泳道 `{args.lane}` 已在 paused 态，看门狗不重复触发（{result['detail']}）。")
    else:
        print(f"🐕 泳道 `{args.lane}` 心跳超时，已暂停等你：{result['detail']}")
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    return 0


def _cmd_summary(args: argparse.Namespace) -> int:
    rows = build_summary(batch=args.batch)
    print(format_summary_line(rows))
    transfer_rows = build_transfer_summary(batch=args.batch)
    print(format_transfer_line(transfer_rows))
    lock_hits = count_lock_hits(batch=args.batch)
    print(format_lock_hit_line(lock_hits))
    if args.json:
        print(json.dumps(
            {"stops": rows, "transfers": transfer_rows, "lock_hits": lock_hits},
            ensure_ascii=False,
        ))
    return 0


def _cmd_record_lock_hit(args: argparse.Namespace) -> int:
    state = record_lock_hit(batch=args.batch, wave=args.wave, lane=args.lane)
    total = len(state.get("lock_hits", []))
    print(f"已记录：泳道 `{args.lane}` 本批第 {total} 次撞 index.lock。")
    if args.json:
        print(json.dumps(state, ensure_ascii=False))
    return 0


def _cmd_dry_run(args: argparse.Namespace) -> int:
    text = Path(args.file).read_text(encoding="utf-8")
    lanes = parse_section_three_lanes(text)
    recognized = [l for l in lanes if l["recognized"]]
    print(f"§三 解出泳道 {len(recognized)}／{len(lanes)} 条")
    for lane in lanes:
        if not lane["recognized"]:
            print(f"  ✗ {lane['lane']}：{lane['reason']}")
    if args.json:
        print(json.dumps(lanes, ensure_ascii=False, indent=2))
    return 0 if lanes and len(recognized) == len(lanes) else 1


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

    p_criteria = sub.add_parser("criteria", help="打印 D1 四档判据表（单一可信源，opener 引用本命令而非复述）")
    p_criteria.add_argument("--json", action="store_true")
    p_criteria.set_defaults(func=_cmd_criteria)

    p_classify = sub.add_parser("classify", help="给一个动作 key 判定档位")
    p_classify.add_argument("--action-key", required=True)
    p_classify.add_argument("--json", action="store_true")
    p_classify.set_defaults(func=_cmd_classify)

    p_lan = sub.add_parser("lan-status", help="3.5：LAN 探针（只读引用未闭合产出扫描器），定批次候选范围")
    p_lan.add_argument("--json", action="store_true")
    p_lan.set_defaults(func=_cmd_lan_status)

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

    p_transfer = sub.add_parser("transfer-out", help="泳道命中 ⏭️ 转出档：记录去向＋推 FYI，不进问答循环")
    p_transfer.add_argument("--batch", required=True)
    p_transfer.add_argument("--wave", type=int, required=True)
    p_transfer.add_argument("--lane", required=True)
    p_transfer.add_argument("--action-key", required=True)
    p_transfer.add_argument("--note", default="")
    p_transfer.add_argument("--no-notify", action="store_true", help="跳过企微推送（联调/测试用）")
    p_transfer.add_argument("--json", action="store_true")
    p_transfer.set_defaults(func=_cmd_transfer_out)

    p_resume = sub.add_parser("resume", help="记录 Shao Peishen 的答复，解除该泳道暂停")
    p_resume.add_argument("--lane", required=True)
    p_resume.add_argument("--answer", required=True)
    p_resume.add_argument("--json", action="store_true")
    p_resume.set_defaults(func=_cmd_resume)

    p_timeout = sub.add_parser("check-timeout", help="D5 解法 3：收回超时未答复的暂停泳道")
    p_timeout.add_argument("--hours", type=float, default=DEFAULT_TIMEOUT_HOURS)
    p_timeout.add_argument("--json", action="store_true")
    p_timeout.set_defaults(func=_cmd_check_timeout)

    p_hb = sub.add_parser("check-heartbeat", help="5.6：波间看门狗——心跳文件超过阈值未更新即暂停等人")
    p_hb.add_argument("--batch", required=True)
    p_hb.add_argument("--wave", type=int, required=True)
    p_hb.add_argument("--lane", required=True)
    p_hb.add_argument("--heartbeat-file", required=True, help="相对仓库根路径，如 reports/lane-heartbeat/OP-xxxx.md")
    p_hb.add_argument("--stale-minutes", type=float, default=HEARTBEAT_STALE_MINUTES_DEFAULT)
    p_hb.add_argument("--json", action="store_true")
    p_hb.set_defaults(func=_cmd_check_heartbeat)

    p_summary = sub.add_parser("summary", help="D6：本批停 N 次｜逐次…一行 ＋ 本批转出 N 项一行")
    p_summary.add_argument("--batch", default=None)
    p_summary.add_argument("--json", action="store_true")
    p_summary.set_defaults(func=_cmd_summary)

    p_show = sub.add_parser("show", help="只读查看当前状态文件")
    p_show.add_argument("--lane", default=None)
    p_show.add_argument("--json", action="store_true")
    p_show.set_defaults(func=_cmd_show)

    p_lock = sub.add_parser("record-lock-hit", help="P4：泳道撞 .git/index.lock 记一次，供 summary 现取汇总")
    p_lock.add_argument("--batch", required=True)
    p_lock.add_argument("--wave", type=int, required=True)
    p_lock.add_argument("--lane", required=True)
    p_lock.add_argument("--json", action="store_true")
    p_lock.set_defaults(func=_cmd_record_lock_hit)

    p_dry = sub.add_parser("dry-run", help="P2：对看护件 §三 跑一遍泳道解析，报解出条数与未识别原因")
    p_dry.add_argument("--file", required=True, help="看护件仓库根相对或绝对路径")
    p_dry.add_argument("--json", action="store_true")
    p_dry.set_defaults(func=_cmd_dry_run)

    return p


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
