"""解析器 + 解析探针测试 —— 锁定 design.md D3/D4 行为。

对真实空白 A2.1 模板验证：章节定位、字段锚点定位、MISSING vs NOT_FOUND 区分、
勾选项解析、不把「下一个 label」误抓为字段值（解析探针发现并修复的核心 bug）。
"""
from qd_b_gate.models import ExtractStatus
from qd_b_gate.parser import SECTION_TITLES, ProposalParser
from qd_b_gate.probe import run_probe


def test_detect_template_version(real_a21_path):
    assert ProposalParser(real_a21_path).detect_template_version() == "A2.1"


def test_all_13_sections_located(real_a21_path):
    secs = ProposalParser(real_a21_path).section_rows()
    assert len(secs) == 13
    for title in SECTION_TITLES:
        assert title in secs, f"章节未定位：{title}"
    # 章节按行升序、区间不重叠
    rows = [secs[t] for t in SECTION_TITLES]
    for (a, b), (c, d) in zip(rows, rows[1:]):
        assert a <= b < c <= d


def test_project_info_anchors_all_resolved(real_a21_path):
    """模块一 14 字段锚点应 100% 定位（即便空白模板值为空也算定位成功）。"""
    doc = ProposalParser(real_a21_path).parse()
    info = {k: v for k, v in doc.fields.items() if k.startswith("一、项目信息/")}
    assert len(info) == 14
    not_found = [k for k, v in info.items() if v.status == ExtractStatus.NOT_FOUND]
    assert not_found == [], f"锚点未命中：{not_found}"


def test_blank_template_values_are_missing_not_next_label(real_a21_path):
    """核心回归：空白模板的值字段必须是 MISSING，绝不能把右侧下一个 label 当值。

    （解析探针发现的 bug：'first non-empty right' 会把 '项目名称' 的值抓成 '项目令'。）
    """
    doc = ProposalParser(real_a21_path).parse()
    next_labels = {"项目令", "项目经理", "结束日期", "项目所属事业部", "目标车型/车辆平台",
                   "功能安全目标ASIL", "SOP目标年份/项目结项时间（软件开发项目）"}
    for key in ("项目名称", "项目代号", "客户名称", "开始日期"):
        fv = doc.fields[f"一、项目信息/{key}"]
        assert fv.status == ExtractStatus.MISSING
        assert fv.value is None
        assert _norm(fv.source_cell) != ""           # 值单元格已定位
    # 没有任何字段把下一个 label 文本当作值
    for fv in doc.fields.values():
        assert fv.value not in next_labels, f"{fv.key} 误抓到下一 label：{fv.value}"


def test_checkboxes_parsed_and_bounded(real_a21_path):
    """项目等级 3 项 / 适用法规体系 5 项；项目类型不被当复选框、其选项不污染。"""
    doc = ProposalParser(real_a21_path).parse()
    assert [o for o, _ in doc.checkboxes["项目等级"]] == ["1", "2", "3"]
    fagui = [o for o, _ in doc.checkboxes["适用法规/体系"]]
    assert fagui == ["无", "ISO26262", "ISO21434", "IATF16949", "CMMI4"]
    # 项目类型 是文本单选，不应出现在复选框里
    assert "项目类型" not in doc.checkboxes
    # 适用法规的选项没有被项目类型行污染（边界停止生效）
    assert "产品类" not in fagui and "技术服务类" not in fagui


def test_probe_gate_blank_template(real_a21_path):
    """解析探针 D4 门槛：空白模板锚点定位率 100%、章节 13/13。"""
    rep = run_probe(real_a21_path)
    assert rep.template_version == "A2.1"
    assert rep.sections_found == 13
    assert rep.anchor_resolution_rate == 1.0
    assert rep.not_found == 0
    assert len(rep.pending_modules) == 12      # 仅模块一已实现


def _norm(s):
    return "" if s is None else str(s).strip()


# ---- 模块四：项目目标三列表（档三 C06/C07 的取数侧，队列 #340③） ----

def test_module4_objectives_parsed_from_blank_template(real_a21_path):
    """空白模板：6 个固定标签全在册，且模板自带的「…」占位行不得被当成一条目标。"""
    doc = ProposalParser(real_a21_path).parse()
    rows = doc.tables["项目目标"]
    labels = [r["目标类型"] for r in rows]
    assert labels == ["硬件技术目标", "软件技术目标", "质量目标", "专利",
                      "功能安全目标（如有）", "信息安全目标（如有）"]
    assert "…" not in labels          # 省略号是填写骨架，不是数据行


def test_module4_keeps_custom_rows_appended_after_the_fixed_labels(huafeng_path):
    """🔴 华丰在 6 个固定标签之后追加了 3 行自定义「目标类型」，且都带实质内容。

    若按"固定标签硬编码"取行，这 3 行会被**静默丢弃**——而且因为 C06/C07 只关心其中
    两个固定标签，**连测试都不会发现**（判例素材 2026-08-18 §五）。本条即为此而设：
    固定标签只用于定位、不用于过滤。
    """
    doc = ProposalParser(huafeng_path).parse()
    labels = [r["目标类型"] for r in doc.tables["项目目标"]]
    assert len(labels) == 9                      # 6 固定 + 3 自定义
    assert "EPA认证" in labels
    assert "后处理选型方案及后处理供应商选型" in labels
    detail = next(r for r in doc.tables["项目目标"]
                  if r["目标类型"] == "后处理选型方案及后处理供应商选型")["详细指标"]
    assert detail                                # 自定义行的内容也须取到，不能只留标签


def test_risk_table_now_carries_the_milestone_column(huafeng_path):
    """C05 取数侧：风险表「所属里程碑」列（四份文件恒为第 4 列）。"""
    doc = ProposalParser(huafeng_path).parse()
    rows = doc.tables["风险"]
    assert rows and all("所属里程碑" in r for r in rows)
    assert [r["所属里程碑"] for r in rows] == ["项目立项"] * 3
