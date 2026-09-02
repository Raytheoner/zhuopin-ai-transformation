"""采购提前期中位数统计单测（队列 §一 #403 子项 ⑵ ／ §四 #125 拍板 D-2(b)）。

TestNormalize      — join 键规整（🔴 本文件的主要存在理由，见下）
TestCompute        — 数据卫生漏斗 H1~H6 逐条
TestVerifyJoin     — join 字面不一致时必须 fail-loud，不得静默出数

🔴 **为什么专门为 join 写测试**：财务域已有先例教训——join 字段字面不一致会
**静默落空且不报错**，两边都跑成功、结果是空的，而报表看上去完全正常。本统计的
join 键 `GR.(SrcDocNo, SrcDocLineNo)` → `Purchase.(DocNo, DocLineNo)` 里，行号在
真实数据中是 int（`10`），一旦某侧变成 `'10.0'` 或 `' 10'`，命中率会悄悄归零而
中位数照样打印出来。`TestNormalize` 钉死的就是这一点。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "leadtime_median.py"
_spec = importlib.util.spec_from_file_location("leadtime_median", _SCRIPT)
lm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lm)


def _po(doc, line, item, business_date, qty=100.0, supplier="供应商A"):
    return {"DocNo": doc, "DocLineNo": line, "ItemCode": item, "ItemName": f"品名{item}",
            "ConfirmQty": qty, "SupplierName": supplier,
            "BusinessDate": f"{business_date}T00:00:00"}


def _gr(src_doc, src_line, item, business_date, qty=100.0):
    return {"RcvDocNo": f"R{src_doc}", "DocLineNo": 10, "SrcDocNo": src_doc,
            "SrcDocLineNo": src_line, "ItemCode": item, "ItemName": f"品名{item}",
            "RcvQtyTU": qty, "BusinessDate": f"{business_date}T00:00:00"}


class TestNormalize:
    """join 键规整——三态不相等是这个统计最容易静默失败的地方。"""

    @pytest.mark.parametrize("raw,expected", [
        (10, "10"), ("10", "10"), (10.0, "10"), ("10.0", "10"), (" 10 ", "10"),
    ])
    def test_line_no_variants_collapse_to_one(self, raw, expected):
        assert lm._norm_line(raw) == expected

    def test_empty_line_no_stays_empty(self):
        assert lm._norm_line(None) == ""
        assert lm._norm_line("") == ""

    def test_non_numeric_line_no_preserved(self):
        assert lm._norm_line("A1") == "A1"

    def test_doc_no_keeps_case_and_suffix(self):
        # 🔴 真实数据里 `ZPCG20220628001W` 的 W 是有意义的后缀；折叠大小写或去后缀
        # 会把两张不同的单合并成一张，属于「看着更干净、其实错了」。
        assert lm._norm_doc("  ZPCG20220628001W ") == "ZPCG20220628001W"
        assert lm._norm_doc("zpcg1") != lm._norm_doc("ZPCG1")


class TestCompute:
    def _run(self, po, gr, **kw):
        kw.setdefault("months", 0)
        kw.setdefault("arrival", "first")
        kw.setdefault("min_samples", 1)
        return lm.compute(po, gr, **kw)

    def test_basic_lead_time(self):
        po = [_po("D1", 10, "M1", "2026-01-01")]
        gr = [_gr("D1", 10, "M1", "2026-01-11")]
        r = self._run(po, gr)
        assert r["results"][0]["median"] == 10

    def test_h1_drops_gr_without_source_doc(self):
        po = [_po("D1", 10, "M1", "2026-01-01")]
        gr = [_gr("D1", 10, "M1", "2026-01-11"), _gr("", 10, "M1", "2026-01-11")]
        r = self._run(po, gr)
        assert r["funnel"]["GR 行 · H1 剔除无来源单号"] == 1

    def test_h2a_drops_returns_and_h2b_drops_zero_receipts(self):
        po = [_po("D1", 10, "M1", "2026-01-01"), _po("D2", 10, "M1", "2026-01-01")]
        gr = [_gr("D1", 10, "M1", "2026-01-11", qty=-5.0),
              _gr("D2", 10, "M1", "2026-01-11", qty=0.0)]
        r = self._run(po, gr)
        assert r["funnel"]["GR 行 · H2a 剔除 RcvQtyTU<0（退货/红字冲销）"] == 1
        assert r["funnel"]["GR 行 · H2b 剔除 RcvQtyTU=0（零入库，无实物到货）"] == 1
        assert r["funnel"]["采购行 · 进入统计"] == 0

    def test_h3_drops_red_letter_po_line(self):
        po = [_po("D1", 10, "M1", "2026-01-01", qty=-100.0)]
        gr = [_gr("D1", 10, "M1", "2026-01-11")]
        r = self._run(po, gr)
        assert r["funnel"]["PO 行 · H3 剔除 ConfirmQty<=0（红字/作废）"] == 1
        assert r["funnel"]["采购行 · 进入统计"] == 0

    def test_h4_partial_receipts_take_first_by_default(self):
        po = [_po("D1", 10, "M1", "2026-01-01")]
        gr = [_gr("D1", 10, "M1", "2026-01-21"), _gr("D1", 10, "M1", "2026-01-06")]
        r = self._run(po, gr)
        assert r["results"][0]["median"] == 5           # 取首次（01-06），不是 01-21
        assert r["funnel"]["采购行 · 其中分多次入库的行"] == 1

    def test_h4_last_arrival_caliber(self):
        po = [_po("D1", 10, "M1", "2026-01-01")]
        gr = [_gr("D1", 10, "M1", "2026-01-21"), _gr("D1", 10, "M1", "2026-01-06")]
        r = self._run(po, gr, arrival="last")
        assert r["results"][0]["median"] == 20

    def test_h5_drops_negative_lead_time(self):
        po = [_po("D1", 10, "M1", "2026-01-10")]
        gr = [_gr("D1", 10, "M1", "2026-01-01")]        # 入库早于制单 ⇒ 数据错误
        r = self._run(po, gr)
        assert r["funnel"]["采购行 · H5 剔除提前期为负（入库早于制单）"] == 1
        assert r["funnel"]["采购行 · 进入统计"] == 0

    def test_h6_marks_insufficient_sample_and_withholds_median(self):
        po = [_po(f"D{i}", 10, "M1", "2026-01-01") for i in range(3)]
        gr = [_gr(f"D{i}", 10, "M1", "2026-01-11") for i in range(3)]
        r = self._run(po, gr, min_samples=5)
        row = r["results"][0]
        assert row["n"] == 3 and row["enough"] is False
        assert "median" not in row        # 🔴 样本不足时**不给数**，而不是给个不可靠的数

    def test_quartiles_use_nearest_rank_not_interpolation(self):
        # 小样本下不插值——避免造出数据里根本没有的天数。
        po = [_po(f"D{i}", 10, "M1", "2026-01-01") for i in range(5)]
        gr = [_gr(f"D{i}", 10, "M1", d) for i, d in enumerate(
            ["2026-01-02", "2026-01-03", "2026-01-05", "2026-01-09", "2026-01-21"])]
        r = self._run(po, gr, min_samples=5)
        row = r["results"][0]
        assert row["median"] == 4
        assert row["p25"] in (1, 2, 4) and row["p75"] in (4, 8, 20)
        assert row["min"] == 1 and row["max"] == 20

    def test_line_no_type_mismatch_still_joins(self):
        """🔴 回归钉子：PO 侧 int 行号、GR 侧字符串行号，必须仍然接上。"""
        po = [_po("D1", 10, "M1", "2026-01-01")]
        gr = [_gr("D1", "10.0", "M1", "2026-01-11")]
        r = self._run(po, gr)
        assert r["funnel"]["GR 行 · 剔除接不上采购行"] == 0
        assert r["results"][0]["median"] == 10

    def test_window_filters_by_order_date(self):
        po = [_po("D1", 10, "M1", "2020-01-01")]
        gr = [_gr("D1", 10, "M1", "2020-01-11")]
        r = self._run(po, gr, months=24)
        assert r["funnel"]["采购行 · 进入统计"] == 0


class TestVerifyJoin:
    def test_passes_when_literals_align(self):
        po = [_po(f"D{i}", 10, "M1", "2026-01-01") for i in range(10)]
        gr = [_gr(f"D{i}", 10, "M1", "2026-01-11") for i in range(10)]
        info = lm.verify_join(po, gr)
        assert info["rate"] == 1.0

    def test_fails_loud_when_literals_diverge(self):
        """🔴 字面不一致时必须中止，不得静默出一个建立在空 join 上的中位数。"""
        po = [_po(f"D{i}", 10, "M1", "2026-01-01") for i in range(10)]
        gr = [_gr(f"XX{i}", 10, "M1", "2026-01-11") for i in range(10)]
        with pytest.raises(SystemExit):
            lm.verify_join(po, gr)

    def test_empty_source_doc_rows_excluded_from_denominator(self):
        # `SrcDocNo` 为空的行不是「join 失败」，是「本就没有采购来源」，
        # 计入分母会把命中率稀释成假警报。
        po = [_po("D1", 10, "M1", "2026-01-01")]
        gr = [_gr("D1", 10, "M1", "2026-01-11")] + [_gr("", 10, "M1", "2026-01-11")] * 50
        info = lm.verify_join(po, gr)
        assert info["linked"] == 1 and info["rate"] == 1.0
