"""`工具-队列行K2外置.py` 单测（队列 §一 `#552`，2026-09-10，CC 泳道 `552-k2-tool`）。

白盒：按路径 importlib 加载被测脚本，把 `REPO_ROOT` 指向临时目录——**不触碰真实
队列与真实外置件**。验收单来自 `#552` 行内与 2026-09-10 手写原型的两次实撞：

- ①「保留段选错致改后仍超闸」⇒ 报错、外置件一个字节不写、JSON 不产出。
- ②「重跑把同段追加两次」⇒ 第二次跑判为 ALREADY-IN-LOG，不重复追加。
- 只追加绝不覆盖 ⇒ 既有内容以前缀形式原样保留（变异检验点：把 `open(path, "a")`
  改成 `"w"` 时 `test_既有外置件只追加_旧内容锚点仍在` 与静态守卫用例同时转红）。
"""
from __future__ import annotations

import datetime
import importlib.util
import io
import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-队列行K2外置.py")
QUEUE_MECH_REL = "1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md"
QUEUE_BIZ_REL = "1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md"
LOG_DIR_REL = "1-转型规划/0-全景路线图/队列行日志"
TODAY = datetime.date(2026, 9, 10)
SEP = "━━━"

HEADER_1 = (
    "## 一、任务看板\n\n"
    "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
    "|---|---|---|---|---|---|---|---|\n"
)
HEADER_4 = (
    "\n## 四、需 Shao Peishen 的动作\n\n"
    "| # | 事项 | 等谁 | 截止 |\n"
    "|---|---|---|---|\n"
)


