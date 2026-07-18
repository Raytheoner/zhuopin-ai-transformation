"""进件白名单：只处理指定 5 人的消息/文件（Paul 2026-07-16 口头需求，队列 #35）。

机器人此前对任何发件人一律归档+转发 Paul+群通报，导致同事发来的无关项目
消息被误当业务内容处理、污染队列与 Paul 私信。白名单外发送人改为只收到
一条礼貌回复（说明机器人尚未正式开通），不落档/不转发/不占用队列行/不发
群通报。

与 `department_mapping.py`（发送人→部门，用于归档目的地）是两件不同的事——
白名单只回答"这条消息要不要被处理"，不回答"处理后归哪个部门"。陈承
（IT，userid=2023458）不在 `department_mapping.yaml` 里（现有四部门口径不含
IT），命中白名单后仍会按现有归档逻辑落入"待分拣"——这是沿用现有行为，
不做特殊化（Paul 确认"归档+转发+群通报三条路径正常走"= 现有逻辑不变）。

陈承同时开通场景①（跟进信直达）推送对象（Paul 2026-07-16 确认）：
`delivery.py::push_followup` 按调用方传入的 `chatid` 直接发送，本就不经
本表过滤，故无需为此额外改动代码——调用 `scripts/push_followup_letter.py`
时把 `--chatid` 传成 `2023458` 即可对陈承推送。

Paul 本人（`PAUL_USERID`）此前不在白名单里，导致他自己发的 test 消息也会
被当"未开通"礼貌拒复、不落档不进队列——这在验证服务是否真正连通归档链
时会造成误判（收到礼貌回复≠归档链没问题，只是发件人不在白名单）。2026-07-18
总线审计发现后补入，Paul 现可像五位专员一样触发完整归档+转发+群通报三条
路径（转发/抄送逻辑本就对 Paul 自身发送有特殊处理，见 `forwarding.py`）。
"""
from __future__ import annotations

from .constants import PAUL_USERID

# 白名单发送人 userid（五位专员，Paul 2026-07-16 口头确认；Paul 本人，
# 2026-07-18 总线审计补入，见上）：
# - 2023458        陈承（IT）
# - ChenChen       陈忱（质量部）
# - tangyanping    唐燕萍（财务部）
# - YaoZuYi        姚祖怡（采购部）
# - Hongqin.Wang   王泓钦（销售部）
# - PAUL_USERID    Paul 本人（== "ShaoPeiShen"，见 constants.py）
WHITELISTED_SENDER_USERIDS = frozenset(
    {
        "2023458",
        "ChenChen",
        "tangyanping",
        "YaoZuYi",
        "Hongqin.Wang",
        PAUL_USERID,
    }
)

NOT_ONBOARDED_REPLY = (
    "您好，本机器人目前仅面向指定专员开通，暂不支持与您会话，敬请谅解。"
)


def is_whitelisted(sender: str) -> bool:
    """白名单外一律 fail-closed（不猜测、不放行），与 `department_mapping`
    的 fail-closed 风格一致。"""
    return sender in WHITELISTED_SENDER_USERIDS
