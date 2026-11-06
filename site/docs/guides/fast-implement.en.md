# /fast-implement

`/fast-implement` is a single-pass route without a coordinator, an architect, independent QA, or
approval gates. The current session writes the implementation. The route is for a small task whose
direction is not under discussion.

## When to use

- The ticket is labeled `afk` and `pipeline::fast`. This is a small scope, usually up to three story
  points.
- The task fits within one verifiable boundary and does not need independent verification by a
  separate role.
- A `hitl` ticket never goes through this route: for it there is `/to-guide`, where a human does the
  implementation.

If the command receives an epic instead of a ticket, it takes the first suitable ticket on the
frontier: open, not blocked, not taken by anyone, and labeled `pipeline::fast` together with `afk`.
A ticket that is named explicitly but has no `pipeline::fast` label goes to `/implement`.

## Pre-flight

1. **Resolve the ticket.** An explicit `hitl` ticket stops the work and points to `/to-guide`; an
   explicit `afk` ticket without `pipeline::fast` stops it and points to `/implement`.
2. **Check blockers.** An open blocker stops the work, and the ticket must be marked
   `status::blocked`.
3. **Mark it in progress, before the branch and any edits.** Replace the current `status::*` with
   `status::in-progress`:

   ```bash
   gh issue edit 102 --remove-label status::ready --remove-label status::blocked \
     --add-label status::in-progress
   ```

   Then check that `status::in-progress` is the only state label. A failed write is a stop, not a
   reason to continue without the label.
4. **Branch.** Create an issue branch from the ticket's integration branch; the name must match the
   project's `branch_pattern` and must not match the protected branches.

## Steps

1. **Test first.** New behavior starts with a failing test per `/tdd` at the agreed seam.
2. **Implementation.** Write the minimum code to make the test green, then refactor without changing
   behavior.
3. **Review by consent.** Offer `/code-review`; if it is declined, record the refusal explicitly.
4. **Commit and push.** After separate consent, make a semantic commit and push the issue branch,
   reporting the hash and the push result.
5. **Offer publication.** Name `/to-pull-requests` and stop: a human opens the PR.

<figure class="ah-diagram">
  <div class="ah-diagram-bar">
    <figcaption>Route selection by ticket labels and the five steps of the single-pass path.</figcaption>
    <button class="ah-diagram-expand" type="button" aria-haspopup="dialog">Expand</button>
    <a class="ah-diagram-open" href="../../assets/diagrams/fast-implement-route.html" target="_blank" rel="noopener">Open separately ↗</a>
  </div>
  <iframe class="ah-diagram-frame" data-theme-sync src="../../assets/diagrams/fast-implement-route.html" title="/fast-implement: route and steps" loading="lazy"></iframe>
</figure>

## How it differs from /implement

| Aspect | `/fast-implement` | `/implement` |
| --- | --- | --- |
| Who writes the code | the current session | dispatched roles managed by the coordinator |
| Gates | none | architect → developer → code-review → qa → publish |
| Approval | human consent for review, commit, and push | approval at every gate by policy |
| Independent QA | no, a full run at the end of the session | yes, clean-room on the pinned candidate |
| Artifacts | a commit in the issue branch | candidate commit, brief, reports, ledger |
| Requires capability | no | `backend-orchestration` |

## Next

- ["/implement"](implement.md)
- [TDD](tdd.md)
- [Code review](code-review.md)
