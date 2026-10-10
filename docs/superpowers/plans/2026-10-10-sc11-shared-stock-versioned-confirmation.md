# 供审执行边界（根会话收敛）

本计划供审，不授权立即执行；已批准 A2/B2/§10 design SHA EF3FFE667DB3A8959794E921245B42774F920FE764215F211F6D8EA43DF685C5 不变。

1. 起点固定 `28337c0ebb52afdbf61e955ecdbc22d151bcd185`。获批后 app 原生 `create_worktree(allowAsync=true, name=sc11-inventory-transfer-1010, ref=28337c0ebb52afdbf61e955ecdbc22d151bcd185)` 创建新候选并附着；批准包含返回的仓库外新checkout/必要Git元数据，实际绝对路径留证。旧树/dirty/历史证据保留，不安装依赖。
2. 产品只改正文七路径，测试只跑三个定向文件：test_shared_reservation.py、test_versioned_audit_gate.py、test_pmc_gate.py。baseline仅现有test_pmc_gate.py；TDD及实现后沿同一获批清单，无根混跑/全包tests。计划下文46是全包预期背景，不是本次运行清单或结果；本次拟验收12＋12＋6，实际JUnit计数为准。
3. 各次主仓 ignored `reports/sc11-inventory-transfer-1010/run-<uuid>/` 新UUID、独立basetemp（含合成JSONL/lock）、JUnit/stdio/退出码，-B/no cache；不覆盖、清理旧目录。下面各任务块的命令均采用同一CandidateRoot参数命令，不得硬编码主仓产品cwd。
4. 本期仅单进程串行合成固定周拟稿、共享库存整单分配及绑定当前版本的PMC流程技术合同；stage mock actor不是专业签认。单参门禁必须核真实JSONL当前revision与最新confirm/refuse；registry无跨进程自动恢复，缺authority fail closed。真实库存/物流/优先级、月中插单、业务签认、ERP/邮件各有后续前置。
5. 计划及批准OpenSpec从主仓读，候选diff/SHA和测试review在新树；根共享锁回写tasks/队列。候选提交整合/ff/push、生产、真实取数/外发、晋档/归档分别审。

---

# SC11 Inventory Transfer Implementation Plan

> **状态：具体实施计划供审；本稿不授权源码、测试、Guardian、真实数据、ERP 写入、邮件外发、晋档或归档。**
> OpenSpec design 基线 SHA-256：`EF3FFE667DB3A8959794E921245B42774F920FE764215F211F6D8EA43DF685C5`。
> 正式批准消费记录及已修订 `tasks.md` 为本计划依据；design SHA 冻结不变。3M.1 仍需本计划、逐文件白名单与执行环境获批，本稿本身不授权实施。

## Goal

在 SC11 现有骨架 API 旁增加一个版本化、仅 synthetic/mock 的拟稿入口：共享库存账本按显式 `scenario_order` 整单预留；候选只在完整评分 tuple 相同且给出 `scenario_candidate_order` 时用该顺序破同分；拟稿内容形成不可变 revision 与完整 business hash；PMC 确认/拒绝、创建/修订都先追加平台 audit 事件；只有绑定当前 `draft_id/revision/content_hash` 的实名确认才通过新执行门禁。整单不拆分、不替代。ERP 和邮件通道保持未接并 fail-loud。

## Architecture

- 只扩展现有场景包，不创建平台服务或连接器。旧 `run_draft`, `TransferPlanDraft`, `approve`, `commit_to_erp(draft)`, `notify_outsourced_warehouse(draft)` 符号及调用签名保留；新增 `run_versioned_draft` 及版本化生命周期入口。执行函数仍只收一个 draft 参数，但 legacy `approved_by` 只能作为旧历史投影，不能通过新的严格门禁。旧 `TransferPlanDraft` 调用执行门禁时 fail-closed 并提示使用版本化确认；有效版本化确认仍因通道未接而抛 `NotWiredYet`。
- `DraftRevision` 用冻结 dataclass 保存 `draft_id`、递增 `revision`、`schema_version`、`algorithm_version`、canonical `content_json` 与 SHA-256 `content_hash`。业务 JSON 包含完整 demand/库存/距离输入及来源版本、as-of、两种 scenario 顺序、priority assumption、候选评分结果、reservation/unmet/shortage 输出；不含展示顺序、时钟或签认人。canonical JSON 用 UTF-8、排序 key、紧凑分隔符、`allow_nan=False`；库存/需求中的数值必须有限。hash 不依赖可变 dict/list。
- `ApprovalRecord` 是冻结值，记 `draft_id/revision/content_hash`、实名 `pmc_manager`、结果 (`confirmed` 或 `refused`) 与 UTC 时间；事件 ID/显示文字只进 audit。`VersionedTransferPlanDraft` 是 revision 与可选 record 的冻结组合；确认/拒绝返回新组合，不改写旧对象。
- A2 单次模拟从输入快照复制余额，余额索引为 `(inventory_snapshot_id, source_warehouse, material_id)`。按 `scenario_order` 访问 demand；候选按当前余额过滤，只接受整单可供量，确认选中后原子扣减。候选评分完全缺失、所有候选 tuple 不可判定、无合法完整同分破局顺序时记 `unranked`；不能依 Python 稳定排序暗选。完整 tuple 不同则 `scenario_candidate_order` 不得改变胜负。没有完整可行候选记整单 `unmet`；单独计算 arithmetic shortage，不将缺量拆成 provisional reservation。
- 新生命周期事件复用 `zhuopin_platform.audit.AuditEvent` / `AuditLogger.record` 与既有 JSONL sink；`decision` 结构化保存事件类型、精确版本/hash、情景假设及状态，`data_sources` 保存字符串来源引用。evaluator 或 audit 缺失、事件写入失败、hash 校验失败时不返回有效状态。audit 写入异常原样传播。
- B2 当前版本由 `gate.py` 内的版本 authority registry 持有 `draft_id -> AuditLogger`；仅在 create/revise 事件已成功追加后登记。单参执行门禁从该 logger 的 JSONL `query_by(scenario="SC11")` 读取该 draft 最新 create/revise 事件，并比较其 revision/hash；读事件前须要求 `verify_chain().ok`，损坏链也 fail-closed。revision 不匹配、无 authority、读审计失败都 fail-closed。`draft_id` 由调用方生成唯一 UUID，本进程内重复创建会拒绝。重启后 registry 不自动恢复，因此旧对象不能跨进程执行；当前窄片不新增 rehydrate 入口。该机制用已落盘审计事件作当前版本真值，不依赖调用方再传第二个参数。

## 根审补充：持久确认与当前版本

执行门禁除了核当前create/revise版次，还必须核同一JSONL最新confirm/refuse事件：无真实确认事件、手工构造ApprovalRecord、后续refuse均拒绝；PMC/结果/时间绑定落盘事件。确认对象timestamp采用AuditEvent.timestamp。registry只引用真正JsonlSink，同一draft不得切换审计路径，已存在于该JSONL的draft_id不能重创。阶段为单进程串行mock；无跨进程恢复与并发生命周期承诺，重启缺authority即关闭，后续真实阶段需独立设计。

## Tech Stack

Python 3.11+；dataclasses、标准库 `json`/`hashlib`/`math`/`datetime`；现有 `pytest`、场景 `tests/conftest.py` 路径引导、`zhuopin_platform.audit.AuditLogger`。不新增依赖、不 `pip install -e`。未来命令使用项目隔离解释器 `C:\Dev\Codex\runtimes\zhuopin-ai\venv\Scripts\python.exe`，工作目录为 `4-数字员工/采购部/SC11-库存智能调拨`。

## Spec Path

- `openspec/changes/sc11-inventory-transfer/specs/sc11-transfer-planning/spec.md`：PMC gate、shared stock、immutable hash、audit persistence。
- `openspec/changes/sc11-inventory-transfer/design.md`：A2/B2、§10.1–10.4；冻结 SHA 见页首。
- `openspec/changes/sc11-inventory-transfer/tasks.md`：已批准 A2/B2 与 3M mock 切片拆分；3M.1 仍需具体计划/白名单批准，3M.2–3M.8 尚未执行；2.2–2.6 与 3/4/5 组真实依赖不由本计划解除。

## Global Constraints

1. 执行实现前先获得本计划逐文件白名单和执行环境批准；获批后仍只做 3M synthetic/mock，不勾 2.2–2.6，不碰真实计划/库存/物流、真实优先级、替代料、部分调拨、ERP、邮件、部署、发布、归档或全景文档。
2. mock 两种顺序分别命名并计入 hash/audit：`scenario_order: tuple[int, ...]` 是输入 demand 下标的完整排列；`scenario_candidate_order: Mapping[int, tuple[str, ...]]` 是 demand 下标到仓库编码序列的映射，只能破完整评分 tuple 同分。二者均是 fixture 假设，不是业务规则。
3. 输入校验拒绝重复/越界/遗漏的 demand index、无效仓库序列、NaN/Infinity、空 snapshot/version/as-of/source refs、未覆盖四原则的 priority assumption；拒绝不得回退到默认排序、默认矩阵或可用量。
4. legacy API 的 Python 名称与签名保留，但 legacy `approved_by/approved_at` 不得给版本化调用授权。修改现有门禁测试明确这一差异，避免旧确认字段形成旁路。
5. 每个产品或测试任务的路径白名单只能是下列“未来修改文件”；本轮实际只修改本 ignored 计划文件。pytest JSONL 写入各测试的 `tmp_path`；命令的 junit/stdout/stderr/temporary files 写入新 UUID 子目录 `reports/sc11-inventory-transfer-1010/run-<uuid>/`。该路径被 `.gitignore` 忽略；不得清理旧目录或任何既有证据。
6. 不重写 audit 底座。既有 `AuditLogger.record(AuditEvent)` 失败关闭；不以 `audit=None` 对新版本 API 降级；低层纯构造函数不得宣称为完整 L2 delivery。
7. 不改原 tasks/spec/design；实现期间若发现设计/接口需扩界，停在该节点，提出正式变更供审，不自解闸。已批准的 3M 拆分和 design 状态不再作为新增前置。

## Current Code Contracts and Allowed Future File Set

现有源码已逐字读取：

