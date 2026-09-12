"""可 Open 池两侧对账断言（队列 #312，Shao Peishen 2026-09-02 裁定「以看板判据为准」；
`OP-0912-H` 落地）——锁死「**两侧对同一份队列真身算出的池必须逐行相同**」。

两侧 ＝ ① 企微推送器 `aibot_service.open_pool_reminder.build_pool_items_from_repo`
（直接 import 权威模块 `shared_tools/open_pool.py`）；② 看板 artifact 数据层
`0-学习与工具/工具-项目状态卡数据层.ps1`（经 `工具-可Open池.py --json-b64` 子进程调
同一模块）。裁定原文：「对齐不是抄一遍判据，是让两侧共用同一个判定函数」——本文件
不是在验证两份判据抄得像不像，是在验证**接线**：ps1 拿到的确实是那同一个函数的输出，
且推送器没有在权威模块之外再叠一层自己的过滤。

三层：⑴ 合成夹具上推送器 vs CLI（每个判据分支各一行，任一侧私加过滤即红）；
⑵ 生产队列真身上推送器 vs CLI；⑶ 生产队列真身上推送器 vs **真跑 ps1**（需 pwsh／
powershell 与看板硬编码的仓库根 `C:\\Dev\\zhuopin-ai` 在位，缺则 skip 并说明——
不假装验过）。
"""
from __future__ import annotations

import base64
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from aibot_service.open_pool_reminder import build_pool_items_from_repo
from zhuopin_platform.shared_tools.queue_table import iter_queue_paths

REPO_ROOT = Path(__file__).resolve().parents[3]
CLI = REPO_ROOT / "0-学习与工具" / "工具-可Open池.py"
KANBAN_PS1 = REPO_ROOT / "0-学习与工具" / "工具-项目状态卡数据层.ps1"

_HEADER = (
    "## 一、任务看板\n\n"
    "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
    "|---|------|--------|-------------|----------|------|--------|------|\n"
)


def _row(no: str, task: str, status: str, owner: str = "待领") -> str:
    return f"| {no} | {task} | {owner} | 输入 | 产出 | {status} | — | 09-12 |\n"


def _run_cli(repo_root: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", str(CLI), "--repo-root", str(repo_root), "--json-b64"],
        capture_output=True, text=True, encoding="utf-8",
    )
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("@@POOL64@@")), None)
    assert line is not None, f"CLI 未输出 @@POOL64@@：rc={proc.returncode} stderr={proc.stderr[-400:]}"
    return json.loads(base64.b64decode(line[len("@@POOL64@@"):]).decode("utf-8"))


def _reminder_view(repo_root: Path) -> list[tuple[str, str | None, str | None]]:
    return sorted(
        (i.row_id, i.domain, i.status) for i in build_pool_items_from_repo(repo_root)
    )


def _cli_view(payload: dict) -> list[tuple[str, str | None, str | None]]:
    return sorted((p["no"], p["dom"], p["st"]) for p in payload["pool"])


# ── ⑴ 合成夹具：每个判据分支各一行 ─────────────────────────────────────────

_MECH = (
    _HEADER
    + _row("1", "open 入池", "[S:open][D:机] 待领")
    + _row("2", "partial 入池", "[S:partial][D:机] 🟡 尾巴待领")
    + _row("3", "partial 首标记✅ 带 flag", "[S:partial][D:机] ✅ 主体交付，尾巴待领")
    + _row("4", "partial 自陈在办排除", "[S:partial][D:机] 🔄 在办中")
    + _row("5", "assigned 排除", "[S:open][D:机][A:已派出] 🔄 在办")
    + _row("6", "状态列🛑排除", "[S:open][D:机] 🛑 排队中")
    + _row("7", "🛑 排队中·暂非可动（任务列🛑，#381 形态）", "[S:open][D:机] 待领")
    + _row("9", "hold 排除", "[S:hold][D:机] ⏸")
    + _row("10", "缺域 degraded", "[S:open] 待领")
    + _row("11", "缺字段 degraded", "待领（历史）")
    + "| 12 | 撑列 skipped | 待领 | 输入 | 产出 | [S:open][D:机] | — | 多 | 09-12 |\n"
)
_BIZ = (
    _HEADER
    + _row("21", "业务 open 入池", "[S:open][D:业] 待领")
    + _row("22", "业务 blocked 排除", "[S:blocked][D:业] 等回件")
    + _row("23", "业务 timed 排除", "[S:timed=2026-10-01][D:业] 定时")
)


