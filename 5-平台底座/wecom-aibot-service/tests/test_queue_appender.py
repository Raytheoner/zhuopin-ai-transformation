import pytest

from zhuopin_platform.audit import AuditLogger

from aibot_service.queue_appender import (
    append_pending_task,
    _next_task_id,
    _parse_section_one_high_water_mark,
    _section_bounds,
    _ROW_ID_RE,
)

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


# ── 编号高水位线（2026-07-24 首次清扫下游 gap，队列 #99）─────────────────

SAMPLE_QUEUE_WITH_HIGH_WATER_MARK = """\
---
title: "跨桌任务队列（单一调度文件）"
---

> **编号高水位线：§一 #123 ｜ §四 #36**（2026-07-24 首次清扫起启用）

## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|

## 二、待 commit 批次

后续内容不动。
"""


def test_parse_section_one_high_water_mark_reads_section_one_number():
    lines = SAMPLE_QUEUE_WITH_HIGH_WATER_MARK.splitlines()
    assert _parse_section_one_high_water_mark(lines) == 123


def test_parse_section_one_high_water_mark_missing_line_returns_none():
    lines = SAMPLE_QUEUE.splitlines()
    assert _parse_section_one_high_water_mark(lines) is None


def test_parse_section_one_high_water_mark_malformed_line_returns_none():
    """标注行存在但格式变化（缺 §一 编号），不得抛异常，按"解析失败"处理。"""
    lines = "> **编号高水位线：格式已变，无法解析**".splitlines()
    assert _parse_section_one_high_water_mark(lines) is None


def test_next_task_id_uses_high_water_mark_when_higher_than_visible_max():
    """清扫后场景：§一 表格里可见行已被搬空（或只剩较小号），但顶部高水
    位线仍是 #123——新编号必须接续 124，不能从可见的小号重新数起（队列
    #99 描述的确切 bug 场景：清扫把最高号行迁走后与已归档编号撞号）。"""
    lines = SAMPLE_QUEUE_WITH_HIGH_WATER_MARK.splitlines()
    header_idx = next(i for i, l in enumerate(lines) if l.strip() == "## 一、任务看板")
    start, end = _section_bounds(lines, header_idx)
    assert _next_task_id(lines, start, end) == 124


SAMPLE_QUEUE_WITH_STALE_HIGH_WATER_MARK = """\
> **编号高水位线：§一 #10 ｜ §四 #5**（尚未跑过本轮清扫更新）

## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 1 | 任务一 | CC | 指针1 | 产出1 | 待领 | — | 07-09 |
| 18 | 任务十八 | CC | 指针18 | 产出18 | 待领 | — | 07-11 |
"""


def test_next_task_id_prefers_visible_max_when_higher_than_high_water_mark():
    """高水位线滞后于表格内实际最大号（如尚未跑过清扫更新该行）时，仍应
    取两者较大值——不能让一个过时的、偏小的高水位线把编号往回拉。"""
    lines = SAMPLE_QUEUE_WITH_STALE_HIGH_WATER_MARK.splitlines()
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


# ── 编号高水位线跨清扫场景（队列 #99）─────────────────────────────────────

QUEUE_BEFORE_SWEEP = """\
> **编号高水位线：§一 #17 ｜ §四 #5**（首次清扫前，尚未更新到本轮）

## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 1 | 任务一 | CC | 指针1 | 产出1 | 待领 | — | 07-09 |
| 18 | 任务十八 | CC | 指针18 | 产出18 | 待领 | — | 07-11 |

## 二、待 commit 批次

后续内容不动。
"""

# 清扫后：#1/#18 已整行迁出正文（搬进归档件），§一 表格暂时空表；顶部高水
# 位线同步更新为清扫时的真实最大号 #18——若清扫前恰好还有一条 #19 之类的
# 行，高水位线会是 19，此处用 18 复刻"表格清空、水位线=历史最大号"的典型
# 清扫后状态。
QUEUE_AFTER_SWEEP = """\
> **编号高水位线：§一 #18 ｜ §四 #5**（2026-07-24 首次清扫起启用）

## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|

## 二、待 commit 批次

后续内容不动。
"""