- `4-数字员工/采购部/SC11-库存智能调拨/sc11_transfer/models.py`：`TransferDemand(material_id, to_warehouse, qty, needed_by, product_id="")`、`TransferCandidate(demand, from_warehouse, qty, hops=1)`、可变 `TransferPlanDraft(lines, unmet, priority_assumption, approved_by, approved_at)`。
- `.../sc11_transfer/routing.py`：`enumerate_candidates(demand, stock_by_warehouse)`、`build_draft(demands, stock_by_warehouse, principles, priority_assumption)`；后者当前逐 demand 独立选首候选，故新版用独立入口/内部函数，不改变旧 API 结果。
- `.../sc11_transfer/agent.py`：`run_draft(..., *, evaluator, audit: AuditLogger | None = None)`；新入口需要求非空 evaluator 和非空可写 audit。
- `.../sc11_transfer/gate.py`：`approve(draft, pmc_manager)`、`commit_to_erp(draft)`、`notify_outsourced_warehouse(draft)`；后两者签名单参数。严格版本确认须在既有单参数执行入口验证 `VersionedTransferPlanDraft`，legacy draft 不可凭 `approved_by` 放行。
- `.../tests/conftest.py` 已在 import 前用 `zhuopin_platform.bootstrap.ensure_paths(..., strict=True)` 指向当前 worktree；禁止依赖 editable install。
- 平台 audit API 是 `5-平台底座/zhuopin_platform/zhuopin_platform/audit/events.py::AuditEvent`、`.../audit/logger.py::AuditLogger.record(event)`、`.../audit/sinks.py::JsonlSink`；事件的 `data_sources` 值是字符串，`AuditLogger.jsonl(path)` 可读回记录。

未来实施严格限定为以下 7 个路径（4 个源码、2 个新增测试文件、1 个现有门禁测试）：

1. `4-数字员工/采购部/SC11-库存智能调拨/sc11_transfer/models.py`
2. `4-数字员工/采购部/SC11-库存智能调拨/sc11_transfer/routing.py`
3. `4-数字员工/采购部/SC11-库存智能调拨/sc11_transfer/agent.py`
4. `4-数字员工/采购部/SC11-库存智能调拨/sc11_transfer/gate.py`
5. `4-数字员工/采购部/SC11-库存智能调拨/tests/test_shared_reservation.py`（新增）
6. `4-数字员工/采购部/SC11-库存智能调拨/tests/test_versioned_audit_gate.py`（新增）
7. `4-数字员工/采购部/SC11-库存智能调拨/tests/test_pmc_gate.py`（仅调整 legacy approved_by 不再授权的期望）

本计划没有读取或修改被拒的采购部级 `CLAUDE.md`；当前设备/业务阈值仍属 Owner/专业签认前置，不影响本次 mock 技术计划。

### Exact New Value-Type Contracts

`models.py` 的新增类型按以下完整字段实施，不改变既有模型：

```python
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
import json
import re
from typing import Literal

def _finite_number(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)

@dataclass(frozen=True)
class AllocationRow:
    demand_index: int
    material_id: str
    to_warehouse: str
    qty: float
    needed_by: str
    product_id: str
    status: Literal["provisionally_reserved", "unmet", "unranked"]
    from_warehouse: str | None
    reserved_qty: float
    arithmetic_shortage: float
    candidate_scores: tuple[tuple[str, float, int, tuple[tuple[int, float], ...]], ...]

    def __post_init__(self) -> None:
        if isinstance(self.demand_index, bool) or not isinstance(self.demand_index, int) or self.demand_index < 0:
            raise ValueError("demand_index must be a non-negative integer")
        if not self.material_id or not self.to_warehouse or not self.needed_by:
            raise ValueError("allocation identity fields are required")
        qty = _finite_number(self.qty, "qty")
        reserved = _finite_number(self.reserved_qty, "reserved_qty")
        shortage = _finite_number(self.arithmetic_shortage, "arithmetic_shortage")
        if qty <= 0 or reserved < 0 or shortage < 0:
            raise ValueError("allocation quantities are outside their allowed range")
        if self.status not in {"provisionally_reserved", "unmet", "unranked"}:
            raise ValueError("unknown allocation status")
        if self.status == "provisionally_reserved":
            if not self.from_warehouse or reserved != qty:
                raise ValueError("provisional reservation must reserve the full demand from one source")
        elif self.from_warehouse is not None or reserved != 0:
            raise ValueError("unmet/unranked rows cannot carry a reservation")
        copied_scores = tuple(
            (source, _finite_number(candidate_qty, "candidate qty"), hops,
             tuple((rank, _finite_number(score, "score")) for rank, score in score_tuple))
            for source, candidate_qty, hops, score_tuple in self.candidate_scores
        )
        if any(not source or candidate_qty <= 0 or isinstance(hops, bool)
               or not isinstance(hops, int) or hops < 0
               or len(score_tuple) != 4
               or any(isinstance(rank, bool) or not isinstance(rank, int) or rank not in {0, 1}
                      for rank, _ in score_tuple)
               for source, candidate_qty, hops, score_tuple in copied_scores):
            raise ValueError("candidate score identity/hops are invalid")
        object.__setattr__(self, "qty", qty)
        object.__setattr__(self, "reserved_qty", reserved)
        object.__setattr__(self, "arithmetic_shortage", shortage)
        object.__setattr__(self, "candidate_scores", copied_scores)

@dataclass(frozen=True)
class SharedReservationResult:
    rows: tuple[AllocationRow, ...]
    remaining_stock: tuple[tuple[str, str, str, float], ...]

    def __post_init__(self) -> None:
        rows = tuple(self.rows)
        remaining = tuple(
            (snapshot, source, material, _finite_number(qty, "remaining qty"))
            for snapshot, source, material, qty in self.remaining_stock
        )
        if any(not snapshot or not source or not material or qty < 0
               for snapshot, source, material, qty in remaining):
            raise ValueError("remaining stock rows require keys and non-negative quantities")
        object.__setattr__(self, "rows", rows)
        object.__setattr__(self, "remaining_stock", remaining)

@dataclass(frozen=True)
class DraftRevision:
    draft_id: str
    revision: int
    schema_version: str
    algorithm_version: str
    content_json: str
    content_hash: str

    def __post_init__(self) -> None:
        if not all((self.draft_id, self.schema_version, self.algorithm_version)):
            raise ValueError("revision identity and versions are required")
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision < 1:
            raise ValueError("revision must be a positive integer")
        if not isinstance(self.content_json, str):
            raise ValueError("content_json must be text")
        json.loads(self.content_json)
        if not re.fullmatch(r"[0-9a-f]{64}", self.content_hash):
            raise ValueError("content_hash must be lowercase SHA-256 hex")

@dataclass(frozen=True)
class ApprovalRecord:
    draft_id: str
    revision: int
    content_hash: str
    pmc_manager: str
    outcome: Literal["confirmed", "refused"]
    recorded_at: str

    def __post_init__(self) -> None:
        if not self.draft_id or not self.content_hash or not self.pmc_manager.strip():
            raise ValueError("approval identity and named actor are required")
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision < 1:
            raise ValueError("approval revision must be a positive integer")
        if self.outcome not in {"confirmed", "refused"}:
            raise ValueError("approval outcome is invalid")
        datetime.fromisoformat(self.recorded_at)

@dataclass(frozen=True)
class VersionedTransferPlanDraft:
    revision: DraftRevision
    approval: ApprovalRecord | None = None

    def __post_init__(self) -> None:
        if self.approval is not None and (
            self.approval.draft_id, self.approval.revision, self.approval.content_hash
        ) != (
            self.revision.draft_id, self.revision.revision, self.revision.content_hash
        ):
            raise ValueError("approval must bind the exact revision")
```

`remaining_stock` tuple 每项是 snapshot id、source warehouse、material id、remaining quantity，并按前三项排序。AllocationRow 仅存业务 scalar，禁止内嵌 frozen 但可能含可变引用的 TransferDemand/TransferCandidate。shortage 与 status 分离，不生成部分 provisional line。model validation 要求身份/版本/hash/姓名非空、revision>=1、数量 finite 且非负；provisional 必须整单且有 source，其余状态不得带 reservation。组合构造 VersionedTransferPlanDraft 时，approval 的 draft_id/revision/hash 必须与 revision 完全匹配。legacy TransferPlanDraft 字段保持原样。

## Implementation Tasks

每项按测试先行执行；本轮不执行以下任一命令。新类型必须实现真实 `__post_init__` 校验，而非仅在说明中列规则：`AllocationRow` 校验业务身份、状态集合、bool-excluded demand index 与数量、finite/non-negative 数量、整单 reservation invariant；`SharedReservationResult` 固化 rows/remaining_stock tuples；`DraftRevision` 校验非空 identity/version、非 bool 正整数 revision、JSON text 与 64 位 hex hash；`ApprovalRecord` 校验非空实名/时间及非 bool 正整数 revision；`VersionedTransferPlanDraft` 校验 approval 的 draft_id/revision/hash 精确匹配。新 routing 入口要求 priority 恰 4 个唯一原则键且与 `principles` 键完全一致；新入口拒绝 bool demand quantity 和 bool scenario index。

### 1. Add immutable revision and approval value types

**Files:** `sc11_transfer/models.py`, `tests/test_versioned_audit_gate.py`。

AllocationRow 保存需求业务 scalar、选择状态、整单数量、算术缺口、源仓编码及 candidate score scalar tuples，不嵌套 TransferDemand/TransferCandidate。SharedReservationResult 的剩余库存每项为 `(snapshot, source, material, remaining_qty)` 并按 key 排序。DraftRevision 保存 canonical JSON string 与 SHA-256，不存可变 payload。ApprovalRecord 保存确切 draft_id/revision/content_hash、实名 PMC、确认或拒绝及 UTC 时间。VersionedTransferPlanDraft 构造时要求 approval 与 revision 的 draft_id/revision/hash 完全一致。身份和版本非空、revision>=1、数量 finite 且满足 whole-demand invariant。保留现有 legacy dataclass/API 字段与签名。

**Tests first:** 值对象边界与输入拒绝纳入 versioned 模块固定 12 个用例；其中 `test_actor_and_refusal_reason_and_invalid_boundaries_rejected` 同时检查 `AllocationRow` bool index/qty、routing bool demand/index、重复原则键、非四键 priority 与 actor/refusal；不另设额外 collection。完整用例代码见后文“Complete future test cases”。先运行：

```powershell
param([Parameter(Mandatory = $true)][string]$CandidateRoot)
$sc11ResolvedRoot = (Resolve-Path -LiteralPath $CandidateRoot -ErrorAction Stop).Path
$sc11CandidateHead = (& git -C $sc11ResolvedRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $sc11CandidateHead -ne '28337c0ebb52afdbf61e955ecdbc22d151bcd185') { throw 'SC11 candidate HEAD differs from approved start' }
$sc11RunDir = Join-Path 'C:/Dev/zhuopin-ai/reports/sc11-inventory-transfer-1010' ('run-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $sc11RunDir -ErrorAction Stop | Out-Null
Push-Location (Join-Path $sc11ResolvedRoot '4-数字员工/采购部/SC11-库存智能调拨')
try {
    & 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -B -m pytest -q -ra -p no:cacheprovider 'tests/test_shared_reservation.py' 'tests/test_versioned_audit_gate.py' 'tests/test_pmc_gate.py' --basetemp (Join-Path $sc11RunDir 'basetemp') --junitxml (Join-Path $sc11RunDir 'junit.xml') 1> (Join-Path $sc11RunDir 'stdout.log') 2> (Join-Path $sc11RunDir 'stderr.log')
    $sc11TestExit = $LASTEXITCODE
    [IO.File]::WriteAllText((Join-Path $sc11RunDir 'exit-code.txt'), [string]$sc11TestExit, [Text.UTF8Encoding]::new($false))
}
finally { Pop-Location }
if ($sc11TestExit -ne 0) { throw "SC11 targeted pytest failed with exit code $sc11TestExit; preserve $sc11RunDir" }
```

