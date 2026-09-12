# -*- coding: utf-8 -*-
"""落库 sweep · 文档台账重跑改条件触发（`OP-0912-R`，批 `B-0912_落库瘦身`，
Shao Peishen 2026-09-12 答 2a）单测。

被测对象＝`工具-落库sweep.py::_rerun_ledger` 及其指纹判据
`_ledger_content_fingerprint`／`_ledger_unchanged_against_index`。派单件
§一.4 点名三条：「输入未变 ⇒ 跳过」「输入变了 ⇒ 重跑」「指纹读失败 ⇒ 照跑」。

夹具用**真 git 仓库 ＋ 台账生成器桩**（桩每跑写一行「> 生成于 <当前时刻>」
＋ 由环境变量注入的正文），与生产形态同构：生产里正是这一行时间戳让
`git status` 永远报"有改动"。`sweep` 模块按同目录既有惯例经
`importlib.util.spec_from_file_location` 加载（文件名含中文）。
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SWEEP_SPEC = importlib.util.spec_from_file_location(
    "commit_sweep_for_ledger_conditional", Path(__file__).resolve().parent / "工具-落库sweep.py"
)
sweep = importlib.util.module_from_spec(_SWEEP_SPEC)
_SWEEP_SPEC.loader.exec_module(sweep)

# 桩：正文来自环境变量 `LEDGER_STUB_BODY`；时间戳行每跑必不同——行首形态与生产
# 一致（`> 生成于 YYYY-MM-DD HH:MM｜`，指纹正则只锚这一段），行尾再缀一个微秒级
# isoformat，保证同一分钟内连跑两次也不相等（生产里是分钟级，判据一样）。
_STUB_LEDGER_SCRIPT = (
    "import os\n"
    "from datetime import datetime\n"
    "from pathlib import Path\n"
    "p = Path(__file__).resolve().parents[1] / '1-转型规划' / '0-全景路线图' / '文档台账-自动生成.md'\n"
    "p.parent.mkdir(parents=True, exist_ok=True)\n"
    "stamp = datetime.now().strftime('%Y-%m-%d %H:%M')\n"
    "body = os.environ.get('LEDGER_STUB_BODY', '共 1 份 md')\n"
    "p.write_text('# 文档台账\\n\\n> 生成于 ' + stamp + '｜扫描范围：x（' + datetime.now().isoformat() + '）\\n'\n"
    "             + '> ' + body + '\\n', encoding='utf-8')\n"
)


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=cwd,
                           capture_output=True, text=True, encoding="utf-8", check=check)


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    work = tmp_path / "work"
    _git(tmp_path, "init", "-q", str(work))
    _git(work, "config", "user.email", "test@example.com")
    _git(work, "config", "user.name", "Test")
    (work / ".gitignore").write_text("**/reports/\n", encoding="utf-8")
    script = work / sweep.LEDGER_SCRIPT_REL
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(_STUB_LEDGER_SCRIPT, encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "init")
    monkeypatch.setenv("LEDGER_STUB_BODY", "共 1 份 md")
    return work


def _commit_count(repo: Path) -> int:
    return int(_git(repo, "rev-list", "--count", "HEAD").stdout.strip())


def _ledger_dirty(repo: Path) -> bool:
    return bool(_git(repo, "status", "--porcelain=v1", "--", sweep.LEDGER_OUTPUT_REL).stdout.strip())


# ---------- 指纹本身 ----------

def test_指纹只剔时间戳行_其余逐字计入():
    a = "# 台账\n\n> 生成于 2026-09-12 10:00｜扫描范围：x\n> 共 1 份 md\n"
    b = "# 台账\n\n> 生成于 2026-09-12 11:37｜扫描范围：x\n> 共 1 份 md\n"
    c = "# 台账\n\n> 生成于 2026-09-12 10:00｜扫描范围：x\n> 共 2 份 md\n"
    assert sweep._ledger_content_fingerprint(a) == sweep._ledger_content_fingerprint(b)
    assert sweep._ledger_content_fingerprint(a) != sweep._ledger_content_fingerprint(c)
    assert len(sweep._ledger_content_fingerprint(a)) == 64  # sha256 hex


# ---------- 派单件三条 ----------

def test_首次入库_index里没有台账_按已变处理照常提交(repo: Path):
    """fail-open 的一支：index 里根本没有台账 ⇒ 指纹无从比对 ⇒ 照常提交。"""
    log: list[str] = []
    sweep._rerun_ledger(repo, log)
    joined = "\n".join(log)
    assert _commit_count(repo) == 2, joined
    assert "index 里没有已入库的台账" in joined and "照常提交" in joined
    assert not _ledger_dirty(repo)


def test_输入未变_仅时间戳不同_跳过提交并还原工作区(repo: Path):
    """派单件 ①：文件集没变 ⇒ 再跑一次只差时间戳行 ⇒ 不产生 commit、工作区干净、
    日志留「台账未变、跳过（指纹 <8 位>）」。"""
    sweep._rerun_ledger(repo, [])          # 第一次：入库
    before = _commit_count(repo)
    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    committed = _git(repo, "show", "HEAD:" + sweep.LEDGER_OUTPUT_REL).stdout

    log: list[str] = []
    sweep._rerun_ledger(repo, log)         # 第二次：只有时间戳变
    joined = "\n".join(log)

    assert _commit_count(repo) == before, joined
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == head_before
    assert not _ledger_dirty(repo), "工作区里不该留下一份只改了时间戳的台账"
    # 工作区文件已从 index 还原 ⇒ 时间戳仍是入库那一份的
    assert (repo / sweep.LEDGER_OUTPUT_REL).read_text(encoding="utf-8") == committed
    fp8 = sweep._ledger_content_fingerprint(committed)[:8]
    assert f"台账未变、跳过（指纹 {fp8}）" in joined


def test_输入变了_照跑并提交(repo: Path, monkeypatch: pytest.MonkeyPatch):
    """派单件 ②：正文变了 ⇒ 指纹不一致 ⇒ 照旧提交一条台账 commit。"""
    sweep._rerun_ledger(repo, [])
    before = _commit_count(repo)

    monkeypatch.setenv("LEDGER_STUB_BODY", "共 2 份 md")
    log: list[str] = []
    sweep._rerun_ledger(repo, log)
    joined = "\n".join(log)

    assert _commit_count(repo) == before + 1, joined
    assert "台账未变" not in joined
    assert "台账已重跑并本地提交" in joined
    assert "共 2 份 md" in _git(repo, "show", "HEAD:" + sweep.LEDGER_OUTPUT_REL).stdout
    assert not _ledger_dirty(repo)


def test_指纹读失败_照跑并提交_且日志写明原因(repo: Path, monkeypatch: pytest.MonkeyPatch):
    """派单件 ③（fail-open）：指纹计算本身抛异常 ⇒ 不得静默跳过，按已变处理照常
    提交，并在日志里写明「指纹取不到」。用 monkeypatch 让指纹函数炸掉——模拟
    读文件／解码等任何一环失败。"""
    sweep._rerun_ledger(repo, [])
    before = _commit_count(repo)

    def _boom(_text: str) -> str:
        raise OSError("模拟：台账读取失败")

    monkeypatch.setattr(sweep, "_ledger_content_fingerprint", _boom)
    log: list[str] = []
    sweep._rerun_ledger(repo, log)
    joined = "\n".join(log)

    assert _commit_count(repo) == before + 1, joined
    assert "台账指纹取不到" in joined and "照常提交" in joined
    assert "台账未变" not in joined
    assert not _ledger_dirty(repo)


def test_生成器本身失败_不提交不还原_沿用既有告警(repo: Path):
    """边界：生成器非零退出 ⇒ 既有分支「台账重跑失败（不影响已落库批次）」，
    指纹逻辑根本不介入——确认本棒没有改动这条既有路径。"""
    sweep._rerun_ledger(repo, [])
    before = _commit_count(repo)
    (repo / sweep.LEDGER_SCRIPT_REL).write_text("import sys\nsys.exit(3)\n", encoding="utf-8")

    log: list[str] = []
    sweep._rerun_ledger(repo, log)
    joined = "\n".join(log)
    assert _commit_count(repo) == before
    assert "台账重跑失败" in joined
    assert "指纹" not in joined
