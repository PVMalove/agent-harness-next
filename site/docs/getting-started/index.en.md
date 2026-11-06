# Quick start

Agent Harness Next installs skills, hooks, and context documents into a project as a verifiable
snapshot. After installation the project runs on its own. Skills and hooks work through the native
mechanisms of Claude Code and Codex, and orchestration uses the Rust runtime and the local runtime store.

!!! note "Early access"

    This site describes the current version, but behavior and flags still change. Before you install
    into a working project, make a backup and check the requirements.

## Installation path

Select a build. The diagram shows which snapshot ends up in the project. The nodes are clickable.

<div class="ah-flow" id="ah-install-flow">
  <button class="ah-diagram-expand ah-core-expand" id="ah-install-expand" type="button" aria-haspopup="dialog">Expand</button>
  <div class="ah-core-scroll"><div class="ah-core is-fit" id="ah-install-map"></div></div>
  <div class="ah-flow-note" id="ah-install-note" aria-live="polite">
    <b>Select a build</b>
    <span>Click a capability or any node of the diagram.</span>
  </div>
</div>

## Requirements

| Component | Requirement |
| --- | --- |
| Python | 3.12 or newer |
| Git | The project directory is already initialized as a Git repository |
| Runtime | Claude Code or Codex: skills and hooks connect natively |
| OS | Linux; on Windows, a supported runtime and a named pipe |
| `uv` | For the web console and local harness checks |
| Optional | Docker or rootless Podman for the container worker and QA |

## 1. Install the global layer

The global layer is installed once per machine. It holds a minimal instruction profile and the
`start-project` and `integrate-project` skills. The `--runtime` option is repeatable.

```bash
python3 bin/install-global.py --target-home "$HOME" \
  --runtime claude --runtime codex
```

`--check` shows the status without writing. `--replace-conflicts` replaces conflicting files and
saves a backup of them first. The installer does not touch MCP, models, plugins, credentials, or
permissions.

## 2. Connect the harness to a project

Start a new project with the `start-project` skill. Start an existing project with
`integrate-project`: it studies the repository conventions first and then embeds the harness.

Direct installation into a Git repository:

```bash
python3 harness/bin/harness.py init /path/to/repository \
  --capability engineering-suite \
  --project-type software --stack python --base-branch main --language ru \
  --qa-gate-command "make test"
```

If the project already has its own skills with the same names, use `adopt`. It keeps everything that
is not part of the selected capability and fails with a list of conflicts. `--replace-conflicts`
replaces the conflicting directories without a backup, so check the list first.

```bash
python3 harness/bin/harness.py adopt /path/to/repository \
  --capability engineering-suite --replace-conflicts
```

A capability sets the snapshot contents. The builds are mutually exclusive.

| Capability | What it adds |
| --- | --- |
| `project-foundation` | The default domain-neutral base: design, research, handoff, and the project language. |
| `mattpocock-suite` | The full upstream set, pinned to a verified commit. |
| `engineering-suite` | The engineering workflow: epics and tickets, triage, two-axis review, `qa-gate`, and PR preparation. |
| `backend-orchestration` | On top of `engineering-suite`: a coordinator, roles, briefs, worktrees, a ledger, and a QA lane. |

## 3. Check the installation: health

`health` checks the installation and the environment, and without flags it changes nothing. Run it
after `init`, `adopt`, or `update`, after you clone a project, and when the agent does not find the skills.

```bash
python3 harness/bin/harness.py health /path/to/repository
python3 harness/bin/harness.py health /path/to/repository --fix
python3 harness/bin/harness.py health /path/to/repository --online
python3 harness/bin/harness.py health /path/to/repository --json
```

| Flag | What it does |
| --- | --- |
| no flags | Local checks of files, directories, the environment, and the Repo Map. |
| `--fix` | Creates the missing `.harness/` directories and regenerates a stale skill registry. It does not touch worktrees. |
| `--online` | Adds tracker checks: `gh`/`glab` authorization, origin reachability, permissions, and labels. |
| `--json` | Prints a machine-readable report with `schema_version: 1`. |

Each line is marked `✅` ok, `⚠️` warn, `❌` fail, or `-` skipped. On `fail` the command prints the
reason and the command that fixes it. The "Orchestration" group appears only with `backend-orchestration`.
It shows the ledger, unfinished batches, dispatches without activity, and untracked worktrees.

## 4. First commands

```bash
python3 harness/bin/harness.py list /path/to/repository
python3 harness/bin/harness.py diff /path/to/repository
python3 harness/bin/harness.py update /path/to/repository
```

| Command | Purpose |
| --- | --- |
| `list <repo>` | Lists the installed skills. |
| `diff <repo>` | Shows the differences from the locked snapshot; `--json` gives a machine-readable report. |
| `update <repo>` | Pulls the new capability version and keeps the local edits. |
| `console <repo>` | The TUI panel and the web console: tasks, orchestration, reports, and recovery. |
| `cleanup <repo>` | A cleanup plan for `.harness/.sandboxes`; `--apply` deletes, and `--mode hard` requires `--apply --confirm HARD`. |
| `uninstall <repo>` | A plan and the full removal of the harness; `--apply --confirm UNINSTALL` saves the changed files in `.harness-uninstall-backup/`. |

`console` is beta. It needs `uv`, and on the first run it downloads dependencies, so it needs network
access. `console --web` starts the Console Server, prints a URL with a token, and opens the browser.

If `backend-orchestration` is installed, add a state check:

```bash
python3 .harness/orchestration/coordinator.py --repo . dispatch preflight
python3 .harness/orchestration/coordinator.py --repo . ledger validate --full
```

## Next

- [Workflow](../guides/workflow.md)
- [CLI and configuration](../reference/cli.md)
- [Architecture overview](../architecture/overview.md)
- [Rust runtime](../architecture/runtime.md)
- [Reference](../reference/index.md)
- [Demo](../demo/index.md)
