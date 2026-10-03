# FI5 可比量 mock 试点 Implementation Plan

> 执行方法沿用当前 **Native**；计划审阅后使用 `executing-plans` 按任务执行。实际建造须由正式 Guardian 绑定获准隔离工作树。派生模型任务显式 `gpt-6-luna`；本计划使用纯编号，正式 OpenSpec tasks 保存执行进度。

**Goal:** 落实已批准 D1–D20 的四列可比量、同场景重复发票检出、部门费用统计与有审计的 `/finance/fi5` mock 门户，保持判定/拦截/风险等级待签认。

**Architecture:** 输入先冻结成可追溯快照，使用 Decimal 与 Fraction 做字段算术；每行均保留人工复核，跨期/缺分母不进入对应计算。报告服务先写平台 batch/report 两条审计再交付；门户工厂和条件网关路由没有监听入口。

**Tech Stack:** Python >=3.11、现有 dataclass 输入、标准库 csv/Decimal/Fraction、`zhuopin_platform.criteria_signoff` 与 `audit`、Flask >=3.0（现有门户技术栈）。保留现有 pydantic>=2.0，不另加数据库、LLM、OCR 或 ERP SDK。

**Spec:** `C:/Dev/zhuopin-ai/4-数字员工/财务部/FI5-费用报销智能审核/intent.md`；`C:/Dev/zhuopin-ai/openspec/changes/fi5-expense-audit-mvp/design.md` 的 D1–D20、四条实施约束及 2026-09-17 追记；同包 tasks 与四份 delta specs。

**Status:** 当前 Native 完成准备，待本具体计划及下述前置拆分审阅。当前未改产品文件、未新增或运行产品测试、未启动 Guardian 建造。计划批准不替代财务专业签认、真实样本验证、实际技术设计/HEAD 绑定、ff、生产或外发授权。

## Global Constraints

1. 「四列可比量必须全算、并列呈现，不得预选、不得默认排序」；非适用或不可算的单元格显示原因，四列始终存在。
2. 「任何档位都不写回 U9C」；判据未签认时没有超标判断、实际拦截、风险分级、自动放行或自动通知。
3. 「跨期分支必须显式造用例覆盖」；`period` 与提交日月份不一致时，预算占用单元格为空且需人工。原始明细统计明确以单据声明期间分组，不等于签认财务归期。
4. 「重复发票」保持「检出但不判违规」；`risk_grade` 恒空，`needs_manual_review` 恒真。
5. 专业判据保持未签认，无默认阈值、频繁窗口、住宿标准、招待限额、含税选择或关联识别启发式。`FREQUENT_CLAIM_CRITERIA` 替换旧 `RISK_GRADE_BOUNDARIES`，FI5 4→4。
6. 当前只处理受控 mock。CSV 未声明币种，本期输出单位固定标为「合成金额」，不假称 CNY；未来真实币种/schema 对齐另过数据闸。OEM mock 上下文固定 `MOCK-OEM-A`，不装入真实 OEM 资料。
7. 数据源由可信 provider 提供；real/未知模式显式拒绝，不能回退 mock。当前不做发票 OCR、真伪校验、跨源 join、FI2 后8位 join 或 LLM 判断。
8. 「上级」通知与「财务经理」抽审是两个角色、两个动作；收件人均空，不解析岗位或人名。标准持有人按 D8 为唐燕萍，不设置 backup。
9. 每次可比量运行与报告生成均走 `config.audit_decision()`；未成功留痕不交付报告。平台 audit append-only，3年留存要求在部署/运维证据中核，不凭本期 mock 测试宣称落实。
10. 不新增外部端口、不写 `app.run()`、不启动监听；真实网关身份传递/授权接线、`.51`、Windows 原服务工作树继承均属于后续发布准备。
11. 看护者 master 只准备文档；实际业务代码进入获准 managed linked worktree，使用官方隔离 Python 与 bootstrap，不在根目录混跑 pytest、不重装共享全局 editable 指针。

## Review Focus

1. 跨期、缺预算、预算零/负、人数/夜数为零或缺失：对应列明确不可算，其余有效列保留，全部转人工。Task2 逐项断言。
2. 同一单多行同科目、单头金额与明细不一致：占用分子按该单该科目明细合计，不重复累加整个报销单；金额不一致时占用为空。Task2 专门覆盖。
3. 发票前导零、空格、全半角、同一单分行与跨单重复：保留原始文本，跨单同号检出；同一单分行不冒充第二张单；不判断违规。Task1/2 覆盖。
4. 窗口漏填、窗口变化、申请人笔数与明细行数混淆：窗口无默认值，按提交日闭区间数 distinct claim，门户无窗口时只呈现选择器。Task1/2/4 覆盖。
5. 身份伪造、audit 第二条失败、报告字段空值被转成0、共享网关已有改动：未鉴权不加载数据，审计失败无报告，政策/风险空值保留；路由增量保留已有条目。Task3/4/5 覆盖。

---

## 0. 现时事实与需要审阅的边界

来源绑定于 master `d69989de5684f6f3988125692c78c17c6359b234`，捕获前后 HEAD 相同。22件输入的精确路径/字节/SHA 在忽略证据 `fi5-comparables-plan-source-bindings.json`（SHA `da621f2ea48d012a54505bfe412b634104dfcf2bb5692ee0f2df168e24a644f5`）。主要基线：

| 来源 | SHA256 |
|---|---|
| intent | `3e6a66997152a7384d0822fc733d881ad0b1df6c57d2190862d995a4cc21b75c` |
| design | `9503fd224cbf4c94cb1ca9f3b9b78065ea5fd569fa8397aac50ae5f86b796ab2` |
| tasks | `84b76b924831508f1b0306d1474856d042494dae989f89bb5b70a7468bf15005` |
| config | `316dae34cd4d4eb15d3c298bb308123ca222e68982508a0c07febb1d24e3981c` |
| models | `5767df798db177d8b3de5e0eb439644f5d370847f91c2bb754c06d02bae6faf1` |
| gateway routing | `146e15f3d7c404de57c3a77bdc5e266ba7676ea3e58bc7c00338918c13955b0c` |

补充只读核`portal_gateway/webapp.py`的forward调用：完整path原样传入，SHA256 `74c4383aab2f0318f958b8a8735e4cec16233c91bf006226c76691b657e4b644`；此件仅为接口依据，不在本计划修改白名单。

1. 官方 #470 为 open，领取方保留历史骨架归属。D1–D20 的 intent/design 2026-09-09 已批准；当前无可比量引擎/门户。`models.py` 是 dataclass，金额注解 float；规范化时逐值转换 Decimal，保持原输入构造接口。
2. 当前夹具是 **2张单头、3条明细、3条预算**，并非3张单头。日期全部2026-09-02、同月；发票号为三个不同的14位带前导零字符串。当前包另有 #606 只读探针，不当作审核引擎。
3. AST 只读清点 FI5/FI6/FI8/FI9/FI10 注册表为4/4/3/3/4，共18条声明，均见 `Criterion` 构造；这不是运行时签认判定。清点 SHA `7e41575163ba0f7f740c7fd55615a1b663f2a1c816ff4d050a3f8c19a31e922f`。D11 在本期只改 FI5，不为凑数改别域；若未来他域新增获准判据，比较前后差值仍应为0，记录新总数。
4. 前置表 v11 已有 FI5 行，启动月2026-10，Owner待指派，倒排日期仅参考。旧 intent 的无行/2027-02 是历史，不复述为现时阻塞或自行改排期。
5. 官方跟进闸现时锁于已推送2026-09-23 01:02 UTC的财务部#20，在途；信正文第1项已索取报销单/管理办法/预算表，第4项含科目表。Markdown frontmatter「待你审」是旧稿状态，当前以官方闸为准。没有核到回件，当前不重发、不开#21、不起真实判例表。Q20 的历史「尚未索取」已不能作为现时事实。
6. #606 的自查任务机器状态done，只证明探针/缺口调查收口；tasks 2.4/2.5 仍未勾。2026-09-17 design 追记明确说原§2全部收口没有随 D1–D20 批过，当前不自行删除这个实施门槛。

**本具体计划需要确认的新增决策仅一项：**将 mock 可比量实现的前置与真实 OCR/跨源发票/专业判定的前置分开。mock 分支按 D1–D20 构建；原2.1–2.5/2.7等真实/签认任务保留未完成，继续约束对应真实分支。完整计划确认后，正式 Guardian 必须有可核验的范围/路径/SHA/设计批准输入；确认前不 apply，不以 #606 done 推导全部数据闸关闭。

## 1. 文件职责与白名单

