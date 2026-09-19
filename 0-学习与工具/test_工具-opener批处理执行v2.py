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

import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest
import uuid
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().with_name("工具-opener批处理执行v2.ps1")
GEN_SCRIPT = Path(__file__).resolve().with_name("工具-opener生成.py")
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def _load_gen_module():
    """按 `test_工具-opener生成.py::_load_module` 同法白盒加载生成器——本文件只借它拼一个
    带「模型：」字段的真实【设置】行做互测夹具，不测生成器自身（那是它自己的测试文件的事）。"""
    spec = importlib.util.spec_from_file_location("_opener_gen_for_v2_mutual_test", GEN_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

pytestmark = pytest.mark.skipif(
    shutil.which("pwsh") is None or os.name != "nt", reason="需要 Windows ＋ PowerShell 7（pwsh）"
)

#: 最小 plan：一个泳道一条 opener（`### A1` ＋ 粘贴端／泳道行 ＋ 围栏块）。
#: 🔴 队列 #600 合入前补缺：通用夹具一律「worktree：☐」——#600 起脚本会对【设置】声明 ☑ 的 opener
#: 真跑 `git worktree add`，而 `$RepoRoot` 取脚本物理位置＝真实仓库；通用用例（session/哨兵/模型）
#: 与 worktree 无关，声明 ☑ 只会往真实仓库塞 `demo` worktree 与 `claude/op1231a-demo` 分支（09-17 实撞）。
#: 需要 ☑ 的两类（残留回收、#600 四场景）改用 `PLAN_TEXT_WT` 并以随机名＋tearDown 自清。
PLAN_TEXT_WT = "\n".join([
    "# 波次计划（单测夹具）", "",
    "### A1 · 示例泳道", "",
    "粘贴端：CC ｜ 泳道：demo-lane", "",
    "```",
    "[OP-1231-A]【CC】示例任务",
    "【设置】执行环境：CC ｜ 分支：master（从 master 起 `claude/op1231a-demo`） ｜ worktree：☑（demo，新 worktree，收工自删） ｜ 工作区：无 ｜ session：新开 ｜ 派出线：环境总线",
    "读 ① 队列 §一 `#549` → ② `CLAUDE.md` 恢复上下文，按该行执行。本件为 A 类，直接开工。",
    "```", "",
])
PLAN_TEXT = PLAN_TEXT_WT.replace("master（从 master 起 `claude/op1231a-demo`）", "master").replace(
    "worktree：☑（demo，新 worktree，收工自删）", "worktree：☐")

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

    def test_非Detach也写launcher_json_起跑时刻正本(self):
        """`#571`⑶：收工探针取起跑时刻以 `launcher.json.started_at_utc` 为正本；此前只有 `-Detach`
        写它，`-LogDir` 显式指定的语义名批没有正本。非 Detach 跑也必须写。"""
        r = _run(["-Plan", str(self.plan), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir)],
                 self.root, self.env, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        launcher = json.loads((self.log_dir / "launcher.json").read_text(encoding="utf-8-sig"))
        self.assertIn("pid", launcher)
        self.assertRegex(launcher["started_at_utc"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertEqual(Path(launcher["log_dir"]), self.log_dir)


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
        # 队列 #600：脚本以自身物理位置的上一级为仓库根并对其跑 git（收工核验快照），变异副本所在目录须是 git 仓库。
        (self.root / "mutant").mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "-q", str(self.root / "mutant")], check=True, capture_output=True)
        mutant_dir.mkdir(parents=True)
        mutant = mutant_dir / SCRIPT.name
        mutant.write_text(src[:i] + src[j:], encoding="utf-8")
        self._set_stub(_stub_two_round(first="活干完了但忘了哨兵", retry="OPENER_DONE"))
        r = self._run_batch(script=mutant)
        self.assertEqual(r.returncode, 1, "补问段抽掉后 NO-SENTINEL 没回来 ⇒ 正例是恒真的\n" + r.stdout + r.stderr)
        rows = self._rows()
        self.assertEqual(rows[0]["Status"], "NO-SENTINEL")
        self.assertFalse((self.log_dir / "demo-lane-A1.retry.log").exists())


class Model路由默认sonnet(_Base):
    """队列 §一 `#581` ⑴：`-Model` 默认由 `''` 改为 `'sonnet'`；显式 `-Model opus` 照常生效；
    首轮与补问两处（`$claudeArgs`/`$retryArgs`）同源自同一个 `$Model` 形参，一次断言两处。"""

    def test_不给Model_首轮默认传sonnet(self):
        r = _run(["-Plan", str(self.plan), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir)],
                  self.root, self.env, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        first = (self.log_dir / "demo-lane-A1.log").read_text(encoding="utf-8-sig")
        self.assertIn("--model sonnet", first)

    def test_显式Model_opus_覆盖默认(self):
        r = _run(["-Plan", str(self.plan), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir),
                   "-Model", "opus"], self.root, self.env, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        first = (self.log_dir / "demo-lane-A1.log").read_text(encoding="utf-8-sig")
        self.assertIn("--model opus", first)
        self.assertNotIn("--model sonnet", first)

    def test_NO_SENTINEL补问轮_同样带model_sonnet(self):
        self.stub_file.write_text(
            _stub_two_round(first="活干完了但忘了哨兵", retry="OPENER_DONE"), encoding="utf-8")
        r = _run(["-Plan", str(self.plan), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir),
                   "-SentinelRetryTimeoutSec", "20"], self.root, self.env, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        retry_log = self.log_dir / "demo-lane-A1.retry.log"
        self.assertIn("--model sonnet", retry_log.read_text(encoding="utf-8-sig"),
                      "补问轮与首轮同源自同一个 $Model 形参，不得漏传")


class Opener级模型字段(_Base):
    """队列 §一 `#581` 合入前补缺 ⑴⑵⑶：opener【设置】行可带「模型：sonnet｜opus」——
    缺省继承批级 `-Model`；显式值覆盖批级默认；非法值判 `FAIL(model)` 且不起 claude
    （不消耗一个 session、日志点名非法值）。首轮与 NO-SENTINEL 补问同源自同一个 `$op.Model`。"""

    _SETTINGS_LINE = (
        "【设置】执行环境：CC ｜ 分支：master ｜ "
        "worktree：☐ ｜ 工作区：无 ｜ session：新开 ｜ 派出线：环境总线"
    )

    def _write_plan_with_model_field(self, suffix: str):
        text = PLAN_TEXT.replace(self._SETTINGS_LINE, self._SETTINGS_LINE + suffix)
        self.assertNotEqual(text, PLAN_TEXT, "夹具替换未命中【设置】行，测试基线已漂移")
        self.plan.write_text(text, encoding="utf-8")

    def test_缺省继承批级(self):
        # opener 本身不带「模型」字段，批级传 -Model opus（非默认 sonnet）⇒ 该条须继承 opus。
        r = _run(["-Plan", str(self.plan), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir),
                  "-Model", "opus"], self.root, self.env, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        first = (self.log_dir / "demo-lane-A1.log").read_text(encoding="utf-8-sig")
        self.assertIn("model=opus", first)
        self.assertIn("--model opus", first)

    def test_显式opus覆盖批级默认(self):
        self._write_plan_with_model_field(" ｜ 模型：opus")
        # 批级不传 -Model ⇒ 批级默认 sonnet；本条 opener 显式 opus 须覆盖之。
        r = _run(["-Plan", str(self.plan), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir)],
                  self.root, self.env, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        first = (self.log_dir / "demo-lane-A1.log").read_text(encoding="utf-8-sig")
        self.assertIn("model=opus", first)
        self.assertIn("--model opus", first)
        self.assertNotIn("--model sonnet", first)

    def test_非法值判FAIL不起claude(self):
        self._write_plan_with_model_field(" ｜ 模型：haiku")
        r = _run(["-Plan", str(self.plan), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir)],
                  self.root, self.env, timeout=300)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        rows = json.loads((self.log_dir / "summary.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Status"], "FAIL(model)")
        log_text = (self.log_dir / "demo-lane-A1.log").read_text(encoding="utf-8-sig")
        self.assertIn("haiku", log_text, "日志须点名非法取值，不能只说「模型不对」")
        self.assertNotIn("STUB-ARGS", log_text, "非法模型值须在起 claude 之前拦下，不得真的调用一次")
        self.assertEqual(rows[0]["Session"], "", "未起 claude ⇒ 不应生成 session id")


