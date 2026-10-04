# #658 入口参数契约 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 本项目执行方法已定为正式 Guardian 隔离工作树；所有派生任务显式 `gpt-6-luna`。本次仅编计划，等待 Shao Peishen 另审。

**Goal:** 新获批 Workflow/Guardian 按阶段传递、封存获批 effort，保留历史批次恢复语义，并如实区分声明、命令与实际观测。

**Architecture:** 在既有 workflow_state 中集中校验严格契约与切换清单；driver 在 attempt 锁内封存并在 runner 前重核。provider 只负责可选参数的精确 argv 传递及原生证据边界，Guardian v3 把每项契约摘要加入原有计划指纹。历史任务依据明确封存清单识别，不能以缺少新字段作为旧任务判据。

**Tech Stack:** Python 3.14、stdlib、pytest；既有 Codex CLI/App Server、OpenSpec spec-driven；不新增依赖、模块、hook、CLI consumer、CI 配置或调度。

**Spec:** 原工作树 `C:/Users/Paul Shao/.codex/worktrees/reasoning-entry-design-1004/zhuopin-ai/openspec/changes/reasoning-entry-policy-658/` 下 proposal/design/specs/reasoning-entry-policy/spec/tasks；与 `C:/Dev/zhuopin-ai/0-学习与工具/codex-handoff/入口参数658-设计审阅表-2026-10-04.md` **共同解释**。A 审阅表决定 actual 缺证仅阻止实际强度符合性声明，不阻止其它已获批阶段产物闸。

## Global Constraints

- 模型固定 `gpt-6-luna`；proposal=`medium`、implement=`high`、review=`high`；test/release 不启动新模型，不选择 effort。
- `schema`=`zhuopin.reasoning-contract/v1`；三 phase 完整映射；canonical UTF-8 JSON：sorted keys、compact separators、ensure_ascii=False；摘要排除 `contract_sha256`。
- 新任务缺失/非法/未知/漂移契约在 provider 前停止；provider 参数错误在 Popen 前停止；不降档、不换模型、不以 TypeError 重试弱接口。
- `actual_effort=null`、`observation_status=unavailable` 是当前公开接口下的准确结果；argv、主机配置、thread/read 当前配置、prompt 和私有 rollout 均不能作为逐轮实际 effort。
- 历史 v1/v2 保持原算法与文件；不注入新 effort、不原位升级。新计划 fingerprint v3。
- 保留 Luna、sandbox、mutex、timeout/context、批准与 HEAD、隔离工作树、结构/CI/review/发布人工闸；delivery_accepted 不因参数正确变 true。
- 本计划未执行代码/测试/ff/生产/发送；#634 仍等入口依赖实际闭合。本次 1a 批准只能进入计划。

## Review Focus

1. 新 prepare 若遗漏契约，不能因“没有版本字段”静默降为 legacy；Task 2/4/6 各有负例。
2. argv_override、重复 `-c`、resume thread 或内嵌换模型参数不能绕过声明；Task 3 测试最终 argv 和零 Popen。
3. 同一批准文件格式变化、同批改映射、键顺序变化分别区分字节漂移和 canonical 相等；Task 1/5/6 测试。
4. 新 attempt/turn 的实际观测必须清空；线程配置和旧轮值不能冒充当前执行；Task 3/4 测试。
5. 历史 v1/v2 既要能原样恢复，又不能给新 task/新 batch 开缺契约入口；Task 2/5/6 测试固定历史摘要和新身份拒绝。

---

## 批准、基线与文件职责

记录日期 2026-10-05；编制 Native OP-1002-Z。设计 HEAD=`606c3bd498bf57b2ed2f9cd8d3f5773ce7d6e869`；本次只读核查源码 HEAD=`7f0806a58ecd19c76a6cad9a418a5693a2d4e818`。正式实施前核对两者差异，只处理已审白名单，不把当前 master 文档提交当实现。

| 批准/证据 | SHA256 |
|---|---|
| 原 design.md | `97d010a5945b3f7d72bae5dd746b8e5ab702355aa295ff5498054639d41d4bd4` |
| A 设计审阅表 | `5832d1239e676720f8bed9bf4198c4dc5142d7a3cff48879dc1bfdd27c2c44ff` |
| 本轮人答原文 human-approval.txt | `9c2aee2cbd84a65546be9926a2b7a0169ceb3921a5125fbfc7c9be2d6c4a6f84` |
| 仅编计划 design-658-plan-only.json | `7d5fffcb79fd9db4fa41e168ee0afb73098f63ae7ba84ffd736f7a90a05e7fee` |
| 合法 YAML 候选 | `ad734da2ba5f4c5a6979a8bbb6bad4db20fb21ec275ceca5f24842fbdfaf5bef` |

批准证据位于 `C:/Dev/Codex/runtimes/zhuopin-ai/approvals/1005-entry-plan-material-revision/`；plan-only JSON **不能**传给 implement 作为真实实现批准。

下表前十项均相对实施工作树 `0-学习与工具/codex-handoff/`；不在主仓执行这些修改。

| 文件 | 职责 | 当前接缝 |
|---|---|---|
| workflow_state.py | 严格 schema/canonical、批准文件引用、切换清单、attempt 封存/恢复核对 | load_state；begin_attempt 的 prepare callback 在锁内先于新 attempt |
| model_provider.py | 可选二参数、精确 argv、request/result 新字段、当前观测 unavailable | command:70；run:269；main:422；最终 argv_override 后、Popen 前再核 |
| workflow_driver.py | 外部批准载入、锁内契约封存、逐阶段 runner 前重核、结果审计 | collect_evidence；_run_model:422；advance:1310 prepare_attempt |
| guardian_adapter.py | v3 fingerprint、batch 绑定、逐次 dispatch 核对 | _plan_sha256:84；plan_batch:138；_advance_task:279 |
| guardian_entry.py | manifest 契约引用、旧批恢复判别、新计划公开发布/claims 前校验 | _execution_bindings:120；_assert_plan_sources:305；start:511 |
| tests/test_workflow_state.py | schema、状态与切换 fixture | load_state_module / prepared 已存在 |
| tests/test_model_provider.py | 捕获 argv、Popen 零调用、legacy、无观测推断 | provider() / TestProvider 已存在 |
| tests/test_workflow_driver.py | 三阶段 fake runner、漂移、resume、原保护 | fixture 返回 driver/repo/folder 已存在 |
| tests/test_guardian_adapter.py | v1/v2 golden、v3摘要、同批漂移 | load() / rows() 已存在 |
| tests/test_guardian_entry.py | 新 manifest 与 legacy registry 恢复、未授权零派发 | load()/candidate()/manifest()/executor() 已存在 |
| openspec/changes/reasoning-entry-policy-658/.openspec.yaml | 原 Markdown 元数据改为合法两行 YAML | 原封存包不原地改；在真正获批实现 HEAD 改 |

