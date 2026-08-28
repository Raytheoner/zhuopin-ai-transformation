"""跨桌任务队列.md 结构 lint（队列 #309 步骤 2③，CI 基线）。

复用 `工具-共享文档编辑锁.py` release 校验①⑤两项检查用到的底层解析
函数（`_split_live_sections`/`_table_data_rows`/`SECTION_COLUMN_COUNTS`/
`_section_two_status_is_ambiguous`）——同一份文件、同一套表格约定，不该
两处各写一套判据（同 `_table_data_rows` 自身 docstring 的既有原则）。
用 `importlib.util.spec_from_file_location` 按文件路径加载（本项目测试
文件已有的既定手法，如 `test_工具-落库sweep.py`），不走 `import 工具-...`
的包名解析——两者都不是 `pip install -e` 的可安装包，不存在多 worktree
共享 editable install 的静默劫持风险（那类风险专指 `zhuopin_platform`/
`aibot_service` 这类被装进全局 site-packages 的包，见 `工具-落库sweep.py`
文件头部"零依赖"说明）。

作用域与 release 校验的关系（互补，非重复）：release 校验只查"本次持锁
期间新增/改动的行"（session-diff-scoped，依赖 acquire 时的快照与预留
记录）；本脚本查"当前文件整体"（whole-file-scoped，无会话上下文）——
CI 治的是"不管改动经没经过编辑锁协议（如 #305 指出的机器人写队列路径
完全绕过锁），产物本身是否结构完整"，与 release 校验治的"写入那一刻
拦一次"是两个不同的防线，见队列 #309 行内 CI 步骤 2③ 说明原文
「编辑锁的 release 校验只在有人走锁时才生效…CI 不论谁写、走哪条路都拦」。

只做队列 #309 行内文字明确点名的两项：①列数（§一＝8／§二＝4／§四＝4，
天然覆盖裸竖线致列偏移的情形——`_table_data_rows` 按原样 split("|")，
不做任何"容错"，裸竖线会直接体现为列数偏差）；②§二 状态列格式（既不
含"待"也不含"✅"判为模糊）。不做 release 校验独有的另外四项（②批次
文件清单自声明／③编号预留归属／④P0-P1 未核断言／⑥跟进信暂缓一致性）
——这四项依赖 acquire 时的快照与本次持锁期间的预留记录，CI 没有这个
会话上下文，硬套会产生大量"整份历史文件都是新改动"式的假阳性，且不在
#309 行内 lint 范围文字里，不属于本次要补的那一块。

第③项（队列 #313，拍板项 10 选 (b)）：断言权威模块
`zhuopin_platform.shared_tools.queue_table` 可 import。背景——编辑锁/
台账/sweep/队列查询四处消费者各自都用
`try: from zhuopin_platform.shared_tools.queue_table import ... except
ImportError: class queue_table: ...` 兜底桩隔离测试环境（#306 apply 时
两个真实隔离测试用例逼出，桩本身不主张删），但这意味着"哪天路径变了或
包装坏了，四处会各自静默降级回本地实现、零报错"——本项断言只求把这条
本会静默的路径变成 CI 会显式报红的路径，不改桩本身。**故意不用
`pip install -e`**：`queue_table.py` 自身与其所在的 `zhuopin_platform`/
`shared_tools` 两层 `__init__.py` 均无第三方依赖（纯标准库），走与场景
入口脚本同款的 #300 式 sys.path 引导即可稳定 import，不必为一个零依赖
模块在 CI 里多装一次平台底座包（`queue-structure-lint` job 目前不装）。

第④项（队列 #352）：称呼判据——根 `CLAUDE.md` §1 称呼纪律「一律称
`Shao Peishen`，不用 `Paul`」此前**纯属人守**，写反了只能靠人读到。本项
把它挂到 CI 这条不可绕过的咽喉上（同根 `CLAUDE.md` §5 规则退休制的
「机制化」一支）。🔴 **必须带 baseline**：判据上线时存量非零（2026-08-24
实测 21 个活行、74 处命中），无 baseline 直接开门禁会让 CI 长期红，而一条
长期红的门禁等于没有门禁（同队列 §四 #58「非阻断提示被连续 6 次越过后
信息量为零」的另一面）。做法见下方 `_appellation_scan` 与
`APPELLATION_BASELINE_PATH` 处的完整说明。

第⑤项（队列 #426，OP-0828-P）：**编号高水位线不得低于实测最大已用号**。
治的不是「有一格没补上」，而是那一格为什么会漏——**一个不对称**：高水位线
只被 `acquire --reserve` 自动推进，手工立行与 `append-row --number` 都不会
推它。2026-08-28 那次滞后**是被另一条机制偶然掩盖掉的**（同日一条机器人
`append-row` 追行把它一路推过头，顺手补上了），于是它既没被发现也没被修，
只是暂时看不见。完整论证见下方 `high_water_mark_check` 上方注释块。

同一批还加了**运行时作用域自报**（#426 第③件，见 `print_scope_self_report`）：
每次运行先打印本次实际校验的绝对路径——本脚本的 `REPO_ROOT` 恒解到主工作区
（见下方 `#314①` 注释），在 linked worktree 里跑时它校验的**不是**调用者刚
改的那份文件，而此前它从不说这件事。

用法：
  python 0-学习与工具/工具-队列结构lint.py
  # 退出码 0=通过；1=发现违规（详情打印到 stdout）
  python 0-学习与工具/工具-队列结构lint.py --emit-baseline
  # 把当前称呼判据命中集按 baseline 格式打到 stdout（不写盘，见下方说明）
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

QUEUE_REL = "1-转型规划/0-全景路线图/跨桌任务队列.md"
EDIT_LOCK_SCRIPT = Path(__file__).resolve().with_name("工具-共享文档编辑锁.py")

_spec = importlib.util.spec_from_file_location("queue_lint_editlock_reuse", EDIT_LOCK_SCRIPT)
editlock = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(editlock)

# 队列 #315（apply）：拆分后 QUEUE_REL 转为纯指针文件，不再是权威内容
# 承载——lint 改遍历两份真实内容文件，否则本 CI 门禁会对着一份几乎空的
# 指针文件永远报"零违规"，把"未来新行必须带机器字段"这道硬门禁静默
# 失效（同 CLAUDE.md §5"工具静默回退"反模式）。两个具体路径读 `editlock`
# 已加载的局部绑定（同一惯例，供测试 monkeypatch）。
QUEUE_PATHS_REL = [editlock.QUEUE_MECHANISM_PATH_REL, editlock.QUEUE_BUSINESS_PATH_REL]

# 队列 #314①：REPO_ROOT 复用 editlock 已算好的值（`_resolve_repo_root()`，
# 经 `git rev-parse --git-common-dir` 解到"所有 worktree 共享的主工作区"），
# 不再自己按 `Path(__file__).resolve().parents[1]` 算一份worktree本地路径。
# 2026-08-09 实测坐实两者会给出不同答案：本脚本在建造用的 linked worktree
# 里跑时，旧写法算出的是"这个 worktree 自己签出的那份队列文件"（可能是
# 创建 worktree 那一刻的旧快照，此后主工作区经 editlock 协议〇.7 发生的
# 任何编辑都不会体现在这份本地副本里）；而 `工具-共享文档编辑锁.py`／
# `工具-队列查询.py` 的 `_resolve_repo_root()` 一律解到主工作区（其
# docstring 明文"所有 git worktree 共享同一把锁的关键"）——队列文件的
# 权威副本只有主工作区那一份。两者不一致意味着：在 linked worktree 里
# 直接跑 `python 工具-队列结构lint.py`（本脚本 docstring 给出的原样用法）
# 校验的是错误的文件，可能得出与 editlock release 校验完全相反的结论，
# 且不报错——同 `CLAUDE.md` §5"工具静默回退"的教科书形态。
REPO_ROOT = editlock.REPO_ROOT


# ---------------------------------------------------------------------------
# 队列 #366 / S2：队列禁止复述信状态（一期 --warn）
# ---------------------------------------------------------------------------
#
# S1（Shao Peishen 2026-08-21 答 §四 #85 选 (b)）确立：**一封信的状态，唯一
# 权威源是跟进信 README 的「发送状态」列，跨桌任务队列不是信状态的载体。**
# 队列行里写「等某某#N 闭环／待某某回件」这类**复述**，一律是会过时的快照
# ——2026-08-21 当天两次咬人（质量部#8 回灌全做完闸还锁着；采购部#17 回件
# 13:13 到、13:15 队列已追行而 README 未动）都始于有人照着这类快照下判断。
#
# 判据只认「**等/待 + 部门#N + 闭环/回件/回灌**」这个紧凑形态，前后各留
# ≤8 字的窗口。窗口是**实测标定**的，不是拍的：0 字窗口漏掉全部 5 处存量，
# 40 字窗口把 18 处正常叙述（如「#344 判例包已作为 采购部#16 发出、现等
# 回件」这类**事后陈述**）一并卷进来。8/8 恰好命中且仅命中那 5 处。
_LETTER_STATUS_RESTATE_RE = re.compile(
    r"(等|待).{0,8}?(采购部|财务部|质量部|IT部|销售部)#\d+.{0,8}?(闭环|回件|回灌)"
)
# §二 是 commit 批次行，天然是历史记录；§一 里 `[S:done]` 的行同理（「历史
# 记录不追改」是本项目硬规则）。两者都**只统计、不报违规**——但必须把数
# 打印出来，否则就成了"静默豁免"，与本判据要治的毛病同族。
FOLLOWUP_RESTATE_SCOPE_SECTIONS = ("一", "四")
FOLLOWUP_RESTATE_HINT = (
    "队列不得复述信状态（它会过时）。改为写指针："
    "「串行闸状态跑 python 0-学习与工具/工具-跟进闸查询.py --to <收信人>」"
)


def _followup_restate_scan(text: str) -> tuple[list[str], int]:
    """返回 (活行违规说明列表, 历史行命中数)。

    活行 ＝ §一 非 `[S:done]` 的行 ＋ §四 全部行；历史行 ＝ §一 `[S:done]`
    的行（§二 不在扫描范围内，见上方常量注释）。
    """
    sections = editlock._split_live_sections(text)
    live: list[str] = []
    historical = 0
    for label in FOLLOWUP_RESTATE_SCOPE_SECTIONS:
        for line, cells in editlock._table_data_rows(sections.get(label, "")):
            match = _LETTER_STATUS_RESTATE_RE.search(line)
            if not match:
                continue
            if label == "一" and len(cells) > 5:
                status_value, _, _ = editlock._parse_status_domain_fields(cells[5])
                if status_value == "done":
                    historical += 1
                    continue
            row_id = cells[0] if cells else "?"
            live.append(
                f"§{label} #{row_id} 复述了信状态「{match.group(0)}」——{FOLLOWUP_RESTATE_HINT}"
            )
    return live, historical


# ---------------------------------------------------------------------------
# 队列 #352：称呼判据（`Paul` → `Shao Peishen`），带 baseline
# ---------------------------------------------------------------------------
#
# 根 `CLAUDE.md` §1：「一律称 `Shao Peishen`，不用 `Paul`」。成因是 `Paul`
# 同时是 Windows 账户名、英文名与决策人代称，三重含义混用已多次致错。
#
# 🔴 **三条豁免，每一条都必须计数并打印，不得静默**——「静默豁免」正是本
# 判据所属的这一族毛病本身（同 `_followup_restate_scan` 的既有原则）：
#
#   ⑴ **路径／账户名 `Paul Shao` 恒不算违规**。根 `CLAUDE.md` §1 明写
#      「🔴 绝不替换路径里的 `Paul Shao`（改了路径即失效）」——本机用户
#      目录就是 `C:\\Users\\Paul Shao\\`，计划任务的运行身份字面量也是
#      `Paul Shao / S4U`。判据用**紧跟其后的 ` Shao`** 做否定前瞻，不去
#      猜「这个位置像不像路径」。 ⚠️ **已知假阴性，如实登记**：真有人写
#      「Paul Shao 拍板」时本判据不会报。这是**刻意选的方向**——本判据的
#      代价不对称：漏报只是少拦一次，误报会把「绝不可改」的路径推给下一
#      个人去改。2026-08-24 实测两份队列共 7 处 `Paul Shao`，全部落在路径
#      或账户名里，无一是称呼用法。
#
#   ⑵ **§一 `[S:done]` 行恒不算违规**。根 `CLAUDE.md` §1：「历史记录不
#      追改——队列已完成行/归档件/进度编年/既往报告与 openspec design 里
#      的 `Paul` 指同一人，保持原样」。
#
#   ⑶ **行内写了 `称呼豁免：〈理由〉` 的行不算违规**。逃生阀，范式直接沿用
#      队列 §四 #58 已验证过的 `WIP豁免：`：🔴 **理由的唯一真源是行内标记，
#      不是命令行开关**——命令行参数是会话级的、随窗口关闭即消失，而这条
#      逃生阀要治的恰恰是「越过之后没人知道为什么」；写在行里则进 git、被
#      本 lint 与值周巡检都看得见、可 grep 计数。真实用例＝**队列 #352 行
#      自己**：一条定义称呼判据的队列行必须引用它要拦的那个字面量，否则
#      根本说不清自己在拦什么（同 #355「防回归判据的初版命中了我写在注释
#      里解释这个反范式的那段话」，是同一个自指问题的第二次出现）。
#
# ⚠️ **扫描面只有 §一／§二／§四 的表格数据行，如实登记**：队列顶部的
# 「协议〇」正文、各区标题与说明段都不在 `_table_data_rows` 的返回里，因此
# 本判据管不到它们。这与本文件既有的列数／§二状态列／信状态复述三项判据
# 是同一个扫描面——不为称呼判据单开一套解析，那会变成第二份关于「队列长
# 什么样」的判据（同 `_table_data_rows` 自身 docstring 的既有原则）。
#
# **baseline 的判据是「计数棘轮」，不是「快照比对」**——每个行键记一个数，
# 当前命中数 > baseline 数才算违规。刻意不记命中片段的哈希：那样一来，在
# 一条已 baseline 的行里改动**离 `Paul` 很远的**正文也会让指纹失配、报出
# 一个纯属噪音的违规，而修它最省事的办法就是重刷 baseline ⇒ 门禁自废。
# ⚠️ **棘轮的已知盲区，如实登记**：同一行内「删掉一处 `Paul`、又新写一处」
# 净变化为 0，不会被拦。接受它——那一行本就在 baseline 里、本就是历史行。
#
# 🔴 **刻意不提供 `--update-baseline` 式的一键重刷**。`--emit-baseline` 只
# 把 JSON 打到 stdout，要落盘必须自己重定向、自己 commit、自己在 PR 里被
# 人看见。一个能一键抹平的门禁，在第一次挡住人的那天就会被抹平。
APPELLATION_BASELINE_PATH = Path(__file__).resolve().with_name("队列称呼判据-baseline.json")
# 大小写敏感是判据的一部分：`PAUL_USERID`（企微 userid 常量）、`cc_to_paul`
# （函数参数名）都是代码标识符、不是称呼，不该被本判据碰。
_APPELLATION_RE = re.compile(r"(?<![A-Za-z])Paul(?![A-Za-z])(?![ \t]+Shao)")
APPELLATION_EXEMPT_MARK = "称呼豁免："
APPELLATION_SCOPE_SECTIONS = ("一", "二", "四")
APPELLATION_HINT = (
    "根 CLAUDE.md §1 称呼纪律：一律称 `Shao Peishen`，不用 `Paul`。"
    f"确有必要保留字面量时，在本行内写 `{APPELLATION_EXEMPT_MARK}〈理由〉`"
    "（理由进 git、可 grep、可被值周巡检看见）"
)


def _appellation_row_key(label: str, cells: list[str]) -> str:
    """行键跨两份队列文件全局唯一，**刻意不含文件名**。

    §一／§四 的编号由协议〇「编号高水位线」跨两份文件统一发号，故
    `一#352` 在两份文件里只可能存在一处。不含文件名是为了让 #315 式
    「行从一份队列挪到另一份」不产生假违规——挪走的那一侧会少一个键、
    挪到的那一侧会多一个键，若键里带文件名，一次纯搬家就会同时报出
    「baseline 漂移」和「新增违规」两条，而实际上一个字都没改。
    """
    return f"{label}#{cells[0].strip() if cells else '?'}"


def _appellation_scan(text: str) -> dict[str, dict]:
    """扫一份队列文件，返回 {行键: {...}}。

    每条记录含：`count`（违规命中数）、`snippets`（命中片段，供人眼定位）、
    `exempt`（豁免原因，`None` 表示不豁免）。豁免行 `count` 照常统计——
    **必须能被数出来**，否则逃生阀被批量使用时没人看得见。
    """
    sections = editlock._split_live_sections(text)
    found: dict[str, dict] = {}
    for label in APPELLATION_SCOPE_SECTIONS:
        for line, cells in editlock._table_data_rows(sections.get(label, "")):
            matches = list(_APPELLATION_RE.finditer(line))
            if not matches:
                continue
            exempt = None
            if APPELLATION_EXEMPT_MARK in line:
                exempt = "行内标记"
            elif label == "一" and len(cells) > 5:
                status_value, _, _ = editlock._parse_status_domain_fields(cells[5])
                if status_value == "done":
                    exempt = "[S:done] 历史行"
            found[_appellation_row_key(label, cells)] = {
                "count": len(matches),
                "snippets": [
                    line[max(0, m.start() - 12):m.end() + 12].strip()
                    for m in matches[:3]
                ],
                "exempt": exempt,
            }
    return found


def load_appellation_baseline(path: Path | None = None) -> tuple[dict[str, int], str | None]:
    """读 baseline，返回 (命中数映射, 错误说明)。

    🔴 **读不到就报错，不回退成空字典**。空字典会让每一行存量都变成违规
    ——那当然也是红的，但红的原因会被读成「队列里突然多了 74 处称呼违规」，
    而真相是「baseline 文件没找着」。同根 `CLAUDE.md` §5「工具静默回退」：
    要让失败长得像失败。
    """
    target = path or APPELLATION_BASELINE_PATH
    if not target.exists():
        return {}, (
            f"称呼判据 baseline 文件不存在：{target}"
            "（本判据以 baseline 冻结存量、只拦新增，缺它则无法区分历史与新增，"
            "见队列 #352）"
        )
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        raw = data["命中"]
        return {str(k): int(v) for k, v in raw.items()}, None
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        return {}, f"称呼判据 baseline 文件无法解析：{target}（{exc!r}）"


def appellation_check(
    repo_root: Path, baseline_path: Path | None = None
) -> tuple[list[str], dict]:
    """返回 (违规说明列表, 统计信息)。违规**计入** `lint()` 与退出码。

    与 `followup_restate_warnings`（#366/S2 一期只告警）的分野在于本判据
    有 baseline：存量已被冻结、当天即绿，硬拦不会拦住任何既有内容，只拦
    此后新写的。没有 baseline 才需要先走告警期。
    """
    baseline, baseline_error = load_appellation_baseline(baseline_path)
    stats = {
        "exempt_rows": [],       # [(行键, 原因, 命中数)]
        "drift": [],             # baseline 记了、如今命中数变少或归零的行键
        "live_rows": 0,
        "live_hits": 0,
    }
    if baseline_error:
        return [baseline_error], stats

    violations: list[str] = []
    seen: set[str] = set()
    for queue_path in QUEUE_PATHS_REL:
        target = repo_root / queue_path
        if not target.exists():
            continue
        for key, rec in _appellation_scan(target.read_text(encoding="utf-8")).items():
            seen.add(key)
            if rec["exempt"]:
                stats["exempt_rows"].append((key, rec["exempt"], rec["count"]))
                continue
            stats["live_rows"] += 1
            stats["live_hits"] += rec["count"]
            frozen = baseline.get(key, 0)
            if rec["count"] <= frozen:
                if rec["count"] < frozen:
                    stats["drift"].append(f"{key}（baseline {frozen} → 现 {rec['count']}）")
                continue
            violations.append(
                f"[{queue_path}] §{key.replace('#', ' #')} 称呼违规："
                f"本行 `Paul` 命中 {rec['count']} 处，baseline 冻结时为 {frozen} 处"
                f"（新增 {rec['count'] - frozen} 处）；片段 "
                + " ｜ ".join(f"「{s}」" for s in rec["snippets"])
                + f"。{APPELLATION_HINT}"
            )
    for key, frozen in baseline.items():
        if key not in seen and frozen:
            stats["drift"].append(f"{key}（baseline {frozen} → 现 0／行已不在扫描面）")
    return violations, stats


def emit_appellation_baseline(repo_root: Path) -> str:
    """按 baseline 文件格式生成当前命中集的 JSON 文本（**只返回，不写盘**）。

    豁免行（路径形态由正则天然排除；`[S:done]` 与行内标记由 `exempt` 排除）
    一律不入 baseline——它们本就永远不会被判违规，写进去只是死条目，而死
    条目会让下一个读 baseline 的人以为那些行是被 baseline 放行的。
    """
    hits: dict[str, int] = {}
    for queue_path in QUEUE_PATHS_REL:
        target = repo_root / queue_path
        if not target.exists():
            continue
        for key, rec in _appellation_scan(target.read_text(encoding="utf-8")).items():
            if rec["exempt"]:
                continue
            hits[key] = rec["count"]

    def _sort_key(item: tuple[str, int]) -> tuple[int, int, str]:
        label, _, num = item[0].partition("#")
        order = APPELLATION_SCOPE_SECTIONS.index(label) if label in APPELLATION_SCOPE_SECTIONS else 9
        return (order, int(num) if num.isdigit() else 10**9, num)

    return json.dumps(
        {
            "说明": (
                "队列 #352 称呼判据 baseline：冻结判据上线当日的存量命中，只拦新增。"
                "键＝`§区#行号`（跨两份队列文件全局唯一，刻意不含文件名，见 "
                "`工具-队列结构lint.py::_appellation_row_key`）；值＝该行 `Paul` 命中数。"
                "🔴 历史记录不追改——本文件的存在正是这条纪律的机器表达，不得为了让"
                "数字好看而去改历史行的正文。"
            ),
            "重刷方式": (
                "python 0-学习与工具/工具-队列结构lint.py --emit-baseline > "
                "0-学习与工具/队列称呼判据-baseline.json"
                "（刻意没有一键写盘开关：重刷必须经过一次显式重定向 + 一次 commit，"
                "好让它在 diff 里被人看见）"
            ),
            "冻结日期": "2026-08-24",
            "命中": dict(sorted(hits.items(), key=_sort_key)),
        },
        ensure_ascii=False,
        indent=2,
    ) + "\n"


# ---------------------------------------------------------------------------
# 队列 #426 / OP-0828-P：编号高水位线不得低于实测最大已用号
# ---------------------------------------------------------------------------
#
# 🔴 **本判据治的不是「有一格没补上」，是那一格为什么会漏——一个不对称。**
#
# 高水位线（机制环境文件顶部那行 `编号高水位线：§一 #N ｜ §四 #M`）只有
# **一条**路径会自动推进：`工具-共享文档编辑锁.py acquire --reserve N
# --section X`（协议〇.7／队列 #163，读→分配→回写在同一持锁窗口内原子完成）。
# 而**手工立行**——直接编辑表格、或 `append-row --number` 写字面编号——把行
# 写进去了，**顶部那行一个字都不会动**（队列 §四 #128 ⑻ 已逐步复现过这条路）。
#
# 2026-08-28 实测到的那一次，恰好把这个不对称的两半都摆了出来：
#   · `4aab5b0` §一 `#426` 由 CC agent **手工**立行 ⇒ 高水位线**没动**，停在 425；
#   · `fc01961` §一 `#427` 由企微机器人 `append-row` 自动追行 ⇒ 高水位线
#     **一次从 425 推到 427**，顺手把 `#426` 欠的那一格一起补上了。
#
# 🔑 **所以那天没人撞号，不是因为机制守住了，是因为当天恰好有一封专员回件。**
# 缺陷被另一条机制偶然掩盖，于是它既没被发现、也没被修，只是暂时看不见——
# 这与根 `CLAUDE.md` §5「工具静默回退」、§一 `#341` 同族：**错误不产生任何信号。**
#
# ⚠️ **不得把本判据读成「编辑锁没有防护」**——`_reserve_ids` 里已经有一道
# **取号时**的碰撞检测（队列 #185）：真去 `--reserve` 时，若算出的号已出现在
# 可见行里，它当场 `ReserveFailedError` 拒绝。**那道防护是真的、且是硬的。**
# 本判据补的是它的**时间位置**：那道防护在「下一个人来取号」那一刻才响，而且
# 响在他脸上（他没做错任何事）；本判据在**引入滞后的那次改动进 CI 时**就响，
# 响在做那次改动的人脸上。同一个缺陷，两个不同的发现时点。
#
# **扫描面：只比两份活队列文件的可见行，刻意不含归档件。** 归档件的编号按
# 构造恒 ≤ 归档当时的高水位线，把它们纳入只会为「高水位线被人手工回退到
# 归档号以下」这一种从未发生过的形态付出一整套脆弱的归档标题解析（归档件
# 历次标题措辞不统一，见 `editlock._split_live_sections` 的 docstring 说明）。
# 🔴 **如实登记这个盲区**：高水位线若被回退到某个**已归档**编号以下，本判据
# 看不见——但 `_reserve_ids` 的取号碰撞检测同样看不见（它也只扫可见行），
# 故本判据没有比既有防线更弱，只是没有更强。
HIGH_WATER_SECTIONS = ("一", "四")
HIGH_WATER_HINT = (
    "高水位线只被 `工具-共享文档编辑锁.py acquire --reserve N --section X` 自动推进；"
    "手工立行与 `append-row --number` 写字面号都不会推它。"
    "修法二选一：⑴ 在持锁窗口内把机制环境文件顶部那行改到 ≥ 实测最大已用号；"
    "⑵ 此后一律用 `--reserve` 取号，不自己写字面编号（协议〇.7／队列 #163）。"
)


def _visible_max_numbers(text: str) -> dict[str, int]:
    """一份队列文件里各分区**可见行**的最大编号（无可见行的分区不出现在返回值里）。"""
    sections = editlock._split_live_sections(text)
    result: dict[str, int] = {}
    for label in HIGH_WATER_SECTIONS:
        numbers = [
            int(cells[0])
            for _, cells in editlock._table_data_rows(sections.get(label, ""))
            if cells and cells[0].strip().isdigit()
        ]
        if numbers:
            result[label] = max(numbers)
    return result


def _parse_high_water_line(text: str) -> tuple[str, dict[str, int]] | None:
    """从一份队列正文里取出高水位线整行与各分区当前值；不含该行返回 `None`。"""
    line_match = editlock.HIGH_WATER_MARK_LINE_PATTERN.search(text)
    if line_match is None:
        return None
    start = text.rfind('\n', 0, line_match.start()) + 1
    end = text.find('\n', line_match.end())
    line = text[start:] if end == -1 else text[start:end]
    values: dict[str, int] = {}
    for label in HIGH_WATER_SECTIONS:
        pattern = editlock.SECTION_NUMBER_PATTERNS.get(label)
        if pattern is None:
            continue
        section_match = pattern.search(line)
        if section_match is not None:
            values[label] = int(section_match.group(2))
    return line.strip(), values


def high_water_mark_check(repo_root: Path) -> tuple[list[str], dict]:
    """返回 (违规说明列表, 统计信息)。违规**计入** `lint()` 与退出码。

    🔴 **不需要 baseline**：判据上线时存量为零（2026-08-28 实测高水位线
    `§一 #427 ｜ §四 #132`，两份活队列可见行实测最大 `§一 427 ／ §四 132`，
    完全对齐），故当天即绿，硬拦不会挡住任何既有内容——同 `appellation_check`
    的分野说明：有存量才需要先走告警期。
    """
    stats = {
        "carriers": [],   # [(相对路径, 高水位线原行)]
        "current": {},    # {分区: 高水位线当前值}
        "max_used": {},   # {分区: (实测最大已用号, 出处相对路径)}
    }
    violations: list[str] = []

    parsed_texts: list[tuple[str, str]] = []
    for queue_path in QUEUE_PATHS_REL:
        target = repo_root / queue_path
        if not target.exists():
            continue
        parsed_texts.append((queue_path, target.read_text(encoding="utf-8")))

    # ⑴ 载体唯一性。高水位线**恒定只存机制环境那一份**（编辑锁模块常量
    # `QUEUE_LOCK_ANCHOR` 处的决策点 1/2：拆分为双文件后编号空间仍单一）。
    # 🔴 业务场景那份**没有**这行是设计、不是缺陷——给它补一行就等于造出
    # 两个会各自漂移的真值，那比滞后一格严重得多，故此处反过来拦「出现第二
    # 份载体」，而不是拦「有一份没有」。
    for queue_path, text in parsed_texts:
        parsed = _parse_high_water_line(text)
        if parsed is not None:
            stats["carriers"].append((queue_path, parsed[0]))
    if not stats["carriers"]:
        violations.append(
            "两份活队列文件均不含「编号高水位线」标注行——取号载体缺失，"
            "`acquire --reserve` 会直接 fail-loud 拒绝取号（见 "
            "`工具-共享文档编辑锁.py::_reserve_ids`）。" + HIGH_WATER_HINT
        )
        return violations, stats
    if len(stats["carriers"]) > 1:
        violations.append(
            "出现 %d 份「编号高水位线」载体（%s）——编号空间单一，载体也必须"
            "单一（恒定只存机制环境那一份，见 `工具-共享文档编辑锁.py` 的 "
            "`QUEUE_LOCK_ANCHOR` 决策点 1/2）。两份载体会各自漂移，"
            "而漂移出来的两个值都「看起来很正常」。"
            % (len(stats["carriers"]), "、".join(p for p, _ in stats["carriers"]))
        )
        return violations, stats

    carrier_path, carrier_line = stats["carriers"][0]
    stats["current"] = _parse_high_water_line(
        dict(parsed_texts)[carrier_path]
    )[1]

    # ⑵ 各分区实测最大已用号——🔴 **逐份解析后合并，绝不拼接文本再解析一次**。
    # `editlock._split_live_sections` 只取第一个 `## 一、`，拼接会静默丢掉
    # 第二份文件的 §一（队列 §一 `#312` 已因这一手法实际翻过车，那次的表现
    # 同样是「结果看起来完全正常」）。
    for queue_path, text in parsed_texts:
        for label, value in _visible_max_numbers(text).items():
            known = stats["max_used"].get(label)
            if known is None or value > known[0]:
                stats["max_used"][label] = (value, queue_path)

    for label in HIGH_WATER_SECTIONS:
        used = stats["max_used"].get(label)
        if used is None:
            continue  # 该分区可见行已全部归档，无可比对象
        current = stats["current"].get(label)
        if current is None:
            violations.append(
                f"[{carrier_path}] 高水位线行不含 §{label} 编号（格式漂移）："
                f"{carrier_line}。{HIGH_WATER_HINT}"
            )
            continue
        if current < used[0]:
            violations.append(
                f"[{carrier_path}] 编号高水位线 §{label} #{current} **低于**两份"
                f"活队列可见行实测最大已用号 #{used[0]}（该号在 [{used[1]}]）"
                f"——下一次 `--reserve --section {label}` 会算出一个已被占用的号，"
                f"届时 `_reserve_ids` 的碰撞检测会当场拒绝取号，"
                f"拦在**下一个来取号的人**脸上（他没做错任何事）。{HIGH_WATER_HINT}"
            )

    return violations, stats


def lint(repo_root: Path) -> list[str]:
    """队列 #315：遍历两份物理队列文件（机制环境／业务场景），每份独立跑
    同一套校验，违规说明前缀标注来源文件，避免两份文件都出问题时混在
    一起分不清是哪一份。"""
    violations: list[str] = []
    for queue_path in QUEUE_PATHS_REL:
        target = repo_root / queue_path
        if not target.exists():
            violations.append(f"[{queue_path}] 文件不存在，无法校验。")
            continue
        text = target.read_text(encoding="utf-8")
        violations.extend(
            f"[{queue_path}] {v}" for v in _lint_one_file(text)
        )
    # 队列 #352：称呼判据自带 baseline（存量已冻结、当天即绿），故直接进
    # 违规列表参与退出码——它与 #366/S2 那条只 warn 的判据不同，那条上线时
    # 存量非零且没有 baseline，一期硬拦会挡住所有人的 push。
    appellation, _ = appellation_check(repo_root)
    violations.extend(appellation)
    # 队列 #426 / OP-0828-P：高水位线判据同样无需 baseline（上线当日实测
    # 已对齐），故与称呼判据同侧，直接参与退出码。
    high_water, _ = high_water_mark_check(repo_root)
    violations.extend(high_water)
    return violations


def followup_restate_warnings(repo_root: Path) -> tuple[list[str], int]:
    """队列 #366 / S2 一期：只 warn、不计入 `lint()` 的违规、不影响退出码。

    🔴 一期刻意不硬拦，与 `claude-progress-lint` 同策略：本判据上线时存量
    非零（实测 3 处活行），一期就 `--enforce` 会立刻挡住所有人的 push，而
    「队列不得复述信状态」这条规则如果第一天就被绕过，绕过的将是 lint 本身。
    二期存量清零后另派单件切硬拦。
    """
    warnings: list[str] = []
    historical_total = 0
    for queue_path in QUEUE_PATHS_REL:
        target = repo_root / queue_path
        if not target.exists():
            continue
        live, historical = _followup_restate_scan(target.read_text(encoding="utf-8"))
        warnings.extend(f"[{queue_path}] {w}" for w in live)
        historical_total += historical
    return warnings, historical_total


def _broken_row_head_violations(section_text: str, label: str) -> list[str]:
    """队列 #414 A3：**行头断裂**——lint 此前的两处真实盲区。

    🔴 **先更正一条派单件里的判断**：派单件写「`#414` 一度为 13 列，而本
    lint 报通过，请复现并修」。**该形态实测复现不出来**——构造一条真正 13
    列的 §一 行，现有列数校验**当场就报**（已配反例单测锁死）。真正让 lint
    静默放行的是另外两种形态，它们的共同点是**行根本没能进入列数校验**：

      **C · 编号格被清空** —— `_table_data_rows` 把「首格为空」当作表头/
      分隔行跳过（`_TABLE_HEADER_FIRST_CELLS` 含空串）。于是编号被冲掉的
      行**连列数校验都没机会跑**。这正是 2026-08-26 事故形态之一「列位错置
      → 编号格 → 行头断裂，grep 与队列查询双双找不到该行」。

      **D · 行首竖线丢失** —— `split_row_cells` 对不以 `|` 开头的行返回
      `None`，该行被整条丢弃。

    🔑 **元判据（比这两条修法更值得记住）**：**一行「坏到连解析器都不认它
    是一行」的数据，会从所有按行校验的判据里彻底消失，于是 lint 报「通过」
    ——通过的意思是「我检查过的都没问题」，不是「没问题」。** 同族＝「工具
    静默回退」（取证知识库 §二）：坏消息让人追根因，而「太干净」的结果不会。

    两条判据均已对当前生产队列实测：**0 误报**（判据刻意收窄——C 要求其余
    格确有内容且不是分隔行；D 要求行尾是 `|` 且竖线 ≥3，才算「像一条被
    截断的表格行」，纯正文里偶然出现的竖线不会命中）。
    """
    violations: list[str] = []
    for line in section_text.splitlines():
        stripped = line.strip()
        cells = editlock.queue_table.split_row_cells(line)
        preview = stripped if len(stripped) <= 80 else stripped[:80] + "…"

        if cells is not None and cells and not cells[0].strip():
            rest = "".join(cells[1:]).strip()
            others = [c.strip() for c in cells[1:] if c.strip()]
            is_separator = bool(others) and all(
                set(c) <= {"-", ":", " "} for c in others
            )
            if rest and not is_separator:
                violations.append(
                    f"§{label} 行**首格为空**且其余格有内容——行头断裂，该行会被"
                    f"当成表头/分隔行静默跳过，列数校验根本跑不到它，grep 与队列"
                    f"查询也都找不到它（队列 #414 实测形态）：{preview}"
                )
            continue

        if cells is None and stripped.endswith("|") and stripped.count("|") >= 3:
            violations.append(
                f"§{label} 行**行首竖线丢失**——该行不以 `|` 开头却以 `|` 结尾"
                f"且含多个竖线，形似一条被截断的表格行；解析器会整条丢弃它，"
                f"因而不进任何按行校验（队列 #414 实测形态）：{preview}"
            )
    return violations


def _lint_one_file(text: str) -> list[str]:
    sections = editlock._split_live_sections(text)
    violations: list[str] = []
    for label, expected_cols in editlock.SECTION_COLUMN_COUNTS.items():
        section_text = sections.get(label, "")
        # 队列 #414 A3：先扫"坏到进不了列数校验"的行——行头断裂的两种形态
        # 会被解析器整条丢弃，不先单独扫一遍，下面的循环永远看不到它们。
        violations.extend(_broken_row_head_violations(section_text, label))
        for line, cells in editlock._table_data_rows(section_text):
            preview = line.strip()
            if len(preview) > 80:
                preview = preview[:80] + "…"
            if len(cells) != expected_cols:
                violations.append(
                    f"§{label} 行列数为 {len(cells)}（应为 {expected_cols}，"
                    f"含反引号内裸竖线等致列偏移的情形）：{preview}"
                )
                continue
            if label == "二" and editlock._section_two_status_is_ambiguous(cells[3]):
                violations.append(
                    f"§二 行状态列开头片段既不含「待」也不含「✅」"
                    f"（会被 sweep 判为状态列模糊，见 #247）：{preview}"
                )
            if label == "一":
                # 队列 #308 决策点 1：106 行存量回填与七处消费者切换均已
                # 完成后新增的硬门禁——§一 任意数据行状态列不以 `[S:` 开头
                # 即判违规，把"未来新行必须带机器字段"从约定升级为可执行
                # 门禁。回填/消费者切换完成前不得上线（会对存量误报），
                # 现已确认全部完成（见队列 #308 行内回写）。
                status_value, _, _ = editlock._parse_status_domain_fields(cells[5])
                if status_value is None:
                    violations.append(
                        f"§一 行状态列缺少机器可读字段（须以 `[S:done/open/partial/"
                        f"hold/blocked/timed=YYYY-MM-DD]` 开头，见队列 #308）：{preview}"
                    )
    return violations


def check_queue_table_importable(repo_root: Path) -> str | None:
    """队列 #313：断言权威模块 `zhuopin_platform.shared_tools.queue_table`
    可 import。返回 None＝可 import；否则返回违规说明字符串。

    走与场景入口脚本同款的 #300 式 sys.path 引导（本函数自己插一次，
    不依赖调用方是否已引导过），不用 `pip install -e`——该模块与其两层
    `__init__.py` 均无第三方依赖，直接插路径即可稳定导入。"""
    platform_dir = repo_root / "5-平台底座" / "zhuopin_platform"
    if not platform_dir.is_dir():
        return f"未找到 {platform_dir}（仓库根标记缺失，无法校验权威模块可达性）"
    inserted = str(platform_dir) not in sys.path
    if inserted:
        sys.path.insert(0, str(platform_dir))
    try:
        import importlib

        module = importlib.import_module("zhuopin_platform.shared_tools.queue_table")
        if not hasattr(module, "SECTION_COLUMN_COUNTS"):
            return (
                "zhuopin_platform.shared_tools.queue_table 可 import，但缺少"
                "预期符号 SECTION_COLUMN_COUNTS（模块内容被改动？）"
            )
        # 队列 #366 / S4：同一条断言扩到 `followup_gate`。理由与 #313 逐字
        # 相同——`工具-共享文档编辑锁.py` 对它也有兜底（import 不到时 S4
        # 桥二整条校验跳过，只打一行 ⚠），**那条降级路径本身是静默的**，
        # 本断言存在的唯一目的就是让它红。
        gate = importlib.import_module("zhuopin_platform.shared_tools.followup_gate")
        missing = [
            name for name in ("CLOSED_STATUS_PREFIXES", "is_closed_status",
                              "find_unsynced_letters", "reply_matches_letter")
            if not hasattr(gate, name)
        ]
        if missing:
            return (
                "zhuopin_platform.shared_tools.followup_gate 可 import，但缺少"
                f"预期符号 {'、'.join(missing)}（模块内容被改动？）"
                "——编辑锁的 S4 桥二校验会因此静默跳过"
            )
        return None
    except ImportError as exc:
        return (
            f"zhuopin_platform.shared_tools.queue_table 无法 import：{exc}"
            "（四处消费者——编辑锁／台账／sweep／队列查询——的兜底桩会各自"
            "静默降级回本地实现，此断言正是为了不让那次降级零报错，见队列 #313）"
        )
    finally:
        if inserted:
            sys.path.remove(str(platform_dir))


def print_scope_self_report() -> None:
    """队列 #426 第 ③ 件：**运行时自报本次实际校验的绝对路径**。

    🔴 **纯打印，不改任何判定、不影响退出码。** 本函数存在的全部理由是
    `#426` 行内那句实测：某个 worktree 隔离的 CC agent 在一次会话里三次跑
    本脚本、三次报「lint 通过」，而**那三次校验的都是主工作区那份文件、
    不是它自己改的那份**——`REPO_ROOT` 按设计恒解到主工作区（见本文件头部
    `#314①` 注释），这是对的；错的是**它从不说自己在看哪份文件**，于是
    「lint 通过」这句话在 linked worktree 里说出来时，含义与所有人以为的不同。

    🔑 **判据（比这几行 print 本身通用得多）**：**一个工具凡是「实际作用
    对象」可能与「调用者以为的作用对象」不一致，它就必须在每次运行时把
    实际对象打出来。** 沉默在这里不是中立的——它让一句正确的结论被读成
    另一句话。同族＝根 `CLAUDE.md` §5「工具静默回退」。
    """
    script_worktree = Path(__file__).resolve().parents[1]
    print(f"📍 本次实际校验（REPO_ROOT ＝ 主工作区，见文件头 #314①）：{REPO_ROOT}")
    for queue_path in QUEUE_PATHS_REL:
        target = REPO_ROOT / queue_path
        mark = "" if target.exists() else "  ⚠ 不存在"
        print(f"     - {target}{mark}")
    same = script_worktree == REPO_ROOT
    if not same:
        try:
            same = script_worktree.samefile(REPO_ROOT)
        except OSError:
            same = False
    if not same:
        print(
            f"⚠️ 本脚本副本位于另一个 worktree：{script_worktree}\n"
            "   ⇒ **本次校验的不是你改的那份队列文件，是主工作区那份**"
            "（队列文件的权威副本只有主工作区那一份，见文件头 #314① 与队列 §一 #426）。\n"
            "   本次「通过／不通过」不构成对你 worktree 内改动的任何结论；"
            "你那份要等 ff 进 master、由 sweep 同步回主工作区后才会被本 lint 看到。"
        )


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if "--emit-baseline" in args:
        # 只打到 stdout，不写盘——落盘须显式重定向，见 `emit_appellation_baseline`。
        sys.stdout.write(emit_appellation_baseline(REPO_ROOT))
        return 0

    # 队列 #426③：**先自报作用域，再跑判据**——放最前面是因为退出码那一行
    # 是读者唯一必看的一行，而「这句话是对哪份文件说的」必须在它之前出现。
    print_scope_self_report()

    violations = lint(REPO_ROOT)
    import_error = check_queue_table_importable(REPO_ROOT)
    if import_error:
        violations.append(import_error)

    # 队列 #352：称呼判据的三类豁免必须逐类打数出来。豁免本身不是问题，
    # **数不出来的豁免才是**——`WIP豁免：` 那条逃生阀当初就写明「批量出现
    # 即说明上限定错了，应回去重议而不是继续豁免」，前提是它数得出来。
    _, appellation_stats = appellation_check(REPO_ROOT)
    if appellation_stats["exempt_rows"]:
        by_reason: dict[str, int] = {}
        for _, reason, count in appellation_stats["exempt_rows"]:
            by_reason[reason] = by_reason.get(reason, 0) + count
        print(
            "  称呼判据豁免："
            + "；".join(f"{r} {n} 处" for r, n in sorted(by_reason.items()))
            + f"（行内标记原文可 grep `{APPELLATION_EXEMPT_MARK}`，批量出现即须回队列 #352 重议判据）"
        )
    print(
        f"  称呼判据 baseline：受管活行 {appellation_stats['live_rows']} 行／"
        f"{appellation_stats['live_hits']} 处命中，均已冻结；"
        f"漂移（命中变少或行已不在扫描面）{len(appellation_stats['drift'])} 处"
        "——漂移不算违规，是可以收紧 baseline 的信号。"
    )

    # 队列 #426：把「高水位线 vs 实测最大已用号」两个数**都打出来**，不止在
    # 违规时才说话。理由与上面豁免计数同一条：一个只在出事时才出声的判据，
    # 平时无法被任何人核对，也就无从知道它是不是早已失效（同 §四 #58）。
    _, hwm_stats = high_water_mark_check(REPO_ROOT)
    if hwm_stats["carriers"]:
        parts = []
        for label in HIGH_WATER_SECTIONS:
            current = hwm_stats["current"].get(label)
            used = hwm_stats["max_used"].get(label)
            parts.append(
                f"§{label} 高水位线 #{current if current is not None else '缺'}"
                f" ／ 实测最大已用号 #{used[0] if used else '无可见行'}"
            )
        print(
            "  编号高水位线（载体＝"
            + hwm_stats["carriers"][0][0]
            + "）："
            + "；".join(parts)
            + "——高水位线只被 `acquire --reserve` 自动推进，手工立行不会推它。"
        )

    # 队列 #366 / S2 一期：先打印 warn 段，再打印硬判据结论——放在前面是
    # 因为退出码由硬判据决定，读者看到 `✓ 通过` 后就不会再往下看了。
    restate_warnings, restate_historical = followup_restate_warnings(REPO_ROOT)
    if restate_warnings:
        print(f"⚠ 队列复述信状态（S2 一期只告警，不计入退出码）：{len(restate_warnings)} 处活行")
        for w in restate_warnings:
            print(f"  - {w}")
    print(
        f"  二期基线：活行 {len(restate_warnings)} 处；"
        f"另有 {restate_historical} 处落在 §一 `[S:done]` 历史行，"
        "按「历史记录不追改」豁免、不计入（§二 批次行不在扫描范围）。"
    )

    files_desc = "、".join(QUEUE_PATHS_REL)
    if not violations:
        print(
            f"✓ {files_desc} 结构 lint 通过"
            "（列数／§二状态列格式／权威模块可 import／称呼判据／编号高水位线）。"
        )
        return 0

    print(f"✗ {files_desc} 结构 lint 发现 {len(violations)} 处违规：")
    for v in violations:
        print(f"  - {v}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
