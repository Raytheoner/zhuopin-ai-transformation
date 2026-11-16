---
name: finishing-a-development-branch
description: Use when implementation is complete, all tests pass, and you need to decide how to integrate the work
---

## zhuopinAI Codex 强制覆盖与衔接规则

- 标准 feature 链：`zhuopin-requirement-grill` 产出并确认 `intent.md` → `openspec-propose` 产出 proposal/design/specs/tasks → `openspec-apply-change` 按 `executing-plans` + `test-driven-development` 在本主会话串行执行 `tasks.md` 切片；每片先写/更新 pytest 再实现，最终在受影响子项目独立跑完整 pytest 与功能/audit 验收。refinement 可用轻量 proposal，但必须同步 delta spec 与对应 pytest。
- `tasks.md` 全 `[x]` 且归档前置、观察窗口与外部签认均闭合时，当场走 `openspec-archive-change`；明示暂缓或冻结合同保留，不能仅凭 N/N 越闸。
- 根 `AGENTS.md` 的本主会话串行是唯一默认。未经任务级明确授权，不启动 `subagent-driven-development` 的自动派生、并发泳道或独立模型审核；旧冻结合同和明确独审仍按原要求。
- 上游 “Rulings, not stalls” 不授权越权自决。缺 design 审、L2、合规、外部口径，或缺 `git commit/push/ff` 的逐项授权时停在对应闸；已批同范围不重复索取。真实源、生产与外发也遵守根规则。

# Finishing a Development Branch

## Overview

**Core principle:** Verify tests → Detect environment → Present options → Execute choice → Clean up.

**Announce at start:** "I'm using the finishing-a-development-branch skill to complete this work."

## Project Authorization Boundary

Default to keeping the current candidate and evidence. Existing same-scope integration decisions are reused, not re-asked. Do not commit, switch a shared checkout, pull, merge, push, delete a branch or remove a worktree merely because implementation is finished. Each operation needs its existing specific authorization. Integration is ff-only after verifying the exact target is clean, unoccupied and an ancestor of the candidate; divergence stops the operation. Explicit independent/safety review and frozen contracts remain gates.

## Step 1: Verify Tests

Use the required affected-project verification bound to the actual candidate. Reuse valid evidence for an unchanged candidate/environment; changed code or invalidated evidence requires the corresponding checks. Do not run a mixed repository-root suite or repeat the same validation solely to finish a session.

**If tests fail**, report the failures and stop — the menu comes after a green suite:

```
Tests failing (<N> failures). Must fix before completing:

[Show failures]
```

**If tests pass:** continue to Step 2.

## Step 2: Detect Environment

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
# Capture now, while still inside the workspace — Step 5 changes directory
# before cleanup (Step 6) needs this value
WORKTREE_PATH=$(git rev-parse --show-toplevel)
```

This determines which menu to show and how cleanup works:

| State | Menu | Cleanup |
|-------|------|---------|
| `GIT_DIR == GIT_COMMON` (normal repo) | Standard 3 options | No worktree to clean up |
| `GIT_DIR != GIT_COMMON`, named branch | Standard 3 options | Provenance-based (see Step 6) |
| `GIT_DIR != GIT_COMMON`, detached HEAD | Reduced 2 options (no merge) | Externally managed — leave in place |

## Step 3: Determine Base Branch

The base branch is whatever this work forked from — usually named in the
plan, the conversation, or the branch's upstream. If it is not already
known, ask: "This branch split from <your best guess> - is that correct?"
Confirm before merging: merging into the wrong base is expensive to undo.

## Step 4: Present Options

**Only when a new integration decision is actually missing, offer the applicable choices below; keep-as-is is the default recommendation, not permission to integrate. A prior explicit same-scope keep/no-push instruction requires no new menu.**

```
Implementation complete. What would you like to do?

