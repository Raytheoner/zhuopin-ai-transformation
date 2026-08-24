"""`scripts/rebuild_invoice_csv.py` 三道安全闸测试（队列 #371，2026-08-24）。

本脚本会**改写生产数据**（`.51` 上那份 3409 行的 `invoice.csv`），所以它的三道闸
比它的主逻辑更值得测：闸没拦住的那一次，删掉的是财务真实数据。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "rebuild_invoice_csv.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("_rebuild_invoice_csv", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


rebuild = _load_module()


def _row(inv_no, ap_no="AP-1", item_code="X001", qty=10, untaxed=100.0, tax=13.0):
    return {"inv_no": inv_no, "ap_no": ap_no, "item_code": item_code, "unit": "个",
            "unit_price": "10.0", "inv_qty": str(qty), "untaxed_amount": str(untaxed),
            "tax_rate": "0.13", "tax_amount": str(tax), "inv_date": "2026-06-11"}


def _ledger(*pairs):
    """pairs = (文件名, 行数, processed_at)"""
    return {f"hash-{i}": {"file": f, "row_count": n, "processed_at": t}
            for i, (f, n, t) in enumerate(pairs)}


# ── 闸①：归属重建的累加校验 ────────────────────────────────────────────────

def test_partition_matches_ledger_order():
    rows = [_row("A"), _row("B"), _row("C")]
    ledger = _ledger(("second.xlsx", 1, "2026-08-02T00:00:00Z"),
                     ("first.xlsx", 2, "2026-08-01T00:00:00Z"))
    blocks = rebuild.partition_by_ledger(rows, ledger)
    # 按 processed_at 排序 ⇒ first.xlsx 先，拿走前 2 行
    assert [f for f, _seg in blocks] == ["first.xlsx", "second.xlsx"]
    assert [r["inv_no"] for r in blocks[0][1]] == ["A", "B"]
    assert [r["inv_no"] for r in blocks[1][1]] == ["C"]


def test_gate1_aborts_when_ledger_and_csv_diverge():
    """🔴 ledger 行数合计与 CSV 行数对不上 ⇒ 归属重建不成立，必须中止而不是猜。"""
    rows = [_row("A"), _row("B"), _row("C")]
    ledger = _ledger(("one.xlsx", 2, "2026-08-01T00:00:00Z"))   # 合计 2 ≠ 3
    with pytest.raises(rebuild.RebuildAborted, match="闸①未过"):
        rebuild.partition_by_ledger(rows, ledger)


# ── 闸③：被删行必须是精确重复 ──────────────────────────────────────────────

def test_dedup_drops_cross_file_duplicate_invoice():
    """两个文件各贡献同一张发票一次 ⇒ 保留第一个文件的那份、删掉第二份。"""
    rows = [_row("INV-1"), _row("INV-1")]
    ledger = _ledger(("a.xlsx", 1, "2026-08-01T00:00:00Z"),
                     ("b.xlsx", 1, "2026-08-02T00:00:00Z"))
    blocks = rebuild.partition_by_ledger(rows, ledger)
    kept, dropped = rebuild.dedup_by_invoice(blocks)
    assert len(kept) == 1
    assert len(dropped) == 1
    assert dropped[0][0] == "b.xlsx"


def test_dedup_keeps_repeated_lines_within_one_file():
    """🔴 同一文件内同发票多行是合法数据（真实实证见 tax_export_ingest 测试），不许删。"""
    rows = [_row("INV-1"), _row("INV-1"), _row("INV-1")]
    ledger = _ledger(("a.xlsx", 3, "2026-08-01T00:00:00Z"))
    blocks = rebuild.partition_by_ledger(rows, ledger)
    kept, dropped = rebuild.dedup_by_invoice(blocks)
    assert len(kept) == 3
    assert dropped == []


def test_gate3_aborts_when_duplicate_rows_differ():
    """🔴 两份源文件对同一张发票给出**不同**数字 ⇒ 这不是简单重复，必须中止。

    「留一个删一个」在这里是错的——哪一个是对的，只有人能判。
    """
    rows = [_row("INV-1", untaxed=100.0), _row("INV-1", untaxed=999.0)]
    ledger = _ledger(("a.xlsx", 1, "2026-08-01T00:00:00Z"),
                     ("b.xlsx", 1, "2026-08-02T00:00:00Z"))
    blocks = rebuild.partition_by_ledger(rows, ledger)
    with pytest.raises(rebuild.RebuildAborted, match="闸③未过"):
        rebuild.dedup_by_invoice(blocks)


def test_dedup_is_noop_when_no_duplicates():
    rows = [_row("INV-1"), _row("INV-2")]
    ledger = _ledger(("a.xlsx", 1, "2026-08-01T00:00:00Z"),
                     ("b.xlsx", 1, "2026-08-02T00:00:00Z"))
    kept, dropped = rebuild.dedup_by_invoice(rebuild.partition_by_ledger(rows, ledger))
    assert len(kept) == 2
    assert dropped == []


# ── 闸②：与源文件交叉验证 ──────────────────────────────────────────────────

def test_gate2_passes_when_block_matches_source(tmp_path):
    from test_tax_export_ingest import _make_export_xlsx, _row as _xlsx_row

    export_dir = tmp_path / "export"
    export_dir.mkdir()
    _make_export_xlsx(export_dir / "a.xlsx", [_xlsx_row(digital_no="INV-1")])
    blocks = [("a.xlsx", [_row("INV-1")])]
    checked, skipped = rebuild.verify_against_sources(blocks, export_dir)
    assert (checked, skipped) == (1, 0)


def test_gate2_aborts_when_block_exceeds_source(tmp_path):
    """🔴 重建出的段里某发票行数 > 源文件里的真实行数 ⇒ 归属重建与源数据矛盾，中止。"""
    from test_tax_export_ingest import _make_export_xlsx, _row as _xlsx_row

    export_dir = tmp_path / "export"
    export_dir.mkdir()
    _make_export_xlsx(export_dir / "a.xlsx", [_xlsx_row(digital_no="INV-1")])   # 源里 1 行
    blocks = [("a.xlsx", [_row("INV-1"), _row("INV-1")])]                      # 段里 2 行
    with pytest.raises(rebuild.RebuildAborted, match="闸②未过"):
        rebuild.verify_against_sources(blocks, export_dir)


def test_gate2_skips_files_no_longer_on_disk(tmp_path):
    """源文件已被删除（本次事故正是如此）⇒ 无法验证，如实计入 skipped，不报错。"""
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    blocks = [("gone.xlsx", [_row("INV-1")])]
    checked, skipped = rebuild.verify_against_sources(blocks, export_dir)
    assert (checked, skipped) == (0, 1)
