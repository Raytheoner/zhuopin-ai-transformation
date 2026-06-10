"""数据源开关 + 审计按源标记 + 客户隔离键（任务 2.2/2.3/3.1，design D2/D4）。"""
from __future__ import annotations

import json

from sc8 import config
from sc8.pipeline import compute_forecasts
from sc8.sources import build_data_sources


# ── D2：数据源开关（环境变量驱动，默认 mock，对客外发开关全程关闭）──────────────
def test_data_source_mode_defaults_mock(monkeypatch):
    monkeypatch.delenv("SC8_DATA_SOURCE", raising=False)
    assert config.data_source_mode() == "mock"


def test_data_source_mode_real(monkeypatch):
    monkeypatch.setenv("SC8_DATA_SOURCE", "real")
    assert config.data_source_mode() == "real"


def test_srm_source_mode_defaults_mock(monkeypatch):
    monkeypatch.delenv("SC8_SRM_SOURCE", raising=False)
    assert config.srm_source_mode() == "mock"


def test_customer_outbound_switch_is_off():
    # 红线：SRM 联调通过 + 门禁 6 项全勾前，对客外发总开关全程关闭
    assert config.CUSTOMER_OUTBOUND_ENABLED is False


# ── D4：客户隔离键可切换（现客户名；IT 补 customer_id 后改一处）─────────────────
def test_isolation_key_uses_customer_name_by_default(sales_orders):
    assert config.ISOLATION_KEY_FIELD == "customer_name"
    so = sales_orders[0]
    assert config.customer_isolation_key(so) == so.customer_name


def test_isolation_key_switchable_to_customer_id(monkeypatch, sales_orders):
    # 模拟 IT 补好 customer_id 后只改这一处
    monkeypatch.setattr(config, "ISOLATION_KEY_FIELD", "customer_id")
    so = sales_orders[0]
    assert config.customer_isolation_key(so) == so.customer_id


def test_isolation_key_falls_back_to_name_when_field_empty(monkeypatch, sales_orders):
    # customer_id 字段切换但值为空 → 回退客户名（不产生空键串库）
    monkeypatch.setattr(config, "ISOLATION_KEY_FIELD", "customer_id")
    so = sales_orders[0]
    object.__setattr__(so, "customer_id", "")
    assert config.customer_isolation_key(so) == so.customer_name


# ── 任务 2.3：审计按源如实标记（fo/bom/srm_committed/smt_lead）─────────────────
def test_build_data_sources_tags_each_source():
    ds = build_data_sources(order_src="real", bom_src="real",
                            srm_src="mock", lead_src="mock")
    assert ds == {"fo": "real", "bom": "real",
                  "srm_committed": "mock", "smt_lead": "mock"}


def test_compute_forecasts_records_per_source_tags(
        tmp_path, sales_orders, bom, srm_deliveries, lead_time, params, outsource_ids):
    from zhuopin_platform.audit import AuditLogger
    audit_path = tmp_path / "audit.jsonl"
    audit = AuditLogger.jsonl(audit_path)
    ds = build_data_sources(order_src="real", bom_src="real",
                            srm_src="mock", lead_src="mock")
    compute_forecasts(
        sales_orders, bom, srm_deliveries, lead_time, params,
        audit=audit, outsource_ids=outsource_ids, data_sources=ds,
    )
    lines = [json.loads(l) for l in audit_path.read_text(encoding="utf-8").splitlines() if l]
    assert lines, "应有预测审计记录"
    for rec in lines:
        assert rec["data_sources"]["fo"] == "real"
        assert rec["data_sources"]["bom"] == "real"
        assert rec["data_sources"]["srm_committed"] == "mock"   # SRM 降级如实标记


def test_compute_forecasts_default_data_sources_mock(
        tmp_path, sales_orders, bom, srm_deliveries, lead_time, params, outsource_ids):
    # 不传 data_sources → 向后兼容，默认全 mock（golden 路径不受影响）
    from zhuopin_platform.audit import AuditLogger
    audit_path = tmp_path / "audit.jsonl"
    audit = AuditLogger.jsonl(audit_path)
    compute_forecasts(sales_orders, bom, srm_deliveries, lead_time, params,
                      audit=audit, outsource_ids=outsource_ids)
    rec = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[0])
    assert rec["data_sources"]["bom"] == "mock"
    assert rec["data_sources"]["srm_committed"] == "mock"
