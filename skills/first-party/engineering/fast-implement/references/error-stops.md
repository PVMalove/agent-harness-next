# Error stops

Read this when an error interrupts `/fast-implement`, before calling a human about it.

An **error stop** is any call to a human caused by an error: a hook block, an unexpected failure, or
a dead end with no analysed way forward. Ordinary questions are not error stops: an unclear
requirement, a choice of solution, or a planned confirmation gate (the seam, code review, commit and
push). A stop that `SKILL.md` prescribes without an error, such as a `hitl` ticket or an open
blocker, is not one either. This is the definition of the `diagnosing-bugs` skill's "RCA phase — on
an error stop"; if the two ever differ, that phase's definition applies.

## Before an error stop

Handle the error by its output:

1. **An `FMEA: <guid> (<title>)` line** (or a `fmea` field beside `reason_code` in a hook's JSON
   answer): apply the `recovery` of that catalog entry, which is the printed remedy
   (`harness fmea show <title|id>` prints the entry), and repeat the failed step at most three
   times: the same limit of three as the test author's failed calls (ADR 0012).
2. **No `FMEA:` line:** the remedy is only a hint. Apply it once, without working around a hook.
3. **Neither restored the work:** it is an error stop.

## On an error stop

Keep the stopped work for the human's decision and continue without waiting for an answer:

1. Leave the stopped ticket's checkout untouched: its `status::*` label, its branch and its
   uncommitted changes stay as they are. Never commit, stash, reset or discard them.
2. Run the RCA phase of the `diagnosing-bugs` skill ("RCA phase — on an error stop"). It ends with
   `RCA draft: <path>. Continue with the next free ticket.`
3. Report the stopped ticket and the draft path in one line. Then take the next free ticket as
   `SKILL.md` → "Resolve the ticket" step 2 picks it from the stopped ticket's parent epic, and run
   it from `SKILL.md` → "Pre-flight" in a clean checkout. When the current checkout has
   uncommitted changes, open a new worktree for the next ticket by
   `.harness/instructions/worktrees.md`.
4. Stop and report the draft path and the reason when the stopped ticket has no parent epic, no
   ticket qualifies, or a new worktree cannot be created.

An error stop relaxes no other rule: commit and push still need the developer's explicit
permission, a PR still needs the developer's explicit confirmation, auto-merge stays forbidden, and
the tracker is written (the RCA draft's bug ticket or comment included) only after the developer's
explicit "yes".
