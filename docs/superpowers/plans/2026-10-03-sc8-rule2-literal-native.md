# SC8 规则 2 逐字化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. 已选择当前会话 Native；步骤用纯编号记录，遵守用户不使用不可交互 checkbox 的要求。

**Goal:** 将已批准 P1 的窗口内未来无答交起算点改为业务日期，以独立默认 OFF 开关控制，并交付真实对照工具及逐项发布证据。

**Architecture:** 起算分支只在 `forecast.no_feedback_start_date()`；批次入口捕获一次规则开关与参数版本，逐行、快照、audit 和展示消费同一不可变上下文。真实对照按冻结输入的行位置对齐两侧，避免重复 FO 单号被折叠或风险排序造成错配；调用方不传启发式起算点时保持原计算基准。

**Tech Stack:** Python、dataclasses、pytest、现有 SC8/U9C/SRM、平台 bootstrap/audit、现有 HTML/JS；不加依赖。

**Spec:** `C:/Dev/zhuopin-ai/openspec/changes/sc8-atp-batch2-closeout/design.md`；同目录 `tasks.md`；`specs/delivery-date-forecast/spec.md`。先读三件及本轮经明确批准的 D5 红→橙勘误。

**状态：具体计划待审。** 本稿是拟实施内容，文内代码与命令尚未执行。原 design 2026-09-03 已放行；用户于 2026-10-03 明确批准仅更正 D5 的零缺口未答复预期及 91 日网格，保留现有四色。本稿仍按 writing-plans 请求完整具体计划审；当前 Native 方式沿用。实际实施须正式立行、Guardian 与获准隔离工作树；未来测试也须用户明确批准本计划所列验证。

## Global Constraints

- P1 `SC8_KIT_DATE_RULE2_LITERAL` 与既有 `SC8_KIT_DATE_RULE1` 独立；新增键默认 OFF。
- 仅改变出货日晚于业务日期且位于三自然月窗口内的无答交起算点；含上界是当前实现，专业边界签认任务仍保留。
- 过期分支、规则 1 的窗外算法与规则 3 的 `max` 聚合按原值；不用 90 天替代三自然月窗口。
- `_classify` 实际口径保留：gap>3 红；gap=1–3 黄；gap≤0 且存在未答复件橙；全部有答复且按期绿。D5 零缺口为橙。
- 不改变 `ForecastParams` 的字段形状、估算函数缺省起算基准、pipeline 的显式黄金参数或 SRM 答交判据。
- `#445` 常量误读已在当前源码修复为 `active_param_version()`；本计划补同一次求值与 audit 的一致性，不重复声称尚未修。
- mock 与真实黄金基准双绿、真实对照、姚祖怡复核、代码实际部署/CreationDate、开关重算与数字核对均为正式发布要求。历史 509 passed/4 skipped 不作当前证据；真实夹具 skip 不算通过。
- P2 PMC 导入完整范围保留，另有专业模板/来源前置及独立计划，MUST NOT 与 P1 同批开启。本计划不将 P2 从整包验收删掉。
- OEM 资料不入 Git；真实冻结载荷放仓库外受控位置。本轮只写准备文档，不读取 .env 凭据或改变生产。
- 看护者主仓不建业务分支、不改业务代码；下述修改与测试全部是获准隔离树内的未来步骤。ff、生产部署、外发和 L2 各取具体授权。

## Review Focus

1. 两个规则四种组合及默认 OFF：R2 开、R1 关时窗外仍用旧基准；Task 1/2 矩阵测试。
2. 月末、闰年、含上界：按自然月截断而非固定 90 天；Task 2 边界测试。
3. 混合已答交/无答交、库存已覆盖、无 BOM：规则 3 与确定晚到瓶颈不被新起算替代；Task 3 端到端测试。
4. 取数期间环境开关变化：同一批次日期、显示与 audit 不能各读一份环境；Task 3 批中翻转及一次求值测试。
5. 重复 FO 单号/相同物料行及未触发的变色：按原输入位置对齐、不以零反例冒充覆盖；Task 4 重复行与负例测试。

## 文件及接口边界

以下路径均相对 `4-数字员工/采购部/SC8-客户订单交期智能承诺/`；执行时 `$sc8Root` 为**正式 Guardian 返回的隔离工作树**内该场景绝对路径，不自行猜树名。

| 文件 | 责任 |
|---|---|
| `sc8/config.py` | 独立 R2 开关、版本标记、`ForecastContext` 与一次捕获 |
| `sc8/forecast.py` | 唯一日期分支；向后兼容直接函数调用 |
| `sc8/baoguan.py` | 消费上下文、可选输入顺序返回、图例/静态页说明 |
| `sc8/baoguan_service.py` | 捕获一次、传播至全批、审计与 Snapshot 使用同版本 |
| `sc8/webapp.py` | 缓存页面显示 Snapshot 的实际版本，图例不重新显示现场版本 |
| `scripts/run_baoguan_dashboard.py` | 静态看板计算/渲染共用上下文 |
| `sc8/kit_date_comparison.py`（新增） | 无网络的逐行不变式核验与覆盖状态 |
| `scripts/compare_kit_date_rule2.py`（新增） | 读既有冻结格式、实际开关 OFF/ON 对照、外部报告与 receipt |
| `tests/test_kit_date_rule2.py`（新增） | 纯函数、开关/参数、端到端/反例 |
| `tests/test_kit_date_rule2_comparison.py`（新增） | 比较器、重复行、坏载荷/缺冻结文件 |
| `tests/test_baoguan_service.py`、`tests/test_baoguan_webapp.py` | 对原服务及缓存 UI 回归 |
| 场景 `CLAUDE.md`、本包 `tasks.md` | 据实际证据回写实现/阻塞项，保持 P2 与发布待办 |

