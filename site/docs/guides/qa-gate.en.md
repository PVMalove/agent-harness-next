# QA gate and Release Gate

The QA gate runs the project's full set of checks. In backend orchestration, an independent QA role
checks a pinned candidate in a clean environment. The Release Gate checks the candidate/target pair
and the resulting tree. A local `/qa-gate` run alone does not prove clean-room isolation.

## QA gate

`/qa-gate` reads `qa_gate_commands` and `shell` from `.harness/project.json` and runs commands in order
in the current checkout. If the configuration is absent in a linked worktree, it reads configuration
and the summary wrapper from the main worktree, while checks still run against the current checkout.
The first failure stops the run. An absent file or command list requires configuration first.

The wrapper returns PASS or a bounded failure summary with failed tests, diagnostics and a sanitized
log path. Passing targeted checks is not a full gate pass.

In `backend-orchestration`, `qa run` uses `verification_commands`, prepares a clean checkout of the
exact candidate and isolates the QA environment from developer work.
Preparation failures and code failures have different retry routes; see [clean-room QA](orchestration/qa.md).
Command fields and fallback rules are described in [verification settings](../getting-started/settings/orchestration/verification.md).

## Incremental verification

A full run at every step is too expensive, so the verification plan is computed, not chosen by eye.

- **ChangeImpact** builds the set of affected items from the project graph. Unknown impact widens the
  check and does not narrow it.
- **VerificationPlan** is pinned by a digest in the approval, so the set of checks cannot be replaced
  after the agreement.
- The developer and review get targeted checks by the plan, and QA gets a full run on the final SHA.
- A retry after a failure runs **only the failed nodes** by their exact identifiers. An empty
  selection does not count as success: it is `not_run`, and it needs a separate decision.

## Release Gate

The gate confirms the pair `{candidate_sha, target_sha}` and compares the tree after the merge. "Roughly
the same commit" is not accepted: if the tree in the target branch differs from the checked
candidate, the gate fails even when the ancestor commit matches. This way a squash merge and a manual
edit during conflict resolution do not pass unnoticed.

<figure class="ah-diagram">
  <div class="ah-diagram-bar">
    <figcaption>The verification plan, the full run on the final SHA, and the tree comparison in the Release Gate.</figcaption>
    <button class="ah-diagram-expand" type="button" aria-haspopup="dialog">Expand</button>
    <a class="ah-diagram-open" href="../../assets/diagrams/qa-release-gate.html" target="_blank" rel="noopener">Open separately ↗</a>
  </div>
  <iframe class="ah-diagram-frame" data-theme-sync src="../../assets/diagrams/qa-release-gate.html" title="QA gate and Release Gate" loading="lazy"></iframe>
</figure>

## CI evidence instead of a local run

If the tracker provides a full CI run, CI evidence for the combined result of the pull request is
accepted instead of local QA. Only completed evidence is accepted: passed or failed. When the set of
checks is incomplete, the command records nothing and reports that a local run is needed.

The commands and the configuration field are described in the [CLI reference](../reference/cli.md#ci-evidence).

## Next

- [Code review](code-review.md)
- [CLI and configuration](../reference/cli.md#ci-evidence)
- ["/implement"](implement.md)
