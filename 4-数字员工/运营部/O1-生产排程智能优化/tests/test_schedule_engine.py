"""测试 schedule_engine：物料到货日 + SMT 工时 → SMT 完工日。

本文件分两部分：
  一、收割保真回归网 —— 逐字迁自 supplychain `tests/test_smt_scheduling.py`，
      仅改 import 路径，其余不动（tasks 5.1）。它们与被收割实现同批写成，
      作用是证明「收割没改坏东西」。
  二、新增边界用例 —— **从 spec 反推而非从实现反推**（design D7 ②）。原测试
      与原实现同源，可能同源错误；如「不跳周末」原文只在 docstring 提了一句、
      并无对应断言，本文件补上。
"""
import warnings
from datetime import date

import pytest

from o1_smt_scheduling.schedule_engine import (
    schedule_smt,
    load_smt_lead_time,
    is_placeholder_lead_time,
)


# ══════════════════════════════════════════════════════════════════════════
# 一、收割保真回归网（迁自 supplychain，仅改 import）
# ══════════════════════════════════════════════════════════════════════════

class TestLoadSmtLeadTime:
    def test_returns_dict(self):
        lt = load_smt_lead_time()
        assert isinstance(lt, dict)

    def test_known_product_exists(self):
        lt = load_smt_lead_time()
        assert "F02N.0040" in lt

    def test_lead_days_is_int(self):
        lt = load_smt_lead_time()
        for product_id, days in lt.items():
            assert isinstance(days, int), f"{product_id} 的工时应为整数"

    def test_all_products_loaded(self):
        """SMT 工时表应包含所有 ECU + PCBA 产品（原 17 个 + FO 新增 29 个 = 46 个）。

        🔴 该断言绑死行数，正是 design D7 预警的那条：收割时在 CSV 头加了声明块，
        若声明块被 csv.DictReader 读成数据行，本断言会以看似无关的方式失败。
        """
        lt = load_smt_lead_time()
        assert len(lt) == 46


class TestScheduleSmt:
    def test_single_material_basic(self):
        """一种物料，完工日 = 到货日 + 工时"""
        arrivals = {"M001": date(2026, 6, 1)}
        lt_map = {"F02N.0040": 7}
        assert schedule_smt("F02N.0040", arrivals, lt_map) == date(2026, 6, 8)

    def test_multiple_materials_takes_latest(self):
        """多种物料，从最晚到货日起算"""
        arrivals = {
            "M001": date(2026, 6, 1),
            "M002": date(2026, 6, 10),   # 最迟
            "M003": date(2026, 5, 28),
        }
        lt_map = {"F02N.0040": 7}
        assert schedule_smt("F02N.0040", arrivals, lt_map) == date(2026, 6, 17)

    def test_empty_arrivals_returns_none(self):
        """没有任何物料到货记录 → 无法排产，返回 None"""
        assert schedule_smt("F02N.0040", {}, {"F02N.0040": 7}) is None

    def test_unknown_product_returns_none(self):
        """产品不在 SMT 工时表里 → 返回 None"""
        arrivals = {"M001": date(2026, 6, 1)}
        assert schedule_smt("F99N.9999", arrivals, {"F02N.0040": 7}) is None

    def test_zero_lead_days(self):
        """工时为 0 → 到货当天即完工（边界）"""
        arrivals = {"M001": date(2026, 6, 1)}
        assert schedule_smt("F02N.0040", arrivals, {"F02N.0040": 0}) == date(2026, 6, 1)

    def test_uses_real_lead_time_csv(self):
        """使用随附 CSV 工时表，F02N.0040 应得到合理结果"""
        lt_map = load_smt_lead_time()
        result = schedule_smt("F02N.0040", {"M001": date(2026, 6, 1)}, lt_map)
        assert result is not None
        assert result > date(2026, 6, 1)


# ══════════════════════════════════════════════════════════════════════════
# 二、新增边界用例（从 spec 反推）
# ══════════════════════════════════════════════════════════════════════════

