# -*- coding: utf-8 -*-
"""⑷ 收窄判据的误报率对比 + ⑸ 撞号是不是真撞号。"""
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(sys.argv[1])
QUEUES = [
    "1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md",
    "1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md",
]
MALE = ["姚祖怡", "泓钦", "陈承", "朱映桦", "解植雅", "汤易水", "孙涛",
        "袁洋", "刘伟", "聂鑫", "邵培申"]
FEMALE = ["陈忱", "唐燕萍", "李姣龙", "钱婷", "孙国庆", "陶钰", "朱云澜",
          "叶燕", "齐奇", "汤丽萍"]


def section_rows(text, heading_prefix):
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


NOT_TA = ("其他", "其它", "他们", "他人", "他处", "他方", "他日", "其他人")


def mask_non_pronoun_ta(text):
    """把非代词用法的『他』遮成 〇，其余保留。"""
    out = text
    for w in NOT_TA:
        out = out.replace(w, "〇" * len(w))
    return out


def hits_wholecell(text, names, pronoun):
    if pronoun == "他":
        text = mask_non_pronoun_ta(text)
    found = [n for n in names if n in text]
    return found if (found and pronoun in text) else []


def hits_proximity(text, names, pronoun, window):
    """人名之后 window 字符内出现该代词，且这段里没有出现异性名字。"""
    scan = mask_non_pronoun_ta(text) if pronoun == "他" else text
    other = FEMALE if names is MALE else MALE
    res = []
    for n in names:
        for m in re.finditer(re.escape(n), scan):
            seg = scan[m.end():m.end() + window]
            if pronoun in seg:
                cut = seg[:seg.index(pronoun)]
                if any(o in cut for o in other):
                    continue          # 中间隔着异性名字，代词多半指那个人
                res.append((n, scan[max(0, m.start() - 20):m.end() + window]))
    return res


for window in (None, 40, 25, 15):
    tp = 0
    samples = []
    for q in QUEUES:
        text = (ROOT / q).read_text(encoding="utf-8")
        for sec in ("一、", "二、", "四、"):
            for line, cells in section_rows(text, sec):
                for names, pronoun in ((MALE, "她"), (FEMALE, "他")):
                    if window is None:
                        h = hits_wholecell(line, names, pronoun)
                        if h:
                            tp += 1
                    else:
                        h = hits_proximity(line, names, pronoun, window)
                        if h:
                            tp += 1
                            if len(samples) < 6:
                                samples.append((pronoun, h[0][0], h[0][1][:110]))
    label = "整行（无收窄）" if window is None else f"邻近 {window} 字"
    print(f"── {label}：命中 {tp} 行")
    for s in samples:
        print(f"     [{s[1]}→{s[0]}] …{s[2]}…")
    print()

print("=" * 20, "⑸ 撞号明细（看是不是真撞号）", "=" * 20)
byprefix = defaultdict(list)
for q in QUEUES:
    text = (ROOT / q).read_text(encoding="utf-8")
    for line, cells in section_rows(text, "二、"):
        if len(cells) != 4:
            continue
        m = re.match(r"^(B-\d{4})_(\S+?)(?:_|$)", cells[0])
        if m:
            byprefix[m.group(1) + "_" + m.group(2)].append(cells[0])
n = 0
for k, v in sorted(byprefix.items()):
    if len(v) > 1:
        n += 1
        if n <= 12:
            print(f"  {k} ×{len(v)}")
            for name in v:
                print(f"      {name}")
print(f"→ 撞号前缀共 {n} 个")
