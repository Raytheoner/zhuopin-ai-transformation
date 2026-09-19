# -*- coding: utf-8 -*-
"""`工具-main-leak回放.py` 单测（队列 §一 #611 / #454 同批，2026-09-19 OP-0919-K）。"""
import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import unittest

TOOL = pathlib.Path(__file__).resolve().parent / "工具-main-leak回放.py"


def _load():
    spec = importlib.util.spec_from_file_location("main_leak_replay", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GATE_SNIPPET = """
        $leakLines = @($newLeakLines | Where-Object {
            $lp = $_.Substring(3)
            -not ($lp -eq 'reports' -or $lp -like 'reports/*' -or $lp -eq 'a/b/pending-ff.jsonl')
        })
"""

PATCH_NEW = """# 队列 #600 ⑷ 收工核验
----- 已跟踪文件改动：a/b/pending-ff.jsonl -----
diff --git a/x b/x
+这一行是正文，回放器不得读它，也不得把它当成路径
----- 已跟踪文件改动：a/b/queue.md -----
diff --git a/y b/y
"""

PATCH_LEGACY = """diff --git a/z b/z
index 000..111 100644
"""


class WhitelistIsReadFromGateScriptTests(unittest.TestCase):
    """🔴 白名单判据只此一份：现取 `.ps1`，解析不到即 fail-loud，不退回硬编码。"""

    def setUp(self):
        self.mod = _load()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)
        (self.root / "0-学习与工具").mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def _gate(self, body: str) -> pathlib.Path:
        p = self.root / "0-学习与工具" / "工具-opener批处理执行v2.ps1"
        p.write_text(body, encoding="utf-8")
        return p

    def test_从_ps1_现取精确项与_glob_项(self):
        exact, globs = self.mod.read_gate_whitelist(self._gate(GATE_SNIPPET))
        self.assertEqual(sorted(exact), ["a/b/pending-ff.jsonl", "reports"])
        self.assertEqual(globs, ["reports/*"])

    def test_解析不到白名单块即_fail_loud_不退回默认值(self):
        """闸改了写法而回放器没跟上时，必须当场炸——退回硬编码会让回放报
        「全过」而生产照旧 FAIL，那是「只会报成功的守卫」。"""
        with self.assertRaises(SystemExit):
            self.mod.read_gate_whitelist(self._gate("# 这里没有白名单块"))

    def test_判据正本文件不存在也_fail_loud(self):
        with self.assertRaises(SystemExit):
            self.mod.read_gate_whitelist(self.root / "0-学习与工具" / "不存在.ps1")


class LeakListParsingTests(unittest.TestCase):
    """🔑 判 FAIL 只需要文件名——本类钉住「只读表头、不读正文」。"""

    def setUp(self):
        self.mod = _load()
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _patch(self, name: str, body: str) -> pathlib.Path:
        p = self.dir / name
        p.write_text(body, encoding="utf-8")
        return p

    def test_只取表头行的路径_不把_diff_正文当路径(self):
        leaks, legacy = self.mod.leaks_of(self._patch("x-main-leak.patch", PATCH_NEW))
        self.assertEqual(leaks, ["a/b/pending-ff.jsonl", "a/b/queue.md"])
        self.assertFalse(legacy)
        self.assertFalse(any("这一行是正文" in x for x in leaks))

    def test_老格式补丁被标出而不是默默算成_OK(self):
        leaks, legacy = self.mod.leaks_of(self._patch("y-main-leak.patch", PATCH_LEGACY))
        self.assertEqual(leaks, [])
        self.assertTrue(legacy, "无表头的老格式必须被标出，不得默默计成通过")


class PredicateTests(unittest.TestCase):
    def setUp(self):
        self.mod = _load()

    def test_精确项与_glob_项都生效(self):
        allowed = self.mod.make_predicate(["reports"], ["reports/*"], [])
        self.assertTrue(allowed("reports"))
        self.assertTrue(allowed("reports/a/b.txt"))
        self.assertFalse(allowed("1-转型规划/x.md"))

    def test_extra_是候选修法的追加白名单(self):
        allowed = self.mod.make_predicate([], [], ["1-转型规划/*/跨桌任务队列-*.md"])
        self.assertTrue(allowed("1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md"))
        self.assertFalse(allowed("1-转型规划/0-全景路线图/取证件-随便起的名字.md"))


class CliSmokeTests(unittest.TestCase):
    def test_对真实仓库跑一遍_退出码与输出体积都合规(self):
        """回放器自己不许变成新的 token 黑洞：全量逐条表须远小于单份补丁。"""
        r = subprocess.run([sys.executable, str(TOOL)], capture_output=True, text=True,
                           encoding="utf-8", cwd=str(TOOL.resolve().parent.parent))
        self.assertIn(r.returncode, (0, 1), r.stdout + r.stderr)
        self.assertIn("有效分母", r.stdout)
        self.assertLess(len(r.stdout.encode("utf-8")), 8192,
                        "全量回放输出应 <8 KB——它存在的理由就是替代 cat 补丁正文")


if __name__ == "__main__":
    unittest.main()
