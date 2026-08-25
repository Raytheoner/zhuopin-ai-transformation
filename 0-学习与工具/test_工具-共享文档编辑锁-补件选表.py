"""队列 #399（followup-supplement-channel）：**第二份**独立 README 解析实现
的显式选表 ＋ 变异验证。

🔴 两份实现（`aibot_service.readme_table` 与本工具的 `_followup_readme_rows`）
改判前**同时**依赖着一条从未被任何人声明的判据——「文件里第一个以 `|` 开头
且含『发送状态』的行就是主表表头」。它当时正确，**只因为补件表恰好排在主表
后面**：把补件表挪到主表之前（一次纯排版编辑），两份会**同时**开始把补件表
读成主表，**且都不报错**。

**只改一份 ＝ 只修了一半，而修了的那一半会让人以为整件事已经修完了**
（§四 #119 决策点 2 红字）。故服务侧那份有的反例与变异验证，本份也必须各有
一条、且判据同形——本文件与
`5-平台底座/wecom-aibot-service/tests/test_readme_table_section_selection.py`
是刻意成对的。
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "工具-共享文档编辑锁.py"


def _load_module():
    """白盒 import 脚本本体（文件名含连字符/中文，不能直接 `import`）。"""
    spec = importlib.util.spec_from_file_location("_edit_lock_section_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MAIN_BLOCK = """\
## 现有跟进信清单

| 编号 | 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |
|------|------|--------|---------|---------|---------|
| 财务部#15 | 2026-08-23 | 财务部 · 唐燕萍 | FI2 面板复核 | 尽快 | ✅ 已推送 |
| 采购部#18 | 2026-08-24 | 采购部 · 姚祖怡 | 判例批改表 | 8 月内 | 🆕 待发 |
"""

SUPPLEMENT_BLOCK = """\
## 补件登记（不占编号、不占串行闸，2026-08-24 立表）

| 承接编号 | 日期 | 收信人 | 主要事项 | 需回复 | 发送状态 |
|---------|------|--------|---------|--------|---------|
| 财务部#15 | 2026-08-25 | 财务部 · 唐燕萍 | 面板已修复可采信 | 是 | ✅ 已推送 2026-08-25 |
"""

MAIN_FIRST = MAIN_BLOCK + "\n" + SUPPLEMENT_BLOCK
# 🔴 反例：一次**纯排版编辑**——一个字都没改，只调了两节的先后。
SUPPLEMENT_FIRST = SUPPLEMENT_BLOCK + "\n" + MAIN_BLOCK


def legacy_followup_readme_rows(text, section=None):
    """改判**前**的原实现，逐字照搬（`section` 收下即弃——原实现根本没有
    「读哪张表」这个概念，这正是问题所在；找不到时返回空列表，也照搬）。"""
    lines = text.splitlines()
    header_idx = None
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
        return []
    rows = []
    for i in range(header_idx + 2, len(lines)):
        line = lines[i]
        if not line.strip().startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) <= status_col_index:
            continue
        rows.append((line, cells, status_col_index))
    return rows


class SectionSelectionTests(unittest.TestCase):
    def setUp(self):
        self.module = _load_module()

    def _assert_main_rows_unaffected_by_table_order(self, rows_of):
        """反例判据本体——与服务侧 `assert_main_table_unaffected_by_table_
        order` 同形：两表次序颠倒后，主表消费者读到的数据行必须逐字不变。

        判据写成「前后逐字相等」而不是「读到了主表」——后者会诱使实现去猜，
        前者只认可观测的等价。
        """
        before = [cells for _, cells, _ in rows_of(MAIN_FIRST)]
        after = [cells for _, cells, _ in rows_of(SUPPLEMENT_FIRST)]
        self.assertEqual(
            before, after,
            "两表次序颠倒后读到的主表行变了 —— 说明实现仍在依赖「谁排在文件前面」",
        )
        self.assertEqual([c[0] for c in after], ["财务部#15", "采购部#18"])

    # ------------------------------------------------------- 变异验证（成对）

    def test_反例对新实现变绿(self):
        self._assert_main_rows_unaffected_by_table_order(
            self.module._followup_readme_rows)

    def test_反例对改判前的原实现变红(self):
        """🔴 **不能对原实现变红的测试是空转，不计入本要求的满足**
        （design 决策点 3(a)，同队列 §一 #355 那条教训）。"""
        with self.assertRaises(AssertionError):
            self._assert_main_rows_unaffected_by_table_order(
                legacy_followup_readme_rows)

    def test_原实现在补件表排前时读成了补件表且不报错(self):
        """把「它错在哪」也钉住——不只是「不相等」，而是**具体错成了补件表，
        且全程无异常无告警**。这是 design §〇⑶ 那句实测的回归锁。"""
        rows = legacy_followup_readme_rows(SUPPLEMENT_FIRST)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1][4], "是", "读到的是补件表的「需回复」列")

    # ----------------------------------------------------------- 选表本身

    def test_不传_section_取主表而非文件里第一个表(self):
        rows = self.module._followup_readme_rows(SUPPLEMENT_FIRST)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][1][0], "财务部#15")

    def test_显式取补件表(self):
        rows = self.module._followup_readme_rows(
            MAIN_FIRST, self.module.FOLLOWUP_SUPPLEMENT_TABLE_SECTION)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1][4], "是")

    def test_章节缺失时抛错而不是返回空列表(self):
        """空列表与「这张表真的一行都没有」在调用方眼里逐字相同——#399 当初
        能藏住整整一天，正是因为班次把「读不到」显示成了「今天没活」。"""
        with self.assertRaises(self.module.FollowupReadmeSectionError):
            self.module._followup_readme_rows(SUPPLEMENT_BLOCK)

    def test_章节内无发送状态表时同样抛错(self):
        with self.assertRaises(self.module.FollowupReadmeSectionError):
            self.module._followup_readme_rows(
                "## 现有跟进信清单\n\n只有散文没有表格。\n\n## 下一节\n")

    def test_三级标题不构成章节边界(self):
        """补件表下方逐封正文用的是 `### 财务部 · 唐燕萍 ——…`，它必须留在
        补件章节内，否则补件表会被切掉一半。"""
        text = MAIN_FIRST + "\n### 财务部 · 唐燕萍 —— 逐封正文\n\n正文若干。\n"
        rows = self.module._followup_readme_rows(
            text, self.module.FOLLOWUP_SUPPLEMENT_TABLE_SECTION)
        self.assertEqual(len(rows), 1)

    # --------------------------------------------------------- 降级须出声

    def test_出声降级包装不静默(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rows = self.module._followup_readme_rows_advisory(SUPPLEMENT_BLOCK)
        self.assertEqual(rows, [])
        self.assertIn("定位失败", buf.getvalue(),
                      "降级可以不阻断队列 release，但绝不可以不出声")

    # ------------------------------------- 第三处依赖同一判据的函数（tasks 1.3）

    def test_表头列定位同批显式化(self):
        idx_main_first = self.module._followup_header_col_index(MAIN_FIRST, "收信人")
        idx_supp_first = self.module._followup_header_col_index(SUPPLEMENT_FIRST, "收信人")
        self.assertEqual(idx_main_first, idx_supp_first)
        self.assertEqual(idx_main_first, 2)

    def test_表头列定位在章节缺失时抛错(self):
        with self.assertRaises(self.module.FollowupReadmeSectionError):
            self.module._followup_header_col_index(SUPPLEMENT_BLOCK, "收信人")


if __name__ == "__main__":
    unittest.main()
