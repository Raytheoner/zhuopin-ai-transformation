# -*- coding: utf-8 -*-
"""
写入时刻哨兵（H3 乱码 ／ H4 代词 ／ 公共框架）端到端单测。

🔴 为什么是端到端而不是纯函数单测：哨兵的契约是「stdin 收 hook JSON → 退出码 ＋ stderr」，
   这三样任何一样对不上，哨兵在生产里就是不生效的。逐个函数测过、契约却对不上，
   正是 OP-0819-F「建成 9 天从没响过」那类事故的成因形态。故本文件一律真跑脚本、
   真喂 JSON、真断言退出码。

对应 openspec 变更包 project-hooks-write-time-sentinels 的三份 delta spec。
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
H3 = HOOKS_DIR / "sentinel-mojibake.ps1"
H4 = HOOKS_DIR / "sentinel-pronoun.ps1"
REPO_ROOT = Path(__file__).resolve().parents[1]
ROSTER_REL = "6-人才与组织/人员名录-称谓与性别-正本.md"

FFFD = "\ufffd"
BEL = "\u0007"

pytestmark = pytest.mark.skipif(
    shutil.which("pwsh") is None, reason="需要 PowerShell 7（pwsh）"
)


# ─────────────────────────────────────────────────────────────────────────────
# 驱动
# ─────────────────────────────────────────────────────────────────────────────

def run_sentinel(script: Path, payload: dict, repo_root: Path, mode: str = "block"):
    """真跑一次哨兵：喂 stdin JSON，返回 (returncode, stderr 文本)。"""
    write_mode(repo_root, mode)
    env = dict(os.environ)
    env["ZHUOPIN_SENTINEL_REPO_ROOT"] = str(repo_root)
    proc = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(script)],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        capture_output=True,
        env=env,
        cwd=str(repo_root),
    )
    err = proc.stderr.decode("utf-8", errors="replace")
    return proc.returncode, err


def write_mode(repo_root: Path, mode: str) -> None:
    d = repo_root / "0-学习与工具" / "hooks"
    d.mkdir(parents=True, exist_ok=True)
    (d / "sentinels-mode.json").write_text(
        json.dumps({"mode": mode}, ensure_ascii=False), encoding="utf-8"
    )


def heartbeat(repo_root: Path) -> dict:
    p = repo_root / "reports" / "hooks-heartbeat.json"
    return json.loads(p.read_text(encoding="utf-8"))


def write_payload(target: Path, content: str, tool: str = "Write") -> dict:
    """构造一次 Write 的 hook JSON，并把内容真的落盘（PostToolUse 在写入之后触发）。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {
        "session_id": "test-session",
        "cwd": str(target.parent),
        "hook_event_name": "PostToolUse",
        "tool_name": tool,
        "tool_input": {"file_path": str(target), "content": content},
    }


def edit_payload(target: Path, whole: str, new_string: str) -> dict:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(whole, encoding="utf-8")
    return {
        "session_id": "test-session",
        "cwd": str(target.parent),
        "hook_event_name": "PostToolUse",
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(target),
            "old_string": "__old__",
            "new_string": new_string,
        },
    }


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """一个最小仓库夹具：带 reports/ 与真实名录正本副本。"""
    (tmp_path / "reports").mkdir()
    roster_src = REPO_ROOT / ROSTER_REL
    dst = tmp_path / ROSTER_REL
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(roster_src, dst)
    write_mode(tmp_path, "block")
    return tmp_path


def letter(repo: Path, name: str = "财务部-测试-跟进-2026-08-29-单测.md") -> Path:
    return repo / "6-人才与组织" / "部门AI专员跟进" / name


# ─────────────────────────────────────────────────────────────────────────────
# 公共框架 · Requirement「只对解析出的写入目标与本次新增内容判定」
# ─────────────────────────────────────────────────────────────────────────────

def test_脚本三件齐备():
    for p in (COMMON, H3, H4):
        assert p.is_file(), f"缺文件：{p}"


def test_正文提到受保护路径不被误判(repo: Path):
    """tasks 1.9 反例：本班亲身踩中——把「谈论某事」误判成「做某事」。"""
    target = repo / "1-转型规划" / "0-全景路线图" / "某报告.md"
    content = "# 报告\n\n本节引用了全局守卫脚本 `~/.claude/hooks/audit-log.ps1` 的写法。\n"
    rc, err = run_sentinel(H3, write_payload(target, content), repo)
    assert rc == 0, err
    assert heartbeat(repo)["verdict"] == "pass"


