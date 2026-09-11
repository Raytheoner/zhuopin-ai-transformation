"""第 16 类常驻告警——未并入分支超阈值（队列 §一 `#553` ⑶，`OP-0911-G`）单测。

两层各测各的：
- **分类器** `工具-未并入分支分类.py`：每个用例起一个临时 git 仓库，真跑 git（patch-id／
  cherry-pick／for-each-ref），核 A／B／C 判定与 `first_unmerged_date`。
- **sweep 第 16 类** `_check_unmerged_branch_backlog`：进程内 monkeypatch 子进程调用与发送层，
  核阈值边界（B 4/5、天数 6/7）、A 类不计、指纹静默、dry-run 不写不推、判据不可用不判零。
- **端到端**一例：临时仓库里放真分类器脚本，sweep 子进程真调，5 条 B 分支 10 天 ⇒ 触发。

🔴 独立成文件（不并入 `test_工具-落库sweep.py`）：该文件 471 条超单次工具上限（`#550`），
本类只需跑本文件。变异 2 组的验证记录见队列 `#553` 收工段（把 patch-id 比对换成 merge-base 判
⇒ `test_A类_patchid等价_即使master后来改掉那行` 转红；去掉 7 天判 ⇒ `test_天数边界_6天不触发` 转红）。
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SWEEP_SCRIPT = HERE / "工具-落库sweep.py"
TRIAGE_SCRIPT = HERE / "工具-未并入分支分类.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sweep = _load("commit_sweep_for_unmerged_tests", SWEEP_SCRIPT)
triage = _load("unmerged_branch_triage", TRIAGE_SCRIPT)


# ------------------------------------------------------------------ 夹具


class GitRepoFixture:
    """最小 git 仓库：master 一个初始提交；`branch()` 从 master 起分支并写文件提交。"""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self.git("init", "-q", "-b", "master")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.git("config", "commit.gpgsign", "false")
        (self.repo / "base.txt").write_text("base\n", encoding="utf-8")
        self.commit("init")

    def cleanup(self):
        self._tmp.cleanup()

    def git(self, *args, env_extra=None, check=True) -> str:
        env = dict(os.environ)
        if env_extra:
            env.update(env_extra)
        r = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=self.repo,
                           capture_output=True, text=True, encoding="utf-8", env=env)
        if check and r.returncode != 0:
            raise AssertionError(f"git {' '.join(args)} rc={r.returncode}: {r.stderr}")
        return r.stdout

    def write(self, rel: str, text: str):
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def commit(self, msg: str, days_ago: int = 0, allow_empty=False) -> str:
        stamp = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%S+0000")
        self.git("add", "-A")
        args = ["commit", "-q", "-m", msg]
        if allow_empty:
            args.append("--allow-empty")
        self.git(*args, env_extra={"GIT_COMMITTER_DATE": stamp, "GIT_AUTHOR_DATE": stamp})
        return self.git("rev-parse", "HEAD").strip()

    def checkout(self, ref: str, new=False):
        self.git("checkout", "-q", *(["-b"] if new else []), ref)

    def branch_with_file(self, name: str, rel: str, text: str, days_ago: int = 0, msg=None) -> str:
        self.checkout("master")
        self.checkout(name, new=True)
        self.write(rel, text)
        sha = self.commit(msg or f"{name}: {rel}", days_ago=days_ago)
        self.checkout("master")
        return sha

    def classify(self) -> dict:
        return triage.classify(repo=self.repo, base="master")

    def cat(self, result: dict) -> dict[str, str]:
        return {r["name"]: r["category"] for r in result["branches"]}


class TriageClassifierTests(unittest.TestCase):
    """分类器判据：A 三层／C 两条／B；空提交；merge-base 与 patch-id 的分野。"""

    def setUp(self):
        self.fx = GitRepoFixture()

    def tearDown(self):
        self.fx.cleanup()

    def test_零候选(self):
        res = self.fx.classify()
        self.assertEqual(res["total"], 0)
        self.assertEqual(res["counts"], {"A": 0, "B": 0, "C": 0})
        self.assertEqual(res["b_branches"], [])

    def test_B类_真未落地(self):
        sha = self.fx.branch_with_file("claude/op-b1", "feat.txt", "brand new\n", days_ago=3)
        res = self.fx.classify()
        self.assertEqual(self.fx.cat(res), {"claude/op-b1": "B"})
        b = res["b_branches"][0]
        self.assertEqual(b["name"], "claude/op-b1")
        self.assertEqual(b["first_unmerged_date"][:10],
                         (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%d"))
        self.assertEqual(res["branches"][0]["first_unmerged_commit"], sha)

    def test_A类_patchid等价不计入B(self):
        """分支提交被 cherry-pick 进 master（SHA 不同、merge-base 判「未并入」），内容已在。

        分支图上它永远「未并入」——这正是 64 条假阴性的形态（`#455`／`#341`）。本例由
        层① patch-id 命中；即便层①被拿掉，层②（文件逐字节相同）仍会救回，所以变异 1 的
        精确靶是下一例（master 后来改掉那行、层②③都救不回）。
        """
        sha = self.fx.branch_with_file("claude/op-a1", "feat.txt", "same change\n")
        self.fx.git("cherry-pick", sha)  # master 上另行一份等价提交
        # merge-base 视角：分支尖端不是 master 祖先
        r = self.fx.git("merge-base", "--is-ancestor", "claude/op-a1", "master", check=False)
        self.assertEqual(r, "")  # 只为可读：rc 非 0 由下面的候选列表体现
        self.assertEqual([c["name"] for c in triage.list_candidates(self.fx.repo, "master")], ["claude/op-a1"])
        res = self.fx.classify()
        self.assertEqual(self.fx.cat(res), {"claude/op-a1": "A"})
        self.assertEqual(res["b_branches"], [])
        self.assertIn("patch-id", res["branches"][0]["reason"])

    def test_A类_patchid等价_即使master后来改掉那行(self):
        """cherry-pick 进 master 后，master 又把那一行改掉 ⇒ 文件级／行级都对不上，**只有 patch-id 能救**。

        🔴 变异 1 的靶（精确）：把 patch-id 比对拿掉（凡 `base..tip` 非 merge 提交一律当未落地，
        即 merge-base 视角），本例转红——它会被判成 B，正是 `#341`「三点 diff +1452 行未合入」
        那种误判：内容早已进 master，只是后来在 master 上继续演化了。
        """
        sha = self.fx.branch_with_file("claude/op-a4", "feat.txt", "alpha\n")
        self.fx.git("cherry-pick", sha)
        self.fx.write("feat.txt", "alpha v2 (master rewrote it)\n")
        self.fx.commit("master evolved the picked line")
        res = self.fx.classify()
        self.assertEqual(self.fx.cat(res), {"claude/op-a4": "A"})
        self.assertEqual(res["branches"][0]["cherry_plus"], 0)
        self.assertEqual(res["branches"][0]["cherry_minus"], 1)
        self.assertEqual(res["b_branches"], [])

    def test_A类_文件级_squash后合入(self):
        """两个分支提交被 squash 成 master 一个提交（patch-id 对不上）⇒ 触碰文件逐字节相同 ⇒ A。"""
        self.fx.checkout("claude/op-a2", new=True)
        self.fx.write("feat.txt", "line1\n")
        self.fx.commit("part 1")
        self.fx.write("feat.txt", "line1\nline2\n")
        self.fx.commit("part 2")
        self.fx.checkout("master")
        self.fx.write("feat.txt", "line1\nline2\n")
        self.fx.commit("squashed")
        res = self.fx.classify()
        self.assertEqual(self.fx.cat(res), {"claude/op-a2": "A"})
        self.assertIn("逐字节相同", res["branches"][0]["reason"])

    def test_A类_行级_文件后来在master继续改(self):
        """分支新增的每一行都在 master 同文件里，但 master 又多改了别的 ⇒ A（#482 行级口径）。"""
        self.fx.branch_with_file("claude/op-a3", "feat.txt", "alpha\n")
        self.fx.write("feat.txt", "alpha\nbeta (master went on)\n")
        self.fx.commit("master reworked")
        res = self.fx.classify()
        self.assertEqual(self.fx.cat(res), {"claude/op-a3": "A"})
        self.assertIn("每一非空行", res["branches"][0]["reason"])

    def test_C类_后继分支祖先(self):
        self.fx.checkout("claude/op-c1", new=True)
        self.fx.write("feat.txt", "step 1\n")
        self.fx.commit("step 1")
        self.fx.checkout("claude/op-c1-next", new=True)
        self.fx.write("feat.txt", "step 1\nstep 2\n")
        self.fx.commit("step 2")
        self.fx.checkout("master")
        res = self.fx.classify()
        cats = self.fx.cat(res)
        self.assertEqual(cats["claude/op-c1"], "C")
        self.assertEqual(cats["claude/op-c1-next"], "B")
        self.assertEqual([b["name"] for b in res["b_branches"]], ["claude/op-c1-next"])

    def test_C类_只剩过程状态文件(self):
        self.fx.branch_with_file("claude/op-c2", "reports/sweep-x.json", "{\"stale\": 1}\n")
        res = self.fx.classify()
        self.assertEqual(self.fx.cat(res), {"claude/op-c2": "C"})
        self.assertIn("过程状态文件", res["branches"][0]["reason"])

    def test_空提交不算未落地(self):
        self.fx.checkout("claude/op-e1", new=True)
        self.fx.commit("empty", allow_empty=True)
        self.fx.checkout("master")
        res = self.fx.classify()
        self.assertEqual(self.fx.cat(res), {"claude/op-e1": "A"})
        self.assertEqual(res["branches"][0]["empty_commits"], 1)
        self.assertEqual(res["branches"][0]["cherry_plus"], 0)

    def test_非claude前缀不入候选(self):
        self.fx.branch_with_file("feature/x", "feat.txt", "x\n")
        self.fx.branch_with_file("claude/y", "feat2.txt", "y\n")
        self.assertEqual([c["name"] for c in triage.list_candidates(self.fx.repo, "master")], ["claude/y"])

    def test_缓存不改结果且只留本轮SHA(self):
        self.fx.branch_with_file("claude/op-b1", "feat.txt", "brand new\n")
        cache = self.fx.repo / "reports" / "cache.json"
        r1 = triage.classify(repo=self.fx.repo, base="master", cache_path=cache)
        self.assertTrue(cache.exists())
        data = json.loads(cache.read_text(encoding="utf-8"))
        self.assertEqual(data["version"], triage.PATCH_ID_CACHE_VERSION)
        r2 = triage.classify(repo=self.fx.repo, base="master", cache_path=cache)
        self.assertEqual(self.fx.cat(r1), self.fx.cat(r2))
        self.assertEqual(set(data["commits"]), {r1["branches"][0]["first_unmerged_commit"]})

    def test_只读_status前后不变(self):
        self.fx.branch_with_file("claude/op-b1", "feat.txt", "brand new\n")
        before = self.fx.git("status", "--porcelain")
        self.fx.classify()
        self.assertEqual(self.fx.git("status", "--porcelain"), before)
        self.assertEqual(self.fx.git("for-each-ref", "--format=%(refname)").count("\n"), 2)


