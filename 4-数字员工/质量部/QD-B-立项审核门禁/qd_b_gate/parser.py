"""立项申请书解析器（intake-parser）。

把 EQQR8082 A2.1 合并单元格 Excel 表单解析为 ProposalDocument。

设计纪律（design.md D3/D4）：
- 取数锚「章节标题文本」，不锚绝对单元格坐标（模板一月四版）。
- 合并单元格按左上锚点值展开。
- 字段抽取状态显式标记，区分"业务空"与"解析未命中"。

doc_parser 当前仅 QD-B 一个真实消费方（QD-A/8D 尚未建），按 rule-of-three
暂留本场景，预留干净接口；第 2 真实消费方出现再提升进 shared_tools。
"""
from __future__ import annotations

import re
from pathlib import Path

import openpyxl
from openpyxl.utils import coordinate_to_tuple, get_column_letter

from .models import ExtractStatus, FieldValue, ProposalDocument

# 13 模块章节标题（按 A2.1 真实模板正文，非规则表的简称）。
# 取数锚这些文本；用「以…开头」匹配，吸收尾随空格/全半角差异。
SECTION_TITLES = [
    "一、项目信息",
    "二、立项依据",
    "三、项目的目的和意义",
    "四、项目目标",
    "五、关键技术与开发能力评估",
    "六、项目风险分析",
    "七、项目所需资源采购计划",
    "八、项目成本及收益分析",
    "九、项目里程碑计划与阶段预算规划",
    "十、项目现金流分析",
    "十一、项目团队成员",
    "十二、总结",
    "十三、立项决议",
]


def _norm(s) -> str:
    """规范化文本：去空白、全角空格、首尾标点空格，便于锚点匹配。"""
    if s is None:
        return ""
    return str(s).replace("　", " ").strip()