新增运行证据在既有外部 STATE：`reasoning-policy/activation.json` 和新 attempt 证据；不是源码白名单外模块或全局 Codex 设置。原 task/state/plan 不批量改写。首次 activation 由正式实施 review 后单独展示真实历史清单与人答引用，再授权切换；本计划不授权现在写 activation。

**首次建造的启动限制：** #658 本身已经是封存 v2 设计批。获具体实现批准后沿既有 task/batch/workspace 进入 implement，不改绑定、不将它升级 v3；原 design commit 可追溯保留，正常 implement 产生新 HEAD。当前旧入口没有阶段 effort 参数，不能声称首次建造/历史 review 已按新映射执行。新机制的三阶段参数功能在隔离 fixture 和有限 native probe验证，真正新 v3 任务在 ff/切换另审后启用。这个限制必须写入具体实现授权候选；不通过改 globalconfig或prompt假装已绑定high。

## 统一接口与 JSON 接缝

### 外部输入，消除自引用摘要

使用三个已获批、位于主仓和全部模型工作树之外的普通文件：

1. genuine human 原文 + SHA 引用；不能让子模型生成批准。
2. policy/task approval：`schema=zhuopin.reasoning-approval/v1`、`task_id`、`workspace`、`source_head`、`policy_id`、固定 model_route、完整 phase_effort、human_approval_ref。包含任务/阶段值与用户来源，**不含 contract SHA**。
3. ReasoningContractV1：approval_ref.source 指向第 2 件、approval_ref.sha256 是其字节 SHA；contract 自身再计算 canonical SHA。task intent approval 增加 `reasoning_contract_ref={path,sha256}` 指向第 3 件，并由既有 intent_approval_ref 字节封存。

driver 从现有封存 intent_approval_ref 读取这个可选附加字段；既有 prepare/CLI 不需要新增参数或源码修改。真实 prepare 集成 fixture 必须证明引用存取没有丢失。禁止把同一文件的完整 SHA 嵌回自身，禁止手工改运行 state 来补批准。

### 新接口（均在上述五个模块内）

| 模块 | 函数签名索引（下文任务实现） |
|---|---|
| state | `canonical_reasoning_sha256(contract: dict) -> str`；`validate_reasoning_contract(contract: dict) -> dict` |
| state | `verified_reasoning_reference(ref: dict, *, workspace: Path, source_checkout: Path) -> tuple[dict, dict]` |
| state | `activate_reasoning_policy(approval_ref: dict, legacy_tasks: dict, legacy_plans: dict) -> dict` |
| state | `reasoning_entry_kind(current: dict, *, activation: dict) -> str`；`seal_reasoning_contract(current: dict, contract: dict, proof: dict) -> None` |
| state | `bind_reasoning_attempt(current: dict, attempt: dict, *, workspace: Path, resume_thread: str \| None) -> dict \| None` |
| provider | `command(executable, workspace, final, sandbox, *, thread=None, model=None, reasoning_effort=None, reasoning_contract_sha256=None)` |
| provider | `reasoning_request(argv: list[str], *, model: str \| None, reasoning_effort: str \| None, reasoning_contract_sha256: str \| None) -> dict` |
| provider | `reasoning_observation(result: dict, *, request: dict) -> dict`；`verify_reasoning_support(ref: dict, executable: Path, *, workspace: Path) -> dict` |
| provider | `run` 在原 kwargs 后增加 `reasoning_effort=None, reasoning_contract_sha256=None, reasoning_support_ref=None`；CLI 增加 bounded effort/hash/support-ref 三项 |
| driver | `_reasoning_context(task_id: str, phase: str, workspace: Path, attempt: dict, resume_thread: str \| None) -> dict \| None` |
| adapter | `_plan_sha256(plan: dict) -> str`；`plan_batch` 原kwargs后增加 `fingerprint_version=3`；`validate_reasoning_plan(plan: dict, batch_record: dict \| None, task_states: dict) -> None` |
| entry | `_reasoning_bindings(manifest: dict, plan: dict) -> dict`；`_historical_plan_version(record: Path, manifest: dict, activation: dict) -> int` |

这里的签名索引用于跨任务对齐；下列任务给出实际实现与 fixture。`verified_reasoning_reference` 返回 `(contract, proof)`，proof={contract_file_ref, approval_file_ref,human_approval_ref,support_ref}。此函数校验 schema/文件与相互映射；task_id/source_head/workspace 三个字段由 driver/entry 对当前 task 重核。`reasoning_entry_kind` 仅返回 governed/legacy；缺 activation 或历史身份不一致抛 ValueError，不回退。

policy/task approval 另含 `support_ref={path,sha256}`，引用外部受控 `zhuopin.reasoning-support/v1` 文件；该支持文件封存 executable绝对路径/bytesSHA、version原文ref、model/list原文ref、model_id、已批medium/high、官方URL、publicschemaSHA及 `per_turn_effort_available=false`。人答批准链覆盖该support_ref；不得让模型填一份自称“supported”的对象。support更换需新批准与契约，不静默更新旧proof。

| JSON path | 精确语义 |
|---|---|
| state.reasoning_contract / reasoning_contract_sha256 / reasoning_approval_ref | 仅新 governed task 在锁内首次封存；再次读取逐项相等 |
| state.reasoning_contract_ref / reasoning_human_approval_ref / reasoning_support_ref | 外部原文件字节引用，逐阶段再验；不是 prompt 自陈 |
| attempts[-1].reasoning | contract_sha256、phase、declared_effort、approval_sha256、model_route、workspace、resume_thread、attempt_id |
| attempts[-1].reasoning_evidence | request_ref/result_ref/native_ref、provider_argv_sha256、thread_id、turn_id；来自实际外层产物 |
| request.json.reasoning | contract_sha256、declared_effort、command_effort、argv_sha256；每次最终 argv 后计算 |
| result.json.reasoning | 同请求三项＋actual_effort=null、observation_status、conformance_status=unverified、native_evidence_ref |
| plan.reasoning_contract_bindings[task_id] | contract_sha256、contract_ref、approval_ref、workspace；覆盖该新计划 dispatchable IDs |
| plan.plan_fingerprint_version | 新计划 3；原有 1/2 原样计算 |
| activation.legacy_tasks / legacy_plans | 审阅过的 immutable 身份和旧 plan 指纹；不以缺字段/时间戳推断 legacy |

