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
   `.harness/instructions/issue-tracker.md` → Replace the status label; the claim follows Wayfinding
   operations → Claim there.
3. The integration branch comes from `## Integration Branch` or the local ticket's
   `**Integration branch:**` line, otherwise from the epic.
4. When the current branch does not match `branch_pattern`, the skill creates the issue branch from the
   integration branch and pushes it by `.harness/instructions/git-workflow.md` §2 steps 1–2; a matching current
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
run `/to-pull-requests <ticket>` manually. The ticket keeps `status::in-progress` until the merge:
then `/to-pull-requests` replaces it with `status::done`, closes the ticket and moves its unblocked dependents to `status::ready`.

## Test author

The skill owns the short test-author route (formerly section 6 of `.harness/instructions/test-author.md`): the
developer confirms the seam, the preflight runs once, and no dispatch or ledger record is created.
Without `test_paths` and `test_runner` the skill follows the usual `/tdd`. If the preflight answers
anything but `{"status":"ok"}`, the hook is missing or failed, or isolation is unavailable, the skill
continues with the usual `/tdd` in the same session, names the reason in one line, and never starts
an unprotected author. The configuration is in section 2 of the
[test-author guide](../agents/test-author.md).

## Error stops

Before calling a human about an error, the skill follows `references/error-stops.md`. The error-stop
definition, the order before a stop and the RCA phase are the same as in
[`/implement`](implement.md#error-stops); the overall order is on the
[Error stops and RCA](../concepts/error-stops.md) page. `/fast-implement` differs as follows:

- the planned confirmation gates, which are not error stops, are the seam, code review, commit and
  push; a `hitl` ticket or an open blocker is a stop without an error;
- an error with an `FMEA:` line gets the catalog recovery and at most three repeats of the failed
  step; without it the remedy is applied once, without working around a hook;
- on an error stop, the skill leaves the stopped ticket's checkout untouched: its `status::*`
  label, branch and uncommitted changes stay, and nothing is committed, stashed, reset or discarded;
- after the RCA phase, the skill takes the epic's next free ticket by the same selection as
  "Resolve the ticket" step 2 and starts it from the pre-flight in a clean checkout; when the
  current checkout has uncommitted changes, the next ticket gets a new worktree;
- the skill stops and reports the draft path and the reason when the ticket has no epic, no ticket
  qualifies, or a new worktree cannot be created.

An error stop relaxes no other rule: commit and push still need your permission, a PR still needs
your confirmation, auto-merge stays forbidden, and the tracker is written only after your explicit
"yes".

[Source SKILL.md](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/fast-implement/SKILL.md)
