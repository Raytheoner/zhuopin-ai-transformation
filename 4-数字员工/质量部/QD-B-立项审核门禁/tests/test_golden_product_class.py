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
from qd_b_gate.rules.engine import run_all, run_rules
from qd_b_gate.models import Verdict
from qd_b_gate.report import build_report
from qd_b_gate.scoring import score

PC_DIR = Path("C:/Dev/zhuopin-ai/7-外部文档/质量部/"
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


class TestFullPipelineWithManualAndSemanticClasses:
    """run_all()（A+C转人工+B语义占位）+ build_report() 全链回归（任务 6.1/6.2/6.7）。

    锁定：新增的 C 类 42/80/81/82 在两份真实（已签字/已填应对措施）样本上只应产出
    「转人工/不适用」，不得引入新的一票否决或扣分——即"黄金基准不漂移"。
    """

    def test_eq17_full_pipeline_still_qualified(self):
        doc = ProposalParser(_need(EQ17)).parse()
        results = run_all(doc)
        rep = build_report(doc, results=results, sample_id="EQ17")
        assert rep.verdict == "合格"
        assert rep.blocking_items == []
        by = {r.rule_id: r for r in results}
        assert by["80"].verdict == Verdict.MANUAL
        assert by["81"].verdict == Verdict.MANUAL
        assert by["82"].verdict == Verdict.NA
        assert by["42"].verdict == Verdict.MANUAL
        assert len(results) == 82

    def test_bangqi_full_pipeline_still_unqualified_same_driving_rule(self):
        doc = ProposalParser(_need(BANGQI)).parse()
        results = run_all(doc)
        rep = build_report(doc, results=results, sample_id="邦奇")
        assert rep.verdict == "不合格"
        # 一票否决驱动规则不变（仍是财务勾稽 74，不是新增的 C 类签字/应对措施规则）
        assert [r.rule_id for r in rep.blocking_items] == ["74"]
        by = {r.rule_id: r for r in results}
        assert by["80"].verdict == Verdict.MANUAL
        assert by["81"].verdict == Verdict.MANUAL
        # B 类 10 条 + C 类 42/80/81 均落入转人工待办（82 恒 NA，不计入待办）
        assert len(rep.manual_todo_items) == 13


class TestCrossModuleZeroScoreDrift:
    """C01–C10 落地后的"零分数漂移可证"回归（变更包 qd-b-cross-module-check）。

    `scoring.py::score()` 只遍历 registry 的 82 条，C01–C10 不在其内；只要跨模块结果
    不并进 `results`，总分与档位在数学上不可能变。本类把这条"可证"钉成回归断言：
    真值取自 `data/golden/manifest.md` 与场景 CLAUDE.md §7 冒烟记录。
    """

    #: 🔴 **已签认**的黄金基准（＝`data/golden/manifest.md` 真值）。
    #: 未经 Shao Peishen 签认不得改动本常量——它与 manifest 是同一份真值的两个副本，
    #: 改了这里而没改 manifest（或反之）就等于黄金基准无声地移动了一半。
    #:
    #: EQ17 `98.80 → 100.00`：Shao Peishen 2026-08-25 签认（队列 §四 #112 选 (a)，本行已销号），
    #: 依据件＝`docs/基准变更说明-规则12并入无-2026-08-25.md`。EQ17 的 `ASIL=无` 此前不在
    #: 规则 12 同义词集内、被判「待改进」扣 1.20 分——那是一条**误判**（评审委员会判它合格），
    #: 陈忱 2026-08-21 Q2 裁定「无」视同 NA 后修掉。**不是口径放宽，档位仍为合格。**
    #: 华丰 96.44／邦奇 94.89 与三份的档位、一票否决驱动规则 before/after 全不变（实测对照
    #: `ac38bec` vs `734ee18` 两个 checkout，见队列 #340 本次回写段）。
    GOLDEN = {"EQ17": ("合格", 100.00, []), "邦奇": ("不合格", 94.89, ["74"])}

    @pytest.mark.parametrize("name, path", [("EQ17", EQ17), ("邦奇", BANGQI)])
    def test_tier_and_veto_unchanged_after_cross_module(self, name, path):
        """档位与一票否决是硬断言——本次改动**不得**移动这两者。

        得分单独一条断言（见下），因为它确实会因规则 12 修正而移动，须走签认闸。
        """
        doc = ProposalParser(_need(path)).parse()
        results = run_all(doc)
        sr = score(results)
        rep = build_report(doc, results=results, score_result=sr, sample_id=name)
        tier, _total, veto = self.GOLDEN[name]
        assert rep.verdict == tier
        assert sr.veto_rules == veto
        assert len(results) == 82          # 跨模块条目未混入 82 条结果集

    @pytest.mark.parametrize("name, path", [("EQ17", EQ17), ("邦奇", BANGQI)])
    def test_total_score_matches_the_signed_golden_baseline(self, name, path):
        """签认闸已开（Shao Peishen 2026-08-25，§四 #112）——EQ17 按新基准 100.00 硬断言。

        闸未开期间本条曾挂 `xfail(strict=True)` 作为「闸还锁着」的可见信号；签认落地时
        三处（manifest／`GOLDEN`／本标记）同批处置，标记已摘、不留在代码里。
        """
        doc = ProposalParser(_need(path)).parse()
        sr = score(run_all(doc))
        assert round(sr.total_score, 2) == self.GOLDEN[name][1]

    @pytest.mark.parametrize("name, path", [("EQ17", EQ17), ("邦奇", BANGQI)])
    def test_cross_module_items_stay_out_of_every_scored_list(self, name, path):
        doc = ProposalParser(_need(path)).parse()
        results = run_all(doc)
        rep = build_report(doc, results=results, sample_id=name)
        cross_ids = {i.rule_id for i in rep.cross_module_items}
        assert cross_ids == {f"C{n:02d}" for n in range(1, 11)}
        for bucket in (rep.all_results, rep.blocking_items,
                       rep.warning_items, rep.manual_todo_items):
            assert not (cross_ids & {r.rule_id for r in bucket})

    def test_eq17_reproduces_the_start_date_gap_found_in_the_340_assessment(self):
        """#340 评估件实测：EQ17 项目开始 2026-06-01 vs 首阶段开始 2026-05-29，差 3 天。"""
        doc = ProposalParser(_need(EQ17)).parse()
        rep = build_report(doc, results=run_all(doc), sample_id="EQ17")
        c04 = next(i for i in rep.cross_module_items if i.rule_id == "C04")
        assert c04.verdict == Verdict.WARN
        assert "2026-06-01" in c04.evidence and "2026-05-29" in c04.evidence

    def test_bangqi_reproduces_the_cost_gap_found_in_the_340_assessment(self):
        """#340 评估件实测：邦奇成本 E 131.96 万 vs 小计⑩和 85.298 万，差 46.662 万。

        与已知 driving rule 74/69 缺口同源——是同一处缺陷的第二条独立检出路径。
        """
        doc = ProposalParser(_need(BANGQI)).parse()
        rep = build_report(doc, results=run_all(doc), sample_id="邦奇")
        c02 = next(i for i in rep.cross_module_items if i.rule_id == "C02")
        assert c02.verdict == Verdict.WARN
        assert "46.662" in c02.evidence
