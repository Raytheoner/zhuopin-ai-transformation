"""Token 用量零度量基线（队列 §一 `#580`，`OP-0916-T`，2026-09-16）。

**要治的病**：Antigravity 报告给出组织级用量数字（26,166 次请求、45.8 亿
cache_read），但本仓从未解析过 `~/.claude/projects/**/*.jsonl`（CC 本机会话
的原始事实来源）——模型分布、上下文峰值、开场底噪、机制税四项此前**只能
凭印象，没有机器可读的独立复核**。本工具只读解析这批 jsonl，产出周报，
供 Phase 1-6 用作验收分母（见 `1-转型规划/0-全景路线图/
构建Token消耗优化-核验与路线图-2026-09-16.md` §Phase 0）。

--------------------------------------------------------------------------
🔴 三条硬边界
--------------------------------------------------------------------------

**⑴ 只读、不调用任何模型。** 唯一写动作是 `--out`／`--json-out` 指定的报告
文件；不改、不删任何 `.jsonl` 原始记录。

**⑵ 同一 requestId 的多行必须去重，取末条。** 本机 CC 会话日志把一次 API
请求的每个 content block（thinking／text／tool_use）各写一行、共享同一
`requestId`（`message.id` 兜底），且每行都重复整条消息的 `usage` 快照——
不去重会把请求数与 token 数按内容块数放大好几倍。工具调用数不受此影响：
每个 `tool_use` 块本就只出现一行，照原样计数即可，**不能套用同一套去重
逻辑**（那样会把并行工具调用也去重掉）。

**⑶ 开场底噪只认「本窗口内新起的会话」。** 「首次请求 input+cache 总量」
量的是新会话开场的固定成本；若把窗口中段某个老会话的某次请求误当「首次」，
量出来的是压缩/续接后的峰值，不是开场成本。故先看会话在整份文件里的
**真实第一条**请求，只有它的日期落在 `[--since, --until]` 内才计入分布——
文件仍需通读到尾（窗口过滤只管「算不算」，不管「读不读」）。

--------------------------------------------------------------------------
指标口径（写死，来自路线图 §Phase 0，改动须过 Shao Peishen）
--------------------------------------------------------------------------

1. 按日、按模型统计 input / cache_creation / cache_read / output 与请求数
2. 🔴 按「链」统计，不按 sessionId：Agent 子泳道 jsonl（`<会话目录>/subagents/
   *.jsonl`）与主会话 jsonl 共享同一 `sessionId` 字段——若直接按 sessionId
   分组会把「一条主链＋N 条子泳道」全部塌成一行。统计单位改为**文件**（每
   个 jsonl 文件＝一条链），每条链标 `chain_type`（主链／子泳道）与
   `parent_session_id`（子泳道＝其所属会话目录名，主链＝自身）；另出一张
   按 `parent_session_id` 合计的表（主链＋其全部子泳道相加）。请求数、工具
   调用数、上下文峰值（单条请求 input+cache 之和的最大值）、累计
   cache_read 口径不变；Top N（默认 20）按窗口内总 token 降序，附首条用户
   消息前 60 字作为标题（子泳道的首条用户消息通常是派单 prompt 本身）
3. 开场底噪：本窗口内新起会话的首次请求 input+cache 总量，报 P50/P95
4. 机制税：Bash 命令命中机制工具白名单的占比（白名单口径同
   `0-学习与工具/hooks/hooks-pretooluse-queue-read-guard.ps1::AllowlistedToolScripts`，
   见 `reports/hooks-audit.jsonl` 「命中机制工具白名单」历史记录佐证）
5. 看护会话识别：满足其一即算——⑴ 首条用户消息**前 60 字**（同 §二 展示口径）
   含「看护」；⑵ Bash 命令命中
   `check-heartbeat|check-timeout|heartbeat|summary|泳道看护状态机\\.py`
   （覆盖 `lane-heartbeat`／`Get-Content …heartbeat` 等轮询形态）且占比
   > 30%。原判据只认 ⑵ 且正则过窄，漏掉标题即含「看护」但未必高频调用
   看护脚本的链；⑴ 判据只看**前 60 字**、不搜全文——建造类 opener 正文里
   普遍带「看护者 OP-xxx」溯源尾注，搜全文会把大多数建造链也误判成看护链

用法
--------------------------------------------------------------------------

    python 0-学习与工具/工具-Token用量度量.py --since 2026-09-06 --until 2026-09-13

    # 与 Antigravity 报告对账（可选，仅影响报告 §六 的对比表，不影响其余指标）
    python 0-学习与工具/工具-Token用量度量.py --since 2026-09-06 --until 2026-09-13 \\
        --antigravity-requests 26166 --antigravity-cache-read 4580000000
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# ── 机制工具白名单（口径同 hooks-pretooluse-queue-read-guard.ps1，🔴 改它须两处同改） ──
MECHANISM_TOOL_NAMES = [
    "工具-共享文档编辑锁.py",
    "工具-队列查询.py",
    "工具-落库sweep.py",
    "工具-队列结构lint.py",
    "工具-跟进信README登记.py",
    "工具-跟进信README归档.py",
    "工具-跟进信README查询.py",
    "工具-跟进信README行长外置.py",
]
_MECHANISM_RE = re.compile("|".join(re.escape(name) for name in MECHANISM_TOOL_NAMES))

# 看护会话识别：Bash 命令命中即算一次「看护类调用」（`heartbeat` 已覆盖
# `check-heartbeat`／`lane-heartbeat`／`Get-Content …heartbeat` 等轮询形态）
WATCHER_CMD_RE = re.compile(r"check-heartbeat|check-timeout|heartbeat|summary|泳道看护状态机\.py")
# 标题判据：首条用户消息含「看护」即直接判定，不受 Bash 占比阈值约束
WATCHER_TITLE_RE = re.compile(r"看护")
WATCHER_THRESHOLD = 0.30  # 🔴 口径判据，改它须 Shao Peishen 拍板


# ══════════════════════════════════════════════════════════════════════════
# 数据结构
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class ReqUsage:
    ts: datetime
    day: date
    model: str
    input_tokens: int = 0
    cache_creation: int = 0
    cache_read: int = 0
    output_tokens: int = 0

    @property
    def context_total(self) -> int:
        return self.input_tokens + self.cache_creation + self.cache_read

    @property
    def total(self) -> int:
        return self.context_total + self.output_tokens


@dataclass
class ToolCall:
    ts: datetime
    day: date
    name: str
    command: str = ""


@dataclass
class SessionData:
    session_id: str          # 链标识：主链＝文件名（＝真实 sessionId）；子泳道＝
                              # "<所属会话目录名>/subagents/<文件名>"，与主链的
                              # session_id 不会撞（避免同一 parent_session_id 下
                              # 多条链被误判成同一行，见模块 docstring 指标口径 2）
    file: Path
    chain_type: str = "主链"  # "主链" | "子泳道"
    parent_session_id: str = ""  # 所属会话（子泳道＝派它出去的主会话；主链＝自身）
    first_user_text: str = ""
    # 按文件内出现顺序去重后的请求（每 requestId 一条，取末条 usage）
    requests_order: list = field(default_factory=list)   # list[str]，requestId 出现顺序
    requests_by_id: dict = field(default_factory=dict)    # requestId -> ReqUsage
    tool_calls: list = field(default_factory=list)        # list[ToolCall]，原样计数不去重
    bad_json_lines: int = 0

    def ordered_requests(self) -> list:
        return [self.requests_by_id[rid] for rid in self.requests_order
                if rid in self.requests_by_id]


@dataclass
class Gap:
    kind: str
    source: str
    line_no: int
    detail: str = ""


SAMPLE_CAP = 5
GAP_KINDS = {
    "bad_json": "格式不一 · 非合法 JSON 行",
    "unreadable": "文件不存在或读取失败",
    "no_timestamp": "assistant 记录缺 timestamp",
    "bad_timestamp": "timestamp 无法解析",
}


# ══════════════════════════════════════════════════════════════════════════
# 扫描
# ══════════════════════════════════════════════════════════════════════════

def parse_ts(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def to_local_day(dt: datetime, basis: str) -> date:
    if basis == "utc":
        return dt.astimezone(timezone.utc).date()
    return dt.astimezone().date()   # 本机时区


def _chain_identity(path: Path) -> tuple[str, str, str]:
    """按文件路径判「链」身份，不依赖行内 `sessionId`字段（该字段在子泳道
    jsonl 里就是父会话的 sessionId，两者相同，不能拿它当链的唯一标识）。

    返回 (chain_id, chain_type, parent_session_id)。子泳道文件路径形如
    `<会话目录>/subagents/agent-xxx.jsonl`；主链文件路径形如
    `<会话目录>.jsonl`（文件名本身即 sessionId）。
    """
    if path.parent.name == "subagents":
        parent_session_id = path.parent.parent.name
        chain_id = f"{parent_session_id}/subagents/{path.stem}"
        return chain_id, "子泳道", parent_session_id
    return path.stem, "主链", path.stem


def scan_file(path: Path, basis: str, gaps: dict, gap_samples: dict) -> SessionData | None:
    """逐行流式扫一条链（一个 jsonl 文件）；返回全量（未按窗口过滤）聚合。"""
    chain_id, chain_type, parent_session_id = _chain_identity(path)
    sess = SessionData(session_id=chain_id, file=path,
                        chain_type=chain_type, parent_session_id=parent_session_id)
    try:
        fh = open(path, "r", encoding="utf-8", errors="replace")
    except OSError:
        gaps["unreadable"] += 1
        return None
    with fh:
        for line_no, raw_line in enumerate(fh, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                gaps["bad_json"] += 1
                if len(gap_samples["bad_json"]) < SAMPLE_CAP:
                    gap_samples["bad_json"].append(f"{path.name}:{line_no}")
                sess.bad_json_lines += 1
                continue
            if not isinstance(rec, dict):
                continue
            rec_type = rec.get("type")

            if rec_type == "user" and not sess.first_user_text:
                msg = rec.get("message") or {}
                content = msg.get("content")
                if isinstance(content, str) and content.strip():
                    sess.first_user_text = content.strip()

            if rec_type != "assistant":
                continue
            msg = rec.get("message") or {}
            ts_raw = rec.get("timestamp")
            dt = parse_ts(ts_raw)
            if dt is None:
                gaps["no_timestamp" if not ts_raw else "bad_timestamp"] += 1
                key = "no_timestamp" if not ts_raw else "bad_timestamp"
                if len(gap_samples[key]) < SAMPLE_CAP:
                    gap_samples[key].append(f"{path.name}:{line_no}")
                continue
            day = to_local_day(dt, basis)

            rid = rec.get("requestId") or msg.get("id")
            usage = msg.get("usage") or {}
            model = msg.get("model") or "?"
            if rid:
                if rid not in sess.requests_by_id:
                    sess.requests_order.append(rid)
                # 🔴 取末条：同一 requestId 反复出现时，后一条覆盖前一条
                sess.requests_by_id[rid] = ReqUsage(
                    ts=dt, day=day, model=model,
                    input_tokens=int(usage.get("input_tokens") or 0),
                    cache_creation=int(usage.get("cache_creation_input_tokens") or 0),
                    cache_read=int(usage.get("cache_read_input_tokens") or 0),
                    output_tokens=int(usage.get("output_tokens") or 0),
                )

            for block in msg.get("content") or []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    name = str(block.get("name") or "?")
                    command = ""
                    if name == "Bash":
                        command = str((block.get("input") or {}).get("command") or "")
                    sess.tool_calls.append(ToolCall(ts=dt, day=day, name=name, command=command))
    return sess


# ══════════════════════════════════════════════════════════════════════════
# 聚合
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class Aggregate:
    since: date
    until: date
    # (day, model) -> 累加
    daily_model: dict = field(default_factory=lambda: defaultdict(lambda: defaultdict(int)))
    # 链汇总（仅窗口内活动的链；一条链＝一个 jsonl 文件，见 `_chain_identity`）
    session_rows: list = field(default_factory=list)
    # 按 parent_session_id 合计（主链＋其全部子泳道相加）
    parent_totals: dict = field(default_factory=lambda: defaultdict(lambda: defaultdict(int)))
    parent_titles: dict = field(default_factory=dict)  # parent_session_id -> 标题（优先取主链）
    # 开场底噪：窗口内新起会话的首次请求 context_total
    opening_noise: list = field(default_factory=list)
    # 机制税（全局）
    bash_total: int = 0
    bash_mechanism_hits: int = 0
    watcher_sessions: list = field(default_factory=list)
    gaps: dict = field(default_factory=lambda: defaultdict(int))
    gap_samples: dict = field(default_factory=lambda: defaultdict(list))
    files_scanned: int = 0
    files_unreadable: int = 0

    def in_window(self, d: date) -> bool:
        return self.since <= d <= self.until


def aggregate_session(sess: SessionData, agg: Aggregate) -> None:
    all_reqs = sess.ordered_requests()
    if all_reqs:
        first = all_reqs[0]
        if agg.in_window(first.day):
            agg.opening_noise.append(first.context_total)

    win_reqs = [r for r in all_reqs if agg.in_window(r.day)]
    win_calls = [c for c in sess.tool_calls if agg.in_window(c.day)]
    if not win_reqs and not win_calls:
        return

    for r in win_reqs:
        bucket = agg.daily_model[(r.day, r.model)]
        bucket["requests"] += 1
        bucket["input"] += r.input_tokens
        bucket["cache_creation"] += r.cache_creation
        bucket["cache_read"] += r.cache_read
        bucket["output"] += r.output_tokens

    bash_calls = [c for c in win_calls if c.name == "Bash"]
    mechanism_hits = sum(1 for c in bash_calls if _MECHANISM_RE.search(c.command))
    watcher_hits = sum(1 for c in bash_calls if WATCHER_CMD_RE.search(c.command))
    agg.bash_total += len(bash_calls)
    agg.bash_mechanism_hits += mechanism_hits

    title = sess.first_user_text[:60].replace("\n", " ").replace("\r", " ")

    # 看护识别：标题含「看护」／Bash 占比超阈值，命中其一即算（见模块口径 5）。
    # 🔴 标题判据只认「首条用户消息前 60 字」（同 §二 展示口径），不搜全文——
    # 派单 opener 正文里几乎都有「派出线：… ｜ 看护者 OP-xxx」这类溯源尾注，
    # 若搜全文会把绝大多数建造类主链也当成看护链（实测：全文口径命中 123／
    # 177 条、cache_read 占比 67.3%，与 §〇 人工复核基线「24 条／14.4%」严重
    # 不符；改搜前 60 字后才对齐，因为看护 opener 的标注习惯是「看护」二字
    # 出现在标题最前面，如 `[OP-0907-Y]【CC】看护B-0907_Y`）。
    ratio = (watcher_hits / len(bash_calls)) if bash_calls else 0.0
    by_title = bool(WATCHER_TITLE_RE.search(title))
    by_ratio = bool(bash_calls) and ratio > WATCHER_THRESHOLD
    if by_title or by_ratio:
        reason = "标题含看护+Bash占比" if (by_title and by_ratio) else ("标题含看护" if by_title else "Bash占比")
        agg.watcher_sessions.append({
            "session_id": sess.session_id, "parent_session_id": sess.parent_session_id,
            "chain_type": sess.chain_type, "reason": reason, "ratio": ratio,
            "watcher_calls": watcher_hits, "bash_calls": len(bash_calls),
        })

    context_peak = max((r.context_total for r in win_reqs), default=0)
    cache_read_sum = sum(r.cache_read for r in win_reqs)
    total_tokens = sum(r.total for r in win_reqs)
    agg.session_rows.append({
        "session_id": sess.session_id,
        "chain_type": sess.chain_type,
        "parent_session_id": sess.parent_session_id,
        "title": title,
        "requests": len(win_reqs),
        "tool_calls": len(win_calls),
        "context_peak": context_peak,
        "cache_read_sum": cache_read_sum,
        "total_tokens": total_tokens,
        "bash_calls": len(bash_calls),
        "bash_mechanism_hits": mechanism_hits,
    })

    parent_id = sess.parent_session_id or sess.session_id
    pbucket = agg.parent_totals[parent_id]
    pbucket["chains"] += 1
    pbucket["requests"] += len(win_reqs)
    pbucket["tool_calls"] += len(win_calls)
    pbucket["cache_read_sum"] += cache_read_sum
    pbucket["total_tokens"] += total_tokens
    pbucket["bash_calls"] += len(bash_calls)
    pbucket["bash_mechanism_hits"] += mechanism_hits
    # 标题优先取主链；主链尚未出现前，暂用先扫到的那条子泳道占位，扫到主链即覆盖
    if title and (sess.chain_type == "主链" or parent_id not in agg.parent_titles):
        agg.parent_titles[parent_id] = title


def percentile(values: list, pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * pct
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return float(s[f])
    return s[f] + (s[c] - s[f]) * (k - f)


# ══════════════════════════════════════════════════════════════════════════
# 报告
# ══════════════════════════════════════════════════════════════════════════

def render_markdown(agg: Aggregate, args, root: Path) -> str:
    L: list = []
    now = datetime.now().astimezone()
    basis_txt = "本地时区" if args.date_basis == "local" else "UTC"
    L.append("# Token 用量零度量基线报告")
    L.append("")
    L.append(f"- 生成时刻：`{now.isoformat(timespec='seconds')}`（本地时区）")
    L.append(f"- 窗口：**{args.since} ～ {args.until}**（含首尾，归日基准：{basis_txt}）")
    L.append(f"- 解析根：`{root}`")
    L.append(f"- 扫描文件数：{agg.files_scanned}（不可读 {agg.files_unreadable}）")
    L.append("- 🔴 本报告**只读**：不调用任何模型，不改写任何 `.jsonl`。")
    L.append("")

    # ── 一 按日 × 模型 ──
    L.append("## 一 · 按日 × 模型 汇总")
    L.append("")
    L.append("| 日期 | 模型 | 请求数 | input | cache_creation | cache_read | output |")
    L.append("|---|---|---:|---:|---:|---:|---:|")
    rows_sorted = sorted(agg.daily_model.items(), key=lambda kv: (kv[0][0], kv[0][1]))
    tot_req = tot_in = tot_cc = tot_cr = tot_out = 0
    for (day, model), v in rows_sorted:
        L.append(f"| {day} | {model} | {v['requests']:,} | {v['input']:,} | "
                 f"{v['cache_creation']:,} | {v['cache_read']:,} | {v['output']:,} |")
        tot_req += v["requests"]; tot_in += v["input"]; tot_cc += v["cache_creation"]
        tot_cr += v["cache_read"]; tot_out += v["output"]
    L.append(f"| **合计** | — | **{tot_req:,}** | **{tot_in:,}** | **{tot_cc:,}** | "
             f"**{tot_cr:,}** | **{tot_out:,}** |")
    L.append("")

    # ── 二 按链统计 Top N（一个 jsonl 文件＝一条链；主链／子泳道分开列） ──
    top_n = args.top_n
    ranked = sorted(agg.session_rows, key=lambda r: -r["total_tokens"])
    L.append(f"## 二 · 按链统计 Top {top_n}（按窗口内总 token 降序；主链＋子泳道各占一行）")
    L.append("")
    L.append(f"- 窗口内有活动的链数：**{len(agg.session_rows)}**")
    L.append("")
    L.append("| 链（首条用户消息前 60 字） | 类型 | 父会话 | 请求数 | 工具调用数 | 上下文峰值 | 累计 cache_read | 总 token |")
    L.append("|---|---|---|---:|---:|---:|---:|---:|")
    for r in ranked[:top_n]:
        title = r["title"] or f"`{r['session_id'][:8]}`（无可提取的首条用户文本）"
        L.append(f"| {title} | {r['chain_type']} | `{r['parent_session_id'][:8]}` | {r['requests']:,} | {r['tool_calls']:,} | "
                 f"{r['context_peak']:,} | {r['cache_read_sum']:,} | {r['total_tokens']:,} |")
    if not ranked:
        L.append("| _窗口内无链活动_ | | | | | | | |")
    L.append("")

    # ── 二B 按父会话合计（主链＋其全部子泳道相加） ──
    parent_ranked = sorted(agg.parent_totals.items(), key=lambda kv: -kv[1]["total_tokens"])
    L.append(f"## 二B · 按父会话合计 Top {top_n}（主链＋其全部子泳道相加）")
    L.append("")
    L.append(f"- 窗口内出现过活动的父会话数：**{len(agg.parent_totals)}**")
    L.append("")
    L.append("| 父会话（标题取主链，无主链时取先扫到的子泳道） | 链数 | 请求数 | 工具调用数 | 累计 cache_read | 总 token |")
    L.append("|---|---:|---:|---:|---:|---:|")
    for parent_id, v in parent_ranked[:top_n]:
        title = agg.parent_titles.get(parent_id, "") or f"`{parent_id[:8]}`（无可提取的首条用户文本）"
        L.append(f"| {title} | {v['chains']:,} | {v['requests']:,} | {v['tool_calls']:,} | "
                 f"{v['cache_read_sum']:,} | {v['total_tokens']:,} |")
    if not parent_ranked:
        L.append("| _窗口内无父会话活动_ | | | | | |")
    L.append("")

    # ── 三 开场底噪 ──
    L.append("## 三 · 开场底噪（窗口内新起会话，首次请求 input+cache 总量）")
    L.append("")
    n = len(agg.opening_noise)
    p50 = percentile(agg.opening_noise, 0.50)
    p95 = percentile(agg.opening_noise, 0.95)
    L.append(f"- 窗口内新起会话数：**{n}**")
    L.append(f"- P50：**{p50:,.0f}** ｜ P95：**{p95:,.0f}**")
    L.append("")

    # ── 四 机制税 ──
    ratio = (agg.bash_mechanism_hits / agg.bash_total) if agg.bash_total else 0.0
    L.append("## 四 · 机制税（Bash 命中机制工具白名单的占比）")
    L.append("")
    L.append(f"- 窗口内 Bash 调用总数：**{agg.bash_total:,}**")
    L.append(f"- 命中白名单：**{agg.bash_mechanism_hits:,}**（{ratio:.1%}）")
    L.append("- 白名单口径：" + "、".join(f"`{name}`" for name in MECHANISM_TOOL_NAMES))
    L.append("")
    mech_ranked = sorted(
        [r for r in agg.session_rows if r["bash_calls"] > 0],
        key=lambda r: -(r["bash_mechanism_hits"] / r["bash_calls"]))[:top_n]
    if mech_ranked:
        L.append(f"Top {len(mech_ranked)} 机制税占比最高的链：")
        L.append("")
        L.append("| 链 | Bash 调用数 | 命中白名单 | 占比 |")
        L.append("|---|---:|---:|---:|")
        for r in mech_ranked:
            pct = r["bash_mechanism_hits"] / r["bash_calls"]
            title = r["title"] or f"`{r['session_id'][:8]}`"
            L.append(f"| {title} | {r['bash_calls']:,} | {r['bash_mechanism_hits']:,} | {pct:.1%} |")
        L.append("")

    # ── 五 看护链识别 ──
    L.append(f"## 五 · 看护链识别（首条用户消息含「看护」，或 Bash 命中 "
             f"`check-heartbeat\\|check-timeout\\|heartbeat\\|summary\\|泳道看护状态机\\.py` "
             f"占比 > {WATCHER_THRESHOLD:.0%}，命中其一即算）")
    L.append("")
    if agg.watcher_sessions:
        watcher_cache_read = sum(
            r["cache_read_sum"] for r in agg.session_rows
            if r["session_id"] in {w["session_id"] for w in agg.watcher_sessions})
        pct_of_total = (watcher_cache_read / tot_cr) if tot_cr else 0.0
        L.append(f"命中 **{len(agg.watcher_sessions)}** 条链，合计 cache_read **{watcher_cache_read:,}**"
                 f"（占窗口总量 {pct_of_total:.1%}）：")
        L.append("")
        L.append("| 链 | 类型 | 父会话 | 命中依据 | 看护类 Bash 调用 | Bash 调用总数 | 占比 |")
        L.append("|---|---|---|---|---:|---:|---:|")
        for w in sorted(agg.watcher_sessions, key=lambda x: -x["ratio"]):
            L.append(f"| `{w['session_id'][:8]}` | {w['chain_type']} | `{w['parent_session_id'][:8]}` | "
                     f"{w['reason']} | {w['watcher_calls']} | {w['bash_calls']} | {w['ratio']:.1%} |")
    else:
        L.append("_窗口内未命中任何看护链。_")
    L.append("")

    # ── 六 与 Antigravity 对账 ──
    L.append("## 六 · 与 Antigravity 报告对账")
    L.append("")
    if args.antigravity_requests is not None or args.antigravity_cache_read is not None:
        L.append("| 指标 | 本机实测（本窗口） | Antigravity 报告 | 差异 |")
        L.append("|---|---:|---:|---:|")
        if args.antigravity_requests is not None:
            diff = tot_req - args.antigravity_requests
            pct = (tot_req / args.antigravity_requests) if args.antigravity_requests else 0
            L.append(f"| 请求数 | {tot_req:,} | {args.antigravity_requests:,} | "
                     f"{diff:+,}（本机占比 {pct:.1%}） |")
        if args.antigravity_cache_read is not None:
            diff = tot_cr - args.antigravity_cache_read
            pct = (tot_cr / args.antigravity_cache_read) if args.antigravity_cache_read else 0
            L.append(f"| cache_read | {tot_cr:,} | {args.antigravity_cache_read:,} | "
                     f"{diff:+,}（本机占比 {pct:.1%}） |")
        L.append("")
        L.append("**差异原因**：本工具只解析**本机** `~/.claude/projects/**/*.jsonl`；"
                 "Antigravity 报告的数字是**组织级**用量（同一 Anthropic 账户下所有机器／"
                 "云端 session 的合计）。本次窗口内实测同时发现多条 `model:\"<synthetic>\"` "
                 "限额拒绝记录，字段 `quotaLimits.overageDisabledReason=\"org_level_disabled\"` "
                 "与 `rateLimitType` 覆盖 `seven_day`（周）与月度两种——**直接证实用量与限额都在"
                 "组织级核算，本机只是分母的一部分**，故本机数字系统性小于 Antigravity 报告属"
                 "预期内差异，不是解析遗漏。")
        L.append("")
    else:
        L.append("_未传 `--antigravity-requests`／`--antigravity-cache-read`，跳过对账表；"
                 "口径见上方「差异原因」写法，供下次传参复用。_")
        L.append("")

    # ── 七 缺口与边界 ──
    L.append("## 七 · 缺口与边界")
    L.append("")
    if agg.gaps:
        L.append("| 缺口类别 | 命中条数 | 样本 |")
        L.append("|---|---:|---|")
        for kind, cnt in sorted(agg.gaps.items(), key=lambda kv: -kv[1]):
            samples = "；".join(agg.gap_samples.get(kind, []))
            L.append(f"| {GAP_KINDS.get(kind, kind)} | {cnt} | {samples or '—'} |")
    else:
        L.append("_未发现缺口。_")
    L.append("")
    L.append("- 只统计**本机**会话日志；跨机／云端 session 不在本工具可见范围内（见 §六）。")
    L.append("- 「工具调用数」统计全部 `tool_use` 块，不限于 Bash；「机制税」「看护会话识别」"
             "两项只看 Bash 命令行文本。")
    L.append("- 开场底噪只统计**窗口内新起**的会话（真实首条请求落在窗口内），"
             "跨窗口边界续接的老会话不计入。")
    L.append("")
    return "\n".join(L)


# ══════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════

def _find_repo_root_by_markers(start: Path) -> Path:
    """保底：跑不了 git 时按目录标记向上探测（原逻辑，仅作兜底）。"""
    for p in [start, *start.parents]:
        if (p / "CLAUDE.md").exists() and (p / "0-学习与工具").is_dir():
            return p
    return start


def find_repo_root(start: Path) -> Path:
    """主工作区根目录，手法同 `工具-共享文档编辑锁.py::_resolve_repo_root`：
    `git rev-parse --git-common-dir` 不论在主工作区还是任一 linked worktree
    里跑，都解到同一个共享 `.git` 目录，其父目录即主工作区根。🔴 若按目录
    标记向上探测（原逻辑），在 worktree 内跑会探到 worktree 自己那份完整
    checkout（同样有 `CLAUDE.md` 与 `0-学习与工具`），导致 `--out` 缺省落进
    worktree、收工删 worktree 时报告随之丢失（`#580` 09-16 09:14 实撞，已由
    Cowork 在主仓重跑找回）。"""
    start_dir = start if start.is_dir() else start.parent
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=start_dir, capture_output=True, text=True, check=True,
        )
        return Path(result.stdout.strip()).parent
    except (subprocess.CalledProcessError, OSError, FileNotFoundError):
        return _find_repo_root_by_markers(start)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Token 用量零度量基线（队列 #580）——只读解析 ~/.claude/projects/**/*.jsonl。",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default="", metavar="PATH",
                    help="jsonl 根目录，默认取本机 USERPROFILE/.claude/projects")
    ap.add_argument("--since", required=True, metavar="YYYY-MM-DD", help="窗口起（含）")
    ap.add_argument("--until", required=True, metavar="YYYY-MM-DD", help="窗口止（含）")
    ap.add_argument("--date-basis", choices=("local", "utc"), default="local",
                    help="归日基准（默认 local；jsonl 时间戳本身是 UTC）")
    ap.add_argument("--top-n", type=int, default=20, help="Top N 会话（默认 20）")
    ap.add_argument("--out", default="", metavar="PATH",
                    help="报告落盘路径；缺省写 reports/token-usage-<起>-<止>.md")
    ap.add_argument("--json-out", default="", metavar="PATH",
                    help="机器消费 JSON 落盘路径；缺省与 --out 同名 .json")
    ap.add_argument("--repo-root", default="", help="仓库根（默认自本文件向上探测）")
    ap.add_argument("--antigravity-requests", type=int, default=None,
                    help="Antigravity 报告的请求数，用于 §六 对账（可选）")
    ap.add_argument("--antigravity-cache-read", type=int, default=None,
                    help="Antigravity 报告的 cache_read 总量，用于 §六 对账（可选）")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        since = date.fromisoformat(args.since)
        until = date.fromisoformat(args.until)
    except ValueError as exc:
        print(f"错误：--since/--until 不是合法日期：{exc}", file=sys.stderr)
        return 2
    if since > until:
        print("错误：--since 不能晚于 --until。", file=sys.stderr)
        return 2

    root = Path(args.root) if args.root else Path.home() / ".claude" / "projects"
    if not root.is_dir():
        print(f"错误：解析根不存在或不是目录：{root}", file=sys.stderr)
        return 2

    repo_root = Path(args.repo_root) if args.repo_root else find_repo_root(Path(__file__).resolve())

    agg = Aggregate(since=since, until=until)
    files = sorted(root.rglob("*.jsonl"))
    for path in files:
        agg.files_scanned += 1
        sess = scan_file(path, args.date_basis, agg.gaps, agg.gap_samples)
        if sess is None:
            agg.files_unreadable += 1
            continue
        aggregate_session(sess, agg)

    report = render_markdown(agg, args, root)

    out_path = Path(args.out) if args.out else repo_root / "reports" / f"token-usage-{since}-{until}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"✅ 报告已写出：{out_path}")

    json_path = Path(args.json_out) if args.json_out else out_path.with_suffix(".json")
    payload = {
        "since": since.isoformat(), "until": until.isoformat(), "date_basis": args.date_basis,
        "root": str(root), "files_scanned": agg.files_scanned, "files_unreadable": agg.files_unreadable,
        "daily_model": [
            {"day": day.isoformat(), "model": model, **v}
            for (day, model), v in sorted(agg.daily_model.items(), key=lambda kv: (kv[0][0], kv[0][1]))
        ],
        "sessions": sorted(agg.session_rows, key=lambda r: -r["total_tokens"]),
        "parent_sessions": [
            {"parent_session_id": pid, "title": agg.parent_titles.get(pid, ""), **v}
            for pid, v in sorted(agg.parent_totals.items(), key=lambda kv: -kv[1]["total_tokens"])
        ],
        "opening_noise": {
            "n": len(agg.opening_noise),
            "p50": percentile(agg.opening_noise, 0.50),
            "p95": percentile(agg.opening_noise, 0.95),
        },
        "mechanism_tax": {
            "bash_total": agg.bash_total, "bash_mechanism_hits": agg.bash_mechanism_hits,
            "ratio": (agg.bash_mechanism_hits / agg.bash_total) if agg.bash_total else 0.0,
        },
        "watcher_sessions": agg.watcher_sessions,
        "gaps": dict(agg.gaps),
        "antigravity": {
            "requests": args.antigravity_requests, "cache_read": args.antigravity_cache_read,
        },
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ JSON 已写出：{json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
