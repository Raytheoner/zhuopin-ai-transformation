"""平台底座路径引导样板 lint（队列 #345 第二步 / 变更包 platform-bootstrap-ensure-paths 决策点 4）。

## 为什么要有这道门禁

本变更包退休了根 CLAUDE.md §5「新场景 scaffold 时照抄既有场景引导代码片段」这条**人守**
约定。退休制要求二选一：机制化，或删除。**光把 CLAUDE.md 改成一行指针不算机制化**——那
只是用一条人守换另一条人守，而 SC2（2026-08-18 新建，晚于 #300 修复共识）已经证明人守在
这里无效：规则被遵守了（作者确实去抄了），结果仍是错的（抄到的是无条件 raise 的 A 形态，
抄到哪一种取决于他当时看的是哪个文件）。**本脚本就是那条对价。**

## 判据

已跟踪的 `.py` 文件里，凡出现**向上逐级搜索**祖先目录找 `5-平台底座/zhuopin_platform`
标记的引导块，唯一被允许的形态是调用 `ensure_paths()` 的极小 stub：

    _HERE = Path(__file__).resolve()
    for _p in _HERE.parents:
        if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
            sys.path.insert(0, str(_p / "5-平台底座" / "zhuopin_platform"))
            break
    from zhuopin_platform.bootstrap import ensure_paths  # noqa: E402
    ensure_paths(__file__, <自身包根>[, strict=True])  # noqa: E402

判违规的信号（任一命中即报）：
① 文件里**没有** `ensure_paths(` 调用 —— 判断还留在文件里，没有收拢；
② 用了旧遍历写法 `for _p in (_HERE, *_HERE.parents)` —— 那是 35 份手抄副本的共同指纹
   （`_HERE` 是文件、不可能命中标记，把它放进遍历本就无意义）；
③ 块内出现 `else:` / `raise` / `find_spec` —— 布局与失败判断现在只该在 `bootstrap.py` 一处。

## 刻意不覆盖的另一族（范围克制，不是遗漏）

`0-学习与工具/` 下的编辑锁／sweep／队列结构 lint／队列查询／文档台账，以及 SC8
`build_golden_real.py`，是**按固定层数算出平台底座路径**、不做祖先搜索的另一族；其中几个
的 `else` 分支是队列 #313④⑤ **刻意设计**的"隔离环境兜底桩／CI 可达性断言"，并进来会把那个
语义毁掉。它们另行登记，不在本门禁范围内——**门禁宁可窄而准，不可宽到逼人不断加豁免**
（豁免一多，门禁就名存实亡）。

## 过渡期

决策点 4 的默认项是「(a) CI 硬门禁 ＋ 过渡期先按 (c) 跑一轮告警不阻断」。故本脚本默认
只告警、退出码 0；加 `--enforce` 才阻断。CI 在存量真实清零后切 `--enforce`——**先确认清零、
再关门**，否则门禁上线第一天就是红的，只会被习惯性忽略。

用法：
  python 0-学习与工具/工具-引导样板lint.py            # 告警模式（退出码恒 0）
  python 0-学习与工具/工具-引导样板lint.py --enforce   # 阻断模式（有违规即 1）
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

MARKER_RE = re.compile(r'"5-平台底座"\s*/\s*"zhuopin_platform"')
# 只认「向上逐级搜索祖先目录」这一个签名——正是 spec 场景点名的那个形状。
ANCESTOR_SEARCH_RE = re.compile(r"for _p in \(?_HERE(?:, ?\*_HERE\.parents\)|\.parents)")
LEGACY_LOOP_RE = re.compile(r"for _p in \(_HERE, \*_HERE\.parents\)")
CANONICAL_LOOP_RE = re.compile(r"for _p in _HERE\.parents")
ENSURE_CALL_RE = re.compile(r"\bensure_paths\(")

# 引导块内允许出现的**顶层**语句形状——只用于判定块到哪一行为止，不代表它们合规。
BLOCK_TOP_LEVEL = tuple(re.compile(p) for p in (
    r"^_HERE\b", r"^_entries\b", r"^for _p in ", r"^else:\s*$", r"^for _entry in ",
    r"^from zhuopin_platform\.bootstrap import ", r"^ensure_paths\(",
))

# 豁免：判断的唯一合法归宿，与三个以真实 stub 文本／合成布局为夹具的测试/工具自身。
EXEMPT_SUFFIXES = (
    "5-平台底座/zhuopin_platform/zhuopin_platform/bootstrap.py",
    "5-平台底座/zhuopin_platform/tests/test_worktree_import_bootstrap.py",
    "5-平台底座/zhuopin_platform/tests/test_bootstrap_ensure_paths.py",
    "0-学习与工具/工具-引导样板lint.py",
    "0-学习与工具/test_工具-引导样板lint.py",
)


def _tracked_py_files(repo_root: Path) -> list[str]:
    # -c core.quotepath=false：git 默认会把中文路径八进制转义，本项目路径几乎全是中文
    # （同 `工具-密钥扫描lint.py`，成因见该文件注释）。
    out = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files", "*.py"],
        cwd=repo_root, capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout
    return [ln for ln in out.splitlines() if ln.strip()]


def _block_bounds(lines: list[str]) -> tuple[int, int] | None:
    """定位引导块的行号区间（0-based，[lo, hi) 半开）；不属本门禁范围则返回 None。

    边界靠"块内成分"判定，而不是固定前瞻若干行——早期版本用「标记行 + 4 行前瞻」，会把
    A 形态末尾的 `raise`、B 形态的 `find_spec` 恰好切在块外，于是门禁只报得出"未收拢"
    这一条、报不出真正的判断分支。单测 `test_A形态_无条件raise` 就是钉住这一点的。
    """
    if not any(ANCESTOR_SEARCH_RE.search(ln) for ln in lines):
        return None            # 无祖先搜索 ⇒ 另一族，不属本门禁范围（见模块 docstring）
    if not any(MARKER_RE.search(ln) for ln in lines):
        return None

    lo = next(i for i, ln in enumerate(lines) if ANCESTOR_SEARCH_RE.search(ln))
    while lo > 0 and lines[lo - 1].startswith(("_HERE", "_entries")):
        lo -= 1

    hi = lo
    while hi < len(lines):
        ln = lines[hi]
        if (ln.strip() == "" or ln.startswith((" ", "\t", "#"))
                or any(pat.match(ln) for pat in BLOCK_TOP_LEVEL)):
            hi += 1
            continue
        break
    return lo, hi


def check_file(rel_path: str, text: str) -> list[str]:
    if rel_path.replace("\\", "/").endswith(EXEMPT_SUFFIXES):
        return []
    lines = text.splitlines()
    bounds = _block_bounds(lines)
    if bounds is None:
        return []
    lo, hi = bounds
    block = "\n".join(lines[lo:hi])

    problems: list[str] = []
    if not ENSURE_CALL_RE.search(text):
        problems.append("引导块未收拢：全文找不到 ensure_paths() 调用")
    if LEGACY_LOOP_RE.search(block):
        problems.append("用了旧遍历写法 `for _p in (_HERE, *_HERE.parents)`，"
                        "应为 `for _p in _HERE.parents`")
    elif not CANONICAL_LOOP_RE.search(block):
        problems.append("stub 遍历写法不是 `for _p in _HERE.parents`")
    if re.search(r"^\s*else:", block, re.M):
        problems.append("引导块含 else 分支：布局判断应只存在于 bootstrap.ensure_paths()")
    for token in ("raise", "find_spec"):
        if re.search(rf"\b{token}\b", block):
            problems.append(f"引导块含 {token}：失败判断应只存在于 bootstrap.ensure_paths()")
    return [f"{rel_path}: {p}" for p in problems]


def main() -> int:
    ap = argparse.ArgumentParser(description="平台底座路径引导样板 lint")
    ap.add_argument("--enforce", action="store_true",
                    help="有违规即以退出码 1 阻断（默认只告警、退出码 0）")
    args = ap.parse_args()

    files = _tracked_py_files(REPO_ROOT)
    violations: list[str] = []
    scanned = 0
    for rel in files:
        try:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if MARKER_RE.search(text) and ANCESTOR_SEARCH_RE.search(text):
            scanned += 1
        violations.extend(check_file(rel, text))

    if not violations:
        print(f"✓ 引导样板 lint 通过（{len(files)} 个已跟踪 .py，其中 {scanned} 个含引导块，"
              "全部为 ensure_paths() stub 形态）。")
        return 0

    mode = "阻断" if args.enforce else "告警（过渡期，不阻断）"
    print(f"✗ 引导样板 lint 发现 {len(violations)} 处违规【{mode}】：")
    for v in violations:
        print(f"  - {v}")
    print("\n  唯一被允许的样板见 "
          "`5-平台底座/zhuopin_platform/zhuopin_platform/bootstrap.py` 模块 docstring。")
    return 1 if args.enforce else 0


if __name__ == "__main__":
    sys.exit(main())
