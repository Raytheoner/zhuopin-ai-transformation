from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path

import pytest


TOOL = Path(__file__).with_name("工具-需求与变更包门禁lint.py")


def load_tool():
    spec = importlib.util.spec_from_file_location("requirements_change_gate", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_repo(tmp_path: Path) -> Path:
    root = tmp_path
    for folder in ("openspec/changes/sc1-new-feature/specs/sc1-core",
                   "openspec/specs/sc1-core",
                   "4-数字员工/采购部/SC1-example/tests",
                   "docs/requirements", "0-学习与工具",
                   "1-转型规划/0-全景路线图"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    (root / "openspec/config.yaml").write_text(
        "schema: spec-driven\nmodes:\n  feature:\n    mode: feature\n"
        "    requires: intent proposal design specs tasks pytest\n"
        "  refinement:\n    mode: refinement\n"
        "    requires: proposal specs pytest tasks\n"
        "rules:\n  proposal:\n"
        "    - MANDATORY 知识资产三问\n"
        "    - MANDATORY 验收与晋档条件\n"
        "    - MANDATORY 退休哪一个既有守卫\n"
        "    - MANDATORY .gitignore\n"
        "    - MANDATORY intent.md\n"
        "    - docs/codex/rules/场景建造与合规.md\n", encoding="utf-8")
    (root / "docs/requirements/INDEX.md").write_text(
        "# 六部门需求与规格索引\n"
        "## 表一：能力与主规格索引\n"
        "| 能力/场景ID | 部门/域 | 档位 | openspec/specs/路径 | 对应子项目 pytest 测试路径 | 状态 |\n"
        "|---|---|---|---|---|---|\n"
        "| `SC1` | 采购 | 档1 | `openspec/specs/sc1-core/spec.md` | `4-数字员工/采购部/SC1-example/tests/test_core.py` | 主规格已建 |\n"
        "## 表二：在途变更包四态表\n"
        "| 变更包名 | 部门/域 | 模式 (feature/refinement) | 四态标签 | tasks 进度 | 外部卡点/队列行指针 |\n"
        "|---|---|---|---|---:|---|\n"
        "| `sc1-new-feature` | 采购 | feature | active_mvp | 1/2 | — |\n"
        "## 表三：全景规划与原队列承接\n"
        "| 场景ID | 部门/域 | 权威排期 | 原队列/暂缓依据 | 构建与验收边界 |\n"
        "|---|---|---|---|---|\n"
        "| SC1 | 采购 | — | #1 | mock不代专业与生产验收 |\n",
        encoding="utf-8")
    (root / "openspec/specs/sc1-core/spec.md").write_text("## Requirements\n", encoding="utf-8")
    (root / "1-转型规划/0-全景路线图/场景registry-规划倒逼扫描器.jsonl").write_text(
        '{"code":"SC1","domain":"采购"}\n', encoding="utf-8")
    (root / "4-数字员工/采购部/SC1-example/tests/test_core.py").write_text(
        "def test_core(): assert True\n", encoding="utf-8")
    change = root / "openspec/changes/sc1-new-feature"
    (change / "proposal.md").write_text(
        "## Why\n新能力。\n\n## 知识资产三问（强制，全景规划 §1.4 第 2 条）\n"
        "默会经验：判断阈值。持有人及 backup：甲、乙。提取方法：专家批改。\n\n"
        "## 验收与晋档条件（强制，四档口径）\n"
        "档1 mock，晋档条件：业务签认；价值指标：风险型。\n\n"
        "## .gitignore 覆盖\n不新增自动生成文件；不适用。\n", encoding="utf-8")
    (change / "design.md").write_text("## Decisions\n已审。\n", encoding="utf-8")
    (change / "tasks.md").write_text("- [x] 1. 测试\n- [ ] 2. 实现\n", encoding="utf-8")
    (change / "specs/sc1-core/spec.md").write_text(
        "## ADDED Requirements\n### Requirement: core\nSHALL work.\n"
        "#### Scenario: one\n- WHEN run\n- THEN work\n", encoding="utf-8")
    (root / "0-学习与工具/需求与变更包门禁lint-baseline.json").write_text(
        json.dumps({"schema_version": 1, "initial_legacy": {}, "legacy": {}},
                   ensure_ascii=False), encoding="utf-8")
    return root


def codes(root: Path) -> set[str]:
    return {item.code for item in load_tool().check_repository(root)}


def test_valid_feature_fixture_passes(tmp_path):
    assert codes(fixture_repo(tmp_path)) == set()


def test_missing_mode_is_rejected(tmp_path):
    root = fixture_repo(tmp_path)
    config = root / "openspec/config.yaml"
    config.write_text(config.read_text(encoding="utf-8").replace("  refinement:", "  obsolete:"),
                      encoding="utf-8")
    assert "CONFIG_MODES" in codes(root)


def test_mode_without_spec_or_pytest_contract_is_rejected(tmp_path):
    root = fixture_repo(tmp_path)
    config = root / "openspec/config.yaml"
    config.write_text(config.read_text(encoding="utf-8").replace(
        "requires: proposal specs pytest tasks", "requires: proposal tasks"), encoding="utf-8")
    assert "CONFIG_MODES" in codes(root)


@pytest.mark.parametrize("required_clause", [
    "知识资产三问", "验收与晋档条件", "退休哪一个既有守卫",
    ".gitignore", "intent.md", "docs/codex/rules/场景建造与合规.md",
])
def test_config_cannot_drop_existing_mandatory_clause(tmp_path, required_clause):
    root = fixture_repo(tmp_path)
    config = root / "openspec/config.yaml"
    config.write_text(config.read_text(encoding="utf-8").replace(required_clause, "已删除旧条款"),
                      encoding="utf-8")
    assert "CONFIG_MANDATORY" in codes(root)


def test_unindexed_change_and_active_limits_are_rejected(tmp_path):
    root = fixture_repo(tmp_path)
    index = root / "docs/requirements/INDEX.md"
    index.write_text(index.read_text(encoding="utf-8").replace("`sc1-new-feature`", "`other`"),
                     encoding="utf-8")
    assert "CHANGE_NOT_INDEXED" in codes(root)
    text = index.read_text(encoding="utf-8").replace("`other`", "`sc1-new-feature`")
    extra = "\n".join(f"| `sc{i}-feature` | 采购 | feature | active_mvp | 0/1 | — |" for i in range(2, 7))
    index.write_text(text.replace("## 表三：", extra + "\n## 表三：", 1), encoding="utf-8")
    assert "ACTIVE_LIMIT" in codes(root)


def test_complete_change_requires_archive_or_explicit_hold(tmp_path):
    root = fixture_repo(tmp_path)
    tasks = root / "openspec/changes/sc1-new-feature/tasks.md"
    tasks.write_text("- [x] 1. 测试\n- [x] 2. 实现\n", encoding="utf-8")
    assert "UNARCHIVED_COMPLETE" in codes(root)
    proposal = root / "openspec/changes/sc1-new-feature/proposal.md"
    proposal.write_text(proposal.read_text(encoding="utf-8") +
                        "\n暂不归档：等待真实源签认。\n", encoding="utf-8")
    assert "UNARCHIVED_COMPLETE" not in codes(root)


def test_new_feature_mandatory_sections_are_enforced(tmp_path):
    root = fixture_repo(tmp_path)
    proposal = root / "openspec/changes/sc1-new-feature/proposal.md"
    proposal.write_text("## Why\n新能力。\n", encoding="utf-8")
    assert "FEATURE_PROPOSAL" in codes(root)


def test_refinement_requires_delta_and_corresponding_test(tmp_path):
    root = fixture_repo(tmp_path)
    index = root / "docs/requirements/INDEX.md"
    index.write_text(index.read_text(encoding="utf-8").replace("| feature |", "| refinement |"),
                     encoding="utf-8")
    (root / "openspec/changes/sc1-new-feature/specs/sc1-core/spec.md").unlink()
    assert "REFINEMENT_DELTA" in codes(root)
    (root / "openspec/changes/sc1-new-feature/specs/sc1-core/spec.md").write_text(
        "## MODIFIED Requirements\n", encoding="utf-8")
    (root / "4-数字员工/采购部/SC1-example/tests/test_core.py").unlink()
    assert "INDEX_TEST_MISSING" in codes(root)


def test_refinement_cannot_use_scaffold_only_test(tmp_path):
    root = fixture_repo(tmp_path)
    index = root / "docs/requirements/INDEX.md"
    index.write_text(index.read_text(encoding="utf-8")
                     .replace("| feature |", "| refinement |")
                     .replace("tests/test_core.py", "tests/test_scaffold.py"), encoding="utf-8")
    (root / "4-数字员工/采购部/SC1-example/tests/test_scaffold.py").write_text(
        "def test_scaffold(): assert True\n", encoding="utf-8")
    assert "REFINEMENT_TEST" in codes(root)


def test_broken_index_spec_path_is_rejected(tmp_path):
    root = fixture_repo(tmp_path)
    (root / "openspec/specs/sc1-core/spec.md").unlink()
    assert "INDEX_SPEC_MISSING" in codes(root)


def test_existing_but_wrong_kind_index_paths_are_rejected(tmp_path):
    root = fixture_repo(tmp_path)
    (root / "docs/requirements/fake.md").write_text("not a spec", encoding="utf-8")
    (root / "docs/requirements/helper.py").write_text("not a test", encoding="utf-8")
    index = root / "docs/requirements/INDEX.md"
    index.write_text(index.read_text(encoding="utf-8")
                     .replace("openspec/specs/sc1-core/spec.md", "docs/requirements/fake.md")
                     .replace("4-数字员工/采购部/SC1-example/tests/test_core.py",
                              "docs/requirements/helper.py"), encoding="utf-8")
    assert {"INDEX_SPEC_PATH", "INDEX_TEST_PATH"}.issubset(codes(root))


def test_registry_scene_must_enter_index_pool(tmp_path):
    root = fixture_repo(tmp_path)
    registry = root / "1-转型规划/0-全景路线图/场景registry-规划倒逼扫描器.jsonl"
    registry.write_text(registry.read_text(encoding="utf-8") +
                        '{"code":"SC2","domain":"采购"}\n', encoding="utf-8")
    assert "SCENE_NOT_IN_POOL" in codes(root)


def test_legacy_baseline_freezes_exact_deficiency_only(tmp_path):
    root = fixture_repo(tmp_path)
    tool = load_tool()
    proposal = root / "openspec/changes/sc1-new-feature/proposal.md"
    proposal.write_text("## Why\n旧包缺节。\n", encoding="utf-8")
    before = tool.check_repository(root)
    assert any(x.code == "FEATURE_PROPOSAL" for x in before)
    baseline = root / "0-学习与工具/需求与变更包门禁lint-baseline.json"
    baseline.write_text(json.dumps({
        "schema_version": 1,
        "initial_legacy": {"sc1-new-feature": ["FEATURE_PROPOSAL"]},
        "legacy": {"sc1-new-feature": {
            "fingerprint": tool.package_fingerprint(proposal.parent),
            "missing": ["FEATURE_PROPOSAL"],
        }},
    }, ensure_ascii=False), encoding="utf-8")
    assert "FEATURE_PROPOSAL" not in codes(root)
    (proposal.parent / "tasks.md").write_text("- [ ] 1. 新触碰\n", encoding="utf-8")
    assert "FEATURE_PROPOSAL" in codes(root)


def test_baseline_cannot_grow_exception_set(tmp_path):
    root = fixture_repo(tmp_path)
    baseline = root / "0-学习与工具/需求与变更包门禁lint-baseline.json"
    baseline.write_text(json.dumps({
        "schema_version": 1, "initial_legacy": {},
        "legacy": {"new-package": {"fingerprint": "abc", "missing": ["FEATURE_PROPOSAL"]}},
    }), encoding="utf-8")
    assert "BASELINE_GROWTH" in codes(root)


def test_initial_legacy_anchor_rejects_dual_baseline_growth(tmp_path, monkeypatch):
    root = fixture_repo(tmp_path)
    tool = load_tool()
    empty_digest = hashlib.sha256(b"{}").hexdigest()
    monkeypatch.setattr(tool, "ROOT", root)
    monkeypatch.setattr(tool, "INITIAL_LEGACY_SHA256", empty_digest, raising=False)
    baseline = root / "0-学习与工具/需求与变更包门禁lint-baseline.json"
    baseline.write_text(json.dumps({
        "schema_version": 1,
        "initial_legacy": {"new-package": ["FEATURE_PROPOSAL"]},
        "legacy": {"new-package": {"fingerprint": "abc", "missing": ["FEATURE_PROPOSAL"]}},
    }), encoding="utf-8")
    assert "BASELINE_GROWTH" in {item.code for item in tool.check_repository(root)}


def test_missing_baseline_fails_closed(tmp_path):
    root = fixture_repo(tmp_path)
    (root / "0-学习与工具/需求与变更包门禁lint-baseline.json").unlink()
    assert "INPUT_MISSING" in codes(root)
