# FI8 名义曲线与 what-if Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. 当前 Native 方法沿用；本主仓会话只准备、核验和正式编排，业务写入必须在获准 Guardian 同仓隔离工作树。所有派生模型显式 `gpt-6-luna`。

**Goal:** 落实已经批准的 FI8 D1–D17：CNY mock 应收/应付按明确输入区间生成“名义，非预测”的净流量曲线，在其上叠加可追溯 what-if，准备独立后端、受控门户呈现及每次生成的 audit；预测、告警和真实接线保留未完成项。

**Architecture:** 算术纯函数消费显式 mock 周区间，不采用财务周默认。服务层验证 synthetic/版本/身份并写 append-only audit 后才交付曲线；独立 Flask 工厂承载呈现及 auth 接入点，网关采用 finance 路由。当前不监听新端口、不部署或合并生产服务。

**Tech Stack:** Python >=3.11、stdlib Decimal/date/dataclasses、现有 zhuopin_platform audit/criteria_signoff；Flask 工厂采用网关既有 Flask 栈，FI8 pyproject 显式声明同一依赖。测试待本具体计划的验证范围获准后逐项目执行。

**Spec:** `4-数字员工/财务部/FI8-现金流预测与智能预警/intent.md`（2026-09-08 已确认）；`openspec/changes/fi8-cashflow-forecast-mvp/design.md`（整包已审 D1–D17）；同包三个 delta specs 与 tasks。计划实现 design 已允许部分，不重新 grill 已定方向。

## Global Constraints

1. 输出流入/流出/逐周净额/累计净额；不输出 closing_balance，不读 opening_balance，不以0或推算银行余额绕过授权。
2. 4/8/12 周来自场景定义；周起始日/跨月/跨年业务口径 FI8-G-02 未签认。函数要求显式合成区间，不把合成区间认成公司财务口径；real 请求一律 fail-loud。
3. 名义层全程标“名义，非预测”；预测层留空并标“预测层待 PAYMENT_CYCLE_SAMPLING 签认”；不根据合同日假装预测回款。
4. what-if 同页并排、异色底、标“假设情景，非预测”；不能关闭假设标记，不进导出/推送，结果携带 baseline_ref。
5. 判据无默认值。按 D11 新增 CREDIT_LINE_AS_AVAILABLE_FUNDS 的未签认声明；RULE_VERSION 不升。历史1a.5不追改，实际签认数不得从聊天或日期推定。
6. D16 名义生成/what-if 各记一条，包含 RULE_VERSION、输入快照、请求方；audit失败不交付新结果。只存元数据/技术摘要，不写原文或财务单据明细。
7. O2收入递延、missing_snapshot新处理、历史回款预测、缺口窗口、催收、真实U9C/银行/OAuth接线均不在本次实现；原待办保持。
8. `/finance/fi8` 不新起对外端口，后端独立。只准备工厂/路由/auth接入点；现场服务/计划任务/.env/防火墙/生产监听不变。现网真实身份传递未验收，不能称已启用真实门户。
9. 实现前正式 Guardian 提案须绑定实际 design/head 与允许路径；实施/验证/review/ff/部署/外发依次留证。本文无上述执行或通过证据。

## Review Focus

- 到期日正好在区间起/止日：起日归当前区间，止日归下一相邻区间；未覆盖单据须可见，不以总量0掩盖。
- 重复doc_no/非法日期/NaN或Infinity：明确拒绝输入，不重复计数，不悄悄填默认金额/日期。
- 延期把收款移出视界：基线快照不变，情景列明范围外单据，周净额和累计净额同步改变，不生成缺口判定。
- 未可信授权或 audit 写入失败：页面/服务不输出该次计算结果，不用请求正文伪造请求方。
- mock 登录与生产敏感路由：当前仅准备显式路由和空壳auth接点；缺乏真实身份/网关接线证据不能开启真实数据。

## 文件与责任

`R=4-数字员工/财务部/FI8-现金流预测与智能预警`、`C=openspec/changes/fi8-cashflow-forecast-mvp`、`G=5-平台底座/unified-portal-gateway`。以下缩写只为文档阅读；正式 allowed_paths 全用相对正本的逐文件完整路径。