class 生成器与v2解析口径互测(_Base):
    """队列 §一 `#581` 合入前补缺 ⑷：`工具-opener生成.py::_settings_line` 落笔的「模型：」字段形态，
    与本脚本的解析正则须是同一口径——任一方悄悄改了分隔符/字段名，这条互测应转红（其余单测各自
    只测半边，看不见两边漂移）。用生成器真实产出（非手写模拟）喂给 v2 解析＋真跑一次桩 claude。"""

    def test_生成器产出的模型字段被v2按同一口径解析(self):
        gen = _load_gen_module()
        with tempfile.TemporaryDirectory() as gen_tmp:
            # 隔离撞号扫描与取号台账（同 `test_工具-opener生成.py::setUpModule` 手法），
            # 不因本机当日真实占用编号或写脏 reports/op-id-claims.jsonl 而失真/致污染。
            gen.REPO_ROOT = Path(gen_tmp)
            gen.CLAIMS_FILE = Path(gen_tmp) / "op-id-claims.jsonl"
            block = gen.generate_opener(
                op_id="OP-1231-M", env="CC", short_name="互测任务", branch="mutual-slug",
                worktree="☐", workspace="无（纯库内）",
                session="新开", line="环境总线", input_pointer="示例派单件.md",
                task_class="A", do_items=["第一步"], dont_items=["不做的事"], model="opus",
            )
        self.assertIn("｜ 模型：opus", block, "生成器自身产出形态已变——互测夹具先于 v2 那半失真")
        plan = "\n".join([
            "# 波次计划（生成器互测夹具）", "",
            "### A1 · 互测", "", "粘贴端：CC ｜ 泳道：demo-lane", "",
            block, "",
        ])
        self.plan.write_text(plan, encoding="utf-8")
        r = _run(["-Plan", str(self.plan), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir)],
                  self.root, self.env, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        first = (self.log_dir / "demo-lane-A1.log").read_text(encoding="utf-8-sig")
        self.assertIn("model=opus", first)
        self.assertIn("--model opus", first)


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


