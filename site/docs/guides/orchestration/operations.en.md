# Diagnostics and state

Start with status and diagnostics. Change records only through the coordinator CLI. Lock release, migration and resuming stopped work have different conditions and approvals.

[Orchestration overview](../../backend-orchestration.md)

## Compatibility and migration {#compatibility-and-migration}

All new batch fields and the four brief fields (`transition`, `transition_digest`, `retry_idempotency_key`,
`orchestration_policy`; either all or none) are optional. Records created earlier remain valid, the ledger version
does not change, and `ledger migrate` is not needed. New records pass the same integrity check (`context_pressure`
with a hash, the shape of the attention fields, brief consistency). The CLI behavior changed: `dispatch create` with
`--approved-by` now requires `--transition-digest`. A brief without the field `commit_plan_divergence` and a batch
without `commit_plan` also remain valid. A plan entry without `covers` covers the DoD item by its position. A brief
without `carried_items`, a transition without `carried_items_sha256`, a batch without `carried_items`, and a
code-review report without `review.carried_items` are also valid. An empty channel adds nothing to the transition,
so earlier digests do not change. A report without `incomplete_items` and a brief without the kind
`incomplete-item` are also valid. The new source kind, the report field, and the route value `narrowed-retry` were
introduced without a ledger version change and without a migration. A routing record without `retry_item_ids`, the
report field `carried_item_closure`, and the route value `fix-forward` were also introduced without a ledger
version change and without a migration. A developer-retry brief for a decision recorded before them gets a section
without a check against `retry_item_ids`. A completed developer-retry report that was recorded before the
`fix-forward` route appeared, without `carried_item_closure` for a brief with carried items, is still decided
through `batch decide`. Each item gets the status `omitted` and enters `carried_items_gap`. So `accept` and the
policy auto-accept are rejected, and `override-warning` requires a `--note` other than `none`. `retry`, `block`,
`fail`, and `abandon` are available. `report submit` rejects a new report of this kind. A brief without
`rebase_target_commit`, a transition without `rebase_target_sha`, and the route value `rebase-fix-forward` were also
introduced without a ledger version change and without a migration: a transition without a target keeps its
earlier digest. A brief without `delta_review_scope` and a transition without `delta_review_sha256` are also valid
and were introduced without a ledger version change and without a migration: a code-review transition without the
section keeps its earlier digest. The `supersedes` reference in a batch and plan and the route value `supersede`
were also introduced without a ledger version change and without a migration: a batch and plan without the
reference are read as before.

The `route` field in a routing record and the `decision` detail in the transition audit record of a batch are also
optional and were introduced without a ledger version change (it stays 3). A decision recorded before them is read
as is and remains valid. `ledger migrate` does not add or derive a route for it. Only a new `batch decide` decision
writes a route. A recorded `route` outside the closed set of routes is rejected when the batch is read.

## Inventory and closing a dead-end batch {#inventory-and-closing-a-dead-end-batch}

To see what exists and what is not closed:

```bash
python .harness/orchestration/coordinator.py --repo . batch list --open
python .harness/orchestration/coordinator.py --repo . batch list --ticket '#123'
```

The normal path to a terminal state is `batch decide`, but it requires exactly one report awaiting a decision, and a
report requires a live dispatch with a confirmed model. A worker that died before its self-report never reports, and
neither `fail` nor `block` can close such a batch. A separate command exists for this case:

```bash
python .harness/orchestration/coordinator.py --repo . batch abandon \
  --batch <batch-id> --approved-by 'approver name' --approved-at <approval-time-utc> \
  --reason 'worker died before the model self-report, the decision is unreachable'
```

It requires an explicit approval and a non-empty reason, moves the batch to `abandoned`, keeps `last_accepted`,
marks all unclosed dispatches as `abandoned`, and writes the decision next to the others. **It deletes nothing**: the
immutable brief, the reports, and the QA artifacts stay in place. You cannot apply it again to a batch that is
already terminal.

After a confirmed launch failure, continue the same batch after you remove the cause:

```bash
python .harness/orchestration/coordinator.py --repo . batch resume-stop \
  --batch <batch-id> --approved-by 'operator name' --approved-at <current-UTC-time> \
  --note 'fixed the worker launch directory'
```

