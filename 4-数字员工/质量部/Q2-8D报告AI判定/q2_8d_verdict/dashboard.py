"""Q2 8D 判定综合仪表盘（档 1 ＝ 汇总结构 ＋ Markdown 清单；门户页 `/quality/q2` 消费本模块）。

一屏汇总：七维（D1–D7）得分／满分聚合、A/B/C/D 分级分布（含语义层待人工的区间桶）、
结构性退回与红线命中清单、处置建议分布。

🔴 本模块只做汇总聚合，不新写判据、不改评分口径——数字全部来自 `Verdict`／`RuleFinding`
（引擎已按 `config.CRITERIA` 算好），本文件不得再对分数做任何变换。
"""
from __future__ import annotations

from collections import Counter

from .models import Verdict

STEPS = ("D1", "D2", "D3", "D4", "D5", "D6", "D7")   # 七维：D0/D8 已豁免（J2），不入统计
PENDING_BUCKET = "区间（待人工）"
GRADE_ORDER = ("A", "B", "C", "D", PENDING_BUCKET)


def summarize(verdicts: list[Verdict]) -> dict:
    by_grade = Counter((v.grade or PENDING_BUCKET) for v in verdicts)
    by_disposition = Counter(v.disposition.value for v in verdicts)
    by_step: dict[str, dict[str, float]] = {s: {"auto": 0.0, "max": 0.0} for s in STEPS}
    for v in verdicts:
        for f in v.rules:
            if f.step in by_step:
                by_step[f.step]["auto"] += f.score
                by_step[f.step]["max"] += f.max_score
    for s in STEPS:
        by_step[s]["auto"] = round(by_step[s]["auto"], 2)
        by_step[s]["max"] = round(by_step[s]["max"], 2)
    structural_returns = [
        {"report_id": v.report_id, "empty_sections": list(v.structural_empty_sections)}
        for v in verdicts if v.structural_return
    ]
    redline_hits = [
        {"report_id": v.report_id, "redline_no": r.redline_no, "status": r.status.value}
        for v in verdicts for r in v.redlines if r.status.value != "未触发"
    ]
    return {
        "total": len(verdicts),
        "by_grade": {g: by_grade.get(g, 0) for g in GRADE_ORDER},
        "by_step": by_step,
        "by_disposition": dict(by_disposition),
        "structural_returns": structural_returns,
        "redline_hits": redline_hits,
    }


def render_markdown(verdicts: list[Verdict], *, rule_version: str, automation_level: str) -> str:
    s = summarize(verdicts)
    lines = [
        f"# Q2 · 8D 判定汇总（{automation_level}，AI 只出评级与建议；规则版本 {rule_version}）",
        "",
        "> 🔴 本清单为 mock 数据汇总，非真实 8D 评审结论；退回决定永远由质量工程师签发。",
        "",
        "## 七维得分（D1–D7，已自动判定部分；语义层待人工部分不计入）",
        "| 维度 | 自动得分 | 满分 |", "|---|---:|---:|",
        *[f"| {k} | {v['auto']} | {v['max']} |" for k, v in s["by_step"].items()],
        "",
        "## 分级分布（A/B/C/D，含语义层待人工区间桶）",
        "| 分级 | 份数 |", "|---|---:|",
        *[f"| {g} | {n} |" for g, n in s["by_grade"].items()],
        "",
        "## 处置建议分布",
        "| 建议 | 份数 |", "|---|---:|",
        *[f"| {d} | {n} |" for d, n in s["by_disposition"].items()],
    ]
    if s["structural_returns"]:
        lines += ["", "## 结构性退回（判例 9）"]
        lines += [f"- **{r['report_id']}**：{r['empty_sections']} 整段为空" for r in s["structural_returns"]]
    if s["redline_hits"]:
        lines += ["", "## 红线命中"]
        lines += [f"- **{r['report_id']}** 红线{r['redline_no']}：{r['status']}" for r in s["redline_hits"]]
    return "\n".join(lines) + "\n"
