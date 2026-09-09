"""`工具-取证件回显lint.py` 单测（队列 §一 `#530` 期望产出 ⑶）。

队列行点名的三条最小覆盖必须逐条钉死，否则这道守卫就是摆设：

1. **有回显 → 过**；
2. **无回显 → 拒**；
3. **判绿只核一族 → 拒**。

另加三类同样致命的守：
- 🔴 **fail-closed**：`门禁判据族清单.json` 与工具 docstring 不自洽时**报错退 2**，
  绝不「清单读不到就当零条清单静默放行」——那正是本项目最熟悉的失败形态
  （根 `CLAUDE.md` §5「工具静默回退」）。
- 🔴 **漂移守**：工具 docstring 长出第三族而清单没跟上时当场红。
- 🔴 **负例真的被拦下**：只跑绿不算数——门禁若因判据过宽而永远不响，等同没建。

判据文本一律用**内联的伪取证件**喂进检查函数，不依赖真实取证件的具体措辞；只有
「全库实跑应为绿」那一条用真实仓库（它本来就是在核真实状态）。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-取证件回显lint.py")


def _load():
    spec = importlib.util.spec_from_file_location("_evidence_echo_lint_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


M = _load()

#: 伪清单：形状与真实清单同族，工具名刻意换掉——用来证明判据靠的是**结构**，
#: 不是记住了「引导样板lint」这几个字。
FAKE_MANIFEST = {
    "门禁工具": [
        {
            "id": "甲乙lint",
            "路径": "0-学习与工具/工具-取证件回显lint.py",
            "别名": ["甲乙lint", "甲乙 lint"],
            "判据族": [
                {"docstring锚": "判据一", "名称": "甲族", "别名": ["判据一", "甲族"]},
                {"docstring锚": "判据二", "名称": "乙族", "别名": ["判据二", "乙族"]},
            ],
            "整套复跑命令": ["工具-甲乙lint.py"],
        }
    ]
}


def _check(md_text: str, manifest: dict | None = None, rel: str = "取证件-伪.md"):
    """把一段伪取证件全文跑完两族判据，返回违规记录列表。"""
    mani = FAKE_MANIFEST if manifest is None else manifest
    out = []
    for seg in M.split_segments(md_text):
        out.extend(M.check_segment(rel, seg, mani))
    return out


# ────────────────────────────────────────────── 判据一：断言 × 证据

class 判据一_回显配对(unittest.TestCase):

    def test_有命令有回显_过(self):
        """队列 #530 ⑶ 第一条：有回显 → 过。"""
        md = """## 三、修复与复核

`引导样板` 那处存量已清零，**✅ 已修**。

取证手段：`python -m pytest "0-学习与工具/test_工具-引导样板lint.py" -q`
⇒ **`27 passed, 4 subtests passed in 2.78s`**。
"""
        self.assertEqual(_check(md), [])

    def test_无回显_拒(self):
        """队列 #530 ⑶ 第二条：无回显 → 拒。命令有、回显没有，也算不合格。"""
        md = """## 三、修复与复核

那处存量已清零，**✅ 已修**。跑了 `python -m pytest "0-学习与工具/test_x.py" -q`。
"""
        v = _check(md)
        self.assertEqual(len(v), 1, msg=f"应报 1 处，实得 {v}")
        self.assertEqual(v[0]["判据"], "判据一")
        self.assertEqual(v[0]["缺"], ["回显"])

    def test_无命令无回显_拒且缺两样(self):
        md = """## 〇 结论速览

| job | 状态 |
|---|---|
| 平台底座 lint | ✅ **本日转绿** |
"""
        v = _check(md)
        self.assertEqual(len(v), 1, msg=f"应报 1 处，实得 {v}")
        self.assertEqual(v[0]["缺"], ["命令", "回显"])
        self.assertEqual(v[0]["段"], "〇 结论速览")

    def test_证据跨段不算数(self):
        """2026-09-06 那次失实的形状：速览段写结论、证据在别处 ⇒ 仍须报。"""
        md = """## 〇 结论速览

| job | 状态 |
|---|---|
| 平台底座 lint | ✅ **已修** |

## 七、回记

`python -m pytest "0-学习与工具/test_x.py" -q` ⇒ `27 passed`。
"""
        v = _check(md)
        self.assertEqual(len(v), 1, msg=f"应报 1 处，实得 {v}")
        self.assertEqual(v[0]["段"], "〇 结论速览")

    def test_降级措辞不算断言(self):
        """把 ✅ 改成「据称已修·未取证」是判据允许的出路，不得反过来被判违规。"""
        md = """## 三、现状

该项**据称已修**，本会话未取证，故不写 ✅。
"""
        self.assertEqual(_check(md), [])

    def test_撤回与引述不算断言(self):
        """「原记『本日转绿』失实」是撤回，不是在断言绿。"""
        md = """## 〇 结论速览

⚠️ **原记「本日转绿」失实** ⇒ 2026-09-09 回记：当日 19:02 转绿后又被打红。
"""
        self.assertEqual(_check(md), [])

    def test_围栏块内的转绿不算断言(self):
        """代码块里的 `转绿` 多半是被引用的回显原文，不是本件的断言。"""
        md = """## 三、附录

```
2026-09-06 该 job 转绿
```
"""
        self.assertEqual(_check(md), [])

    def test_散文里的git与箭头不算证据(self):
        """🔴 判据必须窄：门禁若因『每段都提到过 git』而永远不响，等同没建。"""
        md = """## 三、结论

翻了 git 历史，又看了 python 脚本 ⇒ 结论是那处 **✅ 已修**。
"""
        v = _check(md)
        self.assertEqual(len(v), 1, msg=f"散文用词被误判成了证据：{v}")
        self.assertEqual(v[0]["缺"], ["命令", "回显"])

    def test_多条断言同段_逐条报(self):
        md = """## 三、结论

第一处 **✅ 已修**。
第二处也 **✅ 已修复**。
"""
        v = _check(md)
        self.assertEqual(len(v), 2)