| 文件 | 责任 | 状态 |
|---|---|---|
| R/fi8_cashflow_forecast/models.py | WeeklyCashflow 净额字段与假设标记守卫 | 修改现有 |
| R/fi8_cashflow_forecast/config.py | 第四条未签认声明、问法按 D1/D12；保留银行授权/RULE_VERSION | 修改现有 |
| R/fi8_cashflow_forecast/nominal.py | 显式周区间、净流量纯函数 | 新增 |
| R/fi8_cashflow_forecast/whatif.py | 非破坏性日期位移、基线引用 | 新增 |
| R/fi8_cashflow_forecast/service.py | synthetic/身份/快照校验与 audit | 新增 |
| R/fi8_cashflow_forecast/mock_source.py | 固定工程合成快照与明确区间，无真实通道或预测标准答案 | 新增 |
| R/fi8_cashflow_forecast/webapp.py | 独立 Flask 工厂、呈现/auth接入点 | 新增 |
| R/fi8_cashflow_forecast/templates/fi8.html | 名义/预测/假设区隔，Jinja autoescape | 新增 |
| R/pyproject.toml | 声明 Flask 依赖和模板 package-data | 修改现有 |
| R/tests/test_scaffold.py | 四条注册表及净额契约守卫 | 修改现有 |
| R/tests/test_nominal.py、test_whatif.py、test_service.py、test_webapp.py | 纯 mock 验证 | 各新增 |
| R/CLAUDE.md | 六段式接口/状态/证据，真实未闭项 | 新增，当前不存在 |
| G/portal_gateway/routing.py | FI8显式配置路由，保护默认门户试点 | 修改现有 |
| G/tests/test_routing.py | FI8最长前缀/权限/未配置行为 | 修改现有 |
| C/proposal.md、tasks.md、specs/fi8-forecast-engine/spec.md、specs/fi8-gap-alerting/spec.md、specs/fi8-whatif-engine/spec.md | design 连带条文与名义/预测待办区分 | 修改现有 |
| openspec/specs/fi8-forecast-engine/spec.md、fi8-gap-alerting/spec.md、fi8-whatif-engine/spec.md | 正式sync已审delta | 修改现有，sync后逐条复核 |

不改 design/intent 的已批准历史，不改平台注册表/audit、O2、其他财务场景、运行配置或部署文件。实施发现其他调用者或必要路径时，先报告差异供批准，不扩大白名单。

## Task 0: 正式启动、delta 与 tasks 对齐

**Files:** 上表 C 与主spec；**Consumes:** 已确认intent/D1–D17；**Produces:** 正式受审implementation路径和更新后的名义层待办。

1. 当前Native展示具体计划；按 writing-plans 等审阅答复，保留 Native 方法。该计划的测试代码/命令是待批准的验证范围，本轮不新增或执行。
2. 正式Guardian在获准同仓干净隔离树提案物化此计划，保留原 fi8-cashflow-forecast-mvp 变更；不新造同业务场景。拿实际design_head/SHA/路径白名单批准再进入Task1。
3. 用 D1 将 forecast输出“期末余额”改净额，用 D9 补名义层显式入口和预测签认闸；gap量改累计净流出最深点，告警实现仍待签认；what-if明确叠名义层且不出缺口/导出/推送。D5 六处授权/专业签认分开；不删历史未完成的3.2/3.4/3.5/§4。
4. tasks追加按D9的当次名义/what-if/门户/audit分组，将本轮各项映射到下文Task1–5。2.1/2.2/2.3未解除的部分保持未完成，2.6按D5/D10明确两条路径及“不设backup”的已裁部分。
5. 正式delta `openspec validate fi8-cashflow-forecast-mvp --strict` 后依 openspec-sync-specs 同步三份主spec，逐条核对。结构通过不替代设计/专业签认或产品测试。

## Task 1: 显式 mock 周区间和净流量

实施顺序为下列跟踪项；本文先展示契约/代码再展示测试便于阅读，执行时必须先红后绿。

- [ ] 1.1 将本Task具体测试与四条unsigned期望写入指定测试文件；先运行取得缺新接口/声明的红证据。
- [ ] 1.2 按Step1模型/配置和Step2算法修改指定源文件；不读取未签判据或银行余额。
- [ ] 1.3 运行下文指定子项目命令取得绿证据，核对回归统计；外层驱动提交绑定HEAD。

**Files:** R/fi8_cashflow_forecast/{models,config,nominal}.py；R/tests/{test_scaffold,test_nominal}.py。

**Interfaces:** `WeekPeriod(start:date,end:date,label:str)`；`NominalResult(snapshot_id,horizon,points,outside_horizon,label)`；`build_nominal(ar,ap,*,periods,horizon,snapshot_id)`。ar/ap仍使用已有ReceivablePlan/PayablePlan。期间由调用方显式提供，无周起始日默认。

**Step1（待实施）**：models的 WeeklyCashflow 以 Decimal 字段 `inflow/outflow/net_flow/cumulative_net_flow` 替代 closing_balance；保存 week_start/index/horizon/rule_version，不改 OpeningBalance/GapWindow 以免冒称其已实现。WhatIfScenario删除可写的is_hypothetical字段，改下面恒True的只读property；config按D11新增未签认Criterion，CASH_GAP_THRESHOLD问法改累计净流出深度，PAYMENT_CYCLE_SAMPLING包含样本不足问法，RULE_VERSION原值不变。

```python
from decimal import Decimal

@dataclass
class WeeklyCashflow:
    week_start: str
    week_index: int
    inflow: Decimal = Decimal(0)
    outflow: Decimal = Decimal(0)
    net_flow: Decimal = Decimal(0)
    cumulative_net_flow: Decimal = Decimal(0)
    horizon: int = 0
    rule_version: str = ""

@dataclass
class WhatIfScenario:
    scenario_id: str
    description: str
    adjustments: dict = field(default_factory=dict)
    baseline_ref: str = ""

    @property
    def is_hypothetical(self) -> bool:
        return True
```

