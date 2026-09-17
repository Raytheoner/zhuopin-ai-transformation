"""CLI：对 mock 样本跑判定，输出 Markdown 清单 ＋ 审计 JSONL（reports/，gitignore）。

用法：python -m q2_8d_verdict.run [--source mock] [--out reports/]
"""
from __future__ import annotations

import sys
from pathlib import Path

# —— 平台底座路径引导（唯一被允许的样板，见 bootstrap.py docstring；服务/CLI 入口不带 strict）——
_HERE = Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        sys.path.insert(0, str(_p / "5-平台底座" / "zhuopin_platform"))
        break
from zhuopin_platform.bootstrap import ensure_paths  # noqa: E402
ensure_paths(__file__, _HERE.parent.parent)  # noqa: E402

import argparse  # noqa: E402

from zhuopin_platform.audit import AuditLogger, JsonlSink  # noqa: E402

from q2_8d_verdict import config, feed_source  # noqa: E402
from q2_8d_verdict.engine import VerdictEngine  # noqa: E402
from q2_8d_verdict.models import Verdict  # noqa: E402


def render_markdown(verdicts: list[Verdict]) -> str:
    lines = [f"# Q2 · 8D 判定清单（{config.AUTOMATION_LEVEL}，AI 只出评级与建议；规则版本 {config.RULE_VERSION}）", "",
             "| 报告 | 场景 | 结构闸 | 红线 | 自动得分 | 上界 | 等级/区间 | 处置建议 |", "|---|---|---|---|---|---|---|---|"]
    for v in verdicts:
        rl = "、".join(f"{r.redline_no}{'🔴' if r.status.value.startswith('触发') else ('🟡' if '疑似' in r.status.value else '⚪')}" for r in v.redlines) or "—"
        g = v.grade or f"{v.grade_range[0]}–{v.grade_range[1]}"
        lines.append(f"| {v.report_id} | {v.scene}{' ⚠' if v.scene_flags else ''} | {'退回' if v.structural_return else '过'} | {rl} | {v.score_auto} | {v.score_upper}/{v.score_max} | {g} | {v.disposition.value} |")
    lines += ["", "说明：🔴 触发（自动判 D）／🟡 疑似·转人工／⚪ 未触发或转人工核；等级区间＝语义层待人工时的下界–上界。"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default=config.DATA_SOURCE_DEFAULT)
    ap.add_argument("--out", default=str(_HERE.parent.parent / "reports"))
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    engine = VerdictEngine(audit=AuditLogger(JsonlSink(out / "q2_audit.jsonl")))
    verdicts = [engine.evaluate(doc) for doc, _ in feed_source.load(a.source)]
    md = render_markdown(verdicts)
    (out / "q2_verdicts.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
