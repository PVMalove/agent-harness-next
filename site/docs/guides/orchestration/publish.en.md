# Publish and PR

Accepted publish completes the pipeline for the candidate. PR preparation separately checks the integration branch and verification evidence. Opening a PR requires confirmation; a person merges it.

[Orchestration overview](../../backend-orchestration.md)

## Integration accounting after publish {#integration-accounting-after-publish}

A finished batch is history: it is not reopened and not rewritten. The link that the next integration
step needs (ticket, issue branch, source batch, published candidate SHA, and target SHA of the
integration ref) is recorded by a separate immutable record, the Integration record. The `integration`
group creates and reads it. None of the commands writes the batch, plan, dispatch, or reports. Only `refresh`
(below) changes Git:

```bash
python .harness/orchestration/coordinator.py --repo . integration prepare \
  --ticket '#123' --branch feature/issue-123-short-name
python .harness/orchestration/coordinator.py --repo . integration status \
  --ticket '#123' --branch feature/issue-123-short-name
python .harness/orchestration/coordinator.py --repo . integration link-evidence \
  --record <integration_record_id> --kind ci --result passed \
  --candidate-commit <sha> --target-commit <sha> --reference <run-url> [--artifact-sha256 <hex>]
```

Run `prepare` after an accepted publish and before a merge or branch deletion. It selects the only
finished batch with an accepted publish for the ticket+branch pair. It checks the published SHA in two
independent ways: by the accepted publish report (the report and brief digest) and by `ls-remote`
(the remote branch is exactly the candidate, and the integration ref is exactly the pinned target). The evidence
comes from the accepted green QA of the same SHA. The response contains `integration_record_id`, the
`candidate_sha`/`target_sha` pair, and digest links to the source QA and publish. A repeated `prepare` does not
create a second record and does not lose the first one (`created: false`). A refusal always contains a remedy. The refusal
cases are: no batch found for the ticket and branch; `--batch` belongs to another pair; the batch is not finished or not
published; several published batches without `--batch` (one batch is never substituted for another);
`--candidate-commit` is not equal to the published SHA; the remote branch is missing or different; there is no accepted
green QA; the integration ref has already moved forward and there is no record yet; the remote is unavailable; the batch history
was changed after the record.

The record lies in `reports/integration/`, and the evidence lies in `reports/integration-evidence/` inside the
already verified `reports` directory: the ledger schema version and `ledger migrate` do not change.

`status` is observation only, under the same read-only contract. It does not create a dispatch, writes nothing,
and gives the same answer on repetition. The states are: `current` (the integration ref is still at the
recorded target), `stale` (the ref has moved forward; `refresh_required: true`), and `unavailable` (the remote did not
respond; the pair cannot be confirmed). The source QA applies only to the recorded pair.
`source_evidence.applies_to_current_pair` is `false` when `stale`, and the old QA is not accepted for
a new candidate/target pair. `status` itself starts nothing. `integration refresh` (below) can update the pair
when it is `stale`. After a refresh, `status` shows the current pair (`candidate_sha`,
`target_sha`, the original values in `original_candidate_sha`/`original_target_sha`), the `refreshes` list,
and the `verification` block: `required: true` until there is a passed CI or local-QA of exactly this pair
(`resolver` does not count), and always `re_review_required: false`.

`refresh` is the PR preparation route instead of a mandatory developer rerun caused by a base shift:

```bash
python .harness/orchestration/coordinator.py --repo . integration refresh \
  --ticket '#123' --branch feature/issue-123-short-name
```

The command reads the current SHA of the integration ref. If it equals the pair's target, no rebase is run
(`state: unchanged`, nothing is written). Otherwise it rebases the issue branch in the worktree of its batch
onto this exact SHA and publishes the branch with `--force-with-lease` and the expected old SHA, so
another person's commit on the remote is not lost. The command refuses with a remedy if the worktree is not on the issue branch
at the recorded candidate, if the worktree has uncommitted changes or an operation in progress, or
if the remote branch no longer equals the recorded candidate. Stash, reset, and bypass are not applied, protected
and `integration/*` branches are never a write target, and other worktrees are not touched.

