"""open_pool.py 单测（队列 #312，2026-09-02 裁定「以看板判据为准、两侧共用同一判定函数」）。

判据逐条各配用例（open／partial 入池、done/blocked/hold/timed 排除、[A: 排除、
🛑 两列排除、partial 自陈在办单列、partial 首标记 ✅ 带 flag、缺字段 degraded、
列数不符 skipped），另配「两份物理文件逐份解析后合并」与 JSON 形状用例。
两侧（推送器 vs 看板 ps1）对同一份队列真身逐行相同的断言测试在
`wecom-aibot-service/tests/test_open_pool_alignment.py`（那边能 import 推送器）。
"""
from __future__ import annotations

from pathlib import Path

from zhuopin_platform.shared_tools.open_pool import (
    PARTIAL_DONE_MARK_FLAG,
    PARTIAL_IN_PROGRESS_WHY,
    VERDICT_DEGRADED,
    VERDICT_EXCLUDED,
    VERDICT_OUT,
    VERDICT_POOL,
    VERDICT_SKIPPED,
    compute_open_pool,
    judge_open_pool_row,
    judge_section_one,
    lead_task_text,
    leading_segment,
    parse_status_domain_fields,
    section_one_text,
    snapshot_to_kanban_payload,
)
from zhuopin_platform.shared_tools.queue_table import iter_queue_paths

_HEADER = (
    "## 一、任务看板\n\n"
    "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
    "|---|------|--------|-------------|----------|------|--------|------|\n"
)


def _row(no: str, task: str, status: str, owner: str = "待领") -> str:
    return f"| {no} | {task} | {owner} | 输入 | 产出 | {status} | — | 09-12 |\n"


def _cells(no: str, task: str, status: str, owner: str = "待领") -> list[str]:
    return [no, task, owner, "输入", "产出", status, "—", "09-12"]


# ── 单行判据 ───────────────────────────────────────────────────────────────


def test_open_row_enters_pool():
    v = judge_open_pool_row(_cells("1", "活", "[S:open][D:机] 待领"))
    assert v.verdict == VERDICT_POOL and v.status == "open" and v.domain == "机"


def test_partial_row_enters_pool_by_default():
    """裁定 ⑴：partial ＝ 主体做完、尾巴挂着，尾巴本身就是可开工的活。"""
    v = judge_open_pool_row(_cells("2", "活", "[S:partial][D:业] 🟡 半边待领（另一半已交付）"))
    assert v.verdict == VERDICT_POOL and v.status == "partial" and v.flag == ""


def test_done_blocked_hold_timed_are_structurally_out():
    for st in ("done", "blocked", "hold", "timed=2026-10-01"):
        v = judge_open_pool_row(_cells("3", "活", f"[S:{st}][D:机] 正文"))
        assert v.verdict == VERDICT_OUT, st


def test_assigned_marker_anywhere_in_status_cell_is_out():
    v = judge_open_pool_row(_cells("4", "活", "[S:open][D:机][A:已派出] 🔄 在办"))
    assert v.verdict == VERDICT_OUT and v.assigned is True


def test_stop_marker_in_status_body_is_out():
    """裁定 ⑵：🛑 ＝ 明示的「结构性不可动」。"""
    v = judge_open_pool_row(_cells("5", "活", "[S:open][D:机] 🛑 **排队中·暂非可动**"))
    assert v.verdict == VERDICT_OUT and "状态列" in v.why


def test_stop_marker_leading_task_column_is_out():
    """认两列（OP-0911-N design D-B 甲，`#381` 形态）：任务列 🛑 起首、状态列不含。
    生产实测 `#382`／`#448` 即此形态，此前两侧都误入池。"""
    v = judge_open_pool_row(_cells("6", "🛑 **排队中·暂非可动（WIP 超限）**", "[S:open][D:机] 待领"))
    assert v.verdict == VERDICT_OUT and "任务列" in v.why


