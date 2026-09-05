#!/usr/bin/env python3
"""回归 2026-09-05 实撞（Cowork 业务总线自查修复，队列登记见 B-0905_C 附带批）：
`发企微.py` 的 `REPO_ROOT` 若按 `__file__` 所在 checkout 推算，会在被
`工具-泳道看护状态机.py::_load_wecom_sender` 从隔离 worktree 内加载时解到
worktree 根而非主工作区根——`.env`（`.gitignore`、只存在于主工作区，不随
worktree checkout 带过来）在 worktree 根下找不到，`load_webhook()`
`sys.exit`，调用方 `_notify_best_effort` 的 `except SystemExit` 把它吞掉、
静默降级为「仅落状态」：凡从 CC worktree 里发起的 pause「等你」企微通知
全部悄悄丢失，Shao Peishen 收不到等待答复的提醒。

修复：`REPO_ROOT` 改用 `git rev-parse --git-common-dir` 解析——逐字复用
`工具-共享文档编辑锁.py::_resolve_repo_root` 同一判据，不重写第二份。

复现手法同 `test_工具-共享文档编辑锁.py::EditLockCrossWorktreeTests`
惯例：真实 `git worktree add` 建主工作区＋一个 linked worktree。
"""
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "发企微.py"


def _load_module_from(path: Path):
    spec = importlib.util.spec_from_file_location("_test_faqiwei_reuse", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class WecomRepoRootCrossWorktreeTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.main_root = Path(self._tmpdir.name) / "main"
        self.main_root.mkdir()
        self._git("init", "-q")
        self._git("config", "user.email", "test@example.com")
        self._git("config", "user.name", "Test")
        script_dir = self.main_root / "0-学习与工具"
        script_dir.mkdir()
        (script_dir / "发企微.py").write_text(
            SCRIPT.read_text(encoding="utf-8"), encoding="utf-8"
        )
        (self.main_root / "1-转型规划").mkdir()
        (self.main_root / ".gitignore").write_text(".env\n", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "init")
        # .env 只落主工作区——真实生产里它被 .gitignore，从不随 worktree checkout 带走。
        (self.main_root / ".env").write_text(
            'WECOM_WEBHOOK_URL="https://example.invalid/webhook"\n', encoding="utf-8"
        )
        self.linked_root = Path(self._tmpdir.name) / "linked"
        self._git("worktree", "add", "-q", str(self.linked_root), "-b", "linked-branch")

    def tearDown(self):
        self._tmpdir.cleanup()
        sys.modules.pop("_test_faqiwei_reuse", None)

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args], cwd=self.main_root, check=True,
            capture_output=True, text=True,
        )

    def test_repo_root_resolves_to_main_workspace_from_linked_worktree(self):
        script = self.linked_root / "0-学习与工具" / "发企微.py"
        self.assertTrue(script.exists(), "linked worktree 应有自己的 checkout 副本")
        module = _load_module_from(script)
        self.assertTrue(
            (module.REPO_ROOT / "0-学习与工具").samefile(self.main_root / "0-学习与工具"),
            f"REPO_ROOT 应恒指主工作区，实际={module.REPO_ROOT}",
        )

    def test_load_webhook_finds_env_from_linked_worktree(self):
        # 修复前：linked worktree 根下没有 .env，load_webhook() 会 sys.exit；
        # 修复后应能读到主工作区的 .env——这正是本次事故的直接复现。
        self.assertFalse((self.linked_root / ".env").exists())
        script = self.linked_root / "0-学习与工具" / "发企微.py"
        module = _load_module_from(script)
        url = module.load_webhook()
        self.assertEqual(url, "https://example.invalid/webhook")

    def test_repo_root_falls_back_when_not_a_git_repo(self):
        # 非仓库环境（git 命令失败）时退回按脚本自身路径推算，保底不崩。
        outside = Path(self._tmpdir.name) / "not-a-repo" / "0-学习与工具"
        outside.mkdir(parents=True)
        script = outside / "发企微.py"
        script.write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
        module = _load_module_from(script)
        self.assertEqual(module.REPO_ROOT, outside.parent)


if __name__ == "__main__":
    unittest.main()
