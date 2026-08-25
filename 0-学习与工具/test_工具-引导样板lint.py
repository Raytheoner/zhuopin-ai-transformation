"""工具-引导样板lint.py 单测（队列 #345 第二步 / 变更包 platform-bootstrap-ensure-paths 决策点 4）。

白盒方式：直接调用 `check_file(rel_path, text)`，喂**真实存在过的四种形态原文**，不触碰
真实仓库文件。

🔴 本文件存在的理由：一道从不报警的门禁与没有门禁等价，而"存量已清零"恰恰意味着对真实
仓库跑一遍**永远是绿的**、证明不了它还认得违规。故这里逐形态复现——尤其 A 形态，那是
2026-08-18 把 8091／8093 打挂、且 SC2 出生即抄到的那一份。
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-引导样板lint.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("_stub_lint_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M = _load_module()

# ── 四种真实形态原文（节选自 2026-08-18 收拢前的生产文件）────────────────────
FORM_A = '''\
_HERE = Path(__file__).resolve()
for _p in (_HERE, *_HERE.parents):
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        for _entry in (_p / "5-平台底座" / "zhuopin_platform", _HERE.parent.parent):
            if str(_entry) not in sys.path:
                sys.path.insert(0, str(_entry))
        break
else:
    raise RuntimeError(f"未找到仓库根标记 5-平台底座/zhuopin_platform（从 {_HERE} 向上查找）")
'''

FORM_B = '''\
_HERE = Path(__file__).resolve()
for _p in (_HERE, *_HERE.parents):
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        for _entry in (_p / "5-平台底座" / "zhuopin_platform", _HERE.parent.parent):
            if str(_entry) not in sys.path:
                sys.path.insert(0, str(_entry))
        break
else:
    if str(_HERE.parent.parent) not in sys.path:
        sys.path.insert(0, str(_HERE.parent.parent))
    from importlib.util import find_spec
    if find_spec("zhuopin_platform") is None:
        raise RuntimeError("既未找到仓库根标记……")
'''

FORM_C = '''\
_HERE = Path(__file__).resolve()
_entries = [_HERE.parent.parent]
for _p in (_HERE, *_HERE.parents):
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        _entries.insert(0, _p / "5-平台底座" / "zhuopin_platform")
        break
else:
    _flat = _HERE.parent.parent.parent / "zhuopin_platform"
    if _flat.is_dir():
        _entries.insert(0, _flat)
for _entry in _entries:
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))
'''

FORM_D = '''\
_HERE = Path(__file__).resolve()
for _p in (_HERE, *_HERE.parents):
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        for _entry in (_p / "5-平台底座" / "zhuopin_platform", _HERE.parent.parent):
            if str(_entry) not in sys.path:
                sys.path.insert(0, str(_entry))
        break
'''

STUB_OK = '''\
_HERE = Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        sys.path.insert(0, str(_p / "5-平台底座" / "zhuopin_platform"))
        break
from zhuopin_platform.bootstrap import ensure_paths  # noqa: E402
ensure_paths(__file__, _HERE.parent.parent)  # noqa: E402
'''

STUB_OK_STRICT = STUB_OK.replace(
    "ensure_paths(__file__, _HERE.parent.parent)",
    "ensure_paths(__file__, _HERE.parent.parent, strict=True)")

# 固定层数算路径 + 刻意的兜底桩：另一族，**不在**本门禁范围（队列 #313④⑤）
FIXED_DEPTH_WITH_FALLBACK = '''\
_QUEUE_TABLE_SEARCH_ROOT = Path(__file__).resolve().parents[1]
_PLATFORM_PATH = _QUEUE_TABLE_SEARCH_ROOT / "5-平台底座" / "zhuopin_platform"
if _PLATFORM_PATH.is_dir():
    if str(_PLATFORM_PATH) not in sys.path:
        sys.path.insert(0, str(_PLATFORM_PATH))
    from zhuopin_platform.shared_tools import queue_table  # noqa: E402
else:
    class queue_table:  # type: ignore[no-redef]
        QUEUE_PATH_REL = "1-转型规划/0-全景路线图/跨桌任务队列.md"
'''


class 违规形态必须被抓到(unittest.TestCase):
    def test_A形态_无条件raise(self):
        """2026-08-18 打挂 8091／8093、且 SC2 出生即抄到的那一份。"""
        problems = M.check_file("4-数字员工/某域/某场景/tests/conftest.py", FORM_A)
        self.assertTrue(problems)
        self.assertTrue(any("ensure_paths" in p for p in problems))
        self.assertTrue(any("raise" in p for p in problems))

    def test_B形态_find_spec回退(self):
        problems = M.check_file("4-数字员工/某域/某场景/pkg/run.py", FORM_B)
        self.assertTrue(problems)
        self.assertTrue(any("find_spec" in p for p in problems))

    def test_C形态_显式探测兄弟目录(self):
        problems = M.check_file("4-数字员工/某域/某场景/scripts/run_web.py", FORM_C)
        self.assertTrue(problems)

    def test_D形态_无else静默跳过(self):
        """最隐蔽的一种：不报错，只是把真实失败点推迟到更难归因处。"""
        problems = M.check_file("4-数字员工/某域/某场景/scripts/x.py", FORM_D)
        self.assertTrue(problems)
        self.assertTrue(any("旧遍历写法" in p for p in problems))

    def test_四种形态无一漏网(self):
        for name, text in (("A", FORM_A), ("B", FORM_B), ("C", FORM_C), ("D", FORM_D)):
            with self.subTest(形态=name):
                self.assertTrue(M.check_file(f"4-数字员工/x/y/{name}.py", text))


class 合规形态不得误报(unittest.TestCase):
    def test_stub非strict(self):
        self.assertEqual(M.check_file("4-数字员工/某域/某场景/scripts/run.py", STUB_OK), [])

    def test_stub_strict(self):
        self.assertEqual(
            M.check_file("4-数字员工/某域/某场景/tests/conftest.py", STUB_OK_STRICT), [])

    def test_固定层数算路径带兜底桩_不属本门禁范围(self):
        """队列 #313④⑤ 刻意设计的隔离环境兜底桩：不做祖先搜索，并进来会毁掉那个语义。"""
        self.assertEqual(
            M.check_file("0-学习与工具/工具-落库sweep.py", FIXED_DEPTH_WITH_FALLBACK), [])

    def test_无引导块的普通文件(self):
        self.assertEqual(M.check_file("x/y.py", "import os\nprint(1)\n"), [])

    def test_bootstrap自身豁免(self):
        """判断的唯一合法归宿——它必然含 raise/find_spec，不豁免则门禁自相矛盾。"""
        text = FORM_B + '\nraise RuntimeError("x")\n'
        self.assertEqual(
            M.check_file("5-平台底座/zhuopin_platform/zhuopin_platform/bootstrap.py", text), [])


