"""校准工具 — 预填结果 vs 人工黄金样本，计算字段命中率。

用法：
    from qda_prefill.calibrate import compare_record, batch_report
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .field_extractor import EightDRecord

# 字段名映射（JSON/dict键 → §1.1中文字段名）
_FIELD_NAMES = [
    "案例ID", "客户(脱敏)", "失效现象描述", "不良分类", "安全相关",
    "临时对策(D3)", "根本原因(D4)", "纠正/预防(D5-D7)",
    "关联FMEA条目", "关联物料/供应商", "结案日期", "根因验证有效",
]

# 精确匹配字段（必须完全相等）
_EXACT_FIELDS = {"案例ID", "不良分类", "安全相关", "结案日期", "根因验证有效"}


@dataclass
class FieldHit:
    field: str
    ai_value: str
    golden_value: str
    hit: bool
    score: float   # 0.0-1.0
    method: str    # "exact" | "coverage" | "empty_both"


@dataclass
class RecordComparison:
    source: str
    hits: list[FieldHit]

    @property
    def overall_score(self) -> float:
        if not self.hits:
            return 0.0
        return sum(h.score for h in self.hits) / len(self.hits)

    @property
    def hit_count(self) -> int:
        return sum(1 for h in self.hits if h.hit)


def compare_record(record: EightDRecord, golden: dict[str, str],
                   source: str = "") -> RecordComparison:
    """将单条预填结果与人工黄金样本逐字段对比。"""
    rec_dict = record.to_dict()
    hits: list[FieldHit] = []
    for field in _FIELD_NAMES:
        ai_val = (rec_dict.get(field) or {}).get("value", "").strip()
        golden_val = golden.get(field, "").strip()
        hit, score, method = _compare_field(field, ai_val, golden_val)
        hits.append(FieldHit(field=field, ai_value=ai_val, golden_value=golden_val,
                              hit=hit, score=score, method=method))
    return RecordComparison(source=source, hits=hits)


def _compare_field(field: str, ai: str, golden: str) -> tuple[bool, float, str]:
    if not ai and not golden:
        return True, 1.0, "empty_both"
    if not ai or not golden:
        return False, 0.0, "one_empty"
    if field in _EXACT_FIELDS:
        hit = ai.lower() == golden.lower()
        return hit, 1.0 if hit else 0.0, "exact"
    # 关键词覆盖：人工填写的关键词有多少出现在AI输出中
    golden_tokens = set(_tokenize(golden))
    ai_tokens = set(_tokenize(ai))
    if not golden_tokens:
        return True, 1.0, "empty_golden_tokens"
    coverage = len(golden_tokens & ai_tokens) / len(golden_tokens)
    return coverage >= 0.8, round(coverage, 3), "coverage"


def _tokenize(text: str) -> list[str]:
    """中英文分词（简单版）。"""
    # 英文词
    tokens = re.findall(r"[a-zA-Z0-9]{2,}", text.lower())
    # 中文2-4字组合
    tokens += re.findall(r"[一-龥]{2,4}", text)
    return tokens


def load_golden_csv(path: Path | str) -> list[dict[str, str]]:
    """加载人工黄金样本 CSV，返回字典列表（每条一行）。"""
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


def batch_report(comparisons: list[RecordComparison]) -> str:
    """生成 Markdown 格式的校准报告。"""
    if not comparisons:
        return "无比对结果。"

    # 汇总每字段命中率
    field_scores: dict[str, list[float]] = {f: [] for f in _FIELD_NAMES}
    for comp in comparisons:
        for hit in comp.hits:
            field_scores[hit.field].append(hit.score)

    lines = ["# 8D预填脚本校准报告", "",
             f"**样本数**：{len(comparisons)}",
             "",
             "## 字段命中率", "",
             "| 字段 | 命中率 | 方法 | 建议 |",
             "|------|:------:|------|------|"]

    for field in _FIELD_NAMES:
        scores = field_scores[field]
        avg = sum(scores) / len(scores) if scores else 0.0
        pct = f"{avg*100:.0f}%"
        method = "精确" if field in _EXACT_FIELDS else "覆盖"
        emoji = "✅" if avg >= 0.8 else ("⚠️" if avg >= 0.5 else "🔴")
        advice = "" if avg >= 0.8 else ("优化提取规则" if avg >= 0.5 else "重点改进，LOW置信字段")
        lines.append(f"| {field} | {emoji} {pct} | {method} | {advice} |")

    overall = sum(c.overall_score for c in comparisons) / len(comparisons)
    lines += ["", f"**总体命中率**：{overall*100:.1f}%", ""]

    if overall < 0.6:
        lines.append("> ⚠️ 总体命中率低于60%（MVP目标），重点优化🔴字段后重跑。")
    elif overall < 0.8:
        lines.append("> ⚠️ 已达MVP目标(≥60%)，持续优化至80%+。")
    else:
        lines.append("> ✅ 命中率良好（≥80%），可进入陈忱团队试用阶段。")

    lines += ["", "## 逐条明细", ""]
    for comp in comparisons:
        lines.append(f"### {comp.source or '样本'} （总分 {comp.overall_score*100:.0f}%）")
        lines.append("")
        lines.append("| 字段 | AI预填 | 人工标注 | 得分 |")
        lines.append("|------|--------|---------|:----:|")
        for h in comp.hits:
            score_str = f"{h.score*100:.0f}%" if h.score > 0 else "0%"
            ai_short = h.ai_value[:40] + "…" if len(h.ai_value) > 40 else h.ai_value
            g_short = h.golden_value[:40] + "…" if len(h.golden_value) > 40 else h.golden_value
            lines.append(f"| {h.field} | {ai_short} | {g_short} | {score_str} |")
        lines.append("")

    return "\n".join(lines)
