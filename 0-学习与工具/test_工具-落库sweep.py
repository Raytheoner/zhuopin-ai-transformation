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

另覆盖 #121(b) 修法（2026-07-27）：陈旧 `.git/index.lock` 前置自愈——
- test_stale_index_lock_is_self_healed_and_run_proceeds → 陈旧锁自动清除后本轮
  正常继续处理批次。
- test_fresh_index_lock_aborts_gracefully_with_log → 新鲜锁（疑似真实并发 git
  进程）不抢占，优雅跳过并**必须落盘日志**——回归修复前"未捕获异常导致
  LastTaskResult=1 但日志无新条目"的症状。
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
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

        # 真实项目 reports/ 全局 gitignore（**/reports/）——队列 #222 起，
        # sweep 在起跑最开头就会往 LOG_REL 写一行（启动即写日志首行），若
        # 测试仓库不还原这条 gitignore，该写入会把日志文件自己变成一个
        # "不属于任何批次声明"的脏文件，被 _status_paths 捕获后触发"非
        # clean"整轮跳过——这不是生产环境会出现的问题（生产仓库确有该
        # gitignore 规则），只是测试夹具需要还原真实布局才能验证真实行为。
        (self.work / ".gitignore").write_text("**/reports/\n", encoding="utf-8")

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
        # 队列 #288 起，提交与推送职责拆分——批次先"已本地提交"，推送发生
        # 在本轮末尾统一的一次"已统一推送"，不再是单个批次自己的"已落库
        # 并推送"（旧文案）。
        log_text = log_file.read_text(encoding="utf-8")
        self.assertIn("已本地提交", log_text)
        self.assertIn("已统一推送", log_text)

    def test_end_to_end_248_incident_row_is_not_swept_while_genuine_pending_row_still_is(self):
        """队列 #248 端到端真实验证（非 dry-run，走真实 CLI + 真实 git 提交）：
        一行状态列开头是 ✅ 已完成、句级分隔符之后的说明文字引用了判据原文
        （含"待"字）的行，不应被 sweep 取活覆写；同一轮里一条真正待处理的行
        仍应正常落库——证明取活→落库→回写全链路在修法后依然正常工作，
        判据既不误取活也不会收得过紧。"""
        self._init_and_push(rows="")
        done_row_status = (
            "**✅ 已完成**（sweep 自动落库 2026-08-05 08:00 UTC）。"
            "说明：本次登记文字引用了 sweep 判据原文"
            "「既不含 ✅ 也不含表示尚未处理的单字」，仅作说明，不影响本行已完成状态。"
        )
        rows = (
            f"| B-248复现 | `0-全景路线图/跨桌任务队列.md`（占位，不应被处理） "
            f"| `docs(test): 不应发生的提交` | {done_row_status} |\n"
            "| B-真实待处理 | `0-全景路线图/跨桌任务队列.md`（同文件，验证不受上一行影响） "
            "| `docs(test): 应该发生的提交` | 待处理（登记，待 sweep 落库） |\n"
        )
        self._write_queue(rows)

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        pushed_queue = _git(self.origin, "show", "master:" + sweep.QUEUE_REL).stdout
        self.assertIn("B-248复现", pushed_queue)
        self.assertIn(done_row_status, pushed_queue,
                       "开头✅、分隔符之后引用判据关键词的行，内容不应被 sweep 改动/覆写")
        self.assertIn("B-真实待处理", pushed_queue)
        self.assertNotIn("待处理（登记，待 sweep 落库）", pushed_queue,
                          "真正待处理的行应被正常取活并回写为已完成，不能因本次修法而收得过紧")
        self.assertIn("sweep 自动落库", pushed_queue)


class SafetyGateTests(SweepTestBase):
    def test_orphan_dirty_file_does_not_block_unrelated_batch(self):
        """队列 #238：批次隔离生效后，一个与在办批次毫无关系的孤儿脏文件
        不应再让整轮 return 0——旧行为（本用例修复前的名字正是
        test_unaccounted_dirty_file_blocks_whole_run）在 08-04 实测里正是
        20 批积压的根因，故本用例断言方向整体反转：批次应正常落库，孤儿
        文件只在日志里留痕提示，不阻塞任何人、也不被误删/误动。"""
        self._init_and_push(rows="")
        row = ("| B-TEST | `0-全景路线图/跨桌任务队列.md`（新行占位） "
               "| `docs(test): 测试批次落库` | 待 CC 取活 |\n")
        self._write_queue(row)
        # 无关脏文件——不属于任何待 commit 批次声明，且不与 B-TEST 的声明
        # 片段有任何交集（B-TEST 只声明了队列文件本身）。
        (self.work / "杂物.md").write_text("别人session的未提交东西\n", encoding="utf-8")

        result = _run_sweep(self.work)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("孤儿", result.stdout)
        self.assertIn("杂物.md", result.stdout)
        # 关键反转：B-TEST 与孤儿文件毫无声明交集，应正常落库并推送。
        pushed_queue = _git(self.origin, "show", "master:" + sweep.QUEUE_REL).stdout
        self.assertIn("✅ 已完成", pushed_queue)
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
    """要求③"推送非快进"场景——2026-08-06 起（队列 #288，openspec 变更包
    `sweep-ff-sync-batch-reorder`）职责已拆分：`_process_normal_batch` 只
    负责本地提交，不再自己校验快进/推送；"origin 已分叉时如何处理"这一
    职责整体移到批次提交完成后的统一对齐步骤（见 `SyncReorderTests`，覆盖
    "不冲突自动 rebase 推送成功"与"真实冲突安全回滚+复用分叉告警"两种
    子场景）。本类保留下来，专门验证"职责已经真的移走"这一契约本身：
    `_process_normal_batch` 在 origin 已分叉时应该正常完成本地提交、
    不再抛出任何异常——避免未来有人不小心把校验逻辑加回这个函数里。"""

    def test_process_normal_batch_only_commits_locally_even_when_origin_has_diverged(self):
        self._init_and_push(rows="")
        row_line = ("| B-TEST | `0-全景路线图/跨桌任务队列.md`（新行占位） "
                    "| `docs(test): 测试批次落库` | 待 CC 取活 |\n")
        self._write_queue(row_line)
        queue_text = self._queue_text()
        rows = sweep._parse_section_two(queue_text)
        row = next(r for r in rows if r["batch_id"] == "B-TEST")

        # 另开一个 clone，向 origin 推一个本地工作区看不到的提交，制造分叉——
        # 模拟"其他并发 session 已经抢先 push 了 master"。
        other_clone = self.work.parent / "other_clone"
        _git(self.work.parent, "clone", "-q", str(self.origin), str(other_clone))
        _git(other_clone, "config", "user.email", "other@example.com")
        _git(other_clone, "config", "user.name", "Other")
        (other_clone / "旁路提交.md").write_text("并发session的内容\n", encoding="utf-8")
        _git(other_clone, "add", "-A")
        _git(other_clone, "commit", "-q", "-m", "并发提交")
        _git(other_clone, "push", "-q", "origin", "master")

        log: list[str] = []
        # 不应再抛出 SweepAbort——是否能与 origin 对齐已不是这个函数的职责。
        sweep._process_normal_batch(self.work, row, [sweep.QUEUE_REL], dry_run=False, log=log)

        local_log = _git(self.work, "log", "--oneline").stdout
        self.assertIn("测试批次落库", local_log, "批次内容应已在本地提交")
        # 不要求 git status 完全无输出——编辑锁工具留下的 `.editlock*` 标记
        # 文件在真实项目里已被 .gitignore 排除，本测试夹具未声明同款忽略
        # 规则，属正常噪音（同 SyncReorderTests 里同一处说明）；真正要断言
        # 的是队列文件本身已提交、不再是脏改动。
        dirty_after = [ln for ln in _git(self.work, "status", "--porcelain").stdout.splitlines()
                       if ln[3:] == sweep.QUEUE_REL]  # 精确比对路径，避免误配 .editlock* 等前缀同名文件
        self.assertEqual(dirty_after, [], "队列文件应已随批次一起提交，不应仍是脏改动")
        # origin 完全不受影响——分叉的处理是另一个函数的职责，不在这里发生。
        origin_head = _git(self.origin, "rev-parse", "master").stdout.strip()
        local_head = _git(self.work, "rev-parse", "HEAD").stdout.strip()
        self.assertNotEqual(local_head, origin_head)
        local_log = _git(self.work, "log", "--oneline").stdout
        self.assertIn("测试批次落库", local_log)


class IndexLockSelfHealTests(SweepTestBase):
    """#121(b)：`.git/index.lock` 残留会让后续 `_run_git`（check=True）抛未捕获
    的 CalledProcessError——不是 SweepAbort，main() 的 except 接不住，日志也就
    没机会落盘。这正是实测到的"LastTaskResult=1 但日志无新条目"。"""

    def test_stale_index_lock_is_self_healed_and_run_proceeds(self):
        self._init_and_push(rows="")
        row = ("| B-TEST | `0-全景路线图/跨桌任务队列.md`（新行占位） "
               "| `docs(test): 测试批次落库` | 待 CC 取活 |\n")
        self._write_queue(row)

        lock_file = self.work / ".git" / "index.lock"
        lock_file.write_text("", encoding="utf-8")
        stale_time = time.time() - sweep.STALE_INDEX_LOCK_MINUTES * 60 - 60
        os.utime(lock_file, (stale_time, stale_time))

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(lock_file.exists(), "陈旧 index.lock 应已被自愈清除")
        self.assertIn("自愈", result.stdout)

        # 自愈只是前置步骤，不是自愈完就停手——本轮应正常继续处理批次。
        origin_log = self._origin_log()
        self.assertEqual(len(origin_log.strip().splitlines()), 3, origin_log)  # init+批次+台账
        pushed_queue = _git(self.origin, "show", "master:" + sweep.QUEUE_REL).stdout
        self.assertIn("✅ 已完成", pushed_queue)

    def test_fresh_index_lock_aborts_gracefully_with_log(self):
        self._init_and_push(rows="")
        row = ("| B-TEST | `0-全景路线图/跨桌任务队列.md`（新行占位） "
               "| `docs(test): 测试批次落库` | 待 CC 取活 |\n")
        self._write_queue(row)

        lock_file = self.work / ".git" / "index.lock"
        lock_file.write_text("", encoding="utf-8")  # mtime = 刚刚，视为新鲜

        before_log = self._origin_log()
        result = _run_sweep(self.work)

        # 关键回归点：修复前这种情况会在某个 check=True 的 _run_git 调用处抛
        # 未捕获的 CalledProcessError；修复后应优雅跳过（退出码 0）且必须落盘日志。
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("index.lock", result.stdout)
        self.assertEqual(self._origin_log(), before_log, "不应有任何提交被推送")
        self.assertIn("待 CC 取活", self._queue_text(), "队列不应被改动")

        log_file = self.work / sweep.LOG_REL
        self.assertTrue(log_file.exists(), "即便跳过本轮，也必须落盘日志（回归 #121(b)）")
        self.assertIn("index.lock", log_file.read_text(encoding="utf-8"))
        self.assertTrue(lock_file.exists(), "新鲜锁不应被清除——可能是真实并发 git 进程")


