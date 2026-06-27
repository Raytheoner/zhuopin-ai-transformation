"""QD-B 项目立项审核门禁（开发类 EQQR8082 A2.1）。

数字人对照 82 条规则 + C01–C10 跨模块校验预审开发类立项申请书，
出三档立项审核报告，L2 评审委员会/PMO 复核确认，全链写平台 audit。
"""
from .models import ExtractStatus, FieldValue, ProposalDocument
from .parser import ProposalParser

__all__ = ["ExtractStatus", "FieldValue", "ProposalDocument", "ProposalParser"]
