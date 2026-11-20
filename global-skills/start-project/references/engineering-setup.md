# Engineering setup

Read this file when the manifest selects `engineering-suite` or `backend-orchestration`. Each command
below takes the project path as `<repo>`; `harness <command> --help` lists its flags. Put every value
and integration from this file into the manifest, and write or apply it only after the owner confirms.

## `harness init` values

`.harness/project.json` is created only by `harness init` for these two capabilities. Derive each
value from the repository, confirm it in the manifest, and pass it as a flag:

- `--language ru|en` — the project's output language (default `ru`).
- `--base-branch` and `--pr-base-branch` — the default branch and the release base for epic
  integration branches (default: `--base-branch`).
- `--branch-pattern` — the issue-branch regex (default `^feature/issue-[0-9]+-.+`).
- `--qa-gate-command` — repeat once per command, in run order; this becomes `qa_gate_commands`
  (default: empty, and `/qa-gate` then stops and asks).
- `--tracker-type github|gitlab|local`, `--tracker-host`, `--tracker-project` — default: derived
  from `origin`.
- `--test-path` (repeatable) and `--test-runner-command` — the test author's write zone and runner;
  no default.

Without a terminal, `harness init` takes the default for every omitted flag without asking.

## Team presets, catalogs and `pr_checklist`

- `harness presets <repo> --manifest <file>` previews which configuration files a preset changes;
  `--apply` writes them with a backup. A preset's `requires` checks the installed capabilities, its
  `qa_gate_commands` and `pr_checklist` lists are appended without duplicates, and its
  `workflow_overlays` add orchestration overlays by ID.
- `harness catalogs <repo>` (optionally `--source <id>`) lists the presets that the sources in
  `.harness/catalogs.json` index; it shows metadata only. `harness presets <repo> --catalog <id>
  --entry <id>` previews one entry. Applying a catalog entry needs that source set to
  `"access": "install-allowed"` with the reviewed index's SHA-256 in `sha256`; that change is the
  owner's decision after they review the index and the preset.
- `pr_checklist` in `.harness/project.json` holds up to 32 single-line project questions that
  every PR body answers with project evidence (`docs/agents/git-workflow.md`). `harness init` has no flag for it: add it through a
  preset or by editing the file, then run `harness health`.

## Explicit invocation

`--no-model-invocation <skill>` (repeatable) on `harness init`, `harness update` or `harness adopt`
makes a managed skill run only when invoked by name in this project; `harness.lock` records the
choice. `--clear-no-model-invocation <skill>` restores the packaged policy. A skill that is
explicit-only at its source stays explicit-only. Offer it when the owner wants a model-invoked skill
to run only on request.

## Runtime events

For project commands on runtime lifecycle events (`session_start`, `session_end`, `stop`), write
`.harness/runtime-events.json` with `runtimes` and `events`, then run `harness runtime-events <repo>`.
It writes each runtime's native config (`.claude/settings.json`, `.codex/hooks.json`,
`.cursor/hooks.json`) and records it in `.harness/integrations.json`; `--list-adapters` shows the
paths and events. In Codex, the owner reviews and trusts the new hook definitions in `/hooks`.

## Inventory

For the **Wired** layer in Finish, run `harness inventory <repo> --json`. It lists each skill's
source, selecting capability, project path and drift, and in `discovery` each runtime discovery path
with its state: `linked`, `missing`, `foreign` (not a Harness link) or `unresolved`. Wired holds
when every discovery path the project uses is `linked`.

## `backend-orchestration` only

- **Runtime store.** The owner runs `harness-runtime init` as `SKILL.md` Assemble step 5 shows.
- **`pre_qa_commands`** in `.harness/orchestration.json` — project checks that the QA gate runs on
  the candidate after environment preparation. Developer and review dispatches do not run them, and
  a new batch pins the list. Fill it from the CI checks the audit found and the owner confirmed.
  `/fast-implement` and `/qa-gate` do not use it.
- **Workflow overlays.** `harness workflow-overlays <repo> --manifest <file>` previews named-slot
  edits (`post-developer`, `pre-review`, `qa-preparation`, `pre-qa`) to `.harness/orchestration.json`;
  `--apply` writes them with a backup. A YAML manifest needs a Python with PyYAML.