class ClassifySectionTwoRowsUnitTests(unittest.TestCase):
    """`_classify_section_two_rows` 纯函数级单测——2026-07-28 判据修复的核心回归点。

    直接覆盖四种状态列写法（不经过完整 git 流程，快且精确）：
    含✅的待处理写法（登记方误写，历史上曾致石沉大海）/ 纯待处理写法（推荐写法）/
    已完成（不应被重跑）/ 模糊状态（既不含✅也不含待，应被识别但不处理）。
    """

    def test_classifies_four_status_forms(self):
        rows = [
            {"batch_id": "A-含✅误写", "status_cell": "✅ 已完成（本次登记，待 sweep 落库）"},
            {"batch_id": "B-纯待处理", "status_cell": "待处理（登记，待 sweep 落库）"},
            {"batch_id": "C-已完成", "status_cell": "**✅ 已完成**（sweep 自动落库 2026-07-27 00:00 UTC）"},
            {"batch_id": "D-模糊状态", "status_cell": "内容已确认"},
        ]
        pending, ambiguous = sweep._classify_section_two_rows(rows)
        self.assertEqual([r["batch_id"] for r in pending], ["A-含✅误写", "B-纯待处理"],
                          "含✅但同时带'待'字样的误写，与纯'待'写法，均应判定为待处理")
        self.assertEqual([r["batch_id"] for r in ambiguous], ["D-模糊状态"],
                          "只有既不含✅也不含待的行才是模糊状态")
        # C-已完成 既不在待处理也不在模糊状态里——正常略过，不告警。
        all_ids = {r["batch_id"] for r in pending} | {r["batch_id"] for r in ambiguous}
        self.assertNotIn("C-已完成", all_ids)

    def test_leading_segment_excludes_quoted_rule_citation_after_separator(self):
        """队列 #248 真实事故复现：开头是完成标记，句级分隔符之后的说明文字
        引用了判据原文（含"待"字），不应因此被误判为待处理。"""
        row = {
            "batch_id": "B-0805_复现248事故",
            "status_cell": (
                "**✅ 已完成**（sweep 自动落库 2026-08-05 08:00 UTC）。"
                "说明：本次登记文字引用了 sweep 判据原文"
                "「既不含 ✅ 也不含表示尚未处理的单字」，仅作说明，不影响本行已完成状态。"
            ),
        }
        pending, ambiguous = sweep._classify_section_two_rows([row])
        self.assertEqual(pending, [], "句级分隔符之后引用判据关键词，不应被判为待处理（回归 #248）")
        self.assertEqual(ambiguous, [])

    def test_leading_segment_excludes_citation_after_dash_separator(self):
        """同 #248 场景，但用"——"破折号分隔（项目另一常见句级分隔写法）。"""
        row = {
            "batch_id": "B-0805_破折号变体",
            "status_cell": "**✅ 已完成**（sweep 自动落库）——原判据讨论：待字样出现在此处不应触发误判",
        }
        pending, ambiguous = sweep._classify_section_two_rows([row])
        self.assertEqual(pending, [], "破折号之后的判据讨论文字不应触发误判")
        self.assertEqual(ambiguous, [])

    def test_no_separator_still_detects_pending_within_short_cell(self):
        """反向用例：短促、无句级分隔符的状态列（真实误写场景），'待'字仍须被检出，
        不能因为本次改判据而让判据收得过紧、导致真正待处理的批次被漏判。"""
        row = {"batch_id": "B-短促误写", "status_cell": "✅ 已完成（本次登记，待 sweep 落库）"}
        pending, ambiguous = sweep._classify_section_two_rows([row])
        self.assertEqual([r["batch_id"] for r in pending], ["B-短促误写"])

    def test_fullwidth_space_and_asterisk_prefix_stripped(self):
        """队列 #248 决策点 4：前导剥离字符集含全角空格。"""
        row = {"batch_id": "B-全角空格前导", "status_cell": "　**✅ 已完成**（sweep 自动落库）"}
        pending, ambiguous = sweep._classify_section_two_rows([row])
        self.assertEqual(pending, [])
        self.assertEqual(ambiguous, [], "全角空格+星号剥离后开头即为✅，应判已完成而非模糊状态")


class ResolveBatchFilesUnitTests(unittest.TestCase):
    """`_resolve_batch_files` 纯函数级单测——队列 #234(1) 精确相等优先修复。"""

    def test_exact_match_wins_even_when_another_path_also_ends_with_fragment(self):
        # 08-04 真实现场复现：根 CLAUDE.md 与 SC8/CLAUDE.md 同时脏，片段
        # `CLAUDE.md` 在旧实现下对两者各算一次 → 判为 ambiguous。
        dirty = ["CLAUDE.md", "4-数字员工/采购部/SC8-.../CLAUDE.md"]
        resolved, not_dirty, ambiguous = sweep._resolve_batch_files(
            "`CLAUDE.md`（根 CLAUDE.md 的改动）", dirty,
        )
        self.assertEqual(resolved, ["CLAUDE.md"])
        self.assertEqual(not_dirty, [])
        self.assertEqual(ambiguous, [], "精确命中应唯一采用，不应被判为歧义")

    def test_suffix_match_still_works_when_no_exact_match(self):
        dirty = ["4-数字员工/采购部/SC8-.../CLAUDE.md", "杂物.md"]
        resolved, not_dirty, ambiguous = sweep._resolve_batch_files(
            "`SC8-.../CLAUDE.md`（省略前缀写法）", dirty,
        )
        self.assertEqual(resolved, ["4-数字员工/采购部/SC8-.../CLAUDE.md"])
        self.assertEqual(not_dirty, [])
        self.assertEqual(ambiguous, [])

    def test_true_ambiguity_without_exact_match_is_still_flagged(self):
        # 反向用例（CLAUDE.md §5"清单确实缺其它文件时安全门仍必须拦截"）：
        # 两个候选都只是后缀匹配、没有一个精确相等——真实无法判定，仍须
        # 落 ambiguous，不能因本次收窄而放松成"随便选一个"。
        dirty = [
            "4-数字员工/采购部/SC8-.../CLAUDE.md",
            "4-数字员工/质量部/QD-B-.../CLAUDE.md",
        ]
        resolved, not_dirty, ambiguous = sweep._resolve_batch_files("`CLAUDE.md`", dirty)
        self.assertEqual(resolved, [])
        self.assertEqual(not_dirty, [])
        self.assertEqual(ambiguous, ["CLAUDE.md"])

    def test_no_match_is_not_dirty(self):
        resolved, not_dirty, ambiguous = sweep._resolve_batch_files(
            "`不存在的文件.md`", ["杂物.md"],
        )
        self.assertEqual(resolved, [])
        self.assertEqual(not_dirty, ["不存在的文件.md"])
        self.assertEqual(ambiguous, [])


