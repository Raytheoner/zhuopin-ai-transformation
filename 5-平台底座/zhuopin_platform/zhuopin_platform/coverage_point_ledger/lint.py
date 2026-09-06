"""台账目录 lint —— **目录下不得出现子目录**（D8，断言测试 ＝ tasks §1.6）。

## 为什么这件事需要一条 lint

`.gitignore` 第 32 行 `**/*.jsonl` 把所有运行时审计 JSONL 挡在库外；D7 在其**之后**
开了一条范围严格限定的例外：

    !6-人才与组织/部门AI专员跟进/口径点台账/*.jsonl

🔴 **`!` 例外不递归**（审材料 §6.3 第 4 条对照组实测，真仓库 `OP-0906-Q` 已复现）：
子目录里的 `.jsonl` 仍会被 `**/*.jsonl` 吞掉 —— **不报错、不提示、`git add` 也不抱怨，
文件就是进不了库**。等到有人发现「台账里怎么少了一个域」，中间写进去的事实已经
只存在于某台机器的本地磁盘上。

⇒ 又一个「错误不产生任何信号」。这类错误只有主动去找的 lint 能拦，写在文档里没用。

## 顺带查的第二件事

除五份域文件外的其它 `.jsonl` 也会被例外放行（例外是 `*.jsonl` 而非五个文件名），
故一并报出来 —— 不是违规，是提醒：**多出来的那份 `.jsonl` 会静默入库**。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import LedgerLintError
from .models import Domain


@dataclass(frozen=True)
class LintFinding:
    """一条发现。`fatal=True` 的会让 `assert_clean()` 抛。"""

    kind: str
    path: str
    detail: str
    fatal: bool


@dataclass(frozen=True)
class LintReport:
    ledger_dir: str
    findings: tuple[LintFinding, ...]

    @property
    def fatal(self) -> tuple[LintFinding, ...]:
        return tuple(f for f in self.findings if f.fatal)

    @property
    def ok(self) -> bool:
        return not self.fatal

    def render(self) -> str:
        if not self.findings:
            return f"✅ {self.ledger_dir}：目录布局合规（无子目录、五份域文件平铺）"
        lines = [f"台账目录 lint：{self.ledger_dir}"]
        for f in self.findings:
            lines.append(f"  {'❌' if f.fatal else '⚠️'} [{f.kind}] {f.path} —— {f.detail}")
        return "\n".join(lines)


def lint_ledger_dir(ledger_dir: Path | str) -> LintReport:
    """检查台账目录布局，返回报告（**不抛**；要抛用 `assert_clean()`）。

    三类发现：

      · ``子目录``（fatal，D8）—— 目录下任何子目录。
      · ``域文件缺失``（fatal）—— 五份域文件之一不存在。缺一份 ＝ 那个域的点
        无处可写，而 `LedgerStore.append` 会顺手建出来、不报警。
      · ``意外jsonl``（非 fatal）—— 五份之外的 `.jsonl`，会被 `!` 例外一并放行入库。
    """
    root = Path(ledger_dir)
    findings: list[LintFinding] = []

    if not root.is_dir():
        return LintReport(
            ledger_dir=str(root),
            findings=(
                LintFinding(
                    kind="目录不存在",
                    path=str(root),
                    detail="台账目录不存在；先跑 LedgerStore.initialize() 建五份空域文件",
                    fatal=True,
                ),
            ),
        )

    expected = {d.filename for d in Domain}

    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if entry.is_dir():
            inner = sorted(p.name for p in entry.rglob("*.jsonl"))
            detail = (
                f"D8：台账目录下不得建子目录。`.gitignore` 的 `!` 例外**不递归**，"
                f"其中的 .jsonl 会被 `**/*.jsonl` 静默忽略"
            )
            if inner:
                detail += f"；本子目录内已有 {len(inner)} 个 .jsonl（{inner[:5]}），它们此刻并未入库"
            findings.append(
                LintFinding(kind="子目录", path=str(entry), detail=detail, fatal=True)
            )
        elif entry.suffix == ".jsonl" and entry.name not in expected:
            findings.append(
                LintFinding(
                    kind="意外jsonl",
                    path=str(entry),
                    detail=(
                        f"不是五份域文件之一，但 `!…/*.jsonl` 例外会把它一并放行入库。"
                        f"合法域文件：{sorted(expected)}"
                    ),
                    fatal=False,
                )
            )

    for filename in sorted(expected):
        if not (root / filename).is_file():
            findings.append(
                LintFinding(
                    kind="域文件缺失",
                    path=str(root / filename),
                    detail="五份域文件须平铺齐全（D2）；缺一份则该域的点无处可写",
                    fatal=True,
                )
            )

    return LintReport(ledger_dir=str(root), findings=tuple(findings))


def assert_clean(ledger_dir: Path | str) -> LintReport:
    """lint 不过即抛 `LedgerLintError`（供 CI／收工自检直接调用）。"""
    report = lint_ledger_dir(ledger_dir)
    if not report.ok:
        raise LedgerLintError(report.render())
    return report


def main(argv: list[str] | None = None) -> int:
    """命令行入口：``python -m zhuopin_platform.coverage_point_ledger.lint <台账目录>``。"""
    import argparse

    from .store import LEDGER_DIR_RELPATH

    parser = argparse.ArgumentParser(description="口径点台账目录 lint（D8：不得有子目录）")
    parser.add_argument("ledger_dir", nargs="?", default=LEDGER_DIR_RELPATH)
    args = parser.parse_args(argv)

    report = lint_ledger_dir(args.ledger_dir)
    print(report.render())
    return 1 if not report.ok else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