def _write_dual(repo_root: Path, mech: str, biz: str) -> None:
    mech_rel, biz_rel = iter_queue_paths()
    for rel, text in ((mech_rel, mech), (biz_rel, biz)):
        p = repo_root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def test_synthetic_fixture_reminder_equals_kanban_cli(tmp_path: Path):
    _write_dual(tmp_path, _MECH, _BIZ)
    payload = _run_cli(tmp_path)
    assert _reminder_view(tmp_path) == _cli_view(payload)
    # 判据分支全覆盖的期望池（任一分支漂了这里也红，不只靠两侧互相印证）
    assert [p["no"] for p in payload["pool"]] == ["1", "2", "3", "21"]
    assert [p["no"] for p in payload["poolEx"]] == ["4"]
    assert payload["poolDeg"] == ["10", "11"]
    assert payload["skipped"] == ["12"]
    assert next(p for p in payload["pool"] if p["no"] == "3")["flag"] != ""


def test_synthetic_fixture_mutation_reminder_side_filter_would_be_caught(tmp_path: Path):
    """变异验证：若推送器在权威模块之外私加一层「只取 open」（2026-09-02 之前的形态），
    ⑴ 必红。这里用「把 partial 行从推送器视图里去掉」模拟那次漂移。"""
    _write_dual(tmp_path, _MECH, _BIZ)
    payload = _run_cli(tmp_path)
    drifted = [t for t in _reminder_view(tmp_path) if t[2] != "partial"]
    assert drifted != _cli_view(payload)


# ── ⑵ 生产队列真身：推送器 vs CLI ──────────────────────────────────────────


def test_real_queue_reminder_equals_kanban_cli():
    payload = _run_cli(REPO_ROOT)
    assert payload["errors"] == []
    assert _reminder_view(REPO_ROOT) == _cli_view(payload)


# ── ⑶ 生产队列真身：推送器 vs 真跑看板 ps1 ─────────────────────────────────


def _find_powershell() -> str | None:
    for name in ("pwsh", "powershell"):
        exe = shutil.which(name)
        if exe:
            return exe
    return None


def test_real_queue_reminder_equals_kanban_ps1_pool():
    """真跑 `工具-项目状态卡数据层.ps1`（从本 checkout 起，脚本用本 checkout 的代码、
    数据读它硬编码的 `$root`），取其 `pool`／`src.q1`／`src.pool`，与推送器对该 `$root`
    的结果逐行比对。这是 `open-pool-assigned-field-and-opener-env-filter` tasks 3.2
    「两处真跑比对」的机器版——此前那一步要靠人打开看板读一个数。"""
    shell = _find_powershell()
    if shell is None:
        pytest.skip("本机无 pwsh／powershell，无法真跑看板数据层 ps1（未验，非通过）")
    # 先把控制台输出编码钉成 UTF-8 再起脚本：PS 5.1 默认按系统代码页（本机 GBK）输出，
    # `机／业` 会被本进程按 UTF-8 解成替换符而误判成两侧不一致。
    command = "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; & '" + str(KANBAN_PS1).replace("'", "''") + "'"
    proc = subprocess.run(
        [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
    )
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("@@JSON@@")), None)
    assert line is not None, f"ps1 未输出 @@JSON@@：rc={proc.returncode} stderr={proc.stderr[-400:]}"
    data = json.loads(line[len("@@JSON@@"):])
    if not data.get("rootOk"):
        pytest.skip(f"看板硬编码仓库根不在位：{data.get('root')}（未验，非通过）")
    assert data["src"]["pool"]["ok"] is True, data["src"]["pool"]["why"]
    assert data["src"]["q1"]["ok"] is True, data["src"]["q1"]["why"]
    kanban = sorted((p["no"], p["dom"], p["st"]) for p in data["pool"])
    reminder = _reminder_view(Path(data["root"]))
    assert kanban == reminder, (
        f"看板独有 {sorted(set(kanban) - set(reminder))}；推送器独有 {sorted(set(reminder) - set(kanban))}"
    )
