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

VALID_ENVS = ("CC", "Cowork")
VALID_TASK_CLASSES = ("A", "B")

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


#: 十项必填字段 ＋ 四项可选补充字段——`OpenerSpec.__init__` 的关键字参数名单一可信源。
_OPENER_SPEC_FIELDS = REQUIRED_FIELDS + ("claude_section", "do_items", "dont_items", "title_call_override")


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
    ) -> None:
        self.op_id, self.env, self.short_name = op_id, env, short_name
        self.branch, self.worktree, self.workspace = branch, worktree, workspace
        self.session, self.line, self.input_pointer, self.task_class = (
            session, line, input_pointer, task_class)
        self.claude_section = claude_section
        self.do_items = list(do_items) if do_items else ["…"]
        self.dont_items = list(dont_items) if dont_items else ["…"]
        self.title_call_override = title_call_override


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
    if spec.task_class not in VALID_TASK_CLASSES:
        raise OpenerGenError(f"A或B类须为 'A' 或 'B'，收到：{spec.task_class!r}")
    if not OP_ID_RE.match(spec.op_id):
        raise OpenerGenError(f"编号须匹配全称 `OP-MMDD-X` 形式（如 OP-0905-A），收到：{spec.op_id!r}")
    if len(spec.short_name) > 12:
        raise OpenerGenError(f"短名须 ≤12 字，收到 {len(spec.short_name)} 字：{spec.short_name!r}")
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
    if spec.env == "CC" and not BRANCH_SLUG_RE.match(spec.branch):
        raise OpenerGenError(
            "CC 侧分支须传短横线 slug（骨架 `<短横线名>` 占位符，如 'opener-gen'，"
            f"小写字母数字与连字符），收到：{spec.branch!r}"
        )
    if WINDOWS_ABS_PATH_RE.match(spec.input_pointer):
        raise OpenerGenError(
            "输入指针须写仓库根相对路径，不接受本机绝对路径"
            f"（根 CLAUDE.md §5「路径写仓库根相对路径」），收到：{spec.input_pointer!r}"
        )


def _title_call_line(op_id: str, short_name: str) -> str:
    mmdd, suffix = _mmdd_and_suffix(op_id)
    return (
        f'开工第一件事：调 mcp__ccd_session_mgmt__set_session_title（session_id 传字面量 "self"），'
        f"标题：[Win]{mmdd}{suffix}-{short_name}。{SUBTASK_EXCEPTION}"
    )


def _settings_line(spec: OpenerSpec) -> str:
    if spec.env == "CC":
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

    title_line = f"[{spec.op_id}]【{spec.env}】{spec.short_name}"
    do_block = "\n".join(f"{i + 1}. {item}" for i, item in enumerate(spec.do_items))
    dont_block = "\n".join(f"- {item}" for item in spec.dont_items)
    title_call = spec.title_call_override if spec.title_call_override is not None \
        else _title_call_line(spec.op_id, spec.short_name)

    if spec.env == "CC":
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
    else:
        body_lines = [
            title_line,
            _settings_line(spec),
            _read_line(spec),
            "",
            "做什么：",
            do_block,
            "",
            "收工：产出登记 §二 待 commit 批次（走 `0-学习与工具/工具-共享文档编辑锁.py`，"
            "勿裸改、勿自行 commit），由落库 sweep 取活。",
        ]

    opener_block = "```\n" + "\n".join(body_lines) + "\n```"

    # 自校验：复用既有 `check_block` 判据，产出必须自己先过自己定的门（模板库 §〇.0 同款约束）。
    lint = _load_lint_module()
    blocks = lint.iter_fenced_blocks(opener_block)
    if not blocks:
        raise OpenerGenError("生成物未能被识别为围栏代码块（内部拼装错误）")
    problems = lint.check_block(blocks[0])
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
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = _build_arg_parser()
    args = ap.parse_args(argv)
    kwargs = {
        "op_id": args.op_id, "env": args.env, "short_name": args.short_name,
        "branch": args.branch, "worktree": args.worktree, "workspace": args.workspace,
        "session": args.session, "line": args.line, "input_pointer": args.input_pointer,
        "task_class": args.task_class, "claude_section": args.claude_section,
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
