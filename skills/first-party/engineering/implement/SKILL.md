---
name: implement
description: "Coordinates one afk ticket labeled pipeline::full through architect, developer, code-review, QA and publish dispatches, then offers /to-pull-requests. Use explicitly when the backend-orchestration capability is installed; use /fast-implement for pipeline::fast and /to-guide for hitl. Never writes the feature code itself."
disable-model-invocation: true
---

# Implement

**Objective:** Coordinate exactly one ticket through `architect → developer → code-review → qa → publish`, then offer `/to-pull-requests`. This session **is** the coordinator: it creates and observes dispatches but never implements the ticket itself. Invoke it only on an explicit request (`/implement`, or `$implement` in Codex).

Language contract: agents communicate with each other and write free-text protocol/state evidence in
English. Every completion report addressed to this coordinator is in Russian and includes
`"report_language": "ru"`; preserve commands, paths, IDs, and quoted evidence verbatim.
Machine-read report values stay exact English enums: `outcome: completed | blocked | failed`,
check `result: pass | fail | not_run`, and `blockers.status` / `risks.status: none | present`.
Each blockers/risks field is a status/details object; translate only its description.
This binds the text this session writes, not only the text it reads: translate the ticket into
English before it reaches a batch or a worker prompt. `definition_of_done` and `prohibited_changes`
are rejected outright when they carry Cyrillic, and a worker prompt carrying the untranslated
ticket body is the same contract violation the coordinator cannot see.

## Route

This is the opt-in `backend-orchestration` route. Confirm that its installed coordinator is usable:

```bash
python .harness/orchestration/coordinator.py --repo . dispatch status
```

If the command is unavailable or cannot read its state, stop. For a `pipeline::fast` ticket, tell the
developer to run `/fast-implement` instead. For a `pipeline::full` ticket, say that this route needs
the `backend-orchestration` capability, or that the developer may relabel the ticket
`pipeline::fast` on the tracker and then run `/fast-implement`.
A `ledger_busy` answer is not unavailability: another coordinator operation holds the ledger lock,
so repeat the command after its `retry_after_seconds`.
Do not infer or repair an opt-in capability. Process one ticket to a terminal batch state before
beginning another.

Before any tracker write, confirm this session is rooted in the main checkout. For an existing
issue worktree, follow `references/issue-worktree.md` → Session write access for this runtime (Claude
Code: `EnterWorktree` with `path=<issue-worktree>`, then `ExitWorktree` with `action: keep`, no
coordinator command between them) and run `worktree check --worktree <issue-worktree>` inside the
session sandbox. Continue on
`"writable": true`. On refusal, report the affected path and the setup command for this runtime.
For a new issue worktree, verify `runtime status` lists `worktree.create` or that the session can
write `.git/worktrees`. Probe the report inbox before changing ticket status and check the new
checkout before creating the batch.

If another batch holds the same unfinished ticket, branch or worktree, or the `concurrency_budget`
is exhausted, read `references/recovery.md` → "A batch blocks the ticket" before proposing anything.

## Coordinator contract

Resolve the tracker ticket, issue branch and blockers without opening a second batch for the same
work. Ticket status is part of that pre-flight, after the write-access probe in "Route", before
`batch create` and before the issue branch exists: check the ticket's blockers whatever its current label (any still open → stop, name them,
and make sure it carries `status::blocked`); otherwise replace its `status::*` label with
`status::in-progress` exactly as `/fast-implement` Pre-flight steps 1–2 do, and confirm it is the
only `status::*` label. A failed label write is a blocker, not a warning. Before `batch create`, run the batch-level preflight with bounded expected files, services and
diff size. Confirm the implementation owner from the ticket and the role manifests. Pass the
same `--writer-role database-migrations` or `--writer-role messaging-integration` to `batch
preflight` and `batch create` for specialist work. The default owner is `developer`. If compatible
slices need different owners, use dependent tickets. Pin the writer's explicit scope with
`--allowed-path` (repeat it for every path or glob inside the selected role's write ceiling).
Independent batches use separate worktrees, within the project's concurrency budget. If preflight rejects the ticket, stop and offer the developer `/to-tickets` to split it; never ask an architect to discover
whether an oversized ticket should have been split. When creating the batch with `batch create`,
specify `--required-gate review --required-gate qa`: the full implement pipeline explicitly sets
both independent Standards/Spec review and serialized clean-room QA gates. Before dispatching the
planned writer, verify that these mandatory gates are recorded in the batch's
`required_gates`; halt early if missing rather than sending a worker into a risk-gate omission.

## Batch preparation

The coordinator must take every procedure from agent sources only: this skill, `.harness/orchestration/playbook.md`,
`.harness/orchestration/roles/`, the guides in `.harness/instructions/`, and the `--help` and `remedy` output of
the coordinator CLI. The coordinator must not take a procedure from a Russian human document
(`backend-orchestration.md`, `site/docs/`, `ARCHITECTURE.md`, `site/docs/skills/`, `site/docs/hooks/`).
The coordinator must not copy conventions from another batch and must not read ledger files in
`.harness/orchestration/state/`. The coordinator must read state only through CLI commands (`batch list`,
`batch decision-packet`, `dispatch status`). If these sources do not give a step, that gap is a
blocker: the coordinator must stop and report it to the developer, and must not reconstruct the step.

Start these steps only after the ticket pre-flight above (blockers, `status::in-progress`).
The coordinator reads `approval_policy` from `.harness/orchestration.json` first. Under
`approval_policy: auto`, the coordinator reads `references/auto-path.md` before step 5, because that
reference governs `batch approve` and every later decision.

1. **Integration ref.** Use the ticket's `## Integration Branch` value (the `**Integration branch:**`
   line on the local tracker). If the ticket has no such section, use its `## Git base` value. If it has neither, use the same section of the parent epic.
   A missing value for a ticket that has a parent epic is a blocker; do not infer it from the
   checkout or from memory. A ticket without a parent epic uses `base_branch`: omit `--integration-ref`.
