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
from pathlib import Path

from zhuopin_platform.audit import AuditLogger

from aibot_service.open_pool_reminder import (
    OpenPoolItem,
    build_pool_items,
    compute_new_ids,
    default_state,
    discover_opener_files,
    find_opener_path,
    format_pool_reminder_message,
    load_state,
    new_known_state,
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
    index = [(Path("派单件-X.md"), {82, 315})]
    assert find_opener_path("82", index) == Path("派单件-X.md")


def test_find_opener_path_substring_false_positive_avoided():
    """队列 #302 同款教训：正文含 `#220` 不应让 row_id="22" 被误判命中——
    `_ROW_NUMBER_RE` 按完整数字游程提取，220 != 22。"""
    index = [(Path("本周计划-X.md"), {220, 221})]
    assert find_opener_path("22", index) is None


def test_find_opener_path_no_match_returns_none():
    index = [(Path("派单件-X.md"), {1, 2, 3})]
    assert find_opener_path("999", index) is None


def test_find_opener_path_non_digit_row_id_returns_none():
    index = [(Path("派单件-X.md"), {1, 2, 3})]
    assert find_opener_path("205-A", index) is None


def test_find_opener_path_returns_first_index_match():
    index = [
        (Path("开场prompt-A.md"), {1}),
        (Path("本周计划-B.md"), {1, 2}),
    ]
    assert find_opener_path("1", index) == Path("开场prompt-A.md")


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
    path = tmp_path / "state.json"
    save_state(path, {"known_open_ids": ["82", "98"]})
    assert load_state(path) == {"known_open_ids": ["82", "98"]}


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