设场景根 `S = 4-数字员工/财务部/FI5-费用报销智能审核`，变更根 `O = openspec/changes/fi5-expense-audit-mvp`。下表是未来精确触碰区，当前本计划不写这些源码：

| 文件 | 操作/职责 |
|---|---|
| `S/fi5_expense_audit/contracts.py` | 新建：冻结输入、显式窗口、精确编码与结构验证 |
| `S/fi5_expense_audit/mock_source.py` | 新建：仅三张受控CSV，模式/schema/哈希验证 |
| `S/fi5_expense_audit/comparables.py` | 新建：四列算术、同号检出、原始字段聚合 |
| `S/fi5_expense_audit/service.py` | 新建：审计前置、两角色未发送草稿、报告返回 |
| `S/fi5_expense_audit/webapp.py`、`S/fi5_expense_audit/templates/fi5.html` | 新建：鉴权注入的无监听门户工厂 |
| `S/fi5_expense_audit/config.py` | 修改：D11四项归位、D8持有人、unsigned版本、快照模式文案 |
| `S/fi5_expense_audit/models.py` | 仅改旧docstring/注释中D2与D11描述；不破坏既有constructor/default |
| `S/tests/test_contracts.py`、`test_comparables.py`、`test_service.py`、`test_webapp.py` | 新建：本计划给出的mock验证及Review Focus |
| `S/tests/test_scaffold.py` | 修改：四个key和历史文案；守住全部未签认 |
| `S/pyproject.toml`、`S/CLAUDE.md` | 修改依赖/package-data；新建六段场景文档 |
| `O/design.md`、`O/tasks.md`、`O/specs/fi5-policy-rules/spec.md`、`O/specs/fi5-budget-guard/spec.md`、`O/specs/fi5-risk-grading/spec.md`、`O/specs/fi5-expense-report/spec.md` | 仅在本计划/前置拆分获批后对齐D1–D20；保留旧真实任务与未完成判据 |
| `5-平台底座/unified-portal-gateway/portal_gateway/routing.py`、`tests/test_fi5_route.py` | 条件增量路由与独立mock验证；另包执行，不覆盖FI8等已有条目 |

原三张CSV、探针、平台底座audit/criteria源码、员工/组织数据、真实件、根规则、部署配置不进入此业务实现白名单。没有真实provider、通知发送或U9C写回接口。

## 2. 通用执行方式

1. 先完成具体计划/前置拆分审阅，再由正式 Guardian 绑定任务 #470、本计划SHA、实际 design输入与隔离工作树；缺等价正式入口/批准证据时记录缺口，准备件保留，不造ready。
2. 在隔离树内先复核22件输入。若完整计划未进入隔离HEAD，用正式批准的只读路径/SHA接入；不把主仓5,000项旧dirty复制到树里。
3. 原包对齐只增加可比量分支的任务/要求，标明原§2对真实分支仍有效，不把原判定/拦截/风险项勾完，不改主 specs正本冒充sync完成。技术设计有实质改变时回具体设计审。
4. 后文测试命令属于**待授权验证范围**，本次未执行。未来每个任务先写给出的失败用例，确认失败后实现，再跑同一用例及本子项目测试。场景/网关各自工作目录，禁止根pytest。
5. 所有命令工作目录取正式 Guardian 返回的绝对工作树；不得回落master。下面是可执行的统一运行包装，参数必须由实际回执提供：

```powershell
param(
  [Parameter(Mandatory)][string]$ApprovedWorktreeRoot,
  [Parameter(Mandatory)][ValidateSet('fi5','gateway')][string]$Subproject,
  [Parameter(Mandatory)][string[]]$PytestArgs
)
$taskRoot = (Resolve-Path -LiteralPath "$ApprovedWorktreeRoot").Path
if ($taskRoot -eq 'C:\Dev\zhuopin-ai') { throw 'watcher master cannot build' }
$expectedCommon = (Resolve-Path -LiteralPath 'C:\Dev\zhuopin-ai\.git').Path
$actualCommon = (& git -C "$taskRoot" rev-parse --path-format=absolute --git-common-dir).Trim()
if ($LASTEXITCODE -ne 0) { throw 'git metadata unavailable' }
$actualCommon = (Resolve-Path -LiteralPath "$actualCommon").Path
if ($actualCommon -ne $expectedCommon) { throw 'not a linked project worktree' }
$relative = if ($Subproject -eq 'fi5') { '4-数字员工/财务部/FI5-费用报销智能审核' } else { '5-平台底座/unified-portal-gateway' }
Set-Location -LiteralPath (Join-Path "$taskRoot" "$relative")
& 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -m pytest @PytestArgs
if ($LASTEXITCODE -ne 0) { throw 'subproject verification failed' }
```

这个包装只校验仓关联，**不构成Guardian授权检查的替代品**；先核正式任务/HEAD/白名单。新依赖只在批准的隔离环境按项目pyproject准备，不重装共享editable平台。

## Task 1. 冻结输入、mock来源与判据归位

**Files:** contracts.py、mock_source.py、config.py、models.py注释、test_contracts.py、test_scaffold.py；折叠必要配置到本任务。

**Interfaces:** `normalise(claims, lines, budgets, *, sources: dict[str,str]) -> Snapshot`；`load_mock(root: Path, *, source_mode: str) -> Snapshot`；`ReportWindow(start: date, end: date)`；`canonical(value) -> str`。

1. 先写test_contracts.py：从受控CSV取得2/3/3、发票前导零保持、输入不被修改、窗口必填；NaN/inf/非法期间/孤儿明细/重复三键预算/重复行ID应明确失败。现有四项key更新为最后一项FREQUENT，值保持未签认。
2. 失败验证命令：`python -m pytest tests/test_contracts.py tests/test_scaffold.py -q`（使用上面正式工作树包装）。预期首次失败为新模块未存在/旧key不符；不能把环境导入错误当红测成功。
3. contracts.py完整实现：

```python
from __future__ import annotations
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from fractions import Fraction

def _encode(value):
    if isinstance(value, Decimal): return str(value)
    if isinstance(value, Fraction): return {'numerator': value.numerator, 'denominator': value.denominator}
    if type(value) is date: return value.isoformat()
    raise TypeError(f'unsupported canonical value: {type(value).__name__}')

def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False, default=_encode)

def money(value) -> Decimal:
    if isinstance(value, bool): raise ValueError('boolean amount')
    try: result = Decimal(str(value))
    except (InvalidOperation, ValueError): raise ValueError('invalid amount') from None
    if not result.is_finite(): raise ValueError('non-finite amount')
    return result

def text(value, field):
    if not isinstance(value, str) or not value.strip(): raise ValueError(f'missing {field}')
    return value

def period(value):
    text(value, 'period')
    if not re.fullmatch(r'[0-9]{4}-(0[1-9]|1[0-2])', value): raise ValueError('invalid period')
    date.fromisoformat(value + '-01')
    return value

def day(value):
    if not isinstance(value, str): raise ValueError('date must be text')
    result = date.fromisoformat(value)
    if result.isoformat() != value: raise ValueError('date must be YYYY-MM-DD')
    return result

def integer(value, field, nullable=False):
    if nullable and value is None: return None
    if type(value) is not int: raise ValueError(f'invalid {field}')
    return value

@dataclass(frozen=True)
class Claim:
    claim_id: str
    claimant: str
    department: str
    period: str
    claim_type: str
    total_amount: Decimal
    submitted_at: date

@dataclass(frozen=True)
class Line:
    claim_id: str
    line_no: int
    account: str
    amount: Decimal
    invoice_no: str | None
    occasion: str
    headcount: int | None
    travel_grade: str
    nights: int | None

@dataclass(frozen=True)
class Budget:
    department: str
    account: str
    period: str
    budget_amount: Decimal
    used_amount: Decimal

@dataclass(frozen=True)
class ReportWindow:
    start: date
    end: date
    def __post_init__(self):
        if type(self.start) is not date or type(self.end) is not date or self.start > self.end:
            raise ValueError('invalid explicit window')

@dataclass(frozen=True)
class Snapshot:
    claims: tuple[Claim, ...]
    lines: tuple[Line, ...]
    budgets: tuple[Budget, ...]
    sources: tuple[tuple[str, str], ...]
    @property
    def mode(self): return 'mock'
    @property
    def unit(self): return 'synthetic_amount'
    @property
    def oem_context(self): return 'MOCK-OEM-A'
    @property
    def sha256(self):
        data = {**asdict(self), 'mode': self.mode, 'unit': self.unit, 'oem_context': self.oem_context}
        return hashlib.sha256(canonical(data).encode('utf-8')).hexdigest()

def normalise(claims, lines, budgets, *, sources):
    cs = tuple(Claim(text(c.claim_id,'claim_id'), text(c.claimant,'claimant'), text(c.department,'department'),
                     period(c.period), text(c.claim_type,'claim_type'), money(c.total_amount), day(c.submitted_at)) for c in claims)
    ls = []
    for line in lines:
        number = integer(line.line_no, 'line_no')
        if number <= 0: raise ValueError('line_no must be positive')
        inv = line.invoice_no
        if inv is not None and not isinstance(inv, str): raise ValueError('invoice_no must be text')
        if inv is not None and not inv.strip(): inv = None
        if not isinstance(line.occasion, str) or not isinstance(line.travel_grade, str): raise ValueError('invalid optional text')
        ls.append(Line(text(line.claim_id,'claim_id'), number, text(line.account,'account'), money(line.amount), inv,
                       line.occasion, integer(line.headcount,'headcount',True), line.travel_grade, integer(line.nights,'nights',True)))
    bs = tuple(Budget(text(b.department,'department'), text(b.account,'account'), period(b.period),
                      money(b.budget_amount), money(b.used_amount)) for b in budgets)
    ids = [c.claim_id for c in cs]
    keys = [(l.claim_id,l.line_no) for l in ls]
    bkeys = [(b.department,b.account,b.period) for b in bs]
    if len(ids) != len(set(ids)): raise ValueError('duplicate claim_id')
    if len(keys) != len(set(keys)): raise ValueError('duplicate line key')
    if len(bkeys) != len(set(bkeys)): raise ValueError('duplicate budget key')
    if any(l.claim_id not in set(ids) for l in ls): raise ValueError('orphan line')
    if any(c.claim_id not in {l.claim_id for l in ls} for c in cs): raise ValueError('claim missing detail')
    source_pairs = []
    for name, digest in sorted(sources.items()):
        text(name,'source name')
        if not isinstance(digest,str) or not re.fullmatch(r'[0-9a-f]{64}',digest): raise ValueError('invalid source SHA')
        source_pairs.append((name,digest))
    if not source_pairs: raise ValueError('missing source manifest')
    return Snapshot(cs, tuple(ls), bs, tuple(source_pairs))
```

