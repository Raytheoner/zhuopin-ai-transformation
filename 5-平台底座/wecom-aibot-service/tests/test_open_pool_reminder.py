"""open_pool_reminder.py 单测（队列 #312）。

覆盖五类：①§一 `[S:open]` 行解析（含域字段/缺字段非静默降级）；②opener
文件探测（词边界，同 #302 教训避免 `#22` 误命中 `#220`）；③指纹去重（池
从 0 变非 0 / 新增行号触发，集合不变或缩小静默，消失后再现视为新）；
④提醒文案格式（自带下一步动作）；⑤`send_open_pool_reminder` 主通道/
兜底四态（形状仿 `test_decision_reminder.py::send_decision_reminder`
同款用例）。

沿用本服务既有测试风格（纯函数式用例，不套 unittest.TestCase）。
"""
from __future__ import annotations

import asyncio
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

from zhuopin_platform.audit import AuditLogger

from aibot_service.open_pool_reminder import (
    AssignedBackfillCandidate,
    OpenPoolItem,
    StaleCandidate,
    build_pool_items,
    build_pool_items_from_repo,
    compute_new_ids,
    compute_stale_candidates,
    default_state,
    discover_opener_files,
    find_opener_path,
    format_pool_reminder_message,
    format_stale_reminder_message,
    list_assigned_backfill_candidates,
    list_assigned_backfill_candidates_from_repo,
    load_state,
    new_known_state,
    new_stale_state,
    parse_open_pool_rows,
    save_state,
    send_open_pool_reminder,
)

SECTION_ONE_SAMPLE = """\
## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 82 | 真可开工·业务域 | 待领 | 输入 | 产出 | [S:open][D:业] 待领（P1，紧急） | — | 07-30 |
| 98 | 真可开工·机制域 | 待领 | 输入 | 产出 | [S:open][D:机] 待领（P2） | — | 07-30 |
| 315 | 域字段缺失仍算可开工 | 待领 | 输入 | 产出 | [S:open] 待领（域字段历史缺失） | — | 07-30 |
| 172 | 在办中不算 | CC 平台 | 输入 | 产出 | [S:partial][D:机] 待领（三步已完成两步） | — | 07-30 |
| 224 | 受阻不算 | CC | 输入 | 产出 | [S:blocked][D:业] 待领（依赖签认） | — | 07-30 |
| 129 | 定时触发不算 | CC | 输入 | 产出 | [S:timed=2026-08-25][D:机] 待领 | — | 07-30 |
| 22 | 已完成不算 | CC | 输入 | 产出 | [S:done][D:机] ✅ 已完成 | — | 07-30 |
| 11 | 缺字段行 | 待领 | 输入 | 产出 | 待领（历史遗留，未回填字段） | — | 07-09 |

## 二、占位
"""


# ── 解析：§一 [S:open] 行 ──────────────────────────────────────────────────


def test_parse_open_pool_only_status_open_rows_included():
    rows = {r.row_id: r for r in parse_open_pool_rows(SECTION_ONE_SAMPLE)}
    assert set(rows) == {"82", "98", "315"}


def test_parse_open_pool_partial_hold_blocked_timed_done_excluded():
    rows = {r.row_id: r for r in parse_open_pool_rows(SECTION_ONE_SAMPLE)}
    for excluded_id in ("172", "224", "129", "22"):
        assert excluded_id not in rows


def test_parse_open_pool_domain_field_captured():
    rows = {r.row_id: r for r in parse_open_pool_rows(SECTION_ONE_SAMPLE)}
    assert rows["82"].domain == "业"
    assert rows["98"].domain == "机"


def test_parse_open_pool_missing_domain_field_is_none_not_excluded():
    rows = {r.row_id: r for r in parse_open_pool_rows(SECTION_ONE_SAMPLE)}
    assert "315" in rows
    assert rows["315"].domain is None


def test_parse_open_pool_malformed_row_column_count_is_skipped():
    malformed = (
        "## 一、任务看板\n\n"
        "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
        "|---|------|--------|-------------|----------|------|--------|------|\n"
        "| 99 | 裸竖线撑列 | 多出一列 | 输入 | 产出 | [S:open] | — | 额外一列 | 07-31 |\n"
    )
    assert parse_open_pool_rows(malformed) == []


def test_missing_status_field_emits_runtime_warning_and_skipped():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        rows = {r.row_id: r for r in parse_open_pool_rows(SECTION_ONE_SAMPLE)}
    assert "11" not in rows  # 非静默降级：跳过，不像 decision_reminder 那样回退旧判据
    assert any(
        issubclass(w.category, RuntimeWarning) and "状态字段缺失" in str(w.message)
        for w in caught
    )


