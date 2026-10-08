## 1. Design Approval and Worktree Qualification

- [x] 1.1 Shao Peishen reviews and approves proposal, display spec, and design before implementation begins.
- [x] 1.2 After approval, recheck the existing approved portal UI worktree, branch, HEAD, and working tree; confirm the authorized file scope without changing the SC8 worktree.
- [x] 1.3 Map every existing QD-B report field and status to P13/P14/P15 placement, source, fallback text, and evidence; record any mismatch for review before code.

## 2. Read-only Presentation Update

- [x] 2.1 Update only the existing QD-B `webapp.py` HTML/CSS presentation to the approved visual variables and report hierarchy.
- [x] 2.2 Preserve the existing upload flow, authentication, size/type limits, routes, download behavior, all report fields, filters, and text escaping.
- [x] 2.3 Show the audit event timestamp as the evaluation time and mark the original source-data timestamp as unavailable; do not infer freshness.
- [x] 2.4 Check P13 upload and P14/P15 report/evidence views at 1440×1024, 390×844, and 320px; retain keyboard operation and all required content.

## 3. Focused Presentation Contract

- [x] 3.1 Add `tests/test_webapp_ui_contract.py` using constructed result objects only; cover all verdict states, required sections, version/audit metadata, absent source timestamp, long Chinese, and escaped HTML.
- [x] 3.2 Run only the new presentation contract test and the explicitly approved narrow static checks; do not run historical fixtures, the full matrix, uploads, or `evaluate()`.
- [x] 3.3 Inspect rendered desktop/mobile pages and verify field-for-field alignment with the approved mapping.

## 4. Independent Review and Release Preparation

- [x] 4.1 Obtain an explicit `gpt-6-luna` read-only review of the implementation HEAD and resolve only in-scope findings.
- [x] 4.2 Re-run the focused presentation check after changes and record the exact HEAD, files, commands, and results.
- [x] 4.3 Prepare a release evidence package; request separate authorization for master integration, production deployment, activation, and any real-sample validation.
