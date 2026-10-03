# FI6 四列度量与月度聚合 Implementation Plan

> **For agentic workers:** 当前执行方式已指定为 **Native**；使用 `executing-plans` 逐任务实施，完整具体计划审阅通过后再经正式 Guardian 进入获准隔离工作树。本文步骤用纯编号。当前文件是准备件，代码块尚未写入产品，也未运行产品测试。

**Goal:** 在显式 mock 输入上同时给出四类度量、月度维度聚合和可追溯门户原型，为财务侧签认提供对照，保持判定与处置未开启。

**Architecture:** 冻结输入快照 → 无判据的纯算术 → 批次和报告两条审计 → 经鉴权的 Flask factory。原三张合成 CSV 保留；另建完整标注的度量示例，经验分位数只从显式逐笔历史计算。网关按显式后端地址条件注册，factory 自身不启动监听。

**Tech Stack:** Python >=3.11（现有 pyproject）、Fraction/Decimal、dataclasses、Flask >=3.0、现有平台 audit 与统一门户网关；未来 pytest 在 FI6 与网关各自目录运行。

**Spec:** `4-数字员工/财务部/FI6-异常交易实时检测/intent.md`；`openspec/changes/fi6-anomaly-detect-mvp/{design,tasks}.md` 与三份 delta specs。D1–D19 已批准，本文不是重开这些决策。

## Global Constraints

1. 原 design：“四列度量必须同时产出、同时呈现”。不得把单列原型算成 D1 交付。
2. 原 design：“`data/golden/` 在四条判据签认前保持为空”。mock 不标异常，不进入判例库。
3. 原 D16：“`txn_date` 与 `period` 不一致即标需人工、不进度量”。两个来源值原样保留。
4. 原 D12：`risk_grade` 恒空；`needs_manual_review` 恒真。判定、升级是否成立均无结论，不能把 `escalated=False` 解读成已判定无须推送。
5. 四条 Criterion 仍未签认；`RULE_VERSION = "fi6-skeleton-unsigned-2026-09-03"` 不升版。新增形态常量只记录 batch 降级，不设置日/班次周期。
6. real 模式显式 `U9C_TXN_NOT_READY`，不回退 mock；不连 U9C，不读取真实交易，不发通知、不写回付款。
7. 财务交易数据按现有财务域边界处理；后续混入 OEM 技术资料时另过隔离审查。L2 与专业口径由人签认。
8. 不新起端口、不合并后端进程；门户路径 `/finance/fi6`。ff、`.51`、真实对外发送各按原规则取得针对该项授权。
9. 报告标注“AI 分析建议，处置在财务主管”；每批次和每次报告先写平台 audit，失败不呈现数字。
10. 当前 Native 只准备文档；实际构建绑定正式任务、Guardian 与批准的隔离树。不得在主仓创建业务分支或改业务代码。

## Review Focus

1. 只有统计摘要，无逐笔历史：分位数不可推得，四类度量一起留空并说明缺证据，不能使用正态分布近似（Task 2）。
2. 两个期间冲突、重复交易号、AP/AR 相同单位：冲突不进度量、重复拒绝、方向分开，不出现双计（Task 1/2）。
3. 零均值/中位数/标准差、负交易与并列历史值：数学未定义时不造结果；符号保留；分位次给严格/包含相等两个累计比例（Task 2）。
4. 经办字段缺失：归“未提供经办”证据组，不猜姓名或岗位；报告仍包含缺列计数和所有维度（Task 2）。
5. 未鉴权、审计任一步失败、网关误用全局公开权限：阻止数字呈现、保留已追加审计、财务场景须域管理员（Task 3/4）。

## 0. 当前事实、具体新增选择与执行入口

### 0.1 取证边界

2026-10-03 本次封存 24 个命名公开来源；manifest 为 `fi6-measurements-plan-source-bindings.json`（SHA `1329079ad12478c66976a11b80e8ac2a6f2b24ff6bab1b319a388e360a9a0fdb`），捕获前后 HEAD 均为 `cf9cb1431cf3eb8c037eec5fcff7542234f3b0f4`。实施前重新捕获，不把该 HEAD 当长期固定事实。

现有 FI6 只有 models/config 骨架，没有度量引擎、报告或服务入口。交易 4 笔、单位 3 个、摘要基线 3 条。基线是 `sample_months/mean_amount/median_amount/stddev_amount/mean_monthly_count`，没有逐笔分布、基线期间、经办或标准差种类。不能从摘要反推经验分位数，也不能断言提供的标准差使用总体/样本算法。

FI3 已有 `ValidationVerdict(req_no, outcome, findings, rule_version, …)` / `CheckFinding(check_id, code, level, …)`。旧 `FI3_NO_ENTITY` 是 9 月 3 日历史描述，不能用来判断现时不存在。FI6 只留显式引用，不改 FI3，也不从 `source_doc` 猜付款申请号。

当前前置总表 v11 已有 FI6 行，启动月 **2026-10**、Owner **待指派**；原无行/2027-04 属历史。财务部 #20 已推送 2026-09-23 01:02 UTC、仍在途；本次公开闸查询无未拆件，下一号21。该信第2项已索取 FI6 的12–24个月应收应付流水和单位主数据；真实回件未验证，不重复发信。

### 0.2 本文需要具体审阅的新增内容

原 design 2026-09-17 追记仍要求 §2 逐条关闭后进入 §3。本计划提议把**mock 度量原型**与**真实判定/资料/通道**分开审核；本计划未获审阅前不自行拆掉原门槛，不改 tasks 勾选。

技术表示也明确列出，供本次具体计划审阅：倍数列同时列 `金额/提供均值` 与 `金额/提供中位数`；经验分位次列同时列 `历史金额<当前金额的比例` 与 `历史金额<=当前金额的比例`，不做百分位插值；绝对额列为 `abs(原金额)`，原带符号金额另列；σ列为 `(原金额-提供均值)/提供标准差`，展示标准差来源标签。此表示不给四条业务判据默认值，也不选择真实基线采样口径。任何数学前提缺失，四个度量槽全部空，原始金额仍作为来源字段可见。

新增合成样例采用显式声明的2个月、总体标准差，仅为可复算工程输入；该选择不应用到真实材料。原三张 CSV 不改、不补标签。月度报告对单位、科目、经办三种维度分别分组，并同时给全部度量分量的名次；页面不按其中一列自动重排行。

### 0.3 实施前闸及目录

1. 具体计划、上述表示、mock/真实前置拆分及未来 mock 验证获确认。
2. 正式任务与 Guardian 将本文件路径及 SHA、24源 manifest、准确触碰文件绑定，确认与 FI5/FI8 的网关文件互斥后进入隔离树；并行共享 `routing.py` 时不得同时应用。
3. 根据批准的 Guardian 返回值设置 `$fi6ApprovedTree`，必须是本仓 linked worktree，不能是 `C:/Dev/zhuopin-ai`。路径规范化后核对 `git rev-parse --git-common-dir` 与本仓相同；HEAD 与批准基线不符则回查漂移。不要执行下文命令直到此闸通过。
4. 隔离 Python 使用 invoke.ps1 解析环境，不重装共享 editable 指针；下列 future 命令中的 `$fi6Python` 为 Probe/Guardian 实际返回的绝对解释器路径，`$fi6Scene` 为 `Join-Path $fi6ApprovedTree '4-数字员工/财务部/FI6-异常交易实时检测'`。测试均 `Push-Location -LiteralPath $fi6Scene` 后运行，`finally { Pop-Location }`。

## 文件与接口地图

