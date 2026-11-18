---
name: code-review
description: Review the changes since a fixed point (commit, branch, tag, or merge-base) along two axes — Standards (does the code follow this repo's documented coding standards?) and Spec (does the code match what the originating issue/spec asked for?). Runs both reviews in parallel sub-agents and reports them side by side. Use when the user wants to review a branch, a PR, work-in-progress changes, or asks to "review since X".
---

Two-axis review of the diff between `HEAD` and a fixed point the user supplies. Never edit code;
report findings only.

- **Standards** — does the code conform to this repo's documented coding standards?
- **Spec** — does the code faithfully implement the originating issue / spec?

Both axes run as **parallel sub-agents** so they don't pollute each other's context, then this skill aggregates their findings.

This workflow is runtime-neutral: use the existing manually configured review mechanism. It
must not launch a runtime-specific adapter, choose a provider or model, or change the reviewed
branch. Write both sub-agent briefs and the aggregated report in the
`language` from `.harness/project.json` (default `ru`), whatever the prompt's language.

The issue tracker should have been provided to you. If `docs/agents/issue-tracker.md` is missing, tell the user to run `harness update`, which seeds it from the harness templates. On GitLab, every `glab` command takes `-R <project-url>`; `<project-url>` and the other GitLab placeholders (`<host>`, `<project-id>`) are defined in `docs/agents/issue-tracker.md` → GitLab → Conventions.

## Process

### 1. Pin the fixed point

Whatever the user said is the fixed point — a commit SHA, branch name, tag, `main`, `HEAD~5`, etc. If they didn't specify one, ask for it.

If the user names a PR or MR, its target branch is the fixed point. Read the target and source branches — GitHub: `gh pr view <n> --json baseRefName,headRefName`; GitLab: `glab mr view <iid> -R <project-url> -F json` (`target_branch`, `source_branch`). Then run `git fetch origin <target>` and use `origin/<target>` as the fixed point. The current checkout must be the source branch; if it is not, tell the user instead of switching branches (see _Runtime boundary_).

Capture the diff command once: `git diff <fixed-point>...HEAD` (three-dot, so the comparison is against the merge-base). Also note the list of commits via `git log <fixed-point>..HEAD --oneline`.

Before going further, confirm the fixed point resolves (`git rev-parse <fixed-point>`) and the diff is non-empty. A bad ref or empty diff should fail here — not inside two parallel sub-agents.

For the gated `/implement` route (a coordinator Context Package and candidate SHA, or a
delta-review), read `references/gated-route.md`.

### 2. Identify the spec source

Look for the originating spec, in this order:

1. Issue references in the commit messages or the named PR/MR (`#123`, `Closes #45`, `Related to #45`, etc.) — fetch via the workflow in `docs/agents/issue-tracker.md`: GitHub `gh issue view <n> --comments`; GitLab `glab issue view <n> -R <project-url> --comments`. A GitLab `!67` is a merge request, not an issue: read it with `glab mr view 67 -R <project-url> --comments` (GitHub PR: `gh pr view <n> --comments`) and take its ticket from the `Closes #<ID>`/`Related to #<ID>` footer.
2. A path the user passed as an argument.
3. A spec file under `docs/`, `specs/`, or `.scratch/` matching the branch name or feature.
4. If nothing is found, ask the user where the spec is. If they say there isn't one, the **Spec** sub-agent will skip and report "no spec available".

When the ticket names `## Parent: #<epic>`, also fetch the epic. Its specification's
`## Non-Goals & Rejected Alternatives` and `## Surgical File & Contract Changes`, with the ticket's
`## Out of scope`, `## Contract touchpoints` and `## Relevant Files (Discovery Context)`, define
what counts as scope creep; pass them to the Spec axis.

### 3. Identify the standards sources

Anything in the repo that documents how code should be written, such as `CODING_STANDARDS.md` or `CONTRIBUTING.md`.

On top of whatever the repo documents, the Standards axis always carries the **smell baseline** below — a fixed set of Fowler code smells (_Refactoring_, ch.3) that applies even when a repo documents nothing. Two rules bind it:

- **The repo overrides.** A documented repo standard always wins; where it endorses something the baseline would flag, suppress the smell.
- **Always a judgement call.** Each smell is a labelled heuristic ("possible Feature Envy"), never a hard violation — and, like any standard here, skip anything tooling already enforces.

Read `references/smell-baseline.md` before launching the Standards axis.

### 4. Review both axes

Launch the `code-review-standards` and `code-review-spec` subagents defined in `.claude/agents/` through the coding application's manually configured mechanism. Wait for both reports, then return them to this primary session for aggregation. Do not replace either axis with an inline review.

**`code-review-standards` prompt** — include:

- The full diff command and commit list.
- The list of standards-source files you found in step 3, **plus `references/smell-baseline.md`** pasted in full — the sub-agent has no other access to it.

**`code-review-spec` prompt** — include:

- The diff command and commit list.
- The path or fetched contents of the spec, and of the parent epic's specification and the ticket's
  scope sections when step 2 found them.

If the spec is missing, skip the `code-review-spec` sub-agent and note this in the final report.

### 5. Aggregate

Present the two reports under `## Standards` and `## Spec` headings, verbatim or lightly cleaned. Do **not** merge or rerank findings — the two axes are deliberately separate (see _Why two axes_).

End with a one-line summary: total findings per axis, and the worst issue _within each axis_ (if any). Don't pick a single winner across axes — that's the reranking the separation exists to prevent.

## Why two axes

A change can pass one axis and fail the other:
- Code that follows every standard but implements the wrong thing → **Standards pass, Spec fail.**
- Code that does exactly what the issue asked but breaks the project's conventions → **Spec pass, Standards fail.**

Reporting them separately stops one axis from masking the other.
