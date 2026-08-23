#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""变更包「实质完工」判定（OP-0823-F，队列 §四 #87；变更包 auto-archive-substantive-complete）。

━━━ 这个工具解决什么 ━━━

`openspec list` 的 `N/M` **对两类包给出完全相同的外观，而它们该被怎么处理是相反的**：

    sweep-ops-webhook-cutover     30/31   差的那 1 条 = 它自己的 archive 步骤  ⇒ 实质完工
    queue-status-machine-field    47/48   差的那 1 条 = `8.3 真实主工作区验证`  ⇒ 真没做完

后果已经现实发生：2026-08-23 那轮 sweep「疑似遗忘归档」告警 4 报 3 误，因为它只看得到
`N/M`。而误报的代价不是噪音，**是它会训练人忽略这条告警**——那条告警存在的全部意义正是
在真的漏了归档时把人拦住。

本模块把「未勾的那几条到底是不是只剩 archive 这个动作本身」这个判断从人脑搬到代码里。

⚠️ **一处必须写明的更正**（2026-08-23 开工取证，推翻派单件 §一 的立论一半）：
派单件断言「归档做不了、判据死锁」。**「做不了」不成立**——`openspec/changes/archive/` 下
50 个已归档包里 **39 个归档时是 N/N**，做法是先把那条 archive task 自己勾上再跑 archive。
⇒ 本工具的价值**不是**「让本来归不了档的包能归档」（那件事一直在发生），而是
**把一个做过 50 次、且机器分不出真假的手工判断机制化**。不要在别处把它写成「破死锁」。

━━━ 🔴 本工具不执行归档 ━━━

**它只做判定，不调用 `openspec archive`、不勾任何 task、不移动任何目录。**
范围由 Shao Peishen 2026-08-23 拍板取 (b)：判据只用来给落库 sweep 的滞留告警**分类**，
归档动作仍由人做。判定结果分四类，各自措辞不同——「疑似遗忘归档」只留给真遗忘：

    complete（N/N）                     ⇒ 「只差归档这一步」（**最纯的真遗忘**，见 §3.1ter）
    substantively-complete ＋ 无人留话   ⇒ 「只差归档这一步」（真遗忘，升级告警）
    substantively-complete ＋ 有人留话   ⇒ 「作者已写明理由，但未用机器认得的入口」＋给出三条入口
    incomplete                          ⇒ 「尚有 N 条真未完项」（它没完工，谈不上忘了归档）
    no-tasks                            ⇒ 「判不了完工」（显式记名，不静默略过）

🔴 **第一类曾被漏掉，且它是最常见的那一种** —— 39/50 已归档包在归档时是 N/N。
修复前 N/N 会落进 `incomplete` 被说成「尚有 0 条真未完项，它没完工」，自相矛盾
且恰好把最该喊的那一类喊反了。判据的完整定义见 `is_substantively_complete`。

权衡与取舍见 `1-转型规划/0-全景路线图/定夺件-【CC】自动归档范围-a自动归档vs-b只修告警-2026-08-23.md`。

⚠️ **文件名保留 `工具-变更包自动归档.py` 不改**：它已被 commit、队列行、派单件以此名引用，
改名会让那些指针失效（本项目已多次记过「指针指向已不存在的东西」这个形态）。
**以本注释为准：本工具不归档。**
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ── 判定结果四态 ──────────────────────────────────────────────────────────────
# 刻意用字符串常量而非 Enum：判定结果要落进 sweep 日志与告警正文，字符串直接可读，
# 且单测断言不必 import 本模块的类型。
NO_TASKS = "no-tasks"                        # 无任何复选框行 —— 判不了完工，显式记名
COMPLETE = "complete"                        # 0 未勾 —— 已无欠账
SUBSTANTIVE = "substantively-complete"       # ≥1 未勾，且**全部**是 archive 动作类
INCOMPLETE = "incomplete"                    # ≥1 未勾，其中有真未完项

_CHECKBOX_RE = re.compile(r"^\s*[-*]\s+\[([ xX])\]\s*(.*)$")

