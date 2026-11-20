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
2. The ticket label changes to `status::in-progress` with the command of
   `docs/agents/issue-tracker.md` → Replace the status label; the claim follows Wayfinding
   operations → Claim there.
3. The integration branch comes from `## Integration Branch` or the local ticket's
   `**Integration branch:**` line, otherwise from the epic.
4. When the current branch does not match `branch_pattern`, the skill creates the issue branch from the
   integration branch and pushes it by `docs/agents/git-workflow.md` §2 steps 1–2; a matching current
   branch stays the working branch.
5. The ticket's `## Relevant Files (Discovery Context)`, `## Contract touchpoints` and
   `## Out of scope` bound the change, and its `Action -> Verify` criteria are the checks. A change
   outside them needs your approval.

## Implementation and finish

The implementation steps follow the `developer` skill: the seam is agreed before the first test,
then `/tdd`, the optional test author under `tdd/references/test-author.md`, and the `Verify`
checks. `/qa-gate` runs the full suite before the PR; it runs only `qa_gate_commands`, while
`pre_qa_commands` and the QA overlays apply to `/implement` alone. The skill then asks whether to run code
review, waits for permission to commit and push, and pushes the issue branch. Finally, it offers to
run `/to-pull-requests <ticket>` manually. The ticket keeps `status::in-progress`: after the merge,
`/to-pull-requests` closes it and moves its unblocked dependents to `status::ready`.

## Test author

The skill owns the short test-author route (formerly section 6 of `docs/agents/test-author.md`): the
developer confirms the seam, the preflight runs once, and no dispatch or ledger record is created.
Without `test_paths` and `test_runner` the skill follows the usual `/tdd`. If the preflight answers
anything but `{"status":"ok"}`, the hook is missing or failed, or isolation is unavailable, the skill
continues with the usual `/tdd` in the same session, names the reason in one line, and never starts
an unprotected author. The configuration is in section 2 of the
[test-author guide](../agents/test-author.md).

[Source SKILL.md](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/fast-implement/SKILL.md)
