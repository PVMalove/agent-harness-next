---
title: Releases
description: Agent Harness Next releases.
toc_depth: 2
---

# Releases

A short change history: each release has a date, a summary of changes, and collapsed full
notes. The canonical list with assets is in [GitHub Releases](https://github.com/PVMalove/agent-harness-next/releases).

<div class="ah-releases" markdown="1">

## v2.0.0 {.ah-release-title}

<p class="ah-release-meta">Breaking: 4 · Added: 63 · Changed: 26 · Fixed: 44</p>

<p class="ah-release-summary">Highlights: required Rust runtime and runtime store · ledger version 4 · migrate and rollback with human approval · web console.</p>

Moving from 1.x and rolling back are described in the [upgrade guide](../guides/upgrade-2-0.md); the
supported platforms are on the [Platforms](../project/platforms.md) page.

???+ note "Breaking changes"

    - **[Required Rust runtime]:** Orchestration operational state lives in the runtime store `state/runtime.db`, and only `harness-runtime serve` writes to it. An unavailable runtime gives `runtime_unavailable` and exit code 2 (#792, #801, #807).
    - **[Ledger version 4]:** `harness-runtime migrate` moves ledger version 3 to the runtime store and writes `ledger.json` with `version: 4`; after that, a 1.x installation refuses with exit code 2 (#797).
    - **[File epoch until migrate]:** Coordinator 2.0.0 runs on the file `ledger.json` version 3 until a human runs `harness-runtime migrate`; a version 1 or 2 ledger must first be converted with `coordinator.py ledger migrate`. The container QA, the docker executor, the `recovery` commands and the operational hold need the runtime store, and in the file epoch they exit with code 2 and name `harness-runtime migrate` in the remedy (#814).
    - **[New project on the runtime store]:** A project without orchestration state gets its store from `harness-runtime init` with a human approval, with no file ledger and no `migrate`. The coordinator creates no file ledger on such a project: `batch create`, `batch plan` and `ledger reset` exit with code 2 and name `harness-runtime init` in the remedy. ADR 0036 (#1146).
    - **[Migrate with approval]:** `harness-runtime migrate` and `rollback --to-legacy` require `--approved-by`, `--approved-at`, and `--reason`, and only a human runs them (#803, #826).

The full list of additions, changes, and fixes is in the `[2.0.0]` section of
[CHANGELOG.md](https://github.com/PVMalove/agent-harness-next/blob/master/CHANGELOG.md).

## v1.5.1 — 18 October 2026 {.ah-release-title}

<p class="ah-release-meta">Added: 4 · Changed: 2 · Fixed: 4 · <a href="https://github.com/PVMalove/agent-harness-next/releases/tag/v1.5.1">Open on GitHub</a></p>

<p class="ah-release-summary">Highlights: Batch verification profiles · Fast developer-retry checks · Lock ledger state.</p>

??? note "Full notes"

    **Added**

    - **[Batch verification profiles]:** The optional `verification_profiles` key in `.harness/orchestration.json` sets the developer and code-review commands for a path scope. `batch create` freezes the commands of the first profile whose `paths` cover every `--allowed-path`. With partial coverage, or without the key, the batch gets the shared lists, and clean-room QA still runs `verification_commands`.
    - **[Fast developer-retry checks]:** The optional `retry_verification` key (`lint` and `test_command`) gives a developer retry the lint commands and one test command for the `related_tests` of its Context Package. Without related tests, or without the key, the retry runs the usual developer commands. The first developer dispatch, code-review, and QA do not change, and `checks_run` is still compared with the brief verbatim (#757).
    - **[Lock ledger state]:** When the ledger is busy, `ledger lock-status` immediately reports who holds the lock, how long it has been held, and when it can be released, without waiting for the ledger to become free. The same summary appears in the orchestration section of the console and updates on the live screen (#759).
    - **[Forced lock release]:** `ledger release-lock --force --approved-by --approved-at --reason` releases a lock at any verdict, only with human approval, and writes an audit record with a checksum that `ledger validate` verifies. No policy, including `auto`, runs the command; in the console it is available with confirmation (#759).

    **Changed**

    - **[Parallel pytest]:** `make verify` runs pytest with up to eight workers instead of four when enough cores are available (#758).
    - **[Windows CI checks]:** The `verify-windows` job is disabled and kept commented out in `verify.yml`, and `windows-latest` is removed from the vector memory probe matrix. Linux checks did not change (#753).

    **Fixed**

    - **[Sandbox worker lock]:** The lock records the PID namespace and the boot of the owner, so `ledger release-lock` no longer takes a foreign process with the same pid for the live owner. The lock of a stopped sandbox worker is released on timeout. Records of the old format are checked as before (#759).
    - **[Cleanup after squash-merge]:** The cleanup step of `/to-pull-requests` checks whether the branch is merged by the PR state, not by `git branch -d`, which always refuses after a squash-merge. The agent offers to delete the local branch to the developer, and the developer runs `git branch -D` (#753).
    - **[Metadata check in an integration branch PR]:** CI no longer checks commit messages that are already in the default branch. Before, a PR that merged a fresh `master` into an integration branch failed on a foreign published commit whose message can no longer be fixed. New commits of the PR are checked as before (#753).
    - **[Console configuration without `project.json`]:** The console configuration section again builds the default `project.json` document. Since 1.5.0 the template contains a placeholder for the test fields, the console did not fill it, and it refused with the error "valid JSON required" (#753).

## v1.5.0 — 18 October 2026 {.ah-release-title}

<p class="ah-release-meta">Added: 7 · Fixed: 2 · <a href="https://github.com/PVMalove/agent-harness-next/releases/tag/v1.5.0">Open on GitHub</a></p>

<p class="ah-release-summary">Highlights: Test author in fast-implement · Protected build and database · Test author.</p>

??? note "Full notes"

    **Added**

    - **[Test author in fast-implement]:** `/fast-implement` agrees the seam with the developer before the first test. When `test-author-preflight.sh` returns `{"status":"ok"}`, it runs the same Red→Green→Refactor cycle as the developer of the full route: it passes the requirement and the scenario without the algorithm, checks the expectation, adds a skeleton, forbids weakening an accepted expectation, and limits the cycle to three failed calls. An unavailable author, a failed hook, or unavailable isolation keeps the ordinary `/tdd` with a named reason. The coordinator, architect, and QA steps are not added, and the ledger and approvals do not change. The project guide `docs/agents/test-author.md` describes the opt-in, the settings of the protected environment, the supported versions and environments, and rollback. Clean-room checks the full and short routes, a new and an old project without `test_paths`, rollback with a failed hook and with unavailable isolation, a simple test, and the build and database scenarios with a scripted model stub. Only `make test-author-probe` confirms real Claude Code. The quality of tests written by a model is not measured (#557).
    - **[Protected build and database]:** The optional `test_runner.build` and `test_runner.database` prepare fresh artifacts and a separate test database inside the sandbox. The build writes only to empty approved directories through temporary backing directories, and the test reads the artifacts without write access. Sources and configuration stay protected. The database starts only for the selected SQL tests and stops together with them. The schema, the CLI flags, `harness health`, and preflight support the settings without changing projects that do not have them. Clean-room checks a real compiler and PostgreSQL, including rollback and constraints. `HARNESS_REQUIRE_TEST_DATABASE=1` forbids skipping the database evidence (#556).

    - **[Test author]:** The `pvmalove-suite` installation adds the optional `test-author` subagent, its scoped guard `.claude/hooks/test-author-guard.py`, and the activation check `.claude/hooks/test-author-preflight.sh`. The subagent writes one behavior test and runs it through `run-test.sh`. Writing is allowed only inside `test_paths` (zones of the form `<directory>/**`), `Bash` only for the runner call, and a refusal is returned as a soft JSON with exit code 0 and does not affect the dispatch and the ledger. Preflight enables the author only with valid `test_paths` and `test_runner`, confirmed isolation, a working guard, and project trust accepted in Claude Code (`hasTrustDialogAccepted` for the exact path). Otherwise it answers with one reason (`project_untrusted`, `isolation_unavailable`, and others), and the developer continues the ordinary route. Support is limited to Claude Code. Clean-room checks activation, the three states of missing trust, soft refusals, and a real behavior Red. `make test-author-probe` additionally runs a real Claude Code, which confirms that the scoped hook fires and goes through the Red cycle itself (#554). `make verify` and CI do not run this probe: it needs credentials and spends quota.
    - **[Isolated test run]:** The `pvmalove-suite` installation adds `.claude/hooks/run-test.sh <test-id>`. The runner runs one selected test in a bubblewrap sandbox. In it, production code, `.git`, and the runner configuration are available to the test and its child processes read-only, host service sockets in `/run` are hidden, and writing is allowed only in the `test_paths` directories, the temporary directory, the cache, and the run reports. The test command is set by the new `test_runner` field in `.harness/project.json`, and `test_paths` is now described in the schema and checked by `harness health`. A new project gets both fields with the flags `harness init --test-path` and `--test-runner-command`; without the flags the fields are not written. Without confirmed isolation, the runner refuses with a clear reason and does not run the test. It returns the result as one short JSON line without the test output (#553).
    - **[Red→Green→Refactor cycle with the test author]:** While `test-author-preflight.sh` returns `ok`, the developer runs every implementation step as a cycle with the test author: passes the requirement, the seam, the public signatures, and the fixtures, checks the expectation against the requirement before implementation, and does not weaken an accepted expectation for Green. The statuses `red`, `needs_skeleton`, and `contract_gap` are handled explicitly. Compilation, import, fixture, and environment errors do not count as Red, and a test that is green at once is not accepted. After three failed calls in a row for one test, the ordinary blocker applies, and there are no new dispatches or ledger states. A clean-room scenario with a scripted model stub checks the cycle (#555).
    - **[External runtime adapters]:** Claude Code and Codex run a separate worker in the assigned checkout with the parameters from the brief. The CLI installs and updates the adapters together with `backend-orchestration`, and the console settings show their state and require a review with confirmation. Local files are protected from implicit replacement. The shared seed adds six permissions for observing orchestration (#715).

    - **[Claude worker launch in an issue worktree]:** The `backend-orchestration` installation adds `.harness/adapters/claude_worker.py`, a runtime adapter for `transport: external`. The Agent tool cannot start a subagent in an existing checkout (the subagent starts in the main checkout, and `EnterWorktree` rejects it there), so a Claude in-process worker cannot start in `worker_worktree`. `dispatch send --adapter` runs the adapter in `worker_worktree`, and the adapter starts a detached headless `claude -p` with the model, effort, and `allowed_tools` from the brief and with `dontAsk`. The adapter lies outside the hashed runtime package, so installing it does not change the pin of an open batch. The skill `implement` and the guide `worktrees.md` describe both paths: the adapter gives a real cwd, while an in-process subagent works by absolute paths and `git -C`, and its self-report proves the checkout it works in, not the cwd (#718).

    **Fixed**

    - **[Recovery of unfinished development]:** `batch rewind --preserved-commit` keeps the explicitly confirmed commits and the uncommitted files of a stopped writer that are listed through `--preserved-file`, when the writer has no report or checkpoint. The next run checks the preserved checkout. The history, the manual approvals, and the retry budgets are kept (#733).
    - **[Candidate after rewind]:** The history and the ledger check use the `source_dispatch_id` of the candidate registration, so a repeated rewind after registration keeps the ledger readable (#715).

## v1.4.6 — 14 October 2026 {.ah-release-title}

<p class="ah-release-meta">Fixed: 2 · <a href="https://github.com/PVMalove/agent-harness-next/releases/tag/v1.4.6">Open on GitHub</a></p>

<p class="ah-release-summary">Highlights: Repeated batch base · Context Package.</p>

??? note "Full notes"

    **Fixed**

    - **[Repeated batch base]:** A batch created on a branch that has commits of an earlier batch of the same ticket counts its changes from `branch_start_commit`, not from `integration_base_commit`. The developer and publish reports, `scope_warnings`, the checkpoint, and the risk assessment no longer include foreign commits in `changed_files`, `commit_map`, and `review_scope`. `risk assess --base-commit` accepts this base. A superseding batch and the brief count as before (#686).
    - **[Context Package]:** A large Python file among the starting files enters the package as a symbol index with line ranges, not as a whole. If the package does not fit the token limit, the heaviest starting files are replaced with an index instead of `dispatch create` and `dispatch propose` refusing (#687).

## v1.4.5 — 13 October 2026 {.ah-release-title}

<p class="ah-release-meta">Added: 6 · Fixed: 3 · <a href="https://github.com/PVMalove/agent-harness-next/releases/tag/v1.4.5">Open on GitHub</a></p>

<p class="ah-release-summary">Highlights: Stages in console reports · Stage filters and order · Time to PR.</p>

??? note "Full notes"

    **Added**

    - **[Stages in console reports]:** The "Reports" section shows all recorded stages, including stages without a report, not only completed reports. A stage without a report opens the batch timeline, and the list is refreshed with the `r` key or the ↻ button (#676).
    - **[Stage filters and order]:** Stages are selected by status and by completeness (all, incomplete, complete), together with the previous filters by ticket, role, result, and date. The order is set by time, ticket, role, or status in both directions, and stages with unknown time stay at the end (#676).
    - **[Time to PR]:** The list and the batch timeline show the start of work and the time to PR creation, which the console reads through `gh` or `glab` on entry and on refresh, without writing to the ledger. If the request fails, the value stays "unknown", and if there is no PR, the console writes "PR not created yet" (#676).
    - **[Startup assessment in dispatch status]:** `dispatch status` shows the `startup` assessment for each dispatch: the worker state (`absent`, `reported`, `rejected-at-startup`, `stopped`, `live`, or `unknown`), the failure classification, and what remains unknown. Capacity, rate-limit, and service-unavailable are distinguished from each other and separated from code defects (#679).
    - **[Adapter flag check]:** `dispatch send` compares `--adapter-arg` with the adapter's `dispatch --help` and rejects an unsupported flag before it passes the brief, leaving the dispatch approved and unsent. If the help does not answer, the reason goes into `adapter_preflight` as a limitation, not as a confirmation of capabilities (#679).
    - **[Runtime probe without a worker]:** `dispatch runtime-probe` checks the app-server runtime against the brief: the model in `model/list`, the `thread/start` fields, and one `turn/start` on a read-only thread without tools. A capacity, rate-limit, or unavailability error after `thread/start` gives a classified failure, not READY. The probe writes nothing to the ledger and does not replace the model self-report (#679).

    **Fixed**

    - **[List recommendation in setup]:** An accepted recommendation for a list field updates the selection checkmarks, and later edits are kept. A partial selection no longer distorts the draft JSON (#676).
    - **[Premature abandon]:** The warning about a silent dispatch and the recovery messages name the read-only commands `batch auto-report`, `batch decision-packet`, `dispatch status`, and `ledger validate`, and offer waiting, `resume-stop`, or `rewind`, while `batch abandon` stays a separate human decision. An exhausted infrastructure retry budget keeps the batch in the stopped state until a human chooses, and the counters are not reset (#679).
    - **[Restart of an unknown worker]:** `batch resume-stop` refuses if `dispatch status` shows the worker in the state `live` or `unknown`, until the operator stops the worker through the runtime and repeats the command with `--runtime-stopped`. The previous path for a rejected self-report, a report, and a startup failure does not change (#679).

## v1.4.4 — 12 October 2026 {.ah-release-title}

<p class="ah-release-meta">Fixed: 1 · Changed: 1 · Breaking changes: 1 · <a href="https://github.com/PVMalove/agent-harness-next/releases/tag/v1.4.4">Open on GitHub</a></p>

<p class="ah-release-summary">Highlights: Report statuses · High-risk machine fields · Strict report enums.</p>

??? note "Full notes"

    **Fixed**

    - **[Report statuses]:** `blockers` and `risks` separate the system status `none | present` from the description, including both review axes, the checkpoint, and the continuation. Policies read the status, and an invalid report is rejected before it is written, with a fix hint. A repeated submission keeps automatic acceptance (#672, #674).

    **Changed**

    - **[High-risk machine fields]:** Separate enums set the results of integration checks (`passed / failed`), the retry reasons and routes, and the batch and dispatch states. The values are checked at the read and write boundaries. Unknown literals do not become evidence of success or a new state. The transition rules, the approvals, the SHA bindings, and the spending of the retry budget are kept (#674).

    **Breaking changes**

    - **[Strict report enums]:** `blockers` and `risks` require the object `{"status": "none", "details": ""}` or `{"status": "present", "details": "description"}`, and the check result must be exactly `pass`, `fail`, or `not_run`. Old strings, `passed`, `not-run`, and `not_run_architect_read_only` are no longer accepted. Saved reports are not rewritten (#672, #674).

## v1.4.2 — 12 October 2026 {.ah-release-title}

<p class="ah-release-meta">Fixed: 1 · <a href="https://github.com/PVMalove/agent-harness-next/releases/tag/v1.4.2">Open on GitHub</a></p>

<p class="ah-release-summary">Highlights: Report check results.</p>

??? note "Full notes"

    **Fixed**

    - **[Report check results]:** `report submit` accepts the equivalent `pass` and `passed`, saves success as `pass`, and saves a check that was not run as `not_run`. The old `not-run` is accepted for compatibility. Saved reports are read without being rewritten. Unknown results are rejected with a hint before the report is written, and they no longer stop the automatic path after submission (#669).

## v1.4.1 — 12 October 2026 {.ah-release-title}

<p class="ah-release-meta">Added: 6 · Changed: 2 · Fixed: 2 · <a href="https://github.com/PVMalove/agent-harness-next/releases/tag/v1.4.1">Open on GitHub</a></p>

<p class="ah-release-summary">Highlights: Harness update in the console · Seed file selection · Console language.</p>

??? note "Full notes"

    **Added**

    - **[Harness update in the console]:** A separate screen shows the versions, the drift of managed files, and a line-by-line diff, and offers the update mode and a confirmed run (#668).
    - **[Seed file selection]:** The `harness update` command accepts the repeatable flag `--force-seed-file PATH`, which overwrites only the listed seed files, and `harness diff --json` lists the differing seed files in the `seed_differing` field. The console lets you select the files with checkmarks (#668).
    - **[Console language]:** The `F2` key switches the interface between Russian and English, including on screens that are already open. `HARNESS_CONSOLE_LANG` sets the initial language (#668).

    - **[Menu instead of JSON in setup]:** Entries of nested blocks (for example, `assignment_plans`) and lists of strings are edited with menu items: add an entry (with settings copied from an existing one), configure, delete. The "As text (JSON)" button returns to editing as text, and a block with fields shows a summary instead of the whole JSON (#668).

    - **[Repo Map settings]:** The "Settings" tab in the Repo Map window switches the map mode `minimal`/`full`, opens the wizard on `repo_map_policy`, installs the parsers of the selected languages, and manages project memory: initialization (enabling with the default sources and `harness memory build`), synchronization, rebuild, and the wizard on `memory_policy`. The "Diagnostics" tab checks HEAD, the mode, the parser bundle, the coverage of project languages, the built map, and the memory, and suggests what to fix (#668).
    - **[Parser installation]:** The command `harness parsers install <repo> --language <language>` downloads only the needed pinned wheels from PyPI, verifies SHA-256, and assembles a bundle in the local registry, and `harness parsers status` shows for which languages it is usable (#668).

    **Changed**

    - **[Unified console style]:** All screens are framed after the model of the main one: a top line with the version, the branch, and the check counters, a colored result log, and unified buttons and menu sizes. The title shows the commit of the selected project (#668).
    - **[Configuration versions directory]:** Versions are stored in `.harness/config_versions/` instead of `.harness/config-versions/`. Versions from the previous directory are moved on first access, so nothing is lost, and the storage path is visible on the setup and versions screens (#668).

    **Fixed**

    - **[Copy and paste in the console]:** Ctrl+C and Ctrl+V work with the system clipboard (Wayland, X11, macOS, Windows, WSL), not only with the application buffer (#668).
    - **[AI hint response]:** A CLI response in a code block or with an encoded value is accepted, and a refusal names the reason instead of the general "unsuitable recommendation" (#668).

## v1.4.0 — 11 October 2026 {.ah-release-title}

<p class="ah-release-meta">Added: 5 · Changed: 3 · Fixed: 3 · <a href="https://github.com/PVMalove/agent-harness-next/releases/tag/v1.4.0">Open on GitHub</a></p>

<p class="ah-release-summary">Highlights: Setup in the console · Configuration versions · Connecting another project.</p>

??? note "Full notes"

    **Added**

    - **[Setup in the console]:** A step-by-step wizard explains the parameters of `project.json` and `orchestration.json`, marks the recommended option, and takes project features into account (Makefile, stack, default branch). The wizard checks the draft, links errors to steps, and applies the files after a review of the differences (#663).
    - **[Configuration versions]:** Both JSON configurations are saved as a version in `.harness/config-versions/` without being applied, from the setup menu, and are restored with an automatic backup of the current set. A damaged version stays in the list with the reason, and a version from another Harness release is marked with a warning (#663).
    - **[Connecting another project]:** The main screen leads through the steps "choose a project → preliminary checks → installation → setup → final diagnostics" for the selected Git project. The installation goes through the same confirmation form as the Harness section, and an update keeps the set of capabilities that is already installed (#663).
    - **[Diagnostics on connection]:** The report separates what was checked from what was skipped, and the analysis of sandbox settings from actual access. The online GitHub/GitLab checks and the local fixes run as separate actions (#663).
    - **[Optional AI hints]:** The wizard uses the current authorization of an available Codex CLI or Claude Code CLI, compares up to four options, and explains the choice. The CLI status is determined without a request to the model. If the CLI is unavailable, the wizard continues with the ordinary hints (#663).

    **Changed**

    - **[Reading the configuration]:** Health, memory, and the coordinator read `project.json` and `orchestration.json` as a consistent pair through `harness/configuration.py`, so they do not see a mixed set during a write. Writing and versions are moved to `harness/configuration_store.py` and are not part of the installation into target projects (#663).
    - **[Console: screen workers]:** On close, the dashboard cancels only its own background checks, not the workers of child screens (#663).
    - **[Configuration schema]:** `branch_pattern` in `project.schema.json` got `format: regex`, and `harness health` rejects an invalid regular expression. In `orchestration.schema.json`, the `infrastructure_retry_policy` block is moved to the top level of `properties`, and `effort` is limited to the enumeration `none … ultra` (#663).

    **Fixed**

    - **[Paths with symbolic links]:** Reading the configuration no longer wrongly rejects a repository opened through a symbolic link or a relative path (#663).
    - **[Backup before writing]:** References to environment variables such as `TOKEN=$CI_TOKEN` are not counted as a secret, and a refusal because of a secret names the file (#663).
    - **[CLI helper response]:** CLI warnings in stderr no longer spoil the structured response, and the line "Not logged in" is no longer counted as a Codex CLI login (#663).

## v1.3.2 — 11 October 2026 {.ah-release-title}

<p class="ah-release-meta">Added: 3 · Changed: 4 · <a href="https://github.com/PVMalove/agent-harness-next/releases/tag/v1.3.2">Open on GitHub</a></p>

<p class="ah-release-summary">Highlights: Manual orchestration recovery · Conditional stage acceptance · Retry threshold for review findings.</p>

??? note "Full notes"

    **Added**

    - **[Manual orchestration recovery]:** A stopped `auto` batch can be resumed with the `batch resume-stop` command, and the `batch rewind --to` command returns it to a previous stage. Accepted reports and decisions are kept, `ledger validate` checks the log without writing, and an early failure with code 429 no longer needs a checkpoint (#662).
    - **[Conditional stage acceptance]:** If a report is stopped only by an infrastructure failure and the work looks complete, a human accepts the stage with the command `batch decide --decision accept-conditional --infrastructure-failure`. The pipeline goes on, and publish waits until a later gate independently confirms the stage. `batch resume-stop` now also recognizes an infrastructure reason in the text of a blocked report. The decision stays with the human (#662).
    - **[Retry threshold for review findings]:** The parameter `auto_retry_min_severity` and the flag `batch create --auto-retry-min-severity` set the severity of review findings from which `auto` sends the work to a retry. The default is `info`: the previous behavior does not change (#662).

    **Changed**

    - **[Viewing an auto report does not write a stop]:** The `batch auto-report` command only reads the state. `batch auto-decide` writes the stop: the batch moves to `paused`, and a human resumes it from there (#662).
    - **[Unified abandon]:** Both refusal paths write `abandoned` with `last_accepted`, so `batch create --supersedes` accepts either of them (#662).
    - **[Worker directory check]:** For architect, developer, conflict-resolver, database-migrations, messaging-integration, and code-review, the working directory check is mandatory regardless of `worker_attestation_required`. An explicit `--worktree` is checked in `dispatch preflight` and `dispatch send` (#662).
    - **[Stricter batch resume]:** The `batch resume` command refuses for a batch with `approval_policy: auto`, a recorded stop, or a manual recovery. For them, use `batch resume-stop` (#662).

## v1.3.1 — 9 October 2026 {.ah-release-title}

<p class="ah-release-meta">Added: 18 · Changed: 13 · Fixed: 26 · Security: 4 · <a href="https://github.com/PVMalove/agent-harness-next/releases/tag/v1.3.1">Open on GitHub</a></p>

<p class="ah-release-summary">Highlights: Bounded infrastructure retries · Technical Russian rules · Separate QA environment preparation.</p>

??? note "Full notes"

    **Added**

    - **[Bounded infrastructure retries]:** A project may allow QA and publish retries after access is confirmed to be restored. The coordinator keeps the approved boundaries, the budget, and the earlier reports (#619).
    - **[Technical Russian rules]:** The writing rules for documentation and the changelog are collected in `docs/technical-russian.md`: coherent text, exact terminology, and the Keep a Changelog format without a limit on sentence length (#645).
    - **[Separate QA environment preparation]:** The `qa_preparation` parameter separates environment setup from the execution of code checks. An infrastructure failure no longer spends the developer's attempts (#618).
    - **[Access rights check]:** The coordinator checks access rights before QA, Git, and publish run. If rights are missing, the coordinator stops the operation and prints a fix instruction (#617).
    - **[Git error classification]:** The coordinator determines the exact cause of a failure in Git operations. The system no longer replaces an access denial with a merge conflict error (#617).
    - **[Automatic path auto]:** With `approval_policy: auto`, the coordinator goes from `batch approve` to an accepted publish without a human. The policy approves each step, and `batch auto-decide` makes the decisions on reports and writes them as `policy:auto` with evidence (#643).
    - **[Stops and final report]:** A closed list of stops ends the automatic path and passes each next step to a human. The `batch auto-report` command prints the final report before a PR is opened. Only a human opens the PR (#643).
    - **[First commit of grilling documents]:** `/to-spec` commits the changed grilling documents (`CONTEXT.md`, `CONTEXT-MAP.md`, ADRs in `docs/adr/`) as the first `docs: …` commit in the new integration branch of the epic, and publishes the branch with this commit. The current checkout switches to the new branch, and unrelated changes do not enter the commit. The hook `block-direct-master.sh` allows only this commit and only before the branch is published (#644).
    - **[Carrying over incomplete items]:** A read-only role lists the unfinished items of the brief in `incomplete_items`. The coordinator passes them to the target role through `--carry-incomplete` or repeats the stage with a narrowed retry (#501).
    - **[Tooling restart with changes]:** A tooling restart after a failure inherits the uncommitted changes of the developer. The developer continues the work without losing edits (#502).
    - **[Developer fix-forward]:** The `developer-retry` brief carries a closed list of carried-over items, and the report closes each item. The coordinator rejects the report if the history after the snapshot is rewritten (#503).
    - **[Rebase inside a retry]:** The route `rebase-fix-forward` carries the developer's work onto a new target inside the retry. The coordinator checks the carried commits through `rebased_from` and patch-id (#504).
    - **[Superseding batch]:** The command `batch create --supersedes` continues the work after `abandon` in a new batch. The new batch carries over the accepted architect plan and the last accepted candidate (#506).
    - **[Delta-review after fix-forward]:** Code-review after a fix-forward checks only the changes of the fix. The coordinator switches the review to full mode if the conditions of delta-review are not met (#625, #628).
    - **[Role access policy]:** The configuration sets the access of roles in modes that do not depend on the transport. The coordinator passes work to a role only after the worker's access is confirmed (#624).
    - **[QA evidence for the hook]:** The hook `require-qa-gate` accepts the QA evidence of the same HEAD that the coordinator accepted. A repeated `make verify` before a PR is no longer needed (#631).
    - **[Verify help]:** The command `scripts/verify.py --help` describes the verification stages and runs nothing. An unknown argument ends the command with code 2.
    - **[New Archify diagrams]:** The directory `docs/diagrams/` got five diagrams: project memory, the path `approval_policy: auto`, PR continuation, recovery routes, and module seams. Each diagram has a PNG preview.

    **Changed**

    - **[Context package refresh]:** The coordinator automatically creates a new context package when the memory sources change. The command `dispatch create` no longer fails with a stale context error (#636).
    - **[QA resource cleanup]:** The command `qa run` correctly releases the queue and resources on any error. The process does not hang and does not block the next runs (#617).
    - **[Warnings about change boundaries]:** Going outside the allowed paths now produces a warning instead of a hard refusal. The operator confirms such a change with the explicit action `override-warning` (#633).
    - **[Requirements for the auto configuration]:** The configuration check and `harness health` reject `approval_policy: auto` together with `human_approval_gate: tty`, or without `worker_attestation_required: true` (#643).
    - **[Auto batch after a configuration change]:** A batch created with `approval_policy: auto` approves steps by policy only while the project configuration selects `auto`. After the policy changes in the configuration, each transition of such a batch requires `--approved-by` and `--approved-at` (#643).
    - **[Git time limit]:** The harness limits the time of Git calls in hooks, the coordinator, `harness health`, cleanup, and installation. A hung or missing Git ends the command with an instruction and does not block the session.
    - **[Clean-room step limit]:** Each step of the clean-room check is limited in time. A hung step ends the check with a clear error instead of an idle CI.
    - **[Documentation in technical Russian]:** The README, the harness guide, and the backend orchestration guide are rewritten in living, coherent language by the rules of `docs/technical-russian.md`, without choppy phrases. Facts, links, and commands did not change.
    - **[Developer documentation separated from agent documentation]:** The guide `harness-guide.md` and the guide `backend-orchestration.md` are moved from `harness/docs/` to `docs/` and are no longer copied to `.harness/docs/` of the target project. The installation and `harness update` deliver only `technical-english.md` and `project-memory.md` to agents, and `harness update` removes stale copies of the guides.
    - **[Archify 3.0.1 diagrams]:** All diagrams in `docs/diagrams/` are rebuilt with the latest stable release, Archify 3.0.1, and the PNG previews are updated. The earlier diagrams were built with the candidate `2.17.0-dev.1`.
    - **[Diagrams of specific processes]:** The identical "input → work → result" diagram is removed from the pages of skills, hooks, and agents, and the `skill-contract-fill.*` files are deleted. The pages `/implement`, `/to-spec`, `/to-tickets`, `/wayfinder`, `/fast-implement`, `/triage`, `/qa-gate`, `/to-pull-requests`, `/grilling`, `coordinator`, and `playbook` show a diagram of their own process.
    - **[Orchestration configuration example]:** `orchestration.example.json` enables `approval_policy: auto`, parallel batches (`concurrency_budget: 5`), all eight roles with `transport`, `default_runtime`, and `write_paths`, `tool_policy`, `test_path_patterns`, and the Repo Map gate `min_tier`. The orchestration README describes the setup by this example without mentioning stale zones. The check lists stay empty: the project fills them.
    - **[Console help]:** The "Documentation" section in `harness console` refers to `harness --help` and `.harness/orchestration/playbook.md` instead of the guides that no longer exist in the project.

    **Fixed**

    - **[Tracker failure reason]:** `harness health --online` names the reason for a `git ls-remote origin` failure: credentials, a TLS certificate, a proxy, or the network. The hint points to the fix, and stderr, the `origin` URL, and credentials do not enter the output (#626).
    - **[unittest test discovery]:** `harness install` no longer installs `.harness/__init__.py`, and `python -m unittest` from the project root finds the project tests again. `harness update` removes this file from an earlier installation (#626).
    - **[Tracker in memory sync]:** `harness memory sync` takes the tracker from the `tracker` field in `.harness/project.json` and keeps the subgroups of the project path. The command explicitly addresses the host in `gh` and `glab` (#626).
    - **[Closure after rebase]:** The closure of carried-over items after `rebase-fix-forward` accepts only commits of the retry chain. Carried copies of earlier commits no longer close items (#627).
    - **[Batch preparation in implement]:** `/implement` prepares a batch only from English agent sources. Russian documentation no longer enters the preparation procedure (#641).
    - **[False commit blocking]:** The hook `block-direct-master` no longer blocks a command from a variable if the word `commit` appears only in an option. Commands without `git commit` and `git push` pass (#642).
    - **[False QA pass]:** The QA gate ran only the first part of a string command of the form `python a.py && python b.py`. Now the shell runs the whole chain, and the gate sees every failure.
    - **[Hooks on Python 3.9]:** The project hooks work on Python 3.9 again. Before, an import error blocked any Bash command.
    - **[Order of auto stops]:** The `auto` policy looks for a stop in this order: integrity, budget, route. An exhausted budget no longer hides an integrity violation.
    - **[Review blockers in auto]:** The `auto` policy does not accept a review report if the Standards or Spec axis names `blockers`. Such a report stops the automatic path until a human decides.
    - **[Auto final report]:** `batch auto-report` shows the coordinator findings that are not yet in the brief. The report counts the budget spent on one dispatch, and the hint for the next step takes a policy change into account.
    - **[Ledger cleanup]:** `ledger clean` no longer deletes the checkpoint of live batches. If a batch record is unreadable, the command refuses and deletes nothing.
    - **[Retry after a policy decision]:** An infrastructure retry checks the hash of the QA report. A report changed after the decision no longer allows a new brief.
    - **[Dispatch publish]:** `dispatch publish` limits the time of `git push` and checks the branch on the remote exactly. A hung push no longer holds the ledger lock.
    - **[Releasing the QA queue]:** An interrupted `qa run` releases the lease and the QA queue. Taking the queue with `integration local-qa` no longer breaks dispatch recovery.
    - **[Checkpoint after a base shift]:** The coordinator compares the developer checkpoint with the report base after the integration branch shifts. Files from upstream no longer cause a false refusal.
    - **[Conflict resolution]:** `integration resolve` after a race with the target names the created batch and the exact `batch abandon` command. A repeated resolve passes after that.
    - **[Local QA check]:** `integration local-qa` correctly reports that the branch is not based on the target. `context-package register` compares `--base-commit` with the actual base of the package.
    - **[Non-UTF-8 files]:** The coordinator reads a diff with files in legacy encodings without crashing. A report or role manifest that is not UTF-8 gives an error with an instruction.
    - **[Context Package]:** Context Package includes changed files with non-ASCII names and nested ADRs. A Git failure while building the package gives an error with an instruction.
    - **[Repo Map resilience]:** Repo Map goes into degraded mode with a damaged lock, a policy that is not UTF-8, and a bundle read error. The cache no longer leaves temporary files.
    - **[Project memory]:** Memory accepts glob patterns in the project root. A busy index gives the error "memory writer busy".
    - **[Integration inventory]:** The installer no longer overwrites an unreadable `.harness/integrations.json`. The command asks to fix the file and keeps the project entries.
    - **[Delivery statistics]:** The statistics report checks the rate card and gives an instruction for unreadable files. Damaged ledger records no longer interrupt the report.
    - **[Console harness console]:** The console screens show the error of a background run instead of the endless status "running…". The dashboard captures command output by default.
    - **[qa-gate summary]:** The `qa-gate` summary reports `Status: ERROR` if the command cannot be run. `diff_coverage` counts changed files with non-ASCII names.

    **Security**

    - **[Push from an issue branch]:** The hook `block-direct-master` blocks `git push --all`, `--branches`, `--mirror`, and glob refspecs. Such pushes could update `main` or `integration/*`.
    - **[Private names check]:** `check_private_terms` blocks publication if Git did not answer in time. Before, a timeout skipped the check.
    - **[Ledger generation directory]:** The ledger rejects a generation name with path separators. The pointer no longer leaves the ledger directory.
    - **[Vendor snapshot list]:** The vendor snapshot check compares the list of files in `SHA256SUMS`, not only their count. An extra or repeated line no longer hides an unchecked file.

## v1.2.0 — 2 October 2026 {.ah-release-title}

<p class="ah-release-meta">Added: 8 · Changed: 1 · Fixed: 1 · <a href="https://github.com/PVMalove/agent-harness-next/releases/tag/v1.2.0">Open on GitHub</a></p>

<p class="ah-release-summary">Highlights: Project memory (RAG): a computed SQLite FTS5 cache of "how this was solved before" based on local sources (ADRs, glossary, task archive, Completion reports, QA findings, and Lifecycle ledger) · Commands harness memory: build (cache build), search (search with BM25 ranking), rebuild (full rebuild), sync (sanitized snapshot of tickets and PRs from the tracker), and eval (offline quality evaluation) · Frozen memory pointers in Context Package: selection of relevant cards by the goal and DoD of the ticket with metadata (title, status, path, hash) without including untrusted source text; support for the --no-memory flag, quotas by source type, and a token limit inside the package budget.</p>

??? note "Full notes"

    **Added**

    - Project memory (RAG): a computed SQLite FTS5 cache of "how this was solved before" based on local sources (ADRs, glossary, task archive, Completion reports, QA findings, and Lifecycle ledger).
    - Commands `harness memory`: `build` (cache build), `search` (search with BM25 ranking), `rebuild` (full rebuild), `sync` (sanitized snapshot of tickets and PRs from the tracker), and `eval` (offline quality evaluation).
    - Frozen memory pointers in Context Package: selection of relevant cards by the goal and DoD of the ticket with metadata (title, status, path, hash) without including untrusted source text; support for the `--no-memory` flag, quotas by source type, and a token limit inside the package budget.
    - Memory evidence base in the Completion report: the fields `used_memory` (sources used) and `lessons` (lessons learned).
    - Project memory diagnostics in `harness health`: a check of SQLite FTS5 availability, the `memory_policy` configuration, the freshness of the index, and the tracker snapshot.
    - Shared index for linked worktrees: reading the local index of the main checkout without re-indexing.
    - Offline golden gate of search quality on a corpus of tickets, with measurement of recall@k and the noise level.
    - Documentation and a guide to project memory (`harness/docs/project-memory.md`) and to the procedure for updating existing projects in `harness/docs/harness-guide.md`.

    **Changed**

    - The project configuration `.harness/project.json` supports the optional sections `memory` and `memory_policy` (memory is off by default, existing projects keep working without opt-in).

    **Fixed**

    - Prevented the asyncio loop shutdown from hanging in console tests and added limited Windows verify diagnostics.

## v1.1.1 — 2 October 2026 {.ah-release-title}

<p class="ah-release-meta">Fixed: 2 · <a href="https://github.com/PVMalove/agent-harness-next/releases/tag/v1.1.1">Open on GitHub</a></p>

<p class="ah-release-summary">Highlights: Backend orchestration: a developer report retry without accept no longer leads the batch into a dead end · Backend orchestration: dispatch create runs the same brief checks as dispatch send, including the link between the candidate and the risk assessment.</p>

??? note "Full notes"

    **Fixed**

    - Backend orchestration: a developer report retry without `accept` no longer leads the batch into a dead end. The next developer dispatch pins `snapshot_commit` to the candidate of this report, is created and sent, and its commits continue the history of the candidate: `commit_map` counts only the new commits. A risk assessment can be registered for such a candidate, and it does not open code-review/QA. A retry after an accepted candidate works as before.
    - Backend orchestration: `dispatch create` runs the same brief checks as `dispatch send`, including the link between the candidate and the risk assessment. A brief that send is certain to reject is no longer issued, and the remedy names the needed command.

## v1.1.0 — 28 September 2026 {.ah-release-title}

<p class="ah-release-meta">Added: 2 · <a href="https://github.com/PVMalove/agent-harness-next/releases/tag/v1.1.0">Open on GitHub</a></p>

<p class="ah-release-summary">Highlights: <code>harness uninstall</code> fully removes the harness from a project · the Harness section in <code>harness console</code>: plan and application of the removal (enter UNINSTALL).</p>

??? note "Full notes"

    **Added**

    - `harness uninstall <repo>`: full removal of the harness from a project — `.harness/`, discovery links, seed files, `AGENTS.md`, `CLAUDE.md`, and the harness lines in `.gitignore`. Without `--apply` it prints a plan. `--apply --confirm UNINSTALL` applies it, first copying the files changed by the project and the project data of `.harness/` to `.harness-uninstall-backup/<time>/`. With active orchestration batches, the removal is rejected.
    - `harness console`, Harness section: plan and application of the harness removal (enter `UNINSTALL`).

## v1.0.1 — 28 September 2026 {.ah-release-title}

<p class="ah-release-meta">Added: 1 · Changed: 3 · Fixed: 1 · <a href="https://github.com/PVMalove/agent-harness-next/releases/tag/v1.0.1">Open on GitHub</a></p>

<p class="ah-release-summary">Highlights: harness console, Harness section: the commands update --force-managed-files and update --force-seed-files, a preview of hard cleanup; the soft/hard cleanup commands (plan and application) are grouped after the installation commands · harness console: the background is set only on the screen — the other elements are transparent and separated by frames with titles (the top bar with the menu icon ☰, command "Output", Diagnostics, Reports, report, timeline, QA logs, Help, Repo Map); the selected item of lists, tree, and tabs and the button under the cursor are highlighted with color, without fill · harness console, Dashboard: "Status" lists the health errors and warnings, Repo Map facts are printed one per line; the panel scrolls inside the frame.</p>

??? note "Full notes"

    **Added**

    - `harness console`, Harness section: the commands `update --force-managed-files` and `update --force-seed-files`, a preview of hard cleanup; the soft/hard cleanup commands (plan and application) are grouped after the installation commands.

    **Changed**

    - `harness console`: the background is set only on the screen — the other elements are transparent and separated by frames with titles (the top bar with the menu icon `☰`, command "Output", Diagnostics, Reports, report, timeline, QA logs, Help, Repo Map); the selected item of lists, tree, and tabs and the button under the cursor are highlighted with color, without fill.
    - `harness console`, Dashboard: "Status" lists the health errors and warnings, Repo Map facts are printed one per line; the panel scrolls inside the frame.
    - `harness console`: the "Offline checks" button on the Dashboard and in Diagnostics runs the offline checks again.

    **Fixed**

    - `harness console`: in a low window, the Harness and Orchestration panels no longer overlap — the lists of states and commands scroll inside their frames.

## v1.0.0 — 28 September 2026 {.ah-release-title}

<p class="ah-release-meta">Added: 10 · Changed: 2 · <a href="https://github.com/PVMalove/agent-harness-next/releases/tag/v1.0.0">Open on GitHub</a></p>

<p class="ah-release-summary">Highlights: The first stable release of the portable Agent Harness with capability snapshots, the installation CLI, orchestration, and Repo Map · A GitHub Release with the installation archive, SHA-256, and notes from this section; it is published automatically after a merge into master if the version tag from harness/VERSION does not exist yet · A managed example <code>.harness/orchestration.example.json</code>.</p>

??? note "Full notes"

    **Added**

    - The first stable release of the portable Agent Harness with capability snapshots, the installation CLI, orchestration, and Repo Map.
    - A GitHub Release with the installation archive, SHA-256, and notes from this section. It is published automatically after a merge into `master` if the version tag from `harness/VERSION` does not exist yet.
    - A managed example `.harness/orchestration.example.json` for `backend-orchestration`: it is updated on `init`, `adopt`, and `update`. `init` creates `.harness/orchestration.json` from it once.
    - The orchestration reference `harness/orchestration/README.md`: the structure of the coordinator and all fields of `orchestration.json` with defaults.
    - README: a catalog of all skills with descriptions in Russian, and instructions for `harness health` and `harness console`.
    - Russian descriptions of project agents in `docs/agents/` with a full translation of the manifests and `docs/agents/README.md`.
    - `harness console`: a warm theme in a terracotta and amber palette, the harness mark with an installation description on the main screen, status coloring in Diagnostics, and the `Help` section (also `F1`).
    - `harness console`: in the Harness section — the installation state and pipeline usage; in Orchestration — pipeline statistics and the batch history with a filter by state and a jump to the timeline.
    - The reference `harness-guide.md` is rewritten: navigation by tasks, cheat-sheet tables, examples of commands and output, and eight new Archify diagrams (choosing the installation command, `/to-spec`, `/wayfinder`, `/fast-implement`, `/tdd`, the `status::*` labels, and two end-to-end examples).
    - All 23 diagrams in `docs/diagrams/` pass `archify finalize` (validate, deliver, check, browser-check). The previews are regenerated, the reference images ship next to it in `harness/docs/diagrams/`, and `scripts/verify.py` compares them with `docs/diagrams/previews/`.

    **Changed**

    - The global layer installer is renamed to `bin/install-global.py`: run `python3 bin/install-global.py ...`.
    - The harness reference and the backend orchestration guide are moved from `docs/agents/` into the managed snapshot `.harness/docs/{harness-guide,backend-orchestration}.md` (the source is `harness/docs/`) and are updated by the `harness update` command. The earlier copies in `docs/agents/` of the target project are no longer used and are deleted manually.

</div>
