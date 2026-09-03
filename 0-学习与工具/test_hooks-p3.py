# -*- coding: utf-8 -*-
"""
P3 hooks（队列 §一 `#381`⑸ⓐⓑⓒⓓ，openspec 变更包 `cc-hooks-p3`）端到端单测。

🔴 同 `test_hooks-哨兵.py` 的既有理由：哨兵的契约是「stdin 收 hook JSON → 退出码 ＋
`hookSpecificOutput.additionalContext`」，逐函数测过、契约却对不上，正是
`OP-0819-F`「建成 9 天从没响过」那类事故的成因形态。故本文件一律真跑脚本、真喂
JSON、真断言退出码与输出结构，不 mock PowerShell 进程本身。

范围：本文件只测**独立的 PowerShell 钩子脚本**（ⓐ SessionStart／ⓑ UserPromptSubmit／
ⓒ PreToolUse／ⓓ Stop）。ⓔ（`acquire` 路由提示）与 ⓕ（sweep rules 尺寸巡检）是对既有
Python 工具的直接修改，测试并入各自既有文件
（`test_工具-共享文档编辑锁.py` ／ `test_工具-落库sweep.py`），不在本文件重复。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent / "hooks"
COMMON = HOOKS_DIR / "hooks-common.ps1"
SESSIONSTART = HOOKS_DIR / "hooks-sessionstart-context.ps1"
EDITLOCK_GUARD = HOOKS_DIR / "hooks-pretooluse-editlock-guard.ps1"
STANDING_FIVE = HOOKS_DIR / "hooks-userpromptsubmit-standing-five.ps1"
REPO_ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    shutil.which("pwsh") is None, reason="需要 PowerShell 7（pwsh）"
)


# ─────────────────────────────────────────────────────────────────────────────
# 驱动
# ─────────────────────────────────────────────────────────────────────────────

def run_hook(script: Path, payload: dict, repo_root: Path) -> tuple[int, dict, str]:
    """真跑一次钩子：喂 stdin JSON，返回 `(退出码, 解析后的 stdout JSON 或 {}, stderr)`。"""
    env = dict(os.environ)
    env["ZHUOPIN_SENTINEL_REPO_ROOT"] = str(repo_root)
    proc = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(script)],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        capture_output=True,
        env=env,
        cwd=str(repo_root),
    )
    out = proc.stdout.decode("utf-8", errors="replace").strip()
    err = proc.stderr.decode("utf-8", errors="replace")
    parsed: dict = {}
    if out:
        try:
            parsed = json.loads(out)
        except json.JSONDecodeError:
            pass
    return proc.returncode, parsed, err


def audit_lines(repo_root: Path) -> list[dict]:
    p = repo_root / "reports" / "hooks-audit.jsonl"
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


QUEUE_REL = "1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md"


def write_minimal_queue(repo_root: Path, section_one_rows: list[str]) -> None:
    p = repo_root / QUEUE_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(
        ["# 跨桌任务队列（测试夹具）", "", "## 一、任务看板", ""]
        + section_one_rows
        + ["", "## 二、待 commit 批次（CC 取活销行）", "", "（空）"]
    )
    p.write_text(body, encoding="utf-8")


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """非 git 目录夹具：练 fail-open 路径（无 `.git` 时 fsck/rev-list 均应失败但不崩）。"""
    (tmp_path / "reports").mkdir()
    return tmp_path


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    """真实最小 git 仓库：有 `master` 分支与一个提交，练「正常在办」路径。"""
    (tmp_path / "reports").mkdir()

    def run(*args):
        subprocess.run(["git", *args], cwd=str(tmp_path), check=True,
                        capture_output=True)

    run("init", "-q", "-b", "master")
    run("config", "user.email", "test@example.com")
    run("config", "user.name", "Test")
    (tmp_path / "README.md").write_text("test\n", encoding="utf-8")
    run("add", "README.md")
    run("commit", "-q", "-m", "init")
    return tmp_path


# ─────────────────────────────────────────────────────────────────────────────
# ⓐ SessionStart（hooks-sessionstart-context.ps1）
# ─────────────────────────────────────────────────────────────────────────────

class TestSessionStartContext:
    def test_脚本文件齐备(self):
        assert COMMON.is_file()
        assert SESSIONSTART.is_file()

    def test_非git目录仍fail_open且留痕(self, repo: Path):
        """无 `.git`：fsck/rev-list 必然失败，但钩子本身不得以非零退出码收尾。"""
        rc, out, err = run_hook(SESSIONSTART, {"session_id": "s1"}, repo)
        assert rc == 0, err
        ctx = out.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "本地" in ctx and "UTC" in ctx
        lines = audit_lines(repo)
        assert len(lines) == 1
        assert lines[0]["hook"] == "sessionstart-context"
        assert lines[0]["sessionId"] == "s1"

    def test_真实git仓库_双标时刻与ahead_behind(self, git_repo: Path):
        rc, out, err = run_hook(SESSIONSTART, {"session_id": "s2"}, git_repo)
        assert rc == 0, err
        ctx = out.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "仓库连通性正常" in ctx or "git fsck" in ctx
        # 无 origin 时 ahead/behind 不可解析，须显式说明、不得假装 0/0。
        assert "ahead/behind 不可用" in ctx or "ahead=" in ctx

    def test_队列文件缺失_显式说明不静默(self, git_repo: Path):
        rc, out, err = run_hook(SESSIONSTART, {"session_id": "s3"}, git_repo)
        assert rc == 0, err
        ctx = out.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "待领队列摘要不可用" in ctx

    def test_队列有待领行_摘要含编号(self, git_repo: Path):
        write_minimal_queue(git_repo, [
            "| 501 | [S:open] 🔄 测试任务甲 | 待领 | x | y | z | 2026-09-04 |",
            # 🔴 真实生产形态（同 §一 现网多行）：[S:open] 之后紧跟 [D:机] 与 🛑，
            # 表示"状态字段仍是 open，但因 WIP 顶格排队中"——本行不应计入待领摘要。
            "| 502 | [S:open][D:机] 🛑 **排队中（WIP 满）** 测试任务乙 | 待领 | x | y | z | 2026-09-04 |",
            "| 503 | [S:done] 测试任务丙已完成 | - | x | y | z | 2026-09-04 |",
        ])
        rc, out, err = run_hook(SESSIONSTART, {"session_id": "s4"}, git_repo)
        assert rc == 0, err
        ctx = out.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "#501" in ctx
        assert "#503" not in ctx  # done 不算待领

    def test_stdin为空仍放行(self, git_repo: Path):
        proc = subprocess.run(
            ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(SESSIONSTART)],
            input=b"",
            capture_output=True,
            env={**os.environ, "ZHUOPIN_SENTINEL_REPO_ROOT": str(git_repo)},
            cwd=str(git_repo),
        )
        assert proc.returncode == 0

    def test_每次运行都追加审计行_不覆盖(self, git_repo: Path):
        run_hook(SESSIONSTART, {"session_id": "a"}, git_repo)
        run_hook(SESSIONSTART, {"session_id": "b"}, git_repo)
        lines = audit_lines(git_repo)
        assert len(lines) == 2
        assert {l["sessionId"] for l in lines} == {"a", "b"}


# ─────────────────────────────────────────────────────────────────────────────
# ⓒ PreToolUse 编辑锁门禁（hooks-pretooluse-editlock-guard.ps1）
# ─────────────────────────────────────────────────────────────────────────────

QUEUE_MECH_REL = "1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md"
QUEUE_BIZ_REL = "1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md"
RELAY_CARD_REL = "1-转型规划/0-全景路线图/session接力-Phase1收口.md"


def pretooluse_payload(repo_root: Path, rel_target: str, tool: str = "Edit") -> dict:
    return {
        "session_id": "test-session",
        "cwd": str(repo_root),
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": {"file_path": str(repo_root / rel_target)},
    }


def write_lock(repo_root: Path, anchor_rel: str, *, minutes_ago: float = 1.0,
               released: bool = False, who: str = "CC-test", corrupt: bool = False) -> Path:
    from datetime import datetime, timedelta, timezone
    lock_path = repo_root / (anchor_rel + ".editlock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if corrupt:
        lock_path.write_text("{not valid json", encoding="utf-8")
        return lock_path
    held_since = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    payload = {"who": who, "note": "test", "held_since": held_since, "history": []}
    if released:
        payload["released"] = True
    lock_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return lock_path


def touch(repo_root: Path, rel: str, content: str = "占位\n") -> None:
    p = repo_root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text(content, encoding="utf-8")


class TestPreToolUseEditlockGuard:
    def test_脚本文件存在(self):
        assert EDITLOCK_GUARD.is_file()

    def test_非受保护文件放行(self, repo: Path):
        rc, out, err = run_hook(
            EDITLOCK_GUARD, pretooluse_payload(repo, "4-数字员工/某场景/CLAUDE.md"), repo)
        assert rc == 0, err

    def test_无锁时拦截机制环境队列(self, repo: Path):
        touch(repo, QUEUE_MECH_REL)
        rc, out, err = run_hook(EDITLOCK_GUARD, pretooluse_payload(repo, QUEUE_MECH_REL), repo)
        assert rc == 2
        assert "acquire" in err
        lines = audit_lines(repo)
        assert lines[-1]["verdict"] == "violation"

    def test_有效锁放行(self, repo: Path):
        touch(repo, QUEUE_MECH_REL)
        write_lock(repo, QUEUE_MECH_REL, minutes_ago=1.0)
        rc, out, err = run_hook(EDITLOCK_GUARD, pretooluse_payload(repo, QUEUE_MECH_REL), repo)
        assert rc == 0, err
        assert audit_lines(repo)[-1]["verdict"] == "pass"

    def test_业务场景队列共用机制环境锚点的锁(self, repo: Path):
        """`QUEUE_LOCK_ANCHOR` 恒为机制环境文件——业务场景队列的锁文件不是它自己的
        `.editlock`，而是机制环境文件那一份（同 `工具-共享文档编辑锁.py` 既有语义）。"""
        touch(repo, QUEUE_BIZ_REL)
        write_lock(repo, QUEUE_MECH_REL, minutes_ago=1.0)  # 锁写在锚点，不是业务场景自己
        rc, out, err = run_hook(EDITLOCK_GUARD, pretooluse_payload(repo, QUEUE_BIZ_REL), repo)
        assert rc == 0, err

    def test_陈旧锁视为无效(self, repo: Path):
        touch(repo, QUEUE_MECH_REL)
        write_lock(repo, QUEUE_MECH_REL, minutes_ago=45.0)  # 超过 30 分钟阈值
        rc, out, err = run_hook(EDITLOCK_GUARD, pretooluse_payload(repo, QUEUE_MECH_REL), repo)
        assert rc == 2
        assert "陈旧" in err

    def test_已release的锁视为无效(self, repo: Path):
        """release 是"改写为 released 标记、不删除文件"——held_since 仍在有效期内
        但已释放，必须仍判为无锁（同 `_read_lock` 既有语义）。"""
        touch(repo, QUEUE_MECH_REL)
        write_lock(repo, QUEUE_MECH_REL, minutes_ago=1.0, released=True)
        rc, out, err = run_hook(EDITLOCK_GUARD, pretooluse_payload(repo, QUEUE_MECH_REL), repo)
        assert rc == 2
        assert "release" in err

    def test_锁文件损坏视为无效_不崩溃(self, repo: Path):
        touch(repo, QUEUE_MECH_REL)
        write_lock(repo, QUEUE_MECH_REL, corrupt=True)
        rc, out, err = run_hook(EDITLOCK_GUARD, pretooluse_payload(repo, QUEUE_MECH_REL), repo)
        assert rc == 2
        assert "解析失败" in err

    def test_接力卡使用独立于队列锚点的锁(self, repo: Path):
        """接力卡不属于 `_is_queue_system_target`，各自持锁——机制环境的锁对它无效。"""
        touch(repo, RELAY_CARD_REL)
        write_lock(repo, QUEUE_MECH_REL, minutes_ago=1.0)  # 只给队列锚点上锁，不给接力卡
        rc, out, err = run_hook(EDITLOCK_GUARD, pretooluse_payload(repo, RELAY_CARD_REL), repo)
        assert rc == 2, "队列锚点的锁不应覆盖接力卡"

        write_lock(repo, RELAY_CARD_REL, minutes_ago=1.0)  # 给接力卡自己上锁
        rc2, out2, err2 = run_hook(EDITLOCK_GUARD, pretooluse_payload(repo, RELAY_CARD_REL), repo)
        assert rc2 == 0, err2

    def test_非Edit类工具不受约束(self, repo: Path):
        touch(repo, QUEUE_MECH_REL)
        rc, out, err = run_hook(
            EDITLOCK_GUARD, pretooluse_payload(repo, QUEUE_MECH_REL, tool="Bash"), repo)
        assert rc == 0, err

    def test_缺file_path时fail_open(self, repo: Path):
        payload = {
            "session_id": "s", "cwd": str(repo), "hook_event_name": "PreToolUse",
            "tool_name": "Edit", "tool_input": {},
        }
        rc, out, err = run_hook(EDITLOCK_GUARD, payload, repo)
        assert rc == 0, err
        assert audit_lines(repo)[-1]["verdict"] == "undetermined"


# ─────────────────────────────────────────────────────────────────────────────
# ⓑ UserPromptSubmit 常驻五条（hooks-userpromptsubmit-standing-five.ps1）
# ─────────────────────────────────────────────────────────────────────────────

def write_root_claude_md(repo_root: Path, items: dict[int, str]) -> None:
    """构造一份带 `<!-- UPS5:n -->` 锚点的最小根 CLAUDE.md 夹具。

    `items`：`{锚点编号: 该行正文}`，编号可以不连续/不从 1 开始/重复出现同一编号
    （多次调用同一 key 需在调用方自行拼多行），用于覆盖"缺失/重复"两类异常路径。
    """
    lines = ["# CLAUDE.md（测试夹具）", ""]
    for idx, body in items.items():
        lines.append(f"- {body}<!-- UPS5:{idx} -->")
    (repo_root / "CLAUDE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def get_context(out: dict) -> str:
    return out.get("hookSpecificOutput", {}).get("additionalContext", "")


class TestUserPromptSubmitStandingFive:
    def test_脚本文件存在(self):
        assert STANDING_FIVE.is_file()

    def test_五条齐全时全部出现且各自截断在预算内(self, repo: Path):
        write_root_claude_md(repo, {
            1: "称呼一律「Shao Peishen」，不用「Paul」",
            2: "禁从名字推断性别；正本之外称「该专员／其／对方」",
            3: "决策清单须带 (a)/(b) 选项标签、写清代价、标默认项",
            4: "可粘贴 prompt 必标粘贴端 `▶ 粘贴端：Cowork／CC`",
            5: "默认项须先问：谁执行？代价是停滞还是错误继续？",
        })
        rc, out, err = run_hook(STANDING_FIVE, {"session_id": "s"}, repo)
        assert rc == 0, err
        ctx = get_context(out)
        assert "⚠" not in ctx
        for kw in ("称呼一律", "禁从名字推断性别", "决策清单须带", "可粘贴 prompt", "默认项须先问"):
            assert kw in ctx, f"缺 {kw}：{ctx}"
        body_bytes = len(ctx[len("📌 常驻五条："):].encode("utf-8"))
        assert body_bytes <= 300
        assert audit_lines(repo)[-1]["verdict"] == "pass"

    def test_长文本各条仍全部出现不因总预算被整条挤掉(self, repo: Path):
        """🔴 回归锁：曾经的实现"各截 80B 再整体截 300B"会让第 5 条整条从尾部消失——
        改为按实得条数均分预算后，5 条都必须在，只是每条更短。"""
        long_text = "这是一段刻意写得很长的正文用来测试截断行为是否会让后面的条目整条消失不见" * 2
        write_root_claude_md(repo, {i: f"第{i}条：{long_text}" for i in range(1, 6)})
        rc, out, err = run_hook(STANDING_FIVE, {"session_id": "s"}, repo)
        assert rc == 0, err
        ctx = get_context(out)
        for i in range(1, 6):
            assert f"第{i}条" in ctx, f"第{i}条从输出中消失了：{ctx}"

    def test_锚点缺失时可见不静默(self, repo: Path):
        write_root_claude_md(repo, {1: "只有第一条", 2: "只有第二条", 3: "只有第三条"})
        rc, out, err = run_hook(STANDING_FIVE, {"session_id": "s"}, repo)
        assert rc == 0, err
        ctx = get_context(out)
        assert "预期 5" in ctx and "实得 3" in ctx
        assert "只有第一条" in ctx  # 找到的仍要展示，不因为不全就整体隐藏
        assert audit_lines(repo)[-1]["verdict"] == "undetermined"

    def test_锚点重复时报告不静默选一个(self, repo: Path):
        lines = [
            "# CLAUDE.md（测试夹具）", "",
            "- 第一次出现<!-- UPS5:2 -->",
            "- 第二次出现同编号<!-- UPS5:2 -->",
            "- 三<!-- UPS5:3 -->", "- 四<!-- UPS5:4 -->",
            "- 五<!-- UPS5:5 -->", "- 一<!-- UPS5:1 -->",
        ]
        (repo / "CLAUDE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        rc, out, err = run_hook(STANDING_FIVE, {"session_id": "s"}, repo)
        assert rc == 0, err
        ctx = get_context(out)
        assert "重复编号" in ctx and "2" in ctx

    def test_根CLAUDE_md不存在时fail_open(self, repo: Path):
        rc, out, err = run_hook(STANDING_FIVE, {"session_id": "s"}, repo)
        assert rc == 0, err
        ctx = get_context(out)
        assert "不可用" in ctx
        assert audit_lines(repo)[-1]["verdict"] == "error"

    def test_stdin为空仍能工作(self, repo: Path):
        write_root_claude_md(repo, {i: f"第{i}条" for i in range(1, 6)})
        proc = subprocess.run(
            ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(STANDING_FIVE)],
            input=b"",
            capture_output=True,
            env={**os.environ, "ZHUOPIN_SENTINEL_REPO_ROOT": str(repo)},
            cwd=str(repo),
        )
        assert proc.returncode == 0

    def test_真实根CLAUDE_md五条齐全零漂移(self):
        """对**真实**根 `CLAUDE.md`（本 worktree 已按 ⓑ 建造插好五处锚点）跑一次——
        既是回归锁，也是"锚点真的插对了地方"的生产前验活。"""
        rc, out, err = run_hook(STANDING_FIVE, {"session_id": "s"}, REPO_ROOT)
        assert rc == 0, err
        ctx = get_context(out)
        assert "⚠" not in ctx, f"真实根 CLAUDE.md 的锚点数量或格式有异常：{ctx}"