def test_parse_open_pool_summary_is_task_cell_prefix():
    rows = {r.row_id: r for r in parse_open_pool_rows(SECTION_ONE_SAMPLE)}
    assert rows["82"].summary == "真可开工·业务域"


# ── opener 探测：词边界 + 索引命中 ──────────────────────────────────────────


def test_find_opener_path_exact_match_hits():
    index = [(Path("派单件-X.md"), [(None, {82, 315})])]
    assert find_opener_path("82", None, index) == Path("派单件-X.md")


def test_find_opener_path_substring_false_positive_avoided():
    """队列 #302 同款教训：正文含 `#220` 不应让 row_id="22" 被误判命中——
    `_ROW_NUMBER_RE` 按完整数字游程提取，220 != 22。"""
    index = [(Path("本周计划-X.md"), [(None, {220, 221})])]
    assert find_opener_path("22", None, index) is None


def test_find_opener_path_no_match_returns_none():
    index = [(Path("派单件-X.md"), [(None, {1, 2, 3})])]
    assert find_opener_path("999", None, index) is None


def test_find_opener_path_non_digit_row_id_returns_none():
    index = [(Path("派单件-X.md"), [(None, {1, 2, 3})])]
    assert find_opener_path("205-A", None, index) is None


def test_find_opener_path_returns_first_index_match():
    index = [
        (Path("开场prompt-A.md"), [(None, {1})]),
        (Path("本周计划-B.md"), [(None, {1, 2})]),
    ]
    assert find_opener_path("1", None, index) == Path("开场prompt-A.md")


# ── opener 环境过滤（队列 #312，OP-0830-D，design D3）────────────────────


def test_find_opener_path_confirmed_env_mismatch_is_excluded():
    """真实事故复现：`#435`（领取方 CC）不得被一个明确声明 Cowork 的候选块
    命中——即便该块确实提到了 `#435`（顺带提及）。08:31 推送曾把 `#435`
    的 opener 指给《开场prompt-【Cowork】构建环境接力-2026-08-29晚.md》，
    照它复制会开成 Cowork 会话去做一件 CC 的活。"""
    index = [(Path("开场prompt-【Cowork】构建环境接力-2026-08-29晚.md"), [("Cowork", {435})])]
    assert find_opener_path("435", "CC", index) is None


def test_find_opener_path_matching_env_is_given():
    index = [(Path("派单件-【CC】全局记忆巡检与root棘轮-队列435-2026-08-29.md"), [("CC", {435})])]
    assert find_opener_path("435", "CC", index) == Path(
        "派单件-【CC】全局记忆巡检与root棘轮-队列435-2026-08-29.md"
    )


def test_find_opener_path_mismatch_skips_to_next_matching_candidate():
    """两个候选都提到同一行号：环境冲突的块被跳过，继续找到环境相符的
    那个——不是"第一个命中就返回"，是"第一个环境不冲突的命中才返回"。"""
    index = [
        (Path("开场prompt-【Cowork】构建环境接力-2026-08-29晚.md"), [("Cowork", {435})]),
        (Path("派单件-【CC】队列435.md"), [("CC", {435})]),
    ]
    assert find_opener_path("435", "CC", index) == Path("派单件-【CC】队列435.md")


def test_find_opener_path_unknown_row_env_does_not_filter():
    """领取方环境未知（owner 列写法不规范/split-ownership）时不做环境
    过滤——不确定不等于"确认冲突"，不因此牺牲既有匹配（design D3 取舍：
    漏给的代价是他多点一次队列行，给错的代价是开一个错环境的会话去做
    活，二者不对称，这里只精确堵已验证过的确认冲突）。"""
    index = [(Path("开场prompt-【Cowork】构建环境接力-2026-08-29晚.md"), [("Cowork", {435})])]
    assert find_opener_path("435", None, index) == Path(
        "开场prompt-【Cowork】构建环境接力-2026-08-29晚.md"
    )


def test_find_opener_path_unlabeled_candidate_block_is_not_filtered():
    """候选块没有『设置』声明环境（旧式文件/未遵守开场词纪律）时同样不
    过滤——只在两侧都已知且冲突时才排除。"""
    index = [(Path("旧式文件.md"), [(None, {435})])]
    assert find_opener_path("435", "CC", index) == Path("旧式文件.md")


