"""`工具-执行体对齐重启.ps1` 第 2 关「2b 进程新鲜度」单测（队列 §一 #570，OP-0913-G）。

被测的是一个断口：落后数为 0 时，脚本原来直接报「已对齐，无需处置」退出 0，
**完全不看常驻进程起于何时**。2026-09-12 实证：进程比代码老 21 小时，`-DryRun`
照报绿；同日另一例晚 50 秒照报绿。本文件把那两种场景各造一遍，断言脚本不再
在断口上报绿。

夹具做法（不依赖任何真实计划任务、不碰 `wecom-service-home`）：
  · 临时 git 仓库，主工作区 = master，`.claude/worktrees/<name>` 用
    `git worktree add --detach` 注册（第 1 关只认注册项 ＋ `.git` 条目）；
  · 「常驻进程」＝一个 `powershell Start-Sleep`，命令行里带上该 worktree 路径
    ——脚本找进程链的判据就是「命令行含 `<worktree>/`」，与真执行体同一判据；
  · 新鲜／过期由「进程起于 ff 之前还是之后」决定，中间 `sleep` ≥2 s 是因为
    git 提交时刻与 reflog 时刻只到秒。

🔴 只在 Windows ＋ `powershell.exe`（5.1）下跑——sweep 侧 `_restart_carrier`
就是用 `powershell.exe` 调它，单测用同一解释器。没有即整文件跳过。
🔴 断言只看退出码与 ASCII 标记（`2b`／pid），不比对中文回显——5.1 的 `-File`
输出走控制台代码页，跨机器不稳定。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "工具-执行体对齐重启.ps1"
PS = shutil.which("powershell.exe") or shutil.which("powershell")
HAS_PS = PS is not None and os.name == "nt"

CARRIER = "carrier-under-test"


def _git(args: list[str], cwd: Path) -> str:
    r = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=cwd,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} 失败：{r.stdout}{r.stderr}")
    return r.stdout


def _commit(root: Path, msg: str) -> None:
    (root / "README.md").write_text(f"{msg}\n{time.time()}\n", encoding="utf-8")
    _git(["add", "-A"], root)
    _git(["commit", "-q", "-m", msg], root)


@pytest.mark.skipif(not HAS_PS, reason="需要 Windows ＋ powershell.exe（5.1）")
class ProcessFreshnessTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        # realpath：脚本内部 Resolve-Path 得到的是长路径，进程命令行里的路径必须与之
        # 逐字符一致（大小写不敏感、分隔符已归一），否则找不到「常驻进程」。
        self.root = Path(os.path.realpath(self._tmp.name))
        _git(["init", "-q", "-b", "master"], self.root)
        _git(["config", "user.email", "test@example.com"], self.root)
        _git(["config", "user.name", "Test"], self.root)
        _commit(self.root, "init")
        self.wt = self.root / ".claude" / "worktrees" / CARRIER
        self.wt.parent.mkdir(parents=True)
        _git(["worktree", "add", "--detach", "-q", str(self.wt), "master"], self.root)
        self.procs: list[subprocess.Popen] = []

    def tearDown(self):
        for p in self.procs:
            try:
                p.kill()
            except OSError:
                pass
        for p in self.procs:
            try:
                p.wait(timeout=10)
            except Exception:
                pass
        try:
            _git(["worktree", "remove", "--force", str(self.wt)], self.root)
        except AssertionError:
            pass
        self._tmp.cleanup()

    # ---- helpers ----
    def _spawn_carrier(self) -> subprocess.Popen:
        """起一个命令行含 `<worktree>/` 的进程，充当常驻执行体。"""
        marker = str(self.wt).replace("\\", "/") + "/"
        p = subprocess.Popen(
            [PS, "-NoProfile", "-NonInteractive", "-Command",
             f"Start-Sleep -Seconds 600 # {marker}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.procs.append(p)
        time.sleep(1.5)  # 让 CIM 能看到它，并与下一步的 git 时刻拉开 ≥1 s
        return p

    def _ff_worktree(self) -> None:
        _git(["merge", "--ff-only", "-q", "master"], self.wt)

    def _run(self, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [PS, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", str(SCRIPT), "-WorktreeName", CARRIER, "-RepoRoot", str(self.root), *extra],
            cwd=self.root, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=300,
        )

    def _alive(self, p: subprocess.Popen) -> bool:
        return p.poll() is None

    # ---- cases ----
    def test_落后0且进程晚于代码_报新鲜_退出0(self):
        _commit(self.root, "c1")
        self._ff_worktree()
        time.sleep(1.5)
        p = self._spawn_carrier()
        r = self._run("-DryRun")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("2b", r.stdout)
        self.assertIn(f"pid={p.pid}", r.stdout)
        self.assertTrue(self._alive(p))

    def test_落后0但进程早于代码_DryRun_退出18不报绿(self):
        p = self._spawn_carrier()
        time.sleep(1.5)
        _commit(self.root, "c1")          # 代码在进程之后落库
        self._ff_worktree()
        r = self._run("-DryRun")
        self.assertEqual(r.returncode, 18, r.stdout + r.stderr)
        self.assertIn("2b", r.stdout)
        self.assertIn(f"pid={p.pid}", r.stdout)
        self.assertTrue(self._alive(p), "干跑不得动进程")

    def test_过期_实跑_开关OFF_只告警退出18_不动进程(self):
        p = self._spawn_carrier()
        time.sleep(1.5)
        _commit(self.root, "c1")
        self._ff_worktree()
        # 三种「OFF」：无 .env／键缺失／值不认识——各跑一次
        for env_text in (None, "OTHER=1\n", "CARRIER_AUTO_RESTART_ENABLED=maybe\n"):
            env_path = self.root / ".env"
            if env_text is None:
                if env_path.exists():
                    env_path.unlink()
            else:
                env_path.write_text(env_text, encoding="utf-8")
            r = self._run()
            self.assertEqual(r.returncode, 18, f"{env_text!r}\n{r.stdout}{r.stderr}")
            self.assertIn("-RestartOnly", r.stdout, "只告警时必须打印处置命令")
            self.assertTrue(self._alive(p), f"开关 OFF 不得杀进程（{env_text!r}）")

    def test_过期_实跑_开关ON_走重启路径(self):
        """开关 ON ⇒ 进入第 4 关停服（本夹具的「常驻进程」会被杀掉），随后因为
        没有任何计划任务指向本 worktree，第 6 关按既有语义退出 17（无可重启的
        常驻任务）。断言的是**路径**：进程被停 ＋ 退出码 17，而不是 18／0。"""
        p = self._spawn_carrier()
        time.sleep(1.5)
        _commit(self.root, "c1")
        self._ff_worktree()
        (self.root / ".env").write_text("CARRIER_AUTO_RESTART_ENABLED=true\n", encoding="utf-8")
        r = self._run()
        self.assertEqual(r.returncode, 17, r.stdout + r.stderr)
        self.assertFalse(self._alive(p), "开关 ON 应已走停服关")

    def test_落后0且无进程_退出0并明写无在跑进程(self):
        _commit(self.root, "c1")
        self._ff_worktree()
        r = self._run("-DryRun")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("2b", r.stdout)

    def test_进程起于提交之后ff之前_按reflog时刻仍判过期(self):
        """提交时刻只是下界：进程若起于「commit 之后、ff 之前」，只比提交时刻会
        误判新鲜。脚本取 max(提交时刻, reflog 移动时刻) 才抓得住这一档。"""
        _commit(self.root, "c1")          # T0 提交（master 前进，worktree 未 ff）
        time.sleep(1.5)
        p = self._spawn_carrier()         # T1 进程起，晚于提交
        time.sleep(1.5)
        self._ff_worktree()               # T2 ff，reflog 时刻晚于进程
        r = self._run("-DryRun")
        self.assertEqual(r.returncode, 18, r.stdout + r.stderr)
        self.assertIn(f"pid={p.pid}", r.stdout)

    def test_落后大于0_路径不变_干跑退出0(self):
        """回归：落后 >0 时不进 2b，干跑仍退出 0（既有语义不动）。"""
        self._spawn_carrier()
        _commit(self.root, "c1")          # master 前进，worktree 不 ff ⇒ 落后 1
        r = self._run("-DryRun")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("2b", r.stdout)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
