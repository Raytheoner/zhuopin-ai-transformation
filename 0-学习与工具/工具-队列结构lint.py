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

用法：
  python 0-学习与工具/工具-队列结构lint.py
  # 退出码 0=通过；1=发现违规（详情打印到 stdout）
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
QUEUE_REL = "1-转型规划/0-全景路线图/跨桌任务队列.md"
EDIT_LOCK_SCRIPT = Path(__file__).resolve().with_name("工具-共享文档编辑锁.py")

_spec = importlib.util.spec_from_file_location("queue_lint_editlock_reuse", EDIT_LOCK_SCRIPT)
editlock = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(editlock)


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
    return violations


def main() -> int:
    violations = lint(REPO_ROOT)
    if not violations:
        print(f"✓ {QUEUE_REL} 结构 lint 通过（列数／§二状态列格式）。")
        return 0

    print(f"✗ {QUEUE_REL} 结构 lint 发现 {len(violations)} 处违规：")
    for v in violations:
        print(f"  - {v}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