def test_只判新增内容不为既有内容负责(repo: Path):
    target = repo / "docs" / "既有.md"
    whole = f"第一行含旧坏字节 供{FFFD}商\n第二行是本次改的干净内容\n"
    rc, err = run_sentinel(H3, edit_payload(target, whole, "第二行是本次改的干净内容"), repo)
    assert rc == 0, err
    assert heartbeat(repo)["verdict"] == "pass"


def test_解析不出目标时放行且记为无法判定(repo: Path):
    payload = {"session_id": "s", "tool_name": "Bash", "tool_input": {"command": "echo hi"}}
    rc, err = run_sentinel(H3, payload, repo)
    assert rc == 0, err
    hb = heartbeat(repo)
    assert hb["verdict"] == "undetermined"
    assert "无法判定" in hb["note"]


def test_命令串里的坏字节不被当成写入内容(repo: Path):
    """MUST NOT 对 command 字段做正则——命令串里有坏字节也不是一次写入。"""
    payload = {
        "session_id": "s",
        "tool_name": "Bash",
        "tool_input": {"command": f"echo 供{FFFD}商"},
    }
    rc, _ = run_sentinel(H3, payload, repo)
    assert rc == 0
    assert heartbeat(repo)["verdict"] == "undetermined"


# ─────────────────────────────────────────────────────────────────────────────
# 公共框架 · Requirement「fail-open 且不静默失败」／「自证在岗」
# ─────────────────────────────────────────────────────────────────────────────

def test_坏JSON时放行且异常进心跳(repo: Path):
    """tasks 1.10 反例：脚本抛异常必须放行，且心跳仍落盘。"""
    write_mode(repo, "block")
    env = dict(os.environ)
    env["ZHUOPIN_SENTINEL_REPO_ROOT"] = str(repo)
    proc = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(H3)],
        input=b"{ this is not json ",
        capture_output=True,
        env=env,
        cwd=str(repo),
    )
    assert proc.returncode == 0
    hb = heartbeat(repo)
    assert hb["verdict"] == "error"
    assert hb["error"], "异常放行必须留下异常摘要——放行可以，静默不行"


def test_放行也落心跳且标注时区基准(repo: Path):
    target = repo / "docs" / "干净.md"
    rc, _ = run_sentinel(H3, write_payload(target, "一切正常\n"), repo)
    assert rc == 0
    hb = heartbeat(repo)
    assert hb["verdict"] == "pass"
    assert hb["lastRun"]
    assert "UTC" in hb["lastRunBasis"], "时刻必须显式标基准"
    assert hb["runs"]["total"] >= 1


def test_心跳是单一定名文件不分片(repo: Path):
    target = repo / "docs" / "a.md"
    for i in range(3):
        run_sentinel(H3, write_payload(target, f"第 {i} 次\n"), repo)
    files = list((repo / "reports").glob("hooks-heartbeat*"))
    assert [f.name for f in files] == ["hooks-heartbeat.json"]
    assert heartbeat(repo)["runs"]["total"] == 3


def test_坏心跳时检查本身出声不静默(repo: Path):
    """tasks 5.3 反例：心跳文件是坏 JSON 时，不得静默吞掉。"""
    (repo / "reports" / "hooks-heartbeat.json").write_text("{ 坏 json", encoding="utf-8")
    target = repo / "docs" / "b.md"
    rc, _ = run_sentinel(H3, write_payload(target, "正常内容\n"), repo)
    assert rc == 0
    hb = heartbeat(repo)
    assert "无法解析" in hb["note"], "上一份心跳坏掉这件事必须现身，不能静默重置"


def test_warn模式命中不打断_block模式才拦(repo: Path):
    target = repo / "docs" / "c.md"
    payload = write_payload(target, f"供{FFFD}商风险\n")
    rc_warn, err_warn = run_sentinel(H3, payload, repo, mode="warn")
    assert rc_warn == 0
    assert heartbeat(repo)["verdict"] == "violation"
    assert heartbeat(repo)["mode"] == "warn"
    rc_block, _ = run_sentinel(H3, payload, repo, mode="block")
    assert rc_block == 2