def _load():
    spec = importlib.util.spec_from_file_location("_k2_externalize_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _seg(tag: str, size: int) -> str:
    """造一段可辨识、且 UTF-8 字节数约为 size 的正文。"""
    body = f"{tag} " + "甲" * max(1, (size - len(tag.encode("utf-8")) - 1) // 3)
    return body


def _cell(*segments: str) -> str:
    return f" {SEP} ".join(segments)


def _row1(number: str, status: str) -> str:
    return f"| {number} | 任务{number} | CC | 输入 | 产出 | {status} | 触碰区 | 2026-09-10 |\n"


def _row4(number: str, item: str) -> str:
    return f"| {number} | {item} | Shao Peishen | 09-12 |\n"


class _Base(unittest.TestCase):
    def setUp(self):
        self.module = _load()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.module.REPO_ROOT = self.root
        (self.root / QUEUE_MECH_REL).parent.mkdir(parents=True, exist_ok=True)
        (self.root / LOG_DIR_REL).mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.tmp.cleanup()

    def write_queue(self, text: str, rel: str = QUEUE_MECH_REL):
        (self.root / rel).write_text(text, encoding="utf-8")

    def log(self, row: str, section: str = "一") -> Path:
        return self.module.log_path_for(section, row)

    def run_cli(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = self.module.main(list(argv), today=TODAY)
        return code, out.getvalue(), err.getvalue()

    def json_path(self, row: str, section: str = "一") -> Path:
        return self.root / self.module.DEFAULT_OUT_DIR_REL / f"{section}-#{row}.changes.json"


class 段切分与选段(_Base):
    def test_split_丢弃空段并去空白(self):
        self.assertEqual(self.module.split_segments(f"a {SEP}  b {SEP} "), ["a", "b"])

    def test_keep_解析正负序号并去重(self):
        self.assertEqual(self.module.parse_keep("1,-1,1", 4), [0, 3])

    def test_keep_越界即报错(self):
        with self.assertRaises(self.module.K2Error):
            self.module.parse_keep("5", 4)
        with self.assertRaises(self.module.K2Error):
            self.module.parse_keep("0", 4)

    def test_四区外置件命名带分区后缀(self):
        self.assertEqual(self.log("122", "四").name, "#122-四.md")
        self.assertEqual(self.log("455").name, "#455.md")


class 计划与结构断言(_Base):
    def setUp(self):
        super().setUp()
        self.cell = _cell("[S:open][D:机] 首段", _seg("二", 300), _seg("三", 300), "末段")
        self.write_queue(HEADER_1 + _row1("9", self.cell))

    def test_plan_不写任何文件(self):
        code, out, _ = self.run_cli("--row", "9")
        self.assertEqual(code, 0)
        self.assertIn("共 4 段", out)
        self.assertIn("EXTERNALIZE", out)
        self.assertFalse(self.log("9").exists())
        self.assertFalse(self.json_path("9").exists())

    def test_段数断言失败即拒绝且不写(self):
        code, _, err = self.run_cli("--row", "9", "--apply", "--expect-segments", "3", "--who", "T")
        self.assertEqual(code, 2)
        self.assertIn("段数断言失败", err)
        self.assertFalse(self.log("9").exists())
        self.assertFalse(self.json_path("9").exists())

    def test_首段不保留即拒绝(self):
        code, _, err = self.run_cli("--row", "9", "--apply", "--expect-segments", "4", "--who", "T", "--keep", "2,-1")
        self.assertEqual(code, 2)
        self.assertIn("首段必须保留", err)
        self.assertFalse(self.log("9").exists())

    def test_一区首段不带机器字段即拒绝(self):
        self.write_queue(HEADER_1 + _row1("9", _cell("没有机器字段的首段", "二", "三")))
        code, _, err = self.run_cli("--row", "9", "--apply", "--expect-segments", "3", "--who", "T")
        self.assertEqual(code, 2)
        self.assertIn("[S:", err)

    def test_单段格无中间段可外置(self):
        self.write_queue(HEADER_1 + _row1("9", "[S:open][D:机] 只有一段"))
        code, _, err = self.run_cli("--row", "9", "--apply", "--expect-segments", "1", "--who", "T")
        self.assertEqual(code, 2)
        self.assertIn("只有 1 段", err)

    def test_塌列行拒绝(self):
        self.write_queue(HEADER_1 + f"| 9 | 任务 | CC | 输入 | {self.cell} | 触碰区 | 2026-09-10 |\n")
        code, _, err = self.run_cli("--row", "9")
        self.assertEqual(code, 2)
        self.assertIn("列数", err)

    def test_两分区都命中时不猜(self):
        self.write_queue(HEADER_1 + _row1("9", self.cell) + HEADER_4 + _row4("9", "事项"))
        code, _, err = self.run_cli("--row", "9")
        self.assertEqual(code, 2)
        self.assertIn("不止一处", err)
        code, out, _ = self.run_cli("--row", "9", "--section", "一")
        self.assertEqual(code, 0)
        self.assertIn("§一 #9", out)

    def test_行不存在(self):
        code, _, err = self.run_cli("--row", "77")
        self.assertEqual(code, 2)
        self.assertIn("没找到", err)


class 真写与回读(_Base):
    def setUp(self):
        super().setUp()
        self.first = "[S:open][D:机] 首段结论"
        self.s2, self.s3 = _seg("二段", 600), _seg("三段", 600)
        self.last = "末段收口"
        self.cell = _cell(self.first, self.s2, self.s3, self.last)
        self.write_queue(HEADER_1 + _row1("9", self.cell))

    def apply(self, *extra):
        return self.run_cli("--row", "9", "--apply", "--expect-segments", "4", "--who", "CC T", *extra)

    def test_首次外置_创建外置件并产出JSON(self):
        code, out, err = self.apply()
        self.assertEqual(code, 0, err)
        log_text = self.log("9").read_text(encoding="utf-8")
        self.assertTrue(log_text.startswith("---\n"))
        self.assertIn(self.s2, log_text)
        self.assertIn(self.s3, log_text)
        self.assertIn("第 2、3 段", log_text)
        payload = json.loads(self.json_path("9").read_text(encoding="utf-8"))
        self.assertEqual(list(payload), ["set"])
        new_cell = payload["set"]["状态"]
        self.assertTrue(new_cell.startswith(self.first))
        self.assertTrue(new_cell.endswith(self.last))
        self.assertNotIn(self.s2, new_cell)
        self.assertIn("📎 **2 段已于 2026-09-10 外置**", new_cell)
        self.assertIn("md5:", new_cell)
        self.assertIn("本格只留原第 1、4 段（共 4 段）", new_cell)
        self.assertIn(f"`{LOG_DIR_REL}/#9.md`", new_cell)
        self.assertLess(len(new_cell.encode("utf-8")), self.module.ROW_LENGTH_CAP_BYTES)
        self.assertIn("[OK]", out)
        self.assertIn("edit-row", out)

    def test_指针里的md5与外置件一致(self):
        self.apply()
        import hashlib
        real = hashlib.md5(self.log("9").read_text(encoding="utf-8").encode("utf-8")).hexdigest()[:8]
        new_cell = json.loads(self.json_path("9").read_text(encoding="utf-8"))["set"]["状态"]
        self.assertIn(f"md5:{real}", new_cell)

    def test_既有外置件只追加_旧内容锚点仍在(self):
        old = "---\ntitle: 既有\n---\n\n# 旧批次\n\n这是 OP-0910-R 十几分钟前刚写的建造对账全文，一个字都不能少。\n"
        self.log("9").write_text(old, encoding="utf-8")
        code, _, err = self.apply()
        self.assertEqual(code, 0, err)
        new = self.log("9").read_text(encoding="utf-8")
        self.assertTrue(new.startswith(old), "既有内容必须以前缀形式原样保留——覆盖即此处转红")
        self.assertGreater(len(new), len(old))
        self.assertIn(self.s2, new)

    def test_既有外置件过小视为残骸停手(self):
        self.log("9").write_text("---\n", encoding="utf-8")
        code, _, err = self.apply()
        self.assertEqual(code, 2)
        self.assertIn("残骸", err)
        self.assertEqual(self.log("9").read_text(encoding="utf-8"), "---\n")
        self.assertFalse(self.json_path("9").exists())

    def test_实撞2_重跑不把同段追加两次(self):
        self.apply()
        first_log = self.log("9").read_text(encoding="utf-8")
        # 模拟 edit-row 尚未落格（队列里仍是旧格）就再跑一次
        code, out, err = self.apply()
        self.assertEqual(code, 0, err)
        second_log = self.log("9").read_text(encoding="utf-8")
        self.assertEqual(first_log, second_log, "第二次跑不得再写外置件")
        self.assertEqual(second_log.count(self.s2), 1)
        self.assertIn("ALREADY-IN-LOG", out)
        new_cell = json.loads(self.json_path("9").read_text(encoding="utf-8"))["set"]["状态"]
        self.assertIn("本次未重复追加", new_cell)
        self.assertIn("工具第 1 批", new_cell)

    def test_实撞1_保留段选错仍超闸_不写不产出(self):
        huge_last = _seg("巨末段", 4200)
        self.write_queue(HEADER_1 + _row1("9", _cell(self.first, self.s2, self.s3, huge_last)))
        code, _, err = self.apply()
        self.assertEqual(code, 2)
        self.assertIn("仍超闸", err)
        self.assertFalse(self.log("9").exists(), "超闸时外置件一个字节都不能写")
        self.assertFalse(self.json_path("9").exists())

    def test_实撞1_对既有外置件同样一个字节不写(self):
        old = "---\ntitle: 既有\n---\n\n# 旧批次 旧内容旧内容旧内容旧内容旧内容旧内容旧内容\n"
        self.log("9").write_text(old, encoding="utf-8")
        huge_last = _seg("巨末段", 4200)
        self.write_queue(HEADER_1 + _row1("9", _cell(self.first, self.s2, self.s3, huge_last)))
        code, _, _ = self.apply()
        self.assertEqual(code, 2)
        self.assertEqual(self.log("9").read_text(encoding="utf-8"), old)

    def test_既有指针段并入新指针_不写进外置件(self):
        old_pointer = f"📎 **3 段已于 2026-09-09 外置**（md5:deadbeef）见 `{LOG_DIR_REL}/#9.md`；本格只留首段＋末段。"
        old = "---\ntitle: 既有\n---\n\n# 第 1 批\n\n旧段原文旧段原文旧段原文旧段原文旧段原文旧段原文\n"
        self.log("9").write_text(old, encoding="utf-8")
        self.write_queue(HEADER_1 + _row1("9", _cell(self.first, old_pointer, self.s3, self.last)))
        code, out, err = self.apply()
        self.assertEqual(code, 0, err)
        self.assertIn("POINTER→并入新指针", out)
        log_text = self.log("9").read_text(encoding="utf-8")
        # 旧指针段自本格移除，但其原文（含旧 md5）要在外置件里留档——"原文原样"不留缺口
        self.assertIn("deadbeef", log_text)
        self.assertIn("自本格移除的旧指针段原文", log_text)
        self.assertEqual(log_text.count("deadbeef"), 1)
        self.assertIn(self.s3, log_text)
        # 重跑：旧指针段已在件内，不再重录
        self.write_queue(HEADER_1 + _row1("9", _cell(self.first, old_pointer, self.s3, self.last)))
        code2, _, _ = self.apply()
        self.assertEqual(code2, 0)
        self.assertEqual(self.log("9").read_text(encoding="utf-8"), log_text)
        new_cell = json.loads(self.json_path("9").read_text(encoding="utf-8"))["set"]["状态"]
        self.assertNotIn("deadbeef", new_cell)
        self.assertIn("1 条指针段已并入本指针", new_cell)
        self.assertEqual(new_cell.count("📎"), 1)

    def test_自定义keep_保留多段(self):
        code, _, err = self.apply("--keep", "1,3,-1")
        self.assertEqual(code, 0, err)
        new_cell = json.loads(self.json_path("9").read_text(encoding="utf-8"))["set"]["状态"]
        self.assertIn(self.s3, new_cell)
        self.assertNotIn(self.s2, new_cell)
        self.assertIn("本格只留原第 1、3、4 段", new_cell)
        self.assertNotIn(self.s3, self.log("9").read_text(encoding="utf-8"))

    def test_四区行_JSON键为事项且外置件带分区后缀(self):
        item = _cell("四区首段", _seg("四二", 300), "四末")
        self.write_queue(HEADER_1 + _row1("9", self.cell) + HEADER_4 + _row4("3", item))
        code, _, err = self.run_cli("--row", "3", "--apply", "--expect-segments", "3", "--who", "T")
        self.assertEqual(code, 0, err)
        self.assertTrue(self.log("3", "四").exists())
        payload = json.loads(self.json_path("3", "四").read_text(encoding="utf-8"))
        self.assertIn("事项", payload["set"])

    def test_业务场景文件里的行也能找到(self):
        self.write_queue(HEADER_1, QUEUE_MECH_REL)
        self.write_queue(HEADER_1 + _row1("12", self.cell), QUEUE_BIZ_REL)
        code, out, _ = self.run_cli("--row", "12")
        self.assertEqual(code, 0)
        self.assertIn(QUEUE_BIZ_REL, out)

    def test_verify_落格前不一致_落格后一致(self):
        self.apply()
        jp = str(self.json_path("9"))
        code, out, _ = self.run_cli("--verify-json", jp)
        self.assertEqual(code, 1)
        self.assertIn("≠", out)
        new_cell = json.loads(self.json_path("9").read_text(encoding="utf-8"))["set"]["状态"]
        self.write_queue(HEADER_1 + _row1("9", new_cell))  # 模拟 edit-row 已落格
        code, out, _ = self.run_cli("--verify-json", jp)
        self.assertEqual(code, 0, out)
        self.assertIn("✓", out)


class 只追加写函数(_Base):
    def test_文件在读后被改动即停手(self):
        p = self.root / "x.md"
        p.write_text("A" * 100, encoding="utf-8")
        with self.assertRaises(self.module.K2Error):
            self.module.append_only_write(p, "B" * 100, "追加")
        self.assertEqual(p.read_text(encoding="utf-8"), "A" * 100)

    def test_不存在时创建_存在时追加(self):
        p = self.root / "sub" / "y.md"
        out = self.module.append_only_write(p, "", "头" * 40)
        self.assertEqual(out, "头" * 40)
        out2 = self.module.append_only_write(p, "头" * 40, "尾")
        self.assertEqual(out2, "头" * 40 + "尾")


class 静态守卫_源码里没有覆盖式写盘(unittest.TestCase):
    """变异检验的常驻形态：把追加改成覆盖，本用例独立于行为测试转红。"""

    def test_open模式只有a与x(self):
        src = SCRIPT.read_text(encoding="utf-8")
        modes = re.findall(r'\.open\(\s*"([a-z+]+)"', src)
        self.assertTrue(modes, "源码应至少有一处 .open(")
        self.assertTrue(set(modes) <= {"a", "x"}, f"外置件写盘只许 a/x 模式，实际：{modes}")

    def test_write_text只用于JSON产物(self):
        src = SCRIPT.read_text(encoding="utf-8")
        calls = re.findall(r"(\w+)\.write_text\(", src)
        self.assertEqual(calls, ["out_path"], f"write_text 只许写 JSON 产物，实际：{calls}")


if __name__ == "__main__":
    unittest.main()
