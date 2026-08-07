"""真实税务导出 Excel 摄取集成测试（队列 #295，design：fi2-tax-export-ingest）。

默认跳过：仅当显式置 FI2_RUN_REAL=1 且 STOCK_API_BASE/STOCK_API_KEY 就位时运行
（同 `test_real_integration.py` 既有门禁范式）。样本为唐燕萍 2026-08-06 放入
`.51:D:\airead` 的 8 张真实发票导出件，已下载至本目录 `data/real_tax_export_samples/`
（financial 红色数据，`.gitignore` 的 `data/real_*` 规则覆盖，不入库）。

8 个样本对应的真实 ap_no 已于 2026-08-07 用真实 `ZpConnector` 逐一核实（部分沿用
round-1/design D18 已知的真实 AP 单号），本测试验证 `resolve_ap_no` 对同一批真实
数据能重新推导出一致结果——不是自证，是用独立于 `tax_export_ingest.py` 实现的
既有 `get_ap_lines(ap_no)` 反向核对。
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("FI2_RUN_REAL") != "1",
    reason="真实集成测试：置 FI2_RUN_REAL=1 且 STOCK_API_BASE/STOCK_API_KEY 就位才运行",
)

_SAMPLES_DIR = Path(__file__).resolve().parent.parent / "data" / "real_tax_export_samples"

# sample_N.xlsx → 数电发票号码 → 2026-08-07 真实核实的 ap_no（見 design.md Context）
_EXPECTED_AP_NO = {
    "26322000005633189671": "AP-2026070071",
    "26327000000742719331": "AP-2026070036",
    "26327000000742720017": "AP-2026070035",
    "26312000003314325436": "AP-2026060073",
    "26312000003103567591": "AP-2026060004",
    "26312000002434006411": "AP-2026040083",
    "25312000000417169997": "AP-2025120181",
    "26942000000588188581": "AP-2026050057",
}


def _connector():
    from zhuopin_platform.shared_tools.erp_connector import ZpConnector
    return ZpConnector.from_env()


@pytest.mark.skipif(not _SAMPLES_DIR.exists(), reason="真实样本目录不存在（financial 红色数据，不入库）")
def test_real_ap_no_resolution_matches_known_ground_truth():
    from fi2.tax_export_ingest import parse_export_workbook, resolve_ap_no

    conn = _connector()
    xlsx_files = sorted(_SAMPLES_DIR.glob("*.xlsx"))
    assert len(xlsx_files) == 8, f"预期 8 个真实样本，实际 {len(xlsx_files)}"

    resolved = {}
    for path in xlsx_files:
        rows = parse_export_workbook(path)
        digital_no = str(rows[0]["数电发票号码"]).strip()
        ap_no, reason, detail = resolve_ap_no(conn, digital_no)
        resolved[digital_no] = (ap_no, reason, detail)

    assert set(resolved.keys()) == set(_EXPECTED_AP_NO.keys())
    for digital_no, expected_ap_no in _EXPECTED_AP_NO.items():
        ap_no, reason, detail = resolved[digital_no]
        assert ap_no == expected_ap_no, f"{digital_no}: 期望 {expected_ap_no}，实得 {ap_no}（{reason} {detail}）"


@pytest.mark.skipif(not _SAMPLES_DIR.exists(), reason="真实样本目录不存在（financial 红色数据，不入库）")
def test_real_ingest_directory_end_to_end(tmp_path):
    """真实端到端跑一次完整摄取，如实打印命中率（不预设通过率——item_code 反查
    的真实唯一命中率是本次待观察项，见 design.md「验收与晋档条件」）。"""
    from fi2.tax_export_ingest import ingest_directory

    conn = _connector()
    ledger_path = tmp_path / "ledger.json"
    result = ingest_directory(_SAMPLES_DIR, ledger_path, conn, now="2026-08-07T00:00:00Z")

    assert len(result.files_processed) == 8
    assert result.files_skipped == []

    resolved_ap_nos = {r["ap_no"] for r in result.resolved_rows}
    print(f"\n[真实摄取] 成功解析行数={len(result.resolved_rows)} "
          f"未解析记录数={len(result.diagnostics)} "
          f"涉及 ap_no={sorted(resolved_ap_nos)}")
    for d in result.diagnostics:
        print(f"  未解析: file={d.file} row={d.row_index} reason={d.reason} "
              f"inv={d.digital_invoice_no} detail={d.detail}")

    # ap_no 反查作为摄取前置步骤，必须对全部 8 张发票都解析成功（本测试的硬断言）；
    # item_code 反查是否每行都能唯一命中，如实观察不预设（真实存在"多笔批次合并成
    # 一张发票行"的已知边界场景，见 test_resolve_item_code_zero_match_when_qty_not_in_ap_lines）。
    diagnosed_ap_no_failures = [d for d in result.diagnostics if d.reason.startswith("ap_no_")]
    assert diagnosed_ap_no_failures == [], f"存在 ap_no 反查失败: {diagnosed_ap_no_failures}"
