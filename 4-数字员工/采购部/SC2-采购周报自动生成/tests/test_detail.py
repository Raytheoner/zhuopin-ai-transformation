"""明细层单测（队列 §一 `#538`：周报数字须能展开到「正是这些行」，且行数与周报逐字相等）。

三族判据：
- **同源**：三节 × 三窗口的明细「计入行数」＝ `compute_metrics` 的对应指标（mock 数据集 ＋ 构造数据集）。
- **对账是硬断言**：数据集与周报一旦分叉（多一行／少一行），`reconcile` 必须抛、接口必须 500、CLI 必须不写文件。
- **落盘往返**：数据集快照 dump → load 逐字段相等；schema 不符拒读；缺快照上抛且**不现取**。
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import replace
from datetime import date, timedelta

import pytest

from sc2 import config, detail
from sc2.metrics import compute_metrics
from sc2.models import FrozenDataset, OrderLine, ReceiptRecord
from sc2.report import build_report, save_snapshot
from sc2.sources import MockFeed
from sc2.webapp import create_app
from sc2.windows import build_windows

BASE = date(2026, 8, 19)
PREFIX = "/procurement/sc2"


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("SC2_REPORTS_DIR", str(tmp_path))
    monkeypatch.delenv("ZP_GATE_PASSWORD", raising=False)
    yield


@pytest.fixture()
def mock_bundle():
    windows = build_windows(BASE)
    dataset = MockFeed().fetch(windows)
    report = build_report(dataset, windows)
    return dataset, windows, report


def _line(po, ln, day, *, status=2, qty=100.0, rcv=0.0, known=True, mat="M1", sup="S1"):
    return OrderLine(po_id=po, line_no=ln, material_id=mat, supplier_id=sup,
                     qty_ordered=qty if known else 0.0, qty_received=rcv, order_date=day,
                     expected_date=day, confirmed_date=day, line_status=status,
                     unit_price=2.0, supplier_name="供应商", buyer="采购员",
                     doc_type="PO01", qty_confirmed_known=known)


def _receipt(doc, ln, day, po, po_ln, qty=10.0):
    return ReceiptRecord(receipt_doc_no=doc, line_no=ln, po_id=po, po_line_no=po_ln,
                         material_id="M1", supplier_name="供应商", receipt_date=day,
                         qty_received=qty, unit_price=2.0)


@pytest.fixture()
def crafted_bundle():
    """构造数据集：窗口边界两侧各一行、四种「不计入未清」形态各一行、一条追不回来源的收货。

    刻意让每个判据都有恰好一行样本——任何一条判据被改错，都会让某一格的计数变 1。
    """
    windows = build_windows(BASE)
    cur = windows.current
    lines = (
        _line("PO-A", "1", cur.start),                            # 本周首日：计入下单、计入未清
        _line("PO-A", "2", cur.end),                              # 本周末日：计入下单、计入未清
        _line("PO-B", "1", cur.start - timedelta(days=1)),        # 上周末日：不计入本周（边界外）
        _line("PO-C", "1", cur.end + timedelta(days=1)),          # 下周首日：不计入本周（边界外）
        _line("PO-D", "1", cur.start, status=4),                  # 短缺关闭：计入下单、不计入未清
        _line("PO-D", "2", cur.start, status=3),                  # 自然关闭：同上
        _line("PO-E", "1", cur.start, qty=50, rcv=50),            # 已收齐：未清量 0，不计入未清
        _line("PO-F", "1", cur.start, known=False),               # 确认数量未知：不计入未清
        _line("PO-G", "1", cur.start, status=-1),                 # 状态未知、未收：按未关闭计入未清
    )
    receipts = (
        _receipt("R1", "10", cur.start, "PO-B", "1"),             # 可溯源（PO-B 在全量索引里）
        _receipt("R2", "10", cur.end, "PO-X", "9"),               # 追不回来源
        _receipt("R3", "10", cur.end + timedelta(days=1), "PO-A", "1"),   # 下周：不计入本周
    )
    dataset = FrozenDataset(order_lines=lines, receipts=receipts, mode="mock",
                            fetched_at="2026-08-19T10:00:00+08:00",
                            range_start=windows.month_ago.start, range_end=cur.end)
    report = build_report(dataset, windows)
    return dataset, windows, report


# ── 一、同源：明细计入行数 ＝ 周报指标 ────────────────────────────────────────

@pytest.mark.parametrize("bundle_name", ["mock_bundle", "crafted_bundle"])
def test_三节三窗口明细计入行数等于周报指标(bundle_name, request):
    dataset, windows, report = request.getfixturevalue(bundle_name)
    metrics = {m.key: m for m in report.metrics}
    for section, (_, metric_key) in detail.SECTIONS.items():
        for slot in detail.WINDOWS:
            table = detail.build_table(dataset, windows, section, slot)
            assert table.counted == int(metrics[metric_key].__getattribute__(slot).value), \
                f"{section}/{slot}"


def test_构造数据集的下单节恰为窗口内行且边界两侧不入(crafted_bundle):
    dataset, windows, _ = crafted_bundle
    table = detail.build_table(dataset, windows, "order", "current")
    keys = {(r[0], r[1]) for r in table.rows}
    assert keys == {("PO-A", "1"), ("PO-A", "2"), ("PO-D", "1"), ("PO-D", "2"),
                    ("PO-E", "1"), ("PO-F", "1"), ("PO-G", "1")}
    assert ("PO-B", "1") not in keys and ("PO-C", "1") not in keys
    assert table.counted == len(table.rows) == 7


def test_在途节列出全部窗口内行并逐行标出计入与剔除原因(crafted_bundle):
    dataset, windows, _ = crafted_bundle
    table = detail.build_table(dataset, windows, "open", "current")
    by_key = {(r[0], r[1]): r for r in table.rows}
    col = {c: i for i, c in enumerate(table.columns)}
    assert len(table.rows) == 7, "在途节须列出窗口内全部下单行，不只列计入的"
    assert table.counted == 3                                   # PO-A/1, PO-A/2, PO-G/1
    assert by_key[("PO-A", "1")][col["计入未清行数"]] == "是"
    assert by_key[("PO-G", "1")][col["计入未清行数"]] == "是"
    assert "已关闭" in by_key[("PO-D", "1")][col["剔除原因"]]
    assert "短缺关闭" in by_key[("PO-D", "1")][col["剔除原因"]]
    assert "未清数量为 0" in by_key[("PO-E", "1")][col["剔除原因"]]
    assert "确认数量未取到" in by_key[("PO-F", "1")][col["剔除原因"]]
    # 计入的行剔除原因为空；剔除的行原因非空——两列互斥，不允许「否」而无原因
    for r in table.rows:
        assert (r[col["计入未清行数"]] == "是") == (r[col["剔除原因"]] == "")


def test_收货节可溯源列与全量订单索引一致(crafted_bundle):
    dataset, windows, _ = crafted_bundle
    table = detail.build_table(dataset, windows, "receipt", "current")
    col = {c: i for i, c in enumerate(table.columns)}
    rows = {r[0]: r for r in table.rows}
    assert set(rows) == {"R1", "R2"}, "下周那条收货不得入本周"
    assert rows["R1"][col["可溯源到采购订单行"]] == "是", "PO-B 是上周下的单，但全量索引里有它"
    assert rows["R2"][col["可溯源到采购订单行"]] == "否"


def test_确认数量未知的行数量与金额列写未取到而非0(crafted_bundle):
    dataset, windows, _ = crafted_bundle
    table = detail.build_table(dataset, windows, "order", "current")
    col = {c: i for i, c in enumerate(table.columns)}
    row = next(r for r in table.rows if (r[0], r[1]) == ("PO-F", "1"))
    assert row[col["确认数量"]] == "未取到"
    assert row[col["下单金额"]] == "未取到"
    assert row[col["未清数量"]] == "未取到"


def test_未知节或窗口拼错即报错不猜(mock_bundle):
    dataset, windows, _ = mock_bundle
    with pytest.raises(ValueError):
        detail.build_table(dataset, windows, "orders", "current")
    with pytest.raises(ValueError):
        detail.build_table(dataset, windows, "order", "this_week")


# ── 二、对账是硬断言 ────────────────────────────────────────────────────────

def test_对账通过时返回三节三窗口计数(mock_bundle):
    dataset, windows, report = mock_bundle
    counts = detail.reconcile(dataset, windows, report)
    assert set(counts) == set(detail.SECTIONS)
    assert all(set(v) == set(detail.WINDOWS) for v in counts.values())
    assert counts["order"]["current"] == 3 and counts["open"]["current"] == 1


def test_数据集多一行即对账失败(mock_bundle):
    """数据集与周报分叉的最小形态：多出一行落在本周的下单行。"""
    dataset, windows, report = mock_bundle
    extra = replace(dataset.order_lines[0], po_id="PO-EXTRA")
    forked = replace(dataset, order_lines=dataset.order_lines + (extra,))
    with pytest.raises(detail.DetailMismatch) as ei:
        detail.reconcile(forked, windows, report)
    assert "下单节·本周" in str(ei.value)


def test_数据集少一行收货即对账失败(mock_bundle):
    dataset, windows, report = mock_bundle
    forked = replace(dataset, receipts=dataset.receipts[1:])
    with pytest.raises(detail.DetailMismatch) as ei:
        detail.reconcile(forked, windows, report)
    assert "收货节" in str(ei.value)


# ── 三、CSV 呈现 ─────────────────────────────────────────────────────────────

def test_csv带BOM且首行为列头行数与表一致(mock_bundle):
    dataset, windows, _ = mock_bundle
    table = detail.build_table(dataset, windows, "order", "current")
    text = detail.render_csv(table)
    assert text.startswith("\ufeff"), "Excel 双击打开中文不乱码依赖 BOM"
    rows = list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))
    assert tuple(rows[0]) == table.columns
    assert len(rows) - 1 == len(table.rows) == 3
    assert "\r\n" in text


def test_csv文件名含期次节名与窗口名():
    assert detail.csv_filename("2026-W36", "order", "current") == "sc2_2026-W36_下单_本周.csv"
    assert detail.csv_filename("2026-W36", "open", "month_ago") == "sc2_2026-W36_在途_上月同期.csv"


# ── 四、数据集快照落盘 ──────────────────────────────────────────────────────

def test_数据集快照往返逐字段相等(mock_bundle):
    dataset, _, report = mock_bundle
    path = detail.save_dataset(dataset, report.period)
    assert path.parent == config.reports_dir()
    loaded = detail.load_dataset(report.period)
    assert loaded.order_lines == dataset.order_lines
    assert loaded.receipts == dataset.receipts
    assert (loaded.mode, loaded.fetched_at, loaded.range_start, loaded.range_end) == \
        (dataset.mode, dataset.fetched_at, dataset.range_start, dataset.range_end)
    assert loaded.source_notes == dataset.source_notes


def test_数据集快照schema不符即拒读(mock_bundle):
    dataset, _, report = mock_bundle
    path = detail.save_dataset(dataset, report.period)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["schema"] = detail.DATASET_SCHEMA + 1
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="schema"):
        detail.load_dataset(report.period)


def test_缺数据集快照即上抛并指明要先重算():
    with pytest.raises(FileNotFoundError, match="api/refresh"):
        detail.load_dataset("2026-W01")


def test_从快照复原的数据集可重算出与原周报相同的指标(mock_bundle):
    """快照的价值：脱离 ERP 也能把整期指标重算出来，而且一格不差。"""
    dataset, windows, report = mock_bundle
    detail.save_dataset(dataset, report.period)
    again = compute_metrics(detail.load_dataset(report.period), windows)
    assert [(m.key, m.current.value, m.previous.value, m.month_ago.value) for m in again] == \
        [(m.key, m.current.value, m.previous.value, m.month_ago.value) for m in report.metrics]


# ── 五、Web 接口 ─────────────────────────────────────────────────────────────

@pytest.fixture()
def client():
    app = create_app(base_date=BASE, mode="mock")
    app.config["TESTING"] = True
    return app.test_client()


def test_生成周报时数据集快照与周报快照成对落盘(client):
    client.get(f"{PREFIX}/")                       # 首次访问触发 _regenerate
    period = client.get(f"{PREFIX}/api/report").get_json()["period"]
    assert config.snapshot_path(period).exists()
    assert detail.dataset_path(period).exists(), "只落周报快照不落数据集，该期就展不开到行"


def test_明细索引给出每格明细行数与周报值并相等(client):
    client.get(f"{PREFIX}/")
    r = client.get(f"{PREFIX}/api/detail")
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    for section, (_, metric_key) in detail.SECTIONS.items():
        sec = body["sections"][section]
        assert sec["metric"] == metric_key
        for slot in detail.WINDOWS:
            cell = sec["windows"][slot]
            assert cell["rows"] == int(cell["reported"])
            assert cell["csv"].startswith(PREFIX)


def test_明细csv下载行数等于周报下单行数(client):
    client.get(f"{PREFIX}/")
    reported = next(m for m in client.get(f"{PREFIX}/api/detail").get_json()["sections"].values()
                    if m["metric"] == "order_line_count")["windows"]["current"]["reported"]
    r = client.get(f"{PREFIX}/api/detail/order.csv?window=current")
    assert r.status_code == 200
    assert r.mimetype == "text/csv"
    assert "attachment" in r.headers["Content-Disposition"]
    text = r.get_data(as_text=True)
    rows = list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))
    assert len(rows) - 1 == int(reported) == 3


def test_明细接口拼错节或窗口返回404(client):
    client.get(f"{PREFIX}/")
    assert client.get(f"{PREFIX}/api/detail/orders.csv").status_code == 404
    assert client.get(f"{PREFIX}/api/detail/order.csv?window=nope").status_code == 404


def test_该期无数据集快照时返回404并提示重算而不现取(client):
    """生成于明细导出上线之前的期次：只有周报快照、没有数据集快照。"""
    client.get(f"{PREFIX}/")
    period = client.get(f"{PREFIX}/api/report").get_json()["period"]
    detail.dataset_path(period).unlink()
    r = client.get(f"{PREFIX}/api/detail/order.csv")
    assert r.status_code == 404
    assert "api/refresh" in r.get_json()["error"]
    assert not detail.dataset_path(period).exists(), "404 路径不得顺手现取并落一份新快照"


def test_数据集与周报分叉时接口拒绝导出返回500(client):
    """快照被改过（或两处口径分叉）⇒ 宁可 500，不给一份对不上的明细。"""
    client.get(f"{PREFIX}/")
    period = client.get(f"{PREFIX}/api/report").get_json()["period"]
    path = detail.dataset_path(period)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["order_lines"].append(dict(data["order_lines"][0], po_id="PO-FORK"))
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    r = client.get(f"{PREFIX}/api/detail/order.csv")
    assert r.status_code == 500
    assert "不一致" in r.get_json()["error"]
    assert client.get(f"{PREFIX}/api/detail").status_code == 500


def test_周报页含三节九个明细链接且全在前缀下(client):
    html = client.get(f"{PREFIX}/").get_data(as_text=True)
    for section in detail.SECTIONS:
        for slot in detail.WINDOWS:
            assert f'href="{PREFIX}/api/detail/{section}.csv?window={slot}"' in html
    assert "计算过程明细导出" in html


def test_明细接口在门禁下不得未鉴权取到业务数据(monkeypatch):
    monkeypatch.setenv("ZP_GATE_PASSWORD", "s3cret")
    app = create_app(base_date=BASE, mode="mock")
    app.config["TESTING"] = True
    r = app.test_client().get(f"{PREFIX}/api/detail/order.csv")
    assert r.status_code in (302, 401)
    assert "PO-2601" not in r.get_data(as_text=True)


# ── 六、CLI ──────────────────────────────────────────────────────────────────

def test_cli_detail从快照导出九个csv且行数与周报相等(mock_bundle, tmp_path, capsys):
    import run_sc2

    dataset, _, report = mock_bundle
    save_snapshot(report)
    detail.save_dataset(dataset, report.period)
    out = tmp_path / "out"
    rc = run_sc2.main(["detail", "--period", report.period, "--out", str(out)])
    assert rc == 0
    files = sorted(out.glob("*.csv"))
    assert len(files) == 9
    order_csv = out / detail.csv_filename(report.period, "order", "current")
    rows = list(csv.reader(io.StringIO(order_csv.read_text(encoding="utf-8").lstrip("\ufeff"))))
    assert len(rows) - 1 == 3
    assert "9 格全等" in capsys.readouterr().out


def test_cli_detail对账失败一个文件都不写(mock_bundle, tmp_path):
    import run_sc2

    dataset, _, report = mock_bundle
    save_snapshot(report)
    forked = replace(dataset, receipts=dataset.receipts[1:])
    detail.save_dataset(forked, report.period)
    out = tmp_path / "out"
    with pytest.raises(detail.DetailMismatch):
        run_sc2.main(["detail", "--period", report.period, "--out", str(out)])
    assert not list(out.glob("*.csv")) if out.exists() else True


def test_cli_report与autopush落数据集快照(monkeypatch, capsys):
    import run_sc2

    rc = run_sc2.main(["report", "--mode", "mock", "--base", BASE.isoformat()])
    assert rc == 0
    period = build_windows(BASE).current.label()
    assert detail.dataset_path(period).exists()
    detail.dataset_path(period).unlink()
    rc = run_sc2.main(["autopush", "--mode", "mock", "--base", BASE.isoformat(), "--no-push"])
    assert rc == 0
    assert detail.dataset_path(period).exists()