# ────────────────────────────────────────────── 判据二：多族判绿

class 判据二_多族复跑(unittest.TestCase):

    def test_只核一族_拒(self):
        """队列 #530 ⑶ 第三条：判绿只核一族 → 拒。"""
        md = """## 三、结论

`甲乙lint` 的判据一那处存量已清零 ⇒ **✅ 已修**。
实证：`python -m pytest "0-学习与工具/test_甲.py" -q` ⇒ `27 passed`。
"""
        v = _check(md)
        judged = [x for x in v if x["判据"] == "判据二"]
        self.assertEqual(len(judged), 1, msg=f"应报判据二 1 处，实得 {v}")
        self.assertEqual(judged[0]["覆盖"], "1/2")
        self.assertEqual(judged[0]["缺族"], ["乙族"])

    def test_两族都点到名_过(self):
        md = """## 三、结论

`甲乙lint` 的判据一与判据二双双清零 ⇒ **✅ 已修**。
实证：`python -m pytest "0-学习与工具/test_甲.py" -q` ⇒ `27 passed`。
"""
        self.assertEqual([x for x in _check(md) if x["判据"] == "判据二"], [])

    def test_跑整套命令_过(self):
        """跑脚本本体必然经过所有族，无须逐族点名。"""
        md = """## 三、结论

`甲乙lint` **✅ 已修**：`python "0-学习与工具/工具-甲乙lint.py" --enforce`
⇒ 退出码 `0`。
"""
        self.assertEqual([x for x in _check(md) if x["判据"] == "判据二"], [])

    def test_一族都没点名也没整套命令_拒(self):
        md = """## 三、结论

`甲乙lint` 那处 **✅ 已修**。
实证：`python -m pytest "0-学习与工具/test_甲.py" -q` ⇒ `27 passed`。
"""
        judged = [x for x in _check(md) if x["判据"] == "判据二"]
        self.assertEqual(len(judged), 1)
        self.assertEqual(judged[0]["覆盖"], "0/2")

    def test_没提到该工具的段不受判据二约束(self):
        md = """## 三、结论

别处那个东西 **✅ 已修**：`python "0-学习与工具/工具-别的.py"` ⇒ 退出码 `0`。
"""
        self.assertEqual([x for x in _check(md) if x["判据"] == "判据二"], [])


# ────────────────────────────────────────────── 清单自洽 / fail-closed