预期先因类型尚不存在而失败；最终 versioned 模块统一收集 12 tests，不设单独的 3-test 收集数。具体代码与统一 UUID 证据命令见本计划后文。

### 2. Implement shared-reservation simulation without changing legacy routing

**Files:** `sc11_transfer/routing.py`, `tests/test_shared_reservation.py`。

新增完整接口 `build_shared_reservation_draft(demands: Sequence[TransferDemand], stock_by_warehouse: Mapping[str, Mapping[str, float]], principles: Mapping[str, Principle], priority_assumption: Sequence[str], *, scenario_order: Sequence[int], scenario_candidate_order: Mapping[int, Sequence[str]], inventory_snapshot_id: str) -> SharedReservationResult`。每个 demand 恰有一个 `AllocationRow`；`rows` 按 `scenario_order` 排列，`candidate` 仅在 provisional 时非空；`arithmetic_shortage` 精确定义为 `max(0, demand.qty - sum(该 demand 的所有非目标源仓当前余额))`，不表示可分配量；`remaining_stock` 行含 `(inventory_snapshot_id, source_warehouse, material_id, remaining_qty)`。不得改变 `build_draft` 的签名/语义。内部先复制库存，再严格遍历 scenario_order；每个 demand 对 live balance 调 `enumerate_candidates`，按四原则构成完整评分 tuple。全部不可评分则 `unranked`；非完整评分 tuple 的未决并列也 `unranked`；完整 tuple 唯一最优可选；完整 tuple 相同必须有覆盖并且无重复的 candidate order 才按 fixture 顺序选。candidate order 不得把更差评分提到前面。仅选中整单数量后一次扣账；无可行单仓候选时记完整 unmet，不扣账，并独立记总量 shortage。账本 key 在 content 输出中始终包含 snapshot id/source/material。

**Tests first:** 12 tests：SC11-C06（6 个库存满足先到的 4，后到 4 unmet；剩余2、shortage2）；翻转 demand 顺序；仓库/物料账本隔离；整单不可拆分及 shortage 分离；余额不足后转用另一个完整候选；demand order 非全排列拒绝；全缺评分 unranked；完整同分无候选顺序 unranked；显式候选顺序只破同分；非同分不能被候选顺序覆盖；局部缺分同分 unranked；余额非负且 unmet 不改变余额。候选评分行固定为 `(source_warehouse, qty, hops, score_tuple)`，模型、构造与 JSON 投影一律使用这四个字段。先运行：

```powershell
param([Parameter(Mandatory = $true)][string]$CandidateRoot)
$sc11ResolvedRoot = (Resolve-Path -LiteralPath $CandidateRoot -ErrorAction Stop).Path
$sc11CandidateHead = (& git -C $sc11ResolvedRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $sc11CandidateHead -ne '28337c0ebb52afdbf61e955ecdbc22d151bcd185') { throw 'SC11 candidate HEAD differs from approved start' }
$sc11RunDir = Join-Path 'C:/Dev/zhuopin-ai/reports/sc11-inventory-transfer-1010' ('run-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $sc11RunDir -ErrorAction Stop | Out-Null
Push-Location (Join-Path $sc11ResolvedRoot '4-数字员工/采购部/SC11-库存智能调拨')
try {
    & 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -B -m pytest -q -ra -p no:cacheprovider 'tests/test_shared_reservation.py' 'tests/test_versioned_audit_gate.py' 'tests/test_pmc_gate.py' --basetemp (Join-Path $sc11RunDir 'basetemp') --junitxml (Join-Path $sc11RunDir 'junit.xml') 1> (Join-Path $sc11RunDir 'stdout.log') 2> (Join-Path $sc11RunDir 'stderr.log')
    $sc11TestExit = $LASTEXITCODE
    [IO.File]::WriteAllText((Join-Path $sc11RunDir 'exit-code.txt'), [string]$sc11TestExit, [Text.UTF8Encoding]::new($false))
}
finally { Pop-Location }
if ($sc11TestExit -ne 0) { throw "SC11 targeted pytest failed with exit code $sc11TestExit; preserve $sc11RunDir" }
```

预期先因新入口尚不存在失败；实现后同命令须显示 12 passed。

### 3. Add canonical business payload and versioned create/revise orchestration

**Files:** `sc11_transfer/agent.py`, `sc11_transfer/models.py`, `tests/test_versioned_audit_gate.py`。

在 `agent.py` 保留 `_content_hash` 和 `run_draft` 旧行为，另新增完整接口 `run_versioned_draft(demands: Sequence[TransferDemand], stock_by_warehouse: Mapping[str, Mapping[str, float]], warehouses: Sequence[Warehouse], distances: Mapping[tuple[str, str], float], priority_assumption: Sequence[str], *, draft_id: str, inventory_snapshot_id: str, inventory_version: str, inventory_as_of: str, source_refs: Mapping[str, str], scenario_order: Sequence[int], scenario_candidate_order: Mapping[int, Sequence[str]], evaluator: str, audit: AuditLogger) -> VersionedTransferPlanDraft`。其中 `source_refs` 必须恰有 `plans/stock/distances` 三个非空字符串值；snapshot/version/as-of/draft_id/evaluator 均非空；`draft_id` 由调用方生成唯一 UUID，本进程重复创建会拒绝；audit 必须是可写且支持 JSONL chain verification 的 `AuditLogger`，写入后 `verify_chain().total >= 1`。入口构造版本化 principles、调用共享账本入口、构建规范化业务 payload、计算 SHA-256、创建 revision，然后先调用有效的 `audit.record(event: AuditEvent) -> None`（`scenario=SC11`、`action=transfer_plan_create`、`automation_level=L2`、decision 精确含 draft_id/revision/hash/假设/状态、data_sources 是 source_refs）再返回 wrapper。audit 写入异常直接传播。

新增完整接口 `revise_versioned_draft(previous: VersionedTransferPlanDraft, demands: Sequence[TransferDemand], stock_by_warehouse: Mapping[str, Mapping[str, float]], warehouses: Sequence[Warehouse], distances: Mapping[tuple[str, str], float], priority_assumption: Sequence[str], *, inventory_snapshot_id: str, inventory_version: str, inventory_as_of: str, source_refs: Mapping[str, str], scenario_order: Sequence[int], scenario_candidate_order: Mapping[int, Sequence[str]], evaluator: str, audit: AuditLogger) -> VersionedTransferPlanDraft`：固定 `draft_id`，revision 精确加一；按新全量输入重新模拟/hash；不复制 previous 的 approval；先追加 `transfer_plan_revise` 事件再返回未确认 revision。

canonical payload 明确列入每个 demand/candidate 的所有 dataclass 业务字段、初始 stock 与结果余额、snapshot/version/as-of、来源引用、distance 输入、四原则假设、两个 scenario orders、provisional/unranked/unmet/shortage 明细、schema/algorithm 版本。mapping key 排序，list 顺序只有业务语义顺序才保留；通过 `json.dumps(..., ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)` 固定编码。将 canonical UTF-8 bytes 的 SHA-256 写入 `content_hash`；显示文本、签认人、时间不进入 hash。

**Tests first:** versioned 模块目标固定为 12 个用例，覆盖 hash/input snapshot、source 变更、revision、JSONL 和 write-failure；完整代码见后文。先运行：

```powershell
param([Parameter(Mandatory = $true)][string]$CandidateRoot)
$sc11ResolvedRoot = (Resolve-Path -LiteralPath $CandidateRoot -ErrorAction Stop).Path
$sc11CandidateHead = (& git -C $sc11ResolvedRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $sc11CandidateHead -ne '28337c0ebb52afdbf61e955ecdbc22d151bcd185') { throw 'SC11 candidate HEAD differs from approved start' }
$sc11RunDir = Join-Path 'C:/Dev/zhuopin-ai/reports/sc11-inventory-transfer-1010' ('run-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $sc11RunDir -ErrorAction Stop | Out-Null
Push-Location (Join-Path $sc11ResolvedRoot '4-数字员工/采购部/SC11-库存智能调拨')
try {
    & 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -B -m pytest -q -ra -p no:cacheprovider 'tests/test_shared_reservation.py' 'tests/test_versioned_audit_gate.py' 'tests/test_pmc_gate.py' --basetemp (Join-Path $sc11RunDir 'basetemp') --junitxml (Join-Path $sc11RunDir 'junit.xml') 1> (Join-Path $sc11RunDir 'stdout.log') 2> (Join-Path $sc11RunDir 'stderr.log')
    $sc11TestExit = $LASTEXITCODE
    [IO.File]::WriteAllText((Join-Path $sc11RunDir 'exit-code.txt'), [string]$sc11TestExit, [Text.UTF8Encoding]::new($false))
}
finally { Pop-Location }
if ($sc11TestExit -ne 0) { throw "SC11 targeted pytest failed with exit code $sc11TestExit; preserve $sc11RunDir" }
```

预期新入口尚不存在时失败；完整实现后该模块收集 12 tests 并通过。

### 4. Bind confirmation/refusal and execution gate to exact current revision

**Files:** `sc11_transfer/gate.py`, `tests/test_versioned_audit_gate.py`, `tests/test_pmc_gate.py`。

新增 `confirm_versioned_draft(draft: VersionedTransferPlanDraft, pmc_manager: str, *, evaluator: str, audit: AuditLogger) -> VersionedTransferPlanDraft` 和 `refuse_versioned_draft(draft, pmc_manager, reason, *, evaluator, audit) -> VersionedTransferPlanDraft`。两者校验实名/evaluator、对 `content_json` 重算 hash 等于 revision hash，再先写对应 L2 `transfer_plan_confirm` / `transfer_plan_refuse` JSONL 事件（绑定当前 draft_id/revision/hash、责任人与结果），成功后返回附带不可变 `ApprovalRecord` 的新 wrapper；audit 失败不得返回有效确认/拒绝状态。拒绝结果永不满足执行授权。

保留 `approve(draft, pmc_manager)` 与执行函数一参数签名以兼容调用/数据字段；legacy approve 只更新旧投影。`commit_to_erp(draft)` / `notify_outsourced_warehouse(draft)` 对 legacy `TransferPlanDraft` 一律 `PmcApprovalRequired`（说明旧 approved_by 无版本授权）；对版本化 wrapper 校验 approval 的 outcome、实名、draft_id、revision、hash 与当前重算 hash。任一缺失/失配均 `PmcApprovalRequired`；精确确认匹配时仍抛既有 `NotWiredYet`。邮件错误继续明确另需单独外发授权。此改动不连接通道，不产生成功落库/发送 audit。

