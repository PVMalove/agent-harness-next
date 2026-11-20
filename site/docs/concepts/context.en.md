# Context management

The context cost depends on how long a step runs, not on the volume of skills. One step can take many
rounds and hours, and the accumulated history starts to get in the way: the agent stops seeing the main point. So the
history is compressed at step boundaries, and the data a step needs arrives as a prepared package.

## Session hygiene

| Method | What it does | When |
| --- | --- | --- |
| History compression | Turns the history into a summary and keeps the recorded decisions | At a step boundary, after you record the decisions in the glossary, an ADR, or the tracker |
| Full clear | Starts the session from a blank slate | Before a new ticket |
| Handoff document | Passes the state of the work to another session or model | When the work continues in another window |

The names and availability of these commands depend on the runtime; the meaning is the same — you may
compress the history only where the decisions are already recorded outside the session.

## When to compress

Do not compress in the middle of a step: the thread of reasoning is lost, and the work starts over. On the contrary,
after the decisions of a round are recorded in the glossary, an ADR, or a ticket, you can compress the history without loss —
everything essential already lies in files.

## Context Package

For the pipeline roles, the context is not "collected" in a dialogue but assembled deterministically.

- **Contents.** The diff, the starting files, a bounded project graph, the relevant tests, the cards of
  architectural decisions, and the source hashes.
- **No model.** The package is assembled deterministically, without a call to an LLM: the same input gives the
  same package.
- **Immutability.** The package is fixed for the step. The role works with it, not with what has since
  changed in the repository.
- **Freshness.** Before every run, the source hashes are compared. If a source changed, the package is
  stale, and this is visible before the work, not after the result diverges.
- **Pointers, not text.** Project memory enters the package as pointers: title, status, path, and
  hash. You open the source text only when needed.
- **Budget.** The package has a token ceiling and quotas by source type: the context is limited
  in advance, not after an overflow happens.

The package is registered in the ledger, so later you can answer the question of exactly what data the
role worked with.

## Next

- [Worktrees](worktrees.md)
- ["/implement"](../guides/implement.md)
- [CLI](../reference/cli.md)
