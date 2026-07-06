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
    if field == "不良分类":
        # 归一：AI 输出枚举「设计/制程/物料/使用不当」，人工答案常带后缀「设计问题」等
        hit = _norm_category(ai) == _norm_category(golden)
        return hit, 1.0 if hit else 0.0, "exact"
    if field == "结案日期":
        # 归一：人工答案可能带「00:00:00」时间戳，只比日期
        hit = ai[:10] == golden[:10]
        return hit, 1.0 if hit else 0.0, "exact"
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


def _norm_category(v: str) -> str:
    """不良分类归一：去「问题/类」后缀，取枚举核心词。"""
    v = (v or "").strip()
    for suf in ("问题", "类别", "类"):
        if v.endswith(suf):
            v = v[: -len(suf)]
    return v.strip()


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


# ── 黄金样本（xlsx「8D历史库录入表」）────────────────────────────────────────

_CASE_ID_CLEAN_RE = re.compile(r"(8D[-_]\d{4}[-_]\d{2}[-_]\d{3})", re.IGNORECASE)


def clean_case_id(raw: str) -> str:
    """从「8D-2025-05-001 某车型平台-A密封不良」这类单元格取纯案例ID。"""
    m = _CASE_ID_CLEAN_RE.search(raw or "")
    return m.group(1).upper().replace("_", "-") if m else (raw or "").strip()


def load_golden_xlsx(path: Path | str, sheet: str = "8D历史库录入表") -> dict[str, dict[str, str]]:
    """读 xlsx 人工标准答案页 → {案例ID: {canonical字段名: 值}}。

    该页 12 列与 _FIELD_NAMES 同序（列名略异，如「失效现象描述(D2)」），按位置映射。
    案例ID 单元格含 ID+标题，用 clean_case_id 归一。
    """
    import openpyxl
    wb = openpyxl.load_workbook(str(path), data_only=True)
    ws = wb[sheet]
    rows = list(ws.iter_rows(values_only=True))
    out: dict[str, dict[str, str]] = {}
    for row in rows[1:]:                         # 跳过表头
        if not row or row[0] is None or not str(row[0]).strip():
            continue
        rec = {}
        for i, fname in enumerate(_FIELD_NAMES):
            val = row[i] if i < len(row) else None
            rec[fname] = "" if val is None else str(val).strip()
        cid = clean_case_id(rec["案例ID"])
        rec["案例ID"] = cid                      # 归一后覆盖，便于精确比对
        out[cid] = rec
    return out


# ── 12 字段可信度地图（候选）────────────────────────────────────────────────

# 档位阈值（候选建议，终版由陈忱校准会拍板）
_TIER_HIGH = 0.8       # ≥80% 命中 → 候选「高可信：人工抽验」
_TIER_MANUAL = 0.5     # <50%       → 候选「需人工：AI 只建议、人工必改」


def confidence_map(comparisons: list[RecordComparison]) -> list[dict]:
    """逐字段命中率 → 可信度档位候选。这是候选，非终版（陈忱校准会审定）。"""
    field_scores: dict[str, list[float]] = {f: [] for f in _FIELD_NAMES}
    field_hits: dict[str, int] = {f: 0 for f in _FIELD_NAMES}
    for comp in comparisons:
        for h in comp.hits:
            field_scores[h.field].append(h.score)
            field_hits[h.field] += int(h.hit)
    n = len(comparisons)
    out = []
    for f in _FIELD_NAMES:
        scores = field_scores[f]
        avg = sum(scores) / len(scores) if scores else 0.0
        hit_rate = field_hits[f] / n if n else 0.0
        if avg >= _TIER_HIGH:
            tier = "高可信（候选）：人工抽验"
        elif avg >= _TIER_MANUAL:
            tier = "半自动（候选）：AI 建议 + 人工确认"
        else:
            tier = "需人工（候选）：AI 只建议、人工必改"
        out.append({
            "字段": f, "平均得分": round(avg, 3), "命中数": f"{field_hits[f]}/{n}",
            "档位候选": tier,
            "精确/覆盖": "精确" if f in _EXACT_FIELDS else "覆盖",
        })
    return out
