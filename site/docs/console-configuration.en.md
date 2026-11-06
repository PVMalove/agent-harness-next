# Project setup in the console

Run `python3 harness/bin/harness.py console /path/to/project` from the Harness distribution.
The console keeps this CLI source when you switch to another project.

## Connecting a project

On the home screen, choose "Open project" (key `1`). The screen guides you through the steps
"choose project → pre-checks → install/adopt → configure → final diagnostics"; the current step is
marked in the "Stages" frame. The "Project" and "Harness contents" frames are on the left, the
"Install plan" and "Checks" frames are on the right, and the "Result" frame with a colored log is at
the bottom. When the terminal is 120 columns wide or more, the frames form two columns; when it is
narrower, they form one column.

1. **Choose a project.** Enter a path or open "Browse directories". You need a local
   Git repository; for a new directory, run `git init` first. The "Browse folders" button
   opens and closes the directory picker, and "Check path" builds the plan. The console shows
   the absolute project root, the action (`init`, `adopt`, or `update`), and the installed contents.
2. **Pre-checks.** After the path check, the console runs the local diagnostics by itself.
   The GitHub/GitLab online checks run with a separate "Online" button in the "Checks" frame.
3. **Install.** You choose the Harness contents by the descriptions: workflow includes the
   `project.json` setup, and Backend adds roles and `orchestration.json`. For a project that is
   already installed, the installed contents are selected by default; changing the contents replaces
   the previous set of managed capabilities, and the plan warns you about this. The "Install" button
   opens the same confirmation form with the CLI command as the Harness section.
4. **Configure.** The "Configure" button in the "Checks" frame starts the wizard for the selected project.
5. **Final diagnostics.** After you close the wizard, the console repeats the local checks.
   The "Open project" button in the "Project" frame makes it the target of all console sections; the
   header of the home screen then shows the branch and commit of the new project.

The plan checks the occupied discovery paths, the project's own files, and drift of the managed snapshot.
You must resolve conflicts before the install; this menu does not enable force or replace.
Cancel keeps the previous target. While a command runs, you cannot switch the project. The results
of background checks of the previous project do not reach the new screen, because the dashboard
cancels its workers when it closes, and a late result from a closed screen is discarded.

The "Checks" frame has four buttons: "Offline" and "Online" run diagnostics, "Fix"
applies local fixes, and "Configure" opens the wizard.

### Diagnostics on connect

The report starts with a summary: how many checks ran, how many were skipped, and how many
need a fix. A skipped check does not count as passed. The Codex/Claude sandbox checks
analyze settings files, not actual access, and the summary says so separately.
The online check covers authorization, repository access, and permissions; a local
tracker skips the network checks. After confirmation, "Fix locally" applies the
existing local health fixes (without the network and without changes to the external tracker) and
repeats the check. The log in the "Result" frame highlights statuses: success in green, warnings in
amber, errors in red.

## Updating Harness

The "Update Harness" section (key `2`) shows the frames "Versions" (the installed and available
version, and whether an update is needed), "What changes in managed files" (drift from `harness diff --json`),
"Update mode", "Seed files", "Plan", "Diff", and "Result".

There are three modes: a plain `update`, an `update` that overwrites managed files
(`--force-managed-files`), and an `update` that overwrites selected seed files. The seed file list
shows only the files that differ from the template; the ☑/☐ checkboxes select which of them to overwrite, and
"Select all" and "Clear selection" change all marks at once. The selected files are passed with the flag
`--force-seed-file PATH`, one flag per file; the other seed files stay as they are. The file list
on the left in the "Diff" frame opens the line-by-line changes of the selected file, with added and
removed lines highlighted. The "Update" button opens a confirmation form with the exact CLI command;
"Check again" rereads the drift. The section does not change files until you confirm the run.

### Runtime adapters in settings

The initial "Configuration setup" screen shows the state of each adapter:
"not installed", "up to date", or "needs update". The "Preview install and update" button
opens the list of changes of a plain `harness update`; writing starts only after confirmation.
Cancel keeps the files, and a plan that changed after the preview requires a new preview.

The console restores missing adapters and updates managed versions within the current capability
set. It does not enable force, does not change the transport, and does not add `backend-orchestration`
automatically. If a capability is missing, the window shows an explanation and a CLI hint for an explicit
choice of contents. You must resolve local changes and collisions before you confirm the update.

## Steps and draft

Open "Configuration setup" (key `8`) and choose `project.json`, `orchestration.json`,
or both files in the "Configuration editing" frame. The wizard loads the
existing values, and a missing file starts from the standard template.
Without the matching capability, the wizard offers to install it first.

The steps are grouped by schema sections. Each step shows the purpose of the field,
the recommendation and its reason, the current answer, and its effect. The recommendation takes the
project traits into account: the default branch, the tracker type, the Makefile, and the stack. The recommended option in the list
is marked with ★. For key values, the wizard describes the effect, the limit, and the use case.
Choose an answer or enter a value. Strings are entered without quotes; numbers, lists, and
objects are entered as JSON. Single choice is used for mutually exclusive values, and checkboxes are used
for booleans and lists of enums. A choice page shows at most four values; the
"More options" button opens the next group.

A block with fields (for example `memory_policy`) is shown as a summary: which fields are already set, while the fields themselves
are configured on the next steps. Records with arbitrary names (`assignment_plans`,
`provider_profiles`) and lists of strings are edited in two ways, which the buttons
"Via menu" and "As text (JSON)" switch between. In the menu, you select a record in the list: "Configure record" (or Enter)
opens its fields, "Delete record" removes it, and "Add record" creates a new one from the pattern of the
selected record and opens its fields at once. For a list of strings, there are "Add item" and "Delete item".
Both ways change the same draft.

