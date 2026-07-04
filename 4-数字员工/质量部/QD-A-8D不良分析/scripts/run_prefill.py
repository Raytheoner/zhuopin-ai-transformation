"""8D预填脚本 CLI 入口。

用法：
    python scripts/run_prefill.py --input path/to/8d.docx --output result.json
    python scripts/run_prefill.py --input path/to/8d.docx --golden golden.csv --report report.md
    python scripts/run_prefill.py --input path/to/8d.docx --preview

真实8D文档不入库（data/golden/ 已 gitignore）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 使场景本地包可导入（无需pip install）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qda_prefill.calibrate import (RecordComparison, batch_report,
                                    compare_record, load_golden_csv)
from qda_prefill.doc_reader import read
from qda_prefill.field_extractor import extract_fields
from qda_prefill.scrubber import TokenState, build_token_table, scrub_text


def run(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"错误：文件不存在 — {input_path}", file=sys.stderr)
        sys.exit(1)

    print(f"读取文档：{input_path.name} …")
    doc = read(input_path)
    record = extract_fields(doc)

    # 脱敏建议
    token_state = TokenState(oem_level=args.oem_level)
    for field_label, field_data in record.to_dict().items():
        text = field_data.get("value", "")
        if text:
            scrub_text(text, token_state)

    # 构建输出
    result = {
        "source": str(input_path),
        "fields": record.to_dict(),
        "deidentification": {
            "token_table": token_state.mapping,
            "note": "上表为建议令牌，请确认后手动脱敏；机密映射关系本地保管，不入库。",
        },
    }

    # 输出 JSON
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        print(f"预填结果已写入：{out_path}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    # 预览（Markdown）
    if args.preview or not args.output:
        _print_preview(record, token_state)

    # 校准模式
    if args.golden:
        golden_rows = load_golden_csv(Path(args.golden))
        if not golden_rows:
            print("警告：黄金样本文件为空", file=sys.stderr)
            return
        # 单文件只与第一行对比（多文件用batch脚本）
        comp = compare_record(record, golden_rows[0], source=input_path.name)
        report_text = batch_report([comp])
        if args.report:
            report_path = Path(args.report)
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(report_text, encoding="utf-8")
            print(f"校准报告已写入：{report_path}")
        else:
            print("\n" + report_text)


def _print_preview(record, token_state: TokenState) -> None:
    print("\n" + "=" * 60)
    print("8D 预填结果预览（§1.1模板）")
    print("=" * 60)
    for field_label, field_data in record.to_dict().items():
        val = field_data.get("value", "") or "(空)"
        conf = field_data.get("confidence", "")
        note = field_data.get("note", "")
        flag = "🔴" if conf == "LOW" else ("⚠️" if conf == "MED" else "✅")
        print(f"\n【{field_label}】{flag} [{conf}]")
        print(f"  {val[:200]}{'…' if len(val) > 200 else ''}")
        if note:
            print(f"  ↳ 注：{note}")

    print("\n" + "=" * 60)
    print("脱敏建议（令牌映射表）")
    print("=" * 60)
    print(build_token_table(token_state))
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="8D预填脚本 — 从8D原文预填§1.1录入表")
    parser.add_argument("--input",  "-i", required=True, help="8D文档路径（.docx/.pdf）")
    parser.add_argument("--output", "-o", help="预填结果输出路径（.json），不指定则打印到终端")
    parser.add_argument("--golden", "-g", help="人工黄金样本CSV路径（校准模式）")
    parser.add_argument("--report", "-r", help="校准报告输出路径（.md），校准模式下有效")
    parser.add_argument("--preview", "-p", action="store_true", help="同时输出可读预览")
    parser.add_argument("--oem-level", default="B",
                        choices=["A", "B", "C"], help="OEM令牌级别（默认B级）")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
