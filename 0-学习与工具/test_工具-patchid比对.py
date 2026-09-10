"""`工具-patchid比对.py` 单测（队列 §一 `#534`，`OP-0910-Y`）。

两组夹具：
1. **合成小仓**（`tempfile` 里 `git init`）——正向（真需 ff）／反向（内容已在
   master）／`#341` 形态（等价提交的文件后来在 master 又被改写，blob 不同但
   patch-id 相同）／空提交／分支已是祖先／ref 不存在。
2. **真实仓库夹具**（`#534` 期望产出 ⑶ 明写「反向用例用 `#455` 的真实三提交做
   夹具」）：`74184a2`／`4987cd2`／`7bd70b5` 三提交 ＋ `#341` 实证靶 `4b8a98a`。
   对象库里查不到这些提交（浅克隆／别的机器）即 skip，不假装跑过。
"""
from __future__ import annotations

import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-patchid比对.py")
REAL_REPO = SCRIPT.parent.parent

#: `#455` 真实三提交（分支 `claude/op0905n-editrow-guard-455`，父→子序）。
REAL_455_COMMITS = ("74184a2", "4987cd2", "7bd70b5")
#: `#341` 实证靶（分支 `claude/op0905o-domain-route-341` 尖端；2026-09-10 曾被
#: 三点 diff 误判「+1452 行未合入」）。
REAL_341_TIP = "4b8a98a"


def _load():
    spec = importlib.util.spec_from_file_location("_patchid_compare_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


#: 合成小仓原始提交固定用这个过去的时间戳——否则 cherry-pick 若与原提交落在
#: 同一秒内，会算出**逐字节相同的 SHA**（同树、同父、同作者/提交时间、同信息），
#: master 直接指向原提交，「谱系不同、内容相同」的夹具就不成立（首次跑测试实撞）。
_FIXED_DATE = "2026-09-01T00:00:00+0800"


def _git(repo: Path, *args: str, fixed_date: bool = False) -> str:
    env = dict(os.environ)
    if fixed_date:
        env["GIT_AUTHOR_DATE"] = _FIXED_DATE
        env["GIT_COMMITTER_DATE"] = _FIXED_DATE
    proc = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    if proc.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} 失败：{proc.stderr}")
    return proc.stdout.strip()


def _real_commit_exists(sha: str) -> bool:
    proc = subprocess.run(
        ["git", "-C", str(REAL_REPO), "rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}"],
        capture_output=True,
    )
    return proc.returncode == 0


class _SyntheticRepo:
    """合成小仓：master 一个基线提交；`feat` 分支两个提交 A/B。"""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name)
        _git(self.path, "init", "-q", "-b", "master")
        (self.path / "base.txt").write_text("base\n", encoding="utf-8")
        _git(self.path, "add", "base.txt")
        _git(self.path, "commit", "-q", "-m", "base", fixed_date=True)
        _git(self.path, "checkout", "-q", "-b", "feat")
        (self.path / "a.txt").write_text("alpha\n", encoding="utf-8")
        _git(self.path, "add", "a.txt")
        _git(self.path, "commit", "-q", "-m", "A: add a.txt", fixed_date=True)
        self.sha_a = _git(self.path, "rev-parse", "HEAD")
        (self.path / "a.txt").write_text("alpha\nbeta\n", encoding="utf-8")
        _git(self.path, "commit", "-q", "-am", "B: extend a.txt", fixed_date=True)
        self.sha_b = _git(self.path, "rev-parse", "HEAD")
        _git(self.path, "checkout", "-q", "master")

    def cleanup(self):
        self._tmp.cleanup()

    def master_commit(self, filename: str, content: str, msg: str) -> str:
        (self.path / filename).write_text(content, encoding="utf-8")
        _git(self.path, "add", filename)
        _git(self.path, "commit", "-q", "-m", msg)
        return _git(self.path, "rev-parse", "HEAD")


