"""`工具-待合分支巡检-白名单判据.ps1` 单测（派单件 `派单件-【CC】ff低风险白名单-2026-09-12.md` §一.5，OP-0912-S）。

派单件点名的五条：
- 纯 md 分支 ⇒ 命中；
- 含一个 `.py` ⇒ 不命中；
- 触碰队列／`.claude/rules`／`CLAUDE.md` ⇒ 不命中；
- 判据命令失败（ref 解析不出）⇒ 不命中（fail-closed，⑸）；
- 冲突 ⇒ 不命中（⑷ merge-tree）。

外加 `Get-FfWhitelistFileVerdict` 的纯函数逐路径判定（`.json` 不算低风险、`openspec/**` 非可执行放行、
`.txt` 等既不在允许集合也不在黑名单的一律不放行、`.gitignore`／`.claude/**` 判载体）。

🔴 需要 PowerShell 7（`pwsh`）与 git ≥ 2.38（`merge-tree --write-tree`）；缺任一即整文件跳过
（同 `test_工具-泳道分支合入-回归判定.py` 手法）。每个用例在临时目录里 `git init` 一个小仓库、造 master
与分支，再经 pwsh dot-source 判据库调 `Test-FfWhitelist`，把结果 `ConvertTo-Json` 回来断言——不碰真仓库。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

LIB = Path(__file__).resolve().with_name("工具-待合分支巡检-白名单判据.ps1")

pytestmark = pytest.mark.skipif(shutil.which("pwsh") is None, reason="需要 PowerShell 7（pwsh）")


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return proc.stdout.strip()


def _run_json(ps_body: str):
    """把 `ps_body`（先 dot-source 判据库）写成临时 .ps1 跑 pwsh，返回反序列化后的 JSON。"""
    script = f". '{LIB.as_posix()}'\r\n{ps_body}\r\n"
    with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as f:
        f.write(script)
        path = f.name
    try:
        proc = subprocess.run(
            ["pwsh", "-NoProfile", "-NonInteractive", "-File", path],
            capture_output=True, text=True, timeout=120, encoding="utf-8",
        )
        assert proc.returncode == 0, f"pwsh 非零退出（stderr）：{proc.stderr}\n(stdout){proc.stdout}"
        out = proc.stdout.strip()
        return json.loads(out) if out else None
    finally:
        Path(path).unlink(missing_ok=True)


def _verdict(repo: Path, branch: str, base: str = "master") -> dict:
    return _run_json(
        f"$v = Test-FfWhitelist -Repo '{repo.as_posix()}' -Branch '{branch}' -Base '{base}'\r\n"
        "$v | ConvertTo-Json -Depth 6 -Compress"
    )


def _checks(v: dict) -> dict[str, dict]:
    return {c["Id"]: c for c in v["Checks"]}


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """一个带 master 首提交的小仓库：README.md ＋ 一份 .py ＋ 一份队列真身 ＋ 一份 CLAUDE.md。"""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "master")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")
    _git(r, "config", "commit.gpgsign", "false")
    (r / "README.md").write_text("# base\n", encoding="utf-8")
    (r / "tool.py").write_text("print('base')\n", encoding="utf-8")
    q = r / "1-转型规划" / "0-全景路线图"
    q.mkdir(parents=True)
    (q / "跨桌任务队列-机制环境.md").write_text("| # | 行 |\n", encoding="utf-8")
    (r / "CLAUDE.md").write_text("# 纪律\n", encoding="utf-8")
    (r / ".claude" / "rules").mkdir(parents=True)
    (r / ".claude" / "rules" / "队列与落库.md").write_text("规则\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "base")
    return r


def _branch_with(repo: Path, name: str, files: dict[str, str], msg: str = "change") -> None:
    """从 master 切出 `name`，写入 `files`（相对路径→内容），提交一次，再切回 master。"""
    _git(repo, "checkout", "-q", "-b", name, "master")
    for rel, content in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)
    _git(repo, "checkout", "-q", "master")


# ── 派单件五条 ──────────────────────────────────────────────────────────────

def test_pure_md_branch_hits(repo: Path):
    _branch_with(repo, "claude/docs-only", {
        "1-转型规划/0-全景路线图/取证件-2026-09-12-x.md": "取证\n",
        "openspec/changes/foo/design.md": "# design\n",
        "6-人才与组织/名录.md": "名录\n",
    })
    v = _verdict(repo, "claude/docs-only")
    assert v["Hit"] is True
    c = _checks(v)
    assert all(c[i]["Ok"] for i in ("⑴", "⑵", "⑶", "⑷", "⑸")), c
    assert sorted(v["Files"]) == [
        "1-转型规划/0-全景路线图/取证件-2026-09-12-x.md",
        "6-人才与组织/名录.md",
        "openspec/changes/foo/design.md",
    ]


def test_one_py_file_misses(repo: Path):
    _branch_with(repo, "claude/with-py", {
        "openspec/changes/foo/design.md": "# design\n",
        "0-学习与工具/工具-新.py": "print(1)\n",
    })
    v = _verdict(repo, "claude/with-py")
    assert v["Hit"] is False
    c = _checks(v)
    assert c["⑵"]["Ok"] is False and "工具-新.py" in c["⑵"]["Detail"]
    assert c["⑴"]["Ok"] is False          # 允许集合判定与 ⑵ 同向
    assert c["⑷"]["Ok"] is True           # 冲突判据独立评估、不受 ⑵ 影响
    assert c["⑸"]["Ok"] is True           # 命令都成功，是「判据不满足」不是「取不到」


@pytest.mark.parametrize("rel, reason_key", [
    ("1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md", "队列真身"),
    (".claude/rules/队列与落库.md", ".claude/**"),
    ("CLAUDE.md", "CLAUDE.md"),
    ("4-数字员工/采购部/SC4/CLAUDE.md", "CLAUDE.md"),
    (".gitignore", ".gitignore"),
    (".claude/settings.json", ".claude/**"),
])
def test_touching_carrier_misses(repo: Path, rel: str, reason_key: str):
    _branch_with(repo, "claude/touch-carrier", {
        "openspec/changes/foo/design.md": "# design\n",
        rel: "改了载体\n",
    })
    v = _verdict(repo, "claude/touch-carrier")
    assert v["Hit"] is False
    c = _checks(v)
    assert c["⑶"]["Ok"] is False, c["⑶"]
    assert reason_key in c["⑶"]["Detail"], c["⑶"]["Detail"]


def test_command_failure_misses_fail_closed(repo: Path):
    # ref 解析不出 ⇒ ⑸ 失败、Hit=False、其余四条保持「未评估」——不得把「取不到」算成「通过」
    v = _verdict(repo, "claude/does-not-exist")
    assert v["Hit"] is False
    c = _checks(v)
    assert c["⑸"]["Ok"] is False and "ref 解析不出" in c["⑸"]["Detail"]
    for i in ("⑴", "⑵", "⑶", "⑷"):
        assert c[i]["Ok"] is False and c[i]["Detail"] == "未评估"
    # base 解析不出同样 fail-closed
    _branch_with(repo, "claude/fine", {"a.md": "a\n"})
    v2 = _verdict(repo, "claude/fine", base="no-such-base")
    assert v2["Hit"] is False and "no-such-base" in _checks(v2)["⑸"]["Detail"]


def test_conflict_misses(repo: Path):
    # 分支与 master 同一文件同一行各改一版 ⇒ merge-tree 冲突 ⇒ ⑷ 失败
    _branch_with(repo, "claude/conflicting", {"README.md": "# branch version\n"})
    (repo / "README.md").write_text("# master version\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "master moves")
    v = _verdict(repo, "claude/conflicting")
    assert v["Hit"] is False
    c = _checks(v)
    assert c["⑷"]["Ok"] is False and "冲突" in c["⑷"]["Detail"]
    assert c["⑴"]["Ok"] and c["⑵"]["Ok"] and c["⑶"]["Ok"]   # 文件判据本身都通过，只栽在 ⑷


# ── 补充：空差异与 master 并行推进（非冲突）────────────────────────────────

def test_empty_diff_misses(repo: Path):
    # 分支＝master（零差异）⇒ 无可 ff 之物 ⇒ ⑸ 失败（fail-closed），不是「命中」
    _git(repo, "branch", "claude/same-as-master", "master")
    v = _verdict(repo, "claude/same-as-master")
    assert v["Hit"] is False
    assert "差异文件为空" in _checks(v)["⑸"]["Detail"]


def test_master_advanced_elsewhere_still_hits(repo: Path):
    # master 在别的文件上前进（rebase 后可纯 ff 的典型形态）⇒ 仍命中；差异只算分支侧
    _branch_with(repo, "claude/docs", {"openspec/changes/foo/proposal.md": "# p\n"})
    (repo / "other.md").write_text("master side\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "master moves elsewhere")
    v = _verdict(repo, "claude/docs")
    assert v["Hit"] is True
    assert v["Files"] == ["openspec/changes/foo/proposal.md"]


# ── Get-FfWhitelistFileVerdict 纯函数 ─────────────────────────────────────

def _file_verdict(path: str) -> dict:
    return _run_json(f"Get-FfWhitelistFileVerdict -Path '{path}' | ConvertTo-Json -Compress")


@pytest.mark.parametrize("path, allowed, rule", [
    ("1-转型规划/0-全景路线图/取证件.md", True, "allow"),
    ("openspec/changes/x/design.md", True, "allow"),
    ("openspec/changes/x/notes.txt", True, "allow"),            # openspec/** 非可执行放行
    ("openspec/changes/x/.openspec.yaml", False, "code"),        # yaml 算配置，不放行
    ("1-转型规划/0-全景路线图/队列回写待补/B-0908.json", False, "code"),  # .json 一律不算低风险
    ("0-学习与工具/工具-x.ps1", False, "code"),
    ("0-学习与工具/模块.psd1", False, "code"),
    ("1-转型规划/某件.txt", False, "outside"),                   # 既不在允许集合也不在黑名单 ⇒ 不放行
    ("6-人才与组织/口径点台账/IT域.jsonl", False, "outside"),
    ("7-外部文档/x.docx", False, "outside"),
    ("1-转型规划/0-全景路线图/跨桌任务队列.md", False, "carrier"),
    ("1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md", False, "carrier"),
    ("CLAUDE.md", False, "carrier"),
    ("5-平台底座/CLAUDE.md", False, "carrier"),
    (".claude/rules/x.md", False, "carrier"),
    (".claude/settings.local.json", False, "carrier"),
    (".claude/hooks/x.ps1", False, "carrier"),
    (".gitignore", False, "carrier"),
    ("sub/dir/.gitattributes", False, "carrier"),
    ("1-转型规划\\0-全景路线图\\反斜杠路径.md", True, "allow"),   # 反斜杠归一化
])
def test_file_verdict(path: str, allowed: bool, rule: str):
    v = _file_verdict(path)
    assert v["Allowed"] is allowed, v
    assert v["Rule"] == rule, v
