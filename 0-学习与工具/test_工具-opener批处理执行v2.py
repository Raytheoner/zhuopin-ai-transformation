"""`工具-opener批处理执行v2.ps1` v2.1 单测（队列 §一 `#549` ⑴⑵，承接 `#522` ⑷⑸，2026-09-10）。

三件事各配正例：
- **`--resume` 接管**：每条 opener 的 session id 由脚本先定、以 `--session-id` 交给 `claude`，
  并写进日志首行与 `summary.txt` 的 Session 列（`summary.json` 机读副本同样带）。
- **`-Detach`**：后台起、立即返回日志目录；子进程退出码落 `exit.txt`（launcher 不再丢退出码）。
- **解析器不动**：`### A<N>` 三件套那段是 `#550` 的触碰面，本清单只证明它对 `-DryRun` 仍解得出。

🔴 `claude` 用一个放在临时 PATH 里的桩（`claude.cmd`）顶替：把收到的参数回显一遍、再打
`OPENER_DONE`——**测的是本脚本怎么起它**，不是 claude 本身。真 claude 一次要跑几十分钟，
且会真的改仓库。
🔴 需要 PowerShell 7（`pwsh`）；没有即整文件跳过（同 `test_hooks-p3.py` 手法）。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().with_name("工具-opener批处理执行v2.ps1")
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

pytestmark = pytest.mark.skipif(
    shutil.which("pwsh") is None or os.name != "nt", reason="需要 Windows ＋ PowerShell 7（pwsh）"
)

#: 最小 plan：一个泳道一条 opener（`### A1` ＋ 粘贴端／泳道行 ＋ 围栏块）。
PLAN_TEXT = "\n".join([
    "# 波次计划（单测夹具）", "",
    "### A1 · 示例泳道", "",
    "粘贴端：CC ｜ 泳道：demo-lane", "",
    "```",
    "[OP-1231-A]【CC】示例任务",
    "【设置】执行环境：CC ｜ 分支：master（从 master 起 `claude/op1231a-demo`） ｜ worktree：☑（demo，新 worktree，收工自删） ｜ 工作区：无 ｜ session：新开 ｜ 派出线：环境总线",
    "读 ① 队列 §一 `#549` → ② `CLAUDE.md` 恢复上下文，按该行执行。本件为 A 类，直接开工。",
    "```", "",
])

#: 桩 claude：回显参数（供断言 `--session-id <id>` 真的传到了）并打哨兵。
CLAUDE_STUB = "@echo off\r\necho STUB-ARGS: %*\r\necho OPENER_DONE\r\nexit /b 0\r\n"


def _run(args: list[str], cwd: Path, env: dict, timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-File", str(SCRIPT), *args],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=timeout,
    )


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.plan = self.root / "plan.md"
        self.plan.write_text(PLAN_TEXT, encoding="utf-8")
        stub_dir = self.root / "stub"
        stub_dir.mkdir()
        (stub_dir / "claude.cmd").write_text(CLAUDE_STUB, encoding="ascii")
        self.env = dict(os.environ)
        self.env["PATH"] = str(stub_dir) + os.pathsep + self.env.get("PATH", "")
        self.log_dir = self.root / "batch-log"

    def tearDown(self):
        self._tmp.cleanup()


class 解析与DryRun(_Base):
    def test_dry_run_解得出泳道且写exit_txt(self):
        r = _run(["-Plan", str(self.plan), "-DryRun", "-LogDir", str(self.log_dir)], self.root, self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("demo-lane", r.stdout)
        self.assertIn("A1", r.stdout)
        # `-LogDir` 已定 ⇒ 任何退出点都落退出码（-Detach 调用方靠它，不靠进程句柄）。
        self.assertEqual((self.log_dir / "exit.txt").read_text(encoding="utf-8").strip(), "0")


class Resume接管_session_id(_Base):
    def test_session_id先定_传给claude_并落日志首行与summary(self):
        r = _run(["-Plan", str(self.plan), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir)],
                 self.root, self.env, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        log = self.log_dir / "demo-lane-A1.log"
        self.assertTrue(log.is_file(), sorted(p.name for p in self.log_dir.iterdir()))
        first = log.read_text(encoding="utf-8-sig").splitlines()[0]
        m = re.search(r"session=(" + UUID_RE.pattern + ")", first)
        self.assertIsNotNone(m, f"日志首行无 session id：{first!r}")
        sid = m.group(1)
        self.assertIn(f"claude --resume {sid}", first)
        # 桩回显证明 `--session-id <同一个 id>` 真的传给了 claude（不是只写在日志里）。
        body = log.read_text(encoding="utf-8-sig")
        self.assertIn(f"--session-id {sid}", body)
        # summary.txt 表格带 Session 列且值就是那个 id；末行 EXIT=0。
        summary = (self.log_dir / "summary.txt").read_text(encoding="utf-8-sig")
        self.assertIn("Session", summary)
        self.assertIn(sid, summary)
        self.assertRegex(summary, r"EXIT=0\s*$")
        # 机读副本同样带。
        rows = json.loads((self.log_dir / "summary.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Session"], sid)
        self.assertEqual(rows[0]["Status"], "OK")
        self.assertEqual((self.log_dir / "exit.txt").read_text(encoding="utf-8").strip(), "0")

    def test_两条opener各自不同的session_id(self):
        plan2 = PLAN_TEXT + "\n".join([
            "### A2 · 第二条", "", "粘贴端：CC ｜ 泳道：demo-lane", "",
            "```", "[OP-1231-B]【CC】示例二",
            "【设置】执行环境：CC ｜ 分支：master ｜ worktree：☐ ｜ 工作区：无 ｜ session：新开 ｜ 派出线：环境总线",
            "读 ① 队列 §一 `#549`。", "```", "",
        ])
        self.plan.write_text(plan2, encoding="utf-8")
        r = _run(["-Plan", str(self.plan), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir)],
                 self.root, self.env, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rows = json.loads((self.log_dir / "summary.json").read_text(encoding="utf-8-sig"))
        sids = {row["Session"] for row in rows}
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(sids), 2, "两条 opener 不得共用一个 session id")


class Detach后台起(_Base):
    def test_立即返回日志目录_子进程退出码落exit_txt(self):
        t0 = time.monotonic()
        r = _run(["-Plan", str(self.plan), "-Detach", "-DryRun", "-LogDir", str(self.log_dir)],
                 self.root, self.env)
        elapsed = time.monotonic() - t0
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # stdout 末行＝日志目录（Cowork 取它）。
        self.assertEqual(r.stdout.strip().splitlines()[-1].strip(), str(self.log_dir))
        launcher = json.loads((self.log_dir / "launcher.json").read_text(encoding="utf-8-sig"))
        self.assertIn("pid", launcher)
        self.assertEqual(Path(launcher["log_dir"]), self.log_dir)
        self.assertEqual(Path(launcher["exit_file"]), self.log_dir / "exit.txt")
        # 子进程（-DryRun）应很快结束并把退出码写下来；launcher 自己**不等它**。
        deadline = time.monotonic() + 90
        exit_file = self.log_dir / "exit.txt"
        while not exit_file.is_file() and time.monotonic() < deadline:
            time.sleep(0.5)
        self.assertTrue(exit_file.is_file(), "子进程未落 exit.txt（-Detach 拿不到退出码＝本项要消灭的形态）")
        self.assertEqual(exit_file.read_text(encoding="utf-8").strip(), "0")
        child_out = (self.log_dir / "launcher-stdout.log").read_text(encoding="utf-8-sig")
        self.assertIn("demo-lane", child_out)
        self.assertLess(elapsed, 60, "launcher 应立即返回，不该等子进程")


if __name__ == "__main__":
    unittest.main()
