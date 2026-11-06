# block-public-attribution

## 1. Name and localization

- **English name:** block-public-attribution
- **Translation / Essence:**

```text
Blocking of AI attribution in public Git metadata
```

## 2. Full description

The script fires at the `PreToolUse` stage for the `Bash` tool. Its goal is to guarantee that all Git commits, Pull Requests, Merge Requests, pushes, and tracker texts (issues, comments, notes) on GitHub and GitLab contain no automatic attribution: mentions of the use of AI assistants (such as Claude, ChatGPT, Copilot, Gemini, and others), the trailer "Co-authored-by: AI", and session URLs.

The check works on two levels:
- **Git metadata** — commit messages, and the title and body of a PR/MR. The full list of prohibited terms `FORBIDDEN` applies here: names of models and runtimes, attribution, session URLs.
- **Tracker text** — the title and body of an issue, comments on issues and PRs, notes on issues and MRs, including through `glab api`. Only the attribution pattern `TRACKER_ATTRIBUTION` applies here: the trailer `Co-Authored-By`, the claim "generated/written by <assistant>", an AI-generated mark, and links to assistant sessions. Runtime names and paths such as `.claude/` or `CLAUDE.md` are project vocabulary in tickets, so they are not blocked by themselves.

The execution logic includes:
1. Safe JSON parsing (through Python) to extract the command being run from `tool_input.command`.
2. Cutting out heredoc bodies: this is stdin, not command words. A marker stays in place of the operator, and the body is checked only if the operator stands inside a checked argument, for example `-m "$(cat <<'EOF' ... EOF)"` or `--body "$(cat <<'EOF' ... EOF)"`.
3. Detection of the operation type from the command text without heredoc bodies: `git commit`, `git push`, `gh pr` and `glab mr` `create`/`new`/`edit`/`update`, `gh`/`glab issue` `create`/`new`/`edit`/`update`, comments `gh issue|pr comment`, notes `glab issue|mr note`, `glab api`.
4. When it detects these operations, the script uses the `shlex` module (Python) to parse the command arguments. For each publishing command, a flag table defines which short and long flags carry text in exactly this CLI:
   - `gh pr create|new|edit`, `gh issue create|new|edit|comment`, `gh pr comment` — `-t`/`--title`, `-b`/`--body`, and the file `-F`/`--body-file`;
   - `glab mr create|new|edit|update`, `glab issue create|new|update` — `-t`/`--title`, `-d`/`--description`, and the file `--description-file`;
   - `glab issue note`, `glab mr note` — `-m`/`--message`;
   - `glab api` — the fields `-F`/`--field` and `-f`/`--raw-field` with the key `body`, `description`, or `title`; the value `-F key=@<path>` is read from a file.

   In gh, `-d` is `--draft`, in glab `-b` is `--target-branch`, and `-m` outside notes is a milestone: such flags do not count as text. All forms are read: `-t X`, `-tX`, `-t=X`, the cluster `-dt X`, `--title=X`, and repeated flags.
5. Check of the string values and of the content of the specified files against the pattern of their own level. The file must be reachable by a literal path: a shell variable, `-` or `@-` (stdin), and a nonexistent path block the command.
6. For push commands and for PR/MR create/edit commands, the messages of local (unpushed) commits reachable from `HEAD` (`git log HEAD --not --remotes`) are also checked.
7. If the script finds prohibited substrings or hits an error while reading files or strings, it aborts the command, returns error code `2`, and prints a warning to stderr.

## 3. Contracts

- **Input (Input/Brief):** A JSON object passed on `stdin` that contains the parameters of the tool call (in particular, `tool_input.command`). When needed, it reads message files (by the paths from the command arguments) and the history of local commits.
- **Output (Output/Report):** If the check succeeds, it returns code `0` (the command is allowed). If it finds AI attribution, it prints an error message to `stderr` and exits with code `2` (execution is prohibited). The message names the level: Git metadata or tracker text.

## Source

[block-public-attribution.sh](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/block-public-attribution.sh)
