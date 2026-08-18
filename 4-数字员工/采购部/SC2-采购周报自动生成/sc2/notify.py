"""推送层 —— 企微（spec: sc2-report-delivery「首版推送范围收窄」）。

🔴 **首版只推采购部群 + 姚祖怡，不推管理层**（design D8）。理由与 D5 同源：
**没经他过目的数字不进管理层视野**。一份口径尚未定版的周报进了管理层，纠错成本
远高于晚推送一期——#228 那族教训正是「通知已送达而内容其实还不对」。

**推送范围写死在常量里、不从环境读**：若做成 `SC2_EXTRA_RECIPIENTS` 这类环境
变量，扩大范围就成了一次改配置的事，不再经过任何评审——spec 要求扩大范围
MUST 经显式变更，故此处刻意不给运行时旁路。
"""
from __future__ import annotations

from . import config
from .review import ReviewStore, ensure_publishable

#: 首版推送对象。**扩大范围须改本常量并走变更评审**，不接受环境变量注入。
RECIPIENTS: tuple[str, ...] = ("采购部群", "姚祖怡")


def _send(webhook_url: str, text: str) -> None:
    """真实发送。抽成独立函数便于测试替换。"""
    from zhuopin_platform.shared_tools.notifiers.wecom import send_markdown

    send_markdown(webhook_url, text)


def push(period: str, *, text: str, store: ReviewStore | None = None,
         webhook_url: str | None = None) -> bool:
    """推送某期周报。

    :returns: True ＝ 本次真的发出去了；False ＝ 该期此前已推送过，本次跳过。

    🔴 **先过确认门**：未确认即上抛 `UnconfirmedError`，绝不推送。这是「未确认
    不得对外推送」在推送侧的执行点——确认层与推送层各守一道，不互相假设。
    """
    store = store or ReviewStore()
    ensure_publishable(store, period)

    if not store.mark_pushed(period):
        return False                      # 已推送过；重启后也不会重复发

    url = webhook_url if webhook_url is not None else config.wecom_webhook()
    if url:
        _send(url, text)
    return True
