# -*- coding: utf-8 -*-
"""
队列 §一 `#381`⑸ⓗ2（K3 口径）`hooks-pretooluse-queue-read-guard.ps1` 端到端单测。

同 `test_hooks-p3.py` 既有理由：钩子的契约是「stdin 收 hook JSON → 退出码 ＋
stderr 提示」，真跑脚本、真喂 JSON、真断言退出码，不 mock PowerShell 进程本身
——逐函数测过、契约却对不上，正是 `OP-0819-F`「建成 9 天从没响过」那类事故的
成因形态。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent / "hooks"
GUARD = HOOKS_DIR / "hooks-pretooluse-queue-read-guard.ps1"

pytestmark = pytest.mark.skipif(
    shutil.which("pwsh") is None, reason="需要 PowerShell 7（pwsh）"
)

QUEUE_MECH_REL = "1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md"
QUEUE_BIZ_REL = "1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md"
QUEUE_ARCHIVE_REL = "1-转型规划/0-全景路线图/跨桌任务队列-归档-202608.md"
QUEUE_DIR_REL = "1-转型规划/0-全景路线图"


def run_hook(payload: dict, repo_root: Path) -> tuple[int, str, str]:
    """真跑一次钩子：喂 stdin JSON，返回 `(退出码, stdout, stderr)`。本钩子不产出
    结构化 stdout（不同于 SessionStart 那枚），只在拦截时写 stderr。"""
    env = dict(os.environ)
    env["ZHUOPIN_SENTINEL_REPO_ROOT"] = str(repo_root)
    proc = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(GUARD)],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        capture_output=True,
        env=env,
        cwd=str(repo_root),
    )
    out = proc.stdout.decode("utf-8", errors="replace")
    err = proc.stderr.decode("utf-8", errors="replace")
    return proc.returncode, out, err


def audit_lines(repo_root: Path) -> list[dict]:
    p = repo_root / "reports" / "hooks-audit.jsonl"
    if not p.is_file():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_payload(repo_root: Path, rel_target: str) -> dict:
    return {
        "session_id": "test-session", "cwd": str(repo_root),
        "hook_event_name": "PreToolUse", "tool_name": "Read",
        "tool_input": {"file_path": str(repo_root / rel_target)},
    }


def grep_payload(repo_root: Path, rel_path: str | None) -> dict:
    tool_input: dict = {"pattern": "无所谓"}
    if rel_path is not None:
        tool_input["path"] = str(repo_root / rel_path)
    return {
        "session_id": "test-session", "cwd": str(repo_root),
        "hook_event_name": "PreToolUse", "tool_name": "Grep",
        "tool_input": tool_input,
    }


def bash_payload(repo_root: Path, command: str) -> dict:
    return {
        "session_id": "test-session", "cwd": str(repo_root),
        "hook_event_name": "PreToolUse", "tool_name": "Bash",
        "tool_input": {"command": command},
    }


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    (tmp_path / "reports").mkdir()
    return tmp_path


class TestScriptExists:
    def test_脚本文件存在(self):
        assert GUARD.is_file()


class TestReadTarget:
    def test_命中机制环境真身即拒绝(self, repo: Path):
        rc, out, err = run_hook(read_payload(repo, QUEUE_MECH_REL), repo)
        assert rc == 2
        assert "--digest" in err and "--row" in err
        assert audit_lines(repo)[-1]["verdict"] == "violation"

    def test_命中业务场景真身即拒绝(self, repo: Path):
        rc, out, err = run_hook(read_payload(repo, QUEUE_BIZ_REL), repo)
        assert rc == 2

    def test_命中归档件即拒绝(self, repo: Path):
        rc, out, err = run_hook(read_payload(repo, QUEUE_ARCHIVE_REL), repo)
        assert rc == 2
        assert audit_lines(repo)[-1]["verdict"] == "violation"

    def test_非受保护文件放行(self, repo: Path):
        rc, out, err = run_hook(read_payload(repo, "CLAUDE.md"), repo)
        assert rc == 0, err
        assert audit_lines(repo)[-1]["verdict"] == "pass"

    def test_同目录下不匹配归档命名规则的文件放行(self, repo: Path):
        """`跨桌任务队列瘦身-方案-2026-09-04.md` 与队列真身同目录，但既不是两份
        真身、也不匹配「跨桌任务队列-归档-*.md」——不应被误伤。"""
        rc, out, err = run_hook(
            read_payload(repo, "1-转型规划/0-全景路线图/跨桌任务队列瘦身-方案-2026-09-04.md"),
            repo,
        )
        assert rc == 0, err

    def test_缺file_path时fail_open且标undetermined(self, repo: Path):
        payload = {
            "session_id": "s", "cwd": str(repo), "hook_event_name": "PreToolUse",
            "tool_name": "Read", "tool_input": {},
        }
        rc, out, err = run_hook(payload, repo)
        assert rc == 0, err
        assert audit_lines(repo)[-1]["verdict"] == "undetermined"


class TestGrepTarget:
    def test_path命中机制环境真身即拒绝(self, repo: Path):
        rc, out, err = run_hook(grep_payload(repo, QUEUE_MECH_REL), repo)
        assert rc == 2

    def test_path为目录不拒绝(self, repo: Path):
        """只判"结构化目标字段精确命中"，不做目录归属之类的模糊启发式——
        见脚本 DESCRIPTION 段。"""
        rc, out, err = run_hook(grep_payload(repo, QUEUE_DIR_REL), repo)
        assert rc == 0, err

    def test_未传path视为无目标可判(self, repo: Path):
        rc, out, err = run_hook(grep_payload(repo, None), repo)
        assert rc == 0, err
        assert audit_lines(repo)[-1]["verdict"] == "undetermined"


class TestBashTarget:
    @pytest.mark.parametrize("verb,cmd_fmt", [
        ("Get-Content", 'Get-Content "{path}"'),
        ("cat", 'cat "{path}"'),
        ("grep", 'grep -n "{path}"'),
        ("Select-String", 'Select-String -Path "{path}" -Pattern x'),
    ])
    def test_四个读命令直击机制环境真身均拒绝(self, repo: Path, verb, cmd_fmt):
        command = cmd_fmt.format(path=QUEUE_MECH_REL)
        rc, out, err = run_hook(bash_payload(repo, command), repo)
        assert rc == 2, f"{verb} 应被拦：{err}"
        assert audit_lines(repo)[-1]["verdict"] == "violation"

    def test_直击归档件同样拒绝(self, repo: Path):
        rc, out, err = run_hook(
            bash_payload(repo, f'cat "{QUEUE_ARCHIVE_REL}"'), repo)
        assert rc == 2

    def test_读命令但目标非队列文件放行(self, repo: Path):
        rc, out, err = run_hook(bash_payload(repo, "cat CLAUDE.md"), repo)
        assert rc == 0, err

    def test_目标是队列文件但命令非四个读命令之一放行(self, repo: Path):
        rc, out, err = run_hook(
            bash_payload(repo, f'git log -- "{QUEUE_MECH_REL}"'), repo)
        assert rc == 0, err

    def test_cat单独出现于concatenate中不误判(self, repo: Path):
        """`\\bcat\\b` 词边界——"concatenate" 不应被当成 `cat` 命令。"""
        rc, out, err = run_hook(
            bash_payload(repo, f'python concatenate.py "{QUEUE_MECH_REL}"'), repo)
        assert rc == 0, err

    def test_grep关键字单独出现不误判(self, repo: Path):
        """真实回归场景：`pytest -k grep` 常见于跑本项目自己的单测，不应被拦。"""
        rc, out, err = run_hook(
            bash_payload(repo, "python -m pytest 0-学习与工具/test_工具-队列查询.py -k grep"),
            repo,
        )
        assert rc == 0, err

    def test_白名单_队列查询工具自带grep参数不自我反噬(self, repo: Path):
        """撞车实例（脚本 DESCRIPTION 段明记）：合规命令
        `--digest --grep <关键词> --file <归档件>` 字面同时含"grep"与归档文件名，
        若无白名单会被 K3 自己新增的 --grep 功能反噬。"""
        command = (
            f'python 0-学习与工具/工具-队列查询.py --digest --grep 关键词 '
            f'--file {QUEUE_ARCHIVE_REL}'
        )
        rc, out, err = run_hook(bash_payload(repo, command), repo)
        assert rc == 0, err
        assert "白名单" in audit_lines(repo)[-1]["detail"]

    def test_白名单_编辑锁工具调用放行(self, repo: Path):
        command = (
            f'python 0-学习与工具/工具-共享文档编辑锁.py release --who CC '
            f'--file {QUEUE_MECH_REL}'
        )
        rc, out, err = run_hook(bash_payload(repo, command), repo)
        assert rc == 0, err

    def test_白名单_sweep工具调用放行(self, repo: Path):
        rc, out, err = run_hook(
            bash_payload(repo, "python 0-学习与工具/工具-落库sweep.py"), repo)
        assert rc == 0, err

    def test_白名单_队列结构lint工具调用放行(self, repo: Path):
        rc, out, err = run_hook(
            bash_payload(repo, "python 0-学习与工具/工具-队列结构lint.py"), repo)
        assert rc == 0, err

    def test_缺command字段fail_open且标undetermined(self, repo: Path):
        payload = {
            "session_id": "s", "cwd": str(repo), "hook_event_name": "PreToolUse",
            "tool_name": "Bash", "tool_input": {},
        }
        rc, out, err = run_hook(payload, repo)
        assert rc == 0, err
        assert audit_lines(repo)[-1]["verdict"] == "undetermined"


class TestUnrelatedTool:
    def test_非Read_Grep_Bash工具不受约束且不留痕(self, repo: Path):
        payload = {
            "session_id": "s", "cwd": str(repo), "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": str(repo / QUEUE_MECH_REL), "content": "x"},
        }
        rc, out, err = run_hook(payload, repo)
        assert rc == 0, err
        assert audit_lines(repo) == [], "非管辖工具防御性放行，不应留痕（同 ⓒ 既有惯例）"


class TestAuditTrail:
    def test_审计行含钩子名与工具名(self, repo: Path):
        run_hook(read_payload(repo, QUEUE_MECH_REL), repo)
        line = audit_lines(repo)[-1]
        assert line["hook"] == "pretooluse-queue-read-guard"
        assert line["tool"] == "Read"
        assert line["sessionId"] == "test-session"