A clean rebase returns `state: rebased`, `new_candidate_sha`, and `verification_required: true`, does not
call the resolver, and does not spend its two cycles. A text conflict returns `state: conflict` and
`resolver` (`conflicting_files`, `candidate_sha`, `target_sha`, `worktree`, `cycles_spent: 0`);
the rebase is aborted, and the branch and the worktree stay as they were. A rebase writes an immutable
`IntegrationRefreshRecord` in `reports/integration-refresh/` (the earlier and the new candidate, the target,
the commits before and after). The old QA stays as historical evidence, and the new candidate is confirmed by CI
or local-QA of the pair through `link-evidence`; a repeated review because of a refresh is not needed. A conflict and work
that needs a developer follow the rebase route from ADR 0012, and `refresh` does not depend on it.

`resolve` is the text conflict route (the `conflict-resolver` role, ADR 0015). It writes nothing to
Git and rejects a clean rebase, because that is the work of `refresh`. A conflict becomes a new batch
of the `resolver` kind next to the ticket's finished batch, and the brief, reports, and history of the finished batch do not change:

```bash
python .harness/orchestration/coordinator.py --repo . integration resolve \
  --ticket '#123' --branch feature/issue-123-short-name
```

The response contains `batch_id`, the conflicting files, the candidate and target SHA, the scope, and the remaining budget.
The `next_action` of the batch is `resolve-conflict`. Then the ordinary path follows: `batch approve`, then
`dispatch create --role conflict-resolver --purpose work` (first `--propose`). The brief carries an
immutable `resolver` section: the ticket, the requirements of both sides (`sides.candidate` is the DoD of the source
batch; `sides.target` is the plan records of the tickets `(#N)` from the subjects of the target commits, otherwise the subject and body
of the commit), the candidate and target SHA, the scope, the prohibitions, the commit plan, the checks, the remaining budget, and
`report_staging_path`. The role opens the skill `resolving-merge-conflicts`, preserves the requirements of both
sides, and does not add functionality outside them.

The budget is two automatic target SHAs, and a third needs a human decision. A cycle is spent only by
a recorded resolver report for a new target SHA, whereas a clean rebase, a human answer, and
a fix on the same target do not spend a cycle. Fixes on one target are limited by
`retry_policy.max_developer_retries`. The budget is derived from the append-only events of
`reports/resolver-events/` (`cycle-spent`, `same-target-fix`, `human-decision`, `scope-change`,
`exhausted`), so a lost session or a resume does not reset it.

The resolver does not guess incompatible requirements: it writes a checkpoint (`blockers` with a specific description
and the options) and ends the session. The human answer is recorded as a separate event before the resume:

```bash
python .harness/orchestration/coordinator.py --repo . integration resolver-event \
  --record <id> --kind human-decision --dispatch <dispatch-id> \
  --decided-by <имя> --option <вариант> --note '<решение>' [--extends-budget]
python .harness/orchestration/coordinator.py --repo . dispatch resume \
  --dispatch <dispatch-id> --trigger human-decision --file <facts.json> \
  --approved-by <имя> --approved-at <время>
```

The same session continues the same dispatch: a new developer is not created, and neighboring batches are not
stopped. `--extends-budget` gives one more automatic target after two are spent.
A scope change is an ordinary approval of a new dispatch (`--kind scope-change` only records it).
The source brief is not rewritten. The existing check rejects a resume with changed facts.
A lost runtime session is resumed through the existing checkpoint/resume or
`batch resume`. The counters are taken from the events.

After the budget is exhausted (`exhausted`), only this task stops: the branch and the evidence
are kept. The same resolver continues an integration incompatibility after a human decision.
A defect in the ticket itself (`resolver.cause: task-defect`) is returned to the ordinary developer.

The resolver report carries a top-level `resolver` block: `preserved_requirements` (each requirement of
both sides verbatim from the brief), `human_decisions` (the ids of only those human-decision events that
answer a checkpoint of this dispatch), `target_sha`, `resolved_candidate_sha`, `cause`,
`changed_files`, and `commits` with a plan record for each commit. A standalone
`human-decision --extends-budget` without a checkpoint is recorded only as a ledger event and does not get into the report.
Besides one more automatic target cycle, it gives another `max_developer_retries`
attempts to fix the same target. An accepted resolution follows a narrow route: a repeated code-review
is skipped, but QA and CI or local-QA of the new candidate/target pair are required
(`integration status` keeps `verification.required`).

`collect-ci` collects CI proof for the combined result of the PR (ADR 0016):

```bash
python .harness/orchestration/coordinator.py --repo . integration collect-ci \
  --ticket '#123' --branch feature/issue-123-short-name --pull-request 45
```