def test_append_pending_task_before_sweep_uses_visible_max(tmp_path):
    """清扫前：表格内仍看得见 #18，高水位线（#17）落后于可见最大号——新行
    应延续可见序列到 19，不被一个偏旧的高水位线拉低。"""
    queue_path = tmp_path / "queue.md"
    queue_path.write_text(QUEUE_BEFORE_SWEEP, encoding="utf-8")

    row = append_pending_task(
        queue_path,
        description="企微反馈自动归档：清扫前测试",
        owner="CC 平台",
        input_pointer="p",
        expected_output="e",
        date_str="2026-07-27",
    )

    assert row.startswith("| 19 |")
    assert "| 19 | 企微反馈自动归档：清扫前测试 |" in queue_path.read_text(encoding="utf-8")


def test_append_pending_task_after_sweep_continues_from_high_water_mark(tmp_path):
    """队列 #99 描述的确切 bug 场景：清扫把 #1/#18 迁出正文后，§一 表格暂时
    空表——旧实现会从 #1 重新编号，与已迁入归档件的 #1/#18 撞号；修复后应
    读取顶部高水位线（#18），新行编号为 19。"""
    queue_path = tmp_path / "queue.md"
    queue_path.write_text(QUEUE_AFTER_SWEEP, encoding="utf-8")

    row = append_pending_task(
        queue_path,
        description="企微反馈自动归档：清扫后测试",
        owner="CC 平台",
        input_pointer="p",
        expected_output="e",
        date_str="2026-07-27",
    )

    assert row.startswith("| 19 |")
    new_text = queue_path.read_text(encoding="utf-8")
    assert "| 19 | 企微反馈自动归档：清扫后测试 |" in new_text
    assert "| 1 |" not in new_text.split("## 一、任务看板", 1)[1].split("## 二", 1)[0]


def test_append_pending_task_with_audit_logs_nothing_when_high_water_mark_parses(tmp_path):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    queue_path = tmp_path / "queue.md"
    queue_path.write_text(QUEUE_AFTER_SWEEP, encoding="utf-8")

    append_pending_task(
        queue_path,
        description="d", owner="o", input_pointer="i", expected_output="e",
        date_str="2026-07-27", audit=audit,
    )

    records = audit.query_by(scenario="wecom-aibot", action="queue_high_water_mark_parse_failed")
    assert records == []


def test_append_pending_task_with_audit_logs_fallback_when_marker_missing(tmp_path):
    """高水位线标注行缺失（旧版文件/格式漂移）时，仍应按"仅取可见最大号"
    回落计算（不崩溃、不阻塞追加），但需留痕一条审计事件供日后排查。"""
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    queue_path = tmp_path / "queue.md"
    queue_path.write_text(SAMPLE_QUEUE, encoding="utf-8")  # 无高水位线标注行

    row = append_pending_task(
        queue_path,
        description="d", owner="o", input_pointer="i", expected_output="e",
        date_str="2026-07-27", audit=audit,
    )

    assert row.startswith("| 19 |")  # 回落行为不变：仍是可见最大号(18)+1
    records = audit.query_by(scenario="wecom-aibot", action="queue_high_water_mark_parse_failed")
    assert len(records) == 1
    assert records[0]["decision"]["fallback"] == "visible_max_only"
    assert records[0]["decision"]["task_id"] == 19


def test_append_pending_task_without_audit_param_skips_logging_silently(tmp_path):
    """不传 `audit`（既有调用方/未接线场景）时行为与加此参数前完全一致，
    不应因为省略该参数而报错。"""
    queue_path = tmp_path / "queue.md"
    queue_path.write_text(SAMPLE_QUEUE, encoding="utf-8")

    row = append_pending_task(
        queue_path,
        description="d", owner="o", input_pointer="i", expected_output="e",
        date_str="2026-07-27",
    )
    assert row.startswith("| 19 |")