actual unavailable 时普通产物依原闸；conflict 或身份漂移则接受失败。不得把 conformance_status=unverified 写成整体 delivery accepted。

### 未来执行通用命令

下列命令均在**获批后**使用；本次没有运行 pytest。工作树变量从正式 Guardian binding 取得，绝不猜路径。所有路径加引号。

```powershell
$entryWorkspace = (Get-Content -LiteralPath $approvedBindingPath -Raw | ConvertFrom-Json).workspace
$entryPython = 'C:\Dev\Codex\runtimes\zhuopin-ai\venv\Scripts\python.exe'
Set-Location -LiteralPath (Join-Path $entryWorkspace '0-学习与工具/codex-handoff')
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
```

任务内的 node-id 运行用 `$entryPython`，cwd 如上；每 task 先红后绿，记录实际结果，不能预填 passed。提交仅隔离树内本 task 白名单，外层先审 path diff 再提交；不自行在 master commit/ff。

---

## Task 1：合法元数据、严格契约和外部批准引用

**Files:** Modify workflow_state.py；Test tests/test_workflow_state.py；Modify 本任务 .openspec.yaml。

**Interfaces:** Produces canonical_reasoning_sha256 / validate_reasoning_contract / verified_reasoning_reference；外部 proof 与 phase 映射供 Task 2/4/6 使用。

- [ ] **Step 1：添加以下拟新增 fixture 和严格 schema 测试。** 放入现有 state 测试文件，不新建 conftest。

```python
import copy

def reasoning_contract_fixture(state):
    value = {'schema': 'zhuopin.reasoning-contract/v1',
             'policy_id': 'entry-658-A-v1',
             'phase_effort': {'proposal': 'medium', 'implement': 'high', 'review': 'high'},
             'model_route': 'gpt-6-luna',
             'approval_ref': {'source': 'C:/outside/approval.json', 'sha256': 'a' * 64}}
    value['contract_sha256'] = state.canonical_reasoning_sha256(value)
    return value

def test_reasoning_contract_canonical_and_phase_mapping():
    state = load_state_module()
    contract = reasoning_contract_fixture(state)
    shuffled = dict(reversed(list(contract.items())))
    assert state.canonical_reasoning_sha256(contract) == state.canonical_reasoning_sha256(shuffled)
    assert state.validate_reasoning_contract(shuffled) == contract

@pytest.mark.parametrize('mutation', [
    lambda c: c['phase_effort'].pop('review'),
    lambda c: c['phase_effort'].update(test='high'),
    lambda c: c['phase_effort'].update(implement='max'),
    lambda c: c.update(extra=True),
    lambda c: c.update(schema='zhuopin.reasoning-contract/v2'),
    lambda c: c.update(model_route='gpt-6-astra'),
    lambda c: c['approval_ref'].update(sha256='A' * 64),
    lambda c: c['approval_ref'].update(extra=True),
    lambda c: c.update(policy_id=''),
    lambda c: c.update(contract_sha256='0' * 64),
])
def test_reasoning_contract_invalid_fails_closed(mutation):
    state = load_state_module()
    contract = reasoning_contract_fixture(state)
    mutation(contract)
    with pytest.raises(ValueError, match='reasoning_policy_invalid|reasoning_binding_drift'):
        state.validate_reasoning_contract(contract)
```

- [ ] **Step 2：红测。** Run `& $entryPython -m pytest 'tests/test_workflow_state.py::test_reasoning_contract_canonical_and_phase_mapping' 'tests/test_workflow_state.py::test_reasoning_contract_invalid_fails_closed' -q`。预期当前缺新函数失败；记录真实错误。
- [ ] **Step 3：实现 strict schema，保留现有 imports 与 state 保护。** 核心可直接采用：

```python
def canonical_reasoning_sha256(contract):
    payload = {k: v for k, v in contract.items() if k != 'contract_sha256'}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode('utf8')).hexdigest()

def validate_reasoning_contract(contract):
    keys = {'schema', 'policy_id', 'phase_effort', 'model_route',
            'approval_ref', 'contract_sha256'}
    invalid = 'reasoning_policy_invalid'
    if not isinstance(contract, dict) or set(contract) != keys:
        raise ValueError(invalid)
    if (contract['schema'] != 'zhuopin.reasoning-contract/v1'
            or not isinstance(contract['policy_id'], str) or not contract['policy_id'].strip()
            or contract['model_route'] != 'gpt-6-luna'):
        raise ValueError(invalid)
    phase = contract['phase_effort']
    if not isinstance(phase, dict) or phase != {'proposal': 'medium', 'implement': 'high', 'review': 'high'}:
        raise ValueError(invalid)
    proof = contract['approval_ref']
    if (not isinstance(proof, dict) or set(proof) != {'source', 'sha256'}
            or not isinstance(proof['source'], str) or not proof['source'].strip()
            or not isinstance(proof['sha256'], str)
            or not re.fullmatch(r'[a-f0-9]{64}', proof['sha256'])):
        raise ValueError(invalid)
    digest = contract['contract_sha256']
    if not isinstance(digest, str) or not re.fullmatch(r'[a-f0-9]{64}', digest):
        raise ValueError(invalid)
    if digest != canonical_reasoning_sha256(contract):
        raise ValueError('reasoning_binding_drift')
    return json.loads(json.dumps(contract))
```

`verified_reasoning_reference` 的实际读取核验实现如下；复用当前 `_read_regular/_safe_parent` 无 reparse/多硬链、前后 identity 方法。受控 approval 根由部署 runtime 指定并在外层启动时核实，不接受模型更改；示例 helper接收该已核根，不能根据任意ref自己推导可信根。Task1同时导出内部`_reasoning_read_ref`给本模块其它校验调用。

