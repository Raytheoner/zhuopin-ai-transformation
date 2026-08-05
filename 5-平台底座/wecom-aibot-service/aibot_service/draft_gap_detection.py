"""队列 #245：跟进信"该起草而没起草"检测——补齐 design.md D5 明确标注为
Non-Goal 的另一半比对逻辑。

design D5 原文：两态语义（`readme_table.DRAFT_PENDING_REVIEW_STATUS`/
`FINALIZED_STATUS_MARKER`）生效后，"起草了但没登记 README"这一子问题已被
结构性堵死——任何起草动作必然留下一行 `⏳ 待你审`。但"某个发布收口批次
本该触发起草、却连 `⏳ 待你审` 都没有"仍无检测，design 原文把这一半留作
"后续独立评估"，不预先设计。本模块正是那个后续评估：只做检测，不发送
任何通知——通知载体/时机仍是独立评估项，见文件底部 `build_gap_report`
的定位说明。

比对两侧信号：
- 侧 A（"该起草"信号）：近 `window_days` 天内、commit 触碰了已知已部署
  场景 CLAUDE.md 的提交。`SCENARIO_RECIPIENTS` 与 `工具-落库sweep.py::
  DEPLOYED_SCENARIO_PREFIXES`（队列 #229）同一白名单精神独立维护一份——
  本批刻意不改 `工具-落库sweep.py`（见 A 批派单件〇节边界），且零依赖
  设计一贯不跨包 import 对方，两处各自维护成本极低。判据同样宁窄勿宽：
  只认"commit 确实改动了该场景 CLAUDE.md"这一可机检事实，不解析 diff
  内容语义（是否真的写了"部署状态"段）——与 #229 同一取舍。
- 侧 B（"已起草"信号）：README 全表任意状态的行（design D5 用词"⏳ 待你审
  及以上状态"——两态语义生效后，表里存在的任意一行必然至少经过
  `⏳ 待你审`，故只需读表即可，不需要额外信源）。

交叉比对：某收信人对应场景近 `window_days` 天内有提交，但该收信人在最早
一次提交日期（含）之后没有任何已起草的跟进信行，即判定为缺口。
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from .readme_table import ReadmeTableError, column_index, iter_rows, split_department_and_name

DEFAULT_WINDOW_DAYS = 7

# 队列 #229 同一白名单精神的独立副本（key＝场景目录前缀，value＝该场景
# 归属的收信人姓名，须与 dispatch.py::KNOWN_RECIPIENT_USERIDS 的姓名口径
# 一致，否则交叉比对时永远匹配不上）。命令中心（AI运营指挥中心）没有
# 单一部门归属的跟进信收信人，刻意不纳入——宁漏勿误报。
SCENARIO_RECIPIENTS: dict[str, str] = {
    "4-数字员工/采购部/SC8-客户订单交期智能承诺/": "姚祖怡",
    "4-数字员工/质量部/QD-B-立项审核门禁/": "陈忱",
    "4-数字员工/财务部/FI2-三单匹配自动对账/": "唐燕萍",
}

_COMMIT_SEP = "\x02"
_FIELD_SEP = "\x1f"


@dataclass
class ScenarioCommitEvent:
    recipient: str
    scenario_prefix: str
    commit_date: date
    commit_sha: str
    subject: str


@dataclass
class MissingDraftGap:
    recipient: str
    scenario_prefix: str
    event_date: date
    commit_sha: str


def find_recent_scenario_commits(
    repo_root: Path, today: date, window_days: int = DEFAULT_WINDOW_DAYS,
) -> list[ScenarioCommitEvent]:
    """扫描近 `window_days` 天内触碰了 `SCENARIO_RECIPIENTS` 任一场景目录
    的提交。一次提交若同时命中多个场景前缀，各自记一条事件——现实中一次
    提交通常只改一个场景，多命中属边界情形，如实全记不做取舍。"""
    since = (today - timedelta(days=window_days)).isoformat()
    result = subprocess.run(
        [
            # 场景目录含中文——git 默认 core.quotepath=true 会把 --name-only
            # 输出的非 ASCII 路径按八进制转义（如 "4-\346\225\260..."），
            # 前缀匹配必然全部落空；显式关闭以拿到原始 UTF-8 路径。
            "git", "-c", "core.quotepath=false", "-C", str(repo_root), "log",
            f"--since={since}T00:00:00",
            "--name-only",
            f"--pretty=format:{_COMMIT_SEP}%H{_FIELD_SEP}%cI{_FIELD_SEP}%s",
        ],
        capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode != 0:
        return []

    events: list[ScenarioCommitEvent] = []
    for block in result.stdout.split(_COMMIT_SEP):
        block = block.strip("\n")
        if not block:
            continue
        lines = block.splitlines()
        header = lines[0]
        parts = header.split(_FIELD_SEP, 2)
        if len(parts) != 3:
            continue
        commit_sha, commit_date_iso, subject = parts
        try:
            commit_date = datetime.fromisoformat(commit_date_iso).date()
        except ValueError:
            continue
        touched = [ln for ln in lines[1:] if ln.strip()]
        for prefix, recipient in SCENARIO_RECIPIENTS.items():
            if any(p.startswith(prefix) for p in touched):
                events.append(
                    ScenarioCommitEvent(
                        recipient=recipient, scenario_prefix=prefix,
                        commit_date=commit_date, commit_sha=commit_sha, subject=subject,
                    )
                )
    return events


def _drafted_recipient_dates(readme_text: str) -> list[tuple[str, date]]:
    """README 全表每一行的（收信人姓名，日期）——不筛状态列，两态语义
    生效后表里存在的任意一行都算"已起草"（见模块 docstring 侧 B）。"""
    try:
        rows = iter_rows(readme_text)
    except ReadmeTableError:
        return []
    if not rows:
        return []

    header_cells = rows[0].header_cells
    recipient_idx = column_index(header_cells, "收信人")
    date_idx = column_index(header_cells, "日期")

    drafted: list[tuple[str, date]] = []
    for row in rows:
        recipient_cell = (
            row.cells[recipient_idx] if recipient_idx is not None and recipient_idx < len(row.cells) else ""
        )
        date_cell = row.cells[date_idx] if date_idx is not None and date_idx < len(row.cells) else ""
        _, name = split_department_and_name(recipient_cell)
        if not name:
            continue
        try:
            row_date = date.fromisoformat(date_cell.strip())
        except ValueError:
            continue
        drafted.append((name, row_date))
    return drafted


def find_missing_drafts(
    readme_text: str, events: list[ScenarioCommitEvent], today: date,
) -> list[MissingDraftGap]:
    """侧 A／侧 B 交叉比对。同一（收信人，场景）在窗口内可能有多次提交——
    只按最早一次判定缺口，避免同一缺口因多次提交被重复报告；`today` 参数
    预留给未来"缺口本身也该有个新鲜度上限"之类的扩展，本次实现暂未使用。
    """
    del today  # 暂未使用，见上方 docstring
    drafted = _drafted_recipient_dates(readme_text)

    earliest_by_scenario: dict[tuple[str, str], ScenarioCommitEvent] = {}
    for event in events:
        key = (event.recipient, event.scenario_prefix)
        current = earliest_by_scenario.get(key)
        if current is None or event.commit_date < current.commit_date:
            earliest_by_scenario[key] = event

    gaps: list[MissingDraftGap] = []
    for (recipient, scenario_prefix), event in earliest_by_scenario.items():
        has_draft = any(
            name == recipient and row_date >= event.commit_date for name, row_date in drafted
        )
        if not has_draft:
            gaps.append(
                MissingDraftGap(
                    recipient=recipient, scenario_prefix=scenario_prefix,
                    event_date=event.commit_date, commit_sha=event.commit_sha,
                )
            )
    return gaps


def build_gap_report(gaps: list[MissingDraftGap], window_days: int) -> str:
    """人可读的检测结果文本，供拆件巡逻「待发信盘点」步骤并入报告。本函数
    只产出文本——发不发、怎么发（私信/群 webhook/纯人工阅读报告）是
    design D5 明确留白的独立评估项，不在本模块范围内。"""
    if not gaps:
        return f"待发信盘点（扩展版，近 {window_days} 天已部署场景 vs 已起草跟进信）：无缺口"
    lines = [
        f"待发信盘点（扩展版，近 {window_days} 天）：发现 {len(gaps)} 处疑似"
        "「该起草而没起草」"
    ]
    for gap in gaps:
        lines.append(
            f"- {gap.recipient}｜场景 {gap.scenario_prefix}｜最早改动 "
            f"{gap.event_date.isoformat()}｜commit {gap.commit_sha[:8]}"
        )
    return "\n".join(lines)
