# Integration-PR mode (`--release <epic>`)

Read this file when the developer runs `/to-pull-requests --release <epic>`, optionally with
`--target <branch>`. It opens the integration PR/MR of the epic's integration branch into
`base_branch` or into another `integration/*` branch, and after the developer confirms a merge into
`base_branch` it closes the epic. Child tickets are not touched here: each one was closed after its own merge into the
integration branch. This mode never edits `CHANGELOG.md` or the project version.

GitLab conventions, the `!<iid>` and `#<iid>` references and the one-command-per-shell-call rule are
the same as in the skill.

## 1. Resolve the epic and the branches

- Read the epic — GitHub: `gh issue view <epic> --json title,state,body`; GitLab:
  `glab issue view <epic> -R <project-url> -F json`. Stop when it is already closed.
- `<integration-branch>` is the value of its `## Integration Branch` section; stop and ask when it is
  missing. `<base-branch>` is `base_branch` from `.harness/project.json`.
- `<target-branch>` is the value of `--target <branch>` when the developer gave it, otherwise
  `base_branch`. Accept it only when it is `base_branch` or an `integration/*` branch other than
  `<integration-branch>`, and `origin/<target-branch>` exists after a fetch; otherwise stop and ask.

## 2. Check that every child ticket is closed

- GitHub: `gh api repos/<owner>/<repo>/issues/<epic>/sub_issues --paginate --jq '.[] | [.number, .state, .title] | @tsv'`.
- GitLab: `GITLAB_HOST=<host> glab api --paginate projects/<project-id>/issues/<epic>/links`; keep the
  linked issues of this project whose description carries `## Parent: #<epic>`, as in the frontier
  query of `.harness/instructions/issue-tracker.md`.

Continue only when every child ticket is closed. Otherwise list the open ones and stop: an open child is
unmerged or unconfirmed work, and the release would ship without it or with half of it.

For each closed child, find the merged PR/MR that targets `<integration-branch>` and names the ticket
in its `Related to #<n>` footer — GitHub: `gh pr list --base <integration-branch> --state merged --search "<n> in:body" --json number,title,body`;
GitLab: `glab mr list -R <project-url> --target-branch <integration-branch> --merged --search "#<n>" --output json`.
A child closed as `resolution::wontfix` has no PR; list it separately.

## 3. Verify the integration branch

Work in a clean checkout of `<integration-branch>` whose `HEAD` equals `origin/<integration-branch>` after
a fetch, so the PR hook finds a checkout for the PR head. If a clean worktree, the main checkout
included, already has `<integration-branch>` checked out, use it. If that worktree is dirty, stop and
ask the developer: Git never checks out one branch twice. Otherwise create one with
`git worktree add .harness/.sandboxes/worktrees/integration-pr-<epic> <integration-branch>`, without
`-b`, so Git creates the tracking branch from `origin/<integration-branch>`; `coordinator.py worktree
create` and `EnterWorktree` refuse an `integration/*` branch. If that command fails because
`.git/worktrees` is read-only in the sandbox or a hook blocks it, give the developer the command and
stop. Remember whether this mode created the worktree: part 6 removes only that one. Never commit to it. Record the full `HEAD`
SHA as the release candidate before running checks.

- Run `/qa-gate` there and stop on failure. A failure is fixed by new child tickets based on
  `<integration-branch>`, never by a commit on the integration branch itself.
- For an opt-in project with `verification_plan_policy.ticket_diff_selection` on, the release pair
  needs the `full` run: a `-light` check never confirms it (see "Test policy by PR target" in
  `references/integration-route.md`).

### Verify the epic criteria

- Read `## Acceptance criteria` from the child ticket bodies through the tracker CLI or the local
  ticket files.
- For each row of `## Acceptance & Verification Criteria` in the published spec, record its
  requirement ID, observable scenario, related tickets or PRs, the exact check, and the result and
  evidence on the release candidate. Use `[R<n>]` in child `Action -> Verify` lines to find related
  work. For older tickets without IDs, match the observable scenario and check when the match is
  clear. Use the spec's check directly for criteria without a clear child match.
- Reuse QA results that provide evidence for that criterion on the release candidate. Otherwise,
  run the spec's check on that SHA, including scenarios that span several tickets. For a manual
  check, record the steps and observed result. A check with no result is `not_run`.
- Treat a closed ticket or a merged child PR as a reference to the work. A criterion linked to a
  child closed as `resolution::wontfix` still needs evidence. Every criterion row is required; never
  treat one as optional. If any check failed, lacks evidence, or is `not_run`, list the affected
  criteria and stop before requesting release confirmation. Resolve the gap through a child ticket
  or an approved update to the epic spec.
- If the epic has no structured criteria, record epic acceptance as unverified and continue with
  the existing child and QA checks.

### Release Gate (opt-in project)

Run this part after `/qa-gate` only for a project with a valid `backend-orchestration` opt-in, as the
skill defines it; skip it otherwise. Every command is
`python .harness/orchestration/coordinator.py --repo . <command>`.

- Record the pair; a repeat is idempotent:
  `integration prepare --ticket "#<epic>" --branch "<integration-branch>"`. The target is
  `<target-branch>`: for `base_branch` no flag is needed, and for another `integration/*` branch add
  `--target <target-branch>`. The command checks that the epic's `## Integration Branch` section names
  the branch and records the remote heads of the branch and the target. The pair always requires the
  `full` check, so a `-light` check never confirms it. Any refusal is an operational stop: report it
  to the developer.