Ctrl+C and Ctrl+V work with the system clipboard through `wl-copy`/`wl-paste`, `xclip`, `xsel`,
`pbcopy`/`pbpaste`, or PowerShell; without such a utility, the application clipboard remains, and pasting from the
terminal (usually Ctrl+Shift+V) always works. The variable `HARNESS_CONSOLE_SYSTEM_CLIPBOARD=0`
disables the system clipboard.

The "Back" and "Next" transitions keep the answers in the draft. The step list lets you
jump to the field you need. You can add, change, or remove an optional object
as a whole; after you add it, its nested fields are available. This is how you edit additional
profiles, role assignments, access/tool policies, and extensions.

Press "Review summary". The console shows both kinds of checks — the JSON schema constraints
and the current Health/orchestration validators — together with the full JSON
and the differences. The "Go to the step with the error" list opens the field that the
message refers to. `approval_policy=auto` requires `trusted` and `worker_attestation_required=true`;
the `access_policy` setting does not grant the runtime access by itself.
The diagnostics check the actual QA commands and access separately.

"Apply" requires confirmation of the target and overwrites the selected working files.
If another process changes a file while the wizard is open, the write stops.
Then the "Load external changes" button accepts the new file contents and applies your edits
to them again; fields changed both by you and from outside are listed in the
message (your value wins). After that, review the summary again and apply it.
Closing before apply discards the draft after confirmation.

## Versions and recovery

You can save a version in two ways: "Save version"
in the "Saved versions" frame of the main configuration menu
saves the current working set as is, and the same button on the summary screen saves the filled-in
draft without applying it. Each snapshot contains a consistent set of both files, including
the absence of a file, the date, the description, the identifier, the installed Harness version, and the SHA-256
of the files. Versions are stored in `.harness/config_versions/` of the selected project (the full path is shown in
the "Saved versions" frame and on the versions screen), are ignored by Git
in the standard installation, and survive soft/hard cleanup. The decision to publish versions to Git
is made separately; by default they stay local. The ledger and worktrees are not part of the snapshot;
recovery does not change the brief/batch that are already recorded.

The "Versions / rollback" screen consists of the frames "Storage" (the project and the versions directory path), "Versions",
"Differences" with a colored diff, and "Actions". It shows the metadata and the differences from the active
configuration; if there are no versions, it says so and disables recovery.
After the hash and compatibility checks, you can restore the selected version
with confirmation. If the version was created for another Harness release, the screen warns you
about it. Before an apply or a rollback, the current files are saved in a separate
snapshot: it lets you return to the previous state. Files that are absent from the snapshot
are deleted during recovery.

A damaged version (for example, with an unreadable manifest) stays in the list with a ⚠ mark
and the reason. You cannot apply an incompatible version: the screen names the fields that violate
the contract and does not change the active configuration. To use its content, apply
another version, or fix the fields in the wizard and save a new version.

If the current file contains a value that looks like a secret (for example, `TOKEN=abc` in a QA command),
you cannot create a backup: the message names the file. Replace the value with a reference to an
environment variable, for example `TOKEN=$CI_TOKEN`; such references do not count as secrets.

A file lock and a journal serialize writes. During an unfinished
transaction, the Health, tracker, and coordinator readers get the previous set.
The next time you open the wizard, the unfinished write is recovered. If the files were changed by hand after
a failure, the automatic recovery stops
to keep the external edits. Direct manual JSON readers do not use this
protocol; `read_config_bundle` and
`read_config_file` from `harness/configuration.py` are meant for a consistent read of the pair.

## CLI hints

AI is off by default. When a step opens, the console determines, without a model request, the
availability, flags, and authorization of `codex` and `claude`; the "Check CLI" button repeats the
check. An unavailable option is disabled and labeled with the reason. Choose an available CLI
and press "Suggest with AI". The CLI itself must already have a valid authorization;
the wizard does not open a login, does not ask for an API key, and does not read auth files.

The subprocess keeps the standard HOME/CODEX_HOME and runs in a separate temporary
directory. The request contains the name/type of the current field, up to four valid options, the
standard explanation, the OS, the presence of known stack files, and the console recommendation. Commands,
project paths, and values of its configuration are not sent. The helper compares the options
(up to four lines of "option — consequences") and explains why the selected one suits the project
from these traits; it does not invent information outside the context.

Codex runs through `exec` with a read-only sandbox, without the user config,
rules, shell, hooks, plugins, MCP from the user config, and other helper
tools. Claude Code uses `-p --safe-mode --tools "" --strict-mcp-config`,
and keeps the OAuth/keychain authorization; `--bare` is not used here.
The CLI diagnostic output (stderr) is separate from the answer, so warnings do not spoil the
structured result. The session is not continued and is not saved. The request is limited to
90 seconds and to the answer size; moving to another step or closing cancels the pending
result. Compatibility is determined from `--help` of the installed version: if the needed flag
is missing, the wizard falls back to the plain hints.

You can take the suggestion into the draft with a separate button. The general checks and the final
confirmation stay mandatory. If the CLI or login is missing, the version is unsupported,
or there is a network error, a limit, or an unsuitable answer, the wizard explains the refusal
and keeps working with the plain hints.

Configurations, version descriptions, and answers are checked for recognizable secrets,
but this is not a universal detector. Do not enter secrets in these fields.
Keep the authorization in the standard CLI storage.

## What is not checked automatically

- A manual scenario in a separate Backend project and a real Codex/Claude request from the console
  are run by a human; the report about them is published in the project tracker.
- Automated tests replace GitHub/GitLab and the CLI with controlled responses, including a refusal
  and a timeout; real checks run in an agreed environment.
- The `msvcrt` lock branch (Windows) was not executed in the tests on Linux.