在现有 CRITERIA 声明末尾加 `Criterion(key="CREDIT_LINE_AS_AVAILABLE_FUNDS", question="授信额度算不算可动用资金", owner="财务侧")`，不调用 `.signed()`。`test_scaffold.CRITERIA_KEYS` 的完整新值为 `("CASH_GAP_THRESHOLD","COLLECTION_ESCALATION_CRITERIA","PAYMENT_CYCLE_SAMPLING","CREDIT_LINE_AS_AVAILABLE_FUNDS")`；其参数化unsigned测试自然覆盖新增项，不把历史1a.5的“三条”追改。

**Step2**：新纯函数的完整算法契约为：

```python
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from . import config, models

@dataclass(frozen=True)
class WeekPeriod:
    start: date
    end: date
    label: str

@dataclass(frozen=True)
class NominalResult:
    snapshot_id: str
    horizon: int
    points: tuple
    outside_horizon: tuple[str, ...]
    label: str = "名义，非预测"

def build_nominal(ar, ap, *, periods, horizon, snapshot_id):
    if type(horizon) is not int or horizon not in config.FORECAST_HORIZONS_WEEKS or len(periods) != horizon:
        raise ValueError("period count must match explicit 4/8/12 horizon")
    if not snapshot_id or any(not p.label or p.end-p.start != timedelta(days=7) for p in periods):
        raise ValueError("snapshot and explicit synthetic weekly intervals required")
    if any(a.end != b.start for a, b in zip(periods, periods[1:])):
        raise ValueError("periods must be ordered and contiguous")
    ins = [Decimal(0) for _ in periods]
    outs = [Decimal(0) for _ in periods]
    outside = []
    seen = set()
    for kind, rows, totals in (("AR", ar, ins), ("AP", ap, outs)):
        for row in rows:
            key = f"{kind}:{row.doc_no}"
            if not row.doc_no or key in seen:
                raise ValueError("mock document identity missing or duplicate")
            seen.add(key)
            try:
                due = date.fromisoformat(row.due_date)
                amount = Decimal(str(row.amount))
            except (TypeError, ValueError, InvalidOperation) as exc:
                raise ValueError("invalid date or amount") from exc
            if not amount.is_finite():
                raise ValueError("non-finite amount")
            index = next((i for i,p in enumerate(periods) if p.start <= due < p.end), None)
            if index is None:
                outside.append(key)
            else:
                totals[index] += amount
    cumulative = Decimal(0)
    points = []
    for i, p in enumerate(periods):
        net = ins[i] - outs[i]
        cumulative += net
        points.append(models.WeeklyCashflow(
            week_start=p.start.isoformat(), week_index=i+1,
            inflow=ins[i], outflow=outs[i], net_flow=net,
            cumulative_net_flow=cumulative, horizon=horizon,
            rule_version=config.RULE_VERSION))
    return NominalResult(snapshot_id, horizon, tuple(points), tuple(outside))
```

金额按输入符号和 Decimal 精确算术保留，不引入四舍五入、税额、信用额度或负数业务解释。该mock doc_no唯一约束不是对真实多行账单的归并口径；真实模式未开。

**Step3**：计划内测试输入（新造合成，未读取/冒充现有CSV）：

```python
from datetime import date, timedelta
from decimal import Decimal
import pytest
from fi8_cashflow_forecast import models
from fi8_cashflow_forecast.nominal import WeekPeriod, build_nominal

def periods(n):
    start = date(2026, 12, 28)  # explicit synthetic calendar, not financial signoff
    return tuple(WeekPeriod(start+timedelta(days=7*i), start+timedelta(days=7*(i+1)), f"mock-{i+1}") for i in range(n))

@pytest.mark.parametrize("n", [4, 8, 12])
def test_nominal_boundaries_and_cumulative(n):
    ar = [models.ReceivablePlan("A1","mock-customer",100,"2026-12-28"),
          models.ReceivablePlan("A2","mock-customer",50,"2027-01-04")]
    ap = [models.PayablePlan("P1","mock-supplier",30,"2026-12-31")]
    result = build_nominal(ar,ap,periods=periods(n),horizon=n,snapshot_id="mock-S1")
    assert result.label == "名义，非预测"
    assert len(result.points) == n
    assert result.points[0].net_flow == Decimal("70")
    assert result.points[1].cumulative_net_flow == Decimal("120")
    assert not hasattr(result.points[0], "closing_balance")
```

在同一测试文件再逐个实际给非法日期、重复A1、NaN、非连续区间、空snapshot、范围外日期，断言ValueError或outside_horizon；浮点0.1/0.2用Decimal(str())验证精确净额。test_scaffold注册表期望改四条，新增项仍unsigned；银行授权仍None且不在注册表。

**Step4**：获验证授权后从R根跑 `python -m pytest tests/test_nominal.py tests/test_scaffold.py -q`，记录红→绿和原文，模型只写文件，正式外层提交当次HEAD。

## Task 2: 非破坏性 what-if

- [ ] 2.1 先写本Task合成延期/只读假设/来源失败测试，执行得到红证据。
- [ ] 2.2 实现下文whatif.py并补边界验证；不改基线输入。
- [ ] 2.3 运行下文最具体测试取得绿证据，外层提交并复核本Task差异。

**Files:** R/fi8_cashflow_forecast/whatif.py、R/tests/test_whatif.py。

**Consumes:** Task1的显式期间/名义纯函数与已有WhatIfScenario；**Produces:** `apply_whatif(ar,ap,*,scenario,periods,horizon,baseline)` 返回原基线引用、情景曲线与逐周净额差异。

