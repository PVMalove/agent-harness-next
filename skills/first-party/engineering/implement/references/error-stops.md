# Error stops

Read this when an error interrupts the coordinator, before calling a human about it.

An **error stop** is any call to a human caused by an error: a hook block, an unexpected failure, or
a dead end with no analysed way forward. Ordinary questions are not error stops: an unclear
requirement, a choice of solution, or a planned confirmation gate (an approval the
`approval_policy` requires, opening a PR). A stop that `SKILL.md` prescribes without an error, such
as an open blocker, is not one either, and neither is a recovery route of `recovery.md` or the
playbook that continues without a human. This is the definition of the `diagnosing-bugs` skill's
"RCA phase — on an error stop"; if the two ever differ, that phase's definition applies.

## Before an error stop

Handle the error by its output:

1. **An `FMEA: <guid> (<title>)` line** (or a `fmea` field beside `reason_code` in a hook's JSON
   answer): apply the `recovery` of that catalog entry, which is the printed remedy
   (`harness fmea show <title|id>` prints the entry), and repeat the failed step at most three
   times: the same limit of three as the test author's failed calls (ADR 0012). A worker dispatch
   is still retried only through the routes and budgets that `batch decision-packet` shows.
2. **No `FMEA:` line:** the remedy is only a hint. Apply it once, within this skill's limits (no
   hand-edited state, no worked-around hook).
3. **Neither restored the work:** it is an error stop.

## On an error stop

Keep the stopped work for the human's decision and continue without waiting for an answer:

1. Under `approval_policy: auto`, record the pause first (`auto-path.md`). Leave the paused batch
   and the stopped ticket's `status::*` label as they are: the human chooses the batch's route.
2. Run the RCA phase of the `diagnosing-bugs` skill ("RCA phase — on an error stop"). It ends with
   `RCA draft: <path>. Continue with the next free ticket.`
3. Report the stopped ticket, its batch and the draft path in one line. Then take the next free
   ticket: run the frontier query of `.harness/instructions/issue-tracker.md` → Wayfinding
   operations on the stopped ticket's parent epic and keep only `afk` + `pipeline::full` tickets: a
   `pipeline::fast` ticket goes through `/fast-implement`. The query's own order picks the first
   one. On GitHub or GitLab, claim it by that section's Claim operation. Start it from `SKILL.md` →
   "Route" with its own batch and issue worktree. The paused batch still counts toward
   `concurrency_budget`.
4. Stop and report the draft path and the reason when the stopped ticket has no parent epic, no
   ticket qualifies, the `concurrency_budget` is exhausted, or the coordinator itself is
   unavailable. With a `concurrency_budget` of 1 (the default), the paused batch exhausts it.

An error stop relaxes no other rule: a PR still needs the developer's explicit confirmation,
auto-merge stays forbidden, and the tracker is written (the RCA draft's bug ticket or comment
included) only after the developer's explicit "yes".
