"""真延期识别 + 去重推送（capability: baoguan-alert-dispatch，design D6）。

每次刷新后：
  ① detect_new_red：本次 🔴 真延期行 vs 上次快照按稳定键 (item_code, fo_id, ship_date) 比对，
     取**新增**的真延期（上次不在、本次出现）；
  ② dispatch_new_reds：对新增真延期，经案例去重（无未关闭案例才建案+推送），
     推企微保供运维群（内部运维口径，**非对客**、不受 CUSTOMER_OUTBOUND_ENABLED 影响），并写 audit。

去重账本 = 案例本身（D6）：建案幂等 + 已建案不重推，天然防重复轰炸。
推送内容只含内部运维信息（料号/瓶颈子件/确定延期天数），**不含客户名**（运维群口径）。
"""
from __future__ import annotations


def red_key(row: dict) -> tuple[str, str, str]:
    """真延期稳定键 = (成品料号, 预测订单号, 计划出货日)。与行序无关。"""
    return (row.get("id", ""), row.get("so", ""), row.get("ship", ""))


def detect_new_red(curr, prev) -> list[dict]:
    """识别新增 🔴 真延期：本次 risk=='red' 且上次快照同稳定键不是真延期。

    curr/prev：Snapshot（prev 可为 None=首次刷新，则所有真延期都算新增）。
    """
    prev_red = set()
    if prev is not None:
        prev_red = {red_key(r) for r in prev.rows if r.get("risk") == "red"}
    return [r for r in curr.rows if r.get("risk") == "red" and red_key(r) not in prev_red]


def _is_bottleneck_unanswered(row: dict) -> bool:
    """瓶颈子件是否在本行"无答复子件明细"里——与 case_store.bottleneck_unanswered
    同一判据（#223），建案时据此传入，驱动 case_draft.py 客户草稿措辞分支。"""
    bn = row.get("bn") or "—"
    nfd_ids = {d.get("id") for d in (row.get("nfd") or [])}
    return bn in nfd_ids


def _alert_markdown(row: dict) -> str:
    """单条真延期的企微保供运维消息（内部口径，不含客户名）。

    队列#147续（2026-07-29，Paul 拍板改口径后）：延期天数/瓶颈改用 `gap`（全量口径，
    与卡片头部徽标同源），不再用 `cg`（仅确定承诺子件）——避免运维群收到的告警数字
    跟看板头部对不上，重蹈本次姚祖怡二次举证的同类矛盾。措辞区分瓶颈子件是否已答复：
    未答复时明确写"保守预警/估算"，不把猜测包装成"确定"发给运维群误导决策。
    """
    gap = row.get("gap")
    bn = row.get("bn") or "—"
    unanswered = _is_bottleneck_unanswered(row)
    if unanswered:
        gap_txt = f"保守预警 +{gap} 天（未答复估算）" if gap is not None else "保守预警（未答复估算）"
        bn_txt = f"瓶颈子件（未答复）`{bn}`"
    else:
        gap_txt = f"确定延期 +{gap} 天" if gap is not None else "确定延期"
        bn_txt = f"确定瓶颈子件 `{bn}`"
    return (f"🔴 **保供真延期** 成品 `{row.get('id','')}`（单 {row.get('so','')}）\n"
            f"> 计划出货 {row.get('ship','')}　|　{gap_txt}\n"
            f"> {bn_txt}　|　子件 {row.get('comp',0)}（未答复 {row.get('nf',0)}）\n"
            f"> 已自动建案，请保供运维跟进催货/协调。")


def dispatch_new_reds(new_reds: list[dict], case_store, *, webhook_url: str | None = None,
                      audit=None, sender=None) -> list[dict]:
    """对新增真延期：去重建案 → 推企微 → 写 audit。返回实际推送的行（已去重）。

    case_store：去重账本（find_open_by_key / create_case 幂等）。
    webhook_url：保供运维群 webhook（缺省不推，仅建案）。
    sender：注入的发送函数 sender(webhook_url, content)（测试用）；缺省走 wecom.send_markdown。
    """
    pushed: list[dict] = []
    for row in new_reds:
        item_code, fo_id, ship_date = red_key(row)
        # D6 去重：已有未关闭案例 → 不建、不推
        if case_store.find_open_by_key(item_code, fo_id, ship_date):
            continue
        # 队列#147续：建案天数改用 gap（全量口径，与建案原因——该行判红——同源），
        # 不再用 cg（仅确定承诺，可能远小于实际驱动红色的全量估算天数）。
        # #223 已解决：bottleneck_unanswered 随建案一并落库，驱动 case_draft.py
        # 客户草稿的"确定 vs 交期未确认"措辞分支，不再隐含"这是真实确认"的固定语义。
        case, created = case_store.create_case(
            item_code=item_code, fo_id=fo_id, customer_name=row.get("cust", ""),
            ship_date=ship_date, confirmed_gap_days=int(row.get("gap") or 0),
            bottleneck_material=row.get("bn", ""),
            bottleneck_unanswered=_is_bottleneck_unanswered(row))
        if not created:        # 并发兜底：刚被别处建案
            continue
        content = _alert_markdown(row)
        # 真实事故复现（2026-07-29，队列#147续口径切换首轮重算，大量行同时首次判红）：
        # 短时间内连续推送触发企微 API 限流（errcode=45009），旧代码让 send() 的异常
        # 直接冒泡，导致本行之后剩余全部新增真延期都不再建案/推送、且整个 /api/refresh
        # 请求报错——案例已建但通知漏发、且中断了本该继续的后续行处理。改为单行推送
        # 失败只记 audit + 跳过通知，不影响本行"已建案"的事实，也不阻断循环处理其余行。
        push_ok = True
        if webhook_url:
            send = sender
            if send is None:
                from zhuopin_platform.shared_tools.notifiers import wecom
                send = wecom.send_markdown
            try:
                send(webhook_url, content)
            except Exception as e:
                push_ok = False
                if audit is not None:
                    from zhuopin_platform.audit import AuditEvent
                    audit.record(AuditEvent(
                        scenario="SC8", action="baoguan_red_alert_push_failed",
                        evaluator="system", automation_level="L1",
                        decision={"case_no": case.case_no, "item_code": item_code,
                                  "fo_id": fo_id, "ship_date": ship_date,
                                  "error": f"{type(e).__name__}: {e}"[:200]},
                        data_sources={"baoguan": "real"}))
        if audit is not None:
            from zhuopin_platform.audit import AuditEvent
            audit.record(AuditEvent(
                scenario="SC8", action="baoguan_red_alert", evaluator="system",
                automation_level="L1",
                decision={"case_no": case.case_no, "item_code": item_code,
                          "fo_id": fo_id, "ship_date": ship_date,
                          "gap_days": int(row.get("gap") or 0),
                          "pushed": bool(webhook_url) and push_ok},
                data_sources={"baoguan": "real"}))
        if push_ok:
            pushed.append(row)
    return pushed
