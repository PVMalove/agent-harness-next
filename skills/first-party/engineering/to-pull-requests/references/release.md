# Release mode (`--release <epic>`)

Read this file when the developer runs `/to-pull-requests --release <epic>`. It opens the release
PR/MR of the epic's integration branch into `base_branch`, and after the developer confirms the merge
it closes the epic. Child tickets are not touched here: each one was closed after its own merge into the
integration branch. This mode never edits `CHANGELOG.md` or the project version.

GitLab conventions, the `!<iid>` and `#<iid>` references and the one-command-per-shell-call rule are
the same as in the skill.

## 1. Resolve the epic and the branches

- Read the epic — GitHub: `gh issue view <epic> --json title,state,body`; GitLab:
  `glab issue view <epic> -R <project-url> -F json`. Stop when it is already closed.
- `<integration-branch>` is the value of its `## Integration Branch` section; stop and ask when it is
  missing. `<base-branch>` is `base_branch` from `.harness/project.json`.

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
a fetch, so the PR hook finds a checkout for the PR head. Never commit to it. Record the full `HEAD`
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

## 4. Prepare the body

Follow `.harness/instructions/git-workflow.md` §3 and store the body at
`.harness/.sandboxes/pr_body/pr-body-<epic>-release.md`. The summary comes from the epic. Under What
changed, write one line per child: `#<pr> <title> (#<ticket>)`. Under Verification, give the `/qa-gate`
result, the results by epic criterion and the release candidate SHA. Under Not verified & risks,
list unverified criteria, including the legacy case above, children without a merged PR, and any
check that did not run. Choose the footer (`Closes #<epic>` or `Related to #<epic>`) by
`.harness/instructions/git-workflow.md` §2 step 6 → Ticket footer, with `<epic>` for `<ID>` and `<base-branch>`
as the target.

## 5. Confirm and open

Ask the developer for explicit, separate confirmation that the release PR may be opened; state the
release candidate SHA, the QA and epic acceptance results, and the child list. Stop for their
answer. After approval, fetch and recheck that both the local and remote integration refs match the
release candidate SHA. If either changed, repeat verification and request fresh confirmation.
Then, from the checkout of part 3, with the epic title as `<title>`:

- **GitHub:** `gh pr create --base <base-branch> --head <integration-branch> --title '<title>' --body-file <path>`.
- **GitLab:** `glab mr create -R <project-url> --source-branch <integration-branch> --target-branch <base-branch> --title '<title>' --description-file <path> --yes`.

Delete the body file only after the command succeeds. Return the link and wait for the CI of the PR:
GitHub `gh pr checks <n>`, GitLab the pipeline of the MR. Never merge it.

## 6. After the merge

Act only after the developer confirms the merge.

- Check the merge, then close or verify the epic by its footer, as
  `.harness/instructions/git-workflow.md` §2 step 7 → Close the ticket after merge describes, with `<epic>` for
  `<ID>` and `<base-branch>` as the expected target.
- Offer `/delivery-stats <epic>`. Never delete `<integration-branch>`; that is the developer's call.

## Local markdown tracker

Read the published spec from `.scratch/<feature>/spec.md`. Check that every ticket in
`.scratch/<feature>/issues/*.md` reads `**Workflow:** done` and use those files as the references
to the work. Run part 3 using the local integration ref if there is no remote. In place of the PR
body, show the criterion results before asking for confirmation. Recheck the integration ref against
the release candidate SHA
before asking the developer to merge `<integration-branch>` into `<base-branch>`. If it changed,
repeat verification and request fresh confirmation. After the developer confirms the merge, require
`git merge-base --is-ancestor <release-candidate-sha> <base-ref>` to succeed and offer `/delivery-stats`.
