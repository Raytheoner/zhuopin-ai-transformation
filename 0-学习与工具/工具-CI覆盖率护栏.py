"""CI 覆盖率下界护栏（队列 #309 步骤 2 追加设计输入，2026-08-08）。

背景：`工具-CI矩阵发现.py` 用自动发现替代了手写矩阵清单，解决"新场景
忘加进 CI"这一半的问题；但发现规则本身也可能悄悄失效（例如判据被改
坏、或某类测试文件的命名/结构不再匹配判据），且**发现规则完美**不代表
**测试真的都跑通过**——一个"看起来完全正常的全绿"，可能只是它根本没
测到以为的那些东西（同根 CLAUDE.md §5「工具静默回退」教训）。故设三条
独立于发现规则是否完美的下界，任一跌破即 CI 亮红：

- **总 passed 用例数 ≥ 基线**（步骤 1 实测 1704，2026-08-08）
- **总 skipped 用例数 ≤ 基线**（步骤 1 实测 40——CI 环境无 `.env`/`.51`，
  skip 是预期的；但 skip 数若**上升**，说明有测试在 CI 里悄悄不跑了，
  表现同样是"全绿"，这与判据静默失效是同一形态）
- **参与聚合的子项目（矩阵腿）数 ≥ 基线**（13）

聚合数据来源：每个矩阵腿运行 `pytest --junit-xml=pytest-result.xml` 产出
的结构化报告（JUnit XML，`<testsuite tests= skipped= failures= errors=>`
属性），比正则解析"X passed, Y skipped"这类自由格式摘要行更可靠——后者
在不同 pytest 版本/插件下措辞会变，前者是 pytest 自身长期维护的标准
输出契约。

用法：
  python 0-学习与工具/工具-CI覆盖率护栏.py --results-dir <下载 artifact 后的目录>
  # 退出码 0=达标；1=任一下界跌破（详情打印到 stdout）
"""
from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

BASELINE_PASSED_MIN = 1704
BASELINE_SKIPPED_MAX = 40
BASELINE_PROJECT_COUNT_MIN = 13


def _iter_testsuite_elements(xml_path: Path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    if root.tag == "testsuites":
        yield from root.findall("testsuite")
    elif root.tag == "testsuite":
        yield root


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
        return 1

    print("✓ CI 覆盖率下界护栏通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
