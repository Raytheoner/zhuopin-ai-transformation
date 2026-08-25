"""入站白名单：准入判据、两表串联不变式、拒绝可见性（队列 #380 ／ §四 #116，
变更包 `aibot-inbound-whitelist-li-jiaolong`）。

Shao Peishen 2026-08-25 三点全批：⑴ 准入判据取 **(乙) 出站即入站**、⑵ 解植雅
（`2025621`）**(b) 一并补入**、⑶ **补 `whitelist_rejected` 独立通道告警**。

🔑 **本文件里真正带新信息的是那两条不变式测**，不是"某某在不在表里"那几条：
本包的真问题从来不是"少了李姣龙一个人"，而是**出站名单与入站名单各自演进、
此前没有任何机制保证二者一致**——李姣龙这个缺口是有人做部门映射核对时顺手
撞出来的，不是机制发现的。判据 (乙) 的执行体就在下面
`test_出站已知收件人必须同时入站可达`：**今后任何新收件人进了 `dispatch.py`
却没进白名单，这条测当场变红。**
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.shared_tools.secrets import EnvSecretsProvider

from aibot_service.connection import build_connector, BOTID_KEY, SECRET_KEY
from aibot_service.constants import PAUL_USERID
from aibot_service.department_mapping import load_department_mapping, resolve_department
from aibot_service.dispatch import KNOWN_RECIPIENT_USERIDS
from aibot_service.intake import DEPARTMENT_TO_QUEUE_OWNER
from aibot_service.whitelist import (
    WHITELISTED_SENDER_USERIDS,
    alert_whitelist_rejected,
    format_whitelist_rejected_alert,
    is_whitelisted,
)

from fakes import fake_client_factory

LI_JIAOLONG = "2025672"
XIE_ZHIYA = "2025621"

# 🔴 `PAUL_USERID` 是"在白名单、不在部门映射"这条不变式的**唯一豁免**，且它是
# **显式豁免、不是默默跳过**（tasks.md 2.3 明确要求）。理由：他是决策人本人，
# 不是任何一个部门的对接专员——给他编一个部门映射值，等于凭空造出一条"邵培申
# 属于某部门"的事实，而 `forwarding.py` 本就对他自身发送另有特殊处理。
DEPARTMENT_MAPPING_EXEMPT_SENDERS = frozenset({PAUL_USERID})

QUEUE_TEXT = """\
## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 1 | 既有任务 | CC | p | e | 待领 | — | 07-09 |
"""

REJECTED_MESSAGE_BODY = "机器人你好，请问下周的对账口径改了吗"


def _secrets():
    return EnvSecretsProvider(override={BOTID_KEY: "BOT1", SECRET_KEY: "SECRET1"})


def _text_frame(sender: str, content: str = "x") -> dict:
    return {"body": {"msgtype": "text", "from": {"userid": sender}, "text": {"content": content}}}


# ───────────────────────── 1. 放行结果（tasks 2.1 / 2.2） ─────────────────────────


def test_李姣龙入站可达():
    assert is_whitelisted(LI_JIAOLONG) is True


def test_解植雅入站可达():
    """他 2026-07-20T02:55:21Z 已被本门禁静默挡回一次（审计 jsonl:204），
    36 天无人知情——本次放行是 §四 #116 决策点 2(b)。"""
    assert is_whitelisted(XIE_ZHIYA) is True


def test_既有六项一字不动():
    """回归锁：本次只加两个 userid，此前六项一个不动、一个不改。"""
    for userid in ("2023458", "ChenChen", "tangyanping", "YaoZuYi", "Hongqin.Wang", PAUL_USERID):
        assert userid in WHITELISTED_SENDER_USERIDS


def test_两位新人的_userid_都是纯数字工号而非拼音猜测():
    """🔴 财务部六人里有两个是纯数字工号形态；任何"按拼音猜 userid"的做法在
    他们身上一定错，且错的形态是 fail-closed 静默跳过、命令行一切正常。"""
    for userid, pinyin_guess in ((LI_JIAOLONG, "LiJiaoLong"), (XIE_ZHIYA, "XieZhiYa")):
        assert userid.isdigit()
        assert not is_whitelisted(pinyin_guess)


def test_解析部门_两位新人_yaml数字键经str归一后仍查得中():
    mapping = load_department_mapping()
    assert resolve_department(LI_JIAOLONG, mapping) == "财务部"
    assert resolve_department(XIE_ZHIYA, mapping) == "采购部"


def test_intake_已有对应_owner_无需改动():
    """tasks 1.4：这是**核验、不是改动**——`DEPARTMENT_TO_QUEUE_OWNER` 本就含
    这两个部门，本次不新增任何 owner 取值。"""
    assert DEPARTMENT_TO_QUEUE_OWNER["财务部"] == "财务专线"
    assert DEPARTMENT_TO_QUEUE_OWNER["采购部"] == "采购专线"