class CheckDirtyPathAgainstPendingBatchTests(unittest.TestCase):
    """队列 #101①：`_check_dirty_paths_against_pending_batches` + CLI 模式单测。

    只读、不需要 git 仓库——被测函数只读队列 markdown 文件，本类用普通临时目录
    （非 git 仓库）验证 CLI 短路确实发生在 `_check_preconditions`/`.git` 断言之前。
    供 `工具-主工作区安全同步.ps1` 在建议 `git checkout --` 弃改前调用。
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmp.name)
        (self.repo_root / "1-转型规划" / "0-全景路线图").mkdir(parents=True, exist_ok=True)
        # 刻意不 git init——验证本检查模式不依赖真实 git 仓库。

    def tearDown(self):
        self._tmp.cleanup()

    def _write_queue(self, rows_md: str) -> None:
        text = QUEUE_HEADER_ONLY.format(rows=rows_md)
        (self.repo_root / sweep.QUEUE_REL).write_text(text, encoding="utf-8")

    def test_declared_dirty_file_matches_pending_batch(self):
        self._write_queue("| B-x | `4-数字员工/采购部/x.py` | `msg` | 待处理（登记）|\n")
        results = sweep._check_dirty_paths_against_pending_batches(
            self.repo_root, ["4-数字员工/采购部/x.py"])
        self.assertEqual(results, [("4-数字员工/采购部/x.py", "B-x")])

    def test_undeclared_dirty_file_does_not_match(self):
        self._write_queue("| B-x | `4-数字员工/采购部/x.py` | `msg` | 待处理（登记）|\n")
        results = sweep._check_dirty_paths_against_pending_batches(
            self.repo_root, ["某个无关文件.md"])
        self.assertEqual(results, [("某个无关文件.md", None)])

    def test_completed_batch_not_treated_as_pending(self):
        """已 ✅ 完成的批次不再算"待处理"——即便文件路径字面对得上，也不该拦
        `git checkout --`：那属于批次完工后的新改动，不是本机制要保护的对象。"""
        self._write_queue(
            "| B-done | `4-数字员工/采购部/x.py` | `msg` | ✅ 已完成（sweep 自动落库）|\n")
        results = sweep._check_dirty_paths_against_pending_batches(
            self.repo_root, ["4-数字员工/采购部/x.py"])
        self.assertEqual(results, [("4-数字员工/采购部/x.py", None)])

    def test_multiple_paths_independently_resolved(self):
        self._write_queue(
            "| B-x | `a.py`／`b.py` | `msg` | 待处理（登记）|\n"
            "| B-y | `c.py` | `msg` | 待处理（登记）|\n"
        )
        results = sweep._check_dirty_paths_against_pending_batches(
            self.repo_root, ["a.py", "c.py", "d.py"])
        self.assertEqual(results, [("a.py", "B-x"), ("c.py", "B-y"), ("d.py", None)])

    def test_cli_mode_short_circuits_before_git_repo_assertion(self):
        """CLI 模式须在 `_check_preconditions`（要求真实 `.git`）之前短路返回——
        本用例的 repo_root 根本不是 git 仓库，若短路顺序错了会在此处报错而非
        输出 MATCH/NOMATCH 行。"""
        self._write_queue("| B-x | `4-数字员工/采购部/x.py` | `msg` | 待处理（登记）|\n")
        proc = _run_sweep(self.repo_root, "--check-dirty-in-pending-batch",
                          "4-数字员工/采购部/x.py", "无关文件.md")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = proc.stdout.strip().splitlines()
        self.assertIn("MATCH\tB-x\t4-数字员工/采购部/x.py", lines)
        self.assertIn("NOMATCH\t无关文件.md", lines)


class ExactMatchEndToEndTests(SweepTestBase):
    """队列 #234(1) 的 CLI 端到端复现：批次已正确声明的文件不应因"另一个
    同名文件也脏"而被误判歧义（08-04 真实现场：根 CLAUDE.md 因与
    SC8/CLAUDE.md 同时脏被判 ambiguous，20 批积压）。队列 #238 批次隔离
    落地后，SC8 那份孤儿文件也不再拖累 B-TEST 整批——断言方向随之更新为
    "B-TEST 正常落库 + SC8 只作孤儿提示"，不再是"整轮安全跳过"。"""

    def test_correctly_declared_file_not_flagged_ambiguous_by_duplicate_basename(self):
        self._init_and_push(rows="")
        row = ("| B-TEST | `CLAUDE.md`、`0-全景路线图/跨桌任务队列.md` "
               "| `docs(test): 精确相等优先` | 待 CC 取活 |\n")
        self._write_queue(row)
        (self.work / "CLAUDE.md").write_text("根 CLAUDE.md 的改动，属于本批次\n", encoding="utf-8")
        # 制造"另一个同名文件也脏"的现场——不属于本批次声明，与批次声明的
        # 片段字符串完全相同（模拟根 CLAUDE.md vs SC8/CLAUDE.md 撞名）。
        other_dir = self.work / "4-数字员工" / "采购部" / "SC8"
        other_dir.mkdir(parents=True)
        (other_dir / "CLAUDE.md").write_text("另一份同名文件，不属于本批次（模拟并发 session）\n",
                                               encoding="utf-8")

        result = _run_sweep(self.work)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # 关键断言：根 CLAUDE.md 已被正确声明+精确解析，B-TEST 与 SC8 那份
        # 孤儿文件毫无声明交集，队列 #238 批次隔离后应正常落库并推送——
        # 修复前（#234(1) 只做精确相等优先、未做批次隔离）此处会因
        # "非 clean"整轮跳过，SC8 拖累了本已正确声明的 B-TEST。
        pushed_queue = _git(self.origin, "show", "master:" + sweep.QUEUE_REL).stdout
        self.assertIn("✅ 已完成", pushed_queue)
        # SC8 那份始终未被任何批次声明，应作为孤儿在日志里留痕提示（不阻塞）。
        self.assertIn("孤儿", result.stdout)
        orphan_lines = [
            line for line in result.stdout.splitlines() if line.strip().startswith("- ")
        ]
        self.assertTrue(orphan_lines)
        self.assertTrue(all("SC8" in line for line in orphan_lines), orphan_lines)


class BatchIsolationIntegrationTests(SweepTestBase):
    """队列 #238 CLI 端到端：一批因自身声明歧义而暂缓，另一批与之无关，
    应正常落库——验证"部分批次落库 + 部分暂缓"这一核心场景，及可解释
    日志（打印歧义片段的匹配候选，回应 #234 附带要求）。"""

    def test_ambiguous_batch_deferred_while_unrelated_clean_batch_proceeds(self):
        self._init_and_push(rows="")
        (self.work / "content1.md").write_text("干净批次的内容\n", encoding="utf-8")
        sc8_dir = self.work / "4-数字员工" / "采购部" / "SC8"
        sc8_dir.mkdir(parents=True)
        (sc8_dir / "CLAUDE.md").write_text("SC8 的 CLAUDE.md\n", encoding="utf-8")
        qdb_dir = self.work / "4-数字员工" / "质量部" / "QD-B"
        qdb_dir.mkdir(parents=True)
        (qdb_dir / "CLAUDE.md").write_text("QD-B 的 CLAUDE.md\n", encoding="utf-8")

        rows = (
            "| B-CLEAN | `content1.md`、`0-全景路线图/跨桌任务队列.md`（新行占位） "
            "| `docs(test): 干净批次应正常落库` | 待处理 |\n"
            "| B-BLOCKED | `CLAUDE.md` "
            "| `docs(test): 歧义批次应被暂缓` | 待处理 |\n"
        )
        self._write_queue(rows)

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        # B-CLEAN 正常落库并推送；B-BLOCKED 因自身声明歧义而暂缓，队列里
        # 原样保留"待处理"，未被误标记已完成。
        pushed_queue = _git(self.origin, "show", "master:" + sweep.QUEUE_REL).stdout
        rows_after = {r["batch_id"]: r for r in sweep._parse_section_two(self._queue_text())}
        self.assertIn("sweep 自动落库", rows_after["B-CLEAN"]["status_cell"])
        self.assertIn("✅", pushed_queue)
        self.assertEqual(rows_after["B-BLOCKED"]["status_cell"], "待处理",
                          "被暂缓的批次不应被误标记为已完成")
        self.assertEqual(_git(self.origin, "show", "master:content1.md", check=False).returncode, 0,
                          "B-CLEAN 的内容文件应已真实落库")

        # 可解释日志：逐条写明因哪个片段命中几处候选而暂缓。
        self.assertIn("B-BLOCKED", result.stdout)
        self.assertIn("因声明片段未能唯一判定而暂缓", result.stdout)
        self.assertIn("CLAUDE.md", result.stdout)
        self.assertIn("命中 2 处", result.stdout)
        self.assertIn("SC8", result.stdout)
        self.assertIn("QD-B", result.stdout)

    def test_all_batches_blocked_logs_no_batch_processable_without_crashing(self):
        """两个批次全部因自身歧义暂缓时，main() 应正常收尾（不崩溃、
        退出码 0），且日志明确说明"本轮无批次可落库"，而不是安静地什么
        都不说。"""
        self._init_and_push(rows="")
        sc8_dir = self.work / "4-数字员工" / "采购部" / "SC8"
        sc8_dir.mkdir(parents=True)
        (sc8_dir / "CLAUDE.md").write_text("SC8\n", encoding="utf-8")
        qdb_dir = self.work / "4-数字员工" / "质量部" / "QD-B"
        qdb_dir.mkdir(parents=True)
        (qdb_dir / "CLAUDE.md").write_text("QD-B\n", encoding="utf-8")

        row = "| B-BLOCKED | `CLAUDE.md` | `docs(test): 歧义批次` | 待处理 |\n"
        self._write_queue(row)

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("本轮无批次可落库", result.stdout)
        self.assertEqual(len(self._origin_log().strip().splitlines()), 1,
                          "全部批次暂缓时不应产生任何新提交")
        self.assertIn("init", self._origin_log())
        self.assertEqual(sweep._parse_section_two(self._queue_text())[0]["status_cell"], "待处理")


class PendingCriteriaIntegrationTests(SweepTestBase):
    """CLI 级端到端验证：四种状态形态在真实 git 流程里各自的下场。"""

    def test_four_status_forms_processed_correctly_end_to_end(self):
        self._init_and_push(rows="")
        (self.work / "content1.md").write_text("待处理批次1内容\n", encoding="utf-8")
        (self.work / "content2.md").write_text("待处理批次2内容\n", encoding="utf-8")

        rows = (
            "| B-CHECK-AND-DAI | `content1.md`、`0-全景路线图/跨桌任务队列.md`（新行占位） "
            "| `docs(test): 含✅误写的待处理批次` "
            "| ✅ 已完成（本次登记，待 sweep 落库） |\n"
            "| B-DAI-ONLY | `content2.md` "
            "| `docs(test): 纯待处理批次` "
            "| 待处理（登记，待 sweep 落库） |\n"
            "| B-DONE | `不存在的文件.md` "
            "| `docs(test): 已完成不应被重跑` "
            "| **✅ 已完成**（sweep 自动落库 2026-07-27 00:00 UTC） |\n"
            "| B-AMBIGUOUS | `不存在的文件.md` "
            "| `docs(test): 模糊状态不应被处理` "
            "| 内容已确认 |\n"
        )
        self._write_queue(rows)

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        # 含✅误写 + 纯待处理 均应被识别并落库销行。
        rows_after = {r["batch_id"]: r for r in sweep._parse_section_two(self._queue_text())}
        self.assertIn("sweep 自动落库", rows_after["B-CHECK-AND-DAI"]["status_cell"],
                       "含✅但带'待'字样的误写，此前会被永久判定已处理而漏掉——本次应被正常处理")
        self.assertIn("sweep 自动落库", rows_after["B-DAI-ONLY"]["status_cell"])

        # 已完成行原样不动，不产生二次提交。
        self.assertEqual(rows_after["B-DONE"]["status_cell"],
                          "**✅ 已完成**（sweep 自动落库 2026-07-27 00:00 UTC）")

        # 模糊状态行原样不动，但必须有告警（宁可吵不可哑），日志与 stdout 均须出现。
        self.assertEqual(rows_after["B-AMBIGUOUS"]["status_cell"], "内容已确认")
        self.assertIn("状态列模糊", result.stdout)
        self.assertIn("B-AMBIGUOUS", result.stdout)
        log_text = (self.work / sweep.LOG_REL).read_text(encoding="utf-8")
        self.assertIn("B-AMBIGUOUS", log_text)

        # 两个内容文件均已真实落库入 origin（不是只改了状态列的空转）。
        self.assertEqual(_git(self.origin, "show", "master:content1.md", check=False).returncode, 0)
        self.assertEqual(_git(self.origin, "show", "master:content2.md", check=False).returncode, 0)


class SyncBehindOriginTests(SweepTestBase):
    """2026-07-28 补：主工作区本地 master 落后 origin/master 的前置自愈。"""

    def _push_from_other_clone(self, filename: str, message: str) -> None:
        other_clone = self.work.parent / f"other_clone_{filename}"
        _git(self.work.parent, "clone", "-q", str(self.origin), str(other_clone))
        _git(other_clone, "config", "user.email", "other@example.com")
        _git(other_clone, "config", "user.name", "Other")
        (other_clone / filename).write_text("并发 worktree 的内容\n", encoding="utf-8")
        _git(other_clone, "add", "-A")
        _git(other_clone, "commit", "-q", "-m", message)
        _git(other_clone, "push", "-q", "origin", "master")

    def test_behind_origin_with_pending_batch_commits_then_rebases_and_pushes(self):
        """队列 #288（2026-08-06，openspec 变更包 `sweep-ff-sync-batch-reorder`）
        起，本用例的实际路径已变化——原名
        `test_pure_behind_auto_ff_merges_then_processes_pending_batch` 断言
        "落后 origin/master" 这句 ff-only 文案，但批次改为"先本地提交再对齐"
        后，提交完成的那一刻本地相对最初的 origin 快照已经是**领先**（多了
        这个批次的提交），而 origin 同时也领先（多了另一 worktree 的推送）
        ——两者互不为祖先，构成分叉，故实际走的是 `git rebase` 分支，不是
        `--ff-only`。断言相应更新为检查 rebase 相关文案与最终结果；真正
        "落后但当轮无批次可提交"的 ff-only 直接路径见
        `SyncReorderTests.test_pure_behind_with_no_pending_batch_still_ff_merges`。
        （如实记录：本次调整属于职责重排的自然结果，不是发现了新缺陷。）"""
        self._init_and_push(rows="")
        # 模拟另一 worktree 的 CC session 已把改动推去 origin/master——
        # 本地工作区尚未 fetch/merge。
        self._push_from_other_clone("另一worktree产出.md", "另一worktree推送")

        local_head_before = _git(self.work, "rev-parse", "HEAD").stdout.strip()
        origin_head_before = _git(self.origin, "rev-parse", "master").stdout.strip()
        self.assertNotEqual(local_head_before, origin_head_before, "前提：本地确实落后")

        row = ("| B-TEST | `0-全景路线图/跨桌任务队列.md`（新行占位） "
               "| `docs(test): 测试批次落库` | 待 CC 取活 |\n")
        self._write_queue(row)

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("git rebase 自动对齐", result.stdout)
        self.assertNotIn("跳过本轮", result.stdout)

        # 本地已通过 rebase 追上另一 worktree 的推送，且当轮批次照常处理。
        local_log = _git(self.work, "log", "--oneline").stdout
        self.assertIn("另一worktree推送", local_log)
        pushed_queue = _git(self.origin, "show", "master:" + sweep.QUEUE_REL).stdout
        self.assertIn("✅ 已完成", pushed_queue)

        origin_log = self._origin_log()
        # init + 另一worktree推送 + 本批次 + 台账重跑 = 4
        self.assertEqual(len(origin_log.strip().splitlines()), 4, origin_log)

    def test_diverged_from_origin_master_skips_without_forcing(self):
        self._init_and_push(rows="")
        # 本地有一个尚未推送的本地提交。
        (self.work / "本地未推送.md").write_text("本地独有内容\n", encoding="utf-8")
        _git(self.work, "add", "-A")
        _git(self.work, "commit", "-q", "-m", "本地未推送提交")
        # 另一 clone 基于同一起点推了一支不同的提交——制造真分叉（互不为祖先）。
        self._push_from_other_clone("并发内容.md", "并发提交")

        local_head_before = _git(self.work, "rev-parse", "HEAD").stdout.strip()
        origin_head_before = _git(self.origin, "rev-parse", "master").stdout.strip()

        result = _run_sweep(self.work)
        # 队列 #171：分叉此前静默退出码 0（计划任务看到"成功"），修复后
        # 前置分叉检测改用 is_fork=True，退出码变为 FORK_EXIT_CODE（人工介入语义）。
        self.assertEqual(result.returncode, sweep.FORK_EXIT_CODE, result.stdout + result.stderr)
        self.assertIn("非快进", result.stdout)

        self.assertEqual(_git(self.work, "rev-parse", "HEAD").stdout.strip(), local_head_before,
                          "分叉场景不应尝试合并，本地 HEAD 不应变化")
        self.assertEqual(_git(self.origin, "rev-parse", "master").stdout.strip(), origin_head_before,
                          "不应有任何强推，origin 端不应变化")