# ─────────────────────────────────────────────────────────────────────────────
# H3 · 乱码哨兵
# ─────────────────────────────────────────────────────────────────────────────

def test_H3_内容含替换字符即拦并给出行号偏移码点(repo: Path):
    target = repo / "docs" / "d.md"
    content = f"第一行正常\n供{FFFD}商风险初筛\n"
    rc, err = run_sentinel(H3, write_payload(target, content), repo)
    assert rc == 2
    assert "U+FFFD" in err
    assert "第 2 行" in err
    assert "行内第" in err


def test_H3_路径含替换字符即拦(repo: Path):
    """2026-07-04 事故形态：路径与内容同现。"""
    target = repo / "docs" / f"供{FFFD}商.md"
    payload = {
        "session_id": "s",
        "cwd": str(repo),
        "tool_name": "Write",
        "tool_input": {"file_path": str(target), "content": "正常内容\n"},
    }
    rc, err = run_sentinel(H3, payload, repo)
    assert rc == 2
    assert "写入目标路径" in err
    assert "U+FFFD" in err


def test_H3_BEL控制字符即拦(repo: Path):
    """2026-08-19 事故形态：D:\\airead 被写成含 BEL。"""
    target = repo / "docs" / "e.md"
    content = f"路径是 D:\\a{BEL}read 目录\n"
    rc, err = run_sentinel(H3, write_payload(target, content), repo)
    assert rc == 2
    assert "U+0007" in err


def test_H3_制表符与换行不误伤(repo: Path):
    target = repo / "docs" / "f.md"
    content = "| 列一\t列二 |\n| --- |\n| 值\t值 |\n"
    rc, err = run_sentinel(H3, write_payload(target, content), repo)
    assert rc == 0, err


def test_H3_二进制目标放行(repo: Path):
    for ext in (".docx", ".png"):
        target = repo / "docs" / f"g{ext}"
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "session_id": "s",
            "cwd": str(repo),
            "tool_name": "Write",
            "tool_input": {"file_path": str(target), "content": f"供{FFFD}商"},
        }
        rc, err = run_sentinel(H3, payload, repo)
        assert rc == 0, f"{ext}: {err}"


def test_H3_代码块内放行而正文内拦截_同一坏字节对照(repo: Path):
    """spec 明列的那对对照：同一个坏字节，位置不同结论必须不同。"""
    fenced = repo / "docs" / "复盘A.md"
    body = "# 复盘\n\n当时写出来是这样：\n\n```\n供" + FFFD + "商\n```\n\n以上。\n"
    rc, err = run_sentinel(H3, write_payload(fenced, body), repo)
    assert rc == 0, err

    plain = repo / "docs" / "复盘B.md"
    body2 = "# 复盘\n\n当时写出来是 供" + FFFD + "商 这样。\n"
    rc2, _ = run_sentinel(H3, write_payload(plain, body2), repo)
    assert rc2 == 2


def test_H3_块引用内放行(repo: Path):
    target = repo / "docs" / "复盘C.md"
    body = "# 复盘\n\n> 原文：供" + FFFD + "商\n"
    rc, err = run_sentinel(H3, write_payload(target, body), repo)
    assert rc == 0, err


def test_H3_豁免带理由生效_只写标记不生效(repo: Path):
    ok = repo / "docs" / "豁免A.md"
    body = "供" + FFFD + "商　乱码豁免：本行原样引用 2026-07-04 事故字节\n"
    rc, err = run_sentinel(H3, write_payload(ok, body), repo)
    assert rc == 0, err

    bad = repo / "docs" / "豁免B.md"
    body2 = "供" + FFFD + "商　乱码豁免：\n"
    rc2, _ = run_sentinel(H3, write_payload(bad, body2), repo)
    assert rc2 == 2, "只有标记、没有理由的豁免不得生效"


