# Rust runtime

`harness-runtime serve` is one process per state directory. It listens on a Unix domain socket on Linux
and macOS or on a named pipe on Windows, checks the peer identity, and runs typed operations.
The runtime does not decide policy. It accepts an already approved brief, compares the digests, and
executes only the saved plan. Python does not start a worker or a QA container directly.

## Process and IPC

A protocol frame is a length and JSON. The `hello` handshake negotiates the protocol version and
confirms the client identity. A version mismatch is the error `protocol_unsupported`. A foreign uid
or token is `unauthorized_peer`.

| Envelope field | Purpose |
| --- | --- |
| `operation_id` | A deterministic intent key. A retry returns the saved result, and the same id with a different payload is `idempotency_conflict`. |
| `expected_revision` | A CAS on the state row. A conflict is a typed error, not a silent overwrite. |
| `request_deadline` | Limits the wait for a response. The client retries with the same `operation_id`. |
| `fencing_token` | Protects the singleton QA lane from two owners. |

Execution goes in three steps: `intent` → start → `committed`. Before a retry the runtime runs
reconcile and does not start a second process if the object already exists.

```bash
python3 .harness/orchestration/coordinator.py --repo . runtime status
```

## Stop and restart

`harness-runtime stop --repo <repo>` stops the runtime of a repository the same way as SIGTERM: it
sends the `shutdown` operation over the runtime IPC with the runtime token and waits until the
runtime lets the instance lock go (up to 30 s). The runtime removes its socket and token file
itself. Executions outlive the stop, as with SIGTERM. The command prints one JSON line.

`harness-runtime restart --repo <repo>` runs `stop`, then `serve` in the same process: it prints the
`serve` readiness line and exits with its codes. The client connections of the old runtime close
with it; a client reads the new token again.

| Code | `stop` | `restart` |
| --- | --- | --- |
| 0 | `{"status":"stopped","pid":<pid>}` or `{"status":"not_running"}`; a repeat is safe | the runtime stopped normally |
| 1 | the runtime holds the lock but did not answer in 30 s (`[runtime_unavailable]`), or accepted `shutdown` but did not let the lock go in 30 s (`[deadline_exceeded]`) | `stop` failed, or the running `serve` ended with an error |
| 2 | refused, nothing stopped: wrong arguments, the directory is no repository (`[not_found]`), the runtime refused `hello` (`[unauthorized_peer]`, `[protocol_unsupported]`) or does not know `shutdown` (`[unknown_operation]`) | `stop` refused, or `serve` refused to start |

The command does not stop a runtime release without `shutdown`: stop it once with SIGTERM (Ctrl+Break
on Windows); `stop` and `restart` work after that. On Windows the contract is the same; the client
connects to the runtime named pipe.

## Store

Operational state is SQLite WAL with short transactions and no external calls inside a transaction.
The store is versioned: an incompatible schema version is rejected without a write.

- **Authority.** `ledger.json` version 4 and `state/AUTHORITY.json` name the store as the only
  writer of operational state.
- **Audit.** Each mutation leaves a record in the hash chain. A checkpoint speeds up the regular
  check, and `validate --full` recomputes the whole chain.
- **Leases.** A lease holds the owner, the `fencing_token`, and `expires_at`. An expired term does not
  release the lease by itself. The runtime first checks that the owner is alive, and only a proven
  death or the owner's own command with a matching token releases the lease.
- **Idempotency.** The operations table stores the `operation_id`, the request digest, and the result,
  so a retry after a broken transport returns the same response.

```bash
python3 .harness/orchestration/coordinator.py --repo . ledger validate --full
python3 .harness/orchestration/coordinator.py --repo . ledger lock-status
cat .harness/orchestration/state/AUTHORITY.json
```

## Supervisor and OCI

The process identity is the `boot_id`, the PID namespace inode, the pid, and the start time. A PID alone
proves nothing: an object from another namespace or another boot does not count as a live worker.

- **Linux.** Accounting by process group. Where systemd is available, it uses a transient scope for
  cgroup v2. The stop is SIGTERM to the group and, after a grace period, SIGKILL.
- **Windows.** A named Job Object without `KILL_ON_JOB_CLOSE`, so that the execution survives a
  runtime restart.
- **Containers.** An OCI image, dispatch labels, and a ban on mounting the engine and runtime
  sockets. Egress goes through an allowlist proxy. The harness does not build or publish images.
- **Recovery.** Reconcile after SIGKILL adopts the container execution by its labels, proves that
  the process is absent, or leaves the state `unknown`. The lease is released after the stop and after
  the exit evidence is written.

The execution states are `launching → running → stopping → exited | lost | unknown`. Only `exited`
and `lost` are terminal. `unknown` stays observable and can move to `running`, `exited`, or `lost` at
the next observation.

## Reconcile and recovery

Reconcile compares the saved intent with the actual host state. If the object already exists, the
runtime does not start a second process. If the object is proven absent, the execution gets `lost` and
becomes terminal. The execution state is an observation of Rust, and Python chooses the dispatch state
from this observation. The runtime never writes the batch lifecycle directly.

## Verification

- **ChangeImpact** builds an `ImpactSet` from the Repo Map graph. An unknown impact widens the
  check and does not narrow it.
- **VerificationPlan** is pinned by a digest in the approval. The developer and the review get focused
  checks, and QA gets a full clean-room run on the final SHA.
- **Failed-only** reruns the exact nodeids. An empty selection is `not_run`, not a success.
- **Release Gate** confirms the `{candidate_sha, target_sha}` pair and compares the tree after the merge.

## Failure domains

An error is typed, so that a retry does not spend the role budget on infrastructure.

| Domain | Example | What the harness does |
| --- | --- | --- |
| `environment_preparation` | A dependency is missing, or the image is not built | A retry after the environment is prepared. |
| `infrastructure` | EPERM, SELinux, an unavailable engine | A retry on the same SHA, separate from the code. |
| `policy` | An approval or a hook is violated | A refusal with a remedy, without auto-approval. |
| `code_test` | A test or mypy fails | A return to the developer with evidence. |
| `timeout` | The deadline expired | A stop with a grace period and partial evidence. |

## Security

| Boundary | Rule |
| --- | --- |
| Runtime socket | Only the peer uid/SID and a capability token; directory `0700`, socket `0600`, token `0600`. |
| Engine socket | Never mounted into a worker or a QA container. |
| Approval | The immutable brief binds the plan, the image, the policy digest, and the verification digest. |
| Hooks | A profile does not disable the critical guards; `strict` does not block recovery. |
| Secrets | They do not reach the command line, the logs, the audit, or the reports. |

## Decisions

| ADR | Topic |
| --- | --- |
| 0019 | A single Rust runtime and incremental verification |
| 0020 | Moving operational state to the runtime store |
| 0021 | Authority, IPC, and idempotence |
| 0022 | The supervisor of processes and OCI containers |
| 0023 | Incremental checks |
| 0025 | The built-in container executor |
| 0026 | The consolidation of Harness Next and the Release Gate |

## Next

- [Architecture overview](overview.md)
- [Quick start](../getting-started/index.md)
- [Reference](../reference/index.md)
