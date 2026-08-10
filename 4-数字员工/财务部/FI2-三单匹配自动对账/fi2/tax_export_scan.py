"""税务导出 Excel 定时扫描 + 失败告警（队列 #82 第2层收尾，2026-08-10）。

Layer 1（队列 #295，已建成）：`tax_export_ingest.ingest_directory` 提供"扫描目录→
跳过已处理→解析→ap_no/item_code 反查→产出"的核心能力，手动触发
（`scripts/ingest_tax_export.py`，Q3 拍板"不挂定时"）。本模块＝Layer 2：把 Layer 1
包成可被 Windows 计划任务每日调度的形态，只加两件 Layer 1 本身不做的事——不改
`ingest_directory`/`write_invoice_csv`（原样复用，判据零改动）。

① **失败判定**：区分"文件级摄取失败"（`sheet_missing`／`field_missing`／
`parse_error`——今天 #82 sheet 名事故正是这一类：12 个真实文件 100% 摄取失败，
但手动 CLI 本身退出码仍是 0，无人会注意到）与"行级诊断"（`ap_no_zero_match` 等，
真实数据里约 89% 属不经 U9C PO/GR/AP 链路的服务类发票，是预期噪声、非故障，见
队列 #82 08-10 回填）。只有前者才算"扫描失败"、需要人为介入，才触发告警——不对
行级诊断发告警，否则告警会被真实数据的高噪声比例淹没，形同虚设。

② **告警**：命中文件级失败（或 `ingest_directory` 本身抛异常，如 U9C 连接/目录
不可达）时，经既有群 webhook 逃生通道通知 Shao Peishen（`WECOM_WEBHOOK_URL`，同
`wecom-aibot-service/scripts/alert_webhook.py`/`decision_reminder.py` 既定判据——
本告警主题是"自动化机制自身出问题"，不是业务内容，按
`3-治理与合规/通知通道架构决策件-webhook退役与aibot单一出口-2026-08-06.md` §4.2
判据走 webhook 逃生通道，不经 aibot、不直接触达唐燕萍）。webhook 未配置时静默
跳过告警本身（不阻断扫描），同 `alert_webhook.py` 既有降级方式；告警发送失败
（网络故障等）同样不得掩盖扫描本身已完成的事实，只记录 `alert_error` 供调用方
如实呈现，不向上抛出掩盖扫描结果。
"""
from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Callable

from .tax_export_ingest import IngestDiagnostic, IngestResult, ingest_directory, write_invoice_csv

# 文件级失败：整份文件解析不出任何行、需人工核查（结构性问题）。不含行级诊断
# （ap_no_zero_match/ap_no_ambiguous/item_code_zero_match/item_code_ambiguous/
# digital_invoice_no_missing）——那些是真实数据的正常噪声，见模块 docstring。
_FILE_LEVEL_REASONS = frozenset({"parse_error", "sheet_missing", "field_missing"})

_DEFAULT_ALERT_HEADER = "⚠️ FI2 税务导出摄取扫描告警"


@dataclasses.dataclass
class ScanOutcome:
    result: IngestResult | None = None
    file_level_failures: list[IngestDiagnostic] = dataclasses.field(default_factory=list)
    scan_error: str = ""          # ingest_directory 本身抛出异常时的描述（扫描未完成）
    alert_sent: bool = False
    alert_error: str = ""


def file_level_failures(result: IngestResult) -> list[IngestDiagnostic]:
    """从摄取结果中筛出"文件级"诊断——见模块 docstring 的判据。"""
    return [d for d in result.diagnostics if d.reason in _FILE_LEVEL_REASONS]


