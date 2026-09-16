# -*- coding: utf-8 -*-
"""
PostToolUse 150k 转场计量钩子（队列 §一 `#582`，Token 优化 Phase 2B）端到端单测。

同 `test_hooks-p3.py` 的既有理由：真跑 `pwsh` 脚本、真喂 stdin JSON，只断言
退出码 ＋ stdout（`hookSpecificOutput.additionalContext`，未越线时应为空）＋
`reports/hooks-audit.jsonl` 与 `reports/context-meter/<sid>.json` 落盘结果，
不 mock PowerShell 进程本身。全部夹具合成，不读真实 transcript。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent / "hooks"
CONTEXT_METER = HOOKS_DIR / "hooks-posttooluse-context-meter.ps1"

pytestmark = pytest.mark.skipif(
    shutil.which("pwsh") is None, reason="需要 PowerShell 7（pwsh）"
)


# ─────────────────────────────────────────────────────────────────────────────
# 驱动 ＋ 夹具
# ─────────────────────────────────────────────────────────────────────────────

def run_hook(payload: dict, repo_root: Path) -> tuple[int, dict, str, float]:
    """真跑一次钩子：喂 stdin JSON，返回 `(退出码, 解析后的 stdout JSON 或 {}, stderr, 耗时秒)`。"""
    env = dict(os.environ)
    env["ZHUOPIN_SENTINEL_REPO_ROOT"] = str(repo_root)
    t0 = time.monotonic()
    proc = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(CONTEXT_METER)],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        capture_output=True,
        env=env,
        cwd=str(repo_root),
    )
    elapsed = time.monotonic() - t0
    out = proc.stdout.decode("utf-8", errors="replace").strip()
    err = proc.stderr.decode("utf-8", errors="replace")
    parsed: dict = {}
    if out:
        try:
            parsed = json.loads(out)
        except json.JSONDecodeError:
            pass
    return proc.returncode, parsed, err, elapsed


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


def state_path(repo_root: Path, session_id: str) -> Path:
    return repo_root / "reports" / "context-meter" / f"{session_id}.json"


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
        # 三份拆成 input/cache_creation/cache_read 任意占比都行，判据只看总和。
        lines.append(assistant_line(input_tokens=2, cache_creation=ctx - 2, cache_read=0))
        lines.append(user_tool_result_line())
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def posttooluse_payload(transcript_path: Path, *, session_id: str = "s1", tool: str = "Bash") -> dict:
    return {
        "session_id": session_id,
        "hook_event_name": "PostToolUse",
        "tool_name": tool,
        "transcript_path": str(transcript_path),
    }


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    (tmp_path / "reports").mkdir()
    return tmp_path


# ─────────────────────────────────────────────────────────────────────────────
# 判据
# ─────────────────────────────────────────────────────────────────────────────

class TestContextMeter:
    def test_脚本文件存在(self):
        assert CONTEXT_METER.is_file()

    def test_未越线静默无输出(self, repo: Path):
        t = write_transcript(repo, 80_000)
        rc, out, err, _ = run_hook(posttooluse_payload(t), repo)
        assert rc == 0, err
        assert out == {}, "未越线时不应有任何 stdout 输出"
        lines = audit_lines(repo)
        assert lines[-1]["verdict"] == "pass"
        assert not state_path(repo, "s1").exists(), "未越线不应落状态文件"

    def test_越150k首次提醒(self, repo: Path):
        t = write_transcript(repo, 160_000)
        rc, out, err, _ = run_hook(posttooluse_payload(t), repo)
        assert rc == 0, err
        ctx = out.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "150k" in ctx or "150" in ctx
        assert "OPENER_PARTIAL" in ctx
        assert "160k" in ctx
        assert audit_lines(repo)[-1]["verdict"] == "remind"
        assert state_path(repo, "s1").is_file()
        state = json.loads(state_path(repo, "s1").read_text(encoding="utf-8"))
        assert state["lastTier"] == 1

    def test_同档不重复(self, repo: Path):
        t1 = write_transcript(repo, 160_000, name="t1.jsonl")
        rc1, out1, err1, _ = run_hook(posttooluse_payload(t1), repo)
        assert rc1 == 0, err1
        assert out1 != {}

        t2 = write_transcript(repo, 165_000, name="t2.jsonl")
        rc2, out2, err2, _ = run_hook(posttooluse_payload(t2), repo)
        assert rc2 == 0, err2
        assert out2 == {}, "同档（仍在 [150k,200k)）不应重复提醒"
        assert audit_lines(repo)[-1]["verdict"] == "pass"

    def test_软线措辞与硬线措辞(self, repo: Path):
        """09-16 两档：<250k 为软提醒（须先产出增量），≥250k 为硬线（立即收尾）。"""
        t1 = write_transcript(repo, 160_000)
        _, out1, _, _ = run_hook(posttooluse_payload(t1, session_id="tier-soft"), repo)
        ctx1 = out1["hookSpecificOutput"]["additionalContext"]
        assert "软提醒" in ctx1 and "增量" in ctx1 and "硬线：立即收尾" not in ctx1
        t2 = write_transcript(repo, 260_000)
        _, out2, _, _ = run_hook(posttooluse_payload(t2, session_id="tier-hard"), repo)
        ctx2 = out2["hookSpecificOutput"]["additionalContext"]
        assert "250k 硬线" in ctx2 and "立即收尾" in ctx2

    def test_越200k再提醒(self, repo: Path):
        t1 = write_transcript(repo, 160_000, name="t1.jsonl")
        run_hook(posttooluse_payload(t1), repo)

        t2 = write_transcript(repo, 205_000, name="t2.jsonl")
        rc2, out2, err2, _ = run_hook(posttooluse_payload(t2), repo)
        assert rc2 == 0, err2
        ctx = out2.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert ctx, "跨过 200k 档位应再次提醒"
        assert "205k" in ctx
        state = json.loads(state_path(repo, "s1").read_text(encoding="utf-8"))
        assert state["lastTier"] == 2

    def test_只看最后一条assistant记录(self, repo: Path):
        """第一条已越 150k，但最后一条又跌回 80k（模拟接力换新会话后同一 sessionId
        文件被复用的极端情形）——判据只应看最后一条，不应因"曾经越过"而提醒。"""
        t = write_transcript(repo, 200_000, 80_000)
        rc, out, err, _ = run_hook(posttooluse_payload(t), repo)
        assert rc == 0, err
        assert out == {}

    def test_transcript文件不存在时静默放行(self, repo: Path):
        rc, out, err, _ = run_hook(
            posttooluse_payload(repo / "不存在.jsonl"), repo)
        assert rc == 0, err
        assert out == {}
        assert audit_lines(repo)[-1]["verdict"] == "error"

    def test_transcript全是损坏行时静默放行(self, repo: Path):
        t = repo / "transcript.jsonl"
        t.write_text("这不是合法JSON\n{也不是}\n", encoding="utf-8")
        rc, out, err, _ = run_hook(posttooluse_payload(t), repo)
        assert rc == 0, err
        assert out == {}
        assert audit_lines(repo)[-1]["verdict"] == "error"

    def test_assistant记录缺usage字段时静默放行(self, repo: Path):
        t = repo / "transcript.jsonl"
        t.write_text(
            json.dumps({"type": "assistant", "message": {"role": "assistant", "content": []}}) + "\n",
            encoding="utf-8",
        )
        rc, out, err, _ = run_hook(posttooluse_payload(t), repo)
        assert rc == 0, err
        assert out == {}
        assert audit_lines(repo)[-1]["verdict"] == "error"

    def test_缺session_id或transcript_path时不拦工具(self, repo: Path):
        rc, out, err, _ = run_hook({"hook_event_name": "PostToolUse", "tool_name": "Bash"}, repo)
        assert rc == 0, err
        assert out == {}
        assert audit_lines(repo)[-1]["verdict"] == "undetermined"

    def test_stdin为空仍放行(self, repo: Path):
        env = dict(os.environ)
        env["ZHUOPIN_SENTINEL_REPO_ROOT"] = str(repo)
        proc = subprocess.run(
            ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(CONTEXT_METER)],
            input=b"", capture_output=True, env=env, cwd=str(repo),
        )
        assert proc.returncode == 0

    def test_不同session各自独立计档(self, repo: Path):
        t1 = write_transcript(repo, 160_000, name="t1.jsonl")
        run_hook(posttooluse_payload(t1, session_id="alpha"), repo)

        t2 = write_transcript(repo, 160_000, name="t2.jsonl")
        rc, out, err, _ = run_hook(posttooluse_payload(t2, session_id="beta"), repo)
        assert rc == 0, err
        ctx = out.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert ctx, "不同 session 的档位状态互不影响，beta 首次越线仍应提醒"

    def test_耗时断言_大文件尾读不随文件体量线性变慢(self, repo: Path):
        """回归锁：钩子若退化成对整份 transcript 做 `Get-Content -Raw` 全量解析，
        一份数十 MB 的 transcript 会让单次调用显著变慢。本测试只断言一个宽松的
        绝对上限（进程冷启动本身即占大头，不是复刻 p95 < 300ms 的生产 SLA），
        用于拦住"退化为全量扫描"这一类回归，不是精确计时。"""
        t = repo / "transcript.jsonl"
        # 前置巨量噪音行（每行数百字节，共约 20MB），目标记录紧贴文件尾部。
        padding_line = json.dumps(
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "content": "占位噪音" * 40}
            ]}}, ensure_ascii=False
        )
        with t.open("w", encoding="utf-8") as f:
            for _ in range(60_000):
                f.write(padding_line + "\n")
            f.write(assistant_line(input_tokens=2, cache_creation=159_998, cache_read=0) + "\n")
            f.write(user_tool_result_line() + "\n")

        rc, out, err, elapsed = run_hook(posttooluse_payload(t), repo)
        assert rc == 0, err
        ctx = out.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert ctx, "大文件场景下也应正确定位到尾部的越线记录"
        assert elapsed < 5.0, f"耗时 {elapsed:.2f}s 疑似退化为全量扫描（大文件仍应只读尾部窗口）"
