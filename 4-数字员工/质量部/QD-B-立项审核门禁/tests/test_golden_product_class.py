"""产品类黄金基准（收口-3）—— EQ17（合格）+ 邦奇（不合格）。

样本＝质量专线 2026-07 交付的产品类立项书 + 评审报告（陈忱 AI判断引擎 v5.0 出的答案）。
财务表勾稽 A 类规则（模块六~十：风险系数/成本效益F=D-E/折旧/现金流合计/收益指标）已实现——
本文件是「引擎档位 == 评审报告档位」的严格回归：EQ17 全链无阻断项 → 合格；
邦奇因 driving rule 74（累计现金流末期≠成本效益利润F，相差46.66万）触发一票否决 → 不合格，
与两份评审报告的判定结果一致。

样本在 7-外部文档（LAN/gitignore），缺失自动跳过。
"""
from pathlib import Path

import pytest

from qd_b_gate.parser import ProposalParser
from qd_b_gate.rules.engine import run_rules
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


def test_eq17_matches_report_qualified():
    """EQ17（评审报告=合格 99.2）：引擎判档=合格，无一票否决，财务勾稽规则全部通过。"""
    doc = ProposalParser(_need(EQ17)).parse()
    results = run_rules(doc)
    sc = score(results)
    assert sc.tier == "合格"
    assert sc.veto is False
    by = {r.rule_id: r for r in results}
    # 财务表勾稽核心规则（风险系数/F=D-E/折旧/现金流合计/累计现金流/收益指标）须全部判定通过
    for rid in ("39", "40", "50", "51", "55", "59", "60", "61", "67", "68", "69", "74"):
        assert by[rid].verdict == Verdict.PASS, f"规则{rid} 应通过：{by[rid].evidence}"


def test_bangqi_matches_report_unqualified():
    """邦奇（评审报告=不合格，driving rule=74 累计现金流阻断+69现金流合计）：引擎判档须一致。"""
    doc = ProposalParser(_need(BANGQI)).parse()
    results = run_rules(doc)
    by = {r.rule_id: r for r in results}
    # driving rule：累计现金流末期/现金流合计 均与成本效益利润F不一致（相差约46.66万）
    assert by["74"].verdict == Verdict.FAIL
    assert by["74"].is_blocking
    assert by["69"].verdict == Verdict.FAIL
    # 收益指标未达标（产品类需≥5，邦奇仅1.18）
    assert by["62"].verdict == Verdict.WARN

    sc = score(results)
    assert sc.veto is True
    assert "74" in sc.veto_rules
    assert sc.tier == "不合格"
    assert sc.provisional is True  # 仍有 B/待收口规则未实现，分数暂定不影响本例的一票否决判定
