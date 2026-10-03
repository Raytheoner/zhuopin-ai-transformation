# Rolling Business Task Loop and Panorama Rebaseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. `subagent-driven-development` is an alternate execution method only if Shao Peishen explicitly selects delegation. Steps use checkbox syntax for tracking.

**Goal:** Reconcile the authoritative panorama and implementation route with the approved rolling-scope policy, and define a live-session loop that starts eligible business tasks without treating target dates as prerequisites.

**Architecture:** Keep the panorama and its schedule as the strategic source of truth; add a task-readiness and launch loop driven by Probe, public Guardian/Workflow status and the official queue interface. Rebaseline the nine governed document units and regenerate the two DOCX outputs in one audited batch. Q9 APQP remains outside the formal scene count until specialist evidence selects its pilot stage and the scene design passes review.

**Tech Stack:** Markdown and HTML source documents; official PowerShell Probe and queue/lock tools; project Python runtime and `md2word.py` for DOCX regeneration; document rendering for visual review.

**Spec:** `docs/superpowers/specs/2026-10-02-rolling-business-task-loop-design.md`

## Global Constraints

- “Phase 1/Phase 2 表示战略批次与目标节点，不是开工窗口。排期用于排序和最迟节点管理，不压住已满足前置条件的任务。”
- “无真实前置阻塞且输入材料已齐的业务任务，应进入正式启动集合，并在既有并发能力内立即派入获准车道；超出并发能力的任务保持容量排队，不得误标为业务依赖阻塞。”
- “真实并发仍受当前车道上限、同泳道串行与共享触碰约束。”
- “启动须走正式 manifest、Guardian 和获准隔离工作树。”
- “ff、生产部署、对外发送、L2 决策继续按具体事项逐项授权。”
- “新场景经查重、业务意图签认和设计审查后纳入正式范围。”
- “未签认的阈值、红线和验收标准不设默认值。”
- “数据先 mock/脱敏；客户数据严格隔离。”
- Queue reads use `工具-队列查询.py --digest --actionable` or official `--row N --section 一 --field all`; never read or grep queue source files directly.
- Preserve all pre-existing dirty files, branches and worktrees. The master-side caretaker does not create business branches or edit business code.
- Do not start background polling when the Codex session ends.

## Review Focus

1. **Stale queue state vs. actual delivery:** before resuming an open/partial row, compare its current artifact, sign-off ledger and log; the owning task must record whether work is already merged or still branch-only.
2. **Passed target date vs. missing material:** a past or near target date cannot clear a missing sample/version prerequisite; preserve the blocker and its owner.
3. **Q9/Q4 shared Control Plan input:** keep the APQP stage decision and PPAP final-package decision separate; record a shared source/version reference and check there is no duplicate acceptance rule.
4. **35 vs. 42 scope drift and stale phase prose:** verify scene totals, Phase 1/2 lists, schedule rows and version headers agree across the authoritative documents; report historical snapshots separately instead of rewriting them.
5. **Live session vs. project completion:** prove the completion predicate uses the signed formal scope, roadmap goals and associated actionable business rows; no background continuation is claimed after the session closes.

## File and Responsibility Map

