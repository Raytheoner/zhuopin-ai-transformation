"""跟进信「往返天数」度量（队列 §一 `#447` ⑵ 的度量侧配套）。

## 它解决的问题

信级往返周期此前**没有脚本**——2026-08-23 的《度量复盘》与 2026-09-01 的
design 审前置取证都是人工解析 README 主表算的。两次算出 **2 天** 与 **7 天**
两个中位数，而 §4.5 查清：**两个都对，也都不是真值**。前者是样本缺失下的值
（慢的那 12 封当时还没转态、不在闭环集里），后者是样本污染下的值（**把补记
日当成了回件日**）。12 封信在 2026-08-23 当天被批量补转态，真实回件日在那一
刻被覆盖式销毁，**全程不产生任何信号**：屏幕上只是一个数字从 2 变成了 7。

⇒ 本脚本与登记 CLI 的 `--fact-date`（`工具-跟进信README登记.py`）是**同一件事
的两半**：那边负责把「事实日」与「补记日」分开写下来，这边负责在算中位数时
**把说不清的样本拎出去单列**，而不是让它们悄悄把中位数拽走。

## 三个桶，各自单列（🔴 本脚本最该被记住的一段）

| 桶 | 含义 | 进中位数？ |
|---|---|---|
| `可算` | 状态尾标里有具体事实日 | ✅ |
| `事实日未知` | 有人**明确记下**「查不出来」 | ❌ 单列 |
| `无标注` | 尾标机制（2026-09-07）之前写的历史行 | ❌ 单列 |

🔴 **`事实日未知` 与 `无标注` 是两回事，不许合并**：前者是「记了，结论是不
知道」，后者是「没记，真实日期未必丢了」。把两者混成一个「缺失」桶，等于把
「没记」洗成「记了不知道」，正是本行要根治的那类信息销毁的温和版本。

⚠️ **可算样本为 0 是当下的正常输出**，不是脚本坏了：尾标 2026-09-07 才上线，
在此之前的 45 行主表全部落在 `无标注` 桶。本脚本**拒绝在可算样本不足时报中位
数**（不是报 0、也不是拿另外两个桶凑数）——一个「没有样本也照样给数」的度量
脚本，就是 §4.5 那两个中位数的制造方式。

## 复用而非重造

- 表格解析：`aibot_service.readme_table.iter_rows`——不新造第二份 README 解析器。
- 状态判据：`zhuopin_platform.shared_tools.followup_gate`。
- 事实日尾标的正则与「哪些状态承载事实日」：importlib 复用
  `工具-跟进信README登记.py`（`FACT_MARK_RE`／`_parse_fact_mark`／
  `FACT_DATE_REQUIRED_PREFIXES`／`FACT_DATE_UNKNOWN`）——**写侧与读侧必须是
  同一份判据**，各写一份的后果是写进去的标读不出来，而且不报错。

## 用法

    python 0-学习与工具/工具-跟进信往返度量.py
    python 0-学习与工具/工具-跟进信往返度量.py --json
    python 0-学习与工具/工具-跟进信往返度量.py --file 6-人才与组织/部门AI专员跟进/README-归档-202609.md
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import sys
from datetime import date
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent

_REGISTRY_SCRIPT = _TOOLS_DIR / "工具-跟进信README登记.py"
_registry_spec = importlib.util.spec_from_file_location(
    "_followup_roundtrip_registry_reuse", _REGISTRY_SCRIPT
)
registry = importlib.util.module_from_spec(_registry_spec)
sys.modules[_registry_spec.name] = registry
_registry_spec.loader.exec_module(registry)

REPO_ROOT: Path = registry.REPO_ROOT
README_REL: str = registry.README_REL
FACT_DATE_UNKNOWN: str = registry.FACT_DATE_UNKNOWN

from aibot_service.readme_table import (  # noqa: E402  （sys.path 已由 registry 引导）
    MAIN_TABLE_SECTION,
    ReadmeTableError,
    column_index,
    iter_rows,
)
from zhuopin_platform.shared_tools import followup_gate  # noqa: E402

# 可算样本低于这个数就不报中位数——两三个样本的中位数只是其中一个样本的值，
# 拿它当「周期」会比不报更误导（§4.1 实测分布是双峰的，小样本必然只落一峰）。
MIN_SAMPLES_FOR_MEDIAN = 5

BUCKET_COMPUTABLE = "可算"
BUCKET_UNKNOWN = FACT_DATE_UNKNOWN
BUCKET_UNMARKED = "无标注"
BUCKET_NA = "不适用"


class MetricError(RuntimeError):
    pass


def _classify_row(number: str, sent_date: str, status_cell: str) -> dict:
    """把一行归入四个桶之一，可算时附往返天数与补记滞后。"""
    normalized = followup_gate.normalize_status(status_cell)
    carries_fact = any(
        normalized.startswith(p) for p in registry.FACT_DATE_REQUIRED_PREFIXES
    )
    item: dict = {"number": number, "sent_date": sent_date, "bucket": BUCKET_NA}
    if not carries_fact:
        # 未发三态／`✅ 无需回复`／`❌ 已作废`：不存在「事实发生在别的一天」。
        item["reason"] = "该状态不承载事实日期"
        return item

    parsed = registry._parse_fact_mark(status_cell)
    if parsed is None:
        item["bucket"] = BUCKET_UNMARKED
        item["reason"] = "尾标机制（2026-09-07）之前写的行——真实日期未必丢了，只是没记"
        return item

    fact_date, recorded_on = parsed
    item["recorded_on"] = recorded_on
    if fact_date == FACT_DATE_UNKNOWN:
        item["bucket"] = BUCKET_UNKNOWN
        item["fact_date"] = FACT_DATE_UNKNOWN
        item["reason"] = "有人明确记下「查不出来」——不得用补记日顶替，故单列"
        return item

    item["bucket"] = BUCKET_COMPUTABLE
    item["fact_date"] = fact_date
    try:
        item["roundtrip_days"] = (
            date.fromisoformat(fact_date) - date.fromisoformat(sent_date)
        ).days
        item["backfill_lag_days"] = (
            date.fromisoformat(recorded_on) - date.fromisoformat(fact_date)
        ).days
    except ValueError as exc:
        # 日期列本身形态坏了 ⇒ 不静默当 0，退回单列并说明。
        item["bucket"] = BUCKET_UNMARKED
        item["reason"] = f"日期解析失败（{exc}）——不猜、不按 0 计"
    return item


def build_report(text: str, source: str) -> dict:
    try:
        rows = iter_rows(text, MAIN_TABLE_SECTION)
    except ReadmeTableError as exc:
        raise MetricError(f"README 表格解析失败：{exc}") from exc
    if not rows:
        raise MetricError("主表没有任何数据行——先怀疑是不是没读到目标文件")

    header = rows[0].header_cells
    number_col = column_index(header, "编号")
    date_col = column_index(header, "日期")
    if number_col is None or date_col is None:
        raise MetricError("主表表头缺「编号」或「日期」列")

    items = []
    for row in rows:
        if len(row.cells) <= max(number_col, date_col, row.status_col_index):
            continue
        items.append(
            _classify_row(
                row.cells[number_col].strip(),
                row.cells[date_col].strip(),
                row.cells[row.status_col_index],
            )
        )

    buckets: dict[str, list[dict]] = {
        BUCKET_COMPUTABLE: [], BUCKET_UNKNOWN: [], BUCKET_UNMARKED: [], BUCKET_NA: [],
    }
    for item in items:
        buckets[item["bucket"]].append(item)

    computable = buckets[BUCKET_COMPUTABLE]
    days = sorted(i["roundtrip_days"] for i in computable)
    lags = sorted(i["backfill_lag_days"] for i in computable)
    enough = len(days) >= MIN_SAMPLES_FOR_MEDIAN
    return {
        "source": source,
        "total_rows": len(items),
        "median_days": statistics.median(days) if enough else None,
        "median_reason": None if enough else (
            f"可算样本 {len(days)} 个 < 下限 {MIN_SAMPLES_FOR_MEDIAN}，拒绝报中位数"
            "——不拿另外两个桶凑数，也不报 0"
        ),
        "samples": days,
        "backfill_lag_median": statistics.median(lags) if enough else None,
        "backfill_lag_max": max(lags) if lags else None,
        "buckets": {name: [i["number"] for i in rows_] for name, rows_ in buckets.items()},
        "counts": {name: len(rows_) for name, rows_ in buckets.items()},
        "items": items,
    }


def render(report: dict) -> str:
    lines = [
        f"跟进信往返天数度量 ｜ 源：{report['source']} ｜ 主表 {report['total_rows']} 行",
        "",
        f"  {BUCKET_COMPUTABLE}：{report['counts'][BUCKET_COMPUTABLE]} 封"
        f"（样本 {report['samples']}）",
    ]
    if report["median_days"] is None:
        lines.append(f"  ⚠️ 中位数未计算——{report['median_reason']}")
    else:
        lines.append(f"  ✅ 往返天数中位数：{report['median_days']} 天")
        lines.append(
            f"  补记滞后：中位 {report['backfill_lag_median']} 天 ／ "
            f"最大 {report['backfill_lag_max']} 天"
        )
    lines += [
        "",
        "🔴 以下两桶各自单列，均不混入中位数（两者不是一回事，不许合并）：",
        f"  · `{BUCKET_UNKNOWN}`（记了，结论是不知道）：{report['counts'][BUCKET_UNKNOWN]} 封"
        f" {report['buckets'][BUCKET_UNKNOWN] or ''}",
        f"  · `{BUCKET_UNMARKED}`（没记；尾标 2026-09-07 才上线，之前的行天然在此）："
        f"{report['counts'][BUCKET_UNMARKED]} 封",
        f"  · `{BUCKET_NA}`（该状态不承载事实日期）：{report['counts'][BUCKET_NA]} 封",
    ]
    if report["counts"][BUCKET_UNMARKED] and report["median_days"] is None:
        lines += [
            "",
            "📌 可算样本为 0 属当下的正常输出，不是脚本坏了：写侧的 `--fact-date`"
            " 2026-09-07 才上线，此后每一次 `set-status` 转态都会给这个桶补一个样本。",
        ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="跟进信往返天数度量（`事实日未知` 与「无标注」各自单列，不混入中位数）"
    )
    parser.add_argument(
        "--file", default=README_REL,
        help="目标文件相对仓库根路径（默认跟进信 README 主表；可指向归档件）",
    )
    parser.add_argument("--json", action="store_true", help="机器消费用")
    args = parser.parse_args(argv)

    path = REPO_ROOT / args.file
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"✗ 读不到 {args.file}（{exc.__class__.__name__}）", file=sys.stderr)
        return 1
    try:
        report = build_report(text, args.file)
    except MetricError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
