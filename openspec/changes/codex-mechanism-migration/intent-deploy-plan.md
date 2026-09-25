# Codex intent→deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Shao Peishen 已指定 inline 实施；不派子代理。

**Goal:** 将已工作的任务驱动建造流程接到 Codex，在现有队列、泳道状态机、opener 批处理和 LAN 收口之间形成可恢复、可取证的阶段接力。

**Architecture:** `handoff.py` 保留单任务队列/HEAD 锚与 provider；新增小型阶段判定和驱动模块。泳道动作、暂停、心跳、部署转出仍只调用现有状态机；opener、CI、ff 与 LAN 收口各调用原入口，不建立第二套规则或真实业务任务池。

**Tech Stack:** Windows PowerShell 7、隔离 CPython 3.14、pytest、Git worktree、现有 Codex provider/OpenSpec/项目专用队列工具。

**Spec:** `openspec/changes/codex-mechanism-migration/intent-deploy-design.md`（2026-09-25 已由 Shao Peishen 书面批准）；另读同包 `intent.md`、`tasks.md`，旧三消费者通过项不重跑。

## Global Constraints

- Claude 已封存；不执行、不回退、不把源端 API 改名当 Codex 等价物。中英文 last30days 与其他无关项目配置不碰。
- 项目正本 `C:/Dev/zhuopin-ai`；只用 `工具-队列查询.py` 读队列；写队列须 acquire→edit/append→release，§二由 ZhuopinCommitSweep 落库。已有脏文件、旧分支和工作树不清理。
- 默认消费者/自动化保持暂停；`-ConsumerEnabled`、返回 0、`turn.completed`、`OPENER_DONE`、§二登记均不单独构成交付通过。真实触发器未验收不得称“自动继续”。
- 设计审、ff、生产 `.51` 与真实对外发送逐项授权；off/unknown LAN 对 `.51` fail closed。L2 不代签，ASIL C/D 不自动参与，mock/脱敏与 OEM 隔离先行。
- 原生证据至少含源 task/batch/lane ID、Codex thread、HEAD、worktree、工具/hook 事件、产物哈希、目标 CI 与独立 review；缺一项不跨相应阶段。
- 实施时先以 `using-git-worktrees` 在隔离工作树执行；每片 TDD、针对性测试、review、按项目 §二批次提交。真实 `.51` 只在 On LAN 和该项授权后验收。

## File map

| 文件 | 唯一职责 |
|---|---|
| `0-学习与工具/codex-handoff/workflow_state.py`（新） | 单任务阶段记录的原子读写、attempt 锁与重启判定；不存泳道状态 |
| `0-学习与工具/codex-handoff/workflow_gate.py`（新） | 根据现有产物/模型/CI/review 证据返回下一阶段或明确停因；调用现有动作分类器，不复制表 |
| `0-学习与工具/codex-handoff/workflow_driver.py`（新） | 单任务阶段调度；以注入的命令执行器调用现有 provider、OpenSpec、CI、review 入口 |
| `0-学习与工具/codex-handoff/guardian_adapter.py`（新） | 看护件/泳道批次与单任务驱动连接；调用现有泳道状态机、opener 生成/lint/批处理/等待工具 |
| `0-学习与工具/codex-handoff/handoff.py`（改） | 在既有 `prepare/run/probe` 外暴露受控 `advance/status/recover` CLI；已有 `run_stage` 在批准设计后认 `design_head` 为实施起点，review 仍认 `implementation_head` |
| `0-学习与工具/工具-opener生成.py`、`.agents/skills/zhuopin-lane-watch/SKILL.md`（必要时改） | 只在 guardian 接缝实证通过后开放 Codex guardian；源端能力仍 fail-loud |
| `0-学习与工具/codex-handoff/tests/test_workflow_*.py`（新） | 每单元针对性的状态、证据、调度、看护和发布边界测试 |
| `0-学习与工具/codex-handoff/README.md`、本变更包 `tasks.md`/`acceptance.md`（改） | 写入真正运行入口、停点、证据与未闭合项；任务勾选不等于验收 |