**Tests first:** versioned 模块固定 12 tests，覆盖实名/hash gate、refuse、legacy approved_by、通道未接、四类独立审计写失败（create 使用真实 `JsonlSink` 目录写失败；confirm/refuse/revise 各独立注入 sink failure）；完整用例代码见后文。更新 `test_pmc_gate.py` 中一项 legacy expectation 为先抛 `PmcApprovalRequired`；六项既有测试仍保留。先运行：

```powershell
param([Parameter(Mandatory = $true)][string]$CandidateRoot)
$sc11ResolvedRoot = (Resolve-Path -LiteralPath $CandidateRoot -ErrorAction Stop).Path
$sc11CandidateHead = (& git -C $sc11ResolvedRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $sc11CandidateHead -ne '28337c0ebb52afdbf61e955ecdbc22d151bcd185') { throw 'SC11 candidate HEAD differs from approved start' }
$sc11RunDir = Join-Path 'C:/Dev/zhuopin-ai/reports/sc11-inventory-transfer-1010' ('run-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $sc11RunDir -ErrorAction Stop | Out-Null
Push-Location (Join-Path $sc11ResolvedRoot '4-数字员工/采购部/SC11-库存智能调拨')
try {
    & 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -B -m pytest -q -ra -p no:cacheprovider 'tests/test_shared_reservation.py' 'tests/test_versioned_audit_gate.py' 'tests/test_pmc_gate.py' --basetemp (Join-Path $sc11RunDir 'basetemp') --junitxml (Join-Path $sc11RunDir 'junit.xml') 1> (Join-Path $sc11RunDir 'stdout.log') 2> (Join-Path $sc11RunDir 'stderr.log')
    $sc11TestExit = $LASTEXITCODE
    [IO.File]::WriteAllText((Join-Path $sc11RunDir 'exit-code.txt'), [string]$sc11TestExit, [Text.UTF8Encoding]::new($false))
}
finally { Pop-Location }
if ($sc11TestExit -ne 0) { throw "SC11 targeted pytest failed with exit code $sc11TestExit; preserve $sc11RunDir" }
```

预期首次因版本化 gate 未实现失败；实现后 focused gate 命令收集 18 tests（新模块 12 + 既有 gate 6）并通过。

### 5. Review the narrow mock slice and run SC11 package regression

**Files:** 仅上述 7 个未来实施路径。

独立 review 逐条核 Spec Review Focus；确认 legacy 字段不能授权、现有 22 个骨架测试仍通过，新增共享账本与版本化测试各 12 项。禁止真实输入、ERP/mail、开发服务、真实 PMC 签认、修改平台、修改 OpenSpec 或归档。

```powershell
param([Parameter(Mandatory = $true)][string]$CandidateRoot)
$sc11ResolvedRoot = (Resolve-Path -LiteralPath $CandidateRoot -ErrorAction Stop).Path
$sc11CandidateHead = (& git -C $sc11ResolvedRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $sc11CandidateHead -ne '28337c0ebb52afdbf61e955ecdbc22d151bcd185') { throw 'SC11 candidate HEAD differs from approved start' }
$sc11RunDir = Join-Path 'C:/Dev/zhuopin-ai/reports/sc11-inventory-transfer-1010' ('run-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $sc11RunDir -ErrorAction Stop | Out-Null
Push-Location (Join-Path $sc11ResolvedRoot '4-数字员工/采购部/SC11-库存智能调拨')
try {
    & 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -B -m pytest -q -ra -p no:cacheprovider 'tests/test_shared_reservation.py' 'tests/test_versioned_audit_gate.py' 'tests/test_pmc_gate.py' --basetemp (Join-Path $sc11RunDir 'basetemp') --junitxml (Join-Path $sc11RunDir 'junit.xml') 1> (Join-Path $sc11RunDir 'stdout.log') 2> (Join-Path $sc11RunDir 'stderr.log')
    $sc11TestExit = $LASTEXITCODE
    [IO.File]::WriteAllText((Join-Path $sc11RunDir 'exit-code.txt'), [string]$sc11TestExit, [Text.UTF8Encoding]::new($false))
}
finally { Pop-Location }
if ($sc11TestExit -ne 0) { throw "SC11 targeted pytest failed with exit code $sc11TestExit; preserve $sc11RunDir" }
```

本次三文件期望 **30 passed、0 failed、0 skipped**（6 个既有 PMC gate + 新增 24：12 个共享库存、12 个版本/hash/audit/gate）。原全包 46 仅为历史背景，不运行。节点命令均在场景目录执行；不在仓库根混跑，不安装 editable 包。测试文件只用 `tmp_path` 写 JSONL；运行证据使用新 UUID ignored 子目录并保留旧证据。本轮没有运行这些命令。

## Review Focus

1. **A2 shared stock / no split:** 对 `(snapshot, source, material)` 共用余额守恒；整单 provisional 或完整 unmet，短缺数字独立；SC11-C06 任一顺序都是 provisional 4 / unmet 4 / balance 2 / shortage 2。Owned by `test_shared_reservation.py` 的前 7 项。
2. **两种顺序没有业务越权:** demand `scenario_order` 只决定 mock 试算访问顺序；candidate order 只能破完整评分 tuple 同分；缺评分、未解平分不得依稳定输入顺序暗选。Owned by `test_shared_reservation.py` 的 8–12 项。
3. **Hash 覆盖完整且 canonical:** snapshot/source/as-of、输入值、schema/algorithm、两种顺序、假设、lines/unmet/shortage 均入 hash；display/time/evaluator 不入业务 hash；NaN/Infinity 拒绝。Owned by `test_versioned_audit_gate.py` 的 4–12 项。
4. **不可变确认不可迁移:** confirm/refuse/revise 留存旧对象；新 revision 无旧确认；必须匹配 `draft_id/revision/hash`；`approved_by` 非空或旧 approval 均不得放行。Owned by versioned gate tests 与 `test_pmc_gate.py`。
5. **持久 audit / 通道 fail closed:** create/confirm/refuse/revise 事件可从真实 JSONL 读回并绑定精确 hash；evaluator/audit 缺失或写失败不返回有效状态；匹配批准后 ERP/mail 仍 `NotWiredYet`，mail 另需授权。Owned by `test_versioned_audit_gate.py` 的 JSONL/failure/channel cases。

## Dependencies, Blockers, and Migration

- 本计划只覆盖合成首项技术切片。`tasks.md` 的 2.2 前置总表更新与打标/Owner闭合、2.3 生产计划通路、2.4 三委外仓库存、2.5 专业原则签认和实名 backup、2.6 物流矩阵/口径分别维持原状态；本计划不声称这些已完。
- 六项专业规则问题（原则冲突优先、尽量少定义、距离单位/矩阵来源、拆分/替代、月中插单、缺数据处置）各自继续挡住对应真实业务阶段，不挡获批后的纯 mock 技术实现。真实输入还需要权限、版本/as-of 与来源审计；不从 fixture 推导业务 Owner 或阈值。
- 旧 draft 和旧 approval 字段/记录原样保留作历史展示；不自动迁移旧 `approved_by` 为新的 `ApprovalRecord`。旧执行函数名/单参形态继续存在，但版本化确认才可走严格检查；未接通道仍 fail-loud。回滚保留旧骨架，不得用旧签名放行新版本。
- 已批准的 3M mock 依赖拆分继续按 tasks 执行；本计划只待计划及精确白名单获批后，才可开始 mock 实现/测试。全场景保持未归档。

## Authoritative Test Count and Audit Failure Matrix

The single implementation-stage count is: `test_shared_reservation.py` 12 tests; `test_versioned_audit_gate.py` 12 tests; existing `test_pmc_gate.py` 6 tests. Focused gate is 18; the full SC11 package is **46** (22 baseline + 24 new). Four fail-closed audit cases are distinct create, confirm, refuse and revise sink-write tests. These are future expected counts only.

## Self-Review / Approval Request

- Design/spec 对应 A2/B2 目标、原门禁、mock 边界与真实前置均覆盖；实施路径限定为 4 源码 + 3 测试文件；没有省略号、TODO、未定义新平台接口或空断言。
- 原 API 符号/签名保留，但 `approved_by` 不再是授权依据；legacy gate 的更严格拒绝是为了符合已批准 spec，须在计划审查中确认这项兼容口径。
- **请求审查本计划的逐文件范围、legacy gate 行为、测试断言/计数及是否允许按上述 3M mock 窄片推进。** 本计划获批前不实施、不跑产品测试、不晋档、不归档。
+


## Concrete executable source additions and test code

This appendix is the source of truth for the new entrypoints described above. Keep the original legacy functions unchanged.

### routing.py addition

Import isfinite from math; add this definition without editing enumerate_candidates, rank_candidates, or build_draft.

