---
name: to-guide
description: Turns a hitl ticket into a step-by-step manual implementation guide with ready-to-paste prompts for an AI IDE (Cursor, Copilot Chat). Use explicitly for a ticket a human will code by hand; use /fast-implement or /implement for afk tickets. Writes only the guide and the ticket's claim and status, never code.
disable-model-invocation: true
---

Invoke only on an explicit request (`/to-guide`, or `$to-guide` in Codex). This is the `hitl`
counterpart of `/implement` and `/fast-implement`: instead of an agent writing the code, the human
gets a navigator's checklist. Coding, code review, `qa-gate`, and the PR stay with the human; the
guide names the exact commands for them. Never edit production code, tests, or the ticket's scope.
On GitLab, every `glab` command takes `-R <project-url>` and every `glab api` call is written
`GITLAB_HOST=<host> glab api projects/<project-id>/...`; the placeholders are defined in
`docs/agents/issue-tracker.md` → GitLab → Conventions.

## Check the ticket

1. **Read it.** Fetch the issue number, URL, or `.scratch/<feature>/issues/NN-*.md` path the user
   names (see `docs/agents/issue-tracker.md`). If it is `status::blocked`, check its blockers the way
   `/fast-implement` does and stop if any is open. If it is `status::specs`, or lacks `hitl`, say so
   and ask whether to proceed: this skill expects a fully specified, human-routed ticket
   (`docs/agents/triage-labels.md`).
2. **Take its scope.** Start from the ticket's `## Relevant Files (Discovery Context)` and
   `## Contract touchpoints`, verify them in the code, and keep `## Out of scope` out of the guide.
   Use the parent specification's accepted decisions and the project's glossary and ADRs. If the
   work needs a file outside that scope, name it in the guide as needing the maintainer's approval.
3. **Claim it.** Assign the ticket to the maintainer with the claim of
   `docs/agents/issue-tracker.md` → Wayfinding operations → Claim before any other write, so a
   concurrent session does not pick the same ticket.
4. **Mark it in progress.** Replace the current `status::*` label (`status::ready`, a cleared
   `status::blocked`, or a `status::specs` the user agreed to proceed with) with `status::in-progress`
   by `docs/agents/issue-tracker.md` → Replace the status label (`docs/agents/triage-labels.md` →
   State machine step 5; local tracker: the `**Workflow:**` line). Read the ticket back and confirm it
   carries exactly one `status::*` label. If the label write fails, stop and report it.

## Write the guide

5. Read `references/guide-template.md` and fill it. In its section 5 write only this project's
   tracker commands, taken from `docs/agents/git-workflow.md` §2 steps 6–7, and fill in `<project-url>`, `<host>`, `<project-id>`, `<target-branch>`,
   `<ID>`, `<title>` and `<slug>` with real values (`<title>` in single quotes, each apostrophe as
   `'\''`, or `''` in PowerShell); only the PR/MR number stays a placeholder. Write the whole guide,
   prompts included, in the `language` from `.harness/project.json` (default `ru`).
6. Save it under `docs/tasks/` by `docs/agents/artifacts.md` (issue ID and slug), inside the epic's
   folder when the ticket has a parent epic. If the write fails, report it and return the guide in chat.

## Rules for the prompts

- Each prompt is explicit and self-contained: the human pastes it verbatim into the AI IDE.
- Point the IDE at existing code to imitate ("follow the pattern in `<file>`").
- Keep each step small enough to compile and review on its own, like `/to-tickets` vertical slices.
- Ask for the test first in every prompt: the project requires TDD (`docs/agents/git-workflow.md`)
  whoever writes the code.
- Tie each step to the acceptance criterion it satisfies and to its `Verify` command.

## Finish

Return the guide's path and a one-line summary. Never start coding, review, commit, or open a PR.