## Review Focus

1. **同一任务重复触发**：两个 `advance` 不可同时启动模型；第二个只得到 busy，原 attempt 证据不变（Task 1）。
2. **授权文件内容改变**：路径相同但哈希漂移时不得复用 design/ff 批准（Task 2）。
3. **旧哨兵/错 thread 证据**：mtime 早于本 attempt 或 thread/workspace 不符时不得进入测试/review（Task 2）。
4. **批内局部失败**：依赖项停、独立泳道继续，零心跳的 MAX-WAIT 不误判为完成（Task 4）。
5. **off/unknown LAN 与重复部署授权**：只转出；不执行 `.51`，不能把第一项授权借给第二项（Task 5）。

---

### Task 1: 单任务阶段记录与重启恢复

**Files:** Create `0-学习与工具/codex-handoff/workflow_state.py`, `0-学习与工具/codex-handoff/tests/test_workflow_state.py`; modify `handoff.py` 的 `prepare` 状态写入，保留旧键兼容。

**Interfaces:** Consumes `handoff.py` 已有 `STATE/runs/<id>/state.json`、`source_head`；produces `load_state(task_id: str) -> dict`, `begin_attempt(task_id: str, phase: str, expected_head: str) -> dict`, `finish_attempt(task_id: str, attempt_id: str, outcome: dict) -> dict`, `recover(task_id: str, observed: dict) -> dict`。状态采用 `phase_status` 与 append-only `attempts`，`delivery_accepted` 默认 false；`running.lock` 用原有 exclusive-create 语义。

- [ ] **Step 1: 写失败测试。** 用 `tmp_path` 创建 prepared 状态；同 task 调两次 `begin_attempt`，断言第二次 `FileExistsError`、首 attempt ID 未变；构造残留锁/未知进程，`recover` 返回 `blocked_unknown` 且不删锁；完成后重启读取同一证据引用。
  ```python
  first = state.begin_attempt("sample", "proposal", "abc")
  with pytest.raises(FileExistsError):
      state.begin_attempt("sample", "proposal", "abc")
  assert state.load_state("sample")["attempts"][-1]["id"] == first["id"]
  ```
- [ ] **Step 2: 跑 RED。** `& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest "0-学习与工具/codex-handoff/tests/test_workflow_state.py" -q -p no:cacheprovider`；预期缺模块/断言失败，不能启动模型。
- [ ] **Step 3: 实现。** 状态文件临时文件 `replace` 原子落盘；attempt ID 用 UUID；锁已有时只读报 busy；`recover` 只在证据明确证明进程结束且结果可验证时结算，未知状态保留现场。
  ```python
  def begin_attempt(task_id: str, phase: str, expected_head: str) -> dict:
      current = load_state(task_id)
      if current["source_head"] != expected_head:
          raise ValueError("HEAD drift")
      folder = STATE / "runs" / task_id
      with (folder / "running.lock").open("x", encoding="utf8") as lock:
          lock.write(phase)
      attempt = {"id": uuid.uuid4().hex, "phase": phase, "status": "running"}
      current.setdefault("attempts", []).append(attempt)
      write_json(folder / "state.json", current)
      return attempt
  ```
- [ ] **Step 4: 跑 GREEN 和旧回归。** 上述目标测试及 `tests/test_handoff.py::test_active_lock_is_not_broken`、`::test_model_success_is_not_delivery_success`。确认没有改旧 prepare/run 的外部结果。
- [ ] **Step 5: 独立审查并登记本片 §二 批次，核实际 commit。** 文件清单只含本片；不把预存脏文件纳入。

### Task 2: 证据闸与阶段迁移表

**Files:** Create `workflow_gate.py`, `tests/test_workflow_gate.py`；修改 `workflow_state.py` 只补证据引用字段。

**Interfaces:** Consumes Task 1 状态、`model_provider.py` 结果及原生证据路径、OpenSpec/CI/review 机器报告、现有 `工具-泳道看护状态机.py::classify`；produces `decide_next(state: dict, evidence: dict) -> dict`，返回 `{"next_phase": str | None, "status": "ready" | "paused" | "blocked", "reason": str}`。顺序固定 `intent→proposal→design_pause→implement→test→review→release_ready`；deploy 不由此函数执行。