def test_stop_marker_not_leading_does_not_exclude():
    """判据只认「以 🛑 起首」，正文中段提到 🛑 不算（防判据过宽）。"""
    v = judge_open_pool_row(_cells("7", "活（去 🛑 后可领）", "[S:open][D:机] 🟢 可领，见 🛑 说明"))
    assert v.verdict == VERDICT_POOL


def test_partial_self_declared_in_progress_is_excluded_and_listed():
    v = judge_open_pool_row(_cells("8", "活", "[S:partial][D:机] 🔄 在办中（三步已完成两步）。尾注"))
    assert v.verdict == VERDICT_EXCLUDED and v.why == PARTIAL_IN_PROGRESS_WHY
    assert v.lead_status == "🔄 在办中（三步已完成两步）"


def test_partial_in_progress_word_after_separator_is_not_matched():
    """开头片段截到首个句级分隔符——「在办」出现在 `。`／`——`／`━━━` 之后不算。"""
    v = judge_open_pool_row(_cells("9", "活", "[S:partial][D:机] 尾巴待领。历史：曾在办"))
    assert v.verdict == VERDICT_POOL


def test_open_row_with_in_progress_words_is_not_excluded():
    """例外排除只对 partial；open 行自陈「在办」应打 `[A:`，不靠猜中文。"""
    v = judge_open_pool_row(_cells("10", "活", "[S:open][D:机] 在办中"))
    assert v.verdict == VERDICT_POOL


def test_partial_with_done_mark_enters_pool_with_flag():
    v = judge_open_pool_row(_cells("11", "活", "[S:partial][D:机] ✅ **主体交付**，尾巴待领"))
    assert v.verdict == VERDICT_POOL and v.flag == PARTIAL_DONE_MARK_FLAG


def test_missing_status_field_is_degraded():
    v = judge_open_pool_row(_cells("12", "活", "待领（历史遗留）"))
    assert v.verdict == VERDICT_DEGRADED and "[S:" in v.why


def test_missing_domain_field_is_degraded_not_pooled():
    """缺 `[D:]` 归 degraded（看板 `$poolDeg` 口径）：按域分组渲染的看板对域为 None 的
    行会计入 N 却渲染不出来；推送器不猜域（`#523` 同理）。"""
    v = judge_open_pool_row(_cells("13", "活", "[S:open] 待领"))
    assert v.verdict == VERDICT_DEGRADED and "[D:" in v.why


def test_missing_domain_on_done_row_is_out_not_degraded():
    """只对可动状态报缺域；done 行缺域本就不进池，报它只会把告警做成噪声。"""
    v = judge_open_pool_row(_cells("14", "活", "[S:done] ✅"))
    assert v.verdict == VERDICT_OUT


def test_column_count_mismatch_is_skipped():
    v = judge_open_pool_row(_cells("15", "活", "[S:open][D:机] 待领") + ["多一列"], column_ok=False)
    assert v.verdict == VERDICT_SKIPPED and v.row_id == "15"


def test_leading_bold_and_fullwidth_space_are_stripped():
    v = judge_open_pool_row(_cells("16", "活", "**[S:open][D:机]**　🛑 排队"))
    assert v.verdict == VERDICT_OUT  # 剥掉 `*`／全角空格后仍能识别字段与 🛑


# ── 辅助函数 ───────────────────────────────────────────────────────────────


def test_leading_segment_cuts_at_first_separator():
    assert leading_segment("* 🟡 待领——历史") == "🟡 待领"
    assert leading_segment("　✅ 完。尾") == "✅ 完"
    assert leading_segment("无分隔") == "无分隔"


def test_lead_task_text_truncates_at_78_with_ellipsis():
    long = "字" * 100
    assert lead_task_text(long) == "字" * 78 + "…"
    assert lead_task_text("短") == "短"


