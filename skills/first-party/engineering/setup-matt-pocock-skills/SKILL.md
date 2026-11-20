---
name: setup-matt-pocock-skills
description: Configures the issue tracker, triage labels and domain docs the engineering skills read, in .harness/project.json and .harness/instructions/. Run once before first use; the labels themselves come from /setup-labels.
disable-model-invocation: true
---

# Setup Matt Pocock's Skills

Configure the per-repo settings the engineering skills read. Under the harness, `harness update` seeds
the guides and this skill fills in the project-specific parts:

- **Issue tracker** — `tracker` in `.harness/project.json`; the commands for every tracker type live in
  `.harness/instructions/issue-tracker.md`.
- **Triage labels** — the label vocabulary in `.harness/instructions/triage-labels.md`; `/setup-labels`
  creates the labels in GitHub or GitLab.
- **Domain docs** — where `CONTEXT.md` and ADRs live.

This is a prompt-driven skill: explore, present what you found, confirm with the user, then write.

## Process

### 1. Explore

Read the current state:

- `.harness/instructions/issue-tracker.md` and `.harness/instructions/triage-labels.md`. If either is
  missing, stop and tell the user to run `harness update`, which seeds them; old installs keep them in
  `docs/agents/`, and the same update moves them.
- `tracker` in `.harness/project.json`, and `git remote -v`: GitHub, GitLab (`gitlab.com` or a
  self-hosted host), or no remote.
- `.scratch/` — sign that the local markdown tracker is already in use.
- `AGENTS.md` and `CLAUDE.md` at the repo root, and an existing `## Agent skills` section in either.
- `CONTEXT.md`, `CONTEXT-MAP.md`, `docs/adr/`, and monorepo signals (`pnpm-workspace.yaml`, a
  `workspaces` field in `package.json`, a populated `packages/*` with its own `src/`).

### 2. Present findings and ask

Summarise what is present and what is missing. Take the sections in order — one section, one answer —
and lead each with the recommended answer. Skip a section that exploration already settled.

**Section A — Issue tracker.** Recommend the tracker the remote points at; otherwise offer GitHub,
GitLab, local markdown (`.scratch/<feature>/`), or another tracker the user describes in one paragraph.

**Section B — Triage labels.** The vocabulary is the harness taxonomy in
`.harness/instructions/triage-labels.md`. For GitHub or GitLab, recommend running `/setup-labels` once
after this skill. The local markdown tracker has no labels.

**Section C — Domain docs.** Default to **single-context**: one `CONTEXT.md` and `docs/adr/` at the repo
root. Offer **multi-context** (a root `CONTEXT-MAP.md` pointing to per-context `CONTEXT.md` files) only
when exploration found monorepo signals.

### 3. Confirm and edit

Show the user a draft of the `tracker` value, any added section of
`.harness/instructions/issue-tracker.md`, and the `## Agent skills` block below. Let them edit before
writing.

### 4. Write

- Set `tracker` in `.harness/project.json` to the chosen type, host and project, then run
  `harness health` and fix what it reports for `tracker`.
- For another tracker, add a section to `.harness/instructions/issue-tracker.md` that records the
  user's workflow as prose, next to the GitHub, GitLab and local markdown sections.
- Add or update the `## Agent skills` block in `CLAUDE.md` if it exists, else in `AGENTS.md`; when
  neither exists, ask which one to create. Update an existing block in place and keep the surrounding
  sections as they are.

```markdown
## Agent skills

### Issue tracker

[one-line summary of where issues are tracked]. See `.harness/instructions/issue-tracker.md`.

### Triage labels

[one-line summary of the label vocabulary]. See `.harness/instructions/triage-labels.md`.

### Domain docs

[single-context: `CONTEXT.md` and `docs/adr/` at the root, or multi-context: `CONTEXT-MAP.md`].
```

### 5. Done

Tell the user the setup is complete, which engineering skills now read these files, and that the
next step for GitHub or GitLab is `/setup-labels`. They can edit `.harness/instructions/*.md` directly
later; `harness update` keeps those edits.
