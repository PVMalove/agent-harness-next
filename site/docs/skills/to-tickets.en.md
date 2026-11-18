# /to-tickets — Decomposition into tickets

Run `/to-tickets` explicitly (`$to-tickets` in Codex) after `/publish-epic`. The skill splits an
approved specification into the minimum set of verifiable tickets with dependencies and execution
waves. It never changes code, tests, `CONTEXT.md`, ADRs, or the specification's decisions, never
creates branches, and never starts `/implement`.

## Input

- A specification whose status is exactly `Approved`. For a draft or open blockers in
  `## Open Questions & Risks`, the skill lists the blockers and offers to return to `/to-spec`.
- A published epic with an `## Integration Branch` section. If it is missing, the skill offers
  `/publish-epic`.
- Without a specification, the skill first agrees on the missing requirements and the path list.
  Such tickets have no parent epic and start from `base_branch`.

## Decomposition rules

- Tickets name only paths from the spec's `## Relevant Files (Discovery Context)` and
  `## Surgical File & Contract Changes`. A new path appears in the plan with its reason and enters
  a ticket only after your approval.
- Items from `## Non-Goals & Rejected Alternatives` never become tickets.
- Each ticket is a vertical slice that carries its change and its checks; the build and tests stay
  green after every ticket. There are no tickets for drive-by cleanup or "all tests at the end".
- A blocking edge requires a result dependency or a requirement incompatibility. Tickets without
  blockers form Wave 1.
- `afk` tickets get a story-point score and a `pipeline::fast` or `pipeline::full` label.

## Approval and publication

Before writing, the skill checks that every requirement `R<n>` and every acceptance criterion is
covered by at least one ticket and that the dependency graph has no cycles. It then shows the
cards, waves, traceability matrix, new paths, and drafted epic sections, and waits for explicit
approval.

After approval, the skill publishes the tickets to GitHub, GitLab, or
`.scratch/<feature-slug>/issues/`, links them to the epic, and shows a summary table: link, title, wave, short summary, story
points, estimated hours from `story_points.hours` in `.harness/project.json`, and labels. If a write
fails, the complete cards stay in chat. Finally, the skill offers to start a Wave 1 ticket
manually with `/implement` or `/fast-implement`, matching its `pipeline::*` label.

[Source SKILL.md](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/to-tickets/SKILL.md)