- Run `integration next --record <id>` with the `integration_record_id` of prepare. Continue only on
  step `confirm-pr` whose `candidate_sha` equals the release candidate and whose `target_sha` equals
  `git rev-parse origin/<target-branch>`. Its `qa_source` is `verification-pending-after-pr` until CI
  or local QA of exactly that pair passes, never `original-qa`. Handle any other `step` as
  `references/integration-route.md` describes for a record of an `integration/*` branch: stop and
  hand the data to the coordinator session, and never commit to the integration branch.
- After the PR opens, run part B of `references/integration-route.md` with `--record <id>` in place of
  `<ticket-branch>`. After the merge, check the tree as **Check the tree** in skill step 7 describes,
  with `--record <id>`.

## 4. Prepare the body

Follow `.harness/instructions/git-workflow.md` §3 and store the body at
`.harness/.sandboxes/pr_body/pr-body-<epic>-release.md`. The summary comes from the epic. Under What
changed, write one line per child: `#<pr> <title> (#<ticket>)`; never put a closing keyword
(`Closes`, `Fixes`, `Resolves`) before a child reference: each child was closed after its own merge. Under Verification, give the `/qa-gate`
result, the results by epic criterion and the release candidate SHA. Under Not verified & risks,
list unverified criteria, including the legacy case above, children without a merged PR, and any
check that did not run. Choose the footer by `.harness/instructions/git-workflow.md` §2 step 6 → Ticket footer,
with `<epic>` for `<ID>` and `<target-branch>` as the target: `Closes #<epic>` only when `<target-branch>` is
`base_branch` and that rule's default branch, `Related to #<epic>` in every other case.

## 5. Confirm and open

Ask the developer for explicit, separate confirmation that the integration PR may be opened; state
`<target-branch>`, the release candidate SHA, the QA and epic acceptance results, and the child list;
with a Release Gate record, also its `candidate_sha`, `target_sha` and `qa_source`. Stop for their
answer. After approval, fetch and recheck that both the local and remote integration refs match the
release candidate SHA. If either changed, repeat verification and request fresh confirmation.
Then, from the checkout of part 3, with the epic title as `<title>`:

- **GitHub:** `gh pr create --base <target-branch> --head <integration-branch> --title '<title>' --label pr::integration --body-file <path>`.
- **GitLab:** `GITLAB_HOST=<host> glab api projects/<project-id>/merge_requests -X POST -f source_branch=<integration-branch> -f target_branch=<target-branch> -f title='<title>' -f labels=pr::integration -F description=@<path>`. `glab mr create` writes `.git/config` before the API request, so it fails when a sandbox keeps that file read-only. The MR is `!<iid>`, with `iid` and `web_url` from the JSON the command prints.

`pr::integration` labels the PR; it never carries a `type::*` label, because it collects tickets of
several types.

Delete the body file only after the command succeeds. Return the link and wait for the CI of the PR:
GitHub `gh pr checks <n>`, GitLab the pipeline of the MR. Never merge it.

## 6. After the merge

Act only after the developer confirms the merge.

- Check the merge as `.harness/instructions/git-workflow.md` §2 step 7 → Close the ticket after merge
  describes, with `<epic>` for `<ID>` and `<target-branch>` as the expected target. With a Release Gate
  record, also check the tree as part 3 describes. If the check fails, leave the epic unchanged and tell
  the developer.
- **Target `base_branch`:** close or verify the epic by its footer with the commands of that step 7.
  Replace the epic's `status::specs` with `status::done` by the replacement rule of
  `.harness/instructions/triage-labels.md` (State machine step 5; on GitLab with `--unlabel`): before an
  explicit close for `Related to #<epic>`, right after the verified auto-close for `Closes #<epic>`. If
  the epic has no `status::specs` or more than one `status::*` label, stop and ask the developer. Offer
  `/delivery-stats <epic>`.
- **Target another `integration/*` branch:** leave the epic open and its labels unchanged, because the
  work is not in `base_branch` yet.
- **Worktree:** remove the worktree only when part 3 created it, with `git worktree remove <path>`. If it
  fails because `.git/worktrees` is read-only in the sandbox, give the developer that command. Never
  remove the main checkout or a worktree this mode did not create.
- **Integration branch:** never delete `<integration-branch>`. Ask the developer whether it is needed
  for the next epic. On a no, give the developer the deletion commands to run themselves; the agent
  never runs them.

## Local markdown tracker

Read the published spec from `.scratch/<feature>/spec.md`. Check that every ticket in
`.scratch/<feature>/issues/*.md` reads `**Workflow:** done` and use those files as the references
to the work. Run part 3 using the local integration ref if there is no remote. In place of the PR
body, show the criterion results before asking for confirmation. Recheck the integration ref against
the release candidate SHA
before asking the developer to merge `<integration-branch>` into `<target-branch>`. If it changed,
repeat verification and request fresh confirmation. After the developer confirms the merge, require
`git merge-base --is-ancestor <release-candidate-sha> <base-ref>` to succeed and offer `/delivery-stats`.
