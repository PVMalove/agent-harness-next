# Optional test-author cycle

One protocol for the full `/implement` route and the `/fast-implement` short route. The developer
role's own rules are in `.harness/orchestration/roles/references/developer-test-author.md`;
activation is described in `docs/agents/test-author.md`.

## Select the executor

- **Short route (`/fast-implement`):** run `python3 -I -B .harness/health/test_author.py preflight --repo .`
  once before the first test. It selects runtime/model/effort from the explicit `test_author`
  profile in `.harness/project.json` and invokes the supported protected adapter
  (`.claude/hooks/test-author-preflight.sh` for Claude).
- **Full route (`/implement`):** the developer role reference above selects the executor.

Only exactly `{"status":"ok"}` enables the author. Missing settings, `runtime_unsupported`,
`disabled`, a missing or failing hook, unavailable isolation, or no `test_paths` or `test_runner`
keep ordinary TDD in this session: state the sanitized `reason` (or that the hook failed) in one
line. Do not start an unprotected author, do not substitute another executor, and do not re-run
preflight hoping for another answer. There is no implied provider or model.

## Hand off each step

- **Short route:** save a prompt-file and call
  `python3 -I -B .harness/health/test_author.py run --repo . --prompt-file <path>`, so the project
  runtime/model/effort apply even when this session uses other settings.
- **Full route:** hand off as the developer role reference above prescribes.

Give the author one behavior requirement, one scenario, the agreed public seam, the public
signatures and the existing fixtures. Never pass a proposed algorithm or implementation snippet as
the basis of an expectation. The author may write only one test in `test_paths` and run only that
test through `.claude/hooks/run-test.sh <test-id>`; it writes no production code or skeleton and
receives no orchestration manifest, dispatch, brief/report, approval, or ledger lifecycle.

## Read the reply

The author answers in compact English with `status` (`red`, `needs_skeleton` or `contract_gap`),
the requirement, the inputs, the source of the expectation, the test id and, for `red`, the
sanitized runner JSON plus the failed assertion, the expectation and the actual result from the
run's `log.txt`.

- **Verify the expectation** against the requirement and its stated source before any
  implementation. An expectation derived from the implementation, or one the requirement does not
  support, goes back to the author as a failed call. An accepted expectation is never weakened to
  reach Green; only a justified contract change (the requirement or the agreed seam changed with
  the developer) allows correcting it, with a new author call and a new verification.
- **Statuses:** `red` continues. `needs_skeleton`: write only types and signatures with no logic,
  then rerun the author on the same scenario. `contract_gap`: clarify the requirement or seam with
  the developer, never guess it.
- **Not a behavioral Red:** a compile or import error, a fixture error, and an environment or runner
  refusal are never Red, whatever `status` says. A test that is Green immediately does not count as
  a cycle. Each is a failed author call.
- **Green, then Refactor:** after a confirmed behavioral Red, write the minimal implementation that
  passes the unchanged test and run it by its test id; refactor only on Green, re-run the test, then
  request the next test.
- **Attempt limit:** after three consecutive failed author calls on one test, stop the local retries
  and report the blocker to the developer. A guard denial counts as one failed call, and the denied
  call is never rephrased. Local retries create no dispatch and no ledger state.
