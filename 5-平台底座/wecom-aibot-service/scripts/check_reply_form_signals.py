"""队列 #446：拆件班次用的回件形态识别 CLI——`reply_form_detection.py` 的
薄命令行封装，不含任何新判断逻辑。

## 用法
    python scripts/check_reply_form_signals.py <docx路径> [<docx路径> ...]

对每个路径跑一次 `analyze_docx()`，打印：
  1. 一行 `summary_line()` 摘要（四类信号计数）；
  2. 逐格 ☒/☐（含表格行上下文，见 `CheckboxItem.row_context`）；
  3. 高亮段全文（合并后）；
  4. 批注内容与圈住的原文；
  5. 修订（`w:ins`/`w:del`）文字。

非 `.docx` 路径（如企微文本反馈归档的 `.md`）直接跳过并提示——本模块
只识别 docx 内的四类结构化/半结构化信号，纯文本回复的"形态"就是它的
全文本身，不需要（也不能）套用本工具。

## 不做什么
不做语义判断、不回填任何权威载体（README/队列）——输出止于"这份 docx
里有什么"，供拆件人工/CC 读一眼再落笔，不是可以直接照抄的结论。

退出码：0 ＝ 全部路径处理完毕（不论各自识别出多少信号）；
        2 ＝ 至少一个路径不是合法 docx（读不了 `word/document.xml`），
             这类失败不得被静默吞掉当成"零信号"。
"""
from __future__ import annotations

import sys
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVICE_DIR))

from aibot_service.reply_form_detection import analyze_docx  # noqa: E402


def _print_signals(path: Path) -> bool:
    """返回 True＝正常解析，False＝解析失败（非法 docx）。"""
    print(f"===== {path.name} =====")
    if path.suffix.lower() != ".docx":
        print(f"[跳过] 非 docx（{path.suffix or '无扩展名'}）——纯文本回复不适用本工具，全文即形态本身。")
        print()
        return True
    try:
        sig = analyze_docx(path)
    except (ValueError, OSError) as exc:
        print(f"[读取失败] {exc}")
        print()
        return False

    print(sig.summary_line())

    if sig.checkboxes:
        print("-- 复选框（逐格） --")
        for c in sig.checkboxes:
            mark = "☒" if c.checked else "☐"
            row = f"　| 同行其余单元格：{c.row_context}" if c.row_context else ""
            print(f"  {mark} {c.context}{row}")

    if sig.loose_checkbox_chars:
        print("-- 裸勾选字符（控件外，语义需人工确认） --")
        for lc in sig.loose_checkbox_chars:
            print(f"  {lc.char} | 上下文：{lc.context}")

    if sig.highlights:
        print(f"-- 高亮段全文（合并后 {len(sig.highlights)} 段，"
              f"未合并 run 计 {sig.highlight_run_count_total} 处） --")
        for h in sig.highlights:
            print(f"  [{h.color}] {h.text}")

    if sig.comments:
        print("-- 批注 --")
        for c in sig.comments:
            print(f"  #{c.comment_id} {c.author} {c.date}：{c.text}")
            if c.anchor_text:
                print(f"      圈住原文：{c.anchor_text}")

    if sig.tracked_changes:
        print("-- 修订标记 --")
        for t in sig.tracked_changes:
            kind = "插入" if t.kind == "ins" else "删除"
            print(f"  [{kind}] {t.author} {t.date}：{t.text}")

    print()
    return True


def main(argv: list) -> int:
    if not argv:
        print("用法：python scripts/check_reply_form_signals.py <docx路径> [<docx路径> ...]")
        return 2
    ok = True
    for arg in argv:
        path = Path(arg)
        if not path.exists():
            print(f"===== {arg} =====")
            print("[不存在] 路径读不到——不得当成「零信号」，须人工确认归档是否完整。")
            print()
            ok = False
            continue
        if not _print_signals(path):
            ok = False
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
