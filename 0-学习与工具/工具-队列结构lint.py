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
import sys
from pathlib import Path

QUEUE_REL = "1-转型规划/0-全景路线图/跨桌任务队列.md"
EDIT_LOCK_SCRIPT = Path(__file__).resolve().with_name("工具-共享文档编辑锁.py")

_spec = importlib.util.spec_from_file_location("queue_lint_editlock_reuse", EDIT_LOCK_SCRIPT)
editlock = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(editlock)

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


def lint(repo_root: Path) -> list[str]:
    text = (repo_root / QUEUE_REL).read_text(encoding="utf-8")
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

    if not violations:
        print(f"✓ {QUEUE_REL} 结构 lint 通过（列数／§二状态列格式／权威模块可 import）。")
        return 0

    print(f"✗ {QUEUE_REL} 结构 lint 发现 {len(violations)} 处违规：")
    for v in violations:
        print(f"  - {v}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
