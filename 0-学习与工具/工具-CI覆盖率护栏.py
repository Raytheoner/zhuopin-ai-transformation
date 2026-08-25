"""CI 覆盖率下界护栏（队列 #309 步骤 2 追加设计输入，2026-08-08）。

背景：`工具-CI矩阵发现.py` 用自动发现替代了手写矩阵清单，解决"新场景
忘加进 CI"这一半的问题；但发现规则本身也可能悄悄失效（例如判据被改
坏、或某类测试文件的命名/结构不再匹配判据），且**发现规则完美**不代表
**测试真的都跑通过**——一个"看起来完全正常的全绿"，可能只是它根本没
测到以为的那些东西（同根 CLAUDE.md §5「工具静默回退」教训）。故设三条
独立于发现规则是否完美的下界，任一跌破即 CI 亮红：

- **总 passed 用例数 ≥ 基线**（**1698**，见下方"基线勘误"）
- **总 skipped 用例数 ≤ 基线**（**46**——CI 环境无 `.env`/`.51`，
  skip 是预期的；但 skip 数若**上升**，说明有测试在 CI 里悄悄不跑了，
  表现同样是"全绿"，这与判据静默失效是同一形态）
- **参与聚合的子项目（矩阵腿）数 ≥ 基线**（13）

**基线勘误（2026-08-08，如实登记）**：步骤 1 本机"干净 worktree"实测最初
记为 1704 passed / 40 skipped，但两个真实 CI 运行（`gh run 31249058308`／
`31252676477`）稳定复现 **1698 passed / 46 skipped**——真实差值精确定位
到 QD-B（`real_a21_path`/`huafeng_path` 两个 session 级 fixture 依赖的
真实立项书样本，分别落在 `7-外部文档/`〔整体 gitignore〕与
`data/golden/`〔湘 .gitignore〕，从未进入 git 历史）与 QD-A
（`test_track_a_calibration.py:90` 同类"答案页 xlsx 不在预期路径"跳过）
各一处。当场用一个全新 `git worktree add` 直接核验：这两处真实样本文件
在干净 worktree 里确实不存在，与真实 CI 的跳过结果完全吻合——**本机
早前记录的 1704/40 本身不是干净环境的真实值**，具体是本机早前哪一次
`git worktree` 验证残留了额外状态导致数字偏高，未能完全回溯复原，但
不影响结论：**1698/46 才是有据可查、可反复复现的真实基线**，本文件与
队列 #309 行的历史记录已同步勘误（历史记录本身不追改，只标注勘误，
见 CLAUDE.md「历史记录不追改」惯例）。

聚合数据来源：每个矩阵腿运行 `pytest --junit-xml=pytest-result.xml` 产出
的结构化报告（JUnit XML，`<testsuite tests= skipped= failures= errors=>`
属性），比正则解析"X passed, Y skipped"这类自由格式摘要行更可靠——后者
在不同 pytest 版本/插件下措辞会变，前者是 pytest 自身长期维护的标准
输出契约。

🔴 **红了要能当场判断"该红不该红"（队列 #398⑶，2026-08-25）**：本护栏原先
只报数字（"跳过用例数 59 > 基线 46"），不报**是哪些用例、为什么跳**——于是
看到红的人无法就地判断这是"测试悄悄不跑了"（真该红）还是"新场景带来的
合理增长"（基线过期）。2026-08-25 实测：那 13 个增量**逐条都有显式 skip
理由**（真实样本 gitignore／`*_RUN_REAL=1` 环境闸），需下载 artifact 手工
解析 XML 才能得出这个结论——一道"红了也没人能判断"的门禁，与没有门禁
只差一步。故跌破时一并打印按腿、按理由聚合的跳过清单。

⚠️ **绝对数下界在持续长大的仓库上必然过期**：基线 1698/46/13 立于
2026-08-08（13 腿）；2026-08-25 实测已是 **15 腿 / 2868 passed / 59 skipped**
——passed 远超下界、腿数超下界，唯独 skipped 顶破天花板。这与 #398 另两处
（`.51` 加了口令门、skill 不落本机）是**同一种失效**：判据没坏，目标变了，
而判据不知道目标变了。是否改判据形态（绝对上限 → 占比／按理由分类）属
口径变更，**不在本文件自行决定**，见队列 §四 待拍板行。

用法：
  python 0-学习与工具/工具-CI覆盖率护栏.py --results-dir <下载 artifact 后的目录>
  # 退出码 0=达标；1=任一下界跌破（详情打印到 stdout）
"""
from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

BASELINE_PASSED_MIN = 1698
BASELINE_SKIPPED_MAX = 46
BASELINE_PROJECT_COUNT_MIN = 13


