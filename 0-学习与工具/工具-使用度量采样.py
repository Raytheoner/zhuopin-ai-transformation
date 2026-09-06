"""使用度量只读采样（队列 §一 `#436` ⑶③ / `OP-0906-T`，2026-09-06）。

**要治的病**：一个场景部署上线之后，「有没有人在用、用了哪些功能、哪些功能
从来没被点过」这件事**在本仓库里没有任何机器可读的答案**——`发布即收口`
四关只管到「部署 ＋ 灰度开闸」，之后全靠专员在跟进信里说一句「在用」。
而平台 `audit` 每一次 AI 决策都留了痕、场景 web 每一次请求也都落了访问日志，
**事实一直在盘上，只是没人读**。本工具就是「先查事实再问人」的那一步：
只读地把两类日志汇成一张「场景 × 用户 × 日」的表，外加零触发功能清单与
日志缺口清单。

口径来源＝`1-转型规划/0-全景路线图/端到端构建workflow优化-方案-2026-09-06.md`
§四 W5（Shao Peishen 2026-09-06 拍板「立项，但只读采样、三档 3／7／14」）；
任务书全文＝`1-转型规划/0-全景路线图/队列行日志/#436.md` (iii)。

--------------------------------------------------------------------------
🔴 四条硬边界（Shao Peishen 2026-09-06 当场拍死，改实现的人必须先读这一段）
--------------------------------------------------------------------------

**⑴ 只读。** 本工具不写 `README-跟进机制与命名约定.md`、不推企微、不起草任何
信、不改任何场景代码、不新增定时任务。唯一的写动作是「把报告写到 `--out`
指定的那个文件」，而那个文件默认是 stdout。拍板前的方案原文里有一条
「14 天零使用自动起草使用确认判例包草稿进 README」——**那条被砍掉了**，
不要凭旧方案文档把它加回来。

**⑵ 三档就是 3／7／14，全部确定性、不涉模型。** 分档只看一个数：
`截止日 - 该 (场景,用户) 最后一次活动日`。3–6 天＝「记日志」；7–13 天＝
「只读诊断」；≥14 天＝「需你定夺」候选。**不得自行加档、不得改阈值**——
阈值属口径判据，改它命中 🟡 档（须他一个字母），不是实现细节。

**⑶ 「只读诊断」诊的是「已在用但未留痕」，不是「没在用」。** 7 天档要做的
事是：拿这个人**最近一次企微回件／文件落档日期**（`7-外部文档/` 文件 mtime
＋ 跟进信 README 主表）跟「日志里最后一次活动日」比——**证据比日志新，就
说明人在用、只是这条使用路径没留痕**，那是留痕缺口，不是使用缺口。两者的
处置完全相反（前者补埋点，后者问人），报成一种就等于把结论做错了。

**⑷ 日志缺口是产出，不是噪声。** 无法识别用户／无时间戳／格式不一这三类
必须逐类计数并出样本行号。**尤其是访问日志根本不含个人身份**
（`shared_tools/access_log.py` 明写「不采集个人身份」，只有 `source_ip`）
⇒ 访问侧的「用户」维度天然只能到 IP 粒度，这不是本工具的 bug，而是采集层
的既定边界，报告里必须写明，**不得用任何猜测把 IP 映射成人名**。

--------------------------------------------------------------------------
🔑 三条反直觉判据
--------------------------------------------------------------------------

**⑴ 「零触发功能」的全集不能只取自日志。** 直觉写法是「把日志里出现过的
路由／动作去重当全集，窗口内没出现的就是零触发」——那样**从上线到今天一次
都没被触发过的功能永远不会出现在清单里**，而那恰恰是最该被看见的一类。故
本工具支持 `--inventory` 传入功能全集；**没有 inventory 时报告必须显式声明
「全集取自日志历史，从未触发过的功能不可见」**，不许沉默降级。

**⑵ 日期必须先判基准再归集。** `AuditEvent` 与 `AccessLogEntry` 的
`timestamp` 都是 `datetime.now(timezone.utc).isoformat()` ＝ **UTC**；而
「连续 N 天零使用」是业务口径、按**本地日**算。默认 `--date-basis local`
（带时区的时间戳转本地后再归日），报告抬头把基准原样打出来。不带时区的
时间戳按本地解释并**单列一类缺口**——因为「按本地解释」是个假设，假设要
可见。

**⑶ 大文件只能流式读。** `#358` 实测 `.51` 保供看板审计日志已到 309 MB 级
且无轮转。本工具一律逐行读、只留聚合计数（bucket 数受「场景×用户×日」组合
数约束，不随文件字节数增长），**任何 `read()`／`readlines()`／
`json.load(整个文件)` 的改法都会在真实日志上 OOM**。报告末尾的「轮转建议」
只建议、不实施——`#358` 须先走 openspec design 审，且 design 中已明确排除
「按大小截断」「删旧文件」（会丢证据，直接违反 IATF 红线 2 的 3 年留存）。

--------------------------------------------------------------------------
用法
--------------------------------------------------------------------------

    # 单场景 audit
    python 0-学习与工具/工具-使用度量采样.py --audit reports/fi2_audit.jsonl

    # 两场景、audit ＋ 访问日志 ＋ 连接器痕迹，出 Markdown 报告
    python 0-学习与工具/工具-使用度量采样.py \\
        --audit  fi2_audit.jsonl --audit fi2_web_audit.jsonl \\
        --access fi2_http_requests.jsonl \\
        --audit  baoguan_audit.jsonl \\
        --access baoguan_http_requests.jsonl \\
        --trace  baoguan_access_trace.jsonl=SC8 \\
        --window 30 --asof 2026-09-06 --out reports/使用度量采样-2026-09-06.md

`PATH=场景码` 后缀用于**记录本身不含场景标识**的日志：连接器痕迹
（`AccessTrace` 只有 source/action/target）必须显式给码；访问日志的服务名
若不在内置映射表里也可以这样兜底。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# ── 常量：三档阈值（🔴 口径判据，改它须走 🟡 档，不是实现细节） ──────────────
BAND_LOG = 3        # 3–6 天：记日志
BAND_DIAGNOSE = 7   # 7–13 天：只读诊断
BAND_DECIDE = 14    # ≥14 天：需你定夺候选

# 访问日志 service 名 → 场景码（call site 见各场景 webapp.py::create_app）
SERVICE_TO_SCENARIO = {
    "FI2 三单匹配自动对账": "FI2",
    "QD-B 立项审核门禁": "QD-B",
    "成品保供预警看板": "SC8",
    "SC2 采购周报": "SC2",
}

UNKNOWN_SCENARIO = "（未知场景）"
UNATTRIBUTED_USER = "（未署名）"
DATE_RE = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")

GAP_KINDS = {
    "bad_json": "格式不一 · 非合法 JSON 行",
    "not_object": "格式不一 · JSON 不是对象",
    "unknown_shape": "格式不一 · 字段组合不属任何已知形态",
    "no_scenario": "无法识别场景（记录无 scenario／service，且未用 PATH=场景码 指定）",
    "no_timestamp": "无时间戳",
    "bad_timestamp": "时间戳无法解析",
    "naive_timestamp": "时间戳无时区标记（已按本地解释，属假设）",
    "no_user": "无法识别用户 · audit 记录 evaluator 为空",
    "ip_only": "无法识别用户 · 访问日志按设计不采集个人身份（仅 source_ip）",
    "trace_no_user": "无法识别用户 · 连接器痕迹按设计无用户字段",
    "unreadable": "文件不存在或读取失败",
}

SAMPLE_CAP = 5   # 每类缺口最多留几条样本（大文件下不能无限攒）


# ══════════════════════════════════════════════════════════════════════════
# 数据结构
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class InputSpec:
    """一个输入文件：路径 ＋ 形态 ＋ 可选的外部场景码。"""
    path: Path
    kind: str                 # 'audit' | 'access' | 'trace'
    scenario_hint: str = ""   # PATH=场景码 给的外部场景码


@dataclass
class Gap:
    kind: str
    source: str
    line_no: int
    detail: str = ""


@dataclass
class Tally:
    """全部聚合结果。桶数只随「场景×用户×日」组合数增长，不随文件字节数增长。"""
    # (scenario, user, day) -> 次数
    access: dict = field(default_factory=lambda: defaultdict(int))
    decisions: dict = field(default_factory=lambda: defaultdict(int))
    traces: dict = field(default_factory=lambda: defaultdict(int))   # (scenario, day)
    # scenario -> set[功能名]
    routes_all: dict = field(default_factory=lambda: defaultdict(set))
    routes_win: dict = field(default_factory=lambda: defaultdict(set))
    actions_all: dict = field(default_factory=lambda: defaultdict(set))
    actions_win: dict = field(default_factory=lambda: defaultdict(set))
    # (scenario, user) -> 最后活动日 / 首次活动日
    last_seen: dict = field(default_factory=dict)
    first_seen: dict = field(default_factory=dict)
    gaps: dict = field(default_factory=lambda: defaultdict(int))
    gap_samples: dict = field(default_factory=lambda: defaultdict(list))
    files: list = field(default_factory=list)   # [{path, kind, exists, bytes, lines, ok}]

    def note_gap(self, gap: Gap) -> None:
        self.gaps[gap.kind] += 1
        if len(self.gap_samples[gap.kind]) < SAMPLE_CAP:
            self.gap_samples[gap.kind].append(gap)

    def touch(self, scenario: str, user: str, day: date) -> None:
        key = (scenario, user)
        if key not in self.first_seen or day < self.first_seen[key]:
            self.first_seen[key] = day
        if key not in self.last_seen or day > self.last_seen[key]:
            self.last_seen[key] = day


# ══════════════════════════════════════════════════════════════════════════
# 解析
# ══════════════════════════════════════════════════════════════════════════

def parse_input_spec(raw: str, kind: str) -> InputSpec:
    """`PATH` 或 `PATH=场景码` —— 只按**最后一个** `=` 拆，Windows 盘符路径安全。"""
    scenario = ""
    if "=" in raw:
        head, _, tail = raw.rpartition("=")
        # 场景码不含路径分隔符，且非空；否则整串当路径（防 `a=b.jsonl` 这类文件名误拆）
        if head and tail and not any(c in tail for c in "/\\"):
            raw, scenario = head, tail
    return InputSpec(path=Path(raw), kind=kind, scenario_hint=scenario)


def to_day(raw: str, basis: str, tally: Tally, source: str, line_no: int) -> date | None:
    """ISO 时间戳 → 归集用「日」。基准由 `basis` 定（local／utc），不带时区的单列缺口。"""
    if not raw:
        tally.note_gap(Gap("no_timestamp", source, line_no))
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        tally.note_gap(Gap("bad_timestamp", source, line_no, str(raw)[:60]))
        return None
    if dt.tzinfo is None:
        tally.note_gap(Gap("naive_timestamp", source, line_no, str(raw)[:60]))
        return dt.date()
    if basis == "utc":
        return dt.astimezone(timezone.utc).date()
    return dt.astimezone().date()   # 本地时区


def classify(rec: dict) -> str:
    """按字段组合判形态，不看文件名——文件名会骗人，字段不会。"""
    if "scenario" in rec and "action" in rec and "automation_level" in rec:
        return "audit"
    if "service" in rec and "path" in rec and "method" in rec:
        return "access"
    if "source" in rec and "action" in rec and "scenario" not in rec:
        return "trace"
    return ""


def scan_file(spec: InputSpec, tally: Tally, win_start: date, win_end: date,
              basis: str) -> None:
    """逐行流式扫一个文件。🔴 任何一次性读全文件的改法都会在 309 MB 日志上 OOM。"""
    src = str(spec.path)
    info = {"path": src, "kind": spec.kind, "exists": spec.path.exists(),
            "bytes": 0, "lines": 0, "ok": False}
    if not spec.path.exists():
        tally.note_gap(Gap("unreadable", src, 0, "文件不存在"))
        tally.files.append(info)
        return
    try:
        info["bytes"] = spec.path.stat().st_size
    except OSError:
        pass
    try:
        with open(spec.path, "r", encoding="utf-8", errors="replace") as fh:
            for line_no, line in enumerate(fh, start=1):
                info["lines"] = line_no
                line = line.strip()
                if not line:
                    continue
                _ingest_line(line, line_no, spec, tally, win_start, win_end, basis)
        info["ok"] = True
    except OSError as exc:
        tally.note_gap(Gap("unreadable", src, 0, str(exc)[:80]))
    tally.files.append(info)


def _ingest_line(line: str, line_no: int, spec: InputSpec, tally: Tally,
                 win_start: date, win_end: date, basis: str) -> None:
    src = str(spec.path)
    try:
        rec = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        tally.note_gap(Gap("bad_json", src, line_no, line[:60]))
        return
    if not isinstance(rec, dict):
        tally.note_gap(Gap("not_object", src, line_no, line[:60]))
        return

    shape = classify(rec) or spec.kind
    if not classify(rec):
        # 字段组合不认识：如果连声明形态的必备字段也没有，记一笔
        need = {"audit": ("scenario", "action"), "access": ("path",), "trace": ("action",)}
        if not any(k in rec for k in need.get(shape, ())):
            tally.note_gap(Gap("unknown_shape", src, line_no, line[:60]))
            return

    day = to_day(rec.get("timestamp", ""), basis, tally, src, line_no)
    if day is None:
        return
    in_win = win_start <= day <= win_end

    if shape == "audit":
        scenario = str(rec.get("scenario") or "").strip() or spec.scenario_hint
        if not scenario:
            tally.note_gap(Gap("no_scenario", src, line_no))
            scenario = UNKNOWN_SCENARIO
        action = str(rec.get("action") or "").strip() or "（无动作名）"
        tally.actions_all[scenario].add(action)
        if in_win:
            tally.actions_win[scenario].add(action)
        user = str(rec.get("evaluator") or "").strip()
        if not user:
            tally.note_gap(Gap("no_user", src, line_no))
            user = UNATTRIBUTED_USER
        tally.decisions[(scenario, user, day)] += 1
        tally.touch(scenario, user, day)

    elif shape == "access":
        service = str(rec.get("service") or "").strip()
        scenario = (spec.scenario_hint or SERVICE_TO_SCENARIO.get(service, ""))
        if not scenario:
            tally.note_gap(Gap("no_scenario", src, line_no, f"service={service!r}"))
            scenario = service or UNKNOWN_SCENARIO
        route = f"{rec.get('method', '?')} {rec.get('path', '?')}"
        tally.routes_all[scenario].add(route)
        if in_win:
            tally.routes_win[scenario].add(route)
        ip = str(rec.get("source_ip") or "").strip()
        # 🔴 采集层按设计不含个人身份 —— 只能到 IP 粒度，绝不猜人名
        tally.note_gap(Gap("ip_only", src, line_no, ip))
        user = f"ip:{ip}" if ip else f"ip:{UNATTRIBUTED_USER}"
        tally.access[(scenario, user, day)] += 1
        tally.touch(scenario, user, day)

    else:  # trace —— 连接器痕迹：无场景、无用户
        scenario = spec.scenario_hint
        if not scenario:
            tally.note_gap(Gap("no_scenario", src, line_no, "连接器痕迹无 scenario 字段"))
            scenario = UNKNOWN_SCENARIO
        action = f"connector:{rec.get('source', '?')}/{rec.get('action', '?')}"
        tally.actions_all[scenario].add(action)
        if in_win:
            tally.actions_win[scenario].add(action)
        tally.note_gap(Gap("trace_no_user", src, line_no))
        tally.traces[(scenario, day)] += 1


# ══════════════════════════════════════════════════════════════════════════
# 三档判定 ＋ 只读诊断
# ══════════════════════════════════════════════════════════════════════════

def band_of(idle_days: int) -> str:
    if idle_days >= BAND_DECIDE:
        return "需你定夺"
    if idle_days >= BAND_DIAGNOSE:
        return "只读诊断"
    if idle_days >= BAND_LOG:
        return "记日志"
    return ""


def readme_last_dates(repo_root: Path) -> dict:
    """跟进信 README 主表 → {姓名: 最近日期}。走既有只读查询工具，不 Read 主表。"""
    tool = repo_root / "0-学习与工具" / "工具-跟进信README查询.py"
    out: dict = {}
    if not tool.exists():
        return out
    try:
        proc = subprocess.run([sys.executable, str(tool), "--digest", "--json"],
                              cwd=str(repo_root), capture_output=True, text=True,
                              encoding="utf-8", timeout=60)
        if proc.returncode != 0:
            return out
        data = json.loads(proc.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return out
    for row in data.get("rows", []):
        name = (row.get("name") or "").strip()
        if not name:
            continue
        blob = f"{row.get('status_digest', '')} {row.get('delivery_digest', '')}"
        for m in DATE_RE.finditer(blob):
            try:
                d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                continue
            if name not in out or d > out[name]:
                out[name] = d
    return out


def external_doc_last_mtime(repo_root: Path, name: str) -> date | None:
    """`7-外部文档/` 下路径含该姓名的最新落档 mtime（只读，目录缺失时返回 None）。"""
    root = repo_root / "7-外部文档"
    if not name or not root.is_dir():
        return None
    newest = None
    for dirpath, _dirnames, filenames in os.walk(root):
        rel = Path(dirpath)
        dir_hit = name in str(rel)
        for fn in filenames:
            if not dir_hit and name not in fn:
                continue
            try:
                ts = (rel / fn).stat().st_mtime
            except OSError:
                continue
            d = datetime.fromtimestamp(ts).date()
            if newest is None or d > newest:
                newest = d
    return newest


def diagnose(user: str, last_activity: date, asof: date, repo_root: Path,
             readme_dates: dict) -> dict:
    """只读诊断：证据比日志新 ⇒ 「已在用但未留痕」。仅 7 天档及以上调用。"""
    name = user.split(":", 1)[1] if user.startswith("ip:") else user
    is_ip = user.startswith("ip:")
    res = {"name": name, "identity_resolvable": not is_ip,
           "readme_date": None, "doc_date": None, "verdict": ""}
    if is_ip or name == UNATTRIBUTED_USER:
        res["verdict"] = "无法诊断（该维度不含个人身份，无法与名录／README 对齐）"
        return res
    res["readme_date"] = readme_dates.get(name)
    res["doc_date"] = external_doc_last_mtime(repo_root, name)
    cands = [d for d in (res["readme_date"], res["doc_date"]) if d]
    if not cands:
        res["verdict"] = "无外部证据（README 主表与 7-外部文档 均未匹配到该姓名）"
        return res
    newest = max(cands)
    if last_activity < newest <= asof:
        res["verdict"] = f"⚠️ 已在用但未留痕（最近证据 {newest}，晚于日志最后活动 {last_activity}）"
    else:
        res["verdict"] = f"证据未晚于日志（最近证据 {newest}）"
    return res


# ══════════════════════════════════════════════════════════════════════════
# 报告
# ══════════════════════════════════════════════════════════════════════════

def build_summary(tally: Tally, asof: date, win_start: date) -> list:
    """场景 × 用户 汇总行（含三档），按 闲置天数 倒序。"""
    acc_win: dict = defaultdict(int)
    dec_win: dict = defaultdict(int)
    for (s, u, d), v in tally.access.items():
        if win_start <= d <= asof:
            acc_win[(s, u)] += v
    for (s, u, d), v in tally.decisions.items():
        if win_start <= d <= asof:
            dec_win[(s, u)] += v
    rows = []
    for (scenario, user), last in sorted(tally.last_seen.items()):
        acc = acc_win.get((scenario, user), 0)
        dec = dec_win.get((scenario, user), 0)
        idle = (asof - last).days
        rows.append({"scenario": scenario, "user": user, "first": tally.first_seen[(scenario, user)],
                     "last": last, "idle": idle, "access": acc, "decisions": dec,
                     "band": band_of(idle)})
    rows.sort(key=lambda r: (-r["idle"], r["scenario"], r["user"]))
    return rows


def render(tally: Tally, args, asof: date, win_start: date, inventory: dict,
           repo_root: Path) -> str:
    L: list = []
    now = datetime.now().astimezone()
    basis_txt = "本地时区" if args.date_basis == "local" else "UTC"
    L.append("# 使用度量只读采样报告")
    L.append("")
    L.append(f"- 生成时刻：`{now.isoformat(timespec='seconds')}`（本地时区，`Get-Date` 同基准）")
    L.append(f"- 采样截止日（asof）：**{asof}** ｜ 窗口：**{args.window} 天**（{win_start} ～ {asof}）")
    L.append(f"- 归日基准：**{basis_txt}**（`--date-basis {args.date_basis}`）")
    L.append(f"- 三档阈值：**{BAND_LOG} / {BAND_DIAGNOSE} / {BAND_DECIDE}** 天（口径判据，改它须 Shao Peishen 拍板）")
    L.append("- 🔴 本报告**只读**：不写 README、不推企微、不起草任何信、不改场景代码。")
    L.append("")

    # ── 输入 ──
    L.append("## 〇 · 输入文件")
    L.append("")
    L.append("| 文件 | 形态 | 存在 | 字节 | 读入行数 | 读取 |")
    L.append("|---|---|---|---|---|---|")
    for f in tally.files:
        L.append(f"| `{f['path']}` | {f['kind']} | {'是' if f['exists'] else '否'} | "
                 f"{f['bytes']:,} | {f['lines']:,} | {'✅' if f['ok'] else '❌'} |")
    L.append("")

    # ── §一 场景 × 用户 汇总 ──
    summary = build_summary(tally, asof, win_start)
    L.append("## 一 · 场景 × 用户 汇总（窗口内计数 ＋ 闲置天数）")
    L.append("")
    if not summary:
        L.append("_无任何可归集记录。_")
    else:
        L.append("| 场景 | 用户 | 首次活动 | 最后活动 | 闲置天数 | 窗口内访问 | 窗口内 AI 决策 | 档 |")
        L.append("|---|---|---|---|---:|---:|---:|---|")
        for r in summary:
            L.append(f"| {r['scenario']} | `{r['user']}` | {r['first']} | {r['last']} | "
                     f"{r['idle']} | {r['access']} | {r['decisions']} | {r['band'] or '—'} |")
    L.append("")

    # ── §二 场景 × 用户 × 日 明细 ──
    L.append(f"## 二 · 场景 × 用户 × 日 明细（窗口内，最多 {args.max_rows} 行）")
    L.append("")
    keys = set(tally.access) | set(tally.decisions)
    detail = sorted((k for k in keys if win_start <= k[2] <= asof),
                    key=lambda k: (k[2], k[0], k[1]), reverse=True)
    if not detail:
        L.append("_窗口内无记录。_")
    else:
        L.append("| 日期 | 场景 | 用户 | 访问次数 | AI 决策次数 |")
        L.append("|---|---|---|---:|---:|")
        for k in detail[:args.max_rows]:
            L.append(f"| {k[2]} | {k[0]} | `{k[1]}` | {tally.access.get(k, 0)} | "
                     f"{tally.decisions.get(k, 0)} |")
        if len(detail) > args.max_rows:
            L.append("")
            L.append(f"_另有 {len(detail) - args.max_rows} 行未列出（`--max-rows` 调整）。_")
    if tally.traces:
        L.append("")
        L.append("连接器痕迹（无用户维度，只到 场景 × 日）：")
        L.append("")
        L.append("| 日期 | 场景 | 痕迹条数 |")
        L.append("|---|---|---:|")
        for (s, d), n in sorted(tally.traces.items(), key=lambda kv: (kv[0][1], kv[0][0]), reverse=True):
            if win_start <= d <= asof:
                L.append(f"| {d} | {s} | {n} |")
    L.append("")

    # ── §三 零触发功能 ──
    L.append("## 三 · 零触发功能清单（窗口内一次未触发）")
    L.append("")
    if inventory:
        L.append("功能全集来源：`--inventory` 声明件。")
    else:
        L.append("🔴 **功能全集取自日志历史（本工具见过的路由／动作去重）**——"
                 "**从上线至今一次都没被触发过的功能，在本清单里看不见**。"
                 "要看全，须用 `--inventory` 传入功能全集声明件。")
    L.append("")
    scenarios = sorted(set(tally.routes_all) | set(tally.actions_all) | set(inventory))
    any_zero = False
    for s in scenarios:
        inv = inventory.get(s, {})
        routes_all = set(inv.get("routes", [])) | tally.routes_all.get(s, set())
        actions_all = set(inv.get("actions", [])) | tally.actions_all.get(s, set())
        zero_r = sorted(routes_all - tally.routes_win.get(s, set()))
        zero_a = sorted(actions_all - tally.actions_win.get(s, set()))
        if not zero_r and not zero_a:
            continue
        any_zero = True
        L.append(f"### {s}")
        L.append("")
        if zero_a:
            L.append(f"- 零触发动作（{len(zero_a)}/{len(actions_all)}）："
                     + "、".join(f"`{a}`" for a in zero_a))
        if zero_r:
            L.append(f"- 零触发路由（{len(zero_r)}/{len(routes_all)}）："
                     + "、".join(f"`{r}`" for r in zero_r))
        L.append("")
    if not any_zero:
        L.append("_窗口内所有已知功能均有触发。_")
        L.append("")

    # ── §四 三档 ──
    readme_dates = {} if args.no_diagnose else readme_last_dates(repo_root)
    L.append(f"## 四 · 三档判定（{BAND_LOG} / {BAND_DIAGNOSE} / {BAND_DECIDE} 天，确定性、不涉模型）")
    L.append("")
    for band, title, note in (
        ("需你定夺", f"≥ {BAND_DECIDE} 天零使用 —— 「需你定夺」候选",
         "处置＝由 Shao Peishen 答「起草使用确认判例包／深化／下架」，"
         "🔴 **本工具不自动起草、不写 README**。"),
        ("只读诊断", f"{BAND_DIAGNOSE} – {BAND_DECIDE - 1} 天零使用 —— 只读诊断",
         "诊断的是「已在用但未留痕」：证据比日志新 ⇒ 补埋点，不是问人。"),
        ("记日志", f"{BAND_LOG} – {BAND_DIAGNOSE - 1} 天零使用 —— 只记日志",
         "本档不产生任何动作。"),
    ):
        hits = [r for r in summary if r["band"] == band]
        L.append(f"### {title}（{len(hits)} 项）")
        L.append("")
        L.append(f"> {note}")
        L.append("")
        if not hits:
            L.append("_无。_")
            L.append("")
            continue
        for r in hits:
            line = (f"- **{r['scenario']} · `{r['user']}`** —— 最后活动 {r['last']}，"
                    f"闲置 {r['idle']} 天")
            L.append(line)
            if band in ("只读诊断", "需你定夺") and not args.no_diagnose:
                dg = diagnose(r["user"], r["last"], asof, repo_root, readme_dates)
                L.append(f"  - 只读诊断：{dg['verdict']}")
                if dg["readme_date"]:
                    L.append(f"    - 跟进信 README 主表最近日期：{dg['readme_date']}")
                if dg["doc_date"]:
                    L.append(f"    - `7-外部文档/` 最近落档 mtime：{dg['doc_date']}")
            elif band in ("只读诊断", "需你定夺"):
                L.append("  - 只读诊断：已按 `--no-diagnose` 跳过。")
        L.append("")

    # ── §五 日志缺口 ──
    L.append("## 五 · 日志缺口")
    L.append("")
    if not tally.gaps:
        L.append("_未发现缺口。_")
    else:
        L.append("| 缺口类别 | 命中条数 | 样本（文件:行号） |")
        L.append("|---|---:|---|")
        for kind, n in sorted(tally.gaps.items(), key=lambda kv: -kv[1]):
            samples = "；".join(f"`{Path(g.source).name}:{g.line_no}`"
                                + (f" {g.detail}" if g.detail else "")
                                for g in tally.gap_samples[kind])
            L.append(f"| {GAP_KINDS.get(kind, kind)} | {n} | {samples or '—'} |")
    L.append("")
    L.append("🔴 **`ip_only` 不是 bug**：`shared_tools/access_log.py` 按设计「不采集个人身份」"
             "（无登录系统，本就无个人身份可采）⇒ 访问侧的「用户」天然只能到 IP 粒度。"
             "本工具**不做任何 IP→人名的猜测**。若要把访问侧接进「场景 × 用户」，"
             "须先解决身份识别（同 W4 前置：每专员专属链接 token 或企微鉴权），属另一件事。")
    L.append("")

    # ── §六 轮转建议 ──
    L.append("## 六 · 轮转建议（只建议，不实施 —— 承队列 `#358`）")
    L.append("")
    big = [f for f in tally.files if f["bytes"] >= args.rotate_warn_mb * 1024 * 1024]
    total_bytes = sum(f["bytes"] for f in tally.files)
    total_lines = sum(f["lines"] for f in tally.files)
    avg = (total_bytes / total_lines) if total_lines else 0
    L.append(f"- 本次读入合计 **{total_bytes:,} 字节 / {total_lines:,} 行**，"
             f"平均每行约 {avg:,.0f} 字节。")
    if big:
        for f in big:
            L.append(f"- ⚠️ `{f['path']}` 已达 **{f['bytes'] / 1024 / 1024:,.1f} MB**"
                     f"（阈值 {args.rotate_warn_mb} MB）。")
    else:
        L.append(f"- 本次输入均未超过 {args.rotate_warn_mb} MB 告警阈值。")
    L.append("")
    L.append("建议（**只建议**，须先过 `#358` 的 openspec design 审后才可实现）：")
    L.append("")
    L.append("1. 归档方向＝**冷存储且保持可检索**，🔴 design 中已显式排除「按大小截断」"
             "「删旧文件」——两者都会丢证据，直接违反 IATF 红线 2（AI 决策 append-only、"
             "3 年留存、可追溯）。")
    L.append("2. 落点应在平台底座 `zhuopin_platform/audit/`（`logger.py`／`sinks.py` 现"
             "全库零 `rotate`／`retention`／`max_bytes` 实现），**不是** `.51` 单机运维——"
             "在 `.51` 上按机器修，SC2／SC8／QD-B／FI2 四处要各修一遍。")
    L.append("3. 与 9 月 ClickHouse 迁移的衔接须一并在 design 里定，避免建了又拆。")
    L.append("4. 🔴 **本工具不实施任何轮转**，也不读写除 `--out` 之外的任何文件。")
    L.append("")

    # ── 边界 ──
    L.append("## 七 · 边界（如实登记，不假装闭合）")
    L.append("")
    L.append("- 访问侧无个人身份，「场景 × 用户」在访问维度只到 IP 粒度（见 §五）。")
    L.append("- 连接器痕迹（`AccessTrace`）无 scenario、无用户字段，场景码只能由 "
             "`PATH=场景码` 外部指定；无法归到人。")
    L.append("- 「零触发功能」全集在无 `--inventory` 时取自日志历史，"
             "**从未触发过的功能不可见**（见 §三 首段）。")
    L.append("- 只读诊断的姓名匹配是**字面匹配**（audit `evaluator` ↔ README 主表姓名 ↔ "
             "`7-外部文档/` 路径）；匹配不到即如实报「无外部证据」，"
             "**不做任何推断**（人的属性＝硬事实，见根 `CLAUDE.md` §1）。")
    L.append("- 本工具无定时任务、无 job 化；是否 job 化待本报告过目后另议。")
    L.append("")
    return "\n".join(L)


# ══════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════

def find_repo_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "CLAUDE.md").exists() and (p / "0-学习与工具").is_dir():
            return p
    return start


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="使用度量只读采样（队列 #436 ⑶③）——只读，不写 README／不推企微／不起草信。",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--audit", action="append", default=[], metavar="PATH[=场景码]",
                    help="平台 audit JSONL（AuditEvent 形态：scenario/action/evaluator）")
    ap.add_argument("--access", action="append", default=[], metavar="PATH[=场景码]",
                    help="场景 web 访问日志 JSONL（AccessLogEntry 形态：service/method/path/source_ip）")
    ap.add_argument("--trace", action="append", default=[], metavar="PATH=场景码",
                    help="连接器痕迹 JSONL（AccessTrace 形态，无 scenario／无用户，须显式给场景码）")
    ap.add_argument("--window", type=int, default=30, help="采样窗口天数（默认 30）")
    ap.add_argument("--asof", default="", metavar="YYYY-MM-DD",
                    help="采样截止日；默认取本机今天（本地时区）")
    ap.add_argument("--date-basis", choices=("local", "utc"), default="local",
                    help="时间戳归日基准（默认 local；日志本身是 UTC）")
    ap.add_argument("--inventory", default="", metavar="PATH",
                    help='功能全集声明 JSON：{"FI2": {"routes": [...], "actions": [...]}}')
    ap.add_argument("--out", default="", metavar="PATH", help="报告落盘路径；缺省写 stdout")
    ap.add_argument("--json", dest="json_out", default="", metavar="PATH",
                    help="另存机器消费用 JSON")
    ap.add_argument("--repo-root", default="", help="仓库根（默认自本文件向上探测）")
    ap.add_argument("--max-rows", type=int, default=200, help="§二 明细最多列几行（默认 200）")
    ap.add_argument("--rotate-warn-mb", type=int, default=100,
                    help="§六 轮转建议的体积告警阈值 MB（默认 100）")
    ap.add_argument("--no-diagnose", action="store_true",
                    help="跳过 7／14 档的只读诊断（不读 README 主表与 7-外部文档）")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    specs = ([parse_input_spec(r, "audit") for r in args.audit]
             + [parse_input_spec(r, "access") for r in args.access]
             + [parse_input_spec(r, "trace") for r in args.trace])
    if not specs:
        print("错误：至少要给一个 --audit／--access／--trace 输入。", file=sys.stderr)
        return 2
    if args.window < 1:
        print("错误：--window 须 ≥ 1。", file=sys.stderr)
        return 2

    if args.asof:
        try:
            asof = date.fromisoformat(args.asof)
        except ValueError:
            print(f"错误：--asof 不是合法日期：{args.asof!r}", file=sys.stderr)
            return 2
    else:
        asof = datetime.now().astimezone().date()
    win_start = asof - timedelta(days=args.window - 1)

    repo_root = Path(args.repo_root) if args.repo_root else find_repo_root(Path(__file__).resolve())

    inventory = {}
    if args.inventory:
        try:
            inventory = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"错误：--inventory 读取失败：{exc}", file=sys.stderr)
            return 2

    tally = Tally()
    for spec in specs:
        scan_file(spec, tally, win_start, asof, args.date_basis)

    if not any(f["ok"] for f in tally.files):
        print("错误：所有输入文件都不可读，未产生报告。", file=sys.stderr)
        return 1

    report = render(tally, args, asof, win_start, inventory, repo_root)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(f"✅ 采样报告已写出：{out}")
    else:
        sys.stdout.write(report)

    if args.json_out:
        summary = build_summary(tally, asof, win_start)
        payload = {
            "asof": asof.isoformat(), "window": args.window,
            "date_basis": args.date_basis,
            "bands": {"log": BAND_LOG, "diagnose": BAND_DIAGNOSE, "decide": BAND_DECIDE},
            "files": tally.files,
            "summary": [{**r, "first": r["first"].isoformat(), "last": r["last"].isoformat()}
                        for r in summary],
            "gaps": dict(tally.gaps),
        }
        jp = Path(args.json_out)
        jp.parent.mkdir(parents=True, exist_ok=True)
        jp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ JSON 已写出：{jp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
