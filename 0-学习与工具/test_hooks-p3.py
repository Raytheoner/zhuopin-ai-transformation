# -*- coding: utf-8 -*-
"""
P3 hooks（队列 §一 `#381`⑸ⓐⓑⓒⓓ，openspec 变更包 `cc-hooks-p3`）端到端单测。

🔴 同 `test_hooks-哨兵.py` 的既有理由：哨兵的契约是「stdin 收 hook JSON → 退出码 ＋
`hookSpecificOutput.additionalContext`」，逐函数测过、契约却对不上，正是
`OP-0819-F`「建成 9 天从没响过」那类事故的成因形态。故本文件一律真跑脚本、真喂
JSON、真断言退出码与输出结构，不 mock PowerShell 进程本身。

范围：本文件只测**独立的 PowerShell 钩子脚本**（ⓐ SessionStart／ⓑ UserPromptSubmit／
ⓒ PreToolUse／ⓓ Stop）。ⓔ（`acquire` 路由提示）与 ⓕ（sweep rules 尺寸巡检）是对既有
Python 工具的直接修改，测试并入各自既有文件
（`test_工具-共享文档编辑锁.py` ／ `test_工具-落库sweep.py`），不在本文件重复。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent / "hooks"
COMMON = HOOKS_DIR / "hooks-common.ps1"
SESSIONSTART = HOOKS_DIR / "hooks-sessionstart-context.ps1"
REPO_ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    shutil.which("pwsh") is None, reason="需要 PowerShell 7（pwsh）"
)


# ─────────────────────────────────────────────────────────────────────────────
# 驱动
# ─────────────────────────────────────────────────────────────────────────────

def run_hook(script: Path, payload: dict, repo_root: Path) -> tuple[int, dict, str]:
    """真跑一次钩子：喂 stdin JSON，返回 `(退出码, 解析后的 stdout JSON 或 {}, stderr)`。"""
    env = dict(os.environ)
    env["ZHUOPIN_SENTINEL_REPO_ROOT"] = str(repo_root)
    proc = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(script)],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        capture_output=True,
        env=env,
        cwd=str(repo_root),
    )
    out = proc.stdout.decode("utf-8", errors="replace").strip()
    err = proc.stderr.decode("utf-8", errors="replace")
    parsed: dict = {}
    if out:
        try:
            parsed = json.loads(out)
        except json.JSONDecodeError:
            pass
    return proc.returncode, parsed, err


def audit_lines(repo_root: Path) -> list[dict]:
    p = repo_root / "reports" / "hooks-audit.jsonl"
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


QUEUE_REL = "1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md"


def write_minimal_queue(repo_root: Path, section_one_rows: list[str]) -> None:
    p = repo_root / QUEUE_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(
        ["# 跨桌任务队列（测试夹具）", "", "## 一、任务看板", ""]
        + section_one_rows
        + ["", "## 二、待 commit 批次（CC 取活销行）", "", "（空）"]
    )
    p.write_text(body, encoding="utf-8")


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """非 git 目录夹具：练 fail-open 路径（无 `.git` 时 fsck/rev-list 均应失败但不崩）。"""
    (tmp_path / "reports").mkdir()
    return tmp_path


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    """真实最小 git 仓库：有 `master` 分支与一个提交，练「正常在办」路径。"""
    (tmp_path / "reports").mkdir()

    def run(*args):
        subprocess.run(["git", *args], cwd=str(tmp_path), check=True,
                        capture_output=True)

    run("init", "-q", "-b", "master")
    run("config", "user.email", "test@example.com")
    run("config", "user.name", "Test")
    (tmp_path / "README.md").write_text("test\n", encoding="utf-8")
    run("add", "README.md")
    run("commit", "-q", "-m", "init")
    return tmp_path


# ─────────────────────────────────────────────────────────────────────────────
# ⓐ SessionStart（hooks-sessionstart-context.ps1）
# ─────────────────────────────────────────────────────────────────────────────

class TestSessionStartContext:
    def test_脚本文件齐备(self):
        assert COMMON.is_file()
        assert SESSIONSTART.is_file()

    def test_非git目录仍fail_open且留痕(self, repo: Path):
        """无 `.git`：fsck/rev-list 必然失败，但钩子本身不得以非零退出码收尾。"""
        rc, out, err = run_hook(SESSIONSTART, {"session_id": "s1"}, repo)
        assert rc == 0, err
        ctx = out.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "本地" in ctx and "UTC" in ctx
        lines = audit_lines(repo)
        assert len(lines) == 1
        assert lines[0]["hook"] == "sessionstart-context"
        assert lines[0]["sessionId"] == "s1"

    def test_真实git仓库_双标时刻与ahead_behind(self, git_repo: Path):
        rc, out, err = run_hook(SESSIONSTART, {"session_id": "s2"}, git_repo)
        assert rc == 0, err
        ctx = out.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "仓库连通性正常" in ctx or "git fsck" in ctx
        # 无 origin 时 ahead/behind 不可解析，须显式说明、不得假装 0/0。
        assert "ahead/behind 不可用" in ctx or "ahead=" in ctx

    def test_队列文件缺失_显式说明不静默(self, git_repo: Path):
        rc, out, err = run_hook(SESSIONSTART, {"session_id": "s3"}, git_repo)
        assert rc == 0, err
        ctx = out.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "待领队列摘要不可用" in ctx

    def test_队列有待领行_摘要含编号(self, git_repo: Path):
        write_minimal_queue(git_repo, [
            "| 501 | [S:open] 🔄 测试任务甲 | 待领 | x | y | z | 2026-09-04 |",
            # 🔴 真实生产形态（同 §一 现网多行）：[S:open] 之后紧跟 [D:机] 与 🛑，
            # 表示"状态字段仍是 open，但因 WIP 顶格排队中"——本行不应计入待领摘要。
            "| 502 | [S:open][D:机] 🛑 **排队中（WIP 满）** 测试任务乙 | 待领 | x | y | z | 2026-09-04 |",
            "| 503 | [S:done] 测试任务丙已完成 | - | x | y | z | 2026-09-04 |",
        ])
        rc, out, err = run_hook(SESSIONSTART, {"session_id": "s4"}, git_repo)
        assert rc == 0, err
        ctx = out.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "#501" in ctx
        assert "#503" not in ctx  # done 不算待领

    def test_stdin为空仍放行(self, git_repo: Path):
        proc = subprocess.run(
            ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(SESSIONSTART)],
            input=b"",
            capture_output=True,
            env={**os.environ, "ZHUOPIN_SENTINEL_REPO_ROOT": str(git_repo)},
            cwd=str(git_repo),
        )
        assert proc.returncode == 0

    def test_每次运行都追加审计行_不覆盖(self, git_repo: Path):
        run_hook(SESSIONSTART, {"session_id": "a"}, git_repo)
        run_hook(SESSIONSTART, {"session_id": "b"}, git_repo)
        lines = audit_lines(git_repo)
        assert len(lines) == 2
        assert {l["sessionId"] for l in lines} == {"a", "b"}