def test_build_pool_items_real_cowork_file_not_used_as_cc_opener(tmp_path: Path):
    """队列 #312 真实事故回归：用 `#435` 与《开场prompt-【Cowork】构建
    环境接力-2026-08-29晚.md》这对真实数据做验证——CC 行不得被这份
    Cowork 接力卡命中当作 opener（即便该文件确实提到了 #435）。"""
    real_file = (
        Path(__file__).resolve().parents[3]
        / "1-转型规划" / "0-全景路线图"
        / "开场prompt-【Cowork】构建环境接力-2026-08-29晚.md"
    )
    real_text = real_file.read_text(encoding="utf-8")
    assert "#435" in real_text  # 前提断言：真实文件确实提到 #435（顺带提及）
    assert "执行环境：Cowork" in real_text  # 前提断言：该文件确声明 Cowork

    repo_root = _make_repo(tmp_path)
    opener_dir = repo_root / "1-转型规划" / "0-全景路线图"
    (opener_dir / real_file.name).write_text(real_text, encoding="utf-8")

    queue_text = (
        "## 一、任务看板\n\n"
        "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
        "|---|------|--------|-------------|----------|------|--------|------|\n"
        "| 435 | 全局记忆巡检 | CC（写生产码、自行 commit+push、一任务一 worktree） "
        "| 输入 | 产出 | [S:open][D:机] 待领 | — | 08-29 |\n"
    )
    items = {i.row_id: i for i in build_pool_items(queue_text, repo_root)}
    assert items["435"].opener_path is None  # 宁可不给，也不给错的


# ══════════════════════════════════════════════════════════════════════════
# 队列 #312（OP-0830-D）· assigned 字段 [A:...] ＋ 领取方环境推断
# ══════════════════════════════════════════════════════════════════════════

_ASSIGNED_SAMPLE = """\
## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 501 | 已派出仍标 open 不再进池 | CC（写生产码） | 输入 | 产出 | [S:open][D:机][A:已派出] 🔄 在办中 | — | 08-30 |
| 502 | 顺序写反仍应被排除 | CC | 输入 | 产出 | [S:open][A:已派出][D:机] 🔄 在办中 | — | 08-30 |
| 503 | 正常待领 | CC（写生产码） | 输入 | 产出 | [S:open][D:机] 待领 | — | 08-30 |

## 二、占位
"""


def test_assigned_row_excluded_from_pool():
    rows = {r.row_id for r in parse_open_pool_rows(_ASSIGNED_SAMPLE)}
    assert "501" not in rows
    assert "503" in rows


def test_assigned_row_with_reversed_field_order_still_excluded():
    """design D1：字段顺序写反虽然会让域字段被吃掉，但『行含 [A:』这条
    排除判据不解析取值、不看位置——仍必须排除，不能因为顺序错了反而
    漏排除。"""
    rows = {r.row_id for r in parse_open_pool_rows(_ASSIGNED_SAMPLE)}
    assert "502" not in rows


def test_reversed_field_order_emits_runtime_warning():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        parse_open_pool_rows(_ASSIGNED_SAMPLE)
    messages = [str(w.message) for w in caught if issubclass(w.category, RuntimeWarning)]
    assert any("顺序错误" in m and "502" in m for m in messages)


