# CLI and configuration

Every command has the form `harness <command> <repo> [flags]`, where `<repo>` is the path to the target project, not
necessarily the current directory. Harness itself does not become a dependency of the project: it works on the
repository at that path and copies a verifiable snapshot into it.

## Commands

| Command | What it does | Writes to disk |
| --- | --- | --- |
| `init` | First installation into a project that has no harness | yes |
| `adopt` | Installation over a project that already has its own skills with the same names | yes |
| `diff` | Compares the project with the locked snapshot | no |
| `update` | Pulls in a new version of the capability | yes |
| `registry` | Rebuilds the project skill registry | yes |
| `lock-project-skills` | Fixes the hashes of the skills that the project itself owns | yes |
| `memory build/search/rebuild/sync/eval` | Local memory index and pointers to allowed sources | `build`, `rebuild`, `sync` — yes; `search`, `eval` — no |
| `parsers status/install` | Project graph parsers: bundle state and language installation | `install` — yes; `status` — no |
| `health` | Diagnostics of the installation and the environment | only with `--fix` |
| `ticket-status` | Moves a spec's ticket to a task-board column: replaces its `status::*` label on GitHub, GitLab or in the local tracker when the transition is allowed | only for the local `.scratch/` tracker |
| `list` | List of installed skills | no |
| `cleanup` | Plan and removal of disposable `.harness` data | only with `--apply` |
| `worktree-remove` | Removes a managed worktree and keeps the branch | yes |
| `uninstall` | Plan and full removal of harness from the project | only with `--apply` |
| `console` | Interactive console: TUI; `--web` starts a server | through the selected commands |
| `console-server` | Starts the console server without the interactive shell | no |

## Which command to choose

| | `init` | `adopt` |
| --- | --- | --- |
| When | The repository has no harness at all | The project already has its own skills under the names of the selected capability |
| Requirement | Fails if the snapshot is already installed | Does not require an empty project: keeps project skills outside the capability |
| Conflict with skill directories | Fails without a bypass flag | `--replace-conflicts` replaces only the conflicting names |

| | `diff` | `update` |
| --- | --- | --- |
| Writes to disk | no, report only | yes |
| Exit code | `0` clean, `1` there is a divergence | `0` on success, otherwise an error |
| Local edits | shows them as a divergence and does not touch them | refuses without a flag; `--force-managed-files` overwrites the snapshot, `--force` — the snapshot and seed files |

The capability defines the content of the snapshot. The builds are mutually exclusive: `project-foundation`,
`mattpocock-suite`, `engineering-suite`, `backend-orchestration`.

## The `.harness/project.json` configuration

The contract is strict: an unknown field is an error, not a warning. Each field is read by its own
consumer.

| Field | Purpose |
| --- | --- |
| `$schema` | Link to the project configuration schema |
| `language` | Language of reports, commits, and published texts |
| `base_branch` | Release branch from which integration branches are created |
| `branch_pattern` | Regular expression for the issue branch name |
| `qa_gate_commands` | Commands of the full local quality run |
| `shell` | Shell for `qa_gate_commands`: `bash` or `powershell` |
| `tracker` | Project tracker: `type` (`github`, `gitlab`, `local`), `host`, `project` |
| `ci_required_checks` | Names of CI checks whose evidence is accepted instead of local QA |
| `test_paths` | Project test directories |
| `test_runner` | Command that runs a single test |
| `hook_policy` | Hooks policy: `profile` (`minimal`, `standard`, `strict`) and `escalations` |
| `story_points` | Estimation scale and thresholds for routing to `pipeline::fast` / `pipeline::full` |
| `memory` | Enables the local project memory |
| `memory_policy` | Allowed sources, redact rules, threshold, and memory budget |

Inside `tracker`, only `type`, `host`, and `project` are allowed. Certificates, proxies, and credentials
are not written here: they stay in the personal configuration of the tracker CLI. Inside `hook_policy`, escalations
only raise the profile for paths and roles; the validator rejects a downgrade.

## CI evidence

The `ci_required_checks` field is a list of unique non-empty names of CI checks whose evidence
is accepted from the tracker.

```bash
python3 .harness/orchestration/coordinator.py --repo . integration collect-ci \
  --pull-request 42 --record <record-id>
```

The command collects CI evidence for the merged result of the pull request and records only
completed evidence: passed or failed. If the required set is incomplete, the command
writes nothing and reports that a local run is needed: `local_qa_required: true`. The full
local run then stays mandatory — half of the set cannot be accepted.

The next step for an integration record is named by:

```bash
python3 .harness/orchestration/coordinator.py --repo . integration next --ticket 42 --branch feature/issue-42-csv
```

## health

`harness health <repo>` without flags changes nothing. Each check is marked `ok`, `warn`, `fail`, or
`skipped`; on `fail` the command prints the reason and the fix command.

| Flag | What it does |
| --- | --- |
| no flags | Files, directories, environment, and project graph |
| `--fix` | Creates missing `.harness` directories and rebuilds a stale skill registry; does not touch worktrees |
| `--online` | Adds tracker checks: CLI authorization, remote availability, permissions, and labels |
| `--json` | Machine-readable report for scripts and dashboards |

The "Orchestration" group appears only when `backend-orchestration` is installed: it shows
the authority (`runtime-store`) and the schema version, unfinished batches, dispatches without activity, and
unaccounted worktrees.

## Project memory

`harness memory` works offline and makes no network calls.

```bash
python3 harness/bin/harness.py memory build /path/to/repository
python3 harness/bin/harness.py memory search /path/to/repository "правила ретраев"
python3 harness/bin/harness.py memory rebuild /path/to/repository
```

Search returns pointers — the title, status, path, and hash of the source — not the document text:
open the source only when needed. The index is derived: deleting it loses nothing, and
`rebuild` restores it from scratch. Without an explicit allowlist in `memory_policy`, nothing
is indexed.

## Repo Map

`parsers status` shows the state of the parser bundle, and `parsers install --language <language>` downloads the
pinned wheels and builds the bundle. Without parsers, the project graph degrades explicitly: checks
show this on a separate line and do not silently narrow the impact of changes.

```bash
python3 harness/bin/harness.py parsers status /path/to/repository
python3 harness/bin/harness.py parsers install /path/to/repository --language python
```

## Coordinator

When `backend-orchestration` is installed, the project gets
`.harness/orchestration/coordinator.py` — the orchestration CLI. All commands are read-only where this
is declared; state is read only through them.

| Group | Purpose |
| --- | --- |
| `config` | Validation and normalization of the orchestration configuration |
| `ledger` | Integrity of the audit chain, lock, status |
| `runtime` | Query to the runtime process: handshake and state |
| `batch` | Batch lifecycle: plan, approval, reports, decisions |
| `dispatch` | Launch, observation, and stopping of roles |
| `qa` | QA run and its evidence |
| `integration` | Integration record, CI evidence, next step |
| `risk` | Change risk assessment |
| `context-package` | Registration of a deterministic context package |

The gate order and batch handling are described in the [`/implement`](../guides/implement.md) guide.

## Console

`harness console <repo>` starts the interactive console: tasks, orchestration, reports, and
recovery. The console is beta. It needs `uv`, and the first run downloads dependencies, so network
access is required.

`--web` starts the console server, prints a URL with a token, and opens the browser; `--no-open` prints the
URL without opening it. The console server is the same interface as the TUI, but for the browser: thin
endpoints and a React/TS client.

## Next

- [“/implement”](../guides/implement.md)
- [QA gate and Release Gate](../guides/qa-gate.md)
- [Labels](labels.md)
- [Reference](index.md)
