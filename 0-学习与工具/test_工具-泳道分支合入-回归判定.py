"""`工具-泳道分支合入-回归判定.ps1` 单测（队列 §一 `#562`，`OP-0911-S`，2026-09-11）。

背景：`工具-泳道分支合入.ps1` ④ 原用 `$LASTEXITCODE -ne 0` 二值判「未全绿」，与
`.claude/rules/两桌同步与取证.md` §二 的零回归口径（"同一组失败在纯 master 同命令复跑逐条复现"）
不一致——K2 行长闸日期夹具 `ROW_LENGTH_BLOCK_FROM=2026-09-11` 起在纯 master 上永久红，
旧判据会让此后每条分支都假阳停在 ④。本文件测三个被抽出、可独立验证的纯函数：

- `Get-PytestFailedTests`：从 pytest `-q -rf` 输出里抠出 `FAILED <用例名>` 集合（排序去重）。
- `Get-PytestSummaryLine`：取 `=====` 包住的结语行（"N failed, M passed in Ts"），供日志
  "自陈零回归必须写出手段＋真实回显"（两桌同步与取证.md §三）落地成可读文本。
- `Get-NewFailures`：分支失败集合相对纯 master 失败集合的"新增"部分——空即零回归、放行；
  非空即新增失败、应拒。这是 ④ 判据的核心，取代原来的二值 `$LASTEXITCODE`。

🔴 需要 PowerShell 7（`pwsh`）；没有即整文件跳过（同 `test_hooks-p3.py` 手法）。本文件只测
纯函数（不需要真实 git/pytest 环境）；真实分支合入回归验证走 `OP-0911-N` 那次实撞重放，
记在队列 §二 批次行内，不在本文件里。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

LIB = Path(__file__).resolve().with_name("工具-泳道分支合入-回归判定.ps1")

pytestmark = pytest.mark.skipif(shutil.which("pwsh") is None, reason="需要 PowerShell 7（pwsh）")


def _run_json(ps_body: str):
    """把 `ps_body`（先 dot-source 库文件）写成临时 .ps1 跑 pwsh，返回反序列化后的 JSON。"""
    script = f". '{LIB.as_posix()}'\r\n{ps_body}\r\n"
    with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as f:
        f.write(script)
        path = f.name
    try:
        proc = subprocess.run(
            ["pwsh", "-NoProfile", "-NonInteractive", "-File", path],
            capture_output=True, text=True, timeout=60, encoding="utf-8",
        )
        assert proc.returncode == 0, f"pwsh 非零退出（stderr）：{proc.stderr}\n(stdout){proc.stdout}"
        out = proc.stdout.strip()
        return json.loads(out) if out else None
    finally:
        Path(path).unlink(missing_ok=True)


#: 仿 `OP-0911-N` 实撞的 pytest -q -rf 输出（K2 行长闸日期夹具两条，分支侧）。
BRANCH_PYTEST_OUTPUT = r"""
=================================== FAILURES ===================================
____________ test_row_length_over_cap_warns_before_cutoff_does_not_block ____________
assert False
____________ test_row_length_section_four_topic_column_checked ____________
assert False
=============================== short test summary info ================================
FAILED 0-学习与工具/test_工具-队列行长闸.py::test_row_length_over_cap_warns_before_cutoff_does_not_block
FAILED 0-学习与工具/test_工具-队列行长闸.py::test_row_length_section_four_topic_column_checked
=========================== 2 failed, 561 passed in 8.91s ===========================
"""

#: 纯 master（rebase 前）同命令——两条同名失败，无新增。
MASTER_PYTEST_OUTPUT_SAME = r"""
=================================== FAILURES ===================================
=============================== short test summary info ================================
FAILED 0-学习与工具/test_工具-队列行长闸.py::test_row_length_over_cap_warns_before_cutoff_does_not_block
FAILED 0-学习与工具/test_工具-队列行长闸.py::test_row_length_section_four_topic_column_checked
=========================== 2 failed, 530 passed in 8.60s ===========================
"""

#: 全绿输出（无 FAILED 行、无失败结语）。
GREEN_PYTEST_OUTPUT = r"""
=========================== 563 passed in 9.12s ===========================
"""


class TestGetPytestFailedTests:
    def test_extracts_and_sorts_failed_names(self):
        ps = f"""
$out = @'
{BRANCH_PYTEST_OUTPUT}
'@
Get-PytestFailedTests -Output $out | ConvertTo-Json -AsArray
"""
        result = _run_json(ps)
        assert result == [
            "0-学习与工具/test_工具-队列行长闸.py::test_row_length_over_cap_warns_before_cutoff_does_not_block",
            "0-学习与工具/test_工具-队列行长闸.py::test_row_length_section_four_topic_column_checked",
        ]

    def test_green_output_yields_empty_array(self):
        ps = f"""
