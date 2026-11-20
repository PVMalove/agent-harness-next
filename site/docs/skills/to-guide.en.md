# /to-guide — Manual implementation guide

Run `/to-guide` explicitly (`$to-guide` in Codex) for a `hitl` ticket a person implements by hand.
The skill prepares a step-by-step guide with ready-to-paste prompts for an AI IDE (Cursor, Copilot
Chat). Coding, review, `qa-gate`, and the PR stay with the person; the guide names the exact
commands for them.

## Preparation

1. The skill reads the ticket and checks its blockers. If the ticket is `status::specs` or lacks
   `hitl`, it asks whether to proceed.
2. The scope comes from the ticket's `## Relevant Files (Discovery Context)` and
   `## Contract touchpoints`, verified against the code. `## Out of scope` stays out of the guide. A
   file outside the scope is marked as needing the maintainer's approval.
3. The skill assigns the ticket to the maintainer and changes its label to `status::in-progress`
   with the commands of `docs/agents/issue-tracker.md` (Wayfinding operations → Claim and Replace the
   status label).

## The guide

The guide follows `references/guide-template.md` with five sections:

1. context and constraints;
2. file map;
3. steps with prompts;
4. verification;
5. what to do after implementing: the skill takes the project's tracker commands for the footer and
   the ticket closure from `docs/agents/git-workflow.md` §2 steps 6–7 and fills in real values.

Each prompt is self-contained, starts with the test, and names its acceptance criterion and
`Verify` command. Verification comes from the ticket's `Action -> Verify` criteria or the spec's
`## Acceptance & Verification Criteria`. The guide is written in the language from
`.harness/project.json` and saved under `docs/tasks/`, in the epic folder for a child task.

[Source SKILL.md](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/to-guide/SKILL.md)
