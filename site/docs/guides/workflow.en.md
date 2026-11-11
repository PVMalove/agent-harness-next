# Workflow {#workflow-guide}

Choose a route from the current state of the task. After implementation, the agent checks the result
and publishes the issue branch. Opening a PR needs separate confirmation; a person performs the merge.

## Where to start {#entries}

- **You have a bug or a small ticket.** Run `/triage` to clarify requirements, blockers and execution mode.
  For an `afk` ticket labeled `pipeline::fast`, use [/fast-implement](fast-implement.md).
- **You have an idea or unclear requirements.** Start with [/grilling](../skills/grilling.md).
  In an existing repository, [/grill-with-docs](../skills/grill-with-docs.md) also records decisions.
- **The work is large and the route is uncertain.** [/wayfinder](../skills/wayfinder.md) helps work through
  decisions across sessions. After agreement, hand the result to `/to-spec`.
- **You have an approved specification.** `/to-tickets` splits it into independently verifiable tasks.

If you are unsure about the route, [/ask-matt](../skills/ask-matt.md) helps choose an entry point.

## Stages and results {#steps}

1. **Explore the idea.** Agree on the goal, scope and open questions.
2. **Write the specification.** `/to-spec` collects decisions and publishes them after agreement.
3. **Prepare tickets.** `/to-tickets` proposes slices, dependencies and estimates before publishing.
4. **Implement and check.** `/implement` takes roles through orchestration gates;
   `/fast-implement` handles a small task in the current session; `/to-guide` prepares instructions for a person.
5. **Prepare the PR.** After publishing the branch, invoke `/to-pull-requests` separately.
   The agent checks the branch and QA evidence and asks to open the PR. A person performs the merge.

A ready ticket does not need to repeat design and specification.

<figure class="ah-diagram">
  <div class="ah-diagram-bar">
    <figcaption>Which commands lead from each entry point to the merge, and what is skipped.</figcaption>
    <button class="ah-diagram-expand" type="button" aria-haspopup="dialog">Expand</button>
    <a class="ah-diagram-open" href="../../assets/diagrams/workflow-entries.html" target="_blank" rel="noopener">Open separately ↗</a>
  </div>
  <iframe class="ah-diagram-frame" data-theme-sync src="../../assets/diagrams/workflow-entries.html" title="Entry points and the five workflow steps" loading="lazy"></iframe>
</figure>

## Exploring the idea {#idea}

`/grill-me` supports discussion without a repository. `/grill-with-docs` works in an existing project
and records terminology and decisions. `/domain-modeling` clarifies the domain in `CONTEXT.md`;
an ADR records an agreed architectural choice that is hard to reverse.

The result is an agreed goal, scope and decisions that `/to-spec` can use.
Detailed questions and rules belong in the [skills catalog](../skills/index.md).

## Specification {#spec}

`/to-spec` uses requirements already discussed. The specification describes the problem, solution,
user scenarios, module boundaries, testing decisions, excluded scope and integration branch.
Review these decisions before publication. The agent does not reset an existing integration branch.

## Tickets {#tickets}

Each ticket must deliver a verifiable result. A dependency is needed when work requires another
ticket's result; overlapping files alone do not establish a blocker.

`/to-tickets` agrees on slices and estimates, then publishes tasks. Labels `pipeline::fast` and
`pipeline::full` choose the route; `hitl` and `afk` choose the implementer. A ready task receives
`status::ready`; a task with an open blocker receives `status::blocked`.

<figure class="ah-diagram">
  <div class="ah-diagram-bar">
    <figcaption>How a ticket moves through the labels <code>status::ready</code>, <code>status::in-progress</code>, and <code>status::blocked</code>.</figcaption>
    <button class="ah-diagram-expand" type="button" aria-haspopup="dialog">Expand</button>
    <a class="ah-diagram-open" href="../../assets/diagrams/ticket-status.html" target="_blank" rel="noopener">Open separately ↗</a>
  </div>
  <iframe class="ah-diagram-frame" data-theme-sync src="../../assets/diagrams/ticket-status.html" title="The state label of a ticket" loading="lazy"></iframe>
</figure>

## Context for roles {#discovery}

With `backend-orchestration` enabled, the coordinator prepares a Context Package: a pinned set of
sources, tests and decisions for a role. It checks package freshness before dispatching the role.
See the [orchestration guide](../backend-orchestration.md) for setup and execution.

## Next step {#next}

- [/implement](implement.md): independent roles and gates.
- [/fast-implement](fast-implement.md): a small ticket in one session.
- [TDD](tdd.md), [review](code-review.md), [QA](qa-gate.md): how the result is checked.
