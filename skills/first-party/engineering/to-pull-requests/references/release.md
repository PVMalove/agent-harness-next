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
  query of `docs/agents/issue-tracker.md`.

Continue only when every child ticket is closed. Otherwise list the open ones and stop: an open child is
unmerged or unconfirmed work, and the release would ship without it or with half of it.

For each closed child, find the merged PR/MR that targets `<integration-branch>` and names the ticket
in its `Related to #<n>` footer — GitHub: `gh pr list --base <integration-branch> --state merged --search "<n> in:body" --json number,title,body`;
GitLab: `glab mr list -R <project-url> --target-branch <integration-branch> --merged --search "#<n>" --output json`.
A child closed as `resolution::wontfix` has no PR; list it separately.

## 3. Verify the integration branch

Work in a clean checkout of `<integration-branch>` whose `HEAD` equals `origin/<integration-branch>` after
a fetch, so the PR hook finds a checkout for the PR head. Never commit to it.

- Run `/qa-gate` there and stop on failure. A failure is fixed by new child tickets based on
  `<integration-branch>`, never by a commit on the integration branch itself.
- For an opt-in project with `verification_plan_policy.ticket_diff_selection` on, the release pair
  needs the `full` run: a `-light` check never confirms it (see "Test policy by PR target" in
  `references/integration-route.md`).

## 4. Prepare the body

Follow `docs/agents/git-workflow.md` §3 and store the body at
`.harness/.sandboxes/pr_body/pr-body-<epic>-release.md`. The summary comes from the epic. Under What
changed, write one line per child: `#<pr> <title> (#<ticket>)`. Under Verification, give the `/qa-gate`
result of part 3. Under Not verified & risks, list children without a merged PR and any check that did
not run. The footer is `Closes #<epic>` when `<base-branch>` is the repository default branch (resolved as
in skill step 4), otherwise `Related to #<epic>`.

## 5. Confirm and open

Ask the developer for explicit, separate confirmation that the release PR may be opened; state the
`HEAD` SHA of `<integration-branch>`, the QA result and the child list. Stop for their answer. Then,
from the checkout of part 3, with the epic title as `<title>`:

- **GitHub:** `gh pr create --base <base-branch> --head <integration-branch> --title '<title>' --body-file <path>`.
- **GitLab:** `glab mr create -R <project-url> --source-branch <integration-branch> --target-branch <base-branch> --title '<title>' --description-file <path> --yes`.

Delete the body file only after the command succeeds. Return the link and wait for the CI of the PR:
GitHub `gh pr checks <n>`, GitLab the pipeline of the MR. Never merge it.

## 6. After the merge

Act only after the developer confirms the merge.

- Check the merge as in skill step 7, with `<base-branch>` as the expected target.
- `Closes #<epic>`: verify that the epic is closed; if it is still open, close it explicitly and tell
  the developer why the tracker did not. `Related to #<epic>`: close it explicitly — GitHub:
  `gh issue close <epic> --reason completed`; GitLab: `glab issue close <epic> -R <project-url>`.
- Offer `/delivery-stats <epic>`. Never delete `<integration-branch>`; that is the developer's call.

## Local markdown tracker

There is no PR or epic issue. Run part 2 on `.scratch/<feature>/issues/*.md`: every ticket must read
`**Workflow:** done`. Run part 3, ask for the same separate confirmation, then ask the developer to merge
`<integration-branch>` into `<base-branch>` themselves. After they confirm, require
`git merge-base --is-ancestor <integration-ref> <base-ref>` to succeed and offer `/delivery-stats`.