4. mock_source.py完整实现；header严格以当前夹具为准，不承诺真实schema：

```python
from __future__ import annotations
import csv
import hashlib
import io
from pathlib import Path
from .config import U9C_EXPENSE_NOT_READY
from .contracts import normalise, money
from .models import ExpenseClaim, ExpenseLine, BudgetBalance

HEADERS = {
 'expense_claims.csv': ['claim_id','claimant','department','period','claim_type','total_amount','submitted_at'],
 'expense_lines.csv': ['claim_id','line_no','account','amount','invoice_no','occasion','headcount','travel_grade','nights'],
 'budget_balance.csv': ['department','account','period','budget_amount','used_amount'],
}

def load_mock(root: Path, *, source_mode: str):
    if source_mode != 'mock': raise RuntimeError(U9C_EXPENSE_NOT_READY)
    tables, hashes = {}, {}
    for name, header in HEADERS.items():
        raw = (root / name).read_bytes()
        hashes[name] = hashlib.sha256(raw).hexdigest()
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''))
        if reader.fieldnames != header: raise ValueError(f'unsupported mock schema: {name}')
        rows = list(reader)
        if any(None in row or any(v is None for v in row.values()) for row in rows): raise ValueError(f'malformed CSV: {name}')
        tables[name] = rows
    claims = [ExpenseClaim(r['claim_id'],r['claimant'],r['department'],r['period'],r['claim_type'],
                            money(r['total_amount']),r['submitted_at']) for r in tables['expense_claims.csv']]
    def optint(value):
        return None if value == '' else int(value)
    lines = [ExpenseLine(r['claim_id'],int(r['line_no']),r['account'],money(r['amount']),r['invoice_no'] or None,
                          r['occasion'],optint(r['headcount']),r['travel_grade'],optint(r['nights'])) for r in tables['expense_lines.csv']]
    budgets = [BudgetBalance(r['department'],r['account'],r['period'],money(r['budget_amount']),
                             money(r['used_amount'])) for r in tables['budget_balance.csv']]
    return normalise(claims,lines,budgets,sources=hashes)
```

现有float注解的dataclass在运行时不强制类型，本adapter在金额位置传Decimal；不改变原constructor。未来静态类型检查若要求注解升级，列出独立兼容性差异后审核，不悄悄改调用面。

5. config.py第四条改为如下，前三项仍原key；四项owner按D8均为唐燕萍。版本改为 `fi5-comparables-unsigned-2026-10-03`，保留导入期assert与audit_decision；新增 `BUDGET_SOURCE_MODE = 'snapshot_batch_constraint_downgrade'`，明确约束下降级。不添加任何signed/value/default。

```python
Criterion(key='FREQUENT_CLAIM_CRITERIA',
          question='频繁报销：窗口多长、笔数上限多少，月底正常波峰如何排除',
          owner='唐燕萍', note='D11语义归位；未签认，不设默认窗口或次数')
```

6. test_contracts.py关键可执行内容（未来文件内导入明确）：

```python
from dataclasses import replace, FrozenInstanceError
from datetime import date
from decimal import Decimal
import pytest
from fi5_expense_audit.contracts import ReportWindow, normalise, money
from fi5_expense_audit.mock_source import load_mock

def test_mock_snapshot_and_literal_ids(mock_dir):
    snap = load_mock(mock_dir, source_mode='mock')
    assert (len(snap.claims),len(snap.lines),len(snap.budgets)) == (2,3,3)
    assert snap.lines[0].invoice_no == '00000000000001'
    assert snap.lines[0].amount == Decimal('2400.00')
    assert len(snap.sha256) == 64
    with pytest.raises(FrozenInstanceError): snap.lines[0].amount = Decimal('0')

@pytest.mark.parametrize('value',['NaN','Infinity','-Infinity',True])
def test_nonfinite_or_boolean_money_rejected(value):
    with pytest.raises(ValueError): money(value)

def test_explicit_window_has_no_default():
    with pytest.raises(TypeError): ReportWindow()
    with pytest.raises(ValueError): ReportWindow(date(2026,9,30),date(2026,9,1))

def test_invalid_mode_does_not_read_or_fallback(mock_dir):
    with pytest.raises(RuntimeError,match='报销模块'): load_mock(mock_dir,source_mode='real')
    with pytest.raises(RuntimeError): load_mock(mock_dir,source_mode='unknown')

def test_duplicate_budget_and_orphan_rejected(simple_claim,simple_lines,simple_budget):
    claim = replace(simple_claim,submitted_at='2026-09-02')
    source = {'mock-case':'0'*64}
    with pytest.raises(ValueError,match='duplicate budget'):
        normalise([claim],simple_lines,[simple_budget[0],simple_budget[0]],sources=source)
    with pytest.raises(ValueError,match='orphan'):
        normalise([claim],[replace(simple_lines[0],claim_id='missing')],simple_budget,sources=source)
```

在同一测试文件追加以下完整用例；空集合只有已给定schema与来源时才表示真实的0条输入，专业列不因此变0：

```python
from dataclasses import asdict
import shutil
from fi5_expense_audit.mock_source import HEADERS

@pytest.mark.parametrize('changes',[{'period':'2026-13'},{'submitted_at':'2026-9-2'},{'submitted_at':'2026-09-02T00:00:00'}])
def test_invalid_period_or_noncanonical_date(simple_claim,simple_lines,simple_budget,changes):
    claim=replace(simple_claim,submitted_at='2026-09-02',**{k:v for k,v in changes.items() if k != 'submitted_at'})
    if 'submitted_at' in changes: claim=replace(claim,submitted_at=changes['submitted_at'])
    with pytest.raises(ValueError): normalise([claim],simple_lines,simple_budget,sources={'mock-case':'0'*64})

def test_duplicate_ids_and_unchanged_legacy_input(simple_claim,simple_lines,simple_budget):
    claim=replace(simple_claim,submitted_at='2026-09-02')
    before=(asdict(claim),[asdict(l) for l in simple_lines],[asdict(b) for b in simple_budget])
    sources={'mock-case':'0'*64}
    normalise([claim],simple_lines,simple_budget,sources=sources)
    assert before == (asdict(claim),[asdict(l) for l in simple_lines],[asdict(b) for b in simple_budget])
    with pytest.raises(ValueError,match='duplicate claim'):
        normalise([claim,claim],simple_lines,simple_budget,sources=sources)
    with pytest.raises(ValueError,match='duplicate line'):
        normalise([claim],[simple_lines[0],simple_lines[0]],simple_budget,sources=sources)

@pytest.mark.parametrize('bad_header',[
    'claim_id,line_no,account,amount,invoice_no,occasion,headcount,travel_grade,nights,extra',
    'claim_id,line_no,account,amount,invoice_no,occasion,headcount,headcount,nights',
])
def test_csv_schema_is_not_guessed(mock_dir,tmp_path,bad_header):
    for name in HEADERS: shutil.copyfile(mock_dir/name,tmp_path/name)
    path=tmp_path/'expense_lines.csv'
    content=path.read_text(encoding='utf-8').splitlines()
    path.write_text('\n'.join([bad_header,*content[1:]])+'\n',encoding='utf-8')
    with pytest.raises(ValueError,match='schema'): load_mock(tmp_path,source_mode='mock')

def test_empty_tables_require_headers_and_stay_empty(tmp_path):
    for name,header in HEADERS.items(): (tmp_path/name).write_text(','.join(header)+'\n',encoding='utf-8')
    snap=load_mock(tmp_path,source_mode='mock')
    assert (snap.claims,snap.lines,snap.budgets) == ((),(),())
```