2. **Issue worktree.** Create it before `batch create`. `batch create` refuses a worktree that
   `git worktree list` does not show. Use `worktree create` and the exact commands in
   `references/issue-worktree.md`. Confirm `"writable": true` from
   `worktree check` before `batch create`. If access is missing, open it for this runtime (Claude
   Code: the `EnterWorktree`/`ExitWorktree` pair above) and repeat the check. Stay in the main
   checkout.
3. **Batch scope.** Run `batch preflight` with the same `--ticket`, `--definition-of-done`,
   `--allowed-path`, `--expected-*`, `--dependency` and `--writer-role` values as `batch create`;
   preflight takes no `--goal`, `--prohibited-change`, `--branch`, `--worktree`,
   `--integration-ref` or `--required-gate`. Translate the
   ticket into English first: `batch create` rejects Cyrillic in `--goal`, `--definition-of-done`
   and `--prohibited-change`. Keep commands, paths, and IDs verbatim. Map the ticket sections:
   each `## Acceptance criteria` item → `--definition-of-done`, each `## Out of scope` item →
   `--prohibited-change`, each item of the parent epic's `## Non-Goals & Rejected Alternatives` →
   `--prohibited-change` when the ticket names `## Parent: #<epic>`, and the paths of `## Contract touchpoints` and
   `## Relevant Files (Discovery Context)` → `--allowed-path` and `--expected-file`.

   **Pipeline cost.** After a passing `batch preflight` and before `batch create`, compare the
   `pipeline::full` label with the ticket's actual size. Show the developer the estimate: the
   preflight's `expected_files` and `expected_changed_lines`, the ticket's `## Story Points`, and
   `story_points.fast_threshold` from `.harness/project.json`. If every expected file is
   documentation or skill text (`*.md`, `docs/**`, `site/**`, `skills/**`), or the Story Points are at
   or below `fast_threshold`, offer to relabel the ticket `pipeline::fast` on the tracker and run
   `/fast-implement` instead. The developer decides; wait for the answer under every
   `approval_policy`. Continue with step 4 unless the developer chooses `/fast-implement`; then stop
   before `batch create`. Never relabel the ticket yourself.
4. **Create the batch.** Repeat the list flags once for each value.

   ```bash
   python .harness/orchestration/coordinator.py --repo . batch create \
     --ticket "#<ID>" --branch "feature/issue-<ID>-<slug>" --worktree "<absolute worktree path>" \
     --integration-ref "<integration-branch>" --goal "<English goal>" \
     --definition-of-done "<English item>" --prohibited-change "<English item>" \
     --allowed-path "<path or glob>" --expected-file "<path>" --expected-service "<service>" \
     --expected-changed-lines <N> --required-gate review --required-gate qa
   ```

   `--ticket`, `--branch`, `--worktree`, `--definition-of-done`, `--prohibited-change` and at least
   one `--allowed-path` are mandatory. `--branch` must match `branch_pattern`. `--expected-file`,
   `--expected-service` and `--expected-changed-lines` are mandatory when the project policy
   requires estimates. The CLI refuses an oversized ticket and prints a `remedy`.
