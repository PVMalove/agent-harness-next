# Implement — Implementation

## 1. Name and localization

- **English name:** `Implement`
- **Russian translation:**

```text
Реализация
```

## 2. Full translation of the skill text

<div class="ah-skill-text" markdown="1">

```yaml
name: implement
description: Coordinate one backend ticket through the approved architect, developer, review, QA, and publish handoffs.
disable-model-invocation: true
```

### Implementation

**Objective:** take exactly one ticket through `architect → developer → code-review → qa → publish`,
then offer `/to-pull-requests`. This session **is** the coordinator: it creates and observes the
dispatches, but does not implement the ticket itself.

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

#### Route

This is the opt-in `backend-orchestration` route. Confirm that the installed coordinator is usable:

```bash
python .harness/orchestration/coordinator.py --repo . dispatch status
```

If the command is unavailable or does not read its state, stop and offer the developer
`/fast-implement`. A `ledger_busy` answer is not unavailability: another coordinator operation holds
the ledger lock, so repeat the command after its `retry_after_seconds`. Do not repair and do not
infer the opt-in capability. Take one ticket to a terminal batch state before starting the next.

Before any tracker write (the `status::*` label swap), confirm that the session is rooted in the main
checkout and can write every directory the pipeline writes:

- `.git/worktrees` (for an existing issue worktree: its git metadata directory from
  `git -C <worktree> rev-parse --absolute-git-dir`);
- the issue worktree directory, when it exists;
- `.harness/.sandboxes/scratch/inbox/`.

Probe each directory by creating and removing one temporary file. A sandboxed session writes only
inside its own directory, and a worktree another session created stays read-only under
`.git/worktrees` even from the main checkout. On a failure, stop with one message that names the
directory and the action: open the session in the main checkout, one that can write the issue
worktree and its git metadata. Touch neither the tracker nor the ledger. `batch create`, and
`dispatch preflight` and `dispatch send` for a write role, refuse an issue worktree or git metadata
directory the session cannot write.

If another batch holds the same unfinished ticket, branch, or worktree, or `concurrency_budget` is
exhausted, check `batch list --open`, the conflicting dispatch, and its decision packet. Tell the
developer which batch blocks the work and how to finish it in the normal order. If its worker can no
longer send a report, first run `batch auto-report`, `batch decision-packet`, `dispatch status`, and
`ledger validate`, and quote the `startup` assessment of this dispatch: the worker state, the failure
classification, and what remains unknown. Explain which option applies — waiting, fixing the start, a
human-approved `batch resume-stop`, `batch rewind`, or cancelling an unsent dispatch — and why the
others do not fit. Only after that, offer `batch abandon` as a separate explicit human decision about
the whole batch: show a copy-ready command with the actual batch ID, the verified operator name,
`--approved-at "$(date -u +%Y-%m-%dT%H:%M:%SZ)"`, and a reason based on the observed failure. Do not
substitute `--approved-by` as if the operator has already approved the action, and do not run the
command for the operator without that approval. `ledger clean` deletes only orphaned evidence, and
`ledger reset` does not clear an active batch.

#### Batch preparation

The coordinator takes every procedure from agent sources only: this skill,
`.harness/orchestration/playbook.md`, `.harness/orchestration/roles/`, the guides in `docs/agents/`,
and the `--help` and `remedy` output of the coordinator CLI. It does not take a procedure from a
Russian human document (`backend-orchestration.md`, `site/docs/`, `ARCHITECTURE.md`,
`site/docs/skills/`, `site/docs/hooks/`). It does not copy conventions from another batch and does
not read ledger files in `.harness/orchestration/state/`; it reads state only through CLI commands
(`batch list`, `batch decision-packet`, `dispatch status`). If these sources do not give a step, that
gap is a blocker: the coordinator stops, reports it to the developer, and does not reconstruct the
step.

Start these steps only after the ticket pre-flight in "The coordinator contract" (blockers,
`status::in-progress`).

1. **Integration ref.** Use the ticket's `## Integration Branch` value. If the ticket has no such
   section, use its `## Git base` value. If it has neither, use the same section of the parent epic.
   A missing value for a ticket that has a parent epic is a blocker; do not infer it from the
   checkout or from memory. A ticket without a parent epic uses `base_branch`: omit
   `--integration-ref`.
