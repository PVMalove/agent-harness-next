# Integrate Project — Project integration

## 1. Name and localization

- **English name:** `Integrate Project`
- **Russian translation:**

```text
Интеграция проекта
```

## 2. Full translation of the skill text

<div class="ah-skill-text" markdown="1">

```yaml
name: integrate-project
description: Audit an existing, already-substantial codebase and fold this harness into it without disrupting what is already there. Use when a repository already has meaningful code, conventions, CI, or other AI-tool configuration and needs the harness (skills, AGENTS.md, discovery links) integrated for the first time. For a brand-new idea, an empty or near-empty repository, or revising an already-harnessed project, use `start-project` instead.
```

### Integrate Project

Integrate the portable harness into a codebase that already exists, without guessing what the project already knows about itself. Read the real files before asking; treat the repository, not the conversation, as the primary source of truth.

Resolve the real path of this skill and confirm that the public `agent-harness` root two levels above it contains `skills/REGISTRY.md` and `harness/bin/harness.py`. This resolution is complete only when both files exist; otherwise report that the public package is incomplete instead of assuming a different installation.

#### Audit

1. **Stack and commands.** Read the manifests directly — `package.json` (and its `scripts`), lockfiles, `pyproject.toml`/`requirements.txt`, `go.mod`, `Cargo.toml`, `Gemfile`, or their equivalents. Derive the stack and the real install/run/test/lint/build commands from what is actually configured, not from README claims or the user's memory.
2. **Conventions the manifest does not state.** Read the CI workflow files (`.github/workflows/*`, `.gitlab-ci.yml`, and so on) for the commands CI actually runs — the real state of things outweighs documentation, which may be stale. Read recent branch names (`git branch -a`, `git log --all --oneline -20`) and the remote's default branch for `branch_pattern` and `base_branch`. Study the existing test/documentation directory structure instead of assuming a convention.
3. **Existing AI-tool configuration.** Look for `AGENTS.md`, `CLAUDE.md`, `.cursor/rules`, `.github/copilot-instructions.md`, and a `.claude/` directory that this harness does not manage (where `.harness/harness.lock` does not exist yet). Read what is there. An existing instruction that conflicts with this harness's conventions is a finding to reconcile with the owner, not a file to overwrite silently.
4. **Domain.** Classify the project's primary work — software, content, research/knowledge, operations, personal, or another explicit domain — based on what the repository actually contains.
5. **What the files cannot answer.** The Definition of Done, the delivery/merge policy, and the prohibited actions are rarely found in the repository. Mark them as open questions instead of guessing them from stack conventions.
6. **Decision-history signal.** Check whether the repository already has an ADR (architecture decision record log) or decision-record convention (`docs/adr/`, or another place that an existing document points to), and get a rough idea of its merge/session history (`gh pr list --state merged` / `glab mr list --merged`, `git log --all --oneline | wc -l`). This is a signal for the optional "Reconstruct decision history" stage below, not the investigation itself — only skim it.

The audit is read-only. Do not write, install, or choose capabilities at this stage.

#### Presentation and confirmation

Summarize the results briefly: the stack, the real commands, the branch/CI convention, the detected domain, any existing AI-tool configuration and where it conflicts with this harness, and the recommended capability. Ask only about what the Audit left truly open — do not re-ask what a file already answered.
Do not continue until the owner confirms this manifest.

If step 6 found a meaningful history and there is no existing decision-record convention, offer the optional "Reconstruct decision history" stage below separately — call it a slow investigation, independent of the harness installation, so that the owner can easily decline it. Agreement here does not change this manifest; a refusal does not block the Install.

#### Install

Continue from the "Assemble" section of `global-skills/start-project/SKILL.md`, starting at step 2 and onward, using this audit in place of its step 1 (which the Audit stage of this skill already covers more deeply), together with its "Finish" section unchanged. A repository that reaches this skill has, by definition, no existing harness, so Assemble step 5 (`harness init`) applies, not step 6 (`harness update`/`adopt`) — unless the Audit found an already present `.harness/harness.lock` file, in which case stop and switch fully to `start-project`: that is routine harness maintenance, not a first integration.

Set `hook_policy` with the `standard` profile explicitly, as Assemble step 5 says: put the profile in the confirmed manifest and, after `harness init`, verify that `.harness/project.json` contains `"hook_policy": {"profile": "standard"}` and that `harness health` shows `hooks.policy` with the `standard` profile. The repository's own hooks stay in their native files: `harness init` merges them with the managed entries and does not replace them.

#### Reconstruct decision history (optional)

Only when the owner agreed above. This is a separate read-only investigation, independent of the Install in both directions — it does not block the Install and does not require the harness to be installed first.
Read [RECONSTRUCT-HISTORY.md](https://github.com/PVMalove/agent-harness-next/blob/master/global-skills/integrate-project/RECONSTRUCT-HISTORY.md) for the sources, the evidence discipline, the ADR template, and the shape of the final report. This stage writes no file — including no ADR — until the owner has seen that report and separately authorized exactly which ones to write.

</div>

## 3. Contracts

- **Input (Input/Brief):** an existing substantial repository without the harness, and the owner's confirmation.
- **Process (Process):** a read-only audit, manifest approval, then Assemble/Finish from `start-project` and, if the owner chooses, history reconstruction.
- **Output (Output/Report):** the confirmed manifest, the integrated harness, and a report of open questions.

## Source

[SKILL.md](https://github.com/PVMalove/agent-harness-next/blob/master/global-skills/integrate-project/SKILL.md)
