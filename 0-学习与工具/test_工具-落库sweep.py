"""工具-落库sweep.py 单测（队列 #68③，五条硬要求逐条覆盖）。

黑盒为主：每个用例起一对临时 git 仓库（本地 bare "origin" + 工作区），
仿真真实项目布局的最小子集（§二表格 + 编辑锁脚本 + 台账脚本桩），跑
CLI（`--repo-root` 覆盖生产路径断言）后核对 origin 侧的提交历史与工作区
队列文件内容——不触碰真实项目仓库。

覆盖点对应五条硬要求：
- test_happy_path_commits_atomically_with_ledger_rerun → ①单独 add 声明文件 + ②
  批次内容与销行标记同一 commit + ⑤台账随批次自动重跑。
- test_unaccounted_dirty_file_blocks_whole_run → ③"非 clean"（账面对不上的脏文件）
  整轮跳过，不强行处理，也不误伤无关脏文件。
- test_non_master_branch_skips → ③"非 master"跳过。
- test_process_normal_batch_stops_when_push_not_fast_forward → ③"推送非快进"时
  停手不强推，本地提交保留、远端不变，退出码 2（用直接调用内部函数的方式构造
  "本地已提交、push 前才发现分叉"这一时序，CLI 级黑盒测试难以确定性构造该竞态）。
- test_straggler_row_marked_done_without_content_commit → ②"遗留尾巴"处置：批次已
  登记但当前无对应脏改动时，只补销行、不产生内容 commit。
"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-落库sweep.py")
EDIT_LOCK_SOURCE = Path(__file__).resolve().with_name("工具-共享文档编辑锁.py")

_spec = importlib.util.spec_from_file_location("commit_sweep", SCRIPT)
sweep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sweep)

QUEUE_HEADER_ONLY = (
    "---\ntitle: 测试队列\n---\n\n# 测试队列\n\n"
    "## 一、任务看板\n\n| # | 任务 | 状态 |\n|---|------|------|\n| 1 | 占位 | 待领 |\n\n"
    "## 二、待 commit 批次\n\n"
    "| 批次 | 文件清单 | 建议 message | 状态 |\n"
    "|------|---------|--------------|------|\n"
    "{rows}"
    "\n## 三、口径冻结标\n\n（无）\n"
)

STUB_LEDGER_SCRIPT = (
    "from pathlib import Path\n"
    "p = Path(__file__).resolve().parents[1] / '1-转型规划' / '0-全景路线图' / '文档台账-自动生成.md'\n"
    "p.parent.mkdir(parents=True, exist_ok=True)\n"
    "p.write_text('台账桩内容 v1\\n', encoding='utf-8')\n"
)


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    # 测试自身校验用的 git 调用也要关 quotepath——本项目路径几乎全是中文，
    # 不关掉的话 status/show/log -p 里的路径会被转义成八进制字符串，见 SUT 里
    # 同样理由的注释（工具-落库sweep.py::_run_git）。
    return subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=cwd,
                           capture_output=True, text=True, encoding="utf-8", check=check)


def _run_sweep(work: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(work), *extra],
        capture_output=True, text=True, encoding="utf-8",
    )


class SweepTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.origin = base / "origin.git"
        self.work = base / "work"
        _git(base, "init", "--bare", "-q", str(self.origin))
        _git(base, "init", "-q", str(self.work))
        _git(self.work, "config", "user.email", "test@example.com")
        _git(self.work, "config", "user.name", "Test")
        _git(self.work, "remote", "add", "origin", str(self.origin))

        (self.work / "0-学习与工具").mkdir(parents=True)
        shutil.copy(EDIT_LOCK_SOURCE, self.work / "0-学习与工具" / "工具-共享文档编辑锁.py")
        (self.work / "0-学习与工具" / "工具-文档台账生成.py").write_text(
            STUB_LEDGER_SCRIPT, encoding="utf-8")
        (self.work / "1-转型规划" / "0-全景路线图").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _write_queue(self, rows: str) -> None:
        (self.work / sweep.QUEUE_REL).write_text(
            QUEUE_HEADER_ONLY.format(rows=rows), encoding="utf-8", newline="")

    def _commit_all(self, message: str) -> None:
        _git(self.work, "add", "-A")
        _git(self.work, "commit", "-q", "-m", message)

    def _init_and_push(self, rows: str = "") -> None:
        self._write_queue(rows)
        self._commit_all("init")
        _git(self.work, "branch", "-M", "master")
        _git(self.work, "push", "-q", "-u", "origin", "master")

    def _origin_log(self) -> str:
        return _git(self.origin, "log", "--oneline").stdout

    def _queue_text(self) -> str:
        return (self.work / sweep.QUEUE_REL).read_text(encoding="utf-8")


class HappyPathTests(SweepTestBase):
    def test_happy_path_commits_atomically_with_ledger_rerun(self):
        self._init_and_push(rows="")
        # 仿真"Cowork 登记了一条待 commit 批次"——只改队列文件、不提交，
        # 声明片段刻意省略"1-转型规划/"前缀（真实项目里的通行写法）。
        row = ("| B-TEST | `0-全景路线图/跨桌任务队列.md`（新行占位） "
               "| `docs(test): 测试批次落库` | 待 CC 取活 |\n")
        self._write_queue(row)

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        # 要求①：只 add 了声明文件——工作区里除队列文件外没有别的改动可添，
        # 此处用"origin 只多出预期的两个 commit（批次本身 + 台账重跑）"间接验证
        # 没有产生任何游离的/意外的提交内容。
        origin_log = self._origin_log()
        self.assertEqual(len(origin_log.strip().splitlines()), 3,  # init + 批次 + 台账
                          origin_log)

        pushed_queue = _git(self.origin, "show", "master:" + sweep.QUEUE_REL).stdout
        self.assertIn("✅ 已完成", pushed_queue)
        self.assertIn("sweep 自动落库", pushed_queue)
        # 要求②：批次内容与销行标记在同一个 commit——队列历史上唯一一次
        # touch 这一行的提交，落地时就已经是"✅ 已完成"，从未存在过一个独立
        # 提交记录过"待 CC 取活"的中间状态（即"内容已提交、销行还没跟上"的
        # 慢一拍尾巴不会发生，因为压根没有分两次提交）。
        history_touching_row = _git(
            self.origin, "log", "-p", "--", sweep.QUEUE_REL,
        ).stdout
        self.assertEqual(history_touching_row.count("B-TEST |"), 1,
                          "队列历史上应恰好一次出现该行——只有落地态，没有过渡态")
        self.assertIn("+| B-TEST |", history_touching_row)
        self.assertIn("✅ 已完成", history_touching_row)
        self.assertNotIn("待 CC 取活", history_touching_row)

        # 要求⑤：台账随批次自动重跑一次并入库。
        ledger = _git(self.origin, "show", "master:" + sweep.LEDGER_OUTPUT_REL).stdout
        self.assertIn("台账桩内容 v1", ledger)

        log_file = self.work / sweep.LOG_REL
        self.assertTrue(log_file.exists())
        self.assertIn("已落库并推送", log_file.read_text(encoding="utf-8"))


class SafetyGateTests(SweepTestBase):
    def test_unaccounted_dirty_file_blocks_whole_run(self):
        self._init_and_push(rows="")
        row = ("| B-TEST | `0-全景路线图/跨桌任务队列.md`（新行占位） "
               "| `docs(test): 测试批次落库` | 待 CC 取活 |\n")
        self._write_queue(row)
        # 无关脏文件——不属于任何待 commit 批次声明。
        (self.work / "杂物.md").write_text("别人session的未提交东西\n", encoding="utf-8")

        before_log = self._origin_log()
        result = _run_sweep(self.work)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("非 clean", result.stdout)
        self.assertIn("杂物.md", result.stdout)
        self.assertEqual(self._origin_log(), before_log, "不应有任何提交被推送")
        self.assertIn("待 CC 取活", self._queue_text(), "队列不应被改动")
        self.assertTrue((self.work / "杂物.md").exists(), "无关文件不应被误删/误动")

    def test_non_master_branch_skips(self):
        self._init_and_push(rows="")
        _git(self.work, "checkout", "-q", "-b", "other-branch")

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("非 master", result.stdout)

    def test_dry_run_makes_no_changes(self):
        self._init_and_push(rows="")
        row = ("| B-TEST | `0-全景路线图/跨桌任务队列.md`（新行占位） "
               "| `docs(test): 测试批次落库` | 待 CC 取活 |\n")
        self._write_queue(row)
        before_log = self._origin_log()

        result = _run_sweep(self.work, "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self._origin_log(), before_log)
        self.assertIn("待 CC 取活", self._queue_text())
        self.assertFalse((self.work / sweep.LOG_REL).exists(), "dry-run 不应落盘日志")


class StragglerTailTests(SweepTestBase):
    def test_straggler_row_marked_done_without_content_commit(self):
        # 批次已随 init 一并提交（队列文件本身干净），但声明的文件从未真实
        # 存在过脏改动——仿真"内容已在此前某次提交中落库，只是没销行"的尾巴。
        row = ("| B-STALE | `不存在的文件.md` "
               "| `docs(test): 早已落库只是没销行` | 待 CC 取活 |\n")
        self._init_and_push(rows=row)

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        origin_log = self._origin_log()
        # init + 补销尾巴（无台账变化——桩脚本首次运行本会产生台账 commit；
        # 但补销尾巴分支同样会触发 processed_any=True 进而重跑台账，故为 3 行）。
        self.assertEqual(len(origin_log.strip().splitlines()), 3, origin_log)

        pushed_queue = _git(self.origin, "show", "master:" + sweep.QUEUE_REL).stdout
        self.assertIn("✅ 已完成", pushed_queue)
        self.assertIn("补销遗留尾巴", pushed_queue)

        # 补销尾巴那次 commit 只应改队列文件，不应有内容文件被凭空 add 进来。
        tail_commit_files = _git(
            self.origin, "show", "--name-only", "--format=", "master~1",
        ).stdout.strip().splitlines()
        self.assertEqual(tail_commit_files, [sweep.QUEUE_REL])


class LateForwardCheckTests(SweepTestBase):
    """要求③"推送非快进"里最难构造的时序：本地已经 commit 完批次内容，
    真要 push 前才发现 origin/master 已经分叉——用直接调用内部函数的方式
    构造该状态，CLI 级黑盒测试无法确定性地插入这个时间点。"""

    def test_process_normal_batch_stops_when_push_not_fast_forward(self):
        self._init_and_push(rows="")
        row_line = ("| B-TEST | `0-全景路线图/跨桌任务队列.md`（新行占位） "
                    "| `docs(test): 测试批次落库` | 待 CC 取活 |\n")
        self._write_queue(row_line)
        queue_text = self._queue_text()
        rows = sweep._parse_section_two(queue_text)
        row = next(r for r in rows if r["batch_id"] == "B-TEST")

        # 另开一个 clone，向 origin 推一个本地工作区看不到的提交，制造分叉——
        # 模拟"其他并发 session 在本次 sweep 处理期间抢先 push 了 master"。
        other_clone = self.work.parent / "other_clone"
        _git(self.work.parent, "clone", "-q", str(self.origin), str(other_clone))
        _git(other_clone, "config", "user.email", "other@example.com")
        _git(other_clone, "config", "user.name", "Other")
        (other_clone / "旁路提交.md").write_text("并发session的内容\n", encoding="utf-8")
        _git(other_clone, "add", "-A")
        _git(other_clone, "commit", "-q", "-m", "并发提交")
        _git(other_clone, "push", "-q", "origin", "master")

        log: list[str] = []
        with self.assertRaises(sweep.SweepAbort) as ctx:
            sweep._process_normal_batch(self.work, row, [sweep.QUEUE_REL], dry_run=False, log=log)
        self.assertEqual(ctx.exception.exit_code, 2)
        self.assertIn("本地已提交", str(ctx.exception))
        self.assertIn("推送非快进", str(ctx.exception))

        # 本地提交没有被撤销（不是"假装什么都没发生"），但也没有被强推上去。
        local_head = _git(self.work, "rev-parse", "HEAD").stdout.strip()
        origin_head = _git(self.origin, "rev-parse", "master").stdout.strip()
        self.assertNotEqual(local_head, origin_head)
        local_log = _git(self.work, "log", "--oneline").stdout
        self.assertIn("测试批次落库", local_log)


if __name__ == "__main__":
    unittest.main()
