"""产品类黄金基准（收口-3）—— EQ17（合格）+ 邦奇（不合格）。

样本＝质量专线 2026-07 交付的产品类立项书 + 评审报告（陈忱 AI判断引擎 v5.0 出的答案）。
本文件先锁定「解析可用 + 判档缺口」基线：现引擎仅实现模块一 A 类（18/68），
产品类判档所需的财务表勾稽规则（69 现金流合计/74 累计现金流/60 全生命周期毛利率
/61-62 收益指标）尚未实现——故邦奇「不合格」暂无法复现（driving rule 74 PENDING）。
财务规则落地后，本基线转为「引擎档位 == 评审报告档位」的严格回归。

样本在 7-外部文档（LAN/gitignore），缺失自动跳过。
"""
from pathlib import Path

import pytest

from qd_b_gate.parser import ProposalParser
from qd_b_gate.rules.engine import run_rules
from qd_b_gate.rules.registry import load_registry
from qd_b_gate.models import Verdict
from qd_b_gate.scoring import score

PC_DIR = Path("C:/Users/Paul Shao/OneDrive/Projects/企业AI转型/7-外部文档/质量部/"
              "产品类立项申请书及评审报告")
EQ17 = PC_DIR / "EQ17匹配VM发动机开发项目立项申请书（合格）.xlsx"
BANGQI = PC_DIR / "邦奇新一代TCU合作开发项目立项申请书（不合格）.xlsx"


def _need(p: Path) -> str:
    if not p.exists():
        pytest.skip(f"产品类样本不在预期路径（LAN/gitignore）：{p}")
    return str(p)


def test_product_class_parses():
    """两份产品类立项书均应解析为 产品类 + 13/13 章节。"""
    for p in (EQ17, BANGQI):
        doc = ProposalParser(_need(p)).parse()
        assert doc.project_type == "产品类"
        assert len(ProposalParser(_need(p)).section_rows()) == 13


def test_eq17_currently_qualified():
    """EQ17（评审报告=合格 99.2）：现引擎已实现规则无一失败 → 暂定合格，与档位一致。"""
    doc = ProposalParser(_need(EQ17)).parse()
    sc = score(run_rules(doc))
    assert sc.tier == "合格"


def test_bangqi_gap_documented():
    """邦奇（评审报告=不合格）：driving rule 74 累计现金流一致=阻断，但尚未实现（PENDING）。

    锁定缺口：现引擎因 rule 74 未实现而误判「暂定合格」；财务规则落地后应转为不合格。
    """
    reg = load_registry()
    assert reg.get(74).blocking is True            # 74 已是阻断（20260710 权威）
    doc = ProposalParser(_need(BANGQI)).parse()
    by = {r.rule_id: r for r in run_rules(doc)}
    assert by["74"].verdict == Verdict.PENDING     # 尚未实现 → 记为缺口
    assert by["69"].verdict == Verdict.PENDING     # 现金流合计一致 亦未实现
    # 现引擎暂定合格（因阻断项未实现），provisional 必为真——不冒判为终局
    sc = score(run_rules(doc))
    assert sc.provisional is True
