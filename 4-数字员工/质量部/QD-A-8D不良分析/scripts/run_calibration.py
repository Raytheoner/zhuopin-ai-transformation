"""8D 预填脚本 · 批量校准（轨 A）。

对 8D库 7 份原始 .pptx 跑预填 → 与 xlsx「8D历史库录入表」人工标准答案逐字段比对，
产出：① 逐字段 diff 报告 ② 12 字段可信度地图（候选）③ 脱敏占位质量检查。

红线：原始 8D 未脱敏、含真实客户数据——本脚本输出写 `results/`（.gitignore，LAN 内），
不入库、不进向量库；可信度地图是候选，交陈忱校准会审定。

用法：
    python scripts/run_calibration.py
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qda_prefill.calibrate import (batch_report, clean_case_id, compare_record,
                                    confidence_map, load_golden_xlsx)
from qda_prefill.doc_reader import read
from qda_prefill.field_extractor import extract_fields
from qda_prefill.scrubber import TokenState, scrub_text

ROOT = Path("C:/Dev/zhuopin-ai")
LIB = ROOT / "7-外部文档/质量部/8D库"
# 注：7-外部文档/质量部 2026-07 由质量专线重组，工作汇总.xlsx 移入「产品类立项申请书及评审报告」子夹
GOLDEN_XLSX = ROOT / "7-外部文档/质量部/产品类立项申请书及评审报告/AI质量智能建设就绪工作汇总.xlsx"
OUT = Path(__file__).resolve().parent.parent / "results"

# 原始文件 ↔ 案例ID（CC质量专线-prompt-2026-07-04 已核对 1:1）
PAIRING = {
    "1.大燕冲压件开裂8D-5.20.pptx": "8D-2025-05-001",
    "2.EQ15G-8D报告（F18C漏刷写问题）20260415.pptx": "8D-2026-03-001",
    "3.EQ07-3连接器与电容干涉问题8D报0609.pptx": "8D-2026-06-001",
    "4.EQ43芯片引脚短路.pptx": "8D-2026-05-001",
    "5.EQ15-2喷油异常，加速无力报告8D报告.pptx": "8D-2026-02-001",
    "6.EQ42下盖开裂不良8D (2026-4-21).pptx": "8D-2026-04-001",
    "7.EQ42-C2 元器件损坏8D报告.pptx": "8D-2025-01-001",
}

_EMAIL_RE = re.compile(r"[\w.\-]+@[\w.\-]+\.\w+")
_DOMAIN_RE = re.compile(r"\b[\w-]+\.(?:com|cn|net)\b", re.I)


def main():
    OUT.mkdir(exist_ok=True)
    golden = load_golden_xlsx(GOLDEN_XLSX)

    comparisons = []
    truncated, missing, scrub_rows = [], [], []
    for fname, cid in PAIRING.items():
        fpath = LIB / fname
        if not fpath.exists():
            missing.append((fname, cid, "文件不存在"))
            continue
        if not zipfile.is_zipfile(fpath):
            sz = fpath.stat().st_size
            truncated.append((fname, cid, f"非有效 pptx（{sz:,} 字节，源文件截断/缺 zip 尾目录，需重取）"))
            continue
        doc = read(fpath)
        record = extract_fields(doc)
        g = golden.get(cid)
        if not g:
            missing.append((fname, cid, "标准答案页无此案例ID"))
            continue
        comparisons.append(compare_record(record, g, source=f"{fname[:20]}→{cid}"))

        # 脱敏占位质量：对全文跑一遍 scrubber，统计实体 + 残留身份指纹
        state = TokenState()
        res = scrub_text(doc.full_text, state)
        by_type: dict[str, int] = {}
        for e in res.entities:
            by_type[e.entity_type] = by_type.get(e.entity_type, 0) + 1
        leaks = sorted(set(_EMAIL_RE.findall(res.suggested))
                       | set(_DOMAIN_RE.findall(res.suggested)))
        scrub_rows.append((cid, by_type, leaks))

    # ── 写报告 ──
    diff = batch_report(comparisons)
    (OUT / "校准-diff报告.md").write_text(diff, encoding="utf-8")

    cmap = confidence_map(comparisons)
    lines = ["# 12 字段可信度地图（候选）", "",
             f"> 基于 {len(comparisons)} 份可用样本；**候选，非终版**——高/需人工由陈忱校准会拍板。", "",
             "| 字段 | 平均得分 | 命中数 | 精确/覆盖 | 档位候选 |",
             "|------|:-------:|:-----:|:--------:|---------|"]
    for r in cmap:
        lines.append(f"| {r['字段']} | {r['平均得分']*100:.0f}% | {r['命中数']} | {r['精确/覆盖']} | {r['档位候选']} |")
    (OUT / "校准-可信度地图候选.md").write_text("\n".join(lines), encoding="utf-8")

    # 脱敏质量
    slines = ["# 脱敏占位质量检查", "",
              "每案例 scrubber 识别到的实体类型计数 + 残留身份指纹（邮箱/域名=明确漏网）。", ""]
    for cid, by_type, leaks in scrub_rows:
        slines.append(f"## {cid}")
        slines.append(f"- 识别实体：{by_type or '（无）'}")
        slines.append(f"- ⚠ 残留身份指纹：{leaks or '（未检出邮箱/域名）'}")
        slines.append("")
    (OUT / "校准-脱敏质量.md").write_text("\n".join(slines), encoding="utf-8")

    # ── 终端摘要 ──
    print(f"可用样本 {len(comparisons)}/7；截断 {len(truncated)}；缺失 {len(missing)}")
    for f, c, why in truncated + missing:
        print(f"  ⚠ [{c}] {f[:30]} — {why}")
    overall = sum(c.overall_score for c in comparisons) / len(comparisons) if comparisons else 0
    print(f"总体命中率：{overall*100:.1f}%（MVP 门槛 60%）")
    print(f"报告已写入（LAN 内，不入库）：{OUT}")


if __name__ == "__main__":
    main()