The command works only with the `github` tracker and the `ci_required_checks` list from
`.harness/project.json`. CI is accepted if both conditions are met: the checks ran on the merge commit of the
PR whose parents are exactly the current candidate and target; and all required checks passed. Then the
command writes an immutable record with `verification: collector-accepted`. `integration status`
shows a `qa_replacement` block (the source, repository, PR, pair SHAs, merge commit, and check run id).
If the integration ref has moved forward, `qa_replacement.applies` becomes `false`, and
`re_refresh_required` becomes `true`: a new refresh and a new collection are needed. The fallback path is a full local
QA. It is needed on `fallback` with the reason `unsupported_tracker`, `not_configured`, `unavailable`,
`wrong_repository`, `wrong_pull_request`, `wrong_base`, `unknown_checkout`, `head_only`, `stale_candidate`, `stale_target`, `missing_check`, `pending_check`,
`inconclusive_check`, or `light_check`. In this case nothing is written. The `light_check` reason
means that `ci_required_checks` contains a check whose name ends in `-light` (the `verify-light` job
for PRs to `integration/**`), while the pair requires full QA: the saved pair selection is not
`ticket-diff`, there is no pair record, it uses the old contract, or it is damaged. Such a check does
not confirm the pair, so a full local QA or full CI is required. CI unavailability counts neither as a
code finding nor as a success. A completed `failure` on a confirmed pair is recorded as
`collector-failed`. A CI linked manually through `link-evidence` stays `unverified` and does not close the verification of
the pair. CI does not replace the source QA reports.

`local-qa` is the fallback path when the CI of the combined result is absent, unavailable, or
unusable (`--ci-condition absent|unavailable|unusable`, required `--reason` and `--record`):

```bash
python .harness/orchestration/coordinator.py --repo . integration local-qa \
  --record <integration-record-id> --ci-condition absent --reason 'CI не настроен для ветки'
```

The command pins an immutable request (the candidate/target pair, the reason, the full list of
`verification_commands`) and runs the existing gate runner in an isolated clean-room checkout
of the exact candidate. The task branch, the terminal source batch, and the accepted reports do not change, and
the code is not fixed. The run goes through the shared FIFO QA queue (`qa status`): two heavy QA runs do not work
at the same time, and the other batches continue implementation. The command writes the result as a separate immutable
record with the commands, a sanitized artifact, and a checksum, and links it as evidence
`kind: local-qa` with `verification: verified`, but only if the pair and the remote branch have not moved:
an earlier result does not confirm another SHA or a target movement. A check failure is a finding with
`state: failed`, which stays for the PR session to route. Infrastructure unavailability gives
a separate `state: unavailable` without findings. A retry is possible only with an explicit `--retry` and not more than
`max_infrastructure_retries`, after which `state: exhausted` occurs. A manually linked
`local-qa` stays `unverified` and does not close the verification of the pair.

`next` is the read-only PR continuation step (ADR 0017). It writes nothing to Git, the ledger, dispatch, or the PR and
does not contact the tracker. It classifies `status`, the evidence, open resolver batches, and the budget
events:

```bash
python .harness/orchestration/coordinator.py --repo . integration next \
  --ticket '#123' --branch feature/issue-123-short-name [--pull-request 45]
```

The steps (`step`) are: `unavailable` (the integration ref cannot be read: an operational stop, not a code defect),
`resolver-open` (a resolver batch is open; the PR session waits, no cycle is spent), `refresh`, `route-failure`
(a failed check of the current pair), `human-decision` (the resolver budget is exhausted), `confirm-pr` (before the PR),
`verify` (with `--pull-request`: the updated pair needs CI or local-QA), and `handoff` (the pair is current and
verified: `candidate_sha`, `target_sha`, `qa_source` `original-qa|ci|local-qa`, `reference`,
`refreshed`). Old evidence allows entering PR preparation (`confirm-pr`), but does not count as QA of
the new candidate: `verify` and `handoff` require verification of exactly the updated pair.