# 判据（派单件 §3.1，宁严勿宽）：两条**须同时满足**。
#   条件一：行内含 `archive`（大小写不敏感）
#   条件二：行内含 `/opsx:archive`、`openspec archive`、或「归档」三者之一
# 只满足条件二（如「- [ ] 归档后回填队列行」）不算——那是归档的下游工作，不是归档本身。
_ARCHIVE_WORD_RE = re.compile(r"archive", re.IGNORECASE)
_ARCHIVE_ACTION_RE = re.compile(r"/opsx:archive|openspec\s+archive|归档")


def is_archive_action_line(line: str) -> bool:
    """这一条未勾项是不是「archive 这个动作本身」。

    🔴 判据刻意不放宽到「未勾数 ≤1」——实测反例 `queue-status-machine-field` 47/48，
    那 1 条是 `8.3 真实主工作区验证`，是真未完项；按数量判会把它错归档，而 archive
    不可逆。
    """
    return bool(_ARCHIVE_WORD_RE.search(line) and _ARCHIVE_ACTION_RE.search(line))


# ── 「这行里有没有人留了话」（形态判别，不做自然语言理解）────────────────────
#
# 🔴 这一节由 2026-08-23 首次 dry-run 的实测结果反推而来，**不在派单件原规格内**：
# 判据判出的 3 个「实质完工」，**3 个的 archive 行都带着作者写的「本次不做／本轮不做，
# 前置条件未满足」**。判据只看关键词，结构上读不到同一行后半截那些字。
#
# 队列 §四 #87 早已说穿这个形态（「都把理由写了……只是没写在机器认得的地方」），
# 并且**明确否掉了靠认自然语言来补救**：
#     「不该把机制放宽去认自然语言——『本次不做』这种话随手就能写，
#       模糊匹配会让降噪变成默认；要求一个特定字符串正是它有价值的地方。」
#
# ⇒ 故这里**不判断那些字是什么意思，只判断「这里有没有字」**：
#   一条光秃的 archive 行（最近三次真实归档全是这个形态）vs 一条挂着说明或子项的行。
_CODE_SPAN_RE = re.compile(r"`[^`]*`")
_TASK_NUM_RE = re.compile(r"^\s*[-*]\s+\[[ xX]\]\s*[\d.]*\s*")
_NOISE_RE = re.compile(r"[\s\-—–、，。；：,.;:()（）*_#\[\]\"'’“”/]+")
# 去掉命令与标点后，剩下多少个实词字符才算「留了话」。8 是保守取值：宁可多判为
# 「有人留了话」（后果＝交人看一眼），也不可少判（后果＝不可逆误归档）。
_HUMAN_NOTE_MIN_CHARS = 8


def carries_human_note(line: str) -> bool:
    """这条 archive 行上有没有人留了话（形态判别）。

    做法：剥掉复选框与任务编号 → 剥掉反引号代码段（命令本身）→ 剥掉裸命令词与开关 →
    剩下的实词字符若超过阈值，判为「有人留了话」。
    """
    rest = _TASK_NUM_RE.sub("", line)
    rest = _CODE_SPAN_RE.sub("", rest)
    rest = _ARCHIVE_ACTION_RE.sub("", rest)
    rest = re.sub(r"--?yes\b|-y\b|[\w-]*archive[\w-]*", "", rest, flags=re.IGNORECASE)
    rest = _NOISE_RE.sub("", rest)
    return len(rest) >= _HUMAN_NOTE_MIN_CHARS


@dataclass
class Verdict:
    """一个变更包的判定结果。

    `unchecked` 保留原文行，供告警／dry-run 逐条回显——#87 的教训：
    只印一句写死的话、不说命中了什么，判据就无法被现场证伪。
    """

    name: str
    status: str
    checked: int = 0
    unchecked: list[str] = field(default_factory=list)
    reason: str = ""
    # 🔴 任一未勾项（含其缩进子项）上有人留了话 —— 无论走 (a) 还是 (b)，这一位为真时
    # 都不得自动归档，只能交人看一眼。见上文 `carries_human_note` 的成因。
    unchecked_carry_notes: bool = False

    @property
    def total(self) -> int:
        return self.checked + len(self.unchecked)

    @property
    def progress(self) -> str:
        return "无 tasks" if self.status == NO_TASKS else f"{self.checked}/{self.total}"


