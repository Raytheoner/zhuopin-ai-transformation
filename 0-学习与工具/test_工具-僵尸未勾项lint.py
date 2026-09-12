"""`工具-僵尸未勾项lint.py` 单测（openspec 包 `tasks-zombie-item-detect` tasks 2.1–2.3 ／ `OP-0912-AA`）。

在临时目录里合成最小仓库（`openspec/changes/<包>/tasks.md`），逐形态调 `scan()`／`main()`——不触碰真实仓库。

🔴 **本文件存在的理由**：这道闸对真实仓库首跑就是绿的（J-A／J-C 存量实测为 0），对真实仓库跑一遍永远证明
不了它还认得违规。故四条判据的正反例逐个复现，**外加四条必须锁死的边界**：
① J-B 无论命中多少条都不返回非零退出码（R1，tasks 2.2）；② J-B 输出措辞是「请复核」、不是「疑似已完成」
（已知边界 2）；③ `openspec/changes/archive/**` 不进扫描面、但名字含 archive 的活跃包要进（tasks 2.3）；
④ 「前置 N.M」多值写法三种分隔形态各一条夹具（决策点 4 (a) 的实现义务）——不支持即门禁上线第一天就是红的。
"""
from __future__ import annotations

import importlib.util
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-僵尸未勾项lint.py")


def _load_module():
    name = "_zombie_lint_under_test"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module      # @dataclass 需要先进 sys.modules（同 test_工具-场景包intent闸lint.py）
    spec.loader.exec_module(module)
    return module


M = _load_module()


def _repo(pkgs: dict[str, str]) -> Path:
    """pkgs：{包相对路径（可含 archive/…）: tasks.md 全文}。返回临时仓库根。"""
    root = Path(tempfile.mkdtemp(prefix="zombie-lint-"))
    for rel, text in pkgs.items():
        d = root / "openspec" / "changes" / rel
        d.mkdir(parents=True)
        (d / "tasks.md").write_text(text, encoding="utf-8")
    return root


def _run_main(root: Path, *extra: str) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = M.main(["--root", str(root), "--no-git", *extra])
    return rc, buf.getvalue()


# ------------------------------------------------------------------ 夹具

# fi2 形态：节标题声明前置 1.5/1.6（斜杠），7.1 已 [x] 而 1.5 仍 [ ]
FI2_HEADER_DECL = """# fi2 Tasks

## 1. 环境
- [ ] 1.5 前置登记：唐燕萍 R1-R6 规则草案
- [x] 1.6 前置登记：U9C 财务接口

## 7. 真实数据验证（待数据闸；前置 1.5/1.6）
- [x] 7.1 规则定稿后替换 config.py
- [ ] 7.3 物料编码映射表就绪后接入
"""

# fi1 形态：条目正文声明前置 1.6，7.4 已 [x] 而 1.6 仍 [ ]
FI1_BODY_DECL = """# fi1 Tasks

## 1. 环境
- [ ] 1.6 前置登记：IT 开放 U9C webapi 端点

## 7. 真实数据验证
- [x] 7.4 （最终切换，前置 1.6）IT 开放端点后切 u9c 直读
"""

# status-triage 形态：`前置 0.1/0.4`（斜杠）、`前置 2.3、0.3`（顿号）、`,`／`，`（spec 明列）
STATUS_TRIAGE_MULTI = """# status-triage Tasks

## 0. design 审前置
- [x] 0.1 **前置登记**：design D4 ＝ (a)
- [x] 0.2 **前置登记**：D3 ＝ (a)
- [x] 0.3 **前置登记**：次序 ＝ (a)
- [x] 0.4 openspec validate 通过

## 1. 否定词表与回测（前置 0.1/0.4）
- [x] 1.1 否定词表定稿

## 2. 只读候选出口（前置 0.2）
- [x] 2.3 单测

## 3. sweep 第 12 类接线（前置 2.3、0.3）
- [x] 3.1 接线
"""