# ── 判据二 · `.env` 凭据锚定（队列 #354，变更包 env-anchor-collapse tasks 3.4）────
#
# 🔴 同一条理由：一道从不报警的门禁与没有门禁等价。这里逐形态复现 A 家族与 B 家族的
# **真实原文**，尤其那两条「结论对、理由碰巧成立」的变体——它们最像合规代码。

# A 家族共同语义（9 份手抄副本的公因式，`run_baoguan_web.py` 是上游）
ENV_FORM_A = '''\
def _find_env() -> Path | None:
    """从本脚本向上逐级查找最近的 `.env`（布局无关）。"""
    here = Path(__file__).resolve()
    for d in (here.parent, *here.parents):
        cand = d / ".env"
        if cand.exists():
            return cand
    return None
'''

# 内联无函数变体（`run_sc2.py`）
ENV_FORM_INLINE = '''\
def load_env() -> None:
    here = Path(__file__).resolve()
    for d in (here.parent, *here.parents):
        cand = d / ".env"
        if not cand.exists():
            continue
        for line in cand.read_text(encoding="utf-8-sig").splitlines():
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
        return
'''

# `os.path` 变体（`serve.py` 修复前原文）
ENV_FORM_OSPATH = '''\
def _find_env():
    here = ROOT
    while True:
        cand = os.path.join(here, ".env")
        if os.path.isfile(cand):
            return cand
        parent = os.path.dirname(here)
        if parent == here:
            return None
        here = parent
'''

# 2026-08-25 才出生的第三变体（`compare_kit_date_*.py`）——**设计清单里没有它**，
# 是这道门禁自己扫出来的。它带着一段看起来很有道理的注释，最难被人眼判违规。
ENV_FORM_NEWEST = '''\
def _find_dotenv() -> Path | None:
    """自下而上找第一个真实存在的 `.env`（worktree 里没有，会一路走到主工作区）。"""
    for p in _HERE.parents:
        if (p / ".env").is_file():
            return p / ".env"
    return None
'''

# 收拢后的合规写法
ENV_FORM_COLLAPSED = '''\
from zhuopin_platform.env_anchor import load_env as _resolve_and_load_env


def load_env() -> None:
    """从本脚本向上逐级查找最近的 `.env` —— 这句散文描述的正是被本门禁禁止的反范式，
    它出现在 docstring 里，**不得**被判违规（tasks 3.2：区分缺陷本身与讲解它的散文）。
    """
    print(_resolve_and_load_env(__file__).describe())
'''


