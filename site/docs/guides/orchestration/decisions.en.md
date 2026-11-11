# Decisions and retries

Read the decision packet first. It binds the report, candidate SHA and allowed next actions. A retry needs a matching route; changing the reason must not hide a project defect.

[Orchestration overview](../../backend-orchestration.md)

## `retry` routing and the `abandon` decision {#retry-routing-and-the-abandon-decision}

`batch decide --decision retry` no longer means "developer again". The coordinator stores a routing record on the
decision: `route`, `previous_role`, `reason_category`, `next_role`, `next_action`,
`rationale`, and `candidate_commit` (while it has not changed). The coordinator determines the cause only from the
structured data of the report: outcome, findings, the severity of the Standards/Spec axes, failed checks, and
whether the candidate changed. Free text in `blockers`/`output` is not classified. You can pass an explicit cause
through `--reason-category` (`code`, `requirements`, `candidate-change`,
`verification-infrastructure`, `transport`, `context-pressure`, `tooling`, `block-bypass`,
`unknown`). But it does not override a finding that was found. A rate limit, an unavailable Bash/WSL wrapper, and
a transport failure are operational evidence (`verification-infrastructure` or `transport`), not a
code finding. A context limit gives `context-pressure` only if a `critical` observation `context_pressure`
is recorded for the reporting dispatch (see below). A bare claim gives `unknown`.

**Failure domains.** Each routing record carries `failure`: exactly one ADR 0019 domain
(`environment_preparation`, `infrastructure`, `policy`, `tooling`, `code_test`, `timeout`,
`cancelled`, `unknown`) with the evidence that shows this domain: `domain`, `method`,
`matched`, and `source`. `method` is `structured` (a report, stage, or runtime field), `heuristic`
(a text pattern, which never proves `code_test`), `approver` (a human or a policy named the domain),
or `fallback`, and `fallback` always means `unknown`.

The `code_test` domain is proven by a finding in a review, a warning/blocker severity on an axis, an explicit retry that
the reviewer assigned, a failed check, an open carried item, a confirmed project defect during
QA preparation, a conflict-resolver report with `resolver.cause: task-defect`, and a shifted candidate (it
changed after the dispatch was pinned). The coordinator treats a shifted candidate as `code_test`
on purpose: the ledger proves that the work itself changed, so the route stays a developer retry
and spends the budget, as it did before the domains appeared. A `retry_reason_classifier` hint is not proof:
it does not replace a structured fact of the report, and without such a fact the domain stays `unknown`.

The other domains follow from facts. A structured `tooling_blocker` gives `tooling`,
a confirmed QA environment failure gives `environment_preparation`, a recorded `critical` observation
`context_pressure` gives `infrastructure`, and `block-bypass` gives `policy`. Anything that no
structured fact confirms is `unknown`, but never `code_test`.

Only a retry with the `code_test` domain spends `retry_policy.max_developer_retries`.
`infrastructure`, `environment_preparation`, `policy`, `tooling`, `timeout`, `cancelled`, and `unknown`
never spend it. When developer retries are counted for the `budget-exhausted` stop,
only such records are counted.

The coordinator refuses a developer retry on a code-review, qa, verification, or publish report if the
domain is not `code_test`. The refusal is typed as `UnprovenFailureError` and carries `failure`; `batch decide
--decision retry` returns `failure` and a remedy and writes nothing. Under `approval_policy: auto`, the same
refusal becomes the stop `no-automatic-route`/`unknown-reason`, and its evidence keeps `failure`.
The same stop ends an automatic developer retry with the `unknown` domain, because such a
retry would not spend the budget and would remain without a limit.

The approver proves the `code_test` domain with the categories `--reason-category code`, `requirements`, or
`candidate-change`. The approver may also request a developer retry through `--retry-role developer`, including
for a code-review, qa, or verification report that a tool blocked. Both variants prove the
`code_test` domain as `approver` and spend the budget. The exception is `tooling-retry`: with
`--retry-role developer`, such a retry of the developer stage keeps the `tooling` domain and spends nothing;
the other `tooling-retry` routes do not spend it either. A decision recorded before the domains appeared
does not carry `failure`, and the previous rule applies to it.

| Report stage | `accept` | `retry` | `block` / `fail` | `abandon` |
| --- | --- | --- | --- | --- |
| architect | developer | new architect | terminal | `abandoned` |
| developer | risk assessment | `developer-retry` continues the unaccepted candidate of this report (`snapshot_commit` is its `commit_sha`); the retry creates a new candidate, and that candidate gets a new risk assessment; the budget is spent only for the `code_test` domain; with a non-empty closed list of carried items, the route is `fix-forward` | terminal | `abandoned` |
| verification | risk assessment | `developer-retry` for the `code_test` domain, otherwise a refusal | terminal | `abandoned` |
| code-review | qa | new code-review on the same `candidate_commit` if the report is `blocked`, the cause is `verification-infrastructure`/`transport`/`context-pressure`, findings are empty, both axes have no findings, there is no failed check, and the candidate did not change; in other cases `developer-retry` for the `code_test` domain (with a non-empty closed list of carried items, `fix-forward`), and a refusal for another domain | terminal | `abandoned` |
| qa | publish | new qa on the same SHA under the same condition (QA stays read-only); a defect or a new candidate is a `developer-retry` for the `code_test` domain, otherwise a refusal | terminal | `abandoned` |
| publish | `completed` | new publish on the same accepted SHA for `verification-infrastructure`/`transport`/`context-pressure`; `developer-retry` for the `code_test` domain if the candidate must change; otherwise a refusal | terminal | `abandoned` |

