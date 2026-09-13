"""合入链路留痕单测（队列 §一 `#571` ⑹⑺⑻，`OP-0913-E` 并入，2026-09-13）。

⑻ 点名的四条：
- `工具-泳道分支合入.ps1` 合入成功／被拒（④ 回归新增失败）／被打断（③ rebase 冲突）三条路径各在
  `<登记册目录>/ff-patrol-<yyyyMMdd>.jsonl` 留一行，`action`／`exit`／各关布尔／④ 两侧失败集合与实际结局一致；
- 已合分支再入册即被销：`Invoke-PendingFfRegistrySweep` 把「已是 master 祖先」「分支已不存在」的行迁进
  `<登记册目录>/pending-ff.done-<yyyyMMdd>.jsonl`（原字段保留＋`done_reason`），登记册只剩真待合行，且幂等。
外加 `工具-待合分支巡检.ps1` 端到端一条：登记册里一条带授权原文的 docs 分支 → 巡检调合入脚本 → 两个
actor 各留一行、登记册销行、done 文件写 `本轮合入`（验证 `-Repo`／`-TempRoot` 透传这条路真通）。

🔴 需要 PowerShell 7（`pwsh`）与 git；缺任一即整文件跳过（同 `test_工具-泳道分支合入-回归判定.py` 手法）。
每个用例在 `tmp_path` 里 `git init` 一个小仓库＋一个 bare `origin`（合入脚本 ⑤ 会 `push origin`），
临时 rebase worktree 也落在 `tmp_path`（`-TempRoot`）——不碰真仓库、不碰 `C:\\Dev`。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
LIB = TOOLS / "工具-合入链路留痕.ps1"
MERGE = TOOLS / "工具-泳道分支合入.ps1"
PATROL = TOOLS / "工具-待合分支巡检.ps1"
# 登记册目录（OP-0913-L：自被 gitignore 整棵忽略的 reports/ 迁出）——与 `工具-合入链路留痕.ps1::Get-FfLedgerDir` 同源。
# 🔴 这里故意写死字面量而不去读 ps1：脚本改落点时让本测试失败、逼人同步，而不是两边一起悄悄漂移。
LEDGER = Path("1-转型规划") / "0-全景路线图" / "合入登记"

pytestmark = pytest.mark.skipif(
    shutil.which("pwsh") is None or shutil.which("git") is None, reason="需要 PowerShell 7（pwsh）与 git"
)


def _git(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8", check=check,
    )
    return proc.stdout.strip()


def _pwsh(*args: str, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", *args],
        capture_output=True, text=True, timeout=timeout, encoding="utf-8",
    )


def _pwsh_file(script: Path, *args: str, timeout: int = 300) -> subprocess.CompletedProcess:
    return _pwsh("-File", str(script), *args, timeout=timeout)


def _pwsh_lib_json(ps_body: str, tmp: Path):
    """dot-source 留痕库后执行 `ps_body`，stdout 按 JSON 反序列化返回。"""
    path = tmp / "_run.ps1"
    path.write_text(f". '{LIB.as_posix()}'\r\n{ps_body}\r\n", encoding="utf-8")
    proc = _pwsh("-File", str(path))
    assert proc.returncode == 0, f"pwsh 非零退出（stderr）：{proc.stderr}\n(stdout){proc.stdout}"
    out = proc.stdout.strip()
    return json.loads(out) if out else None


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "jsonl 不得带 BOM"
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]


def _trace_rows(repo: Path) -> list[dict]:
    rows: list[dict] = []
    for p in sorted((repo / LEDGER).glob("ff-patrol-*.jsonl")):
        rows.extend(_read_jsonl(p))
    return rows


def _done_rows(repo: Path) -> list[dict]:
    rows: list[dict] = []
    for p in sorted((repo / LEDGER).glob("pending-ff.done-*.jsonl")):
        rows.extend(_read_jsonl(p))
    return rows


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """master 首提交：README.md ＋ tool.py ＋ 一条全绿的 test_tool.py；bare origin 已推 master。"""
    r = tmp_path / "repo"
    r.mkdir()
    bare = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "master", str(bare))
    _git(r, "init", "-q", "-b", "master")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")
    _git(r, "config", "commit.gpgsign", "false")
    (r / "README.md").write_text("# base\nline2\n", encoding="utf-8")
    (r / "tool.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (r / "test_tool.py").write_text("from tool import f\n\n\ndef test_f():\n    assert f() == 1\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "base")
    _git(r, "remote", "add", "origin", str(bare))
    _git(r, "push", "-q", "-u", "origin", "master")
    return r


def _branch_with(repo: Path, name: str, files: dict[str, str], msg: str = "change") -> None:
    """从 master 切出 `name`，写入文件并提交一次，再切回 master。"""
    _git(repo, "checkout", "-q", "-b", name, "master")
    for rel, content in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)
    _git(repo, "checkout", "-q", "master")


def _run_merge(repo: Path, tmp_root: Path, branch: str, tests: str = "") -> subprocess.CompletedProcess:
    args = ["-Branch", branch, "-Repo", str(repo), "-TempRoot", str(tmp_root)]
    if tests:
        args += ["-Tests", tests]
    return _pwsh_file(MERGE, *args)


# ── OP-0913-L 登记册落点：三类文件都落在 合入登记/，且该目录在真仓库里不被 gitignore 吞掉 ──────

def test_ledger_paths_all_resolve_under_relocated_dir(repo: Path, tmp_path: Path):
    """`Get-FfLedgerDir`／`Get-PendingFfRegistryPath`／`Get-FfPatrolTracePath`／`Get-PendingFfDonePath` 四个函数
    与本测试写死的 `LEDGER` 同源；路径里不得再出现 `reports`。"""
    out = _pwsh_lib_json(
        f"$r = '{repo.as_posix()}'\r\n"
        "$now = Get-Date -Year 2026 -Month 9 -Day 13 -Hour 10 -Minute 0 -Second 0\r\n"
        "[ordered]@{ dir = (Get-FfLedgerDir -Repo $r); reg = (Get-PendingFfRegistryPath -Repo $r);"
        " trace = (Get-FfPatrolTracePath -Repo $r -Now $now); done = (Get-PendingFfDonePath -Repo $r -Now $now) }"
        " | ConvertTo-Json -Compress", tmp_path,
    )
    norm = {k: Path(v) for k, v in out.items()}
    assert norm["dir"] == repo / LEDGER
    assert norm["reg"] == repo / LEDGER / "pending-ff.jsonl"
    assert norm["trace"] == repo / LEDGER / "ff-patrol-20260913.jsonl"
    assert norm["done"] == repo / LEDGER / "pending-ff.done-20260913.jsonl"
    assert all("reports" not in p.parts for p in norm.values()), "落点不得回到被 gitignore 整棵忽略的 reports/"


def test_real_repo_gitignore_tracks_ledger_dir_but_still_ignores_reports():
    """对真仓库的 `.gitignore` 做 `git check-ignore`：合入登记/ 下的三类 jsonl 不被忽略，reports/ 下同名文件仍被忽略。
    🔴 只读、不写真仓库；这条是 A1 三条判据里「目录级 glob 否定有效」的机器守。"""
    real = TOOLS.parent
    if not (real / ".gitignore").exists() or _git(real, "rev-parse", "--is-inside-work-tree", check=False) != "true":
        pytest.skip("不在真仓库内")
    ledger = LEDGER.as_posix()
    tracked = [f"{ledger}/pending-ff.jsonl", f"{ledger}/pending-ff.done-20260913.jsonl",
               f"{ledger}/ff-patrol-20260913.jsonl", f"{ledger}/pending-ff.parked-20260913.jsonl"]
    ignored = ["reports/pending-ff.jsonl", "reports/ff-patrol-20260913.jsonl", "reports/noise.jsonl",
               f"{ledger}/sub/pending-ff.jsonl"]   # 例外不递归（D8）
    for rel in tracked:
        proc = subprocess.run(["git", "-C", str(real), "check-ignore", "-q", rel], capture_output=True)
        assert proc.returncode == 1, f"{rel} 不该被忽略（check-ignore 退出码 {proc.returncode}）"
    for rel in ignored:
        proc = subprocess.run(["git", "-C", str(real), "check-ignore", "-q", rel], capture_output=True)
        assert proc.returncode == 0, f"{rel} 应仍被忽略（check-ignore 退出码 {proc.returncode}）"


# ── ⑻ 合入脚本三条路径各留一行 ──────────────────────────────────────────────

def test_merge_success_leaves_one_trace_row(repo: Path, tmp_path: Path):
    _branch_with(repo, "claude/ok-docs", {"docs/note.md": "留痕\n"})
    proc = _run_merge(repo, tmp_path, "claude/ok-docs")
    assert proc.returncode == 0, proc.stdout + proc.stderr

    rows = _trace_rows(repo)
    assert len(rows) == 1, rows
    r = rows[0]
    assert (r["actor"], r["branch"], r["action"], r["exit"]) == ("合入", "claude/ok-docs", "合入", 0)
    assert all(r["gates"][k] is True for k in ("①备份ref", "②脏文件零交集", "③rebase零冲突", "④回归零新增", "⑤ff+push", "⑥四ref一致")), r["gates"]
    assert r["failed_branch"] == [] and r["failed_master"] == []
    assert r["master_after"] == _git(repo, "rev-parse", "--short", "master")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}", r["ts"]), "ts 须为本地 ISO 8601 带偏移"
    # 真的进 master 且推到了 origin
    assert _git(repo, "rev-parse", "master") == _git(repo, "rev-parse", "origin/master") == _git(repo, "rev-parse", "claude/ok-docs")


def test_merge_rejected_by_regression_records_both_failure_sets(repo: Path, tmp_path: Path):
    """④ 拒绝：分支把 test_tool.py 改红，纯 master 同命令全绿 ⇒ 新增失败 ⇒ exit 4，两侧失败集合落盘。"""
    _branch_with(repo, "claude/reject-regress", {
        "test_tool.py": "from tool import f\n\n\ndef test_f():\n    assert f() == 2\n",
    })
    proc = _run_merge(repo, tmp_path, "claude/reject-regress", tests="test_tool.py")
    assert proc.returncode == 4, proc.stdout + proc.stderr

    rows = _trace_rows(repo)
    assert len(rows) == 1, rows
    r = rows[0]
    assert (r["actor"], r["action"], r["exit"], r["tests"]) == ("合入", "拒绝", 4, "test_tool.py")
    g = r["gates"]
    assert g["①备份ref"] is True and g["②脏文件零交集"] is True and g["③rebase零冲突"] is True
    assert g["④回归零新增"] is False
    assert g["⑤ff+push"] is None and g["⑥四ref一致"] is None, "没走到的关必须是 null，不是 false"
    assert r["failed_branch"] == ["test_tool.py::test_f"]
    assert r["failed_master"] == []
    # master 未动
    assert _git(repo, "rev-parse", "master") == _git(repo, "rev-parse", "origin/master")
    assert subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", "claude/reject-regress", "master"]).returncode != 0


def test_merge_interrupted_by_rebase_conflict(repo: Path, tmp_path: Path):
    """③ 被打断：分支与 master 改同一行 ⇒ rebase 冲突 ⇒ exit 3，action=被打断、③=false、后续关全 null。"""
    _branch_with(repo, "claude/interrupt-conflict", {"README.md": "# branch side\nline2\n"})
    (repo / "README.md").write_text("# master side\nline2\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "master moves the same line")
    _git(repo, "push", "-q", "origin", "master")

    proc = _run_merge(repo, tmp_path, "claude/interrupt-conflict")
    assert proc.returncode == 3, proc.stdout + proc.stderr

    rows = _trace_rows(repo)
    assert len(rows) == 1, rows
    r = rows[0]
    assert (r["actor"], r["action"], r["exit"]) == ("合入", "被打断", 3)
    assert r["gates"]["③rebase零冲突"] is False
    assert r["gates"]["④回归零新增"] is None and r["gates"]["⑤ff+push"] is None
    assert "rebase 冲突" in r["note"]


# ── ⑻ 已合分支再入册即被销 ────────────────────────────────────────────────────

def test_registry_sweep_moves_merged_and_missing_rows_only(repo: Path, tmp_path: Path):
    _branch_with(repo, "claude/already-in", {"a.md": "a\n"})
    _git(repo, "merge", "-q", "--ff-only", "claude/already-in")           # 已是 master 祖先
    _branch_with(repo, "claude/still-pending", {"b.md": "b\n"})            # 真待合
    reg = repo / LEDGER / "pending-ff.jsonl"
    reg.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"branch": "claude/already-in", "authorized_text": "Shao Peishen 答 1a"},
        {"branch": "claude/ghost-branch", "authorized_text": "Shao Peishen 答 2a"},   # 分支已不存在
        {"branch": "claude/still-pending", "authorized_text": "Shao Peishen 答 3a"},
    ]
    reg.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")

    result = _pwsh_lib_json(
        f"$r = Invoke-PendingFfRegistrySweep -Repo '{repo.as_posix()}' -RegistryPath '{reg.as_posix()}'\r\n"
        "$r | ConvertTo-Json -Depth 5 -Compress", tmp_path,
    )
    moved = {m["Branch"]: m["Reason"] for m in result["Moved"]}
    assert moved == {"claude/already-in": "已是 master 祖先", "claude/ghost-branch": "分支已不存在"}
    assert result["Kept"] == 1

    # 登记册只剩真待合行，原文原样
    kept = _read_jsonl(reg)
    assert kept == [rows[2]]
    # done 文件：原字段保留 ＋ done_reason ＋ master_sha
    done = {d["branch"]: d for d in _done_rows(repo)}
    assert set(done) == {"claude/already-in", "claude/ghost-branch"}
    assert done["claude/already-in"]["authorized_text"] == "Shao Peishen 答 1a"
    assert done["claude/already-in"]["done_reason"] == "已是 master 祖先"
    assert done["claude/already-in"]["master_sha"] == _git(repo, "rev-parse", "master")
    assert done["claude/ghost-branch"]["done_reason"] == "分支已不存在"
    assert all("done_at" in d for d in done.values())
    # ⑹ 销行本身也留痕
    trace = [t for t in _trace_rows(repo) if t["action"] == "销行"]
    assert sorted(t["branch"] for t in trace) == ["claude/already-in", "claude/ghost-branch"]
    assert all(t["actor"] == "巡检" for t in trace)

    # 幂等：再跑一次零动作，文件不变
    before_done = _done_rows(repo)
    result2 = _pwsh_lib_json(
        f"$r = Invoke-PendingFfRegistrySweep -Repo '{repo.as_posix()}' -RegistryPath '{reg.as_posix()}'\r\n"
        "$r | ConvertTo-Json -Depth 5 -Compress", tmp_path,
    )
    assert result2["Moved"] == [] and result2["Kept"] == 1
    assert _done_rows(repo) == before_done
    assert _read_jsonl(reg) == [rows[2]]


def test_registry_sweep_dry_run_touches_nothing(repo: Path, tmp_path: Path):
    _branch_with(repo, "claude/already-in", {"a.md": "a\n"})
    _git(repo, "merge", "-q", "--ff-only", "claude/already-in")
    reg = repo / LEDGER / "pending-ff.jsonl"
    reg.parent.mkdir(parents=True, exist_ok=True)
    reg.write_text(json.dumps({"branch": "claude/already-in", "authorized_text": "x"}) + "\n", encoding="utf-8")
    result = _pwsh_lib_json(
        f"$r = Invoke-PendingFfRegistrySweep -Repo '{repo.as_posix()}' -RegistryPath '{reg.as_posix()}' -DryRun\r\n"
        "$r | ConvertTo-Json -Depth 5 -Compress", tmp_path,
    )
    assert [m["Branch"] for m in result["Moved"]] == ["claude/already-in"]
    assert reg.exists() and len(_read_jsonl(reg)) == 1
    assert _done_rows(repo) == [] and _trace_rows(repo) == []


def test_registry_sweep_removes_file_when_everything_is_done(repo: Path, tmp_path: Path):
    _branch_with(repo, "claude/already-in", {"a.md": "a\n"})
    _git(repo, "merge", "-q", "--ff-only", "claude/already-in")
    reg = repo / LEDGER / "pending-ff.jsonl"
    reg.parent.mkdir(parents=True, exist_ok=True)
    reg.write_text(json.dumps({"branch": "claude/already-in", "authorized_text": "x"}) + "\n", encoding="utf-8")
    _pwsh_lib_json(
        f"Invoke-PendingFfRegistrySweep -Repo '{repo.as_posix()}' -RegistryPath '{reg.as_posix()}' | Out-Null", tmp_path,
    )
    assert not reg.exists(), "全部销行后登记册应移除（与动作一 `$kept` 为空即 Remove-Item 同口径）"
    assert [d["branch"] for d in _done_rows(repo)] == ["claude/already-in"]


def test_write_trace_keeps_unparseable_registry_line_verbatim(repo: Path, tmp_path: Path):
    """解析不了的登记行不能被 sweep 丢掉，也不能被误销（它由动作一自己报）。"""
    reg = repo / LEDGER / "pending-ff.jsonl"
    reg.parent.mkdir(parents=True, exist_ok=True)
    reg.write_text("{not json\n", encoding="utf-8")
    result = _pwsh_lib_json(
        f"$r = Invoke-PendingFfRegistrySweep -Repo '{repo.as_posix()}' -RegistryPath '{reg.as_posix()}'\r\n"
        "$r | ConvertTo-Json -Depth 5 -Compress", tmp_path,
    )
    assert result["Moved"] == [] and result["Kept"] == 1
    assert reg.read_text(encoding="utf-8").strip() == "{not json"


# ── 巡检端到端：登记册 → 调合入脚本 → 两个 actor 各留一行 → 销行 ──────────────

def test_patrol_end_to_end_merges_registered_branch_and_leaves_both_traces(repo: Path, tmp_path: Path):
    _branch_with(repo, "claude/registered-docs", {"docs/x.md": "x\n"})
    reg = repo / LEDGER / "pending-ff.jsonl"
    reg.parent.mkdir(parents=True, exist_ok=True)
    reg.write_text(json.dumps({
        "branch": "claude/registered-docs",
        "authorized_text": "Shao Peishen 2026-09-13 答 1a（单测夹具）",
    }, ensure_ascii=False) + "\n", encoding="utf-8")

    proc = _pwsh_file(PATROL, "-Repo", str(repo), "-TempRoot", str(tmp_path), "-NoAutoWhitelist", timeout=600)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "[MERGED] claude/registered-docs" in proc.stdout, proc.stdout

    rows = _trace_rows(repo)
    by_actor = {r["actor"]: r for r in rows if r["branch"] == "claude/registered-docs"}
    assert set(by_actor) == {"巡检", "合入"}, rows
    assert by_actor["合入"]["action"] == "合入" and by_actor["合入"]["exit"] == 0
    assert by_actor["巡检"]["action"] == "合入" and by_actor["巡检"]["merge_exit"] == 0
    assert by_actor["巡检"]["path"] == "登记册"
    assert by_actor["巡检"]["authorized_text"].startswith("Shao Peishen 2026-09-13 答 1a")
    assert by_actor["巡检"]["gates"] == {"授权原文": True, "脏文件零交集": True}

    # 登记册销行：文件已空 ⇒ 移除；done 文件写「本轮合入」
    assert not reg.exists()
    done = _done_rows(repo)
    assert [(d["branch"], d["done_reason"]) for d in done] == [("claude/registered-docs", "本轮合入")]
    assert done[0]["master_sha"] == _git(repo, "rev-parse", "master")
    assert _git(repo, "rev-parse", "master") == _git(repo, "rev-parse", "origin/master")


def test_patrol_registered_branch_already_merged_is_swept_not_remerged(repo: Path, tmp_path: Path):
    """⑺ 当日实证原型：`op0913g` 08:34 已 ff 进 master，09:3x 那行仍在登记册 ⇒ 巡检一跑即销、不再调合入脚本。"""
    _branch_with(repo, "claude/merged-by-hand", {"docs/y.md": "y\n"})
    _git(repo, "merge", "-q", "--ff-only", "claude/merged-by-hand")
    reg = repo / LEDGER / "pending-ff.jsonl"
    reg.parent.mkdir(parents=True, exist_ok=True)
    reg.write_text(json.dumps({"branch": "claude/merged-by-hand", "authorized_text": "x"}) + "\n", encoding="utf-8")

    proc = _pwsh_file(PATROL, "-Repo", str(repo), "-TempRoot", str(tmp_path), "-NoAutoWhitelist", timeout=600)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "[PENDING-SWEPT] 1 行" in proc.stdout, proc.stdout
    assert "[NO-PENDING]" in proc.stdout
    assert not reg.exists()
    assert [(d["branch"], d["done_reason"]) for d in _done_rows(repo)] == [("claude/merged-by-hand", "已是 master 祖先")]
    actors = [r["actor"] for r in _trace_rows(repo)]
    assert actors == ["巡检"], "不该调合入脚本（没有 actor=合入 的行）"
    assert _trace_rows(repo)[0]["action"] == "销行"


def test_patrol_rejected_merge_keeps_registry_row_and_records_exit_code(repo: Path, tmp_path: Path):
    """登记册分支带 tests 且回归新增失败 ⇒ 合入脚本 exit 4 ⇒ 巡检行 action=拒绝、merge_exit=4，登记行保留待人看。
    也直接验证 `Invoke-MergeScript` 拿到的是子进程退出码而不是管道末端的。"""
    _branch_with(repo, "claude/registered-regress", {
        "test_tool.py": "from tool import f\n\n\ndef test_f():\n    assert f() == 2\n",
    })
    reg = repo / LEDGER / "pending-ff.jsonl"
    reg.parent.mkdir(parents=True, exist_ok=True)
    row = {"branch": "claude/registered-regress", "tests": "test_tool.py", "authorized_text": "Shao Peishen 答 1a"}
    reg.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    proc = _pwsh_file(PATROL, "-Repo", str(repo), "-TempRoot", str(tmp_path), "-NoAutoWhitelist", timeout=600)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "合入失败（退出码 4）" in proc.stdout, proc.stdout

    by_actor = {r["actor"]: r for r in _trace_rows(repo)}
    assert set(by_actor) == {"巡检", "合入"}
    assert (by_actor["合入"]["action"], by_actor["合入"]["exit"]) == ("拒绝", 4)
    assert by_actor["合入"]["failed_branch"] == ["test_tool.py::test_f"] and by_actor["合入"]["failed_master"] == []
    assert (by_actor["巡检"]["action"], by_actor["巡检"]["merge_exit"], by_actor["巡检"]["tests"]) == ("拒绝", 4, "test_tool.py")
    assert _read_jsonl(reg) == [row], "被拒的行必须原样留在登记册"
    assert _done_rows(repo) == []


def test_patrol_dry_run_writes_no_trace_and_moves_nothing(repo: Path, tmp_path: Path):
    _branch_with(repo, "claude/already-in", {"a.md": "a\n"})
    _git(repo, "merge", "-q", "--ff-only", "claude/already-in")
    _branch_with(repo, "claude/registered-docs", {"docs/x.md": "x\n"})
    reg = repo / LEDGER / "pending-ff.jsonl"
    reg.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"branch": "claude/already-in", "authorized_text": "x"},
        {"branch": "claude/registered-docs", "authorized_text": "y"},
    ]
    reg.write_text("".join(json.dumps(x) + "\n" for x in rows), encoding="utf-8")

    master_before = _git(repo, "rev-parse", "master")
    proc = _pwsh_file(PATROL, "-Repo", str(repo), "-TempRoot", str(tmp_path), "-NoAutoWhitelist", "-DryRun", timeout=600)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "[DRY] 本可销行" in proc.stdout and "[DRY] claude/registered-docs 前置已满足" in proc.stdout, proc.stdout
    assert _read_jsonl(reg) == rows
    assert _trace_rows(repo) == [] and _done_rows(repo) == []
    assert _git(repo, "rev-parse", "master") == master_before, "干跑不得动 master"
