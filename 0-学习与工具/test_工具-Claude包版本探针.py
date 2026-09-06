# -*- coding: utf-8 -*-
"""
`工具-Claude包版本探针.ps1`（队列 §一 `#486`，OP-0906-J）单测。

🔴 同 `test_hooks-p3.py` 的既有理由：真跑脚本、真喂环境变量、真断言 stdout 契约，
不 mock PowerShell 进程本身。夹具注入的是**三处原始读数**
（`ZHUOPIN_CLAUDE_PROBE_FAKE` 里的 `registered` / `servicePathName` / `stagedDirs`），
**不是判定结果** —— 版本抠取、四段版本比较、引号包裹的 `PathName` 解析这些真正会出错的
地方，必须被测到。

覆盖的组合（队列行「构造三种版本值组合」的展开）：
  ⑴ 三者一致                      ⇒ ok，且 BannerLine 为空（正常态不加噪音）
  ⑵ 暂存里有更高版本（其中一个不一致）⇒ pending-update
  ⑶ 服务 PathName 版本不一致        ⇒ service-drift
  ⑷ 二者同时不一致（全不一致）       ⇒ pending-update 优先，但两条 reason 都在
  ⑸ 低版本残留目录                  ⇒ **不**触发（这是本探针相对队列行字面的收紧口径，
                                     用例把它钉死，防后来者「照字面改回去」）
  ⑹ 任一处读不出来                  ⇒ unknown，绝不因「没看见差异」而报 ok
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent
PROBE = TOOLS_DIR / "工具-Claude包版本探针.ps1"
SESSIONSTART = TOOLS_DIR / "hooks" / "hooks-sessionstart-context.ps1"
REPO_ROOT = TOOLS_DIR.parent

pytestmark = pytest.mark.skipif(
    shutil.which("pwsh") is None, reason="需要 PowerShell 7（pwsh）"
)

PFN = "pzs8sxrjxfjjc"


def pkg_dir(version: str) -> str:
    return f"Claude_{version}_x64__{PFN}"


def svc_path(version: str) -> str:
    """生产里 `Win32_Service.PathName` 是**带引号**的整串，夹具照抄这个形态。"""
    return (
        f'"C:\\Program Files\\WindowsApps\\{pkg_dir(version)}'
        f'\\app\\resources\\cowork-svc.exe"'
    )


def run_probe(fake: dict | None, *args: str) -> tuple[int, str]:
    env = dict(os.environ)
    if fake is None:
        env.pop("ZHUOPIN_CLAUDE_PROBE_FAKE", None)
    else:
        env["ZHUOPIN_CLAUDE_PROBE_FAKE"] = json.dumps(fake, ensure_ascii=False)
    proc = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(PROBE), *args],
        capture_output=True,
        env=env,
        cwd=str(REPO_ROOT),
    )
    return proc.returncode, proc.stdout.decode("utf-8", errors="replace").strip()


def verdict_of(fake: dict | None) -> dict:
    rc, out = run_probe(fake, "-Json")
    # 🔴 探针是诊断件不是门禁：退出码恒 0，判定只走 stdout。这条本身也要守住。
    assert rc == 0, f"探针退出码应恒为 0，实得 {rc}；输出={out}"
    assert out, "探针 -Json 无输出"
    return json.loads(out)


def banner_of(fake: dict | None) -> str:
    rc, out = run_probe(fake, "-BannerLine")
    assert rc == 0
    return out


# ─────────────────────────────────────────────────────────────────────────────
# ⑴ 全一致
# ─────────────────────────────────────────────────────────────────────────────

def test_三者一致时判定ok():
    v = verdict_of(
        {
            "registered": ["1.46388.4.0"],
            "servicePathName": svc_path("1.46388.4.0"),
            "stagedDirs": [pkg_dir("1.46388.4.0")],
        }
    )
    assert v["verdict"] == "ok"
    assert v["registeredVersion"] == "1.46388.4.0"
    assert v["serviceVersion"] == "1.46388.4.0"
    assert v["pendingVersions"] == []
    assert v["errors"] == []
    assert v["remedy"] == "", "ok 态不该给补救动作"


def test_ok时开场横幅一行都不加():
    """正常态加行 ＝ 把横幅训练成背景音，故 ok 必须输出空串。"""
    assert (
        banner_of(
            {
                "registered": ["1.46388.4.0"],
                "servicePathName": svc_path("1.46388.4.0"),
                "stagedDirs": [pkg_dir("1.46388.4.0")],
            }
        )
        == ""
    )


# ─────────────────────────────────────────────────────────────────────────────
# ⑵ 暂存里有更高版本 —— 本探针的主信号（2026-09-04 15:42 强关事件的形态）
# ─────────────────────────────────────────────────────────────────────────────

def test_暂存更高版本判定pending_update():
    v = verdict_of(
        {
            "registered": ["1.46388.4.0"],
            "servicePathName": svc_path("1.46388.4.0"),
            "stagedDirs": [pkg_dir("1.46388.4.0"), pkg_dir("1.46388.5.0")],
        }
    )
    assert v["verdict"] == "pending-update"
    assert v["pendingVersions"] == ["1.46388.5.0"]
    assert v["remedy"], "非 ok 态必须带补救动作"
    assert "Restart-Service CoworkVMService -Force" in v["remedy"]


def test_pending时横幅一行含两个版本与补救():
    line = banner_of(
        {
            "registered": ["1.46388.4.0"],
            "servicePathName": svc_path("1.46388.4.0"),
            "stagedDirs": [pkg_dir("1.46388.5.0")],
        }
    )
    assert line, "pending-update 必须出横幅行"
    assert "\n" not in line, "开场横幅只许多打一行"
    assert "1.46388.4.0" in line and "1.46388.5.0" in line
    assert "勿直接开长会话" in line


def test_四段版本按数值比较而非字符串():
    """`1.9.0.0` > `1.46388.4.0` 只在字符串序下成立；必须走 [version] 数值比较。"""
    v = verdict_of(
        {
            "registered": ["1.46388.4.0"],
            "servicePathName": svc_path("1.46388.4.0"),
            "stagedDirs": [pkg_dir("1.9.0.0")],
        }
    )
    assert v["verdict"] == "ok", "1.9.0.0 数值上低于 1.46388.4.0，不该报 pending"
    assert v["staleStagedVersions"] == ["1.9.0.0"]


# ─────────────────────────────────────────────────────────────────────────────
# ⑶ 服务 PathName 版本错位
# ─────────────────────────────────────────────────────────────────────────────

def test_服务PathName版本不一致判定service_drift():
    v = verdict_of(
        {
            "registered": ["1.46388.4.0"],
            "servicePathName": svc_path("1.46388.1.0"),
            "stagedDirs": [pkg_dir("1.46388.4.0"), pkg_dir("1.46388.1.0")],
        }
    )
    assert v["verdict"] == "service-drift"
    assert v["serviceVersion"] == "1.46388.1.0"
    assert v["registeredVersion"] == "1.46388.4.0"
    assert any("PathName" in r for r in v["reasons"])


# ─────────────────────────────────────────────────────────────────────────────
# ⑷ 全不一致 —— 两条 reason 都得在，verdict 取更急的那个
# ─────────────────────────────────────────────────────────────────────────────

def test_两种错位同时成立时pending优先且两条理由都在():
    v = verdict_of(
        {
            "registered": ["1.46388.4.0"],
            "servicePathName": svc_path("1.46388.1.0"),
            "stagedDirs": [pkg_dir("1.46388.1.0"), pkg_dir("1.46388.9.0")],
        }
    )
    assert v["verdict"] == "pending-update"
    assert v["pendingVersions"] == ["1.46388.9.0"]
    joined = " ".join(v["reasons"])
    assert "已暂存未注册" in joined
    assert "PathName" in joined


# ─────────────────────────────────────────────────────────────────────────────
# ⑸ 低版本残留 —— 收紧口径的钉子
# ─────────────────────────────────────────────────────────────────────────────

def test_低于已注册版本的残留目录不触发提示():
    """
    🔴 这条是**故意与队列 `#486` 行字面不同**的口径：行内写「三者不一致即提示」，
    但本机常年躺着 3 个低版本残留目录，照字面实现＝每次开场都误报，而
    `Restart-Service` 对残留毫无作用。本用例把「残留不报警」钉死，
    防后来者按字面把它改回去。
    """
    v = verdict_of(
        {
            "registered": ["1.46388.4.0"],
            "servicePathName": svc_path("1.46388.4.0"),
            "stagedDirs": [
                pkg_dir("1.30096.0.0"),
                pkg_dir("1.32352.1.0"),
                pkg_dir("1.34493.0.0"),
                pkg_dir("1.46388.4.0"),
            ],
        }
    )
    assert v["verdict"] == "ok"
    assert v["staleStagedVersions"] == ["1.30096.0.0", "1.32352.1.0", "1.34493.0.0"]
    assert banner_of(
        {
            "registered": ["1.46388.4.0"],
            "servicePathName": svc_path("1.46388.4.0"),
            "stagedDirs": [pkg_dir("1.30096.0.0"), pkg_dir("1.46388.4.0")],
        }
    ) == ""


# ─────────────────────────────────────────────────────────────────────────────
# ⑹ 读不到 ⇒ unknown，绝不当 ok
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "missing", ["registered", "servicePathName", "stagedDirs"]
)
def test_任一处读不出来一律unknown(missing: str):
    fake = {
        "registered": ["1.46388.4.0"],
        "servicePathName": svc_path("1.46388.4.0"),
        "stagedDirs": [pkg_dir("1.46388.4.0")],
    }
    fake[missing] = None
    v = verdict_of(fake)
    assert v["verdict"] == "unknown", f"{missing} 读不到时不得报 ok"
    assert v["errors"], "unknown 必须给出读不到的原因"


def test_unknown时横幅出一行且说明读不到不等于没错位():
    fake = {
        "registered": None,
        "servicePathName": svc_path("1.46388.4.0"),
        "stagedDirs": [pkg_dir("1.46388.4.0")],
    }
    line = banner_of(fake)
    assert line
    assert "\n" not in line
    assert "读不到 ≠ 没有错位" in line


def test_服务PathName抠不到版本时算unknown():
    v = verdict_of(
        {
            "registered": ["1.46388.4.0"],
            "servicePathName": '"C:\\somewhere\\else\\cowork-svc.exe"',
            "stagedDirs": [pkg_dir("1.46388.4.0")],
        }
    )
    assert v["verdict"] == "unknown"
    assert any("PathName" in e for e in v["errors"])


def test_空的已注册列表算读不到而不是ok():
    """`Get-AppxPackage` 返回空 ＝ 没读到对象，不是「没有错位」。"""
    v = verdict_of(
        {
            "registered": [],
            "servicePathName": svc_path("1.46388.4.0"),
            "stagedDirs": [pkg_dir("1.46388.4.0")],
        }
    )
    assert v["verdict"] == "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# 真读一次（不构造夹具）—— 只断言契约面，不断言本机具体版本
# ─────────────────────────────────────────────────────────────────────────────

def test_真读本机时输出结构完整且退出码为0():
    v = verdict_of(None)
    assert v["verdict"] in {"ok", "pending-update", "service-drift", "unknown"}
    for key in (
        "registeredVersion",
        "serviceVersion",
        "stagedVersions",
        "pendingVersions",
        "staleStagedVersions",
        "reasons",
        "errors",
        "remedy",
    ):
        assert key in v, f"JSON 契约缺字段 {key}"


def test_探针是只读的_源码里不得出现写操作():
    """
    队列 `#486` 写死「纯只读，不自动改服务、不提权」。这条用**源码扫描**守住，
    因为「不小心加了一句 Restart-Service」是这类工具最典型的漂移形态，
    而运行时测不出来（正常路径根本不会走到那句）。
    """
    import re

    src = PROBE.read_text(encoding="utf-8")
    # 先摘掉 `<# ... #>` 帮助块与整行/行尾 `#` 注释 —— 补救动作文本
    # `Restart-Service CoworkVMService -Force` 是**给人看的提示语**，本来就该出现在
    # 注释与 `$RemedyText` 常量里；要守的是它别变成一句真调用。
    code = re.sub(r"<#.*?#>", "", src, flags=re.DOTALL)
    code = re.sub(r"'[^']*'", "''", code)  # 单引号字面量 → 掏空
    code = re.sub(r'"[^"]*"', '""', code)  # 双引号字面量 → 掏空
    code_lines = []
    for line in code.splitlines():
        line = re.sub(r"(^|\s)#.*$", "", line)  # 整行注释与行尾注释
        stripped = line.strip()
        if stripped:
            code_lines.append(stripped)

    forbidden = [
        "Restart-Service",
        "Stop-Service",
        "Start-Service",
        "Set-Service",
        "Add-AppxPackage",
        "Remove-AppxPackage",
        "Start-Process",
        "New-Item",
        "Set-Content",
        "Out-File",
        "RunAs",
    ]
    for stripped in code_lines:
        for f in forbidden:
            assert f not in stripped, f"探针不得含写操作 `{f}`：{stripped}"


# ─────────────────────────────────────────────────────────────────────────────
# 开场横幅接线 —— 端到端
# ─────────────────────────────────────────────────────────────────────────────

def run_sessionstart(fake: dict | None, repo_root: Path) -> dict:
    env = dict(os.environ)
    env["ZHUOPIN_SENTINEL_REPO_ROOT"] = str(repo_root)
    env.pop("ZHUOPIN_SKIP_CLAUDE_PROBE", None)
    if fake is None:
        env.pop("ZHUOPIN_CLAUDE_PROBE_FAKE", None)
    else:
        env["ZHUOPIN_CLAUDE_PROBE_FAKE"] = json.dumps(fake, ensure_ascii=False)
    proc = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(SESSIONSTART)],
        input=json.dumps({"session_id": "t-486"}, ensure_ascii=False).encode("utf-8"),
        capture_output=True,
        env=env,
        cwd=str(repo_root),
    )
    out = proc.stdout.decode("utf-8", errors="replace").strip()
    assert proc.returncode == 0, out
    return json.loads(out)


@pytest.fixture()
def hook_repo(tmp_path: Path) -> Path:
    """给钩子一个最小仓库根：只要有队列文件即可，其余分支走「不可用」路径。"""
    q = tmp_path / "1-转型规划" / "0-全景路线图"
    q.mkdir(parents=True)
    (q / "跨桌任务队列-机制环境.md").write_text(
        "## 一、待领\n| # | 任务 | 状态 |\n|---|---|---|\n"
        "| 486 | Claude 包版本探针 | [S:open][D:机] 待领 |\n"
        "## 二、待 commit\n",
        encoding="utf-8",
    )
    return tmp_path


def test_横幅在pending时多打一行(hook_repo: Path):
    ctx = run_sessionstart(
        {
            "registered": ["1.46388.4.0"],
            "servicePathName": svc_path("1.46388.4.0"),
            "stagedDirs": [pkg_dir("1.46388.5.0")],
        },
        hook_repo,
    )
    msg = ctx["hookSpecificOutput"]["additionalContext"]
    probe_lines = [l for l in msg.splitlines() if l.startswith("📦")]
    assert len(probe_lines) == 1, f"应恰好多打一行，实得 {probe_lines}"
    assert "1.46388.5.0" in probe_lines[0]


def test_横幅在ok时不多打行且既有各行仍在(hook_repo: Path):
    ctx = run_sessionstart(
        {
            "registered": ["1.46388.4.0"],
            "servicePathName": svc_path("1.46388.4.0"),
            "stagedDirs": [pkg_dir("1.46388.4.0")],
        },
        hook_repo,
    )
    msg = ctx["hookSpecificOutput"]["additionalContext"]
    assert not [l for l in msg.splitlines() if l.startswith("📦")]
    # 🔴 回归：只加这一行，既有四段一段都不许丢。
    assert "🕐" in msg
    assert "↕" in msg
    assert "📋" in msg
    assert "#486" in msg


def test_探针不可用时横幅仍出且钩子不崩(hook_repo: Path):
    ctx = run_sessionstart(
        {
            "registered": None,
            "servicePathName": svc_path("1.46388.4.0"),
            "stagedDirs": [pkg_dir("1.46388.4.0")],
        },
        hook_repo,
    )
    msg = ctx["hookSpecificOutput"]["additionalContext"]
    probe_lines = [l for l in msg.splitlines() if l.startswith("📦")]
    assert len(probe_lines) == 1
    assert "读不到" in probe_lines[0]
    assert "🕐" in msg


def test_环境变量可关掉探针(hook_repo: Path):
    env = dict(os.environ)
    env["ZHUOPIN_SENTINEL_REPO_ROOT"] = str(hook_repo)
    env["ZHUOPIN_SKIP_CLAUDE_PROBE"] = "1"
    env["ZHUOPIN_CLAUDE_PROBE_FAKE"] = json.dumps(
        {
            "registered": ["1.46388.4.0"],
            "servicePathName": svc_path("1.46388.4.0"),
            "stagedDirs": [pkg_dir("1.46388.5.0")],
        }
    )
    proc = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(SESSIONSTART)],
        input=json.dumps({"session_id": "t-486"}).encode("utf-8"),
        capture_output=True,
        env=env,
        cwd=str(hook_repo),
    )
    assert proc.returncode == 0
    msg = json.loads(proc.stdout.decode("utf-8", errors="replace").strip())[
        "hookSpecificOutput"
    ]["additionalContext"]
    assert not [l for l in msg.splitlines() if l.startswith("📦")]
