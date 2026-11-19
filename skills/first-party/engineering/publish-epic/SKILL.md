---
name: publish-epic
description: Publishes an approved /to-spec specification as the feature's epic, applies the epic labels, and sets up its integration branch with the session's approved glossary and ADR changes. Use explicitly between /to-spec and /to-tickets. Never changes the specification's decisions or production code.
disable-model-invocation: true
---

Invoke only on an explicit request (`/publish-epic`, or `$publish-epic` in Codex). Read
`docs/agents/issue-tracker.md`, `docs/agents/triage-labels.md`, and `docs/agents/git-workflow.md` §1
first; if a tracker file is missing, tell the user to run `harness update` and stop. Change only the
tracker, the epic's spec file and folder, and the integration branch, as approved below.

## Check the input

1. Take the spec path from the user, or find the task folder under `docs/tasks/` by
   `docs/agents/artifacts.md`. Publish only a spec whose status line is exactly
   `**Status** — Approved`. For any other status, list its blockers and offer `/to-spec`.
2. If the epic already exists (the folder is named `issue-<ID>-…` and the issue is open), do not
   publish it again; continue with the integration branch for that epic.
3. Read the required `base_branch` from `.harness/project.json`. If it is absent, stop and report
   the invalid project config.

## Approve the plan

Present the plan and wait for explicit approval before any tracker or Git command:

- the epic title and the spec file that becomes its body
- labels: `type::feature` or `type::bug` (ask when the spec leaves it unclear), `status::specs`, and
  `task-report::required` unless the user says to skip it; never `status::ready` or `epic::<slug>`
- `integration/<service-or-team>`: the branch the spec names under `## Integration Branch`, or a
  slug derived from explicit project or domain language. Never guess the slug
- the grill docs to commit, from
  `git status --porcelain --untracked-files=all -- CONTEXT-MAP.md ':(glob)**/CONTEXT.md' ':(glob)**/docs/adr/**'`.
  Include only changes made and reported by the session or expressly approved for this epic.
  Inspect each diff and exclude any path with unrelated changes. For a rename, record both paths

## Publish the epic

1. If the spec lacks `## Integration Branch`, add it with `- Branch: <name>` before
   `## Relevant Files (Discovery Context)`. Change nothing else in the spec.
2. Publish by tracker. Keep `<title>` in single quotes and write each apostrophe as `'\''` in a
   POSIX shell or `''` in PowerShell. Never pass the body inline or through a heredoc.
   - GitHub: `gh issue create --title '<title>' --body-file <spec path>`, then
     `gh issue edit <epic> --add-label '<label>,<label>'`.
   - GitLab: `glab issue create -R <project-url> --title '<title>' --description-file <spec path> --yes`,
     then `glab issue update <epic> -R <project-url> --label '<label>,<label>'`. The epic number is the
     last segment of the printed URL. GitLab silently creates a missing label, so `/setup-labels`
     must have run first. Placeholders are defined in `docs/agents/issue-tracker.md` → GitLab.
   - Local tracker: write the spec to `.scratch/<feature-slug>/spec.md` with `**Category:**`,
     `**Workflow:** status::specs`, and `**Task report:** required` lines after the title.
3. Rename a slug-only task folder to `issue-<epic>-<slug>/` by `docs/agents/artifacts.md`.

## Set up the integration branch

Run this only after the epic exists. Never reset, force-update, or delete an existing branch.
If publication succeeded but a branch step fails, report the partial state and the exact recovery
action; never recreate the epic.

- Fetch the base ref. Create the branch with `git branch integration/<service-or-team>` from
  `origin/<base_branch>`, or from the local base branch without a remote. Do not use
  `git switch -c` or `git checkout -b`: the branch-name hook allows them only for `branch_pattern`.
- If the branch already exists on the remote, do not commit to it or switch the worktree. Report
  that any grill docs stay uncommitted, with the recovery action: commit them on the first child
  ticket's issue branch and merge them through its PR.
- If the branch is absent on the remote and there are no grill docs, do not switch the worktree.
- If the branch is absent on the remote and there are grill docs, commit them before the push:
  1. Run `git switch integration/<service-or-team>`; uncommitted changes move with the worktree.
     If it refuses because of a conflict, stop. Never use `--force`, `--discard-changes`, `--merge`,
     or a reset. Report the error and the recovery: `git stash push --include-untracked`, switch,
     `git stash pop`, resolve conflicts, and continue from sub-step 2.
  2. Check the index. If it already contains changes outside the approved grill docs, leave it
     intact and report the blocker. Otherwise stage only the approved paths with
     `git add -- <path>...`; never `git add -A`, `git add .`, or `git commit -a`.
  3. Commit as a standalone command, without `&&`, `;`, a pipe, or a variable:
     `git commit -m 'docs: <short epic summary>'`, following the commit rules in
     `docs/agents/git-workflow.md`. The `block-direct-master` hook allows it only in this form, with
     an index of grill docs only, while the branch is absent on `origin`.
  4. If the hook blocks the commit, stop and do not push. Report the hook message, that the docs
     stay staged, and the recovery: remove the cause and repeat sub-step 3.
- Push a branch absent on the remote with `git push -u origin integration/<service-or-team>`.
  For a local tracker, commit as above but do not push. Without a remote, create the local branch
  only; do not commit or push, and report that the grill docs stay uncommitted.

## Finish

Report the epic number or path, the applied labels, the branch state (created, reused, pushed, or
not pushed), and the committed or uncommitted grill docs with any recovery action. Offer to run
`/to-tickets` manually. Never invoke it.