class _CapturingWebhookHandler(BaseHTTPRequestHandler):
    """极简本地 webhook 桩：记录收到的请求体，恒回 `{"errcode": 0}`。"""

    received: list[dict] = []

    def do_POST(self):  # noqa: N802 — BaseHTTPRequestHandler 既定命名
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        type(self).received.append(json.loads(body.decode("utf-8")))
        response = json.dumps({"errcode": 0}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, *args):  # 静默——不打印到测试输出
        pass


class ForkAlertTests(SweepTestBase):
    """队列 #171：分叉静默停摆告警——检测/告警发送/连续升级/解除后重置。"""

    def setUp(self):
        super().setUp()
        _CapturingWebhookHandler.received = []
        self._server = HTTPServer(("127.0.0.1", 0), _CapturingWebhookHandler)
        self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._server_thread.start()
        self.webhook_url = f"http://127.0.0.1:{self._server.server_port}/webhook"

    def tearDown(self):
        self._server.shutdown()
        self._server.server_close()
        super().tearDown()

    def _write_env_webhook(self) -> None:
        (self.work / ".env").write_text(
            f"WECOM_WEBHOOK_URL={self.webhook_url}\n", encoding="utf-8",
        )

    def _diverge(self) -> None:
        self._init_and_push(rows="")
        (self.work / "本地未推送.md").write_text("本地独有内容\n", encoding="utf-8")
        _git(self.work, "add", "-A")
        _git(self.work, "commit", "-q", "-m", "本地未推送提交")
        other_clone = self.work.parent / "other_clone_fork"
        _git(self.work.parent, "clone", "-q", str(self.origin), str(other_clone))
        _git(other_clone, "config", "user.email", "other@example.com")
        _git(other_clone, "config", "user.name", "Other")
        (other_clone / "并发内容.md").write_text("并发 session 的内容\n", encoding="utf-8")
        _git(other_clone, "add", "-A")
        _git(other_clone, "commit", "-q", "-m", "并发提交")
        _git(other_clone, "push", "-q", "origin", "master")

    def test_fork_without_env_skips_send_but_still_elevates_exit_code_and_writes_state(self):
        self._diverge()
        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, sweep.FORK_EXIT_CODE, result.stdout + result.stderr)
        self.assertIn("未在 .env 找到", result.stdout)
        state = json.loads((self.work / sweep.FORK_STATE_REL).read_text(encoding="utf-8"))
        self.assertEqual(state["consecutive"], 1)
        self.assertEqual(len(_CapturingWebhookHandler.received), 0, "无 .env 时不应尝试网络请求")

    def test_fork_with_webhook_sends_alert_once(self):
        self._diverge()
        self._write_env_webhook()
        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, sweep.FORK_EXIT_CODE, result.stdout + result.stderr)
        self.assertIn("分叉告警已推送", result.stdout)
        self.assertEqual(len(_CapturingWebhookHandler.received), 1)
        payload = _CapturingWebhookHandler.received[0]
        self.assertEqual(payload["msgtype"], "markdown")
        self.assertIn("分叉", payload["markdown"]["content"])
        self.assertIn("首次检测到", payload["markdown"]["content"])

    def test_consecutive_fork_runs_escalate_count_in_alert(self):
        self._diverge()
        self._write_env_webhook()
        _run_sweep(self.work)
        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, sweep.FORK_EXIT_CODE, result.stdout + result.stderr)
        self.assertEqual(len(_CapturingWebhookHandler.received), 2)
        second_payload = _CapturingWebhookHandler.received[1]
        self.assertIn("连续第 2 轮", second_payload["markdown"]["content"])
        state = json.loads((self.work / sweep.FORK_STATE_REL).read_text(encoding="utf-8"))
        self.assertEqual(state["consecutive"], 2)

    def test_fork_resolved_resets_state_and_exit_code_returns_to_zero(self):
        self._diverge()
        self._write_env_webhook()
        first = _run_sweep(self.work)
        self.assertEqual(first.returncode, sweep.FORK_EXIT_CODE, first.stdout + first.stderr)
        self.assertTrue((self.work / sweep.FORK_STATE_REL).exists())

        # 人工介入解除分叉：把本地分支重置到与 origin/master 一致（模拟 Paul/CC
        # 手动 reset --hard 或 rebase 后的结果——具体解决手段不是本测试关心的，
        # 只关心"解除后下一轮 sweep 应恢复健康且清空陈旧计数"）。
        _git(self.work, "fetch", "origin")
        _git(self.work, "reset", "--hard", "origin/master")

        second = _run_sweep(self.work)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertFalse(
            (self.work / sweep.FORK_STATE_REL).exists(),
            "分叉解除后应清空连续计数状态文件，不留陈旧数据",
        )

    def test_non_fork_skip_does_not_write_fork_state_or_alert(self):
        # 对照组：非 master 分支属"健康跳过"，不应被误判为分叉告警对象。
        self._init_and_push(rows="")
        self._write_env_webhook()
        _git(self.work, "checkout", "-q", "-b", "other-branch")

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.work / sweep.FORK_STATE_REL).exists())
        self.assertEqual(len(_CapturingWebhookHandler.received), 0)


class EditLockProbeUnitTests(unittest.TestCase):
    """队列 #198(b)：`_edit_lock_is_actively_held` 纯函数级判据——三态输出
    文本里只有"占用中且未陈旧"含"（有效）"三字。"""

    def test_active_lock_output_is_detected(self):
        stdout = "占用方：Cowork-财务专线（改队列）\n备注：\n已持锁：3 分钟（有效）\n"
        self.assertTrue(sweep._edit_lock_is_actively_held(stdout))

    def test_no_lock_output_is_not_detected(self):
        self.assertFalse(sweep._edit_lock_is_actively_held("（无锁，可直接编辑）\n"))

    def test_stale_lock_output_is_not_detected(self):
        stdout = "占用方：某会话\n备注：\n已持锁：40 分钟（已陈旧（可接管））\n"
        self.assertFalse(sweep._edit_lock_is_actively_held(stdout))


