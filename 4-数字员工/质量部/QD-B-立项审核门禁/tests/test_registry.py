"""规则注册表测试 —— 锁定 82 条规则元数据与三分类（design.md D2/D8）。"""
from qd_b_gate.rules import load_registry


def test_registry_has_82_rules():
    reg = load_registry()
    assert len(reg) == 82


def test_class_split_68_10_4():
    """工作汇总.xlsx 自动化列三分类：68 可机器核 / 10 半自动 / 4 转人工。"""
    reg = load_registry()
    counts = reg.counts()
    assert counts == {"A": 68, "B": 10, "C": 4}


def test_severity_map_blocking():
    """阻断/重要 → 错误（一票否决）；一般 → 警告；提示 → 提示。"""
    reg = load_registry()
    assert reg.severity_map["阻断"] == "错误"
    assert reg.severity_map["提示"] == "提示"
    # 阻断级规则一定 blocking
    r1 = reg.get(1)                       # 项目名称（阻断）
    assert r1.severity == "阻断" and r1.blocking is True
    r2 = reg.get(2)                       # 项目令（提示）
    assert r2.severity == "提示" and r2.blocking is False


def test_known_rules_present():
    reg = load_registry()
    # 收益指标（规则 61/62，阻断，合规阈值）
    assert reg.get(61).check_item == "收益指标"
    assert reg.get(61).blocking is True
    # 半自动语义规则（规则 20 立项依据"是什么"）属 B 类
    assert reg.get(20).impl_class == "B"
    # 转人工（规则 80 项目经理签字）属 C 类
    assert reg.get(80).impl_class == "C"


def test_rule_version_recorded():
    reg = load_registry()
    assert reg.rule_version          # 非空，随表更新登记
    assert "立项门禁" in load_registry().source or reg.source