class SyntheticRepoTests(unittest.TestCase):
    def setUp(self):
        self.module = _load()
        self.repo = _SyntheticRepo()

    def tearDown(self):
        self.repo.cleanup()

    def test_positive_needs_merge_when_nothing_cherry_picked(self):
        # 正向：master 上什么都没做 ⇒ 两个独有提交都无等价 ⇒ 真需 ff。
        r = self.module.compare(branch="feat", base="master", repo=self.repo.path)
        self.assertEqual(r["verdict"], self.module.VERDICT_NEEDS_MERGE)
        self.assertFalse(r["all_in_master"])
        self.assertEqual(r["unique_commit_count"], 2)
        self.assertEqual([m["sha"] for m in r["missing"]], [self.repo.sha_a, self.repo.sha_b])
        self.assertEqual(r["matched"], [])
        self.assertEqual(r["missing_file_count"], 1)

    def test_negative_in_master_after_cherry_pick(self):
        # 反向：master 另行提交了同一份改动（cherry-pick ⇒ 新 SHA、同 patch-id）。
        _git(self.repo.path, "cherry-pick", self.repo.sha_a, self.repo.sha_b)
        r = self.module.compare(branch="feat", base="master", repo=self.repo.path)
        self.assertEqual(r["verdict"], self.module.VERDICT_IN_MASTER)
        self.assertTrue(r["all_in_master"])
        self.assertEqual(r["unique_commit_count"], 2)
        self.assertEqual(len(r["matched"]), 2)
        self.assertEqual(r["missing"], [])
        self.assertEqual(r["hit_file_count"], 1)
        # 证据必须是逐对的：分支 SHA ≠ master SHA，但 patch-id 相同（谱系不同、内容相同）。
        for pair in r["matched"]:
            self.assertNotEqual(pair["sha"], pair["master_sha"])
            self.assertEqual(len(pair["patch_id"]), 40)
        # 分支图仍显示「未并入」（master..feat 仍有 2 个提交）——正是 #455 形态。
        ahead = _git(self.repo.path, "rev-list", "--count", "master..feat")
        self.assertEqual(ahead, "2")

    def test_341_shape_master_later_rewrote_the_file_still_in_master(self):
        # `#341` 形态：等价提交进了 master，之后 master 又改写了同一个文件 ⇒
        # blob 不同、三点 diff 仍报「+N 行」，但 patch-id 判据必须判「已在 master」。
        _git(self.repo.path, "cherry-pick", self.repo.sha_a, self.repo.sha_b)
        self.repo.master_commit("a.txt", "alpha\nbeta\ngamma-master-only\n", "master later edit")
        # 三点 diff 的假阴性如实复现：
        three_dot = _git(self.repo.path, "diff", "--shortstat", "master...feat")
        self.assertIn("insertion", three_dot)
        # blob 逐字节也不同：
        two_dot = _git(self.repo.path, "diff", "--shortstat", "master", "feat", "--", "a.txt")
        self.assertIn("deletion", two_dot)
        # patch-id 判据：
        r = self.module.compare(branch="feat", base="master", repo=self.repo.path)
        self.assertTrue(r["all_in_master"], r)
        self.assertEqual(r["verdict"], self.module.VERDICT_IN_MASTER)

    def test_partial_cherry_pick_is_needs_merge_and_lists_exactly_the_missing_one(self):
        _git(self.repo.path, "cherry-pick", self.repo.sha_a)
        r = self.module.compare(branch="feat", base="master", repo=self.repo.path)
        self.assertFalse(r["all_in_master"])
        self.assertEqual([m["sha"] for m in r["matched"]], [self.repo.sha_a])
        self.assertEqual([m["sha"] for m in r["missing"]], [self.repo.sha_b])

    def test_branch_already_ancestor_is_in_master_with_zero_unique(self):
        _git(self.repo.path, "merge", "-q", "--ff-only", "feat")
        r = self.module.compare(branch="feat", base="master", repo=self.repo.path)
        self.assertTrue(r["all_in_master"])
        self.assertEqual(r["unique_commit_count"], 0)
        self.assertIn("分支已是 master 祖先", self.module.format_evidence(r))

    def test_empty_commit_is_listed_not_counted_as_missing(self):
        _git(self.repo.path, "cherry-pick", self.repo.sha_a, self.repo.sha_b)
        _git(self.repo.path, "checkout", "-q", "feat")
        _git(self.repo.path, "commit", "-q", "--allow-empty", "-m", "empty marker")
        empty_sha = _git(self.repo.path, "rev-parse", "HEAD")
        _git(self.repo.path, "checkout", "-q", "master")
        r = self.module.compare(branch="feat", base="master", repo=self.repo.path)
        self.assertTrue(r["all_in_master"])
        self.assertEqual([e["sha"] for e in r["empty_commits"]], [empty_sha])
        self.assertEqual(r["unique_commit_count"], 3)
        self.assertIn("空 diff", self.module.format_evidence(r))

    def test_merge_commits_are_counted_separately_not_compared(self):
        _git(self.repo.path, "cherry-pick", self.repo.sha_a, self.repo.sha_b)
        self.repo.master_commit("m.txt", "m\n", "master-only commit")
        _git(self.repo.path, "checkout", "-q", "feat")
        _git(self.repo.path, "merge", "-q", "--no-ff", "-m", "merge master into feat", "master")
        _git(self.repo.path, "checkout", "-q", "master")
        r = self.module.compare(branch="feat", base="master", repo=self.repo.path)
        self.assertTrue(r["all_in_master"])
        self.assertEqual(r["merge_commit_count"], 1)
        self.assertIn("merge 提交 1 个不参与比对", self.module.format_evidence(r))

    def test_unknown_ref_raises_not_a_verdict(self):
        with self.assertRaises(self.module.PatchIdCompareError):
            self.module.compare(branch="no-such-branch", base="master", repo=self.repo.path)

    # ---------------- CLI ----------------

    def _run_cli(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = self.module.main(list(argv))
        return rc, out.getvalue(), err.getvalue()

    def test_cli_exit_codes_three_way(self):
        rc, out, _ = self._run_cli("--branch", "feat", "--repo", str(self.repo.path))
        self.assertEqual(rc, 1)
        self.assertIn("✗ 真需 ff", out)
        _git(self.repo.path, "cherry-pick", self.repo.sha_a, self.repo.sha_b)
        rc, out, _ = self._run_cli("--branch", "feat", "--repo", str(self.repo.path), "--json")
        self.assertEqual(rc, 0)
        self.assertIn("✓ 内容已在 master", out)
        self.assertIn('"verdict": "in_master"', out)
        rc, _, err = self._run_cli("--branch", "ghost", "--repo", str(self.repo.path))
        self.assertEqual(rc, 2)
        self.assertIn("解析失败", err)


@unittest.skipUnless(
    all(_real_commit_exists(s) for s in REAL_455_COMMITS + (REAL_341_TIP,)),
    "真实仓库夹具提交不在对象库（浅克隆／别的机器），跳过",
)
class RealRepoFixtureTests(unittest.TestCase):
    """`#455` 真实三提交 ＋ `#341` 实证靶——用本仓库对象库现取，不复制补丁。"""

    def setUp(self):
        self.module = _load()

    def test_455_three_real_commits_are_all_in_master(self):
        # 分支尖端就是第三个提交；base 用本地 master（三提交 2026-09-05 即已进 master）。
        r = self.module.compare(branch=REAL_455_COMMITS[-1], base="master", repo=REAL_REPO)
        self.assertTrue(r["all_in_master"], self.module.format_evidence(r))
        self.assertEqual(r["unique_commit_count"], 3)
        matched_short = [m["sha"][:7] for m in r["matched"]]
        self.assertEqual(matched_short, list(REAL_455_COMMITS))
        # 逐对：三个 master 侧等价提交都不是分支 SHA 本身（谱系不同才是本案）。
        for m in r["matched"]:
            self.assertNotEqual(m["sha"], m["master_sha"])
        self.assertGreater(r["hit_file_count"], 0)

    def test_341_target_is_in_master_despite_three_dot_diff(self):
        r = self.module.compare(branch=REAL_341_TIP, base="master", repo=REAL_REPO)
        self.assertTrue(r["all_in_master"], self.module.format_evidence(r))
        self.assertEqual(r["unique_commit_count"], 1)
        self.assertEqual(r["hit_file_count"], 7)


if __name__ == "__main__":
    unittest.main()
