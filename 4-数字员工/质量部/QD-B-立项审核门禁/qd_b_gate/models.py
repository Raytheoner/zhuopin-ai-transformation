"""QD-B 立项审核门禁 —— 结构化数据模型。

立项申请书（EQQR8082 A2.1）是合并单元格 Excel 表单（A1:Z145、376 个 merge）。
解析器把它转成本模块的结构化模型，规则引擎/语义判定/报告聚合在此之上工作。

设计要点（对齐 design.md / specs）：
- 每个字段带「抽取状态」(extracted / missing / low_confidence)，区分
  "字段真为空（规则判不合格）" 与 "解析未抽到（解析探针待人工核）"。
- 取数锚「章节标题文本」，模型保留 source_cell 便于审计回溯与改版适配。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ExtractStatus(str, Enum):
    """字段抽取状态 —— 解析探针的核心产物。"""
    EXTRACTED = "extracted"        # 锚点命中且有明确值
    MISSING = "missing"            # 锚点命中但值为空（可能是"必填为空"，交规则判）
    NOT_FOUND = "not_found"        # 锚点未命中（解析问题，待人工核，≠ 业务空）
    LOW_CONFIDENCE = "low_conf"    # 合并单元格歧义/多候选，低置信


@dataclass
class FieldValue:
    """单个字段的抽取结果。"""
    key: str                       # 规范字段键，如 "一、项目信息/项目经理"
    value: Any = None              # 抽取到的原始值（已 strip）
    status: ExtractStatus = ExtractStatus.NOT_FOUND
    source_cell: str = ""          # 取数单元格坐标（审计/改版适配）
    anchor: str = ""               # 命中的章节/字段标题文本
    reason: str = ""               # 缺失/低置信原因

    @property
    def is_empty(self) -> bool:
        """业务意义上的"空"：抽到了锚点但没值。NOT_FOUND 不算业务空（是解析问题）。"""
        return self.status == ExtractStatus.MISSING

    @property
    def is_present(self) -> bool:
        return self.status == ExtractStatus.EXTRACTED and self.value not in (None, "")


@dataclass
class ProposalDocument:
    """一份解析后的立项申请书。"""
    template_version: str = "unknown"     # A0 / A1 / A2 / A2.1
    project_type: str = ""                # 产品类 / 技术服务类（驱动适用规则集）
    source_path: str = ""

    # 普通 label→value 字段，键 = "章节/字段"
    fields: dict[str, FieldValue] = field(default_factory=dict)
    # 文本区域模块（立项依据 / 目的意义 / 技术总结 / 商务总结），键 = 模块名
    text_areas: dict[str, FieldValue] = field(default_factory=dict)
    # 勾选项（项目等级 / 适用法规体系 / ASIL / 立项决议），键 = 字段名 → [(选项, 是否勾选)]
    checkboxes: dict[str, list[tuple[str, bool]]] = field(default_factory=dict)
    # 表格区域，键 = 表名 → 行记录列表（保留列名）
    tables: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    # 解析诊断（解析探针报告用）
    warnings: list[str] = field(default_factory=list)

    # ---- 取值便捷方法 ----
    def get(self, key: str) -> FieldValue:
        return self.fields.get(key, FieldValue(key=key, status=ExtractStatus.NOT_FOUND,
                                               reason="字段未在解析结果中"))

    def table(self, name: str) -> list[dict[str, Any]]:
        return self.tables.get(name, [])

    def checked_options(self, name: str) -> list[str]:
        return [opt for opt, ck in self.checkboxes.get(name, []) if ck]