| 文件 | 责任 |
|---|---|
| `fi6_anomaly_detect/models.py` | 保留原五契约，增加冻结 FI3 结果引用；不引入关联方 bool |
| `fi6_anomaly_detect/inputs.py` | 精确金额、严格 CSV、冻结快照与声明、源 SHA |
| `fi6_anomaly_detect/metrics.py` | 四类度量全有或全空，月度三维聚合与并列名次 |
| `fi6_anomaly_detect/service.py` | 纯算术结果通过两条审计后才交付 |
| `fi6_anomaly_detect/webapp.py` / `templates/fi6.html` | required DI 鉴权、明确期间、转义、所有列并排 |
| `fi6_anomaly_detect/config.py` | apply 时仅加 `DETECTION_TRIGGER_MODE="batch"`，不改注册表/版本 |
| `data/mock/metrics_demo/{transactions,parties,history_baseline,history_values}.csv` / `README.md` | 独立可复算合成输入，原三表保留 |
| `tests/test_inputs.py` / `test_metrics.py` / `test_service.py` / `test_webapp.py` | 下述未来 mock 验证，当前没有建立这些文件 |
| `pyproject.toml` | Flask 依赖与模板 package-data |
| `5-平台底座/unified-portal-gateway/portal_gateway/routing.py` / `tests/test_fi6_route.py` | 条件 route，独立网关验证，后端地址不设默认 |
| 场景 `CLAUDE.md` / change `tasks.md` | 六段说明、按真实证据拆分待办，不归档未完成整包 |

### Task 1: 冻结可追溯输入与独立合成样例

**Files:** 上表 inputs.py、models.py、mock metrics_demo 五件、test_inputs.py。既有 Transaction/PartyProfile/HistoryBaseline/AnomalyFinding/CaseRecord 不删除、不换成这个内部快照类型。

**Interfaces:** `load_snapshot(root: Path, *, mode: str, snapshot_id: str, declaration: SampleDeclaration) -> Snapshot`；Snapshot 供 Task2/3 只读使用。调用方提供声明，没有12月或日期默认。Task1 不判断交易是否异常。

1. 写未来测试 `tests/test_inputs.py`：

```python
from dataclasses import FrozenInstanceError
from fractions import Fraction
from pathlib import Path
import pytest
from fi6_anomaly_detect.inputs import InputInvalid, SampleDeclaration, load_snapshot

DEMO = Path(__file__).resolve().parents[1] / 'data/mock/metrics_demo'
DECL = SampleDeclaration('2026-07', '2026-08', 'all-explicit-synthetic-rows', 'population-synthetic')

def test_exact_frozen_and_source_bound():
    snap = load_snapshot(DEMO, mode='mock', snapshot_id='fi6-demo-v1', declaration=DECL)
    assert snap.transactions[0].amount == Fraction(15)
    assert len(snap.source_hashes) == 4
    with pytest.raises(FrozenInstanceError):
        snap.transactions[0].period = '2026-10'

def test_real_never_reads_or_falls_back(tmp_path):
    with pytest.raises(InputInvalid, match='U9C'):
        load_snapshot(tmp_path, mode='real', snapshot_id='real-request', declaration=DECL)

def test_duplicate_and_invalid_direction(tmp_path):
    for file in DEMO.glob('*.csv'):
        (tmp_path / file.name).write_bytes(file.read_bytes())
    tx = tmp_path / 'transactions.csv'
    text = tx.read_text(encoding='utf-8')
    first = text.splitlines()[1]
    tx.write_text(text + first + '\n', encoding='utf-8')
    with pytest.raises(InputInvalid, match='DUPLICATE_TXN'):
        load_snapshot(tmp_path, mode='mock', snapshot_id='duplicate', declaration=DECL)
    tx.write_text(text.replace(',AP,', ',OTHER,', 1), encoding='utf-8')
    with pytest.raises(InputInvalid, match='DIRECTION'):
        load_snapshot(tmp_path, mode='mock', snapshot_id='bad-direction', declaration=DECL)

def test_nonfinite_and_no_related_field(tmp_path):
    from dataclasses import fields
    from fi6_anomaly_detect.models import PartyProfile
    assert not {'is_related', 'is_related_party', 'related', 'related_party'} & {f.name for f in fields(PartyProfile)}
    for file in DEMO.glob('*.csv'):
        (tmp_path / file.name).write_bytes(file.read_bytes())
    tx = tmp_path / 'transactions.csv'
    tx.write_text(tx.read_text(encoding='utf-8').replace(',15.00,', ',NaN,', 1), encoding='utf-8')
    with pytest.raises(InputInvalid, match='FINITE_AMOUNT'):
        load_snapshot(tmp_path, mode='mock', snapshot_id='bad-amount', declaration=DECL)
```

2. 在获准树内运行单文件确认失败是缺新模块；保留 exit/output，不接受环境错误冒充红测试：`& $fi6Python -m pytest 'tests/test_inputs.py' -q`。

3. 新建 `inputs.py` 的完整内容：

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
import csv
import hashlib
import io
import re
from .config import U9C_TXN_NOT_READY

class InputInvalid(ValueError):
    pass

@dataclass(frozen=True)
class SampleDeclaration:
    start_month: str
    end_month: str
    selection: str
    stddev_basis: str

@dataclass(frozen=True)
class Txn:
    txn_id: str
    direction: str
    party_id: str
    account: str
    amount: Fraction
    txn_date: str
    period: str
    source_doc: str
    operator_id: str

@dataclass(frozen=True)
class Baseline:
    party_id: str
    account: str
    direction: str
    sample_months: int
    mean: Fraction
    median: Fraction
    stddev: Fraction
    mean_monthly_count: Fraction

@dataclass(frozen=True)
class Party:
    party_id: str
    party_name: str
    party_type: str
    unified_social_code: str
    registered_address: str

@dataclass(frozen=True)
class Snapshot:
    snapshot_id: str
    mode: str
    declaration: SampleDeclaration
    transactions: tuple[Txn, ...]
    baselines: tuple[Baseline, ...]
    parties: tuple[Party, ...]
    history: tuple[tuple[str, str, str, Fraction], ...]
    source_hashes: tuple[tuple[str, str], ...]

def money(value: str) -> Fraction:
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError):
        raise InputInvalid('FINITE_AMOUNT_REQUIRED') from None
    if not parsed.is_finite():
        raise InputInvalid('FINITE_AMOUNT_REQUIRED')
    return Fraction(parsed)

def month(value: str) -> str:
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', value):
        raise InputInvalid('MONTH_REQUIRED')
    try:
        date.fromisoformat(value + '-01')
    except ValueError:
        raise InputInvalid('MONTH_REQUIRED') from None
    return value