class TestPrereqRefParsing(unittest.TestCase):
    """决策点 4 (a) 的实现义务：三种分隔形态各一条夹具（不支持即上线第一天红 2 条）。"""

    def test_slash_fi2_form(self):
        ids, n = M.parse_prereq_refs("## 7. 真实数据验证（待数据闸；前置 1.5/1.6）")
        self.assertEqual(ids, ["1.5", "1.6"])
        self.assertEqual(n, 1)

    def test_slash_status_triage_form(self):
        ids, n = M.parse_prereq_refs("## 1. 否定词表与回测（前置 0.1/0.4）")
        self.assertEqual(ids, ["0.1", "0.4"])
        self.assertEqual(n, 1)

    def test_dunhao_form(self):
        ids, n = M.parse_prereq_refs("## 3. sweep 第 12 类接线（前置 2.3、0.3）")
        self.assertEqual(ids, ["2.3", "0.3"])
        self.assertEqual(n, 1)

    def test_comma_forms_spec_listed(self):
        self.assertEqual(M.parse_prereq_refs("前置 3.6, 4.7，5.3")[0], ["3.6", "4.7", "5.3"])

    def test_three_values_dunhao(self):
        self.assertEqual(M.parse_prereq_refs("## 6. 真实数据验证（前置 3.6、4.7、5.3）")[0],
                         ["3.6", "4.7", "5.3"])

    def test_single_with_trailing_condition(self):
        # status-triage §4「前置 0.1 答 (a)；答 (b) 本节作废重写」——尾随文字不吞进项号
        self.assertEqual(M.parse_prereq_refs("## 4. 台账（前置 0.1 答 (a)；答 (b) 本节作废重写）")[0], ["0.1"])

    def test_two_refs_same_line_count_two(self):
        ids, n = M.parse_prereq_refs("前置 1.5 与 前置 2.3、0.3")
        self.assertEqual(ids, ["1.5", "2.3", "0.3"])
        self.assertEqual(n, 2)

    def test_multivalue_prevents_false_jc(self):
        """不支持多值 ⇒ fi2 1.6 与 status-triage 0.3 会被 J-C 误判为无下游引用。这里锁死它们不被误判。"""
        root = _repo({"fi2-recon-mvp": FI2_HEADER_DECL.replace("- [ ] 1.5", "- [x] 1.5"),
                      "status-triage-resident-round": STATUS_TRIAGE_MULTI})
        rep = M.scan(root, git_dates=False)
        self.assertEqual(rep.jc, [], rep.jc)
        self.assertEqual(rep.ja, [], rep.ja)


class TestJA(unittest.TestCase):
    def test_header_declared_prereq_hit(self):
        rep = M.scan(_repo({"fi2-recon-mvp": FI2_HEADER_DECL}), git_dates=False)
        self.assertEqual(len(rep.ja), 1, rep.ja)
        self.assertIn("7.1 → 1.5", rep.ja[0])
        self.assertNotIn("→ 1.6", rep.ja[0])          # 1.6 已 [x]，不算

    def test_body_declared_prereq_hit(self):
        rep = M.scan(_repo({"fi1-warehouse-reconcile": FI1_BODY_DECL}), git_dates=False)
        self.assertEqual(len(rep.ja), 1, rep.ja)
        self.assertIn("7.4 → 1.6", rep.ja[0])

    def test_no_hit_when_declaring_item_unchecked(self):
        text = FI2_HEADER_DECL.replace("- [x] 7.1", "- [ ] 7.1")
        rep = M.scan(_repo({"fi2-recon-mvp": text}), git_dates=False)
        self.assertEqual(rep.ja, [])

    def test_no_hit_when_prereq_checked(self):
        text = FI2_HEADER_DECL.replace("- [ ] 1.5", "- [x] 1.5")
        rep = M.scan(_repo({"fi2-recon-mvp": text}), git_dates=False)
        self.assertEqual(rep.ja, [])

    def test_subsection_inherits_parent_header_prereq(self):
        text = """# T
## 1. 环境
- [ ] 1.5 前置登记：X
## 7. 验证（前置 1.5）
### 7a. 子节
- [x] 7.1 做完了
"""
        rep = M.scan(_repo({"p": text}), git_dates=False)
        self.assertEqual(len(rep.ja), 1, rep.ja)
        self.assertIn("7.1 → 1.5", rep.ja[0])

    def test_unresolved_ref_is_visible_hint_not_violation(self):
        text = """# T
## 1. 环境
- [x] 1.1 正文写「前置 9.9」但本文件没有 9.9
"""
        rep = M.scan(_repo({"p": text}), git_dates=False)
        self.assertEqual(rep.ja, [])
        self.assertEqual(len(rep.unresolved), 1, rep.unresolved)
        self.assertIn("9.9", rep.unresolved[0])
        rc, out = _run_main(_repo({"p": text}), "--enforce")
        self.assertEqual(rc, 0)
        self.assertIn("不存在 9.9", out)

    def test_enforce_exit_code_only_with_enforce(self):
        root = _repo({"fi2-recon-mvp": FI2_HEADER_DECL})
        self.assertEqual(_run_main(root)[0], 0)
        rc, out = _run_main(root, "--enforce")
        self.assertEqual(rc, 1)
        self.assertIn("[J-A]", out)