# ─────────────── 2. 两条不变式（tasks 2.3 ＋ §四 #116 决策点 1(乙)） ───────────────


def test_出站已知收件人必须同时入站可达():
    """🔴 **判据 (乙) 的执行体**：凡在 `dispatch.py::KNOWN_RECIPIENT_USERIDS`
    内者 SHALL 同时入站可达。

    **方向是单向的、刻意如此**：出站 ⊆ 入站，反向不要求——解植雅在白名单里
    但不在出站收件人表里（我方不主动给他发跟进信），这完全正常。要求双向相等
    会把"入站放行"和"出站投递"两件不同的授权强行绑死。

    失败时报出的是差集本身，不是一句"断言失败"——差集里那几个人正是"我方发得
    出去、他们回不进来"的人，而这种不对称的失败形态是**静默的**：他们只会收到
    一句"暂不支持与您会话"，我方这边什么也不会发生。
    """
    outbound = set(KNOWN_RECIPIENT_USERIDS.values())
    unreachable_inbound = outbound - set(WHITELISTED_SENDER_USERIDS)
    assert unreachable_inbound == set(), (
        f"这些人我方发得出去、却回不进来（出站在册、入站被挡）：{sorted(unreachable_inbound)}。"
        f"判据 (乙)「出站即入站」要求两表求差为空——请在 whitelist.py 与 "
        f"department_mapping.yaml 里**同批**补齐。"
    )


def test_在白名单者必须同时有部门映射_PAUL_USERID显式豁免():
    """tasks 2.3 的不变式：不得存在「已放行但无部门映射」的中间态。

    这不是理论风险——陈承（`2023458`）2026-07-16 入白名单、2026-07-22 才补部门
    映射（队列 #70），其间来件全部落 `7-外部文档/待分拣/`、队列行标"发送人身份
    待确认"、owner 落未命中默认值，**与"连身份都没认出来"共用同一个落点，读队列
    的人分不出二者**。

    `PAUL_USERID` 的豁免写在 `DEPARTMENT_MAPPING_EXEMPT_SENDERS` 里、并在此处
    显式相减——**不是在循环里 `continue` 掉**：豁免必须是一件看得见、需要有人
    专门写一行才能新增的事。
    """
    mapping = load_department_mapping()
    whitelisted_needing_mapping = set(WHITELISTED_SENDER_USERIDS) - DEPARTMENT_MAPPING_EXEMPT_SENDERS
    unmapped = whitelisted_needing_mapping - set(mapping)
    assert unmapped == set(), (
        f"这些 userid 已放行入站、却没有部门映射：{sorted(unmapped)}。"
        f"其来件会落 `7-外部文档/待分拣/`、队列行标「发送人身份待确认」——"
        f"这是 MUST 避免的中间态，不是可接受的稳态（队列 #70）。"
    )


def test_豁免名单本身受控():
    """守卫的守卫：若哪天有人为了让上面那条测变绿而往豁免名单里塞人，本条变红。"""
    assert DEPARTMENT_MAPPING_EXEMPT_SENDERS == {PAUL_USERID}


# ───────────────── 3. 拒绝可见性（tasks 2.4 ／ §四 #116 决策点 3） ─────────────────


def test_告警文案含_userid_msgtype_与_UTC_时刻():
    text = format_whitelist_rejected_alert(
        XIE_ZHIYA, "text", datetime(2026, 7, 20, 2, 55, 21, tzinfo=timezone.utc)
    )
    assert XIE_ZHIYA in text
    assert "msgtype=text" in text
    assert "2026-07-20 02:55:21 UTC" in text


def test_告警文案把本地时刻换算成_UTC_再标基准():
    """根 CLAUDE.md 硬规则：引用任何时刻前先答"这是 UTC 还是本地"，并显式标基准。
    传进来的若是带 +08:00 的本地时刻，输出必须是换算后的 UTC，且带 `UTC` 字样。"""
    local = datetime(2026, 7, 20, 10, 55, 21, tzinfo=timezone(timedelta(hours=8)))
    assert "2026-07-20 02:55:21 UTC" in format_whitelist_rejected_alert(XIE_ZHIYA, "text", local)


def test_告警函数的签名根本收不下正文():
    """🔴 "不外泄正文"不是靠"记得别传"守的，是靠**拿不到**守的。

    `format_whitelist_rejected_alert` 只接受 `sender`/`msgtype`/`occurred_at`
    三个入参——没有任何形参能装下消息正文，所以泄漏正文这件事在这一层不可能
    通过"忘了"发生，只可能通过有人**专门加一个形参**发生（那会在 code review
    里显形）。
    """
    import inspect

    params = set(inspect.signature(format_whitelist_rejected_alert).parameters)
    assert params == {"sender", "msgtype", "occurred_at"}
    for leaky in ("text", "content", "text_content", "body", "message"):
        assert leaky not in params


