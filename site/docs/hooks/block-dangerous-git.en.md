# block-dangerous-git

## 1. Name and localization
- **English name:** block-dangerous-git.sh
- **Translation / Essence:**

```text
Blocking of dangerous Git commands
```
## 2. Full description
This hook script (type `PreToolUse(Bash)`) blocks destructive Git commands. It intercepts commands such as `git reset --hard`, `git clean -f`, `git branch -D`, `git checkout .`, and `git restore .`. The script is adapted from "git-guardrails-claude-code", but it intentionally does not block `git push` directly (protection of pushes to main branches is handled separately in `block-direct-master.sh`). The logic protects the local repository from accidental loss of uncommitted changes by the agent and requires explicit confirmation from the user.

The command is parsed as shell, not searched as raw text. Only a run of `git` is blocked: the command word, including inside `$(...)`, backticks, `sh -c`/`bash -c`, `eval`, and a heredoc body that is fed to a shell (`bash <<'EOF'`). Words that are passed to a shell on the same line through `|`, `<<<`, or `<(...)` (`echo "..." | sh`) are also parsed as a script. A mention of the same string in quotes, in an argument of another interpreter (`python -c "..."`), or in the body of a heredoc for a non-shell (`python - <<'EOF'`) is data, and the command passes. If the command cannot be parsed (for example, an unclosed quote), the hook falls back to a search in the raw text and blocks on a match.

Known limitations: the hook does not see a command that another interpreter or a remote shell runs (`python -c "os.system(...)"`, `ssh host '...'`), nor the content of a file passed to a shell (`cat x | sh`, `bash script.sh`). Global `git` options (`git -C dir reset --hard`) are not parsed, as before. Any word `sh`/`bash`/`zsh`/`dash`/`ksh`/`eval` on a line counts as a shell, so a rare example such as `grep bash <<EOF` with a dangerous string in the body is blocked (a false positive on the safe side).
## 3. Contracts
- **Input (Input/Brief):** A string (through stdin) that contains the command in the format `"command": "..."` (usually passed by the agent infrastructure before Bash runs).
- **Output (Output/Report):** Returns code `0` if no dangerous patterns are found. Returns code `2` and a message in `stderr` if the command is blocked.
## Source

[block-dangerous-git.sh](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/block-dangerous-git.sh)