```python
def _reasoning_read_ref(ref, *, authority_root, forbidden_roots):
    if (not isinstance(ref, dict) or set(ref) != {'path', 'sha256'}
            or not isinstance(ref['path'], str)
            or not isinstance(ref['sha256'], str)
            or not re.fullmatch(r'[a-f0-9]{64}', ref['sha256'])):
        raise ValueError('reasoning_binding_drift')
    path = Path(ref['path'])
    root = Path(authority_root).absolute()
    if (not path.is_absolute() or path.resolve() != path
            or not path.is_relative_to(root)
            or any(path.is_relative_to(Path(item).resolve()) for item in forbidden_roots)):
        raise ValueError('reasoning_binding_drift')
    try:
        raw, identity = _read_regular(path, root)
    except (OSError, ValueError):
        raise ValueError('reasoning_binding_drift') from None
    if hashlib.sha256(raw).hexdigest() != ref['sha256']:
        raise ValueError('reasoning_binding_drift')
    return raw
```

`verified_reasoning_reference`按顺序调用这个helper读contract、approval、human与support引用。contract交validate_reasoning_contract；approval schema/policy/model/phase 与contract相等，再核human/support原文件 bytes，返回task_id/source_head/workspace字段供driver/entry逐项比对。自由输入文件自陈不能代替真实外层人答链。

- [ ] **Step 4：补拟新增引用负例。** 以下代码可直接加入同一state测试文件；另对directory/reparse/multilink应用当前`_read_regular`负例夹具，错误仍binding_drift，原state bytes不变。

```python
@pytest.mark.parametrize('mode', ['drift', 'delete', 'workspace', 'directory'])
def test_reasoning_reference_drift_and_workspace_escape(tmp_path, mode):
    state = load_state_module()
    authority = tmp_path / 'authority'
    workspace = tmp_path / 'model'
    authority.mkdir()
    workspace.mkdir()
    path = authority / 'proof.json'
    path.write_bytes(b'{"text":"synthetic approval"}')
    ref = {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    assert state._reasoning_read_ref(ref, authority_root=authority,
                                    forbidden_roots=[workspace]) == path.read_bytes()
    if mode == 'drift':
        path.write_bytes(path.read_bytes() + b' ')
    elif mode == 'delete':
        path.unlink()
    elif mode == 'workspace':
        copied = workspace / 'proof.json'
        copied.write_bytes(path.read_bytes())
        ref['path'] = str(copied.resolve())
    else:
        path.unlink()
        path.mkdir()
    with pytest.raises(ValueError, match='reasoning_binding_drift'):
        state._reasoning_read_ref(ref, authority_root=authority, forbidden_roots=[workspace])
```
- [ ] **Step 5：元数据只写下面两行；通过真实 status 和 strict 结构检查。** 其它四件正文逐字节 SHA 保持原封存值。

```yaml
schema: spec-driven
created: 2026-10-04
```

Run from 工作树根：`openspec status --change reasoning-entry-policy-658 --json` 和 `openspec validate reasoning-entry-policy-658 --strict`；预期 exit0、schemaName spec-driven。这不是产品测试或已实现证明。
- [ ] **Step 6：绿测、外层提交。** Step 2 两节点及新引用节点全部通过，提交 `feat: seal approved reasoning contract schema`，仅本 task 三文件。

## Task 2：切换清单和 attempt 原子封存

**Files:** Modify workflow_state.py；Test tests/test_workflow_state.py。

**Interfaces:** Consumes Task 1 三函数；Produces activation、reasoning_entry_kind、seal_reasoning_contract、bind_reasoning_attempt。复用 begin_attempt(…,prepare=…) 锁，不另造并行状态写入口。

- [ ] **Step 1：拟新增判别负例。** 下面 fixture 的 activation 只在测试内存存在。

```python
def test_reasoning_new_task_cannot_become_legacy_by_omitting_fields():
    state = load_state_module()
    activation = {'schema': 'zhuopin.reasoning-activation/v1', 'legacy_tasks': {},
                  'legacy_plans': {}, 'policy_id': 'entry-658-A-v1'}
    current = {'id': 'new-task', 'reasoning_contract': None}
    assert state.reasoning_entry_kind(current, activation=activation) == 'governed'
    with pytest.raises(ValueError, match='reasoning_contract_missing'):
        state.bind_reasoning_attempt(current, {'id': 'a', 'phase': 'proposal'},
                                     workspace=Path('C:/model'), resume_thread=None)

def test_reasoning_attempt_resets_observation_and_seals_selection(tmp_path, monkeypatch):
    state = load_state_module()
    monkeypatch.setattr(state, 'STATE', tmp_path)
    folder = prepared(tmp_path)
    contract = reasoning_contract_fixture(state)
    current = state.load_state('sample')
    current.update(reasoning_contract=contract,
                   reasoning_contract_sha256=contract['contract_sha256'],
                   reasoning_entry_kind='governed', workspace=str(tmp_path.resolve()))
    current['reasoning_observation'] = {'actual_effort': 'high', 'observation_status': 'observed'}
    state._write_json(folder / 'state.json', current)
    attempt = state.begin_attempt('sample', 'proposal', 'abc',
        prepare=lambda locked: locked.update(reasoning_entry_kind='governed'))
    binding = state.bind_reasoning_attempt(state.load_state('sample'), attempt,
                                         workspace=tmp_path.resolve(), resume_thread=None)
    assert binding['declared_effort'] == 'medium'
    assert binding['attempt_id'] == attempt['id']
    assert state.load_state('sample')['reasoning_observation'] == {
        'actual_effort': None, 'observation_status': 'unavailable'}
```

- [ ] **Step 2：红测。** Run 两新节点。新状态字段出现并不构成合法 approval；引用漂移负例仍须通过 Task 1 的真实字节验证。
- [ ] **Step 3：实现历史身份判别和切换封存。** `activate_reasoning_policy` 仅外层调用；activation file 用 create-exclusive + recovery mutex，已有文件只读比对，不能 replace。approval_ref 指向独立切换批准，SHA 与 human 来源核实；legacy_tasks 是人审清单，包含每 task 的 id/created/source_head/source_git_common_dir/workspace/intent_approval_ref；legacy_plans 包含 batch_id/原 plan_ref 字节 SHA/原 `_plan_sha256`/version1或2。现时任何 busy/running.lock 拒绝切换，防运行中改配置。新 task 不在清单则 governed；清单内任一 immutable 字段不符则 binding_drift。不扫描/推断 task 时间先后，不改历史 state/plan。未部署 activation 的新入口停止并报告缺少切换批准，不能建空清单悄悄上线。

核心 attempt 字段选择代码：

