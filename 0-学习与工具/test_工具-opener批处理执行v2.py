"""`工具-opener批处理执行v2.ps1` v2.1 单测（队列 §一 `#549` ⑴⑵，承接 `#522` ⑷⑸，2026-09-10）。

四件事各配正例：
- **`NO-SENTINEL` 补问（v2.2，`#550` 重定向棒 `OP-0910-S`）**：首轮无哨兵 ⇒ 用 `claude --resume <同一个 sid>`
  补问一次；拿到即 `OK`／`PARTIAL` 且 `Sentinel=补问`（与首轮自觉输出分开计数）；两轮都无 ⇒ 仍 `NO-SENTINEL`
  并停本泳道；补问挂死 ⇒ 到 `-SentinelRetryTimeoutSec` 整树 kill、判 `NO-SENTINEL`、不无限等；`FAIL` 不补问。
  🔴 变异守卫：把脚本里 `>>> #550 补问 begin`…`<<< end` 整段抽掉，第一条用例必须转红——否则它是恒真的。
  历史回放：四条立行实证泳道的**首轮输出形态**（544 反引号包哨兵／507·529 被 600s 上限掐断／k2 本就 PARTIAL）
  用桩逐字复现；🔴 真 session id 的回放不在单测里（要真跑 claude），在队列 `#550` 行内另记。
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


def _stub_two_round(first: str, retry: str, hang_retry_sec: int = 0, exit_code: int = 0) -> str:
    """两轮桩：无 `--resume` ＝首轮，打 `first`；带 `--resume` ＝补问，打 `retry`。

    `first`／`retry` 每行一条 `echo`（空串＝什么都不打）。`hang_retry_sec>0` ⇒ 补问先 ping 挂住这么多秒
    （模拟补问自身挂死），`exit_code` ⇒ 首轮退出码（FAIL 场景）。也回显 `STUB-CWD`，证泳道 Job 真在仓库根跑。
    """
    def _echo(block: str) -> str:
        return "".join(f"echo {ln}\r\n" for ln in block.splitlines() if ln.strip())
    hang = f"ping -n {hang_retry_sec + 1} 127.0.0.1 >nul\r\n" if hang_retry_sec else ""
    return (
        "@echo off\r\n"
        "echo STUB-ARGS: %*\r\n"
        "echo STUB-CWD: %CD%\r\n"
        "echo %* | findstr /C:\"--resume\" >nul\r\n"
        "if %errorlevel%==0 (\r\n"
        f"{hang}{_echo(retry)}exit /b 0\r\n"
        ")\r\n"
        f"{_echo(first)}exit /b {exit_code}\r\n"
    )


#: 2026-09-10 四条立行实证泳道的首轮末尾形态（自 `reports/opener-batch/20260910-14*/` 各 .log 逐字摘）。
#: 544：哨兵被包进反引号，`^OPENER_DONE\s*$` 不命中；507／529：claude 自身「Background tasks still running
#: after 600s; terminating」把会话掐断在收尾前，只剩一句进度；k2：本就 `OPENER_PARTIAL:` 顶格，不该触发补问。
HISTORY_FIRST_ROUND = {
    "544-heartbeat-batch": "`OPENER_DONE`\n## OP-0910-M · #544 收工回执",
    "507-sweep-apply": "Queue writeback done and verified. Waiting on the two full-suite runs before the final --append and worktree cleanup.",
    "529-timeout-semantics": "While the regression finishes, here is the state of the lane so far.",
    "k2-externalize": "OPENER_PARTIAL: 超限行 23→1，仅余 #537 按「不降质外置」留步，待下轮 #443 清扫迁档消解。",
}


def _run(args: list[str], cwd: Path, env: dict, timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-File", str(SCRIPT), *args],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=timeout,
    )


class _Base(unittest.TestCase):
    STUB = CLAUDE_STUB

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.plan = self.root / "plan.md"
        self.plan.write_text(PLAN_TEXT, encoding="utf-8")
        stub_dir = self.root / "stub"
        stub_dir.mkdir()
        self.stub_file = stub_dir / "claude.cmd"
        self.stub_file.write_text(self.STUB, encoding="utf-8")
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


class NoSentinel补问(_Base):
    """v2.2 `#550`：判出 NO-SENTINEL 先 `--resume` 补问一次，仍无才停本泳道。"""

    def _run_batch(self, extra: list[str] | None = None, script: Path | None = None, retry_timeout: int = 20):
        args = ["-Plan", str(self.plan), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir),
                "-SentinelRetryTimeoutSec", str(retry_timeout), *(extra or [])]
        if script is None:
            return _run(args, self.root, self.env, timeout=300)
        return subprocess.run(
            ["pwsh", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script), *args],
            cwd=self.root, capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=self.env, timeout=300,
        )

    def _rows(self) -> list[dict]:
        return json.loads((self.log_dir / "summary.json").read_text(encoding="utf-8-sig"))

    def _set_stub(self, text: str):
        self.stub_file.write_text(text, encoding="utf-8")

    def test_首轮无哨兵_补问拿到DONE_判OK且Sentinel标补问(self):
        self._set_stub(_stub_two_round(first="活干完了但忘了哨兵", retry="OPENER_DONE"))
        r = self._run_batch()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rows = self._rows()
        self.assertEqual(rows[0]["Status"], "OK")
        self.assertEqual(rows[0]["Sentinel"], "补问", "补问拿到的必须与首轮自觉输出分开标——否则遵守率被掩盖")
        sid = rows[0]["Session"]
        # 补问用的是**同一个** session id 的 --resume，且补问输出单独落盘。
        retry_log = self.log_dir / "demo-lane-A1.retry.log"
        self.assertTrue(retry_log.is_file(), sorted(p.name for p in self.log_dir.iterdir()))
        self.assertIn(f"--resume {sid}", retry_log.read_text(encoding="utf-8-sig"))
        self.assertIn("--resume", (self.log_dir / "demo-lane-A1.log").read_text(encoding="utf-8-sig"))
        summary = (self.log_dir / "summary.txt").read_text(encoding="utf-8-sig")
        self.assertIn("SENTINEL_FIRST=0", summary)
        self.assertIn("SENTINEL_RETRY=1", summary)
        self.assertIn("SENTINEL_NONE=0", summary)
        self.assertRegex(summary, r"EXIT=0\s*$")

    def test_补问拿到PARTIAL_判PARTIAL(self):
        self._set_stub(_stub_two_round(first="做到一半停在决策点", retry="OPENER_PARTIAL: 停在 design 审"))
        r = self._run_batch()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rows = self._rows()
        self.assertEqual(rows[0]["Status"], "PARTIAL")
        self.assertEqual(rows[0]["Sentinel"], "补问")

    def test_首轮自觉输出_不补问_Sentinel标首轮(self):
        r = self._run_batch()  # 默认桩：首轮即 OPENER_DONE
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rows = self._rows()
        self.assertEqual(rows[0]["Sentinel"], "首轮")
        self.assertFalse((self.log_dir / "demo-lane-A1.retry.log").exists(), "首轮已有哨兵不得再补问")
        self.assertIn("SENTINEL_FIRST=1", (self.log_dir / "summary.txt").read_text(encoding="utf-8-sig"))

    def test_两轮都无_仍NO_SENTINEL_并停本泳道(self):
        plan2 = PLAN_TEXT + "\n".join([
            "### A2 · 同泳道后续", "", "粘贴端：CC ｜ 泳道：demo-lane", "",
            "```", "[OP-1231-B]【CC】示例二", "读 ① 队列 §一 `#550`。", "```", "",
        ])
        self.plan.write_text(plan2, encoding="utf-8")
        self._set_stub(_stub_two_round(first="没哨兵", retry="还是没哨兵"))
        r = self._run_batch()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        rows = self._rows()
        self.assertEqual(len(rows), 1, "NO-SENTINEL 须停本泳道，A2 不得起跑")
        self.assertEqual(rows[0]["Status"], "NO-SENTINEL")
        self.assertEqual(rows[0]["Sentinel"], "无")
        # 只补问一次，不循环：桩每被调一次回显一行 STUB-ARGS。
        retry_text = (self.log_dir / "demo-lane-A1.retry.log").read_text(encoding="utf-8-sig")
        self.assertEqual(retry_text.count("STUB-ARGS"), 1)
        self.assertEqual((self.log_dir / "demo-lane-A1.log").read_text(encoding="utf-8-sig").count("STUB-ARGS"), 1)
        self.assertIn("SENTINEL_NONE=1", (self.log_dir / "summary.txt").read_text(encoding="utf-8-sig"))

    def test_补问挂死_超时kill_判NO_SENTINEL_不无限等(self):
        self._set_stub(_stub_two_round(first="没哨兵", retry="OPENER_DONE", hang_retry_sec=60))
        t0 = time.monotonic()
        r = self._run_batch(retry_timeout=3)
        elapsed = time.monotonic() - t0
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertLess(elapsed, 45, f"补问挂死 60s 却等了 {elapsed:.0f}s——超时没生效")
        rows = self._rows()
        self.assertEqual(rows[0]["Status"], "NO-SENTINEL")
        self.assertEqual(rows[0]["Sentinel"], "无")
        self.assertIn("timeout(3s, killed)", (self.log_dir / "demo-lane-A1.log").read_text(encoding="utf-8-sig"))

    def test_退出码非零FAIL_不补问(self):
        self._set_stub(_stub_two_round(first="崩了", retry="OPENER_DONE", exit_code=7))
        r = self._run_batch()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        rows = self._rows()
        self.assertEqual(rows[0]["Status"], "FAIL(7)")
        self.assertEqual(rows[0]["Sentinel"], "—")
        self.assertFalse((self.log_dir / "demo-lane-A1.retry.log").exists(), "进程层失败不是遵守问题，不补问")

    def test_FullAuto开关真的生效_不给即acceptEdits(self):
        # v2.2 顺手实证：原码 `-ArgumentList …, [bool]$FullAuto, …` 在参数位是字符串 "[bool]False"（非空 ⇒ 恒真），
        # 于是 -FullAuto 给不给都 --dangerously-skip-permissions；改为 `([bool]$FullAuto)` 才是布尔。
        r = self._run_batch()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        first = (self.log_dir / "demo-lane-A1.log").read_text(encoding="utf-8-sig")
        self.assertIn("--permission-mode acceptEdits", first)
        self.assertNotIn("--dangerously-skip-permissions", first)
        shutil.rmtree(self.log_dir)
        r = self._run_batch(extra=["-FullAuto"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("--dangerously-skip-permissions", (self.log_dir / "demo-lane-A1.log").read_text(encoding="utf-8-sig"))

    def test_泳道Job在仓库根跑_不继承调用方cwd(self):
        # 2026-09-10 实证：四条泳道 session 全落在 Cowork 调用方 cwd（OneDrive\文档），--resume 按 cwd 找会找不到。
        self._set_stub(_stub_two_round(first="没哨兵", retry="OPENER_DONE"))
        other_cwd = self.root / "elsewhere"
        other_cwd.mkdir()
        r = subprocess.run(
            ["pwsh", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT),
             "-Plan", str(self.plan), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir),
             "-SentinelRetryTimeoutSec", "20"],
            cwd=other_cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=self.env, timeout=300,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        repo_root = SCRIPT.parent.parent
        for name in ("demo-lane-A1.log", "demo-lane-A1.retry.log"):
            text = (self.log_dir / name).read_text(encoding="utf-8-sig")
            m = re.search(r"STUB-CWD: (.+)", text)
            self.assertIsNotNone(m, name)
            self.assertEqual(Path(m.group(1).strip()).resolve(), repo_root.resolve(),
                             f"{name}：泳道里的 claude 没在仓库根跑（首轮与补问须同一 cwd，否则 --resume 找不到会话）")

    def test_变异守卫_抽掉补问段_第一条用例必须转红(self):
        """🔴 恒真检验：把 `>>> #550 补问 begin`…`<<< #550 补问 end` 整段抽掉后跑同一场景，须回到 NO-SENTINEL。"""
        src = SCRIPT.read_text(encoding="utf-8")
        begin, end = "# >>> #550 补问 begin", "# <<< #550 补问 end"
        i, j = src.index(begin), src.index(end)
        self.assertGreater(j, i)
        mutant_dir = self.root / "mutant" / "tools"
        mutant_dir.mkdir(parents=True)
        mutant = mutant_dir / SCRIPT.name
        mutant.write_text(src[:i] + src[j:], encoding="utf-8")
        self._set_stub(_stub_two_round(first="活干完了但忘了哨兵", retry="OPENER_DONE"))
        r = self._run_batch(script=mutant)
        self.assertEqual(r.returncode, 1, "补问段抽掉后 NO-SENTINEL 没回来 ⇒ 正例是恒真的\n" + r.stdout + r.stderr)
        rows = self._rows()
        self.assertEqual(rows[0]["Status"], "NO-SENTINEL")
        self.assertFalse((self.log_dir / "demo-lane-A1.retry.log").exists())


class 历史泳道回放_桩(_Base):
    """2026-09-10 四条立行实证泳道的首轮形态逐字回放（桩）。🔴 真 session id 回放不在此（见 `#550` 行内）。"""

    def _run_lane(self, lane: str, first: str, retry: str) -> dict:
        self.stub_file.write_text(_stub_two_round(first=first, retry=retry), encoding="utf-8")
        self.plan.write_text(PLAN_TEXT.replace("泳道：demo-lane", f"泳道：{lane}"), encoding="utf-8")
        r = _run(["-Plan", str(self.plan), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir),
                  "-SentinelRetryTimeoutSec", "20"], self.root, self.env, timeout=300)
        rows = json.loads((self.log_dir / "summary.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(len(rows), 1, r.stdout + r.stderr)
        shutil.rmtree(self.log_dir)
        return rows[0]

    def test_544_反引号包哨兵_补问后OK(self):
        row = self._run_lane("544-heartbeat-batch", HISTORY_FIRST_ROUND["544-heartbeat-batch"], "OPENER_DONE")
        self.assertEqual((row["Status"], row["Sentinel"]), ("OK", "补问"))

    def test_507_529_被600s上限掐断_补问后PARTIAL(self):
        for lane in ("507-sweep-apply", "529-timeout-semantics"):
            row = self._run_lane(lane, HISTORY_FIRST_ROUND[lane], "OPENER_PARTIAL: 全量回归未跑完即被掐断")
            self.assertEqual((row["Status"], row["Sentinel"]), ("PARTIAL", "补问"), lane)

    def test_k2_本就PARTIAL_不触发补问(self):
        row = self._run_lane("k2-externalize", HISTORY_FIRST_ROUND["k2-externalize"], "OPENER_DONE")
        self.assertEqual((row["Status"], row["Sentinel"]), ("PARTIAL", "首轮"))


if __name__ == "__main__":
    unittest.main()
