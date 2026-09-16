"""sweep／lint／扫描器共享输出层（队列 §一 #597 ⑵）。

只改输出**形态**，不改任何判据：成功路径（退出码 0）默认只打印摘要
（≤20 行），全文另写 `reports/output-throttle/<tool_name>/<时间戳>.log`
并在摘要末尾回显该路径；`--verbose` 时保留旧行为（整段原样打印，不
写摘要、不截断）。失败／警告路径（退出码非 0）不受影响，一律整段原样
打印——`失败／警告／豁免信息全量保留`（本行 opener 引导语原话），因为
那正是排障需要的东西。

用法（各工具 `main()` 内，原逻辑不动，只把"整段打印"这一步换成调用
本模块）：

    from _输出截流 import emit

    ...原有 print(...) 全部改成 append 进 lines: list[str]...
    return emit("工具-密钥扫描lint", lines, exit_code, verbose=args.verbose)

或者对已有"先攒 list[str]、最后 print('\\n'.join(...))"这种写法
（如 `工具-落库sweep.py` 的 `log`），直接：

    print("\\n".join(log)) if verbose_or_nonzero else emit(...)

`emit()` 本身只负责"摘要 vs 全文"的裁决与落盘，不接管调用方已有的
"是否打印""退出码是什么"这些判断——调用方仍自己决定何时调用它。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

REPORTS_SUBDIR = "reports/output-throttle"
SUMMARY_LINE_CAP = 19  # 摘要内容行上限；连同一行回显路径合计 ≤20 行。


def _repo_root_from_here() -> Path:
    return Path(__file__).resolve().parents[1]


def write_full_report(tool_name: str, lines: list[str], *, repo_root: Path | None = None) -> Path:
    """把全文写入 reports/output-throttle/<tool_name>/<时间戳>.log，返回落点路径。"""
    root = repo_root or _repo_root_from_here()
    report_dir = root / REPORTS_SUBDIR / tool_name
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    report_path = report_dir / f"{ts}.log"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def summarize(lines: list[str], report_path: Path) -> list[str]:
    """把全文行裁成 ≤20 行摘要：优先保留告警/失败/豁免类信号行，
    不足则按原顺序补齐，末尾恒附回显路径行。"""
    signal_prefixes = ("⚠", "✗", "🔴", "🟡")
    signal_lines = [ln for ln in lines if ln.strip().startswith(signal_prefixes)]

    body = signal_lines[:SUMMARY_LINE_CAP]
    if len(body) < SUMMARY_LINE_CAP:
        for ln in lines:
            if len(body) >= SUMMARY_LINE_CAP:
                break
            if ln not in body:
                body.append(ln)

    omitted = len(lines) - len(body)
    if omitted > 0:
        body.append(f"…（其余 {omitted} 行已省略，全文见 {report_path}）")
    else:
        body.append(f"（全文已存 {report_path}）")
    return body


def emit(
    tool_name: str,
    lines: list[str],
    exit_code: int,
    *,
    verbose: bool = False,
    repo_root: Path | None = None,
) -> int:
    """成功（exit_code == 0）且非 --verbose 时输出摘要＋落盘全文；
    其余情形整段原样打印（旧行为）。返回值＝传入的 exit_code，方便
    调用方写成 `return emit(...)`。"""
    if verbose or exit_code != 0:
        print("\n".join(lines))
        return exit_code

    report_path = write_full_report(tool_name, lines, repo_root=repo_root)
    for line in summarize(lines, report_path):
        print(line)
    return exit_code