def test_未配置告警通道时整体关闭_只留审计(tmp_path):
    """`alert_send is None`（未配置 `WECOM_WEBHOOK_URL`）⇒ 行为与本次改动前
    逐字相同：不发告警、不写任何告警相关审计。"""
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    asyncio.run(alert_whitelist_rejected(None, audit, "system", XIE_ZHIYA, "text"))
    assert audit.query_by(scenario="wecom-aibot") == []


def test_告警发出后留痕(tmp_path):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    sent: list[str] = []
    asyncio.run(alert_whitelist_rejected(sent.append, audit, "system", XIE_ZHIYA, "text"))

    assert len(sent) == 1
    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert actions == ["whitelist_rejected_alerted"]


def test_告警通道失败不向上抛_只留失败痕(tmp_path):
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")

    def _boom(_text: str) -> None:
        raise RuntimeError("webhook 模拟失败")

    asyncio.run(alert_whitelist_rejected(_boom, audit, "system", XIE_ZHIYA, "text"))

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert actions == ["whitelist_rejected_alert_failed"]


# ─────────── 4. 端到端（tasks 2.4 端到端半 ＋ tasks 3.1／3.2 归档链路） ───────────


def test_端到端_被挡时告警发出且不含正文_审计照常写入(tmp_path):
    """spec「白名单拒绝 SHALL 对我方可见」＋「告警不外泄被拒消息正文」两条
    Scenario 的端到端形态。"""
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}
    alerts: list[str] = []

    build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        client_factory=fake_client_factory(store),
        whitelist_alert_fallback_send=alerts.append,
    )
    asyncio.run(
        store["client"].handlers["message"][0](
            _text_frame("random_colleague", REJECTED_MESSAGE_BODY)
        )
    )

    assert len(alerts) == 1
    assert "random_colleague" in alerts[0]
    assert REJECTED_MESSAGE_BODY not in alerts[0]
    # 正文里任何一个可辨识片段都不该出现
    assert "对账口径" not in alerts[0]

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert actions == ["whitelist_rejected", "whitelist_rejected_alerted"]
    # 拒绝仍是彻底的：不落档、不建行
    assert not any((tmp_path / "7-外部文档").rglob("*.md"))
    assert (tmp_path / "queue.md").read_text(encoding="utf-8") == QUEUE_TEXT


def test_端到端_告警通道不可用不得吞掉拒绝事实(tmp_path):
    """spec「告警通道不可用不得吞掉拒绝事实」Scenario。**次序是判据本身**：
    `whitelist_rejected` 必须在告警失败痕之前、且必须存在。"""
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}

    def _boom(_text: str) -> None:
        raise RuntimeError("webhook 模拟失败")

    build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        client_factory=fake_client_factory(store),
        whitelist_alert_fallback_send=_boom,
    )
    asyncio.run(store["client"].handlers["message"][0](_text_frame("random_colleague")))

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert actions == ["whitelist_rejected", "whitelist_rejected_alert_failed"]
    assert not any((tmp_path / "7-外部文档").rglob("*.md"))


@pytest.mark.parametrize(
    ("sender", "department", "owner"),
    [(LI_JIAOLONG, "财务部", "财务专线"), (XIE_ZHIYA, "采购部", "采购专线")],
)
def test_端到端_放行后归档落对部门且队列行_owner_正确(tmp_path, sender, department, owner):
    """tasks 3.1／3.2：本机可做、不需真人——以新放行的 userid 构造入站帧，验证
    **落 `7-外部文档/<部门>/` 而非 `待分拣/`**，且队列行 owner 正确、**不含**
    「发送人身份待确认」标注（即不重演陈承 07-16→07-22 那个中间态）。"""
    (tmp_path / "queue.md").write_text(QUEUE_TEXT, encoding="utf-8")
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    store: dict = {}

    build_connector(
        secrets=_secrets(),
        audit=audit,
        external_docs_root=tmp_path / "7-外部文档",
        queue_path=tmp_path / "queue.md",
        client_factory=fake_client_factory(store),
    )
    asyncio.run(store["client"].handlers["message"][0](_text_frame(sender, "本月对账已完成")))

    archived = list((tmp_path / "7-外部文档" / department).glob("*.md"))
    assert len(archived) == 1
    assert not (tmp_path / "7-外部文档" / "待分拣").exists()

    queue_text = (tmp_path / "queue.md").read_text(encoding="utf-8")
    new_rows = [ln for ln in queue_text.splitlines() if ln not in QUEUE_TEXT.splitlines()]
    assert len(new_rows) == 1
    assert owner in new_rows[0]
    assert "发送人身份待确认" not in new_rows[0]

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert "archived" in actions
    assert "whitelist_rejected" not in actions