所有单元测试在场景目录运行。隔离环境由 `invoke.ps1`/Guardian 解析；下面 `$scenePython` 是其返回的 Python 路径，不能给共享全局 site-packages 重装 editable 指针。不得在根目录混跑 pytest。

---

### Task 1: 独立开关与一次参数上下文

**Files:** Modify `sc8/config.py`；Create `tests/test_kit_date_rule2.py`。

**Interfaces:**

- `kit_date_rule2_enabled() -> bool`，默认关，沿用 on/1/true/yes 输入语义。
- `active_param_version(*, rule1: bool|None=None, rule2: bool|None=None, base_version: str|None=None) -> str`；不传布尔时现取，传布尔时不重读环境。
- `default_params(*, param_version: str|None=None) -> ForecastParams`，既有无参调用保留。
- `ForecastContext(params: ForecastParams, rule1: bool, rule2: bool)` frozen；`forecast_context(params: ForecastParams|None=None) -> ForecastContext`，同一次求值贯穿后续任务。

1. 在新增测试文件写下开关/版本矩阵，先保留实际导入失败作为新接口的红灯：

```python
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
```

2. 获准测试后运行 `& "$scenePython" -m pytest 'tests/test_kit_date_rule2.py' -q`，保存新接口不存在的实际失败。不得把未执行记为红灯。
3. 在 config 加 `replace` 的 dataclasses import；新增以下实现，并替换旧 `active_param_version`。`default_params` 原构造中的 `param_version=active_param_version()` 改为 `param_version=(param_version if param_version is not None else active_param_version())`，其余数值参数按原常量构造：

```python
def kit_date_rule2_enabled() -> bool:
    return os.environ.get('SC8_KIT_DATE_RULE2_LITERAL', 'off').strip().lower() in (
        'on', '1', 'true', 'yes')

def active_param_version(*, rule1: bool | None = None,
                         rule2: bool | None = None,
                         base_version: str | None = None) -> str:
    r1 = kit_date_rule1_enabled() if rule1 is None else rule1
    r2 = kit_date_rule2_enabled() if rule2 is None else rule2
    base = PARAM_VERSION if base_version is None else base_version
    while base.endswith(('+rule1', '+rule2')):
        base = base.rsplit('+', 1)[0]
    return base + ('+rule1' if r1 else '') + ('+rule2' if r2 else '')

@dataclass(frozen=True)
class ForecastContext:
    params: ForecastParams
    rule1: bool
    rule2: bool

def forecast_context(params: ForecastParams | None = None) -> ForecastContext:
    r1, r2 = kit_date_rule1_enabled(), kit_date_rule2_enabled()
    version = active_param_version(rule1=r1, rule2=r2,
                                   base_version=None if params is None
                                   else params.param_version)
    p = (default_params(param_version=version) if params is None
         else replace(params, param_version=version))
    return ForecastContext(p, r1, r2)
```

4. 运行同一新测试及既有 `tests/test_kit_date_rule1_start.py`；记录真正通过数、skip、失败信息。可独立评审开关及上下文接口后，在获准隔离分支只暂存两文件，commit `feat(sc8): freeze independent kit date rule controls`。

### Task 2: 唯一起算分支及自然月矩阵

**Files:** Modify `sc8/forecast.py`；Extend `tests/test_kit_date_rule2.py`。

**Interfaces:** `no_feedback_start_date(ship_date: date, today: date, params: ForecastParams|None=None, *, rule1_enabled: bool=True, rule2_enabled: bool=False) -> date`。新增 keyword 默认保持旧直接调用的规则 1 契约；实际开关状态由 Task 3 显式传入。估算函数不自行读取新开关。

1. 在新测试文件追加以下可直接执行的用例：

```python
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
```

2. 运行新增函数用例，确认 keyword/新分支尚未接入的实际失败；不能修改预期绕过失败。
3. 替换 `forecast.no_feedback_start_date` 为以下完整函数；`ship_within_horizon` 与 `_shift_months` 按现有定义使用：

```python
def no_feedback_start_date(ship_date: date, today: date,
                           params: ForecastParams | None = None, *,
                           rule1_enabled: bool = True,
                           rule2_enabled: bool = False) -> date:
    p = params or config.default_params()
    if ship_within_horizon(today, ship_date, p):
        return today if rule2_enabled else max(ship_date, today)
    if not rule1_enabled:
        return max(ship_date, today)
    anchor = _shift_months(ship_date.replace(day=1), -p.rule1_months_back)
    return date(anchor.year, anchor.month, p.rule1_start_day)
```

4. 运行新增日期用例与既有 rule1/forecast 测试。核原调用没传 `heuristic_base_date` 的估算路径未改；按实证评审后 commit `feat(sc8): apply literal rule2 only inside future horizon`。