| File | Responsibility in this plan |
|---|---|
| `docs/superpowers/specs/2026-10-02-rolling-business-task-loop-design.md` | Approved source design; read-only during implementation |
| `1-转型规划/0-全景路线图/文档台账-自动生成.md` | Governed-document index; use targeted lookup before route edits and regenerate if its source changes |
| `1-转型规划/0-全景路线图/卓品智能AI转型全景规划.md` | Strategic scope, authoritative schedule table and §0.2 change record |
| `1-转型规划/0-全景路线图/卓品智能AI转型实施计划（最新版）.md` | Scene inventory, dependencies, execution route and target dates |
| `1-转型规划/0-全景路线图/跨场景前置数据与知识库任务总表.md` | Cross-scene material and dependency readiness |
| `1-转型规划/0-全景路线图/全景甘特图-场景排期.html` | Visual schedule mirror; confirm canonical path from the governed-document inventory before editing |
| `1-转型规划/0-全景路线图/业务特性驱动的四链联动蓝图-42场景重梳-2026-07-05.md` | Review for impact; edit only if approved decisions alter an endpoint or chain link |
| `CLAUDE.md` | Current-progress and scene-total references |
| `1-转型规划/0-全景路线图/全景路线图重组机制与变更日志.md` | Append the structural rebaseline record |
| `1-转型规划/0-全景路线图/session接力-Phase1收口.md` | Refresh the rolling handoff snapshot and next-session focus |
| `1-转型规划/0-全景路线图/卓品智能AI转型全景规划.docx` | Regenerated output from the panorama Markdown |
| `1-转型规划/0-全景路线图/卓品智能AI转型实施计划（最新版）.docx` | Regenerated output from the implementation-plan Markdown |
| `1-转型规划/0-全景路线图/移交单-全景路线图-2026-10-02-滚动范围与Q9-APQP重基线.md` | New execution handoff with `status: 待执行`, signed scope decisions and freeze/release evidence |
| Official queue target returned by the queue/lock tools | Rebaseline row and §三 freeze marker; never edit a queue file directly |

The rebaseline skill calls these nine governed document units: the eight Markdown/HTML source entries above (the four-chain blueprint is conditional) plus the two DOCX outputs, which together form unit 9. The generated document ledger is the path/status authority; if it omits a listed canonical file, resolve the discrepancy before editing and record the result in the handoff. The new execution handoff and regenerated ledger are supporting audit artifacts, not additions to the nine-unit count.

---

### Task 1: Establish the Rebaseline Handoff and Freeze Gate

**Files:**
- Read: `docs/superpowers/specs/2026-10-02-rolling-business-task-loop-design.md`
- Read: `0-学习与工具/codex-handoff/业务泳道看护接力-2026-10-02.md`
- Create: `1-转型规划/0-全景路线图/移交单-全景路线图-2026-10-02-滚动范围与Q9-APQP重基线.md`
- Modify through the official lock tool only: the existing rebaseline queue row and §三 freeze marker

**Interfaces:**
- Consumes: approved design decisions and current OP-1002 handoff status (`待接棒`).
- Produces: an execution handoff with `status: 待执行`, decision links, scope boundary, touched-document set and release condition.

- [ ] **Step 1: Refresh the execution baseline**

Run `& '.\0-学习与工具\codex-handoff\invoke.ps1' -Mode Probe` and the official queue digest. Query only the selected current rows `#592`, `#477`, `#510` using the official row interface. Record HEAD, existing dirty state, public Guardian status and any active touches in the handoff. Do not clean or reinterpret existing dirty assets.

- [ ] **Step 2: Create the formal rebaseline handoff**

Record the approved scope policy and Q9 decisions from the spec. Set `status: 待执行`. Include why this is a structural rebaseline, the exact documents in the file map, the freeze release condition, the 35/42 reconciliation requirement and the rule that Q9 remains outside the formal count pending a specialist-selected pilot stage and design review.

- [ ] **Step 3: Register the task and freeze marker**

Use the official shared-document lock flow: acquire and check its exit status; use the queue tool's merge-review and reserve/append flow for a new row only if no existing row can carry the work; record the §三 freeze marker with scope, reason, date and release condition; verify the write; release the lock. Preserve the exact canonical queue path returned by the tool.

- [ ] **Step 4: Verify the preflight gate**

Confirm the handoff is `待执行`, the freeze marker is visible through the authorized queue view, the lock is released, and no conflicting task is editing the same panorama documents. If any prerequisite fails, stop route edits and record the specific blocker.

### Task 2: Build the Cross-Document Change Matrix

**Files:**
- Read: `1-转型规划/0-全景路线图/文档台账-自动生成.md` (targeted queries only)
- Read: all governed sources in the File and Responsibility Map
- Modify: `1-转型规划/0-全景路线图/移交单-全景路线图-2026-10-02-滚动范围与Q9-APQP重基线.md`