class Worktree残留回收_v2_4(_Base):
    """队列 `#584` ⑶b：每条 opener 处理完后，若它自建的 worktree（【设置】行「worktree：☑
    （<名>，...」）还在——多半是子会话崩溃/超时/漏做「收工自删」——把其 `reports/` 残留
    捞回主工作区 `reports/_from-worktree/<泳道>/`，不丢产出。桩 claude 什么也不改，
    worktree 目录本身由本测试预先摆好，模拟「子会话没来得及/没删掉」的现场。

    🔴 本脚本 `$RepoRoot = Split-Path -Parent $PSScriptRoot` 后 `Set-Location $RepoRoot`——
    走的是脚本**物理落盘位置**的仓库根，不认 `-Plan`/`cwd` 指到的临时夹具目录（`Resume接管`
    等既有用例靠 `-LogDir` 传绝对路径绕开这一点）。本类的回收目标是仓库相对路径
    （`.claude/worktrees/<名>`、`reports/_from-worktree/<泳道>`），天然只能落在这个真实仓库根，
    故直接在其下用**随机名**摆放/清理夹具，不占用真实泳道名、跑完必删。"""

    def setUp(self):
        super().setUp()
        self.real_repo_root = SCRIPT.resolve().parent.parent
        token = uuid.uuid4().hex[:8]
        self.wt_name = f"test-wt-{token}"
        self.branch_name = f"claude/optest584-{token}"
        self.lane_name = f"test-lane-{token}"
        self.wt_dir = self.real_repo_root / ".claude" / "worktrees" / self.wt_name
        self.dest_dir = self.real_repo_root / "reports" / "_from-worktree" / self.lane_name

    def tearDown(self):
        # 队列 #600 ⑴：v2.ps1 现在会真的 `git worktree add` 建隔离 worktree——夹具里没
        # 预先建目录的场景（`test_worktree已被自己删干净时无残留可回收也不报错`）会让脚本
        # 对**真实仓库**跑一次真 `git worktree add -b claude/op1231a-demo`（分支名取自
        # `PLAN_TEXT`「分支：」字段，未随 `self.wt_name` 变化）——先 rmtree 目录，
        # 再 `worktree prune` 清掉 `.git/worktrees/<名>` 残留元数据，最后删分支，
        # 不留手为真实仓库添的 worktree/branch 垃圾。
        real_repo = self.real_repo_root
        subprocess.run(["git", "-C", str(real_repo), "worktree", "remove", "--force", str(self.wt_dir)],
                        capture_output=True)
        shutil.rmtree(self.wt_dir, ignore_errors=True)
        subprocess.run(["git", "-C", str(real_repo), "worktree", "prune"], capture_output=True)
        subprocess.run(["git", "-C", str(real_repo), "branch", "-D", self.branch_name],
                        capture_output=True)
        shutil.rmtree(self.dest_dir, ignore_errors=True)
        super().tearDown()

    def _write_plan(self, worktree_field: str = "☑（{wt}，新 worktree，收工自删）") -> None:
        text = (
            PLAN_TEXT_WT
            .replace("泳道：demo-lane", f"泳道：{self.lane_name}")
            .replace("claude/op1231a-demo", self.branch_name)
            .replace("worktree：☑（demo，新 worktree，收工自删）",
                      "worktree：" + worktree_field.format(wt=self.wt_name))
        )
        self.plan.write_text(text, encoding="utf-8")

    def test_worktree残留reports被捞回主工作区(self):
        self._write_plan()
        wt_reports = self.wt_dir / "reports"
        (wt_reports / "sub").mkdir(parents=True)
        (wt_reports / "top.log").write_text("残留一", encoding="utf-8")
        (wt_reports / "sub" / "nested.json").write_text('{"k":1}', encoding="utf-8")

        r = _run(["-Plan", str(self.plan), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir)],
                 self.root, self.env, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

        self.assertEqual((self.dest_dir / "top.log").read_text(encoding="utf-8"), "残留一")
        self.assertEqual((self.dest_dir / "sub" / "nested.json").read_text(encoding="utf-8"), '{"k":1}')
        # 源目录原样保留（本步骤是「捞一份」不是「搬走」，万一回收逻辑本身有 bug，原件还在能再救一次）。
        self.assertTrue((wt_reports / "top.log").is_file())
        log = (self.log_dir / f"{self.lane_name}-A1.log").read_text(encoding="utf-8-sig")
        self.assertIn("worktree 残留回收", log)
        self.assertIn("2 个文件", log)

    def test_worktree已被自己删干净时无残留可回收也不报错(self):
        self._write_plan()  # 不预先创建 `.claude/worktrees/<名>/` ⇒ 模拟子会话已按纪律删除干净。
        r = _run(["-Plan", str(self.plan), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir)],
                 self.root, self.env, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(self.dest_dir.exists())
        rows = json.loads((self.log_dir / "summary.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(rows[0]["Status"], "OK")

    def test_worktree字段是空框时不触发回收(self):
        # 队列 #549 夹具里第二条 opener 本就是「worktree：☐」（不用 worktree）——同一路径上
        # 不该硬解出一个名字来瞎扫。
        self._write_plan(worktree_field="☐")
        (self.wt_dir / "reports").mkdir(parents=True)
        (self.wt_dir / "reports" / "top.log").write_text("不该被扫到", encoding="utf-8")
        r = _run(["-Plan", str(self.plan), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir)],
                 self.root, self.env, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(self.dest_dir.exists())


class 脚本建隔离worktree四场景_v2_600(_Base):
    """队列 `#600` ⑴⑵⑷ 四场景：脚本层强制建 worktree（成功／建失败／声明缺名）＋第三道闸
    （收工核验主仓泄漏）。与 `Worktree残留回收_v2_4` 同法——`$RepoRoot` 走脚本物理落盘位置，
    只能在真实仓库根下用随机名摆夹具、跑完必删（见该类 docstring）。

    实测先确认过前提：`git worktree add` 建出的目录不会被主仓 `git status --porcelain`
    判成未跟踪内容（git 认得链接 worktree），故第三道闸不会把「脚本自己建的 worktree」
    误判成泄漏——本类第 1/4 条用例即验证这一点没有回归。
    """

    def setUp(self):
        super().setUp()
        self.real_repo_root = SCRIPT.resolve().parent.parent
        token = uuid.uuid4().hex[:8]
        self.wt_name = f"test-wt600-{token}"
        self.lane_name = f"test-lane600-{token}"
        self.branch_name = f"claude/optest600-{token}"
        self.wt_dir = self.real_repo_root / ".claude" / "worktrees" / self.wt_name
        self.decoy_dir = self.real_repo_root / ".claude" / "worktrees" / f"decoy600-{token}"
        self.leak_file = self.real_repo_root / f"_test-leak-600-{token}.md"

    def tearDown(self):
        real_repo = self.real_repo_root
        subprocess.run(["git", "-C", str(real_repo), "worktree", "remove", "--force", str(self.wt_dir)],
                        capture_output=True)
        subprocess.run(["git", "-C", str(real_repo), "worktree", "remove", "--force", str(self.decoy_dir)],
                        capture_output=True)
        shutil.rmtree(self.wt_dir, ignore_errors=True)
        shutil.rmtree(self.decoy_dir, ignore_errors=True)
        subprocess.run(["git", "-C", str(real_repo), "worktree", "prune"], capture_output=True)
        subprocess.run(["git", "-C", str(real_repo), "branch", "-D", self.branch_name], capture_output=True)
        if self.leak_file.exists():
            self.leak_file.unlink()
        super().tearDown()

    def _write_plan(self, worktree_field: str = "☑（{wt}，新 worktree，收工自删）") -> None:
        text = (
            PLAN_TEXT_WT
            .replace("泳道：demo-lane", f"泳道：{self.lane_name}")
            .replace("claude/op1231a-demo", self.branch_name)
            .replace("worktree：☑（demo，新 worktree，收工自删）",
                      "worktree：" + worktree_field.format(wt=self.wt_name))
        )
        self.plan.write_text(text, encoding="utf-8")

    def test_正常worktree由脚本建成并注入env标记(self):
        self._write_plan()
        self.stub_file.write_text(
            "@echo off\r\n"
            "echo STUB-LANE-WT: %ZHUOPIN_LANE_WORKTREE%\r\n"
            "echo STUB-MAIN-REPO: %ZHUOPIN_MAIN_REPO%\r\n"
            "echo STUB-CWD: %CD%\r\n"
            "echo OPENER_DONE\r\n"
            "exit /b 0\r\n",
            encoding="utf-8",
        )
        r = _run(["-Plan", str(self.plan), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir)],
                 self.root, self.env, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rows = json.loads((self.log_dir / "summary.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(rows[0]["Status"], "OK")
        # worktree 真被脚本建出来（不是夹具预置），且第三道闸没把它自己误判成泄漏。
        self.assertTrue(self.wt_dir.is_dir())
        wt_list = subprocess.run(["git", "-C", str(self.real_repo_root), "worktree", "list"],
                                  capture_output=True, text=True, encoding="utf-8").stdout
        self.assertIn(str(self.wt_dir).replace("\\", "/"), wt_list)  # git 输出恒用正斜杠
        log = (self.log_dir / f"{self.lane_name}-A1.log").read_text(encoding="utf-8-sig")
        self.assertIn("worktree 已建", log)
        self.assertIn("STUB-LANE-WT: " + str(self.wt_dir), log)
        self.assertIn("STUB-MAIN-REPO: " + str(self.real_repo_root), log)
        # 合入前补缺：worktree 提示不得挤掉「日志首行＝session」契约（#549 续跑接管靠它）。
        self.assertRegex(log.splitlines()[0], r"session=" + UUID_RE.pattern)
        # 声明 worktree 时 claude 在该 worktree 里跑（首轮与补问同一 cwd 的前提）。
        m = re.search(r"STUB-CWD: (.+)", log)
        self.assertIsNotNone(m)
        self.assertEqual(Path(m.group(1).strip()).resolve(), self.wt_dir.resolve())
        self.assertFalse((self.log_dir / f"{self.lane_name}-A1-main-leak.patch").exists())

    def test_相对LogDir在worktree泳道下仍落到调用方目录(self):
        # 实测补缺：相对 -LogDir 曾随泳道 Push-Location 漂进 worktree，泳道起 claude 前即崩。
        self._write_plan()
        r = _run(["-Plan", str(self.plan), "-Yes", "-StaggerSec", "0", "-LogDir", "rel-log"],
                 self.root, self.env, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rel = self.root / "rel-log"
        rows = json.loads((rel / "summary.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(rows[0]["Status"], "OK")
        self.assertRegex((rel / f"{self.lane_name}-A1.log").read_text(encoding="utf-8-sig").splitlines()[0],
                         r"session=" + UUID_RE.pattern)

    def test_worktree建失败时判FAIL不起claude(self):
        # 让目标分支先在别处（decoy worktree）被检出——脚本走「分支已存在 ⇒ 不带 -b 的
        # worktree add」分支，git 会因「分支已在别的 worktree 检出」报错（fatal，exit 128），
        # 产出确定性可复现的建失败场景（实测见 OP-0916-ZZ 手工探测，`already used by worktree`）。
        subprocess.run(
            ["git", "-C", str(self.real_repo_root), "worktree", "add", "-b", self.branch_name,
             str(self.decoy_dir), "master"],
            check=True, capture_output=True,
        )
        self._write_plan()
        r = _run(["-Plan", str(self.plan), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir)],
                 self.root, self.env, timeout=300)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)  # 批内有 FAIL ⇒ 批次退出码 1
        rows = json.loads((self.log_dir / "summary.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(rows[0]["Status"], "FAIL(worktree-build)")
        log = (self.log_dir / f"{self.lane_name}-A1.log").read_text(encoding="utf-8-sig")
        self.assertIn("git worktree add 失败", log)
        self.assertNotIn("STUB-ARGS", log)  # claude 确未被起，没消耗一次真实调用
        self.assertFalse(self.wt_dir.exists())

    def test_声明worktree却解析不出名字时判FAIL(self):
        self._write_plan(worktree_field="☑")
        r = _run(["-Plan", str(self.plan), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir)],
                 self.root, self.env, timeout=300)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        rows = json.loads((self.log_dir / "summary.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(rows[0]["Status"], "FAIL(worktree-name)")
        log = (self.log_dir / f"{self.lane_name}-A1.log").read_text(encoding="utf-8-sig")
        self.assertIn("解析不出名字", log)
        self.assertFalse(self.wt_dir.exists())

    def test_主仓误写触发第三道闸判FAIL并存补丁不自动撤回(self):
        # 模拟 #596/#599 那类泄漏：claude 子进程（本测试用桩顶替）绕过前两道闸，直接用
        # 绝对路径往主工作区写一个白名单外的新文件——第三道闸须在收工核验时逮住它。
        # 队列 #611 归属判定合入后，光凭这一步不够了：还须证明「该泳道 worktree 实际
        # 触碰过」这个路径，故本例让泳道自己的分支先提交一份同名文件（模拟它确实在
        # 做这份工作、只是又用绝对路径多写了一份到主仓），归属判定才会把这份泄漏计入
        # 本泳道账——防判据过宽的另一半场景见下一条
        # `test_看护者同时段写入主仓不判该泳道FAIL`。
        self._write_plan()
        leak_path = self.leak_file
        leak_name = leak_path.name
        self.stub_file.write_text(
            "@echo off\r\n"
            f'echo lane content> "{leak_name}"\r\n'
            f'git -c user.name=test -c user.email=test@example.com add "{leak_name}"\r\n'
            f'git -c user.name=test -c user.email=test@example.com commit -m "lane commit" --quiet\r\n'
            f'echo leaked content> "{leak_path}"\r\n'
            "echo OPENER_DONE\r\n"
            "exit /b 0\r\n",
            encoding="utf-8",
        )
        r = _run(["-Plan", str(self.plan), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir)],
                 self.root, self.env, timeout=300)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        rows = json.loads((self.log_dir / "summary.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(rows[0]["Status"], "FAIL(main-leak)")
        log = (self.log_dir / f"{self.lane_name}-A1.log").read_text(encoding="utf-8-sig")
        self.assertIn("收工核验", log)
        self.assertIn("🔴🔴🔴", log)
        patch = self.log_dir / f"{self.lane_name}-A1-main-leak.patch"
        self.assertTrue(patch.is_file())
        patch_text = patch.read_text(encoding="utf-8-sig")
        self.assertIn(leak_path.name, patch_text)
        # 不自动撤回：泄漏文件应仍原样留在主工作区，供人工核实后再决定去留。
        self.assertTrue(leak_path.exists())

    def test_看护者同时段写入主仓不判该泳道FAIL(self):
        # 队列 #611 归属判定（`1a`）核心场景复现：泳道 worktree 干干净净跑完（没提交、
        # 没碰这个文件），主工作区却在它运行期间冒出一个白名单外的新文件——这是看护者
        # （或任何其它并行进程）同时段直接写主仓，与本泳道无关，不该记它的账。
        # 本例用旧版桩（纯 `echo` 绝对路径、不碰 worktree）来站在「泄漏候选存在但
        # 与本泳道 worktree 无关联」这一侧，断言判 OK、不产出 main-leak 补丁。
        self._write_plan()
        leak_path = self.leak_file
        self.stub_file.write_text(
            "@echo off\r\n"
            f'echo bystander content> "{leak_path}"\r\n'
            "echo OPENER_DONE\r\n"
            "exit /b 0\r\n",
            encoding="utf-8",
        )
        r = _run(["-Plan", str(self.plan), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir)],
                 self.root, self.env, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rows = json.loads((self.log_dir / "summary.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(rows[0]["Status"], "OK")
        self.assertFalse((self.log_dir / f"{self.lane_name}-A1-main-leak.patch").exists())
        # 旁观者文件本身不受第三道闸处置（既不属于泳道账，也不自动清理），原样留存。
        self.assertTrue(leak_path.exists())

    def test_泳道回写队列三类白名单后不判FAIL(self):
        # 队列 #611 ⑵ 竞态复现：泳道收工按协议〇回写队列（`ff-patrol-<date>.jsonl` 每次
        # ff 必写／两份队列物理文件／`队列行日志/#<N>.md` 这个 K2 外置件），但 sweep 尚未
        # 及时提交——此时主工作区必然带着这三类改动。方案 D 之前，第三道闸会把这份「合规
        # 回写」误判成泄漏；本例三类一次叠加造出同一竞态，断言不再判 FAIL。
        self._write_plan(worktree_field="☐")
        root_dir = self.real_repo_root / "1-转型规划" / "0-全景路线图"
        ff_patrol = root_dir / "合入登记" / "ff-patrol-20261231.jsonl"
        row_log = root_dir / "队列行日志" / "#999999.md"
        queue_md = root_dir / "跨桌任务队列-业务场景.md"
        original_queue_text = queue_md.read_text(encoding="utf-8")

        def _cleanup():
            ff_patrol.unlink(missing_ok=True)
            row_log.unlink(missing_ok=True)
            queue_md.write_text(original_queue_text, encoding="utf-8")

        self.addCleanup(_cleanup)
        self.stub_file.write_text(
            "@echo off\r\n"
            f'echo {{"op":"test"}}> "{ff_patrol}"\r\n'
            f'echo # 泳道回写测试> "{row_log}"\r\n'
            f'echo ^<!-- 泳道回写测试，tearDown 还原 --^>>> "{queue_md}"\r\n'
            "echo OPENER_DONE\r\n"
            "exit /b 0\r\n",
            encoding="utf-8",
        )
        r = _run(["-Plan", str(self.plan), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir)],
                 self.root, self.env, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rows = json.loads((self.log_dir / "summary.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(rows[0]["Status"], "OK")
        self.assertFalse((self.log_dir / f"{self.lane_name}-A1-main-leak.patch").exists())


if __name__ == "__main__":
    unittest.main()
