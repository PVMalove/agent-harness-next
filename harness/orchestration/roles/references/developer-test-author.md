# Developer: optional test author

Read this before the first test. Run `python3 -I -B .harness/health/test_author.py preflight --repo
<worker_worktree> --brief <approved brief path>` in the worker checkout; it calls that checkout's
`.claude/hooks/test-author-preflight.sh` itself. Only exactly `{"status":"ok"}` enables the author;
any other answer keeps ordinary TDD with the reason stated. The cycle is prose for the developer, not
a new dispatch, role, state or ledger record.

## The cycle

The Red-Green-Refactor cycle is the one protocol of the `tdd` skill: `references/test-author.md`,
installed as `.harness/skills/tdd/references/test-author.md` in the checkout whose
`.harness/orchestration/roles/` you read. Its handoff, reply, `needs_skeleton` and `contract_gap`
statuses, Not a behavioral Red rule (a test that is Green immediately included), Green and Refactor
apply unchanged, with these role rules:

- **Seam.** Take the seam from the accepted architect design in the brief's
  `accepted_design.output`. A seam the brief did not agree is not invented: escalate it through the
  ordinary blocker path.
- **`contract_gap`.** Clarify the requirement or seam from the brief or escalate through the
  ordinary blocker path; never guess it.
- **Expectation.** An accepted expectation is never weakened to reach Green. Only a justified
  contract change inside the brief's scope allows correcting it, with a new author call and a new
  verification.
- **Attempt limit.** After three consecutive failed author calls on one test, stop the local retries
  and report through the ordinary blocker path. A guard denial counts as one failed call, and the
  denied call is never rephrased (see "Never work around a hook" in `common.md`). A local author
  retry and a guard denial create no new dispatch, add no ledger state and do not bypass the
  playbook's recovery rules.

## Executor

Inherit runtime/model/effort from the approved developer brief; project settings never override it.
A selected runtime without a protected adapter returns `runtime_unsupported`, preserving ordinary
TDD without a provider substitution. The current protected adapter supports an `external` Claude Code
developer: its process, preflight, guard and runner must all serve the brief's canonical
`worker_worktree`. Install the project harness in that worker checkout before dispatch. Preflight
takes the project root from Git; `CLAUDE_PROJECT_DIR` is optional, and a different value gives
`project_dir_mismatch`. A linked worktree of a repository whose main checkout is trusted in Claude
Code needs no trust entry of its own. Do not copy state or trust from the main checkout.

Only exactly `{"status":"ok"}` and an `Agent(test-author)` or `Agent` permission in the approved brief
allow calling the named author without model/effort overrides (no `model` or `effort` line in its
frontmatter). Otherwise use ordinary TDD and name the preflight reason or `agent_tool_unavailable`;
do not widen the approved tools at launch.

Give the author one test path within the brief's allowed scope, the requirement and the runner log
root from the adapter prompt. Linked worktrees share `<main>/.harness/.sandboxes/runs/`; the author
reads `isolated-test-<run_id>/log.txt` there. The adapter exposes that evidence directory without
changing the brief's tool list. Test writes and runner execution remain in the worker checkout.

An `in-process` developer does not call the native author: the main checkout's
`test-author-preflight.sh` with `--worktree <worker_worktree>` answers `checkout_mismatch`, because
its guard and runner serve the main checkout. For each handoff it runs `python3 -I -B
<worker_worktree>/.harness/health/test_author.py run --repo <worker_worktree> --brief <approved brief
path> --prompt-file <path>`, which checks the worker's preflight and starts the author bound to the
worker's guard and runner; the same brief permission rule applies, and a refusal keeps ordinary TDD
with its reason. Other runtimes are unsupported. A refusal never creates a blocker, another dispatch
or ledger state. The optional author does not change independent QA or the Rust runtime authority.
