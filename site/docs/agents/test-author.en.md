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

```json
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
| `CLAUDE_PROJECT_DIR` matches the root of the Git checkout | `project_untrusted` |
| Claude Code is not started with `CLAUDE_CODE_SIMPLE=1` or `CLAUDE_CODE_SAFE_MODE=1` | `claude_code_unsupported` |
| The user accepted the trust dialog for this project | `project_untrusted` |
| The agent `test-author.md` is installed | `agent_missing` |
| The scoped `PreToolUse` hook is enabled in the agent | `scoped_hook_unsupported` |
| `test_paths` and `test_runner` are set, and the write zones are valid | `test_paths_missing`, `test_runner_missing`, `config_invalid`, `write_zone_rejected` |
| The file `test-author-guard.py` is executable and answers with JSON | `guard_hook_unavailable` |
| `run-test.sh --probe` confirms isolation | `isolation_unavailable`, `runner_unavailable` |

Trust is checked against the project entry in `~/.claude.json` (or `$CLAUDE_CONFIG_DIR/.claude.json`):
the exact project path must have `hasTrustDialogAccepted: true`. The native mode
`claude --print` skips the trust dialog, so preflight checks the decision itself. If Claude
Code treats the project as trusted through a parent directory or the Git root, but there is no entry for the
path itself (for example, in a separate worktree), preflight answers `project_untrusted`. This is a
safe refusal, not an error. Open the project at this path in Claude Code and accept the dialog.

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

Preflight serves only the checkout where it lives. The developer in-process worker works in
a separate worktree from the brief, and `CLAUDE_PROJECT_DIR` points to the main checkout, so a call
without arguments would check the wrong directory. Such a developer runs
`"$CLAUDE_PROJECT_DIR/.claude/hooks/test-author-preflight.sh" --worktree <worktree from the brief>`.
The answer `{"status":"ok"}` is possible only if the canonical path of the argument matches the checkout of the
script. For a separate worker checkout the answer is `checkout_mismatch`. The author does not write or
run tests in the main checkout: the guard and the runner serve only the checkout of the script.

The external transport (`harness/adapters/claude_worker.py`, headless `claude -p` in a worktree) does not
enable the author and does not run preflight: the native `--print` mode skips the trust dialog, and the
worktree path has no trust entry, so the reason is `transport_unsupported`. This is a developer decision, not an
answer from preflight.

Any answer other than `{"status":"ok"}` leaves the usual TDD in the worker checkout: the developer writes
the failing test, then makes it green, and names the reason in the output. This is not a blocker, and the ledger does
not change.
