# Stops, refusals and recovery

Read the section that matches the situation. Recovery routes and approvals follow the
Recovery route table in `.harness/orchestration/playbook.md`.

## A batch blocks the ticket

If another batch holds the same unfinished ticket, branch or worktree, or the `concurrency_budget`
is exhausted, inspect `batch list --open`, the conflicting dispatch,
and its decision packet. Tell the developer which batch is blocking and how to finish it normally.
If its worker can no longer produce a report, first run `batch auto-report`,
`batch decision-packet`, `dispatch status` and `ledger validate`, and quote the dispatch's
`startup` assessment: worker state, classification and unknowns. Explain which of waiting, launch
repair, human-approved `batch resume-stop`, `batch rewind` and cancelling an unsent dispatch
applies, and why the others do not. Offer `batch abandon` only after that, as a separate explicit
human choice for the whole batch: show a copyable command with the actual batch ID, the verified
operator name, `--approved-at "$(date -u +%Y-%m-%dT%H:%M:%SZ)"`, and a reason grounded in the
observed failure. Never supply `--approved-by` as though they already approved, or execute the
command for them without that approval. `ledger clean` only removes orphaned evidence, and
`ledger reset` does not clear an active batch.

## Runtime store hold

When the runtime store holds a batch (attention `operational-hold`, or a refusal whose `REMEDY`
names recovery), run `recovery status --batch <id> --json`, fix the cause, resolve open attention,
then run `recovery resume --batch <id>`. Recovery never reruns an accepted stage and never starts a
worker: continue with the `next` command it prints. An `ambiguous-effect` refusal waits for a human
decision. After a configuration edit, run `config validate --canonical --json` before the next
transition. Details: "Operational hold and recovery commands" in
`.harness/orchestration/playbook.md`.

## Infrastructure-only failure

When a stage's report is `blocked` only by an infrastructure failure although its work looks
complete (a developer's commits match the plan, for example), a human may decide
`batch decide --decision accept-conditional --infrastructure-failure --note <cause>`. The pipeline
advances as after `accept`, but the stage stays an open condition that a later code-review or qa
accept must independently close; publish refuses while one is open. Never choose it yourself, and
prefer `resume-stop` when the stage can simply be restarted.

## Block bypass and tooling blockers

A worker that works around a hook or tool block (another command form, tool, script file, `eval`,
interpreter or a split command) breaks the protocol: never accept or warning-override that report,
and record the violation in `--note`. For an architect or developer (publish included), decide
`retry` with a developer reason category (not `tooling`) or `block`. For a read-only code-review, qa
or verification role, pass `--reason-category block-bypass` to `batch decision-packet` and, once its
`route_preview.retry.route` is `bypass-rerun`, to `batch decide --decision retry`: the same stage
re-runs on the same SHA with no new candidate and no developer retry spent, and its new dispatch
needs explicit approval under every `approval_policy` except `auto`. A report that stops with
`tooling_blocker` instead is confirmed
before its retry: check that its `command` is legitimate under the brief (allowed paths and tool policy) and
that its `message` refuses that command. For a false positive, file or reuse a bug ticket against
the tool through the tracker CLI (tool, command, message, dispatch ID), name the ticket in `--note`,
and run `batch decide --decision retry` once `route_preview.retry.route` is `tooling-retry`; it
re-runs the same stage on the same SHA (a developer continues its last commit) and spends no
`retry_policy.max_developer_retries`. A command that is not legitimate is no false positive: retry
with the developer reason category its evidence supports. Resolve the `tooling-retry-repeated`
attention, raised by the third consecutive tooling retry on one candidate, only once the tool is
fixed.

## A failed check the diff may not cause

When a developer report has a check with `checks_run[].result: fail`, find out whether the diff
causes the failure before `batch auto-decide` under `approval_policy: auto`, or before you propose
`retry` under any other policy:

1. Name the failed tests from the check's evidence or its log.
2. List the candidate's diff: `git -C <abs issue worktree> diff --name-only <batch base>..<candidate>`.
   The failure is related when the diff changes a failed test file, a module that test imports, or
   the test configuration (`conftest.py`, `pyproject.toml`, `uv.lock`).
3. Run only the failed tests at the candidate from the coordinator session, without moving the
   session: use the command's own working-directory option, for example
   `env -C <abs issue worktree> <test command> <failed test ids>`. If they fail again, run them at the
   batch base in the same way.

Write the evidence in English as a findings file under `.harness/.sandboxes/scratch/inbox/`, in the
`--findings-file` format `{"findings": [{"summary", "files", "expected_evidence"}]}`: the failed
tests, the diff files, each run with its commit, result and duration, and the known differences of
the worker environment (for example, its sandbox). If the evidence shows that the diff causes the
failure, continue with `batch auto-decide` or the usual `retry`.

If the diff touches none of the failed tests and they pass alone or fail at the base too, a
developer retry cannot fix the code. No decision accepts that report: a failed check is a
`code_test` failure, so `accept-conditional` and `override-warning` refuse it, and every `retry` of
it is a developer-retry. Do not run `batch auto-decide` and do not propose `retry`: show the evidence
to the developer and wait for their choice:

- Fix the environment first (or the checks the brief carries), then run
  `batch decide --decision retry --note <findings file and cause>`. The developer-retry reruns the
  checks without a code change. It then reports `outcome: blocked` with an empty `commit_map` and
  no failed check (`.harness/orchestration/roles/references/developer-retry.md`). For that report,
  propose `batch decide --decision retry --reason-category verification-infrastructure`: the route
  `verification` reruns the checks read-only on the same candidate. Or the developer decides
  `batch decide --decision accept-conditional --infrastructure-failure --note <cause>` (section
  "Infrastructure-only failure"); after that accept,
  `batch carry-over --batch <id> --findings-file <path>` hands the evidence to code-review as a
  carried item.
- Or `block` the batch.

## Defect in a clean developer report

When you find a defect in a clean developer report whose DoD is met inside its allowed paths, do not retry
it: accept it with `batch decide --findings-file <path>`, or after a policy auto-accept run
`batch carry-over --batch <id> --findings-file <path>` before its code-review dispatch exists. The
finding travels into the code-review brief as a carried item (route `carry-over`), and the one
developer retry is spent after review. Retry a developer report without accept only for an unmet
DoD item or an out-of-scope change.
