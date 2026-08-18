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


if __name__ == "__main__":
    unittest.main()
