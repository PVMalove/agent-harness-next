# Recovery

Before recovery, read the batch state and stop reason. Show the person the action, its consequences and required approvals. Do not edit store records by hand.

[Orchestration overview](../../backend-orchestration.md)

## Manual recovery and stage repeat {#manual-recovery-and-stage-repeat}

`batch auto-report` only reads the state. The detected cause is in `observed_stop`.
To record a stop, call `batch auto-decide` explicitly: the batch moves to `paused`, even if the
worker did not manage to send a report. A repeated call in paused does not change the ledger.

```bash
python .harness/orchestration/coordinator.py --repo . ledger validate
python .harness/orchestration/coordinator.py --repo . batch resume-stop \
  --batch <id> --approved-by '<оператор>' --approved-at '<текущий UTC>' --note 'worker checkout fixed'
python .harness/orchestration/coordinator.py --repo . batch rewind \
  --batch <id> --to code-review --approved-by '<оператор>' --approved-at '<текущий UTC>' --note 'repeat review'
```

`resume-stop` fits a confirmed worktree/model mismatch or an OS refusal to start the adapter,
but it restarts only a worker with a known outcome: `absent`, `reported`, `rejected-at-startup`,
or `stopped`. For a rejected self-report, the contract is unchanged: a human approval takes the dispatch out of
circulation, and the ledger rejects its late records. If `dispatch status` shows `live` or
`unknown`, the command refuses and changes nothing: stop the worker through its runtime and repeat
the command with `--runtime-stopped`. A missing self-report is not confirmed by `resume-stop`: stop the worker
and record `dispatch cancel --runtime-stopped`. If there is no structural proof, a cautious text heuristic looks for an infrastructure cause
(rate limit, timeout, network, runtime crash, resources, unavailable service) in the `blockers` of a blocked
report and in the runtime error. A sign of a problem with tests, linter, types, conflict, scope, or
requirements outweighs it; unknown text stays unknown. The match is recorded in the
event as `classification` with `method: heuristic`; it only suggests a cause, and the
human approval decides. It keeps the role, scope, candidate, and fix-forward findings. The repeat gets a new dispatch ID,
context, and approval. An operational attempt does not spend a second developer retry. When paused because of the
budget or an unknown cause, a pending report can be returned for a manual decision. When the budget of
infrastructure retries is exhausted, `resume-stop` refuses, and the batch stays in the stopped state
until a human decides: wait, fix the launch, change the attention policy, run `rewind`, or
separately decide `batch abandon`; the counters are not reset. Dirty files, an unknown SHA, failed
checks, and new code findings require the ordinary fix route.

After recovery, `manual_all` applies, including a continuation after a 429. The source `auto_stop`
and `auto_report` stay as history. The new report shows the current progress and `historical_report`.
`blocked` and `failed` hold the ticket/branch/worktree; a repeated batch is forbidden until they are closed.
Both abandon paths record `abandoned` and `last_accepted`. An old `failed` can be superseded only
with a proven human abandon; an ordinary failed is not a refusal of the work.

Rewind selects a reached stage: `architect`, `developer`, `code-review`, `qa`, or `publish`.
`verification` requires a registered candidate, and `resolve-conflict` requires a resolver boundary.
Old dependent approvals/reports/risk/QA are excluded from the active chain, but not deleted.
HEAD and commit objects stay in place. After a return to architect, a new accepted plan is needed;
after a return to a writer, the new attempt spends the developer retry budget. No counter is
reset. The `batch approve` requirement is kept until the first accept.

If a stage report is `blocked` only because of an infrastructure failure, and the work in the report looks
finished (for example, the developer commits match the plan, but the handoff to review failed),
a human can accept the stage conditionally:

```bash
python .harness/orchestration/coordinator.py --repo . batch decide --batch <id> \
  --decision accept-conditional --infrastructure-failure --note '<проверенная причина>' \
  --approved-by '<оператор>' --approved-at '<текущий UTC>'
```