def test_H3_拦截进既有audit日志形态(repo: Path, tmp_path: Path):
    """拦截 MUST 进 ~/.claude/audit-blocks-<date>.log，且 MUST NOT 新造日志形态。"""
    fake_home = tmp_path / "fakehome"
    (fake_home / ".claude").mkdir(parents=True)
    env = dict(os.environ)
    env["ZHUOPIN_SENTINEL_REPO_ROOT"] = str(repo)
    env["USERPROFILE"] = str(fake_home)
    write_mode(repo, "block")
    target = repo / "docs" / "h.md"
    payload = write_payload(target, f"供{FFFD}商\n")
    proc = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(H3)],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        capture_output=True, env=env, cwd=str(repo),
    )
    assert proc.returncode == 2
    logs = list((fake_home / ".claude").glob("audit-blocks-*.log"))
    assert len(logs) == 1, "不得新造日志文件形态"
    line = logs[0].read_text(encoding="utf-8").strip().splitlines()[-1]
    cols = line.split("\t")
    assert len(cols) == 6, "须复用既有六列 TSV 形态"
    assert cols[1] == "block"
    assert "H3" in cols[5]


# ─────────────────────────────────────────────────────────────────────────────
# H4 · 代词哨兵
# ─────────────────────────────────────────────────────────────────────────────

GOLDEN = ["祖怡", "燕萍", "映桦", "植雅", "易水", "姣龙", "国庆"]


def _wrong_pronoun_for(alias: str, repo: Path) -> str:
    """从名录里读该别名的性别，写一个反的代词——测试夹具同样不硬编码性别。"""
    text = (repo / ROSTER_REL).read_text(encoding="utf-8")
    import re

    for m in re.finditer(r"([一-龥]{2,4})（(男|女)", text):
        if m.group(1).endswith(alias):
            return "她" if m.group(2) == "男" else "他"
    raise AssertionError(f"名录里找不到 {alias}")


def test_H4_名录内人物代词写反即拦(repo: Path):
    tgt = letter(repo)
    body = "# 跟进信\n\n李姣龙已在昨天完成判例批改，他确认三条口径无异议。\n"
    rc, err = run_sentinel(H4, write_payload(tgt, body), repo)
    assert rc == 2
    assert "李姣龙" in err
    assert "第 3 行" in err
    assert "「他」" in err and "「她」" in err


def test_H4_代词正确则放行(repo: Path):
    tgt = letter(repo)
    body = "# 跟进信\n\n唐燕萍已签认财务口径，她要求下周补一份对照表。\n"
    rc, err = run_sentinel(H4, write_payload(tgt, body), repo)
    assert rc == 0, err


def test_H4_七个高危名字全覆盖(repo: Path):
    for alias in GOLDEN:
        wrong = _wrong_pronoun_for(alias, repo)
        tgt = letter(repo, f"采购部-{alias}-跟进-2026-08-29-单测.md")
        body = f"# 跟进信\n\n{alias}已收到判例包，{wrong}会在本周五前回件。\n"
        rc, err = run_sentinel(H4, write_payload(tgt, body), repo)
        assert rc == 2, f"{alias} 写成「{wrong}」未被判违规：{err}"
        assert alias in err


def test_H4_一段两个不同性别人名则放行(repo: Path):
    tgt = letter(repo)
    body = "# 跟进信\n\n姚祖怡与陈忱已一起过完判例包，他会把结论汇总给我。\n"
    rc, err = run_sentinel(H4, write_payload(tgt, body), repo)
    assert rc == 0, err


def test_H4_名录外人物不触发(repo: Path):
    tgt = letter(repo)
    body = "# 跟进信\n\n客户对接人罗铁柱表示，他下周才有空评审。\n"
    rc, err = run_sentinel(H4, write_payload(tgt, body), repo)
    assert rc == 0, err


def test_H4_块引用内旧信原文放行_同句正文内拦截(repo: Path):
    quoted = letter(repo, "财务部-引用-跟进-2026-08-29-单测.md")
    body = "# 跟进信\n\n> 上一封原文：李姣龙已确认，他无异议。\n"
    rc, err = run_sentinel(H4, write_payload(quoted, body), repo)
    assert rc == 0, err

    plain = letter(repo, "财务部-正文-跟进-2026-08-29-单测.md")
    body2 = "# 跟进信\n\n李姣龙已确认，他无异议。\n"
    rc2, _ = run_sentinel(H4, write_payload(plain, body2), repo)
    assert rc2 == 2


