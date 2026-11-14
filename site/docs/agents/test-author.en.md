# Test-author

## 1. Purpose

`test-author` is an optional in-session developer subagent for the next behavior test of the
Red → Green → Refactor cycle. It writes exactly one test and runs it through
`.claude/hooks/run-test.sh`. The developer keeps the production code, the skeleton, and the
orchestration.

The executor is selected from the configuration before the check of the protected adapter. The
common command `python3 -I -B .harness/health/test_author.py preflight --repo .` returns the single
line `{"status":"ok"}` when `test_paths`, `test_runner`, process isolation, and the scoped guard are
confirmed. On any refusal it returns `{"status":"disabled","reason":"<sanitized reason>"}`, and the
developer continues the usual route.

## 2. Configuration

`.harness/project.json` holds the optional settings of the test zone and the runner:

```json {.ah-code-wrap}
"test_paths": ["tests/**"],
"test_runner": {"command": ["python3", "-m", "pytest", "{test_id}"]}
```

`test_paths` is a non-empty list of unique relative glob patterns without `..` segments. The schema
and `harness health` accept any such glob, but the test author activates only with write zones of
the form `<directory>/**`: the other segments are literal (no `*?[]{}` and no `\`), the first
segment is not `.git`, `.harness`, `.claude`, `.agents`, or `.codex`, the directory exists, no
symlink is on the path to it, no file inside has several hard links, and the zones are not nested
in each other. Otherwise preflight answers `write_zone_rejected`, for example for `tests/*.py`.
`test_runner.command` is an argv without a shell, with exactly one `{test_id}` argument, which is
not the first one. The schema, the validator, and `harness health` use one contract. Missing fields
are not an error, but they turn the test author off.

The full `/implement` route inherits `resolved_runtime`, `resolved_model` and `resolved_effort` from
the approved developer brief. Pass `--brief <path>` to the common preflight. Later orchestration
changes and the short profile of the project do not change that approved choice. The native
`Agent(test-author)` template sets no `model` and no effort; the developer calls it without
model/effort overrides. A stale local fixed model or effort gives `test_author_config_invalid`.
Review the template diff before you replace the seed with
`harness update . --force-seed-file .claude/agents/test-author.md`, which restores the inheritance.

The short `/fast-implement` route reads a separate explicit profile in `.harness/project.json`:

```json {.ah-code-wrap}
"test_author": {"runtime": "<runtime>", "model": "<model>", "effort": "<effort>"}
```

The values are the choice of the user, not defaults. All three fields are required inside the
profile. Without the profile the short route gets `test_author_missing`. Without valid brief fields
the full route gets `test_author_config_invalid`, without a fallback to the project profile.
`resolve --repo . [--brief <path>]` shows the selected fields and their source.

The short route saves the requirement and one scenario in a local prompt file, then calls:

```sh {.ah-code-wrap}
python3 -I -B .harness/health/test_author.py run --repo . --prompt-file '<prompt-file>'
```

The launcher checks the protected adapter again, passes the exact model and effort, and sends the
task through stdin. It does this also when the current session uses another model. A runtime
without a protected adapter gets `runtime_unsupported`; another CLI never replaces it. Only Claude
Code has such an adapter now; the `.claude` paths below refer to its guard and runner, not to the
selection of the executor. To switch the author to Claude Code, add `claude` with `model` and
`effort` to `assignment_plans.developer.runtimes` of `.harness/orchestration.json`. When the plan
has several runtimes, select `claude` in `assignment_plans.developer.default_runtime`. Without a
developer plan, `test_author.runtime` of `.harness/project.json` sets the runtime.

## 3. Protection

The frontmatter of the installed `.claude/agents/test-author.md` attaches
`.claude/hooks/test-author-guard.py` to this subagent only, for `Write`, `Edit`, and `Bash`.

- `Write` and `Edit` pass only after path normalization and only inside `test_paths`. A symlink
  that leads out of the test zone is refused.
- `Bash` allows only one call of `.claude/hooks/run-test.sh <test-id>` (an equivalent call through
  the trusted system `bash` is allowed). Shell metacharacters, `--probe`, extra arguments, and other
  commands are refused.
- A refusal is soft: the hook prints JSON with the reason, does not change the dispatch or the
  ledger, and exits with code 0. Other subagents do not get this protection and do not change their
  route.

Preflight checks the conditions and, at the first violation, answers `disabled` with one fixed
reason:

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
| Runtime, model and effort are selected from the developer brief or the short profile of the project | `test_author_missing`, `test_author_config_invalid` |
| The selected runtime has a protected adapter | `runtime_unsupported` |
| The file `test-author-guard.py` is executable and answers with JSON | `guard_hook_unavailable` |
| `run-test.sh --probe` confirms isolation | `isolation_unavailable`, `runner_unavailable` |

Preflight takes the project root from Git, so neither `export CLAUDE_PROJECT_DIR` nor a root entry
in the settings is needed. A `CLAUDE_PROJECT_DIR` that Claude Code passes is only compared with the
Git root.

Trust is checked against an entry in `~/.claude.json` (or `$CLAUDE_CONFIG_DIR/.claude.json`):
`hasTrustDialogAccepted: true` must be set for the exact checkout path, or for the main checkout of
the repository when the checkout is its linked worktree from `git worktree list`. The native mode
`claude --print` skips the trust dialog, so preflight checks the decision itself. A new worktree of
a trusted repository needs no dialog of its own. Trust that only a parent directory has does not
count: preflight answers `project_untrusted`, a safe refusal. Open the main checkout in Claude Code
and accept the dialog (ADR 0033).

The checks of the agent, the hook, and the guard are static: preflight does not start Claude Code
and does not prove that the hook fires in a live session. So `guard_hook_unavailable` means only
that the executable guard is missing or its answer is broken. The own check of the harness on a
real Claude Code confirms that the scoped hook fires; that check is not part of the installed
project. If the agent or the hook is missing, Claude Code runs in a mode that turns hooks off, the
project is not trusted, or isolation is unavailable, test-author does not start without protection.

## 4. Call contract

While preflight returns `{"status":"ok"}`, the developer calls test-author before each
implementation step. The developer passes the requirement and the seam from the architect brief,
the public signatures, the existing fixtures, and one scenario. A proposed algorithm or a fragment
of the implementation never becomes the basis of the expectation. The developer does not invent a
seam that the brief did not agree, and escalates it as a blocker in the usual way. Test-author reads
the minimal relevant files, writes one test only in `test_paths`, runs the selected test through
the runner, and briefly returns, in English:

1. `status`: `red`, `needs_skeleton`, or `contract_gap`;
2. the requirement and the scenario;
3. the input data and the independent source of the expectation;
4. the test identifier;
5. for `red`, the Red evidence: the sanitized runner JSON and, in a few lines, the failed
   assertion, the expectation, and the actual result. The JSON holds only fixed keys, so the author
   takes these three facts from `log.txt` of the run (the directory comes from `run_id`).

If the runner refused or the test is Green, the subagent reports the fact and stops. It does not
create a manifest, a dispatch, a brief or report, an approval, or a ledger record.

## 5. The Red → Green → Refactor cycle

The cycle is guidance for the developer, not a new role, state, or ledger record.

1. The developer checks the expectation against the requirement and the source before the
   implementation. An accepted expectation is not weakened to get Green. It may be corrected only
   when the contract changes for a good reason, with a new call to the author and a new check.
2. `red` means: go to the implementation. `needs_skeleton` means: the developer writes only types
   and signatures without logic, and the author runs again. `contract_gap` means: the developer
   clarifies the requirement from the brief or escalates it; guessing the contract is not allowed.
3. A compilation or import error, a fixture error, and an environment error are not a behavior Red,
   whatever `status` the author reports. A test that is Green at once goes back to the author
   explicitly and does not count as a successful cycle.
4. After a confirmed Red, the developer writes the minimal implementation until Green, refactors on
   Green, and only then requests the next test.
5. After three failed calls to the author in a row for one test, the developer follows the usual
   blocker path. A guard refusal counts as one failed call, and a refused call is not reworded. A
   local retry of the author and a separate guard refusal do not create a dispatch or ledger state
   and do not bypass the recovery rules of `/implement`. Independent QA, its role, and the ledger do
   not change.

The optional `test_runner.build` and `test_runner.database` set up the build and a separate test
database (see section 6). Test-author does not change artifacts: its `Write` and `Edit` stay in
`test_paths`. If protection is unavailable, the author is turned off.

The runner starts the database only for the matching `test_runner.database.test_ids`; pure domain
logic needs no server. Check SQL, rollback, and constraints on the production engine. The refusals
`build_failed`, `build_timeout`, and `database_unavailable` are not a behavior Red.

`--probe` checks the settings and the mounts of both phases, but does not start the build, the
database server, or the selected test. Preflight stores a refusal of the settings or the mounts as
`disabled` with a sanitized reason, and the developer continues the usual route without the test
author. The readiness of a specific database is checked only for the selected SQL test; its refusal
is not a Red.

## 6. The short `/fast-implement` route

`/fast-implement` uses the same test author and the same cycle from section 5, but without the steps
of the coordinator, the architect, and independent QA: the developer session runs the cycle itself,
from the ticket to the push. Only the origin of the seam is different: it does not come from the
architect brief, but is agreed with the developer before the first test. The skill names the
requirement, the seam, the public signatures, and the existing fixtures, stops until the developer
answers, and does not write a test on a seam that is not agreed. The handoff to the author, the
check of the expectation, the skeleton, the ban on weakening an accepted expectation, and the limit
of three failed calls in a row are the same as in the full route. Local retries do not create a
dispatch or ledger state.

**Opt-in.** The test author is off while `.harness/project.json` has no `test_paths` and
`test_runner`. A new project gets them with the flags `harness init --test-path` and
`--test-runner-command`. An old project without these fields does not change: `/fast-implement`
follows the usual `/tdd`. To turn the author on in an old project, add both fields by hand and run
`harness health`.

**Protected environment.** The tests of the author run only through `.claude/hooks/run-test.sh`.
The optional fields `test_runner.build` (`command` and `artifact_paths`) and `test_runner.database`
(`engine`, `test_ids`, `command`, `ready_command`) prepare fresh artifacts and a separate test
database inside the sandbox. They are set with the flags `--test-build-command`,
`--test-artifact-path`, `--test-database-engine`, `--test-database-test-id`,
`--test-database-command`, and `--test-database-ready-command`, together with
`--test-runner-command`. The build writes only into empty artifact directories created in advance,
the test reads them without write access, and the database starts only for the matching
`test_ids`. Pure domain logic needs no database.

**Supported versions and environments.**

- Only Claude Code has a protected adapter now; a selection of Codex or another runtime stays in
  the diagnostics and gives `runtime_unsupported`. The harness does not pin a minimum Claude Code
  version: preflight statically checks the agent, the scoped hook, and the guard, and the own check
  of the harness (`make test-author-probe`, which needs `claude` and a login) confirms that the hook
  fires in a live session.
- Linux only, with bubblewrap 0.9.0+ and unprivileged user namespaces. On Windows and macOS the
  runner answers `isolation_unavailable`, and preflight turns the author off.
- The checkout must not be in `/tmp`, `/run`, `/dev`, or `/proc`. The build needs a compiler or the
  tools of `test_runner.build.command`; SQL tests need the tools of the selected DBMS (in the checks
  of the harness: `postgres`, `initdb`, `psql`, and `pg_isready` in `PATH`). Without them only the
  matching run refuses, not the whole project.
- The hook needs `python3` (or `python`) in `PATH`, and the project must be accepted in the trust
  dialog of Claude Code.

**Fallback to the usual route.** If preflight answered anything other than `{"status":"ok"}`, the
hook is missing or failed, or isolation is unavailable, `/fast-implement` continues with the usual
`/tdd` in the same session, names the sanitized reason to the developer in one line, and does not
start an unprotected author. This outcome adds no steps of the coordinator, the architect, or QA and
does not change the ledger.

## 7. The full `/implement` route

Option A of task #971 was selected: the author works beside an external developer in its worker
worktree, with the runtime, model and effort of the developer brief. The supported adapter starts
the developer in that checkout, so the runtime, the scoped hook and the runner refer to the same
code. Install the harness in the worker checkout and enable `test_paths` and `test_runner` there; do
not copy the orchestration state of the main checkout. A worktree of a trusted repository needs no
trust dialog of its own; if the main checkout is not trusted, open it in Claude Code and accept the
dialog. Neither the installer, the developer nor a headless launch makes that trust decision for
you.

The external developer runs the common preflight with `--repo <worker_worktree> --brief <brief
path>`. For the protected Claude adapter this is `.claude/hooks/test-author-preflight.sh --worktree
<worker_worktree> --brief <brief path>`. Only the exact `{"status":"ok"}` enables the next step. The
approved brief must also allow `Agent(test-author)` or `Agent`; otherwise the reason of the
developer is `agent_tool_unavailable`. The new orchestration template gives the named permission
only to the developer. Existing projects with a tool policy enable it explicitly in
`tool_policy.roles.developer` and keep the other tools. Explicit restrictions are never widened
automatically; the tool list is bound to the digest before the approval (ADR 0024).

The author writes in the `test_paths` of the worker and uses its runner. The developer passes one
specific test path in the brief scope and the log root from the adapter prompt:
`<main>/.harness/.sandboxes/runs/`. Linked worktrees share these logs; `run_id` points to
`isolated-test-<run_id>/log.txt` under that root. The adapter gives access to the evidence, and the
scoped guard keeps its write and Bash limits. The code, the tests and the Git status of the main
checkout stay unchanged; the shared runtime logs stay in its ignored sandbox.

A preflight of the main checkout with the `--worktree` of a separate worker answers
`checkout_mismatch`: its guard and runner serve only the main checkout. An in-process developer
therefore calls the author through the launcher of its worktree:
`python3 -I -B <worker_worktree>/.harness/health/test_author.py run --repo <worker_worktree> --brief <brief path> --prompt-file <file>`.
The launcher checks the preflight of the worker and starts the author with the guard and the runner
of that worktree; the brief permission rule is the same. Any preflight refusal or an unavailable
tool to call the author keeps the usual TDD in the worker, with the reason, without a blocker and
without new ledger records. The runtime selection comes from the developer; a missing protected
adapter for it keeps the usual TDD, without a substitute executor.

This release verifies Python tests through unittest and pytest. Rust tests in
`native/harness-runtime/crates/*/tests` are not supported by this solution: no write zones and no
separate runner were added for them. A configurable argv is not itself restricted to Python, but it
does not establish the support of another stack. Usual Rust QA stays required for Rust changes.

## 8. Diagnostics and live check

### How to enable the test author

1. Set `test_paths` and `test_runner` (section 2) and add a `test_author` block with runtime, model
   and effort to `.harness/project.json`. When `.harness/orchestration.json` has a developer plan,
   `harness health --fix` adds the block from that plan itself; it does not change an existing
   block.
2. Open Claude Code once in the main checkout of the repository and accept the trust dialog. The
   worktrees of this repository need no trust of their own.
3. Run `harness health` and do the step under each `hooks.test_author_*` line with the status warn.
   The lines check the conditions one by one, so repeat health until all of them are ok.

`harness health` reports `hooks.test_author`: the readiness of preflight or a sanitized refusal,
and the selected runtime, model and effort with their source. Health uses the developer plan of the
orchestration, marked `planned`, and otherwise the short profile of the project. A planned
readiness does not replace an approved brief. Without opt-in the check is skipped with a reason; an
unavailable optional author gives a warning and keeps the usual route working. The result of
preflight refers to the checkout that health runs for; a worker worktree checks its own preflight
when it calls the author.

Health shows each condition of the author as its own line, and a refused line prints the step that
fixes it — a command or a fragment of the configuration:

| Line | What it checks | Step on a refusal |
| --- | --- | --- |
| `hooks.test_author_config` | the `test_author` block in `.harness/project.json` | the block fragment from the developer plan and `harness health --fix` |
| `hooks.test_author_root` | the project root by Git, and that `CLAUDE_PROJECT_DIR` matches it when the variable is set | both paths at `project_dir_mismatch` and `unset CLAUDE_PROJECT_DIR` |
| `hooks.test_author_trust` | the trust of Claude Code in this checkout or in the main checkout that lists it in `git worktree list` | the path to trust and `cd <main checkout> && claude` |
| `hooks.test_author_guard` | the agent, the executable guard and its check of the configuration | `harness update` or a fix of `test_paths` and `test_runner` |
| `hooks.test_author_runner` | the executable `.claude/hooks/run-test.sh` | `harness update` |
| `hooks.test_author_probe` | the isolation probe of the runner | the step for the reason: bubblewrap, user namespaces, location of the checkout |

Guard and probe run scripts of the project, so their lines are skipped before the trust.

Health runs no Claude process, no selected test, no build and no database, and changes no trust.
The isolation probe creates and removes a temporary sandbox under the shared `runs/`. A static
`preflight: ok` does not prove that the scoped hook fires live. `make test-author-probe` checks
that: it needs a Claude Code login and quota. It uses the runtime, model and effort of the
developer plan of the source project, not a separate model of its own. An unsupported runtime
adapter fails explicitly. The supported probe confirms the guard, a behavior Red and an external
developer that calls the author in a worker worktree; a fixture developer then proves Green of the
unchanged test.

Each CLI call leaves a sanitized `test-author-probe-*.json` in the shared
`.harness/.sandboxes/reports/`: checkout, stage, exit code, time, usage and cost reported by the
runtime, and a separate limit. Unknown metrics stay `null`; a limit is not usage. The reports
survive the removal of the clean-room project, without full transcripts or credentials. The share
of a subscription quota can be absent from the runtime data and is never calculated from USD.
