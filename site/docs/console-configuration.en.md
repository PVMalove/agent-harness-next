# Configure a project in the console

The console connects a Git repository, edits `project.json` and `orchestration.json`, checks the
result and saves configuration versions. It previews changes and asks before writing.
Field definitions belong in [Settings](getting-started/settings/index.md).

This guide describes the terminal interface. Its keyboard shortcuts and action names do not
describe the layout of the web console.

## Connecting a project

1. Choose "Open project" (`1`) on the home screen and enter a local Git repository path.
   Run `git init` first for a new directory.
2. Choose "Check path". The console identifies `init`, `adopt` or `update`, installed capabilities
   and conflicts. Local diagnostics start automatically.
3. Review the installation plan. Changing capabilities replaces the managed capability set.
   Resolve conflicts and local edits before confirmation; this screen does not enable force.
4. Confirm the displayed installation command, then open "Configure".
5. After configuration, review the repeated diagnostics. "Open project" makes the selected
   repository the target of the other console sections.

Cancel keeps the previous target. You cannot switch projects while a command runs.

### Diagnostics on connect

"Offline" checks local files and the environment. "Online" separately checks authentication,
repository access and GitHub/GitLab permissions; a local tracker skips network checks.
After confirmation, "Fix" applies local health repairs and repeats diagnostics.

`skipped` means a check did not run. Reading sandbox settings files does not prove actual worker
access. See the [orchestration access chapter](guides/orchestration/access.md).

## Updating Harness

Open "Update Harness" (`2`) and inspect the version, drift and diff of each changed file.
Choose a mode before confirming the command.

| Mode | What it changes |
| --- | --- |
| Plain `update` | Updates under normal rules and reports local conflicts |
| `--force-managed-files` | Overwrites the managed snapshot, preserving seed files |
| Selected seed files | Passes `--force-seed-file PATH` for each selected file |

"Check again" rereads changes. Review the plan again if it changes after the preview.

### Runtime adapters in settings

The install/update preview shows missing or outdated adapters.
A confirmed plain `harness update` restores them within the selected capability set.
It does not change transport or add `backend-orchestration` automatically.

## Steps and draft

1. Open "Configuration setup" (`8`) and choose one or both files.
   The wizard loads current values and uses a template for a missing file.
2. Visit the fields you need. Each step describes its purpose, current answer and recommendation
   with a reason. Enter strings without quotes; enter numbers, lists and objects as JSON.
3. For `provider_profiles`, `assignment_plans` and lists, choose menu or JSON editing.
   Both update the same draft. "Back" and "Next" preserve answers.
4. Choose "Review summary". Inspect JSON, the diff, schema checks and validator diagnostics.
   The error list links to the relevant field.
5. Choose "Apply" and confirm the target. Working files stay unchanged until this action.

If a file changes externally, writing stops. "Load external changes" merges the new version with
your draft and lists conflicting fields; your answers win in those fields.
Review the diff again before applying. Closing an unsaved draft requires confirmation.

`approval_policy=auto` requires `trusted` and `worker_attestation_required=true`.
Setting `access_policy` does not itself grant runtime access.

The clipboard uses an available system utility; without one, the application clipboard remains.
`HARNESS_CONSOLE_SYSTEM_CLIPBOARD=0` disables the system clipboard. Terminal paste is usually
available through Ctrl+Shift+V.

## Versions and recovery

"Save version" in the configuration menu saves the working configuration.
The same button on the summary screen saves the draft without applying it.
A snapshot includes both files, including file absence, description, date, Harness version and hashes.
It stays local in `.harness/config_versions/` and survives cleanup. It excludes the ledger and worktrees.

Before restoring, select a version, read its diff and confirm.
The console checks hashes and compatibility. Before applying or rolling back, it saves the current
files as a separate version. Restoring a snapshot that omits a file deletes that file.
A damaged or incompatible version cannot be applied.

A file lock and journal protect coherent writes of the two configuration files.
The wizard recovers an interrupted transaction; if files were edited manually afterwards,
automatic recovery stops to preserve external edits.

Do not enter secrets in commands, configuration or version descriptions. A recognized secret blocks
snapshot creation; a variable reference such as `TOKEN=$CI_TOKEN` is allowed.
Detection does not cover all secrets. Keep authentication in the standard CLI store.

## CLI hints

AI is off by default. "Check CLI" determines whether `codex` and `claude` are present, support the
required flags and are authenticated, without asking a model. To make a request, select an available
CLI and choose "Suggest with AI". The wizard uses existing CLI authentication and does not ask for keys.

The request includes the field description, up to four choices, stack traits, OS and recommendation.
Commands, the project path and configuration values are not sent. The CLI runs in a temporary directory
while keeping its normal authentication environment. Codex uses a read-only sandbox with user settings
and tools disabled; Claude Code uses `-p --safe-mode --tools "" --strict-mcp-config`.
The session is neither saved nor continued. Requests have a 90-second limit and a response-size limit.
Moving to another step cancels the pending result.

Taking the answer into the draft is a separate action. Checks and write confirmation remain required.
Unsupported CLI versions, network, authentication or response errors leave plain hints available.

## What is not checked automatically

Automated checks do not prove an external tracker, a real model request or actual worker permissions
in your environment. These scenarios need separate checks.
Console behavior is checked against [its source](https://github.com/PVMalove/agent-harness-next/tree/master/harness/console).
