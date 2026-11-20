# check-worktree-branch-name

## 1. Name and localization
- **English name:** PreToolUse: Check Worktree Branch Name
- **Translation / Essence:**

```text
Validation of the branch (worktree) name before it is created, against the project conventions, and a check that the task exists in the tracker.
```
## 2. Full description
The hook `check-worktree-branch-name.sh` fires before the `EnterWorktree` tool runs (the PreToolUse event). It is meant to enforce the "Issue First" approach and one branch naming style in the project.

How it works:
1. The JSON argument of the tool call is read from standard input (stdin), and the field `"name"` is extracted.
2. If the name is not set explicitly (for example, the call enters an existing worktree by path), the checks are skipped.
3. If the name is set, it is checked against the regular expression `branch_pattern` from `.harness/project.json` (default `^feature/issue-[0-9]+-.+`). If the name does not match the pattern, execution is blocked.
4. If the pattern check succeeds, the issue number (the first sequence of digits) is extracted from the branch name.
5. The number is passed to `tracker-issue.py`, the same check as in `check-branch-name.sh`: the project tracker resolver determines the tracker and the project (the `tracker` field or `origin`), and `gh`/`glab` get an explicit `-R`. For a local tracker, an unknown project path, without the `.harness/health` package, or without an installed CLI, the check is skipped; without Python the hook blocks creation, like `check-branch-name.sh`.
6. If the issue is not found, issues are disabled in the project, the CLI is not authorized, or the project is unavailable, the hook aborts the tool and names that reason.
## 3. Contracts
- **Input (Input/Brief):** JSON with the arguments of the `EnterWorktree` tool call, delivered to `stdin`. The optional field `"name"` is expected.
- **Output (Output/Report):** On success, or when there is no name, return code `0` is returned. If the naming convention is violated or the issue could not be confirmed (not found, issues disabled, no authorization, project unavailable, the CLI did not answer within 10 s or exited with an unrecognized error), code `2` is returned and a message with the reason is printed to `stderr`.
## Source

[check-worktree-branch-name.sh](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/check-worktree-branch-name.sh)
