# require-bounded-check.sh — bounded check output

## 1. Name and localization

- **Source hook:** [`harness/project/hooks/require-bounded-check.sh`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/require-bounded-check.sh)
- **Translation:** a requirement for bounded output of a full test run.

## 2. Full description

The `PreToolUse(Bash)` hook reads the command from the input JSON. If the project has no
`.harness/project.json`, the hook blocks nothing. If the config exists, the hook checks the commands from
`qa_gate_commands`, a full `pytest`, and a full `python -m unittest`. Such a run requires the
`qa-gate/scripts/test_summary.py` wrapper, which shortens and cleans the output before it enters the
session history. A targeted `pytest` with a `::` node ID and `unittest` with the full dotted path of the test
pass without the wrapper.

Mentioning the name does not count as a run. The shared shell parser `pr_commands.py` keeps argument
boundaries and parses simple commands, nested shells, and executable substitutions. The DoD text in
`gh issue create --body`, the `glab issue create` description, the `git commit` message, the arguments of
`echo`/`printf`, and the arguments of read commands do not count as a check run. Comments and the literal text of a
heredoc are also skipped. A real run through `bash -c`, `eval`, `timeout`, `find -exec`,
`$(...)`, backticks, process substitution, or a shell heredoc is blocked. Unparseable
executable text and interpreter code are checked conservatively by substring.

## 3. Contract

- **Input:** A Bash command on stdin and the target project's `.harness/project.json`. Parsing needs
  Python 3.10+ and the neighboring `pr_commands.py`. If the config exists, a Python or module error gives exit code `2`.
- **Output:** Exit code `0` for an allowed call. For a full run without the wrapper: exit code `2` and a fix
  command in stderr.
