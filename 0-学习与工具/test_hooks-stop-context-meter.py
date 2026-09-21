# -*- coding: utf-8 -*-
"""
Stop 读取面钩子（队列 §一 `#639`，泳道读取面切分）端到端单测。

同 `test_hooks-context-meter.py` 的既有理由：真跑 `pwsh` 脚本、真喂 stdin JSON，
只断言退出码 ＋ stdout（本钩子恒不产出 `additionalContext`）＋
`reports/hooks-audit.jsonl` 与 `reports/context-meter/<sid>.json` 落盘结果，不 mock
PowerShell 进程本身。全部夹具合成，不读真实 transcript。

🔑 `test_读取面缺口_纯文本收尾轮次的usage只有Stop钩子补得上` 是本次改动的核心证据：
复现队列 #639 实测现象的最小场景——末轮回复不含工具调用直接收尾，PostToolUse
因此从未读到那条 usage，闸持续低估；断言里给出改动前（只跑 PostToolUse）与
改动后（PostToolUse + Stop）两个具体读数，即"改后误差的实测数"。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent / "hooks"
POSTTOOLUSE_METER = HOOKS_DIR / "hooks-posttooluse-context-meter.ps1"
STOP_METER = HOOKS_DIR / "hooks-stop-context-meter.ps1"

pytestmark = pytest.mark.skipif(
    shutil.which("pwsh") is None, reason="需要 PowerShell 7（pwsh）"
)


def run_hook(script: Path, payload: dict, repo_root: Path) -> tuple[int, dict, str]:
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


def assistant_line(input_tokens: int, cache_creation: int, cache_read: int) -> str:
    return json.dumps(
        {
            "type": "assistant",
            "sessionId": "s",
            "message": {
                "usage": {
                    "input_tokens": input_tokens,
                    "cache_creation_input_tokens": cache_creation,
                    "cache_read_input_tokens": cache_read,
                    "output_tokens": 10,
                }
            },
        },
        ensure_ascii=False,
    )


def user_tool_result_line(text: str = "（工具结果，不含 usage）") -> str:
    return json.dumps(
        {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "content": text}]}},
        ensure_ascii=False,
    )


def write_transcript(repo_root: Path, *contexts: int, name: str = "transcript.jsonl") -> Path:
    """按顺序为每个 `contexts` 值追加一条 assistant usage 记录，中间穿插一条
    工具结果噪音行，模拟"assistant 消息 → 工具调用 → 工具结果"真实交替序列。
    最新一条在文件末尾——判据只应看最后一条。"""
    p = repo_root / name
    lines = []
    for ctx in contexts:
        lines.append(assistant_line(input_tokens=2, cache_creation=ctx - 2, cache_read=0))
        lines.append(user_tool_result_line())
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def audit_lines(repo_root: Path) -> list[dict]:
    p = repo_root / "reports" / "hooks-audit.jsonl"
    if not p.is_file():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def state_path(repo_root: Path, session_id: str) -> Path:
    return repo_root / "reports" / "context-meter" / f"{session_id}.json"


def stop_payload(transcript_path: Path, *, session_id: str = "s1", stop_hook_active: bool = False) -> dict:
    return {
        "session_id": session_id,
        "hook_event_name": "Stop",
        "transcript_path": str(transcript_path),
        "stop_hook_active": stop_hook_active,
    }


def posttooluse_payload(transcript_path: Path, *, session_id: str = "s1") -> dict:
    return {
        "session_id": session_id,
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "transcript_path": str(transcript_path),
    }


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    (tmp_path / "reports").mkdir()
    return tmp_path


class TestStopContextMeter:
    def test_脚本文件存在(self):
        assert STOP_METER.is_file()

    def test_恒不产出additionalContext(self, repo: Path):
        t = write_transcript(repo, 260_000)
        rc, out, err = run_hook(STOP_METER, stop_payload(t), repo)
        assert rc == 0, err
        assert out == {}, "Stop 读取面只补状态，不重复提醒"

    def test_写入状态文件(self, repo: Path):
        t = write_transcript(repo, 160_000)
        rc, out, err = run_hook(STOP_METER, stop_payload(t), repo)
        assert rc == 0, err
        state = json.loads(state_path(repo, "s1").read_text(encoding="utf-8"))
        assert state["lastContext"] == 160_000
        assert state["lastTier"] == 1

    def test_档位只升不降(self, repo: Path):
        """状态里已记过更高档位时，Stop 读到的当前值若换算出更低档位，不应回退档位。"""
        t1 = write_transcript(repo, 200_000, name="t1.jsonl")
        run_hook(STOP_METER, stop_payload(t1), repo)
        t2 = write_transcript(repo, 80_000, name="t2.jsonl")
        run_hook(STOP_METER, stop_payload(t2), repo)
        state = json.loads(state_path(repo, "s1").read_text(encoding="utf-8"))
        assert state["lastTier"] == 2, "80k 换算出 0 档，不应覆盖已记的 2 档"
        assert state["lastContext"] == 80_000, "lastContext 仍如实记当前读数，只有 lastTier 不回退"

    def test_保留toolCalls与callCountNotified不被本钩子改动(self, repo: Path):
        meter_dir = repo / "reports" / "context-meter"
        meter_dir.mkdir(parents=True, exist_ok=True)
        (meter_dir / "s1.json").write_text(
            json.dumps({"lastTier": 0, "lastContext": 10_000, "lastTs": "x",
                        "toolCalls": 42, "callCountNotified": True}, ensure_ascii=False),
            encoding="utf-8",
        )
        t = write_transcript(repo, 80_000)
        run_hook(STOP_METER, stop_payload(t), repo)
        state = json.loads(state_path(repo, "s1").read_text(encoding="utf-8"))
        assert state["toolCalls"] == 42
        assert state["callCountNotified"] is True

    def test_stop_hook_active时仍照常补写(self, repo: Path):
        """与 hooks-stop-decision-check.ps1 不同：本钩子不是格式判定，重试轮次的
        transcript 只会更长，补问轮次攒的上下文也该被计入，不该被防循环开关挡住。"""
        t = write_transcript(repo, 160_000)
        rc, out, err = run_hook(STOP_METER, stop_payload(t, stop_hook_active=True), repo)
        assert rc == 0, err
        state = json.loads(state_path(repo, "s1").read_text(encoding="utf-8"))
        assert state["lastContext"] == 160_000

    def test_transcript文件不存在时静默放行(self, repo: Path):
        rc, out, err = run_hook(STOP_METER, stop_payload(repo / "不存在.jsonl"), repo)
        assert rc == 0, err
        assert out == {}
        assert audit_lines(repo)[-1]["verdict"] == "error"

    def test_缺session_id或transcript_path时不拦(self, repo: Path):
        rc, out, err = run_hook(STOP_METER, {"hook_event_name": "Stop"}, repo)
        assert rc == 0, err
        assert out == {}
        assert audit_lines(repo)[-1]["verdict"] == "undetermined"

    def test_stdin为空仍放行(self, repo: Path):
        env = dict(os.environ)
        env["ZHUOPIN_SENTINEL_REPO_ROOT"] = str(repo)
        proc = subprocess.run(
            ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(STOP_METER)],
            input=b"", capture_output=True, env=env, cwd=str(repo),
        )
        assert proc.returncode == 0

    # ── 核心证据：读取面缺口与补齐后的实测差值 ──────────────────────────

    def test_读取面缺口_纯文本收尾轮次的usage只有Stop钩子补得上(self, repo: Path):
        """复现队列 #639 实测现象的最小场景：三轮对话，前两轮各带一次工具调用
        （PostToolUse 各触发一次），第三轮（真实峰值所在）是纯文本收尾、不含
        工具调用——PostToolUse 因此永远不会为第三轮触发。

        断言给出两个具体读数：
        - 只跑 PostToolUse（旧行为）：状态停在第二轮的 200_000，未曾追上第三轮
          的 215_000，误差 15_000（对应队列 #639 实测的「闸持续偏低」现象）。
        - 追加跑 Stop（新行为）：状态被补写到第三轮的真实值 215_000，误差归零。
        """
        t = repo / "transcript.jsonl"

        # 第一轮：assistant(180_000) + 工具调用 ⇒ PostToolUse #1 在此刻触发
        lines = [assistant_line(input_tokens=2, cache_creation=179_998, cache_read=0),
                 user_tool_result_line()]
        t.write_text("\n".join(lines) + "\n", encoding="utf-8")
        rc1, _, err1 = run_hook(POSTTOOLUSE_METER, posttooluse_payload(t), repo)
        assert rc1 == 0, err1

        # 第二轮：assistant(200_000) + 工具调用 ⇒ PostToolUse #2 在此刻触发
        lines.extend([assistant_line(input_tokens=2, cache_creation=199_998, cache_read=0),
                      user_tool_result_line()])
        t.write_text("\n".join(lines) + "\n", encoding="utf-8")
        rc2, _, err2 = run_hook(POSTTOOLUSE_METER, posttooluse_payload(t), repo)
        assert rc2 == 0, err2

        # 旧行为核验点：只有前两轮的 PostToolUse 跑过，状态应停在 200_000。
        old_state = json.loads(state_path(repo, "s1").read_text(encoding="utf-8"))
        OLD_TRUE_PEAK = 215_000
        old_gap = OLD_TRUE_PEAK - old_state["lastContext"]
        assert old_state["lastContext"] == 200_000
        assert old_gap == 15_000, f"复现队列#639现象：PostToolUse-only 读数与真实峰值差 {old_gap}"

        # 第三轮：assistant(215_000)，纯文本收尾——不追加工具结果行，不触发 PostToolUse，
        # 只有 Stop 事件会发生。
        lines.append(assistant_line(input_tokens=2, cache_creation=214_998, cache_read=0))
        t.write_text("\n".join(lines) + "\n", encoding="utf-8")
        rc3, out3, err3 = run_hook(STOP_METER, stop_payload(t), repo)
        assert rc3 == 0, err3

        # 新行为核验点：Stop 读取面补写后，状态应追上真实峰值，误差归零。
        new_state = json.loads(state_path(repo, "s1").read_text(encoding="utf-8"))
        new_gap = OLD_TRUE_PEAK - new_state["lastContext"]
        assert new_state["lastContext"] == 215_000
        assert new_gap == 0, f"Stop 读取面补写后应追平真实峰值，实测残差 {new_gap}"
        assert new_state["lastTier"] == 2, "215_000 应换算出 2 档（[200k,250k)）"