```python
def build_shared_reservation_draft(
    demands: Sequence[TransferDemand],
    stock_by_warehouse: Mapping[str, Mapping[str, float]],
    principles: Mapping[str, Principle],
    priority_assumption: Sequence[str],
    *,
    scenario_order: Sequence[int],
    scenario_candidate_order: Mapping[int, Sequence[str]],
    inventory_snapshot_id: str,
) -> SharedReservationResult:
    if len(principles) != 4 or len(priority_assumption) != 4 or len(set(priority_assumption)) != 4 or set(priority_assumption) != set(principles):
        raise ValueError("all four principle keys are required")
    if not inventory_snapshot_id:
        raise ValueError("inventory snapshot id is required")
    if any(isinstance(index, bool) or not isinstance(index, int) for index in scenario_order):
        raise ValueError("scenario indices must be integers, not bool")
    if len(scenario_order) != len(demands) or set(scenario_order) != set(range(len(demands))):
        raise ValueError("scenario_order must be a full permutation")
    if any(isinstance(index, bool) or not isinstance(index, int)
           or index < 0 or index >= len(demands) for index in scenario_candidate_order):
        raise ValueError("candidate-order keys must name a valid demand index")
    balances: dict[tuple[str, str], float] = {}
    for warehouse, items in stock_by_warehouse.items():
        for material, raw in items.items():
            if isinstance(raw, bool):
                raise ValueError("stock quantities cannot be bool")
            qty = float(raw)
            if not warehouse or not material or not isfinite(qty) or qty < 0:
                raise ValueError("stock must have keys and finite non-negative quantities")
            balances[(warehouse, material)] = qty
    rows: list[AllocationRow] = []
    for index in scenario_order:
        demand = demands[index]
        if isinstance(demand.qty, bool):
            raise ValueError("demand quantities cannot be bool")
        qty = float(demand.qty)
        if not isfinite(qty) or qty <= 0:
            raise ValueError("demand must be finite and positive")
        shortage = max(0.0, qty - sum(
            stock for (wh, material), stock in balances.items()
            if material == demand.material_id and wh != demand.to_warehouse
        ))
        live: dict[str, dict[str, float]] = {}
        for (wh, material), stock in balances.items():
            live.setdefault(wh, {})[material] = stock
        candidates = enumerate_candidates(demand, live)
        scored: list[tuple[TransferCandidate, tuple[tuple[int, float], ...], bool]] = []
        for candidate in candidates:
            score_tuple: list[tuple[int, float]] = []
            complete = True
            for key in priority_assumption:
                raw_score = principles[key].score(candidate)
                if raw_score is None:
                    score_tuple.append((1, 0.0))
                    complete = False
                else:
                    score = float(raw_score)
                    if not isfinite(score):
                        raise ValueError("principle scores must be finite or None")
                    score_tuple.append((0, score))
            scored.append((candidate, tuple(score_tuple), complete))
        score_rows = tuple(
            (candidate.from_warehouse, candidate.qty, candidate.hops, score)
            for candidate, score, _ in sorted(scored, key=lambda item: item[0].from_warehouse)
        )
        selected = None
        status = "unmet" if not scored else "unranked"
        if scored:
            best_key = min(item[1] for item in scored)
            best = [item for item in scored if item[1] == best_key]
            if len(best) == 1 and best[0][2]:
                selected, status = best[0][0], "provisionally_reserved"
            elif len(best) > 1 and all(item[2] for item in best):
                order = scenario_candidate_order.get(index)
                feasible = {item[0].from_warehouse for item in scored}
                tied = {item[0].from_warehouse for item in best}
                if order is not None and len(order) == len(set(order)) and set(order) == feasible:
                    source = next((warehouse for warehouse in order if warehouse in tied), None)
                    selected = next(
                        (item[0] for item in best if item[0].from_warehouse == source), None
                    )
                    if selected is not None:
                        status = "provisionally_reserved"
        if selected is not None:
            account = (selected.from_warehouse, demand.material_id)
            balances[account] -= qty
            if balances[account] < 0:
                raise AssertionError("reservation made stock negative")
        rows.append(AllocationRow(
            demand_index=index, material_id=demand.material_id,
            to_warehouse=demand.to_warehouse, qty=qty, needed_by=demand.needed_by,
            product_id=demand.product_id, status=status,
            from_warehouse=selected.from_warehouse if selected else None,
            reserved_qty=qty if selected else 0.0, arithmetic_shortage=shortage,
            candidate_scores=score_rows,
        ))
    remaining = tuple(
        (inventory_snapshot_id, wh, material, qty)
        for (wh, material), qty in sorted(balances.items())
    )
    return SharedReservationResult(tuple(rows), remaining)
```

### Canonical payload construction and lifecycle

Add in agent.py next to current imports/constants; import JsonlSink from zhuopin_platform.audit.sinks. The current APIs used here are build_principles, warehouse_index, AuditEvent and AuditLogger.record. Import `require_new_draft_id`, `register_current_revision` and `_require_current_revision` from `sc11_transfer.gate` (gate imports only models, so this direction introduces no cycle). Keep run_draft and its _content_hash behavior unchanged.

```python
SC11_SCHEMA_VERSION = "sc11-transfer-v1"
SC11_ALGORITHM_VERSION = "shared-reservation-a2-v1"

def _canonical_hash(payload: dict[str, Any]) -> tuple[str, str]:
    content_json = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return content_json, hashlib.sha256(content_json.encode("utf-8")).hexdigest()

def _versioned_build(
    demands, stock_by_warehouse, warehouses, distances, priority_assumption, *,
    draft_id, revision, inventory_snapshot_id, inventory_version, inventory_as_of,
    source_refs, scenario_order, scenario_candidate_order, evaluator, audit, action,
):
    required = {"plans", "stock", "distances"}
    if not draft_id.strip() or not evaluator.strip():
        raise ValueError("draft_id and evaluator are required")
    if not inventory_snapshot_id.strip() or not inventory_version.strip() or not inventory_as_of.strip():
        raise ValueError("snapshot/version/as_of are required")
    if set(source_refs) != required or any(not isinstance(v, str) or not v.strip() for v in source_refs.values()):
        raise ValueError("source_refs must contain plans/stock/distances")
    if not isinstance(audit, AuditLogger) or not isinstance(audit.sink, JsonlSink):
        raise ValueError("versioned entry requires JSONL AuditLogger")
    if action == "transfer_plan_create":
        require_new_draft_id(draft_id, audit)
    if set(priority_assumption) != {
        "fewest_cross_warehouse", "prefer_material_warehouse",
        "shared_material_by_line_date", "nearest_between_outsourced",
    }:
        raise ValueError("four principle assumptions must be explicit")
    principles = build_principles(warehouse_index(warehouses), distances)
    result = build_shared_reservation_draft(
        demands, stock_by_warehouse, principles, priority_assumption,
        scenario_order=scenario_order, scenario_candidate_order=scenario_candidate_order,
        inventory_snapshot_id=inventory_snapshot_id,
    )
    payload = {
        "schema_version": SC11_SCHEMA_VERSION,
        "algorithm_version": SC11_ALGORITHM_VERSION,
        "draft_id": draft_id,
        "revision": revision,
        "inventory": {"snapshot_id": inventory_snapshot_id,
                      "version": inventory_version, "as_of": inventory_as_of},
        "source_refs": dict(sorted(source_refs.items())),
        "demands": [
            {"material_id": d.material_id, "to_warehouse": d.to_warehouse, "qty": float(d.qty),
             "needed_by": d.needed_by, "product_id": d.product_id} for d in demands
        ],
        "initial_stock": [
            {"warehouse": wh, "material": material, "qty": float(qty)}
            for wh, items in sorted(stock_by_warehouse.items())
            for material, qty in sorted(items.items())
        ],
        "warehouses": [
            {"code": w.code, "name": w.name, "kind": w.kind.value}
            for w in sorted(warehouses, key=lambda item: item.code)
        ],
        "distances": [
            {"from": pair[0], "to": pair[1], "value": float(value)}
            for pair, value in sorted(distances.items())
        ],
        "priority_assumption": list(priority_assumption),
        "scenario_order": list(scenario_order),
        "scenario_candidate_order": {
            str(i): list(order) for i, order in sorted(scenario_candidate_order.items())
        },
        "rows": [
            {"demand_index": r.demand_index, "material_id": r.material_id,
             "to_warehouse": r.to_warehouse, "qty": r.qty, "needed_by": r.needed_by,
             "product_id": r.product_id, "status": r.status,
             "from_warehouse": r.from_warehouse, "reserved_qty": r.reserved_qty,
             "arithmetic_shortage": r.arithmetic_shortage,
             "candidate_scores": [
                 {"source": source, "qty": qty, "hops": hops,
                  "tuple": [list(pair) for pair in score]}
                 for source, qty, hops, score in r.candidate_scores
             ]} for r in result.rows
        ],
        "remaining_stock": [list(row) for row in result.remaining_stock],
    }
    content_json, digest = _canonical_hash(payload)
    revision_value = DraftRevision(
        draft_id, revision, SC11_SCHEMA_VERSION, SC11_ALGORITHM_VERSION, content_json, digest
    )
    audit.record(AuditEvent(
        scenario=SCENARIO, action=action, evaluator=evaluator.strip(), automation_level="L2",
        decision={"event": action, "draft_id": draft_id, "revision": revision,
                  "content_hash": digest, "priority_assumption": list(priority_assumption),
                  "scenario_order": list(scenario_order),
                  "scenario_candidate_order": {
                      str(i): list(order) for i, order in sorted(scenario_candidate_order.items())
                  }, "status": "draft"},
        data_sources=dict(source_refs), content_hash=digest,
    ))
    register_current_revision(revision_value, audit)
    return VersionedTransferPlanDraft(revision_value)

def run_versioned_draft(
    demands, stock_by_warehouse, warehouses, distances, priority_assumption, *,
    draft_id, inventory_snapshot_id, inventory_version, inventory_as_of, source_refs,
    scenario_order, scenario_candidate_order, evaluator, audit,
) -> VersionedTransferPlanDraft:
    return _versioned_build(
        demands, stock_by_warehouse, warehouses, distances, priority_assumption,
        draft_id=draft_id, revision=1, inventory_snapshot_id=inventory_snapshot_id,
        inventory_version=inventory_version, inventory_as_of=inventory_as_of,
        source_refs=source_refs, scenario_order=scenario_order,
        scenario_candidate_order=scenario_candidate_order, evaluator=evaluator,
        audit=audit, action="transfer_plan_create",
    )

def revise_versioned_draft(
    previous, demands, stock_by_warehouse, warehouses, distances, priority_assumption, *,
    inventory_snapshot_id, inventory_version, inventory_as_of, source_refs, scenario_order,
    scenario_candidate_order, evaluator, audit,
) -> VersionedTransferPlanDraft:
    old = previous.revision
    actual = _canonical_hash(json.loads(old.content_json))[1]
    if actual != old.content_hash:
        raise ValueError("previous revision hash is invalid")
    _require_current_revision(old, audit=audit)
    return _versioned_build(
        demands, stock_by_warehouse, warehouses, distances, priority_assumption,
        draft_id=old.draft_id, revision=old.revision + 1,
        inventory_snapshot_id=inventory_snapshot_id, inventory_version=inventory_version,
        inventory_as_of=inventory_as_of, source_refs=source_refs,
        scenario_order=scenario_order, scenario_candidate_order=scenario_candidate_order,
        evaluator=evaluator, audit=audit, action="transfer_plan_revise",
    )
```

All original demand/stock/warehouse/distance values are copied into the payload before return. This payload binds hash to schema, algorithm, source refs, input versions/as-of, all assumptions, score tuples and outputs. The exact JSON encoding is ensure_ascii=False, sorted keys, compact separators, allow_nan=False; UTF-8 SHA-256. Audit append happens before returning the draft. Revise reuses draft ID, increments revision, recomputes full payload/hash, and drops old approval.

### Confirmation, refusal and execution gate

Keep existing approve(TransferPlanDraft, pmc_manager) unchanged as legacy data projection. Add versioned types, AuditLogger, hashlib/datetime/AuditEvent imports. Preserve one draft argument on execution calls. The registry below is only a process-local handle to the persisted JSONL current-version authority. A missing handle (including after process restart) rejects execution; no approval is automatically rehydrated or trusted from a detached object.

