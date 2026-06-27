"""华丰已填件 · 第一份黄金基准（模块一值抽取）。

技术服务类样本，对照工作汇总.xlsx「立项门禁」K 列试评结果锁定解析正确性。
样本本地脱敏、不入库（缺失自动跳过）。全 13 模块 + 82 规则黄金回归随实现扩展。
"""
from qd_b_gate.models import ExtractStatus
from qd_b_gate.parser import ProposalParser
from qd_b_gate.probe import run_probe


def test_huafeng_sections_and_anchors(huafeng_path):
    """序号锚点对版本差异（封面 A2，模块八/九描述异于空白模板）仍 13/13、定位 100%。"""
    rep = run_probe(huafeng_path)
    assert rep.sections_found == 13
    assert rep.anchor_resolution_rate == 1.0


def test_huafeng_known_values(huafeng_path):
    """对照 K 列试评：项目经理/客户/事业部/类型/开始日期。"""
    doc = ProposalParser(huafeng_path).parse()
    f = lambda k: doc.fields[f"一、项目信息/{k}"].value
    assert f("项目经理") == "谢培雯"
    assert f("客户名称") == "华丰动力股份有限公司"
    assert f("项目所属事业部") == "发动机电控事业部"
    assert f("项目类型") == "技术服务类"
    assert f("开始日期") == "2026-06-15"          # Excel 序列号 46188 → ISO 日期


def test_huafeng_missing_matches_trial(huafeng_path):
    """K 列试评中"未填写/不适用"的字段，解析须为 MISSING（业务空），非误抓。

    规则 11 结束日期 K 列="[不合格]未填写"；项目代号="技术服务类不适用"；项目令系统生成留空。
    """
    doc = ProposalParser(huafeng_path).parse()
    assert doc.fields["一、项目信息/结束日期"].status == ExtractStatus.MISSING
    assert doc.fields["一、项目信息/项目代号"].status == ExtractStatus.MISSING


def test_huafeng_version_mismatch_flagged(huafeng_path):
    """封面嵌入版本 A2 vs 文件名 2.1 的不一致须留痕告警（数据质量问题交陈忱）。"""
    doc = ProposalParser(huafeng_path).parse()
    assert doc.template_version == "A2"
    assert any("版本不一致" in w for w in doc.warnings)