- [ ] **Step 1: 写 RED 参数化表。** 有队列/intent/HEAD 才放 proposal；OpenSpec 草稿校验/哈希齐才停 design；设计批准原文和哈希匹配才放 implement；模型 `output_needs_review` 还必须同 thread/workspace 的 tool/hook 与产物哈希；CI 目标结果齐才放 review；独立 review 结论与 implementation HEAD 对齐才放 release_ready。另测设计文件被改、旧 mtime 哨兵、错 thread、未知动作、exit0 无工具/产物均 blocked 或 paused。
  ```python
  decision = gate.decide_next(state, {"model_status": "output_needs_review", "exit_code": 0})
  assert decision["status"] == "blocked"
  assert decision["next_phase"] is None
  ```
- [ ] **Step 2: 跑 RED。** `& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest "0-学习与工具/codex-handoff/tests/test_workflow_gate.py" -q -p no:cacheprovider`。
- [ ] **Step 3: 实现纯判定。** 证据路径存在且 SHA256 等于登记值；授权绑定任务+设计版本+HEAD；复用运行时 `classify(action_key)`，未知按它返回的 🟡；不在本模块落泳道 pause 或发通知。
  ```python
  def decide_next(state: dict, evidence: dict) -> dict:
      if state.get("phase") == "implement" and not evidence.get("native_tool_events"):
          return {"next_phase": None, "status": "blocked", "reason": "missing native tool evidence"}
      if state.get("phase") == "proposal" and not evidence.get("design_approval_sha256"):
          return {"next_phase": None, "status": "paused", "reason": "design review required"}
      if state.get("phase") == "intent" and evidence.get("queue_row") and evidence.get("intent_sha256"):
          return {"next_phase": "proposal", "status": "ready", "reason": "intent verified"}
      return {"next_phase": None, "status": "blocked", "reason": "phase evidence incomplete"}
  ```
- [ ] **Step 4: 跑 GREEN。** 本片测试加 `tests/test_model_provider.py::TestProvider::test_success_still_needs_product_acceptance`；静态核 `rg` 确认未复制四档字典和 LAN 部署 SOP。
- [ ] **Step 5: review、§二 登记并核实际提交。** 机器输出中明确 `blocked/paused/ready`，不是布尔通过。

### Task 3: 单任务 Codex 阶段驱动

**Files:** Create `workflow_driver.py`, `tests/test_workflow_driver.py`；modify `handoff.py` 增 `advance/status/recover` 子命令，`README.md` 增用法。必要时只在 `model_provider.py` 增缺失的证据读取接口，不改变已验收消费者。

**Interfaces:** Consumes Task 1 `begin_attempt/finish_attempt`、Task 2 `decide_next`、已有 `handoff.prepare/run_stage`、`工具-CI矩阵发现.py` 和 OpenSpec CLI；produces `advance(task_id: str, workspace: Path, authorization: Path | None, executor: Callable) -> dict` 与 `status(task_id: str) -> dict`。本模块内的 `collect_evidence(task_id, workspace)` 只读产物与原生审计，`current_head(workspace)` 用现有 `handoff.git`，`run_one_stage(attempt, workspace, authorization, executor)` 根据 phase 调用现有阶段入口并调用 `finish_attempt`。`proposal` 用同一 provider 在隔离 worktree 生成实际 OpenSpec 文件并提交，记录 `design_head` 与设计文件哈希；设计批准必须绑定这个哈希。随后 `run_stage implement` 以 `design_head` 为预期 HEAD（旧任务无该键时仍用 `source_head`），review 仍以 `implementation_head` 为预期 HEAD。`executor` 以 argv 数组调用，不拼 shell 文本；只启动一次被判为 ready 的阶段。

