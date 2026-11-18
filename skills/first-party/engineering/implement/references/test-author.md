# Test author in the full route

Read this before a developer dispatch when the project enables the test author. The cycle
itself (handoff, statuses, attempt limit) is in `../tdd/references/test-author.md` and in
`.harness/orchestration/roles/developer.md`; this file covers what the coordinator prepares.

**Test author in the full route.** The author inherits runtime/model/effort from the approved
developer brief, without a separate role assignment or project-profile override. A selected runtime
without a protected adapter returns `runtime_unsupported` and keeps ordinary TDD. The current
protected adapter lets an `external` Claude Code developer call the author in
`send.worker_worktree`, using `Agent(test-author)` without model/effort overrides. Before dispatch, install the harness in that exact checkout.
A linked worktree of a repository whose main checkout the human trusted in Claude Code needs no trust
dialog of its own and no `CLAUDE_PROJECT_DIR` export: preflight takes the project root from Git (ADR 0033).
Never copy the main checkout's runtime state or trust.
The developer checks its own `.claude/hooks/test-author-preflight.sh --worktree <send.worker_worktree> --brief <approved brief path>`
and enables the author only after exactly `{"status":"ok"}` and an `Agent(test-author)` or `Agent`
permission in the approved brief. The default developer role policy includes the named permission;
a project override remains authoritative. Missing permission gives `agent_tool_unavailable` and
ordinary TDD, never a launch-time tool expansion. Pass the shared runner log root from the adapter
prompt to the author along with one test path within the brief's scope.

For `in-process`, the main preflight with `--worktree <send.worker_worktree>` answers
`checkout_mismatch`: the main checkout's guard and runner serve only the main checkout. The worker
prompt therefore names the worktree's launcher for each handoff:
`python3 -I -B <send.worker_worktree>/.harness/health/test_author.py run --repo <send.worker_worktree> --brief <approved brief path> --prompt-file <path>`.
It checks that worktree's preflight and starts the author with its guard and runner, under the same
brief permission rule. A refusal (exit 3 with a reason) keeps ordinary TDD with that reason.
Keep the selected executor visible in refusals; never substitute Claude for an unsupported runtime. A preflight refusal or unavailable author
never creates a blocker or changes the Rust ledger. State this in the worker prompt.
