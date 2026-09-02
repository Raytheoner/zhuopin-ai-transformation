"""工具-跟进信frontmatter校验.py 单测（队列 §一 `#447` ⑴）。

白盒方式：把临时目录当 repo_root，在其下造出 `6-人才与组织/部门AI专员跟进/` 夹具，
**不触碰真实的 64 封信与 README**（README 的「发送状态」列是信级唯一权威源，
2026-08-21 §四 `#85` 答 (b)，本包一个字节不动）。

🔴 **两条回归锁**（各对应一次真身实测发现，不是凭空造的用例）：
- `test_决策点_带尾随说明不判违规` —— 取证件 §三⑴ 建议的全串锚定正则
  `^\\d+ 项(（.+）)?$` 在真身上**会误杀 `IT部#5` 那条真实取值**。本测把那条原文钉住。
- `test_推送摘要派生件不参与判定` —— `采购部#19` 被正信与 `-推送摘要.md` 共用，
  后者无 `status`。若不排除，S1 会对一个根本不该守的文件常年报违规。
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-跟进信frontmatter校验.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("_followup_fm_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MOD = _load_module()

GOOD = """---
title: 采购部跟进（2026-09-01）——三条判例请批
status: ⏳ 待你审
created: 2026-09-01
收信人: 采购部 · 姚祖怡
编号: 采购部#20
决策点: 2 项（判例 A 是否成立 / 阈值取 3 天还是 5 天）
配套: 队列 #447
---