- [ ] **Step 1: 写 RED。** fake executor 记录调用：proposal 在隔离 worktree 写实际 `proposal.md/design.md/tasks.md` 并提交 `design_head`；不批准时零次 implement；批准原文绑定 design SHA256/HEAD 后只在干净隔离 worktree 调一次 provider；旧 `source_head` 任务仍兼容；测试按 CI 矩阵逐子项目、失败停止；review 使用记录的 implementation HEAD 和新轮次，产出可解析 `review.json`（HEAD/结论/findings）；重复 `advance` 不多起进程；`status/recover` 只读不触发模型。真实 provider 仍 mock，测试不接外网。
  ```python
  result = driver.advance("sample", worktree, None, fake_executor)
  assert result["status"] == "paused"
  assert not any("implement" in call for call in calls)
  ```
- [ ] **Step 2: 跑 RED。** `& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest "0-学习与工具/codex-handoff/tests/test_workflow_driver.py" -q -p no:cacheprovider`。
- [ ] **Step 3: 实现最小驱动。** 保留 `handoff.py run --phase plan|implement|review` 兼容入口；新 `advance` 先 `decide_next`，以 `begin_attempt` 锁定。proposal 通过 provider 的 workspace-write 在独立工作树产出 OpenSpec 三件，校验并 commit 后记录 `design_head`；implement 在该 HEAD 的干净工作树继续；test 逐子项目写机器报告；review 在独立 Codex 轮次输出结构化 `review.json`，需与 implementation HEAD 一致。每次写原生命令/报告/哈希，最后重新判定下一步；不在同一次模型退出后无限自旋。
  ```python
  def advance(task_id, workspace, authorization, executor):
      decision = decide_next(load_state(task_id), collect_evidence(task_id, workspace))
      if decision["status"] != "ready":
          return decision
      attempt = begin_attempt(task_id, decision["next_phase"], current_head(workspace))
      return run_one_stage(attempt, workspace, authorization, executor)
  ```
- [ ] **Step 4: 跑 GREEN 和旧接口回归。** 本片测试、`tests/test_handoff.py::test_implementation_commit_can_be_reviewed_in_same_task`、`::test_review_rejects_drift_from_recorded_implementation`、受影响 CI 发现器测试。核 CLI `--help` 与隔离测试 task `sample-task` 的 `invoke.ps1 -Mode Workflow status --id sample-task` 不运行模型。
- [ ] **Step 5: review、§二 登记并核实际提交。** 交付可重启的单任务离线链；此时尚不宣称 guardian 或无人值守常驻。

### Task 4: Claude 看护行为的 Codex guardian 接缝

**Files:** Create `guardian_adapter.py`, `tests/test_guardian_adapter.py`；必要时 modify `工具-opener生成.py` 的 Codex guardian fail-loud 分支、对应 `test_工具-opener生成.py`；更新 `.agents/skills/zhuopin-lane-watch/SKILL.md`。不改 `工具-泳道看护状态机.py` 判据或 LAN 正本。

**Interfaces:** Consumes Task 3 `advance`，现有状态机 CLI `criteria/classify/lan-status/pause/resume/transfer-out/heartbeat/check-heartbeat/summary`，现有 `工具-opener批处理执行v2.ps1 -DryRun -Yes/-ConsumerEnabled`、`工具-泳道看护等待.py wait`；produces `plan_batch(batch_id: str, queue_rows: list[dict], lan: dict) -> dict`、`dispatch_batch(plan: dict, enabled: bool, executor: Callable) -> dict`、`observe_batch(batch_id: str) -> dict`。本模块内的 `parse_dry_run(stdout: str) -> list[str]` 解析现有 runner 输出、失败即报错；batch/lane/task ID 明确映射，候选/触碰区来自专用查询工具。