### Task 3: 批次接通、真分类反例、audit 和显示

**Files:** Modify `sc8/baoguan.py`、`sc8/baoguan_service.py`、`sc8/webapp.py`、`scripts/run_baoguan_dashboard.py`；Extend新增测试及原 service/webapp 测试。

**Interfaces:**

- `assess_supply_risk`、`build_dashboard` 新增 keyword `context: config.ForecastContext|None=None`，保留原 `params`；两者同时传且不相等时 `ValueError`。
- `build_dashboard` 新增 `preserve_input_order: bool=False`；默认仍按原风险/缺口排序，对照显式为 True。
- `render_legend(params: ForecastParams|None=None, *, include_version: bool=True) -> str`。静态输出传同一 `ctx.params`；服务壳图例不显示另取的版本，实际版本来自 Snapshot。

1. 在 `tests/test_kit_date_rule2.py` 追加辅助契约与端到端用例。沿用实际 `_classify`，不新造简化颜色函数：

```python
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
    (date(2026,11,30),1,'yel'), (date(2026,12,1),0,'gap'),
    (date(2026,11,27),4,'red'),
])
def test_d5_real_classifier(monkeypatch,ship,expected_gap,expected_color):
    off,on = run_pair(monkeypatch,ship)
    assert off.kit_date == ship + timedelta(days=90)
    assert off.gap_days == 90 and off.risk == 'red'
    assert on.kit_date == date(2026,12,1)
    assert (on.gap_days,on.risk) == (expected_gap,expected_color)

def test_daily_real_color_grid(monkeypatch):
    colors = Counter()
    for offset in range(1,92):
        ship = TODAY + timedelta(days=offset)
        off,on = run_pair(monkeypatch,ship)
        assert (off.kit_date-on.kit_date).days == offset
        colors[on.risk] += 1
    assert colors == {'red':86,'yel':3,'gap':2}

def test_rule3_and_confirmed_bottleneck_remain(monkeypatch):
    late = SrmDeliveryOrder(delivery_id='SYN-D',demand_id='',supplier_id='',
        material_id='CONF',qty_committed=0,committed_date='2027-05-20',status='confirmed')
    off,on = run_pair(monkeypatch,date(2026,11,20),parts=('NF','CONF'),srm=(late,))
    assert off.kit_date == on.kit_date == date(2027,5,20)
    assert off.bottleneck_material == on.bottleneck_material == 'CONF'
    assert off.risk == on.risk == 'red'

def test_inventory_covered_and_missing_bom_unchanged(monkeypatch):
    off,on = run_pair(monkeypatch,date(2026,11,20),inventory={'NF':100})
    assert off.kit_date == on.kit_date
    assert off.risk == on.risk
    off,on = run_pair(monkeypatch,date(2026,11,20),parts=())
    assert off.kit_date == on.kit_date is None
    assert off.risk == on.risk == 'red'

def assert_connected(off,on):
    assert on.kit_date == date(2026,12,1), (on.kit_date, '应为业务日期+90')
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
```

2. 在 service 原测试文件加实际 mock loaders 的批中翻转测试，不触网：

```python
def test_snapshot_context_captured_once_even_if_loader_changes_environment(monkeypatch):
    monkeypatch.setenv('SC8_KIT_DATE_RULE1','on')
    monkeypatch.setenv('SC8_KIT_DATE_RULE2_LITERAL','on')
    monkeypatch.setenv('SC8_NET_INVENTORY','off')
    monkeypatch.setenv('SC8_PO_TRANSIT','off')
    order = SalesOrder(so_id='SYN-FO',customer_id='',customer_name='合成客户',
        item_code='SYN-P',qty=10,required_date='2026-12-01',doc_type='预测订单')
    material_bom = _bom('SYN-P','NF')
    calls = []
    original = config.active_param_version
    def observed_version(**kw):
        calls.append(kw)
        return original(**kw)
    monkeypatch.setattr(config,'active_param_version',observed_version)
    def orders_loader(**kw):
        monkeypatch.setenv('SC8_KIT_DATE_RULE2_LITERAL','off')
        return [order]
    monkeypatch.setattr(bs,'load_real_orders',orders_loader)
    monkeypatch.setattr(bs,'load_real_bom',lambda *args,**kw: material_bom)
    monkeypatch.setattr(bs,'load_srm_deliveries',lambda *args,**kw: [])
    monkeypatch.setattr(bs,'load_material_commitments',lambda *args,**kw: {})
    class Sink:
        def __init__(self): self.events=[]
        def record(self,event): self.events.append(event)
    sink = Sink()
    snap = bs.compute_snapshot(today=date(2026,9,2),audit=sink)
    event = next(e for e in sink.events if e.action == 'baoguan_snapshot')
    assert len(calls) == 1
    assert snap.rows[0]['kit'] == '2026-12-01'
    assert snap.rows[0]['risk'] == 'gap'
    assert snap.param_version == config.PARAM_VERSION + '+rule1+rule2'
    assert event.decision['param_version'] == snap.param_version
    assert event.decision['kit_date_rules'] == {'rule1':True,'rule2':True}
```

3. 在 `baoguan.py` 加以下完整 helper，并在两函数签名追加 context，build 另追加 preserve_input_order：