```python
def bind_reasoning_attempt(current, attempt, *, workspace, resume_thread):
    if current.get('reasoning_entry_kind') == 'legacy':
        return None
    contract = current.get('reasoning_contract')
    if contract is None:
        raise ValueError('reasoning_contract_missing')
    checked = validate_reasoning_contract(contract)
    phase = attempt['phase']
    if phase not in checked['phase_effort']:
        raise ValueError('reasoning_policy_invalid')
    if current.get('reasoning_contract_sha256') != checked['contract_sha256']:
        raise ValueError('reasoning_binding_drift')
    if Path(current['workspace']).resolve() != Path(workspace).resolve():
        raise ValueError('reasoning_binding_drift')
    return {'attempt_id': attempt['id'], 'phase': phase,
            'contract_sha256': checked['contract_sha256'],
            'declared_effort': checked['phase_effort'][phase],
            'approval_sha256': checked['approval_ref']['sha256'],
            'model_route': checked['model_route'], 'workspace': str(Path(workspace).resolve()),
            'resume_thread': resume_thread}
```

`begin_attempt` 在 existing prepare callback 后构造 attempt；仅 governed model phase 填入上面 binding；清空 task observation 为 null/unavailable，再将 attempt+state 一次写盘。test phase 不调用 bind_reasoning_attempt。`seal_reasoning_contract` 初次写完整 contract/proof，已存在必须全文及摘要相同；case差异/批准bytes漂移不容忍。`reasoning_entry_kind`的每次legacy判定必须再核activation的外部批准链和清单immutable身份，不能相信state上自填的`reasoning_entry_kind=legacy`；bind函数只消费刚通过该核验的外层current，_reasoning_context再次独立判别。
- [ ] **Step 4：补拟新增 `test_reasoning_activation_is_once_and_has_no_legacy_mutation` 与 `test_reasoning_resume_identity_drift`。** 对同一批/task相同批准重复调用幂等；改批准、旧taskimmutable、thread、phase、workspace、model、digest各拒绝；对历史 state/plan 比 before/after bytes。resume 以先前真实 attempt 的 reasoning/request/session refs核验，不用新请求的 thread自证。
- [ ] **Step 5：绿测与提交。** Run 新节点、既有 `test_duplicate_attempt_does_not_replace_first`、`test_unknown_crash_keeps_lock_and_evidence`、`test_recover_rejects_forged_terminal_observation_and_preserves_state`。提交 `feat: bind reasoning attempts without upgrading legacy state`。

## Task 3：provider 精确参数、无回退和观测边界

**Files:** Modify model_provider.py；Test tests/test_model_provider.py。

**Interfaces:** Consumes effort+canonical digest 两 kwargs；Produces request.reasoning/result.reasoning。旧 consumer 同时省略两项时返回原 argv、原行为。

- [ ] **Step 1：拟新增精确 argv/legacy fixture。**

```python
@pytest.mark.parametrize('effort', ['medium', 'high'])
@pytest.mark.parametrize('thread', [None, '01234567-89ab-cdef-0123-456789abcdef'])
def test_reasoning_exact_argv_new_resume(tmp_path, effort, thread):
    p = provider()
    argv = p.command('codex.exe', tmp_path, tmp_path / 'final.txt', 'workspace-write',
                     model='gpt-6-luna', thread=thread,
                     reasoning_effort=effort, reasoning_contract_sha256='a' * 64)
    index = argv.index('-c')
    assert argv[index + 1] == 'model_reasoning_effort=' + effort
    assert index < argv.index('exec')
    assert ('resume' in argv) == (thread is not None)
    proof = p.reasoning_request(argv, model='gpt-6-luna', reasoning_effort=effort,
                                reasoning_contract_sha256='a' * 64)
    assert proof['declared_effort'] == proof['command_effort'] == effort

def test_reasoning_legacy_argv_is_exact(tmp_path):
    p = provider()
    assert p.command('codex.exe', tmp_path, tmp_path / 'final.txt', 'read-only') == [
        'codex.exe', '-a', 'never', '-s', 'read-only', '-C', str(tmp_path),
        'exec', '--json', '-o', str(tmp_path / 'final.txt'), '-']
```

- [ ] **Step 2：红测。** Run 两新节点与 `TestProvider::test_safe_command_new_and_resume`；当前新 kwargs 未定义应失败。
- [ ] **Step 3：实现 pair 校验和最终 argv 核对。** model_provider.py补`import re`。两参数同时 None且support_ref也None为 legacy；其中一项缺失、effort不等medium/high、hash非lower64hex、model非Luna均报 reasoning_policy_invalid。command 在现有 optional model 后、exec 前添加 `['-c', f'model_reasoning_effort={reasoning_effort}']`；CLI argparse 增加effort/hash/support-ref三项，support-ref读取外部JSON引用，无自动默认契约。

```python
def reasoning_request(argv, *, model, reasoning_effort, reasoning_contract_sha256):
    if reasoning_effort is None and reasoning_contract_sha256 is None:
        return {}
    if (reasoning_effort not in ('medium', 'high') or model != 'gpt-6-luna'
            or not isinstance(reasoning_contract_sha256, str)
            or not re.fullmatch(r'[a-f0-9]{64}', reasoning_contract_sha256)):
        raise ValueError('reasoning_policy_invalid')
    try:
        exec_index = argv.index('exec')
    except ValueError:
        raise ValueError('provider_request_mismatch') from None
    config = [(i, argv[i + 1]) for i, arg in enumerate(argv[:-1]) if arg in ('-c', '--config')]
    efforts = [(i, value) for i, value in config if value.startswith('model_reasoning_effort=')]
    if efforts != [(exec_index - 2, 'model_reasoning_effort=' + reasoning_effort)]:
        raise ValueError('provider_request_mismatch')
    if any(arg.startswith('--config=') or arg.startswith('-c=') for arg in argv):
        raise ValueError('provider_request_mismatch')
    return {'contract_sha256': reasoning_contract_sha256,
            'declared_effort': reasoning_effort, 'command_effort': reasoning_effort,
            'argv_sha256': hashlib.sha256(json.dumps(argv, ensure_ascii=False,
                 separators=(',', ':')).encode('utf8')).hexdigest()}
```

在 `run` 最终 argv_override 后调用此函数；governed override 必须与安全 command **整数组相等**，防 sandbox/model/resume替换；旧 fixture override 不受新规则影响。随后verify_reasoning_support：support-ref外部safe regular bytes与SHA、schema、固定model、medium/high、version/model-list原文refs核；最终argv[0]的absolute解析路径与support.executable.path相同且当前bytesSHA相同；可执行文件若是shim，支持包还需封存实际被调用nativebinary的ref，不能只验shim字节。任何缺证/漂移beforePopen停止reasoning_policy_invalid/binding_drift。把 reasoning和support_ref写入 request，再 Popen；失败照旧写 result并保留stderr，不调用Popen。`reasoning_observation` 当前只返回 actual null/unavailable/conformance unverified；result identity/request digest错误返回 conflict并拒绝接受。配置型 reasoningEffort字段一律忽略。既有 native_telemetry 仅保留 model/context用途，不加私有effort检索。
- [ ] **Step 4：拟新增拒绝/无推断测试。**