The command keeps the accepted reports, the original stop, and `next_action`, marks the failed dispatch as
`abandoned`, and moves the batch to `awaiting-approval`. The next `dispatch create` requires a new approval and keeps
the contract of the interrupted role. The detailed limits are described in the section ["Manual recovery and stage
repeat"](recovery.md#manual-recovery-and-stage-repeat). For an unknown reason, or to return to an earlier gate, use `batch rewind`. `completed` and `abandoned` are
final.

Before sending, `dispatch send` checks the `--adapter-arg` flags against the adapter's `dispatch --help` and rejects
an unsupported flag before it passes the brief: the dispatch stays approved and unsent. If `--help` does not
respond, the result goes to `adapter_preflight` as a `limitation`.
`dispatch runtime-probe --dispatch <id> --runtime-command <runtime> --runtime-arg=app-server` checks the app-server
runtime without a worker: `model/list`, the `thread/start` fields, and one `turn/start` on an ephemeral read-only
thread without tools. A capacity, rate-limit, or unavailability error after `thread/start` gives a classified
failure, not READY. The probe writes nothing to the ledger and does not replace the model self-report.

The `stale` watchdog does not prove that the process ended. First stop the worker through its runtime, then record
`dispatch cancel --runtime-stopped` with a human approval and run a rewind.
The compatible command `batch resume` applies only to the earlier manual path without auto/recovery.
For a stale dispatch, it also requires `--runtime-stopped`, `--approved-by`, and `--approved-at`.

For an unfinished initial developer, pin the saved HEAD through `--candidate-commit` at the next
`dispatch preflight`, `dispatch propose`, and approved `dispatch create`. This is a startup snapshot, not an
accepted completed candidate: the risk assessment and the later gates follow the acceptance of the final report.
The commit map of the initial work covers the whole original plan from the batch base, including the commits saved
before the failure. Earlier risks stay in the report. `developer-retry` keeps a separate contract: only new commits
after the snapshot.

A batch is pinned to the runtime under which it was planned. `batch create` records the hash of the whole runtime
package in `.harness/`: the top-level modules and all subpackages (`orchestration/`, `gate_runner/`,
`context_builder/`, and others). It also stores an immutable snapshot of this package in
`.harness/orchestration/state/runtimes/`. If the runtime is reinstalled after that (for example, by
`harness update` from the branch of another task), the commands of this batch (`--batch`, `--dispatch`, or
`dispatch_id` in the `--file` file of `report submit`, `dispatch checkpoint`, and `dispatch telemetry`) run
automatically from the snapshot code. The role descriptions also come from the snapshot. New batches get the new
runtime. So tasks run in parallel and do not block each other. A snapshot that was changed by hand is rejected. For
a batch created before snapshots existed, the hash covers only `orchestration/`, and there is no snapshot. Restore
it from the package of the revision on which the batch was planned: a `.harness` from a temporary worktree where
`harness update` has run, or the `harness/` directory from `git archive <revision> harness`, will do:

```bash
python .harness/orchestration/coordinator.py --repo . batch restore-runtime \
  --batch <batch-id> --from <path to the package of the pinned revision>
```

The command accepts a directory only if its hash matches the pinned one. The snapshot and the new runtime work with
one ledger. So `ledger migrate` to a new schema version refuses to run while unfinished batches pinned to another
runtime exist. First finish them or cancel them on their own runtime.

If the pinned snapshot already satisfies all DoD items, do not create a fictitious commit for a write-role report
and do not use `abandon`. Record a separate terminal decision:

```bash
python .harness/orchestration/coordinator.py --repo . batch not-required \
  --batch <batch-id> --approved-by 'approver name' --approved-at <approval-time-utc> \
  --reason 'pinned snapshot already satisfies every definition-of-done item'
```

The command leaves audit evidence, cancels unclosed dispatches, moves the batch to `completed` with
`completion_kind: no-implementation`, and returns a recommendation to close the linked issue with the label
`resolution::wontfix`. An ordinary write-role report must still contain a real commit and the exact changed files.

If you find an error **before** the brief is passed to the runtime, do not abandon the batch. Cancel only this
unsent dispatch: the immutable brief stays in the audit trail, and the batch returns to `awaiting-approval` and can
get a corrected dispatch.

```bash
python .harness/orchestration/coordinator.py --repo . dispatch cancel \
  --dispatch <dispatch-id> --approved-by 'approver name' \
  --approved-at <approval-time-utc> --reason 'fix the assignment before the worker starts'
```

Never edit the files in `.harness/orchestration/state/` by hand. These records are the evidence for which the whole
route exists. If there is no standard command for your case, that is a tool defect, not a reason to open an editor.

## Model self-report and dispatch watchdog {#model-self-report-and-dispatch-watchdog}

A sent dispatch is not considered live by itself. As its first action after it receives the brief, the role
confirms the model that is really active:

```bash
python .harness/orchestration/coordinator.py --repo . dispatch self-report \
  --dispatch <dispatch-id> --model <actual model> \
  --worktree "$(git rev-parse --show-toplevel)"
```

A match with the `resolved_model` of the immutable brief moves the dispatch to `working`. If
`worker_attestation_required` is on, the coordinator also checks the passed Git top-level, the issue branch of a
write role, or the pinned SHA of a review role. A mismatch immediately moves the dispatch to `blocked`, marks the
batch `blocked`, and ends the command with an error. After that, the coordinator does not accept `report submit` for
this dispatch. The fix is a new dispatch with a new brief, not an edit of the sent one. Without a successful
self-report, a completion report is not accepted at all. So a substituted or wrongly configured model is visible
immediately, not after the window is spent.

For architect/developer, `worker_attestation_required` also requires that the Git worktree HEAD at the moment of the
first `self-report` literally equals the immutable `snapshot_commit` from the brief. For an allowed
`dispatch resume` of a write role, the fresh self-report checks the exact `commit_sha` of the last registered
checkpoint. The original brief and the boundary of the commit-plan evidence stay unchanged. For architect,
developer, verification, and code-review, `dispatch create` selects `snapshot_commit` in this order:

1. an explicit `--candidate-commit`;
2. the `commit_sha` of an unaccepted developer report, while the batch waits for its `developer-retry`;
3. the last accepted developer candidate, for example `developer-retry` after a code-review blocker, qa, or publish
   (a repeat on the same SHA does not create a developer dispatch);
4. otherwise `base_commit`.

`dispatch preflight` and the freshness check of the Context Package use the same rule. A retry continues the
history of this candidate and adds separate logical commits according to the immutable commit plan. The coordinator
does not run or suggest `git reset --soft`. If the worktree HEAD does not match the pinned snapshot, fix the
configuration of the new dispatch or choose a worktree at this commit, without rewriting the existing history.

For `developer-retry`, `dispatch preflight` additionally returns `retry_start`: the handoff from which the new
developer session starts, its starting files, `context_estimate` (the threshold, and the estimate before and after
compaction), and `warning`. `decision_packet` repeats the estimate and the warning as `retry_context_estimate` and
`retry_context_warning`. The handoff content, the smart-zone threshold, and the compaction rules are in the section
"Developer-retry handoff" of `playbook.md`.

Before it writes the brief, `dispatch create` runs the same check on it as `dispatch send`. A brief that send would
reject is not created: neither the brief nor its status appears in the ledger. An example is `--candidate-commit`
without a linked immutable risk assessment. The remedy names
`risk assess --batch <batch-id> --candidate-commit <sha> --changed-file <path>...`. After it, a new
`dispatch propose` and `create` are needed (first cancel the unsent brief through `dispatch cancel`). The check at
`dispatch send` stays in place.

While the role works, it sends a heartbeat, and the coordinator session polls the state. By default, a dispatch
allows up to an hour of silence for a long build or test. But the immutable brief requires a heartbeat right after
the self-report and then at least once every five minutes. This keeps a fast signal about a live worker, and a
working developer does not become stale because of one long tool call:

```bash
python .harness/orchestration/coordinator.py --repo . dispatch heartbeat --dispatch <dispatch-id>
python .harness/orchestration/coordinator.py --repo . dispatch status \
  --batch <batch-id> --stale-after 3600
```

For each dispatch, `dispatch status` shows the role, the transport, `resolved_model`, the self-report result, the
`startup` estimate (the worker state, the failure classification, the unknowns), the time of the last heartbeat,
`silent_seconds`, and the `stale` flag. This generalizes the QA lease expiry to any dispatch, not only to the
clean-room QA lane. Stale is a blocker that the coordinator escalates to a human; the coordinator does not change
the state on timeout by itself.

`dispatch heartbeat` takes an optional pair `--context-tokens <N> --context-source probe`. This is the number of
tokens that the coordinator measured in a live context probe (see "Reporting and token monitoring" below), not a
role self-report. This keeps the [token accounting rule](../../backend-orchestration.md#language-and-evidence) ("Tokens are only observable provider or
runtime telemetry"): the role itself does not supply this value. The value goes into the open `extra`
field of the dispatch status. The ledger schema does not change, and no new event is introduced in `dispatch wait`.

For each dispatch, `dispatch status` additionally returns the last `telemetry` record (`dispatch telemetry`, see
below) and `context_advisory`. This is a pure read, and missing telemetry is not an error: `telemetry` and
`context_advisory.observed` are then `null`, and `context_advisory.level` stays `"ok"`.

## Busy ledger, `report complete`, and `ledger release-lock` {#busy-ledger-report-complete-and-ledger-release-lock}

Each coordinator command takes an exclusive ledger lock (`.coordinator.lock` in the state directory). The lock
records its owner: `pid`, `host`, and `acquired_at`. On a platform with `/proc`, the record is extended with
`pid_namespace` (the `/proc/self/ns/pid` link) and `boot_id`, and also with `operation`, the coordinator command
that took the lock. Old records without these fields are read as before. The lock is held by whoever first created
this record exclusively. A process gets a refusal and does not write into a foreign lock if its still empty lock
directory was removed and taken again. While another operation holds the lock, a write command ends with the error
`ledger is locked by another operation`. Its remedy suggests repeating the command and names `ledger release-lock`,
not a manual delete.

Coordinator polling survives a busy lock:

- `dispatch wait` counts a busy lock as a skipped poll and keeps polling until its `--timeout`. The report is
  returned as soon as the lock is free. If the lock stays busy until the end of the wait, the result is the ordinary
  `{"dispatch_id": ..., "event": "timeout"}`;
- `dispatch status` with a busy lock ends with exit code 0 and answers in a structured way:
  `{"ledger_busy": true, "retry_after_seconds": ..., "lock": {...}, "remedy": ...}`. Here `lock` contains the owner
  and `held_seconds`. This is not an unavailable coordinator: repeat `dispatch status` after
  `retry_after_seconds`.

The tolerance applies only to these two polling commands, `report complete`, and the release of the QA lane in
`qa run`. No write goes without the lock. For the other commands, a busy lock remains an error. With a busy lock,
`report complete` stops at the step that could not read the state. It writes nothing, and its remedy names itself
for the repeat.

`qa run` releases the QA lane after a failure and after the report is written. If the lock is busy, the release
waits for it for up to 30 seconds and retries every 0.25 seconds. When the lock is free, `qa run` removes only the
lease and the queue record of its own dispatch. After a failure, it also returns the dispatch to `approved`, and the
same dispatch can be started again right away. If the lock is busy for all 30 seconds, the error
`QA dispatch <id> was not released` names the dispatch, the lease owner, and the time the lease expires. The
dispatch then stays `working`. After the lease expires, the coordinator runs `qa clear-stale-lease`. The command
removes the lease and the queue record and returns the dispatch to `approved` if it has no recorded report. After
that, the same dispatch is started again. The command response and the record `qa-lane/recoveries/*.json` contain
`restored_dispatch_state`: `approved` or `null`. The rollback of a run that outlived its lease does not remove the
lease of a new run of the same dispatch and does not change its state.

A read-only command shows the lock state. It does not take the lock, so it works when the ledger is busy:

```bash
python .harness/orchestration/coordinator.py --repo . ledger lock-status
```

The response is `{"locked": false}` or an object with the fields `acquired_at`, `held_seconds`, `owner`,
`operation`, `verdict` (a verdict from the table below), `stale_after_seconds`, `remaining_seconds` (how long until
the timeout release, not less than zero), and `release_available` (whether the ordinary `release-lock` would release
the lock right now). The "Lock ledger" panel in the orchestration section of the Harness console shows the same
information; the hold time and the remainder update on the live screen.

Only a command with an owner check releases a lock that stays busy:

```bash
python .harness/orchestration/coordinator.py --repo . ledger release-lock
```

The verdict depends on the owner:

| Lock owner | Verdict |
| --- | --- |
| The owner process is alive (on this host, in the same PID namespace and boot) | refusal `owner-alive`, at any lock age |
| The owner is on another host | refusal `owner-on-another-host`: run the command on that host |
| The owner is from another PID namespace or another boot, the lock is younger than `LEDGER_LOCK_STALE_SECONDS` | refusal `owner-in-other-environment`: the pid of a worker from a sandbox (`--unshare-pid`) points to a foreign process, so it cannot be checked |
| The owner is from another PID namespace or another boot, the lock is older than `LEDGER_LOCK_STALE_SECONDS` | released, `owner-unknown-stale` |
| The owner process has ended (on this host) | released, `owner-dead` |
| There is no readable owner record, the lock is younger than `LEDGER_LOCK_STALE_SECONDS` (3600 s) | refusal `owner-unknown-recent`; the remedy names how many seconds until the lock can be released |
| There is no readable owner record, the lock is older than `LEDGER_LOCK_STALE_SECONDS` | released, `owner-unknown-stale` |

A readable owner record is missing in two cases. First: the lock was taken by an old runtime, and there is no record
at all. Second: the owner died after it created `owner.json` but before it wrote it; the record is empty or
unreadable. The age of an unreadable record counts from the mtime of `owner.json`, and without a record, from the
mtime of the lock directory. While the lock is younger than the threshold, the owner may still be writing itself, so
the command refuses. An owner that has not written the created record within `LEDGER_LOCK_STALE_SECONDS` is
considered ended.

Success returns `{"released": true, "reason": ..., "lock": {...}}`, and if there is no lock,
`{"released": false, "lock": null}`. A refusal is an error with the reason, the owner, and `held_seconds`, and the
lock is not touched. The `lock` object describes the released lock:

| Field | Meaning |
| --- | --- |
| `path` | the lock directory |
| `owner` | the owner record (`pid`, `host`, `acquired_at`), or `null` if there is no readable record |
| `owner_record` | `readable`: the record was read; `unreadable`: `owner.json` exists but is empty or unreadable; `absent`: there is no record |
| `acquired_at` | `acquired_at` from the record, otherwise the mtime of `owner.json` for an unreadable record, or of the lock directory |
| `held_seconds` | how many seconds the lock has been held at the time of the check |

In the runtime store epoch (store schema 3), `ledger lock-status` keeps the fields of the file lock and their
verdicts and adds the `qa_lease` object: the owner of the QA-lane lease, the identity of its process,
`fencing_token`, `expires_at`, `stale_heartbeat`, the runtime verdict, and `release_available`. If the file lock is
not busy, `ledger release-lock` without `--force` releases an expired lease only with the verdict `owner-dead`. The
command rejects a live owner with exit code 2 and the line `REMEDY: [lease_held] stale_heartbeat=… verdict=…`.
`--force` with an approval and a reason releases the lease at any verdict through `lease_clear`, and the runtime
writes the decision to the audit.

### Parallel writes, read snapshots, and the QA-lane lease

Commands of different batches write in parallel. A command reads the store from one snapshot (`state.read` with
`snapshot`): a commit of another batch between its two reads gives neither a refusal nor half of two states. Read
commands (`dispatch status`, `batch auto-report`, `batch decision-packet`, `qa status`) do not wait for a writer.
A write to one batch is still serialized by the `revision` of the row. A decision across all batches
(`concurrency_budget` in `dispatch create`, a duplicate ticket, branch, or worktree in `batch create`) is protected
by the revision of the `generation` row from the snapshot of this decision. Of two commands that decided from one
state, one commits, and the other gets `revision_conflict` on `generation`
and retries.

The QA lane in the store is a singleton lease with a `fencing_token`. `qa run` and `integration local-qa` take it
with the `lease_acquire` operation. The runtime records the identity of the owner process from the kernel: host,
boot, PID namespace, pid, and the process start time. Each new lease increases `fencing_token`. The owner extends
the lease by heartbeat every third of `lease_ttl_seconds` (300 s by default; `--lease-seconds` overrides the term).
A release or heartbeat with a foreign owner or token gets `fencing_mismatch`. After `expires_at`, the runtime checks
the owner by identity only:

| Verdict | Meaning | Lease |
| --- | --- | --- |
| `owner-dead` | the same host, boot, and PID namespace, and no process with this pid | released without `--force` |
| `owner-alive` | the pid is taken by a process with the recorded start time | stays |
| `owner-pid-reused` | the pid is taken by a process with a different start time | stays: this does not prove death |
| `owner-in-other-environment` | another boot or PID namespace | stays |
| `owner-on-another-host` | another host | stays |
| `owner-unknown` | there is no identity (a schema 2 lease, a client outside the runtime's view) | stays |

The next `qa run`, `integration local-qa`, or `ledger release-lock` releases the lease of a dead owner. The audit
record contains the owner, the identity, the observation, the verdict, and the time. Like `qa clear-stale-lease`,
the release deletes the owner's queue record, returns its QA dispatch to `approved`, and writes `qa-lane/recoveries`.
With any other verdict, the request ends with exit code 2 with `[lease_held]` and `stale_heartbeat`. `qa status`
shows `stale_heartbeat`, and `dispatch status` shows the lane in the top-level object `qa_lane`. Neither the
automation nor `ledger release-lock` without `--force` releases a live owner. The manual override remains
`ledger release-lock --force` or `qa clear-stale-lease`. Start `harness-runtime serve` in a PID namespace that the
coordinators can see (the host or an ancestor of their sandboxes). A runtime that does not see the client does not
record its identity, and such a lease is not released automatically.

The command releases only the lock that it checked: if the owner changed during the release, it refuses and asks
for a repeat. Runs of `ledger release-lock` do not overlap, because an OS file lock
(`.coordinator.lock.release` in the state directory) serializes them, and the system releases it itself when the
process exits. A second parallel run gets the refusal `another ledger release-lock is releasing the ledger lock`
and repeats after the first. You must not delete the lock or other state files by hand.

If a stopped worker left the lock and its pid matches a live process (an old record without `pid_namespace`, the
verdict `owner-alive`), or you cannot wait for the timeout, the operator releases the lock by force:

```bash
python .harness/orchestration/coordinator.py --repo . ledger release-lock --force \
  --approved-by "<operator>" --approved-at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --reason "<why the owner will not finish the operation>"
```

Without `--approved-by`, `--approved-at`, or `--reason`, the command refuses; a `policy:...` approval is rejected,
and with `human_approval_gate: tty` it must be confirmed on the terminal. No policy, including `auto`, runs this
command. Before the release, the command writes an audit record with a checksum (`record_sha256`) to `lock-audit/`
in the state directory: who approved it and when, the reason, the verdict of the check, and the previous state of
the lock. If the lock could not be released after the record was written, a second record,
`ledger-lock-force-release-failed`, names the first. `ledger validate` checks the checksums of these records; it
does not detect a record replaced together with its checksum, or a deleted file. In the console, the same action is
the command "Release ledger lock" with a confirmation.

## Runtime autostart {#runtime-autostart}

In Claude Code, the `runtime-autostart` hook starts `harness-runtime serve` (ADR 0031), not the
developer and not the agent. The hook runs outside the agent sandbox, so serve can reach Docker.

- **Start.** Before every `.harness/orchestration/coordinator.py` command, the hook calls
  `harness-runtime ensure` for the main checkout. If no runtime answers, ensure starts its own serve
  and waits up to 40 s until it is ready; the developer sees a message with the pid and the journal.
- **Reuse.** A running serve, started by hand or by another session, is reused silently; no second
  instance starts.
- **Owners.** An own serve keeps its owners: the session (`<session_id>`) and subagents
  (`<session_id>/<agent_id>`). `Stop` and `SubagentStop` release the owner. An owner also leaves when
  the Claude Code process (`CLAUDE_PID`) ended or the owner was not renewed for an hour (TTL).
- **Stop.** An own serve stops itself when no owner is left, no connection is open and the store is
  idle: no dispatch in `dispatched` or `working`, no held QA lease, no QA queue and no unfinished
  execution. A store that cannot be read counts as busy. A manual serve never stops by itself.
- **Journal.** `<runtime directory>/<repo-id>.serve.log` (mode `0600`); the hook message names it.
- **Stale build.** The hook starts only `native/harness-runtime/target/release/harness-runtime` that
  is fresh by the dep-info `harness-runtime.d`, `Cargo.lock` and `Cargo.toml`. It never starts a
  stale build: it only attaches to a running serve and otherwise warns that the build is stale.
  Rebuild with `cargo build --release --manifest-path native/harness-runtime/Cargo.toml`.
- **Environment.** Serve gets the environment of Claude Code without the variables the application
  adds only for hooks (`CLAUDECODE`, `CLAUDE_PID`, `CLAUDE_PROJECT_DIR` and the others of ADR 0031).
- **Failure.** A serve refusal (exit code 2), a timeout, a missing binary or the sandbox give the
  warning `[runtime-autostart-failed]` with the cause and the journal. The hook never blocks.
- **Foreign checkout.** The hook starts only the binary of the main checkout of the session project
  (`CLAUDE_PROJECT_DIR`). The coordinator of another repository, a path to it that a command only
  mentions, or an empty `CLAUDE_PROJECT_DIR` give the warning `[runtime-autostart-failed]
  coordinator репозитория … не относится к основному checkout проекта сессии` (the coordinator of
  the repository does not belong to the main checkout of the session project); no binary starts.
  Start the serve of that repository by hand.
- **Build trust.** The hook runs `native/harness-runtime/target/release/harness-runtime` of the main
  checkout outside the agent sandbox. The dep-info check rejects a stale build but not a replaced
  file. Do not let the agent write to `target/release` of the main checkout (ADR 0031, section 5).

Codex and Windows get no autostart: start `harness-runtime serve --repo <repo>` by hand outside the
agent sandbox. The remedy of the `[runtime_unavailable]` error says the same. The hook reaches a
project with `harness update`, which a person runs.

## Lifecycle writes in the runtime store epoch {#lifecycle-writes-in-the-runtime-store-epoch}

After `harness-runtime migrate` (`ledger.json` version 4), the Rust runtime accepts every batch and dispatch
mutation, not a file write and not the `.coordinator.lock` lock (ADR 0020, ADR 0021, section 4). Python does not
open `runtime.db` and has no fallback write path: without a running runtime, a write command refuses with exit
code 2 and `[runtime_unavailable]`, and creates and changes nothing.

- **Write unit.** The `_ledger_lock` block of a command became its write unit. The ledger primitives
  (`write_immutable`, `write_artifact`, `replace`, `delete`) only accumulate mutations, and the command reads its
  own writes from its own view. On a clean exit from the block, the coordinator sends one `state.write` operation
  per batch; an exception inside the block sends nothing except the records that the failure saves itself (the
  attempt record on an access refusal of `qa run` and the `needs_attention` flag on a refusal of `dispatch create`:
  before the exception, they call `persist_writes`, as the file ledger held them). Each outer `_ledger_lock` block
  and each `read_state` reads a fresh store snapshot, so the `dispatch wait` poll sees a new `reported` and new
  heartbeats; reads of a command before the block see the snapshot of its start. A nested block joins the outer
  unit. If the mutations touch two batches, they go in two transactions: each is atomic, but not both together.
- **CAS by revision.** `state.read` returns the `revision` of each row (`batch`, `dispatch`, `dispatch-status`,
  `qa-lane`, the QA queue, the `record` row). The first touch of an existing row carries the revision that the
  command read; the request envelope carries the revision of the batch row (0 at creation). A committed transaction
  increases the revision of each affected row by exactly 1. A stale revision gives `revision_conflict`, and nothing
  is written.
- **Transaction.** `BEGIN IMMEDIATE`, then the rows in the order `batch` → `qa_lane` → `generation` (the batch rows,
  the QA-lane rows, then the audit and the `operations` row); one audit record per mutation in request order.
  Immutable records (plan, brief, report, checkpoint, evidence) are not replaced and not deleted
  (`invariant_violation`). SQLite checks the schema invariants: CHECK for the batch and CHECK for the execution
  state (`DispatchState` is terminal while the execution is `unknown`, `launching`, or `running`).
- **Idempotency.** The `operations` row (`intent`, `committed`, or `failed`) is written in the same transaction. A
  repeat with the same `operation_id` and the same request digest returns the stored result; the same
  `operation_id` with a different request gives `idempotency_conflict`. `operation_id` equals
  `sha256(batch_id, expected_revision, operation, payload_digest)` (ADR 0021, section 4). The payload contains
  times, so a command restarted after a SIGKILL of the coordinator builds a new key, and the CAS by `revision`
  answers `revision_conflict`, not the stored result: the command must be repeated.

| Code | When | Retry | REMEDY (first line) |
|---|---|---|---|
| `revision_conflict` | another command changed the row after the read | yes | `[revision_conflict]` repeat the command: it reads the store again and applies the policy to the current state |
| `store_busy` | the store is busy longer than 5 seconds | yes | `[store_busy]` repeat the command |
| `runtime_unavailable` | the runtime does not respond | yes | `[runtime_unavailable]` start `harness-runtime serve --repo <repo>` |
| `idempotency_conflict` | `operation_id` is already taken by another request | no | `[idempotency_conflict]` repeat the command: it derives a new id from the current revision |
| `invariant_violation` | the change breaks a store invariant or the audit chain does not converge | no | `[invariant_violation]` stop the writers and run `ledger validate --full` |

Each refusal ends the command with exit code 2 and starts the first `REMEDY:` line with the code in brackets.
Commands that waited for a busy ledger treat `store_busy` as a busy ledger: `dispatch status` answers
`ledger_busy`, and the `dispatch wait` poll skips the busy tick and repeats it. In the store epoch, the
`_ledger_lock` block does not wait for a lock: `store_busy` comes from `state.read` or from sending the write, that
is, already inside the block. So the release of the QA lane after `qa run` does not wait 30 seconds, as with a file
lock, but passes `store_busy` through at once; the lease and the queue record stay until the lease expires, and
`qa clear-stale-lease` releases them.

### The audit chain and `ledger validate --full`

The audit chain is stored in the `audit` table: each record is linked by hash to the previous one, and the first
record is `legacy-import` with the anchor of the import manifest. The `audit_checkpoint` table remembers the last
checked record. An ordinary command (read and write) checks only the records after the checkpoint; a write moves
the checkpoint in its own transaction. A missing or damaged checkpoint means a full check, and the next write or
`ledger validate` rebuilds it without an error. A write builds the missing checkpoint before the `BEGIN IMMEDIATE`
transaction (the full check runs in a read snapshot that does not block writers), so inside the transaction only the
tail of the chain is checked (ADR 0020, section 3). An unreadable store gives `store_busy` (the lock is busy) or
`internal` during the check, not `invariant_violation`: send the operator to the snapshot recovery only when the
chain does not converge.

`coordinator.py ledger validate --full` does not use the checkpoint. It recomputes the chain from genesis (the `seq`
sequence, the hashes of the records and links, the closed vocabulary of actions), checks record 1 against
`store_meta` and `AUTHORITY.json`, recomputes the import manifest and the hashes of the legacy audit and the
generations, runs `PRAGMA integrity_check` and `foreign_key_check`, and checks each row written by a command against
the last audit record of its path. This finds a deleted, inserted, or reordered record and a row changed outside the
runtime. Rows that were imported and not rewritten after the import are checked only by the `migrate` parity. A
failure writes nothing; a success rebuilds the checkpoint. In the file ledger epoch, `--full` is accepted and equals
the ordinary check (there is no cache).

In the runtime store epoch, `ledger migrate`, `ledger clean`, and `ledger reset` refuse with exit code 2: the
history is already imported, the store holds no orphaned records, and the command cannot reset it.
`ledger status` shows the epoch and the number of audit records.

## Reporting and token monitoring: `dispatch telemetry` {#reporting-and-token-monitoring-dispatch-telemetry}

```bash
python .harness/orchestration/coordinator.py --repo . dispatch telemetry --file telemetry.json
```

The command writes source-observed metrics (of a worker or coordinator session) to the audit trail of the batch:
`input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `max_context_tokens`, `tool_calls`,
`tool_output_bytes`, `poll_turns`, `restart_reason`, `recorded_at`. A missing provider field stays `null`, not an
estimated zero. The command is **intentionally data-only**: it only writes a telemetry record and cannot change the
role state, the scheduling, the approvals, or the model routing.

In the **return value** (not in the stored ledger record), the command adds
`context_advisory: {"level": "ok"|"warn"|"over", "limit", "warn_at", "observed"}`. This is an advisory estimate of
`max_context_tokens` against the threshold `adaptive_continuation_policy.context_limit` in the project
`.harness/orchestration.json`. `adaptive_continuation_policy.context_warn_ratio` sets the share of the threshold
for the warning (a share of `context_limit`, `0.8` by default;
`warn_at = round(context_limit * context_warn_ratio)`). `level` is `"ok"` while `observed` (or its absence) is
below `warn_at`; `"warn"` in the range `[warn_at, context_limit)`; `"over"` at `context_limit` and above. This is a
pure estimate: it does not trigger a checkpoint automatically. The decision about a checkpoint stays with the
coordinator, as for any other signal, except the auto-resume on 429 (see ["Checkpoint and a new worker session"](#checkpoint-and-a-new-worker-session) below). The
baseline from `playbook.md` ("Baseline metrics") stays, in the same way, a guideline and not a hidden limit.

## Checkpoint and a new worker session {#checkpoint-and-a-new-worker-session}

A write role (developer, database-migrations, messaging-integration, conflict-resolver) may stretch one dispatch
over several worker sessions if the whole TDD cycle in one session inflates its context. A read-only role
(architect, qa, code-review) may not: a checkpoint attempt for it is rejected at once.

Instead of a completion report, the current worker session records a non-final checkpoint: a separate, hashed
ledger record that cannot be mistaken for a report:

```bash
python .harness/orchestration/coordinator.py --repo . dispatch checkpoint \
  --file checkpoint.json
```

`checkpoint.json` must contain exactly: `dispatch_id`, `commit_sha`, `changed_files`,
`remaining_definition_of_done` (a subset of the DoD of the approved dispatch), `passing_checks` (in the
`checks_run` format of the completion report, with commands from the approved `verification_commands`), `risks`,
`blockers`, and `context_package_id`, a reference to the last Context Package registered for the batch, or the
literal `not applicable — no context package registered` if the batch has none yet. No foreign fields: no raw chat
history and no logs of earlier failed attempts. `checkpoint` requires an already confirmed self-report. The command
moves the dispatch status to `checkpointed` and does not touch the outcome enum (`completed`/`blocked`/`failed`).
This enum stays only with the completion report.

A new worker session for the same dispatch ID starts with the `dispatch resume` command. The authorization depends
on why the previous session ended:

```bash
# the runtime adapter reported a rate-limit termination: the authorization is automatic
python .harness/orchestration/coordinator.py --repo . dispatch resume --dispatch <dispatch-id> \
  --termination-reason rate_limit

# a planned trigger (context limit / N TDD cycles / a large failure log / a finished vertical
# slice): an explicit coordinator decision is required
python .harness/orchestration/coordinator.py --repo . dispatch resume --dispatch <dispatch-id> \
  --trigger context-limit --measured-value 162000 --file continuation-facts.json \
  --approved-by "project coordinator" --approved-at <approval-time-utc>
```

A `--termination-reason` recognized as a rate limit (`rate_limit`/`rate-limit`/`429`) authorizes the new session
automatically. No new human or coordinator decision is required. Any other reason, including a missing or
unrecognized one, is treated as a planned trigger. This is a safe default toward approval, not away from it:

- `--trigger` is required and must be one of `context-limit`, `tdd-cycles`, `failure-log`, `vertical-slice`.
- for `context-limit`/`tdd-cycles`/`failure-log`, `--measured-value` must be not less than its
  `adaptive_continuation_policy` threshold (`context_limit`/`tdd_cycle_count`/`failure_log_bytes`) from
  `.harness/orchestration.json`. Without an explicit configuration, the documented default values are used
  (150000 / 3 / 20000), not values hardcoded separately in each place.
- `--file` must contain JSON with `dispatch_id`, `remaining_definition_of_done`, `risks`, and `dependencies` that
  literally match the last checkpoint (the first two fields) and the dispatch (`dependencies`). `blockers` is not
  part of the comparison: their wording may change between sessions without a real drift of scope/DoD/risks/
  dependencies. A mismatch is a signal that they really changed. Then the coordinator must close the current
  dispatch and open a new one through the ordinary approval, not resume this one.
- the authorization is recorded in the same `coordinator_decisions` as accept/retry/block/fail/abandon/cancel: no
  new record type is introduced.

`resume` accepts only a `checkpointed` dispatch, returns it to `dispatched`, and discards the previous model
self-report. This means that the new session must go through `dispatch self-report` and `dispatch heartbeat` again,
exactly as at the first contact, before the next checkpoint or completion report is accepted. The circle closes with
the same dispatch ID: checkpoint → `dispatch resume` → a new self-report/heartbeat → finally one completion report.

Updating the installed runtime does not change the runtime snapshot of the active batch. If the old snapshot
contains a continuation error, keep the checkpoint and the Git history, then choose the standard recovery on the
fixed runtime with a new approval. The new batch must pin the original integration base, the full DoD/commit plan,
and the saved writer HEAD. Review and QA check the whole final candidate. The recorded briefs, reports, and runtime
snapshots of the old batch stay as audit evidence.
