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

队列 §一 #637（Shao Peishen 2026-09-21 答 `1b`）：某些"零命中也回显"的
承诺行（如各常驻状态告警类的每轮首行）不带 `⚠/✗/🔴/🟡` 信号前缀，
`summarize()` 原实现只按前缀猜测该保留谁，名额一满就把它们静默挤掉
——"没打印"与"没跑"在屏幕上长得一模一样。**不走扩前缀集**（那只能
挡住已知的这一批，下一个新类目照样复发），改让调用方在 `log.append`
那一刻用 `must_keep()` 显式声明"本行不许被摘要裁"：

    log.append(must_keep("🧭 XX 扫描（每轮回显，零命中亦不省略）：..."))

`summarize()` 保证 must-keep 行**无条件全部保留**，不占用信号行／
普通行的名额；这意味着 must-keep 行本身若多于 `SUMMARY_LINE_CAP`，
摘要总行数**允许超出 19 行**——这是刻意选择，见 `summarize()` 判据：
must-keep 存在的唯一理由就是"这一类到底跑没跑"必须可见，让摘要多打
几行远比再次静默丢掉信号安全。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

REPORTS_SUBDIR = "reports/output-throttle"
SUMMARY_LINE_CAP = 19  # 摘要内容行上限（must-keep 行不占用此名额，见 must_keep()）。

# 队列 §一 #637：must-keep 行标记。选一个不可能出现在正常日志文本里的
# 控制字符组合，`summarize()` 据此识别并无条件保留，其余场景（`--verbose`／
# 失败路径整段打印）不解析该标记，直接原样打印——为免真的把控制字符甩到
# 终端／落盘全文里，`emit()` 在那两条路径也会先行剥离标记。
_MUST_KEEP_MARKER = "\x00MUST-KEEP\x00"


def must_keep(line: str) -> str:
    """标记一行"不许被 summarize() 的摘要名额挤掉"（队列 §一 #637）。

    用在调用方 `log.append(must_keep(...))` 那一刻——判据在写入现场
    显式声明，不靠 `summarize()` 事后用前缀猜。
    """
    return f"{_MUST_KEEP_MARKER}{line}"


def _strip_must_keep(line: str) -> tuple[bool, str]:
    if line.startswith(_MUST_KEEP_MARKER):
        return True, line[len(_MUST_KEEP_MARKER):]
    return False, line


def strip_must_keep(line: str) -> str:
    """去掉 `must_keep()` 标记、只留原文——供不经过 `emit()` 的落盘/打印
    路径使用（如 `工具-落库sweep.py::_flush_log` 把 `log` 原样追加进常驻
    审计日志 `reports/sweep-commit.log`，不是走 `emit()` 那条摘要路径）。"""
    return _strip_must_keep(line)[1]


def _repo_root_from_here() -> Path:
    return Path(__file__).resolve().parents[1]


def write_full_report(tool_name: str, lines: list[str], *, repo_root: Path | None = None) -> Path:
    """把全文写入 reports/output-throttle/<tool_name>/<时间戳>.log，返回落点路径。"""
    root = repo_root or _repo_root_from_here()
    report_dir = root / REPORTS_SUBDIR / tool_name
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    report_path = report_dir / f"{ts}.log"
    clean_lines = [_strip_must_keep(ln)[1] for ln in lines]
    report_path.write_text("\n".join(clean_lines) + "\n", encoding="utf-8")
    return report_path


def summarize(lines: list[str], report_path: Path) -> list[str]:
    """把全文行裁成「must-keep 行数 ＋ ≤20 行」摘要（Shao Peishen 2026-09-22 答 `1a` 放开原 ≤20 硬上限）：`must_keep()` 标记行无条件全部保留、
    不占名额（队列 §一 #637），剩余名额按原逻辑优先保留告警/失败/
    豁免类信号行，不足则按原顺序补齐，末尾恒附回显路径行。"""
    signal_prefixes = ("⚠", "✗", "🔴", "🟡")

    must_keep_lines: list[str] = []
    other_lines: list[str] = []
    for ln in lines:
        is_must_keep, text = _strip_must_keep(ln)
        (must_keep_lines if is_must_keep else other_lines).append(text)

    # 队列 §一 `#637` 六关④ 实证修正（2026-09-21 `Win-0921-A`）：此处原为
    # `SUMMARY_LINE_CAP - len(must_keep_lines)`，与第 47 行注释「must-keep 行不占用
    # 此名额」自相矛盾——十余条常驻表头被保住后 remaining_cap 只剩 7，正文被挤掉。
    # 实撞：`ResidentServiceDeploymentHintTests::test_batch_touching_resident_service_path_gets_hint`
    # 断言的 `ZhuopinAibotDevListener` 那行（表头 `⚠ 本批改动涉及常驻服务运行体` 在、
    # 点名正文被裁）。must-keep 是「保住表头」，不该以「挤掉正文」为代价。
    remaining_cap = SUMMARY_LINE_CAP
    signal_lines = [ln for ln in other_lines if ln.strip().startswith(signal_prefixes)]

    body = list(must_keep_lines)
    fill = signal_lines[:remaining_cap]
    if len(fill) < remaining_cap:
        for ln in other_lines:
            if len(fill) >= remaining_cap:
                break
            if ln not in fill:
                fill.append(ln)
    body.extend(fill)

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
    其余情形整段原样打印（旧行为，`must_keep()` 标记不生效——反正整段
    都保留，标记字符先剥掉，不让控制字符漏进终端）。返回值＝传入的
    exit_code，方便调用方写成 `return emit(...)`。"""
    if verbose or exit_code != 0:
        print("\n".join(_strip_must_keep(ln)[1] for ln in lines))
        return exit_code

    report_path = write_full_report(tool_name, lines, repo_root=repo_root)
    for line in summarize(lines, report_path):
        print(line)
    return exit_code