class 判据二_env凭据锚定(unittest.TestCase):
    def test_A家族原文必须红(self):
        self.assertTrue(M.check_env_anchor("4-数字员工/x/scripts/run_x.py", ENV_FORM_A))

    def test_内联变体必须红(self):
        self.assertTrue(M.check_env_anchor("4-数字员工/x/run_sc2.py", ENV_FORM_INLINE))

    def test_ospath变体必须红(self):
        self.assertTrue(M.check_env_anchor("1-转型规划/x/other.py", ENV_FORM_OSPATH))

    def test_2026_08_25新出生的变体必须红(self):
        """设计清单外的第三变体——门禁的价值恰恰在于它不依赖那份人工清单。"""
        self.assertTrue(M.check_env_anchor("4-数字员工/x/scripts/compare_x.py",
                                           ENV_FORM_NEWEST))

    def test_收拢后写法为绿(self):
        self.assertEqual(M.check_env_anchor("4-数字员工/x/scripts/run_x.py",
                                            ENV_FORM_COLLAPSED), [])

    def test_散文描述反范式不得误判(self):
        """🔴 #355 与 #324 两次教训：裸子串判据会命中「讲解这个反范式的散文」。

        收拢后的 9 个入口 docstring 全在逐字描述这个反范式；判据若锚在子串上，
        它们会全部被点亮，然后这道门禁被习惯性忽略。
        """
        prose = (
            '"""本模块讲解一个反范式：从脚本向上逐级找最近的 `.env`，\n'
            '   写法形如 for d in here.parents: cand = d / ".env"。\n'
            '   它从 linked worktree 跑时命中陈旧副本且不报错。"""\n'
            "import os\n"
        )
        self.assertEqual(M.check_env_anchor("4-数字员工/x/doc.py", prose), [])

    def test_注释里的反范式不得误判(self):
        commented = (
            '# 原写法：for d in (here.parent, *here.parents): cand = d / ".env"\n'
            "# 已收拢，见 env_anchor.py\n"
            "import os\n"
        )
        self.assertEqual(M.check_env_anchor("4-数字员工/x/y.py", commented), [])

    def test_只有env字面量没有向上走_不判违规(self):
        """读一个固定位置的 `.env` 不属本判据（那是 B 家族，另有收拢路径）。"""
        text = 'for line in (ROOT / ".env").read_text().splitlines():\n    pass\n'
        self.assertEqual(M.check_env_anchor("4-数字员工/x/y.py", text), [])

    def test_只有向上走没有env_不判违规(self):
        text = "for p in here.parents:\n    if (p / 'pyproject.toml').is_file():\n        break\n"
        self.assertEqual(M.check_env_anchor("4-数字员工/x/y.py", text), [])

    def test_语法错误文件不炸(self):
        self.assertEqual(M.check_env_anchor("x/y.py", "def broken(:\n"), [])

    def test_env_anchor自身豁免(self):
        """收拢的目的地本身——不豁免则门禁自相矛盾。"""
        self.assertEqual(
            M.check_env_anchor(
                "5-平台底座/zhuopin_platform/zhuopin_platform/env_anchor.py", ENV_FORM_A), [])

    def test_变异验证夹具文件豁免(self):
        """两份测试内含 A 家族原文作变异验证夹具；判据若不认它们，那两套测试是空转的。"""
        for rel in ("5-平台底座/zhuopin_platform/tests/test_env_anchor.py",
                    "1-转型规划/AI运营指挥中心/tests/test_serve_env_anchor_parity.py"):
            self.assertEqual(M.check_env_anchor(rel, ENV_FORM_A), [], rel)

    def test_serve自身豁免(self):
        """唯一的生产例外（零三方依赖 ＋ `.51` 部署侧无平台底座），其等价性另有 parity 测试守。"""
        self.assertEqual(
            M.check_env_anchor("1-转型规划/AI运营指挥中心/serve.py", ENV_FORM_OSPATH), [])

    def test_学习与工具族豁免(self):
        self.assertEqual(M.check_env_anchor("0-学习与工具/发企微.py", ENV_FORM_A), [])

    def test_每条豁免都写明了理由(self):
        """豁免不写理由，下一个人只能猜，而猜的结果通常是再加一条。"""
        for suffix, reason in M.ENV_ANCHOR_EXEMPT:
            self.assertTrue(reason.strip(), f"{suffix} 的豁免没写理由")


class 真实仓库现状(unittest.TestCase):
    def test_存量已清零(self):
        """收口判据：全库非 stub 形态命中数为 0（tasks 6.3）。"""
        repo = M.REPO_ROOT
        violations = []
        for rel in M._tracked_py_files(repo):
            try:
                text = (repo / rel).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            violations.extend(M.check_file(rel, text))
        self.assertEqual(violations, [], f"仍有非 stub 形态残留：{violations}")

    def test_env锚定存量已清零(self):
        """判据二的收口判据（tasks 3.5 切 `--enforce` 的前置条件之一）。"""
        repo = M.REPO_ROOT
        violations = []
        for rel in M._tracked_py_files(repo):
            try:
                text = (repo / rel).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            violations.extend(M.check_env_anchor(rel, text))
        self.assertEqual(violations, [], f"仍有「向上逐级找 .env」残留：{violations}")


if __name__ == "__main__":
    unittest.main()