四项unsigned守护及版本一致性仍由现有test_scaffold执行。

7. 跑相同命令；验证18声明前后差值0（只读AST，不导入别域），记录实际结果。隔离树只暂存本Task明确文件后提交 `feat(fi5): freeze mock inputs and align unsigned criteria`。

## Task 2. 四列可比量、同号检出与部门聚合

**Files:** comparables.py、test_comparables.py。

**Interfaces:** `analyse(snapshot: Snapshot, window: ReportWindow) -> tuple[tuple[ComparableRow,...], tuple[GroupRow,...]]`。Snapshot/Window来自Task1；值用精确Fraction，列的缺失保持None，整数笔数不通过明细计数获得。

1. 先写下面oracle与分支用例，运行 `python -m pytest tests/test_comparables.py -q`，确认新模块红测。
2. comparables.py完整实现：

```python
from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from .contracts import Snapshot, ReportWindow

@dataclass(frozen=True)
class ComparableRow:
    claim_id: str
    line_no: int
    claimant: str
    department: str
    period: str
    account: str
    amount: Decimal
    lodging_daily: Fraction | None
    entertainment_per_person: Fraction | None
    budget_occupancy: Fraction | None
    applicant_window_count: int
    duplicate_claim_ids: tuple[str,...]
    flags: tuple[str,...]
    @property
    def risk_grade(self): return ''
    @property
    def needs_manual_review(self): return True
    @property
    def judgement(self): return None
    @property
    def intercept(self): return None

@dataclass(frozen=True)
class GroupRow:
    department: str
    account: str
    period: str
    amount: Fraction
    claim_count: int
    line_count: int
    period_conflict_count: int
    @property
    def over_standard_count(self): return None
    @property
    def risk_distribution(self): return None

def analyse(snapshot: Snapshot, window: ReportWindow):
    claims = {c.claim_id:c for c in snapshot.claims}
    chosen = {c.claim_id for c in snapshot.claims if window.start <= c.submitted_at <= window.end}
    applicant_counts = Counter(c.claimant for c in snapshot.claims if c.claim_id in chosen)
    amounts = defaultdict(lambda: Fraction(0))
    head_totals = defaultdict(lambda: Fraction(0))
    invoices = defaultdict(set)
    for line in snapshot.lines:
        amounts[(line.claim_id,line.account)] += Fraction(line.amount)
        head_totals[line.claim_id] += Fraction(line.amount)
        if line.invoice_no is not None: invoices[line.invoice_no].add(line.claim_id)
    budgets = {(b.department,b.account,b.period):b for b in snapshot.budgets}
    rows, aggregates = [], {}
    for line in snapshot.lines:
        if line.claim_id not in chosen: continue
        claim = claims[line.claim_id]
        flags, lodging, entertainment, occupancy = [], None, None, None
        if line.account == '差旅费-住宿':
            if line.nights is None or line.nights <= 0: flags.append('lodging_denominator_missing')
            else: lodging = Fraction(line.amount) / line.nights
        if line.account == '业务招待费':
            if line.headcount is None or line.headcount <= 0: flags.append('entertainment_denominator_missing')
            else: entertainment = Fraction(line.amount) / line.headcount
        conflict = claim.period != claim.submitted_at.strftime('%Y-%m')
        mismatch = Fraction(claim.total_amount) != head_totals[claim.claim_id]
        budget = budgets.get((claim.department,line.account,claim.period))
        if conflict: flags.append('period_conflict')
        if mismatch: flags.append('claim_total_mismatch')
        if budget is None: flags.append('budget_missing')
        elif budget.budget_amount <= 0: flags.append('budget_denominator_nonpositive')
        elif not conflict and not mismatch:
            occupancy = (Fraction(budget.used_amount) + amounts[(claim.claim_id,line.account)]) / Fraction(budget.budget_amount)
        if line.amount < 0: flags.append('negative_amount_source')
        others = tuple(sorted(invoices.get(line.invoice_no,set()) - {claim.claim_id})) if line.invoice_no is not None else ()
        if others: flags.append('duplicate_invoice_detected_not_judged')
        rows.append(ComparableRow(claim.claim_id,line.line_no,claim.claimant,claim.department,claim.period,
                                  line.account,line.amount,lodging,entertainment,occupancy,
                                  applicant_counts[claim.claimant],others,tuple(flags)))
        key = (claim.department,line.account,claim.period)
        group = aggregates.setdefault(key,{'amount':Fraction(0),'claims':set(),'lines':0,'conflicts':0})
        group['amount'] += Fraction(line.amount)
        group['claims'].add(claim.claim_id)
        group['lines'] += 1
        group['conflicts'] += int(conflict)
    groups = tuple(GroupRow(*key,g['amount'],len(g['claims']),g['lines'],g['conflicts']) for key,g in aggregates.items())
    return tuple(rows),groups
```

统计按原始 `claim.period` 字段分组，页面明示「单据声明期间；归期未签认」，不把跨期明细迁入提交月。金额输入保留Decimal，所有求和/除法用Fraction，避免受外部Decimal context精度改变影响。预算只计算同一单同科目合计，**不把本批每张独立报销单叠加成新的占用口径**。重复检出范围是本输入快照；不声明快照外无重复。

3. test_comparables.py具体oracles：

```python
from dataclasses import replace
from datetime import date
from decimal import Decimal
from fractions import Fraction
import pytest
from fi5_expense_audit.contracts import ReportWindow
from fi5_expense_audit.mock_source import load_mock
from fi5_expense_audit.comparables import analyse

def window(): return ReportWindow(date(2026,9,1),date(2026,9,30))

def test_four_columns_match_independent_mock_oracles(mock_dir):
    snap = load_mock(mock_dir,source_mode='mock')
    rows,groups = analyse(snap,window())
    expected = [(Fraction(800),None,Fraction(209,200),1),
                (None,Fraction(115),Fraction(313,300),1),
                (None,Fraction(640,3),Fraction(419,400),1)]
    assert [(r.lodging_daily,r.entertainment_per_person,r.budget_occupancy,r.applicant_window_count) for r in rows] == expected
    assert [g.amount for g in groups] == [Decimal('2400'),Decimal('460'),Decimal('1280')]
    assert all(r.risk_grade == '' and r.needs_manual_review and r.judgement is None and r.intercept is None for r in rows)
    assert all(g.over_standard_count is None and g.risk_distribution is None for g in groups)

def test_cross_period_is_not_allocated_to_budget(mock_dir):
    snap = load_mock(mock_dir,source_mode='mock')
    changed = replace(snap,claims=(replace(snap.claims[0],period='2026-08'),snap.claims[1]))
    rows,groups = analyse(changed,window())
    assert rows[0].budget_occupancy is None and 'period_conflict' in rows[0].flags
    assert rows[0].lodging_daily == Fraction(800)
    assert groups[0].period == '2026-08' and groups[0].period_conflict_count == 1

def test_same_claim_account_amount_is_not_head_total(mock_dir):
    snap = load_mock(mock_dir,source_mode='mock')
    extra = replace(snap.lines[0],line_no=3,amount=Decimal('100'),invoice_no='00000000000004')
    changed = replace(snap,claims=(replace(snap.claims[0],total_amount=Decimal('2960')),snap.claims[1]),lines=(*snap.lines,extra))
    rows,_ = analyse(changed,window())
    assert rows[0].budget_occupancy == Fraction(21,20)
    assert rows[3].budget_occupancy == Fraction(21,20)
    assert rows[0].applicant_window_count == 1

def test_cross_claim_duplicate_is_literal_detection_only(mock_dir):
    snap = load_mock(mock_dir,source_mode='mock')
    duplicate = replace(snap.lines[2],invoice_no=snap.lines[0].invoice_no)
    changed = replace(snap,lines=(snap.lines[0],snap.lines[1],duplicate))
    rows,_ = analyse(changed,window())
    assert rows[0].duplicate_claim_ids == (snap.claims[1].claim_id,)
    assert rows[0].risk_grade == '' and rows[0].needs_manual_review
    spaced = replace(duplicate,invoice_no=' '+duplicate.invoice_no)
    rows,_ = analyse(replace(snap,lines=(snap.lines[0],snap.lines[1],spaced)),window())
    assert rows[0].duplicate_claim_ids == ()

@pytest.mark.parametrize('field',[None,0,-1])
def test_missing_or_nonpositive_lodging_denominator(mock_dir,field):
    snap = load_mock(mock_dir,source_mode='mock')
    changed = replace(snap,lines=(replace(snap.lines[0],nights=field),*snap.lines[1:]))
    rows,_ = analyse(changed,window())
    assert rows[0].lodging_daily is None and rows[0].needs_manual_review
    assert rows[0].budget_occupancy == Fraction(209,200)
```

