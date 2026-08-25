"""队列 #399（followup-supplement-channel）：README 表格按章节标题显式选表。

🔴 **本文件的核心不是「新实现能选对表」，而是「这条判据不是空转」。**

design 决策点 3 答 (a)+(b)，其中 (a) 半明写：反例测试**须能对退休前的原实现
变红，否则是空转**（同队列 §一 #355 那条教训——防回归判据的初版自己红了，
红得对）。故本文件把反例判据本身抽成一个接受「实现」为入参的函数
`assert_main_table_unaffected_by_table_order`，然后：

- `test_反例对新实现变绿` —— 喂新实现，必须通过；
- `test_反例对改判前的原实现变红` —— 喂逐字照搬的原实现，**必须 AssertionError**。

两条一起才构成变异验证。只写前者的话，一条永远为真的断言也能"通过"。

⚠️ CI 整体 run 长期 failure（队列 §一 #398 ⑶）⇒ 本文件的红绿信号可能淹没在
既有的红里，故本包 apply 时**在本地实跑取证**，不以 CI 绿为准。
"""
from __future__ import annotations

import pytest

from aibot_service.readme_table import (
    MAIN_TABLE_SECTION,
    SUPPLEMENT_TABLE_SECTION,
    ReadmeTableError,
    RowLocation,
    iter_rows,
    section_span,
)

_MAIN_BLOCK = """\
## 现有跟进信清单

| 编号 | 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |
|------|------|--------|---------|---------|---------|
| 财务部#15 | 2026-08-23 | 财务部 · 唐燕萍 | FI2 面板复核 | 尽快 | ✅ 已推送 2026-08-23 08:26 UTC |
| 采购部#18 | 2026-08-24 | 采购部 · 姚祖怡 | 判例批改表 | 8 月内 | 🆕 待发 |
"""

_SUPPLEMENT_BLOCK = """\
## 补件登记（不占编号、不占串行闸，2026-08-24 立表）

| 承接编号 | 日期 | 收信人 | 主要事项 | 需回复 | 发送状态 |
|---------|------|--------|---------|--------|---------|
| 财务部#15 | 2026-08-25 | 财务部 · 唐燕萍 | 面板已修复可采信 ＋ R5 分母请签认 | 是 | ✅ 已推送 2026-08-25 |
"""

MAIN_FIRST = _MAIN_BLOCK + "\n" + _SUPPLEMENT_BLOCK
# 🔴 反例：一次**纯排版编辑**——只调了两节的先后，一个字都没改。
SUPPLEMENT_FIRST = _SUPPLEMENT_BLOCK + "\n" + _MAIN_BLOCK


def legacy_iter_rows(text: str, section: str | None = None) -> list[RowLocation]:
    """改判**前**的原实现，逐字照搬（`section` 入参收下即弃——原实现根本没有
    「读哪张表」这个概念，这正是问题所在）。

    判据＝「文件里第一个以 `|` 开头且含『发送状态』的行就是表头」。它当时
    正确，**只因为补件表恰好排在主表后面**。
    """
    lines = text.splitlines()
    header_idx = None
    header_cells: list[str] = []
    status_col_index = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("|") and "发送状态" in line:
            header_cells = [c.strip() for c in line.strip().strip("|").split("|")]
            for j, cell in enumerate(header_cells):
                if cell.startswith("发送状态"):
                    status_col_index = j
                    break
            header_idx = i
            break
    if header_idx is None or status_col_index < 0:
        raise ReadmeTableError('未找到含"发送状态"列的表格')
    rows: list[RowLocation] = []
    for i in range(header_idx + 2, len(lines)):
        line = lines[i]
        if not line.strip().startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) <= status_col_index:
            continue
        rows.append(RowLocation(i, cells, status_col_index, header_cells))
    return rows


