# Start Project — Start a project

## 1. Name and localization

- **English name:** `Start Project`
- **Russian translation:**

```text
Начать проект
```

## 2. Full translation of the skill text

<div class="ah-skill-text" markdown="1">

```yaml
name: start-project
description: Start a new project from an idea or create, audit, or update its self-contained agent harness. Use when the user wants to shape or initialize a software, content, research, operations, personal, or other project, decide when it needs a repository, or install or revise a project harness. Ordinary work inside an already-harnessed project does not invoke this skill; a repository with substantial existing code and conventions but no harness yet is better served by `integrate-project`'s deeper audit.
```

### Start project

Own the path from an unshaped idea to a portable project. A repository, stack, tracker, and harness
are outputs of project design, not prerequisites. Keep each phase read-only until the owner confirms
its proposed durable artifact.

Resolve this skill's real path and verify that the public `agent-harness` root two levels above it
contains `skills/REGISTRY.md` and `harness/bin/harness.py`. Its vendored workflows are a library: use
the registry to locate and read only the exact `SKILL.md` needed for the current phase. This
resolution is complete only when both files exist; otherwise report that the public package is
incomplete instead of guessing another installation.

#### Shape

1. Establish whether the user has an idea, a seed directory, or an existing repository. Inspect
   existing files before asking questions. A repository with substantial existing code and
   conventions but no harness yet is `integrate-project`'s dedicated audit, not this generic path —
   hand off to it rather than deriving facts thinly here.
2. Classify the project's primary work as software, content, research/knowledge, operations,
   personal, or another explicit domain. Classification selects workflows; it does not constrain
   what the project may become.
3. Resolve the decisions that change the next artifact. For an unshaped idea, read and follow
   `skills/vendor/mattpocock/productivity/grilling/SKILL.md`. Use `research`, `to-questionnaire`,
   `prototype`, or `domain-modeling` only when its registry description matches the current branch.
   Tracker-dependent workflows such as `to-spec` and `wayfinder` begin after a repository and its
   tracker contract exist.
4. Keep disposable thinking in the session. Once purpose, intended outcome, recurring work, and
   the next useful artifact are known, recommend exactly one of: continue the conversation, write a
   brief, create a seed repository, or assemble a harness.

Shape is complete only when the owner confirms that recommendation or explicitly keeps the work in
the conversation. Confirmation authorizes that one artifact, not later scaffolding.

#### Seed

After the owner confirms a seed, create or reuse the named Git repository and write only the
confirmed brief and decision notes. Preserve an existing repository's layout and instructions.
Record unresolved stack, tracker, and harness decisions as unresolved rather than choosing them to
make the seed look complete.

Seed is complete when the repository path is verified, durable files contain only confirmed facts,
`git status` has been inspected, and the owner can see which decisions remain open. Application
code, tracker setup, and a harness require their own confirmed next artifact.

#### Assemble

Build a harness only after the project has stable work to support, or immediately when the user
explicitly requests one.

1. Derive purpose, project type, stage, base branch, tracker, recurring activities, commands,
   boundaries, delivery policy, and Definition of Done from the repository and conversation. Mark
   inapplicable commands and tracker as `N/A`.
2. Select the smallest coherent public capability:
   - `project-foundation` for general project thinking, research, handoff, domain language, and
     agent-facing instructions;
   - `mattpocock-suite` for the unmodified upstream engineering skills;
   - `engineering-suite` instead of `mattpocock-suite` for this harness's ticket, review, QA and PR
     workflow configured in `.harness/project.json`;
   - `backend-orchestration`, which includes `engineering-suite`, only for the gated `/implement`
     route;
   - no additional package merely because it is available.
