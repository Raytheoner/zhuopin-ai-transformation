"""确认层 —— 发布签认记录（spec: sc2-anomaly-review）。

🔴 ━━━ **本模块已由「推送闸门」降为「事后签认记录」（2026-08-25）** ━━━

**原设计**：这道门曾是 SC2 保持 L3 的唯一结构性保证——周报非经人工确认不得推送。

**现状**：队列 §四 `#89` 已拍板（Shao Peishen 2026-08-22 答 `OP0822A` 定夺 1 选 (a)）
**取消确认发布前置**，周五 20:00 自动生成并自动推群；连带定性亦已拍板：
**「SC2 周报不属 IATF 需签认输出」**。⇒ 推送侧不再调用本模块做前置校验，
原 `ensure_publishable()` / `UnconfirmedError` 已随之删除。

⚠️ **删掉的是「闸」，不是「签认能力」**。`confirm()` 与页面上那个按钮都还在，
它现在记录的是「**有人事后看过并签了字**」——仍写 `AuditLogger`、仍强制要求确认人。
**若日后要把闸装回去**（拍板原话是「有必要以后再改」），落点只有一处：
在 `notify.push()` 里恢复一次「该期是否已 CONFIRMED」的判断。故意让它只有一处，
免得下次改回来时漏掉某条旁路。

🔴 **可逆性有边界，此处留痕**：代码随时能改回去，**但按自动发布跑过的那几周，
审计记录里就是没有人工签认，事后补不回来**。改回去只对未来生效。

**仍然成立的两条设计封堵**（与闸无关，故不随之取消）：
- **重新生成会把已确认退回待确认**——内容变了，先前那次签认就不再适用于新数字；
  否则等于拿旧签认给新内容背书（#228 那族教训的同构形态）。
- **状态落盘而非只存内存**——一次重启不该把「已确认」抹掉，也不该让已推送的
  再推一遍（`mark_pushed` 现在是推送幂等的唯一依靠，比过去更要紧）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from . import config
from .models import WeeklyReport


class PublishState(str, Enum):
    PENDING = "pending"          # 已生成，待人工确认
    CONFIRMED = "confirmed"      # 已确认，可推送


@dataclass
class _Entry:
    state: str
    fingerprint: str
    confirmed_by: str = ""
    confirmed_at: str = ""
    snapshot_id: str = ""
    pushed: bool = False
    anomalies: tuple[str, ...] = ()


def _fingerprint(report: WeeklyReport) -> str:
    """周报内容指纹——用于判断「重新生成后内容是否变了」。"""
    import hashlib

    payload = json.dumps(
        [[m.key, m.current.value, m.previous.value, m.month_ago.value, m.anomaly]
         for m in report.metrics],
        ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class ReviewStore:
    """确认状态存储（JSON 落 `reports/`，跨进程可见）。

    每次读写都直接过盘，不缓存——本场景是周级低频操作，正确性远比性能重要，
    且「进程内缓存 + 多进程」正是确认状态最容易失真的地方。
    """

    def __init__(self, path=None):
        self._path = path or config.publish_state_path()

    def _read(self) -> dict[str, dict[str, Any]]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _write(self, data: dict[str, dict[str, Any]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                              encoding="utf-8")

    def get(self, period: str) -> _Entry | None:
        raw = self._read().get(period)
        if raw is None:
            return None
        return _Entry(
            state=raw.get("state", PublishState.PENDING.value),
            fingerprint=raw.get("fingerprint", ""),
            confirmed_by=raw.get("confirmed_by", ""),
            confirmed_at=raw.get("confirmed_at", ""),
            snapshot_id=raw.get("snapshot_id", ""),
            pushed=bool(raw.get("pushed", False)),
            anomalies=tuple(raw.get("anomalies", ())),
        )

    def register(self, report: WeeklyReport) -> None:
        """登记一期新生成的周报。

        🔴 内容指纹变了即**退回待确认**并清掉已推送标记：新数字必须重新过人眼。
        指纹未变则保留原状态——同一份内容重复生成不该反复要求确认。
        """
        data = self._read()
        fp = _fingerprint(report)
        prev = data.get(report.period)
        if prev and prev.get("fingerprint") == fp:
            return
        data[report.period] = {
            "state": PublishState.PENDING.value,
            "fingerprint": fp,
            "anomalies": [m.key for m in report.anomalies],
            "pushed": False,
        }
        self._write(data)

    def set_confirmed(self, period: str, *, confirmed_by: str,
                      snapshot_id: str, at: str) -> dict[str, Any]:
        data = self._read()
        entry = data.setdefault(period, {"state": PublishState.PENDING.value,
                                         "fingerprint": "", "anomalies": []})
        entry.update({
            "state": PublishState.CONFIRMED.value,
            "confirmed_by": confirmed_by,
            "confirmed_at": at,
            "snapshot_id": snapshot_id,
        })
        self._write(data)
        return dict(entry)

    def mark_pushed(self, period: str) -> bool:
        """标记已推送。返回 True 表示本次是首次推送、应当真的发出去。

        重启后再调返回 False——这正是「重启不得重复推送」那条要求的落点。
        """
        data = self._read()
        entry = data.get(period)
        if entry is None or entry.get("pushed"):
            return False
        entry["pushed"] = True
        self._write(data)
        return True


def status_of(store: ReviewStore, period: str) -> PublishState:
    entry = store.get(period)
    if entry is None:
        return PublishState.PENDING
    return PublishState(entry.state)


def _audit_logger():
    from zhuopin_platform.audit.logger import AuditLogger

    return AuditLogger.jsonl(config.audit_path())


def confirm(store: ReviewStore, period: str, *, confirmed_by: str,
            snapshot_id: str, audit=None) -> dict[str, Any]:
    """人工确认发布。

    :param confirmed_by: 确认人。**必填且不得为空**——IATF 要求可归责，一次
        没有主语的确认在审核时等于没有确认。
    :returns: 本次确认记录（含异常列表）。

    异常的存在**不阻断**确认：真实业务波动被标为异常是常态，确认人有权在看到
    标记后仍确认发布；但**该判断必须被记录**，故异常列表一并写进审计。
    """
    who = (confirmed_by or "").strip()
    if not who:
        raise ValueError("确认人不得为空（IATF 可归责要求）")

    entry = store.get(period)
    anomalies = list(entry.anomalies) if entry else []
    at = datetime.now().astimezone().isoformat(timespec="seconds")

    from zhuopin_platform.audit.events import AuditEvent

    (audit or _audit_logger()).record(AuditEvent(
        scenario="SC2",
        action="weekly_report_publish_confirm",
        evaluator=who,
        automation_level="L3",
        decision={
            "period": period,
            "snapshot_id": snapshot_id,
            "anomalies": anomalies,
        },
        data_sources={"snapshot": snapshot_id},
        timestamp=at,
    ))
    rec = store.set_confirmed(period, confirmed_by=who,
                              snapshot_id=snapshot_id, at=at)
    rec["anomalies"] = anomalies
    return rec