- [ ] **Step 1: 写 RED。** 用隔离队列夹具验证 off/unknown LAN 排除内网活、触碰区重叠分波、锁工具最后波、默认上限 10/并行最多 4/错峰至少 90 秒（运行值从既有正本现取或受测配置）；`DryRun` 解出的泳道与计划不等即禁止 dispatch；一泳道失败只阻断依赖链；零心跳 `MAX-WAIT` 不是完成；用户只说“开启泳道看护”不能偷偷转成无头；disabled 零模型进程。
  ```python
  plan = guardian.plan_batch("B-fixture", rows, {"effective": "off"})
  assert "lan_only" not in plan["dispatchable_ids"]
  assert plan["waves"][-1]["kind"] == "lock_tools"
  ```
- [ ] **Step 2: 跑 RED。** `& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest "0-学习与工具/codex-handoff/tests/test_guardian_adapter.py" -q -p no:cacheprovider`；仅新接缝类，尚不重跑生成器旧类。
- [ ] **Step 3: 实现薄接缝。** 只调用状态机原命令/函数落档和等待；生成器在 Codex guardian 使用本机可用入口替换源端标题/Task 指令，输出先经现有 lint；无真实持续触发器时只提供前台看护并标 `needs_manual_wake`，不创建隐形 cron。
  ```python
  def dispatch_batch(plan, enabled, executor):
      runner = ROOT / "0-学习与工具" / "工具-opener批处理执行v2.ps1"
      argv = ["pwsh", "-NoProfile", "-File", str(runner), "-Plan", plan["file"], "-DryRun", "-Yes",
              "-MaxParallel", str(min(4, plan["max_parallel"])), "-StaggerSec", "90"]
      parsed_ids = parse_dry_run(executor(argv)["stdout"])
      if parsed_ids != plan["lane_ids"]:
          return {"status": "blocked", "reason": "lane parse mismatch"}
      if not enabled:
          return {"status": "paused", "reason": "consumer disabled"}
      result = executor(["pwsh", "-NoProfile", "-File", str(runner),
                         "-Plan", plan["file"], "-Yes", "-ConsumerEnabled",
                         "-MaxParallel", str(min(4, plan["max_parallel"])), "-StaggerSec", "90"])
      return {"status": "output_needs_review", "runner": result}
  ```
- [ ] **Step 4: 跑 GREEN 与源契约回归。** 新类、`test_工具-泳道看护等待.py::LaneWatchWaitTests`、`test_工具-泳道看护状态机.py::LaneParsingDryRunTests`、`test_工具-opener生成.py::VariantGuardianTests`；用脱敏看护件做 `dry-run` 和 lint，保留解析回执。若 guardian 无实际 Codex 执行接缝，维持 fail-loud，不先改 skill 为“已迁移”。
- [ ] **Step 5: review、§二 登记并核实际提交。** 交付前台看护与批量依赖处理；后台自动能力以真实触发器验收结果单独判定。

### Task 5: 发布准备、ff 与 LAN 转出的授权边界

**Files:** Create `workflow_release.py`, `tests/test_workflow_release.py`；modify `workflow_driver.py` 只增加 `release_ready/transfer` 接点；更新 README/acceptance。既有 `工具-泳道分支合入.ps1`、`工具-待合分支巡检.ps1` 与 LAN skill 只调用，不复制逻辑。

**Interfaces:** Consumes Task 2 的 `release_ready` 判定、现有状态机 `pause_lane/transfer_out_lane/authorize_deploy`；produces `prepare_release(task_id: str, evidence: dict) -> dict` 和 `transfer_deploy(task_id: str, batch: str, lane: str, item: str) -> dict`。后者只记录转出及指针，不发起 `.51` 连接。ff 由既有授权入口负责；本模块只输出可审阅的待授权件。

- [ ] **Step 1: 写 RED。** 缺 review/CI 不得 release-ready；未授权 ff 不调用合入；patch-id 已在 master 时记录 skip；`.51` off/unknown 时只转出、零 deploy；重复授权不能跨 item；external_send/L2/ASIL 动作恒拒绝自动执行。
  ```python
  result = release.transfer_deploy("sample", "B-fixture", "A1", "deploy-1")
  assert result["status"] == "transferred"
  assert not any(".51" in call for call in command_log)
  ```