def test_correct_field_order_emits_no_order_warning():
    only_good = (
        "## 一、任务看板\n\n"
        "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
        "|---|------|--------|-------------|----------|------|--------|------|\n"
        "| 501 | 正常顺序 | CC | 输入 | 产出 | [S:open][D:机][A:已派出] 🔄 在办 | — | 08-30 |\n"
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        parse_open_pool_rows(only_good)
    assert not any("顺序错误" in str(w.message) for w in caught)


def test_removing_assigned_field_returns_row_to_pool():
    """spec Scenario「撤销派出」：`[A:...]` 被删除且仍为 `[S:open]` ⇒
    该行重新进入池子。"""
    with_a = (
        "## 一、任务看板\n\n"
        "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
        "|---|------|--------|-------------|----------|------|--------|------|\n"
        "| 501 | 撤销测试 | CC | 输入 | 产出 | [S:open][D:机][A:已派出] 🔄 在办 | — | 08-30 |\n"
    )
    without_a = with_a.replace("[A:已派出] ", "")
    assert "501" not in {r.row_id for r in parse_open_pool_rows(with_a)}
    assert "501" in {r.row_id for r in parse_open_pool_rows(without_a)}


def test_row_env_inferred_from_owner_column():
    """`_infer_row_environment` 的四种真实观测形态（2026-08-30 对生产队列
    全部 `[S:open]` 行实测得出）：干净单值／split-ownership／两者都不提。"""
    text = (
        "## 一、任务看板\n\n"
        "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
        "|---|------|--------|-------------|----------|------|--------|------|\n"
        "| 601 | CC 独占 | CC（写生产码） | 输入 | 产出 | [S:open][D:机] 待领 | — | 08-30 |\n"
        "| 602 | Cowork 独占 | Cowork 质量专线 | 输入 | 产出 | [S:open][D:机] 待领 | — | 08-30 |\n"
        "| 603 | 两者都提（split-ownership） | CC（A1）＋Cowork（A2） | 输入 | 产出 "
        "| [S:open][D:机] 待领 | — | 08-30 |\n"
        "| 604 | 两者都不提 | Shao Peishen | 输入 | 产出 | [S:open][D:机] 待领 | — | 08-30 |\n"
    )
    rows = {r.row_id: r for r in parse_open_pool_rows(text)}
    assert rows["601"].env == "CC"
    assert rows["602"].env == "Cowork"
    assert rows["603"].env is None
    assert rows["604"].env is None


# ══════════════════════════════════════════════════════════════════════════
# 队列 #312（OP-0830-D）· 存量回填候选（design D4）
# ══════════════════════════════════════════════════════════════════════════

_BACKFILL_SAMPLE = """\
## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 701 | 在办未打 A，正文起首为 🔄 | 值周巡检 | 输入 | 产出 | [S:open][D:机] 🔄 **在办（示例）** | — | 08-30 |
| 702 | 已打 A，不需要回填 | CC | 输入 | 产出 | [S:open][D:机][A:已派出] 🔄 在办 | — | 08-30 |
| 703 | 待领，正文非 🔄 起首 | 待领 | 输入 | 产出 | [S:open][D:机] 待领 | — | 08-30 |
| 704 | partial 不在本判据范围 | CC | 输入 | 产出 | [S:partial][D:机] 🔄 在办 | — | 08-30 |

## 二、占位
"""


def test_backfill_candidate_open_row_with_marker_is_listed():
    ids = {c.row_id for c in list_assigned_backfill_candidates(_BACKFILL_SAMPLE)}
    assert ids == {"701"}


def test_backfill_candidate_already_assigned_row_is_not_listed():
    ids = {c.row_id for c in list_assigned_backfill_candidates(_BACKFILL_SAMPLE)}
    assert "702" not in ids


def test_backfill_candidate_without_marker_is_not_listed():
    """design D4：🔄 只是"必是候选"的充分条件，不是"排除非候选"的
    充要判据——本函数不会把没有该形状的行当成候选，也不代为穷举其余
    真正在办但没写 🔄 的行（那些由人补充）。"""
    ids = {c.row_id for c in list_assigned_backfill_candidates(_BACKFILL_SAMPLE)}
    assert "703" not in ids


def test_backfill_candidate_excludes_non_open_status():
    ids = {c.row_id for c in list_assigned_backfill_candidates(_BACKFILL_SAMPLE)}
    assert "704" not in ids


def test_backfill_candidate_carries_domain_and_summary():
    candidates = {c.row_id: c for c in list_assigned_backfill_candidates(_BACKFILL_SAMPLE)}
    cand = candidates["701"]
    assert isinstance(cand, AssignedBackfillCandidate)
    assert cand.domain == "机"
    assert cand.summary == "在办未打 A，正文起首为 🔄"


def test_backfill_candidates_from_repo_scans_both_physical_files(tmp_path: Path):
    """同 `build_pool_items_from_repo` 缺口一同款教训——不为新功能重犯
    "只跟一份物理队列文件"的坑。"""
    _write_dual_queue(tmp_path, _BACKFILL_SAMPLE, _BUSINESS_BACKFILL_SAMPLE)
    ids = {c.row_id for c in list_assigned_backfill_candidates_from_repo(tmp_path)}
    assert ids == {"701", "801"}


_BUSINESS_BACKFILL_SAMPLE = """\
## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 801 | 业务场景域同样应被扫到 | 待领 | 输入 | 产出 | [S:open][D:业] 🔄 **在办** | — | 08-30 |

## 二、占位
"""


# ── discover_opener_files / build_pool_items（真实文件系统集成）───────────


def _make_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    opener_dir = repo_root / "1-转型规划" / "0-全景路线图"
    opener_dir.mkdir(parents=True)
    return repo_root


def test_discover_opener_files_matches_three_naming_conventions(tmp_path: Path):
    repo_root = _make_repo(tmp_path)
    opener_dir = repo_root / "1-转型规划" / "0-全景路线图"
    (opener_dir / "派单件-X-2026-08-09.md").write_text("引用 #82", encoding="utf-8")
    (opener_dir / "开场prompt-Y-2026-08-09.md").write_text("引用 #98", encoding="utf-8")
    (opener_dir / "本周计划-2026-08-10.md").write_text("A7 #312", encoding="utf-8")
    (opener_dir / "不相关文档-Z.md").write_text("与 opener 无关", encoding="utf-8")

    files = discover_opener_files(repo_root)
    names = {p.name for p in files}
    assert names == {
        "派单件-X-2026-08-09.md", "开场prompt-Y-2026-08-09.md", "本周计划-2026-08-10.md",
    }


def test_discover_opener_files_missing_dir_returns_empty(tmp_path: Path):
    assert discover_opener_files(tmp_path / "不存在的仓库") == []


def test_build_pool_items_marks_opener_path_when_referenced(tmp_path: Path):
    repo_root = _make_repo(tmp_path)
    opener_dir = repo_root / "1-转型规划" / "0-全景路线图"
    (opener_dir / "本周计划-2026-08-10.md").write_text("A7 处理 #82，复制即用。", encoding="utf-8")

    items = {i.row_id: i for i in build_pool_items(SECTION_ONE_SAMPLE, repo_root)}
    assert set(items) == {"82", "98", "315"}
    expected_rel = str(Path("1-转型规划") / "0-全景路线图" / "本周计划-2026-08-10.md")
    assert items["82"].opener_path == expected_rel
    assert items["98"].opener_path is None
    assert items["315"].opener_path is None


def test_build_pool_items_empty_pool_returns_empty_without_scanning(tmp_path: Path):
    repo_root = _make_repo(tmp_path)
    no_open_rows = (
        "## 一、任务看板\n\n"
        "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
        "|---|------|--------|-------------|----------|------|--------|------|\n"
        "| 1 | 已完成 | CC | 输入 | 产出 | [S:done][D:机] ✅ | — | 07-30 |\n"
    )
    assert build_pool_items(no_open_rows, repo_root) == []


# ── 指纹去重：compute_new_ids / new_known_state ─────────────────────────────


def _items(*row_ids: str) -> list[OpenPoolItem]:
    return [OpenPoolItem(row_id=rid, domain="机", summary="s", opener_path=None) for rid in row_ids]


def test_compute_new_ids_pool_zero_to_nonzero_all_new():
    new_ids = compute_new_ids(_items("82", "98"), default_state())
    assert new_ids == {"82", "98"}


def test_compute_new_ids_unchanged_set_is_silent():
    state = {"known_open_ids": ["82", "98"]}
    new_ids = compute_new_ids(_items("82", "98"), state)
    assert new_ids == set()


def test_compute_new_ids_new_row_appears_only_that_one_flagged():
    state = {"known_open_ids": ["82"]}
    new_ids = compute_new_ids(_items("82", "315"), state)
    assert new_ids == {"315"}


def test_compute_new_ids_pool_shrinking_triggers_nothing():
    """池子缩小（行被领走）不应触发推送——那是好消息，不是"有事需要你
    开工"（队列 #147「狼来了」红线：绝不做"存在即提醒"）。"""
    state = {"known_open_ids": ["82", "98"]}
    new_ids = compute_new_ids(_items("82"), state)
    assert new_ids == set()


def test_new_known_state_replaces_not_unions_so_reappearance_counts_as_new():
    # 第一轮：82/98 出现，全部视为新。
    state = default_state()
    round1_items = _items("82", "98")
    new1 = compute_new_ids(round1_items, state)
    assert new1 == {"82", "98"}
    state = new_known_state(round1_items)

    # 第二轮：98 离开池子（被领走/转 partial）。
    round2_items = _items("82")
    new2 = compute_new_ids(round2_items, state)
    assert new2 == set()
    state = new_known_state(round2_items)
    assert state == {"known_open_ids": ["82"]}

    # 第三轮：98 重新回到 open——应再次被当"新出现"提醒一次。
    round3_items = _items("82", "98")
    new3 = compute_new_ids(round3_items, state)
    assert new3 == {"98"}


def test_state_round_trip_via_save_and_load(tmp_path: Path):
    """队列 #312 缺口二：状态 schema 由单键扩为双键，`load_state` 恒返回
    补齐后的完整形状（写入时缺的键按默认值补，见 `default_state`）——这是
    "旧状态文件平滑升级"这条契约的另一面，故本用例断言的是补齐后的结果，
    不是"写进去什么就读出什么"。"""
    path = tmp_path / "state.json"
    save_state(path, {"known_open_ids": ["82", "98"]})
    assert load_state(path) == {"known_open_ids": ["82", "98"], "stale_notified_at": {}}


def test_state_round_trip_preserves_stale_notified_at(tmp_path: Path):
    path = tmp_path / "state.json"
    state = {"known_open_ids": ["82"], "stale_notified_at": {"82": "2026-08-19T12:00:00+00:00"}}
    save_state(path, state)
    assert load_state(path) == state


def test_load_state_missing_file_returns_default(tmp_path: Path):
    assert load_state(tmp_path / "不存在.json") == default_state()


# ── format_pool_reminder_message ────────────────────────────────────────────


def test_format_message_none_when_no_new_ids():
    items = _items("82")
    assert format_pool_reminder_message(items, set()) is None


def test_format_message_includes_opener_path_action_text():
    items = [OpenPoolItem(row_id="82", domain="业", summary="真可开工", opener_path="本周计划-2026-08-10.md")]
    text = format_pool_reminder_message(items, {"82"})
    assert text is not None
    assert "#82" in text
    assert "opener 在 `本周计划-2026-08-10.md`" in text
    assert "复制即用" in text


def test_format_message_includes_pending_opener_notice_when_missing():
    items = [OpenPoolItem(row_id="315", domain=None, summary="域字段缺失仍算可开工", opener_path=None)]
    text = format_pool_reminder_message(items, {"315"})
    assert text is not None
    assert "尚未出 opener" in text
    assert "[域未标注]" in text


def test_format_message_only_lists_items_in_new_ids():
    items = [
        OpenPoolItem(row_id="82", domain="业", summary="旧的，已提醒过", opener_path=None),
        OpenPoolItem(row_id="315", domain="机", summary="新出现", opener_path=None),
    ]
    text = format_pool_reminder_message(items, {"315"})
    assert text is not None
    assert "#315" in text
    assert "#82" not in text


# ── send_open_pool_reminder：主通道/兜底（形状仿 send_decision_reminder）───


class _FakeConnector:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[tuple[str, str]] = []

    async def send_markdown(self, recipient: str, text: str) -> None:
        self.calls.append((recipient, text))
        if self.should_fail:
            raise RuntimeError("WebSocket not connected, unable to send data")


def _actions(audit: AuditLogger) -> list[str]:
    return [r["action"] for r in audit.query_by(scenario="wecom-aibot")]


def test_send_open_pool_reminder_primary_success_records_sent(tmp_path: Path):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = _FakeConnector(should_fail=False)

    asyncio.run(send_open_pool_reminder(connector, audit, "🔔 可 Open 池新增 1 条", "ShaoPeiShen"))

    assert connector.calls == [("ShaoPeiShen", "🔔 可 Open 池新增 1 条")]
    assert _actions(audit) == ["open_pool_reminder_sent"]


def test_send_open_pool_reminder_falls_back_to_webhook_on_primary_failure(tmp_path: Path):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = _FakeConnector(should_fail=True)
    fallback_calls: list[str] = []

    asyncio.run(send_open_pool_reminder(
        connector, audit, "🔔 可 Open 池新增 1 条", "ShaoPeiShen",
        fallback_send=fallback_calls.append,
    ))

    assert fallback_calls == ["🔔 可 Open 池新增 1 条"]
    assert _actions(audit) == ["open_pool_reminder_send_failed", "open_pool_reminder_fallback_sent"]


def test_send_open_pool_reminder_fallback_failure_does_not_raise(tmp_path: Path):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = _FakeConnector(should_fail=True)

    def failing_fallback(text: str) -> None:
        raise RuntimeError("webhook 也挂了")

    asyncio.run(send_open_pool_reminder(
        connector, audit, "🔔 可 Open 池新增 1 条", "ShaoPeiShen", fallback_send=failing_fallback,
    ))

    assert _actions(audit) == ["open_pool_reminder_send_failed", "open_pool_reminder_fallback_failed"]


def test_send_open_pool_reminder_no_fallback_configured_only_logs_failure(tmp_path: Path):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = _FakeConnector(should_fail=True)

    asyncio.run(send_open_pool_reminder(
        connector, audit, "🔔 可 Open 池新增 1 条", "ShaoPeiShen", fallback_send=None,
    ))

    assert _actions(audit) == ["open_pool_reminder_send_failed"]


# ══════════════════════════════════════════════════════════════════════════
# 队列 #312 缺口一 · 双文件取数（2026-08-19 零时巡检查清）
# ══════════════════════════════════════════════════════════════════════════

_BUSINESS_SAMPLE = """\
## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 334 | 保供看板新增物料看板视图 | 待领 | 输入 | 产出 | [S:open][D:业] 待领（P2） | — | 08-17 |
| 344 | 齐料日期口径 | 待领 | 输入 | 产出 | [S:blocked][D:业] 等回件 | — | 08-18 |

## 二、占位
"""


def _write_dual_queue(repo_root: Path, mechanism, business) -> None:
    """按 `queue_table.iter_queue_paths()` 的真实相对路径落两份物理队列文件
    （不硬编码路径字面量——那正是本轮要修的"下游各自记一份路径"形态）。"""
    from zhuopin_platform.shared_tools.queue_table import iter_queue_paths

    mech_rel, biz_rel = iter_queue_paths()
    for rel, text in ((mech_rel, mechanism), (biz_rel, business)):
        if text is None:
            continue
        path = repo_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def test_business_file_open_rows_enter_pool(tmp_path: Path):
    """缺口一的直接回归：业务场景文件里的 open 行必须进池。

    修复前生产实测 known_open_ids ＝ ["240","337","338","341","98"] 五个
    全是机制环境行，采购 #334 一个都不在——本用例即那个事实的可执行形式。
    """
    _write_dual_queue(tmp_path, SECTION_ONE_SAMPLE, _BUSINESS_SAMPLE)
    items = build_pool_items_from_repo(tmp_path)
    assert "334" in {i.row_id for i in items}


def test_dual_files_merged_into_one_pool(tmp_path: Path):
    _write_dual_queue(tmp_path, SECTION_ONE_SAMPLE, _BUSINESS_SAMPLE)
    ids = {i.row_id for i in build_pool_items_from_repo(tmp_path)}
    # 机制环境三条（82/98/315）＋ 业务场景一条（334）；另一条业务行是
    # blocked，结构性排除。
    assert ids == {"82", "98", "315", "334"}


def test_pool_items_carry_source_queue_file(tmp_path: Path):
    """陈化催办要去"该行所在的那份文件"上查 git 历史，故来源须随行携带。"""
    from zhuopin_platform.shared_tools.queue_table import iter_queue_paths

    mech_rel, biz_rel = iter_queue_paths()
    _write_dual_queue(tmp_path, SECTION_ONE_SAMPLE, _BUSINESS_SAMPLE)
    by_id = {i.row_id: i for i in build_pool_items_from_repo(tmp_path)}
    assert by_id["98"].queue_rel == mech_rel
    assert by_id["334"].queue_rel == biz_rel


def test_missing_one_queue_file_warns_and_keeps_the_other(tmp_path: Path):
    """一份缺失时不得静默把残缺结果当作完整的池——那正是缺口一的形态。"""
    _write_dual_queue(tmp_path, SECTION_ONE_SAMPLE, None)  # 业务场景那份不落盘
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        items = build_pool_items_from_repo(tmp_path)
    assert any(issubclass(w.category, RuntimeWarning) for w in caught)
    assert {i.row_id for i in items} == {"82", "98", "315"}


def test_concatenating_texts_would_silently_drop_second_section_one(tmp_path: Path):
    """锁死"逐份解析后合并"这个选择，不是"拼接文本后解析一次"。

    _parse_table_rows 用 text.find(heading) 只取**第一个** `## 一、`
    ⇒ 拼接后第二份的 §一 会被静默丢弃，症状与缺口一一模一样且更难发现。
    本用例把这个陷阱固化成断言，防止后来者"顺手简化"成拼接。
    """
    concatenated = SECTION_ONE_SAMPLE + "\n" + _BUSINESS_SAMPLE
    assert "334" not in {r.row_id for r in parse_open_pool_rows(concatenated)}

    _write_dual_queue(tmp_path, SECTION_ONE_SAMPLE, _BUSINESS_SAMPLE)
    assert "334" in {i.row_id for i in build_pool_items_from_repo(tmp_path)}


# ══════════════════════════════════════════════════════════════════════════
# 队列 #312 缺口二 · 陈化催办
# ══════════════════════════════════════════════════════════════════════════

_NOW = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)