2. **Issue worktree.** Create it before `batch create`: `batch create` refuses a worktree that
   `git worktree list` does not show. The exact commands, and the recovery after a half-done
   `git worktree add -b`, are in `docs/agents/worktrees.md` → Coordinator issue worktree. Stay in the
   main checkout.
3. **Batch scope.** Run `batch preflight` with the same scope flags as `batch create`. Translate the
   ticket into English first: `batch create` rejects Cyrillic in `--goal`, `--definition-of-done`,
   and `--prohibited-change`. Keep commands, paths, and IDs verbatim.
4. **Create the batch.** Repeat the list flags once for each value.

   ```bash
   python .harness/orchestration/coordinator.py --repo . batch create \
     --ticket "#<ID>" --branch "feature/issue-<ID>-<slug>" --worktree "<absolute worktree path>" \
     --integration-ref "<integration-branch>" --goal "<English goal>" \
     --definition-of-done "<English item>" --prohibited-change "<English item>" \
     --allowed-path "<path or glob>" --expected-file "<path>" --expected-service "<service>" \
     --expected-changed-lines <N> --required-gate review --required-gate qa
   ```

   `--ticket`, `--branch`, `--worktree`, `--definition-of-done`, `--prohibited-change`, and at least
   one `--allowed-path` are mandatory. `--branch` must match `branch_pattern`. `--expected-file`,
   `--expected-service`, and `--expected-changed-lines` are mandatory when the project policy
   requires estimates. The CLI refuses an oversized ticket and prints a `remedy`.
5. **Approve the batch.** `batch approve --batch <id> --approved-by <operator> --approved-at <UTC time>`
   moves the batch from `planned` to `awaiting-approval`. This needs the operator's explicit
   approval: show the command, as for `batch abandon`, and do not run it for the operator.

**Commit plan.** The architect puts its plan in the report field `commit_plan`. `report submit`
refuses a plan that breaks the rules below or names a path outside the batch `allowed_paths`; an
accept pins the reported plan. Pass a plan file only when the report carries none, and pin it with
`batch decide --batch <id> --decision accept --approved-by <operator> --approved-at <UTC time> --commit-plan-file <path>`.
The operator approves this decision; never supply `--approved-by` for them. A plan file passed beside
a reported plan must hold the same plan. Write the file under `.harness/.sandboxes/scratch/inbox/` or
the project session scratchpad `.harness/.sandboxes/scratch/sessions/<session_id>/scratchpad/`; a path
outside the repository and its worktrees, such as an external `/tmp` scratchpad, is refused. The file
is a JSON object with the single key `commit_plan`: a non-empty list in commit order.

```json
{"commit_plan": [{"id": "tests", "summary": "Add failing tests", "expected_paths": ["tests/**"], "covers": [1]}]}
```

Each entry has exactly these fields:

- `id`: unique; up to 64 characters of letters, digits, `.`, `_`, `-`; the first character is a
  letter or digit;
- `summary`: non-empty;
- `expected_paths`: a non-empty list of relative paths or globs, with no leading `/` and no `..`;
- `covers`: a non-empty list of 1-based `--definition-of-done` item numbers, without repeats.

Every definition-of-done item must appear in at least one entry. The CLI rejects a broken file and
prints the expected format.

#### The coordinator contract

Resolve the tracker ticket, the issue branch, and the blockers without opening a second batch for the
same work. The ticket status is part of this pre-flight: after the write-access probe in "Route",
before `batch create`, and before the issue branch is created. Check the ticket's blockers under any
current label. If any is still open, stop, name them, and make sure that `status::blocked` is set.
Otherwise replace the `status::*` label with `status::in-progress` exactly as steps 2–3 of phase 1 of
`/fast-implement` do, and verify that it is the only `status::*` label. A failed label write is a
blocker, not a warning.

Before `batch create`, run the batch-level preflight with bounded expected files, services, and diff
size. Pin the writer's explicit scope with `--allowed-path` (repeat it; a path or glob inside the
developer's write ceiling): batches with overlapping files run in parallel in their own worktrees,
and a change outside the scope is rejected. If the preflight rejects the ticket, split it with
`/to-tickets`. Never ask an architect to discover whether an oversized ticket should have been split.
When you call `batch create`, pass `--required-gate review --required-gate qa`: the full implement
pipeline explicitly sets both independent gates, the Standards/Spec review and the serialized
clean-room QA. Before the write-role (`developer`) dispatch, verify that these mandatory gates are
recorded in the batch's `required_gates`. If they are missing, stop early rather than send a worker
past a risk gate.

