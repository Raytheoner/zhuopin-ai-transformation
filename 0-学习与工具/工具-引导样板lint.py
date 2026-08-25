"""平台底座**引导与凭据锚定**样板 lint（队列 #345 第二步 ＋ #354 收拢，两道判据一处守）。

> 🔴 **文件名只说了一半，是刻意的**：本脚本现在守两族——`sys.path` 引导（#345）与 `.env`
> 凭据锚定（#354）。**不改文件名**——改名会打断 CI 配置与全库引用，而那两处的收益远小于
> 代价（变更包 `env-anchor-collapse` 决策点 5(a) 明确如此定）。适用范围以本 docstring 为准。

## 两族判据（一处守，账最清楚）

| | 守什么 | 收拢到哪 | 来源 |
|---|---|---|---|
| 判据一 | `sys.path` 引导块的手抄形态 | `zhuopin_platform/bootstrap.py::ensure_paths` | #345 |
| 判据二 | 「向上逐级找 `.env`」的手抄形态 | `zhuopin_platform/env_anchor.py::load_env` | #354 |

两族是**同一条人守的两半**：#345 退休了「照抄既有场景的引导代码」，却把 `.env` 那半留在原地
（该变更包 design 决策点 5 明确列为 Non-Goal）——**#354 就是被留下的那一半自己发作了**，
而且这次漂的是密钥（前两次漂的是状态文件，丢了会重来；密钥用错了不会报错，只会发到一个
早已作废的地址）。故 one-in-one-out 落在同一个文件里。

## 为什么要有这道门禁

本变更包退休了根 CLAUDE.md §5「新场景 scaffold 时照抄既有场景引导代码片段」这条**人守**

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

## 判据二：向上逐级找 `.env`（#354）

已跟踪的 `.py` 里，凡出现「从本文件向上逐级搜索祖先目录、命中即取那份 `.env`」的循环，
即违规——正确写法是一行 `zhuopin_platform.env_anchor.load_env(__file__)`。

🔴 **判据锚在 AST 结构，不用裸子串**（tasks 3.2，#355 与 #324 两次教训）：判据只看
**`for`/`while` 循环节点的子树**里是否同时出现「`.env` 字面量」与「向上走的动作」
（`.parents` 属性访问，或 `os.path.dirname` 调用）。**讲解这个反范式的散文一律不命中**——
模块/函数 docstring 是循环体外的 `Constant`，根本不在被检查的子树里。这一条不是理论：
本变更包收拢后的 9 个入口，其 `load_env()` docstring 全都在逐字描述这个反范式，裸子串判据
会把它们全部点亮，然后被习惯性忽略。

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
import ast
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

# ── 判据二（#354）：向上逐级找 `.env` ──────────────────────────────────────────

#: 判据二的豁免清单（tasks 3.3）。每一条都写明**为什么**——豁免不写理由，下一个人只能猜，
#: 而猜的结果通常是再加一条（豁免一多，门禁就名存实亡）。
ENV_ANCHOR_EXEMPT: tuple[tuple[str, str], ...] = (
    ("5-平台底座/zhuopin_platform/zhuopin_platform/env_anchor.py",
     "判断的唯一合法归宿——收拢的目的地本身"),
    ("5-平台底座/zhuopin_platform/tests/test_env_anchor.py",
     "内含 A 家族原文作**变异验证**夹具：判据若不认它，整套测试是空转的"),
    ("1-转型规划/AI运营指挥中心/tests/test_serve_env_anchor_parity.py",
     "内含 serve.py 修复前原文作变异验证夹具，同上"),
    ("1-转型规划/AI运营指挥中心/serve.py",
     "🔴 **唯一的生产例外，且是刻意的**：本服务「零三方依赖」是既定设计原则，`.51` 上跑裸 "
     "`python serve.py`、部署侧无 venv 也无 `pip install -e zhuopin_platform`，import 平台底座"
     "会让 8092 命令中心在生产起不来而本地全绿（#345 原话：本地永远能找到标记）。其内联实现"
     "与平台底座那份的**等价性**由 `tests/test_serve_env_anchor_parity.py` 逐布局钉死，"
     "不是无人看管的第 10 种语义"),
)

#: `0-学习与工具/` 工具族——与判据一同源的范围克制（见上文「刻意不覆盖的另一族」）。
ENV_ANCHOR_EXEMPT_PREFIXES = ("0-学习与工具/",)


def _env_anchor_exempt(rel_path: str) -> bool:
    norm = rel_path.replace("\\", "/")
    return (norm.startswith(ENV_ANCHOR_EXEMPT_PREFIXES)
            or any(norm.endswith(suffix) for suffix, _reason in ENV_ANCHOR_EXEMPT))


def _walks_upward(node: "ast.AST") -> bool:
    """子树里有没有「向上走」的动作：`.parents` 属性访问，或 `os.path.dirname(...)` 调用。"""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and sub.attr in ("parents", "parent"):
            return True
        if isinstance(sub, ast.Attribute) and sub.attr == "dirname":
            return True
    return False


def _mentions_env_file(node: "ast.AST") -> bool:
    """子树里有没有 `.env` 字面量（含 `.env.test` 等派生名）。"""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            if sub.value == ".env" or sub.value.startswith(".env."):
                return True
    return False


def check_env_anchor(rel_path: str, text: str) -> list[str]:
    """判据二：AST 上找「循环 ＋ 向上走 ＋ `.env` 字面量」的合流点。

    🔴 **只看 `for`/`while` 节点的子树**——docstring 与注释是循环体外的东西，天然不在范围内。
    这正是「区分缺陷本身与讲解这个反范式的散文」的实现方式（tasks 3.2）。
    """
    if _env_anchor_exempt(rel_path):
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    problems: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.For, ast.While)):
            continue
        if _mentions_env_file(node) and _walks_upward(node):
            problems.append(
                f"{rel_path}:{node.lineno}: 向上逐级找 `.env` 的手抄形态——"
                "应改为一行 `zhuopin_platform.env_anchor.load_env(__file__)`"
                "（队列 #354；从 linked worktree 跑时本写法命中陈旧副本且不报错）"
            )
    return problems


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
    env_violations: list[str] = []
    scanned = 0
    for rel in files:
        try:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if MARKER_RE.search(text) and ANCESTOR_SEARCH_RE.search(text):
            scanned += 1
        violations.extend(check_file(rel, text))
        env_violations.extend(check_env_anchor(rel, text))

    if not violations and not env_violations:
        print(f"✓ 引导与凭据锚定 lint 通过（{len(files)} 个已跟踪 .py，其中 {scanned} 个含引导块，"
              "全部为 ensure_paths() stub 形态；零「向上逐级找 .env」手抄形态）。")
        return 0

    mode = "阻断" if args.enforce else "告警（过渡期，不阻断）"
    total = len(violations) + len(env_violations)
    print(f"✗ 引导与凭据锚定 lint 发现 {total} 处违规【{mode}】：")
    if violations:
        print(f"  ── 判据一 · sys.path 引导（#345），{len(violations)} 处 ──")
        for v in violations:
            print(f"  - {v}")
        print("    唯一被允许的样板见 "
              "`5-平台底座/zhuopin_platform/zhuopin_platform/bootstrap.py` 模块 docstring。")
    if env_violations:
        print(f"  ── 判据二 · .env 凭据锚定（#354），{len(env_violations)} 处 ──")
        for v in env_violations:
            print(f"  - {v}")
        print("    唯一被允许的写法见 "
              "`5-平台底座/zhuopin_platform/zhuopin_platform/env_anchor.py` 模块 docstring。")
    return 1 if args.enforce else 0


if __name__ == "__main__":
    sys.exit(main())
