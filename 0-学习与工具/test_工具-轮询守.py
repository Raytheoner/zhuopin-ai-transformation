"""轮询守单测（队列 §一 `#575` 甲，`OP-0913-Q`，批 `B-0913_轮询守`，2026-09-13）。

看护件 §二 点名的三条路径＋判据字面锁定：
- 无信号不唤模型：探针 `[NO-SIGNAL]`＋巡检三个静默标记 ⇒ 桩 claude 零调用、留痕行 `woke=false`；
- 有信号唤一次：探针 `[SIGNAL]`（或巡检 `[MERGED]`）⇒ 桩 claude 恰好一次、prompt 带两条命令原文与「不要重跑」；
- 命令非零退出不静默吞：探针 stdout 仍是 `[NO-SIGNAL]` 但退出码 3 ⇒ 照样唤模型，stderr 进 prompt，留痕记 exit=3；
- 外加：无标记 fail-open、`[NO-PENDING]` 归静默（锁定与看护件字面「非 [NO-ACTION]」的有意偏差）、`-DryRun` 零副作用
  （探针得 `--peek`、巡检得 `-DryRun`、不唤模型但仍留痕）、每轮一行痕（跑两次＝两行）、静默集合字面锁定。

🔴 需要 PowerShell 7（`pwsh`）与 python；`claude -p` 一律用 `.ps1` 桩替掉，不真起会话。每个用例只碰 `tmp_path`。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
GUARD = TOOLS / "工具-轮询守.ps1"

pytestmark = pytest.mark.skipif(shutil.which("pwsh") is None, reason="需要 PowerShell 7（pwsh）")

QUIET_PATROL = "[WL-NO-ACTION] 本轮白名单无可合入项。\n[NO-PENDING] 无待合登记。\n[WT-NO-ACTION] 本轮无可清理 worktree。"


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


class Rig:
    """一个用例一套桩：探针（.py）／巡检（.ps1）／claude（.ps1）＋章程文件＋留痕目录。"""

    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.repo = tmp / "repo"
        self.repo.mkdir()
        self.log = tmp / "log"
        self.skill = _write(tmp / "skill.md", "# 桩章程\n按输出分支处理。\n")
        self.claude_calls = tmp / "claude-calls.txt"
        self.claude_prompt = tmp / "claude-prompt.txt"
        self.probe_args = tmp / "probe-args.txt"
        self.patrol_args = tmp / "patrol-args.txt"
        self.probe = tmp / "probe.py"
        self.patrol = tmp / "patrol.ps1"
        self.claude = _write(
            tmp / "claude.ps1",
            "$in = [Console]::In.ReadToEnd()\n"
            f"Add-Content -Path '{self.claude_calls}' -Value ('ARGS: ' + ($args -join ' ')) -Encoding UTF8\n"
            f"Set-Content -Path '{self.claude_prompt}' -Value $in -Encoding UTF8\n"
            "Write-Output '桩回复'\nexit 0\n",
        )

    def set_probe(self, stdout: str, exit_code: int = 0, stderr: str = "") -> None:
        _write(
            self.probe,
            "import sys\n"
            f"open(r'{self.probe_args}', 'a', encoding='utf-8').write(' '.join(sys.argv[1:]) + '\\n')\n"
            f"sys.stdout.write({stdout!r})\n"
            f"sys.stderr.write({stderr!r})\n"
            f"sys.exit({exit_code})\n",
        )

    def set_patrol(self, stdout: str, exit_code: int = 0, stderr: str = "") -> None:
        lines = "\n".join(f"Write-Host '{ln}'" for ln in stdout.split("\n") if ln)
        err = f"[Console]::Error.WriteLine('{stderr}')\n" if stderr else ""
        _write(
            self.patrol,
            f"Add-Content -Path '{self.patrol_args}' -Value ($args -join ' ') -Encoding UTF8\n"
            f"{lines}\n{err}exit {exit_code}\n",
        )

    def run(self, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                "pwsh", "-NoProfile", "-NonInteractive", "-File", str(GUARD),
                "-Repo", str(self.repo), "-LogDir", str(self.log),
                "-ProbeScript", str(self.probe), "-PatrolScript", str(self.patrol),
                "-ClaudeExe", str(self.claude), "-SkillDoc", str(self.skill),
                "-PythonExe", sys.executable, *extra,
            ],
            capture_output=True, text=True, encoding="utf-8", timeout=180,
        )

    def rows(self) -> list[dict]:
        files = sorted(self.log.glob("poll-guard-*.jsonl"))
        assert files, f"留痕文件不存在于 {self.log}"
        out: list[dict] = []
        for f in files:
            out += [json.loads(ln) for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]
        return out

    def claude_call_count(self) -> int:
        if not self.claude_calls.exists():
            return 0
        return sum(1 for ln in self.claude_calls.read_text(encoding="utf-8").splitlines() if ln.startswith("ARGS:"))


@pytest.fixture
def rig(tmp_path: Path) -> Rig:
    return Rig(tmp_path)


# ── 路径一：无信号不唤模型 ─────────────────────────────────────────────────────

def test_quiet_both_sides_does_not_wake_model_but_leaves_trace(rig: Rig):
    rig.set_probe("[NO-SIGNAL] 无新收工、无新停滞。\n")
    rig.set_patrol(QUIET_PATROL)
    proc = rig.run()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert rig.claude_call_count() == 0
    rows = rig.rows()
    assert len(rows) == 1
    row = rows[0]
    assert row["woke"] is False and row["signal"] is False, row
    assert row["probe"]["verdict"] == "quiet" and row["patrol"]["verdict"] == "quiet", row
    assert row["probe"]["exit"] == 0 and row["patrol"]["exit"] == 0
    assert "不入库" in row["note"]
    assert "capture" not in row, "安静轮不该存全文捕获"
    assert not (rig.log / "rounds").exists()


def test_no_pending_counts_as_quiet_locked_deviation(rig: Rig):
    """看护件写「巡检非 [NO-ACTION]」；巡检真身登记册为空时打 [NO-PENDING]，章程把两者并列为空跑——锁定为静默。"""
    rig.set_probe("[NO-SIGNAL] 无新事。\n")
    rig.set_patrol("[WL-OFF] 白名单自动 ff 已关停。\n[NO-PENDING] 登记处为空。\n[WT-NO-ACTION] 本轮无可清理 worktree。")
    proc = rig.run()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert rig.claude_call_count() == 0
    assert rig.rows()[-1]["patrol"]["verdict"] == "quiet"


# ── 路径二：有信号唤一次 ───────────────────────────────────────────────────────

def test_probe_signal_wakes_model_exactly_once_with_both_outputs(rig: Rig):
    rig.set_probe("[SIGNAL]\n　批 `20260913-140558` 收工。\n")
    rig.set_patrol(QUIET_PATROL)
    proc = rig.run()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert rig.claude_call_count() == 1
    args = rig.claude_calls.read_text(encoding="utf-8")
    assert "-p" in args and "--allowedTools" in args
    # 🔴 `Bash(git log:*)` 须作为**一个**参数到达（Start-Process 不自动加引号、CLI 按空格切分——2026-09-13 真 claude.exe 实测踩过）
    assert "--allowedTools Read Glob Grep Bash(git log:*)" in args
    prompt = rig.claude_prompt.read_text(encoding="utf-8")
    assert "不要重跑探针" in prompt and "不要重跑巡检" in prompt
    assert "桩章程" in prompt, "章程原文须整段进 prompt"
    assert "20260913-140558" in prompt, "探针 stdout 原样进 prompt"
    assert "[WT-NO-ACTION]" in prompt, "巡检 stdout 原样进 prompt"
    row = rig.rows()[-1]
    assert row["woke"] is True and row["signal"] is True
    assert row["probe"]["verdict"] == "markers:SIGNAL" and row["patrol"]["verdict"] == "quiet"
    assert row["claude"]["exit"] == 0
    cap = Path(row["capture"])
    assert (cap / "claude.out").read_text(encoding="utf-8").strip() == "桩回复"
    assert (cap / "prompt.txt").exists() and (cap / "probe.out").exists() and (cap / "patrol.out").exists()


def test_patrol_merged_wakes_model_once(rig: Rig):
    rig.set_probe("[NO-SIGNAL] 无新事。\n")
    rig.set_patrol("[WL-NO-ACTION] 本轮白名单无可合入项。\n[MERGED] claude/op0913x-demo\n[WT-NO-ACTION] 本轮无可清理 worktree。")
    proc = rig.run()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert rig.claude_call_count() == 1
    row = rig.rows()[-1]
    assert row["patrol"]["verdict"] == "markers:MERGED" and row["woke"] is True


# ── 路径三：命令非零退出不静默吞 ───────────────────────────────────────────────

def test_probe_nonzero_exit_is_a_signal_even_if_stdout_says_no_signal(rig: Rig):
    rig.set_probe("[NO-SIGNAL] 看起来没事\n", exit_code=3, stderr="Traceback: 探针炸了 boom-7f3\n")
    rig.set_patrol(QUIET_PATROL)
    proc = rig.run()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert rig.claude_call_count() == 1, "非零退出必须唤模型，不得静默吞"
    prompt = rig.claude_prompt.read_text(encoding="utf-8")
    assert "boom-7f3" in prompt, "stderr 必须带进 prompt"
    row = rig.rows()[-1]
    assert row["probe"]["exit"] == 3 and row["probe"]["verdict"] == "exit:3" and row["woke"] is True


def test_patrol_nonzero_exit_is_a_signal(rig: Rig):
    rig.set_probe("[NO-SIGNAL] 无新事。\n")
    rig.set_patrol(QUIET_PATROL, exit_code=1, stderr="巡检异常 zz-42")
    proc = rig.run()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert rig.claude_call_count() == 1
    assert "zz-42" in rig.claude_prompt.read_text(encoding="utf-8")
    assert rig.rows()[-1]["patrol"]["verdict"] == "exit:1"


def test_no_marker_output_is_fail_open_signal(rig: Rig):
    rig.set_probe("something went sideways but exit 0\n")
    rig.set_patrol(QUIET_PATROL)
    proc = rig.run()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert rig.claude_call_count() == 1
    assert rig.rows()[-1]["probe"]["verdict"] == "no-marker"


# ── 干跑、每轮留痕、判据字面锁定 ───────────────────────────────────────────────

def test_dry_run_has_zero_side_effects_but_still_judges_and_traces(rig: Rig):
    rig.set_probe("[SIGNAL]\n有事。\n")
    rig.set_patrol("[NO-PENDING] 无待合登记。\n[DRY] x 本可 remove（未执行）")
    proc = rig.run("-DryRun")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert rig.claude_call_count() == 0, "干跑不得唤模型"
    assert "--peek" in rig.probe_args.read_text(encoding="utf-8"), "干跑探针必须带 --peek（不标已报、不推企微）"
    assert "-DryRun" in rig.patrol_args.read_text(encoding="utf-8"), "干跑巡检必须带 -DryRun"
    row = rig.rows()[-1]
    assert row["dry_run"] is True and row["signal"] is True and row["woke"] is False


def test_every_round_appends_exactly_one_trace_line(rig: Rig):
    rig.set_probe("[NO-SIGNAL] 无新事。\n")
    rig.set_patrol(QUIET_PATROL)
    assert rig.run().returncode == 0
    assert rig.run().returncode == 0
    rows = rig.rows()
    assert len(rows) == 2 and rows[0]["round"] != rows[1]["round"] or rows[0]["ts"] != rows[1]["ts"]
    assert all("total_ms" in r and "ts" in r for r in rows)


def test_production_probe_never_gets_peek_or_no_notify(rig: Rig):
    """章程原话：`--via-scheduled-task` 不能漏；`--no-notify` 绝不用。非干跑时探针参数只能是前者。"""
    rig.set_probe("[NO-SIGNAL] 无新事。\n")
    rig.set_patrol(QUIET_PATROL)
    assert rig.run().returncode == 0
    args = rig.probe_args.read_text(encoding="utf-8").strip()
    assert "--via-scheduled-task" in args and "--peek" not in args and "--no-notify" not in args


def test_quiet_marker_sets_are_locked_literally():
    """静默集合＝口径判据（🟡 档）。改字面须 Shao Peishen 答复，本测试逼人同步而不是悄悄漂移。"""
    src = GUARD.read_text(encoding="utf-8")
    assert "$ProbeQuietMarkers  = @('NO-SIGNAL')" in src
    assert "$PatrolQuietMarkers = @('WL-NO-ACTION', 'WL-OFF', 'NO-PENDING', 'NO-ACTION', 'WT-NO-ACTION')" in src
