"""单测：`工具-承载性一致性扫描.py`（队列 §一 `#601`）。

覆盖三态判据＋载体抽取窗口＋队列行号核验（经假 `工具-队列查询.py` 桩，
不依赖真实队列真身，避免测试跑到真队列文件上）。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_MODULE_NAME = "_test_carrier_scan_module"
_MODULE_PATH = Path(__file__).parent / "工具-承载性一致性扫描.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def m():
    return _load_module()


def _fake_queue_query_tool(repo_root: Path, valid_rows: set[str]) -> None:
    """在 `repo_root` 下放一个假 `工具-队列查询.py`，`--row N --format json`
    时按 `valid_rows` 回答 `found`，不碰真实队列文件。"""
    tool_dir = repo_root / "0-学习与工具"
    tool_dir.mkdir(parents=True, exist_ok=True)
    rows_literal = json.dumps(sorted(valid_rows))
    (tool_dir / "工具-队列查询.py").write_text(
        "import sys, json\n"
        f"VALID = set({rows_literal})\n"
        "argv = sys.argv[1:]\n"
        "row = argv[argv.index('--row') + 1]\n"
        "print(json.dumps({'row': row, 'found': row in VALID}))\n",
        encoding="utf-8",
    )


# ------------------------------------------------------------------
# 载体抽取窗口
# ------------------------------------------------------------------

def test_extract_claims_carrier_after_marker(m):
    text = "🛡 机器守已生效，落点＝CI job `scene-intent-gate-lint`（`.github/workflows/ci.yml`）。"
    claims = m.extract_claims("fake.md", text)
    assert len(claims) == 1
    kinds = {c.kind for c in claims[0].carriers}
    assert "ci_job" in kinds
    assert "file" in kinds


def test_extract_claims_window_does_not_leak_across_long_run_on_sentence(m):
    """回归：长复句里与标记无关的反引号路径不得被误当作该标记的载体
    （实测撞过 `.claude/rules/场景建造与合规.md` 一句 140+ 字的复句）。"""
    filler = "填充填充填充填充填充填充填充填充填充填充" * 6  # 60 字无关文本，撑开距离
    text = (
        "原写「机器守＝openspec validate 闸（队列 §一 需求侧机器守行，"
        "CC 建成前本条人守）」，其中都不存在：09-06 实测……" + filler +
        "本仓 8 份缺 config.yaml 点名 MANDATORY 节的 `proposal.md`，"
        "`openspec validate --all --strict` 仍 169 passed；"
    )
    claims = m.extract_claims("fake.md", text)
    assert len(claims) == 1
    # `proposal.md` 距标记 100+ 字，不应被抽入这条 claim 的载体。
    assert all(c.value != "proposal.md" for c in claims[0].carriers)


def test_extract_claims_carrier_before_marker_within_window(m):
    text = "改动须先过 `release` 校验⑪，2026-09-11 起阻断（机器守＝`0-学习与工具/工具-共享文档编辑锁.py`）。"
    claims = m.extract_claims("fake.md", text)
    assert len(claims) == 1
    assert any(c.kind == "file" and "编辑锁" in c.value for c in claims[0].carriers)


def test_no_marker_no_claim(m):
    assert m.extract_claims("fake.md", "这是一句普通的规则文本，没有任何自陈。") == []


# ------------------------------------------------------------------
# state③：命令式约束、零结构化载体
# ------------------------------------------------------------------

def test_imperative_without_carrier_is_listed(m):
    text = "改本文件前必须先读一遍全文。"
    hits = m.extract_no_carrier_imperatives("fake.md", text)
    assert len(hits) == 1


def test_imperative_with_carrier_not_listed(m):
    text = "改本文件前必须先跑 `0-学习与工具/工具-共享文档编辑锁.py`。"
    hits = m.extract_no_carrier_imperatives("fake.md", text)
    assert hits == []


# ------------------------------------------------------------------
# ExistenceChecker
# ------------------------------------------------------------------

def test_file_exists_direct_path(m, tmp_path):
    (tmp_path / "a.py").write_text("x", encoding="utf-8")
    checker = m.ExistenceChecker(tmp_path)
    assert checker.file_exists("a.py") is True
    assert checker.file_exists("b.py") is False


def test_file_exists_basename_fallback_under_known_dirs(m, tmp_path):
    nested = tmp_path / "0-学习与工具" / "hooks"
    nested.mkdir(parents=True)
    (nested / "sentinel-pronoun.ps1").write_text("x", encoding="utf-8")
    checker = m.ExistenceChecker(tmp_path)
    # 规则文本里常省略目录，只写裸文件名——应能在已知目录树下按 basename 找到。
    assert checker.file_exists("sentinel-pronoun.ps1") is True


def test_queue_row_exists_via_stub_tool(m, tmp_path):
    _fake_queue_query_tool(tmp_path, {"416", "566"})
    checker = m.ExistenceChecker(tmp_path)
    assert checker.queue_row_exists("416") is True
    assert checker.queue_row_exists("999") is False


def test_queue_row_missing_tool_is_not_found(m, tmp_path):
    checker = m.ExistenceChecker(tmp_path)
    assert checker.queue_row_exists("1") is False


def test_ci_job_exists(m, tmp_path):
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "ci.yml").write_text(
        "name: ci\njobs:\n  scene-intent-gate-lint:\n    runs-on: ubuntu-latest\n"
        "  other-job:\n    runs-on: ubuntu-latest\n",
        encoding="utf-8",
    )
    checker = m.ExistenceChecker(tmp_path)
    assert checker.ci_job_exists("scene-intent-gate-lint") is True
    assert checker.ci_job_exists("no-such-job") is False


def test_skill_exists(m, tmp_path):
    (tmp_path / ".claude" / "skills" / "zhuopin-lane-watch").mkdir(parents=True)
    checker = m.ExistenceChecker(tmp_path)
    assert checker.skill_exists("zhuopin-lane-watch") is True
    assert checker.skill_exists("no-such-skill") is False


# ------------------------------------------------------------------
# 协议〇节抽取
# ------------------------------------------------------------------

def test_extract_protocol_zero_section_found(m):
    text = (
        "# 标题\n\n正文\n\n"
        "## 〇、协议（十一条）\n\n1. 第一条\n2. 第二条\n\n"
        "## 一、待领\n\n后面的内容不应被抽入。"
    )
    section = m._extract_protocol_zero(text)
    assert section is not None
    assert "第一条" in section
    assert "后面的内容不应被抽入" not in section


def test_extract_protocol_zero_section_absent(m):
    assert m._extract_protocol_zero("# 标题\n\n没有协议〇\n") is None


# ------------------------------------------------------------------
# 端到端 scan()：三态 ＋ 自举验收（⑤ 故意造一条指错载体的假规则）
# ------------------------------------------------------------------

def _build_fake_repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / "0-学习与工具").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    _fake_queue_query_tool(tmp_path, set())
    return tmp_path


def test_scan_state1_missing(m, tmp_path):
    repo = _build_fake_repo(tmp_path)
    (repo / ".claude" / "rules" / "fake.md").write_text(
        "🔴 机器守＝`0-学习与工具/工具-不存在的脚本.py`（假设已建成）。\n",
        encoding="utf-8",
    )
    findings = m.scan(repo)
    assert len(findings["missing"]) == 1
    assert findings["missing"][0]["carrier_value"] == "0-学习与工具/工具-不存在的脚本.py"
    assert findings["misdirected"] == []


def test_scan_state2_misdirected_deliberately_planted(m, tmp_path):
    """⑤ 自举验收：故意造一条「指错载体」的假规则，确认 ② 态真的报出来。"""
    repo = _build_fake_repo(tmp_path)
    (repo / ".claude" / "rules" / "fake.md").write_text(
        "🔴 机器守＝`0-学习与工具/工具-并不存在的稀土价格扫描.py`（承接稀土价格扫描）。\n",
        encoding="utf-8",
    )
    # 真实落点换了个文件名，但内容里带着同一个关键词「稀土价格」。
    (repo / "0-学习与工具" / "工具-稀土价格真实扫描器.py").write_text(
        "# 稀土价格扫描的真实实现\n", encoding="utf-8",
    )
    findings = m.scan(repo)
    assert findings["missing"] == []
    assert len(findings["misdirected"]) == 1
    item = findings["misdirected"][0]
    assert "稀土价格真实扫描器" in item["suspected_real_location"]


def test_scan_state3_no_carrier_listed_not_alerted(m, tmp_path):
    repo = _build_fake_repo(tmp_path)
    (repo / ".claude" / "rules" / "fake.md").write_text(
        "改动前必须先做一次全面评审，不得跳过。\n", encoding="utf-8",
    )
    findings = m.scan(repo)
    assert findings["missing"] == []
    assert findings["misdirected"] == []
    assert len(findings["no_carrier"]) == 1


def test_scan_existing_carrier_produces_no_finding(m, tmp_path):
    repo = _build_fake_repo(tmp_path)
    (repo / "0-学习与工具" / "工具-真实存在.py").write_text("x", encoding="utf-8")
    (repo / ".claude" / "rules" / "fake.md").write_text(
        "🔴 机器守＝`0-学习与工具/工具-真实存在.py`。\n", encoding="utf-8",
    )
    findings = m.scan(repo)
    assert findings["missing"] == []
    assert findings["misdirected"] == []
    assert findings["markerless"] == []


def test_format_report_smoke(m, tmp_path):
    repo = _build_fake_repo(tmp_path)
    findings = m.scan(repo)
    report = m.format_report(findings)
    assert "① 缺失" in report
    assert "② 指错载体" in report
    assert "③ 无载体清单" in report


# ------------------------------------------------------------------
# 自举验收 ①：本文件真的挂进了 `工具-落库sweep.py` 的第 19 类常驻状态告警
# ------------------------------------------------------------------

def test_registered_in_sweep_main_sequence():
    sweep_src = (Path(__file__).parent / "工具-落库sweep.py").read_text(encoding="utf-8")
    assert "_check_carrier_consistency(repo_root, log)" in sweep_src
    assert "def _check_carrier_consistency(" in sweep_src
