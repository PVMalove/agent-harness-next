# Developer: retry, fix-forward and rebase

Read this when the brief is a `developer-retry` or carries a non-null `rebase_target_commit`.

A developer retry receives, besides its brief, the retry handoff (the playbook's "Developer-retry
handoff") and its starting files. Start from the handoff's findings and starting files: they replace
re-reading the earlier work, and the existing candidate history is the code to extend.

A developer-retry is a fix-forward: it continues from the brief's `snapshot_commit` and adds new
commits on top of it. Never amend, squash, reset, rebase or force-push `snapshot_commit` or a commit
below it. `report submit` refuses a report whose `commit_sha` does not descend from
`snapshot_commit`; its remedy is to recover the rewritten commits from `git reflog`, re-apply the fix
as new commits without amend or squash, and report the new HEAD. Only a retry under a rebase
target is measured from that target instead. Two sources share the name `rebase_target_commit`: the
brief's field, non-null only on a `rebase-fix-forward` brief or on a superseding batch's
developer-retry brief (below), and, on a legacy stale-base record (`base_rebase_required`, written
by a runtime that still checked base freshness), the batch's target that the prompt names; the
brief field is `null` on that legacy rebase brief.

A developer-retry brief with a non-null `rebase_target_commit` (route `rebase-fix-forward`: the
integration base moved ahead and a human approved the new tip; or a superseding batch whose
snapshot does not contain its integration base yet) rebases and fixes in the same dispatch. First
rebase the commits above the old base onto exactly that target, never onto a newer
tip: `git rebase --onto <rebase_target_commit> $(git merge-base <snapshot_commit>
<rebase_target_commit>)`. Resolve a conflict inside the zone; a resolution that changes a commit is
allowed. Then add the fix commits on top. Its `commit_map` accounts for every previous-candidate
commit (after that merge-base, up to `snapshot_commit`) exactly once: its rebased copy as
`{"commit_sha": <copy>, "rebased_from": <original>}`, which inherits the original's plan entry and
names none, or a commit the rebase did not carry (for example, one already upstream) as
`{"rebased_from": <original>, "dropped": "<reason>"}`. Every commit after the target appears
exactly once: a rebased copy as above, a new commit as `{commit_sha, plan_entry_id}` under the
strict retry rule below. `changed_files` and `carried_item_closure` are measured from the target,
and so are those of a later retry of this report until it is accepted.
The coordinator compares each `rebased_from` pair by `git patch-id`; a mismatch does not refuse the
report but is shown for delta-review. A missing, repeated or unknown previous-candidate commit, a
copy that is its own original (a merge of the target instead of a rebase) and an empty `dropped`
reason are refused, and a brief without a target refuses `rebased_from` and `dropped` entries.