def test_H4_引号里的代词是词例引用不判违规(repo: Path):
    """🔴 真实语料回归：2026-08-29 本班拿一封历史跟进信真跑时抓到的误报。

    原句是 `代词自检: … 全部写作「她」；「他」0 处` —— 那个「他」不是在指代谁，
    是在**谈论这个字**，而且这句话恰恰是**做对了自检**的那句。design 已预判此形态：
    「写称谓纪律时会举反例，H4 若不认上下文，规则文档自己就违规」。
    """
    tgt = letter(repo, "财务部-词例-跟进-2026-08-29-单测.md")
    body = (
        "# 跟进信\n\n"
        "代词自检：全文第三人称仅指李姣龙，为女性，全部写作「她」；「他」0 处。\n"
    )
    rc, err = run_sentinel(H4, write_payload(tgt, body), repo)
    assert rc == 0, err


def test_H4_定位得到绝对行号(repo: Path):
    """换行符风格不一致时也必须给出文件绝对行号，不许静默退化成相对行号。"""
    tgt = letter(repo, "财务部-行号-跟进-2026-08-29-单测.md")
    body = "# 跟进信\n\n第二段占位。\n\n李姣龙已确认，他无异议。\n"
    payload = write_payload(tgt, body)
    # 磁盘上是 CRLF、入参是 LF。🔴 必须 write_bytes：Windows 上 write_text 会把 "\n" 再翻成
    # "\r\n"，于是 "\r\n" 变成 "\r\r\n"——本班第一版就是这么写的，测出来的「定位不到」
    # 其实是夹具自己造的假象，不是被测代码的问题。
    tgt.write_bytes(body.replace("\n", "\r\n").encode("utf-8"))
    rc, err = run_sentinel(H4, payload, repo)
    assert rc == 2
    assert "第 5 行" in err, f"未给出绝对行号：{err}"
    assert "未能在文件中唯一定位" not in err


def test_H4_豁免带理由生效(repo: Path):
    tgt = letter(repo, "财务部-豁免-跟进-2026-08-29-单测.md")
    body = "# 跟进信\n\n李姣龙已确认，他无异议。　代词豁免：本行原样引用 财务部#14 原文，历史记录不追改\n"
    rc, err = run_sentinel(H4, write_payload(tgt, body), repo)
    assert rc == 0, err


def test_H4_名录缺失时明说无法核验且不给结论(repo: Path):
    # 🔴 函数名刻意不含被断言的那个禁词——pytest 的 tmp_path 会把函数名拼进目录路径，
    #    而路径本身会出现在哨兵输出里，写进函数名就会把断言变成恒假（本班实测踩中一次）。
    (repo / ROSTER_REL).unlink()
    tgt = letter(repo)
    body = "# 跟进信\n\n李姣龙已确认，他无异议。\n"
    rc, err = run_sentinel(H4, write_payload(tgt, body), repo)
    assert rc == 0
    assert "本类无法核验" in err
    assert "未发现违规" not in err
    assert heartbeat(repo)["verdict"] == "unverifiable"


def test_H4_名录解析出0人时同样无法核验(repo: Path):
    (repo / ROSTER_REL).write_text("# 空名录\n\n这里一个人物条目也没有。\n", encoding="utf-8")
    tgt = letter(repo)
    rc, err = run_sentinel(H4, write_payload(tgt, "# 跟进信\n\n李姣龙已确认，他无异议。\n"), repo)
    assert rc == 0
    assert "本类无法核验" in err
    assert "未发现违规" not in err


def test_H4_非跟进信目标不判(repo: Path):
    tgt = repo / "1-转型规划" / "某规划.md"
    body = "# 规划\n\n李姣龙已确认，他无异议。\n"
    rc, err = run_sentinel(H4, write_payload(tgt, body), repo)
    assert rc == 0, err


# ─────────────────────────────────────────────────────────────────────────────
# 落库 sweep 第 9 类常驻告警 · 哨兵零心跳（tasks §5）
# ─────────────────────────────────────────────────────────────────────────────

import importlib.util  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402

_SWEEP_SPEC = importlib.util.spec_from_file_location(
    "commit_sweep_for_hooks", Path(__file__).resolve().parent / "工具-落库sweep.py"
)
sweep = importlib.util.module_from_spec(_SWEEP_SPEC)
_SWEEP_SPEC.loader.exec_module(sweep)