# ------------------------------------------------------------------ sweep 第 16 类


def _payload(b_days: list[int], a: int = 0, c: int = 0, names=None) -> dict:
    now = datetime.now(timezone.utc)
    bs = []
    for i, d in enumerate(b_days):
        bs.append({"name": (names[i] if names else f"claude/op-b{i}"), "tip": f"{i:040x}",
                   "first_unmerged_date": (now - timedelta(days=d, minutes=5)).isoformat(),
                   "sides": ["local"], "reason": "x"})
    return {"base": "master", "base_sha": "0" * 40, "total": len(bs) + a + c,
            "counts": {"A": a, "B": len(bs), "C": c}, "branches": [], "b_branches": bs}


class UnmergedBranchAlertTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        (self.repo / "reports").mkdir()
        self.sent: list[str] = []
        self._orig = (sweep._load_webhook_url, sweep._send_wecom_markdown, sweep._run_unmerged_branch_json)
        sweep._load_webhook_url = lambda repo_root: "https://example.invalid/hook"
        sweep._send_wecom_markdown = lambda url, text: self.sent.append(text)
        self.payload = _payload([])
        sweep._run_unmerged_branch_json = lambda repo_root: (self.payload, None)

    def tearDown(self):
        sweep._load_webhook_url, sweep._send_wecom_markdown, sweep._run_unmerged_branch_json = self._orig
        self._tmp.cleanup()

    def _run(self, dry_run=False) -> str:
        log: list[str] = []
        sweep._check_unmerged_branch_backlog(self.repo, log, dry_run=dry_run)
        return "\n".join(log)

    def _state(self) -> dict:
        p = self.repo / sweep.UNMERGED_BRANCH_STATE_REL
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    # ---- 接线与回显

    def test_已接入主流程且在dry_run块之外(self):
        src = SWEEP_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("_check_unmerged_branch_backlog(repo_root, log, dry_run=args.dry_run)", src)

    def test_阈值常量为他答2a所定(self):
        self.assertEqual(sweep.UNMERGED_BRANCH_B_MIN_COUNT, 5)
        self.assertEqual(sweep.UNMERGED_BRANCH_B_MIN_AGE_DAYS, 7)

    def test_零命中也回显(self):
        text = self._run()
        self.assertIn("第 16 类", text)
        self.assertIn("B 0（真未落地）", text)
        self.assertIn("未触发", text)
        self.assertEqual(self.sent, [])

    # ---- 阈值边界

    def test_条数边界_4条不触发(self):
        self.payload = _payload([30, 30, 30, 30])
        text = self._run()
        self.assertIn("未触发", text)
        self.assertEqual(self.sent, [])
        self.assertEqual(self._state(), {})

    def test_条数边界_5条触发(self):
        self.payload = _payload([30, 30, 30, 30, 30])
        text = self._run()
        self.assertIn("触发告警", text)
        self.assertEqual(len(self.sent), 1)
        self.assertIn("B 类（真未落地）**5 条**", self.sent[0])
        self.assertIn("最老 **30 天**", self.sent[0])
        self.assertEqual(len(self._state()), 1)

    def test_天数边界_6天不触发(self):
        """🔴 变异 2 的靶：去掉 7 天判，本例转红（5 条、最老 6 天本不该响）。"""
        self.payload = _payload([6, 6, 6, 6, 6])
        text = self._run()
        self.assertIn("B 最老 6 天", text)
        self.assertIn("未触发", text)
        self.assertEqual(self.sent, [])

    def test_天数边界_7天触发(self):
        self.payload = _payload([7, 1, 1, 1, 1])
        text = self._run()
        self.assertIn("B 最老 7 天", text)
        self.assertIn("触发告警", text)
        self.assertEqual(len(self.sent), 1)

    def test_最老按最老一条而非首条(self):
        ev = sweep._evaluate_unmerged_branch_backlog(_payload([1, 40, 3]))
        self.assertEqual(ev["oldest_days"], 40)
        self.assertEqual(ev["items"][0]["days"], 40)

    # ---- A／C 不计

    def test_A类C类不计入阈值只附计数(self):
        self.payload = _payload([30, 30, 30, 30], a=64, c=4)  # B 只有 4
        text = self._run()
        self.assertIn("A 64（内容已在 master）", text)
        self.assertIn("C 4（该删）", text)
        self.assertIn("未触发", text)
        self.assertEqual(self.sent, [])
        self.payload = _payload([30] * 5, a=64, c=4)
        self._run()
        self.assertIn("A 类（内容已在 master）64 条／C 类（该删）4 条不计入阈值", self.sent[0])

    # ---- 指纹静默

    def test_指纹不变即静默_变化即换key(self):
        self.payload = _payload([30] * 5, names=[f"claude/x{i}" for i in range(5)])
        self._run()
        self.assertEqual(len(self.sent), 1)
        fp1 = next(iter(self._state()))
        self._run()  # 同一集合、24 h 内：不再推
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(list(self._state()), [fp1])
        # 天数变了但集合没变 ⇒ 指纹不变
        self.payload = _payload([31] * 5, names=[f"claude/x{i}" for i in range(5)])
        self._run()
        self.assertEqual(len(self.sent), 1)
        # 集合变了（多一条）⇒ 旧 key 解除、新 key 告警
        self.payload = _payload([31] * 6, names=[f"claude/x{i}" for i in range(6)])
        self._run()
        self.assertEqual(len(self.sent), 3)
        self.assertIn("解除／指纹变化", self.sent[1])
        self.assertIn(fp1, self.sent[1])
        self.assertIn("**6 条**", self.sent[2])
        self.assertNotIn(fp1, self._state())

    def test_回落阈下即解除(self):
        self.payload = _payload([30] * 5)
        self._run()
        self.payload = _payload([30] * 4)
        text = self._run()
        self.assertEqual(len(self.sent), 2)
        self.assertIn("解除", self.sent[1])
        self.assertIn("解除通知", text)
        self.assertEqual(self._state(), {})

    # ---- dry-run／不可用

    def test_dry_run_回显但不写状态不推送(self):
        self.payload = _payload([30] * 5)
        text = self._run(dry_run=True)
        self.assertIn("触发告警", text)
        self.assertIn("dry-run", text)
        self.assertIn("| 🌿 落库sweep：**未并入分支超阈值**", text)
        self.assertEqual(self.sent, [])
        self.assertEqual(self._state(), {})

    def test_判据不可用不判零(self):
        sweep._run_unmerged_branch_json = lambda repo_root: (None, "子进程炸了")
        text = self._run()
        self.assertIn("判据不可用", text)
        self.assertIn("不据此判为零未落地", text)
        self.assertEqual(len(self.sent), 1)
        self.assertIn("这一轮什么也没量", self.sent[0])
        # 恢复后自动解除
        sweep._run_unmerged_branch_json = lambda repo_root: (_payload([]), None)
        self._run()
        self.assertEqual(len(self.sent), 2)
        self.assertIn("已恢复可用", self.sent[1])

    def test_告警正文列最老三条(self):
        ev = sweep._evaluate_unmerged_branch_backlog(
            _payload([50, 40, 30, 20, 10], names=[f"claude/n{d}" for d in (50, 40, 30, 20, 10)]))
        text = sweep._render_unmerged_branch_alert(ev)
        self.assertIn("`claude/n50`", text)
        self.assertIn("`claude/n40`", text)
        self.assertIn("`claude/n30`", text)
        self.assertNotIn("`claude/n20`", text)
        self.assertIn("不自动合并、不自动删除", text)