4. 同文件追加以下完整Review Focus用例，不改原CSV：

```python
@pytest.mark.parametrize('value',[None,0,-1])
def test_entertainment_denominator_is_not_assumed(mock_dir,value):
    snap=load_mock(mock_dir,source_mode='mock')
    changed=replace(snap,lines=(snap.lines[0],replace(snap.lines[1],headcount=value),snap.lines[2]))
    rows,_=analyse(changed,window())
    assert rows[1].entertainment_per_person is None
    assert 'entertainment_denominator_missing' in rows[1].flags

@pytest.mark.parametrize('value',[Decimal('0'),Decimal('-1')])
def test_budget_nonpositive_has_no_default(mock_dir,value):
    snap=load_mock(mock_dir,source_mode='mock')
    changed=replace(snap,budgets=(replace(snap.budgets[0],budget_amount=value),*snap.budgets[1:]))
    rows,_=analyse(changed,window())
    assert rows[0].budget_occupancy is None and 'budget_denominator_nonpositive' in rows[0].flags

def test_missing_budget_and_total_conflict(mock_dir):
    snap=load_mock(mock_dir,source_mode='mock')
    rows,_=analyse(replace(snap,budgets=snap.budgets[1:]),window())
    assert rows[0].budget_occupancy is None and 'budget_missing' in rows[0].flags
    changed=replace(snap,claims=(replace(snap.claims[0],total_amount=Decimal('2861')),snap.claims[1]))
    rows,_=analyse(changed,window())
    assert rows[0].budget_occupancy is None and 'claim_total_mismatch' in rows[0].flags
    assert rows[0].lodging_daily == Fraction(800)

def test_same_claim_split_invoice_is_not_second_claim(mock_dir):
    snap=load_mock(mock_dir,source_mode='mock')
    changed=replace(snap,lines=(snap.lines[0],replace(snap.lines[1],invoice_no=snap.lines[0].invoice_no),snap.lines[2]))
    rows,_=analyse(changed,window())
    assert rows[0].duplicate_claim_ids == rows[1].duplicate_claim_ids == ()

@pytest.mark.parametrize('other_invoice',['０００００００００００００１','different-prefix-00000001'])
def test_no_fullwidth_or_suffix_join(mock_dir,other_invoice):
    snap=load_mock(mock_dir,source_mode='mock')
    changed=replace(snap,lines=(snap.lines[0],snap.lines[1],replace(snap.lines[2],invoice_no=other_invoice)))
    rows,_=analyse(changed,window())
    assert rows[0].duplicate_claim_ids == ()

def test_window_count_uses_distinct_claims_and_explicit_range(mock_dir):
    snap=load_mock(mock_dir,source_mode='mock')
    changed=replace(snap,claims=(snap.claims[0],replace(snap.claims[1],claimant=snap.claims[0].claimant)))
    rows,_=analyse(changed,window())
    assert [r.applicant_window_count for r in rows] == [2,2,2]
    assert analyse(changed,ReportWindow(date(2026,9,3),date(2026,9,3))) == ((),())

def test_negative_source_amount_is_not_declared_violation(mock_dir):
    snap=load_mock(mock_dir,source_mode='mock')
    changed=replace(snap,claims=(replace(snap.claims[0],total_amount=Decimal('-1940')),snap.claims[1]),
                    lines=(replace(snap.lines[0],amount=Decimal('-2400')),snap.lines[1],snap.lines[2]))
    rows,_=analyse(changed,window())
    assert rows[0].lodging_daily == Fraction(-800)
    assert 'negative_amount_source' in rows[0].flags and rows[0].risk_grade == ''

def test_calculation_is_independent_of_decimal_context(mock_dir):
    from decimal import localcontext
    snap=load_mock(mock_dir,source_mode='mock')
    with localcontext() as context:
        context.prec=2
        rows,groups=analyse(snap,window())
    assert rows[1].budget_occupancy == Fraction(313,300)
    assert groups[0].amount == Fraction(2400)
```
5. 运行Task1+2两个测试文件及场景test_scaffold；核四列、缺值原因、原快照SHA未变。精确暂存并提交 `feat(fi5): calculate four comparable fields without policy judgement`。

## Task 3. 有审计的报告服务与两角色草稿

**Files:** service.py、test_service.py。消费analyse/规范化snapshot，产生冻结Report与payload；只引用平台audit，不改底座。

1. 先写RecordingAudit成功/第一条失败/第二条失败三个mock，验证2条动作、rule_version、输入SHA、请求方、窗口、build_id及未出报告；运行 `python -m pytest tests/test_service.py -q`。
2. service.py完整实现：

```python
from __future__ import annotations
import hashlib
from dataclasses import asdict, dataclass
from typing import Protocol
from uuid import uuid4
from zhuopin_platform.audit import AuditEvent
from . import config
from .contracts import Snapshot, ReportWindow, canonical, text
from .comparables import ComparableRow, GroupRow, analyse

class Recorder(Protocol):
    def record(self,event:AuditEvent) -> None: ...

class AuditWriteError(RuntimeError): pass

@dataclass(frozen=True)
class RoleDraft:
    kind: str
    role: str
    body: str
    @property
    def recipient(self): return None
    @property
    def sent(self): return False

@dataclass(frozen=True)
class Report:
    snapshot_id: str
    run_id: str
    window: ReportWindow
    rows: tuple[ComparableRow,...]
    groups: tuple[GroupRow,...]
    drafts: tuple[RoleDraft,...]
    def payload(self):
        return {'snapshot_id':self.snapshot_id,'run_id':self.run_id,'window':asdict(self.window),
                'unit':'synthetic_amount','policy_judgement':None,'intercept':None,
                'rows':[{**asdict(r),'risk_grade':'','needs_manual_review':True,'judgement':None,'intercept':None} for r in self.rows],
                'groups':[{**asdict(g),'over_standard_count':None,'risk_distribution':None} for g in self.groups],
                'drafts':[{**asdict(d),'recipient':None,'sent':False} for d in self.drafts]}

def prepare_report(snapshot:Snapshot,window:ReportWindow,*,actor:str,build_id:str,audit:Recorder) -> Report:
    text(actor,'trusted actor')
    text(build_id,'approved build id')
    rows,groups = analyse(snapshot,window)
    report = Report(snapshot.sha256,uuid4().hex,window,rows,groups,(
        RoleDraft('superior_notification','上级','通知处置待判据签认及组织汇报关系确认；未发送'),
        RoleDraft('manual_review','财务经理','AI初审建议，结案在财务经理；具体岗位待确认'),
    ))
    output_hash = hashlib.sha256(canonical(report.payload()).encode('utf-8')).hexdigest()
    common = config.audit_decision(snapshot_id=snapshot.sha256,run_id=report.run_id,
               window_start=window.start.isoformat(),window_end=window.end.isoformat(),build_id=build_id,
               source_mode=snapshot.mode,unit=snapshot.unit,row_count=len(rows),
               risk_grade='',needs_manual_review=True,policy_judgement=None,intercept=None)
    try:
        audit.record(AuditEvent(scenario='FI5',action='comparables_batch',evaluator=actor,automation_level='L2',
                               decision=common,data_sources=dict(snapshot.sources),oem_context=snapshot.oem_context,content_hash=output_hash))
        audit.record(AuditEvent(scenario='FI5',action='expense_report',evaluator=actor,automation_level='L2',
                               decision={**common,'group_count':len(groups)},data_sources=dict(snapshot.sources),
                               oem_context=snapshot.oem_context,content_hash=output_hash))
    except Exception as error:
        raise AuditWriteError('audit write failed; report withheld') from error
    return report
```