结构化调整唯一当前形态为 `{"receivable_delay_days":{"A1":30}}`；不接自然语言、不调整金额、不猜客户映射。界面按已选mock单据构造它；批量选择同一mock客户后列出具体doc_no，输入者确认后调用。明确参数是情景假设，不是回款取样标准。

```python
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from .nominal import build_nominal

@dataclass(frozen=True)
class WhatIfResult:
    baseline_ref: str
    scenario_id: str
    curve: object
    net_deltas: tuple
    is_hypothetical: bool = field(default=True, init=False)
    label: str = "假设情景，非预测"

def apply_whatif(ar, ap, *, scenario, periods, horizon, baseline):
    if scenario.is_hypothetical is not True or scenario.baseline_ref != baseline.snapshot_id:
        raise ValueError("hypothetical flag and exact baseline required")
    if not scenario.scenario_id or set(scenario.adjustments) != {"receivable_delay_days"}:
        raise ValueError("unsupported scenario schema")
    expected=build_nominal(ar,ap,periods=periods,horizon=horizon,snapshot_id=baseline.snapshot_id)
    if baseline.horizon != horizon or baseline.points != expected.points:
        raise ValueError("baseline content or horizon mismatch")
    changes = scenario.adjustments["receivable_delay_days"]
    known = {row.doc_no for row in ar}
    if not isinstance(changes, dict) or not set(changes) <= known:
        raise ValueError("unknown receivable")
    shifted = []
    for row in ar:
        days = changes.get(row.doc_no, 0)  # no adjustment means this row stays; not a business criterion
        if type(days) is not int:
            raise ValueError("delay must be an explicit integer number of days")
        shifted.append(replace(row, due_date=(date.fromisoformat(row.due_date)+timedelta(days=days)).isoformat()))
    curve = build_nominal(shifted,ap,periods=periods,horizon=horizon,snapshot_id=baseline.snapshot_id)
    if baseline.horizon != horizon:
        raise ValueError("baseline horizon mismatch")
    deltas = tuple(a.net_flow-b.net_flow for a,b in zip(curve.points,baseline.points))
    return WhatIfResult(baseline.snapshot_id,scenario.scenario_id,curve,deltas)
```

基线必须由服务用同一已固定快照/期间现算并作为对象传入，不能接受客户端造的baseline曲线。延期后新增的范围外单据保留；不把它解释成资金缺口窗口。

计划测试：用Task1合成A1从12/28延期7日，断言原输入due_date不变、第一/二周差异-100/+100、累计末值不变；延期400日断言outside_horizon包含AR:A1且视界末净额减少100；未知单据/错误baseline/horizon/布尔days/非法schema各抛ValueError。传is_hypothetical=False构造必须TypeError，构造后赋值False必须AttributeError，情景结果frozen且flag不可通过构造覆盖。获准后从R根跑 `python -m pytest tests/test_whatif.py -q`；无宣称已执行。

核心测试的完整输入/断言：

```python
from datetime import date,timedelta
from decimal import Decimal
import pytest
from fi8_cashflow_forecast import models
from fi8_cashflow_forecast.nominal import WeekPeriod,build_nominal
from fi8_cashflow_forecast.whatif import apply_whatif

@pytest.mark.parametrize("days,outside",[(7,False),(400,True)])
def test_shift_is_traceable_and_non_destructive(days,outside):
    start=date(2026,12,28)
    periods=tuple(WeekPeriod(start+timedelta(days=7*i),start+timedelta(days=7*(i+1)),f"synthetic-{i}") for i in range(4))
    ar=[models.ReceivablePlan("A1","mock-customer",100,"2026-12-28")]
    baseline=build_nominal(ar,[],periods=periods,horizon=4,snapshot_id="mock-S1")
    scenario=models.WhatIfScenario("mock-WI","mock-delay",{"receivable_delay_days":{"A1":days}},"mock-S1")
    result=apply_whatif(ar,[],scenario=scenario,periods=periods,horizon=4,baseline=baseline)
    assert ar[0].due_date=="2026-12-28"
    assert result.baseline_ref=="mock-S1" and result.is_hypothetical
    assert result.net_deltas[0]==Decimal("-100")
    if outside:
        assert "AR:A1" in result.curve.outside_horizon
        assert result.curve.points[-1].cumulative_net_flow==0
    else:
        assert result.net_deltas[1]==Decimal("100")
        assert result.curve.points[-1].cumulative_net_flow==Decimal("100")

def test_hypothetical_marker_is_read_only():
    scenario=models.WhatIfScenario("mock-WI","mock",{},"mock-S1")
    with pytest.raises(AttributeError):
        scenario.is_hypothetical=False
    with pytest.raises(TypeError):
        models.WhatIfScenario("mock-WI","mock",{},"mock-S1",is_hypothetical=False)
```

## Task 3: 快照、身份与 audit 服务

- [ ] 3.1 先写下文服务/审计/真实模式拒绝测试并跑红。
- [ ] 3.2 实现service.py/mock_source.py，固定SHA和明确合成日历，无共享文件产物。
- [ ] 3.3 跑服务绿证据与tmp_path audit链核验；记录原文和外层HEAD。

