# Upgrade from 1.x to 2.0

This page describes how to move a project from Agent Harness Next 1.x to 2.0.0 and how to go back
to 1.x. The migration and rollback contract is set by ADR 0020, "Moving operational state from the
file ledger to the Rust SQLite WAL store", sections 1, 5, and 6.

## What changes

- **The Rust runtime is required for orchestration.** Operational state lives in the runtime store
  `state/runtime.db`, and only the `harness-runtime serve` process writes to it. An unavailable
  runtime gives `runtime_unavailable` and exit code 2.
- **`ledger.json` gets `version: 4`.** `harness-runtime migrate` writes it at the cutover commit
  point. After that point, a 1.x installation refuses with exit code 2.
- **Coordinator 2.0.0 does not run on the file ledger.** On `ledger.json` versions 1–3 it exits with
  code 2, and its remedy names `harness-runtime migrate`.
- **A human runs migrate and rollback.** Both commands require human approval. The agent does not
  run them.

A project without backend orchestration (no `.harness/orchestration/state/`) has nothing to
migrate: `harness update` is enough.

## Before the upgrade

1. Build `harness-runtime` (Rust 1.89+):
   `cargo build --release --manifest-path native/harness-runtime/Cargo.toml`.
2. Check the ledger version in `.harness/orchestration/state/ledger.json`. `migrate` imports only
   version 3. On versions 1 and 2 it refuses with exit code 2 and `protocol_unsupported`: first run
   `coordinator.py ledger migrate` of the 1.x installation, then move on to 2.0.
3. Finish the orchestration work. `migrate` refuses with exit code 2 and changes nothing when:
    - the QA lane holds a lease or a queue;
    - a dispatch is `dispatched` or `working`. Wait for the reports, or move stuck dispatches to
      `abandoned`;
    - the ledger fails `coordinator.py ledger validate`;
    - the state directory still holds the store of an earlier rollback (`AUTHORITY.json` names
      `file-ledger`). `migrate` does not overwrite it: archive or remove `runtime.db` and
      `AUTHORITY.json` yourself and repeat the command.
4. Back up the `.harness/orchestration/state/` directory. `migrate` takes its own snapshot in
   `.harness/orchestration/state-snapshots/<utc>/`, but an emergency rollback needs a copy outside
   the repository.

## Upgrade

1. Update the project installation:

    ```bash
    harness update <repo>
    ```

    `harness diff <repo>` shows the changes to the managed files beforehand, and `harness update`
    keeps local edits.

2. Check the installation:

    ```bash
    harness health <repo>
    ```

    Fix every `fail` before the migration. Health often prints the fix command itself.

## Migrate the state

A human runs this command. The approval is written to the store audit chain and to
`AUTHORITY.json`.

```bash
harness-runtime migrate --repo <repo> \
  --approved-by <human> \
  --approved-at <RFC 3339 time> \
  --reason <reason>
```

An empty approval field, or a time that is not RFC 3339 or is in the future, gives exit code 2 and
`malformed_request`. An approver with the `policy:` prefix gives exit code 2 and `policy_denied`.
The command prints one JSON line, and each refusal prints a `REMEDY:` line with the operator action.

| Code | Meaning | What to do |
| --- | --- | --- |
| 0 | Done. A repeat after the commit point answers `already_cut_over: true` and changes nothing | Go on to the check |
| 2 | Refused on approval or a precondition; the state is unchanged | Fix the cause from `REMEDY:` and repeat |
| 3 | Interrupted after the start; the partial store is removed and the file ledger keeps authority | Repeat `migrate` or go back to 1.x |
| 4 | Invariant violation: a legacy write during the import or a parity mismatch. The file ledger keeps authority | Investigate the cause from `REMEDY:` by hand, then repeat `migrate` or go back to 1.x |

After exit code 0:

```bash
harness health <repo>
```

## Start, stop, and restart the runtime

