# test-author-guard.py — scoped guard of the test-author subagent

## 1. Name and localization

- **Source script:** [`harness/project/hooks/test-author-guard.py`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/test-author-guard.py)
- **Translation:** the guard hook of the test-author subagent.

## 2. Full description

`test-author-guard.py` is a `PreToolUse` event hook for `Write`, `Edit`, and `Bash`, but it is not in
`settings.local.json`: the installation copies it to `.claude/hooks/`, and only the
frontmatter of the agent `.claude/agents/test-author.md` connects it. Therefore the guard acts on the calls of the
test-author subagent, while the project-wide hooks (`block-scratch-outside-docs-tasks.sh`, `require-bounded-check.sh`,
and the others) remain in force and fire in the same way as for any agent.

The guard allows exactly three kinds of calls:

- `Write` and `Edit` — the path after normalization lies inside `test_paths`; a symlink that leads outside
  the zone, and paths under `.git`, `.harness`, `.claude`, `.agents`, `.codex` are rejected;
- `apply_patch` of the second runtime — each path of the patch from the headers `*** Add File:`,
  `*** Update File:`, `*** Delete File:`, and `*** Move to:` (absolute from the payload `cwd`, parsed by the
  `apply_patch_payload.py` adapter) passes the same check as a `Write`/`Edit` path; a patch with at least
  one path outside `test_paths` gets `write_outside_test_paths`, and an unparseable patch gets
  `patch_unparseable` with a hint about which patch format to send;
- `Bash` — one call of `.claude/hooks/run-test.sh <test-id>` (an equivalent call through the
  trusted system `bash` is allowed); shell metacharacters, `--probe`, extra arguments, and other
  commands are rejected.

Other tools get the refusal `tool_not_allowed`. If the payload comes from another agent
(`agent_type` differs from `test-author`), the guard passes the call silently: the route of the developer and
of other agents does not change.

**Soft refusal.** The hook prints one `PreToolUse` JSON with `permissionDecision: deny` and the reason
`test-author: <reason>` and exits with code 0. It writes no files, changes neither the dispatch nor the ledger,
and returns no user input. Before the check of the call, the guard checks the activation again:
whether the agent is installed with the hook enabled, whether `test_paths`, `test_runner`, and the write zones are valid; on
a failure, the refusal gets the reason of this check or `guard_unavailable`.

**Internal mode.** `test-author-guard.py --validate-config` prints `{"status":"ok"}` or
`{"status":"disabled","reason":"<reason>"}`. Only
[`test-author-preflight.sh`](test-author-preflight.md) calls it.

## 3. Contracts

- **Input:** The `PreToolUse` JSON in stdin with `agent_type`, `tool_name`, `tool_input`; the project root
  is taken from `CLAUDE_PROJECT_DIR`, not from the path in the call.
- **Refusal reasons (closed set):** `malformed_payload`, `write_outside_test_paths`,
  `write_path_invalid`, `patch_unparseable`, `runner_only`, `test_id_invalid`, `tool_not_allowed`, `guard_unavailable`
  and the reasons of the activation check: `agent_missing`, `scoped_hook_unsupported`, `config_invalid`,
  `test_paths_missing`, `test_runner_missing`, `write_zone_rejected`.
- **Exit code:** always `0`.

## Source

[test-author-guard.py](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/test-author-guard.py),
[test_guard.py](https://github.com/PVMalove/agent-harness-next/blob/master/tests/test_author/test_guard.py),
[test_compatibility.py](https://github.com/PVMalove/agent-harness-next/blob/master/tests/test_author/test_compatibility.py),
[docs/agents/test-author.md](../agents/test-author.md),
ADR 0014
