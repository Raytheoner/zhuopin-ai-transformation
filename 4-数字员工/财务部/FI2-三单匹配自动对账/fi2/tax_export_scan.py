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
不可达）时，经群 webhook 逃生通道通知 Shao Peishen（**`WECOM_WEBHOOK_URL_OPS`＝IT
运维部群；2026-08-19 队列 #82 更正——原写的裸 `WECOM_WEBHOOK_URL` 按 #282 指向业务
部门群，键名对不上会把机制故障播到业务群，故调用入口
`scripts/scan_tax_export_scheduled.py` 只读 `_OPS`、不回退**；同
`wecom-aibot-service/scripts/alert_webhook.py`/`decision_reminder.py` 既定判据——
本告警主题是"自动化机制自身出问题"，不是业务内容，按
`3-治理与合规/通知通道架构决策件-webhook退役与aibot单一出口-2026-08-06.md` §4.2
判据走 webhook 逃生通道，不经 aibot、不直接触达唐燕萍）。webhook 未配置时静默
跳过告警本身（不阻断扫描），同 `alert_webhook.py` 既有降级方式；告警发送失败
（网络故障等）同样不得掩盖扫描本身已完成的事实，只记录 `alert_error` 供调用方
如实呈现，不向上抛出掩盖扫描结果。

③ **源头断供检测（2026-08-17 补，队列 #82）**：①②只覆盖"文件来了但摄取不了"，
**完全不覆盖"文件根本没来"**——而后者恰是本行立项动机本身（"她每日投放、我方漏
取一天积压一天"）的对偶形态，且**更隐蔽**：无新文件时扫描一切正常（退出码 0、
零诊断、零告警），机制看起来在健康运行，实际上源头早已断供。**2026-08-17 实测坐实
这不是假想**：`.51` 上 `D:\airead` 自 2026-08-10 13:11 起 5 个工作日零新文件，
`Fi2TaxExportDailyScan` 每天照跑、`LastTaskResult` 恒为 0、`NumberOfMissedRuns=0`，
ledger 20 条与目录 20 个文件精确一致（证明不是"处理后被移走"）——**整整一周无人
知晓，因为没有任何一处会说话**。

