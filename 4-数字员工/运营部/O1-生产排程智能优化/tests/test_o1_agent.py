"""测试 O1 场景入口 run_smt_schedule（tasks 5.4-5.7）。

覆盖 spec `o1-smt-schedule-agent` 的三条 Requirement：
  · 排产结果写平台审计
  · 真实数据源未就绪时须显式失败
  · 推算结果须标明其可信边界
"""
from datetime import date

import pytest

from zhuopin_platform.shared_tools.models import ProductionPlan
from zhuopin_platform.shared_tools.connector_errors import RealEndpointNotReadyError

from o1_smt_scheduling.agent import run_smt_schedule, ScheduleResult


# ── 夹具（inline dict，自包含不依赖外部文件；design D6）─────────────────────

def _plans():
    """两张真实料号的工单，第三张用一个不在工时表里的料号，用于覆盖分项返回。"""
    return [
        ProductionPlan("MO001", "F02N.0040", "EQ02-DW-C1", 100, "2026-06-20"),
        ProductionPlan("MO002", "F02N.0064", "EQ47-P1", 50, "2026-06-22"),
        ProductionPlan("MO003", "X99N.9999", "查无此料", 10, "2026-06-25"),
    ]


def _arrivals():
    return {
        # F02N.0040 齐料日 = 6/10（取最迟）→ +7 → 6/17
        "F02N.0040": {"M001": date(2026, 6, 1), "M002": date(2026, 6, 10)},
        # F02N.0064 齐料日 = 6/5 → +7 → 6/12
        "F02N.0064": {"M003": date(2026, 6, 5)},
        # X99N.9999 有到货但无工时配置
        "X99N.9999": {"M004": date(2026, 6, 1)},
    }


class _RecordingLogger:
    """最小审计接收方替身：只收不写，便于断言。"""

    def __init__(self):
        self.events = []

    def record(self, event):
        self.events.append(event)


# ── 1. 审计留痕 ─────────────────────────────────────────────────────────────

class TestAudit:
    def test_writes_audit_event_when_logger_given(self):
        logger = _RecordingLogger()
        run_smt_schedule(_plans(), _arrivals(), audit_logger=logger)

        assert len(logger.events) == 1
        ev = logger.events[0]
        assert ev.scenario == "O1"
        assert ev.automation_level == "L1"          # design D3 拍板：首版记 L1
        assert "F02N.0040" in ev.decision["scheduled"]
        assert ev.decision["analyzed_at"]
        assert ev.data_sources                       # 各输入来源须如实标注

    def test_audit_records_placeholder_flag(self):
        """审计里必须能看出这次用的是不是占位工时——事后追溯要靠它"""
        logger = _RecordingLogger()
        run_smt_schedule(_plans(), _arrivals(), audit_logger=logger)
        assert logger.events[0].decision["lead_time_is_placeholder"] is True

    def test_silent_without_logger(self):
        """未传审计接收方 → 正常返回、不写审计、不抛异常（单测不依赖 sink）"""
        result = run_smt_schedule(_plans(), _arrivals())
        assert isinstance(result, ScheduleResult)
        assert result.scheduled


# ── 2. 可信边界 ─────────────────────────────────────────────────────────────

class TestTrustBoundary:
    def test_result_carries_placeholder_flag(self):
        result = run_smt_schedule(_plans(), _arrivals())
        assert result.lead_time_is_placeholder is True

    def test_partial_failure_returns_both_sides(self):
        """部分产品无法排产 → 可排产的给日期、不可排产的单列原因，不整批失败"""
        result = run_smt_schedule(_plans(), _arrivals())

        assert result.scheduled == {
            "F02N.0040": date(2026, 6, 17),
            "F02N.0064": date(2026, 6, 12),
        }
        assert "X99N.9999" in result.unschedulable
        assert "工时" in result.unschedulable["X99N.9999"]   # 原因可读，非空字符串

    def test_missing_arrivals_listed_not_dropped(self):
        """有工单但完全没有到货记录的产品，须出现在 unschedulable，不得静默丢弃"""
        plans = [ProductionPlan("MO009", "F02N.0040", "EQ02-DW-C1", 10, "2026-06-20")]
        result = run_smt_schedule(plans, {})
        assert result.scheduled == {}
        assert "F02N.0040" in result.unschedulable
        assert "到货" in result.unschedulable["F02N.0040"]

    def test_counts_are_consistent(self):
        result = run_smt_schedule(_plans(), _arrivals())
        assert len(result.scheduled) + len(result.unschedulable) == len(result.products)


# ── 3. real 档位 fail-loud ──────────────────────────────────────────────────

class _FailLoudConnector:
    """模拟 real 档位下取生产计划即 fail-loud 的底座连接器。"""

    def get_production_plan(self):
        raise RealEndpointNotReadyError(
            "get_production_plan",
            "zp 无生产计划端点，待 U9C MO（UFIDA.U9.MO.MO.MO）CommonEntity 外网开放或 LAN/VPN",
        )


class TestRealModeFailLoud:
    def test_real_mode_raises_and_returns_nothing(self):
        """real 档位未 opt-in → 抛错，且不返回任何完工日"""
        with pytest.raises(RealEndpointNotReadyError) as exc:
            run_smt_schedule(None, _arrivals(), connector=_FailLoudConnector())

        assert exc.value.method == "get_production_plan"
        assert "UFIDA.U9.MO.MO.MO" in exc.value.reason   # 错误须含待解锁端点名

    def test_real_mode_failure_writes_no_audit(self):
        """失败即失败，不留一条看起来像成功的审计"""
        logger = _RecordingLogger()
        with pytest.raises(RealEndpointNotReadyError):
            run_smt_schedule(None, _arrivals(),
                             connector=_FailLoudConnector(), audit_logger=logger)
        assert logger.events == []

    def test_plans_from_connector_when_given(self):
        """连接器可用时，工单由连接器取——切换数据源不动引擎"""
        class _OkConnector:
            def get_production_plan(self):
                return _plans()

        result = run_smt_schedule(None, _arrivals(), connector=_OkConnector())
        assert result.scheduled["F02N.0040"] == date(2026, 6, 17)
        assert result.data_sources["production_plan"] == "connector"

    def test_inline_plans_marked_as_mock_source(self):
        result = run_smt_schedule(_plans(), _arrivals())
        assert result.data_sources["production_plan"] == "mock"


class TestSourceExclusivity:
    """plans 与 connector 互斥——同时给会让审计说不清工单来源，故拒绝而非静默取舍。"""

    def test_both_sources_rejected(self):
        class _OkConnector:
            def get_production_plan(self):
                return _plans()

        with pytest.raises(ValueError, match="互斥"):
            run_smt_schedule(_plans(), _arrivals(), connector=_OkConnector())

    def test_neither_source_rejected(self):
        with pytest.raises(ValueError, match="至少提供其一"):
            run_smt_schedule(None, _arrivals())
