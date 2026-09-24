"""轮询守单测（队列 §一 `#575` 甲，`OP-0913-Q`，批 `B-0913_轮询守`，2026-09-13）。

看护件 §二 点名的三条路径＋判据字面锁定：
- 无信号不唤模型：探针 `[NO-SIGNAL]`＋巡检三个静默标记 ⇒ 桩 claude 零调用、留痕行 `woke=false`；
- 有信号唤一次：探针 `[SIGNAL]`（或巡检 `[MERGED]`）⇒ 桩 claude 恰好一次、prompt 带两条命令原文与「不要重跑」；
- 命令非零退出不静默吞：探针 stdout 仍是 `[NO-SIGNAL]` 但退出码 3 ⇒ 照样唤模型，stderr 进 prompt，留痕记 exit=3；
- 外加：无标记 fail-open、`[NO-PENDING]` 归静默（锁定与看护件字面「非 [NO-ACTION]」的有意偏差）、`-DryRun` 零副作用
  （探针得 `--peek`、巡检得 `-DryRun`、不唤模型但仍留痕）、每轮一行痕（跑两次＝两行）、静默集合字面锁定。

`OP-0913-S` 实机三修（批 `B-0913_轮询守实机三修`，看护件 §二 点名的四条新覆盖）：
- ⑴ 注册脚本 `工具-注册轮询守计划任务.ps1`：解析到 0 字节／ReparsePoint 的可执行文件 ⇒ 拒绝、退出非零、不打印包装内容；
  真身全过 ⇒ `-WhatIf` 退出 0 且包装里烘的是真身路径（本机若有 `%LOCALAPPDATA%\\Microsoft\\WindowsApps\\pwsh.exe` 别名，用它当活体样本）；
- ⑵ `run-poll-guard-hidden.vbs` 退出码透传：桩 `run-poll-guard.ps1` exit 7 ⇒ `cscript` 进程退出 7（此前恒 0）；
- ⑶ 常驻标记 `[WT-BLOCKED]` 同集合再现 ⇒ 不唤模型、留痕照写（`verdict=quiet-sticky:WT-BLOCKED`）；顺序不同不算变化；
- ⑷ 集合变化（多／少／换一个）⇒ 唤模型；状态文件只落留痕目录（`sticky-markers.json`）。

🔴 需要 PowerShell 7（`pwsh`）与 python；`claude -p` 一律用 `.ps1` 桩替掉，不真起会话。每个用例只碰 `tmp_path`。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
GUARD = TOOLS / "工具-轮询守.ps1"
REGISTER = TOOLS / "工具-注册轮询守计划任务.ps1"
VBS = TOOLS / "run-poll-guard-hidden.vbs"

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
        self.guard = tmp / 'guard.ps1'
        self.guard.write_text(GUARD.read_text(encoding='utf-8-sig').replace('Global\\ZhuopinPollGuard', 'Local\\PollFixture-' + uuid.uuid4().hex), encoding='utf-8-sig')
        self.claude = _write(tmp / 'provider.py',
            "import sys,json,pathlib\n"
            "args=sys.argv[1:]\n"
            "prompt=sys.stdin.read()\n"
            f"with open({str(self.claude_calls)!r},'a',encoding='utf-8') as f: f.write('ARGS: '+' '.join(args)+'\\n')\n"
            f"pathlib.Path({str(self.claude_prompt)!r}).write_text(prompt,encoding='utf-8')\n"
            "ev=pathlib.Path(args[args.index('--evidence')+1]); ev.mkdir(parents=True)\n"
            "(ev/'result.json').write_text(json.dumps({'status':'output_needs_review','thread_id':'fixture'}),encoding='utf-8')\n"
            "print('桩回复')\n")

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
                "pwsh", "-NoProfile", "-NonInteractive", "-File", str(self.guard),
                "-Repo", str(self.repo), "-LogDir", str(self.log),
                "-ProbeScript", str(self.probe), "-PatrolScript", str(self.patrol),
                "-ProviderScript", str(self.claude), "-ConsumerEnabled", "-SkillDoc", str(self.skill),
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
    assert "--sandbox read-only" in args and "--enabled" in args
    # 🔴 `Bash(git log:*)` 须作为**一个**参数到达（Start-Process 不自动加引号、CLI 按空格切分——2026-09-13 真 claude.exe 实测踩过）
    assert "--workspace " + str(rig.repo) in args
    prompt = rig.claude_prompt.read_text(encoding="utf-8")
    assert "不要重跑探针" in prompt and "不要重跑巡检" in prompt
    assert "桩章程" in prompt, "章程原文须整段进 prompt"
    assert "20260913-140558" in prompt, "探针 stdout 原样进 prompt"
    assert "[WT-NO-ACTION]" in prompt, "巡检 stdout 原样进 prompt"
    row = rig.rows()[-1]
    assert row["woke"] is True and row["signal"] is True
    assert row["probe"]["verdict"] == "markers:SIGNAL" and row["patrol"]["verdict"] == "quiet"
    assert row["model"]["exit"] == 0
    cap = Path(row["capture"])
    assert (cap / "model.out").read_text(encoding="utf-8").strip() == "桩回复"
    assert (cap / "prompt.txt").exists() and (cap / "probe.out").exists() and (cap / "patrol.out").exists()


def test_不给Model_继承Codex配置(rig: Rig):
    """队列 #581 ⑶：全仓 grep 补漏的第三处 claude -p 调用点（此前 `-Model` 默认 ''，与 v2.ps1 同款缺口）。"""
    rig.set_probe("[SIGNAL]\n批完成。\n")
    rig.set_patrol(QUIET_PATROL)
    proc = rig.run()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    args = rig.claude_calls.read_text(encoding="utf-8")
    assert "--model" not in args


