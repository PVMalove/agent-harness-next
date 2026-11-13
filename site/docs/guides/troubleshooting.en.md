# Troubleshooting

This page lists the messages that the installer, the CLI, and the hooks print, with their cause and
the action to take. If a message is not in the table, the next step is `harness health <repo>`: it
shows what exactly is not configured and often prints the fix command itself.

## Installation and update

| Message (fragment) | Cause | What to do |
| --- | --- | --- |
| `harness requires Python 3.12+` | The Python version is below the supported one | Update Python: the CLI and the installer do not run on older versions |
| `python: The term 'python' is not recognized` in PowerShell | `python` or `py` is not in `PATH` | Check the `Path` variable, open a new terminal window, or call the interpreter by its full path |
| `not a Git repository: <path>` | `init`, `adopt`, or `update` was run on a directory without Git | Run `git init` in the target directory and repeat |
| `project harness already exists; use 'harness update <repo>'` | `init` where the snapshot is already installed | Run `harness update` |
| `project harness is missing; use 'harness init <repo>'` | `update` where there is no snapshot | Run `harness init` |
| `selected skill names already exist; inspect them or use --replace-conflicts` | The project already has skills with the same names | Look at the list of conflicts; if the replacement is expected, repeat with `--replace-conflicts` |
| `local skill changes would be overwritten; review them or use --force` | Managed files have local edits | Study the differences: for the snapshot use `--force-managed-files`, for the snapshot and seed files use `--force` |
| `discovery path already exists and is not managed: <path>` | Something foreign sits where the skills directory should be | For `init`, remove it manually or use `adopt`; for `adopt`, use `--replace-conflicts`; for `update`, use `--force` |
| `install-global.py`: `[CONFLICT] ... (re-run with --replace-conflicts ...)` | The profile or symlink location is occupied | Repeat with `--replace-conflicts`: the conflicting files are first copied to a backup |
| `install-global.py`: `Failed to create symlink` | No permission to create a directory symlink | Enable developer mode in the system or start the terminal with elevated rights |

## Project configuration

| Message (fragment) | Cause | What to do |
| --- | --- | --- |
| `.harness/project.json has unknown field(s): <name>` | A field outside the strict schema contract | Remove the field, or implement it at once in the schema, the template, and the validator; doing it separately is a divergence |
| `.harness/project.json tracker has unknown field(s): <name>` | A field inside `tracker` outside the contract | Only `type`, `host`, and `project` are allowed in `tracker` |

The allowed top-level fields are: `$schema`, `language`, `base_branch`, `branch_pattern`,
`qa_gate_commands`, `shell`, `tracker`, `ci_required_checks`, `test_paths`, `test_runner`,
`hook_policy`, `story_points`, `memory`, `memory_policy`.

Certificates, proxies, and credentials are not written to the configuration: they stay in the personal
configuration of the tracker CLI.

## Hooks and orchestration

| Message (fragment) | Cause | What to do |
| --- | --- | --- |
| `Zero Direct Commits: push с целевым рефом '<ref>' запрещён` | The command updates a protected branch | Work in an issue branch and push it; a human updates protected branches through a merge |
| `Zero Direct Commits: команду с git commit/push не удалось разобрать` | The command is built so that the hook cannot understand its effect | Split it into simple commands without substitutions, parentheses, and chains |
| `правка меняет ключ hook_policy в .harness/project.json` | An agent tries to change the hooks policy | A human changes the policy; the agent may edit the file without changing the key |
| `настройки hooks (.claude/settings*.json, .codex/hooks.json) и каталоги hooks` | An attempt to write to the hooks settings or directories | A human changes these files: their content determines what is blocked at all |
| `this repository is in the file-ledger epoch` | The project has not been moved to the runtime store yet, and the command needs the new epoch | Run `harness-runtime migrate` once as the [upgrade guide](upgrade-2-0.md) describes and repeat the command |
| `hook_response.py: ожидается 'run <hook_id> <команда...>' с зарегистрированным hook_id` on every Bash call | A new hook, such as `runtime-autostart`, is wired while `.claude/hooks/hook_response.py` is old | Run `harness update <repo> --force-seed-file .claude/hooks/hook_response.py`: the envelope is replaced with the template (the previous bytes go to `.harness/.sandboxes/seed-backups/`), and the same run wires the hook. A plain `harness update` no longer wires such a hook while the envelope does not know it, and `runtime-autostart` with an old envelope only warns |
| `ledger validate` finds a divergence in the audit chain | The state was edited around the CLI, or the chain is damaged | Do not edit `.harness/orchestration/state/` manually; read the report and decide by the recovery route |

The recovery commands (`ledger lock-status`, `qa clear-stale-lease`, `batch rewind`, `dispatch cancel`)
are not blocked by any hooks profile: otherwise there would be no way out of a refusal.

## health as the first step

`harness health <repo>` without flags changes nothing and shows checks of files, directories, the
environment, and the project graph.

- `--fix` creates the missing `.harness/` directories and rebuilds a stale skills registry; it does
  not touch worktrees.
- `--online` adds tracker checks: CLI authorization, remote availability, permissions, and labels.
- `--json` prints a machine-readable report for scripts.

Each line is marked `ok`, `warn`, `fail`, or `skipped`; on `fail` the command prints the cause and
the fix command. The "Orchestration" group appears only when `backend-orchestration` is installed.

## Next

- [CLI and configuration](../reference/cli.md)
- [QA gate and Release Gate](qa-gate.md)
- [Workflow](workflow.md)