**Files:** R/fi8_cashflow_forecast/service.py、R/tests/test_service.py。

**Consumes:** 输入ar/ap、显式期间、snapshot_sha256、source=`synthetic`、currency=`CNY`、请求方来自可信auth回调；**Produces:** `CashflowService.nominal(...)` / `.whatif(...)`。不加载银行余额/真实U9C/历史取样。

```python
import hashlib
import json
from dataclasses import asdict
from zhuopin_platform.audit import AuditEvent
from . import config
from .nominal import build_nominal
from .whatif import apply_whatif

def snapshot_hash(ar, ap, periods, currency):
    payload={"ar":[asdict(r) for r in ar],"ap":[asdict(r) for r in ap],
             "periods":[asdict(p) for p in periods],"currency":currency}
    raw=json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(",",":"),default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

class CashflowService:
    def __init__(self, *, audit):
        if audit is None:
            raise ValueError("audit required")
        self.audit = audit

    def _check(self, source, currency, actor, snapshot_id, calendar_evidence):
        if source != "synthetic":
            raise RuntimeError(config.U9C_AR_AP_NOT_READY)
        if currency != "CNY" or not actor or not snapshot_id or not isinstance(calendar_evidence,str) or not calendar_evidence.startswith("synthetic-"):
            raise ValueError("explicit synthetic CNY snapshot/calendar/actor required")

    def _record(self, action, actor, result, calendar_evidence, scenario_id="", label="名义，非预测", scenario_sha256=""):
        self.audit.record(AuditEvent(
            scenario="FI8", action=action, evaluator=actor, automation_level="L2",
            decision=config.audit_decision(snapshot_id=result.snapshot_id,
                horizon=result.horizon,label=label,scenario_id=scenario_id,
                calendar_evidence=calendar_evidence,scenario_sha256=scenario_sha256),
            data_sources={"ar_ap_snapshot":result.snapshot_id,"calendar":calendar_evidence}))

    def nominal(self, ar, ap, *, periods, horizon, snapshot_id, source, currency, actor, calendar_evidence):
        self._check(source,currency,actor,snapshot_id,calendar_evidence)
        if snapshot_id != snapshot_hash(ar,ap,periods,currency):
            raise ValueError("snapshot content changed")
        result=build_nominal(ar,ap,periods=periods,horizon=horizon,snapshot_id=snapshot_id)
        self._record("nominal_curve_generated",actor,result,calendar_evidence)
        return result

    def whatif(self, ar, ap, *, periods, horizon, snapshot_id, source, currency, actor, calendar_evidence, scenario):
        self._check(source,currency,actor,snapshot_id,calendar_evidence)
        if snapshot_id != snapshot_hash(ar,ap,periods,currency):
            raise ValueError("snapshot content changed")
        baseline=build_nominal(ar,ap,periods=periods,horizon=horizon,snapshot_id=snapshot_id)
        result=apply_whatif(ar,ap,scenario=scenario,periods=periods,horizon=horizon,baseline=baseline)
        encoded=json.dumps(asdict(scenario),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
        self._record("whatif_generated",actor,result.curve,calendar_evidence,result.scenario_id,
                     result.label,hashlib.sha256(encoded).hexdigest())
        return baseline,result
```

`snapshot_id` 是服务装载的固定合成快照SHA，不接受页面任意指定。快照绑定 ar/ap规范序列、期间列表及currency（date/金额原样明确序列化后UTF-8 SHA256），what-if的情景另绑定schema和id；结果audit只存SHA/状态，不存单据。Task4 load_fixture 由构建方提供该快照，客户端只能选择horizon和结构化调整。

新增 mock_source.py 提供以下完整工程fixture函数；它不是财务判例包、公司周口径或真实CSV复刻。原data/mock四表保留，K3拒绝的CSV读取不换途径重读，不宣称已核原表金额。

```python
from datetime import date,timedelta
from . import config,models
from .nominal import WeekPeriod
from .service import snapshot_hash

def load_fixture(horizon):
    if type(horizon) is not int or horizon not in config.FORECAST_HORIZONS_WEEKS:
        raise ValueError("invalid horizon")
    start=date(2026,12,28)
    periods=tuple(WeekPeriod(start+timedelta(days=7*i),start+timedelta(days=7*(i+1)),f"synthetic-{i+1}") for i in range(horizon))
    ar=[models.ReceivablePlan("A1","mock-customer",100,"2026-12-28"),models.ReceivablePlan("A2","mock-customer",50,"2027-01-04")]
    ap=[models.PayablePlan("P1","mock-supplier",30,"2026-12-31")]
    return {"ar":ar,"ap":ap,"periods":periods,"horizon":horizon,
            "snapshot_id":snapshot_hash(ar,ap,periods,"CNY"),"source":"synthetic",
            "currency":"CNY","calendar_evidence":"synthetic-fi8-engineering-v1"}
```

服务未来测试用记录器对象实现 `.record(event)`，断言一次nominal一个事件、一次what-if一个事件、RULE_VERSION及snapshot/actor齐全；坏record抛OSError时没有返回值。参数real/USD/空actor/未声明calendar拒绝，所有四条判据仍unsigned；这不代表专业闸已经通过。