def load_snapshot(root: Path, *, mode: str, snapshot_id: str, declaration: SampleDeclaration) -> Snapshot:
    if mode == 'real':
        raise InputInvalid(U9C_TXN_NOT_READY)
    if mode != 'mock' or not snapshot_id.strip():
        raise InputInvalid('EXPLICIT_MOCK_SNAPSHOT_REQUIRED')
    if month(declaration.start_month) > month(declaration.end_month):
        raise InputInvalid('SAMPLE_RANGE_INVALID')
    if not declaration.selection.strip() or not declaration.stddev_basis.strip():
        raise InputInvalid('SAMPLE_DECLARATION_REQUIRED')
    source_hashes = []
    def table(name: str, columns: list[str], *, optional: tuple[str, ...] = ()):
        try:
            blob = (root / name).read_bytes()
        except OSError:
            raise InputInvalid('INPUT_TABLE_UNAVAILABLE:' + name) from None
        source_hashes.append((name, hashlib.sha256(blob).hexdigest()))
        try:
            reader = csv.DictReader(io.StringIO(blob.decode('utf-8-sig')))
            actual = reader.fieldnames or []
            if actual != columns and actual != columns + list(optional):
                raise InputInvalid('CSV_SCHEMA_INVALID:' + name)
            rows = list(reader)
        except (UnicodeError, csv.Error):
            raise InputInvalid('CSV_UNREADABLE:' + name) from None
        if any(None in row or any(v is None for v in row.values()) for row in rows):
            raise InputInvalid('CSV_ROW_INVALID:' + name)
        return rows
    txs = []
    seen = set()
    for r in table('transactions.csv', ['txn_id','direction','party_id','account','amount','txn_date','period','source_doc'], optional=('operator_id',)):
        if not all(r[k].strip() for k in ('txn_id','party_id','account')):
            raise InputInvalid('TXN_IDENTIFIERS_REQUIRED')
        if r['txn_id'] in seen:
            raise InputInvalid('DUPLICATE_TXN')
        seen.add(r['txn_id'])
        if r['direction'] not in {'AP', 'AR'}:
            raise InputInvalid('DIRECTION_INVALID')
        try:
            day = date.fromisoformat(r['txn_date'])
        except ValueError:
            raise InputInvalid('TXN_DATE_INVALID') from None
        if day.isoformat() != r['txn_date']:
            raise InputInvalid('TXN_DATE_INVALID')
        txs.append(Txn(r['txn_id'], r['direction'], r['party_id'], r['account'], money(r['amount']),
                       r['txn_date'], month(r['period']), r['source_doc'], r.get('operator_id', '')))
    if not txs:
        raise InputInvalid('EMPTY_TRANSACTION_BATCH')
    baselines = []
    keys = set()
    for r in table('history_baseline.csv', ['party_id','account','direction','sample_months','mean_amount','median_amount','stddev_amount','mean_monthly_count']):
        key = (r['party_id'], r['account'], r['direction'])
        if key in keys or not r['party_id'].strip() or not r['account'].strip() or r['direction'] not in {'AP','AR'}:
            raise InputInvalid('BASELINE_KEY_INVALID')
        keys.add(key)
        try:
            count = int(r['sample_months'])
        except ValueError:
            raise InputInvalid('SAMPLE_MONTHS_INVALID') from None
        if count <= 0:
            raise InputInvalid('SAMPLE_MONTHS_INVALID')
        baselines.append(Baseline(*key, count, money(r['mean_amount']), money(r['median_amount']),
                                  money(r['stddev_amount']), money(r['mean_monthly_count'])))
    parties = []
    ids = set()
    for r in table('parties.csv', ['party_id','party_name','party_type','unified_social_code','registered_address']):
        if not r['party_id'].strip() or r['party_id'] in ids:
            raise InputInvalid('PARTY_ID_INVALID')
        ids.add(r['party_id'])
        parties.append(Party(*(r[k] for k in ['party_id','party_name','party_type','unified_social_code','registered_address'])))
    history = []
    if (root / 'history_values.csv').exists():
        for r in table('history_values.csv', ['party_id','account','direction','amount']):
            if r['direction'] not in {'AP','AR'} or not r['party_id'].strip() or not r['account'].strip():
                raise InputInvalid('HISTORY_KEY_INVALID')
            history.append((r['party_id'], r['account'], r['direction'], money(r['amount'])))
    return Snapshot(snapshot_id, mode, declaration, tuple(txs), tuple(baselines), tuple(parties), tuple(history), tuple(source_hashes))
```

4. 新增 mock 文件，全部位于 `data/mock/metrics_demo/`。这些是明确新建的合成资料，不是既有 CSV 的补全事实：

`transactions.csv`：

```csv
txn_id,direction,party_id,account,amount,txn_date,period,source_doc,operator_id
M-1,AP,MOCK-P1,MOCK-ACCOUNT,15.00,2026-09-01,2026-09,MOCK-DOC-1,MOCK-OP-1
M-2,AP,MOCK-P1,MOCK-ACCOUNT,20.00,2026-09-02,2026-09,MOCK-DOC-2,
M-3,AP,MOCK-P1,MOCK-ACCOUNT,15.00,2026-10-01,2026-09,MOCK-DOC-3,MOCK-OP-1
```

`parties.csv`：

```csv
party_id,party_name,party_type,unified_social_code,registered_address
MOCK-P1,合成单位1,供应商,MOCK-CODE,合成地址1
```

`history_baseline.csv`：

```csv
party_id,account,direction,sample_months,mean_amount,median_amount,stddev_amount,mean_monthly_count
MOCK-P1,MOCK-ACCOUNT,AP,2,10.00,10.00,5.00,2.00
```

`history_values.csv`：

```csv
party_id,account,direction,amount
MOCK-P1,MOCK-ACCOUNT,AP,5.00
MOCK-P1,MOCK-ACCOUNT,AP,5.00
MOCK-P1,MOCK-ACCOUNT,AP,15.00
MOCK-P1,MOCK-ACCOUNT,AP,15.00
```

`README.md` 完整内容：

```markdown
# FI6 度量合成输入 v1
全部字段为工程合成，无真实单位、人员、异常标签。原三张 mock CSV 原样保留。
显式输入声明：start_month=2026-07；end_month=2026-08；selection=all-explicit-synthetic-rows；stddev_basis=population-synthetic。
四个历史金额5、5、15、15：均值10，中位数10，总体方差25，标准差5。
M-1：倍数均值/中位数均为3/2；经验累计比例严格小于=1/2、包含相等=1；绝对额15；σ=1。
M-2：倍数均为2；经验比例均为1；绝对额20；σ=2。
M-3：原日期2026-10-01与账期2026-09不一致，四列都空、需人工、不分桶。
经办MOCK-OP-1是假标识；M-2经办未提供，不推断。没有哪笔异常、哪家关联的判断。
2个月与总体标准差仅为此合成输入，不能转为真实业务默认或专业签认。
```

5. 在 `models.py` 保留原类并追加下述冻结引用类；Transaction 最末加 `fi3_result: Optional[FI3ResultRef] = None`（已有 `from __future__ import annotations` 允许后定义）。不把上游 outcome 翻译成 FI6 risk_grade：

```python
@dataclass(frozen=True)
class FI3ResultRef:
    req_no: str
    outcome: str
    check_ids: tuple[str, ...]
    rule_version: str
    source_snapshot_sha256: str
```

映射必须显式提供 txn_id→req_no，后续真实适配器另审。本原型不产生该映射，未关联显示“未提供 FI3 引用”；不猜原单据关联。冻结类只消费 FI3 真实字段，额外 SHA 是本方来源证据，不要求上游新增能力。

6. 同目录重跑 `tests/test_inputs.py`、既有 `test_scaffold.py`；未签认注册表、关联字段缺席、原默认侧全部保留。记录真实结果后按准确文件表在隔离树提交 Task1。不得因原 legacy 缺逐笔历史而修改原 CSV。

### Task 2: 同时产出四类度量及月度三维聚合

**Files:** Create `fi6_anomaly_detect/metrics.py`；Create `tests/test_metrics.py`。

**Interfaces:** `measure(snapshot: Snapshot) -> tuple[MetricRow, ...]`；`monthly(rows: tuple[MetricRow, ...], *, period: str) -> MonthlyReport`。金额与比例全用 Fraction，无浮点阈值；输出冻结，顺序沿原交易顺序。月度只有显式 period，无日期默认。数据排序仅用于中位数及报告所有分量的排名，不能成为逐笔默认视图。

1. 写完整的未来测试 `tests/test_metrics.py`：

```python
from dataclasses import replace, FrozenInstanceError
from fractions import Fraction as F
from pathlib import Path
import pytest
from fi6_anomaly_detect.inputs import SampleDeclaration, load_snapshot
from fi6_anomaly_detect.metrics import measure, monthly