```python
def _forecast_context(params: ForecastParams | None,
                      context: config.ForecastContext | None) -> config.ForecastContext:
    if context is None:
        return config.forecast_context(params)
    if params is not None and params != context.params:
        raise ValueError('params differ from frozen forecast context')
    return context
```

`assess_supply_risk` 的 `p = params or config.default_params()` 替换为 `ctx = _forecast_context(params, context)` 与 `p = ctx.params`；原 heuristic_base 表达式完整替换为：

```python
    heuristic_base = (
        no_feedback_start_date(ship,today,p,rule1_enabled=ctx.rule1,
                               rule2_enabled=ctx.rule2)
        if ctx.rule1 or ctx.rule2 else None
    )
```

`build_dashboard` 在库存分配之前加 `ctx = _forecast_context(params, context)`；每个 assess 调用用 `params=ctx.params, context=ctx`。原最终风险排序前加：

```python
    if preserve_input_order:
        return rows
```

由此对照按源位置返回，日常 UI 排序仍走原 return。没有新颜色判断或取数路径。

4. 在 `compute_snapshot` 的 `today = today or date.today()` 之后加 `ctx = config.forecast_context()`；build 调用追加 `params=ctx.params, context=ctx`；Snapshot 的 param_version 用 `ctx.params.param_version`。原 `baoguan_snapshot` decision 字典追加以下项（asdict 是该模块已有 import）：

```python
                      'param_version': ctx.params.param_version,
                      'parameters': asdict(ctx.params),
                      'kit_date_rules': {'rule1':ctx.rule1,'rule2':ctx.rule2},
```

5. 静态 runner 的 build 之前加 `ctx = config.forecast_context()`；build 用 `context=ctx`，`render_html`/`render_markdown` 用 `params=ctx.params`。在 `render_legend` 新增 include_version 参数，`p = ...` 后加 `version_note = f'，参数版本 {_html.escape(p.param_version)}' if include_version else ''`，将原三段 max+90 描述替换为：

```python
        f'<p><b>无答复子件齐料日估算</b>：在三自然月内、晚于业务日期且启用逐字规则时，'
        f'从业务日期起算；已过期从业务日期起算；窗外仅在规则1启用时按前三自然月20日起算。'
        f'其它情形沿用 max(计划出货日,业务日期)。起算点加 {p.no_feedback_lead_days} 天'
        f'{version_note}；估算不等于供应商确定承诺。</p>'
```

`render_html` 页脚中原硬写 max(出货日,今天)+N 的句子替换为“无答复估算按本页参数与图例，非供应商确定承诺”。现有图例的四行分类及“剔除估算”描述按本文件 Global Constraints 的当前 `_classify` 事实更正文案，替换内容是：

```python
        '<h4>四色判据</h4>'
        '<table><tr><th>图标</th><th>名称</th><th>判据</th></tr>'
        '<tr><td>🔴</td><td>高风险</td><td>无BOM或全量齐料缺口&gt;3天；瓶颈未答复时为保守预警</td></tr>'
        '<tr><td>🟠</td><td>待催</td><td>缺口≤0且仍存在未答复子件，需催确认</td></tr>'
        '<tr><td>🟡</td><td>偏紧</td><td>全量齐料缺口1–3天；按瓶颈是否已答复区分确定延期与估算</td></tr>'
        '<tr><td>🟢</td><td>按期</td><td>全部已答复且齐料不晚于计划出货日</td></tr></table>'
        '<p>颜色由现有全量齐料缺口判定；动作明确区分供应商确认与无答复估算。</p>'
```

这些文字展示已有代码事实，不修改判据。服务 `_shell_page` 调用改为 `render_legend(config.default_params(),include_version=False)`；`applySnap` 中 ts 的已刷新分支改为 `('最后更新 '+(s.generated_at||'—')+' · 参数 '+META.ver)`。header 与预测审计均显示 Snapshot 的同一版本。其它页面及 material board 不改。

6. 新增静态/服务 UI 断言后运行此 Task 的新增测试与原 service/webapp 文件：

```python
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

def test_service_shell_version_comes_from_snapshot():
    from sc8.webapp import _shell_page
    html = _shell_page()
    assert 's.param_version' in html and "+' · 参数 '+META.ver" in html

def test_mismatched_context_is_explicit_error(monkeypatch):
    monkeypatch.setenv('SC8_KIT_DATE_RULE2_LITERAL','on')
    ctx = config.forecast_context()
    other = config.ForecastParams(param_version='different')
    with pytest.raises(ValueError,match='frozen forecast context'):
        baoguan.build_dashboard([],[],[],today=TODAY,params=other,context=ctx)
```

获准隔离树内按真实结果评审本 Task，commit `feat(sc8): connect frozen rule2 context to dashboard and audit`。

### Task 4: 冻结载荷的逐行真实开关对照

**Files:** Create `sc8/kit_date_comparison.py`、`scripts/compare_kit_date_rule2.py`、`tests/test_kit_date_rule2_comparison.py`。

**Interfaces:** `compare_rows(before: list[BaoguanRow], after: list[BaoguanRow], *, today: date, params: ForecastParams) -> dict`；输入必须按源顺序，返回逐行、移动数、变色数和三条覆盖状态；不变式反例抛 `AssertionError`。runner 必须读取已有外部冻结文件，不连网络、不回退 mock。