def assert_main_table_unaffected_by_table_order(rows_of) -> None:
    """反例判据本体：**把补件表挪到主表之前，主表消费者读到的东西必须逐字
    不变**（或 fail-loud），MUST NOT 静默读成另一张表。

    `rows_of(text, section)` 是被测实现。断言写成「前后逐字相等」而不是
    「读到了主表」——后者会诱使实现去猜，前者只认可观测的等价。
    """
    before = rows_of(MAIN_FIRST, MAIN_TABLE_SECTION)
    after = rows_of(SUPPLEMENT_FIRST, MAIN_TABLE_SECTION)
    assert [r.cells for r in before] == [r.cells for r in after], (
        "两表次序颠倒后主表消费者读到的数据行变了 —— 说明实现仍在依赖"
        "「谁排在文件前面」这条隐式判据"
    )
    assert [r.header_cells for r in before] == [r.header_cells for r in after]
    assert all(r.header_cells[0] == "编号" for r in after), (
        "读到的表头首列不是「编号」——补件表首列叫「承接编号」，这说明读串了表"
    )


def test_反例对新实现变绿():
    assert_main_table_unaffected_by_table_order(iter_rows)


def test_反例对改判前的原实现变红():
    """🔴 变异验证：不能对原实现变红的测试是空转，不计入本要求的满足。"""
    with pytest.raises(AssertionError):
        assert_main_table_unaffected_by_table_order(legacy_iter_rows)


def test_原实现在补件表排前时确实读成了主表且不报错():
    """把「它错在哪」也钉住——不只是「不等于」，而是**具体错成了补件表，
    且全程没有任何异常/告警**。这一条是 design §〇⑶ 那句实测的回归锁。"""
    rows = legacy_iter_rows(SUPPLEMENT_FIRST)
    assert rows[0].header_cells[0] == "承接编号"
    assert len(rows) == 1


# ---------------------------------------------------------------- 选表本身

def test_不传_section_时取主表而非文件里第一个表():
    rows = iter_rows(SUPPLEMENT_FIRST)
    assert rows[0].header_cells[0] == "编号"
    assert len(rows) == 2


def test_显式取补件表():
    rows = iter_rows(MAIN_FIRST, SUPPLEMENT_TABLE_SECTION)
    assert len(rows) == 1
    assert rows[0].header_cells[0] == "承接编号"
    assert rows[0].cells[4] == "是"


def test_章节标题缺失时_fail_loud_而不是回落到另一张表():
    with pytest.raises(ReadmeTableError) as exc:
        iter_rows(_SUPPLEMENT_BLOCK)  # 只有补件表，没有主表章节
    assert MAIN_TABLE_SECTION in str(exc.value)


def test_章节标题缺失时_不得返回空列表当作没有数据():
    """空列表与「这张表真的一行都没有」在调用方眼里逐字相同——#399 当初能藏
    住整整一天，正是因为班次把「读不到」显示成了「今天没活」。"""
    with pytest.raises(ReadmeTableError):
        iter_rows(_MAIN_BLOCK, SUPPLEMENT_TABLE_SECTION)


def test_章节内无发送状态表时同样报错():
    text = "## 现有跟进信清单\n\n只有一段散文，没有表格。\n\n## 下一节\n"
    with pytest.raises(ReadmeTableError):
        iter_rows(text)


def test_三级标题不构成章节边界():
    """补件表下方逐封正文用的是 `### 财务部 · 唐燕萍 ——…`，它必须留在补件
    章节内，否则补件表会被切掉一半。"""
    text = _MAIN_BLOCK + "\n" + _SUPPLEMENT_BLOCK + "\n### 财务部 · 唐燕萍 —— 逐封正文\n\n正文若干。\n"
    lines = text.splitlines()
    start, end = section_span(lines, SUPPLEMENT_TABLE_SECTION)
    assert end == len(lines), "三级标题被误当成了章节边界"
    assert len(iter_rows(text, SUPPLEMENT_TABLE_SECTION)) == 1


def test_章节标题带括注仍可按前缀匹配():
    """真身标题是 `## 补件登记（不占编号、不占串行闸，2026-08-24 立表）`。"""
    assert len(iter_rows(MAIN_FIRST, "补件登记")) == 1
