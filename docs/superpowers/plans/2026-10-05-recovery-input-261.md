# Recovery Input Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for the proposed Native execution, or superpowers:subagent-driven-development only if Shao Peishen explicitly selects it. Internal steps use checkbox syntax for tracking; this file grants no implementation permission.

**Goal:** 为已终结empty_changes的implement尝试，通过正式Workflow/Guardian传递单次获准恢复输入并封存公开送达证据，保留原任务和全部历史批准。

**Architecture:** 独立recovery_input.py做严格schema、外部文件及原任务身份校验；driver使用原任务锁在新attempt内原子封存恢复消费标记，再把不可变输入快照追加至原prompt。provider只增加可选公开输入证据；Guardian新恢复计划使用v4，历史v1/v2及独立reasoning v3不改义。

**Tech Stack:** 本机隔离CPython、stdlib（dataclasses/hashlib/json/pathlib/re/stat）、pytest；既有Codex Workflow/Guardian与Git linked worktree。无新依赖、无全局editable安装。

**Spec:** 主仓绝对路径`C:/Dev/zhuopin-ai/docs/superpowers/specs/2026-10-05-recovery-input-261-design.md`，SHA256 `b96140e81b9d6a97c58711a98c0e76072d324d506333e36a3e2c571916418922`；独立OpenSpec包`openspec/changes/recovery-input-261/`。执行者先核存在和SHA，再按≤200行窗口读spec和本计划，不猜隔离树内副本、不整读或复制计划。

用户本次原答：“#262：批准恢复输入传递设计A，先出独立机制具体实施计划，实施另审；原#658批准保留，新失败批暂不退役或重派，ff与真实切换另审。”该答复只批准本计划编制。本计划待§四#263审阅，不授权任何代码、测试模型、退役、重派或发布。

记录：2026-10-05 09:48:26 +08:00（Get-Date）；本次Probe全部checks exit0，读源码时主仓HEAD=ef0b931451c0a0e2e19c83ddc7c28128f023412c。实施准备须重新Probe并绑定实际基线，不用这个时点HEAD解除旧任务闸。

## Global Constraints

1. 首版只接受最新、终结的implement/empty_changes；busy=false、工作树干净且HEAD等于原design_head。proposal/review、脏树timeout resume、running尝试及自动重试不支持。
2. 原task/intent/design/实施批准/Guardian计划/旧attempt字节不改；只在获批独立机制工作树修改下述14路径。原#658的11路径批准不扩成新白名单。
3. 模型显式`gpt-6-luna`；不改变effort。恢复实现先兼容legacy，reasoning契约独立获批、独立切换；不把v3待实现当已存在。
4. 输入/批准件位于主仓及全部模型工作树之外；严格JSON拒绝重复键和未知键；原始JSON≤32768 bytes、instructions 1～8192 UTF-8 bytes、documents 1～8、max_lines整数1～200（bool拒绝）。可选一个UTF-8 BOM，文件SHA含BOM。
5. 同一恢复批准最多一次launch；任务锁内原子封存消费，崩溃/未知现场保守停下，不复用批准、不伪装recover解锁。
6. 无输入的legacy prompt、argv和v1/v2 fingerprint保持字节/历史语义；v4恢复plan不原位升级旧批。未支持的v3继续明确拒绝，绝不解释成v4。
7. 送达、遵循、产物验收分开；exit0不是交付。CI、freshthread独立review、ff/入口切换/.51/外发/L2原闸保持。
8. 此计划不处理B-1005退役、不启动#658或解除#634。正常机制发布与旧任务执行版本兼容核验闭合后，才另审恢复。
9. Native父执行者在独立工作树按正常Git/锁/证据规则提交；任何Workflow派生模型只写文件，由其既有外层驱动提交。不得把Native实现伪装成Workflow implement终态，不手改阶段state。均不复制runner、不改PYTHONPATH、不换hook、不创建后台调度。

## Review Focus

| 易漏输入/状态 | 预期 | 所属验证 |
|---|---|---|
| JSON中的true充当max_lines，重复键覆盖绑定 | 拒绝，不能因Python bool是int而放行 | Task1 TestRecoverySchema |
| Windows大小写/空格路径、祖先junction指向工作树 | 真实路径边界校验、链接拒绝，文件读取前后身份一致 | Task1 TestRecoveryLocations |
| 锁前验证后另一次attempt结束或外部审批变字节 | 锁内重验最新attempt与相同快照，launch=0 | Task2/Task4 |
| Guardian循环把恢复许可传入第二阶段或二次唤醒 | 首次implement单次消费；后续test/review不传，失败不重试 | Task6 |
| recovery/provider证据不一致但有代码改动和exit0 | commit之前拒绝接受，保持交付未接受 | Task3/Task4 |

## 文件职责与有限实施白名单

所有路径相对主仓，路径前缀为`0-学习与工具/codex-handoff/`：

| 文件 | 责任 |
|---|---|
| recovery_input.py（新建） | 输入/审批schema、冻结快照、外部路径、原身份校验、prompt/evidence构造 |
| workflow_state.py | begin_attempt新增可选恢复回调，新attempt一次消费和原子落盘 |
| model_provider.py | 可选input_evidence核验及request/result公开证据 |
| workflow_driver.py | 锁前/锁内验证、stage传递、追加prompt、接受前送达核验 |
| handoff.py | advance CLI成对参数、legacy run拒绝 |
| guardian_entry.py | manifest校验、外部快照/计划绑定和重醒漂移拒绝 |
| guardian_adapter.py | v4 fingerprint及单次阶段转交 |
| tests/test_recovery_input.py（新建） | schema、文件/路径、绑定、冻结快照与纯prompt测试 |
| tests/test_workflow_state.py | 一次消费、原子性、竞争/崩溃兼容 |
| tests/test_model_provider.py | 公开request/result、pre-Popen拒绝、legacy不变 |
| tests/test_workflow_driver.py | 全stage链、拒绝矩阵、最终artifact/CI闸不放宽 |
| tests/test_handoff.py | CLI参数/路由及legacy拒绝 |
| tests/test_guardian_entry.py | 正式manifest→plan→runner、封存漂移、原claim保护 |
| tests/test_guardian_adapter.py | v1/v2黄金摘要、v4两项投影、循环/重醒消费 |

共14路径。docs/OpenSpec本次制品由Sweep落库，不列入模型实现白名单；不改旧reasoning-entry-policy-658包、CI、hooks、invoke.ps1、其它provider consumer、账户配置或调度。若实施证明必须增加路径，停止提出具体范围修订，不借原#658批准扩大。

## 已核实际接缝与bootstrap