For each handoff, choose the worker checkout and pass its absolute path as `--worktree` to
`dispatch preflight`. Show `batch decision-packet`, then create an approved immutable brief. Pass the
same explicit `--worktree` to `dispatch send`; code-review also keeps `--checkout`. Preflight and send
verify the selected path, branch, and startup SHA. Start the worker in exactly `send.worker_worktree`
with a runtime mechanism that supports that existing directory. Verify that mechanism before launch:
`isolation: worktree` alone does not prove attachment to an existing worktree. If the runtime cannot
select that checkout, report a blocker.

The coordinator stays in the main checkout. The coordinator itself never does `cd` into a worktree,
not even as `cd <worktree> && …`: the shell working directory persists between commands, so one
`cd` moves the whole session. Read worktree files by absolute paths: `git -C <abs worktree> …`,
`rg <pattern> <abs worktree path>`, and the file-reading tools with absolute paths. If the session
has moved after all, `cd` back to the main checkout before the next command. A selected path is only
intent; the self-report proves the worker's actual working directory. Pass the brief's
`report_staging_path` to the worker verbatim: a role that has to guess where its report belongs
writes it outside the project.

**Claude Code runtime.** The Agent tool cannot select an existing checkout: a subagent starts in the
main checkout, and `EnterWorktree` refuses it there. Two paths exist; state which one the batch uses.

- `external` (strict): set the worker roles' `transport` to `external` in
  `.harness/orchestration.json` and send with
  `--adapter <main-repo>/.harness/adapters/claude_worker.py` (absolute path). `dispatch send` runs
  the adapter in `send.worker_worktree`, and the adapter runs a headless `claude -p` there with the
  brief's model, effort, and `allowed_tools`, so the worker's working directory is the issue
  worktree. Under the runtime (a brief with `execution`), the adapter waits for the worker in the
  foreground and exits with its code; without `execution`, it detaches the worker. The adapter
  builds the prompt. For a retry, put the retry lines in a file inside the repository and pass
  `--adapter-arg=--extra-prompt-file=<path>`. A permission layer may refuse launching an agent from
  the coordinator session. That refusal is a stop: show the developer the exact `dispatch send`
  command to run in their own terminal, then continue with `dispatch wait`.
- `in-process` (weaker evidence): the subagent's working directory is the main checkout, so the
  template's directory check would stop it. Replace that check in its prompt: it probes
  `git -C <worker_worktree>` for the top-level, branch, and HEAD, runs every command with `git -C` or
  `cd <worker_worktree> &&`, and uses absolute paths for every file. Its self-report then proves the
  checkout it works in, not its working directory; say so in the final report.

**The test author in the full route.** The author inherits runtime/model/effort from the approved
developer brief, without a separate role assignment or a project-profile override. A selected
runtime without a protected adapter returns `runtime_unsupported` and keeps the ordinary TDD. The
current protected adapter lets an `external` Claude Code developer call the author in
`send.worker_worktree` through `Agent(test-author)` without model/effort overrides. Before the
dispatch, install the harness in that exact checkout. A linked worktree of a repository whose main
checkout the human trusted in Claude Code needs no trust dialog of its own and no
`CLAUDE_PROJECT_DIR` export: the preflight takes the project root from Git (ADR 0033). Never copy the
main checkout's runtime state or trust.

The developer runs its own
`.claude/hooks/test-author-preflight.sh --worktree <send.worker_worktree> --brief <approved brief path>`
and enables the author only after exactly `{"status":"ok"}` and an `Agent(test-author)` or `Agent`
permission in the approved brief. The default developer role policy includes the named permission; a
project override remains authoritative. A missing permission gives `agent_tool_unavailable` and the
ordinary TDD, never a launch-time tool expansion. Pass the author the shared runner log root from the
adapter prompt and one test path within the brief's scope.

For `in-process`, the main-checkout preflight with `--worktree <send.worker_worktree>` answers
`checkout_mismatch`: the main checkout's guard and runner serve only the main checkout. The worker
prompt therefore names that worktree's launcher for each handoff:
`python3 -I -B <send.worker_worktree>/.harness/health/test_author.py run --repo <send.worker_worktree> --brief <approved brief path> --prompt-file <path>`.
The launcher checks that worktree's preflight and starts the author with its guard and runner, under
the same brief permission rule. A refusal (exit 3 with a reason) keeps the ordinary TDD with that
reason. Keep the selected executor visible in refusals, and never substitute Claude for an
unsupported runtime. A preflight refusal or an unavailable author never creates a blocker and never
changes the Rust ledger. State this in the worker prompt.