```python
from zhuopin_platform.audit.sinks import JsonlSink

_CURRENT_REVISION_AUDIT: dict[str, AuditLogger] = {}

def require_new_draft_id(draft_id: str, audit: AuditLogger) -> None:
    if not draft_id.strip() or draft_id in _CURRENT_REVISION_AUDIT:
        raise ValueError("draft_id must be non-empty and unique in this process")
    if _latest_revision_event(audit, draft_id) is not None:
        raise ValueError("draft_id already exists in this JSONL history")

def _latest_revision_event(audit: AuditLogger, draft_id: str) -> dict | None:
    rows = audit.query_by(scenario="SC11")
    matching = [
        row for row in rows
        if row.get("action") in {"transfer_plan_create", "transfer_plan_revise"}
        and row.get("decision", {}).get("draft_id") == draft_id
    ]
    return matching[-1] if matching else None

def _require_current_revision(revision: DraftRevision, *, audit: AuditLogger | None = None) -> None:
    registered = _CURRENT_REVISION_AUDIT.get(revision.draft_id)
    authority = registered if registered is not None else audit
    if authority is None:
        raise PmcApprovalRequired("current revision authority is unavailable")
    if not isinstance(authority, AuditLogger) or not isinstance(authority.sink, JsonlSink):
        raise PmcApprovalRequired("current revision requires JSONL authority")
    if audit is not None and (
        not isinstance(audit, AuditLogger) or not isinstance(audit.sink, JsonlSink)
        or audit.sink.log_path.resolve() != authority.sink.log_path.resolve()
    ):
        raise PmcApprovalRequired("audit differs from registered current authority")
    chain = authority.verify_chain()
    if not chain.ok or chain.total < 1:
        raise PmcApprovalRequired("audit chain is invalid")
    latest = _latest_revision_event(authority, revision.draft_id)
    if latest is None:
        raise PmcApprovalRequired("current revision is absent from audit history")
    decision = latest.get("decision", {})
    if (decision.get("revision"), decision.get("content_hash")) != (
        revision.revision, revision.content_hash
    ):
        raise PmcApprovalRequired("draft is not the current audited revision")

def register_current_revision(revision: DraftRevision, audit: AuditLogger) -> None:
    _require_current_revision(revision, audit=audit)
    _CURRENT_REVISION_AUDIT[revision.draft_id] = audit

def _verify_revision(draft: VersionedTransferPlanDraft) -> None:
    actual = hashlib.sha256(draft.revision.content_json.encode("utf-8")).hexdigest()
    if actual != draft.revision.content_hash:
        raise PmcApprovalRequired("draft hash does not match content")

def _record_decision(draft, pmc_manager, outcome, evaluator, audit, reason=""):
    if not pmc_manager.strip() or not evaluator.strip():
        raise ValueError("PMC manager and evaluator are required")
    _verify_revision(draft)
    r = draft.revision
    _require_current_revision(r, audit=audit)
    action = "transfer_plan_confirm" if outcome == "confirmed" else "transfer_plan_refuse"
    event = AuditEvent(
        scenario="SC11", action=action, evaluator=evaluator.strip(), automation_level="L2",
        decision={"event": action, "draft_id": r.draft_id, "revision": r.revision,
                  "content_hash": r.content_hash, "pmc_manager": pmc_manager.strip(),
                  "outcome": outcome, "reason": reason},
        data_sources={"draft": "sha256:" + r.content_hash}, content_hash=r.content_hash,
    )
    audit.record(event)
    record = ApprovalRecord(
        r.draft_id, r.revision, r.content_hash, pmc_manager.strip(), outcome, event.timestamp,
    )
    return VersionedTransferPlanDraft(r, record)

def confirm_versioned_draft(draft, pmc_manager, *, evaluator, audit):
    if draft.approval is not None:
        raise PmcApprovalRequired("revise before another decision")
    return _record_decision(draft, pmc_manager, "confirmed", evaluator, audit)

def refuse_versioned_draft(draft, pmc_manager, reason, *, evaluator, audit):
    if not reason.strip():
        raise ValueError("refusal reason is required")
    if draft.approval is not None:
        raise PmcApprovalRequired("revise before another decision")
    return _record_decision(draft, pmc_manager, "refused", evaluator, audit, reason.strip())

def _require_versioned_confirmation(draft, action):
    if isinstance(draft, TransferPlanDraft):
        raise PmcApprovalRequired(action + ": legacy approved_by is not version-bound")
    if not isinstance(draft, VersionedTransferPlanDraft):
        raise PmcApprovalRequired(action + ": versioned draft required")
    _verify_revision(draft)
    a, r = draft.approval, draft.revision
    _require_current_revision(r)
    if a is None or a.outcome != "confirmed" or not a.pmc_manager.strip():
        raise PmcApprovalRequired(action + ": exact PMC confirmation required")
    if (a.draft_id, a.revision, a.content_hash) != (r.draft_id, r.revision, r.content_hash):
        raise PmcApprovalRequired(action + ": confirmation does not bind revision")
    authority = _CURRENT_REVISION_AUDIT[r.draft_id]
    decisions = [row for row in authority.query_by(scenario="SC11")
                 if row.get("action") in {"transfer_plan_confirm", "transfer_plan_refuse"}
                 and row.get("decision", {}).get("draft_id") == r.draft_id
                 and row.get("decision", {}).get("revision") == r.revision
                 and row.get("decision", {}).get("content_hash") == r.content_hash]
    latest = decisions[-1] if decisions else None
    if latest is None or latest.get("action") != "transfer_plan_confirm":
        raise PmcApprovalRequired(action + ": current confirmation is absent or refused")
    decision = latest["decision"]
    if (decision.get("pmc_manager"), decision.get("outcome"), latest.get("timestamp")) != (
        a.pmc_manager, a.outcome, a.recorded_at
    ):
        raise PmcApprovalRequired(action + ": confirmation does not match persisted event")

def commit_to_erp(draft: TransferPlanDraft | VersionedTransferPlanDraft) -> None:
    _require_versioned_confirmation(draft, "ERP commit")
    raise NotWiredYet("ERP write path is not connected.")

def notify_outsourced_warehouse(
    draft: TransferPlanDraft | VersionedTransferPlanDraft,
) -> None:
    _require_versioned_confirmation(draft, "warehouse notice")
    raise NotWiredYet("Mail is not connected; sending requires separate authorization.")
```

### Complete test modules

Reservation test module has 12 independently collected tests for C06 order, reverse order, no split, shortage, multiple candidates, frozen/source mutation, invalid demand permutation, missing scores, explicit complete tie, non-tie precedence, partial tie order, and incomplete score tie. Versioned module has 12 tests for canonical input detachment/hash changes, revision without approval migration/current-version rejection, four-event JSONL/chain (`verify_chain().ok` and `.total == 4`), four separate audit-write failures (one real `JsonlSink` filesystem failure), actor/refusal and invalid-boundary validation, refused/legacy gate, matching confirmation with unwired channels, and tampered content.

The following code block is an illustrative excerpt, not a separate pytest module. The complete source for each new test file appears in the final section titled “Full test-file source for the approved plan”; only those two complete modules define the planned collection.

```python
def test_c06_shared_reservation_conserves_stock():
    result = run([demand(4), demand(4)], {"SRC": {"M1": 6.0}})
    assert [row.status for row in result.rows] == ["provisionally_reserved", "unmet"]
    assert [row.reserved_qty for row in result.rows] == [4.0, 0.0]
    assert result.rows[1].arithmetic_shortage == 2.0
    assert result.remaining_stock == (("snap-1", "SRC", "M1", 2.0),)

def test_c06_reverse_order_uses_full_remaining_stock():
    result = run([demand(4), demand(4)], {"SRC": {"M1": 6.0}}, order=(1, 0))
    assert [row.demand_index for row in result.rows] == [1, 0]
    assert [row.status for row in result.rows] == ["provisionally_reserved", "unmet"]
    assert [row.reserved_qty for row in result.rows] == [4.0, 0.0]
    assert result.rows[1].arithmetic_shortage == 2.0
    assert result.remaining_stock[0][3] == 2.0

def test_unresolved_equal_complete_scores_do_not_use_stable_order():
    result = run([demand()], {"A": {"M1": 6.0}, "B": {"M1": 6.0}},
                 score=lambda wh, key: 1.0)
    assert result.rows[0].status == "unranked"

def test_source_mutation_cannot_change_revision_hash(tmp_path):
    demands, stock, warehouses, distances = inputs()
    draft = create_from_values(tmp_path, demands, stock, warehouses, distances)
    captured = draft.revision.content_json
    digest = draft.revision.content_hash
    stock["MAT"]["M1"] = 99.0
    distances[("MAT", "OUT")] = 50.0
    demands.append(TransferDemand("M2", "OUT", 1.0, "2026-10-11"))
    assert draft.revision.content_json == captured
    assert hashlib.sha256(captured.encode("utf-8")).hexdigest() == digest

def test_confirm_sink_injection_propagates(tmp_path, monkeypatch):
    audit = AuditLogger.jsonl(tmp_path / "events.jsonl")
    draft = create(tmp_path, audit=audit)
    def fail(event):
        raise OSError("sink unavailable")
    monkeypatch.setattr(audit, "record", fail)
    with pytest.raises(OSError):
        confirm_versioned_draft(draft, "PMC A", evaluator="reviewer", audit=audit)
    assert draft.approval is None
```

The earlier snippets are examples only and do not add separate test cases. The two complete source blocks in the final section define the full 12 + 12 collection.

## Test counts, review focus, future commands

Single consistent totals: existing SC11 22; test_shared_reservation.py 12; test_versioned_audit_gate.py 12; test_pmc_gate.py remains 6; focused gate 18; complete package 46. This expected collection count replaces every earlier interim count in this draft.

Five review focuses:
1. Shared stock/no split and arithmetic shortage: reservation tests for C06, no split, shortage and second source.
2. Demand/tie order and missing scores: permutation, incomplete score, explicit tie, strict score, partial order.
3. Canonical content/detachment: hashes include all input versions/refs/assumptions/results, source mutation does not change stored content.
4. Confirmation cannot migrate: hash/revision actor binding, revision drops approval, legacy approved_by never authorizes.
5. Real JSONL/fail closed: create/confirm/refuse/revise events chain, each append failure propagates, connected channels remain NotWiredYet.

Only after approval of this plan and its exact seven-path whitelist, execute commands from the SC11 package directory. Each run writes to a freshly generated ignored UUID path; never delete old evidence.

```powershell
param([Parameter(Mandatory = $true)][string]$CandidateRoot)
$sc11ResolvedRoot = (Resolve-Path -LiteralPath $CandidateRoot -ErrorAction Stop).Path
$sc11CandidateHead = (& git -C $sc11ResolvedRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $sc11CandidateHead -ne '28337c0ebb52afdbf61e955ecdbc22d151bcd185') { throw 'SC11 candidate HEAD differs from approved start' }
$sc11RunDir = Join-Path 'C:/Dev/zhuopin-ai/reports/sc11-inventory-transfer-1010' ('run-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $sc11RunDir -ErrorAction Stop | Out-Null
Push-Location (Join-Path $sc11ResolvedRoot '4-数字员工/采购部/SC11-库存智能调拨')
try {
    & 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -B -m pytest -q -ra -p no:cacheprovider 'tests/test_shared_reservation.py' 'tests/test_versioned_audit_gate.py' 'tests/test_pmc_gate.py' --basetemp (Join-Path $sc11RunDir 'basetemp') --junitxml (Join-Path $sc11RunDir 'junit.xml') 1> (Join-Path $sc11RunDir 'stdout.log') 2> (Join-Path $sc11RunDir 'stderr.log')
    $sc11TestExit = $LASTEXITCODE
    [IO.File]::WriteAllText((Join-Path $sc11RunDir 'exit-code.txt'), [string]$sc11TestExit, [Text.UTF8Encoding]::new($false))
}
finally { Pop-Location }
if ($sc11TestExit -ne 0) { throw "SC11 targeted pytest failed with exit code $sc11TestExit; preserve $sc11RunDir" }
```