def _item(row_id: str, opener=None) -> OpenPoolItem:
    return OpenPoolItem(
        row_id=row_id, domain="机", summary=f"任务 {row_id}",
        opener_path=opener, queue_rel="1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md",
    )


def _touched(days_ago):
    def _fn(item: OpenPoolItem):
        if item.row_id not in days_ago:
            return None
        return _NOW - timedelta(days=days_ago[item.row_id])
    return _fn


def test_stale_row_beyond_threshold_is_flagged():
    cands, degraded = compute_stale_candidates(
        [_item("334")], default_state(), _NOW, touched_at=_touched({"334": 9}),
    )
    assert [c.item.row_id for c in cands] == ["334"]
    assert cands[0].idle_days == 9
    assert degraded == []


def test_fresh_row_within_threshold_is_silent():
    """#334 在 2026-08-19 实测末次触碰 08-17（2 天）——本用例即那个真实取值
    的形状：缺口一修好后它靠「新增即推」被推出来，而不是靠陈化催办。"""
    cands, _ = compute_stale_candidates(
        [_item("334")], default_state(), _NOW, touched_at=_touched({"334": 2}),
    )
    assert cands == []


def test_stale_row_already_notified_within_interval_is_silent():
    state = default_state()
    state["stale_notified_at"] = {"334": (_NOW - timedelta(days=3)).isoformat()}
    cands, _ = compute_stale_candidates(
        [_item("334")], state, _NOW, touched_at=_touched({"334": 30}),
    )
    assert cands == []