`dispatch send` checks the adapter's flags against its `dispatch --help` before the handoff and
rejects an unsupported flag. Fix the `--adapter-arg` values and send the same approved dispatch once
more. Show the `limitation` from `adapter_preflight` in the send result when it is present. To
diagnose an app-server runtime without a worker, run `dispatch runtime-probe`; its result is
evidence, and the worker's model self-report stays mandatory.

The coordinator never writes feature code and never repairs state by hand. A report is evidence, not
the authority to advance. The architect precedes the developer; an accepted candidate passes the
required review, QA, and publish gates. A write-role worker that stopped before any change returns an
honest report with `outcome: blocked`, bound to the verified checkout commit, with empty
`changed_files` and no checks run. The coordinator decision packet returns an explicit recovery route
(`retry`, `block`, or a human-chosen `abandon`) without registering a candidate and without weakening
the validation of `completed` reports.

Before every write-role dispatch, the immutable brief carries an ordered commit plan. Each entry
names one independently reviewable logical change, its expected files, and the DoD items it covers;
use one entry only when the entire approved change is inseparable. The coordinator derives one entry
per DoD item; to use the architect's plan instead, pin it on the architect accept with
`batch decide --decision accept --commit-plan-file <path>`. A recovery keeps the accepted plan, or
replaces it with a newly approved plan that explains the changed boundary. The developer's completion
report maps every created commit to the entries it closes. A mapping that is not one-to-one needs
`dod_coverage` and `divergence_justification`. A report with a `not_covered` item can be accepted
only through `override-warning` with a note other than `none`, or returned with `retry`. A report
whose `changed_files` lie outside the brief's `write_paths` is recorded with a `scope_warnings` entry
and is accepted only the same way. Do not merge unrelated implementation, tests, documentation, or
type-only repairs into one recovery commit merely because they are staged together.

Follow the configured approval policy. Under `manual_all`, every transition needs explicit approval:
show the decision packet, ask, and wait. Under `low_risk`, the coordinator accepts a clean completed
report of a batch whose allowed paths lie inside `low_risk_paths` with an audited policy decision,
and the next eligible dispatch may already be approved. Under `milestone`, clean reports outside the
QA, publish, and risk milestones are also accepted automatically; stop at the remaining milestones.
Continue from the recorded `next_action` without asking the operator to repeat a policy decision.
Blockers, failed checks, risk triggers, review findings, and publish still require the applicable
manual decision. Never write `--approved-by` on the operator's behalf and never narrate a decision
the operator did not make. `human_approval_gate: tty` requires confirmation on the operator's
terminal for transitions that still need human approval. When you choose a recovery route for
`retry` or `abandon`, show the decision packet's `route_preview` (with the `--reason-category` or
`--retry-role` you intend to pass to `batch decide`) and follow the Recovery route table in
`.harness/orchestration/playbook.md` (situation → route → who approves → evidence). Report each
startup failure under its own classification (unsupported flag, missing or refused self-report,
capacity, rate-limit, service-unavailable) together with its recovery route.

When the runtime store holds a batch (attention `operational-hold`, or a refusal whose `REMEDY`
names recovery), run `recovery status --batch <id> --json`, fix the cause, resolve the open
attention, and run `recovery resume --batch <id>`. Recovery never reruns an accepted stage and never
starts a worker: continue with the `next` command it prints. An `ambiguous-effect` refusal waits for
a human decision. After a configuration edit, run `config validate --canonical --json` before the
next transition. Details: "Operational hold and recovery commands" in
`.harness/orchestration/playbook.md`.

Under `approval_policy: auto`, the coordinator makes each path decision by policy and writes it as
`policy:auto`; follow "Automatic path" in `.harness/orchestration/playbook.md`. Do not write
`--approved-by` or `--approved-at`: run `batch approve`, `dispatch create`, and a planned
`dispatch resume --trigger` without them. For every pending report that the `report submit` or
`qa run` chain did not accept, including the publish report, run `batch auto-decide --batch <id>`.
Pass only:

- `--commit-plan-file` with an exact copy of the architect's plan, only when the report carries no
  `commit_plan`;