In Claude Code, the `runtime-autostart` hook starts `serve` before a coordinator command and stops
it when the runtime is no longer needed. See [Runtime autostart](orchestration/operations.md#runtime-autostart).
Codex and Windows have no autostart: start `serve` by hand outside the agent sandbox.

```bash
harness-runtime serve --repo <repo>
harness-runtime stop --repo <repo>
harness-runtime restart --repo <repo>
```

`stop` stops the runtime the same way as SIGTERM and waits up to 30 s for the instance lock to be
released. `restart` runs `stop` and then `serve` in the same process.

| Code | `stop` |
| --- | --- |
| 0 | `stopped` or `not_running`; a repeat is safe |
| 1 | The runtime did not answer or did not release the lock within 30 s |
| 2 | Refused; nothing is stopped |

A runtime version without the `shutdown` operation is stopped once with SIGTERM (Ctrl+Break on
Windows); after that, `stop` and `restart` work.

The full table of exit codes and answers is in the "Stop and restart" section of
[Rust runtime](../architecture/runtime.md).

## Roll back to 1.x

The rollback returns the state directory to the 1.x installation. A human runs it as well.

1. Stop the runtime: `harness-runtime stop --repo <repo>`. A running `serve` holds the instance
   lock, and the rollback refuses with exit code 2 (`lease_held`). While the rollback runs, do not
   run coordinator commands: in Claude Code, autostart would start `serve` again.
2. Wait for an empty QA lane and for the executions to finish. The rollback refuses with exit code 2
   when the QA lane holds a lease or a queue, or when a dispatch execution is `launching`,
   `running`, `stopping`, or `unknown`. A dispatch in `dispatched` or `working` with a stopped
   execution is exported as is.
3. Run the rollback:

    ```bash
    harness-runtime rollback --to-legacy --repo <repo> \
      --approved-by <human> \
      --approved-at <RFC 3339 time> \
      --reason <reason>
    ```

    The exit codes are the same as for `migrate`. A repeat after completion answers
    `already_rolled_back: true` with exit code 0; a repeat after a failure continues from the last
    completed step.

4. Return the project to the latest 1.x release, `v1.5.1`. In the harness checkout, switch to the
   `v1.5.1` tag (or unpack that release's archive from GitHub Releases) and run
   `python3 harness/bin/harness.py update <repo>` from it.
5. Check the state with `coordinator.py ledger validate` of the 1.x installation. A passing check
   completes the rollback. A failing check leaves only the emergency rollback from a snapshot
   (below).

What remains after the rollback:

- `ledger.json` has `version: 3` again, and `AUTHORITY.json` has `authority: file-ledger`.
- The archive `state/runtime-export/<store_id>.tar` keeps the audit chain, the operations, and the
  QA lane state. Its sha256 is written to the `runtime-rollback` audit record and to
  `AUTHORITY.json`.
- `runtime.db` stays read-only for investigation; its schema version is not lowered.

## Emergency rollback from a snapshot

If `rollback --to-legacy` is not available, or the 1.x `ledger validate` does not accept its
result, the state directory is restored from the backup or from the `state-snapshots/<utc>/`
snapshot that `migrate` took. No command does this: it is done by hand and only with a separate
approval of the project owner, because it loses everything the runtime wrote after the cutover:

- batches, dispatches, reports, decisions, and approvals created after the migration;
- store audit records, including the cutover record;
- the state of the QA lane and of the executions.

Steps:

1. Get the owner's approval and record it, with the reason, where the project keeps its decisions.
2. Stop the runtime: `harness-runtime stop --repo <repo>`.
3. Move the current `.harness/orchestration/state/` to an archive outside the repository. Do not
   delete `runtime.db` in it: it remains the only copy of the records written after the cutover.
4. Copy the contents of the snapshot or the backup to `.harness/orchestration/state/`.
5. Return the project to `v1.5.1` and run `coordinator.py ledger validate`, as in steps 4 and 5 of
   the regular rollback.

## Next

- [Recovery](orchestration/recovery.md) — `recovery` commands for a stopped batch.
- [Troubleshooting](troubleshooting.md) — CLI, hook, and runtime messages.
- [Platforms](../project/platforms.md) — what CI checks on each platform.
