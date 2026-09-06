"""opener 生成器 —— 按 `opener骨架.md` 唯一格式来源，参数化拼出成品 opener（队列 §一 `#461`）。

## 背景与取号

队列 `#461`（`OP-0902-X2` 立行，2026-09-02）委托本工具承接"格式＋编号两件同源解决"——
此前手写 opener 反复漏字段（`工具-opener块lint.py` 记录的形态①~⑤），本工具把拼装步骤
机制化，缺字段直接报错退出、不出半成品。

🔴 **格式正本的时效说明（本次建造实测发现，写入供后续核对）**：`#461` 行原文写
"§〇.00 骨架本批同时落档，生成器可直接以它为唯一格式来源"——这句在 2026-09-02 写下时
准确，但 `专线opener模板库.md` 已于 **2026-09-04 A2 瘦身**把骨架正文迁出（该库 §〇.00
现在只剩一句指针）。当前唯一可照抄物是 `1-转型规划/0-全景路线图/opener骨架.md`
（根 `CLAUDE.md` §3 与模板库 §〇.00 均已指向这里）。本工具的 CC/Cowork 模板即按该文件
2026-09-04 生效版逐字对齐，**不从模板库 §〇 任一节重建**。

## 判据复用（不写第二份）

拼装结果自检复用 `工具-opener块lint.py::check_block`（同一份判据实现），不再自造第二套
"opener 块合不合格"的规则——理由与该 lint 脚本本身"不写第二份"的告诫一致：两处各自
实现同一判据、然后悄悄漂移，是本项目已反复踩过的坑。

## P7① 撞号查重（构建环境瘦身第三轮方案-2026-09-05 P7；队列 §一 `#487`）

`OP-0904-E` 曾撞号——两条互不知情的线各自取了同一个编号。取号规则本身写在
`opener骨架.md` 文末（人守 `grep`），但人守就会漏跑。本工具在 `generate_opener`
内加一道机器守：按 `--op-id` 的 `MMDD` 部分，扫 `1-转型规划/` 全树 `.md`，收集当日
已出现过的编号后缀——**全称**（`OP-MMDD-X`）与**短形**（`[Win]MMDDX-`，仅认这个
锚点，不做全文裸子串扫描，见 `opener骨架.md`「短形 MMDDX 只用于 session 名」）
两种形态皆计入。命中即拒绝，报错信息里直接给出当日下一个未用的空号，不需要
调用方自己再算一遍。

## variant：三种骨架变体（构建环境瘦身第三轮方案 P2/P4；队列 §一 `#487`）

- `standard`（默认）：骨架【CC】／【Cowork】标准变体，含 `set_session_title` 行。
- `subtask_lane`：骨架【CC · 子任务泳道】变体——**不含** `set_session_title` 行
  （2026-09-05 队列 §一 `#487`／(甲) 拍板：源头不放，不指望子任务读懂例外句），
  收尾无条件追加 P4 两条默认口径（并行上限 4／错峰 ≥90 秒；只 push 分支不 ff）。
- `guardian`：骨架 §三bis 看护者开场词变体——含 `set_session_title`（它是本批
  唯一真正被粘贴进独立 CC 会话的一份），分支字段是固定字面量（看护者本身不建
  分支），正文追加同一条 P4 默认口径（这次是讲给看护者听，指导它怎么起子任务）。

## `--do` / `--dont` 的静默丢弃守卫（队列 §一 `#487` 子项／`OP-0906-M`，2026-09-06）

2026-09-06 实撞：`--env Cowork --dont "<三条硬约束>"` **既不生效也不报错**——不是工具
bug，是当时【Cowork】骨架本身只有「做什么／收工」两段。判据：**一个参数被接受却不
生效，比它被拒绝更危险。**

Shao Peishen 2026-09-06 裁 **(c) 甲＋精简版乙**，两个洞分别用两种手法堵：

- **Cowork ⇒ 让它生效（方案甲）**：骨架【Cowork】节补「不做什么」段、本工具 Cowork
  分支拼 `dont_block`、`工具-opener块lint.py` 形态⑦机器守。**Cowork 不再被本守卫拦。**
- **`--variant guardian` ⇒ fail-loud（精简版乙）**：§三bis 看护者开场词是固定形态
  （四行 ＋ P4 扇出口径），正文既不拼 `--do` 也不拼 `--dont`，且**不该**为它补段
  （看护者的任务正本在看护件全文里）。这个洞补段补不掉，只能报错退出（退出码 1），
  并在报错信息里给出该走哪条承接路径。

`BODY_PARAM_SUPPORT` 白名单登记每个「环境×变体」真的会拼进成品的正文参数；
🔴 **白名单而非黑名单**——黑名单忘登记 ⇒ 回到静默丢弃（fail-open，看不见），
白名单忘登记 ⇒ 该组合所有可选正文参数一律被拒（fail-closed，噪音大但当场看得见）。

## 用法

    python 0-学习与工具/工具-opener生成.py --env CC \\
        --op-id OP-0905-A --short-name 示例任务 \\
        --branch demo-slug --worktree "☑（demo-wt，新 worktree，收工自删）" \\
        --workspace 无 --session 新开 --line 环境总线 \\
        --input-pointer "1-转型规划/0-全景路线图/示例派单件.md" --task-class A \\
        --do "第一步" --do "第二步" --dont "不做的事"

任一必填字段缺失／不合骨架硬规则 ⇒ 抛错退出（退出码 1），不打印半成品。
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import string
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
#: 骨架正本（唯一可照抄物，2026-09-04 由模板库 §〇.00 拆出独立成件）。
SKELETON_FILE = REPO_ROOT / "1-转型规划" / "0-全景路线图" / "opener骨架.md"
#: `check_block` 判据实现的物理落点（复用，不第二次实现）。
LINT_SCRIPT = REPO_ROOT / "0-学习与工具" / "工具-opener块lint.py"

#: 子任务例外句——那一行的一部分，不得删、不得简写（骨架「三处最常丢的结构」表）。
SUBTASK_EXCEPTION = (
    "🔴 例外：你若是被 Task/Agent 起的子任务，跳过本行不要执行——子任务没有自己的 session，"
    '"self" 会解析到父 session、把调度你的那条会话改名（2026-08-28 实撞）。'
)

#: 「环境×变体」→ 该组合的成品**真的会拼进去**的可选正文参数（队列 §一 `#487` 子项／
#: `OP-0906-M`，Shao Peishen 2026-09-06 裁 (c) 甲＋精简版乙）。不在名单里的参数一旦
#: 传入即 **fail-loud 报错退出**，不静默丢弃。
#:
#: 🔴 **为什么是白名单而不是黑名单**：黑名单要求「每加一个变体就记得去登记它不支持什么」，
#: 忘了登记 ⇒ 回到静默丢弃（fail-open，看不见）。白名单忘了登记 ⇒ 该组合所有可选正文参数
#: 一律被拒（fail-closed，噪音大但当场看得见），下一个人两分钟就能补上。
#: **判据：一个参数被接受却不生效，比它被拒绝更危险。**
#:
#: 🔴 **本表登记的是「拼装函数的事实」，不是「骨架应该长什么样」**——改了
#: `generate_opener` 的任一 `body_lines` 分支，必须同步改这里，否则表本身就成了第二份
#: 会漂移的判据。当前事实（2026-09-06 逐行核过 `generate_opener`，含本批方案甲改动）：
#:   - CC/standard、CC/subtask_lane：拼 do_block ＋ dont_block ⇒ 两个都支持；
#:   - Cowork/standard：方案甲 2026-09-06 补段后同样拼 do_block ＋ dont_block ⇒ 两个都支持
#:     （🔴 **此前只拼 do_block，是本行实撞的那个洞；甲已让 `--dont` 生效，故本守卫
#:     对 Cowork 自动失效——不要再在这里拦 Cowork，会与甲互相打架**）；
#:   - CC/guardian：§三bis 看护者开场词固定四行 ＋ P4 口径，**do/dont 都不拼**，且不该补段
#:     （看护者的任务正本在看护件全文里）⇒ 唯一仍需 fail-loud 的组合。
BODY_PARAM_SUPPORT = {
    ("CC", "standard"): {"do_items", "dont_items"},
    ("CC", "subtask_lane"): {"do_items", "dont_items"},
    ("CC", "guardian"): set(),
    ("Cowork", "standard"): {"do_items", "dont_items"},
}

#: 参数名 → CLI 旗标，用于报错信息里直接点名调用方敲的那个旗标。
_BODY_PARAM_FLAG = {"do_items": "--do", "dont_items": "--dont"}

#: 各组合被拒时给的**替代承接建议**——只报错不给出路会让调用方改去写更糟的形态
#: （把硬约束塞进 `--do` 的某一条尾巴，读者当成待办而不是禁令）。
_BODY_PARAM_ALTERNATIVE = {
    ("CC", "guardian"): (
        "§三bis 看护者开场词是固定形态（四行 ＋ P4 扇出口径），正文不拼 `做什么／不做什么` "
        "——看护者的任务正本在**看护件全文**里，`--input-pointer` 已指向它。"
        "要给看护者加约束请改看护件，不要走本工具的正文参数。"
    ),
}

VALID_ENVS = ("CC", "Cowork")
VALID_TASK_CLASSES = ("A", "B")
#: 三种骨架变体（模块文档「variant」节）；`subtask_lane`／`guardian` 只对 CC 有意义。
VALID_VARIANTS = ("standard", "subtask_lane", "guardian")

#: 队列 #461 明文列出的十个必填字段；任一缺失即报错退出、不出件。
REQUIRED_FIELDS = (
    "op_id", "env", "short_name", "branch", "worktree", "workspace",
    "session", "line", "input_pointer", "task_class",
)

OP_ID_RE = re.compile(r"^OP-\d{4}-[A-Za-z0-9]+$")
#: worktree 字段必须以勾选符号开头，不是裸名字（骨架「三处最常丢的结构」表第一条）。
CHECKBOX_RE = re.compile(r"^[☑☐]")
#: CC 侧分支短横线名（骨架 `<短横线名>` 占位符的字面约束）。
BRANCH_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
#: 路径纪律：仓库根相对路径，不接受本机绝对路径（根 CLAUDE.md §5「路径写仓库根相对路径」）。
WINDOWS_ABS_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")

# ── P7① 撞号查重（模块文档同节）────────────────────────────────────────────
#: 全称形态：`OP-0905-A`。捕获 `(mmdd, suffix)`。
USED_ID_FULL_RE = re.compile(r"OP-(\d{4})-([A-Za-z0-9]+)")
#: 短形形态：只认 `[Win]MMDDX-` 这个锚点（骨架「短形 MMDDX 只用于 session 名」），
#: 不做全文裸子串扫描——避免把正文里纯数字巧合误判为已用编号。
USED_ID_SHORT_RE = re.compile(r"\[Win\](\d{4})([A-Za-z0-9]+)-")

#: P4 默认口径（构建环境瘦身第三轮方案 P4；队列 §一 `#487`）——生成子任务泳道／
#: 看护者开场词时无条件写入，不由调用方每次手打、防止漏写。
SUBTASK_PARALLEL_NOTE = "🔴 并行上限 4，超出排下一波，错峰 ≥90 秒（构建环境瘦身第三轮方案 P4）。"
SUBTASK_PUSH_NOTE = (
    "🔴 收工只 push 本泳道分支，不碰主仓、不 ff master——主仓 ff 由 sweep 收尾段"
    "或看护者收工时串行做（构建环境瘦身第三轮方案 P4）。"
)
GUARDIAN_PARALLEL_NOTE = (
    "🔴 用 Task/Agent 起子任务时并行上限 4，超出排下一波，错峰 ≥90 秒；"
    "各子任务收工只 push 自己分支，不碰主仓、不 ff master（构建环境瘦身第三轮方案 P4）。"
)


def _scan_used_suffixes(mmdd: str) -> set[str]:
    """扫 `1-转型规划/` 全树 `.md`，收集当日（`mmdd`）已出现过的编号后缀（大写）。

    🔴 读 `REPO_ROOT` 走模块全局、不做默认参数——测试靠 monkeypatch
    `模块.REPO_ROOT` 指向临时夹具目录（同 `test_工具-泳道看护状态机.py`
    既定手法），默认参数会在定义时就把旧值绑死，测试改不动它。
    """
    used: set[str] = set()
    search_root = REPO_ROOT / "1-转型规划"
    if not search_root.is_dir():
        return used
    for path in search_root.rglob("*.md"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in USED_ID_FULL_RE.finditer(text):
            if m.group(1) == mmdd:
                used.add(m.group(2).upper())
        for m in USED_ID_SHORT_RE.finditer(text):
            if m.group(1) == mmdd:
                used.add(m.group(2).upper())
    return used


def _next_free_suffix(used: set[str]) -> str:
    """按字母表找下一个当日未用的单字母后缀；26 个用尽再兜底双字母（本项目至今
    未出现过单日超 26 个任务的极端情形，双字母只是不留死角，不特别优化）。"""
    for ch in string.ascii_uppercase:
        if ch not in used:
            return ch
    for c1 in string.ascii_uppercase:
        for c2 in string.ascii_uppercase:
            cand = c1 + c2
            if cand not in used:
                return cand
    raise OpenerGenError("当日编号后缀已耗尽（含双字母兜底），需人工介入")


def _check_op_id_not_reused(spec: "OpenerSpec") -> None:
    mmdd, suffix = _mmdd_and_suffix(spec.op_id)
    used = _scan_used_suffixes(mmdd)
    if suffix.upper() in used:
        next_free = _next_free_suffix(used)
        raise OpenerGenError(
            f"编号 {spec.op_id} 当日（{mmdd}）已被使用（撞号，队列 #461／#487 P7① 查重，"
            f"命中全称或 `[Win]{mmdd}{suffix}-` 短形）；下一个空号：OP-{mmdd}-{next_free}"
        )


class OpenerGenError(ValueError):
    """字段缺失或不合骨架硬规则 ⇒ 报错退出、不出件（队列 #461 明文要求）。"""