class 清单自洽(unittest.TestCase):

    def test_真实清单自洽(self):
        """随代码入库的真实清单必须与各工具 docstring 对齐。"""
        problems = M.校验清单自洽(M.load_manifest())
        self.assertEqual(problems, [], msg="；".join(problems))

    def test_族锚不在docstring里_报(self):
        bad = json.loads(json.dumps(FAKE_MANIFEST))
        bad["门禁工具"][0]["判据族"][1]["docstring锚"] = "判据九十九"
        bad["门禁工具"][0].pop("族命名模式", None)
        problems = M.校验清单自洽(bad)
        self.assertTrue(any("判据九十九" in p for p in problems), problems)

    def test_漂移守_docstring长出未登记的族(self):
        """工具长出第三族而清单没跟上 ⇒ 当场红，不等下一次判绿出错。"""
        bad = json.loads(json.dumps(FAKE_MANIFEST))
        bad["门禁工具"][0]["族命名模式"] = "判据[一二三四五]"
        problems = M.校验清单自洽(bad)
        # 本脚本 docstring 里只有「判据一／判据二」，故该模式不该报未登记族；
        # 反过来，把声明砍掉一族就必须报。
        self.assertEqual(problems, [], msg="；".join(problems))
        bad["门禁工具"][0]["判据族"] = bad["门禁工具"][0]["判据族"][:1]
        problems = M.校验清单自洽(bad)
        self.assertTrue(any("未登记的判据族" in p for p in problems), problems)
        self.assertTrue(any("只声明了 1 族" in p for p in problems), problems)

    def test_只守一族的工具不该登记(self):
        bad = {"门禁工具": [{
            "id": "单族", "路径": "0-学习与工具/工具-取证件回显lint.py",
            "判据族": [{"docstring锚": "判据一", "名称": "甲", "别名": []}],
            "整套复跑命令": ["x"],
        }]}
        problems = M.校验清单自洽(bad)
        self.assertTrue(any("只声明了 1 族" in p for p in problems), problems)

    def test_路径不存在_报(self):
        bad = json.loads(json.dumps(FAKE_MANIFEST))
        bad["门禁工具"][0]["路径"] = "0-学习与工具/不存在的工具.py"
        problems = M.校验清单自洽(bad)
        self.assertTrue(any("不存在" in p for p in problems), problems)

    def test_清单缺失_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "没有这个文件.json"
            with self.assertRaises(M.ManifestError):
                M.load_manifest(missing)


# ────────────────────────────────────────────── 取件范围

class 取件范围(unittest.TestCase):

    def test_文件名判据(self):
        self.assertTrue(M.是取证件("1-转型规划/0-全景路线图/取证件-x.md", "正文"))
        self.assertTrue(M.是取证件("1-转型规划/0-全景路线图/CI长期红-逐job根因取证-x.md", "正文"))
        self.assertFalse(M.是取证件("1-转型规划/0-全景路线图/卓品智能AI转型全景规划.md", "正文"))

    def test_派工载体不入守(self):
        """派单件／看护件／opener／队列真身是流水载体，另有各自的守，不重叠。"""
        for name in ("派单件-【CC】x取证-x.md", "看护件-x取证-x.md",
                     "opener集-x.md", "跨桌任务队列-机制环境.md"):
            self.assertFalse(
                M.是取证件(f"1-转型规划/0-全景路线图/{name}", "正文"), msg=name
            )

    def test_逐文件开关优先于文件名(self):
        self.assertTrue(M.是取证件(
            "1-转型规划/0-全景路线图/随便什么.md", f"正文\n{M.OPT_IN_MARKER}\n"))
        self.assertFalse(M.是取证件(
            "1-转型规划/0-全景路线图/取证件-x.md", f"正文\n{M.OPT_OUT_MARKER}\n"))


# ────────────────────────────────────────────── baseline 棘轮

class Baseline棘轮(unittest.TestCase):

    def _v(self, key, n):
        return [{"key": key, "判据": "判据一", "file": "f", "line": i,
                 "段": "s", "说明": "", "excerpt": ""} for i in range(n)]

    def test_冻结数以内不算违规(self):
        live, drift = M.apply_baseline(self._v("f::s", 2), {"f::s": 2})
        self.assertEqual(live, [])
        self.assertEqual(drift, [])

    def test_超出冻结数只报超出的那几条(self):
        live, _ = M.apply_baseline(self._v("f::s", 5), {"f::s": 2})
        self.assertEqual(len(live), 3)
        self.assertEqual(live[0]["baseline冻结数"], 2)

    def test_未冻结的段一处即违规(self):
        live, _ = M.apply_baseline(self._v("新::段", 1), {})
        self.assertEqual(len(live), 1)

    def test_修好了报漂移而不是报违规(self):
        live, drift = M.apply_baseline([], {"f::s": 3})
        self.assertEqual(live, [])
        self.assertEqual(drift, ["f::s（baseline 3 → 现 0）"])

    def test_真实baseline可解析(self):
        baseline, err = M.load_baseline()
        self.assertIsNone(err, msg=str(err))
        self.assertIsInstance(baseline, dict)

    def test_baseline缺失时不静默当空(self):
        with tempfile.TemporaryDirectory() as td:
            _, err = M.load_baseline(Path(td) / "无.json")
        self.assertIsNotNone(err)
        self.assertIn("不存在", err)


