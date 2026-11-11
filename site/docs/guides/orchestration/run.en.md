# Run and report

The coordinator tracks a batch, a unit of work for a ticket. Each dispatch gives a role an immutable brief. Follow planning, delivery and report acceptance in order.

[Orchestration overview](../../backend-orchestration.md)

## Choosing roles and planning a batch {#3-choosing-roles-and-planning-a-batch}

The base set has four write roles and three read-only roles.

| Role | Mode | When to assign |
| --- | --- | --- |
| `developer` | write | An ordinary backend change inside a service or bounded context. |
| `database-migrations` | write | A schema/data migration and its rollout/rollback. |
| `messaging-integration` | write | Outbox, routing, message schema, retry, or DLQ. |
| `conflict-resolver` | write | A text conflict between the ticket branch and a shifted integration SHA; assigned only by the `integration resolve` route. |
| `architect` | read-only | A boundary decision that is hard to reverse. |
| `qa` | read-only | Independent verification through a project-facing interface is needed. |
| `code-review` | read-only | Mandatory for the listed high-risk triggers; produces separate Standards and Spec reports. |

One task may pass through several roles. But the handoff inside one batch is always sequential, and
a batch has only one active writer. Batches with overlapping files may run in parallel,
each in its own issue branch and worktree, as long as `concurrency_budget` allows. Overlaps are resolved
at integration and do not block the launch. The coordinator rejects two batches for the same
unfinished ticket, branch, or worktree. Heavy integration/quality checks go through one
serialized quality-gate lane.

For API/public contract, schema/data migration, outbox/queues, transactions,
authorization/security, and concurrency/retry, completion is impossible until the coordinator has received both
independent `code-review` reports: Standards and Spec.

After a developer dispatch, the candidate commit gets a deterministic risk assessment from the DoD, the changed
files, and the developer-reported triggers. The assessment decides when the composite read-only `code-review` is
**mandatory**, but not when it is *allowed*. You can create a review for any candidate, and the
`/implement` pipeline always does. The Standards and Spec axes stay separate evidence. A separate QA
dispatch is created only after an accepted review (if one is mandatory): the mandatory full QA gate
in a clean room cannot be replaced by the developer's local check. Any new candidate commit after a
finding or a failed QA goes through the risk assessment again.
## Coordinator CLI and lifecycle {#4-coordinator-cli-and-lifecycle}

Runtime-neutral mode has no "start everyone" command. The coordinator CLI manages records through
`planned → awaiting-approval ↔ active → completed`, with the recoverable states `paused`,
`blocked`, `failed` and the final rejection `abandoned`. After a manual recovery, the effective
policy is `manual_all`. Under `manual_all`, every
report leaves its dispatch in `reported` until a human decides. Under `low_risk`, the coordinator
automatically accepts a clean completed report batch if the whole batch scope lies inside
`low_risk_paths`. The coordinator records the decision in the ledger. Blockers, failed checks, disclosed risks, risk
triggers, and findings from any review axis keep the manual gate. Publish also needs a separate
approval. Under `milestone`, the coordinator also automatically accepts a clean report of an ordinary role. But
QA, publish, and risky transitions remain manual milestones. Under `auto`, the coordinator walks the path
from `batch approve` to an accepted publish without a human. The policy approves each step, and
`batch auto-decide` decides on the reports (see "Automatic path `approval_policy: auto`"
below). Opening a PR and the merge remain manual.