Protocol的省略号是Python接口声明，不是未实现业务步骤。传入的生产实现须为平台AuditLogger；测试只用明确RecordingAudit。审计不拷贝申请人/发票原文，只留来源校验值和报告hash。未签認关联口径不在FI5增加注册表条目；未具备字段时没有关联判断接口。

3. test_service.py具体内容：

```python
from datetime import date
import pytest
from fi5_expense_audit import config
from fi5_expense_audit.contracts import ReportWindow
from fi5_expense_audit.mock_source import load_mock
from fi5_expense_audit.service import prepare_report, AuditWriteError

class RecordingAudit:
    def __init__(self,fail_at=None): self.events=[]; self.fail_at=fail_at; self.calls=0
    def record(self,event):
        self.calls += 1
        if self.calls == self.fail_at: raise OSError('synthetic audit failure')
        self.events.append(event)

def test_batch_and_report_are_both_audited(mock_dir):
    snap=load_mock(mock_dir,source_mode='mock'); audit=RecordingAudit()
    report=prepare_report(snap,ReportWindow(date(2026,9,1),date(2026,9,30)),actor='mock-admin',build_id='mock-build',audit=audit)
    assert [e.action for e in audit.events] == ['comparables_batch','expense_report']
    assert all(e.decision['rule_version'] == config.RULE_VERSION and e.decision['snapshot_id'] == snap.sha256 for e in audit.events)
    assert all(e.evaluator == 'mock-admin' and e.decision['build_id'] == 'mock-build' for e in audit.events)
    assert len({e.content_hash for e in audit.events}) == 1
    assert [d.kind for d in report.drafts] == ['superior_notification','manual_review']
    assert all(d.recipient is None and not d.sent for d in report.drafts)

@pytest.mark.parametrize('fail_at',[1,2])
def test_audit_failure_returns_no_report(mock_dir,fail_at):
    audit=RecordingAudit(fail_at)
    with pytest.raises(AuditWriteError):
        prepare_report(load_mock(mock_dir,source_mode='mock'),ReportWindow(date(2026,9,1),date(2026,9,30)),
                       actor='mock-admin',build_id='mock-build',audit=audit)
    assert len(audit.events) == fail_at-1
```

同文件追加：

```python
@pytest.mark.parametrize('actor,build_id',[(' ','mock-build'),('mock-admin','')])
def test_identity_and_build_are_required(mock_dir,actor,build_id):
    audit=RecordingAudit()
    with pytest.raises(ValueError):
        prepare_report(load_mock(mock_dir,source_mode='mock'),ReportWindow(date(2026,9,1),date(2026,9,30)),
                       actor=actor,build_id=build_id,audit=audit)
    assert audit.events == []

def test_service_does_not_mutate_snapshot_or_sign_criteria(mock_dir):
    from zhuopin_platform.criteria_signoff import CriterionNotSignedOffError
    snap=load_mock(mock_dir,source_mode='mock'); before=snap.sha256
    prepare_report(snap,ReportWindow(date(2026,9,1),date(2026,9,30)),actor='mock-admin',build_id='mock-build',audit=RecordingAudit())
    assert snap.sha256 == before
    for key in config.CRITERIA.keys():
        with pytest.raises(CriterionNotSignedOffError): config.CRITERIA.value_of(key)
```

两个role不能合并为一个person。第二审计失败时第一条可已追加，不能回滚append-only或宣称整批留痕成功。
4. 运行前三任务测试及现有骨架测试，精确暂存后提交 `feat(fi5): audit comparable reports before delivery`。

## Task 4. 无监听门户工厂与可见的未签认列

**Files:** webapp.py、templates/fi5.html、test_webapp.py、pyproject.toml。本任务折叠Flask依赖及模板package-data配置。

**Interfaces:** `create_app(*,load_snapshot:Callable[[],Snapshot],get_actor:Callable[[],str|None],audit:Recorder,build_id:str) -> Flask`。授权callback为可信注入点；不得直接信任请求header/单据申请人。此期只做mock鉴权验证，真实网关userid到actor尚待发布接线核验。

1. 先写认证缺失不加载数据/空窗口只picker/有效窗口200/非法窗口400/审计失败503/两列空/不排序/HTML转义用例，运行 `python -m pytest tests/test_webapp.py -q`。
2. webapp.py完整实现：

```python
from __future__ import annotations
from decimal import Decimal, localcontext
from fractions import Fraction
from flask import Flask, request, render_template
from .contracts import ReportWindow, day
from .service import prepare_report, AuditWriteError

FIELD_STATES = {
 'lodging_denominator_missing':'住宿夜数缺失或非正数',
 'entertainment_denominator_missing':'招待人数缺失或非正数',
 'period_conflict':'声明期间与提交月不一致，预算占用需人工',
 'claim_total_mismatch':'单头与明细金额不一致，预算占用需人工',
 'budget_missing':'预算行缺失',
 'budget_denominator_nonpositive':'预算分母非正数',
 'negative_amount_source':'负金额含义待人工确认',
 'duplicate_invoice_detected_not_judged':'同号检出，未判违规',
}

def display(value):
    if value is None: return '不可算或不适用'
    if isinstance(value,Fraction):
        with localcontext() as context:
            context.prec=28
            return format(Decimal(value.numerator)/Decimal(value.denominator),'f')
    return str(value)

def create_app(*,load_snapshot,get_actor,audit,build_id):
    app=Flask(__name__)
    app.jinja_env.filters['quantity']=display
    app.jinja_env.filters['field_state']=lambda flag: FIELD_STATES.get(flag,'字段状态需人工核对')
    @app.get('/finance/fi5')
    def fi5():
        actor=get_actor()
        if not isinstance(actor,str) or not actor.strip(): return '无访问权限',403
        start=request.args.get('start'); end=request.args.get('end')
        if start is None and end is None: return render_template('fi5.html',report=None)
        if not start or not end: return '请给定完整统计窗口',400
        if len(request.args.getlist('start')) != 1 or len(request.args.getlist('end')) != 1: return '统计窗口参数重复',400
        try: window=ReportWindow(day(start),day(end))
        except (TypeError,ValueError): return '统计窗口无效',400
        try: report=prepare_report(load_snapshot(),window,actor=actor,build_id=build_id,audit=audit)
        except AuditWriteError: return '审计记录失败，报告未生成',503
        except (TypeError,ValueError,RuntimeError,OSError,ArithmeticError): return '输入来源或字段不可用，请核对材料',422
        return render_template('fi5.html',report=report)
    return app
```

没有app.run、监听配置、真实provider、上传/导出/通知动作。UI显示的28位是工程呈现精度；内部Fraction与独立oracle精确对账，不宣称已经完成真实Excel的财务精度签认。

3. templates/fi5.html完整内容：

```html
<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>FI5 费用可比量</title>
<h1>FI5 费用可比量 · 合成材料</h1>
<p>AI 初审建议，结案在财务经理。当前全部需人工复核。</p>
<form method="get"><label>窗口开始 <input type="date" name="start" required></label>
<label>窗口结束 <input type="date" name="end" required></label><button>生成报告</button></form>
{% if report %}
<p>统计窗口：{{ report.window.start }} 至 {{ report.window.end }}（按提交日）；单位：合成金额。</p>
<p>四类可比量并列，未选口径。住宿夜数与含税口径待签认；预算源为约束下的快照批次降级。</p>
<table><thead><tr><th>单号/行号</th><th>申请人</th><th>住宿日均</th><th>招待人均</th><th>预算占用比率</th><th>申请人窗口内笔数</th><th>重复检出（不判违规）</th><th>字段异常</th><th>判定：待判据签认</th><th>拦截：待判据签认</th></tr></thead><tbody>
{% for row in report.rows %}<tr><td>{{ row.claim_id }}/{{ row.line_no }}</td><td>{{ row.claimant }}</td>
<td>{{ row.lodging_daily|quantity }}</td><td>{{ row.entertainment_per_person|quantity }}</td><td>{{ row.budget_occupancy|quantity }}</td><td>{{ row.applicant_window_count }}</td>
<td>{% if row.duplicate_claim_ids %}同号见于 {{ row.duplicate_claim_ids|join('、') }}，需人工{% endif %}</td>
<td>{% for flag in row.flags %}{{ flag|field_state }} {% endfor %}</td><td></td><td></td></tr>{% endfor %}
</tbody></table>
<h2>部门费用统计</h2><p>按单据声明期间汇总；归期未签认。风险分布与超标笔数待签认。</p>
<table><tr><th>部门</th><th>科目</th><th>声明期间</th><th>原始明细金额</th><th>单数</th><th>明细数</th><th>跨期明细数</th><th>超标笔数</th><th>风险分布</th></tr>
{% for group in report.groups %}<tr><td>{{ group.department }}</td><td>{{ group.account }}</td><td>{{ group.period }}</td><td>{{ group.amount|quantity }}</td><td>{{ group.claim_count }}</td><td>{{ group.line_count }}</td><td>{{ group.period_conflict_count }}</td><td></td><td></td></tr>{% endfor %}</table>
<h2>待人工处置</h2>{% for draft in report.drafts %}<p>{{ draft.role }}：{{ draft.body }}；收件岗位未确认。</p>{% endfor %}
<p>快照 {{ report.snapshot_id }}；审计批次 {{ report.run_id }}。</p>
{% endif %}</html>
```

