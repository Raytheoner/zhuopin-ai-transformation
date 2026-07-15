from aibot_service.queue_appender import append_pending_task, _next_task_id, _section_bounds

SAMPLE_QUEUE = """\
---
title: "跨桌任务队列（单一调度文件）"
---

# 跨桌任务队列

## 〇、协议

正文……

## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 1 | 任务一 | CC | 指针1 | 产出1 | 待领 | — | 07-09 |
| 18 | 任务十八 | CC | 指针18 | 产出18 | 待领 | — | 07-11 |

## 二、待 commit 批次

后续内容不动。
"""

# 复刻真实队列文件的结构：§一 用 8 列表格 + 自己的编号（最大到 18），
# §四 是完全不同的 4 列表格、**自己独立的编号**（1-11，比 §一 小）。
# 2026-07-13 真实联调发现：旧实现无边界扫描，会把新行插进 §四 里、
# 还借用 §四 自己更小的编号——本测试文件专门盯防这个回归。
SAMPLE_QUEUE_WITH_LATER_TABLE = """\
## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 1 | 任务一 | CC | 指针1 | 产出1 | 待领 | — | 07-09 |
| 18 | 任务十八 | CC | 指针18 | 产出18 | 待领 | — | 07-11 |

## 二、占位小节

无关内容。

## 四、需 Paul 的动作

| # | 事项 | 等谁 | 截止 |
|---|------|------|------|
| 9 | 事项九 | Paul | 7/17 前 |
| 10 | 事项十 | Paul | CC 开建前 |
| 11 | 事项十一 | Paul | 8D 校准会前 |
"""


def test_next_task_id_computes_max_plus_one():
    lines = SAMPLE_QUEUE.splitlines()
    header_idx = next(i for i, l in enumerate(lines) if l.strip() == "## 一、任务看板")
    start, end = _section_bounds(lines, header_idx)
    assert _next_task_id(lines, start, end) == 19


def test_append_pending_task_inserts_after_last_row(tmp_path):
    queue_path = tmp_path / "queue.md"
    queue_path.write_text(SAMPLE_QUEUE, encoding="utf-8")

    row = append_pending_task(
        queue_path,
        description="企微反馈自动归档：姚祖怡 发来文件 x.xlsx",
        owner="采购专线",
        input_pointer="`7-外部文档/采购部/x.xlsx`",
        expected_output="核实内容并按需处理",
        date_str="2026-07-11",
    )

    new_text = queue_path.read_text(encoding="utf-8")
    assert "| 19 | 企微反馈自动归档：姚祖怡 发来文件 x.xlsx | 采购专线 |" in new_text
    assert row in new_text
    # 原有行未被破坏，且新增行紧跟在原表格最后一行之后
    lines = new_text.splitlines()
    idx_18 = next(i for i, l in enumerate(lines) if l.strip().startswith("| 18 |"))
    idx_19 = next(i for i, l in enumerate(lines) if l.strip().startswith("| 19 |"))
    assert idx_19 == idx_18 + 1
    # §二 及之后内容未被破坏
    assert "## 二、待 commit 批次" in new_text
    assert "后续内容不动。" in new_text


def test_append_pending_task_on_empty_table_starts_at_one(tmp_path):
    text = """\
## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|

## 二、下一节
"""
    queue_path = tmp_path / "queue.md"
    queue_path.write_text(text, encoding="utf-8")

    append_pending_task(
        queue_path,
        description="d",
        owner="o",
        input_pointer="i",
        expected_output="e",
        date_str="2026-07-11",
    )
    new_text = queue_path.read_text(encoding="utf-8")
    assert "| 1 | d | o | i | e | 待领 |  | 2026-07-11 |" in new_text


def test_append_pending_task_does_not_leak_into_later_differently_shaped_table(tmp_path):
    """2026-07-13 真实生产链路联调发现的严重回归：新行必须留在 §一 自己的
    表格里，编号延续 §一 自己的序列（19），不得跑进后面 §四 的 4 列表格、
    不得借用 §四 更小的独立编号（9/10/11）。"""
    queue_path = tmp_path / "queue.md"
    queue_path.write_text(SAMPLE_QUEUE_WITH_LATER_TABLE, encoding="utf-8")

    append_pending_task(
        queue_path,
        description="企微反馈自动归档：tangyanping 发来文本反馈",
        owner="财务专线",
        input_pointer="`7-外部文档/财务部/x.md`",
        expected_output="核实内容并按需处理",
        date_str="2026-07-13",
    )

    new_text = queue_path.read_text(encoding="utf-8")
    lines = new_text.splitlines()

    # 编号必须延续 §一 自己的序列（18 之后是 19），不是 §四 的 11 之后
    assert "| 19 | 企微反馈自动归档：tangyanping 发来文本反馈 | 财务专线 |" in new_text
    assert "| 12 | 企微反馈自动归档" not in new_text

    # 新行必须紧跟在 §一 的 "| 18 | ... |" 之后，且早于 "## 二、占位小节"
    idx_18 = next(i for i, l in enumerate(lines) if l.strip().startswith("| 18 |"))
    idx_19 = next(i for i, l in enumerate(lines) if l.strip().startswith("| 19 |"))
    idx_section2 = next(i for i, l in enumerate(lines) if l.strip() == "## 二、占位小节")
    idx_section4 = next(i for i, l in enumerate(lines) if l.strip() == "## 四、需 Paul 的动作")
    assert idx_19 == idx_18 + 1
    assert idx_19 < idx_section2 < idx_section4

    # §四 自己的表格必须原封不动（行数、内容、编号都不受影响）
    assert "| 9 | 事项九 | Paul | 7/17 前 |" in new_text
    assert "| 10 | 事项十 | Paul | CC 开建前 |" in new_text
    assert "| 11 | 事项十一 | Paul | 8D 校准会前 |" in new_text
    section4_rows = [l for l in lines[idx_section4:] if l.strip().startswith("|")]
    assert len(section4_rows) == 5  # 表头 + 分隔 + 3 条原行，没被插入新行