def _iter_testsuite_elements(xml_path: Path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    if root.tag == "testsuites":
        yield from root.findall("testsuite")
    elif root.tag == "testsuite":
        yield root


def collect_skip_reasons(results_dir: Path) -> dict[str, dict[str, int]]:
    """按矩阵腿 → skip 理由聚合跳过用例数（队列 #398⑶）。

    理由取 `<skipped message=...>`，截断到首行前 100 字符——CI 里这些理由
    普遍形如「真实样本不在预期路径（LAN/gitignore）：<绝对路径>」，路径尾巴
    对判断没有增量信息，反而会把清单撑爆。
    """
    per_leg: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for xf in sorted(results_dir.rglob("pytest-result.xml")):
        leg = xf.parent.name
        for suite in _iter_testsuite_elements(xf):
            for case in suite.iter("testcase"):
                for skipped in case.findall("skipped"):
                    message = (skipped.get("message") or "(无理由)").splitlines()[0]
                    per_leg[leg][message[:100]] += 1
    return {leg: dict(reasons) for leg, reasons in per_leg.items()}


def format_skip_breakdown(per_leg: dict[str, dict[str, int]]) -> list[str]:
    """把 collect_skip_reasons 的结果排成可直接打进 CI 日志的行。"""
    lines: list[str] = []
    ordered = sorted(per_leg.items(), key=lambda kv: -sum(kv[1].values()))
    for leg, reasons in ordered:
        leg_total = sum(reasons.values())
        if not leg_total:
            continue
        lines.append(f"    · {leg}：跳过 {leg_total} 条")
        for message, count in sorted(reasons.items(), key=lambda kv: -kv[1]):
            lines.append(f"        {count:>3} × {message}")
    return lines


def aggregate(results_dir: Path) -> dict:
    xml_files = sorted(results_dir.rglob("pytest-result.xml"))
    total_tests = total_skipped = total_failures = total_errors = 0
    for xf in xml_files:
        for suite in _iter_testsuite_elements(xf):
            total_tests += int(suite.get("tests", 0))
            total_skipped += int(suite.get("skipped", 0))
            total_failures += int(suite.get("failures", 0))
            total_errors += int(suite.get("errors", 0))
    total_passed = total_tests - total_skipped - total_failures - total_errors
    return {
        "project_count": len(xml_files),
        "passed": total_passed,
        "skipped": total_skipped,
        "failures": total_failures,
        "errors": total_errors,
        "tests": total_tests,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results-dir", required=True, help="下载全部 pytest-result-* artifact 后的根目录")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    if not results_dir.exists():
        print(f"✗ 结果目录不存在：{results_dir}（artifact 下载步骤是否失败？）")
        return 1

    stats = aggregate(results_dir)
    print(
        f"聚合结果：{stats['project_count']} 个子项目，"
        f"tests={stats['tests']} passed={stats['passed']} "
        f"skipped={stats['skipped']} failures={stats['failures']} errors={stats['errors']}"
    )

    violations = []
    if stats["project_count"] < BASELINE_PROJECT_COUNT_MIN:
        violations.append(
            f"子项目数 {stats['project_count']} < 基线 {BASELINE_PROJECT_COUNT_MIN}"
            "（矩阵自动发现可能漏掉了某个子项目，或某个矩阵腿的 artifact 上传失败）"
        )
    if stats["passed"] < BASELINE_PASSED_MIN:
        violations.append(
            f"通过用例数 {stats['passed']} < 基线 {BASELINE_PASSED_MIN}"
            "（可能有测试被静默跳过而非真正运行，或用例被删除，需人工核实是否合理）"
        )
    if stats["skipped"] > BASELINE_SKIPPED_MAX:
        violations.append(
            f"跳过用例数 {stats['skipped']} > 基线 {BASELINE_SKIPPED_MAX}"
            "（CI 环境应无 .env/.51，skip 数上升可能意味着某类测试在 CI 里意外不再运行）"
        )

    if violations:
        print(f"✗ CI 覆盖率下界护栏未通过，{len(violations)} 项：")
        for v in violations:
            print(f"  - {v}")
        # 跌破时必须把"是哪些用例、为什么跳"一并摊开——只报数字的红，
        # 看到的人无法就地判断该红不该红，等于把判断成本转嫁给下一个人。
        if stats["skipped"] > BASELINE_SKIPPED_MAX:
            breakdown = format_skip_breakdown(collect_skip_reasons(results_dir))
            if breakdown:
                print("\n  跳过用例明细（按矩阵腿／理由聚合，用于判断是合理增长还是静默失效）：")
                print("\n".join(breakdown))
                print(
                    "\n  判读提示：每条都带显式 skip 理由（真实样本 gitignore／"
                    "`*_RUN_REAL=1` 环境闸）⇒ 属合理增长，应走基线复核；"
                    "出现无理由或理由是「导入失败/收集为空」⇒ 属静默失效，必须修。"
                )
        return 1

    print("✓ CI 覆盖率下界护栏通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
