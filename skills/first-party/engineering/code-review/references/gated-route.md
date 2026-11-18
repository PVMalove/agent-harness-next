# Review inside the gated /implement route

For the gated `/implement` route, review also consumes the coordinator's pinned Context Package and
candidate SHA. Review verifies that pinned candidate even if the integration base moved ahead: there
is no mandatory base-freshness gate. PR preparation on a moved base goes through
`integration refresh`, which rebases only the batch's issue branch onto the exact target SHA. A
delta-review is either test-only (after a Warning: a new candidate with a test-only diff, brief
field `delta_review_of`) or after a fix-forward (brief section `delta_review_scope`, chosen by the
coordinator). A fix-forward delta-review reviews both axes on the delta alone and relies on the
prior review's report for the rest of the candidate. The coordinator escalates it to a full review
when the candidate or the new commits match a risk trigger the prior review did not see, change a
file outside the carried items, break a rebased copy's `git patch-id`, drop a previous-candidate
commit, or add no commits. Either delta-review is an independent review dispatch, never an in-place
replacement of the original evidence.