def snapshot():
    return load_snapshot(Path(__file__).resolve().parents[1] / 'data/mock/metrics_demo',
                         mode='mock', snapshot_id='demo', declaration=SampleDeclaration(
                         '2026-07','2026-08','all-explicit-synthetic-rows','population-synthetic'))

def test_all_four_exact_and_never_judges():
    rows = measure(snapshot())
    assert rows[0].values == (F(3,2), F(3,2), F(1,2), F(1), F(15), F(1))
    assert rows[1].values == (F(2), F(2), F(1), F(1), F(20), F(2))
    assert rows[2].values is None and rows[2].blockers == ('PERIOD_CONFLICT',)
    assert all(r.risk_grade == '' and r.needs_manual_review and r.judgment is None and r.escalation is None for r in rows)
    with pytest.raises(FrozenInstanceError):
        rows[0].risk_grade = 'high'

def test_summary_alone_and_zero_divisors_keep_all_slots_empty():
    snap = snapshot()
    assert all(r.values is None for r in measure(replace(snap, history=())))
    for field in ('mean', 'median', 'stddev'):
        base = replace(snap.baselines[0], **{field: F(0)})
        rows = measure(replace(snap, baselines=(base,)))
        assert rows[0].values is None and rows[0].blockers
    conflict = replace(snap.baselines[0], mean=F(99))
    assert 'BASELINE_SUMMARY_CONFLICT' in measure(replace(snap, baselines=(conflict,)))[0].blockers

def test_direction_isolated_and_negative_source_preserved():
    snap = snapshot()
    ar = replace(snap.transactions[0], txn_id='AR-1', direction='AR', amount=F(-5))
    rows = measure(replace(snap, transactions=(ar,)))
    assert rows[0].values is None and 'BASELINE_ABSENT' in rows[0].blockers
    neg = replace(snap.transactions[0], txn_id='CREDIT-1', amount=F(-5))
    row = measure(replace(snap, transactions=(neg,)))[0]
    assert row.source_amount == F(-5)
    assert row.values == (F(-1,2), F(-1,2), F(0), F(0), F(5), F(-3))

def test_report_all_dimensions_missing_operator_and_unallocated():
    rows = measure(snapshot())
    report = monthly(rows, period='2026-09')
    assert report.period == '2026-09'
    assert {g.dimension for g in report.groups} == {'party', 'account', 'operator'}
    party = next(g for g in report.groups if g.dimension == 'party')
    assert party.count == 2 and party.ready_count == 2 and party.source_total == F(35)
    assert party.means == (F(7,4),F(7,4),F(3,4),F(1),F(35,2),F(3,2))
    assert len(party.ranks) == 6
    assert any(g.dimension == 'operator' and g.key == '未提供经办' for g in report.groups)
    assert [r.txn_id for r in report.unallocated] == ['M-3']
    assert monthly(rows, period='2026-10').groups == ()

def test_no_report_tail_filters_full_evidence():
    rows = measure(snapshot())
    report = monthly(rows, period='2026-09')
    assert report.unallocated == (rows[2],)
    assert len([g for g in report.groups if g.dimension == 'operator']) == 2
    assert all(len(g.ranks) == 6 for g in report.groups)
```

2. 单文件确认失败：`& $fi6Python -m pytest 'tests/test_metrics.py' -q`。只接受缺新实现等预期失败。

3. 新建 `metrics.py` 完整内容：

```python
from __future__ import annotations
from dataclasses import dataclass, replace
from fractions import Fraction as F
from .inputs import InputInvalid, Snapshot, month
from .config import U9C_TXN_NOT_READY

@dataclass(frozen=True)
class MetricRow:
    txn_id: str
    party_id: str
    account: str
    direction: str
    operator_id: str
    txn_date: str
    period: str
    source_amount: F
    values: tuple[F, F, F, F, F, F] | None
    blockers: tuple[str, ...]
    master_gaps: tuple[str, ...]
    stddev_basis: str
    risk_grade: str = ''
    needs_manual_review: bool = True
    judgment: None = None
    escalation: None = None

@dataclass(frozen=True)
class Group:
    dimension: str
    key: str
    direction: str
    count: int
    ready_count: int
    source_total: F
    means: tuple[F, ...] | None
    ranks: tuple[int | None, ...]

@dataclass(frozen=True)
class MonthlyReport:
    period: str
    groups: tuple[Group, ...]
    unallocated: tuple[MetricRow, ...]
    disclaimer: str = 'AI 分析建议，处置在财务主管'

