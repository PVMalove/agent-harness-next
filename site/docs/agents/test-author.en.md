# Test-author

## 1. Purpose

`test-author` is an optional in-session developer subagent for the next behavior test of the
Red → Green → Refactor cycle. It writes exactly one test and runs it through
`.claude/hooks/run-test.sh`. The developer keeps the production code, the skeleton, and the orchestration.

The subagent is available only in Claude Code, and only after a successful
`.claude/hooks/test-author-preflight.sh`. The command returns the single line `{"status":"ok"}`
when `test_paths`, `test_runner`, process isolation, and the scoped guard are confirmed. On any
refusal it returns `{"status":"disabled","reason":"<sanitized reason>"}`, and the
developer continues the usual route.

## 2. Configuration

Both optional settings go in `.harness/project.json`:

```json {.ah-code-wrap}
"test_paths": ["tests/**"],
"test_runner": {"command": ["python3", "-m", "pytest", "{test_id}"]}
```

`test_paths` is a non-empty list of unique relative glob patterns without `..` segments.
The schema and `harness health` accept any such glob, but the test author activates only with write zones
of the form `<directory>/**`: the other segments are literal (no `*?[]{}` and no `\`), the first segment is not
`.git`, `.harness`, `.claude`, `.agents`, or `.codex`, the directory exists, there is no
symlink on the path to it, there are no files with several hard links inside, and the zones are not nested in each other. Otherwise
preflight answers `write_zone_rejected`, for example for `tests/*.py`.
`test_runner.command` is an argv without a shell, with exactly one `{test_id}` argument, which is not
the first one. The schema, the validator, and `harness health` use one contract. Missing fields are not
an error, but they turn the test author off.

The full `/implement` route inherits `resolved_runtime`, `resolved_model` and `resolved_effort`
from the approved developer brief. Pass `--brief <path>` to general preflight. Later orchestration
changes and the project short profile do not alter that approved choice. The native
`Agent(test-author)` template uses `model: inherit` with no effort override; the developer calls
it without model/effort overrides. A stale local fixed model or effort yields
`test_author_config_invalid`. Review the template diff before replacing the seed with
`harness update . --force-seed-file .claude/agents/test-author.md`.

The short `/fast-implement` route uses a separate explicit profile in `.harness/project.json`:

```json {.ah-code-wrap}
"test_author": {"runtime": "claude", "model": "sonnet", "effort": "high"}
```

This is an example user choice, not defaults. All three fields are required inside the profile.
Without it, the short route returns `test_author_missing`. Invalid developer brief fields give
`test_author_config_invalid` on the full route, without falling back to the project profile.
`resolve --repo . [--brief <path>]` shows the selected fields and source.

The short route saves the requirement and one scenario in a local prompt file, then calls:

```sh {.ah-code-wrap}
python3 -I -B .harness/health/test_author.py run --repo . --prompt-file '<prompt-file>'
```

The launcher rechecks the protected adapter, passes exact model/effort and sends the task through
stdin, including when the current session uses a different model. A runtime without a protected
adapter returns `runtime_unsupported`; it is never replaced by another CLI. Currently only Claude
Code has that adapter; `.claude` paths below refer to its guard and runner, not an implied executor.

## 3. Protection

The frontmatter of the installed `.claude/agents/test-author.md` attaches
`.claude/hooks/test-author-guard.py` to this subagent only, for `Write`, `Edit`, and `Bash`.

- `Write` and `Edit` pass only after path normalization and only inside `test_paths`. A symlink
  that leads outside the test zone is rejected.
- `Bash` allows only one call of `.claude/hooks/run-test.sh <test-id>` (an
  equivalent call through the trusted system `bash` is allowed). Shell metacharacters, `--probe`,
  extra arguments, and other commands are rejected.
- A refusal is soft: the hook prints JSON with the reason, does not change the dispatch or the ledger, and exits with code 0.
  Other subagents do not get this protection and do not change their route.

Preflight checks the conditions and, on the first violation, answers `disabled` with one
fixed reason:

| Check | Refusal reason |
| --- | --- |
| The optional `--worktree <path>` names the same checkout where preflight lives | `checkout_mismatch` |
| The checkout where preflight lives is the root of its own Git work tree (`git rev-parse --show-toplevel`) | `project_untrusted` |
| `CLAUDE_PROJECT_DIR`, when passed, matches that Git root | `project_dir_mismatch` |
| Claude Code is not started with `CLAUDE_CODE_SIMPLE=1` or `CLAUDE_CODE_SAFE_MODE=1` | `claude_code_unsupported` |
| The user accepted the trust dialog for this checkout or for the main checkout of its repository | `project_untrusted` |
| The agent `test-author.md` is installed | `agent_missing` |
| The scoped `PreToolUse` hook is enabled in the agent | `scoped_hook_unsupported` |
| `test_paths` and `test_runner` are set, and the write zones are valid | `test_paths_missing`, `test_runner_missing`, `config_invalid`, `write_zone_rejected` |
| The file `test-author-guard.py` is executable and answers with JSON | `guard_hook_unavailable` |
| `run-test.sh --probe` confirms isolation | `isolation_unavailable`, `runner_unavailable` |

Preflight takes the project root from Git, so neither `export CLAUDE_PROJECT_DIR` nor a root
entry in settings is needed. A `CLAUDE_PROJECT_DIR` passed by Claude Code is only compared with
the Git root.

Trust is checked against an entry in `~/.claude.json` (or `$CLAUDE_CONFIG_DIR/.claude.json`):
`hasTrustDialogAccepted: true` must be set for the exact checkout path or for the repository's
main checkout when the checkout is its linked worktree from `git worktree list`. The native mode
`claude --print` skips the trust dialog, so preflight checks the decision itself. A new worktree
of a trusted repository needs no dialog of its own. Trust given only to a parent directory does
not count: preflight answers `project_untrusted`, a safe refusal. Open the main checkout in
Claude Code and accept the dialog (ADR 0033).

The agent, hook, and guard checks are static: preflight does not start Claude Code and does not prove
that the hook will fire in a live session. So `guard_hook_unavailable` means only that the
executable guard is missing or its answer is broken. The harness's own check on a real Claude Code
confirms that the scoped hook really fires; that check is not part of the installed project. If the agent
or the hook is missing, Claude Code runs in a mode that turns hooks off, the project is not
trusted, or isolation is unavailable, test-author does not start without protection.

## 4. Call contract

While preflight returns `{"status":"ok"}`, the developer calls test-author before each implementation
step. The developer passes the requirement and the seam from the
architect brief, the public signatures, the existing fixtures, and one scenario. A proposed
algorithm or implementation fragment does not become a basis for the expectation. The developer does not invent a seam that is not agreed
in the brief, and escalates it as a blocker in the usual way. Test-author reads
the minimal relevant files, writes one test only in `test_paths`, runs the selected
test through the runner, and briefly returns, in English:

1. `status`: `red`, `needs_skeleton`, or `contract_gap`;
2. the requirement and the scenario;
3. the input data and the independent source of the expectation;
4. the test identifier;
5. for `red`, the Red evidence: the sanitized runner JSON and, in a few lines, the failed
   assertion, the expectation, and the actual result. The JSON contains only fixed keys, so the author takes these
   three facts from the run's `log.txt` (the directory comes from `run_id`).

If the runner refused or the test turned out Green, the subagent reports the fact and stops. It does not
create a manifest, dispatch, brief/report, approval, or ledger record.

## 5. The Red → Green → Refactor cycle

The cycle is prose for the developer, not a new role, state, or ledger record.

1. The developer checks the expectation against the requirement and the source before implementation. An accepted expectation is not
   weakened to get Green. It may be corrected only when the contract changes for a good reason,
   with a new call to the author and a new check.
2. `red` means move to implementation. `needs_skeleton` means the developer writes only types and signatures without
   logic, and the author is run again. `contract_gap` means the developer clarifies the requirement from the brief
   or escalates it; guessing the contract is not allowed.
3. A compilation or import error, a fixture error, and an environment error are not a behavior Red,
   whatever `status` the author reports. A test that is Green at once goes back to the author explicitly and does not count as
   a successful cycle.
4. After a confirmed Red, the developer writes the minimal implementation until Green, refactors on
   Green, and only then requests the next test.
5. After three failed calls to the author in a row for one test, the developer follows the usual blocker path.
   A guard refusal counts as one failed call, and a rejected call is not reworded.
   A local retry of the author and a separate guard refusal do not create a dispatch or ledger state and do not
   bypass the `/implement` recovery rules.
   Independent QA, its role, and the ledger do not change.

The optional `test_runner.build` and `test_runner.database` set up the build and a separate test
database (see section 6). Test-author does not change artifacts: its
`Write`/`Edit` stay limited to `test_paths`. If protection is unavailable, the author is turned off.

The runner starts the database only for the matching `test_runner.database.test_ids`; pure domain
logic needs no server. Check SQL, rollback, and constraints on the production engine.
The refusals `build_failed`, `build_timeout`, and `database_unavailable` are not a behavior Red.

`--probe` checks the settings and mounts of both phases, but does not start the build, the database server,
or the selected test. A refusal of the settings or mounts is stored in preflight as `disabled`
with a sanitized reason, and the developer continues the usual route without the test author. The readiness
of a specific database is checked only for the selected SQL test; its refusal is not counted as Red.

## 6. The short `/fast-implement` route

`/fast-implement` uses the same test author and the same cycle from section 5, but without the steps of
coordinator, architect, and independent QA: the developer session runs the cycle itself from the ticket to the push.
Only the origin of the seam differs: it does not come from the architect brief, but is agreed with
the developer before the first test. The skill names the requirement, the seam, the public signatures, and the existing
fixtures, stops until the developer answers, and does not write a test on an unagreed seam.
The handoff to the author, the expectation check, the skeleton, the ban on weakening an accepted expectation, and the limit of three
failed calls in a row are the same as in the full route. Local retries do not create a dispatch or
ledger state.

**Opt-in.** The test author is off while `.harness/project.json` has no `test_paths` and
`test_runner`. A new project gets them with the flags `harness init --test-path` and
`--test-runner-command`. An old project without these fields does not change: `/fast-implement` follows the usual
`/tdd`. To turn the author on in an old project, add both fields by hand and run
`harness health`.

**Protected environment.** The author's tests run only through `.claude/hooks/run-test.sh`. The optional
fields `test_runner.build` (`command` and `artifact_paths`) and `test_runner.database` (`engine`,
`test_ids`, `command`, `ready_command`) prepare fresh artifacts and a separate test database inside the
sandbox. They are set with the flags `--test-build-command`, `--test-artifact-path`, `--test-database-engine`,
`--test-database-test-id`, `--test-database-command`, and `--test-database-ready-command` together with
`--test-runner-command`. The build writes only into pre-created empty artifact directories, the test
reads them without write access, and the database starts only for the matching `test_ids`. Pure domain logic
needs no database.

**Supported versions and environments.**

- Claude Code only; Codex is not supported. The harness does not pin a minimum Claude Code version:
  preflight statically checks the agent, the scoped hook, and the guard, and the harness's own check
  (`make test-author-probe`, which needs `claude` and a login) confirms that the hook fires in a live session.
- Linux only, with bubblewrap 0.9.0+ and unprivileged user namespaces. On Windows and macOS
  the runner answers `isolation_unavailable`, and preflight turns the author off.
- The checkout must not live in `/tmp`, `/run`, `/dev`, or `/proc`. The build needs a compiler or the
  tool set in `test_runner.build.command`; SQL tests need the tools of the chosen DBMS
  (in the harness's checks: `postgres`, `initdb`, `psql`, and `pg_isready` in `PATH`). Without them only
  the matching run refuses, not the whole project.
- The hook needs `python3` (or `python`) in `PATH`, and the project must be accepted in the Claude Code
  trust dialog.

**Fallback to the usual route.** If preflight answered anything other than `{"status":"ok"}`, if the hook is missing or
failed, or if isolation is unavailable, `/fast-implement` continues with the usual `/tdd` in the same session, names the
sanitized reason to the developer in one line, and does not start an unprotected author. This
outcome adds no coordinator, architect, or QA steps and does not change the ledger.

## 7. The full `/implement` route

The author works beside an external developer in its worker worktree, using runtime/model/effort
from the developer brief. The supported adapter starts the developer in that checkout, so the
runtime, scoped hook and runner refer to the same code. Install the harness in the worker checkout
and enable `test_paths` and `test_runner` there; do not copy main-checkout orchestration state.
A worktree of a trusted repository needs no trust dialog of its own; if the main checkout is not
trusted, open it in Claude Code and accept the dialog. Neither the installer, developer nor a
headless launch makes that trust decision for you.

The external developer runs general preflight with `--repo <worker_worktree> --brief <brief path>`.
For the protected Claude adapter this is `.claude/hooks/test-author-preflight.sh --worktree
<worker_worktree> --brief <brief path>`. Only exact `{"status":"ok"}` enables the next step.
The approved brief must also allow `Agent(test-author)` or `Agent`; otherwise the developer's
reason is `agent_tool_unavailable`. The new orchestration template grants the named permission
only to developer. Existing projects with a tool policy enable it explicitly in
`tool_policy.roles.developer`, retaining other tools. Explicit restrictions are never widened
automatically; the tool list is digest-bound before approval under ADR 0024.

The author writes within the worker's `test_paths` and uses its runner. The developer passes one
specific test path within brief scope and the log root from the adapter prompt:
`<main>/.harness/.sandboxes/runs/`. These logs are shared in linked worktrees; `run_id` points to
`isolated-test-<run_id>/log.txt` under that root. The adapter grants access to evidence while the
scoped guard retains its write and Bash limits. Main-checkout code, tests and Git status stay
unchanged; shared runtime logs remain in its ignored sandbox.

Main-checkout preflight with a separate worker's `--worktree` answers `checkout_mismatch`: its
guard and runner serve only the main checkout. An in-process developer therefore calls the author
through its worktree's launcher:
`python3 -I -B <worker_worktree>/.harness/health/test_author.py run --repo <worker_worktree> --brief <brief path> --prompt-file <file>`.
The launcher checks the worker's preflight and starts the author with that worktree's guard and
runner; the brief permission rule is the same. Any preflight refusal or unavailable
author-calling tool leaves ordinary TDD in the worker, with its reason and without a blocker or
new ledger record. Runtime selection comes from the developer; lack of a
protected adapter retains ordinary TDD, without substituting an executor.

This release verifies Python tests through unittest and pytest. Rust tests in
`native/harness-runtime/crates/*/tests` are not supported by this solution: no write zones and
separate runner were added for them. Configurable argv is not itself restricted to Python, but
it does not establish another stack's support. Ordinary Rust QA remains required for Rust changes.

## 8. Diagnostics and live check

`harness health` reports `hooks.test_author`: preflight readiness or a sanitized refusal, selected
runtime/model/effort and source. Health uses the orchestration developer plan, marked `planned`,
and otherwise the project short profile. Planned readiness does not replace an approved brief.
For the supported Claude adapter, Health checks trust by the preflight rule: the exact checkout
path or the main checkout that lists it in `git worktree list`. Without opt-in the check is
skipped with a reason; an unavailable optional author warns while ordinary development works.
Health prints each author condition — the `test_author` block, the project root by Git, trust,
guard, runner and probe — as its own `hooks.test_author_*` line, and a refused line prints its fix
step. `harness health --fix` adds a missing `test_author` block from the developer plan. The
[test-author settings](../getting-started/settings/test-author.md#enable) describe how to enable
the author.

Health runs no Claude process, selected test, build or database and changes no trust. The isolation
probe creates and removes a temporary sandbox under shared `runs/`. Static `preflight: ok` does
not prove the scoped hook fires live. `make test-author-probe` checks that: it needs Claude Code
login and quota. It uses runtime/model/effort from the source project's developer plan, not a
separate cheap model. An unsupported runtime adapter fails explicitly. The supported probe
confirms the guard, behavioral Red and an external developer calling the author in a worker
worktree; a fixture developer then proves Green of the unchanged test.

Each CLI call leaves a sanitized `test-author-probe-*.json` in shared
`.harness/.sandboxes/reports/`: checkout, stage, exit code, time, runtime-reported usage/cost and a
separate limit. Unknown metrics stay `null`; a limit is not usage. Reports survive clean-room
project removal, without full transcripts or credentials. Subscription quota share may be absent
from runtime data and is never calculated from USD.
