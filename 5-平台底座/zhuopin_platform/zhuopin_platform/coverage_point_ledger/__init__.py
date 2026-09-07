"""口径点台账 —— **信是视图、点是真身**（openspec 变更包 `coverage-point-ledger`，队列 §一 `#439`）。

## 一句话语义

需求管理的单位由「信」改为「**点**」：每个口径点一条稳定 `id`、一串 **append-only**
事件行；跟进信降为台账的**投影**（D6）。本模块 ＝ 那本账的读写实现（tasks §1.3）
＋ 三条硬约束的执行面（§1.4／§1.5／§1.6）。

## 权威载体

  · **schema 正本** ＝ `6-人才与组织/部门AI专员跟进/口径点台账/SCHEMA.md`（§一 文件、§二 字段、§三 六条约束）
  · **Decisions D1–D9** ＝ `openspec/changes/coverage-point-ledger/design.md`
  · **任务分解** ＝ 同包 `tasks.md`

🔴 本模块与上述任一处冲突 ⇒ **以 SCHEMA.md／design.md 为准，当场改齐代码**，
不在代码注释里另立一套口径（那就是第二本账，正是 D6 要消灭的东西）。

## 四个文件，各管一段

| 文件 | 管什么 | 对应 tasks |
|---|---|---|
| `models.py`    | 一行事件的形状（`LedgerEvent`）＋ 四个枚举；构造期即校验字段契约 | §1.3 |
| `store.py`     | 读写句柄 `LedgerStore`；**全包唯一写入口**，append-only | §1.3 |
| `aggregate.py` | 跨域聚合 `aggregate()` → `Snapshot`；**只读、只在内存** | §1.4（D3） |
| `overdue.py`   | 超期扫描 `scan_overdue()`；**只出催办草稿，不改状态** | §1.5（D5） |
| `lint.py`      | 目录 lint `lint_ledger_dir()`；**不得有子目录** | §1.6（D8） |
| `letters.py`   | 信 ↔ 点 的连接面 `points_for_letter()`；**只读**，回件侧与发送侧共用一份判据 | §2bis（2b.2／2b.3） |
| `cli.py`       | 命令行入口（`transition`／`points-by-letter`）；写只经 `LedgerStore.append_many` | §2bis（2b.1） |

## 三条硬约束（各有一个断言测试盯着，不是只写在这里）

  1. **D3 · 跨域聚合只读**：不产生任何合并落盘产物，**含缓存**。
     ⇒ `tests/test_coverage_point_ledger_aggregate.py`
  2. **D5 · `已签认` 只能由真实回件驱动**：无 `evidence` 的 `已签认` 连对象都造不出来；
     超期只出催办草稿；全包只有一处写内容的代码。
     ⇒ `tests/test_coverage_point_ledger_signoff.py`
  3. **D8 · 台账目录不得有子目录**：`.gitignore` 的 `!` 例外不递归，子目录内 `.jsonl`
     被静默忽略。
     ⇒ `tests/test_coverage_point_ledger_lint.py`

## 用法

    from pathlib import Path
    from zhuopin_platform.coverage_point_ledger import (
        LedgerEvent, LedgerStore, Domain, Event, Status, PointType,
        aggregate, scan_overdue, lint_ledger_dir,
    )

    store = LedgerStore(Path("6-人才与组织/部门AI专员跟进/口径点台账"))
    store.append(LedgerEvent(
        id="FI2-D19-03", event=Event.CREATE, status=Status.ASKING,
        type=PointType.CRITERION, scene="FI2", proposer="唐燕萍",
        fact_date="2026-09-06", recorded_on="2026-09-06T21:30:00+08:00",
        by="OP-0906-Z",
        case_text="…（判例批改法左栏原文）", proposed_ruling="…（右栏原文）",
        carrier=["openspec:coverage-point-ledger"],
    ))

    snap = aggregate(store)                       # 只读，不落盘
    scan_overdue(snap, today=date(2026, 10, 1))   # 只出草稿，不改状态
    lint_ledger_dir(store.ledger_dir)             # D8

## 🔴 刻意**没有**做的（防止后来人顺手加回来）

  · **没有 `update()`／`delete()`／任何改前行的入口** —— 「历史行永不改写」不是纪律，是没有那个函数。
  · **没有 `Snapshot.save()`／`to_csv()`** —— 有了它，D3 就退化成「调用方记得别调」。
  · **没有 `auto_signoff()`／`expire_and_sign()`** —— D5 要的是这条路**不存在**，不是默认关闭。
  · **没有缓存层** —— D3 括号里的「含缓存」拦的正是「读五份太慢，缓存一下」这类优化。
  · **不写 `criteria_signoff` 注册表** —— SCHEMA §四 那条（`id` 形态⑴ 与
    `criteria_signoff` 同名、由台账驱动注册表）**留待两包合审**，定前形态⑴ 只作命名约定，
    本模块**零依赖** `zhuopin_platform.criteria_signoff`。

## ⚠️ 一处已知的 schema 内部不一致（本轮不替它做决定，登记待裁）

SCHEMA §二 字段表写 `carrier` 「≥1（建点**或转态**行）」，但 §二 的最小示例里
第 2、3 行（`转态`）**都没有 `carrier`**。两者不可能同时成立。

本模块的取舍：**两类行都不在写入期强制 ≥1**，两条硬理由（详见 `models.py` 首部）：
⑴ 强制会让 tasks 6.3 的质量型指标「承接载体缺失数量」**结构性恒为 0**，
基线与「目标归零」一起失去意义；⑵ 强制会逼 tasks §2 回溯拆点**编一个载体**
才写得进去，而编出来的载体不产生任何信号。⇒ 载体缺失走**度量**
（`Snapshot.missing_carrier`），不走写入拒绝。
🔴 **这不是裁决**，请在两包合审时一并定死，届时改齐本处与 SCHEMA §二。
"""

from .aggregate import Point, Snapshot, aggregate
from .errors import (
    LedgerContractError,
    LedgerError,
    LedgerLintError,
    LedgerReadError,
    LedgerWriteRejected,
)
from .letters import (
    NON_PROJECTION_REPORT_LINE,
    normalize_letter_ref,
    points_for_letter,
    require_letter_ref,
)
from .lint import LintFinding, LintReport, assert_clean, lint_ledger_dir
from .models import (
    EVIDENCE_REQUIRED_STATUSES,
    FACT_DATE_UNKNOWN,
    Domain,
    Event,
    LedgerEvent,
    PointType,
    Status,
)
from .overdue import SCANNABLE_STATUSES, OverdueDraft, scan_overdue
from .store import LEDGER_DIR_RELPATH, LedgerStore

__all__ = [
    # 数据结构
    "LedgerEvent",
    "Domain",
    "Event",
    "Status",
    "PointType",
    "FACT_DATE_UNKNOWN",
    "EVIDENCE_REQUIRED_STATUSES",
    # 读写
    "LedgerStore",
    "LEDGER_DIR_RELPATH",
    # 聚合（只读）
    "aggregate",
    "Snapshot",
    "Point",
    # 信 ↔ 点（只读，回件侧与发送侧共用）
    "points_for_letter",
    "normalize_letter_ref",
    "require_letter_ref",
    "NON_PROJECTION_REPORT_LINE",
    # 超期（只出草稿）
    "scan_overdue",
    "OverdueDraft",
    "SCANNABLE_STATUSES",
    # lint
    "lint_ledger_dir",
    "assert_clean",
    "LintReport",
    "LintFinding",
    # 异常
    "LedgerError",
    "LedgerContractError",
    "LedgerWriteRejected",
    "LedgerReadError",
    "LedgerLintError",
]