def classify_tasks(text: str, name: str = "") -> Verdict:
    """按 tasks.md 全文判定该包的完工形态。纯函数，不碰文件系统。"""
    checked = 0
    unchecked: list[str] = []
    carry_notes = False
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = _CHECKBOX_RE.match(line)
        if not m:
            continue
        if m.group(1) != " ":
            checked += 1
            continue
        unchecked.append(line.strip())
        if carries_human_note(line):
            carry_notes = True
            continue
        # 说明也可能写在**下一行的缩进子项**里（sweep-ops 的「本轮不做」就在子项上），
        # 只看本行会漏掉它——那正是一次不可逆误归档的入口。
        indent = len(line) - len(line.lstrip())
        for nxt in lines[i + 1:]:
            if not nxt.strip():
                break
            if len(nxt) - len(nxt.lstrip()) <= indent or _CHECKBOX_RE.match(nxt):
                break
            carry_notes = True
            break

    if checked == 0 and not unchecked:
        return Verdict(name, NO_TASKS, 0, [], "无任何复选框行，判不了完工——显式记名，不静默略过")
    if not unchecked:
        return Verdict(name, COMPLETE, checked, [], "已无欠账")

    non_archive = [ln for ln in unchecked if not is_archive_action_line(ln)]
    if non_archive:
        return Verdict(
            name, INCOMPLETE, checked, unchecked,
            f"尚有 {len(non_archive)} 条真未完项（非 archive 动作）",
            unchecked_carry_notes=carry_notes,
        )
    reason = f"未勾的 {len(unchecked)} 条全部是 archive 动作本身"
    if carry_notes:
        reason += "，🔴 但行内/子项有人留了话 —— 不得自动归档，交人看一眼"
    return Verdict(name, SUBSTANTIVE, checked, unchecked, reason, unchecked_carry_notes=carry_notes)


def is_substantively_complete(verdict: Verdict) -> bool:
    """「实质完工」的完整定义（派单件 §3.1ter，2026-08-23 Shao Peishen 追问自洽性后补）。

    **两条任一命中即成立**：

        ⑴ 未勾项数 ＝ 0（N/N）
        ⑵ 未勾项 ≥1 且全部是 archive 动作本身

    🔴 **⑴ 极易被漏掉，而它恰恰是最常见的那一种。** 派单件 §3.1ter 把它论证为「治本
    （新包不再把 archive 写进 tasks）生效之后才会出现」的未来问题——**但实测它现在就是
    主流路径**：`openspec/changes/archive/` 下 50 个已归档包里 **39 个在归档时是 N/N**。
    ⇒ 一个包在「勾完最后一条」到「跑完 archive」之间必然经过 N/N，这个窗口一旦超过
    滞留阈值，它就是**最纯的真遗忘归档**（连一条未勾项都没有，除了归档没别的事可做）。

    **本判据修复前的真实行为**：N/N 的包落进 `INCOMPLETE` 分支，被告警说成
    「尚有 0 条真未完项 —— 它没完工」——**既自相矛盾，又恰好把最该喊的那一类喊反了。**
    """
    return verdict.status in (COMPLETE, SUBSTANTIVE)


def scan_changes(changes_dir: Path) -> list[Verdict]:
    """扫描 `openspec/changes/*/tasks.md`，逐包判定。跳过 `archive/`（已归档的不再判）。"""
    verdicts: list[Verdict] = []
    if not changes_dir.is_dir():
        return verdicts
    for child in sorted(changes_dir.iterdir()):
        if not child.is_dir() or child.name == "archive":
            continue
        tasks = child / "tasks.md"
        if not tasks.is_file():
            verdicts.append(Verdict(child.name, NO_TASKS, 0, [], "无 tasks.md 文件"))
            continue
        verdicts.append(classify_tasks(tasks.read_text(encoding="utf-8", errors="replace"), child.name))
    return verdicts


# ── 执行环境前置（派单件 §3.3bis）────────────────────────────────────────────
# 🔴 这一节的存在理由，来自 OP-0823-D 同日的真实翻车：
#   「我读的是 worktree 副本、你那边读的是主工作区真身。同一个相对路径、两个不同的事实，
#     两边都读得出结果、都不报错。」
# 代入本工具即灾难：副本里「未勾项全是 archive」，真身里那个包可能还有未完项、甚至已被
# 别人归档；而 archive 是不可逆目录移动，读错一次就把没完工的包永久移走，**且移完之后
# 没有任何机制会告诉你移错了**。
#
# 判定**复用 `工具-落库sweep.py` 已有的那套**，不另写一套——两套判定各自为政正是本项目
# 反复记过的形态（派单件 §3.3bis 明确要求）。


