## Subagent dispatch requires multi-agent support

Use the actual tools and schema exposed in the current session. Tool availability is not authorization to delegate. This project defaults to one serial main session; spawn only when the user explicitly requests it or the applicable frozen/safety contract requires authorized independent review. Do not edit machine-level config to enable an assumed feature as part of ordinary work.

- **Spawning:** `fork_turns` accepts `"all"` (default) or `"none"` in the current schema. Full-history `"all"` inherits the parent model/effort and cannot take `model`/`reasoning_effort` overrides. An authorized project child must explicitly use `model: "gpt-6-luna"` and `reasoning_effort: "high"`, so use `fork_turns: "none"` and supply the task, allowed paths and required evidence explicitly. `agent_type` is a role selector, not a model; use it only within its actual permission/schema. Do not assert version-based behavior instead of reading the tools.
- **Fix rounds:** use `followup_task` for an existing authorized non-root agent: an idle target is triggered, while a running target receives the follow-up at a message boundary. Do not assume eviction/reload behavior or dispatch a replacement without checking the actual returned status and authorization.
- **Lifecycle:** the current tool set has `interrupt_agent`, which interrupts execution and leaves the agent available for messages; it is not a `close_agent` operation. Do not fabricate a close tool or assume eviction/reload guarantees absent from the actual schema.
- **Model names:** check the current spawn allowlist before an authorized dispatch. If the mandated Luna/high route cannot be specified or is unavailable, keep that subtask pending; do not silently inherit or substitute a different model.

## Waiting on children

`wait_agent` is an event subscription, not a poll: a long wait wakes
the moment a child produces mailbox activity, with the same latency as
a short one. Short-timeout polling buys nothing and costs a tool call —
and a context rebill — per poll. In measured sessions, roughly
two-thirds of all wait calls were short polls that timed out.

- While you still have local work, do not wait at all. A completed
  child's final answer is pushed into your mailbox and arrives with
  your next turn.
- When you are genuinely idle with children outstanding, wait in
  bounded stretches consistent with active response requirements (here, `timeout_ms` up to 60000). After each stretch — wake or timeout — post one
  status line, run `list_agents`, and chase any child that finished
  without reporting. Avoid repeated unchanged polls; choose a bounded wait within the actual schema and active communication requirements.
- Completion mail cannot wake an idle controller (it is delivered
  without triggering a turn); covering that idle window is
  `wait_agent`'s only job. A stretch that times out with no activity
  is your cue to reconcile, not to shorten the next stretch.

## Model routing on spawns

Only authorized isolated (`fork_turns: "none"`) spawns set both `model` and `reasoning_effort` explicitly, using this project's `gpt-6-luna`/`high` rule. Full-history forks inherit those settings and do not accept overrides; therefore they are not a substitute for the explicit-route requirement. Do not ask for or write unverified machine-level routing keys as a workaround. Availability of collaboration tools does not create a new reviewer requirement.

## Environment Detection

Skills that create worktrees or finish branches should detect their
environment with read-only git commands before proceeding:

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
BRANCH=$(git branch --show-current)
```

- `GIT_DIR != GIT_COMMON` → already in a linked worktree (skip creation)
- `BRANCH` empty → detached HEAD (cannot branch/push/PR from sandbox)

See `using-git-worktrees` Step 0 and `finishing-a-development-branch`
Step 1 for how each skill uses these signals.

## Codex App Finishing

When branch/push operations are unavailable in an externally managed worktree, preserve the scoped candidate and evidence. Do not commit all files or stage other sessions' changes. Only after the specific operation is authorized, inspect the actual App tools/controls; an observed control is not proof it can move this chat or bypass sandbox permissions. Possible user-requested controls include:

- **"Create branch"** — names the branch, then commit/push/PR via App UI
- **"Hand off to local"** — transfers work to the user's local checkout

The agent can prepare scoped evidence and run necessary verification. Staging, commits, branch moves, push and PR creation retain their specific authorization and ownership checks; none is a finishing default.