def measure(snapshot: Snapshot) -> tuple[MetricRow, ...]:
    if snapshot.mode != 'mock':
        raise InputInvalid(U9C_TXN_NOT_READY)
    base_by_key = {(b.party_id, b.account, b.direction): b for b in snapshot.baselines}
    parties = {p.party_id: p for p in snapshot.parties}
    result = []
    for t in snapshot.transactions:
        issues = []
        values = None
        key = (t.party_id, t.account, t.direction)
        b = base_by_key.get(key)
        hist = tuple(h[3] for h in snapshot.history if h[:3] == key)
        if t.txn_date[:7] != t.period:
            issues.append('PERIOD_CONFLICT')
        else:
            if snapshot.declaration.end_month >= t.period:
                issues.append('BASELINE_NOT_BEFORE_TRANSACTION')
            if b is None:
                issues.append('BASELINE_ABSENT')
            if not hist:
                issues.append('EMPIRICAL_HISTORY_ABSENT')
            if b is not None:
                if b.mean == 0 or b.median == 0 or b.stddev <= 0:
                    issues.append('BASELINE_DIVISOR_UNDEFINED')
                if hist:
                    hmean = sum(hist, F(0)) / len(hist)
                    ordered = sorted(hist)
                    n = len(ordered)
                    hmedian = ordered[n//2] if n % 2 else (ordered[n//2-1] + ordered[n//2]) / 2
                    if b.mean != hmean or b.median != hmedian:
                        issues.append('BASELINE_SUMMARY_CONFLICT')
                    if snapshot.declaration.stddev_basis == 'population-synthetic':
                        variance = sum(((h - hmean)**2 for h in hist), F(0)) / n
                        if b.stddev**2 != variance:
                            issues.append('SYNTHETIC_STDDEV_CONFLICT')
            if not issues:
                assert b is not None and hist
                values = (t.amount / b.mean, t.amount / b.median,
                          F(sum(h < t.amount for h in hist), len(hist)),
                          F(sum(h <= t.amount for h in hist), len(hist)),
                          abs(t.amount), (t.amount - b.mean) / b.stddev)
        p = parties.get(t.party_id)
        gaps = ['RELATED_CRITERIA_UNSIGNED', 'FI3_REFERENCE_NOT_SUPPLIED']
        if p is None:
            gaps.append('PARTY_PROFILE_ABSENT')
        else:
            if not p.unified_social_code.strip():
                gaps.append('SOCIAL_CODE_ABSENT')
            if not p.registered_address.strip():
                gaps.append('ADDRESS_ABSENT')
        result.append(MetricRow(t.txn_id,t.party_id,t.account,t.direction,t.operator_id,
                                t.txn_date,t.period,t.amount,values,tuple(issues),tuple(gaps),
                                snapshot.declaration.stddev_basis))
    return tuple(result)

def monthly(rows: tuple[MetricRow, ...], *, period: str) -> MonthlyReport:
    month(period)
    allocated = tuple(r for r in rows if r.txn_date[:7] == r.period == period)
    unallocated = tuple(r for r in rows if r.txn_date[:7] != r.period)
    groups = []
    for dimension, attr in [('party','party_id'),('account','account'),('operator','operator_id')]:
        buckets = {}
        for r in allocated:
            key = getattr(r, attr) or '未提供经办'
            buckets.setdefault((key, r.direction), []).append(r)
        dimension_groups = []
        for (key, direction), items in buckets.items():
            ready = [r for r in items if r.values is not None]
            means = tuple(sum((r.values[i] for r in ready), F(0))/len(ready) for i in range(6)) if ready else None
            dimension_groups.append(Group(dimension,key,direction,len(items),len(ready),
                                           sum((r.source_amount for r in items), F(0)),means,(None,)*6))
        for g in dimension_groups:
            ranks = tuple(1 + sum(other.means[i] > g.means[i] for other in dimension_groups
                                 if other.direction == g.direction and other.means is not None)
                          for i in range(6)) if g.means is not None else (None,)*6
            groups.append(replace(g, ranks=ranks))
    return MonthlyReport(period,tuple(groups),unallocated)
```

该报告对每个维度×方向输出全部组：交易笔数、度量可算笔数、带符号金额合计、六个分量均值和各自名次（对应四类度量）。由于四类同时有/空，各度量出现次数均为 ready_count。名次同值同名、按比其大的组数+1，不跨 AP/AR 比，不产生综合风险分数。缺度量行仍在计数和原金额合计中，均值分母明确为 ready_count。期间冲突另列本批次未分桶项，不归任何月份。

4. 增补关系可判定性与 FI3 契约未来测试到 `test_metrics.py`：

```python
def test_master_data_gaps_are_never_related_verdict():
    snap = snapshot()
    rows = measure(replace(snap, parties=()))
    assert 'PARTY_PROFILE_ABSENT' in rows[0].master_gaps
    assert rows[0].needs_manual_review and rows[0].judgment is None
    from fi6_anomaly_detect.models import FI3ResultRef
    ref = FI3ResultRef('MOCK-REQ', 'MOCK-UPSTREAM-OUTCOME', ('FI3-1',), 'mock-source-version', 'a'*64)
    with pytest.raises(FrozenInstanceError):
        ref.outcome = 'changed'

def test_unsigned_criteria_remain_explicit_errors():
    from fi6_anomaly_detect.config import CRITERIA
    from zhuopin_platform.criteria_signoff import CriterionNotSignedOffError
    for key in ('AMOUNT_SURGE_CRITERIA','FREQUENCY_ANOMALY_CRITERIA','RELATED_PARTY_CRITERIA','L2_ESCALATION_CRITERIA'):
        with pytest.raises(CriterionNotSignedOffError):
            CRITERIA.value_of(key)
```

5. future 重跑 inputs/metrics/scaffold；任何失败先找事实，不把比例改成浮点近似来绿测。记录差异为0的 **mock 数学对账**，不宣称真实 Excel 验收完成；Task2 独立提交。

### Task 3: 审计成功后交付度量与报告

**Files:** Create `fi6_anomaly_detect/service.py` / `tests/test_service.py`；Modify config.py 仅追加 batch 形态常量。

**Interfaces:** `prepare(snapshot: Snapshot, *, period: str, actor: str, build_id: str, audit: Recorder) -> Delivery`。Recorder 提供真实 `AuditLogger.record(AuditEvent)` 形状；没有默认审计器、匿名 actor 或通知发送。Delivery 只带冻结 rows/report/快照与结果标识。

1. 写未来 `tests/test_service.py`：

```python
from pathlib import Path
import pytest
from fi6_anomaly_detect.config import RULE_VERSION
from fi6_anomaly_detect.inputs import SampleDeclaration, load_snapshot
from fi6_anomaly_detect.service import AuditUnavailable, prepare

class RecordingAudit:
    def __init__(self, fail_on=0):
        self.events = []
        self.fail_on = fail_on
    def record(self, event):
        if len(self.events) + 1 == self.fail_on:
            raise OSError('synthetic audit failure')
        self.events.append(event)

def snapshot():
    return load_snapshot(Path(__file__).resolve().parents[1] / 'data/mock/metrics_demo', mode='mock',
                         snapshot_id='demo', declaration=SampleDeclaration(
                         '2026-07','2026-08','all-explicit-synthetic-rows','population-synthetic'))

def test_two_bound_events_and_no_notify():
    audit = RecordingAudit()
    result = prepare(snapshot(), period='2026-09', actor='MOCK-ACTOR', build_id='mock-head', audit=audit)
    assert [e.action for e in audit.events] == ['measurement_batch','monthly_measurement_report']
    assert all(e.evaluator == 'MOCK-ACTOR' and e.decision['rule_version'] == RULE_VERSION for e in audit.events)
    assert all(e.decision['snapshot_hash'] == result.snapshot_hash and e.content_hash == result.output_hash for e in audit.events)
    assert result.recipient_role is None and result.notification_state == 'not_enabled'
    assert len(result.output_hash) == len(result.snapshot_hash) == 64

@pytest.mark.parametrize('fail_on', [1,2])
def test_audit_failure_withholds_delivery(fail_on):
    audit = RecordingAudit(fail_on)
    with pytest.raises(AuditUnavailable):
        prepare(snapshot(), period='2026-09', actor='MOCK-ACTOR', build_id='mock-head', audit=audit)
    assert len(audit.events) == fail_on - 1

def test_actor_build_and_real_guard():
    from dataclasses import replace
    from fi6_anomaly_detect.inputs import InputInvalid
    for actor, build in [('', 'mock-head'), ('MOCK-ACTOR','')]:
        with pytest.raises(InputInvalid):
            prepare(snapshot(), period='2026-09', actor=actor, build_id=build, audit=RecordingAudit())
    with pytest.raises(InputInvalid, match='U9C'):
        prepare(replace(snapshot(), mode='real'), period='2026-09', actor='MOCK-ACTOR', build_id='mock-head', audit=RecordingAudit())
```

2. future 单文件确认失败：`& $fi6Python -m pytest 'tests/test_service.py' -q`。

3. `service.py` 完整内容：

```python
from __future__ import annotations
from dataclasses import asdict, dataclass
from fractions import Fraction
from typing import Protocol
import hashlib
import json
from zhuopin_platform.audit import AuditEvent
from .config import U9C_TXN_NOT_READY, audit_decision
from .inputs import InputInvalid, Snapshot
from .metrics import MetricRow, MonthlyReport, measure, monthly

class Recorder(Protocol):
    def record(self, event: AuditEvent) -> None: ...

class AuditUnavailable(RuntimeError):
    pass

@dataclass(frozen=True)
class Delivery:
    snapshot_id: str
    snapshot_hash: str
    output_hash: str
    rows: tuple[MetricRow, ...]
    report: MonthlyReport
    recipient_role: None = None
    notification_state: str = 'not_enabled'

def canonical(value) -> str:
    def convert(item):
        if isinstance(item, Fraction):
            return {'numerator': item.numerator, 'denominator': item.denominator}
        if isinstance(item, dict):
            return {key: convert(val) for key, val in item.items()}
        if isinstance(item, (list,tuple)):
            return [convert(val) for val in item]
        return item
    return json.dumps(convert(value), ensure_ascii=False, sort_keys=True, separators=(',',':'), allow_nan=False)

def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()

def prepare(snapshot: Snapshot, *, period: str, actor: str, build_id: str, audit: Recorder) -> Delivery:
    if snapshot.mode != 'mock':
        raise InputInvalid(U9C_TXN_NOT_READY)
    if not actor.strip() or not build_id.strip():
        raise InputInvalid('TRUSTED_ACTOR_AND_BUILD_REQUIRED')
    rows = measure(snapshot)
    report = monthly(rows, period=period)
    snapshot_hash = digest(asdict(snapshot))
    output_hash = digest({'rows': [asdict(r) for r in rows], 'report': asdict(report)})
    shared = dict(snapshot_id=snapshot.snapshot_id, snapshot_hash=snapshot_hash,
                  output_hash=output_hash, build_id=build_id, period=period,
                  kind='measurement_only', trigger_mode='batch', sampling=asdict(snapshot.declaration))
    for action, counts in [('measurement_batch', {'row_count':len(rows), 'ready_count':sum(r.values is not None for r in rows)}),
                            ('monthly_measurement_report', {'group_count':len(report.groups), 'unallocated_count':len(report.unallocated)})]:
        event = AuditEvent(scenario='FI6', action=action, evaluator=actor, automation_level='L2',
                           decision=audit_decision(**shared, **counts),
                           data_sources=dict(snapshot.source_hashes), content_hash=output_hash)
        try:
            audit.record(event)
        except Exception:
            raise AuditUnavailable('AUDIT_WRITE_FAILED') from None
    return Delivery(snapshot.snapshot_id,snapshot_hash,output_hash,rows,report)
```

`Recorder` 的 `...` 是 Protocol 方法声明，非省略实现。真实 audit 对象由部署组装；本原型不用 FI1 的默认匿名 evaluator。两个写入不是事务：第一条成功第二条失败时，保留第一条追加记录并拒绝交付，不删除或回写审计。重试产生新的批次运行记录，输入/输出 hash 相同可追溯，不冒充一次且仅一次执行。

4. apply 时在 config.py 追加唯一形态值：

```python
# 当前约束下的降级，仅记录批次形态；无轮询周期、无实时能力承诺。
DETECTION_TRIGGER_MODE = 'batch'
```

将 service.shared 中 `trigger_mode='batch'` 换为从 config 导入的 `DETECTION_TRIGGER_MODE`（同时保留 U9C_TXN_NOT_READY、audit_decision 导入）。规则版本与四项注册表逐字节对照不漂移；该常量不是 Criterion，也不把 FI6-G-02 自动加入注册表。

5. future 重跑 inputs/metrics/service/scaffold 四文件。检查审计 payload 不含原始单位地址、社会信用代码或银行账号；只含来源标识/hash、参数与汇总数量。Task3 独立提交。

### Task 4: 有鉴权的门户原型、条件路由与准备交付

**Files:** Create webapp.py、templates/fi6.html、test_webapp.py、场景 CLAUDE.md；Modify pyproject.toml；条件 Modify gateway/routing.py、Create gateway/tests/test_fi6_route.py；精确更新本变更 tasks.md 的实际子项。

**Interfaces:** `create_app(*, authorize: Callable[[], str|None], snapshot_provider: Callable[[], Snapshot], audit: Recorder, build_id: str) -> Flask`。authorize 只能返回已验证的财务域管理员 actor；真实网关 identity/binding 未明确前，不对真实服务注册可访问路由。不信 `X-Actor`、查询参数或任意 userid。

1. 写未来 `tests/test_webapp.py`：

```python
from pathlib import Path
import pytest
from fi6_anomaly_detect.inputs import SampleDeclaration, load_snapshot
from fi6_anomaly_detect.webapp import create_app

class Audit:
    def __init__(self, fail=False):
        self.events = []
        self.fail = fail
    def record(self, event):
        if self.fail:
            raise OSError('synthetic failure')
        self.events.append(event)

def provider():
    return load_snapshot(Path(__file__).resolve().parents[1]/'data/mock/metrics_demo', mode='mock',
                         snapshot_id='demo', declaration=SampleDeclaration(
                         '2026-07','2026-08','all-explicit-synthetic-rows','population-synthetic'))

def app(authorize=lambda: 'MOCK-ADMIN', audit=None):
    return create_app(authorize=authorize, snapshot_provider=provider, audit=audit or Audit(), build_id='mock-head')

def test_required_auth_and_header_cannot_impersonate():
    with pytest.raises(TypeError):
        create_app()
    client = app(authorize=lambda: None).test_client()
    assert client.get('/finance/fi6?period=2026-09', headers={'X-Actor':'MOCK-ADMIN'}).status_code == 403

def test_explicit_period_and_four_parallel_columns():
    audit = Audit()
    client = app(audit=audit).test_client()
    assert client.get('/finance/fi6').status_code == 200 and not audit.events
    for query in ('?period=2026-09&period=2026-10','?period=bad','?period=2026-09&sort=sigma'):
        assert client.get('/finance/fi6'+query).status_code == 400
    response = client.get('/finance/fi6?period=2026-09')
    text = response.get_data(as_text=True)
    assert response.status_code == 200 and len(audit.events) == 2
    for label in ('四种度量并列，未选口径','倍数','经验分位次','绝对额','σ偏离','待四条判据签认','未提供经办','本批次未分桶'):
        assert label in text
    assert '3/2' in text and 'MOCK-OP-1' in text
    assert 'AI 分析建议，处置在财务主管' in text

def test_audit_failure_does_not_show_measurements():
    response = app(audit=Audit(fail=True)).test_client().get('/finance/fi6?period=2026-09')
    assert response.status_code == 503 and '3/2' not in response.get_data(as_text=True)

def test_autoescape_source_identifier():
    from dataclasses import replace
    snap = provider()
    snap = replace(snap, transactions=(replace(snap.transactions[0], operator_id='<script>x</script>'),))
    client = create_app(authorize=lambda:'MOCK-ADMIN', snapshot_provider=lambda:snap, audit=Audit(), build_id='mock-head').test_client()
    text = client.get('/finance/fi6?period=2026-09').get_data(as_text=True)
    assert '<script>x</script>' not in text and '&lt;script&gt;x&lt;/script&gt;' in text
```

2. future 单文件确认失败：`& $fi6Python -m pytest 'tests/test_webapp.py' -q`。

3. 新建 `webapp.py` 完整内容：

```python
from __future__ import annotations
from typing import Callable
from flask import Flask, Response, render_template, request
from .inputs import InputInvalid, Snapshot, month
from .service import AuditUnavailable, Recorder, prepare

def create_app(*, authorize: Callable[[],str|None], snapshot_provider: Callable[[],Snapshot],
               audit: Recorder, build_id: str) -> Flask:
    if not callable(authorize) or not callable(snapshot_provider) or not build_id.strip():
        raise ValueError('EXPLICIT_DEPENDENCIES_REQUIRED')
    app = Flask(__name__)
    app.add_template_filter(lambda value: '' if value is None else str(value), 'exact')
    @app.get('/finance/fi6')
    def view():
        actor = authorize()
        if not actor or not actor.strip():
            return Response('无财务域访问权限', status=403)
        if set(request.args) - {'period'} or len(request.args.getlist('period')) > 1:
            return Response('仅接受一个明确月份，不支持单列排序', status=400)
        period = request.args.get('period')
        if period is None:
            return render_template('fi6.html', delivery=None)
        try:
            month(period)
            delivery = prepare(snapshot_provider(), period=period, actor=actor, build_id=build_id, audit=audit)
        except InputInvalid:
            return Response('输入或基线资料未就绪，请核对来源与月份', status=400)
        except AuditUnavailable:
            return Response('审计写入失败，本次结果未交付', status=503)
        return render_template('fi6.html', delivery=delivery)
    return app
```

没有 `app.run()`、绑定 host/port 或默认弱鉴权。authorize 抛错不视为放行；实际 auth 装配失败留错误，由服务守护恢复。未选月份只给表单、不取数据、不生成数字。预留 callback 不是生产 SSO 已打通证明。

4. `templates/fi6.html` 完整内容：

```html
<!doctype html><html lang="zh"><head><meta charset="utf-8"><title>FI6 度量对照</title></head><body>
<h1>FI6 mock 度量对照</h1><p>四种度量并列，未选口径；待四条判据签认。</p>
<p>当前为约束下的批次降级。AI 分析建议，处置在财务主管。</p>
<form method="get"><label>明确月份 <input name="period" type="month" required></label><button>生成对照</button></form>
{% if delivery %}
<h2>逐笔证据（本批次完整顺序）</h2>
<table><thead><tr><th>交易</th><th>方向</th><th>单位/科目</th><th>经办</th><th>原日期/账期</th><th>原金额</th><th>倍数（均值/中位数）</th><th>经验分位次（严格小于/包含相等）</th><th>绝对额</th><th>σ偏离（提供标准差）</th><th>判定：待四条判据签认</th><th>人工确认</th></tr></thead><tbody>
{% for r in delivery.rows %}<tr><td>{{r.txn_id}}</td><td>{{r.direction}}</td><td>{{r.party_id}} / {{r.account}}</td><td>{{r.operator_id or '未提供经办'}}</td><td>{{r.txn_date}} / {{r.period}}</td><td>{{r.source_amount|exact}}</td>
{% if r.values %}<td>{{r.values[0]|exact}} / {{r.values[1]|exact}}</td><td>{{r.values[2]|exact}} / {{r.values[3]|exact}}</td><td>{{r.values[4]|exact}}</td><td>{{r.values[5]|exact}}（{{'该合成样例：总体标准差' if r.stddev_basis == 'population-synthetic' else '按输入提供，种类未签认'}}）</td>{% else %}<td></td><td></td><td></td><td></td>{% endif %}
<td></td><td>需人工；关联口径未签认，FI3 引用未提供{% if 'PARTY_PROFILE_ABSENT' in r.master_gaps %}；单位主数据未提供{% endif %}{% if r.blockers %}；度量输入不足或期间冲突，四列留空{% endif %}</td></tr>{% endfor %}
</tbody></table>
<h2>{{delivery.report.period}} 月度聚合</h2><p>所有单位、科目、经办组并列；各列名次仅描述数值，不代表严重程度，不触发推送。均值分母为度量可算笔数；金额合计保留来源符号。</p>
<table><thead><tr><th>维度/组/方向</th><th>笔数/可算笔数</th><th>原金额合计</th><th>倍数均值/两名次</th><th>分位次均值/两名次</th><th>绝对額均值/名次</th><th>σ均值/名次</th></tr></thead><tbody>
{% for g in delivery.report.groups %}<tr><td>{{{'party':'单位','account':'科目','operator':'经办'}[g.dimension]}} / {{g.key}} / {{g.direction}}</td><td>{{g.count}} / {{g.ready_count}}</td><td>{{g.source_total|exact}}</td>
{% if g.means %}<td>{{g.means[0]|exact}} / {{g.means[1]|exact}}；{{g.ranks[0]}} / {{g.ranks[1]}}</td><td>{{g.means[2]|exact}} / {{g.means[3]|exact}}；{{g.ranks[2]}} / {{g.ranks[3]}}</td><td>{{g.means[4]|exact}}；{{g.ranks[4]}}</td><td>{{g.means[5]|exact}}；{{g.ranks[5]}}</td>{% else %}<td></td><td></td><td></td><td></td>{% endif %}</tr>{% endfor %}
</tbody></table>
<h2>本批次未分桶</h2><p>以下日期/账期冲突项不进入任何月份合计。</p><ul>{% for r in delivery.report.unallocated %}<li>{{r.txn_id}}：{{r.txn_date}} / {{r.period}}；需人工确认归期</li>{% endfor %}</ul>
{% endif %}</body></html>
```

上方模板已将 dimension 固定映射为“单位/科目/经办”，合成总体标准差标签与“输入提供、种类未签认”分开；没有真实标准差签认标签。映射不会改变数值。

5. pyproject.toml existing dependencies 末尾加 `"flask>=3.0"`，追加：

```toml
[tool.setuptools.package-data]
fi6_anomaly_detect = ["templates/*.html"]
```

6. 网关 conditional registration：在既有 `routing.py` 追加函数，`default_route_table()` 仅把原来 `return [home route]` 改成 `return add_fi6_route([home route])`。保留现有 FI5/FI8 等实际条目，按执行时 HEAD 冲突解决；不要重新写整张路由表。

```python
def add_fi6_route(routes: list[Route]) -> list[Route]:
    from urllib.parse import urlsplit
    explicit = (os.environ.get('PORTAL_GATEWAY_FI6_BACKEND') or '').strip()
    if not explicit:
        return routes
    target = urlsplit(explicit)
    try:
        port = target.port
    except ValueError:
        raise ValueError('FI6_BACKEND_INVALID') from None
    if (target.scheme != 'http' or target.hostname not in {'127.0.0.1','localhost'}
            or port is None or not 1 <= port <= 65535 or target.username is not None
            or target.password is not None or target.path not in {'','/'}
            or target.query or target.fragment):
        raise ValueError('FI6_BACKEND_MUST_BE_EXPLICIT_EXISTING_LOOPBACK_SERVICE')
    if any(r.prefix == '/finance/fi6' for r in routes):
        raise ValueError('FI6_ROUTE_ALREADY_REGISTERED')
    return [*routes, Route('/finance/fi6', explicit.rstrip('/'), 'finance', PermissionTier.DOMAIN_ADMIN)]
```

此函数只记录已获准服务的明确 URL，不启动服务、不选新端口、不改环境变量、不替代后端自身 auth。真正的 session→backend 信任装配和原服务树 listener 归属未核验前，不设置生产环境项。gateway `webapp.py` 原样全路径转发，FI6 factory 接收 `/finance/fi6`，不剥前缀。

7. 未来新建网关自己的 `tests/test_fi6_route.py`，测试仅 mock 无网络/监听：

```python
import pytest
from portal_gateway.permissions import PermissionTier, has_access, resolve_tier
from portal_gateway.routing import add_fi6_route, default_route_table, match_route

def test_conditional_finance_admin_route(monkeypatch):
    monkeypatch.delenv('PORTAL_GATEWAY_FI6_BACKEND', raising=False)
    before = default_route_table()
    assert all(r.prefix != '/finance/fi6' for r in before)
    monkeypatch.setenv('PORTAL_GATEWAY_FI6_BACKEND','http://127.0.0.1:19006')
    routes = add_fi6_route(before)
    route = match_route(routes,'/finance/fi6')
    assert route.domain == 'finance' and route.required_tier == PermissionTier.DOMAIN_ADMIN
    assert routes[:-1] == before
    mapping = {'mock-admin':[{'domain':'finance','tier':PermissionTier.DOMAIN_ADMIN}]}
    assert not has_access(route.required_tier, resolve_tier(mapping,None,'finance'))
    assert not has_access(route.required_tier, resolve_tier(mapping,'unlisted','finance'))
    assert has_access(route.required_tier, resolve_tier(mapping,'mock-admin','finance'))

@pytest.mark.parametrize('url',['http://outside.example:19006','http://127.0.0.1','http://127.0.0.1:19006/path','http://u:p@localhost:19006','https://localhost:19006'])
def test_no_arbitrary_backend(monkeypatch,url):
    monkeypatch.setenv('PORTAL_GATEWAY_FI6_BACKEND',url)
    with pytest.raises(ValueError):
        add_fi6_route([])

def test_complete_forwarded_path_and_no_http(monkeypatch):
    from portal_gateway import webapp
    from portal_gateway.sso import COOKIE_NAME, make_session_cookie_value
    from types import SimpleNamespace
    monkeypatch.setenv('PORTAL_GATEWAY_FI6_BACKEND','http://127.0.0.1:19006')
    seen = []
    def forward(route,path,**kwargs):
        seen.append((path,kwargs['query_string']))
        class Fake:
            status_code = 200
            raw = SimpleNamespace(headers={'Content-Type':'text/html'})
            def iter_content(self,chunk_size=8192):
                yield b'mock-fi6'
            def close(self):
                pass
        return Fake()
    monkeypatch.setattr(webapp,'forward_request',forward)
    secret = 'synthetic-test-secret'
    mapping = {'mock-admin':[{'domain':'finance','tier':PermissionTier.DOMAIN_ADMIN}]}
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as directory:
        app = webapp.create_app(secret=secret,routes=add_fi6_route([]),mapping=mapping,audit_path=Path(directory)/'audit.jsonl')
        client = app.test_client()
        client.set_cookie(COOKIE_NAME,make_session_cookie_value(secret,'mock-admin'))
        response = client.get('/finance/fi6?period=2026-09')
        assert response.status_code == 200
        assert response.get_data() == b'mock-fi6'
    assert seen == [('/finance/fi6','period=2026-09')]
```

端口19006只出现在 monkeypatch 假地址中，未运行监听、未占端口。执行时以现时 webapp.forward_request 响应消费形状复核 Fake；本轮静态接口读取不是测试通过证据。

8. 未来各子项目验证命令，分目录保留证据，不能从根混跑：

```powershell
Push-Location -LiteralPath $fi6Scene
try { & $fi6Python -m pytest 'tests/' -q } finally { Pop-Location }
$fi6Gateway = Join-Path $fi6ApprovedTree '5-平台底座/unified-portal-gateway'
Push-Location -LiteralPath $fi6Gateway
try { & $fi6Python -m pytest 'tests/' -q } finally { Pop-Location }
```

`.51`、真实 U9C、通知/OAuth 网络测试不属于这次 mock 验证。verify 命令 exit 非0 时修复或留正式阻塞，禁止抄历史10/12passed。

9. 场景 CLAUDE.md 交付正文用下面六段，不省缺口：

```markdown
# FI6 异常交易实时检测
## 1. 业务边界
应收/应付交易模式；FI3付款重复、超額、账户校验不在此重做。当前只交mock度量及报告，无异常判定。
## 2. 输入与来源
原三张mock CSV保留；metrics_demo是明确合成对账输入，附声明、源hash。real fail-loud，真实流水/基线采样/经办资料未签认。
## 3. 流程与接口
load_snapshot→measure→monthly→prepare两条audit→required-authorize factory；四类同时有或同时空。期间冲突不分桶。FI3ResultRef是下游需求引用，无自动映射。
## 4. 人工闸与知识资产
四Criterion未签认、RULE_VERSION仍unsigned；G01归期/G02采样/G03岗位/G04材料保留。needs_manual_review恒真、risk_grade空、判定与升级未启用、无自动付款。golden为空，无LLM。
## 5. 验证与审计
mock逐笔四列精确比对；真实Excel差异0待资料。每批次/报告走平台audit，任一失败不交付；已写事件不回滚。现时测试结果由Guardian交付证据填写，不沿用旧数字。
## 6. 运行与发布
create_app无监听；/finance/fi6条件route且仅finance admin。独立后端、无新端口；实际auth/运行树/端口归属另核。ff/生产/发送逐项授权，.51冒烟及回滚证据未完成前不宣称发布收口。
```

第5段实际证据由执行时附精确命令、exit、HEAD与输出引用；不能把本文准备时间写成产品测试时间。

10. 如实际实现与验证均获批准并完成，用正式工具更新 tasks 精确子项，保留原文历史，新增“本次 mock 度量”分项，不整勾3.6（三检测器未完成）/4.3（真实判例库未启用）/5.3（发送未启用）/6.3（生产未授权）。整包未完工，不 archive；写明“暂不归档：判定、真实资料/签认/运行与发布门槛未闭合”。
11. Native 实现完成后对实际 HEAD 作 fresh review，所有派生 reviewer 必须显式 gpt-6-luna；review 与修复在批准树内，不评本文草稿冒充实现审查。review/测试/交付证据满足后准备具体 ff 请求，生产与对外发送另闸；Task4 的 mock交付不等于全景场景完工。

## Spec 覆盖与保留事项

| Requirement / 已批决定 | 本次具体落点 | 保留的真实前置 |
|---|---|---|
| 未签认不默认；版本双向校验 | Task1保留config；Task2 unsigned异常守；Task3不升版 | 四Criterion签认与真实判定算法未实施 |
| PartyProfile禁关联bool | Task1/2，字段检查与缺资料人工侧 | 专员圈定真实关联依据字段 |
| 三类检测器 | 只做D1四类算术、D2可判定性检查；无patterns/risk结果 | 金额/频率/关联判定继续留开 |
| 无案例不能当正常 | Task2所有行manual真、judgment空；golden无文件 | 真实判例采集由财务L2明确确认 |
| 判例实名和版本 | 原CaseRecord保持；D5载体不重开 | case采集/回归/误报率均留开，未发明mock判例 |
| 案例驱动持续学习 | 保留整包任务4.3–4.5 | 实名真实判例与签認版本区间 |
| L2升级不处置、平台notifier | Task3 recipient_role=None、发送未启用；门限读取仍抛 | G03岗位、升级判据、真实发送逐项授权 |
| 全链audit | D10每批次/每报告Task3当前准备；每笔判定以后随判定加入 | 未执行审计代码；3年由现有平台留存机制承担 |
| 系统性聚合报告 | D9 Task2按单位/科目/经办，全维度/全部名次/笔数；Task4免责声明 | 当前只描述度量，不标系统性“已证实漏洞” |
| D3/D4/D6/D7/D8 | batch降级、FI3引用、唐燕萍无backup沿用、材料与通道合并既有项 | 真实通道、Owner、FI6→FI8对手方仍不能推定 |
| D11/D12/D13/D15/D16/D17/D18/D19 | 门户/空风险/精确mock对账/无LLM/跨期留空/显式采样标签/签认动员/角色单收未指派 | real Excel及专业G点待证；不发第21封 |

## 自审与本轮状态

本文在发布前按24命名来源检查漂移、Python围栏只做AST语法检查、逐项检查签名/字段和上述覆盖。AST检查不执行代码，不证明本实现或mock验收通过；代码/测试仍只在Markdown内。

完整意图/design已批、Native方式已选。本计划新增具体表示和mock/真实前置拆分，按writing-plans完整具体计划审阅门槛提交；尚未得到该具体批准则不启动实现。本轮不改产品代码、判据、OpenSpec任务状态、服务配置或生产；官方#471仍open，专员专业口径仍待签认。