class EditLockProbeIntegrationTests(SweepTestBase):
    """队列 #198(b) CLI 级集成：真实占用编辑锁后跑 sweep，验证零 git 动作。"""

    def test_active_lock_blocks_whole_run_with_zero_git_actions(self):
        row = ("| B-TEST | `0-全景路线图/跨桌任务队列.md`（新行占位） "
               "| `docs(test): 测试批次落库` | 待 CC 取活 |\n")
        self._init_and_push(rows=row)
        self._write_queue(row)

        acquire = subprocess.run(
            [sys.executable, str(self.work / "0-学习与工具" / "工具-共享文档编辑锁.py"),
             "--file", sweep.QUEUE_REL, "acquire", "--who", "测试占用方", "--note", "模拟人类持锁"],
            cwd=self.work, capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(acquire.returncode, 0, acquire.stdout + acquire.stderr)

        before_log = self._origin_log()
        result = _run_sweep(self.work)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("有效占用", result.stdout)
        self.assertEqual(self._origin_log(), before_log, "锁占用期间不应有任何提交被推送")
        self.assertIn("待 CC 取活", self._queue_text(), "队列不应被改动，连 git add 都不应发生")


class UnpushedCommitBackfillTests(SweepTestBase):
    """队列 #194：起跑段无条件补推未推送提交，不绑定"§二 有无待处理批次"。"""

    def test_unpushed_commit_with_no_pending_batches_is_backfilled(self):
        """仿真真实复现场景：上一轮已在本地 commit 完批次内容但 push 失败
        （网络抖动），队列文件里该行已是"✅已完成"（销行随 commit 一起落盘）
        ——本轮 §二 无待处理批次，旧判据会直接空转、提交永远滞留本地。"""
        self._init_and_push(rows="")
        (self.work / "已提交未推送.md").write_text("上一轮本地提交的内容\n", encoding="utf-8")
        _git(self.work, "add", "-A")
        _git(self.work, "commit", "-q", "-m", "docs(test): 模拟上一轮提交成功推送失败")
        local_head = _git(self.work, "rev-parse", "HEAD").stdout.strip()
        origin_head_before = _git(self.origin, "rev-parse", "master").stdout.strip()
        self.assertNotEqual(local_head, origin_head_before, "前提：本地确实领先未推送")

        result = _run_sweep(self.work)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("起跑补推", result.stdout)
        origin_head_after = _git(self.origin, "rev-parse", "master").stdout.strip()
        self.assertEqual(origin_head_after, local_head, "滞留的本地提交应已被补推上去")

    def test_dry_run_reports_would_push_without_pushing(self):
        self._init_and_push(rows="")
        (self.work / "已提交未推送.md").write_text("内容\n", encoding="utf-8")
        _git(self.work, "add", "-A")
        _git(self.work, "commit", "-q", "-m", "docs(test): 本地提交")
        origin_head_before = _git(self.origin, "rev-parse", "master").stdout.strip()

        result = _run_sweep(self.work, "--dry-run")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("[dry-run] 起跑将补推", result.stdout)
        self.assertEqual(_git(self.origin, "rev-parse", "master").stdout.strip(), origin_head_before,
                          "dry-run 不应真实 push")


class FlushPendingLockAppendsTests(SweepTestBase):
    """队列 #192-A（主载体）：sweep 起跑段子进程调用 flush 脚本，异常隔离不
    中断批次处理主流程。"""

    def _flush_script_path(self) -> Path:
        path = self.work / sweep.FLUSH_PENDING_LOCK_SCRIPT_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def test_missing_flush_script_is_silently_skipped(self):
        """本 checkout 未部署机器人服务（脚本不存在）——静默跳过，不产生噪音日志，
        批次处理照常进行（回归既有 happy path）。"""
        self._init_and_push(rows="")
        row = ("| B-TEST | `0-全景路线图/跨桌任务队列.md`（新行占位） "
               "| `docs(test): 测试批次落库` | 待 CC 取活 |\n")
        self._write_queue(row)

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("flush", result.stdout.lower())

    def test_flush_script_failure_does_not_block_batch_processing(self):
        """flush 异常必须捕获并记日志后继续跑批次，不可让兜底把主干带崩。"""
        self._flush_script_path().write_text(
            "import sys\nsys.stderr.write('模拟flush失败：目标文件损坏')\nsys.exit(1)\n",
            encoding="utf-8",
        )
        self._init_and_push(rows="")
        row = ("| B-TEST | `0-全景路线图/跨桌任务队列.md`（新行占位） "
               "| `docs(test): 测试批次落库` | 待 CC 取活 |\n")
        self._write_queue(row)

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("flush 失败", result.stdout)
        self.assertIn("模拟flush失败", result.stdout)
        pushed_queue = _git(self.origin, "show", "master:" + sweep.QUEUE_REL).stdout
        self.assertIn("✅ 已完成", pushed_queue, "flush 失败不应阻止批次照常落库")

    def test_flush_script_success_output_is_logged(self):
        self._flush_script_path().write_text(
            "print('已补录 2 条')\n", encoding="utf-8",
        )
        self._init_and_push(rows="")

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("已补录 2 条", result.stdout)

    def test_dry_run_does_not_invoke_flush_script(self):
        """dry-run 不应产生真实副作用——flush 脚本存在也不应被调用。"""
        marker = self.work.parent / "flush_invoked.marker"
        self._flush_script_path().write_text(
            f"from pathlib import Path\nPath(r'{marker}').write_text('invoked')\n", encoding="utf-8",
        )
        self._init_and_push(rows="")

        result = _run_sweep(self.work, "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(marker.exists(), "dry-run 不应真实调用 flush 脚本")


class DecisionReminderSecondCarrierTests(SweepTestBase):
    """队列 #219：决策提醒第二载体——sweep 起跑段子进程调用
    `decision_reminder_check.py`，须在编辑锁窗口之外、异常隔离不中断批次
    处理主流程（同 #192-A `FlushPendingLockAppendsTests` 同一测试范式）。"""

    def _reminder_script_path(self) -> Path:
        path = self.work / sweep.DECISION_REMINDER_SCRIPT_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def test_missing_reminder_script_is_silently_skipped(self):
        """本 checkout 未部署机器人服务（脚本不存在）——静默跳过，不产生
        噪音日志，批次处理照常进行（回归既有 happy path）。"""
        self._init_and_push(rows="")
        row = ("| B-TEST | `0-全景路线图/跨桌任务队列.md`（新行占位） "
               "| `docs(test): 测试批次落库` | 待 CC 取活 |\n")
        self._write_queue(row)

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("决策提醒", result.stdout)

    def test_reminder_script_failure_does_not_block_batch_processing(self):
        """异常（含非零退出码）必须捕获并记日志后继续跑批次，不可让第二
        载体把主干带崩（实现约束③）。"""
        self._reminder_script_path().write_text(
            "import sys\nsys.stderr.write('模拟决策提醒失败：WS 连接超时')\nsys.exit(1)\n",
            encoding="utf-8",
        )
        self._init_and_push(rows="")
        row = ("| B-TEST | `0-全景路线图/跨桌任务队列.md`（新行占位） "
               "| `docs(test): 测试批次落库` | 待 CC 取活 |\n")
        self._write_queue(row)

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("决策提醒第二载体退出码", result.stdout)
        self.assertIn("模拟决策提醒失败", result.stdout)
        pushed_queue = _git(self.origin, "show", "master:" + sweep.QUEUE_REL).stdout
        self.assertIn("✅ 已完成", pushed_queue, "第二载体失败不应阻止批次照常落库")

    def test_reminder_script_success_with_new_items_is_logged(self):
        self._reminder_script_path().write_text(
            "print('已发送提醒（2 项）。')\n", encoding="utf-8",
        )
        self._init_and_push(rows="")

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("决策提醒第二载体", result.stdout)
        self.assertIn("已发送提醒（2 项）", result.stdout)

    def test_reminder_script_no_new_items_produces_no_noise_log(self):
        """判定为"无新增/超期决策项"是最常见的正常态（每小时跑一次，大多数
        时候没有新东西）——不应刷屏，只在真有内容时才记一行。"""
        self._reminder_script_path().write_text(
            "print('[OK] 无新增/超期决策项，本次不发送。')\n", encoding="utf-8",
        )
        self._init_and_push(rows="")

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("决策提醒第二载体：", result.stdout)

    def test_dry_run_does_not_invoke_reminder_script(self):
        """dry-run 不应产生真实副作用——第二载体脚本存在也不应被调用（会
        真实触发发送企微消息，不可在 dry-run 里发生）。"""
        marker = self.work.parent / "reminder_invoked.marker"
        self._reminder_script_path().write_text(
            f"from pathlib import Path\nPath(r'{marker}').write_text('invoked')\n", encoding="utf-8",
        )
        self._init_and_push(rows="")

        result = _run_sweep(self.work, "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(marker.exists(), "dry-run 不应真实调用决策提醒第二载体脚本")

    def test_reminder_invoked_before_edit_lock_would_be_taken(self):
        """实现约束①：须在 sweep 自己取编辑锁窗口之外调用——用一个会记录
        "调用瞬间编辑锁文件是否存在"的探测脚本，验证调用发生在
        `_strike_off_rows` 真正 acquire 锁之前（此刻锁文件应尚不存在）。"""
        probe_marker = self.work.parent / "lock_state_at_reminder_call.txt"
        lock_file_rel = sweep.QUEUE_REL + ".editlock"
        self._reminder_script_path().write_text(
            "import os\nfrom pathlib import Path\n"
            f"lock_exists = os.path.exists(r'{self.work}/{lock_file_rel}')\n"
            f"Path(r'{probe_marker}').write_text(str(lock_exists))\n",
            encoding="utf-8",
        )
        self._init_and_push(rows="")
        row = ("| B-TEST | `0-全景路线图/跨桌任务队列.md`（新行占位） "
               "| `docs(test): 测试批次落库` | 待 CC 取活 |\n")
        self._write_queue(row)

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(probe_marker.exists())
        self.assertEqual(probe_marker.read_text(encoding="utf-8").strip(), "False",
                          "第二载体调用瞬间不应有编辑锁被 sweep 自己持有")


class ScheduledTaskMirrorSyncTests(SweepTestBase):
    """队列 #235/#188：定时任务真身↔镜像自动核对——检出差异需就地本地提交
    （不留孤儿脏文件）+ 复用 #171 webhook 告警；无变化时静默；凭据拦截同样
    告警但不产生 commit（脚本自身不写该任务的镜像文件）。"""

    def setUp(self):
        super().setUp()
        _CapturingWebhookHandler.received = []
        self._server = HTTPServer(("127.0.0.1", 0), _CapturingWebhookHandler)
        self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._server_thread.start()
        self.webhook_url = f"http://127.0.0.1:{self._server.server_port}/webhook"

    def tearDown(self):
        self._server.shutdown()
        self._server.server_close()
        super().tearDown()

    def _write_env_webhook(self) -> None:
        (self.work / ".env").write_text(
            f"WECOM_WEBHOOK_URL={self.webhook_url}\n", encoding="utf-8",
        )

    def _backup_script_path(self) -> Path:
        path = self.work / sweep.SCHEDULED_TASK_BACKUP_SCRIPT_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def test_missing_backup_script_is_silently_skipped(self):
        self._init_and_push(rows="")
        row = ("| B-TEST | `0-全景路线图/跨桌任务队列.md`（新行占位） "
               "| `docs(test): 测试批次落库` | 待 CC 取活 |\n")
        self._write_queue(row)

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("镜像核对", result.stdout)

    def test_no_diff_produces_no_commit_and_no_webhook_noise(self):
        self._backup_script_path().write_text(
            "print('=== 定时任务 prompt 回镜报告 ===\\n  任务甲: · 无变化')\n",
            encoding="utf-8",
        )
        self._init_and_push(rows="")
        self._write_env_webhook()

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("镜像核对", result.stdout)
        self.assertEqual(len(_CapturingWebhookHandler.received), 0)

    def test_detected_diff_is_committed_locally_and_pushed_plus_alerted(self):
        """脚本模拟"检出差异并写回镜像文件"——须被就地 add+commit（不留
        孤儿脏文件），随本轮末尾统一推送，并触发一次 webhook 告警。"""
        mirror_dir_rel = sweep.SCHEDULED_TASK_MIRROR_DIR_REL
        mirror_leaf = mirror_dir_rel.split("/")[-1]
        self._backup_script_path().write_text(
            "from pathlib import Path\n"
            f"mirror = Path(__file__).resolve().with_name({mirror_leaf!r})\n"
            "mirror.mkdir(parents=True, exist_ok=True)\n"
            "(mirror / '任务甲.SKILL.md').write_text('更正后的内容\\n', encoding='utf-8')\n"
            "print('=== 定时任务 prompt 回镜报告 ===\\n  任务甲: ✓ 已更新镜像')\n",
            encoding="utf-8",
        )
        self._init_and_push(rows="")
        self._write_env_webhook()

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("检出差异并已自动更正", result.stdout)

        # 不留孤儿脏文件：镜像目录本身必须已被提交（不针对整个工作区断言——
        # 测试夹具自己写的 .env 未加入 .gitignore，与本用例验证的行为无关）。
        mirror_status = _git(self.work, "status", "--porcelain", "--", mirror_dir_rel).stdout
        self.assertEqual(mirror_status.strip(), "", "镜像差异必须在 dirty_paths 捕获前就地提交，不留孤儿")

        # 随本轮末尾统一推送——origin 应能看到这次镜像更正的提交。
        pushed_mirror = _git(
            self.origin, "show", f"master:{mirror_dir_rel}/任务甲.SKILL.md",
        ).stdout
        self.assertIn("更正后的内容", pushed_mirror)

        self.assertEqual(len(_CapturingWebhookHandler.received), 1)
        payload = _CapturingWebhookHandler.received[0]
        self.assertIn("镜像核对", payload["markdown"]["content"])

    def test_credential_blocked_alerts_without_local_changes(self):
        """命中凭据扫描——脚本按自身设计不写入该任务镜像（无 git 变化），
        但退出码非零，须告警提示人工核实，不应静默。"""
        self._backup_script_path().write_text(
            "import sys\n"
            "print('=== 定时任务 prompt 回镜报告 ===\\n  任务乙: 🔴 命中凭据扫描·已拒绝写入')\n"
            "sys.exit(1)\n",
            encoding="utf-8",
        )
        self._init_and_push(rows="")
        self._write_env_webhook()

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, "凭据拦截是纯提示，不应改变 sweep 本轮退出码：" +
                          result.stdout + result.stderr)
        self.assertIn("疑似命中凭据扫描", result.stdout)
        self.assertEqual(len(_CapturingWebhookHandler.received), 1)
        payload = _CapturingWebhookHandler.received[0]
        self.assertIn("凭据扫描", payload["markdown"]["content"])

    def test_dry_run_does_not_invoke_backup_script(self):
        marker = self.work.parent / "mirror_sync_invoked.marker"
        self._backup_script_path().write_text(
            f"from pathlib import Path\nPath(r'{marker}').write_text('invoked')\n", encoding="utf-8",
        )
        self._init_and_push(rows="")

        result = _run_sweep(self.work, "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(marker.exists(), "dry-run 不应真实调用定时任务镜像核对脚本")


class BatchLandingCountTests(SweepTestBase):
    """队列 #257（P3，先计数不告警）：每轮落库批次数记录——纯数据积累，
    不改变任何既有行为。"""

    def test_processed_batch_records_landing_count(self):
        self._init_and_push(rows="")
        row = ("| B-TEST | `0-全景路线图/跨桌任务队列.md`（新行占位） "
               "| `docs(test): 测试批次落库` | 待 CC 取活 |\n")
        self._write_queue(row)

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        log_path = self.work / sweep.SESSION_BATCH_COUNT_LOG_REL
        self.assertTrue(log_path.exists())
        record = json.loads(log_path.read_text(encoding="utf-8").strip().splitlines()[-1])
        self.assertEqual(record["batch_count"], 1)
        self.assertIn("B-TEST", record["batch_ids"])

    def test_no_pending_batches_does_not_create_landing_count_file(self):
        self._init_and_push(rows="")

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.work / sweep.SESSION_BATCH_COUNT_LOG_REL).exists())

    def test_dry_run_does_not_write_landing_count(self):
        self._init_and_push(rows="")
        row = ("| B-TEST | `0-全景路线图/跨桌任务队列.md`（新行占位） "
               "| `docs(test): 测试批次落库` | 待 CC 取活 |\n")
        self._write_queue(row)

        result = _run_sweep(self.work, "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.work / sweep.SESSION_BATCH_COUNT_LOG_REL).exists())


class StartupLogLineTests(SweepTestBase):
    """队列 #222：启动即写日志首行——不等收尾统一 flush，即便本轮在起跑
    极早期就发生"连 except Exception 都接不住"的崩溃，也应已有一行落盘，
    使"启动后立刻崩溃"与"压根没启动"在日志上不再表现完全相同（#121(b)
    遗留未做项）。"""

    def test_start_line_is_flushed_before_any_risky_code_runs(self):
        self._init_and_push(rows="")
        import unittest.mock as mock

        with mock.patch.object(
            sweep, "_heal_stale_index_lock", side_effect=SystemExit(1),
        ):
            argv_backup = sys.argv
            try:
                sys.argv = ["工具-落库sweep.py", "--repo-root", str(self.work)]
                with self.assertRaises(SystemExit):
                    sweep.main()
            finally:
                sys.argv = argv_backup

        log_text = (self.work / sweep.LOG_REL).read_text(encoding="utf-8")
        self.assertIn("=== sweep 运行", log_text,
                      "即便后续代码发生 except Exception 都接不住的崩溃，启动首行也应已落盘")

    def test_start_line_not_duplicated_on_normal_run(self):
        """回归：正常运行一轮，日志文件里"=== sweep 运行"这一行应恰好出现
        一次（首行单独 flush + 收尾 flush 剩余部分，不应重复写入同一行）。"""
        self._init_and_push(rows="")
        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        log_text = (self.work / sweep.LOG_REL).read_text(encoding="utf-8")
        self.assertEqual(log_text.count("=== sweep 运行"), 1, log_text)

    def test_dry_run_does_not_flush_start_line(self):
        self._init_and_push(rows="")
        result = _run_sweep(self.work, "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.work / sweep.LOG_REL).exists(), "dry-run 不应落盘日志")


class UnexpectedExceptionFallbackTests(SweepTestBase):
    """队列 #198(a)：main() 通用异常兜底——未预期异常必须写日志（含 UTC）+
    webhook 告警 + 独立退出码，判据与"任务根本没启动"（零日志）区分开。"""

    def setUp(self):
        super().setUp()
        _CapturingWebhookHandler.received = []
        self._server = HTTPServer(("127.0.0.1", 0), _CapturingWebhookHandler)
        self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._server_thread.start()
        self.webhook_url = f"http://127.0.0.1:{self._server.server_port}/webhook"

    def tearDown(self):
        self._server.shutdown()
        self._server.server_close()
        super().tearDown()

    def test_injected_unexpected_exception_writes_log_and_alerts_with_independent_exit_code(self):
        self._init_and_push(rows="")
        (self.work / ".env").write_text(f"WECOM_WEBHOOK_URL={self.webhook_url}\n", encoding="utf-8")

        import unittest.mock as mock
        with mock.patch.object(
            sweep, "_heal_stale_index_lock", side_effect=RuntimeError("模拟未预期异常")
        ):
            argv_backup = sys.argv
            try:
                sys.argv = ["工具-落库sweep.py", "--repo-root", str(self.work)]
                returncode = sweep.main()
            finally:
                sys.argv = argv_backup

        self.assertEqual(returncode, sweep.UNEXPECTED_EXIT_CODE)
        self.assertNotEqual(sweep.UNEXPECTED_EXIT_CODE, 0)
        self.assertNotEqual(sweep.UNEXPECTED_EXIT_CODE, sweep.FORK_EXIT_CODE)

        log_text = (self.work / sweep.LOG_REL).read_text(encoding="utf-8")
        self.assertIn("未预期异常", log_text)
        self.assertIn("RuntimeError", log_text)
        self.assertIn("模拟未预期异常", log_text)
        self.assertIn("UTC", log_text)  # 时间基准必须显式标注（CLAUDE.md §5）

        self.assertEqual(len(_CapturingWebhookHandler.received), 1)
        alert_text = _CapturingWebhookHandler.received[0]["markdown"]["content"]
        self.assertIn("未预期异常", alert_text)
        self.assertIn("RuntimeError", alert_text)


class ResidentServiceDeploymentHintTests(SweepTestBase):
    """队列 #198(c)：本轮 commit 命中常驻服务路径时，日志与 webhook 附部署提示。"""

    def setUp(self):
        super().setUp()
        _CapturingWebhookHandler.received = []
        self._server = HTTPServer(("127.0.0.1", 0), _CapturingWebhookHandler)
        self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._server_thread.start()
        self.webhook_url = f"http://127.0.0.1:{self._server.server_port}/webhook"

    def tearDown(self):
        self._server.shutdown()
        self._server.server_close()
        super().tearDown()

    def test_batch_touching_resident_service_path_gets_hint(self):
        # .env 须先落进初始提交（随 init 一起 clean）——否则它作为未声明的
        # 脏文件会被"非 clean"门禁拦在批次处理之前，测试永远走不到本条要验的逻辑。
        (self.work / ".env").write_text(f"WECOM_WEBHOOK_URL={self.webhook_url}\n", encoding="utf-8")
        self._init_and_push(rows="")
        service_file = self.work / "5-平台底座" / "wecom-aibot-service" / "aibot_service" / "foo.py"
        service_file.parent.mkdir(parents=True)
        service_file.write_text("# 测试改动\n", encoding="utf-8")

        row = ("| B-TEST | `5-平台底座/wecom-aibot-service/aibot_service/foo.py`、"
               "`0-全景路线图/跨桌任务队列.md`（新行占位） "
               "| `docs(test): 涉常驻服务的批次` | 待 CC 取活 |\n")
        self._write_queue(row)

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("涉及常驻服务", result.stdout)
        self.assertIn("ZhuopinAibotDevListener", result.stdout)
        self.assertEqual(len(_CapturingWebhookHandler.received), 1)
        self.assertIn("常驻服务", _CapturingWebhookHandler.received[0]["markdown"]["content"])

    def test_batch_not_touching_resident_service_path_gets_no_hint(self):
        (self.work / ".env").write_text(f"WECOM_WEBHOOK_URL={self.webhook_url}\n", encoding="utf-8")
        self._init_and_push(rows="")
        row = ("| B-TEST | `0-全景路线图/跨桌任务队列.md`（新行占位） "
               "| `docs(test): 不涉常驻服务` | 待 CC 取活 |\n")
        self._write_queue(row)

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("涉及常驻服务", result.stdout)
        self.assertEqual(len(_CapturingWebhookHandler.received), 0)


class PartitionPendingRowsUnitTests(unittest.TestCase):
    """`_partition_pending_rows_by_batch_isolation` 纯函数级单测——队列
    #238 批次隔离核心判据，不经过完整 git 流程，快且精确。"""

    def test_clean_row_with_unrelated_orphan_stays_in_clean_rows(self):
        rows = [{"batch_id": "B-CLEAN", "files_cell": "`content1.md`"}]
        dirty = ["content1.md", "杂物.md"]
        log: list[str] = []
        clean_rows, resolution, orphans = sweep._partition_pending_rows_by_batch_isolation(
            rows, dirty, log,
        )
        self.assertEqual([r["batch_id"] for r in clean_rows], ["B-CLEAN"])
        self.assertEqual(resolution["B-CLEAN"], (["content1.md"], [], []))
        self.assertEqual(orphans, ["杂物.md"])
        self.assertTrue(any("孤儿" in line for line in log))
        self.assertTrue(any("杂物.md" in line for line in log))

    def test_ambiguous_row_excluded_from_clean_rows_with_explain_log(self):
        rows = [{"batch_id": "B-BLOCKED", "files_cell": "`CLAUDE.md`"}]
        dirty = [
            "4-数字员工/采购部/SC8-.../CLAUDE.md",
            "4-数字员工/质量部/QD-B-.../CLAUDE.md",
        ]
        log: list[str] = []
        clean_rows, resolution, orphans = sweep._partition_pending_rows_by_batch_isolation(
            rows, dirty, log,
        )
        self.assertEqual(clean_rows, [])
        self.assertEqual(resolution["B-BLOCKED"], ([], [], ["CLAUDE.md"]))
        # 歧义片段的候选路径不应被算作"孤儿"——它们是有人声明（只是歧义）。
        self.assertEqual(orphans, [])
        self.assertTrue(any("B-BLOCKED" in line and "暂缓" in line for line in log))
        self.assertTrue(any("命中 2 处" in line for line in log))

    def test_one_ambiguous_row_does_not_affect_other_clean_rows(self):
        rows = [
            {"batch_id": "B-CLEAN", "files_cell": "`content1.md`"},
            {"batch_id": "B-BLOCKED", "files_cell": "`CLAUDE.md`"},
        ]
        dirty = [
            "content1.md",
            "4-数字员工/采购部/SC8-.../CLAUDE.md",
            "4-数字员工/质量部/QD-B-.../CLAUDE.md",
        ]
        log: list[str] = []
        clean_rows, resolution, orphans = sweep._partition_pending_rows_by_batch_isolation(
            rows, dirty, log,
        )
        self.assertEqual([r["batch_id"] for r in clean_rows], ["B-CLEAN"])
        self.assertEqual(orphans, [], "两份 CLAUDE.md 均已被 B-BLOCKED 的歧义片段引用，不是孤儿")

    def test_no_pending_rows_all_dirty_paths_are_orphans(self):
        """零批次登记时，所有脏文件都应被视为孤儿（供 #236(2) 追踪告警），
        不因"没有批次可比对"而漏检。"""
        log: list[str] = []
        clean_rows, resolution, orphans = sweep._partition_pending_rows_by_batch_isolation(
            [], ["杂物1.md", "杂物2.md"], log,
        )
        self.assertEqual(clean_rows, [])
        self.assertEqual(resolution, {})
        self.assertEqual(orphans, ["杂物1.md", "杂物2.md"])


class OrphanFileAlertTests(SweepTestBase):
    """队列 #236(2)：孤儿脏文件持续超过阈值即主动告警——首次出现不告警、
    跨阈值告警一次、阈值窗口内不重复、窗口外再度提醒、脱离孤儿状态即清空。"""

    def setUp(self):
        super().setUp()
        _CapturingWebhookHandler.received = []
        self._server = HTTPServer(("127.0.0.1", 0), _CapturingWebhookHandler)
        self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._server_thread.start()
        self.webhook_url = f"http://127.0.0.1:{self._server.server_port}/webhook"

    def tearDown(self):
        self._server.shutdown()
        self._server.server_close()
        super().tearDown()

    def _write_env_webhook(self) -> None:
        (self.work / ".env").write_text(
            f"WECOM_WEBHOOK_URL={self.webhook_url}\n", encoding="utf-8",
        )

    def _write_orphan_state(self, entries: dict) -> None:
        path = self.work / sweep.ORPHAN_STATE_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")

    def _iso(self, hours_ago: float) -> str:
        return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()

    def test_newly_seen_orphan_is_tracked_but_not_alerted(self):
        self._init_and_push(rows="")
        self._write_env_webhook()
        (self.work / "杂物.md").write_text("刚出现的孤儿\n", encoding="utf-8")

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(_CapturingWebhookHandler.received), 0, "首次出现不应立即告警")
        state = json.loads((self.work / sweep.ORPHAN_STATE_REL).read_text(encoding="utf-8"))
        self.assertIn("杂物.md", state)
        self.assertIsNone(state["杂物.md"]["last_alerted"])

    def test_orphan_past_threshold_triggers_alert(self):
        self._init_and_push(rows="")
        self._write_env_webhook()
        (self.work / "杂物.md").write_text("持续存在的孤儿\n", encoding="utf-8")
        self._write_orphan_state({
            "杂物.md": {
                "first_seen": self._iso(sweep.ORPHAN_ALERT_THRESHOLD_HOURS + 0.5),
                "last_alerted": None,
            },
        })

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(_CapturingWebhookHandler.received), 1)
        content = _CapturingWebhookHandler.received[0]["markdown"]["content"]
        self.assertIn("杂物.md", content)
        state = json.loads((self.work / sweep.ORPHAN_STATE_REL).read_text(encoding="utf-8"))
        self.assertIsNotNone(state["杂物.md"]["last_alerted"])

    def test_alert_not_repeated_within_threshold_window(self):
        self._init_and_push(rows="")
        self._write_env_webhook()
        (self.work / "杂物.md").write_text("持续存在的孤儿\n", encoding="utf-8")
        self._write_orphan_state({
            "杂物.md": {
                "first_seen": self._iso(sweep.ORPHAN_ALERT_THRESHOLD_HOURS * 3),
                "last_alerted": self._iso(0.5),  # 半小时前刚提醒过
            },
        })

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(_CapturingWebhookHandler.received), 0,
                          "阈值窗口内不应重复打扰（#147 狼来了教训）")

    def test_alert_repeats_after_another_threshold_window(self):
        self._init_and_push(rows="")
        self._write_env_webhook()
        (self.work / "杂物.md").write_text("持续存在的孤儿\n", encoding="utf-8")
        self._write_orphan_state({
            "杂物.md": {
                "first_seen": self._iso(sweep.ORPHAN_ALERT_THRESHOLD_HOURS * 3),
                "last_alerted": self._iso(sweep.ORPHAN_ALERT_THRESHOLD_HOURS + 0.1),
            },
        })

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(_CapturingWebhookHandler.received), 1,
                          "满一个阈值周期后应再次提醒")

    def test_resolved_orphan_is_cleared_from_state(self):
        """孤儿一旦被声明（本轮不再出现在脏路径里）即从状态清除，不留陈旧
        记录误导下一次真实孤儿的"已孤儿多久"文案。"""
        self._init_and_push(rows="")
        self._write_env_webhook()
        self._write_orphan_state({
            "已消失的文件.md": {"first_seen": self._iso(10), "last_alerted": None},
        })

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        state = json.loads((self.work / sweep.ORPHAN_STATE_REL).read_text(encoding="utf-8"))
        self.assertNotIn("已消失的文件.md", state)

    def test_orphan_alert_without_webhook_env_skips_send_but_logs(self):
        self._init_and_push(rows="")
        (self.work / "杂物.md").write_text("持续存在的孤儿\n", encoding="utf-8")
        self._write_orphan_state({
            "杂物.md": {
                "first_seen": self._iso(sweep.ORPHAN_ALERT_THRESHOLD_HOURS + 0.5),
                "last_alerted": None,
            },
        })

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("未在 .env 找到", result.stdout)
        self.assertEqual(len(_CapturingWebhookHandler.received), 0)

    def test_dry_run_does_not_write_orphan_state(self):
        self._init_and_push(rows="")
        (self.work / "杂物.md").write_text("孤儿\n", encoding="utf-8")

        result = _run_sweep(self.work, "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.work / sweep.ORPHAN_STATE_REL).exists(),
                          "dry-run 不应产生真实状态文件副作用")


