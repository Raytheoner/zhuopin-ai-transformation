"""`工具-泳道纪律复制lint.py` 单测（变更包 `lane-watch-deploy-extension` §4；队列 §一 `#478`）。

两件事必须被钉死，否则这道守卫就是摆设：

1. 🔴 **fail-closed**——判据词抽不出来时**报错**，绝不"抽不到词就当没违规"（抽不到词
   ⇒ 检查恒过 ⇒ 守卫静默失效，本项目最熟悉的失败形态）；
2. 🔴 **负例真的被拦下**——只跑绿不算数（design 决策点 6⑶(a) 明确列为硬性）。

判据词一律用**内联的伪正本文本**喂进抽取函数，不依赖真实正本的具体措辞；只有
「全库实跑应为绿」那一条用真实仓库（它本来就是在核真实状态）。
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-泳道纪律复制lint.py")


def _load():
    spec = importlib.util.spec_from_file_location("_lane_copy_lint_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


#: 伪正本：形状与真实正本同族，措辞刻意不同——用来证明抽取靠的是**结构**，不是记住了哪几个词。
FAKE_SOURCE = """## 触发与前置

- 触发：某人说一句话。

## 执行步骤

1. **第一步**：做点别的。
4. **起无头泳道**：opener 正文含授权链、心跳段、以及 🔴 每项固定四步＝甲步→乙步→丙步→丁步；
   丙步不过即撤回停项。

## 版本
"""


class ExtractMarkersTests(unittest.TestCase):
    def setUp(self):
        self.m = _load()

    def test_extracts_sequence_and_fallback_action_in_source_order(self):
        markers = self.m.extract_markers(FAKE_SOURCE)
        self.assertEqual(markers, ["甲步", "乙步", "丙步", "丁步", "撤回"])

    def test_fail_closed_when_section_missing(self):
        with self.assertRaises(self.m.CriteriaExtractionFailed):
            self.m.extract_markers("## 别的小节\n\n随便什么内容。\n")

    def test_fail_closed_when_step_sequence_missing(self):
        text = "## 执行步骤\n\n1. 做点什么，但没有写成固定N步的箭头串。\n"
        with self.assertRaises(self.m.CriteriaExtractionFailed):
            self.m.extract_markers(text)

    def test_fail_closed_when_too_few_markers(self):
        text = "## 执行步骤\n\n4. 每项固定二步＝甲步→乙步。\n"
        with self.assertRaises(self.m.CriteriaExtractionFailed):
            self.m.extract_markers(text)

    def test_real_source_of_truth_yields_markers(self):
        """真实正本此刻抽得出判据词——抽不出就该整条 CI 红，而不是静默放行。"""
        text = (self.m.REPO_ROOT / self.m.SOURCE_OF_TRUTH_REL).read_text(encoding="utf-8")
        markers = self.m.extract_markers(text)
        self.assertGreaterEqual(len(markers), 4)


class ViolationDetectionTests(unittest.TestCase):
    def setUp(self):
        self.m = _load()
        self.markers = self.m.extract_markers(FAKE_SOURCE)

    def test_copied_sequence_is_flagged(self):
        """🔴 负例：一段照抄的可执行序列必须被拦下。"""
        text = "每项固定四步＝甲步→乙步→丙步→丁步；丙步不过即撤回停项。\n"
        v = self.m.check_file("x.md", text, self.markers, 4)
        self.assertEqual(len(v), 1)
        self.assertGreaterEqual(v[0]["matched"], 4)

    def test_abridged_mention_is_not_flagged(self):
        """正例：警示性的缩略提及带不动门槛条数——「提到它」不等于「抄了它」。"""
        text = "「甲步→别的→丙步→不过即撤回」那套纪律只长在另一侧，本包重实现一遍就是复制护栏。\n"
        self.assertEqual(self.m.check_file("x.md", text, self.markers, 4), [])

    def test_pointer_line_is_exempt(self):
        """指针句豁免：既有指向动词、又真的指着正本，才算指针句。"""
        line = ("🔴 MUST 现读 `0-学习与工具/skills源码/zhuopin-lan-closeout/SKILL.md`"
                "「执行步骤」第 4 项：甲步→乙步→丙步→丁步；丙步不过即撤回。\n")
        self.assertTrue(self.m.is_pointer_line(line))
        self.assertEqual(self.m.check_file("x.md", line, self.markers, 4), [])

    def test_pointer_verb_alone_does_not_exempt(self):
        """只写「见」而不指向正本 ⇒ 不豁免——豁免收窄，防的是「加个词就绕过」。"""
        text = "见下：甲步→乙步→丙步→丁步；丙步不过即撤回停项。\n"
        self.assertFalse(self.m.is_pointer_line(text.strip()))
        self.assertEqual(len(self.m.check_file("x.md", text, self.markers, 4)), 1)

    def test_out_of_order_words_do_not_count_as_sequence(self):
        """判据是**序列**不是词袋：顺序不对的散落词不构成可执行序列。"""
        text = "丁步、丙步、乙步、甲步 四个词在这里各自出现了一次，但不成序列。\n"
        run, _ = self.m.ordered_marker_run(text, self.markers)
        self.assertLess(run, 4)

    def test_paragraph_granularity_does_not_leak_across_blank_lines(self):
        text = "甲步 在这一段。\n\n乙步 在这一段。\n\n丙步 在这一段。\n\n丁步 在这一段。\n"
        self.assertEqual(self.m.check_file("x.md", text, self.markers, 4), [])


class RepositoryScanTests(unittest.TestCase):
    def setUp(self):
        self.m = _load()

    def test_guarded_globs_cover_the_four_carrier_families(self):
        files = self.m.guarded_files()
        self.assertIn("0-学习与工具/工具-泳道看护状态机.py", files)
        self.assertIn("0-学习与工具/skills源码/zhuopin-lane-watch/SKILL.md", files)
        self.assertTrue(any(f.startswith("openspec/changes/lane-watch-mode/") for f in files))
        self.assertTrue(
            any(f.startswith("openspec/changes/lane-watch-deploy-extension/") for f in files),
            "本变更包自身必须在守卫范围内——把自己排除在外就是自证不可信",
        )
        self.assertNotIn(self.m.SOURCE_OF_TRUTH_REL, files)

    def test_repository_is_currently_clean(self):
        """正例全库实跑：当前三处载体 ＋ 本变更包一律不含副本。"""
        self.assertEqual(self.m.main([]), 0)


if __name__ == "__main__":
    unittest.main()
