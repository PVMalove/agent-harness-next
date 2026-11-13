# Test-author

`test-author` is an optional developer helper: it writes **one behavior test** for the next
Red → Green → Refactor step and runs it through the protected runner. Production code, skeletons,
refactoring and orchestration remain with the developer. This is an in-session subagent, not a
separate ledger role. If protection is unavailable, ordinary TDD continues without an unprotected author.

## Enable the test author {#enable}

1. Set [`test_paths` and `test_runner`](#configuration) and add a `test_author` block with runtime,
   model and effort to `.harness/project.json`. When `.harness/orchestration.json` has a developer
   plan, `harness health --fix` adds the block from that plan; it never changes an existing block.
2. Open Claude Code in the repository's main checkout once and accept the trust dialog. Worktrees
   of this repository need no trust of their own.
3. Run `harness health` and follow the step under each `hooks.test_author_*` line with status
   warn: the lines check the `test_author` block, the project root by Git, trust, guard, runner
   and the isolation probe. Rerun health until every line is ok. Guard and probe run project
   scripts, so their lines are skipped until trust is accepted.

```bash {.ah-code-wrap}
harness health --fix
```

## project.json fields {#configuration}

Settings live in `.harness/project.json`. Activation needs `test_paths` and `test_runner`;
the short route also needs explicit `test_author`. All three groups are optional for the project
as a whole. The example uses pytest and an existing `tests` directory: model and effort show a
user choice, **not defaults**. See [project.json](project.md) for the overall contract.

```json {.ah-code-wrap}
{
  "test_paths": ["tests/**"],
  "test_runner": {"command": ["python3", "-m", "pytest", "{test_id}"]},
  "test_author": {"runtime": "claude", "model": "sonnet", "effort": "high"}
}
```

| Field | Contract |
| --- | --- |
| `test_paths` | Non-empty array of unique relative globs without `..`. Author activation accepts only existing literal `<directory>/**` zones; further restrictions are below. |
| `test_runner.command` | Shell-free argv with at least two non-empty string arguments. Exactly one separate `{test_id}`, not first: the runner replaces it with one selected test ID. `harness health` rejects two placeholders, though the draft-07 schema cannot fully express that constraint. |
| `test_runner.build.command` | Required inside authored `build`: non-empty argv without `{test_id}` or NUL. Runs the protected build phase. |
| `test_runner.build.artifact_paths` | Required inside `build`: non-empty array of unique literal `<directory>/**` entries. Directories must already exist and be empty; the build gets fresh writable backing directories, tests read them without write access. The runner does not clear a non-empty directory for you. |
| `test_runner.database.engine` | Required inside `database`: production-engine ID matching `[a-z][a-z0-9_-]{0,63}`. Does not install a DBMS automatically. |
| `test_runner.database.test_ids` | Required non-empty array of unique non-empty strings: `fnmatchcase` selectors. Only a matching test starts the database. |
| `test_runner.database.command` | Required non-empty argv without `{test_id}` or NUL. Starts a separate foreground database server inside the sandbox. |
| `test_runner.database.ready_command` | Required non-empty argv without `{test_id}` or NUL. Checks server readiness; argv does not perform shell substitution. |
| `test_author.runtime` | Required in the short profile: ID matching `[A-Za-z0-9][A-Za-z0-9_-]*`. Currently only `claude` has a protected adapter; other IDs do not turn into another CLI selection. |
| `test_author.model` | Required explicit CLI ID/alias matching `[A-Za-z0-9][A-Za-z0-9._:-]*`, without spaces. No default model. |
| `test_author.effort` | Required: `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max` or `ultra`. Schema validity does not prove that the chosen CLI supports a value. No default. |

Omitting `build` means no separate build phase; omitting `database` means no separate server.
When present, **all** listed fields within each object are required. Source files and `test_paths`
are read-only during the build. The database gets private directories through
`HARNESS_TEST_DATABASE_DIR` and `HARNESS_TEST_DATABASE_SOCKET_DIR`, without TCP or access to host
services. A project wrapper reads these variables itself. Pure domain logic needs no database;
test SQL on the production engine. See the [runner contract](../../hooks/run-test.md).

## Short /fast-implement route {#short-route}

The short route selects runtime/model/effort **from the project's `test_author`**, even when the
current session uses a different model. Before the first test, the developer agrees on the
requirement and seam: the public boundary where behavior is tested. This route adds no
coordinator, architect or independent QA.

At the installed target project's root, inspect selection and protection:

```bash {.ah-code-wrap}
python3 -I -B .harness/health/test_author.py resolve --repo .
python3 -I -B .harness/health/test_author.py preflight --repo .
```

`resolve` shows runtime/model/effort and `source: project`. `preflight` returns one JSON line:
only exact `{"status":"ok"}` enables the author. Exit code 0 alone does not mean ready:
refusal also returns `{"status":"disabled","reason":"…"}`. The isolation probe creates and
removes a temporary sandbox; it does not run an LLM, selected test, build or database.

The route saves the agreed requirement and one scenario in a local prompt file, then uses
the launcher (this command actually starts the agent CLI):

```bash {.ah-code-wrap}
python3 -I -B .harness/health/test_author.py run --repo .   --prompt-file '<local-prompt-file>'
```

Supply an existing task file without secrets. The launcher rechecks protection and passes
the chosen model/effort plus the task through stdin. An unsupported runtime is not substituted.

## Full /implement route {#full-route}

The author inherits `resolved_runtime`, `resolved_model` and `resolved_effort` from the
**approved developer brief**. The short profile and later orchestration changes do not alter
that selection. `.claude/agents/test-author.md` uses `model: inherit` with no effort override;
the developer calls `Agent(test-author)` without model/effort overrides.

For an external developer, the harness and protection must be installed **in the worker
worktree**. A worktree of a trusted repository needs no trust dialog of its own; if the main
checkout is not trusted, open it in Claude Code and accept trust yourself. Do not copy main
checkout orchestration state there. In the developer session running in that worktree:

```bash {.ah-code-wrap}
python3 -I -B .harness/health/test_author.py resolve --repo . \
  --brief '<approved-developer-brief.json>'
python3 -I -B .harness/health/test_author.py preflight --repo . \
  --brief '<approved-developer-brief.json>'
```

Selection source is `developer`. The approved brief must allow `Agent(test-author)` or `Agent`.
For an existing tool policy, check `tool_policy.roles.developer` while retaining other permissions;
an old approval cannot be widened. Changes need new propose/approval. See [role assignments](orchestration/roles.md).

The author writes only within the worker test zone **and** brief scope. Runner logs are shared
in linked worktrees: `<main>/.harness/.sandboxes/runs/isolated-test-<run_id>/log.txt`. The developer
passes this evidence path, rather than permission to write main-checkout production code.

Main-checkout protection with a separate worker worktree answers `checkout_mismatch`, so an
in-process developer calls the author through its worktree's launcher:
`python3 -I -B <worker_worktree>/.harness/health/test_author.py run --repo <worker_worktree> --brief <brief> --prompt-file <file>`.
A refusal keeps ordinary TDD with its reason. Refusal creates no new dispatch, blocker or ledger
record. The complete [test-author contract](../../agents/test-author.md) describes the cycle
and independent test expectations.

## Activation conditions {#activation}

- Linux, bubblewrap 0.9.0+ and unprivileged user namespaces. Windows/macOS receive
  `isolation_unavailable`. The checkout cannot be under `/tmp`, `/run`, `/dev` or `/proc`.
- Installed agent, executable scoped guard and runner. Bash, Python and the chosen test/build/DB
  tools must be available. An argv entry alone does not establish support for unverified tools.
- `test_paths` identifies existing literal directories. No symlinks along the path, files with
  multiple hard links or nested zones. The first segment is not `.git`, `.harness`, `.claude`,
  `.agents` or `.codex`; other segments contain no `*?[]{}` or backslash. For example, `tests/*.py`
  can pass the schema but not author activation.
- The checkout is the root of its own Git work tree; `CLAUDE_PROJECT_DIR` is optional but, when
  set, matches that root. Claude Code is not running with `CLAUDE_CODE_SIMPLE=1` or
  `CLAUDE_CODE_SAFE_MODE=1`. A human accepted trust for **this checkout or the main checkout of its
  repository**. Do not repair this by writing an auth/trust file; open the project and accept the
  dialog.
- The chosen runtime has a protected adapter. Currently that is Claude Code; the harness pins
  no minimum CLI version. Preflight checks agent/hook statically; live firing is confirmed separately.

The guard confines `Write`/`Edit` to the test zone and `Bash` to one `run-test.sh <test-id>` call
(including through trusted system Bash). Shell metacharacters, `--probe` and extra author
commands are refused. `--probe` is for preflight/developer diagnostics, not bypassing the guard.

## Preflight refusal reasons {#refusals}

Checks stop at the first refusal. Correct the cause and retry; do not disable the guard to get
`ok`. This table covers executor selection and protected-adapter checks together.

| Code | Cause → action |
| --- | --- |
| `test_author_missing` | No short profile → configure runtime/model/effort for the short route; supply the approved brief for the full route. |
| `test_author_config_invalid` | Invalid profile/brief or a stale fixed model/effort in the agent → check the selected source/template, without substituting another runtime. Replace a local seed only after reviewing its diff. |
| `runtime_unsupported` | No protected runtime adapter → ordinary TDD; another CLI is not enabled automatically. |
| `checkout_mismatch` | Wrong checkout → run protection in the worker with its brief. |
| `project_dir_mismatch` | The passed `CLAUDE_PROJECT_DIR` is not the checkout's Git root → call the author from that worktree's session or through its launcher; do not spoof identity through an environment variable. |
| `project_untrusted` | The checkout is not a Git root, or neither it nor the repository's main checkout is trusted → open the main checkout in Claude Code and accept trust. |
| `claude_code_unsupported` | The CLI mode disables required hooks → use a supported environment, without bypassing the check. |
| `agent_missing` | Missing/invalid `.claude/agents/test-author.md` → check installation in the correct checkout. |
| `scoped_hook_unsupported` | Expected scoped PreToolUse hook absent in frontmatter → compare with the current template, retaining protection. |
| `test_paths_missing` | No test zones → configure existing test directories. |
| `test_runner_missing` | No runner configuration → provide verified single-test argv. |
| `config_invalid` | Invalid runner/zone fields → correct configuration against the contract. |
| `write_zone_rejected` | Unsupported glob, symlink, hard link or overlapping zones → select valid directories without widening into production. |
| `guard_hook_unavailable` | Guard missing/not executable/invalid response → inspect installed file and Python. This does not prove live hook firing. |
| `isolation_unavailable` | Sandbox cannot be confirmed → check Linux, bubblewrap, namespaces and checkout location; otherwise use ordinary TDD. |
| `runner_unavailable` | Runner or required interpreter absent/broken → check installed files and PATH. |
| `selector_unavailable` | Protected adapter cannot invoke the selector → check installed `.harness/health/test_author.py` integrity. |
| `orchestration_unavailable` | Planned diagnostics cannot load orchestration → check the installed backend; this does not select a short profile for the user. |
| `preflight_failed` | Unknown/invalid/overlong response or preflight failure → inspect installed protection; arbitrary text is not `ok`. |

`agent_tool_unavailable` is the developer's decision when the brief lacks an `Agent` tool,
rather than a general-preflight JSON reason. Launcher-stage refusals include `runtime_unavailable`,
`prompt_missing`, `prompt_unavailable` and `author_unavailable`: check the selected CLI, task file
and process completion. They never authorize an unprotected launch.

## Live check {#live-check}

`harness health .` shows `hooks.test_author`, selected runtime/model/effort and source. It diagnoses
the developer plan with a `planned` marker, falling back to the short profile when no plan exists.
This does not replace an approved brief. Missing opt-in is skipped; an unavailable optional author
warns without breaking the ordinary route. Health runs no LLM, test, build or database.

The **harness source repository** provides a separate live check requiring Claude Code login
and spending quota; agree on that action before running it:

```bash {.ah-code-wrap}
make test-author-probe
```

It uses runtime/model/effort from the developer plan and checks the guard, behavioral Red,
external developer calling the author in a worker and Green of the unchanged test. Ordinary
verify/CI do not run it. `test-author-probe-*.json` files remain in shared
`.harness/.sandboxes/reports/`: phase, checkout, exit code, time and runtime-reported usage/cost.
Unknown metrics remain `null`; limits are not usage, and subscription quota share is not derived from USD.

## Limits and ordinary TDD {#limits}

This release verifies Python tests through unittest/pytest. It does not support
`native/harness-runtime/crates/*/tests` Rust tests through this solution: configurable argv in
a schema does not prove stack support. Required Rust QA commands remain in force.

Import/compilation, fixture or build errors (`build_failed`, `build_timeout`) and an unavailable
database (`database_unavailable`) are not behavioral Red. `needs_skeleton` asks the developer
for types/signatures only; `contract_gap` requires clarification. Never weaken expectations for
Green. Three consecutive failed author calls for one test use the ordinary blocker route.
Activation refusal instead leaves ordinary TDD without new blocker/ledger state.

## Configure with an agent {#agent-setup}

??? quote ah-skill-text "Agent prompt: short test-author route"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Read the test-author guide and current test_paths/test_runner/test_author. Ask which explicit
    runtime/model/effort the short route should use; no defaults or runtime substitution.
    Check supported protected adapter, literal test zones and single-test argv. Use resolve and
    preflight for diagnostics only after explaining the temporary isolation probe. Do not run an
    author/test to configure it; ordinary TDD remains available when protection is unavailable.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Agent prompt: full test-author route"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Read the approved developer brief in its worker checkout. Inherit resolved_runtime/model/effort,
    never the short profile or later live orchestration settings. Confirm worker-local installation,
    user trust of the worker or its repository's main checkout and approved Agent(test-author)
    permission; never spoof trust or widen
    approved tools. Keep model: inherit without effort override. Use preflight with the brief in
    the correct checkout; refusal leaves ordinary TDD, not an unprotected or substituted author.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Agent prompt: live test-author verification"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Explain static hooks.test_author health/preflight versus actual scoped-hook execution.
    In the harness source, make test-author-probe needs login and spends quota. Ask explicitly
    before running it; do not select a cheaper model instead of the developer plan.
    Inspect sanitized test-author-probe reports only, never transcripts or credentials. Missing usage
    is null; a limit is not spent quota. If live execution is not authorized, report it unverified.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```