```python
def test_reasoning_mismatch_stops_before_popen(tmp_path):
    p = provider()
    calls = []
    result = p.run(workspace=tmp_path, evidence=tmp_path / 'evidence', prompt='synthetic',
                   enabled=True, model='gpt-6-luna', reasoning_effort='medium',
                   reasoning_contract_sha256='a' * 64, executable='codex.exe',
                   argv_override=['codex.exe', 'exec', '-'],
                   popen=lambda *a, **kw: calls.append(a))
    assert calls == []
    assert result['accepted'] is False
    assert 'provider_request_mismatch' in str(result.get('error'))

def test_reasoning_thread_config_is_not_actual_effort():
    p = provider()
    request = {'declared_effort': 'medium', 'command_effort': 'medium',
               'contract_sha256': 'a' * 64, 'thread_id': 'current', 'turn_id': 'now'}
    result = {'thread_id': 'current', 'turn_id': 'now',
              'reasoningEffort': 'high', 'actual_model': 'gpt-6-luna'}
    observed = p.reasoning_observation(result, request=request)
    assert observed['actual_effort'] is None
    assert observed['observation_status'] == 'unavailable'
    assert observed['conformance_status'] == 'unverified'
```

再以 parametrized override 覆盖重复/缺`-c`、wrongvalue、放exec后、`--config=`、wrongmodel/sandbox/thread；均Popen0。拟新增`test_reasoning_support_missing_or_binary_drift_stops_launch`用synthetic绝对exe文件bytes与外部support包，覆盖missing/unknownversion/catalogSHA漂移/binSHA漂移；均Popen0。利用既有 fake Popen与synthetic有效support包注入CLI exit2/stdout/stderr，断言仅1次launch、保留原argv/model/effort、无retry，标拟新增 `test_reasoning_cli_rejection_has_no_retry`。
- [ ] **Step 5：绿测与提交。** Run 新节点、原 TestProvider、TestTelemetryFreshness、D3 进程停机证据节点。提交 `feat: pass exact approved reasoning effort to Codex provider`。

## Task 4：driver 批准绑定、三阶段传递与恢复

**Files:** Modify workflow_driver.py；Test tests/test_workflow_driver.py。

**Interfaces:** Consumes state三校验/封存接口和 provider两个kwargs；Produces _reasoning_context 与 attempt证据引用。test/release路径不选effort。

- [ ] **Step 1：拟新增三phase缺契约必须零runner。** 复用已有 disposable linked worktree fixture。

```python
@pytest.mark.parametrize('phase', ['proposal', 'implement', 'review'])
def test_reasoning_governed_missing_contract_stops_before_runner(fixture, phase):
    driver, repo, folder = fixture
    current = driver.state.load_state('sample')
    current['reasoning_entry_kind'] = 'governed'
    driver.state._write_json(folder / 'state.json', current)
    calls = []
    with pytest.raises(ValueError, match='reasoning_contract_missing'):
        driver._run_model('sample', phase, repo, {'id': 'new', 'phase': phase},
                          lambda **kw: calls.append(kw), model='gpt-6-luna')
    assert calls == []
```

所有有效值测试通过外部 contract/proof fixtures与新 activation fixture，不在 model runner 中补写批准。拟新增 `test_reasoning_driver_phase_kwargs` 对medium/high/high分别捕获 kwargs、digest及attempt.reasoning。保留既有 fake runner 兼容：**legacy**测试 kwargs不多传，governed fake必须声明或`**kwargs`，不得捕TypeError换弱调用。
- [ ] **Step 2：红测。** Run 新缺契约节点、既有 `test_run_model_passes_explicit_model_to_provider_runner`。
- [ ] **Step 3：实现按现有 prepare seam 封存。** `advance.prepare_attempt` 在 workspace校验后载入外部activation并判别legacy/governed；governed从已封存intent_approval_ref读取reasoning_contract_ref，核actualfile/human/Task1字段，seal；begin_attempt 按Task2写binding。运行 `_reasoning_context` 必须重新核文件 SHA、state/attempt/phase/HEAD/workspace/approval和resume身份；only governed追加kwargs如下：

```python
context = _reasoning_context(task_id, phase, workspace, attempt, resume_thread)
if context is not None:
    kwargs['reasoning_effort'] = context['declared_effort']
    kwargs['reasoning_contract_sha256'] = context['contract_sha256']
    kwargs['reasoning_support_ref'] = context['support_ref']
result = runner(**kwargs)  # 原异常停机机制；禁止 TypeError 降档重试。
```

runner后由request/result实际文件ref建立reasoning_evidence；校验request reasoning及argvSHA=provider argvCanonical；result.source/attempt/workspace/thread匹配。new turn clears oldobservation，配置字段无实际证明。actual unavailable保留现有阶段结构闸；native identity冲突/公开执行矛盾(若未来有获批接口)blocked，不发布产物acceptance。当前无公开perturn effort adapter，不输出 observed；未来引入需另审接口与白名单。
- [ ] **Step 4：拟新增 approval drift/resume/evidence负例。** 参数矩阵 phase3×failure4（missing/invalidschema/contractdigest/approvalbytes），fake runner0；statecallback失败 unlock，已有attempt与HEAD原样。resume通过既有timeout终止证明再比较上一attempt.reasoning/原request/session/thread；改变任一 binding拒绝。freshreview仍newthread，不能为省费复用implementthread。记录拟新增 `test_reasoning_driver_binding_drift`、`test_reasoning_resume_preserves_binding_and_clears_observation`、`test_reasoning_unavailable_does_not_claim_conformance`。
- [ ] **Step 5：绿测与提交。** Run新节点及真实既有 `test_proposal_binding_drift_stops_before_provider`、`test_approval_drift_blocks_implementation`、`test_status_and_recover_do_not_start_model`、`test_review_uses_new_thread_and_structured_head_bound_report`、`test_advance_blocks_workspace_write_stages_from_source_checkout`。提交 `feat: enforce approved reasoning before workflow model launch`。

