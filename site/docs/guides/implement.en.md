# /implement

`/implement` is a pipeline with explicit gates and approvals: dispatched roles write the
implementation, and the session coordinates. The route is enabled only by the `backend-orchestration`
capability; without it, use `/fast-implement`. The command is started manually and in a new, clean
session.

## When to use

| Situation | Command |
| --- | --- |
| A task with independent boundaries or a mandatory independent check | `/implement` |
| A small task whose direction is not under discussion | `/fast-implement` |
| A human does the implementation from a ready guide | `/to-guide` |

The route is strictly tied to the ticket label: auto-selection skips `pipeline::fast` tickets, and a
ticket that is named explicitly runs the full cycle regardless of its label. There is no shortened
path between review and QA; the shortened path is called `/fast-implement`.

## Pre-flight

1. **Blockers.** Check that the ticket has no open blockers; otherwise the work stops.
2. **State label.** Replace the current `status::*` with `status::in-progress` before creating the
   branch and making any edits, and check that it is the only one.
3. **Integration ref.** Take the branch from the ticket's `## Integration Branch` section; if there is
   none, take it from the parent epic or from the project's `base_branch`.
4. **Issue worktree.** Create the ticket's worktree from the integration branch: `batch create`
   refuses to work with a worktree that is not in `git worktree list`.
5. **Scope.** Run `batch preflight` with the same flags that will go to `batch create`, including
   `--allowed-path` and the Definition of Done items. The TDD requirement is recorded as a separate DoD
   item.

## Gates

| Gate | What happens | Decision | Artifact |
| --- | --- | --- | --- |
| architect | The plan: seam, boundaries, order of edits | by `approval_policy` | the accepted architect report |
| developer | Implementation by the plan, tests before code | by `approval_policy` | candidate commit |
| code-review | Two axes, Standards and Spec, independently | by `approval_policy` | the review report on both axes |
| qa | A full run on the pinned candidate, Release Gate | by `approval_policy` | QA evidence for the SHA |
| publish | The accepted SHA is declared published | by `approval_policy` | the publication record |

The order is strict: the coordinator rejects `dispatch create --role developer` until the batch has
an accepted architect report. The approval policy is set in the orchestration configuration: gates can
be passed manually, or automatic acceptance can be allowed by the policy `approval_policy: auto`. The
list of stops (integrity, budget, recovery route) stays closed in that case, and only a human
bypasses it.

<figure class="ah-diagram">
  <div class="ah-diagram-bar">
    <figcaption>The five pipeline gates. The diagram shows manual approval.</figcaption>
    <button class="ah-diagram-expand" type="button" aria-haspopup="dialog">Expand</button>
    <a class="ah-diagram-open" href="../../assets/diagrams/implement-gates.html" target="_blank" rel="noopener">Open separately ↗</a>
  </div>
  <iframe class="ah-diagram-frame" data-theme-sync src="../../assets/diagrams/implement-gates.html" title="/implement: gates and approval" loading="lazy"></iframe>
</figure>

## Hybrid publication contract

This is a strictly opt-in route: only the selected capability enables it, and no other build
activates it. The developer creates a candidate commit; the work report stays `reported` until a decision
under `approval_policy`. Only the developer publishes the accepted SHA through publish, and a person then separately invokes
`/to-pull-requests`. The agent opens the PR only after explicit confirmation. The `integration next` command names the next step from the
integration record. The adapter only transports what is already approved: it does not decide what to
publish, and it does not open a PR.

## Liveness and recovery

- **Model self-report.** As its first action, the role confirms the active model. A mismatch with the
  model in the brief moves the dispatch to `blocked`, and the report is not accepted.
- **Heartbeat and watchdog.** The role sends a heartbeat, and the coordinator polls the status; a
  silent dispatch is raised to a human as a blocker.
- **Early blocked report.** The developer may report a blocker before the commit and name a recovery
  route; the coordinator does not invent a commit in its place.
- **Stopping and cancelling are a human decision.** `batch resume-stop` sets and clears a pause,
  `batch rewind` returns the batch to a previous step, and `batch abandon` closes a dead-end batch.
  All three need approval and a reason.
- **The human trail is not edited.** The state in `.harness/orchestration/state/` is read only through
  the CLI: it is an audit trail, not a working file.

<figure class="ah-diagram">
  <div class="ah-diagram-bar">
    <figcaption>How a dispatch moves between states and where a human decision is needed.</figcaption>
    <button class="ah-diagram-expand" type="button" aria-haspopup="dialog">Expand</button>
    <a class="ah-diagram-open" href="../../assets/diagrams/dispatch-lifecycle.html" target="_blank" rel="noopener">Open separately ↗</a>
  </div>
  <iframe class="ah-diagram-frame" data-theme-sync src="../../assets/diagrams/dispatch-lifecycle.html" title="The lifecycle of a dispatch and a batch" loading="lazy"></iframe>
</figure>

## Add-ons on top of the pipeline

| When | What |
| --- | --- |
| After publish | `/to-pull-requests` — the PR and wrap-up: branch check, PR body, closing the ticket |
| A PR body is needed | the `pr-composer` subagent fills the template and returns the path to the file |
| A `hitl` ticket | `/to-guide` prepares a guide with prompts for manual implementation |
| Before the first pipeline run | `/setup-labels` creates the labels in the tracker once |
| A closed epic | `/delivery-stats` shows the cost of the work on the epic |

`/to-pull-requests` and `/to-guide` do not start automatically: a human calls them.

## Coordinator commands

```bash
python3 .harness/orchestration/coordinator.py --repo . batch list --open --ticket '#102'
python3 .harness/orchestration/coordinator.py --repo . batch decision-packet --batch <batch-id>
python3 .harness/orchestration/coordinator.py --repo . dispatch status --batch <batch-id> --stale-after 3600
python3 .harness/orchestration/coordinator.py --repo . ledger validate --full
```

`batch decision-packet` collects compact evidence for approval, `dispatch status` shows the liveness
of the roles, and `ledger validate` checks the integrity of the audit chain. All three commands are
read-only.

## Next

- ["/fast-implement"](fast-implement.md)
- [QA gate and Release Gate](qa-gate.md)
- [Examples](examples.md)
