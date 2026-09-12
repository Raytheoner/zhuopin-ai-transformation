"""opener 派出前查队列态——单测（openspec 包 `opener-batch-archive-precheck`，队列 §一 #397／#561，
design 决策点 1/2/3 Shao Peishen 2026-09-12 签认 (a)；apply 泳道 OP-0912-Z）。

三层各配正例与反例：
- **`工具-队列查询.py --include-archive --format json`**（spec `queue-query-archive-lookup`）：四态 A/B/C/D；
  🔴 C 态防回归——`#368` 归档行 `cells[5]` 原样复刻为 `[S:open][D:业] 🆕 2026-08-21 立行，未开工`，断言
  `status_field=="open"` 与 `done==True` **同时成立**：实现若改为读状态字段判归档行，`done` 变 False、本用例必红；
  假阳性防护（正文提及 `#368` 的行不算）；§四 同号不串；单文件多个 §一 表全扫；默认（不传新开关）输出逐字不变。
- **`工具-opener派出前校验.ps1`**：标题抽行号（`§四 #N(x)` 剥除、多行号、无行号）；合取语义；fail-open（Python 起不来）；`-Force`。
- **v1／v2 挂点**：SKIPPED 不起 claude、不进哨兵判定、不 break／不停泳道；整泳道跳空不 Start-Job；SKIPPED 进汇总与
  summary.txt／summary.json；退出码不受影响；`-DryRun` 显示跳过标记。

夹具＝临时 git 仓库（`工具-队列查询.py` 按 `--git-common-dir` 解析仓库根，同 `DualFileQueryTests` 惯例），
把 v1／v2／helper／查询工具四份脚本拷进 `<tmp>/0-学习与工具/`，队列真身与归档件按生产路径放；`claude` 用临时 PATH
里的桩 `claude.cmd` 顶替（同 `test_工具-opener批处理执行v2.py`）。
🔴 PowerShell 部分需要 Windows ＋ pwsh；没有即跳过那两组，Python 查询工具的用例不受影响。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent
QUERY = TOOLS_DIR / "工具-队列查询.py"
HELPER = TOOLS_DIR / "工具-opener派出前校验.ps1"
V1 = TOOLS_DIR / "工具-opener批处理执行.ps1"
V2 = TOOLS_DIR / "工具-opener批处理执行v2.ps1"

QUEUE_DIR_REL = Path("1-转型规划") / "0-全景路线图"
MECH_REL = QUEUE_DIR_REL / "跨桌任务队列-机制环境.md"
BIZ_REL = QUEUE_DIR_REL / "跨桌任务队列-业务场景.md"
ARCH_07_REL = QUEUE_DIR_REL / "跨桌任务队列-归档-202607.md"
ARCH_08_REL = QUEUE_DIR_REL / "跨桌任务队列-归档-202608.md"

HEADER_ONE = (
    "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
    "|---|------|--------|-------------|----------|------|--------|------|\n"
)
HEADER_FOUR = "| # | 事项 | 等谁 | 截止 |\n|---|------|------|------|\n"

MECH_FIXTURE = (
    "# 跨桌任务队列（机制环境）\n\n## 〇、协议\n\n（略）\n\n## 一、任务看板\n\n" + HEADER_ONE +
    "| 200 | 在办未完成行 | CC | 无 | 无 | [S:open][D:机] 🟢 可领 | 无 | 2026-09-01 |\n"
    "| 397 | 批处理派出前查归档（#396 治本） | CC | 无 | 无 | [S:blocked][D:机] 🟡 停在 design 审 | 无 | 2026-08-25 |\n"
    "| 395 | 已并入 #397，从未进归档 | CC | 无 | 无 | [S:done][D:机] ✅ 并入 #397 销号 | 无 | 2026-08-25 |\n"
    "\n## 二、待 commit 批次（CC 取活销行）\n\n| 批次 | 文件清单 | 说明 | 状态 |\n|------|---------|------|------|\n"
    "\n## 四、需 Shao Peishen 的动作（例外与拍板）\n\n" + HEADER_FOUR +
    "| 200 | §四 与 §一 同号、互不相干 | Shao Peishen | 不急 |\n"
)
BIZ_FIXTURE = (
    "# 跨桌任务队列（业务场景）\n\n## 一、任务看板\n\n" + HEADER_ONE +
    "| 201 | 业务侧在办行 | Cowork | 无 | 无 | [S:open][D:业] 待领 | 无 | 2026-09-01 |\n"
    "\n## 二、待 commit 批次（CC 取活销行）\n\n| 批次 | 文件清单 | 说明 | 状态 |\n|------|---------|------|------|\n"
)
# 归档 2026-07：live 写法的标题（`## 一、任务看板（已完成行）`）。
ARCH_07_FIXTURE = (
    "# 跨桌任务队列 · 归档 2026-07\n\n## 一、任务看板（已完成行）\n\n" + HEADER_ONE +
    "| 302 | 七月归档行 | CC | 无 | 无 | [S:done][D:机] ✅ | 无 | 2026-07-20 |\n"
    "\n## 四、需 Paul 的动作（已收口）\n\n" + HEADER_FOUR + "| 77 | 七月 §四 行 | — | — |\n"
)
# 归档 2026-08：复刻生产件结构——§二 在前；`## §一 …` H2 多表；`## §一 #214 状态续写` 无表；
# `## 2026-08-24 值周清扫迁入` 普通 H2 下挂 `### §一` H3 两表；`### §四` 内有编号 88。
# 🔴 #368 行 cells[1] 写销号、cells[5] 仍 `[S:open]`——生产件 L583 原样（design 取证二）。
ARCH_08_FIXTURE = (
    "# 跨桌任务队列 · 归档 2026-08\n\n"
    "## 二、待 commit 批次（已完成，按原文原样迁入）\n\n| 批次 | 文件清单 | 说明 | 状态 |\n|------|---------|------|------|\n"
    "| B-0801_x | `a.md` | 正文提到 #368 不算命中 | ✅ 已完成 |\n\n"
    "## §一 任务看板 · 2026-08-03 协议〇.8 专项清扫迁入（1 行）\n\n" + HEADER_ONE +
    "| 300 | 八月第一表 | CC | 无 | 无 | [S:done][D:机] ✅ | 无 | 2026-08-03 |\n\n"
    "## §一 任务看板 · 2026-08-04 增量清扫迁入（1 行）\n\n" + HEADER_ONE +
    "| 303 | 八月第二表 | CC | 无 | 无 | [S:done][D:机] ✅ | 无 | 2026-08-04 |\n\n"
    "## §一 #214 状态续写 · 2026-08-05 孤儿块原文迁入\n\n（一段没有表格的原文，提到 #368 与 #300）\n\n"
    "## 2026-08-24 值周清扫迁入（协议〇.8）\n\n本节按域分两表。\n\n"
    "### §一 任务看板 · 机制环境（2 行）\n\n" + HEADER_ONE +
    "| 363 | 结论同去向 §一 #368 | CC | 无 | 无 | [S:done][D:机] ✅ 见 #368 | 无 | 2026-08-21 |\n"
    "| 364 | 另一行正文也提 #368 两次：#368、#368 | CC | 无 | 无 | [S:done][D:机] ✅ | 无 | 2026-08-21 |\n\n"
    "### §一 任务看板 · 业务场景（1 行）\n\n" + HEADER_ONE +
    "| 368 | ✅ **[S:done] 整行销号（2026-08-22，② 由 Cowork 全景路线图线经 OP-0821-M 完成）** 质量域场景清单重审 | Cowork | 无 | 无 | [S:open][D:业] 🆕 2026-08-21 立行，未开工 | 无 | 2026-08-21 |\n\n"
    "### §四 需 Shao Peishen 的动作（已闭环）（1 行）\n\n" + HEADER_FOUR +
    "| 88 | §四 的 88，与 §一 无关；正文再提一次 #368 | Shao Peishen | 已闭环 |\n"
)

CLAUDE_STUB = "@echo off\r\necho STUB-ARGS: %*\r\necho OPENER_DONE\r\nexit /b 0\r\n"

HAS_PWSH = shutil.which("pwsh") is not None and os.name == "nt"


def _init_repo(root: Path, *, copy_runners: bool) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    tools = root / "0-学习与工具"
    tools.mkdir()
    shutil.copy(QUERY, tools / QUERY.name)
    if copy_runners:
        for f in (HELPER, V1, V2):
            shutil.copy(f, tools / f.name)
    (root / QUEUE_DIR_REL).mkdir(parents=True)
    (root / MECH_REL).write_text(MECH_FIXTURE, encoding="utf-8")
    (root / BIZ_REL).write_text(BIZ_FIXTURE, encoding="utf-8")
    (root / ARCH_07_REL).write_text(ARCH_07_FIXTURE, encoding="utf-8")
    (root / ARCH_08_REL).write_text(ARCH_08_FIXTURE, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)


def _line_of(path: Path, first_cell: str) -> int:
    """独立算出「首格为 first_cell 的行」的 1-based 行号，供断言用（不复用被测实现）。"""
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if re.match(r"^\|\s*" + re.escape(first_cell) + r"\s*\|", line):
            return i
    raise AssertionError(f"夹具里没有首格为 {first_cell} 的行：{path}")


# ══════════════════════════════════════════════════════════════════════════
# 一、工具-队列查询.py：--include-archive ＋ --format json
# ══════════════════════════════════════════════════════════════════════════

class QueryArchiveJsonTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _init_repo(self.root, copy_runners=False)

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(self.root / "0-学习与工具" / QUERY.name), *args],
            cwd=self.root, capture_output=True, text=True, encoding="utf-8",
        )

    def _json(self, row: str, *extra: str) -> dict:
        r = self._run("--row", row, "--section", "一", "--include-archive", "--format", "json", *extra)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return json.loads(r.stdout.strip().splitlines()[-1])

    # ---- 四态 ----
    def test_1_1_A态_live未完成_done为False(self):
        j = self._json("397")
        self.assertEqual((j["found"], j["carrier"], j["done"], j["reason"]), (True, "live", False, "live-open"))
        self.assertEqual(j["status_field"], "blocked")
        self.assertEqual(j["file"], MECH_REL.as_posix())

    def test_1_2_B态_live已done_从未进归档_也判done(self):
        j = self._json("395")
        self.assertEqual((j["carrier"], j["done"], j["reason"]), ("live", True, "live-done"))

    def test_1_3_C态_归档命中_判done_理由archived(self):
        j = self._json("368")
        self.assertEqual((j["found"], j["carrier"], j["done"], j["reason"]), (True, "archive", True, "archived"))
        self.assertEqual(j["file"], ARCH_08_REL.as_posix())

    def test_1_4_C态防回归_状态列仍open_但done恒True_不依赖cells5(self):
        """🔴 本包最关键的一条：归档 `#368` 的 cells[5] 是 `[S:open][D:业] 🆕 …`，实现若改成读状态字段，
        done 会变 False——本用例必须失败。两个断言缺一不可。"""
        j = self._json("368")
        self.assertEqual(j["status_field"], "open", "夹具或解析变了：cells[5] 机器字段应为 open")
        self.assertTrue(j["done"], "归档命中必须恒 done，不得参考 status_field")

    def test_1_5_D态_不存在的行号_unresolved_且done为False(self):
        j = self._json("9999")
        self.assertEqual((j["found"], j["carrier"], j["file"], j["line"]), (False, "none", None, None))
        self.assertEqual((j["done"], j["reason"]), (False, "unresolved"))

    def test_json_退出码_未命中也是0_不与读取失败共用(self):
        r = self._run("--row", "9999", "--section", "一", "--include-archive", "--format", "json")
        self.assertEqual(r.returncode, 0)

    # ---- 行定位判据 ----
    def test_1_9_假阳性防护_命中的是首格368那一行_不是正文提及的行(self):
        j = self._json("368")
        self.assertEqual(j["line"], _line_of(self.root / ARCH_08_REL, "368"))
        # 正文提及 #368 的行（363／364／§二 批次／§四 88）都不是命中对象。
        for other in ("363", "364", "88"):
            self.assertNotEqual(j["line"], _line_of(self.root / ARCH_08_REL, other))

    def test_1_10_章节归属_查节一88_不得命中归档节四的88(self):
        j = self._json("88")
        self.assertFalse(j["found"], j)
        self.assertEqual(j["reason"], "unresolved")

    def test_章节归属_live_节四同号不串_查节一200命中节一(self):
        j = self._json("200")
        self.assertEqual((j["carrier"], j["section"], j["reason"]), ("live", "一", "live-open"))
        self.assertEqual(j["line"], _line_of(self.root / MECH_REL, "200"))

    def test_1_11_单文件多个节一表_H2与H3混用_全部扫到(self):
        for row in ("300", "303", "363", "368"):
            j = self._json(row)
            self.assertEqual((j["carrier"], j["file"]), ("archive", ARCH_08_REL.as_posix()), row)
        j = self._json("302")
        self.assertEqual(j["file"], ARCH_07_REL.as_posix())

    def test_live优先于归档_A到D短路(self):
        """live 与归档同号时（理论上不该发生）live 结论优先——不会因为归档里有同号就误判 done。"""
        arch = self.root / ARCH_08_REL
        arch.write_text(arch.read_text(encoding="utf-8") +
                        "\n### §一 任务看板 · 补（1 行）\n\n" + HEADER_ONE +
                        "| 200 | 归档里也有个 200 | CC | 无 | 无 | [S:done][D:机] ✅ | 无 | 2026-08-30 |\n",
                        encoding="utf-8")
        j = self._json("200")
        self.assertEqual((j["carrier"], j["done"]), ("live", False))

    def test_不传include_archive时_json仍只查live_归档行unresolved(self):
        r = self._run("--row", "368", "--section", "一", "--format", "json")
        j = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual((j["found"], j["reason"]), (False, "unresolved"))
        self.assertNotIn(ARCH_08_REL.as_posix(), j["searched"])

    # ---- 默认行为逐字不变（决策点 5）----
    def test_2_5_默认不传新开关_未找到文案与退出码不变(self):
        r = self._run("--row", "368", "--section", "一")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(
            r.stdout,
            f"✗ 未找到 §一 中编号/批次为「368」的行（已查：{MECH_REL.as_posix()}、{BIZ_REL.as_posix()}）。\n",
        )

    def test_2_5_默认不传新开关_命中输出不变(self):
        r = self._run("--row", "397", "--section", "一")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(
            r.stdout,
            f"【命中于：{MECH_REL.as_posix()}】\n"
            "【§一 #397 · 状态列全文】\n"
            "[S:blocked][D:机] 🟡 停在 design 审\n"
            "\n【机器字段解析】状态＝blocked，域 机\n",
        )

    def test_text模式_include_archive_归档命中打判据提示(self):
        r = self._run("--row", "368", "--section", "一", "--include-archive")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn(f"【命中于：{ARCH_08_REL.as_posix()}】", r.stdout)
        self.assertIn("归档命中即完成", r.stdout)

    def test_help_列出两个新开关(self):
        r = self._run("--help")
        self.assertIn("--include-archive", r.stdout)
        self.assertIn("--format", r.stdout)


# ══════════════════════════════════════════════════════════════════════════
# 二、工具-opener派出前校验.ps1（helper 本体）
# ══════════════════════════════════════════════════════════════════════════

def _pwsh(script: str, cwd: Path, env: dict | None = None, timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=timeout,
    )


@pytest.mark.skipif(not HAS_PWSH, reason="需要 Windows ＋ PowerShell 7（pwsh）")
class HelperTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _init_repo(self.root, copy_runners=True)
        self.helper = self.root / "0-学习与工具" / HELPER.name

    def tearDown(self):
        self._tmp.cleanup()

    def _row_ids(self, title: str) -> list[int]:
        r = _pwsh(f". '{self.helper}'; (Get-OpenerQueueRowIds -Title '{title}') -join ','", self.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = r.stdout.strip()
        return [int(x) for x in out.split(",") if x]

    def _decide(self, titles: list[tuple[str, str]], force: bool = False) -> list[dict]:
        items = ", ".join(f"[pscustomobject]@{{Id='{i}';Title='{t}';Paste='CC';Text='x'}}" for i, t in titles)
        r = _pwsh(
            f". '{self.helper}'; $ops = @({items}); "
            f"$r = @(Set-OpenerDispatchDecision -Openers $ops -RepoRoot '{self.root}' -Quiet{' -Force' if force else ''}); "
            "$r | Select-Object Id, Skip, SkipReason, PrecheckNote, @{n='QueueRows';e={@($_.QueueRows)}} | ConvertTo-Json -AsArray -Depth 3",
            self.root,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return json.loads(r.stdout)

    def test_1_7_锚点排除_节四编号不进查询(self):
        self.assertEqual(self._row_ids("【CC】#353 apply：闭环形态——队列 #353／§四 #108(a)"), [353])

    def test_多行号_队列397与396_两个都抽到(self):
        self.assertEqual(self._row_ids("【CC】#397 批处理派出前查归档（#396 治本）——队列 #397／#396"), [397, 396])

    def test_1_6_无行号标题_抽不出_属正常形态(self):
        self.assertEqual(self._row_ids("【Cowork】队列每周清扫迁归档（本轮巡检移交件）——协议〇.8／§四 #44"), [])

    def test_节二批次引用被剥除(self):
        self.assertEqual(self._row_ids("收工登记——§二 B-0912_x／队列 #200"), [200])

    def test_四态映射_与告警文案可区分(self):
        rows = self._decide([
            ("A1", "x——队列 #397"), ("A2", "x——队列 #395"), ("A3", "x——队列 #368"),
            ("A4", "x——队列 #9999"), ("A5", "x——协议〇.8／§四 #44"),
        ])
        by = {r["Id"]: r for r in rows}
        self.assertFalse(by["A1"]["Skip"]); self.assertIn("live-open", by["A1"]["PrecheckNote"])
        self.assertTrue(by["A2"]["Skip"]); self.assertIn("live-done", by["A2"]["SkipReason"])
        self.assertTrue(by["A3"]["Skip"]); self.assertIn("archived@跨桌任务队列-归档-202608.md", by["A3"]["SkipReason"])
        self.assertFalse(by["A4"]["Skip"]); self.assertIn("unresolved", by["A4"]["PrecheckNote"])
        self.assertFalse(by["A5"]["Skip"]); self.assertIn("no-row-ref", by["A5"]["PrecheckNote"])
        # 1.6：「无行号」与「写了行号但查不到」文案可区分。
        self.assertNotEqual(by["A4"]["PrecheckNote"], by["A5"]["PrecheckNote"])
        self.assertNotIn("unresolved", by["A5"]["PrecheckNote"])

    def test_1_8_合取_仅一行done则派出_全部done才跳过(self):
        rows = self._decide([("A1", "x——队列 #368／#397"), ("A2", "x——队列 #368／#395"), ("A3", "x——队列 #368／#9999")])
        by = {r["Id"]: r for r in rows}
        self.assertFalse(by["A1"]["Skip"], by["A1"])   # archived ＋ live-open ⇒ 派出
        self.assertTrue(by["A2"]["Skip"], by["A2"])    # archived ＋ live-done ⇒ 跳过
        self.assertFalse(by["A3"]["Skip"], by["A3"])   # archived ＋ unresolved ⇒ 派出（unresolved 不算 done）
        self.assertEqual(by["A2"]["QueueRows"], [368, 395])

    def test_3_4_fail_open_查询工具缺失_派出并告警(self):
        (self.root / "0-学习与工具" / QUERY.name).unlink()
        rows = self._decide([("A1", "x——队列 #368")])
        self.assertFalse(rows[0]["Skip"])
        self.assertIn("precheck-failed", rows[0]["PrecheckNote"])

    def test_3_4_fail_open_查询工具崩溃_派出并告警(self):
        (self.root / "0-学习与工具" / QUERY.name).write_text("raise SystemExit('boom')\n", encoding="utf-8")
        rows = self._decide([("A1", "x——队列 #368")])
        self.assertFalse(rows[0]["Skip"])
        self.assertIn("precheck-failed", rows[0]["PrecheckNote"])

    def test_1_13_Force_全部不跳_留痕(self):
        rows = self._decide([("A1", "x——队列 #368")], force=True)
        self.assertFalse(rows[0]["Skip"])
        self.assertIn("[Force]", rows[0]["SkipReason"])


# ══════════════════════════════════════════════════════════════════════════
# 三、v1／v2 挂点（临时仓库 ＋ 桩 claude）
# ══════════════════════════════════════════════════════════════════════════

V1_PLAN = "\n".join([
    "# 本周计划（单测夹具）", "",
    "### A1 ·【Cowork】已归档的活——队列 #368", "", "▶ 粘贴端：Cowork", "", "```", "opener A1 正文", "```", "",
    "### A2 ·【CC】在办的活——队列 #200", "", "▶ 粘贴端：CC", "", "```", "opener A2 正文", "```", "",
    "### A3 ·【CC】无行号的活——协议〇.8／§四 #44", "", "▶ 粘贴端：CC", "", "```", "opener A3 正文", "```", "",
])
V2_PLAN = "\n".join([
    "# 波次计划（单测夹具）", "",
    "### A1 ·【CC】已归档的活——队列 #368", "", "粘贴端：CC ｜ 泳道：lane-skip", "", "```", "opener A1 正文", "```", "",
    "### A2 ·【CC】在办的活——队列 #200", "", "粘贴端：CC ｜ 泳道：lane-run", "", "```", "opener A2 正文", "```", "",
    "### A3 ·【CC】live 已 done——队列 #395", "", "粘贴端：CC ｜ 泳道：lane-run", "", "```", "opener A3 正文", "```", "",
    "### A4 ·【CC】无行号的活——协议〇.8／§四 #44", "", "粘贴端：CC ｜ 泳道：lane-run", "", "```", "opener A4 正文", "```", "",
])


@pytest.mark.skipif(not HAS_PWSH, reason="需要 Windows ＋ PowerShell 7（pwsh）")
class RunnerHookTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _init_repo(self.root, copy_runners=True)
        stub_dir = self.root / "stub"
        stub_dir.mkdir()
        (stub_dir / "claude.cmd").write_text(CLAUDE_STUB, encoding="utf-8")
        self.env = dict(os.environ)
        self.env["PATH"] = str(stub_dir) + os.pathsep + self.env.get("PATH", "")
        self.v1 = self.root / "0-学习与工具" / V1.name
        self.v2 = self.root / "0-学习与工具" / V2.name
        self.plan_v1 = self.root / "plan-v1.md"
        self.plan_v1.write_text(V1_PLAN, encoding="utf-8")
        self.plan_v2 = self.root / "plan-v2.md"
        self.plan_v2.write_text(V2_PLAN, encoding="utf-8")
        self.log_dir = self.root / "batch-log"

    def tearDown(self):
        self._tmp.cleanup()

    def _run_file(self, script: Path, args: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["pwsh", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script), *args],
            cwd=self.root, capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=self.env, timeout=timeout,
        )

    def _v1_log_dir(self) -> Path:
        dirs = sorted((self.root / "reports" / "opener-batch").glob("*"))
        self.assertEqual(len(dirs), 1, dirs)
        return dirs[0]

    # ---- v1 ----
    def test_v1_DryRun_显示跳过标记_不起session(self):
        r = self._run_file(self.v1, ["-Plan", str(self.plan_v1), "-DryRun"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertRegex(r.stdout, r"A1 \| Cowork \| ⏭ SKIPPED（#368 archived@跨桌任务队列-归档-202608\.md:\d+）")
        self.assertIn("将按序执行 2 个 opener：A2(CC) → A3(CC)　｜ SKIPPED 1 个：A1", r.stdout)
        self.assertFalse((self.root / "reports").exists())

    def test_1_12_v1_跳过不起claude_不判NO_SENTINEL_不break_退出码0(self):
        r = self._run_file(self.v1, ["-Plan", str(self.plan_v1), "-Yes"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        log_dir = self._v1_log_dir()
        self.assertFalse((log_dir / "A1.log").exists(), "被跳过的 A1 不得起 claude")
        self.assertTrue((log_dir / "A2.log").exists())
        self.assertTrue((log_dir / "A3.log").exists(), "A1 跳过后 A2/A3 须照常执行（不 break）")
        # 收尾提示的静态文案本身含「NO-SENTINEL」四字，只断言汇总表里没有任何一行被判成它。
        self.assertNotRegex(r.stdout, re.compile(r"^A\d+\s+\S+\s+NO-SENTINEL", re.MULTILINE))
        self.assertNotIn("停下（fail-loud", r.stdout)
        self.assertRegex(r.stdout, r"A1\s+Cowork\s+SKIPPED")
        skipped = (log_dir / "skipped.txt").read_text(encoding="utf-8-sig")
        self.assertIn("[skipped] A1 | #368 archived@跨桌任务队列-归档-202608.md", skipped)

    def test_v1_Force_全部照派_日志留痕(self):
        r = self._run_file(self.v1, ["-Plan", str(self.plan_v1), "-Yes", "-Force"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((self._v1_log_dir() / "A1.log").exists())
        self.assertIn("[Force] 归档校验已被绕过", r.stdout)

    def test_4_5_v1_停下时续跑提示是整行可粘贴命令(self):
        stub = self.root / "stub" / "claude.cmd"
        stub.write_text("@echo off\r\necho 没有哨兵\r\nexit /b 0\r\n", encoding="utf-8")
        r = self._run_file(self.v1, ["-Plan", str(self.plan_v1), "-Yes", "-FullAuto"])
        self.assertEqual(r.returncode, 1)
        self.assertIn("NO-SENTINEL", r.stdout)
        m = re.search(r"^\s*(powershell -ExecutionPolicy Bypass -Command \"& '.*?' -Plan '.*?' -Only A2,A3 -Yes -FullAuto\")\s*$",
                      r.stdout, re.MULTILINE)
        self.assertIsNotNone(m, "续跑提示须是整行 -Command 形态：\n" + r.stdout)
        self.assertIn(self.v1.name, m.group(1))  # 临时目录会以 8.3 短名出现，只比对文件名

    # ---- v2 ----
    def test_v2_DryRun_泳道清单只含实际将派出的成员(self):
        r = self._run_file(self.v2, ["-Plan", str(self.plan_v2), "-DryRun", "-LogDir", str(self.log_dir)])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("⏭ SKIPPED 2 个", r.stdout)
        self.assertIn("泳道 1 条", r.stdout)
        self.assertIn("◆ lane-run ：A2→A4（泳道内串行）", r.stdout)
        self.assertNotIn("◆ lane-skip", r.stdout)
        self.assertEqual((self.log_dir / "exit.txt").read_text(encoding="utf-8").strip(), "0")

    def test_1_12_5_2_v2_整泳道跳空不StartJob_泳道内跳过不停泳道_SKIPPED进summary(self):
        r = self._run_file(self.v2, ["-Plan", str(self.plan_v2), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir)])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("泳道「lane-skip」启动", r.stdout, "整泳道跳空不得 Start-Job")
        self.assertFalse((self.log_dir / "lane-skip-A1.log").exists())
        self.assertTrue((self.log_dir / "lane-run-A2.log").exists())
        self.assertFalse((self.log_dir / "lane-run-A3.log").exists(), "泳道内被跳过的 A3 不得起 claude")
        self.assertTrue((self.log_dir / "lane-run-A4.log").exists(), "A3 跳过后 A4 须照常执行（不停泳道）")
        summary = (self.log_dir / "summary.txt").read_text(encoding="utf-8")
        self.assertIn("SKIPPED=2", summary)
        self.assertRegex(summary, r"\[skipped\] A1 \| #368 archived@跨桌任务队列-归档-202608\.md:\d+")
        self.assertRegex(summary, r"\[skipped\] A3 \| #395 live-done@跨桌任务队列-机制环境\.md:\d+")
        self.assertIn("EXIT=0", summary)
        self.assertNotIn("NO-SENTINEL", summary)
        rows = json.loads((self.log_dir / "summary.json").read_text(encoding="utf-8"))
        by = {row["Id"]: row for row in rows}
        self.assertEqual(by["A1"]["Status"], "SKIPPED")
        self.assertEqual(by["A3"]["Status"], "SKIPPED")
        self.assertEqual(by["A2"]["Status"], "OK")
        self.assertEqual(by["A4"]["Status"], "OK")

    def test_5_4_v2_退出码不受跳过影响_有FAIL仍为1(self):
        (self.root / "stub" / "claude.cmd").write_text("@echo off\r\necho x\r\nexit /b 3\r\n", encoding="utf-8")
        r = self._run_file(self.v2, ["-Plan", str(self.plan_v2), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir)])
        self.assertEqual(r.returncode, 1)
        summary = (self.log_dir / "summary.txt").read_text(encoding="utf-8")
        self.assertIn("SKIPPED=2", summary)
        self.assertIn("FAIL(3)", summary)

    def test_v2_全部跳过_无泳道_退出码0_summary仍写(self):
        only = ["-Only", "A1,A3"]
        r = self._run_file(self.v2, ["-Plan", str(self.plan_v2), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir), *only])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("全部 opener 已 SKIPPED，无泳道可起", r.stdout)
        self.assertNotIn("启动", r.stdout)
        summary = (self.log_dir / "summary.txt").read_text(encoding="utf-8")
        self.assertIn("SKIPPED=2", summary)
        self.assertIn("EXIT=0", summary)

    def test_v2_Force_全部照派_Detach子进程也带Force(self):
        r = self._run_file(self.v2, ["-Plan", str(self.plan_v2), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir), "-Force"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((self.log_dir / "lane-skip-A1.log").exists())
        self.assertIn("[Force] 归档校验已被绕过", r.stdout)
        src = self.v2.read_text(encoding="utf-8")
        self.assertIn("if ($Force) { $childArgs += '-Force' }", src)

    def test_3_4_helper缺失_v1_v2_均fail_open_全部照派(self):
        (self.root / "0-学习与工具" / HELPER.name).unlink()
        r1 = self._run_file(self.v1, ["-Plan", str(self.plan_v1), "-Yes"])
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
        self.assertIn("helper 不存在", r1.stdout)
        self.assertTrue((self._v1_log_dir() / "A1.log").exists(), "helper 缺失时 A1 须照常派出")
        r2 = self._run_file(self.v2, ["-Plan", str(self.plan_v2), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir)])
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertTrue((self.log_dir / "lane-skip-A1.log").exists())
        self.assertIn("SKIPPED=0", (self.log_dir / "summary.txt").read_text(encoding="utf-8"))

    def test_变异守卫_抽掉v2挂点_已归档的A1会被照常派出(self):
        """🔴 恒真检验：把 v2 的 Set-OpenerDispatchDecision 调用换成空操作，A1 须回到「照常派出」。"""
        src = self.v2.read_text(encoding="utf-8")
        needle = "    $openers = @(Set-OpenerDispatchDecision -Openers @($openers) -RepoRoot $RepoRoot -Force:$Force)"
        self.assertIn(needle, src)
        self.v2.write_text(src.replace(needle, "    $openers = @($openers | ForEach-Object { $_ | Add-Member -NotePropertyName Skip -NotePropertyValue $false -PassThru })"), encoding="utf-8")
        r = self._run_file(self.v2, ["-Plan", str(self.plan_v2), "-Yes", "-StaggerSec", "0", "-LogDir", str(self.log_dir)])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((self.log_dir / "lane-skip-A1.log").exists(), "挂点抽掉后 A1 没被派出 ⇒ 正例是恒真的")


if __name__ == "__main__":
    unittest.main()