- `--findings-file` for coordinator findings on a developer report;
- `--bug-ticket` after you file or reuse the tool's bug ticket through the tracker CLI;
- `--block-bypass --note` when a role worked around a block.

Pass nothing else, and never choose the decision yourself. After a refused command, run
`batch auto-report --batch <id>` to observe the evidence. This read-only command does not record a
stop. If it shows `observed_stop`, run `batch auto-decide --batch <id>` to record the pause, even
without a pending report, then show `batch auto-report` again. The automatic path ends permanently
at that pause. Check `batch decision-packet`, `dispatch status`, and `ledger validate` before you
offer waiting, fixing the start, a human-approved `batch resume-stop`, or `batch rewind --to <gate>`
to repeat an earlier gate. If the infrastructure budget is exhausted, the batch stays paused until
such a human decision. Use the playbook's "Operator recovery" procedure. The original stop stays in
the history; all later approvals, including recognized 429 continuations, follow `manual_all`.
Honor an approval the human already gave explicitly in this session for the concrete operation;
never invent one.

When a stage's report is `blocked` only by an infrastructure failure although its work looks
complete (for example, the developer's commits match the plan), a human may decide
`batch decide --decision accept-conditional --infrastructure-failure --note <cause>`. The pipeline
advances as after `accept`, but the stage stays an open condition that a later code-review or qa
accept must close independently; publish refuses while one is open. Never choose this decision
yourself, and prefer `resume-stop` when the stage can simply be restarted.

A worker that bypassed a hook or tool block (with another form of the command, another tool, a
script file, `eval`, another interpreter, or a split command) violates the protocol: such a
report cannot be accepted or closed through an override warning, and the violation is recorded in `--note`. For
the architect and the developer (publish included), the decision is `retry` with the developer category (not `tooling`) or
`block`. For the read-only role code-review, qa, or verification, `--reason-category block-bypass`
is passed to `batch decision-packet` and, when its `route_preview.retry.route` equals `bypass-rerun`,
to `batch decide --decision retry`: the same stage repeats on the same SHA without a new candidate and
without spending a developer retry, and a new dispatch requires explicit approval under any `approval_policy`
except `auto`.

A report that instead
stopped with `tooling_blocker` is checked first, before its retry: its `command` is legal under the brief (allowed paths and
tool policy), and the `message` rejects it. If this is a false trigger, file or reuse a
bug ticket for the tool through the tracker CLI (tool, command, message, dispatch ID), name it
in `--note`, and run `batch decide --decision retry` when `route_preview.retry.route` equals
`tooling-retry`: the same stage repeats on the same SHA (the developer continues from its last
commit), and `retry_policy.max_developer_retries` is not spent. An illegal command is not a false
trigger: retry with the developer category that the evidence confirms. The
`tooling-retry-repeated` attention, raised by a third consecutive tooling retry on one candidate, is cleared only
after the tool is fixed.

A defect found in a clean developer report whose DoD is met inside its allowed paths is no reason for a retry:
accept the report through `batch decide --findings-file <path>`, or after a policy auto-accept run
`batch carry-over --batch <id> --findings-file <path>` while the code-review dispatch is not created. The
finding goes into the code-review brief as a carried-over item (the `carry-over` route), and the single developer
retry is spent after the review. Retry a developer report without an accept only for an unmet DoD item
or a change outside the scope.

Each worker records a model self-report and is observed by the event-driven watchdog; these facts
serve as evidence and never give a reason to edit the immutable brief.

Use the brief's shared Context Package ID across the architect, the developer, and resumed worker
sessions while the pinned base/candidate is unchanged. Before escalating, read only its starting
files and directly referenced symbols. A changed candidate creates one new shared package for its
review, not a duplicate per role. Continuations and retries stop at the project budget; a 429 is no
exception to that budget.

Run `dispatch wait` between send and report. `stale`, a model or worktree mismatch, a changed harness
snapshot, and a failed deterministic gate are blockers for the coordinator, not prompts for a broad
LLM recovery. Silence or a timeout does not prove that the worker stopped. `batch resume-stop`
refuses a worker whose `startup` state is `live` or `unknown`: stop it through its runtime and repeat
the command with `--runtime-stopped`. The `in-process` and external transports keep the same brief
and evidence contract.

A busy ledger (`ledger is locked by another operation`, or `ledger_busy` from `dispatch status`) is
transient: repeat `dispatch wait` or `dispatch status`. When a relayed `report submit` result carries
`completion`, the report is already recorded: never ask the worker to submit it again. Run its
`command` (`report complete --dispatch <dispatch-id>`) yourself and repeat it until no step fails; it
is idempotent. When the failed step needs a human, follow its remedy instead. Never remove the ledger
lock or any state file by hand. A lock that stays held goes to
`coordinator.py --repo . ledger release-lock`, which refuses a lock whose owner process is alive.
`ledger lock-status` shows the holder and the time left until a timeout release without taking the
lock. For the lock of a stopped sandboxed worker, show the operator a copy-ready
`ledger release-lock --force --approved-by <operator> --approved-at <time> --reason <why>`. It is the
operator's action, never yours, under every `approval_policy`.

In the runtime-store epoch, coordinators of different batches write in parallel and read from
snapshots. A `revision_conflict` on `generation` means that another command decided over every batch
first: repeat the command. The QA lane is a lease with a fencing token and a heartbeat
(`lease_ttl_seconds`). An expired lease of a dead owner (`owner-dead`) needs no `--force`: the next
`qa run` or a plain `ledger release-lock` reaps it. `[lease_held]` with `stale_heartbeat=true` means
that the owner may be alive (`owner-alive`, `owner-pid-reused`, `owner-in-other-environment`,
`owner-unknown`). Such a lease is never released automatically; only the operator's
`ledger release-lock --force` or `qa clear-stale-lease` clears it. `harness-runtime serve` must run
in a PID namespace that sees the coordinators.

Never start `harness-runtime serve` from your own Bash. In Claude Code, the `runtime-autostart` hook
starts it before the first coordinator command and releases it at the end of the turn (ADR 0031); in
Codex and on Windows, the developer starts it. On a `[runtime-autostart-failed]` warning or a
`[runtime_unavailable]` refusal, stop the route and relay the cause, the remedy, and the journal path
(`<repo-id>.serve.log`) to the developer.

#### External launch and observation

Use the shipped example explicitly: `--adapter .harness/orchestration/adapters/claude_code.py`;
`claude` and `codex` are runtime executables, not adapters. Read the playbook's "Observable external
workers" section for its visible-console requirement, the explicit background choice, the native
access probe, and the per-invocation sandbox mode. A parent-side probe does not prove the worker
tool's sandbox access. Run the native worker probe before feature work; a permanent EROFS/EPERM needs
an environment repair.

Use `dispatch wait` for lifecycle signals. The console and `dispatch observe` read the existing events
locally: no extra model calls, agent progress prompts, or logs in the model context for observation.
For a supervised worker, `dispatch logs --dispatch <id> --follow` prints its run-log events as JSON
lines until the execution ends, without holding the ledger lock. An `in-process` worker has no event
stream (`stream_reason` says so); follow its self-report, heartbeat, and the `checkpoints` that
`observe` lists. A proven early exit takes the path auto-report → auto-decide → human
`resume-stop --restart`; the one confirmation covers only an unchanged successor and never resets the
infrastructure budget. A ready but unsent report takes the playbook's "Delivering a worker report
after a tool refusal" section, not another developer run. Keep the original file and check results
and the relay provenance.

#### The worker prompt

Every worker prompt is this template, filled from the result of `dispatch send` and the CLI call
that sent it. The brief and the Context Package carry the task; the prompt also carries the mandatory
lifecycle. `<coordinator CLI>` is substituted with the Python executable, the absolute path of `coordinator.py`,
and the absolute `--repo` of the original dispatch (plus `--state-dir` when it is set). Paths are escaped for the
worker shell. The ledger address is preserved even when the worker runs in another worktree. The heartbeat interval is
copied verbatim from `dispatch send.heartbeat.every_seconds`.

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
Context Package <context_package_id>: start from its starting_files, symbol_graph and
related_tests. For a starting file with non-empty sections, read only the start_line–end_line
ranges the task needs.
Work within the brief; escalate a blocker for anything the brief and the package leave out.
Before your final reply, write the completion report JSON to the exact report staging path using
the common and role-specific report contract, with report_language: ru.
Use exact English enums: outcome = completed | blocked | failed; checks_run[].result = pass | fail | not_run.
Set blockers and risks (also in every review axis) to {"status": "none", "details": ""} when absent,
or {"status": "present", "details": "<Russian description>"} when present. A none status requires empty
details; present requires a non-empty description. Put other explanations in output. Strings, translated
statuses, passed and not-run are invalid; no aliases or old report formats are accepted.
Then run:
<coordinator CLI> report submit --file "<report_staging_path>"
Completion means the report is recorded in the ledger. Include the submit result in your final reply.
If submission fails before recording, return the command and error as a blocker; keep the report file.
If the result includes completion, relay it to the coordinator for report complete; the report is
already recorded, so submit it only once. Chat text alone does not complete the dispatch.
```

An architect retry reads `retry_reason` from its immutable brief. The coordinator must record a
non-empty English `batch decide --note`; that note, the source dispatch, and the decision digest are
bound to the next transition. Historical or structured retries without a human note carry their
sealed routing rationale with an explicit source instead; never label it a human explanation. Do not
add an extra prompt file and do not read a sandbox-dependent TMPDIR. An explicit human retry with a
non-empty note acknowledges only that decision's unknown reason; other attention findings stay
independent.

A developer retry adds two lines from the `retry_start` of its `dispatch preflight`:

```text
Retry handoff: <retry_start.handoff, verbatim JSON>
Retry starting files: <paths from retry_start.starting_files>
```

This lifecycle is mandatory for every new or resumed worker session, including a developer retry.
A session that stopped at a checkpoint follows the separate checkpoint protocol instead of the completion
report. Final text without a recorded completion or a valid checkpoint is an unfinished
handoff; the coordinator requests the missing protocol from the same available worker session.

Large documents (the role catalog, `playbook.md`, `git-workflow.md`) and earlier reports reach the
worker only as section ranges of the Context Package or through the retry handoff. A developer brief
carries the accepted architect design in `accepted_design`; do not retell it in the prompt. The
prompt assigns exactly its own brief and, for a retry, the blocking findings from the handoff
(developer) or the retry reason line (architect).

A developer retry always starts a new session from the compact handoff and does not continue the history of the previous
developer session. The decision packet of the preflight carries `retry_context_estimate` and
`retry_context_warning` as evidence; they never block a dispatch. Code-review and QA stay new independent sessions; by the template
only their prompt changes. The handoff, the smart zone threshold, and the compact are defined in the
"Developer-retry handoff" section of the playbook.

#### Authoritative guidance

This is a short coordinator contract, not a second orchestration procedure. The full rules are
module-owned guidance:

- `.harness/orchestration/playbook.md` owns the lifecycle, the authority, the immutable brief, the completion
  evidence, the parallelism, and the metric rules.
- `.harness/orchestration/roles/` owns the boundary, the required proof, and the specialist trigger of each role.
- The `--help` output and the `remedy` of the coordinator CLI own the command syntax and the
  operational recovery.
- `docs/agents/git-workflow.md` owns the issue-branch, commit, push, and PR boundaries.
- `docs/agents/worktrees.md` owns the issue worktree creation and its recovery.

Follow these files without duplicating or weakening their rules. Do not invent token metrics:
use only provider- or runtime-observed telemetry and keep the missing-data notes.

#### Completion

After an accepted publish, record the integration link before the merge or the deletion of the branch:
`python .harness/orchestration/coordinator.py --repo . integration prepare --ticket "#<ID>" --branch "<issue-branch>"`
(add `--batch <batch-id>` when several batches published the branch). The command writes only the
immutable integration record and is safe to repeat; on refusal, give its remedy to the developer and do not bypass it. Do not
edit a completed batch and its reports by hand.

Under `approval_policy: auto`, first show the final report of `batch auto-report --batch <id>`
(decisions, accepted risks, findings, retries, budget, DoD coverage, review and QA results).
Then offer `/to-pull-requests <ticket>`. Do not run it automatically,
do not open or merge a PR, do not write to the integration branch, and do not close the ticket with this skill. A pull
request needs the developer's explicit confirmation under every `approval_policy`; auto-merge is
prohibited. Leave
`status::in-progress` on the ticket: closing it and moving the unblocked dependents to `status::ready` is done by
`/to-pull-requests` after the merge.

</div>

## 3. Contracts

- **Input:** an AFK ticket, the installed opt-in capability, and the developer's explicit approvals.
- **Process:** the coordinator runs five handoffs, checks the model self-report and the liveness, and accepts
  only proven reports.
- **Output:** the accepted candidate SHA, the QA evidence, and an offer of `/to-pull-requests`.

## 4. Architecture diagram

![/implement: the pipeline with gates](../diagrams/previews/implement-pipeline.workflow.png)

## Recovery

`auto-report` observes, `auto-decide` records `paused`. A manual `resume-stop` and `rewind --to`
keep the original stop and enable `manual_all` for all following steps, including 429.
A human accepts a stage report that an infrastructure failure alone blocked after the work was finished with the
`accept-conditional` decision: the stage stays an open condition that a later independent gate
closes, and publish refuses until then. Without structural evidence, `resume-stop` proposes a cause
through a cautious heuristic over the blockers text; the human still decides.
Rewind does not change the Git history, but excludes the old dependent QA/review/risk from the active chain.
The counters are kept. Repeated developer work spends the retry budget; a restart after a
confirmed environment failure draws on a separate infrastructure budget.

Before send, the coordinator checks the explicit worker directory with `--worktree`, and the worker confirms the
actual path/branch/HEAD with the self-report. The coordinator CLI stays bound to the main repo/state.
The coordinator itself never does `cd` into a worktree, not even as `cd <worktree> && …`: the shell working directory
persists between commands, so one such call moves the whole session into the worktree. Worktree files
are read by absolute paths: `git -C <worktree> …`, `rg <pattern> <path in the worktree>`, and the file-reading
tools. If the session has moved after all, return it to the main checkout before the next
command.

When the runtime store holds a batch (attention `operational-hold`, or a refusal whose `REMEDY`
names recovery), run `recovery status --batch <id> --json`, fix the cause, resolve the open
attention, and run `recovery resume --batch <id>`. Recovery never reruns an accepted stage and never
starts a worker: continue with the command from the `next` field. An `ambiguous-effect` refusal waits
for a human decision. After a configuration edit, run `config validate --canonical --json` before
the next transition. The detailed limits are set by `.harness/orchestration/playbook.md`, section
Operator recovery.

### Worker startup failure

Silence, a timeout, or a missing report does not mean that the task has lost its purpose. Before
offering recovery or `batch abandon`, the coordinator runs the read-only commands
`batch auto-report`, `batch decision-packet`, `dispatch status`, and `ledger validate`.
`dispatch status` shows the `startup` assessment for each dispatch: the worker state (`absent`,
`reported`, `rejected-at-startup`, `stopped`, `live`, or `unknown`), the failure classification, and what
remains unknown. Capacity, rate-limit, and service-unavailable are classified separately from
code defects.

`dispatch send` validates the `--adapter-arg` flags against `dispatch --help` of the adapter before it passes the brief,
so an unsupported flag stops the send, and the dispatch stays approved and
unsent. `dispatch runtime-probe` checks the app-server runtime on an ephemeral read-only thread
without tools: the brief model in `model/list`, the `thread/start` fields, and the completion of one turn. A
capacity error after `thread/start` gives a classified failure, not READY. The probe writes nothing to the
ledger and does not replace the model self-report.

`batch resume-stop` restarts only a worker with a known outcome. If `startup` shows
`live` or `unknown`, the command refuses: the operator stops the worker through the runtime and repeats it
with the `--runtime-stopped` flag. For a rejected self-report, the previous contract does not change: a human
approval retires the dispatch, and the ledger rejects its late records. If the infrastructure
budget is exhausted, `resume-stop` refuses, and the batch stays paused until a human decision: wait,
fix the start, change the attention policy, run `rewind`, or decide on
`batch abandon` separately. `dispatch cancel`
cancels only an unsent dispatch, and `batch abandon` closes the whole batch; the brief, the report,
the Context Package, and the audit stay as evidence in both cases.

## Updating the launch and observation route

An example `.harness/orchestration/adapters/claude_code.py` ships, selected explicitly with
`--adapter`. The runtime executable is selected separately; the pack does not turn `codex` into an adapter.
The parent's access is checked and, before feature work, the worker's own tools. A global
sandbox shutdown is not required; an unsuitable profile is not repeated without preparing the environment.

The console reads the existing stream locally, without extra tokens and model messages.
The receipt, the process, the exit code, the ledger, and the handing over and acceptance of the report are shown separately. The first self-report
has its own deadline; only a proven outcome allows recovery. `resume-stop --restart`
allows one human confirmation to approve an unchanged successor, keeping manual_all
and the operational budget. A ready source report can be passed through the standard report relay with an audit,
keeping fail/not_run. The architect-retry reason now comes from brief.retry_reason; the external
extra-prompt-file and the manual Retry reason line are no longer needed.

## Source

[SKILL.md](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/implement/SKILL.md)