The failure routing rule: a failure is only a `collector-failed` CI or a `failed`
generated local-QA of the current pair that has no passed verified check. A passed, verified
check of the current pair clears the failure regardless of the write order. A failure recorded after it does not
open the route while the passed check still applies to the current pair. If the pair went through a refresh or
a resolver, the route is `resolver` (a behavioral incompatibility after a clean rebase, a consequence of a
resolver fix; the budget `cycles_total`/`cycles_spent`/`remaining`/`internal_fix_budget` and
`fixes_on_target` are in the response; on exhaustion, `human-decision` with
`integration resolver-event --extends-budget`). If the pair is the original one, the route is `developer`:
the task's own defect goes to the ordinary developer with review and QA (ADR 0012). The finished source
batch is terminal, and `batch decide` on it refuses. So the `next` hint names an executable
path: a new batch of the same ticket and issue branch through the ordinary `/implement` route
(`batch create --ticket T --branch B --worktree W --integration-ref I`, then architect, developer,
code-review, QA, and publish; a finished batch does not block a new one). The base of the new batch is the integration
tip. So the developer report shows in `commit_map` also the branch commits that are already published (with `dod_coverage` and
`divergence_justification`). After an accepted publish, `integration prepare --ticket T --branch B --batch
<new batch>` creates a new record, and `integration next --record <new record> --pull-request N`
continues the PR, while the failed evidence of the earlier record stays as history. One ticket and branch now has
two records, and `<ticket-branch>` is rejected with the refusal "several integration records match".
`--record <new record>` replaces `<ticket-branch>` in the `integration` commands of the `to-pull-requests` skill.
The operational CI fallback and `unavailable`/`exhausted` local-QA do not create failed evidence and do not
become a code failure. For a failure of the updated pair, `integration resolve` creates a resolver batch with
`resolver.trigger: verification-failure` (`failed_evidence_ids`, empty `conflicting_files`) even
when `tip == target`. The `target` side is taken from the commits that landed in the target after the source
target of the record (`identity.target_sha..tip`). The scope stays the task's own files (an edit of
other files is a new approved `scope-change` dispatch). The budget and the limit of fixes on the same target
are the same as for a conflict. A human answer and waiting for CI neither reset nor spend the budget.

The `next` hint in the result of `collect-ci`: `pending_check` is `{action: wait}`; `not_configured` and
`unsupported_tracker` are `{action: local-qa, ci_condition: absent}`; `unavailable` is `local-qa` with
`unavailable`; the other fallbacks are `local-qa` with `unusable`; `failed` is `{action: route}`. For `accepted`
there is no hint: the full local QA is skipped (`qa_replacement.applies`).

`/to-pull-requests` runs this process. Before the PR, a separate human confirmation is needed, bound
to the exact `candidate_sha`/`target_sha` pair. A change of the pair before opening makes it invalid.
After the PR is opened or updated, it waits for CI; if CI is unusable, the fallback `local-qa` runs, then
`handoff` for a manual merge. Before the merge, the verified SHA pairs and the QA source are shown. The handoff
does not promise immutability until the merge, and a new target repeats the refresh and verification.
Server branch
protection and the merge queue are not enabled automatically. The merge stays manual, and the ticket is closed
only after a confirmed merge.

`link-evidence` is the only public way to attach future CI, local-QA, or resolver results to a record
(`--kind ci|local-qa|resolver`). Each link is a separate immutable record with its own
`candidate_sha`/`target_sha` pair and `verification: unverified`; the source evidence of the record never
gets a new pair, and a check of a new pair does not replace the old one. A repeat of the same link is
idempotent (`linked: false`). This operation does not start CI, local-QA, or the resolver itself. In `status`,
each link shows whether its pair relates to the current tip
(`pair_checks[].applies_to_current_pair`).

## Advisory tool call {#advisory-tool-call}

`.harness/orchestration/advisory.py` is a cheap non-role CLI for purely utility subtasks:
ranking files by keyword, a log summary, and a rough risk hint. It runs outside the
brief/report/self-report/heartbeat contract. It is not a dispatch: it writes no ledger record and does not
import `ledger/`/`contract.py`/`coordinator.py`. The output is ephemeral. It is printed to stdout and
recomputed on every call. It is not saved anywhere as ground truth for another
dispatch:

```bash
python .harness/orchestration/advisory.py rank-files --keyword payments -- services/payments/handler.py README.md
python .harness/orchestration/advisory.py summarize-log --file qa-output.log
python .harness/orchestration/advisory.py classify-risk --text "data migration for payments" --known-trigger data-migration
```

The advisory output is not an authorization: the coordinator/contract validation path does not accept it as a
basis to create a dispatch, lower a risk, accept QA, or change a scope. The only
authoritative source of risk stays `coordinator.py risk assess`.
