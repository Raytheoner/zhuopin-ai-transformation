"""推送层 —— 企微智能机器人（spec: sc2-report-delivery「首版推送范围收窄」）。

🔴 **首版只推采购部群 + 姚祖怡，不推管理层**（design D8）。理由与 D5 同源：
**没经他过目的数字不进管理层视野**。

**推送范围写死在常量里、不从环境读**：若做成 `SC2_EXTRA_RECIPIENTS` 这类环境
变量，扩大范围就成了一次改配置的事，不再经过任何评审——spec 要求扩大范围
MUST 经显式变更，故此处刻意不给运行时旁路。

━━━ 🔴 **2026-08-25 起：确认发布不再是推送前置**（队列 §四 `#89`，Shao Peishen
2026-08-22 答 `OP0822A` 定夺 1 选 (a)）━━━

姚祖怡要的是「周五晚 8 点自动给出本周的，出来后挂到页面上，**同步推到群里**」。
原设计里那道「须有人点『确认发布』才允许推送」的门与之正面冲突，已按拍板**取消**。
连带定性亦已由 Shao Peishen 拍板：**「SC2 周报不属 IATF 需签认输出」**，实现方据此
执行、无需再向上找依据（旁证＝姚祖怡本人在 `采购部#17` 判例表 B 里写的「仅作为
工作量参考使用」）。

🔴 **两条代价当时已当面写明、他知情后仍选 (a)，此处只留痕、不复议**：
1. **审计轨迹层面不可逆** —— 代码随时能改回去，**但按自动发布跑过的那几周，记录里
   就是没有人工签认，事后补不回来**。「以后再改」只对未来生效。
2. 他答复时的前提是「二选一」，而本项实为三选一；中间方案（自动生成 ＋ 自动私信
   提醒、群推仍点一下）已如实呈现，**他知悉后仍选 (a)**。

⇒ 故本模块此后**不再调用 `ensure_publishable`**。`review.confirm()` 仍在、仍可用，
但它现在记录的是「**有人事后看过并签字**」，不再是推送的闸门（见 `review.py` 模块头）。

**保留下来的两道保护，不随本次一并取消**（它们防的不是签认，是重复与误投）：
- **幂等**：`store.mark_pushed()` 仍在，重启或重跑不会把同一期发第二遍。
- **范围**：收件人仍只有采购部群与姚祖怡，扩大仍须改常量走评审。
"""
from __future__ import annotations

from pathlib import Path

from . import outbox
from .review import ReviewStore

#: 首版推送对象。**扩大范围须改本常量并走变更评审**，不接受环境变量注入。
RECIPIENTS: tuple[str, ...] = ("采购部群", "姚祖怡")


def push(period: str, *, text: str, store: ReviewStore | None = None,
         outbox_path: Path | None = None) -> bool:
    """推送某期周报。

    :returns: True ＝ 本次真的写进了 outbox；False ＝ 该期此前已推送过，本次跳过。

    ⚠️ **True 的含义是「已交付给中继」，不是「群里已经看到了」**。真实送达取决于
    笔记本侧中继是否在跑（见 `outbox` 模块头）。调用方若要向人汇报「已推送」，
    须一并读 `outbox.pending()`——否则就是 `#82` 那个形态：**每天都在跑，一条都没发出去，
    而没有人察觉**。
    """
    store = store or ReviewStore()

    # 🔴 幂等在写盘之前：先抢占「本期已推送」这个标记，再写 outbox。
    # 反过来（先写后标记）会在两次调用挤在一起时把同一期写进去两遍。
    if not store.mark_pushed(period):
        return False

    outbox.enqueue(period=period, text=text, path=outbox_path)
    return True