5. **Approve the batch.** `batch approve` moves the batch from `planned` to `awaiting-approval`.
   The step depends on `approval_policy`:
   - `auto`: run `batch approve --batch <id>` yourself, without `--approved-by` and
     `--approved-at`; the policy records the approval (`references/auto-path.md`).
   - Every other policy: the step needs the operator's explicit approval. Present
     `batch approve --batch <id> --approved-by <operator> --approved-at <UTC time>`, as for
     `batch abandon`, and do not run it for them.

## Dispatch handoffs

Use the planned writer as `--role` for implementation, its retries and `--purpose publish`.
For each handoff, choose the worker checkout and pass its absolute path as `--worktree` to
`dispatch preflight`. Show `batch decision-packet`, then create an approved immutable brief. Pass
the same explicit `--worktree` to `dispatch send`; code-review also keeps `--checkout`. Preflight
and send verify the selected path, branch and startup SHA. Start the worker in exactly
`send.worker_worktree` using a runtime-supported mechanism for that existing directory. Verify that
mechanism before launch: `isolation: worktree` alone does not prove attachment to an existing
worktree. If the runtime cannot select that checkout, report a blocker. The coordinator stays in the
main checkout. Never `cd` into a worktree from the coordinator session, not even as
`cd <worktree> && …`: the shell's working directory persists between commands, so one `cd` moves the
whole session. Read worktree files by absolute path: `git -C <abs worktree> …`, `rg <pattern> <abs
worktree path>`, and the file tools with absolute paths. If the session moved anyway, `cd` back to
the main checkout before the next command. A selected path is intent; self-report proves the worker's actual CWD. Pass the
brief's `report_staging_path` to the worker verbatim; a role that has to guess where its report
belongs writes it outside the project.

**Claude Code runtime.** The Agent tool cannot select an existing checkout. In Claude Code, read
`references/claude-code-runtime.md` and state which worker path (`external` or `in-process`) the batch uses.

**Test author.** When the project enables the test author, read `references/test-author.md` before
the developer dispatch and state its outcome in the worker prompt.

`dispatch send` checks the adapter's flags against its `dispatch --help` before the handoff and
refuses an unsupported one: fix the `--adapter-arg` values and send the same approved dispatch
again. Show any `limitation` in the send result's `adapter_preflight`. To diagnose an app-server
runtime without a worker, run `dispatch runtime-probe`; its result is evidence, and the worker's
model self-report stays mandatory.

The coordinator never writes feature code or repairs state by hand. A report is evidence, not
permission to advance. Architect precedes developer; accepted candidate proceeds through the
required review/QA/publish gates. A write-role worker stopped early before making changes returns a
truthful `outcome: blocked` report bound to the verified checkout commit with empty `changed_files`
and unrun checks; the coordinator decision packet returns an explicit recovery route (`retry`,
`block`, or a human-selected `abandon`) without registering a candidate or weakening `completed`
report validation.

Before the architect accept and before a `developer` work dispatch, read `references/commit-plan.md`:
the immutable brief carries an ordered commit plan, and the developer's report maps every commit to
the entries it closes.

Follow the configured approval policy. Under `manual_all`, every transition needs explicit approval:
show the decision packet, ask, and wait. Under `low_risk`, a clean completed report of a batch whose
allowed paths lie inside `low_risk_paths` is accepted by the coordinator with an audited policy decision, and the next eligible dispatch
may already be approved. Under `milestone`, clean reports outside QA, publish and risk milestones
are also accepted automatically; stop for the remaining milestone decisions. Continue from the
recorded `next_action` without asking the operator to repeat a policy decision. Blockers, failed
checks, risk triggers, review findings and publish still require the applicable manual decision.
Never write `--approved-by` on the operator's behalf or
narrate a decision they did not make. `human_approval_gate: tty` requires confirmation on the
operator's terminal for transitions that still require human approval. When choosing a recovery
route for `retry` or `abandon`, show the decision packet's `route_preview` (with the
`--reason-category` or `--retry-role` you intend to pass to `batch decide`) and follow the
Recovery route table in `.harness/orchestration/playbook.md` (situation → route → who approves →
evidence). When a route is `rebase` (`next_action: rebase`, also shown as `route_preview.accept`),
create `dispatch create --role rebaser`; after its accepted report run the risk assessment and go
to QA, never to a new code-review. Report each startup failure under its own classification (unsupported flag, missing
or refused self-report, capacity, rate-limit, service-unavailable) together with its recovery
route.