```python
import pytest
from fi8_cashflow_forecast import config
from fi8_cashflow_forecast.mock_source import load_fixture
from fi8_cashflow_forecast.service import CashflowService

class Recorder:
    def __init__(self,fail=False):
        self.events=[]
        self.fail=fail
    def record(self,event):
        if self.fail:
            raise OSError("synthetic audit unavailable")
        self.events.append(event)

def test_nominal_audit_precedes_delivery():
    recorder=Recorder()
    result=CashflowService(audit=recorder).nominal(**load_fixture(4),actor="mock-admin")
    assert len(recorder.events)==1
    assert recorder.events[0].decision["rule_version"]==config.RULE_VERSION
    assert recorder.events[0].decision["snapshot_id"]==result.snapshot_id
    assert recorder.events[0].evaluator=="mock-admin"
    with pytest.raises(OSError):
        CashflowService(audit=Recorder(True)).nominal(**load_fixture(4),actor="mock-admin")

def test_real_currency_and_snapshot_drift_fail():
    service=CashflowService(audit=Recorder())
    data=load_fixture(4)
    with pytest.raises(RuntimeError):
        service.nominal(**{**data,"source":"real"},actor="mock-admin")
    with pytest.raises(ValueError):
        service.nominal(**{**data,"currency":"USD"},actor="mock-admin")
    data["ar"][0].amount=999
    with pytest.raises(ValueError,match="snapshot content changed"):
        service.nominal(**data,actor="mock-admin")
```

获准后从R根跑 `python -m pytest tests/test_service.py -q`。实际JSONL集成仅用tmp_path、平台AuditLogger.jsonl并verify_chain，不能写共享生产路径。

## Task 4: 独立门户工厂和 auth 预留

- [ ] 4.1 先写本Task后端和网关的mock测试分别跑红；不启动监听。
- [ ] 4.2 写工厂/模板/依赖/package-data和条件路由，不修改现场env或部署。
- [ ] 4.3 从R/G分别运行指定集合跑绿，独立核对标签/权限/无导出及错误阻断。

**Files:** R/webapp.py、templates/fi8.html、pyproject.toml、tests/test_webapp.py；G/routing.py、tests/test_routing.py。

**Interfaces:** `create_app(*,service,load_fixture,authorize)`；`load_fixture(horizon)` 返回Task3所需ar/ap/periods/snapshot/source/currency/calendar；`authorize(request)` 返回可信actor字符串或None。三者为必填注入，不提供来源/身份默认。当前验证全部test_client，禁止 app.run/启动监听/真实请求。

后端工厂核心：

FI8 pyproject的dependencies在原项后追加 `"flask>=3.0"`（与现有网关Python栈兼容，实际版本由隔离环境解析，不改全局安装），并增加 `[tool.setuptools.package-data]` 下 `fi8_cashflow_forecast = ["templates/*.html"]`，使发布工厂时模板不丢。

```python
from flask import Flask, abort, render_template, request
from .models import WhatIfScenario

def create_app(*, service, load_fixture, authorize):
    if not callable(load_fixture) or not callable(authorize):
        raise ValueError("explicit mock source and trusted auth callback required")
    app=Flask(__name__)

    @app.before_request
    def gate():
        actor=authorize(request)
        if not actor:
            abort(403)
        request.environ["fi8_actor"]=actor

    @app.get("/finance/fi8")
    def page():
        horizon=int(request.args.get("horizon","4"))  # published 4-week default view, not week-bucketing policy
        data=load_fixture(horizon)
        baseline=service.nominal(**data,actor=request.environ["fi8_actor"])
        return render_template("fi8.html",baseline=baseline,scenario=None)

    @app.post("/finance/fi8/whatif")
    def whatif():
        body=request.get_json(force=False,silent=False)
        if not isinstance(body,dict) or set(body)!={"horizon","scenario_id","description","adjustments","baseline_ref"}:
            abort(400)
        data=load_fixture(body["horizon"])
        scenario=WhatIfScenario(scenario_id=body["scenario_id"],description=body["description"],
            adjustments=body["adjustments"],baseline_ref=body["baseline_ref"])
        baseline,result=service.whatif(**data,actor=request.environ["fi8_actor"],scenario=scenario)
        return render_template("fi8.html",baseline=baseline,scenario=result)

    @app.errorhandler(ValueError)
    def invalid(exc):
        return {"error":"invalid_mock_input"},400
    return app
```

页面使用 Jinja autoescape，不能 `safe` 回显输入。模板完整最小骨架：

