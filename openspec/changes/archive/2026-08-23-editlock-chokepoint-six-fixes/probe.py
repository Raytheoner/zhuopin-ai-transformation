# -*- coding: utf-8 -*-
"""对 §二 现存批次行做三项取证：⑶ 路径格式、⑸ 批次号重名、⑷ 性别代词误报率。"""
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(sys.argv[1])
QUEUES = [
    "1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md",
    "1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md",
]
EXTS = {".md", ".py", ".json", ".yaml", ".yml", ".txt", ".html", ".ps1", ".docx",
        ".xlsx", ".csv", ".jsonl", ".sh", ".cfg", ".toml", ".ini", ".js", ".ts",
        ".bat", ".log", ".xml", ".sql", ".env", ".gitignore"}


def section_rows(text, heading_prefix):
    """返回 §heading 下的数据行 cells 列表（简易切列，够取证用）。"""
    m = re.search(r"^## " + heading_prefix, text, re.M)
    if not m:
        return []
    rest = text[m.end():]
    nxt = re.search(r"^## ", rest, re.M)
    if nxt:
        rest = rest[:nxt.start()]
    rows = []
    for line in rest.splitlines():
        s = line.strip()
        if not (s.startswith("|") and s.endswith("|")):
            continue
        cells = [c.strip() for c in s[1:-1].split("|")]
        if all(set(c) <= set("-: ") for c in cells):
            continue
        rows.append((s, cells))
    return rows


def looks_like_path(frag):
    f = frag.strip()
    if not f:
        return False
    if f.endswith("/"):
        return True
    suf = Path(f).suffix.lower()
    return suf in EXTS


def path_format_problem(frag):
    f = frag.strip()
    if re.match(r"^[A-Za-z]:[\\/]", f) or f.startswith("/") or f.startswith("\\\\"):
        return "绝对路径"
    if "\\" in f:
        return "反斜杠分隔符"
    if f.startswith("./") or f.startswith("../"):
        return "相对前缀"
    if "/" not in f:
        return None if (ROOT / f).exists() else "裸文件名（仓库根下不存在同名文件）"
    return None


print("=" * 20, "⑶ 路径格式取证", "=" * 20)
fmt_bad = Counter()
exist_bad = []
total_frag = 0
for q in QUEUES:
    text = (ROOT / q).read_text(encoding="utf-8")
    for line, cells in section_rows(text, "二、"):
        if len(cells) != 4:
            continue
        for frag in re.findall(r"`([^`]+)`", cells[1]):
            if not looks_like_path(frag):
                continue
            total_frag += 1
            p = path_format_problem(frag)
            if p:
                fmt_bad[p] += 1
                if fmt_bad[p] <= 4:
                    print(f"  [{p}] {frag}   ← 批次 {cells[0][:40]}")
            elif "/" in frag and not (ROOT / frag).exists():
                exist_bad.append((cells[0][:40], frag))
print(f"→ 形如路径的片段共 {total_frag} 个；格式违规 {sum(fmt_bad.values())} 个 {dict(fmt_bad)}")
print(f"→ 格式合规但当前磁盘上不存在的：{len(exist_bad)} 个（若加存在性校验即为误报量）")
for b in exist_bad[:8]:
    print("   ", b)

print("=" * 20, "⑸ 批次号重名取证", "=" * 20)
prefixes = Counter()
for q in QUEUES:
    text = (ROOT / q).read_text(encoding="utf-8")
    for line, cells in section_rows(text, "二、"):
        if len(cells) != 4:
            continue
        m = re.match(r"^(B-\d{4}_\d+)", cells[0])
        if m:
            prefixes[m.group(1)] += 1
dups = {k: v for k, v in prefixes.items() if v > 1}
print(f"→ 现存批次号前缀 {len(prefixes)} 个，其中重名 {len(dups)} 个：{dups}")

print("=" * 20, "⑷ 性别代词取证", "=" * 20)
MALE = ["姚祖怡", "泓钦", "陈承", "朱映桦", "解植雅", "汤易水", "孙涛",
        "袁洋", "刘伟", "聂鑫", "邵培申"]
FEMALE = ["陈忱", "唐燕萍", "李姣龙", "钱婷", "孙国庆", "陶钰", "朱云澜",
          "叶燕", "齐奇", "汤丽萍"]
STANDALONE_TA = re.compile(r"(?<!其)(?<!其)他(?!们)(?!人)")
hit_m = hit_f = 0
samples = []
for q in QUEUES:
    text = (ROOT / q).read_text(encoding="utf-8")
    for sec in ("一、", "二、", "四、"):
        for line, cells in section_rows(text, sec):
            names_m = [n for n in MALE if n in line]
            names_f = [n for n in FEMALE if n in line]
            if names_m and "她" in line:
                hit_m += 1
                if len(samples) < 5:
                    samples.append(("男名+她", names_m, line[:90]))
            cleaned = line.replace("其他", "").replace("其它", "").replace("他们", "").replace("他人", "")
            if names_f and "他" in cleaned:
                hit_f += 1
                if len(samples) < 10:
                    samples.append(("女名+他", names_f, line[:90]))
print(f"→ 男名+『她』命中 {hit_m} 行；女名+独立『他』命中 {hit_f} 行")
for s in samples:
    print("   ", s[0], s[1], s[2])