def test_stale_row_renotified_after_interval():
    state = default_state()
    state["stale_notified_at"] = {"334": (_NOW - timedelta(days=8)).isoformat()}
    cands, _ = compute_stale_candidates(
        [_item("334")], state, _NOW, touched_at=_touched({"334": 30}),
    )
    assert [c.item.row_id for c in cands] == ["334"]


def test_unknown_touch_time_is_conservative_and_not_silent():
    """取不到 git 时间 ⇒ 视为"刚触碰、不催"，且必须留下可见记录。

    反过来把 None 当"很久没动"，会让每一条新行在下一次运行时立刻被催，
    等于把机制退化成定夺 1 里已被否决的 (c)「池非空就推」。
    """
    cands, degraded = compute_stale_candidates(
        [_item("999")], default_state(), _NOW, touched_at=_touched({}),
    )
    assert cands == []
    assert len(degraded) == 1 and "999" in degraded[0]


def test_naive_now_raises_rather_than_silently_not_nudging():
    """时间基准不一致必须炸出来，不得被兜成"不催"（根 CLAUDE.md 时间戳硬规则）。"""
    import pytest

    with pytest.raises(TypeError):
        compute_stale_candidates(
            [_item("334")], default_state(), datetime(2026, 8, 19, 12, 0),
            touched_at=_touched({"334": 30}),
        )