1. 新测试文件写下正例、重复单号与拒绝反例：

```python
from datetime import date, timedelta
from dataclasses import replace
from pathlib import Path
import json
import pytest
from sc8 import baoguan, config
from sc8.kit_date_comparison import compare_rows
from sc8.models import SalesOrder
from zhuopin_platform.shared_tools.models import BomRow

TODAY = date(2026,9,2)

def make_pair(monkeypatch, *, dates=('2026-11-30','2026-12-01')):
    orders = [SalesOrder(so_id='SAME-FO',customer_id='',customer_name='合成客户',
        item_code='SYN-P',qty=10,required_date=d,doc_type='预测订单') for d in dates]
    material_bom = [BomRow(product_id='SYN-P',component_id='NF',component_name='合成子件',
        level=1,qty_per_unit=1.0,loss_rate=0.0,unit='PCS')]
    monkeypatch.setenv('SC8_KIT_DATE_RULE1','on')
    monkeypatch.setenv('SC8_NET_INVENTORY','off')
    sides=[]
    for flag in ('off','on'):
        monkeypatch.setenv('SC8_KIT_DATE_RULE2_LITERAL',flag)
        sides.append(baoguan.build_dashboard(orders,material_bom,[],today=TODAY,
                                            preserve_input_order=True))
    return sides

def test_duplicate_fo_is_not_collapsed(monkeypatch):
    before,after=make_pair(monkeypatch)
    result=compare_rows(before,after,today=TODAY,params=config.ForecastParams())
    assert [r['source_index'] for r in result['rows']] == [0,1]
    assert result['moved'] == result['color_changed'] == 2
    assert result['coverage']['color_direction'] == 'triggered'

def test_identical_duplicate_rows_still_have_two_positions(monkeypatch):
    before,after=make_pair(monkeypatch,dates=('2026-11-30','2026-11-30'))
    result=compare_rows(before,after,today=TODAY,params=config.ForecastParams())
    assert len(result['rows']) == 2 and result['moved'] == 2

def test_later_or_redder_is_rejected(monkeypatch):
    before,after=make_pair(monkeypatch)
    later=[replace(after[0],kit_date=before[0].kit_date+timedelta(days=1)),after[1]]
    with pytest.raises(AssertionError,match='later'):
        compare_rows(before,later,today=TODAY,params=config.ForecastParams())
    fake_before=[replace(before[0],risk='grn'),before[1]]
    with pytest.raises(AssertionError,match='redder'):
        compare_rows(fake_before,after,today=TODAY,params=config.ForecastParams())

def test_outside_horizon_change_is_rejected(monkeypatch):
    before,after=make_pair(monkeypatch,dates=('2027-01-20',))
    altered=[replace(after[0],kit_date=after[0].kit_date-timedelta(days=1))]
    with pytest.raises(AssertionError,match='outside'):
        compare_rows(before,altered,today=TODAY,params=config.ForecastParams())

def test_unchanged_colors_are_explicitly_unverified(monkeypatch):
    before,after=make_pair(monkeypatch,dates=('2026-11-20',))
    result=compare_rows(before,after,today=TODAY,params=config.ForecastParams())
    assert result['moved'] == 1 and result['color_changed'] == 0
    assert result['coverage']['color_direction'] == 'untriggered_unverified'

def test_missing_or_bad_cache_never_falls_back(tmp_path,monkeypatch):
    from scripts import compare_kit_date_rule2 as runner
    monkeypatch.setenv('SC8_NET_INVENTORY','on')
    missing=tmp_path/'missing.json'
    out=tmp_path/'comparison.md'
    arguments=['--cache',str(missing),'--out',str(out),'--today','2026-09-02',
               '--rule1','on','--input-head','a'*40]
    with pytest.raises(SystemExit): runner.main(arguments)
    assert not out.exists()
    missing.write_text('{"orders":[]}',encoding='utf-8')
    with pytest.raises(ValueError,match='cache format invalid'):
        runner.main(arguments)
    assert not out.exists()

def test_runner_restores_both_flags_and_writes_receipt(tmp_path,monkeypatch):
    from scripts import compare_kit_date_rule2 as runner
    monkeypatch.setenv('SC8_NET_INVENTORY','on')
    monkeypatch.setenv('SC8_KIT_DATE_RULE1','off')
    monkeypatch.setenv('SC8_KIT_DATE_RULE2_LITERAL','on')
    cache=tmp_path/'inputs.json';out=tmp_path/'comparison.md'
    cache.write_text(json.dumps({'orders':[],'bom':[],'srm':[],
        'inventory':{},'purchase_orders':{},'commitments':{}}),encoding='utf-8')
    assert runner.main(['--cache',str(cache),'--out',str(out),'--today','2026-09-02',
        '--rule1','on','--input-head','a'*40]) == 0
    import os
    assert os.environ['SC8_KIT_DATE_RULE1'] == 'off'
    assert os.environ['SC8_KIT_DATE_RULE2_LITERAL'] == 'on'
    receipt=json.loads(out.with_suffix('.md.receipt.json').read_text('utf-8'))
    assert receipt['coverage']['color_direction'] == 'untriggered_unverified'
    assert receipt['parameters']['on']['param_version'].endswith('+rule1+rule2')
```

2. 获准后运行新文件，保存新模块不存在/守卫未实现的实际失败；然后写完整比较器：

