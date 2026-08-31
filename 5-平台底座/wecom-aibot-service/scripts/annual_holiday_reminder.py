"""队列 #379：法定节假日日历「每年更新」提醒——每年 9 月 1 日向李姣龙催办
次年节假日日历，并抄送 ShaoPeiShen 一条知会。判断逻辑见
`aibot_service.annual_holiday_reminder`（可独立单测），本文件只负责网络 I/O
与 CLI。

**存活自证（队列 #379 行内硬要求，不可省）**：本脚本设计为**每日**触发（同
`ZhuopinDecisionReminderDaily` 惯例，而非依赖 Windows 原生"每年一次"触发器），
内部按本机**本地日期**（根 `CLAUDE.md`「时间戳必判 UTC vs Win 本地」——判"今天
是不是 9 月 1 日"用本地日期，不用 UTC）判断是否到该发送的那一天；**非 9 月 1
日照样运行、只是不发送**，但**每次运行都会刷新 `last_checked_at` 心跳**（写入
状态文件），使"任务是否还活着"这件事不必等到明年 9 月才能验证——同族教训见
队列 #379 原文：「一年后才第一次跑的定时任务，到时候多半是坏的、且没人会
知道它坏了」。

**发送前置校验（队列 #380 是本行硬前置）**：发送前核验 `dispatch.py::
KNOWN_RECIPIENT_USERIDS`（出站）与 `whitelist.py::is_whitelisted`（入站）
均已放行李姣龙——任一不通即中止、不发送、写 `annual_holiday_reminder_blocked`
审计并尝试走独立 webhook 告警（不依赖本服务自身长连接，同 `#193`/`#387`/
`#380` 既有兜底通道惯例），因为这正是本行历史上已经发生过的形态：出站先通、
入站后通，中间那段窗口若照发不误，她的回复会被 fail-closed 静默挡回。

用法：
  python scripts/annual_holiday_reminder.py               # 正常路径：非 9-1 只刷心跳，9-1 才发
  python scripts/annual_holiday_reminder.py --dry-run      # 只打印将执行的判断与文案，不发送/不落状态
  python scripts/annual_holiday_reminder.py --force        # 忽略日期与"今年已发过"两道闸，立即发送
                                                             # （人工执行首触发用，见队列 #379 B-1(a)）
  python scripts/annual_holiday_reminder.py --message "..."  # 覆盖默认文案（今年首次特例用，
                                                             # 见队列 #379：2027 表已提前给过，
                                                             # 不应重新索取）

环境变量（同 `decision_reminder_check.py`/`push_followup_letter.py` 既有约定）：
  WECOM_AIBOT_QUEUE_PATH   可选，仓库根解析锚点
  WECOM_AIBOT_REPO_ROOT    可选，显式指定仓库根，绕开动态 git 解析
  WECOM_AIBOT_AUDIT_PATH   可选，直接指定审计文件路径
  WECOM_AIBOT_ANNUAL_REMINDER_STATE_PATH  可选，状态/心跳文件路径
  WECOM_WEBHOOK_URL        可选，前置校验失败时的兜底群 webhook 告警通道
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

SERVICE_DIR = Path(__file__).resolve().parent.parent
NAIVE_REPO_ROOT = SERVICE_DIR.parents[1]

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

from zhuopin_platform.audit import AuditLogger, AuditEvent  # noqa: E402
from zhuopin_platform.shared_tools.notifiers import wecom  # noqa: E402
from zhuopin_platform.shared_tools.notifiers.wecom_aibot import AibotConnector  # noqa: E402
from zhuopin_platform.shared_tools.secrets import EnvSecretsProvider  # noqa: E402

from aibot_service.annual_holiday_reminder import (  # noqa: E402
    LI_JIAOLONG_USERID,
    STATE_REL,
    check_admission,
    format_reminder_message,
    load_state,
    next_target_year,
    save_state,
    should_send,
)
from aibot_service.connection import BOTID_KEY, SECRET_KEY  # noqa: E402
from aibot_service.constants import PAUL_USERID  # noqa: E402
from aibot_service.dispatch import KNOWN_RECIPIENT_USERIDS  # noqa: E402
from aibot_service.repo_paths import (  # noqa: E402
    DEFAULT_QUEUE_RELATIVE_PATH,
    resolve_audit_path,
    resolve_default_queue_anchor,
    resolve_repo_root,
)
from aibot_service.whitelist import is_whitelisted  # noqa: E402


def _resolve_paths() -> tuple[Path, Path, Path]:
    """(仓库根, 审计文件, 状态文件)——与 `run_aibot_service.py` 同一套解析，
    确保本脚本与常驻监听器写同一份审计文件（`resolve_audit_path` docstring：
    "常驻服务与一次性脚本共用同一份文件"）。"""
    queue_anchor = resolve_default_queue_anchor(NAIVE_REPO_ROOT, DEFAULT_QUEUE_RELATIVE_PATH)
    resolved_repo_root = resolve_repo_root(queue_anchor, fallback=NAIVE_REPO_ROOT)
    audit_path = Path(os.environ.get("WECOM_AIBOT_AUDIT_PATH", "") or resolve_audit_path(resolved_repo_root))
    state_path = Path(
        os.environ.get("WECOM_AIBOT_ANNUAL_REMINDER_STATE_PATH", "")
        or (resolved_repo_root / "5-平台底座" / "wecom-aibot-service" / STATE_REL)
    )
    return resolved_repo_root, audit_path, state_path


def _resolve_ops_webhook(repo_root: Path) -> str | None:
    load_dotenv(repo_root / "5-平台底座" / ".env")
    return os.environ.get("WECOM_WEBHOOK_URL") or None


async def _send(bot_id: str, secret: str, chatid: str, text: str) -> dict:
    connected = asyncio.Event()
    conn_error: dict = {"err": None}
    connector = AibotConnector(
        bot_id,
        secret,
        max_reconnect_attempts=0,
        on_authenticated=lambda: connected.set(),
        on_error=lambda e: (conn_error.__setitem__("err", str(e)), connected.set()),
    )
    await connector.connect()
    try:
        await asyncio.wait_for(connected.wait(), timeout=15)
        if conn_error["err"]:
            raise RuntimeError(f"连接失败：{conn_error['err']}")
        return await connector.send_markdown(chatid, text)
    finally:
        connector.disconnect()


def main() -> int:
    parser = argparse.ArgumentParser(description="队列 #379：年度节假日日历更新提醒（李姣龙）")
    parser.add_argument("--dry-run", action="store_true", help="只打印判断与文案，不发送/不落状态")
    parser.add_argument("--force", action="store_true", help="忽略日期闸与幂等闸，立即发送（人工首触发用）")
    parser.add_argument("--message", type=str, default=None, help="覆盖默认文案（今年首次特例用）")
    args = parser.parse_args()

    repo_root, audit_path, state_path = _resolve_paths()
    audit = AuditLogger.jsonl(audit_path)
    state = load_state(state_path)

    now_local = datetime.now().astimezone()
    now_utc = datetime.now(timezone.utc)
    today_local = now_local.date()

    print(f"[INFO] 本地日期 {today_local.isoformat()}（{now_local.isoformat()}）"
          f" / UTC {now_utc.isoformat()}；今年已发过={state.get('last_sent_year') == today_local.year}；"
          f"--force={args.force}")

    if not should_send(today_local, state, force=args.force):
        reason = ("今年已发过（--force 可强制重发）"
                   if state.get("last_sent_year") == today_local.year else "非触发日，仅心跳")
        print(f"[SKIP] 本次不发送——{reason}")
        if not args.dry_run:
            state["last_checked_at"] = now_utc.isoformat()
            save_state(state_path, state)
            audit.record(
                AuditEvent(
                    scenario="wecom-aibot",
                    action="annual_holiday_reminder_heartbeat",
                    evaluator="system",
                    automation_level="L1",
                    decision={"sent": False, "reason": reason},
                    data_sources={"today_local": today_local.isoformat()},
                )
            )
        return 0

    next_year = next_target_year(today_local)
    message = args.message or format_reminder_message(next_year)
    print(f"[PLAN] 将发送给李姣龙（{LI_JIAOLONG_USERID}）：\n{message}")

    admission = check_admission(KNOWN_RECIPIENT_USERIDS, is_whitelisted)
    print(f"[CHECK] 队列 #380 前置：出站已知={admission.outbound_ok}，入站白名单={admission.inbound_ok}")
    if not admission.passed:
        reason = (f"队列 #380 前置未通过（出站={admission.outbound_ok}，"
                   f"入站={admission.inbound_ok}），已中止、未发送")
        print(f"[BLOCKED] {reason}")
        if args.dry_run:
            return 1
        audit.record(
            AuditEvent(
                scenario="wecom-aibot",
                action="annual_holiday_reminder_blocked",
                evaluator="system",
                automation_level="L1",
                decision={"sent": False, "recipient": LI_JIAOLONG_USERID, "reason": reason},
                data_sources={"target_year": next_year},
            )
        )
        webhook_url = _resolve_ops_webhook(repo_root)
        if webhook_url:
            try:
                wecom.send_text(webhook_url, f"⚠️ 企微智能机器人服务：{reason}")
            except Exception as exc:  # noqa: BLE001 —— 告警失败不应掩盖本次中止已写入审计的事实
                print(f"[WARN] 告警发送失败（审计已记）：{exc!r}")
        return 1

    if args.dry_run:
        print("[DRY-RUN] 前置校验通过，未实际发送。")
        return 0

    load_dotenv(repo_root / "5-平台底座" / ".env")
    secrets = EnvSecretsProvider()
    bot_id = secrets.get(BOTID_KEY)
    secret = secrets.get(SECRET_KEY)

    try:
        ack = asyncio.run(_send(bot_id, secret, LI_JIAOLONG_USERID, message))
    except Exception as exc:  # noqa: BLE001 —— 发送失败必须留痕，不得静默吞掉
        print(f"[FAIL] 发送异常：{exc!r}")
        audit.record(
            AuditEvent(
                scenario="wecom-aibot",
                action="annual_holiday_reminder_failed",
                evaluator="system",
                automation_level="L1",
                decision={"sent": False, "recipient": LI_JIAOLONG_USERID},
                data_sources={"error": repr(exc), "target_year": next_year},
            )
        )
        return 1

    errcode = ack.get("errcode") if isinstance(ack, dict) else None
    errmsg = ack.get("errmsg") if isinstance(ack, dict) else None
    print(f"[ACK] {ack!r}")
    audit.record(
        AuditEvent(
            scenario="wecom-aibot",
            action="annual_holiday_reminder_sent",
            evaluator="system",
            automation_level="L1",
            decision={
                "sent": True,
                "recipient": LI_JIAOLONG_USERID,
                "errcode": errcode if isinstance(errcode, int) else None,
                "errmsg": errmsg if isinstance(errmsg, str) else None,
            },
            data_sources={"target_year": next_year, "message_override": bool(args.message)},
        )
    )
    state["last_sent_at"] = now_utc.isoformat()
    state["last_sent_year"] = today_local.year
    state["last_checked_at"] = now_utc.isoformat()
    state["last_target_year"] = next_year
    save_state(state_path, state)

    # 抄送 ShaoPeiShen 一条知会——短消息，不走 message_length 降级机制
    # （那是为长跟进信设计的；本条固定短文案，远低于任何已知限额）。
    try:
        cc_ack = asyncio.run(
            _send(
                bot_id,
                secret,
                PAUL_USERID,
                f"【抄送】已向李姣龙发送 {next_year} 年度节假日日历更新提醒（队列 #379 年度定时）。",
            )
        )
        cc_errcode = cc_ack.get("errcode") if isinstance(cc_ack, dict) else None
        print(f"[CC-ACK] {cc_ack!r}")
    except Exception as exc:  # noqa: BLE001 —— 抄送失败不影响主发送已成功的事实，只记录
        cc_errcode = None
        print(f"[WARN] 抄送 ShaoPeiShen 失败（不影响主发送结果）：{exc!r}")
    audit.record(
        AuditEvent(
            scenario="wecom-aibot",
            action="annual_holiday_reminder_cc_paul",
            evaluator="system",
            automation_level="L1",
            decision={"sent": cc_errcode == 0, "recipient": PAUL_USERID},
            data_sources={"target_year": next_year},
        )
    )

    if errcode == 0:
        print(f"[OK] errcode=0，已发送并写入审计（{audit_path}）。")
        return 0
    print(f"[WARN] errcode={errcode!r}（非 0 或判不出），已如实写入审计文件，请人工核查。")
    return 2


if __name__ == "__main__":
    sys.exit(main())
