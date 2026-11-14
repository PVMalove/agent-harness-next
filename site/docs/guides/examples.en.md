# Full examples

Below is one end-to-end walkthrough for each entry point. The epic about report export is shown twice,
in the `afk` and `hitl` branches, to show how `/implement` ends and how `/to-guide` ends.

## A single ticket

An incoming bug: dates in PDF reports appear one day earlier than in the interface. The scope fits in
one session, and no decomposition is needed.

1. **An issue arrives** from a user, with no labels and no comments.
2. **`/triage`** gathers context, checks that the work is not already done, and reproduces the defect:
   the report service takes the time without the project's time zone. The recommendation is
   `type::bug`, `afk`, `status::ready`.
3. **`/fast-implement`** passes pre-flight, sets `status::in-progress`, writes a failing test "date in
   the project time zone", fixes the defect, gets a green run, and after consent commits and pushes.
4. **`/to-pull-requests`** is started by a human: branch check, QA, PR body, publication.

If triage had returned `hitl`, step 3 would become `/to-guide`: a human would do the implementation
by following the guide. `/to-spec` and `/to-tickets` were not called in this chain.

## An epic-sized task: the afk branch

The feature "export reports to CSV" is worked out in one session, but it needs decomposition.

1. **`/grill-with-docs`** runs rounds: which reports are exported, who starts the export, how numbers
   are formatted. The term "Exportable report" is added to the glossary.
2. **`/to-spec`** finds the seam: the existing report formatting service. The epic is published with
   the label `status::specs` and the integration branch name `integration/reports`.
3. **`/to-tickets`** creates two vertical slices: "CSV formatting service" (`afk`, `status::ready`)
   and "Export button on the report page" (`afk`, `status::blocked`, waits for the first).
4. **`/implement`** for the first ticket runs pre-flight, an issue worktree from `integration/reports`,
   a batch with the Definition of Done, and then the gates: architect → developer → code-review → qa →
   publish.
5. **`/to-pull-requests`**: QA evidence for the published SHA is already accepted, so no repeated run
   is needed. The PR goes to `integration/reports` with the note `Related to #<ID>`.
6. **After the merge** the ticket is closed, and the dependent slice moves from `status::blocked` to
   `status::ready`. The next `/implement` takes it from the frontier.

## An epic-sized task: the hitl branch

The same epic, but a human performs the migration of working configurations: it is not given to an
autonomous agent.

1. **`/grill-with-docs`** → **`/to-spec`** → **`/to-tickets`**: the ticket "Migrate the export
   configuration" gets `hitl` and `status::ready`.
2. **`/to-guide`** studies the code, assigns the ticket to the current tracker user
   (`@me`), sets `status::in-progress`, and
   writes the guide: a file map and steps with prompts, each starting with a test.
3. **A human works next**: coding in their own environment, `/code-review`, `/qa-gate`, a PR with
   `Related to #<ID>`, the merge, and the closing of the ticket.

The epic stays open with a list of subtasks; it is closed by a separate decision.

## A large, undefined scope

The task "move authorization to an external provider" does not fit in one session: neither the
provider nor the user migration scheme is known.

1. **The map.** `/wayfinder` names the destination "all new sign-ins go through the external provider,
   local passwords are disabled", and then lays out the fog: the choice of provider is a fact, the
   migration of existing users is a decision.
2. **Map tickets.** A research ticket "Choose a provider" (`afk`) and a grilling ticket "Migration
   scheme" (`hitl`, blocked by the first).
3. **Walking the map.** The research ticket closes with a comparison of providers by price and SLA.
   The next session resolves the grilling ticket: the decision is "forced password reset at first
   sign-in, no bulk migration of hashes".
4. **The handoff.** The frontier is empty and the map is closed, so `/wayfinder` hands the work to
   `/to-spec` and does not move to implementation itself. After that, it goes as in the epic example.

## Next

- [Workflow](workflow.md)
- ["/implement"](implement.md)
- ["/fast-implement"](fast-implement.md)
