"""审核层 —— 骨架期整层都在前置闸后面，**刻意没有任何可用实现**。

保留本模块（而不是等前置到位再建）有两个作用：
① 把「哪些能力被卡住了」变成可执行、可被测试断言的事实，而不是一句 README 里的说明；
② 让调用方现在就能把接口签名固定下来——前置到位后补的是函数体，不是调用方。
"""
from __future__ import annotations

from typing import Any

from . import pending
from .models import ExtractionResult


def compare_with_standard(result: ExtractionResult) -> list[dict[str, Any]]:
    """与公司标准条款库比对、标出偏差项。

    前置＝标准条款库（法务＋采购，前置总表 §一 `SC4` 行）。
    """
    pending.require("standard_clause_library")
    raise AssertionError("unreachable")  # pragma: no cover - require() 恒抛


def grade_risk(result: ExtractionResult) -> list[dict[str, Any]]:
    """给偏差项打风险等级。

    前置＝合同风险条款判据（法务，前置总表 §一.2；backup 待点名）。
    """
    pending.require("risk_clause_criteria")
    raise AssertionError("unreachable")  # pragma: no cover - require() 恒抛


def detect_missing_clauses(result: ExtractionResult) -> list[dict[str, Any]]:
    """识别缺失条款（如缺 IATF 追溯要求、缺保密协议）。

    前置＝标准条款库（"本该有哪几类"只能由它定义）。
    """
    pending.require("standard_clause_library")
    raise AssertionError("unreachable")  # pragma: no cover - require() 恒抛
