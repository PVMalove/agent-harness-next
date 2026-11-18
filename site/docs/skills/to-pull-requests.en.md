# /to-pull-requests — PR, ticket closure and release

Run `/to-pull-requests <ticket>` manually (in Codex, use `$to-pull-requests`) after `/implement` or
`/fast-implement` pushed the issue branch. The skill opens the PR/MR only after your separate
confirmation. Once you confirm the merge, it closes the ticket, unblocks dependent tickets and removes
the worktree. The skill itself never merges.

## Resuming

The merge confirmation usually comes in another session. Step 0 finds the PR/MR of the current branch
(`gh pr list --head <branch> --state all`, on GitLab `glab mr list --source-branch <branch>`): without
a PR the skill starts at step 1, with an open PR it goes to verification and the handoff, and with a
merged one to the merge checks, the ticket closure and the cleanup.

## Child ticket PR

1. The target branch comes from the ticket's `## Integration Branch` or the local ticket's
   `**Integration branch:**` line, otherwise it is `base_branch`.
2. The branch must be clean, match `branch_pattern` and equal its upstream branch.
3. QA first, then confirmation. Without the backend-orchestration opt-in, and for `pipeline::fast`,
   the skill runs `/qa-gate`. In an opt-in project it validates the accepted QA evidence of the exact
   SHA and calls `integration next` per `references/integration-route.md`, part A, instead of
   rerunning QA.
4. The PR body follows the `git-workflow.md` §3 template and is built from the ticket and the
   verification evidence, not from the diff alone. Under Verification, each `Action -> Verify`
   criterion appears with its command and result; a criterion without evidence goes under Not
   verified & risks. The ticket's `Out of scope` and the epic's Non-Goals state what the PR
   deliberately does not change.
5. The separate readiness question names the QA result and, in an opt-in project, `candidate_sha`,
   `target_sha` and `qa_source`. PR metadata follows the "Project-Only Metadata" rule of §1.
6. A `task-report::required` report is published in the `## Completion report` format of
   `project-memory.md`; otherwise `memory sync` skips it.
7. After the PR opens in an opt-in project, part B of `references/integration-route.md` collects CI
   through `integration collect-ci` or runs `integration local-qa`. With
   `verification_plan_policy.ticket_diff_selection` on, a ticket PR into `integration/*` is confirmed
   by the run of its own diff (`ticket-diff`, CI `verify-light`), and the `light_check` reason never
   confirms a `full` pair.

## After the merge

The skill checks the merge and, for an opt-in project, the tree of the merge commit
(`--merge-commit`, `merge-tree-mismatch`). It then closes the ticket or verifies its auto-close, and
moves to `status::ready` the tickets that no longer have an open blocker. Drafts in `docs/tasks/` are
not tickets. A managed worktree is removed with `coordinator.py worktree remove`, a session worktree
with the runtime's tool. When the sandbox blocks the removal, the skill hands you the command. When
the epic's last child ticket closes, the skill offers `/to-pull-requests --release <epic>`.

## Release (`--release <epic>`)

Following `references/release.md`, the mode opens the PR of the epic's integration branch into
`base_branch`. It checks that every child ticket is closed, runs the full `/qa-gate` on the
integration branch, and checks the epic criteria against evidence on the same SHA. The release PR
lists child PRs and the results by epic criterion. Missing evidence for a required criterion
blocks the release before the confirmation request. The separate confirmation applies to the
verified SHA. After the confirmed merge, the skill closes the epic and
offers `/delivery-stats <epic>`. This mode never changes `CHANGELOG.md` or the project version.

![PR continuation after an accepted publish](../diagrams/previews/pr-continuation.workflow.png)

[Source SKILL.md](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/to-pull-requests/SKILL.md)