def test_显式CodexModel_覆盖默认(rig: Rig):
    rig.set_probe("[SIGNAL]\n批完成。\n")
    rig.set_patrol(QUIET_PATROL)
    proc = rig.run("-Model", "gpt-6-astra")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    args = rig.claude_calls.read_text(encoding="utf-8")
    assert "--model gpt-6-astra" in args
    assert "--model sonnet" not in args


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
    assert "$PatrolStickyMarkers = @('WT-BLOCKED')" in src


# ── OP-0913-S 缺陷三：常驻标记按内容集合去重 ─────────────────────────────────

BLOCKED_AB = "[WL-NO-ACTION] 本轮白名单无可合入项。\n[NO-PENDING] 无待合登记。\n[WT-BLOCKED] musing-pascal-68d14e; recursing-hofstadter-eb7215"
BLOCKED_BA = "[WL-NO-ACTION] 本轮白名单无可合入项。\n[NO-PENDING] 无待合登记。\n[WT-BLOCKED] recursing-hofstadter-eb7215; musing-pascal-68d14e"
BLOCKED_ABC = "[WL-NO-ACTION] 本轮白名单无可合入项。\n[NO-PENDING] 无待合登记。\n[WT-BLOCKED] musing-pascal-68d14e; recursing-hofstadter-eb7215; gallant-lumiere-b482be"
BLOCKED_A = "[WL-NO-ACTION] 本轮白名单无可合入项。\n[NO-PENDING] 无待合登记。\n[WT-BLOCKED] musing-pascal-68d14e"


def test_sticky_same_set_does_not_wake_but_still_traces(rig: Rig):
    """第一轮实机留痕原样：探针安静、白名单无动作、登记处为空，唯一叫醒模型的是 [WT-BLOCKED]——常驻条件不是事件。"""
    rig.set_probe("[NO-SIGNAL] 无新事。\n")
    rig.set_patrol(BLOCKED_AB)
    assert rig.run().returncode == 0
    assert rig.claude_call_count() == 1, "首次出现＝新信号，唤一次"
    assert rig.run().returncode == 0
    assert rig.claude_call_count() == 1, "同一组 worktree 再现 ⇒ 不算新信号、不得再唤"
    rows = rig.rows()
    assert len(rows) == 2, "留痕照写：两轮两行"
    first, second = rows
    assert first["patrol"]["verdict"] == "markers:WT-BLOCKED" and first["woke"] is True
    assert first["patrol"]["sticky"]["WT-BLOCKED"]["changed"] is True
    assert second["patrol"]["verdict"] == "quiet-sticky:WT-BLOCKED" and second["woke"] is False and second["signal"] is False
    assert second["patrol"]["markers"] == ["WL-NO-ACTION", "NO-PENDING", "WT-BLOCKED"], "标记原样留痕，去重不改写标记"
    assert second["patrol"]["sticky"]["WT-BLOCKED"]["changed"] is False
    assert second["patrol"]["sticky"]["WT-BLOCKED"]["set"] == ["musing-pascal-68d14e", "recursing-hofstadter-eb7215"]
    assert "capture" not in second, "被去重的安静轮不该存全文捕获"
    state = rig.log / "sticky-markers.json"
    assert state.exists(), "集合必须落盘比对，不许只比标记名"
    data = json.loads(state.read_text(encoding="utf-8"))
    assert sorted(data["WT-BLOCKED"]["set"]) == ["musing-pascal-68d14e", "recursing-hofstadter-eb7215"]
    assert data["WT-BLOCKED"]["suppressed"] == 1
    assert "合入登记" not in str(state)