`code`, `requirements`, and `candidate-change` lead to `developer-retry` when the `code_test` domain is
proven. `unknown`, or a contradictory or unconfirmed cause, does not prove a code defect: on the
manual path, the developer stage repeats through `developer-retry` without spending the budget, and on the
automatic path, the policy stops such a retry. The code-review, qa, verification, and publish stages
get a refusal (see "Failure domains"). Only the three operational categories can repeat a read-only stage
on the same SHA, and only with empty findings, an unchanged candidate, and no
scope/requirement blocker. A repeat on the same SHA is a new immutable dispatch: a new
dispatch ID, a repeated Context Package freshness check, and its own explicit approval under
`manual_all`, while the earlier brief, report, and blocker remain audit evidence. Fictitious and empty commits
are not used, and a new candidate always needs a new risk assessment. `block` and `fail` do not start a retry
themselves. `--retry-role developer` forcibly selects a developer retry where the coordinator
would otherwise repeat the same role on the same SHA.

`tooling` is a separate operational category: a hook, a safety classifier, or the ledger
blocked a legitimate action of the role. The coordinator assigns it only from the structured field
`tooling_blocker` (`tool`, the exact `command`, `message`) in a report with `outcome: blocked`. A finding,
a failed check, a shifted candidate, or a developer category must not override the category. An explicit
`--reason-category tooling` without this field gives `unknown`. Another named operational category
follows its previous route. The `tooling` route at any stage is `tooling-retry`: a new dispatch of the same
stage on the same SHA (architect, verification, code-review, qa, or publish). For the developer, this is
a `developer-retry` that continues its latest commit. This commit is recorded in the
`candidate_commit` of the routing record. In the table above, "three operational categories" still mean
`verification-infrastructure`, `transport`, and `context-pressure`.

If a hook blocked exactly the developer's `git commit`, the developer reverts nothing and adds to the
`tooling_blocker` the field `uncommitted_files`: a non-empty list without repeats, where each path is written
as Git prints it and lies inside the write zone. `commit_sha` then points to the developer's latest
commit, and the `tooling-retry` restart inherits these changes. `dispatch preflight`
pins HEAD to the developer's latest commit and allows a dirty worktree only if its
uncommitted paths (excluding coordinator state and tool sandboxes) exactly match the
list from the report and lie in the batch zone. Preflight rejects an extra file, a missing file, or a file
outside the zone, and the message and remedy name each mismatch. A clean worktree without a list passes, as
before, and for other dispatches preflight does not check the worktree for uncommitted changes.

`block-bypass` means that a read-only role (code-review, qa, or verification) bypassed a hook or tool
block instead of stopping with a `tooling_blocker`. Only the approver names this category. A report with the
violation is not evidence: its findings, failed checks, and outcome do not affect the
route, and only a shifted candidate still leads to `developer-retry`. The route is
`bypass-rerun`: a new dispatch of the same stage on the same SHA (for verification, on its
registered candidate) without a new candidate commit. `batch decide` requires a `--note` that
describes the violation, and the report itself is not accepted and is not closed through override-warning. The new
dispatch always requires an explicit approval (`--approved-by`) under any `approval_policy` except `auto`,
and `bypass-rerun` does not spend `retry_policy.max_developer_retries`. For architect, developer, and
publish, `block-bypass` is rejected: such a report still gets a `retry` with a developer category
(`code`, `requirements`, `candidate-change`) or `block`.

A retry of an unaccepted developer report continues its history. While the batch waits for this `developer-retry`,
the coordinator takes the candidate from the immutable report (`commit_sha`, verified by hash) and pins the
`snapshot_commit` of the new developer dispatch to it. The worktree is rolled back neither to the base nor to an older
accepted candidate. The `commit_map` of a retry counts only commits on top of `snapshot_commit`. Each
new commit closes exactly one distinct entry of the plan, and `dod_coverage` and
`divergence_justification` in a retry report are rejected. The default path is
`dispatch propose`/`create` without `--candidate-commit`. Then the brief gets `candidate_commit: null`
and needs no risk assessment, like a developer retry after code-review. To bind this SHA to the
transition digest, pass `--candidate-commit <commit_sha>`. Then, before
`dispatch propose`/`create`, while the batch is in `awaiting-approval`, a `risk assess` for the same SHA is needed.
Such an assessment is only evidence. `next_action` stays `developer-retry`, `required_next_role` and
the requirement of a new candidate are kept, and code-review and QA do not open. A `risk assess` for
another SHA is rejected. A retry report with the same SHA is not accepted. A retry after code-review, qa, or
publish still pins `snapshot_commit` to the latest accepted developer candidate.

