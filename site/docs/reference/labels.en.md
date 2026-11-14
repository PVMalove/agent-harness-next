# Labels

Each axis has its own label, and the axes do not mix. The pipeline state is a separate axis from who
does the work: a ticket can be `status::ready` and `hitl`, and these are two different statements.

## Axes

| Axis | Values | Applied by |
| --- | --- | --- |
| Type | `type::bug`, `type::feature`, `type::refactoring`, `type::chore`, `type::security`, `type::performance`, `type::hotfix` | `/triage` |
| Execution mode | `hitl`, `afk` | `/triage`, `/to-tickets` |
| State | `status::specs`, `status::ready`, `status::in-progress`, `status::blocked` | `/triage`, `/to-spec`, `/to-tickets`, `/implement`, `/fast-implement`, `/to-pull-requests` |
| Route | `pipeline::fast`, `pipeline::full` | `/to-tickets` |
| Context | `task-report::required`, `resolution::wontfix` | `/to-spec`, `/to-tickets`, `/triage` |
| Wayfinder | `wayfinder:map`, `wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling`, `wayfinder:task` | `/wayfinder` |

`hitl` means that a human does the work following a guide; `afk` means that the task can be handed to an agent.
`/to-tickets` derives `pipeline::fast` or `pipeline::full` from the scope estimate in story points: a small
task takes the short path, a large one takes the full cycle with gates.

The optional informational axes `priority::*`, `severity::*`, and `env::*` (target project only) are
described in the target project's `docs/agents/triage-labels.md`.

## The single-label rule

The state axis holds exactly one label. The transition `status::ready` → `status::in-progress` replaces the
label and does not add a second one; the same applies to `status::blocked`. Two state labels are an error
that makes the route choice and the automatic ticket pick undefined.

The mode axis is not filled while `status::specs` is set: at the elaboration stage it is not yet decided who
will do the work. The `pipeline::*` route is not set on `hitl` tickets: the short path does not apply to them.

## State machine

1. **No state label.** The issue is implicitly considered "needs triage".
2. **`status::specs`.** An epic or a large task: a specification is written and tickets are sliced. Such a ticket is
   not taken into work.
3. **`status::ready`.** The ticket is fully described and can be taken. This is the state that the automatic pick
   selects.
4. **`status::in-progress`.** An active session is working on the ticket. `/implement` and `/fast-implement` set the
   label before the branch is created and before the first edit.
5. **`status::blocked`.** The ticket waits for a dependency or for a human answer. A block is set for a
   dependency on a result, not for an overlap of files.
6. **Back to `status::ready`.** The blocker clears when the predecessor is closed, and the predecessor is closed only
   after its merge is confirmed. An open PR, accepted QA, and a push do not remove the blocker.

After the merge and closing, the ticket keeps `status::in-progress`: the closed state itself means "done".

A rejected ticket loses its `status::*` label, gets `resolution::wontfix`, and is closed.

## Where each label is applied

| Step | What it applies |
| --- | --- |
| `/triage` | Type, execution mode, state; a rejection closes the ticket with `resolution::wontfix` |
| `/to-spec` | `status::specs` on the epic and `task-report::required` |
| `/to-tickets` | Mode, the `pipeline::*` route, `status::ready` or `status::blocked` |
| `/implement`, `/fast-implement` | `status::in-progress` in place of the current state label |
| `/to-pull-requests` | After a merge: `status::blocked` → `status::ready` on the unblocked dependents |

## Next

- [Workflow](../guides/workflow.md)
- [“/implement”](../guides/implement.md)