**Interfaces:**
- Consumes: frozen scope, approved spec and governed-document inventory.
- Produces: a per-document old-value/new-value matrix and a list of exact zero-residual search terms.

- [ ] **Step 1: Resolve the authoritative file inventory**

Use the generated ledger first. Verify each source document's status and canonical path with targeted lookups. Reconcile the source skill's conditional four-chain entry and the Gantt file's ledger status before any write. Record missing/nonstandard ledger entries; do not enumerate the route folder to replace the ledger.

- [ ] **Step 2: Capture current authoritative counts and dates**

Read the panorama's §0.2 and authoritative schedule table, then compare the implementation plan's inventory and dates. Record the live total, the stale “42” references, the old version header, and every conflicting S1/S2/S3 date in the matrix. Do not change history snapshots.

- [ ] **Step 3: Define Q9's current formal status**

Record Q9 as a separately approved candidate with the confirmed Q4 boundary and owner. Keep it out of the committed scene count and detailed schedule until Quality/Engineering/Project recommend one evidence-backed stage and the Q9 design review passes. Do not create APQP acceptance thresholds or send a specialist request externally in this task.

- [ ] **Step 4: Review route dependencies**

For each scene, map latest target date, required stage materials, prerequisites, current evidence state and whether it is independently startable. Identify which wording is strategic batch metadata and which phrase currently acts like a start-date gate. Put the exact old phrases and target documents into the matrix.

### Task 3: Rebaseline the Authoritative Panorama

**Files:**
- Modify: `1-转型规划/0-全景路线图/卓品智能AI转型全景规划.md`
- Read/verify: `1-转型规划/0-全景路线图/移交单-全景路线图-2026-10-02-滚动范围与Q9-APQP重基线.md`

**Interfaces:**
- Consumes: reviewed change matrix and frozen route scope.
- Produces: a single authoritative scope, start-readiness rule, completion predicate and §0.2 audit entry.

- [ ] **Step 1: Update §0.2 before body changes**

Append a dated structural-rebaseline entry that references the approved spec and handoff, explains rolling formal scope, date semantics, live-session task loop and Q9's candidate status. Do not rewrite prior §0.2 entries.

- [ ] **Step 2: Reconcile the official total and Phase 1/2 narrative**

Set the current formal count from the signed scenario inventory; remove the “42” stale assertion from current-state sections while preserving dated history with explicit historical labels. Keep Q9 as a candidate pending its specialist/design gates; do not increment the committed total yet.

- [ ] **Step 3: Normalize the authoritative schedule table**

For every scene, retain its target/latest date and prerequisite. Remove any wording that treats the month as earliest start. Reconcile S1/S2/S3 order against the signed scenario inventory and current authoritative schedule; describe the verified order as strategic context, while making readiness—not phase month—the start criterion.

- [ ] **Step 4: Reconcile objectives and completion predicate**

State that completion requires all formal-scope scenes to be accepted or formally retired, roadmap-level targets achieved or formally retired, associated business tasks closed, and evidence/write-back complete. State that an approved new scene reopens completion status.

- [ ] **Step 5: Verify panorama consistency**

Compare §0.2, the schedule table, formal scene inventory and completion predicate against the matrix. Add each newly introduced distinct phrase to the zero-residual term list before moving to dependent documents.

### Task 4: Synchronize the Implementation Route and Dependency Table

**Files:**
- Modify: `1-转型规划/0-全景路线图/卓品智能AI转型实施计划（最新版）.md`
- Modify: `1-转型规划/0-全景路线图/跨场景前置数据与知识库任务总表.md`
- Read: authoritative panorama and change matrix

**Interfaces:**
- Consumes: finalized panorama scope, dates, and task readiness rules.
- Produces: matching scene totals, target dates, dependency statuses and Q9 candidate gate.

- [ ] **Step 1: Align inventory and version header**

Update the implementation plan's current version/date header and scene inventory to match the panorama. Retain historical change notes as dated history; do not leave an older count presented as current.

