"""队列 #446 步骤③：8(+1) 封已归档回件离线回归——机器读出的形态 vs 人当时最终结论。

**为什么是离线回归、不必等新回件**：这 9 封回件（原派单件点名 8 封，见文末
「与派单件数字对不上，如实登记」）人当时都已读过、结论均已留痕于跟进信
README《现有跟进信清单》，其中 **4 次读错并事后纠正**——机器读出的形态与
人当时的**最终**（纠正后）结论逐条对，对不上就是本模块有 bug，不需要等
新回件送到才能验证。

**本脚本只做形态比对，不做语义判断**（同 `reply_form_detect.py` docstring
边界）：它只回答"机器数出来的勾选数/高亮数/批注数对不对"，不回答"这算不
算已作答"——后者的黄金答案本身就是人工事后从多轮往返里拼出来的，不该
再交回一个自动化脚本去二次判断。

`7-外部文档/` 是本机本地目录（`.gitignore` 覆盖，不入库，见仓库根
`.gitignore` 「外部参考文档」条），因此**不在任何单个 worktree checkout
里，只在共享主工作区物理存在**——与 `run_aibot_service.py` 的
`WECOM_AIBOT_EXTERNAL_DOCS_ROOT` 默认解析同一逻辑（`resolve_repo_root` 走
`git rev-parse --git-common-dir` 找所有 worktree 共享的那个仓库根，而不是
调用方自己 `__file__` 反推的 worktree 根）。本脚本能在任一 worktree 里跑，
不需要额外配置。

用法：
    python scripts/reply_form_regression.py
    python scripts/reply_form_regression.py --format markdown > 回归结果.md
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parent.parent
NAIVE_REPO_ROOT = SERVICE_DIR.parents[1]  # 5-平台底座/wecom-aibot-service -> 本 checkout 自身的根
sys.path.insert(0, str(SERVICE_DIR))

from aibot_service.reply_form_detect import detect_reply_form  # noqa: E402
from aibot_service.repo_paths import (  # noqa: E402
    DEFAULT_QUEUE_RELATIVE_PATH,
    resolve_default_queue_anchor,
    resolve_repo_root,
)

import os  # noqa: E402


@dataclass
class GoldenSample:
    label: str  # 部门#N
    relative_path: str  # 相对 7-外部文档/ 的路径
    human_conclusion: str  # README「发送状态」列里记的、人当时**最终**（纠正后）结论一句话
    source_readme_line: str  # 取证指针，供复核


# 黄金基准逐条取自 `6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md`
# 《现有跟进信清单》对应行——只摘录与"回件形态"直接相关的那一句话，完整
# 上下文按 source_readme_line 指针去查，不在本文件复述整行（那一行常常
# 上千字节）。
GOLDEN_SAMPLES: list[GoldenSample] = [
    GoldenSample(
        label="财务部#14",
        relative_path="财务部/财务部-tangyanping-回复-2026-08-22-财务部-唐燕萍-跟进-2026-08-22-漏勾致歉与审批流免除与起点反转受理-回复-8fc9f9053a205815d9c73e717586957f.docx",
        human_conclusion="零批注(0)、零修订(w:ins/w:del 各0)、零勾选控件(w14:checkbox/<w:sdt> 各0)，w:highlight 78 处——正文插高亮段作答",
        source_readme_line="README 财务部#14 行（2026-08-23 拆件回灌）",
    ),
    GoldenSample(
        label="财务部#15",
        relative_path="财务部/财务部-tangyanping-回复-2026-08-24-财务部-唐燕萍-跟进-2026-08-23-起点反转方案已定稿与两处口径请裁-回复-0781c0957e25a2e8fed6902d49ceabb1.docx",
        human_conclusion="0 批注／0 修订／6 个真复选框一个都没勾／55 处高亮——同族第二次靠高亮作答",
        source_readme_line="README 财务部#15 行（2026-08-24 拆件回灌，zipfile 直读实测）",
    ),
    GoldenSample(
        label="IT部#9",
        relative_path="IT/IT-2023458-回复-2026-08-24-文本反馈-977560aea6e22a5858e0bf0b31e43058.md",
        human_conclusion="纯文本反馈（.md），非 docx 结构化形态，无勾选/批注/修订/高亮可数——须整份通读",
        source_readme_line="README IT部#9 行",
    ),
    GoldenSample(
        label="IT部#10",
        relative_path="IT/IT-2023458-回复-2026-08-24-文本反馈-c712e9f3d0321e866bc677f2b4f3f6c9.md",
        human_conclusion="纯文本反馈（.md），非 docx 结构化形态——须整份通读",
        source_readme_line="README IT部#10 行",
    ),
    GoldenSample(
        label="质量部#9",
        relative_path="质量部/质量部-ChenChen-回复-2026-08-25-回复：质量部-陈忱-跟进-2026-08-21-Q2改写技术回应与8D评审判例批改表-b19f159eaec579a7ba743b4026cb8ae1.docx",
        human_conclusion="六条判例全数作答：五条 ☒✅ 签认+判例2 ✏️改判；w14:checkbox XML 取证 ☒6/☐8（14 个复选框、6 个已勾、无预勾选）",
        source_readme_line="README 质量部#9 行（2026-08-25 拆件巡逻第二班）",
    ),
    GoldenSample(
        label="质量部#10",
        relative_path="质量部/质量部-ChenChen-回复-2026-08-28-文本反馈-5035641b5511c3afad927a6635cd7bc7.md",
        human_conclusion="纯文本反馈（.md），非 docx 结构化形态——须整份通读",
        source_readme_line="README 质量部#10 行",
    ),
    GoldenSample(
        label="采购部#18",
        relative_path="采购部/采购部-YaoZuYi-回复-2026-08-26-采购部-姚祖怡-跟进-2026-08-24-物料看板已上线请试用与三条读数口径确认-272f6c884a1a8affc542b6e3928796f1.docx",
        human_conclusion=(
            "🔴 同族关键回归案例：3 条判例表共 9 个勾选格，"
            "**首次误判为「9 格全空」**（致姚祖怡被要求多回一封本不必回的信、"
            "为此专发致歉信采购部#20）；`read_checkboxes()`/直拆 Word 原始标记"
            "两种读法逐字一致的**纠正后**结论 ＝ 9 个复选框、3 个勾上"
        ),
        source_readme_line="README 采购部#18 行 + 采购部#20 行（致歉信原文给出纠正后数字）",
    ),
    GoldenSample(
        label="采购部#19",
        relative_path="采购部/采购部-YaoZuYi-回复-采购部#19-2026-08-28-采购部-姚祖怡-跟进-2026-08-26-三条判例再送与六件一次问齐-75623acea04d884de489c1d068fa36f0.docx",
        human_conclusion=(
            "三条读数口径判例表 ✅/❌/✏️ 三列 × 3 行共 9 格，python-docx 逐格实读为全空"
            "（问题1/2 他已用段落文字作答）；"
            "🔴 同日第二次同类错——巡逻当时只扫表格，漏掉他写在**段落里**的第 5/6 件两个勾，"
            "发现后已更正"
        ),
        source_readme_line="README 采购部#19 行 + 采购部#20 行（致歉信原文交代「同日第二次」）",
    ),
    GoldenSample(
        label="采购部#20",
        relative_path="采购部/采购部-YaoZuYi-回复-采购部#20-2026-08-31-采购部-姚祖怡-跟进-2026-08-28-读取缺陷致歉与判例4真实案例-c8fa4c95716a335db5ecdaf4d950390e.docx",
        human_conclusion="尚无逐格黄金基准（README 未细列本封形态数字）——本次只做结构快照存档，不做比对判定",
        source_readme_line="README 采购部#20 行",
    ),
]


def resolve_external_docs_root() -> Path:
    """与 `run_aibot_service.py` 完全同一套解析逻辑（同一环境变量、同一优先级），
    确保任一 worktree 里跑本脚本都能找到共享主工作区里的 `7-外部文档/`。"""
    queue_anchor = resolve_default_queue_anchor(NAIVE_REPO_ROOT, DEFAULT_QUEUE_RELATIVE_PATH)
    resolved_repo_root = resolve_repo_root(queue_anchor, fallback=NAIVE_REPO_ROOT)
    override = os.environ.get("WECOM_AIBOT_EXTERNAL_DOCS_ROOT")
    if override:
        return Path(override)
    return resolved_repo_root / "7-外部文档"


def run_regression(external_docs_root: Path) -> list[dict]:
    rows = []
    for sample in GOLDEN_SAMPLES:
        path = external_docs_root / sample.relative_path
        row: dict = {
            "label": sample.label,
            "path": str(path),
            "human_conclusion": sample.human_conclusion,
            "source": sample.source_readme_line,
        }
        if not path.exists():
            row["status"] = "MISSING"
            row["machine_summary"] = f"文件不存在：{path}"
            rows.append(row)
            continue
        try:
            report = detect_reply_form(path)
        except Exception as exc:  # noqa: BLE001 —— 回归脚本，任何解析异常都要如实报出
            row["status"] = "ERROR"
            row["machine_summary"] = f"{type(exc).__name__}: {exc}"
            rows.append(row)
            continue
        row["status"] = "OK"
        row["machine_summary"] = report.summary()
        row["forms_present"] = report.forms_present
        row["raw_highlight_element_count"] = report.raw_highlight_element_count
        if report.checkboxes:
            checked_indices = [c.index for c in report.checkboxes if c.checked]
            row["checkbox_detail"] = (
                f"{len(report.checkboxes)} 个复选框，{len(checked_indices)} 个已勾"
                f"（已勾序号：{checked_indices}）"
            )
        rows.append(row)
    return rows


def format_text(rows: list[dict]) -> str:
    lines = []
    for row in rows:
        lines.append(f"### {row['label']}")
        lines.append(f"- 文件：{row['path']}")
        lines.append(f"- 状态：{row['status']}")
        lines.append(f"- 机器读出：{row['machine_summary']}")
        if "checkbox_detail" in row:
            lines.append(f"  - {row['checkbox_detail']}")
        lines.append(f"- 人当时最终结论：{row['human_conclusion']}")
        lines.append(f"- 取证指针：{row['source']}")
        lines.append("")
    return "\n".join(lines)


def format_markdown_table(rows: list[dict]) -> str:
    lines = [
        "| 编号 | 状态 | 机器读出的形态 | 人当时最终结论 | 取证指针 |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        machine = row["machine_summary"].replace("|", "／")
        human = row["human_conclusion"].replace("|", "／")
        lines.append(
            f"| {row['label']} | {row['status']} | {machine} | {human} | {row['source']} |"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="队列 #446 步骤③：历史回件离线回归（机器形态 vs 人当时最终结论）"
    )
    parser.add_argument("--format", choices=["text", "markdown"], default="text")
    parser.add_argument(
        "--external-docs-root",
        type=Path,
        default=None,
        help="覆盖 7-外部文档/ 的解析路径（默认走与 run_aibot_service.py 相同的跨 worktree 解析）",
    )
    args = parser.parse_args()

    external_docs_root = args.external_docs_root or resolve_external_docs_root()
    print(f"[外部文档根] {external_docs_root}", file=sys.stderr)

    rows = run_regression(external_docs_root)
    if args.format == "markdown":
        print(format_markdown_table(rows))
    else:
        print(format_text(rows))

    missing = [r for r in rows if r["status"] != "OK"]
    if missing:
        print(
            f"\n[提醒] {len(missing)}/{len(rows)} 条未能正常读出（MISSING/ERROR），"
            "常见原因＝本机未同步 7-外部文档/（gitignore 本地目录），"
            "非本模块缺陷；详情见上方各条状态。",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
