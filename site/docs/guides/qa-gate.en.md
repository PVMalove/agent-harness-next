# QA gate and Release Gate

The QA gate is a full, independent quality run on a pinned candidate. The Release Gate confirms that
exactly the tree that was checked is the one that was published. These are two different checks: the
first answers "the code works", the second answers "exactly what was checked reached the repository".

## QA gate

The gate runs the `qa_gate_commands` from `.harness/project.json` (linter, type check, tests) in an
isolated environment, not in the developer's working tree. QA does not reuse the developer's cache or
environment: otherwise the run proves only that everything was already built locally.

The full set is QA's duty. The developer gets targeted checks for their change, and the full run is
done on the final candidate. Each command is wrapped in a summary: on success, a PASS line; on
failure, the test totals, the failed nodes, the final exceptions, and the path to a sanitized log.
The full stdout does not reach the session.

If the `qa_gate_commands` field is empty, the check is not skipped: it stops and asks to fill in the
configuration. The command shell is set by the `shell` field: in a project where a bare `bash`
resolves to someone else's stub, `bash` is replaced with an explicit interpreter.

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
