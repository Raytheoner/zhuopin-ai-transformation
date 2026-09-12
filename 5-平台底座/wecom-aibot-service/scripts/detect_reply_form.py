"""队列 #446 步骤①②：对**单份**回件跑形态识别 + 按形态提原文片段——供拆件
巡逻人工步骤直接调用（建议接入点见 `1-转型规划/0-全景路线图/回件形态识别接入
建议-拆件巡逻章程§二-2026-09-05.md`）。

🔴 本脚本只做结构化识别与原文抽取，**不做语义判断、不回灌任何队列/README**
（那是队列 `#446` 状态列写明必须留人的边界）——它回答"这份文档里有什么"，
不回答"这算不算已作答"。

用法：
    python scripts/detect_reply_form.py "7-外部文档/采购部/xxx回复.docx"
    python scripts/detect_reply_form.py "7-外部文档/IT/xxx文本反馈.md" --full-text
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVICE_DIR))

from aibot_service.reply_form_detect import detect_reply_form  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="对单份回件（.docx/.md/.txt）做形态识别 + 按形态提原文片段（不做语义判断）"
    )
    parser.add_argument("path", type=Path, help="回件文件路径")
    parser.add_argument(
        "--full-text", action="store_true", help="额外打印通读全文（段落/纯文本原文）"
    )
    args = parser.parse_args()

    if not args.path.exists():
        print(f"[ERROR] 文件不存在：{args.path}", file=sys.stderr)
        sys.exit(1)

    report = detect_reply_form(args.path)

    print(f"文件：{report.source_path}")
    print(f"形态：{report.summary()}")
    print(f"forms_present：{report.forms_present}")

    if report.doc_type == "plain_text":
        if args.full_text:
            print("\n—— 全文（须整份通读，硬约束 1）——")
            print(report.plain_text)
        return

    if report.checkboxes:
        print("\n—— 复选框逐格明细（硬约束 1：不限表格内外）——")
        for c in report.checkboxes:
            where = "表格内" if c.in_table else "段落内"
            mark = "☒已勾" if c.checked else "☐未勾"
            print(f"  [{c.index}] {mark}（{where}）｜上下文：{c.context[:60]}")

    if report.highlights:
        print(
            f"\n—— 高亮叙事段（合并后 {len(report.highlights)} 段，"
            f"原始 <w:highlight> 元素 {report.raw_highlight_element_count} 处）——"
        )
        for h in report.highlights:
            print(f"  [段落{h.paragraph_index}] {h.text}")

    if report.comments:
        print(f"\n—— 批注（{len(report.comments)} 条）——")
        for c in report.comments:
            print(f"  [{c.comment_id}] {c.author or '未知作者'}：{c.comment_text}")
            print(f"      锚定原文：{c.anchor_text}")

    if report.revisions:
        print(f"\n—— 修订（{report.insert_count} 处插入 + {report.delete_count} 处删除）——")
        for r in report.revisions:
            kind_label = "插入" if r.kind == "ins" else "删除"
            print(f"  [{kind_label}] {r.author or '未知作者'}：{r.text}")

    if report.tables:
        print(f"\n—— 表格原始字符（{len(report.tables)} 张，硬约束 2：看字符不看列名）——")
        for t in report.tables:
            print(f"  表{t.table_index}：")
            for row in t.rows:
                print(f"    {row}")

    if args.full_text:
        print("\n—— 全文段落（硬约束 1：含表格单元格、按文档顺序）——")
        for idx, para in enumerate(report.full_paragraphs):
            if para.strip():
                print(f"  [{idx}] {para}")


if __name__ == "__main__":
    main()
