from datetime import date, timedelta
from dataclasses import asdict
from collections import Counter
import pytest
from sc8 import config, forecast, baoguan
from sc8.models import SalesOrder
from zhuopin_platform.shared_tools.models import BomRow, SrmDeliveryOrder

@pytest.mark.parametrize('r1,r2,suffix', [
    ('off','off',''), ('on','off','+rule1'),
    ('off','on','+rule2'), ('on','on','+rule1+rule2'),
])
def test_policy_version_matrix(monkeypatch, r1, r2, suffix):
    monkeypatch.setenv('SC8_KIT_DATE_RULE1', r1)
    monkeypatch.setenv('SC8_KIT_DATE_RULE2_LITERAL', r2)
    ctx = config.forecast_context()
    assert ctx.params.param_version == config.PARAM_VERSION + suffix
    assert (ctx.rule1, ctx.rule2) == (r1 == 'on', r2 == 'on')
    assert set(asdict(ctx.params)) == {
        'param_version','no_feedback_lead_days','outsource_extra_days',
        'logistics_days','deviation_alert_days','rule1_horizon_months',
        'rule1_months_back','rule1_start_day',
    }

@pytest.mark.parametrize('value', ['on','1','true','yes',' ON '])
def test_rule2_truthy(monkeypatch, value):
    monkeypatch.setenv('SC8_KIT_DATE_RULE2_LITERAL', value)
    assert config.kit_date_rule2_enabled() is True

def test_rule2_default_off_and_frozen(monkeypatch):
    monkeypatch.delenv('SC8_KIT_DATE_RULE2_LITERAL', raising=False)
    monkeypatch.setenv('SC8_KIT_DATE_RULE1', 'off')
    ctx = config.forecast_context()
    monkeypatch.setenv('SC8_KIT_DATE_RULE2_LITERAL', 'on')
    assert ctx.rule2 is False
    assert ctx.params.param_version == config.PARAM_VERSION

def test_custom_numeric_params_and_base_version_survive(monkeypatch):
    monkeypatch.setenv('SC8_KIT_DATE_RULE1', 'off')
    monkeypatch.setenv('SC8_KIT_DATE_RULE2_LITERAL', 'on')
    p = config.ForecastParams(param_version='custom-v3+rule1',
                              no_feedback_lead_days=75)
    ctx = config.forecast_context(p)
    assert ctx.params.param_version == 'custom-v3+rule2'
    assert ctx.params.no_feedback_lead_days == 75
    assert p.param_version == 'custom-v3+rule1'

TODAY = date(2026, 9, 2)

@pytest.mark.parametrize('r1,r2', [(False,False),(True,False),
                                  (False,True),(True,True)])
@pytest.mark.parametrize('ship', [date(2026,8,20), date(2026,9,2),
                                  date(2026,11,20), date(2027,1,20)])
def test_start_matrix(r1, r2, ship):
    p = config.ForecastParams()
    got = forecast.no_feedback_start_date(ship, TODAY, p,
        rule1_enabled=r1, rule2_enabled=r2)
    if ship <= TODAY:
        expected = TODAY
    elif ship <= date(2026,12,2):
        expected = TODAY if r2 else ship
    else:
        expected = date(2026,10,20) if r1 else ship
    assert got == expected

@pytest.mark.parametrize('today,last,after,rule1_after', [
    (date(2026,1,31),date(2026,4,30),date(2026,5,1),date(2026,2,20)),
    (date(2028,2,29),date(2028,5,29),date(2028,5,30),date(2028,2,20)),
])
def test_natural_month_inclusive_boundary(today, last, after, rule1_after):
    p = config.ForecastParams()
    assert forecast.no_feedback_start_date(last,today,p,
        rule1_enabled=True,rule2_enabled=True) == today
    assert forecast.no_feedback_start_date(after,today,p,
        rule1_enabled=True,rule2_enabled=True) == rule1_after

def test_daily_delta_is_exact():
    p = config.ForecastParams()
    for offset in range(1,92):
        ship = TODAY + timedelta(days=offset)
        off = forecast.no_feedback_start_date(ship,TODAY,p,
            rule1_enabled=True,rule2_enabled=False)
        on = forecast.no_feedback_start_date(ship,TODAY,p,
            rule1_enabled=True,rule2_enabled=True)
        assert (off-on).days == offset, (ship,off,on)

def test_unmodified_direct_call_keeps_rule1_contract():
    assert forecast.no_feedback_start_date(date(2027,1,20),TODAY) == date(2026,10,20)
    assert forecast.no_feedback_start_date(date(2026,11,20),TODAY) == date(2026,11,20)

def so(ship, *, so_id='FO-SYN-1', qty=10):
    return SalesOrder(so_id=so_id, customer_id='',customer_name='合成客户',
        item_code='SYN-P',qty=qty,required_date=ship.isoformat(),
        doc_type='预测订单',item_name='合成成品')

def bom(*parts):
    return [BomRow(product_id='SYN-P',component_id=m,component_name=m,
        level=1,qty_per_unit=1.0,loss_rate=0.0,unit='PCS') for m in parts]