def test_sticky_set_order_does_not_matter(rig: Rig):
    rig.set_probe("[NO-SIGNAL] 无新事。\n")
    rig.set_patrol(BLOCKED_AB)
    assert rig.run().returncode == 0
    rig.set_patrol(BLOCKED_BA)
    assert rig.run().returncode == 0
    assert rig.claude_call_count() == 1
    assert rig.rows()[-1]["patrol"]["verdict"] == "quiet-sticky:WT-BLOCKED"


@pytest.mark.parametrize("changed", [BLOCKED_ABC, BLOCKED_A], ids=["多一个", "少一个"])
def test_sticky_set_change_wakes_model(rig: Rig, changed: str):
    rig.set_probe("[NO-SIGNAL] 无新事。\n")
    rig.set_patrol(BLOCKED_AB)
    assert rig.run().returncode == 0
    assert rig.run().returncode == 0
    assert rig.claude_call_count() == 1
    rig.set_patrol(changed)
    assert rig.run().returncode == 0
    assert rig.claude_call_count() == 2, "集合变化 ⇒ 新信号、唤模型"
    row = rig.rows()[-1]
    assert row["patrol"]["verdict"] == "markers:WT-BLOCKED" and row["woke"] is True
    assert row["patrol"]["sticky"]["WT-BLOCKED"]["changed"] is True
    assert row["patrol"]["sticky"]["WT-BLOCKED"]["prev"] == ["musing-pascal-68d14e", "recursing-hofstadter-eb7215"]
    prompt = rig.claude_prompt.read_text(encoding="utf-8")
    assert "常驻标记 [WT-BLOCKED] 内容集合较上次落盘变化" in prompt
    # 变化后的集合再现 ⇒ 又归静默
    assert rig.run().returncode == 0
    assert rig.claude_call_count() == 2


def test_sticky_swap_one_wakes_model(rig: Rig):
    rig.set_probe("[NO-SIGNAL] 无新事。\n")
    rig.set_patrol(BLOCKED_AB)
    assert rig.run().returncode == 0
    rig.set_patrol("[WL-NO-ACTION] x\n[NO-PENDING] y\n[WT-BLOCKED] musing-pascal-68d14e; gallant-lumiere-b482be")
    assert rig.run().returncode == 0
    assert rig.claude_call_count() == 2, "换一个也算变化"


def test_sticky_disappear_then_reappear_is_new_signal(rig: Rig):
    rig.set_probe("[NO-SIGNAL] 无新事。\n")
    rig.set_patrol(BLOCKED_AB)
    assert rig.run().returncode == 0
    rig.set_patrol(QUIET_PATROL)
    assert rig.run().returncode == 0
    assert rig.claude_call_count() == 1
    assert rig.rows()[-1]["patrol"]["verdict"] == "quiet" and "sticky" not in rig.rows()[-1]["patrol"]
    assert "WT-BLOCKED" not in json.loads((rig.log / "sticky-markers.json").read_text(encoding="utf-8"))
    rig.set_patrol(BLOCKED_AB)
    assert rig.run().returncode == 0
    assert rig.claude_call_count() == 2, "消失后再出现＝新信号"


def test_sticky_dedup_does_not_mask_other_signals(rig: Rig):
    rig.set_probe("[NO-SIGNAL] 无新事。\n")
    rig.set_patrol(BLOCKED_AB)
    assert rig.run().returncode == 0
    rig.set_patrol(BLOCKED_AB + "\n[MERGED] claude/op0913x-demo")
    assert rig.run().returncode == 0
    assert rig.claude_call_count() == 2
    assert rig.rows()[-1]["patrol"]["verdict"] == "markers:MERGED", "去重只摘常驻标记，别的响亮标记照旧"
    rig.set_probe("[SIGNAL]\n有事。\n")
    rig.set_patrol(BLOCKED_AB)
    assert rig.run().returncode == 0
    assert rig.claude_call_count() == 3, "探针侧信号不受巡检侧去重影响"
    assert rig.rows()[-1]["patrol"]["verdict"] == "quiet-sticky:WT-BLOCKED"


def test_sticky_nonzero_exit_still_signals(rig: Rig):
    rig.set_probe("[NO-SIGNAL] 无新事。\n")
    rig.set_patrol(BLOCKED_AB)
    assert rig.run().returncode == 0
    rig.set_patrol(BLOCKED_AB, exit_code=1, stderr="巡检异常 zz-43")
    assert rig.run().returncode == 0
    assert rig.claude_call_count() == 2 and rig.rows()[-1]["patrol"]["verdict"] == "exit:1"


def test_sticky_dry_run_does_not_persist_state(rig: Rig):
    rig.set_probe("[NO-SIGNAL] 无新事。\n")
    rig.set_patrol(BLOCKED_AB)
    assert rig.run("-DryRun").returncode == 0
    assert not (rig.log / "sticky-markers.json").exists(), "干跑零副作用，不落状态"
    assert rig.rows()[-1]["signal"] is True and rig.rows()[-1]["woke"] is False