def test_parse_status_domain_fields_shapes():
    assert parse_status_domain_fields("[S:open][D:机] 正文") == ("open", "机", " 正文")
    assert parse_status_domain_fields("[S:timed=2026-10-01] x")[0] == "timed=2026-10-01"
    assert parse_status_domain_fields("无字段") == (None, None, "无字段")


# ── 分区与文件 ─────────────────────────────────────────────────────────────


def test_section_one_text_only_takes_first_heading():
    """🔴 只取第一个 `## 一、`——两份文件必须逐份解析后合并，拼接会静默丢第二份。"""
    text = _HEADER + _row("1", "a", "[S:open][D:机] 待领") + "\n## 二、x\n" + _HEADER + _row("2", "b", "[S:open][D:业] 待领")
    ids = {v.row_id for v in judge_section_one(text)}
    assert ids == {"1"}
    assert section_one_text("没有一节") == ""


def test_judge_section_one_returns_all_verdicts_unfiltered():
    text = _HEADER + _row("1", "a", "[S:open][D:机] 待领") + _row("2", "b", "[S:done][D:机] ✅") + _row("3", "c", "无字段")
    by_id = {v.row_id: v.verdict for v in judge_section_one(text)}
    assert by_id == {"1": VERDICT_POOL, "2": VERDICT_OUT, "3": VERDICT_DEGRADED}


def _write_dual(tmp_path: Path, mech: str | None, biz: str | None) -> None:
    mech_rel, biz_rel = iter_queue_paths()
    for rel, text in ((mech_rel, mech), (biz_rel, biz)):
        if text is None:
            continue
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def test_compute_open_pool_merges_both_physical_files(tmp_path: Path):
    _write_dual(
        tmp_path,
        _HEADER + _row("1", "机", "[S:open][D:机] 待领"),
        _HEADER + _row("2", "业", "[S:partial][D:业] 尾巴待领") + _row("3", "业", "[S:blocked][D:业] 等回件"),
    )
    snap = compute_open_pool(tmp_path)
    assert snap.pool_ids() == ["1", "2"] and snap.errors == []
    mech_rel, biz_rel = iter_queue_paths()
    assert [rel for rel, _v in snap.pool] == [mech_rel, biz_rel]


def test_compute_open_pool_reports_missing_file_as_error(tmp_path: Path):
    """残缺的结果不当作完整的池：缺一份文件必须显式出现在 `errors`。"""
    _write_dual(tmp_path, _HEADER + _row("1", "机", "[S:open][D:机] 待领"), None)
    snap = compute_open_pool(tmp_path)
    _mech_rel, biz_rel = iter_queue_paths()
    assert snap.pool_ids() == ["1"]
    assert [rel for rel, _why in snap.errors] == [biz_rel]


def test_kanban_payload_shape_matches_ps1_contract(tmp_path: Path):
    """键名与看板 ps1 原 `$pool`／`$poolEx`／`$poolDeg` 逐字一致（JS 按这些键渲染）。"""
    _write_dual(
        tmp_path,
        _HEADER
        + _row("1", "活一", "[S:open][D:机] 待领")
        + _row("2", "活二", "[S:partial][D:机] 🔄 在办中")
        + _row("3", "活三", "[S:open] 缺域")
        + "| 4 | 撑列 | 待领 | 输入 | 产出 | [S:open][D:机] | — | 多 | 09-12 |\n",
        _HEADER,
    )
    payload = snapshot_to_kanban_payload(compute_open_pool(tmp_path))
    assert payload["pool"] == [{"no": "1", "dom": "机", "st": "open", "task": "活一", "flag": ""}]
    assert payload["poolEx"] == [{"no": "2", "dom": "机", "why": PARTIAL_IN_PROGRESS_WHY, "lead": "🔄 在办中"}]
    assert payload["poolDeg"] == ["3"]
    assert payload["skipped"] == ["4"]
    assert payload["errors"] == []