class UnmergedBranchEndToEndTests(unittest.TestCase):
    """临时仓库里放真分类器，sweep 子进程真调：5 条 B 分支各 10 天 ⇒ 触发；含 1 条 A 不计。"""

    def setUp(self):
        self.fx = GitRepoFixture()
        (self.fx.repo / "0-学习与工具").mkdir()
        shutil.copy(TRIAGE_SCRIPT, self.fx.repo / sweep.UNMERGED_BRANCH_SCRIPT_REL)
        self.fx.git("add", "-A")
        self.fx.commit("tooling")
        self.sent: list[str] = []
        self._orig = (sweep._load_webhook_url, sweep._send_wecom_markdown)
        sweep._load_webhook_url = lambda repo_root: "https://example.invalid/hook"
        sweep._send_wecom_markdown = lambda url, text: self.sent.append(text)

    def tearDown(self):
        sweep._load_webhook_url, sweep._send_wecom_markdown = self._orig
        self.fx.cleanup()

    def test_端到端_5条B各10天触发_A不计(self):
        for i in range(5):
            self.fx.branch_with_file(f"claude/op-b{i}", f"f{i}.txt", f"unique {i}\n", days_ago=10)
        sha = self.fx.branch_with_file("claude/op-a", "fa.txt", "picked\n", days_ago=30)
        self.fx.git("cherry-pick", sha)
        log: list[str] = []
        sweep._check_unmerged_branch_backlog(self.fx.repo, log)
        text = "\n".join(log)
        self.assertIn("A 1（内容已在 master）／B 5（真未落地）／C 0（该删）", text)
        self.assertIn("B 最老 10 天", text)
        self.assertIn("触发告警", text)
        self.assertEqual(len(self.sent), 1)
        self.assertTrue((self.fx.repo / sweep.UNMERGED_BRANCH_PATCHID_CACHE_REL).exists())
        self.assertTrue((self.fx.repo / sweep.UNMERGED_BRANCH_STATE_REL).exists())


if __name__ == "__main__":
    unittest.main()