# ── OP-0913-S 缺陷一：注册脚本 fail-loud 校验可执行文件真身 ──────────────────

def _real_pwsh() -> str:
    """shutil.which('pwsh') 在本机可能就是那个 0 字节别名，真身要向 pwsh 进程自己要。"""
    out = subprocess.run(["pwsh", "-NoProfile", "-c", "(Get-Process -Id $PID).Path"], capture_output=True, text=True, encoding="utf-8")
    return out.stdout.strip()


def _run_register(**exe: str) -> subprocess.CompletedProcess:
    args = ["pwsh", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(REGISTER), "-Repo", str(TOOLS.parent), "-WhatIf"]
    for k, v in exe.items():
        args += [f"-{k}", v]
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=120)


def _real_exes(**override: str) -> dict[str, str]:
    git = shutil.which("git")
    base = {"PwshExe": _real_pwsh(), "PythonExe": sys.executable, "GitExe": git or sys.executable,
            "CodexExe": sys.executable, "NodeExe": sys.executable}   # claude/node 只要求是真二进制，拿 python 顶替即可
    base.update(override)
    return base


def test_register_accepts_real_binaries_and_bakes_real_pwsh_path():
    proc = _run_register(**_real_exes())
    assert proc.returncode == 0, proc.stdout + proc.stderr
    real = _real_pwsh()
    assert f'-PwshExe "{real}"' in proc.stdout, "包装里烘的必须是真身"
    assert "Local\\Microsoft\\WindowsApps\\pwsh.exe" not in proc.stdout, "别名路径不得出现在包装里"
    assert "exit 9" in proc.stdout, "包装起手校验 pwsh 存在，不存在留痕＋exit 9"


@pytest.mark.parametrize("which", ["PwshExe", "PythonExe", "GitExe", "CodexExe", "NodeExe"])
def test_register_rejects_zero_byte_executable(tmp_path: Path, which: str):
    fake = tmp_path / "fake.exe"
    fake.write_bytes(b"")
    proc = _run_register(**_real_exes(**{which: str(fake)}))
    assert proc.returncode != 0, "0 字节可执行文件必须拒绝并退出非零"
    combined = proc.stdout + proc.stderr
    assert "Length=0" in combined and "不生成包装、不注册" in combined
    assert "[WhatIf] 将写入" not in proc.stdout and "[WhatIf] 将注册" not in proc.stdout, "拒绝时不得走到生成包装／注册两步"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows 应用执行别名")
def test_register_rejects_app_execution_alias_reparse_point():
    """活体样本：%LOCALAPPDATA%\\Microsoft\\WindowsApps\\pwsh.exe（Length=0、ReparsePoint）——第一轮实机就是被它打回来的。"""
    import os
    alias = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps" / "pwsh.exe"
    if not alias.exists():
        pytest.skip("本机没有 pwsh 应用执行别名")
    proc = _run_register(**_real_exes(PwshExe=str(alias)))
    assert proc.returncode != 0
    assert "ReparsePoint" in proc.stdout + proc.stderr


def test_register_symlink_is_rejected_when_creatable(tmp_path: Path):
    link = tmp_path / "link.exe"
    try:
        link.symlink_to(Path(sys.executable))
    except OSError:
        pytest.skip("本机无创建符号链接的权限")
    proc = _run_register(**_real_exes(PythonExe=str(link)))
    assert proc.returncode != 0 and "ReparsePoint" in proc.stdout + proc.stderr


# ── OP-0913-S 缺陷二：VBS 退出码透传 ──────────────────────────────────────────

@pytest.mark.skipif(sys.platform != "win32" or shutil.which("cscript") is None, reason="需要 Windows cscript")
@pytest.mark.parametrize("code", [7, 0], ids=["非零", "零"])
def test_vbs_passes_through_wrapper_exit_code(tmp_path: Path, code: int):
    """桩 run-poll-guard.ps1 放在 VBS 同目录（scriptDir 动态取自身所在目录），exit N 必须原样成为 cscript 的退出码。"""
    vbs = tmp_path / "run-poll-guard-hidden.vbs"
    vbs.write_bytes(VBS.read_bytes())
    (tmp_path / "run-poll-guard.ps1").write_text(f"exit {code}\n", encoding="utf-8-sig")
    proc = subprocess.run(["cscript", "//nologo", str(vbs)], capture_output=True, text=True, timeout=120)
    assert proc.returncode == code, f"VBS 吞了退出码：期望 {code}，得到 {proc.returncode}；{proc.stdout}{proc.stderr}"