Expected future results: 12 / 12 / 18 / 46 passed and zero skips/errors/failures. No command was run during this plan edit. The root execution boundary limits future runs to the three focused files (expected 30); earlier full-package 46 is context only. reports/sc11-inventory-transfer-1010 is ignored; keep every UUID directory.

## Existing dependencies and boundaries

Tasks 2.2 master-data completeness/Owner closure; 2.3 production plan feed; 2.4 outsourced inventory feed; 2.5 professional principles and named backup; 2.6 logistics matrix remain unchanged. The six professional questions (priority conflict, fewest metric, distance source/unit, split/substitute, mid-month insertion, missing-data action) block respective real stages only; do not infer an Owner/threshold from fixtures. Preserve legacy approved_by as history and never migrate it to versioned confirmation. ERP/mail remain disconnected; mail needs separate authorization. Do not re-approve accepted A2/B2 or the approved 3M dependency split. Full scene stays unarchived.

## Self-review and approval request

Plan preparation only: code/test contents are proposals for review, not implemented or executed. The design freezes, approved task split, source contracts, three focused files with 12/12/6 = 30 expected cases (46 is historical whole-package context only), seven-file whitelist, and UUID evidence behavior are stated here. Review the exact helper signatures and source path scope before approving implementation.

## Full test-file source for the approved plan

The short examples earlier are explanatory excerpts only. The blocks below are the complete source to create in the two new test paths. They each define exactly 12 test functions; no additional parametrized cases.

### tests/test_shared_reservation.py

```python
from dataclasses import FrozenInstanceError
import pytest
from sc11_transfer.models import TransferDemand
from sc11_transfer.principles import Principle
from sc11_transfer.routing import build_shared_reservation_draft

KEYS = ("p1", "p2", "p3", "p4")

def demand(qty=6.0):
    return TransferDemand("M1", "OUT", qty, "2026-10-10", "P1")

def make_principles(score):
    return {
        key: Principle(key, key, lambda candidate, key=key: score(candidate.from_warehouse, key))
        for key in KEYS
    }

def run(demands, stock, *, order=None, ties=None, score=None):
    score_fn = score or (lambda warehouse, key: 0.0)
    return build_shared_reservation_draft(
        demands, stock, make_principles(score_fn), KEYS,
        scenario_order=order if order is not None else tuple(range(len(demands))),
        scenario_candidate_order=ties or {}, inventory_snapshot_id="snap-1",
    )

def test_c06_six_stock_reserves_four_then_four_is_unmet():
    result = run([demand(4), demand(4)], {"SRC": {"M1": 6.0}})
    assert [r.status for r in result.rows] == ["provisionally_reserved", "unmet"]
    assert [r.reserved_qty for r in result.rows] == [4.0, 0.0]
    assert result.rows[1].arithmetic_shortage == 2.0
    assert result.remaining_stock == (("snap-1", "SRC", "M1", 2.0),)

def test_c06_reverse_order():
    result = run([demand(4), demand(4)], {"SRC": {"M1": 6.0}}, order=(1, 0))
    assert [r.demand_index for r in result.rows] == [1, 0]
    assert [r.status for r in result.rows] == ["provisionally_reserved", "unmet"]
    assert [r.reserved_qty for r in result.rows] == [4.0, 0.0]
    assert result.rows[1].arithmetic_shortage == 2.0
    assert result.remaining_stock == (("snap-1", "SRC", "M1", 2.0),)

def test_no_partial_split():
    result = run([demand(6)], {"A": {"M1": 4.0}, "B": {"M1": 2.0}})
    assert result.rows[0].status == "unmet"
    assert result.rows[0].from_warehouse is None
    assert result.rows[0].reserved_qty == 0.0
    assert sum(row[3] for row in result.remaining_stock) == 6.0

def test_shortage_is_separate_from_unmet():
    result = run([demand(6)], {"A": {"M1": 4.0}})
    assert result.rows[0].status == "unmet"
    assert result.rows[0].arithmetic_shortage == 2.0
    assert result.remaining_stock == (("snap-1", "A", "M1", 4.0),)

def test_second_candidate_uses_shared_live_balance():
    score = lambda warehouse, key: 0.0 if warehouse == "A" else 1.0
    result = run([demand(6), demand(6)], {"A": {"M1": 6.0}, "B": {"M1": 6.0}}, score=score)
    assert [r.from_warehouse for r in result.rows] == ["A", "B"]
    assert [r.status for r in result.rows] == ["provisionally_reserved"] * 2
    assert result.remaining_stock == (("snap-1", "A", "M1", 0.0),
                                      ("snap-1", "B", "M1", 0.0))

def test_frozen_output_does_not_retain_source_objects():
    stock = {"A": {"M1": 6.0}}
    demands = [demand()]
    result = run(demands, stock)
    stock["A"]["M1"] = 99.0
    demands.append(demand(1))
    assert result.remaining_stock == (("snap-1", "A", "M1", 0.0),)
    assert len(result.rows) == 1
    assert not hasattr(result.rows[0], "demand")
    assert not hasattr(result.rows[0], "candidate")
    with pytest.raises(FrozenInstanceError):
        result.rows[0].qty = 8.0

def test_non_permutation_order_rejected():
    with pytest.raises(ValueError, match="permutation"):
        run([demand(), demand(2)], {"A": {"M1": 8.0}}, order=(0, 0))

def test_all_missing_scores_are_unranked():
    missing = {key: (lambda candidate: None) for key in KEYS}
    principles = {key: Principle(key, key, missing[key]) for key in KEYS}
    result = build_shared_reservation_draft(
        [demand()], {"A": {"M1": 6.0}}, principles, KEYS,
        scenario_order=(0,), scenario_candidate_order={}, inventory_snapshot_id="snap-1",
    )
    assert result.rows[0].status == "unranked"

def test_complete_equal_score_requires_explicit_tie_order():
    equal = lambda warehouse, key: 1.0
    unresolved = run([demand()], {"A": {"M1": 6.0}, "B": {"M1": 6.0}}, score=equal)
    selected = run([demand()], {"A": {"M1": 6.0}, "B": {"M1": 6.0}},
                   ties={0: ("B", "A")}, score=equal)
    assert unresolved.rows[0].status == "unranked"
    assert selected.rows[0].from_warehouse == "B"

def test_tie_order_cannot_override_different_scores():
    score = lambda warehouse, key: 0.0 if warehouse == "A" else 1.0
    result = run([demand()], {"A": {"M1": 6.0}, "B": {"M1": 6.0}},
                 ties={0: ("B", "A")}, score=score)
    assert result.rows[0].from_warehouse == "A"

def test_partial_or_duplicate_tie_order_is_unranked():
    equal = lambda warehouse, key: 0.0
    partial = run([demand()], {"A": {"M1": 6.0}, "B": {"M1": 6.0}},
                  ties={0: ("A",)}, score=equal)
    duplicate = run([demand()], {"A": {"M1": 6.0}, "B": {"M1": 6.0}},
                    ties={0: ("A", "A")}, score=equal)
    assert partial.rows[0].status == "unranked"
    assert duplicate.rows[0].status == "unranked"

def test_missing_component_in_best_equal_tuple_is_unranked():
    def score(warehouse, key):
        return None if key == "p4" else 0.0
    result = run([demand()], {"A": {"M1": 6.0}, "B": {"M1": 6.0}},
                 ties={0: ("A", "B")}, score=score)
    assert result.rows[0].status == "unranked"
```

### tests/test_versioned_audit_gate.py