故新增：以 ledger 中最大 `processed_at`（即"最后一次真的吃到新文件"的时刻）为锚，
距今超过 `silence_workdays` 个工作日仍无新文件即告警。**刻意复用 ledger 而不新建
状态文件**——它本就逐文件记录了处理时刻，是现成且唯一的真相源（零新增载体）。
**判据只在工作日成立**（周末/节假日空扫不告警，她 08-06 定的投放口径是"工作日上午
10 点前"）；**已知边界**：工作日计算只按周一~周五，不含中国法定节假日，故长假后
可能早报一次（宁可早报不可漏报，且早报的代价只是问一声）。**超阈值即每次告警、不
做递减抑制**——源头断供是需人为动作（问一声）才能解除的状态、不会自愈，属"出现→
解除"骨架的标准形态；且频率上限受计划任务约束（每天至多 1 次），不会刷屏。
"""
from __future__ import annotations

import dataclasses
import datetime
from pathlib import Path
from typing import Callable

from .tax_export_ingest import (
    IngestDiagnostic,
    IngestResult,
    ingest_directory,
    load_ingested_invoice_nos,
    load_ledger,
    write_invoice_csv,
)

# 文件级失败：整份文件解析不出任何行、需人工核查（结构性问题）。不含行级诊断
# （ap_no_zero_match/ap_no_ambiguous/item_code_zero_match/item_code_ambiguous/
# digital_invoice_no_missing）——那些是真实数据的正常噪声，见模块 docstring。
_FILE_LEVEL_REASONS = frozenset({"parse_error", "sheet_missing", "field_missing"})

_DEFAULT_ALERT_HEADER = "⚠️ FI2 税务导出摄取扫描告警"
_SILENCE_ALERT_HEADER = "⚠️ FI2 税务导出源头断供告警"

# 源头断供阈值：连续多少个工作日无新文件即告警。3 个工作日＝大半周没动静，
# 偶尔晚投一天不误报，真断供也不至于拖太久才被发现。见模块 docstring ③。
SILENCE_WORKDAYS_DEFAULT = 3


@dataclasses.dataclass
class SourceSilence:
    """源头断供判定结果——ledger 里"最后一次吃到新文件"距今已超阈值。"""
    last_ingest_at: str            # ledger 中最大 processed_at（ISO，UTC）；从未摄取过则为 ""
    workdays_silent: int           # 距今的工作日数（周一~周五，不含节假日，见 docstring ③）
    threshold: int


@dataclasses.dataclass
class ScanOutcome:
    result: IngestResult | None = None
    file_level_failures: list[IngestDiagnostic] = dataclasses.field(default_factory=list)
    scan_error: str = ""          # ingest_directory 本身抛出异常时的描述（扫描未完成）
    source_silence: SourceSilence | None = None   # 源头断供（None＝未命中/不适用）
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


# ── 源头断供检测（模块 docstring ③）──────────────────────────────────────

def _parse_iso(ts: str) -> datetime.datetime | None:
    """宽松解析 ISO 时间戳；无法解析返回 None（不抛出——ledger 是历史累积数据，
    单条格式异常不该让整次扫描失败）。无时区信息的一律按 UTC 处理：ledger 由
    `scan_tax_export_scheduled.py`/`ingest_tax_export.py` 写入，两者均传
    `datetime.now(timezone.utc).isoformat()`（带 offset），故这只是防御性兜底。
    """
    try:
        dt = datetime.datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None
    return dt.replace(tzinfo=datetime.timezone.utc) if dt.tzinfo is None else dt


def last_ingest_at(ledger: dict) -> str:
    """ledger 中最大的 `processed_at`——"最后一次真的吃到新文件"的时刻。
    空 ledger（从未摄取过任何文件）返回 ""。
    """
    stamps = [v.get("processed_at", "") for v in ledger.values() if isinstance(v, dict)]
    parsed = [(dt, s) for s in stamps if (dt := _parse_iso(s)) is not None]
    return max(parsed)[1] if parsed else ""


def workdays_between(start: datetime.datetime, end: datetime.datetime) -> int:
    """`start` 之后、截至 `end`（含）的工作日数（周一~周五）。

    不含中国法定节假日——已知边界，见模块 docstring ③（长假后可能早报一次，
    宁可早报不可漏报）。`end` 早于 `start` 时返回 0。
    """
    d, last = start.date(), end.date()
    if last <= d:
        return 0
    count = 0
    while d < last:
        d += datetime.timedelta(days=1)
        if d.weekday() < 5:            # 0=周一 … 4=周五
            count += 1
    return count


def detect_source_silence(ledger: dict, now: str, threshold: int) -> SourceSilence | None:
    """判定源头是否已断供超阈值。命中返回 `SourceSilence`，否则 None。

    **只在工作日判定**：周末跑到的扫描一律不告警（她的投放口径是工作日，周末本就
    没有新文件，此时告警纯属噪声）。空 ledger（从未摄取过）同样不告警——那属于
    "还没开始"而非"断供"，两者性质不同，不该用同一条告警混淆。
    """
    now_dt = _parse_iso(now)
    if now_dt is None or now_dt.weekday() >= 5:
        return None

    last = last_ingest_at(ledger)
    last_dt = _parse_iso(last) if last else None
    if last_dt is None:
        return None

    silent = workdays_between(last_dt, now_dt)
    if silent < threshold:
        return None
    return SourceSilence(last_ingest_at=last, workdays_silent=silent, threshold=threshold)


def build_silence_message(*, export_dir, silence: SourceSilence) -> str:
    """组装源头断供告警正文——如实陈述观察到的事实，不代为判断原因、不代拟动作。"""
    return "\n".join([
        _SILENCE_ALERT_HEADER,
        f"目录：{export_dir}",
        f"已连续 {silence.workdays_silent} 个工作日无新增导出文件"
        f"（阈值 {silence.threshold} 个工作日）。",
        f"最后一次成功摄取：{silence.last_ingest_at}（UTC）",
        "",
        "扫描机制本身运行正常（本次扫描无报错），是源头没有新文件。",
        "可能原因需人工确认：导出方停投／投放到了别的目录／导出流程本身中断。",
    ])


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
    silence_workdays: int = SILENCE_WORKDAYS_DEFAULT,
) -> ScanOutcome:
    """Layer 2 编排：跑一次 `ingest_directory`（原样复用，见模块 docstring）→
    产出 `invoice.csv`（若有新解析行）→ 判定是否命中文件级失败 → 命中则告警；
    若本次一个新文件都没有，再判一次源头是否已断供超阈值（docstring ③）。

    `ingest_directory` 本身抛异常（如 U9C 连接失败/目录不可达）时，本函数捕获、
    尝试告警、然后原样重新抛出——调用方（CLI）据此以非零退出码结束，使计划任务
    的"上次运行结果"也留下可见信号（告警是第一层防线，任务历史是第二层，双保险，
    不互斥）。

    **两类告警互斥、文件级失败优先**：既有新文件又同时判断源头断供在逻辑上不可能
    （有新文件即证明源头活着），故只在 `files_processed` 为空时才判源头断供。
    """
    # 发票级幂等闸（队列 #371）：已入库发票号从 invoice.csv 现读，零新增载体。
    # 🔴 定时扫描才是每日真正跑的那条路径——#371 那次翻倍就是从这里进的库，
    # 只修手动 CLI 等于没修。
    invoice_csv = Path(out_dir) / "invoice.csv"
    try:
        result = ingest_directory(
            export_dir, ledger_path, connector, now=now,
            known_invoice_nos=load_ingested_invoice_nos(invoice_csv),
        )
    except Exception as exc:  # noqa: BLE001 —— 扫描异常需如实告警，但不得吞掉，向上抛出
        alert_sent, alert_error = _try_alert(
            webhook_url, build_alert_message(export_dir=export_dir, scan_error=str(exc)), sender)
        outcome = ScanOutcome(result=None, scan_error=str(exc),
                               alert_sent=alert_sent, alert_error=alert_error)
        raise ScanFailedError(outcome) from exc

    if result.resolved_rows:
        write_invoice_csv(result.resolved_rows, invoice_csv)

    failures = file_level_failures(result)
    outcome = ScanOutcome(result=result, file_level_failures=failures)
    if failures:
        alert_sent, alert_error = _try_alert(
            webhook_url, build_alert_message(export_dir=export_dir, failures=failures), sender)
        outcome.alert_sent = alert_sent
        outcome.alert_error = alert_error
        return outcome

    if not result.files_processed:
        silence = detect_source_silence(load_ledger(ledger_path), now, silence_workdays)
        if silence is not None:
            outcome.source_silence = silence
            alert_sent, alert_error = _try_alert(
                webhook_url, build_silence_message(export_dir=export_dir, silence=silence), sender)
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
