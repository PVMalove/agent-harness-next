# /to-spec — Technical specification

Run `/to-spec` explicitly (`$to-spec` in Codex) after `/grilling`, `/grill-me`, or `/grill-with-docs`. The skill carries
the goal, accepted choices with their option numbers, and reasons for rejecting alternatives
into the specification. For a direct invocation, first approve the files the skill can read.

## Approval

- Discovery Context lists the files the skill can read, cite, and include in its change plan.
  If `artifacts/discovery-context.md` is missing or empty, approve a minimal list of paths.
  A previously declined path requires fresh approval.
- For an unresolved technical choice, the skill shows an options matrix. Reply `1`, `2`, or
  `3` to select an available option. Use `details 2` or `details all` for an explanation in
  chat without file writes.
- With open blockers, explicitly request `Draft — has open blockers` to save a draft. It lists
  each blocker and the work that depends on it.

## Output

Once you approve the path, the skill saves the specification in its task folder under
`docs/tasks/`. For a child task this is the epic folder, where the skill first looks for
`artifacts/discovery-context.md`. The document describes file and contract changes, edge cases, and verifiable
acceptance criteria. If the write fails, the skill returns the full text in chat.

Epic publication and branch setup are separate steps. Once the spec is approved, request
revisions or run `/to-tickets` or `/implement` manually when its prerequisites are met.
[Git and epic workflow](../agents/git-workflow.md)

[Source SKILL.md](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/to-spec/SKILL.md)