class TestJB(unittest.TestCase):
    ZOMBIE_SECTION = """# T
## 10. 面板
- [ ] 10.11b 真未决：等唐燕萍团队批改（D14 Open Question）
- [x] 10.12 已交付
- [ ] 10.13 节内最后一项（已知边界 1：本判据够不着）
"""

    def test_hit_and_wording(self):
        rep = M.scan(_repo({"fi2-recon-mvp": self.ZOMBIE_SECTION}), git_dates=False)
        self.assertEqual(len(rep.jb), 1, rep.jb)
        self.assertIn("10.11b", rep.jb[0])
        self.assertIn(M.JB_WORDING, rep.jb[0])                  # MUST 「请复核」
        self.assertNotIn(M.JB_FORBIDDEN, rep.jb[0])             # MUST NOT 「疑似已完成」
        self.assertNotIn("可以勾除", rep.jb[0])

    def test_last_item_not_hit_known_boundary_1(self):
        rep = M.scan(_repo({"fi2-recon-mvp": self.ZOMBIE_SECTION}), git_dates=False)
        self.assertFalse(any("10.13" in x for x in rep.jb))

    def test_no_cross_section_hit(self):
        text = """# T
## 1. A
- [ ] 1.1 未做
## 2. B
- [x] 2.1 做完
"""
        rep = M.scan(_repo({"p": text}), git_dates=False)
        self.assertEqual(rep.jb, [])

    def test_jb_never_nonzero_exit_even_with_enforce(self):
        """R1 ／ tasks 2.2：J-B 无论命中多少条，MUST NOT 返回非零退出码。"""
        many = "# T\n## 1. A\n" + "".join(f"- [ ] 1.{i} 未做\n" for i in range(1, 30)) + "- [x] 1.30 做完\n"
        root = _repo({"p": many})
        rep = M.scan(root, git_dates=False)
        self.assertEqual(len(rep.jb), 29)
        rc, out = _run_main(root, "--enforce")
        self.assertEqual(rc, 0)
        self.assertIn("J-B 节内乱序 29 条", out)
        self.assertNotIn(M.JB_FORBIDDEN, out)
        self.assertIn("无违规", out)


class TestJC(unittest.TestCase):
    def test_unreferenced_prereq_decl_is_violation(self):
        text = """# T
## 1. 环境
- [ ] 1.6 前置登记：IT 开放端点
## 7. 验证
- [x] 7.4 切直读
"""
        rep = M.scan(_repo({"p": text}), git_dates=False)
        self.assertEqual(len(rep.jc), 1, rep.jc)
        self.assertIn("1.6", rep.jc[0])
        self.assertIn("前置 1.6", rep.jc[0])          # 出路里写明要补的那句
        self.assertEqual(_run_main(_repo({"p": text}), "--enforce")[0], 1)

    def test_referenced_decl_passes(self):
        rep = M.scan(_repo({"fi1-warehouse-reconcile": FI1_BODY_DECL}), git_dates=False)
        self.assertEqual(rep.jc, [])

    def test_bold_decl_is_recognized(self):
        text = "# T\n## 0. 前置\n- [x] 0.1 **前置登记**：D4 ＝ (a)\n## 1. A\n- [x] 1.1 做\n"
        rep = M.scan(_repo({"p": text}), git_dates=False)
        self.assertEqual(rep.prereq_decls, 1)
        self.assertEqual(len(rep.jc), 1)

    def test_mention_not_at_head_is_not_a_decl(self):
        """本包自己的 1.2／1.7 在反引号／书名号里提到「前置登记」——是引用概念，不是前置登记项。"""
        text = """# T
## 1. 取证
- [x] 1.2 `git log -S'1.5 前置登记' -- x/tasks.md` 实跑
- [x] 1.7 J-C 基线实跑 —— 全库「前置登记」项 3 个
"""
        rep = M.scan(_repo({"p": text}), git_dates=False)
        self.assertEqual(rep.prereq_decls, 0)
        self.assertEqual(rep.jc, [])


