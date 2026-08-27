"""税务导出 Excel 定时扫描 CLI（队列 #82 第2层，2026-08-10 build）。

计划任务专用入口（`register-tax-export-scan-task.ps1` 每日调度）——与手动 CLI
`scripts/ingest_tax_export.py`（Q3 拍板"不挂定时"，保留原样不改）并存：两者共享
同一 `--out-dir`/`--ledger`（内容哈希幂等，谁先跑到都一样，互不冲突）。本脚本
额外做手动 CLI 不做的事：文件级摄取失败（sheet 名/必需列不符、无法解析）与源头
断供（连续 N 个工作日无新文件）经群 webhook 告警 Shao Peishen，非零退出码，供计划
任务"上次运行结果"留痕（见 `fi2/tax_export_scan.py` 模块 docstring）。

**退出码语义**（计划任务 `LastTaskResult` 据此区分，勿合并）：
    0 = 扫描正常（有新文件摄取成功，或无新文件但未超断供阈值）
    1 = 扫描本身异常，或有文件级摄取失败——**我方机制出问题**，需查代码/连接/目录
    2 = 源头断供超阈值——**我方机制正常，是没有新文件来**，需人去问源头一声
两者性质完全不同、处置动作也完全不同，故不共用一个非零码。

用法（在 `.51` 服务器本机跑，可直接访问 `D:\\airead` 与 U9C 财务 API）：
    python scan_tax_export_scheduled.py --export-dir D:\\airead --out-dir C:\\fi2\\app\\data\\tax_export

本地测试（指向本地样本目录 + 本地已处理清单）：
    python scan_tax_export_scheduled.py --export-dir data/tax_export_samples \\
        --out-dir data/tax_export --ledger data/tax_export/.processed_exports.json

**告警去向**：只读 `WECOM_WEBHOOK_URL_OPS`（IT 运维部群），**刻意不回退到裸
`WECOM_WEBHOOK_URL`**——后者按队列 #282 已确认指向业务部门群（本机根 `.env` 注释
即写明"采购内部工作群"），而本告警的主题是"自动化机制自己出问题了"，按通知通道
决策件 `3-治理与合规/通知通道架构决策件-webhook退役与aibot单一出口-2026-08-06.md`
§4.2／§5.1，其受众收敛为「Shao Peishen ＋ IT 陈承」二人，**业务部门此后不从任何
webhook 收消息**。回退一旦命中即等于把机制故障播到业务群——"静默跳过"只是没响，
"发错群"是响在错的人面前，后者更坏，故不留这条回退路径。未配置时仍按既有降级
方式静默跳过（不阻断扫描本身）。
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

#: 🔴 **本入口刻意不声明必需键**（队列 #354 决策点 4 ＝ (c)）——告警 webhook 未配置时
#: **静默跳过、不阻断扫描本身**是本脚本模块 docstring 明写的既定语义（见「告警去向」段）。
#: 把它列进 required 会把「今天没配告警」升级成「今天不扫描」，那是拿摄取去赌告警，
#: **代价方向反了**。本变更包只改「读哪一份 `.env`」，不趁机改这条既定降级语义。
REQUIRED_ENV_KEYS: tuple[str, ...] = ()


def load_env() -> None:
    """读入本次运行该用的那份 `.env`（解析见 `zhuopin_platform.env_anchor`，队列 #354）。

    🔴 **本文件是 #354 的原始举证点**：原实现「向上逐级找最近的 `.env`」，从 linked worktree
    跑时先命中 `.claude/worktrees/<n>/.env` 而**永远到不了仓库根**——实测那份副本里的
    `_OPS` 密钥已陈旧两代，**失败形态是「告警发到一个早已作废的地址、返回码没人看」而不是
    报错**。收拢后由 `--git-common-dir` 规范化到主工作区，worktree 与主工作区必然同解。
    命中路径经 `describe()` 打印进计划任务日志——本脚本每日跑，这一行就是它的凭据来源留痕。
    """
    print(_resolve_and_load_env(__file__, required=REQUIRED_ENV_KEYS).describe())


#: 本告警唯一的去向键——IT 运维部群 webhook（队列 #282 前提①，2026-08-07 已落 `.env`）。
ALERT_WEBHOOK_ENV = "WECOM_WEBHOOK_URL_OPS"

#: 未解析记录的 stdout 打印上限——超出部分只进 JSONL。真实数据上这批是 26,000 行
#: 起步（队列 #418 ⑺），全量打印只会把这一整段淹掉，反而更看不见。
_DIAG_PRINT_LIMIT = 50


def resolve_alert_webhook(env) -> str | None:
    """取告警 webhook：**只认 `WECOM_WEBHOOK_URL_OPS`，不回退裸 `WECOM_WEBHOOK_URL`**。

    理由见模块 docstring「告警去向」段：裸键指向业务部门群，回退命中即为发错群。
    """
    url = (env.get(ALERT_WEBHOOK_ENV) or "").strip()
    return url or None


def main() -> int:
    load_env()
    ap = argparse.ArgumentParser(description="税务导出发票明细 Excel 定时扫描（队列 #82 第2层）")
    ap.add_argument("--export-dir", required=True, help="税务导出 Excel 所在目录（如 D:\\airead）")
    ap.add_argument("--out-dir", default=str(_ROOT / "data" / "tax_export"),
                     help="产出 invoice.csv 的目录（即传给 FeedSource 的 invoice_sample_dir）")
    ap.add_argument("--ledger", default=None,
                     help="已处理清单路径（默认 <out-dir>/.processed_exports.json）")
    ap.add_argument("--silence-workdays", type=int, default=None,
                     help="源头断供阈值：连续多少个工作日无新文件即告警（默认 3）")
    args = ap.parse_args()

    from fi2.tax_export_ingest import summarize_diagnostics, write_diagnostics_jsonl
    from fi2.tax_export_scan import SILENCE_WORKDAYS_DEFAULT, ScanFailedError, scan_once
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
    webhook_url = resolve_alert_webhook(os.environ)

    silence_workdays = (args.silence_workdays if args.silence_workdays is not None
                        else SILENCE_WORKDAYS_DEFAULT)

    try:
        outcome = scan_once(args.export_dir, out_dir, ledger_path, conn, now=now,
                             webhook_url=webhook_url, silence_workdays=silence_workdays)
    except ScanFailedError as e:
        print(f"扫描异常：{e.outcome.scan_error}", file=sys.stderr)
        if e.outcome.alert_sent:
            print("已发送 webhook 告警。", file=sys.stderr)
        elif webhook_url:
            print(f"webhook 告警发送失败：{e.outcome.alert_error}", file=sys.stderr)
        else:
            print(f"{ALERT_WEBHOOK_ENV} 未配置，未发送告警。", file=sys.stderr)
        return 1

    result = outcome.result
    print(f"新处理文件：{result.files_processed}")
    print(f"跳过（已处理过）：{result.files_skipped}")
    print(f"成功解析行数：{len(result.resolved_rows)}")
    # 队列 #371：跨文件重复发票被闸掉的行数——预期内的正常现象（她的导出区间会重叠），
    # 故不告警、不计非零退出码；但**必须打印**，否则又是一个「静默」。
    print(f"跳过重复发票行数：{result.duplicate_rows_skipped}"
          f"（涉 {len(result.duplicate_invoice_nos)} 张发票，"
          "该发票号已由此前文件贡献过——预期内，非故障）")

    # 队列 #418：未解析行重试。🔴 定时扫描才是每日真正跑的那条路径——那 4 张假
    # 「无发票支撑」就是从这里进的库，只在手动 CLI 打印等于没打印。
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
        # 🔴 源文件已删/已改 ⇒ 这些发票永远进不来，面板会持续把对应 AP 单报为
        # 「无发票支撑」。必须出声——沉默正是 #418 那批假报当初的潜伏方式。
        # ⚠️ 「要不要为此发 webhook 告警／算不算文件级失败」属告警口径，本次不自定，
        # 已登队列 #418 待业务总线定（现行为：如实打印，不改退出码、不新增告警触发）。
        print(f"🔴 无法再重试：{result.unretryable_unresolved} 行 —— 源文件已不在盘上"
              f"或内容已变更：{result.unretryable_files}。"
              "这些发票将永远不会进入 invoice.csv，面板会持续把对应 AP 单报为"
              "「无发票支撑」。须把原导出文件放回导出目录后重跑。", file=sys.stderr)

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

    def _report_alert() -> None:
        if outcome.alert_sent:
            print("已发送 webhook 告警。", file=sys.stderr)
        elif webhook_url:
            print(f"webhook 告警发送失败：{outcome.alert_error}", file=sys.stderr)
        else:
            print(f"{ALERT_WEBHOOK_ENV} 未配置，未发送告警。", file=sys.stderr)

    if outcome.file_level_failures:
        print(f"⚠️ 文件级摄取失败 {len(outcome.file_level_failures)} 处", file=sys.stderr)
        _report_alert()
        return 1

    if outcome.source_silence is not None:
        s = outcome.source_silence
        print(f"⚠️ 源头断供：已连续 {s.workdays_silent} 个工作日无新增导出文件"
              f"（阈值 {s.threshold}），最后一次成功摄取 {s.last_ingest_at}（UTC）。"
              "扫描机制本身正常，是源头没有新文件。", file=sys.stderr)
        _report_alert()
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
