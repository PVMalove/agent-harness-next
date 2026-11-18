---
name: developer
description: Implements an agreed change in the current issue branch within the ticket's scope and reports changes, checks, unverified items, risks and blockers. Use for standalone implementation outside a coordinator dispatch, or when a calling skill such as fast-implement hands over its implementation step; never commits, pushes, or opens a pull request.
---

# Developer

Implement one agreed change in this session and finish with a human-readable evidence report. This
skill is separate from the coordinator's `developer` role: inside an orchestration dispatch, follow
`harness/orchestration/roles/developer.md` and the brief instead; this skill neither repeats nor
widens them.

## Prerequisites

Check every prerequisite before editing any file. If one is missing, stop: make no change, and
return the evidence report with an empty Changes section and a blocker that names the missing
prerequisite.

1. **A task with acceptance criteria.** A named ticket or an explicit scope from the user states
   what is done. When this repository defines an "Issue First" rule (for example in
   `docs/agents/git-workflow.md`), the task must be an existing ticket.
2. **Readable project settings.** `.harness/project.json` is readable and gives `branch_pattern`
   and `base_branch`.
3. **An issue branch.** The current branch matches `branch_pattern` and is neither `base_branch`
   nor an `integration/*` branch.

Uncommitted changes that belong to someone else are not a stop: note them and preserve them.

## Scope

Change only the files the task needs. When the ticket has `## Relevant Files (Discovery Context)`,
`## Contract touchpoints` or `## Out of scope`, they set that scope; a path outside them needs the
human's approval first. Do not refactor, reformat or "improve" adjacent code. When the task needs a
change outside its scope, ask the human; when no human can answer, report it as a blocker.

## Implementation

Agree the requirement and the public seam with the human before the first test, then use `/tdd` at
that seam. When the calling skill selected a test-author cycle, follow `../tdd/references/test-author.md`.

## Completion

The work is complete when every acceptance criterion is implemented and its `Verify` command, the
targeted tests, and the lint and typecheck commands from `qa_gate_commands` in
`.harness/project.json` have run, or are listed as unverified with the reason.

This skill never commits, never pushes, never opens a pull request, never runs code review and never
changes tracker labels. The calling skill or the human decides those steps.

## Evidence

Finish with a report in chat, in the project's language, with these five sections in this order.
Write an empty section as "none" in that language.

1. **Changes:** each changed file and why it changed.
2. **Checks:** each command run and its result: pass, fail or not run.
3. **Unverified:** what no check proved, with the reason.
4. **Risks:** residual risks for the reviewer.
5. **Blockers:** what stopped the work, including a missing prerequisite.