3. When the owner names a team preset, or the project has `.harness/catalogs.json`, list presets
   with `harness catalogs <repo>` and preview one with `harness presets <repo> --catalog <id>
   --entry <id>`. Apply it with `--apply` only after the owner confirms the preview. A preset does
   not authorize unrelated personal knowledge, tasks, notes, or secrets. For `engineering-suite` or
   `backend-orchestration`, read [references/engineering-setup.md](#engineering-setup)
   before writing the manifest.
4. Present one harness manifest containing the project facts, public capability, overlay packages,
   project-only packages, integrations, boundaries, and files that will change. Resolve same-name,
   provenance, and licensing conflicts, then obtain owner confirmation for this manifest.
5. For a confirmed new harness run the resolved package command, replacing the example values with
   the confirmed manifest:

   ```bash
   python3 "<resolved-agent-harness-root>/harness/bin/harness.py" init "<repo>" \
     --project-type <type> \
     --capability <selected-capability> \
     --base-branch <branch>
   ```

   For `engineering-suite` and `backend-orchestration`, also pass every value the manifest
   confirmed: `--language`, `--pr-base-branch`, `--branch-pattern`, `--qa-gate-command` (repeat in
   run order), `--tracker-type`, `--tracker-host`, `--tracker-project`, `--test-path` (repeatable).
   Without a terminal, `harness init` silently takes the default for every omitted value.

   On Windows/PowerShell there is no `python3` (use `python`), and line
   continuation is `` ` ``, not `\`.

   Fill every unresolved `{{...}}` in `AGENTS.md`. Add project-only packages under
   `.harness/skills`; run `harness lock-project-skills` for their versioned hash lock, then
   `harness registry` after composing all packages. Use relative discovery links, never links back
   to a machine-local catalog.

   For `engineering-suite` and `backend-orchestration`, install `hook_policy` with the `standard`
   profile explicitly: name the profile in the manifest and, after `harness init`, verify that
   `.harness/project.json` holds `"hook_policy": {"profile": "standard"}` and that `harness health`
   reports `hooks.policy` with profile `standard`. Do not pick `minimal` or `strict` unless the
   owner asked for it. Other capabilities create no `.harness/project.json` and no hooks.

   When the manifest includes `backend-orchestration`, the new project needs its runtime store
   before the first `batch create`. The store needs a human approval, so do not run the command
   yourself. Show the owner the command with the real path, ask them to run it with their own
   approval, and wait for their confirmation:

   ```bash
   harness-runtime init --repo "<repo>" \
     --approved-by <human> --approved-at <RFC 3339 time> --reason <text>
   ```

   After the confirmation, `harness health` no longer warns at `orchestration.ledger_summary`.
6. For an existing harness run `harness diff` before `harness update`. Use `harness adopt
   --replace-conflicts` only for an explicit migration after reviewing same-name conflicts.
   `harness update` does not write `hook_policy`; leave the `hook_policy` of an existing project to
   its owner.
7. Keep MCP servers, plugins, hooks, and runtime settings in their native project files. When such
   files exist, inventory their relative paths, hashes, runtimes, verification action, and secret
   environment-variable names in `.harness/integrations.json`; never copy credentials into Git.

Assemble is complete when the confirmed manifest is represented by committed project files, every
package has source and hash provenance, and no unconfirmed integration or workflow was added.

#### Finish

Prove each layer separately:

1. **Stored** — selected packages and locks exist under `.harness/`.
2. **Wired** — `.agents/skills` and `.claude/skills` resolve to the same project snapshot.
3. **Healthy** — `harness health` passes: template markers, names, registry, public/overlay hashes,
   discovery links, and integration inventory agree.
4. **Advertised** — a fresh runtime session lists an installed project skill. If the runtime has no
   native project skill root, it can route through `.harness/skills/REGISTRY.md` from `AGENTS.md`.
5. **Invoked** — that session opens the selected skill through its native mechanism.

If the current session cannot rescan discovery, report steps 4 and 5 as the exact remaining fresh-
session check. Finish by naming the project type, installed capabilities, excluded surfaces,
verification evidence, and next useful action. With a GitHub or GitLab tracker under
`engineering-suite` or `backend-orchestration`, that action is `/setup-labels`.

#### `references/engineering-setup.md` { #engineering-setup }

Read this file when the manifest selects `engineering-suite` or `backend-orchestration`. Each command
below takes the project path as `<repo>`; `harness <command> --help` lists its flags. Put every value
and integration from this file into the manifest, and write or apply it only after the owner confirms.

##### `harness init` values

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

##### Team presets, catalogs and `pr_checklist`

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

##### Explicit invocation

`--no-model-invocation <skill>` (repeatable) on `harness init`, `harness update` or `harness adopt`
makes a managed skill run only when invoked by name in this project; `harness.lock` records the
choice. `--clear-no-model-invocation <skill>` restores the packaged policy. A skill that is
explicit-only at its source stays explicit-only. Offer it when the owner wants a model-invoked skill
to run only on request.

##### Runtime events

For project commands on runtime lifecycle events (`session_start`, `session_end`, `stop`), write
`.harness/runtime-events.json` with `runtimes` and `events`, then run `harness runtime-events <repo>`.
It writes each runtime's native config (`.claude/settings.json`, `.codex/hooks.json`,
`.cursor/hooks.json`) and records it in `.harness/integrations.json`; `--list-adapters` shows the
paths and events. In Codex, the owner reviews and trusts the new hook definitions in `/hooks`.

##### Inventory

For the **Wired** layer in Finish, run `harness inventory <repo> --json`. It lists each skill's
source, selecting capability, project path and drift, and in `discovery` each runtime discovery path
with its state: `linked`, `missing`, `foreign` (not a Harness link) or `unresolved`. Wired holds
when every discovery path the project uses is `linked`.

##### `backend-orchestration` only

- **Runtime store.** The owner runs `harness-runtime init` as `SKILL.md` Assemble step 5 shows.
- **`pre_qa_commands`** in `.harness/orchestration.json` — project checks that the QA gate runs on
  the candidate after environment preparation. Developer and review dispatches do not run them, and
  a new batch pins the list. Fill it from the CI checks the audit found and the owner confirmed.
  `/fast-implement` and `/qa-gate` do not use it.
- **Workflow overlays.** `harness workflow-overlays <repo> --manifest <file>` previews named-slot
  edits (`post-developer`, `pre-review`, `qa-preparation`, `pre-qa`) to `.harness/orchestration.json`;
  `--apply` writes them with a backup. A YAML manifest needs a Python with PyYAML.

</div>

## 3. Contracts

- **Input (Input/Brief):** an idea, a seed directory, or a repository, plus the owner's answers.
- **Process (Process):** run Shape, Seed, Assemble, and Finish in order; each durable write needs a separate owner confirmation.
- **Output (Output/Report):** a verified repository, a manifest, and a wired project harness, or the exact next artifact.

## Source

[SKILL.md](https://github.com/PVMalove/agent-harness-next/blob/master/global-skills/start-project/SKILL.md)
