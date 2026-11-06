# Map of hooks

A catalog of the hook scripts of Harness Next: what each hook intercepts, what the contract of the input and the output is, and where the source lives.
Every managed hook answers with a single JSON verdict ([hook-response](hook-response.md)) and obeys the policy profile
of the project; the profile does not turn critical guards off.

## Git and branches

| Hook | Event | Purpose |
| --- | --- | --- |
| [block-dangerous-git](block-dangerous-git.md) | `PreToolUse(Bash)` | Blocking of destructive Git commands. |
| [block-direct-master](block-direct-master.md) | `PreToolUse(Bash)` | Prohibition of direct commits and pushes to protected branches (`master`, `main`, `base_branch`, `integration/*`). |
| [block-pr-merge](block-pr-merge.md) | `PreToolUse(Bash)` | Prohibition of automatic PR/MR merge: a human performs the merge. |
| [block-public-attribution](block-public-attribution.md) | `PreToolUse(Bash)` | Blocking of AI attribution in public Git metadata. |
| [check-branch-name](check-branch-name.md) | `PreToolUse(Bash)` | Check of the name of a new branch and of the existence of the related issue (Issue First). |
| [check-worktree-branch-name](check-worktree-branch-name.md) | `PreToolUse(EnterWorktree)` | The same for a branch created together with a worktree. |

## QA and checks

| Hook | Event | Purpose |
| --- | --- | --- |
| [require-qa-gate](require-qa-gate.md) | `PreToolUse(Bash)` | Blocking of creating a PR/MR without a successful QA. |
| [record-qa-gate-pass](record-qa-gate-pass.md) | called by a skill | Recording of a successful QA gate pass for the current state. |
| [mark-qa-gate-passed](mark-qa-gate-passed.md) | `PostToolUse(Bash)` | Marking of the QA gate pass after the last `qa_gate_commands` command. |
| [require-bounded-check](require-bounded-check.md) | `PreToolUse(Bash)` | Bounded output of a full test run through the `test_summary.py` wrapper. |
| [targeted-check-reminder](targeted-check-reminder.md) | `PreToolUse(Write/Edit)`, `Stop`, `SubagentStop` | A reminder at the end of a role turn to read back the targeted checks of the brief. |
| [run-test](run-test.md) | a script, not a hook | An isolated run of one selected test in bubblewrap. |

## Policy and risky paths

| Hook | Event | Purpose |
| --- | --- | --- |
| [protect-hook-policy](protect-hook-policy.md) | `PreToolUse` (Bash and the file tools) | Protection of the hooks policy: the `hook_policy` key, the hooks settings, and directories. |
| [block-scratch-outside-docs-tasks](block-scratch-outside-docs-tasks.md) | `PreToolUse(Write/Edit)` | Task drafts are written only to `docs/tasks/` inside the project. |
| [impact-first-touch](impact-first-touch.md) | `PreToolUse(Write/Edit)` | A warning about the first touch of a risky path in an operation. |
| [sensitive-path-recheck](sensitive-path-recheck.md) | `PreToolUse(Write/Edit)`, `strict` profile | A warning about every new edit of a sensitive path. |

## Test-author

| Hook | Event | Purpose |
| --- | --- | --- |
| [test-author-guard](test-author-guard.md) | `PreToolUse` (wired by the agent frontmatter) | The guard hook of the test-author subagent: exactly three kinds of allowed calls. |
| [test-author-preflight](test-author-preflight.md) | a script, not a hook | A check that test-author can be enabled without losing protection. |

## Auxiliary

| Document | Type | Purpose |
| --- | --- | --- |
| [hook-response](hook-response.md) | shared module | The response envelope of managed hooks: a JSON verdict, a return code, and the policy profile. |
| [install-and-update](install-and-update.md) | installation | The merge of the managed entries of the settings file and the second-runtime adapter. |
| [count-skill-usage](count-skill-usage.md) | `PreToolUse(Skill)` | Accounting of skill calls, best-effort, never blocks. |

## Related documents

- Skills and pipeline roles: [skills map](../skills/index.md)
- Agents and guides: [agents map](../agents/index.md)
- Hook reference: [reference/hooks](../reference/hooks.md)