- workflow_state.py::begin_attempt(237起)：排他running.lock；prepare(current)在新attempt创建前；原子state.json写入。不能在普通prepare里偷偷写旧封印；新增独立recovery_prepare(current, attempt)回调，在生成新id后、append之前执行。
- workflow_driver.py::_run_model(422)、_implement(839)、run_one_stage(1224)、advance(1310)。批准快照和白名单已有真实校验；_implement在provider之后、commit之前可加送达核验。
- model_provider.py::run(269起)已有request.json在Popen前写出，prompt_sha256来自真实字符串；不能把另算的文本冒充stdin。
- handoff.py::main的真实advance argparse/driver调用是CLI接缝；不存在workflow_cli.py。
- guardian_entry.py::_execution_bindings(120)、start(511)及_assert_plan_sources；guardian_adapter.py::_advance_task(279)、run_foreground内run_stages(约693)是转交链。循环不能重复传许可。
- 原任务源码校验当前检查source_checkout/common-dir与design HEAD，未在本轮有限源码内发现独立“driver版本锁”字段；这不是已证明未来版本无约束。正式发布时记录实际invoke/driver源文件SHA并重跑隔离兼容fixture，若存在新绑定拒绝则保留停点另审迁移。

实施准备采用独立机制task slug `recovery-input-261`（与现有OpenSpec目录一致）及正式新机制队列行；不重新prepare #658。新行、工作树、书面批准/allowed_paths在计划实施获批后通过既有工具登记。设计包已在主仓，Native父执行者读取其绝对路径/SHA，在独立树建造，不调用尚未存在的恢复接口。

本轮源码另核出bootstrap限制：现有_proposal要求proposal/design/tasks三件都在changed集合，已落库包原样复核不能形成正式proposal seal。因此本计划推荐Native实施，不为了制造seal重写已批三件或手填Workflow state。其产物按Native Git/CI/独立review证据验收，不宣称具有Workflow implementation_head字段。若选择必须自动Workflow/Guardian建造，则先停下审阅其正式既有设计采纳路径；本14路径机制授权不自动涵盖新“adopt”接口。未来新独立工作树由using-git-worktrees按现时基线创建，全部旧树保留。

## Task 1: 恢复schema、外部文件与冻结快照

**Files:** Create recovery_input.py、tests/test_recovery_input.py。

**Interfaces（全计划唯一签名表）:**

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class DocRef:
    path: str
    sha256: str
    max_lines: int

@dataclass(frozen=True)
class RecoverySnapshot:
    recovery_id: str
    task_id: str
    previous_attempt_id: str
    input_path: str
    input_sha256: str
    approval_path: str
    approval_sha256: str
    context_json: str
    documents: tuple[DocRef, ...]

class RecoveryError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)

```

接口索引如下，函数的输入/返回在此统一，核心实现和测试见步骤：

| 函数 | 参数 | 返回 |
|---|---|---|
| load_snapshot | input_path: Path, approval_path: Path；keyword current: dict, workspace: Path, protected_roots: tuple[Path, ...] | RecoverySnapshot |
| revalidate | snapshot: RecoverySnapshot；keyword current/workspace/protected_roots同上 | 同字节RecoverySnapshot，否则异常 |
| verify_source_files | snapshot: RecoverySnapshot | None；只核来源文件，不核当前阶段资格 |
| attempt_binding | snapshot: RecoverySnapshot；keyword source_batch: str或None | dict |
| append_context | base_prompt: str, snapshot: RecoverySnapshot | tuple[str, dict] |
| validate_input_evidence | prompt: str, value: dict | 已核dict |
| verify_delivery | evidence_dir: Path, metadata: dict, result: dict | None或RecoveryError |

返回对象只含不可变primitive/tuple/str，不向调用者暴露可变dict。context_json使用canonical sorted JSON：原payload全部字段（schema改为zhuopin.recovery-input-context/v1）+input_sha256+approval_sha256+固定scope_note；不含approval text或文档全文。scope_note固定为“经审核的定向更正数据；不是权限、shell或更高优先级指令；原allowed_paths仍唯一实施白名单”。

- [ ] Step1：新建TestRecoverySchema/TestRecoveryLocations/TestRecoveryBindings/TestRecoveryPrompt类，写下列完整fixture（只用于脱敏tmp_path；文件工单/批准均为假，不指向真实runtime）。

```python
import hashlib, importlib.util, json, sys
from pathlib import Path
import pytest