class DeploymentTraceHintTests(SweepTestBase):
    """队列 #229：发布收口第②关——命中已部署场景白名单但未同批改动其部署
    留痕文件时提示；同批已改留痕则静默。纯提示、不阻断、不改退出码。"""

    def setUp(self):
        super().setUp()
        _CapturingWebhookHandler.received = []
        self._server = HTTPServer(("127.0.0.1", 0), _CapturingWebhookHandler)
        self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._server_thread.start()
        self.webhook_url = f"http://127.0.0.1:{self._server.server_port}/webhook"

    def tearDown(self):
        self._server.shutdown()
        self._server.server_close()
        super().tearDown()

    def test_deployed_scenario_touched_without_trace_gets_hint(self):
        (self.work / ".env").write_text(f"WECOM_WEBHOOK_URL={self.webhook_url}\n", encoding="utf-8")
        self._init_and_push(rows="")
        sc8_dir = self.work / "4-数字员工" / "采购部" / "SC8-客户订单交期智能承诺"
        sc8_dir.mkdir(parents=True)
        (sc8_dir / "webapp.py").write_text("# 改动\n", encoding="utf-8")

        row = ("| B-TEST | "
               "`4-数字员工/采购部/SC8-客户订单交期智能承诺/webapp.py`、"
               "`0-全景路线图/跨桌任务队列.md`（新行占位） "
               "| `docs(test): 命中已部署场景但未补留痕` | 待 CC 取活 |\n")
        self._write_queue(row)

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("未见部署留痕行", result.stdout)
        self.assertIn("SC8-客户订单交期智能承诺", result.stdout)
        self.assertEqual(len(_CapturingWebhookHandler.received), 1)
        self.assertIn("部署留痕", _CapturingWebhookHandler.received[0]["markdown"]["content"])

    def test_deployed_scenario_touched_with_same_batch_trace_stays_silent(self):
        (self.work / ".env").write_text(f"WECOM_WEBHOOK_URL={self.webhook_url}\n", encoding="utf-8")
        self._init_and_push(rows="")
        sc8_dir = self.work / "4-数字员工" / "采购部" / "SC8-客户订单交期智能承诺"
        sc8_dir.mkdir(parents=True)
        (sc8_dir / "webapp.py").write_text("# 改动\n", encoding="utf-8")
        (sc8_dir / "CLAUDE.md").write_text("已补充部署状态段\n", encoding="utf-8")

        row = ("| B-TEST | "
               "`4-数字员工/采购部/SC8-客户订单交期智能承诺/webapp.py`、"
               "`4-数字员工/采购部/SC8-客户订单交期智能承诺/CLAUDE.md`、"
               "`0-全景路线图/跨桌任务队列.md`（新行占位） "
               "| `docs(test): 已同批补留痕` | 待 CC 取活 |\n")
        self._write_queue(row)

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("未见部署留痕行", result.stdout)
        self.assertEqual(len(_CapturingWebhookHandler.received), 0)

    def test_non_deployed_scenario_path_gets_no_hint(self):
        (self.work / ".env").write_text(f"WECOM_WEBHOOK_URL={self.webhook_url}\n", encoding="utf-8")
        self._init_and_push(rows="")
        row = ("| B-TEST | `0-全景路线图/跨桌任务队列.md`（新行占位） "
               "| `docs(test): 不涉已部署场景` | 待 CC 取活 |\n")
        self._write_queue(row)

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("未见部署留痕行", result.stdout)
        self.assertEqual(len(_CapturingWebhookHandler.received), 0)