```python
from __future__ import annotations
from datetime import date
from sc8.baoguan import BaoguanRow
from sc8.config import ForecastParams
from sc8.forecast import ship_within_horizon

_RANK={'grn':0,'yel':1,'gap':2,'red':3}

def compare_rows(before: list[BaoguanRow],after: list[BaoguanRow],*,
                 today: date,params: ForecastParams) -> dict:
    assert len(before)==len(after),'row count changed'
    results=[];changed=0;moved=0;color_changed=0
    for index,(old,new) in enumerate(zip(before,after)):
        old_key=(old.so_id,old.product_id,old.ship_date,old.qty)
        new_key=(new.so_id,new.product_id,new.ship_date,new.qty)
        assert old_key==new_key,f'row identity mismatch at {index}'
        fields=('kit_date','gap_days','risk','bottleneck_material')
        differs=any(getattr(old,f)!=getattr(new,f) for f in fields)
        eligible=old.ship_date>today and ship_within_horizon(today,old.ship_date,params)
        assert eligible or not differs,f'change outside future horizon at {index}'
        if (old.kit_date is None)!=(new.kit_date is None):
            raise AssertionError(f'missing kit date changed at {index}')
        advance=None
        if old.kit_date is not None:
            assert new.kit_date<=old.kit_date,f'kit date later at {index}'
            advance=(old.kit_date-new.kit_date).days
            moved+=int(advance>0)
        assert old.risk in _RANK and new.risk in _RANK,f'unknown risk at {index}'
        assert _RANK[new.risk]<=_RANK[old.risk],f'risk redder at {index}'
        color_changed+=int(old.risk!=new.risk);changed+=int(differs)
        results.append({'source_index':index,'so_id':old.so_id,
            'product_id':old.product_id,'ship':old.ship_date.isoformat(),
            'qty':old.qty,'before_kit':old.kit_date.isoformat() if old.kit_date else None,
            'after_kit':new.kit_date.isoformat() if new.kit_date else None,
            'before_gap':old.gap_days,'after_gap':new.gap_days,
            'before_risk':old.risk,'after_risk':new.risk,
            'before_bottleneck':old.bottleneck_material,
            'after_bottleneck':new.bottleneck_material,'advance_days':advance})
    return {'rows':results,'changed':changed,'moved':moved,'color_changed':color_changed,
        'coverage':{'branch_direction':'triggered' if changed else 'untriggered_unverified',
                    'date_direction':'triggered' if moved else 'untriggered_unverified',
                    'color_direction':'triggered' if color_changed else 'untriggered_unverified'}}
```

3. 新 runner 使用以下完整内容。控制读已有 cache，显式业务日期；外部载荷的 input-head 是来源声明，须另附实际采集证据，不能从当前代码 HEAD 推成生产输入的来源 HEAD：