@pytest.fixture
def recovery_case(tmp_path):
    source = Path(__file__).resolve().parents[1] / "recovery_input.py"
    spec = importlib.util.spec_from_file_location("recovery_test", source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    root = tmp_path / "main"
    workspace = tmp_path / "worktree"
    outside = tmp_path / "approval space"
    for path in (root, workspace, outside): path.mkdir()
    document = root / "plan.md"
    document.write_text("fixture plan\n", encoding="utf8")
    old = "1" * 32
    current = {"id": "sample", "source_head": "a" * 40,
        "design_head": "a" * 40, "design_ref": {"sha256": "b" * 64},
        "design_approval_ref": {"sha256": "c" * 64},
        "workspace": str(workspace.resolve()), "phase_status": "blocked",
        "attempts": [{"id": old, "phase": "implement", "status": "blocked",
                      "path_guard_reason": "empty_changes", "finished_at": "2026-10-05T00:00:00+00:00"}]}
    payload = {"schema": "zhuopin.recovery-input/v1", "recovery_id": "r-1",
        "task_id": "sample", "phase": "implement", "previous_attempt_id": old,
        "workspace": str(workspace.resolve()), "design_head": "a" * 40,
        "design_sha256": "b" * 64, "implementation_approval_sha256": "c" * 64,
        "instructions": "Check the absolute plan path first; read at most 200 lines.",
        "documents": [{"path": str(document.resolve()),
                       "sha256": hashlib.sha256(document.read_bytes()).hexdigest(), "max_lines": 200}]}
    input_path, approval_path = outside / "input.json", outside / "approval.json"
    def publish(value=payload):
        input_path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf8")
        proof = {"schema": "zhuopin.recovery-input-approval/v1", "recovery_id": "r-1",
            "task_id": "sample", "phase": "implement", "previous_attempt_id": old,
            "recovery_input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
            "implementation_approval_sha256": "c" * 64,
            "approval_source": "fixture explicit approval", "text": "approve this fixture recovery once"}
        approval_path.write_text(json.dumps(proof), encoding="utf8")
    publish()
    return module, input_path, approval_path, current, workspace, (root, workspace), payload, publish

class TestRecoverySchema:
    @pytest.mark.parametrize("bad", [True, 0, 201, 1.0, "200"])
    def test_max_lines_rejects_non_integer_or_out_of_bounds(self, recovery_case, bad):
        m, ip, ap, current, ws, roots, payload, publish = recovery_case
        payload["documents"][0]["max_lines"] = bad
        publish()
        with pytest.raises(m.RecoveryError, match="recovery_input_invalid"):
            m.load_snapshot(ip, ap, current=current, workspace=ws, protected_roots=roots)

class TestRecoveryPrompt:
    def test_freezes_input_and_keeps_base_hash(self, recovery_case):
        m, ip, ap, current, ws, roots, payload, publish = recovery_case
        frozen = m.load_snapshot(ip, ap, current=current, workspace=ws, protected_roots=roots)
        base = "existing exact base prompt\n"
        prompt, metadata = m.append_context(base, frozen)
        assert prompt.startswith(base)
        context = json.loads(prompt.split("\nrecovery_input_context=", 1)[1])
        assert context["documents"][0]["path"] == payload["documents"][0]["path"]
        assert "fixture plan\\n" not in prompt
        assert metadata["base_prompt_sha256"] == hashlib.sha256(base.encode()).hexdigest()
        assert metadata["effective_prompt_sha256"] == hashlib.sha256(prompt.encode()).hexdigest()
        ip.write_bytes(ip.read_bytes() + b" ")
        with pytest.raises(m.RecoveryError, match="binding_drift"):
            m.revalidate(frozen, current=current, workspace=ws, protected_roots=roots)
```

- [ ] Step2：从未来独立工作树codex-handoff cwd运行隔离Python `-m pytest -q tests/test_recovery_input.py::TestRecoverySchema tests/test_recovery_input.py::TestRecoveryPrompt`，确认红因为模块/函数未实现，不是环境collection错误。
- [ ] Step3：实现strict parser与不可变DTO。JSON使用object_pairs_hook拒绝重复键；大小先取len(bytes)，utf-8-sig严格decode；json.loads的NaN/Infinity用parse_constant拒绝。每层exact key set，不把float/bool当int。审批exact字段集采用上面fixture，不允许额外“权限”字段。recovery_id正则`[a-z0-9][a-z0-9-]{0,63}`；task/attempt必须非空并与原状态相等；所有SHA必须lowercase 64hex、HEAD lowercase40hex。批准原文/source均要求非空str，分别≤8192/2048 UTF-8 bytes，不执行文本。

```python
import hashlib, json, re

def strict_object(raw: bytes) -> dict:
    if not 1 <= len(raw) <= 32768:
        raise RecoveryError("recovery_input_invalid")
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value: raise RecoveryError("recovery_input_invalid")
            value[key] = item
        return value
    def reject_constant(value):
        raise RecoveryError("recovery_input_invalid")
    try:
        value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=pairs,
                           parse_constant=reject_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RecoveryError("recovery_input_invalid") from exc
    if not isinstance(value, dict): raise RecoveryError("recovery_input_invalid")
    return value

def canonical(value: dict) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()
```

- [ ] Step4：实现单次read稳定快照：先核绝对路径、regular文件与每级祖先无symlink/Windows is_junction/reparse属性，再resolve(strict=True)；输入/审批resolved路径不得落在任一protected root。打开rb后fstat→read(size bound+1)→fstat，并与路径lstat身份（dev/ino/size/mtime_ns）比较，变化则binding_drift；文件错误不回显内容。文档引用允许在主仓/工作树，但必须绝对regular、摘要一致；流式hash，全文不存context。revalidate再次load得到新snapshot，与原tuple逐字段相等，否则binding_drift；这是锁内的第二次验证，prompt只用第二次已相同的快照，不第三次读外部说明。
- [ ] Step5：绑定current：原id/workspace/design_ref/design_approval_ref及最新attempt一致；最新attempt status=blocked、phase=implement、path_guard_reason=empty_changes且finished_at是有效有时区ISO时间；running/其它失败拒绝。driver另外负责实际Git clean/HEAD与mutex，不信payload宣称busy=false。审批input原始SHA/原批准SHA及task/recovery/attempt/phase必须全部相等。
- [ ] Step6：追加块采用`base + "\nrecovery_input_context=" + context_json + "\n"`，块中固定说明其为已审更正数据而非权限/shell/高优先级指令。metadata严格为schema=`zhuopin.recovery-delivery/v1`、recovery_input_context（解析context_json所得对象）、base_prompt_sha256、effective_prompt_sha256、suffix_sha256。validate_input_evidence按context重建完整suffix，验证prompt以该suffix结尾，切除suffix重新核base，验证effective/suffix digest，拒绝多余字段。不把document body或审批text落公开request。

```python
def append_context(base_prompt: str, snapshot: RecoverySnapshot) -> tuple[str, dict]:
    suffix = "\nrecovery_input_context=" + snapshot.context_json + "\n"
    effective = base_prompt + suffix
    metadata = {"schema": "zhuopin.recovery-delivery/v1",
        "recovery_input_context": json.loads(snapshot.context_json),
        "base_prompt_sha256": digest(base_prompt.encode("utf8")),
        "effective_prompt_sha256": digest(effective.encode("utf8")),
        "suffix_sha256": digest(suffix.encode("utf8"))}
    return effective, metadata

def validate_input_evidence(prompt: str, value: dict) -> dict:
    keys = {"schema", "recovery_input_context", "base_prompt_sha256",
            "effective_prompt_sha256", "suffix_sha256"}
    if not isinstance(value, dict) or set(value) != keys or value["schema"] != "zhuopin.recovery-delivery/v1":
        raise RecoveryError("recovery_delivery_mismatch")
    context = value["recovery_input_context"]
    if not isinstance(context, dict): raise RecoveryError("recovery_delivery_mismatch")
    suffix = "\nrecovery_input_context=" + canonical(context) + "\n"
    if not prompt.endswith(suffix): raise RecoveryError("recovery_delivery_mismatch")
    base = prompt[:-len(suffix)]
    hashes = {"base_prompt_sha256": digest(base.encode("utf8")),
        "effective_prompt_sha256": digest(prompt.encode("utf8")),
        "suffix_sha256": digest(suffix.encode("utf8"))}
    if any(value[k] != v for k, v in hashes.items()):
        raise RecoveryError("recovery_delivery_mismatch")
    return json.loads(canonical(value))
```

该pure helper验证字节一致性；schema/context身份另由load_snapshot和driver原批准闸验证，provider不能独立凭metadata授予权限。
- [ ] Step7：补充并运行三个真实边界类：TestRecoveryLocations（绝对/空格/大小写归一、文件/祖先链接、文档缺失/变化/符号链接），TestRecoveryBindings（错id/phase/latest/approval/hash/source/未知字段），TestRecoverySchema（byte边界/BOM/重复键/UTF8/NaN/doc数量）。junction实测用隔离tmp下PowerShell New-Item -ItemType Junction，测试结束仅删除本fixture junction，验证目标内容未变；环境不能创建junction则报告覆盖缺口，不能把skip当覆盖通过。
- [ ] Step8：绿后保存Task1 patch/测试输出，Native父执行者按14路径逐任务提交到独立分支，不合master；若有派生执行模型，其不自行commit。任务交付为可验证冻结schema/helper，后续消费者只调用本签名。

## Task 2: 锁内一次性许可与崩溃留痕

**Files:** Modify workflow_state.py；Test tests/test_workflow_state.py。

**Consumes:** Task1 attempt_binding与RecoveryError；state层不自行读外部文件，不引入input权限判断。
**Produces:** `begin_attempt(task_id: str, phase: str, expected_head: str, *, expected_state_snapshot: tuple | None = None, prepare=None, recovery_prepare=None) -> dict`；recovery_prepare签名`(locked_state: dict, new_attempt: dict) -> None`；`reserve_recovery(current: dict, attempt: dict, binding: dict) -> None`。

- [ ] Step1：新增TestRecoveryReservation类。prepared fixture按该文件已有prepared(tmp_path)建fake state，初始attempt为fixture的32hex终结empty_changes。以下测试绑定是纯state层值，不证明真实授权。

```python
class TestRecoveryReservation:
    def test_consumed_permission_cannot_be_reserved_twice(self):
        state = load_state_module()
        binding = {"recovery_id": "r-1", "previous_attempt_id": "1" * 32,
                   "recovery_input_ref": {"path": "input", "sha256": "a" * 64},
                   "recovery_approval_ref": {"path": "approval", "sha256": "b" * 64}}
        current = {"attempts": []}
        first = {"id": "2" * 32, "phase": "implement", "status": "running"}
        state.reserve_recovery(current, first, binding)
        current["attempts"].append(first)
        with pytest.raises(ValueError, match="recovery_already_consumed"):
            state.reserve_recovery(current, {"id": "3" * 32}, binding)
        assert first["recovery_permission_status"] == "reserved"
```

- [ ] Step2：跑该node确认红；再实现消费算法。扫描所有原attempt的recovery_binding：同recovery_id或同approval SHA已出现即拒绝，不依赖旧attempt最终status；binding拷贝入new_attempt，初始化delivery_status=not_started、compliance_status=unknown、recovery_permission_status=reserved、source_recovery_batch。保存原attempt前后byte-equivalent，不能给旧attempt补字段。

```python
def reserve_recovery(current: dict, attempt: dict, binding: dict) -> None:
    for old in current.get("attempts", []):
        prior = old.get("recovery_binding")
        if prior and (prior.get("recovery_id") == binding["recovery_id"] or
                      prior.get("recovery_approval_ref", {}).get("sha256") ==
                      binding["recovery_approval_ref"]["sha256"]):
            raise ValueError("recovery_already_consumed")
    attempt["recovery_binding"] = json.loads(json.dumps(binding))
    attempt["recovery_permission_status"] = "reserved"
    attempt["recovery_delivery_status"] = "not_started"
    attempt["recovery_compliance_status"] = "unknown"
```

- [ ] Step3：在原begin_attempt内部生成id后、append之前调用recovery_prepare；原prepare(current)和HEAD/snapshot检查顺序不变。所有恢复绑定和新attempt在同一次state._write_json中落盘后才允许模型启动。回调失败使用原异常路径，不留下新attempt、不运行模型。
恢复分支的写异常需要区分“确定未落盘”与“写结果未知”：异常后能只读确认最新attempt不是本new id则按原逻辑释放自己锁；已能读到本new id/reserved或状态无法读取时保留running.lock与现场。legacy无recovery_prepare的异常清理完全不变。不能因state.replace已经成功而finally/temp清理报错就unlink锁再重派。
- [ ] Step4：新增类节点test_callback_failure_preserves_original_state、test_lock_race_allows_single_attempt、test_crash_after_reservation_never_refunds、test_write_failure_never_launches。两线程Barrier同时begin_attempt，恰一个拿running.lock；真实tmp state两次调用，断言一次new id、旧attempt原文不变。模拟原子写替换成功后崩溃，保留reserved标记/锁不自动refund；无法证明是否launch则正式结算后要求新的明确恢复批准，不提供复用开关。
- [ ] Step5：从canonical cwd运行TestRecoveryReservation与既有state互斥/HEAD/直接finish拒绝节点（以实际`--collect-only`核名称）至绿。原finish authority不改、原recover仍fail closed；状态回调不造退出证据。

## Task 3: Provider公开request/result送达证据

**Files:** Modify model_provider.py；Test tests/test_model_provider.py。
**Consumes:** recovery_input.validate_input_evidence(prompt, value)、RecoveryError。
**Produces:** provider.run原签名增加keyword `input_evidence: dict | None = None`，command函数与CLI argv均不变。

- [ ] Step1：新增TestRecoveryInputEvidence；用已有TestProvider真实隔离child fixture模式捕获stdin并返回thread.started/turn.completed（非模型、不调用外网）。伪child只读取stdin，输出规范事件，不执行instructions。

```python
class TestRecoveryInputEvidence:
    def test_bad_metadata_cannot_start_process(self, tmp_path):
        p = provider()
        calls = []
        result = p.run(workspace=tmp_path, evidence=tmp_path / "bad",
            prompt="fixture", enabled=True, model="gpt-6-luna",
            input_evidence={"schema": "zhuopin.recovery-delivery/v1"},
            popen=lambda *args, **kw: calls.append(args))
        assert calls == []
        assert result["status"] == "recovery_delivery_mismatch"
        assert result["accepted"] is False
```

- [ ] Step2：跑node确认红；然后在run的既有try、写request前调用validator，捕获RecoveryError写result.status=recovery_delivery_mismatch（不回显自由文本），exit_code仍None；不Popen。不带input_evidence时不调用validator、不增加request/result键、不变legacy hash/argv。
- [ ] Step3：有效metadata深拷贝进request的`input_evidence`，base/effective SHA亦存在其中；result只回显`input_evidence_binding`：recovery_id、input_sha256、approval_sha256、base/effective SHA。request中的prompt_sha256仍由prompt.encode真实生成；禁止argv_override替代业务输入入口，原测试注入能力仅Python API保留。
- [ ] Step4：新增test_request_contains_exact_bounded_context、test_result_echoes_same_binding、test_audit_failure_before_launch_starts_no_child、test_legacy_request_has_no_new_keys、test_different_effective_sha_stops_launch。完整context只包含脱敏instructions和已批准documents refs，审批text及document正文不写request；测试搜索独特sentinel保证不泄露两者。
- [ ] Step5：使用TestRecoveryInputEvidence及既有TestProvider/TestReviewRegressions运行至绿。事件summary/context/timeout/清理原守不改，不用退出0设置accepted=true；actual_effort不添加/推断。

## Task 4: Workflow全阶段传递、锁内重验及commit前验收

**Files:** Modify workflow_driver.py；Test tests/test_workflow_driver.py。
**Consumes:** Task1全部API、Task2 recovery_prepare与reserve_recovery、Task3 input_evidence。
**Produces:** `advance(task_id: str, workspace: Path, authorization: Path | None = None, executor=default_executor, *, model_runner=None, retry_failed_ci=False, refresh_ci_evidence=False, model: str | None = None, recovery_input: Path | None = None, recovery_approval: Path | None = None, recovery_batch: str | None = None) -> dict`；run_one_stage/_implement/_run_model各增加optional `recovery_snapshot: RecoverySnapshot | None = None`，不把snapshot放全局或环境变量。

- [ ] Step1：在现有approved_fixture上创建新的driver_recovery_case fixture。移除fixture遗留implementation_head/evidence，因为恢复条件是“尚无成功实现”；添加最新failed attempt并按现有formal approval bytes构造测试输入。下面fixture代码与Task1 fixture并行独立，不引用真实任务。

```python
@pytest.fixture
def driver_recovery_case(approved_fixture, tmp_path):
    driver, repo, folder, approval = approved_fixture
    current = driver.state.load_state("sample")
    for key in ("implementation_head", "implementation_evidence", "implementation_thread_id"):
        current.pop(key, None)
    previous = "1" * 32
    current.update(phase="proposal", phase_status="blocked", attempts=[{
        "id": previous, "phase": "implement", "status": "blocked",
        "path_guard_reason": "empty_changes", "finished_at": "2026-10-05T00:00:00+00:00"}])
    driver._save("sample", current)
    outside = tmp_path / "recovery proof"
    outside.mkdir()
    input_path, proof_path = outside / "input.json", outside / "proof.json"
    document = Path(current["design_ref"]["path"])
    payload = {"schema": "zhuopin.recovery-input/v1", "recovery_id": "r-driver",
        "task_id": "sample", "phase": "implement", "previous_attempt_id": previous,
        "workspace": str(repo.resolve()), "design_head": current["design_head"],
        "design_sha256": current["design_ref"]["sha256"],
        "implementation_approval_sha256": driver._sha(approval),
        "instructions": "Read only the bound absolute fixture document in 200-line windows.",
        "documents": [{"path": str(document.resolve()), "sha256": driver._sha(document), "max_lines": 200}]}
    input_path.write_text(json.dumps(payload), encoding="utf8")
    proof_path.write_text(json.dumps({"schema": "zhuopin.recovery-input-approval/v1",
        "recovery_id": "r-driver", "task_id": "sample", "phase": "implement",
        "previous_attempt_id": previous, "recovery_input_sha256": driver._sha(input_path),
        "implementation_approval_sha256": driver._sha(approval),
        "approval_source": "explicit fixture recovery", "text": "approve one fixture recovery"}), encoding="utf8")
    return driver, repo, folder, approval, input_path, proof_path

class TestRecoveryDriver:
    def test_wrong_document_stops_before_runner(self, driver_recovery_case):
        driver, repo, folder, approval, ip, ap = driver_recovery_case
        data = json.loads(ip.read_text())
        data["documents"][0]["sha256"] = "0" * 64
        ip.write_text(json.dumps(data))
        proof = json.loads(ap.read_text())
        proof["recovery_input_sha256"] = driver._sha(ip)
        ap.write_text(json.dumps(proof))
        calls = []
        before = (folder / "state.json").read_bytes()
        result = driver.advance("sample", repo, approval,
            model_runner=lambda **kw: calls.append(kw), model="gpt-6-luna",
            recovery_input=ip, recovery_approval=ap)
        assert result["status"] == "blocked"
        assert result["reason"] == "recovery_document_drift"
        assert calls == []
        assert (folder / "state.json").read_bytes() == before
```

- [ ] Step2：run TestRecoveryDriver红；实现advance成对检查：缺一、与CI retry/refresh任一同时传入、next_phase非implement、resume_thread非None均明确blocked；无许可不能覆盖gate.decide_next原决定。先collect_evidence/_bound_approval等现时原闸，再load_snapshot（protected roots含真实source_checkout及current workspace；Guardian传全部工作树边界已外层核，driver至少核本task两根）。新增非法phase/provider参数不能动旧状态。
- [ ] Step3：在begin_attempt的recovery_prepare中，以locked_state调用revalidate；重核actual HEAD与_clean、_bound_approval/ref未漂移；调用reserve_recovery封存attempt_binding。用函数局部nonlocal接收locked snapshot，在begin_attempt返回后沿stage传下去。绑定锁内当前latest attempt必须仍为原previous id；这个校验发生在新attempt append之前。不在provider之后补消费标记。

```python
locked_recovery = None
def prepare_recovery(locked_state, new_attempt):
    nonlocal locked_recovery
    locked_recovery = recovery.revalidate(snapshot, current=locked_state,
        workspace=workspace, protected_roots=protected_roots)
    if current_head(workspace) != locked_state["design_head"] or not _clean(workspace):
        raise recovery.RecoveryError("recovery_attempt_ineligible")
    approved = _bound_approval(task_id, workspace, locked_state)
    if approved["authorization_sha256"] != json.loads(locked_recovery.context_json)["implementation_approval_sha256"]:
        raise recovery.RecoveryError("binding_drift")
    state.reserve_recovery(locked_state, new_attempt,
        recovery.attempt_binding(locked_recovery, source_batch=recovery_batch))
```

该段位于advance局部作用域，snapshot/protected_roots来自本步骤锁前load；legacy无输入时不传recovery_prepare关键字，保留旧fake调用兼容。若任何异常落盘后状态不明，原running.lock/正式recover逻辑保持，不删锁“重试”。

- [ ] Step4：_run_model只对implement且resume_thread为空处理snapshot，在原批准prompt完整形成后append_context。kwargs新增input_evidence只在snapshot非None时添加；原argv与model选择不变。把base/effective SHA封存在当前新attempt，由外层使用已有state._save在其持锁期更新新attempt，不覆盖旧attempt。snapshot引用须与已reserved attempt绑定一致，否则拒绝启动。
- [ ] Step5：provider回后、任何git add/commit之前verify_delivery：公开request/result文件必须位于本attempt evidence目录、regular文件、可读JSON；request.prompt_sha256、input_evidence完整context/base/effective/suffix、result.input_evidence_binding与driver metadata一致，result来源task/attempt/workspace/thread按既有_native gate继续核。缺证/漂移调用_implementation_blocked(reason=recovery_delivery_mismatch)，不接受代码。不把fake provider直接返回的metadata当文件证明。
此处同时verify_source_files(locked_recovery)和_bound_approval复核原外部批准；启动后的资格不能再用latest失败判据，但任何原输入/审批/文档字节漂移或原批准漂移仍在commit前拒绝，保留provider公开失败和工作树diff，不能自动重跑。

```python
def verify_delivery(evidence_dir: Path, metadata: dict, result: dict) -> None:
    paths = (evidence_dir / "request.json", evidence_dir / "result.json")
    if any(p.is_symlink() or not p.is_file() for p in paths):
        raise RecoveryError("recovery_delivery_mismatch")
    try:
        request, saved_result = (json.loads(p.read_text(encoding="utf8")) for p in paths)
        context = metadata["recovery_input_context"]
        expected = {key: metadata[key] for key in ("base_prompt_sha256", "effective_prompt_sha256")}
        expected.update(recovery_id=context["recovery_id"],
            input_sha256=context["input_sha256"], approval_sha256=context["approval_sha256"])
        if request.get("input_evidence") != metadata or request.get("prompt_sha256") != metadata["effective_prompt_sha256"]:
            raise RecoveryError("recovery_delivery_mismatch")
        if saved_result.get("input_evidence_binding") != expected or result.get("input_evidence_binding") != expected:
            raise RecoveryError("recovery_delivery_mismatch")
        if saved_result.get("prompt_sha256") != metadata["effective_prompt_sha256"]:
            raise RecoveryError("recovery_delivery_mismatch")
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        raise RecoveryError("recovery_delivery_mismatch") from exc
```

regular/reparse稳定读取复用Task1 read策略，此reference code展示字段比对，实施不得放宽既有目录/文件身份验证。送达成功只置recovery_delivery_status=delivered、compliance_status=unknown；不为final声明生成observed。模型仍empty_changes走原artifact闸。
- [ ] Step6：新增TestRecoveryDriver参数测试：busy/锁内latest改变/脏树/HEAD/hash漂移/timeout resume/错phase/二次许可/缺request/错result摘要/正常追加。fake runner必须写request/result/event/session的受限既有真实fixture证据，才能让原native核验通过；test_delivered_empty_changes_remains_blocked必须真正无diff、送达文件正确、断言path_guard_reason=empty_changes与delivered分开。
- [ ] Step7：新增test_input_changes_between_precheck_and_lock、test_old_approval_and_attempts_unchanged、test_delivery_mismatch_never_calls_git_commit；用monkeypatch挂begin_attempt前改外部文件，真实调用回调拒绝。commit spy断言0；有合法service.py改动但错证据仍不接受，不把模型误写代码当成功。
- [ ] Step8：执行新类及既有test_run_model_defaults_to_explicit_luna_when_unspecified、test_run_model_rejects_non_luna_before_provider、test_implementation_seals_approval_before_model_and_never_replaces_it、test_implement_outer_commit_is_bound_to_approval_paths、test_review_uses_new_thread_and_structured_head_bound_report。绿后Native父执行者在独立分支提交，CI/review路径不携带恢复snapshot。

## Task 5: 正式CLI成对参数

**Files:** Modify handoff.py；Test tests/test_handoff.py。
**Consumes:** driver.advance两项Path参数；recovery_batch只供Guardian内部，不暴露伪造batch CLI。
**Produces:** Workflow advance公开`--recovery-input`、`--recovery-approval`。run不声明两个flag，argparse收到即退出2，不进入run_stage。

- [ ] Step1：新增TestRecoveryCLI；复用现有test_advance_cli_passes_optional_model中的假driver导入注入方式，写以下argv用例。此测试只验证路由，不批准调用。

```python
class TestRecoveryCLI:
    @pytest.mark.parametrize("extra,expected_calls", [
        (["--recovery-input", "C:/fixture/input.json"], 0),
        (["--recovery-approval", "C:/fixture/proof.json"], 0),
        (["--recovery-input", "C:/fixture/input.json", "--recovery-approval", "C:/fixture/proof.json"], 1),
    ])
    def test_recovery_cli_requires_pair(self, extra, expected_calls, monkeypatch):
        calls = []
        fake_driver = SimpleNamespace(advance=lambda *args, **kw:
            calls.append((args, kw)) or {"status": "blocked"})
        fake_spec = SimpleNamespace(loader=SimpleNamespace(exec_module=lambda module: None))
        monkeypatch.setattr(importlib.util, "spec_from_file_location", lambda *a, **k: fake_spec)
        monkeypatch.setattr(importlib.util, "module_from_spec", lambda spec: fake_driver)
        monkeypatch.setattr(workflow.sys, "argv", ["handoff.py", "advance", "--id", "sample",
            "--workspace", "C:/fixture/worktree", "--model", "gpt-6-luna", *extra])
        assert workflow.main() in (1, 2)
        assert len(calls) == expected_calls
        if calls:
            assert calls[0][1]["recovery_input"] == Path("C:/fixture/input.json")
            assert calls[0][1]["recovery_approval"] == Path("C:/fixture/proof.json")
```

此类沿test_handoff.py现有imports、workflow实例及SimpleNamespace构造运行；最终node-id在该类内统一收集。
- [ ] Step2：跑新类红，然后实现两flag及main成对fail-loud。只有有成对值时向driver传新kwargs；无flag保持现有driver fake签名，返回码和json输出惯例不变。

```python
a.add_argument("--recovery-input")
a.add_argument("--recovery-approval")
# main内advance分支，在调用driver之前：
recovery_kwargs = {}
if bool(args.recovery_input) != bool(args.recovery_approval):
    raise ValueError("recovery_input_invalid")
if args.recovery_input:
    recovery_kwargs = {"recovery_input": Path(args.recovery_input),
                       "recovery_approval": Path(args.recovery_approval)}
```

保留当前其它关键字并展开recovery_kwargs。不加run、prepare、status、recover、release等参数；legacy flag拒绝是argparse标准行为。
- [ ] Step3：新增test_legacy_run_rejects_recovery_flags（pytest.raises(SystemExit) code2，run_stage spy=0）、test_advance_without_recovery_keeps_existing_kwargs、test_unicode_space_path_is_one_argument。路径使用数组，不拼shell，不给环境变量旁路。
- [ ] Step4：跑TestRecoveryCLI与既有test_advance_cli_passes_optional_model、test_active_lock_is_not_broken、test_model_success_is_not_delivery_success；完成后仅读`invoke.ps1 -Mode Workflow advance --help`/run --help核参数，不调用真实任务advance。

## Task 6: Guardian v4封存、重醒与一次阶段转交

**Files:** Modify guardian_entry.py、guardian_adapter.py；Test tests/test_guardian_entry.py、tests/test_guardian_adapter.py。
**Consumes:** Task1 snapshot/helpers、Task4 driver参数；既有live queue/LAN/plan/claim闸。
**Produces:** manifest optional `recovery_inputs: {task_id: {input: absolute_path, approval: absolute_path}}`；plan optional `recovery_bindings`，每项含input/approval refs、原task/attempt/design/workspace/原批准SHA；`_advance_task(task_id, workspace, authorization, executor, model_runner, *, recovery_paths: tuple[Path, Path] | None = None, recovery_batch: str | None = None)`；run_foreground在既有keyword签名末新增 `recovery_snapshots: dict[str, RecoverySnapshot] | None = None`。

- [ ] Step1：新增entry::TestRecoveryGuardianEntry与adapter::TestRecoveryFingerprint/TestRecoveryStageLoop。用现有candidate/manifest/executor helper生成fixture，假队列通过正式查询形状返回，不读真实队列；prepared linked-worktree/批准按真实fixture更新到latest empty_changes。首轮TestRecoveryGuardianEntry断言publicrequest匹配输入instructions、input_sha，不是只mock `_advance_task`后断言“已送达”。
- [ ] Step2：entry解析recovery_inputs exact pair schema：映射task_id必须在本批candidates/dispatchable内、workspaces与authorizations映射中；空映射等价无输入；不能带到transfer/excluded任务、不能给别的task或占用batch补。先load_snapshot核eligibility，生成plan.recovery_bindings，type(version)=int且version4未占用才选择v4；无input按原plan_batch版本生成。
- [ ] Step3：_assert_plan_sources在发布和运行前使用verify_source_files复核input/approval/doc字节，并比原recovery_bindings；不得从watch读取说明。**已经启动后**stage_validator只能核来源字节和新attempt的消费绑定，不能再次要求latest仍是原failed attempt，否则合法CI/review会被误拦。Task1 verify_source_files专做内容/身份校验、不重跑phase eligibility；启动前的真正eligibility在Task4锁内校验。
- [ ] Step4：adapter::_plan_sha256保持原v1/v2代码分支及原字段payload完全相同。v4使用v2的semantic dry_run payload，额外包含version=4、recovery_bindings，以及reasoning_projection=`{mode: legacy, contract_sha256: null}`或`{mode: governed, contract_sha256: 已封存值}`。本基线v3未实现，不能在本机制任务发明v3算法或启用governed；有原#658正式v3实现时才复用其已核投影/校验，否则非legacy模式报recovery_mode_unsupported。任何v3 baseline缺失保持unknown version拒绝，不“向后兼容”为v2。

```python
# 放在既有_plan_sha256版本分派中，不替换原v1/v2分支。
if version == 4:
    payload = {key: plan.get(key) for key in fields}
    payload.update(plan_fingerprint_version=4,
        dry_run=_semantic_dry_run(plan, plan.get("dry_run")),
        recovery_bindings=plan["recovery_bindings"],
        reasoning_projection=plan["reasoning_projection"])
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode("utf8")).hexdigest()
```

version/recovery schema必须在hash前validator核，不让dict.get缺值生成“有效hash”。v4必须非空合法recovery_bindings；legacy projection契约必须null。新增版本选择不改变default constant使所有无input任务自动v4。
- [ ] Step5：run_stages首次需要implement才传pair，拿driver正式结果中的`recovery_attempt_id`与`recovery_permission_status=reserved`后立即标本次已转交；后续阶段不传任何恢复kwargs。若driver首次blocked，即结束循环，不去普通advance重试。重醒先核batch record/同task状态：该binding已有new attempt，绝不再传或再launch implement；只在原有阶段闸允许test/review且同一已核实施HEAD时按正常链继续。最新仍empty_changes或unknown lock则保持blocked；不能因内存flag丢失重派。
- [ ] Step6：新增test_recovery_input_sha_changes_v4_digest、test_v1_v2_golden_unchanged、test_v3_not_reinterpreted、test_mapping_changed_before_run_refuses、test_data_changed_after_implement_blocks_ci、test_missing_approval_mapping_refuses、test_recovery_sent_once_not_into_review、test_second_wake_never_replays、test_first_failure_has_no_second_advance。v1/v2黄金payload/digest从本基线原算法计算并固化，不能在测试里调用同一新函数算expected镜像实现。
- [ ] Step7：回归既有test_v2_plan_fingerprint_drops_only_verified_raw_stdout_hashes、test_same_batch_changed_plan_cannot_resume_old_approval、test_guardian_advance_pins_explicit_luna_model、entry::test_different_batches_cannot_advance_same_live_queue_row、test_retire_stalled_batch_requires_external_evidence_then_releases_claim、test_plan_then_run_accepts_only_stdout_hash_drift、test_plan_then_run_blocks_semantic_receipt_tamper_before_stage_dispatch。新机制不调用retire、不改claims释放算法。

## Task 7: 逐项目CI、独立review与有限原生fixture

**Files:** 不增加白名单；各测试在Tasks1～6所属test文件内。主仓审阅文档由父会话持锁另登，不让模型写私有runtime或文档旁路。
**Deliverables:** 同一implementation HEAD的CI原文/摘要/JUnit、独立review；输入传输的脱敏原生报告另列，不能冒充实际业务恢复。

- [ ] Step1：确认14路径diff精确覆盖，无旧任务/工作树泄漏；记录Native implementation HEAD、patch-id、source/design/批准SHA。Native父执行者逐task正常分支提交，任何派生模型不commit；不伪造Workflow成功attempt或implementation_head状态字段。
- [ ] Step2：先收集拟新增节点，核实际classes名称；从独立机制工作树的`0-学习与工具/codex-handoff`启动以下命令，Python绝对路径必须重新由Probe解析核存在，不根目录混跑。以下绝对runtime是本轮已核路径，不保证未来自动有效。

```powershell
# -WorkingDirectory由调用工具指定为独立机制工作树的codex-handoff子项目。
& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest --collect-only -q "tests/test_recovery_input.py::TestRecoverySchema" "tests/test_recovery_input.py::TestRecoveryLocations" "tests/test_recovery_input.py::TestRecoveryBindings" "tests/test_recovery_input.py::TestRecoveryPrompt" "tests/test_workflow_state.py::TestRecoveryReservation" "tests/test_model_provider.py::TestRecoveryInputEvidence" "tests/test_workflow_driver.py::TestRecoveryDriver" "tests/test_handoff.py::TestRecoveryCLI" "tests/test_guardian_entry.py::TestRecoveryGuardianEntry" "tests/test_guardian_adapter.py::TestRecoveryFingerprint" "tests/test_guardian_adapter.py::TestRecoveryStageLoop"
```

上列都是拟新增节点，本轮未存在/未运行。每Task红绿用其类node-id，不写`-k`。真实既有node-id已通过rg核存在；Task2额外原节点为test_duplicate_attempt_does_not_replace_first、test_unknown_crash_keeps_lock_and_evidence、test_finish_attempt_rejects_untrusted_direct_outcome、test_attempt_prepare_callback_runs_only_after_lock_and_persists_with_attempt。
- [ ] Step3：affected CI roots必须由实际矩阵发现重新核为codex-handoff；完整规范CI从该cwd运行，不用invoke.ps1 Test（其默认全tests和cwd形状不能代替规范driver CI目标）。

```powershell
& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest -q --tb=short --junit-xml=pytest-result.xml
```

stdout/stderr分别留原文、退出码直接取被执行进程、JUnit归档到正式driver attempt目录并hash，CI报告target.argv/cwd/nodeid与现时ci.yml形状一致。超过几分钟的测试由正常长任务哨兵机制留exit，不不断tail日志。
- [ ] Step4：在纯master独立对照树以相同canonical cwd/命令跑既有受影响节点和完整CI。新增节点master不存在，明确标not applicable，不能复制新测试到master冒称原基线。旧失败逐条对照；新增失败只在分支出现即停，不改断言/skip、不给pytest-result旧报告换hash凑绿。
- [ ] Step5：按requesting-code-review技能派独立无历史上下文的Luna审阅者（需本计划审批明确许可该review；reviewer显式model=gpt-6-luna，fork_turns=none），仅读同独立机制task/implementation HEAD，输入引用设计、计划、14路径批准及CI原文。父执行者保存review结论与审阅HEAD绑定；不是调用Workflow review并手填阶段state。不在源会话改变子任务模型；review finding按同分支修复，范围外修补另审。
- [ ] Step6：在实施验证授权若明确包含一次有限原生传输probe，建立全新脱敏fixture task（不命名为#658，假队列经既有fixture正规路径），绑定latest empty_changes与外部假批准，Luna freshthread、sandbox workspace-write。instructions只要求检查一个绝对mock plan路径，Test-Path/Get-FileHash后Get-Content最多20行，并写白名单`probe-output.txt`为OK；不存在真实业务数据。不要将fixture fake批准用到真实STATE/队列；父守护方建立夹具并核目录隔离，模型不写private runtime。
- [ ] Step7：捕获公开request/result/events/session及SHA；核完整recovery context/effective digest、实际工具先存在/hash/有限窗口、白名单产物三层。第1层通过、第2层未知时分别报告；缺证或失败不自动再试。normal native fixture pipeline只能在审批绑定的次数范围执行；本轮计划编制不创建或运行该fixture。
- [ ] Step8：review通过只在Native交付报告标“可提交发布审阅，未接受上线”；不设置Workflow release-ready state。ff、入口切换和#658实际恢复另审。实施审批若不含原生probe，明确保留验收缺口。

## Task 8: 发布准备与#658恢复前置（仅报告，不执行）

**Files:** 无新增实现路径；只用Native发布报告、正式只读status及审批登记工具，不调用未形成task seal的release。

- [ ] Step1：生成绑定Native implementation HEAD的发布准备报告，不调用没有正式task state的Workflow release、不ff、不activation。核正式invoke来自主仓，driver/provider/Guardian源文件SHA是待发布版本；不能调用独立树runner直接运行原#658。
- [ ] Step2：说明#658原worktree/design HEAD/11路径批准仍保留。机制发布后，在获准脱敏fixture中由正式主仓入口控制旧格式任务linked tree，证明task code anchor与entry source分离、原批准/白名单、mutex/fingerprint仍正常；若真实入口版本绑定拒绝，停下提出有限迁移设计，不修改旧封印。
- [ ] Step3：列逐项待审：独立机制ff；正式入口activation；B-1005_入口恢复实施退役；新恢复输入/单次launch。不能将实施计划批准一次包含这些动作。原#658 input/hash/claims本轮不改。恢复件具体内容只沿已审设计§6，不再要求重复审核原11路径。
- [ ] Step4：只在上述后续审批和当次前置实测闭合后，经正式retire/new immutable plan/paired recovery approval派一次；这是未来审批后的动作，不在本计划实施授权内。没有本轮自动调度器，不承诺“审批一来自动继续”。

## 规格覆盖、自审与本轮检查

| 已批设计范围 | 对应任务 |
|---|---|
| strict外部输入/审批、冻结对象/路径/文件hash | Task1 |
| 一次launch、锁内重验、新attempt不动旧attempt | Task2/Task4 |
| 真实prompt追加与公开request/result | Task3/Task4 |
| 正式CLI/Guardian传递、历史v1/v2/v3和新v4 | Task5/Task6 |
| 两次失败/空产物保护、CI/review、原生分层证据 | Task4/Task7 |
| 独立建造、正常发布、执行版本兼容、原批保留 | Task8 |

接口自审：Snapshot唯一数据源是Task1；state只消费binding；provider metadata由append_context生成/反校验；entry启动后的内容复核用verify_source_files，不误用latest-failure eligibility；只有driver锁内load/revalidate接收当前旧attempt。不得换同名可变dict/API。

本轮仅读真实源码/既有测试helper/node-id/ci.yml、运行Probe与Workflow status、写计划。设计SHA已Get-FileHash重核一致；#658最新状态仍blocked/busy=false/empty_changes，未形成implementation HEAD、CI或review。所有拟新增fixture/node-id均未创建或执行，本计划中的预期结果不是实测通过。

2026-10-05 10:03:41 +08:00本机文档检查：隔离Python提取13个python fenced blocks并逐个ast.parse，exit0，全部语法可解析；任务标题计数8。禁止占位词/未写函数体扫描无命中；接口仅列签名、实际步骤含核心算法与fixture。AST成功不是运行测试通过；本文件大小约54KB，执行读取必须用≤200行窗口。

实现准备仍需独立Native新工单/队列/linked workspace以及绑定设计/计划/14路径的实施授权证据；不捏造Workflow task seal，执行版本边界在正常发布前仍需原生兼容核验。本轮不改原设计文件status或哈希来记录批准；人答链只通过队列和本计划留痕。

## 计划审阅与执行方法

建议批准本计划及14路径隔离建造/逐项目验证，采用Native就地执行Tasks1～6；阶段内红绿，最终由正式freshthread Luna独立review。接口紧密关联，Native比每Task开新代理更少重复上下文；所有派生测试模型仍显式Luna。可选Subagent-driven只在明确选择后按技能派发Luna，不默认启动。

§四#263需要明确答复：A推荐批准计划、Native独立机制14路径实现/逐项目验证，是否包含一次脱敏原生传输probe明确写出；B修订后再审。ff/真实切换、新失败批退役、#658重派均另审，原#658实施批准保留。
