# Code review: delta-review

Read this when the code-review brief carries `delta_review_of` (a test-only delta-review) or
`delta_review_scope` (a delta-review after a fix-forward).

## Test-only delta-review

A dispatch brief carrying `delta_review_of` (a prior, retried code-review dispatch id) and
`delta_review_axis: spec` is a delta-review: the coordinator has already verified that the prior
Standards verdict was Clean, the prior Spec verdict was Warning or Blocker, and the fix diff since
that candidate touches only test/fixture paths and matches none of this role's risk triggers.
Standards must be reported exactly as inherited — `severity: clean`, `findings: []`, and
`inherited_from` set to `delta_review_of`; Spec is always analysed again. In a brief with
`delta_review_of`, any production, security, schema, or public-contract change requires a full
independent review. This dispatch is always a new, independent session: it never resumes the prior
review's session.

## Delta-review after a fix-forward

A code-review brief without `delta_review_of` may carry `delta_review_scope`: the coordinator found
that the candidate comes from an accepted `fix-forward` or `rebase-fix-forward` developer-retry on a
candidate an earlier review of the batch judged, and chose the review's scope itself. The section
names the prior review (`prior_review`: dispatch id, `report_sha256`, reviewed candidate, base and
risk assessment), the developer-retry, `delta_base`, the `delta_commits`, the `reviewed_copies` and
the retry's `closure`.

With `mode: delta`, the new commits match no risk trigger the prior review did not see, change no
file outside the carried items, every rebased copy kept its original's `git patch-id`, and the
rebase dropped no previous-candidate commit. Review both axes on
`git diff <delta_base> <candidate_commit>` only, plus the closure of every carried item; the prior
review's report is the evidence for the rest of the candidate, so do not review that again or
restate its findings. A copy listed in `reviewed_copies` is already reviewed. Keep `review.scope`
equal to the brief's full `review_scope`, and report both axes with your own severity and findings,
never `inherited_from`. In delta mode `carried_items` also holds the prior review's `review-finding`
items and the developer's `incomplete-item` entries the developer-retry carried, whether or not the
developer closed them. This also holds when the coordinator accepted the retry through
`override-warning`. Account for each one in
`review.carried_items` like any carried item: `closed` when the delta closes it as its
`expected_evidence` asks (the `closure` names the closing commits), `open` when the defect is still
there or the developer's item is still undone, and `unverified` when it could not be checked. Unlike
an item handed to this review, a developer's `incomplete-item` may be `open`: the developer, not
this review, owes it, and its retry goes back to a developer. A defect the delta adds is an ordinary
finding on its axis. A retry of this review hands every item it did not mark `closed` to the next
developer-retry, together with its own findings.

With `mode: full`, the section lists the `escalations` that ruled a delta out (`new-risk-trigger`,
`file-outside-carried-items`, `patch-id-mismatch`, `dropped-commit` or `no-new-commits`, each with
its evidence). Review the whole candidate as an ordinary full review; the section is audit evidence
only and adds no carried item.
