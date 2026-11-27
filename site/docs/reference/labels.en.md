# Labels

Each axis has its own label, and the axes do not mix. The pipeline state is a separate axis from who
does the work: a ticket can be `status::ready` and `hitl`, and these are two different statements.

## Axes

| Axis | Values | Applied by |
| --- | --- | --- |
| Type | `type::bug`, `type::feature`, `type::refactoring`, `type::chore`, `type::security`, `type::performance`, `type::hotfix` | `/triage` |
| Execution mode | `hitl`, `afk` | `/triage`, `/to-tickets` |
| State | `status::specs`, `status::ready`, `status::in-progress`, `status::blocked`, `status::done` | `/triage`, `/publish-epic`, `/to-tickets`, `/implement`, `/fast-implement`, `/to-pull-requests` |
| Route | `pipeline::fast`, `pipeline::full` | `/to-tickets` |
| Context | `task-report::required`, `resolution::wontfix`, `rca::done` | `/publish-epic`, `/to-tickets`, `/triage`, the `/diagnosing-bugs` RCA phase |
| PR kind | `pr::ticket`, `pr::integration` | `/to-pull-requests` |
| Wayfinder | `wayfinder:map`, `wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling`, `wayfinder:task` | `/wayfinder` |

`hitl` means that a human does the work following a guide; `afk` means that the task can be handed to an agent.
`/to-tickets` derives `pipeline::fast` or `pipeline::full` from the scope estimate in story points: a small
task takes the short path, a large one takes the full cycle with gates.

The `pr::*` axis labels PRs, not tickets, and every PR carries exactly one such label. `pr::ticket`
marks the PR of one ticket, including the PR of an epic-less ticket into `base_branch`; it inherits
the ticket's `type::*`. `pr::integration` marks any PR whose head is an `integration/*` branch,
whatever its target; it carries no `type::*`, because it collects tickets of several types.
`rca::done` means the bug ticket was created from a completed RCA: it goes next to `type::bug` and
never replaces it.

The optional informational axes `priority::*`, `severity::*`, and `env::*` (target project only) are
described in the target project's `.harness/instructions/triage-labels.md`.

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

After the confirmed merge, `/to-pull-requests` replaces `status::in-progress` with `status::done` and closes the
ticket; a ticket the tracker closed by itself through `Closes #<ID>` gets the label right after the close is verified.

A rejected ticket loses its `status::*` label, gets `resolution::wontfix`, and is closed.

## Where each label is applied

| Step | What it applies |
| --- | --- |
| `/triage` | Type, execution mode, state; a rejection closes the ticket with `resolution::wontfix` |
| `/publish-epic` | `type::*`, `status::specs` and `task-report::required` on the epic |
| `/to-tickets` | Mode, the `pipeline::*` route, `status::ready` or `status::blocked` |
| `/implement`, `/fast-implement` | `status::in-progress` in place of the current state label |
| `/to-pull-requests` | Ticket PR: `pr::ticket` and the ticket's `type::*`; integration PR: `pr::integration` without `type::*`. After a merge: `status::done` in place of `status::in-progress`; `status::blocked` → `status::ready` on the unblocked dependents. With `--release <epic>`, after the integration PR merges into `base_branch`: `status::done` in place of the epic's `status::specs` |
| The `/diagnosing-bugs` RCA phase | After the developer's explicit "yes": `type::bug` and `rca::done` on a new bug ticket; `status::blocked` on the stopped ticket when the bug blocks it |

## Next

- [Workflow](../guides/workflow.md)
- [“/implement”](../guides/implement.md)