```python
import hashlib
import json
from uuid import uuid4
import pytest
from zhuopin_platform.audit import AuditLogger
from sc11_transfer.agent import run_versioned_draft, revise_versioned_draft
from sc11_transfer.gate import (
    NotWiredYet, PmcApprovalRequired, commit_to_erp, confirm_versioned_draft,
    notify_outsourced_warehouse, refuse_versioned_draft,
)
from sc11_transfer.models import (
    TransferDemand, TransferPlanDraft, Warehouse, WarehouseKind,
)

PRIORITY = (
    "fewest_cross_warehouse", "prefer_material_warehouse",
    "shared_material_by_line_date", "nearest_between_outsourced",
)

def inputs():
    return (
        [TransferDemand("M1", "OUT", 6.0, "2026-10-10", "P1")],
        {"MAT": {"M1": 8.0}},
        [Warehouse("MAT", "material", WarehouseKind.MATERIAL),
         Warehouse("OUT", "outsourced", WarehouseKind.OUTSOURCED)],
        {("MAT", "OUT"): 1.0},
    )

def create(tmp_path, audit=None, **changes):
    options = {
        "draft_id": f"D-{uuid4().hex}",
        "inventory_snapshot_id": "S1",
        "inventory_version": "V1",
        "inventory_as_of": "2026-10-10T00:00:00+08:00",
        "source_refs": {"plans": "mock:p1", "stock": "mock:s1", "distances": "mock:d1"},
        "scenario_order": (0,),
        "scenario_candidate_order": {},
        "evaluator": "fixture",
        "audit": audit if audit is not None else AuditLogger.jsonl(tmp_path / f"events-{uuid4().hex}.jsonl"),
    }
    options.update(changes)
    return run_versioned_draft(*inputs(), PRIORITY, **options)

def test_hash_capture_survives_source_mutation(tmp_path):
    demands, stock, warehouses, distances = inputs()
    draft = run_versioned_draft(
        demands, stock, warehouses, distances, PRIORITY, draft_id=f"D-{uuid4().hex}",
        inventory_snapshot_id="S1", inventory_version="V1",
        inventory_as_of="2026-10-10T00:00:00+08:00",
        source_refs={"plans": "p1", "stock": "s1", "distances": "d1"},
        scenario_order=(0,), scenario_candidate_order={}, evaluator="fixture",
        audit=AuditLogger.jsonl(tmp_path / "hash.jsonl"),
    )
    captured = draft.revision.content_json
    digest = draft.revision.content_hash
    stock["MAT"]["M1"] = 99.0
    distances[("MAT", "OUT")] = 50.0
    demands.append(TransferDemand("M2", "OUT", 1.0, "2026-10-11"))
    assert draft.revision.content_json == captured
    assert hashlib.sha256(captured.encode("utf-8")).hexdigest() == digest
    assert json.loads(captured)["initial_stock"][0]["qty"] == 8.0

def test_source_snapshot_version_and_asof_change_hash(tmp_path):
    def payload_and_identity_neutral_hash(draft):
        payload = json.loads(draft.revision.content_json)
        assert hashlib.sha256(draft.revision.content_json.encode("utf-8")).hexdigest() == draft.revision.content_hash
        comparable = {key: value for key, value in payload.items() if key != "draft_id"}
        encoded = json.dumps(comparable, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        return payload, hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    base_payload, baseline = payload_and_identity_neutral_hash(create(tmp_path))
    assert base_payload["inventory"] == {
        "snapshot_id": "S1", "version": "V1", "as_of": "2026-10-10T00:00:00+08:00",
    }
    for option, field, value in (
        ("inventory_snapshot_id", "snapshot_id", "S2"),
        ("inventory_version", "version", "V2"),
        ("inventory_as_of", "as_of", "2026-10-11"),
    ):
        payload, digest = payload_and_identity_neutral_hash(create(tmp_path, **{option: value}))
        assert payload["inventory"] == {**base_payload["inventory"], field: value}
        assert digest != baseline
    refs = {"plans": "p2", "stock": "mock:s1", "distances": "mock:d1"}
    payload, digest = payload_and_identity_neutral_hash(create(tmp_path, source_refs=refs))
    assert payload["source_refs"] == refs
    assert digest != baseline

def test_revision_is_new_and_does_not_migrate_approval(tmp_path):
    audit = AuditLogger.jsonl(tmp_path / "revision.jsonl")
    first = create(tmp_path, audit=audit)
    confirmed = confirm_versioned_draft(first, "PMC A", evaluator="reviewer", audit=audit)
    revised = revise_versioned_draft(
        confirmed, *inputs(), PRIORITY, inventory_snapshot_id="S2", inventory_version="V2",
        inventory_as_of="2026-10-11",
        source_refs={"plans": "p2", "stock": "s2", "distances": "d2"},
        scenario_order=(0,), scenario_candidate_order={}, evaluator="fixture", audit=audit,
    )
    assert revised.revision.draft_id == first.revision.draft_id
    assert revised.revision.revision == 2
    assert revised.approval is None
    assert confirmed.approval.outcome == "confirmed"
    with pytest.raises(PmcApprovalRequired, match="current audited revision"):
        commit_to_erp(confirmed)
    with pytest.raises(PmcApprovalRequired):
        commit_to_erp(revised)

def test_create_confirm_refuse_revise_jsonl_and_chain(tmp_path):
    path = tmp_path / "lifecycle.jsonl"
    audit = AuditLogger.jsonl(path)
    draft = create(tmp_path, audit=audit)
    confirmed = confirm_versioned_draft(draft, "PMC A", evaluator="reviewer", audit=audit)
    refused = refuse_versioned_draft(draft, "PMC B", "correct", evaluator="reviewer", audit=audit)
    with pytest.raises(PmcApprovalRequired, match="absent or refused"):
        commit_to_erp(confirmed)
    revised = revise_versioned_draft(
        confirmed, *inputs(), PRIORITY, inventory_snapshot_id="S2", inventory_version="V2",
        inventory_as_of="2026-10-11",
        source_refs={"plans": "p2", "stock": "s2", "distances": "d2"},
        scenario_order=(0,), scenario_candidate_order={}, evaluator="fixture", audit=audit,
    )
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [event["action"] for event in events] == [
        "transfer_plan_create", "transfer_plan_confirm",
        "transfer_plan_refuse", "transfer_plan_revise",
    ]
    assert events[0]["content_hash"] == draft.revision.content_hash
    assert events[1]["decision"]["content_hash"] == confirmed.revision.content_hash
    assert events[2]["decision"]["outcome"] == "refused"
    assert events[3]["decision"]["revision"] == revised.revision.revision == 2
    verified = audit.verify_chain()
    assert verified.ok
    assert verified.total == 4

def test_create_audit_failure_returns_no_draft(tmp_path):
    blocked_path = tmp_path / "blocked.jsonl"
    blocked_path.mkdir()
    audit = AuditLogger.jsonl(blocked_path)
    with pytest.raises(OSError):
        create(tmp_path, audit=audit)

def test_confirm_audit_failure_returns_no_confirmation(tmp_path, monkeypatch):
    audit = AuditLogger.jsonl(tmp_path / "confirm-fail.jsonl")
    draft = create(tmp_path, audit=audit)
    before = audit.sink.log_path.read_bytes()
    monkeypatch.setattr(audit.sink, "write", lambda event: (_ for _ in ()).throw(OSError("sink unavailable")))
    with pytest.raises(OSError):
        confirm_versioned_draft(draft, "PMC A", evaluator="reviewer", audit=audit)
    assert draft.approval is None
    assert audit.sink.log_path.read_bytes() == before

def test_refuse_audit_failure_returns_no_refusal(tmp_path, monkeypatch):
    audit = AuditLogger.jsonl(tmp_path / "refuse-fail.jsonl")
    draft = create(tmp_path, audit=audit)
    before = audit.sink.log_path.read_bytes()
    monkeypatch.setattr(audit.sink, "write", lambda event: (_ for _ in ()).throw(OSError("sink unavailable")))
    with pytest.raises(OSError):
        refuse_versioned_draft(draft, "PMC A", "correct", evaluator="reviewer", audit=audit)
    assert draft.approval is None
    assert audit.sink.log_path.read_bytes() == before

def test_revise_audit_failure_returns_no_revision(tmp_path, monkeypatch):
    audit = AuditLogger.jsonl(tmp_path / "revise-fail.jsonl")
    draft = create(tmp_path, audit=audit)
    before = audit.sink.log_path.read_bytes()
    monkeypatch.setattr(audit.sink, "write", lambda event: (_ for _ in ()).throw(OSError("sink unavailable")))
    with pytest.raises(OSError):
        revise_versioned_draft(
            draft, *inputs(), PRIORITY, inventory_snapshot_id="S2", inventory_version="V2",
            inventory_as_of="2026-10-11",
            source_refs={"plans": "p2", "stock": "s2", "distances": "d2"},
            scenario_order=(0,), scenario_candidate_order={}, evaluator="fixture", audit=audit,
        )
    assert draft.revision.revision == 1
    assert audit.sink.log_path.read_bytes() == before

def test_actor_and_refusal_reason_and_invalid_boundaries_rejected(tmp_path):
    audit = AuditLogger.jsonl(tmp_path / "actors.jsonl")
    draft = create(tmp_path, audit=audit)
    with pytest.raises(ValueError):
        confirm_versioned_draft(draft, " ", evaluator="reviewer", audit=audit)
    with pytest.raises(ValueError):
        refuse_versioned_draft(draft, "PMC A", " ", evaluator="reviewer", audit=audit)
    from sc11_transfer.models import AllocationRow
    from sc11_transfer.principles import Principle
    from sc11_transfer.routing import build_shared_reservation_draft
    with pytest.raises(ValueError, match="demand_index"):
        AllocationRow(True, "M1", "OUT", 1.0, "2026-10-10", "P1",
                      "provisionally_reserved", "MAT", 1.0, 0.0, ())
    with pytest.raises(ValueError, match="finite number"):
        AllocationRow(0, "M1", "OUT", True, "2026-10-10", "P1",
                      "provisionally_reserved", "MAT", 1.0, 0.0, ())
    bool_demand = TransferDemand("M1", "OUT", True, "2026-10-10", "P1")
    principles = {key: Principle(key, key, lambda candidate: 0.0) for key in PRIORITY}
    with pytest.raises(ValueError, match="bool"):
        build_shared_reservation_draft(
            [bool_demand], {"MAT": {"M1": 1.0}}, principles, PRIORITY,
            scenario_order=(0,), scenario_candidate_order={}, inventory_snapshot_id="S1",
        )
    with pytest.raises(ValueError, match="bool"):
        build_shared_reservation_draft(
            inputs()[0], {"MAT": {"M1": 8.0}}, principles, PRIORITY,
            scenario_order=(True,), scenario_candidate_order={}, inventory_snapshot_id="S1",
        )
    duplicate_priority = PRIORITY[:3] + (PRIORITY[2],)
    with pytest.raises(ValueError, match="four principle keys"):
        build_shared_reservation_draft(
            inputs()[0], {"MAT": {"M1": 8.0}}, principles, duplicate_priority,
            scenario_order=(0,), scenario_candidate_order={}, inventory_snapshot_id="S1",
        )

def test_refused_or_legacy_draft_cannot_execute(tmp_path):
    audit = AuditLogger.jsonl(tmp_path / "legacy.jsonl")
    refused = refuse_versioned_draft(
        create(tmp_path, audit=audit), "PMC A", "correct", evaluator="reviewer", audit=audit,
    )
    legacy = TransferPlanDraft(approved_by="historical PMC", approved_at="historical time")
    with pytest.raises(PmcApprovalRequired):
        commit_to_erp(refused)
    with pytest.raises(PmcApprovalRequired, match="legacy approved_by"):
        commit_to_erp(legacy)
    with pytest.raises(PmcApprovalRequired, match="legacy approved_by"):
        notify_outsourced_warehouse(legacy)

def test_exact_confirmation_still_hits_unwired_channels(tmp_path):
    audit = AuditLogger.jsonl(tmp_path / "channels.jsonl")
    confirmed = confirm_versioned_draft(
        create(tmp_path, audit=audit), "PMC A", evaluator="reviewer", audit=audit,
    )
    with pytest.raises(NotWiredYet):
        commit_to_erp(confirmed)
    with pytest.raises(NotWiredYet, match="separate authorization"):
        notify_outsourced_warehouse(confirmed)

def test_content_tamper_fails_closed(tmp_path):
    from dataclasses import replace
    from datetime import datetime, timezone
    from sc11_transfer.models import ApprovalRecord, VersionedTransferPlanDraft
    unaudited = create(tmp_path)
    forged = VersionedTransferPlanDraft(unaudited.revision, ApprovalRecord(
        unaudited.revision.draft_id, unaudited.revision.revision,
        unaudited.revision.content_hash, "PMC A", "confirmed",
        datetime.now(tz=timezone.utc).isoformat(),
    ))
    with pytest.raises(PmcApprovalRequired, match="absent or refused"):
        commit_to_erp(forged)
    audit = AuditLogger.jsonl(tmp_path / "tamper.jsonl")
    confirmed = confirm_versioned_draft(
        create(tmp_path, audit=audit), "PMC A", evaluator="reviewer", audit=audit,
    )
    corrupted = type(confirmed)(replace(confirmed.revision, content_json="{}"), confirmed.approval)
    with pytest.raises(PmcApprovalRequired):
        commit_to_erp(corrupted)
```

This second module contains 12 cases. Existing test_pmc_gate.py retains 6; alter only the legacy approved_by expectation to PmcApprovalRequired.