```python
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict
from datetime import date,datetime,timezone
from pathlib import Path

_HERE=Path(__file__).resolve()
_REPO_ROOT=next(p for p in _HERE.parents
                if (p/'5-平台底座'/'zhuopin_platform').is_dir())
sys.path.insert(0,str(_REPO_ROOT/'5-平台底座'/'zhuopin_platform'))
from zhuopin_platform.bootstrap import ensure_paths
ensure_paths(__file__,_HERE.parent.parent)
from scripts.compare_kit_date_rule1 import _load_inputs
from sc8 import config
from sc8.baoguan import build_dashboard
from sc8.kit_date_comparison import compare_rows

def _external(path: str) -> Path:
    resolved=Path(path).resolve()
    if any(resolved.is_relative_to(p) for p in
           (_REPO_ROOT,Path('C:/Dev/zhuopin-ai').resolve())):
        raise ValueError('real input/output must stay outside repository checkouts')
    return resolved

def _run(flag: str,rule1: str,inputs: tuple,today: date):
    keys=('SC8_KIT_DATE_RULE1','SC8_KIT_DATE_RULE2_LITERAL')
    saved={key:os.environ.get(key) for key in keys}
    try:
        os.environ[keys[0]]=rule1;os.environ[keys[1]]=flag
        ctx=config.forecast_context()
        assert ctx.rule1==(rule1=='on') and ctx.rule2==(flag=='on'),'switch not connected'
        orders,bom,srm,inventory,purchase_orders,commitments=inputs
        rows=build_dashboard(orders,bom,srm,today=today,context=ctx,
            inventory=inventory,purchase_orders=purchase_orders,
            material_commitments=commitments,preserve_input_order=True)
        return rows,ctx
    finally:
        for key,value in saved.items():
            if value is None: os.environ.pop(key,None)
            else: os.environ[key]=value

def _cell(value) -> str:
    return str(value if value is not None else '—').replace('|','\\|').replace('\n',' ')

def main(argv=None) -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--cache',required=True)
    ap.add_argument('--out',required=True)
    ap.add_argument('--today',required=True,type=date.fromisoformat)
    ap.add_argument('--rule1',required=True,choices=('on','off'))
    ap.add_argument('--input-head',required=True)
    args=ap.parse_args(argv)
    cache=_external(args.cache);out=_external(args.out)
    if not cache.is_file(): ap.error('existing frozen cache is required; no network fallback')
    if not re.fullmatch('[0-9a-f]{40}',args.input_head): ap.error('input-head must be a 40-digit SHA')
    if not config.net_inventory_enabled(): ap.error('production comparison requires net inventory ON')
    try:
        inputs=_load_inputs(cache)
    except (ValueError,TypeError,KeyError,AttributeError) as exc:
        raise ValueError(f'cache format invalid: {type(exc).__name__}') from exc
    controls={'net_inventory':config.net_inventory_enabled(),
              'po_transit':config.po_transit_enabled(),'bom_max_depth':config.bom_max_depth()}
    before,off_ctx=_run('off',args.rule1,inputs,args.today)
    after,on_ctx=_run('on',args.rule1,inputs,args.today)
    assert controls=={'net_inventory':config.net_inventory_enabled(),
                      'po_transit':config.po_transit_enabled(),
                      'bom_max_depth':config.bom_max_depth()},'non-P1 controls drifted'
    comparison=compare_rows(before,after,today=args.today,params=off_ctx.params)
    code_head=subprocess.check_output(['git','-C',str(_REPO_ROOT),'rev-parse','HEAD'],
                                       text=True).strip()
    receipt={'generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'today':args.today.isoformat(),'cache_sha256':hashlib.sha256(cache.read_bytes()).hexdigest(),
        'input_head_declared':args.input_head,'code_head':code_head,'controls':controls,
        'rule1':args.rule1,'parameters':{'off':asdict(off_ctx.params),'on':asdict(on_ctx.params)},
        'changed':comparison['changed'],'moved':comparison['moved'],
        'color_changed':comparison['color_changed'],'coverage':comparison['coverage'],
        'network_used':False}
    lines=['# SC8 规则2 前后对照','',
        '齐料日提前 ≠ 交期变好。本项采纳更乐观的估算判据，不代表供应商实际改善。','',
        f'业务日期：{args.today}；输入 SHA：`{receipt["cache_sha256"]}`；代码 HEAD：`{code_head}`。','',
        '覆盖状态：`'+json.dumps(comparison['coverage'],ensure_ascii=False)+'`。',
        'untriggered_unverified 表示本轮空过、未获验证；没有反例不能作为已覆盖。','',
        '| 源位置 | FO | 物料 | 数量 | 出货日 | OFF齐料/色 | ON齐料/色 | 前移天数 |',
        '|---:|---|---|---:|---|---|---|---:|']
    for row in comparison['rows']:
        values=(row['source_index'],row['so_id'],row['product_id'],row['qty'],row['ship'],
                str(row['before_kit'])+'/'+row['before_risk'],
                str(row['after_kit'])+'/'+row['after_risk'],row['advance_days'])
        lines.append('| '+' | '.join(_cell(v) for v in values)+' |')
    out.parent.mkdir(parents=True,exist_ok=True)
    receipt_path=out.with_suffix(out.suffix+'.receipt.json')
    if out.exists() or receipt_path.exists(): raise FileExistsError('use a new report path')
    with out.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write('\n'.join(lines)+'\n')
    with receipt_path.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(receipt,stream,ensure_ascii=False,indent=2);stream.write('\n')
    print(json.dumps({'report':str(out),'receipt':str(receipt_path),
                      'changed':comparison['changed'],'coverage':comparison['coverage']},
                     ensure_ascii=False))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
```

4. 运行新增比较测试与 Task 1–3 测试。另核 OFF/ON 两次真实参数 version 不同但其它数字参数相同；重复行不可压成按 so_id 的字典。真正通过后评审，commit `feat(sc8): compare literal rule2 on frozen input without row collapse`。

### Task 5: 全量回归、真实证据与逐项发布准备

**Files:** 原场景测试集、`data/golden/real_frozen/` 的已授权外部/忽略夹具、场景 `CLAUDE.md`、本包 `tasks.md`、外部真实报告与 receipt。产品测试代码只按前四 Task 添入；不重写黄金期望使测试变绿。

1. 实施前通过正式 Guardian 查重，并为本 plan 创建独立实施行；读取目标行、design/tasks、同一输入的前置/触碰区公开状态。Guardian 获准且当前 plan 审通过后，在返回隔离树读取 AGENTS/CLAUDE 与运行时路径。主仓保持看护职责。保存基线 HEAD、源哈希与原测试输出；任何真实源或已知 P2 前置缺失均在实施行显式留步。
2. 获准测试后，分别以新键 OFF/ON 运行场景全量，恢复原环境。示例命令在隔离场景目录，使用真实已解析的 `$scenePython`：

```powershell
$savedRule2 = [Environment]::GetEnvironmentVariable('SC8_KIT_DATE_RULE2_LITERAL')
try {
    $env:SC8_KIT_DATE_RULE2_LITERAL = 'off'
    & "$scenePython" -m pytest 'tests' -q
    if ($LASTEXITCODE -ne 0) { throw 'SC8 OFF regression failed' }
    $env:SC8_KIT_DATE_RULE2_LITERAL = 'on'
    & "$scenePython" -m pytest 'tests' -q
    if ($LASTEXITCODE -ne 0) { throw 'SC8 ON regression failed' }
} finally {
    [Environment]::SetEnvironmentVariable('SC8_KIT_DATE_RULE2_LITERAL', $savedRule2, 'Process')
}
```