Fix-forward is a route of the existing developer-retry, not a new transition. A `retry` decision
that leads to `developer-retry` records in the routing record `retry_item_ids`, a closed, possibly
empty list of carried items that the developer-retry brief will carry. For a code-review retry, it
includes the open `coordinator-finding` items, the Standards and Spec axis findings of this review
(`review-finding`), and the open `incomplete-item` items for the developer. For a qa, publish, or
verification retry, it includes the same items without review findings, and for a developer work report retry, it includes the items of its
own brief, none of which was accepted. A non-empty list makes the route `fix-forward`;
a developer `tooling-retry` keeps its route and writes the same list. The developer-retry brief carries
exactly these items, and a mismatch with `retry_item_ids` is rejected as an invariant violation.

The developer continues from `snapshot_commit` with new commits on top of it and reports in the completion report
with the field `carried_item_closure`, one record for each brief item:
`{"item_id": <id>, "commits": [<sha>, ...]}` with the commits of the retry chain that close the item,
or `{"item_id": <id>, "not_closed": "<reason>"}`. The retry chain is this dispatch and the earlier
attempts that passed the same closed list to it. A developer report retry and a developer `tooling-retry`
pass the items of their brief to the next attempt, and the `snapshot_commit` of the next attempt is the HEAD
of the previous one. Commits are counted from the `snapshot_commit` of the first attempt of the chain, from which the
`snapshot_commit` of this dispatch still descends; with an approved rebase target, counting starts from it, and
after a not-yet-accepted `rebase-fix-forward` attempt in the chain, from its target. Therefore an item closed by an
earlier attempt cites its commit, and after a rebase, its carried-over copy.

After a `rebase-fix-forward` attempt, commits of two kinds belong to the chain: the new commits of its attempts
and the carried-over copies whose `rebased_from` in the `commit_map` of the attempt report points to a commit
of the chain. An earlier rebase is taken into account: a copy of a copy leads to the original commit. A carried-over copy
of a commit that existed before the chain (it lies in the `snapshot_commit` of the first attempt or below)
is rejected with the same remedy as the original. There is one exception: an old stale-base rebase does not write
`rebased_from`, and its closure still counts all commits above the batch target. A completed report
of such a brief must carry the field, a blocked or failed report may carry it, and reports of other briefs
must not. `report submit` rejects, with a remedy, a missing, unknown, or repeated item, an empty
reason, an empty list of commits, an unresolvable SHA, and a commit that the retry chain did not create;
the commits are checked against Git, including for a brief without `commit_plan`. A `not_closed` item is a carried gap, and
such a report is not clean: the policy does not accept it automatically, and `--decision accept` is rejected.
`override-warning` requires a `--note` other than `none` and records
`carried_items_gap` in the decision. The `commit_map` of a retry report keeps the strict rule of checking against the commit plan, and
`batch decision-packet` shows, for the developer-retry items, the status `closed` with the commit SHAs or
`open` with the reason.

Without an approved rebase target, the `commit_sha` of a retry report must be a descendant of `snapshot_commit`.
A report after an amend, squash, or reset is rejected with the message `developer-retry candidate <sha> does
not descend from snapshot_commit <snapshot>: the retry rewrote the history it continues (amend,
squash or reset)`. Remedy: restore the rewritten commits from `git reflog`, repeat the fix
with new commits without amend and squash, and report the new HEAD. The retry of a rebase report of a legacy
stale-base record (`base_rebase_required`, recorded before ADR 0014) is still checked against its rebase
target.