class RefuseToRun(RuntimeError):
    """执行环境不满足前置——**拒绝执行，不是告警、不是跳过。**"""


def _load_sweep():
    path = Path(__file__).resolve().with_name("工具-落库sweep.py")
    spec = importlib.util.spec_from_file_location("_sweep_for_auto_archive", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_main_workspace(repo_root: Path, sweep=None) -> None:
    """非主工作区一律拒绝执行。

    复用 sweep 的 `MAIN_WORKSPACE` 常量与 `_assert_not_a_linked_worktree`
    （`.git` 是目录=主工作区；是文件=linked worktree）。
    """
    sweep = sweep or _load_sweep()
    if repo_root.resolve() != Path(sweep.MAIN_WORKSPACE).resolve():
        raise RefuseToRun(
            f"✗ 拒绝执行：repo_root={repo_root} 不是约定的主工作区 {sweep.MAIN_WORKSPACE}。"
            "本工具只在主工作区运行——worktree 副本的 tasks.md 可能停在分支点，而 archive 不可逆。"
        )
    try:
        sweep._assert_not_a_linked_worktree(repo_root)
    except sweep.SweepAbort as exc:  # 转成本模块的异常类型，调用方只需认一种
        raise RefuseToRun(
            f"✗ 拒绝执行：{exc}"
            "（本工具只在主工作区运行——worktree 副本的 tasks.md 可能停在分支点，而 archive 不可逆。）"
        ) from exc


# ── 告警分类（sweep 的滞留告警调这里）─────────────────────────────────────────
#
# 🔴 三类各自措辞，而不是「把误报的滤掉」。误报的对立面不是静默，是**说对话**：
# 若只把「有人留了话」那几个包滤掉不报，人就再也看不到「作者留了话但没用机器入口」
# 这件事——而那正是队列 §四 #87 查出的真根因，也正是下一次误报会重新长出来的地方。

ALERT_FORGOTTEN = "forgotten"      # 实质完工 ＋ 无人留话 ⇒ 只差归档这一步（这才是真遗忘）
ALERT_UNDECLARED = "undeclared"    # 实质完工 ＋ 有人留话 ⇒ 有理由，但没写在机器认得的地方
ALERT_UNFINISHED = "unfinished"    # 尚有真未完项 ⇒ 它没完工，谈不上忘了归档

# 三条现成降噪入口（队列 §四 #87 实测：机制早已具备，缺的是没人知道有这三个入口）。
# 🔴 第 2 类的告警正文**必须**把它们逐条列出——告警若只说「你没声明」而不给声明方式，
# 等于把同一个缺口原样留在那里。
DECLARE_ENTRIES = (
    "在 proposal/design/tasks 任一处写文本标记 `暂不归档`（作者对未来的永久声明）",
    "在同上三处写 `预期观察窗口：N 天`（命中即报「🔭 观察中」、不计异常，超窗才升级）",
    "跑 `工具-落库sweep.py --ack-stale-change <包名> --note <依据>`"
    "（复核者对过去某一刻的确认，带 done/total 指纹，tasks 一有新勾选即自动失效）",
)


ALERT_UNJUDGEABLE = "unjudgeable"  # 无 tasks.md ⇒ 判不了完工，显式记名而不是猜


def alert_class(verdict: Verdict) -> str:
    """把判定结果映射成告警类别。

    🔴 `COMPLETE`（N/N）**必须映射到 ALERT_FORGOTTEN，不能落进 UNFINISHED** ——
    见 `is_substantively_complete` 文档：那是最纯的真遗忘归档，而修复前它会被说成
    「尚有 0 条真未完项，它没完工」。派单件 §3.1ter。
    """
    if verdict.status == NO_TASKS:
        return ALERT_UNJUDGEABLE
    if verdict.status == COMPLETE:
        return ALERT_FORGOTTEN
    if verdict.status == SUBSTANTIVE:
        return ALERT_UNDECLARED if verdict.unchecked_carry_notes else ALERT_FORGOTTEN
    return ALERT_UNFINISHED


def alert_phrase(verdict: Verdict, days_idle: float) -> str:
    """一行措辞。逐条回显包名／结论／理由，使判据可被现场证伪（#87 教训）。"""
    kind = alert_class(verdict)
    head = f"`{verdict.name}`（{verdict.progress}，{days_idle:.1f} 天无改动）"
    if kind == ALERT_FORGOTTEN:
        why = (
            "tasks 已全部勾完（N/N），除归档外无事可做"
            if verdict.status == COMPLETE
            else "未勾项只剩 archive 动作本身且无人留说明"
        )
        return f"⚠ {head} **只差归档这一步** —— {why}，疑似遗忘归档"
    if kind == ALERT_UNDECLARED:
        return (
            f"📝 {head} **作者已写明理由，但未用机器认得的入口** —— "
            f"未勾项只剩 archive 动作，且行内/子项有人留了话"
        )
    if kind == ALERT_UNJUDGEABLE:
        return f"⚠️ {head} **判不了完工** —— 无 tasks.md，显式记名交人看"
    n = sum(1 for ln in verdict.unchecked if not is_archive_action_line(ln))
    return f"⬜ {head} **尚有 {n} 条真未完项** —— 它没完工，不属遗忘归档"


def declare_entries_block(indent: str = "  ") -> str:
    """第 2 类告警要附的三条出口。"""
    return "\n".join(f"{indent}· {e}" for e in DECLARE_ENTRIES)


# ── CLI ───────────────────────────────────────────────────────────────────────

_LABEL = {
    COMPLETE: "🟢 实质完工 · N/N（除归档外无事可做）",
    SUBSTANTIVE: "🟢 实质完工 · 未勾项只剩 archive 本身",
    INCOMPLETE: "⬜ 未完工",
    NO_TASKS: "⚠️ 判不了",
}


def render(verdicts: list[Verdict], verbose: bool = False) -> str:
    lines = ["变更包完工形态判定（判据：未勾项是否全部为 archive 动作本身）", ""]
    for order in (COMPLETE, SUBSTANTIVE, INCOMPLETE, NO_TASKS):
        group = [v for v in verdicts if v.status == order]
        if not group:
            continue
        lines.append(f"── {_LABEL[order]}（{len(group)} 个）" + "─" * 30)
        for v in group:
            lines.append(f"  {v.name:<48} {v.progress:>10}   {v.reason}")
            if verbose or order == SUBSTANTIVE:
                for ln in v.unchecked:
                    lines.append(f"      └ {ln}")
        lines.append("")
    n_sub = sum(1 for v in verdicts if is_substantively_complete(v))
    lines.append(f"合计 {len(verdicts)} 个在途包，其中判为「实质完工」{n_sub} 个"
                 "（＝ N/N 或 未勾项全为 archive 本身，派单件 §3.1ter）。")
    lines.append("🔴 本工具只判定、不归档。")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="变更包完工形态判定（只判定，不归档）"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="保留兼容：本工具本就只判定不改动，加不加都一样")
    parser.add_argument("--repo-root", default=None, help="仅供单测覆盖主工作区断言，生产不要传")
    parser.add_argument("--verbose", action="store_true", help="所有分组都逐条回显未勾项")
    args = parser.parse_args(argv)

    sweep = _load_sweep()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(sweep.MAIN_WORKSPACE)
    # 本工具纯只读，故主工作区断言在 CLI 里**不阻断**、只提示：读到 worktree 副本的清单
    # 仍有参考价值，但必须让人知道读的是副本（副本可能停在分支点——实测本变更包建造用的
    # worktree 里就有 2 个主工作区根本不存在的空「幽灵包」目录）。
    try:
        assert_main_workspace(repo_root, sweep)
    except RefuseToRun as exc:
        print(
            f"⚠️ {exc}\n"
            "   （本工具只读，继续打印，但下列结果来自非主工作区，不得据以判断。）\n",
            file=sys.stderr,
        )

    print(render(scan_changes(repo_root / "openspec" / "changes"), verbose=args.verbose))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
