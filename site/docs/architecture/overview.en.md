# Architecture overview

Policy and execution are separate. Python makes decisions and manages approvals. The Rust runtime stores
operational state and starts processes. Git stays the owner of history and candidates.

<div class="ah-arch">
  <div class="panel">
    <div class="layer">
      <div class="tag">Policy</div>
      <div class="nodes"><span class="node">coordinator</span> <span class="node">approvals</span> <span class="node primary">human</span></div>
    </div>
    <div class="layer">
      <div class="tag">Runtime</div>
      <div class="nodes"><span class="node ok">supervisor</span> <span class="node ok">reconcile</span> <span class="node ok">engine</span></div>
    </div>
    <div class="layer">
      <div class="tag">State</div>
      <div class="nodes"><span class="node">SQLite WAL</span> <span class="node">audit</span> <span class="node">leases</span></div>
    </div>
  </div>
  <div class="panel">
    <div class="layer">
      <div class="tag">Git</div>
      <div class="nodes"><span class="node">candidate</span> <span class="node">branch</span> <span class="node">worktree</span></div>
    </div>
    <div class="layer">
      <div class="tag">Project</div>
      <div class="nodes"><span class="node">project.json</span> <span class="node">harness.lock</span> <span class="node">REGISTRY.md</span></div>
    </div>
  </div>
</div>

## Policy and execution

Python is the policy layer. The coordinator plans a batch, collects approvals, and accepts role reports.
The Rust runtime is the trusted supervisor of the host. It executes only a brief that is already
approved, verifies the plan and image digests, and does not decide policy itself. Each handoff gets a
separate confirmation, so a role cannot widen its scope during the work.

Operational state lives in the runtime store, not in files that Python edits. This is the main rule:
each entity has exactly one writer, and a transaction saves each state transition instead of an
appended file line.

Git stays the owner of history. The candidate, the branches, and the worktrees are ordinary Git
objects, and the runtime does not rewrite them. The project contracts — `.harness/project.json`,
`harness.lock`, and `REGISTRY.md` — belong to the target repository. The harness installer updates
them, not the runtime.

## Who owns what

| Entity | Writer | What it means |
| --- | --- | --- |
| Batch/dispatch lifecycle | Rust runtime | Python makes the decision and the runtime saves it in a transaction. Python does not write to the store directly, only through IPC. |
| Approvals and policy | Python | A human and the policy layer make the decision; the runtime executes the saved decision. |
| Operational intent | Rust store | The idempotency key, the attempt, and reconcile live in one transaction. |
| Git history and candidate | Git | The candidate, the branches, and the worktrees are ordinary Git objects; the runtime does not rewrite them. |
| Audit | Rust store | A hash chain with a checkpoint for incremental verification. |

!!! note "A fallback writer is prohibited"

    If the runtime is unavailable, Python does not start writing to a file ledger "to continue".
    The operation returns a typed error with a remedy.

## Trust boundaries

The boundary runs between the Python policy layer, the Rust runtime, and the untrusted worker. The
runtime is the trusted supervisor of the host. The worker is a candidate in a container or in a
separate process.

| Boundary | Rule |
| --- | --- |
| Runtime socket | Only the peer uid/SID and a capability token; directory `0700`, socket `0600`. |
| Engine socket | Never mounted into a worker or a QA container. |
| Approval | The immutable brief binds the plan, the image, the policy digest, and the verification digest. |
| Secrets | They do not reach the command line, the logs, the audit, or the reports. |

For details, see the [Security](runtime.md) section and ADR 0021.

## Layers and the delivery model

| Layer | Source of truth | Responsibility |
| --- | --- | --- |
| Capability catalog | `harness/CAPABILITIES.json` | Resolves the snapshot contents and the dependencies between builds. |
| Skill packages | `skills/vendor/`, `skills/first-party/` | Instructions, translations, and overrides; nobody edits the vendor snapshot by hand. |
| Project snapshot | `.harness/skills/`, `harness.lock`, `REGISTRY.md` | Independent delivery into the target repository, drift, and provenance. |
| Project contract | `.harness/project.json` | The language, the base branch, the branch template, and the check commands. |
| Orchestration core | the coordinator and the ledger | Policy, approvals, batch lifecycle, audit, and role dispatch. |
| Evidence execution | the gate runner and evidence | Checks, sanitized evidence, and telemetry. |
| Runtime boundary | the project adapter | Delivers an already approved brief; it changes neither scope nor state. |

The delivery chain is `capability → skills → project snapshot → .harness/project.json → runtime`.
`harness init`, `adopt`, and `update` resolve the capability from the catalog, copy the packages, and
record the lock. Claude Code and Codex find the same snapshot through their native skill roots, and
`REGISTRY.md` stays the index of the installed set. After installation the target project runs on its
own: the source clone of the harness is not needed at run time.

## Discovery Pipeline

Context moves between sessions through verifiable artifacts, not through a retelling in chat:

1. `/grilling` proposes candidate paths and writes only the explicitly approved files into the artifact.
2. `/to-spec` saves this list in the epic, in the `## Relevant Files (Discovery Context)` section.
3. `/to-tickets` assigns the paths to tickets and builds the Path inventory.
4. The context builder reads the pinned commit and collects the exact diff, the start files, the
   related tests, the ADRs, and the precedent cards into an immutable Context Package.
5. The coordinator registers the package in the ledger and checks its freshness before a new dispatch.

## Backend orchestration

`backend-orchestration` is an opt-in capability on top of `engineering-suite`. The coordinator owns the
batch, the approval of each handoff, scope changes, the QA lane, and the acceptance of reports. A role
gets an immutable brief, confirms the model self-report, and sends a heartbeat. It cannot widen the
scope, choose a model, or merge a PR.

The regular `/implement` command goes through `architect → developer → code-review → qa → publish`.
Review and QA work with the pinned candidate SHA, and the PR stays a separate manual step.

## Next

- [Rust runtime](runtime.md)
- [Quick start](../getting-started/index.md)
- [Reference](../reference/index.md)