- [ ] **Step 2: Align timeline, milestones and prose**

Update the route's S1/S2/S3 narratives and milestone rows from the panorama schedule matrix. Replace stale start-date language with “target/latest date; readiness permits earlier start”. Keep due dates and real material gates distinct.

- [ ] **Step 3: Align prerequisite rows**

Update each affected cross-scene dependency row and §三 tracking note. Mark a task startable only when its required stage materials, business criteria, permissions and actual dependencies are available. Keep #510's sample/version requirement as a true blocker until the PPAP package is received and reconciled.

- [ ] **Step 4: Record Q9 without inflating committed scope**

List Q9 APQP as the separately approved candidate: independent upstream APQP review, Q4 remains downstream PPAP package review, Quality leads with Engineering/Project co-sign, one stage pilot pending expert recommendation, mock/sanitized first, L2 human final review. Do not add an unsigned stage/acceptance criterion.

- [ ] **Step 5: Cross-check both files**

Re-read the affected sections side-by-side. Confirm every formal scene has one scope record, one current target date and its dependencies; confirm Q9's candidate status agrees in both documents.

### Task 5: Update Visual and Root-Level Planning Mirrors

**Files:**
- Modify if in governed inventory: `1-转型规划/0-全景路线图/全景甘特图-场景排期.html`
- Review and modify only if chain endpoints/links change: `1-转型规划/0-全景路线图/业务特性驱动的四链联动蓝图-42场景重梳-2026-07-05.md`
- Modify: `CLAUDE.md`
- Read: finalized panorama and implementation route

**Interfaces:**
- Consumes: reconciled scene counts, target dates and candidate status.
- Produces: current visual/root references that agree with the authoritative documents.

- [ ] **Step 1: Update the Gantt mirror**

If the Gantt file is in the current governed-document inventory, align its scene bars, month values, total and footnotes to the finalized schedule. If absent or stale in the inventory, record and resolve that governance gap before editing it.

- [ ] **Step 2: Review the four-chain blueprint**

Compare Q9's approved boundary with blueprint endpoints. Update the blueprint only if an endpoint or chain link changes; otherwise record “reviewed, no endpoint/link change” in the handoff.

- [ ] **Step 3: Update root current-progress references**

Add a dated current-progress paragraph in `CLAUDE.md`; correct current scene totals and route pointers. Mark obsolete current-state statements as historical and point to the new paragraph instead of deleting history.

- [ ] **Step 4: Verify the mirror layer**

Check the Gantt (if governed), blueprint impact decision and root summary against the panorama matrix. Resolve any mismatch before proceeding.

### Task 6: Record the Rebaseline and Refresh Handoffs/Index

**Files:**
- Modify: `1-转型规划/0-全景路线图/全景路线图重组机制与变更日志.md`
- Modify: `1-转型规划/0-全景路线图/session接力-Phase1收口.md`
- Regenerate: `1-转型规划/0-全景路线图/文档台账-自动生成.md`
- Modify: the new rebaseline handoff from Task 1

**Interfaces:**
- Consumes: all prior reviewed source changes.
- Produces: an auditable change-log row, current session continuation card and refreshed document index.

- [ ] **Step 1: Append the rebaseline log entry**

Append one §四 row with date, trigger, scope, decision source, status and responsible line. Do not rewrite prior log entries.

- [ ] **Step 2: Refresh the Phase 1 session handoff**

Update its current snapshot, date section, newly approved rolling task loop, Q9 pending specialist gate and next recommended business lane. Preserve prior snapshots and note the old 35/42 inconsistency as reconciled.

- [ ] **Step 3: Regenerate the governed-document ledger**

Run the official document-ledger generator after all additions/renames. Confirm the rebaseline handoff, session card and all canonical route documents are indexed with valid status heads.

### Task 7: Regenerate and Inspect the Two DOCX Outputs

**Files:**
- Read: the finalized panorama and latest implementation-plan Markdown
- Regenerate: `1-转型规划/0-全景路线图/卓品智能AI转型全景规划.docx`
- Regenerate: `1-转型规划/0-全景路线图/卓品智能AI转型实施计划（最新版）.docx`