- [ ] **Step 2: 跑 RED。** 隔离 Python `-m pytest "0-学习与工具/codex-handoff/tests/test_workflow_release.py" -q -p no:cacheprovider`。
- [ ] **Step 3: 实现。** 只把 `release_ready` 证据、人要答的逐项问题、LAN 指针落盘；需要执行 `.51` 时重新现读 LAN 正本并走其当次探针/授权/快照→执行→冒烟→回滚纪律，当前 off LAN 不启动。真实对外发送不提供调度命令。
  ```python
  def transfer_deploy(task_id, batch, lane, item):
      transfer = lane_machine.transfer_out_lane(batch=batch, wave=1, lane=lane,
                                                action_key="deploy_51", note=item, notify_fn=None)
      return {"status": "transferred", "item": item,
              "pointer": lane_machine.deploy_discipline_pointer(), "evidence": transfer}
  ```
- [ ] **Step 4: 跑 GREEN 与状态机 deploy 授权/重复绑定回归。** 使用隔离状态路径和 fake LAN prober；不碰生产 `.51`。核没有第二套快照/冒烟/回滚代码。
- [ ] **Step 5: review、§二 登记并核实际提交。** ff、生产部署仍由既有逐项授权触发，不能以本模块的 release-ready 自动执行。

### Task 6: 原生端到端与现场调度验收

**Files:** Create `0-学习与工具/codex-handoff/tests/test_workflow_e2e.py`（离线契约集成）；modify 本包 `acceptance.md`、`tasks.md`、README。实际原生证据放本机隔离 `reports/mechanism-migration-648/`，不提交凭据或原始敏感 payload。

**Interfaces:** Consumes Tasks 1–5 公共入口；produces 可复查 acceptance 矩阵与每项 `pass/fail/blocked/evidence-gap`。不更改三消费者已验收状态。

- [ ] **Step 1: 写完整 E2E 夹具并先跑 RED。** 脱敏单任务从真实队列查询接口的隔离替身进入：intent→proposal/tasks→design 停→该项授权→独立 worktree Codex 建造→CI 矩阵目标→独立 review→release-ready；再跑 10 个反例：未批设计、未知动作、未信任 hook、HEAD 漂移、CI 失败、重复触发、崩溃恢复、旧哨兵、off/unknown LAN、越权 ff/发送。批量另证依赖停链/独立继续/错峰/心跳。
- [ ] **Step 2: 跑最小失败例，排除夹具误接真实系统。** `& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest "0-学习与工具/codex-handoff/tests/test_workflow_e2e.py" -q -p no:cacheprovider`；所有 fake 网络/信号/发送入口在测试进程内注入。
- [ ] **Step 3: 修到 GREEN 后跑一次真实 Codex 隔离建造。** 用全新测试 worktree、随机无敏感任务 ID、正常已信任 hooks、`invoke.ps1` 运行，记录原生 thread/turn/tool/hook、产物 SHA256、CI 报告和独立 review。只验证本地建造，不 ff、不触 `.51`、不外发；失败保留全部证据。
- [ ] **Step 4: 验证 guardian 及调度真实性。** 若仅前台会话可用，验 `needs_manual_wake` 并把后台项标 blocked；若启用 Windows/Codex automation，先保存账户/触发器/停止开关和旧消费者 Disabled 证据，再以一次受控实际触发验单消费者与产物，不以配置存在代替调度。五个既有 PAUSED 自动化未经逐项授权不得启用。
- [ ] **Step 5: 最终独立 review、逐项证据矩阵、§二 登记与实际 commit 核验。** `#648` 只有在整套必要机制真实通过后才能改 done；`.51` 如仍 off LAN，明确记录该生产项 blocked，业务开发闸按原批准范围判定，不把离线负例写为生产通过。计划任务复核只认机器证据，不认勾选。

## Execution handoff

先由 Shao Peishen 审阅本计划。批准后按既定 inline 方式调用 `executing-plans`，实施 Task 1→6；每片失败即停依赖步骤、修复后才前进。期间需新的 design、ff、生产或真实发送决定时呈现该项具体产物和证据再请求逐项授权；已有授权不重复索取。