## Task 5：Guardian fingerprint v3 与不变历史算法

**Files:** Modify guardian_adapter.py；Test tests/test_guardian_adapter.py。

**Interfaces:** Consumes per-task contract绑定与Task2legacy清单；Produces fingerprint3与validate_reasoning_plan。历史version必须显式1/2，不能随constant=3丢失2。

- [ ] **Step 1：先固定现有 v1/v2 reference payload。** 在获批实现前，用当前源码与现有fixture将两种算法计算结果存成测试文件内固定golden字符串；同时保留现有独立referencepayload运算。不能从改后源码生成“expected”。现有2节点明确设置version2，不依赖新default。拟新增v3敏感测试如下。

```python
def test_reasoning_v3_contract_changes_fingerprint():
    guardian = load()
    plan = guardian.plan_batch('B-v3', rows(), {'effective': 'off'}, fingerprint_version=3)
    plan['reasoning_contract_bindings'] = {
        task: {'contract_sha256': 'a' * 64} for task in plan['dispatchable_ids']}
    first = guardian._plan_sha256(plan)
    changed = json.loads(json.dumps(plan))
    task = changed['dispatchable_ids'][0]
    changed['reasoning_contract_bindings'][task]['contract_sha256'] = 'b' * 64
    assert guardian._plan_sha256(changed) != first
```

- [ ] **Step 2：红测。** Run新v3节点＋现有 `test_v2_plan_fingerprint_drops_only_verified_raw_stdout_hashes`、`test_v1_digest_is_exact_legacy_and_unknown_version_fails_closed`。历史源码golden生成是 future获批fixture读计算，不是现在真实批次变更。
- [ ] **Step 3：实现明确三分支。** 原fields集合、version1完整dry_run、version2semantic_dry_run均逐字保持。exact type int，bool/float/string/None/99拒绝。version3加完整reasoning_contract_bindings进入canonicalpayload，验证mapping keys==dispatchable IDs且digest格式合法；保持其它fields全量封存。核心分支：

```python
version = plan.get('plan_fingerprint_version', 1)
if type(version) is not int or version not in (1, 2, 3):
    raise ValueError('unknown plan fingerprint version')
payload = {key: plan.get(key) for key in fields}
if version == 1:
    payload['dry_run'] = plan.get('dry_run')
else:
    payload['plan_fingerprint_version'] = version
    payload['dry_run'] = _semantic_dry_run(plan, plan.get('dry_run'))
if version == 3:
    payload['reasoning_contract_bindings'] = plan['reasoning_contract_bindings']
```

initial_batch_record封存v3binding；每 `_advance_task` 前比较plan/batch/task/externalapproval/currentworkspace，漂移零driver调用。仍显式Luna；历史清单匹配v1/v2不传effort、不得新增contract字段。
- [ ] **Step 4：拟新增 `test_reasoning_same_batch_drift_stops_before_advance`。** 用 existing same-batch fixture，首次封存后改任务digest、proofhash、workspace各一例；调用计数不增加、batchbytes/旧任务bytes不改。原 version1/2 golden均相等。
- [ ] **Step 5：绿测与提交。** Run新节点与既有samebatch/stagevalidator/concurrencystagger/Luna节点。提交 `feat: fingerprint governed reasoning plans with v3`。

## Task 6：Guardian manifest 与旧批恢复入口

**Files:** Modify guardian_entry.py；Test tests/test_guardian_entry.py。

**Interfaces:** Consumes state verified_reasoning_reference/activation 与 adapter v3；Produces _reasoning_bindings / _historical_plan_version。manifest增加reasoning_contracts={task_id: {path,sha256}}；authorizations仍是阶段设计批准，不与参数契约批准混用。

- [ ] **Step 1：拟新增新plan缺契约零派发。**

```python
def test_reasoning_new_manifest_missing_contract_does_not_dispatch(tmp_path, monkeypatch):
    monkeypatch.setenv('ZHUOPIN_CODEX_STATE', str(tmp_path / 'state'))
    entry = load()
    calls = []
    result = entry.start(manifest(tmp_path, [candidate()]), executor=executor(calls),
                         lan_prober=lambda: {'status': 'off', 'effective': 'off'}, run=True)
    assert result['status'] == 'blocked'
    assert 'reasoning_contract_missing' in result['reason']
    assert not (tmp_path / 'state' / 'guardian-batches' / 'B-human.json').exists()
```

有效fixture通过外部activation和对应准备task/proof，不仅塞一个字符串。旧 existing fixtures归入测试内明确legacy清单，不把生产缺proof当legacy。
- [ ] **Step 2：红测。** Run新节点；预期当前入口尚不检查reasoning。
- [ ] **Step 3：实现绑定次序。** start先完成原livequeue/LAN/workspace核验；从已经存在的planrecord和activation判别历史version，只有已登记原v1/v2 bytes/fingerprint且batch/任务身份一致才用原version再建同义candidateplan。新record统一3。`_reasoning_bindings`按dispatchable IDs检查manifest/taskintentapproval两个contractref一致，再做Task1外部核验、task/workspace/source HEAD一致；把bindings加plan后才dry_run/_publish_plan/claims。每stage `_assert_plan_sources`再核外部refs与sealedtaskcontract；missing/extra/wrongtaskdigest/ref漂移停止。历史入口不得用manifest提供的新contract注入老批，必须另批重新获批。
- [ ] **Step 4：拟新增正/负fixture。** `test_reasoning_manifest_matches_task_and_plan` 正例v3两次wake只启动一次；`test_reasoning_legacy_plan_recovery_never_upgrades` 原v1/v2 golden/bytes未变、oldstagekwargs无新effort；同旧batch换契约、同sourcehead新task想借legacy、陌生version、proof在modelworkspace皆blocked且无claims。LANhold不启动模型；其后人工醒转仍需该新plan完整taskcontract。
- [ ] **Step 5：绿测与提交。** Run新节点和真实既有 `test_human_start_exact_prepared_state_advances_and_second_wake_does_not_relaunch`、`test_same_batch_live_queue_change_requires_new_review`、`test_prepared_queue_anchor_must_match_current_live_locator`、`test_reviewed_watch_piece_bytes_cannot_change_before_run`。提交 `feat: validate governed manifest contracts before Guardian claims`。

## Task 7：逐项目证据、有限原生取证与独立 review

**Files:** 上述五测试文件；实现审计证据写外部runtime，review不写业务source。

