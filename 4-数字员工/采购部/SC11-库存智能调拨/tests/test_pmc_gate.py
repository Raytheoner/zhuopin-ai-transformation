"""PMC 确认门禁 —— 本骨架期唯一一条实心红线，测试写在最前面。"""
from __future__ import annotations

import pytest

from sc11_transfer import gate
from sc11_transfer.models import TransferPlanDraft


@pytest.fixture
def draft() -> TransferPlanDraft:
    return TransferPlanDraft()


def test_未确认时落ERP即抛并点名门禁来源(draft):
    with pytest.raises(gate.PmcApprovalRequired) as ei:
        gate.commit_to_erp(draft)
    assert "采购专线 2026-07-06" in str(ei.value)


def test_未确认时外发邮件即抛(draft):
    with pytest.raises(gate.PmcApprovalRequired):
        gate.notify_outsourced_warehouse(draft)


def test_确认须实名而非布尔(draft):
    with pytest.raises(ValueError, match="可归责人"):
        gate.approve(draft, "   ")


def test_确认后仍不静默执行而是如实报通道未接(draft):
    gate.approve(draft, "李PMC")
    assert draft.is_approved
    # "确认过了"和"能执行了"是两件事；静默 no-op 会产出一条『落库成功』而 ERP 里什么都没有
    with pytest.raises(gate.NotWiredYet):
        gate.commit_to_erp(draft)
    with pytest.raises(gate.NotWiredYet):
        gate.notify_outsourced_warehouse(draft)


def test_门禁不接受任何旁路参数(draft):
    # 一个能被参数关掉的门禁，在下一次赶工时就会被关掉。此处断言执行侧函数
    # 只接受 draft 一个入参，没有 force / already_confirmed 之类的开关。
    import inspect

    for fn in (gate.commit_to_erp, gate.notify_outsourced_warehouse):
        params = list(inspect.signature(fn).parameters)
        assert params == ["draft"], f"{fn.__name__} 出现了旁路参数：{params}"


def test_外发授权与调拨确认是两道授权(draft):
    gate.approve(draft, "李PMC")
    with pytest.raises(gate.NotWiredYet, match="两件事、两道授权"):
        gate.notify_outsourced_warehouse(draft)
