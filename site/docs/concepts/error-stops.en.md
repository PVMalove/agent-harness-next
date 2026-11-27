# Error stops and RCA

When the agent hits an error and cannot get back to work by itself, it does not wait for a human.
The agent writes the root cause to an RCA draft and takes the epic's next free ticket, so an
automated run does not turn into a manual one. The decision is recorded in ADR 0042.

## What an error stop is

An **error stop** is any call to a human caused by an error: a hook block, an unexpected failure,
or a dead end with no analysed way forward. Ordinary agent questions are not error stops: an unclear
requirement, a choice of solution, and planned confirmation gates such as the seam, opening a PR,
creating a ticket or a merge. Neither is a stop without an error that a skill prescribes, such as a
`hitl` ticket or an open blocker.

## The order before an error stop

The agent handles the error by its output:

1. **There is a `FMEA: <guid> (<title>)` line.** The error belongs to an analysed failure mode of
   the [FMEA catalog](fmea.md). The agent applies the entry's `recovery` and repeats the failed step
   at most three times, the same attempt budget as in ADR 0012.
2. **There is no `FMEA:` line.** The error's remedy is only a hint. The agent applies it once,
   without working around hooks or hand-editing state.
3. **Neither helped.** This is an error stop.

## What the agent does on an error stop

1. It leaves the stopped work as it is: the ticket's `status::*` label, the branch, uncommitted
   changes and the paused batch. The human decides what to do with them.
2. It runs the [RCA phase](../skills/diagnosing-bugs.md#rca) of the `diagnosing-bugs` skill: up to
   five "why" steps with evidence, the root cause and its class. The result is an RCA draft under
   `docs/tasks/rca-<symptom-slug>/`, which is never committed. It holds a proposed FMEA entry and,
   when the root cause is in the harness, a bug-ticket draft as well.
3. It reports the stopped ticket and the draft path in one line and takes the epic's next free
   ticket by the frontier query. `/implement` takes only `afk` + `pipeline::full` tickets;
   `/fast-implement` takes `afk` + `pipeline::fast` tickets and opens a new worktree for the next
   ticket when the checkout is dirty.
4. It stops and reports the draft path and the reason when the ticket has no epic, no free ticket
   remains, or it cannot continue: for `/implement`, the `concurrency_budget` is exhausted (with the
   default of 1, the paused batch takes it) or the coordinator is unavailable; for
   `/fast-implement`, a worktree cannot be created.

Per-skill details are in the [`/implement`](../skills/implement.md#error-stops) and
[`/fast-implement`](../skills/fast-implement.md) sections.

## What stays with the human

An error stop relaxes no confirmation rule:

- the tracker is written only after the developer's explicit "yes" for a specific draft. The
  developer picks the target tracker and decides whether the bug blocks the stopped ticket
  (`status::blocked` and a `Blocked by` line). The bug ticket gets the labels `type::bug` and
  `rca::done`;
- before the bug-ticket draft, the agent searches open `type::bug` tickets for the same root cause
  and, on a match, proposes a comment instead of a new ticket;
- commit and push in `/fast-implement` still wait for permission, a PR needs a separate
  confirmation, and only a human merges.

## How error stops become rarer

Every RCA ends with a proposed FMEA entry with a "do X and retry" scenario. The entry enters the
catalog together with an automated recovery test, and the error then prints a `FMEA:` line. The
next time, the same failure is handled by step 1 of the order above and no longer stops the agent.

## Next

- [FMEA catalog](fmea.md)
- [diagnosing-bugs: RCA phase](../skills/diagnosing-bugs.md#rca)
- [Labels](../reference/labels.md)
