"""保供案例处置中心存储（design D6/D7）—— 收割自 supplychain src/delay_case.py。

与 supplychain 延期案例的差异：状态机改为**保供口径**
  催货(expedite) → 协调(coordinate) → 改期/确认(reschedule) → 关闭(closed)
（supplychain 是 采购→PMC→SMT→客户通知，业务语义不同，不复用其枚举）。

D6 去重账本即案例本身：真延期稳定键 = (item_code, fo_id, ship_date)。
  · 新增真延期且无未关闭案例 → 建案（初态 催货）；
  · 已有未关闭案例 → 不重建（幂等）。建案与「是否已推送企微」统一到案例表，天然去重。

红线：案例含真实客户名 → SQLite DB 只落 reports/（git-ignored），绝不入库。
db_path=":memory:" 用于测试（内存库，互不影响）。所有状态变更由服务层串行（低频人工操作）。
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path


class CaseStatus(str, Enum):
    EXPEDITE   = "expedite"     # 催货：催供应商答交/到货
    COORDINATE = "coordinate"   # 协调：内部协调改期/插单/替代料
    RESCHEDULE = "reschedule"   # 改期/确认：供应商新承诺已确认 / 已与客户对齐改期
    CLOSED     = "closed"       # 关闭：料已齐 / 风险消除 / 人工关闭


NEXT_STATUS: dict[CaseStatus, CaseStatus] = {
    CaseStatus.EXPEDITE:   CaseStatus.COORDINATE,
    CaseStatus.COORDINATE: CaseStatus.RESCHEDULE,
    CaseStatus.RESCHEDULE: CaseStatus.CLOSED,
    CaseStatus.CLOSED:     CaseStatus.CLOSED,     # 终态
}

# 各状态处置 SLA（小时）——Paul 2026-06-24 定：催货 24 / 协调 48 / 改期确认 72
SLA_HOURS: dict[CaseStatus, int] = {
    CaseStatus.EXPEDITE:   24,
    CaseStatus.COORDINATE: 48,
    CaseStatus.RESCHEDULE: 72,
    CaseStatus.CLOSED:     999,
}

STATUS_LABEL: dict[CaseStatus, str] = {
    CaseStatus.EXPEDITE:   "📞 催货中",
    CaseStatus.COORDINATE: "🤝 协调中",
    CaseStatus.RESCHEDULE: "📅 改期/确认",
    CaseStatus.CLOSED:     "✅ 已关闭",
}


@dataclass
class SupplyCase:
    """单条保供案例（成品行粒度的真延期处置）。"""
    id:                 int
    case_no:            str          # 显示编号 BG-0001
    item_code:          str          # 成品料号
    fo_id:              str          # 预测订单号
    customer_name:      str
    ship_date:          str          # 计划出货日（稳定键的一部分）
    confirmed_gap_days: int          # 建案时的确定延期天数
    bottleneck_material: str         # 确定瓶颈子件
    status:             CaseStatus
    new_confirmed_date: str          # 供应商新承诺交期 / 改期后出货日（人工填）
    created_at:         str
    updated_at:         str
    resolved_at:        str
    # 瓶颈子件是否"无任何供应商答复"（#223，客户草稿措辞用；与 alert_dispatch._alert_markdown
    # 的 unanswered 判据同源——建案时由 dispatch_new_reds 按 bn in nfd_ids 计算传入，
    # 手动建案默认 False=已答复，可在建案表单勾选覆盖）。默认值仅为兼容旧记录/未知来源，
    # 不代表"已核实答复"——对客措辞层面仍以此字段的实际取值为准，不得脑补。
    bottleneck_unanswered: bool = False

    @property
    def status_label(self) -> str:
        return STATUS_LABEL.get(self.status, self.status.value)

    @property
    def sla_hours(self) -> int:
        return SLA_HOURS[self.status]

    @property
    def hours_since_update(self) -> float:
        return (datetime.now() - datetime.fromisoformat(self.updated_at)).total_seconds() / 3600

    @property
    def is_overdue_sla(self) -> bool:
        return self.is_open and self.hours_since_update > self.sla_hours

    @property
    def is_open(self) -> bool:
        return self.status != CaseStatus.CLOSED


@dataclass
class CaseEvent:
    """案例操作历史（append-only）。"""
    id:          int
    case_id:     int
    action:      str   # created / advanced / closed / draft / note
    actor:       str
    note:        str
    from_status: str
    to_status:   str
    created_at:  str


class CaseStore:
    """保供案例 SQLite 存储与状态机操作。"""

    def __init__(self, db_path: str | Path = ":memory:"):
        self._conn = self._init_db(db_path)

    def _init_db(self, db_path) -> sqlite3.Connection:
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False：waitress 多线程下可共用连接；写操作经服务层串行
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS supply_cases (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                case_no             TEXT    UNIQUE NOT NULL,
                item_code           TEXT    NOT NULL,
                fo_id               TEXT    NOT NULL DEFAULT '',
                customer_name       TEXT    NOT NULL DEFAULT '',
                ship_date           TEXT    NOT NULL DEFAULT '',
                confirmed_gap_days  INTEGER NOT NULL DEFAULT 0,
                bottleneck_material TEXT    NOT NULL DEFAULT '',
                status              TEXT    NOT NULL DEFAULT 'expedite',
                new_confirmed_date  TEXT    NOT NULL DEFAULT '',
                created_at          TEXT    NOT NULL,
                updated_at          TEXT    NOT NULL,
                resolved_at         TEXT    NOT NULL DEFAULT '',
                bottleneck_unanswered INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS supply_case_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id     INTEGER NOT NULL REFERENCES supply_cases(id),
                action      TEXT    NOT NULL,
                actor       TEXT    NOT NULL DEFAULT '',
                note        TEXT    NOT NULL DEFAULT '',
                from_status TEXT    NOT NULL DEFAULT '',
                to_status   TEXT    NOT NULL DEFAULT '',
                created_at  TEXT    NOT NULL
            );
        """)
        # #223：为已存在的旧库（CREATE TABLE IF NOT EXISTS 对已有表不生效）补迁移新列，
        # 幂等——真实部署库（reports/*.db，gitignore）可能已有历史行，不能假设总是新库。
        existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(supply_cases)")}
        if "bottleneck_unanswered" not in existing_cols:
            conn.execute(
                "ALTER TABLE supply_cases ADD COLUMN bottleneck_unanswered INTEGER NOT NULL DEFAULT 0")
        conn.commit()
        return conn

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _row_to_case(self, row: sqlite3.Row) -> SupplyCase:
        return SupplyCase(
            id=row["id"], case_no=row["case_no"], item_code=row["item_code"],
            fo_id=row["fo_id"], customer_name=row["customer_name"],
            ship_date=row["ship_date"], confirmed_gap_days=row["confirmed_gap_days"],
            bottleneck_material=row["bottleneck_material"],
            status=CaseStatus(row["status"]), new_confirmed_date=row["new_confirmed_date"],
            created_at=row["created_at"], updated_at=row["updated_at"],
            resolved_at=row["resolved_at"],
            bottleneck_unanswered=bool(row["bottleneck_unanswered"]),
        )

    def _log_event(self, case_id: int, action: str, actor: str, note: str,
                   from_status: str, to_status: str, now: str) -> None:
        self._conn.execute(
            """INSERT INTO supply_case_events
               (case_id, action, actor, note, from_status, to_status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (case_id, action, actor, note, from_status, to_status, now))

    # ── 去重键查询（D6）──────────────────────────────────────────────────────
    def find_open_by_key(self, item_code: str, fo_id: str, ship_date: str) -> SupplyCase | None:
        """按稳定键 (item_code, fo_id, ship_date) 找未关闭案例（去重账本）。"""
        row = self._conn.execute(
            """SELECT * FROM supply_cases
               WHERE item_code=? AND fo_id=? AND ship_date=? AND status != 'closed'""",
            (item_code, fo_id, ship_date)).fetchone()
        return self._row_to_case(row) if row else None

    # ── 建案 ─────────────────────────────────────────────────────────────────
    def create_case(self, *, item_code: str, fo_id: str, customer_name: str,
                    ship_date: str, confirmed_gap_days: int = 0,
                    bottleneck_material: str = "", bottleneck_unanswered: bool = False,
                    actor: str = "系统",
                    note: str = "自动检测到真延期", manual: bool = False) -> tuple[SupplyCase, bool]:
        """建案（幂等）。返回 (案例, 是否新建)。

        同稳定键已有未关闭案例 → 返回 (已有案例, False)，不重建（去重核心）。
        manual=True 仅改建案事件文案（手动录入），状态机一致。
        bottleneck_unanswered：瓶颈子件是否无任何供应商答复（#223，驱动对客草稿措辞）。
        """
        existing = self.find_open_by_key(item_code, fo_id, ship_date)
        if existing:
            return existing, False

        now = self._now()
        max_id = self._conn.execute("SELECT MAX(id) FROM supply_cases").fetchone()[0] or 0
        case_no = f"BG-{max_id + 1:04d}"
        cur = self._conn.execute(
            """INSERT INTO supply_cases
               (case_no, item_code, fo_id, customer_name, ship_date, confirmed_gap_days,
                bottleneck_material, status, new_confirmed_date, created_at, updated_at,
                resolved_at, bottleneck_unanswered)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?, '', ?)""",
            (case_no, item_code, fo_id, customer_name, ship_date, confirmed_gap_days,
             bottleneck_material, CaseStatus.EXPEDITE.value, now, now,
             int(bottleneck_unanswered)))
        self._conn.commit()
        case_id = cur.lastrowid
        self._log_event(case_id, "created", actor,
                        "手动建案" if manual else note, "", CaseStatus.EXPEDITE.value, now)
        self._conn.commit()
        return self.get_case(case_id), True

    # ── 状态推进 / 关闭 ────────────────────────────────────────────────────────
    def advance_status(self, case_id: int, *, actor: str, note: str = "",
                       new_confirmed_date: str = "") -> SupplyCase:
        """推进到下一合法状态。已关闭不可推进（ValueError）。"""
        row = self._conn.execute("SELECT * FROM supply_cases WHERE id=?", (case_id,)).fetchone()
        if not row:
            raise ValueError(f"案例 {case_id} 不存在")
        current = CaseStatus(row["status"])
        if current == CaseStatus.CLOSED:
            raise ValueError(f"案例 {row['case_no']} 已关闭，不可再推进")
        nxt = NEXT_STATUS[current]
        now = self._now()
        if new_confirmed_date:
            self._conn.execute(
                "UPDATE supply_cases SET status=?, updated_at=?, new_confirmed_date=? WHERE id=?",
                (nxt.value, now, new_confirmed_date, case_id))
        else:
            self._conn.execute(
                "UPDATE supply_cases SET status=?, updated_at=? WHERE id=?",
                (nxt.value, now, case_id))
        self._log_event(case_id, "advanced", actor, note, current.value, nxt.value, now)
        self._conn.commit()
        return self.get_case(case_id)

    def resolve_case(self, case_id: int, *, actor: str, note: str = "") -> SupplyCase:
        """直接关闭案例（料已齐/风险消除/人工关闭，可跳过中间态）。"""
        row = self._conn.execute("SELECT * FROM supply_cases WHERE id=?", (case_id,)).fetchone()
        if not row:
            raise ValueError(f"案例 {case_id} 不存在")
        now = self._now()
        current = CaseStatus(row["status"])
        self._conn.execute(
            "UPDATE supply_cases SET status=?, updated_at=?, resolved_at=? WHERE id=?",
            (CaseStatus.CLOSED.value, now, now, case_id))
        self._log_event(case_id, "closed", actor, note, current.value, CaseStatus.CLOSED.value, now)
        self._conn.commit()
        return self.get_case(case_id)

    # ── 查询 ─────────────────────────────────────────────────────────────────
    def get_case(self, case_id: int) -> SupplyCase | None:
        row = self._conn.execute("SELECT * FROM supply_cases WHERE id=?", (case_id,)).fetchone()
        return self._row_to_case(row) if row else None

    def get_open_cases(self) -> list[SupplyCase]:
        rows = self._conn.execute(
            "SELECT * FROM supply_cases WHERE status != 'closed' ORDER BY updated_at DESC").fetchall()
        return [self._row_to_case(r) for r in rows]

    def get_stale_cases(self) -> list[SupplyCase]:
        return [c for c in self.get_open_cases() if c.is_overdue_sla]

    def get_all_cases(self, *, include_closed: bool = False) -> list[SupplyCase]:
        sql = ("SELECT * FROM supply_cases ORDER BY updated_at DESC" if include_closed
               else "SELECT * FROM supply_cases WHERE status != 'closed' ORDER BY updated_at DESC")
        return [self._row_to_case(r) for r in self._conn.execute(sql).fetchall()]

    def get_events(self, case_id: int) -> list[CaseEvent]:
        rows = self._conn.execute(
            "SELECT * FROM supply_case_events WHERE case_id=? ORDER BY created_at, id",
            (case_id,)).fetchall()
        return [CaseEvent(id=r["id"], case_id=r["case_id"], action=r["action"],
                          actor=r["actor"], note=r["note"], from_status=r["from_status"],
                          to_status=r["to_status"], created_at=r["created_at"]) for r in rows]

    def add_note(self, case_id: int, *, actor: str, note: str) -> None:
        """追加一条备注事件（不改状态，如「已生成草稿」）。"""
        self._log_event(case_id, "note", actor, note, "", "", self._now())
        self._conn.commit()
