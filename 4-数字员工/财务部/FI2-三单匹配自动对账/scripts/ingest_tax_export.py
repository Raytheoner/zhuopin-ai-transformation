"""税务导出发票明细 Excel 摄取 CLI（队列 #295，design：fi2-tax-export-ingest）。

手动/按需触发（Q3 默认(a)，不挂定时——第 2 层定时扫描留待后置）。产出的
`invoice.csv` 落 `--out-dir`，供既有 `FeedSource(invoice_sample_dir=...)` 通道
原样消费，`feed_source.py` 本身零改动。

用法（在 `.51` 服务器本机跑，可直接访问 `D:\\airead` 与 U9C 财务 API）：
    python -m scripts.ingest_tax_export --export-dir D:\\airead --out-dir C:\\fi2\\app\\data\\tax_export

本地测试（指向本地样本目录 + 本地已处理清单）：
    python -m scripts.ingest_tax_export --export-dir data/tax_export_samples \\
        --out-dir data/tax_export --ledger data/tax_export/.processed.json
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys
from pathlib import Path

# —— 平台底座路径引导（队列 #345 收拢；唯一被允许的样板，实现见
# `5-平台底座/zhuopin_platform/zhuopin_platform/bootstrap.py`）。必须放在本文件任何
# zhuopin_platform / 场景包 import 之前。下方五行只负责让 bootstrap 自身可被 import、
# 不含任何判断分支；开发机 monorepo 与 `.51` 扁平部署两种布局的分歧由 ensure_paths 处理。——
_HERE = Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        sys.path.insert(0, str(_p / "5-平台底座" / "zhuopin_platform"))
        break
from zhuopin_platform.bootstrap import ensure_paths  # noqa: E402
ensure_paths(__file__, _HERE.parent.parent)  # noqa: E402

from zhuopin_platform.env_anchor import load_env as _resolve_and_load_env  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent

#: 本入口**没有**必需的凭据键（队列 #354 决策点 4 ＝ (c)：调用方声明自己要什么）。
#: 摄取是纯本地 Excel → CSV，FI2 从 `.env` 读的全是有默认值的容差/开关（`FI2_*`）。
#: 🔴 **空清单是一个经核查的结论，不是没填**——判据＝`fi2/` 全包 `environ.get()` 命中的
#: 8 个键逐个看过，无一是无默认值的凭据。此后若新增真凭据依赖，请同步补进本清单。
REQUIRED_ENV_KEYS: tuple[str, ...] = ()

#: 未解析记录的 stdout 打印上限——超出部分只进 JSONL。真实数据上这批是 26,000 行
#: 起步（队列 #418 ⑺），全量打印只会把这一整段淹掉，反而更看不见。
_DIAG_PRINT_LIMIT = 50


def load_env() -> None:
    """读入本次运行该用的那份 `.env`（解析见 `zhuopin_platform.env_anchor`，队列 #354）。

    🔴 **原实现是「向上逐级找最近的 `.env`」**——从 linked worktree 跑时命中 worktree 自己
    那份陈旧副本、**且不报错**。收拢后由 `--git-common-dir` 规范化到主工作区；`.51` 扁平
    布局（无 git、无 marker）走部署根锚点，行为与此前一致。凭据只在 `.env`，不入库、不打印。
    """
    print(_resolve_and_load_env(__file__, required=REQUIRED_ENV_KEYS).describe())


def main() -> int:
    load_env()
    ap = argparse.ArgumentParser(description="税务导出发票明细 Excel 摄取（队列 #295）")
    ap.add_argument("--export-dir", required=True, help="税务导出 Excel 所在目录（如 D:\\airead）")
    ap.add_argument("--out-dir", default=str(_ROOT / "data" / "tax_export"),
                     help="产出 invoice.csv 的目录（即传给 FeedSource 的 invoice_sample_dir）")
    ap.add_argument("--ledger", default=None,
                     help="已处理清单路径（默认 <out-dir>/.processed_exports.json）")
    args = ap.parse_args()

    from fi2.tax_export_ingest import (
        ingest_directory,
        load_ingested_invoice_nos,
        summarize_diagnostics,
        write_diagnostics_jsonl,
        write_invoice_csv,
    )
    from zhuopin_platform.audit.sinks import JsonlSink
    from zhuopin_platform.shared_tools.connector_audit import ConnectorAudit
    from zhuopin_platform.shared_tools.erp_connector import ZpConnector

    out_dir = Path(args.out_dir)
    ledger_path = Path(args.ledger) if args.ledger else out_dir / ".processed_exports.json"

    reports_dir = _ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    trace = ConnectorAudit(sink=JsonlSink(reports_dir / "fi2_access_trace.jsonl"))
    conn = ZpConnector.from_env(audit=trace)

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    # 发票级幂等闸（队列 #371）：已入库发票号直接从 invoice.csv 现读，零新增载体。
    invoice_csv = out_dir / "invoice.csv"
    result = ingest_directory(
        args.export_dir, ledger_path, conn, now=now,
        known_invoice_nos=load_ingested_invoice_nos(invoice_csv),
    )

    if result.resolved_rows:
        write_invoice_csv(result.resolved_rows, invoice_csv)

    print(f"新处理文件：{result.files_processed}")
    print(f"跳过（已处理过）：{result.files_skipped}")
    print(f"成功解析行数：{len(result.resolved_rows)}")
    print(f"跳过重复发票行数：{result.duplicate_rows_skipped}"
          f"（涉 {len(result.duplicate_invoice_nos)} 张发票，"
          "该发票号已由此前文件贡献过——预期内，非故障）")

    # ── 未解析行重试（队列 #418）──────────────────────────────────────────
    # 这三行是本次修复的可观测出口：面板此前报的假「无发票支撑」，就是第一行里的这些
    # 发票；它们此前只在 stdout 一闪而过，从不落盘、也从不重试。
    print(f"重试解开行数：{result.retried_rows_resolved}"
          f"（涉 {len(result.retried_invoice_nos)} 张发票——此前批次曾报未解析，"
          "本次 AP 单已可反查到；面板上这些发票此前显示为「无发票支撑」）")
    for inv in result.retried_invoice_nos[:20]:
        print(f"  ✅ 已补入 发票号={inv}")
    if len(result.retried_invoice_nos) > 20:
        print(f"  ...另有 {len(result.retried_invoice_nos) - 20} 张")
    print(f"仍未解开、留待下次重试：{result.pending_unresolved} 行"
          "（AP 单可能尚未立账——预期内，非故障）")
    if result.unretryable_unresolved:
        # 🔴 源文件已删/已改 ⇒ 这些行永远解不开了，必须出声（模块 docstring ③）。
        print(f"🔴 无法再重试：{result.unretryable_unresolved} 行 —— 源文件已不在盘上"
              f"或内容已变更：{result.unretryable_files}。"
              "这些发票将永远不会进入 invoice.csv，面板会持续把对应 AP 单报为"
              "「无发票支撑」。须把原导出文件放回 --export-dir 后重跑。")

    # ── 未解析记录：先汇总、再落盘、最后才截断打印（队列 #424「让丢行可见并可查」）──
    # 🔴 原实现是「逐条 print，不落盘」。真实数据上这是 26,000 行起步（#418 ⑺），
    # 而计划任务的 stdout 无人翻阅 ⇒ 等于这批丢行在生产上从不存在记录。
    print(f"未解析记录数：{len(result.diagnostics)}")
    for reason, n_rows, n_inv in summarize_diagnostics(result):
        print(f"  · {reason}：{n_rows} 行（涉 {n_inv} 张发票）")
    diag_path = reports_dir / "fi2_ingest_diagnostics.jsonl"
    n_written = write_diagnostics_jsonl(result, diag_path, now=now)
    print(f"未解析记录已落盘（追加）：{n_written} 条 → {diag_path}"
          "（可按 reason／发票号回查；不含金额与数量原始值）")
    for d in result.diagnostics[:_DIAG_PRINT_LIMIT]:
        loc = f"{d.file}" + (f" 第{d.row_index}行" if d.row_index else "")
        print(f"  [{d.reason}] {loc}"
              + (f" 发票号={d.digital_invoice_no}" if d.digital_invoice_no else "")
              + (f" {d.detail}" if d.detail else ""))
    if len(result.diagnostics) > _DIAG_PRINT_LIMIT:
        print(f"  ...另有 {len(result.diagnostics) - _DIAG_PRINT_LIMIT} 条，见上面那份 JSONL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