1. Integrate into <base-branch> locally using separately authorized ff-only
2. Push and create a Pull Request
3. Keep the branch as-is (I'll handle it later)

Which option?
```

**Detached HEAD — present exactly these 2 options:**

```
Implementation complete. You're on a detached HEAD (externally managed workspace).

1. Push as new branch and create a Pull Request
2. Keep as-is (I'll handle it later)

Which option?
```

Present the menu exactly as written — concise, with every option coming
from the list above. Discarding the work happens only in response to your
human partner explicitly asking for it (see "If your human partner asks to
discard the work" below). Wait for their answer; the integration decision
is theirs.

## Step 5: Execute Choice

### Option 1: Authorized FF-Only Integration

```bash
# Get main repo root for CWD safety
MAIN_ROOT=$(git -C "$(git rev-parse --git-common-dir)/.." rev-parse --show-toplevel)
cd "$MAIN_ROOT"

# Only after target ownership, cleanliness, fast-forward ancestry and specific authorization are verified.
# Never switch an occupied business checkout; do not pull as a finishing default.
git checkout <base-branch>
git merge --ff-only <feature-branch>

# Verify tests on merged result
<test command>
```

If tests fail on the merged result: stop, leave the worktree and branch in
place, and investigate — nothing has been pushed, so the merge is local
and recoverable.

A green integrated result is not authorization to delete a branch or worktree. Keep both unless cleanup is separately authorized and evidence is preserved (Step 6).

### Option 2: Push and Create PR

Run only after explicit approval for this branch, remote and operation; ff authorization or session completion does not authorize push. Never stage/commit other sessions' files.

```bash
git push -u origin <feature-branch>
# From a detached HEAD, name the new branch on the remote:
# git push origin HEAD:refs/heads/<new-branch>
```

Then create the pull/merge request against <base-branch> with the forge's
tooling — its CLI if one is available, or the creation URL most forges
print when you push — following the repo's PR template and conventions if
present, and report the URL to your human partner.

Keep the worktree — your human partner iterates on PR feedback there.

### Option 3: Keep As-Is

Report: "Keeping branch <name>. Worktree preserved at <path>."

### If your human partner asks to discard the work

This path exists only as a response to an explicit request to throw the
work away. Confirm first:

```
This will permanently delete:
- Branch <name>
- All commits: <commit-list>
- Worktree at <path>

Type 'discard' to confirm.
```

Wait for that exact confirmation. When it arrives:

```bash
MAIN_ROOT=$(git -C "$(git rev-parse --git-common-dir)/.." rev-parse --show-toplevel)
cd "$MAIN_ROOT"
```

Then clean up the worktree (Step 6) and force-delete the branch:

```bash
git branch -D <feature-branch>
```

## Step 6: Cleanup Workspace

Keep the workspace by default, including after ff-only integration. A folder named `.worktrees/` or `worktrees/` does not prove ownership. Cleanup requires explicit authorization for the exact owned workspace, confirmation of no active business use or conflicting changes, and preserved ledgers/raw logs/untracked/ignored evidence with verified hashes. Commits alone are insufficient. Inspect and preserve before removing anything; never use `--force`, broad `prune`, `clean`, reset or full-repository stash to finish.

Use the host's supported managed-worktree archive tool when applicable, preserving needed ignored files separately. A primary/shared/pinned/unknown workspace stays in place. If cleanup is refused or preservation is incomplete, retain the workspace and report the concrete reason. Do not offer a business checkout switch or deletion as a default workaround. An explicit discard still requires the exact scope/confirmation above and cannot delete other sessions' work.

## Quick Reference

| Option | Merge | Push | Keep Worktree | Cleanup Branch |
|--------|-------|------|---------------|----------------|
| 1. Authorized ff-only | ff-only | - | yes by default | separately authorized |
| 2. Create PR | - | yes | yes | - |
| 3. Keep as-is | - | - | yes | - |
| Discard (explicit request only) | - | - | - | yes (force) |

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Tests passed earlier this session" | Run the suite on the tree you are about to integrate. A green run only proves the tree it ran on. |
| "They obviously want it merged" | Integration is your human partner's decision. Present the menu and wait. |
| "They seem done with this feature — I'll offer to discard it" | The menu is complete as written. Discard happens only when your human partner asks for it in so many words. |
| "'Yeah, get rid of it' counts as confirmation" | Only the typed word `discard` authorizes deletion. |
| "The PR is up, so the worktree is clutter now" | PR feedback gets fixed in that worktree. It stays until the work lands. |
| "This other worktree looks stale — I'll clean it too" | A directory name does not prove ownership or authorize cleanup. Leave other sessions' worktrees in place. |
| "Removal refused — `--force` is just finishing the cleanup" | The refusal means files exist only in that worktree. `--force` destroys them permanently. Show your human partner and ask. |
| "The merged-result failure is probably flaky" | A failing merged result stops everything. Branch and worktree stay put while you investigate. |
| "The base branch is obviously main" | Confirm the fork point or ask. Merging into the wrong base is expensive to undo. |
| "The push was rejected — force-push will fix it" | A rejected push means the remote moved. Investigate; force-push only on your human partner's explicit request. |
