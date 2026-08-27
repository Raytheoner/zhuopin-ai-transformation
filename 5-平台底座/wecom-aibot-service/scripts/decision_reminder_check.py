"""需 Shao Peishen 决策项/待领 opener 主动提醒——一次性触发工具（队列 #172，
2026-08-10 起同进程并入队列 #312 可 Open 池提醒）。

两条互补的提醒共用本脚本、共用同一次 aibot 连接，各自独立判定/独立状态
文件/独立发送与否（互不阻塞——一条有内容另一条没有也照常各自处理）：

  **① 决策提醒（队列 #172，见 `aibot_service.decision_reminder` 模块
  docstring）**——管"待你定夺"：拆件巡逻收工时调用本脚本一次，新登的
  §四 项/新增的 P0/P1 待领行因从未见过而立即触发（事件驱动即时提醒）；
  独立 Windows 计划任务每日固定时点再调用一次，捕捉"已过截止"/"待领
  超期"的升级提醒（1/3/7 天递减间隔，同一天两层都调用也不会重复提醒）。

  **② 可 Open 池提醒（队列 #312，见 `aibot_service.open_pool_reminder`
  模块 docstring）**——管"待你开工"：§一 状态字段为 `[S:open]` 的行即
  "可立即开工"，指纹（当前可 Open 行号集合）出现新行号才推一次，池子
  缩小或维持不变均静默（队列 #147「狼来了」教训，不做"存在即提醒"）。
  🔴 取数覆盖**两份**物理队列文件（#315 拆分后机制环境／业务场景各一
  份），2026-08-19 前只读了机制环境那一份 ⇒ 采购／财务／质量三域从未
  进过池（队列 #312 缺口一）。

  **③ 可 Open 池陈化催办（队列 #312 缺口二，2026-08-19）**——管"你有活
  一直没开"：某可 Open 行的 git 末次触碰时间超过 7 天且距上次催办已满
  7 天，推一条催办。与 ② 分别计指纹、独立成一条消息、audit action 名
  单独区分——② 判"池里出现了以前没有的活"，③ 判"某条活一直没被领走"，
  用其一取代另一个都会漏掉另一半。

**两者为何同进程（而非各开一个脚本/各注册一个定时任务）**：队列 #312
行内设计明确"两者互补，可同进程"——巡逻侧的调用点在拆件巡逻定时任务
prompt（仓库外，`C:\\Users\\Paul Shao\\Claude\\Scheduled\\huijian-chaijian-
patrol\\SKILL.md`），本脚本无法从仓库内触达，需 Cowork 侧改动该 prompt
本体才能新增一个调用点；把 ② 并进本脚本本体，巡逻/每日定时任务侧维持
"调用本脚本一次"不变，零新增仓库外改动面，同时省下一次多余的 WS 连接
握手。

用法：
  python scripts/decision_reminder_check.py
  python scripts/decision_reminder_check.py --dry-run   # 只打印将发送的内容，不实际发送/不落状态文件
  python scripts/decision_reminder_check.py --ack-item '§四#47' --note '…'   # 确认某项已闭环
  python scripts/decision_reminder_check.py --list-acks                       # 看现有确认

**`--ack-item`（`OP-0828-B`，判据关不掉的修法）**——判据只读截止列，而队列行守
「历史记录不追改」⇒ 一行处置完了仍会被永远报下去（实测 `§四 #47` 已写
「本行处置完毕」、截止列 `**已收口 2026-08-03**`，仍每轮命中）。本参数记一条
带**判定依据**与**内容指纹**的确认，指纹只盖判据格（§四＝截止列／§一＝状态列），
**该格一被改写即自动失效、恢复告警**——它不是永久白名单。详见
`aibot_service.decision_reminder` 模块 docstring。**它仍要人跑一条命令，
不是"机制守"，不夸大。**

环境变量（同 `push_followup_letter.py`/`alert_webhook.py` 既有约定）：
  WECOM_AIBOT_QUEUE_PATH   可选，仓库根解析锚点，默认 <本 checkout 根>/
                           1-转型规划/0-全景路线图/跨桌任务队列.md
  WECOM_AIBOT_REPO_ROOT    可选，显式指定仓库根，绕开动态 git 解析
  WECOM_AIBOT_AUDIT_PATH   可选，直接指定审计文件路径
  WECOM_AIBOT_DECISION_ACK_PATH  可选，指纹确认文件路径（默认服务目录下
                           `reports/decision_reminder_ack.json`；便于只读验证时另指）
  WECOM_WEBHOOK_URL        可选，主通道（智能机器人私信）失败时的兜底群 webhook
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

SERVICE_DIR = Path(__file__).resolve().parent.parent
NAIVE_REPO_ROOT = SERVICE_DIR.parents[1]  # 5-平台底座/wecom-aibot-service -> 本 checkout 自身的根

# —— 平台底座路径引导（队列 #345 收拢；唯一被允许的样板，实现见
# `5-平台底座/zhuopin_platform/zhuopin_platform/bootstrap.py`）。必须放在本文件任何
# zhuopin_platform / 场景包 import 之前。下方五行只负责让 bootstrap 自身可被 import、
# 不含任何判断分支；开发机 monorepo 与 `.51` 扁平部署两种布局的分歧由 ensure_paths 处理。——
_HERE = Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        sys.path.insert(0, str(_p / "5-平台底座" / "zhuopin_platform"))
        break
from zhuopin_platform.bootstrap import ensure_paths  # noqa: E402
ensure_paths(__file__, SERVICE_DIR)  # noqa: E402

from zhuopin_platform.audit import AuditLogger  # noqa: E402
from zhuopin_platform.shared_tools.notifiers import wecom  # noqa: E402
from zhuopin_platform.shared_tools.notifiers.wecom_aibot import AibotConnector  # noqa: E402
from zhuopin_platform.shared_tools.secrets import EnvSecretsProvider  # noqa: E402

from aibot_service.connection import BOTID_KEY, SECRET_KEY  # noqa: E402
from aibot_service.constants import PAUL_USERID  # noqa: E402
from aibot_service.decision_reminder import (  # noqa: E402
    ACK_COMMAND_HINT,
    DEFAULT_ACK_REL,
    DEFAULT_STATE_REL,
    ackable_state,
    evaluate,
    format_digest_message,
    load_acks,
    record_ack,
    save_acks,
    send_decision_reminder,
)
from aibot_service.decision_reminder import load_state as load_decision_state  # noqa: E402
from aibot_service.decision_reminder import save_state as save_decision_state  # noqa: E402
from aibot_service.open_pool_reminder import (  # noqa: E402
    build_pool_items_from_repo,
    compute_new_ids,
    compute_stale_candidates,
    format_pool_reminder_message,
    format_stale_reminder_message,
    last_touched_at,
    new_known_state,
    new_stale_state,
    send_open_pool_reminder,
)
from aibot_service.open_pool_reminder import load_state as load_pool_state  # noqa: E402
from aibot_service.open_pool_reminder import save_state as save_pool_state  # noqa: E402
from aibot_service.queue_edit_lock import AIBOT_LOCK_WHO, SubprocessQueueEditLock  # noqa: E402
from aibot_service.queue_lock_pending import flush_pending_queue_appends  # noqa: E402
from aibot_service.repo_paths import (  # noqa: E402
    DEFAULT_QUEUE_RELATIVE_PATH,
    resolve_audit_path,
    resolve_default_queue_anchor,
    resolve_open_pool_reminder_state_path,
    resolve_pending_queue_appends_path,
    resolve_pending_queue_lock_appends_path,
    resolve_repo_root,
)

QUEUE_REL = DEFAULT_QUEUE_RELATIVE_PATH


def _resolve_ack_path(resolved_repo_root: Path) -> Path:
    """指纹确认文件位置（`OP-0828-B`）。环境变量可覆盖，便于只读验证时另指。"""
    override = os.environ.get("WECOM_AIBOT_DECISION_ACK_PATH")
    if override:
        return Path(override)
    return resolved_repo_root / "5-平台底座" / "wecom-aibot-service" / DEFAULT_ACK_REL


def _resolve_paths() -> tuple[Path, Path]:
    """(仓库根, 队列文件)——`--ack-item`/`--list-acks` 与主流程共用同一套解析，
    绝不各写一份（判据格取自哪一份队列，两条路径必须一致）。"""
    queue_anchor = resolve_default_queue_anchor(NAIVE_REPO_ROOT, QUEUE_REL)
    resolved_repo_root = resolve_repo_root(queue_anchor, fallback=NAIVE_REPO_ROOT)
    return resolved_repo_root, resolved_repo_root / QUEUE_REL


def cmd_ack_item(key: str, note: str) -> int:
    """记一次「我核过了，这一项确已闭环」。

    与 `工具-未闭合产出扫描.py::cmd_ack_form1` 逐条对齐：`--note` 不得为空；
    **算不出指纹就拒绝记录**——不落一条没有指纹的确认，那种确认永远不会
    失效，正是本机制要避免的白名单。
    """
    resolved_repo_root, queue_path = _resolve_paths()
    if not queue_path.exists():
        print(f"[SKIP] 队列文件不存在：{queue_path}", file=sys.stderr)
        return 1
    queue_text = queue_path.read_text(encoding="utf-8")
    ack_path = _resolve_ack_path(resolved_repo_root)
    acks = load_acks(ack_path)

    # 🔴 用 `ackable_state()`（把所有行都当见过的），**不是空状态、也不是生产
    # 状态**：空状态会让一个截止日还在未来的行也能被 ack，那之后它到期时指纹
    # 没变、永远不会响 ＝ 永久白名单；生产状态则会因"本轮不到期"把一条确实在
    # 超期的行藏起来、算不出指纹。理由见 `ackable_state` docstring。
    today = date.today()
    result = evaluate(queue_text, today, ackable_state(queue_text, today), acks=acks)
    match = next((i for i in result.items if i.key == key), None)
    already = next((s for s in result.suppressed if s.key == key), None)
    if match is None and already is not None:
        print(f"· 无需重复确认：{key} 当前指纹 {already.fingerprint} 与已有确认一致，本轮本就静默。")
        return 0
    if match is None:
        print(f"✗ 当前提醒候选里没有 `{key}`，拒绝记录确认——"
              "无法计算指纹，且一条确认不该指向一个不存在的候选。")
        print("  现存候选：" + ("；".join(i.key for i in result.items) or "（无）"))
        return 1
    try:
        acks = record_ack(acks, key, fingerprint=match.fingerprint, note=note)
    except ValueError as exc:
        print(f"✗ {exc}")
        return 1
    save_acks(ack_path, acks)
    print(f"✓ 已记录确认：{key}（判据格指纹 {match.fingerprint}）。")
    print("  指纹未变期间本项不再提醒；**该行判据格一被改写**"
          "（§四＝截止列／§一＝状态列）即自动失效、恢复告警。")
    print(f"  确认落在 `{ack_path}`（本机状态、不入库）。")
    print("  ⚠️ 它不替你去队列里补那个 ✅ —— 队列里这一行看起来仍是未闭合的。")
    return 0


def cmd_list_acks() -> int:
    resolved_repo_root, queue_path = _resolve_paths()
    ack_path = _resolve_ack_path(resolved_repo_root)
    acks = load_acks(ack_path)
    if not acks:
        print(f"（无确认记录：{ack_path}）")
        return 0
    queue_text = queue_path.read_text(encoding="utf-8") if queue_path.exists() else ""
    today = date.today()
    result = (evaluate(queue_text, today, ackable_state(queue_text, today), acks=acks)
              if queue_text else None)
    live_suppressed = {s.key for s in result.suppressed} if result else set()
    stale = set(result.stale_acks) if result else set()
    print(f"确认记录 {len(acks)} 条（{ack_path}）：")
    for key, entry in sorted(acks.items()):
        if key in stale:
            state = "⚠️ 对不上任何现存行"
        elif key in live_suppressed:
            state = "✅ 生效中（指纹未变）"
        else:
            state = "🔁 指纹已变或本轮非候选"
        print(f"- {key}｜{state}｜指纹 {entry.get('fingerprint','?')}"
              f"｜{entry.get('acked_at','?')}\n    依据：{entry.get('note','')}")
    return 0


async def _flush_pending_lock_appends_second_carrier(
    resolved_repo_root: Path, queue_path: Path, audit: AuditLogger, fallback_send,
) -> None:
    """队列 #192-A 第二道载体（主载体＝`工具-落库sweep.py` 每小时子进程调用，
    见其 `_flush_pending_lock_appends`）——两处各调一次，互为冗余，成本近乎
    为零；`#199` 的 `0x800710E0` 间歇性失败正说明单一载体不可靠。

    刻意不建 WS 长连接（`connector=None`，同独立脚本
    `flush_pending_lock_appends.py` 用法）——本函数只在决策提醒判定之前
    调用一次，不因新增这一步而让原有决策提醒逻辑多等一次连接握手。失败
    只降级记 audit（`flush_pending_queue_appends` 内部已有），不向上抛出，
    不得影响本脚本原有的决策提醒判定与发送。"""
    pending_lock_path = Path(
        os.environ.get(
            "WECOM_AIBOT_PENDING_LOCK_PATH", resolve_pending_queue_lock_appends_path(resolved_repo_root)
        )
    )
    pending_queue_appends_path = Path(
        os.environ.get(
            "WECOM_AIBOT_PENDING_APPENDS_PATH", resolve_pending_queue_appends_path(resolved_repo_root)
        )
    )

    def _lock_factory():
        return SubprocessQueueEditLock(
            resolved_repo_root, queue_path, who=AIBOT_LOCK_WHO, note="每日提醒兜底补录",
        )

    try:
        flushed = await flush_pending_queue_appends(
            pending_path=pending_lock_path,
            queue_path=queue_path,
            repo_root=resolved_repo_root,
            audit=audit,
            lock_factory=_lock_factory,
            connector=None,
            recipient=PAUL_USERID,
            fallback_send=fallback_send,
            git_sync_pending_path=pending_queue_appends_path,
        )
    except Exception as exc:  # noqa: BLE001 —— 第二道载体失败不应影响本脚本主流程
        print(f"[WARN] pending_queue_lock_appends.jsonl flush 失败（不影响决策提醒本身）：{exc}", file=sys.stderr)
        return
    if flushed:
        print(f"[OK] 兜底 flush：已补录 {flushed} 条")


async def _run(dry_run: bool) -> int:
    load_dotenv(SERVICE_DIR.parent / ".env")

    queue_anchor = resolve_default_queue_anchor(NAIVE_REPO_ROOT, QUEUE_REL)
    resolved_repo_root = resolve_repo_root(queue_anchor, fallback=NAIVE_REPO_ROOT)
    queue_path = resolved_repo_root / QUEUE_REL
    decision_state_path = resolved_repo_root / "5-平台底座" / "wecom-aibot-service" / DEFAULT_STATE_REL
    pool_state_path = resolve_open_pool_reminder_state_path(resolved_repo_root)

    if not queue_path.exists():
        print(f"[SKIP] 队列文件不存在：{queue_path}", file=sys.stderr)
        return 1

    audit_path = Path(
        os.environ.get("WECOM_AIBOT_AUDIT_PATH", resolve_audit_path(resolved_repo_root))
    )
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit = AuditLogger.jsonl(audit_path)

    webhook_url = os.environ.get("WECOM_WEBHOOK_URL")
    fallback_send = (
        (lambda text: wecom.send_text(webhook_url, f"⚠️ {text}")) if webhook_url else None
    )

    # 队列 #192-A 第二道载体：dry-run 不做真实动作（会真实 commit/push），
    # 与主载体 sweep 的 dry-run 处理方式一致。
    if not dry_run:
        await _flush_pending_lock_appends_second_carrier(
            resolved_repo_root, queue_path, audit, fallback_send,
        )

    queue_text = queue_path.read_text(encoding="utf-8")
    today = date.today()

    # ① 队列 #172：需 Shao Peishen 决策项/待领 opener 主动提醒。
    #    `OP-0828-B`：叠加指纹确认——已核实闭环的项本轮静默，判据格一改即恢复。
    decision_state = load_decision_state(decision_state_path)
    decision_acks = load_acks(_resolve_ack_path(resolved_repo_root))
    decision_result = evaluate(queue_text, today, decision_state, acks=decision_acks)
    decision_items = decision_result.items
    new_decision_state = decision_result.state
    decision_message = format_digest_message(
        decision_items, decision_result.suppressed, decision_result.stale_acks,
    )
    # 🔴 抑制条数**每轮都打**，含 0 条：一个只会变长、从不回显的抑制清单
    # 正是这套告警最该防的「看起来干净」。
    print(f"[判据] 决策提醒命中 {len(decision_items)} 项；"
          f"指纹确认压住 {len(decision_result.suppressed)} 项；"
          f"对不上现存行的陈旧确认 {len(decision_result.stale_acks)} 条。")

    # ② 队列 #312：可 Open 池事件驱动提醒——判据与 ① 均读 #308 同一份
    # 机器字段，互不依赖，各自独立算、独立决定是否有内容要发。
    #
    # 🔴 **取数走 `build_pool_items_from_repo`（双文件），不是 `queue_text`
    # 那一份**（队列 #312 缺口一，2026-08-19 零时巡检查清）：`QUEUE_REL`
    # 只指向机制环境那份，而 #315 拆分后采购／财务／质量三域的构建任务全
    # 住在业务场景那份里 ⇒ 三个域从未进过池。① 决策提醒仍读 `queue_text`
    # ——那是另一条独立链路，其取数范围是否同样欠账不在本次范围内（如实
    # 登记，见队列 #312 回写）。
    pool_state = load_pool_state(pool_state_path)
    pool_items = build_pool_items_from_repo(resolved_repo_root)
    new_pool_ids = compute_new_ids(pool_items, pool_state)
    pool_message = format_pool_reminder_message(pool_items, new_pool_ids)
    new_pool_state = new_known_state(pool_items)

    # ③ 队列 #312 缺口二：陈化催办——「新增即推」对"有活一直没开"结构性
    # 沉默，而这正是 Shao Peishen 要的那一半（「提醒我加快」）。与 ② 分别
    # 计指纹、独立成一条消息，互不覆盖。
    now = datetime.now(timezone.utc)
    stale_candidates, stale_degraded = compute_stale_candidates(
        pool_items, pool_state, now,
        touched_at=lambda item: (
            last_touched_at(resolved_repo_root, item.queue_rel, item.row_id)
            if item.queue_rel else None
        ),
    )
    for note in stale_degraded:
        print(f"[WARN] {note}", file=sys.stderr)
    stale_message = format_stale_reminder_message(stale_candidates)
    stale_ids = {c.item.row_id for c in stale_candidates}
    new_pool_state["stale_notified_at"] = new_stale_state(
        pool_items, pool_state, stale_ids if stale_message else set(), now,
    )

    if decision_message is None and pool_message is None and stale_message is None:
        print("[OK] 无新增/超期决策项，可 Open 池亦无新增行号、无陈化行，本次不发送。")
        if not dry_run:
            save_decision_state(decision_state_path, new_decision_state)
            save_pool_state(pool_state_path, new_pool_state)
        return 0

    if decision_message:
        print(decision_message)
    if pool_message:
        print(pool_message)
    if stale_message:
        print(stale_message)

    if dry_run:
        print("[dry-run] 以上内容不实际发送，状态文件不落地。")
        return 0

    # 先落两份状态，即便发送失败也不重复计入下次判定（同既有决策提醒惯例）。
    save_decision_state(decision_state_path, new_decision_state)
    save_pool_state(pool_state_path, new_pool_state)

    secrets = EnvSecretsProvider()
    bot_id = secrets.get(BOTID_KEY)
    secret = secrets.get(SECRET_KEY)
    connector = AibotConnector(bot_id, secret, max_reconnect_attempts=3)
    await connector.connect()
    await asyncio.sleep(1)  # 等 aibot_subscribe 认证完成

    try:
        if decision_message:
            await send_decision_reminder(
                connector, audit, decision_message, PAUL_USERID, fallback_send=fallback_send,
            )
        if pool_message:
            await send_open_pool_reminder(
                connector, audit, pool_message, PAUL_USERID, fallback_send=fallback_send,
            )
        if stale_message:
            await send_open_pool_reminder(
                connector, audit, stale_message, PAUL_USERID, fallback_send=fallback_send,
                action_prefix="open_pool_stale_reminder",
            )
    finally:
        connector.disconnect()

    sent_summary = []
    if decision_message:
        sent_summary.append(f"决策提醒 {len(decision_items)} 项")
    if pool_message:
        sent_summary.append(f"可 Open 池新增 {len(new_pool_ids)} 项")
    if stale_message:
        sent_summary.append(f"可 Open 池陈化催办 {len(stale_candidates)} 项")
    print(f"[OK] 已发送：{'；'.join(sent_summary)}。")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="需 Shao Peishen 决策项/待领 opener 主动提醒")
    parser.add_argument("--dry-run", action="store_true", help="只打印将发送的内容，不实际发送/不落状态文件")
    parser.add_argument(
        "--ack-item", default=None, metavar="KEY",
        help="确认某一提醒项已闭环（如 '§四#47'），带内容指纹；判据格一改即自动失效。")
    parser.add_argument(
        "--note", default="",
        help="--ack-item 配套：本次核的是什么、凭什么核的，必填。")
    parser.add_argument("--list-acks", action="store_true", help="列出现有指纹确认及其生效状态")
    args = parser.parse_args()
    if args.ack_item is not None:
        sys.exit(cmd_ack_item(args.ack_item, args.note))
    if args.list_acks:
        sys.exit(cmd_list_acks())
    sys.exit(asyncio.run(_run(args.dry_run)))


if __name__ == "__main__":
    main()