def test_stale_state_pruned_when_row_leaves_pool():
    state = default_state()
    state["stale_notified_at"] = {"334": _NOW.isoformat(), "341": _NOW.isoformat()}
    kept = new_stale_state([_item("334")], state, set(), _NOW)
    assert kept == {"334": _NOW.isoformat()}


def test_reentering_row_restarts_from_new_touch_point():
    """行离开池后又转回 open，不得带着旧催办记录立刻被催——记录已被裁剪，
    此后按新的末次触碰时间重新起算。"""
    state = default_state()
    state["stale_notified_at"] = {"334": (_NOW - timedelta(days=90)).isoformat()}
    pruned = new_stale_state([], state, set(), _NOW)  # 离开池那一轮
    assert pruned == {}
    state["stale_notified_at"] = pruned
    cands, _ = compute_stale_candidates(
        [_item("334")], state, _NOW, touched_at=_touched({"334": 1}),
    )
    assert cands == []


def test_new_stale_state_stamps_only_actually_notified_rows():
    kept = new_stale_state([_item("334"), _item("341")], default_state(), {"334"}, _NOW)
    assert kept == {"334": _NOW.isoformat()}


def test_legacy_state_file_without_stale_key_loads_clean(tmp_path: Path):
    path = tmp_path / "state.json"
    path.write_text('{"known_open_ids": ["98"]}', encoding="utf-8")
    state = load_state(path)
    assert state["known_open_ids"] == ["98"]
    assert state["stale_notified_at"] == {}


