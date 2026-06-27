"""解析探针（design.md D4）—— 立项书的第一刀。

在写 82 条规则判定前，先验「能否从合并单元格表单稳定抽出每个字段」。
产出字段抽取覆盖报告（章节命中 / 字段锚点命中 / 缺失 / 低置信 / 未命中），
作为规则全量判定的前置门槛：抽取准确率不达约定阈值则停下复盘解析，
不在不可靠的解析之上空跑规则。

注意：对「空白模板」探针衡量的是「锚点定位」能力（字段能否被定位到值单元格）；
「值抽取」准确率需用「已填写样本」（陈忱黄金样本 / 收口-3）测。两者都要过。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .models import ExtractStatus, ProposalDocument
from .parser import SECTION_TITLES, ProposalParser

# 已实现解析的模块（随 parser 扩展逐步加入）。
IMPLEMENTED_MODULES = ["一、项目信息"]
PENDING_MODULES = [s for s in SECTION_TITLES if s not in IMPLEMENTED_MODULES]


@dataclass
class ProbeReport:
    source: str
    template_version: str
    sections_found: int
    sections_total: int
    located: int = 0          # 锚点命中（字段被定位，含值空）
    extracted: int = 0        # 命中且有值
    missing: int = 0          # 命中但值空（业务空）
    not_found: int = 0        # 锚点未命中（解析问题）
    low_conf: int = 0
    total_fields: int = 0
    warnings: list[str] = field(default_factory=list)
    pending_modules: list[str] = field(default_factory=list)
    field_detail: list[dict] = field(default_factory=list)

    @property
    def anchor_resolution_rate(self) -> float:
        """锚点定位率 = 命中(含空) / 总字段。空白模板用此衡量解析可行性。"""
        return self.located / self.total_fields if self.total_fields else 0.0

    @property
    def value_extraction_rate(self) -> float:
        """值抽取率 = 抽到值 / 总字段。需用已填样本衡量才有意义。"""
        return self.extracted / self.total_fields if self.total_fields else 0.0

    def summary(self) -> str:
        lines = [
            f"解析探针报告  ({Path(self.source).name})",
            f"  模板版本        : {self.template_version}",
            f"  章节定位        : {self.sections_found}/{self.sections_total}",
            f"  字段锚点定位率  : {self.anchor_resolution_rate:.0%} "
            f"({self.located}/{self.total_fields})",
            f"  值抽取率        : {self.value_extraction_rate:.0%} "
            f"(空白模板为 0 属正常；需已填样本衡量)",
            f"  状态分布        : 抽到值 {self.extracted} / 业务空 {self.missing} "
            f"/ 未命中 {self.not_found} / 低置信 {self.low_conf}",
            f"  未实现解析模块  : {len(self.pending_modules)} → {self.pending_modules}",
        ]
        if self.warnings:
            lines.append("  warnings:")
            lines += [f"    ! {w}" for w in self.warnings]
        return "\n".join(lines)


def run_probe(path: str | Path) -> ProbeReport:
    parser = ProposalParser(path)
    doc: ProposalDocument = parser.parse()
    secs = parser.section_rows()

    rep = ProbeReport(
        source=str(path),
        template_version=doc.template_version,
        sections_found=len(secs),
        sections_total=len(SECTION_TITLES),
        warnings=list(doc.warnings),
        pending_modules=list(PENDING_MODULES),
    )
    for fkey, fv in doc.fields.items():
        rep.total_fields += 1
        if fv.status == ExtractStatus.EXTRACTED:
            rep.extracted += 1
            rep.located += 1
        elif fv.status == ExtractStatus.MISSING:
            rep.missing += 1
            rep.located += 1          # 锚点命中（值单元格被定位），只是值空
        elif fv.status == ExtractStatus.LOW_CONFIDENCE:
            rep.low_conf += 1
            rep.located += 1
        else:
            rep.not_found += 1
        rep.field_detail.append({
            "field": fkey, "status": fv.status.value,
            "value": fv.value, "source_cell": fv.source_cell, "reason": fv.reason,
        })
    return rep


def main():
    import sys
    default = (Path(__file__).resolve().parent.parent
               / "../../../7-外部文档/质量部/EQQR8082立项申请书（开发类）-A2.1.xlsx")
    path = sys.argv[1] if len(sys.argv) > 1 else str(default)
    rep = run_probe(path)
    print(rep.summary())


if __name__ == "__main__":
    main()
