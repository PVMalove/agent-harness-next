# Publish approved tickets

Follow this file only after the user approves the plan. Use the cards and labels exactly as approved.

## Integration branch

Read the parent epic's `## Integration Branch` section before writing any child ticket and copy its
exact branch name into every child. If the epic has no integration branch, stop and offer
`/publish-epic`. A ticket without a parent epic has neither `## Parent` nor `## Integration Branch`.

## Local tracker

- Append the approved `## Architecture invariants` and `## Implementation discipline` sections to
  the epic's `.scratch/<feature-slug>/spec.md`; the board reads that file as the epic body.
- Write one file per ticket as `.scratch/<feature-slug>/issues/<NN>-<slug>.md` (01, 02, …) with the
  local ticket file template.
- Set `**Workflow:**` to `status::blocked` when the ticket has blockers, otherwise `status::ready`.
  Set `**Execution:**` to `hitl` or `afk` (see `docs/agents/triage-labels.md`). For `afk`, write the
  final score in `**Story Points:**` and the approved label in `**Pipeline:**`; omit both for `hitl`.
  Add `**Task report:** required` unless the user said to skip it.
- `/fast-implement` finds the next ticket by each file's `**Workflow:**` field.

## GitHub and GitLab

`<project-url>`, `<host>`, and `<project-id>` are defined in `docs/agents/issue-tracker.md` →
GitLab → Conventions.

- Publish one issue per ticket in dependency order from a body file with the tracker issue body
  template. GitHub: `gh issue create --title '<title>' --body-file <path>`. GitLab:
  `glab issue create -R <project-url> --title '<title>' --description-file <path> --yes`; the ticket's
  number is the last segment of the printed URL. Keep `<title>` in single quotes and write each
  apostrophe as `'\''` in a POSIX shell or `''` in PowerShell. Never pass a body inline with
  `--body`, `--description`, or a heredoc (see `docs/agents/git-workflow.md` §1).
- Record each blocker with its reason: a native dependency on GitHub, a `Blocked by #<M>` line on
  GitLab. The text fallback carries the same edge and reason.
- Apply labels from `docs/agents/triage-labels.md`: `type::*`; `status::ready`, or `status::blocked`
  when another ticket in this batch gates it; `hitl` or `afk`; for `afk`, the approved
  `pipeline::fast` or `pipeline::full`; and `task-report::required` unless told to skip it. GitLab:
  `glab issue update <n> -R <project-url> --label '<label>,<label>'`. GitLab silently creates a
  missing label with its default color, so `/setup-labels` must have run first.
- Link every ticket to the epic through the tracker's parent link, never an `epic::<slug>` label.
  GitHub: a native sub-issue of the epic. GitLab: the `## Parent: #<epic>` section plus exactly one
  `relates_to` link created right after the ticket:
  `GITLAB_HOST=<host> glab api --method POST projects/<project-id>/issues/<n>/links -F target_project_id=<numeric-project-id> -F target_issue_iid=<epic> -F link_type=relates_to`.
  Read `<numeric-project-id>` once per batch from the `id` field of
  `GITLAB_HOST=<host> glab api projects/<project-id>`. No links are created between tickets.
- Mirror each published body to the epic folder under `docs/tasks/` as
  `tickets/issue-<ID>-<slug>.md`. Rename the folder to `issue-<epic-id>-<epic-slug>/` first if it is
  still slug-only (`docs/agents/artifacts.md`).
- Do not close or rewrite the epic. Only append the list of created ticket numbers and the approved
  `## Architecture invariants` and `## Implementation discipline` sections. Read its current body
  (GitHub `gh issue view <epic> --json body --jq .body`; GitLab the `description` field of
  `glab issue view <epic> -R <project-url> -F json`), append, save it as the epic's spec file in its
  `docs/tasks/` folder, and publish that file: GitHub `gh issue edit <epic> --body-file <path>`;
  GitLab `glab issue update <epic> -R <project-url> --description-file <path>`.
- To find takeable tickets, query the frontier as `/wayfinder` does
  (`docs/agents/issue-tracker.md#wayfinding-operations`), scoped to the epic's children.

## Summary table

Read `language` from `.harness/project.json` (default `ru`); it sets only the "What to build"
column. If the runtime can dispatch a sub-agent, send one call for the whole batch with every
ticket's title, body, and the target language, and ask for one concise sentence per ticket.
Otherwise write the sentences yourself. List every applied label.

| Ticket | Wave | What to build | Story Points | Labels |
| --- | --- | --- | --- | --- |
| <number, link, or path> | <N> | <one-line summary> | <score, or "—" for hitl> | <comma-separated labels> |
