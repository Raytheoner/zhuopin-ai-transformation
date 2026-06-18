"""
风险评估报告生成器 — 输出 Markdown 格式标准化报告。

报告包含：报告头、综合评分摘要、各维度明细、AI 风险描述、
AI 建议动作、数据来源说明、采购经理审批确认区。
"""
from __future__ import annotations
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from src.scoring import ScoringResult

_CST = timezone(timedelta(hours=8))

_SOURCE_BADGE = {
    "SRM自动":     "[SRM 自动]",
    "人工录入":    "[人工录入]",
    "人工覆盖":    "[人工覆盖]",
    "数据不足":    "[数据不足]",
    "未确认（默认完全单源）": "[数据不足]",
    "需采购主数据确认": "[数据不足]",
    "数据不足 - 需人工补录": "[数据不足]",
    "ERP待接入":   "[ERP 待接入]",
}

_LEVEL_COLOR = {1: "🟢", 2: "🟡", 3: "🟠", 4: "🔴", 5: "⛔"}


def _badge(source: str) -> str:
    for key, badge in _SOURCE_BADGE.items():
        if key in source:
            return badge
    return "[人工录入]" if source else ""


def _safe_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name)


def generate_report(
    result: ScoringResult,
    supplier_name: str,
    supplier_code: str,
    evaluator: str,
    remark: str,
    delivery_source: str,
    risk_descriptions: list[str],
    action_items: list[str],
    reports_dir: Path,
    iqc_source: str = "",
    financial_source: str = "",
    single_source_source: str = "",
) -> Path:
    """
    生成 Markdown 风险评估报告，保存到 reports_dir。

    Returns:
        Path: 生成的报告文件路径
    """
    reports_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(tz=_CST)
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    date_str = now.strftime("%Y年%m月%d日 %H:%M")
    filename = f"{_safe_filename(supplier_name)}_{timestamp_str}_风险评估报告.md"
    report_path = reports_dir / filename

    level_icon = _LEVEL_COLOR.get(result.risk_level, "")
    d_badge = _badge(delivery_source)
    # 优先用 scorer 返回的 note（缺失/不足），否则用调用方传入的来源标注
    iqc_src_display = result.iqc.source or iqc_source or "人工录入"
    fin_src_display = result.financial.source or financial_source or "人工录入"
    ss_src_display = result.single_source.source or single_source_source or "人工录入"
    i_badge = _badge(iqc_src_display)
    f_badge = _badge(fin_src_display)
    s_badge = _badge(ss_src_display)

    risks_md = "\n".join(f"{i+1}. {r}" for i, r in enumerate(risk_descriptions))
    actions_md = "\n".join(f"{i+1}. {a}" for i, a in enumerate(action_items))

    # 有效权重（评分引擎在某维度数据不足时会剔除该维度并重新归一化其余权重）。
    # 报告须按**有效权重**展示，否则会继续显示误导的固定 35%/30%/20%/15%。
    w = result.weights
    _pct = lambda x: f"{x * 100:.0f}%"
    delivery_excluded = w.get("delivery", 0.0) == 0.0
    _dims = [
        ("交付准时率", result.delivery.value, w.get("delivery", 0.0)),
        ("IQC 合格率", result.iqc.value, w.get("iqc", 0.0)),
        ("财务稳定性", result.financial.value, w.get("financial", 0.0)),
        ("单源依赖", result.single_source.value, w.get("single_source", 0.0)),
    ]
    _active = [(n, v, wt) for n, v, wt in _dims if wt > 0]
    _terms = "  +  ".join(f"{v:.2f} × {_pct(wt)}" for n, v, wt in _active)
    _calc = "  +  ".join(f"{v * wt:.3f}" for n, v, wt in _active)
    summary_formula = (
        f"综合评分 = {_terms}\n"
        f"        = {_calc}\n"
        f"        = {result.composite_score:.2f}"
    )
    if delivery_excluded:
        summary_formula = (
            "⚠ 交付维度数据不足（SRM 看板为前瞻视图，无法计算历史准时率），\n"
            "  已剔除该维度并对其余维度权重重新归一化（真实历史准时率待 U9C 收货历史接入）。\n\n"
            + summary_formula
        )
    # 维度明细表的权重列（剔除维度显示「—」）
    _wt_cell = lambda k: ("— (剔除)" if w.get(k, 0.0) == 0.0 else _pct(w.get(k, 0.0)))

    source_notes = []
    for dim, src in [
        ("交付准时率", delivery_source),
        ("IQC 合格率", iqc_src_display),
        ("财务稳定性", fin_src_display),
        ("单源依赖", ss_src_display),
    ]:
        if src:
            source_notes.append(f"- **{dim}**：{src}")
    source_section = "\n".join(source_notes) if source_notes else "- 所有数据均来自人工录入"

    report = f"""# 供应商风险评估报告

---

## 报告基本信息

| 项目 | 内容 |
|------|------|
| **供应商名称** | {supplier_name} |
| **供应商编码** | {supplier_code or "—"} |
| **评估日期** | {date_str} |
| **评估人** | {evaluator} |
| **评估目的** | {remark or "例行风险评估"} |
| **综合风险等级** | {level_icon} **{result.risk_level} 级（{result.risk_label}）** |
| **综合评分** | **{result.composite_score:.2f} / 5.00** |

---

## 综合评分摘要

```
{summary_formula}
```

**风险等级：{result.risk_level} 级（{result.risk_label}）** {level_icon}

---

## 各维度评分明细

| 维度 | 有效权重 | 评分 | 数据来源 | 备注 |
|------|------|------|----------|------|
| 交付准时率 | {_wt_cell("delivery")} | {result.delivery.value:.1f} / 5.0 | {d_badge} | {delivery_source or "—"} |
| IQC 合格率 | {_wt_cell("iqc")} | {result.iqc.value:.1f} / 5.0 | {i_badge} | {iqc_src_display} |
| 财务稳定性 | {_wt_cell("financial")} | {result.financial.value:.2f} / 5.0 | {f_badge} | {fin_src_display} |
| 单源依赖风险 | {_wt_cell("single_source")} | {result.single_source.value:.1f} / 5.0 | {s_badge} | {ss_src_display} |

---

## 核心风险描述（AI 生成）

{risks_md}

> ⚠️ 以上为 AI 辅助分析，仅供参考，不构成最终评估结论。

---

## 建议动作（AI 生成）

{actions_md}

> ⚠️ 以上为 AI 辅助建议，最终决策由采购经理确认。

---

## 数据来源说明

{source_section}

**标注说明：**
- `[SRM 自动]`：从携客云 SRM API 自动获取
- `[人工录入]`：操作人手动输入
- `[人工覆盖]`：SRM 数据被人工值覆盖
- `[数据不足]`：数据缺失，使用默认值（评分 = 2.5 或最低分）
- `[ERP 待接入]`：等待 ERP 接口接通后自动获取

---

## 采购经理审批确认区

> **声明：** 本报告为 AI 辅助生成的建议性意见，最终决策由采购经理确认。
> 评估结果已写入审计日志，符合 IATF 16949 追溯要求。

| 项目 | 内容 |
|------|------|
| **采购经理姓名** | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; |
| **签字** | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; |
| **确认日期** | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; |

**确认结论：**

☐ 接受评估结论，按建议动作执行

☐ 有异议，说明：_________________________________

---

*报告生成时间：{date_str} | 评估工具：SC1 供应商风险初筛 v0.1*
"""

    report_path.write_text(report, encoding="utf-8")
    return report_path