The decision is recorded as `accept-conditional`, the pipeline goes on as after `accept`, and the stage
stays an open condition of the batch. An unconditional `accept` of a later gate independently closes the condition:
code-review or qa for architect, developer, and verification; qa for code-review and
qa. While the condition is open, publish and completion refuse. A conditional qa does not count as a green QA,
so publish still requires a real QA. A conditional publish is accepted only if the remote
branch already points to the candidate. The report must be `blocked` without failed checks, and the other
checks of an ordinary `accept` (commit plan, scope, DoD) are kept. Rewind lifts the conditions
of cancelled dispatches. If the stage can simply be restarted, `resume-stop` is preferable.

A live worker must first be stopped by the runtime means. Then the operator records
`dispatch cancel --runtime-stopped` with approved_by/approved_at/reason. A timeout does not prove a stop.
After that, a rewind can be run. The old dispatch no longer accepts a heartbeat/report/checkpoint.

For an old pinned batch, the new recovery commands use the installed runtime. An event with a
human approval links the source pin to the new control runtime and saves its snapshot.
The source immutable plan and the old brief/report do not change. `ledger validate` fixes nothing.

Before the handoff, pass one absolute `--worktree` to preflight and send. For a writer, the path must
match the issue worktree, branch, and startup SHA. The self-report checks the actual directory even
when two checkouts have the same SHA. The runtime must be able to select an existing directory; `isolation: worktree`
alone is not enough. The coordinator stays in the main checkout.

If the writer session ended before the first checkpoint, the operator can run
`dispatch resume --trigger startup-failure --runtime-stopped` with a new approval and `--note`.
The `--file` file contains exactly `dispatch_id`, `definition_of_done`, `dependencies`, `write_paths`,
`prohibited_changes` from the brief. A clean worktree must stay at the known startup SHA.
The command records separate startup evidence, spends the continuation budget, and requires a new
self-report/heartbeat. A changed scope, unknown commits, or a paused batch exclude this path.

### Batch hold and the `recovery` commands {#batch-hold-and-the-recovery-commands}

Unknown, missing, or unreadable system data does not become a decision (ADR 0026).
If strict reading rejects a batch record, `recovery resume` holds the batch with the record
`recovery/hold/<batch_id>.json` of the `operationalHold.v1` contract: the state is `held`, and the refusal has the step
`hold:<reason>`, where the reason is `unknown-value`, `missing-value`, or `unreadable-record`. The hold
writes no lifecycle record, decision, or approval, and a terminal batch is never held.
A hold record that cannot be read also holds the batch, but no `recovery` command releases it:
the remedy names `ledger validate --full` and an escalation to a human.

While the hold is in effect, these commands refuse with code 2, write nothing, and name the recovery route in `REMEDY`:
`dispatch propose` and `dispatch create`, `dispatch send`,
`dispatch self-report`, `dispatch checkpoint`, `report submit`, `qa run`, `dispatch publish`,
`batch decide`, `batch resume`, `batch resume-stop`, and `batch rewind`. The reaction to a finished
execution of a supervised dispatch also waits: `dispatch status --dispatch` shows the refusal as
`reaction_error`, and the report stays in `pending_report`. With an active `auto` policy, `batch auto-decide`
records an `integrity-failure`/`operational-hold` stop and never decides a report and never
makes an abandon; without an active policy, the command refuses like `batch decide`. The commands that stay available are
`dispatch heartbeat`, `dispatch cancel`, `batch abandon`, `batch attention check` and `resolve`,
`batch decision-packet`, and the read commands. `batch attention check` raises the attention
`operational-hold`. The decision packet of a held batch shows the `operational_hold` field, and empty
`options` and `recovery_route.commands`: `recovery status`, `batch attention resolve` (if the attention
is raised), and `recovery resume`.

Recovery never resolves the attention, and `recovery resume` refuses with `attention-open` while the
attention is open. So the order is: read the diagnostics, remove the cause, resolve the
attention, then release the hold.

```bash
python .harness/orchestration/coordinator.py --repo . recovery status --batch <id> --json
python .harness/orchestration/coordinator.py --repo . recovery reload --batch <id>
python .harness/orchestration/coordinator.py --repo . batch attention resolve --batch <id> --note '…' --approved-by … --approved-at …
python .harness/orchestration/coordinator.py --repo . recovery resume --batch <id>
```

