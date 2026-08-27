"""跟进信正文长度守卫与超限降级（队列 §一 #416，`OP-0828-B`）。

━━━ **缺陷原样** ━━━
`delivery.py` 把整篇正文当**一条** `send_markdown` 发出去，全库无任何长度
守卫。企微服务端对超限消息**不回 ack**，SDK `ws.py` 的
`_reply_ack_timeout = 5.0` 到点抛 `TimeoutError`。
🔴 **调大那个 5.0 不是修复**——服务端根本不会回，等多久都一样。

━━━ **实测区间（本模块阈值的全部依据，2026-08-28 本机复测）** ━━━
🔴 **先更正一处口径**：`波次收口-2026-08-26泳道版-2026-08-27.md` §十一 那张表
里的字节数是 **md 文件大小**，而真正发出去的串是**剥掉 frontmatter 之后的
正文**（`delivery._strip_frontmatter`）。两者差一个题头（实测 600~700 B）。
本模块一律按**实际发送串**计，故复测如下：

| 信 | 文件 B | 实际发送 B | 字符数 | 结果 |
|---|---|---|---|---|
| `质量部#8` C05–C07 判例批改表 | 13,939 | **13,242** | 6,354 | ✅ 已发出 |
| `采购部#18` 物料看板 | 11,407 | 11,104 | 4,604 | ✅ |
| 🔴 `采购部#19` | 25,255 | **24,597** | 12,569 | 🔴 两次同一处失败 |

⇒ **已知可发 ≤ 13,254 B**（含 `【抄送】` 前缀的那一条）／**已知发不出
≥ 24,597 B**。真实阈值落在这中间，**本班未实测出确切值**——测准它需要向
企微真发若干条消息，属对外发送，已登记待签认（见收工报告）。

**默认阈值取 14,000 B，取值理由写在这里以免后人当成拍脑袋**：
- 必须 **>13,254**，否则 `质量部#8` 那种今天发得出去的信会被无谓降级
  （opener 验收②要求它「不触发降级、行为不变」）；
- 必须 **<24,597**，否则守卫形同虚设；
- 区间内取**靠近已知可发那一端**，因为**两个方向的代价不对称**：阈值偏低
  ⇒ 多降级一封（收信人拿到提要＋完整附件，内容一点没少，只是要点开附件）；
  阈值偏高 ⇒ 发送直接失败（信压根没到，要等人发现再重试）。**宁可多降级，
  不可漏拦。**

**按字节不按字符**，依据是仓内既有实测：队列 §四 `#47` 记着群 webhook
「4096 **字节**上限（中文 UTF-8 每字 3 字节，实际远超字节上限）报
`errcode=40058`」——企微这一族限额是按字节算的。⚠️ **智能机器人通道与群
webhook 不是同一个限额**（本通道实测 13,242 B 能发，远超 4096），此处只借
用「按字节」这一条口径，不借用那个数。

━━━ 🔴 **守卫必须按「每条实际要发出去的串」算，不是按原文算** ━━━
`delivery.py` 三处发正文：私信发 `content`／抄送 ShaoPeiShen 与群抄送都发
`f"【抄送】{content}"`。**抄送比原文长。** 一封正文刚好卡在限内的信，抄送
那两条会先超 ⇒ **私信成功、群里什么都没有**，外观是「发出去了」。故本模块
的入口 `plan_body()` 一次性算齐**本次会发出的每一条串**，任一条超限即整封
降级——三条通道发同一个 body，不存在「一条全文、一条提要」的错位。
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

CC_PREFIX = "【抄送】"

#: 单条 markdown 消息的字节上限。取值理由见模块 docstring。
#: 🔴 实测出确切阈值后**只改这一个常量**（连同 docstring 里那张表）。
DEFAULT_MARKDOWN_MAX_BYTES = 14000

ENV_MARKDOWN_MAX_BYTES = "WECOM_AIBOT_MARKDOWN_MAX_BYTES"

_H1_RE = re.compile(r"^#\s+(.*\S)\s*$")
_H2_RE = re.compile(r"^##\s+(.*\S)\s*$")
_H3_RE = re.compile(r"^###\s+(.*\S)\s*$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")


class OversizedMessageError(RuntimeError):
    """本次内容无论如何都发不出去——**在发出任何一条之前**抛出。

    🔴 抛在这里是刻意的：它保住了 `#416` 那条「失败必须是干净的」性质
    ——`sent:False／acks:[]／media_ids:[]／backfilled:False`，README 状态
    与事实一致、可安全重试、不会退化成「私信发了、群没发」的半发。
    """


def markdown_max_bytes() -> int:
    """当前阈值。环境变量 `WECOM_AIBOT_MARKDOWN_MAX_BYTES` 可覆盖。

    **每次调用都重读环境变量**（不在 import 期定死）——`.51` 上真实阈值一旦
    测出来，改一个环境变量即可生效，不必等一次部署。取不到/非法值时回落
    默认并**不静默**：非法值直接回落是本项目「工具静默回退」那一族的入口，
    故此处对负数与非数字一律回落到默认值，且把原值写进异常之外的返回不做
    ——调用方拿到的永远是一个合法正整数。
    """
    raw = os.environ.get(ENV_MARKDOWN_MAX_BYTES)
    if raw is None:
        return DEFAULT_MARKDOWN_MAX_BYTES
    try:
        value = int(raw.strip())
    except (AttributeError, ValueError):
        return DEFAULT_MARKDOWN_MAX_BYTES
    return value if value > 0 else DEFAULT_MARKDOWN_MAX_BYTES


def measure(text: str) -> int:
    """一条串的字节长度（UTF-8）。判据口径的唯一入口，别处不得另算一遍。"""
    return len(text.encode("utf-8"))


@dataclass
class OutboundVariant:
    """本次会真的发出去的一条串。"""

    channel: str  # "私信" / "抄送ShaoPeiShen" / "群抄送"
    prefix: str
    size: int


@dataclass
class BodyPlan:
    body: str  # 三条通道统一发这一份
    degraded: bool
    original_bytes: int
    body_bytes: int
    limit: int
    variants: list[OutboundVariant] = field(default_factory=list)
    omitted_sections: int = 0

    @property
    def max_variant_bytes(self) -> int:
        return max((v.size for v in self.variants), default=self.body_bytes)

    def audit_fields(self) -> dict:
        """写进 audit `decision` 的守卫观测值——降级与否都写，便于事后复核。"""
        return {
            "length_guard": {
                "limit_bytes": self.limit,
                "original_bytes": self.original_bytes,
                "body_bytes": self.body_bytes,
                "max_outbound_bytes": self.max_variant_bytes,
                "degraded": self.degraded,
                "omitted_sections": self.omitted_sections,
                "channels": {v.channel: v.size for v in self.variants},
            }
        }


def outbound_variants(body: str, *, cc_channels: list[str]) -> list[OutboundVariant]:
    """本次会发出去的每一条串及其字节数。

    `cc_channels` 传的是**本次真的会抄送**的通道名（调用方按自己那两个
    `if` 的条件算好再传进来）——不是「有没有这个参数」，是「这一封会不会
    真的走这条通道」。传空即本次只发私信。
    """
    variants = [OutboundVariant("私信", "", measure(body))]
    for channel in cc_channels:
        variants.append(OutboundVariant(channel, CC_PREFIX, measure(CC_PREFIX + body)))
    return variants


def _strip_fenced(lines: list[str]) -> list[bool]:
    """逐行标出「是否在代码块围栏内」——围栏里的 `## xxx` 不是小节标题。"""
    inside = False
    flags: list[bool] = []
    for line in lines:
        if _FENCE_RE.match(line):
            flags.append(True)  # 围栏行本身也不是标题
            inside = not inside
            continue
        flags.append(inside)
    return flags


def extract_outline(content: str) -> tuple[str, list[str]]:
    """摘要的两个确定性输入：H1 标题 ＋ 逐条小节标题。

    🔴 **规则是「取全部二级标题」，不是「挑出要他办的事」**——正文里没有任何
    机器可读的标记能区分「这一节要他回」与「这一节只是知会」，靠中文措辞猜
    正是 `#308` 那一族（`工具-落库sweep.py::OBSERVATION_WINDOW_RE` 已把「猜
    中文关键词」明列为要根治的形态，`OP-0827-G` 也是因此否掉了同类修法）。
    **全列出来，一条不漏，让收信人自己看**——代价是提要比人手写的略粗，
    收益是它不会漏掉任何一件要他办的事。

    退化次序（每一档都写死，不即兴）：
    ⑴ 有 `## ` 二级标题 ⇒ 用它们；
    ⑵ 没有二级、有 `### ` 三级 ⇒ 用三级（有些短信只分了三级）；
    ⑶ 一个标题都没有 ⇒ 返回空列表，摘要里明写「正文无小节标题」。
    H1 取不到时回落到首个非空行（截断到 60 字符），不留空标题。
    """
    lines = content.splitlines()
    fenced = _strip_fenced(lines)

    h1 = ""
    h2: list[str] = []
    h3: list[str] = []
    for line, in_fence in zip(lines, fenced):
        if in_fence:
            continue
        if not h1:
            m = _H1_RE.match(line)
            if m:
                h1 = m.group(1).strip()
                continue
        m2 = _H2_RE.match(line)
        if m2:
            h2.append(m2.group(1).strip())
            continue
        m3 = _H3_RE.match(line)
        if m3:
            h3.append(m3.group(1).strip())

    if not h1:
        for line in lines:
            if line.strip():
                h1 = line.strip()[:60]
                break

    return h1, (h2 if h2 else h3)


def build_summary(
    content: str,
    *,
    attachment_names: list[str],
    original_bytes: int,
    limit: int,
    keep_sections: int | None = None,
) -> tuple[str, int]:
    """按确定规则生成降级正文。返回 `(摘要, 未列出的小节数)`。

    🔴 **必须在正文里显式告知「内容不全在这儿」**——这一条比降级本身更要紧：
    收信人若不知道这是提要，会以为这封信就这么点事，那比发不出去更糟
    （发不出去至少有人会发现）。故摘要里有两处明写：顶部一句 ⚠️、底部一句
    📎，且都点名附件。
    """
    h1, sections = extract_outline(content)
    total = len(sections)
    kept = sections if keep_sections is None else sections[:max(keep_sections, 0)]
    omitted = total - len(kept)

    names = "、".join(attachment_names) if attachment_names else "本信附件"

    parts = [f"# {h1}" if h1 else "# （本信无标题）", ""]
    parts.append(
        f"⚠️ **这条企微消息只是提要，不是完整正文。** "
        f"原文 {original_bytes:,} 字节，超过单条消息上限 {limit:,} 字节，"
        f"故此处只列小节标题。"
    )
    parts.append(
        f"📎 **完整说明、判例表与对照表都在附件里**（{names}）——"
        f"**勾选与批改请直接在附件的 Word 上做，一切以附件为准。**"
    )
    parts.append("")
    if total:
        parts.append(f"本信共 {total} 个小节：")
        parts.extend(f"{i}. {title}" for i, title in enumerate(kept, 1))
        if omitted:
            parts.append(f"…另有 **{omitted}** 个小节未在此列出（全部在附件里）。")
    else:
        parts.append("（正文未分小节，全部内容都在附件里。）")
    parts.append("")
    parts.append("—— 本提要由推送机制按固定规则自动生成，未改写任何一句原文。")
    return "\n".join(parts), omitted


def plan_body(
    content: str,
    *,
    cc_channels: list[str],
    attachment_names: list[str],
    limit: int | None = None,
) -> BodyPlan:
    """本次到底发哪一份正文——**在发出任何一条之前**一次性决定。

    ⑴ 原文的每一条外发串都在限内 ⇒ 原样发，`degraded=False`，行为与守卫
       上线前逐字相同；
    ⑵ 任一条超限 ⇒ 整封降级为「提要＋附件」，**三条通道发同一份提要**
       （不允许「私信全文、群里提要」这种错位）；
    ⑶ 🔴 **超限但没有任何附件 ⇒ 直接抛 `OversizedMessageError`，一条都不发**
       ——降级的前提是「完整内容在附件里」，没有附件的降级等于**静默丢内容**，
       那正是本次要防的东西；
    ⑷ 提要本身仍超限 ⇒ 逐条砍掉末尾小节并**显式写出砍了几条**，绝不静默
       截断；砍到一条不剩仍超限 ⇒ 抛 `OversizedMessageError`。
    """
    effective_limit = markdown_max_bytes() if limit is None else limit
    original_bytes = measure(content)

    variants = outbound_variants(content, cc_channels=cc_channels)
    if all(v.size <= effective_limit for v in variants):
        return BodyPlan(
            body=content, degraded=False, original_bytes=original_bytes,
            body_bytes=original_bytes, limit=effective_limit, variants=variants,
        )

    over = [v for v in variants if v.size > effective_limit]
    if not attachment_names:
        raise OversizedMessageError(
            f"正文超过单条消息上限且本信无附件，拒绝发送（一条都没发，可安全重试）："
            f"上限 {effective_limit} 字节，超限通道＝"
            + "／".join(f"{v.channel} {v.size} 字节" for v in over)
            + "。降级的前提是完整内容在附件里；没有附件时降级等于静默丢内容。"
        )

    _, sections = extract_outline(content)
    for keep in range(len(sections), -1, -1):
        summary, omitted = build_summary(
            content, attachment_names=attachment_names,
            original_bytes=original_bytes, limit=effective_limit, keep_sections=keep,
        )
        summary_variants = outbound_variants(summary, cc_channels=cc_channels)
        if all(v.size <= effective_limit for v in summary_variants):
            return BodyPlan(
                body=summary, degraded=True, original_bytes=original_bytes,
                body_bytes=measure(summary), limit=effective_limit,
                variants=summary_variants, omitted_sections=omitted,
            )

    raise OversizedMessageError(
        f"降级提要本身仍超过单条消息上限 {effective_limit} 字节（小节已全部略去），"
        "拒绝发送——一条都没发，可安全重试。请人工拆信或缩短标题。"
    )