上面固定映射呈现字段事实，不显示编程错误或凭据；未识别flag使用「字段状态需人工核对」，审计原码保留，不编财务结论。

4. pyproject dependencies追加 `"flask>=3.0"`；新增：

```toml
[tool.setuptools.package-data]
fi5_expense_audit = ["templates/*.html"]
```

5. test_webapp.py构造方式及关键断言：

```python
from fi5_expense_audit.mock_source import load_mock
from fi5_expense_audit.webapp import create_app

class RecordingAudit:
    def __init__(self,fail=False): self.events=[]; self.fail=fail
    def record(self,event):
        if self.fail: raise OSError('synthetic')
        self.events.append(event)

def test_portal_requires_actor_before_loading(mock_dir):
    calls=[]
    app=create_app(load_snapshot=lambda:calls.append(True),get_actor=lambda:None,audit=RecordingAudit(),build_id='mock-build')
    response=app.test_client().get('/finance/fi5?start=2026-09-01&end=2026-09-30',headers={'X-Actor':'fake-admin'})
    assert response.status_code == 403 and calls == []

def test_picker_and_all_four_columns(mock_dir):
    audit=RecordingAudit()
    app=create_app(load_snapshot=lambda:load_mock(mock_dir,source_mode='mock'),get_actor=lambda:'mock-admin',audit=audit,build_id='mock-build')
    client=app.test_client()
    assert client.get('/finance/fi5').status_code == 200 and audit.events == []
    response=client.get('/finance/fi5?start=2026-09-01&end=2026-09-30')
    body=response.get_data(as_text=True)
    assert response.status_code == 200 and len(audit.events) == 2
    for label in ('住宿日均','招待人均','预算占用比率','申请人窗口内笔数','待判据签认','未选口径'):
        assert label in body
    assert 'sort=' not in body and '<script' not in body
    assert client.get('/finance/fi5?start=2026-09-01').status_code == 400
```

同文件追加完整分支断言；用Flask test_client，不启动服务或浏览器监听：

```python
from dataclasses import replace
from decimal import Decimal
import pytest

@pytest.mark.parametrize('query',['?start=bad&end=2026-09-30','?start=2026-09-30&end=2026-09-01','?start=2026-09-01&start=2026-09-02&end=2026-09-30'])
def test_invalid_window_does_not_generate_report(mock_dir,query):
    audit=RecordingAudit()
    app=create_app(load_snapshot=lambda:load_mock(mock_dir,source_mode='mock'),get_actor=lambda:'mock-admin',audit=audit,build_id='mock-build')
    assert app.test_client().get('/finance/fi5'+query).status_code == 400
    assert audit.events == []

def test_second_audit_failure_withholds_report(mock_dir):
    class SecondFail(RecordingAudit):
        def record(self,event):
            if self.events: raise OSError('synthetic second failure')
            self.events.append(event)
    audit=SecondFail()
    app=create_app(load_snapshot=lambda:load_mock(mock_dir,source_mode='mock'),get_actor=lambda:'mock-admin',audit=audit,build_id='mock-build')
    response=app.test_client().get('/finance/fi5?start=2026-09-01&end=2026-09-30')
    assert response.status_code == 503 and '2400' not in response.get_data(as_text=True)
    assert len(audit.events) == 1

def test_blank_actor_and_unusable_source(mock_dir):
    app=create_app(load_snapshot=lambda:load_mock(mock_dir,source_mode='mock'),get_actor=lambda:' ',audit=RecordingAudit(),build_id='mock-build')
    assert app.test_client().get('/finance/fi5').status_code == 403
    def bad_source(): raise ValueError('synthetic unusable source')
    app=create_app(load_snapshot=bad_source,get_actor=lambda:'mock-admin',audit=RecordingAudit(),build_id='mock-build')
    assert app.test_client().get('/finance/fi5?start=2026-09-01&end=2026-09-30').status_code == 422

def test_source_text_is_escaped_and_unavailable_cell_is_not_zero(mock_dir):
    snap=load_mock(mock_dir,source_mode='mock')
    changed=replace(snap,claims=(replace(snap.claims[0],claimant='<script>alert(1)</script>'),snap.claims[1]),
                    budgets=(replace(snap.budgets[0],budget_amount=Decimal('0')),*snap.budgets[1:]))
    before=changed.sha256
    app=create_app(load_snapshot=lambda:changed,get_actor=lambda:'mock-admin',audit=RecordingAudit(),build_id='mock-build')
    body=app.test_client().get('/finance/fi5?start=2026-09-01&end=2026-09-30').get_data(as_text=True)
    assert '<script>alert' not in body and '&lt;script&gt;' in body
    assert '预算分母非正数' in body and '不可算或不适用' in body
    assert changed.sha256 == before
    assert 'sort=' not in body
```
6. 跑该测试文件与场景全套（在S目录），确认模板随包可取；精确提交 `feat(fi5): expose audited mock comparable portal factory`。

## Task 5. 条件网关路由、文档与完整交付审查

**Files:** gateway/routing.py、gateway/tests/test_fi5_route.py、S/CLAUDE.md、本包正式tasks进度。gateway另子项目验证，不能把FI5绿测当网关通过。

1. 先核同文件在办触碰，尤其FI8计划未来的routing增量；取实际源码重新合并，不能用本计划基线覆盖他人条目。确认无冲突后添加仅在 `PORTAL_GATEWAY_FI5_BACKEND` 明确设置时的白名单条目，域finance，tier DOMAIN_ADMIN（起步最小授权，正式岗位映射待发布核）。新backend没有默认端口或外部地址。
2. 未来routing.py在保留既有default_route_table内容前提下，加入以下验证函数，并在现有routes返回前条件追加；这是完整新增行为，原route构造及其他已追加分支按现时源码保留：

```python
from urllib.parse import urlsplit

def _fi5_backend_url(raw: str) -> str:
    parsed=urlsplit(raw)
    try: port=parsed.port
    except ValueError: raise ValueError('invalid FI5 backend port') from None
    if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1','localhost','::1')
        or port is None or not 1 <= port <= 65535 or parsed.username is not None or parsed.password is not None
        or parsed.path not in ('','/') or parsed.query or parsed.fragment):
        raise ValueError('FI5 backend must be an explicit approved local service URL')
    return raw.rstrip('/')

def append_fi5_route(routes):
    raw=(os.environ.get('PORTAL_GATEWAY_FI5_BACKEND') or '').strip()
    if not raw: return routes
    if any(route.prefix == '/finance/fi5' for route in routes): raise ValueError('duplicate FI5 route')
    return [*routes, Route(prefix='/finance/fi5',backend_base_url=_fi5_backend_url(raw),
                          domain='finance',required_tier=PermissionTier.DOMAIN_ADMIN)]
```

当前源码基线下的default_route_table完整改法如下；开工若有他人新条目，不覆盖新条目，先针对实际diff重审本段增量：

```python
def default_route_table() -> list[Route]:
    backend=os.environ.get('PORTAL_GATEWAY_HOME_BACKEND','http://127.0.0.1:8092')
    routes=[Route(prefix='/',backend_base_url=backend,domain='portal',required_tier=PermissionTier.PUBLIC_READ,
                  backend_gate_password_env='ZP_GATE_PASSWORD')]
    return append_fi5_route(routes)
```

这里只注册路由，不设置真实环境、不启动后端。真实身份/口令通道由发布时设计另核；本工厂不接收未经核验的用户header，故不能凭代理单测宣称端到端授权完成。

3. gateway/tests/test_fi5_route.py关键测试：

