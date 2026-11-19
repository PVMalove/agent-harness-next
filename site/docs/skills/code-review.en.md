# /code-review — Two-axis review

`/code-review` reviews the diff since a fixed point (commit, branch, tag, or merge-base) along two
axes in parallel subagents and shows the reports side by side. The skill never changes code.

- **Standards:** whether the code follows the repository's documented standards. On top of them
  applies the Fowler code-smell baseline from `references/smell-baseline.md`. A repository standard
  overrides the baseline, and each smell is a judgement call, never a hard violation.
- **Spec:** whether the code implements the originating ticket or specification.

## Spec sources

The skill finds the ticket from references in the commits or the named PR/MR, a path argument, or a
spec file under `docs/`, `specs/` or `.scratch/`. When the ticket names `## Parent: #<epic>`, the
skill also reads the epic. The spec's `## Non-Goals & Rejected Alternatives` and
`## Surgical File & Contract Changes`, together with the ticket's `## Out of scope`,
`## Contract touchpoints` and `## Relevant Files (Discovery Context)`, show where the change went
beyond the task. Without a spec, the Spec axis is skipped and the report says so.

## Output

The axis reports appear under `## Standards` and `## Spec` headings, never merged or reranked,
followed by one summary line per axis. The report language comes from `language` in
`.harness/project.json`. For the `/implement` route (a coordinator Context Package, delta-review),
the rules are in `references/gated-route.md`.

[Source SKILL.md](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/code-review/SKILL.md)