**Interfaces:**
- Consumes: finalized Markdown sources.
- Produces: matching DOCX deliverables in the same rebaseline batch.

- [ ] **Step 1: Regenerate each DOCX from its canonical Markdown**

Run the official Probe to resolve the project-managed isolated Python interpreter, then use that interpreter with `0-学习与工具\md转Word工具\md2word.py`; pass the source Markdown, its corresponding DOCX output path and `--org 卓品智能科技`.

- [ ] **Step 2: Verify regeneration evidence**

Record each output's pre/post modification time and byte size. Both must change after regeneration; a successful command without changed output metadata is not sufficient.

- [ ] **Step 3: Render and inspect both documents**

Use the `documents` skill's render-and-verify workflow. Inspect every rendered page for missing tables, broken headings, page overflow, stale totals and incorrect date labels. Fix Markdown/source layout and regenerate until both DOCX documents match their sources.

### Task 8: Write-After Checks, Zero-Residual Audit and Closeout

**Files:**
- Verify: every modified file in Tasks 1–7
- Update through official queue/lock tools: rebaseline row, freeze marker and handoff status
- Commit: one rebaseline batch containing the nine governed document units, required ledger/log/handoff changes and two DOCX outputs; never include unrelated dirty files

**Interfaces:**
- Consumes: complete source/DOCX batch and documented evidence.
- Produces: verified route batch, released freeze marker and archived handoff/queue status.

- [ ] **Step 1: Run write-after verification per modified file**

For each modified text file, pass its absolute path and one unique phrase newly written to it to `工具-写后反查.ps1` as `-Path` and `-Keyword` arguments, and capture the exit status. Also compare file byte size/line count before and after. For both DOCX files, verify changed modification time and size.

- [ ] **Step 2: Run the zero-residual checks**

Search the full repository for each exact stale term recorded in the matrix. Confirm current totals agree in the panorama, implementation plan, Gantt (if governed) and root `CLAUDE.md`. Do not rewrite historical snapshots; report each exempt historical occurrence as an explicit residual with its file and reason.

- [ ] **Step 3: Verify task and authorization closure**

Re-query #592, #477 and #510 through the official row interface and reconcile each state against delivery evidence. Keep Q9 a candidate until its specific stage and design review pass; keep #510 blocked only while sample/version evidence is still missing. Do not mark a row complete from a document-only action.

- [ ] **Step 4: Register and commit the explicit audited batch**

Register the pending commit batch in queue §二 through the official lock tool and immediately run the queue sweep. Stage the explicit rebaseline file manifest, inspect `git diff --cached --name-only`, run `git diff --cached --check`, and create one commit with message `docs(rebaseline): panorama rolling-scope rebaseline + docx + log`. The nine units include the DOCX pair as unit 9; supporting audit files may join the commit, but no unrelated or pre-existing dirty file may be staged. Do not push, ff or deploy without the required specific authorization.

- [ ] **Step 5: Clear the freeze and close the handoff**

After the commit is verified, use the shared-document lock to release the §三 freeze marker, update the queue row to `待验收` or `完成` according to the evidence, record the output paths, and update the rebaseline handoff to `已执行归档` only if every subtask is complete. If any subtask remains incomplete, preserve a partial status and list the exact unresolved item. Release the lock and verify the row state through the official queue tool.

## Execution Handoff

This is a documentation-governance plan, not a code implementation plan. Recommended execution method: **Native**, because the source files share one scope matrix, one lock/freeze interval and one same-commit DOCX batch; a single editor avoids split-brain changes. Subagent-driven execution requires Shao Peishen's explicit selection and would still preserve the single final review/commit gate.

After plan review, begin at Task 1. Q9's exact APQP pilot stage is a specialist evidence decision; it is not silently defaulted by this plan. The first business-lane candidates after rebaseline are #592 calibration continuation and #477 manual system-owner verification; #510 remains gated on PPAP samples and version baseline.