The commands `recovery status|reload|resume|fix|abort --batch <id>` work only on the installed
runtime in the `runtime-store` epoch, do not read stdin, and need no TTY or Textual, so the console
calls them as a process:

| Code | stdout | When |
| --- | --- | --- |
| 0 | a `recoveryStatus.v1` document with `outcome: done` | the action is done |
| 2 | a `recoveryStatus.v1` document with `outcome: refused` | the policy refused; `refusals` and `diagnostics` name the reason |
| 2 | empty, `ERROR:` and `REMEDY:` in stderr | the command cannot run: the file ledger epoch (remedy `harness-runtime migrate`), a `runtime_client` refusal (`[runtime_unavailable]`, `[store_busy]`, `[revision_conflict]`), an incomplete approval, or an interruption |

The `recoveryStatus.v1` document is the console contract. It contains `contract`, `action`, `outcome`,
`batch_id`, `observed_at`, `resumable`, `lifecycle`, `hold`, `checks`, `diagnostics`,
`skipped_advisories`, `actions`, `intent`, and `next`. Each of the 13 checks (`config`, `store`,
`ledger`, `batch`, `lifecycle`, `runtime`, `snapshot`, `context`, `compatibility`, `operation`,
`liveness`, `attention`, `approval`) shows a status and diagnostics: the pointer, the redacted
expected and received values, a hint, and a remedy. Secrets do not get into the document.

- `status` only reads. `--skip <diagnostic-id>` (repeatable) hides an advisory from the
  closed list (`config-normalized`) for one call and writes nothing.
- `reload` rereads and checks the configuration and the runtime hello (protocol 1.5, `store_id`,
  features `state.read`, `state.write`, and `state.recovery`), returns this evidence under the key
  `runtime`, and does not start a worker.
- `resume` repeats the `status` checks in one write unit. A refusal of any check changes
  nothing, except the hold of a batch whose record strict reading rejects. Otherwise the command releases the
  hold and reacts to the observable execution of each open supervised dispatch:
  a finished execution gets a reaction (step `reconcile`), an `unknown` execution gives the refusal
  `ambiguous-effect`, and a live worker is not started a second time. A recorded stop continues
  only through the auditable `batch resume-stop`, for which `resume` accepts `--approved-by`,
  `--approved-at`, and `--note` (all three together or none); otherwise `batch rewind` is needed. The document
  adds `steps` (`hold`, `release`, `reconcile`, `resume-stop`), `refusals`,
  `dispatch_created: false`, `worker_started: false`, `status`, and `next`. `resume` does not create a
  dispatch, does not rewrite the brief, and does not change the attention, budgets, `auto_stop`, and terminal
  refusals; the next transition needs an approval with the current digest.
- `fix` shows a safe normalization of the configuration, and `fix --apply` applies it with a configuration
  transaction and resumes nothing.
- `abort` records an exit from recovery: it abandons nothing, stops nothing, and cleans nothing.

`reload`, `resume`, `fix`, and `abort` first write a durable intent
`recovery/intent/<batch_id>.json` (`recoveryIntent.v1`). After a cancel, EOF, or SIGINT, the intent
stays `interrupted`, and a repeat of the command completes the action. An internal exception gives the diagnostic
`internal-error` with a correlation ID, not a configuration error.

The Harness console (`harness console`, the Orchestration section) shows every recovery command in the
`batch` group: `recovery status`, `recovery reload`, the `recovery fix` preview, and `recovery abort` run
without confirmation. `recovery resume` records a terminal coordinator decision and `recovery fix --apply`
overwrites the configuration, so both ask for confirmation.

Recovery records follow the same authority as the lifecycle (ADR 0020, ADR 0021): Python
decides, the Rust store writes.

| Record | Decides | Writes | Write rules |
| --- | --- | --- | --- |
| `recovery/hold/<batch_id>.json`, `recovery/intent/<batch_id>.json` | Python: `operational_hold` and `recovery_api` in the command's write unit | Rust store, `state.write` (protocol 1.5, feature `state.recovery`) | only `create`, then `replace` by the row revision, `delete` refuses; the `batch_id` field equals the path id; the batch row exists in the same transaction; one audit record per mutation; no schema migration |