class ProposalParser:
    """按章节标题锚点解析立项书。"""

    def __init__(self, path: str | Path):
        self.path = str(path)
        self.wb = openpyxl.load_workbook(path, data_only=True)
        self.ws = self._pick_sheet()
        # 合并区域：左上坐标 -> range 对象；坐标 -> 左上坐标（值解析用）
        self._merge_anchor: dict[str, str] = {}
        for rng in self.ws.merged_cells.ranges:
            tl = rng.coord.split(":")[0]
            for row in range(rng.min_row, rng.max_row + 1):
                for col in range(rng.min_col, rng.max_col + 1):
                    self._merge_anchor[f"{get_column_letter(col)}{row}"] = tl

    def _pick_sheet(self):
        for name in self.wb.sheetnames:
            if "立项申请书" in name and "开发" in name:
                return self.wb[name]
        # 退路：最大的工作表
        return max(self.wb.worksheets, key=lambda w: (w.max_row or 0) * (w.max_column or 0))

    # ---------- 基础取值 ----------
    def cell(self, coord: str):
        """读单元格，自动解析合并区域到左上锚点值。"""
        anchor = self._merge_anchor.get(coord, coord)
        return self.ws[anchor].value

    def _value_adjacent(self, coord: str) -> tuple[object, str]:
        """读 label 单元格紧邻右侧的「值单元格」（label 合并跨度结束列+1）。

        关键纪律（解析探针经验）：取「紧邻」单元格而非「向右第一个非空」——
        否则空白模板里值为空时会误抓到右边的下一个 label。值为空 → 返回
        (None, 坐标)，由调用方判为 MISSING（业务空），与 NOT_FOUND 区分。
        """
        r, c = coordinate_to_tuple(coord)
        start = c + 1
        rng = self._range_of(coord)
        if rng is not None:
            start = rng.max_col + 1
        cc = f"{get_column_letter(start)}{r}"
        v = self.cell(cc)
        src = self._merge_anchor.get(cc, cc)
        if v is None or _norm(v) == "":
            return None, src
        return v, src

    def _range_of(self, coord: str):
        anchor = self._merge_anchor.get(coord, coord)
        for rng in self.ws.merged_cells.ranges:
            if rng.coord.split(":")[0] == anchor:
                return rng
        return None

    def find_label(self, text: str, row_range: tuple[int, int] | None = None) -> str | None:
        """在（可选行范围内）按文本找 label 单元格坐标。以 norm 后「相等或以之开头」匹配。"""
        t = _norm(text)
        lo, hi = row_range or (1, self.ws.max_row)
        for row in self.ws.iter_rows(min_row=lo, max_row=hi):
            for cell in row:
                cv = _norm(cell.value)
                if cv and (cv == t or cv.startswith(t)):
                    return cell.coordinate
        return None

    # ---------- 章节定位 ----------
    def section_rows(self) -> dict[str, tuple[int, int]]:
        """返回各章节标题 -> (起始行, 结束行)。结束行 = 下一章节起始行-1。"""
        starts: list[tuple[str, int]] = []
        for title in SECTION_TITLES:
            coord = self.find_label(title)
            if coord:
                starts.append((title, coordinate_to_tuple(coord)[0]))
        starts.sort(key=lambda x: x[1])
        out: dict[str, tuple[int, int]] = {}
        for i, (title, row) in enumerate(starts):
            end = starts[i + 1][1] - 1 if i + 1 < len(starts) else self.ws.max_row
            out[title] = (row, end)
        return out

    def detect_template_version(self) -> str:
        """从封面/履历或标题识别模板版本（A0/A1/A2/A2.1）。"""
        for name in self.wb.sheetnames:
            ws = self.wb[name]
            for row in ws.iter_rows(min_row=1, max_row=min(40, ws.max_row or 1)):
                for cell in row:
                    m = re.search(r"A2\.1|A2(?!\.)|A1\b|A0\b|EQQR8082", _norm(cell.value))
                    if m and "A2.1" in _norm(cell.value):
                        return "A2.1"
        # 文件名兜底
        if "A2.1" in self.path:
            return "A2.1"
        return "unknown"

    # ---------- 主入口 ----------
    def parse(self) -> ProposalDocument:
        doc = ProposalDocument(source_path=self.path)
        doc.template_version = self.detect_template_version()
        if doc.template_version != "A2.1":
            doc.warnings.append(
                f"模板版本={doc.template_version}，MVP 仅适配 A2.1，按 A2.1 锚点解析可能偏差，需人工核"
            )
        secs = self.section_rows()
        missing_secs = [t for t in SECTION_TITLES if t not in secs]
        if missing_secs:
            doc.warnings.append(f"未定位到章节：{missing_secs}")

        self._parse_project_info(doc, secs.get("一、项目信息"))
        return doc

    # ---------- 模块一：项目信息 ----------
    # label 文本 -> 规范字段键（吸收尾随空格）
    INFO_FIELDS = {
        "项目名称": "项目名称",
        "项目令": "项目令",
        "客户CTS/SOR版本号": "客户CTS/SOR版本号",
        "项目代号": "项目代号",
        "项目经理": "项目经理",
        "目标车型/车辆平台": "目标车型/车辆平台",
        "客户名称": "客户名称",
        "项目所属事业部": "项目所属事业部",
        "SOP目标年份": "SOP目标年份/项目结项时间",
        "开始日期": "开始日期",
        "结束日期": "结束日期",
        "功能安全目标ASIL": "功能安全目标ASIL",
        "预算总工时": "预算总工时",
        "项目类型": "项目类型",          # 产品类/技术服务类（文本/单选，非 True/False 复选框）
    }

    # 复选框字段（True/False 成对）。项目类型不在此列 —— 它是文本单选，走普通取值。
    CHECKBOX_FIELDS = ["项目等级", "适用法规/体系"]

    def _parse_project_info(self, doc: ProposalDocument, rng: tuple[int, int] | None):
        if rng is None:
            doc.warnings.append("模块一未定位，项目信息字段全部 NOT_FOUND")
            return
        for label_text, key in self.INFO_FIELDS.items():
            coord = self.find_label(label_text, rng)
            fkey = f"一、项目信息/{key}"
            if coord is None:
                doc.fields[fkey] = FieldValue(key=fkey, status=ExtractStatus.NOT_FOUND,
                                              anchor=label_text, reason="标题锚点未命中")
                continue
            value, src = self._value_adjacent(coord)
            if value is None:
                doc.fields[fkey] = FieldValue(key=fkey, status=ExtractStatus.MISSING,
                                              anchor=label_text, source_cell=src,
                                              reason="锚点命中但值为空")
            else:
                doc.fields[fkey] = FieldValue(key=fkey, value=_norm(value),
                                              status=ExtractStatus.EXTRACTED,
                                              anchor=label_text, source_cell=src)

        # 勾选项：项目等级 / 适用法规体系 — True/False 成对，扫描止于下一 label
        for cb in self.CHECKBOX_FIELDS:
            self._parse_checkbox_row(doc, cb, rng)

    def _is_stop_label(self, value) -> bool:
        """该单元格是否是「另一个字段/章节标题」—— 复选框扫描遇到它即停。"""
        t = _norm(value)
        if not t:
            return False
        stops = set(self.INFO_FIELDS.keys()) | set(self.CHECKBOX_FIELDS) | set(SECTION_TITLES)
        return any(t == s or t.startswith(s) for s in stops)

    def _parse_checkbox_row(self, doc: ProposalDocument, label_text: str,
                            rng: tuple[int, int]):
        """解析同一行的复选框：扫 label 所在行，True/False 后跟选项文本；遇到下一 label 停。"""
        coord = self.find_label(label_text, rng)
        if coord is None:
            doc.warnings.append(f"勾选项「{label_text}」标题未命中")
            return
        r, c = coordinate_to_tuple(coord)
        options: list[tuple[str, bool]] = []
        cells = [self.ws.cell(row=r, column=col) for col in range(c + 1, self.ws.max_column + 1)]
        i = 0
        while i < len(cells):
            v = cells[i].value
            if isinstance(v, bool):
                opt = ""
                if i + 1 < len(cells) and _norm(cells[i + 1].value):
                    opt = _norm(cells[i + 1].value)
                options.append((opt, bool(v)))
                i += 2
            elif self._is_stop_label(v):
                break          # 撞到下一个字段标题（如「适用法规/体系」），停止
            else:
                i += 1
        if options:
            doc.checkboxes[label_text] = options
