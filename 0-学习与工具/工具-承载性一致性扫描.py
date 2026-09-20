#!/usr/bin/env python3
"""承载性一致性扫描器（队列 §一 `#601`，2026-09-17 `OP-0911-H` 改判范围）。

判据正本：`1-转型规划/0-全景路线图/派单件-【CC】新场景intent闸机器守-2026-09-17.md`。

只读、只报告，不改任何被扫到的规则文件一个字节。扫描面（见 `SCAN_TARGETS`／
`QUEUE_PROTOCOL_SOURCES`）里的「机器守＝／落点＝／机器强制／机器判据／
由机器／闸＝」类自陈句，抽出其中**结构化**载体（反引号文件路径、`#NNN`
队列行号、job 反引号 id、skill 反引号 name），核对是否真实存在，分三态：

  ① 缺失（missing）  —— 自陈载体不存在，且在候选真实落点里也找不到同
     关键词的东西 ⇒ 告警。
  ② 指错（misdirected）—— 自陈载体不存在，但同一口径的关键词能在
     `0-学习与工具/*.py`／`.github/workflows/*.yml`／`.claude/settings.json`
     里找到疑似真实落点 ⇒ 告警，文案给出「自陈 A，疑似真实落点 B」。
  ③ 无载体清单（no_carrier）—— 命令式约束（必须／一律／不得／禁止／永不）
     但全文找不到任何结构化载体指向 ⇒ 只列入 `reports/`，不进告警。

🔴 只判「有无与一致性」，不判规则对错（`#284` 已实证这条判据有效、弱校验
拦得住「压根没做这一步」而非判断错误）。**不做**语义理解、不猜测口径
对错，抽不出结构化载体就不判——宁可漏报（留给人工），不做无凭据的
断言。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT_MARKERS = (".git",)

# ------------------------------------------------------------------
# 扫描面
# ------------------------------------------------------------------

#: 逐条规则文件／skill 说明书 —— 支持 glob。
SCAN_GLOBS = [
    (".claude/rules/*.md", "rules"),
    (".claude/skills/*/SKILL.md", "skills-installed"),
    ("0-学习与工具/skills源码/*/SKILL.md", "skills-source"),
]
#: 根 CLAUDE.md 单独列（不是 glob 命中，文件名固定）。
ROOT_CLAUDE_MD = "CLAUDE.md"

#: 两份队列真身的「协议〇」节——**只扫这一节**，不扫 §一/§二/§四 数据行
#: （那些是单行可达 78 KB 的巨行，且是任务记录不是规则自陈）。
QUEUE_PROTOCOL_SOURCES = [
    "1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md",
    "1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md",
]
#: 协议〇小节起讫：从含「〇、」的标题行开始，到下一个同级 `## ` 标题为止。
PROTOCOL_HEADING_RE = re.compile(r"^##\s*〇、", re.MULTILINE)
NEXT_HEADING_RE = re.compile(r"^##\s", re.MULTILINE)

#: 自陈标记——六类，覆盖「载体＝在前」与「载体…机器守 在后」两种语序，
#: 故不在正则里绑定方向，由调用方按整句（前后到句读为止）抽取载体。
MARKER_RE = re.compile(r"机器守\s*[＝=]|落点\s*[＝=]|机器强制|机器判据|由机器|闸\s*[＝=]")

#: 句子边界——中文句读＋换行，用来把「标记」还原成它所在的整句上下文
#: （作为外层夹紧边界，真正的取词窗口见 `_CARRIER_WINDOW_BEFORE/AFTER`）。
SENTENCE_BOUNDARY = "。；\n"

#: 载体取词窗口——本仓大量规则句是长复句（逗号／顿号／括注分隔、无句读），
#: 若只夹紧到整句，一句话里跟自陈无关的反引号路径会被误当成载体（实测
#: 命中：`.claude/rules/场景建造与合规.md` 一句 140+ 字的复句里，`proposal.md`
#: 与「机器守＝」相距 100+ 字却毫无关系）。收窄成「标记前后各一小段」，
#: 前窗口小（载体多半写在标记后）、后窗口够放下一个 `job \`x\`（\`y.yml\`）`
#: 这类嵌套括注。
_CARRIER_WINDOW_BEFORE = 30
_CARRIER_WINDOW_AFTER = 200

#: 结构化载体抽取——只认这四类，抽不出即不判（见模块 docstring）。
FILE_PATH_CARRIER_RE = re.compile(
    r"`([^`\n]+\.(?:py|ps1|psm1|md|json|jsonl|ya?ml))`"
)
QUEUE_ROW_CARRIER_RE = re.compile(r"#(\d{1,4})\b")
CI_JOB_CARRIER_RE = re.compile(r"job\s*`([a-zA-Z0-9_-]+)`", re.IGNORECASE)
SKILL_CARRIER_RE = re.compile(r"skill\s*`([a-zA-Z0-9_-]+)`", re.IGNORECASE)

#: state② 候选真实落点面——同一口径关键词命中即报「疑似真实落点」。
CANDIDATE_REAL_LOCATIONS = [
    ("0-学习与工具/*.py", "script"),
    (".github/workflows/*.yml", "ci-workflow"),
    (".claude/settings.json", "settings"),
]
#: 关键词抽取停用词——太通用，命中即噪声。
STOPWORDS = {
    "机器", "守卫", "落点", "载体", "口径", "本条", "本句", "队列", "本行",
    "现已", "现在", "已经", "以及", "以下", "本次", "这条", "那条", "本项",
}

#: state③——命令式约束扫描；同一句内出现下列关键词、且四类结构化载体
#: 均未命中，即列入无载体清单（只列不报警）。
IMPERATIVE_RE = re.compile(r"必须|一律|不得|禁止|永不")

REPORT_REL = "reports/carrier-consistency-scan.md"


def find_repo_root(start: Path) -> Path:
    cur = start.resolve()
    for _ in range(20):
        if any((cur / marker).exists() for marker in REPO_ROOT_MARKERS):
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return start.resolve()


# ------------------------------------------------------------------
# 数据结构
# ------------------------------------------------------------------

@dataclass
class Carrier:
    kind: str  # file / queue_row / ci_job / skill
    value: str


@dataclass
class Claim:
    source: str          # 相对路径（或 "队列-机制环境" 之类的短名）
    line_no: int
    marker: str
    sentence: str
    carriers: list = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.source}#L{self.line_no}:{self.marker}"


# ------------------------------------------------------------------
# 扫描面收集
# ------------------------------------------------------------------

def _iter_rule_texts(repo_root: Path):
    seen = set()
    for pattern, _label in SCAN_GLOBS:
        for path in sorted(repo_root.glob(pattern)):
            if not path.is_file() or path in seen:
                continue
            seen.add(path)
            rel = path.relative_to(repo_root).as_posix()
            try:
                yield rel, path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                yield rel, f"<<读取失败：{exc}>>"

    root_claude = repo_root / ROOT_CLAUDE_MD
    if root_claude.is_file():
        try:
            yield ROOT_CLAUDE_MD, root_claude.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            yield ROOT_CLAUDE_MD, f"<<读取失败：{exc}>>"


def _extract_protocol_zero(text: str) -> str | None:
    """截取「〇、协议」小节全文（含标题行到下一个 `## ` 标题之前）。"""
    m = PROTOCOL_HEADING_RE.search(text)
    if not m:
        return None
    start = m.start()
    tail = NEXT_HEADING_RE.search(text, m.end())
    end = tail.start() if tail else len(text)
    return text[start:end]


def _iter_queue_protocol_texts(repo_root: Path):
    """`(rel, section_text, error, note)`——`error` 专指「文件读不到／
    读取异常」（判为扫描器自身故障）；`section` 找不到降级为 `note`
    （两份队列里只有一份实际承载协议〇正文，见机制环境.md frontmatter
    「用途」自述，业务场景.md 本就没有这节属正常，不该算作扫描器故障）。"""
    for rel in QUEUE_PROTOCOL_SOURCES:
        path = repo_root / rel
        if not path.is_file():
            yield rel, None, f"文件不存在：{rel}", None
            continue
        try:
            full = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            yield rel, None, f"读取失败：{exc}", None
            continue
        section = _extract_protocol_zero(full)
        if section is None:
            yield rel, None, None, "未找到「〇、协议」标题行（该文件也可能本就不承载协议〇正文）"
            continue
        yield rel, section, None, None


def iter_scan_sources(repo_root: Path):
    """产出 `(source_label, text)`；文本读取失败时计入 `errors`（不静默
    跳过），协议节找不到计入 `notes`（较低严重度，见上）。"""
    errors: list[str] = []
    notes: list[str] = []
    for rel, text in _iter_rule_texts(repo_root):
        if text.startswith("<<读取失败"):
            errors.append(f"{rel}：{text}")
            continue
        yield rel, text
    for rel, section, err, note in _iter_queue_protocol_texts(repo_root):
        if err:
            errors.append(f"{rel}（协议〇节）：{err}")
            continue
        if note:
            notes.append(f"{rel}（协议〇节）：{note}")
            continue
        yield f"{rel}（协议〇节）", section
    return errors, notes


# ------------------------------------------------------------------
# 自陈与载体抽取
# ------------------------------------------------------------------

def _sentence_span(text: str, at: int) -> tuple[int, int]:
    start = max((text.rfind(ch, 0, at) for ch in SENTENCE_BOUNDARY), default=-1)
    start = start + 1 if start >= 0 else 0
    ends = [text.find(ch, at) for ch in SENTENCE_BOUNDARY]
    ends = [e for e in ends if e != -1]
    end = min(ends) + 1 if ends else len(text)
    return start, end


def _extract_carriers(sentence: str) -> list[Carrier]:
    carriers: list[Carrier] = []
    for m in FILE_PATH_CARRIER_RE.finditer(sentence):
        carriers.append(Carrier("file", m.group(1)))
    for m in CI_JOB_CARRIER_RE.finditer(sentence):
        carriers.append(Carrier("ci_job", m.group(1)))
    for m in SKILL_CARRIER_RE.finditer(sentence):
        carriers.append(Carrier("skill", m.group(1)))
    # 队列行号刻意放最后抽：避免把 CI job／skill 名里恰好带 `#` 的片段
    # （实际不会出现，但顺序上先专后泛，行为更可预期）。
    for m in QUEUE_ROW_CARRIER_RE.finditer(sentence):
        carriers.append(Carrier("queue_row", m.group(1)))
    return carriers


def extract_claims(source: str, text: str) -> list[Claim]:
    claims: list[Claim] = []
    for m in MARKER_RE.finditer(text):
        sent_start, sent_end = _sentence_span(text, m.start())
        sentence = text[sent_start:sent_end]
        line_no = text.count("\n", 0, m.start()) + 1
        # 载体只在「标记附近一小段」里找（见 `_CARRIER_WINDOW_*` 上方长注），
        # 但仍以整句边界夹紧，不越过句读。
        win_start = max(sent_start, m.start() - _CARRIER_WINDOW_BEFORE)
        win_end = min(sent_end, m.end() + _CARRIER_WINDOW_AFTER)
        window = text[win_start:win_end]
        claim = Claim(source=source, line_no=line_no, marker=m.group(0),
                       sentence=sentence.strip())
        claim.carriers = _extract_carriers(window)
        claims.append(claim)
    return claims


def extract_no_carrier_imperatives(source: str, text: str) -> list[dict]:
    """state③：命令式约束句 ＋ 全句零结构化载体。"""
    hits = []
    seen_lines = set()
    for m in IMPERATIVE_RE.finditer(text):
        start, end = _sentence_span(text, m.start())
        sentence = text[start:end].strip()
        if not sentence or _extract_carriers(sentence):
            continue
        line_no = text.count("\n", 0, m.start()) + 1
        dedupe_key = (source, line_no)
        if dedupe_key in seen_lines:
            continue
        seen_lines.add(dedupe_key)
        hits.append({"source": source, "line": line_no,
                      "sentence": sentence[:160]})
    return hits


# ------------------------------------------------------------------
# 存在性核验
# ------------------------------------------------------------------

_QUEUE_QUERY_TOOL_REL = "0-学习与工具/工具-队列查询.py"


class ExistenceChecker:
    """把「载体存在与否」的核验手段集中到一处，并缓存重复查询。"""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self._queue_row_cache: dict[str, bool] = {}
        self._ci_jobs: set[str] | None = None
        self._skill_dirs: set[str] | None = None

    def file_exists(self, rel_or_name: str) -> bool:
        direct = self.repo_root / rel_or_name
        if direct.is_file():
            return True
        # 只给了裸文件名（无目录）时，在常见载体目录里按 basename 兜底找一次
        # ——同族既有约定（规则文本里常省略目录，见 `sentinel-pronoun.ps1`
        # 这类写法）；范围刻意收窄到 `.claude/` 与 `0-学习与工具/`，不做
        # 全仓 rglob（避免命中无关同名文件、也避免大仓库上的性能坑）。
        if "/" not in rel_or_name:
            for base in (".claude", "0-学习与工具"):
                base_dir = self.repo_root / base
                if not base_dir.is_dir():
                    continue
                try:
                    if any(base_dir.rglob(rel_or_name)):
                        return True
                except OSError:
                    continue
        return False

    def queue_row_exists(self, row_id: str) -> bool:
        if row_id in self._queue_row_cache:
            return self._queue_row_cache[row_id]
        tool = self.repo_root / _QUEUE_QUERY_TOOL_REL
        found = False
        if tool.is_file():
            try:
                proc = subprocess.run(
                    [sys.executable, str(tool), "--row", row_id, "--format", "json"],
                    cwd=self.repo_root, capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=30,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    payload = json.loads(proc.stdout)
                    found = bool(payload.get("found"))
            except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
                found = False
        self._queue_row_cache[row_id] = found
        return found

    def _load_ci_jobs(self) -> set[str]:
        if self._ci_jobs is not None:
            return self._ci_jobs
        jobs: set[str] = set()
        for path in (self.repo_root / ".github" / "workflows").glob("*.yml"):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            in_jobs_block = False
            for line in text.splitlines():
                if re.match(r"^jobs:\s*$", line):
                    in_jobs_block = True
                    continue
                if not in_jobs_block:
                    continue
                m = re.match(r"^  ([a-zA-Z0-9_-]+):\s*$", line)
                if m:
                    jobs.add(m.group(1))
                elif line and not line.startswith(("  ", "\t")):
                    in_jobs_block = False
        self._ci_jobs = jobs
        return jobs

    def ci_job_exists(self, job_id: str) -> bool:
        return job_id in self._load_ci_jobs()

    def _load_skill_dirs(self) -> set[str]:
        if self._skill_dirs is not None:
            return self._skill_dirs
        names: set[str] = set()
        for base in (".claude/skills", "0-学习与工具/skills源码"):
            base_dir = self.repo_root / base
            if not base_dir.is_dir():
                continue
            for child in base_dir.iterdir():
                if child.is_dir():
                    names.add(child.name)
        self._skill_dirs = names
        return names

    def skill_exists(self, name: str) -> bool:
        return name in self._load_skill_dirs()

    def carrier_exists(self, carrier: Carrier) -> bool:
        if carrier.kind == "file":
            return self.file_exists(carrier.value)
        if carrier.kind == "queue_row":
            return self.queue_row_exists(carrier.value)
        if carrier.kind == "ci_job":
            return self.ci_job_exists(carrier.value)
        if carrier.kind == "skill":
            return self.skill_exists(carrier.value)
        return False


# ------------------------------------------------------------------
# state② 疑似真实落点关键词回查
# ------------------------------------------------------------------

_CJK_TOKEN_RE = re.compile(r"[一-鿿]{2,}|[a-zA-Z][a-zA-Z0-9_-]{2,}")


def _keywords_from_sentence(sentence: str) -> list[str]:
    # 反引号内容本身就是「已判定不存在的载体」，不当关键词用（否则
    # state② 会把「自陈的载体名」当关键词去别处搜，永远搜不到自己）。
    stripped = re.sub(r"`[^`]*`", " ", sentence)
    raw_tokens = [t for t in _CJK_TOKEN_RE.findall(stripped) if t not in STOPWORDS]
    # 中文连写无天然分词边界，一段连续 CJK 常把多个语义词粘成一整串
    # （如「承接稀土价格扫描」＝「承接」＋「稀土价格」＋「扫描」）——只拿
    # 整串去别处比对基本搜不中。长串额外滑窗切 4 字／3 字子串兜底召回，
    # 短串（≤4 字，本身多半就是一个词）原样保留。
    expanded: list[str] = []
    for t in raw_tokens:
        expanded.append(t)
        if len(t) > 4:
            for width in (4, 3):
                for i in range(len(t) - width + 1):
                    expanded.append(t[i:i + width])
    # 去重、保序，只留 ≥3 字（2 字太通用、误配对率高），取前 20 个候选。
    seen = []
    for t in expanded:
        if len(t) >= 3 and t not in seen:
            seen.append(t)
    return seen[:20]


def find_suspected_real_location(repo_root: Path, sentence: str) -> str | None:
    keywords = _keywords_from_sentence(sentence)
    if not keywords:
        return None
    for pattern, _label in CANDIDATE_REAL_LOCATIONS:
        for path in sorted(repo_root.glob(pattern)):
            if not path.is_file():
                continue
            haystack = path.name
            try:
                haystack += "\n" + path.read_text(encoding="utf-8", errors="replace")[:4000]
            except OSError:
                pass
            hit_kw = next((kw for kw in keywords if kw in haystack), None)
            if hit_kw:
                rel = path.relative_to(repo_root).as_posix()
                return f"`{rel}`（关键词「{hit_kw}」命中）"
    return None


# ------------------------------------------------------------------
# 主流程
# ------------------------------------------------------------------

def scan(repo_root: Path) -> dict:
    checker = ExistenceChecker(repo_root)
    missing: list[dict] = []       # state①
    misdirected: list[dict] = []   # state②
    no_carrier: list[dict] = []    # state③
    markerless: list[dict] = []    # 附加：标记出现但零结构化载体（不计三态）
    errors: list[str] = []
    notes: list[str] = []
    sources_scanned: list[str] = []

    gen = iter_scan_sources(repo_root)
    while True:
        try:
            source, text = next(gen)
        except StopIteration as stop:
            if stop.value:
                errors.extend(stop.value[0])
                notes.extend(stop.value[1])
            break
        sources_scanned.append(source)
        claims = extract_claims(source, text)
        for claim in claims:
            if not claim.carriers:
                markerless.append({
                    "source": claim.source, "line": claim.line_no,
                    "marker": claim.marker, "sentence": claim.sentence[:160],
                })
                continue
            for carrier in claim.carriers:
                exists = checker.carrier_exists(carrier)
                if exists:
                    continue
                record = {
                    "source": claim.source, "line": claim.line_no,
                    "marker": claim.marker, "carrier_kind": carrier.kind,
                    "carrier_value": carrier.value,
                    "sentence": claim.sentence[:200],
                    "key": f"{claim.key}:{carrier.kind}:{carrier.value}",
                }
                suspected = find_suspected_real_location(repo_root, claim.sentence)
                if suspected:
                    record["suspected_real_location"] = suspected
                    misdirected.append(record)
                else:
                    missing.append(record)
        no_carrier.extend(extract_no_carrier_imperatives(source, text))

    return {
        "missing": missing,
        "misdirected": misdirected,
        "no_carrier": no_carrier,
        "markerless": markerless,
        "errors": errors,
        "notes": notes,
        "sources_scanned": sources_scanned,
    }


def format_report(findings: dict) -> str:
    lines = ["# 承载性一致性扫描 · 本轮全文", ""]
    lines.append(f"扫描面：{len(findings['sources_scanned'])} 份文件／小节。")
    if findings["errors"]:
        lines.append(f"\n## 扫描面读取异常（{len(findings['errors'])} 项，**不据此判为干净**）\n")
        for err in findings["errors"]:
            lines.append(f"- {err}")
    if findings["notes"]:
        lines.append(f"\n## 备注（{len(findings['notes'])} 项，非扫描器故障，供人工核实）\n")
        for note in findings["notes"]:
            lines.append(f"- {note}")

    lines.append(f"\n## ① 缺失（{len(findings['missing'])} 项）\n")
    if not findings["missing"]:
        lines.append("（零命中）")
    for item in findings["missing"]:
        lines.append(
            f"- `{item['source']}` L{item['line']}｜标记「{item['marker']}」｜"
            f"载体（{item['carrier_kind']}）`{item['carrier_value']}` 不存在\n"
            f"  > {item['sentence']}"
        )

    lines.append(f"\n## ② 指错载体（{len(findings['misdirected'])} 项，核心态）\n")
    if not findings["misdirected"]:
        lines.append("（零命中）")
    for item in findings["misdirected"]:
        lines.append(
            f"- `{item['source']}` L{item['line']}｜标记「{item['marker']}」｜"
            f"自陈载体（{item['carrier_kind']}）`{item['carrier_value']}` 不存在，"
            f"疑似真实落点：{item['suspected_real_location']}\n"
            f"  > {item['sentence']}"
        )

    lines.append(f"\n## ③ 无载体清单（{len(findings['no_carrier'])} 项，只列不报警）\n")
    if not findings["no_carrier"]:
        lines.append("（零命中）")
    for item in findings["no_carrier"][:200]:
        lines.append(f"- `{item['source']}` L{item['line']}｜{item['sentence']}")
    if len(findings["no_carrier"]) > 200:
        lines.append(f"- …另有 {len(findings['no_carrier']) - 200} 条未列出")

    lines.append(f"\n## 附：标记出现但未抽出结构化载体（{len(findings['markerless'])} 项，人工判断，不计入三态）\n")
    if not findings["markerless"]:
        lines.append("（零命中）")
    for item in findings["markerless"][:100]:
        lines.append(f"- `{item['source']}` L{item['line']}｜标记「{item['marker']}」\n  > {item['sentence']}")

    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--json", action="store_true", help="额外输出 JSON 到 stdout")
    parser.add_argument("--write-report", action="store_true",
                        help=f"把全文报告写入 `{REPORT_REL}`（默认只打印摘要）")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root) if args.repo_root else find_repo_root(Path(__file__).parent)
    findings = scan(repo_root)

    if args.write_report:
        report_path = repo_root / REPORT_REL
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(format_report(findings) + "\n", encoding="utf-8")
        print(f"已写入 {report_path}")

    print(
        f"扫描面 {len(findings['sources_scanned'])} 份｜① 缺失 {len(findings['missing'])}｜"
        f"② 指错 {len(findings['misdirected'])}｜③ 无载体 {len(findings['no_carrier'])}｜"
        f"附·标记未抽出 {len(findings['markerless'])}｜异常 {len(findings['errors'])}｜"
        f"备注 {len(findings['notes'])}"
    )
    if args.json:
        print(json.dumps(findings, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
