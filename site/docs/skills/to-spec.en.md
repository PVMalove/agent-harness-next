# /to-spec — Technical specification

Run `/to-spec` explicitly (`$to-spec` in Codex) after `/grilling`, `/grill-me`, or `/grill-with-docs`. The skill carries
the goal, accepted choices with their option numbers, and reasons for rejecting alternatives
into the specification. For a direct invocation, first approve the files the skill can read. The
skill reads files only within the approved scope and never changes code, tests, project
configuration, `CONTEXT.md`, ADRs, or Discovery Context.

## Approval

- Discovery Context lists the files the skill can read, cite, and include in its change plan.
  If `artifacts/discovery-context.md` is missing or empty, approve a minimal list of paths.
  A previously declined path requires fresh approval.
- For an unresolved technical choice, the skill shows an options matrix. Reply `1`, `2`, or
  `3` to select an available option. Use `details 2` or `details all` for an explanation in
  chat without file writes.
- With open blockers, explicitly request `Draft — has open blockers` to save a draft. It lists
  each blocker and the work that depends on it.
- Before approval, the skill checks that the epic's highest-impact risks have requirements and
  observable outcomes. For a migration, it checks whether the spec covers reading the old format
  and retrying after a partial failure. It raises gaps in the same approval conversation.

## Output

Once you approve the path, the skill saves the specification in its task folder under
`docs/tasks/`. For a child task this is the epic folder, where the skill first looks for
`artifacts/discovery-context.md`. The document describes file and contract changes, edge cases,
and verifiable acceptance criteria. For a complex epic, `Goal & Scope` identifies the first
end-to-end scenario to demonstrate, why it comes first, and how to verify it independently of
later slices. If the write fails, the skill returns the full text in chat.

`/publish-epic` publishes the epic and sets up its integration branch. Once the spec is approved,
request revisions or run `/publish-epic` and then `/to-tickets`, or `/implement`, manually when
its prerequisites are met.
[Git and epic workflow](../agents/git-workflow.md)

[Source SKILL.md](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/to-spec/SKILL.md)