class TestNaturalDayArithmetic:
    """spec「完工日按齐料日加工时推算」— 跨周末不顺延（tasks 5.2）。

    原测试只在模块 docstring 写了「周末跳过逻辑（不跳）」，无任何断言覆盖，
    即这条业务口径此前从未被测试锁定。
    """

    def test_spans_weekend_without_shifting(self):
        """齐料日 2026-06-05（周五）+ 3 天 → 2026-06-08（周一），按自然日直加"""
        assert date(2026, 6, 5).weekday() == 4        # 前提自检：确是周五
        result = schedule_smt("F02N.0040", {"M001": date(2026, 6, 5)}, {"F02N.0040": 3})
        assert result == date(2026, 6, 8)
        assert result.weekday() == 0                  # 落在周一，未因跨周末顺延

    def test_result_may_fall_on_weekend(self):
        """自然日口径下完工日本身可以落在周六——若哪天改为工作日口径，本用例必红"""
        result = schedule_smt("F02N.0040", {"M001": date(2026, 6, 3)}, {"F02N.0040": 3})
        assert result == date(2026, 6, 6)
        assert result.weekday() == 5                  # 周六


class TestMalformedLeadTimeRows:
    """spec「工时表格式非法」— 跳过该行，而非静默视为 0 天（tasks 5.3）。"""

    def _write(self, tmp_path, text):
        p = tmp_path / "lt.csv"
        p.write_text(text, encoding="utf-8", newline="\n")
        return p

    def test_non_integer_lead_days_row_skipped(self, tmp_path):
        csv_path = self._write(tmp_path, (
            "product_id,product_name,smt_lead_days\n"
            "A001,好料,7\n"
            "B002,坏料,七天\n"          # 非整数
            "C003,好料2,5\n"
        ))
        with pytest.warns(UserWarning, match="B002"):
            lt = load_smt_lead_time(csv_path)
        assert lt == {"A001": 7, "C003": 5}
        assert "B002" not in lt          # 关键：不是 0，是根本不在表里

    def test_empty_lead_days_row_skipped(self, tmp_path):
        csv_path = self._write(tmp_path, (
            "product_id,product_name,smt_lead_days\n"
            "A001,好料,7\n"
            "B002,空工时,\n"
            "C003,好料2,5\n"
        ))
        lt = load_smt_lead_time(csv_path)
        assert "B002" not in lt

    def test_skipped_product_then_returns_none(self, tmp_path):
        """被跳过的产品随后排产 → 返回 None（而非用 0 天算出一个假完工日）"""
        csv_path = self._write(tmp_path, (
            "product_id,product_name,smt_lead_days\n"
            "B002,坏料,七天\n"
        ))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            lt = load_smt_lead_time(csv_path)
        assert schedule_smt("B002", {"M001": date(2026, 6, 1)}, lt) is None


class TestPlaceholderDeclaration:
    """spec「工时对照表须声明其数据可信度」（tasks 5.4 的引擎侧一半）。"""

    def test_bundled_table_is_marked_placeholder(self):
        assert is_placeholder_lead_time() is True

    def test_declaration_text_present_in_file(self):
        """声明须写在数据文件里，而非只写在文档里——文档不会随数据被复制走"""
        from o1_smt_scheduling.schedule_engine import _LEAD_TIME_CSV
        text = _LEAD_TIME_CSV.read_text(encoding="utf-8")
        assert "非真实工时" in text
        assert "禁止用于任何对外承诺" in text

    def test_table_without_marker_is_not_placeholder(self, tmp_path):
        p = tmp_path / "real.csv"
        p.write_text(
            "# @placeholder: false\n"
            "product_id,product_name,smt_lead_days\n"
            "A001,真料,9\n",
            encoding="utf-8", newline="\n",
        )
        assert is_placeholder_lead_time(p) is False
        assert load_smt_lead_time(p) == {"A001": 9}

    def test_table_with_no_marker_defaults_to_placeholder(self, tmp_path):
        """无标记的表按占位处理——缺省应偏保守，不得默认当真实数据"""
        p = tmp_path / "bare.csv"
        p.write_text(
            "product_id,product_name,smt_lead_days\nA001,料,9\n",
            encoding="utf-8", newline="\n",
        )
        assert is_placeholder_lead_time(p) is True
