"""队列 #355 防回归：PowerShell 脚本里不得出现「孤立 CR」，wrapper 模板不得用双引号 here-string。

事故原文（2026-08-19 OP-0819-D 撞出，2026-08-24 修）：
    `register-decision-reminder-task.ps1` 用**双引号** here-string（``@" … "@``）
    拼 wrapper 正文。双引号 here-string 会做转义与插值，模板注释里的
    ``` `resolve_repo_root` ```（反引号包裹的标识符）中，「反引号 + r」被当成 CR
    转义序列 ⇒ 生成物第 933 字节处写出一个**孤立 CR**（0x0D 未跟 0x0A）。
    PowerShell 把孤立 CR 当断行，注释就地截断，后半截
    「esolve_repo_root 会以这个路径为」被当命令执行，每日 08:30 必报
    CommandNotFoundException。

🔑 为什么必须由测试守，而不是靠人记得：
    这个缺陷**不产生任何失败信号**——stdout 正常、exit code 0、状态文件正确，
    只有 stderr 多一条没人看的异常，藏了 8 天。生成物本身是 gitignore 件，
    没人会去读它。所以唯一能拦住复发的位置是「入库的生成器源码」。
    同族＝根 CLAUDE.md「工具静默回退」：**不报错，只是悄悄换掉了一个字节**。

本文件只做静态扫描，不起 PowerShell 子进程（保持测试可移植、不依赖宿主 shell）。
生成期的运行时防线是 `assert-no-orphan-cr.ps1`，两者互补：
    - 这里守「源码里不许再出现那个范式」
    - 那里守「万一还是生成出来了，写盘前后 fail-loud 中止」
"""
import re
from pathlib import Path

import pytest

SERVICE_ROOT = Path(__file__).resolve().parent.parent

# 生成 wrapper 的两份注册脚本——本组约束只针对它们（其余 .ps1 不产生被
# 定时任务直接执行的生成物，不强加同一范式）。
GENERATOR_SCRIPTS = (
    "register-decision-reminder-task.ps1",
    "register-followup-dispatch-task.ps1",
)

# 生成期运行时防线，两份生成器共用一份（不各自复制——复述即漂移）。
CR_ASSERTER = "assert-no-orphan-cr.ps1"


def _orphan_cr_offsets(data: bytes) -> list[int]:
    """返回所有「0x0D 未跟 0x0A」的字节偏移。CRLF 与裸 LF 都不算。"""
    return [
        i
        for i, byte in enumerate(data)
        if byte == 0x0D and (i + 1 >= len(data) or data[i + 1] != 0x0A)
    ]


def _service_ps1_files() -> list[Path]:
    # 只扫本服务目录自身的 .ps1，不递归进 worktree/生成物目录。
    return sorted(SERVICE_ROOT.glob("*.ps1"))


def test_service_ps1_files_discovered():
    """自检：扫描集合非空。

    否则下面三条 parametrize 会**零用例通过**——「判据恒真、零信息量」正是
    根 CLAUDE.md 点名的同族陷阱：一个永远绿、却什么也没测的守卫，比没有守卫更坏。
    """
    found = _service_ps1_files()
    assert found, f"{SERVICE_ROOT} 下未发现任何 .ps1，扫描范围失效"
    names = {p.name for p in found}
    for required in (*GENERATOR_SCRIPTS, CR_ASSERTER):
        assert required in names, f"{required} 不在扫描集合内：{sorted(names)}"


@pytest.mark.parametrize("ps1_path", _service_ps1_files(), ids=lambda p: p.name)
def test_no_orphan_cr_in_committed_ps1(ps1_path: Path):
    """入库的 .ps1 源码本身不得含孤立 CR。

    源码带孤立 CR 时，双引号 here-string 会把它原样带进生成物，且
    `Get-Content` 读出来一切正常——肉眼与常规 diff 都看不出来。
    """
    offsets = _orphan_cr_offsets(ps1_path.read_bytes())
    assert not offsets, (
        f"{ps1_path.name} 含 {len(offsets)} 个孤立 CR（0x0D 未跟 0x0A），偏移 {offsets}。"
        "见队列 #355：PowerShell 会把它当断行，其后的内容会被当命令执行。"
    )


