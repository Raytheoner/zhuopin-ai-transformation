"""跨桌任务队列.md 结构 lint（队列 #309 步骤 2③，CI 基线）。

复用 `工具-共享文档编辑锁.py` release 校验①⑤两项检查用到的底层解析
函数（`_split_live_sections`/`_table_data_rows`/`SECTION_COLUMN_COUNTS`/
`_section_two_status_is_ambiguous`）——同一份文件、同一套表格约定，不该
两处各写一套判据（同 `_table_data_rows` 自身 docstring 的既有原则）。
用 `importlib.util.spec_from_file_location` 按文件路径加载（本项目测试
文件已有的既定手法，如 `test_工具-落库sweep.py`），不走 `import 工具-...`
的包名解析——两者都不是 `pip install -e` 的可安装包，不存在多 worktree
共享 editable install 的静默劫持风险（那类风险专指 `zhuopin_platform`/
`aibot_service` 这类被装进全局 site-packages 的包，见 `工具-落库sweep.py`
文件头部"零依赖"说明）。

作用域与 release 校验的关系（互补，非重复）：release 校验只查"本次持锁
期间新增/改动的行"（session-diff-scoped，依赖 acquire 时的快照与预留
记录）；本脚本查"当前文件整体"（whole-file-scoped，无会话上下文）——
CI 治的是"不管改动经没经过编辑锁协议（如 #305 指出的机器人写队列路径
完全绕过锁），产物本身是否结构完整"，与 release 校验治的"写入那一刻
拦一次"是两个不同的防线，见队列 #309 行内 CI 步骤 2③ 说明原文
「编辑锁的 release 校验只在有人走锁时才生效…CI 不论谁写、走哪条路都拦」。

只做队列 #309 行内文字明确点名的两项：①列数（§一＝8／§二＝4／§四＝4，
天然覆盖裸竖线致列偏移的情形——`_table_data_rows` 按原样 split("|")，
不做任何"容错"，裸竖线会直接体现为列数偏差）；②§二 状态列格式（既不
含"待"也不含"✅"判为模糊）。不做 release 校验独有的另外四项（②批次
文件清单自声明／③编号预留归属／④P0-P1 未核断言／⑥跟进信暂缓一致性）
——这四项依赖 acquire 时的快照与本次持锁期间的预留记录，CI 没有这个
会话上下文，硬套会产生大量"整份历史文件都是新改动"式的假阳性，且不在
#309 行内 lint 范围文字里，不属于本次要补的那一块。

第③项（队列 #313，拍板项 10 选 (b)）：断言权威模块
`zhuopin_platform.shared_tools.queue_table` 可 import。背景——编辑锁/
台账/sweep/队列查询四处消费者各自都用
`try: from zhuopin_platform.shared_tools.queue_table import ... except
ImportError: class queue_table: ...` 兜底桩隔离测试环境（#306 apply 时
两个真实隔离测试用例逼出，桩本身不主张删），但这意味着"哪天路径变了或
包装坏了，四处会各自静默降级回本地实现、零报错"——本项断言只求把这条
本会静默的路径变成 CI 会显式报红的路径，不改桩本身。**故意不用
`pip install -e`**：`queue_table.py` 自身与其所在的 `zhuopin_platform`/
`shared_tools` 两层 `__init__.py` 均无第三方依赖（纯标准库），走与场景
入口脚本同款的 #300 式 sys.path 引导即可稳定 import，不必为一个零依赖
模块在 CI 里多装一次平台底座包（`queue-structure-lint` job 目前不装）。

用法：
  python 0-学习与工具/工具-队列结构lint.py
  # 退出码 0=通过；1=发现违规（详情打印到 stdout）
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

QUEUE_REL = "1-转型规划/0-全景路线图/跨桌任务队列.md"
EDIT_LOCK_SCRIPT = Path(__file__).resolve().with_name("工具-共享文档编辑锁.py")

_spec = importlib.util.spec_from_file_location("queue_lint_editlock_reuse", EDIT_LOCK_SCRIPT)
editlock = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(editlock)

# 队列 #315（apply）：拆分后 QUEUE_REL 转为纯指针文件，不再是权威内容
# 承载——lint 改遍历两份真实内容文件，否则本 CI 门禁会对着一份几乎空的
# 指针文件永远报"零违规"，把"未来新行必须带机器字段"这道硬门禁静默
# 失效（同 CLAUDE.md §5"工具静默回退"反模式）。两个具体路径读 `editlock`
# 已加载的局部绑定（同一惯例，供测试 monkeypatch）。
QUEUE_PATHS_REL = [editlock.QUEUE_MECHANISM_PATH_REL, editlock.QUEUE_BUSINESS_PATH_REL]

# 队列 #314①：REPO_ROOT 复用 editlock 已算好的值（`_resolve_repo_root()`，
# 经 `git rev-parse --git-common-dir` 解到"所有 worktree 共享的主工作区"），
# 不再自己按 `Path(__file__).resolve().parents[1]` 算一份worktree本地路径。
# 2026-08-09 实测坐实两者会给出不同答案：本脚本在建造用的 linked worktree
# 里跑时，旧写法算出的是"这个 worktree 自己签出的那份队列文件"（可能是
# 创建 worktree 那一刻的旧快照，此后主工作区经 editlock 协议〇.7 发生的
# 任何编辑都不会体现在这份本地副本里）；而 `工具-共享文档编辑锁.py`／
# `工具-队列查询.py` 的 `_resolve_repo_root()` 一律解到主工作区（其
# docstring 明文"所有 git worktree 共享同一把锁的关键"）——队列文件的
# 权威副本只有主工作区那一份。两者不一致意味着：在 linked worktree 里
# 直接跑 `python 工具-队列结构lint.py`（本脚本 docstring 给出的原样用法）
# 校验的是错误的文件，可能得出与 editlock release 校验完全相反的结论，
# 且不报错——同 `CLAUDE.md` §5"工具静默回退"的教科书形态。
REPO_ROOT = editlock.REPO_ROOT


# ---------------------------------------------------------------------------
# 队列 #366 / S2：队列禁止复述信状态（一期 --warn）
# ---------------------------------------------------------------------------
#
# S1（Shao Peishen 2026-08-21 答 §四 #85 选 (b)）确立：**一封信的状态，唯一
# 权威源是跟进信 README 的「发送状态」列，跨桌任务队列不是信状态的载体。**
# 队列行里写「等某某#N 闭环／待某某回件」这类**复述**，一律是会过时的快照
# ——2026-08-21 当天两次咬人（质量部#8 回灌全做完闸还锁着；采购部#17 回件
# 13:13 到、13:15 队列已追行而 README 未动）都始于有人照着这类快照下判断。
#
# 判据只认「**等/待 + 部门#N + 闭环/回件/回灌**」这个紧凑形态，前后各留
# ≤8 字的窗口。窗口是**实测标定**的，不是拍的：0 字窗口漏掉全部 5 处存量，
# 40 字窗口把 18 处正常叙述（如「#344 判例包已作为 采购部#16 发出、现等
# 回件」这类**事后陈述**）一并卷进来。8/8 恰好命中且仅命中那 5 处。
_LETTER_STATUS_RESTATE_RE = re.compile(
    r"(等|待).{0,8}?(采购部|财务部|质量部|IT部|销售部)#\d+.{0,8}?(闭环|回件|回灌)"
)
# §二 是 commit 批次行，天然是历史记录；§一 里 `[S:done]` 的行同理（「历史
# 记录不追改」是本项目硬规则）。两者都**只统计、不报违规**——但必须把数
# 打印出来，否则就成了"静默豁免"，与本判据要治的毛病同族。
FOLLOWUP_RESTATE_SCOPE_SECTIONS = ("一", "四")
FOLLOWUP_RESTATE_HINT = (
    "队列不得复述信状态（它会过时）。改为写指针："
    "「串行闸状态跑 python 0-学习与工具/工具-跟进闸查询.py --to <收信人>」"
)


def _followup_restate_scan(text: str) -> tuple[list[str], int]:
    """返回 (活行违规说明列表, 历史行命中数)。

    活行 ＝ §一 非 `[S:done]` 的行 ＋ §四 全部行；历史行 ＝ §一 `[S:done]`
    的行（§二 不在扫描范围内，见上方常量注释）。
    """
    sections = editlock._split_live_sections(text)
    live: list[str] = []
    historical = 0
    for label in FOLLOWUP_RESTATE_SCOPE_SECTIONS:
        for line, cells in editlock._table_data_rows(sections.get(label, "")):
            match = _LETTER_STATUS_RESTATE_RE.search(line)
            if not match:
                continue
            if label == "一" and len(cells) > 5:
                status_value, _, _ = editlock._parse_status_domain_fields(cells[5])
                if status_value == "done":
                    historical += 1
                    continue
            row_id = cells[0] if cells else "?"
            live.append(
                f"§{label} #{row_id} 复述了信状态「{match.group(0)}」——{FOLLOWUP_RESTATE_HINT}"
            )
    return live, historical


def lint(repo_root: Path) -> list[str]:
    """队列 #315：遍历两份物理队列文件（机制环境／业务场景），每份独立跑
    同一套校验，违规说明前缀标注来源文件，避免两份文件都出问题时混在
    一起分不清是哪一份。"""
    violations: list[str] = []
    for queue_path in QUEUE_PATHS_REL:
        target = repo_root / queue_path
        if not target.exists():
            violations.append(f"[{queue_path}] 文件不存在，无法校验。")
            continue
        text = target.read_text(encoding="utf-8")
        violations.extend(
            f"[{queue_path}] {v}" for v in _lint_one_file(text)
        )
    return violations


def followup_restate_warnings(repo_root: Path) -> tuple[list[str], int]:
    """队列 #366 / S2 一期：只 warn、不计入 `lint()` 的违规、不影响退出码。

    🔴 一期刻意不硬拦，与 `claude-progress-lint` 同策略：本判据上线时存量
    非零（实测 3 处活行），一期就 `--enforce` 会立刻挡住所有人的 push，而
    「队列不得复述信状态」这条规则如果第一天就被绕过，绕过的将是 lint 本身。
    二期存量清零后另派单件切硬拦。
    """
    warnings: list[str] = []
    historical_total = 0
    for queue_path in QUEUE_PATHS_REL:
        target = repo_root / queue_path
        if not target.exists():
            continue
        live, historical = _followup_restate_scan(target.read_text(encoding="utf-8"))
        warnings.extend(f"[{queue_path}] {w}" for w in live)
        historical_total += historical
    return warnings, historical_total


def _lint_one_file(text: str) -> list[str]:
    sections = editlock._split_live_sections(text)
    violations: list[str] = []
    for label, expected_cols in editlock.SECTION_COLUMN_COUNTS.items():
        section_text = sections.get(label, "")
        for line, cells in editlock._table_data_rows(section_text):
            preview = line.strip()
            if len(preview) > 80:
                preview = preview[:80] + "…"
            if len(cells) != expected_cols:
                violations.append(
                    f"§{label} 行列数为 {len(cells)}（应为 {expected_cols}，"
                    f"含反引号内裸竖线等致列偏移的情形）：{preview}"
                )
                continue
            if label == "二" and editlock._section_two_status_is_ambiguous(cells[3]):
                violations.append(
                    f"§二 行状态列开头片段既不含「待」也不含「✅」"
                    f"（会被 sweep 判为状态列模糊，见 #247）：{preview}"
                )
            if label == "一":
                # 队列 #308 决策点 1：106 行存量回填与七处消费者切换均已
                # 完成后新增的硬门禁——§一 任意数据行状态列不以 `[S:` 开头
                # 即判违规，把"未来新行必须带机器字段"从约定升级为可执行
                # 门禁。回填/消费者切换完成前不得上线（会对存量误报），
                # 现已确认全部完成（见队列 #308 行内回写）。
                status_value, _, _ = editlock._parse_status_domain_fields(cells[5])
                if status_value is None:
                    violations.append(
                        f"§一 行状态列缺少机器可读字段（须以 `[S:done/open/partial/"
                        f"hold/blocked/timed=YYYY-MM-DD]` 开头，见队列 #308）：{preview}"
                    )
    return violations


def check_queue_table_importable(repo_root: Path) -> str | None:
    """队列 #313：断言权威模块 `zhuopin_platform.shared_tools.queue_table`
    可 import。返回 None＝可 import；否则返回违规说明字符串。

    走与场景入口脚本同款的 #300 式 sys.path 引导（本函数自己插一次，
    不依赖调用方是否已引导过），不用 `pip install -e`——该模块与其两层
    `__init__.py` 均无第三方依赖，直接插路径即可稳定导入。"""
    platform_dir = repo_root / "5-平台底座" / "zhuopin_platform"
    if not platform_dir.is_dir():
        return f"未找到 {platform_dir}（仓库根标记缺失，无法校验权威模块可达性）"
    inserted = str(platform_dir) not in sys.path
    if inserted:
        sys.path.insert(0, str(platform_dir))
    try:
        import importlib

        module = importlib.import_module("zhuopin_platform.shared_tools.queue_table")
        if not hasattr(module, "SECTION_COLUMN_COUNTS"):
            return (
                "zhuopin_platform.shared_tools.queue_table 可 import，但缺少"
                "预期符号 SECTION_COLUMN_COUNTS（模块内容被改动？）"
            )
        # 队列 #366 / S4：同一条断言扩到 `followup_gate`。理由与 #313 逐字
        # 相同——`工具-共享文档编辑锁.py` 对它也有兜底（import 不到时 S4
        # 桥二整条校验跳过，只打一行 ⚠），**那条降级路径本身是静默的**，
        # 本断言存在的唯一目的就是让它红。
        gate = importlib.import_module("zhuopin_platform.shared_tools.followup_gate")
        missing = [
            name for name in ("CLOSED_STATUS_PREFIXES", "is_closed_status",
                              "find_unsynced_letters", "reply_matches_letter")
            if not hasattr(gate, name)
        ]
        if missing:
            return (
                "zhuopin_platform.shared_tools.followup_gate 可 import，但缺少"
                f"预期符号 {'、'.join(missing)}（模块内容被改动？）"
                "——编辑锁的 S4 桥二校验会因此静默跳过"
            )
        return None
    except ImportError as exc:
        return (
            f"zhuopin_platform.shared_tools.queue_table 无法 import：{exc}"
            "（四处消费者——编辑锁／台账／sweep／队列查询——的兜底桩会各自"
            "静默降级回本地实现，此断言正是为了不让那次降级零报错，见队列 #313）"
        )
    finally:
        if inserted:
            sys.path.remove(str(platform_dir))


def main() -> int:
    violations = lint(REPO_ROOT)
    import_error = check_queue_table_importable(REPO_ROOT)
    if import_error:
        violations.append(import_error)

    # 队列 #366 / S2 一期：先打印 warn 段，再打印硬判据结论——放在前面是
    # 因为退出码由硬判据决定，读者看到 `✓ 通过` 后就不会再往下看了。
    restate_warnings, restate_historical = followup_restate_warnings(REPO_ROOT)
    if restate_warnings:
        print(f"⚠ 队列复述信状态（S2 一期只告警，不计入退出码）：{len(restate_warnings)} 处活行")
        for w in restate_warnings:
            print(f"  - {w}")
    print(
        f"  二期基线：活行 {len(restate_warnings)} 处；"
        f"另有 {restate_historical} 处落在 §一 `[S:done]` 历史行，"
        "按「历史记录不追改」豁免、不计入（§二 批次行不在扫描范围）。"
    )

    files_desc = "、".join(QUEUE_PATHS_REL)
    if not violations:
        print(f"✓ {files_desc} 结构 lint 通过（列数／§二状态列格式／权威模块可 import）。")
        return 0

    print(f"✗ {files_desc} 结构 lint 发现 {len(violations)} 处违规：")
    for v in violations:
        print(f"  - {v}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