def test_stale_state_wrong_type_is_reset_not_crash(tmp_path: Path):
    path = tmp_path / "state.json"
    path.write_text('{"known_open_ids": [], "stale_notified_at": ["oops"]}', encoding="utf-8")
    assert load_state(path)["stale_notified_at"] == {}


def test_stale_message_carries_next_action_and_idle_days():
    msg = format_stale_reminder_message([
        StaleCandidate(item=_item("334", "1-转型规划/0-全景路线图/opener集-x.md"), idle_days=9),
        StaleCandidate(item=_item("341"), idle_days=12),
    ])
    assert "陈化催办 2 条" in msg
    assert "已滞留 12 天" in msg and "已滞留 9 天" in msg
    assert "opener集-x.md" in msg
    assert "尚未出 opener" in msg
    # 滞留最久的排最前——他要先看到压得最久的那条。
    assert msg.index("#341") < msg.index("#334")


def test_stale_message_none_when_no_candidates():
    assert format_stale_reminder_message([]) is None


def test_new_and_stale_fingerprints_do_not_shadow_each_other():
    """两条判据分别计指纹（派单件明写"不要互相覆盖"）：一条行已被「新增
    即推」提醒过（进了 known_open_ids）之后，仍能独立地被陈化催办命中。"""
    items = [_item("341")]
    state = {"known_open_ids": ["341"], "stale_notified_at": {}}
    assert compute_new_ids(items, state) == set()
    cands, _ = compute_stale_candidates(
        items, state, _NOW, touched_at=_touched({"341": 20}),
    )
    assert [c.item.row_id for c in cands] == ["341"]


def test_stale_reminder_uses_distinct_audit_action(tmp_path: Path):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    connector = _FakeConnector(should_fail=False)
    asyncio.run(send_open_pool_reminder(
        connector, audit, "⏳ 陈化催办", "ShaoPeiShen",
        action_prefix="open_pool_stale_reminder",
    ))
    assert _actions(audit) == ["open_pool_stale_reminder_sent"]
