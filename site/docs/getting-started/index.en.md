# Quick start

Agent Harness Next installs skills, hooks, and context documents into a project as a verifiable
snapshot. After installation the project runs on its own. Skills and hooks work through the native
mechanisms of Claude Code and Codex, and orchestration uses the Rust runtime and the local runtime store.

!!! note "Early access"

    This site describes the current version, but behavior and flags still change. Before you install
    into a working project, make a backup and check the requirements.

## Start with an agent {#agent-setup}

[New project](../skills/start-project.md) · [Existing project](../skills/integrate-project.md) · [Shape the idea](../skills/grilling.md) · [Terms and ADRs](../skills/vendor/domain-modeling.md).

??? quote ah-skill-text "Agent prompt: start a new project"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Read and invoke the installed start-project skill; do not duplicate or bypass its phases.
    If it cannot be located, report the missing skill instead of simulating it.
    Start with the idea: goal, users, recurring work, project type and stack constraints.
    Follow Shape to decide whether to stay in conversation, write a brief, seed a repository or
    assemble a harness. Ask before creating a repository; do not assume software or choose a stack.
    For an approved seed, agree on structure, CONTEXT.md terminology and first ADRs for stack,
    branching and QA. Record only confirmed decisions with sources; leave open choices explicit.
    For approved harness assembly, choose capability, language, branch pattern, actual QA commands
    and project.json from evidence and answers. Keep phases independently reviewable.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Agent prompt: integrate an existing project"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Read and invoke the installed integrate-project skill; do not duplicate its workflow.
    If unavailable, report the missing skill instead of pretending to invoke it.
    Audit read-only first: manifests, actual build/test commands, CI, branches, domain, existing
    AI instructions/configuration, ADR conventions and installed harness state. Preserve live work.
    Present findings, conflicts and the proposed installation manifest; wait for confirmation.
    Offer optional decision-history reconstruction separately when useful. Read that skill's
    RECONSTRUCT-HISTORY.md only for the approved investigation; do not invent reasons from code.
    Each proposed ADR needs evidence/source links; label uncertainty and obtain consent before
    writing inferred decisions. Create or extend the existing ADR convention and CONTEXT.md.
    Only after the approved audit/manifest, install the selected capability without replacing
    unrelated native settings. Configure project.json with discovered QA commands, not guesses.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

## Installation path

Select a build. The diagram shows which snapshot ends up in the project. The nodes are clickable.

<div class="ah-flow" id="ah-install-flow">
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
| `uv` | Required for the console environment and local harness checks; absence produces `environment.uv: fail` |
| `harness-runtime` | For backend orchestration; building from source requires Rust 1.89+ |
| Optional | Docker or rootless Podman for the container worker and QA |

Harness does not install the project's own dependencies. Prepare them separately using the
[environment guide](settings/environment.md).

## 1. Install the global layer

The global layer is installed once per machine. It holds a minimal instruction profile and the
`start-project` and `integrate-project` skills. The `--runtime` option is repeatable.

```bash {.ah-code-wrap}
python3 bin/install-global.py --target-home "$HOME" \
  --runtime claude --runtime codex
```

`--check` shows the status without writing. `--replace-conflicts` replaces conflicting files and
saves a backup of them first. The installer does not touch MCP, models, plugins, credentials, or
permissions.

??? quote ah-skill-text "Agent prompt: global layer"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Locate bin/install-global.py in the actual harness source and inspect --help.
    Inspect --check before proposing installation. Ask which runtime(s) and target home are needed;
    --runtime is repeatable. Show the exact command and global-file effects, then obtain approval.
    After approval run that installation and check status again. Do not replace conflicts without
    separate approval; explain the documented backup behavior. Do not configure credentials/MCP.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```


## 2. Connect the harness to a project

Start a new project with the `start-project` skill. Start an existing project with
`integrate-project`: it studies the repository conventions first and then embeds the harness.

Direct installation into a Git repository:

```bash {.ah-code-wrap}
python3 harness/bin/harness.py init /path/to/repository \
  --capability engineering-suite \
  --project-type software --stack python --base-branch main --language ru \
  --qa-gate-command "make test"
```

If the project already has its own skills with the same names, use `adopt`. It keeps everything that
is not part of the selected capability and fails with a list of conflicts. `--replace-conflicts`
replaces the conflicting directories without a backup, so check the list first.

```bash {.ah-code-wrap}
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

??? quote ah-skill-text "Agent prompt: connect the harness"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Determine whether the repository is new, established or already harnessed. Recommend the
    installed start-project, integrate-project or an explicit CLI installation based on that state.
    Inspect harness --help; ask unresolved capability, project type, stack, base branch, language
    and QA commands. Show install/adopt effects and conflicts. Execute only the approved command;
    do not silently use --replace-conflicts or overwrite project configuration.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```


## 3. Check the installation: health

`health` checks the installation and the environment, and without flags it changes nothing. Run it
after `init`, `adopt`, or `update`, after you clone a project, and when the agent does not find the skills.

```bash {.ah-code-wrap}
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

??? quote ah-skill-text "Agent prompt: check health"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Run the installed local harness health for the exact repository; this does not require online
    checks. Explain ok/warn/fail/skipped and their concrete consequences, without copying secrets.
    Propose fixes one group at a time. Ask before --fix, inspect its effects, then run only approved
    repairs and recheck. Do not use --online without consent; tracker login and permission changes
    remain the user's actions. A skipped check is not a passed check.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```


## 4. First commands

```bash {.ah-code-wrap}
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

```bash {.ah-code-wrap}
python3 .harness/orchestration/coordinator.py --repo . dispatch preflight \
  --batch '<batch-id>' --role developer
python3 .harness/orchestration/coordinator.py --repo . ledger validate --full
```

??? quote ah-skill-text "Agent prompt: first commands"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Explain list and diff from the installed CLI and use them to show current state.
    Ask which next operation is wanted: update, cleanup preview or console. Preview update changes
    and cleanup's deletion set; update and cleanup --apply need explicit confirmation.
    Explain console first-run uv downloads and that its bootstrap URL contains a credential;
    do not print that URL in reports. Do not start services or perform cleanup just to demonstrate.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```


## Next

- [Workflow](../guides/workflow.md)
- [CLI and configuration](../reference/cli.md)
- [Architecture overview](../architecture/overview.md)
- [Rust runtime](../architecture/runtime.md)
- [Reference](../reference/index.md)
- [Demo](../demo/index.md)
