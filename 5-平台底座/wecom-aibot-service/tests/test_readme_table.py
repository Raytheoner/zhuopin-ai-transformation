import pytest

from aibot_service.readme_table import locate_row, write_status, ReadmeTableError

SAMPLE = """\
## 现有跟进信清单

| 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |
|------|--------|---------|---------|---------|
| 2026-07-04 | 质量部 · 陈忱 | 产品类样本 | 尽量 7/15 前 | ✅ 已发 |
| 2026-07-06 | 质量部 · 陈忱 | 8D 预填校准会议程 | 校准会 7 月内 | 🆕 待发 |
| 2026-07-09 | 采购部 · 姚祖怡 | 整合信 | 8月初 | 🆕 待发 |

## 下一节
"""


def test_locate_row_finds_status_column():
    loc = locate_row(SAMPLE, lambda cells: "8D 预填校准会议程" in cells[2])
    assert loc.status_col_index == 4
    assert loc.cells[0] == "2026-07-06"
    assert loc.cells[4] == "🆕 待发"


def test_locate_row_raises_when_no_match():
    with pytest.raises(ReadmeTableError):
        locate_row(SAMPLE, lambda cells: "不存在的事项" in cells[2])


def test_locate_row_disambiguates_multiple_pending_rows():
    loc = locate_row(SAMPLE, lambda cells: "姚祖怡" in cells[1] and "整合信" in cells[2])
    assert loc.cells[0] == "2026-07-09"


def test_write_status_replaces_only_target_row():
    loc = locate_row(SAMPLE, lambda cells: "8D 预填校准会议程" in cells[2])
    new_text = write_status(SAMPLE, loc, "✅ 已推送 2026-07-11 10:00 UTC")

    lines = new_text.splitlines()
    assert "✅ 已推送 2026-07-11 10:00 UTC" in lines[loc.line_index]
    # 其他行不受影响
    assert "✅ 已发" in new_text
    assert "🆕 待发" in new_text  # 姚祖怡那行仍是待发
    reparsed = locate_row(new_text, lambda cells: "姚祖怡" in cells[1])
    assert reparsed.cells[4] == "🆕 待发"


def test_write_status_preserves_trailing_content():
    loc = locate_row(SAMPLE, lambda cells: "整合信" in cells[2])
    new_text = write_status(SAMPLE, loc, "✅ 已推送 X")
    assert "## 下一节" in new_text
