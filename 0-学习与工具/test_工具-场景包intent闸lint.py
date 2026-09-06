"""`工具-场景包intent闸lint.py` 单测（队列 §一 `#436` ⑶① ／ `OP-0906-S`）。

在临时目录里合成一个最小仓库（`4-数字员工/<部门>/<场景>/` ＋ `openspec/changes/<包>/`），
逐形态调 `scan()`——不触碰真实仓库文件。

🔴 **本文件存在的理由与 `test_工具-引导样板lint.py` 同**：这道闸对真实仓库首跑就是绿的
（存量已按三层豁免冻结），对真实仓库跑一遍永远证明不了它还认得违规。故五种形态逐个复现，
**外加两条防误伤回归**——机制类包（正文引用了场景目录但身份不属该场景）与长码优先
（`sc10-…` 不得被 `SC1` 抢走），这两条正是首跑时把 5 个机制类包从违规名单里摘出来的判据。
"""
from __future__ import annotations

import datetime as _dt
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-场景包intent闸lint.py")


def _load_module():
    name = "_intent_gate_under_test"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    # 🔴 必须先进 sys.modules 再 exec：被测模块用了 @dataclass，而
    # `dataclasses._is_type` 会按 `cls.__module__` 回查 `sys.modules`，
    # 查不到就 `AttributeError: 'NoneType' object has no attribute '__dict__'`。
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


M = _load_module()

TODAY = _dt.date(2026, 9, 6)          # 豁免期内
AFTER_DEADLINE = _dt.date(2026, 11, 1)  # 2026-10-31 之后

INTENT_CONFIRMED = """---
title: "SC4 intent"
status: 已确认
---

## 一、M2 自查事实
## 二、已定
## 三、待专员
"""

INTENT_DRAFT = INTENT_CONFIRMED.replace("status: 已确认", "status: 待确认")
INTENT_NO_STATUS = INTENT_CONFIRMED.replace("status: 已确认\n", "")


class _Repo:
    """最小合成仓库。"""

    def __init__(self, tmp: Path):
        self.root = tmp

    def scene(self, dept: str, dirname: str, *, intent: str | None = None,
              claude_md: str | None = None) -> str:
        d = self.root / M.SCENE_ROOT_NAME / dept / dirname
        d.mkdir(parents=True, exist_ok=True)
        if intent is not None:
            (d / "intent.md").write_text(intent, encoding="utf-8")
        if claude_md is not None:
            (d / "CLAUDE.md").write_text(claude_md, encoding="utf-8")
        return f"{M.SCENE_ROOT_NAME}/{dept}/{dirname}"

    def package(self, name: str, *, proposal: str = "", tasks: str = "",
                caps: tuple[str, ...] = ()) -> Path:
        p = self.root / M.CHANGES_REL / name
        p.mkdir(parents=True, exist_ok=True)
        (p / "proposal.md").write_text(proposal, encoding="utf-8")
        (p / "tasks.md").write_text(tasks, encoding="utf-8")
        for cap in caps:
            (p / "specs" / cap).mkdir(parents=True, exist_ok=True)
            (p / "specs" / cap / "spec.md").write_text("# spec\n", encoding="utf-8")
        return p


class IntentGateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = _Repo(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    # ── 五例（派单件 (ii).4 点名）──────────────────────────────────────────

    def test_有intent且已确认_放行(self):
        rel = self.repo.scene("采购部", "SC20-新场景甲", intent=INTENT_CONFIRMED)
        self.repo.package("sc20-new-scene", proposal=f"改 `{rel}/src/x.py`")
        rep = M.scan(self.repo.root, TODAY)
        self.assertEqual(rep.violations, [], rep.violations)
        self.assertEqual(len(rep.passed), 1)

    def test_有intent但未确认_违规(self):
        rel = self.repo.scene("采购部", "SC20-新场景甲", intent=INTENT_DRAFT)
        self.repo.package("sc20-new-scene", proposal=f"改 `{rel}/src/x.py`")
        rep = M.scan(self.repo.root, TODAY)
        self.assertEqual(len(rep.violations), 1, rep.violations)
        self.assertIn("不是 `已确认`", rep.violations[0])
        self.assertIn("sc20-new-scene", rep.violations[0])

    def test_无intent_违规且点名期望路径(self):
        rel = self.repo.scene("采购部", "SC20-新场景甲")
        self.repo.package("sc20-new-scene", proposal=f"改 `{rel}/src/x.py`")
        rep = M.scan(self.repo.root, TODAY)
        self.assertEqual(len(rep.violations), 1, rep.violations)
        self.assertIn(f"{rel}/intent.md", rep.violations[0])
        self.assertIn("zhuopin-requirement-grill", rep.violations[0])

    def test_豁免名单内_放行(self):
        rel = self.repo.scene("采购部", "SC4-合同条款自动提取与审核")
        self.repo.package("sc4-contract-clause-extraction", proposal=f"改 `{rel}/`")
        rep = M.scan(self.repo.root, TODAY)
        self.assertEqual(rep.violations, [], rep.violations)
        self.assertEqual(len(rep.exempted), 1)
        self.assertIn("存量包级", rep.exempted[0])

    def test_到期后豁免失效_转违规(self):
        rel = self.repo.scene("采购部", "SC4-合同条款自动提取与审核")
        self.repo.package("sc4-contract-clause-extraction", proposal=f"改 `{rel}/`")
        rep = M.scan(self.repo.root, AFTER_DEADLINE)
        self.assertEqual(rep.exempted, [], rep.exempted)
        self.assertEqual(len(rep.violations), 1, rep.violations)
        self.assertIn("缺 `", rep.violations[0])

    # ── 两条防误伤回归（首跑时正是它们把 5 个机制类包摘出违规名单）────────

    def test_机制类包只引用场景路径_不适用本闸(self):
        rel = self.repo.scene("采购部", "SC20-新场景甲")   # 没有 intent.md
        self.repo.package("queue-domain-routing",
                          proposal=f"受影响面：`{rel}/scripts/x.py`",
                          caps=("queue-dual-file-topology", "platform-oem-isolation"))
        rep = M.scan(self.repo.root, TODAY)
        self.assertEqual(rep.violations, [], rep.violations)
        self.assertEqual(len(rep.mechanism_refs), 1)
        self.assertIn("SC20", rep.mechanism_refs[0])

    def test_长码优先_SC10不被SC1抢走(self):
        rel1 = self.repo.scene("采购部", "SC1-供应商风险初筛")
        rel10 = self.repo.scene("采购部", "SC10-BOM评审与物料库管控", intent=INTENT_CONFIRMED)
        self.repo.package("sc10-bom-x", proposal=f"改 `{rel10}/` 与 `{rel1}/`")
        rep = M.scan(self.repo.root, TODAY)
        self.assertEqual(rep.violations, [], rep.violations)
        self.assertEqual(rep.passed, ["sc10-bom-x → SC10"])

    # ── 其余判据 ──────────────────────────────────────────────────────────

    def test_深化类永久豁免_不随到期日失效(self):
        rel = self.repo.scene("采购部", "SC8-客户订单交期智能承诺")
        self.repo.package("sc8-material-board-view", proposal=f"改 `{rel}/sc8/x.py`")
        for day in (TODAY, AFTER_DEADLINE):
            rep = M.scan(self.repo.root, day)
            self.assertEqual(rep.violations, [], f"{day}: {rep.violations}")
            self.assertIn("深化类·永久", rep.exempted[0])

    def test_部署状态段作为附加深化信号(self):
        rel = self.repo.scene("运营部", "O5-新运营场景",
                              claude_md="# x\n\n## 部署状态（2026-09-01）\n- 已上线\n")
        self.repo.package("o5-something", proposal=f"改 `{rel}/`")
        rep = M.scan(self.repo.root, AFTER_DEADLINE)
        self.assertEqual(rep.violations, [], rep.violations)
        self.assertIn("「部署状态」段", rep.exempted[0])

    def test_capability前缀也算场景身份(self):
        rel = self.repo.scene("财务部", "FI20-新财务场景")
        self.repo.package("recon-mvp-2026", proposal=f"改 `{rel}/`",
                          caps=("fi20-match-engine",))
        rep = M.scan(self.repo.root, TODAY)
        self.assertEqual(len(rep.violations), 1, rep.violations)
        self.assertIn("spec capability 前缀", rep.violations[0])

    def test_intent缺status字段_违规(self):
        rel = self.repo.scene("采购部", "SC20-新场景甲", intent=INTENT_NO_STATUS)
        self.repo.package("sc20-new-scene", proposal=f"改 `{rel}/`")
        rep = M.scan(self.repo.root, TODAY)
        self.assertEqual(len(rep.violations), 1, rep.violations)
        self.assertIn("无 `status:` 字段", rep.violations[0])

    def test_archive目录不扫(self):
        rel = self.repo.scene("采购部", "SC20-新场景甲")
        p = self.repo.root / M.CHANGES_REL / "archive" / "2026-09-01-sc20-old"
        p.mkdir(parents=True)
        (p / "proposal.md").write_text(f"改 `{rel}/`", encoding="utf-8")
        rep = M.scan(self.repo.root, TODAY)
        self.assertEqual(rep.violations, [], rep.violations)
        self.assertEqual(rep.scanned_packages, 0)

    def test_frontmatter解析(self):
        self.assertEqual(M.read_frontmatter_status(INTENT_CONFIRMED), "已确认")
        self.assertEqual(M.read_frontmatter_status('---\nstatus: "已确认"\n---\n'), "已确认")
        self.assertIsNone(M.read_frontmatter_status("no frontmatter\nstatus: 已确认\n"))
        self.assertIsNone(M.read_frontmatter_status(INTENT_NO_STATUS))

    # ── 真实仓库：首跑必须零违规（「先确认清零、再关门」的机器化留痕）────

    def test_真实仓库首跑零违规(self):
        rep = M.scan(M.REPO_ROOT, TODAY)
        self.assertEqual(rep.violations, [], "\n".join(rep.violations))
        self.assertGreater(rep.scanned_packages, 0)
        self.assertGreater(rep.scenes, 0)


if __name__ == "__main__":
    unittest.main()
