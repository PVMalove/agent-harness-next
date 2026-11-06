# impact-first-touch.sh — first touch of a risky path

## 1. Name and localization

- **Source hook:** [`harness/project/hooks/impact-first-touch.sh`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/impact-first-touch.sh)
  and the shared body [`change_impact_hooks.py`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/change_impact_hooks.py)
- **Translation:** a warning about the first touch of a risky path in an operation.

## 2. Full description

An advisory hook `PreToolUse(Write|Edit)` from the matrix of ADR 0024, section 2a. It reads
`tool_input.file_path` and warns when the agent edits, for the first time in an operation, a path whose impact
ChangeImpact does not compute from the import graph: the build and check configuration (`pyproject.toml`, `uv.lock`,
`Makefile`, `conftest.py`, `.github/*`, `scripts/verify.py`, `scripts/verification/*`) or the catalog of
capabilities and skills (`harness/CAPABILITIES.json`, `skills/*`). The set matches the rules
`build-config-changed` and `capabilities-or-skills-changed` of the function `path_unknown_code` in
`harness/repo_map/change_impact.py`. The rule `non-python-file` is not in the set; otherwise every edit of a document
would be risky. The hook does not see the harness package and keeps a copy of the rules;
`tests/core/test_change_impact_hooks.py` compares the copy with the source.

The path is compared after `realpath`, relative to the nearest ancestor directory with `.git` (a directory or a
worktree file), in posix form; on Windows the comparison ignores case. The hook
passes a path outside a git checkout without a warning.

The model receives the warning: stdout contains
`{"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "<text>"}}` without
`permissionDecision`, so the permission flow does not change. The hook never blocks.

- **Profiles.** `minimal` — the hook does not work: the envelope answers `allow`, the body does not run, and no state
  is written. `standard` and `strict` — `warn` with the code `risky-path-first-touch`.
- **Deduplication.** One notification per path in an operation: this is the first touch, and a repeated edit
  of the same path creates no warning loop. An operation is an agent run: `operation_id` equals the first 32
  hex characters of the sha256 of the array `["hook-operation", session_id, agent_id or ""]`. A role subagent, an external worker,
  and the coordinator get different operations, while a new dispatch, a developer retry, and a repeated role get a new
  operation and a new notification. The marker `n-<key>.json` is created through `O_EXCL`, so exactly one of
  parallel calls warns. The marker also serves as an evidence record: its path is in
  `evidence_ref` of the verdict. The storage and its limits are described in
  [targeted-check-reminder.md](targeted-check-reminder.md).
- **Internal error.** Unreadable JSON, no `session_id` or `tool_input.file_path`, a storage failure,
  any exception, a non-zero code, and the 10 s timeout (`ADVISORY_TIMEOUT_SECONDS`) give `warn`
  `internal-error` with code `0` and empty stdout ([hook-response.md](hook-response.md)).
- **Second runtime.** A file edit arrives there as `apply_patch` without `file_path`, so the hook is not
  connected until the payload adapter exists. `harness health` lists it in the line `no event or
  payload` with a check outside the hook — the ChangeImpact gate under ADR 0023.

## 3. Contract

- **Input:** The JSON of the `PreToolUse` event in stdin: `session_id`, `agent_id` (for a subagent),
  `hook_event_name`, `tool_name`, `tool_input.file_path`, `cwd`; the profile comes only from `hook_policy` in
  `.harness/project.json`.
- **Output:** Code `0` always. A first touch of a risky path gives `additionalContext` in stdout, the first
  stderr line `[risky-path-first-touch] <text>`, and the line `evidence_ref=<path>`; the last
  stderr line is the verdict of the envelope. All other calls give `allow` without stdout.
- **State:** `.harness/.sandboxes/hook-events/<operation_id>/n-<key>.json`; the hook does not run
  tests, `make`, or `git`.

## Source

[impact-first-touch.sh](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/impact-first-touch.sh),
[change_impact_hooks.py](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/change_impact_hooks.py),
[change_impact.py](https://github.com/PVMalove/agent-harness-next/blob/master/harness/repo_map/change_impact.py)