# ── 乐观并发重试（2026-07-22，队列 #69/#70 事故后补）──────────────────────

class _FlakyPath:
    """包一层真实 Path，模拟"计算插入行期间磁盘被并发写"的竞态：在第
    `race_before_call` 次 `read_text` 调用之前，往真实文件里插进一行，模拟
    另一个写手（如另一条企微消息的归档追加，或人工/CC 编辑）抢先写入。"""

    def __init__(self, real_path, race_before_call=2, race_forever=False):
        self._real = real_path
        self._call_count = 0
        self._race_before_call = race_before_call
        self._race_forever = race_forever
        self._injected = False

    def read_text(self, encoding="utf-8"):
        self._call_count += 1
        should_race = self._race_forever or (
            self._call_count == self._race_before_call and not self._injected
        )
        if should_race:
            self._injected = True
            current = self._real.read_text(encoding=encoding)
            lines = current.splitlines()
            ids = [int(m.group(1)) for l in lines if (m := _ROW_ID_RE.match(l.strip()))]
            last_row_idx = max(
                i for i, l in enumerate(lines) if _ROW_ID_RE.match(l.strip())
            )
            new_id = max(ids) + 1
            lines.insert(
                last_row_idx + 1,
                f"| {new_id} | 并发写手抢先插入的行 | 其他专线 | p | e | 待领 | — | 07-22 |",
            )
            self._real.write_text("\n".join(lines) + "\n", encoding=encoding)
        return self._real.read_text(encoding=encoding)

    def write_text(self, content, encoding="utf-8"):
        return self._real.write_text(content, encoding=encoding)

    def __str__(self):
        return str(self._real)


def test_append_pending_task_retries_when_disk_changes_before_write(tmp_path):
    """写入前的核验读发现磁盘已被并发写手改过（模拟另一条归档同时抢先追加了
    一行）——应放弃本轮计算、按最新磁盘内容重新定位插入点/重新编号，不得拿
    过期的计算结果覆盖对方刚写入的行（这正是队列 #69/#70 事故的根因：原实现
    没有这层核验，静默覆盖过路人的追加）。"""
    queue_path = tmp_path / "queue.md"
    queue_path.write_text(SAMPLE_QUEUE, encoding="utf-8")
    flaky = _FlakyPath(queue_path, race_before_call=2)

    row = append_pending_task(
        flaky,
        description="我方要追加的行",
        owner="财务专线",
        input_pointer="p2",
        expected_output="e2",
        date_str="2026-07-22",
    )

    final_text = queue_path.read_text(encoding="utf-8")
    # 对方抢先插入的行必须还在，没被覆盖丢失
    assert "| 19 | 并发写手抢先插入的行 | 其他专线 |" in final_text
    # 我方的行按重算后的新编号（20）追加在对方之后，不是过期的 19
    assert "| 20 | 我方要追加的行 | 财务专线 |" in final_text
    assert row.startswith("| 20 |")
    lines = final_text.splitlines()
    idx_19 = next(i for i, l in enumerate(lines) if l.strip().startswith("| 19 |"))
    idx_20 = next(i for i, l in enumerate(lines) if l.strip().startswith("| 20 |"))
    assert idx_20 == idx_19 + 1


def test_append_pending_task_raises_after_max_retries_under_perpetual_race(tmp_path):
    """磁盘被持续不断地并发改写（每次核验都发现变化）——重试耗尽后应显式
    报错，而不是无限重试卡死，也不是放弃核验直接覆盖。"""
    queue_path = tmp_path / "queue.md"
    queue_path.write_text(SAMPLE_QUEUE, encoding="utf-8")
    flaky = _FlakyPath(queue_path, race_forever=True)

    with pytest.raises(RuntimeError, match="持续被并发写入"):
        append_pending_task(
            flaky,
            description="我方要追加的行",
            owner="财务专线",
            input_pointer="p2",
            expected_output="e2",
            date_str="2026-07-22",
            max_retries=3,
        )