```html
<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>FI8 名义曲线</title>
<style>body{font:16px sans-serif}.columns{display:grid;grid-template-columns:1fr 1fr;gap:1rem}table{border-collapse:collapse}th,td{padding:.5rem;border:1px solid #bbb}td{text-align:right}.hypothesis{background:#fff3db}.pending{border:2px dashed #999;padding:1rem}</style>
<h1>FI8 名义净流量</h1><p>合成 mock 数据 · 财务周口径未签认</p>
<nav><a href="/finance/fi8?horizon=4">4周</a> <a href="/finance/fi8?horizon=8">8周</a> <a href="/finance/fi8?horizon=12">12周</a></nav>
<section class="pending">预测层待 PAYMENT_CYCLE_SAMPLING 签认</section>
<div class="columns"><section><h2>名义，非预测</h2><p>快照 {{ baseline.snapshot_id }}</p>
<table><tr><th>区间起日</th><th>流入</th><th>流出</th><th>净额</th><th>累计净额</th></tr>
{% for p in baseline.points %}<tr><td>{{ p.week_start }}</td><td>{{ p.inflow }}</td><td>{{ p.outflow }}</td><td>{{ p.net_flow }}</td><td>{{ p.cumulative_net_flow }}</td></tr>{% endfor %}</table>
<p>视界外单据 {{ baseline.outside_horizon }}</p></section>
<section class="hypothesis"><h2>假设情景，非预测</h2>
{% if scenario %}<p>基线 {{ scenario.baseline_ref }} · 情景 {{ scenario.scenario_id }}</p><table><tr><th>区间起日</th><th>情景净额</th><th>累计净额</th><th>与基线差异</th></tr>
{% for p in scenario.curve.points %}<tr><td>{{ p.week_start }}</td><td>{{ p.net_flow }}</td><td>{{ p.cumulative_net_flow }}</td><td>{{ scenario.net_deltas[loop.index0] }}</td></tr>{% endfor %}</table><p>视界外单据 {{ scenario.curve.outside_horizon }}</p>
{% else %}<p>尚未运行假设情景</p>{% endif %}</section></div>
</html>
```

模板在hypothesis section前加入以下完整合成输入操作，POST body只用上述五字段，没有rawactor/source/currency入口、自然语言解析、导出或推送按钮。

```html
<form id="fi8-adjust"><label>合成应收单 <select id="doc"><option>A1</option><option>A2</option></select></label>
<label>假设延期天数 <input id="days" type="number" step="1" required></label><button>运行假设情景</button></form>
<p id="fi8-error" role="alert"></p>
<script>
document.getElementById('fi8-adjust').addEventListener('submit',async function(event){
  event.preventDefault();
  const body={horizon:{{ baseline.horizon|tojson }},scenario_id:'mock-user-scenario',description:'显式合成延期情景',
    adjustments:{receivable_delay_days:{[document.getElementById('doc').value]:Number(document.getElementById('days').value)}},
    baseline_ref:{{ baseline.snapshot_id|tojson }}};
  const response=await fetch('/finance/fi8/whatif',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(!response.ok){document.getElementById('fi8-error').textContent='情景未生成，请检查输入或授权';return;}
  const html=await response.text();document.open();document.write(html);document.close();
});
</script>
```

空日期/金额及不认识结构都不自动纠正。Jinja tojson处理插入JS的固定快照，不用用户HTML插值。表单无开放外部URL，同源fetch；CSRF/auth身份的真实网关接线另属启用前证据，当前不对外暴露后端。正式后端运行器不在范围，不以工厂存在宣称可常驻。

网关未来变更：只在显式 `PORTAL_GATEWAY_FI8_BACKEND` 已由运维配置且生产mock登录条件复核后追加 `Route(prefix="/finance/fi8", backend_base_url=backend, domain="finance", required_tier=PermissionTier.DOMAIN_ADMIN)`；该financial明细/计算属于敏感/操作面。env为空不注册新路由，不设数字端口默认，不改默认门户试点。实际URL透传行为须用existing gateway测试锁住完整prefix，不能自行假设剥离前缀。authorize目前是预留必填回调，不从用户自报header取得可信身份；未来真实启用必须补身份传播证据。

替换现有 default_route_table() 的具体代码（其余routing函数保持）：

```python
def default_route_table() -> list[Route]:
    from portal_gateway.sso import mock_login_enabled
    backend=os.environ.get("PORTAL_GATEWAY_HOME_BACKEND","http://127.0.0.1:8092")
    routes=[Route(prefix="/",backend_base_url=backend,domain="portal",
                  required_tier=PermissionTier.PUBLIC_READ,backend_gate_password_env="ZP_GATE_PASSWORD")]
    fi8_backend=(os.environ.get("PORTAL_GATEWAY_FI8_BACKEND") or "").strip()
    if fi8_backend:
        if mock_login_enabled():
            raise RuntimeError("FI8 finance route requires mock login disabled")
        routes.append(Route(prefix="/finance/fi8",backend_base_url=fi8_backend,domain="finance",
                            required_tier=PermissionTier.DOMAIN_ADMIN))
    return routes
```

该分支不自动设env或接网，域管理员人员/真实网关认证按正本，不新增用户授权。source backend与网关认证回调未真实接线前，即使配置backend也不是可启用的真实FI8服务。

计划测试：test_client分别无actor403、授权mockGET200及三标签、POST延期得到并排差异、请求body自报actor/source被400拒绝、错误baseline400、注入脚本转义、audit失败不成功返回；任何 `/export` `/push` 均404。网关分别未配置无新增route、显式mockbackendfinance/admin route、前缀最长匹配和未授权拒绝，mock登录+真实敏感路由不得启用。获准后从R根跑 `python -m pytest tests/test_webapp.py -q`，另从G根跑 `python -m pytest tests/test_routing.py tests/test_permissions.py tests/test_webapp.py -q`；不从repo根混跑。