```python
import pytest
from portal_gateway.permissions import PermissionTier
from portal_gateway.routing import append_fi5_route, default_route_table, match_route

def test_fi5_route_requires_explicit_backend(monkeypatch):
    monkeypatch.delenv('PORTAL_GATEWAY_FI5_BACKEND',raising=False)
    assert not any(r.prefix == '/finance/fi5' for r in default_route_table())
    monkeypatch.setenv('PORTAL_GATEWAY_FI5_BACKEND','http://127.0.0.1:18095')
    routes=default_route_table()
    route=match_route(routes,'/finance/fi5')
    assert route.domain == 'finance' and route.required_tier == PermissionTier.DOMAIN_ADMIN
    assert route.backend_base_url == 'http://127.0.0.1:18095'
    assert any(r.prefix == '/' for r in routes)
    assert match_route(routes,'/finance/fi50').prefix != '/finance/fi5'

@pytest.mark.parametrize('value',['https://example.com','http://127.0.0.1','http://user:pw@127.0.0.1:18095','http://127.0.0.1:18095/path'])
def test_unapproved_backend_shape_rejected(monkeypatch,value):
    monkeypatch.setenv('PORTAL_GATEWAY_FI5_BACKEND',value)
    with pytest.raises(ValueError): default_route_table()
```

同文件追加纯mock权限判定与保留既有条目验证，不改真实department_mapping.yaml：

```python
from portal_gateway.permissions import resolve_tier
from portal_gateway.routing import Route

def test_fi5_minimum_tier_is_not_granted_to_unknown_or_other_domain(monkeypatch):
    monkeypatch.setenv('PORTAL_GATEWAY_FI5_BACKEND','http://127.0.0.1:18095')
    target=match_route(default_route_table(),'/finance/fi5')
    mapping={'other':[{'domain':'quality','tier':PermissionTier.DOMAIN_ADMIN}],
             'member':[{'domain':'finance','tier':PermissionTier.DOMAIN_MEMBER}],
             'admin':[{'domain':'finance','tier':PermissionTier.DOMAIN_ADMIN}]}
    for actor in (None,'unknown','other','member'):
        assert resolve_tier(mapping,actor,target.domain) < target.required_tier
    assert resolve_tier(mapping,'admin',target.domain) >= target.required_tier

def test_existing_route_is_kept_and_duplicate_fi5_is_rejected(monkeypatch):
    monkeypatch.setenv('PORTAL_GATEWAY_FI5_BACKEND','http://127.0.0.1:18095')
    original=Route('/finance/fi8','http://127.0.0.1:18098','finance',PermissionTier.DOMAIN_ADMIN)
    routes=append_fi5_route([original])
    assert routes[0] is original
    with pytest.raises(ValueError,match='duplicate'): append_fi5_route(routes)
```

18095/18098仅test字符串，不创建监听、不成为产品默认值。独立运行 `python -m pytest tests/test_fi5_route.py -q`，再在网关目录运行现有全套；本新增验证不调用网络forward，不发HTTP请求。

另补一项forward调用的mock，确认本场景工厂需要的完整URL前缀与查询保留；当前webapp.py实际向forward_request传入原path，而不是删除路由前缀。此验证替换requests.request，不调用网络：

```python
from portal_gateway.routing import forward_request

def test_forward_keeps_full_fi5_path_and_query(monkeypatch):
    calls=[]
    sentinel=object()
    def fake_request(method,url,**kwargs):
        calls.append((method,url,kwargs))
        return sentinel
    monkeypatch.setattr('portal_gateway.routing.requests.request',fake_request)
    route=Route('/finance/fi5','http://127.0.0.1:18095','finance',PermissionTier.DOMAIN_ADMIN)
    result=forward_request(route,'/finance/fi5',method='GET',headers={},query_string='start=2026-09-01&end=2026-09-30')
    assert result is sentinel
    assert calls[0][1] == 'http://127.0.0.1:18095/finance/fi5?start=2026-09-01&end=2026-09-30'
```

该函数级mock不证明真实认证身份已贯通；生产provider与gateway签名/会话验证仍须实测后才能发布。
4. S/CLAUDE.md完整六段要点：定位（D1可比量；非完整智能审核）、决策（D1–D20及获准前置拆分/计划SHA）、底座（criteria/audit/bootstrap/无新通道）、红线（无判定/写回/外发；unsigned；双角色）、时间线（实际HEAD/命令/结果，失败也记）、依赖（11专业/材料点、Owner/端点/OCR/真实身份/发布）。只写实际发生的验证结果，不填预计passed数量。
5. 原task对应关系只将实际新增的mock可比量任务逐项关闭；原2.1–2.5真实项、正式材料/财务Excel验收、判定/通知/风险/部署仍未完成。D11计数检查只证明语义归位，不能代签四项标准。
6. 场景与网关分别核CI矩阵，使用对应子项目工作目录与正式runtime；不复用旧全仓CI结论。前次已核39jobs的CI是旧HEAD，只作历史线索，本批review需要实际构建HEAD。
7. Native完工后按requesting-code-review做独立review，派生模型显式gpt-6-luna，绑定actual implementation HEAD与白名单；review修复仍在隔离树。业务代码差异、输出审计、mock对账零差异与未闭合项全部可审阅。
8. 精确暂存Task5实际文件并提交 `feat(fi5): register guarded comparable route and delivery evidence`。正式Guardian接受本批交付后进入发布准备；ff、生产、真实外发分别取得针对该项授权。没有这些回执不清理工作树，不把mock门户计成真实上线。

## 3. 需求覆盖与保留的完整终态

| 原requirement/决策 | 本期证据 | 后续仍需的证据 |
|---|---|---|
| 未签认不得默认、版本一致 | Task1四项unsigned守护；Task2不读专业值 | 签认后四步落地；知识资产登记 |
| 数据驱动政策规则 | Task1保留注册表，Task2输出政策比较的字段量 | 两表真实条文/案例签认后实现逐行判定，不称本期已完成 |
| 提交时预算校验/拦截 | Task2快照字段算术；Task3/4判定/拦截为空 | 端点/归期/含税/阈值；实际动作始终不写U9C，动作方式按获准设计 |
| 复用通知通道 | Task3只有未发送角色草稿，无自建通道 | 角色口径/HR-IT数据源/真实发送授权后接平台notifier |
| 三类风险分级 | Task1四项归位；Task2风险恒空，关联不推断 | 两政策表/FREQUENT及FI6共用关联证据、所需字段到位 |
| LLM黄金集 | 当前无LLM运行时；无虚假黄金集验收 | 将来OCR真伪/关联LLM引入前补冻结输入/专家输出，未有不晋档3 |
| L2不自动结案 | Task2/3/4恒manual；双角色未解析 | 专业签认不替代实名抽审；结案角色正式映射 |
| 每笔判定审计/可追溯 | 本期无判定；Task3按D10每batch/report先审计 | 将来逐笔判定事件、3年留存/实际运维证据 |
| 部门聚合 | Task2原始金额/单数/行数/声明期间冲突计数 | 超标笔数/风险分布待签认，当前保持空 |
| D16验收 | Task2独立精确分数oracles，mock逐列差0 | 一期真实报销单＋Excel逐笔逐列差0；材料与G05/G06专业口径先齐 |
| D15门户/7.2 | Task4无监听工厂；Task5条件路由mock | 真实身份接线、审批角色、既有服务工作树部署/回滚与授权 |

**本期完工定义：**获准的mock分支全部任务有真实代码/命令结果/审计/review/Guardian接受回执，且无专业默认值与越权动作。当前没有上述执行证据，本文不报本期已完工。

**FI5完整完工定义保留：**专业判据、材料、真实schema/通道/发票与OCR验证、真实Excel对账、后续政策/风险/通知、L2、审计保留、正式review/发布及四关证据全部闭合；真实分支前置仍在官方队列/原tasks中。当前本计划只是其中已批准可比量方向的具体准备，不将整个项目缩为mock完成。

## 4. 计划自审记录与交接

1. 覆盖D1–D20及四条实施约束；原九项requirement逐项区分本期实做/后续证据。两种窗口（请求统计窗口与专业频繁判据）分开；未知归期/含税/夜数不默认签认。
2. Contracts→analyse→prepare_report→create_app签名一致；原dataclass接口保留。两个角色对象未合并；输出空风险/判定不转零。全部代码与测试仅在本文，当前未创建相应产品文件。
3. 当前完整草案先保存在忽略工作区，自审后在正式锁下整体发布，避免把短占位稿交给落库消费者。发布时登记计划/核验/业务队列三件，写后读回与实际SHA另留receipt。
4. `writing-plans`要求完整具体计划审阅后再实施；当前Native方法保持。本次需审阅的是本文件和mock/真实前置拆分及mock验证范围，D1–D20、D8持有人、不写U9C、Native方法无需重问。审核答复绑定本计划实际SHA，后续正式Guardian校验实际输入。