1. Create a planned batch, then approve it separately:

   ```bash
   python .harness/orchestration/coordinator.py --repo . batch create \
     --ticket '#123' --branch feature/issue-123-payment-validation \
     --worktree issue-123-payment-validation \
     --allowed-path 'services/payments/**' \
     --definition-of-done 'Добавить валидацию платежа' \
     --prohibited-change 'Не менять migration или публичный API' \
     --required-gate review --required-gate qa
   python .harness/orchestration/coordinator.py --repo . batch approve \
     --batch <batch-id> --approved-by 'имя утверждающего' \
     --approved-at <approval-time-utc>
   ```

   `batch create` first runs `git fetch origin <ref>`. The ref is `--integration-ref` if it is passed,
   otherwise the project `base_branch` (for epic-less tasks). The command records the fetched tip as
   `base_commit`/`integration_base_commit`; a stale local HEAD never replaces it.
   The full `/implement` route requires an explicit `--required-gate review --required-gate qa`
   (independent Standards/Spec review and full clean-room QA), and the coordinator checks that they are present in
   `required_gates` before it sends the write-role (`developer`) worker. In the allowed direct CLI scenarios,
   you may omit `--required-gate` (the default is `["none"]`). After that, review, QA, and publish check the
   pinned candidate even if `origin/<ref>` has moved forward. There is no mandatory base freshness check
   and no forced developer restart, and other batches do not stop on this. The final
   base update is done by `integration refresh` when the PR is prepared (section "Integration accounting
   after publish").
2. Check the active batches, `concurrency_budget`, the writer lane, and the quality-gate lane. An overlap of files
   with another batch is no reason to delay the start, and a busy serialized quality-gate lane does not block
   parallel implementation. If a batch hits the budget, wait for an active batch to finish or
   raise `concurrency_budget`.
3. Create and separately approve an architect dispatch, accept its report, and only then create the
   developer dispatch. The order is strict: the coordinator rejects `dispatch create --role developer`
   until the same batch has an architect report accepted through `batch decide --decision accept`.
   The rule lives in `coordinator.py`, so it applies to both the manual CLI and `/implement`. The CLI
   saves the immutable brief before the handoff:

   ```bash
   # dry run first: shows the canonical transition and its digest, does not write the brief
   python .harness/orchestration/coordinator.py --repo . dispatch propose \
     --batch <batch-id> --role developer --runtime codex
   # the approval is valid only for the digest shown
   python .harness/orchestration/coordinator.py --repo . dispatch create \
    --batch <batch-id> --role developer --runtime codex --approved-by 'имя утверждающего' \
     --approved-at <approval-time-utc> --transition-digest <transition_digest>
   python .harness/orchestration/coordinator.py --repo . dispatch send \
     --dispatch <dispatch-id> --adapter <project-runtime-adapter>
   ```

   For a role with `transport: "in-process"`, you do not pass an adapter at all. `dispatch send --dispatch <id>`
   returns the path to the brief. After that, the coordinator **immediately** starts the role as a subagent
   of the current session. Between these actions, there are no reads of earlier dispatches, reports, or templates. Without
   `.harness/orchestration.json`, add the `--model` and `--effort` of the calling session to `dispatch create`.
   For the coordinator and architect, choose `medium` unless the developer explicitly approved otherwise.

   Accepting the architect report may pin the commit plan the architect proposed instead of the default plan:

   ```bash
   python .harness/orchestration/coordinator.py --repo . batch decide \
     --batch <batch-id> --decision accept --approved-by 'имя утверждающего' \
     --approved-at <approval-time-utc> --commit-plan-file .harness/.sandboxes/scratch/commit-plan.json
   ```

   The file lies in the repository or one of its worktrees and contains exactly one key,
   `{"commit_plan": [...]}`. Each entry contains exactly four fields: a unique `id`
   (`[A-Za-z0-9][A-Za-z0-9._-]{0,63}`), a non-empty `summary`, a non-empty list `expected_paths`
   (relative paths or globs without a leading `/` and without a `..` segment), and `covers`, the numbers of the DoD items
   `1..n` that the entry implements. The order of entries is the order of commits. Accept is rejected with a
   remedy if any DoD item is covered by no entry, if an entry names a nonexistent item,
   or if the flag is not passed with `--decision accept` on an architect report. Then the report stays waiting for a
   decision, and the batch does not change. The coordinator saves the verified plan in the batch as `commit_plan`.
   The architect decision receives `commit_plan_sha256`. This plan becomes the `commit_plan` of every
   developer brief of the batch, including `developer-retry`. If the plan in the batch does not match the digest of the
   accepted decision, the developer brief is not created. Without the file, the brief contains one `step-N` entry
   per DoD item with `covers: [N]`. Under `low_risk` and `milestone`, the coordinator automatically accepts a
   clean architect report with the default plan. Therefore an architect who proposes a different plan
   states this in `risks`, and the report waits for a manual decision.

   `dispatch send --role code-review` is the only case that needs one more mandatory flag:
   `--checkout <path>`. It points to a worktree that is actually checked out at the `candidate_commit` of the
   dispatch (see the clean-room QA lane below: review needs the same isolation). All other roles
   do not pass `--checkout`. Without it, the coordinator rejects `dispatch send` and shows the exact text of the
   expected flag.
4. Accept one schema-validated completion report with evidence. The coordinator saves it as
   canonical JSON and a deterministic Markdown projection. After that, the dispatch stays `reported`, and the
   batch waits for the next decision:

   ```bash
   python .harness/orchestration/coordinator.py --repo . report submit \
     --file developer-report.json
   ```
   In `checks_run[*].result`, the canonical values are `pass`, `fail`, and `not_run`; only the architect
   may use `not_run_architect_read_only`, for compatibility with old briefs.
   Architect work without a verification gate keeps `checks_run` empty.
   `pass` and `passed` are equivalent; the old `not-run` is equivalent to `not_run`. New reports
   are saved with the canonical values; old immutable reports are read without being rewritten.
   Unknown results are rejected with a `remedy` before the canonical report is written. Fix the
   staging file according to the evidence and repeat the submission for the same dispatch: `pass` means a
   successful command, `fail` means an unsuccessful one, and `not_run` means a command that did not run. Automatic acceptance
   treats `pass` and `passed` the same.
   A result that is admissible as evidence does not mean the report is accepted automatically.
   Before the decision, the coordinator checks the report again, so an old recorded report
   with an unknown result is also refused. Do not edit an immutable report;
   for an already recorded report or a stopped batch, the operator chooses an existing
   recovery route separately. After `resume-stop`, the `auto` policy does not return.

   Before the next dispatch, the coordinator records a separate decision. Under `manual_all` or with an unclean
   report, a human accepts the report, overrides the warning, or requires a retry. Under `low_risk` and with a clean
   report, the coordinator itself records `accept` with the rationale
   `Auto-accepted due to low_risk policy and clean report`, computes `next_action`, and prepares the
   next admissible dispatch. Under `milestone`, a clean report outside a milestone also receives `accept`.
   After the developer, the coordinator assesses risk, and the QA dispatch waits for a separate approval. A clean
   QA report under `milestone` waits for a human decision.

   The policy chain (`policy-decide`, `risk-assess`, `next-dispatch`) runs as separate commands after
   the report is recorded. Each command may stop: the ledger is busy, `needs_attention` is raised,
   or the batch state changed. Then `report submit` still exits with code 0. The report
   is recorded, and the response names it (`report`, `report_sha256`) and carries a `completion` object. The object
   contains `route: "report-completion"`, `failed_step`, the state of each step (`done`,
   `already-done`, `not-applicable`, `failed`, `not-run`), `error`, `remedy`, and the exact command
   `command`. The coordinator itself runs it (`run_by: "coordinator"`), not the worker:

   ```bash
   python .harness/orchestration/coordinator.py --repo . report complete --dispatch <dispatch-id>
   ```

   `report complete` is idempotent: each step is derived from the ledger, so an already recorded decision,
   risk assessment, or next dispatch is not repeated, and a repeated run writes nothing.
   The command repeats only the policy recorded at `report submit` (`auto_accept_policy` in the dispatch
   status). It never records the report again and never creates a dispatch for the role that submitted the report.
   The `risk-assess` step assesses the candidate of the report: for the developer, these are its `commit_sha` and
   `changed_files`; for read-only verification, it is the candidate pinned in its dispatch, with the files from the
   diff against the batch base, as `risk assess` counts them. A step that needs a human stops with the
   remedy of that step. For a report left to a human, all steps are `not-applicable`. Do not
   submit the report again: it is already recorded.

   A manual decision looks like this:

   ```bash
   python .harness/orchestration/coordinator.py --repo . batch decide \
     --batch <batch-id> --decision accept --approved-by 'имя утверждающего' \
     --approved-at <approval-time-utc>
   ```

   A developer report against a brief with a `commit_plan` carries `commit_map`. These are the pairs
   `{commit_sha, plan_entry_id}` for every commit after `snapshot_commit` (for a rebase, after
   `rebase_target`). In an initial and a rebase report, this is a relation. A commit that closes several
   entries yields one pair for each entry. An entry closed by several commits yields one pair for
   each commit. A mapping that is not one-to-one (a merged commit, a split or unclosed entry) is a
   divergence. Then the report must carry `dod_coverage`, exactly one record for each DoD item:
   `{"dod_item": <n>, "commits": [<sha>, ...]}` with commits of this dispatch, or
   `{"dod_item": <n>, "not_covered": "<reason>"}`. The report must also carry a non-empty
   `divergence_justification`: what was merged, split, or added, and why. For a one-to-one mapping,
   `dod_coverage` is optional (the coordinator derives the coverage from the `covers` of the plan), and
   `divergence_justification` is rejected.
   `report submit` and `batch decide` reject structural errors, each with a remedy:
   an unmapped created commit, a commit not from this dispatch, an unknown entry, a repeated pair,
   a divergence without `dod_coverage` or without a justification, coverage without an item, with another item, or
   another commit, `not_covered` without a reason. In `developer-retry` and in reports of other roles, these two
   fields are rejected.

   `report submit` also checks `dod_coverage` against `commit_map` and the `covers` of the plan. The command rejects
   a DoD item that is declared covered by a set of commits if `commit_map` maps none of
   them to an entry that has this item in `covers`. The remedy names the item, the declared commits, and the
   plan entries that cover this item. The reverse direction is admissible. `not_covered` with a reason
   is also valid for an item that the mapping formally covers. Like any `not_covered`, it
   requires a manual decision. A one-to-one report without `dod_coverage` gets its coverage from `covers` and does not
   need this check.

   A justified divergence with full coverage does not by itself make a report unclean. Under
   `low_risk` and `milestone`, the coordinator automatically accepts a report that is clean in other respects. The decision
   record receives `commit_plan_divergence` (`developer_dispatch_id`, `justification`,
   `merged_commits`, `split_entries`, `unclosed_entries`). A manual acceptance receives the same record.
   Any `not_covered` item makes the report unclean under any policy. Auto-accept does not fire,
   and `--decision accept` is rejected. You can accept the report only through `--decision override-warning` with
   a `--note` other than `none` (the decision receives `dod_not_covered` with the reasons). Otherwise, you can
   return the report through `retry`. Going outside the scope is a warning, not a refusal. For a completed developer
   report with `changed_files` outside `write_paths`, `report submit` records it. `batch decision-packet`
   shows these paths in `scope_warnings`. Such a report is not accepted automatically under any
   policy, and `--decision accept` is rejected. You can accept it only through
   `--decision override-warning` with a `--note` other than `none` and an explicit `--approved-by`. The decision
   receives `scope_warnings`, and the override adds a coordinator finding. The next code-review brief
   carries these paths as an item that the review must close. Accepting an architect report with
   `--commit-plan-file` succeeds if the `expected_paths` of the plan go beyond the `allowed_paths` of the batch.
   Then the packet (with the same `--commit-plan-file`) and the decision contain the same `scope_warnings`. The ban
   on writing outside `write_paths` for the worker itself, the `changed_files` check in the checkpoint, and the reports of
   other write roles remain strict.
   `batch decision-packet` shows `dod_coverage`, `dod_coverage_source` (`report` or
   `derived`), and `commit_plan_divergence`. The code-review brief carries the `commit_plan_divergence` of the
   latest accepted initial or rebase developer report (for other roles, the field is `null`). With
   it, the reviewer checks that the commit boundaries stayed reviewable.

   A defect that the coordinator found in a clean developer report does not spend a developer-retry before review
   (the `carry-over` route). Retrying a developer report without accept is an exception only for an unfulfilled
   DoD item or a change outside the scope. In other cases, the report is accepted with findings:

   ```bash
   python .harness/orchestration/coordinator.py --repo . batch decide \
     --batch <batch-id> --decision accept --approved-by 'имя утверждающего' \
     --approved-at <approval-time-utc> --findings-file .harness/.sandboxes/scratch/findings.json
   ```

   The file lies in the repository or one of its worktrees and contains exactly one key,
   `{"findings": [...]}`. Each finding contains exactly three fields: a non-empty `summary`, `files`, a
   non-empty list of unique paths from the repository root in POSIX form (without a leading `/`, backslash,
   or `..` segment), and a non-empty `expected_evidence`: what the review uses to confirm the closure.
   The text of a finding is passed to a role, so it is in English. The flag is admissible only with `accept` or
   `override-warning` on a completed developer work report. Otherwise, the decision is rejected with a remedy, and the
   batch does not change. The coordinator records each finding in the batch append-only as a
   `carried_items` record: `item_id` `coordinator-finding-<n>` (the sequence number in the batch), `source` (`kind`,
   `dispatch_id` and `report_sha256` of the accepted report, `candidate_commit`), `summary`, `files`,
   `expected_evidence`, `attached_at`, `attached_by`, and `record_sha256`. The coordinator checks
   this hash on every read of the batch.

   The auto-accept policy does not take a findings file. After it, `batch carry-over` adds the findings:

   ```bash
   python .harness/orchestration/coordinator.py --repo . batch carry-over \
     --batch <batch-id> --findings-file .harness/.sandboxes/scratch/findings.json
   ```

   The command creates no dispatch and does not change the candidate, so a human does not approve it. It
   records the coordinator decision `carry-over` with `approved_by: policy:carry-over`. It attaches the findings
   to the latest accepted developer work report. A batch with `next_action: qa` moves to
   `code-review`. The command is rejected with a remedy: while any report waits for a decision; if the batch has no
   accepted developer work report; if a dispatch was already created after it that was not cancelled and not
   moved to `abandoned` by `batch resume`. For an unsent code-review (or a qa created by the
   low_risk chain), the remedy is `dispatch cancel` and a repeat of `batch carry-over`. For a sent one, the remedy is to
   report the defect when deciding its report. For an already decided report, attach the finding through
   `batch decide --findings-file` when accepting the next developer report.

   While a finding is open, the risk assessment sends the candidate to `code-review`, even if no trigger
   matched (the `review_required` of the assessment record does not change). A finding is closed when a code-review
   whose brief carried it is accepted (`accept` or `override-warning`). A review retry leaves it open.

   Every brief carries a `carried_items` section, the shared channel for carried items. It is an object: the key is
   the source kind (`coordinator-finding`, `review-finding`, `incomplete-item`), and the value is a list of
   `{item_id, source, summary, files, expected_evidence}`. An empty channel is `{}`. The code-review and
   developer work briefs carry all open `coordinator-finding` items. A developer brief that answers a `retry`
   of a code-review with the `fix-forward` route also carries the Standards and Spec axis findings of that review
   as `review-finding` (`item_id` `review-finding-<n>`; `source` is `dispatch_id`, `report_sha256`,
   `axis`, `severity`; `files: []`; `expected_evidence` is the evidence of the finding). Therefore the single
   developer-retry closes both groups and spends `retry_policy.max_developer_retries` once.
   Accept with findings and `batch carry-over` do not spend the budget. A non-empty section enters the transition as
   `carried_items_sha256`. Therefore a finding added after `dispatch propose` needs a new
   approval.

   The code-review report accounts for each brief item in the optional `review.carried_items`:
   `[{"item_id": ..., "status": "closed" | "open" | "unverified", "evidence": ...}]`. `report submit`
   rejects an item that the brief did not carry, a repeated item, an unknown status, and empty evidence.
   Omitting an item is structurally admissible, but an omission, like `unverified` and `open`, is a carried gap, and
   such a report is not clean: the policy does not accept it automatically, and `--decision accept` is rejected.
   `override-warning` requires a `--note` other than `none` and records `carried_items_gap`
   in the decision. You can also return the report through `retry`. The blocker and warning rules keep
   their priority. An `open` item is structural evidence of the `code` category, so such a retry leads to a
   developer-retry by the `fix-forward` route. `batch decision-packet` shows `carried_items`
   (each item with `source`, `summary`, `status` — for a code-review report, `omitted` for an omitted
   item — and `evidence`) and `carried_items_gap`.

   A read-only role (architect, verification, code-review, or qa) that did not complete part of the brief
   lists the unfinished items in the optional report field `incomplete_items`:
   `[{"brief_item": ..., "reason": ..., "target_role": ...}]`. The text is written in English because the
   item goes into the brief of the next role as agent-to-agent text. Each string is non-empty and at most
   1600 characters long. `target_role` is the report role itself (for a narrowed retry) or a later role:
   architect → architect, developer, code-review, or qa; verification → verification, code-review,
   or qa; code-review → code-review or qa; qa → qa. An item that a tool prevented from running
   (for example, a safety classifier) carries its own `tooling_blocker` of the same shape as the one in the
   report, under any outcome. `report submit` rejects, with a remedy, the field on a write role, an item without
   `reason`, an unknown or inadmissible `target_role`, Cyrillic, and an invalid `tooling_blocker`.

   A report with a non-empty `incomplete_items` is not accepted automatically under any `approval_policy`, and
   a plain `accept` or `override-warning` is rejected. A human chooses one of two decisions:

   ```bash
   python .harness/orchestration/coordinator.py --repo . batch decide \
     --batch <batch-id> --decision accept --approved-by 'имя утверждающего' \
     --approved-at <approval-time-utc> --carry-incomplete
   python .harness/orchestration/coordinator.py --repo . batch decide \
     --batch <batch-id> --decision retry --approved-by 'имя утверждающего' \
     --approved-at <approval-time-utc> --narrowed
   ```

   `--carry-incomplete` (with `accept` or `override-warning`) records a `carry-over` routing record with
   `carried_item_ids` (`incomplete-item-<n>`, numbered continuously across the batch). `next_action` changes as
   for any accept of this stage. The batch does not store the items. The work brief of the target role reads them from the
   immutable report and carries them in `carried_items` as `incomplete-item`. This continues until a
   dispatch of this role whose brief carried them is accepted (`accept` or `override-warning`). A retry leaves the
   item open. For code-review, an open item sends the candidate to code-review, even if the risk
   assessment found no triggers. The flag is rejected without items, with another decision, and when at least
   one item targets the report role itself. Only a narrowed retry closes such an item.

   `--narrowed` (only with `retry`) repeats the same stage on the same SHA. The brief of the new dispatch carries
   only the items of the report. The Definition of Done in the brief stays the full DoD of the batch. The route is
   `narrowed-retry` with `reason_category: null`. If at least one item carries a `tooling_blocker`, the route is
   `tooling-retry` with the category `tooling` (confirm the false positive and open a bug ticket against the
   tool; the attention `tooling-retry-repeated` limits a series). The budget
   `retry_policy.max_developer_retries` is not spent, and the new dispatch is approved according to
   `approval_policy`. `--narrowed` is rejected: for developer and publish; for a report without items;
   together with `--reason-category` or `--retry-role developer`; and with structural evidence of another
   route. Such evidence is a finding or a warning/blocker severity on an axis, an open carried item, a
   failed check, or a shifted candidate. A retry without `--narrowed` ignores the items and is routed as
   before.

   The `source` of an `incomplete-item` item contains the `dispatch_id` and `report_sha256` of the report, its `role`,
   `target_role` (the role whose brief carries the item), `route` (`carry-over`, `narrowed-retry`, or
   `tooling-retry`), `reason`, and `reason_category` (`tooling` for an item with `tooling_blocker`, otherwise
   `null`). `summary` is the `brief_item`, and `files` is empty. `batch decision-packet` shows the
   `incomplete_items` of the report; without `--findings-file`, it adds `route_preview["carry-over"]`,
   the record that `--carry-incomplete` will make, or a refusal. `batch decision-packet --narrowed`
   shows the route of the narrowed retry.

A minimal manual brief stores the ticket and dispatch ID, the role and its access, the selected
profile/model/effort, the allowed paths (write scope), the issue branch/worktree, the DoD, the prohibitions, the commands,
the dependencies, and the approval. For a write role, the completion report must include the commit SHA, the exact changed
files, the results of all checks, the risks, the blockers, and the next coordinator decision. A write role may
stop before any changes (for example, because of a risk trigger when a required gate is missing). Then the
coordinator accepts an honest report with `outcome: blocked`, empty `changed_files`, and a `commit_sha`
bound to the verified checkout (`snapshot_commit`). The coordinator registers the report and
returns a `decision_packet` with a `recovery_route` (`retry`, `block`, `abandon`). It does not register an unfinished
candidate. For a read-only role, the report states
`not applicable — read-only role` instead of a SHA.

New facts do not change a sent brief: the coordinator adds a separate decision with evidence. If the
scope, DoD, assignment, or proof changed, the current dispatch ends and a new one is created.
A repeat after `blocked` or `failed` is also a new dispatch with a new ID and brief.

## Observing a launch and a ready unsubmitted report {#observing-a-launch-and-a-ready-unsubmitted-report}

The shipped example is `.harness/orchestration/adapters/claude_code.py`; `claude` or `codex`
by themselves are not adapters. From the Harness console, the selected session opens first,
then the confirmed send runs. For an intentionally hidden launch, pass
`--adapter-arg=--visibility=background`. The example keeps native permissions and hooks.
A check of the parent does not confirm access of the Bash tools inside the worker: the native probe must
pass before implementation. A permanent access denial requires preparing the environment, not identical retries.
Change the sandbox profile before propose/approval; global settings are not disabled.

`dispatch observe --dispatch <id> --offset <next_offset>` reads the existing events locally.
Opening the panel, refreshing, and reconnecting do not call the model; you can close the window without stopping the
worker. A human confirms a native-permission request; it does not give dispatch approval.
By default, the first self-report is awaited for 120 seconds, regardless of heartbeat stale. For a proven
early completion: auto-report → auto-decide → human resume-stop --restart. A repeated
launch keeps the original contract; on drift, a new proposal is needed.

For a ready report that the worker could not submit, the coordinator uses the original staging file:
`report submit --file <path> --relayed-by <sender> --relay-reason <exact-error>
--source-sha256 <hash-original-bytes>`. The worker JSON is not edited, and provenance is written separately.
Fail/not_run stay as they are; make lint does not replace make verify. If the report is already recorded,
use report complete when the submit result points to that route. Comparing a failure
with the base SHA is separate evidence, not a retroactive fix of the original report.

## Optional external adapter {#5-optional-external-adapter}

The `backend-orchestration` capability ships two standard adapters:
`.harness/adapters/claude_worker.py` for Claude Code and `.harness/adapters/codex_worker.py` for Codex.
`harness init`/`adopt` install them, and an ordinary `harness update <repo>` restores
missing files and updates the managed versions. The console settings offer the states,
plan preview, and explicit confirmation; the current capability set is preserved.

For an already approved dispatch with `external` chosen, use the adapter of the assigned runtime:

```bash
python /path/to/project/.harness/orchestration/coordinator.py --repo /path/to/project dispatch send --dispatch <dispatch-id> --adapter /path/to/project/.harness/adapters/claude_worker.py
```

For Codex, replace the adapter path with `/path/to/project/.harness/adapters/codex_worker.py`.
The coordinator runs the `.py` file with its own Python in the worker checkout. The model and effort parameters
come from the immutable brief, and the lifecycle prompt is passed through stdin. Claude limits
additional access to the incoming reports directory and uses the native `allowed_tools`;
Codex passes this list in the prompt, and selects the sandbox by `access`: `read-only` or
`workspace-write`. This is not a native Codex tool filter.
Both adapters reject `qa`, `purpose: publish`, another transport, and a missing `allowed_tools`.
An early worker exit, even with code `0`, returns a launch error and the end of the log.
To check a command without a model, there is `dispatch --dry-run`; for a test executable,
`--claude-bin`/`--codex-bin`; for developer-retry lines, `--extra-prompt-file`.

For `transport: "external"`, the project passes `--adapter <path>` to `dispatch send`. This is a transport-only
boundary. The coordinator passes the approved immutable brief to this executable through `--repo` and
`--brief`.
The adapter is responsible for starting the worker in the chosen environment. It does not choose a scope, does not accept a report,
does not plan the next dispatch, and does not merge a PR. After starting, the worker returns a completion report
under the general rules of section 4. The access and launch environment checks belong to the project adapter.

## First pilot and the source of rules {#6-first-pilot-and-the-source-of-rules}

Do not set token limits or a "right" level of parallelism by eye. In the first pilot period,
record for each closed ticket agent starts, tokens per batch, quality-gate wall time, and
post-integration defects, including the source and the missing data. The form and the common counting rules
are in `.harness/orchestration/pilot.md`.

The full normative source is `.harness/orchestration/playbook.md`, and the boundaries of individual roles are
in `.harness/orchestration/roles/`. If the convenience of a specific runtime conflicts with this
contract, the manifest, the immutable brief, and the explicit approval take priority.

The architectural contract of the route is recorded in full in
[ADR 0003](https://github.com/PVMalove/agent-harness-next/blob/master/docs/adr/0003-orchestration-core.md): an opt-in capability, a separate
approval for dispatch, review and QA for one SHA, local sanitized evidence, and an adapter
only for transport. Turning `/implement` into a coordinator-driven pipeline by default, model
self-report, the dispatch watchdog, per-role transport, and zero-config defaults are recorded in
[ADR 0005](https://github.com/PVMalove/agent-harness-next/blob/master/docs/adr/0005-implement-pipeline.md).
