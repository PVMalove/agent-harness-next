# mark-qa-gate-passed

## 1. Name and localization
- **English name:** mark-qa-gate-passed
- **Translation / Gist:**

```text
Marking a successful QA gate pass
```
## 2. Full description
The `mark-qa-gate-passed.sh` script is a hook that runs after a Bash tool command succeeds (`PostToolUse(Bash)`). Its main task is to record that the current state of the worktree has passed all quality checks (the QA gate).

The hook analyzes its input and checks whether the command that just ran is the last command in the `qa_gate_commands` list (defined in the `.harness/project.json` configuration file). In a linked worktree, where the gitignored `.harness/` directory is absent, the configuration comes from the project root (`CLAUDE_PROJECT_DIR`). If the session itself runs in a linked worktree, the configuration comes from the repository's main worktree. If it exists nowhere, the hook does nothing. The QA gate stops at the first failure, so a successful finish of the last command guarantees that all previous checks also passed.

Only a run of the whole last command counts as a match. Its simple commands must follow each other with the same separators, or a shell (`bash`, `sh`, `zsh`, `dash`, `ksh`, `powershell`, `pwsh`) must receive the whole command as a command string: `bash -lc '<command>'` or `-Command '<command>'`, as the `qa-gate` skill runs it. The command must not be preceded by `||`. Only `&&` may follow it. It must not run in the background. Otherwise a successful Bash call does not mean the command succeeded (`<command> || true`, `<command>; true`, `<command> | tail`). The marker is also not set in two other cases. In the first, the command only contains the text of the QA command, for example a narrower test selection `<command> test_one`. In the second, the command goes beyond the bash subset that the strict hooks lexer parses: a `$(...)` substitution, or an assignment before the program such as `FOO=1 <command>`.

On a match, the script builds a unique repository state identifier from the hash of the current commit (`HEAD`) and the hash of the uncommitted changes (`git diff`). It saves this string to the marker file `.claude/.qa-gate/passed`. Later, the `require-qa-gate.sh` hook checks that this marker is current before a pull request is created.

This hook works as a fallback: normally the `qa-gate` skill writes this marker itself through the `record-qa-gate-pass.sh` script, because the skill runs in an isolated context. This hook covers the cases where the agent runs the QA gate commands directly through Bash calls in the main session.

The hook is wired only in `.claude/settings.local.json`, where `PostToolUse` fires only after a successful command. It is not wired in the second coding runtime: that runtime also calls `PostToolUse` after a command with a non-zero exit code, and its payload has no exit code (see [install-and-update.md](install-and-update.md)).
## 3. Contracts
- **Input (Input/Brief):** JSON with the parameters of the executed action (passed through `stdin`), containing information about the Bash command that ran.
- **Output (Output/Report):** On a successful check, the script creates or updates the marker file `.claude/.qa-gate/passed`. It contains a string with the current repository state in the format `<HEAD_hash>:<diff_hash>`. Exit code 0.
## Source

[mark-qa-gate-passed.sh](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/mark-qa-gate-passed.sh)