$out = @'
{GREEN_PYTEST_OUTPUT}
'@
$r = @(Get-PytestFailedTests -Output $out)
ConvertTo-Json -InputObject $r
"""
        result = _run_json(ps)
        assert result == []

    def test_dedupes_repeated_failed_lines(self):
        ps = r"""
$out = @'
FAILED a.py::test_x
FAILED a.py::test_x
FAILED b.py::test_y
'@
Get-PytestFailedTests -Output $out | ConvertTo-Json -AsArray
"""
        result = _run_json(ps)
        assert result == ["a.py::test_x", "b.py::test_y"]


class TestGetPytestSummaryLine:
    def test_extracts_inner_text_from_equals_wrapped_line(self):
        ps = f"""
$out = @'
{BRANCH_PYTEST_OUTPUT}
'@
Get-PytestSummaryLine -Output $out | ConvertTo-Json
"""
        result = _run_json(ps)
        assert result == "2 failed, 561 passed in 8.91s"

    def test_green_summary(self):
        ps = f"""
$out = @'
{GREEN_PYTEST_OUTPUT}
'@
Get-PytestSummaryLine -Output $out | ConvertTo-Json
"""
        result = _run_json(ps)
        assert result == "563 passed in 9.12s"


class TestGetNewFailures:
    def test_zero_regression_when_branch_failures_are_subset_of_master(self):
        """`OP-0911-N` 实撞原型：分支两条失败，纯 master 同命令同两条失败 ⇒ 新增＝空 ⇒ 应放行。"""
        ps = """
$branch = @(
    '0-学习与工具/test_工具-队列行长闸.py::test_row_length_over_cap_warns_before_cutoff_does_not_block',
    '0-学习与工具/test_工具-队列行长闸.py::test_row_length_section_four_topic_column_checked'
)
$master = @(
    '0-学习与工具/test_工具-队列行长闸.py::test_row_length_over_cap_warns_before_cutoff_does_not_block',
    '0-学习与工具/test_工具-队列行长闸.py::test_row_length_section_four_topic_column_checked'
)
$r = @(Get-NewFailures -BranchFailed $branch -MasterFailed $master)
ConvertTo-Json -InputObject $r
"""
        result = _run_json(ps)
        assert result == []

    def test_new_failure_not_present_on_master_is_flagged(self):
        """分支比 master 多红一条 ⇒ 那一条即"新增失败"，应拒 ff。"""
        ps = """
$branch = @('a.py::test_old_red', 'b.py::test_newly_broken')
$master = @('a.py::test_old_red')
$r = @(Get-NewFailures -BranchFailed $branch -MasterFailed $master)
ConvertTo-Json -InputObject $r
"""
        result = _run_json(ps)
        assert result == ["b.py::test_newly_broken"]

    def test_branch_fixing_a_master_failure_is_not_penalized(self):
        """分支修好了 master 上原本就红的一条（分支失败集合是 master 的真子集）⇒ 仍是零回归。"""
        ps = """
$branch = @('a.py::test_still_red')
$master = @('a.py::test_still_red', 'c.py::test_also_red_on_master')
$r = @(Get-NewFailures -BranchFailed $branch -MasterFailed $master)
ConvertTo-Json -InputObject $r
"""
        result = _run_json(ps)
        assert result == []

    def test_no_failures_at_all_is_zero_regression(self):
        ps = """
$r = @(Get-NewFailures -BranchFailed @() -MasterFailed @())
ConvertTo-Json -InputObject $r
"""
        result = _run_json(ps)
        assert result == []

    def test_realistic_master_and_branch_outputs_end_to_end(self):
        """端到端：直接从两段仿真 pytest 输出算到"新增失败"，不手填数组——覆盖
        Get-PytestFailedTests → Get-NewFailures 的组合，是 ④ 段实际的调用顺序。"""
        ps = f"""
$branchOut = @'
{BRANCH_PYTEST_OUTPUT}
'@
$masterOut = @'
{MASTER_PYTEST_OUTPUT_SAME}
'@
$branchFailed = @(Get-PytestFailedTests -Output $branchOut)
$masterFailed = @(Get-PytestFailedTests -Output $masterOut)
$r = @(Get-NewFailures -BranchFailed $branchFailed -MasterFailed $masterFailed)
ConvertTo-Json -InputObject $r
"""
        result = _run_json(ps)
        assert result == []
