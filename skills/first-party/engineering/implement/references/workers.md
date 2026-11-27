# Waiting for and observing workers

Read this after `dispatch send`, when a command reports a busy ledger or lease, or when a
worker launches externally.

## Wait, ledger and runtime

Run `dispatch wait` between send and report. `stale`, model/worktree mismatch, changed harness
snapshot, and a failed deterministic gate are blockers for the coordinator, not prompts for broad
LLM recovery. Silence or a timeout does not prove that a worker stopped.

Judge whether a worker is alive only from `dispatch status --dispatch <id>`: `startup.worker_state`,
`execution.state` for a supervised worker, `heartbeat_at` and `stale`. Never use `ps`, `pgrep` or
`kill -0` from the coordinator session as evidence. The Claude Code sandbox runs each command in its
own PID namespace, so `ps -g <pgid>` is empty even for a live worker whose heartbeat still arrives. `batch resume-stop`
refuses a worker whose `startup` state is `live` or `unknown`: stop it through its runtime and
repeat the command with `--runtime-stopped`. In-process and external transports preserve the same
brief and evidence contract.

A busy ledger (`ledger is locked by another operation`, or `ledger_busy` from `dispatch status`) is
transient: repeat `dispatch wait` or `dispatch status`. When a relayed `report submit` result
carries `completion`, the report is already recorded: never ask the worker to submit it again. Run
its `command` (`report complete --dispatch <dispatch-id>`) yourself and repeat it until no step
fails; it is idempotent. When the failed step needs a human, follow its remedy instead. Never remove
the ledger lock or any state file by hand; a lock that stays held goes to
`coordinator.py --repo . ledger release-lock`, which refuses a lock whose owner process is alive.
`ledger lock-status` shows the holder and the time left until a timeout release without taking the
lock. For the lock of a stopped sandboxed worker, show the operator a copyable
`ledger release-lock --force --approved-by <operator> --approved-at <time> --reason <why>`; it is
their action, never yours, under every `approval_policy`.

In the runtime-store epoch, coordinators of different batches write in parallel and read from
snapshots; a `revision_conflict` on `generation` means another command decided over every batch
first: repeat the command. The QA lane is a lease with a fencing token and a heartbeat
(`lease_ttl_seconds`). An expired lease of a dead owner (`owner-dead`) needs no `--force`: the next
`qa run` or a plain `ledger release-lock` reaps it. `[lease_held]` with `stale_heartbeat=true`
means the owner may live (`owner-alive`, `owner-pid-reused`, `owner-in-other-environment`,
`owner-unknown`): it is never released automatically, and only the operator's
`ledger release-lock --force` or `qa clear-stale-lease` clears it. `harness-runtime serve` must run
in a PID namespace that sees the coordinators.

Never start `harness-runtime serve` from your own Bash: in Claude Code the `runtime-autostart` hook
starts it before the first coordinator command and releases it at the end of the turn (ADR 0031);
in Codex and on Windows the developer starts it. On a `[runtime-autostart-failed]` warning or a
`[runtime_unavailable]` refusal, stop the route and relay the cause, the remedy and the journal path
(`<repo-id>.serve.log`) to the developer.

## External launch and observation

Use the shipped example explicitly with `--adapter .harness/orchestration/adapters/claude_code.py`;
`claude` and `codex` are runtime executables, not adapters. Read the playbook's "Observable external
workers" for its visible-console requirement, explicit background choice, native access probe and
per-invocation sandbox mode. A parent-side probe does not prove the worker tool's sandbox access.
Run the native worker probe before feature work; a permanent EROFS/EPERM needs environment repair.

Use `dispatch wait` for lifecycle signals. The console/`dispatch observe` reads existing events
locally: no extra model calls, agent progress prompts or logs in model context for observation.
For a supervised worker, `dispatch logs --dispatch <id> --follow` prints its run-log events as
JSON lines until the execution ends, without holding the ledger lock.
An in-process worker has no event stream (`stream_reason` says so); follow its self-report,
heartbeat and the `checkpoints` that `observe` lists.
A proven early exit uses auto-report → auto-decide → human `resume-stop --restart`; the one
confirmation covers only an unchanged successor and never resets the infrastructure budget.
A ready but unsent report uses the playbook's "Delivering a worker report after a tool refusal",
not another developer run. Retain the original file/check results and relay provenance.