def _load_lint_module():
    """复用 `工具-opener块lint.py` 的 `check_block`／`iter_fenced_blocks`，不写第二份判据。"""
    spec = importlib.util.spec_from_file_location("_zp_opener_lint_reuse", LINT_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 opener 块判据实现：{LINT_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mmdd_and_suffix(op_id: str) -> tuple[str, str]:
    """`OP-0904-M` → `("0904", "M")`。"""
    _, mmdd, suffix = op_id.split("-", 2)
    return mmdd, suffix


#: 十项必填字段 ＋ 五项可选补充字段——`OpenerSpec.__init__` 的关键字参数名单一可信源。
_OPENER_SPEC_FIELDS = REQUIRED_FIELDS + (
    "claude_section", "do_items", "dont_items", "title_call_override", "variant",
)


class OpenerSpec:
    """字段容器（**不用 `@dataclass`**：本模块经 `importlib.util.module_from_spec` 跨文件
    加载时不会注册进 `sys.modules`，而 Python 3.14 的 dataclass 处理需要
    `sys.modules[cls.__module__]` 可解析——两者组合会在 import 时直接抛
    `AttributeError`，手写 `__init__` 绕开这条依赖，不是风格选择）。
    """

    __slots__ = _OPENER_SPEC_FIELDS

    def __init__(
        self, *, op_id: str, env: str, short_name: str, branch: str, worktree: str,
        workspace: str, session: str, line: str, input_pointer: str, task_class: str,
        claude_section: str = "", do_items: list[str] | None = None,
        dont_items: list[str] | None = None, title_call_override: str | None = None,
        variant: str = "standard",
    ) -> None:
        self.op_id, self.env, self.short_name = op_id, env, short_name
        self.branch, self.worktree, self.workspace = branch, worktree, workspace
        self.session, self.line, self.input_pointer, self.task_class = (
            session, line, input_pointer, task_class)
        self.claude_section = claude_section
        self.do_items = list(do_items) if do_items else ["…"]
        self.dont_items = list(dont_items) if dont_items else ["…"]
        self.title_call_override = title_call_override
        self.variant = variant


def _require_all_fields(values: dict) -> None:
    missing = [f for f in REQUIRED_FIELDS if not str(values.get(f, "")).strip()]
    if missing:
        raise OpenerGenError(
            f"缺失必填字段：{'、'.join(missing)}"
            "（编号／执行环境／短名／分支／worktree情形／工作区情形／session／派出线／"
            "输入指针／A或B类，十项任一不能省，队列 #461 明文要求）"
        )


def _validate_spec(spec: OpenerSpec) -> None:
    if spec.env not in VALID_ENVS:
        raise OpenerGenError(f"执行环境须为 CC 或 Cowork，收到：{spec.env!r}")
    if spec.variant not in VALID_VARIANTS:
        raise OpenerGenError(f"variant 须为 {VALID_VARIANTS} 之一，收到：{spec.variant!r}")
    if spec.variant != "standard" and spec.env != "CC":
        raise OpenerGenError(
            f"variant={spec.variant!r} 只对 CC 有意义（骨架【CC · 子任务泳道】／§三bis "
            f"均无 Cowork 对应形态），收到 env={spec.env!r}"
        )
    if spec.task_class not in VALID_TASK_CLASSES:
        raise OpenerGenError(f"A或B类须为 'A' 或 'B'，收到：{spec.task_class!r}")
    if not OP_ID_RE.match(spec.op_id):
        raise OpenerGenError(f"编号须匹配全称 `OP-MMDD-X` 形式（如 OP-0905-A），收到：{spec.op_id!r}")
    label_len = len(spec.short_name) + (2 if spec.variant == "guardian" else 0)
    if label_len > 12:
        raise OpenerGenError(
            f"短名须 ≤12 字（guardian 变体首行拼「看护」+短名，须一并 ≤12），"
            f"收到 {label_len} 字：{spec.short_name!r}"
        )
    if not CHECKBOX_RE.match(spec.worktree):
        raise OpenerGenError(
            "worktree 字段须以勾选符号 ☑／☐ 开头，不是裸名字"
            f"（骨架「三处最常丢的结构」表第一条），收到：{spec.worktree!r}"
        )
    if spec.session != "新开":
        raise OpenerGenError(
            f"session 字段骨架固定字面为「新开」（骨架未定义其他取值），收到：{spec.session!r}"
        )
    if spec.env == "Cowork" and spec.branch != "master":
        raise OpenerGenError(f"Cowork 侧分支固定为 master（骨架【Cowork】骨架），收到：{spec.branch!r}")
    if spec.env == "CC" and spec.variant != "guardian" and not BRANCH_SLUG_RE.match(spec.branch):
        # guardian 的分支字段是骨架 §三bis 固定字面量「master（看护者本身不建分支，
        # 不改代码）」，不是短横线 slug——调用方须整段传入，不受本条约束。
        raise OpenerGenError(
            "CC 侧分支须传短横线 slug（骨架 `<短横线名>` 占位符，如 'opener-gen'，"
            f"小写字母数字与连字符），收到：{spec.branch!r}"
        )
    if WINDOWS_ABS_PATH_RE.match(spec.input_pointer):
        raise OpenerGenError(
            "输入指针须写仓库根相对路径，不接受本机绝对路径"
            f"（根 CLAUDE.md §5「路径写仓库根相对路径」），收到：{spec.input_pointer!r}"
        )


def _reject_silently_dropped_body_params(kwargs: dict, spec: OpenerSpec) -> None:
    """调用方传了「这个环境×变体根本不会拼进成品」的正文参数 ⇒ 报错退出（fail-loud）。

    🔴 **本函数解决的不是「参数写错了」，而是「参数写对了却没生效」**：
    2026-09-06 实撞——`--env Cowork --dont "<三条硬约束>"` 被静默丢弃，不报错、
    不出现在成品里，起草者以为约束传达到了（当次靠那三条本来也写在接力卡里侥幸兜住，
    属侥幸不属机制）。同族＝`acquire --domain` 漏传是「静默少算」而不是被拦下。

    🔴 **Cowork 已由方案甲让 `--dont` 真的生效，不由本函数拦**（两者同落会互相打架）；
    本函数落地后只剩 `--variant guardian` 一个洞在守——那个洞补段补不掉。

    🔴 **判「传没传」只看 `kwargs`，不看 `spec`**：`OpenerSpec.__init__` 会把
    `do_items`／`dont_items` 的 `None` 兜成 `["…"]` 占位，读 `spec` 分不出
    「没传」与「传了空」——判据必须站在兜底之前。
    """
    supported = BODY_PARAM_SUPPORT.get((spec.env, spec.variant))
    if supported is None:
        # 白名单没登记这个组合 ⇒ fail-closed（宁可全拒也不静默丢），见常量表注释。
        supported = set()
    passed = {k for k in _BODY_PARAM_FLAG if kwargs.get(k)}
    dropped = sorted(passed - supported, key=lambda k: _BODY_PARAM_FLAG[k])
    if not dropped:
        return
    flags = "、".join(f"`{_BODY_PARAM_FLAG[k]}`" for k in dropped)
    alt = _BODY_PARAM_ALTERNATIVE.get(
        (spec.env, spec.variant),
        "该组合的成品形态不含这些段，请改用 `--input-pointer` 指向的派单件承接。",
    )
    raise OpenerGenError(
        f"{flags} 传入了内容，但 env={spec.env}／variant={spec.variant} 的成品**不会包含**"
        f"它们——若不报错就会被静默丢弃（参数被接受却不生效，比被拒绝更危险；"
        f"2026-09-06 实撞一次，队列 §一 `#487` 子项／`OP-0906-M`）。{alt}"
    )


def _title_call_line(op_id: str, short_name: str) -> str:
    mmdd, suffix = _mmdd_and_suffix(op_id)
    return (
        f'开工第一件事：调 mcp__ccd_session_mgmt__set_session_title（session_id 传字面量 "self"），'
        f"标题：[Win]{mmdd}{suffix}-{short_name}。{SUBTASK_EXCEPTION}"
    )


def _title_call_line_guardian(op_id: str, short_name: str) -> str:
    """骨架 §三bis 看护者开场词的 `set_session_title` 行——它是本批唯一真正被
    粘贴进独立 CC 会话的一份，仍需要标题；措辞与标准句不同（强调"你自己不属于
    子任务跳过例外"），故不复用 `_title_call_line`。"""
    mmdd, suffix = _mmdd_and_suffix(op_id)
    return (
        f'开工第一件事：调 mcp__ccd_session_mgmt__set_session_title（session_id 传字面量 "self"），'
        f"标题：[Win]{mmdd}{suffix}-看护{short_name}。🔴 你是本批唯一真正被粘贴进独立 CC 会话的一份"
        "（其余泳道均由你用 Task/Agent 派发，正文里已不再放这一行——2026-09-05 队列 §一 `#487`／(甲)："
        "源头不放，不再指望子任务的文本例外句被真正遵守），本条对你适用，正常执行即可，"
        "标题设定后不要再被子任务顶掉，你自己不属于「跳过本行」的例外范围。"
    )


def _settings_line(spec: OpenerSpec) -> str:
    if spec.env == "CC":
        if spec.variant == "guardian":
            # 骨架 §三bis 固定字面量：看护者本身不建分支、不改代码——调用方
            # 须整段传入 `branch`（如 "master（看护者本身不建分支，不改代码）"），
            # 不套用标准变体「从 master 起 claude/opMMDDx-<slug>」的拼装模板。
            branch_field = spec.branch
        else:
            mmdd, suffix = _mmdd_and_suffix(spec.op_id)
            branch_field = f"master（从 master 起 `claude/op{mmdd}{suffix.lower()}-{spec.branch}`）"
    else:
        branch_field = "master"
    return (
        f"【设置】执行环境：{spec.env} ｜ 分支：{branch_field} ｜ worktree：{spec.worktree} ｜ "
        f"工作区：{spec.workspace} ｜ session：{spec.session} ｜ 派出线：{spec.line}"
    )


def _read_line(spec: OpenerSpec) -> str:
    section = f" §{spec.claude_section}" if spec.claude_section else ""
    if spec.env == "CC":
        clause = (
            "A 类（口径已定、判据已写死），无需再问澄清，直接开工"
            if spec.task_class == "A" else "B 类，开工前问我 2-3 个澄清"
        )
        return (
            f"读 ① `{spec.input_pointer}` → ② `CLAUDE.md`{section} 恢复上下文，"
            f"按下述执行。本件为 {clause}。"
        )
    return (
        f"读 ① `{spec.input_pointer}` → ② `CLAUDE.md`{section} 恢复上下文，"
        f"按下述执行。本件为 {spec.task_class} 类。"
    )


def generate_opener(**kwargs) -> str:
    """按十项必填字段拼出成品 opener 文本；缺字段或违反骨架硬规则 ⇒ 抛 `OpenerGenError`。"""
    _require_all_fields(kwargs)
    known = set(_OPENER_SPEC_FIELDS)
    spec = OpenerSpec(**{k: v for k, v in kwargs.items() if k in known})
    _validate_spec(spec)
    # 🔴 顺序刻意：先 `_validate_spec` 定下合法的 env／variant，本条判据才有意义；
    # 放在 `_check_op_id_not_reused` 之前——撞号查重要扫全树 `.md`（秒级），
    # 而「参数会被丢掉」是纯本地判断，没理由让调用方先等一次全树扫描才被告知。
    _reject_silently_dropped_body_params(kwargs, spec)
    _check_op_id_not_reused(spec)  # P7①：当日撞号即拒，见模块文档

    do_block = "\n".join(f"{i + 1}. {item}" for i, item in enumerate(spec.do_items))
    dont_block = "\n".join(f"- {item}" for item in spec.dont_items)

    if spec.variant == "guardian":
        title_line = f"[{spec.op_id}]【{spec.env}】看护{spec.short_name}"
        title_call = spec.title_call_override if spec.title_call_override is not None \
            else _title_call_line_guardian(spec.op_id, spec.short_name)
        body_lines = [
            title_line,
            _settings_line(spec),
            title_call,
            f"读 `{spec.input_pointer}` 全文＋ `CLAUDE.md` 恢复上下文。",
            "",
            "你是本批的**看护者**，不是执行者。用 Task/Agent 工具为各条泳道各起一个子任务，"
            '`isolation: "worktree"`，把对应【CC · 子任务泳道】opener 的正文原样作为子任务 prompt。'
            "🔴 不要改写 opener 正文。",
            "",
            GUARDIAN_PARALLEL_NOTE,
        ]
    else:
        title_line = f"[{spec.op_id}]【{spec.env}】{spec.short_name}"
        if spec.env == "CC" and spec.variant == "standard":
            title_call = spec.title_call_override if spec.title_call_override is not None \
                else _title_call_line(spec.op_id, spec.short_name)
            body_lines = [
                title_line,
                _settings_line(spec),
                title_call,
                _read_line(spec),
                "",
                "做什么：",
                do_block,
                "",
                "不做什么：",
                dont_block,
            ]
        elif spec.env == "CC" and spec.variant == "subtask_lane":
            # 骨架【CC · 子任务泳道】变体：不放 set_session_title 行（源头不放，
            # 见模块文档「variant」节），收尾无条件追加 P4 两条默认口径。
            body_lines = [
                title_line,
                _settings_line(spec),
                _read_line(spec),
                "",
                "做什么：",
                do_block,
                "",
                "不做什么：",
                dont_block,
                SUBTASK_PARALLEL_NOTE,
                SUBTASK_PUSH_NOTE,
            ]
        else:
            body_lines = [
                title_line,
                _settings_line(spec),
                _read_line(spec),
                "",
                "做什么：",
                do_block,
                "",
                # 🔴 2026-09-06 补（队列 §一 `#487` 子项／`OP-0906-I`）：此前 Cowork 分支
                # 不拼「不做什么」段，`--dont` 传进来被**静默丢弃**——不报错、不出现在
                # 成品里，起草者以为约束传达到了（2026-09-06 实撞一次）。骨架
                # 【Cowork】节已同步补段，`工具-opener块lint.py` 形态⑦机器守。
                "不做什么：",
                dont_block,
                "",
                "收工：产出登记 §二 待 commit 批次（走 `0-学习与工具/工具-共享文档编辑锁.py`，"
                "勿裸改、勿自行 commit），由落库 sweep 取活。",
            ]

    opener_block = "```\n" + "\n".join(body_lines) + "\n```"

    # 自校验：复用既有 `check_block` 判据，产出必须自己先过自己定的门（模板库 §〇.0 同款约束）。
    # `is_subtask_lane`：subtask_lane 变体天生不含 set_session_title，须告知 lint
    # 这是形态⑥要求的那类块，否则会被形态①误判为"CC opener 缺 set_session_title"。
    lint = _load_lint_module()
    blocks = lint.iter_fenced_blocks(opener_block)
    if not blocks:
        raise OpenerGenError("生成物未能被识别为围栏代码块（内部拼装错误）")
    problems = lint.check_block(blocks[0], is_subtask_lane=(spec.variant == "subtask_lane"))
    if problems:
        detail = "；".join(f"[{code}] {msg}" for code, msg in problems)
        raise OpenerGenError(f"生成物未通过 `工具-opener块lint.py::check_block` 自检：{detail}")

    return opener_block


def _build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="opener 生成器（队列 #461）：按 opener骨架.md 唯一格式来源拼出成品 opener。"
    )
    ap.add_argument("--op-id", required=True, help="全称编号，如 OP-0905-A")
    ap.add_argument("--env", required=True, choices=VALID_ENVS, help="执行环境")
    ap.add_argument("--short-name", required=True, help="短名，≤12 字")
    ap.add_argument("--branch", required=True,
                    help="CC：短横线 slug（如 opener-gen）；Cowork：固定传 master")
    ap.add_argument("--worktree", required=True, help="worktree 情形，须以 ☑／☐ 开头")
    ap.add_argument("--workspace", required=True, help="工作区情形（§〇.1 四种填法之一或「无」）")
    ap.add_argument("--session", required=True, help="骨架固定为「新开」")
    ap.add_argument("--line", required=True, help="派出线名")
    ap.add_argument("--input-pointer", required=True, help="首要输入的仓库根相对路径")
    ap.add_argument("--task-class", required=True, choices=VALID_TASK_CLASSES, help="A 或 B 类")
    ap.add_argument("--claude-section", default="", help="CLAUDE.md 相关节号（可选）")
    ap.add_argument("--do", dest="do_items", action="append", default=None, help="做什么条目，可重复")
    ap.add_argument("--dont", dest="dont_items", action="append", default=None, help="不做什么条目，可重复")
    ap.add_argument("--variant", default="standard", choices=VALID_VARIANTS,
                    help="骨架变体：standard（默认）／subtask_lane（子任务泳道）／guardian（§三bis 看护者开场词）")
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = _build_arg_parser()
    args = ap.parse_args(argv)
    kwargs = {
        "op_id": args.op_id, "env": args.env, "short_name": args.short_name,
        "branch": args.branch, "worktree": args.worktree, "workspace": args.workspace,
        "session": args.session, "line": args.line, "input_pointer": args.input_pointer,
        "task_class": args.task_class, "claude_section": args.claude_section,
        "variant": args.variant,
    }
    if args.do_items:
        kwargs["do_items"] = args.do_items
    if args.dont_items:
        kwargs["dont_items"] = args.dont_items
    try:
        print(generate_opener(**kwargs))
    except OpenerGenError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
