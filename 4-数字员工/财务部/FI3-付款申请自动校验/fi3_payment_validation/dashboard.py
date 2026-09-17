"""FI3-7 付款申请综合校验仪表盘（档 1 ＝ 汇总结构 ＋ Markdown 清单；门户页 `/finance/fi3` 留档 2）。

一屏汇总：四态计数／各子场景命中计数／拦截与特批明细（可穿透到 req_no ＋ 发现）／到期日清单。
🔴 账号只以尾 4 位出现（发现里的 evidence 已在检查器脱敏，本模块不再接触原始账号）。
"""
from __future__ import annotations

from collections import Counter

from . import config
from .validation_engine import OUTCOME_BLOCK, OUTCOME_PASS, OUTCOME_REMIND, OUTCOME_SPECIAL
from .models import ValidationVerdict

OUTCOMES = (OUTCOME_PASS, OUTCOME_REMIND, OUTCOME_BLOCK, OUTCOME_SPECIAL)


def summarize(verdicts: list[ValidationVerdict]) -> dict:
    by_outcome = Counter(v.outcome for v in verdicts)
    by_check = Counter(f.check_id for v in verdicts for f in v.findings)
    by_level = Counter(f.level for v in verdicts for f in v.findings)
    return {
        "rule_version": config.RULE_VERSION,
        "automation_level": config.AUTOMATION_LEVEL,
        "total": len(verdicts),
        "by_outcome": {o: by_outcome.get(o, 0) for o in OUTCOMES},
        "by_check": dict(sorted(by_check.items())),
        "by_level": dict(by_level),
        "blocked": [{"req_no": v.req_no, "reasons": [f.reason for f in v.findings if f.level == config.LEVEL_BLOCK]}
                    for v in verdicts if v.outcome == OUTCOME_BLOCK],
        "special": [{"req_no": v.req_no, **v.special_approval} for v in verdicts if v.outcome == OUTCOME_SPECIAL],
        "due_dates": [{"req_no": v.req_no, "due_date": v.due_date} for v in verdicts if v.due_date],
    }


def render_markdown(verdicts: list[ValidationVerdict]) -> str:
    s = summarize(verdicts)
    lines = [
        f"# FI3 付款申请校验清单（{s['automation_level']} 建议 · 规则 {s['rule_version']}）",
        "",
        "> 🔴 本清单只是校验建议，付款执行永远由人在 U9C／银企系统完成。",
        "",
        "| 结果态 | 数量 |", "|---|---:|",
        *[f"| {o} | {n} |" for o, n in s["by_outcome"].items()],
        "",
        "| 子场景 | 命中 |", "|---|---:|",
        *[f"| {c} | {n} |" for c, n in s["by_check"].items()],
        "",
        "## 逐单明细",
    ]
    for v in verdicts:
        lines.append(f"- **{v.req_no}** {v.outcome}" + (f" · 到期 {v.due_date}" if v.due_date else ""))
        for f in v.findings:
            lines.append(f"  - [{f.check_id}·{f.level}] {f.reason}")
        if v.special_approval:
            sa = v.special_approval
            lines.append(f"  - 🟣 {sa['tag']}：{sa['approver']} 批，{sa['backfill_deadline']} 前补齐，入《{sa['tracking_list']}》")
    return "\n".join(lines) + "\n"
