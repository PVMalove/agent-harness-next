# targeted-check-reminder.sh — reminder about targeted checks

## 1. Name and localization

- **Source hook:** [`harness/project/hooks/targeted-check-reminder.sh`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/targeted-check-reminder.sh)
  and the shared body [`change_impact_hooks.py`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/change_impact_hooks.py)
- **Translation:** a reminder at the end of a role turn to read back the targeted checks of the brief.

## 2. Full description

An advisory hook from the matrix of ADR 0024, section 2a, on two events:

- **`PreToolUse(Write|Edit)`** — keeps a touch log of the operation and answers `allow` without output. The record
  `t-<sha256(realpath)[:32]>.json` contains the path, the checkout root, and the kind: `report` for a write to
  `.harness/.sandboxes/scratch/inbox/*.json` (`report_staging_path`), `touch` for everything else. The record
  is created through `O_EXCL` once and does not change.
- **`Stop` and `SubagentStop`** — the end of the role turn. The main agent (coordinator, external worker)
  ends the turn with the `Stop` event, an in-process role subagent with the `SubagentStop` event. The changes are
  the existing log files, except the paths under `.harness/` and `docs/tasks/` and the reports themselves. If
  there are no changes, or the last report of the operation is newer than all changes by `mtime`, the hook stays silent. Otherwise it
  gives `warn` with the code `targeted-checks-unreported` and stdout `{"systemMessage": "<text>"}`: the number of
  files, the worktree, and the requirement to read back the targeted checks of the brief in `checks_run`.

The hook never continues the turn: `Stop` and `SubagentStop` have no `decision: block`, no code `2`, and no
`additionalContext`, and with `stop_hook_active: true` it answers `allow` without output. So there is no cycle.
The hook does not run tests, `make`, or `git`: it only makes a `stat` of the log files.

- **Profiles.** `minimal` — the hook does not work: the body does not run, and the log is not written. `standard` and
  `strict` — the log and the reminder.
- **Deduplication.** The subject of the notification is the sorted state `(path, mtime_ns, size)`
  of the changed files and `mtime_ns` of the last report. A repeated `Stop` without new changes stays silent;
  a new edit or a new report changes the digest and gives a new reminder.

### Operation storage

The state of the three ChangeImpact hooks lives in `<project>/.harness/.sandboxes/hook-events/<operation_id>/`.
The hook takes the project root by the location of the module (`.claude/hooks/` of the project); the directory is
gitignored and one-shot. The operation directory contains the notification markers `n-<key>.json` and the touch log
`t-<key>.json`. There are no locks and no read-modify-write: each file is created through `O_EXCL`, so the
behavior is the same on Linux and Windows. The storage is bounded: no more than 64 operation directories (when
a new one is created, the oldest by `mtime` are deleted) and no more than 2048 files in an operation (beyond that, records are not
created, and the hook answers `allow` with a diagnostic in stderr). File names consist only of hex, and the
hook uses no temporary `/tmp` directories and no `fcntl`.

### Second runtime

The template `.codex/hooks.json` connects this hook only on `Stop` and `SubagentStop`: the second runtime
delivers both events with `session_id`, `stop_hook_active`, and, for `SubagentStop`, `agent_id`. File edits
arrive there as `apply_patch` without `file_path`, so the touch log on `Write` and `Edit` waits for the
payload adapter. Until then the log of the second runtime is empty, and the reminder stays silent; `harness health`
lists the line `PreToolUse` in `no event or payload` with a check outside the hook — the reconciliation of
`checks_run` by the coordinator.

## 3. Contract

- **Input:** The JSON of the event in stdin: `session_id`, `agent_id` (for a subagent), `hook_event_name`;
  for `PreToolUse` — `tool_input.file_path` and `cwd`, for `Stop` and `SubagentStop` — `stop_hook_active`.
- **Output:** Code `0` always. The reminder — `systemMessage` in stdout, the first stderr line
  `[targeted-checks-unreported] <text>`, the line `evidence_ref=<path>`, and the verdict `warn`; all other
  calls — `allow` without stdout. An internal error — `warn` `internal-error` with empty stdout, so that
  a partial output does not break the `Stop` protocol of the second runtime.

## Source

[targeted-check-reminder.sh](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/targeted-check-reminder.sh),
[change_impact_hooks.py](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/change_impact_hooks.py)
