> 2026-10-10当前checkpoint：批准14路径合成A派生/B失败关闭及四指标同源明细已实现；独立审查的raw稳定身份缺口和来源PO行关联错误经RED→GREEN关闭，最终scene144＋platform50通过，根14SHA/dirty/AST与原缓存10字段兼容已核。HTTP保留全三节三窗口reconcile闸，缺口可能闭锁该scope全部detail路由；四指标报告仍可读。 完整证据见同日《SC2收货316合成实现与最终核验-2026-10-10.md/.json》，下文旧供审/未批字句仅历史时点。整体暂不归档。

# Tasks: SC2 收货报表 BizType316 子集

> 正式OpenSpec任务清单供审。只有文档成包/结构核验可在准备阶段记完成；实现、测试、真实来源及发布任务均未执行。 Knowledge holder/Owner: **unknown**. Backup: **unknown**. The unknown assignees gate professional signoff and real-business phase, but do not block Native mock work. Any technical implementation requires approved design and a specific approved implementation plan.

## 1. Review and ownership
 
- [x] 1.5 2026-10-10本人批准具体实施计划SHA6B52F0…19B9C、14路径/五定向测试与新Native/UUID副作用；原答及实际候选见《三采购具体实施计划批准消费-2026-10-10.md/.json》。只解合成实施闸，产品任务仍按实绩回填。

- [x] 1.1 Review proposal scope as an independent SC2 receipt slice; retain #277 exactly and keep #654 separate.
- [x] 1.2 Shao Peishen 于当前会话明确批准 D1–D10 并要求继续写实施计划；原答、questionItemId及design SHA256见 `0-学习与工具/codex-handoff/五项定夺答复消费-2026-10-10.md` / `.json`。不重问#277；实现、产品测试和发布仍待对应具体批准。
- [ ] 1.3 Record the real knowledge holder and Backup by name before professional signoff or real-business work. Both are currently unknown; do not infer them from IT/采购 replies. This assignment is not a prerequisite for isolated Native mock work.
- [x] 1.4 将四件成包于正式 `openspec/changes/sc2-biztype316-receipts/`，完成严格结构核验和§二登记；2026-10-10 strict 1/0，批次`B-1010_SC2收货316设计供审`。此项只计文档准备，不代表design审批或产品验证。

## 2. Source capability evidence (required for real source use and B route; not a mock prerequisite)

2026-10-10具体计划已根审供审：`docs/superpowers/plans/2026-10-10-sc2-biztype316-receipts.md`，SHA 6B52F0…19B9C；14路径/五定向测试文件/Native新候选及UUID副作用待本人批准。供审绑定见同日SC2具体实施计划供审绑定；产品与测试任务仍未完成。

- [ ] 2.1 Obtain the GR endpoint contract for explicit `bizType` filtering, omitted-parameter behavior, returned type fields, and relevant response metadata. Separate IT statements from independently verified facts. In parallel, Native mock may implement typed-row derivation and fail-closed behavior without this live evidence.
- [ ] 2.2 For route B only, establish independent evidence that an explicit 316 filter applies across every page. Until proven, B remains disabled/fail-closed; mock tests are not proof of server behavior.
- [ ] 2.3 Record the actual organization selection source and request semantics before any real-business result is labeled. Do not hardcode `Org=Z`; do not reopen closed IT14 or rerun already consumed queries. This is not a prerequisite to isolated Native mock work.
- [ ] 2.4 Record the existing GR/Query row semantics for posted, void, return, and reversal rows if those fields are available. Preserve current row inclusion until a documented existing rule or new professional approval requires otherwise.
- [ ] 2.5 Before real-source acceptance, confirm stable receipt line identity, BusinessDate, quantity, unit price, supplier name, and complete pagination; report missing fields by affected metric, not as zero. Synthetic fixtures can exercise missing-field behavior earlier.

## 3. Implement typed source and isolated subset (after approval)

- [x] 3.1 After approved design and a specific implementation plan, update the connector adapter to model optional explicit filters and per-row type evidence. Native mock may implement the interface and fail-closed behavior without live source evidence; omitted `bizType` remains unfiltered, and route B stays disabled until its server-filter evidence gate passes.
- [x] 3.2 Update SC2's new scope/typed wrapper and source path to carry type/filter/missing-field evidence without defaulting missing values to 316/zero; preserve legacy shared `ReceiptRecord` types/default behavior.
- [x] 3.3 Implement and mock-test isolated `receipts_316`: exercise route A by deriving 316 from synthetic complete per-row-typed rows while leaving shared `dataset.receipts` intact; exercise route B as fail-closed/disabled unless a verified server-filter evidence object is present. Leave other metrics on the existing shared receipt collection. Live evidence is required only before enabling B or accepting real-source results.
- [x] 3.4 Keep the current four metric labels/algorithms. If evidence requires changing price basis, supplier identity, or treatment of returns/voids, stop that rule change for the relevant professional signoff.

## 4. Preserve detail, snapshots, caches, and ignore boundaries

- [x] 4.1 Update SC2 `sc2/detail.py` so the 316 detail uses exactly the same verified subset/window as the four 316 metrics, and reports incomplete detail when required membership/fields are unknown.
- [x] 4.2 Use explicit scope/version identities such as `sc2_weekly_{period}__biztype316-v1.json`, `sc2_dataset_{period}__biztype316-v1.json`, and `gr_lines_{days}d__biztype316-v1.json`; resolve their actual directories from `config.reports_dir()` and `_po_cache_file.parent`. Old untyped snapshots/caches cannot satisfy 316 requests. Preserve old files and old report values without recomputation or overwrite.
- [x] 4.3 Update `sc2/report.py`, `sc2/config.py`, or `sc2/webapp.py` only where needed to label 316 scope, persist source evidence, and present the existing UI's gap state; do not redesign the dashboard.
- [ ] 4.4 The default SC2 reports and connector cache locations already match their current ignore rules; recheck exact resolved paths only if approved configuration changes them. Do not add broad ignore rules. 正式proposal/design/tasks/spec已在可跟踪的OpenSpec目录；不使用ignored准备稿替代正式件。

## 5. Planned verification (not run)

- [x] 5.1 Add/update SC2 source tests for explicit 316 request, API-parameter omission, filter-not-applied response, row-type absence, and pagination completeness.
- [x] 5.2 Add/update metric tests for a mixed synthetic 316/326/449 set; assert four approved metrics use only 316 while other shared-receipt metrics remain unchanged.
- [x] 5.3 Add/update detail tests for same-subset/window alignment, metric-specific missing fields, and incomplete cohort reporting.
- [x] 5.4 Add/update snapshot/cache tests proving old report values/files remain unchanged, schema-1 data is never treated as 316, and untyped cache keys do not satisfy a 316 request.
- [ ] 5.5 Use synthetic `MOCK-*` identifiers only; validate the source-capability evidence independently from mock tests before any real-data acceptance.

## 6. Release boundary

- [ ] 6.1 Complete approved design, implementation, review, required CI/tests, formal record writeback, and all change tasks first; archive only after formal writeback and all tasks are complete. Merge/ff and each release or publication step require their own applicable approval and are not implied by archive.
- [ ] 6.2 Any production query, server change, deployment, release, recalculation, or external message requires its own applicable authorization; none is granted by #277 or this pending-review package.
- [ ] 6.3 Keep #538 partial until its own deployment/comparison/root-cause criteria close. Do not use this change to close, reopen, or rewrite its history.