Before a decision on a developer report with a failed check (`checks_run[].result: fail`), read
`references/recovery.md` → "A failed check the diff may not cause": a retry cannot fix a failure the
diff does not cause.

Each worker records a model self-report and is observed by the event-driven watchdog; those facts
are evidence, never a reason to edit an immutable brief.

Use the brief's shared Context Package ID across architect, developer and resumed worker sessions
when the pinned base/candidate is unchanged. Read only its starting files and directly referenced
symbols before escalating. A changed candidate creates one new shared package for its review, not a
role-specific duplicate. Continuations and retries stop at the project budget; a 429 is not an
exception to that budget.

Run `dispatch wait` between send and report. Silence or a timeout does not prove that a worker
stopped, and neither does `ps` from this session: only `dispatch status` shows whether a worker is
alive. Read `references/workers.md` for waiting, a busy ledger or QA lease, the runtime service,
and external launch and observation. Never remove the ledger lock or a state file by hand, and never
start `harness-runtime serve` from your own shell.

## Stops and recovery

When a worker cannot produce a report or a launch fails, run `batch auto-report`,
`batch decision-packet`, `dispatch status` and `ledger validate`, and quote the dispatch's `startup`
assessment before proposing waiting, launch repair, human-approved `batch resume-stop` (with
`--runtime-stopped` once the worker is stopped through its runtime), `batch rewind`, or cancelling an
unsent dispatch. `dispatch runtime-probe` diagnoses an app-server runtime without a worker. Read
`references/recovery.md` for the matching case: a batch blocking the ticket, a runtime-store hold, an
infrastructure-only failure, a failed check the diff may not cause, a block bypass or tooling
blocker, and a defect in a clean developer report. Never accept or warning-override a report whose worker worked around a hook or tool block.

## Worker prompt

Every worker prompt is this template, filled from the `dispatch send` result and the CLI invocation
used to send it. The brief and Context Package carry the task; the prompt also carries the mandatory
lifecycle. Fill `<coordinator CLI>` with the Python executable, absolute `coordinator.py` path and
absolute `--repo` (plus `--state-dir` when supplied) used for that dispatch; fill `<repo>` with that
absolute `--repo` and `<role>` with the dispatched role. Quote paths for the
worker's shell. Keep this same ledger address even when the worker runs in another worktree.
Copy the heartbeat interval from `dispatch send.heartbeat.every_seconds` verbatim.

```text
You are the <role> worker for dispatch <dispatch_id>.
Brief: <brief path from dispatch send>
Report staging path: <report_staging_path from dispatch send, verbatim>
Coordinator CLI: <coordinator CLI>
Expected worker checkout: <worker_worktree from dispatch send, canonical absolute path>
Expected startup SHA: <worker_snapshot_commit from dispatch send>
Before task work, run git rev-parse --show-toplevel, git branch --show-current and git rev-parse HEAD
in your runtime's current directory. Compare the top-level path and HEAD with the expected values
above, and the branch with the brief. Stop on any mismatch; do not reset Git history or claim
another checkout as your actual directory. Confirm your active model and the probed Git top-level:
<coordinator CLI> dispatch self-report --dispatch <dispatch_id> --model "<actual active model>" --worktree "<probed Git top-level>"
Proceed only after a successful self-report; escalate a mismatch or unavailable model identity.
Immediately after self-report and at least every <heartbeat.every_seconds> seconds while working, run:
<coordinator CLI> dispatch heartbeat --dispatch <dispatch_id>
Contracts: before task work, read the common role contract <repo>/.harness/orchestration/roles/common.md
and your role contract <repo>/.harness/orchestration/roles/<role>.md. Write English coordination text
by <repo>/.claude/rules/technical-english.md and Russian report text by <repo>/.claude/rules/technical-russian.md.
Context Package <context_package_id>: start from its summary in the brief. Read only the indicated
start_line–end_line ranges needed for the task.
For more, read one section of the pinned package:
<coordinator CLI> context-package show --dispatch <dispatch_id> --section <section>
(for example related_tests, precedent_cards, memory or goal).
Work within the brief; escalate a blocker for anything the brief and the package leave out.
Before your final reply, write the completion report JSON to the exact report staging path using
the common and role-specific report contract, with report_language: ru.
Use exact English enums: outcome = completed | blocked | failed; checks_run[].result = pass | fail | not_run.
Set blockers and risks (also in every review axis) to {"status": "none", "details": ""} when absent,
or {"status": "present", "details": "<Russian description>"} when present. A none status requires empty
details; present requires a non-empty description. Put other explanations in output. Strings, translated
statuses, passed and not-run are invalid; no aliases or old report formats are accepted.
Then run:
<coordinator CLI> report submit --compact --file "<report_staging_path>"
Confirm the ledger receipt in one line. Relay any blocked transition or required next action.
If submission fails before recording, return the command and error as a blocker; keep the report file.
If the result includes completion, relay it to the coordinator for report complete; the report is
already recorded, so submit it only once. Chat text alone does not complete the dispatch.
```

