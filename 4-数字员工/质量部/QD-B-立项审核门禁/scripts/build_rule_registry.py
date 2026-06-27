"""从工作汇总.xlsx「立项门禁」页导出 82 条规则元数据 → data/rules/registry.json。

规则即数据（design.md D2）：工作汇总.xlsx 为单一可信源，规则注册表是其
机器可读快照。规则集演进 → 重跑本脚本 → 登记规则版本号 → 走黄金基准回归。

用法：
    py scripts/build_rule_registry.py [path-to-工作汇总.xlsx] [rule_version]
默认读 ../../../7-外部文档/质量部/AI质量智能建设就绪工作汇总.xlsx。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import openpyxl

HERE = Path(__file__).resolve().parent
SCENE = HERE.parent
DEFAULT_XLSX = SCENE / "../../../7-外部文档/质量部/AI质量智能建设就绪工作汇总.xlsx"
OUT = SCENE / "data/rules/registry.json"

# 「立项门禁」页表头（A1:K1）→ 规范字段名
COLS = {
    "规则ID": "rule_id", "章节": "section", "检查项": "check_item",
    "适用类型": "applies_to", "严重度": "severity", "检查类型": "check_type",
    "判定标准（通过条件）": "pass_condition", "阈值/取值域": "threshold",
    "取数来源": "source_anchor", "自动化": "automation", "备注": "trial_result",
}

# 「立项门禁」J 列严重度（阻断/重要/一般/提示）→「封面」三级（错误/警告/提示）。
# 映射在收口-1 由业务最终确认；此处为 MVP 默认（design.md D8）：
#   阻断 → 错误（一票否决）；重要 → 错误（候选，可由业务下调为警告）；
#   一般 → 警告；提示 → 提示。
SEVERITY_MAP = {
    "阻断": "错误",
    "重要": "错误",   # MVP 默认计入一票否决；收口-1 可下调为「警告」
    "一般": "警告",
    "提示": "提示",
}

# 自动化分类 → 实现类别（design 三分类）
AUTOMATION_CLASS = {
    "可机器核": "A",   # 确定性纯函数
    "半自动": "B",     # LLM 语义判定
    "转人工": "C",     # 只验在否
}


def build(xlsx_path: Path, rule_version: str) -> dict:
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb["立项门禁"]
    header = [(_norm(c.value)) for c in ws[1]]
    idx = {COLS[h]: i for i, h in enumerate(header) if h in COLS}

    rules = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] is None or _norm(row[0]) == "":
            continue
        rec = {key: _norm(row[i]) if i < len(row) else "" for key, i in idx.items()}
        sev = rec.get("severity", "")
        auto = rec.get("automation", "")
        rec["severity_level"] = SEVERITY_MAP.get(sev, "警告")
        rec["impl_class"] = AUTOMATION_CLASS.get(auto, "A")
        rec["blocking"] = rec["severity_level"] == "错误"
        rules.append(rec)

    by_class = {}
    for r in rules:
        by_class[r["impl_class"]] = by_class.get(r["impl_class"], 0) + 1

    return {
        "rule_version": rule_version,
        "source": str(Path(xlsx_path).name),
        "source_sheet": "立项门禁",
        "applies_to": "开发类 EQQR8082 A2.1",
        "severity_map": SEVERITY_MAP,
        "count": len(rules),
        "count_by_class": by_class,
        "rules": rules,
    }


def _norm(v) -> str:
    if v is None:
        return ""
    return str(v).replace("　", " ").strip()


def main():
    xlsx = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_XLSX
    version = sys.argv[2] if len(sys.argv) > 2 else "2026-06-27"
    reg = build(xlsx, version)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"  rule_version={reg['rule_version']}  count={reg['count']}")
    print(f"  by_class={reg['count_by_class']}  (A=可机器核 B=半自动 C=转人工)")


if __name__ == "__main__":
    main()
