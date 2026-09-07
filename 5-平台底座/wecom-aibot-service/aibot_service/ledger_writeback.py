"""发送侧 → 口径点台账回写（`coverage-point-ledger` tasks §2bis 的 2b.3）。

## 补的是哪个洞

2026-09-07 `财务部#17` 发出后，台账里那两行 `在途` 是 `OP-0907-L` **手写脚本**补的
——不是机制。手写补的东西，下一封信没人补就没有；而"没补"与"这封信本来就不投影
任何点"在台账里长得一模一样，**不产生任何信号**。⇒ 把这一步挂到发送成功之后。

## 判据：这封信投影了哪些点

两个来源取并集，两者都**必须与台账里真实存在的点求交**（下面第三条是安全网）：

  ⑴ **台账侧已连线** —— 点的 `letters` 里已出现过同一个 `部门#N`（起草期连的线）。
  ⑵ **信侧自陈** —— 信 md 的 frontmatter `口径点:`（若有）或 `配套:` 字段里被反引号
     引起来的 id。真身实例（`财务部#17`）：

         配套: 队列 §一 #474（FI10 场景行）／口径点台账 `FI10-G-07`（…）／…

  ⑶ 🔴 **两个来源的结果一律与 `Snapshot.points` 求交**：`配套:` 是自由文本，里面
     的反引号内容可能是路径、队列号、变更包名。求交之后，"解析出了噪声"最坏的
     后果是没命中，**不会**凭空往台账里写一个不存在的点。

## 只推一步：`待问` → `在途`

  · 当前 `待问` ⇒ 追加一行 `转态 在途`，带 `letters=[部门#N]`。
  · 当前已是 `在途` ⇒ **跳过**。重推同一封信不该产生第二行 `在途`（同一封信发出去
    这件事只发生过一次；真正的第二次发送会带来新的 `部门#N`）。
  · 当前 `已签认` 及以后 ⇒ **跳过**。把一个已签认的点因为一次重推拖回 `在途` 是
    无因倒退，`LedgerStore` 本来就会拒（须带 `note`）——这里不去凑那个 `note`，
    凑出来的理由是假的。

## 🔴 失败一律不上抛

本模块的任何异常都由 `delivery.push_followup` 捕获并记审计，**不影响"信已经发出去了"
这个既成事实**（与 `cc_to_paul`／`cc_group` 完全相同的隔离模式）。台账没写上是可以
事后补的；把一次成功的发送报成失败、让下一班当作"待发"重发，才是不可挽回的。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from zhuopin_platform.coverage_point_ledger import (
    Event,
    LedgerEvent,
    LedgerStore,
    Status,
    aggregate,
    normalize_letter_ref,
    points_for_letter,
)
from zhuopin_platform.coverage_point_ledger.cli import now_recorded_on

#: 台账目录 ＝ 跟进信 README 的**同级**子目录。两者同属
#: `6-人才与组织/部门AI专员跟进/`，故不必去猜仓库根（`__file__` 向上反推在
#: 主工作区／worktree／`.51` 扁平部署三种布局下会解出三个不同答案，队列 #126）。
LEDGER_DIRNAME = "口径点台账"

#: frontmatter 里被反引号引起来的片段。
_BACKTICKED = re.compile(r"`([^`]+)`")
#: 点 id 的形状：`FI10-G-07`／`FI2-D19-03`／`FI10-NRV_ESTIMATION_BASIS`。
#: 🔴 只用来**筛掉明显不是 id 的东西**（路径、句子）；真正的把关是与台账求交。
_POINT_ID_SHAPE = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9_]+)+$")
#: 信侧自陈点 id 的字段，按顺序取第一个存在的。
_POINT_ID_FIELDS = ("口径点", "配套")


@dataclass
class LedgerWritebackResult:
    """一次发送侧回写的结果 —— 供审计与日志如实交代发生了什么。"""

    letter: str | None = None
    transitioned: list[str] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)  # 点 id → 跳过原因
    matched: list[str] = field(default_factory=list)

    @property
    def is_non_projection(self) -> bool:
        """这封信不投影任何点 —— 正常形态，不是故障。"""
        return not self.matched

    def describe(self) -> str:
        if self.letter is None:
            return "未能从 README 行取到信编号，台账未回写"
        if self.is_non_projection:
            return f"{self.letter} 非台账投影，零回写"
        parts = [f"{self.letter} 投影 {len(self.matched)} 个点"]
        if self.transitioned:
            parts.append(f"转 在途 {len(self.transitioned)} 个：{'／'.join(self.transitioned)}")
        if self.skipped:
            parts.append(
                "跳过 " + "／".join(f"{pid}（{why}）" for pid, why in sorted(self.skipped.items()))
            )
        return "；".join(parts)


def resolve_ledger_dir(readme_path: Path) -> Path:
    return Path(readme_path).resolve().parent / LEDGER_DIRNAME


def letter_ref_from_row(header_cells: list[str], cells: list[str]) -> str | None:
    """从 README 行的**编号列**取 `部门#N`；取不到返回 ``None``。

    🔴 **只认表头带「编号」的那一列**（主表 `编号`、补件表 `承接编号`），
    不做"全行扫一遍、找到像编号的就用"的兜底：`主要事项` 列里常常提到别的信
    （"你上一封 `财务部#16` …"），扫出来的可能是**另一封信**，而写错信编号之后
    台账看上去完全正常。宁可这次不写（有审计可查），不可写错一封。
    """
    for header, cell in zip(header_cells, cells):
        if "编号" in header:
            ref = normalize_letter_ref(cell)
            if ref:
                return ref
    return None


def point_ids_declared_in_letter(md_path: Path) -> tuple[str, ...]:
    """信 md 的 frontmatter 自陈的点 id（`口径点:` 优先，否则 `配套:`）。

    解析不出／文件读不了 ⇒ 空元组。本函数**不负责判真伪**，真伪由调用方与台账
    求交决定（见模块文档第 ⑶ 条）。
    """
    try:
        text = Path(md_path).read_text(encoding="utf-8")
    except OSError:
        return ()
    if not text.startswith("---"):
        return ()
    end = text.find("\n---", 3)
    if end == -1:
        return ()
    frontmatter = text[3:end]

    for name in _POINT_ID_FIELDS:
        for line in frontmatter.splitlines():
            key, sep, value = line.partition(":")
            if not sep or key.strip() != name:
                continue
            found = tuple(
                token
                for token in _BACKTICKED.findall(value)
                if _POINT_ID_SHAPE.match(token.strip())
            )
            if found:
                return found
    return ()


def record_letter_sent(
    *,
    readme_path: Path,
    md_path: Path,
    header_cells: list[str],
    cells: list[str],
    by: str,
    sent_on: str | None = None,
) -> LedgerWritebackResult:
    """发送成功后把这封信投影的点由 `待问` 推到 `在途`。

    :param by: 写入者，落台账 `by` 字段（会话编号／脚本名）。
    :param sent_on: 发出日 `YYYY-MM-DD`，落 `fact_date`；不传取今天。
        🔴 **`fact_date` ＝ 发出日，`recorded_on` ＝ 写入时刻**，两者分开取，
        不是同一个值的两种写法（成因见 tasks 3.3 那 12 封被"补转态"覆盖掉真实
        日期的信）。
    :raises: 台账相关异常一律上抛给 `push_followup` 去记审计（见模块文档末条）。
    """
    result = LedgerWritebackResult()
    result.letter = letter_ref_from_row(header_cells, cells)
    if result.letter is None:
        return result

    store = LedgerStore(resolve_ledger_dir(readme_path))
    snapshot = aggregate(store)

    matched = {p.id: p for p in points_for_letter(snapshot, result.letter)}
    for declared in point_ids_declared_in_letter(md_path):
        point = snapshot.points.get(declared.strip())
        if point is not None:  # ⑶ 与台账求交——解析出的噪声在这里被挡住
            matched.setdefault(point.id, point)
    result.matched = sorted(matched)

    fact_date = sent_on or date.today().isoformat()
    to_write: list[LedgerEvent] = []
    for point_id in result.matched:
        point = matched[point_id]
        if point.status is not Status.ASKING:
            result.skipped[point_id] = f"当前 {point.status.value}"
            continue
        to_write.append(
            LedgerEvent(
                id=point_id,
                event=Event.TRANSITION,
                status=Status.IN_FLIGHT,
                fact_date=fact_date,
                recorded_on=now_recorded_on(),
                by=by,
                letters=(result.letter,),
            )
        )

    if to_write:
        store.append_many(to_write)
        result.transitioned = [e.id for e in to_write]
    return result
