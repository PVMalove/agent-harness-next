# Integration route (backend-orchestration opt-in)

Read this file only when the project has a valid `backend-orchestration` opt-in and the ticket is not
labeled `pipeline::fast`. Every command below is `python .harness/orchestration/coordinator.py --repo . <command>`,
and `<ticket-branch>` stands for `--ticket "#<ID>" --branch "<current-issue-branch>"`.

A record of an epic's `integration/*` branch (`source_kind: integration-branch`, the release PR of
`references/release.md`) follows the same steps with `--record <id>` in place of `<ticket-branch>`,
with three differences. No batch QA covers its pair, so `qa evidence` does not apply and
`confirm-pr` answers `qa_source: verification-pending-after-pr` until CI or local QA of exactly that
pair passes. The harness never rewrites an integration branch: on `refresh`, and on
`route-failure` with `route: fix-ticket`, stop; a child ticket based on that branch fixes it, then
`integration prepare` runs again for its new head. `integration refresh` and `integration resolve`
refuse such a record.

## A. Before the PR (skill step 3)

Resolve the full current SHA with `git rev-parse HEAD` after the step 2 synchronization and validate it
before any PR action.

1. First observe the integration record, read-only: `integration status <ticket-branch>`. A refusal saying that no integration record exists does not block the PR: skip the integration steps of this file and continue with the evidence check and the old flow. If it reports `unavailable`, the integration ref could not be read: stop and report it to the developer as an operational stop, never as a code failure. If `refreshes` is not empty, the branch was already refreshed: validate `original_candidate_sha` below instead of the current SHA, because the old accepted QA only permits entering PR preparation and is never QA of the refreshed candidate.
2. Then validate the accepted QA evidence of that SHA:
   `python .harness/orchestration/coordinator.py --repo . qa evidence --ticket "#<ID>" --branch "<current-issue-branch>" --candidate-commit "<full-SHA>"`.
   The CLI selects the unique batch with accepted QA evidence for that SHA, so abandoned
   historical batches with the same ticket and branch do not matter. If more than one batch accepted that exact
   SHA, stop and repeat the command with its explicit `--batch <batch-id>`. Stop if the command rejects
   missing, unaccepted, or SHA-mismatched evidence.
3. Then ask for the next step, read-only: `integration next <ticket-branch>`. It never writes Git, the ledger, a dispatch or a PR; act on its `step`:
   - `refresh`: the integration ref moved. Run `integration refresh <ticket-branch>`; a clean rebase updates only your own issue branch (it does not need re-review and spends no resolver cycle), so make sure `git rev-parse HEAD` equals the new `candidate_sha` and repeat `integration next`. On `state: conflict` run `integration resolve <ticket-branch>`, which only creates the resolver batch, and hand its `batch_id` to the coordinator session (`batch approve`, then `dispatch create --role conflict-resolver`). On any other refusal (dirty worktree, changed remote) stop and hand the data to the developer through the rebase route of ADR 0012; do not create a dispatch or rerun QA yourself.
   - `resolver-open`: an open resolver batch owns the branch. Stop and wait for the coordinator session; no cycle is spent by waiting.
   - `route-failure` or `human-decision`: a check of the current pair failed. Stop and hand the data to the coordinator session. The same resolver takes a failure of a refreshed pair inside its budget (`integration resolve`); a failure of the original pair is the task's own defect and goes to a regular developer with review and QA: the coordinator session plans a new batch of the same ticket and issue branch through the ordinary `/implement` route (`batch create --ticket <ticket> --branch <branch> --worktree <worktree> --integration-ref <integration ref>`, then architect, developer, code-review, QA and publish; the completed source batch is terminal, is never decided again and does not block the new one), and after its accepted publish runs `integration prepare --ticket <ticket> --branch <branch> --batch <new batch>`, so repeat `integration next --record <new record> --pull-request <n>`. Once the follow-up record exists, one ticket and branch have two integration records and `<ticket-branch>` is refused with "several integration records match": `--record <new record>` replaces `<ticket-branch>` in the integration commands of skill steps 3, 6, 6a and 7. `human-decision` means the two resolver cycles or the same-target fixes are spent: only the developer's decision extends them (`integration resolver-event --kind human-decision --extends-budget`), and an answer never resets the budget.
   - `confirm-pr`: continue with skill step 3. `qa_source` is `original-qa` (the original pair), `verification-pending-after-pr` (a refreshed pair that no CI or local QA covers yet), or `ci` / `local-qa` (a refreshed pair that already has that verified evidence).

## B. Verify the opened or updated PR (skill step 6a)

Run these after opening the PR and after any later update of its branch (a refresh or resolver push):

- `integration collect-ci <ticket-branch> --pull-request <n>` asks the tracker for combined-result CI. If it is accepted, the CI replaces a repeat of full local QA (`qa_replacement.applies`) and nothing else runs.
- `next.action: wait` (a check is still running): repeat the command after a pause of about a minute, at most ten times, then ask the developer whether to keep waiting or to use local QA. Waiting spends no resolver cycle.
- `next.action: local-qa` (CI is missing or unusable): run the existing fallback `integration local-qa --record <integration_record_id> --ci-condition <next.ci_condition> --reason "<reason from collect-ci>"` (the full local QA of the exact pair through the shared QA lane). An `unavailable` or `exhausted` result is an operational stop reported as such, never a code failure.
- `next.action: route` (CI of exactly this pair failed and was recorded): follow the route action through `integration next` below; run no local QA. The `local_qa_required: true` that collect-ci returns next to it is inherited semantics for every non-accepted outcome, and `route` takes precedence.
- **Test policy by PR target (projects with `verification_plan_policy.ticket_diff_selection` on).** A ticket PR into an `integration/*` branch is confirmed by the run of its own diff: the pair requires `ticket-diff` and CI runs `verify-light`. The PR of the integration branch into the default branch needs a pair that requires `full`, so it needs the full CI that `integration collect-ci` accepts, or the fallback `integration local-qa`. The `light_check` reason means a `-light` check is listed in `ci_required_checks`; it never confirms a `full` pair, so take the `local-qa` fallback or ask the operator to list the full checks. If the full run fails before the default branch, do not patch the integration branch directly: ask the developer to open fix tickets whose base is that integration branch, and each follows the diff run of its own PR.
- Then run `integration next <ticket-branch> --pull-request <n>` and act on `step` as in part A: `verify` (repeat this part), `route-failure`/`human-decision` (stop and hand over; operational failures never appear here), `refresh` (the target moved: repeat refresh, update the PR and this part), `release-gate-refused` (the Release Gate refuses this pair: its `refusals` name a moved issue branch, a target outside the candidate history or QA evidence `qa.evidence.verify` refused; stop and hand the data to the coordinator session, never merge), or `handoff`.