An architect retry reads `retry_reason` from its immutable brief. The coordinator must record a
non-empty English `batch decide --note`; that note, source dispatch and decision digest are bound
to the next transition. Historical or structured retries without a human note carry their sealed
routing rationale with an explicit source instead; never label it a human explanation. Do not add an extra prompt file or read a sandbox-dependent TMPDIR.
An explicit human retry with a non-empty note acknowledges only that decision's unknown reason;
other attention findings remain independent.

Every developer session (initial, continuation and developer-retry) adds one line after
`Work within the brief`:

```text
<developer_skill.instruction from dispatch send or dispatch resume, verbatim>
```

When `dispatch send` or `dispatch resume` refuses because the installed developer skill is missing,
do not start the worker: stop and hand its remedy to the human. A batch pinned on a runtime from
before this field returns no `developer_skill`; then check that
`<repo>/.harness/skills/developer/SKILL.md` exists and build the same line with that absolute path.

A developer retry adds two lines from the `retry_start` of its `dispatch preflight`:

```text
Retry handoff: <retry_start.handoff, verbatim JSON>
Retry starting files: <paths from retry_start.starting_files>
```

Use this lifecycle for every new or resumed worker session, including developer-retry. A continuation
that stops at a checkpoint follows the checkpoint protocol instead of submitting a completion report.
The coordinator treats a final reply without recorded completion or a valid checkpoint as an
unfinished handoff and requests the missing protocol from the same available worker session.

Large documents (the role catalog, `playbook.md`, `git-workflow.md`) and
prior reports reach a worker only as Context Package section ranges or through the retry handoff.
A developer brief carries the accepted architect design in `accepted_design`; do not retell it in
the prompt.
The work a prompt asks for is exactly its brief plus, for a retry, the handoff's blocking findings (developer) or the retry reason line (architect).

A developer retry is always a new session started from its compact handoff, never a continuation of
the previous developer session's history. The preflight's decision packet carries the retry's
`retry_context_estimate` and `retry_context_warning` as evidence; they never gate the dispatch. Code-review and QA stay new
independent sessions; only their prompt follows this template. The playbook's "Developer-retry
handoff" defines the handoff, the smart-zone threshold and the compact.

## Authoritative guidance

This is the coordinator contract; conditional procedures live in `references/`, and it is not a
second orchestration manual. Full rules are module-owned guidance:

- `.harness/orchestration/playbook.md` owns lifecycle, authority, immutable brief, completion
  evidence, parallelism, and metric rules.
- `.harness/orchestration/roles/` owns each role's boundary, required proof, and specialist trigger.
- The `--help` output and the `remedy` of the coordinator CLI own command syntax and operational recovery.
- `.claude/rules/git-delivery.md` owns the mandatory branch, commit, merge, and PR-confirmation
  rules; `.harness/instructions/git-workflow.md` owns the issue-branch, push, and PR procedure.
- `references/issue-worktree.md` owns issue worktree creation and its recovery.

Follow those files rather than duplicating or weakening their rules here. In particular, do not
invent token metrics: use only provider- or runtime-observed telemetry and preserve missing-data
notes.

## Wrap-up

After an accepted publish, record the integration link before the branch is merged or deleted:
`python .harness/orchestration/coordinator.py --repo . integration prepare --ticket "#<ID>" --branch "<issue-branch>"`
(add `--batch <batch-id>` when several batches published the branch). It writes only an immutable
integration record and is safe to repeat; if it refuses, report its remedy to the developer and do
not work around it. Never edit the completed batch or its reports by hand.

Under `approval_policy: auto`, first show the final report of `batch auto-report --batch <id>`
(decisions, accepted risks, findings, retries, budget, DoD coverage, review and QA results).
Then offer `/to-pull-requests <ticket>`. Do not invoke it automatically, open
or merge a PR, write to an integration branch, or close the ticket in this skill. A pull request
needs the developer's explicit confirmation under every `approval_policy`; auto-merge is forbidden. Leave
`status::in-progress` on the ticket: replacing it with `status::done`, closing the ticket and moving its
unblocked dependents to `status::ready` belong to `/to-pull-requests` after the merge.