正文。
"""


def _write(root: Path, name: str, text: str) -> None:
    directory = root / MOD.FOLLOWUP_DIR
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(text, encoding="utf-8")


class FrontmatterSchemaTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _check(self, name: str, text: str):
        _write(self.root, name, text)
        letters, _ = MOD.collect_letters(str(self.root))
        self.assertEqual(len(letters), 1, "夹具应恰好被收集到 1 封")
        return MOD.check_letter(letters[0])

    # ---------- S1 ----------

    def test_合规信零违规(self):
        violations, _ = self._check("采购部-姚祖怡-跟进-2026-09-01-三条判例.md", GOOD)
        self.assertEqual(violations, [])

    def test_缺决策点即违规(self):
        text = GOOD.replace("决策点: 2 项（判例 A 是否成立 / 阈值取 3 天还是 5 天）\n", "")
        violations, _ = self._check("采购部-姚祖怡-跟进-2026-09-01-三条判例.md", text)
        self.assertTrue(any("缺必写字段 `决策点:`" in v for v in violations), violations)

    def test_决策点0项合法(self):
        """通报类信的真实形态。判它违规会逼出假数据。"""
        text = GOOD.replace(
            "决策点: 2 项（判例 A 是否成立 / 阈值取 3 天还是 5 天）",
            "决策点: 0 项（本信不含需她定夺的判定规则；仅一处知会）",
        )
        violations, _ = self._check("采购部-姚祖怡-跟进-2026-09-01-三条判例.md", text)
        self.assertEqual(violations, [])

    def test_必写字段取值为空即违规(self):
        text = GOOD.replace("配套: 队列 #447", "配套:")
        violations, _ = self._check("采购部-姚祖怡-跟进-2026-09-01-三条判例.md", text)
        self.assertTrue(any("`配套:` 取值为空" in v for v in violations), violations)

    # ---------- S2 ----------

    def test_收件人判为非法别名(self):
        text = GOOD.replace("收信人: 采购部 · 姚祖怡", "收件人: 姚祖怡（采购部 AI 专员）")
        violations, _ = self._check("采购部-姚祖怡-跟进-2026-09-01-三条判例.md", text)
        self.assertTrue(any("S2 非法别名 `收件人:`" in v for v in violations), violations)

    def test_别名存在时不重复报缺收信人(self):
        """S2 已报出的字段，S1 不得再报一次「缺」——同一处失血只应计一次。"""
        text = GOOD.replace("收信人: 采购部 · 姚祖怡", "收件人: 姚祖怡（采购部 AI 专员）")
        violations, _ = self._check("采购部-姚祖怡-跟进-2026-09-01-三条判例.md", text)
        self.assertFalse(any("缺必写字段 `收信人:`" in v for v in violations), violations)
        self.assertEqual(len(violations), 1, violations)

    # ---------- S3 ----------

    def test_决策点_带尾随说明不判违规(self):
        """🔴 回归锁：取证件建议的全串锚定正则会误杀这条 `IT部#5` 的真实取值。"""
        text = GOOD.replace(
            "决策点: 2 项（判例 A 是否成立 / 阈值取 3 天还是 5 天）",
            "决策点: 2 项（FO 预测订单接口能否补行级状态字段 / PO 采购订单接口能否补"
            "行级关闭状态字段），或告知已有的替代查询方式",
        )
        violations, _ = self._check("IT部-陈承-跟进-2026-07-28-两个接口.md", text)
        self.assertEqual(violations, [], "带尾随说明的真实取值不得被判违规")

    def test_决策点未以数字项起首即违规(self):
        text = GOOD.replace(
            "决策点: 2 项（判例 A 是否成立 / 阈值取 3 天还是 5 天）",
            "决策点: 请她确认两件事",
        )
        violations, _ = self._check("采购部-姚祖怡-跟进-2026-09-01-三条判例.md", text)
        self.assertTrue(any("`决策点` 未以" in v for v in violations), violations)

    def test_created非日期形态即违规(self):
        text = GOOD.replace("created: 2026-09-01", "created: 2026年9月1日")
        violations, _ = self._check("采购部-姚祖怡-跟进-2026-09-01-三条判例.md", text)
        self.assertTrue(any("`created` 非 YYYY-MM-DD" in v for v in violations), violations)

    def test_编号非部门井号数字即违规(self):
        text = GOOD.replace("编号: 采购部#20", "编号: 第 20 封")
        violations, _ = self._check("采购部-姚祖怡-跟进-2026-09-01-三条判例.md", text)
        self.assertTrue(any("`编号` 非" in v for v in violations), violations)

    # ---------- S4 / 范围 ----------

    def test_推送摘要派生件不参与判定(self):
        """🔴 回归锁：派生件无 status、与正信共用编号，判它违规是判据被绕开的起点。"""
        _write(self.root, "采购部-姚祖怡-跟进-2026-08-26-三条判例-推送摘要.md",
               "---\ntitle: 推送摘要\n编号: 采购部#19\n---\n\n摘要。\n")
        letters, _ = MOD.collect_letters(str(self.root))
        self.assertTrue(letters[0].is_derived)
        violations, _ = MOD.check_letter(letters[0])
        self.assertEqual(violations, [])

    def test_重号只在正信之间判定(self):
        _write(self.root, "采购部-姚祖怡-跟进-2026-08-26-三条判例.md", GOOD)
        _write(self.root, "采购部-姚祖怡-跟进-2026-08-26-三条判例-推送摘要.md",
               "---\ntitle: 推送摘要\n编号: 采购部#20\n---\n\n摘要。\n")
        letters, _ = MOD.collect_letters(str(self.root))
        self.assertEqual(MOD.duplicate_numbers(letters), {},
                         "派生件与正信同号不算重号")
        _write(self.root, "采购部-姚祖怡-跟进-2026-08-27-另一封.md", GOOD)
        letters, _ = MOD.collect_letters(str(self.root))
        self.assertIn("采购部#20", MOD.duplicate_numbers(letters))

    def test_无frontmatter文件不判违规只登记(self):
        _write(self.root, "采购部-姚祖怡-跟进-2026-09-01-裸文件.md", "没有 frontmatter。\n")
        letters, headless = MOD.collect_letters(str(self.root))
        self.assertEqual(letters, [])
        self.assertEqual(headless, ["采购部-姚祖怡-跟进-2026-09-01-裸文件.md"])

    def test_since之前的历史信不进违规清单(self):
        bad = GOOD.replace("决策点: 2 项（判例 A 是否成立 / 阈值取 3 天还是 5 天）\n", "")
        _write(self.root, "采购部-姚祖怡-跟进-2026-07-01-历史信.md",
               bad.replace("created: 2026-09-01", "created: 2026-07-01"))
        rc = MOD.main(["--repo-root", str(self.root), "--since", "2026-09-01", "--enforce"])
        self.assertEqual(rc, 0, "历史信不追改，不得阻断")

    def test_since之后的新信照常阻断(self):
        bad = GOOD.replace("决策点: 2 项（判例 A 是否成立 / 阈值取 3 天还是 5 天）\n", "")
        _write(self.root, "采购部-姚祖怡-跟进-2026-09-01-新信.md", bad)
        rc = MOD.main(["--repo-root", str(self.root), "--since", "2026-09-01", "--enforce"])
        self.assertEqual(rc, 1)

    def test_缺created的信不得逃出since判定(self):
        """🔴 回归锁：`created` 为空时恒小于任何 --since 值 ⇒ **缺字段反而免检**。

        真身实测有 2 封 2026-09-02 的在办信正是缺 `created`。这是「错误不产生任何
        信号」那一族——判据看起来在跑，实际把最该查的那批放了过去。
        """
        bad = GOOD.replace("created: 2026-09-01\n", "")
        _write(self.root, "采购部-姚祖怡-跟进-2026-09-02-缺created.md", bad)
        rc = MOD.main(["--repo-root", str(self.root), "--since", "2026-09-01", "--enforce"])
        self.assertEqual(rc, 1, "缺 created 的信必须留在判定范围内")

    def test_created形态非法同样不得逃出since判定(self):
        bad = GOOD.replace("created: 2026-09-01", "created: 2026年9月1日")
        _write(self.root, "采购部-姚祖怡-跟进-2026-09-02-created非法.md", bad)
        rc = MOD.main(["--repo-root", str(self.root), "--since", "2026-09-01", "--enforce"])
        self.assertEqual(rc, 1)

    def test_默认测量模式不阻断(self):
        bad = GOOD.replace("决策点: 2 项（判例 A 是否成立 / 阈值取 3 天还是 5 天）\n", "")
        _write(self.root, "采购部-姚祖怡-跟进-2026-09-01-新信.md", bad)
        self.assertEqual(MOD.main(["--repo-root", str(self.root)]), 0)


class RealCorpusTest(unittest.TestCase):
    """对真身只读跑一次，锁住三条实测事实（只读，不写）。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.repo = Path(__file__).resolve().parents[1]
        cls.letters, _ = MOD.collect_letters(str(cls.repo))

    def test_真身可被解析(self):
        self.assertGreaterEqual(len(self.letters), 60, "真身信件数异常，判据可能扫错目录")

    def test_收信人收件人分裂仍然存在(self):
        counter = MOD.census(self.letters)
        self.assertGreater(counter["收件人"], 0,
                           "若已归一则本测该改——它是 S2 存在的理由")
        self.assertGreater(counter["收信人"], counter["收件人"])

    def test_status取值漂移量大于十种(self):
        values = MOD.drift_report(self.letters, "status")
        self.assertGreater(len(values), 10,
                           "S4 观测的漂移；若已收敛则枚举可定，见产出件 §四开放点")


if __name__ == "__main__":
    unittest.main()
