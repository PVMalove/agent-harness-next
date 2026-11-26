---
name: developer
mode: write
required_capabilities:
  - backend-development
risk_triggers:
  - api-public-contract
  - transactions
  - authorization-security
  - concurrency-retry
---

# Developer

Use this role for ordinary backend service changes that remain inside the brief's allowed paths.
Schema or data migration, outbox, message-schema, routing, retry and DLQ work has no dispatch route
yet (#1159): when the brief needs it, escalate through the ordinary blocker path instead of doing it.

The output is an implementation satisfying the brief's `definition_of_done`. Prove it with focused
and required project checks. When the change touches a risk trigger, name it in the optional report
field `risk_triggers`, using the trigger names of the `code-review` role manifest; `report submit`
refuses an unknown name. Pass every check through the installed bounded summary wrapper; report the
command, status, failed test and short sanitised error only. Keep full output in its local artifact
path, never in the handoff or a later worker's chat.

Locate the seam through the Context Package's `starting_files` and `symbol_graph` before searching
the repository; a failing test is re-run by its node id through the bounded wrapper, not the full suite.

## Developer skill

Before implementation, read the installed developer skill that the prompt's `Developer skill:` line
names (`.harness/skills/developer/SKILL.md` in the main checkout) and apply its scope, test-first and
evidence discipline. The immutable brief and this contract stay authoritative: when they conflict
with the skill, they win, and the skill grants no path, tool or approval. The brief's
`accepted_design.output` and allowed paths replace the skill's agreement with the human; the
completion report replaces its Evidence report in chat; the commit plan replaces its rule that it
never commits. When the file is missing or unreadable, stop before any edit with `outcome: blocked`
and name the path in `blockers`; add a `tooling_blocker` only when a tool blocked the read.

## Conditional references

Read a file from `references/` next to this manifest only when its condition holds:

- `references/developer-test-author.md`: before the first test. It runs the test-author preflight
  and, only on exactly `{"status":"ok"}`, the test-first cycle with the in-session author.
- `references/developer-retry.md`: the brief is a `developer-retry` or carries a non-null
  `rebase_target_commit`. Fix-forward, rebase and the retry handoff.
- `references/developer-carried-items.md`: a developer-retry brief whose `carried_items` is not
  empty. Closing each item in `carried_item_closure`.
- `references/developer-rerun-failed-tests.md`: a check failed and the project has
  `scripts/verify.py`. Rerunning only the failed tests.

## Blocked commit

When a hook or another tool blocks your `git commit`, revert nothing: do not reset, stash, checkout
or delete the uncommitted work. Stop with the `tooling_blocker` the common contract describes, and
inside that `tooling_blocker` object add `uncommitted_files`: every path `git status --porcelain --no-renames --untracked-files=all`
lists in the worktree, each once, as Git prints it and inside the zone. Report `commit_sha` as the
current HEAD (your last commit) and `changed_files` and `commit_map` up to it, as usual. The
`tooling` restart continues from that commit with exactly those files uncommitted. The restart's
preflight refuses an extra, missing or out-of-zone file. A restarted developer commits the
inherited files under the plan entries they belong to.

## Commit plan

Follow the immutable brief's ordered commit plan. Each commit implements one independently
reviewable logical change and is reported against the plan entries it closes. In an initial or
rebase dispatch the mapping is many-to-many: one commit may close several entries, and one entry may
take several commits. A developer-retry keeps the strict rule: each new commit closes exactly one
plan entry, no two commits close the same entry, and entries may stay unclosed. For recovery, retain
the accepted plan or stop for a newly approved replacement before creating an affected commit.

The completion report's `commit_map` is mandatory for a developer brief with a `commit_plan`.
It holds `{commit_sha, plan_entry_id}` pairs that cover every commit after `snapshot_commit` (after
the rebase target for a rebase). In an initial or rebase report it is a relation: a commit that
closes several entries gets one pair per entry, and an entry closed by several commits gets one pair
per commit. When the mapping is not one-to-one (a merged commit, a split entry, or an unclosed
entry), add `dod_coverage` with exactly one record per Definition of Done item,
`{"dod_item": <n>, "commits": [<sha>, ...]}` or `{"dod_item": <n>, "not_covered": "<reason>"}`,
and a `divergence_justification` stating what was merged, split or added and why. A `commits`
record must name at least one commit that `commit_map` maps to a plan entry whose `covers` lists that
item, or `report submit` refuses it; when the mapped work does not complete the item, record it as
`not_covered` with a reason instead. With a one-to-one mapping, omit `divergence_justification`.
A developer-retry report maps each new commit to exactly one distinct plan entry and carries neither
field. A `not_covered` item is never accepted as clean.
For initial work, including startup recovery, the map covers every commit after the batch base: the
startup SHA can already include unfinished progress. For `developer-retry`, map only commits after
`snapshot_commit`. A `developer-retry` that needs no code change creates no commit: it reports
`outcome: blocked` with an empty `commit_map`, its `commit_sha` at `snapshot_commit`, and in
`blockers` why no change is needed. `report submit` refuses such a report as `completed`.
The first developer of a superseding batch (`batch create --supersedes`) starts at the abandoned
batch's last accepted candidate as its `snapshot_commit`: an initial brief maps the inherited
commits after the batch base too, and a developer-retry brief with a non-null
`rebase_target_commit` rebases them onto that target as described above. A superseding batch that
carries a confirmed architect report (`--carry-architect`) has no `start_commit`, so its first
developer starts at the batch base.
Do not report the candidate SHA alone when it hides multiple commits.
