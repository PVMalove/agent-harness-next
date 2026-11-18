# Commit plan

Read this before the architect accept and before every write-role dispatch.

Before every write-role dispatch, the immutable brief carries an ordered commit plan. Each entry
names one independently reviewable logical change, its expected files and the DoD items it covers;
use one entry only when the entire approved change is inseparable. The coordinator derives one entry
per DoD item; to use the architect's plan instead, pin it on the architect accept with
`batch decide --decision accept --commit-plan-file <path>`. A recovery preserves the accepted plan,
or replaces it with a newly approved plan that explains the changed boundary. The developer's
completion report maps every created commit to the entries it closes; a mapping that is not
one-to-one needs `dod_coverage` and `divergence_justification`, and a report with a `not_covered`
item can be accepted only by `override-warning` with a note other than `none`, or returned with
`retry`. A report whose `changed_files` lie outside the brief's `write_paths` is recorded with a
`scope_warnings` entry and is accepted only the same way. Do not collapse unrelated implementation, tests, documentation, or type-only repairs into a
recovery commit merely because they are staged together.

**Commit plan.** The architect puts its plan in the report field `commit_plan`; `report submit`
refuses a plan that breaks the rules below or names a path outside the batch `allowed_paths`, and an
accept pins the reported plan. Pass a plan file only when the report carries none: pin it with
`batch decide --batch <id> --decision accept --approved-by <operator> --approved-at <UTC time> --commit-plan-file <path>`. The operator approves this decision; never supply `--approved-by` for them.
A plan file passed beside a reported plan must hold the same plan. Write the file under
`.harness/.sandboxes/scratch/inbox/` or the project session scratchpad
`.harness/.sandboxes/scratch/sessions/<session_id>/scratchpad/`; a path outside the repository and
its worktrees, such as an external `/tmp` scratchpad, is refused.
The file is a JSON object with the single key `commit_plan`, a non-empty list in commit order:

```json
{"commit_plan": [{"id": "tests", "summary": "Add failing tests", "expected_paths": ["tests/**"], "covers": [1]}]}
```

Each entry has exactly these fields: `id` (unique; up to 64 characters of letters, digits, `.`, `_`, `-`; the first character is a letter or digit),
`summary` (non-empty), `expected_paths` (non-empty list of relative paths or globs, with no leading `/`
and no `..`), and `covers` (non-empty list of 1-based `--definition-of-done` item numbers, without
repeats). Every definition-of-done item must appear in at least one entry. The CLI rejects a
broken file and prints the expected format.