Rebase-fix-forward is also a route of the existing developer-retry, not a new transition. A `retry`
decision that leads to `developer-retry` or `fix-forward` (a retry of a developer, verification,
code-review, qa, or publish report; not `tooling-retry` and not `bypass-rerun`) runs `git fetch` for
`origin/<integration_ref>`. The route becomes `rebase-fix-forward` if both conditions are met: the tip
moved forward from the pinned `integration_base_commit`; and the candidate that the retry will continue
(the retry's own candidate for a developer report, otherwise the latest accepted one) does not contain this tip yet. The routing
record additionally names `rebase_target_commit` (the new tip) and `integration_base_commit` (the base
it moved away from) and keeps `retry_item_ids`. `next_action` stays `developer-retry`, and such a
retry spends one `retry_policy.max_developer_retries` when its failure domain is `code_test`.
A fetch error rejects `batch decide --decision retry` with a remedy. `decision-packet` shows it
in `route_preview.retry`.
The decision only proposes the target: the `integration_base_commit` of the batch does not change before accept.

The target enters a brief only through a dispatch with an explicit approval under any `approval_policy` except
`auto`. The approval of another policy is rejected for it. `dispatch propose` shows the transition with the field
`rebase_target_sha`, and the brief gets `rebase_target_commit`. Besides this, the brief field is filled
only for the developer-retry of a superseding batch (see "Superseding batch" below). In all other briefs, it
is `null`, including the developer dispatch of a legacy stale-base record:

```bash
python .harness/orchestration/coordinator.py --repo . batch decision-packet --batch <batch-id>
python .harness/orchestration/coordinator.py --repo . batch decide --batch <batch-id> \
  --decision retry --reason-category code --approved-by 'имя утверждающего' \
  --approved-at <approval-time-utc>
python .harness/orchestration/coordinator.py --repo . dispatch propose \
  --batch <batch-id> --role developer --runtime claude
python .harness/orchestration/coordinator.py --repo . dispatch create \
  --batch <batch-id> --role developer --runtime claude --approved-by 'имя утверждающего' \
  --approved-at <approval-time-utc> --transition-digest <transition_digest>
```

The developer moves the commits over the old base exactly onto this target
(`git rebase --onto <rebase_target_commit> $(git merge-base <snapshot_commit> <rebase_target_commit>)`),
resolves the conflicts, and adds fix commits in the same dispatch. Its `commit_map` lists each
commit of the previous candidate (after the `git merge-base` of `snapshot_commit` and the target up to
`snapshot_commit`) exactly once: `{"commit_sha": <copy>, "rebased_from": <original>}`, where the
carried-over copy inherits the plan item of the original, or `{"rebased_from": <original>, "dropped":
"<reason>"}` for a commit that the rebase did not carry over. Each commit after the target appears exactly
once: as a carried-over copy or as a new commit `{commit_sha, plan_entry_id}` under the strict
retry rule. `changed_files` and `carried_item_closure` are counted from the target. The check "the candidate is a
descendant of `snapshot_commit`" does not apply to such a brief. `report submit` rejects, with a remedy,
a missing, repeated, or unknown commit of the previous candidate, a copy that is identical to its
original (a merge of the target instead of a rebase), an empty `dropped` reason, a commit that the dispatch did not
create, and `rebased_from`/`dropped` in the report of a brief without a target.

`report submit`, `batch decision-packet`, and the `accept`/`override-warning` decision return
`rebase_check`: `rebase_target_commit`, `previous_base_commit`, `rebased` pairs with `patch_id_match`
(a `git patch-id --stable` comparison), `dropped`, and `patch_id_mismatches`. A patch-id mismatch
means a conflict that was resolved with changes: the report is not rejected and does not lose its clean status, and the pair
is shown for delta-review. Accepting such a report pins `integration_base_commit` = target,
and accepting a later retry whose candidate already stands on this target acts the same way. A retry of a not-yet-accepted
rebase report, like its `tooling-retry`, counts both `changed_files` and the commits of
`carried_item_closure` from the target. If the tip moves again, review and QA check the pinned candidate, and the branch
is updated by `integration refresh` when the PR is prepared (ADR 0014).

A batch created on a branch with commits of an earlier batch of the same ticket (its `branch_start_commit`
is a strict descendant of `integration_base_commit`) counts its changes from `branch_start_commit`. The
`changed_files` and `commit_map` of the developer and publish reports, their `scope_warnings`, the
checkpoint, and `risk assess` (`--base-commit`, `review_scope`) are counted from it. A superseding batch counts from
`integration_base_commit`; a batch whose start is not a descendant of this base (after an accepted
rebase and for a resolver batch) counts the same way. The brief and the Context Package (`--base-commit`) stay on
`integration_base_commit`. The rule does not distinguish accepted commits from unverified ones: the new batch does not review the commits
of an abandoned (`abandon`) batch.

Delta-review after fix-forward is also not a new transition and not a new decision. The coordinator itself
chooses the scope of the next code-review in `dispatch propose` and `dispatch create --role code-review`
without `--delta-review-of`. The coordinator makes the choice when all conditions are met: the candidate is the
`commit_sha` of the latest accepted developer work report of the batch; this report is a developer-retry; the
route `fix-forward` or `rebase-fix-forward` opened its chain of consecutively repeated developer-retry attempts;
the latest code-review before the chain finished its report on the `snapshot_commit` of the chain's first
attempt and was accepted or repeated in a developer. This code-review is the prior review. The brief
gets the field `delta_review_scope`: `mode` (`delta` or
`full`), `route`, `prior_review` (dispatch ID, `report_sha256`, the verified candidate,
`review_base`, `risk_assessment_id`), `developer_dispatch_id`, `delta_base`, `delta_commits`,
`reviewed_copies`, `closure` (the `carried_item_closure` of the accepted report), and `escalations`. The transition
binds the section with the field `delta_review_sha256`. `dispatch propose` shows it as
`delta_review_scope`. In all other briefs, the field is `null`, including with an explicit
`--delta-review-of`: a test-only delta-review works as before.

The delta is `git diff <delta_base> <candidate_commit>`. Without a rebase, `delta_base` is the candidate of the prior
review, and after a rebase in the chain, the commits after the last rebase target are taken. The leading
carried-over copies count as verified (`reviewed_copies`) if, by the `rebased_from` pairs from the
`rebase_check` of the chain reports, they lead to a commit from the range of the prior review and `git patch-id`
matches at every step; `delta_base` is the parent of the first other commit. The coordinator selects the mode
`full` automatically, without a manual choice, if at least one escalation `{reason, evidence}` is found:

- `new-risk-trigger` — a trigger of the risk assessment of the candidate (together with the developer triggers) or
  of the commits and files of the delta that was not in the assessment of the prior review;
- `file-outside-carried-items` — a delta file outside the files of the carried developer-retry items (for a
  `review-finding`, this is the `review_scope` of its review);
- `patch-id-mismatch` — a pair from `patch_id_mismatches` of any report of the chain;
- `dropped-commit` — a `dropped` record from the `rebase_check` of any report of the chain: the candidate lost
  a change that the prior review verified, and the delta of the remaining commits does not show this;
- `no-new-commits` — there are no new commits to check.

In this case, the brief is an ordinary full review, and the section remains audit evidence. In `delta` mode,
the `carried_items` of the brief additionally carries the `review-finding` and `incomplete-item` items for the developer from the
brief of the accepted developer-retry. The reviewer checks both axes only on the delta, and for the rest of the
candidate relies on the report of the prior review; the reviewer accounts for each item in `review.carried_items`, and
an omission, `open`, or `unverified` is a carried gap. `review_scope` and `review.scope` stay
full. Accepting any review, delta or full, leads to `qa`, and the clean-room QA runs on the new SHA with the
full `verification_commands`. A delta-review retry passes to the next developer-retry
the carried items that the review did not mark `closed`, and the review's own findings
get the next numbers `review-finding-N`.

A code-review `blocker` is never accepted. While `retry_policy.max_developer_retries` still allows a
developer retry, `retry` or `abandon` is available for it. After the budget is exhausted, `retry`
is rejected, and the blocker is closed through `block`, `fail`, or `abandon`. Then the work is split
or re-planned in a new batch. `tooling-retry` does not spend this budget and is not rejected when it is
exhausted. A human still decides each such retry, and the attention `tooling-retry-repeated` limits
a series. `--retry-role developer` on a read-only stage still gives a
`developer-retry` that spends the budget.

The `abandon` decision is available after any completion report. It requires an explicit approval and a non-empty
`--reason`, moves the batch to the terminal `abandoned`, and marks unclosed dispatches as
`abandoned`:

```bash
python .harness/orchestration/coordinator.py --repo . batch decide \
  --batch <batch-id> --decision abandon --approved-by 'имя утверждающего' \
  --approved-at <approval-time-utc> --reason 'план заменён, начинаем новый batch'
```

`abandon` does not delete the worktree, candidate, brief, report, Context Package, or audit evidence, does not
close the issue, and does not create a PR. Only what does not belong to evidence is removed: staged copies of
reports in the agent inbox and QA-queue records of dispatches that will no longer run (a live QA lease
is still released only by `qa clear-stale-lease`). The batch records `abandoned.last_accepted`, the
latest accepted stage and its candidate. From it, you can create a fresh batch on the same branch and the same
candidate. `abandon` never serves as an automatic fallback for `block`, `fail`, or `retry`.
The `batch abandon` command for a batch that will never have a report stays as before. It
ends such a batch in `failed`.

### Superseding batch: `batch create --supersedes`

If a batch is closed by the `batch decide --decision abandon` decision after a dead end (for example, a code-review
blocker with an exhausted retry budget), a superseding batch continues the work. It is created for
the same ticket and the same issue branch and starts from `abandoned.last_accepted`, not from a new architect
and a manual cherry-pick of the accepted commits:

```bash
python .harness/orchestration/coordinator.py --repo . batch create \
  --ticket '#443' --branch feature/issue-443-<slug> --worktree <тот же worktree> \
  --allowed-path '<scope>' --definition-of-done '<item>' --prohibited-change '<rule>' \
  --supersedes <abandoned-batch-id> --approved-by 'имя утверждающего' \
  --approved-at <approval-time-utc>
```

`--supersedes` requires human approval. `--approved-by` and `--approved-at` are checked the same way as
for `batch abandon`: the approval TTL and the terminal confirmation when `human_approval_gate: tty`.
An approver with the `policy:` prefix is rejected. Approval flags without `--supersedes` are also rejected:
an ordinary batch is approved through `batch approve`. A superseding batch also goes through
`batch approve` after creation. The command names a remedy and writes nothing in these cases: the source is not in the current
generation of the ledger; its state is not `abandoned`; `abandoned.last_accepted` is `null`; the ticket or
issue branch differs; the latest accepted candidate does not resolve to a commit. A batch closed by
`batch abandon` stays in `failed` without `last_accepted`. With `null`, nothing was accepted. In both
cases, an ordinary batch is needed. The exception is a source with `null` that itself superseded a batch. Then the
remedy suggests passing that batch (the `supersedes.batch_id` of the source) to `--supersedes` again, because its
`last_accepted` is still the latest. An abandoned batch does not hold the ticket, branch, or worktree. But
another unfinished batch with the same ticket, branch, or worktree still blocks creation.

The new batch and its immutable plan carry the same immutable `supersedes` reference: `batch_id`,
`approved_by`, `approved_at`, a copy of `last_accepted`, `definition_of_done_matches`, `architect`,
`start_commit`, and `rebase_target_commit`. A batch whose reference diverges from the plan fails the
integrity check. The `coordinator_decisions` of the new batch contain one `supersede` record. Its routing record
of the `supersede` route names `previous_role`, `next_role`, `next_action`, `candidate_commit`
(`start_commit`), `rebase_target_commit`, `superseded_batch_id`, `rationale`, and `decided_at`.

What is carried over:

- with the same Definition of Done (the lists match item by item): the accepted architect of the source by
  the reference `supersedes.architect` (`batch_id`, `dispatch_id`, `report`, `report_sha256`,
  `commit_plan_sha256`) and the commit plan pinned at its accept through `--commit-plan-file`.
  If the source itself carried over an architect, the same reference is passed. The batch starts with
  `next_action: developer`: the developer dispatch is created at once, and an architect dispatch is not allowed.
  With a different Definition of Done, nothing is carried over, and the architect stage runs again;
- `start_commit` is the candidate from `last_accepted` (`null` if only an architect was accepted). For a
  superseding batch without an accepted developer, this candidate is its own `start_commit`.
  Therefore the next superseding batch in the chain does not lose the accepted candidate. The first developer
  dispatch takes it as `snapshot_commit`. The brief, the preflight, and the Context Package freshness check
  see the same SHA. If `start_commit` is a descendant of the integration base pinned at create,
  this is an ordinary initial developer: its `commit_map` covers all commits after the base, including the
  `start_commit` commits;
- `rebase_target_commit` is this base, if `start_commit` does not contain it. Then the first developer is a
  developer-retry of the rebase route inside the retry. It rebases the commits onto the target, fixes
  on top, and submits the `rebased_from` pairs. `report submit` returns `rebase_check`. Such a dispatch
  requires an explicit approval with a transition digest under any `approval_policy` except `auto`. The target
  stays in the brief until the snapshot being continued contains it. This happens, for example, after a retry of
  a report that was not yet rebased.

What is never carried over: the risk assessment, code-review, QA, carried items, candidate registrations,
and operator decisions. They stay evidence of the abandoned batch and are available only through
`supersedes.batch_id`. The risk assessment, review, and QA run again on the new candidate. The `supersede`
record is not a retry and does not spend `retry_policy.max_developer_retries`: the superseding batch has its
own budget. The abandoned batch is only read. The worktree must stand on `start_commit`. If
the dead-end attempt left unaccepted commits above it, the runtime attestation rejects the developer with a
remedy. A human decides to move the branch back. The coordinator looks for the source only in the current generation of the
ledger.

### The `route` field: routing record, decision packet, and audit

Every `retry` and `abandon` decision in `batch decide` records the selected recovery route in
`routing.route`, one value of the closed set `RECOVERY_ROUTES`: `developer-retry`,
`same-candidate-rerun` (a new code-review, qa, or publish on the same SHA), `verification`,
`architect-retry`, and `abandon`. `batch decide` either records the other values under special
conditions or does not record them at all:

- `batch decide` does not record `report-completion`. It is named by `completion` in `report submit`
  when the policy chain stopped after the recorded report (see step 4 above and "Busy ledger"
  below).
- `carry-over` is recorded by `accept` or `override-warning` with `--findings-file` and by `batch carry-over`
  (see step 4). This is a routing record with `previous_role: developer`, `next_role` and `next_action`
  `code-review`, `candidate_commit`, `carried_item_ids`, and `rationale`, without `reason_category` and
  `decided_at`; it does not apply to `next_action`, and the next step goes through the risk assessment, as with
  any developer accept. The same route is recorded by `accept` or `override-warning` of a read-only
  report with `--carry-incomplete` (see step 4): then `previous_role` is the stage of the report, and `next_role` and
  `next_action` are the ordinary next step of its accept.
- `tooling-retry` is recorded by `retry` with the category `tooling` (see above), and also by `retry --narrowed`
  if an item carries a `tooling_blocker`.
- `bypass-rerun` is recorded by `retry` with the category `block-bypass` (see above).
- `narrowed-retry` is recorded by `retry --narrowed` for the unfinished items of a read-only report (see
  step 4); its routing record additionally names `carried_item_ids`.
- `fix-forward` is recorded by a `retry` that leads to `developer-retry` with a non-empty closed list
  of carried items (see above).
- `rebase-fix-forward` is recorded by a `retry` that leads to `developer-retry` while the integration base
  has moved forward (see above); its routing record additionally names `rebase_target_commit` and
  `integration_base_commit`.
- `batch decide` does not record `supersede`: `batch create --supersedes` records it in the
  `coordinator_decisions` of the new batch (see "Superseding batch" above).

Every routing record with `next_action: developer-retry` (`developer-retry`, `fix-forward`,
`rebase-fix-forward`, and the developer `tooling-retry`) additionally names `retry_item_ids`. The route
is set in the same place as `next_action`, from the same structured data and never from free
text. The `abandon` routing record has the same shape, but `reason_category`, `next_role`, `next_action`, and
`candidate_commit` are `null`, and `rationale` contains only structural facts (`--reason`
stays in `note`). The normative table "situation → route → who approves → evidence" is the section
"Recovery route table" in `.harness/orchestration/playbook.md`.

`batch decision-packet` shows the route before the decision is recorded: the field `route_preview` contains
`retry`, the routing record computed the same way as in `batch decide` (without `decided_at`), and `abandon`,
`{"route": "abandon"}`. The packet accepts the same `--reason-category`, `--retry-role developer`, and
`--narrowed` as `batch decide`, and writes nothing. For an already decided report and for the packet of the
next dispatch, `route_preview` is `null`:

```bash
python .harness/orchestration/coordinator.py --repo . batch decision-packet \
  --batch <batch-id> --reason-category verification-infrastructure
```
## Automatic path `approval_policy: auto` {#automatic-path-approval_policy-auto}

The `auto` policy applies while the project configuration and the batch plan select `auto` and the batch has no
`auto_stop`. The session does not pass `--approved-by` or `--approved-at`. The policy approves:

- `batch approve`: `coordinator_approval.approved_by` equals `policy:auto`;
- `dispatch create`, including the milestones `publish`, `risk-trigger`, `risk-reassessment-required`,
  `bypass-rerun`, `rebase-fix-forward`, and `rebase-target`;
- `dispatch resume --trigger` for a planned continuation, except `human-decision`;
- `batch carry-over`: the decision is written as `policy:auto`, not as `policy:carry-over`.

An explicit `--approved-by` under `auto` remains a human approval. Each policy approval is one hashable record
in `batch.auto_decisions` (`sequence`, `kind`, `dispatch_id`, `approved_by`, `approved_at`, `rationale`,
`evidence`). Ledger validation recomputes `record_sha256` and checks the record against the approval it names.

The `report submit` or `qa run` chain accepts a clean report as before. For all other reports, including the publish
report, the session runs:

```bash
python .harness/orchestration/coordinator.py --repo . batch auto-decide --batch <batch-id>
```

The command computes the decision from the ledger facts, passes it through the `batch decide` checks, and writes it
as `policy:auto` with the route, the reason, and the evidence. The session passes only the inputs that require
judgment:

- `--commit-plan-file` is the architect's plan. The policy pins the plan if it lies inside `allowed_paths` and
  covers all DoD items. Otherwise the path stops. If the command cannot read the file as a JSON object, it refuses
  and writes nothing.
- `--findings-file` holds the coordinator's findings for an accepted developer report.
- `--bug-ticket` is the tooling bug ticket for `tooling-retry`. Without it, the command refuses and writes
  nothing.
- `--block-bypass --note` applies when a role bypassed a hook or tool block.

The policy accepts a clean report and records its risks as `accepted_risks`. A review report in which the Standards
or Spec axis names `blockers` is not clean. For all other reports, the policy selects `retry` according to
`route_preview`. The policy never selects `override-warning`, `block`, `fail`, or `abandon`. A conflict-resolver
report is outside the automatic path: a human decides it.

The closed list of stops:

| `category` | `reason` |
| --- | --- |
| `integrity-failure` | `stale`, `model-mismatch`, `worktree-mismatch`, `harness-snapshot-changed`, `deterministic-gate-failed`, `ledger-validation-failed`, `operational-hold` |
| `budget-exhausted` | `retry_policy.max_developer_retries`, `continuation_policy.max_continuations`, `continuation_policy.max_rate_limit_resumes`, `attention_policy.max_infrastructure_retries`, `tooling-retry-repeated` |
| `no-automatic-route` | `unknown-reason`, `abandon-dead-end`, `supersede-dead-end`, `qa-environment-failure` |

`batch auto-decide` and `batch auto-report` find a stop in this order: integrity, budget, route.
The coordinator writes the stop once in `batch.auto_stop`, together with the final report.
The command only prints `ledger-validation-failed`: the ledger is untrustworthy. The policy writes the
`operational-hold` stop when the runtime store holds the batch: the policy does not decide the report and does not
abandon, and only `recovery resume` releases the hold (section "Batch hold and the `recovery` commands").
A stop creates no decision and does not weaken validation. After a stop, every batch step requires `--approved-by`,
and the batch cannot return to `auto`.

The policy also writes the `no-automatic-route`/`unknown-reason` stop when a read-only stage or publish fails with
`UnprovenFailureError` (see "Failure domains"): the decision is not written, and the stop evidence keeps `failure`.

The coordinator writes the final report once in `batch.auto_report`: when the publish report is accepted or at a
stop.
The report lists the `policy:auto` decisions, the accepted risks, the findings, the retries and the spent budget,
the DoD coverage by commit plan, the review and QA results, and the stop. The command prints the report:

```bash
python .harness/orchestration/coordinator.py --repo . batch auto-report --batch <batch-id>
```

If no report is recorded, the command records the stop that the ledger shows, or prints a live report with
`recorded: false`. The policy does not open or merge a PR: a PR opens only after explicit human confirmation, and
auto-merge is prohibited.

## Approval bound to the transition digest {#approval-bound-to-the-transition-digest}

`dispatch propose` takes the same arguments as `dispatch create`, but does not write a brief. It registers the
shared Context Package that the brief will pin. Then it returns the canonical transition and its
`transition_digest`. This is the SHA-256 of the batch ID, the ID and role of the previous dispatch, the reason
category, the next role/action and purpose, the candidate SHA, the base SHA, the review scope, the verification
commands, the Context Package ID, and the required gates. `dispatch create` with an explicit approval must receive
this digest in `--transition-digest`. The coordinator recomputes the transition from the ledger and rejects any
mismatch. So a change of scope, candidate, role, verification command, reason category, or Context Package
requires a new `propose` and a new approval. The coordinator stores the digest in the approval and in the
immutable brief, together with the transition itself. Ledger validation recomputes it. A policy approval
(`milestone`, `low_risk`) is derived from the transition being created and is bound to its own digest.
With `human_approval_gate: "tty"`, the confirmation prompt shows the digest.

If the Repo Map of the pinned package has a tier other than `full`, the `dispatch propose` result also contains
`context_package_quality_warning`: the tier, the reason for the degradation, and the parser provenance. This is a
warning for the approving human, not a dispatch block. For `full`, the field is absent.

Without `repo_map_policy.min_tier`/`min_tier_by_role`, Repo Map degradation never blocks a dispatch. Only the
non-blocking warning described above remains. `repo_map_policy` may contain `min_tier` (a common minimum for the
repository) and/or `min_tier_by_role` (a per-role override; the keys are exactly
`architect`/`developer`/`code-review`). The resolution order is then: the role override, then `min_tier`, then no
gate. If a minimum is set for the role and the actual tier of the pinned Context Package is worse than required
(the tier order follows ADR 0008: `minimal` < `full`), the coordinator rejects both `dispatch propose` and
`dispatch create` before any approval. The reason names the role and the actual and required tier. This check runs
in the shared path before the `propose`/`create` branch. So a ready `--transition-digest` does not bypass it. A
role that is not listed in `min_tier_by_role` keeps the default behavior (no block) when there is no common
`min_tier`.

An expired (`approval_ttl_seconds`) or terminal-rejected approval is fail-closed: the coordinator does not repeat
the call itself and does not substitute an older approval.

## Idempotency of a read-only retry {#idempotency-of-a-read-only-retry}

The brief of the roles `architect`, `code-review`, `qa`, and publish stores
`retry_idempotency_key = sha256(role + candidate SHA + base SHA + review scope + reason category +
digest verification commands)`. While the open batch has an active dispatch (not decided, not cancelled, not
abandoned) with the same key, a new dispatch is rejected. A finished retry does not block a new dispatch on the
same candidate: it gets a new immutable ID. A change of candidate always changes the key. A repeated review/QA never
edits the earlier report and brief.

## Context pressure {#context-pressure}

`dispatch context-pressure --dispatch <id> --observed-tokens <N> --source probe|provider-usage|
runtime-adapter` writes an observation with `observed_tokens`, `context_limit`, `warning_threshold`, `level`
(`ok`/`warning`/`critical`), and `recorded_at`. Without `--observed-tokens`, the configured
`context_telemetry_provider` supplies the number. The source is only the provider/runtime: a model self-report is
rejected. The limit and the warning share are values pinned in the brief. The record is a pure observation: it does
not change `next_action`, does not create a retry, and does not remove an approval. At `critical`, it states the
worker's obligation. A write role creates a checkpoint at the nearest green TDD boundary or returns a structured
blocker. A read-only role returns a blocker. A continuation is created only from a checkpoint and only with a new
model self-report. A retry with the category `context-pressure` requires such a `critical` record for the reporting
dispatch.

## Attention state {#attention-state}

`needs_attention` is a batch flag, not a lifecycle state: it does not change `state`, `next_action`, the candidate,
or the evidence, but it prohibits the creation of the next dispatch. The fields `needs_attention`,
`attention_reason`, `attention_since`, `last_safe_action`, and `recommended_human_action` describe the flag. The
reasons:

| `attention_reason` | When |
| --- | --- |
| `operational-hold` | the runtime store holds the batch with the record `recovery/hold/<batch_id>.json`; after the cause is removed, a human resolves the attention, then `recovery resume` releases the hold |
| `unknown-reason` | a retry with the reason `unknown` |
| `infrastructure-retry-repeated` | operational retries of one candidate exceed `max_infrastructure_retries` |
| `tooling-retry-repeated` | the third consecutive `tooling-retry` on one candidate; cleared after the tool is fixed |
| `retry-queued-too-long` | an accepted retry waits for a dispatch longer than `retry_queue_seconds` |
| `stale-evidence` | the Context Package pinned in an unfinished dispatch diverges from the base or from the current developer candidate (the same one that `snapshot_commit` selects) |
| `stale-dispatch` | a live dispatch is silent longer than `stale_dispatch_seconds` |

`batch decide --decision retry`, `dispatch wait` (the `stale` event), and `batch attention check --batch <id>` set
the flag. The last command simply evaluates the batch now. Only a human clears the flag:
`batch attention resolve --batch <id> --note '…' --approved-by … --approved-at …` acknowledges the open findings
(the same event is not raised again) and writes an event to `attention_events`. If `human_notifier` is configured,
it is called when the flag is set. An adapter failure is recorded as `failed` and does not cancel the flag.