def run_pair(monkeypatch, ship, *, parts=('NF',), srm=(), inventory=None):
    monkeypatch.setenv('SC8_KIT_DATE_RULE1','on')
    monkeypatch.setenv('SC8_NET_INVENTORY','off' if inventory is None else 'on')
    results = []
    for value in ('off','on'):
        monkeypatch.setenv('SC8_KIT_DATE_RULE2_LITERAL',value)
        results.append(baoguan.build_dashboard([so(ship)],bom(*parts),list(srm),
            today=TODAY,inventory=inventory,preserve_input_order=True)[0])
    return results

@pytest.mark.parametrize('ship,expected_gap,expected_color', [
    (date(2026,11,30),1,baoguan.RISK_YELLOW), (date(2026,12,1),0,baoguan.RISK_GAP),
    (date(2026,11,27),4,baoguan.RISK_RED),
])
def test_d5_real_classifier(monkeypatch,ship,expected_gap,expected_color):
    off,on = run_pair(monkeypatch,ship)
    assert off.kit_date == ship + timedelta(days=90)
    assert off.gap_days == 90 and off.risk == baoguan.RISK_RED
    assert on.kit_date == date(2026,12,1)
    assert (on.gap_days,on.risk) == (expected_gap,expected_color)

def test_daily_real_color_grid(monkeypatch):
    colors = Counter()
    for offset in range(1,92):
        ship = TODAY + timedelta(days=offset)
        off,on = run_pair(monkeypatch,ship)
        assert (off.kit_date-on.kit_date).days == offset
        colors[on.risk] += 1
    assert colors == {baoguan.RISK_RED:86,baoguan.RISK_YELLOW:3,baoguan.RISK_GAP:2}

def test_rule3_and_confirmed_bottleneck_remain(monkeypatch):
    late = SrmDeliveryOrder(delivery_id='SYN-D',demand_id='',supplier_id='',
        material_id='CONF',qty_committed=0,committed_date='2027-05-20',status='confirmed')
    off,on = run_pair(monkeypatch,date(2026,11,20),parts=('NF','CONF'),srm=(late,))
    assert off.kit_date == on.kit_date == date(2027,5,20)
    assert off.bottleneck_material == on.bottleneck_material == 'CONF'
    assert off.risk == on.risk == baoguan.RISK_RED

def test_inventory_covered_and_missing_bom_unchanged(monkeypatch):
    off,on = run_pair(monkeypatch,date(2026,11,20),inventory={'NF':100})
    assert off.kit_date == on.kit_date
    assert off.risk == on.risk
    off,on = run_pair(monkeypatch,date(2026,11,20),parts=())
    assert off.kit_date == on.kit_date is None
    assert off.risk == on.risk == baoguan.RISK_RED

def assert_connected(off,on):
    inferred_start = on.kit_date - timedelta(days=90)
    assert on.kit_date == date(2026,12,1), (
        on.kit_date, '应为业务日期+90', 'start_delta_days', (inferred_start-TODAY).days)
    assert (off.kit_date-on.kit_date).days == 89

def test_old_start_mutation_is_detected(monkeypatch):
    assert_connected(*run_pair(monkeypatch,date(2026,11,30)))
    def old_start(ship,today,params=None,**kw):
        return max(ship,today)
    monkeypatch.setattr(baoguan,'no_feedback_start_date',old_start)
    with pytest.raises(AssertionError):
        assert_connected(*run_pair(monkeypatch,date(2026,11,30)))

def test_missing_rule2_argument_is_detected(monkeypatch):
    real_start = forecast.no_feedback_start_date
    def omit_rule2(ship,today,params=None,**kw):
        return real_start(ship,today,params,rule1_enabled=kw.get('rule1_enabled',True))
    monkeypatch.setattr(baoguan,'no_feedback_start_date',omit_rule2)
    with pytest.raises(AssertionError):
        assert_connected(*run_pair(monkeypatch,date(2026,11,30)))

def test_static_html_consumes_frozen_params(monkeypatch):
    monkeypatch.setenv('SC8_KIT_DATE_RULE1','off')
    monkeypatch.setenv('SC8_KIT_DATE_RULE2_LITERAL','on')
    ctx = config.forecast_context()
    rows = baoguan.build_dashboard([so(date(2026,12,1))],bom('NF'),[],
        today=TODAY,context=ctx)
    monkeypatch.setenv('SC8_KIT_DATE_RULE2_LITERAL','off')
    html = baoguan.render_html(rows,today=TODAY,params=ctx.params)
    assert ctx.params.param_version in html
    assert '估算不等于供应商确定承诺' in html

def test_mismatched_context_is_explicit_error(monkeypatch):
    monkeypatch.setenv('SC8_KIT_DATE_RULE2_LITERAL','on')
    ctx = config.forecast_context()
    other = config.ForecastParams(param_version='different')
    with pytest.raises(ValueError,match='frozen forecast context'):
        baoguan.build_dashboard([],[],[],today=TODAY,params=other,context=ctx)
