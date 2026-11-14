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
| `cleanup` | Plan and removal of disposable `.harness` data and abandoned container resources | only with `--apply` |
| `worktree-remove` | Removes a managed worktree and keeps the branch | yes |
| `worktree-venv` | Links an issue worktree's `.harness/.venv` to the main checkout's venv when `uv.lock` and `pyproject.toml` match | yes |
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

The capability defines the content of the snapshot. The builds: `project-foundation`,
`mattpocock-suite`, `engineering-suite`, `backend-orchestration`. Without `--capability`, `project-foundation`
is installed. `engineering-suite` extends `mattpocock-suite`, and `backend-orchestration` extends
`engineering-suite`.

## The `.harness/project.json` configuration

The contract is strict: an unknown field is an error, not a warning. `language`, `base_branch`,
`branch_pattern`, and `qa_gate_commands` are required; the other fields are optional. Each field is read by its own
consumer.

| Field | Purpose |
| --- | --- |
| `$schema` | Link to the project configuration schema |
| `language` | Output language (`ru` or `en`): code-review reports and the PR body template |
| `base_branch` | Release branch: `/to-spec` creates epic integration branches from it; it is also the base for work without an epic |
| `branch_pattern` | Regular expression for the issue branch name |
| `qa_gate_commands` | Commands of the full local quality run |
| `shell` | Shell for `qa_gate_commands`: `bash` or `powershell` |
| `tracker` | Project tracker: `type` (`github`, `gitlab`, `local`), `host`, `project` |
| `ci_required_checks` | Names of CI checks whose evidence is accepted instead of local QA |
| `test_paths` | Relative glob paths of tests: the only write zone of test-author; without the field, test-author is off |
| `test_runner` | Command that runs a single test in isolation; together with `test_paths`, required for test-author |
| `test_author` | Executor of the short test-author route: `runtime`, `model`, `effort` |
| `hook_policy` | Hooks policy: `profile` (`minimal`, `standard`, `strict`) and `escalations` |
| `story_points` | Estimation scale and thresholds for routing to `pipeline::fast` / `pipeline::full` |
| `memory` | Enables the local project memory |
| `memory_policy` | Allowed sources, redact rules, threshold, and memory budget |

Inside `tracker`, only `type`, `host`, and `project` are allowed. Certificates, proxies, and credentials
are not written here: they stay in the personal configuration of the tracker CLI. Inside `hook_policy`, escalations
only raise the profile for paths and roles; the validator rejects an escalation weaker than the base profile.

## CI evidence

The `ci_required_checks` field is a list of unique non-empty names of CI checks. When all of them
pass, the coordinator accepts the evidence from the tracker instead of a repeated full local QA run. An
empty or missing field means that CI evidence is not configured and local QA is required.

The names in `ci_required_checks` are full checks: `verify`, `rust` and the other jobs that
`verify.yml` runs for a pull request into `master`. Do not list `-light` names there: the
`verify-light` job runs only for a pull request into `integration/**`, and `collect-ci` answers such
a check with the reason `light_check` when the pair requires full QA. The field lives in the local
`.harness/project.json`, which is not committed. The operator sets it once when enabling CI
evidence and describes that step in the pull request text (ADR 0016, addendum #937).

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
| `--online` | Adds tracker checks: CLI authorization, remote availability, permissions, and labels (up to 10 s per check); without the flag, every `tracker.*` check except `tracker.project` is skipped |
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

Repo Map builds the project graph with tree-sitter parsers. `parsers status` shows the state of the parser
bundle, and `parsers install --language <language>` downloads the pinned wheels and builds the bundle; the
languages are `python`, `typescript`, `javascript`, `go`, `java`, `csharp`, and the flag is repeatable. Without parsers, the project graph degrades explicitly: checks
show this on a separate line and do not silently narrow the impact of changes.

```bash
python3 harness/bin/harness.py parsers status /path/to/repository
python3 harness/bin/harness.py parsers install /path/to/repository --language python
```

## Coordinator

When `backend-orchestration` is installed, the project gets
`.harness/orchestration/coordinator.py` — the orchestration CLI. Orchestration state is read only through its
commands; commands marked read-only change nothing. The `harness-runtime serve` process holds the state: while it
is not running, orchestration commands refuse with `[runtime_unavailable]`.

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
| `report` | Intake of role reports (`report submit`) and the report policy steps (`report complete`) |
| `recovery` | Status, reload, resume, fix, and abort of a stopped batch |

The gate order and batch handling are described in the [`/implement`](../guides/implement.md) guide.

## Console

`harness console <repo>` starts the interactive console: tasks, orchestration, reports, and
recovery. The console is beta. It needs `uv`, and the first run downloads dependencies, so network
access is required. If `uv` is not in `PATH`, the command shows the `harness health` report.

`--web` starts the console server or finds a running one, prints a URL with a token, and opens the browser; `--no-open` prints the
URL without opening it. The console server is the same interface as the TUI, but for the browser: thin
endpoints and a React/TS client.

## Next

- [“/implement”](../guides/implement.md)
- [QA gate and Release Gate](../guides/qa-gate.md)
- [Labels](labels.md)
- [Reference](index.md)
