# Automatic path

Read this when `approval_policy` is `auto`.

Under `approval_policy: auto`, the coordinator takes every path decision by policy and records it
as `policy:auto`; follow "Automatic path" in `.harness/orchestration/playbook.md`. Do not write
`--approved-by` or `--approved-at`: run `batch approve`, `dispatch create` and a planned
`dispatch resume --trigger` without them. For every pending report that the `report submit` or
`qa run` chain did not accept, including the publish report, run
`batch auto-decide --batch <id>`. Before `batch auto-decide` on a developer report with a failed
check, follow `references/recovery.md` → "A failed check the diff may not cause". Pass `--commit-plan-file` with the architect's plan copied
exactly only when the report carries no `commit_plan`, `--findings-file` for coordinator findings on a developer report, `--bug-ticket` after
you file or reuse the tool's bug ticket through the tracker CLI, and `--block-bypass --note` when a
role worked around a block. Pass nothing else, and never choose the decision yourself. After a refused command, run `batch auto-report --batch <id>` to observe evidence. This read-only
command does not record a stop. If it shows `observed_stop`, run `batch auto-decide --batch <id>`
to record the pause, even without a pending report, then show `batch auto-report` again.
The automatic path ends permanently at that pause. Inspect `batch decision-packet`, `dispatch status`
and `ledger validate` before you propose waiting, launch repair, human-approved `batch resume-stop`,
or `batch rewind --to <gate>` to repeat an earlier gate. An exhausted infrastructure budget keeps
the batch paused for that human choice.
Use the playbook's "Operator recovery" procedure. The original stop stays historical; all later
approvals, including recognized 429 continuations, follow `manual_all`. Honor an approval already
explicitly given in this session for the concrete operation; never invent one.
