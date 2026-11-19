# /fast-implement — Short implementation route

Run `/fast-implement` explicitly (`$fast-implement` in Codex) for an `afk` ticket labeled
`pipeline::fast`. The skill implements the ticket in the current session, test-first, with no
architect step, independent QA role, or coordinator gates. It never opens a PR, runs `qa-gate`, or
closes the ticket.

## Input

- A named ticket, an epic, or nothing. For an epic, the skill takes the first open, unblocked,
  unclaimed `afk` ticket with `pipeline::fast` from the lowest wave and assigns it to itself.
- A `hitl` ticket goes to `/to-guide`, a `pipeline::full` ticket to `/implement`. Without a ticket
  under an Issue First rule, the skill asks you to prepare one with `/to-spec`, `/publish-epic` and
  `/to-tickets`.

## Pre-flight

1. Open blockers stop the work.
2. The ticket label changes to `status::in-progress`.
3. The integration branch comes from `## Integration Branch` or the local ticket's
   `**Integration branch:**` line, otherwise from the epic.
4. The skill creates and pushes the issue branch.
5. The ticket's `## Relevant Files (Discovery Context)`, `## Contract touchpoints` and
   `## Out of scope` bound the change, and its `Action -> Verify` criteria are the checks. A change
   outside them needs your approval.

## Implementation and finish

The implementation steps follow the `developer` skill: the seam is agreed before the first test,
then `/tdd`, the optional test author under `tdd/references/test-author.md`, and the `Verify`
checks. `/qa-gate` runs the full suite before the PR. The skill then asks whether to run code
review, waits for permission to commit and push, and pushes the issue branch. Finally, it offers to
run `/to-pull-requests <ticket>` manually.

[Source SKILL.md](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/fast-implement/SKILL.md)
