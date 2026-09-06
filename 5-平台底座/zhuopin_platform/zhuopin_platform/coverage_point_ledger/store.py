"""台账读写 —— **append-only**，本文件是全包唯一的写盘入口（tasks §1.3）。

## 一句话语义

**只能加行，不能改行、不能删行。** 本类刻意**没有** `update()`／`delete()`／`rewrite()`，
也没有任何以 `"w"` 模式打开域文件的代码 —— 「历史行永不改写」不是靠调用方自觉，
是靠没有那个函数。

## append-only 审计三问（tasks §1.3 括号里那三件）

| 问 | 落在哪个字段 |
|---|---|
| **谁改的** | `by`（会话编号 `OP-…` 或人名） |
| **何时** | `recorded_on`（写入时刻，带 `+08:00`）；与 `fact_date`（事实发生日）**并存**，两者之差 ＝ 补记滞后 |
| **依据哪封回件** | `evidence`（落档件路径）＋ `letters`（`部门#N`） |

🔴 **不另建审计文件**：台账自己就是审计轨（SCHEMA §一 引言）。再建一份就是第二本账，
而本包的立项前提正是「不建第二本账」（D6）。

## 写入期强制的三条（SCHEMA §三 约束 1／2／6）

  1. **同一 `id` 的行序 ＝ 时间序，状态单向；倒退行必须带 `note`**（§三.1）
     —— 倒退不禁止（现实里确有推翻重来），但**必须留因**，否则一次静默倒退
     会让这个点的度量从此对不上，且不产生任何信号。
  2. **`已签认` 缺 `evidence` ⇒ 拒**（§三.2，D5）—— 该条已在 `LedgerEvent`
     构造期抛掉（不变式 ⑸），写入期这里是第二道，防的是绕过构造器直接拼字典的路径。
  3. **`id` 前缀与域文件不符 ⇒ 拒**（§三.6，D2 派生）—— OEM 隔离红线的直接后果：
     写错文件 ＝ 质量域数据落进采购域文件，而 git diff 看上去只是多了一行。

## 🔴 刻意没有做的

  · **不提供 `signoff()` / `auto_signoff()` / `expire_and_sign()` 之类的便捷方法**
    —— 见 `overdue.py`：超期只生成催办草稿，状态保持 `在途`（D5）。
  · **不缓存**：每次读都重新逐份读文件。跨域聚合禁止任何合并落盘产物含缓存（D3），
    而「先只缓存单域、以后顺手合一下」正是那类东西的起点。
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Iterator

from .errors import LedgerReadError, LedgerWriteRejected
from .models import EVIDENCE_REQUIRED_STATUSES, Domain, Event, LedgerEvent, Status

# 仓库内台账目录（相对仓库根）。调用方一般显式传绝对路径；本常量只用于
# 「这条路径在文档里长什么样」的单一出处，避免又出现一处会漂移的副本。
LEDGER_DIR_RELPATH = "6-人才与组织/部门AI专员跟进/口径点台账"


class LedgerStore:
    """一个台账目录的读写句柄。

    用法::

        store = LedgerStore(repo_root / "6-人才与组织/部门AI专员跟进/口径点台账")
        store.append(LedgerEvent(...))          # 自动按 id 前缀落到对应域文件
        events = store.read_domain(Domain.FINANCE)
        chain  = store.chain("FI10-NRV_ESTIMATION_BASIS")
        cur    = store.current_status("FI10-NRV_ESTIMATION_BASIS")
    """

    def __init__(self, ledger_dir: Path | str) -> None:
        self.ledger_dir = Path(ledger_dir)

    # ------------------------------------------------------------------ 路径

    def path_of(self, domain: Domain) -> Path:
        return self.ledger_dir / domain.filename

    def domain_files(self) -> dict[Domain, Path]:
        return {d: self.path_of(d) for d in Domain}

    def initialize(self) -> list[Path]:
        """建出五份**空**域文件（不存在才建），返回全部五条路径。

        🔴 用 `Path.touch()` 而不是 `open("w")`：touch 不写任何内容，
        既建得出骨架，又让「全包只有一处写内容的代码」这条断言（tasks 1.5 的
        `test_写入口唯一` ）保持成立。已存在的文件**绝不截断**。
        """
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for domain in Domain:
            path = self.path_of(domain)
            if not path.exists():
                path.touch()
            paths.append(path)
        return paths

    # ------------------------------------------------------------------ 读

    def read_domain(self, domain: Domain) -> list[LedgerEvent]:
        """逐行读一个域文件。文件不存在 ⇒ 空列表；坏行 ⇒ 抛，**不跳过**。"""
        path = self.path_of(domain)
        if not path.exists():
            return []
        events: list[LedgerEvent] = []
        with path.open("r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                text = line.strip()
                if not text:
                    continue
                try:
                    event = LedgerEvent.from_json_line(text)
                except Exception as exc:
                    raise LedgerReadError(
                        f"{path}:{lineno} 不是合法台账行：{exc}。"
                        f"🔴 本模块不跳过坏行——跳过一行 ＝ 少算一个点，而少算不产生任何信号。"
                    ) from exc
                actual = Domain.for_id(event.id)
                if actual is not domain:
                    raise LedgerReadError(
                        f"{path}:{lineno} id={event.id!r} 前缀属 {actual.label}域，"
                        f"却出现在 {domain.label}域 文件里。"
                        f"🔴 OEM 隔离红线：域由 id 前缀隐含（D2），串域即越界。"
                    )
                events.append(event)
        return events

    def read_all(self) -> dict[Domain, list[LedgerEvent]]:
        """五个域**各自**读回，返回按域分桶的结果 —— 刻意不返回一个合并列表。

        🔴 合并动作留给调用方在内存里做（见 `aggregate.py`），本方法不替它合，
        更不把合并结果写到任何地方（D3）。
        """
        return {domain: self.read_domain(domain) for domain in Domain}

    def chain(self, point_id: str) -> list[LedgerEvent]:
        """一个点的全部事件行，按文件顺序（＝时间顺序）。"""
        domain = Domain.for_id(point_id)
        return [e for e in self.read_domain(domain) if e.id == point_id]

    def current(self, point_id: str) -> LedgerEvent | None:
        """一个点的当前态 ＝ 它的**最后一行**；从未建点则 ``None``。"""
        chain = self.chain(point_id)
        return chain[-1] if chain else None

    def current_status(self, point_id: str) -> Status | None:
        cur = self.current(point_id)
        return cur.status if cur is not None else None

    def iter_events(self) -> Iterator[LedgerEvent]:
        """逐份、逐行地流式读全库 —— 不在内部攒任何合并列表（D3 的读侧形态）。"""
        for domain in Domain:
            yield from self.read_domain(domain)

    # ------------------------------------------------------------------ 写

    def append(self, event: LedgerEvent) -> Path:
        """追加一行，返回被写的域文件路径。**这是全包唯一的写内容入口。**

        写入前按 SCHEMA §三 约束 1／2／6 校验；任一不过即抛 `LedgerWriteRejected`，
        **不写半行、不降级为 warning**。
        """
        domain = self._resolve_domain(event)
        self._check_evidence(event)
        self._check_transition(event)
        path = self.path_of(domain)
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        self._append_line(path, event.to_json_line())
        return path

    def append_many(self, events: Iterable[LedgerEvent]) -> list[Path]:
        """逐条 append。**刻意不做批量原子写**：中途被拒时前面已写的行**保留**
        —— 它们各自都是已经发生过的事实，为了「这一批失败了」而回滚掉真实事件，
        正是本台账要防的那类覆盖式销毁。
        """
        return [self.append(e) for e in events]

    # -------------------------------------------------------------- 写入期校验

    @staticmethod
    def _resolve_domain(event: LedgerEvent) -> Domain:
        """SCHEMA §三.6：`id` 前缀与域文件不符 ⇒ 写入拒绝。"""
        try:
            return Domain.for_id(event.id)
        except Exception as exc:
            raise LedgerWriteRejected(f"写入被拒：{exc}") from exc

    @staticmethod
    def _check_evidence(event: LedgerEvent) -> None:
        """SCHEMA §三.2 ＋ D5 的**第二道**（第一道在 `LedgerEvent` 构造期）。

        🔴 两道都要：构造期那道防「正常路径」，这道防「绕过构造器直接拼对象」的路径
        （如 `dataclasses.replace` 出来的、或从别处反序列化的）。**一道闸只挡一种绕法。**
        """
        if event.status in EVIDENCE_REQUIRED_STATUSES and not event.evidence:
            raise LedgerWriteRejected(
                f"写入被拒：id={event.id!r} status={event.status.value} 缺 evidence。"
                f"🔴 D5：`已签认` 只能由**真实回件**驱动，不存在任何超期自动签认路径。"
            )

    def _check_transition(self, event: LedgerEvent) -> None:
        """SCHEMA §三.1：行序 ＝ 时间序；状态单向；倒退行必须带 `note`。"""
        prev = self.current(event.id)

        if event.event is Event.CREATE:
            if prev is not None:
                raise LedgerWriteRejected(
                    f"写入被拒：id={event.id!r} 已存在建点行，不得重复建点。"
                    f"（同一 id 只能建一次；要改它的定义请写 `补记` 行并留 note）"
                )
            return

        if prev is None:
            raise LedgerWriteRejected(
                f"写入被拒：id={event.id!r} 尚无 `建点` 行，不能直接写 "
                f"`{event.event.value}`。"
                f"🔑 先建点再转态——否则这个点的「它是什么／谁提的／原文是什么」永远缺失。"
            )

        # `已作废` 是链外终态；从它出来算倒退，同样须留因。
        if event.status.rank < prev.status.rank or prev.status is Status.VOIDED:
            if event.status is not Status.VOIDED and not event.note:
                raise LedgerWriteRejected(
                    f"写入被拒：id={event.id!r} 状态由 `{prev.status.value}` 退到 "
                    f"`{event.status.value}`，倒退行必须带 note 留因（SCHEMA §三.1）。"
                    f"🔑 倒退本身不禁止，**无因倒退**才禁止——一次静默倒退之后，"
                    f"这个点的度量从此对不上，且不产生任何信号。"
                )

    @staticmethod
    def _append_line(path: Path, json_line: str) -> None:
        """🔴 **全包唯一一处写文件内容的代码。**

        `newline="\\n"` 定死行尾：Windows 默认会把 ``\\n`` 翻成 ``\\r\\n``，
        而 `.gitignore` 的 `!` 例外、按行 diff、以及「一行一事件」的可比对性
        都建立在行尾唯一之上。

        `tasks 1.5` 的 `test_写入口唯一_全包只有此处写内容` 用 AST 扫描断言
        这个函数是唯一命中点 —— 若将来有人新增第二处写盘，那条测试会红。
        """
        with path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json_line + "\n")