全量 ON 时，既有“只测规则1”的测试要在对应测试函数/fixture显式固定规则2 OFF，而不是让新全局键改变旧用例前提；在实现 diff 中逐项记录这些局部隔离。禁止给整个 suite 强制关 R2 使 ON 套件空过。新 Task 1–4 独立覆盖 ON 的真实接通。当前测试数按现场列出，与历史 509/4 比较并解释任何减少；skip 不作 pass。若基础 mock 对本项两侧完全相同，明写“mock 语料没有端到端覆盖力”，不能抵消构造性测试要求。
3. 分别跑 `tests/test_golden.py` 与 `tests/test_golden_real.py`；真实 expected/frozen 文件不存在则留步，使用已授权受控来源补齐并记哈希，不造政策答案、不联网偷偷重建。显式黄金参数 `sc8-params-v0` 保持原值，pipeline 未传启发式起算点保持原计算。按 CI 矩阵在平台目录用平台自身隔离运行时跑平台 tests；运行 `openspec validate --all --strict` 并保存实际输出。不得用本轮 GitHub 的基础 CI 代替新增 P1 测试。
4. LAN 真实对照阶段先核当前生产载荷控制值与原语料采集证据，包括净额/PO/规则1/业务日期/库存与承诺快照；沿用 `compare_kit_date_rule1.py` 的外部 cache 格式。本新 runner 只消费已有已授权冻结件。收集与使用真实样本的权限/可达性未到位就停该依赖，mock 构造测试仍独立推进。运行路径由受控输入记录具体提供，先绑定 SHA、来源 HEAD 声明与实际采集记录，不能猜一份冻结件。
5. 在已授权外部目录调用新 runner，指定固定业务日期、明确 rule1 状态及真实来源 SHA。报告自带三不变式及“空过未验证”。与 `docs/queue_118_规则2逐字化改判前后24行对照-2026-09-02.md` 逐行比对；11/24 是旧离线推演，真实结果为准。若不一致，将具体差异与来源带回 D3-bis 审阅，不伪造“新结果仍等于旧推演”。
6. 当前跟进闸采购 #25 仍待审，不另起/占号/重发。真实对照及 D4 自然月含边界复核并入获准串行链，姚祖怡实际签认后才能作为启用前置；此前设计批准与本次勘误不能替代该专业签认。将实现/回归/真实对照/代码 review 的具体证据与尚未闭合项提交发布准备。
7. 从已获准隔离分支按实际 diff 做 code review；按用户模型纪律，任何所需派生 reviewer 必须显式 Luna且适用 review 技能要求实际派出。未评审/未修好不完成。只在分别取得具体授权后做 ff、`.51` `sync-to-server.ps1` 部署、进程 CreationDate 核验和开关更改。部署配置前先备份受控原 `.env` 并存 SHA、不输出凭据；独立开启 P1，P2维持原未开启状态；`POST /api/refresh` 后查快照时间、版本、四色/移动行与对照一致性。
8. OFF 部署基线与 ON 数字都据现场证据核对，不能只看脚本“已重启”。若真实语料颜色本就全红，按 report 的实际移动/版本及 coverage 如实报告“本轮无变色”，不编造数字已变；构造性 D5 用例仍须实证通过。原 tasks 1.5.7 的“四色确实变了”在真实无变色时**不能回勾**，提交其具体验收差异给发布审，而不是把参数标记存在当作颜色变化。只有七步全有证据才报告已启用；生产/外发/L2 未授权的环节保持开放。

### 规格覆盖表与文档自审

| 原 tasks / Requirement | 本计划落点 |
|---|---|
| 1.1.1–1.1.4 独立开关、唯一日期、#445 | Task1–3；现时 #445 修复与上下文传播分别说明 |
| 1.2.1–1.2.8 全分支/四组合/版本 | Task1–3；矩阵、月末、批中环境变化、service audit/UI |
| 1.2.9–1.2.13 差值与接通/变色守卫 | Task2逐日；Task3旧函数/漏参元测试、D5实际四色；Task4later/redder反例 |
| 1.3.1–1.3.6 回归/双黄金/平台/严格校验 | Task5.2–3，不将 skip/历史或基础 CI 作新通过 |
| 1.4.1–1.4.4 真实冻结对照/三不变式/离线对比/反读防护 | Task4完整runner；Task5.4–6真实来源与姚复核 |
| 1.5.1–1.5.7 逐项授权上线七步 | Task5.7–8，CreationDate、先OFF、签认、启用与实际数字；真实无变色不能假勾1.5.7 |
| 原 §2 P2、§3 专业签认、§4整包收口 | 范围保留，P2另计划/独立开启；D4/专业/整包验收不由P1计划销号 |

文档自审检查：接口定义与调用名/keyword一致；五项 Review Focus均有拥有其实现的具体测试；没有新增产品源或执行测试。Markdown代码只做语法解析与人工源接口对照，不导入产品模块、不当产品验证。正式实施时每一步的红/绿、commit、review及运行环境仍据实际结果登记。

**请求的这次审阅**：确认本完整计划及其中 mock/离线回归验证范围，沿用当前 Native；批准后走正式 Guardian 与获准隔离树实施。真实取数、ff、生产部署、姚祖怡签认与外发在各自环节另取针对该项的授权。完整项目与 SC8 P2 尚未完工。