**Interfaces:** consumes真实实现HEAD、批准allowlist、新fixture、publiccapability证据；produces stdout/stderr/JUnitSHA、structuredHEAD-boundreview；不制造actual-effort证明。

- [ ] **Step 1：白名单与当前基线对照。** 对implementation HEAD的diff仅上述11路径；同口径独立master对照工作树使用相同runtime/cwd/node-id。不得在共享全局site-packages install editable，不改CI或其它consumer。基线fixture与实现fixture结果分列，旧失败不吞。
- [ ] **Step 2：全codex-handoff项目CI。** canonicalcwd=`<bound-worktree>/0-学习与工具/codex-handoff`；官方CI命令如下，不能替换成根混跑。

```powershell
& $entryPython -m pytest -q --tb=short --junit-xml=pytest-result.xml
```

外层capture argv/cwd/exit/stdout/stderr/JUnit，SHA及attempt/HEAD按现有driver核验，真实总数后写。Task7只在计划+具体实现/验证获批后执行。
- [ ] **Step 3：所选CLI/model精确支持再核。** 保留可执行文件absolutepath/bytesSHA、`codex --version`/`codex exec --help`/`codex exec resume --help`出口0证据、publicmodel/list raw+SHA、schema版本+SHA。官方配置的可用值取决于model/client；本地当前model/list仅证明medium/high支持选项。CLI/globalconfig可识别`-c`不等于真实执行强度。若运行version/modelcatalog改动或支持无法确定，proposal/model阶段前停止，用户批准新policy后另identity，不回退。
- [ ] **Step 4：有限原生transport probe（需具体执行验证授权）。** 使用测试隔离非业务workspace、显式Luna、medium一次/high一次，prompt固定“只回复 OK，不调用工具，不读取文件”；capture最终argv、publicevents、thread/turn/model/workspace/request与result。最多两轮、不resume业务thread、不改globalconfig、不取private rollout。exit/turn完成证明transport受理和原生轮次完成；actual仍null/unavailable，不能说实测medium/high执行。重扫publicschema若仍无perturn effort，将精确absence与refs交review。若schema新增字段，保留变化并另审adapter，不临时补parser。
- [ ] **Step 5：正式独立只读review。** 原设计+A审表+本计划+人答链+实现HEAD+JUnit+原生证据同封存；freshreviewthread、显式Luna。首次建造所属历史v2仍依原批准和旧入口完成review，不强注入high、不称旧轮实际参数符合新policy；切换后的新v3review必须按high绑定。actual unavailable仍不能claimconformance。检查隔离路径/漂移/无回退/旧fingerprint/其他consumer。findings处理仅现有allowlist，超界先提设计审；参数功能候选正确不等于release已审。

## Task 8：切换审阅、发布准备与 #634 接力

**Files:** 无额外业务源码；正式发布/切换证据在既有runtime与§二登记。

**Interfaces:** ConsumesreviewedimplementationHEAD；Produces可审的release准备、legacy清单、activation候选；#634新proposal输入只在依赖已闭合后形成。

- [ ] **Step 1：列真正准备启用时的legacy任务/plan清单。** 用正式Workflow/Guardian公开status逐项核busyfalse；原v1/v2 bytes和fingerprint分列，前后task/plan bytes不改；说明准备未派任务是否已存在真实批准。当前#334新批尚未部署新机制、不是v3示例；不把#658设计批人工升级。
- [ ] **Step 2：展示切换approval候选。** activation仅首次外层create-exclusive；人审清单未批准不写，不能把执行plan批准自动当切换批准。approval绑定实现HEAD/policy/全部历史immutable映射/humanref，任何busy或漂移即停。发布ff另项明确授权；保留原工作树/分支和dirty文档，不清理。
- [ ] **Step 3：获ff与切换具体授权后才启用。** 在真正部署入口测试新preparedtask缺contract失败、有效三phase exactkwargs、旧批准batch原样恢复；结果登记。新任务缺契约不能继续。没有逐轮公开effort证据仍不claim实际执行符合性。
- [ ] **Step 4：依赖闭合后另出#634重派proposal。** 保留已批Win/Mac口径与保全退役；新proof绑定新入口三phase映射，编号业务design仍另审。本plan与代码review不替代#634设计批准。

## 来源核验与本次限制

- 官方配置：[Codex Configuration Reference](https://learn.chatgpt.com/docs/config-file/config-reference)，本次2026-10-05实际打开并定位model_reasoning_effort；可用强度取决于model/client。
- 官方模型：[GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna)，本次实际打开并定位reasoning.effort；API枚举不扩张本计划已批medium/high。
- 公开App Server/本地schema证据与哈希在原A审表；Thread.reasoningEffort是当前/最近配置，不是Turn执行证据。本计划不新增虚构事件字段。
- 当前 workflow_cli.py 的只读源码请求被既有PreToolUse K3守卫拒绝；未绕过/修改守卫。以已读driver.collect_evidence读取intent_approval_ref和真实existingfixture落细无CLI改动路径；Task4必须用合法定向方式完成真实prepare集成验证，若引用丢失则停并提具体scope修订，不能偷偷修改CLI白名单。
- 原基线设计元数据status失败、strict曾通过；Task1实际修复后两项均核，不把原包说成全部有效。
- 本次只读取源码/规格并编写本计划；以上全部新node-id为**拟新增**，没有创建测试文件、运行pytest、启动原生probe或实施代码。

## 自审覆盖与交接

| spec要求 | 实施任务 | 自审结果 |
|---|---|---|
| approved contract / missing/drift before launch | 1、2、4、6 | 统一canonical/外部人答链/封存；新入口不给legacy默认 |
| exact argv / no fallback / legacy provider | 3、4 | finaloverride后整数组核验，零Popen，legacy字节保持 |
| declared/command/actual distinct | 2、3、4、7 | 当前actualnull；reset；配置不冒充；A不全阶段阻断 |
| resume bindings | 2、4 | 跟旧真实attempt/request/session核，漂移新授权新identity |
| v3 / historicalv1v2 | 2、5、6、8 | 三明确分支、旧golden、获批历史清单、原样恢复 |
| oldguards/CI/review/humangates | 4、6、7、8 | 已核真实节点、逐子项目、freshreview、ff/切换另审 |

执行路由沿用项目正式Guardian隔离工作树，不另问是否转Native写业务代码。计划人审通过后，仍先准备具体task/worktree/allowlist/实现验证授权；不能用本次plan-only证明跨闸。原封存§一#658及input/watch/manifest保持不变，批准/计划登记在§二。