```python
from fi8_cashflow_forecast.mock_source import load_fixture
from fi8_cashflow_forecast.service import CashflowService
from fi8_cashflow_forecast.webapp import create_app

class Sink:
    def record(self,event):
        self.last=event

def test_page_and_hypothesis_gate():
    service=CashflowService(audit=Sink())
    denied=create_app(service=service,load_fixture=load_fixture,authorize=lambda request:None).test_client()
    assert denied.get("/finance/fi8").status_code==403
    client=create_app(service=service,load_fixture=load_fixture,authorize=lambda request:"mock-admin").test_client()
    response=client.get("/finance/fi8")
    assert response.status_code==200
    text=response.get_data(as_text=True)
    assert "名义，非预测" in text and "PAYMENT_CYCLE_SAMPLING" in text
    assert "假设情景，非预测" in text
    body={"horizon":4,"scenario_id":"mock-WI","description":"mock", "adjustments":{"receivable_delay_days":{"A1":7}},"baseline_ref":load_fixture(4)["snapshot_id"]}
    assert client.post("/finance/fi8/whatif",json=body).status_code==200
    assert client.post("/finance/fi8/whatif",json={**body,"actor":"forged"}).status_code==400
    assert client.post("/finance/fi8/whatif",json={**body,"baseline_ref":"different"}).status_code==400
    assert client.get("/finance/fi8/export").status_code==404
    assert client.post("/finance/fi8/push").status_code==404
```

网关新增的具体守卫测试：

```python
import pytest
from portal_gateway.routing import default_route_table,match_route
from portal_gateway.permissions import PermissionTier

def test_fi8_explicit_route_and_mock_login_rejection(monkeypatch):
    monkeypatch.delenv("PORTAL_GATEWAY_FI8_BACKEND",raising=False)
    assert all(r.prefix!="/finance/fi8" for r in default_route_table())
    monkeypatch.setenv("PORTAL_GATEWAY_FI8_BACKEND","http://127.0.0.1:1") # synthetic unreachable fixture, never contacted
    monkeypatch.delenv("PORTAL_GATEWAY_MOCK_LOGIN",raising=False)
    route=match_route(default_route_table(),"/finance/fi8/whatif")
    assert route.prefix=="/finance/fi8" and route.domain=="finance"
    assert route.required_tier==PermissionTier.DOMAIN_ADMIN
    monkeypatch.setenv("PORTAL_GATEWAY_MOCK_LOGIN","1")
    with pytest.raises(RuntimeError,match="mock login disabled"):
        default_route_table()
```

`http://127.0.0.1:1` 仅是未连接的路由匹配fixture，不是新监听端口/生产配置；可选用现有测试的mock URL值，但不为其启动服务。

## Task 5: 逐项目验证、review 与发布准备

- [ ] 5.1 执行下列两项目的获准完整验证并保存证据；不能替代全项目CI。
- [ ] 5.2 更新当次CLAUDE/tasks与未闭项，保持整包未完工状态。
- [ ] 5.3 独立Luna review实际HEAD，留ff/生产/真实接线/晋档的逐项请求。

**Files:** R/CLAUDE.md、C/tasks.md；实际未闭项见Global Constraints。

1. 按 invoke.ps1 现时隔离runtime与CI矩阵，分别在R、G启动各自完整相关测试；fixture为mock/临时audit，记录命令/cwd/exit/stdout/stderr SHA与统计，禁止改共享全局editable指针。计划命令是 `python -m pytest tests/ -q`，实际python绝对路径由Probe解析后引用。
2. 最近已核的3f9062fc公开CI有未闭失败（本日公开状态核验件，31成功/8失败）；本轮未核后续HEAD的新CI，不能把本项目窄测试当全项目零回归。受影响roots结果和发布时现取全局CI分别报告；失败保留原文，禁止擅自降低baseline或覆盖旧报告。
3. 更新R六段式CLAUDE：定位/决策/依赖/红线/状态/未闭项，写名义已实现与预测/周口径/真实资料/授权/运营未完成，不能报档1、已接U9C或已部署。
4. 独立只读review绑定implementation HEAD，所有派生显式Luna；结论依原始native/hook/改动证据，不凭口头模型自评。正式tasks仅勾实际已做项，§4及权限/数据/专业未闭项保留。
5. 本包尚有真实阻塞待办，写机器认得的 `暂不归档` 理由。不把本次名义层局部完成当整包tasks全完成，不能强行archive或重定义整体成功。
6. 提供实际head/patch-id/验证/review与回滚准备，再逐项申请ff；真实网关接线、生产监听/服务/部署、资料接入、银行授权、专业签认和外发各自单独批准。当前没有任何这些通过证据。

## Self-review 与实施停点

当前审阅计划覆盖 D1–D17 对本轮的全部效力：D1净额、D2不建对客、D3 L8保留、D4区隔、D5路径拆分、D6无LLM、D7通道未核、D8 CNY、D9名义/what-if、D10不设backup、D11第四条声明、D12样本不足保持未签、D13角色收件保持、D14资料信已在途而不重发、D15门户/auth空壳、D16audit、D17先mock机械对账/真实验收待口径与资料。

计划含实际算法和视图示例；它们尚未写产品文件或运行。当前Native完成文档准备后先等本完整计划审阅，正式实施仍由Guardian隔离及实际head证据接力，不修改旧获批设计文本以制造新批准。
