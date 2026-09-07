"""`工具-规划倒逼扫描器.py` 单测（队列 §一 `#462` ／ openspec 包 `plan-backpressure-scanner`）。

## 本文件的组织方式与别的 lint 单测不同，理由写在这里

包 tasks 8.1 写死：**四个已知误判形态各有一条「在真实数据上跑的」断言测试，且每条都有
反向对照组**。⇒ 本文件分两半：

- **`Real*` 系列 ＝ 在本仓库真实数据上跑**（真队列、真 `4-数字员工/`、真 `openspec/changes`）。
  合成一个假仓库测不到"取证件那版为什么在真实数据上错了"——四个误判形态全部是**真实数据
  的形状**造成的，mock 掉数据就等于把被测对象换掉了。这也是 proposal 里
  「mock 先行不适用、改为只读先行」那条红线的落点。
- **`Synthetic*` 系列 ＝ 临时目录合成最小仓库**，测 registry 解析、边界、降级等与具体数据
  无关的判据。

🔴 **反向对照组是本文件的重点，不是形式主义。** design D2 起草期与取证件 §三 犯的是**同一种
错**——"看到一个数对上了就当判据成立"（取证件注释声称守住右边界、实际没有；design 初稿
声称阈值 3 有实测支撑、实际只核了两行且核错一行）。一条没有反向对照的断言，与一条恒真的
断言长得完全一样。故凡守卫类断言，都配一条"把守卫拆掉后它必须失败"的对照。
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-规划倒逼扫描器.py")
REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    name = "_plan_backpressure_under_test"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    # 🔴 先进 sys.modules 再 exec——被测模块用了 @dataclass，`dataclasses._is_type`
    # 会按 `cls.__module__` 回查 sys.modules，查不到就 AttributeError（同
    # `test_工具-场景包intent闸lint.py` 的既有注）。
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


M = _load_module()


def _write_registry(root: Path, rows: list[dict]) -> None:
    path = root / M.REGISTRY_PATH_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "// 合成 registry\n"
        + "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8")


def _scenario(code: str, domain: str = "采购", **kw) -> dict:
    row = {"code": code, "domain": domain, "title": f"{code} 场景",
           "planned_month": "2027-01", "aliases": [code],
           "excludes": [], "suspended": ""}
    row.update(kw)
    return row


def _queue_file(root: Path, rel: str, rows: list[tuple[str, str]]) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    body = ["# 队列", "", "## 一、任务看板", "",
            "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |",
            "|---|---|---|---|---|---|---|---|"]
    for rid, task in rows:
        body.append(f"| {rid} | {task} | 待领 | — | — | [S:open] | — | — |")
    body += ["", "## 二、待 commit 批次", ""]
    path.write_text("\n".join(body) + "\n", encoding="utf-8")


# ===========================================================================
# 形态 ⑴ 自指行 —— 招牌用例：宣布问题存在的那一行，被当成问题已解决的证据
# ===========================================================================

class RealSelfReferentialRow(unittest.TestCase):
    """`#463` 的状态列点名 14 个场景、任务列只点名 `SC4`。真实数据上跑。"""

    @classmethod
    def setUpClass(cls):
        cls.verdicts = M.classify(REPO_ROOT)
        cls.by_code = {v.scenario.code: v for v in cls.verdicts}

    def test_销售域五场景不因463被判已承接(self):
        # 🔴 tasks 2.1.1：本包的招牌用例。S1 因 `#259`（阶段编号）被降级为「疑似」，
        # 其余四个必须落在「三处皆无」——**都不得是「已承接」**。
        for code in ("S1", "S2", "S3", "S5", "S6"):
            with self.subTest(code=code):
                self.assertNotEqual(self.by_code[code].bucket, "已承接",
                                    f"{code} 被判已承接——自指行假阴性回归了")

    def test_463仍在队列里_否则本条断言是空的(self):
        # 🔴 反向对照组之一：若 `#463` 已被销行，上面那条断言会因"根本没有那一行"
        # 而恒真。先证明干草堆里确实还有那根针。
        found = False
        for rel in M.QUEUE_PATHS_REL:
            section = M._split_section_one((REPO_ROOT / rel).read_text(encoding="utf-8"))
            for line in section.splitlines():
                cells = M._queue_table.split_row_cells(line)
                if cells and len(cells) >= 2 and M._row_id(cells) == "463":
                    found = True
                    self.assertIn("14 个场景", cells[1],
                                  "#463 任务列已改写，本用例的前提需重核")
                    self.assertIn("SC4", M.target_segment(cells[1]))
        self.assertTrue(found, "§一 已无 #463——本组断言失去被测对象，须重挑用例")

    def test_反向对照_扫全行则销售域立刻被判已承接(self):
        # 🔴 反向对照组之二：把判据放宽回"扫全行"，`#463` 的状态列会让销售域
        # 五场景全部命中——证明"只扫任务列标的段"这一条确实在起作用，
        # 而不是因为队列里恰好没人提过它们。
        whole_rows = []
        for rel in M.QUEUE_PATHS_REL:
            section = M._split_section_one((REPO_ROOT / rel).read_text(encoding="utf-8"))
            for line in section.splitlines():
                cells = M._queue_table.split_row_cells(line)
                if cells and len(cells) >= 2 and M._row_id(cells) == "463":
                    whole_rows.append(line)
        self.assertTrue(whole_rows)
        hay = "\n".join(whole_rows)
        hits = [c for c in ("S1", "S2", "S3", "S5", "S6")
                if M._alias_regex(c).search(hay)]
        self.assertGreaterEqual(
            len(hits), 4,
            "扫全行竟然没让销售域大面积命中——`#463` 的状态列形状已变，"
            "本对照组失效，须重新取证")


# ===========================================================================
# 形态 ⑵ 命名空间对撞 —— excludes 只降级不剔除
# ===========================================================================

class RealNamespaceCollision(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.by_code = {v.scenario.code: v for v in M.classify(REPO_ROOT)}

    def test_R1不因202被判已承接(self):
        # tasks 3.1b：`#202` 里的 R1 是「工程研发 AI Champion 门禁」，不是 R1 场景。
        self.assertNotEqual(self.by_code["R1"].bucket, "已承接")

    def test_S1不因259被判已承接(self):
        # tasks 3.1b：`#259` 里的 S1 是 Phase 1 筑基期阶段编号。
        self.assertNotEqual(self.by_code["S1"].bucket, "已承接")

    def test_被排除的场景仍留在清单里_只降级不剔除(self):
        # 🔴 tasks 3.2：MUST NOT 从输出消失。
        for code in ("R1", "R5", "S1"):
            with self.subTest(code=code):
                v = self.by_code[code]
                self.assertEqual(v.bucket, "疑似已承接·待人确认")
                self.assertTrue(v.downgraded, "降级档必须带命中详情")

    def test_降级时打印是哪条excludes命中的(self):
        # tasks 3.3：这一档没法被人判，如果不说是哪条词命中的。
        text = M.render_text(M.classify(REPO_ROOT))
        self.assertIn("excludes 命中", text)
        self.assertIn("收口外部对抗性评审", text)

    def test_每条excludes都带真实来源行号(self):
        # 🔴 tasks 3.1：不写来源的排除词，下一个人只能猜它当初挡的是什么。
        for sc in M.load_registry(REPO_ROOT):
            for ex in sc.excludes:
                with self.subTest(code=sc.code, phrase=ex.phrase):
                    self.assertRegex(ex.source, r"#\d+")

    def test_反向对照_没有excludes时R1会被判已承接(self):
        # 🔴 反向对照组：把 R1 的 excludes 清空后，`#202` 会让它变成「已承接」——
        # 证明降级确实是 excludes 干的，不是"本来就没命中"。
        scenarios = [s for s in M.load_registry(REPO_ROOT) if not s.retired]
        naked = [s if s.code != "R1" else M.Scenario(
            s.code, s.domain, s.title, s.planned_month, s.aliases, (), s.suspended)
            for s in scenarios]
        hits = M.scan_queue(REPO_ROOT, naked)["R1"]
        self.assertTrue(hits, "去掉 excludes 后 R1 在队列里零命中——对照组前提不成立")
        self.assertTrue(all(blocked == "" for _, blocked in hits))


# ===========================================================================
# 形态 ⑶ 右边界 —— 取证件那句"注释声称有守卫、实际没有"
# ===========================================================================

class BoundaryAssertions(unittest.TestCase):

    NEGATIVE = (("FI1", "FI10-存货跌价智能分析"),
                ("SC1", "SC10-BOM评审与物料库管控"),
                ("O1", "O10"))

    def test_短码不得命中长码(self):
        for alias, hay in self.NEGATIVE:
            with self.subTest(alias=alias):
                self.assertIsNone(M._alias_regex(alias).search(hay))

    def test_正向对照_正常命中不受影响(self):
        self.assertIsNotNone(
            M._alias_regex("SC4").search("SC4-合同条款自动提取与审核"))

    def test_反向对照_去掉右边界后三条必须全部失败(self):
        # 🔴 tasks 2.4.3：否则说明测试根本没测到守卫。
        for alias, hay in self.NEGATIVE:
            with self.subTest(alias=alias):
                self.assertIsNotNone(
                    M._alias_regex(alias, right_boundary=False).search(hay),
                    f"去掉右侧 lookahead 后 {alias} 竟仍不命中 {hay}——"
                    "本对照组没有测到守卫，等于四条断言全是恒真的")

    def test_真实工程目录上FI1不命中FI10(self):
        by_code = {v.scenario.code: v for v in M.classify(REPO_ROOT)}
        refs = " ".join(e.ref for e in by_code["FI1"].accepted)
        self.assertNotIn("FI10", refs)


# ===========================================================================
# 形态 ⑷ 宽紧两档 —— 标的段判据，以及被撤回的"阈值 3"不得复活
# ===========================================================================

class TargetSegment(unittest.TestCase):

    def test_首个粗体段即标的段(self):
        self.assertEqual(M.target_segment("**FI3 付款校验 design**：后段提到 SC8"),
                         "FI3 付款校验 design")

    def test_无粗体时取前60字(self):
        cell = "甲" * 100
        self.assertEqual(M.target_segment(cell), "甲" * 60)

    def test_标的段之外的引用不构成承接(self):
        # tasks 2.1.3
        seg = M.target_segment("**标的是 SC4 合同条款**——沿革里提到 SC10 与 FI2")
        self.assertIsNotNone(M._alias_regex("SC4").search(seg))
        for other in ("SC10", "FI2"):
            self.assertIsNone(M._alias_regex(other).search(seg))

    def test_标的段点名多个场景时全部计入(self):
        # 🔴 tasks 2.1.2：`#339`（FI3 唯一真承接行）与 `#467`（SC4 场景立行行）
        # 是 design D2 起草期那条"阈值 3"判据会误杀的行。
        by_code = {v.scenario.code: v for v in M.classify(REPO_ROOT)}
        fi3_refs = " ".join(e.ref for e in by_code["FI3"].accepted)
        self.assertIn("#339", fi3_refs, "FI3 的唯一真承接行 #339 丢了")
        sc4_refs = " ".join(e.ref for e in by_code["SC4"].accepted)
        self.assertIn("#467", sc4_refs, "SC4 的场景立行行 #467 丢了")

    def test_实现中不存在按场景数量做整体排除的分支(self):
        # 🔴 tasks 8.6：被撤回的判据不得以任何形式复活。AST 扫全模块——
        # 找"对场景码集合/列表长度与常数比大小"的比较。
        tree = M.module_ast()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            left = node.left
            if not (isinstance(left, ast.Call)
                    and isinstance(left.func, ast.Name) and left.func.id == "len"):
                continue
            for op, comp in zip(node.ops, node.comparators):
                if isinstance(op, (ast.GtE, ast.Gt)) and isinstance(comp, ast.Constant):
                    src = ast.unparse(node)
                    self.assertNotIn("hits", src,
                                     f"疑似「点名数量达阈值即整体排除」判据复活：{src}")
                    self.assertNotIn("codes", src, f"同上：{src}")


# ===========================================================================
# 前置依赖：只展示、不设闸；且不得按 emoji 推断
# ===========================================================================

class PrereqDisplayOnly(unittest.TestCase):

    def test_无前置行的场景照样进清单(self):
        by_code = {v.scenario.code: v for v in M.classify(REPO_ROOT)}
        no_row = [v for v in by_code.values()
                  if v.bucket == "三处皆无" and v.prereq_row is None]
        self.assertTrue(no_row, "真实数据里没有『前置总表无此场景行』的样本，用例需重挑")
        text = M.render_text(list(by_code.values()))
        self.assertIn("前置总表无此场景行", text)

    def test_判定路径里不存在按emoji推断前置的分支(self):
        # 🔴 tasks 4.2：该表图例里 🔴 ＝「关键前置（卡场景上线）」而非「未就绪」，
        # 按 emoji 判会得到与语义相反的结果。AST 扫全模块的字符串常量。
        tree = M.module_ast()
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc:
                    docstrings.add(doc)
        # 🔴 判据落在**比较/判定**上，不落在字符串出现上——渲染层当然会用 🔴/🟡
        # 给三档打标（那是给人看的输出，不是判据）。真要"按 emoji 推断前置"，必然表现为
        # 拿 emoji 常量去比较、`in`、或 `startswith/find`。故扫这三种形态。
        emojis = ("🔴", "🟡", "🟢", "⚪", "⏸")
        del docstrings  # 本判据不需要排除 docstring：docstring 不是比较运算

        def _emoji_const(node) -> str | None:
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for e in emojis:
                    if e in node.value:
                        return node.value
            return None

        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                for operand in [node.left, *node.comparators]:
                    bad = _emoji_const(operand)
                    self.assertIsNone(
                        bad, f"判定路径按 emoji 做比较：{ast.unparse(node)[:120]}"
                             "——该表图例里 🔴 ＝「关键前置（卡场景上线）」而非「未就绪」，"
                             "按它判会得到与语义相反的结果")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr in ("startswith", "endswith", "find", "index"):
                for arg in node.args:
                    self.assertIsNone(
                        _emoji_const(arg),
                        f"判定路径按 emoji 做前缀/查找判定：{ast.unparse(node)[:120]}")

    def test_机器字段缺失时非静默降级为未知(self):
        # tasks 4.4：(b) 档切换预留，缺字段一律 unknown，绝不回退到关键词/emoji 推断。
        self.assertEqual(M._prereq_machine_field("🔴 关键前置（卡场景上线）"), "unknown")
        self.assertEqual(M._prereq_machine_field("[P:ready] 已解除"), "ready")
        self.assertEqual(M._prereq_machine_field("[P:blocked] 等 IT"), "blocked")


# ===========================================================================
# 写侧：本模块一个字节都不写队列（design D5 ＝ (b)）
# ===========================================================================

class WriteSideIsClosed(unittest.TestCase):

    def test_跑完扫描后两份队列逐字节不变(self):
        # 🔴 tasks 5.7.1
        before = {rel: hashlib.sha256((REPO_ROOT / rel).read_bytes()).hexdigest()
                  for rel in M.QUEUE_PATHS_REL}
        M.classify(REPO_ROOT)
        M.queue_row_drafts(M.classify(REPO_ROOT))
        after = {rel: hashlib.sha256((REPO_ROOT / rel).read_bytes()).hexdigest()
                 for rel in M.QUEUE_PATHS_REL}
        self.assertEqual(before, after)

    def test_暂缓场景无论哪一档都不出队列行草案(self):
        # 🔴 tasks 5.7.2：他已明令不立的行，不该由机器写出来给人按。
        verdicts = M.classify(REPO_ROOT)
        drafted = {d["code"] for d in M.queue_row_drafts(verdicts)}
        suspended = {v.scenario.code for v in verdicts if v.scenario.suspended}
        self.assertTrue(suspended, "真实 registry 里没有 suspended 场景，用例前提不成立")
        self.assertFalse(drafted & suspended)

    def test_模块内既不调子进程也不import编辑锁(self):
        # 🔴 tasks 5.7.3 的反面：写侧未放开之前，连"能写"的路径都不该存在。
        # AST 判据（不是 grep 正文）——docstring 里当然会提到 `append-row`。
        tree = M.module_ast()
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertNotIn("subprocess", imported,
                         "模块 import 了 subprocess——写侧未放开前不该有能起子进程的路径")
        calls = {ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
        for forbidden in ("subprocess.run", "subprocess.Popen", "os.system"):
            self.assertNotIn(forbidden, calls)
        # 写盘只允许落 reports/（清单件），不得写任何队列路径
        writes = [ast.unparse(n) for n in ast.walk(tree)
                  if isinstance(n, ast.Call) and ast.unparse(n.func).endswith("write_text")]
        for w in writes:
            self.assertIn("report", w.lower(), f"疑似向非 reports/ 路径写盘：{w}")

    def test_暂缓场景保留在清单但移出推送(self):
        verdicts = M.classify(REPO_ROOT)
        with_susp = M.unaccepted_codes(verdicts, include_suspended=True)
        push = M.unaccepted_codes(verdicts, include_suspended=False)
        self.assertTrue(with_susp - push, "暂缓场景没有被移出推送口径")
        text = M.render_text(verdicts)
        for code in sorted(with_susp - push):
            self.assertIn(code, text, f"{code} 被移出推送的同时也从清单里消失了")


# ===========================================================================
# registry 与一致性校验
# ===========================================================================

class RealRegistry(unittest.TestCase):

    def test_一致性校验在真实仓库上通过(self):
        missing, extra = M.lint_registry(REPO_ROOT)
        self.assertEqual((missing, extra), ([], []))

    def test_35个在办场景加5个退休编号(self):
        rows = M.load_registry(REPO_ROOT)
        self.assertEqual(len([r for r in rows if not r.retired]), 35)
        self.assertEqual({r.code for r in rows if r.retired},
                         {"Q1", "Q3", "Q5", "Q7", "Q8"})

    def test_registry未被gitignore覆盖(self):
        # 🔴 tasks 1.2：实测，不是"应该没被忽略"这类推断。
        result = subprocess.run(
            ["git", "check-ignore", M.REGISTRY_PATH_REL],
            cwd=REPO_ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1,
                         f"registry 被 .gitignore 覆盖了：{result.stdout.strip()}")

    def test_暂缓标记必须带来源与日期(self):
        for sc in M.load_registry(REPO_ROOT):
            if sc.suspended:
                with self.subTest(code=sc.code):
                    self.assertRegex(sc.suspended, r"#\d+")
                    self.assertRegex(sc.suspended, r"\d{4}-\d{2}-\d{2}")

    def test_退休编号不参与扫描(self):
        codes = {v.scenario.code for v in M.classify(REPO_ROOT)}
        self.assertFalse(codes & {"Q1", "Q3", "Q5", "Q7", "Q8"})

    def test_排期月不进任何判据(self):
        # spec：planned_month 仅供展示。把所有排期月改成远期，结论必须一字不变。
        base = {v.scenario.code: v.bucket for v in M.classify(REPO_ROOT)}
        rows = M.load_registry(REPO_ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            root = self._mirror(Path(tmp))
            _write_registry(root, [
                {"code": r.code, "domain": r.domain, "title": r.title,
                 "planned_month": "2099-12", "aliases": list(r.aliases),
                 "excludes": [{"phrase": e.phrase, "source": e.source} for e in r.excludes],
                 "suspended": r.suspended, **({"retired": True} if r.retired else {})}
                for r in rows])
            moved = {v.scenario.code: v.bucket for v in M.classify(root)}
        self.assertEqual(base, moved)

    @staticmethod
    def _mirror(dst: Path) -> Path:
        """把真实仓库的判定输入面按原路径软复制到临时目录（只复制读得到的那几处）。"""
        for rel in M.QUEUE_PATHS_REL + (M.PREREQ_DOC_PATH_REL, M.PLAN_DOC_PATH_REL):
            src = REPO_ROOT / rel
            tgt = dst / rel
            tgt.parent.mkdir(parents=True, exist_ok=True)
            tgt.write_bytes(src.read_bytes())
        for rel in (M.SCENE_ROOT_REL, M.OPENSPEC_CHANGES_REL, M.OPENSPEC_ARCHIVE_REL):
            base = REPO_ROOT / rel
            if not base.is_dir():
                continue
            for p in base.iterdir():
                if p.is_dir():
                    (dst / rel / p.name).mkdir(parents=True, exist_ok=True)
                    for q in p.iterdir():
                        if q.is_dir():
                            (dst / rel / p.name / q.name).mkdir(parents=True, exist_ok=True)
        return dst


class SyntheticRegistry(unittest.TestCase):

    def test_坏行fail_loud_并指明行号(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / M.REGISTRY_PATH_REL
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{"code":"SC1","domain":"采购","aliases":["SC1"]}\n{ 坏\n',
                            encoding="utf-8")
            with self.assertRaises(M.RegistryError) as ctx:
                M.load_registry(root)
            self.assertIn("第 2 行", str(ctx.exception))

    def test_excludes缺来源即拒(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_registry(root, [_scenario("SC1", excludes=[{"phrase": "x"}])])
            with self.assertRaises(M.RegistryError):
                M.load_registry(root)

    def test_suspended缺日期即拒(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_registry(root, [_scenario("SC1", suspended="他说的（#463）")])
            with self.assertRaises(M.RegistryError):
                M.load_registry(root)

    def test_退休编号不制造永久差集(self):
        # tasks 1.3.3
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / M.PLAN_DOC_PATH_REL
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text(
                "### 🚀 加速启动总览\n\n"
                "| 月份 | 采购/供应链 | 运营/制造 | 工程研发 | 质量 | 财务 | 销售/BD |\n"
                "|---|---|---|---|---|---|---|\n"
                "| 2026-07 | SC1 | — | — | 〔Q5 已下架撤下〕 | — | — |\n",
                encoding="utf-8")
            _write_registry(root, [
                _scenario("SC1"),
                {"code": "Q5", "domain": "", "title": "已下架", "planned_month": "",
                 "aliases": [], "excludes": [], "suspended": "", "retired": True},
            ])
            self.assertEqual(M.lint_registry(root), ([], []))

    def test_排期表新增码而registry未跟则校验失败并点名(self):
        # tasks 1.3.1
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / M.PLAN_DOC_PATH_REL
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text(
                "### 🚀 加速启动总览\n\n"
                "| 月份 | 采购/供应链 | 运营/制造 | 工程研发 | 质量 | 财务 | 销售/BD |\n"
                "|---|---|---|---|---|---|---|\n"
                "| 2026-07 | SC1；SC9 | — | — | — | — | — |\n",
                encoding="utf-8")
            _write_registry(root, [_scenario("SC1")])
            missing, extra = M.lint_registry(root)
            self.assertEqual(missing, ["SC9"])
            self.assertEqual(extra, [])

    def test_中文标题改写而码集合未变则校验通过(self):
        # 🔴 tasks 1.3.2：防校验器自身易碎。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / M.PLAN_DOC_PATH_REL
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text(
                "### 🚀 加速启动总览\n\n"
                "| 月份 | 采购/供应链 | 运营/制造 | 工程研发 | 质量 | 财务 | 销售/BD |\n"
                "|---|---|---|---|---|---|---|\n"
                "| 2026-07 | **SC1** ~~旧名~~〔v9 改内涵：另起一段中文，含脚注①〕 "
                "| — | — | — | — | — |\n",
                encoding="utf-8")
            _write_registry(root, [_scenario("SC1")])
            self.assertEqual(M.lint_registry(root), ([], []))


class SyntheticMatching(unittest.TestCase):

    def test_openspec归档包剥日期前缀后按首段比(self):
        self.assertEqual(M.package_head_segment("fi5-expense-audit-mvp"), "fi5")
        self.assertEqual(
            M.package_head_segment("2026-07-02-o2-kit-shortage-alert"), "o2")
        self.assertEqual(M.package_head_segment("fi10-inventory-writedown-mvp"), "fi10")

    def test_变更包按首段匹配_不递归不子串(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("fi10-inventory-writedown-mvp", "archive"):
                (root / M.OPENSPEC_CHANGES_REL / name).mkdir(parents=True, exist_ok=True)
            scenarios = [M.Scenario("FI1", "财务", "", "", ("FI1",), (), ""),
                         M.Scenario("FI10", "财务", "", "", ("FI10",), (), "")]
            got = M.scan_openspec(root, scenarios)
            self.assertEqual(got["FI1"], [])
            self.assertEqual(len(got["FI10"]), 1)

    def test_工程目录只扫一层不递归(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / M.SCENE_ROOT_REL / "采购部" / "SC1-供应商风险初筛" / "SC4-子目录"
             ).mkdir(parents=True, exist_ok=True)
            scenarios = [M.Scenario("SC1", "采购", "", "", ("SC1",), (), ""),
                         M.Scenario("SC4", "采购", "", "", ("SC4",), (), "")]
            got = M.scan_projects(root, scenarios)
            self.assertEqual(len(got["SC1"]), 1)
            self.assertEqual(got["SC4"], [],
                             "递归进了场景内部子目录——干草堆被无谓放大")

    def test_状态列提及不构成承接(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_registry(root, [_scenario("SC4"), _scenario("SC10")])
            _queue_file(root, M.QUEUE_PATHS_REL[0],
                        [("463", "**十四个场景：立行与排期（含 `SC4` 优先）**")])
            scenarios = M.load_registry(root)
            got = M.scan_queue(root, scenarios)
            self.assertEqual(len(got["SC4"]), 1)
            self.assertEqual(got["SC10"], [])


class OutputContract(unittest.TestCase):

    def test_三档各自可独立计数且数量出现在头部(self):
        verdicts = M.classify(REPO_ROOT)
        bk = M.buckets(verdicts)
        self.assertEqual(set(bk), {"三处皆无", "疑似已承接·待人确认", "已承接"})
        head = M.render_text(verdicts).splitlines()[1]
        for k in bk:
            self.assertIn(str(len(bk[k])), head)

    def test_范围声明恒在输出里(self):
        self.assertIn("不构成排期建议", M.render_text(M.classify(REPO_ROOT)))

    def test_已承接结论必须记名(self):
        for v in M.classify(REPO_ROOT):
            if v.bucket == "已承接":
                with self.subTest(code=v.scenario.code):
                    for e in v.accepted:
                        self.assertTrue(e.ref and e.alias)

    def test_json输出可被机器消费(self):
        payload = M.to_payload(M.classify(REPO_ROOT))
        self.assertEqual(payload["total"], 35)
        self.assertEqual(payload["counts"]["三处皆无"],
                         len(payload["unaccepted"]))
        json.dumps(payload, ensure_ascii=False)

    def test_判定路径零LLM(self):
        src = SCRIPT.read_text(encoding="utf-8")
        for token in ("anthropic", "openai", "claude.messages", "completion("):
            self.assertNotIn(token, src.lower())


# ===========================================================================
# sweep 第 13 类接入
#
# 🔴 **本组刻意落在本文件、不落 `test_工具-落库sweep.py`**：本次同批另有一条泳道要改
# `工具-落库sweep.py` 的 pathspec 提交段（看护批 B-0907_Y 的 A7），两边都往那个测试
# 文件里加用例必然撞。本类只依赖 sweep 的公开行为（常量 ＋ 三个函数），放这里不影响
# 覆盖面，且把冲突面收敛到零。
# ===========================================================================

class SweepClass13(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        name = "_commit_sweep_under_test"
        spec = importlib.util.spec_from_file_location(
            name, REPO_ROOT / "0-学习与工具" / "工具-落库sweep.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        cls.sweep = module

    def test_类号为13且不与既有类争号(self):
        src = (REPO_ROOT / "0-学习与工具" / "工具-落库sweep.py").read_text(encoding="utf-8")
        self.assertIn("第 13 类", src)
        # 第 13 类只应由本次这一处占用（章节头 ＋ 若干处引用），且第 14 类尚无人用。
        self.assertNotIn("第 14 类", src)

    def test_状态文件全部落在reports下_不入库(self):
        for attr in dir(self.sweep):
            if attr.startswith("PLAN_BACKPRESSURE_") and attr.endswith("_REL"):
                value = getattr(self.sweep, attr)
                if attr == "PLAN_BACKPRESSURE_SCRIPT_REL":
                    continue
                with self.subTest(attr=attr):
                    self.assertTrue(value.startswith("reports/"), value)
                    result = subprocess.run(
                        ["git", "check-ignore", value],
                        cwd=REPO_ROOT, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0,
                                     f"{value} 未被 .gitignore 覆盖，会污染工作区")

    def test_子进程调用而非进程内import(self):
        tree = ast.parse((REPO_ROOT / "0-学习与工具" / "工具-落库sweep.py")
                         .read_text(encoding="utf-8"))
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "_run_plan_backpressure_json")
        self.assertIn("subprocess.run", ast.unparse(fn))

    def test_本轮未巡检与已巡检且无告警在文件里长得不一样(self):
        # 🔴 spec `plan-backpressure-output`：两种情形的痕迹 MUST NOT 相同。
        # 第 8 类当年的事故形态就是它们长得一样。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "reports").mkdir(parents=True, exist_ok=True)
            scanned = self.sweep._mark_plan_backpressure_scan(root, "scanned", "")
            marker_after_scan = json.loads(
                (root / self.sweep.PLAN_BACKPRESSURE_SCAN_MARKER_REL)
                .read_text(encoding="utf-8"))
            skipped = self.sweep._mark_plan_backpressure_scan(root, "skipped", "整轮早退")
            marker_after_skip = json.loads(
                (root / self.sweep.PLAN_BACKPRESSURE_SCAN_MARKER_REL)
                .read_text(encoding="utf-8"))
        self.assertNotEqual(marker_after_scan, marker_after_skip)
        self.assertEqual(scanned["last_round_status"], "scanned")
        self.assertEqual(skipped["last_round_status"], "skipped")
        self.assertEqual(skipped["consecutive_skips"], 1)
        self.assertEqual(scanned["consecutive_skips"], 0)

    def test_连续未巡检计数归零于真的跑到那一轮(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "reports").mkdir(parents=True, exist_ok=True)
            for _ in range(3):
                self.sweep._mark_plan_backpressure_scan(root, "skipped", "早退")
            self.assertEqual(
                self.sweep._mark_plan_backpressure_scan(root, "scanned", "")["consecutive_skips"],
                0)

    def test_陈化催办阈值为7天且新出现的码不算陈化(self):
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        seen = {
            "R2": (now - timedelta(days=8)).isoformat(),
            "S4": (now - timedelta(days=1)).isoformat(),
        }
        stale = dict(self.sweep._plan_backpressure_stale_codes(seen))
        self.assertIn("R2", stale)
        self.assertNotIn("S4", stale)
        self.assertEqual(self.sweep.PLAN_BACKPRESSURE_STALE_DAYS, 7)

    def test_场景消失后再出现按新问题重新计时(self):
        # 🔴 否则它一回来就"已陈化 90 天"，催办立刻响，而那不是事实。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "reports").mkdir(parents=True, exist_ok=True)
            first = self.sweep._plan_backpressure_first_seen(root, {"R2"})
            self.sweep._plan_backpressure_first_seen(root, set())      # 被立行，消失
            again = self.sweep._plan_backpressure_first_seen(root, {"R2"})
        self.assertNotEqual(first["R2"], again["R2"])

    def test_同一批24小时内不重复推送(self):
        # spec：同一批未承接场景 MUST NOT 在 24 小时内产生第二次推送。
        self.assertEqual(self.sweep.PLAN_BACKPRESSURE_ALERT_INTERVAL_HOURS, 24.0)

    def test_暂缓复核周期为30天(self):
        self.assertEqual(self.sweep.PLAN_BACKPRESSURE_SUSPENDED_REVIEW_DAYS, 30)

    def test_告警正文含范围声明与并入审核提醒(self):
        payload = M.to_payload(M.classify(REPO_ROOT))
        codes = [d["code"] for d in payload["unaccepted"] if not d["suspended"]]
        text = self.sweep._render_plan_backpressure_alert(payload, codes)
        self.assertIn("不构成排期建议", text)
        self.assertIn("并入审核", text)

    def test_负例不触发任何自动的判据收紧(self):
        # 🔴 spec：负例 MUST NOT 触发任何自动的判据收紧。判据落在"sweep 里没有任何
        # 一条写 registry 的路径"上——收紧判据 ＝ 改 registry 的 aliases/excludes。
        src = (REPO_ROOT / "0-学习与工具" / "工具-落库sweep.py").read_text(encoding="utf-8")
        self.assertNotIn(M.REGISTRY_PATH_REL, src)


if __name__ == "__main__":
    unittest.main()