# ────────────────────────────────────────────── 退出码语义

class 退出码(unittest.TestCase):
    """门禁的价值全在退出码上——`--enforce` 有违规却退 0，等同没建。"""

    坏件 = [(
        "1-转型规划/0-全景路线图/取证件-伪-无回显.md",
        "## 三、结论\n\n那处 **✅ 已修**。\n",
    )]

    def _run(self, argv, files):
        真 = M.guarded_files
        M.guarded_files = lambda: files
        try:
            return M.main(argv)
        finally:
            M.guarded_files = 真

    def test_告警模式有违规也退0(self):
        self.assertEqual(self._run([], self.坏件), 0)

    def test_enforce有违规退1(self):
        self.assertEqual(self._run(["--enforce"], self.坏件), 1)

    def test_enforce无违规退0(self):
        self.assertEqual(self._run(["--enforce"], []), 0)

    def test_清单不自洽退2且不是1(self):
        """fail-closed 与「有违规」必须是两个不同的码，否则分不清判据坏了还是内容坏了。"""
        真 = M.load_manifest
        M.load_manifest = lambda *a, **k: {"门禁工具": []}
        try:
            self.assertEqual(self._run(["--enforce"], []), 2)
        finally:
            M.load_manifest = 真


# ────────────────────────────────────────────── 真实仓库实跑

class 真实仓库现状(unittest.TestCase):

    def test_全库实跑为绿(self):
        """上线当日存量已实测为 0（见 baseline 文件 `冻结时实测`），故实跑必须绿。"""
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--enforce"],
            cwd=str(M.REPO_ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        self.assertEqual(
            proc.returncode, 0,
            msg=f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}",
        )

    def test_json输出可解析(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"],
            cwd=str(M.REPO_ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        payload = json.loads(proc.stdout)
        self.assertGreaterEqual(payload["扫描件数"], 1)
        self.assertGreaterEqual(payload["清单工具数"], 1)

    def test_emit_baseline输出可解析且不写盘(self):
        before = M.BASELINE_PATH.read_bytes()
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--emit-baseline"],
            cwd=str(M.REPO_ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("命中", json.loads(proc.stdout))
        self.assertEqual(M.BASELINE_PATH.read_bytes(), before,
                         msg="--emit-baseline 刻意只往 stdout 打，不得写盘")

    def test_复刻2026_09_06原文_两族齐报(self):
        """🔴 本门禁的存在理由：拿**真实历史原文**回放，必须当场两族齐报。

        原文取自 `CI长期红-逐job根因取证-2026-09-06.md` §〇 更正注里逐字保留的那一行
        （2026-09-09 `#520`／`OP-0909-T` 回记时保留下来的）。它当年只有结论、没有回显，
        且只核了判据二就判绿——**这两半正是本脚本两族判据各自要拦的东西**。用真实清单
        （不是伪清单）跑，才证明清单里的 `引导样板lint` 那条是活的。
        """
        原文 = (
            "## 〇 结论速览\n\n"
            "| job | 状态 | 根因归类 | 谁能关掉它 |\n"
            "|---|---|---|---|\n"
            "| 平台底座引导样板 lint | ✅ **本日转绿** | 真实存量（#354 判据二最后 1 处）"
            " | 已修，commit 3c091c9 已在 master |\n"
        )
        mani = M.load_manifest()
        got = []
        for seg in M.split_segments(原文):
            got.extend(M.check_segment(
                "1-转型规划/0-全景路线图/伪-CI长期红-逐job根因取证.md", seg, mani))
        判据 = sorted(v["判据"] for v in got)
        self.assertEqual(判据, ["判据一", "判据二"], msg=f"实得 {got}")
        判据二 = next(v for v in got if v["判据"] == "判据二")
        self.assertEqual(判据二["工具"], "引导样板lint")
        self.assertEqual(判据二["覆盖"], "1/2")

    def test_实证件本身仍受守且为绿(self):
        """`#530` 的实证件必须真的在受守集合里——不然这道门禁守了个空。"""
        rels = [rel for rel, _ in M.guarded_files()]
        self.assertIn(
            "1-转型规划/0-全景路线图/CI长期红-逐job根因取证-2026-09-06.md", rels,
            msg=f"受守集合：{rels}",
        )


if __name__ == "__main__":
    unittest.main()