def build_alert_message(*, export_dir, failures: list[IngestDiagnostic] | None = None,
                         scan_error: str = "") -> str:
    """组装告警正文（纯文本，webhook `send_text`/`send_markdown` 均可用）。

    两种触发源二选一：`scan_error`（`ingest_directory` 本身抛异常，扫描未完成）
    优先；否则按 `failures`（扫描完成但部分文件解析失败）组装。
    """
    lines = [_DEFAULT_ALERT_HEADER, f"目录：{export_dir}"]
    if scan_error:
        lines.append("扫描本身未能完成（异常）：")
        lines.append(f"  {scan_error}")
        return "\n".join(lines)

    failures = failures or []
    lines.append(f"文件级摄取失败 {len(failures)} 处（结构性问题，需人工核查，"
                  "非常规未匹配行——常规行级未匹配不在此告警范围）：")
    for d in failures[:10]:
        lines.append(f"- [{d.reason}] {d.file}" + (f"：{d.detail}" if d.detail else ""))
    if len(failures) > 10:
        lines.append(f"...另有 {len(failures) - 10} 处，详见服务器日志")
    return "\n".join(lines)


def _default_sender(webhook_url: str, content: str) -> None:
    from zhuopin_platform.shared_tools.notifiers import wecom
    wecom.send_text(webhook_url, content)


def _try_alert(webhook_url: str | None, content: str,
                sender: Callable[[str, str], None] | None) -> tuple[bool, str]:
    """告警发送尝试——失败不得向上抛出（告警自身故障不能掩盖/中断扫描主流程）。
    未配置 webhook 时视为"未尝试"，返回 (False, "")，同既有降级方式（不视为错误）。
    """
    if not webhook_url:
        return False, ""
    send = sender or _default_sender
    try:
        send(webhook_url, content)
        return True, ""
    except Exception as exc:  # noqa: BLE001 —— 告警通道本身的任何故障均不得中断调用方
        return False, str(exc)


def scan_once(
    export_dir: Path | str, out_dir: Path | str, ledger_path: Path | str, connector, *,
    now: str, webhook_url: str | None = None,
    sender: Callable[[str, str], None] | None = None,
) -> ScanOutcome:
    """Layer 2 编排：跑一次 `ingest_directory`（原样复用，见模块 docstring）→
    产出 `invoice.csv`（若有新解析行）→ 判定是否命中文件级失败 → 命中则告警。

    `ingest_directory` 本身抛异常（如 U9C 连接失败/目录不可达）时，本函数捕获、
    尝试告警、然后原样重新抛出——调用方（CLI）据此以非零退出码结束，使计划任务
    的"上次运行结果"也留下可见信号（告警是第一层防线，任务历史是第二层，双保险，
    不互斥）。
    """
    try:
        result = ingest_directory(export_dir, ledger_path, connector, now=now)
    except Exception as exc:  # noqa: BLE001 —— 扫描异常需如实告警，但不得吞掉，向上抛出
        alert_sent, alert_error = _try_alert(
            webhook_url, build_alert_message(export_dir=export_dir, scan_error=str(exc)), sender)
        outcome = ScanOutcome(result=None, scan_error=str(exc),
                               alert_sent=alert_sent, alert_error=alert_error)
        raise ScanFailedError(outcome) from exc

    if result.resolved_rows:
        write_invoice_csv(result.resolved_rows, Path(out_dir) / "invoice.csv")

    failures = file_level_failures(result)
    outcome = ScanOutcome(result=result, file_level_failures=failures)
    if failures:
        alert_sent, alert_error = _try_alert(
            webhook_url, build_alert_message(export_dir=export_dir, failures=failures), sender)
        outcome.alert_sent = alert_sent
        outcome.alert_error = alert_error
    return outcome


class ScanFailedError(RuntimeError):
    """`ingest_directory` 本身抛异常时的包装异常——携带 `outcome`（含告警是否已
    尝试/是否成功），调用方（CLI）可据此打印诊断信息，而不必只见到原始 traceback。
    """
    def __init__(self, outcome: ScanOutcome):
        super().__init__(outcome.scan_error)
        self.outcome = outcome
