"""跨域聚合 —— **只读、只在内存**（D3，断言测试 ＝ tasks §1.4）。

## 一句话语义

**逐份读、内存聚合、绝不落盘。** 本文件里没有任何一处 `open(..., "w"/"a")`、
没有 `write_text`、没有 pickle／shelve／sqlite 缓存、没有 `@cache` 落文件的装饰器。

## 为什么这条要落成断言测试而不是写在文档里

D3 的实质是 **OEM 数据隔离红线**：五个域分文件（D2）就是隔离本身，一旦聚合结果
落了盘，那份文件里**同时**有比亚迪线的质量点和采购点 —— 隔离在那一刻就没了，
而磁盘上多出来的那个文件**不会向任何人报告它的存在**。

⚠️ 最容易长出来的形态不是「有人故意导出一份合并表」，而是**性能优化**：
「读五份太慢，缓存一下下次直接读缓存」。缓存文件就是合并落盘产物，
它长得完全不像违规，且写它的人当时只是在优化。⇒ 故 D3 括号里特意写了「含缓存」，
tasks §1.4 的断言测试拦的也正是它。

## 度量脚本（tasks §3.1）应当怎么用本文件

`aggregate()` 返回内存对象，调用方自己算中位数、自己 print。
🔴 **`事实日未知` 的点由 `Snapshot.fact_date_unknown` 单列**，不混入中位数
（SCHEMA §二 `fact_date`）—— 把它当成 0 天或当成不存在，都是在用一个编出来的数
替换一个已知未知。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import Domain, Event, LedgerEvent, Status
from .store import LedgerStore


@dataclass(frozen=True)
class Point:
    """一个口径点在某一时刻的全貌 —— 由它的事件链**推导**出来，不单独存储。

    🔴 **没有 setter、没有 `mark_signed()`**：要改状态只能往台账追加一行，
    然后重新聚合。本类是投影，不是真身。
    """

    id: str
    domain: Domain
    chain: tuple[LedgerEvent, ...]

    @property
    def created(self) -> LedgerEvent:
        """建点行（聚合期已保证存在）。"""
        return self.chain[0]

    @property
    def current(self) -> LedgerEvent:
        """当前态 ＝ 最后一行（SCHEMA §一 引言）。"""
        return self.chain[-1]

    @property
    def status(self) -> Status:
        return self.current.status

    @property
    def scene(self) -> str | None:
        return self.created.scene

    @property
    def proposer(self) -> str | None:
        return self.created.proposer

    @property
    def due(self) -> str | None:
        """最后一次写下的 `due`（后写的覆盖先写的**语义**，但两行都还在文件里）。"""
        for event in reversed(self.chain):
            if event.due is not None:
                return event.due
        return None

    @property
    def carriers(self) -> tuple[str, ...]:
        """全链累积的承接载体，去重保序。空 ⇒ 计入「承接载体缺失」（tasks 6.3 质量型指标）。"""
        seen: dict[str, None] = {}
        for event in self.chain:
            for c in event.carrier:
                seen.setdefault(c, None)
        return tuple(seen)

    @property
    def letters(self) -> tuple[str, ...]:
        """该点被哪些信投影出去（D6：信是视图）。"""
        seen: dict[str, None] = {}
        for event in self.chain:
            for letter in event.letters:
                seen.setdefault(letter, None)
        return tuple(seen)

    def date_of(self, status: Status) -> str | None:
        """某状态**首次**发生的事实日；未到过该状态 ⇒ ``None``。

        取首次而非末次：一个点若曾倒退再前进，度量关心的是它第一次到达那一步的时刻。
        """
        for event in self.chain:
            if event.status is status:
                return event.fact_date
        return None


@dataclass(frozen=True)
class Snapshot:
    """一次跨域聚合的结果 —— **纯内存对象，本类不提供任何 `save()`／`dump()`**。

    🔴 刻意没有 `to_file()`／`write_csv()`：本类一旦有了落盘方法，D3 就变成
    「调用方记得别调它」，而「靠人记得」正是本项目反复吃亏的那一类约束。
    """

    points: dict[str, Point]

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(self.points)

    def by_domain(self, domain: Domain) -> tuple[Point, ...]:
        return tuple(p for p in self.points.values() if p.domain is domain)

    def by_status(self, status: Status) -> tuple[Point, ...]:
        return tuple(p for p in self.points.values() if p.status is status)

    @property
    def domains_present(self) -> frozenset[Domain]:
        """本次聚合实际覆盖到几个域 —— 用来验证「跨域」这件事真的发生了。"""
        return frozenset(p.domain for p in self.points.values())

    @property
    def missing_carrier(self) -> tuple[Point, ...]:
        """承接载体缺失的点 ＝ tasks 6.3 的**质量型价值指标**（首次全量扫描定基线，目标归零）。"""
        return tuple(p for p in self.points.values() if not p.carriers)

    @property
    def fact_date_unknown(self) -> tuple[Point, ...]:
        """建点事实日不可考的点 —— 🔴 度量时**单列**，不混入中位数（SCHEMA §二）。"""
        from .models import FACT_DATE_UNKNOWN

        return tuple(
            p for p in self.points.values() if p.created.fact_date == FACT_DATE_UNKNOWN
        )


def aggregate(source: LedgerStore | Path | str) -> Snapshot:
    """逐份读五个域文件，在内存里聚成 `Snapshot`。

    🔴 **本函数不写任何文件、不建任何目录、不落任何缓存**（D3）。
    tasks §1.4 的断言测试会在调用期间把一切写模式的文件打开拦掉，并对整棵目录树
    做调用前后快照比对 —— 两道都不过就是红。

    :param source: `LedgerStore`，或台账目录路径。
    """
    store = source if isinstance(source, LedgerStore) else LedgerStore(source)

    points: dict[str, Point] = {}
    # 逐域读、逐域收，**不建跨域中间列表**——不是为了省内存，是为了让
    # 「哪一步把两个域的数据放到了一起」在代码里只有下面这一处、看得见。
    for domain in Domain:
        chains: dict[str, list[LedgerEvent]] = {}
        for event in store.read_domain(domain):
            chains.setdefault(event.id, []).append(event)
        for point_id, chain in chains.items():
            if chain[0].event is not Event.CREATE:
                # 首行不是建点 ⇒ 这个点缺「它是什么」，不静默当成正常点算进度量。
                from .errors import LedgerReadError

                raise LedgerReadError(
                    f"{store.path_of(domain)}：id={point_id!r} 的首行是 "
                    f"`{chain[0].event.value}` 而非 `建点`。"
                    f"🔑 缺建点行的点没有 scene／proposer／判例原文，"
                    f"混进度量只会让分母变大、结论变好看。"
                )
            points[point_id] = Point(id=point_id, domain=domain, chain=tuple(chain))

    return Snapshot(points=points)
