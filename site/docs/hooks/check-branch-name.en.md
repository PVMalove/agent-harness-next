# check-branch-name

## 1. Name and localization
- **English name:** check-branch-name (PreToolUse Hook)
- **Translation / Essence:**

```text
Validation of the name of a new branch and a check that the linked task exists (the "Issue First" principle) before the branch is created.
```
## 2. Full description
The `check-branch-name` hook runs before the `Bash` tool is called (as a PreToolUse hook). Its main goal is to stop the agent from creating a branch that is not tied to an existing task in the tracker. It analyzes the commands that the agent passes for `git checkout -b` or `git switch -c`. If it finds such a command, the hook performs these steps:
1. Extracts the target branch name from the command.
2. Matches the branch name against the regular expression `branch_pattern`, which is read from the file `.harness/project.json` (default `^feature/issue-[0-9]+-.+`). If the branch name does not match the pattern, the command is blocked.
3. If the name complies with the rules, the first numeric identifier found in it (the task ID) is extracted.
4. In keeping with the "Issue First" principle, the hook passes the ID to `tracker-issue.py`. It determines the tracker and the project with the project tracker resolver (`.harness/health/project_tracker.py`): the `tracker` field from `.harness/project.json`, and without it the `origin` URL with its port and subgroups. The issue is requested with explicit addressing: `gh issue view <ID> -R <host>/<project>` or `glab issue view <ID> -R https://<host>/<project>`. For a local tracker, an unknown project path, without the `.harness/health` package, or without an installed `gh`/`glab`, the check is skipped.
5. On a refusal, the hook aborts the command and names the reason: the issue is not found (create it through `gh issue create`/`glab issue create`, `/to-spec`, or `/to-tickets`), issues are disabled in the project, the CLI is not authorized on the tracker host, or the project is unavailable.
## 3. Contracts
- **Input (Input/Brief):** A string (in JSON format through stdin) that describes the `Bash` tool call (the field `command` is extracted from it with regular expressions).
- **Output (Output/Report):** If the check succeeds, code `0` (permission to run). If the branching convention is violated or the task could not be confirmed (not found, issues disabled, no authorization, project unavailable, the CLI did not answer within 10 s or exited with an unrecognized error), a diagnostic message with the reason in `stderr` and return code `2` (execution is blocked).
## Source

[check-branch-name.sh](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/check-branch-name.sh)