class FindMissingDeploymentTraceUnitTests(unittest.TestCase):
    """`_find_missing_deployment_trace` 纯函数级单测。"""

    def test_only_claude_md_touched_is_not_treated_as_scenario_touch(self):
        """只改场景自己的 CLAUDE.md（无其它代码改动）——视为纯文档更新，
        不应触发"未见留痕"提示（本身就是留痕文件的改动）。"""
        touched = {"4-数字员工/采购部/SC8-客户订单交期智能承诺/CLAUDE.md"}
        self.assertEqual(sweep._find_missing_deployment_trace(touched), [])

    def test_unrelated_path_produces_no_hits(self):
        touched = {"0-学习与工具/工具-落库sweep.py"}
        self.assertEqual(sweep._find_missing_deployment_trace(touched), [])

    def test_command_center_uses_root_claude_md_as_trace(self):
        touched = {"1-转型规划/AI运营指挥中心/serve.py"}
        hits = sweep._find_missing_deployment_trace(touched)
        self.assertEqual(hits, ["1-转型规划/AI运营指挥中心/"])

        touched_with_trace = {"1-转型规划/AI运营指挥中心/serve.py", "CLAUDE.md"}
        self.assertEqual(sweep._find_missing_deployment_trace(touched_with_trace), [])


class SyncReorderTests(SweepTestBase):
    """队列 #288（openspec 变更包 `sweep-ff-sync-batch-reorder`）：批次先提交
    后同步——复现"本地队列文件脏（有对应 §二 批次声明）＋ origin 有改动同一
    文件的新提交"这一 2026-08-06 真实故障链的核心场景，及其修法覆盖的
    纯落后/纯领先/多批次单次推送等相邻场景。"""

    def _push_queue_edit_from_other_clone(self, transform, message: str) -> None:
        """仿真"另一并发 session 已经提交并推送了对队列文件的改动"——
        transform 接收当前队列文件文本、返回修改后的文本，供调用方精确控制
        改动落在哪一行（用于分别构造"不冲突"与"真实冲突"两种场景）。"""
        other_clone = self.work.parent / f"other_clone_{abs(hash(message))}"
        _git(self.work.parent, "clone", "-q", str(self.origin), str(other_clone))
        _git(other_clone, "config", "user.email", "other@example.com")
        _git(other_clone, "config", "user.name", "Other")
        queue_path = other_clone / sweep.QUEUE_REL
        queue_path.write_text(
            transform(queue_path.read_text(encoding="utf-8")), encoding="utf-8", newline="")
        _git(other_clone, "add", "-A")
        _git(other_clone, "commit", "-q", "-m", message)
        _git(other_clone, "push", "-q", "origin", "master")

    def _mutate_local_queue(self, transform) -> None:
        path = self.work / sweep.QUEUE_REL
        path.write_text(transform(path.read_text(encoding="utf-8")), encoding="utf-8", newline="")

    def test_dirty_batch_plus_origin_edit_same_file_no_conflict_auto_reconciles(self):
        """核心复现用例（验收要求①）：origin 在 §一 追加一行并发新增任务
        （与本地要提交的 §二 批次改动落在不同行），本地队列文件此时正处于
        "有待 commit 批次声明"的脏状态——这正是 2026-08-06 故障链的前提。
        修复前：`_sync_master_if_behind_origin` 的 `git merge --ff-only` 会因
        本地未提交改动被 git 拒绝而 SweepAbort，批次整轮走不到。
        修复后：批次先本地提交，工作区变干净，据此与 origin 对齐时按
        design.md「决策点1」走 rebase（此刻本地因刚提交而领先、origin 也
        领先，构成分叉），两边改动不重叠，rebase 应能自动合并成功并推送。"""
        self._init_and_push(rows="")

        def append_concurrent_task_row(text: str) -> str:
            return text.replace(
                "| 1 | 占位 | 待领 |\n",
                "| 1 | 占位 | 待领 |\n| 2 | 并发session新增任务 | 待领 |\n",
            )
        self._push_queue_edit_from_other_clone(
            append_concurrent_task_row, "并发session追加任务行")

        row = ("| B-TEST | `0-全景路线图/跨桌任务队列.md`（新行占位） "
               "| `docs(test): 测试批次落库` | 待 CC 取活 |\n")
        self._write_queue(row)  # 此刻工作区相对本地 HEAD 是脏的——§二 新增了这一行

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("跳过本轮", result.stdout,
                          "不应再因 origin 同文件新提交而整轮跳过——这正是本次要修复的故障")

        pushed_queue = _git(self.origin, "show", "master:" + sweep.QUEUE_REL).stdout
        self.assertIn("✅ 已完成", pushed_queue, "本轮批次应已正常落库推送")
        self.assertIn("并发session新增任务", pushed_queue,
                       "rebase 应保留 origin 侧并发新增的内容，不能丢")

        local_head = _git(self.work, "rev-parse", "HEAD").stdout.strip()
        origin_head = _git(self.origin, "rev-parse", "master").stdout.strip()
        self.assertEqual(local_head, origin_head, "对齐成功后本地应与 origin 完全同步")

    def test_dirty_batch_plus_origin_edit_same_line_real_conflict_safely_aborts(self):
        """真实内容冲突（验收要求①的另一半）：本地与 origin 都改了 §一
        占位行的同一处文本——rebase 无法自动合并。要求：`git rebase --abort`
        回到批次已提交的干净状态（本地提交不丢），复用既有 #171 分叉告警
        （退出码/`is_fork`/webhook/连续轮次持久化），不强推、不自动解冲突。"""
        _CapturingWebhookHandler.received = []
        server = HTTPServer(("127.0.0.1", 0), _CapturingWebhookHandler)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        try:
            webhook_url = f"http://127.0.0.1:{server.server_port}/webhook"
            self._init_and_push(rows="")
            (self.work / ".env").write_text(
                f"WECOM_WEBHOOK_URL={webhook_url}\n", encoding="utf-8")

            def modify_placeholder_status_on_origin(text: str) -> str:
                return text.replace("| 1 | 占位 | 待领 |", "| 1 | 占位 | 已被并发session领走 |")
            self._push_queue_edit_from_other_clone(
                modify_placeholder_status_on_origin, "并发session修改占位任务状态")

            row = ("| B-TEST | `0-全景路线图/跨桌任务队列.md`（新行占位） "
                   "| `docs(test): 测试批次落库` | 待 CC 取活 |\n")
            self._write_queue(row)
            # 本地也改同一行占位任务的状态列——与 origin 的改动落在完全相同的
            # 文本位置，构成 rebase 无法自动合并的真实冲突。
            self._mutate_local_queue(
                lambda t: t.replace("| 1 | 占位 | 待领 |", "| 1 | 占位 | 本地在办 |"))

            result = _run_sweep(self.work)
            self.assertEqual(result.returncode, sweep.FORK_EXIT_CODE,
                              result.stdout + result.stderr)

            # 本地批次提交必须完整保留（rebase --abort 应回到提交后的干净状态），
            # 不是"假装什么都没发生"（不能连本地提交本身都丢了）。
            local_log = _git(self.work, "log", "--oneline").stdout
            self.assertIn("测试批次落库", local_log)
            # 不要求 git status 完全无输出——编辑锁工具自身会留下 `.editlock*`
            # 标记文件（真实项目里已被 .gitignore 排除，本测试夹具未声明
            # 同款忽略规则，属正常噪音）；真正要断言的是"没有半完成的冲突
            # 标记"：无未合并路径（U/AA/DD），且 rebase 相关目录已被
            # `git rebase --abort` 清理干净。
            status_lines = _git(self.work, "status", "--porcelain").stdout.splitlines()
            unmerged = [ln for ln in status_lines if ln[:2].strip().upper() == "U"
                        or ln[:2] in ("AA", "DD")]
            self.assertEqual(unmerged, [], "rebase --abort 后不应残留任何未合并冲突路径")
            self.assertFalse((self.work / ".git" / "rebase-merge").exists())
            self.assertFalse((self.work / ".git" / "rebase-apply").exists())

            # 没有任何强推——origin 上不应出现本地批次的"✅ 已完成"内容。
            origin_queue = _git(self.origin, "show", "master:" + sweep.QUEUE_REL).stdout
            self.assertNotIn("✅ 已完成", origin_queue)
            self.assertIn("已被并发session领走", origin_queue)

            # 复用既有 #171 分叉告警机制，不新造一套。
            self.assertTrue((self.work / sweep.FORK_STATE_REL).exists())
            self.assertEqual(len(_CapturingWebhookHandler.received), 1)
            alert_text = _CapturingWebhookHandler.received[0]["markdown"]["content"]
            self.assertIn("分叉", alert_text)
        finally:
            server.shutdown()
            server.server_close()

    def test_pure_behind_with_no_pending_batch_still_ff_merges(self):
        """§二 完全无待处理批次时（无内容可提交），本地 master 纯落后 origin
        仍应正常 ff-only 追上——不依赖"本轮有没有批次要提交"这一前提，
        对齐步骤本身在两种情况下都要跑。"""
        self._init_and_push(rows="")

        def append_concurrent_task_row(text: str) -> str:
            return text.replace(
                "| 1 | 占位 | 待领 |\n",
                "| 1 | 占位 | 待领 |\n| 2 | 并发session新增任务 | 待领 |\n",
            )
        self._push_queue_edit_from_other_clone(
            append_concurrent_task_row, "并发session追加任务行")

        local_head_before = _git(self.work, "rev-parse", "HEAD").stdout.strip()
        origin_head_before = _git(self.origin, "rev-parse", "master").stdout.strip()
        self.assertNotEqual(local_head_before, origin_head_before, "前提：本地确实落后")

        result = _run_sweep(self.work)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        local_head_after = _git(self.work, "rev-parse", "HEAD").stdout.strip()
        self.assertEqual(local_head_after, origin_head_before,
                          "无批次可提交时，纯落后仍应被 ff-only 追上")

    def test_multiple_batches_in_one_round_push_exactly_once(self):
        """多个批次在同一轮被处理时，只应有一次 `git push` 调用（而非每个
        批次各自 push）——直接在进程内调用 `sweep.main()` 并包一层记录调用
        次数的 `_run_git`，比黑盒 CLI 更精确，且不改变任何真实 git 行为
        （包装函数原样转发给真实实现，只做计数）。"""
        self._init_and_push(rows="")
        rows = (
            "| B-ONE | `0-全景路线图/跨桌任务队列.md`（新行占位一） "
            "| `docs(test): 批次一` | 待 CC 取活 |\n"
            "| B-TWO | `0-全景路线图/跨桌任务队列.md`（新行占位二） "
            "| `docs(test): 批次二` | 待 CC 取活 |\n"
        )
        self._write_queue(rows)

        real_run_git = sweep._run_git
        push_calls: list[list[str]] = []

        def counting_run_git(args, cwd, check=True):
            if args and args[0] == "push":
                push_calls.append(list(args))
            return real_run_git(args, cwd, check=check)

        import unittest.mock as mock
        argv_backup = sys.argv
        try:
            sys.argv = ["工具-落库sweep.py", "--repo-root", str(self.work)]
            with mock.patch.object(sweep, "_run_git", side_effect=counting_run_git):
                returncode = sweep.main()
        finally:
            sys.argv = argv_backup

        self.assertEqual(returncode, 0)
        self.assertEqual(len(push_calls), 1,
                          f"应恰好一次 git push，实际 {len(push_calls)} 次：{push_calls}")

        pushed_queue = _git(self.origin, "show", "master:" + sweep.QUEUE_REL).stdout
        self.assertEqual(pushed_queue.count("✅ 已完成"), 2, "两个批次都应落库")

    def test_push_failure_after_successful_reconcile_keeps_local_commit(self):
        """对齐成功（无分叉或 rebase 成功）后，最终统一推送因非分叉原因失败
        （如网络抖动）——本地提交不应被撤销，退出码沿用既有"本地已提交但
        推送失败，需人工核查"语义（既有 exit_code=2）。用包装 `_run_git`
        在真正的 `push` 调用上注入一次性失败来确定性构造，不依赖真实网络。"""
        self._init_and_push(rows="")
        row = ("| B-TEST | `0-全景路线图/跨桌任务队列.md`（新行占位） "
               "| `docs(test): 测试批次落库` | 待 CC 取活 |\n")
        self._write_queue(row)

        real_run_git = sweep._run_git

        class _Faux:
            def __init__(self, returncode, stderr=""):
                self.returncode = returncode
                self.stdout = ""
                self.stderr = stderr

        def faulty_run_git(args, cwd, check=True):
            if args and args[0] == "push":
                if check:
                    raise subprocess.CalledProcessError(1, args, output="", stderr="模拟网络错误")
                return _Faux(1, stderr="模拟网络错误：无法连接远端")
            return real_run_git(args, cwd, check=check)

        import unittest.mock as mock
        argv_backup = sys.argv
        try:
            sys.argv = ["工具-落库sweep.py", "--repo-root", str(self.work)]
            with mock.patch.object(sweep, "_run_git", side_effect=faulty_run_git):
                returncode = sweep.main()
        finally:
            sys.argv = argv_backup

        self.assertEqual(returncode, 2, "推送失败（非分叉）应沿用既有『本地提交不会被撤销』语义")
        local_log = _git(self.work, "log", "--oneline").stdout
        self.assertIn("测试批次落库", local_log, "推送失败不应撤销已完成的本地提交")
        local_head = _git(self.work, "rev-parse", "HEAD").stdout.strip()
        origin_head = _git(self.origin, "rev-parse", "master").stdout.strip()
        self.assertNotEqual(local_head, origin_head, "推送既已失败，origin 不应变化")


if __name__ == "__main__":
    unittest.main()
