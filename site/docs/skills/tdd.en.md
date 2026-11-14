# tdd — Test-driven development

Source: [`SKILL.md`](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/tdd/SKILL.md).
In `engineering-suite` this first-party override replaces the vendor skill of the same name and sets the
shared test rules for the developer and the optional test author.

The skill runs the red → green → refactor cycle at an agreed public seam. One test proves one observable
behavior, so several steps and several assertions are allowed in it when they describe that behavior.
The expected value comes from a source independent of the production code: a literal, a reference fixture
with a recorded origin, or an independent oracle. Input variants are expressed through parameterization,
not through a conditional choice of the expectation in the test body.

Internal components and value objects stay real in the test. At an external boundary the skill
distinguishes a command from a query: for a command the test checks the contract it sends, for a query it
substitutes a stub with a ready response. The test replaces the clock and the source of randomness
deterministically at the boundary, and it checks SQL and transactions on the same DBMS as in production,
in an isolated environment. Refactor follows Green. Coverage is a signal, not a goal. The skill adds
flaky-test and seed policies only when the project already requires them.

The vendor version kept the examples and the substitution rules in separate `tests.md` and `mocking.md`.
In the first-party version the substitution rules are in `SKILL.md`, and the examples are in
[`examples.md`](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/tdd/examples.md).

## Optional test author

In full `/implement`, the executor inherits runtime, model, and effort from the approved developer brief.
The short route selects the explicit `test_author` profile from `.harness/project.json`. The shared check is
`python3 -I -B .harness/health/test_author.py preflight --repo <checkout>`; the full route adds
`--brief <brief path>` and runs the check in the worker's checkout. Only exactly `{"status":"ok"}` enables
the author. Missing or invalid settings, `runtime_unsupported`, and other refusals keep ordinary TDD with
the sanitized reason; no executor is substituted. The current protected adapter works through Claude Code
and `.claude/hooks/test-author-preflight.sh`; other runtimes keep ordinary TDD until a protected adapter
exists for them.

The full route with an external Claude executor calls the native `Agent(test-author)` without model or
effort overrides (`model: inherit`), so the developer's approved settings are kept. An in-process worker
passes each handoff to `.harness/health/test_author.py run --repo <worker worktree> --brief <brief path>
--prompt-file <path>`. The short route passes each prompt file to
`.harness/health/test_author.py run --repo . --prompt-file <path>`, so the project model and effort apply
even when the current session uses other settings. Details:
[test author guide](../agents/test-author.md).

When the preflight succeeds, call the subagent before every implementation step. Give it one behavior
requirement, one scenario, the agreed public seam, the public signatures, and the existing fixtures, but
not a proposed algorithm or an implementation snippet. The subagent writes exactly one test only in
`test_paths`, runs it through `.claude/hooks/run-test.sh <test-id>`, and briefly returns in English the
`status` (`red`, `needs_skeleton`, or `contract_gap`), the requirement, the inputs, the independent source
of the expectation, the test id, and, for `red`, the Red evidence: the runner JSON plus the failed
assertion, the expectation, and the actual result from the run's `log.txt`. The production code, the
skeleton, and the orchestration stay with the developer; the test author does not receive a manifest, a
dispatch, a brief/report, an approval, or the ledger lifecycle.

Check the expectation against the requirement before you implement, and do not weaken an accepted
expectation for the sake of Green; a justified contract change needs a new call and a new check. For `needs_skeleton`, write only types and signatures without logic
and repeat the call. A compile, import, fixture, or environment error does not count as Red, and a test
that is green at once does not count as a cycle. After three consecutive failed calls on one test, stop
and return a blocker. The full protocol is described in `developer.md` of the orchestration roles. The
`/fast-implement` short route runs the same protocol in one session: the seam there is the one the
developer agreed before the first test, not one taken from the architect brief, and an unavailable author
keeps the ordinary route with the reason stated.

`mattpocock-suite` continues to ship the unchanged
[vendor snapshot](https://github.com/PVMalove/agent-harness-next/blob/master/skills/vendor/mattpocock/engineering/tdd/SKILL.md).
