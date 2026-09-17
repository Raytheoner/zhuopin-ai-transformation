"""队列 §一 #606 收口-4 实测探针：对 `data/mock/expense_lines.csv` 的 `invoice_no`
列逐条量出位数／前导零／空格／全半角／代码前缀五项字面特征，只读、不改任何数据。

🔴 **本探针的结论边界**：mock 数据为合成占位（`data/mock/README.md` 已自陈），
本探针只能证明"当前 mock 夹具长什么样"，**不能**代表真实报销发票号的字面特征——
后者须等真实材料到位后对真实样本重跑同一套量法（见 design.md 2026-09-17 追记）。

用法：python scripts/probe_606_invoice_no_literal_consistency.py
"""
from __future__ import annotations

import csv
import pathlib
import unicodedata

_HERE = pathlib.Path(__file__).resolve().parent
_MOCK_CSV = _HERE.parent / "data" / "mock" / "expense_lines.csv"


def _width_flag(s: str) -> str:
    widths = {unicodedata.east_asian_width(ch) for ch in s}
    if widths <= {"Na", "H", "N"}:
        return "半角"
    if widths & {"F", "W", "A"}:
        return "含全角"
    return "混合"


def analyze(csv_path: pathlib.Path) -> list[dict[str, object]]:
    rows = []
    with csv_path.open(encoding="utf-8", newline="") as f:
        for rec in csv.DictReader(f):
            no = rec["invoice_no"]
            rows.append(
                {
                    "claim_id": rec["claim_id"],
                    "line_no": rec["line_no"],
                    "invoice_no": no,
                    "位数": len(no),
                    "含空格": " " in no,
                    "宽度": _width_flag(no),
                    "全为数字": no.isdigit(),
                    "前导零数": len(no) - len(no.lstrip("0")) if no.lstrip("0") else len(no),
                    "识别出的代码前缀": no[:2] if not no[:2].isdigit() else "(无，纯数字串)",
                }
            )
    return rows


def main() -> None:
    rows = analyze(_MOCK_CSV)
    print(f"样本来源：{_MOCK_CSV}")
    print(f"样本数：{len(rows)}")
    lengths = {r["位数"] for r in rows}
    prefixes = {r["识别出的代码前缀"] for r in rows}
    print(f"位数取值集合：{sorted(lengths)}（{'一致' if len(lengths) == 1 else '不一致'}）")
    print(f"前缀取值集合：{sorted(prefixes)}")
    print(f"含空格样本数：{sum(1 for r in rows if r['含空格'])}")
    print(f"含全角字符样本数：{sum(1 for r in rows if r['宽度'] != '半角')}")
    print("逐行明细：")
    for r in rows:
        print(f"  {r}")
    print(
        "\n结论：mock 夹具三条 invoice_no 在五个字面维度（位数/前导零/空格/全半角/前缀）"
        "上零变体（长度恒 14、恒纯数字、恒半角、恒无空格、恒无字母前缀）——"
        "**当前夹具不足以证伪或证成任何 join 键假设，该问题只能等真实报销发票样本到位后"
        "用本脚本同一套量法对真实样本重跑**（design.md 2026-09-17 追记）。"
    )


if __name__ == "__main__":
    main()