def _register_sentinels(repo: Path) -> None:
    """在夹具仓库里伪造一次「安装单已执行」——注册标记就是脚本相对路径片段。"""
    d = repo / ".claude"
    d.mkdir(parents=True, exist_ok=True)
    (d / "settings.json").write_text(
        json.dumps(
            {"hooks": {"PostToolUse": [{"matcher": "Edit|Write", "hooks": [
                {"type": "command",
                 "command": 'pwsh -NoProfile -File "0-学习与工具/hooks/sentinel-mojibake.ps1"',
                 "timeout": 10}]}]}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _set_heartbeat(repo: Path, age_days: float) -> None:
    stamp = (datetime.now().astimezone() - timedelta(days=age_days))
    (repo / "reports").mkdir(exist_ok=True)
    (repo / "reports" / "hooks-heartbeat.json").write_text(
        json.dumps({"lastRun": stamp.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + stamp.strftime("%z")[:3] + ":" + stamp.strftime("%z")[3:],
                    "runs": {"total": 7}}, ensure_ascii=False),
        encoding="utf-8",
    )


def test_sweep_未注册时按设计不告警(repo: Path):
    """🔴 安装单执行之前不得每天红一次——永远红着的告警等于没有告警。"""
    log: list[str] = []
    sweep._check_hooks_heartbeat(repo, log)
    text = "\n".join(log)
    assert "按设计不告警" in text
    assert "可能已不在岗" not in text


def test_sweep_心跳新鲜时每轮回显在岗(repo: Path):
    _register_sentinels(repo)
    _set_heartbeat(repo, age_days=0.2)
    log: list[str] = []
    sweep._check_hooks_heartbeat(repo, log)
    text = "\n".join(log)
    assert "哨兵在岗" in text
    assert "非 UTC" in text, "时刻必须显式标基准"


def test_sweep_零心跳即告警(repo: Path):
    _register_sentinels(repo)
    _set_heartbeat(repo, age_days=sweep.HOOKS_HEARTBEAT_STALE_DAYS + 2)
    log: list[str] = []
    sweep._check_hooks_heartbeat(repo, log)
    state = json.loads((repo / sweep.HOOKS_HEARTBEAT_STATE_REL).read_text(encoding="utf-8"))
    assert "零心跳" in state


def test_sweep_心跳文件不存在即告警(repo: Path):
    _register_sentinels(repo)
    log: list[str] = []
    sweep._check_hooks_heartbeat(repo, log)
    state = json.loads((repo / sweep.HOOKS_HEARTBEAT_STATE_REL).read_text(encoding="utf-8"))
    assert "心跳文件不存在" in state


def test_sweep_坏心跳时检查本身出声(repo: Path):
    """tasks 5.3：心跳文件是坏 JSON 时，检查必须出声——判据坏了 ≠ 没有违规。"""
    _register_sentinels(repo)
    (repo / "reports" / "hooks-heartbeat.json").write_text("{ 这不是 json", encoding="utf-8")
    log: list[str] = []
    sweep._check_hooks_heartbeat(repo, log)
    state = json.loads((repo / sweep.HOOKS_HEARTBEAT_STATE_REL).read_text(encoding="utf-8"))
    assert "心跳文件损坏" in state


def test_sweep_心跳恢复后告警自动解除(repo: Path):
    """🔴 告警必须能被「已恢复」关掉，否则又造出一个永远红着的告警。"""
    _register_sentinels(repo)
    log: list[str] = []
    sweep._check_hooks_heartbeat(repo, log)                     # 无心跳 ⇒ 告警
    state = json.loads((repo / sweep.HOOKS_HEARTBEAT_STATE_REL).read_text(encoding="utf-8"))
    assert state, "第一轮应当留下告警状态"

    _set_heartbeat(repo, age_days=0.1)                          # 心跳恢复
    log2: list[str] = []
    sweep._check_hooks_heartbeat(repo, log2)
    state2 = json.loads((repo / sweep.HOOKS_HEARTBEAT_STATE_REL).read_text(encoding="utf-8"))
    assert state2 == {}, "恢复后必须自动解除，无需人工清除"
    assert "解除" in "\n".join(log2)


def test_H4_脚本内零硬编码人名与性别():
    """spec：H4 MUST NOT 在脚本内硬编码任何人名或性别——硬编码即等于造出第二份名录。"""
    src = H4.read_text(encoding="utf-8")
    for alias in GOLDEN + ["李姣龙", "唐燕萍", "姚祖怡", "陈忱", "孙涛"]:
        assert alias not in src, f"脚本里出现了具体人名：{alias}"