class TestScanSurfaceAndOutput(unittest.TestCase):
    def test_archive_dir_excluded_but_archive_named_pkg_included(self):
        """tasks 2.3：archive/** 不进扫描面；`audit-retention-archive` 这类活跃包要进。"""
        root = _repo({
            "archive/2026-08-07-fi2-tax-export-ingest": FI2_HEADER_DECL,     # 有 J-A 违规，但不该被扫
            "audit-retention-archive": FI1_BODY_DECL,                        # 活跃包，有 J-A 违规
        })
        rep = M.scan(root, git_dates=False)
        self.assertEqual(rep.scanned_packages, 1)
        self.assertEqual([f.pkg for f in rep.files], ["audit-retention-archive"])
        self.assertEqual(len(rep.ja), 1)
        rc, out = _run_main(root, "--enforce")
        self.assertEqual(rc, 1)
        self.assertNotIn("fi2-tax-export-ingest", out)
        self.assertNotIn("7.1 → 1.5", out)

    def test_prereq_count_line_and_zero_flag(self):
        root = _repo({"fi2-recon-mvp": FI2_HEADER_DECL, "status-triage-resident-round": STATUS_TRIAGE_MULTI})
        _, out = _run_main(root)
        self.assertIn("本次扫描共发现 4 个前置声明", out)      # fi2 §7 一处 ＋ status §1／§2／§3 三处
        self.assertIn("「前置登记」项 5 个", out)
        empty = _repo({"p": "# T\n## 1. A\n- [ ] 1.1 x\n"})
        _, out0 = _run_main(empty)
        self.assertIn("本次扫描共发现 0 个前置声明", out0)
        self.assertIn("J-A 已整体失效", out0)                   # R2：N=0 是该被看见的信号

    def test_jd_echo_counts_unnumbered_and_marks_unknown_date(self):
        text = "# T\n## 1. A\n- [ ] 1.1 x\n- [ ] a. 不带编号\n- [x] 1.2 y\n"
        root = _repo({"p": text})
        rep = M.scan(root, git_dates=False)
        self.assertEqual(rep.files[0].unchecked_total, 2)
        _, out = _run_main(root)
        self.assertIn("p：未勾 2 项（带编号 1）", out)
        _, out_sum = _run_main(root, "--jd-summary")
        self.assertNotIn("  1.1  ", out_sum)

    def test_fenced_code_is_ignored(self):
        text = "# T\n## 1. A\n- [x] 1.1 做\n```\n- [ ] 1.0 代码块里的假条目（前置 1.1）\n```\n"
        rep = M.scan(_repo({"p": text}), git_dates=False)
        self.assertEqual(len(rep.files[0].items), 1)
        self.assertEqual(rep.prereq_refs, 0)

    def test_read_only(self):
        """spec：纯只读——运行前后临时仓库的文件集合与 mtime 一字不变。"""
        root = _repo({"fi2-recon-mvp": FI2_HEADER_DECL, "p": "# T\n## 1. A\n- [ ] 1.1 x\n"})

        def snapshot():
            return sorted((str(p.relative_to(root)), p.stat().st_mtime_ns, p.stat().st_size)
                          for p in root.rglob("*") if p.is_file())

        before = snapshot()
        _run_main(root, "--enforce")
        M.scan(root, git_dates=True)   # 无 git 仓库：blame 失败须静默、不落盘
        self.assertEqual(snapshot(), before)


class TestRealRepoSmoke(unittest.TestCase):
    """对真实仓库跑一遍：J-A／J-C 存量应为 0（决策点 3 前提，apply 时已实测）；此处只锁「不崩、结构对」。"""

    def test_real_repo_runs(self):
        root = SCRIPT.parent.parent
        if not (root / "openspec" / "changes").is_dir():
            self.skipTest("非仓库布局")
        rep = M.scan(root, git_dates=False)
        self.assertGreater(rep.scanned_packages, 0)
        self.assertGreater(rep.prereq_refs, 0, "R2：真实仓库前置声明数掉到 0 须被看见")


if __name__ == "__main__":
    unittest.main()