@pytest.mark.parametrize("script_name", GENERATOR_SCRIPTS)
def test_generators_use_single_quoted_herestring(script_name: str):
    """wrapper 模板必须是单引号 here-string（``@' … '@``），不得改回双引号。

    单引号 here-string 零转义零插值——模板里写什么就是什么；真实值由占位符
    `.Replace()` 显式代入。这是 #355 的根治点，不是风格偏好。
    """
    text = (SERVICE_ROOT / script_name).read_text(encoding="utf-8")

    # 🔴 判据必须精确到 here-string **开启符**，不能用 `'@"' in text` 这种裸子串：
    # 注释里描述这个反范式时就会写出 `@"` 三个字面字符，裸子串判据会把「解释
    # 缺陷的那段话」误判成「缺陷本身」——本用例初版正是这么红的。
    # PowerShell 语法要求 here-string 开启符后除空白外不得有内容，故锚到行尾。
    double_quoted_openers = re.findall(r'@"[ \t]*\r?\n', text)
    assert not double_quoted_openers, (
        f'{script_name} 出现双引号 here-string 开启符（@" 后直接换行）'
        "——队列 #355 已根治此范式，不得回退。"
        "双引号 here-string 会把注释里的「反引号 + r/n/t」当转义符，静默写出控制字符。"
    )
    assert re.search(r"@'[ \t]*\r?\n", text), (
        f"{script_name} 未找到单引号 here-string 开启符（@' 后直接换行），模板可能被改写"
    )


@pytest.mark.parametrize("script_name", GENERATOR_SCRIPTS)
def test_generators_assert_no_orphan_cr_before_and_after_write(script_name: str):
    """生成器必须 dot-source 断言器，并在写盘**前后各查一次**。

    只查写盘前不够：`Set-Content` 的编码/换行处理也可能引入差异，写后反查才
    对得上真正被定时任务执行的那份字节（同根 CLAUDE.md「写后反查」纪律）。
    """
    text = (SERVICE_ROOT / script_name).read_text(encoding="utf-8")
    assert CR_ASSERTER in text, f"{script_name} 未 dot-source {CR_ASSERTER}"

    lines = text.splitlines()
    call_lines = [i for i, ln in enumerate(lines) if ln.strip().startswith("Assert-NoOrphanCR")]
    write_lines = [i for i, ln in enumerate(lines) if ln.strip().startswith("Set-Content")]

    assert len(write_lines) == 1, f"{script_name} 预期恰有 1 处 Set-Content，实测 {len(write_lines)}"
    write_at = write_lines[0]
    assert any(i < write_at for i in call_lines), f"{script_name} 缺写盘前 Assert-NoOrphanCR"
    assert any(i > write_at for i in call_lines), f"{script_name} 缺写盘后 Assert-NoOrphanCR 反查"


def test_asserter_rejects_a_real_orphan_cr_sample():
    """反例锁死：断言器的判据本身必须能认出真实事故样本。

    样本＝#355 生产 wrapper 那一行的最小复现（`<CR>esolve_repo_root`）。
    这条用例的价值在于：若日后有人把「孤立 CR」的判据写成了别的东西
    （例如误把 CRLF 也算进去、或漏掉「文件末尾的 CR」这个边界），此处会红。
    """
    prefix = "# 显式设置后，".encode("utf-8")
    sample = prefix + b"\x0desolve_repo_root " + "会以这个路径为".encode("utf-8") + b"\r\n"
    assert _orphan_cr_offsets(sample) == [len(prefix)]

    # 边界一：纯 CRLF 文本零命中（不得把正常换行误报成孤立 CR）。
    assert _orphan_cr_offsets(b"a\r\nb\r\n") == []
    # 边界二：裸 LF 零命中（LF-only 文件 PowerShell 照常执行，不是本缺陷）。
    assert _orphan_cr_offsets(b"a\nb\n") == []
    # 边界三：文件**末尾**的 CR 必须算——它后面没有 0x0A，同样会截断。
    assert _orphan_cr_offsets(b"abc\r") == [3]
